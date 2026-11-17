"""Pre-CAD block layout: 1 to 3 arrangements of block models in the box, pictures, check rows and one comparison table.

What it does
    Reads a layout TOML (parts as blocks with size, heat, tags and connectors; box inner size; per variant: where each block sits,
    fans, vents, cable stubs) and for every variant writes
      <variant>_top.png    top view (x right, y back): box, blocks labelled with name and watts, fans, vents, air-path arrow, cables
      <variant>_side.png   elevation seen from the front (x right, z up), same content
    and, across the variants, `comparison.md` and `comparison.png` with: outer volume, footprint, total cable length, vent ratio
    (intake open area / fan swept area), number of clashes, total heat. All into `<out>/layout/` (old files there are removed first).
    Check rows (written to `<out>/checks/layout_study.json`), per variant:
      block clashes            no two blocks (fan bodies included) overlap, and gaps are at least `block_gap_mm`
      inside the box           every block lies inside the inner volume
      panel parts reach wall   every connector marked panel = true has its block face at most `reach_gap_mm` from the inner wall
                               (reach = wall + washer + nut + thread left for the plug: set the gap from that sum)
      fan clear zone           nothing within `fan_clear_mm` in front of a fan (inside the box)
      noisy to sensitive       the smallest gap between a block tagged "noisy" and one tagged "sensitive" is at least `noisy_sensitive_mm`
      intake ratio             passive open area / swept area of the fans blowing one way, at least the first value of `intake_ratio`
                               (default 1.1; the aim is 1.1 to 1.5, and above the second value the row only notes "more open area
                               than needed", it does not fail)
      cables                   every bend fits its radius (each straight piece at least the radii at its two ends), the route stays
                               inside the box and does not cross a block other than its own two end blocks
    Cable routes are right-angle routes with rounded corners: the script tries the six axis orders and keeps the shortest route
    that crosses no block. Length = straight pieces + quarter circles (a corner of radius r saves (2 - pi/2) r). It is an estimate to
    compare arrangements, not the final route (that is measured in the model).

Why it exists (the real failure, told without names)
    A layout was approved from a sketch; in CAD the fan stood two millimetres from a board, the intake was a third of the fan's area
    and the longest cable was 40 mm longer than the cable list said, so boards and cables were redrawn after parts were ordered.
    Block models and these rows catch the same faults while moving a block costs one line of text.

Usage
    python -I scripts/layout_study.py LAYOUT.toml [--project DIR] [--out DIR] [--variants A,B] [--no-pictures]
    Importable: load_study(path), build_variant(study, name), check_variant(v), fan_zone(v, fan), aabb_gap(a, b).

Config (the layout TOML itself; units mm, frame origin at the INNER front-left-bottom corner, x right, y back, z up)
    [study]  name, wall = 2.0, fan_clear_mm = 15, noisy_sensitive_mm = 30, block_gap_mm = 1.0, reach_gap_mm = 1.5,
             intake_ratio = [1.1, 1.5], stub_mm = 5, default_bend_r = 6, tolerance = 0.01
    [parts.<name>]  size = [x, y, z], heat_w = 0, tags = ["noisy" | "sensitive" | any word],
                    connectors = [ {name, face = front|back|left|right|top|bottom, panel = false, at = [x, y, z] (mm from the block's
                                    min corner, before rotation; default the middle of the face)} ]
    [variant.<id>]  title, inner = [x, y, z]
    [variant.<id>.place.<part>]  pos = [x, y, z] (min corner), rot = 0|90|180|270 (about z, counter-clockwise seen from above)
    [[variant.<id>.fan]]  name, face, centre = [u, v], size = 40, blade_d, hub_d, depth, direction = "in" | "out"
                          (u, v on the wall: front/back x,z; left/right y,z; top/bottom x,y)
    [[variant.<id>.vent]] name, face, rect = [u0, v0, u1, v1], open_area_mm2 or open_fraction = 0.5, kind = "intake" | "exhaust"
    [[variant.<id>.cable]] name, from = "part.connector", to = "part.connector", bend_r = 6, colour = "#rrggbb"

Exit codes: 0 all rows pass; 1 a row failed; 2 input missing or matplotlib missing.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import itertools
import math
import shutil

import mech_common as mc

FACES = {"front": (0, -1, 0), "back": (0, 1, 0), "left": (-1, 0, 0), "right": (1, 0, 0), "bottom": (0, 0, -1), "top": (0, 0, 1)}
ROT_FACE = {0: {}, 90: {"front": "right", "right": "back", "back": "left", "left": "front"},
            180: {"front": "back", "back": "front", "left": "right", "right": "left"},
            270: {"front": "left", "left": "back", "back": "right", "right": "front"}}
STUDY_DEFAULTS = {"name": "", "wall": 2.0, "fan_clear_mm": 15.0, "noisy_sensitive_mm": 30.0, "block_gap_mm": 1.0, "reach_gap_mm": 1.5,
                  "intake_ratio": [1.1, 1.5], "stub_mm": 5.0, "default_bend_r": 6.0, "tolerance": 0.01}
CABLE_COLOURS = ["#c0392b", "#8e44ad", "#16a085", "#d35400", "#2c3e50", "#7f8c8d"]


class Variant:
    def __init__(self, vid, title, inner, wall):
        self.id, self.title, self.inner, self.wall = vid, title, tuple(inner), wall
        self.blocks: dict[str, dict] = {}
        self.fans: list[dict] = []
        self.vents: list[dict] = []
        self.cables: list[dict] = []
        self.study: dict = {}


# ---------------------------------------------------------------- geometry -------------------------------------------
def aabb_gap(a, b) -> float:
    """Smallest distance between two boxes (lo, hi); negative of the smallest overlap depth when they overlap."""
    d = [max(a[0][i] - b[1][i], b[0][i] - a[1][i]) for i in range(3)]
    if max(d) > 0:
        return math.sqrt(sum(max(x, 0.0) ** 2 for x in d))
    return max(d)          # all <= 0: overlap, the shallowest axis


def _rot_point(p, centre, rot):
    x, y = p[0] - centre[0], p[1] - centre[1]
    for _ in range((rot // 90) % 4):
        x, y = -y, x
    return (centre[0] + x, centre[1] + y, p[2])


def face_point(lo, hi, face):
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]
    n = FACES[face]
    for i in range(3):
        if n[i]:
            c[i] = hi[i] if n[i] > 0 else lo[i]
    return tuple(c)


def wall_to_xyz(face, u, v, inner):
    """A wall point (u, v) -> inner-frame xyz on the inner wall plane."""
    W, D, H = inner
    return {"front": (u, 0.0, v), "back": (u, D, v), "left": (0.0, u, v), "right": (W, u, v), "bottom": (u, v, 0.0), "top": (u, v, H)}[face]


def face_axes(face):
    """(axis of the wall normal, index of u axis, index of v axis)."""
    return {"front": (1, 0, 2), "back": (1, 0, 2), "left": (0, 1, 2), "right": (0, 1, 2), "bottom": (2, 0, 1), "top": (2, 0, 1)}[face]


def fan_body(fan, inner):
    """AABB (lo, hi) of a fan: size x size x depth, flush against the inner wall."""
    ax, iu, iv = face_axes(fan["face"])
    s, dep = fan["size"], fan["depth"]
    centre = wall_to_xyz(fan["face"], fan["centre"][0], fan["centre"][1], inner)
    lo, hi = list(centre), list(centre)
    for i in (iu, iv):
        lo[i], hi[i] = centre[i] - s / 2, centre[i] + s / 2
    n = FACES[fan["face"]][ax]
    if n > 0:                  # wall at the high end: body extends towards -axis
        lo[ax], hi[ax] = centre[ax] - dep, centre[ax]
    else:
        lo[ax], hi[ax] = centre[ax], centre[ax] + dep
    return tuple(lo), tuple(hi)


def fan_zone(v: Variant, fan: dict, clear: float | None = None):
    """The free zone in front of a fan: the fan's width, `clear` mm deep, on the inside of the fan body."""
    clear = v.study["fan_clear_mm"] if clear is None else clear
    lo, hi = fan_body(fan, v.inner)
    ax, iu, iv = face_axes(fan["face"])
    n = FACES[fan["face"]][ax]
    lo2, hi2 = list(lo), list(hi)
    if n > 0:
        lo2[ax], hi2[ax] = lo[ax] - clear, lo[ax]
    else:
        lo2[ax], hi2[ax] = hi[ax], hi[ax] + clear
    return tuple(lo2), tuple(hi2)


