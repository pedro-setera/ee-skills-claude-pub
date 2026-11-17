"""Drawing = STEP: rebuild every feature from the numbers printed on the drawing and match it to the STEP's edges.

What it does
    Reads <out>/drawings/drawing_manifest.json (the numbers drawing_book.py printed, 2 decimals) and the part's
    STEP, with code of its own (it does not use sheet_features.py):
      - every hole, slot, rectangle, cut-out, pattern hole, hardware hole and outline is rebuilt as a curve from
        the printed X, Y and sizes alone, in the panel's datum frame, and must lie on the STEP's edges within the
        tolerance (default 0.05 mm): one row per feature with its worst deviation. A hole row prints both numbers:
        "printed d 6.50, STEP d 6.50" (the second is measured on the STEP's own edge loop by this script's reader);
        no number of the features file (`model_d` or any other) stands in for the printed one;
      - a hardware hole whose nut is MODELLED is filled by the nut in the STEP, so the printed hole cannot be seen
        there: the row proves the printed X, Y against the STEP's bore (measured in the STEP), that the bore is smaller
        than the printed hole, and that the bore the features file recorded is the one in the STEP;
      - every inner and outer edge loop of the STEP on a drawn panel must be covered by such a rebuilt curve: a
        hole or cut-out without a dimension fails, with its place;
      - every wide flat face of the STEP must lie on a drawn panel (or be its back): a wall with no sheet fails;
      - the printed bend table (outer radius, angle, length) must match the STEP's bend cylinders one to one;
      - the STEP's checksum must be the one the drawing was made from (a drawing of an older STEP fails);
      - with PyMuPDF: every ID with its X and Y must really be printed in the PDF.

Why it exists (the real failure, told without names)
    A drawing looked complete and still missed dimensions: the features had been listed by hand from the model.
    Only a check that starts from the uploaded STEP and asks "which printed number defines this edge?" found
    them all. With it in place the order went through the supplier's review without one geometry question.
    One row still passed for the wrong reason: a modelled nut was rebuilt from the bore that the features file had
    measured, not from the hole the drawing prints, so the row passed whatever number was printed.

Usage
    python -I drawing_vs_step.py --part NAME --step <part.step> [--manifest <drawing_manifest.json>] [--tol 0.05]
                                 [--pdf <part.pdf>] [--project <mech folder>] [--out <folder>]
    python -I drawing_vs_step.py --all [--project <mech folder>] [--out <folder>]
        --part/--step   one part (the STEP may also come from [sheet] parts)      --all  every part, on all cores
        --manifest      default <out>/drawings/drawing_manifest.json
        --tol           the largest distance between a rebuilt curve and the STEP edge (mm)
        --pdf           default <out>/drawings/<part>.pdf
    Needs CadQuery, numpy, scipy, shapely; PyMuPDF for the PDF rows (without it those rows are "could not run").

Config keys (mech.toml)
    [sheet] parts = [ {name, step} ]          [drawing] check_tol = 0.05

Exit codes
    0 every row passes      1 a feature does not match, an edge has no dimension, a face has no panel, or the STEP
    changed since the drawing      2 could not run (no manifest, no STEP, CadQuery missing, or PyMuPDF missing for
    the PDF rows while nothing else failed)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import math
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

STEP_S = 0.04         # sampling step along curves, mm


# ---------------------------------------------------------------- curves from printed numbers ------------------------
def _arc(c, r, a0, a1):
    import numpy as np

    n = max(4, int(abs(a1 - a0) * r / STEP_S) + 1)
    a = np.linspace(a0, a1, n + 1)
    return np.c_[c[0] + r * np.cos(a), c[1] + r * np.sin(a)]


def _dense(pts, closed=True):
    import numpy as np

    pts = np.asarray(pts, float)
    if closed:
        pts = np.r_[pts, pts[:1]]
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(np.hypot(*(b - a)) / STEP_S))
        out.append(a + (b - a) * np.linspace(0, 1, n, endpoint=False)[:, None])
    return np.vstack(out) if out else pts


def circle(x, y, d):
    return _arc((x, y), d / 2, 0.0, 2 * math.pi)


def slot(x, y, w, length, along):
    import numpy as np

    r, h = w / 2, (length - w) / 2
    if along == "X":
        p = np.vstack([_arc((x + h, y), r, -math.pi / 2, math.pi / 2), _arc((x - h, y), r, math.pi / 2, 3 * math.pi / 2)])
    else:
        p = np.vstack([_arc((x, y + h), r, 0, math.pi), _arc((x, y - h), r, math.pi, 2 * math.pi)])
    return _dense(p)


def rect(x, y, w, h, r):
    import numpy as np

    if r <= 0:
        return _dense([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)])
    cs = [((x + w / 2 - r, y - h / 2 + r), -math.pi / 2), ((x + w / 2 - r, y + h / 2 - r), 0.0),
          ((x - w / 2 + r, y + h / 2 - r), math.pi / 2), ((x - w / 2 + r, y - h / 2 + r), math.pi)]
    return _dense(np.vstack([_arc(c, r, a, a + math.pi / 2) for c, a in cs]))


def from_nodes(nodes):
    """The closed curve of a node table: corners (virtual sharp + radius) and arcs to the next node."""
    import numpy as np

    n = len(nodes)
    P = [np.array([nd["X"], nd["Y"]], float) for nd in nodes]
    pts = []
    for i, nd in enumerate(nodes):
        nxt = P[(i + 1) % n]
        if "arc" in nd:
            cx, cy, r, sense = nd["arc"]
            a0 = math.atan2(P[i][1] - cy, P[i][0] - cx)
            a1 = math.atan2(nxt[1] - cy, nxt[0] - cx)
            if sense == "CCW":
                while a1 <= a0 + 1e-9:
                    a1 += 2 * math.pi
            else:
                while a1 >= a0 - 1e-9:
                    a1 -= 2 * math.pi
            pts.append(_arc((cx, cy), r, a0, a1)[:-1])
        elif nd.get("r", 0) > 0:
            prv = P[(i - 1) % n]
            d1, d2 = prv - P[i], nxt - P[i]
            d1, d2 = d1 / np.hypot(*d1), d2 / np.hypot(*d2)
            alpha = math.acos(max(-1.0, min(1.0, float(d1 @ d2))))
            r = nd["r"]
            tl = r / math.tan(alpha / 2)
            bis = (d1 + d2) / np.hypot(*(d1 + d2))
            c = P[i] + bis * r / math.sin(alpha / 2)
            t1, t2 = P[i] + d1 * tl, P[i] + d2 * tl
            a0, a1 = math.atan2(t1[1] - c[1], t1[0] - c[0]), math.atan2(t2[1] - c[1], t2[0] - c[0])
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi      # the short way round
            pts.append(_arc(c, r, a0, a0 + da))
        else:
            pts.append(P[i][None, :])
    return _dense(np.vstack(pts))


def measure_hole(cut_loops, x, y, near=0.6):
    """(diameter, centre offset) of the round cut-out loop of the STEP whose centre is nearest to (x, y) and within `near` mm, or None.
    `cut_loops` = point arrays of the STEP's inner edge loops (this script's own reader), in the panel's frame. The diameter is the
    loop's own width (half of the sum of its extents in X and Y); a loop that is not round (extents differ by more than 0.1) is no hole."""
    best = None
    for pts in cut_loops:
        lo, hi = pts.min(0), pts.max(0)
        w, h = float(hi[0] - lo[0]), float(hi[1] - lo[1])
        if abs(w - h) > 0.1 or w <= 0:
            continue
        off = math.hypot(float((lo[0] + hi[0]) / 2) - x, float((lo[1] + hi[1]) / 2) - y)
        if off <= near and (best is None or off < best[1]):
            best = ((w + h) / 2, off)
    return best


