"""Sheet features: the exported STEP of ONE sheet-metal part -> a features file (panels, holes, bends, flat pattern).

What it does
    Reads the STEP exactly as the supplier will (the exported file, not the model that made it) and writes
    <out>/drawings/<part>.features.json with
      - the sheet thickness (measured; compared with [sheet] thickness and the capability sheet's list);
      - the panels: every flat wall of the part, its faces grouped, seen from outside, with a datum corner and a
        local frame (X to the right, Y up, as seen), the bend lines on it;
      - per panel every hole, slot, rectangular cut-out and free cut-out with its position from the panel datum,
        the outline as nodes (corners with their radius, arcs), regular hole patterns (pitch, rows, count), and
        hardware places (clinch nuts and the like) from the optional table in mech.toml;
      - the bends: cylindrical faces with outer and inner radius, angle, length and the two panels they join;
        sharp bends (two walls meeting in an edge) are listed apart;
      - a flat-pattern ESTIMATE (K factor from config), marked "reference only": the supplier unfolds the STEP
        with its own bend table.
    drawing_book.py prints the drawings from this file; drawing_vs_step.py then checks the printed numbers against
    the STEP with code of its own.

Why it exists (the real failure, told without names)
    A first set of drawings was made from the model's parameters, not from the exported file. Holes that the model
    cut "somewhere else" had no dimension at all, a part with an angled outline had three sizes nobody could
    read, and the supplier would have had to ask for each. Reading the features back from the STEP that is
    uploaded makes "every feature has a number" checkable.

Usage
    python -I sheet_features.py --step <part.step> [--name NAME] [--project <mech folder>] [--out <folder>]
                                [--thickness T] [--k-factor K] [--pattern-min N]
    python -I sheet_features.py --all [--project <mech folder>] [--out <folder>]
        --step         one STEP file holding one sheet-metal solid
        --name         the part's name (default: the file name without extension)
        --all          every part of [sheet] parts in mech.toml, on all cores (MECH_WORKERS limits them)
        --thickness    the nominal thickness to compare with (default [sheet] thickness; without both: measured only)
        --k-factor     for the reference flat pattern (default [sheet] k_factor, else 0.44)
        --pattern-min  the smallest number of equal holes on one pitch that is tabled as a pattern (default 6)
    Needs CadQuery (see CADQUERY_PYTHON / [tools] cadquery_python), numpy, shapely, scipy.

Config keys (mech.toml)
    [sheet] thickness = 1.2, k_factor = 0.44, pattern_min = 6, supplier = "<capability sheet id>"
            parts = [ {name = "base", step = "out/step/base.step"} ]
            bottom_view = "above"            # the panel whose outside looks down is drawn seen from above (default)
            panel_names = { BOTTOM = "FLOOR" }   # optional names instead of TOP/BOTTOM/FRONT/REAR/LEFT/RIGHT
    [[sheet.hardware]] code = "M3 clinch nut", thread = "M3", hole_d = 4.25, body_d = 6.3
                       edge_min = 5.1, bend_min = 7.5     # used by sheet_dfm.py

Exit codes
    0 the features were read and every row passes      1 a row failed (more than one solid, an edge that is
    neither a line nor an arc, a face that is no sheet wall, thickness not as configured)
    2 could not run (no STEP, CadQuery or a library missing)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import json
import math
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

EPS_N = 1e-4          # two unit normals are parallel when 1 - |dot| is below this
EPS_D = 0.02          # two planes are the same when their offsets differ by less (mm)


# ---------------------------------------------------------------- reading the solid ---------------------------------
def _v(p):
    import numpy as np
    return np.array([p.X(), p.Y(), p.Z()])


def load_shape(path):
    import cadquery as cq
    return cq.importers.importStep(str(path)).val()


def face_info(f):
    """{"kind": "plane", n (outward), o} | {"kind": "cyl", r, a, o, span (deg), convex, vlen} | {"kind": "other"}."""
    import numpy as np
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_REVERSED

    s = BRepAdaptor_Surface(f.wrapped)
    t = s.GetType()
    rev = f.wrapped.Orientation() == TopAbs_REVERSED
    if t == GeomAbs_Plane:
        pl = s.Plane()
        n = _v(pl.Axis().Direction())
        if rev:
            n = -n
        return {"kind": "plane", "n": n / np.linalg.norm(n), "o": _v(pl.Location())}
    if t == GeomAbs_Cylinder:
        cy = s.Cylinder()
        a = _v(cy.Axis().Direction())
        a = a / np.linalg.norm(a)
        u0, u1 = s.FirstUParameter(), s.LastUParameter()
        v0, v1 = s.FirstVParameter(), s.LastVParameter()
        pm = _v(s.Value((u0 + u1) / 2, (v0 + v1) / 2))
        return {"kind": "cyl", "r": cy.Radius(), "a": a, "o": _v(cy.Axis().Location()),
                "span": math.degrees(u1 - u0), "convex": not rev, "vlen": abs(v1 - v0), "mid": pm}
    return {"kind": "other", "type": str(t)}


def adjacency(shape, faces):
    """adj[i] = {j: [edge, ...]} for faces sharing an edge."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_IndexedMapOfShape

    fmap = TopTools_IndexedMapOfShape()
    for f in faces:
        fmap.Add(f.wrapped)
    emap = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape.wrapped, TopAbs_EDGE, TopAbs_FACE, emap)
    adj = {i: {} for i in range(len(faces))}
    for k in range(1, emap.Extent() + 1):
        e = TopoDS.Edge_s(emap.FindKey(k))
        ids = sorted({fmap.FindIndex(x) - 1 for x in emap.FindFromIndex(k)})
        ids = [i for i in ids if i >= 0]
        for i in ids:
            for j in ids:
                if i != j:
                    adj[i].setdefault(j, []).append(e)
    return adj