def swept_area(fan):
    return math.pi / 4 * (fan["blade_d"] ** 2 - fan["hub_d"] ** 2)


def vent_area(vent) -> float:
    if vent.get("open_area_mm2") is not None:
        return float(vent["open_area_mm2"])
    u0, v0, u1, v1 = vent["rect"]
    return abs(u1 - u0) * abs(v1 - v0) * float(vent.get("open_fraction", 0.5))


def vent_box(vent, inner, depth=1.0):
    ax, iu, iv = face_axes(vent["face"])
    u0, v0, u1, v1 = vent["rect"]
    a = wall_to_xyz(vent["face"], min(u0, u1), min(v0, v1), inner)
    b = wall_to_xyz(vent["face"], max(u0, u1), max(v0, v1), inner)
    lo, hi = [min(a[i], b[i]) for i in range(3)], [max(a[i], b[i]) for i in range(3)]
    n = FACES[vent["face"]][ax]
    if n > 0:
        lo[ax], hi[ax] = hi[ax] - depth, hi[ax]
    else:
        lo[ax], hi[ax] = lo[ax], lo[ax] + depth
    return tuple(lo), tuple(hi)


# ---------------------------------------------------------------- loading --------------------------------------------
def load_study(path: str) -> dict:
    t = mc.load_toml(path)
    st = dict(STUDY_DEFAULTS)
    st.update(t.get("study", {}))
    t["study"] = st
    if not t.get("variant"):
        raise mc.MechError(f"{path}: no [variant.<id>] table")
    if len(t["variant"]) > 3:
        raise mc.MechError(f"{path}: {len(t['variant'])} variants; the study compares 1 to 3")
    if not t.get("parts"):
        raise mc.MechError(f"{path}: no [parts.<name>] table")
    return t


