"""Placement rotation and origin of every assembled part, derived from JLCPCB's own library footprint.

What it does
    derive   For each part the assembler will place: JLCPCB's library footprint for the part's LCSC number (cached
             in a vendor folder, see fetch_parts.py) is turned in steps of 90 degrees and moved until its pads lie
             on the pads of the board's footprint, pin 1 on pin 1 (pads matched by number; polarised two-pin parts
             by their marked terminal, see "Polarity mark" below). The turn and the origin with the smallest pad
             error are the values for the placement file. Writes the table jlc/rotations.md and jlc/rotations.json.
             A fit is DERIVED only when it proves enough:
               - at least two anchors (common pads) at different places; one place cannot fix a turn;
               - no other turn fits within the limit while putting JLCPCB's pads on other pins (else AMBIGUOUS);
               - the pad error is within the package's limit: pad_tolerance_fraction (0.75) times the smaller side
                 of the pads involved, at most pad_tolerance_mm (0.6 mm); above it the part is FAIL;
               - every electrical pad of ours has a counterpart in JLCPCB's footprint and the other way round (a pad
                 of the other footprint on the same place, with the same number or a number that is no other pin
                 of ours), unless board.toml names it with a reason ([rotations.unmatched_pads.<LCSC number>]).
    test     Derives everything again and compares it with a placement file (CPL). Any difference fails: a
             rotation, a position, a part that is missing or one that must not be placed. It proves consistency
             with the derivation, not physical correctness: pin 1 and polarity are confirmed in the placement preview.

    A part without an LCSC number, without a cached library footprint, or whose polarity mark cannot be found is
    UNKNOWN. It is listed with the reason and never given an assumed rotation. The project may then write its own
    decision for that part into board.toml ([rotations.declared.<REF>]); the table shows it as DECLARED, NOT
    MEASURED (pad error and pads matched null) in a table of its own, and its preview check stays mandatory.

    Polarity mark: every two-pin part whose footprint name (ours or JLCPCB's) is that of a polarised part (CP_...,
    D_..., LED..., ...TANTAL..., ...ELEC..., ...POLAR..., ...DIODE...), or whose reference matches mark_fit_refs, is
    fitted by its mark, never by pad number: JLCPCB's marked pad goes on ours. The mark is read in BOTH footprints'
    silkscreen: a band across the body between the pads, an outline closed at one end only, a plus sign, chamfered
    corners (an electrolytic). It marks pin 1: a diode's cathode, a polarised capacitor's plus (a plus sign at a
    diode or LED marks its anode, the other pad). Where either footprint has no readable mark, or its marks
    disagree, or our mark is not at our pad 1 (KiCad's convention, also K or +), the part is UNKNOWN ("polarity mark
    not found ...") with no rotation. [rotations.marked_pad] names JLCPCB's marked pad by hand.

    Panel: on a board made by panel.py (its own PANEL_* footprints, every other reference <ref>_<n>) each copy takes
    the board.toml entries of <ref> (declared, hand_fit, dnp, ignore), and the bottom-side mapping is written with
    the board's references, so copies equal to the single board keep its confirmation.

Why it exists (a real failure, told without names)
    The assembler places each part by the rotation and position in the placement file, measured against the
    footprint in ITS library, not against the KiCad footprint. Library footprints differ in their 0-degree
    direction, their origin and sometimes their pad numbers. When rotations come from a generic community table,
    three-pin parts can be placed turned, a polarised capacitor reversed, and a diode whose library footprint
    numbers the cathode "2" turned by pad-number matching; every assembled board would be scrap, and only a
    review would catch it. This is the check.

Usage
    python -I jlc_rotations.py --project <hardware/board folder> derive
    python -I jlc_rotations.py --project <hardware/board folder> test [--cpl FILE]
    python -I jlc_rotations.py --out <folder> [--vendor DIR] [--bom FILE] derive <board.kicad_pcb>
    python -I jlc_rotations.py --out <folder> [--vendor DIR] [--bom FILE] test   <board.kicad_pcb> --cpl FILE
    python -I jlc_rotations.py --project <board folder> --out <board folder>/out/panel --bom <panel BOM>
                               test <panel board> --cpl <panel placement file>       a panel made by panel.py
    (every option except --cpl stands BEFORE the word derive or test). --project gives the footprint folder and
    board.toml; without --project and --vendor there is no footprint folder and every part is UNKNOWN (said so).

    Works on any KiCad board. The board is copied to a private folder and the copy is loaded; the design folder is
    never written to. Needs KiCad's Python (the script starts itself again with it). Results go to
    <project>/out/jlc/ or <out>/jlc/: rotations.md, rotations.json (derive), rotations_test.md / .json (test).

    Which parts are placed: every footprint of the board that is not marked "do not populate", not excluded from
    position files, not on the hand-fit, DNP or ignore lists of board.toml. With --bom (a table with designator
    and LCSC number columns) only the designators of that table are placed, and its numbers are used.
    The LCSC number is read from the footprint field named by --lcsc-field (default: see jlc_parts.LCSC_FIELDS).

    Coordinates: KiCad's page frame in mm with Y pointing up (Y negated), the frame of Gerbers plotted with
    absolute coordinates. Bottom-side parts: the angle is derived counter-clockwise as seen from the bottom; that
    convention was never proven on a real order with this script, so such parts stay UNKNOWN, with their candidate
    angles, until the project records that it saw them in JLCPCB's placement preview, bound to this board: the
    checksum of the bottom-side mapping (bottom_side.sha256 in rotations.json), a date and the preview crop. A
    changed bottom-side mapping (another part, footprint, angle or origin offset) needs a new confirmation.
    fab_package.py --preview makes the provisional package for that preview (PREVIEW ONLY, NOT FOR ORDER).

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [rotations]
    vendor = "vendor/jlc_fp"        # folder with <LCSC number>.pretty/ footprints
    origin = "bbox"                 # how the origin is fitted: "bbox" (centres of the pad patterns' bounding
                                    # boxes) or "mean" (mean of the matched pads)
    pad_tolerance_fraction = 0.75   # pad limit: this fraction of the smaller side of the pads involved ...
    pad_tolerance_mm = 0.6          # ... but never more than this (library variants differ in lead span)
    mark_fit_refs = ["D*", "LED*"]  # two-pin parts with these references are fitted by the polarity mark, besides
                                    # every two-pin part with a polarised footprint name (see "Polarity mark")
    [[rotations.bottom_side_confirmed]]   # one per board revision whose bottom side was seen in the preview
    bottom_sha256 = "..."           #   bottom_side.sha256 of rotations.json (also in the preview package)
    date = "YYYY-MM-DD"             #   the day of the preview
    evidence = "reviews/preview_bottom.png"   # the preview crop, relative to the board folder; must exist
    #   (the old "bottom_side_checked = true" is read as not bound to a board: it unlocks nothing)
    [rotations.unmatched_pads.C12345]   # pads without a counterpart that are right, with the reason
    ours = ["5"]   theirs = ["9"]   reason = "..."
    [rotations.fit_pads]            # LCSC number -> pad numbers that mean the same pin in both libraries
    C12345 = ["1", "2", "3", "4"]   #   (when the libraries number or anchor some pads differently)
    [rotations.marked_pad]          # LCSC number -> the pad of JLCPCB's footprint at the marked end (a diode's
    C54321 = "2"                    #   cathode, a capacitor's plus), when no mark can be read in its drawing
    [rotations.declared.F9]         # the project's own, written decision for one part
    rotation_offset = 0             #   added to KiCad's rotation (or: rotation = <absolute angle>)
    reason = "non-polar two-pad part without library data; checked in the placement preview on <date>"
    [bom]
    assembly_file = "out/bom_jlcpcb.csv"   # optional BOM table that decides what is placed
    lcsc_field = "LCSC"   hand_fit = [...]   dnp = [...]   ignore = [...]      (as in jlc_parts.py)

Exit codes
    0  derive: every placed part derived or declared, every pad error inside its limit; test: no difference
    1  findings: an UNKNOWN part, a part that does not fit (FAIL), a difference to the placement file
    2  could not run: no board, KiCad's Python missing, unreadable input, neither --project nor --out

Not checked: that JLCPCB's production library equals the cached footprint (one case on record differed: the
assembler's engineer may still turn a part; verify pin 1 against the pads in the placement preview, never against
the angle number); the polarity of your own footprint's pad 1 when its silkscreen mark agrees with it (a footprint
drawn wrong in both ways); a polarised part whose footprints carry no polarised name and whose reference is not in
mark_fit_refs (it is fitted by pad number).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import csv
import datetime
import fnmatch
import hashlib
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
from jlc_parts import LCSC_FIELDS, MPN_FIELDS, Bom, natural, read_csv  # noqa: E402
from jlc_parts import CannotRun as _BomError  # noqa: E402

TOLERANCE = 0.6                     # mm: the cap of the pad limit (large pads: lead-span variants, 2.50 / 2.54 pitch)
TOL_FRACTION = 0.75                 # pad limit = this x the smaller side of the pads involved, at most TOLERANCE.
#   In the tests the largest error seen was 0.67 x the smaller side (a SOT-23 library variant whose pads lie
#   0.40 mm further out along the lead, on 0.6 mm wide pads); a pad pattern of another span misses by a whole pitch.
MARK_FIT = ["D*", "LED*"]           # references fitted by the polarity mark whatever their footprints are called
POS_TOL = 0.01                      # mm: placement file against the derivation
_LCSC_RE = re.compile(r"^C\d{1,10}$")
_POLAR_NAMES = ("cp_", "d_", "led", "diode", "polar", "tantal", "elec")
_COPY_RE = re.compile(r"^(.+)_(\d+)$")              # a copy <ref>_<n> on a panel made by panel.py
_PANEL_OWN = "PANEL_"                               # panel.py's own footprints: mouse bites, fiducials, tooling holes


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _words(name: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", str(name).lower()) if w]


def polar_name(name: str) -> bool:
    """A footprint name of a polarised two-pin part, after the words of _POLAR_NAMES as KiCad's and JLCPCB's
    libraries use them: the first word CP or D (CP_Elec_..., D_SOD-123), a word that begins with LED, TANTAL, ELEC
    or POLAR, or one that holds DIODE. Read by words, so that IND-SMD_... (an inductor) is no diode."""
    w = _words(name)
    return bool(w) and (w[0] in ("cp", "d") or any(x.startswith(("led", "tantal", "elec", "polar")) or "diode" in x
                                                     for x in w))


def part_kind(ref: str, names: list[str]) -> str:
    """'cap' for a polarised capacitor (its marked terminal is the plus), 'diode' for a diode or LED (the marked
    terminal is the cathode, a plus sign stands at the anode), '' when reference and names do not tell."""
    words = [_words(n) for n in names]
    cap = any(w and (w[0] == "cp" or any(x.startswith(("tantal", "elec", "polar")) for x in w)) for w in words) \
        or re.match(r"C\d", ref) is not None
    diode = any(w and (w[0] == "d" or any(x.startswith("led") or "diode" in x for x in w)) for w in words) \
        or re.match(r"(D|LED)\d", ref) is not None
    return "cap" if cap and not diode else "diode" if diode and not cap else ""


def panel_copies(refs: list[str]) -> dict[str, str]:
    """{reference: the board's reference} on a panel made by panel.py: at least one of its own PANEL_* footprints,
    and every other reference of the form <ref>_<n>. Empty for any other board."""
    rest = [r for r in refs if not r.startswith(_PANEL_OWN)]
    hits = {r: _COPY_RE.match(r) for r in rest}
    if len(rest) == len(refs) or not rest or not all(hits.values()):
        return {}
    return {r: m.group(1) for r, m in hits.items() if m}


def _rot(x: float, y: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def _angle(v: float):
    v = v % 360
    return int(round(v)) if abs(v - round(v)) < 1e-9 else round(v, 3)


def _bar(pts: list) -> tuple | None:
    """The centre line of a thin rectangle (a filled bar: some libraries draw a band or a plus sign so), or None."""
    if len(pts) == 5 and math.hypot(pts[0][0] - pts[4][0], pts[0][1] - pts[4][1]) < 1e-6:
        pts = pts[:4]
    if len(pts) != 4:
        return None
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    e1, e2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
    if min(e1, e2) <= 0 or max(e1, e2) < 2.5 * min(e1, e2) or abs(math.hypot(x2 - x0, y2 - y0) - math.hypot(e1, e2)) > 0.01:
        return None
    cx, cy = (x0 + x1 + x2 + x3) / 4, (y0 + y1 + y2 + y3) / 4
    ux, uy, ln = ((x1 - x0) / e1, (y1 - y0) / e1, e1) if e1 >= e2 else ((x2 - x1) / e2, (y2 - y1) / e2, e2)
    return cx - ux * ln / 2, cy - uy * ln / 2, cx + ux * ln / 2, cy + uy * ln / 2


def silk_strokes(fp, pcbnew, layer, sx: float) -> tuple[list, list]:
    """(straight strokes, places of '+' texts) of a footprint's silkscreen on `layer`, in the fit's frame (X times
    sx, Y up): lines, and thin filled rectangles by their centre line. Arcs and circles carry no mark here."""
    segs, plus = [], []
    mm = pcbnew.ToMM
    for g in fp.GraphicalItems():
        try:
            if g.GetLayer() != layer:
                continue
            if g.GetClass() == "PCB_SHAPE" and g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                a, b = g.GetStart(), g.GetEnd()
                segs.append((sx * mm(a.x), -mm(a.y), sx * mm(b.x), -mm(b.y)))
            elif g.GetClass() == "PCB_SHAPE" and g.GetShape() in (pcbnew.SHAPE_T_POLY, pcbnew.SHAPE_T_RECT):
                if g.GetShape() == pcbnew.SHAPE_T_RECT:
                    a, b = g.GetStart(), g.GetEnd()
                    pts = [(a.x, a.y), (b.x, a.y), (b.x, b.y), (a.x, b.y)]
                else:
                    ol = g.GetPolyShape().Outline(0)
                    pts = [(ol.CPoint(i).x, ol.CPoint(i).y) for i in range(ol.PointCount())]
                bar = _bar([(sx * mm(x), -mm(y)) for x, y in pts])
                if bar:
                    segs.append(bar)
            elif g.GetClass() in ("PCB_TEXT", "FP_TEXT") and g.GetText().strip() == "+":
                q = g.GetPosition()
                plus.append((sx * mm(q.x), -mm(q.y)))
        except Exception:  # noqa: BLE001 - an item another KiCad version describes otherwise is not read
            continue
    return segs, plus


def read_mark(pads: dict, segs: list, plus_at: list, kind: str) -> tuple:
    """(pad, how, disagree) of the marked terminal of a two-pin footprint, read from its silkscreen. Libraries mark
    pin 1, which is a diode's cathode and a polarised capacitor's plus (KiCad's pad 1 of both):
      band          a straight line across the body between the pads, away from the middle;
      closed end    the outline closed by a line across beyond one pad only (KiCad's diodes, LEDs and tantalums);
      plus sign     two crossing strokes or a '+' text: a capacitor's plus; at a diode or LED it marks the anode, so
                    the marked terminal is the other pad (read only when reference or names tell the kind);
      chamfered corners  at one end of the outline: an electrolytic's plus (capacitors only).
    A line at both ends at the same distance is the outline, no mark. pad None: no mark (disagree False) or marks
    that point at different pads (disagree True); `how` then says why."""
    (n1, (x1, y1)), (n2, (x2, y2)) = sorted(pads.items())
    span = math.hypot(x2 - x1, y2 - y1)
    if span < 1e-6:
        return None, "the two pads lie on one place", False
    ux, uy = (x2 - x1) / span, (y2 - y1) / span
    mx, my, half = (x1 + x2) / 2, (y1 + y2) / 2, span / 2

    def ac(x, y):                                   # along the pads (n2 positive), across them
        return (x - mx) * ux + (y - my) * uy, -(x - mx) * uy + (y - my) * ux

    def end(a):
        return n2 if a > 0 else n1
    strokes = []
    for xa, ya, xb, yb in segs:
        (a1, c1), (a2, c2) = ac(xa, ya), ac(xb, yb)
        ln = math.hypot(a2 - a1, c2 - c1)
        if ln >= 0.05:
            strokes.append({"a": (a1 + a2) / 2, "c": (c1 + c2) / 2, "da": abs(a2 - a1), "dc": abs(c2 - c1), "len": ln,
                            "cmax": max(abs(c1), abs(c2)), "plus": False})
    along = [s for s in strokes if s["dc"] < 0.02]
    across = [s for s in strokes if s["da"] < 0.02]
    plus = [ac(x, y)[0] for x, y in plus_at]
    for s in along:
        for t in across:
            if 0.3 <= min(s["len"], t["len"]) and max(s["len"], t["len"]) <= min(2.5, 2.5 * min(s["len"], t["len"])) \
                    and math.hypot(s["a"] - t["a"], s["c"] - t["c"]) <= 0.15:
                plus.append((s["a"] + t["a"]) / 2)
                s["plus"] = t["plus"] = True

    def ends(places: list, outline: bool) -> set:
        keep = [a for a in places if not (outline and any(abs(a + b) < 0.05 for b in places))]
        return {end(a) for a in keep}
    found, clash = [], []
    band = ends([s["a"] for s in across if not s["plus"] and s["len"] > 0.8 and 0.3 < abs(s["a"]) < half - 1e-6], True)
    if len(band) == 1:
        found.append(("band", band.pop()))
    elif band:
        clash.append("bands at both pads")
    closed = ends([s["a"] for s in across if not s["plus"] and s["len"] >= 0.8 and abs(s["a"]) >= half - 1e-6], True)
    if len(closed) == 1:                            # closed at both ends: an outline, not a mark
        found.append(("closed end", closed.pop()))
    if kind:
        sides = ends([a for a in plus if abs(a) > 0.3], False)
        if len(sides) == 1:
            p = sides.pop()
            found.append(("plus sign", p) if kind == "cap" else ("plus sign at the anode", n1 if p == n2 else n2))
        elif sides:
            clash.append("plus signs at both pads")
    if kind == "cap":
        cmax = max([s["cmax"] for s in strokes] or [0.0])
        sides = ends([s["a"] for s in strokes if not s["plus"] and s["len"] >= 0.3 and 0.42 <= s["dc"] / s["len"] <= 0.91
                      and abs(s["c"]) >= 0.6 * cmax and abs(s["a"]) > 0.3], False)
        if len(sides) == 1:
            found.append(("chamfered corners", sides.pop()))
    marked = {p for _, p in found}
    if clash or len(marked) > 1:
        return None, "; ".join(clash + [f"{h} at pad {p}" for h, p in found]), True
    if not found:
        return None, ("no band, closed outline end, plus sign or chamfered corners" if kind == "cap" else
                      "no band, closed outline end or plus sign" if kind else "no band or closed outline end"), False
    return found[0][1], " and ".join(h for h, _ in found), False


def anchors_of(ours: dict, theirs: dict, common: list) -> list:
    """The pads the origin is fitted on: those whose number is unique in both footprints (a tab or exposed pad that
    shares a number is judged afterwards, by its nearest pad), else all common ones."""
    return [n for n in common if len(ours[n]) == 1 and len(theirs[n]) == 1] or common


def fit_turns(ours: dict, theirs: dict, common: list, phis: list, origin: str) -> list:
    """(pad error, turn, origin x, origin y) of JLCPCB's pads onto ours for every turn in `phis`, in that order.
    The pad error is the largest miss over all common pads."""
    unique = anchors_of(ours, theirs, common)
    pairs_src = [(n, ours[n], theirs[n]) for n in common]
    out = []
    for phi in phis:
        ox = [ours[n][0] for n in unique]
        tx = [_rot(theirs[n][0][0], theirs[n][0][1], phi) for n in unique]
        if not ox or not tx:
            continue
        if origin == "mean":
            cqx = sum(p[0] for p in ox) / len(ox) - sum(p[0] for p in tx) / len(tx)
            cqy = sum(p[1] for p in ox) / len(ox) - sum(p[1] for p in tx) / len(tx)
        else:
            # the centres of the two pad patterns' bounding boxes: a mean weights the side with more pads and
            # shifts the origin of an asymmetric package by some hundredths of a millimetre
            cqx = (min(p[0] for p in ox) + max(p[0] for p in ox)) / 2 - (min(p[0] for p in tx) + max(p[0] for p in tx)) / 2
            cqy = (min(p[1] for p in ox) + max(p[1] for p in ox)) / 2 - (min(p[1] for p in tx) + max(p[1] for p in tx)) / 2
        worst = 0.0
        for n, a, t in pairs_src:
            tt = [(_rot(pt[0], pt[1], phi)[0] + cqx, _rot(pt[0], pt[1], phi)[1] + cqy) for pt in t]
            for pa in a:
                worst = max(worst, min(math.hypot(pa[0] - q[0], pa[1] - q[1]) for q in tt))
        out.append((worst, phi, cqx, cqy))
    return out


def _pads(fp, pcbnew, sx: float) -> list[dict]:
    """Every pad of a footprint: number ("m": the number it is matched by), centre in the fit's frame (Y up, X times
    sx), smaller side and reach (box diagonal) in mm, net, electrical (numbered and not a bare hole)."""
    out = []
    for p in fp.Pads():
        q, bb = p.GetPosition(), p.GetBoundingBox()
        side = None
        try:
            if p.GetShape() != pcbnew.PAD_SHAPE_CUSTOM:      # a custom pad's own size is only its anchor
                s = p.GetSize()
                side = pcbnew.ToMM(min(s.x, s.y))
        except (TypeError, AttributeError):                 # another KiCad version: the copper box decides
            pass
        if side is None:
            side = pcbnew.ToMM(min(bb.GetWidth(), bb.GetHeight()))
        n = p.GetNumber()
        out.append({"n": n, "m": n, "x": sx * pcbnew.ToMM(q.x), "y": -pcbnew.ToMM(q.y), "side": side,
                    "reach": pcbnew.ToMM(math.hypot(bb.GetWidth(), bb.GetHeight())), "net": p.GetNetname(),
                    "pad": p, "elec": bool(n) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH})
    return out


def _hit(pad, x: float, y: float, sx: float, pcbnew) -> bool:
    """Is the point (x, y) of the fit's frame inside the copper of `pad`?"""
    try:
        return bool(pad.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(sx * x), pcbnew.FromMM(-y))))
    except Exception:  # noqa: BLE001 - another KiCad version: the distance test alone decides
        return False


