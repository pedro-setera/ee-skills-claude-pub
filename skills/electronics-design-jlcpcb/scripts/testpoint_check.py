"""Test points: sized and placed for the probe, every listed net covered, one side for a fixture; and the table.

What it checks (board stage; on the SAVED board, read from a private copy)
    A test point is every footprint whose reference starts with a prefix of `prefix` (default TP), and every pad
    named in board.toml as [[testpoints.pad]] (a pad used in place of a point: rule DFM-94). Per point:
      pad         its smaller dimension (less what a smaller mask opening hides): FAIL under pad_min, a note under
                  pad_good; the solder mask open (FAIL when not); no paste on a pad that gets no part (FAIL)
      pitch       centre to centre to the nearest other test point of the same side: FAIL under pitch_min, a note
                  under pitch_good (FAIL for a fixture point)
      bodies      from the pad to the nearest other footprint of the same side: FAIL under body_clear (for a pad
                  named in board.toml, which sits among its part's neighbours, a note). Measured to
                  the part's 3D body when body_check.json of the same board state is in the results folder, else
                  to its courtyard (the strict reading: a courtyard is larger than the body), else to the box of
                  its pads and drawing; the row says which
      tall parts  from the pad to the nearest part taller than tall_part: FAIL under tall_clear (for a fixture
                  point: under fixture_tall_clear). Heights come from body_check.json of the same board state (in
                  the results folder), else from [heights] of board.toml; a part within that clearance whose
                  height is not known makes the row UNKNOWN, never a guess (a footprint where nothing is fitted,
                  a hole, a mark, a bare pad, has no height)
      edge        from the pad to the board outline (FAIL under edge_clear for a fixture point; else reported)
      label       a silkscreen text of its side that holds its reference within label_within (a note when not;
                  silk_check.py judges the labels)
      ground      centre to centre to the nearest ground test point (a note beyond ground_within)
    Coverage: every net of `required` (names or patterns) has a point or a named pad, else FAIL naming the net.
      Without the list coverage is UNKNOWN (never PASS), and every net with two or more pads that has neither a
      point nor a pad a probe can hold (a through-hole pad, or a surface pad whose smaller side is probe_pad or
      more: a rule of thumb) is listed as a note. At least one ground point, else FAIL; when every ground point
      is a bare pad: a note "no ground point that a clip can hold".
    Fixture (rule DFM-98): fixture = true: every fixture point on fixture_side, at pitch_good or more, edge_clear
      from the edge, fixture_tall_clear from tall parts; two unplated holes at least half the board's diagonal
      apart, and fixture_hole_clear free of parts round each of them (from the hole's rim, parts of either side;
      the FAIL names the hole and the part), else FAIL. fixture = false: the rows read "no fixture (board
      definition)". Key absent: UNKNOWN: the board definition must say it.

Why it exists (the real failure, told without names)
    Test points were added at the layout from the room that was left: pads a probe slips off, two points too
    close for two probes, a point in the shade of a tall connector, none on the rail that the bring-up plan
    measures first, and the points of the later production fixture on both sides of the board. No rule check
    sees any of it, and the test-point table was typed from memory. The limits are the skill's starting points
    (references/pcb-rules/dfm-dft.md, DFM-90 to DFM-99); where a fixture maker is known, its rules decide.

Usage
    python -I testpoint_check.py --project <hardware/board folder>       results in <project>/out/
    python -I testpoint_check.py <board.kicad_pcb> --out <folder>
    options: --required NET[,NET...], --fixture top|bottom|none, --prefix TP[,MP...], --ground NET[,NET...]
             (they stand for the board.toml keys of a design without a board folder), --no-images
    Results: testpoint_check.md and .json (a row per point with every measured value and its verdict, coverage,
    fixture); testpoints.md (the ONE test-point table for people: DFM-99); review/testpoints_top.png and
    review/testpoints_bottom.png (every point ringed and named; the bottom view mirrored, as seen from the bottom).

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [testpoints]
    prefix = ["TP"]                 # reference prefixes of test-point footprints
    pad_min = 1.0   pad_good = 1.5   pitch_min = 1.27   pitch_good = 2.54   body_clear = 1.0   tall_part = 5.0
    tall_clear = 3.0   edge_clear = 3.0   ground_within = 30.0   label_within = 3.0   probe_pad = 0.8      # all mm
    fixture_tall_clear = 5.0        # mm: clearance of a FIXTURE point to parts taller than tall_part
    fixture_hole_clear = 5.0        # mm free of parts round each locating hole of a fixture
    allow_paste = false             # true: paste on a bare pad is a note (a solder bump is wanted)
    ground_nets = ["GND"]           # names or patterns
    required = ["+3V3", "GND", "/RESET", "SWD*"]     # nets that must have a point or a named pad
    fixture = true                  # true, false; absent: UNKNOWN
    fixture_side = "bottom"         # "top" or "bottom"
    fixture_points = ["TP1", "GND", "SWD*"]          # references or nets (default: every point)
    fixture_holes = ["H1", "H3"]    # the two locating holes (default: any two unplated holes that no part uses)
    [[testpoints.pad]]              # a pad used in place of a test point
    ref = "J3"   pin = "2"   name = "5 V at the input connector"      # name is optional
    [testpoints.normal]             # net = what is normal there (the column of testpoints.md)
    "+3V3" = "3.30 V +-2 %, 0 V in standby"
    [heights]                       # part heights in mm above its side, when there is no body_check.json
    J1 = 12.0
    "C1*" = 7.7                     # a pattern; an exact reference wins
    [review] px_per_mm = 40         # scale limit of the overview images (see review_images.py)
    [[keepout.band]] ...            # edge keep-out bands are drawn on the images (pcb_common.edge_bands)

Exit codes
    0  PASS: no FAIL and no UNKNOWN (notes do not fail)
    1  FAIL, or UNKNOWN items (coverage without a `required` list, no `fixture` key, a height that is missing):
       UNKNOWN is never a pass
    2  CANNOT RUN: KiCad's Python not found, unreadable board, a pad of board.toml that is not on the board

Not checked: whether a point sits on a crystal pin, an RF line or a high-impedance node (DFM-97: by review);
the stub a point adds to a fast net (GEN-42); reach in the enclosure and with the board mounted (MECH-62,
DFM-90: look at the renders); a loop's or hook's own drawing; parts on the other side whose leads come through;
parts marked "do not populate" (no body); vias used as test points (only footprints and named pads count);
the normal values (they come from the design note).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import datetime
import fnmatch
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
from kicad_io import KicadIOError  # noqa: E402

DEFAULTS = {"pad_min": 1.0, "pad_good": 1.5, "pitch_min": 1.27, "pitch_good": 2.54, "body_clear": 1.0, "tall_part": 5.0,
            "tall_clear": 3.0, "fixture_tall_clear": 5.0, "edge_clear": 3.0, "fixture_hole_clear": 5.0,
            "ground_within": 30.0, "label_within": 3.0, "probe_pad": 0.8,
            "allow_paste": False}
DUMP_TIMEOUT = 900.0
FAR = 1e9
C_PASS, C_FAIL, C_NOTE, C_FIX = (70, 225, 100), (255, 70, 70), (255, 190, 40), (60, 220, 255)
OVERVIEW_MP = 16.0                  # largest overview image in megapixels


def _nat(s) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def _fits(name: str, patterns) -> bool:
    """A net name against names or patterns, with or without its sheet path."""
    return any(fnmatch.fnmatchcase(name, p) or fnmatch.fnmatchcase(kicad_io.leaf(name), p) for p in patterns)


# ---- the board, read with KiCad's Python (own process) ---------------------------------------------------------------
def dump(board_path: str) -> dict:
    """What the check needs from a board, as plain data (mm, KiCad's frame: x right, y down)."""
    import pcbnew
    pcb_common.quiet_wx()
    b = kicad_io.load_board(board_path)
    mm = pcbnew.ToMM
    err = pcbnew.FromMM(0.002)                                          # round pads as polygons: distances good to about 0.01 mm
    ps, note = pcb_common.board_outline(b)
    eb = b.GetBoardEdgesBoundingBox()
    bbox = [mm(eb.GetX()), mm(eb.GetY()), mm(eb.GetRight()), mm(eb.GetBottom())]
    loops = []
    if ps is not None:
        loops = [loop for poly in pcb_common.poly_points(ps) for loop in poly]
        bbox = list(pcb_common.pts_box([p for loop in loops for p in loop]))
    silk = {pcbnew.F_SilkS: "top", pcbnew.B_SilkS: "bottom"}

    def one(fn, lid):
        try:
            return fn(lid)
        except TypeError:                                               # KiCad 8 and older: no layer argument
            return fn()

    def text(t, kind):
        shown = t.GetText() if kind == "ref" else t.GetShownText(False)
        return {"text": str(shown), "side": silk[t.GetLayer()], "box": list(pcb_common.bbox_of(t))}

    d = {"file": os.path.basename(board_path), "kicad": pcbnew.GetBuildVersion(), "bbox": bbox,
         "outline": loops, "outline_note": note, "footprints": [], "texts": [],
         "copper_layers": [b.GetLayerName(lay) for lay in b.GetEnabledLayers().CuStack()]}
    kinds = {pcbnew.PAD_ATTRIB_PTH: "pth", pcbnew.PAD_ATTRIB_SMD: "smd", pcbnew.PAD_ATTRIB_NPTH: "npth", pcbnew.PAD_ATTRIB_CONN: "conn"}
    shapes = {getattr(pcbnew, "PAD_SHAPE_" + n): n.lower() for n in ("CIRCLE", "RECT", "OVAL", "TRAPEZOID", "ROUNDRECT",
                                                                    "CHAMFERED_RECT", "CUSTOM") if hasattr(pcbnew, "PAD_SHAPE_" + n)}
    for fp in b.GetFootprints():
        side = pcb_common.fp_side(fp)
        cpoly, cbox = pcb_common.fp_courtyard(fp)
        a = fp.GetAttributes()
        pos = fp.GetPosition()
        pads = []
        for p in fp.Pads():
            on = [n for n, lid in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)) if p.IsOnLayer(lid)]
            lid = pcbnew.B_Cu if on == ["B"] else pcbnew.F_Cu
            size = one(p.GetSize, lid)
            ds = p.GetDrillSize()
            poly = pcbnew.SHAPE_POLY_SET()
            p.TransformShapeToPolygon(poly, lid, 0, err, pcbnew.ERROR_INSIDE)
            pts = pcb_common.poly_points(poly)
            q = p.GetPosition()
            shape = shapes.get(one(p.GetShape, lid), "other")
            w, h = mm(size.x), mm(size.y)
            if shape in ("custom", "other") and pts and len(pts[0][0]) >= 3:   # a drawn pad: the box of its outline
                bx = pcb_common.pts_box(pts[0][0])
                w, h = bx[2] - bx[0], bx[3] - bx[1]
            margin = {}
            for s, ml in (("top", pcbnew.F_Mask), ("bottom", pcbnew.B_Mask)):
                try:
                    margin[s] = mm(one(p.GetSolderMaskExpansion, ml))
                except Exception:                                       # a pad shape this KiCad gives no margin for
                    margin[s] = 0.0
            pads.append({"num": str(p.GetNumber()), "net": str(p.GetNetname()), "x": mm(q.x), "y": mm(q.y),
                         "w": w, "h": h, "shape": shape, "box": list(pcb_common.bbox_of(p)),
                         "poly": pts[0][0] if pts and len(pts[0][0]) >= 3 else None,
                         "drill": mm(ds.x) if p.HasHole() and ds.x > 0 else 0.0, "kind": kinds.get(p.GetAttribute(), "other"),
                         "layers": "".join(on),
                         "mask": {"top": bool(p.IsOnLayer(pcbnew.F_Mask)), "bottom": bool(p.IsOnLayer(pcbnew.B_Mask))},
                         "mask_margin": margin,
                         "paste": {"top": bool(p.IsOnLayer(pcbnew.F_Paste)), "bottom": bool(p.IsOnLayer(pcbnew.B_Paste))}})
        for f in fp.GetFields():
            if f.IsVisible() and f.GetLayer() in silk and f.GetText().strip():
                d["texts"].append(text(f, "ref" if f.GetText() == fp.GetReference() else "field"))
        for g in fp.GraphicalItems():
            if g.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX") and g.GetLayer() in silk:
                d["texts"].append(text(g, "text"))
        d["footprints"].append({
            "ref": fp.GetReference(), "value": fp.GetValue(), "side": side, "x": mm(pos.x), "y": mm(pos.y),
            "dnp": bool(fp.IsDNP()), "exclude_pos": bool(fp.IsExcludedFromPosFiles()), "exclude_bom": bool(fp.IsExcludedFromBOM()),
            "board_only": bool(a & pcbnew.FP_BOARD_ONLY),
            "courtyard": [poly[0] for poly in cpoly if len(poly[0]) >= 3], "courtyard_box": list(cbox) if cbox else None,
            "box": list(pcb_common.fp_part_box(fp) or (mm(pos.x), mm(pos.y), mm(pos.x), mm(pos.y))), "pads": pads})
    for g in b.GetDrawings():
        if g.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX") and g.GetLayer() in silk:
            d["texts"].append(text(g, "text"))
    return d


