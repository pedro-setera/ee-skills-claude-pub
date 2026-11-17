"""Table-driven placing of the makers' STEP files into the assembly, and a loader for a folder of fastener models.

What it does
    Reads `vendor3d/vendor_parts.toml`: one `[[part]]` per bought part with its STEP file, how it is placed (position and
    rotation, or a hole-match: two of the part's own hole positions and the two box positions they go to), colour, source
    URL and licence. Imports each STEP once (in parallel, one process per new file) into a BREP cache keyed by the
    file's sha256, places the parts and returns them as named shapes: `place_all(job) -> (shapes, colours)`.
    Rows: every bought part of the parts list has a real model, or is listed as "block model" with its reason; every
    model file has a recorded source URL and licence. Also `Fasteners(folder)`: screws, nuts, washers, standoffs from a
    folder of STEP files, two per fastener (`<id>.step` full and `<id>_simple.step` envelope).

Why it exists (the real failure, told without names)
    Block models, invented screws and a part stacked the wrong way (the maker's assembly page was not read) made every
    render and several manual pages wrong, twice. A table that says which real model sits where, with its source, and a
    check that no bought part is silently a box, ends that.

Usage
    python -I vendor_parts.py [--project <mech folder>] [--export out.step] [--list]
    vendor_parts.toml:
        bought = ["fan", "jack", "plug"]            # the bought parts of the parts list (or [vendor] bought in mech.toml)
        [[part]]
        id = "fan"                                  # name of the placed part
        file = "fan/fan.step"                       # under vendor3d/
        position = [60, 40, 20]                     # where the part's origin goes (box frame)
        rotation = [0, 0, 90]                       # degrees about x, y, z, applied first
        colour = "#3a3a3a"
        source_url = "https://maker.example/fan"    # direct link, never a browser download click
        licence = "maker's terms: free for design use, do not redistribute"
        replaces = "fan_block"                      # optional: the model solid this one replaces
        [part.match_holes]                          # optional placement on two holes instead of position x, y
        from = [[0, 0], [30, 0]]                    # two hole centres in the part's file frame (after rotation)
        to   = [[60, 40], [90, 40]]                 # the same two holes in the box frame
        z = 5.0
        [[part]]
        id = "jack"
        block_model_reason = "no maker model published; block from the datasheet drawing"
    Fastener frame: the axis is z; a screw's bearing face is at z = 0 and the shank runs to -z; a nut or washer sits
    on z = 0 and rises to +z. Library: generate it elsewhere (see the notes: bd_warehouse in its own venv); the skill
    does not ship it, and without it the fastener rows say "could not run".

Config keys (mech.toml)
    [paths] vendor = "vendor3d/vendor_parts.toml"     [vendor] bought = [...], cache = "<out>/cache/vendor", fasteners = "vendor3d/fasteners"

Exit codes
    0 all pass   1 a row failed   2 could not run (no CadQuery, no table)
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

PARTS_FIELDS = ("source_url", "licence")


def _import_task(args):
    """Worker: import a STEP once and save it as BREP. -> (cache path, error text or '')."""
    src, dst = args
    try:
        import cadquery as cq
        w = cq.importers.importStep(src)
        vals = w.vals()
        shp = cq.Compound.makeCompound(vals) if len(vals) != 1 else vals[0]
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shp.exportBrep(dst)
        return dst, ""
    except Exception as e:
        return dst, f"{type(e).__name__}: {e}"


def cached_brep_paths(files, cache_dir, n_workers=None):
    """files: {key: step path}. Returns {key: brep path} importing the files missing from the cache in parallel."""
    todo, out = [], {}
    for k, p in files.items():
        dst = os.path.join(cache_dir, mc.sha256(p) + ".brep")
        out[k] = dst
        if not os.path.isfile(dst):
            todo.append((p, dst))
    todo = list({t[1]: t for t in todo}.values())
    if todo:
        n = min(n_workers or mc.workers(), len(todo))
        print(f"  importing {len(todo)} STEP file(s) into the cache on {n} process(es)", flush=True)
        if n > 1:
            with ProcessPoolExecutor(n) as ex:
                res = list(ex.map(_import_task, todo))
        else:
            res = [_import_task(t) for t in todo]
        for dst, err in res:
            if err:
                raise mc.MechError(f"STEP import failed for {dst}: {err}")
    return out


def _matrix_2pt(src, dst):
    """Rotation (deg) about z and translation (tx, ty) that carry the two source points onto the two destination points."""
    (ax, ay), (bx, by) = src
    (cx, cy), (dx, dy) = dst
    a0 = math.atan2(by - ay, bx - ax)
    a1 = math.atan2(dy - cy, dx - cx)
    la, lb = math.hypot(bx - ax, by - ay), math.hypot(dx - cx, dy - cy)
    if abs(la - lb) > 0.05:
        raise mc.MechError(f"the two holes are {la:.3f} mm apart in the part and {lb:.3f} mm apart in the box: they are not the same holes")
    r = a1 - a0
    c, s = math.cos(r), math.sin(r)
    return math.degrees(r), (cx - (c * ax - s * ay), cy - (s * ax + c * ay))


def place(shape, spec: dict):
    """Place one imported shape as the table row `spec` says."""
    import cadquery as cq
    V = cq.Vector
    rot = spec.get("rotation", [0, 0, 0])
    s = shape
    for axis, ang in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), rot):
        if ang:
            s = s.rotate(V(0, 0, 0), V(*axis), ang)
    mh = spec.get("match_holes")
    if mh:
        rz, (tx, ty) = _matrix_2pt(mh["from"], mh["to"])
        s = s.rotate(V(0, 0, 0), V(0, 0, 1), rz).translate(V(tx, ty, mh.get("z", 0.0)))
    else:
        p = spec.get("position", [0, 0, 0])
        s = s.translate(V(*p))
    return s


def load_table(job):
    path = mc.path_of(job.cfg, "vendor")
    if not os.path.isfile(path):
        raise mc.MechError(f"no vendor parts table at {path}")
    data = mc.load_toml(path)
    bought = list(data.get("bought", [])) or list(job.cfg.get("vendor", {}).get("bought", []))
    return path, bought, data.get("part", [])


def place_all(job, n_workers=None):
    """-> (shapes {id: placed shape}, colours {id: '#rrggbb'}, table rows). Parts without a file are skipped."""
    import cadquery as cq
    path, _bought, parts = load_table(job)
    base = os.path.dirname(path)
    cache = job.cfg.get("vendor", {}).get("cache") or os.path.join(job.out, "cache", "vendor")
    files = {p["id"]: os.path.join(base, p["file"]) for p in parts if p.get("file") and os.path.isfile(os.path.join(base, p["file"]))}
    breps = cached_brep_paths(files, cache, n_workers)
    shapes, colours = {}, {}
    for p in parts:
        if p["id"] in breps:
            shapes[p["id"]] = place(cq.Shape.importBrep(breps[p["id"]]), p)
            colours[p["id"]] = p.get("colour", "#888888")
    return shapes, colours


def check_rows(job, rows: mc.Rows):
    path, bought, parts = load_table(job)
    base = os.path.dirname(path)
    byid = {p["id"]: p for p in parts}
    if not bought:
        rows.add("VEN-000", "vendor models", "the parts list", "the table names no bought parts (bought = [...])", "every bought part is listed", "fail")
    for n, name in enumerate(bought, 1):
        p = byid.get(name)
        cid = f"VEN-{n:03d}"
        if p is None:
            rows.add(cid, "vendor models", f"{name}: model", "not in the table", "a real model, or 'block model' with its reason", "fail")
        elif p.get("file") and os.path.isfile(os.path.join(base, p["file"])):
            rows.add(cid, "vendor models", f"{name}: model", f"real model {p['file']}", "a real model, or 'block model' with its reason", "pass")
        elif str(p.get("block_model_reason", "")).strip():
            rows.add(cid, "vendor models", f"{name}: model", f"block model, {p['block_model_reason']}", "a real model, or 'block model' with its reason", "pass")
        elif p.get("file"):
            rows.add(cid, "vendor models", f"{name}: model", f"file {p['file']} is not there and no block-model reason is given", "a real model, or 'block model' with its reason", "fail")
        else:
            rows.add(cid, "vendor models", f"{name}: model", "no file and no block-model reason", "a real model, or 'block model' with its reason", "fail")
    for n, p in enumerate(parts, 1):
        if p.get("file"):
            miss = [k for k in PARTS_FIELDS if not str(p.get(k, "")).strip()]
            rows.add(f"VEN-SRC-{n:03d}", "vendor models", f"{p['id']}: source and licence", "recorded" if not miss else "missing: " + ", ".join(miss),
                     "source_url and licence for every model file", "pass" if not miss else "fail")
            if "match_holes" in p:
                try:
                    _matrix_2pt(p["match_holes"]["from"], p["match_holes"]["to"])
                    rows.add(f"VEN-HOL-{n:03d}", "vendor models", f"{p['id']}: hole match", "the two holes are the same distance apart", "equal within 0.05 mm", "pass")
                except mc.MechError as e:
                    rows.add(f"VEN-HOL-{n:03d}", "vendor models", f"{p['id']}: hole match", str(e), "equal within 0.05 mm", "fail")
    return rows


class Fasteners:
    """A folder of fastener STEP files: <id>.step (full, with thread) and <id>_simple.step (envelope, for clash checks).
    The skill ships no library. Without one, `available` is False and load() raises mc.MechError."""

    def __init__(self, folder):
        self.folder = folder
        self.available = bool(folder) and os.path.isdir(folder)

    def ids(self):
        if not self.available:
            return []
        return sorted(f[:-5] for f in os.listdir(self.folder) if f.endswith(".step") and not f.endswith("_simple.step"))

    def path(self, fid, simple=True):
        return os.path.join(self.folder, fid + ("_simple" if simple else "") + ".step")

    def load(self, fid, simple=True):
        import cadquery as cq
        if not self.available:
            raise mc.MechError("no fastener library folder (generate one with bd_warehouse in its own Python; see the notes)")
        p = self.path(fid, simple)
        if not os.path.isfile(p):
            raise mc.MechError(f"fastener model {fid!r} ({'simple' if simple else 'full'}) is not in {self.folder}")
        w = cq.importers.importStep(p)
        vals = w.vals()
        return cq.Compound.makeCompound(vals) if len(vals) != 1 else vals[0]

    def placed(self, fid, point, axis=(0, 0, 1), simple=True):
        """The fastener with its bearing face on `point` and its axis along `axis`."""
        import cadquery as cq
        V = cq.Vector
        s = self.load(fid, simple)
        a = V(*axis).normalized()
        z = V(0, 0, 1)
        d = z.dot(a)
        if abs(d - 1) > 1e-9:
            rot_axis = z.cross(a) if abs(d + 1) > 1e-9 else V(1, 0, 0)
            s = s.rotate(V(0, 0, 0), rot_axis, math.degrees(math.acos(max(-1.0, min(1.0, d)))))
        return s.translate(V(*point))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Place the makers' STEP files; check every bought part has a real model.", epilog="Exit: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--export")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
        rows = mc.Rows()
        check_rows(job, rows)
        fa = Fasteners(mc.rel_to_project(job.cfg, job.cfg.get("vendor", {}).get("fasteners", "vendor3d/fasteners")))
        rows.add("VEN-FAS", "vendor models", "fastener library", f"{len(fa.ids())} fastener model(s)" if fa.available else "no library folder",
                 "a folder of real fastener STEP files", "pass" if fa.ids() else "could_not_run")
        if a.export or not rows.counts()["fail"]:
            mc.reexec_with_cadquery(job.cfg)
            shapes, _col = place_all(job)
            rows.add("VEN-PLC", "vendor models", "parts placed", f"{len(shapes)} placed", "every file imports and is placed", "pass" if shapes or not any(p.get("file") for p in load_table(job)[2]) else "fail")
            if a.export and shapes:
                import box_toolkit as bt
                bt.export_step(shapes, a.export, job.cfg["project"].get("company", ""))
                print("exported", a.export)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    if a.list:
        for p in load_table(job)[2]:
            print(p["id"], "->", p.get("file", "(block model)"))
    rows.print_table(only_bad=True)
    rows.write(job.out, "vendor_parts.py", [load_table(job)[0]])
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