def _meet(o: dict, t: dict, f: tuple, limit: float, sx: float, pcbnew) -> bool:
    """Do our pad o and JLCPCB's pad t lie on one another after the fit f: centres within the limit, or the centre
    of one inside the copper of the other?"""
    _, phi, cx, cy = f
    tx, ty = _rot(t["x"], t["y"], phi)
    tx, ty = tx + cx, ty + cy
    d = math.hypot(o["x"] - tx, o["y"] - ty)
    if d <= limit + 1e-9:
        return True
    if d > (o["reach"] + t["reach"]) / 2:
        return False
    vx, vy = _rot(o["x"] - cx, o["y"] - cy, -phi)
    return _hit(o["pad"], tx, ty, sx, pcbnew) or _hit(t["pad"], vx, vy, 1.0, pcbnew)


def _pin_ok(o: dict, t: dict, nets: dict) -> bool:
    """JLCPCB's pad t may stand for our pad o: the same number, or a number that is no other pin of ours, or a
    number of ours on the same net."""
    return t["m"] == o["n"] or t["m"] not in nets or bool(o["net"] and o["net"] in nets[t["m"]])


def _landing(op: list, tp: list, f: tuple, limit: float, sx: float, pcbnew) -> list:
    """For each electrical pad of JLCPCB's footprint: the numbers of our pads it lies on after the fit f."""
    return [frozenset(o["n"] for o in op if o["elec"] and _meet(o, t, f, limit, sx, pcbnew)) for t in tp if t["elec"]]