def read_board(copy: str) -> dict:
    try:
        import pcbnew  # noqa: F401
    except ImportError:
        pass
    else:
        return dump(copy)
    with kicad_io.private_tmp("testpoint-dump-") as tmp:
        js = os.path.join(tmp, "board.json")
        cmd = [kicad_io.kicad_python(), "-I", "-B", os.path.abspath(__file__), "--dump", copy, js]
        rc, text, blocked = pcb_common.run_guarded(cmd, DUMP_TIMEOUT)
        if blocked or rc != 0 or not os.path.isfile(js):
            raise KicadIOError(f"the board could not be read with KiCad's Python: {blocked or text.strip()[-800:]}")
        with open(js, encoding="utf-8") as f:
            return json.load(f)


# ---- geometry ----------------------------------------------------------------------------------------------------------
def box_poly(b) -> list:
    return [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]


def poly_to_loops(poly, loops) -> float:
    """Distance from a polygon to the nearest edge of any loop (the board outline and its cut-outs)."""
    best = FAR
    n = len(poly)
    for loop in loops:
        m = len(loop)
        for i in range(n):
            a = (poly[i][0], poly[i][1], poly[(i + 1) % n][0], poly[(i + 1) % n][1])
            for j in range(m):
                d = pcb_common.seg_seg(a, (loop[j][0], loop[j][1], loop[(j + 1) % m][0], loop[(j + 1) % m][1]))
                if d < best:
                    best = d
    return best


