"""Print check: rule audit of a part in its print pose, a slicer run on copies of your presets, and a test coupon.

What it does
    (a) Rule audit of an STL / STEP / BREP part, taken in its print pose (z up, lowest face on the bed; --pose FACE lays
        a named face of a STEP part on the bed first, the face the name says: "front" is the face at the minimum y):
        bounding box inside the bed; overhang faces steeper than the profile's limit (area and place listed; short flat
        ceilings, and the roof of a round hole in a vertical wall whose diameter is at most `bridge_max_mm`, are
        bridges and only noted); walls thinner than N extrusion widths (sampled horizontal sections, all cores);
        small-on-large flat steps (a narrow cross-section that starts on a large flat face with no root flare: the
        "thin on thick" snap risk), reported to be LOOKED AT.
        Overhang rows come one per region while a class has at most 5 regions; a class with more gets ONE row with the
        count and the worst value (ids PRT-OVH-BRIDGES, -HOLES, -CEILINGS, -SLOPES), so 46 small vent holes are one
        line, not 46. A real overhang (a slope or a ceiling past the limits, a round hole wider than `bridge_max_mm`)
        still fails, however few or many.
        The audit is approximate: sections are sampled every `section_step` mm, a wall thinner than one sample step in
        z or a feature smaller than a few tenths of a millimetre can be missed, slopes are judged by face normals, and
        the slicer remains the final judge.
    (b) Slicer run (--slice), only when a slicer CLI is present and the user has not declined it: copies the presets named
        in the printer profile to a work folder `<out>/print/slice/slice_*` (never the system temp folder) and slices with
        the copies (the originals are never opened for writing), then reads time, grams, support and the G-code line-type
        comments (overhang wall, bridge, support, floating) into rows. It is "could not run" (nothing is started, and the
        text you need to slice by hand is printed) when: `[tools] slicer = "none"` (declined by the user); no slicer is
        found; or the profile's [slicer] does not name every preset the slicer kind needs (machine, process and filament
        for Bambu / Orca; config for Prusa): the script never slices with the slicer's own defaults.
    (c) --coupon: writes a test coupon STEP/STL from the profile: rows of holes drawn at nominal +0.0 .. +0.5 mm for each
        screw size, a self-tapping post per screw size, an overhang ladder (30 to 60 degrees), a tab and slot pair at
        three clearances; sizes embossed where the font allows, always listed in a legend PNG and coupon.json.

Why it exists (the real failure, told without names)
    Printed parts broke (thin upright bars, a thin post on a flat step) and holes printed 0.3 mm small; the scrapped
    shell and the reprints cost days. Checking the rules on the file, then the slicer's own warnings, then a coupon
    that is printed first, moves the failures to the cheapest place. Two things made the audit useless in practice:
    a box with 46 small round vent holes gave 27 failing overhang rows that nobody could act on (the roof of a small
    hole is a bridge, and one line per class is readable), and a slicer the user had said not to use was run anyway,
    with no preset named and its work folders in the system temp folder.

Usage
    python -I print_check.py PART.stl [PART2.step ...] [--pose bottom|top|front|back|left|right] [--profile PRINTER_PROFILE.toml]
                             [--slice] [--out DIR] [--project <mech folder>]
    python -I print_check.py --coupon [--screws M2,M2.5,M3] [--profile ...] [--out DIR]
    Without a part and with --project the parts are those of [print] parts, or out/print/*.stl.

Config keys
    mech.toml [printer] profile = "path to PRINTER_PROFILE.toml (kept outside the skill)"; [tools] slicer, slicer_kind
              (slicer = "none": the user declined a slicer, it is never auto-detected and --slice runs nothing);
              [print] parts = [...], allow_support = false, step_verdict = "fail"|"na"
    PRINTER_PROFILE.toml
      [printer]  name, bed = [x, y, z], nozzle = 0.4, line_width = 0.45, layer_height = 0.2
      [rules]    max_overhang_deg = 45, bridge_max_mm = 8, min_wall_lines = 2, hole_shrink_mm = 0.3, section_step = 0.5,
                 min_overhang_area = 1.0, step_small_mm = 8, min_flat_area = 30
                 (hole_shrink_mm: 0.3 is the code default, a first guess; the coupon legend says "default 0.3, not yet measured"
                 until the profile carries a number of its own, which the coupon measured)
      [slicer]   machine = "machine.json", process = "process.json", filament = "filament.json"   (Bambu / Orca)
                 config = "settings.ini"                                                              (Prusa)
      [coupon]   thickness = 3.0, screws = ["M2", "M2.5", "M3"]

Exit codes
    0 all rows pass   1 a rule failed   2 could not run (no input, no CadQuery for STEP, no shapely) or only could-not-run rows
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import glob
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

PROFILE_DEFAULT = {
    "printer": {"name": "", "bed": [220.0, 220.0, 250.0], "nozzle": 0.4, "line_width": 0.45, "layer_height": 0.2},
    "rules": {"max_overhang_deg": 45.0, "bridge_max_mm": 8.0, "min_wall_lines": 2, "hole_shrink_mm": 0.3, "section_step": 0.5,
              "min_overhang_area": 1.0, "step_small_mm": 8.0, "min_flat_area": 30.0},
    "slicer": {}, "coupon": {"thickness": 3.0, "screws": ["M2", "M2.5", "M3"]},
}


def load_profile(path=None) -> tuple[dict, str]:
    prof = {k: dict(v) if isinstance(v, dict) else v for k, v in PROFILE_DEFAULT.items()}
    note = "no printer profile: defaults used (bed 220 x 220 x 250, nozzle 0.4, hole shrink 0.3 not yet measured)"
    # the hole shrink is a first guess (0.3 mm) until the profile carries a number the coupon measured
    prof["rules"]["hole_shrink_measured"] = False
    if path:
        if not os.path.isfile(path):
            raise mc.MechError(f"printer profile not found: {path}")
        d = mc.load_toml(path)
        for k, v in d.items():
            if isinstance(v, dict) and isinstance(prof.get(k), dict):
                prof[k].update(v)
            else:
                prof[k] = v
        hs = (d.get("rules") or {}).get("hole_shrink_mm")
        if isinstance(hs, (int, float)) and not isinstance(hs, bool):
            prof["rules"]["hole_shrink_measured"] = True
        else:
            prof["rules"]["hole_shrink_mm"] = PROFILE_DEFAULT["rules"]["hole_shrink_mm"]       # empty or not a number: the default
        note = ""
    return prof, note


# ---------------------------------------------------------------- mesh ----------------------------------------------
def load_mesh(path, pose=None):
    """-> numpy array (N, 3, 3) of triangles in the print pose (lowest point at z = 0, x/y minimum at 0)."""
    import numpy as np
    ext = os.path.splitext(path)[1].lower()
    if ext == ".stl":
        tris = _read_stl(path)
        if pose and pose != "bottom":
            raise mc.MechError("--pose works on STEP/BREP parts; rotate an STL in your slicer or export it in pose")
    elif ext in (".step", ".stp", ".brep"):
        import cadquery as cq
        import box_toolkit as bt
        if ext == ".brep":
            shp = cq.Shape.importBrep(path)
        else:
            vals = cq.importers.importStep(path).vals()
            shp = cq.Compound.makeCompound(vals) if len(vals) != 1 else vals[0]
        try:
            shp = bt.print_pose(shp, pose or "bottom")
        except ValueError as e:
            raise mc.MechError(str(e))
        v, t = shp.tessellate(0.02, 0.1)
        va = np.array([[p.x, p.y, p.z] for p in v], dtype=float)
        tris = va[np.array(t, dtype=int)]
    else:
        raise mc.MechError(f"unsupported part file {path} (STL, STEP or BREP)")
    mn = tris.reshape(-1, 3).min(axis=0)
    return tris - mn if (abs(mn) > 1e-9).any() and ext == ".stl" else tris


def _read_stl(path):
    import numpy as np
    with open(path, "rb") as f:
        data = f.read()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + 50 * n == len(data):
            dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            return np.frombuffer(data, dtype=dt, count=n, offset=84)["v"].astype(float)
    txt = data.decode("utf-8", "replace")
    pts = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", txt)
    if not pts or len(pts) % 3:
        raise mc.MechError(f"{path} is not a readable STL")
    return np.array(pts, dtype=float).reshape(-1, 3, 3)


def normals_areas(tris):
    import numpy as np
    c = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(c, axis=1)
    n = np.divide(c, ln[:, None], out=np.zeros_like(c), where=ln[:, None] > 1e-12)
    return n, ln / 2.0


def regions(tris, mask, key=1000):
    """Group the triangles of `mask` that share a vertex (union-find). -> list of index arrays."""
    import numpy as np
    idx = np.nonzero(mask)[0]
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i in idx:
        vs = [tuple(np.round(tris[i, j] * key).astype(int)) for j in range(3)]
        for v in vs:
            parent.setdefault(v, v)
        a = find(vs[0])
        for v in vs[1:]:
            b = find(v)
            if a != b:
                parent[b] = a
    groups = {}
    for i in idx:
        v = tuple(np.round(tris[i, 0] * key).astype(int))
        groups.setdefault(find(v), []).append(i)
    return [np.array(g) for g in groups.values()]


# ---------------------------------------------------------------- sections (all cores) --------------------------------
_TR = None


def _init_sections(path):
    global _TR
    import numpy as np
    _TR = np.load(path)


def section_polygon(tris, z):
    """Even-odd section polygon of the mesh at height z (shapely geometry, possibly empty)."""
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import linemerge
    from shapely.geometry import LineString
    zz = tris[:, :, 2]
    m = (zz.min(axis=1) < z) & (zz.max(axis=1) > z)
    segs = []
    for t in tris[m]:
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            za, zb = t[a, 2], t[b, 2]
            if (za - z) * (zb - z) < 0:
                k = (z - za) / (zb - za)
                p = t[a] + k * (t[b] - t[a])
                pts.append((round(float(p[0]), 4), round(float(p[1]), 4)))
        if len(pts) == 2 and pts[0] != pts[1]:
            segs.append(LineString(pts))
    if not segs:
        return Polygon()
    merged = linemerge(segs)
    lines = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    res = Polygon()
    for ln in lines:
        if ln.is_ring and len(ln.coords) >= 4:
            res = res.symmetric_difference(Polygon(ln.coords).buffer(0))
    return res


def _thin_of(poly, w):
    """The part of poly narrower than w (opening by w/2 with mitre joins)."""
    if poly.is_empty:
        return poly
    core = poly.buffer(-w / 2.0, join_style=2).buffer(w / 2.0, join_style=2)
    return poly.difference(core.buffer(0.02, join_style=2))


def level_task(args):
    """-> {z, area, thin: [(cx, cy, t_est, area)], wkb} for one section height."""
    z, w, want_wkb = args
    poly = section_polygon(_TR, z)
    thin = []
    t = _thin_of(poly, w)
    for g in (list(t.geoms) if hasattr(t, "geoms") else [t]):
        if g.is_empty or g.area < 0.3 or g.length <= 0:
            continue
        thin.append((round(g.centroid.x, 2), round(g.centroid.y, 2), round(2 * g.area / g.length * 1.0, 3), round(g.area, 2)))
    out = {"z": z, "area": round(poly.area, 3), "thin": thin}
    if want_wkb:
        out["wkb"] = poly.wkb
    return out


def run_levels(tris, tasks, n_workers=None):
    import numpy as np
    n = n_workers if n_workers is not None else mc.workers()
    tmp = tempfile.mkdtemp(prefix="print_check_")
    try:
        p = os.path.join(tmp, "tris.npy")
        np.save(p, tris)
        if n <= 1 or len(tasks) < 8:
            _init_sections(p)
            return [level_task(t) for t in tasks]
        with ProcessPoolExecutor(n, initializer=_init_sections, initargs=(p,)) as ex:
            return list(ex.map(level_task, tasks, chunksize=max(1, len(tasks) // (n * 4))))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- overhang classes ------------------------------------
GROUP_OVER = 5          # more regions than this in one class: one row for the class (count and worst value)


def hole_roof_diameter(tris, normals):
    """The diameter (mm) when the down-facing triangles `tris` (n, 3, 3) with unit `normals` are the roof of a round hole
    whose axis is horizontal (a hole through a vertical wall): all the normals are perpendicular to one horizontal axis,
    the points lie on one circle in the plane across that axis, and the normals point at the circle's centre (a hole, not
    the underside of a rod). None when it is anything else."""
    import numpy as np
    if len(normals) < 3:
        return None
    s = np.linalg.svd(normals, full_matrices=False)
    sv, a = s[1], s[2][-1]
    if sv[0] <= 0 or sv[1] < 0.08 * sv[0] or sv[-1] > 0.04 * sv[0] or abs(a[2]) > 0.05:
        return None                                       # not a curved strip, or its axis is not horizontal
    h = np.array([-a[1], a[0], 0.0])
    h /= np.linalg.norm(h)
    pts = tris.reshape(-1, 3)
    x, z = pts @ h, pts[:, 2]
    if np.ptp(x) < 1e-6 and np.ptp(z) < 1e-6:
        return None
    A = np.column_stack([x, z, np.ones_like(x)])
    sol, *_ = np.linalg.lstsq(A, -(x * x + z * z), rcond=None)
    cx, cz = -sol[0] / 2.0, -sol[1] / 2.0
    r2 = cx * cx + cz * cz - sol[2]
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    if float(np.abs(np.hypot(x - cx, z - cz) - r).max()) > max(0.05, 0.03 * r):
        return None                                       # the points do not lie on one circle
    centre = cx * h + cz * np.array([0.0, 0.0, 1.0]) + float(np.mean(pts @ a)) * a
    cen = tris.mean(axis=1)
    toward = np.einsum("ij,ij->i", normals, centre - cen)
    if float((toward > 0).mean()) < 0.9:
        return None                                       # the normals point away from the centre: a convex rod, not a hole
    return 2.0 * r


def overhang_rows(items, R, rows: mc.Rows, tag=""):
    """The overhang rows from the classified regions (`items`, biggest area first). A class is bridge (flat ceiling of
    span <= bridge_max_mm), hole (roof of a round hole of d <= bridge_max_mm in a vertical wall), ceiling (a flat ceiling
    wider than that) or slope. Bridges and holes pass; ceilings and slopes fail. A class with more than GROUP_OVER regions
    is ONE row (count and worst value); smaller classes keep one row per region."""
    lim, bm = R["max_overhang_deg"], R["bridge_max_mm"]
    by = {}
    for it in items:
        by.setdefault(it["cls"], []).append(it)
    k = 0
    for it in items:
        if len(by[it["cls"]]) > GROUP_OVER:
            continue
        k += 1
        rid = f"PRT{tag}-OVH-{k:02d}"
        a, where = it["area"], it["where"]
        if it["cls"] == "bridge":
            rows.add(rid, "print", "flat ceiling (bridge)", f"{a:.1f} mm2, span {it['span']:.1f} mm, {where}",
                     f"bridge span <= {bm:g} mm (noted, not a failure)", "pass")
        elif it["cls"] == "hole":
            rows.add(rid, "print", "round hole in a vertical wall (bridge)", f"{a:.1f} mm2, diameter {it['d']:.1f} mm, {where}",
                     f"hole diameter <= {bm:g} mm (noted, not a failure)", "pass")
        else:
            rows.add(rid, "print", f"overhang {it['ang']:.0f} degrees from vertical", f"{a:.1f} mm2, {where}",
                     f"<= {lim:g} degrees (or a bridge of <= {bm:g} mm); change the shape or add a taper", "fail")
    for cls, lst in by.items():
        if len(lst) <= GROUP_OVER:
            continue
        tot = sum(i["area"] for i in lst)
        if cls == "bridge":
            w = max(lst, key=lambda i: i["span"])
            rows.add(f"PRT{tag}-OVH-BRIDGES", "print", f"flat ceilings (bridges), {len(lst)} regions",
                     f"{len(lst)} regions, {tot:.0f} mm2 in all; widest span {w['span']:.1f} mm at {w['where']}",
                     f"bridge span <= {bm:g} mm (noted, not a failure)", "pass")
        elif cls == "hole":
            w = max(lst, key=lambda i: i["d"])
            lo_d = min(i["d"] for i in lst)
            dtxt = f"diameter {w['d']:.1f} mm" if w["d"] - lo_d < 0.05 else f"diameters {lo_d:.1f} to {w['d']:.1f} mm"
            rows.add(f"PRT{tag}-OVH-HOLES", "print", f"round holes in vertical walls (bridges), {len(lst)} holes",
                     f"{len(lst)} holes, {dtxt}, {tot:.0f} mm2 of roof in all; widest at {w['where']}",
                     f"hole diameter <= {bm:g} mm (noted, not a failure)", "pass")
        elif cls == "ceiling":
            w = max(lst, key=lambda i: i["span"])
            rows.add(f"PRT{tag}-OVH-CEILINGS", "print", f"flat ceilings wider than the bridge limit, {len(lst)} regions",
                     f"{len(lst)} regions, {tot:.0f} mm2 in all; widest span {w['span']:.1f} mm at {w['where']}",
                     f"bridge span <= {bm:g} mm; change the shape or add a taper", "fail")
        else:
            w = max(lst, key=lambda i: (i["ang"], i["area"]))
            big = max(lst, key=lambda i: i["area"])
            rows.add(f"PRT{tag}-OVH-SLOPES", "print", f"overhangs steeper than {lim:g} degrees, {len(lst)} regions",
                     f"{len(lst)} regions, {tot:.0f} mm2 in all; worst {w['ang']:.0f} degrees from vertical ({w['area']:.1f} mm2) at {w['where']}; "
                     f"largest {big['area']:.1f} mm2 at {big['where']}",
                     f"<= {lim:g} degrees (or a bridge of <= {bm:g} mm); change the shape or add a taper", "fail")


# ---------------------------------------------------------------- the audit ------------------------------------------
def audit(tris, prof, rows: mc.Rows, tag="", step_verdict="fail", n_workers=None):
    import numpy as np
    from shapely import wkb as swkb
    P, R = prof["printer"], prof["rules"]
    bb0, bb1 = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    size = bb1 - bb0
    bed = P["bed"]
    ok = all(size[i] <= bed[i] + 1e-6 for i in range(3))
    rows.add(f"PRT{tag}-BED", "print", "bounding box inside the bed", f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm",
             f"<= {bed[0]:g} x {bed[1]:g} x {bed[2]:g} mm", "pass" if ok else "fail")

    # overhangs
    n, area = normals_areas(tris)
    lim = math.sin(math.radians(R["max_overhang_deg"]))
    zmin = bb0[2]
    on_bed = tris[:, :, 2].max(axis=1) <= zmin + 0.05
    over = (n[:, 2] < -lim - 1e-9) & ~on_bed & (area > 1e-9)
    regs = [r for r in regions(tris, over) if area[r].sum() >= R["min_overhang_area"]]
    regs.sort(key=lambda r: -area[r].sum())
    items = []
    for r in regs:
        pts = tris[r].reshape(-1, 3)
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        a = float(area[r].sum())
        nz = float((n[r, 2] * area[r]).sum() / a)
        span = min(hi[0] - lo[0], hi[1] - lo[1])
        flat = nz < -0.98
        d = None if flat else hole_roof_diameter(tris[r], n[r])
        if flat and span <= R["bridge_max_mm"]:
            cls = "bridge"
        elif d is not None and d <= R["bridge_max_mm"]:
            cls = "hole"                                  # the roof of a small round hole in a vertical wall: a bridge
        else:
            cls = "ceiling" if flat else "slope"
        items.append({"cls": cls, "area": a, "ang": math.degrees(math.asin(min(1.0, -nz))), "span": span, "d": d,
                      "where": f"x {lo[0]:.1f}..{hi[0]:.1f}, y {lo[1]:.1f}..{hi[1]:.1f}, z {lo[2]:.1f}..{hi[2]:.1f}"})
    overhang_rows(items, R, rows, tag)
    if not regs:
        rows.add(f"PRT{tag}-OVH", "print", "overhang faces", "none steeper than the limit", f"<= {R['max_overhang_deg']:g} degrees", "pass")

    # sections: thin walls (and the section polygons for the steps)
    w = R["min_wall_lines"] * P["line_width"]
    h = bb1[2] - bb0[2]
    step = max(R["section_step"], h / 160.0)
    zs = [bb0[2] + step * (k + 0.5) for k in range(int(h / step))] or [bb0[2] + h / 2]
    flats = []
    up = (n[:, 2] > 0.99) & (tris[:, :, 2].max(axis=1) - tris[:, :, 2].min(axis=1) < 0.02) & (tris[:, 0, 2] > zmin + 0.5) & (area > 1e-9)
    for r in regions(tris, up):
        a = float(area[r].sum())
        if a >= R["min_flat_area"]:
            flats.append((a, float(tris[r[0], 0, 2]), r))
    flats.sort(key=lambda f: -f[0])
    flats = flats[:20]
    extra = []
    for a, zf, r in flats:
        extra += [zf - 0.3, zf + 0.3, zf + 2.3]
    t0 = time.time()
    res = run_levels(tris, [(z, w, False) for z in zs] + [(z, w, True) for z in extra], n_workers)
    print(f"  {len(zs)} + {len(extra)} sections in {time.time() - t0:.1f} s", flush=True)
    thin_res = res[:len(zs)]
    clusters = []
    for lv in thin_res:
        for cx, cy, t, a in lv["thin"]:
            for c in clusters:
                if abs(c["x"] - cx) < 2.5 and abs(c["y"] - cy) < 2.5 and lv["z"] - c["z1"] <= step * 1.6:
                    c["z1"], c["t"], c["n"] = lv["z"], min(c["t"], t), c["n"] + 1
                    break
            else:
                clusters.append({"x": cx, "y": cy, "z0": lv["z"], "z1": lv["z"], "t": t, "n": 1})
    # a single thin sample is a corner or a slope edge more often than a wall: needs 2 sections or 0.8 mm of height
    clusters = [c for c in clusters if c["n"] >= 2 or (c["z1"] - c["z0"]) >= 0.8]
    for i, c in enumerate(sorted(clusters, key=lambda c: c["t"])[:12], 1):
        rows.add(f"PRT{tag}-WALL-{i:02d}", "print", "thin wall (about, from sampled sections)", f"~{c['t']:.2f} mm at x {c['x']}, y {c['y']}, z {c['z0']:.1f}..{c['z1']:.1f}",
                 f">= {R['min_wall_lines']} x {P['line_width']:g} = {w:.2f} mm", "fail")
    if not clusters:
        rows.add(f"PRT{tag}-WALL", "print", "walls thinner than the minimum", f"none found in {len(zs)} sections", f">= {w:.2f} mm (approximate)", "pass")

    # small-on-large flat steps
    k = len(zs)
    found = 0
    seen = []
    for fi, (a, zf, r) in enumerate(flats):
        below, above, above2 = (swkb.loads(res[k + 3 * fi + j]["wkb"]) for j in range(3))
        comps = list(above.geoms) if hasattr(above, "geoms") else [above]
        from shapely.geometry import Polygon as _P
        from shapely.ops import unary_union as _U
        foot = _U([_P(tris[i, :, :2]).buffer(0) for i in r])
        fgs = list(foot.geoms) if hasattr(foot, "geoms") else [foot]
        fill = _U([_P(g.exterior) for g in fgs if not g.is_empty]).buffer(0.1)     # the flat face with its holes filled
        comps2 = list(above2.geoms) if hasattr(above2, "geoms") else [above2]
        for c in comps:
            if c.is_empty or c.area < 0.5 or below.area <= 0:
                continue
            mrr = c.minimum_rotated_rectangle
            xy = list(mrr.exterior.coords)
            e1, e2 = math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])
            narrow = min(e1, e2)
            inside = c.intersection(below).area >= 0.9 * c.area
            if not (inside and narrow <= R["step_small_mm"] and c.area <= 0.25 * below.area and c.within(fill)):
                continue                                  # it must stand in a hole of the flat face, i.e. rise out of it
            a2 = sum(g.area for g in comps2 if g.distance(c.centroid) < 1.0 + narrow / 2)
            if a2 > 0 and c.area >= 1.25 * a2:           # it widens toward the flat face: a root flare / cone
                continue
            key = (round(c.centroid.x), round(c.centroid.y), round(zf))
            if key in seen:
                continue
            seen.append(key)
            found += 1
            rows.add(f"PRT{tag}-STEP-{found:02d}", "print", "small section on a large flat face (thin-on-thick: look at it, it can snap)",
                     f"narrow {narrow:.1f} mm ({c.area:.1f} mm2) starts at z {zf:.1f} on a flat of {a:.0f} mm2, x {c.centroid.x:.1f}, y {c.centroid.y:.1f}, no root flare",
                     "give it a cone or a taper (about 1.5 x the diameter at the root), or LOOK at the slicer preview and waive", step_verdict)
    if not found:
        rows.add(f"PRT{tag}-STEP", "print", "small sections on large flat faces", f"none found in {len(flats)} flat face(s) of >= {R['min_flat_area']:g} mm2", "none, or with a root flare", "pass")


# ---------------------------------------------------------------- slicer ---------------------------------------------
def _hms(s):
    t = 0.0
    for v, u in re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", s):
        t += float(v) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u]
    return t


def parse_gcode(text: str) -> dict:
    """time_s, grams, moves {type: extrusion move count}. Reads Bambu/Orca ('; FEATURE:') and Prusa (';TYPE:') comments."""
    res = {"time_s": None, "grams": None, "moves": {}}
    cur = None
    for ln in text.splitlines():
        if ln.startswith(";"):
            m = re.match(r";\s*(?:TYPE|FEATURE)\s*:\s*(.+)", ln)
            if m:
                cur = m.group(1).strip()
                res["moves"].setdefault(cur, 0)
                continue
            m = re.search(r"total estimated time:\s*([0-9dhms .]+)", ln) or re.search(r"estimated printing time \(normal mode\)\s*=\s*([0-9dhms .]+)", ln)
            if m and res["time_s"] is None:
                res["time_s"] = _hms(m.group(1))
            m = re.search(r"(?:total filament weight \[g\]\s*:|filament used \[g\]\s*=)\s*([0-9.]+)", ln)
            if m and res["grams"] is None:
                res["grams"] = float(m.group(1))
        elif cur and (ln.startswith("G1") or ln.startswith("G0")) and re.search(r"\bE-?\d", ln) and not re.search(r"\bE-", ln):
            res["moves"][cur] += 1
    return res


def slicer_command(kind, exe, model, outdir, copies):
    if kind in ("bambu", "orca"):
        settings = ";".join(x for x in (copies.get("machine"), copies.get("process")) if x)
        cmd = [exe, "--outputdir", outdir, "--slice", "0"]
        if settings:
            cmd += ["--load-settings", settings]
        if copies.get("filament"):
            cmd += ["--load-filaments", copies["filament"]]
        return cmd + [model]
    if kind == "prusa":
        cmd = [exe, "--export-gcode", "--output", os.path.join(outdir, "out.gcode")]
        if copies.get("config"):
            cmd += ["--load", copies["config"]]
        return cmd + [model]
    raise mc.MechError(f"unknown slicer kind {kind!r} (bambu, orca, prusa)")


def find_gcode(outdir):
    for g in glob.glob(os.path.join(outdir, "**", "*.gcode"), recursive=True):
        return open(g, encoding="utf-8", errors="replace").read(), g
    for z in glob.glob(os.path.join(outdir, "**", "*.3mf"), recursive=True):
        with zipfile.ZipFile(z) as zf:
            for nm in zf.namelist():
                if nm.lower().endswith(".gcode"):
                    return zf.read(nm).decode("utf-8", "replace"), z + "!" + nm
    return None, None


PRESETS_NEEDED = {"bambu": ("machine", "process", "filament"), "orca": ("machine", "process", "filament"), "prusa": ("config",)}


def slice_part(cfg, prof, part_path, scratch_root, rows: mc.Rows, tag="", allow_support=False, timeout=900):
    """Slice a copy of `part_path` with COPIES of the profile's presets, in a work folder under `scratch_root` (the caller passes
    `<out>/print/slice`). Rows are could_not_run, and nothing is started, when the slicer is declined (`[tools] slicer = "none"`),
    not found, of an unknown kind, or when the profile's [slicer] does not name every preset the kind needs."""
    import env_check
    slc = prof.get("slicer", {})

    def by_hand():
        print(f"Slice by hand: open {os.path.basename(part_path)} in your slicer with your own presets, slice, and read: time, grams, support, and the\n"
              "  warnings or preview colours for overhang wall, bridge, floating shell. Send the numbers and the preview pictures back.")
    if env_check.is_declined(cfg, "slicer"):
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", 'declined by the user ([tools] slicer = "none"): nothing was run',
                 "slice with your presets and read the warnings", "could_not_run")
        by_hand()
        return
    kind, exe = env_check.find_slicer(cfg)
    if not exe:
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", "no slicer command line found", "slice with your presets and read the warnings",
                 "could_not_run")
        by_hand()
        return
    if kind not in PRESETS_NEEDED:
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", f"unknown slicer kind {kind!r} for {os.path.basename(exe)}",
                 "[tools] slicer_kind is bambu, orca or prusa", "could_not_run")
        by_hand()
        return
    unnamed = [k for k in PRESETS_NEEDED[kind] if not slc.get(k)]
    if unnamed:
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", "the printer profile's [slicer] names no " + ", ".join(unnamed) + " preset: nothing was run",
                 "name every preset in PRINTER_PROFILE.toml [slicer] (this script never slices with the slicer's own defaults)", "could_not_run")
        by_hand()
        return
    missing = [k for k in ("machine", "process", "filament", "config") if slc.get(k) and not os.path.isfile(slc[k])]
    if missing:
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", "preset file(s) not found: " + ", ".join(missing), "the profile's [slicer] paths exist", "could_not_run")
        return
    os.makedirs(scratch_root, exist_ok=True)
    work = tempfile.mkdtemp(prefix="slice_", dir=scratch_root)
    print(f"  slice work folder: {work}", flush=True)
    copies = {}
    for k in ("machine", "process", "filament", "config"):
        if slc.get(k):
            dst = os.path.join(work, "preset_" + k + os.path.splitext(slc[k])[1])
            shutil.copyfile(slc[k], dst)               # the slicer is given the COPY; the original is only read
            copies[k] = dst
    model = os.path.join(work, os.path.basename(part_path))
    shutil.copyfile(part_path, model)
    outdir = os.path.join(work, "out")
    os.makedirs(outdir)
    cmd = slicer_command(kind, exe, model, outdir, copies)
    print("  slicing:", " ".join(os.path.basename(c) if os.path.isfile(c) else c for c in cmd), flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, cwd=work)
    except (subprocess.TimeoutExpired, OSError) as e:
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", f"the slicer did not finish: {type(e).__name__}", "the slicer finishes", "could_not_run")
        return
    gtxt, gsrc = find_gcode(outdir)
    if r.returncode != 0 or gtxt is None:
        rows.add(f"PRT{tag}-SLC", "print", "slicer run", f"exit {r.returncode}, no G-code found. " + (r.stderr or r.stdout).strip()[-200:], "a sliced file", "fail")
        return
    g = parse_gcode(gtxt)
    rows.add(f"PRT{tag}-SLC-TIME", "print", "estimated print time", f"{g['time_s'] / 3600:.2f} h" if g["time_s"] else "not found in the G-code", "read from the slicer", "pass" if g["time_s"] else "could_not_run")
    rows.add(f"PRT{tag}-SLC-GRAMS", "print", "filament weight", f"{g['grams']:.1f} g" if g["grams"] is not None else "not found in the G-code", "read from the slicer", "pass" if g["grams"] is not None else "could_not_run")
    mv = g["moves"]
    kinds = lambda *words: sum(v for k, v in mv.items() if any(w in k.lower() for w in words))
    sup, flo = kinds("support"), kinds("float")
    rows.add(f"PRT{tag}-SLC-SUP", "print", "support material", f"{sup} extrusion moves", "none" if not allow_support else "allowed by the project", "pass" if (allow_support or not sup) else "fail")
    rows.add(f"PRT{tag}-SLC-FLT", "print", "floating shells (slicer's own comment)", f"{flo} extrusion moves", "none", "pass" if not flo else "fail")
    rows.add(f"PRT{tag}-SLC-OVH", "print", "overhang wall lines", f"{kinds('overhang')} extrusion moves", "informational: look at them in the preview", "pass")
    rows.add(f"PRT{tag}-SLC-BRG", "print", "bridge lines", f"{kinds('bridge')} extrusion moves", "informational: look at them in the preview", "pass")


