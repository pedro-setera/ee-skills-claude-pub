"""Heat table and simple air estimates for an enclosure, with the bench test that proves them.

What it does
    Reads a heat TOML (parts with watts and a maximum temperature, ambient, fans, vents, box) and writes `<out>/heat/heat_table.md`,
    `<out>/heat/heat_table.json` and `<out>/heat/bench_test_list.md`, plus check rows (`<out>/checks/heat_air.json`):
      total power                        sum of the parts' watts
      air temperature rise (fan)         dT = P / (rho cp Q), rho cp = 1206 J/(m3 K) (air near 25 C, sea level), Q = derate x the fans'
                                         free-air flow (derate default 0.5: a box with grilles, filters and boards in the way gets about
                                         half of the free-air figure). All of P is assumed to heat the air (heat through the walls is ignored).
      natural convection (no fan)        the heat leaves through the walls and, when there are intake and exhaust vents, by stack flow:
                                         P = dT (U A + rho cp Q(dT)), U = 1 / (1/h_in + t/k + 1/h_out) (defaults h_in 4, h_out 8 W/m2K
                                         including radiation, wall conductivity from the material table), A = outer surface x area_factor
                                         (0.85), stack flow Q = Cd A_v sqrt(2 g H dT / T) with Cd 0.6, A_v the series sum of the intake and
                                         exhaust areas, H the height between the vent centres. Solved for dT by bisection.
      part temperature                   T_air + W x theta (case-to-air resistance; give `theta_ca` per part from its data sheet) against its
                                         maximum minus `margin_k`. A part without `theta_ca` gets an ESTIMATE with an ASSUMED 25 K/W (6 K/W
                                         with a heat sink), shown in the row but never judged: its verdict is could_not_run, "datasheet
                                         theta_ca needed"
      intake to swept area ratio         one row per direction group (all the fans that blow the same way): the passive opening the group
                                         draws through (intake vents for exhaust fans, exhaust vents for intake fans, all of that kind
                                         summed) / the summed swept areas of the group's fans. Pass at 1.1 or more; the aim is 1.1 to 1.5, and
                                         above 1.5 the row says it is more open area than needed (see shielding SG-01 and dust), not a failure
      flow of several fans               fans of one direction work in parallel and their flows add; when there is an intake group AND an
                                         exhaust group they are in series, so the flow is the LOWER of the two groups' flows (a push-pull
                                         pair moves as much air as one of its fans, not two)
      fan suggestion                     the smallest size of a generic table (typical free-air flows, approximate, real fans differ by 2x) whose
                                         flow gives the target rise, with the intake area it needs
      flags (from a layout study)        a sensitive part inside a fan's air stream; a part dissipating more than `path_min_w` outside every air
                                         path (the box between an intake vent and a fan, expanded by `path_margin_mm`, and the fan's own stream)
    Every row says "estimate, prove on the bench". The bench test list gives: how to run to steady state, where to log, what the thresholds
    are, with the predicted number next to an empty measured column.
    Limits: a well-mixed box (one air temperature), steady state, no radiation to the parts, no altitude correction (air thins about 1 %
    per 100 m of height above sea level: multiply the flow need), fan curves ignored (only the free-air figure and the derate), no pressure drop
    of dust filters, no solar load. Good to choose a fan size and to compare arrangements within about 30 to 50 %; it does not replace the run.

Why it exists (the real failure, told without names)
    A board ran hot in a closed box because the heat estimate was done once, in a head, against the fan's free-air number; the fan sat
    behind a board, and a sensitive part sat in its jet. A written table with the derate, the path flags and
    a bench list made the two faults visible before the box was built.

Usage
    python -I scripts/heat_air.py HEAT.toml [--project DIR] [--out DIR]

Config (the heat TOML; units W, C, mm, m3/h)
    [heat]  ambient_c = 25, derate = 0.5, target_rise_k = 10, margin_k = 10, path_min_w = 0.5, path_margin_mm = 10,
            layout = "layout.toml" (optional, from layout_study.py), variant = "A", h_in = 4, h_out = 8, area_factor = 0.85
    [box]   outer = [x, y, z], wall_t = 2.0, material = "aluminium" | "steel" | "plastic" (or conductivity_w_mk = ...),
            vent_height_mm = (height between the intake and exhaust vent centres; default 0.5 x z)
    [[part]] name (the name of the block in the layout), watts, max_c, heat_sink = false, theta_ca = K/W (optional), tags = []
    [[fan]]  name, size_mm, free_air_m3h (or free_air_cfm), blade_d, hub_d, direction = "in" | "out" (out = exhaust fan, draws through intake vents)
    [[vent]] name, kind = "intake" | "exhaust", open_area_mm2
    [fan_table]  "40" = 12.0, ... (override the generic sizes: size mm = free-air m3/h)

Exit codes: 0 all rows pass; 1 a row failed; 2 input missing or a row could not run (a part without `theta_ca`).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import math
import shutil

import mech_common as mc

RATIO_LO, RATIO_HI = 1.1, 1.5     # passive opening / swept area: pass from RATIO_LO; above RATIO_HI is a note, not a failure
RATIO_HIGH_NOTE = "more open area than needed; see shielding SG-01 (openings against the wavelength) and dust"
RATIO_RULE = "1.1 or more; 1.1 to 1.5 is the aim (estimate, prove on the bench)"
RHO_CP = 1206.0        # J/(m3 K), air near 25 C at sea level
G = 9.81
# typical free-air flow of common axial fans, m3/h (approximate; real fans vary by 2x between makers and speeds)
FAN_TABLE = {25: 3.0, 30: 5.0, 40: 12.0, 50: 20.0, 60: 30.0, 70: 40.0, 80: 55.0, 92: 75.0, 120: 110.0, 140: 150.0}
CONDUCTIVITY = {"aluminium": 140.0, "steel": 50.0, "plastic": 0.2}      # W/(m K), typical
CFM_TO_M3H = 1.699


def swept_area_mm2(size, blade_d=None, hub_d=None):
    b = blade_d or size - 4.0
    h = hub_d or 0.4 * b
    return math.pi / 4 * (b * b - h * h)


# ---------------------------------------------------------------- estimates ------------------------------------------
def rise_forced(p_w: float, flow_m3h: float, derate: float) -> float:
    """Air temperature rise in kelvin for p_w watts and the fans' free-air flow in m3/h (derated)."""
    q = flow_m3h * derate / 3600.0
    return float("inf") if q <= 0 else p_w / (RHO_CP * q)


