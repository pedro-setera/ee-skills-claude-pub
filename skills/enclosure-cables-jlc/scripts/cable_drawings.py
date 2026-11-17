"""Cable drawings in the cable supplier's own format: one A4 landscape PDF + PNG per cable and a combined PDF.

What it does
    Reads `cables/cables.json` and draws, per cable, the page a cable factory draws itself:
      - top left the customer part number ("CUST P/N" = the cable id), top right the revision line and "Quantity: N PCS";
      - a schematic of the cable with its ends named P1 / P2 / P3, the wires in their colours, the label on the cable,
        position 1 and the last position marked, numbered balloons that point into the BOM;
      - the ONE length dimension with its tolerance and its definition (and "T = n" for a tinned end);
      - WIRING TABLE: "P1 pos (colour) -> P2 pos, AWG" (signal names only with `[cables] show_signals = true`);
      - a CAVITY TABLE for every housing: every position, EMPTY written in the empty ones;
      - a face picture of every housing with the pin-1 mark and the numbering order (two-row housings numbered as the
        mating header numbers them: `part.numbering_order` = "zigzag" or "rows", plus the words of `part.numbering`);
      - an orientation sketch for angled plugs (`exit` = left / right / up / down, `latch` = up / down);
      - BOM table (role, description, supplier code, quantity); NOTES: each non-default as "X, NOT Y", the label text
        and its place, the pin-1 dot, 100 % continuity test; title block (company from `[project] company`, rev, date).
    Nothing else goes on the page: no clearances, no route text, no questions, no product names.
    The label is drawn where `label_position` says: "<n> mm from P1" (or P2), "<n> % of the length from P1" (or P2), or
    "middle"; empty = 30 % from P1. A single coax (type rf, no wires) has no wiring table: its schematic says "centre to
    centre, shield to shield" and no `<id>_wiring.png` is made for it.
    It also writes, per cable, `pictures/<id>_wiring.png` (faces + wiring table: the picture for a revision note) and
    `pictures/<id>_<end>_pinmap.png` / `_orientation.png` (the files `picture` in cables.json can point to).
    Only fields meant for the supplier are drawn. `note_internal` (on a cable, a part, an end or a terminal: a note for
    yourself, such as "part number from memory, to verify") is never drawn, never printed, never on a form.
    Rows: every text on the page is checked for overlap with another text, for leaving the frame or its table cell,
    for request words and deny-list names (WORDS), and for placeholder text ("TBD", "UNKNOWN", "to verify", "to read":
    PLACEHOLDER, fails, the drawing is still written so that it can be looked at); LABELPOS fails a `label_position`
    that cannot be read. A cable with many wires gets its tables on a second sheet.

Why it exists (the real failure, told without names)
    Drawings in our own layout, with route notes and a question on them, came back from the supplier redrawn with the
    supplier's stock defaults: wires in cavities that had to stay empty, positions renumbered. A page laid out like
    theirs, with a cavity table and "X, NOT Y" notes, leaves nothing to re-interpret. Later, a part note written for
    the designer ("from memory: to verify") was printed on a supplier drawing, three drawings put the label at three
    other places than the one written in the data, and a coax got a wiring picture that was only a heading and white space.

Usage
    python -I cable_drawings.py [--project <mech folder>] [--out <folder>] [--cables cables.json] [--only CAB-01]
                                [--date 2026-01-31] [--dpi 150]
    Outputs in <out>/cables/drawings/: <id>_<name>.pdf, <id>_<name>.png (one PNG per sheet), cables_all.pdf
    Needs matplotlib (and numpy).

Config keys (mech.toml)
    [project] company, rev        [cables] file, show_signals = false, deny = [...], tol_mm
    cables.json: `label_position` (text above), `note_internal` (never drawn)

Exit codes
    0 all rows pass   1 a row failed (text overlap, text out of its cell, a banned word, placeholder text, an unreadable
    label position)   2 could not run
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import datetime
import math
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import cable_common as cc  # noqa: E402

PW, PH, M = 297.0, 210.0, 8.0                 # A4 landscape, frame margin (mm)
RED = "#c81e1e"
INK = "#111111"
MIN_PT = 4.6
COAX_TEXT = "centre to centre, shield to shield"       # drawn in the schematic of a single coax (it has no wiring table)
DEFAULT_LABEL_POSITION = "30 % of the length from P1"   # where the label is drawn (and what the note says) when `label_position` is empty


def colour_of(name: str) -> str:
    n = str(name or "").strip().lower()
    for part in re.split(r"[/ ,-]+", n):
        if part in cc.COLOURS:
            return cc.COLOURS[part]
    return n if re.fullmatch(r"#[0-9a-f]{6}", n) else "#b9b9b9"


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_")


# ---------------------------------------------------------------- a page in millimetres ------------------------------
class Sheet:
    """A matplotlib figure addressed in mm, that remembers every text it draws (for the overlap check)."""

    def __init__(self, w=PW, h=PH, frame=True):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        self.plt = plt
        self.w, self.h = w, h
        self.fig = plt.figure(figsize=(w / 25.4, h / 25.4), dpi=100)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(0, h)
        self.ax.axis("off")
        self.texts: list = []                 # (artist, cell rect or None, tag)
        self.problems: list[str] = []
        self.rend = self.fig.canvas.get_renderer()
        self.frame = frame
        if frame:
            self.rect(M, M, w - 2 * M, h - 2 * M, lw=0.9)

    # -- primitives
    def line(self, x0, y0, x1, y1, lw=0.5, color=INK, **kw):
        self.ax.plot([x0, x1], [y0, y1], color=color, lw=lw, solid_capstyle=kw.pop("cap", "butt"), **kw)

    def rect(self, x, y, w, h, lw=0.5, fc="none", ec=INK, **kw):
        from matplotlib.patches import Rectangle
        self.ax.add_patch(Rectangle((x, y), w, h, fill=fc != "none", fc=fc if fc != "none" else None, ec=ec, lw=lw, **kw))

    def circle(self, x, y, r, fc="none", ec=INK, lw=0.5, **kw):
        from matplotlib.patches import Circle
        self.ax.add_patch(Circle((x, y), r, fill=fc != "none", fc=fc if fc != "none" else None, ec=ec, lw=lw, **kw))

    def arrow(self, x0, y0, x1, y1, color=INK, lw=0.5, both=False):
        self.ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=6,
                         arrowprops=dict(arrowstyle="<|-|>" if both else "-|>", color=color, lw=lw, mutation_scale=7, shrinkA=0, shrinkB=0))

    def _size(self, t):
        bb = t.get_window_extent(self.rend)
        k = 25.4 / self.fig.dpi
        return bb.width * k, bb.height * k

    def text(self, x, y, s, size=7.0, ha="left", va="center", color=INK, max_w=None, cell=None, tag="", weight="normal", rot=0, check=True):
        """Draw a text; with max_w the size shrinks until it fits (never cut). cell = (x, y, w, h) it must stay in."""
        s = str(s)
        t = self.ax.text(x, y, s, fontsize=size, ha=ha, va=va, color=color, fontweight=weight, rotation=rot, zorder=8)
        if max_w is not None:
            while self._size(t)[0] > max_w and size > MIN_PT:
                size -= 0.25
                t.set_fontsize(size)
            if self._size(t)[0] > max_w + 0.05:
                self.problems.append(f"'{s[:40]}' does not fit its {max_w:.0f} mm even at {MIN_PT} pt")
        if check:
            self.texts.append((t, cell, tag or s[:30]))
        return t

    def wrap(self, s, max_w, size):
        """Split a text into lines no wider than max_w at this size."""
        words, lines, cur = [w for w in str(s).split(" ") if w], [], ""
        probe = self.ax.text(0, 0, "", fontsize=size)
        for w in words:
            cand = (cur + " " + w).strip()
            probe.set_text(cand)
            if self._size(probe)[0] <= max_w or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        probe.remove()
        return lines

    def table(self, x, y_top, widths, rows, row_h=4.6, size=6.5, header=True, aligns=None, tag="table", wrap_cols=()):
        """Grid table; a cell is a string, or (text, colour swatch). Columns in wrap_cols wrap onto further lines and
        make their row taller. Returns the bottom y."""
        W = sum(widths)
        pad = 1.0
        step = size * 0.44
        cells, heights = [], []
        for i, row in enumerate(rows):
            line_n, crow = 1, []
            for j, cell in enumerate(row):
                sw = None
                if isinstance(cell, tuple):
                    cell, sw = cell
                lines = [str(cell)]
                if j in wrap_cols and not (header and i == 0):
                    lines = self.wrap(str(cell), widths[j] - 2 * pad, size) or [""]
                line_n = max(line_n, len(lines))
                crow.append((lines, sw))
            cells.append(crow)
            heights.append(max(row_h, line_n * step + 2.0))
        H = sum(heights)
        self.rect(x, y_top - H, W, H, lw=0.7)
        y = y_top
        for hgt in heights[:-1]:
            y -= hgt
            self.line(x, y, x + W, y, lw=0.35)
        cx = x
        for wd in widths[:-1]:
            cx += wd
            self.line(cx, y_top, cx, y_top - H, lw=0.35)
        y = y_top
        for i, crow in enumerate(cells):
            cx = x
            hgt = heights[i]
            yc = y - hgt / 2
            for j, (lines, sw) in enumerate(crow):
                wd = widths[j]
                al = (aligns[j] if aligns else "center")
                avail = wd - 2 * pad
                tx = cx + wd / 2 if al == "center" else cx + pad
                if sw:
                    self.rect(cx + pad, yc - 1.3, 3.2, 2.6, lw=0.35, fc=sw)
                    tx, al, avail = cx + pad + 4.2, "left", wd - 2 * pad - 4.2
                for k, ln in enumerate(lines):
                    yy = yc + (len(lines) - 1) * step / 2 - k * step
                    self.text(tx, yy, ln, size=size, ha=al, max_w=avail, cell=(cx, y - hgt, wd, hgt),
                              tag=f"{tag} r{i + 1}c{j + 1}", weight="bold" if header and i == 0 else "normal")
                cx += wd
            y -= hgt
        return y_top - H

    def balloon(self, x, y, n, to=None):
        if to is not None:
            self.line(x, y, to[0], to[1], lw=0.35, color="#555555")
        self.circle(x, y, 2.1, fc="white", lw=0.5, zorder=7)
        self.text(x, y, str(n), size=6.2, ha="center", tag=f"balloon {n}")

    # -- checks
    def check(self) -> tuple[list[str], list[str]]:
        """(overlaps, out-of-frame or out-of-cell) after everything is drawn."""
        self.fig.canvas.draw()
        rend = self.fig.canvas.get_renderer()
        k = 25.4 / self.fig.dpi
        boxes = []
        for t, cell, tag in self.texts:
            if not t.get_text().strip():
                continue
            bb = t.get_window_extent(rend)
            boxes.append((bb.x0 * k, bb.y0 * k, bb.x1 * k, bb.y1 * k, cell, tag, t.get_text()))
        over, out = [], []
        e = 0.25
        for i in range(len(boxes)):
            a = boxes[i]
            if self.frame and (a[0] < M - 0.2 or a[1] < M - 0.2 or a[2] > self.w - M + 0.2 or a[3] > self.h - M + 0.2):
                out.append(f"'{a[6][:30]}' leaves the frame")
            if a[4]:
                cx, cy, cw, ch = a[4]
                if a[0] < cx - 0.3 or a[2] > cx + cw + 0.3 or a[1] < cy - 0.6 or a[3] > cy + ch + 0.6:
                    out.append(f"'{a[6][:30]}' leaves its cell ({a[5]})")
            for j in range(i + 1, len(boxes)):
                b = boxes[j]
                if min(a[2], b[2]) - max(a[0], b[0]) > e and min(a[3], b[3]) - max(a[1], b[1]) > e:
                    over.append(f"'{a[6][:24]}' over '{b[6][:24]}'")
        return over, out + self.problems

    def all_text(self) -> list[str]:
        return [t.get_text() for t, _c, _g in self.texts]


# ---------------------------------------------------------------- cable facts ---------------------------------------
def bom_lines(c: dict) -> list[dict]:
    """[{no, role, description, code, qty, end}] in the order drawn."""
    out = []
    ws = c.get("wires") or []
    if ws:
        awgs = sorted({int(w["awg"]) for w in ws if isinstance(w.get("awg"), (int, float))})
        cols = list(dict.fromkeys(str(w.get("colour", "")) for w in ws))
        desc = f"{c.get('wire_standard', 'UL1007')} / {'/'.join(str(a) for a in awgs)} AWG ({', '.join(cols)}); L\u00a0=\u00a0{cc.fmt(c.get('length_mm') or 0)}\u00a0mm"
        if c.get("twisted"):
            desc += "; twisted"
        out.append({"role": "WIRE", "description": desc, "code": c.get("wire_code", ""), "qty": f"{len(ws)} PCS", "end": None})
    else:
        out.append({"role": "CABLE", "description": c.get("cable_spec", ""), "code": c.get("cable_code", ""), "qty": "1 PCS", "end": None})
    for e in c.get("ends", []):
        p = e.get("part") or {}
        k = e.get("kind")
        if k == "housing":
            n = len([x for x in cc.wires_at(c, e["id"]) if x is not None])
            d = p.get("description") or f"{p.get('positions', '')}-position housing"
            out.append({"role": f"HOUSING {e['id']}", "description": f"{d} / {p.get('mpn', '')}".strip(" /"), "code": p.get("supplier_code", ""), "qty": "1 PCS", "end": e["id"]})
            t = e.get("terminal") or {}
            if t:
                lo, hi = sorted((t.get("awg_min", 0), t.get("awg_max", 0)))
                out.append({"role": f"TERMINAL {e['id']}", "description": f"crimp terminal {lo:g}-{hi:g} AWG / {t.get('mpn', '')}".strip(" /"),
                            "code": t.get("supplier_code", ""), "qty": f"{n} PCS", "end": e["id"]})
        elif k in ("plug", "jack"):
            d = p.get("description") or k
            out.append({"role": f"CONNECTOR {e['id']}", "description": f"{d} / {p.get('mpn', '')}".strip(" /"), "code": p.get("supplier_code", ""), "qty": "1 PCS", "end": e["id"]})
    for x in c.get("bom_extra") or []:
        out.append({"role": str(x.get("role", "")), "description": str(x.get("description", "")), "code": str(x.get("supplier_code", "")),
                    "qty": f"{x.get('qty', 1)} PCS", "end": None})
    for i, b in enumerate(out, 1):
        b["no"] = i
    return out


def notes_of(c: dict) -> list[str]:
    out = list(cc.non_default_lines(c))
    lab = str(c.get("label", "")).strip()
    if lab:
        out.append(f"Label on the cable, {c.get('label_position') or DEFAULT_LABEL_POSITION}: \"{lab}\".")
    hs = [e["id"] for e in c.get("ends", []) if e.get("kind") == "housing"]
    if hs:
        out.append(f"{', '.join(hs)}: mark position 1 of the housing with a dot.")
    for e in c.get("ends", []):
        num = str((e.get("part") or {}).get("numbering", "")).strip()
        if num:
            out.append(f"{e['id']} numbering: {num}.")
        if str(e.get("orientation", "")).strip():
            out.append(f"{e['id']}: {str(e['orientation']).strip().rstrip('.')}.")
        if e.get("kind") == "tinned" and isinstance(e.get("tin_mm"), (int, float)):
            out.append(f"{e['id']}: wire ends stripped and tinned {cc.fmt(e['tin_mm'])} mm, no terminal.")
    if c.get("twisted") and c.get("wires"):
        out.append("Wires twisted together along the whole length.")
    out += [str(n) for n in (c.get("notes") or [])]
    out.append("100 % continuity test: no open, short or crossed wire.")
    return out


def cavity_rows(c: dict, e: dict) -> list[list]:
    at = cc.wires_at(c, e["id"])
    rows = [[f"{e['id']} pos.", "Wire", "AWG"]]
    for pos in range(1, cc.end_positions(e) + 1):
        ws = at.get(pos) or []
        if ws:
            w = ws[0]
            rows.append([str(pos), (str(w.get("colour", "")), colour_of(w.get("colour"))), f"{w.get('awg', ''):g}" if isinstance(w.get("awg"), (int, float)) else ""])
        else:
            rows.append([str(pos), "EMPTY", ""])
    return rows


def wiring_rows(c: dict, show_signals: bool) -> tuple[list[list], list[float]]:
    ends = [e["id"] for e in c.get("ends", [])]
    head = [f"{ends[0]} pos." if ends else "P1 pos.", "Colour", "To", "AWG"] + (["Signal"] if show_signals else [])
    rows = [head]

    def key(w):
        e, p = cc.split_ref(w.get("from", ""))
        return (e, p if isinstance(p, int) else 0)

    for w in sorted(c.get("wires") or [], key=key):
        fe, fp = cc.split_ref(w.get("from", ""))
        te, tp = cc.split_ref(w.get("to", ""))
        tend = cc.end_of(c, te) or {}
        to = f"{te} pos. {tp}" if tend.get("kind") != "tinned" else f"{te} TIN {tp}"
        r = [f"{fp}" if fe == (ends[0] if ends else "P1") else f"{fe}.{fp}", (str(w.get("colour", "")), colour_of(w.get("colour"))), to,
             f"{w.get('awg'):g}" if isinstance(w.get("awg"), (int, float)) else ""]
        if show_signals:
            r.append(str(w.get("signal", "")))
        rows.append(r)
    widths = [15, 26, 22, 11] + ([20] if show_signals else [])
    return rows, widths


# ---------------------------------------------------------------- drawing pieces ------------------------------------
def face_grid(e: dict) -> list[list[int]]:
    """Positions of a housing face as rows of numbers (top row first)."""
    n, rows = cc.end_positions(e), cc.end_rows(e)
    if rows <= 1:
        return [list(range(1, n + 1))]
    per = int(math.ceil(n / rows))
    order = str((e.get("part") or {}).get("numbering_order", "zigzag")).lower()
    if order.startswith("row"):
        return [list(range(r * per + 1, min((r + 1) * per, n) + 1)) for r in range(rows)]
    return [[p for p in range(r + 1, n + 1, rows)] for r in range(rows)]        # zigzag: 1 3 5 / 2 4 6


def face_size(e: dict, cell=6.0) -> tuple[float, float]:
    g = face_grid(e)
    return max(len(r) for r in g) * cell + 4.0, len(g) * cell + 4.0


def draw_face(sh: Sheet, x: float, y: float, c: dict, e: dict, cell=6.0, title=True) -> None:
    """Housing face with its lower-left corner at (x, y): numbered cavities, wire colours, EMPTY, pin-1 mark, order arrow."""
    g = face_grid(e)
    at = cc.wires_at(c, e["id"])
    w, h = face_size(e, cell)
    sh.rect(x, y, w, h, lw=0.8, fc="#f3f1ea")
    for r, row in enumerate(g):
        for k, pos in enumerate(row):
            cx, cy = x + 2 + k * cell, y + h - 2 - (r + 1) * cell
            ws = at.get(pos)
            sh.rect(cx + 0.4, cy + 0.4, cell - 0.8, cell - 0.8, lw=0.5, fc="white")
            if ws:
                sh.rect(cx + 0.4, cy + 0.4, cell - 0.8, (cell - 0.8) * 0.3, lw=0.3, fc=colour_of(ws[0].get("colour")))
                sh.text(cx + cell / 2, cy + cell * 0.62, str(pos), size=min(7.0, cell * 1.05), ha="center", tag=f"{e['id']} face {pos}", weight="bold")
            else:
                sh.rect(cx + 0.4, cy + 0.4, cell - 0.8, cell - 0.8, lw=0.5, fc="#d9d9d9", hatch="////", ec="#8a8a8a")
                sh.rect(cx + 0.4, cy + 0.4, cell - 0.8, cell - 0.8, lw=0.5)
                sh.text(cx + cell / 2, cy + cell * 0.68, str(pos), size=min(5.6, cell * 0.8), ha="center", tag=f"{e['id']} face {pos}", color=INK)
                t_ = sh.text(cx + cell / 2, cy + cell * 0.27, "EMPTY", size=min(4.6, cell * 0.56), ha="center", tag=f"{e['id']} face {pos} EMPTY", color=INK,
                             weight="bold", max_w=cell - 1.0)
                t_.set_bbox(dict(facecolor="#f2f2f2", edgecolor="none", pad=0.4))
    # pin-1 mark: a dot outside the housing at cavity 1 (top-left cavity is position 1 in this view)
    sh.circle(x + 2 + cell / 2, y + h + 1.6, 1.0, fc=INK)
    sh.text(x + 2 + cell + 0.6, y + h + 1.6, "pin-1 mark", size=5.2, ha="left", tag=f"{e['id']} pin-1 mark")
    if title:
        rows = cc.end_rows(e)
        order = "" if rows <= 1 else (" (1-2 across the rows)" if not str((e.get("part") or {}).get("numbering_order", "zigzag")).lower().startswith("row")
                                      else " (1..n along one row)")
        sh.text(x, y - 2.4, f"{e['id']} face, {cc.end_positions(e)} positions{order}", size=5.6, tag=f"{e['id']} face title", max_w=max(w, 44))
    # numbering order arrow under the first row
    if max(len(r) for r in g) > 1:
        yy = y + h + 4.6
        sh.arrow(x + 2 + cell * 0.2, yy, x + 2 + min(len(g[0]), 4) * cell - cell * 0.2, yy, lw=0.5)


def draw_orientation(sh: Sheet, x: float, y: float, e: dict, size=24.0) -> None:
    """Sketch of an angled plug seen on its mating face: latch side and the way the cable leaves."""
    exit_ = str(e.get("exit", "right")).lower()
    latch = str(e.get("latch", "up")).lower()
    bx, by, bw, bh = x + size * 0.3, y + size * 0.3, size * 0.4, size * 0.4
    sh.rect(bx, by, bw, bh, lw=0.8, fc="#e9eef5")
    ly = by + bh if latch != "down" else by - 1.6
    sh.rect(bx + bw * 0.3, ly, bw * 0.4, 1.6, lw=0.6, fc="#c9d3df")
    vec = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}.get(exit_, (1, 0))
    cx, cy = bx + bw / 2, by + bh / 2
    x0, y0 = cx + vec[0] * bw / 2, cy + vec[1] * bh / 2
    x1, y1 = cx + vec[0] * size * 0.52, cy + vec[1] * size * 0.52
    sh.line(x0, y0, x1, y1, lw=2.6, color="#3b3b3b", cap="round")
    sh.arrow(x1, y1, x1 + vec[0] * 3.0, y1 + vec[1] * 3.0, lw=0.8, color=RED)
    sh.text(x, y - 2.4, f"{e['id']} seen on the mating face: cable leaves {exit_.upper()}, latch {'DOWN' if latch == 'down' else 'UP'}",
            size=5.6, tag=f"{e['id']} orientation", max_w=64)
    sh.text(cx, cy, e["id"], size=6.5, ha="center", tag=f"{e['id']} orientation id", weight="bold")


def _wire(sh: Sheet, pts, col, lw=2.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    sh.ax.plot(xs, ys, color="#1a1a1a", lw=lw + 0.9, solid_capstyle="round", solid_joinstyle="round", zorder=3)
    sh.ax.plot(xs, ys, color=col, lw=lw, solid_capstyle="round", solid_joinstyle="round", zorder=4)


def draw_schematic(sh: Sheet, c: dict, boms: list[dict], x0=30.0, x1=160.0, yc=148.0) -> None:
    ends = c.get("ends", [])
    wires = c.get("wires") or []
    L, tol = c.get("length_mm"), c.get("tol_mm")
    slot = {}                                             # (end id, pos) -> y
    exit_x = {}
    places = {}
    for i, e in enumerate(ends[:3]):
        left = i == 0
        ex = x0 if left else x1
        ey = yc if i < 2 else yc - 34.0
        if i == 1 and len(ends) > 2:
            ey = yc + 6.0
        n = max(cc.end_positions(e), len(cc.wires_at(c, e["id"])), 1)
        rows = cc.end_rows(e)
        per = int(math.ceil(n / rows))
        pitch = min(4.2, 30.0 / max(per, 1))
        hh = per * pitch
        places[e["id"]] = (ex, ey, hh, left)
        k = e.get("kind")
        sx = 1 if left else -1                            # direction from the connector body toward the cable
        if k == "housing":
            bw = 8.0 * rows
            bx = ex - bw if left else ex
            sh.rect(bx, ey - hh / 2 - 0.8, bw, hh + 1.6, lw=0.8, fc="#f3f1ea", zorder=5)
            for p in range(1, n + 1):
                r, q = (p - 1) % rows, (p - 1) // rows
                if rows > 1 and str((e.get("part") or {}).get("numbering_order", "zigzag")).lower().startswith("row"):
                    r, q = (p - 1) // per, (p - 1) % per
                y = ey + hh / 2 - (q + 0.5) * pitch + (0.0 if rows == 1 else (0.22 - 0.44 * r) * pitch)
                slot[(e["id"], p)] = y
            for q in range(1, per):
                sh.line(bx, ey + hh / 2 - q * pitch, bx + bw, ey + hh / 2 - q * pitch, lw=0.3, color="#777777", zorder=6)
            tx = bx - 2.2 if left else bx + bw + 2.2
            sh.circle(bx + (1.6 if left else bw - 1.6), ey + hh / 2 - 0.5 * pitch, 0.8, fc=INK, zorder=7)
            sh.text(tx, ey + hh / 2 - 0.5 * pitch, "1", size=6.5, ha="right" if left else "left", tag=f"{e['id']} first")
            if per > 1:
                sh.text(tx, ey - hh / 2 + 0.5 * pitch, str(n if rows == 1 else f"{n - rows + 1}-{n}"), size=6.5, ha="right" if left else "left", tag=f"{e['id']} last")
            exit_x[e["id"]] = ex
            name_x = bx - 9.0 if left else bx + bw + 9.0
        elif k == "tinned":
            ps = sorted(p for p in cc.wires_at(c, e["id"]) if isinstance(p, int)) or [1]
            pitch = 4.0
            for j, p in enumerate(ps):
                slot[(e["id"], p)] = ey + (len(ps) - 1) * pitch / 2 - j * pitch
            exit_x[e["id"]] = ex
            name_x = ex - 10.0 if left else ex + 10.0
        else:                                             # plug / jack
            bw, bh = 15.0, 8.0
            bx = ex - bw if left else ex
            sh.rect(bx, ey - bh / 2, bw, bh, lw=0.8, fc="#d9d2b8", zorder=5)
            if c.get("type") == "rf":                      # a coupling nut; other plugs are a plain body
                nut = bx + (bw * 0.15 if left else bw * 0.55)
                sh.rect(nut, ey - bh / 2 - 1.2, bw * 0.3, bh + 2.4, lw=0.7, fc="#c9c19f", zorder=5)
            slot[(e["id"], 1)] = ey
            exit_x[e["id"]] = ex
            name_x = bx - 9.0 if left else bx + bw + 9.0
            sh.text(bx + bw / 2, ey - bh / 2 - 4.0, (e.get("part") or {}).get("short", k.upper()), size=5.6, ha="center", tag=f"{e['id']} kind", max_w=30)
        sh.text(name_x, ey, e["id"], size=13, ha="center", tag=f"end name {e['id']}", weight="bold")
        _ = sx
    # wires or the cable
    first, second = (ends[0]["id"] if ends else "P1"), (ends[1]["id"] if len(ends) > 1 else "P2")
    if wires:
        tw = bool(c.get("twisted"))
        for w in wires:
            fe, fp = cc.split_ref(w.get("from", ""))
            te, tp = cc.split_ref(w.get("to", ""))
            if (fe, fp) not in slot or (te, tp) not in slot:
                continue
            xa, ya, xb, yb = exit_x[fe], slot[(fe, fp)], exit_x[te], slot[(te, tp)]
            if xa > xb:
                xa, ya, xb, yb, fe, te = xb, yb, xa, ya, te, fe
            col = colour_of(w.get("colour"))
            stub = 14.0
            tend = cc.end_of(c, te) or {}
            fend = cc.end_of(c, fe) or {}
            xe = xb - (5.0 if tend.get("kind") == "tinned" else 0.0)
            xs = xa + (5.0 if fend.get("kind") == "tinned" else 0.0)
            if tw and len(wires) > 1:
                import numpy as np
                idx = wires.index(w)
                xx = np.linspace(xs + stub, xe - stub, 160)
                ym = (ya + yb) / 2
                amp = 1.6
                yy = ym + amp * np.sin((xx - xx[0]) / 4.2 + idx * math.pi)
                pts = [(xs, ya), (xs + stub * 0.5, ya)] + list(zip(xx, yy)) + [(xe - stub * 0.5, yb), (xe, yb)]
            else:
                pts = [(xs, ya), (xs + stub, ya), (xe - stub, yb), (xe, yb)]
            _wire(sh, pts, col)
            for end_, xt, yt, sgn in ((fend, xa, ya, 1), (tend, xb, yb, -1)):
                if end_.get("kind") == "tinned":
                    sh.ax.plot([xt, xt + sgn * 5.0], [yt, yt], color="#b8b8b8", lw=1.5, zorder=4, solid_capstyle="butt")
                    sh.ax.plot([xt, xt + sgn * 5.0], [yt, yt], color="#555555", lw=0.3, zorder=5)
    else:
        ya, yb = slot.get((first, 1), yc), slot.get((second, 1), yc)
        col = colour_of(c.get("colour", "grey"))
        _wire(sh, [(exit_x.get(first, x0), ya), (exit_x.get(first, x0) + 16, ya), (exit_x.get(second, x1) - 16, yb), (exit_x.get(second, x1), yb)], col, lw=3.4)
        if c.get("type") == "rf":                         # a single coax: nothing to wire, so say how it is connected
            sh.text((exit_x.get(first, x0) + exit_x.get(second, x1)) / 2, (ya + yb) / 2 + 5.0, COAX_TEXT, size=6.4, ha="center", tag="coax connection")
    # tinned ends: the T dimension
    for e in ends[:3]:
        if e.get("kind") == "tinned" and e["id"] in places and isinstance(e.get("tin_mm"), (int, float)):
            ex, ey, hh, left = places[e["id"]]
            ys = [y for (i, _p), y in slot.items() if i == e["id"]]
            yb = min(ys) - 4.0
            xa, xb = (ex, ex + 5.0) if left else (ex - 5.0, ex)
            sh.line(xa, yb + 2.5, xa, yb - 1.0, lw=0.3, color=RED)
            sh.line(xb, yb + 2.5, xb, yb - 1.0, lw=0.3, color=RED)
            sh.arrow(xa, yb, xb, yb, color=RED, lw=0.4, both=True)
            sh.text((xa + xb) / 2, yb - 2.6, f"T = {cc.fmt(e['tin_mm'])} TINNED", size=5.8, ha="center", color=RED, tag=f"{e['id']} tin")
    # label on the cable
    lab = str(c.get("label", "")).strip()
    if lab and len(ends) >= 2:
        # where `label_position` says ("15 mm from P2", "30 % of the length from P1", "middle"); an empty value draws it 30 % from P1 and
        # an unreadable one the same way, for looking (the LABELPOS row of the run fails it)
        lend, frac, _why = cc.label_position(c)
        if lend is None:
            lend, frac = first, 0.30
        near, far = (first, second) if lend != second else (second, first)
        xn, xf = exit_x.get(near, x0 if near == first else x1), exit_x.get(far, x1 if near == first else x0)
        lx = xn + (xf - xn) * frac
        ys1 = [y for (i, _p), y in slot.items() if i == near] or [yc]
        ys2 = [y for (i, _p), y in slot.items() if i == far] or [yc]
        ly = (sum(ys1) / len(ys1)) * (1.0 - frac) + (sum(ys2) / len(ys2)) * frac
        t = sh.text(lx, ly, lab, size=6.4, ha="center", tag="label on the cable", max_w=40)
        tw_, th_ = sh._size(t)
        sh.rect(lx - tw_ / 2 - 1.6, ly - th_ / 2 - 1.2, tw_ + 3.2, th_ + 2.4, lw=0.6, fc="white", zorder=7)
    # the ONE length dimension
    if len(ends) >= 2 and isinstance(L, (int, float)):
        tops = [places[e["id"]][1] + places[e["id"]][2] / 2 for e in ends[:2]]
        yd = max(tops) + 12.0
        xa, xb = exit_x.get(first, x0), exit_x.get(second, x1)
        sh.line(xa, yd + 2.0, xa, max(tops[0], yc) + 1.5, lw=0.3, color=RED)
        sh.line(xb, yd + 2.0, xb, max(tops[1], yc) + 1.5, lw=0.3, color=RED)
        sh.arrow(xa, yd, xb, yd, color=RED, lw=0.5, both=True)
        sh.text((xa + xb) / 2, yd + 3.2, f"L = {cc.fmt(L)} \u00b1 {cc.fmt(tol) if isinstance(tol, (int, float)) else ''} mm", size=10, ha="center", color=RED,
                tag="length dimension", weight="bold")
        sh.text((xa + xb) / 2, yd - 2.6, f"L: {c.get('length_def', '')}", size=6.0, ha="center", color=RED, tag="length definition", max_w=xb - xa - 4)
    # branch length (third end)
    if len(ends) > 2 and isinstance(ends[2].get("branch_length_mm"), (int, float)):
        ex, ey, hh, _left = places[ends[2]["id"]]
        xa = exit_x.get(first, x0)
        yd = ey - hh / 2 - 7.0
        sh.line(xa, yd - 2.0, xa, yc - 16.0, lw=0.3, color=RED)
        sh.line(ex, yd - 2.0, ex, ey - hh / 2 - 1.5, lw=0.3, color=RED)
        sh.arrow(xa, yd, ex, yd, color=RED, lw=0.5, both=True)
        sh.text((xa + ex) / 2, yd - 3.0, f"L2 = {cc.fmt(ends[2]['branch_length_mm'])} \u00b1 {cc.fmt(tol) if isinstance(tol, (int, float)) else ''} mm ({first} to {ends[2]['id']})",
                size=7.5, ha="center", color=RED, tag="branch length", weight="bold")
    # balloons
    bx = {}
    for b in boms:
        key = b["end"] or "cable"
        bx.setdefault(key, []).append(b["no"])
    for key, nos in bx.items():
        if key == "cable":
            px = (exit_x.get(first, x0) + exit_x.get(second, x1)) * 0.56
            ys1 = [y for (i, _p), y in slot.items() if i == second] or [yc]
            ys0 = [y for (i, _p), y in slot.items() if i == first] or [yc]
            target = (px, min(min(ys1), min(ys0)) + 1.0)
            base = (px + 8.0, target[1] - 13.0)
        else:
            ex, ey, hh, left = places[key]
            target = (ex + (-3.0 if left else 3.0), ey - hh / 2 - 0.8)
            base = (ex + (-2.0 if left else 2.0) - (len(nos) - 1) * 2.4, ey - hh / 2 - 12.0)
            if cc.end_of(c, key).get("kind") in ("plug", "jack"):      # above the body: the kind text sits below it
                target = (ex + (-9.0 if left else 9.0), ey + 5.2)
                base = (ex + (-11.0 if left else 11.0) - (len(nos) - 1) * 2.4, ey + 13.0)
        for j, n in enumerate(nos):
            sh.balloon(base[0] + j * 4.8, base[1], n, to=target if j == 0 else None)


def title_block(sh: Sheet, c: dict, company: str, rev: str, date: str, sheet_no: int, sheet_n: int, std_tol) -> None:
    x, y, w, h = PW - M - 92.0, M, 92.0, 40.0
    sh.rect(x, y, w, h, lw=0.9)
    for yy in (y + 8, y + 16, y + 24, y + 32):
        sh.line(x, yy, x + w, yy, lw=0.4)
    sh.line(x + 24, y, x + 24, y + 32, lw=0.4)
    sh.line(x + 58, y, x + 58, y + 16, lw=0.4)
    sh.line(x + 72, y, x + 72, y + 16, lw=0.4)
    sh.text(x + w / 2, y + 36, company or "", size=9.5, ha="center", weight="bold", max_w=w - 4, cell=(x, y + 32, w, 8), tag="company")
    lab = dict(size=5.6, color="#444444")
    sh.text(x + 1.2, y + 28, "ITEM", **lab, tag="tb item")
    sh.text(x + 26, y + 28, c.get("name", ""), size=8.5, max_w=w - 28, cell=(x + 24, y + 24, w - 24, 8), tag="tb name", weight="bold")
    sh.text(x + 1.2, y + 20, "CUST P/N", **lab, tag="tb custpn")
    sh.text(x + 26, y + 20, c.get("id", ""), size=8.5, max_w=w - 28, cell=(x + 24, y + 16, w - 24, 8), tag="tb id", weight="bold")
    sh.text(x + 1.2, y + 12, "QUANTITY", **lab, tag="tb qty l")
    sh.text(x + 26, y + 12, f"{c.get('qty', '')} PCS", size=7.5, max_w=30, cell=(x + 24, y + 8, 34, 8), tag="tb qty")
    sh.text(x + 59.2, y + 12, "REV", **lab, tag="tb rev l")
    sh.text(x + 82, y + 12, str(c.get("rev") or rev or "A"), size=8, ha="center", max_w=18, cell=(x + 72, y + 8, 20, 8), tag="tb rev")
    sh.text(x + 1.2, y + 4, "UNIT / SHEET", **lab, tag="tb unit l")
    sh.text(x + 26, y + 4, f"mm    {sheet_no} OF {sheet_n}", size=7.5, max_w=30, cell=(x + 24, y, 34, 8), tag="tb unit")
    sh.text(x + 59.2, y + 4, "DATE", **lab, tag="tb date l")
    sh.text(x + 82, y + 4, date, size=6.6, ha="center", max_w=18.5, cell=(x + 72, y, 20, 8), tag="tb date")


def head(sh: Sheet, c: dict, rev: str, date: str) -> None:
    sh.rect(M, PH - M - 14, 74, 14, lw=0.9)
    sh.text(M + 2, PH - M - 3.4, "CUST P/N", size=5.6, color="#444444", tag="head custpn l")
    sh.text(M + 37, PH - M - 8.6, c.get("id", ""), size=15, ha="center", weight="bold", max_w=70, tag="head custpn")
    x = PW - M - 122
    sh.table(x, PH - M, [14, 66, 24, 18], [["REV", "DESCRIPTION", "DATE", "QTY"],
                                           [str(c.get("rev") or rev or "A"), c.get("name", ""), date, str(c.get("qty", ""))]],
             row_h=6.0, size=7.0, tag="rev table")
    sh.text(PW - M - 3, PH - M - 18.5, f"Quantity: {c.get('qty', '')} PCS", size=11, ha="right", tag="quantity")


def draw_bom(sh: Sheet, boms: list[dict]) -> float:
    rows = [["No.", "Name", "Qty", "Description", "Supplier code"]] + [[str(b["no"]), b["role"], b["qty"], b["description"], b["code"]] for b in boms]
    widths = [8, 26, 13, 60, 21]
    size, rh = 6.2, (4.8 if len(rows) <= 8 else 4.0)
    # measure first (the table is drawn from its top down and must stand on the frame)
    step = size * 0.44
    H = 0.0
    for i, r in enumerate(rows):
        n = 1 if i == 0 else max(1, len(sh.wrap(r[3], widths[3] - 2.0, size)))
        H += max(rh, n * step + 2.0)
    top = M + H
    sh.table(M, top, widths, rows, row_h=rh, size=size, aligns=["center", "left", "center", "left", "center"], tag="BOM", wrap_cols=(3,))
    return top


def draw_notes(sh: Sheet, notes: list[str], x: float, y_top: float, w: float, y_min: float) -> None:
    sh.text(x, y_top, "NOTES", size=7.5, weight="bold", tag="notes title")
    size = 6.6
    while True:
        lines = []
        for i, n in enumerate(notes, 1):
            ls = sh.wrap(n, w - 5.0, size)
            lines.append((f"{i}.", ls))
        step = size * 0.46
        need = sum(len(ls) for _n, ls in lines) * step + len(lines) * 0.9
        if need <= (y_top - 3.6 - y_min) or size <= MIN_PT:
            break
        size -= 0.3
    if need > (y_top - 3.6 - y_min) + 0.1:
        sh.problems.append(f"the NOTES need {need:.0f} mm and have {y_top - 3.6 - y_min:.0f} mm")
    y = y_top - 4.4
    for num, ls in lines:
        nd = num == "0."
        sh.text(x, y, num, size=size, tag=f"note {num}")
        for ln in ls:
            sh.text(x + 5.0, y, ln, size=size, tag=f"note {num} line", color=INK if not nd else INK)
            y -= step
        y -= 0.9


def flow_tables(sh: Sheet, tables: list, x: float, y_top: float, y_min: float, col_w: float, x_max: float, row_h: float, size: float) -> bool:
    """Draw titled tables top to bottom, wrapping into further columns. tables: [(title, rows, widths)]. False when
    they do not fit."""
    y = y_top
    for title, rows, widths in tables:
        k = col_w / sum(widths)
        widths = [v * k for v in widths]
        i = 1
        first = True
        while i < len(rows) or first:
            room = int((y - 5.0 - y_min) / row_h) - 1
            full = int((y_top - 5.0 - y_min) / row_h) - 1
            left = len(rows) - i
            if room < 2 or (first and y < y_top - 0.1 and room < left <= full):      # a table that fits a fresh column is not split
                x += col_w + 5.0
                y = y_top
                if x + col_w > x_max + 0.1:
                    return False
                continue
            part = rows[i:i + room]
            sh.text(x, y - 1.8, title + ("" if first else " (continued)"), size=6.6, weight="bold", tag=f"title {title}", max_w=col_w)
            y = sh.table(x, y - 4.2, widths, [rows[0]] + part, row_h=row_h, size=size, tag=title) - 3.0
            i += len(part)
            first = False
    return True


# ---------------------------------------------------------------- one cable -----------------------------------------
def draw_cable(c: dict, company: str, rev: str, date: str, show_signals: bool, std_tol) -> list[Sheet]:
    boms = bom_lines(c)
    housings = [e for e in c.get("ends", []) if e.get("kind") == "housing" and cc.end_positions(e) > 0]
    angled = [e for e in c.get("ends", []) if _is_angled(e)]
    wrows, wwidths = wiring_rows(c, show_signals)
    tables = []
    if len(wrows) > 1:
        tables.append(("WIRING TABLE", wrows, wwidths))
    for e in housings:
        tables.append((f"CAVITY TABLE {e['id']} ({cc.end_positions(e)} positions)", cavity_rows(c, e), [16, 30, 12]))
    n_rows = sum(len(r) + 2 for _t, r, _w in tables)
    two = n_rows > 26
    sheets = []
    sh = Sheet()
    sheets.append(sh)
    head(sh, c, rev, date)
    title_block(sh, c, company, rev, date, 1, 2 if two else 1, std_tol)
    draw_schematic(sh, c, boms, x0=42.0, x1=(152.0 if not two else 205.0), yc=152.0)
    bom_top = draw_bom(sh, boms)
    draw_notes(sh, notes_of(c), M + 131.0, M + 56.0, 55.0, M + 1.0)
    # faces and orientation sketches, left to right under the schematic
    fx, fy = M + 4.0, max(bom_top + 12.0, 76.0)          # above the NOTES block, under the schematic
    band_top = 104.0
    for e in housings:
        cell = 8.0
        w, h = face_size(e, cell)
        lim = (PW - 2 * M - 100.0) if not two else (PW - 2 * M - 8)
        if w > lim:
            cell = max(2.6, (lim - 4.0) / max(len(r) for r in face_grid(e)))
            w, h = face_size(e, cell)
        if fx + max(w, 46) > (PW - M - 100.0 if not two else PW - M) or fy + h + 8 > band_top + 4:
            sh.problems.append(f"the face of {e['id']} does not fit under the schematic")
            continue
        draw_face(sh, fx, fy, c, e, cell)
        fx += max(w, 46) + 8.0
    for e in angled:
        if fx + 64 > (PW - M - 100.0 if not two else PW - M):
            sh.problems.append(f"the orientation sketch of {e['id']} does not fit under the schematic")
            continue
        draw_orientation(sh, fx, fy, e)
        fx += 70.0
    if not two:
        ok = flow_tables(sh, tables, PW - M - 94.0, PH - M - 26.0, M + 43.0, 92.0, PW - M - 2.0, 4.3 if n_rows <= 22 else 3.7, 6.2)
        if not ok:
            sh.problems.append("the tables do not fit on the sheet")
    else:
        s2 = Sheet()
        sheets.append(s2)
        head(s2, c, rev, date)
        title_block(s2, c, company, rev, date, 2, 2, std_tol)
        ok = flow_tables(s2, tables, M + 4.0, PH - M - 26.0, M + 44.0, 78.0, PW - M - 4.0, 3.9, 6.0)
        if not ok:
            s2.problems.append("the tables do not fit on sheet 2")
    return sheets


def _is_angled(e: dict) -> bool:
    import cable_check
    return cable_check.is_angled(e)


def wiring_picture(c: dict, show_signals: bool, path: str, dpi: int) -> None:
    """Faces of every housing + the wiring table on one small picture (for a revision note)."""
    housings = [e for e in c.get("ends", []) if e.get("kind") == "housing" and cc.end_positions(e) > 0]
    wrows, wwidths = wiring_rows(c, show_signals)
    fw = sum(max(face_size(e)[0], 46) + 8 for e in housings)
    W = max(fw + 8, sum(wwidths) + 12, 90)
    H = 14 + (max([face_size(e)[1] for e in housings] + [0]) + 16 if housings else 0) + len(wrows) * 4.6 + 8
    sh = Sheet(W, H, frame=False)
    sh.rect(0, 0, W, H, lw=0, fc="white", ec="none", zorder=0)
    sh.text(4, H - 6, f"{c.get('id', '')}: positions and wiring", size=9, weight="bold", check=False)
    y = H - 14
    if housings:
        x = 4.0
        hmax = max(face_size(e)[1] for e in housings)
        for e in housings:
            draw_face(sh, x, y - hmax - 8, c, e)
            x += max(face_size(e)[0], 46) + 8
        y -= hmax + 16
    if len(wrows) > 1:
        sh.table(4, y, wwidths, wrows, row_h=4.6, size=6.5, tag="wiring")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sh.fig.savefig(path, dpi=dpi, metadata={"Software": ""})
    sh.plt.close(sh.fig)


def single_picture(c: dict, e: dict, kind: str, path: str, dpi: int) -> None:
    if kind == "pinmap":
        w, h = face_size(e)
        sh = Sheet(max(w, 50) + 10, h + 20, frame=False)
        sh.rect(0, 0, sh.w, sh.h, lw=0, fc="white", ec="none", zorder=0)
        draw_face(sh, 5, 7, c, e)
    else:
        sh = Sheet(74, 40, frame=False)
        sh.rect(0, 0, sh.w, sh.h, lw=0, fc="white", ec="none", zorder=0)
        draw_orientation(sh, 5, 7, e)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sh.fig.savefig(path, dpi=dpi, metadata={"Software": ""})
    sh.plt.close(sh.fig)


def run(job, a) -> tuple[mc.Rows, list, list]:
    try:
        import matplotlib  # noqa: F401
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError:
        raise mc.MechError("the Python library 'matplotlib' is missing")
    data, cpath = cc.load_cables(job, a.cables)
    cfg = cc.cable_cfg(job)
    company = str(job.cfg["project"].get("company", "") or "")
    rev = str(data.get("rev") or job.cfg["project"].get("rev", "A"))
    date = a.date or datetime.date.today().isoformat()
    deny = list(cfg.get("deny") or []) + ([job.cfg["project"]["name"]] if str(job.cfg["project"].get("name", "")).strip() else [])
    out = os.path.join(job.out, "cables", "drawings")
    pics = os.path.join(job.out, "cables", "pictures")
    os.makedirs(out, exist_ok=True)
    rows = mc.Rows()
    made = []
    meta = {"Title": "cable drawings", "Author": "", "Creator": "", "Producer": "", "CreationDate": None, "ModDate": None}
    all_pdf = PdfPages(os.path.join(out, "cables_all.pdf"), metadata=meta)
    n_all = 0
    for c in data["cables"]:
        cid = str(c.get("id", ""))
        if a.only and cid != a.only:
            continue
        sec = f"cable {cid}"
        try:
            sheets = draw_cable(c, company, rev, date, bool(cfg["show_signals"]), None)
        except Exception as e:
            rows.add(f"{cid}-DRAW", sec, "drawing", f"not drawn: {type(e).__name__}: {e}", "one page per cable", "fail")
            continue
        base = os.path.join(out, f"{cid}_{slug(c.get('name', ''))}".rstrip("_"))
        over, outside, words, holders = [], [], [], []
        with PdfPages(base + ".pdf", metadata=dict(meta, Title=cid)) as pdf:
            for k, sh in enumerate(sheets, 1):
                o, x = sh.check()
                over += o
                outside += x
                for s in sh.all_text():
                    for f in cc.text_findings(s, deny):
                        words.append(f"'{s[:30]}': {f}")
                    ph = cc.placeholder_in(s)
                    if ph:
                        holders.append(f"'{s[:40]}': placeholder '{ph}'")
                pdf.savefig(sh.fig)
                all_pdf.savefig(sh.fig)
                n_all += 1
                png = base + (".png" if len(sheets) == 1 else f"_sheet{k}.png")
                sh.fig.savefig(png, dpi=a.dpi, metadata={"Software": ""})
                made.append(png)
                sh.plt.close(sh.fig)
        made.append(base + ".pdf")
        rows.add(f"{cid}-DRAW", sec, "drawing", f"{len(sheets)} sheet(s): {os.path.basename(base)}.pdf", "one drawing per cable in the supplier's layout", "pass")
        rows.add(f"{cid}-OVERLAP", sec, "texts do not overlap", "; ".join(over[:8]) or "none overlap", "no text over another text", "fail" if over else "pass")
        rows.add(f"{cid}-FIT", sec, "texts stay in the frame and in their cells", "; ".join(outside[:8]) or "all inside", "nothing cut, nothing outside", "fail" if outside else "pass")
        rows.add(f"{cid}-WORDS", sec, "words on the drawing", "; ".join(dict.fromkeys(words)) or "clean",
                 "no question, request word, alternative or deny-list name on a drawing", "fail" if words else "pass")
        rows.add(f"{cid}-PLACEHOLDER", sec, "no placeholder text on the drawing", "; ".join(list(dict.fromkeys(holders))[:8]) or "none",
                 "no TBD, UNKNOWN, 'to verify' or 'to read' in any printed text; a note for yourself goes in note_internal (never drawn)",
                 "fail" if holders else "pass")
        lab, lpos = str(c.get("label", "") or "").strip(), str(c.get("label_position", "") or "").strip()
        if lab and lpos:
            lend, frac, why = cc.label_position(c)
            if lend is None:
                rows.add(f"{cid}-LABELPOS", sec, "label drawn where label_position says", why,
                         "'<n> mm from P1|P2', '<n> % of the length from P1|P2' or 'middle'", "fail")
            else:
                rows.add(f"{cid}-LABELPOS", sec, "label drawn where label_position says", f"'{lpos}': drawn {frac * 100:.0f} % of the length from {lend}",
                         "'<n> mm from P1|P2', '<n> % of the length from P1|P2' or 'middle'", "pass")
        wpic = os.path.join(pics, f"{cid}_wiring.png")
        if any(e.get("kind") == "housing" and cc.end_positions(e) > 0 for e in c.get("ends", [])) or c.get("wires"):
            wiring_picture(c, bool(cfg["show_signals"]), wpic, a.dpi)
            made.append(wpic)
        elif os.path.isfile(wpic):
            os.remove(wpic)                                    # nothing to show (a single coax): no picture, and no old one left behind
        for e in c.get("ends", []):
            if e.get("kind") == "housing" and cc.end_positions(e) > 0:
                p = os.path.join(pics, f"{cid}_{e['id']}_pinmap.png")
                single_picture(c, e, "pinmap", p, a.dpi)
                made.append(p)
            if _is_angled(e):
                p = os.path.join(pics, f"{cid}_{e['id']}_orientation.png")
                single_picture(c, e, "orientation", p, a.dpi)
                made.append(p)
    all_pdf.close()
    if n_all == 0:
        os.remove(os.path.join(out, "cables_all.pdf"))
    else:
        made.append(os.path.join(out, "cables_all.pdf"))
    return rows, [cpath], made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cable drawings in the supplier's format.", epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--cables", help="the cable data file")
    ap.add_argument("--only", help="one cable id")
    ap.add_argument("--date", help="date printed on the drawings (default today)")
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
        rows, inputs, made = run(job, a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(job.out, "cable_drawings.py", inputs)
    for p in made:
        print("  wrote", p)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