def wire_edges(wire):
    """[(kind, p0, p1, centre, r, mid, samples)] in the wire's order; kind "L" line, "A" arc, "X" anything else."""
    import numpy as np
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.TopAbs import TopAbs_REVERSED

    out = []
    ex = BRepTools_WireExplorer(wire.wrapped)
    while ex.More():
        c = BRepAdaptor_Curve(ex.Current())
        a, b = c.FirstParameter(), c.LastParameter()
        t = c.GetType()
        length = GCPnts_AbscissaPoint.Length_s(c)
        n = 1 if t == GeomAbs_Line else max(4, int(length / 0.25) + 1)
        ps = [_v(c.Value(a + (b - a) * k / n)) for k in range(n + 1)]
        pm = _v(c.Value((a + b) / 2))
        if ex.Orientation() == TopAbs_REVERSED:
            ps = ps[::-1]
        if t == GeomAbs_Line:
            out.append(("L", ps[0], ps[-1], None, None, pm, ps))
        elif t == GeomAbs_Circle:
            out.append(("A", ps[0], ps[-1], _v(c.Circle().Location()), c.Circle().Radius(), pm, ps))
        else:
            out.append(("X", ps[0], ps[-1], None, None, pm, ps))
        ex.Next()
    return out


def wire_path(edges):
    pts = []
    for e in edges:
        pts.extend(e[6][:-1])
    return pts


# ---------------------------------------------------------------- frames --------------------------------------------
class Frame:
    """A panel's 2D frame: X = (p . u) - u0, Y = (p . v) - v0, seen along -w (w = u x v points at the viewer)."""

    def __init__(self, n, u, v, u0, v0, off):
        self.n, self.u, self.v, self.u0, self.v0, self.off = n, u, v, u0, v0, off

    def uv(self, p):
        return float(p @ self.u) - self.u0, float(p @ self.v) - self.v0

    def origin(self):
        return self.u * self.u0 + self.v * self.v0 + self.n * self.off


def _r(x, n=3):
    return round(float(x), n) + 0.0


def _line_x(p0, p1, q0, q1):
    import numpy as np
    d1, d2 = np.subtract(p1, p0), np.subtract(q1, q0)
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9 * (np.hypot(*d1) * np.hypot(*d2) + 1e-30):
        return None
    t = ((q0[0] - p0[0]) * d2[1] - (q0[1] - p0[1]) * d2[0]) / den
    return np.add(p0, t * d1)


def nodes(edges, fr):
    """A closed wire as drawing nodes, in order: {"u","v","r"} a corner (its virtual sharp; r 0 = sharp, r > 0 = a
    fillet tangent to both lines) or {"u","v","arc":[cu,cv,r,"CW"|"CCW"]} an arc from this point to the next node's
    point. None when an edge is neither a line nor an arc."""
    import numpy as np

    if any(e[0] == "X" for e in edges):
        return None
    e2 = [(k, fr.uv(p0), fr.uv(p1), None if c is None else fr.uv(c), r, fr.uv(pm)) for k, p0, p1, c, r, pm, _s in edges]
    n = len(e2)
    fil = {}
    for i, e in enumerate(e2):
        prv, nxt = e2[(i - 1) % n], e2[(i + 1) % n]
        if e[0] == "A" and prv[0] == "L" and nxt[0] == "L" and n >= 3:
            x = _line_x(prv[1], prv[2], nxt[1], nxt[2])
            if x is None:
                continue
            r = e[4]
            d1, d2 = np.subtract(prv[1], x), np.subtract(nxt[2], x)
            if np.hypot(*d1) < 1e-9 or np.hypot(*d2) < 1e-9:
                continue
            d1, d2 = d1 / np.hypot(*d1), d2 / np.hypot(*d2)
            alpha = math.acos(max(-1.0, min(1.0, float(d1 @ d2))))
            if alpha < 1e-3 or abs(alpha - math.pi) < 1e-3:
                continue
            bis = (d1 + d2) / np.hypot(*(d1 + d2))
            cf = x + bis * r / math.sin(alpha / 2)
            dev = max(abs(np.hypot(*(np.array(q) - cf)) - r) for q in (e[1], e[2], e[5]))
            if dev < 0.02:
                fil[i] = x
    out = []
    for i, (k, p0, _p1, c, r, pm) in enumerate(e2):
        j = (i - 1) % n
        if k == "L":
            if e2[j][0] == "L" or j not in fil:
                out.append({"u": _r(p0[0]), "v": _r(p0[1]), "r": 0.0})
        elif i in fil:
            out.append({"u": _r(fil[i][0]), "v": _r(fil[i][1]), "r": _r(r)})
        else:
            cr = (p0[0] - c[0]) * (pm[1] - c[1]) - (p0[1] - c[1]) * (pm[0] - c[0])
            out.append({"u": _r(p0[0]), "v": _r(p0[1]), "arc": [_r(c[0]), _r(c[1]), _r(r), "CCW" if cr > 0 else "CW"]})
    return out


