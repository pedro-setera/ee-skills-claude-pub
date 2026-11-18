"""The independent second measure of every cable route, and the comparison that fixes the design length.

What it does
    MEASURE (default). A different method on purpose: it knows only the two end poses of each cable (or wire), a bend
    radius and optional via points, from `cables/second_measure.toml`, a file written by a second person from the
    model. It never opens routes.toml and never looks at the first measure. Between consecutive poses it solves the
    shortest admissible path: planar Dubins (arc - straight - arc, all four turn combinations) when the two poses lie
    in one plane, and a three-dimensional arc - straight - arc built from the tangent corners otherwise; the wire
    leaves each connector straight (`lead`, default 3 mm). It writes `route.measure_b_mm` (and `route.wires[key].b`),
    and `route.second` = the shortest length at the cable's MINIMUM bend radius (`reach_mm`) and, for cables whose two
    ends face each other on parallel axes, the axial distance and the sideways offset of the S.
    COMPARE (--compare). Rows per cable and wire:
      CMP      a and b and their difference: at most 2 mm, or a written cause in `route.note`
      DESIGN   design length = the LARGEST of (the LONGER of the two measures + allowance by end type: fixed at both ends +2,
               an end trimmed and soldered at assembly +10), (the LONGER of the two measures + the design tolerance D: the route
               floor) and (the shortest path at the cable's MINIMUM radius, `route.second.reach_mm`, + D: the reach floor), ONE
               length per cable = the longest wire's result, rounded UP to 1 mm. So the shortest cable the maker may deliver
               (L - D) still covers the measured route by construction (a cable shorter than its route is the one fault that
               cannot be fixed in the box); the extra length up to L + D becomes one more bend, judged by SBEND. When a floor
               wins the row says "raised from <a> to <b> so the shortest cable the maker may deliver (L - D) is still as long as
               the measured route" (or "still reaches" for the reach floor). Without second-measure data there is no reach
               floor. A `route.allowance_mm` set by hand still sets the first term; the floors apply anyway.
      LENGTH   `length_mm` in cables.json equals the design length (--apply writes it)
      TOL      the tolerance asked on the drawing (`tol_mm`) is not tighter than the supplier's standard
      REACH    at length - DESIGN tolerance the cable still reaches (not shorter than the shortest path at minimum radius);
               it fails only when `length_mm` was forced below the design length by hand
      SBEND    stiff cables (coax, network, `stiff = true`): the smallest radius of the rest shape of an S between
               parallel axes (elastica: axial distance, offset, length) at length - D, length, length + D
      The design tolerance D is `[tolerance] design_mm` of the capability sheet, else the WIDEST of its `standard_mm`: the
      supplier may draw any of its standard tolerances whatever was asked (asked tighter, drawn at +-5; +-5 is the cable
      maker's floor as read 2026-11). REACH and SBEND are judged at D; their row text also gives the result at the
      cable's own `tol_mm` (the value asked on the drawing, normally the narrowest standard). TOL and the drawing keep `tol_mm`.
      FRESH    measure a was taken from the routes file as it is now
    A cable that is too long between two fixed ends has to bow: on a short stiff cable 2 mm more can halve the radius.

Why it exists (the real failure, told without names)
    Two measures of one short coax can differ by a connector body length when each assumes a different body; only the
    comparison shows it. And on a short stiff cable each extra millimetre tightens the S between two fixed jacks, until
    it bends below its minimum radius.

Usage
    python -I cable_second_measure.py [--project <mech folder>] [--out <folder>] [--poses cables/second_measure.toml]
                                      [--cables cables.json] [--only CAB-01] [--no-write]
    python -I cable_second_measure.py --compare [--apply] [--project ...] [--cables ...] [--sheet <capability.toml>]
    second_measure.toml:
        [[cable]]
        id = "CAB-01"
        radius = 6.0                                       # bend radius of this measure
        start = {p = [20, 30, 12], d = [0, 0, 1]}          # wire exit and the direction the wire LEAVES the connector
        end   = {p = [80, 50, 12], d = [0, 0, 1]}          # the same for the other connector
        via   = [ {p = [50, 40, 30], d = [1, 0, 0]} ]      # optional; d = direction of travel there (default: the chord)
        lead  = [3.0, 3.0]                                 # optional straight exits
        stiff = true                                       # optional: force (or with false, skip) the S-bend data
        [[cable.wire]]                                     # optional, one per wire that differs
        key = "P1.3"
        start = ...   end = ...
    Needs numpy; the S-bend rows need scipy.

Config keys (mech.toml)
    [cables] second, file, supplier, sheet, min_straight_mm = 3.0, compare_max_diff_mm = 2.0, allowance_crimped_mm = 2.0,
             allowance_trimmed_mm = 10.0, tol_mm = 3.0 (used when the capability sheet has no [tolerance] values)
    [cables.types.<name>] min_bend_r, min_bend_x_od, od_mm, stiff

Exit codes
    0 all rows pass   1 a row failed   2 could not run (no poses file, no numpy) or a row could not run (no scipy)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import math
import os
from concurrent.futures import ProcessPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import cable_common as cc  # noqa: E402

try:
    import numpy as np
except ImportError:
    np = None

TIGHT_TEXT = "the supplier draws its standard tolerance silently; design for it"
STIFF_KINDS = ("rf", "ethernet")


class NoPath(Exception):
    pass


def _u(v):
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise NoPath("a direction of zero length")
    return v / n


def _ang(a, b) -> float:
    return math.acos(max(-1.0, min(1.0, float(np.dot(a, b)))))


# ---------------------------------------------------------------- path between two poses -----------------------------
def dubins_plane(q1, t0, t1, R):
    """Shortest planar arc - straight - arc from the origin (heading angle t0) to q1 (heading angle t1), radius R.
    Returns (length, [arc angles and straight]) or None."""
    def left(t):
        return np.array([-math.sin(t), math.cos(t)])

    best = None
    for s1 in (1, -1):
        for s2 in (1, -1):
            c1 = R * s1 * left(t0)
            c2 = q1 + R * s2 * left(t1)
            v = c2 - c1
            D = float(np.linalg.norm(v))
            base = math.atan2(v[1], v[0])
            cands = []
            if s1 == s2:
                cands.append((base, D))
            elif D >= 2 * R:
                cands.append((base + s1 * math.asin(2 * R / D), math.sqrt(max(D * D - 4 * R * R, 0.0))))
            for ts, L in cands:
                a1 = (s1 * (ts - t0)) % (2 * math.pi)
                a2 = (s2 * (t1 - ts)) % (2 * math.pi)
                if a1 > 2 * math.pi - 1e-9:
                    a1 = 0.0
                if a2 > 2 * math.pi - 1e-9:
                    a2 = 0.0
                p = R * s1 * left(t0) - R * s1 * left(t0 + s1 * a1)
                p = p + L * np.array([math.cos(ts), math.sin(ts)])
                p = p + R * s2 * left(ts) - R * s2 * left(ts + s2 * a2)
                if np.linalg.norm(p - q1) > 1e-6:
                    continue
                tot = R * (a1 + a2) + L
                if best is None or tot < best[0]:
                    best = (tot, a1, L, a2)
    return best


def corner_path(P0, h0, P1, h1, R):
    """Three-dimensional arc - straight - arc by tangent corners: each arc is replaced by its corner (the meeting point
    of its two tangents, R tan(angle / 2) from each end); the straight runs corner to corner. Fixed-point iteration on
    the straight's direction. Returns (length, angle1, straight, angle2) or None."""
    u = P1 - P0
    if np.linalg.norm(u) < 1e-9:
        return None
    u = _u(u)
    for _ in range(600):
        a1, a2 = _ang(h0, u), _ang(u, h1)
        if a1 > math.pi - 1e-3 or a2 > math.pi - 1e-3:
            return None
        c = P1 - R * math.tan(a2 / 2) * h1 - (P0 + R * math.tan(a1 / 2) * h0)
        if np.linalg.norm(c) < 1e-9:
            return None
        un = _u(c)
        if np.linalg.norm(un - u) < 1e-13:
            u = un
            break
        u = _u(0.5 * u + 0.5 * un)
    a1, a2 = _ang(h0, u), _ang(u, h1)
    t1, t2 = R * math.tan(a1 / 2), R * math.tan(a2 / 2)
    c = P1 - t2 * h1 - (P0 + t1 * h0)
    if float(np.dot(c, u)) < 0 or abs(np.linalg.norm(c) - float(np.dot(c, u))) > 1e-6:
        return None
    s = float(np.linalg.norm(c)) - t1 - t2
    if s < -1e-7:
        return None
    return R * (a1 + a2) + max(s, 0.0), a1, max(s, 0.0), a2


