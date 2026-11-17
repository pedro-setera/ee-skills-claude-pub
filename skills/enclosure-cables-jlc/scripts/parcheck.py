"""All-core interference, minimum-gap and sweep checks of the solids of a model.

What it does
    - `pairs(shapes, allow=..., min_gap=...)`: every pair of named shapes whose bounding boxes are near each other is
      tested for overlap volume and (when min_gap > 0) for the smallest distance. Intended contacts go in an allow list
      with a volume bound each: an allowed pair passes while its overlap stays at or under its bound. Anything else
      overlapping more than 0.01 mm3, or nearer than min_gap, fails.
    - `sweep(moving, static, direction, steps)`: moves one shape along a vector in `steps` equal steps and tests it
      against every static shape at each position: the "does it go in and come out" check of an assembly order.
    - CLI: all pairs of the solids that `model/build_model.py: build()` returns.
    The shapes are written ONCE as BREP into a temporary folder; each worker process loads the shapes it needs and
    answers one task at a time with plain numbers. The workers run the same function as the serial code, so a run
    with MECH_WORKERS=1 gives the same numbers (the self test proves it).

Why it exists (the real failure, told without names)
    A pair check of 400 solids took half an hour on one core and was skipped before the last export; a clash between a
    connector and a screw hole's tool space reached the first print. On all cores the same check takes minutes, so it
    runs on every build.

Usage
    python -I parcheck.py [--project <mech folder>] [--min-gap 0.0] [--allow allow.toml] [--limit N]
        --allow: TOML with [[allow]] a = "stand_*", b = "board", bound = 0.5  (names may use * ? wildcards; "bound"
                 in mm3, default 0.0 = touching only; a missing bound means any overlap up to 1 mm3)
        --sweep NAME --direction 0,0,-30 --steps 12   insertion check of one solid against all others
    Needs CadQuery (re-runs itself under CADQUERY_PYTHON / [tools] cadquery_python).

Config keys (mech.toml)
    [parcheck] min_gap = 0.0, allow = [{a, b, bound}], skip = ["name*"]     [paths] model

Exit codes
    0 all pass   1 an interference or a gap below the minimum   2 could not run (no CadQuery, no model)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import fnmatch
import os
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

VOL_EPS = 0.01          # mm3: below this an overlap is numerical noise
_DIR = None
_SHAPES: dict = {}


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _init(folder, paths):
    global _DIR
    _DIR = folder
    for p in paths:
        if p not in sys.path:
            sys.path.insert(0, p)


def _shape(name):
    import cadquery as cq
    if name not in _SHAPES:
        _SHAPES[name] = cq.Shape.importBrep(os.path.join(_DIR, _safe(name) + ".brep"))
    return _SHAPES[name]


def _bb_gap(a, b) -> float:
    """Distance between two bounding boxes (0 when they touch or overlap)."""
    dx = max(a.xmin - b.xmax, b.xmin - a.xmax, 0.0)
    dy = max(a.ymin - b.ymax, b.ymin - a.ymax, 0.0)
    dz = max(a.zmin - b.zmax, b.zmin - a.zmax, 0.0)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _solid_pairs(a, b, limit):
    """Pairs of single solids of two shapes whose bounding boxes are within `limit`."""
    sa, sb = list(a.Solids()) or [a], list(b.Solids()) or [b]
    out = []
    for x in sa:
        bx = x.BoundingBox()
        for y in sb:
            if _bb_gap(bx, y.BoundingBox()) <= limit:
                out.append((x, y))
    return out


def pair_task(t):
    """t = (name_a, name_b, limit, want_distance) -> (volume, distance or None, near)."""
    na, nb, limit, want_d = t
    a, b = _shape(na), _shape(nb)
    prs = _solid_pairs(a, b, limit)
    if not prs:
        return 0.0, None, False
    vol = 0.0
    for x, y in prs:
        if _bb_gap(x.BoundingBox(), y.BoundingBox()) <= 0:
            try:
                vol += x.intersect(y).Volume()
            except Exception:
                pass
    dist = None
    if want_d and vol <= VOL_EPS:
        dist = min(x.distance(y) for x, y in prs)
    return vol, dist, True


def sweep_task(t):
    """t = (moving_name, (dx, dy, dz), static_names) -> list of (name, volume) hits (volume > VOL_EPS)."""
    import cadquery as cq
    mname, off, statics = t
    m = _shape(mname).moved(cq.Location(cq.Vector(*off)))
    bm = m.BoundingBox()
    hits = []
    for s in statics:
        sh = _shape(s)
        if _bb_gap(bm, sh.BoundingBox()) > 0:
            continue
        vol = 0.0
        for x, y in _solid_pairs(m, sh, 0.0):
            try:
                vol += x.intersect(y).Volume()
            except Exception:
                pass
        if vol > VOL_EPS:
            hits.append((s, round(vol, 4)))
    return hits


class Pool:
    """with Pool(shapes) as p: p.map(fn, tasks, label) -> results in task order. n <= 1 runs serially in this process."""

    def __init__(self, shapes: dict, n: int | None = None):
        self.n = mc.workers() if n is None else n
        self.dir = tempfile.mkdtemp(prefix="mech_par_")
        t0 = time.time()
        for k, s in shapes.items():
            s.exportBrep(os.path.join(self.dir, _safe(k) + ".brep"))
        print(f"  parallel: {len(shapes)} shapes written in {time.time() - t0:.1f} s, {max(self.n, 1)} worker(s)", flush=True)
        self.ex = None
        if self.n > 1:
            self.ex = ProcessPoolExecutor(self.n, initializer=_init, initargs=(self.dir, [_HERE]))
        else:
            _init(self.dir, [_HERE])
            _SHAPES.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.ex:
            self.ex.shutdown(wait=True, cancel_futures=True)
        _SHAPES.clear()
        shutil.rmtree(self.dir, ignore_errors=True)

    def map(self, fn, tasks, label=""):
        t0 = time.time()
        out = [None] * len(tasks)
        if not self.ex:
            for i, t in enumerate(tasks):
                out[i] = fn(t)
            return out
        futs = {self.ex.submit(fn, t): i for i, t in enumerate(tasks)}
        step = max(1, len(tasks) // 10)
        for k, f in enumerate(as_completed(futs), 1):
            out[futs[f]] = f.result()
            if k % step == 0 or k == len(tasks):
                print(f"  parallel {label}: {k}/{len(tasks)} done, {time.time() - t0:.0f} s", flush=True)
        return out


# ---------------------------------------------------------------- API ------------------------------------------------
def _norm_allow(allow) -> list[tuple[str, str, float]]:
    out = []
    if not allow:
        return out
    if isinstance(allow, dict):
        for k, v in allow.items():
            a, b = (k.split("|", 1) if isinstance(k, str) else k)
            out.append((a, b, 1.0 if v is None else float(v)))
    else:
        for it in allow:
            if isinstance(it, dict):
                out.append((it["a"], it["b"], 1.0 if it.get("bound") is None else float(it["bound"])))
            else:
                a, b = it[0], it[1]
                out.append((a, b, float(it[2]) if len(it) > 2 and it[2] is not None else 1.0))
    return out


def _allowed(allow, a, b):
    """The bound of the first allow entry matching the pair (either order), or None."""
    for pa, pb, bound in allow:
        if (fnmatch.fnmatchcase(a, pa) and fnmatch.fnmatchcase(b, pb)) or (fnmatch.fnmatchcase(a, pb) and fnmatch.fnmatchcase(b, pa)):
            return bound
    return None


def pairs(shapes: dict, allow=None, min_gap: float = 0.0, skip=(), n_workers: int | None = None, same_group=None) -> list[dict]:
    """Test every pair of `shapes` (name -> cq shape). Returns one dict per pair that is near enough to matter:
    {a, b, volume, distance, allowed (bound or None), verdict ('pass'|'fail'), why}.  `same_group(a, b) -> True` skips
    pairs that belong together (e.g. both parts of one sub-assembly)."""
    names = [n for n in shapes if not any(fnmatch.fnmatchcase(n, s) for s in skip)]
    allow_n = _norm_allow(allow)
    bbs = {n: shapes[n].BoundingBox() for n in names}
    limit = max(min_gap, 0.0)
    tasks, keys = [], []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            if same_group and same_group(a, b):
                continue
            if _bb_gap(bbs[a], bbs[b]) <= limit:
                tasks.append((a, b, limit, limit > 0))
                keys.append((a, b))
    res = []
    if not tasks:
        return res
    with Pool({n: shapes[n] for n in {k for p in keys for k in p}}, n_workers) as pool:
        out = pool.map(pair_task, tasks, "pairs")
    for (a, b), (vol, dist, near) in zip(keys, out):
        if not near:
            continue
        bound = _allowed(allow_n, a, b)
        why, verdict = "", "pass"
        if bound is not None:
            if vol > bound + 1e-9:
                verdict, why = "fail", f"overlap {vol:.3f} mm3 is above the allowed {bound:g} mm3"
        elif vol > VOL_EPS:
            verdict, why = "fail", f"overlap {vol:.3f} mm3, not on the allow list"
        elif limit > 0 and dist is not None and dist < min_gap - 1e-9:
            verdict, why = "fail", f"gap {dist:.3f} mm is below the minimum {min_gap:g} mm"
        if vol > VOL_EPS or verdict == "fail" or bound is not None:
            res.append({"a": a, "b": b, "volume": round(vol, 4), "distance": None if dist is None else round(dist, 4),
                        "allowed": bound, "verdict": verdict, "why": why})
    return res


def sweep(moving, static: dict, direction, steps: int, n_workers: int | None = None, moving_name: str = "moving") -> list[dict]:
    """Move `moving` along the vector `direction` (its length is the whole travel) in `steps` steps (positions
    0..steps, so steps + 1 tests). Returns [{step, offset, hits: [(name, mm3)]}]. Position 0 is the final/seated one."""
    d = [float(v) for v in direction]
    tasks = []
    for k in range(steps + 1):
        f = k / steps if steps else 0.0
        tasks.append((moving_name, (d[0] * f, d[1] * f, d[2] * f), list(static.keys())))
    shapes = dict(static)
    shapes[moving_name] = moving
    with Pool(shapes, n_workers) as pool:
        out = pool.map(sweep_task, tasks, "sweep")
    return [{"step": k, "offset": [round(v, 4) for v in t[1]], "hits": h} for k, (t, h) in enumerate(zip(tasks, out))]


# ---------------------------------------------------------------- CLI ------------------------------------------------
def load_model_shapes(job):
    import cadquery as cq
    import box_toolkit as bt
    path = mc.path_of(job.cfg, "model")
    if not os.path.isfile(path):
        raise mc.MechError(f"no model at {path}")
    solids, meta = bt.load_model(path)
    shapes = {}
    for k, v in solids.items():
        s = v.val() if hasattr(v, "val") else v
        if isinstance(s, cq.Shape):
            shapes[k] = s
    return shapes, meta, path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="All-core pair interference / gap / sweep checks on a model's solids.",
                                 epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--min-gap", type=float, default=None)
    ap.add_argument("--allow", help="TOML file with [[allow]] a, b, bound")
    ap.add_argument("--sweep", help="name of the solid to sweep against all others")
    ap.add_argument("--direction", default="0,0,-30")
    ap.add_argument("--steps", type=int, default=10)
    a = ap.parse_args(argv)
    mc.reexec_with_cadquery()
    try:
        job = mc.resolve(a)
        shapes, meta, mpath = load_model_shapes(job)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    cfg = job.cfg.get("parcheck", {})
    allow = list(cfg.get("allow", []))
    if a.allow:
        allow += mc.load_toml(a.allow).get("allow", [])
    gap = a.min_gap if a.min_gap is not None else float(cfg.get("min_gap", 0.0))
    rows = mc.Rows()
    if a.sweep:
        if a.sweep not in shapes:
            print("could not run: no solid named", a.sweep)
            return 2
        d = [float(x) for x in a.direction.split(",")]
        static = {k: v for k, v in shapes.items() if k != a.sweep}
        res = sweep(shapes[a.sweep], static, d, a.steps, moving_name=a.sweep)
        for r in res:
            hit = ", ".join(f"{n} {v} mm3" for n, v in r["hits"])
            rows.add(f"SWP-{r['step']:02d}", "assembly", f"{a.sweep} at offset {r['offset']}", hit or "free", "no overlap",
                     "fail" if r["hits"] else "pass")
    else:
        res = pairs(shapes, allow, gap, skip=cfg.get("skip", ()))
        n = 0
        for r in res:
            n += 1
            rows.add(f"PAR-{n:03d}", "interference", f"{r['a']} / {r['b']}",
                     f"overlap {r['volume']} mm3, gap {r['distance']}", r["why"] or f"allowed up to {r['allowed']} mm3", r["verdict"])
        if not res:
            rows.add("PAR-000", "interference", f"{len(shapes)} solids, all pairs", "no pair overlaps or is too near",
                     f"no overlap, gap >= {gap:g}", "pass")
    rows.print_table(only_bad=True)
    rows.write(job.out, "parcheck.py", [mpath])
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
