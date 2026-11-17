"""Current worksheet of a board: resistance, drop, loss and heating of each power path, with a geometric search
for the narrowest copper in tracks AND in filled zones. A first-order check, not a thermal simulation.

What it does, per power path named in board.toml (net, current, allowed drop and rise)
    Sections in series make a path. A section is
      measured   a centre line across the copper (from / to, or two pads): the net's own copper on each named
                 layer (zone fill, pads, tracks, via rings, merged) is cut across the path every 0.1 mm; the
                 copper length on each cut is the width there. The narrowest cut is the neck. The resistance is
                 the sum over the cuts (exact for current that flows along the line).
      stated     width x length on a layer, as designed (for copper that a straight line does not describe)
      tracks     the routed tracks of a net: lengths per width, read from the board
    For every section: resistance at 20 C on the NOMINAL geometry and on the WORST finished geometry (width
    minus the etch tolerance, minimum finished thickness), the hot resistance, drop and loss at the path current,
    and the steady-state rise. Copper in parallel on several layers: conductances add for the drop; heating is
    rated as ONE conductor of the summed thickness over the shared width, carrying the full current.
    Necks: the rise is a BOUND, from the rise of the parent copper (the section's usual width) up to the
    long-track rise at the neck's width. PASS only when the high value meets the limit; FAIL when even the low
    value does not, or when the high value is beyond neck_fail_factor times the limit; between: UNKNOWN (widen it,
    add a parallel path or copper under it, or put it on the bench infrared list). A neck that stays narrow for
    long_neck_mm or more is a track and is judged on the high value alone. A part's own land (kind "package") is
    listed as package-limited: a bench infrared item unless it passes on the high value.
    Via groups: barrel cross-section pi * t * (d - t) at the minimum hole-wall plating t, resistance, the ratio
    of the summed barrel section to the narrowest copper they join (flagged under 0.5), at least two vias on a
    power path, the worst via taken at 1.25 times its share. Never "amperes per via".
    Pulses (fault, inrush, crowbar): adiabatic rise from the time integral of the squared current, the
    cross-section, copper's volumetric heat capacity and temperature-dependent resistivity, starting from the
    hot steady state; for pulses of a second or more the smaller of that and the steady-state value at the
    pulse current. A peak above the limit (default: the laminate's glass transition temperature) is FAIL.
    No current-density criterion anywhere.

Method and sources
    Resistance: R = rho * L / (w * t), rho = 1.724e-8 ohm m at 20 C, +0.393 % per K.
    Steady-state rise: the IPC-2152-based relation for external conductors fitted in Brooks and Adam, "PCB
    Design Guide to Via and Trace Currents and Temperatures", chapter 5, equation (5.5), coefficients of its
    Table 5.1 (external): dT = 215.3 * I^2 * W^-1.15 * Th^-1.0, I in amperes, W and Th in mils. It is used for
    inner copper too, at its own thickness (conservative). The rise is iterated with the hot resistance until it
    changes by less than 0.5 C; a result that does not settle, or lies beyond 500 C, is FAIL "runaway".
    Adiabatic pulse: T2 = 20 + ((1 + a (T1 - 20)) * exp(a * rho20 * I2t / (A^2 * cv)) - 1) / a, cv = 3.45e6 J/(m3 K).
    Why this method: an older worksheet used a chart formula on nominal sizes; a book check showed that nominal
    sizes, cold resistance, per-layer ratings of stacked copper, long-track charts on short necks and per-via
    ampere figures each mislead. And the rule check does not see pour necks at all: a pour deliberately narrowed
    far below what its current needs passed it.

Limits printed with every result
    Estimate, IPC-2152 basis; not a verified ampacity. Steady state, DC or RMS current, still air, no planes, a
    long track: an upper bound for a board with planes, the average along a track and not its hottest spot.
    Laminate, air and real copper thickness move any rise by 20 % or more. Necks, pads and vias get bounds.
    Pulses get an upper bound. Not modelled: heat from parts and neighbouring copper, air flow, the enclosure.

Usage
    python -I neck_check.py --project <hardware/board folder>             result in <project>/out/current_worksheet.md
    python -I neck_check.py <board.kicad_pcb> --out <folder> [--net NAME --current A]
    Without a path in board.toml (and without --net) the script lists the copper of every net that has a zone or
    a track of 0.4 mm or more, and the result is UNKNOWN: currents are the designer's to state.

board.toml keys
    [current]
    ambient = 45.0            # deg C, local (UNKNOWN until measured: say what you assumed); default 25, marked assumed
    max_rise = 20.0           # deg C allowed steady-state rise
    etch_tolerance = 0.05     # mm taken off every width for the worst geometry
    min_thickness_factor = 0.85   # minimum finished copper thickness as a share of the nominal
    via_wall_um = 18.0        # minimum hole-wall plating (not given: 18 um is ASSUMED and the via rows are UNKNOWN)
    tg = 130.0                # deg C, the laminate's glass transition; pulse_limit defaults to it
    neck_fail_factor = 3.0    # a neck whose long-track rise passes this many times the limit is FAIL (0: UNKNOWN)
    long_neck_mm = 10.0
    copper_um = { "F.Cu" = 35.0, "In1.Cu" = 15.2 }    # nominal thickness; default: the board's stack-up
    [[current.path]]
    name = "input: connector to regulator"
    net = "VIN"               # default net of its sections
    current = 2.0             # A, worst sustained
    max_drop_mv = 50.0        # optional: the drop budget of this path
    series_mohm = 40.0        # optional: parts in series (fuse, ferrite)
    pulses = [ { name = "short-circuit pulse", current = 10.0, time = 1e-5 } ]      # or { i2t = 0.4 } in A2 s
    [[current.path.section]]
    name = "band from the connector"
    from = [10.0, -20.0]      # KiCad frame, mm; or from_pad = "J1.1", to_pad = "U2.1"
    to = [10.0, -15.0]
    half = 1.5                # half length of each cut: only the path's own copper is counted
    layers = ["F.Cu", "B.Cu"] # copper in parallel; the first is the main layer
    kind = "main"             # or "package": a part's own land
    current = 0.7             # optional: this section carries another current
    accepted = "bench infrared at full load, test T3, user YYYY-MM-DD"     # optional: a neck the user accepted
    [[current.path.section]]
    name = "corridor as designed"
    layer = "F.Cu"   width = 3.0   length = 40.0                       # stated
    also = [ { layer = "In2.Cu", width = 3.0, length = 40.0 } ]         # stated copper in parallel
    [[current.path.section]]
    name = "routed feed"
    tracks = "VOUT_A"         # the routed tracks of this net (optional: min_width, layer)
    [[current.path.vias]]
    name = "layer change at the connector"
    count = 3   drill = 0.3   from_layer = "F.Cu"   to_layer = "B.Cu"   # count 0: counted in box = [x0, y0, x1, y1]

Exit codes
    0  PASS: every section, via group, pulse and drop budget passes
    1  FAIL or UNKNOWN: any of them does not pass (UNKNOWN is never a pass), or no path is defined
    2  CANNOT RUN: KiCad's Python not found, unreadable board, a net or pad of board.toml that is not on the board
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402

RHO20, ALPHA, CV = 1.724e-8, 0.00393, 3.45e6
MIL = 0.0254
CUT_STEP = 0.1
DEFAULTS = {"ambient": 25.0, "max_rise": 20.0, "etch_tolerance": 0.05, "min_thickness_factor": 0.85, "via_wall_um": 18.0,
            "tg": 130.0, "pulse_limit": -1.0, "neck_fail_factor": 3.0, "long_neck_mm": 10.0}
UNEVEN = 1.25                       # the worst via of a group against its even share
LIMITS_TEXT = ("Estimate, IPC-2152 basis; not a verified ampacity. Steady state, DC or RMS current, still air, no planes, "
               "a long track: an upper bound for a board with planes; the average along a track, not its hottest spot. "
               "Laminate, air and the real copper thickness move any rise by 20 % or more. Necks, pads and vias get "
               "bounds, not predictions; pulses get an upper bound. Not modelled: heat from parts and neighbouring "
               "copper, air flow, the enclosure. The bench thermal test is the proof.")


# ---- physics ----------------------------------------------------------------------------------------------------------
def rise_ipc(amps, width_mm, thick_um):
    """Steady-state rise (C) of a long external conductor: Brooks and Adam, chapter 5, equation (5.5)."""
    if width_mm <= 0 or thick_um <= 0:
        return float("inf")
    return 215.3 * amps * amps * (width_mm / MIL) ** -1.15 * (thick_um / 25.4) ** -1.0


def rise_hot(amps, width_mm, thick_um, ambient):
    """(self-consistent rise in C, settled?) The fitted rise holds for copper near room temperature; hotter copper
    has more resistance and so more loss. Iterated until the rise changes by less than 0.5 C."""
    r0 = rise_ipc(amps, width_mm, thick_um)
    if not math.isfinite(r0):
        return r0, False
    den = 1 + ALPHA * (25.0 + r0 - 20.0)
    r = r0
    for _ in range(40):
        new = r0 * (1 + ALPHA * (ambient + r - 20.0)) / den
        if new > 500.0:
            return new, False
        if abs(new - r) < 0.5:
            return new, True
        r = new
    return r, False


def width_needed(amps, thick_um, rise):
    return MIL * (215.3 * amps * amps / (rise * thick_um / 25.4)) ** (1 / 1.15)


def adiabatic(t_start, i2t, area_mm2):
    """Copper temperature after a pulse with no cooling (C)."""
    if area_mm2 <= 0:
        return float("inf")
    x = ALPHA * RHO20 * i2t / ((area_mm2 * 1e-6) ** 2 * CV)
    if x > 50:
        return float("inf")
    return 20.0 + ((1 + ALPHA * (t_start - 20.0)) * math.exp(x) - 1) / ALPHA


def r_mohm(length_mm, width_mm, thick_um):
    if width_mm <= 0 or thick_um <= 0:
        return float("inf")
    return RHO20 * (length_mm * 1e-3) / (width_mm * 1e-3 * thick_um * 1e-6) * 1e3


def hot_factor(temp):
    return 1 + ALPHA * (temp - 20.0)


# ---- the board's copper -----------------------------------------------------------------------------------------------
def stackup_copper(board_path):
    """{layer name: thickness in um} from the board file's stack-up; {} when it has none."""
    with open(board_path, encoding="utf-8", errors="replace") as f:
        txt = f.read(400000)
    i = txt.find("(stackup")
    if i < 0:
        return {}
    depth, k = 0, i
    while k < len(txt):
        if txt[k] == "(":
            depth += 1
        elif txt[k] == ")":
            depth -= 1
            if depth == 0:
                break
        k += 1
    out = {}
    for m in re.finditer(r'\(layer\s+"([^"]+)"\s*\(type\s+"copper"\)\s*\(thickness\s+([\d.]+)', txt[i:k]):
        out[m.group(1)] = float(m.group(2)) * 1000.0
    return out