def _same_pins(a: list, b: list, nets: dict) -> bool:
    """Two turns put every pad of JLCPCB's footprint on the same pins of ours, or on pins of the same nets."""
    for x, y in zip(a, b):
        if x == y:
            continue
        nx = set().union(*(nets.get(n, set()) for n in x)) - {""}
        ny = set().union(*(nets.get(n, set()) for n in y)) - {""}
        if not (x and y and nx and nx == ny):
            return False
    return True


def _lcsc_of(fp, want: list[str]) -> str:
    fields = {}
    for f in fp.GetFields():
        fields[_key(f.GetName())] = f.GetText().strip()
    return next((fields[k] for k in want if fields.get(k)), "")


def derive(board_path: str, cfg: dict) -> dict:
    """The derivation of one board. Needs pcbnew. Returns the result dictionary (what rotations.json holds)."""
    import pcbnew
    with kicad_io.private_tmp("jlc-rotations-") as tmp:
        copy = os.path.join(tmp, os.path.basename(board_path))
        kicad_io.copy_board(board_path, copy, lock_source=False)       # nothing is written beside the design
        board = kicad_io.load_board(copy)
        return _derive(board, pcbnew, board_path, cfg)


def _derive(board, pcbnew, board_path: str, cfg: dict) -> dict:
    want = [_key(n) for n in cfg["lcsc_fields"]]
    bom_code: dict[str, str] | None = None
    notes: list[str] = []
    if cfg["bom"]:
        bom = Bom()
        try:
            read_csv(cfg["bom"], bom, cfg["lcsc_fields"], MPN_FIELDS, "board")
        except _BomError as e:
            raise kicad_io.KicadIOError(str(e)) from None
        bom_code = {}
        for ln in bom.lines:
            for r in ln["refs"]:
                bom_code[r] = ln["lcsc"]
        notes += bom.notes
        if bom.duplicates:
            notes.append("designators that appear twice in the BOM table: " + ", ".join(bom.duplicates))
    parts: dict[str, dict] = {}
    skipped: dict[str, list[str]] = {"dnp": [], "excluded_from_position_files": [], "hand_fit": [], "ignored": [],
                                     "not_in_bom": []}
    on_board = set()
    fps = sorted(board.GetFootprints(), key=lambda f: natural(f.GetReference()))
    copies = panel_copies([f.GetReference() for f in fps])          # a panel: <ref>_<n> reads board.toml as <ref>
    if copies:
        notes.append(f"panel made by panel.py: {len(set(copies.values()))} part(s) of the board in "
                     f"{len({_COPY_RE.match(r).group(2) for r in copies})} copies; each copy <ref>_<n> takes the "
                     "board.toml entries of <ref> (declared parts, hand-fit, DNP and ignore lists) and the bottom-side "
                     "confirmation of the single board")
    for fp in fps:
        ref = fp.GetReference()
        base = copies.get(ref, ref)
        on_board.add(ref)
        if any(fnmatch.fnmatchcase(ref, pat) or fnmatch.fnmatchcase(base, pat) for pat in cfg["ignore"]):
            skipped["ignored"].append(ref)
            continue
        if fp.IsDNP() or ref in cfg["dnp"] or base in cfg["dnp"]:
            skipped["dnp"].append(ref)
            continue
        if ref in cfg["hand_fit"] or base in cfg["hand_fit"]:
            skipped["hand_fit"].append(ref)
            continue
        if bom_code is not None:
            if ref not in bom_code:
                skipped["not_in_bom"].append(ref)
                continue
        elif fp.IsExcludedFromPosFiles():
            skipped["excluded_from_position_files"].append(ref)
            continue
        if ref in parts:
            parts[ref].update(status="UNKNOWN", reason=f"the reference {ref} is on the board more than once")
            continue
        parts[ref] = _one(fp, pcbnew, cfg, want, bom_code, notes, base)
    bom_only = sorted((r for r in (bom_code or {}) if r not in on_board), key=natural)
    bottom = bottom_side(parts, cfg, copies)
    over = sorted((r for r, p in parts.items() if p["status"] == "FAIL"), key=natural)
    unknown = [r for r, p in parts.items() if p["status"] == "UNKNOWN"]
    verdict = "PASS" if parts and not unknown and not over and not bom_only else "FAIL"
    bottom["only_reason"] = bool(unknown) and not over and not bom_only and all(parts[r].get("candidate") for r in unknown)
    return {
        "check": "jlc_rotations", "result": verdict,
        "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "board": os.path.basename(board_path), "board_sha256": kicad_io.sha256(board_path),
        "kicad_version": kicad_io.kicad_version(),
        "settings": {"origin": cfg["origin"], "pad_tolerance_mm": cfg["tolerance"],
                     "pad_tolerance_fraction": cfg["fraction"], "vendor": cfg["vendor_shown"],
                     "bom": os.path.basename(cfg["bom"]) if cfg["bom"] else None, "mark_fit_refs": cfg["mark_fit"],
                     "bottom_side_checked": cfg["bottom_old"], "note": cfg["settings_note"]},
        "counts": {"placed": len(parts), "derived": sum(p["status"] == "DERIVED" for p in parts.values()),
                   "declared": sum(p["status"] == "DECLARED" for p in parts.values()), "unknown": len(unknown),
                   "pad_error_above_tolerance": len(over)},
        "parts": parts, "pad_error_above_tolerance": over, "declared": sorted(
            (r for r, p in parts.items() if p["status"] == "DECLARED"), key=natural),
        "bottom_side": bottom, "not_placed": skipped, "in_bom_not_on_board": bom_only, "notes": notes,
        "panel": {"copies": sorted({int(_COPY_RE.match(r).group(2)) for r in copies}),
                  "board_parts": len(set(copies.values()))} if copies else None,
    }


