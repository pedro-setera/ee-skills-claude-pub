"""Sheet-metal rule measure: the supplier's design rules measured ON THE EXPORTED STEP (and the silkscreen DXF).

What it does
    Opens the STEP that will be uploaded (not the model that made it) and measures, with code of its own:
      - one valid solid per file; the longest side against the supplier's limit; the thickness on its list;
      - no face under 0.01 mm2 and no edge under 0.1 mm (leftovers of boolean cuts stop an automatic quote);
      - every bend is a true cylindrical face pair with the table's outer radius (inner = outer - t) and an allowed
        angle (90 degrees unless more are allowed); sharp bends and faces that are neither flat nor cylindrical fail;
      - every leg next to a bend: its length from the other leg's outer face against the smallest flange. The length
        is the LOWEST reach of the leg along the bend's whole axial span (a tab narrower than the bend does not count).
        Two readings: a leg with ONE bend takes the single-bend value (whatever its other leg carries: a closure flange
        on each of two opposite edges of a wide floor is accepted at the single value); a leg BETWEEN
        two or more bends (a U's floor, a Z's middle leg, a wall between a floor bend and a lip bend; the bends may be on
        either face of the leg) takes the "second bend" value. Every row says which reading it used;
      - the inside width of every U (two legs bent the same way, facing each other);
      - every hole, slot and cut-out edge to the nearest bend (round and other shapes have their own value),
        measured by default to the bend's tangent line on its own leg (strict); the other leg's outer face (tangent
        line + outer radius, lenient) is an explicit option. Every row prints BOTH numbers and names the reading;
      - the smallest round hole (>= max(t x factor, absolute)); the web between two cut-outs;
      - hardware (clinch nuts and the like, from the table in mech.toml): centre to the nearest free edge and to
        the nearest bend (the same reading switch as for the holes);
      - bend ends where the sheet continues past the bend without a relief cut.
    With --silk-dxf it also measures the print file: every ink shape inside its face, off the cut-outs, at the
    distance from edges, cut-outs and bend lines, no stroke or gap under the minimum, and the text height (from
    the element list silk_dxf.py writes beside the DXF).
    Rule VALUES come from the capability sheet ([sheet_rules."<t>"], [limits], [silk_rules]); extra margins of
    your own from mech.toml ([sheet.margins]). A rule with no value on the sheet (a [silk_rules] key, [limits]
    max_length, the [materials] thickness list, the chart inks, a hardware table without edge_min / bend_min) is
    reported "could not run", never "not applicable" and never a pass: the exit code is then 2 when nothing failed.
    (Limits with a built-in default say so in the rule text and still run. "Not applicable" is kept for things the
    part simply does not have: no U, no round hole, no cut-out near a bend.)

Why it exists (the real failure, told without names)
    The builder's own checks all passed on the model. An independent measure of the exported files then found several
    failures: bends that were not cylinders, a U channel 1 mm too narrow, nuts too close to an edge, faces
    smaller than 0.1 mm, print running into a cut-out. Every one would have been a question or a rejection from
    the supplier. Measured on the files, with the rule table as data, the order then passed without one
    geometry question.

Usage
    python -I sheet_dfm.py --step <part.step> [--name NAME] [--silk-dxf <file.dxf>] [--silk-json <file.json>]
                           [--capability <sheet.capability.toml>] [--thickness T] [--project <mech>] [--out <dir>]
    python -I sheet_dfm.py --all [--project <mech folder>] [--out <folder>]
        --step        the STEP of one part          --all   every part of [sheet] parts, on all cores
        --silk-dxf    the print file of that part (or silk_dxf in [sheet] parts)
        --silk-json   the element list (default: the DXF's name with .json)
        --capability  the capability sheet (default <project>/suppliers/<[sheet] supplier>.capability.toml)
    Needs CadQuery, numpy, shapely; ezdxf for the print file.

Config keys
    mech.toml
      [sheet] thickness, supplier, parts = [ {name, step, silk_dxf?} ]
              allowed_bend_angles = [90]
              hole_to_bend_from = "tangent"         # default, strict: hole edge (and hardware centre) to the bend's
                                                    # tangent line; "outer_face": to the other leg's outer face
                                                    # (tangent line + outer radius: lenient)
      [sheet.margins] flange = 0, flange_second = 0, hole_to_bend = 0, hardware_edge = 0, hardware_bend = 0,
                      u_inside = 0, hole_to_hole = 0, silk = 0          # added to the supplier's value
      [[sheet.hardware]] code, hole_d, body_d, edge_min, bend_min
      [silk] outline_layer = "OUTLINE_NOT_PRINTED", bend_layer = "BEND_LINE_NOT_PRINTED", allow_ink_overlap = false
    capability sheet
      [materials] thickness = [...]          [limits] max_length, hole_d_min = 1.0, hole_d_min_t_factor = 0.5,
      hole_to_hole = 1.0, u_inside_min = 12.0, tiny_face = 0.01, tiny_edge = 0.1
      [sheet_rules."1.5"] outer_bend_r, min_flange, min_flange_second, hole_to_bend_round, hole_to_bend_square
      [finishes] inks = [...]                [silk_rules] min_text_height, min_line, min_gap, edge_clearance

Exit codes
    0 every rule row passes     1 at least one rule is broken     2 could not run (no STEP, no capability sheet,
    no rule row for this thickness, CadQuery missing, a bad hole_to_bend_from; or a row could not run (a rule value
    missing from the capability sheet, no element list for the text height) while nothing failed)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import math
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

DEFAULT_LIMITS = {"hole_d_min": 1.0, "hole_d_min_t_factor": 0.5, "hole_to_hole": 1.0, "u_inside_min": 12.0,
                  "tiny_face": 0.01, "tiny_edge": 0.1}


def _v(p):
    import numpy as np
    return np.array([p.X(), p.Y(), p.Z()])


def fmt(p):
    return "(" + ", ".join(f"{float(x):.1f}" for x in p) + ")"


READINGS = ("tangent", "outer_face")


def reading_text(cfg_sheet):
    """How a distance to a bend is measured, for the rule text of every hole-to-bend and hardware-to-bend row."""
    r = cfg_sheet.get("hole_to_bend_from")
    if r == "outer_face":
        return "other leg's outer face (set in mech.toml)"
    return "tangent line (set in mech.toml, strict)" if r == "tangent" else "tangent line (default, strict)"


def both_text(h, o):
    """The two numbers of a distance to a bend: to the tangent line on its own leg, to the other leg's outer face."""
    return f"{h:.2f} to the tangent line, {o:.2f} to the other leg's outer face"