def stackup_span(board_path, a, b):
    """Distance in mm between the middles of two copper layers through the stack-up; None when unknown."""
    with open(board_path, encoding="utf-8", errors="replace") as f:
        txt = f.read(400000)
    i = txt.find("(stackup")
    if i < 0:
        return None
    layers = re.findall(r'\(layer\s+"([^"]+)"\s*\(type\s+"([^"]+)"\)(?:(?!\(layer\s).)*?\(thickness\s+([\d.]+)', txt[i:i + 20000], re.S)
    names = [n for n, _, _ in layers]
    if a not in names or b not in names:
        return None
    ia, ib = sorted((names.index(a), names.index(b)))
    return sum(float(t) for _, _, t in layers[ia:ib + 1]) - float(layers[ia][2]) / 2 - float(layers[ib][2]) / 2


class Copper:
    """The net copper of a board, per (net, layer), as contours in mm (KiCad's frame)."""

    def __init__(self, board):
        import pcbnew
        self.p, self.board, self.cache = pcbnew, board, {}
        self.layer_id = {board.GetLayerName(lid): lid for lid in board.GetEnabledLayers().CuStack()}
        self.nets = {}
        for name in board.GetNetsByName().keys():
            self.nets[str(name)] = str(name)
        self.leaf = {}
        for n in self.nets:
            self.leaf.setdefault(kicad_io.leaf(n), []).append(n)

    def net(self, name):
        if name in self.nets:
            return name
        c = self.leaf.get(name, [])
        if len(c) == 1:
            return c[0]
        raise kicad_io.KicadIOError(f"the net '{name}' is " + ("not on the board" if not c else "ambiguous: " + ", ".join(c)))

    def layer(self, name):
        if name not in self.layer_id:
            raise kicad_io.KicadIOError(f"board.toml names the layer '{name}'; the board has {', '.join(self.layer_id)}")
        return self.layer_id[name]

    def contours(self, net, layer_name):
        key = (net, layer_name)
        if key in self.cache:
            return self.cache[key]
        p, b, lid = self.p, self.board, self.layer(layer_name)
        acc = p.SHAPE_POLY_SET()
        err = p.FromMM(0.005)
        for z in b.Zones():
            if z.GetIsRuleArea() or str(z.GetNetname()) != net or not z.IsOnLayer(lid):
                continue
            fp = z.GetFilledPolysList(lid)
            for i in range(fp.OutlineCount()):
                k = acc.AddOutline(fp.Outline(i))
                for h in range(fp.HoleCount(i)):
                    acc.AddHole(fp.Hole(i, h), k)
        for f in b.GetFootprints():
            for pad in f.Pads():
                if str(pad.GetNetname()) == net and pad.IsOnLayer(lid):
                    pad.TransformShapeToPolygon(acc, lid, 0, err, p.ERROR_INSIDE)
        for t in b.GetTracks():
            if str(t.GetNetname()) == net and t.IsOnLayer(lid):
                t.TransformShapeToPolygon(acc, lid, 0, err, p.ERROR_INSIDE)
        acc.Simplify()
        cont = []
        for poly in pcb_common.poly_points(acc):
            cont += poly
        self.cache[key] = cont
        return cont

    def pad_pos(self, spec):
        ref, _, num = spec.partition(".")
        for f in self.board.GetFootprints():
            if f.GetReference() == ref:
                for pad in f.Pads():
                    if str(pad.GetNumber()) == num:
                        q = pad.GetPosition()
                        return (self.p.ToMM(q.x), self.p.ToMM(q.y))
        raise kicad_io.KicadIOError(f"board.toml names the pad '{spec}', which is not on the board")

    def tracks(self, net, layer=None, min_width=0.0):
        """{(layer name, width): length} of a net's routed tracks."""
        out = {}
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_VIA" or str(t.GetNetname()) != net:
                continue
            ln = self.board.GetLayerName(t.GetLayer())
            w = round(self.p.ToMM(t.GetWidth()), 3)
            if (layer is None or ln == layer) and w >= min_width:
                out[(ln, w)] = out.get((ln, w), 0.0) + self.p.ToMM(t.GetLength())
        return out

    def vias(self, net, box=None):
        out = []
        for t in self.board.GetTracks():
            if t.GetClass() == "PCB_VIA" and str(t.GetNetname()) == net:
                q = t.GetPosition()
                x, y = self.p.ToMM(q.x), self.p.ToMM(q.y)
                if box is None or (box[0] <= x <= box[2] and box[1] <= y <= box[3]):
                    out.append((x, y, self.p.ToMM(t.GetDrill())))
        return out