def rise_natural(p_w, outer_mm, wall_t_mm, k, h_in=4.0, h_out=8.0, area_factor=0.85, vent_area_mm2=0.0, vent_h_mm=0.0, t_amb_c=25.0) -> float:
    """Air temperature rise in kelvin by wall conduction/convection plus stack flow through vents (bisection on dT)."""
    x, y, z = [v / 1000.0 for v in outer_mm]
    a = 2 * (x * y + y * z + x * z) * area_factor
    u = 1.0 / (1.0 / h_in + (wall_t_mm / 1000.0) / k + 1.0 / h_out)
    t_k = t_amb_c + 273.15
    av = vent_area_mm2 / 1e6
    hv = vent_h_mm / 1000.0

    def removed(dt):
        q = 0.6 * av * math.sqrt(max(2 * G * hv * dt / t_k, 0.0)) if av > 0 and hv > 0 else 0.0
        return dt * (u * a + RHO_CP * q)
    lo, hi = 0.0, 500.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if removed(mid) < p_w:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def series_area(a1, a2):
    return 0.0 if a1 <= 0 or a2 <= 0 else 1.0 / math.sqrt(1.0 / a1 ** 2 + 1.0 / a2 ** 2)


def fan_groups(fans):
    """Fans split by direction: {"out": [...], "in": [...]} (only the groups that exist). "out" = exhaust fans, which draw the
    air in through the passive INTAKE vents; "in" = intake fans, which push it out through the passive EXHAUST vents."""
    g = {}
    for f in fans:
        g.setdefault(f.get("direction", "out"), []).append(f)
    return g