def leg(P0, h0, P1, h1, R) -> tuple[float, str]:
    """Shortest admissible length from pose (P0, heading h0) to pose (P1, heading h1) at radius R, and the method."""
    P0, P1, h0, h1 = np.asarray(P0, float), np.asarray(P1, float), _u(h0), _u(h1)
    d = P1 - P0
    dist = float(np.linalg.norm(d))
    if dist < 1e-9:
        if _ang(h0, h1) < 1e-6:
            return 0.0, "same pose"
        raise NoPath("two poses at the same point with different directions")
    n = np.cross(h0, h1)
    if np.linalg.norm(n) < 1e-7:
        n = np.cross(h0, d)
        if np.linalg.norm(n) < 1e-7:                       # everything on one line
            if float(np.dot(h0, d)) > 0 and float(np.dot(h0, h1)) > 0:
                return dist, "straight"
            n = np.cross(h0, [1.0, 0, 0] if abs(h0[0]) < 0.9 else [0, 1.0, 0])
    n = _u(n)
    if abs(float(np.dot(d, n))) < 1e-6 * max(1.0, dist) and abs(float(np.dot(h1, n))) < 1e-7:
        e1 = h0
        e2 = np.cross(n, e1)
        q1 = np.array([float(np.dot(d, e1)), float(np.dot(d, e2))])
        t1 = math.atan2(float(np.dot(h1, e2)), float(np.dot(h1, e1)))
        best = dubins_plane(q1, 0.0, t1, R)
        if best is None:
            raise NoPath(f"no planar arc-straight-arc path at radius {R:g}")
        return best[0], "planar Dubins"
    sol = corner_path(P0, h0, P1, h1, R)
    if sol is None:
        raise NoPath(f"no arc-straight-arc path at radius {R:g} (the poses are too close for this radius)")
    return sol[0], "3D arc-straight-arc"