def build_variant(study: dict, vid: str) -> Variant:
    st = study["study"]
    vt = study["variant"][vid]
    inner = vt.get("inner") or study.get("box", {}).get("inner")
    if not inner:
        raise mc.MechError(f"variant {vid}: no inner size")
    v = Variant(vid, vt.get("title", vid), inner, float(st["wall"]))
    v.study = st
    for pname, pl in (vt.get("place") or {}).items():
        part = study["parts"].get(pname)
        if part is None:
            raise mc.MechError(f"variant {vid}: place.{pname}: no such part in [parts]")
        sx, sy, sz = part["size"]
        rot = int(pl.get("rot", 0)) % 360
        if rot not in (0, 90, 180, 270):
            raise mc.MechError(f"variant {vid}: place.{pname}.rot must be 0, 90, 180 or 270")
        if rot in (90, 270):
            sx, sy = sy, sx
        lo = tuple(float(x) for x in pl["pos"])
        hi = (lo[0] + sx, lo[1] + sy, lo[2] + sz)
        conns = {}
        for c in part.get("connectors", []) or []:
            if c["face"] not in FACES:
                raise mc.MechError(f"part {pname}: connector {c.get('name')}: face must be one of {list(FACES)}")
            # local point in the unrotated block
            ox, oy, oz = part["size"]
            lp = list(face_point((0, 0, 0), (ox, oy, oz), c["face"]))
            if c.get("at"):
                lp = [float(a) for a in c["at"]]
            centre_local = (ox / 2, oy / 2)
            rp = _rot_point(lp, centre_local, rot)
            # after rotation the block's min corner is at (0, 0) again once the swapped size is applied
            if rot in (90, 270):
                rp = (rp[0] + (sx - ox) / 2, rp[1] + (sy - oy) / 2, rp[2])
            face = ROT_FACE[rot].get(c["face"], c["face"])
            conns[c["name"]] = {"face": face, "panel": bool(c.get("panel", False)),
                                "pt": (lo[0] + rp[0], lo[1] + rp[1], lo[2] + rp[2]), "normal": FACES[face]}
        v.blocks[pname] = {"lo": lo, "hi": hi, "heat": float(part.get("heat_w", 0.0) or 0.0),
                           "tags": set(part.get("tags", []) or []), "conns": conns}
    for f in vt.get("fan", []) or []:
        fan = dict(f)
        fan.setdefault("size", 40.0)
        fan["blade_d"] = float(fan.get("blade_d") or fan["size"] - 4.0)
        fan["hub_d"] = float(fan.get("hub_d") or 0.4 * fan["blade_d"])
        fan["depth"] = float(fan.get("depth") or max(6.0, fan["size"] * 0.25))
        fan.setdefault("direction", "out")
        if fan["face"] not in FACES:
            raise mc.MechError(f"variant {vid}: fan {fan.get('name')}: bad face")
        v.fans.append(fan)
    for x in vt.get("vent", []) or []:
        vent = dict(x)
        vent.setdefault("kind", "intake")
        v.vents.append(vent)
    for i, c in enumerate(vt.get("cable", []) or []):
        cab = dict(c)
        cab.setdefault("bend_r", st["default_bend_r"])
        cab.setdefault("colour", CABLE_COLOURS[i % len(CABLE_COLOURS)])
        v.cables.append(cab)
    for cab in v.cables:
        cab["route"] = route_cable(v, cab)
    return v


# ---------------------------------------------------------------- cables ---------------------------------------------
def _endpoint(v: Variant, ref: str):
    if "." not in ref:
        raise mc.MechError(f"cable end '{ref}' must be part.connector")
    pn, cn = ref.split(".", 1)
    b = v.blocks.get(pn)
    if b is None or cn not in b["conns"]:
        raise mc.MechError(f"cable end '{ref}': no such part or connector")
    return pn, b["conns"][cn]


def _seg_hits_box(p, q, box, pad=0.0):
    """Does the segment p-q pass through the interior of the box (expanded by pad)?"""
    lo, hi = [box[0][i] - pad for i in range(3)], [box[1][i] + pad for i in range(3)]
    t0, t1 = 0.0, 1.0
    for i in range(3):
        d = q[i] - p[i]
        if abs(d) < 1e-12:
            if p[i] <= lo[i] + 1e-9 or p[i] >= hi[i] - 1e-9:
                return False
        else:
            a, b = (lo[i] - p[i]) / d, (hi[i] - p[i]) / d
            if a > b:
                a, b = b, a
            t0, t1 = max(t0, a), min(t1, b)
            if t0 >= t1 - 1e-9:
                return False
    return True


