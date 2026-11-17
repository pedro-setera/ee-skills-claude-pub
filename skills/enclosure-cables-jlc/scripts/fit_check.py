"""Fit of a board's own STEP in the box model: interference, stands, screw heads and tool columns, connector faces, heights.

What it does
    Loads `model/build_model.py` (`build()` returns the named solids; `PLACEMENTS` or a `placements` entry says where
    each board goes), loads the board's STEP of the interface file, moves it into the box frame and REFUSES to run if
    the STEP on disk differs from the checksum in the interface file. Rows:
      FIT-INT   interference of the board's parts with every box solid (all cores)
      FIT-HOLE  each mounting hole within 0.1 mm of the axis of its stand (solid named <stand_prefix><hole name>)
      FIT-HEAD  per hole a screw-head cylinder above the board top: free of board parts and box parts
      FIT-TOOL  per hole a screwdriver column from there up to the lid opening: free of board parts and box parts
      FIT-CON   per connector of [fit.connectors.<ref>]: mating face against the wall datum (flush tolerance), and the
                gap between its body and the wall's inside (min / max)
      FIT-PLUG  per connector with `plug = [w, h, length]`: the MATED PLUG, an envelope box centred on the connector's
                mating face and reaching from the face outward along the mating direction (toward the wall), against
                every box solid and every board part (the connector's own body excepted) and the board body. Every hit
                is a failed row that names the plug, the solid and the volume. A connector that carries a cable or a
                plug (`cable = true` or `plug_required = true`, in its [fit.connectors.<ref>] table or in the interface
                file) and has no `plug` gives ONE could-not-run row "mated plug not modelled": never a pass.
      FIT-ZONE  part height above the board top, per zone, against the limit
    Every failing row says which side must change: "box" or "board".

Why it exists (the real failure, told without names)
    A connector stood inside the tool space of a mounting screw and a part sat 2 mm too tall under the lid; both were
    found by hand on the first print. The board and the box now meet in one check that reads the board's own 3D file.
    Later, the overmould of a USB-C plug, 12.5 x 6.5 mm on the maker's drawing, ran into a neighbouring part
    while every row passed: the check only compared the receptacle's face with the wall and never built the plug.

Usage
    python -I fit_check.py [--project <mech folder>] [--board NAME] [--no-hash] [--out DIR]
    --no-hash: geometry only, for a draft STEP (the row "checksum" is then could-not-run, never a pass)

Config keys (mech.toml)
    [fit] board = "board"            # key of the board in the model's placements (default: the first)
          interface = "interface.json", stand_prefix = "stand_", hole_tol = 0.1
          screw_head_d = 5.5, screw_head_h = 3.0, driver_d = 6.0
          column_top = <z>            # top of the tool column; default: the top of the box solids
          wall = 1.5                  # wall thickness for the connector gap rows
          skip = ["name*"]            # box solids that are not tested (gaskets, labels)
    [fit.zones]   general = {max = 12.0}     name = {max = 10.0, rect = [x0, y0, x1, y1]}  (rect in the interface frame)
    [fit.connectors.J2]  wall = "front"      # front|back|left|right|top|bottom of the box
          flush = 0.1, face_offset = 0.0     # mating face this far INSIDE the wall's outside face, +- flush
          gap_min = 0.0, gap_max = 0.2       # body to the wall's inside face
          plug = [12.5, 6.5, 12.0]           # mated plug envelope: width, height, length (mm); width and height lie in the
                                             #   mating face (front/back wall: x and z; left/right: y and z; top/bottom: x and y),
                                             #   the length runs from the face outward (toward the wall)
          plug_offset = [0, 0, 0]            # optional: shift of the plug's centre in the face (u, v) and along the mating
                                             #   direction (outward positive); a 2 value list shifts in the face only
          cable = true                       # or plug_required = true: the connector carries a cable or a plug, so a
                                             #   missing `plug` is a could-not-run row (the same keys may stand in the interface file)
    Placement (in the model): PLACEMENTS = {"board": {"origin": [x, y, z], "rot_z": 0, "step": "path (optional)"}}

Exit codes
    0 all rows pass   1 a row failed, or the STEP differs from the interface checksum   2 could not run
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import fnmatch
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import interface_read as ir  # noqa: E402

TOL_VOL = 0.01


def _apply_ops(shape, ops):
    import cadquery as cq
    for op in ops:
        if op[0] == "mirror_xz":
            shape = shape.mirror("XZ")
        elif op[0] == "translate":
            shape = shape.translate(cq.Vector(op[1], op[2], op[3]))
        elif op[0] == "rotate_z":
            shape = shape.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), op[1])
    return shape


def load_step(path):
    import cadquery as cq
    w = cq.importers.importStep(path)
    vals = w.vals()
    return cq.Compound.makeCompound(vals) if len(vals) > 1 else vals[0]


def _box_of(shape_list):
    xs0, ys0, zs0, xs1, ys1, zs1 = [], [], [], [], [], []
    for s in shape_list:
        b = s.BoundingBox()
        xs0.append(b.xmin); ys0.append(b.ymin); zs0.append(b.zmin); xs1.append(b.xmax); ys1.append(b.ymax); zs1.append(b.zmax)
    return min(xs0), min(ys0), min(zs0), max(xs1), max(ys1), max(zs1)


def _corners_box(f, b, z=0.0):
    """Box-frame bounding rectangle (x0, y0, x1, y1) of an interface-frame rectangle b = [x0, y0, x1, y1]."""
    p = [f(b[0], b[1], z), f(b[2], b[3], z), f(b[0], b[3], z), f(b[2], b[1], z)]
    return (min(q[0] for q in p), min(q[1] for q in p), max(q[0] for q in p), max(q[1] for q in p))


def _side(overlap_xy, itf, f):
    """Which side must change for an overlap centred at overlap_xy: inside the outline -> the box; outside -> the board."""
    r = _corners_box(f, itf["outline_box"])
    x, y = overlap_xy
    return "box" if r[0] - 0.5 <= x <= r[2] + 0.5 and r[1] - 0.5 <= y <= r[3] + 0.5 else "board (part outside its outline)"


def _carries_cable(*tables) -> bool:
    """True when any of the connector tables says the connector carries a cable or a plug."""
    return any(bool(t.get("cable")) or bool(t.get("plug_required")) for t in tables if isinstance(t, dict))


def plug_box(f, c, rule, thick):
    """The mated plug of connector `c` as a box in the box frame: (x0, y0, z0, x1, y1, z1), and its text 'w x h x l'.
    `rule` is the connector's [fit.connectors.<ref>] table (plug, plug_offset, wall). Raises ValueError with a sentence when the
    numbers are not usable. The box is centred on the connector's mating face (the face of the body box that looks at the
    wall) and reaches `length` from it outward; plug_offset = [u, v] or [u, v, w] shifts it (w along the mating direction,
    outward positive)."""
    plug = rule.get("plug")
    try:
        assert isinstance(plug, (list, tuple)) and len(plug) == 3
        w, h, ln = (float(x) for x in plug)
        assert w > 0 and h > 0 and ln > 0
    except (TypeError, ValueError, AssertionError):
        raise ValueError(f"plug must be [width, height, length] in mm, all above 0 (got {plug!r})")
    off = rule.get("plug_offset") or [0.0, 0.0, 0.0]
    try:
        assert isinstance(off, (list, tuple)) and len(off) in (2, 3)
        off = [float(x) for x in off]
    except (TypeError, ValueError, AssertionError):
        raise ValueError(f"plug_offset must be [u, v] or [u, v, along] in mm (got {rule.get('plug_offset')!r})")
    u, v, a = (off + [0.0])[:3] if len(off) == 2 else off
    wall = rule.get("wall", "front")
    r = _corners_box(f, c.get("body_box") or c["box"])
    bz = c.get("body_z")
    if bz and len(bz) == 2:
        zlo, zhi = f(0.0, 0.0, float(bz[0]))[2], f(0.0, 0.0, float(bz[1]))[2]
    elif isinstance(c.get("height"), (int, float)):
        zlo = f(0.0, 0.0, thick)[2]
        zhi = zlo + float(c["height"])
    else:
        raise ValueError(f"connector {c.get('ref')} has neither body_z nor height in the interface file: the plug cannot be placed")
    cx, cy, cz = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, (zlo + zhi) / 2
    if wall in ("front", "back"):                     # w along x, h along z
        x0, x1, z0, z1 = cx + u - w / 2, cx + u + w / 2, cz + v - h / 2, cz + v + h / 2
        if wall == "front":
            face = r[1] - a
            y0, y1 = face - ln, face
        else:
            face = r[3] + a
            y0, y1 = face, face + ln
    elif wall in ("left", "right"):                   # w along y, h along z
        y0, y1, z0, z1 = cy + u - w / 2, cy + u + w / 2, cz + v - h / 2, cz + v + h / 2
        if wall == "left":
            face = r[0] - a
            x0, x1 = face - ln, face
        else:
            face = r[2] + a
            x0, x1 = face, face + ln
    elif wall in ("top", "bottom"):                   # w along x, h along y
        x0, x1, y0, y1 = cx + u - w / 2, cx + u + w / 2, cy + v - h / 2, cy + v + h / 2
        if wall == "top":
            face = zhi + a
            z0, z1 = face, face + ln
        else:
            face = zlo - a
            z0, z1 = face - ln, face
    else:
        raise ValueError(f"wall {wall!r} is not one of front, back, left, right, top, bottom")
    return (x0, y0, z0, x1, y1, z1), f"{w:g} x {h:g} x {ln:g}"


def run(job, board_name=None, no_hash=False) -> mc.Rows:
    import cadquery as cq
    import box_toolkit as bt
    import parcheck as pc

    rows = mc.Rows()
    cfg = job.cfg
    fc = cfg.get("fit", {})
    mpath = mc.path_of(cfg, "model")
    if not os.path.isfile(mpath):
        raise mc.MechError(f"no model at {mpath}")
    solids, meta = bt.load_model(mpath)
    pls = meta.get("placements", {})
    if not pls:
        raise mc.MechError("the model gives no placements for a board (PLACEMENTS = {'board': {'origin': [x, y, z]}})")
    bname = board_name or fc.get("board") or next(iter(pls))
    if bname not in pls:
        raise mc.MechError(f"no placement named {bname!r}; the model has: {', '.join(pls)}")
    pl = pls[bname]
    ipath = rel = pl.get("interface") or fc.get("interface") or mc.path_of(cfg, "interface")
    ipath = mc.rel_to_project(cfg, ipath)
    itf = ir.load_interface(ipath)
    spath = pl.get("step")
    spath = mc.rel_to_project(cfg, spath) if spath else ir.step_path(itf)
    inputs = [mpath, ipath] + ([spath] if spath else [])
    if not spath or not os.path.isfile(spath):
        raise mc.MechError(f"the board's STEP is not at {spath}")
    rec = itf.get("step_sha256")
    now = mc.sha256(spath)
    if no_hash:
        rows.add("FIT-SHA", "fit", "board STEP is the one in the interface file", "checksum not compared (--no-hash)",
                 "checksum equal to the interface file's", "could_not_run")
    elif not rec or rec != now:
        rows.add("FIT-SHA", "fit", "board STEP is the one in the interface file",
                 "the interface file records no STEP checksum" if not rec else f"differs (STEP {now[:12]}, interface {rec[:12]})",
                 "checksum equal; if not: regenerate the interface and the STEP in the electronics skill. Board side must change.", "fail")
        rows.write(job.out, "fit_check.py", inputs)
        return rows
    else:
        rows.add("FIT-SHA", "fit", "board STEP is the one in the interface file", "equal", "checksum equal to the interface file's", "pass")

    f = ir.to_box(itf, pl)
    board = _apply_ops(load_step(spath), ir.step_transform(itf, pl))
    thick = float(itf.get("thickness") or 1.6)
    z0 = pl.get("origin", (0, 0, 0))[2]
    z_top = z0 + thick
    skip = fc.get("skip", [])
    box_shapes = {}
    for k, v in solids.items():
        s = v.val() if hasattr(v, "val") else v
        if isinstance(s, cq.Shape) and not any(fnmatch.fnmatchcase(k, p) for p in skip):
            box_shapes[k] = s
    if not box_shapes:
        raise mc.MechError("the model returned no solids")
    bx = _box_of(list(box_shapes.values()))
    col_top = float(pl.get("column_top", fc.get("column_top", bx[5])))

    # board parts: every solid except the board body (a plate of about the board thickness covering most of the outline)
    r_out = _corners_box(f, itf["outline_box"])
    out_area = (r_out[2] - r_out[0]) * (r_out[3] - r_out[1])
    parts = {}
    bodies = {}
    n_body = 0
    for i, s in enumerate(board.Solids()):
        b = s.BoundingBox()
        if abs((b.zmax - b.zmin) - thick) < 0.15 and (b.xmax - b.xmin) * (b.ymax - b.ymin) > 0.5 * out_area:
            n_body += 1
            bodies[f"bb{i}"] = s
            continue
        parts[f"bp{i}"] = s
    conns = itf.get("connectors", [])

    def part_label(name):
        b = parts[name].BoundingBox()
        cx, cy = (b.xmin + b.xmax) / 2, (b.ymin + b.ymax) / 2
        for c in conns:
            r = _corners_box(f, c.get("body_box") or c["box"])
            if r[0] - 0.3 <= cx <= r[2] + 0.3 and r[1] - 0.3 <= cy <= r[3] + 0.3:
                return c["ref"]
        return f"board part at ({cx:.1f}, {cy:.1f}, z {b.zmin:.1f}..{b.zmax:.1f})"

    # cylinders: head space and driver column per hole
    hd, hh, dd = float(fc.get("screw_head_d", 5.5)), float(fc.get("screw_head_h", 3.0)), float(fc.get("driver_d", 6.0))
    cyls, hole_pos = {}, {}
    for h in itf["holes"]:
        x, y, _ = f(h["x"], h["y"], 0.0)
        hole_pos[h["name"]] = (x, y)
        cyls["head_" + h["name"]] = cq.Solid.makeCylinder(hd / 2, hh, cq.Vector(x, y, z_top + 0.01), cq.Vector(0, 0, 1))
        top = max(col_top - (z_top + hh), 0.5)
        cyls["tool_" + h["name"]] = cq.Solid.makeCylinder(dd / 2, top, cq.Vector(x, y, z_top + hh), cq.Vector(0, 0, 1))

    # mated plugs: one envelope box per connector that has `plug = [w, h, length]`; a connector that carries a cable or a plug
    # and has none gives a could-not-run row (never a pass)
    cons_all = fc.get("connectors", {})
    plug_solids, plug_text, plug_wall, plug_rows = {}, {}, {}, []
    flagged = [c["ref"] for c in conns if _carries_cable(c)] + [r_ for r_, rl in cons_all.items() if _carries_cable(rl)]
    for ref in list(dict.fromkeys(list(cons_all) + flagged)):
        rule = cons_all.get(ref, {})
        c = next((x for x in conns if x["ref"] == ref), None)
        if c is None:
            continue                                   # the FIT-CON row for this ref says it is not in the interface file
        if rule.get("plug") is None:
            if _carries_cable(rule, c):
                plug_rows.append((ref, "could_not_run", "mated plug not modelled",
                                  f"give [fit.connectors.{ref}] plug = [width, height, length] (the maker's plug envelope): this connector carries a cable or a plug"))
            continue
        try:
            (x0, y0, z0, x1, y1, z1), txt = plug_box(f, c, rule, thick)
        except ValueError as e:
            plug_rows.append((ref, "could_not_run", f"the mated plug cannot be built: {e}", "a usable plug = [width, height, length]"))
            continue
        plug_solids[ref] = cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))
        plug_text[ref], plug_wall[ref] = txt, rule.get("wall", "front")

    # ---- interference + cylinders, all cores -------------------------------------------------------------------------
    pool_shapes = {"board": board}
    pool_shapes.update({"box:" + k: v for k, v in box_shapes.items()})
    pool_shapes.update({"part:" + k: v for k, v in parts.items()})
    pool_shapes.update({"body:" + k: v for k, v in bodies.items()})
    pool_shapes.update({"cyl:" + k: v for k, v in cyls.items()})
    pool_shapes.update({"plug:" + k: v for k, v in plug_solids.items()})
    tasks, keys = [], []
    for k in box_shapes:
        tasks.append(("board", "box:" + k, 0.0, False)); keys.append(("int", k))
    for cn in cyls:
        for pn in parts:
            tasks.append(("cyl:" + cn, "part:" + pn, 0.0, False)); keys.append(("cylpart", cn, pn))
        for k in box_shapes:
            if cn.startswith("head_") and k.startswith(fc.get("stand_prefix", "stand_")):
                continue
            tasks.append(("cyl:" + cn, "box:" + k, 0.0, False)); keys.append(("cylbox", cn, k))
    for ref in plug_solids:                            # the plug against every box solid, every board part but its own connector's, the board body
        for k in box_shapes:
            tasks.append(("plug:" + ref, "box:" + k, 0.0, False)); keys.append(("plugbox", ref, k))
        for pn in parts:
            if part_label(pn) != ref:
                tasks.append(("plug:" + ref, "part:" + pn, 0.0, False)); keys.append(("plugpart", ref, pn))
        for bn in bodies:
            tasks.append(("plug:" + ref, "body:" + bn, 0.0, False)); keys.append(("plugbody", ref, bn))
    with pc.Pool(pool_shapes) as pool:
        res = pool.map(pc.pair_task, tasks, "fit")
    inter = {}
    cyl_part = {cn: [] for cn in cyls}
    cyl_box = {cn: [] for cn in cyls}
    plug_hits = {ref: [] for ref in plug_solids}          # (what was hit, which side must change, volume)
    for key, (vol, _d, _n) in zip(keys, res):
        if vol <= TOL_VOL:
            continue
        if key[0] == "int":
            inter[key[1]] = vol
        elif key[0] == "cylpart":
            cyl_part[key[1]].append((part_label(key[2]), vol))
        elif key[0] == "plugbox":
            plug_hits[key[1]].append((f"box solid {key[2]}", "box", vol))
        elif key[0] == "plugpart":
            lbl = part_label(key[2])
            plug_hits[key[1]].append((lbl if lbl.startswith("board part") else f"{lbl} (board part)", "board", vol))
        elif key[0] == "plugbody":
            plug_hits[key[1]].append(("the board body", "board", vol))
        else:
            cyl_box[key[1]].append((key[2], vol))

    # FIT-INT: each box solid
    for i, k in enumerate(sorted(box_shapes), 1):
        v = inter.get(k, 0.0)
        if v:
            # where: centre of the overlap, to say which side must change
            try:
                ov = board.intersect(box_shapes[k])
                c = ov.Center()
                side = _side((c.x, c.y), itf, f)
            except Exception:
                side = "box"
            rows.add(f"FIT-INT-{i:02d}", "fit", f"board against {k}", f"overlap {v:.3f} mm3", f"no overlap; {side} must change", "fail")
        else:
            rows.add(f"FIT-INT-{i:02d}", "fit", f"board against {k}", "no overlap", "no overlap", "pass")

    # FIT-PLUG: the mated plug of each connector that has one; the connectors that need one and have none
    for ref in plug_solids:
        hits = sorted(plug_hits[ref], key=lambda x: (-x[2], x[0]))
        what = f"mated plug of {ref} ({plug_text[ref]} mm, from the mating face outward at the {plug_wall[ref]} wall)"
        if hits:
            for n, (name, side, vol) in enumerate(hits, 1):
                rows.add(f"FIT-PLUG-{ref}-{n:02d}", "fit", f"{what} against {name}", f"overlap {vol:.3f} mm3",
                         f"no overlap; {side} must change", "fail")
        else:
            rows.add(f"FIT-PLUG-{ref}", "fit", what + " against the box and the board", "no overlap",
                     "no overlap with any box solid, board part or the board body", "pass")
    for ref, verdict, value, rule_text in plug_rows:
        rows.add(f"FIT-PLUG-{ref}", "fit", f"mated plug of {ref}", value, rule_text, verdict)

    # FIT-HOLE
    pref = fc.get("stand_prefix", "stand_")
    tol = float(fc.get("hole_tol", 0.1))
    for h in itf["holes"]:
        nm = pref + str(h["name"])
        s = box_shapes.get(nm)
        if s is None:
            rows.add(f"FIT-HOLE-{h['name']}", "fit", f"hole {h['name']} on a stand", f"no solid named {nm} in the model",
                     f"a stand within {tol} mm; the box must add it (stands_from_interface does)", "fail")
            continue
        b = s.BoundingBox()
        cx, cy = (b.xmin + b.xmax) / 2, (b.ymin + b.ymax) / 2
        hx, hy = hole_pos[h["name"]]
        d = ((cx - hx) ** 2 + (cy - hy) ** 2) ** 0.5
        rows.add(f"FIT-HOLE-{h['name']}", "fit", f"hole {h['name']} on the axis of {nm}", f"{d:.3f} mm off",
                 f"<= {tol} mm; the box's stand must move (or the interface is old)", "pass" if d <= tol else "fail")

    # FIT-HEAD / FIT-TOOL
    for h in itf["holes"]:
        for kind, label in (("head", "screw head"), ("tool", "screwdriver column")):
            cn = f"{kind}_{h['name']}"
            bad = [f"{n} {v:.2f} mm3" for n, v in cyl_part[cn]]
            badb = [f"{n} {v:.2f} mm3" for n, v in cyl_box[cn]]
            who = ("board" if bad else "") + (" and " if bad and badb else "") + ("box" if badb else "")
            rows.add(f"FIT-{kind.upper()}-{h['name']}", "fit", f"hole {h['name']}: {label} space free",
                     ("free" if not (bad or badb) else "; ".join(["board: " + ", ".join(bad)] * bool(bad) + ["box: " + ", ".join(badb)] * bool(badb))),
                     f"d {hd if kind == 'head' else dd:g} mm free of parts" + ("" if not who else f"; {who} must change"),
                     "pass" if not (bad or badb) else "fail")

    # FIT-CON
    cons = fc.get("connectors", {})
    wall_t = float(fc.get("wall", 1.5))
    for ref, rule in cons.items():
        c = next((x for x in conns if x["ref"] == ref), None)
        if c is None:
            rows.add(f"FIT-CON-{ref}", "fit", f"connector {ref}", "not in the interface file", "the interface lists it; board side must add it", "fail")
            continue
        r = _corners_box(f, c.get("body_box") or c["box"])
        wall = rule.get("wall", "front")
        W, D, H = bx[3] - bx[0], bx[4] - bx[1], bx[5] - bx[2]
        x0, y0 = bx[0], bx[1]
        if wall == "front":
            out_pl, face, inner = y0, r[1], y0 + wall_t
            toward = lambda: r[1] - inner
        elif wall == "back":
            out_pl, face, inner = y0 + D, r[3], y0 + D - wall_t
            toward = lambda: inner - r[3]
        elif wall == "left":
            out_pl, face, inner = x0, r[0], x0 + wall_t
            toward = lambda: r[0] - inner
        elif wall == "right":
            out_pl, face, inner = x0 + W, r[2], x0 + W - wall_t
            toward = lambda: inner - r[2]
        else:
            rows.add(f"FIT-CON-{ref}", "fit", f"connector {ref}", f"wall {wall!r} not handled", "front|back|left|right", "could_not_run")
            continue
        depth_in = abs(face - out_pl)                    # mating face's distance inside the wall's outside face
        gap = toward()
        if "flush" in rule or "face_offset" in rule:
            want, tolf = float(rule.get("face_offset", 0.0)), float(rule.get("flush", 0.1))
            ok = abs(depth_in - want) <= tolf + 1e-9
            rows.add(f"FIT-CON-{ref}-FACE", "fit", f"{ref} mating face against the {wall} wall's outside face",
                     f"{depth_in:.3f} mm inside (target {want:g})", f"{want:g} +- {tolf:g} mm; the box's cut-out depth or the board's connector position must change",
                     "pass" if ok else "fail")
        if "gap_min" in rule or "gap_max" in rule:
            lo, hi = float(rule.get("gap_min", -1e9)), float(rule.get("gap_max", 1e9))
            ok = lo - 1e-9 <= gap <= hi + 1e-9
            rows.add(f"FIT-CON-{ref}-GAP", "fit", f"{ref} body to the inside of the {wall} wall", f"{gap:.3f} mm",
                     f"{lo:g} .. {hi:g} mm (box: the wall or the land; board: the connector position)", "pass" if ok else "fail")

    # FIT-ZONE
    zones = fc.get("zones", {})
    for zn, zd in zones.items():
        lim = float(zd["max"]) if isinstance(zd, dict) else float(zd)
        rect = _corners_box(f, zd["rect"]) if isinstance(zd, dict) and "rect" in zd else None
        worst, who = 0.0, ""
        for pn, s in parts.items():
            b = s.BoundingBox()
            if rect and not (b.xmin < rect[2] and b.xmax > rect[0] and b.ymin < rect[3] and b.ymax > rect[1]):
                continue
            hgt = b.zmax - z_top
            if hgt > worst:
                worst, who = hgt, part_label(pn)
        rows.add(f"FIT-ZONE-{zn}", "fit", f"part height, zone {zn}", f"{worst:.2f} mm ({who or 'no part'})",
                 f"<= {lim:g} mm above the board top; board: lower the part, or box: raise the limit", "pass" if worst <= lim + 1e-9 else "fail")
    if not zones:
        rows.add("FIT-ZONE", "fit", "part height limits", "no [fit.zones] given", "limits per zone in mech.toml", "na")
    rows.write(job.out, "fit_check.py", inputs)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fit of a board's STEP in the box model.", epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--board")
    ap.add_argument("--no-hash", action="store_true", help="skip the STEP checksum (draft STEP): the row counts as could not run")
    a = ap.parse_args(argv)
    mc.reexec_with_cadquery()
    try:
        job = mc.resolve(a)
        rows = run(job, a.board, a.no_hash)
    except (mc.MechError, KeyError) as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
