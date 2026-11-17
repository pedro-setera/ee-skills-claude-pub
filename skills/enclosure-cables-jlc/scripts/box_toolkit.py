"""CadQuery helpers for a parametric box model (printed or sheet metal), in one frame.

What it does
    A library, imported by the project's `model/build_model.py` (see templates/model_template/). Frame: origin at the
    outer front-left-bottom corner of the box, x to the right, y to the back, z up, millimetres, degrees.
    Solids: `cyl`, `box`, `stadium`, `slot`, `rrect`, `csk_hole`, `stand`, `stands_from_interface`.
    Patterns: `hex_field` (a complete regular matrix of holes; on a collision the WHOLE group moves by whole rows or
    columns, never a single hole dropped; no free place = an error), `vent_area_ratio`.
    Panels: `panel_cutouts(shape, face, cutouts, wall, box)` (round, rect, stadium, and a D-hole with one flat or two).
    Reach: `thread_budget`.
    Sheet metal: `bend_sector` (a true cylindrical bend), `u_shell`, `flange`, `clinch_nut` (table + solid).
    Files: `print_pose(part, face)` (the NAMED face of the part's bounding box lies on the bed), `export_step(shape, path,
    company, schema="AP203")` (author line scrubbed; the FILE_SCHEMA of the written file is read back and must name the
    schema asked for), `step_schema(path)`, `load_model(path)`.

Why it exists (the real failure, told without names)
    Vent patterns lost single holes where they met a screw boss, so the open area was no longer what the heat table
    assumed; bends drawn as facets could not be unfolded by the maker's tool; stands were typed as numbers that drifted
    from the board; a print pose put the opposite face on the bed and its test passed because it only measured the
    height; a D-shaped panel hole came out with two flats; the STEP schema the maker recommends could only be set by a
    number the kernel does not document. Each helper does the whole job in one place so the model stays short and the
    numbers stay one set.

Usage
    import sys, os; sys.path.insert(0, os.environ.get("MECH_SCRIPTS", "<skill>/scripts")); import box_toolkit as bt
    python -I box_toolkit.py --selftest     builds each helper once and checks volumes (needs CadQuery)

Config keys
    none (every size is an argument; screw sizes come from the SCREWS table, clinch nuts from CLINCH_NUTS)

Exit codes (selftest): 0 ok, 1 a helper gave a wrong volume, 2 CadQuery missing
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import importlib.util
import math
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    import cadquery as cq
except ImportError:                       # scripts that only need the tables can still import this file
    cq = None

V = (lambda *a: cq.Vector(*a)) if cq else None

# Screw data (mm). d = major diameter; pilot = hole for a self-tapping screw in printed plastic (about 0.8 d, to be
# calibrated with the test coupon); clear = clearance hole in the lid/board side; head_d / head_k = pan head;
# post_d = stand outer diameter (>= 2.5 d for plastic), flare = root flare added to the radius.
SCREWS = {
    "M2":   {"d": 2.0, "pilot": 1.6, "clear": 2.4, "head_d": 3.8, "head_k": 1.3, "post_d": 5.0, "flare": 1.5},
    "M2.5": {"d": 2.5, "pilot": 2.0, "clear": 2.9, "head_d": 4.7, "head_k": 1.6, "post_d": 6.0, "flare": 1.8},
    "M3":   {"d": 3.0, "pilot": 2.5, "clear": 3.4, "head_d": 5.6, "head_k": 2.0, "post_d": 7.0, "flare": 2.0},
    "M4":   {"d": 4.0, "pilot": 3.3, "clear": 4.5, "head_d": 7.5, "head_k": 2.6, "post_d": 9.0, "flare": 2.5},
}

# Self-clinching nuts (PEM-style S / CLS families). Typical catalogue values; the M3 and M4 rows agree with the seed
# capability sheet (templates/jlccnc-sheet-metal.capability.toml, as read 2026-11). VERIFY ON THE SUPPLIER'S PAGE
# before drawing: hole = hole in the sheet, E = head diameter, T = head height above the sheet, A = shank length behind
# the sheet, min_sheet = thinnest sheet it clinches, edge = hole centre to a free edge (catalogue minimum, no margin),
# bend = hole centre to a bend (the supplier's page, as read 2026-11, said 7; 7.5 is a margin that has passed supplier
# review). M2 to M3 share one shank size, so they share the hole and the edge distance. Code suffix -1 / -2 = shank for
# thin / thicker sheet.
CLINCH_NUTS = {
    "S-M2-1":   {"thread": 2.0, "hole": 4.25, "E": 6.3, "T": 1.5, "A": 1.0, "min_sheet": 1.0, "edge": 4.8, "bend": 7.0},
    "S-M2.5-1": {"thread": 2.5, "hole": 4.25, "E": 6.3, "T": 1.5, "A": 1.0, "min_sheet": 1.0, "edge": 4.8, "bend": 7.0},
    "S-M3-1":   {"thread": 3.0, "hole": 4.25, "E": 6.3, "T": 1.5, "A": 1.0, "min_sheet": 1.0, "edge": 4.8, "bend": 7.0},
    "CLS-M3-2": {"thread": 3.0, "hole": 4.25, "E": 6.3, "T": 1.5, "A": 1.4, "min_sheet": 1.4, "edge": 4.8, "bend": 7.0},
    "S-M4-1":   {"thread": 4.0, "hole": 5.40, "E": 7.9, "T": 2.0, "A": 1.0, "min_sheet": 1.0, "edge": 6.9, "bend": 7.0},
    "CLS-M4-2": {"thread": 4.0, "hole": 5.40, "E": 7.9, "T": 2.0, "A": 1.4, "min_sheet": 1.4, "edge": 6.9, "bend": 7.0},
    "S-M5-1":   {"thread": 5.0, "hole": 7.15, "E": 8.75, "T": 2.0, "A": 1.0, "min_sheet": 1.0, "edge": 7.1, "bend": 7.5},
}
CLINCH_NOTE = "typical catalogue values; verify on the supplier's page"


# ---------------------------------------------------------------- frames ---------------------------------------------
_AXES = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1), "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1)}


def _vec(a):
    return V(*_AXES[a]) if isinstance(a, str) else V(*a)


def _plane(p, normal, along=None):
    n = _vec(normal)
    if along is None:
        along = "x" if abs(n.x) < 0.9 else "y"
    xd = _vec(along)
    xd = xd - n * xd.dot(n)             # xDir must be perpendicular to the normal
    return cq.Plane(origin=V(*p), xDir=xd.normalized(), normal=n)


def _prism(wp, depth):
    return wp.extrude(depth).val()


# ---------------------------------------------------------------- primitives ----------------------------------------
def cyl(p, d, length, axis="z"):
    """A cylinder of diameter d and `length` from point p along `axis` ('x','y','z','-z',... or a vector)."""
    return cq.Solid.makeCylinder(d / 2.0, length, V(*p), _vec(axis))


def box(x0, y0, z0, x1, y1, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def rrect(p, w, h, r, depth, normal="z", along=None):
    """A rounded-rectangle prism w x h (w along `along`), centred on p, from p along `normal` for `depth`."""
    wp = cq.Workplane(_plane(p, normal, along)).rect(w, h)
    if r > 0:
        wp = cq.Workplane(_plane(p, normal, along)).sketch().rect(w, h).vertices().fillet(min(r, w / 2 - 1e-6, h / 2 - 1e-6)).finalize()
    return _prism(wp, depth)


def stadium(p, w, h, depth, normal="z", along=None):
    """A stadium (long axis `along`, w x h overall, w >= h), centred on p, from p along `normal` for `depth`."""
    if w <= h:
        return cyl(p, h, depth, normal)
    return rrect(p, w, h, h / 2.0, depth, normal, along)


def slot(p, length, width, depth, along="x", normal="z"):
    """A slot with round ends: `length` overall along `along`, `width` across, centred on p."""
    return stadium(p, length, width, depth, normal, along)


def csk_hole(p, d, head_d, depth, angle=90.0, normal="z"):
    """A countersunk hole's cutter: the cone has its large circle (head_d) at p and narrows INTO the material along
    `normal`; the shank d continues to `depth` from p. A little overshoot is added on the open side."""
    n = _vec(normal)
    h_cone = (head_d - d) / 2.0 / math.tan(math.radians(angle / 2.0))
    cone = cq.Solid.makeCone(head_d / 2.0, d / 2.0, h_cone, V(*p), n)
    shank = cq.Solid.makeCylinder(d / 2.0, depth, V(*p), n)
    over = cq.Solid.makeCylinder(head_d / 2.0, 0.5, V(*p) - n * 0.5, n)
    return cone.fuse(shank).fuse(over).clean()


def stand(p, height, screw="M2.5", post_d=None, hole_depth=None, pilot=None, flare=None, flare_h=None, axis="z", hollow=True):
    """A conical-root post for a self-tapping screw: from base point p up `height` along axis. The root flares from
    post_d + 2 * flare to post_d over flare_h (a cone, never a thin post on a flat step: it snaps), the pilot hole
    (self-tapping, `pilot`) is `hole_depth` deep (default: the whole post minus 1 mm)."""
    s = SCREWS[screw]
    post_d = post_d or s["post_d"]
    pilot = pilot or s["pilot"]
    flare = s["flare"] if flare is None else flare
    flare_h = flare_h if flare_h is not None else min(height * 0.6, flare * 1.6)
    n = _vec(axis)
    base = cq.Solid.makeCone(post_d / 2.0 + flare, post_d / 2.0, flare_h, V(*p), n)
    top = cq.Solid.makeCylinder(post_d / 2.0, max(height - flare_h, 0.01), V(*p) + n * flare_h, n)
    post = base.fuse(top).clean()
    if hollow:
        hd = hole_depth if hole_depth is not None else max(height - 1.0, 1.0)
        post = post.cut(cq.Solid.makeCylinder(pilot / 2.0, hd + 0.01, V(*p) + n * (height - hd), n))
    return post


def stands_from_interface(interface, z_bottom, height, screw="M2.5", placement=None, prefix="stand_", **kw):
    """One stand per mounting hole of an interface.json (dict or path), at the box-frame position of the hole, from
    z_bottom up `height`. `placement` as in interface_read.to_box. Returns {prefix + hole name: solid}."""
    import interface_read as ir
    itf = ir.load_interface(interface) if isinstance(interface, (str, os.PathLike)) else interface
    f = ir.to_box(itf, placement or {})
    out = {}
    for h in itf.get("holes", []):
        x, y, _ = f(h["x"], h["y"], 0.0)
        out[prefix + str(h["name"])] = stand((x, y, z_bottom), height, screw, **kw)
    return out


# ---------------------------------------------------------------- patterns -----------------------------------------
class VentError(Exception):
    pass


class HexField(list):
    """The hole centres of a complete matrix, plus how the group was moved: .shift (du, dv), .rows, .cols, .d."""
    shift = (0.0, 0.0)
    rows = cols = 0
    d = 0.0
    pitch = 0.0

    def open_area(self):
        return len(self) * math.pi * self.d ** 2 / 4.0


def _hits(c, r, forbid, clearance):
    u, v = c
    for f in forbid:
        if len(f) == 3:                                    # circle (u, v, radius)
            if math.hypot(u - f[0], v - f[1]) < r + f[2] + clearance:
                return True
        else:                                              # rectangle (u0, v0, u1, v1)
            nu = min(max(u, f[0]), f[2])
            nv = min(max(v, f[1]), f[3])
            if math.hypot(u - nu, v - nv) < r + clearance:
                return True
    return False


def hex_field(region, pitch, d, cols, rows, forbid=(), clearance=0.0, hexagonal=True, edge_margin=0.0, max_shift_rows=50):
    """A complete `cols` x `rows` matrix of holes of diameter d, centred in `region` = (u0, v0, u1, v1).
    hexagonal=True: every second row is offset by pitch / 2 and rows are pitch * 0.866 apart; False: a square grid.
    forbid: rectangles (u0, v0, u1, v1) or circles (u, v, radius) the holes must stay `clearance` away from.
    On a collision the WHOLE group is moved, by whole rows (v) and whole pitches (u), nearest first; a hole is never
    dropped. When the group does not fit the region without a collision: VentError (change the size, not the count)."""
    u0, v0, u1, v1 = region
    dv = pitch * (math.sqrt(3) / 2.0 if hexagonal else 1.0)
    base = []
    for j in range(rows):
        off = pitch / 2.0 if (hexagonal and j % 2) else 0.0
        for i in range(cols):
            base.append((i * pitch + off, j * dv))
    wu = (cols - 1) * pitch + (pitch / 2.0 if hexagonal and rows > 1 else 0.0)
    wv = (rows - 1) * dv
    cu = (u0 + u1) / 2.0 - wu / 2.0
    cv = (v0 + v1) / 2.0 - wv / 2.0
    r = d / 2.0
    cand = [(0, 0)]
    for k in range(1, max_shift_rows + 1):
        cand += [(0, k), (0, -k), (k, 0), (-k, 0)]
        for m in range(1, k + 1):
            cand += [(m, k), (-m, k), (m, -k), (-m, -k), (k, m), (-k, m), (k, -m), (-k, -m)]
    for iu, iv in cand:
        du, dvv = cu + iu * pitch, cv + iv * dv
        pts = [(du + a, dvv + b) for a, b in base]
        inside = all(u0 + edge_margin <= p[0] - r and p[0] + r <= u1 - edge_margin and v0 + edge_margin <= p[1] - r and p[1] + r <= v1 - edge_margin for p in pts)
        if not inside:
            continue
        if any(_hits(p, r, forbid, clearance) for p in pts):
            continue
        out = HexField(pts)
        out.shift, out.rows, out.cols, out.d, out.pitch = (iu * pitch, iv * dv), rows, cols, d, pitch
        return out
    raise VentError(f"a {cols} x {rows} matrix of d {d} at pitch {pitch} fits nowhere in the region without a collision")


def vent_area_ratio(open_area, fan_d, hub_d=0.0):
    """Open area of the intake / the fan's swept area, pi/4 (fan_d^2 - hub_d^2). Rule of thumb of the skill: 1.1 or more
    passes, 1.1 to 1.5 is the aim. Returns {"ratio", "swept", "verdict": "low|ok|high", "pass", "note"}: "low" (< 1.1) does
    not pass; "high" (> 1.5) still passes and carries the note "more open area than needed; see shielding SG-01 (openings
    against the wavelength) and dust". An estimate, to be proved by the bench test. For several fans blowing the same way
    pass the SUM of their swept areas (one ratio per direction group), see heat_air.py."""
    swept = math.pi / 4.0 * (fan_d ** 2 - hub_d ** 2)
    ratio = open_area / swept if swept > 0 else float("inf")
    verdict = "low" if ratio < 1.1 else ("high" if ratio > 1.5 else "ok")
    note = "more open area than needed; see shielding SG-01 (openings against the wavelength) and dust" if verdict == "high" else ""
    return {"ratio": round(ratio, 3), "swept": round(swept, 2), "verdict": verdict, "pass": ratio >= 1.1, "note": note}


def thread_budget(thread_len, wall, washer=0.0, nut=0.0, plug_needs=0.0):
    """Thread of a panel connector left for the mating plug: thread_len - wall - washer - nut, against what the plug's
    coupling nut needs. Returns {"free", "needs", "margin", "ok"}."""
    free = thread_len - wall - washer - nut
    return {"free": round(free, 3), "needs": plug_needs, "margin": round(free - plug_needs, 3), "ok": free >= plug_needs}


# ---------------------------------------------------------------- panels -------------------------------------------
_FACES = {  # face: (normal pointing OUT of the box, u axis, v axis)  u, v are box-frame coordinates
    "front": ("-y", "x", "z"), "back": ("y", "x", "z"), "left": ("-x", "y", "z"), "right": ("x", "y", "z"),
    "bottom": ("-z", "x", "y"), "top": ("z", "x", "y"),
}


def panel_cutouts(shape, face, cutouts, wall, box_size):
    """Cut a list of openings through the wall of `face`. box_size = (W, D, H). Coordinates (u, v) of a cut-out are
    box-frame values: front/back (x, z), left/right (y, z), top/bottom (x, y). Each cut-out is a dict:
      {"kind": "round", "u", "v", "d"} | {"kind": "rect", "u", "v", "w", "h", "r"?} | {"kind": "stadium", "u", "v", "w", "h"}
      | {"kind": "d", "u", "v", "d", "flat", "flat_side"?}
    A D-hole is a round hole of diameter d with a flat. `flat` is the across-flats size: the distance from the round side to
    the flat (0 < flat <= d). `flat_side` says where the flat is, in the (u, v) of the cut-out: "+v" (default: ONE flat, on
    the +v side, as a single-D panel hole is drawn), "-v" (one flat on the -v side), or "both" (a double-D: two flats `flat`
    apart, centred on v). Cutters run 1 mm outside and 1 mm past the wall's inside."""
    W, D, H = box_size
    n, ua, va = _FACES[face]
    nv = _vec(n)
    origin = {"front": (0, 0, 0), "back": (0, D, 0), "left": (0, 0, 0), "right": (W, 0, 0), "bottom": (0, 0, 0), "top": (0, 0, H)}[face]
    out = shape
    for c in cutouts:
        u, v = c["u"], c["v"]
        p = list(origin)
        for ax, val in ((ua, u), (va, v)):
            p["xyz".index(ax)] = val
        start = V(*p) + nv * 1.0                         # 1 mm outside
        depth = wall + 2.0
        k = c.get("kind", "round")
        if k == "round":
            cut = cq.Solid.makeCylinder(c["d"] / 2.0, depth, start, -nv)
        elif k == "rect":
            cut = rrect(tuple(start), c["w"], c["h"], c.get("r", 0.0), depth, -nv, ua)
        elif k == "stadium":
            cut = stadium(tuple(start), c["w"], c["h"], depth, -nv, ua)
        elif k == "d":
            r = c["d"] / 2.0
            flat = float(c["flat"])
            side = c.get("flat_side", "+v")
            if side not in ("+v", "-v", "both"):
                raise ValueError(f"D-hole flat_side must be '+v', '-v' or 'both', not {side!r}")
            if not 0.0 < flat <= c["d"] + 1e-9:
                raise ValueError(f"D-hole: flat (the distance from the round side to the flat) must be 0 < flat <= d, got {flat} for d {c['d']}")
            cyl_ = cq.Solid.makeCylinder(r, depth, start, -nv)
            # keep the cylinder only on the round side of the flat(s): a box in the BOX frame, so the sign of v is the face's own
            if side == "+v":
                v_lo, v_hi = v - r - 1.0, v - r + flat
            elif side == "-v":
                v_lo, v_hi = v + r - flat, v + r + 1.0
            else:
                v_lo, v_hi = v - flat / 2.0, v + flat / 2.0
            na = next(ax for ax in "xyz" if ax not in (ua, va))              # the axis through the wall
            end = start - nv * depth
            n_lo, n_hi = sorted((start.toTuple()["xyz".index(na)], end.toTuple()["xyz".index(na)]))
            lo, hi = [0.0] * 3, [0.0] * 3
            for ax, (a, b) in ((ua, (u - r - 1.0, u + r + 1.0)), (va, (v_lo, v_hi)), (na, (n_lo - 0.5, n_hi + 0.5))):
                lo["xyz".index(ax)], hi["xyz".index(ax)] = a, b
            cut = cyl_.intersect(box(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]))
        else:
            raise ValueError(f"unknown cut-out kind {k!r}")
        out = out.cut(cut)
    return out


