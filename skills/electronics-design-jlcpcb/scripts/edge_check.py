"""Copper to board edge, measured on the EXPORTED Gerbers: what the factory will etch and cut.

What it checks
    For every copper layer in a folder of Gerber files: the smallest distance from any copper feature (flashed
    pads, drawn tracks and arcs, filled regions) to the board outline of the profile layer (its centre line),
    and that every copper feature lies inside the board and outside every cut-out. A layer fails when the
    distance is under the limit (default 0.30 mm). It works for one board and for a panel (several boards,
    slots, rails); places where copper is meant to reach the edge are listed in board.toml and reported as
    allowed, never silently skipped.
    Edge keep-out bands (a board that slides in slots or rails of its case): a band that carries copper_to_edge
    sets a larger limit along its own stretch of the edge, for the outer copper layer of each side the band
    names (top, bottom or both); the nearest copper along that stretch is reported per band. Inner layers and
    the rest of the outline keep the general limit. The bands apply to the single board, not to its panel.

Why it exists (the real failure, told without names)
    A board's saved zone fill reached the outline while the design-rule check reported nothing: the rule check
    had refilled the zones in memory, the board file and the Gerbers kept the older fill. Design settings and a
    clean rule check say nothing about the files that are uploaded. This check reads those files.

How it measures
    Gerber files are read with this module's own reader (no third-party package): formats in mm or inch,
    standard apertures (circle, rectangle, obround, polygon), aperture macros (circle, vector line, centre line,
    outline, polygon; exposure off and the thermal primitive are noted), linear and circular draws, regions,
    dark and clear polarity, step and repeat. The outline's draws are chained into closed contours. Distance:
    exact segment-to-segment distance between every copper edge and every outline segment (arcs are split so
    the chord error stays under 2 um), minus the stroke radius of draws and circles; 0 when they touch or cross.
    Clear-polarity items (copper removed) are left out of the measurement: the result can only be too strict.

    The reader is also used by review_images.py to draw the layers (read_gerber, read_drill, find_files).

Usage
    python -I edge_check.py --project <hardware/board folder>         Gerbers from <project>/out/jlc/gerbers, and
                                                                       the panel's from out/panel/jlc/gerbers when
                                                                       the project has a panel
    python -I edge_check.py --gerbers <folder> --out <folder>         any folder of Gerber files
    options: --min MM (limit), --name NAME (result base name, default edge_check)

    The panel (project form): measured whenever board.toml has a [panel] table or out/panel/ exists (panel.py
    writes there), in the folder where fab_package.py puts the panel's Gerbers when it is run on the panel board
    with --out out/panel:
        python -I fab_package.py --project <board folder> --out out/panel --name <name>-panel
                                 --bom out/panel/<name>-panel-bom.csv out/panel/board/<name>-panel.kicad_pcb
    A panel whose Gerbers are missing or cannot be read is CANNOT RUN (exit 2), never skipped; the board's result
    is still written. Its result: one section of the same report.

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [edge]
    min = 0.3                              # mm, copper to the outline's centre line
    gerbers = "out/jlc/gerbers"            # the board's Gerber folder
    outline_file = "name.gm1"              # the board's outline Gerber, when its folder holds several candidates
    panel_gerbers = "out/panel/jlc/gerbers"  # the panel's Gerber folder (this default whenever there is a panel);
                                           # naming it also measures a panel that has no [panel] table
    [[edge.allow]]                         # copper that is meant to be nearer (edge fingers, an edge-plated pad)
    box = [x0, y0, x1, y1]                 # mm, in the Gerber files' own frame
    min = 0.0                              # the limit inside the box
    reason = "edge connector fingers"
    on = "board"                           # "board", "panel" or "both" (default)
    [[keepout.band]]                       # an edge keep-out band (all keys: pcb_common.edge_bands); read here:
    name = "left rail"   edge = "left"   sides = "both"   span = [a, b]   (or line = [x0, y0, x1, y1])   width = 3.0
    copper_to_edge = 2.0                   # mm: copper of the named sides stays this far from this edge
                                           # (bands may also come from the "keepouts" of mech/outline.json)
    Band coordinates (span, line) are KiCad's (y down); Gerber files of KiCad carry the same x and the negative y.

Exit codes
    0  PASS: every copper layer at or above the limit, every feature inside the board, the outline closed
    1  FAIL: copper under the limit or outside the board, or an outline that is not closed (board or panel)
    2  CANNOT RUN: no Gerber folder, no profile layer, no copper layer, a file this reader cannot read (for the
       board; or for the panel while the board has no FAIL). Never a pass.

Not checked: drill holes to the edge, solder mask and silkscreen to the edge (silk_check.py does the silkscreen
on the board), inner cut-outs given only as drill slots, negative (plane) layers: those are reported UNKNOWN.
Exposed copper, part bodies and solder joints inside an edge band: body_check.py (its check D).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import glob
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
from pcb_common import inside, pt_seg, seg_seg  # noqa: E402,F401

DEFAULT_MIN = 0.30
PANEL_GERBERS = os.path.join("panel", "jlc", "gerbers")   # below the results folder: fab_package.py --out out/panel
PANEL_HOW = ("python -I scripts/fab_package.py --project <board folder> --out out/panel --name <name>-panel --bom "
             "out/panel/<name>-panel-bom.csv out/panel/board/<name>-panel.kicad_pcb (it writes out/panel/jlc/gerbers/)")
ARC_TOL = 0.002                     # mm: chord error when an arc is split into segments
CHAIN_TOL = 0.01                    # mm: two outline ends closer than this are one point
MAX_LISTED = 40


class GerberError(kicad_io.KicadIOError):
    """A file this reader cannot read correctly. Never guessed around: the check cannot run."""


# ---- geometry --------------------------------------------------------------------------------------------------------
def arc_points(x0, y0, x1, y1, cx, cy, cw, tol=ARC_TOL):
    """Points of an arc from (x0, y0) to (x1, y1) about (cx, cy); equal ends give a full circle."""
    r = math.hypot(x0 - cx, y0 - cy)
    a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
    if cw:
        while a1 >= a0:
            a1 -= 2 * math.pi
    else:
        while a1 <= a0:
            a1 += 2 * math.pi
    if abs(x0 - x1) < 1e-9 and abs(y0 - y1) < 1e-9:
        a1 = a0 - 2 * math.pi if cw else a0 + 2 * math.pi
    step = 2 * math.acos(max(-1.0, 1 - tol / r)) if r > tol else math.pi / 4
    n = max(2, int(abs(a1 - a0) / step) + 1)
    pts = [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = (x0, y0), (x1, y1)
    return pts


def area(p):
    return abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))) / 2


def _rot(x, y, deg):
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def _hull(pts):
    """Convex hull (monotone chain)."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, up = half(pts), half(reversed(pts))
    return lo[:-1] + up[:-1]