def rebuild_panel(pm, bore=None):
    """[(id, kind, points)] of everything printed for one panel; [(id, why)] for what cannot be rebuilt.
    A hole is rebuilt from the diameter PRINTED on the drawing. A modelled nut fills its hole in the STEP, so its printed hole cannot
    be seen there; it is rebuilt at the diameter of the bore measured in the STEP (`bore` = {id: diameter}, by this script's own
    reader) to prove its position. A value copied from the features file (`model_d`) is never used to rebuild anything."""
    out, bad = [], []
    for k, o in enumerate(pm.get("outlines", [])):
        if o.get("nodes"):
            out.append((f"outline {k + 1}", "outline", from_nodes(o["nodes"])))
        else:
            bad.append((f"outline {k + 1}", "no node table printed"))
    for f in pm.get("features", []):
        try:
            if f["kind"] == "hole":
                c = circle(f["X"], f["Y"], f["d"])
            elif f["kind"] == "slot":
                c = slot(f["X"], f["Y"], f["w"], f["l"], f["along"])
            elif f["kind"] == "rect":
                c = rect(f["X"], f["Y"], f["w"], f["h"], f.get("r", 0))
            elif f.get("nodes"):
                c = from_nodes(f["nodes"])
            else:
                bad.append((f["id"], "printed without dimensions"))
                continue
        except KeyError as e:
            bad.append((f["id"], f"a number is missing: {e}"))
            continue
        out.append((f["id"], f["kind"], c))
    for p in pm.get("patterns", []):
        import numpy as np
        cs = []
        for cross, first, count in p["rows"]:
            for k in range(int(count)):
                a = first + k * p["pitch"]
                cs.append(circle(a, cross, p["d"]) if p["row_axis"] == "X" else circle(cross, a, p["d"]))
        if cs:
            out.append((p["id"], f"pattern of {len(cs)}", np.vstack(cs)))
    for h in pm.get("hardware", []):
        if not h.get("hole"):
            bad.append((h["id"], "no hole diameter printed"))
            continue
        d = (bore or {}).get(h["id"]) if h.get("modelled") else None
        out.append((h["id"], "hardware hole", circle(h["X"], h["Y"], d or h["hole"])))
    return out, bad


