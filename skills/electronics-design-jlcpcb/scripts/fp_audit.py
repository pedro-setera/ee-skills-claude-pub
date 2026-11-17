"""Footprint audit: the numbers of every footprint for the comparison with the maker's drawing, and flags.

What it does (experimental: lighter tests than the other checks)
    For each footprint on a board (grouped: the same footprint used by several parts is one row) or in a library
    folder: number of pads, pad sizes, pitch (the smallest and the usual distance between neighbouring pads),
    drills, the box of the pads, the box of the body drawing (fabrication layer), the courtyard box, the 3D
    model with its offset, rotation and scale. The table is what a reviewer holds against the datasheet's land
    pattern: a script cannot know that a header is 2.50 mm and not 2.54 mm.
    Flags:
      no courtyard
      courtyard smaller than the pads, or smaller than the body drawing (the rule check then misses overlaps)
      no 3D model, or a 3D model file that is not found
      3D model outside the courtyard (needs CadQuery to read the model's size; without it: NOT CHECKED)
      silkscreen over pads

Why it exists (real failures, told without names)
    A library header had a 2.54 mm pitch for a 2.50 mm connector: a long connector of that series would not insert.
    Footprints converted from a distributor's library had their courtyard drawn on the body outline, smaller
    than the pads, so the courtyard check missed pad overlaps. A connector's 3D model had its origin at pin 1.
    Library silkscreen dots sat on pad 1.

Usage
    python -I fp_audit.py --project <hardware/board folder>             the board's footprints; <project>/out/fp_audit.md
    python -I fp_audit.py <board.kicad_pcb> --out <folder>
    python -I fp_audit.py --lib <folder with .kicad_mod files> [--lib ...] --out <folder> [--kiprjmod <project folder>]
    The 3D model boxes are measured when a CadQuery Python is found (CADQUERY_PYTHON, or [tools] cadquery_python).

board.toml keys (all optional)
    [fp_audit]
    tolerance = 0.01            # mm a pad or body may pass the courtyard
    no_body = ["TP*", "FID*", "NT*", "LOGO*", "G***", "H*", "MH*"]    # references that need no 3D model
    [tools] cadquery_python = "path/to/python"

Exit codes
    0  no flag;  1  at least one flag (or a check that could not be made: NOT CHECKED is not a pass);
    2  CANNOT RUN: KiCad's Python not found, unreadable board or library.

Not checked: the land pattern against the datasheet (compare the table by hand, with the drawing open), pin 1 and
polarity, paste and mask, the 3D model's shape and colour. A footprint that passes here can still be wrong.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import glob
import json
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402

DEFAULTS = {"tolerance": 0.01}
NO_BODY = ["TP*", "FID*", "NT*", "LOGO*", "G***", "H*", "MH*"]


def stage_models(path_in: str, path_out: str) -> int:
    """(CadQuery Python) Bounding boxes of STEP files: {file: [x0, y0, z0, x1, y1, z1] or None}."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    with open(path_in, encoding="utf-8") as f:
        files = json.load(f)
    out = {}
    for path in files:
        try:
            r = STEPControl_Reader()
            if r.ReadFile(path) != IFSelect_RetDone:
                out[path] = None
                continue
            r.TransferRoots()
            b = Bnd_Box()
            BRepBndLib.AddOptimal_s(r.OneShape(), b, False, False)
            out[path] = None if b.IsVoid() else list(b.Get())
        except Exception:                                               # noqa: BLE001  a model OpenCascade cannot read
            out[path] = None
    with open(path_out, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return 0


def audit_fp(fp, name, origin, kc):
    """Numbers of one footprint in its own frame (as it sits in the library: anchor at 0,0, not rotated)."""
    import pcbnew
    mm = pcbnew.ToMM
    side = pcb_common.fp_side(fp)
    lay = pcb_common.side_layers(side)
    pads, sizes, drills, centres = [], {}, {}, []
    for p in fp.Pads():
        lid = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        s = p.GetSize(lid)
        kind = {pcbnew.PAD_ATTRIB_PTH: "tht", pcbnew.PAD_ATTRIB_SMD: "smd", pcbnew.PAD_ATTRIB_NPTH: "npth"}.get(p.GetAttribute(), "other")
        key = f"{kind} {mm(s.x):.2f} x {mm(s.y):.2f}"
        sizes[key] = sizes.get(key, 0) + 1
        if p.HasHole():
            d = p.GetDrillSize()
            dk = f"{mm(d.x):.2f}" + (f" x {mm(d.y):.2f}" if d.x != d.y else "") + ("" if kind != "npth" else " unplated")
            drills[dk] = drills.get(dk, 0) + 1
        q = p.GetPosition()
        if kind != "npth":
            centres.append((mm(q.x), mm(q.y), str(p.GetNumber())))
        pads.append(pcb_common.bbox_of(p))
    pos = {}
    for x, y, n in centres:
        pos.setdefault((round(x, 3), round(y, 3)), n)
    pts = list(pos)
    nn = []
    for i, a in enumerate(pts):
        d = min((math.hypot(a[0] - b[0], a[1] - b[1]) for j, b in enumerate(pts) if j != i), default=None)
        if d is not None:
            nn.append(round(d, 2))
    usual = max(set(nn), key=nn.count) if nn else None
    pad_box = pcb_common.box_union(pads)
    body = pcb_common.fp_body_box(fp)
    cpoly, cbox = pcb_common.fp_courtyard(fp)
    silk_min = None
    err = pcbnew.FromMM(0.002)
    silk = []
    for g in fp.GraphicalItems():
        if g.GetLayer() == lay["silk"] and g.GetClass() == "PCB_SHAPE":
            ps = pcbnew.SHAPE_POLY_SET()
            g.TransformShapeToPolygon(ps, g.GetLayer(), 0, err, pcbnew.ERROR_INSIDE)
            silk += [poly[0] for poly in pcb_common.poly_points(ps) if len(poly[0]) >= 3]
    if silk:
        for p in fp.Pads():
            if not p.IsOnLayer(lay["cu"]):
                continue
            for poly in pcb_common.poly_points(p.GetEffectivePolygon(lay["cu"], pcbnew.ERROR_INSIDE)):
                pb = pcb_common.poly_box(poly[0])
                for sp in silk:
                    if pcb_common.box_gap(pb, pcb_common.poly_box(sp)) > 1.0:
                        continue
                    d = pcb_common.poly_dist(sp, poly[0])
                    silk_min = d if silk_min is None else min(silk_min, d)
    models = []
    for m in fp.Models():
        fname = str(m.m_Filename)
        unknown_prj = origin is None and "KIPRJMOD" in fname
        models.append({"file": fname, "resolved": None if unknown_prj else pcb_common._model_path(fname, origin or os.getcwd(), kc),
                       "needs_project": unknown_prj,
                       "offset": [m.m_Offset.x, m.m_Offset.y, m.m_Offset.z], "rotation": [m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z],
                       "scale": [m.m_Scale.x, m.m_Scale.y, m.m_Scale.z], "show": bool(m.m_Show)})
    a = fp.GetAttributes()
    return {"name": name, "refs": [], "pads": len(list(fp.Pads())), "sizes": sizes, "drills": drills,
            "pitch_min": min(nn) if nn else None, "pitch_usual": usual, "pad_box": pad_box, "body": body, "courtyard": cbox,
            "silk_to_pad": silk_min, "models": models, "anchor": (mm(fp.GetPosition().x), mm(fp.GetPosition().y)),
            "virtual": bool(a & (pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY))}


def rel_box(b, anchor):
    return None if b is None else [b[0] - anchor[0], b[1] - anchor[1], b[2] - anchor[0], b[3] - anchor[1]]


def fmt_box(b):
    return "-" if b is None else f"{b[2] - b[0]:.2f} x {b[3] - b[1]:.2f}"


def over(inner, outer):
    """How far the box `inner` passes the box `outer` (mm; 0 or less: inside)."""
    return max(outer[0] - inner[0], outer[1] - inner[1], inner[2] - outer[2], inner[3] - outer[3])


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "--stage-models":
        return stage_models(argv[1], argv[2])
    ap = pcb_common.io_parser("Footprint audit: pads, pitch, drills, courtyard, 3D model of every footprint, with flags.",
                              epilog="Exit codes: 0 no flag, 1 flags, 2 could not run.")
    ap.add_argument("--lib", action="append", help="a folder of .kicad_mod files to audit instead of a board (repeatable)")
    ap.add_argument("--kiprjmod", help="with --lib: the KiCad project folder that ${KIPRJMOD} in 3D model paths stands for")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                           # no message box, ever: warnings go to stderr
    import pcbnew
    job = pcb_common.resolve(a, need_board=not a.lib)
    cfg = job.cfg("fp_audit")
    L = pcb_common.Limits(cfg, DEFAULTS)
    tol = L["tolerance"]
    no_body = cfg.get("no_body", NO_BODY)
    kc = kicad_io.find_kicad()
    rows = []
    if a.lib:
        source = "libraries " + ", ".join(os.path.basename(os.path.normpath(p)) for p in a.lib)
        for lib in a.lib:
            lib = os.path.abspath(lib)
            mods = sorted(glob.glob(os.path.join(glob.escape(lib), "*.kicad_mod"))) + \
                sorted(glob.glob(os.path.join(glob.escape(lib), "*", "*.kicad_mod")))
            if not mods:
                raise kicad_io.KicadIOError(f"{lib}: no .kicad_mod file (give a .pretty folder or a folder of them)")
            for m in mods:
                d, n = os.path.dirname(m), os.path.splitext(os.path.basename(m))[0]
                try:
                    fp = pcbnew.FootprintLoad(d, n)
                except Exception as e:                                  # noqa: BLE001
                    fp, why = None, str(e)
                if fp is None:
                    rows.append({"name": n, "refs": [], "error": "KiCad could not load this footprint"})
                    continue
                r = audit_fp(fp, os.path.basename(d).replace(".pretty", "") + ":" + n,
                             os.path.abspath(a.kiprjmod) if a.kiprjmod else None, kc)
                for k in ("pad_box", "body", "courtyard"):
                    r[k] = rel_box(r[k], r["anchor"])
                rows.append(r)
    else:
        source = "board " + os.path.basename(job.board)
        with pcb_common.work_copy(job.board, "fp-audit-") as copy:
            board = kicad_io.load_board(copy)
            groups = {}
            for fp in sorted(board.GetFootprints(), key=lambda f: pcb_common.natural(f.GetReference())):
                ref = fp.GetReference()
                c = pcbnew.FOOTPRINT(fp)                               # a copy, turned back to the library's pose
                if hasattr(c, "SetParentGroup"):
                    c.SetParentGroup(None)                             # a copy must not claim the original's group
                if c.IsFlipped():
                    c.Flip(c.GetPosition(), getattr(pcbnew, "FLIP_DIRECTION_LEFT_RIGHT", False))
                c.SetOrientationDegrees(0)
                r = audit_fp(c, fp.GetFPID().GetUniStringLibId(), os.path.dirname(job.board), kc)
                for k in ("pad_box", "body", "courtyard"):
                    r[k] = rel_box(r[k], r["anchor"])
                key = json.dumps([r["name"], r["sizes"], r["drills"], r["pad_box"] and [round(v, 3) + 0.0 for v in r["pad_box"]],
                                  r["courtyard"] and [round(v, 3) + 0.0 for v in r["courtyard"]], [m["file"] for m in r["models"]],
                                  [m["offset"] for m in r["models"]], [m["rotation"] for m in r["models"]]], sort_keys=True)
                if key in groups:
                    groups[key]["refs"].append(ref)
                else:
                    r["refs"] = [ref]
                    groups[key] = r
            rows = list(groups.values())
    # ---- the 3D model boxes (optional)
    cq, cq_note, boxes = None, "", {}
    files = sorted({m["resolved"] for r in rows for m in r.get("models", []) if m["resolved"] and m["resolved"].lower().endswith((".step", ".stp"))})
    if files:
        import body_check
        cq, cq_note = body_check.find_cadquery(job)
        if cq:
            with kicad_io.private_tmp("fp-audit-") as tmp:
                p_in, p_out = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.json")
                with open(p_in, "w", encoding="utf-8") as f:
                    json.dump(files, f)
                try:
                    r_ = subprocess.run([cq, "-I", "-B", os.path.abspath(__file__), "--stage-models", p_in, p_out], capture_output=True,
                                        text=True, timeout=3600, stdin=subprocess.DEVNULL)
                    if r_.returncode == 0 and os.path.isfile(p_out):
                        with open(p_out, encoding="utf-8") as f:
                            boxes = json.load(f)
                    else:
                        cq, cq_note = None, "the CadQuery stage failed: " + ((r_.stdout or "") + (r_.stderr or "")).strip()[-300:]
                except subprocess.TimeoutExpired:
                    cq, cq_note = None, "the CadQuery stage did not finish"
    # ---- flags
    n_flags = n_unchecked = 0
    for r in rows:
        flags, notes = [], []
        if "error" in r:
            r["flags"], r["notes"] = [r["error"]], []
            n_flags += 1
            continue
        refs = r["refs"]
        needs_body = not r["virtual"] and not (refs and all(pcb_common.matches(x, no_body) for x in refs)) and \
            not r["name"].lower().startswith(("mountinghole", "testpoint", "fiducial"))
        c = r["courtyard"]
        if c is None:
            (flags if needs_body else notes).append("no courtyard")
        else:
            if r["pad_box"] is not None and over(r["pad_box"], c) > tol:
                flags.append(f"courtyard smaller than the pads by {over(r['pad_box'], c):.2f} mm")
            if r["body"] is not None and over(r["body"], c) > tol:
                flags.append(f"courtyard smaller than the body drawing by {over(r['body'], c):.2f} mm")
        if r["body"] is None:
            notes.append("no body drawing on the fabrication layer")
        shown = [m for m in r["models"] if m["show"]]
        if not shown:
            (flags if needs_body else notes).append("no 3D model")
        for m in shown:
            if m.get("needs_project"):
                notes.append("3D model path is relative to the project (${KIPRJMOD}): not looked up; give --kiprjmod")
                n_unchecked += 1
                continue
            if not m["resolved"]:
                flags.append(f"3D model file not found: {os.path.basename(m['file'])}")
                continue
            if c is None:
                continue
            box = boxes.get(m["resolved"])
            rx, ry, rz = m["rotation"]
            if abs(rx) > 1e-6 or abs(ry) > 1e-6:
                notes.append("3D model is rotated about x or y: its box against the courtyard was not measured")
                n_unchecked += 1
            elif box:
                sx, sy = m["scale"][0], m["scale"][1]
                ox, oy = m["offset"][0], m["offset"][1]
                corners = [(box[0] * sx, box[1] * sy), (box[3] * sx, box[1] * sy), (box[3] * sx, box[4] * sy), (box[0] * sx, box[4] * sy)]
                outs = []
                for sign in ((1,) if abs(rz) % 180 < 1e-6 else (1, -1)):      # the sense of a model's z rotation: both tried
                    t = math.radians(sign * rz)
                    pts = [(x * math.cos(t) - y * math.sin(t) + ox, x * math.sin(t) + y * math.cos(t) + oy) for x, y in corners]
                    mb = [min(q[0] for q in pts), -max(q[1] for q in pts), max(q[0] for q in pts), -min(q[1] for q in pts)]   # model y up, footprint y down
                    outs.append((over(mb, c), mb))
                m["box"] = [round(v, 3) for v in outs[0][1]]
                worst, mb = max(outs, key=lambda q: q[0])
                if min(q[0] for q in outs) > max(tol, 0.02):
                    flags.append(f"3D model outside the courtyard by {worst:.2f} mm (model box {mb[2] - mb[0]:.2f} x {mb[3] - mb[1]:.2f} "
                                 f"at offset ({ox:g}, {oy:g}), rotation {rz:g})")
                elif worst > max(tol, 0.02):
                    notes.append(f"3D model rotated by {rz:g}: inside the courtyard for one sense of rotation only; look at the render")
                    n_unchecked += 1
            else:
                notes.append("3D model box not measured" + ("" if cq else " (no CadQuery)") + ("" if m["resolved"].lower().endswith((".step", ".stp")) else " (not a STEP file)"))
                n_unchecked += 1
        if r["silk_to_pad"] is not None and r["silk_to_pad"] <= 1e-6:
            flags.append("silkscreen over pads")
        r["flags"], r["notes"] = flags, notes
        n_flags += len(flags)
    md = pcb_common.header("Footprint audit", job, "fp_audit.py") if job.board else \
        ["# Footprint audit", "", f"Script `fp_audit.py`; {source}; settings: {job.source_note}.", ""]
    md += [f"{len(rows)} footprints from {source}. Sizes in mm, each footprint in its own frame (not rotated). Compare every row "
           "with the maker's land pattern, with the drawing open: this table does not know the datasheet.", "",
           ("3D model boxes measured with CadQuery (" + cq_note + ")." if cq else
            "3D model boxes NOT measured" + (": " + cq_note if cq_note else " (no STEP model to measure)") + "."), "",
           "| Footprint | Used by | Pads | Pad sizes (count) | Pitch: smallest / usual | Drills (count) | Pads box | Body box | Courtyard box | "
           "Silk to pad | 3D model: offset, rotation, scale | Flags |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            md.append(f"| {r['name']} | | | | | | | | | | | **{r['error']}** |")
            continue
        refs = ", ".join(r["refs"][:12]) + (f" ... ({len(r['refs'])})" if len(r["refs"]) > 12 else "")
        sizes = "; ".join(f"{k} ({v})" for k, v in r["sizes"].items())
        drills = "; ".join(f"{k} ({v})" for k, v in r["drills"].items()) or "-"
        pitch = "-" if r["pitch_min"] is None else f"{r['pitch_min']:.2f} / {r['pitch_usual']:.2f}"
        mods = "; ".join(f"{os.path.basename(m['file'])}: ({m['offset'][0]:g}, {m['offset'][1]:g}, {m['offset'][2]:g}), "
                         f"({m['rotation'][0]:g}, {m['rotation'][1]:g}, {m['rotation'][2]:g}), ({m['scale'][0]:g}, {m['scale'][1]:g}, {m['scale'][2]:g})"
                         + ("" if m["resolved"] else " NOT FOUND") for m in r["models"]) or "none"
        silk = "-" if r["silk_to_pad"] is None else f"{r['silk_to_pad']:.2f}"
        fl = "; ".join(f"**{f}**" for f in r["flags"]) + (("; " if r["flags"] else "") + "; ".join("note: " + n for n in r["notes"]) if r["notes"] else "")
        md.append(f"| {r['name']} | {refs or '-'} | {r['pads']} | {sizes or '-'} | {pitch} | {drills} | {fmt_box(r['pad_box'])} | {fmt_box(r['body'])} | "
                  f"{fmt_box(r['courtyard'])} | {silk} | {mods} | {fl or 'none'} |")
    flagged = [r for r in rows if r["flags"]]
    md += ["", f"## Flags: {n_flags} on {len(flagged)} of {len(rows)} footprints", ""]
    md += [f"- {r['name']}" + (f" ({', '.join(r['refs'][:8])}{' ...' if len(r['refs']) > 8 else ''})" if r["refs"] else "") + ": " + "; ".join(r["flags"])
           for r in flagged] or ["None."]
    result = "PASS" if n_flags == 0 and n_unchecked == 0 else ("FAIL" if n_flags else "FAIL (NOT CHECKED items are not a pass)")
    md += ["", "## Not checked", "",
           "The land pattern against the maker's drawing (pitch, pad size, drill, pin 1): compare the table by hand. Paste and "
           "mask. The 3D model's shape." + (f" {n_unchecked} 3D model box(es) could not be measured." if n_unchecked else ""),
           "", f"**Result: {result}** ({n_flags} flag(s), {n_unchecked} model box(es) not measured)"]
    data = {"script": "fp_audit.py", "result": result, "source": source, "limits": L.to_dict(), "cadquery": cq_note if cq else None,
            "footprints": rows}
    p_md, _ = pcb_common.write_result(job.out, "fp_audit", md, data)
    for r in flagged[:40]:
        print(f"FLAG  {r['name']}: " + "; ".join(r["flags"]))
    print(f"{result}: {len(rows)} footprints, {n_flags} flag(s) -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