# ---- Gerber reader ---------------------------------------------------------------------------------------------------
class Layer:
    """One Gerber file as primitives, in mm, in the file's own frame (y up).

    items   ("poly", points, dark) | ("circ", x, y, r, dark) | ("seg", ax, ay, bx, by, r, dark)
            a "seg" is a stroke with round ends of radius r; dark False = clear polarity (removes what is below)
    paths   every drawn stroke as a point list (the profile layer's outline)
    notes   what could not be read exactly (drawn approximately or left out); empty when the picture is exact
    attrs   file attributes (X2 or KiCad's comment form), e.g. {"FileFunction": "Copper,L1,Top"}"""

    def __init__(self, path):
        self.path, self.name = path, os.path.basename(path)
        self.items, self.paths, self.notes, self.attrs = [], [], [], {}
        self.unit = "mm"

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)

    def bbox(self):
        xs, ys = [], []
        for it in self.items:
            if it[0] == "poly":
                xs += [p[0] for p in it[1]]
                ys += [p[1] for p in it[1]]
            elif it[0] == "circ":
                xs += [it[1] - it[3], it[1] + it[3]]
                ys += [it[2] - it[3], it[2] + it[3]]
            else:
                xs += [it[1] - it[5], it[3] - it[5], it[1] + it[5], it[3] + it[5]]
                ys += [it[2] - it[5], it[4] - it[5], it[2] + it[5], it[4] + it[5]]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _eval(expr, var):
    e = re.sub(r"\$(\d+)", lambda m: repr(float(var.get(int(m.group(1)), 0.0))), expr.strip())
    e = e.replace("x", "*").replace("X", "*")
    if not re.fullmatch(r"[0-9eE.+\-*/() ]*", e) or not e.strip():
        raise GerberError(f"macro expression {expr!r} cannot be read")
    return float(eval(e, {"__builtins__": {}}, {}))        # noqa: S307  (arithmetic only: checked above)


def _macro_prims(name, body, params, layer):
    """Primitives of an aperture macro for given parameters: ("circ", x, y, r) | ("poly", points)."""
    var = {i + 1: v for i, v in enumerate(params)}
    prims = []
    for stmt in body:
        stmt = stmt.strip()
        if not stmt or stmt.startswith("0"):
            continue
        if stmt.startswith("$") and "=" in stmt:
            k, e = stmt.split("=", 1)
            var[int(k[1:])] = _eval(e, var)
            continue
        f = [_eval(t, var) for t in stmt.split(",")]
        code = int(f[0])
        if code != 7 and len(f) > 1 and int(f[1]) != 1:
            layer.note(f"aperture macro {name}: a primitive with exposure off (a cut-out inside the pad) is left out")
            continue
        if code == 1:                               # circle: exposure, diameter, x, y[, rotation]
            cx, cy = f[3], f[4]
            if len(f) > 5:
                cx, cy = _rot(cx, cy, f[5])
            prims.append(("circ", cx, cy, f[2] / 2))
        elif code in (2, 20):                       # vector line: exposure, width, x1, y1, x2, y2, rotation
            w, x1, y1, x2, y2 = f[2], f[3], f[4], f[5], f[6]
            rot = f[7] if len(f) > 7 else 0.0
            ln = math.hypot(x2 - x1, y2 - y1) or 1e-12
            nx, ny = -(y2 - y1) / ln * w / 2, (x2 - x1) / ln * w / 2
            pts = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
            prims.append(("poly", [_rot(px, py, rot) for px, py in pts]))
        elif code == 21:                            # centre line: exposure, width, height, cx, cy, rotation
            w, h, cx, cy = f[2] / 2, f[3] / 2, f[4], f[5]
            rot = f[6] if len(f) > 6 else 0.0
            pts = [(cx - w, cy - h), (cx + w, cy - h), (cx + w, cy + h), (cx - w, cy + h)]
            prims.append(("poly", [_rot(px, py, rot) for px, py in pts]))
        elif code == 22:                            # lower-left line (deprecated): exposure, width, height, x, y, rotation
            w, h, x0, y0 = f[2], f[3], f[4], f[5]
            rot = f[6] if len(f) > 6 else 0.0
            pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
            prims.append(("poly", [_rot(px, py, rot) for px, py in pts]))
        elif code == 4:                             # outline: exposure, n, x0, y0, ..., xn, yn, rotation
            n = int(f[2])
            pts = [(f[3 + 2 * i], f[4 + 2 * i]) for i in range(n)]
            rot = f[3 + 2 * (n + 1)] if len(f) > 3 + 2 * (n + 1) else 0.0
            prims.append(("poly", [_rot(px, py, rot) for px, py in pts]))
        elif code == 5:                             # polygon: exposure, vertices, cx, cy, diameter, rotation
            n, cx, cy, dia = int(f[2]), f[3], f[4], f[5]
            rot = f[6] if len(f) > 6 else 0.0
            pts = [(cx + dia / 2 * math.cos(2 * math.pi * i / n), cy + dia / 2 * math.sin(2 * math.pi * i / n))
                   for i in range(n)]
            prims.append(("poly", [_rot(px, py, rot) for px, py in pts]))
        elif code == 7:                             # thermal: cx, cy, outer, inner, gap, rotation
            layer.note(f"aperture macro {name}: a thermal primitive is drawn as a full disc of its outer diameter")
            prims.append(("circ", f[1], f[2], f[3] / 2))
        else:
            raise GerberError(f"{layer.name}: aperture macro {name} uses primitive {code}, which this reader does not know")
    return prims


def _aperture(name, vals, macros, layer, code):
    """-> ("C", d) | ("R", w, h) | ("M", prims, reach)"""
    if name == "C":
        if len(vals) > 1 and vals[1] > 0:
            layer.note("round apertures with a hole are drawn without the hole")
        return ("C", vals[0])
    if name == "R":
        if len(vals) > 2 and vals[2] > 0:
            layer.note("rectangular apertures with a hole are drawn without the hole")
        return ("R", vals[0], vals[1])
    if name == "O":
        w, h = vals[0], vals[1]
        if w >= h:
            return ("M", [("stad", -(w - h) / 2, 0.0, (w - h) / 2, 0.0, h / 2)], max(w, h) / 2)
        return ("M", [("stad", 0.0, -(h - w) / 2, 0.0, (h - w) / 2, w / 2)], max(w, h) / 2)
    if name == "P":
        dia, n = vals[0], int(vals[1])
        rot = vals[2] if len(vals) > 2 else 0.0
        pts = [_rot(dia / 2 * math.cos(2 * math.pi * i / n), dia / 2 * math.sin(2 * math.pi * i / n), rot) for i in range(n)]
        return ("M", [("poly", pts)], dia / 2)
    if name in macros:
        prims = _macro_prims(name, macros[name], vals, layer)
        reach = 0.0
        for p in prims:
            if p[0] == "circ":
                reach = max(reach, math.hypot(p[1], p[2]) + p[3])
            else:
                reach = max([reach] + [math.hypot(x, y) for x, y in p[1]])
        return ("M", prims, reach)
    raise GerberError(f"{layer.name}: aperture D{code} has the unknown type {name!r}")


def _tokens(txt):
    """The commands of a Gerber file in order: ("%", text between the percent signs) or ("*", one statement)."""
    i, n = 0, len(txt)
    while i < n:
        c = txt[i]
        if c == "%":
            j = txt.find("%", i + 1)
            if j < 0:
                raise GerberError("an extended command is not closed with %")
            yield "%", txt[i + 1:j]
            i = j + 1
        elif c in " \t\r\n":
            i += 1
        else:
            j = txt.find("*", i)
            if j < 0:
                if txt[i:].strip():
                    raise GerberError("the file ends inside a command")
                return
            yield "*", txt[i:j].strip()
            i = j + 1


_COORD = re.compile(r"(?:X([+-]?\d+))?(?:Y([+-]?\d+))?(?:I([+-]?\d+))?(?:J([+-]?\d+))?(?:D0*(\d+))?$")