def bottom_side(parts: dict, cfg: dict, copies: dict | None = None) -> dict:
    """Bind the bottom-side confirmation to this board. Parts on the bottom whose fit passed wait as candidates; the
    checksum of their mapping (reference, LCSC number, library footprint, KiCad angle, placement angle, origin offset)
    must equal the bottom_sha256 of a recorded confirmation that has a date and an existing evidence file. Then the
    candidates become DERIVED; otherwise they stay UNKNOWN with the reason. Changes `parts` in place.
    On a panel (copies: {<ref>_<n>: <ref>}) the mapping is written with the board's references, each different row
    once: copies equal to the single board give its checksum; a copy that differs gives another one."""
    wait = sorted((r for r, p in parts.items() if p.get("candidate")), key=natural)
    out = {"parts": wait, "sha256": None, "confirmed": False, "confirmation": None, "old_switch": cfg["bottom_old"]}
    if not wait:
        return out
    table: list = []
    for r in wait:
        row = [(copies or {}).get(r, r), parts[r]["code"], parts[r]["jlc_footprint"], parts[r]["kicad_rot"],
               parts[r]["cpl_rot"], round(parts[r]["cpl_x"] - parts[r]["kicad_x"], 3),
               round(parts[r]["cpl_y"] - parts[r]["kicad_y"], 3)]
        if row not in table:
            table.append(row)
    table.sort(key=lambda row: natural(row[0]))     # stable: a single board keeps the order of its references
    sha = hashlib.sha256(json.dumps(table).encode("utf-8")).hexdigest()
    out["sha256"] = sha
    why = ""
    for c in cfg["bottom_confirmed"]:
        if str(c.get("bottom_sha256", "")).strip().lower() != sha:
            continue
        date, ev = str(c.get("date", "")).strip(), str(c.get("evidence", "")).strip()
        if not date or not ev:
            why = "the confirmation recorded for this checksum has no date or no evidence file (the preview crop)"
        elif not os.path.isfile(ev if os.path.isabs(ev) else os.path.join(cfg["root"] or "", ev)):
            why = f"the evidence file {ev} of the confirmation of {date} is not there"
        else:
            out.update(confirmed=True, confirmation={"bottom_sha256": sha, "date": date, "evidence": ev})
            for r in wait:
                parts[r].update(status="DERIVED", bottom_confirmed=f"{date}, {ev}")
                parts[r].pop("candidate", None)
            return out
    others = sorted({str(c.get("date", "?")) for c in cfg["bottom_confirmed"]
                     if str(c.get("bottom_sha256", "")).strip().lower() != sha})
    if not why:
        why = (f"the confirmation(s) of {', '.join(others)} were made for another bottom-side mapping" if others else
               "[rotations] bottom_side_checked = true is not bound to a board revision" if cfg["bottom_old"] else
               "no confirmation is recorded")
    reason = (f"bottom side: the angle is derived counter-clockwise as seen from the bottom, a convention not proven "
              f"on an order; {why}. Make the preview package (fab_package.py --preview), look at the part in "
              f"JLCPCB's placement preview, then record [[rotations.bottom_side_confirmed]] bottom_sha256 = \"{sha}\", "
              f"date, evidence (the preview crop) in board.toml")
    for r in wait:
        parts[r]["reason"] = reason
    return out