def solve(start, end, via, R, lead) -> tuple[float, list[str]]:
    """Length from the start wire exit to the end wire exit through the via poses."""
    p0, d0 = np.asarray(start["p"], float), _u(start["d"])
    p1, d1 = np.asarray(end["p"], float), _u(end["d"])
    poses = [(p0 + d0 * lead[0], d0)]
    pts = [p0 + d0 * lead[0]] + [np.asarray(v["p"], float) for v in via] + [p1 + d1 * lead[1]]
    for i, v in enumerate(via):
        h = _u(v["d"]) if "d" in v else _u(pts[i + 2] - pts[i])
        poses.append((pts[i + 1], h))
    poses.append((p1 + d1 * lead[1], -d1))
    total, how = lead[0] + lead[1], []
    for (a, ha), (b, hb) in zip(poses, poses[1:]):
        L, m = leg(a, ha, b, hb, R)
        total += L
        how.append(m)
    return total, how


# ---------------------------------------------------------------- S-bend rest shape ---------------------------------
def s_rest_radius(job_):
    """(axial, offset, length) -> smallest bend radius of the rest shape of a cable clamped on two parallel axes
    `axial` apart along them and `offset` apart sideways (the elastica, discretised: minimum of the bending energy).
    None when the cable is shorter than the straight distance; raises ImportError without scipy."""
    axial, offset, length = job_
    from scipy.optimize import minimize
    if length <= math.hypot(axial, offset) + 1e-6:
        return None
    n = 64
    h = length / n

    def full(x):
        return np.concatenate([[0.0], x, [0.0]])           # the angle at the nodes; clamped along the axis at both ends

    def mid(x):
        f = full(x)
        return 0.5 * (f[1:] + f[:-1])

    def energy(x):
        return float(np.sum(np.diff(full(x)) ** 2))

    cons = [{"type": "eq", "fun": lambda x: h * float(np.sum(np.sin(mid(x)))) - offset},
            {"type": "eq", "fun": lambda x: h * float(np.sum(np.cos(mid(x)))) - axial}]
    s = np.linspace(0, 1, n + 1)[1:-1]
    best = None
    for amp in (1.0, 1.6, 0.6):
        x0 = 2 * math.atan2(offset, axial) * amp * np.sin(math.pi * s) + (0.3 * amp * np.sin(2 * math.pi * s) if offset < 1e-9 else 0)
        r = minimize(energy, x0, constraints=cons, method="SLSQP", options={"maxiter": 1000, "ftol": 1e-13})
        if abs(cons[0]["fun"](r.x)) < 1e-5 and abs(cons[1]["fun"](r.x)) < 1e-5 and (best is None or r.fun < best.fun):
            best = r
    if best is None:
        return float("nan")
    k = float(np.max(np.abs(np.diff(full(best.x)))))
    return math.inf if k < 1e-12 else h / k