def nothing_fitted(fp) -> bool:
    """A footprint that carries no part: a hole, a mark, a bare pad (board only; or left out of the BOM and of the
    placement file; or nothing but unplated holes)."""
    return bool(fp["board_only"] or (fp["exclude_bom"] and fp["exclude_pos"])
                or (fp["pads"] and all(q["kind"] == "npth" for q in fp["pads"])))


def hole_dist(x: float, y: float, r: float, fp, body=None) -> tuple[float, str]:
    """Distance from the rim of a hole to a part (measured as part_dist does)."""
    if body:
        return pcb_common.poly_circle(box_poly(body), x, y, r), "3D body"
    if fp["courtyard"]:
        return min(pcb_common.poly_circle(c, x, y, r) for c in fp["courtyard"]), "courtyard"
    return pcb_common.poly_circle(box_poly(fp["box"]), x, y, r), "box of pads and drawing"


def part_dist(poly, fp, body=None) -> tuple[float, str]:
    """Distance from a pad's polygon to a part: to the box of its 3D body when body_check.py measured one, else to
    its courtyard, else to the box of its pads and drawing."""
    if body:
        return pcb_common.poly_dist(poly, box_poly(body), FAR), "3D body"
    if fp["courtyard"]:
        return min(pcb_common.poly_dist(poly, c, FAR) for c in fp["courtyard"]), "courtyard"
    return pcb_common.poly_dist(poly, box_poly(fp["box"]), FAR), "box of pads and drawing (no courtyard)"


# ---- settings ------------------------------------------------------------------------------------------------------------
def str_list(cfg: dict, key: str, default):
    v = cfg.get(key, default)
    if v is None:
        return None
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise KicadIOError(f"board.toml [testpoints] {key} must be a list of texts")
    return v


def heights_of(job, board: str) -> tuple[dict, list, str, dict]:
    """({reference: mm}, [(pattern, mm)], where they come from, {reference: body box}). The body boxes are those
    of the 3D models as body_check.py measured them; they exist only with its result of this board state."""
    path = os.path.join(job.out, "body_check.json")
    note = ""
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        if data.get("sha256") == kicad_io.sha256(board) and isinstance(data.get("bodies"), dict):
            ok = {r: v for r, v in data["bodies"].items() if isinstance(v, dict) and "height" in v}
            boxes = {r: v["box"] for r, v in ok.items() if isinstance(v.get("box"), list) and len(v["box"]) == 4}
            return {r: float(v["height"]) for r, v in ok.items()}, [], "body_check.json of this board state", boxes
        note = "body_check.json is of another board state or holds no bodies: not used; "
    table = job.cfg("heights")
    exact, pats = {}, []
    for k, v in table.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise KicadIOError(f"board.toml [heights] {k} must be a height in mm")
        if any(ch in k for ch in "*?["):
            pats.append((k, float(v)))
        else:
            exact[k] = float(v)
    if exact or pats:
        return exact, pats, note + "board.toml [heights]", {}
    return {}, [], note + "no heights (no body_check.json, no [heights] table)", {}