def read_gerber(path: str) -> Layer:
    """Read one Gerber file (RS-274X / X2). GerberError when the file uses something this reader does not know."""
    lay = Layer(path)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError as e:
        raise GerberError(f"{path}: {e}") from None
    if "D0" not in txt and "D1" not in txt and "%FS" not in txt:
        raise GerberError(f"{lay.name}: not a Gerber file")
    macros, aps = {}, {}
    fmt, k, zero_trail, incremental = None, 1.0, False, False
    x = y = 0.0
    interp, quad_multi, last_d = 1, True, None
    cur, region, contour, dark = None, False, [], True
    sr, sr_start = None, 0

    def close_sr():
        nonlocal sr
        if sr and (sr[0] > 1 or sr[1] > 1):
            block, pblock = lay.items[sr_start:], lay.paths[sr_start_p:]
            for ix in range(sr[0]):
                for iy in range(sr[1]):
                    if ix == 0 and iy == 0:
                        continue
                    ox, oy = ix * sr[2], iy * sr[3]
                    for it in block:
                        lay.items.append(_shift(it, ox, oy))
                    for p in pblock:
                        lay.paths.append([(px + ox, py + oy) for px, py in p])
        sr = None

    sr_start_p = 0

    def num(s, is_x=True):
        if fmt is None:
            raise GerberError(f"{lay.name}: coordinates before the format statement (FS)")
        neg = s.startswith("-")
        digits = s.lstrip("+-")
        if zero_trail:                                  # trailing zeros omitted: pad to the full length
            digits = digits.ljust(fmt[0] + fmt[1], "0")
        return (-1 if neg else 1) * int(digits) / (10 ** fmt[1]) * k

    def stroke(pts):
        lay.paths.append(pts)
        if cur is None:
            raise GerberError(f"{lay.name}: a draw before any aperture was selected")
        if cur[0] == "C":
            r = cur[1] / 2
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                lay.items.append(("seg", ax, ay, bx, by, r, dark))
        elif cur[0] == "R":
            w, h = cur[1] / 2, cur[2] / 2
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                corners = [(px + sx * w, py + sy * h) for px, py in ((ax, ay), (bx, by)) for sx in (-1, 1) for sy in (-1, 1)]
                lay.items.append(("poly", _hull(corners), dark))
        else:
            lay.note("a draw with an aperture that is neither round nor rectangular is drawn as a round stroke of "
                     "its largest size")
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                lay.items.append(("seg", ax, ay, bx, by, cur[2], dark))

    def flash(fx, fy):
        if cur is None:
            raise GerberError(f"{lay.name}: a flash before any aperture was selected")
        if cur[0] == "C":
            lay.items.append(("circ", fx, fy, cur[1] / 2, dark))
        elif cur[0] == "R":
            w, h = cur[1] / 2, cur[2] / 2
            lay.items.append(("poly", [(fx - w, fy - h), (fx + w, fy - h), (fx + w, fy + h), (fx - w, fy + h)], dark))
        else:
            for p in cur[1]:
                if p[0] == "circ":
                    lay.items.append(("circ", fx + p[1], fy + p[2], p[3], dark))
                elif p[0] == "stad":
                    lay.items.append(("seg", fx + p[1], fy + p[2], fx + p[3], fy + p[4], p[5], dark))
                else:
                    lay.items.append(("poly", [(fx + px, fy + py) for px, py in p[1]], dark))

    for kind, body in _tokens(txt):
        if kind == "%":
            for stmt in [s.strip() for s in body.split("*") if s.strip()] if not body.lstrip().startswith("AM") else [body]:
                if stmt.startswith("FS"):
                    m = re.match(r"FS([LT])([AI])X(\d)(\d)Y(\d)(\d)", stmt)
                    if not m:
                        raise GerberError(f"{lay.name}: format statement {stmt!r} cannot be read")
                    zero_trail, incremental = m.group(1) == "T", m.group(2) == "I"
                    fmt = (int(m.group(3)), int(m.group(4)))
                    if incremental:
                        raise GerberError(f"{lay.name}: incremental coordinates are not supported")
                elif stmt.startswith("MO"):
                    k = 25.4 if "IN" in stmt else 1.0
                    lay.unit = "inch" if k != 1.0 else "mm"
                elif stmt.startswith("AM"):
                    parts = [p.strip() for p in stmt[2:].split("*")]
                    macros[parts[0]] = [p for p in parts[1:] if p]
                elif stmt.startswith("AD"):
                    m = re.match(r"ADD(\d+)([A-Za-z_$][\w.$-]*),?(.*)$", stmt)
                    if not m:
                        raise GerberError(f"{lay.name}: aperture definition {stmt!r} cannot be read")
                    vals = [float(v) for v in m.group(3).split("X") if v.strip()] if m.group(3) else []
                    name = m.group(2)
                    if name in ("C", "R", "O", "P") or name in macros:
                        scaled = [v * k for v in vals] if name in ("C", "R", "O") else \
                            ([vals[0] * k] + vals[1:3] + [v * k for v in vals[3:]] if name == "P" else vals)
                        ap = _aperture(name, scaled, macros, lay, m.group(1))
                        if name in macros and k != 1.0:     # macro geometry is in file units
                            ap = ("M", [_scale_prim(p, k) for p in ap[1]], ap[2] * k)
                        aps[int(m.group(1))] = ap
                    else:
                        raise GerberError(f"{lay.name}: aperture D{m.group(1)} has the unknown type {name!r}")
                elif stmt.startswith("LP"):
                    dark = stmt[2:3] != "C"
                elif stmt.startswith("SR"):
                    close_sr()
                    m = re.match(r"SRX(\d+)Y(\d+)I([\d.]+)J([\d.]+)", stmt)
                    if m:
                        sr = (int(m.group(1)), int(m.group(2)), float(m.group(3)) * k, float(m.group(4)) * k)
                        sr_start, sr_start_p = len(lay.items), len(lay.paths)
                elif stmt.startswith(("TF", "TA", "TO", "TD")):
                    if stmt.startswith("TF."):
                        key, _, val = stmt[3:].partition(",")
                        lay.attrs[key] = val
                elif stmt.startswith("IP"):
                    if "NEG" in stmt:
                        raise GerberError(f"{lay.name}: negative image polarity (IPNEG) is not supported")
                elif stmt.startswith(("LM", "LR", "LS")):
                    v = stmt[2:]
                    if (stmt.startswith("LM") and v != "N") or (stmt.startswith("LR") and float(v or 0) != 0.0) or \
                            (stmt.startswith("LS") and float(v or 1) != 1.0):
                        raise GerberError(f"{lay.name}: the layer transform {stmt} is not supported")
                elif stmt.startswith(("AB", "MI", "OF", "SF", "IR", "AS")):
                    if stmt.startswith("AB"):
                        raise GerberError(f"{lay.name}: aperture blocks (AB) are not supported")
                    if re.search(r"[1-9]", stmt[2:]) and not stmt.startswith(("SFA1B1", "SFA1.0B1.0", "ASAXBY")):
                        raise GerberError(f"{lay.name}: the deprecated image transform {stmt} is not supported")
                # IN, LN, and anything else: names and comments
            continue
        s = body
        if not s:
            continue
        if s.startswith("G04"):
            m = re.match(r"G04\s*#@!\s*TF\.([^,]+),?(.*)$", s)
            if m:
                lay.attrs[m.group(1)] = m.group(2)
            continue
        while True:                                     # leading G codes
            m = re.match(r"G0*(\d+)", s)
            if not m:
                break
            g = int(m.group(1))
            s = s[m.end():]
            if g in (1, 2, 3):
                interp = g
            elif g == 36:
                region, contour = True, []
            elif g == 37:
                if len(contour) > 2:
                    lay.items.append(("poly", contour, dark))
                region, contour = False, []
            elif g == 74:
                quad_multi = False
            elif g == 75:
                quad_multi = True
            elif g == 70:
                k, lay.unit = 25.4, "inch"
            elif g == 71:
                k, lay.unit = 1.0, "mm"
            elif g == 91:
                raise GerberError(f"{lay.name}: incremental coordinates (G91) are not supported")
            elif g in (54, 55, 90):
                pass
            else:
                raise GerberError(f"{lay.name}: unknown code G{g}")
        if not s or s in ("M02", "M00", "M01", "M2"):
            if s.startswith("M0") or s == "M2":
                break
            continue
        m = _COORD.match(s)
        if not m:
            raise GerberError(f"{lay.name}: cannot read {body!r}")
        gx, gy, gi, gj, gd = m.groups()
        if gd is not None and int(gd) >= 10 and gx is None and gy is None:
            if int(gd) not in aps:
                raise GerberError(f"{lay.name}: aperture D{gd} is used but not defined")
            cur = aps[int(gd)]
            continue
        nx = num(gx) if gx is not None else x
        ny = num(gy) if gy is not None else y
        op = int(gd) if gd is not None else last_d
        if op is None:
            raise GerberError(f"{lay.name}: a coordinate without an operation code: {body!r}")
        if op in (1, 2, 3):
            last_d = op
        if op == 2:
            if region and len(contour) > 2:
                lay.items.append(("poly", contour, dark))
            contour = [(nx, ny)] if region else contour
        elif op == 1:
            if interp == 1:
                pts = [(x, y), (nx, ny)]
            else:
                ii = num(gi) if gi is not None else 0.0
                jj = num(gj) if gj is not None else 0.0
                if quad_multi:
                    cx, cy = x + ii, y + jj
                else:
                    cx, cy = _single_quadrant_centre(x, y, nx, ny, abs(ii), abs(jj), interp == 2)
                pts = arc_points(x, y, nx, ny, cx, cy, interp == 2)
            if region:
                if not contour:
                    contour = [(x, y)]
                contour += pts[1:]
            elif (x, y) != (nx, ny) or interp != 1:
                stroke(pts)
            else:
                stroke([(x, y), (nx, ny)])
        elif op == 3:
            flash(nx, ny)
        else:
            raise GerberError(f"{lay.name}: cannot read {body!r}")
        x, y = nx, ny
    close_sr()
    return lay