def flange_reach(outer, b, d):
    """(lowest, tallest) reach of a leg's outline from the bend's tangent line, along d, over the bend's WHOLE axial
    span [s0, s1]. The lowest one is the flange: a tab narrower than the bend does not count. Stations: both ends of
    the span, every 0.5 mm, and either side of every corner of the outline. Stations where the leg does not touch the
    bend line (the bend is cut there) are skipped. None when the leg never touches the bend line."""
    import numpy as np
    from shapely.geometry import LineString, Polygon

    s, h = (outer - b["o"]) @ b["a"], (outer - b["o"]) @ d
    pg = Polygon(np.c_[s, h]).buffer(0)
    if pg.is_empty:
        return None
    pg = pg.simplify(1e-5, preserve_topology=True)
    lo, hi = b["s0"] + 1e-3, b["s1"] - 1e-3
    if hi <= lo:
        lo = hi = (b["s0"] + b["s1"]) / 2
    from shapely import get_coordinates
    vx = get_coordinates(pg)[:, 0]
    xs = np.unique(np.round(np.clip(np.concatenate([[lo, hi], np.arange(lo, hi, 0.5), vx - 1e-3, vx + 1e-3]), lo, hi), 4))
    top = float(h.max()) + 1.0
    tops = []
    for x in xs:
        cut = pg.intersection(LineString([(float(x), 0.005), (float(x), top)]))
        pieces = list(cut.geoms) if hasattr(cut, "geoms") else [cut]
        reach = [g.bounds[3] for g in pieces if g.geom_type == "LineString" and not g.is_empty and g.bounds[1] <= 0.006]
        if reach:
            tops.append(max(reach))
    return (min(tops), max(tops)) if tops else None


# ---------------------------------------------------------------- the STEP -------------------------------------------
class Part:
    """The solid's faces with what the measures need (own reader: nothing shared with the drawing scripts)."""

    def __init__(self, path):
        import cadquery as cq
        import numpy as np
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
        from OCP.TopExp import TopExp
        from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_IndexedMapOfShape

        self.shape = cq.importers.importStep(str(path)).val()
        self.faces = self.shape.Faces()
        self.info = []
        for f in self.faces:
            s = BRepAdaptor_Surface(f.wrapped)
            rev = f.wrapped.Orientation() == TopAbs_REVERSED
            if s.GetType() == GeomAbs_Plane:
                n = _v(s.Plane().Axis().Direction())
                n = -n if rev else n
                self.info.append({"k": "plane", "n": n / np.linalg.norm(n), "o": _v(s.Plane().Location())})
            elif s.GetType() == GeomAbs_Cylinder:
                a = _v(s.Cylinder().Axis().Direction())
                self.info.append({"k": "cyl", "r": s.Cylinder().Radius(), "a": a / np.linalg.norm(a),
                                  "o": _v(s.Cylinder().Axis().Location()),
                                  "span": math.degrees(s.LastUParameter() - s.FirstUParameter()), "convex": not rev})
            else:
                self.info.append({"k": "other", "type": str(s.GetType()).split(".")[-1]})
        fmap = TopTools_IndexedMapOfShape()
        for f in self.faces:
            fmap.Add(f.wrapped)
        emap = TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.MapShapesAndAncestors_s(self.shape.wrapped, TopAbs_EDGE, TopAbs_FACE, emap)
        self.adj = {i: set() for i in range(len(self.faces))}
        for k in range(1, emap.Extent() + 1):
            ids = {fmap.FindIndex(x) - 1 for x in emap.FindFromIndex(k)}
            for i in ids:
                self.adj[i] |= ids - {i}
        self._wires = {}

    def wires(self, i):
        """(outer points, [inner points], [inner is-round (centre, r) or None]) of face i, sampled every 0.1."""
        if i not in self._wires:
            f = self.faces[i]
            self._wires[i] = (self._sample(f.outerWire()), [self._sample(w) for w in f.innerWires()],
                              [self._round(w) for w in f.innerWires()])
        return self._wires[i]

    @staticmethod
    def _sample(w, step=0.1):
        import numpy as np
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.BRepTools import BRepTools_WireExplorer
        from OCP.GCPnts import GCPnts_AbscissaPoint
        from OCP.TopAbs import TopAbs_REVERSED

        pts = []
        ex = BRepTools_WireExplorer(w.wrapped)
        while ex.More():
            c = BRepAdaptor_Curve(ex.Current())
            a, b = c.FirstParameter(), c.LastParameter()
            n = max(2, int(GCPnts_AbscissaPoint.Length_s(c) / step) + 1)
            ps = [_v(c.Value(a + (b - a) * k / n)) for k in range(n + 1)]
            pts += (ps[::-1] if ex.Orientation() == TopAbs_REVERSED else ps)[:-1]
            ex.Next()
        return np.array(pts)

    @staticmethod
    def _round(w):
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.GeomAbs import GeomAbs_Circle

        cs = [BRepAdaptor_Curve(e.wrapped) for e in w.Edges()]
        if cs and all(c.GetType() == GeomAbs_Circle for c in cs):
            r = {round(c.Circle().Radius(), 4) for c in cs}
            ctr = {tuple(round(x, 3) for x in _v(c.Circle().Location())) for c in cs}
            if len(r) == 1 and len(ctr) == 1:
                return _v(cs[0].Circle().Location()), cs[0].Circle().Radius()
        return None

    def frame2(self, i):
        import numpy as np
        n = self.info[i]["n"]
        h = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        e1 = np.cross(n, h)
        e1 /= np.linalg.norm(e1)
        return e1, np.cross(n, e1)

    def poly(self, i, holes=False):
        import numpy as np
        from shapely.geometry import Polygon

        e1, e2 = self.frame2(i)
        outer, inner, _r = self.wires(i)
        p = Polygon(np.c_[outer @ e1, outer @ e2]).buffer(0)
        if holes:
            for w in inner:
                p = p.difference(Polygon(np.c_[w @ e1, w @ e2]).buffer(0))
        return p