def classify(edges, fr):
    """An inner wire -> a feature dict in the frame's X, Y: hole | slot | rect | cutout."""
    import numpy as np

    arcs = [e for e in edges if e[0] == "A"]
    lines = [e for e in edges if e[0] == "L"]
    odd = [e for e in edges if e[0] == "X"]
    pts = np.array([fr.uv(p) for e in edges for p in e[6]])
    u0, v0 = pts.min(0)
    u1, v1 = pts.max(0)
    box = {"u": _r((u0 + u1) / 2), "v": _r((v0 + v1) / 2), "w": _r(u1 - u0), "h": _r(v1 - v0)}
    if odd:
        return {"kind": "cutout", **box, "nodes": None, "undimensionable": True}
    if arcs and not lines:
        cs = np.array([fr.uv(e[3]) for e in arcs])
        rs = [e[4] for e in arcs]
        if np.ptp(cs, axis=0).max() < 1e-4 and max(rs) - min(rs) < 1e-4:
            return {"kind": "hole", "u": _r(cs[0][0]), "v": _r(cs[0][1]), "d": _r(2 * rs[0])}
    if len(lines) == 2 and len(arcs) == 2 and len(edges) == 4 and abs(arcs[0][4] - arcs[1][4]) < 1e-4:
        c0, c1 = (fr.uv(a[3]) for a in arcs)
        r = arcs[0][4]
        du, dv = abs(c1[0] - c0[0]), abs(c1[1] - c0[1])
        if min(du, dv) < 1e-4 and max(du, dv) > 1e-4:
            return {"kind": "slot", "u": _r((c0[0] + c1[0]) / 2), "v": _r((c0[1] + c1[1]) / 2), "w": _r(2 * r),
                    "l": _r(max(du, dv) + 2 * r), "along": "X" if du >= dv else "Y"}

    def axis_line(e):
        a, b = fr.uv(e[1]), fr.uv(e[2])
        return abs(a[0] - b[0]) < 1e-4 or abs(a[1] - b[1]) < 1e-4

    if (len(lines) == 4 and len(arcs) in (0, 4) and all(axis_line(e) for e in lines)
            and (not arcs or max(a[4] for a in arcs) - min(a[4] for a in arcs) < 1e-4)):
        return {"kind": "rect", **box, "r": _r(arcs[0][4] if arcs else 0.0)}
    return {"kind": "cutout", **box, "nodes": nodes(edges, fr)}


# ---------------------------------------------------------------- thickness, walls -----------------------------------
def measure_thickness(infos, areas):
    """The area-weighted median of each planar face's distance to the nearest face behind it."""
    import numpy as np

    pl = [(i, f) for i, f in enumerate(infos) if f["kind"] == "plane"]
    seps, wts = [], []
    for i, fi in pl:
        di = float(fi["n"] @ fi["o"])
        best = None
        for j, fj in pl:
            if j == i or fi["n"] @ fj["n"] > -1 + EPS_N:
                continue
            sep = di + float(fj["n"] @ fj["o"])
            if sep > 0.05 and (best is None or sep < best):
                best = sep
        if best is not None:
            seps.append(best)
            wts.append(areas[i])
    if not seps:
        return None
    order = np.argsort(seps)
    cum = np.cumsum(np.array(wts)[order])
    return float(np.array(seps)[order][np.searchsorted(cum, cum[-1] / 2)])


def wider_than(pts2, w):
    """True when the outline holds a place wider than w (an erosion by w / 2 leaves something): a wall face, not a
    cut edge of the sheet (which is nowhere wider than the thickness, whatever its shape)."""
    from shapely.geometry import Polygon

    if len(pts2) < 3:
        return False
    return not Polygon([tuple(p) for p in pts2]).buffer(0).buffer(-w / 2).is_empty


def basis(n):
    import numpy as np

    h = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(n, h)
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(n, e1)


NAMES = [((0, 0, 1), "TOP", "TP"), ((0, 0, -1), "BOTTOM", "BT"), ((0, -1, 0), "FRONT", "FR"), ((0, 1, 0), "REAR", "RE"),
         ((-1, 0, 0), "LEFT", "LE"), ((1, 0, 0), "RIGHT", "RI")]
SEEN = {"TOP": "from above", "BOTTOM": "from below", "FRONT": "from the front", "REAR": "from behind",
        "LEFT": "from the left", "RIGHT": "from the right"}


def view_axes(n, bottom_view):
    """(u, v, seen): the panel as seen from outside, X to the right and Y up; the downward-looking panel is drawn
    from above (through the part) unless bottom_view is "below"."""
    import numpy as np

    z, y = np.array([0.0, 0.0, 1.0]), np.array([0.0, 1.0, 0.0])
    if n[2] < -0.999 and bottom_view != "below":
        return np.array([1.0, 0.0, 0.0]), y, "inside"
    up = z if abs(n[2]) < 0.7 else y
    v = up - (up @ n) * n
    v /= np.linalg.norm(v)
    u = np.cross(v, n)
    return u, v, "outside"