def _shift(it, ox, oy):
    if it[0] == "poly":
        return ("poly", [(px + ox, py + oy) for px, py in it[1]], it[2])
    if it[0] == "circ":
        return ("circ", it[1] + ox, it[2] + oy, it[3], it[4])
    return ("seg", it[1] + ox, it[2] + oy, it[3] + ox, it[4] + oy, it[5], it[6])


def _scale_prim(p, k):
    if p[0] == "circ":
        return ("circ", p[1] * k, p[2] * k, p[3] * k)
    if p[0] == "stad":
        return ("stad",) + tuple(v * k for v in p[1:])
    return ("poly", [(px * k, py * k) for px, py in p[1]])


def _single_quadrant_centre(x0, y0, x1, y1, i, j, cw):
    """Centre of a single-quadrant arc (G74): the offsets are unsigned; the centre is the one of the four that
    gives equal radii and an arc of at most 90 degrees."""
    best = None
    for sx in (1, -1):
        for sy in (1, -1):
            cx, cy = x0 + sx * i, y0 + sy * j
            err = abs(math.hypot(x0 - cx, y0 - cy) - math.hypot(x1 - cx, y1 - cy))
            a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
            sweep = (a0 - a1) % (2 * math.pi) if cw else (a1 - a0) % (2 * math.pi)
            if sweep <= math.pi / 2 + 1e-6 and (best is None or err < best[0]):
                best = (err, cx, cy)
    if best is None:
        raise GerberError("a single-quadrant arc (G74) has no valid centre")
    return best[1], best[2]


# ---- drill files -----------------------------------------------------------------------------------------------------
class Drill:
    """One Excellon drill file: holes [(x, y, diameter)], slots [(x0, y0, x1, y1, diameter)], in mm; plated is
    True, False or None (unknown); notes as in Layer."""

    def __init__(self, path):
        self.path, self.name = path, os.path.basename(path)
        self.holes, self.slots, self.notes, self.plated = [], [], [], None

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)


def read_drill(path: str) -> Drill:
    """Read an Excellon drill file (as KiCad, EasyEDA, Altium and Eagle write them). GerberError when unreadable."""
    d = Drill(path)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [ln.strip() for ln in f.read().splitlines()]
    except OSError as e:
        raise GerberError(f"{path}: {e}") from None
    if not any(ln.startswith("M48") for ln in lines[:20]) and not any(re.match(r"T\d+C", ln) for ln in lines):
        raise GerberError(f"{d.name}: not an Excellon drill file")
    low = d.name.lower()
    if "npth" in low or "nonplated" in low or "non-plated" in low:
        d.plated = False
    elif "pth" in low or "plated" in low:
        d.plated = True
    k, lz, fmt, explicit_fmt, zero_stated = 1.0, False, None, False, False
    tools, cur = {}, None
    x = y = 0.0
    routing, rout_from, header = False, None, True

    def val(s):
        if "." in s:
            return float(s) * k
        nonlocal_fmt = fmt or ((3, 3) if k == 1.0 else (2, 4))
        neg = s.startswith("-")
        digits = s.lstrip("+-")
        if lz:                                          # leading zeros kept, trailing omitted
            digits = digits.ljust(nonlocal_fmt[0] + nonlocal_fmt[1], "0")
        if not explicit_fmt:
            d.note("coordinates without a decimal point and no stated format: 3.3 (mm) or 2.4 (inch) digits assumed")
        if not zero_stated:
            d.note("coordinates without a decimal point and no LZ/TZ statement: trailing zeros taken as written")
        return (-1 if neg else 1) * int(digits) / (10 ** nonlocal_fmt[1]) * k

    for ln in lines:
        if not ln:
            continue
        if ln.startswith(";"):
            if "TF.FileFunction" in ln:
                d.plated = False if "NonPlated" in ln else (True if "Plated" in ln else d.plated)
            m = re.search(r"FORMAT=\{?(\d+|-):(\d+)", ln)
            if m and m.group(1) != "-":
                fmt, explicit_fmt = (int(m.group(1)), int(m.group(2))), True
            elif m:
                explicit_fmt = True
            continue
        up = ln.upper()
        if up.startswith(("METRIC", "INCH", "M71", "M72")):
            k = 1.0 if up.startswith(("METRIC", "M71")) else 25.4
            if ",TZ" in up:
                lz, zero_stated = False, True
            elif ",LZ" in up:
                lz, zero_stated = True, True
            m = re.search(r",(0+)\.(0+)", up)
            if m:
                fmt, explicit_fmt = (len(m.group(1)), len(m.group(2))), True
            continue
        if up in ("M48", "FMAT,2", "FMAT,1", "G90", "G05", "M30", "M00", "VER,1", "DETECT,ON", "ICI,OFF", "ATC,ON") \
                or up.startswith(("FMAT", "VER", "DETECT", "ATC", "M47", "G93", "TCST", "OSTOP", "RSTOP")):
            continue
        if up.startswith("ICI"):
            raise GerberError(f"{d.name}: incremental coordinates are not supported")
        if up in ("%", "M95"):
            header = False
            continue
        m = re.match(r"T(\d+)(?:.*?C([\d.]+))?", up)
        if m and (header or m.group(2)):
            if m.group(2):
                tools[int(m.group(1))] = float(m.group(2)) * k
            if not header:
                cur = int(m.group(1))
            continue
        if m:
            cur = int(m.group(1))
            if cur != 0 and cur not in tools:
                raise GerberError(f"{d.name}: tool T{cur} is used but not defined")
            continue
        if up.startswith("M15"):
            routing, rout_from = True, (x, y)
            continue
        if up.startswith(("M16", "M17")):
            routing = False
            continue
        g = None
        m = re.match(r"G0*(\d+)", up)
        if m and "X" in up or m and "Y" in up:
            g = int(m.group(1))
            up = up[m.end():]
        if "G85" in up:
            a, b = up.split("G85", 1)
            pa, pb = _xy(a, x, y, val), None
            pb = _xy(b, pa[0], pa[1], val)
            d.slots.append((pa[0], pa[1], pb[0], pb[1], tools.get(cur, 0.0)))
            x, y = pb
            continue
        if re.match(r"[XY]", up):
            nx, ny = _xy(up, x, y, val)
            if g in (1, 2, 3) and routing:
                if g != 1:
                    d.note("a routed arc is drawn as a straight slot between its ends")
                d.slots.append((x, y, nx, ny, tools.get(cur, 0.0)))
            elif g == 0:
                pass                                    # rapid move to the start of a rout
            elif routing:
                d.slots.append((x, y, nx, ny, tools.get(cur, 0.0)))
            else:
                if cur is None:
                    raise GerberError(f"{d.name}: a hole before any tool was selected")
                d.holes.append((nx, ny, tools[cur]))
            x, y = nx, ny
            continue
        if up.startswith(("G", "M", "R")):
            if up.startswith("R"):
                raise GerberError(f"{d.name}: repeat commands ({ln}) are not supported")
            continue
        d.note(f"line not understood and left out: {ln[:40]}")
    return d