def cut_width(cont, cx, cy, nx, ny, half):
    """Copper length on the cut through (cx, cy) along the unit direction (nx, ny), from -half to +half: even-odd
    rule over all contours on the line, clipped to the cut."""
    ts = []
    for c in cont:
        n = len(c)
        for i in range(n):
            (x1, y1), (x2, y2) = c[i], c[(i + 1) % n]
            d1 = -(x1 - cx) * ny + (y1 - cy) * nx
            d2 = -(x2 - cx) * ny + (y2 - cy) * nx
            if (d1 <= 0 < d2) or (d2 <= 0 < d1):
                f = d1 / (d1 - d2)
                ts.append((x1 + f * (x2 - x1) - cx) * nx + (y1 + f * (y2 - y1) - cy) * ny)
    ts.sort()
    w = 0.0
    for k in range(0, len(ts) - 1, 2):
        a, e = max(ts[k], -half), min(ts[k + 1], half)
        if e > a:
            w += e - a
    return w


def sweep(cont, p0, p1, half, step=CUT_STEP):
    """Widths on cuts across the line p0 -> p1, every `step` mm: [(distance along, width, x, y)]."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    if ln <= 0:
        raise kicad_io.KicadIOError("a section's centre line has no length")
    ux, uy = dx / ln, dy / ln
    out, k = [], 0
    while k * step <= ln + 1e-9:
        cx, cy = p0[0] + ux * k * step, p0[1] + uy * k * step
        out.append((k * step, cut_width(cont, cx, cy, -uy, ux, half), cx, cy))
        k += 1
    return out


# ---- the worksheet ----------------------------------------------------------------------------------------------------
def section_result(sec, path, cu, L, thick, notes):
    """Measure and rate one section. Returns a dict (see the keys below)."""
    amps = float(sec.get("current", path["current"]))
    net = cu.net(sec.get("net", path.get("net", ""))) if (sec.get("net") or path.get("net")) else None
    tol, tf, amb, lim = L["etch_tolerance"], L["min_thickness_factor"], L["ambient"], float(sec.get("max_rise", path.get("max_rise", L["max_rise"])))
    res = {"name": sec.get("name", "section"), "kind": sec.get("kind", "main"), "current": amps, "limit": lim, "layers": [],
           "notes": [], "accepted": sec.get("accepted")}

    def th(layer):
        if layer not in thick:
            raise kicad_io.KicadIOError(f"no copper thickness known for layer '{layer}' (give [current] copper_um)")
        return thick[layer]

    measured = "from" in sec or "from_pad" in sec
    if measured:
        if net is None:
            raise kicad_io.KicadIOError(f"section '{res['name']}': no net given")
        p0 = cu.pad_pos(sec["from_pad"]) if "from_pad" in sec else tuple(float(v) for v in sec["from"])
        p1 = cu.pad_pos(sec["to_pad"]) if "to_pad" in sec else tuple(float(v) for v in sec["to"])
        half = float(sec.get("half", 2.0))
        layers = sec.get("layers") or [sec.get("layer", "F.Cu")]
        res["type"], res["length"] = "measured", math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        for ly in layers:
            prof = sweep(cu.contours(net, ly), p0, p1, half)
            wmin = min(prof, key=lambda q: q[1])
            ws = sorted(q[1] for q in prof)
            usual = ws[len(ws) // 2]
            narrow = sum(1 for q in prof if q[1] <= max(wmin[1] * 1.1, wmin[1] + 0.02)) * CUT_STEP
            r_nom = sum(r_mohm(CUT_STEP, q[1], th(ly)) for q in prof[:-1]) if wmin[1] > 0 else float("inf")
            r_wst = sum(r_mohm(CUT_STEP, q[1] - tol, th(ly) * tf) for q in prof[:-1]) if wmin[1] - tol > 0 else float("inf")
            res["layers"].append({"layer": ly, "w_min": wmin[1], "at": [round(wmin[2], 2), round(wmin[3], 2)], "w_usual": usual,
                                  "narrow_len": narrow, "r20_nom": r_nom, "r20_worst": r_wst, "t": th(ly), "cuts": len(prof)})
            if wmin[1] >= 2 * half - 1e-6:
                res["notes"].append(f"{ly}: the copper is wider than the cut ({2 * half:.1f} mm) everywhere: the width is at "
                                    f"least that; a longer cut (half) would measure more")
    elif "tracks" in sec:
        tnet = cu.net(sec["tracks"])
        tr = cu.tracks(tnet, sec.get("layer"), float(sec.get("min_width", 0.0)))
        if not tr:
            raise kicad_io.KicadIOError(f"section '{res['name']}': the net '{tnet}' has no routed track that fits")
        res["type"], res["length"] = "tracks", sum(tr.values())
        wmin = min(w for _, w in tr)
        lyr = sorted({ly for ly, _ in tr})
        r_nom = sum(r_mohm(ln, w, th(ly)) for (ly, w), ln in tr.items())
        r_wst = sum(r_mohm(ln, w - tol, th(ly) * tf) for (ly, w), ln in tr.items())
        res["layers"].append({"layer": "+".join(lyr), "w_min": wmin, "at": None, "w_usual": wmin, "narrow_len": res["length"],
                              "r20_nom": r_nom, "r20_worst": r_wst, "t": min(th(ly) for ly in lyr), "cuts": 0})
        res["notes"].append("all routed tracks of the net taken in series (an upper bound when it branches): "
                            + ", ".join(f"{ly} {w:g} x {ln:.1f}" for (ly, w), ln in sorted(tr.items())))
    else:
        res["type"] = "stated"
        try:
            parts = [(sec["layer"], float(sec["width"]), float(sec["length"]))] + \
                    [(a["layer"], float(a["width"]), float(a["length"])) for a in sec.get("also", [])]
        except KeyError as e:
            raise kicad_io.KicadIOError(f"section '{res['name']}': give from/to (measured), tracks, or layer, width and "
                                        f"length (stated); missing {e}") from None
        res["length"] = parts[0][2]
        for ly, w, ln in parts:
            cu.layer(ly)
            res["layers"].append({"layer": ly, "w_min": w, "at": None, "w_usual": w, "narrow_len": ln,
                                  "r20_nom": r_mohm(ln, w, th(ly)), "r20_worst": r_mohm(ln, w - tol, th(ly) * tf), "t": th(ly),
                                  "cuts": 0})
        res["notes"].append("width and length as stated in board.toml, not measured on the board")
    lay = res["layers"]

    def par(key):
        good = [q[key] for q in lay if math.isfinite(q[key]) and q[key] > 0]
        return 1.0 / sum(1.0 / v for v in good) if good else float("inf")

    res["r20_nom"], res["r20_worst"] = par("r20_nom"), par("r20_worst")
    res["r_hot"] = res["r20_worst"] * hot_factor(amb + lim)
    res["drop_mv"] = amps * res["r_hot"]
    res["loss_w"] = amps * amps * res["r_hot"] / 1000.0
    # heating: one conductor of the summed (worst) thickness over the shared width
    t_sum = sum(q["t"] for q in lay) * tf
    w_neck = min(q["w_min"] for q in lay) - tol
    w_usual = min(q["w_usual"] for q in lay) - tol
    res["w_worst"], res["t_worst"] = w_neck, t_sum
    hi, ok_hi = rise_hot(amps, w_neck, t_sum, amb)
    lo, ok_lo = rise_hot(amps, w_usual, t_sum, amb)
    res["rise_high"], res["rise_low"] = hi, min(lo, hi)
    res["w_needed"] = width_needed(amps, t_sum, lim) + tol if amps > 0 else 0.0
    is_neck = res["type"] == "measured" and max(q["narrow_len"] for q in lay) < L["long_neck_mm"] and w_usual > w_neck * 1.15
    res["is_neck"] = is_neck
    if w_neck <= 0:
        verdict, why = "FAIL", "no copper left at the worst geometry (the path is cut or narrower than the etch tolerance)"
    elif not ok_hi and not is_neck:
        verdict, why = "FAIL", "runaway: the rise does not settle"
    elif hi <= lim:
        verdict, why = "PASS", ""
    elif not is_neck:
        verdict, why = "FAIL", f"long-track rise {hi:.0f} C over the limit {lim:.0f} C; needs {res['w_needed']:.2f} mm"
    elif res["rise_low"] > lim:
        verdict, why = "FAIL", f"even the parent copper rises {res['rise_low']:.0f} C (limit {lim:.0f} C)"
    elif L["neck_fail_factor"] > 0 and (hi > L["neck_fail_factor"] * lim or not ok_hi):
        verdict, why = "FAIL", (f"neck: long-track rise at its width {hi:.0f} C is over {L['neck_fail_factor']:g} x the limit; "
                                f"the current needs {res['w_needed']:.2f} mm")
    else:
        verdict, why = "UNKNOWN", (f"neck: rise between {res['rise_low']:.0f} C (parent copper) and {hi:.0f} C (long track at its "
                                   f"width); limit {lim:.0f} C: widen it, add copper under it, or bench infrared")
    if verdict != "PASS" and res["kind"] == "package":
        verdict, why = "UNKNOWN", "package-limited (the part's own land): bench infrared at full load; " + why
    if verdict != "PASS" and res["accepted"]:
        verdict, why = "ACCEPTED", f"{why}; accepted: {res['accepted']}"
    res["result"], res["why"] = verdict, why
    return res


def auto_inventory(cu):
    """Nets that carry power-like copper: [(net, zones on layers, tracks {(layer, w): len}, via count)]."""
    rows = []
    zones = {}
    for z in cu.board.Zones():
        if not z.GetIsRuleArea() and str(z.GetNetname()):
            zones.setdefault(str(z.GetNetname()), set()).update(cu.board.GetLayerName(lid) for lid in z.GetLayerSet().Seq())
    for net in sorted(cu.nets):
        if not net:
            continue
        tr = cu.tracks(net)
        if net in zones or any(w >= 0.4 for _, w in tr):
            rows.append((net, sorted(zones.get(net, [])), tr, len(cu.vias(net))))
    return rows


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Current worksheet: resistance, drop, loss, heating bounds and the narrowest copper of each power path.",
                              epilog="Paths come from board.toml [[current.path]]; see the top of this file. "
                                     "Exit codes: 0 pass, 1 fail or unknown, 2 could not run.")
    ap.add_argument("--net", help="quick look without board.toml: rate the routed tracks of this net")
    ap.add_argument("--current", type=float, help="the current for --net, in A")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                           # no message box, ever: warnings go to stderr
    job = pcb_common.resolve(a)
    cfg = job.cfg("current")
    L = pcb_common.Limits(cfg, DEFAULTS)
    lim_pulse = L["pulse_limit"] if L["pulse_limit"] > 0 else L["tg"]
    paths = [p for p in cfg.get("path", []) if isinstance(p, dict)]
    if a.net:
        if a.current is None:
            raise kicad_io.KicadIOError("--net needs --current")
        paths = [{"name": f"{a.net} (routed tracks)", "net": a.net, "current": a.current, "section": [{"name": "routed tracks", "tracks": a.net}]}]
    assumed = [k for k in ("ambient", "max_rise", "etch_tolerance", "min_thickness_factor", "tg") if L.origin[k] == "default"]
    wall_assumed = L.origin["via_wall_um"] == "default"
    with pcb_common.work_copy(job.board, "neck-check-") as copy:
        board = kicad_io.load_board(copy)
        cu = Copper(board)
        import pcbnew
        canon = stackup_copper(copy)                                    # by KiCad's own layer names
        thick_src = "the board's stack-up" if canon else "ASSUMED 35 um on every layer (the board has no stack-up)"
        thick = {name: canon.get(str(pcbnew.LayerName(lid)), 35.0) for name, lid in cu.layer_id.items()}
        for k, v in cfg.get("copper_um", {}).items():
            thick[k] = float(v)
            thick_src = "board.toml copper_um where given, else " + thick_src
        md = pcb_common.header("Current worksheet (estimate, IPC-2152 basis; not a verified ampacity)", job, "neck_check.py")
        md += [LIMITS_TEXT, "", "Method: resistance rho L / (w t) at 20 C and hot (copper at ambient + allowed rise), on the nominal "
               "and on the worst finished geometry (width - etch tolerance, minimum thickness); pass on the worst. Rise: "
               "IPC-2152-based external relation (Brooks and Adam, ch. 5, eq. 5.5), iterated with the hot resistance, stacked "
               "copper as one conductor of summed thickness. Necks found geometrically: cuts across each path every "
               f"{CUT_STEP} mm through the net's merged copper. No current-density criterion.", "",
               f"Copper thickness (nominal): {', '.join(f'{k} {v:g} um' for k, v in thick.items())}; from {thick_src}.", "",
               "Settings:", ""] + L.table() + [""]
        if assumed:
            md += [f"**ASSUMED (defaults, not from the project):** {', '.join(assumed)}. Local ambient stays UNKNOWN until measured.", ""]
        results, rows_all, n_fail, n_unknown = [], [], 0, 0
        if not paths:
            inv = auto_inventory(cu)
            md += ["## No power path is defined: UNKNOWN", "",
                   "board.toml names no [[current.path]] (net, current, sections), so nothing can be rated. The copper of the "
                   "nets that have a zone or a track of 0.4 mm or more is listed for the designer to state currents against:", "",
                   "| Net | Zones on | Narrowest track (mm) | Tracks (layer width x length mm) | Vias |", "|---|---|---|---|---|"]
            for net, zl, tr, nv in inv:
                wmin = f"{min(w for _, w in tr):g}" if tr else "-"
                trs = "; ".join(f"{ly} {w:g} x {ln:.1f}" for (ly, w), ln in sorted(tr.items())[:8]) + (" ..." if len(tr) > 8 else "")
                md.append(f"| {net} | {', '.join(zl) or '-'} | {wmin} | {trs or '-'} | {nv} |")
            n_unknown = 1
            results.append({"inventory": [{"net": n, "zones": z, "tracks": [[ly, w, round(ln, 2)] for (ly, w), ln in tr.items()],
                                           "vias": nv} for n, z, tr, nv in inv]})
        for path in paths:
            if "current" not in path:
                raise kicad_io.KicadIOError(f"path '{path.get('name', '?')}': current (A) is missing")
            amps = float(path["current"])
            secs = [section_result(s, path, cu, L, thick, None) for s in path.get("section", [])]
            if not secs:
                raise kicad_io.KicadIOError(f"path '{path.get('name', '?')}': no section")
            series = float(path.get("series_mohm", 0.0))
            pr = {"name": path.get("name", "path"), "net": path.get("net", ""), "current": amps, "sections": secs, "vias": [],
                  "pulses": [], "series_mohm": series}
            # vias
            narrow_area = min(s["w_worst"] * s["t_worst"] / 1000.0 for s in secs)        # mm2, the narrowest copper of the path
            r_vias = 0.0
            for v in path.get("vias", []):
                vnet = cu.net(v.get("net", path.get("net", "")))
                found = cu.vias(vnet, v.get("box"))
                count = int(v.get("count", 0)) or len(found)
                drill = float(v.get("drill", 0.0)) or (min(d for _, _, d in found) if found else 0.0)
                span = stackup_span(copy, v.get("from_layer", "F.Cu"), v.get("to_layer", "B.Cu"))
                span_note = ""
                if span is None:
                    span, span_note = pcb_common.mm(board.GetDesignSettings().GetBoardThickness()), " (board thickness: no stack-up)"
                t = L["via_wall_um"] / 1000.0
                vr = {"name": v.get("name", "vias"), "count": count, "drill": drill, "span": span, "wall_um": L["via_wall_um"]}
                if count < 1 or drill <= t:
                    vr.update({"result": "FAIL", "why": "no via found for this group" if count < 1 else "the drill is not larger than the wall"})
                else:
                    area = math.pi * t * (drill - t)
                    r_each = RHO20 * (span * 1e-3) / (area * 1e-6) * 1e3
                    vr.update({"area_each": area, "r_mohm": r_each / count * hot_factor(L["ambient"] + L["max_rise"]),
                               "ratio": count * area / narrow_area if narrow_area > 0 else 0.0})
                    r_vias += vr["r_mohm"]
                    why = []
                    if count < 2:
                        why.append("one via on a power path: use at least two")
                    if vr["ratio"] < 0.5:
                        why.append(f"barrel section {vr['ratio']:.2f} of the narrowest joined copper (under 0.5)")
                    vr["result"] = "FAIL" if why else ("UNKNOWN" if wall_assumed else "PASS")
                    vr["why"] = "; ".join(why) or (f"wall plating {L['via_wall_um']:g} um is ASSUMED: read the fabricator's minimum" if wall_assumed else "")
                    vr["why"] += span_note
                pr["vias"].append(vr)
            # totals
            r_hot = sum(s["r_hot"] for s in secs) + r_vias
            pr["r20_nom"], pr["r20_worst"], pr["r_hot"] = sum(s["r20_nom"] for s in secs), sum(s["r20_worst"] for s in secs), r_hot
            pr["drop_mv"] = sum(s["drop_mv"] for s in secs) + amps * (r_vias + series)
            pr["loss_w"] = sum(s["loss_w"] for s in secs) + amps * amps * r_vias / 1000.0
            budget = path.get("max_drop_mv")
            pr["budget"] = budget
            pr["drop_result"] = "NOT CHECKED" if budget is None else ("PASS" if pr["drop_mv"] <= float(budget) else "FAIL")
            # pulses
            for pu in path.get("pulses", []):
                ip = float(pu.get("current", 0.0))
                tp = float(pu.get("time", 0.0))
                i2t = float(pu["i2t"]) if "i2t" in pu else ip * ip * tp
                worst = None
                for s in secs:
                    t0 = L["ambient"] + min(s["rise_high"], s["limit"]) if math.isfinite(s["rise_high"]) else L["ambient"] + s["limit"]
                    share = s["current"] / amps if amps else 1.0
                    peak = adiabatic(t0, i2t * share * share, s["w_worst"] * s["t_worst"] / 1000.0)
                    if tp >= 1.0 and ip > 0:
                        steady, _ = rise_hot(ip * share, s["w_worst"], s["t_worst"], L["ambient"])
                        peak = min(peak, L["ambient"] + steady)
                    if worst is None or peak > worst[0]:
                        worst = (peak, s["name"])
                for vr in pr["vias"]:
                    if "area_each" in vr:
                        peak = adiabatic(L["ambient"] + L["max_rise"], i2t * (UNEVEN / vr["count"]) ** 2, vr["area_each"])
                        if worst is None or peak > worst[0]:
                            worst = (peak, f"{vr['name']} (worst via at {UNEVEN} x its share)")
                ok = worst is not None and worst[0] <= lim_pulse
                pr["pulses"].append({"name": pu.get("name", "pulse"), "i2t": i2t, "current": ip, "time": tp, "peak": worst[0] if worst else None,
                                     "where": worst[1] if worst else "", "limit": lim_pulse, "result": "PASS" if ok else "FAIL"})
            # markdown
            md += [f"## {pr['name']}: net {pr['net'] or '(per section)'}, {amps:g} A", "",
                   "| Section | Type | Layers | Length (mm) | Narrowest nominal (mm) | at (x, y) | Worst width x thickness (mm x um) | "
                   "R 20 C nominal (mOhm) | R 20 C worst (mOhm) | R hot worst (mOhm) | Drop (mV) | Loss (W) | Rise (C) | Limit (C) | "
                   "Needs (mm) | Result |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for s in secs:
                main_l = s["layers"][0]
                at = f"({main_l['at'][0]:.2f}, {main_l['at'][1]:.2f})" if main_l["at"] else "-"
                rise = f"{s['rise_low']:.1f} .. {s['rise_high']:.1f}" if s["is_neck"] else f"{s['rise_high']:.1f}"
                kind = s["type"] + (", package" if s["kind"] == "package" else "") + (", neck" if s["is_neck"] else "")
                md.append(f"| {s['name']} | {kind} | {' + '.join(q['layer'] for q in s['layers'])} | {s['length']:.1f} | "
                          f"{' / '.join(format(q['w_min'], '.2f') for q in s['layers'])} | {at} | {s['w_worst']:.2f} x {s['t_worst']:.1f} | "
                          f"{s['r20_nom']:.2f} | {s['r20_worst']:.2f} | {s['r_hot']:.2f} | {s['drop_mv']:.1f} | {s['loss_w']:.3f} | {rise} | "
                          f"{s['limit']:g} | {s['w_needed']:.2f} | {s['result']} |")
                rows_all.append((pr["name"], s))
                n_fail += s["result"] == "FAIL"
                n_unknown += s["result"] == "UNKNOWN"
            notes = [f"- {s['name']}: {s['result']}: {s['why']}" for s in secs if s["why"]] + \
                    [f"- {s['name']}: note: {n}" for s in secs for n in s["notes"]]
            md += [""] + notes + ([""] if notes else [])
            if pr["vias"]:
                md += ["| Via group | Count | Drill (mm) | Wall (um) | Barrel length (mm) | Resistance hot (mOhm) | Barrel section / narrowest copper | Result |",
                       "|---|---|---|---|---|---|---|---|"]
                for vr in pr["vias"]:
                    md.append(f"| {vr['name']} | {vr['count']} | {vr['drill']:.2f} | {vr['wall_um']:g} | {vr['span']:.2f} | "
                              f"{vr.get('r_mohm', float('nan')):.3f} | {vr.get('ratio', float('nan')):.2f} | {vr['result']}"
                              f"{': ' + vr['why'] if vr['why'] else ''} |")
                    n_fail += vr["result"] == "FAIL"
                    n_unknown += vr["result"] == "UNKNOWN"
                md.append("")
            if pr["pulses"]:
                md += ["| Pulse | I2t (A2 s) | Peak copper temperature, upper bound (C) | Where | Limit (C) | Result |", "|---|---|---|---|---|---|"]
                for pu in pr["pulses"]:
                    pk = "beyond the model" if pu["peak"] is None or not math.isfinite(pu["peak"]) else f"{pu['peak']:.0f}"
                    md.append(f"| {pu['name']} | {pu['i2t']:.3g} | {pk} | {pu['where']} | {pu['limit']:g} | {pu['result']} |")
                    n_fail += pu["result"] == "FAIL"
                md.append("")
            n_fail += pr["drop_result"] == "FAIL"
            md += [f"Path total: R 20 C nominal {pr['r20_nom']:.2f} mOhm, worst {pr['r20_worst']:.2f} mOhm, hot worst with vias "
                   f"{pr['r_hot']:.2f} mOhm; parts in series {series:g} mOhm; drop {pr['drop_mv']:.1f} mV at {amps:g} A"
                   + (f" against a budget of {float(budget):g} mV: {pr['drop_result']}" if budget is not None else
                      " (no drop budget given: NOT CHECKED)") + f"; copper loss {pr['loss_w']:.3f} W.", ""]
            results.append(pr)
        if rows_all:
            md += ["## Narrowest copper of every measured sweep", "",
                   "| Path | Section | Layer | Sweep (mm) | Narrowest cut (mm) | at (x, y) | Usual width (mm) | Stays narrow for (mm) |",
                   "|---|---|---|---|---|---|---|---|"]
            for pname, s in rows_all:
                if s["type"] != "measured":
                    continue
                for q in s["layers"]:
                    md.append(f"| {pname} | {s['name']} | {q['layer']} | {s['length']:.1f} | {q['w_min']:.2f} | ({q['at'][0]:.2f}, {q['at'][1]:.2f}) | "
                              f"{q['w_usual']:.2f} | {q['narrow_len']:.1f} |")
            md.append("")
        md += ["## Not checked", "",
               "The return path of each current unless it is given as a path of its own (ground is copper with resistance); "
               "connector contacts and the harness; loop inductance; thermal reliefs of pads; anything on a path that no "
               "section describes. A section's cuts are straight: copper that turns needs a section per leg."]
    result = pcb_common.verdict(n_fail, n_unknown)
    md += ["", f"**Result: {result}** ({n_fail} failing, {n_unknown} unknown)"]
    data = {"script": "neck_check.py", "result": result, "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board),
            "limits": L.to_dict(), "thickness_um": thick, "assumed": assumed, "paths": results,
            "crops": [{"name": f"neck_{i + 1}", "frame": "kicad", "x": s["layers"][0]["at"][0], "y": s["layers"][0]["at"][1], "size": 8.0,
                       "why": f"{pn} / {s['name']}: {s['result']}, narrowest {s['layers'][0]['w_min']:.2f} mm"}
                      for i, (pn, s) in enumerate(rows_all) if s["result"] not in ("PASS",) and s["layers"][0]["at"]]}
    p_md, _ = pcb_common.write_result(job.out, "current_worksheet", md, _clean(data))
    for pn, s in rows_all:
        if s["result"] != "PASS":
            print(f"{s['result']}  {pn} / {s['name']}: {s['why']}")
    print(f"{result}: {len(paths)} path(s), {len(rows_all)} section(s) -> {p_md}")
    return 0 if result == "PASS" else 1


def _clean(o):
    """JSON cannot hold infinity: write it as a string."""
    if isinstance(o, float):
        return o if math.isfinite(o) else str(o)
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