def group_flow(groups):
    """(flow m3/h, text). Fans of one direction are in parallel: their free-air flows add. An exhaust group and an intake group
    are in series: the air has to pass both, so the flow is the LOWER of the two group flows (never the sum)."""
    names = {"out": "exhaust", "in": "intake"}
    per = {d: sum(f["_flow"] for f in fs) for d, fs in groups.items()}
    parts = [f"{names[d]} fan(s) {'+'.join(str(f.get('name', '?')) for f in fs)} {per[d]:g} m3/h free air (in parallel, flows add)"
             for d, fs in groups.items()]
    if len(per) == 2:
        flow = min(per.values())
        return flow, "; ".join(parts) + f"; an intake group and an exhaust group are in series, so the lower flow counts: {flow:g} m3/h"
    flow = sum(per.values())
    return flow, parts[0] if parts else ""


def suggest_fan(p_w, target_rise, derate, table=None):
    """(size mm, typical free-air m3/h, needed free-air m3/h, swept area mm2, intake area range mm2) or None when even the largest is too small."""
    table = table or FAN_TABLE
    need = p_w / (RHO_CP * target_rise) / derate * 3600.0
    for size in sorted(table):
        if table[size] >= need:
            sw = swept_area_mm2(size)
            return size, table[size], need, sw
    return None


# ---------------------------------------------------------------- geometry flags (needs a layout) ----------------------
def _hull(a, b):
    return tuple(min(a[0][i], b[0][i]) for i in range(3)), tuple(max(a[1][i], b[1][i]) for i in range(3))


def _expand(b, m):
    return tuple(b[0][i] - m for i in range(3)), tuple(b[1][i] + m for i in range(3))


def fan_stream(v, fan):
    """The fan's own stream: its footprint carried across the whole box along the wall normal."""
    import layout_study as ls
    lo, hi = ls.fan_body(fan, v.inner)
    ax = ls.face_axes(fan["face"])[0]
    lo2, hi2 = list(lo), list(hi)
    lo2[ax], hi2[ax] = 0.0, v.inner[ax]
    return tuple(lo2), tuple(hi2)


def path_boxes(v, margin):
    import layout_study as ls
    boxes = []
    for f in v.fans:
        boxes.append(fan_stream(v, f))
        fb = ls.fan_body(f, v.inner)
        kind = "intake" if f["direction"] == "out" else "exhaust"
        for x in v.vents:
            if x["kind"] == kind:
                boxes.append(_hull(fb, ls.vent_box(x, v.inner)))
    return [_expand(b, margin) for b in boxes]