def _xy(s, x, y, val):
    m = re.match(r"(?:X([+-]?[\d.]+))?(?:Y([+-]?[\d.]+))?", s)
    return (val(m.group(1)) if m and m.group(1) else x, val(m.group(2)) if m and m.group(2) else y)


# ---- which file is which -------------------------------------------------------------------------------------------
_NAME_RULES = [                     # (kind, side, regular expression on the lower-case file name); first match wins
    ("outline", "", r"edge[._-]?cuts|\.gm1$|\.gko$|\.gml$|outline|profile|\.dim$|\.oln$|\.gm\d+$"),
    ("drillmap", "", r"drl_map|drill[-_]?map|drillmap|\.gd\d$|drilldrawing|\.gg\d$"),
    ("mask", "top", r"f[._]mask|\.gts$|topsolder|soldermask[-_]?top|\.stc$"),
    ("mask", "bottom", r"b[._]mask|\.gbs$|bottomsolder|soldermask[-_]?bot|\.sts$"),
    ("paste", "top", r"f[._]paste|\.gtp$|toppaste|\.crc$"),
    ("paste", "bottom", r"b[._]paste|\.gbp$|bottompaste|\.crs$"),
    ("silk", "top", r"f[._]silk|\.gto$|topsilk|silkscreen[-_]?top|\.plc$"),
    ("silk", "bottom", r"b[._]silk|\.gbo$|bottomsilk|silkscreen[-_]?bot|\.pls$"),
    ("fab", "top", r"f[._]fab|topassembly|assembly[-_]?top"),
    ("fab", "bottom", r"b[._]fab|bottomassembly|assembly[-_]?bot"),
    ("copper", "top", r"f[._]cu|\.gtl$|toplayer|top[-_]?copper|\.cmp$|copper[-_]?top"),
    ("copper", "bottom", r"b[._]cu|\.gbl$|bottomlayer|bottom[-_]?copper|\.sol$|copper[-_]?bottom"),
    ("copper", "inner", r"in\d+[._]cu|\.g\d+$|\.gp\d+$|inner|\.ly\d+$"),
]
_OUTLINE_RANK = (r"edge[._-]?cuts", r"outline|profile", r"\.gko$", r"\.gm1$", r"\.gml$", r"\.gm\d+$")
_DRILL_EXT = (".drl", ".xln", ".txt", ".exc", ".drd", ".ncd", ".tap")
_SKIP_EXT = (".gbrjob", ".zip", ".csv", ".json", ".md", ".pdf", ".png", ".rep", ".rpt", ".rul", ".extrep", ".apr",
             ".ldp", ".drr", ".reports", ".html", ".xml", ".pos")


def classify(path: str, attrs: dict | None = None) -> tuple[str, str]:
    """(kind, side) of a production file: kind is copper, mask, paste, silk, outline, fab, drill, drillmap or
    other; side is top, bottom, inner or ''. The file's own attributes win over its name."""
    low = os.path.basename(path).lower()
    ff = (attrs or {}).get("FileFunction", "")
    if ff:
        p = [s.strip() for s in ff.split(",")]
        k = p[0].lower()
        side = "top" if "Top" in p else "bottom" if "Bot" in p else "inner" if "Inr" in p else ""
        table = {"copper": "copper", "soldermask": "mask", "paste": "paste", "legend": "silk", "profile": "outline",
                 "assemblydrawing": "fab", "drillmap": "drillmap", "plated": "drill", "nonplated": "drill"}
        if k in table:
            return table[k], side
        return "other", side
    if low.endswith(_DRILL_EXT) and not re.search(r"drl_map|drill[-_]?map", low):
        return "drill", ""
    for kind, side, rx in _NAME_RULES:
        if re.search(rx, low):
            return kind, side
    return "other", ""


def find_files(folder: str) -> dict:
    """The production files of a folder: {"gerbers": [(path, kind, side, Layer or None, error)], "drills": [...]}.
    Files are read here, so a file that cannot be read is listed with its reason instead of stopping the rest."""
    out = {"gerbers": [], "drills": [], "skipped": []}
    for path in sorted(glob.glob(os.path.join(glob.escape(folder), "*"))):
        if not os.path.isfile(path):
            continue
        low = path.lower()
        if low.endswith(_SKIP_EXT):
            out["skipped"].append(os.path.basename(path))
            continue
        try:
            with open(path, "rb") as f:
                head = f.read(4096)
        except OSError:
            continue
        if b"\x00" in head:
            out["skipped"].append(os.path.basename(path))
            continue
        text = head.decode("utf-8", errors="replace")
        if low.endswith(_DRILL_EXT) and ("M48" in text or re.search(r"T\d+C", text)):
            try:
                out["drills"].append((path, read_drill(path), ""))
            except kicad_io.KicadIOError as e:
                out["drills"].append((path, None, str(e)))
            continue
        if "%FS" in text or "%MO" in text or re.search(r"G04|%ADD", text):
            try:
                lay = read_gerber(path)
                kind, side = classify(path, lay.attrs)
                out["gerbers"].append((path, kind, side, lay, ""))
            except kicad_io.KicadIOError as e:
                kind, side = classify(path)
                out["gerbers"].append((path, kind, side, None, str(e)))
            continue
        out["skipped"].append(os.path.basename(path))
    return out


# ---- outline ---------------------------------------------------------------------------------------------------------
def contours(paths, tol=CHAIN_TOL):
    """Chain strokes into contours: [(points, closed)]."""
    segs = [list(p) for p in paths if len(p) > 1]
    loops = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while changed and math.hypot(cur[0][0] - cur[-1][0], cur[0][1] - cur[-1][1]) > tol:
            changed = False
            for i, p in enumerate(segs):
                if math.hypot(p[0][0] - cur[-1][0], p[0][1] - cur[-1][1]) <= tol:
                    cur += p[1:]
                elif math.hypot(p[-1][0] - cur[-1][0], p[-1][1] - cur[-1][1]) <= tol:
                    cur += p[::-1][1:]
                elif math.hypot(p[-1][0] - cur[0][0], p[-1][1] - cur[0][1]) <= tol:
                    cur = p[:-1] + cur
                elif math.hypot(p[0][0] - cur[0][0], p[0][1] - cur[0][1]) <= tol:
                    cur = p[::-1][:-1] + cur
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        closed = len(cur) > 3 and math.hypot(cur[0][0] - cur[-1][0], cur[0][1] - cur[-1][1]) <= tol
        loops.append((cur[:-1] if closed else cur, closed))
    return loops


