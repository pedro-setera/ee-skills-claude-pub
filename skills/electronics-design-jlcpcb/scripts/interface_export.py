"""Mechanical interface of a board in one generated file: outline, holes, connectors, named parts, heights,
with the checksums of the board file and of the exported STEP. Also exports the STEP.

What it does (experimental: lighter tests than the other checks)
    From the saved board (a private copy is read): the outline box and polygon, the board thickness, every
    mounting hole (position, drill, plated or not, net), every connector and every part named in board.toml
    (position, side, rotation, "box" of pads and body drawing, "body_box" of its whole 3D solid with whatever
    hangs over the board edge, "body_z" from the bottom face, "height" above its own side of the board), the
    tallest part per side and per named zone. It exports the board's STEP with kicad-cli (origin 0,0: x as in KiCad, y negated, z = 0 at the
    bottom face) and writes one JSON that carries the SHA-256 of the board file and of that STEP. The enclosure
    design reads only this file. With --check it tells whether an existing interface file still belongs to the
    board and the STEP on disk.

Why it exists (the real failure, told without names)
    The numbers of a board (hole positions, a connector's mating face, the tallest part) were typed by hand
    into the enclosure model and drifted from the board over several layout rounds. One generated file with
    both checksums ends that: a stale file is visible at once.

Usage
    python -I interface_export.py --project <hardware/board folder>     -> <project>/mech/interface.json,
                                                                           <project>/out/3d/<board>.step,
                                                                           <project>/out/interface_export.md
    python -I interface_export.py <board.kicad_pcb> --out <folder>      -> <folder>/interface.json, <folder>/3d/
    python -I interface_export.py --project <...> --check               compare the checksums only
    options: --no-heights (do not measure 3D bodies), --compare <other interface.json> (outline and holes equal?)
    Heights need a CadQuery Python (CADQUERY_PYTHON or [tools] cadquery_python); without it they are null and
    the exit code is 1 unless --no-heights is given.

board.toml keys (all optional)
    [interface]
    origin = "top-left"        # corner of the outline box that is (0, 0): "top-left" (KiCad's sense, y down) or
                               # "bottom-left" (y up, as most enclosure drawings)
    offset = [0.0, 0.0]        # added to every x, y: the board's place in the enclosure's frame
    frame = "text"             # a description of that frame, copied into the file
    parts = ["LED1", "SW*"]    # further parts to list (LEDs, switches); connectors are always listed
    [interface.zones]          # named areas (in the output frame): the tallest part of each is reported
    under_lid = [0.0, 0.0, 30.0, 20.0]
    [holes] refs, min_d; [connectors] refs       see pcb_common.py

Exit codes
    0  written, complete (or --check: the checksums agree)
    1  written but heights could not be measured, or the STEP lacks 3D models that kicad-cli could not add; or
       NOT written, result UNKNOWN: the board outline could not be built (the file's frame starts at its box);
       --check: the file is stale; --compare: a difference
    2  CANNOT RUN: KiCad not found, unreadable board, STEP export failed, no file to check
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import datetime
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
import body_check  # noqa: E402


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Mechanical interface of a board as one JSON with board and STEP checksums; exports the STEP.",
                              epilog="Exit codes: 0 complete, 1 incomplete or stale, 2 could not run.")
    ap.add_argument("--check", action="store_true", help="only compare an existing interface file with the board and STEP on disk")
    ap.add_argument("--no-heights", action="store_true", dest="no_heights", help="do not measure 3D bodies (no CadQuery needed)")
    ap.add_argument("--compare", help="another interface JSON: report differences of outline and holes")
    a = ap.parse_args(argv)
    job = pcb_common.resolve(a)
    cfg = job.cfg("interface")
    name = os.path.splitext(os.path.basename(job.board))[0]
    p_json = os.path.join(job.project, "mech", "interface.json") if job.project else os.path.join(job.out, "interface.json")
    p_step = os.path.join(job.out, "3d", name + ".step")
    board_sha = kicad_io.sha256(job.board)
    if a.check:
        if not os.path.isfile(p_json):
            raise kicad_io.KicadIOError(f"no interface file to check: {p_json}")
        with open(p_json, encoding="utf-8") as f:
            old = json.load(f)
        rows = [("board file", old.get("board_file_sha256"), board_sha)]
        step = os.path.join(os.path.dirname(p_json), old.get("step_file", "")) if old.get("step_file") else p_step
        step = step if os.path.isfile(step) else p_step
        rows.append(("STEP file", old.get("step_sha256"), kicad_io.sha256(step) if os.path.isfile(step) else "(no STEP file on disk)"))
        ok = all(x == y for _, x, y in rows)
        md = pcb_common.header("Interface file against the saved board", job, "interface_export.py --check")
        md += ["| File | Checksum in the interface file | Checksum on disk | Result |", "|---|---|---|---|"]
        md += [f"| {n} | `{x}` | `{y}` | {'PASS' if x == y else 'FAIL: stale'} |" for n, x, y in rows]
        md += ["", f"**Result: {'PASS' if ok else 'FAIL'}**" + ("" if ok else ": run interface_export.py again and give the enclosure the new file")]
        pcb_common.write_result(job.out, "interface_export", md, {"script": "interface_export.py --check", "result": "PASS" if ok else "FAIL",
                                                                   "rows": [{"file": n, "recorded": x, "on_disk": y} for n, x, y in rows]})
        print(("PASS" if ok else "FAIL") + ": interface file " + ("matches" if ok else "does NOT match") + " the board and STEP on disk")
        return 0 if ok else 1
    kicad_io.require_kicad()
    origin = cfg.get("origin", "top-left")
    if origin not in ("top-left", "bottom-left"):
        raise kicad_io.KicadIOError('[interface] origin must be "top-left" or "bottom-left"')
    off = [float(v) for v in cfg.get("offset", [0.0, 0.0])]
    notes = []
    with pcb_common.work_copy(job.board, "interface-export-") as copy:
        info = pcb_common.read_board(copy, os.path.dirname(job.board))
        if not info["outline"]["ok"]:           # every number of the file is counted from the outline box: none is written
            why = f"the board outline could not be built ({info['outline']['note'] or 'the Edge.Cuts drawing is not a closed outline'})"
            md = pcb_common.header("Mechanical interface export", job, "interface_export.py")
            md += [f"**Result: UNKNOWN (not a pass).** {why[0].upper()}{why[1:]}. The frame of the interface file starts at a corner "
                   "of the outline box, so no interface file and no STEP were written: a box around the drawn lines is not the "
                   "outline. Close the outline on Edge.Cuts, save, and run this again."]
            pcb_common.write_result(job.out, "interface_export", md, {"script": "interface_export.py", "result": "UNKNOWN",
                                                                       "interface": None, "step": None, "differences": [], "notes": [why]})
            print(f"UNKNOWN (not a pass): {why}; no interface file was written")
            return 1
        step_said = body_check.export_step(copy, p_step)
        if step_said:
            notes.append("the STEP is incomplete: " + step_said + "; their heights are missing")
        bb = info["bbox"]

        def tx(x, y):
            return (round(x - bb[0] + off[0], 4), round((y - bb[1] if origin == "top-left" else bb[3] - y) + off[1], 4))

        def tbox(b):
            (x0, y0), (x1, y1) = tx(b[0], b[1]), tx(b[2], b[3])
            return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

        holes_fp = [f for f in info["footprints"] if pcb_common.is_mounting_hole(f, job.cfg("holes"))]
        bodies, heights_ok = {}, False
        if not a.no_heights:
            cq, cq_note = body_check.find_cadquery(job)
            if not cq:
                notes.append("heights not measured: " + cq_note)
            else:
                with kicad_io.private_tmp("interface-export-3d-") as tmp:
                    p_in, p_out = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.json")
                    with open(p_in, "w", encoding="utf-8") as f:
                        json.dump({"step": p_step, "thickness": info["thickness"], "bbox": info["bbox"], "holes": [], "bands": [],
                                   "parts": {f["ref"]: {"side": f["side"]} for f in info["footprints"] if f not in holes_fp}}, f)
                    try:
                        r = subprocess.run([cq, "-I", "-B", os.path.join(_HERE, "body_check.py"), "--stage3d", p_in, p_out],
                                           capture_output=True, text=True, timeout=body_check.STAGE_TIMEOUT, stdin=subprocess.DEVNULL)
                    except subprocess.TimeoutExpired:
                        r = None
                    if r is not None and r.returncode == 0 and os.path.isfile(p_out):
                        with open(p_out, encoding="utf-8") as f:
                            r3 = json.load(f)
                        if r3["ok"]:
                            bodies, heights_ok = r3["bodies"], True
                            for f in info["footprints"]:               # height: the top of the whole solid over its own face
                                b = bodies.get(f["ref"])
                                if b:
                                    b["height"] = (b["full_z"][1] - info["thickness"]) if f["side"] == "top" else -b["full_z"][0]
                        else:
                            notes.append("heights not measured: " + r3["error"])
                    else:
                        notes.append("heights not measured: the 3D stage failed")
    holes = []
    for f in holes_fp:
        p = max((q for q in f["pads"] if q["drill"]), key=lambda q: q["drill"][0])
        x, y = tx(f["x"], f["y"])
        holes.append({"name": f["ref"], "x": x, "y": y, "d": round(p["drill"][0], 4), "plated": p["plated"], "net": p["net"] or None})

    def part(f):
        x, y = tx(f["x"], f["y"])
        b = bodies.get(f["ref"])
        return {"ref": f["ref"], "value": f["value"], "side": f["side"], "x": x, "y": y, "rotation": f["rot"], "box": tbox(f["box"]),
                "body_box": tbox(b["full_box"]) if b else None, "body_z": [round(v, 3) for v in b["full_z"]] if b else None,
                "height": round(b["height"], 3) if b else None}

    conns = [part(f) for f in info["footprints"] if pcb_common.is_connector(f, job.cfg("connectors")) and f not in holes_fp]
    named = [part(f) for f in info["footprints"] if cfg.get("parts") and pcb_common.matches(f["ref"], cfg["parts"])
             and not pcb_common.is_connector(f, job.cfg("connectors"))]
    tallest = {}
    if heights_ok:
        side_of = {f["ref"]: f["side"] for f in info["footprints"]}
        for side in ("top", "bottom"):
            c = [(b["height"], ref) for ref, b in bodies.items() if side_of[ref] == side]
            if c:
                h, ref = max(c)
                tallest[side] = {"ref": ref, "height": round(h, 3)}
        for zname, zb in (cfg.get("zones") or {}).items():
            c = []
            for ref, b in bodies.items():
                tb = tbox(b["box"])
                if tb[0] < zb[2] and tb[2] > zb[0] and tb[1] < zb[3] and tb[3] > zb[1]:
                    c.append((b["height"], ref))
            tallest[zname] = {"ref": max(c)[1], "height": round(max(c)[0], 3), "zone": list(zb)} if c else {"ref": None, "height": 0.0, "zone": list(zb)}
    outline = [[list(tx(x, y)) for x, y in loop] for poly in info["outline"]["polygons"] for loop in poly]
    rel = (lambda p: os.path.relpath(p, os.path.dirname(p_json)).replace(os.sep, "/"))
    data = {"generated_by": "interface_export.py", "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "board_file": rel(job.board), "board_file_sha256": board_sha, "step_file": rel(p_step), "step_sha256": kicad_io.sha256(p_step),
            "kicad": info["kicad"], "units": "mm",
            "frame": {"description": cfg.get("frame", ""), "origin": origin + " corner of the outline box", "y": "down" if origin == "top-left" else "up",
                      "offset": off, "kicad_origin_in_this_frame": list(tx(0.0, 0.0))},
            "outline_box": tbox(bb), "size": [round(bb[2] - bb[0], 4), round(bb[3] - bb[1], 4)], "outline": outline,
            "thickness": info["thickness"], "copper_layers": len(info["copper_layers"]), "holes": holes, "connectors": conns, "parts": named,
            "heights_measured": heights_ok, "tallest_part": tallest, "notes": notes}
    os.makedirs(os.path.dirname(p_json), exist_ok=True)
    kicad_io.atomic_write(p_json, json.dumps(pcb_common.scrub(data), indent=1, ensure_ascii=False) + "\n")
    diffs = []
    if a.compare:
        with open(a.compare, encoding="utf-8") as f:
            other = json.load(f)
        other = other.get("interface", other)
        ob = other.get("outline_box")
        if ob and any(abs(x - y) > 0.011 for x, y in zip(ob, data["outline_box"])):
            diffs.append(f"outline box {data['outline_box']} against {ob}")
        oh = {h["name"]: h for h in other.get("holes", [])}
        for h in holes:
            o = oh.get(h["name"])
            if o is None:
                diffs.append(f"hole {h['name']} is not in the other file")
            elif abs(o["x"] - h["x"]) > 0.011 or abs(o["y"] - h["y"]) > 0.011 or abs(o["d"] - h["d"]) > 0.011:
                diffs.append(f"hole {h['name']}: ({h['x']}, {h['y']}) d {h['d']} against ({o['x']}, {o['y']}) d {o['d']}")
        diffs += [f"hole {n} of the other file is not on the board" for n in oh if n not in {h["name"] for h in holes}]
    incomplete = (not heights_ok and not a.no_heights)
    result = "FAIL" if diffs else ("FAIL (heights not measured)" if incomplete else
                                   ("FAIL (the STEP lacks 3D models: heights are incomplete)" if step_said and not a.no_heights else "PASS"))
    holes_txt = "; ".join(f"{h['name']} ({h['x']}, {h['y']}) d {h['d']}" for h in holes) or "-"
    md = pcb_common.header("Mechanical interface export", job, "interface_export.py")
    md += [f"Interface file `{p_json}`; STEP `{p_step}`, SHA-256 `{data['step_sha256']}`.", "",
           f"Frame: origin at the {origin} corner of the outline box, y {'down' if origin == 'top-left' else 'up'}, offset {off}. "
           f"Outline box {data['outline_box']}, {data['size'][0]:.2f} x {data['size'][1]:.2f} mm, thickness {info['thickness']:.2f} mm.", "",
           "| Item | Count | Detail |", "|---|---|---|",
           f"| Mounting holes | {len(holes)} | {holes_txt} |",
           f"| Connectors | {len(conns)} | {'; '.join(c['ref'] + (' h ' + format(c['height'], '.2f') if c['height'] is not None else '') for c in conns) or '-'} |",
           f"| Named parts | {len(named)} | {'; '.join(c['ref'] for c in named) or '-'} |",
           f"| Tallest part | | {'; '.join(k + ': ' + str(v['ref']) + ' ' + format(v['height'], '.2f') + ' mm' for k, v in tallest.items()) or 'not measured'} |", ""]
    md += [f"- note: {n}" for n in notes]
    md += [f"- DIFFERENT from `{os.path.basename(a.compare)}`: {d}" for d in diffs]
    md += ["", f"**Result: {result}**"]
    pcb_common.write_result(job.out, "interface_export", md, {"script": "interface_export.py", "result": result, "interface": p_json,
                                                               "step": p_step, "differences": diffs, "notes": notes})
    for n in notes + diffs:
        print("note:", n)
    print(f"{result}: {len(holes)} holes, {len(conns)} connectors, heights {'measured' if heights_ok else 'not measured'} -> {p_json}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