# ---------------------------------------------------------------- main calculation ------------------------------------
def analyse(cfg: dict, base_dir: str, rows: mc.Rows) -> dict:
    h = {"ambient_c": 25.0, "derate": 0.5, "target_rise_k": 10.0, "margin_k": 10.0, "path_min_w": 0.5, "path_margin_mm": 10.0,
         "h_in": 4.0, "h_out": 8.0, "area_factor": 0.85}
    h.update(cfg.get("heat", {}))
    parts = cfg.get("part", [])
    if not parts:
        raise mc.MechError("no [[part]] entries")
    fans = [dict(f) for f in cfg.get("fan", [])]
    vents = [dict(x) for x in cfg.get("vent", [])]
    table = {int(k): float(v) for k, v in (cfg.get("fan_table") or {}).items()} or FAN_TABLE
    layout = None
    if h.get("layout"):
        import layout_study as ls
        lp = h["layout"] if os.path.isabs(h["layout"]) else os.path.join(base_dir, h["layout"])
        if not os.path.isfile(lp):
            raise mc.MechError(f"layout file not found: {lp}")
        st = ls.load_study(lp)
        vid = h.get("variant") or next(iter(st["variant"]))
        layout = ls.build_variant(st, vid)
        if not vents:
            vents = [{"name": x["name"], "kind": x["kind"], "open_area_mm2": ls.vent_area(x)} for x in layout.vents]
        for f in fans:
            lf = next((q for q in layout.fans if q["name"] == f["name"]), None)
            if lf:
                f.setdefault("size_mm", lf["size"])
                f.setdefault("blade_d", lf["blade_d"])
                f.setdefault("hub_d", lf["hub_d"])
                f.setdefault("direction", lf["direction"])
    p_total = sum(float(p["watts"]) for p in parts)
    tgt, derate = float(h["target_rise_k"]), float(h["derate"])
    res = {"p_total": p_total, "fan_groups": [], "parts": []}
    rows.add("HEAT-01", "heat", "total power of the parts", f"{p_total:g} W", "sum of the heat table (estimate, prove on the bench)", "pass")
    # flow and rise: fans of one direction add (parallel); an intake group and an exhaust group are in series (the lower flow)
    for f in fans:
        d = str(f.get("direction", "out")).lower()
        if d not in ("in", "out"):
            raise mc.MechError(f"fan {f.get('name', '?')}: direction must be \"in\" or \"out\", not {f.get('direction')!r}")
        f["direction"] = d
        f["_flow"] = float(f["free_air_m3h"]) if f.get("free_air_m3h") is not None else float(f.get("free_air_cfm", 0.0)) * CFM_TO_M3H
    groups = fan_groups(fans)
    flow, flow_how = group_flow(groups)
    box = cfg.get("box", {})
    if fans and flow > 0:
        rise = rise_forced(p_total, flow, derate)
        how = f"{flow_how} x derate {derate:g}"
    else:
        outer = box.get("outer") or (layout and [layout.inner[i] + 2 * layout.wall for i in range(3)])
        if not outer:
            raise mc.MechError("no fan: [box] outer = [x, y, z] is needed for the natural convection estimate")
        k = float(box.get("conductivity_w_mk") or CONDUCTIVITY.get(str(box.get("material", "aluminium")).lower(), 140.0))
        av = series_area(sum(float(x["open_area_mm2"]) for x in vents if x["kind"] == "intake"), sum(float(x["open_area_mm2"]) for x in vents if x["kind"] == "exhaust"))
        rise = rise_natural(p_total, outer, float(box.get("wall_t", 2.0)), k, h["h_in"], h["h_out"], h["area_factor"], av,
                            float(box.get("vent_height_mm", outer[2] * 0.5)), h["ambient_c"])
        how = f"natural convection (walls k {k:g} W/mK" + (f", stack flow through {av:.0f} mm2" if av else ", sealed") + ")"
    res["rise_k"], res["rise_how"] = rise, how
    rows.add("HEAT-02", "heat", "air temperature rise inside the box", f"{rise:.1f} K by {how}",
             f"<= {tgt:g} K (estimate, prove on the bench)", "pass" if rise <= tgt else "fail")
    # parts
    amb = float(h["ambient_c"])
    for i, p in enumerate(parts):
        w = float(p["watts"])
        theta = p.get("theta_ca")
        assumed = theta is None
        if assumed:
            theta = 6.0 if p.get("heat_sink") else 25.0
        t_air = amb + (rise if math.isfinite(rise) else 0.0)
        t_part = t_air + w * float(theta)
        mx = p.get("max_c")
        lim = None if mx is None else float(mx) - float(h["margin_k"])
        lim_txt = "" if lim is None else f"<= {lim:g} C = max {mx:g} - margin {h['margin_k']:g}"
        entry = {"name": p["name"], "watts": w, "max_c": mx, "heat_sink": bool(p.get("heat_sink")), "theta": theta, "theta_assumed": assumed,
                 "t_part": t_part, "tags": list(p.get("tags", []))}
        res["parts"].append(entry)
        if mx is None:
            rows.add(f"HEAT-P{i + 1:02d}", "heat", f"part {p['name']} temperature", f"{t_part:.0f} C", "no maximum given", "na")
            continue
        if assumed:
            # an assumed resistance may not decide a verdict either way: the estimate stays visible, the row cannot be judged
            rows.add(f"HEAT-P{i + 1:02d}", "heat",
                     f"part {p['name']}: {w:g} W x {theta:g} K/W (assumed) + air {t_air:.0f} C",
                     f"{t_part:.0f} C (estimate with an assumed theta; datasheet theta_ca needed)",
                     f"datasheet theta_ca needed, then {lim_txt} (estimate, prove on the bench)",
                     "could_not_run")
            continue
        rows.add(f"HEAT-P{i + 1:02d}", "heat",
                 f"part {p['name']}: {w:g} W x {theta:g} K/W + air {t_air:.0f} C",
                 f"{t_part:.0f} C", f"{lim_txt} (estimate, prove on the bench)",
                 "pass" if t_part <= lim else "fail")
    # fan groups and the intake / swept ratio: one row per direction group
    for d, fs in groups.items():
        kind = "intake" if d == "out" else "exhaust"
        label = "exhaust fans" if d == "out" else "intake fans"
        fnames = "+".join(str(f["name"]) for f in fs)
        sw = sum(swept_area_mm2(float(f.get("size_mm", 40)), f.get("blade_d"), f.get("hub_d")) for f in fs)
        area = sum(float(x["open_area_mm2"]) for x in vents if x["kind"] == kind)
        ratio = area / sw if sw else 0.0
        res["fan_groups"].append({"direction": d, "fans": [f["name"] for f in fs], "swept_mm2": sw, "passive_area_mm2": area,
                                  "ratio": ratio, "flow_m3h": sum(f["_flow"] for f in fs)})
        what = f"{label} {fnames}: {kind} opening {area:.0f} mm2 / swept {sw:.0f} mm2"
        if area <= 0:
            rows.add(f"HEAT-R-{fnames}", "heat", what, f"no {kind} vent listed", RATIO_RULE, "fail")
            continue
        value = f"{ratio:.2f}"
        if ratio > RATIO_HI:
            value += "; " + RATIO_HIGH_NOTE
        rows.add(f"HEAT-R-{fnames}", "heat", what, value, RATIO_RULE, "pass" if ratio >= RATIO_LO else "fail")
    # suggestion
    sug = suggest_fan(p_total, tgt, derate, table)
    if sug:
        size, typ, need, sw = sug
        res["suggestion"] = {"size": size, "typical_m3h": typ, "needed_m3h": need, "swept_mm2": sw, "intake_mm2": (1.1 * sw, 1.5 * sw)}
        rows.add("HEAT-FAN", "heat", f"fan suggestion for a {tgt:g} K rise at {p_total:g} W",
                 f"{size} mm fan (typical {typ:g} m3/h) for {need:.1f} m3/h free air needed; intake {1.1 * sw:.0f} to {1.5 * sw:.0f} mm2",
                 "generic table, approximate (estimate, prove on the bench)", "pass")
    else:
        res["suggestion"] = None
        rows.add("HEAT-FAN", "heat", f"fan suggestion for a {tgt:g} K rise at {p_total:g} W", f"needs {p_total / (RHO_CP * tgt) / derate * 3600:.0f} m3/h free air",
                 "larger than the largest size of the table: use more fans or a heat sink on the hot part", "fail")
    # layout flags
    if layout is not None and (layout.fans or layout.vents):
        import layout_study as ls
        for e in res["parts"]:
            b = layout.blocks.get(e["name"])
            if b is None:
                rows.add(f"HEAT-S-{e['name']}", "heat", f"part {e['name']} found in the layout", "not in the layout", "names must match the layout's blocks", "fail")
                continue
            bb = (b["lo"], b["hi"])
            if "sensitive" in b["tags"] or "sensitive" in e["tags"]:
                hit = [f["name"] for f in layout.fans if ls.aabb_gap(fan_stream(layout, f), bb) < -0.01]
                rows.add(f"HEAT-S-{e['name']}", "heat", f"sensitive part {e['name']} in a fan's air stream",
                         ("in the stream of " + ", ".join(hit)) if hit else "outside every stream", "no sensitive part in the jet or suction path (estimate, prove on the bench)",
                         "fail" if hit else "pass")
        pb = path_boxes(layout, float(h["path_margin_mm"]))
        for e in res["parts"]:
            if e["watts"] < float(h["path_min_w"]):
                continue
            b = layout.blocks.get(e["name"])
            if b is None:
                continue
            inpath = any(ls.aabb_gap(x, (b["lo"], b["hi"])) < -0.01 for x in pb)
            rows.add(f"HEAT-A-{e['name']}", "heat", f"part {e['name']} ({e['watts']:g} W) has an air path", "in a path" if inpath else "outside every air path",
                     f"inside the box between an intake vent and a fan, +{h['path_margin_mm']:g} mm (estimate, prove on the bench)", "pass" if inpath else "fail")
    else:
        rows.add("HEAT-FLAGS", "heat", "sensitive-part and no-path flags", "no layout (set [heat] layout) or no fan and vent in it", "needs a layout study", "na")
    res["h"] = h
    return res