def _item_edges(it):
    if it[0] == "poly":
        p = it[1]
        return [(p[i][0], p[i][1], p[(i + 1) % len(p)][0], p[(i + 1) % len(p)][1]) for i in range(len(p))], 0.0
    if it[0] == "circ":
        return [(it[1], it[2], it[1], it[2])], it[3]
    return [(it[1], it[2], it[3], it[4])], it[5]


def _first_point(it):
    return it[1][0] if it[0] == "poly" else (it[1], it[2])


def _item_boxes(layer):
    """Bounding box (x0, y0, x1, y1) of every item of a layer, in the file's frame."""
    out = []
    for it in layer.items:
        if it[0] == "poly":
            out.append(pcb_common.poly_box(it[1]))
        elif it[0] == "circ":
            out.append((it[1] - it[3], it[2] - it[3], it[1] + it[3], it[2] + it[3]))
        else:
            r = it[5]
            out.append((min(it[1], it[3]) - r, min(it[2], it[4]) - r, max(it[1], it[3]) + r, max(it[2], it[4]) + r))
    return out


class Outline:
    def __init__(self, layer: Layer):
        self.loops = contours(layer.paths)
        self.closed = [lp for lp, c in self.loops if c and len(lp) >= 3]
        self.open = [lp for lp, c in self.loops if not c]
        self.segs = []
        for p in layer.paths:
            self.segs += [(ax, ay, bx, by) for (ax, ay), (bx, by) in zip(p, p[1:]) if (ax, ay) != (bx, by)]
        self.cell = 0.5
        self.grid = {}
        for i, (ax, ay, bx, by) in enumerate(self.segs):
            for gx in range(int(math.floor(min(ax, bx) / self.cell)), int(math.floor(max(ax, bx) / self.cell)) + 1):
                for gy in range(int(math.floor(min(ay, by) / self.cell)), int(math.floor(max(ay, by) / self.cell)) + 1):
                    self.grid.setdefault((gx, gy), []).append(i)

    def on_board(self, x, y) -> bool:
        """Inside the board material: inside an odd number of closed contours."""
        return sum(1 for lp in self.closed if inside(x, y, lp)) % 2 == 1

    def distance(self, it, reach):
        """(distance of one copper item to the outline, point) or (None, None) when farther than `reach`."""
        edges, r = _item_edges(it)
        xs = [e[0] for e in edges] + [e[2] for e in edges]
        ys = [e[1] for e in edges] + [e[3] for e in edges]
        x0, x1 = min(xs) - r - reach, max(xs) + r + reach
        y0, y1 = min(ys) - r - reach, max(ys) + r + reach
        cand = set()
        c = self.cell
        for gx in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for gy in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                cand.update(self.grid.get((gx, gy), ()))
        best = (None, None)
        for i in cand:
            o = self.segs[i]
            for e in edges:
                d = max(0.0, seg_seg(e, o) - r)
                if best[0] is None or d < best[0]:
                    best = (d, ((e[0] + e[2]) / 2, (e[1] + e[3]) / 2))
        if best[0] is not None and best[0] > reach:
            return None, None
        return best


def band_reach(band: dict, it) -> float | None:
    """How near one copper item comes to the guided edge of a band (mm into the board; None when the item is not
    along the band's stretch). The band is in KiCad's frame: the item's y is negated. Round shapes are taken as
    16-sided polygons that hold the point nearest the edge, so the distance is exact along the stretch."""
    (ux, uy), (nx, ny) = band["u"], band["n"]

    def disc(x, y, r):
        return [(x + r * (math.cos(k * math.pi / 8) * nx + math.sin(k * math.pi / 8) * ux),
                 y + r * (math.cos(k * math.pi / 8) * ny + math.sin(k * math.pi / 8) * uy)) for k in range(16)]
    if it[0] == "poly":
        pts = [(x, -y) for x, y in it[1]]
    elif it[0] == "circ":
        pts = disc(it[1], -it[2], it[3])
    elif it[5] > 0:
        pts = _hull(disc(it[1], -it[2], it[5]) + disc(it[3], -it[4], it[5]))
    else:
        pts = [(it[1], -it[2]), (it[3], -it[4])]
    return pcb_common.band_reach(band, pts)