# ---------------------------------------------------------------- the extraction -------------------------------------
def extract(step, name, thickness=None, k_factor=0.44, pattern_min=6, hardware=(), bottom_view="above",
            panel_names=None):
    """The features dict of one part and the list of (id, check, value, rule, verdict) rows."""
    import numpy as np

    rows = []
    shape = load_shape(step)
    solids = shape.Solids()
    rows.append(("01", "one solid in the file", f"{len(solids)} solid(s)", "exactly 1",
                 "pass" if len(solids) == 1 else "fail"))
    faces = shape.Faces()
    infos = [face_info(f) for f in faces]
    areas = [f.Area() for f in faces]
    adj = adjacency(shape, faces)
    bb = shape.BoundingBox()
    lo, hi = np.array([bb.xmin, bb.ymin, bb.zmin]), np.array([bb.xmax, bb.ymax, bb.zmax])
    t_meas = measure_thickness(infos, areas)
    if t_meas is None:
        raise mc.MechError(f"{step}: no pair of parallel flat faces: not a sheet-metal part")
    t = round(t_meas, 3)
    if thickness is not None:
        rows.append(("02", "sheet thickness as configured", f"measured {t:g}", f"{thickness:g} +-0.01",
                     "pass" if abs(t - thickness) <= 0.01 else "fail"))
    else:
        rows.append(("02", "sheet thickness as configured", f"measured {t:g}", "no [sheet] thickness given", "na"))

    # ---- skin faces (the two sides of every wall) and their twins --------------------------------------------------
    edges_of = {}

    def fedges(i):
        if i not in edges_of:
            edges_of[i] = (wire_edges(faces[i].outerWire()), [wire_edges(w) for w in faces[i].innerWires()])
        return edges_of[i]

    cand = {}
    for i, fi in enumerate(infos):
        if fi["kind"] != "plane" or areas[i] < 0.3:
            continue
        di = float(fi["n"] @ fi["o"])
        tw = [j for j, fj in enumerate(infos) if fj["kind"] == "plane" and fi["n"] @ fj["n"] < -1 + EPS_N
              and abs(di + float(fj["n"] @ fj["o"]) - t) < EPS_D]
        if not tw:
            continue
        e1, e2 = basis(fi["n"])
        pts = np.array(wire_path(fedges(i)[0]))
        if wider_than(np.c_[pts @ e1, pts @ e2], 1.2 * t):
            cand[i] = tw
    twin = {}
    for i, tw in cand.items():
        via = set()
        for k in adj[i]:
            if k not in cand:
                via.update(adj[k])
        hit = [j for j in tw if j in cand and j in via]
        if hit:
            twin[i] = max(hit, key=lambda j: areas[j])
    skin = sorted(i for i in twin if twin.get(twin[i]) == i or twin[i] in twin)
    plate_of, plates = {}, []
    for i in skin:
        if i in plate_of:
            continue
        j = twin[i]
        plate_of[i] = plate_of[j] = len(plates)
        plates.append((i, j))
    def _wide(i):
        e1, e2 = basis(infos[i]["n"])
        pts = np.array(wire_path(fedges(i)[0]))
        return wider_than(np.c_[pts @ e1, pts @ e2], 1.2 * t)

    big_other = [i for i, fi in enumerate(infos) if fi["kind"] == "plane" and i not in plate_of and areas[i] > 0.3
                 and _wide(i)]
    odd_faces = [i for i, fi in enumerate(infos) if fi["kind"] == "other"]

    # ---- walls: plates on one plane; the panel is the wall's outer side --------------------------------------------
    walls = []     # {"nc", "m", "faces": {+1: [...], -1: [...]}}
    for i in skin:
        n = infos[i]["n"]
        k = int(np.argmax(np.abs(n) > 1e-6))
        sg = 1 if n[k] > 0 else -1
        nc = n * sg
        d = float(n @ infos[i]["o"])
        m = (d - t / 2) if sg > 0 else (-d + t / 2)
        for w in walls:
            if w["nc"] @ nc > 1 - EPS_N and abs(w["m"] - m) < EPS_D:
                w["faces"][sg].append(i)
                break
        else:
            walls.append({"nc": nc, "m": m, "faces": {sg: [i], -sg: []}})
    centre = (lo + hi) / 2
    pref = np.array([0.2, -0.5, 1.0])
    for w in walls:
        s = w["m"] - float(w["nc"] @ centre)
        sg = 1 if s > 1e-3 else -1 if s < -1e-3 else (1 if w["nc"] @ pref > 0 else -1)
        if not w["faces"][sg]:
            sg = -sg
        w["side"], w["n"] = sg, w["nc"] * sg
        w["area"] = sum(areas[i] for i in w["faces"][sg])
    used, panel_names = {}, dict(panel_names or {})
    walls.sort(key=lambda w: -w["area"])
    for w in walls:
        base, code = next(((nm, cd) for d, nm, cd in NAMES if w["n"] @ np.array(d, float) > 1 - EPS_N), ("OBLIQUE", "OB"))
        k = used.get(base, 0) + 1
        used[base] = k
        w["std"] = base
        w["name"] = base if k == 1 else f"{base}-{k}"
        w["code"] = code if k == 1 else f"{code}{k}"
        w["name"] = panel_names.get(w["name"], w["name"])
    order = {nm: i for i, (_d, nm, _c) in enumerate(NAMES)}
    walls.sort(key=lambda w: (order.get(w["std"], 9), w["name"]))
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    wall_of = {}
    for wi, w in enumerate(walls):
        for sg in (1, -1):
            for i in w["faces"][sg]:
                wall_of[i] = wi
        u, v, seen = view_axes(w["n"], bottom_view)
        axis_al = np.max(np.abs(w["n"])) > 1 - EPS_N
        own = np.array([p for i in w["faces"][w["side"]] for p in wire_path(fedges(i)[0])])
        src = corners if axis_al else own
        off = float(w["n"] @ infos[w["faces"][w["side"]][0]]["o"])
        w["frame"] = Frame(w["n"], u, v, float((src @ u).min()), float((src @ v).min()), off)
        w["seen"], w["axis_aligned"] = seen, bool(axis_al)
        ext = np.array([w["frame"].uv(p) for p in own])
        w["extent"] = [_r(ext[:, 0].min()), _r(ext[:, 1].min()), _r(ext[:, 0].max()), _r(ext[:, 1].max())]

    # ---- bends ------------------------------------------------------------------------------------------------------
    bend_faces = []
    for i, fi in enumerate(infos):
        if fi["kind"] != "cyl" or fi["span"] > 359.0:
            continue
        legs = [j for j in adj[i] if j in plate_of and abs(float(infos[j]["n"] @ fi["a"])) < 0.1]
        if len(legs) >= 1:
            bend_faces.append((i, legs))
    bends, conns = [], []
    for i, legs in bend_faces:
        fi = infos[i]
        if not fi["convex"]:
            continue
        pts = np.array(wire_path(fedges(i)[0]))
        s = (pts - fi["o"]) @ fi["a"]
        inner = None
        for j, _l in bend_faces:
            fj = infos[j]
            if fj["convex"] or abs(abs(fj["a"] @ fi["a"]) - 1) > EPS_N:
                continue
            dv = fj["o"] - fi["o"]
            if np.linalg.norm(dv - (dv @ fi["a"]) * fi["a"]) < EPS_D:
                sj = (np.array(wire_path(fedges(j)[0])) - fi["o"]) @ fi["a"]
                if sj.min() < s.max() - 0.01 and sj.max() > s.min() + 0.01:
                    inner = j
        bends.append({"face": i, "inner": inner, "r_outer": _r(fi["r"]),
                      "r_inner": _r(infos[inner]["r"]) if inner is not None else None,
                      "angle": _r(fi["span"], 2), "length": _r(s.max() - s.min()), "legs": legs,
                      "axis_point": fi["o"] + fi["a"] * float(s.min()), "axis_dir": fi["a"]})
    for i, legs in bend_faces:      # an inner cylinder without an outer one (outer corner sharp)
        if infos[i]["convex"] or any(b["inner"] == i for b in bends):
            continue
        fi = infos[i]
        s = (np.array(wire_path(fedges(i)[0])) - fi["o"]) @ fi["a"]
        bends.append({"face": i, "inner": i, "r_outer": None, "r_inner": _r(fi["r"]), "angle": _r(fi["span"], 2),
                      "length": _r(s.max() - s.min()), "legs": legs, "axis_point": fi["o"] + fi["a"] * float(s.min()),
                      "axis_dir": fi["a"]})
    bends.sort(key=lambda b: tuple(np.round(b["axis_point"], 2)))
    sharp = []
    for i in skin:
        for j, es in adj[i].items():
            if j in plate_of and j > i and abs(float(infos[i]["n"] @ infos[j]["n"])) < 1 - EPS_N \
                    and wall_of[i] != wall_of[j]:
                from OCP.BRepAdaptor import BRepAdaptor_Curve
                from OCP.GCPnts import GCPnts_AbscissaPoint
                ln = sum(GCPnts_AbscissaPoint.Length_s(BRepAdaptor_Curve(e)) for e in es)
                ang = math.degrees(math.acos(max(-1, min(1, float(infos[i]["n"] @ infos[j]["n"])))))
                sharp.append({"panels": sorted({walls[wall_of[i]]["name"], walls[wall_of[j]]["name"]}),
                              "length": _r(ln), "angle": _r(ang, 2)})
    seen_sh, sharp_u = set(), []
    for s_ in sharp:
        key = (tuple(s_["panels"]), s_["length"])
        if key not in seen_sh:
            seen_sh.add(key)
            sharp_u.append(s_)

    # the bend lines on each panel (the tangent lines), and the plate connections for the flat pattern
    for w in walls:
        w["bend_lines"] = []
    for bi, b in enumerate(bends):
        b["id"] = f"B{bi + 1}"
        fi = infos[b["face"]]
        names = set()
        for j in b["legs"]:
            w = walls[wall_of[j]]
            names.add(w["name"])
            shared = adj[b["face"]][j]
            from OCP.BRepAdaptor import BRepAdaptor_Curve
            for e in shared:
                c = BRepAdaptor_Curve(e)
                p0, p1 = _v(c.Value(c.FirstParameter())), _v(c.Value(c.LastParameter()))
                a0, a1 = w["frame"].uv(p0), w["frame"].uv(p1)
                w["bend_lines"].append({"bend": b["id"], "p": [_r(a0[0]), _r(a0[1])], "q": [_r(a1[0]), _r(a1[1])]})
        b["panels"] = sorted(names)
        if len(b["legs"]) == 2:
            conns.append((b, b["legs"][0], b["legs"][1]))

    # ---- hardware (clinch nuts and the like) -----------------------------------------------------------------------
    bodies = []
    for i, fi in enumerate(infos):
        if fi["kind"] == "cyl" and fi["convex"] and fi["span"] > 359.0:
            for hw in hardware:
                if hw.get("body_d") and abs(fi["r"] - float(hw["body_d"]) / 2) < 0.01:
                    c = faces[i].BoundingBox().center
                    bodies.append((hw, np.array([c.x, c.y, c.z]), fi["a"]))

    # ---- per panel ---------------------------------------------------------------------------------------------------
    problems, panels_out = [], []
    n_feat = n_bad_edges = 0
    for w in walls:
        fr = w["frame"]
        hw_rows, hw_c = [], []
        for hw, ctr, a in bodies:
            if abs(abs(float(a @ fr.n)) - 1) > 1e-3:
                continue
            dist = float(ctr @ fr.n) - fr.off
            own = np.array([p for i in w["faces"][w["side"]] for p in wire_path(fedges(i)[0])])
            uvs = np.array([fr.uv(p) for p in own])
            u, v = fr.uv(ctr)
            if not (-t - 6 <= dist <= 6 and uvs[:, 0].min() <= u <= uvs[:, 0].max() and uvs[:, 1].min() <= v <= uvs[:, 1].max()):
                continue
            hw_rows.append({"code": hw.get("code", ""), "thread": hw.get("thread", ""), "u": _r(u), "v": _r(v),
                            "hole": hw.get("hole_d"), "body": "outer face" if dist > 0 else "inner face",
                            "modelled": True})
            hw_c.append((u, v))
        fcs, feats = [], []
        for i in w["faces"][w["side"]]:
            oe, inner = fedges(i)
            nd = nodes(oe, fr)
            if nd is None:
                n_bad_edges += 1
                problems.append(f"{w['name']}: an outline edge is neither a line nor an arc")
            fcs.append({"nodes": nd, "path": [[_r(a), _r(b)] for a, b in (fr.uv(p) for p in wire_path(oe))]})
            for we in inner:
                ft = classify(we, fr)
                if ft["kind"] == "hole":
                    own_hw = next((h for h in hw_rows if h["modelled"] and math.hypot(ft["u"] - h["u"], ft["v"] - h["v"])
                                   < 0.05), None)
                    if own_hw is not None:      # the bore of a modelled nut: in the hardware table, with its size
                        own_hw["model_d"] = ft["d"]
                        own_hw["path"] = [[_r(a), _r(b)] for a, b in (fr.uv(p) for p in wire_path(we))]
                        continue
                if ft["kind"] == "hole":
                    hit = next((hw for hw in hardware if hw.get("hole_d") and abs(ft["d"] - float(hw["hole_d"])) < 0.03),
                               None)
                    if hit is not None:
                        hw_rows.append({"code": hit.get("code", ""), "thread": hit.get("thread", ""), "u": ft["u"],
                                        "v": ft["v"], "hole": ft["d"], "body": "", "modelled": False,
                                        "path": [[_r(a), _r(b)] for a, b in (fr.uv(p) for p in wire_path(we))]})
                        continue
                if ft.get("undimensionable"):
                    n_bad_edges += 1
                    problems.append(f"{w['name']}: a cut-out at X {ft['u']:g} Y {ft['v']:g} has an edge that is neither "
                                    "a line nor an arc")
                ft["path"] = [[_r(a), _r(b)] for a, b in (fr.uv(p) for p in wire_path(we))]
                feats.append(ft)
        pats, rest = find_patterns(feats, pattern_min)
        c = w["code"]
        k = 0
        for fc in fcs:
            ids = []
            for _nd in fc["nodes"] or []:
                k += 1
                ids.append(f"{c}-N{k}")
            fc["node_ids"] = ids
        order_k = {"hole": 0, "slot": 1, "rect": 2, "cutout": 3}
        letter = {"hole": "H", "slot": "S", "rect": "C", "cutout": "C"}
        rest.sort(key=lambda f: (order_k[f["kind"]], round(f["v"], 1), f["u"]))
        cnt = {}
        for f in rest:
            lt = letter[f["kind"]]
            cnt[lt] = cnt.get(lt, 0) + 1
            f["id"] = f"{c}-{lt}{cnt[lt]}"
        pats.sort(key=lambda p: (p["extent"][1], p["extent"][0]))
        for i, p in enumerate(pats):
            p["id"] = f"{c}-PT{i + 1}"
        hw_rows.sort(key=lambda p: (p["v"], p["u"]))
        for i, p in enumerate(hw_rows):
            p["id"] = f"{c}-P{i + 1}"
        n_feat += len(rest) + sum(p["n"] for p in pats) + len(hw_rows)
        std = w["std"]
        seen_txt = ("from above, through the part (the outside of this panel looks down)" if w["seen"] == "inside"
                    else SEEN.get(std, "square on, from outside"))
        datum = ("X and Y from the part's outer extremes (the lower-left corner of the view)" if w["axis_aligned"]
                 else "X and Y from this panel's own lower-left extremes")
        panels_out.append({
            "name": w["name"], "code": c, "normal": [_r(x, 6) for x in w["n"]], "seen": w["seen"],
            "seen_text": seen_txt, "datum_text": datum,
            "origin": [_r(x, 4) for x in fr.origin()], "u": [_r(x, 6) for x in fr.u], "v": [_r(x, 6) for x in fr.v],
            "extent": w["extent"], "area": _r(w["area"], 2), "faces": fcs, "features": rest, "patterns": pats,
            "hardware": hw_rows, "bend_lines": w["bend_lines"]})
    rows.append(("03", "every edge of every outline and cut-out is a line or an arc", f"{n_bad_edges} other edge(s)",
                 "0 (a free curve cannot be dimensioned)", "pass" if n_bad_edges == 0 else "fail"))
    big_other = [i for i in big_other
                 if not any(np.linalg.norm(np.array(faces[i].Center().toTuple()) - c_) < float(hw_["body_d"])
                            for hw_, c_, _a in bodies)]
    rows.append(("04", "every large flat face is one side of a sheet wall",
                 f"{len(big_other)} face(s) without a twin at {t:g}; {len(odd_faces)} face(s) neither flat nor "
                 "cylindrical", "0 / 0", "pass" if not big_other and not odd_faces else "fail"))
    for i in big_other:
        c = faces[i].Center()
        problems.append(f"flat face at ({c.x:.1f}, {c.y:.1f}, {c.z:.1f}), area {areas[i]:.1f}: no opposite face at "
                        f"{t:g} (not a sheet wall: hardware, a pocket or a second thickness)")
    rows.append(("06", "every bend is a cylindrical face", f"{len(bends)} cylindrical, {len(sharp_u)} sharp",
                 "0 sharp (a sharp bend has no radius to make and cannot be unfolded)",
                 "pass" if not sharp_u else "fail"))
    flat = unfold(plates, conns, infos, areas, faces, fedges, plate_of, walls, wall_of, t, k_factor, shape)
    rows.append(("05", "flat pattern estimated (reference only)", flat.get("note", ""),
                 "one connected blank; area x t within 3 % of the volume",
                 "pass" if flat.get("ok") else "could_not_run"))
    out = {
        "script": "sheet_features", "part": name, "units": "mm",
        "step": {"path": os.path.basename(step), "sha256": mc.sha256(step)},
        "thickness": t, "thickness_nominal": thickness, "solids": len(solids),
        "bbox": {"min": [_r(x) for x in lo], "size": [_r(x) for x in hi - lo]},
        "volume": _r(shape.Volume(), 2),
        "panels": panels_out,
        "bends": [{"id": b["id"], "r_outer": b["r_outer"], "r_inner": b["r_inner"], "angle": b["angle"],
                   "length": b["length"], "panels": b["panels"], "axis_point": [_r(x) for x in b["axis_point"]],
                   "axis_dir": [_r(x, 6) for x in b["axis_dir"]], "true_cylinder": True} for b in bends],
        "sharp_bends": sharp_u, "flat": flat, "problems": problems,
        "counts": {"panels": len(panels_out), "features": n_feat, "bends": len(bends), "sharp_bends": len(sharp_u)},
    }
    return out, rows