# ---------------------------------------------------------------- measure -------------------------------------------
def load_poses(path: str) -> list[dict]:
    doc = mc.load_toml(path)
    out = []
    for c in doc.get("cable", []):
        cid = c.get("id")
        if not cid:
            raise mc.MechError(f"{path}: a [[cable]] without id")
        com = {"cable": cid, "radius": c.get("radius"), "lead": c.get("lead"), "stiff": c.get("stiff")}
        if not c.get("wire"):
            out.append({**com, "key": "", "start": c.get("start"), "end": c.get("end"), "via": c.get("via", [])})
        for w in c.get("wire", []):
            out.append({**com, "key": str(w.get("key", "")), "start": w.get("start", c.get("start")), "end": w.get("end", c.get("end")),
                        "via": w.get("via", c.get("via", [])), "radius": w.get("radius", c.get("radius"))})
    return out


def measure(job, a) -> tuple[mc.Rows, list]:
    cfg = cc.cable_cfg(job)
    ppath = mc.rel_to_project(job.cfg, a.poses or cfg["second"])
    if not os.path.isfile(ppath):
        raise mc.MechError(f"no poses file at {ppath}")
    data, cpath = cc.load_cables(job, a.cables)
    types = cc.cable_types(data, cfg)
    by_id = {c.get("id"): c for c in data["cables"]}
    rows = mc.Rows()
    res: dict = {}
    for pd in load_poses(ppath):
        if a.only and pd["cable"] != a.only:
            continue
        rn = pd["cable"] + ("/" + pd["key"] if pd["key"] else "")
        sec = f"cable {pd['cable']}"
        cable = by_id.get(pd["cable"])
        if cable is None:
            rows.add(f"{rn}-B", sec, "second measure", "no such cable id in cables.json", "the id of a cable", "fail")
            continue
        rmin, why = cc.min_bend(cable, types)
        R = pd["radius"] if isinstance(pd["radius"], (int, float)) else rmin
        lead = pd["lead"] if pd["lead"] is not None else [float(cfg["min_straight_mm"])] * 2
        lead = [float(lead)] * 2 if isinstance(lead, (int, float)) else [float(lead[0]), float(lead[1])]
        ok_pose = all(isinstance(p, dict) and "p" in p and "d" in p for p in (pd["start"], pd["end"]))
        if R is None or not ok_pose:
            rows.add(f"{rn}-B", sec, "second measure", "no bend radius" if R is None else "start or end pose missing (p and d)",
                     "two end poses and a bend radius", "fail")
            continue
        if rmin is not None and R < rmin - 1e-9:
            rows.add(f"{rn}-RADIUS", sec, "bend radius of the second measure", f"R {R:g}", f">= R {rmin:g} ({why})", "fail")
        try:
            L, how = solve(pd["start"], pd["end"], pd["via"], float(R), lead)
        except NoPath as e:
            rows.add(f"{rn}-B", sec, "second measure", f"no admissible path: {e}", "a path of straights and arcs at the given radius", "fail")
            continue
        rows.add(f"{rn}-B", sec, "second measure: shortest admissible path", f"{L:.2f} mm at R {R:g} ({', '.join(how)}; straight exits {lead[0]:g} / {lead[1]:g})",
                 "arc-straight-arc between the poses", "pass")
        reach = L
        if rmin is not None and rmin < R - 1e-9:
            try:
                reach = solve(pd["start"], pd["end"], pd["via"], float(rmin), lead)[0]
            except NoPath:
                reach = L
        d0, d1 = _u(pd["start"]["d"]), _u(pd["end"]["d"])
        s_geo = None
        stiff = pd["stiff"] if pd["stiff"] is not None else (cable.get("type") in STIFF_KINDS or bool(types.get(cc.cable_type(cable), {}).get("stiff")))
        if stiff and not pd["via"]:
            if _ang(d0, -d1) < math.radians(5.0):
                v = np.asarray(pd["end"]["p"], float) - np.asarray(pd["start"]["p"], float)
                ax = float(np.dot(v, d0))
                s_geo = {"axial": round(ax, 3), "offset": round(float(np.linalg.norm(v - d0 * ax)), 3)}
            else:
                s_geo = {"not_parallel": True}
        res.setdefault(pd["cable"], []).append({"key": pd["key"], "b": L, "reach": reach, "R": float(R), "s": s_geo, "stiff": bool(stiff)})
    changed = False
    for cid, lst in res.items():
        r = by_id[cid].setdefault("route", {})
        wires = r.setdefault("wires", {})
        for it in lst:
            if it["key"]:
                wires.setdefault(it["key"], {})["b"] = round(it["b"], 2)
        if not wires:
            r.pop("wires", None)
        longest = max(lst, key=lambda it: it["b"])
        r["measure_b_mm"] = round(longest["b"], 2)
        r["second"] = {"radius": longest["R"], "reach_mm": round(max(it["reach"] for it in lst), 2), "stiff": longest["stiff"]}
        if longest["s"]:
            r["second"]["s"] = longest["s"]
        changed = True
    if changed and not a.no_write:
        if cc.save_cables(cpath, data):
            print(f"  wrote route.measure_b_mm into {cpath}")
        else:
            print(f"  {cpath} unchanged: not rewritten")
    return rows, [ppath]