# ---- the overview images ---------------------------------------------------------------------------------------------------
def draw(job, copy: str, info: dict, points: list, ppm_max: float) -> list:
    """review/testpoints_<side>.png for both sides. Returns [(file, what)]; KicadIOError when they cannot be drawn."""
    import review_images as ri
    Image, ImageDraw, _ = ri._pil()
    out = os.path.join(job.out, "review")
    os.makedirs(out, exist_ok=True)
    bbox = tuple(info["bbox"])
    bands, _ = pcb_common.edge_bands(job, bbox)
    made = []
    with kicad_io.private_tmp("testpoint-img-") as tmp:
        want = info["copper_layers"] + ["F.Silkscreen", "B.Silkscreen", "F.Mask", "B.Mask", "F.Fab", "B.Fab", "Edge.Cuts"]
        folder, problems = ri.export_production(copy, tmp, want)
        if problems:
            raise KicadIOError("; ".join(problems))
        L = ri.load_layers(folder)
        gview = ri.full_view(L, ri.k2g(bbox))
        kview = (gview[0], -gview[3], gview[2], -gview[1])
        area = (gview[2] - gview[0]) * (gview[3] - gview[1])
        scale = min(ri.plot_scale(gview, ppm_max), math.sqrt(OVERVIEW_MP * 1e6 / area), 80.0)
        for side in ("top", "bottom"):
            mirror = side == "bottom"
            img = ri.compose(L.stack("labels", side), gview, scale, mirror).convert("RGB")
            img = ri.draw_bands(img, bands, side, kview, scale).convert("RGB")
            dr = ImageDraw.Draw(img)
            font = ri._font(int(max(15, min(44, 1.25 * scale))))
            lw = max(3, int(scale / 6))
            gap = max(3, int(scale / 10))                               # space between a name and its dark plate's rim

            def px(x, y):
                return (((kview[2] - x) if mirror else (x - kview[0])) * scale, (y - kview[1]) * scale)

            here = [p for p in points if p["side"] == side or p["through"]]
            taken, silk = [], []
            for t in info["texts"]:                                     # a name should not hide the board's own labels
                if t["side"] == side:
                    (ax, ay), (bx, by) = px(t["box"][0], t["box"][1]), px(t["box"][2], t["box"][3])
                    silk.append((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))
            for p in here:                                              # the rings first, so that no name hides one
                cx, cy = px(p["x"], p["y"])
                r = max(p["size"] / 2 + 0.8, 1.3) * scale
                col = p["_col"] = C_FAIL if p["result"] == "FAIL" else C_PASS if p["result"] == "PASS" else C_NOTE
                if p["kind"] == "pad":
                    dr.rectangle((cx - r, cy - r, cx + r, cy + r), outline=col, width=lw)
                else:
                    dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=lw)
                if p["fixture"]:
                    r2 = r + lw + 2
                    dr.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), outline=C_FIX, width=max(2, lw // 2))
                p["_ring"] = (cx, cy, r + lw + 4)
                taken.append((cx - r - lw, cy - r - lw, cx + r + lw, cy + r + lw))
            for p in sorted(here, key=lambda q: (q["y"], q["x"])):
                cx, cy, r = p["_ring"]
                label = f"{p['name']} {kicad_io.leaf(p['net']) or '(no net)'}"
                tb = dr.textbbox((0, 0), label, font=font)             # the name sits on a dark plate, readable on any ground
                w, h = tb[2] - tb[0] + 2 * gap, tb[3] - tb[1] + 2 * gap
                spots = [(cx + r, cy - h / 2), (cx - r - w, cy - h / 2), (cx - w / 2, cy - r - h), (cx - w / 2, cy + r),
                         (cx + r, cy - r - h), (cx + r, cy + r), (cx - r - w, cy - r - h), (cx - r - w, cy + r)]
                best = None
                for sx, sy in spots:
                    box = (sx, sy, sx + w, sy + h)
                    inside = box[0] >= 0 and box[1] >= 0 and box[2] <= img.width and box[3] <= img.height
                    clash = sum(1 for t in taken if not (box[2] < t[0] or box[0] > t[2] or box[3] < t[1] or box[1] > t[3]))
                    hidden = sum(1 for t in silk if not (box[2] < t[0] or box[0] > t[2] or box[3] < t[1] or box[1] > t[3]))
                    mx, my = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    stray = any(q is not p and math.hypot(mx - q["_ring"][0], my - q["_ring"][1]) < math.hypot(mx - cx, my - cy)
                                for q in here)                           # nearer to another point's ring than to its own
                    score = clash * 10 + hidden * 3 + (5 if stray else 0) + (0 if inside else 100)
                    if best is None or score < best[0]:
                        best = (score, box)
                    if score == 0:
                        break
                box = best[1]
                nx, ny = min(max(cx, box[0]), box[2]), min(max(cy, box[1]), box[3])     # a leader from the plate to its ring
                far = math.hypot(nx - cx, ny - cy)
                if far > r + 2:
                    dr.line([(nx, ny), (cx + (nx - cx) * (r - lw - 4) / far, cy + (ny - cy) * (r - lw - 4) / far)],
                            fill=p["_col"], width=max(2, lw // 2))
                dr.rectangle(box, fill=(16, 18, 20), outline=p["_col"], width=max(1, lw // 3))
                dr.text((box[0] + gap - tb[0], box[1] + gap - tb[1]), label, fill=(255, 255, 255), font=font)
                taken.append(box)
            n_fail = sum(1 for p in here if p["result"] == "FAIL")
            cap = (f"{side}: {len(here)} test point(s) ringed and named"
                   + (f", {n_fail} FAIL" if n_fail else "") + " | green PASS, red FAIL, amber note or UNKNOWN | square: a pad used as a point"
                   + (" | cyan ring: fixture point" if any(p["fixture"] for p in here) else "")
                   + (" | mirrored: as seen from the bottom" if mirror else "") + f" | {scale:.0f} px/mm")
            name = f"testpoints_{side}.png"
            ri.caption(img, cap).save(os.path.join(out, name))
            made.append((f"review/{name}", cap))
    for p in points:
        p.pop("_ring", None)
        p.pop("_col", None)
    return made


# ---- the check ---------------------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "--dump":
        kicad_io.need_kicad_python()
        kicad_io.atomic_write(argv[2], json.dumps(dump(argv[1])))
        return 0
    ap = pcb_common.io_parser("Test points: sized and placed for the probe, every listed net covered, one side for a fixture.",
                              epilog="Exit codes: 0 pass, 1 FAIL or UNKNOWN items, 2 could not run.")
    ap.add_argument("--required", help="nets that must have a point (comma-separated names or patterns)")
    ap.add_argument("--fixture", choices=("top", "bottom", "none"), help="the side of a production fixture, or none")
    ap.add_argument("--prefix", help="reference prefixes of test points (comma-separated; default TP)")
    ap.add_argument("--ground", help="ground nets (comma-separated names or patterns; default GND)")
    ap.add_argument("--no-images", action="store_true", help="do not draw the overview images")
    a = ap.parse_args(argv)
    job = pcb_common.resolve(a)
    cfg = dict(job.cfg("testpoints"))
    if a.required:
        cfg["required"] = [x.strip() for x in a.required.split(",") if x.strip()]
    if a.fixture:
        cfg["fixture"] = a.fixture != "none"
        if a.fixture != "none":
            cfg["fixture_side"] = a.fixture
    if a.prefix:
        cfg["prefix"] = [x.strip() for x in a.prefix.split(",") if x.strip()]
    if a.ground:
        cfg["ground_nets"] = [x.strip() for x in a.ground.split(",") if x.strip()]
    L = pcb_common.Limits(cfg, DEFAULTS)
    prefixes = str_list(cfg, "prefix", ["TP"])
    ground_nets = str_list(cfg, "ground_nets", ["GND"])
    required = str_list(cfg, "required", None)
    fix_points = str_list(cfg, "fixture_points", None)
    fix_holes = str_list(cfg, "fixture_holes", None)
    fixture = cfg.get("fixture")
    if fixture is not None and not isinstance(fixture, bool):
        raise KicadIOError("board.toml [testpoints] fixture must be true or false")
    fix_side = cfg.get("fixture_side")
    if fix_side not in (None, "top", "bottom"):
        raise KicadIOError("board.toml [testpoints] fixture_side must be \"top\" or \"bottom\"")
    named = cfg.get("pad", [])
    if not isinstance(named, list) or not all(isinstance(n, dict) and n.get("ref") and n.get("pin") is not None for n in named):
        raise KicadIOError("board.toml [[testpoints.pad]] needs ref and pin")
    normal = cfg.get("normal", {})
    if not isinstance(normal, dict):
        raise KicadIOError("board.toml [testpoints.normal] must be a table: net = \"what is normal there\"")
    heights, height_pats, height_src, bodies = heights_of(job, job.board)

    def height(ref):
        if ref in heights:
            return heights[ref]
        return next((h for pat, h in height_pats if fnmatch.fnmatchcase(ref, pat)), None)

    with pcb_common.work_copy(job.board, "testpoint-check-") as copy:
        info = read_board(copy)
        fps = info["footprints"]
        bbox = info["bbox"]
        diag = math.hypot(bbox[2] - bbox[0], bbox[3] - bbox[1])
        is_tp = re.compile(r"^(?:" + "|".join(re.escape(p) for p in sorted(prefixes, key=len, reverse=True)) + r")(?![A-Za-z])") if prefixes else None
        tp_refs = {f["ref"] for f in fps if is_tp and is_tp.match(f["ref"])}

        # ---- the points
        points = []

        def add(fp, pad, kind, label=""):
            side = "bottom" if pad["layers"] == "B" else "top" if pad["layers"] == "F" else fp["side"]
            through = pad["kind"] == "pth" and pad["drill"] > 0
            single = len({p["num"] for p in fp["pads"]}) == 1
            name = fp["ref"] if kind == "point" and single else f"{fp['ref']} pin {pad['num']}"
            excluded = fp["exclude_bom"] or fp["exclude_pos"] or fp["board_only"] or fp["dnp"]
            paste = pad["paste"][side]
            bare = kind == "point" and not through and (excluded or not paste)
            margin = pad["mask_margin"][side]
            size = min(pad["w"], pad["h"])
            points.append({"name": name, "label": label, "ref": fp["ref"], "pin": pad["num"], "kind": kind, "net": pad["net"],
                           "side": side, "through": through, "x": round(pad["x"], 3), "y": round(pad["y"], 3),
                           "pad_w": round(pad["w"], 3), "pad_h": round(pad["h"], 3), "shape": pad["shape"], "size": round(size, 3),
                           "exposed": round(size + 2 * min(margin, 0.0), 3),
                           "mask_open": bool(pad["mask"][side]) and size + 2 * margin > 0, "paste": bool(paste), "bare": bare,
                           "clip": through or (kind == "point" and not bare), "paste_wrong": kind == "point" and paste and excluded,
                           "is_ground": _fits(pad["net"], ground_nets) if pad["net"] else False, "fixture": False,
                           "_poly": pad["poly"] or box_poly(pad["box"]), "_box": pad["box"], "_fp": fp,
                           "fails": [], "notes": [], "unknown": []})

        for fp in fps:
            if fp["ref"] in tp_refs:
                seen = set()
                for pad in fp["pads"]:
                    if pad["kind"] != "npth" and pad["num"] not in seen:
                        seen.add(pad["num"])
                        add(fp, pad, "point")
        for n in named:
            ref, pin = str(n["ref"]), str(n["pin"])
            hit = [(fp, pad) for fp in fps if fp["ref"] == ref for pad in fp["pads"] if pad["num"] == pin]
            if not hit:
                raise KicadIOError(f"board.toml [[testpoints.pad]] names {ref} pin {pin}, which is not on the board")
            if not any(p["ref"] == ref and p["pin"] == pin for p in points):
                add(hit[0][0], hit[0][1], "pad", str(n.get("name", "")))
        points.sort(key=lambda p: (_nat(p["ref"]), _nat(p["pin"])))
        grounds = [p for p in points if p["is_ground"]]

        # ---- fixture points
        fixture_rows, fx_fail, fx_unknown = [], [], []
        if fixture:
            if fix_points is None:
                for p in points:
                    p["fixture"] = True
            else:
                for entry in fix_points:
                    hit = [p for p in points if entry in (p["name"], p["ref"], f"{p['ref']}.{p['pin']}") or (p["net"] and _fits(p["net"], [entry]))]
                    if not hit:
                        fx_fail.append(f"fixture point '{entry}' is no test point and no net with a test point")
                    for p in hit:
                        p["fixture"] = True

        # ---- per point
        others = [f for f in fps if f["ref"] not in tp_refs and not f["dnp"] and (f["pads"] or f["courtyard"])]
        for p in points:
            poly = p["_poly"]
            # pad, mask, paste
            if p["kind"] == "pad":                                      # a pad used as a point: one a probe can hold (DFM-94)
                if not p["through"] and p["exposed"] < L["probe_pad"] - 1e-6:
                    p["fails"].append(f"a pad used as a point, {p['exposed']:.2f} mm on its smaller side: under probe_pad "
                                      f"{L['probe_pad']:g} mm, not a pad a probe can hold")
            elif p["exposed"] < L["pad_min"] - 1e-6:
                p["fails"].append(f"pad {p['exposed']:.2f} mm, under pad_min {L['pad_min']:g} mm")
            elif p["exposed"] < L["pad_good"] - 1e-6:
                p["notes"].append(f"pad {p['exposed']:.2f} mm, under pad_good {L['pad_good']:g} mm")
            if not p["mask_open"]:
                p["fails"].append("the solder mask is not open over the pad")
            if p["paste_wrong"]:
                (p["notes"] if L["allow_paste"] else p["fails"]).append("paste on a pad that gets no part (the stencil leaves a solder bump)")
            # pitch
            same = [q for q in points if q is not p and (q["side"] == p["side"] or q["through"] or p["through"])]
            near = min(same, key=lambda q: math.hypot(q["x"] - p["x"], q["y"] - p["y"]), default=None)
            p["pitch"] = round(math.hypot(near["x"] - p["x"], near["y"] - p["y"]), 3) if near else None
            p["pitch_to"] = near["name"] if near else None
            if near and p["pitch"] < L["pitch_min"] - 1e-6:
                p["fails"].append(f"{p['pitch']:.2f} mm from {near['name']} (centre to centre), under pitch_min {L['pitch_min']:g} mm")
            elif near and p["pitch"] < L["pitch_good"] - 1e-6:
                text = f"{p['pitch']:.2f} mm from {near['name']} (centre to centre), under pitch_good {L['pitch_good']:g} mm"
                (p["fails"] if p["fixture"] else p["notes"]).append(text + (" (a fixture point)" if p["fixture"] else ""))
            # bodies and tall parts (a fixture's probe plate needs more room beside a tall part than a hand probe)
            tall_key = "fixture_tall_clear" if p["fixture"] else "tall_clear"
            best, tall, unknown_h = (FAR, None, ""), (FAR, None, 0.0), []
            for f in others:
                if f is p["_fp"] or (f["side"] != p["side"] and not p["through"]):
                    continue
                if pcb_common.box_gap(p["_box"], f["courtyard_box"] or f["box"]) > max(L[tall_key], L["body_clear"], best[0]) + 0.1:
                    continue
                dist, basis = part_dist(poly, f, bodies.get(f["ref"]))
                if dist < best[0]:
                    best = (dist, f["ref"], basis)
                if dist < L[tall_key] - 1e-6:
                    h = height(f["ref"])
                    if h is None and nothing_fitted(f):
                        h = 0.0                                         # a hole, a mark, a bare pad: nothing is fitted there
                    if h is None:
                        unknown_h.append(f["ref"])
                    elif h > L["tall_part"] and dist < tall[0]:
                        tall = (dist, f["ref"], h)
            p["body"], p["body_to"], p["body_basis"] = (round(best[0], 3), best[1], best[2]) if best[1] else (None, None, "")
            if best[1] and best[0] < L["body_clear"] - 1e-6:            # a part's own pad sits among its neighbours: a note there
                (p["notes"] if p["kind"] == "pad" else p["fails"]).append(
                    f"{best[0]:.2f} mm from {best[1]} ({best[2]}), under body_clear {L['body_clear']:g} mm"
                    + (": a probe has little room on this pad" if p["kind"] == "pad" else ""))
            p["tall"], p["tall_to"], p["tall_height"] = (round(tall[0], 3), tall[1], tall[2]) if tall[1] else (None, None, None)
            p["tall_unknown"] = sorted(unknown_h, key=_nat)
            if tall[1]:
                p["fails"].append(f"{tall[0]:.2f} mm from {tall[1]}, which is {tall[2]:g} mm tall (over tall_part {L['tall_part']:g} mm): "
                                  f"under {tall_key} {L[tall_key]:g} mm" + (" (a fixture point)" if p["fixture"] else ""))
            elif unknown_h:
                p["unknown"].append(f"height not known of {', '.join(p['tall_unknown'])} within {tall_key} {L[tall_key]:g} mm")
            # edge
            p["edge"] = round(poly_to_loops(poly, info["outline"]), 3) if info["outline"] else None
            if p["fixture"]:
                if p["edge"] is None:
                    p["unknown"].append("distance to the board edge not known (the outline is not closed)")
                elif p["edge"] < L["edge_clear"] - 1e-6:
                    p["fails"].append(f"{p['edge']:.2f} mm from the board edge, under edge_clear {L['edge_clear']:g} mm (a fixture point)")
            # label
            word = re.compile(r"(?<![A-Za-z0-9])" + re.escape(p["ref"]) + r"(?![A-Za-z0-9])")
            near_box = p["_fp"]["box"] if p["kind"] == "pad" else p["_box"]    # a named pad: the label of its part
            labels = [(pcb_common.box_gap(near_box, t["box"]), t["text"]) for t in info["texts"]
                      if (t["side"] == p["side"] or p["through"]) and word.search(t["text"])]
            lab = min(labels, default=None)
            p["label_dist"], p["label_text"] = (round(lab[0], 3), lab[1]) if lab else (None, None)
            if lab is None or lab[0] > L["label_within"] + 1e-6:
                p["notes"].append(f"no silkscreen text with '{p['ref']}' within label_within {L['label_within']:g} mm"
                                  + (f" (the nearest is {lab[0]:.1f} mm away)" if lab else ""))
            # ground
            if p["is_ground"]:
                p["ground"], p["ground_to"] = 0.0, p["name"]
            else:
                g = min(grounds, key=lambda q: math.hypot(q["x"] - p["x"], q["y"] - p["y"]), default=None)
                p["ground"] = round(math.hypot(g["x"] - p["x"], g["y"] - p["y"]), 2) if g else None
                p["ground_to"] = g["name"] if g else None
                if g and p["ground"] > L["ground_within"] + 1e-6:
                    p["notes"].append(f"nearest ground point {g['name']} is {p['ground']:.1f} mm away, beyond ground_within {L['ground_within']:g} mm")
            # fixture side
            if p["fixture"] and fix_side and p["side"] != fix_side and not p["through"]:
                p["fails"].append(f"on the {p['side']} side; the fixture side is {fix_side}")
            p["result"] = "FAIL" if p["fails"] else "UNKNOWN" if p["unknown"] else "NOTE" if p["notes"] else "PASS"

        # ---- coverage
        nets = {}
        for f in fps:
            for pad in f["pads"]:
                if pad["net"]:
                    nets.setdefault(pad["net"], []).append((f, pad))
        covered = {p["net"] for p in points if p["net"]}
        cov_rows, cov_fail, cov_notes = [], [], []
        if required is not None:
            for pat in required:
                hit = sorted((n for n in nets if _fits(n, [pat])), key=_nat)
                if not hit:
                    cov_rows.append((pat, "-", "FAIL: no such net on the board"))
                    cov_fail.append(f"required net '{pat}' is not on the board (renamed?)")
                for n in hit:
                    at = [p["name"] for p in points if p["net"] == n]
                    cov_rows.append((pat, n, ("PASS: " + ", ".join(at)) if at else "FAIL: no test point and no named pad"))
                    if not at:
                        cov_fail.append(f"required net {n} has no test point and no named pad")
        else:
            for n in sorted(nets, key=_nat):
                if n in covered or len(nets[n]) < 2:
                    continue
                if not any((pad["kind"] == "pth" and pad["drill"] > 0) or (pad["kind"] in ("smd", "conn") and min(pad["w"], pad["h"]) >= L["probe_pad"] - 1e-6)
                           for _, pad in nets[n]):
                    largest = max(min(pad["w"], pad["h"]) for _, pad in nets[n])
                    cov_notes.append(f"net {n} ({len(nets[n])} pads, the largest {largest:.2f} mm on its smaller side): no test point and no pad a probe can hold")
        g_fail, g_notes = [], []
        if not points and required is None:
            pass                                                        # no point and no list: nothing is known (UNKNOWN below)
        elif not grounds:
            have = sorted(n for n in nets if _fits(n, ground_nets))
            g_fail.append("no ground test point" + (f" on {', '.join(have)}" if have else
                                                    f": the board has no net named {', '.join(ground_nets)} (set [testpoints] ground_nets)"))
        elif not any(p["clip"] for p in grounds):
            g_notes.append("no ground point that a clip can hold: every ground point is a bare pad (" + ", ".join(p["name"] for p in grounds) + ")")

        # ---- fixture rows
        if fixture is None:
            fixture_rows.append(("Fixture", "UNKNOWN: board.toml [testpoints] has no `fixture` key; the board definition must say whether a fixture is planned"))
            fx_unknown.append("fixture: not stated (set [testpoints] fixture = true or false, as the board definition says)")
        elif fixture is False:
            fixture_rows.append(("Fixture", "no fixture (board definition)"))
        else:
            fpts = [p for p in points if p["fixture"]]
            if not fix_side:
                fx_fail.append("fixture = true, but fixture_side is not set (\"top\" or \"bottom\")")
            if not fpts:
                fx_fail.append("fixture = true, but the board has no fixture point")
            wrong = [p["name"] for p in fpts if fix_side and p["side"] != fix_side and not p["through"]]
            close = [f"{p['name']} ({p['pitch']:.2f} mm from {p['pitch_to']})" for p in fpts if p["pitch"] is not None and p["pitch"] < L["pitch_good"] - 1e-6]
            edge = [f"{p['name']} ({p['edge']:.2f} mm)" for p in fpts if p["edge"] is not None and p["edge"] < L["edge_clear"] - 1e-6]
            fixture_rows.append((f"Fixture points ({len(fpts)}) on the {fix_side or '?'} side",
                                 ("FAIL: on the other side: " + ", ".join(wrong)) if wrong else "FAIL: fixture_side not set" if not fix_side else "PASS"))
            fixture_rows.append((f"Fixture points at pitch_good {L['pitch_good']:g} mm or more", ("FAIL: " + ", ".join(close)) if close else "PASS"))
            if any(p["edge"] is None for p in fpts):
                fixture_rows.append((f"Fixture points {L['edge_clear']:g} mm from the board edge", "UNKNOWN: the outline is not closed"))
                fx_unknown.append("fixture: the distance to the board edge is not known (the outline is not closed)")
            else:
                fixture_rows.append((f"Fixture points {L['edge_clear']:g} mm from the board edge", ("FAIL: " + ", ".join(edge)) if edge else "PASS"))
            holes = [(f["ref"], pad["x"], pad["y"], pad["drill"]) for f in fps for pad in f["pads"] if pad["kind"] == "npth" and pad["drill"] > 0]
            if fix_holes is not None:
                chosen, bad = [], []
                for ref in fix_holes:
                    hit = [h for h in holes if h[0] == ref]
                    if hit:
                        chosen.append(hit[0])
                    else:
                        bad.append(ref + (" (plated)" if any(f["ref"] == ref for f in fps) else " (not on the board)"))
                located = chosen
                if bad or len(chosen) < 2:
                    text = "FAIL: " + ("not an unplated hole: " + ", ".join(bad) if bad else "two holes are needed")
                else:
                    dist = max(math.hypot(a_[1] - b_[1], a_[2] - b_[2]) for a_ in chosen for b_ in chosen)
                    text = (f"{'PASS' if dist >= diag / 2 - 1e-6 else 'FAIL'}: {', '.join(h[0] for h in chosen)} are {dist:.1f} mm apart; "
                            f"half the board's diagonal is {diag / 2:.1f} mm")
            else:                                                       # the peg holes of a fitted part are not free for a pin
                free = [h for h in holes if any(f["ref"] == h[0] and nothing_fitted(f) for f in fps)]
                pair = max(((math.hypot(a_[1] - b_[1], a_[2] - b_[2]), a_, b_) for i, a_ in enumerate(free) for b_ in free[i + 1:]),
                           key=lambda t: t[0], default=None)
                located = list(pair[1:]) if pair else free
                if pair is None:
                    text = (f"FAIL: the board has {len(free)} unplated hole(s) that no part uses; two are needed for the fixture's "
                            f"locating pins")
                else:
                    text = (f"{'PASS' if pair[0] >= diag / 2 - 1e-6 else 'FAIL'}: the two unplated holes farthest apart ({pair[1][0]}, {pair[2][0]}) "
                            f"are {pair[0]:.1f} mm apart; half the board's diagonal is {diag / 2:.1f} mm")
            fixture_rows.append(("Two unplated holes at least half the diagonal apart", text))
            if text.startswith("FAIL"):
                fx_fail.append("fixture locating holes: " + text[6:])           # the three rows above fail per point
            # about fixture_hole_clear free of parts round each locating hole, on either side (the pin's collar, a hold-down)
            clear, said = L["fixture_hole_clear"], []
            fitted = [f for f in fps if not f["dnp"] and not nothing_fitted(f) and (f["pads"] or f["courtyard"])]
            for ref, hx, hy, drill in located:
                near_parts = []
                for f in fitted:
                    if f["ref"] == ref or pcb_common.pt_box(hx, hy, f["courtyard_box"] or f["box"]) > clear + drill / 2 + 0.1:
                        continue
                    dist, basis = hole_dist(hx, hy, drill / 2, f, bodies.get(f["ref"]))
                    if dist < clear - 1e-6:
                        near_parts.append((dist, f["ref"], basis))
                near_parts.sort()
                if near_parts:
                    names = ", ".join(f"{r} at {dist:.2f} mm ({basis})" for dist, r, basis in near_parts[:6]) + \
                        (f" and {len(near_parts) - 6} more" if len(near_parts) > 6 else "")
                    said.append(f"{ref}: {names}")
                    fx_fail.append(f"fixture locating hole {ref}: {names} from its rim, under fixture_hole_clear {clear:g} mm")
            fixture_rows.append((f"About {clear:g} mm free of parts round each locating hole (from its rim, either side)",
                                 ("FAIL: " + "; ".join(said)) if said else
                                 ("PASS: " + ", ".join(h[0] for h in located)) if located else "not judged: no locating hole"))

        # ---- images
        images, img_problem = [], ""
        if a.no_images:
            img_problem = "not made (--no-images)"
        else:
            try:
                images = draw(job, copy, info, points, float(job.cfg("review").get("px_per_mm", 40.0)))
            except KicadIOError as e:
                img_problem = f"could NOT be drawn: {e}"

    # ---- the result
    fails = [f"{p['name']} ({p['net'] or 'no net'}): {t}" for p in points for t in p["fails"]] + cov_fail + g_fail + fx_fail
    unknown = [f"{p['name']} ({p['net'] or 'no net'}): {t}" for p in points for t in p["unknown"]] + fx_unknown
    if required is None:
        unknown.append("coverage: no `required` list in board.toml [testpoints]: which nets need a point is not known"
                       + ("" if points else "; the board has no test point at all"))
    if img_problem and not a.no_images:
        fails.append(f"the overview images {img_problem}")
    notes = [f"{p['name']} ({p['net'] or 'no net'}): {t}" for p in points for t in p["notes"]] + g_notes + cov_notes
    result = "FAIL" if fails else "UNKNOWN (not a pass)" if unknown else "PASS"
    for p in points:
        for k in ("_poly", "_box", "_fp"):
            p.pop(k, None)

    def num(v, nd=2):
        return "-" if v is None else f"{v:.{nd}f}"

    md = pcb_common.header("Test points: probe access, coverage, fixture", job, "testpoint_check.py")
    md += [f"**Result: {result}**: {len(points)} test point(s) ({sum(1 for p in points if p['kind'] == 'pad')} of them pads used as a point), "
           f"{len(fails)} FAIL, {len(unknown)} UNKNOWN, {len(notes)} note(s).", "",
           f"Test points are the footprints whose reference starts with {', '.join(prefixes) or '(no prefix)'}"
           + (f", and the {len(named)} pad(s) named in board.toml" if named else "") + f". Ground nets: {', '.join(ground_nets)}. "
           f"Part heights: {height_src}. Coordinates: KiCad's (mm, x to the right, y down).", "",
           "The limits are the skill's STARTING POINTS (references/pcb-rules/dfm-dft.md, DFM-96, DFM-98); where a fixture maker "
           "is known, its rules decide:", ""] + L.table() + [""]
    if info["outline_note"]:
        md += [f"Board outline: {info['outline_note']}: distances to the edge are UNKNOWN.", ""]
    md += ["## Every test point", "",
           "| Point | Net | Side | x | y | Pad (mm) | Mask, paste | Nearest point (mm) | Nearest part (mm) | Tall part within reach | Edge (mm) | "
           "Label | Ground point (mm) | Result |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in points:
        pad = f"{p['pad_w']:.2f} round" if p["shape"] == "circle" else f"{p['pad_w']:.2f} x {p['pad_h']:.2f} {p['shape']}"
        pad += f", exposed {p['exposed']:.2f}" if p["exposed"] < p["size"] - 1e-6 else ""
        mask = ("open" if p["mask_open"] else "COVERED") + (", paste" if p["paste"] else ", no paste") + \
            (", bare pad" if p["bare"] else ", through-hole" if p["through"] else ", a soldered pad" if p["kind"] == "pad" else ", fitted part")
        tall = (f"{p['tall_to']} ({p['tall_height']:g} mm tall) at {p['tall']:.2f}" if p["tall_to"] else
                ("height not known: " + ", ".join(p["tall_unknown"])) if p["tall_unknown"] else "none")
        why = "; ".join(p["fails"] + p["unknown"] + p["notes"])
        md.append(f"| {p['name']}{' (' + p['label'] + ')' if p['label'] else ''}{' [fixture]' if p['fixture'] else ''} | {p['net'] or '(no net)'} | "
                  f"{p['side']}{' (through)' if p['through'] else ''} | {p['x']:.2f} | {p['y']:.2f} | {pad} | {mask} | "
                  f"{num(p['pitch'])}{' to ' + p['pitch_to'] if p['pitch_to'] else ''} | {num(p['body'])}{' to ' + p['body_to'] + ' (' + p['body_basis'].split(' (')[0] + ')' if p['body_to'] else ''} | "
                  f"{tall} | {num(p['edge'])} | {('yes, ' + num(p['label_dist'], 1) + ' mm') if p['label_dist'] is not None and p['label_dist'] <= L['label_within'] else 'NO'} | "
                  f"{'is one' if p['is_ground'] else num(p['ground'], 1) + (' to ' + p['ground_to'] if p['ground_to'] else '')} | "
                  f"{p['result']}{': ' + why if why else ''} |")
    if not points:
        md.append("| (the board has no test point) | | | | | | | | | | | | | |")
    md += ["", "## Coverage", ""]
    if required is not None:
        md += ["| Required (board.toml) | Net on the board | Result |", "|---|---|---|"] + [f"| {a_} | {b_} | {c_} |" for a_, b_, c_ in cov_rows]
    else:
        md += ["**UNKNOWN**: board.toml [testpoints] has no `required` list, so it is not known which nets need a point "
               "(the list is decided at the schematic: DFM-94).",
               f"Nets with two or more pads that have neither a test point nor a pad a probe can hold (a through-hole pad, or a surface "
               f"pad of {L['probe_pad']:g} mm or more on its smaller side; a rule of thumb): {len(cov_notes)}."]
    md += ["", "Ground: " + (g_fail[0] if g_fail else "the board has no test point and no `required` list: not judged" if not points
                             else f"{len(grounds)} ground point(s): {', '.join(p['name'] for p in grounds)}"
                             + ("; " + g_notes[0] if g_notes else "; at least one that a clip can hold (a through-hole pin or a fitted part)")) + ".",
           "", "## Fixture (DFM-98)", "", "| Row | Result |", "|---|---|"] + [f"| {a_} | {b_} |" for a_, b_ in fixture_rows]
    md += ["", "## Files", "", "- `testpoints.md`: the test-point table for people (DFM-99)."]
    md += [f"- `{f}`: {what}." for f, what in images] or [f"- overview images: {img_problem}."]
    for title, items, tag in (("Findings", fails, "FAIL"), ("UNKNOWN", unknown, "UNKNOWN"), ("Notes (not counted)", notes, "NOTE")):
        md += ["", f"## {title}", ""] + ([f"- {tag}: {x}" for x in items] or ["None."])
    md += ["", "## Not checked", "",
           "A point on a crystal pin, an RF line or a high-impedance node (DFM-97) and the stub it adds to a fast net (GEN-42): by "
           "review; reach with the board mounted and in the enclosure: look at the renders; parts of the other side whose leads come "
           "through; parts marked \"do not populate\"; vias used as test points; the normal values of the table.",
           "", f"**Result: {result}** ({len(fails)} FAIL, {len(unknown)} UNKNOWN)"]
    data = {"script": "testpoint_check.py", "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board), "result": result,
            "limits": L.to_dict(), "prefix": prefixes, "ground_nets": ground_nets, "required": required, "heights_from": height_src,
            "points": points, "coverage": [{"required": a_, "net": b_, "result": c_} for a_, b_, c_ in cov_rows],
            "coverage_result": "UNKNOWN" if required is None else ("FAIL" if cov_fail else "PASS"),
            "uncovered_nets": cov_notes, "ground_points": [p["name"] for p in grounds],
            "fixture": {"planned": fixture, "side": fix_side, "points": [p["name"] for p in points if p["fixture"]],
                        "rows": [{"row": a_, "result": b_} for a_, b_ in fixture_rows]},
            "images": [f for f, _ in images], "images_problem": img_problem, "failures": fails, "unknown": unknown, "notes": notes,
            "crops": [{"name": f"testpoint_{p['name'].replace(' ', '_')}", "frame": "kicad", "x": p["x"], "y": p["y"], "size": 12.0,
                       "why": "; ".join(p["fails"])} for p in points if p["fails"]]}
    p_md, _ = pcb_common.write_result(job.out, "testpoint_check", md, data)

    # ---- the table for people
    kc = kicad_io.find_kicad()
    tb = [f"# Test points of `{os.path.basename(job.board)}`", "",
          f"Written by `scripts/testpoint_check.py` from the saved board on {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
          f"{' with KiCad ' + kc.version if kc else ''}; board SHA-256 `{kicad_io.sha256(job.board)}`. Never typed by hand (DFM-99).",
          "Position: KiCad's coordinates (mm), and in brackets from the board's left edge and from its top edge as seen from the top side. "
          "Power is never fed through a test point (DFM-92).", "",
          "| Point | Net | Side | Position x, y (mm) | Pad (mm) | Normal value |", "|---|---|---|---|---|---|"]
    for p in points:
        nv = next((str(v) for k, v in normal.items() if k == p["net"] or k == kicad_io.leaf(p["net"])), "<from the design note>")
        tb.append(f"| {p['name']}{' (' + p['label'] + ')' if p['label'] else ''} | {p['net'] or '(no net)'} | {p['side']}{', through-hole' if p['through'] else ''} | "
                  f"{p['x']:.2f}, {p['y']:.2f} ({p['x'] - bbox[0]:.1f} from the left, {p['y'] - bbox[1]:.1f} from the top) | "
                  f"{(format(p['pad_w'], '.2f') + ' round') if p['shape'] == 'circle' else format(p['pad_w'], '.2f') + ' x ' + format(p['pad_h'], '.2f')} | {nv} |")
    if not points:
        tb.append("| (the board has no test point) | | | | | |")
    kicad_io.atomic_write(os.path.join(job.out, "testpoints.md"), pcb_common.scrub("\n".join(tb) + "\n"))
    for x in (fails + unknown)[:40]:
        print(("FAIL " if x in fails else "UNKNOWN ") + x)
    print(f"{result}: {len(points)} test point(s), {len(fails)} FAIL, {len(unknown)} UNKNOWN, {len(notes)} note(s) -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