def _one(fp, pcbnew, cfg: dict, want: list[str], bom_code: dict | None, notes: list[str], base: str = "") -> dict:
    ref = fp.GetReference()
    base = base or ref                      # on a panel: the board's own reference of this copy
    board_code = _lcsc_of(fp, want)
    code = (bom_code[ref] if bom_code is not None else board_code).strip().upper()
    if bom_code is not None and board_code and board_code.upper() != code and code:
        notes.append(f"{ref}: the board's field says {board_code}, the BOM table says {code} (the table is used)")
    p0 = fp.GetPosition()
    bottom = bool(fp.IsFlipped())
    rot = fp.GetOrientationDegrees() % 360
    row = dict(code=code, status="UNKNOWN", side="bottom" if bottom else "top", value=fp.GetValue(),
               kicad_footprint=str(fp.GetFPID().GetLibItemName()), kicad_rot=round(rot, 3),
               kicad_x=round(pcbnew.ToMM(p0.x), 3), kicad_y=round(-pcbnew.ToMM(p0.y), 3),
               pads=len({p.GetNumber() for p in fp.Pads() if p.GetNumber()}))
    declared = cfg["declared"].get(ref) or cfg["declared"].get(base)

    def unknown(reason: str) -> dict:
        if declared:
            return _declare(row, declared, reason)
        row["reason"] = reason
        return row

    if not code:
        return unknown("no LCSC number on the part (field " + " / ".join(cfg["lcsc_fields"][:3]) + ")")
    if not _LCSC_RE.match(code):
        return unknown(f"'{code}' is not an LCSC number")
    lib = os.path.join(cfg["vendor"], code + ".pretty") if cfg["vendor"] else ""
    mods = sorted(f[:-10] for f in os.listdir(lib) if f.endswith(".kicad_mod")) if lib and os.path.isdir(lib) else []
    if not mods:
        return unknown(f"no cached JLCPCB footprint for {code}" + ("" if cfg["vendor"] else
                                                                     " (no footprint folder: give --vendor or --project)"))
    try:
        jfp = pcbnew.FootprintLoad(lib, mods[0])
        why = "empty file" if jfp is None else ""
    except Exception as e:  # noqa: BLE001 - a damaged library file is data, not a crash
        jfp = None
        why = (str(e).splitlines() or [type(e).__name__])[0][:80]
    if jfp is None:
        return unknown(f"the cached footprint {mods[0]} of {code} could not be loaded ({why})")
    row["jlc_footprint"] = mods[0]
    if len(mods) > 1:
        row["note"] = f"{len(mods)} footprints in the folder of {code}; {mods[0]} used"
    sx = -1.0 if bottom else 1.0           # bottom side: the board seen from below (X mirrored)
    op, tp = _pads(fp, pcbnew, sx), _pads(jfp, pcbnew, 1.0)
    ours: dict[str, list] = {}
    for p in op:
        if p["n"]:
            ours.setdefault(p["n"], []).append((p["x"], p["y"]))
    theirs: dict[str, list] = {}
    for p in tp:
        if p["n"]:
            theirs.setdefault(p["n"], []).append((p["x"], p["y"]))
    nets: dict[str, set] = {}
    for p in op:
        if p["n"]:
            nets.setdefault(p["n"], set()).add(p["net"])
    fitted_by = "pad numbers"
    if len(ours) == 2 and (any(fnmatch.fnmatchcase(base, pat) for pat in cfg["mark_fit"])
                           or polar_name(row["kicad_footprint"]) or polar_name(mods[0])):
        # A polarised two-pin part. The library's pad numbers need not put the marked terminal on pad 1 (one
        # diode footprint has its band at pad 2); the assembler aligns the part's mark with the footprint's
        # mark, so the marked terminal is the pad at the mark: read in both footprints, never assumed.
        if len(theirs) != 2 or not all(len(v) == 1 for v in theirs.values()):
            return unknown(f"polarised two-pin part: JLCPCB's footprint {mods[0]} has the pad numbers "
                           f"{sorted(theirs)[:6]}, not two single pads: the polarity mark cannot be fitted")
        kind = part_kind(base, [row["kicad_footprint"], mods[0]])
        given = cfg["marked_pad"].get(code)
        if given:
            k, k_how, k_bad = str(given), "board.toml marked_pad", False
        else:
            k, k_how, k_bad = read_mark({n: v[0] for n, v in theirs.items()},
                                        *silk_strokes(jfp, pcbnew, pcbnew.F_SilkS, 1.0), kind)
        if k is None:
            return unknown(f"polarised two-pin part: the polarity marks of JLCPCB's footprint {mods[0]} disagree "
                           f"({k_how})" if k_bad else f"polarised two-pin part: polarity mark not found in JLCPCB's "
                           f"footprint {mods[0]} ({k_how} on its silkscreen); look at the part, then name its marked pad "
                           f"in board.toml ([rotations.marked_pad] {code})")
        if k not in theirs:
            return unknown(f"[rotations.marked_pad] {code} = \"{k}\" is no pad of JLCPCB's footprint {mods[0]}")
        mine, o_how, o_bad = read_mark({n: v[0] for n, v in ours.items()},
                                       *silk_strokes(fp, pcbnew, pcbnew.B_SilkS if bottom else pcbnew.F_SilkS, sx), kind)
        if mine is None:
            return unknown(f"polarised two-pin part: the polarity marks of our footprint {row['kicad_footprint']} "
                           f"disagree ({o_how})" if o_bad else f"polarised two-pin part: polarity mark not found in our "
                           f"footprint {row['kicad_footprint']} ({o_how} on its silkscreen); add the mark, or check the "
                           f"part in the placement preview and declare it ([rotations.declared.{base}])")
        named = next((n for n in ("1", "K", "C", "+") if n in ours), None)
        if named is not None and named != mine:
            return unknown(f"polarised two-pin part: our footprint {row['kicad_footprint']} marks pad {mine} ({o_how}), "
                           f"but pad {named} is its marked terminal by KiCad's convention (a diode's cathode, a "
                           "capacitor's plus): check the footprint against the symbol's pin numbers")
        other = [n for n in theirs if n != k][0]
        mine_other = [n for n in ours if n != mine][0]
        theirs = {mine: theirs[k], mine_other: theirs[other]}
        for p in tp:
            p["m"] = {k: mine, other: mine_other}.get(p["n"], p["n"])
        fitted_by = f"polarity mark: JLCPCB's pad {k} ({k_how}) on our pad {mine} ({o_how})"
    common = sorted(set(ours) & set(theirs))
    if code in cfg["fit_pads"]:
        common = [n for n in common if n in cfg["fit_pads"][code]]
        fitted_by = "pads " + ", ".join(common) + " (board.toml fit_pads)"
    if not common:
        return unknown(f"no common pad numbers (ours {sorted(ours)[:6]}, JLCPCB's {sorted(theirs)[:6]})")
    anchors = anchors_of(ours, theirs, common)
    if len({(round(x, 3), round(y, 3)) for n in anchors for x, y in ours[n]}) < 2:
        return unknown(f"one anchor: only pad {', '.join(anchors)} of ours is matched in JLCPCB's footprint "
                       f"{mods[0]}, and one place cannot fix the turn; check that the footprint is the part's")
    side = min([p["side"] for p in op if p["n"] in common] + [p["side"] for p in tp if p["m"] in common])
    limit = round(min(cfg["tolerance"], cfg["fraction"] * side), 3)
    base = ((180.0 - rot) if bottom else rot) % 90.0
    fits = fit_turns(ours, theirs, common, sorted(_angle(base + k * 90) for k in range(4)), cfg["origin"])
    best = min(fits, key=lambda f: f[0])
    worst, phi, qx, qy = best
    near = [f for f in fits if f is not best and round(f[0], 3) <= limit]
    if near:
        land = _landing(op, tp, best, limit, sx, pcbnew)
        other_turns = [f[1] for f in near if not _same_pins(land, _landing(op, tp, f, limit, sx, pcbnew), nets)]
        if other_turns:
            return unknown(f"AMBIGUOUS: the turns {phi:g} and {', '.join(f'{t:g}' for t in other_turns)} degrees "
                           f"all fit within {limit:g} mm and put JLCPCB's pads on different pins of ours")
    row.update(pad_error=round(worst, 3), pad_limit=limit, pads_matched=len(common), pads=len(ours), fit=fitted_by)
    place = dict(cpl_rot=phi, cpl_x=round(sx * qx, 3), cpl_y=round(qy, 3),
                 offset=_angle(phi - (((180.0 - rot) if bottom else rot))))
    if row["pad_error"] > limit:
        row.update(place, status="FAIL", reason=(
            f"the footprints do not fit: pad error {row['pad_error']:g} mm above the limit {limit:g} mm "
            f"({cfg['fraction']:g} x {side:g} mm, the smaller side of the pads involved, at most {cfg['tolerance']:g} mm)"))
        return _declare(row, declared, row.pop("reason")) if declared else row
    expl = cfg["unmatched"].get(code, {})
    ok_ours = set(map(str, expl.get("ours", []))) if expl.get("reason") else set()
    ok_theirs = set(map(str, expl.get("theirs", []))) if expl.get("reason") else set()
    lone_o = sorted({o["n"] for o in op if o["elec"] and not any(
        t["elec"] and _pin_ok(o, t, nets) and _meet(o, t, best, limit, sx, pcbnew) for t in tp)}, key=natural)
    lone_t = sorted({t["n"] for t in tp if t["elec"] and not any(
        o["elec"] and _pin_ok(o, t, nets) and _meet(o, t, best, limit, sx, pcbnew) for o in op)}, key=natural)
    miss_o, miss_t = [n for n in lone_o if n not in ok_ours], [n for n in lone_t if n not in ok_theirs]
    if miss_o or miss_t:
        what = "; ".join(s for s in (miss_o and "ours " + ", ".join(miss_o), miss_t and "JLCPCB's " + ", ".join(miss_t)) if s)
        return unknown(f"pads without a counterpart after the fit: {what} (footprint {mods[0]}): the footprints do not "
                       f"match pin for pin. If that is right, name them with the reason in board.toml "
                       f"[rotations.unmatched_pads.{code}] (ours = [...], theirs = [...], reason = \"...\")"
                       + (" - named there without a reason: not accepted" if expl and not expl.get("reason") else ""))
    if lone_o or lone_t:
        row["unmatched_explained"] = {"ours": lone_o, "theirs": lone_t, "reason": str(expl["reason"]).strip()}
    row.update(place)
    if declared:
        return _declare(row, declared, "")
    if bottom:
        row["candidate"] = True                     # bottom_side() decides with the recorded confirmation
        return row
    row["status"] = "DERIVED"
    return row