# ---------------------------------------------------------------- the STEP, read apart -------------------------------
def _v(p):
    import numpy as np
    return np.array([p.X(), p.Y(), p.Z()])


def step_faces(path):
    """[{kind, n, o, area, outer: pts3, inner: [pts3], wide}] of every face; cylinders with r, a, span, convex, vlen."""
    import cadquery as cq
    import numpy as np
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_REVERSED

    shape = cq.importers.importStep(str(path)).val()

    def sample(w):
        pts = []
        ex = BRepTools_WireExplorer(w.wrapped)
        while ex.More():
            c = BRepAdaptor_Curve(ex.Current())
            a, b = c.FirstParameter(), c.LastParameter()
            n = max(2, int(GCPnts_AbscissaPoint.Length_s(c) / STEP_S) + 1)
            ps = [_v(c.Value(a + (b - a) * k / n)) for k in range(n + 1)]
            pts += (ps[::-1] if ex.Orientation() == TopAbs_REVERSED else ps)[:-1]
            ex.Next()
        return np.array(pts)

    out = []
    for f in shape.Faces():
        s = BRepAdaptor_Surface(f.wrapped)
        rev = f.wrapped.Orientation() == TopAbs_REVERSED
        if s.GetType() == GeomAbs_Plane:
            n = _v(s.Plane().Axis().Direction())
            n = -n if rev else n
            out.append({"kind": "plane", "n": n / np.linalg.norm(n), "o": _v(s.Plane().Location()), "area": f.Area(),
                        "outer": sample(f.outerWire()), "inner": [sample(w) for w in f.innerWires()]})
        elif s.GetType() == GeomAbs_Cylinder:
            a = _v(s.Cylinder().Axis().Direction())
            out.append({"kind": "cyl", "r": s.Cylinder().Radius(), "a": a / np.linalg.norm(a),
                        "span": math.degrees(s.LastUParameter() - s.FirstUParameter()), "convex": not rev,
                        "vlen": abs(s.LastVParameter() - s.FirstVParameter()),
                        "c": np.array(f.Center().toTuple())})
        else:
            out.append({"kind": "other"})
    return out


def is_wide(pts3, n, w):
    """True when a flat face holds a place wider than w (it is a wall, not a cut edge of the sheet)."""
    import numpy as np
    from shapely.geometry import Polygon

    h = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(n, h)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    p2 = np.c_[pts3 @ e1, pts3 @ e2]
    if len(p2) < 3:
        return False
    return not Polygon(p2).buffer(0).buffer(-w / 2).is_empty