def _dedupe(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) > 1e-6:
            out.append(p)
    # drop collinear middle points
    res = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = res[-1], out[i], out[i + 1]
        u = tuple(b[k] - a[k] for k in range(3))
        w = tuple(c[k] - b[k] for k in range(3))
        cr = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        if max(abs(x) for x in cr) > 1e-6:
            res.append(b)
    res.append(out[-1])
    return res


def route_cable(v: Variant, cab: dict) -> dict:
    """{points, length, min_leg_problem, crosses, outside}: shortest right-angle route of the six axis orders that crosses no block."""
    pa, ca = _endpoint(v, cab["from"])
    pb, cb = _endpoint(v, cab["to"])
    stub = float(v.study["stub_mm"])
    r = float(cab["bend_r"])
    s = max(stub, r)
    a0, b0 = ca["pt"], cb["pt"]
    a1 = tuple(a0[i] + ca["normal"][i] * s for i in range(3))
    b1 = tuple(b0[i] + cb["normal"][i] * s for i in range(3))
    best = None
    inner_box = ((0, 0, 0), v.inner)
    for order in itertools.permutations(range(3)):
        pts = [a0, a1]
        cur = list(a1)
        for ax in order:
            cur[ax] = b1[ax]
            pts.append(tuple(cur))
        pts.append(b0)
        pts = _dedupe(pts)
        crosses = []
        for i in range(len(pts) - 1):
            for bn, bl in v.blocks.items():
                if bn in (pa, pb):
                    continue
                if _seg_hits_box(pts[i], pts[i + 1], (bl["lo"], bl["hi"])) and bn not in crosses:
                    crosses.append(bn)
        outside = any(not (-1e-6 <= p[i] <= v.inner[i] + 1e-6) for p in pts for i in range(3))
        # legs and radii
        segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        ncorner = len(pts) - 2
        length = sum(segs) - ncorner * (2.0 - math.pi / 2.0) * r
        short = []
        for i in range(ncorner):                      # corner i joins segs[i] and segs[i+1]; each needs r of both, shared pieces need 2r
            need_prev = r if i == 0 else 2 * r
            need_next = r if i == ncorner - 1 else 2 * r
            if segs[i] < r - 1e-6 or (i > 0 and segs[i] < 2 * r - 1e-6):
                short.append(i)
            if i == ncorner - 1 and segs[i + 1] < r - 1e-6:
                short.append(i + 1)
        key = (len(crosses) + (1 if outside else 0), len(short), length)
        if best is None or key < best[0]:
            best = (key, {"points": pts, "length": length, "short": sorted(set(short)), "crosses": crosses, "outside": outside, "order": order})
    return best[1]


# ---------------------------------------------------------------- checks ---------------------------------------------
def pseudo_blocks(v: Variant):
    """Blocks plus the fan bodies as boxes: name -> (lo, hi)."""
    d = {n: (b["lo"], b["hi"]) for n, b in v.blocks.items()}
    for f in v.fans:
        d["fan:" + f["name"]] = fan_body(f, v.inner)
    return d


def clashes(v: Variant):
    tol = float(v.study["tolerance"])
    gap_min = float(v.study["block_gap_mm"])
    boxes = pseudo_blocks(v)
    overl, close = [], []
    for (an, a), (bn, b) in itertools.combinations(boxes.items(), 2):
        g = aabb_gap(a, b)
        if g < -tol:
            overl.append((an, bn, -g))
        elif g < gap_min - tol:
            if an.startswith("fan:") or bn.startswith("fan:"):
                if g <= tol:       # a fan touching its own neighbour is a clash only if it overlaps; skip touching
                    continue
            close.append((an, bn, g))
    return overl, close


