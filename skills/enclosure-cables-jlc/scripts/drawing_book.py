"""Drawing book: the features file of a sheet-metal part -> one fully dimensioned multi-page PDF per part.

What it does
    From <out>/drawings/<part>.features.json (sheet_features.py) it prints <out>/drawings/<part>.pdf, A3 landscape:
      1. a general sheet: the part's data, the bend table (radius, angle, length, the panels joined), the hardware
         table, the general tolerances and the notes from mech.toml, the list of sheets;
      2. one sheet per panel: the view as seen, the datum corner, an ID at every hole, slot and cut-out, and
         tables with X and Y from the datum for EVERY one of them, the outline as a node table (corners with
         their radius, arcs), a table per hole pattern (every row: its Y, first X, last X, count); outline
         nodes that crowd each other (relief notches, small steps) are labelled in enlarged DETAIL views;
      3. the flat pattern, marked "reference only" with its K factor;
      4. optionally the silkscreen positions (from silk_dxf.py's <part>_silk.json): every printed element with
         its ink (the chart name), its box and its place from the face datum.
    Every number printed goes into <out>/drawings/drawing_manifest.json (the number as printed, 2 decimals), so
    drawing_vs_step.py can rebuild each feature from the drawing alone. Every sheet is checked for overlapping
    text, and every page is also written as a PNG (<out>/drawings/pages/) so that someone LOOKS at it.
    Notes, finish and material lines are printed exactly as written in mech.toml: the script adds no colour, finish
    or process word of its own.

Why it exists (the real failure, told without names)
    Drawings with missing dimensions cost a full extra round before a quote: a part whose outline had angled
    edges left three sizes undefined, and holes had no position from any edge. A supplier's engineer then has to
    ask, and each question costs a working day in another time zone. A drawing book printed from the exported
    STEP, with a table row for every feature, got zero geometry questions.

Usage
    python -I drawing_book.py --features <part.features.json> [--silk <part>_silk.json] [--project <mech folder>]
                              [--out <folder>] [--dpi 110]
    python -I drawing_book.py --all [--project <mech folder>] [--out <folder>]
        --features   one features file            --all   every part of [sheet] parts (all cores)
        --silk       the silkscreen manifest of that part: adds the SILKSCREEN POSITIONS sheet
        --dpi        resolution of the page PNGs (default 110)
    Needs matplotlib and numpy (no CadQuery).

Config keys (mech.toml)
    [project] name, company, rev
    [sheet]   material = "", parts = [ {name, step, silk_dxf?, finish = "", qty = 1, title = ""} ]
    [drawing] tolerances = [ ["Linear, after bending", "+-0.2"], ... ]     # printed as a table, unchanged
              notes = [ "text", ... ]                                       # printed numbered, unchanged
              page = "A3"                                                   # A3 (default) or A4, landscape

Exit codes
    0 the PDF(s) were written, no overlapping text, every feature has its row
    1 overlapping text on a sheet, or a feature that could not be dimensioned (a free curve)
    2 could not run (no features file, matplotlib missing)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import datetime
import json
import math
import os
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

PT = 25.4 / 72.0            # mm per point
PAGES = {"A3": (420.0, 297.0), "A4": (297.0, 210.0)}
INK, GREY, FILL, BLUE, RED = "#111111", "#666666", "#e6eaee", "#0b4f9e", "#b00020"
ROW_H = 4.3                 # table row height, mm
FS = 7.0                    # table font size, pt


def f2(x):
    """A number as printed: 2 decimals, no negative zero."""
    s = f"{float(x):.2f}"
    return "0.00" if s == "-0.00" else s


def pn(x):
    """The printed number as a float (what the manifest stores)."""
    return float(f2(x))


def tw(s, fs):
    """A text's width estimate in mm (for placing; the overlap check uses the real extents)."""
    return 0.58 * fs * PT * len(s)


# ---------------------------------------------------------------- book and sheets ------------------------------------
class Book:
    def __init__(self, part, meta, page="A3"):
        self.part, self.meta = part, meta
        self.pw, self.ph = PAGES.get(page, PAGES["A3"])
        self.sheets, self.overlaps = [], []

    def sheet(self, title):
        sh = Sheet(self, title)
        self.sheets.append(sh)
        return sh

    def save(self, pdf_path, png_dir, dpi):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages

        os.makedirs(png_dir, exist_ok=True)
        for old in os.listdir(png_dir):
            if old.startswith(self.part + "_p") and old.endswith(".png"):
                os.remove(os.path.join(png_dir, old))
        n = len(self.sheets)
        pngs = []
        with PdfPages(pdf_path, metadata={"Title": self.part, "Author": self.meta.get("company", ""),
                                          "Creator": "drawing_book", "Producer": "", "CreationDate": None}) as pdf:
            for i, sh in enumerate(self.sheets):
                sh.title_block(i + 1, n)
                self.overlaps += [(i + 1, a, b) for a, b in sh.find_overlaps()]
                pdf.savefig(sh.fig)
                p = os.path.join(png_dir, f"{self.part}_p{i + 1}.png")
                sh.fig.savefig(p, dpi=dpi)
                pngs.append(p)
                plt.close(sh.fig)
        return pngs