def _declare(row: dict, d: dict, why_unknown: str) -> dict:
    """The project's own decision for one part (board.toml [rotations.declared.<REF>]): DECLARED, NOT MEASURED."""
    if not str(d.get("reason", "")).strip():
        row["reason"] = "declared in board.toml without a reason: not accepted"
        return row
    derived = {k: row.get(k) for k in ("cpl_rot", "cpl_x", "cpl_y", "pad_error") if k in row}
    rot = float(d["rotation"]) if "rotation" in d else row["kicad_rot"] + float(d.get("rotation_offset", 0))
    x = float(d["x"]) if "x" in d else row["kicad_x"] + float(d.get("dx", 0))
    y = float(d["y"]) if "y" in d else row["kicad_y"] + float(d.get("dy", 0))
    row.update(status="DECLARED", cpl_rot=_angle(rot), cpl_x=round(x, 3), cpl_y=round(y, 3),
               pad_error=None, pads_matched=None, pad_limit=None, measured=False,
               preview_check="mandatory: declared by the project, not measured", declared_reason=str(d["reason"]).strip(),
               jlc_footprint=row.get("jlc_footprint") or "(none: declared in board.toml)",
               offset=_angle(rot - row["kicad_rot"]), fit="declared by the project (not measured)")
    if why_unknown:
        row["would_be_unknown"] = why_unknown
    elif derived and (derived["cpl_rot"] != row["cpl_rot"] or abs(derived["cpl_x"] - row["cpl_x"]) > POS_TOL
                      or abs(derived["cpl_y"] - row["cpl_y"]) > POS_TOL):
        row["derived_instead"] = derived
    return row


# ---------------------------------------------------------------------------------------------------------------------
# placement file
# ---------------------------------------------------------------------------------------------------------------------

def cpl_rows(parts: dict, candidates: bool = False) -> list[list[str]]:
    """Rows of JLCPCB's placement file for every derived or declared part, in natural order of the references.
    candidates=True adds the bottom-side parts that wait for the placement preview (a preview-only file)."""
    rows = []
    for ref in sorted(parts, key=natural):
        p = parts[ref]
        if p["status"] in ("DERIVED", "DECLARED") or (candidates and p.get("candidate")):
            rows.append([ref, f"{p['cpl_x']:.3f}", f"{p['cpl_y']:.3f}", "Bottom" if p["side"] == "bottom" else "Top",
                         f"{p['cpl_rot']:g}"])
    return rows


def write_cpl(path: str, parts: dict, candidates: bool = False) -> int:
    rows = cpl_rows(parts, candidates)
    buf = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]] + rows
    import io
    s = io.StringIO()
    csv.writer(s, lineterminator="\r\n").writerows(buf)
    kicad_io.atomic_write(path, s.getvalue())
    return len(rows)