# ---------------------------------------------------------------- patterns -------------------------------------------
def find_patterns(feats, dmin=6):
    """Connected sets of equal holes on one pitch (>= dmin holes) -> (patterns, the other features). A pattern:
    {d, pitch, row_axis "X"|"Y", rows [[cross, first, count]], n, extent, lattice, holes}: in a row the holes are
    exactly `pitch` apart along row_axis, starting at `first`; `cross` is the row's other coordinate."""
    import numpy as np
    from scipy.spatial import cKDTree

    holes = [f for f in feats if f["kind"] == "hole"]
    rest = [f for f in feats if f["kind"] != "hole"]
    by_d = {}
    for h in holes:
        by_d.setdefault(round(h["d"], 2), []).append(h)
    pats = []
    for d, hs in sorted(by_d.items()):
        if len(hs) < dmin:
            rest += hs
            continue
        xy = np.array([(h["u"], h["v"]) for h in hs])
        tree = cKDTree(xy)
        nn = tree.query(xy, k=2)[0][:, 1]
        pitch = float(np.median(nn))
        pairs = tree.query_pairs(pitch + 0.02)
        parent = list(range(len(hs)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for a, b in pairs:
            if abs(np.hypot(*(xy[a] - xy[b])) - pitch) < 0.02:
                parent[find(a)] = find(b)
        groups = {}
        for i in range(len(hs)):
            groups.setdefault(find(i), []).append(i)
        for g in groups.values():
            if len(g) < dmin:
                rest += [hs[i] for i in g]
                continue
            best = None
            for axis in (0, 1):
                rws = {}
                for i in g:
                    key = next((k for k in rws if abs(k - xy[i][1 - axis]) < 0.01), xy[i][1 - axis])
                    rws.setdefault(key, []).append(xy[i][axis])
                runs = []
                for cross, vals in sorted(rws.items()):
                    vals = sorted(vals)
                    start, cnt = vals[0], 1
                    for a, b in zip(vals[:-1], vals[1:]):
                        if abs(b - a - pitch) < 0.02:
                            cnt += 1
                        else:
                            runs.append([_r(cross), _r(start), cnt])
                            start, cnt = b, 1
                    runs.append([_r(cross), _r(start), cnt])
                if best is None or len(runs) < len(best[1]):
                    best = (axis, runs)
            axis, runs = best
            if len(runs) > len(g) / 2:
                rest += [hs[i] for i in g]
                continue
            cr = sorted({r[0] for r in runs})
            step = float(np.median(np.diff(cr))) if len(cr) > 1 else 0.0
            lattice = ("hex" if abs(step - pitch * math.sqrt(3) / 2) < 0.02 else
                       "square" if abs(step - pitch) < 0.02 else "rows")
            us, vs = xy[g, 0], xy[g, 1]
            pats.append({"kind": "pattern", "d": _r(d), "pitch": _r(pitch), "row_axis": "XY"[axis], "rows": runs,
                         "row_step": _r(step), "n": len(g), "lattice": lattice,
                         "extent": [_r(us.min() - d / 2), _r(vs.min() - d / 2), _r(us.max() + d / 2), _r(vs.max() + d / 2)],
                         "holes": [[_r(xy[i][0]), _r(xy[i][1])] for i in g]})
    return pats, rest


# ---------------------------------------------------------------- flat pattern ---------------------------------------
def _rot(axis_p, axis_d, ang):
    import numpy as np

    a = axis_d / np.linalg.norm(axis_d)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    R = np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = axis_p - R @ axis_p
    return M


def unfold(plates, conns, infos, areas, faces, fedges, plate_of, walls, wall_of, t, k, shape):
    """The flat blank, for reference: every plate turned about its bends into the largest plate's plane, each bend
    replaced by a strip of the bend allowance angle x (inner radius + K x t)."""
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    if not plates:
        return {"ok": False, "note": "no sheet wall found", "reference_only": True}
    base = max(range(len(plates)), key=lambda p: areas[plates[p][0]])
    M = {base: np.eye(4)}
    strips, lines = [], []
    todo = [base]
    links = {}
    for b, f1, f2 in conns:
        links.setdefault(plate_of[f1], []).append((b, f1, f2))
        links.setdefault(plate_of[f2], []).append((b, f2, f1))

    def app(Mx, p):
        return Mx[:3, :3] @ p + Mx[:3, 3]

    from OCP.BRepAdaptor import BRepAdaptor_Curve
    adj_edges = {}
    while todo:
        p = todo.pop(0)
        for b, fp, fq in links.get(p, []):
            q = plate_of[fq]
            if q in M:
                continue
            fi = infos[b["face"]]
            a, o = fi["a"], fi["o"]
            th = math.radians(b["angle"])
            n_p, n_q = infos[fp]["n"], infos[fq]["n"]
            R = None
            for ang in (th, -th):
                Rm = _rot(o, a, ang)
                if np.linalg.norm(Rm[:3, :3] @ n_q - n_p) < 1e-3:
                    R = Rm
            if R is None:
                continue
            ri = b["r_inner"] if b["r_inner"] is not None else max((b["r_outer"] or t) - t, 0.0)
            ba = th * (ri + k * t)
            d = np.cross(n_p, a)
            # the tangent line on plate p: the bend face's straight edge lying in p's plane
            e_p = _shared_line(faces, b["face"], fp, adj_edges, shape)
            if e_p is None:
                continue
            if (fi["mid"] - e_p[0]) @ d < 0:
                d = -d
            T = np.eye(4)
            T[:3, 3] = d * ba
            M[q] = M[p] @ T @ R
            e0, e1 = app(M[p], e_p[0]), app(M[p], e_p[1])
            dd = M[p][:3, :3] @ d * ba
            strips.append((b["id"], [e0, e1, e1 + dd, e0 + dd]))
            lines.append((b["id"], e0 + dd / 2, e1 + dd / 2))
            todo.append(q)
    bw = walls[wall_of[plates[base][0]]]
    fr = bw["frame"]
    polys, holes = [], []
    for p, (fa, fb) in enumerate(plates):
        if p not in M:
            continue
        f = fa if infos[fa]["n"] @ (M[p][:3, :3].T @ fr.n) > 0 else fb
        oe, inner = fedges(f)
        polys.append([fr.uv(app(M[p], q)) for q in wire_path(oe)])
        for we in inner:
            holes.append([fr.uv(app(M[p], q)) for q in wire_path(we)])
    geo = [Polygon(o).buffer(0) for o in polys] + [Polygon([fr.uv(q) for q in s]).buffer(0) for _i, s in strips]
    blank = unary_union([g.buffer(1e-4) for g in geo]).buffer(-1e-4)
    for h in holes:
        blank = blank.difference(Polygon(h).buffer(0))
    x0, y0, x1, y1 = blank.bounds
    parts = list(blank.geoms) if hasattr(blank, "geoms") else [blank]
    vol = shape.Volume()
    ratio = blank.area * t / vol if vol else 0.0
    ok = len(parts) == 1 and len(M) == len(plates) and abs(ratio - 1) < 0.03

    def sh(pt):
        return [_r(pt[0] - x0), _r(pt[1] - y0)]

    rings_out, rings_in = [], []
    for g in parts:
        rings_out.append([sh(c) for c in g.exterior.simplify(0.002).coords])
        for r in g.interiors:
            rings_in.append([sh(c) for c in r.simplify(0.002).coords])
    note = (f"blank {x1 - x0:.2f} x {y1 - y0:.2f}, area {blank.area:.1f} mm2, area x t / volume = {ratio:.4f}, "
            f"{len(M)} of {len(plates)} walls unfolded, K {k:g}")
    return {"ok": bool(ok), "reference_only": True, "k_factor": k, "base_panel": bw["name"],
            "size": [_r(x1 - x0), _r(y1 - y0)], "area": _r(blank.area, 2), "area_t_over_volume": _r(ratio, 4),
            "pieces": len(parts), "outer": rings_out, "holes": rings_in,
            "bend_lines": [{"bend": i, "p": sh(fr.uv(a)), "q": sh(fr.uv(b))} for i, a, b in lines],
            "bend_strips": [{"bend": i, "poly": [sh(fr.uv(q)) for q in s]} for i, s in strips], "note": note}


def _shared_line(faces, cyl_i, face_i, cache, shape):
    """The two ends of the straight edge a bend face shares with a wall face."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line

    best = None
    for e in faces[cyl_i].Edges():
        c = BRepAdaptor_Curve(e.wrapped)
        if c.GetType() != GeomAbs_Line:
            continue
        for e2 in faces[face_i].Edges():
            if e.wrapped.IsSame(e2.wrapped):
                p0, p1 = _v(c.Value(c.FirstParameter())), _v(c.Value(c.LastParameter()))
                if best is None or ((p1 - p0) @ (p1 - p0)) > ((best[1] - best[0]) @ (best[1] - best[0])):
                    best = (p0, p1)
    return best


# ---------------------------------------------------------------- command line ---------------------------------------
def run_part(job_args):
    step, name, out, thickness, k, pmin, hardware, bottom_view, panel_names = job_args
    feats, rows = extract(step, name, thickness, k, pmin, hardware, bottom_view, panel_names)
    d = os.path.join(out, "drawings")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{name}.features.json")
    mc.atomic_write(path, json.dumps(feats, indent=1) + "\n")
    return name, path, rows, feats["counts"], feats["problems"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="STEP of one sheet-metal part -> features JSON")
    mc.add_std_args(ap)
    ap.add_argument("--step")
    ap.add_argument("--name")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--thickness", type=float)
    ap.add_argument("--k-factor", type=float)
    ap.add_argument("--pattern-min", type=int)
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    mc.reexec_with_cadquery(job.cfg)
    for lib in ("numpy", "shapely", "scipy"):
        mc.require_module(lib, "sheet_features.py")
    sh = job.cfg.get("sheet", {})
    thickness = args.thickness if args.thickness is not None else sh.get("thickness")
    k = args.k_factor if args.k_factor is not None else sh.get("k_factor", 0.44)
    pmin = args.pattern_min or sh.get("pattern_min", 6)
    hardware = sh.get("hardware", [])
    todo = []
    if args.all:
        for p in sh.get("parts", []):
            todo.append((mc.rel_to_project(job.cfg, p["step"]), p["name"]))
    elif args.step:
        todo.append((os.path.abspath(args.step), args.name or os.path.splitext(os.path.basename(args.step))[0]))
    if not todo:
        print("could not run: give --step <file> or --all with [sheet] parts in mech.toml", file=sys.stderr)
        return 2
    missing = [s for s, _n in todo if not os.path.isfile(s)]
    if missing:
        print("could not run: STEP not found: " + ", ".join(missing), file=sys.stderr)
        return 2
    jobs = [(s, n, job.out, thickness, k, pmin, hardware, sh.get("bottom_view", "above"), sh.get("panel_names"))
            for s, n in todo]
    rows = mc.Rows()
    results = []
    try:
        if len(jobs) == 1:
            results.append(run_part(jobs[0]))
        else:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=min(mc.workers(), len(jobs))) as ex:
                for k_, r in enumerate(ex.map(run_part, jobs)):
                    print(f"  [{k_ + 1}/{len(jobs)}] {r[0]}", flush=True)
                    results.append(r)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    for name, path, prows, counts, problems in results:
        for rid, check, value, rule, verdict in prows:
            rows.add(f"SF-{name}-{rid}", f"features:{name}", check, value, rule, verdict)
        print(f"{name}: {counts['panels']} panels, {counts['features']} features, {counts['bends']} bends"
              f"{', ' + str(counts['sharp_bends']) + ' SHARP bends' if counts['sharp_bends'] else ''} -> {path}")
        for p in problems:
            print("   problem:", p)
    rows.write(job.out, "sheet_features.py", [s for s, _n in todo])
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