# ---------------------------------------------------------------- one part -------------------------------------------
def check_part(job_args):
    import numpy as np
    from scipy.spatial import cKDTree

    name, step, man, tol, pdf = job_args
    rows = []

    def add(rid, check, value, rule, verdict):
        rows.append((f"DV-{name}-{rid}", check, value, rule, verdict))

    sha = mc.sha256(step)
    add("00", "the drawing was made from this STEP", f"STEP sha256 {sha[:12]}, drawing from {man['step_sha256'][:12]}",
        "the same checksum", "pass" if sha == man["step_sha256"] else "fail")
    faces = step_faces(step)
    t = man["thickness"]
    planes = [f for f in faces if f["kind"] == "plane"]
    on_panel = set()
    n_feat = n_bad = 0
    worst_all = 0.0
    for pname, pm in man["panels"].items():
        fr = pm["frame"]
        n, u, v, o = (np.array(fr[k], float) for k in ("normal", "u", "v", "origin"))
        off = float(n @ o)
        u0, v0 = float(o @ u), float(o @ v)

        def uv(P):
            return np.c_[P @ u - u0, P @ v - v0]

        loops = []          # (kind, pts2)
        for k, f in enumerate(planes):
            if f["n"] @ n > 0.9999 and abs(float(f["n"] @ f["o"]) - off) < 0.02:
                on_panel.add(id(f))
                if f["area"] > 0.3 and is_wide(f["outer"], f["n"], 1.2 * t):
                    loops.append(("outline", uv(f["outer"])))
                    loops += [("cut-out", uv(w)) for w in f["inner"]]
            elif f["n"] @ n < -0.9999 and abs(-float(f["n"] @ f["o"]) - (off - t)) < 0.02:
                on_panel.add(id(f))
        cut_loops = [pts for k_, pts in loops if k_ == "cut-out"]
        held = {f["id"]: (f["X"], f["Y"], f.get("d"), False, None) for f in pm.get("features", []) if f.get("kind") == "hole"}
        held.update({h["id"]: (h["X"], h["Y"], h.get("hole"), bool(h.get("modelled")), h.get("model_d")) for h in pm.get("hardware", [])})
        bore = {}
        for hid, (hx, hy, _pd, mod, _md) in held.items():
            m_ = measure_hole(cut_loops, hx, hy) if mod else None
            if m_:
                bore[hid] = m_[0]
        built, bad = rebuild_panel(pm, bore)
        for bid, why in bad:
            n_bad += 1
            add(f"{pname}-{bid}".replace(" ", ""), f"{pname}: {bid} can be rebuilt from the printed numbers", why,
                "every feature fully dimensioned", "fail")
        step_pts = np.vstack([p for _k, p in loops]) if loops else np.zeros((0, 2))
        tree_s = cKDTree(step_pts) if len(step_pts) else None
        for bid, kind, pts in built:
            n_feat += 1
            dev = float(tree_s.query(pts)[0].max()) if tree_s is not None else float("inf")
            worst_all = max(worst_all, dev if math.isfinite(dev) else 0.0)
            ok = dev <= tol
            said, rule = "", f"<= {tol:g}"
            if bid in held and held[bid][2]:
                hx, hy, pd, mod, md = held[bid]
                m_ = measure_hole(cut_loops, hx, hy)
                sd = m_[0] if m_ else None
                if mod and bid in bore:                    # the nut fills its hole: the printed hole is under the nut, the STEP shows the bore
                    said = f"printed hole d {pd:.2f} (under the nut), STEP bore d {sd:.2f}; "
                    rule += "; the STEP's bore smaller than the printed hole; the features file's bore equal to the STEP's"
                    if sd > pd - tol:
                        ok = False
                        said += "the bore is not smaller than the printed hole; "
                    if md and abs(md - sd) > tol:
                        ok = False
                        said += f"the features file says bore d {md:.2f}; "
                elif sd is not None:
                    said = f"printed d {pd:.2f}, STEP d {sd:.2f}; "
                else:
                    said = f"printed d {pd:.2f}, no round hole of the STEP near it; "
            n_bad += 0 if ok else 1
            add(f"{pname}-{bid}".replace(" ", ""), f"{pname}: {bid} ({kind}) as printed lies on the STEP's edges",
                said + (f"worst {dev:.3f} mm" if math.isfinite(dev) else "no STEP edge on this panel"), rule,
                "pass" if ok else "fail")
        all_b = np.vstack([p for _i, _k, p in built]) if built else np.zeros((0, 2))
        tree_b = cKDTree(all_b) if len(all_b) else None
        missing = []
        for kind, pts in loops:
            dev = float(tree_b.query(pts)[0].max()) if tree_b is not None else float("inf")
            if dev > tol:
                c = pts.mean(0)
                missing.append(f"{kind} near X {c[0]:.2f} Y {c[1]:.2f} (off by {dev:.2f})" if math.isfinite(dev)
                               else f"{kind} near X {c[0]:.2f} Y {c[1]:.2f}")
        add(f"{pname}-cover", f"{pname}: every edge loop of the STEP is covered by a printed dimension",
            f"{len(loops)} loops, not covered: " + ("; ".join(missing[:8]) if missing else "none"), "none uncovered",
            "pass" if not missing else "fail")
    # every wide flat face lies on a drawn panel (or is its back)
    hw = [(pm["frame"], h) for pm in man["panels"].values() for h in pm.get("hardware", []) if h.get("modelled")]
    stray = []
    for f in planes:
        if id(f) in on_panel or f["area"] <= 0.3 or not is_wide(f["outer"], f["n"], 1.2 * t):
            continue
        c = f["outer"].mean(0)
        near_hw = False
        for fr, h in hw:
            u, v, o = (np.array(fr[k], float) for k in ("u", "v", "origin"))
            if math.hypot(float((c - o) @ u) - h["X"], float((c - o) @ v) - h["Y"]) < 2.5 * (h.get("hole") or 4.0):
                near_hw = True
        if not near_hw:
            stray.append(f"({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f}) area {f['area']:.1f}")
    add("faces", "every wide flat face of the STEP is on a drawn panel", f"{len(stray)} stray"
        + (": " + "; ".join(stray[:6]) if stray else ""), "0", "pass" if not stray else "fail")
    # the bend table
    normals = [np.array(pm["frame"]["normal"], float) for pm in man["panels"].values()]
    cyl = [f for f in faces if f["kind"] == "cyl" and f["convex"] and f["span"] < 359
           and not (abs(f["vlen"] - t) < 0.02 and any(abs(abs(float(f["a"] @ n)) - 1) < 1e-4 for n in normals))]
    left = [b for b in man.get("bends", []) if b.get("r_outer") is not None]
    unmatched = []
    for f in cyl:
        hit = next((b for b in left if abs(b["r_outer"] - f["r"]) <= tol and abs(b["angle"] - f["span"]) <= 0.5
                    and abs(b["length"] - f["vlen"]) <= 0.1), None)
        if hit is None:
            unmatched.append(f"r {f['r']:.2f} angle {f['span']:.1f} length {f['vlen']:.1f}")
        else:
            left.remove(hit)
    okb = not unmatched and not left
    add("bends", "the printed bend table matches the STEP's bend cylinders",
        f"{len(cyl)} in the STEP, {len(man.get('bends', []))} printed"
        + (", STEP only: " + "; ".join(unmatched[:4]) if unmatched else "")
        + (", printed only: " + ", ".join(b["id"] for b in left) if left else ""),
        "one to one (outer r +-tol, angle +-0.5, length +-0.1)", "pass" if okb else "fail")
    rows += pdf_rows(name, man, pdf)
    return name, rows, n_feat, n_bad, worst_all