def read_cpl(path: str) -> dict:
    """{reference: (x, y, rotation, side)} from a placement file (JLCPCB's columns or KiCad's position file)."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    except (OSError, UnicodeDecodeError) as e:
        raise kicad_io.KicadIOError(f"placement file {os.path.basename(path)} cannot be read: {e}") from None
    if not rows:
        raise kicad_io.KicadIOError(f"placement file {os.path.basename(path)} is empty")
    head = [_key(c) for c in rows[0]]

    def col(*names):
        for n in names:
            if _key(n) in head:
                return head.index(_key(n))
        raise kicad_io.KicadIOError(f"placement file {os.path.basename(path)}: no column {names[0]} "
                                    f"(columns: {', '.join(rows[0])})")
    c_ref, c_x, c_y = col("Designator", "Ref"), col("Mid X", "PosX"), col("Mid Y", "PosY")
    c_rot, c_side = col("Rotation", "Rot"), col("Layer", "Side")
    out: dict[str, tuple] = {}
    dup = []
    for r in rows[1:]:
        try:
            ref = r[c_ref].strip()
            val = (float(r[c_x].replace("mm", "")), float(r[c_y].replace("mm", "")), float(r[c_rot]),
                   "bottom" if r[c_side].strip().lower().startswith("b") else "top")
        except (IndexError, ValueError):
            raise kicad_io.KicadIOError(f"placement file {os.path.basename(path)}: unreadable row {r}") from None
        if ref in out:
            dup.append(ref)
        out[ref] = val
    if dup:
        raise kicad_io.KicadIOError(f"placement file {os.path.basename(path)}: designators twice: {', '.join(dup)}")
    return out


def compare(res: dict, cpl: dict) -> list[str]:
    """Differences between a fresh derivation and a placement file (empty when they agree)."""
    bad = []
    for ref in sorted(res["parts"], key=natural):
        p = res["parts"][ref]
        if p["status"] == "UNKNOWN":
            bad.append(f"{ref}: UNKNOWN ({p.get('reason', '')})" + (" but it is in the placement file" if ref in cpl else ""))
            continue
        if p["status"] == "FAIL":
            bad.append(f"{ref}: JLCPCB's pads miss ours by {p['pad_error']} mm (limit {p['pad_limit']:g} mm)")
        c = cpl.get(ref)
        if c is None:
            bad.append(f"{ref}: not in the placement file")
            continue
        x, y, rot, side = c
        if abs((rot - p["cpl_rot"] + 180) % 360 - 180) > 0.01 or abs(x - p["cpl_x"]) > POS_TOL or \
                abs(y - p["cpl_y"]) > POS_TOL or side != p["side"]:
            bad.append(f"{ref}: placement file {x:g}, {y:g} @ {rot:g} {side} != derived {p['cpl_x']:g}, "
                       f"{p['cpl_y']:g} @ {p['cpl_rot']:g} {p['side']}")
    for ref in sorted(cpl, key=natural):
        if ref not in res["parts"]:
            bad.append(f"{ref}: in the placement file, but not a part to place (not fitted, hand-fitted, excluded or "
                       "not on the board)")
    for ref in res["in_bom_not_on_board"]:
        bad.append(f"{ref}: in the BOM table, not on the board")
    return bad


# ---------------------------------------------------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------------------------------------------------

def _cell(text) -> str:
    return str(text if text is not None else "").replace("|", "\\|")


def markdown(res: dict) -> str:
    c, parts = res["counts"], res["parts"]
    s = res["settings"]
    out = ["# JLCPCB placement rotations and origins, derived from JLCPCB's own footprints", "",
           f"**Result: {res['result']}** - {c['placed']} part(s) to place: {c['derived']} derived, {c['declared']} "
           f"declared by the project (not measured), {c['unknown']} UNKNOWN, {c['pad_error_above_tolerance']} not "
           f"fitting (pad error above the package limit)." + (" Nothing to place was found." if not parts else ""), "",
           f"Board `{res['board']}`, SHA-256 `{res['board_sha256']}`, KiCad {res['kicad_version']}, {res['date']}. "
           f"Library footprints from `{s['vendor'] or '(no vendor folder)'}`; origin fitted by `{s['origin']}`; "
           + (f"placed parts and numbers from `{s['bom']}`." if s["bom"] else "placed parts and numbers from the board.")
           + f" {s['note']}", "",
           "How to read it: JLCPCB's footprint for the part's LCSC number is turned in steps of 90 degrees and moved "
           "until its pads lie on ours, pin 1 on pin 1; two-pin parts with a polarised footprint are matched by the "
           "polarity mark read in both footprints, not by pad number (UNKNOWN when a mark is missing or the marks "
           "disagree). `Offset` is what the placement file adds to KiCad's own rotation. `Pad error` is the "
           f"largest pad miss after the fit; `Limit` is {s['pad_tolerance_fraction']:g} x the smaller side of the pads "
           f"involved, at most {s['pad_tolerance_mm']:g} mm. A fit counts only with two anchors at different places, "
           "no other turn that fits as well on other pins, and a counterpart for every pad on both sides. An UNKNOWN "
           "part gets no rotation: nothing is assumed.", ""]
    unknown = [r for r in sorted(parts, key=natural) if parts[r]["status"] == "UNKNOWN"]
    if unknown:
        out += ["## UNKNOWN: no rotation given", "", "| Ref | Value | LCSC | KiCad footprint | Why |", "|---|---|---|---|---|"]
        out += [f"| {r} | {_cell(parts[r]['value'])} | {parts[r]['code'] or ''} | {_cell(parts[r]['kicad_footprint'])} | "
                f"{_cell(parts[r].get('reason', ''))} |" for r in unknown]
        out += ["", "For each: fetch JLCPCB's footprint (`fetch_parts.py jlc-footprint`), or check the part in the "
                "placement preview and write the decision into board.toml under `[rotations.declared.<REF>]` with "
                "its reason.", ""]
    b = res.get("bottom_side") or {}
    if b.get("parts"):
        out += ["## Bottom side: " + ("confirmed in the placement preview" if b["confirmed"] else
                                      "waiting for the placement preview"), "",
                f"Checksum of the bottom-side mapping: `{b['sha256']}`."]
        if b["confirmed"]:
            out += [f"Confirmed on {b['confirmation']['date']}, evidence `{b['confirmation']['evidence']}`. A changed "
                    "bottom side gives another checksum and needs a new look.", ""]
        else:
            out += ["", "| Ref | LCSC | JLCPCB footprint | KiCad rot | Candidate CPL rot | Candidate X, Y (mm) |",
                    "|---|---|---|---|---|---|"]
            out += [f"| {r} | {parts[r]['code']} | {_cell(parts[r]['jlc_footprint'])} | {parts[r]['kicad_rot']:g} | "
                    f"{parts[r]['cpl_rot']:g} | {parts[r]['cpl_x']:.3f}, {parts[r]['cpl_y']:.3f} |" for r in b["parts"]]
            out += ["", "1. `fab_package.py --preview` writes `jlc_preview/`: PREVIEW ONLY, NOT FOR ORDER. 2. Upload it "
                    "for the placement preview only; look at every part above; save a crop. 3. Record in board.toml "
                    "`[[rotations.bottom_side_confirmed]]` with `bottom_sha256` (above), `date` and `evidence` (the crop). "
                    "4. Remove the cart item; export again.", ""]
    look = [r for r in sorted(parts, key=natural) if parts[r]["status"] in ("DERIVED", "DECLARED") and _matters(parts[r], r)]
    out += ["## Parts whose turn matters: look at each in the placement preview", "",
            "Pin 1, the polarity mark or the connector key must sit as on the silkscreen.", "",
            "| Ref | Value | KiCad footprint | KiCad rot | Offset | CPL rot | Fitted by |", "|---|---|---|---|---|---|---|"]
    out += [f"| {r} | {_cell(parts[r]['value'])} | {_cell(parts[r]['kicad_footprint'])} | {parts[r]['kicad_rot']:g} | "
            f"{parts[r]['offset']:+g} | {parts[r]['cpl_rot']:g} | "
            f"{_cell(parts[r].get('declared_reason') and 'DECLARED: ' + parts[r]['declared_reason'] or parts[r]['fit'])} |"
            for r in look] or ["| (none) | | | | | | |"]
    out += ["", "## Derivation: every part fitted on JLCPCB's footprint (or UNKNOWN)", "",
            "| Ref | LCSC | JLCPCB footprint | Side | KiCad rot | CPL rot | CPL X, Y (mm) | KiCad X, Y | Pad error (mm) | Limit (mm) | Pads fitted |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(parts, key=natural):
        p = parts[r]
        if p["status"] == "DECLARED":
            continue
        if p["status"] == "UNKNOWN":
            out.append(f"| {r} | {p['code'] or ''} | **UNKNOWN** | {p['side']} | {p['kicad_rot']:g} | | | "
                       f"{p['kicad_x']:.3f}, {p['kicad_y']:.3f} | | | |")
            continue
        flag = " **does not fit**" if p["status"] == "FAIL" else ""
        out.append(f"| {r} | {p['code']} | {_cell(p['jlc_footprint'])} | {p['side']} | {p['kicad_rot']:g} | "
                   f"**{p['cpl_rot']:g}** | {p['cpl_x']:.3f}, {p['cpl_y']:.3f} | {p['kicad_x']:.3f}, "
                   f"{p['kicad_y']:.3f} | {p['pad_error']:.3f}{flag} | {p['pad_limit']:.3f} | {p['pads_matched']} of {p['pads']}"
                   + (f"; explained: {_cell(p['unmatched_explained']['reason'])}" if p.get("unmatched_explained") else "")
                   + " |")
    declared = [r for r in sorted(parts, key=natural) if parts[r]["status"] == "DECLARED"]
    if declared:
        out += ["", "## DECLARED by the project: NOT MEASURED", "",
                "Written decisions from board.toml. No pad was fitted, so there is no pad error; each part stays on the "
                "placement preview check (mandatory).", "",
                "| Ref | LCSC | Side | KiCad rot | CPL rot | CPL X, Y (mm) | Reason | Without the declaration |",
                "|---|---|---|---|---|---|---|---|"]
        out += [f"| {r} | {parts[r]['code'] or ''} | {parts[r]['side']} | {parts[r]['kicad_rot']:g} | "
                f"**{parts[r]['cpl_rot']:g}** | {parts[r]['cpl_x']:.3f}, {parts[r]['cpl_y']:.3f} | "
                f"{_cell(parts[r]['declared_reason'])} | {_cell(parts[r].get('would_be_unknown') or (parts[r].get('derived_instead') and 'derived: ' + str(parts[r]['derived_instead'])) or 'derived the same')} |"
                for r in declared]
    out += ["", "## Not placed", ""]
    names = {"dnp": "not fitted (DNP)", "excluded_from_position_files": "excluded from position files in the board",
             "hand_fit": "fitted by hand (board.toml)", "ignored": "ignored (board.toml)",
             "not_in_bom": "on the board, not in the BOM table"}
    any_skipped = False
    for k, label in names.items():
        if res["not_placed"][k]:
            any_skipped = True
            out.append(f"- {label}: {', '.join(res['not_placed'][k])}")
    if not any_skipped:
        out.append("- nothing: every footprint of the board is treated as a part to place")
    if res["in_bom_not_on_board"]:
        out += ["", "**In the BOM table but not on the board:** " + ", ".join(res["in_bom_not_on_board"])]
    out += ["", "## Notes and what was not checked", ""] + [f"- {n}" for n in res["notes"]] + [
        "- JLCPCB's production library may differ from the cached footprint: its engineer may still turn a part; "
        "verify pin 1 against the pads in the placement preview, never against the angle number",
        "- that pad 1 of a two-pin footprint of the board is its marked terminal (cathode, plus) is the KiCad "
        "convention, checked only against the footprint's own silkscreen mark; a footprint drawn wrong in both ways "
        "is not found here"]
    return "\n".join(out) + "\n"


def _matters(p: dict, ref: str) -> bool:
    """A part whose turn can be wrong in a way that matters: more than two pads, polarised, declared, or turned."""
    if p["status"] == "DECLARED" or p["pads"] > 2 or p["offset"] not in (0, 180):
        return True
    low = p["kicad_footprint"].lower()
    return str(p.get("fit", "")).startswith("polarity") or any(low.startswith(n) or n in low for n in _POLAR_NAMES)


def test_markdown(res: dict, bad: list[str], cpl_name: str, n_cpl: int) -> str:
    out = ["# Placement file against a fresh derivation", "",
           f"**Result: {'PASS' if not bad else 'FAIL'}** - {res['counts']['placed']} part(s) derived again from board "
           f"`{res['board']}` (SHA-256 `{res['board_sha256']}`), {n_cpl} row(s) in `{cpl_name}`, "
           f"{len(bad)} difference(s). {res['date']}.", ""]
    out += ["| Difference |", "|---|"] + [f"| {_cell(b)} |" for b in bad] if bad else \
        ["Every row of the placement file equals the derivation (rotation, position within 0.01 mm, side), and "
         "every part to place is in the file."]
    out += ["", f"What this proves: {PROVES}."]
    return "\n".join(out) + "\n"


PROVES = ("consistency - the placement file equals a fresh derivation from the same board and library footprints; "
          "not physical correctness: pin 1 and polarity are confirmed in JLCPCB's placement preview")


# ---------------------------------------------------------------------------------------------------------------------
# settings and command line
# ---------------------------------------------------------------------------------------------------------------------

def _as_list(v) -> list:
    return [] if v is None else ([v] if isinstance(v, str) else list(v))


def settings(a) -> tuple[dict, str, str]:
    """(settings, board path, results folder): command line over board.toml over defaults."""
    toml: dict = {}
    used = []
    if a.project:
        toml = kicad_io.load_settings(a.project)
        used.append("board.toml" if toml else "no board.toml: defaults")
        root = os.path.abspath(a.project)
        try:
            files = kicad_io.project_files(a.project, toml)
            board, out = a.board or files["pcb"], a.out or files["out"]
        except kicad_io.KicadIOError:
            if not a.board:                         # several boards in the project and none named: never guess
                raise
            board = a.board
            out = a.out or os.path.join(root, toml.get("project", {}).get("out_dir", "out"))
    else:
        if not a.out or not a.board:
            raise kicad_io.KicadIOError("give --project <board folder>, or a board file together with --out <folder>")
        used.append("no project folder: defaults and the command line")
        board, out, root = a.board, a.out, None
    if not board or not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"board file not found: {board or '(none in the project folder)'}")
    design = os.path.normcase(os.path.dirname(os.path.abspath(board)))
    if (os.path.normcase(os.path.abspath(out)) + os.sep).startswith(design + os.sep):
        raise kicad_io.KicadIOError("the results folder lies inside the folder of the input design; a design that "
                                    "is only read is never written into: choose another folder with --out")
    r, b = toml.get("rotations", {}), toml.get("bom", {})

    def rel(p):
        return os.path.join(root, p) if root and p and not os.path.isabs(p) else p
    vendor = a.vendor or rel(r.get("vendor")) or (os.path.join(root, "vendor", "jlc_fp") if root else None)
    vendor_shown: str | None = None
    if not vendor:
        used.append("no footprint folder: every part will be UNKNOWN; give --vendor <folder with the cached JLCPCB "
                    "footprints> or --project <board folder> (its vendor/jlc_fp)")
    elif not os.path.isdir(vendor):
        used.append(f"vendor folder {os.path.basename(vendor)} not found: every part will be UNKNOWN")
        vendor_shown = os.path.basename(vendor) + " (not found)"
        vendor = None
    else:
        vendor_shown = os.path.basename(os.path.abspath(vendor))
    bom = a.bom or rel(b.get("assembly_file"))
    if bom and not os.path.isfile(bom):
        raise kicad_io.KicadIOError(f"BOM table not found: {os.path.basename(bom)}")
    origin = a.origin or r.get("origin", "bbox")
    if origin not in ("bbox", "mean"):
        raise kicad_io.KicadIOError("origin must be 'bbox' or 'mean'")
    conf = r.get("bottom_side_confirmed", [])
    cfg = {
        "vendor": vendor, "vendor_shown": vendor_shown, "bom": bom, "origin": origin, "root": root,
        "tolerance": a.tolerance if a.tolerance is not None else float(r.get("pad_tolerance_mm", TOLERANCE)),
        "fraction": float(r.get("pad_tolerance_fraction", TOL_FRACTION)),
        "mark_fit": _as_list(r.get("mark_fit_refs")) or MARK_FIT,
        "bottom_old": bool(r.get("bottom_side_checked", False)),
        "bottom_confirmed": [c for c in ([conf] if isinstance(conf, dict) else conf) if isinstance(c, dict)],
        "unmatched": {k.upper(): v for k, v in r.get("unmatched_pads", {}).items() if isinstance(v, dict)},
        "fit_pads": {k.upper(): [str(x) for x in v] for k, v in r.get("fit_pads", {}).items()},
        "marked_pad": {k.upper(): str(v) for k, v in r.get("marked_pad", {}).items()},
        "declared": dict(r.get("declared", {})),
        "lcsc_fields": a.lcsc_field or _as_list(b.get("lcsc_field")) or LCSC_FIELDS,
        "hand_fit": set(_as_list(b.get("hand_fit"))), "dnp": set(_as_list(b.get("dnp"))),
        "ignore": _as_list(b.get("ignore")),
    }
    if not 0 < cfg["fraction"] <= 2 or cfg["tolerance"] <= 0:
        raise kicad_io.KicadIOError("pad_tolerance_fraction must lie in (0, 2] and pad_tolerance_mm above 0")
    cfg["settings_note"] = ("Settings: " + "; ".join(used) + f"; origin {origin}; pad limit {cfg['fraction']:g} x the "
                            f"smaller pad side, at most {cfg['tolerance']:g} mm; "
                            f"LCSC number from field {' / '.join(cfg['lcsc_fields'][:3])}"
                            + (f"; fit_pads for {', '.join(sorted(cfg['fit_pads']))}" if cfg["fit_pads"] else "")
                            + (f"; declared: {', '.join(sorted(cfg['declared'], key=natural))}" if cfg["declared"] else "")
                            + ".")
    return cfg, board, out


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kicad_io.atomic_write(path, text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Derive JLCPCB placement rotations from JLCPCB's own footprints, or "
                                             "test a placement file against a fresh derivation.")
    ap.add_argument("--project", help="hardware/board folder: board.toml, the footprint folder, results in "
                                      "<project>/out/jlc/. With a board file and --out (a panel) it still gives the "
                                      "footprint folder and board.toml's settings")
    ap.add_argument("--out", help="results folder (files go to <out>/jlc/); needed without --project")
    ap.add_argument("--vendor", help="folder with <LCSC number>.pretty footprints (default with --project: [rotations] "
                                     "vendor, else <project>/vendor/jlc_fp); without --project and --vendor every "
                                     "part is UNKNOWN")
    ap.add_argument("--bom", help="BOM table (CSV) that decides which designators are placed and their numbers")
    ap.add_argument("--lcsc-field", action="append", help="footprint field with the LCSC number (repeatable)")
    ap.add_argument("--origin", choices=["bbox", "mean"], help="origin fit (default bbox)")
    ap.add_argument("--tolerance", type=float, help=f"cap of the pad limit in mm (default {TOLERANCE:g}); the limit is "
                                                    f"{TOL_FRACTION:g} x the smaller pad side up to this cap")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("derive", help="derive and write jlc/rotations.md and .json")
    d.add_argument("board", nargs="?", help="board file (.kicad_pcb)")
    t = sub.add_parser("test", help="derive again and compare with a placement file")
    t.add_argument("board", nargs="?", help="board file (.kicad_pcb)")
    t.add_argument("--cpl", help="placement file (default: the only *cpl*.csv in the results folder)")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_usage(sys.stderr)
        return 2
    cfg, board, out = settings(a)
    jlc = os.path.join(out, "jlc")
    cpl_path = None
    if a.cmd == "test":
        cpl_path = a.cpl
        if not cpl_path:
            cand = sorted(f for f in (os.listdir(jlc) if os.path.isdir(jlc) else []) if f.lower().endswith(".csv")
                          and ("cpl" in f.lower() or "pos" in f.lower()))
            if len(cand) != 1:
                raise kicad_io.KicadIOError(f"{len(cand)} placement files in {jlc}; name one with --cpl")
            cpl_path = os.path.join(jlc, cand[0])
        if not os.path.isfile(cpl_path):
            raise kicad_io.KicadIOError(f"placement file not found: {cpl_path}")
    kicad_io.need_kicad_python()                    # from here on: KiCad's own Python
    res = derive(board, cfg)
    print(cfg["settings_note"])
    c = res["counts"]
    if a.cmd == "derive":
        _write(os.path.join(jlc, "rotations.json"), json.dumps(res, indent=1, sort_keys=True) + "\n")
        _write(os.path.join(jlc, "rotations.md"), markdown(res))
        for r in sorted(res["parts"], key=natural):
            p = res["parts"][r]
            if p["status"] == "UNKNOWN":
                print(f"UNKNOWN  {r}  {p['code'] or '(no LCSC number)'}: {p.get('reason', '')}")
        for r in res["pad_error_above_tolerance"]:
            print(f"FAIL  {r}: {res['parts'][r]['reason']}")
        for r in res["in_bom_not_on_board"]:
            print(f"FAIL  {r}: in the BOM table, not on the board")
        b = res["bottom_side"]
        if b["parts"]:
            print(f"bottom side: {', '.join(b['parts'])}; checksum {b['sha256']}; "
                  + (f"confirmed {b['confirmation']['date']}" if b["confirmed"] else "waiting for the placement preview"))
        print(f"rotations: {res['result']} - {c['placed']} part(s) to place: {c['derived']} derived, {c['declared']} "
              f"declared (not measured), {c['unknown']} UNKNOWN, {c['pad_error_above_tolerance']} not fitting; "
              f"table {os.path.join(jlc, 'rotations.md')}")
        return 0 if res["result"] == "PASS" else 1
    assert cpl_path is not None
    cpl = read_cpl(cpl_path)
    bad = compare(res, cpl)
    _write(os.path.join(jlc, "rotations_test.md"), test_markdown(res, bad, os.path.basename(cpl_path), len(cpl)))
    _write(os.path.join(jlc, "rotations_test.json"), json.dumps(
        {"check": "jlc_rotations_test", "result": "PASS" if not bad else "FAIL", "date": res["date"],
         "board": res["board"], "board_sha256": res["board_sha256"], "placement_file": os.path.basename(cpl_path),
         "placement_file_sha256": kicad_io.sha256(cpl_path), "parts": c["placed"], "rows": len(cpl),
         "differences": bad, "proves": PROVES}, indent=1) + "\n")
    for b in bad:
        print("FAIL  " + b)
    print(f"The test proves {PROVES}.")
    print(f"rotation test: {'PASS' if not bad else 'FAIL'} - {c['placed']} part(s) derived again, {len(cpl)} row(s) in "
          f"{os.path.basename(cpl_path)}, {len(bad)} difference(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