# ---------------------------------------------------------------- compare -------------------------------------------
CHANGE_DESIGN = ("no whole-mm length may work at this tolerance: change the design (more offset, a longer run, an end trimmed at "
                 "assembly, a more flexible cable), do not tighten the tolerance (CB-14)")


def reach_floor(cable: dict, d_tol: float):
    """Smallest whole-mm length whose shortest deliverable cable (L - d_tol) still reaches: ceil(reach_mm + d_tol), where
    `route.second.reach_mm` is the shortest path at the cable's minimum radius. None when there is no second-measure data."""
    reach = ((cable.get("route") or {}).get("second") or {}).get("reach_mm")
    if not isinstance(reach, (int, float)) or isinstance(reach, bool):
        return None
    return int(math.ceil(float(reach) + d_tol - 1e-9))


def design_length(cable: dict, cfg: dict):
    """(design mm or None, longer measure or None, allowance, allowance reason, list of (key, a, b))."""
    r = cable.get("route") or {}
    pairs = []
    for k, w in sorted((r.get("wires") or {}).items()):
        pairs.append((k, w.get("a"), w.get("b")))
    if not pairs:
        pairs.append(("", r.get("measure_a_mm"), r.get("measure_b_mm")))
    alw, awhy = cc.allowance(cable, cfg)
    vals = [v for _k, x, y in pairs for v in (x, y)]
    if any(not isinstance(v, (int, float)) for v in vals):
        return None, None, alw, awhy, pairs
    longer = max(vals)
    return int(math.ceil(longer + alw - 1e-9)), longer, alw, awhy, pairs