def pdf_rows(name, man, pdf):
    """Every ID with its X and Y is printed in the PDF (PyMuPDF)."""
    rid = f"DV-{name}-pdf"
    check = "every ID with its X and Y is printed in the PDF"
    if not pdf or not os.path.isfile(pdf):
        return [(rid, check, f"no PDF at {pdf}", "the PDF beside the manifest", "could_not_run")]
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return [(rid, check, "PyMuPDF is not installed", "all printed", "could_not_run")]
    lines = []
    with fitz.open(pdf) as doc:
        for page in doc:
            words = page.get_text("words")
            ws = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
            cur, y = [], None
            for w in ws:
                ym = (w[1] + w[3]) / 2
                if y is None or abs(ym - y) > 2.0:
                    if cur:
                        lines.append(cur)
                    cur, y = [], ym
                cur.append(w[4])
            if cur:
                lines.append(cur)
    idx = {}
    for ln in lines:
        for w in ln:
            idx.setdefault(w, []).append(ln)

    def f2(x):
        s = f"{float(x):.2f}"
        return "0.00" if s == "-0.00" else s

    want = []
    for pm in man["panels"].values():
        for f in pm.get("features", []):
            want.append((f["id"], [f2(f["X"]), f2(f["Y"])]))
            for nd in f.get("nodes") or []:
                want.append((nd["id"], [f2(nd["X"]), f2(nd["Y"])]))
        for h in pm.get("hardware", []):
            want.append((h["id"], [f2(h["X"]), f2(h["Y"])]))
        for o in pm.get("outlines", []):
            for nd in o.get("nodes") or []:
                want.append((nd["id"], [f2(nd["X"]), f2(nd["Y"])]))
        for p in pm.get("patterns", []):
            for k, (c, a, n) in enumerate(p["rows"]):
                want.append((str(k + 1), [f2(c), f2(a), str(int(n))]))
    for b in man.get("bends", []):
        want.append((b["id"], [f2(b["angle"]), f2(b["length"])]))
    miss = []
    for key, nums in want:
        if not any(all(x in ln for x in nums) for ln in idx.get(key, [])):
            miss.append(key)
    return [(rid, check, f"{len(want)} rows looked up, missing: " + (", ".join(miss[:10]) if miss else "none"),
             "none missing", "pass" if not miss else "fail")]