def write_outputs(res: dict, outd: str, name: str) -> None:
    h = res["h"]
    L = [f"# Heat table: {name}", "", "Every number is an estimate, prove on the bench (see bench_test_list.md).", "",
         f"- Ambient {h['ambient_c']:g} C, target air rise {h['target_rise_k']:g} K, derate {h['derate']:g}, part margin {h['margin_k']:g} K",
         f"- Total {res['p_total']:g} W; air rise {res['rise_k']:.1f} K by {res['rise_how']}", "",
         "| Part | W | Max C | Sink | theta K/W | Estimated C |", "|---|---|---|---|---|---|"]
    for e in res["parts"]:
        L.append(f"| {e['name']} | {e['watts']:g} | {'' if e['max_c'] is None else format(e['max_c'], 'g')} | {'yes' if e['heat_sink'] else 'no'} | "
                 f"{e['theta']:g}{' (assumed)' if e['theta_assumed'] else ''} | {e['t_part']:.0f} |")
    assumed = [e["name"] for e in res["parts"] if e["theta_assumed"]]
    if assumed:
        L += ["", "Assumed theta (the estimate is shown but not judged; datasheet theta_ca needed): " + ", ".join(assumed)]
    if res["fan_groups"]:
        L += ["", "| Fan group | Fans | Flow m3/h | Swept mm2 (sum) | Passive opening mm2 | Ratio (pass from 1.1, aim 1.1 to 1.5) |", "|---|---|---|---|---|---|"]
        for f in res["fan_groups"]:
            note = " (" + RATIO_HIGH_NOTE + ")" if f["ratio"] > RATIO_HI else ""
            L.append(f"| {'exhaust' if f['direction'] == 'out' else 'intake'} | {', '.join(f['fans'])} | {f['flow_m3h']:g} | {f['swept_mm2']:.0f} | "
                     f"{f['passive_area_mm2']:.0f} | {f['ratio']:.2f}{note} |")
    s = res.get("suggestion")
    L += ["", "## Fan suggestion", ""]
    if s:
        L.append(f"A {s['size']} mm fan (typical {s['typical_m3h']:g} m3/h free air; need {s['needed_m3h']:.1f} m3/h) with an intake of "
                 f"{s['intake_mm2'][0]:.0f} to {s['intake_mm2'][1]:.0f} mm2. Generic table: check the chosen fan's own data sheet.")
    else:
        L.append("No size of the generic table is enough: more fans, a heat sink on the hottest part, or less power.")
    mc.atomic_write(os.path.join(outd, "heat_table.md"), "\n".join(L) + "\n")
    import json
    mc.atomic_write(os.path.join(outd, "heat_table.json"), json.dumps({k: v for k, v in res.items() if k != "h"}, indent=1, default=str))
    B = [f"# Bench test list: {name}", "", "The numbers in this document are estimates. This run proves or corrects them.", "",
         "## Set-up", "",
         "1. Final enclosure, closed, with the lid, gaskets, grilles and filters as built; the fan wired as in service. Orientation as in service.",
         "2. Ambient thermometer 0.5 m from the box, out of the fan's stream; write the value at the start and the end.",
         "3. Thermocouples (or an IR camera with a known emissivity sticker) on: the case of every part in the table below; the air at the intake; "
         "the air at the exhaust or at the top inside the box; the outer wall at the hottest spot.",
         "4. Power the box at its WORST case load (every part at its maximum draw), not the average.", "",
         "## Run", "",
         "1. Log every 30 s. Start the clock when the load is applied.",
         "2. Steady state = every logged point changes by less than 0.5 K in 10 minutes (usually 30 to 60 minutes for a metal box).",
         "3. Write the values at steady state; then switch the fan off (if it can fail) and note the time each part needs to reach its limit.", "",
         "## Thresholds", "", "| Point | Estimated | Limit | Measured | Verdict |", "|---|---|---|---|---|",
         f"| Air rise inside minus ambient | {res['rise_k']:.1f} K | {h['target_rise_k']:g} K | | |"]
    for e in res["parts"]:
        lim = "" if e["max_c"] is None else f"{float(e['max_c']) - float(h['margin_k']):g} C"
        B.append(f"| {e['name']} case | {e['t_part']:.0f} C | {lim} | | |")
    B += ["", "## Also look for", "",
          "- A sensitive part that changes behaviour (frequency, noise, reading) when the fan runs: it is in the stream; move it or add a baffle.",
          "- Hot spots on the outer wall above 60 C where a hand can touch.",
          "- Fan noise and the current drawn by the fan at the supply voltage used.",
          "- Repeat at the highest ambient the product is rated for, or add the difference (rated ambient minus test ambient) to every reading."]
    mc.atomic_write(os.path.join(outd, "bench_test_list.md"), "\n".join(B) + "\n")