def check_folder(folder: str, limit: float, allow: list, which: str, outline_file: str | None = None,
                 band_fn=None) -> dict:
    """Measure one Gerber folder. Returns a result dict; raises KicadIOError when the check cannot run.
    band_fn(box of the outline in KiCad's frame) -> (edge bands, where they come from), or None for no bands."""
    if not os.path.isdir(folder):
        raise kicad_io.KicadIOError(f"no such Gerber folder: {folder}")
    files = find_files(folder)
    profile = [g for g in files["gerbers"] if g[1] == "outline"]
    copper = [g for g in files["gerbers"] if g[1] == "copper"]
    picked_note = ""
    if outline_file:
        profile = [g for g in files["gerbers"] if os.path.basename(g[0]).lower() == os.path.basename(outline_file).lower()]
        if not profile:
            raise kicad_io.KicadIOError(f"{folder}: the outline file {outline_file} is not a Gerber file of this folder")
    if not profile:
        raise kicad_io.KicadIOError(f"{folder}: no board-outline (profile) Gerber found; name it with --outline")
    if len(profile) > 1:
        def rank(g):
            if g[3] is not None and g[3].attrs.get("FileFunction", "").startswith("Profile"):
                return -1
            low = os.path.basename(g[0]).lower()
            return next((i for i, rx in enumerate(_OUTLINE_RANK) if re.search(rx, low)), len(_OUTLINE_RANK))
        profile.sort(key=rank)
        picked_note = (f"several outline candidates ({', '.join(os.path.basename(g[0]) for g in profile)}): "
                       f"{os.path.basename(profile[0][0])} is used; name another with --outline")
        profile = profile[:1]
    if not copper:
        raise kicad_io.KicadIOError(f"{folder}: no copper-layer Gerber found")
    bad = [g for g in profile + copper if g[3] is None]
    if bad:
        raise kicad_io.KicadIOError("; ".join(g[4] for g in bad))
    out = Outline(profile[0][3])
    if not out.segs:
        raise kicad_io.KicadIOError(f"{os.path.basename(profile[0][0])}: the outline file draws nothing")
    kicad_made = "kicad" in profile[0][3].attrs.get("GenerationSoftware", "").lower()
    boxes = [a for a in allow if a.get("on", "both") in ("both", which)]
    res = {"folder": folder, "which": which, "outline_file": os.path.basename(profile[0][0]),
           "closed_contours": len(out.closed), "open_contours": len(out.open), "outline_segments": len(out.segs),
           "open_ends": [[round(lp[0][0], 3), round(lp[0][1], 3)] for lp in out.open][:10],
           "kicad_frame": kicad_made, "limit": limit, "layers": [],
           "notes": list(profile[0][3].notes) + ([picked_note] if picked_note else []),
           "other_files": [os.path.basename(g[0]) for g in files["gerbers"] if g[1] not in ("copper", "outline")]}
    reach = max(limit, max([a.get("min", 0.0) for a in boxes] or [0.0])) + 0.5
    bands, res["bands_from"], res["bands_without_limit"] = [], "", []
    if band_fn and out.closed:
        xs = [p[0] for lp in out.closed for p in lp]
        ys = [p[1] for lp in out.closed for p in lp]
        found, res["bands_from"] = band_fn((min(xs), -max(ys), max(xs), -min(ys)))
        bands = [b for b in found if b["copper_to_edge"] is not None]
        res["bands_without_limit"] = [b["name"] for b in found if b["copper_to_edge"] is None]
        if bands and not kicad_made:
            res["notes"].append("these Gerber files were not written by KiCad: the span and line of an edge band are "
                                "read as (x, -y) of the files' own frame")
    for path, _, side, lay, _ in copper:
        row = {"file": os.path.basename(path), "side": side, "items": len(lay.items), "notes": list(lay.notes),
               "min": None, "where": None, "under": [], "outside": [], "allowed": [], "bands": [], "result": "PASS"}
        if lay.attrs.get("FilePolarity", "").strip().lower().startswith("negative"):
            row["result"] = "UNKNOWN"
            row["notes"].append("negative plane layer: copper is what is NOT drawn; not measured")
            res["layers"].append(row)
            continue
        n_clear = 0
        for it in lay.items:
            if not it[-1]:
                n_clear += 1
                continue
            px, py = _first_point(it)
            d, pt = out.distance(it, reach)
            if d is not None and (row["min"] is None or d < row["min"]):
                row["min"], row["where"] = d, pt
            if d is not None and d < limit - 1e-4:
                box = next((a for a in boxes if a["box"][0] <= pt[0] <= a["box"][2] and a["box"][1] <= pt[1] <= a["box"][3]
                            and d >= float(a.get("min", 0.0)) - 1e-4), None)
                entry = {"d": round(d, 4), "x": round(pt[0], 3), "y": round(pt[1], 3), "kind": it[0]}
                if box:
                    entry["reason"] = box.get("reason", "")
                    row["allowed"].append(entry)
                else:
                    row["under"].append(entry)
            elif (d is None or d > 0.0) and out.closed and not out.on_board(px, py):
                row["outside"].append({"x": round(px, 3), "y": round(py, 3), "kind": it[0]})
        if n_clear:
            row["notes"].append(f"{n_clear} clear-polarity item(s) (copper removed) left out: the result can only be "
                                f"too strict")
        for band in bands:
            if side not in ("top", "bottom") or band["sides"] not in ("both", side):
                continue
            lim_b = band["copper_to_edge"]
            (nx, ny), ln = band["n"], band["line"]
            zone = pcb_common.poly_box([(ln[0], ln[1]), (ln[2], ln[3]), (ln[2] + nx * (lim_b + 0.5), ln[3] + ny * (lim_b + 0.5)),
                                        (ln[0] + nx * (lim_b + 0.5), ln[1] + ny * (lim_b + 0.5))])
            br = {"name": band["name"], "edge": band["edge"], "limit": lim_b, "min": None, "where": None, "under": [],
                  "allowed": []}
            for it, b in zip(lay.items, _item_boxes(lay)):
                if not it[-1] or b[2] < zone[0] or b[0] > zone[2] or -b[1] < zone[1] or -b[3] > zone[3]:
                    continue
                v = band_reach(band, it)
                if v is None:
                    continue
                pt = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                if br["min"] is None or v < br["min"]:
                    br["min"], br["where"] = v, pt
                if v < lim_b - 1e-4:
                    box = next((a for a in boxes if a["box"][0] <= pt[0] <= a["box"][2] and a["box"][1] <= pt[1] <= a["box"][3]
                                and v >= float(a.get("min", 0.0)) - 1e-4), None)
                    entry = {"d": round(v, 4), "x": round(pt[0], 3), "y": round(pt[1], 3), "kind": it[0]}
                    if box:
                        entry["reason"] = box.get("reason", "")
                    br["allowed" if box else "under"].append(entry)
            br["result"] = "FAIL" if br["under"] else "PASS"
            row["bands"].append(br)
        if row["under"] or row["outside"] or any(b["under"] for b in row["bands"]):
            row["result"] = "FAIL"
        res["layers"].append(row)
    res["result"] = "FAIL" if (out.open or not out.closed or any(r["result"] == "FAIL" for r in res["layers"])) else \
        ("UNKNOWN" if any(r["result"] == "UNKNOWN" for r in res["layers"]) else "PASS")
    return res


def _where(pt, kicad):
    if pt is None:
        return "-"
    s = f"({pt[0]:.2f}, {pt[1]:.2f}) Gerber"
    return s + f" = ({pt[0]:.2f}, {-pt[1]:.2f}) KiCad" if kicad else s