def thickness_of(part):
    import numpy as np

    pl = [(i, f) for i, f in enumerate(part.info) if f["k"] == "plane"]
    seps, wts = [], []
    for i, fi in pl:
        di = float(fi["n"] @ fi["o"])
        cand = [di + float(fj["n"] @ fj["o"]) for j, fj in pl if j != i and fi["n"] @ fj["n"] < -0.9999]
        cand = [c for c in cand if c > 0.05]
        if cand:
            seps.append(min(cand))
            wts.append(part.faces[i].Area())
    if not seps:
        return None
    o = np.argsort(seps)
    cum = np.cumsum(np.array(wts)[o])
    return round(float(np.array(seps)[o][np.searchsorted(cum, cum[-1] / 2)]), 3)


def measure_step(path, name, t_nom, rules, limits, cfg_sheet, allowed_t):
    """The rule rows of one STEP: [(id, check, value, rule, verdict)]."""
    import numpy as np
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    rows = []

    def add(rid, check, value, rule, ok):
        verdict = ok if isinstance(ok, str) else ("pass" if ok else "fail")
        rows.append((f"DFM-{name}-{rid}", check, value, rule, verdict))

    mg = {k: float(v) for k, v in (cfg_sheet.get("margins") or {}).items()}

    def lim(key, margin=None):
        """(value, text) of a limit; the text says where the number came from."""
        m = mg.get(margin, 0.0) if margin else 0.0
        if key in limits:
            v, src = float(limits[key]), ""
        else:
            v, src = DEFAULT_LIMITS[key], " (default: not on the capability sheet)"
        return v + m, f">= {v:g}" + (f" + {m:g} margin" if m else "") + src

    part = Part(path)
    P, info, faces = part, part.info, part.faces
    sols = part.shape.Solids()
    add("01", "one valid solid in the file", f"{len(sols)} solid(s), valid {bool(part.shape.isValid())}", "1, valid",
        len(sols) == 1 and part.shape.isValid())
    bb = part.shape.BoundingBox()
    size = sorted([bb.xlen, bb.ylen, bb.zlen])
    if "max_length" in limits:
        add("02", "longest side", f"{size[2]:.2f}", f"<= {float(limits['max_length']):g}",
            size[2] <= float(limits["max_length"]))
    else:
        add("02", "longest side", f"{size[2]:.2f}", "no [limits] max_length on the capability sheet", "could_not_run")
    t_meas = thickness_of(part)
    t = t_nom if t_nom is not None else t_meas
    t_ok = t_meas is not None and abs(t_meas - t) <= 0.01
    if not t_ok:
        t_verdict = "fail"
    elif not allowed_t:
        t_verdict = "could_not_run"          # the supplier's list is not on the capability sheet: not a pass
    else:
        t_verdict = "pass" if any(abs(t - float(x)) < 1e-6 for x in allowed_t) else "fail"
    add("03", "sheet thickness", f"measured {t_meas:g}" + (f", configured {t_nom:g}" if t_nom is not None else ""),
        "as configured (+-0.01) and on the supplier's list "
        + (str(allowed_t) if allowed_t else "(no [materials] thickness list on the capability sheet)"), t_verdict)
    areas = [f.Area() for f in faces]
    tf, te = lim("tiny_face")[0], lim("tiny_edge")[0]
    tiny = [a for a in areas if a < tf]
    add("04", "no tiny face", f"{len(tiny)} under {tf:g} mm2 (smallest face {min(areas):.4f})", "0", not tiny)
    el = [e.Length() for e in part.shape.Edges()]
    short = [x for x in el if x < te]
    add("05", "no tiny edge", f"{len(short)} under {te:g} mm (shortest edge {min(el):.4f})", "0", not short)

    # ---- walls (wide flat faces), bends ----------------------------------------------------------------------------
    wide = {i for i, f in enumerate(info) if f["k"] == "plane" and areas[i] > 0.3
            and not P.poly(i).buffer(-0.6 * t).is_empty}
    other = [i for i, f in enumerate(info) if f["k"] == "other"]
    # a bend: a part cylinder next to a wall face, or one of a coaxial pair whose radii differ by t (so that a
    # flange too short to count as a wall is still measured); its legs: the flat faces along its straight edges
    part_cyl = [i for i, f in enumerate(info) if f["k"] == "cyl" and f["span"] < 359]
    bend_cyl = {}
    for i in part_cyl:
        f = info[i]
        legs = [j for j in P.adj[i] if info[j]["k"] == "plane" and abs(float(info[j]["n"] @ f["a"])) < 0.1]
        paired = False
        for j in part_cyl:
            g = info[j]
            dv = g["o"] - f["o"]
            if j != i and g["convex"] != f["convex"] and abs(abs(float(g["a"] @ f["a"])) - 1) < 1e-4                     and np.linalg.norm(dv - (dv @ f["a"]) * f["a"]) < 0.02 and abs(abs(g["r"] - f["r"]) - t) < 0.02:
                paired = True
        if legs and (paired or any(j in wide for j in legs)):
            bend_cyl[i] = legs
    sharp = []
    for i in sorted(wide):
        for j in P.adj[i]:
            if j in wide and j > i and abs(float(info[i]["n"] @ info[j]["n"])) < 0.9999:
                sharp.append((i, j))
    # a sharp bend shows as two wide faces meeting in an edge, on the outside and on the inside: count the corners
    add("06", "every bend is a true cylindrical face",
        f"{len([i for i in bend_cyl if info[i]['convex']])} cylindrical bends, {len(sharp)} sharp wall-to-wall edges, "
        f"{len(other)} faces neither flat nor cylindrical"
        + (" (" + ", ".join(sorted({info[i]['type'] for i in other})) + ")" if other else ""),
        "0 sharp, 0 other", not sharp and not other)
    ro_rule = float(rules["outer_bend_r"])
    angles = [float(a) for a in cfg_sheet.get("allowed_bend_angles", [90])]
    bends = []           # {"i", "o", "a", "s0", "s1", "ro", "legs"}
    for i, legs in sorted(bend_cyl.items()):
        f = info[i]
        if not f["convex"]:
            continue
        pts = P.wires(i)[0]
        s = (pts - f["o"]) @ f["a"]
        inner, inner_i = None, None
        for j in bend_cyl:
            g = info[j]
            dv = g["o"] - f["o"]
            if not g["convex"] and abs(abs(float(g["a"] @ f["a"])) - 1) < 1e-4 \
                    and np.linalg.norm(dv - (dv @ f["a"]) * f["a"]) < 0.02:
                sj = (P.wires(j)[0] - f["o"]) @ f["a"]
                if sj.min() < s.max() - 0.01 and sj.max() > s.min() + 0.01:
                    inner, inner_i = g, j
        bends.append({"i": i, "o": f["o"], "a": f["a"], "s0": float(s.min()), "s1": float(s.max()), "ro": f["r"],
                      "legs": legs, "span": f["span"], "ri": inner["r"] if inner else None,
                      "inner_legs": bend_cyl[inner_i] if inner is not None else []})
    for i, legs in sorted(bend_cyl.items()):          # inside radius without an outside one
        f = info[i]
        if f["convex"] or any(abs(abs(float(b["a"] @ f["a"])) - 1) < 1e-4 and
                              np.linalg.norm((f["o"] - b["o"]) - ((f["o"] - b["o"]) @ b["a"]) * b["a"]) < 0.02
                              for b in bends):
            continue
        s = (P.wires(i)[0] - f["o"]) @ f["a"]
        bends.append({"i": i, "o": f["o"], "a": f["a"], "s0": float(s.min()), "s1": float(s.max()), "ro": None,
                      "legs": legs, "span": f["span"], "ri": f["r"], "inner_legs": []})
    for k, b in enumerate(bends):
        mid = b["o"] + b["a"] * (b["s0"] + b["s1"]) / 2
        ok = (b["ro"] is not None and abs(b["ro"] - ro_rule) <= 0.02 and b["ri"] is not None
              and abs(b["ri"] - (ro_rule - t)) <= 0.02 and any(abs(b["span"] - a) <= 0.5 for a in angles))
        add(f"07.{k + 1}", f"bend at {fmt(mid)}: outer radius / inner radius / angle",
            f"{'none' if b['ro'] is None else format(b['ro'], '.3f')} / "
            f"{'none' if b['ri'] is None else format(b['ri'], '.3f')} / {b['span']:.2f}",
            f"{ro_rule:g} / {ro_rule - t:g} / one of {angles}", ok)
    if not bends:
        add("07", "bend radii and angles", "no cylindrical bend in the part", "-", "fail" if sharp else "na")

    # ---- legs: flange lengths, cut-outs to the bend, reliefs -------------------------------------------------------
    from_outer = cfg_sheet.get("hole_to_bend_from", "tangent") == "outer_face"
    rd_txt = reading_text(cfg_sheet)
    def leg_dir(g, b):
        """Direction along the leg's face, away from the bend's axis."""
        d = np.cross(info[g]["n"], b["a"])
        return -d if float(((P.wires(g)[0] - b["o"]) @ d).mean()) < 0 else d

    leg_bends = {}             # face -> [(bend, direction)] for the faces on a bend's OUTER cylinder: the rows' legs
    inner_leg = {}             # face -> [(bend, direction)] for the faces on a bend's inner cylinder
    for b in bends:
        b["ro_eff"] = b["ro"] if b["ro"] is not None else b["ri"] + t
        for g in b["legs"]:
            leg_bends.setdefault(g, []).append((b, leg_dir(g, b)))
        for g in b["inner_legs"]:
            if g not in b["legs"]:
                inner_leg.setdefault(g, []).append((b, leg_dir(g, b)))

    def twins(g, h):
        """The two faces of one wall: opposite normals, a sheet thickness apart, outlines on top of each other."""
        from shapely.geometry import Polygon
        if float(info[g]["n"] @ info[h]["n"]) > -0.9999:
            return False
        if abs(abs(float((info[h]["o"] - info[g]["o"]) @ info[g]["n"])) - t) > 0.02:
            return False
        e1, e2 = P.frame2(g)
        pa, pb = P.wires(g)[0], P.wires(h)[0]
        a = Polygon(np.c_[pa @ e1, pa @ e2]).buffer(0)
        b = Polygon(np.c_[pb @ e1, pb @ e2]).buffer(0)
        return a.intersection(b).area > 0.5 * min(a.area, b.area)

    # one entry per leg (a wall): the bends it touches on its outer face OR on its inner face; a leg between two or
    # more bends takes the second-bend value, a leg with one bend the single-bend value
    ents = []        # (face, lowest, tallest, centre, bends touched)
    for g, lst in leg_bends.items():
        outer = P.wires(g)[0]
        allb = lst + [x for x in inner_leg.get(g, []) if all(x[0] is not y[0] for y in lst)]
        reach = []
        for b, d in allb:
            r = flange_reach(outer, b, d)
            if r is None:                    # the leg never touches this bend line: fall back to the plain extent
                r = (float(((outer - b["o"]) @ d).max()),) * 2
            reach.append((r[0] + b["ro_eff"], r[1] + b["ro_eff"]))
        lo_v, hi_v = min(reach, key=lambda x: x[0])
        ents.append((g, lo_v, hi_v, outer.mean(0), len(allb)))
    kept = []        # the two faces of one wall give one row (the lower value)
    for e in sorted(ents, key=lambda x: x[1]):
        if not any(twins(e[0], k[0]) for k in kept):
            kept.append(e)
    one = [e for e in kept if e[4] == 1]
    two = [e for e in kept if e[4] > 1]
    need1, need2 = float(rules["min_flange"]) + mg.get("flange", 0), float(rules["min_flange_second"]) + mg.get(
        "flange_second", 0)
    txt1 = f"{float(rules['min_flange']):g}" + (f" + {mg['flange']:g} margin" if mg.get("flange") else "")
    txt2 = f"{float(rules['min_flange_second']):g}" + (f" + {mg['flange_second']:g} margin" if mg.get("flange_second") else "")

    def reach_text(lo_v, hi_v):
        return f"{lo_v:.2f}" + (f" (lowest along the bend; {hi_v:.2f} at the tallest point)" if hi_v - lo_v > 0.005 else "")

    for k, (_g, v, hi_v, c, _n) in enumerate(sorted(one, key=lambda x: x[1])):
        add(f"08.{k + 1}", f"flange (one bend), at {fmt(c)}: length from the other leg's outer face, lowest point along the bend",
            reach_text(v, hi_v), f">= {txt1} (reading: single bend)", v >= need1 - 1e-3)
    for k, (_g, v, hi_v, c, _n) in enumerate(sorted(two, key=lambda x: x[1])):
        add(f"09.{k + 1}", f"leg between bends, at {fmt(c)}: shortest length from a bend's other leg's outer face, "
            "lowest point along the bend", reach_text(v, hi_v), f">= {txt2} (reading: second bend: a leg between bends)",
            v >= need2 - 1e-3)

    # U insides: two inside faces (next to an inside bend radius), facing each other, overlapping
    inside = sorted({j for i, legs in bend_cyl.items() if not info[i]["convex"] for j in legs})
    us = []
    for x, i in enumerate(inside):
        for j in inside[x + 1:]:
            na, nb = info[i]["n"], info[j]["n"]
            if na @ nb > -0.9999:
                continue
            pa, pb = P.wires(i)[0], P.wires(j)[0]
            gap = float((pb.mean(0) - pa.mean(0)) @ na)
            if gap <= t + 0.01:
                continue
            e1, e2 = P.frame2(i)
            from shapely.geometry import MultiPoint
            ha, hb = MultiPoint(np.c_[pa @ e1, pa @ e2]).convex_hull, MultiPoint(np.c_[pb @ e1, pb @ e2]).convex_hull
            if ha.intersection(hb).area > 1.0:
                us.append((gap, (pa.mean(0) + pb.mean(0)) / 2))
    u_need, u_txt = lim("u_inside_min", "u_inside")
    if "u_inside_min" in rules:
        u_need = float(rules["u_inside_min"]) + mg.get("u_inside", 0)
        u_txt = f">= {float(rules['u_inside_min']):g}" + (f" + {mg['u_inside']:g} margin" if mg.get("u_inside") else "")
    for k, (gap, c) in enumerate(sorted(us, key=lambda x: x[0])):
        add(f"10.{k + 1}", f"U channel at {fmt(c)}: inside width", f"{gap:.2f}", u_txt, gap >= u_need - 1e-3)
    if not us:
        add("10", "U channels: inside width", "no U in the part", u_txt, "na")

    # cut-outs to the bends: the edge to the tangent line (h) and to the other leg's outer face (h + outer radius);
    # the default reading is the strict one, the tangent line
    near = {"round": [], "other": []}
    for g, lst in leg_bends.items():
        _o, inner, rnd = P.wires(g)
        for w, r in zip(inner, rnd):
            best = None
            for b, d in lst:
                s_ = (w - b["o"]) @ b["a"]
                ok = (s_ >= b["s0"] - 1.0) & (s_ <= b["s1"] + 1.0)
                if ok.any():
                    h = float(((w[ok] - b["o"]) @ d).min())
                    cand = (h + (b["ro_eff"] if from_outer else 0.0), h, h + b["ro_eff"])
                    best = cand if best is None or cand[0] < best[0] else best
            if best is not None:
                near["round" if r is not None else "other"].append(best + (w.mean(0), None if r is None else 2 * r[1]))
    ref = "the other leg's outer face" if from_outer else "the bend's tangent line"
    for kind, key, rid in (("round", "hole_to_bend_round", "11"), ("other", "hole_to_bend_square", "12")):
        need = float(rules[key]) + mg.get("hole_to_bend", 0)
        txt = (f">= {float(rules[key]):g}" + (f" + {mg['hole_to_bend']:g} margin" if mg.get("hole_to_bend") else "")
               + f" (reading: {rd_txt})")
        lst = sorted(near[kind], key=lambda x: x[0])
        label = "round holes" if kind == "round" else "slots, windows, other cut-outs"
        if not lst:
            add(rid, f"{label}: edge to {ref}", "none next to a bend", txt, "na")
            continue
        v, h, o, c, d = lst[0]
        add(rid, f"{label} ({len(lst)} on bent legs): the closest edge to {ref}",
            f"{both_text(h, o)}; at {fmt(c)}" + (f", d {d:.2f}" if d else ""), txt, v >= need - 1e-3)
        for k, (v, h, o, c, d) in enumerate([x for x in lst[1:] if x[0] < need - 1e-3][:20]):
            add(f"{rid}.{k + 2}", f"{label}: edge to {ref}", f"{both_text(h, o)}; at {fmt(c)}", txt, False)

    # holes: smallest diameter, webs
    seen, holes_d, webs = set(), [], []
    for i in sorted(wide):
        _o, inner, rnd = P.wires(i)
        if not inner:
            continue
        n = info[i]["n"]
        e1, e2 = P.frame2(i)
        from shapely.geometry import Polygon
        polys, keep = [], []
        for w, r in zip(inner, rnd):
            c = w.mean(0)
            key = (tuple(np.round(c - (c @ n) * n, 1)), tuple(np.round(np.abs(n), 3)))
            if key in seen:
                continue
            seen.add(key)
            if r is not None:
                holes_d.append((2 * r[1], c))
            polys.append(Polygon(np.c_[w @ e1, w @ e2]).buffer(0))
            keep.append(c)
        if len(polys) > 1:
            tree = STRtree(polys)
            for a, pa in enumerate(polys):
                for b in tree.query(pa.buffer(3.0)):
                    if b > a:
                        webs.append((pa.distance(polys[b]), keep[a]))
    dmin = max(t * lim("hole_d_min_t_factor")[0], lim("hole_d_min")[0])
    if holes_d:
        d, c = min(holes_d, key=lambda x: x[0])
        add("13", f"smallest round hole ({len(holes_d)} holes)", f"d {d:.2f} at {fmt(c)}",
            f">= {dmin:g} (the larger of t x {lim('hole_d_min_t_factor')[0]:g} and {lim('hole_d_min')[0]:g})"
            + ("" if "hole_d_min" in limits else " (default)"), d >= dmin - 1e-3)
    else:
        add("13", "smallest round hole", "no round hole", f">= {dmin:g}", "na")
    wneed, wtxt = lim("hole_to_hole", "hole_to_hole")
    if webs:
        w, c = min(webs, key=lambda x: x[0])
        bad = sum(1 for x in webs if x[0] < wneed - 1e-3)
        add("14", "web between two cut-outs: the thinnest", f"{w:.2f} at {fmt(c)}; {bad} pair(s) under the rule", wtxt,
            bad == 0)
    else:
        add("14", "web between two cut-outs", "no neighbouring cut-outs", wtxt, "na")

    # hardware
    hw_tab = cfg_sheet.get("hardware") or []
    places = []       # (hw, centre, face index)
    seen = set()
    for i in sorted(wide):
        _o, inner, rnd = P.wires(i)
        n = info[i]["n"]
        for w, r in zip(inner, rnd):
            if r is None:
                continue
            for hw in hw_tab:
                if hw.get("hole_d") and abs(2 * r[1] - float(hw["hole_d"])) < 0.03:
                    key = tuple(np.round(r[0] - (r[0] @ n) * n, 1)) + tuple(np.round(np.abs(n), 3))
                    if key not in seen:
                        seen.add(key)
                        places.append((hw, r[0], i))
    for i, f in enumerate(info):
        if f["k"] == "cyl" and f["convex"] and f["span"] > 359:
            for hw in hw_tab:
                if hw.get("body_d") and abs(f["r"] - float(hw["body_d"]) / 2) < 0.01:
                    c = np.array(faces[i].Center().toTuple())
                    best = None
                    for j in sorted(wide):
                        n = info[j]["n"]
                        if abs(abs(float(n @ f["a"])) - 1) > 1e-4:
                            continue
                        if P.poly(j).area < 1.5 * math.pi * f["r"] ** 2:
                            continue        # the hardware's own end face, not the sheet
                        dist = abs(float((c - info[j]["o"]) @ n))
                        e1, e2 = P.frame2(j)
                        if dist < 3 * t + 6 and P.poly(j).buffer(0.01).contains(Point(float(c @ e1), float(c @ e2))):
                            if best is None or dist < best[0]:
                                best = (dist, j)
                    if best:
                        places.append((hw, c, best[1]))
    for k, (hw, c, i) in enumerate(places):
        n = info[i]["n"]
        outer, inner, rnd = P.wires(i)
        # free edges: the outer wire away from bends, and the other cut-outs
        bend_pts = []
        for b in bends:
            if i in b["legs"] or any(abs(float(info[i]["n"] @ info[g]["n"])) > 0.9999 for g in b["legs"]):
                d = np.cross(n, b["a"])
                h = np.abs((outer - b["o"]) @ d)
                s = (outer - b["o"]) @ b["a"]
                bend_pts.append((h < 0.02) & (s >= b["s0"] - 0.02) & (s <= b["s1"] + 0.02))
        free = outer[~np.any(bend_pts, axis=0)] if bend_pts else outer
        cp = c - ((c - info[i]["o"]) @ n) * n
        dists = [float(np.linalg.norm(free - cp, axis=1).min())] if len(free) else []
        for w, r in zip(inner, rnd):
            dd = np.linalg.norm(w - cp, axis=1)
            if r is not None and np.linalg.norm(r[0] - (r[0] - cp) @ n * n - cp) < 0.05:
                continue            # its own hole
            dists.append(float(dd.min()))
        to_bend = []
        for b in bends:
            if abs(float(b["a"] @ n)) > 1e-4:
                continue
            wv = cp - b["o"]
            if b["s0"] - 3 <= float(wv @ b["a"]) <= b["s1"] + 3 and abs(float(wv @ n)) < b["ro_eff"] + 0.1:
                h = abs(float(wv @ np.cross(b["a"], n)))
                to_bend.append((h + (b["ro_eff"] if from_outer else 0.0), h, h + b["ro_eff"]))
        e_min, b_min = hw.get("edge_min"), hw.get("bend_min")
        e_need = None if e_min is None else float(e_min) + mg.get("hardware_edge", 0)
        b_need = None if b_min is None else float(b_min) + mg.get("hardware_bend", 0)
        ok = True
        if dists and e_need is not None:
            ok &= min(dists) >= e_need - 1e-3
        if to_bend and b_need is not None:
            ok &= min(to_bend)[0] >= b_need - 1e-3
        add(f"15.{k + 1}", f"{hw.get('code', 'hardware')} at {fmt(c)}: centre to a free edge / to a bend",
            (f"{min(dists):.2f} to a free edge" if dists else "no free edge") + " / "
            + (both_text(*min(to_bend)[1:]) if to_bend else "no bend near"),
            f">= {e_need if e_need is not None else 'not given'} / >= {b_need if b_need is not None else 'not given'}"
            f" (bend reading: {rd_txt})",
            ok if (e_need is not None or b_need is not None) else "could_not_run")
    if hw_tab and not places:
        add("15", "hardware places", "none found in the STEP for the [[sheet.hardware]] table", "-", "na")

    # reliefs: where a leg continues past a bend's end, a relief cut must free the bend
    n_cont, where = 0, []
    for g, lst in leg_bends.items():
        outer = P.wires(g)[0]
        from shapely.geometry import Polygon
        for b, d in lst:
            pg = Polygon(np.c_[(outer - b["o"]) @ b["a"], (outer - b["o"]) @ d]).buffer(0)
            for s_end, sg in ((b["s0"], -1), (b["s1"], 1)):
                if pg.contains(Point(s_end + sg * 0.3, 0.1)):
                    n_cont += 1
                    where.append(fmt(b["o"] + b["a"] * s_end))
    add("16", "bend ends where the sheet continues past the bend without a relief cut",
        f"{n_cont}" + (": at " + ", ".join(where[:6]) if where else ""), "0 (a relief wherever a bend meets un-bent sheet)",
        n_cont == 0)
    return rows