# ---------------------------------------------------------------- sheet metal --------------------------------------
def bend_sector(axis, centre, quadrant, a0, a1, r_in, t):
    """A bend as a true cylindrical sector: the ring r_in .. r_in + t round `centre` (2D, in the plane normal to
    `axis`; for axis x: (y, z), y: (x, z), z: (x, y)), limited to the quadrant (su, sv) = signs of the directions
    from the centre, extruded along the axis from a0 to a1. One solid."""
    cu, cv = centre
    su, sv = quadrant
    ro = r_in + t
    base = {"x": V(a0, cu, cv), "y": V(cu, a0, cv), "z": V(cu, cv, a0)}[axis]
    d = {"x": V(1, 0, 0), "y": V(0, 1, 0), "z": V(0, 0, 1)}[axis]
    ring = cq.Solid.makeCylinder(ro, a1 - a0, base, d).cut(cq.Solid.makeCylinder(r_in, a1 - a0, base, d))
    big = ro + 1.0

    def corner(a, b):
        return {"x": V(a0, a, b), "y": V(a, a0, b), "z": V(a, b, a0)}[axis]
    lo_u, hi_u = sorted((cu, cu + su * big))
    lo_v, hi_v = sorted((cv, cv + sv * big))
    p0 = corner(lo_u, lo_v)
    dims = {"x": (a1 - a0, hi_u - lo_u, hi_v - lo_v), "y": (hi_u - lo_u, a1 - a0, hi_v - lo_v), "z": (hi_u - lo_u, hi_v - lo_v, a1 - a0)}[axis]
    quad = cq.Solid.makeBox(dims[0], dims[1], dims[2], p0)
    sec = ring.intersect(quad)
    sols = sec.Solids()
    if len(sols) != 1:
        raise ValueError(f"bend_sector made {len(sols)} solids")
    return sols[0]