def main(argv=None):
    ap = argparse.ArgumentParser(description="match the drawing's printed numbers to the STEP")
    mc.add_std_args(ap)
    ap.add_argument("--part")
    ap.add_argument("--step")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--manifest")
    ap.add_argument("--pdf")
    ap.add_argument("--tol", type=float)
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    mc.reexec_with_cadquery(job.cfg)
    for lib in ("numpy", "scipy", "shapely"):
        mc.require_module(lib, "drawing_vs_step.py")
    d = os.path.join(job.out, "drawings")
    man_path = os.path.abspath(args.manifest) if args.manifest else os.path.join(d, "drawing_manifest.json")
    if not os.path.isfile(man_path):
        print(f"could not run: no manifest at {man_path} (run drawing_book.py first)", file=sys.stderr)
        return 2
    manifest = mc.load_json(man_path)
    tol = args.tol if args.tol is not None else job.cfg.get("drawing", {}).get("check_tol", 0.05)
    cfg_parts = {p["name"]: mc.rel_to_project(job.cfg, p["step"]) for p in job.cfg.get("sheet", {}).get("parts", [])}
    names = list(cfg_parts) if args.all else ([args.part] if args.part else [])
    if not names:
        print("could not run: give --part NAME (with --step) or --all", file=sys.stderr)
        return 2
    jobs = []
    for nm in names:
        step = os.path.abspath(args.step) if (args.step and not args.all) else cfg_parts.get(nm)
        if not step or not os.path.isfile(step):
            print(f"could not run: no STEP for part {nm!r} ({step})", file=sys.stderr)
            return 2
        if nm not in manifest.get("parts", {}):
            print(f"could not run: part {nm!r} is not in {man_path}", file=sys.stderr)
            return 2
        pdf = os.path.abspath(args.pdf) if (args.pdf and not args.all) else os.path.join(os.path.dirname(man_path),
                                                                                         f"{nm}.pdf")
        jobs.append((nm, step, manifest["parts"][nm], tol, pdf))
    results = []
    if len(jobs) == 1:
        results.append(check_part(jobs[0]))
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(mc.workers(), len(jobs))) as ex:
            for k, r in enumerate(ex.map(check_part, jobs)):
                print(f"  [{k + 1}/{len(jobs)}] {r[0]}", flush=True)
                results.append(r)
    rows = mc.Rows()
    for name, prows, n_feat, n_bad, worst in results:
        for rid, check, value, rule, verdict in prows:
            rows.add(rid, f"drawing=step:{name}", check, value, rule, verdict)
        print(f"{name}: {n_feat} printed features rebuilt, {n_bad} not matching, worst deviation {worst:.3f} mm")
    rows.write(job.out, "drawing_vs_step.py", [man_path] + [j[1] for j in jobs])
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