def run(args) -> int:
    try:
        job = mc.resolve(args)
    except mc.MechError:
        if not args.out:
            raise
        job = mc.Job(os.getcwd(), mc.load_config(os.getcwd()), os.path.abspath(args.out))
    if not os.path.isfile(args.heat):
        print(f"could not run: heat file not found: {args.heat}", file=sys.stderr)
        return 2
    cfg = mc.load_toml(args.heat)
    rows = mc.Rows()
    outd = os.path.join(job.out, "heat")
    if os.path.isdir(outd):
        shutil.rmtree(outd, ignore_errors=True)
    os.makedirs(outd, exist_ok=True)
    res = analyse(cfg, os.path.dirname(os.path.abspath(args.heat)), rows)
    write_outputs(res, outd, cfg.get("heat", {}).get("name", os.path.splitext(os.path.basename(args.heat))[0]))
    ins = [args.heat]
    if cfg.get("heat", {}).get("layout"):
        lp = cfg["heat"]["layout"]
        ins.append(lp if os.path.isabs(lp) else os.path.join(os.path.dirname(os.path.abspath(args.heat)), lp))
    rows.write(job.out, "heat_air.py", ins)
    rows.print_table(only_bad=True)
    print(f"heat table and bench list in {outd}")
    print(rows.headline())
    return rows.exit_code()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="heat table and air estimates")
    ap.add_argument("heat", help="heat TOML")
    mc.add_std_args(ap)
    args = ap.parse_args(argv)
    try:
        return run(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