def u_shell(W, D, H, t, r_out):
    """A U-shaped sheet-metal tray, open at the top: width W (x), length D (y), height H (z), thickness t, outer bend
    radius r_out (inner r_out - t), the bends true cylinders. Origin at the outer front-left-bottom corner."""
    if r_out <= t:
        raise ValueError("r_out must be larger than the thickness")
    outer = cq.Workplane("XY").box(W, D, H, centered=False).edges("|Y and <Z").fillet(r_out)
    inner = (cq.Workplane("XY").box(W - 2 * t, D + 2, H, centered=False).translate((t, -1, t))
             .edges("|Y and <Z").fillet(r_out - t))
    return outer.cut(inner).val()


def flange(wall_x, z_top, length, t, r_out, y0, y1, inward=1):
    """A return flange on the top edge of a wall that stands at outer face wall_x (inward = +1: the flange runs toward
    +x, for the left wall; -1 for the right wall): a bend of outer radius r_out from the wall, then a flat `length`
    long, its top at z_top. The wall itself must end at z_top - r_out. Extruded along y from y0 to y1."""
    ri = r_out - t
    cx = wall_x + inward * r_out
    cz = z_top - r_out
    bend = bend_sector("y", (cx, cz), (-inward, 1), y0, y1, ri, t)
    x_a, x_b = (cx, cx + inward * length)
    flat = box(min(x_a, x_b), y0, z_top - t, max(x_a, x_b), y1, z_top)
    return bend.fuse(flat).clean()