class Sheet:
    def __init__(self, book, title):
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        self.book, self.title = book, title
        self.pw, self.ph = book.pw, book.ph
        self.fig = plt.figure(figsize=(self.pw / 25.4, self.ph / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, self.pw)
        self.ax.set_ylim(0, self.ph)
        self.ax.axis("off")
        self.texts = []
        self.ax.add_patch(Rectangle((8, 8), self.pw - 16, self.ph - 16, fill=False, lw=0.9, ec=INK))

    def text(self, x, y, s, fs=FS, ha="left", va="baseline", color=INK, weight="normal", check=True, **kw):
        t = self.ax.text(x, y, s, fontsize=fs, ha=ha, va=va, color=color, weight=weight, family="DejaVu Sans", **kw)
        if check:
            self.texts.append(t)
        return t

    def line(self, xs, ys, lw=0.35, color=INK, ls="-", z=3):
        self.ax.plot(xs, ys, lw=lw, color=color, ls=ls, zorder=z, solid_capstyle="butt")

    def title_block(self, i, n):
        m = self.book.meta
        y0 = 8.0
        self.line([8, self.pw - 8], [y0 + 11, y0 + 11], lw=0.9)
        self.text(11, y0 + 4, f"{m.get('title') or self.book.part}", 10, weight="bold")
        self.text(11 + max(60, tw(m.get('title') or self.book.part, 10) + 8), y0 + 4, self.title, 9)
        right = "   ".join(x for x in (m.get("company", ""), m.get("project", ""), f"rev {m.get('rev', '')}",
                                       m.get("date", ""), "units: mm", f"sheet {i} / {n}") if x.strip())
        self.text(self.pw - 11, y0 + 4, right, 8, ha="right")

    def find_overlaps(self):
        """Pairs of texts whose drawn boxes overlap by more than 0.3 mm in both directions."""
        import numpy as np

        self.fig.canvas.draw()
        rend = self.fig.canvas.get_renderer()
        k = 25.4 / self.fig.dpi
        bx = np.array([[b.x0 * k, b.y0 * k, b.x1 * k, b.y1 * k] for b in
                       (t.get_window_extent(rend) for t in self.texts)]) if self.texts else np.zeros((0, 4))
        out = []
        for a in range(len(bx)):
            ox = np.minimum(bx[a, 2], bx[a + 1:, 2]) - np.maximum(bx[a, 0], bx[a + 1:, 0])
            oy = np.minimum(bx[a, 3], bx[a + 1:, 3]) - np.maximum(bx[a, 1], bx[a + 1:, 1])
            for b in np.nonzero((ox > 0.3) & (oy > 0.3))[0]:
                out.append((self.texts[a].get_text()[:40], self.texts[a + 1 + b].get_text()[:40]))
        # text that leaves the frame is a defect of the same kind
        for t, b in zip(self.texts, bx):
            if b[0] < 8.2 or b[2] > self.pw - 8.2 or b[1] < 8.2 or b[3] > self.ph - 8.2:
                out.append((t.get_text()[:40], "<outside the sheet frame>"))
        return out


class Flow:
    """Tables flowing down columns; a full column starts the next one, a full sheet a continuation sheet."""

    def __init__(self, book, title, sheet, cols):
        self.book, self.title, self.sh, self.cols = book, title, sheet, list(cols)   # cols: [(x, y_top, y_bottom, width)]
        self.ci, self.y = 0, cols[0][1]
        self.cont = 1

    def _next_col(self):
        self.ci += 1
        if self.ci >= len(self.cols):
            self.cont += 1
            self.sh = self.book.sheet(f"{self.title}: tables, continued ({self.cont})")
            pw, ph = self.sh.pw, self.sh.ph
            n = max(1, int((pw - 28) // 132))
            self.cols = [(14 + i * 132, ph - 16, 26, 126) for i in range(n)]
            self.ci = 0
        self.y = self.cols[self.ci][1]

    def para(self, lines, fs=FS, weight="normal", color=INK):
        for s in lines:
            if self.y - ROW_H < self.cols[self.ci][2]:
                self._next_col()
            self.sh.text(self.cols[self.ci][0], self.y - ROW_H + 1.2, s, fs, weight=weight, color=color)
            self.y -= ROW_H
        self.y -= 1.0

    def table(self, head, columns, rows):
        """columns: [(title, width, "l"|"r")]; rows: lists of strings. The header repeats in every column."""
        import numpy as np

        w = sum(c[1] for c in columns)
        i = 0
        first = True
        while first or i < len(rows):
            x0, _yt, yb, cw = self.cols[self.ci]
            if self.y - 3 * ROW_H < yb:
                self._next_col()
                continue
            sc = min(1.0, cw / w)
            self.sh.text(x0, self.y - ROW_H + 1.2, head + ("" if first else " (continued)"), FS + 0.5, weight="bold")
            self.y -= ROW_H
            top = self.y
            xs = np.cumsum([0] + [c[1] * sc for c in columns]) + x0
            has_head = any(c[0] for c in columns)
            if has_head:
                for k, c in enumerate(columns):
                    self._cell(xs[k], xs[k + 1], self.y, c[0], c[2], True)
                self.y -= ROW_H
            while i < len(rows) and self.y - ROW_H >= yb:
                for k, c in enumerate(columns):
                    self._cell(xs[k], xs[k + 1], self.y, rows[i][k], c[2], False)
                self.y -= ROW_H
                i += 1
            for x in xs:
                self.sh.line([x, x], [top, self.y], lw=0.2, color=GREY)
            yy = top
            while yy >= self.y - 1e-6:
                self.sh.line([xs[0], xs[-1]], [yy, yy], lw=0.45 if (yy == top or (has_head and yy == top - ROW_H)) else 0.2, color=GREY)
                yy -= ROW_H
            self.y -= 2.5
            first = False
            if i < len(rows):
                self._next_col()

    def _cell(self, xa, xb, y, s, align, head):
        if align == "r":
            self.sh.text(xb - 1.0, y - ROW_H + 1.2, s, FS, ha="right", weight="bold" if head else "normal")
        else:
            self.sh.text(xa + 1.0, y - ROW_H + 1.2, s, FS, weight="bold" if head else "normal")


class Placer:
    """Label boxes that avoid each other."""

    def __init__(self):
        self.boxes = []

    def hit(self, b):
        return sum(1 for a in self.boxes if min(a[2], b[2]) - max(a[0], b[0]) > -0.4 and
                   min(a[3], b[3]) - max(a[1], b[1]) > -0.4)

    def block(self, x0, y0, x1, y1):
        self.boxes.append((x0, y0, x1, y1))

    def place(self, x, y, s, fs, clear=1.5, prefer=(1, 1), bounds=None):
        """The label's centre for an anchor at (x, y): the first free place round it."""
        w, h = tw(s, fs) + 0.6, fs * PT * 1.05
        dirs = [prefer, (1, 0), (0, 1), (-1, 1), (1, -1), (-1, 0), (0, -1), (-1, -1)]
        best = None
        for rad in (clear, clear + 2.5, clear + 5.5, clear + 9, clear + 14, clear + 20):
            for dx, dy in dirs:
                nrm = math.hypot(dx, dy)
                cx = x + dx / nrm * (rad + w / 2 * abs(dx / nrm))
                cy = y + dy / nrm * (rad + h / 2 * abs(dy / nrm))
                b = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                if bounds and (b[0] < bounds[0] or b[1] < bounds[1] or b[2] > bounds[2] or b[3] > bounds[3]):
                    continue
                n = self.hit(b)
                if n == 0:
                    self.boxes.append(b)
                    return cx, cy
                if best is None or n < best[0]:
                    best = (n, cx, cy, b)
        if best is None:
            return x, y
        self.boxes.append(best[3])
        return best[1], best[2]


# ---------------------------------------------------------------- the panel view -------------------------------------
DETAIL = 46.0               # side of a detail view's box, page mm
CROWD = 4.2                 # outline nodes closer than this on the page are labelled in a detail view


def crowded(all_nodes, s):
    """Groups (2 or more) of outline nodes closer than CROWD on the page at scale s, largest first."""
    n = len(all_nodes)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a in range(n):
        for b in range(a + 1, n):
            na, nb = all_nodes[a][1], all_nodes[b][1]
            if math.hypot(na["u"] - nb["u"], na["v"] - nb["v"]) * s < CROWD:
                parent[find(a)] = find(b)
    groups = {}
    for a in range(n):
        groups.setdefault(find(a), []).append(all_nodes[a])
    out = [g for g in groups.values() if len(g) > 1]
    out.sort(key=lambda g: (min(nd["v"] for _i, nd in g), min(nd["u"] for _i, nd in g)))
    return out


def detail_view(sh, panel, group, letter, c0, c1, rad, bx, by):
    """An enlarged window round a group of crowded nodes, in the box at (bx, by), with their labels."""
    from matplotlib.patches import Circle, Polygon, Rectangle

    inner = DETAIL - 16.0                  # the window; the rim of the box is room for labels
    sd = inner / (2 * rad)
    cx, cy = bx + DETAIL / 2, by + DETAIL / 2

    def D(u, v):
        return cx + (u - c0) * sd, cy + (v - c1) * sd

    frame = Rectangle((bx, by), DETAIL, DETAIL, fc="white", ec=BLUE, lw=0.5, zorder=8)
    sh.ax.add_patch(frame)
    clip = Rectangle((cx - inner / 2 - 3, cy - inner / 2 - 3), inner + 6, inner + 6, transform=sh.ax.transData)
    for fc in panel["faces"]:
        pg = Polygon([D(*q) for q in fc["path"]], closed=True, fc=FILL, ec=INK, lw=0.6, zorder=9)
        sh.ax.add_patch(pg)
        pg.set_clip_path(clip)
    for f in panel["features"]:
        pg = Polygon([D(*q) for q in f["path"]], closed=True, fc="white", ec=INK, lw=0.4, zorder=9)
        sh.ax.add_patch(pg)
        pg.set_clip_path(clip)
    pl = Placer()
    pts = [D(nd["u"], nd["v"]) for _i, nd in group]
    for x, y in pts:
        pl.block(x - 0.8, y - 0.8, x + 0.8, y + 0.8)
        sh.ax.add_patch(Circle((x, y), 0.55, fc=BLUE, ec="none", zorder=10))
    for (nid, _nd), (x, y) in zip(group, pts):
        pref = (1 if x >= cx else -1, 1 if y >= cy else -1)
        lx, ly = pl.place(x, y, short(nid), 6.5, clear=1.0, prefer=pref, bounds=(bx + 0.5, by + 0.5, bx + DETAIL - 0.5,
                                                                                  by + DETAIL - 0.5))
        sh.text(lx, ly, short(nid), 6.5, ha="center", va="center", color=BLUE, zorder=11)
    sh.text(bx, by + DETAIL + 1.5, f"DETAIL {letter}   {scale_name(round(sd, 1))}", 7, weight="bold", color=BLUE)


SCALES = [10, 5, 4, 3, 2, 1.5, 1, 0.75, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.02]


def scale_name(s):
    return f"{s:g} : 1" if s >= 1 else f"1 : {1 / s:g}"


def pick_scale(w, h, aw, ah):
    for s in SCALES:
        if w * s <= aw and h * s <= ah:
            return s
    return SCALES[-1]


def short(i):
    return i.split("-", 1)[1] if "-" in i else i


def panel_view(sh, panel, area):
    """Draw one panel in area (x0, y0, x1, y1); returns the scale."""
    import numpy as np
    from matplotlib.patches import Circle, Polygon

    ax0, ay0, ax1, ay1 = area
    e = panel["extent"]
    w, h = e[2], e[3]                     # from the datum (0, 0) to the far extreme
    m = 24.0                              # room for labels and the overall dimensions
    all_nodes = [(nid, nd) for fc in panel["faces"] for nid, nd in zip(fc.get("node_ids") or [], fc["nodes"] or [])]

    def fit(top):
        sc = pick_scale(max(w, 1), max(h, 1), ax1 - ax0 - 2 * m, top - ay0 - 2 * m)
        return sc, ax0 + m + ((ax1 - ax0 - 2 * m) - w * sc) / 2, ay0 + m + ((top - ay0 - 2 * m) - h * sc) / 2

    s, ox, oy = fit(ay1)
    groups = crowded(all_nodes, s)
    if groups:                            # crowded nodes get enlarged detail views in a band over the view
        s, ox, oy = fit(ay1 - DETAIL - 12)
        groups = crowded(all_nodes, s)
    n_fit = int((ax1 - ax0 - 8) // (DETAIL + 6))
    groups = groups[:n_fit]
    in_detail = {nid for g in groups for nid, _nd in g}

    def P(u, v):
        return ox + u * s, oy + v * s

    pl = Placer()
    bounds = (ax0, ay0, ax1, ay1)
    for fc in panel["faces"]:
        sh.ax.add_patch(Polygon([P(*q) for q in fc["path"]], closed=True, fc=FILL, ec=INK, lw=0.6, zorder=1))
    for bl in panel["bend_lines"]:
        (xa, ya), (xb, yb) = P(*bl["p"]), P(*bl["q"])
        sh.line([xa, xb], [ya, yb], lw=0.5, color=BLUE, ls=(0, (6, 2, 1, 2)), z=4)
    drawn = set()
    for bl in panel["bend_lines"]:
        if bl["bend"] in drawn:
            continue
        drawn.add(bl["bend"])
        (xa, ya), (xb, yb) = P(*bl["p"]), P(*bl["q"])
        cx, cy = pl.place((xa + xb) / 2, (ya + yb) / 2, f"bend {bl['bend']}", 6.5, clear=1.2, prefer=(0, -1),
                          bounds=bounds)
        sh.text(cx, cy, f"bend {bl['bend']}", 6.5, ha="center", va="center", color=BLUE)
    feats = list(panel["features"])
    for f in feats + [h_ for h_ in panel["hardware"] if h_.get("path")]:
        sh.ax.add_patch(Polygon([P(*q) for q in f["path"]], closed=True, fc="white", ec=INK, lw=0.45, zorder=2))
    for p in panel["patterns"]:
        for u, v in p["holes"]:
            sh.ax.add_patch(Circle(P(u, v), p["d"] / 2 * s, fc="white", ec=INK, lw=0.3, zorder=2))
        x0, y0 = P(p["extent"][0] - 1, p["extent"][1] - 1)
        x1, y1 = P(p["extent"][2] + 1, p["extent"][3] + 1)
        sh.line([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], lw=0.3, color=RED, ls=(0, (3, 2)))
        pl.block(x0, y0, x1, y1)
    # the datum: X and Y arrows from (0, 0)
    dx, dy = P(0, 0)
    for (ex, ey), nm in (((12, 0), "X"), ((0, 12), "Y")):
        sh.ax.annotate("", xy=(dx + ex, dy + ey), xytext=(dx, dy), zorder=6,
                       arrowprops=dict(arrowstyle="-|>", lw=0.9, color=RED, shrinkA=0, shrinkB=0))
        sh.text(dx + ex * 1.12 + (0 if ex else -1.2), dy + ey * 1.12 + (0 if ey else -1.2), nm, 8, color=RED,
                weight="bold", ha="center" if ey else "left", va="center" if ex else "bottom")
        pl.block(dx - 1, dy - 1, dx + ex * 1.3 + 2, dy + ey * 1.3 + 2)
    sh.ax.add_patch(Circle((dx, dy), 1.1, fc="none", ec=RED, lw=0.9, zorder=6))
    sh.text(dx - 2.0, dy - 2.0, "0 , 0", 7, color=RED, ha="right", va="top", weight="bold")
    pl.block(dx - 14, dy - 6, dx, dy)
    # anchors first (so that no label covers a small feature), then the labels
    todo = []
    for f in feats:
        x, y = P(f["u"], f["v"])
        if f["kind"] == "hole":
            clear = f["d"] / 2 * s + 0.9
        else:
            clear = min(max(f.get("w", 0), f.get("h", 0), f.get("l", 0)) / 2 * s, 9.0) * 0.72 + 0.8
        todo.append((x, y, short(f["id"]), clear, INK))
    for hw in panel["hardware"]:
        x, y = P(hw["u"], hw["v"])
        sh.ax.add_patch(Circle((x, y), max((hw.get("hole") or 3) / 2 * s, 0.9), fc="none", ec=RED, lw=0.5, zorder=3))
        todo.append((x, y, short(hw["id"]), max((hw.get("hole") or 3) / 2 * s, 0.9) + 0.6, RED))
    for p in panel["patterns"]:
        x, y = P(p["extent"][2] + 1, p["extent"][3] + 1)
        todo.append((x, y, short(p["id"]), 0.8, RED))
    cen = np.mean([P(*q) for fc in panel["faces"] for q in fc["path"]], axis=0)
    node_lab = []
    for nid, nd in all_nodes:
        x, y = P(nd["u"], nd["v"])
        sh.ax.add_patch(Circle((x, y), 0.45, fc=BLUE, ec="none", zorder=5))
        d = np.array([x, y]) - cen
        if nid not in in_detail:
            node_lab.append((x, y, short(nid), (1 if d[0] >= 0 else -1, 1 if d[1] >= 0 else -1)))
    for k, g in enumerate(groups):
        letter = "ABCDEFGHJKLMNPQRSTUVWXYZ"[k % 24]
        us, vs = [nd["u"] for _i, nd in g], [nd["v"] for _i, nd in g]
        c0, c1 = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
        rad = max(max(us) - min(us), max(vs) - min(vs)) / 2 + 1.5
        x, y = P(c0, c1)
        sh.ax.add_patch(Circle((x, y), rad * s + 0.8, fc="none", ec=BLUE, lw=0.5, zorder=6))
        todo.append((x, y, letter, rad * s + 1.2, BLUE))
        detail_view(sh, panel, g, letter, c0, c1, rad, ax0 + 4 + k * (DETAIL + 6), ay1 - DETAIL - 4)
    for x, y, _s, r, _c in todo:
        pl.block(x - min(r, 2), y - min(r, 2), x + min(r, 2), y + min(r, 2))
    for x, y, lab, r, col in todo:
        cx, cy = pl.place(x, y, lab, 7, clear=r, bounds=bounds)
        sh.text(cx, cy, lab, 7, ha="center", va="center", color=col, weight="bold", zorder=7)
        if math.hypot(cx - x, cy - y) > r + 6:
            sh.line([x, cx], [y, cy], lw=0.2, color=GREY)
    for x, y, lab, pref in node_lab:
        cx, cy = pl.place(x, y, lab, 6, clear=0.9, prefer=pref, bounds=bounds)
        sh.text(cx, cy, lab, 6, ha="center", va="center", color=BLUE, zorder=7)
        if math.hypot(cx - x, cy - y) > 6:
            sh.line([x, cx], [y, cy], lw=0.2, color=BLUE)
    # overall sizes from the datum
    x1, y1 = P(w, h)
    yd = oy - 13
    sh.ax.annotate("", xy=(x1, yd), xytext=(dx, yd), arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=INK,
                                                                     shrinkA=0, shrinkB=0))
    sh.line([dx, dx], [yd - 1.5, oy - 3], lw=0.2)
    sh.line([x1, x1], [yd - 1.5, oy - 1], lw=0.2)
    sh.text((dx + x1) / 2, yd + 1.0, f2(w), 8, ha="center")
    xd = ox - 16
    sh.ax.annotate("", xy=(xd, y1), xytext=(xd, dy), arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=INK,
                                                                     shrinkA=0, shrinkB=0))
    sh.line([xd - 1.5, ox - 3], [dy, dy], lw=0.2)
    sh.line([xd - 1.5, ox - 1], [y1, y1], lw=0.2)
    sh.text(xd - 2.2, (dy + y1) / 2, f2(h), 8, ha="center", va="center", rotation=90)
    return s


# ---------------------------------------------------------------- table rows and the manifest ------------------------
def node_rows(ids, nds):
    rows, man = [], []
    for nid, nd in zip(ids, nds):
        if "arc" in nd:
            c = nd["arc"]
            txt = f"arc to next node: centre X {f2(c[0])} Y {f2(c[1])}, r {f2(c[2])}, {c[3]}"
            man.append({"id": nid, "X": pn(nd["u"]), "Y": pn(nd["v"]), "arc": [pn(c[0]), pn(c[1]), pn(c[2]), c[3]]})
        else:
            txt = "sharp corner" if nd["r"] == 0 else f"corner rounded r {f2(nd['r'])} (X, Y: the virtual sharp)"
            man.append({"id": nid, "X": pn(nd["u"]), "Y": pn(nd["v"]), "r": pn(nd["r"])})
        rows.append([nid, f2(nd["u"]), f2(nd["v"]), txt])
    return rows, man


def feature_rows(panel):
    rows, man, extra, bad = [], [], [], []
    for f in panel["features"]:
        m = {"id": f["id"], "kind": f["kind"], "X": pn(f["u"]), "Y": pn(f["v"])}
        if f["kind"] == "hole":
            typ, size = "round hole", f"d {f2(f['d'])}"
            m["d"] = pn(f["d"])
        elif f["kind"] == "slot":
            typ, size = "slot", f"{f2(f['w'])} wide x {f2(f['l'])} long along {f['along']}, round ends"
            m.update(w=pn(f["w"]), l=pn(f["l"]), along=f["along"])
        elif f["kind"] == "rect":
            typ = "rectangle"
            size = f"{f2(f['w'])} (X) x {f2(f['h'])} (Y)" + (f", corners r {f2(f['r'])}" if f["r"] else ", sharp corners")
            m.update(w=pn(f["w"]), h=pn(f["h"]), r=pn(f["r"]))
        elif f.get("nodes"):
            ids = [f"{f['id']}.{k + 1}" for k in range(len(f["nodes"]))]
            typ, size = "cut-out", f"box {f2(f['w'])} x {f2(f['h'])}: see its node table"
            nr, nm = node_rows(ids, f["nodes"])
            extra.append((f"CUT-OUT {f['id']}: OUTLINE NODES, IN ORDER", nr))
            m.update(nodes=nm)
        else:
            typ, size = "cut-out", "NOT DIMENSIONED: an edge is a free curve"
            m.update(undimensioned=True)
            bad.append(f["id"])
        rows.append([f["id"], typ, f2(f["u"]), f2(f["v"]), size])
        man.append(m)
    return rows, man, extra, bad


FEAT_COLS = [("ID", 16, "l"), ("Type", 19, "l"), ("X", 14, "r"), ("Y", 14, "r"), ("Size (all through)", 75, "l")]
NODE_COLS = [("Node", 22, "l"), ("X", 14, "r"), ("Y", 14, "r"), ("Corner", 88, "l")]
PAT_COLS = [("Row", 12, "r"), ("Y", 16, "r"), ("X first", 18, "r"), ("X last", 18, "r"), ("Holes", 14, "r")]
HW_COLS = [("ID", 16, "l"), ("Hardware", 40, "l"), ("Thread", 14, "l"), ("Hole d", 14, "r"), ("X", 14, "r"), ("Y", 14, "r"),
           ("Body on", 26, "l")]
BEND_COLS = [("Bend", 12, "l"), ("Joins", 62, "l"), ("Inner r", 16, "r"), ("Outer r", 16, "r"), ("Angle", 16, "r"),
             ("Length", 18, "r")]


def panel_tables(flow, panel):
    man = {"frame": {"origin": panel["origin"], "u": panel["u"], "v": panel["v"], "normal": panel["normal"]},
           "outlines": [], "features": [], "patterns": [], "hardware": []}
    rows, fman, extra, bad = feature_rows(panel)
    man["features"] = fman
    if rows:
        flow.table(f"HOLES, SLOTS, CUT-OUTS ({len(rows)}): X, Y OF THE CENTRE FROM THE DATUM", FEAT_COLS, rows)
    for head, nr in extra:
        flow.table(head, NODE_COLS, nr)
    for p in panel["patterns"]:
        ax_, cr = p["row_axis"], "Y" if p["row_axis"] == "X" else "X"
        cols = [("Row", 12, "r"), (cr, 16, "r"), (f"{ax_} first", 18, "r"), (f"{ax_} last", 18, "r"), ("Holes", 14, "r")]
        prow = [[str(k + 1), f2(c), f2(a), f2(pn(a) + (n - 1) * pn(p["pitch"])), str(n)]
                for k, (c, a, n) in enumerate(p["rows"])]
        flow.table(f"PATTERN {p['id']}: {p['n']} HOLES d {f2(p['d'])}, PITCH {f2(p['pitch'])} ALONG {ax_} IN EACH ROW",
                   cols, prow)
        man["patterns"].append({"id": p["id"], "d": pn(p["d"]), "pitch": pn(p["pitch"]), "row_axis": ax_, "n": p["n"],
                                "rows": [[pn(c), pn(a), int(n)] for c, a, n in p["rows"]]})
    if panel["hardware"]:
        hrow = [[h["id"], h["code"], h.get("thread", ""), f2(h["hole"]) if h.get("hole") else "", f2(h["u"]), f2(h["v"]),
                 h.get("body", "")] for h in panel["hardware"]]
        flow.table(f"HARDWARE ({len(hrow)}): X, Y OF THE CENTRE FROM THE DATUM", HW_COLS, hrow)
        for h in panel["hardware"]:
            man["hardware"].append({"id": h["id"], "code": h["code"], "X": pn(h["u"]), "Y": pn(h["v"]),
                                    "hole": pn(h["hole"]) if h.get("hole") else None,
                                    "model_d": pn(h["model_d"]) if h.get("model_d") else None,
                                    "modelled": bool(h.get("modelled"))})
    for k, fc in enumerate(panel["faces"]):
        if not fc["nodes"]:
            bad.append(f"{panel['name']} outline {k + 1}")
            man["outlines"].append({"undimensioned": True})
            continue
        nr, nm = node_rows(fc["node_ids"], fc["nodes"])
        head = "OUTLINE NODES, IN ORDER" + (f" (piece {k + 1} of {len(panel['faces'])})" if len(panel["faces"]) > 1 else "")
        flow.table(head, NODE_COLS, nr)
        man["outlines"].append({"nodes": nm})
    return man, bad


# ---------------------------------------------------------------- the sheets -----------------------------------------
def general_sheet(book, feats, cfg, part_cfg):
    sh = book.sheet("GENERAL")
    pw, ph = sh.pw, sh.ph
    sh.text(14, ph - 20, f"{book.meta.get('title') or feats['part']}", 16, weight="bold")
    sh.text(14, ph - 27, "Sheet-metal part, fully dimensioned: every hole, slot and cut-out has its X and Y from the "
                         "datum corner of its panel's sheet.", 8.5)
    flow = Flow(book, "GENERAL", sh, [(14, ph - 34, 26, 126), (146, ph - 34, 26, 126), (278, ph - 34, 26, 126)])
    b = feats["bbox"]["size"]
    data = [["Part", feats["part"]], ["STEP file", os.path.basename(feats["step"]["path"])],
            ["STEP sha256", feats["step"]["sha256"][:16] + "..."],
            ["Overall size", f"{f2(b[0])} x {f2(b[1])} x {f2(b[2])}"], ["Sheet thickness", f2(feats["thickness"])]]
    for key, lab in (("material", "Material"),):
        if cfg.get("sheet", {}).get(key):
            data.append([lab, str(cfg["sheet"][key])])
    for key, lab in (("finish", "Finish"), ("qty", "Quantity")):
        if part_cfg.get(key) not in (None, ""):
            data.append([lab, str(part_cfg[key])])
    flow.table("PART", [("", 30, "l"), ("", 96, "l")], data)
    brow = [[x["id"], " / ".join(x["panels"]), f2(x["r_inner"]) if x["r_inner"] is not None else "none",
             f2(x["r_outer"]) if x["r_outer"] is not None else "none", f2(x["angle"]), f2(x["length"])]
            for x in feats["bends"]]
    if brow:
        flow.table(f"BENDS ({len(brow)}): angle = the angle the sheet is bent through, degrees", BEND_COLS, brow)
    for sb in feats.get("sharp_bends", []):
        flow.para([f"SHARP BEND (no radius in the model): {' / '.join(sb['panels'])}, length {f2(sb['length'])}"],
                  color=RED, weight="bold")
    hrow = []
    for p in feats["panels"]:
        for h in p["hardware"]:
            hrow.append([h["id"], h["code"], h.get("thread", ""), f2(h["hole"]) if h.get("hole") else "", p["name"]])
    if hrow:
        flow.table(f"HARDWARE ({len(hrow)}): positions on each panel's sheet",
                   [("ID", 16, "l"), ("Hardware", 46, "l"), ("Thread", 16, "l"), ("Hole d", 16, "r"), ("Panel", 32, "l")],
                   hrow)
    tol = cfg.get("drawing", {}).get("tolerances") or []
    if tol:
        flow.table("GENERAL TOLERANCES", [("", 76, "l"), ("", 50, "l")], [[str(a), str(b_)] for a, b_ in tol])
    else:
        flow.para(["GENERAL TOLERANCES: none given in mech.toml ([drawing] tolerances)."], weight="bold")
    notes = cfg.get("drawing", {}).get("notes") or []
    if notes:
        flow.para(["NOTES"], FS + 0.5, weight="bold")
        for k, n in enumerate(notes):
            wrapped = textwrap.wrap(str(n), 86) or [""]
            flow.para([f"{k + 1}. " + wrapped[0]] + ["    " + x for x in wrapped[1:]])
    flow.para(["HOW TO READ", ], FS + 0.5, weight="bold")
    flow.para(["Dimensions in mm, angles in degrees.",
               "Each panel has its own sheet, drawn as seen (the sheet says from where).",
               "X is to the right and Y is up on that sheet, both from the datum corner 0 , 0.",
               "IDs: panel code - H hole, S slot, C cut-out, PT pattern, P hardware, N outline node.",
               "The flat pattern sheet is a reference estimate only."])
    return sh, flow


def panel_sheet(book, panel):
    title = f"PANEL {panel['name']} ({panel['code']})"
    sh = book.sheet(title)
    pw, ph = sh.pw, sh.ph
    split = pw * 0.60
    sh.text(14, ph - 18, title, 13, weight="bold")
    sh.text(14, ph - 24.5, f"Seen {panel['seen_text']}. Datum: {panel['datum_text']}.", 8)
    s = panel_view(sh, panel, (12, 24, split, ph - 30))
    sh.text(14, 22.5, f"View scale {scale_name(s)}.  Blue dots: outline nodes.  Blue dash-dot: bend lines (tangent "
                      "lines).  Red dashed box: a hole pattern (its table gives every row).", 7)
    sh.line([split + 2, split + 2], [20, ph - 10], lw=0.3, color=GREY)
    flow = Flow(book, title, sh, [(split + 5, ph - 14, 26, pw - 14 - split - 5)])
    man, bad = panel_tables(flow, panel)
    man["scale"] = s
    return man, bad


def flat_sheet(book, feats):
    from matplotlib.patches import Polygon

    fl = feats["flat"]
    sh = book.sheet("FLAT PATTERN (REFERENCE ONLY)")
    pw, ph = sh.pw, sh.ph
    sh.text(14, ph - 18, "FLAT PATTERN: REFERENCE ONLY", 13, weight="bold", color=RED)
    if not fl.get("outer"):
        sh.text(14, ph - 30, "The part could not be unfolded: " + fl.get("note", ""), 9)
        return {"reference_only": True, "unfolded": False}
    w, h = fl["size"]
    sh.text(14, ph - 24.5, f"An estimate with K factor {fl['k_factor']:g} (bend allowance = angle x (inner r + K x t)); "
                           "the supplier unfolds the STEP with its own bend table. Do not cut from this sheet.", 8)
    area = (14, 26, pw - 14, ph - 30)
    m = 22
    s = pick_scale(w, h, area[2] - area[0] - 2 * m, area[3] - area[1] - 2 * m)
    ox = area[0] + m + ((area[2] - area[0] - 2 * m) - w * s) / 2
    oy = area[1] + m + ((area[3] - area[1] - 2 * m) - h * s) / 2
    for ring in fl["outer"]:
        sh.ax.add_patch(Polygon([(ox + x * s, oy + y * s) for x, y in ring], closed=True, fc=FILL, ec=INK, lw=0.6))
    for ring in fl["holes"]:
        sh.ax.add_patch(Polygon([(ox + x * s, oy + y * s) for x, y in ring], closed=True, fc="white", ec=INK, lw=0.35))
    pl = Placer()
    for bl in fl["bend_lines"]:
        xa, ya, xb, yb = ox + bl["p"][0] * s, oy + bl["p"][1] * s, ox + bl["q"][0] * s, oy + bl["q"][1] * s
        sh.line([xa, xb], [ya, yb], lw=0.5, color=BLUE, ls=(0, (6, 2, 1, 2)))
        cx, cy = pl.place((xa + xb) / 2, (ya + yb) / 2, bl["bend"], 7, clear=1.0, prefer=(0, 1))
        sh.text(cx, cy, bl["bend"], 7, ha="center", va="center", color=BLUE, weight="bold")
    sh.ax.annotate("", xy=(ox + w * s, oy - 10), xytext=(ox, oy - 10),
                   arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=INK, shrinkA=0, shrinkB=0))
    sh.text(ox + w * s / 2, oy - 9, f"{f2(w)} (reference)", 8, ha="center")
    sh.ax.annotate("", xy=(ox - 10, oy + h * s), xytext=(ox - 10, oy),
                   arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=INK, shrinkA=0, shrinkB=0))
    sh.text(ox - 12.5, oy + h * s / 2, f"{f2(h)} (reference)", 8, ha="center", va="center", rotation=90)
    sh.text(14, 22.5, f"Scale {scale_name(s)}.  Blank about {f2(w)} x {f2(h)}, area {fl['area']:.0f} mm2.  Blue "
                      "dash-dot: bend centre lines.", 7)
    return {"reference_only": True, "unfolded": True, "k_factor": fl["k_factor"], "size": [pn(w), pn(h)]}


