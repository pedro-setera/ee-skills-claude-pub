"""Silkscreen check of a board: sizes, clearances on each text's box, labels beside their own parts, unlabelled parts.

What it checks, on both sides of the saved board
    sizes       every silkscreen text at least min_height high with a line of at least min_line; every
                silkscreen line of a footprint or of the board at least min_line wide
    clearances  of every text, measured on its BOX (the rectangle KiCad gives the text: glyph height plus the
                line width; the stricter reading), to pads, holes and through-hole pads, via copper, the board
                edge, other texts, other footprints' marks (texts inside a footprint), footprint outlines and
                part bodies; the distance of the printed strokes is listed beside the box distance
    outlines    footprint silkscreen lines to pads, to the board edge and to vias. Against the pads of its OWN
                part a line fails only when it lies on the pad (the stock library footprints keep about 0.09 mm);
                against another part's pad the limit graphic_pad holds. A line over or beside a via: a finding
                at graphic_via when the via is not covered by solder mask (bare copper: the ink is clipped), a
                counted note when it is covered (cosmetic), a note too when this KiCad cannot say whether it is
                covered (the head of the result then says so)
    ownership   each part's label is lined up with its own part, within own_max of it, its centre nearer its
                own part than any other by own_margin, never between two other parts; a short silkscreen line
                from the label to the part (a leader) is accepted instead; labelled groups named in board.toml
                are tested as groups
    one line    labels of different parts on one line are at least read_gap apart, end to end, so that two
                names never read as one word
    group text  a text that names several parts: each name sits beside its own part
    unlabelled  every placed part has a visible reference on its own side (its reference field, a board text
                that starts with the reference, or a group text); each part without one is a finding until a
                waiver for it is recorded in board.toml
    fields      no other field (value, distributor number, part number) is printed on the silkscreen
    information block   the texts board.toml names are on the board

Why it exists (real failures, told without names)
    A designer's check measured the printed strokes and passed; a reviewer measured the boxes and found text
    almost touching via copper. Labels were read as the neighbour's: a test-point name nearer another point, two
    resistor names side by side reading as one word. Automatic group texts put names beside the wrong parts.
    Some parts of a dense board ended with no legal label spot; that is a decision for the user, with crops,
    never something to leave silent. Library outlines carried 0.12 mm lines the factory drops.

Usage
    python -I silk_check.py --project <hardware/board folder>         result in <project>/out/silk_check.md
    python -I silk_check.py <board.kicad_pcb> --out <folder>          any KiCad board; defaults are printed
    The board is read from a private copy. The result's JSON twin lists a crop location for every finding;
    review_images.py cuts zooms of them.

board.toml keys (all optional; a limit set to -1 switches its rule off, which the result lists as not checked)
    [silk]
    min_height = 1.0   min_line = 0.15                      # the fabricator's minimums (re-read before an order)
    pad = 0.2   hole = 0.5   via = 0.1   edge = 0.4   text = 0.25   mark = 0.5   outline = 0.15   body = 0.15
    graphic_pad = 0.15   graphic_edge = 0.2   graphic_via = 0.1   mark_via = 0.2
                               # graphic_pad: a part outline to ANOTHER part's pad (its own pads: not on the pad);
                               # graphic_via: a part outline to a via that is NOT covered by solder mask
    own_max = 0.8   own_margin = 0.2   own_slack = 0.25   between = 0.8   read_gap = 1.0   group_gap = 0.2
    accept_relaxed = false     # true: a label that is nearer its own part than any other, but without the
                               # margin or between two parts, is listed instead of failed
    accept_same_kind = false   # true: a label that only a part of another kind (letters of the reference) beats
                               # is listed instead of failed
    allow_fields = []          # field names that may be printed, e.g. ["Value"]
    ignore_refs = ["FID*", "REF**", "G***", "LOGO*", "#*"]   # parts that need no label (mounting holes never do)
    info_block = ["MyBoard", "Rev"]                           # texts that must be on the silkscreen
    [[silk.group]]             # a labelled group: labels in one aligned line outside a tight cluster
    name = "decoupling capacitors"   refs = ["C4", "C5"]   kind = "col"     # "col": a column of parts; "row"
    [[silk.waiver]]            # parts the user accepted without a label
    refs = ["C3", "R2"]   reason = "no legal spot; reference is on the assembly drawing"   approved = "user, YYYY-MM-DD"
    [holes] refs, min_d        which footprints are mounting holes (see pcb_common.py)

Exit codes
    0  PASS: no finding (waived parts are listed)
    1  FAIL: any finding
    2  CANNOT RUN: KiCad's Python not found, unreadable board. Never a pass.

Not checked: whether a label is hidden under a 3D body that is larger than the footprint's drawing (look at the
renders); polarity and pin-1 marks; pin legends against the netlist; the meaning of any text. Open the silkscreen
plots of both sides and look.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
from pcb_common import box_gap, inside, poly_box, poly_circle, poly_dist, pt_box, seg_seg  # noqa: E402

DEFAULTS = {"min_height": 1.0, "min_line": 0.15, "pad": 0.2, "hole": 0.5, "via": 0.1, "edge": 0.4, "text": 0.25,
            "mark": 0.5, "outline": 0.15, "body": 0.15, "graphic_pad": 0.15, "graphic_edge": 0.2, "graphic_via": 0.1,
            "mark_via": 0.2, "own_max": 0.8, "own_margin": 0.2, "own_slack": 0.25, "between": 0.8, "read_gap": 1.0,
            "group_gap": 0.2, "accept_relaxed": False, "accept_same_kind": False}
IGNORE_REFS = ["FID*", "REF**", "G***", "LOGO*", "#*"]
EPS = 0.005                         # mm: a distance this much under a limit still passes (rounding of the file)
FAR = 99.0
MAX_LISTED = 150
MAX_CROPS = 80


# ---- geometry on point lists (mm, KiCad's frame) --------------------------------------------------------------------
def polys_dist(polys_a, b):
    return min((poly_dist(a, b) for a in polys_a), default=FAR)


class Index:
    """Things with boxes on a 2 mm grid, to find what lies near a box."""

    def __init__(self, cell=2.0):
        self.cell, self.grid, self.items = cell, {}, []

    def add(self, box, obj):
        i = len(self.items)
        self.items.append((box, obj))
        c = self.cell
        for gx in range(int(math.floor(box[0] / c)), int(math.floor(box[2] / c)) + 1):
            for gy in range(int(math.floor(box[1] / c)), int(math.floor(box[3] / c)) + 1):
                self.grid.setdefault((gx, gy), []).append(i)

    def near(self, box, reach):
        c = self.cell
        seen = set()
        for gx in range(int(math.floor((box[0] - reach) / c)), int(math.floor((box[2] + reach) / c)) + 1):
            for gy in range(int(math.floor((box[1] - reach) / c)), int(math.floor((box[3] + reach) / c)) + 1):
                for i in self.grid.get((gx, gy), ()):
                    if i not in seen:
                        seen.add(i)
                        b, obj = self.items[i]
                        if box_gap(box, b) <= reach:
                            yield b, obj

    def nearest(self, box, dist, start=3.0):
        """(smallest dist(obj), obj) over everything; dist() is only called while a box can still beat the best."""
        reach = start
        while True:
            best = (FAR, None)
            cands = sorted(self.near(box, reach), key=lambda t: box_gap(box, t[0]))
            for b, obj in cands:
                if box_gap(box, b) >= best[0]:
                    break
                d = dist(obj)
                if d < best[0]:
                    best = (d, obj)
            if best[0] <= reach or reach > 400:
                return best
            reach *= 4


# ---- reading the board -----------------------------------------------------------------------------------------------
def _pts(ps):
    out = []
    for poly in pcb_common.poly_points(ps):
        if len(poly[0]) >= 3:
            out.append(poly[0])
    return out


def read_silk(board, cfg_holes, ignore):
    """Everything the rules need, as plain data, per side ("top", "bottom")."""
    import pcbnew
    err = pcbnew.FromMM(0.002)
    mm = pcbnew.ToMM
    S = {s: {"texts": [], "graphics": [], "pads": Index(), "parts": [], "marks": []} for s in ("top", "bottom")}
    silk_side = {pcbnew.F_SilkS: "top", pcbnew.B_SilkS: "bottom"}
    refs = {fp.GetReference() for fp in board.GetFootprints()}

    def text_entry(t, kind, fp_ref, name=""):
        ps = pcbnew.SHAPE_POLY_SET()
        t.TransformShapeToPolygon(ps, t.GetLayer(), 0, err, pcbnew.ERROR_INSIDE)
        polys = _pts(ps)
        if not polys:
            return None
        st = pcbnew.SHAPE_POLY_SET()
        t.TransformTextToPolySet(st, 0, err, pcbnew.ERROR_INSIDE)
        shown = t.GetShownText(False) if kind != "ref" else t.GetText()
        return {"kind": kind, "fp": fp_ref, "name": name, "text": shown, "h": mm(t.GetTextHeight()),
                "th": mm(t.GetTextThickness()), "poly": polys[0], "box": poly_box(polys[0]), "strokes": _pts(st),
                "angle": t.GetDrawRotation().AsDegrees() % 360.0, "mirror": bool(t.IsMirrored()), "owner": None,
                "members": []}

    def graphic_entry(g, fp_ref):
        ps = pcbnew.SHAPE_POLY_SET()
        g.TransformShapeToPolygon(ps, g.GetLayer(), 0, err, pcbnew.ERROR_INSIDE)
        polys = _pts(ps)
        if not polys:
            return None
        seg = None
        if g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            a, e = g.GetStart(), g.GetEnd()
            seg = (mm(a.x), mm(a.y), mm(e.x), mm(e.y))
        solid = bool(g.IsSolidFill()) if hasattr(g, "IsSolidFill") else False
        return {"fp": fp_ref, "polys": polys, "box": pcb_common.box_union([poly_box(p) for p in polys]),
                "width": mm(g.GetWidth()), "solid": solid, "seg": seg}

    holes_fp = set()
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        side = pcb_common.fp_side(fp)
        info = {"ref": ref, "value": fp.GetValue(), "lib": fp.GetFPID().GetUniStringLibId(),
                "pads": [{"num": str(p.GetNumber()), "x": mm(p.GetPosition().x), "y": mm(p.GetPosition().y),
                          "drill": [mm(p.GetDrillSize().x), mm(p.GetDrillSize().y)] if p.HasHole() else None,
                          "plated": p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH} for p in fp.Pads()]}
        is_hole = pcb_common.is_mounting_hole(info, cfg_holes)
        if is_hole:
            holes_fp.add(ref)
        npads = 0
        for p in fp.Pads():
            npads += 1
            for sd, cu in (("top", pcbnew.F_Cu), ("bottom", pcbnew.B_Cu)):
                if p.IsOnLayer(cu) or p.HasHole():
                    lay = cu if p.IsOnLayer(cu) else (pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
                    polys = _pts(p.GetEffectivePolygon(lay, pcbnew.ERROR_INSIDE))
                    if not polys and p.HasHole():
                        pos, ds = p.GetPosition(), p.GetDrillSize()
                        r = max(mm(ds.x), mm(ds.y)) / 2
                        polys = [[(mm(pos.x) + r * math.cos(k * math.pi / 12), mm(pos.y) + r * math.sin(k * math.pi / 12))
                                  for k in range(24)]]
                    for poly in polys:
                        S[sd]["pads"].add(poly_box(poly), {"ref": ref, "num": str(p.GetNumber()), "poly": poly,
                                                          "hole": bool(p.HasHole())})
        body = pcb_common.fp_body_box(fp)
        part = pcb_common.fp_part_box(fp)
        needs = npads > 0 and not is_hole and not pcb_common.matches(ref, ignore)
        if part:
            S[side]["parts"].append({"ref": ref, "box": part, "body": body, "needs": needs, "hole": is_hole,
                                     "x": mm(fp.GetPosition().x), "y": mm(fp.GetPosition().y)})
        for f in fp.GetFields():
            if f.IsVisible() and f.GetLayer() in silk_side and f.GetText().strip():
                e = text_entry(f, "ref" if f.IsReference() else "field", ref, f.GetName())
                if e:
                    if e["kind"] == "ref":
                        e["owner"] = ref
                    S[silk_side[f.GetLayer()]]["texts"].append(e)
        for g in fp.GraphicalItems():
            if g.GetLayer() not in silk_side:
                continue
            sd = silk_side[g.GetLayer()]
            if g.GetClass() == "PCB_TEXT":
                e = text_entry(g, "fptext", ref)
                if e:
                    if e["text"].strip() == ref:
                        e["owner"] = ref                               # a footprint text that shows the reference
                    S[sd]["texts"].append(e)
            elif g.GetClass() == "PCB_SHAPE":
                e = graphic_entry(g, ref)
                if e:
                    S[sd]["graphics"].append(e)
    for d in board.GetDrawings():
        if d.GetLayer() not in silk_side:
            continue
        sd = silk_side[d.GetLayer()]
        if d.GetClass() == "PCB_TEXT":
            e = text_entry(d, "board", None)
            if e:
                toks = [t for t in re.split(r"[\s,;]+", e["text"]) if t]
                members = [t for t in toks if t in refs]
                if len(members) >= 2 and toks[0] in refs:
                    e["members"] = members
                elif toks and toks[0] in refs:
                    e["owner"] = toks[0]
                    e["named"] = len(toks) > 1
                S[sd]["texts"].append(e)
        elif d.GetClass() == "PCB_SHAPE":
            e = graphic_entry(d, None)
            if e:
                S[sd]["graphics"].append(e)
    def covered(via, mask):
        """Is the via covered by solder mask on this side? True, False, or None when this KiCad cannot say."""
        try:
            return bool(via.IsTented(mask))
        except TypeError:
            try:
                return bool(via.IsTented())
            except Exception:                                           # noqa: BLE001
                return None
        except Exception:                                               # noqa: BLE001
            return None

    vias = Index()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            for sd, cu, mask in (("top", pcbnew.F_Cu, pcbnew.F_Mask), ("bottom", pcbnew.B_Cu, pcbnew.B_Mask)):
                if t.IsOnLayer(cu):
                    r = mm(t.GetWidth(cu)) / 2
                    x, y = mm(p.x), mm(p.y)
                    vias.add((x - r, y - r, x + r, y + r), {"x": x, "y": y, "r": r, "side": sd, "covered": covered(t, mask)})
    ps, note = pcb_common.board_outline(board)
    outline = []
    if ps is not None:
        for poly in pcb_common.poly_points(ps):
            outline += [loop for loop in poly if len(loop) >= 3]
    return S, vias, outline, note, holes_fp


# ---- the ownership rules (labels read as their own part's) -----------------------------------------------------------
def kind_of(ref):
    return ref.rstrip("0123456789")


def _ov(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 0.0


def between(bx, others, lim):
    """The label lies between two other parts on opposite sides, each closer than `lim` and overlapping its span."""
    lft = rgt = abv = blw = False
    for pb in others:
        if _ov(pb[1], pb[3], bx[1], bx[3]):
            if pb[2] <= bx[0] + 1e-6 and bx[0] - pb[2] < lim:
                lft = True
            if pb[0] >= bx[2] - 1e-6 and pb[0] - bx[2] < lim:
                rgt = True
        if _ov(pb[0], pb[2], bx[0], bx[2]):
            if pb[1] >= bx[3] - 1e-6 and pb[1] - bx[3] < lim:
                abv = True
            if pb[3] <= bx[1] + 1e-6 and bx[1] - pb[3] < lim:
                blw = True
    return (lft and rgt) or (abv and blw)


def ownership(bx, cbox, ref, parts, L, own_max, margin=None, between_rule=True, same_kind=False):
    """Why the label at box bx does not read as the label of the part with box cbox; None when it does."""
    d_own = box_gap(bx, cbox)
    if d_own > own_max + 1e-9:
        return f"{d_own:.2f} mm from its part (limit {own_max:.2f})"
    cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
    above_below = bx[1] >= cbox[3] or bx[3] <= cbox[1]
    beside = bx[0] >= cbox[2] or bx[2] <= cbox[0]
    if above_below and beside:
        return "off a corner of its part"
    if above_below and not (cbox[0] <= cx <= cbox[2]):
        return "not lined up with its part"
    if beside and not (cbox[1] <= cy <= cbox[3]):
        return "not lined up with its part"
    dc_own = pt_box(cx, cy, cbox)
    m = L["own_margin"] if margin is None else margin
    others = []
    for p in parts:
        r, pb = p["ref"], p["box"]
        if r == ref or p["hole"] or (same_kind and kind_of(r) != kind_of(ref)):
            continue
        others.append(pb)
        if box_gap(bx, pb) < d_own - L["own_slack"]:
            return f"nearer {r} than its part"
        if pt_box(cx, cy, pb) < dc_own + m:
            return f"centre within {m} of {r} as of its part"
    if between_rule and between(bx, others, L["between"]):
        return "between two other parts"
    return None


def inline(a, b, read_gap):
    """Two text boxes on one line in the same reading direction, closer than read_gap along it."""
    wa, ha, wb, hb = a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1]
    if wa >= 0.9 * ha and wb >= 0.9 * hb:
        ov = min(a[3], b[3]) - max(a[1], b[1])
        if ov > 0.4 * min(ha, hb) and max(b[0] - a[2], a[0] - b[2]) < read_gap:
            return True
    if ha >= 0.9 * wa and hb >= 0.9 * wb:
        ov = min(a[2], b[2]) - max(a[0], b[0])
        if ov > 0.4 * min(wa, wb) and max(b[1] - a[3], a[1] - b[3]) < read_gap:
            return True
    return False


def token_boxes(t):
    """The part of a group text's box that carries each member's name: [(reference, box)], split by character
    position along the reading direction."""
    s, bx = t["text"], t["box"]
    n = len(s)
    horiz = (bx[2] - bx[0]) >= (bx[3] - bx[1])
    a = t["angle"]
    forward = (not (135 < a < 315)) if horiz else (45 < a <= 225)      # left to right; bottom to top
    if horiz and t["mirror"]:
        forward = not forward
    out, i = [], 0
    for tok in re.split(r"([\s,;]+)", s):
        j = i + len(tok)
        if tok in t["members"] and n:
            f0, f1 = i / n, j / n
            if horiz:
                w = bx[2] - bx[0]
                x0, x1 = (bx[0] + f0 * w, bx[0] + f1 * w) if forward else (bx[2] - f1 * w, bx[2] - f0 * w)
                out.append((tok, (x0, bx[1], x1, bx[3])))
            else:
                h = bx[3] - bx[1]
                y0, y1 = (bx[3] - f1 * h, bx[3] - f0 * h) if forward else (bx[1] + f0 * h, bx[1] + f1 * h)
                out.append((tok, (bx[0], y0, bx[2], y1)))
        i = j
    return out


def leaders_for(bx, target, segs):
    """Board-level silkscreen lines that join a label box to a part box."""
    return [s for s in segs if (pt_box(s[0], s[1], bx) < 0.3 and pt_box(s[2], s[3], target) < 0.35)
            or (pt_box(s[2], s[3], bx) < 0.3 and pt_box(s[0], s[1], target) < 0.35)]


# ---- the check -------------------------------------------------------------------------------------------------------
class Findings:
    def __init__(self):
        self.rows, self.crops = [], []

    def add(self, rule, side, what, x, y, measured=None, limit=None, size=8.0):
        self.rows.append({"rule": rule, "side": side, "what": what, "x": round(x, 3), "y": round(y, 3),
                          "measured": None if measured is None else round(measured, 3), "limit": limit})
        if len(self.crops) < MAX_CROPS and not any(c["side"] == side and abs(c["x"] - x) < 2 and abs(c["y"] - y) < 2
                                                    for c in self.crops):
            self.crops.append({"name": f"silk_{rule}_{len(self.crops) + 1}", "frame": "kicad", "side": side,
                               "x": round(x, 3), "y": round(y, 3), "size": size, "why": f"{rule}: {what}"})


def centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def label(t):
    s = t["text"].replace("\n", " / ")
    return f"'{s[:28]}'"


def run_check(board, L, cfg, cfg_holes):
    ignore = cfg.get("ignore_refs", IGNORE_REFS)
    S, vias, outline, outline_note, holes_fp = read_silk(board, cfg_holes, ignore)
    F = Findings()
    on = lambda k: L[k] >= 0                                            # noqa: E731
    groups = [g for g in cfg.get("group", []) if isinstance(g, dict) and g.get("refs")]
    group_of = {r: i for i, g in enumerate(groups) for r in g["refs"]}
    waived = {}
    for w in cfg.get("waiver", []):
        for r in w.get("refs", []):
            waived[r] = w
    allow_fields = set(cfg.get("allow_fields", []))
    info = {"texts": 0, "graphics": 0, "labels": 0, "grouped": [], "relaxed": [], "same_kind": [], "leaders": [],
            "group_texts": [], "opposite": [], "unlabelled": [], "waived": [], "groups": [],
            "outline_near_own_pad": 0, "outline_over_covered_via": 0, "outline_via_unknown": 0, "outline_via_items": [],
            "notes": []}
    table = []
    edge_segs = [(lp[i][0], lp[i][1], lp[(i + 1) % len(lp)][0], lp[(i + 1) % len(lp)][1]) for lp in outline
                 for i in range(len(lp))]

    def edge_dist(poly):
        if not edge_segs:
            return None
        n = len(poly)
        best = FAR
        for i in range(n):
            e = (poly[i][0], poly[i][1], poly[(i + 1) % n][0], poly[(i + 1) % n][1])
            for s in edge_segs:
                d = seg_seg(e, s)
                if d < best:
                    best = d
        cx, cy = centre(poly_box(poly))
        if sum(1 for lp in outline if inside(cx, cy, lp)) % 2 == 0:
            return 0.0                                                  # outside the board or in a cut-out
        return best

    labelled = {"top": set(), "bottom": set()}
    for side in ("top", "bottom"):
        D = S[side]
        texts, parts = D["texts"], D["parts"]
        pbox = {p["ref"]: p["box"] for p in parts}
        info["texts"] += len(texts)
        info["graphics"] += len(D["graphics"])
        gidx = Index()
        for g in D["graphics"]:
            gidx.add(g["box"], g)
        leaders = [g["seg"] for g in D["graphics"] if g["fp"] is None and g["seg"]]
        # ---- sizes
        for t in texts:
            cx, cy = centre(t["box"])
            if t["h"] < L["min_height"] - 1e-3:
                F.add("height", side, f"text {label(t)}: height {t['h']:.2f} mm", cx, cy, t["h"], L["min_height"])
            if t["th"] < L["min_line"] - 1e-3:
                F.add("line", side, f"text {label(t)}: line {t['th']:.2f} mm", cx, cy, t["th"], L["min_line"])
            if t["kind"] == "field" and t["name"] not in allow_fields:
                F.add("field", side, f"{t['fp']}: field {t['name']} {label(t)} is printed on the silkscreen", cx, cy)
        thin = {}
        for g in D["graphics"]:
            if 0 < g["width"] < L["min_line"] - 1e-3 and not g["solid"]:
                thin.setdefault(g["fp"] or "(board drawing)", []).append(g)
        for ref, gs in thin.items():
            cx, cy = centre(gs[0]["box"])
            F.add("line", side, f"{ref}: {len(gs)} silkscreen line(s) of {min(g['width'] for g in gs):.2f} mm", cx, cy,
                  min(g["width"] for g in gs), L["min_line"])
        # ---- clearances of every text
        for t in texts:
            bx, poly = t["box"], t["poly"]
            cx, cy = centre(bx)
            size = max(8.0, 1.6 * max(bx[2] - bx[0], bx[3] - bx[1]) + 4)
            row = {"side": side, "text": t["text"], "kind": t["kind"], "owner": t["owner"] or "+".join(t["members"]),
                   "x": round(cx, 2), "y": round(cy, 2), "h": t["h"], "line": t["th"]}
            is_mark = t["kind"] == "fptext" and not t["owner"]
            de = edge_dist(poly)
            row["edge"] = de
            if on("edge") and de is not None and de < L["edge"] - EPS:
                F.add("edge", side, f"text {label(t)}: {de:.2f} mm from the board edge", cx, cy, de, L["edge"], size)
            # pads without and with a hole
            for key, want_hole, name in (("pad", False, "a pad"), ("hole", True, "a hole or through-hole pad")):
                d, o = D["pads"].nearest(bx, lambda p, wh=want_hole: poly_dist(poly, p["poly"]) if p["hole"] == wh else FAR)
                ds = FAR
                if o is not None and t["strokes"]:
                    ds = min((D["pads"].nearest(poly_box(s), lambda p, s=s, wh=want_hole:
                                                poly_dist(s, p["poly"]) if p["hole"] == wh else FAR)[0]
                              for s in t["strokes"]), default=FAR) if d < 3.0 else FAR
                row[key], row[key + "_strokes"], row[key + "_what"] = d, ds, (f"{o['ref']}.{o['num']}" if o else "")
                lim_pad = L["graphic_pad"] if is_mark else L[key]       # a footprint's own mark: the outline rule
                if lim_pad >= 0 and d < lim_pad - EPS:
                    F.add(key, side, f"text {label(t)}: box {d:.2f} mm from {name} ({o['ref']}.{o['num']}); strokes "
                          f"{ds:.2f} mm", cx, cy, d, lim_pad, size)
            d, o = vias.nearest(bx, lambda v: poly_circle(poly, v["x"], v["y"], v["r"]) if v["side"] == side else FAR)
            ds = FAR
            if o is not None and d < 3.0:
                near_v = [v for _, v in vias.near(bx, d + 1.5) if v["side"] == side]
                ds = min((poly_circle(s, v["x"], v["y"], v["r"]) for s in t["strokes"] for v in near_v), default=FAR)
            row["via"], row["via_strokes"] = d, ds
            lim_via = L["mark_via"] if is_mark else L["via"]
            if lim_via >= 0 and d < lim_via - EPS:
                F.add("via", side, f"text {label(t)}: box {d:.2f} mm from via copper at ({o['x']:.2f}, {o['y']:.2f}); "
                      f"strokes {ds:.2f} mm", cx, cy, d, lim_via, size)
            # footprint outlines and part bodies
            if on("outline"):
                for gb, g in gidx.near(bx, L["outline"]):
                    if g["fp"] is None:
                        continue
                    d = polys_dist(g["polys"], poly)
                    if d < L["outline"] - EPS:
                        F.add("outline", side, f"text {label(t)}: {d:.2f} mm from the silkscreen outline of {g['fp']}",
                              cx, cy, d, L["outline"], size)
                        break
            if on("body"):
                for p in parts:
                    if p["body"] and not (t["kind"] in ("fptext", "field") and t["fp"] == p["ref"]):
                        d = box_gap(bx, p["body"])
                        if d < L["body"] - EPS:
                            F.add("body", side, f"text {label(t)}: {d:.2f} mm from the body of {p['ref']}"
                                  + (" (on or under it)" if d == 0 else ""), cx, cy, d, L["body"], size)
                            break
            table.append(row)
        # ---- text to text, and labels on one line
        tidx = Index()
        for i, t in enumerate(texts):
            tidx.add(t["box"], i)
        for i, t in enumerate(texts):
            for _, j in tidx.near(t["box"], max(L["text"], L["mark"], L["read_gap"], 0.0) + 0.1):
                if j <= i:
                    continue
                u = texts[j]
                mark_t = t["kind"] == "fptext" and not t["owner"]
                mark_u = u["kind"] == "fptext" and not u["owner"]
                if mark_t and mark_u and t["fp"] == u["fp"]:
                    continue                                            # two marks of one footprint (its own legend)
                same_group = t["owner"] in group_of and group_of.get(t["owner"]) == group_of.get(u["owner"])
                if mark_t != mark_u and (u["fp"] if mark_u else t["fp"]) != (t["owner"] if mark_u else u["owner"]):
                    key, lim = "mark", L["mark"]
                else:
                    key, lim = "text", (L["group_gap"] if same_group else L["text"])
                d = poly_dist(t["poly"], u["poly"])
                cx, cy = centre(pcb_common.box_union([t["box"], u["box"]]))
                if lim >= 0 and d < lim - EPS:
                    F.add(key, side, f"texts {label(t)} and {label(u)}: {d:.2f} mm apart", cx, cy, d, lim)
                elif on("read_gap") and (t["owner"] or u["owner"]) and t["owner"] != u["owner"] and not same_group \
                        and not t["members"] and not u["members"] and inline(t["box"], u["box"], L["read_gap"]):
                    F.add("one_line", side, f"labels {label(t)} and {label(u)} on one line within {L['read_gap']} mm: "
                          f"they read as one word", cx, cy, None, L["read_gap"])
        # ---- footprint outlines and marks
        for g in D["graphics"]:
            if g["fp"] is None:
                continue
            cx, cy = centre(g["box"])
            if on("graphic_pad"):
                near_own = False
                for _, p in D["pads"].near(g["box"], L["graphic_pad"]):
                    d = polys_dist(g["polys"], p["poly"])
                    if p["ref"] == g["fp"]:                             # its own part's pad: only on the pad
                        if d < EPS:
                            F.add("graphic_pad", side, f"{g['fp']} silkscreen outline lies on its own pad {p['ref']}.{p['num']}",
                                  cx, cy, d, 0.0, 6.0)
                            break
                        near_own = near_own or d < L["graphic_pad"] - EPS
                    elif d < L["graphic_pad"] - EPS:
                        F.add("graphic_pad", side, f"{g['fp']} silkscreen outline: {d:.2f} mm from pad {p['ref']}.{p['num']} "
                              f"of another part", cx, cy, d, L["graphic_pad"], 6.0)
                        break
                else:
                    info["outline_near_own_pad"] += near_own
            if on("graphic_edge") and edge_segs:
                d = min(edge_dist(p) for p in g["polys"])
                if d < L["graphic_edge"] - EPS:
                    F.add("graphic_edge", side, f"{g['fp']} silkscreen outline: {d:.2f} mm from the board edge", cx, cy,
                          d, L["graphic_edge"], 6.0)
            if on("graphic_via"):
                over = set()                                            # coverings of the vias this line is too near to
                for _, v in vias.near(g["box"], L["graphic_via"]):
                    if v["side"] != side:
                        continue
                    d = min(poly_circle(p, v["x"], v["y"], v["r"]) for p in g["polys"])
                    if d < L["graphic_via"] - EPS:
                        over.add(v["covered"])
                        if v["covered"] is not False and len(info["outline_via_items"]) < MAX_LISTED * 4:
                            info["outline_via_items"].append({"fp": g["fp"], "side": side, "x": round(v["x"], 3), "y": round(v["y"], 3),
                                                              "d": round(d, 3), "covered": v["covered"]})
                        if v["covered"] is False:                       # bare copper: a finding
                            F.add("graphic_via", side, f"{g['fp']} silkscreen outline: {d:.2f} mm from the copper of a via that "
                                  f"is not covered by solder mask, at ({v['x']:.2f}, {v['y']:.2f})", cx, cy, d, L["graphic_via"], 6.0)
                            break
                else:
                    info["outline_over_covered_via"] += True in over
                    info["outline_via_unknown"] += None in over and True not in over
        # ---- ownership
        lab = {}
        for t in texts:
            if t["owner"] and t["owner"] in pbox:
                lab.setdefault(t["owner"], t)
                labelled[side].add(t["owner"])
            elif t["owner"]:
                info["opposite"].append(f"{t['owner']} ({side} side label of a part on the other side)")
            for m in t["members"]:
                if m in pbox:
                    labelled[side].add(m)
        info["labels"] += len(lab)
        grouped = set()
        for gi, g in enumerate(groups):
            refs = [r for r in g["refs"]]
            if not all(r in lab for r in refs):
                if any(r in pbox for r in refs):
                    info["groups"].append(f"{g.get('name', gi)}: not every member has a label on the {side} side")
                continue
            cs = [centre(lab[r]["box"]) for r in refs]
            pc = [centre(pbox[r]) for r in refs]
            same = lambda vals: max(vals) - min(vals) < 0.05            # noqa: E731
            if g.get("kind", "col") == "col":
                ok = (same([lab[r]["box"][0] for r in refs]) or same([lab[r]["box"][2] for r in refs])) and \
                    all(abs(c[1] - p[1]) < 0.05 for c, p in zip(cs, pc))
            else:
                ok = (same([lab[r]["box"][1] for r in refs]) or same([lab[r]["box"][3] for r in refs])) and \
                    all(abs(c[0] - p[0]) < 0.05 for c, p in zip(cs, pc))
            info["groups"].append(f"{g.get('name', gi)}: {', '.join(refs)} ({'in group geometry' if ok else 'NOT in group geometry: judged one by one'})")
            if ok:
                others = [p for p in parts if p["ref"] not in refs and not p["hole"]]
                for r in refs:
                    grouped.add(r)
                    d_own = box_gap(lab[r]["box"], pbox[r])
                    if not all(box_gap(lab[r]["box"], p["box"]) >= d_own - 0.05 for p in others):
                        cx, cy = centre(lab[r]["box"])
                        F.add("ownership", side, f"{r} label (group '{g.get('name', gi)}'): a part outside the group is nearer",
                              cx, cy)
        info["grouped"] += sorted(grouped)
        for t in texts:
            cx, cy = centre(t["box"])
            if t["members"]:
                members = [m for m in t["members"] if m in pbox]
                if len(members) < 2:
                    continue
                union = pcb_common.box_union([pbox[m] for m in members])
                others = [p for p in parts if p["ref"] not in members]
                why = ownership(t["box"], union, "+".join(members), others, L, L["own_max"] + 0.4)
                ldg = leaders_for(t["box"], union, leaders)
                note = ""
                if why and ldg:
                    note = " (joined to its cluster by a leader line)"
                elif why and ownership(t["box"], union, "+".join(members), others, L, L["own_max"] + 0.4, margin=0.0,
                                       between_rule=False) is not None:
                    F.add("group_text", side, f"group text {label(t)}: {why}", cx, cy)
                elif why:
                    note = f" (relaxed: {why})"
                info["group_texts"].append(label(t) + note)
                if not ldg:
                    for m, tb in token_boxes(t):
                        if m not in pbox:
                            continue
                        d_own = box_gap(tb, pbox[m])
                        for p in parts:
                            if p["ref"] != m and not p["hole"] and box_gap(tb, p["box"]) < d_own - L["own_slack"]:
                                F.add("group_text", side, f"group text {label(t)}: '{m}' sits nearer {p['ref']} than {m}", cx, cy)
                                break
                continue
            o = t["owner"]
            if not o or o not in pbox or o in grouped or lab.get(o) is not t or L["own_max"] < 0:
                continue
            om = L["own_max"] + (0.4 if t.get("named") else 0.0)
            why = ownership(t["box"], pbox[o], o, parts, L, om)
            if not why:
                continue
            if leaders_for(t["box"], pbox[o], leaders):
                info["leaders"].append(o)
            elif ownership(t["box"], pbox[o], o, parts, L, om, margin=0.0, between_rule=False) is None:
                info["relaxed"].append(f"{o} ({why})")
                if not L["accept_relaxed"]:
                    F.add("ownership", side, f"{o} label: {why} (nearer its own part than any other, without the margin)", cx, cy)
            elif ownership(t["box"], pbox[o], o, parts, L, om, same_kind=True) is None:
                info["same_kind"].append(f"{o} ({why})")
                if not L["accept_same_kind"]:
                    F.add("ownership", side, f"{o} label: {why} (reads as its own only among parts of its kind)", cx, cy)
            else:
                F.add("ownership", side, f"{o} label: {why}", cx, cy)
        # ---- parts without a label on their own side
        for p in sorted(parts, key=lambda q: pcb_common.natural(q["ref"])):
            if p["needs"] and p["ref"] not in labelled[side]:
                if p["ref"] in waived:
                    w = waived[p["ref"]]
                    info["waived"].append(f"{p['ref']} ({w.get('reason', 'no reason given')}; {w.get('approved', 'approval not recorded')})")
                else:
                    info["unlabelled"].append(p["ref"])
                    F.add("unlabelled", side, f"{p['ref']}: no label on the {side} silkscreen", p["x"], p["y"])
    # ---- information block
    info_rows = []
    all_text = [t["text"] for s in S.values() for t in s["texts"]]
    for want in cfg.get("info_block", []):
        ok = any(str(want) in s for s in all_text)
        info_rows.append((str(want), ok))
        if not ok:
            F.rows.append({"rule": "info_block", "side": "", "what": f"the text '{want}' is not on the silkscreen",
                           "x": 0, "y": 0, "measured": None, "limit": None})
    if info["outline_near_own_pad"]:
        info["notes"].append(f"{info['outline_near_own_pad']} footprint outline line(s) nearer than {L['graphic_pad']} mm to a pad of "
                             f"their own part, none on a pad: allowed (the stock library footprints keep about 0.09 mm)")
    if info["outline_over_covered_via"]:
        info["notes"].append(f"{info['outline_over_covered_via']} footprint outline line(s) over or within {L['graphic_via']} mm of "
                             f"a via that is covered by solder mask: listed, not failed (ink on a covered via is cosmetic)")
    if info["outline_via_unknown"]:
        info["notes"].append(f"{info['outline_via_unknown']} footprint outline line(s) over or within {L['graphic_via']} mm of a via "
                             f"whose covering this KiCad could not tell: listed, not failed; look at the solder-mask plot")
    return F, info, table, info_rows, outline_note, bool(edge_segs)


RULES = [("height", "Text height", "min_height"), ("line", "Line width of texts and silkscreen lines", "min_line"),
         ("pad", "Text box to pads", "pad"), ("hole", "Text box to holes and through-hole pads", "hole"),
         ("via", "Text box to via copper (marks inside a footprint: mark_via)", "via"), ("edge", "Text box to the board edge", "edge"),
         ("text", "Text box to another text", "text"), ("mark", "Label to another footprint's mark", "mark"),
         ("outline", "Text box to a footprint's silkscreen outline", "outline"), ("body", "Text box to a part body", "body"),
         ("graphic_pad", "Footprint outline to another part's pad (its own pads: not on the pad)", "graphic_pad"),
         ("graphic_edge", "Footprint outline to the board edge", "graphic_edge"),
         ("graphic_via", "Footprint outline to a via that is not covered by solder mask", "graphic_via"),
         ("ownership", "Label beside its own part", "own_max"), ("one_line", "Labels of different parts on one line", "read_gap"),
         ("group_text", "Group texts: each name beside its own part", None), ("unlabelled", "Parts without a label on their side", None),
         ("field", "Other fields printed on the silkscreen", None), ("info_block", "Information block texts", None)]


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Silkscreen check of a KiCad board (sizes, clearances on text boxes, label ownership).",
                              epilog="Limits come from board.toml [silk]; see the top of this file. "
                                     "Exit codes: 0 pass, 1 findings, 2 could not run.")
    for k in ("min_height", "min_line", "pad", "hole", "via", "edge", "text"):
        ap.add_argument("--" + k.replace("_", "-"), type=float, dest=k, help=f"limit in mm (default {DEFAULTS[k]})")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                           # no message box, ever: warnings go to stderr
    job = pcb_common.resolve(a)
    cfg = job.cfg("silk")
    L = pcb_common.Limits(cfg, DEFAULTS, {k: getattr(a, k) for k in ("min_height", "min_line", "pad", "hole", "via", "edge", "text")})
    with pcb_common.work_copy(job.board, "silk-check-") as copy:
        board = kicad_io.load_board(copy)
        F, info, table, info_rows, outline_note, has_edge = run_check(board, L, cfg, job.cfg("holes"))
    md = pcb_common.header("Silkscreen check", job, "silk_check.py")
    md += [f"{info['texts']} silkscreen texts and {info['graphics']} silkscreen lines on both sides; {info['labels']} labels "
           f"with an owner part. Text clearances are measured on each text's box; the distance of the printed strokes is "
           f"given beside it in the text table (JSON twin). Coordinates: KiCad's (mm)."
           + (" The covering of the vias by solder mask could not be read from this KiCad: a footprint outline over a via is "
              "a note here, never a finding." if info["outline_via_unknown"] else ""), "", "Limits (-1 = rule off):", ""]
    md += L.table() + [""]
    counts = {}
    for r in F.rows:
        counts[r["rule"]] = counts.get(r["rule"], 0) + 1
    md += ["| Rule | Limit (mm) | Findings | Result |", "|---|---|---|---|"]
    off = []
    for rule, title, key in RULES:
        lim = "" if key is None else (L[key] if not isinstance(L[key], bool) else "")
        if key is not None and isinstance(L[key], float) and L[key] < 0:
            off.append(title)
            md.append(f"| {title} | off | - | NOT CHECKED |")
            continue
        if rule == "info_block" and not info_rows:
            md.append(f"| {title} | | - | NOT CHECKED (no info_block in board.toml) |")
            continue
        if rule == "edge" and not has_edge:
            md.append(f"| {title} | {lim} | - | UNKNOWN ({outline_note or 'no closed board outline'}) |")
            counts["_unknown"] = counts.get("_unknown", 0) + 1
            continue
        n = counts.get(rule, 0)
        md.append(f"| {title} | {lim} | {n} | {'PASS' if n == 0 else 'FAIL'} |")
    n_fail = len(F.rows)
    result = pcb_common.verdict(n_fail, counts.get("_unknown", 0))
    md += ["", f"**Result: {result}** ({n_fail} finding(s), {len(info['unlabelled'])} part(s) without a label, "
           f"{len(info['waived'])} waived)", ""]
    if F.rows:
        md += ["## Findings", ""]
        for rule, title, _ in RULES:
            rows = [r for r in F.rows if r["rule"] == rule]
            if not rows:
                continue
            md += [f"### {title} ({len(rows)})", ""]
            for r in rows[:MAX_LISTED]:
                where = f" at ({r['x']:.2f}, {r['y']:.2f}) {r['side']}" if r["side"] else ""
                md.append(f"- {r['what']}{where}")
            if len(rows) > MAX_LISTED:
                md.append(f"- ... and {len(rows) - MAX_LISTED} more (all in the JSON twin)")
            md.append("")
    for key, title, text in (
            ("waived", "Parts without a label, waived in board.toml", ""),
            ("groups", "Labelled groups (board.toml)", "One aligned line outside a cluster, each label on its own part's row or column."),
            ("group_texts", "Group texts", "A text that names several parts; each name was tested against its own part."),
            ("leaders", "Labels joined to their part by a leader line", ""),
            ("relaxed", "Labels nearer their own part than any other, without the margin (or between two parts)",
             "Accepted only with accept_relaxed = true; for the visual reviewers to judge from the images."),
            ("same_kind", "Labels that read as their own part's only among parts of their kind",
             "Accepted only with accept_same_kind = true; for the visual reviewers to judge from the images."),
            ("opposite", "Labels on the side opposite to their part", "Not tested for ownership.")):
        if info[key]:
            md += [f"## {title} ({len(info[key])})", ""] + ([text, ""] if text else []) + [f"- {x}" for x in info[key]] + [""]
    if info["notes"]:
        md += [f"## Notes: listed, not failed ({len(info['notes'])})", ""] + [f"- {x}" for x in info["notes"]] + [""]
    if info_rows:
        md += ["## Information block", ""] + [f"- '{w}': {'on the board' if ok else 'NOT FOUND'}" for w, ok in info_rows] + [""]
    md += ["## Not checked", "",
           "Labels hidden under a 3D body larger than the footprint's drawing; polarity and pin-1 marks; pin legends "
           "against the netlist; the meaning of any text" + ("; switched off: " + ", ".join(off) if off else "") +
           ". Look at the silkscreen plots and tiles of both sides (review_images.py)."]
    data = {"script": "silk_check.py", "result": result, "board": os.path.basename(job.board),
            "sha256": kicad_io.sha256(job.board), "limits": L.to_dict(), "findings": F.rows, "info": info,
            "texts": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in table],
            "crops": F.crops}
    p_md, _ = pcb_common.write_result(job.out, "silk_check", md, data)
    for rule, title, _ in RULES:
        if counts.get(rule):
            print(f"FAIL  {title}: {counts[rule]}")
    print(f"{result}: {n_fail} finding(s), {info['texts']} texts -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