def clinch_nut(code, p=None, n=(0, 0, 1)):
    """Data of a self-clinching nut (see CLINCH_NUTS; verify on the supplier's page). With p (the sheet's face on the
    nut's body side) and n (outward normal of that face): the solid, body E x T above the face, shank in the hole
    behind it, thread bore at the screw's major diameter."""
    if code not in CLINCH_NUTS:
        raise KeyError(f"unknown clinch nut {code!r}; known: {', '.join(CLINCH_NUTS)} ({CLINCH_NOTE})")
    d = dict(CLINCH_NUTS[code])
    if p is None:
        return d
    nv, pv = V(*n), V(*p)
    body = cq.Solid.makeCylinder(d["E"] / 2.0, d["T"], pv, nv)
    shank = cq.Solid.makeCylinder(d["hole"] / 2.0, d["A"], pv - nv * d["A"], nv)
    nut = body.fuse(shank).clean()
    return nut.cut(cq.Solid.makeCylinder(d["thread"] / 2.0, d["T"] + d["A"] + 2, pv - nv * (d["A"] + 1), nv))


# ---------------------------------------------------------------- printing and files --------------------------------
# rotation that puts the named face of the part's bounding box on the bed (z = 0): (axis, degrees, right-hand rule).
# front = the face at the minimum y (the face a viewer at -y sees), back = maximum y, left = minimum x, right = maximum x.
# Turning +90 degrees about x sends (y, z) to (-z, y): the minimum-y face becomes the lowest one.
_POSE = {"bottom": None, "top": ((1, 0, 0), 180), "front": ((1, 0, 0), 90), "back": ((1, 0, 0), -90),
         "left": ((0, 1, 0), -90), "right": ((0, 1, 0), 90)}