def silk_sheet(book, silk):
    """The silkscreen positions: every element's box from its face's datum (the face's lower-left as seen)."""
    from matplotlib.patches import Polygon, Rectangle

    sh = book.sheet("SILKSCREEN POSITIONS")
    pw, ph = sh.pw, sh.ph
    sh.text(14, ph - 18, "SILKSCREEN POSITIONS", 13, weight="bold")
    sh.text(14, ph - 24.5, "Each printed element's box (X0, Y0 = its lower-left corner; W, H) from the lower-left "
                           "extreme of its face, as seen from outside. The artwork itself is the DXF file "
                           f"{silk.get('dxf', '')}.", 8)
    faces = silk["faces"]
    split = pw * 0.55
    n = len(faces)
    slot_h = (ph - 30 - 26) / max(n, 1)
    man = {"dxf": silk.get("dxf", ""), "faces": []}
    rows = []
    for k, fc in enumerate(faces):
        x0, y0, x1, y1 = fc["bbox"]
        w, h = x1 - x0, y1 - y0
        a = (14, ph - 30 - (k + 1) * slot_h, split, ph - 30 - k * slot_h)
        s = pick_scale(w, h, a[2] - a[0] - 30, a[3] - a[1] - 16)
        ox, oy = a[0] + 18, a[1] + 6
        for ring in fc["outline"]:
            sh.ax.add_patch(Polygon([(ox + (x - x0) * s, oy + (y - y0) * s) for x, y in ring], closed=True, fc=FILL,
                                    ec=INK, lw=0.5, zorder=1))
        for ring in fc.get("cutouts", []):
            sh.ax.add_patch(Polygon([(ox + (x - x0) * s, oy + (y - y0) * s) for x, y in ring], closed=True, fc="white",
                                    ec=INK, lw=0.35, zorder=2))
        sh.text(ox, oy + h * s + 2.5, f"Face {fc['name']}, scale {scale_name(s)}", 8, weight="bold")
        pl = Placer()
        fm = {"name": fc["name"], "elements": []}
        for el in fc["elements"]:
            bx = el["bbox"]
            sh.ax.add_patch(Rectangle((ox + (bx[0] - x0) * s, oy + (bx[1] - y0) * s), (bx[2] - bx[0]) * s,
                                      (bx[3] - bx[1]) * s, fill=False, ec=RED, lw=0.35, zorder=4))
            cx, cy = pl.place(ox + (bx[2] - x0) * s, oy + (bx[3] - y0) * s, el["id"], 6, clear=0.6)
            sh.text(cx, cy, el["id"], 6, ha="center", va="center", color=RED)
            rows.append([el["id"], fc["name"], el["kind"], el["ink"], f2(bx[0] - x0), f2(bx[1] - y0), f2(bx[2] - bx[0]),
                         f2(bx[3] - bx[1]), str(el.get("text", ""))[:26]])
            fm["elements"].append({"id": el["id"], "ink": el["ink"], "X0": pn(bx[0] - x0), "Y0": pn(bx[1] - y0),
                                   "W": pn(bx[2] - bx[0]), "H": pn(bx[3] - bx[1])})
        man["faces"].append(fm)
    flow = Flow(book, "SILKSCREEN POSITIONS", sh, [(split + 4, ph - 30, 26, pw - 14 - split - 4)])
    flow.table(f"PRINTED ELEMENTS ({len(rows)})",
               [("ID", 13, "l"), ("Face", 18, "l"), ("Kind", 14, "l"), ("Ink (chart name)", 28, "l"), ("X0", 14, "r"),
                ("Y0", 14, "r"), ("W", 14, "r"), ("H", 14, "r"), ("Text", 44, "l")], rows)
    flow.para(["Inks used: " + ", ".join(silk.get("inks", []))])
    return man