# ---------------------------------------------------------------- the print file -------------------------------------
def read_print(path, ink_layers, outline_layer, bend_layer):
    """{"faces": [polygon], "cutouts": [polygon], "bends": [LineString], "inks": {layer: geometry}} of a print DXF."""
    import ezdxf
    import numpy as np
    from ezdxf import path as zpath
    from scipy.spatial import cKDTree
    from shapely.geometry import LineString, Polygon
    from shapely.ops import polygonize, unary_union

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    def flat(e):
        try:
            return [(v.x, v.y) for v in zpath.make_path(e).flattening(0.005)]
        except Exception:
            return []

    segs = [flat(e) for e in msp if e.dxf.layer == outline_layer]
    segs = [s for s in segs if len(s) >= 2]
    faces, cuts = [], []
    if segs:
        ends = np.array([p for s in segs for p in (s[0], s[-1])])
        tree = cKDTree(ends)
        rep = {}
        for a, b in tree.query_pairs(0.01):
            rep[b] = rep.get(a, a)
        fixed = []
        for k, s in enumerate(segs):
            s = list(s)
            for pos, idx in ((0, 2 * k), (-1, 2 * k + 1)):
                r = idx
                while r in rep:
                    r = rep[r]
                s[pos] = tuple(ends[r])
            fixed.append(LineString(s))
        polys = sorted(polygonize(unary_union(fixed)), key=lambda p: -Polygon(p.exterior).area)
        for p in polys:
            host = next((f for f in faces if Polygon(f.exterior).contains(p.representative_point())), None)
            if host is None:
                faces.append(p)
            else:
                cuts.append(Polygon(p.exterior))
    bends = [LineString(flat(e)) for e in msp if e.dxf.layer == bend_layer and len(flat(e)) >= 2]
    inks = {}
    for lay in ink_layers:
        loops = []
        hatches = [e for e in msp if e.dxf.layer == lay and e.dxftype() == "HATCH"]
        if hatches:
            parts = []
            for h in hatches:
                g = Polygon()
                for bp in h.paths:
                    pts = [(v.x, v.y) for v in zpath.from_hatch_boundary_path(bp).flattening(0.005)]
                    if len(pts) >= 3:
                        g = g.symmetric_difference(Polygon(pts).buffer(0))
                parts.append(g)
            inks[lay] = unary_union(parts)
        else:
            for e in msp:
                if e.dxf.layer == lay and e.dxftype() in ("LWPOLYLINE", "POLYLINE", "CIRCLE"):
                    pts = flat(e)
                    if len(pts) >= 3:
                        loops.append(Polygon(pts).buffer(0))
            g = Polygon()
            for p in sorted(loops, key=lambda q: -q.area):
                g = g.symmetric_difference(p)
            if not g.is_empty:
                inks[lay] = g
    return {"faces": faces, "cutouts": cuts, "bends": bends, "inks": inks}