def print_pose(part, face="bottom"):
    """Rotate the part so that the NAMED face of its bounding box (bottom, top, front, back, left, right: front is the
    face at the minimum y, back the maximum y, left the minimum x, right the maximum x, as in the box frame) lies on the
    bed, and move it to x, y >= 0, z >= 0. Returns a shape. For a non-flat face rotate yourself first."""
    if face not in _POSE:
        raise ValueError(f"unknown face {face!r}; one of {', '.join(_POSE)}")
    s = part.val() if hasattr(part, "val") else part
    rot = _POSE[face]
    if rot:
        s = s.rotate(V(0, 0, 0), V(*rot[0]), rot[1])
    bb = s.BoundingBox()
    return s.translate(V(-bb.xmin, -bb.ymin, -bb.zmin))


_FILE_NAME_RE = re.compile(r"FILE_NAME\s*\((.*?)\)\s*;", re.S)


def scrub_step_header(path, company=""):
    """Rewrite FILE_NAME of a STEP file: no author, the organisation = company, no preprocessor/originating paths."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        txt = f.read()
    name = os.path.basename(path).replace("'", "")
    new = f"FILE_NAME('{name}','',(''),('{company}'),'','','');"
    txt2, n = _FILE_NAME_RE.subn(lambda m: new, txt, count=1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt2)
    return n == 1


# STEP schema names -> the number the kernel's "write.step.schema" takes (the kernel refuses the NAME "AP203", only the number
# 3 works) and the schema name it then writes into FILE_SCHEMA.
STEP_SCHEMAS = {"AP203": (3, "CONFIG_CONTROL_DESIGN"), "AP214": (4, "AUTOMOTIVE_DESIGN"),
                "AP242": (5, "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF")}
_SCHEMA_RE = re.compile(r"FILE_SCHEMA\s*\(\s*\((.*?)\)\s*\)\s*;", re.S)


def step_schema(path):
    """The schema names in the FILE_SCHEMA line of a STEP file, as a list of strings (e.g. ['CONFIG_CONTROL_DESIGN'] for
    AP203); [] when the line is missing."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        head = f.read(20000)
    m = _SCHEMA_RE.search(head)
    return re.findall(r"'([^']*)'", m.group(1)) if m else []