# ---------------------------------------------------------------- one part -------------------------------------------
def make_book(job_args):
    feat_path, silk_path, out, cfg, part_cfg, dpi = job_args
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42
    matplotlib.rcParams["svg.hashsalt"] = "drawing_book"

    feats = mc.load_json(feat_path)
    part = feats["part"]
    pr = cfg.get("project", {})
    meta = {"title": part_cfg.get("title") or part, "company": pr.get("company", ""), "project": pr.get("name", ""),
            "rev": pr.get("rev", ""), "date": datetime.date.today().isoformat()}
    book = Book(part, meta, cfg.get("drawing", {}).get("page", "A3"))
    gsh, gflow = general_sheet(book, feats, cfg, part_cfg)
    man = {"part": part, "step_sha256": feats["step"]["sha256"], "features_sha256": mc.sha256(feat_path),
           "thickness": pn(feats["thickness"]), "decimals": 2, "panels": {},
           "bends": [{"id": b["id"], "r_inner": pn(b["r_inner"]) if b["r_inner"] is not None else None,
                      "r_outer": pn(b["r_outer"]) if b["r_outer"] is not None else None, "angle": pn(b["angle"]),
                      "length": pn(b["length"]), "panels": b["panels"]} for b in feats["bends"]]}
    bad = []
    for panel in feats["panels"]:
        m, b = panel_sheet(book, panel)
        man["panels"][panel["name"]] = m
        bad += b
    man["flat"] = flat_sheet(book, feats)
    if silk_path:
        man["silk"] = silk_sheet(book, mc.load_json(silk_path))
    gflow.table("SHEETS IN THIS PDF", [("Sheet", 14, "r"), ("Content", 112, "l")],
                [[str(i + 1), s.title] for i, s in enumerate(book.sheets)])
    d = os.path.join(out, "drawings")
    pdf = os.path.join(d, f"{part}.pdf")
    pngs = book.save(pdf, os.path.join(d, "pages"), dpi)
    man["pdf"] = os.path.basename(pdf)
    man["sheets"] = [s.title for s in book.sheets]
    man["text_overlaps"] = [list(o) for o in book.overlaps]
    return part, pdf, pngs, man, bad, [feat_path] + ([silk_path] if silk_path else [])