# ---------------------------------------------------------------- coupon --------------------------------------------
def make_coupon(prof, out_dir, screws=None):
    """Write coupon.step / .stl / _legend.png / .json to out_dir. Returns the feature list."""
    import cadquery as cq
    import box_toolkit as bt
    V = cq.Vector
    R, C = prof["rules"], prof["coupon"]
    t = float(C["thickness"])
    screws = screws or C.get("screws", ["M2", "M2.5", "M3"])
    for s in screws:
        if s not in bt.SCREWS:
            raise mc.MechError(f"unknown screw size {s}; known: {', '.join(bt.SCREWS)}")
    feats = []
    row_pitch = lambda s: bt.SCREWS[s]["d"] + 0.5 + 5.0
    y = 3.0
    holes = []
    x0, pitch_extra = 6.0, 4.5
    plate_w = 0.0
    layout = []
    for s in screws:
        d0 = bt.SCREWS[s]["d"]
        yc = y + (d0 + 0.5) / 2 + 1.0
        xc = x0
        for k in range(6):
            dd = d0 + 0.1 * k
            xc += (d0 + 0.5) / 2 + pitch_extra / 2 if k == 0 else 0
            holes.append((xc, yc, dd))
            feats.append({"kind": "hole", "screw": s, "x": round(xc, 2), "y": round(yc, 2), "d": round(dd, 2), "label": f"{s} +{0.1 * k:.1f}"})
            xc += (d0 + 0.5) + pitch_extra
        plate_w = max(plate_w, xc)
        y += (d0 + 0.5) + 5.0
    plate_w = max(plate_w, 100.0)
    # posts
    post_y = y + 6.0
    posts = []
    px = 12.0
    for s in screws:
        posts.append((px, post_y, s))
        feats.append({"kind": "post", "screw": s, "x": px, "y": post_y, "outer_d": bt.SCREWS[s]["post_d"], "pilot_d": bt.SCREWS[s]["pilot"], "height": 8.0})
        px += bt.SCREWS[s]["post_d"] + 10.0
    y = post_y + 10.0
    # overhang ladder
    ladder_y = y + 6.0
    angles = [30, 40, 45, 50, 60]
    ladder = []
    lx = 6.0
    for a in angles:
        ladder.append((lx, ladder_y, a))
        feats.append({"kind": "overhang", "angle_deg_from_vertical": a, "x": lx, "y": ladder_y, "ledge_mm": 6.0})
        lx += 16.0
    y = ladder_y + 12.0
    # mating slots
    slot_y = y + 5.0
    clear = [0.1, 0.2, 0.3]
    sx = 10.0
    slots, tabs = [], []
    for c in clear:
        slots.append((sx, slot_y, c))
        feats.append({"kind": "slot", "x": sx, "y": slot_y, "w": 6.0, "l": 12.0, "clearance_per_side": c})
        tabs.append((sx, -10.0, c))
        feats.append({"kind": "tab", "x": sx, "y": -10.0, "w": round(6.0 - 2 * c, 2), "l": round(12.0 - 2 * c, 2), "thickness": round(t - 0.6, 2), "clearance_per_side": c})
        sx += 22.0
    plate_l = slot_y + 12.0
    plate = bt.box(0, 0, 0, plate_w, plate_l, t)
    for xc, yc, dd in holes:
        plate = plate.cut(bt.cyl((xc, yc, -1), dd, t + 2))
    for xc, yc, c in slots:
        plate = plate.cut(bt.box(xc - 3.0, yc - 6.0, -1, xc + 3.0, yc + 6.0, t + 1))
    for xc, yc, s in posts:
        plate = plate.fuse(bt.stand((xc, yc, t - 0.2), 8.0, s)).clean()
    for xc, yc, a in ladder:
        col = bt.box(xc, yc, t - 0.01, xc + 4.0, yc + 8.0, t + 10.0)
        dz = 6.0 / math.tan(math.radians(a))
        z0 = t + 4.0
        prof_pts = [(xc + 4.0, z0), (xc + 10.0, z0 + dz), (xc + 10.0, z0 + dz + 2.0), (xc + 4.0, z0 + dz + 2.0)]
        ledge = cq.Workplane("XZ", origin=(0, yc + 8.0, 0)).polyline(prof_pts).close().extrude(8.0).val()
        plate = plate.fuse(col.fuse(ledge)).clean()
    solids = [plate]
    for xc, yc, c in tabs:
        solids.append(bt.box(xc - 3.0 + c, yc - 6.0 + c, 0, xc + 3.0 - c, yc + 6.0 - c, t - 0.6))
    comp = cq.Compound.makeCompound([s.val() if hasattr(s, "val") else s for s in solids])
    os.makedirs(out_dir, exist_ok=True)
    cq.exporters.export(cq.Workplane("XY").add(comp), os.path.join(out_dir, "coupon.stl"), "STL", tolerance=0.01)
    bt.export_step(comp, os.path.join(out_dir, "coupon.step"), "")
    import json
    mc.atomic_write(os.path.join(out_dir, "coupon.json"), json.dumps({"thickness": t, "hole_shrink_mm_profile": R.get("hole_shrink_mm", PROFILE_DEFAULT["rules"]["hole_shrink_mm"]),
                                                                           "hole_shrink_measured": bool(R.get("hole_shrink_measured")), "features": feats}, indent=1) + "\n")
    _legend(feats, plate_w, plate_l, R, os.path.join(out_dir, "coupon_legend.png"))
    return feats