def check_variant(v: Variant, rows: mc.Rows) -> dict:
    """Add this variant's check rows; returns the metrics used by the comparison."""
    st = v.study
    pid = f"LAY-{v.id}"
    overl, close = clashes(v)
    bad = [f"{a}~{b} {d:.1f} mm overlap" for a, b, d in overl] + [f"{a}~{b} gap {d:.1f} mm" for a, b, d in close]
    rows.add(f"{pid}-CLASH", "layout", f"[{v.id}] block clashes and gaps", "; ".join(bad) if bad else f"none (min gap rule {st['block_gap_mm']} mm)",
             f"no overlap, gaps >= {st['block_gap_mm']} mm", "fail" if bad else "pass")
    out = []
    for n, b in v.blocks.items():
        for i in range(3):
            if b["lo"][i] < -1e-6 or b["hi"][i] > v.inner[i] + 1e-6:
                out.append(f"{n} {'xyz'[i]} {b['lo'][i]:.1f}..{b['hi'][i]:.1f} outside 0..{v.inner[i]:.1f}")
                break
    for f in v.fans:
        lo, hi = fan_body(f, v.inner)
        if any(lo[i] < -1e-6 or hi[i] > v.inner[i] + 1e-6 for i in range(3)):
            out.append(f"fan {f['name']} sticks out of the wall area")
    rows.add(f"{pid}-INSIDE", "layout", f"[{v.id}] every block inside the box", "; ".join(out) if out else "all inside", "inside the inner volume",
             "fail" if out else "pass")
    for n, b in v.blocks.items():
        for cn, c in b["conns"].items():
            if not c["panel"]:
                continue
            ax = [i for i in range(3) if c["normal"][i]][0]
            if c["normal"][ax] > 0:
                gap = v.inner[ax] - b["hi"][ax]
            else:
                gap = b["lo"][ax]
            ok = -1e-6 <= gap <= st["reach_gap_mm"] + 1e-6
            rows.add(f"{pid}-REACH-{n}.{cn}", "layout", f"[{v.id}] panel part {n}.{cn} reaches the {c['face']} wall", f"gap {gap:.2f} mm",
                     f"0 .. {st['reach_gap_mm']} mm (wall + washer + nut + thread left for the plug)", "pass" if ok else "fail")
    for f in v.fans:
        zlo, zhi = fan_zone(v, f)
        hit = [n for n, (lo, hi) in pseudo_blocks(v).items() if n != "fan:" + f["name"] and aabb_gap((zlo, zhi), (lo, hi)) < -float(st["tolerance"])]
        rows.add(f"{pid}-FAN-{f['name']}", "layout", f"[{v.id}] nothing within {st['fan_clear_mm']:g} mm in front of fan {f['name']}",
                 ", ".join(hit) if hit else "free", f"zone {st['fan_clear_mm']:g} mm deep, fan width, empty", "fail" if hit else "pass")
    noisy = [n for n, b in v.blocks.items() if "noisy" in b["tags"]]
    sens = [n for n, b in v.blocks.items() if "sensitive" in b["tags"]]
    if noisy and sens:
        worst = min(((max(aabb_gap((v.blocks[a]["lo"], v.blocks[a]["hi"]), (v.blocks[b]["lo"], v.blocks[b]["hi"])), 0.0), a, b)
                     for a in noisy for b in sens if a != b), default=None)
        if worst:
            rows.add(f"{pid}-NOISE", "layout", f"[{v.id}] distance noisy to sensitive", f"{worst[0]:.1f} mm ({worst[1]} to {worst[2]})",
                     f">= {st['noisy_sensitive_mm']:g} mm", "pass" if worst[0] >= st["noisy_sensitive_mm"] else "fail")
    else:
        rows.add(f"{pid}-NOISE", "layout", f"[{v.id}] distance noisy to sensitive", "no part tagged both ways", "needs one noisy and one sensitive block", "na")
    ratio = vent_ratio(v)
    lo_r, hi_r = st["intake_ratio"]
    if ratio is None:
        rows.add(f"{pid}-INTAKE", "layout", f"[{v.id}] intake open area / fan swept area", "no fan or no matching vent", f"{lo_r} .. {hi_r}", "na" if not v.fans else "fail")
    else:
        note = "; more open area than needed; see shielding SG-01 (openings against the wavelength) and dust" if ratio > hi_r else ""
        rows.add(f"{pid}-INTAKE", "layout", f"[{v.id}] intake open area / fan swept area", f"{ratio:.2f}{note}",
                 f">= {lo_r} (aim {lo_r} .. {hi_r}; above {hi_r} only a note)", "pass" if ratio >= lo_r else "fail")
    for c in v.cables:
        rt = c["route"]
        probs = []
        if rt["short"]:
            probs.append("a piece is shorter than its bend radius")
        if rt["crosses"]:
            probs.append("crosses " + ", ".join(rt["crosses"]))
        if rt["outside"]:
            probs.append("leaves the box")
        rows.add(f"{pid}-CABLE-{c['name']}", "layout", f"[{v.id}] cable {c['name']} {c['from']} to {c['to']} (R {c['bend_r']:g})",
                 f"{rt['length']:.0f} mm" + ("; " + "; ".join(probs) if probs else ""), "fits its bends, inside, crosses no block", "fail" if probs else "pass")
    outer = [v.inner[i] + 2 * v.wall for i in range(3)]
    return {"volume_l": outer[0] * outer[1] * outer[2] / 1e6, "footprint_cm2": outer[0] * outer[1] / 100.0,
            "outer": outer, "cable_mm": sum(c["route"]["length"] for c in v.cables), "ratio": ratio,
            "clashes": len(overl) + len(close), "heat_w": sum(b["heat"] for b in v.blocks.values()),
            "problems": len(bad) + len(out)}


def vent_ratio(v: Variant):
    """Passive opening area / fan swept area. Exhaust fans pair with intake vents, intake fans with exhaust vents. None when absent."""
    ratios = []
    for direction, kind in (("out", "intake"), ("in", "exhaust")):
        fans = [f for f in v.fans if f["direction"] == direction]
        vents = [x for x in v.vents if x["kind"] == kind]
        if fans and vents:
            ratios.append(sum(vent_area(x) for x in vents) / sum(swept_area(f) for f in fans))
    return min(ratios) if ratios else None