def main(argv=None):
    ap = argparse.ArgumentParser(description="features JSON -> fully dimensioned PDF + manifest")
    mc.add_std_args(ap)
    ap.add_argument("--features")
    ap.add_argument("--silk")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dpi", type=int, default=110)
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    for lib in ("matplotlib", "numpy"):
        mc.require_module(lib, "drawing_book.py")
    parts_cfg = {p["name"]: p for p in job.cfg.get("sheet", {}).get("parts", [])}
    d = os.path.join(job.out, "drawings")
    jobs = []
    if args.all:
        for name, pc in parts_cfg.items():
            sp = os.path.join(job.out, "silk", f"{name}_silk.json")
            jobs.append((os.path.join(d, f"{name}.features.json"), sp if os.path.isfile(sp) else None, job.out, job.cfg,
                         pc, args.dpi))
    elif args.features:
        name = os.path.basename(args.features).replace(".features.json", "")
        jobs.append((os.path.abspath(args.features), os.path.abspath(args.silk) if args.silk else None, job.out,
                     job.cfg, parts_cfg.get(name, {}), args.dpi))
    if not jobs:
        print("could not run: give --features <file> or --all with [sheet] parts in mech.toml", file=sys.stderr)
        return 2
    missing = [j[0] for j in jobs if not os.path.isfile(j[0])] + [j[1] for j in jobs if j[1] and not os.path.isfile(j[1])]
    if missing:
        print("could not run: not found: " + ", ".join(missing) + " (run sheet_features.py first)", file=sys.stderr)
        return 2
    results = []
    if len(jobs) == 1:
        results.append(make_book(jobs[0]))
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(mc.workers(), len(jobs))) as ex:
            for k, r in enumerate(ex.map(make_book, jobs)):
                print(f"  [{k + 1}/{len(jobs)}] {r[0]}", flush=True)
                results.append(r)
    man_path = os.path.join(d, "drawing_manifest.json")
    manifest = mc.load_json(man_path) if os.path.isfile(man_path) else {"script": "drawing_book", "parts": {}}
    rows = mc.Rows()
    inputs = []
    for part, pdf, pngs, man, bad, ins in results:
        manifest["parts"][part] = man
        inputs += ins
        nfeat = sum(len(p["features"]) + len(p["hardware"]) + sum(q["n"] for q in p["patterns"])
                    for p in man["panels"].values())
        rows.add(f"DB-{part}-01", f"drawing:{part}", "every feature and outline has its dimensions",
                 f"{nfeat} features tabled; not dimensioned: {', '.join(bad) if bad else 'none'}", "none left out",
                 "pass" if not bad else "fail")
        ov = man["text_overlaps"]
        rows.add(f"DB-{part}-02", f"drawing:{part}", "no overlapping or clipped text on any sheet",
                 f"{len(ov)} pair(s)" + (": " + "; ".join(f"sheet {o[0]}: '{o[1]}' / '{o[2]}'" for o in ov[:6]) if ov else ""),
                 "0", "pass" if not ov else "fail")
        print(f"{part}: {len(man['sheets'])} sheets -> {pdf}; page pictures: {os.path.dirname(pngs[0])} (look at them)")
    manifest["date"] = mc.now_utc()
    mc.atomic_write(man_path, json.dumps(manifest, indent=1) + "\n")
    rows.write(job.out, "drawing_book.py", inputs)
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