def report_lines(res: dict) -> list[str]:
    kic = res["kicad_frame"]
    out = [f"## {res['which'].capitalize()}: `{os.path.basename(res['folder'].rstrip(os.sep))}`", "",
           f"Outline `{res['outline_file']}`: {res['closed_contours']} closed contour(s), {res['open_contours']} open; "
           f"{res['outline_segments']} segments (arcs split to <= {ARC_TOL * 1000:.0f} um chord error). "
           f"Limit: every copper feature >= {res['limit']:.2f} mm from the outline's centre line and inside the board.", ""]
    if res["open_contours"] or not res["closed_contours"]:
        ends = ", ".join(f"({x:.2f}, {y:.2f})" for x, y in res["open_ends"])
        out += [f"**FAIL: the outline is not closed** ({res['open_contours']} open contour(s); open ends near {ends}). "
                "Inside and outside cannot be told; the factory needs a closed outline.", ""]
    out += ["| Copper layer | Items | Min distance to the outline (mm) | Limit | Where | Under the limit | Outside the board | Result |",
            "|---|---|---|---|---|---|---|---|"]
    for r in res["layers"]:
        dtxt = f"{r['min']:.3f}" if r["min"] is not None else f"> {res['limit'] + 0.5:.2f}"
        if r["result"] == "UNKNOWN":
            dtxt = "not measured"
        out.append(f"| {r['file']} | {r['items']} | {dtxt} | {res['limit']:.2f} | {_where(r['where'], kic)} | "
                   f"{len(r['under'])} | {len(r['outside'])} | {r['result']} |")
    for r in res["layers"]:
        for key, title in (("under", "under the limit"), ("outside", "outside the board or inside a cut-out"),
                           ("allowed", "under the limit but allowed in board.toml")):
            if r[key]:
                out += ["", f"{r['file']}: {len(r[key])} feature(s) {title}" +
                        (f" (first {MAX_LISTED})" if len(r[key]) > MAX_LISTED else "") + ":"]
                for e in r[key][:MAX_LISTED]:
                    d = f"{e['d']:.3f} mm at " if "d" in e else ""
                    why = f" ({e['reason']})" if e.get("reason") else ""
                    out.append(f"- {d}{_where((e['x'], e['y']), kic)}, {e['kind']}{why}")
        for n in r["notes"]:
            out += ["", f"{r['file']}: note: {n}."]
    band_rows = [(r, b) for r in res["layers"] for b in r["bands"]]
    if band_rows:
        out += ["", f"Edge keep-out bands with their own copper-to-edge limit (from {res['bands_from']}): the nearest copper "
                "along each band's stretch of the edge, on the outer layer of each side the band names.", "",
                "| Band | Edge | Copper layer | Nearest copper to this edge (mm) | Limit (mm) | Where | Under the limit | Result |",
                "|---|---|---|---|---|---|---|---|"]
        for r, b in band_rows:
            dtxt = f"{b['min']:.3f}" if b["min"] is not None else f"> {b['limit'] + 0.5:.2f}"
            out.append(f"| {b['name']} | {b['edge']} | {r['file']} | {dtxt} | {b['limit']:.2f} | {_where(b['where'], kic)} | "
                       f"{len(b['under'])} | {b['result']} |")
        for r, b in band_rows:
            for key, title in (("under", "nearer than the band's limit"),
                               ("allowed", "nearer than the band's limit but allowed in board.toml")):
                if b[key]:
                    out += ["", f"{r['file']}, band '{b['name']}': {len(b[key])} feature(s) {title}" +
                            (f" (nearest {MAX_LISTED})" if len(b[key]) > MAX_LISTED else "") + ":"]
                    for e in sorted(b[key], key=lambda e: e["d"])[:MAX_LISTED]:
                        why = f" ({e['reason']})" if e.get("reason") else ""
                        out.append(f"- {e['d']:.3f} mm from the edge, at {_where((e['x'], e['y']), kic)}, {e['kind']}{why}")
    if res.get("bands_without_limit"):
        out += ["", "Edge band(s) without copper_to_edge: " + ", ".join(res["bands_without_limit"]) + ": the general limit "
                "applies along them (body_check.py checks exposed copper inside every band)."]
    for n in res["notes"]:
        out += ["", f"{res['outline_file']}: note: {n}."]
    out += ["", f"Result for the {res['which']}: **{res['result']}**", ""]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Copper to board edge, measured on exported Gerber files.",
                                 epilog="Exit codes: 0 pass, 1 findings, 2 could not run.")
    ap.add_argument("--project", help="the board folder (reads board.toml; results go to <project>/out/); measures "
                                      "out/jlc/gerbers and, when the project has a panel, out/panel/jlc/gerbers")
    ap.add_argument("--gerbers", help="a folder of Gerber files (with --out)")
    ap.add_argument("--out", help="results folder (needed without --project)")
    ap.add_argument("--min", type=float, help=f"limit in mm (default {DEFAULT_MIN})")
    ap.add_argument("--outline", help="file name of the board's outline Gerber, when its folder holds several "
                                      "candidates (the panel's is found by itself)")
    ap.add_argument("--name", default="edge_check", help="base name of the result files (default edge_check)")
    a = ap.parse_args(argv)
    job = pcb_common.resolve(a, need_board=False)
    cfg = job.cfg("edge")
    lim = pcb_common.Limits(cfg, {"min": DEFAULT_MIN}, {"min": a.min})
    allow = cfg.get("allow", [])
    for al in allow:
        if not (isinstance(al.get("box"), list) and len(al["box"]) == 4):
            raise kicad_io.KicadIOError("board.toml: every [[edge.allow]] needs box = [x0, y0, x1, y1]")
    runs = []
    if a.gerbers:
        runs.append(("board", os.path.abspath(a.gerbers)))
    elif job.project:
        runs.append(("board", job.path(cfg.get("gerbers", os.path.join(os.path.basename(job.out), "jlc", "gerbers")))))
        # the panel: whenever the project has one ([panel] table or out/panel/), or a folder is named for it
        if cfg.get("panel_gerbers") or isinstance(job.settings.get("panel"), dict) or \
                os.path.isdir(os.path.join(job.out, "panel")):
            runs.append(("panel", job.path(cfg.get("panel_gerbers") or os.path.join(job.out, PANEL_GERBERS))))
    else:
        raise kicad_io.KicadIOError("give --project <board folder>, or --gerbers <folder> with --out <folder>")
    results = []
    for which, folder in runs:
        if which == "board":
            results.append(check_folder(folder, lim["min"], allow, which, a.outline or cfg.get("outline_file"),
                                        lambda box: pcb_common.edge_bands(job, box)))
            continue
        try:                                        # a panel that cannot be measured is CANNOT RUN, never skipped
            results.append(check_folder(folder, lim["min"], allow, which))
        except kicad_io.KicadIOError as e:
            results.append({"folder": folder, "which": which, "result": "CANNOT RUN", "layers": [],
                            "why": f"{e}. Make the panel's Gerbers: {PANEL_HOW}"})
    if any(r["result"] == "FAIL" for r in results):
        overall = "FAIL"
    elif any(r["result"] == "CANNOT RUN" for r in results):
        overall = "CANNOT RUN (" + ", ".join(r["which"] for r in results if r["result"] == "CANNOT RUN") + ")"
    else:
        overall = "PASS" if all(r["result"] == "PASS" for r in results) else "FAIL (UNKNOWN items are not a pass)"
    md = pcb_common.header("Copper to board edge on the exported Gerbers", job, "edge_check.py")
    md += ["Measured on the files that go to the factory, not on the design. " + "Limits:", ""] + lim.table() + [""]
    crops = []
    for r in results:
        if r["result"] == "CANNOT RUN":
            md += [f"## {r['which'].capitalize()}: CANNOT RUN", "", f"Gerber folder `{pcb_common.scrub(r['folder'])}`: "
                   f"{pcb_common.scrub(r['why'])}", "", f"Result for the {r['which']}: **CANNOT RUN** (not measured, "
                   "never a pass)", ""]
            continue
        md += report_lines(r)
        for row in r["layers"]:
            if row["where"]:
                crops.append({"name": f"edge_min_{r['which']}_{os.path.splitext(row['file'])[0]}", "frame": "gerber",
                              "x": round(row["where"][0], 3), "y": round(row["where"][1], 3), "size": 6.0,
                              "why": f"nearest copper to the outline on {row['file']}: {row['min']:.3f} mm"})
            for e in row["under"][:10] + row["outside"][:10]:
                crops.append({"name": f"edge_fail_{r['which']}_{os.path.splitext(row['file'])[0]}_{len(crops)}",
                              "frame": "gerber", "x": e["x"], "y": e["y"], "size": 6.0,
                              "why": f"copper under the limit or outside the board on {row['file']}"})
            for b in row["bands"]:
                for e in sorted(b["under"], key=lambda e: e["d"])[:5]:
                    crops.append({"name": f"edge_band_{len(crops)}", "frame": "gerber", "x": e["x"], "y": e["y"], "size": 8.0,
                                  "why": f"copper {e['d']:.2f} mm from the edge in band '{b['name']}' on {row['file']} "
                                         f"(limit {b['limit']:.2f} mm)"})
    md += ["## Not checked", "",
           "Drill holes, solder mask and silkscreen to the edge; cut-outs given only as drill slots; whether these "
           "Gerbers are the newest export of the board (fab_package.py --check does that).", "",
           f"**{overall}**"]
    data = {"script": "edge_check.py", "result": overall, "limits": lim.to_dict(), "runs": results, "crops": crops}
    p_md, _ = pcb_common.write_result(job.out, a.name, md, data)
    for r in results:
        if r["result"] == "CANNOT RUN":
            print(f"CANNOT RUN  {r['which']}: {pcb_common.scrub(r['why'])}")
            continue
        for row in r["layers"]:
            dtxt = f"{row['min']:.3f} mm" if row["min"] is not None else "far"
            print(f"{row['result']}  {r['which']} {row['file']}: min {dtxt} (limit {lim['min']:.2f}), "
                  f"{len(row['under'])} under, {len(row['outside'])} outside")
            for b in row["bands"]:
                btxt = f"{b['min']:.3f} mm" if b["min"] is not None else "far"
                print(f"{b['result']}  {r['which']} {row['file']}, band '{b['name']}': nearest copper {btxt} "
                      f"(limit {b['limit']:.2f}), {len(b['under'])} under")
        if r["open_contours"] or not r["closed_contours"]:
            print(f"FAIL  {r['which']}: the outline is not closed")
    print(f"{overall}  -> {p_md}")
    return 0 if overall == "PASS" else 2 if overall.startswith("CANNOT RUN") else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