def export_step(shape, path, company="", schema="AP203"):
    """Export STEP and scrub the header (author, organisation, paths). `shape` may be a Workplane, Shape or a dict of
    named shapes (written as one assembly compound). `schema` is "AP203" (the default: what the sheet-metal maker
    recommends), "AP214", "AP242", or None for whatever the kernel writes by default (AP214). The kernel takes the
    schema as a number, so this sets 3 / 4 / 5 on its "write.step.schema" parameter for the one write and puts the old
    value back afterwards; the FILE_SCHEMA line of the written file is read back and a mismatch raises RuntimeError."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if isinstance(shape, dict):
        shape = cq.Compound.makeCompound([v.val() if hasattr(v, "val") else v for v in shape.values()])
    if hasattr(shape, "val"):
        shape = shape.val()
    num, want = None, None
    if schema is not None:
        key = str(schema).upper()
        if key not in STEP_SCHEMAS:
            raise ValueError(f"unknown STEP schema {schema!r}; one of {', '.join(STEP_SCHEMAS)} or None")
        num, want = STEP_SCHEMAS[key]
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_Writer
    STEPControl_Writer()                                    # the kernel fills its parameters when a writer is made (the value reads 0 before)
    old = Interface_Static.IVal_s("write.step.schema")
    if num is not None and not Interface_Static.SetIVal_s("write.step.schema", num):
        raise RuntimeError(f"the CAD kernel refused write.step.schema = {num} ({schema})")
    try:
        cq.exporters.export(cq.Workplane("XY").add(shape), path, "STEP")
    finally:
        if num is not None:
            Interface_Static.SetIVal_s("write.step.schema", old)
    scrub_step_header(path, company)
    if want is not None and not any(want in s for s in step_schema(path)):
        raise RuntimeError(f"{path}: FILE_SCHEMA is {step_schema(path)}, not {schema} ({want})")
    return path


def load_model(path):
    """Import model/build_model.py by path and call build(). Accepted results: a dict name -> shape (an optional key
    'placements' holds the board placements); or a tuple (solids, placements). A module attribute PLACEMENTS is also
    read. Returns (solids dict of shapes/workplanes, meta dict with 'placements')."""
    path = os.path.abspath(path)
    mdir = os.path.dirname(path)
    if mdir not in sys.path:
        sys.path.insert(0, mdir)
    spec = importlib.util.spec_from_file_location("project_build_model", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.build()
    meta = {"placements": dict(getattr(mod, "PLACEMENTS", {}) or {})}
    if isinstance(res, tuple):
        solids, pl = res[0], (res[1] if len(res) > 1 else {})
        meta["placements"].update(pl or {})
    else:
        solids = dict(res)
        pl = solids.pop("placements", None)
        if isinstance(pl, dict):
            meta["placements"].update(pl)
    for k in list(solids):
        if k.startswith("_") or isinstance(solids[k], (dict, list, tuple, str, int, float)):
            meta[k] = solids.pop(k)
    return solids, meta


# ---------------------------------------------------------------- self test ----------------------------------------
def _selftest() -> int:
    if cq is None:
        print("could not run: CadQuery is missing")
        return 2
    bad = []

    def chk(name, got, want, tol=0.02):
        ok = abs(got - want) <= tol * max(1.0, abs(want))
        print(("ok   " if ok else "FAIL ") + f"{name}: {got:.3f} (want {want:.3f})")
        if not ok:
            bad.append(name)
    chk("cyl", cyl((0, 0, 0), 4, 10).Volume(), math.pi * 4 * 10)
    chk("stadium", stadium((0, 0, 0), 10, 4, 1).Volume(), (6 * 4 + math.pi * 4) * 1)
    chk("rrect", rrect((0, 0, 0), 10, 6, 1, 1).Volume(), (60 - (4 - math.pi)))
    Ro, Ri, k = 3.0, 1.5, 1 - math.pi / 4
    area = (40 * 20 - 2 * Ro ** 2 * k) - ((40 - 3) * (20 - 1.5) - 2 * Ri ** 2 * k)
    chk("u_shell", u_shell(40, 30, 20, 1.5, 3.0).Volume(), area * 30)
    bs = bend_sector("y", (10, 10), (-1, 1), 0, 20, 1.5, 1.5)
    chk("bend_sector", bs.Volume(), math.pi / 4 * (3 ** 2 - 1.5 ** 2) * 20)
    h = hex_field((0, 0, 60, 40), 6, 3, 5, 4, forbid=[(14, 12, 20, 28)])
    chk("hex_field count", len(h), 20, tol=0)
    print("hex shift", h.shift)
    assert h.shift != (0.0, 0.0)
    s = stand((0, 0, 0), 8, "M2.5")
    print("stand volume", round(s.Volume(), 2))
    pz = print_pose(box(0, 0, 0, 10, 20, 30), "front")
    bb = pz.BoundingBox()
    chk("print_pose z", bb.zmax, 20)
    # WHICH face is down: a 3 x 3 x 1 pad on the named face must touch the bed (only the pad is within 0.5 mm of z = 0)
    pads = {"front": (3.5, -1, 13.5, 6.5, 0, 16.5), "back": (3.5, 20, 13.5, 6.5, 21, 16.5), "left": (-1, 8.5, 13.5, 0, 11.5, 16.5),
            "right": (10, 8.5, 13.5, 11, 11.5, 16.5), "bottom": (3.5, 8.5, -1, 6.5, 11.5, 0), "top": (3.5, 8.5, 30, 6.5, 11.5, 31)}
    for face, pad in pads.items():
        posed = print_pose(box(0, 0, 0, 10, 20, 30).fuse(box(*pad)).clean(), face)
        chk(f"print_pose {face}: volume within 0.5 mm of the bed", posed.intersect(box(-100, -100, 0, 100, 100, 0.5)).Volume(), 4.5)
    # D-hole: one flat by default (a circle segment), two flats with flat_side = "both"
    plate = box(0, 0, 0, 40, 2, 40)
    r, fl = 4.0, 6.0
    c = fl - r
    seg = r * r * (math.pi / 2 + math.asin(c / r)) + c * math.sqrt(r * r - c * c)
    one = panel_cutouts(plate, "front", [{"kind": "d", "u": 20, "v": 20, "d": 8, "flat": fl}], 2.0, (40, 2, 40))
    chk("D-hole, one flat", plate.Volume() - one.Volume(), 2.0 * seg)
    two = panel_cutouts(plate, "front", [{"kind": "d", "u": 20, "v": 20, "d": 8, "flat": fl, "flat_side": "both"}], 2.0, (40, 2, 40))
    chk("D-hole, two flats", plate.Volume() - two.Volume(), 2.0 * (math.pi * r * r - 2 * (r * r * math.acos((fl / 2) / r) - (fl / 2) * math.sqrt(r * r - (fl / 2) ** 2))))
    # STEP schema: AP203 by default
    import tempfile
    with tempfile.TemporaryDirectory(prefix="bt_selftest_") as d:
        tmp = os.path.join(d, "s.step")
        export_step(box(0, 0, 0, 5, 5, 5), tmp, "")
        written = step_schema(tmp)
    print("STEP schema written:", written)
    if not any("CONFIG_CONTROL_DESIGN" in s for s in written):
        bad.append("export_step schema")
    print("selftest", "FAILED: " + ", ".join(bad) if bad else "ok")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        import mech_common as mc
        mc.reexec_with_cadquery()
        sys.exit(_selftest())
    print(__doc__)