def hole_shrink_text(R) -> str:
    """The profile's hole shrink as the coupon legend states it: a bare number when the profile carries a measured value,
    else the code default with "(default 0.3, not yet measured)"."""
    hs = R.get("hole_shrink_mm", PROFILE_DEFAULT["rules"]["hole_shrink_mm"])
    return f"{hs:g} mm" if R.get("hole_shrink_measured") else f"{hs:g} mm (default 0.3, not yet measured)"


def _legend(feats, W, L, R, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig, ax = plt.subplots(figsize=(11, 11 * (L + 24) / W / 1.0 if W else 8))
    ax.add_patch(Rectangle((0, 0), W, L, fc="#e8e8e8", ec="k"))
    for f in feats:
        if f["kind"] == "hole":
            ax.add_patch(Circle((f["x"], f["y"]), f["d"] / 2, fc="w", ec="k", lw=0.6))
            ax.text(f["x"], f["y"] + f["d"] / 2 + 0.8, f"{f['d']:.1f}", ha="center", va="bottom", fontsize=7)
        elif f["kind"] == "post":
            ax.add_patch(Circle((f["x"], f["y"]), f["outer_d"] / 2, fc="#c8d8f0", ec="k"))
            ax.add_patch(Circle((f["x"], f["y"]), f["pilot_d"] / 2, fc="w", ec="k", lw=0.6))
            ax.text(f["x"], f["y"] - f["outer_d"] / 2 - 1.0, f"{f['screw']} post\npilot {f['pilot_d']:.1f}", ha="center", va="top", fontsize=7)
        elif f["kind"] == "overhang":
            ax.add_patch(Rectangle((f["x"], f["y"]), 10, 8, fc="#f0d8c0", ec="k"))
            ax.text(f["x"] + 5, f["y"] - 1.0, f"{f['angle_deg_from_vertical']} deg", ha="center", va="top", fontsize=7)
        elif f["kind"] == "slot":
            ax.add_patch(Rectangle((f["x"] - 3, f["y"] - 6), 6, 12, fc="w", ec="k"))
            ax.text(f["x"], f["y"] + 7, f"slot, tab clearance {f['clearance_per_side']:.1f}/side", ha="center", va="bottom", fontsize=7)
        elif f["kind"] == "tab":
            ax.add_patch(Rectangle((f["x"] - f["w"] / 2, f["y"] - f["l"] / 2), f["w"], f["l"], fc="#d8f0c8", ec="k"))
            ax.text(f["x"], f["y"] - f["l"] / 2 - 1.0, f"tab {f['w']:.1f} x {f['l']:.1f}", ha="center", va="top", fontsize=7)
    ax.set_xlim(-2, W + 2)
    ax.set_ylim(-26, L + 3)
    ax.set_aspect("equal")
    ax.set_title(f"Test coupon, top view (mm). Profile hole shrink: expect holes about {hole_shrink_text(R)} smaller than drawn. "
                 "Print it first.", fontsize=8)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- CLI ------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Print rule audit, slicer run on copies of presets, test coupon.",
                                 epilog="Exit: 0 pass, 1 a rule failed, 2 could not run.")
    ap.add_argument("parts", nargs="*")
    ap.add_argument("--project")
    ap.add_argument("--out")
    ap.add_argument("--profile")
    ap.add_argument("--pose")
    ap.add_argument("--slice", action="store_true")
    ap.add_argument("--coupon", action="store_true")
    ap.add_argument("--screws")
    a = ap.parse_args(argv)
    cfg, out = None, os.path.abspath(a.out) if a.out else None
    try:
        try:
            job = mc.resolve(a) if (a.project or not a.out) else None
        except mc.MechError:
            job = None
        if job:
            cfg, out = job.cfg, out or job.out
        else:
            cfg = dict(mc.DEFAULTS, _project=os.getcwd())
        out = out or os.path.join(os.getcwd(), "out")
        ppath = a.profile or (mc.rel_to_project(cfg, cfg["printer"]["profile"]) if cfg.get("printer", {}).get("profile") else None)
        prof, note = load_profile(ppath)
        pdir = os.path.join(out, "print")
        rows = mc.Rows()
        if note:
            print("note:", note)
        inputs = [ppath] if ppath else []
        if a.coupon:
            mc.reexec_with_cadquery(cfg)
            feats = make_coupon(prof, os.path.join(pdir, "coupon"), a.screws.split(",") if a.screws else None)
            rows.add("PRT-CPN", "print", "test coupon written", f"{len(feats)} features in {os.path.join(pdir, 'coupon')}", "print the coupon before the big parts", "pass")
            print(f"coupon: {len(feats)} features -> {os.path.join(pdir, 'coupon')} (coupon.step, coupon.stl, coupon_legend.png, coupon.json)")
        parts = list(a.parts)
        if not parts and not a.coupon:
            pr = cfg.get("print", {}).get("parts")
            parts = [mc.rel_to_project(cfg, p) for p in pr] if pr else sorted(glob.glob(os.path.join(pdir, "*.stl")))
            if not parts:
                raise mc.MechError("no part given (a path to an STL/STEP, or [print] parts in mech.toml)")
        for lib in ("numpy", "shapely"):
            if parts:
                mc.require_module(lib, "print audit")
        for pth in parts:
            if not os.path.isfile(pth):
                raise mc.MechError(f"no such part file: {pth}")
            if os.path.splitext(pth)[1].lower() in (".step", ".stp", ".brep"):
                mc.reexec_with_cadquery(cfg)
            tag = "" if len(parts) == 1 else "-" + re.sub(r"\W", "", os.path.splitext(os.path.basename(pth))[0])[:12]
            print(f"auditing {pth}")
            tris = load_mesh(pth, a.pose)
            audit(tris, prof, rows, tag, cfg.get("print", {}).get("step_verdict", "fail"))
            inputs.append(pth)
            if a.slice:
                slice_part(cfg, prof, pth, os.path.join(pdir, "slice"), rows, tag, bool(cfg.get("print", {}).get("allow_support", False)))
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(out, "print_check.py", inputs)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