def _islands(g):
    return [q for q in (list(g.geoms) if hasattr(g, "geoms") else [g]) if q.geom_type == "Polygon" and not q.is_empty]


def measure_silk(path, json_path, name, cap, cfg_silk, margin):
    """The print-file rows of one DXF."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    rows = []

    def add(rid, check, value, rule, ok):
        rows.append((f"DFM-{name}-S{rid}", check, value, rule, ok if isinstance(ok, str) else ("pass" if ok else "fail")))

    rules = cap.get("silk_rules") or {}
    chart = list((cap.get("finishes") or {}).get("inks") or [])
    lay_of = {i.upper().replace(" ", "_"): i for i in chart}
    if not chart:
        add("01", "the print file has its face outline and at least one ink layer", "not measured",
            "no [finishes] inks (the chart inks) on the capability sheet", "could_not_run")
        return rows
    data = read_print(path, list(lay_of), cfg_silk.get("outline_layer", "OUTLINE_NOT_PRINTED"),
                      cfg_silk.get("bend_layer", "BEND_LINE_NOT_PRINTED"))
    faces, cuts, bends, inks = data["faces"], data["cutouts"], data["bends"], data["inks"]
    add("01", "the print file has its face outline and at least one ink layer",
        f"{len(faces)} face(s), {len(cuts)} cut-out(s), {len(bends)} bend line(s), inks: "
        + (", ".join(lay_of[k] for k in inks) or "none"), ">= 1 face, >= 1 chart ink", bool(faces) and bool(inks))
    if not faces or not inks:
        return rows
    from shapely.geometry import Polygon
    solid = unary_union([Polygon(f.exterior) for f in faces])
    cutu = unary_union(cuts) if cuts else None
    allink = unary_union(list(inks.values()))
    out_a = allink.difference(solid).area
    add("02", "every printed shape lies on a face", f"{out_a:.3f} mm2 outside", "0", out_a < 1e-4)
    over = allink.intersection(cutu).area if cutu is not None else 0.0
    add("03", "no print over a cut-out", f"{over:.3f} mm2 over cut-outs", "0", over < 1e-4)

    def rule(key, rid, label, fn):
        if key not in rules:
            add(rid, label, "not measured", f"no [silk_rules] {key} on the capability sheet", "could_not_run")
            return
        v = float(rules[key]) + margin
        txt = f">= {float(rules[key]):g}" + (f" + {margin:g} margin" if margin else "")
        fn(v, txt)

    def edges(v, txt):
        d_e = min(allink.distance(f.exterior) for f in faces)
        add("04", "print to the face's outer edge: the closest", f"{d_e:.2f}", txt, d_e >= v - 1e-3)
        if cutu is not None:
            d_c = allink.distance(cutu)
            add("05", "print to a cut-out: the closest", f"{d_c:.2f}", txt, d_c >= v - 1e-3)
        else:
            add("05", "print to a cut-out", "no cut-out in the faces", txt, "na")
        if bends:
            d_b = min(allink.distance(b) for b in bends)
            add("06", "print to a bend line: the closest", f"{d_b:.2f}", txt, d_b >= v - 1e-3)
        else:
            add("06", "print to a bend line", "no bend line in the file", txt, "na")

    rule("edge_clearance", "04", "print to edges, cut-outs and bend lines", edges)

    def strokes(v, txt):
        bad, n = [], 0
        for lay, g in inks.items():
            for q in _islands(g):
                n += 1
                e = q.buffer(-v / 2 + 1e-4, 16)
                if e.is_empty or len(_islands(e)) > 1:
                    bad.append((lay_of[lay], q.centroid.coords[0]))
        add("07", f"no stroke or neck thinner than the smallest line ({n} printed islands)",
            f"{len(bad)} too thin" + (": " + "; ".join(f"{i} at ({c[0]:.1f}, {c[1]:.1f})" for i, c in bad[:6]) if bad else ""),
            txt, not bad)

    rule("min_line", "07", "smallest line width", strokes)

    def gaps(v, txt):
        isl = [(lay, q) for lay, g in inks.items() for q in _islands(g)]
        geoms = [q for _l, q in isl]
        tree = STRtree(geoms)
        best, where, n = None, None, 0
        for a, q in enumerate(geoms):
            for b in tree.query(q.buffer(v + 0.5)):
                if b <= a:
                    continue
                d = q.distance(geoms[b])
                if isl[a][0] != isl[b][0] and d == 0.0:
                    continue          # two inks touching or overlapping: its own row
                if best is None or d < best:
                    best, where = d, q.centroid.coords[0]
                n += d < v - 1e-3
        closed = 0
        for q in geoms:
            for r in q.interiors:
                closed += Polygon(r).buffer(-v / 2 + 1e-4, 16).is_empty
        add("08", f"gap between two printed islands: the smallest ({len(geoms)} islands)",
            (f"{best:.2f} at ({where[0]:.1f}, {where[1]:.1f}); {n} pair(s) under the rule" if best is not None
             else "one island only"), txt, n == 0)
        add("09", "open areas inside a printed shape (letter counters) narrower than the smallest gap",
            f"{closed}", "0 (" + txt + ")", closed == 0)

    rule("min_gap", "08", "smallest gap", gaps)
    ks = list(inks)
    ov = sum(inks[a].intersection(inks[b]).area for i, a in enumerate(ks) for b in ks[i + 1:])
    add("10", "two inks never on the same place", f"{ov:.3f} mm2 printed twice",
        "0" if not cfg_silk.get("allow_ink_overlap") else "allowed by [silk] allow_ink_overlap",
        ov < 1e-4 or bool(cfg_silk.get("allow_ink_overlap")))

    def heights(v, txt):
        if not json_path or not os.path.isfile(json_path):
            add("11", "text height", "no element list beside the DXF (silk_dxf.py writes <name>.json)", txt,
                "could_not_run")
            return
        man = mc.load_json(json_path)
        low, n = [], 0
        for fc in man.get("faces", []):
            for el in fc.get("elements", []):
                if el.get("kind") != "text":
                    continue
                n += 1
                bx = el["bbox_file"]
                zone = box(bx[0] - 0.05, bx[1] - 0.05, bx[2] + 0.05, bx[3] + 0.05)
                hs = [q.bounds[3] - q.bounds[1] for q in _islands(allink.intersection(zone))]
                h = max(hs) if hs else 0.0
                if h < v - 1e-3:
                    low.append(f"{el['id']} '{str(el.get('text', ''))[:16]}' {h:.2f}")
        add("11", f"text height: the tallest letter of each text ({n} texts)",
            f"{len(low)} too small" + (": " + "; ".join(low[:6]) if low else ""), txt, not low)

    rule("min_text_height", "11", "smallest text height", heights)
    return rows


# ---------------------------------------------------------------- command line ---------------------------------------
def find_capability(job, arg):
    if arg:
        return os.path.abspath(arg)
    sup = job.cfg.get("sheet", {}).get("supplier", "")
    return os.path.join(job.project, "suppliers", f"{sup}.capability.toml") if sup else None


def rule_row(cap, t):
    for k, v in (cap.get("sheet_rules") or {}).items():
        try:
            if abs(float(k) - t) < 1e-6:
                return v
        except ValueError:
            continue
    return None


def run_part(job_args):
    step, name, t_nom, cap, cfg_sheet, cfg_silk, dxf, sjson = job_args
    t = t_nom
    if t is None:
        t = thickness_of(Part(step))
    rules = rule_row(cap, t) if t is not None else None
    if rules is None:
        return name, None, f"no [sheet_rules.\"{t:g}\"] row on the capability sheet for thickness {t}"
    need = [k for k in ("outer_bend_r", "min_flange", "min_flange_second", "hole_to_bend_round", "hole_to_bend_square")
            if k not in rules]
    if need:
        return name, None, f"[sheet_rules.\"{t:g}\"] lacks: {', '.join(need)}"
    rows = measure_step(step, name, t_nom, rules, cap.get("limits") or {}, cfg_sheet,
                        (cap.get("materials") or {}).get("thickness"))
    if dxf:
        rows += measure_silk(dxf, sjson, name, cap, cfg_silk, float((cfg_sheet.get("margins") or {}).get("silk", 0)))
    return name, rows, None


def main(argv=None):
    ap = argparse.ArgumentParser(description="measure the supplier's sheet-metal rules on the exported STEP / DXF")
    mc.add_std_args(ap)
    ap.add_argument("--step")
    ap.add_argument("--name")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--silk-dxf")
    ap.add_argument("--silk-json")
    ap.add_argument("--capability")
    ap.add_argument("--thickness", type=float)
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    mc.reexec_with_cadquery(job.cfg)
    for lib in ("numpy", "shapely", "scipy"):
        mc.require_module(lib, "sheet_dfm.py")
    cap_path = find_capability(job, args.capability)
    if not cap_path or not os.path.isfile(cap_path):
        print(f"could not run: no capability sheet ({cap_path}); give --capability or set [sheet] supplier",
              file=sys.stderr)
        return 2
    try:
        cap = mc.load_toml(cap_path)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    sh, sk = job.cfg.get("sheet", {}), job.cfg.get("silk", {})
    if sh.get("hole_to_bend_from", "tangent") not in READINGS:
        print(f"could not run: [sheet] hole_to_bend_from = {sh['hole_to_bend_from']!r}; it must be one of {list(READINGS)}",
              file=sys.stderr)
        return 2
    t_nom = args.thickness if args.thickness is not None else sh.get("thickness")
    todo = []
    if args.all:
        for p in sh.get("parts", []):
            dxf = mc.rel_to_project(job.cfg, p["silk_dxf"]) if p.get("silk_dxf") else None
            todo.append((mc.rel_to_project(job.cfg, p["step"]), p["name"], dxf, None))
    elif args.step:
        todo.append((os.path.abspath(args.step), args.name or os.path.splitext(os.path.basename(args.step))[0],
                     os.path.abspath(args.silk_dxf) if args.silk_dxf else None,
                     os.path.abspath(args.silk_json) if args.silk_json else None))
    if not todo:
        print("could not run: give --step <file> or --all with [sheet] parts in mech.toml", file=sys.stderr)
        return 2
    jobs = []
    for step, name, dxf, sjson in todo:
        for f in (step, dxf):
            if f and not os.path.isfile(f):
                print(f"could not run: not found: {f}", file=sys.stderr)
                return 2
        if dxf:
            mc.require_module("ezdxf", "the print file")
            sjson = sjson or os.path.splitext(dxf)[0] + ".json"
        jobs.append((step, name, t_nom, cap, sh, sk, dxf, sjson))
    results = []
    if len(jobs) == 1:
        results.append(run_part(jobs[0]))
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(mc.workers(), len(jobs))) as ex:
            for k, r in enumerate(ex.map(run_part, jobs)):
                print(f"  [{k + 1}/{len(jobs)}] {r[0]}", flush=True)
                results.append(r)
    rows = mc.Rows()
    for name, prows, err in results:
        if err:
            rows.add(f"DFM-{name}-00", f"dfm:{name}", "rule table for this thickness", err, "a row per thickness",
                     "could_not_run")
            continue
        for rid, check, value, rule, verdict in prows:
            rows.add(rid, f"dfm:{name}", check, value, rule, verdict)
    inputs = [cap_path] + [j[0] for j in jobs] + [j[6] for j in jobs if j[6]]
    rows.write(job.out, "sheet_dfm.py", inputs)
    rows.print_table(only_bad=True)
    print(f"rules from {os.path.basename(cap_path)} (read {cap.get('meta', {}).get('read_date', 'date not stated')}): "
          "re-read the supplier's live page before an order")
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