# ---------------------------------------------------------------- pictures -------------------------------------------
def _fit_label(ax, x0, y0, x1, y1, text, colour="#1d2330", min_fs=6.5, max_fs=11, outside_at=None):
    """Text inside a rectangle (data mm), shrunk to fit; below min_fs it goes above the rectangle."""
    import matplotlib
    fig = ax.figure
    bb = ax.get_window_extent()
    sx = bb.width / (ax.get_xlim()[1] - ax.get_xlim()[0])
    sy = bb.height / (ax.get_ylim()[1] - ax.get_ylim()[0])
    wpt = (x1 - x0) * sx * 72.0 / fig.dpi
    hpt = (y1 - y0) * sy * 72.0 / fig.dpi
    lines = text.split("\n")
    need_w = max(len(s) for s in lines) * 0.6
    fs = min(max_fs, 0.92 * wpt / need_w, 0.7 * hpt / (1.25 * len(lines)))
    if fs < min_fs and len(lines) > 1:               # try one line
        text = " ".join(lines)
        lines = [text]
        fs = min(max_fs, 0.92 * wpt / (len(text) * 0.6), 0.7 * hpt / 1.25)
    if fs >= min_fs:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center", fontsize=fs, color=colour, zorder=6, linespacing=1.1)
    else:
        ax.text((x0 + x1) / 2, y1 + 1.0, text.replace("\n", "  "), ha="center", va="bottom", fontsize=min_fs + 0.5, color=colour, zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#9aa3b2", lw=0.5))


def _exposed_rect(rect, covers):
    """The largest rectangle of `rect` (x0, y0, x1, y1) not covered by the later-drawn rectangles `covers`: strips left, right, below, above each of them.
    Returns (rect, fully_visible)."""
    best = [rect]
    for c in covers:
        nxt = []
        for r in best:
            if c[2] <= r[0] or c[0] >= r[2] or c[3] <= r[1] or c[1] >= r[3]:
                nxt.append(r)
                continue
            for q in ((r[0], r[1], min(c[0], r[2]), r[3]), (max(c[2], r[0]), r[1], r[2], r[3]),
                      (r[0], r[1], r[2], min(c[1], r[3])), (r[0], max(c[3], r[1]), r[2], r[3])):
                if q[2] - q[0] > 0.01 and q[3] - q[1] > 0.01:
                    nxt.append(q)
        best = nxt or [(rect[0], rect[1], rect[0], rect[1])]
    return max(best, key=lambda q: (q[2] - q[0]) * (q[3] - q[1])), best == [rect]


def _block_colour(b):
    if "noisy" in b["tags"]:
        return "#f2b27a"
    if "sensitive" in b["tags"]:
        return "#8fb8e8"
    return "#cfd6e0"


def draw_view(v: Variant, view: str, path: str, dpi=110):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle, FancyArrowPatch
    ix, iy = (0, 1) if view == "top" else (0, 2)
    W, H = v.inner[ix], v.inner[iy]
    wall = v.wall
    scale = 7.0 / (W + 2 * wall + 30)
    fig_w = 8.6
    fig_h = max(3.4, fig_w * (H + 2 * wall + 40) / (W + 2 * wall + 30))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_xlim(-wall - 12, W + wall + 18)
    ax.set_ylim(-wall - 22, H + wall + 22)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((-wall, -wall), W + 2 * wall, H + 2 * wall, fc="#e8ebf0", ec="#38404f", lw=1.6, zorder=1))
    ax.add_patch(Rectangle((0, 0), W, H, fc="white", ec="#38404f", lw=0.8, zorder=2))
    name = "top view (back at the top)" if view == "top" else "front elevation (looking at the front, top at the top)"
    ax.set_title(f"Variant {v.id}: {v.title}   -   {name}", fontsize=10, loc="left", color="#1d2330")
    ax.text(0, -wall - 5, f"x 0..{v.inner[0]:g}   {'y' if view == 'top' else 'z'} 0..{H:g} mm inner; wall {wall:g}", fontsize=7, color="#5b6475", va="top")
    order = sorted(v.blocks.items(), key=lambda kv: kv[1]["lo"][2] if view == "top" else -kv[1]["lo"][1])
    rects = [(n, (b["lo"][ix], b["lo"][iy], b["hi"][ix], b["hi"][iy])) for n, b in order]
    for k, (n, b) in enumerate(order):
        x0, x1 = b["lo"][ix], b["hi"][ix]
        y0, y1 = b["lo"][iy], b["hi"][iy]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=_block_colour(b), ec="#38404f", lw=1.0, zorder=3, alpha=0.93))
        txt = n + (f"\n{b['heat']:g} W" if b["heat"] else "")
        (lx0, ly0, lx1, ly1), visible = _exposed_rect((x0, y0, x1, y1), [r for _, r in rects[k + 1:]])
        if not visible:
            txt = txt.replace("\n", " ") + " (partly hidden)"
        _fit_label(ax, lx0, ly0, lx1, ly1, txt, outside_at=(x0, x1, y1))
        for cn, c in b["conns"].items():
            px, py = c["pt"][ix], c["pt"][iy]
            ax.plot([px], [py], marker="s" if c["panel"] else "o", ms=4, mfc="#1d2330", mec="white", mew=0.6, zorder=7)
    for f in v.fans:
        lo, hi = fan_body(f, v.inner)
        axn = face_axes(f["face"])[0]
        behind = FACES[f["face"]][1 if view == "side" else 2] > 0 and axn == (1 if view == "side" else 2)   # on the far wall: blocks hide it
        ax.add_patch(Rectangle((lo[ix], lo[iy]), hi[ix] - lo[ix], hi[iy] - lo[iy], fc="#9aa3b2", ec="#38404f", lw=1.0, zorder=2.8 if behind else 3.5))
        cx, cy = (lo[ix] + hi[ix]) / 2, (lo[iy] + hi[iy]) / 2
        if ix != axn and iy != axn:      # looking along the fan axis: draw the rotor
            ax.add_patch(Circle((cx, cy), f["blade_d"] / 2, fc="none", ec="#38404f", lw=0.9, zorder=4))
            ax.add_patch(Circle((cx, cy), f["hub_d"] / 2, fc="#38404f", ec="none", zorder=4))
        ax.text(cx, hi[iy] + 1.0, f"fan {f['name']} {f['size']:g}", ha="center", va="bottom", fontsize=7, color="#1d2330", zorder=6,
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
        # the free zone in front of the fan
        zlo, zhi = fan_zone(v, f)
        ax.add_patch(Rectangle((zlo[ix], zlo[iy]), zhi[ix] - zlo[ix], zhi[iy] - zlo[iy], fc="none", ec="#1d4ed8", lw=0.8, ls=":", zorder=3.6))
    for x in v.vents:
        lo, hi = vent_box(x, v.inner, depth=1.2)
        vaxis = face_axes(x["face"])[0]
        face_on = vaxis == (1 if view == "side" else 2)          # the wall faces the viewer: show it as a dashed window only
        w_, h_ = max(hi[ix] - lo[ix], 1.2), max(hi[iy] - lo[iy], 1.2)
        x0_, y0_ = lo[ix] - (0 if hi[ix] - lo[ix] > 1 else 0.6), lo[iy] - (0 if hi[iy] - lo[iy] > 1 else 0.6)
        if face_on:
            ax.add_patch(Rectangle((x0_, y0_), w_, h_, fc="#bfd7ff", ec="#1d4ed8", lw=0.9, ls="--", alpha=0.18, zorder=8))
            ax.add_patch(Rectangle((x0_, y0_), w_, h_, fc="none", ec="#1d4ed8", lw=0.9, ls="--", zorder=8))
            ax.text(x0_ + 1.5, y0_ + h_ - 1.0, f"{x['name']} {vent_area(x):.0f} mm2 (in the wall facing you)", fontsize=6.5, color="#1d4ed8", ha="left", va="top", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85))
        else:
            ax.add_patch(Rectangle((x0_, y0_), w_, h_, fc="#bfd7ff", ec="#1d4ed8", lw=0.8, hatch="////", zorder=3.7))
            cx, cy = (lo[ix] + hi[ix]) / 2, (lo[iy] + hi[iy]) / 2
            n = FACES[x["face"]]
            ax.text(cx + n[ix] * 9.0, cy + n[iy] * 9.0, f"{x['name']} {vent_area(x):.0f} mm2", fontsize=6.5, color="#1d4ed8", ha="center", va="center", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85))
    # air path: intake vents -> fans -> exhaust vents (centres), only the first pair shown per fan
    def centre_of(box):
        return tuple((box[0][i] + box[1][i]) / 2 for i in range(3))
    for f in v.fans:
        fc = centre_of(fan_body(f, v.inner))
        src = [x for x in v.vents if x["kind"] == ("intake" if f["direction"] == "out" else "exhaust")]
        for x in src:
            vc = centre_of(vent_box(x, v.inner))
            a, b = (vc, fc) if f["direction"] == "out" else (fc, vc)
            if math.hypot(a[ix] - b[ix], a[iy] - b[iy]) < 3:
                continue
            ax.add_patch(FancyArrowPatch((a[ix], a[iy]), (b[ix], b[iy]), arrowstyle="-|>", mutation_scale=16, lw=2.6, color="#1d4ed8", alpha=0.55, zorder=9))
    for c in v.cables:
        pts = c["route"]["points"]
        ax.plot([p[ix] for p in pts], [p[iy] for p in pts], "-", color=c["colour"], lw=2.2, zorder=8, solid_capstyle="round")
        legs = sorted(range(len(pts) - 1), key=lambda i: -math.hypot(pts[i + 1][ix] - pts[i][ix], pts[i + 1][iy] - pts[i][iy]))
        i0 = legs[0]
        mid = tuple((pts[i0][k] + pts[i0 + 1][k]) / 2 for k in range(3))
        ax.text(mid[ix], mid[iy], f" {c['name']} {c['route']['length']:.0f}", fontsize=6.5, color=c["colour"], zorder=10, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
    ax.text(-wall - 12, -wall - 13, "blue arrow = air path   dotted blue = fan free zone   orange = noisy   blue block = sensitive   lines = cables (mm)",
            fontsize=6.5, color="#5b6475", ha="left", va="top")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def comparison_table(vs: list, metrics: dict, out_md: str, out_png: str):
    heads = ["", *[f"{v.id}: {v.title}" for v in vs]]
    rowsd = [
        ("Outer size (mm)", [" x ".join(f"{x:.0f}" for x in metrics[v.id]["outer"]) for v in vs], None),
        ("Volume (litres)", [f"{metrics[v.id]['volume_l']:.2f}" for v in vs], [metrics[v.id]["volume_l"] for v in vs]),
        ("Footprint (cm2)", [f"{metrics[v.id]['footprint_cm2']:.0f}" for v in vs], [metrics[v.id]["footprint_cm2"] for v in vs]),
        ("Total cable length (mm)", [f"{metrics[v.id]['cable_mm']:.0f}" for v in vs], [metrics[v.id]["cable_mm"] for v in vs]),
        ("Vent ratio (intake / fan swept)", ["n/a" if metrics[v.id]["ratio"] is None else f"{metrics[v.id]['ratio']:.2f}" for v in vs], None),
        ("Clashes + gaps too small", [str(metrics[v.id]["clashes"]) for v in vs], [metrics[v.id]["clashes"] for v in vs]),
        ("Heat total (W)", [f"{metrics[v.id]['heat_w']:g}" for v in vs], None),
        ("Check rows failed", [str(metrics[v.id]["failed"]) for v in vs], [metrics[v.id]["failed"] for v in vs]),
    ]
    lines = ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
    for name, vals, nums in rowsd:
        lines.append("| " + " | ".join([name, *vals]) + " |")
    lines += ["", "Lower is better for volume, footprint, cable length, clashes and failed rows. All values are from block models: an estimate to choose an arrangement, not a final size."]
    mc.atomic_write(out_md, "# Layout comparison\n\n" + "\n".join(lines) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(2.6 + 2.6 * len(vs), 0.5 + 0.42 * (len(rowsd) + 1)), dpi=120)
    ax.axis("off")
    cells = [vals for _, vals, _ in rowsd]
    tbl = ax.table(cellText=[[name, *vals] for name, vals, _ in rowsd], colLabels=heads, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    tbl.auto_set_column_width(list(range(len(heads))))
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#c8ceda")
        if r == 0:
            cell.set_facecolor("#e8ebf0")
            cell.set_text_props(weight="bold")
        elif c == 0:
            cell.set_text_props(ha="left")
            cell._loc = "left"
    for ri, (_, vals, nums) in enumerate(rowsd, start=1):
        if nums and len(set(nums)) > 1:
            best = min(nums)
            for ci, n in enumerate(nums, start=1):
                if n == best:
                    tbl[(ri, ci)].set_facecolor("#d9f0de")
    fig.savefig(out_png, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def soft_resolve(args):
    """Like mc.resolve, but with --out and no mech.toml anywhere the defaults apply (a study can start before the project folder exists)."""
    try:
        return mc.resolve(args)
    except mc.MechError:
        if not getattr(args, "out", None):
            raise
        return mc.Job(os.getcwd(), mc.load_config(os.getcwd()), os.path.abspath(args.out))


def run(args) -> int:
    job = soft_resolve(args)
    path = args.layout
    if not os.path.isfile(path):
        print(f"could not run: layout file not found: {path}", file=sys.stderr)
        return 2
    mc.require_module("matplotlib", "pictures")
    study = load_study(path)
    ids = [s for s in (args.variants.split(",") if args.variants else study["variant"].keys())]
    outd = os.path.join(job.out, "layout")
    if os.path.isdir(outd):
        shutil.rmtree(outd, ignore_errors=True)
    os.makedirs(outd, exist_ok=True)
    rows = mc.Rows()
    vs, metrics = [], {}
    for vid in ids:
        if vid not in study["variant"]:
            print(f"could not run: no variant '{vid}' in {path}", file=sys.stderr)
            return 2
        v = build_variant(study, vid)
        before = len(rows.rows)
        m = check_variant(v, rows)
        m["failed"] = sum(1 for r in rows.rows[before:] if r["verdict"] == "fail")
        metrics[vid] = m
        vs.append(v)
        if not args.no_pictures:
            for view in ("top", "side"):
                draw_view(v, "top" if view == "top" else "side", os.path.join(outd, f"{vid}_{view}.png"))
    if not args.no_pictures:
        comparison_table(vs, metrics, os.path.join(outd, "comparison.md"), os.path.join(outd, "comparison.png"))
    rows.write(job.out, "layout_study.py", [path])
    rows.print_table(only_bad=True)
    print(f"layout study in {outd}")
    print(rows.headline())
    return rows.exit_code()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="pre-CAD block layout study")
    ap.add_argument("layout", help="layout TOML")
    mc.add_std_args(ap)
    ap.add_argument("--variants", help="comma list (default all)")
    ap.add_argument("--no-pictures", action="store_true")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
