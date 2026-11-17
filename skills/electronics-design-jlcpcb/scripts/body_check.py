"""3D check of a board: bodies inside courtyards, nothing in a mounting hole's keep-out, mated plugs clear, edge bands free.

What it checks
    A  every part's 3D body lies inside its courtyard (the body on the part's own side of the board, bounding
       boxes, tolerance settable). A courtyard that does not enclose the real body hides collisions from the
       rule check; a 3D model placed with a wrong offset shows here.
    B  no part body inside any mounting hole's keep-out cylinder (screw head, stand, screwdriver): exact distance
       between each body and the hole's axis, over the height range given in board.toml.
    C  the mated housing and cable exit of named connectors (the connector body grown and extended upward) keep
       a distance from every hole's keep-out.
    D  edge keep-out bands (a board that slides in slots or rails of its case): inside each band there is no
       part body, no courtyard, no through-hole pad and no solder joint, and no exposed copper; the nearest
       offender of each band is reported with its distance from the edge. Bands come from board.toml
       [[keepout.band]] or from the "keepouts" of mech/outline.json (see pcb_common.edge_bands).
    All four checks place things against the board's outline. When the outline cannot be built (the Edge.Cuts
    drawing is not one closed shape) every check is UNKNOWN, which is not a pass: nothing is measured against
    the box of the drawn lines.
    A, B, C and the bodies of D need CadQuery (OpenCascade) and the board's STEP file. Without CadQuery they are
    CANNOT RUN, never a pass; check D then runs on courtyards, pads and exposed copper only and says so, and
    the visual review carries the rest.

Why it exists (real failures, told without names)
    A connector's 3D model with its origin at pin 1 instead of the body centre sits millimetres off in the
    render, possibly over a mounting hole, while the 2D rule check sees nothing: its courtyard is in the right
    place. Parts inside the rail zone of a board that slides into rails jam it.

How it works
    The board is copied to a private folder. With KiCad's Python: courtyards, pads, holes, model names, the
    exposed copper inside each band (copper AND mask opening AND band, as polygons). The STEP comes from
    --step; else the STEP of mech/interface.json is taken when that file's checksums still fit the board and
    the STEP (the one of record, made by interface_export.py); else one is exported from the copy with kicad-cli
    (origin 0,0: x as in KiCad, y negated, z = 0 at the bottom face) as <out>/3d/<name>-body_check.step, so the
    STEP of record is never overwritten. Then the same script runs once more with the CadQuery Python
    (CADQUERY_PYTHON, or [tools] cadquery_python in board.toml, or this Python when it has OCP) to measure the
    solids, named by reference in the STEP. A STEP that does not match the board's outline box is refused.

Usage
    python -I body_check.py --project <hardware/board folder>           result in <project>/out/body_check.md
    python -I body_check.py <board.kicad_pcb> --out <folder> [--step <board.step>]

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [body]
    step = "out/3d/name.step"     # a STEP to use instead of exporting one (it must be of this board)
    tolerance = 0.02              # mm a body may pass its courtyard
    keepout_d = 8.0               # mm: diameter of the keep-out around every mounting hole, both sides
                                  # (not given: 2 x hole diameter + 1 mm is ASSUMED and marked as assumed)
    keepout_above = 12.0          # mm above the top face
    keepout_below = 3.0           # mm below the bottom face
    mated = ["J2", "J3"]          # connectors whose mated housing and cable exit are checked (check C)
    plug_grow = 0.3               # mm the mated housing is larger than the header body, each side
    plug_clear = 1.0              # mm between a mated housing and a hole's keep-out
    no_body = ["TP*", "FID*", "NT*", "LOGO*", "G***"]   # parts that have no body by design (mounting holes never do)
    [[keepout.band]] ...          # see pcb_common.edge_bands
    [holes] refs, min_d           # which footprints are mounting holes (see pcb_common.py)
    [tools] cadquery_python = "path/to/python"

Exit codes
    0  PASS: A, B, C (when connectors are named) and D pass
    1  FAIL: any finding; also a part with a 3D model name but no body in the STEP, or a placed part without
       any 3D model (UNKNOWN is not a pass)
       Also when the board outline cannot be built: every check is then UNKNOWN.
    2  CANNOT RUN: no CadQuery, no KiCad, unreadable board or STEP, a STEP of another board. Never a pass.
       (When check D finds something without CadQuery, the exit code is 1: a finding is a finding.)

Not checked: bodies against each other (the rule check does courtyards), the enclosure, heights against a lid
(interface_export.py gives the heights), anything a 3D model does not show (a model that is itself wrong).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import contextlib
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

DEFAULTS = {"tolerance": 0.02, "keepout_d": -1.0, "keepout_above": 12.0, "keepout_below": 3.0, "plug_grow": 0.3,
            "plug_clear": 1.0}
NO_BODY = ["TP*", "FID*", "NT*", "LOGO*", "G***"]
STAGE_TIMEOUT = 3600.0
EXPOSED_MIN_AREA = 0.01             # mm2 of exposed copper inside a band that counts


# ---- the 3D stage (runs with the CadQuery Python; needs only OCP and the standard library) ----------------------------
def stage3d(path_in: str, path_out: str) -> int:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    with open(path_in, encoding="utf-8") as f:
        d = json.load(f)
    out = {"ok": False, "error": "", "bodies": {}, "holes": [], "bands": [], "board_box": None, "offset": [0.0, 0.0]}

    def done():
        with open(path_out, "w", encoding="utf-8") as f:
            json.dump(out, f)
        return 0

    def bbox(shape):
        b = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, b, False, False)
        return None if b.IsVoid() else b.Get()

    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    if r.ReadFile(d["step"]) != IFSelect_RetDone:
        out["error"] = "the STEP file cannot be read"
        return done()
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    if roots.Length() < 1:
        out["error"] = "the STEP file holds no shape"
        return done()
    comps = TDF_LabelSequence()
    st.GetComponents_s(roots.Value(1), comps)
    shapes = {}
    for i in range(1, comps.Length() + 1):
        lab = comps.Value(i)
        n = TDataStd_Name()
        name = n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else f"?{i}"
        shapes.setdefault(name, []).append(st.GetShape_s(lab))
    refs = set(d["parts"])
    zt = d["thickness"]
    bx = d["bbox"]                                                      # KiCad frame
    # the board body: the component that is no part and whose box is the board's
    board_box = None
    for name, shs in shapes.items():
        if name in refs:
            continue
        for s in shs:
            b = bbox(s)
            if b and abs((b[3] - b[0]) - (bx[2] - bx[0])) < 0.2 and abs((b[4] - b[1]) - (bx[3] - bx[1])) < 0.2:
                board_box = b
    if board_box is None:
        out["error"] = ("no solid in the STEP has the size of the board's outline box "
                        f"({bx[2] - bx[0]:.2f} x {bx[3] - bx[1]:.2f} mm): this STEP is not of this board, or it has no board body")
        return done()
    # the STEP frame: x as KiCad, y = -KiCad y (kicad-cli with origin 0,0); another origin shows as an offset
    ox, oy = bx[0] - board_box[0], -bx[3] - board_box[1]
    oz = -board_box[2]
    out["board_box"], out["offset"] = list(board_box), [ox, oy]

    def own_side(shape, side):
        """The part of a shape on its own side of the board (its body); the whole shape if the cut fails."""
        try:
            if side == "top":
                box = BRepPrimAPI_MakeBox(gp_Pnt(-1e4, -1e4, zt - oz - 0.01), gp_Pnt(1e4, 1e4, zt - oz + 500)).Shape()
            else:
                box = BRepPrimAPI_MakeBox(gp_Pnt(-1e4, -1e4, -oz - 500), gp_Pnt(1e4, 1e4, -oz + 0.01)).Shape()
            com = BRepAlgoAPI_Common(shape, box)
            com.Build()
            if com.IsDone() and bbox(com.Shape()):
                return com.Shape()
        except Exception:                                               # noqa: BLE001  a bad model
            pass
        return shape

    solids = {}
    for ref, p in d["parts"].items():
        if ref not in shapes:
            continue
        body = [own_side(s, p["side"]) for s in shapes[ref]]
        bb = [b for b in (bbox(s) for s in body) if b]
        if not bb:
            continue
        x0, y0, x1, y1 = min(b[0] for b in bb) + ox, min(b[1] for b in bb) + oy, max(b[3] for b in bb) + ox, max(b[4] for b in bb) + oy
        z0, z1 = min(b[2] for b in bb) + oz, max(b[5] for b in bb) + oz
        height = (z1 - zt) if p["side"] == "top" else (0.0 - z0)
        fb = [b for b in (bbox(s_) for s_ in shapes[ref]) if b]            # the whole solid, whatever side it is on
        full = [min(b[0] for b in fb) + ox, -(max(b[4] for b in fb) + oy), max(b[3] for b in fb) + ox, -(min(b[1] for b in fb) + oy)]
        out["bodies"][ref] = {"box": [x0, -y1, x1, -y0], "height": height, "z": [z0, z1], "full_box": full,
                              "full_z": [min(b[2] for b in fb) + oz, max(b[5] for b in fb) + oz]}
        solids[ref] = shapes[ref]

    def rect_dist(x, y, rc):
        return math.hypot(max(rc[0] - x, 0.0, x - rc[2]), max(rc[1] - y, 0.0, y - rc[3]))

    for h in d["holes"]:
        rk = h["keepout_d"] / 2
        axis = BRepBuilderAPI_MakeEdge(gp_Pnt(h["x"] - ox, -h["y"] - oy, -h["below"] - oz),
                                       gp_Pnt(h["x"] - ox, -h["y"] - oy, zt + h["above"] - oz)).Edge()
        near = []
        for ref, b in out["bodies"].items():
            if rect_dist(h["x"], h["y"], b["box"]) > rk + 3.0:
                continue
            dist = min(BRepExtrema_DistShapeShape(s, axis).Value() for s in solids[ref])
            near.append([round(dist - rk, 4), ref])
        near.sort()
        out["holes"].append({"ref": h["ref"], "near": near[:6]})
    for band in d["bands"]:
        xs, ys = [p[0] for p in band["poly"]], [p[1] for p in band["poly"]]
        res = {"name": band["name"], "hits": []}
        for side in (("top", "bottom") if band["sides"] == "both" else (band["sides"],)):
            hgt = band["height"] if band["height"] is not None else 500.0
            z0, z1 = (zt, zt + hgt) if side == "top" else (-hgt, 0.0)
            vol = BRepPrimAPI_MakeBox(gp_Pnt(min(xs) - ox, -max(ys) - oy, z0 - oz + (0.01 if side == "top" else 0)),
                                      gp_Pnt(max(xs) - ox, -min(ys) - oy, z1 - oz - (0.01 if side == "bottom" else 0))).Shape()
            for ref, b in out["bodies"].items():
                if d["parts"][ref]["side"] != side:
                    continue
                bb = b["box"]
                if bb[2] < min(xs) - 5 or bb[0] > max(xs) + 5 or bb[3] < min(ys) - 5 or bb[1] > max(ys) + 5:
                    continue
                dist = min(BRepExtrema_DistShapeShape(s, vol).Value() for s in solids[ref])
                res["hits"].append({"ref": ref, "side": side, "dist": round(dist, 4), "box": bb})
        out["bands"].append(res)
    out["ok"] = True
    out["components"] = len(shapes)
    return done()


# ---- the 2D part of the band check (KiCad's Python) ----------------------------------------------------------------------
def bands_2d(board, info, bands):
    """Courtyards, pads and exposed copper inside each band. Returns {band name: {"rows": [...], "exposed": [...]}}."""
    import pcbnew
    res = {}
    exposed_layers = {}

    def exposed(side):
        if side not in exposed_layers:
            cu, mk = pcbnew.SHAPE_POLY_SET(), pcbnew.SHAPE_POLY_SET()
            board.ConvertBrdLayerToPolygonalContours(pcbnew.F_Cu if side == "top" else pcbnew.B_Cu, cu)
            board.ConvertBrdLayerToPolygonalContours(pcbnew.F_Mask if side == "top" else pcbnew.B_Mask, mk)
            cu.BooleanIntersection(mk)
            exposed_layers[side] = cu
        return exposed_layers[side]

    for band in bands:
        rows, exp = [], []
        sides = ("top", "bottom") if band["sides"] == "both" else (band["sides"],)
        for f in info["footprints"]:
            for side in sides:
                if f["side"] == side:
                    for poly in f["courtyard"]:
                        v = pcb_common.band_reach(band, poly[0])
                        if v is not None:
                            rows.append({"kind": "courtyard", "ref": f["ref"], "side": side, "from_edge": round(v, 3)})
                for p in f["pads"]:
                    through = bool(p["drill"]) and p["plated"]
                    on_side = ("F" if side == "top" else "B") in p["layers"]
                    if not (through or (on_side and p["kind"] in ("smd", "conn", "pth"))):
                        continue
                    b = p["box"]
                    v = pcb_common.band_reach(band, [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])])
                    if v is not None:
                        row = {"kind": "through-hole pad" if through else "pad", "ref": f"{f['ref']}.{p['num']}",
                               "side": "both" if through else side, "from_edge": round(v, 3)}
                        if row not in rows:
                            rows.append(row)
        for side in sides:
            bp = pcbnew.SHAPE_POLY_SET()
            bp.NewOutline()
            for x, y in band["poly"]:
                bp.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
            cu = pcbnew.SHAPE_POLY_SET(exposed(side))
            cu.BooleanIntersection(bp)
            area = cu.Area() / 1e12
            if area >= EXPOSED_MIN_AREA:
                spots = []
                for i in range(min(cu.OutlineCount(), 12)):
                    bb = cu.Outline(i).BBox()
                    spots.append([round(pcb_common.mm(bb.Centre().x), 2), round(pcb_common.mm(bb.Centre().y), 2)])
                exp.append({"side": side, "area": round(area, 3), "pieces": cu.OutlineCount(), "spots": spots})
        res[band["name"]] = {"rows": rows, "exposed": exp}
    return res


def find_cadquery(job) -> tuple[str | None, str]:
    """(interpreter that can import OCP, where it was found) or (None, why not)."""
    cands = []
    if os.environ.get("CADQUERY_PYTHON"):
        cands.append((os.environ["CADQUERY_PYTHON"], "CADQUERY_PYTHON"))
    t = job.cfg("tools").get("cadquery_python")
    if t:
        cands.append((job.path(t), "board.toml [tools] cadquery_python"))
    cands.append((sys.executable, "this Python"))
    why = []
    for py, src in cands:
        if not os.path.isfile(py):
            why.append(f"{src}: no such file {py}")
            continue
        try:
            r = subprocess.run([py, "-c", "import OCP.STEPCAFControl"], capture_output=True, timeout=180,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as e:
            why.append(f"{src}: {e}")
            continue
        if r.returncode == 0:
            return py, src
        why.append(f"{src}: cannot import OCP (CadQuery)")
    return None, "; ".join(why) + ". Set CADQUERY_PYTHON to the interpreter of a CadQuery environment"


def interface_step(job) -> str | None:
    """The STEP that interface_export.py made from this very board file: mech/interface.json names the checksum
    of the board and of the STEP, and both still fit. None when there is no such file or it is stale."""
    if not job.project:
        return None
    path = os.path.join(job.project, "mech", "interface.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        step = os.path.normpath(os.path.join(os.path.dirname(path), str(data["step_file"])))
        if data["board_file_sha256"] == kicad_io.sha256(job.board) and data["step_sha256"] == kicad_io.sha256(step):
            return step
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def no_outline(job, L, note: str) -> int:
    """The result when the board outline cannot be built: the bodies of the STEP are placed by the outline box and
    the edge bands are drawn from it, so every check is UNKNOWN. Nothing is measured against a guessed box."""
    why = f"the board outline could not be built ({note or 'the Edge.Cuts drawing is not a closed outline'})"
    unknown = [f"A, B, C: {why}: the 3D bodies cannot be placed against the board",
               f"D: {why}: the edge bands cannot be drawn"]
    result = pcb_common.verdict(0, len(unknown))
    md = pcb_common.header("3D body check", job, "body_check.py")
    md += ["Limits:", ""] + L.table() + [
        "", f"**Checks A, B, C and D: UNKNOWN.** {why[0].upper()}{why[1:]}. Nothing was measured: a box around the drawn lines "
        "is not the outline. Close the outline on Edge.Cuts, save, and run this check again.",
        "", "## Findings", ""] + [f"- UNKNOWN: {x}" for x in unknown] + ["", f"**Result: {result}** (0 failure(s), {len(unknown)} unknown)"]
    data = {"script": "body_check.py", "result": result, "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board),
            "step": None, "step_sha256": None, "limits": L.to_dict(), "cadquery": None, "keepout_assumed": False,
            "dnp_not_checked": [], "bodies": None, "courtyard": [], "holes": [], "mated": [], "bands": [],
            "bands_result": "UNKNOWN", "failures": [], "unknown": unknown, "crops": [], "outline_unknown": why}
    p_md, _ = pcb_common.write_result(job.out, "body_check", md, data)
    for x in unknown:
        print("UNKNOWN ", x)
    print(f"{result}: 0 bodies, 0 holes, 0 bands -> {p_md}")
    return 1


def export_step(copy: str, dst: str) -> str:
    """The board's STEP as it will be assembled: parts marked 'do not populate' have no body in it. Returns ''
    or, when kicad-cli wrote the STEP but could not add every 3D model, what it said: those parts have no body
    in the STEP (a finding of the checks, never a pass). KiCad 10 ends with an error code in that case, KiCad 9
    does not; its own library carries STEP models only, so a board that names VRML (.wrl) models gets none."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with contextlib.suppress(OSError):
        os.remove(dst)
    r = kicad_io.run_cli(["pcb", "export", "step", "--force", "--subst-models", "--no-dnp", "--user-origin", "0x0mm", "-o", dst, copy],
                         timeout=3600)
    lines = [ln.strip() for ln in (r.stdout + "\n" + r.stderr).splitlines() if ln.strip()]
    if not os.path.isfile(dst):
        raise kicad_io.KicadIOError(f"kicad-cli wrote no STEP file (exit code {r.returncode}): " + " / ".join(lines[-3:])[:600])
    lost = [ln for ln in lines if ln.startswith("Could not add 3D model")]
    if r.returncode == 0 and not lost:
        return ""
    why = next((ln for ln in lines if ln.startswith("File not found")), "")
    return (f"kicad-cli wrote the STEP with exit code {r.returncode}: {len(lost)} 3D model(s) could not be added"
            + (f" (the first: {lost[0].rstrip('.')}; {why})" if lost else "") + (f"; its last line: {lines[-1]}" if lines else "")
            + ". Those parts have no body in the STEP")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "--stage3d":
        return stage3d(argv[1], argv[2])
    ap = pcb_common.io_parser("3D check of a board: bodies in courtyards, hole keep-outs, mated plugs, edge bands.",
                              epilog="Exit codes: 0 pass, 1 findings, 2 could not run (no CadQuery is 'could not run').")
    ap.add_argument("--step", help="the board's STEP file (default: exported here from the board)")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                           # no message box, ever: warnings go to stderr
    job = pcb_common.resolve(a)
    cfg = job.cfg("body")
    L = pcb_common.Limits(cfg, DEFAULTS)
    no_body = cfg.get("no_body", NO_BODY)
    mated = list(cfg.get("mated", []))
    step_given = a.step or (job.path(cfg["step"]) if cfg.get("step") else None)
    name = os.path.splitext(os.path.basename(job.board))[0]
    with pcb_common.work_copy(job.board, "body-check-") as copy:
        board = kicad_io.load_board(copy)
        info = pcb_common.dump_board(board, os.path.dirname(job.board))
        if not info["outline"]["ok"]:
            return no_outline(job, L, info["outline"]["note"])
        bands, band_src = pcb_common.edge_bands(job, info["bbox"])
        b2d = bands_2d(board, info, bands)
        cq, cq_note = find_cadquery(job)
        if step_given:
            step = os.path.abspath(step_given)
            if not os.path.isfile(step):
                raise kicad_io.KicadIOError(f"no such STEP file: {step}")
            step_note = "given"
            if os.path.getmtime(step) < os.path.getmtime(job.board):
                step_note = "given; it is OLDER than the board file: export it again if the board changed"
        elif cq:
            step = interface_step(job)
            step_note = "the STEP of mech/interface.json (its checksums equal this board file and this STEP)"
            if not step:                        # never the STEP of record: interface_export.py owns <out>/3d/<name>.step
                step = os.path.join(job.out, "3d", name + "-body_check.step")
                said = export_step(copy, step)
                step_note = "exported here from the board copy (kicad-cli, origin 0,0)" + (". NOTE: " + said if said else "")
        else:
            step, step_note = None, "not exported (no CadQuery to read it)"
    fps = {f["ref"]: f for f in info["footprints"]}
    hole_fps = [f for f in info["footprints"] if pcb_common.is_mounting_hole(f, job.cfg("holes"))]
    assumed = L["keepout_d"] <= 0
    holes = []
    for f in hole_fps:
        dia = max((p["drill"][0] for p in f["pads"] if p["drill"]), default=0.0)
        holes.append({"ref": f["ref"], "x": f["x"], "y": f["y"], "drill": dia,
                      "keepout_d": (2 * dia + 1.0) if assumed else L["keepout_d"], "above": L["keepout_above"],
                      "below": L["keepout_below"]})
    parts = {f["ref"]: {"side": f["side"]} for f in info["footprints"] if f not in hole_fps}
    r3 = None
    if cq and step:
        with kicad_io.private_tmp("body-check-3d-") as tmp:
            p_in, p_out = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.json")
            with open(p_in, "w", encoding="utf-8") as f:
                json.dump({"step": step, "thickness": info["thickness"], "bbox": info["bbox"], "parts": parts, "holes": holes,
                           "bands": [{"name": b["name"], "poly": b["poly"], "sides": b["sides"], "height": b["height"]}
                                     for b in bands]}, f)
            try:
                r = subprocess.run([cq, "-I", "-B", os.path.abspath(__file__), "--stage3d", p_in, p_out], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=STAGE_TIMEOUT,
                                   stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                raise kicad_io.KicadIOError(f"the 3D stage did not finish in {STAGE_TIMEOUT:.0f} s") from None
            if r.returncode != 0 or not os.path.isfile(p_out):
                raise kicad_io.KicadIOError("the 3D stage failed: " + ((r.stdout or "") + (r.stderr or "")).strip()[-600:])
            with open(p_out, encoding="utf-8") as f:
                r3 = json.load(f)
        if not r3["ok"]:
            raise kicad_io.KicadIOError(f"{os.path.basename(step)}: {r3['error']}")
    # ---- results
    fails, unknown, rows_a, rows_b, rows_c = [], [], [], [], []
    md = pcb_common.header("3D body check", job, "body_check.py")
    md += ["Limits:", ""] + L.table() + [""]
    if r3 is None:
        md += [f"**Checks A, B, C and the part bodies of check D: CANNOT RUN.** {cq_note}. The visual review must carry "
               "them: look at the renders of every connector and every hole.", ""]
    else:
        bodies = r3["bodies"]
        off = r3["offset"]
        md += [f"STEP `{os.path.basename(step)}` ({step_note}), SHA-256 `{kicad_io.sha256(step)}`; {len(bodies)} part bodies; "
               f"CadQuery Python from {cq_note}." + (f" The STEP's origin differs from the board's by ({off[0]:.2f}, {off[1]:.2f}) mm; "
                                                    "that offset was applied." if abs(off[0]) + abs(off[1]) > 0.01 else ""), ""]
        dnp = sorted((r for r in parts if fps[r]["dnp"] and r not in bodies), key=pcb_common.natural)
        if dnp:
            md += [f"NOT CHECKED: {len(dnp)} part(s) marked 'do not populate' have no body in this STEP (it shows the board as it "
                   f"is assembled): {', '.join(dnp)}. If one of them is fitted later, run this check again.", ""]
        for ref in sorted(parts, key=pcb_common.natural):
            f = fps[ref]
            if ref not in bodies:
                shown = [m for m in f["models"] if m["show"]]
                if pcb_common.matches(ref, no_body) or f["board_only"]:
                    continue
                if shown and not f["dnp"]:
                    missing = [m["file"] for m in shown if not m["resolved"]]
                    why = ("3D model file not found: " + ", ".join(os.path.basename(m) for m in missing)) if missing else \
                        "its 3D model gave no body in the STEP"
                    rows_a.append((ref, f["lib"], why, "", "FAIL"))
                    fails.append(f"A: {ref}: {why}")
                elif not shown and not f["dnp"] and f["pads"]:
                    rows_a.append((ref, f["lib"], "no 3D model: body not checked", "", "UNKNOWN"))
                    unknown.append(f"A: {ref}: no 3D model")
                continue
            m = bodies[ref]["box"]
            c = f["courtyard_box"]
            if c is None:
                rows_a.append((ref, f["lib"], "no courtyard", "", "FAIL"))
                fails.append(f"A: {ref}: no courtyard")
                continue
            over = {"left": c[0] - m[0], "right": m[2] - c[2], "top": c[1] - m[1], "bottom": m[3] - c[3]}
            worst = max(over.values())
            if worst > L["tolerance"]:
                sides = ", ".join(f"{k} {v:.2f}" for k, v in over.items() if v > L["tolerance"])
                rows_a.append((ref, f["lib"], f"body past the courtyard: {sides} mm", f"{worst:.2f}", "FAIL"))
                fails.append(f"A: {ref}: body {worst:.2f} mm past its courtyard")
        md += [f"## A. Every 3D body inside its courtyard (the body on its own side of the board, tolerance {L['tolerance']} mm)", ""]
        if rows_a:
            md += ["| Reference | Footprint | Finding | Worst (mm) | Result |", "|---|---|---|---|---|"] + \
                  [f"| {' | '.join(r)} |" for r in rows_a]
        if not [r for r in rows_a if r[4] == "FAIL"]:
            md += ["", f"All {len(bodies)} bodies lie inside their courtyards: PASS."]
        ko = "2 x hole diameter + 1 mm (ASSUMED: no keepout_d in board.toml)" if assumed else f"d {L['keepout_d']:.1f} mm"
        md += ["", f"## B. Part bodies against each mounting hole's keep-out cylinder: {ko}, from {L['keepout_below']:.0f} mm "
               f"below the bottom face to {L['keepout_above']:.0f} mm above the top face", ""]
        if not holes:
            md += ["No mounting hole found (name them in board.toml [holes] refs): NOT CHECKED."]
        else:
            md += ["The nearest bodies per hole; clearance = distance to the hole's axis minus the keep-out radius.", "",
                   "| Hole | Keep-out d (mm) | Part | Clearance (mm) | Result |", "|---|---|---|---|---|"]
            for h, hr in zip(holes, r3["holes"]):
                if not hr["near"]:
                    md.append(f"| {h['ref']} | {h['keepout_d']:.1f} | (no body within 3 mm) | | PASS |")
                for clr, ref in hr["near"][:3]:
                    ok = clr >= 0
                    rows_b.append((h["ref"], ref, clr, ok))
                    md.append(f"| {h['ref']} | {h['keepout_d']:.1f} | {ref} | {clr:.2f} | {'PASS' if ok else 'FAIL'} |")
                for clr, ref in hr["near"]:
                    if clr < 0:
                        fails.append(f"B: {h['ref']}: {ref} is {-clr:.2f} mm inside the keep-out")
        md += ["", f"## C. Mated housings and cable exits (connector body + {L['plug_grow']} mm, up to {L['keepout_above']:.0f} mm) "
               f"against the keep-outs: >= {L['plug_clear']} mm", ""]
        if not mated:
            md += ["No connector is named in board.toml ([body] mated): NOT CHECKED."]
        elif not holes:
            md += ["No mounting hole: nothing to check against."]
        else:
            md += ["| Hole | Connector | Clearance (mm) | Result |", "|---|---|---|---|"]
            for ref in mated:
                if ref not in bodies:
                    md.append(f"| - | {ref} | no body in the STEP | UNKNOWN |")
                    unknown.append(f"C: {ref}: no body in the STEP")
                    continue
                m = bodies[ref]["box"]
                g = L["plug_grow"]
                env = (m[0] - g, m[1] - g, m[2] + g, m[3] + g)
                for h in holes:
                    clr = pcb_common.pt_box(h["x"], h["y"], env) - h["keepout_d"] / 2
                    if clr < 6.0:
                        ok = clr >= L["plug_clear"]
                        rows_c.append((h["ref"], ref, clr, ok))
                        md.append(f"| {h['ref']} | {ref} | {clr:.2f} | {'PASS' if ok else 'FAIL'} |")
                        if not ok:
                            fails.append(f"C: {h['ref']}: mated housing of {ref} is {clr:.2f} mm from the keep-out (< {L['plug_clear']})")
            if not rows_c:
                md.append("| - | none within 6 mm of a keep-out | | PASS |")
    # ---- D: edge bands
    md += ["", "## D. Edge keep-out bands", ""]
    band_res = []
    if not bands:
        md += ["No band is defined (board.toml [[keepout.band]] or the keepouts of mech/outline.json): NOT CHECKED."]
    else:
        md += [f"Bands from {band_src}. Distances are from the guided edge into the board; an item nearer than the band's "
               "width is inside the band." + ("" if r3 else " **Part bodies were not measured (no CadQuery): courtyards, pads "
                                              "and exposed copper only.**"), ""]
        hits3 = {b["name"]: b["hits"] for b in r3["bands"]} if r3 else {}
        for band in bands:
            w = band["width"]
            rows = list(b2d[band["name"]]["rows"])
            for h in hits3.get(band["name"], []):
                bb = h["box"]
                v = pcb_common.band_reach(band, [(bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3])])
                if v is not None:
                    rows.append({"kind": "body", "ref": h["ref"], "side": h["side"], "from_edge": round(v, 3),
                                 "inside": h["dist"] <= 1e-6})
            inside = [r for r in rows if (r["inside"] if "inside" in r else r["from_edge"] < w - 1e-6)]
            outside = [r for r in rows if r not in inside]
            exposed = b2d[band["name"]]["exposed"]
            exp_fail = bool(exposed) and not band["allow_exposed_copper"]
            ok = not inside and not exp_fail
            ln = band["line"]
            md += [f"### {band['name']}: {band['edge']} edge, ({ln[0]:.2f}, {ln[1]:.2f}) to ({ln[2]:.2f}, {ln[3]:.2f}), width {w:.2f} mm, "
                   f"sides: {band['sides']}: {'PASS' if ok else 'FAIL'}", ""]
            if inside:
                md += ["| Inside the band | Kind | Side | From the edge (mm) |", "|---|---|---|---|"]
                for r_ in sorted(inside, key=lambda r: (r["from_edge"], r["ref"])):
                    md.append(f"| {r_['ref']} | {r_['kind']} | {r_['side']} | {r_['from_edge']:.2f} |")
                    fails.append(f"D: band '{band['name']}': {r_['kind']} of {r_['ref']} ({r_['side']}) is {r_['from_edge']:.2f} mm "
                                 f"from the edge (band {w:.2f} mm)")
                md.append("")
            near = min(inside or outside, key=lambda r: r["from_edge"], default=None)
            if near:
                md.append(f"Nearest item: {near['kind']} of {near['ref']} ({near['side']}), {near['from_edge']:.2f} mm from the "
                          f"edge" + ("" if inside else f" ({near['from_edge'] - w:.2f} mm clear of the band)") + ".")
            else:
                md.append("No courtyard, pad or body along this stretch of the edge.")
            for e in exposed:
                spots = ", ".join(f"({x:.2f}, {y:.2f})" for x, y in e["spots"][:6])
                md.append(f"Exposed copper inside the band, {e['side']}: {e['area']:.2f} mm2 in {e['pieces']} piece(s), at {spots}"
                          + (" (allowed in board.toml)." if band["allow_exposed_copper"] else ": FAIL."))
                if exp_fail:
                    fails.append(f"D: band '{band['name']}': {e['area']:.2f} mm2 of exposed copper on the {e['side']} side")
            if not exposed:
                md.append("No exposed copper inside the band.")
            md.append("")
            band_res.append({"name": band["name"], "edge": band["edge"], "width": w, "sides": band["sides"], "poly": band["poly"],
                             "result": "PASS" if ok else "FAIL", "inside": inside, "nearest": near, "exposed": exposed,
                             "bodies_measured": r3 is not None})
    if fails or unknown:
        md += ["", "## Findings", ""] + [f"- FAIL: {x}" for x in fails] + [f"- UNKNOWN: {x}" for x in unknown]
    md += ["", "## Not checked", "",
           "Bodies against each other; the enclosure and lid; anything a 3D model does not show. A 3D model can itself "
           "be wrong: compare each connector's render with its datasheet drawing."
           + ("" if mated else " Check C: no connector named.") + ("" if bands else " Check D: no band defined.")]
    if r3 is None:
        result = "FAIL" if fails else "CANNOT RUN"
        code = 1 if fails else 2
    else:
        result = pcb_common.verdict(len(fails), len(unknown))
        code = 0 if result == "PASS" else 1
    md += ["", f"**Result: {result}**" + (f" ({len(fails)} failure(s), {len(unknown)} unknown)" if fails or unknown else "")]
    data = {"script": "body_check.py", "result": result, "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board),
            "step": step, "step_sha256": kicad_io.sha256(step) if step else None, "limits": L.to_dict(),
            "cadquery": cq_note if cq else None, "keepout_assumed": assumed,
            "dnp_not_checked": sorted(r for r in parts if fps[r]["dnp"] and r3 and r not in r3["bodies"]),
            "bodies": r3["bodies"] if r3 else None, "courtyard": [list(r) for r in rows_a],
            "holes": [{"hole": h, "part": p, "clearance": round(c, 3), "ok": ok} for h, p, c, ok in rows_b],
            "mated": [{"hole": h, "connector": p, "clearance": round(c, 3), "ok": ok} for h, p, c, ok in rows_c],
            "bands": band_res, "bands_result": ("NOT CHECKED" if not bands else "FAIL" if any(b["result"] == "FAIL" for b in band_res) else "PASS"),
            "failures": fails, "unknown": unknown,
            "crops": [{"name": f"band_{b['name']}", "frame": "kicad", "x": round(sum(p[0] for p in b["poly"]) / 4, 2),
                       "y": round(sum(p[1] for p in b["poly"]) / 4, 2), "size": 16.0, "why": f"edge band {b['name']}: {b['result']}"}
                      for b in band_res if b["result"] == "FAIL"]}
    p_md, _ = pcb_common.write_result(job.out, "body_check", md, data)
    for x in fails[:30]:
        print("FAIL ", x)
    for x in unknown[:10]:
        print("UNKNOWN ", x)
    if r3 is None:
        print("CANNOT RUN  checks A, B, C: " + cq_note)
    print(f"{result}: {len(r3['bodies']) if r3 else 0} bodies, {len(holes)} holes, {len(bands)} bands -> {p_md}")
    return code


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