def compare(job, a) -> tuple[mc.Rows, list]:
    cfg = cc.cable_cfg(job)
    data, cpath = cc.load_cables(job, a.cables)
    cap, cap_path = cc.capability(job, a.sheet)
    std = cc.standard_tolerance(cap, cfg)
    dtol = cc.design_tolerance(cap, cfg)          # REACH and SBEND are judged at this tolerance, not at the one asked
    types = cc.cable_types(data, cfg)
    rows = mc.Rows()
    maxd = float(cfg["compare_max_diff_mm"])
    rpath = mc.rel_to_project(job.cfg, cfg["routes"])
    rsha = mc.sha256(rpath) if os.path.isfile(rpath) else None
    s_jobs, s_keys, changed = [], [], False
    for c in data["cables"]:
        cid = c.get("id")
        if a.only and cid != a.only:
            continue
        sec = f"cable {cid}"
        r = c.get("route") or {}
        note = str(r.get("note", "")).strip()
        design, longer, alw, awhy, pairs = design_length(c, cfg)
        first = design                                    # the allowance term; the two floors may raise it
        rfloor = None if longer is None else int(math.ceil(longer + dtol[0] - 1e-9))   # route floor: L - D >= the measured route
        floor = reach_floor(c, dtol[0])
        raised = None
        if design is not None and rfloor > design:
            design, raised = rfloor, "route"
        if design is not None and floor is not None and floor > design:
            design, raised = floor, "reach"
        for k, x, y in pairs:
            rn = cid + ("/" + k if k else "")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                rows.add(f"{rn}-CMP", sec, "first and second measure", f"a = {x}, b = {y}", "both measures present", "fail")
                continue
            d = abs(x - y)
            ok = d <= maxd + 1e-9 or len(note) >= 10
            rows.add(f"{rn}-CMP", sec, "first and second measure", f"a {x:.2f}, b {y:.2f}, difference {d:.2f} mm"
                     + (f"; cause: {note}" if d > maxd and note else ""), f"difference <= {maxd:g} mm, or a written cause in route.note",
                     "pass" if ok else "fail")
        if design is None:
            rows.add(f"{cid}-DESIGN", sec, "design length", "not computed: a measure is missing", "longer of the two + allowance", "fail")
            continue
        if raised == "route":
            dtext = (f"{design} mm: raised from {first} to {design} so the shortest cable the maker may deliver (L - D) is still as long "
                     f"as the measured route (longer measure {longer:.2f} + design tolerance {dtol[0]:g}, rounded up; + {alw:g} ({awhy}) "
                     f"gave {first})")
        elif raised == "reach":
            dtext = (f"{design} mm: raised from {first} to {design} so the shortest cable the maker may deliver (L - D) still reaches "
                     f"(shortest path at the minimum radius {r['second']['reach_mm']:.2f} + design tolerance {dtol[0]:g}, rounded up; longer measure "
                     f"{longer:.2f} + {alw:g} ({awhy}) gave {first})")
        else:
            dtext = f"{design} mm = longer measure {longer:.2f} + {alw:g} ({awhy}), rounded up to 1 mm"
            dtext += f"; the route floor {rfloor} mm (longer measure + design tolerance {dtol[0]:g}) is not higher"
            if floor is not None:
                dtext += f"; the reach floor {floor} mm (shortest path + design tolerance {dtol[0]:g}) is not higher"
        rows.add(f"{cid}-DESIGN", sec, "design length", dtext,
                 "the largest of (the longer of the two + allowance by end type), (the longer of the two + design tolerance: the shortest "
                 "cable the maker may deliver still covers the route) and (shortest path at the minimum radius + design tolerance); "
                 "ONE length per cable = the longest wire's", "pass")
        if a.apply and c.get("length_mm") != design:
            c["length_mm"] = design
            changed = True
        if r.get("design_length_mm") != design:
            c.setdefault("route", {})["design_length_mm"] = design
            changed = True
        L = c.get("length_mm")
        rows.add(f"{cid}-LENGTH", sec, "length_mm equals the design length", f"length_mm {L}, design {design}",
                 "equal (run --compare --apply to write it)", "pass" if L == design else "fail")
        tol = c.get("tol_mm")
        if not isinstance(tol, (int, float)) or tol <= 0:
            rows.add(f"{cid}-TOL", sec, "length tolerance", "no tol_mm", f"+-{std[0]:g} mm or wider", "fail")
            continue
        tight = tol < std[0] - 1e-9
        rows.add(f"{cid}-TOL", sec, "length tolerance", f"+-{tol:g} mm" + (f" is tighter than the standard: {TIGHT_TEXT}" if tight else ""),
                 f"not tighter than +-{std[0]:g} mm ({std[1]})", "fail" if tight else "pass")
        if not isinstance(L, (int, float)):
            continue
        sec2 = r.get("second") or {}
        reach = sec2.get("reach_mm")
        D = dtol[0]
        same = abs(D - tol) < 1e-9
        if isinstance(reach, (int, float)):
            ok = L - D >= reach - 1e-6
            own = f"; at the +-{tol:g} mm asked on the drawing: shortest cable {L - tol:g} mm, " +                   ("reaches" if L - tol >= reach - 1e-6 else f"too short by {reach - (L - tol):.2f} mm")
            rows.add(f"{cid}-REACH", sec, "the cable still reaches at length - design tolerance",
                     f"at the design tolerance +-{D:g} mm ({dtol[1]}): shortest cable {L - D:g} mm, shortest path {reach:.2f} mm"
                     + ("" if ok else f": too short by {reach - (L - D):.2f} mm; length_mm {int(math.ceil(reach + D - 1e-9))} or more reaches "
                                      "(the DESIGN row; run --compare --apply)")
                     + (" (the same as the tolerance asked)" if same else own),
                     f"length - design tolerance (+-{D:g}) >= the shortest admissible path (second measure at the minimum bend radius)",
                     "pass" if ok else "fail")
        else:
            rows.add(f"{cid}-REACH", sec, "the cable still reaches at length - design tolerance", "no second measure",
                     "length - design tolerance >= shortest path", "fail")
        s = sec2.get("s")
        if sec2.get("stiff") and s and not s.get("not_parallel"):
            rmin, why = cc.min_bend(c, types)
            # verdicts at length -+ the design tolerance; the same lengths at the asked tolerance are only shown in the text
            lens = [("minus", L - D), ("nominal", L), ("plus", L + D)]
            if not same:
                lens += [("asked_minus", L - tol), ("asked_plus", L + tol)]
            for name, LL in lens:
                s_jobs.append((s["axial"], s["offset"], float(LL)))
                s_keys.append((cid, sec, name, LL, rmin, why, D, tol))
        elif sec2.get("stiff"):
            rows.add(f"{cid}-SBEND", sec, "S-bend of a stiff cable", "the two ends are not on parallel axes (or the route has via points): judge the bends on the route",
                     "rest shape radius >= minimum", "na")
        src = r.get("a_source") or {}
        if src.get("routes_sha256") and rsha:
            rows.add(f"{cid}-FRESH", sec, "measure a belongs to the present routes file", "same file" if src["routes_sha256"] == rsha else
                     "routes.toml changed after the measure: run cable_route.py again", "checksum of routes.toml at the measure = now",
                     "pass" if src["routes_sha256"] == rsha else "fail")
    if s_jobs:
        try:
            import scipy  # noqa: F401
            n = min(mc.workers(), len(s_jobs))
            if n > 1:
                print(f"  S-bend rest shapes: {len(s_jobs)} on {n} worker(s)", flush=True)
                with ProcessPoolExecutor(n) as ex:
                    radii = list(ex.map(s_rest_radius, s_jobs))
            else:
                radii = [s_rest_radius(j) for j in s_jobs]
        except ImportError:
            radii = None
        solved = {(k[0], k[2]): (k[3], radii[i] if radii is not None else None) for i, k in enumerate(s_keys)}

        def rtxt(rr):
            return "cannot reach" if rr is None else ("did not solve" if rr != rr else f"smallest radius R {rr:.1f} mm")

        for i, (cid, sec, name, LL, rmin, why, D, tol) in enumerate(s_keys):
            if name.startswith("asked_"):
                continue                                     # shown in the text of the minus / plus row, never judged
            rid = f"{cid}-SBEND-{name}"
            at = {"minus": " (length - design tolerance)", "plus": " (length + design tolerance)"}.get(name, "")
            if radii is None:
                rows.add(rid, sec, f"S-bend at {LL:g} mm{at}", "scipy is missing", "rest shape radius >= minimum", "could_not_run")
                continue
            rr = radii[i]
            ax, off = s_jobs[i][0], s_jobs[i][1]
            geo = f"axial {ax:g}, offset {off:g}"
            extra = ""
            if name in ("minus", "plus") and (cid, "asked_" + name) in solved:
                l2, r2 = solved[(cid, "asked_" + name)]
                extra = f"; at the +-{tol:g} mm asked on the drawing (length {l2:g} mm): {rtxt(r2)}"
            elif name in ("minus", "plus"):
                extra = " (the same as the tolerance asked)"
            if rr is None:
                rows.add(rid, sec, f"S-bend at {LL:g} mm{at}", f"shorter than the straight distance {math.hypot(ax, off):.2f} mm ({geo}): it cannot reach{extra}; {CHANGE_DESIGN}",
                         "the cable reaches", "fail")
            elif rr != rr:
                rows.add(rid, sec, f"S-bend at {LL:g} mm{at}", f"the rest shape did not solve ({geo}){extra}", "rest shape radius >= minimum", "could_not_run")
            elif rmin is None:
                rows.add(rid, sec, f"S-bend at {LL:g} mm{at}", f"R {rr:.1f} ({geo}); no minimum known: {why}{extra}", "rest shape radius >= minimum", "could_not_run")
            else:
                good = rr >= rmin - 1e-6
                rows.add(rid, sec, f"S-bend at {LL:g} mm{at}",
                         f"smallest radius R {rr:.1f} mm ({geo}){extra}" + ("" if good else f"; {CHANGE_DESIGN}"), f">= R {rmin:g} ({why})",
                         "pass" if good else "fail")
    if changed and not a.no_write:
        if cc.save_cables(cpath, data):
            print(f"  wrote the design length into {cpath}")
        else:
            print(f"  {cpath} unchanged: not rewritten")
    return rows, ([cap_path] if cap else [])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Independent second measure of the cable routes, and the comparison.",
                                 epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--poses", help="poses file (default [cables] second = cables/second_measure.toml)")
    ap.add_argument("--cables", help="the cable data file")
    ap.add_argument("--sheet", help="capability sheet of the cable supplier (for the standard tolerance)")
    ap.add_argument("--only", help="one cable id")
    ap.add_argument("--compare", action="store_true", help="compare a and b and fix the design length")
    ap.add_argument("--apply", action="store_true", help="with --compare: write the design length into length_mm")
    ap.add_argument("--no-write", action="store_true", help="do not write into cables.json")
    a = ap.parse_args(argv)
    if np is None:
        print("could not run: the Python library 'numpy' is missing")
        return 2
    try:
        job = mc.resolve(a)
        rows, inputs = (compare if a.compare else measure)(job, a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(job.out, "cable_compare.py" if a.compare else "cable_second_measure.py", inputs)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
