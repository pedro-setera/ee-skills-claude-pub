"""Review images of a board: renders, plots per layer, zoom tiles, and a contact sheet that names every crop.

What it makes (in <out>/review/)
    From a board file:
      render_top.png, render_bottom.png, render_angle1.png, render_angle2.png      3D renders by kicad-cli
      plot_top.png, plot_bottom.png          copper, solder-mask openings, silkscreen, holes, outline of one side
      labels_top.png, labels_bottom.png      the label view: silkscreen, pads, fabrication drawing and its
                                             references, holes and vias in distinct colours, copper dimmed
      assembly_top.png, assembly_bottom.png  the assembly drawing (fabrication layer) as an image
      layers/copper_<layer>.png              every copper layer alone, with the holes
      tiles/<side>_<tile>_render.png, tiles/<side>_<tile>_labels.png    a grid of zoom tiles over each side at a
                                             readable scale (default 40 px/mm: 1.0 mm text is 40 px high)
      holes/<ref>_...png                     every mounting hole: top-down render, angled render, both sides'
                                             plots, every inner copper layer
      connectors/<ref>_...png                every connector: top-down render, angled render from outside the
                                             board, label view (both sides for a through-hole connector)
      flags/<name>_...png                    every location flagged by silk_check.py (and edge_check.py)
      panel_*.png                            render and plot of the panel, when the project has one
      Edge keep-out bands of the project (a board that slides in slots or rails; see pcb_common.edge_bands) are
      drawn in magenta, with their name and width, on the plots, label views, assembly drawings, contact sheets
      and on every tile, hole, connector and flag crop of the sides they apply to. The whole-board renders and
      the single copper layers are left as they are.
      contact_top.png, contact_bottom.png    the whole side with the tile grid and tile names drawn on it
      index.md                               the contact sheet: every file, what it shows, where it is
      index.json                             the same as data, with the list of the images this run wrote. The next
                                             run deletes exactly those images first and nothing else: images that
                                             other scripts put into the review folder stay
      designators.csv                        reference, side, x, y, value (then rotation, footprint, dnp, tile)
    From production files alone (--gerbers <folder>, no board): every Gerber layer and the drill files drawn to
    PNG (copper, mask, silkscreen and outline in different colours), one image per layer, one stacked view per
    side, and the same grid of zoom tiles. What cannot be drawn exactly is said in index.md, never drawn wrong.
    (No designators, no renders and no edge bands in this mode: there is no board to take them from.)

Why it exists (the real failures, told without names)
    A first 3D look at a board can find labels on top of other parts, a crowded information block or a hole
    partly covered by a connector, none of which a check has seen. Reviewers who were given whole-board images
    could not read the designators; reviewers who were given tiles could. So the image
    set is made the same way every time, at a scale where every designator is readable, and every crop has a
    name a finding can cite. Scripts add to looking; they never replace it.

How it works
    The board is copied to a private folder; nothing is written beside the design. Renders come from
    `kicad-cli pcb render` (several at once). The plots are drawn by this script from the Gerber and drill
    files that kicad-cli exports from the copy, with the Gerber reader of edge_check.py, so they show what the
    factory files hold, at any scale, without another program. Render tiles are cut from one high-resolution
    top-down render per side; the position of the board in that render is found from a second render of the
    bare board (same camera, no 3D models) and checked. Bottom views are mirrored: as seen from the bottom.
    Coordinates in names and tables are KiCad's (mm, x to the right, y down).

Usage
    python -I review_images.py --project <hardware/board folder>             images in <project>/out/review/
    python -I review_images.py <board.kicad_pcb> --out <folder> [--panel <panel.kicad_pcb>] [--flags a.json ...]
    python -I review_images.py --gerbers <folder> --out <folder>             production files alone
    options: --px-per-mm N, --tile-mm N, --fast (basic render quality), --no-render, --jobs N

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [review]
    px_per_mm = 40           # scale of the tiles
    tile_mm = 24             # core size of a grid tile (tiles overlap by overlap_mm on every side)
    overlap_mm = 2
    quality = "high"         # render quality: "high" or "basic"
    max_render_mp = 16       # largest top-down render in megapixels (a larger board gets a coarser render scale)
    [holes] refs, min_d      which footprints are mounting holes (see pcb_common.py)
    [connectors] refs        reference patterns of connectors (default J*, P*, CN*, CON*, X*, USB*)
    [panel] board = "kicad/name-panel.kicad_pcb"       the panel's board file (default: *panel*.kicad_pcb beside the board;
                             without one there, the one board in <results folder>/panel/board/, where panel.py writes it)
    [[keepout.band]] ...     edge keep-out bands (or the "keepouts" of mech/outline.json): drawn on the images

Exit codes
    0  the complete image set was made
    1  some images could not be made or a layer could not be drawn exactly: index.md lists them
    2  CANNOT RUN: KiCad or Pillow not found, unreadable board, no Gerber files. Never a pass.

Not done here: the looking. Open the images and write what you saw, with the crop names.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import csv
import glob
import json
import math
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
import edge_check as gbr  # noqa: E402

DEFAULTS = {"px_per_mm": 40.0, "tile_mm": 24.0, "overlap_mm": 2.0, "quality": "high", "max_render_mp": 16.0}
FIT = 0.9 * 0.95                    # share of the image height that the board's height fills (then calibrated):
                                    # kicad-cli fits the board's LARGER side to the image height, so the zoom is
                                    # 0.9 * larger side / height (see fit_zoom)
MARGIN = 1.5                        # mm of space around the board in the plots
SS = 2                              # supersampling of the drawings
MAX_PLOT_MP = 40.0                  # largest whole-board drawing in megapixels
RENDER_TIMEOUT = 1800.0

BG = (22, 30, 27)
C_SILK, C_FAB, C_EDGE, C_DRILL = (255, 247, 140), (95, 175, 235), (190, 190, 190), (250, 250, 250)
C_MASK, C_PASTE, C_CRTYD = (240, 170, 70), (170, 170, 170), (200, 110, 200)
C_BAND = (255, 40, 235)             # edge keep-out bands
C_TOP, C_BOT = (205, 55, 55), (60, 100, 215)
C_INNER = [(50, 165, 90), (165, 85, 200), (215, 140, 45), (60, 170, 175), (150, 150, 60), (200, 90, 140)]


def _pil():
    kicad_io.add_user_site()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise kicad_io.KicadIOError("the Pillow library is needed to draw images (pip install pillow)") from None
    Image.MAX_IMAGE_PIXELS = None
    return Image, ImageDraw, ImageFont


# ---- drawing Gerber layers -------------------------------------------------------------------------------------------
def _boxes(layer):
    """Bounding box of every item of a layer (kept on the layer)."""
    if getattr(layer, "_boxes", None) is None:
        bs = []
        for it in layer.items:
            if it[0] == "poly":
                xs, ys = [p[0] for p in it[1]], [p[1] for p in it[1]]
                bs.append((min(xs), min(ys), max(xs), max(ys)))
            elif it[0] == "circ":
                bs.append((it[1] - it[3], it[2] - it[3], it[1] + it[3], it[2] + it[3]))
            else:
                r = it[5]
                bs.append((min(it[1], it[3]) - r, min(it[2], it[4]) - r, max(it[1], it[3]) + r, max(it[2], it[4]) + r))
        layer._boxes = bs
    return layer._boxes


def layer_mask(layer, view, ppm, mirror, min_px=1.0):
    """One Gerber layer as a grey image (255 where it draws). view: (x0, y0, x1, y1) in the file's frame (y up)."""
    Image, ImageDraw, _ = _pil()
    x0, y0, x1, y1 = view
    w, h = max(1, int(round((x1 - x0) * ppm))), max(1, int(round((y1 - y0) * ppm)))
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)

    def px(x, y):
        return (((x1 - x) if mirror else (x - x0)) * ppm, (y1 - y) * ppm)

    for it, b in zip(layer.items, _boxes(layer)):
        if b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1:
            continue
        fill = 255 if it[-1] else 0
        if it[0] == "poly":
            if len(it[1]) >= 3:
                dr.polygon([px(*p) for p in it[1]], fill=fill)
        elif it[0] == "circ":
            cx, cy = px(it[1], it[2])
            r = max(it[3] * ppm, min_px / 2)
            dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
        else:
            a, c = px(it[1], it[2]), px(it[3], it[4])
            wd = max(2 * it[5] * ppm, min_px)
            dr.line([a, c], fill=fill, width=max(1, int(round(wd))))
            if wd >= 3:
                r = wd / 2
                dr.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), fill=fill)
                dr.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=fill)
    return im


def drill_mask(drills, view, ppm, mirror):
    Image, ImageDraw, _ = _pil()
    x0, y0, x1, y1 = view
    w, h = max(1, int(round((x1 - x0) * ppm))), max(1, int(round((y1 - y0) * ppm)))
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)

    def px(x, y):
        return (((x1 - x) if mirror else (x - x0)) * ppm, (y1 - y) * ppm)

    for d in drills:
        for hx, hy, dia in d.holes:
            if x0 - dia <= hx <= x1 + dia and y0 - dia <= hy <= y1 + dia:
                cx, cy = px(hx, hy)
                r = max(dia / 2 * ppm, 0.7)
                dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        for ax, ay, bx, by, dia in d.slots:
            a, c = px(ax, ay), px(bx, by)
            wd = max(dia * ppm, 1.0)
            dr.line([a, c], fill=255, width=max(1, int(round(wd))))
            r = wd / 2
            dr.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), fill=255)
            dr.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=255)
    return im


def compose(stack, view, ppm, mirror, bg=BG):
    """Draw a stack of (layer or drill list, colour, opacity, minimum line px) onto one RGB image."""
    Image, _, _ = _pil()
    s = ppm * SS
    x0, y0, x1, y1 = view
    size = (max(1, int(round((x1 - x0) * s))), max(1, int(round((y1 - y0) * s))))
    img = Image.new("RGB", size, bg)
    for what, colour, alpha, min_px in stack:
        if what is None:
            continue
        m = drill_mask(what, view, s, mirror) if isinstance(what, list) else layer_mask(what, view, s, mirror, min_px * SS)
        if alpha < 1.0:
            m = m.point(lambda v, a=alpha: int(v * a))
        img.paste(colour, (0, 0, size[0], size[1]), m)
    return img.resize((max(1, size[0] // SS), max(1, size[1] // SS)), Image.LANCZOS)


def caption(img, text):
    """The image with a strip of text under it."""
    Image, ImageDraw, ImageFont = _pil()
    try:
        font = ImageFont.load_default(size=15)
    except TypeError:                                                   # an older Pillow: its fixed small font
        font = ImageFont.load_default()
    out = Image.new("RGB", (img.width, img.height + 24), (255, 255, 255))
    out.paste(img.convert("RGB"), (0, 0))
    ImageDraw.Draw(out).text((6, img.height + 3), text, fill=(0, 0, 0), font=font)
    return out


def _font(size):
    _, _, ImageFont = _pil()
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_bands(img, bands, side, kbox, scale):
    """The edge keep-out bands of one side over a drawing or a render crop: a translucent magenta area with its
    outline, and the band's name and width as outlined text. The text is put outside the board, beside the band,
    when that is in view, so that it hides nothing of the band; otherwise inside it. kbox: the view in KiCad's
    frame (mm); the bottom side is mirrored, as the drawings are. Returns the image (the same one when no band
    is in view)."""
    Image, ImageDraw, _ = _pil()
    mirror = side == "bottom"
    out = None
    for b in bands:
        bb = b["box"]
        if b["sides"] not in ("both", side) or bb[2] < kbox[0] or bb[0] > kbox[2] or bb[3] < kbox[1] or bb[1] > kbox[3]:
            continue
        if out is None:
            out = img.convert("RGB")

        def px(x, y):
            return (((kbox[2] - x) if mirror else (x - kbox[0])) * scale, (y - kbox[1]) * scale)
        pts = [px(*q) for q in b["poly"]]
        x0, y0 = max(0, int(min(q[0] for q in pts)) - 2), max(0, int(min(q[1] for q in pts)) - 2)
        x1, y1 = min(out.width, int(max(q[0] for q in pts)) + 3), min(out.height, int(max(q[1] for q in pts)) + 3)
        if x1 <= x0 or y1 <= y0:
            continue
        part = out.crop((x0, y0, x1, y1)).convert("RGBA")
        ov = Image.new("RGBA", part.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        local = [(q[0] - x0, q[1] - y0) for q in pts]
        dr.polygon(local, fill=C_BAND + (70,))
        dr.line(local + [local[0]], fill=C_BAND + (255,), width=max(2, int(scale / 12)))
        out.paste(Image.alpha_composite(part, ov).convert("RGB"), (x0, y0))
        # the name: white letters with a black rim, readable on any ground
        text = f"{b['name']}: keep-out {b['width']:g} mm"
        font = _font(int(max(11, min(24, 0.45 * b["width"] * scale))))
        tb = dr.textbbox((0, 0), text, font=font, stroke_width=2)
        label = Image.new("RGBA", (tb[2] - tb[0] + 4, tb[3] - tb[1] + 4), (0, 0, 0, 0))
        ImageDraw.Draw(label).text((2 - tb[0], 2 - tb[1]), text, fill=(255, 255, 255, 255), font=font, stroke_width=2,
                                   stroke_fill=(0, 0, 0, 255))
        nx, ny = (-b["n"][0] if mirror else b["n"][0]), b["n"][1]      # into the board, in the picture
        if abs(nx) > abs(ny):                                           # a band along a vertical edge: the name reads upward
            label = label.rotate(90, expand=True)
        tx, ty = (x0 + x1 - label.width) // 2, (y0 + y1 - label.height) // 2
        if abs(nx) > 0.99:
            ox = x0 - label.width - 2 if nx > 0 else x1 + 2
            tx = ox if 0 <= ox <= out.width - label.width else tx
        elif abs(ny) > 0.99:
            oy = y0 - label.height - 2 if ny > 0 else y1 + 2
            ty = oy if 0 <= oy <= out.height - label.height else ty
        tx, ty = max(0, min(tx, out.width - label.width)), max(0, min(ty, out.height - label.height))
        if label.width <= out.width and label.height <= out.height:
            spot = out.crop((tx, ty, tx + label.width, ty + label.height)).convert("RGBA")
            out.paste(Image.alpha_composite(spot, label).convert("RGB"), (tx, ty))
    return img if out is None else out


class Layers:
    """The Gerber layers and drill files of one board, by role."""

    def __init__(self):
        self.copper = {}            # name -> Layer, in stack order
        self.side = {"top": {}, "bottom": {}}       # side -> {"silk", "mask", "fab", "crtyd", "paste", "copper"}
        self.outline = None
        self.drills = []
        self.other = {}             # file name -> Layer
        self.notes = []             # what could not be read or drawn exactly
        self.files = []             # (file name, role) for the index

    def stack(self, kind, side):
        s = self.side[side]
        cu_col = C_TOP if side == "top" else C_BOT
        if kind == "plot":
            return [(s.get("copper"), cu_col, 0.9, 1), (s.get("mask"), C_MASK, 0.85, 1), (s.get("silk"), C_SILK, 1.0, 1.5),
                    (self.drills, C_DRILL, 1.0, 1), (self.outline, C_EDGE, 1.0, 2)]
        if kind == "labels":
            return [(s.get("copper"), (120, 72, 72) if side == "top" else (70, 84, 130), 0.55, 1),
                    (s.get("mask"), C_MASK, 0.9, 1), (s.get("fab"), C_FAB, 0.8, 1.2), (s.get("silk"), C_SILK, 1.0, 1.5),
                    (self.drills, C_DRILL, 1.0, 1), (self.outline, C_EDGE, 1.0, 2)]
        if kind == "assembly":
            return [(s.get("mask"), (222, 222, 222), 1.0, 1), (s.get("crtyd"), C_CRTYD, 0.8, 1.2),
                    (s.get("fab"), (0, 0, 0), 1.0, 1.8), (self.drills, (150, 150, 150), 1.0, 1), (self.outline, (0, 0, 0), 1.0, 2.5)]
        raise ValueError(kind)

    def copper_stack(self, name):
        names = list(self.copper)
        i = names.index(name)
        col = C_TOP if i == 0 else C_BOT if i == len(names) - 1 and len(names) > 1 else C_INNER[(i - 1) % len(C_INNER)]
        return [(self.copper[name], col, 1.0, 1), (self.drills, C_DRILL, 1.0, 1), (self.outline, C_EDGE, 1.0, 2)]


def load_layers(folder, kicad_names=None) -> Layers:
    """Read every Gerber and drill file of a folder into a Layers object. kicad_names: {file suffix: layer name}
    for files exported by this script; otherwise the files' attributes and names decide."""
    found = gbr.find_files(folder)
    L = Layers()
    inner = []
    for path, kind, side, lay, err in found["gerbers"]:
        name = os.path.basename(path)
        if lay is None:
            L.notes.append(f"`{name}` could not be read and is NOT drawn: {err}")
            L.files.append((name, "not readable"))
            continue
        for n in lay.notes:
            L.notes.append(f"`{name}`: {n}")
        if kind == "copper" and lay.attrs.get("FilePolarity", "").strip().lower().startswith("negative"):
            L.notes.append(f"`{name}` is a negative image (a plane layer): what is drawn is where copper is REMOVED")
        role = kind + (" " + side if side else "")
        if kind == "outline":
            if L.outline is None:
                L.outline = lay
            else:
                L.other[name] = lay
                role = "outline (second file, drawn alone)"
        elif kind == "copper" and side in ("top", "bottom"):
            L.side[side]["copper"] = lay
        elif kind == "copper":
            inner.append((name, lay))
        elif kind in ("silk", "mask", "paste", "fab") and side in ("top", "bottom"):
            L.side[side][kind] = lay
        elif kind == "drillmap":
            L.other[name] = lay
        else:
            m = re.search(r"([fb])[._](courtyard|crtyd)", name.lower())
            if m:
                L.side["top" if m.group(1) == "f" else "bottom"]["crtyd"] = lay
                role = "courtyard " + ("top" if m.group(1) == "f" else "bottom")
            else:
                L.other[name] = lay
        L.files.append((name, role))

    def inner_key(t):
        m = re.search(r"in(\d+)|l(\d+)|\.g(\d+)$|\.gp(\d+)$|(\d+)", t[0].lower())
        ff = t[1].attrs.get("FileFunction", "")
        m2 = re.search(r"L(\d+)", ff)
        return int(m2.group(1)) if m2 else int(next(g for g in m.groups() if g)) if m else 0

    if "copper" in L.side["top"]:
        L.copper[_layer_label(L.side["top"]["copper"], "top")] = L.side["top"]["copper"]
    for name, lay in sorted(inner, key=inner_key):
        L.copper[_layer_label(lay, os.path.splitext(name)[0])] = lay
    if "copper" in L.side["bottom"]:
        L.copper[_layer_label(L.side["bottom"]["copper"], "bottom")] = L.side["bottom"]["copper"]
    for path, drill, err in found["drills"]:
        name = os.path.basename(path)
        if drill is None:
            L.notes.append(f"`{name}` could not be read and is NOT drawn: {err}")
            L.files.append((name, "drill, not readable"))
            continue
        L.drills.append(drill)
        for n in drill.notes:
            L.notes.append(f"`{name}`: {n}")
        plated = {True: "plated", False: "not plated", None: "plating unknown"}[drill.plated]
        L.files.append((name, f"drill ({plated}): {len(drill.holes)} holes, {len(drill.slots)} slots"))
    return L


def _layer_label(lay, fallback):
    m = re.search(r"-((?:F|B|In\d+)_Cu)\.", lay.name)
    return m.group(1).replace("_", ".") if m else fallback


def full_view(L: Layers, bbox=None):
    """The view box (file frame) of a whole board: the outline's box, else the box of everything, plus a margin."""
    b = bbox
    if b is None and L.outline is not None:
        b = L.outline.bbox()
    if b is None:
        boxes = [lay.bbox() for lay in list(L.copper.values()) + list(L.other.values()) if lay.bbox()]
        if not boxes:
            raise kicad_io.KicadIOError("the Gerber files draw nothing")
        b = pcb_common.box_union(boxes)
    return (b[0] - MARGIN, b[1] - MARGIN, b[2] + MARGIN, b[3] + MARGIN)


def plot_scale(view, ppm):
    """The scale for a whole-board drawing: ppm, or less when the image would pass MAX_PLOT_MP."""
    mp = (view[2] - view[0]) * (view[3] - view[1]) * ppm * ppm / 1e6
    return ppm if mp <= MAX_PLOT_MP else ppm * math.sqrt(MAX_PLOT_MP / mp)


def grid(bbox, tile, overlap):
    """Tiles over a box: [(name, core box, drawn box)], rows A, B ... from the top, columns 1, 2 ... from the left."""
    x0, y0, x1, y1 = bbox
    nc = max(1, math.ceil((x1 - x0) / tile - 1e-6))
    nr = max(1, math.ceil((y1 - y0) / tile - 1e-6))
    cw, rh = (x1 - x0) / nc, (y1 - y0) / nr
    out = []
    for r in range(nr):
        letters = chr(65 + r) if nr <= 26 else chr(65 + r // 26) + chr(65 + r % 26)
        for c in range(nc):
            core = (x0 + c * cw, y0 + r * rh, x0 + (c + 1) * cw, y0 + (r + 1) * rh)
            drawn = (core[0] - overlap, core[1] - overlap, core[2] + overlap, core[3] + overlap)
            out.append((f"{letters}{c + 1}", core, drawn))
    return out


def k2g(box):
    """A KiCad-frame box (y down) as a Gerber-frame box (y up) of KiCad's own Gerber export."""
    return (box[0], -box[3], box[2], -box[1])


# ---- renders ---------------------------------------------------------------------------------------------------------
def strip_models(text: str) -> str:
    """The board text without any (model ...) block: the bare board."""
    out, i = [], 0
    while True:
        j = text.find("(model ", i)
        if j < 0:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:j])
        depth, k = 0, j
        while k < len(text):
            c = text[k]
            if c == '"':
                k += 1
                while text[k] != '"':
                    k += 2 if text[k] == "\\" else 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        i = k + 1


def clone(copy: str, tmp: str, tag: str, bare: bool = False) -> str:
    """A further private copy of the working copy for one kicad-cli process."""
    d = os.path.join(tmp, tag)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, os.path.basename(copy))
    base = copy[:-len(".kicad_pcb")]
    for ext in (".kicad_pro", ".kicad_dru"):
        if os.path.isfile(base + ext):
            shutil.copyfile(base + ext, dst[:-len(".kicad_pcb")] + ext)
    if bare:
        with open(copy, encoding="utf-8", newline="") as f:
            txt = f.read()
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(strip_models(txt))
    else:
        shutil.copyfile(copy, dst)
    return dst


def fit_zoom(bw: float, bh: float) -> str:
    """The --zoom at which a board of bw x bh mm fills FIT of the height of a top-down render."""
    return f"{0.9 * max(bw, bh) / bh:.4f}"


def render(board: str, png: str, args: list[str], quality: str) -> str:
    """One kicad-cli render; returns '' or the reason it failed."""
    try:
        r = kicad_io.run_cli(["pcb", "render", "-o", png, "--quality", quality] + args + [board], timeout=RENDER_TIMEOUT)
    except kicad_io.KicadIOError as e:
        return str(e)
    if r.returncode != 0 or not os.path.isfile(png):
        return ((r.stdout or "") + (r.stderr or "")).strip()[-300:] or f"exit code {r.returncode}"
    return ""


def flatten(img):
    """An RGBA render on a light background, as RGB: the same picture in every viewer."""
    Image, _, _ = _pil()
    if img.mode != "RGBA":
        return img.convert("RGB")
    bg = Image.new("RGBA", img.size, (232, 233, 238, 255))
    return Image.alpha_composite(bg, img).convert("RGB")


class Calibration:
    """Where the board lies in a top-down render: found from a render of the bare board with the same camera."""

    def __init__(self, bare_png, bbox, side):
        Image, _, _ = _pil()
        im = Image.open(bare_png)
        self.ok, self.why = False, ""
        if im.mode != "RGBA":
            self.why = "the bare-board render has no transparent background"
            return
        bb = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        if not bb:
            self.why = "the bare-board render is empty"
            return
        self.left, self.top = bb[0], bb[1]
        self.sx = (bb[2] - bb[0]) / (bbox[2] - bbox[0])
        self.sy = (bb[3] - bb[1]) / (bbox[3] - bbox[1])
        self.bbox, self.side, self.size = bbox, side, im.size
        if abs(self.sx - self.sy) / self.sx > 0.01:
            self.why = f"the bare-board render gives two scales ({self.sx:.2f} and {self.sy:.2f} px/mm)"
            return
        self.ok = True

    def px(self, x, y):
        fx = (self.bbox[2] - x) if self.side == "bottom" else (x - self.bbox[0])
        return self.left + fx * self.sx, self.top + (y - self.bbox[1]) * self.sy

    def crop(self, img, box):
        (ax, ay), (bx, by) = self.px(box[0], box[1]), self.px(box[2], box[3])
        l, r = sorted((ax, bx))
        return img.crop((int(round(l)), int(round(ay)), int(round(r)), int(round(by))))

    def check(self, img, holes):
        """Compare with the real render: unplated holes that are see-through in the bare render must be at the
        same pixels in the real one (parts may cover some). Returns (n same, n tested)."""
        a = img.getchannel("A") if img.mode == "RGBA" else None
        if a is None:
            return 0, 0
        same = tested = 0
        for h in holes:
            x, y = self.px(h["x"], h["y"])
            if 0 <= x < img.width and 0 <= y < img.height:
                tested += 1
                same += 1 if a.getpixel((int(x), int(y))) < 250 else 0      # a hole shows the background (or its shadow)
        return same, tested


def view_angle(x, y, bbox):
    """Rotation about the vertical axis (degrees) that turns the board edge nearest to (x, y) toward the camera."""
    d = {"left": x - bbox[0], "right": bbox[2] - x, "rear": y - bbox[1], "front": bbox[3] - y}
    near = sorted(d, key=d.get)
    vx = (-1 if near[0] == "left" else 1 if near[0] == "right" else 0)
    vy = (1 if near[0] == "rear" else -1 if near[0] == "front" else 0)
    if d[near[1]] < 1.5 * d[near[0]] + 2.0 and {near[0], near[1]} not in ({"left", "right"}, {"front", "rear"}):
        vx += (-1 if near[1] == "left" else 1 if near[1] == "right" else 0)       # a corner: look along the diagonal
        vy += (1 if near[1] == "rear" else -1 if near[1] == "front" else 0)
    return math.degrees(math.atan2(-vx, -vy))


# ---- the board mode --------------------------------------------------------------------------------------------------
def export_production(copy: str, tmp: str, layers: list[str]) -> tuple[str, list[str]]:
    """Gerbers of the given layers and the drill files of a board copy, into one folder. Returns (folder, problems)."""
    out = os.path.join(tmp, "gerbers")
    os.makedirs(out, exist_ok=True)
    problems = []
    try:
        kicad_io.run_cli(["pcb", "export", "gerbers", "-o", out + os.sep, "--layers", ",".join(layers), "--no-protel-ext",
                          clone(copy, tmp, "exp_g")], check=True)
    except kicad_io.KicadIOError as e:
        problems.append(f"Gerber export failed: {e}")
    try:
        kicad_io.run_cli(["pcb", "export", "drill", "-o", out + os.sep, "--format", "excellon", "--excellon-units", "mm",
                          "--excellon-separate-th", clone(copy, tmp, "exp_d")], check=True)
    except kicad_io.KicadIOError as e:
        problems.append(f"drill export failed: {e}")
    return out, problems


def find_panel(job, a):
    if a.panel:
        return os.path.abspath(a.panel)
    cfg = job.cfg("panel")
    if cfg.get("board"):
        return job.path(cfg["board"])
    if job.project:
        base = os.path.basename(job.board).lower()
        c = [p for p in glob.glob(os.path.join(glob.escape(os.path.dirname(job.board)), "*.kicad_pcb"))
             if "panel" in os.path.basename(p).lower() and os.path.basename(p).lower() != base]
        if not c:                                   # where panel.py writes it: <results folder>/panel/board/
            out = kicad_io.project_files(job.project, job.settings)["out"]
            c = glob.glob(os.path.join(glob.escape(out), "panel", "board", "*.kicad_pcb"))
        if len(c) == 1:
            return c[0]
    return None


def read_flags(paths):
    flags, problems = [], []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            problems.append(f"flag file `{os.path.basename(p)}` not readable: {e}")
            continue
        for c in data.get("crops", []):
            if isinstance(c, dict) and "x" in c and "y" in c:
                c = dict(c)
                c["source"] = os.path.basename(p)
                flags.append(c)
    return flags, problems


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", str(s)).strip("_") or "x"


def remove_own(out: str) -> None:
    """Delete the images that an earlier run of this script wrote into `out` (they are listed in its index.json)
    and nothing else: other scripts put images of their own into the review folder, and those stay."""
    try:
        with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(old, dict) or not str(old.get("script", "")).startswith("review_images.py"):
        return
    root = os.path.abspath(out)
    for img in old.get("images", []):
        path = os.path.abspath(os.path.join(root, str(img.get("file", "")) if isinstance(img, dict) else ""))
        if path.startswith(root + os.sep) and path.lower().endswith(".png"):
            try:
                os.remove(path)
            except OSError:
                pass


def board_mode(job, a, lim) -> int:
    Image, ImageDraw, _ = _pil()
    out = os.path.join(job.out, "review")
    remove_own(out)
    for sub in ("tiles", "holes", "connectors", "flags", "layers"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    t0 = time.monotonic()
    quality = "basic" if a.fast else lim["quality"]
    problems, notes, made = [], [], []          # made: (section, file, what)
    jobs_n = a.jobs or max(2, (os.cpu_count() or 4) // 2)
    panel = find_panel(job, a)
    with kicad_io.private_tmp("review-images-") as tmp, pcb_common.work_copy(job.board) as copy, \
            ThreadPoolExecutor(max_workers=jobs_n) as pool:
        info = pcb_common.read_board(clone(copy, tmp, "dump"), os.path.dirname(job.board))
        bbox = tuple(info["bbox"])
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if bw <= 0 or bh <= 0:
            raise kicad_io.KicadIOError("the board has no size (no outline and no items)")
        if not info["outline"]["ok"]:
            notes.append(f"Board outline: {info['outline']['note']}; the box of the Edge.Cuts drawing is used.")
        bands, band_src = pcb_common.edge_bands(job, bbox)
        cu = info["copper_layers"]
        want = cu + ["F.Silkscreen", "B.Silkscreen", "F.Mask", "B.Mask", "F.Fab", "B.Fab", "F.Courtyard", "B.Courtyard",
                     "Edge.Cuts"]
        f_exp = pool.submit(export_production, copy, tmp, want)
        # ---- renders, all submitted at once
        ppm = lim["px_per_mm"]
        rppm = min(ppm, math.sqrt(lim["max_render_mp"] * 1e6 * FIT * FIT / (bw * bh)))
        rw, rh = int(bw * rppm / FIT) + 16, int(bh * rppm / FIT) + 32
        renders = {}
        holes = [f for f in info["footprints"] if pcb_common.is_mounting_hole(f, job.cfg("holes"))]
        conns = [f for f in info["footprints"] if pcb_common.is_connector(f, job.cfg("connectors")) and f not in holes]
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2

        def angled(tag, x, y, span, bottom):
            zoom = max(1.0, max(bw, bh) / max(34.0, 2.0 * span))
            rot = f"{125 if bottom else -55},0,{view_angle(x, y, bbox):.0f}"
            return ["-w", "1000", "-h", "1000", "--background", "opaque", "--perspective", "--zoom", f"{zoom:.2f}",
                    "--rotate", rot, "--pivot", f"{(x - cx) / 10:.3f},{-(y - cy) / 10:.3f},0"]

        if not a.no_render:
            top_args = ["-w", str(rw), "-h", str(rh), "--background", "transparent", "--zoom", fit_zoom(bw, bh)]
            for side in ("top", "bottom"):
                renders[f"render_{side}"] = pool.submit(render, clone(copy, tmp, f"r_{side}"), os.path.join(out, f"render_{side}.png"),
                                                        top_args + ["--side", side], quality)
                renders[f"bare_{side}"] = pool.submit(render, clone(copy, tmp, f"b_{side}", bare=True),
                                                      os.path.join(tmp, f"bare_{side}.png"), top_args + ["--side", side], "basic")
            iso_w, iso_h = (2400, 1500) if bw >= bh else (1500, 2400)
            for name, rot in (("render_angle1", "-50,0,35"), ("render_angle2", "-50,0,215")):
                renders[name] = pool.submit(render, clone(copy, tmp, name), os.path.join(out, name + ".png"),
                                            ["-w", str(iso_w), "-h", str(iso_h), "--background", "opaque", "--perspective",
                                             "--rotate", rot], quality)
            for f in holes:
                tag = f"holes/{safe_name(f['ref'])}_angled"
                renders[tag] = pool.submit(render, clone(copy, tmp, safe_name(tag)), os.path.join(out, tag + ".png"),
                                           angled(tag, f["x"], f["y"], 10.0, False), quality)
            for f in conns:
                b = f["box"]
                tag = f"connectors/{safe_name(f['ref'])}_angled"
                renders[tag] = pool.submit(render, clone(copy, tmp, safe_name(tag)), os.path.join(out, tag + ".png"),
                                           angled(tag, (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(b[2] - b[0], b[3] - b[1]),
                                                  f["side"] == "bottom"), quality)
        f_panel = None
        if panel:
            if not os.path.isfile(panel):
                problems.append(f"the panel board `{panel}` does not exist")
                panel = None
            else:
                f_panel = pool.submit(panel_images, panel, out, tmp, quality, a.no_render, lim["px_per_mm"])
        # ---- plots from the exported production files
        gfolder, exp_problems = f_exp.result()
        problems += exp_problems
        L = load_layers(gfolder)
        problems += [n for n in L.notes]
        gview = full_view(L, k2g(bbox))
        kview = (gview[0], -gview[3], gview[2], -gview[1])
        fppm = plot_scale(gview, ppm)
        if fppm < ppm:
            notes.append(f"Whole-board drawings are at {fppm:.1f} px/mm (the board is large); the tiles are at {ppm:.0f} px/mm.")
        tiles = grid(bbox, lim["tile_mm"], lim["overlap_mm"])
        nrow = len({t[0].rstrip("0123456789") for t in tiles})
        ncol = len(tiles) // nrow

        def save(img, rel, section, what):
            p = os.path.join(out, rel.replace("/", os.sep))
            img.save(p)
            made.append((section, rel, what))

        def draw_job(kind, side, kbox, scale, rel, section, what, cap=None):
            img = compose(L.stack(kind, side), k2g(kbox), scale, side == "bottom", (255, 255, 255) if kind == "assembly" else BG)
            img = draw_bands(img, bands, side, kbox, scale)
            save(caption(img, cap) if cap else img, rel, section, what)

        draws = []
        for side in ("top", "bottom"):
            mir = " (mirrored: as seen from the bottom)" if side == "bottom" else ""
            draws.append(pool.submit(draw_job, "plot", side, kview, fppm, f"plot_{side}.png", "whole",
                                     f"{side}: copper, mask openings (orange), silkscreen (yellow), holes (white), outline{mir}"))
            draws.append(pool.submit(draw_job, "labels", side, kview, fppm, f"labels_{side}.png", "whole",
                                     f"{side} label view: silkscreen (yellow), pads (orange), fabrication drawing and "
                                     f"references (blue), holes and vias (white), copper dimmed{mir}"))
            draws.append(pool.submit(draw_job, "assembly", side, kview, fppm, f"assembly_{side}.png", "whole",
                                     f"{side} assembly drawing: fabrication layer (black), courtyards (violet), pads (grey){mir}"))
            for name, core, drawn in tiles:
                capt = (f"{side} {name} labels | x {drawn[0]:.1f}..{drawn[2]:.1f}  y {drawn[1]:.1f}..{drawn[3]:.1f} mm "
                        f"(KiCad) | {ppm:.0f} px/mm" + (" | mirrored" if side == "bottom" else ""))
                draws.append(pool.submit(draw_job, "labels", side, drawn, ppm, f"tiles/{side}_{name}_labels.png",
                                         f"tile {side}", "label view", capt))
        for name in L.copper:
            def cu_job(name=name):
                img = compose(L.copper_stack(name), gview, fppm, name == list(L.copper)[-1] and len(L.copper) > 1)
                save(img, f"layers/copper_{safe_name(name)}.png", "layers",
                     f"copper layer {name} alone, with the holes" + (" (mirrored)" if name == list(L.copper)[-1] and len(L.copper) > 1 else ""))
            draws.append(pool.submit(cu_job))
        # holes and connectors: plots
        for f in holes:
            hb = (f["x"] - 9, f["y"] - 9, f["x"] + 9, f["y"] + 9)
            ref = safe_name(f["ref"])
            for side in ("top", "bottom"):
                capt = f"{f['ref']} {side} plot | centre ({f['x']:.2f}, {f['y']:.2f}) | 18 mm window"
                draws.append(pool.submit(draw_job, "plot", side, hb, 55.0, f"holes/{ref}_plot_{side}.png", "hole " + f["ref"],
                                         f"{side} plot around the hole", capt))
            for name in list(L.copper)[1:-1]:
                def in_job(name=name, hb=hb, ref=ref, f=f):
                    img = compose(L.copper_stack(name), k2g(hb), 55.0, False)
                    save(caption(img, f"{f['ref']} copper {name} | 18 mm window"), f"holes/{ref}_copper_{safe_name(name)}.png",
                         "hole " + f["ref"], f"inner copper layer {name} around the hole")
                draws.append(pool.submit(in_job))
        for f in conns:
            b = f["box"]
            m = 4.0
            cb = (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
            span = max(cb[2] - cb[0], cb[3] - cb[1])
            sc = min(60.0, max(ppm, 1100.0 / span)) if span * ppm < 1100 else min(ppm, 2200.0 / span)
            sides = [f["side"]] + ([("bottom" if f["side"] == "top" else "top")] if f["kind"] == "tht" or
                                   any(p["drill"] for p in f["pads"]) else [])
            for side in sides:
                capt = f"{f['ref']} {side} labels | x {cb[0]:.1f}..{cb[2]:.1f}  y {cb[1]:.1f}..{cb[3]:.1f} mm | {sc:.0f} px/mm"
                draws.append(pool.submit(draw_job, "labels", side, cb, sc, f"connectors/{safe_name(f['ref'])}_labels_{side}.png",
                                         "connector " + f["ref"], f"{side} label view around the connector", capt))
        # flagged locations
        flag_files = [os.path.abspath(p) for p in (a.flags or [])]
        if job.project and not a.flags:
            flag_files = [p for p in (os.path.join(job.out, "silk_check.json"), os.path.join(job.out, "edge_check.json"))
                          if os.path.isfile(p)]
        flags, fl_problems = read_flags(flag_files)
        problems += fl_problems
        flag_rows = []
        for i, c in enumerate(flags):
            x, y = float(c["x"]), float(c["y"])
            if c.get("frame") == "gerber":
                y = -y
            size = float(c.get("size", 8.0))
            fb = (x - size / 2, y - size / 2, x + size / 2, y + size / 2)
            sc = min(140.0, 1000.0 / size)
            name = f"{i + 1:03d}_{safe_name(c.get('name', 'flag'))}"
            sides = [c["side"]] if c.get("side") in ("top", "bottom") else ["top", "bottom"]
            rels = []
            for side in sides:
                rel = f"flags/{name}_labels_{side}.png"
                capt = f"{c.get('name', 'flag')} {side} | centre ({x:.2f}, {y:.2f}) | {size:.0f} mm window | {sc:.0f} px/mm"
                draws.append(pool.submit(draw_job, "labels", side, fb, sc, rel, "flag", str(c.get("why", "")), capt))
                rels.append(rel)
            flag_rows.append((name, c, sides, fb, rels))
        for d in draws:
            try:
                d.result()
            except Exception as e:                                      # one drawing must not stop the others
                problems.append(f"a drawing failed: {type(e).__name__}: {e}")
        # ---- renders: results, calibration, crops
        cal = {}
        for tag, fut in renders.items():
            why = fut.result()
            if why:
                problems.append(f"`{tag}` was not rendered: {why}")
            elif not tag.startswith("bare_"):
                what = {"render_top": "3D render, top, straight down", "render_bottom": "3D render, bottom (mirrored: as seen from the bottom)",
                        "render_angle1": "3D render, angled, from the front left", "render_angle2": "3D render, angled, from the rear right"}
                if tag in what:
                    made.append(("whole", tag + ".png", what[tag]))
                else:
                    kind, ref = tag.split("/")[0], tag.split("/")[1].rsplit("_", 1)[0]
                    made.append((("hole " if kind == "holes" else "connector ") + ref, tag + ".png",
                                 "angled 3D render, seen from outside the board" if kind == "connectors" else "angled 3D render"))
        npth = [h for h in info["holes"] if not h["plated"] and h["d"] >= 1.0]
        for side in ("top", "bottom"):
            png, bare = os.path.join(out, f"render_{side}.png"), os.path.join(tmp, f"bare_{side}.png")
            if a.no_render or not (os.path.isfile(png) and os.path.isfile(bare)):
                continue
            c = Calibration(bare, bbox, side)
            if not c.ok:
                problems.append(f"render tiles of the {side} were not cut: {c.why}")
                continue
            img = Image.open(png)
            if img.size != c.size:
                problems.append(f"render tiles of the {side} were not cut: the two renders differ in size")
                continue
            same, tested = c.check(img, npth)
            notes.append(f"Render scale, {side}: {c.sx:.1f} px/mm (1.0 mm text is {c.sx:.0f} px high); position of the board "
                         f"found from a bare-board render; {same} of {tested} unplated holes are see-through at the "
                         f"predicted pixels" + (" (the others are covered by parts or not checked)." if tested else
                                                " (the board has no unplated hole to check with)."))
            if tested and same == 0:
                problems.append(f"render tiles of the {side}: no unplated hole was found where the calibration predicts "
                                f"it; the crops may be offset: compare a tile with the label view before using them")
            cal[side] = (c, img)
            for name, core, drawn in tiles:
                crop = draw_bands(flatten(c.crop(img, drawn)), bands, side, drawn, c.sx)
                save(caption(crop, f"{side} {name} render | x {drawn[0]:.1f}..{drawn[2]:.1f}  y {drawn[1]:.1f}..{drawn[3]:.1f} mm "
                                   f"(KiCad) | {c.sx:.0f} px/mm" + (" | mirrored" if side == "bottom" else "")),
                     f"tiles/{side}_{name}_render.png", f"tile {side}", "3D render")
            for f in holes:
                hb = (f["x"] - 9, f["y"] - 9, f["x"] + 9, f["y"] + 9)
                save(caption(draw_bands(flatten(c.crop(img, hb)), bands, side, hb, c.sx), f"{f['ref']} {side} render | centre ({f['x']:.2f}, {f['y']:.2f}) | 18 mm window"),
                     f"holes/{safe_name(f['ref'])}_render_{side}.png", "hole " + f["ref"], f"3D render, {side}, straight down")
            for f in conns:
                if f["side"] != side:
                    continue
                b = f["box"]
                cb = (b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4)
                save(caption(draw_bands(flatten(c.crop(img, cb)), bands, side, cb, c.sx), f"{f['ref']} {side} render | x {cb[0]:.1f}..{cb[2]:.1f}  y {cb[1]:.1f}..{cb[3]:.1f} mm"),
                     f"connectors/{safe_name(f['ref'])}_render_{side}.png", "connector " + f["ref"], f"3D render, {side}, straight down")
            for name, c_, sides, fb, rels in flag_rows:
                if side in sides:
                    crop = flatten(c.crop(img, fb))
                    crop = draw_bands(crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS), bands, side, fb, 3 * c.sx)
                    rel = f"flags/{name}_render_{side}.png"
                    save(caption(crop, f"{c_.get('name', 'flag')} {side} render, enlarged 3x"), rel, "flag", "3D render")
                    rels.append(rel)
        # ---- contact sheets
        for side in ("top", "bottom"):
            src = os.path.join(out, f"labels_{side}.png")
            if not os.path.isfile(src):
                continue
            im = Image.open(src).convert("RGB")
            k = min(1.0, 2600.0 / max(im.size))
            im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
            dr = ImageDraw.Draw(im)
            s = fppm * k
            font = _font(max(14, int(min(lim["tile_mm"] * s / 4, 40))))
            for name, core, drawn in tiles:
                xa = (kview[2] - core[2]) * s if side == "bottom" else (core[0] - kview[0]) * s
                xb = (kview[2] - core[0]) * s if side == "bottom" else (core[2] - kview[0]) * s
                ya, yb = (core[1] - kview[1]) * s, (core[3] - kview[1]) * s
                dr.rectangle((xa, ya, xb, yb), outline=(0, 255, 255), width=2)
                dr.text((xa + 6, ya + 4), name, fill=(0, 255, 255), font=font)
            im.save(os.path.join(out, f"contact_{side}.png"))
            made.append(("whole", f"contact_{side}.png", f"{side} label view with the tile grid and the tile names"))
        if f_panel is not None:
            p_made, p_problems = f_panel.result()
            made += p_made
            problems += p_problems
        for side, (c_, img) in cal.items():
            flat = flatten(img)
            img.close()
            flat.save(os.path.join(out, f"render_{side}.png"))
    # ---- designators.csv and index.md
    tile_of = {}
    for f in info["footprints"]:
        tile_of[f["ref"]] = next((n for n, core, _ in tiles if core[0] <= f["x"] <= core[2] and core[1] <= f["y"] <= core[3]), "")
    with kicad_io.atomic_open(os.path.join(out, "designators.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["reference", "side", "x", "y", "value", "rotation", "footprint", "dnp", "tile", "label_on_silkscreen"])
        for f in info["footprints"]:
            w.writerow([f["ref"], f["side"], f"{f['x']:.3f}", f"{f['y']:.3f}", f["value"], f"{f['rot']:.1f}", f["lib"],
                        "yes" if f["dnp"] else "no", tile_of[f["ref"]], "yes" if f["ref_on_silk"] else "no"])
    have = {rel for _, rel, _ in made}
    md = pcb_common.header("Review images: contact sheet", job, "review_images.py")
    md += [f"Board {bw:.2f} x {bh:.2f} mm, {len(cu)} copper layers ({', '.join(cu)}), {len(info['footprints'])} footprints "
           f"({sum(1 for f in info['footprints'] if f['side'] == 'top')} top, "
           f"{sum(1 for f in info['footprints'] if f['side'] == 'bottom')} bottom), {len(holes)} mounting holes, "
           f"{len(conns)} connectors.", "",
           "Coordinates are KiCad's (mm, x to the right, y down). **Bottom views are mirrored: as seen from the bottom.** "
           "The plots are drawn from the Gerber and drill files exported from this board; the renders are KiCad's.",
           "Every designator with its side, position, value and tile: `designators.csv`.", "", "Settings:", ""] + lim.table() + [""]
    md += [f"- {n}" for n in notes] + ([""] if notes else [])
    md += ["## How to use", "",
           "Open the images; a report says what was seen and names the crop file. Start with `contact_top.png` and "
           "`contact_bottom.png`, then go through the tiles of each side: the label view shows what is printed and "
           "where the pads, holes and vias are; the render shows what is visible with the parts fitted.", "",
           "## Whole board", "", "| File | What it shows |", "|---|---|"]
    md += [f"| `{rel}` | {what} |" for sec, rel, what in made if sec == "whole"]
    md += ["", f"## Tiles: {nrow} row(s) A.. from the top (smallest y), {ncol} column(s) 1.. from the left (smallest x)", "",
           f"Core size {(bbox[2] - bbox[0]) / ncol:.1f} x {(bbox[3] - bbox[1]) / nrow:.1f} mm, drawn with {lim['overlap_mm']:.0f} mm "
           f"overlap on every side at {ppm:.0f} px/mm.", "",
           "| Tile | x (mm) | y (mm) | Files (tiles/) | Designators, top | Designators, bottom |", "|---|---|---|---|---|---|"]
    for name, core, drawn in tiles:
        files = [f"{side}_{name}_{v}.png" for side in ("top", "bottom") for v in ("render", "labels")
                 if f"tiles/{side}_{name}_{v}.png" in have]
        refs = {s: " ".join(f["ref"] for f in info["footprints"] if tile_of[f["ref"]] == name and f["side"] == s) or "-"
                for s in ("top", "bottom")}
        md.append(f"| {name} | {core[0]:.1f} .. {core[2]:.1f} | {core[1]:.1f} .. {core[3]:.1f} | "
                  f"{', '.join('`' + x + '`' for x in files)} | {refs['top']} | {refs['bottom']} |")
    for title, items, sec in (("Mounting holes", holes, "hole "), ("Connectors", conns, "connector ")):
        md += ["", f"## {title}", ""]
        if not items:
            md.append("None found" + (" (name them in board.toml [holes] refs)." if sec == "hole " else
                                      " (name their reference patterns in board.toml [connectors] refs)."))
            continue
        md += ["| Reference | Value | Side | Position (mm) | Files |", "|---|---|---|---|---|"]
        for f in items:
            files = [f"`{rel}` ({what})" for s, rel, what in made if s == sec + f["ref"]]
            drill = max((p["drill"][0] for p in f["pads"] if p["drill"]), default=0)
            extra = f", drill {drill:.2f}" if sec == "hole " else ""
            md.append(f"| {f['ref']} | {f['value']} | {f['side']} | ({f['x']:.2f}, {f['y']:.2f}){extra} | {'; '.join(files) or 'none'} |")
    md += ["", "## Flagged locations", ""]
    if not flag_files:
        md.append("No flag file was given (silk_check.py and edge_check.py write them; run those first).")
    elif not flag_rows:
        md.append("The flag files " + ", ".join(f"`{os.path.basename(p)}`" for p in flag_files) + " hold no location.")
    else:
        md += ["| Crop | From | Why | Position (mm) | Files |", "|---|---|---|---|---|"]
        for name, c, sides, fb, rels in flag_rows:
            md.append(f"| {name} | {c['source']} | {c.get('why', '')} | ({(fb[0] + fb[2]) / 2:.2f}, {(fb[1] + fb[3]) / 2:.2f}) | "
                      f"{', '.join('`' + r + '`' for r in rels if r in have)} |")
    md += ["", "## Copper layers", "", "| File | What it shows |", "|---|---|"]
    md += [f"| `{rel}` | {what} |" for sec, rel, what in made if sec == "layers"]
    md += ["", "## Edge keep-out bands", ""]
    if bands:
        md += [f"From {band_src}. Drawn in magenta, with name and width, on the plots, label views, assembly drawings, contact "
               "sheets and on every tile, hole, connector and flag crop of the sides a band applies to; not on the "
               "whole-board renders and not on the single copper layers. Look along each band on both sides: no part "
               "body, courtyard, solder joint, label or exposed copper may lie in it (body_check.py measures it).", "",
               "| Band | Edge | From (x, y) to (x, y), mm | Width (mm) | Sides | Tiles that show it |", "|---|---|---|---|---|---|"]
        for b in bands:
            bb, ln = b["box"], b["line"]
            shown = [n for n, _, d in tiles if not (bb[2] < d[0] or bb[0] > d[2] or bb[3] < d[1] or bb[1] > d[3])]
            md.append(f"| {b['name']} | {b['edge']} | ({ln[0]:.2f}, {ln[1]:.2f}) to ({ln[2]:.2f}, {ln[3]:.2f}) | {b['width']:g} | "
                      f"{b['sides']} | {' '.join(shown) or '-'} |")
    else:
        md.append("None defined (board.toml [[keepout.band]] or the keepouts of mech/outline.json): nothing drawn.")
    md += ["", "## Panel", ""]
    pm = [(rel, what) for sec, rel, what in made if sec == "panel"]
    md += ([f"Panel board `{os.path.basename(panel)}`.", "", "| File | What it shows |", "|---|---|"] +
           [f"| `{rel}` | {what} |" for rel, what in pm]) if pm else ["The project has no panel board (or none was named)."]
    md += ["", "## Not made, or not drawn exactly", ""]
    md += [f"- {p}" for p in problems] if problems else ["Nothing: the image set is complete."]
    if a.no_render:
        md.append("- 3D renders were switched off (--no-render).")
    result = "PASS" if not problems and not a.no_render else "FAIL (incomplete image set)"
    md += ["", f"**{result}**: {len(made)} images in {time.monotonic() - t0:.0f} s."]
    kicad_io.atomic_write(os.path.join(out, "index.md"), pcb_common.scrub("\n".join(md) + "\n"))
    data = {"script": "review_images.py", "result": result, "board": os.path.basename(job.board), "bbox": list(bbox),
            "px_per_mm": ppm, "tiles": [{"name": n, "core": list(c), "drawn": list(d)} for n, c, d in tiles],
            "images": [{"section": s, "file": r, "what": w} for s, r, w in made], "problems": problems, "notes": notes,
            "holes": [f["ref"] for f in holes], "connectors": [f["ref"] for f in conns],
            "bands": [{"name": b["name"], "edge": b["edge"], "width": b["width"], "sides": b["sides"], "poly": [list(q) for q in b["poly"]]}
                      for b in bands]}
    kicad_io.atomic_write(os.path.join(out, "index.json"), json.dumps(pcb_common.scrub(data), indent=1) + "\n")
    print(f"{result}: {len(made)} images, {len(tiles)} tiles per side, {len(holes)} holes, {len(conns)} connectors, "
          f"{len(flag_rows)} flagged locations -> {os.path.join(out, 'index.md')}")
    for p in problems[:20]:
        print("  not made / not exact:", p)
    return 0 if result == "PASS" else 1


def panel_images(panel: str, out: str, tmp: str, quality: str, no_render: bool, ppm: float):
    """Renders and plots of the panel board. Returns (made, problems)."""
    made, problems = [], []
    ptmp = os.path.join(tmp, "panel")
    os.makedirs(ptmp)
    with pcb_common.work_copy(panel, "review-panel-") as copy:
        info = pcb_common.read_board(clone(copy, ptmp, "dump"), os.path.dirname(panel))
        bbox = tuple(info["bbox"])
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if not no_render:
            sc = min(30.0, math.sqrt(9e6 * FIT * FIT / (bw * bh)))
            for side in ("top", "bottom"):
                why = render(clone(copy, ptmp, "r" + side), os.path.join(out, f"panel_render_{side}.png"),
                             ["-w", str(int(bw * sc / FIT)), "-h", str(int(bh * sc / FIT)), "--background", "opaque", "--zoom", fit_zoom(bw, bh),
                              "--side", side], quality)
                if why:
                    problems.append(f"`panel_render_{side}` was not rendered: {why}")
                else:
                    made.append(("panel", f"panel_render_{side}.png", f"3D render of the panel, {side}"))
        gfolder, exp_problems = export_production(copy, ptmp, info["copper_layers"] + ["F.Silkscreen", "B.Silkscreen", "F.Mask",
                                                                                         "B.Mask", "Edge.Cuts"])
        problems += ["panel: " + p for p in exp_problems]
        L = load_layers(gfolder)
        problems += ["panel: " + n for n in L.notes]
        view = full_view(L, k2g(bbox))
        sc = plot_scale(view, ppm)
        for side in ("top", "bottom"):
            compose(L.stack("plot", side), view, sc, side == "bottom").save(os.path.join(out, f"panel_plot_{side}.png"))
            made.append(("panel", f"panel_plot_{side}.png", f"plot of the panel, {side}: copper, mask openings, silkscreen, "
                         f"holes, outline, at {sc:.0f} px/mm" + (" (mirrored)" if side == "bottom" else "")))
    return made, problems


# ---- the Gerber mode -------------------------------------------------------------------------------------------------
def gerber_mode(job, a, lim) -> int:
    Image, ImageDraw, _ = _pil()
    folder = os.path.abspath(a.gerbers)
    if not os.path.isdir(folder):
        raise kicad_io.KicadIOError(f"no such Gerber folder: {folder}")
    out = os.path.join(job.out, "review")
    remove_own(out)
    for sub in ("tiles", "layers"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    t0 = time.monotonic()
    L = load_layers(folder)
    if not L.copper and not L.other and L.outline is None:
        raise kicad_io.KicadIOError(f"{folder}: no readable Gerber file")
    problems = list(L.notes)
    ppm = lim["px_per_mm"]
    view = full_view(L)
    fppm = plot_scale(view, ppm)
    made = []
    core_box = (view[0] + MARGIN, view[1] + MARGIN, view[2] - MARGIN, view[3] - MARGIN)
    # tiles are named in image order: row A at the top of the picture (largest y of the file frame)
    tiles = []
    for name, core, drawn in grid((core_box[0], -core_box[3], core_box[2], -core_box[1]), lim["tile_mm"], lim["overlap_mm"]):
        tiles.append((name, (core[0], -core[3], core[2], -core[1]), (drawn[0], -drawn[3], drawn[2], -drawn[1])))
    with ThreadPoolExecutor(max_workers=a.jobs or max(2, (os.cpu_count() or 4) // 2)) as pool:
        futs = []

        def job_draw(stack, v, scale, mirror, rel, section, what, cap=None, bg=BG):
            img = compose(stack, v, scale, mirror, bg)
            (caption(img, cap) if cap else img).save(os.path.join(out, rel.replace("/", os.sep)))
            made.append((section, rel, what))

        sides = [s for s in ("top", "bottom") if L.side[s]]
        for side in sides:
            mir = side == "bottom"
            futs.append(pool.submit(job_draw, L.stack("plot", side), view, fppm, mir, f"stack_{side}.png", "whole",
                                    f"{side} stacked view: copper, mask openings (orange), silkscreen (yellow), holes "
                                    f"(white), outline" + (" (mirrored: as seen from the bottom)" if mir else "")))
            for name, core, drawn in tiles:
                capt = (f"{side} {name} | x {drawn[0]:.1f}..{drawn[2]:.1f}  y {drawn[1]:.1f}..{drawn[3]:.1f} mm (file frame, y up) | "
                        f"{ppm:.0f} px/mm" + (" | mirrored" if mir else ""))
                futs.append(pool.submit(job_draw, L.stack("plot", side), drawn, ppm, mir, f"tiles/{side}_{name}.png",
                                        f"tile {side}", "stacked view", capt))
        for name in L.copper:
            futs.append(pool.submit(job_draw, L.copper_stack(name), view, fppm, False, f"layers/copper_{safe_name(name)}.png",
                                    "layers", f"copper layer `{L.copper[name].name}` with the holes (not mirrored)"))
        for side in ("top", "bottom"):
            for kind, col in (("silk", C_SILK), ("mask", C_MASK), ("paste", C_PASTE), ("fab", C_FAB)):
                lay = L.side[side].get(kind)
                if lay is not None:
                    futs.append(pool.submit(job_draw, [(lay, col, 1.0, 1.5), (L.outline, C_EDGE, 1.0, 2)], view, fppm, False,
                                            f"layers/{kind}_{side}.png", "layers",
                                            f"{kind} {side} `{lay.name}` with the outline (not mirrored)"))
        for fname, lay in L.other.items():
            futs.append(pool.submit(job_draw, [(lay, (200, 200, 120), 1.0, 1.5), (L.outline, C_EDGE, 1.0, 2)], view, fppm, False,
                                    f"layers/other_{safe_name(os.path.splitext(fname)[0])}.png", "layers",
                                    f"`{fname}` (role not recognised or a drill map) with the outline"))
        if L.drills:
            futs.append(pool.submit(job_draw, [(L.drills, C_DRILL, 1.0, 1), (L.outline, C_EDGE, 1.0, 2)], view, fppm, False,
                                    "layers/drills.png", "layers", "all drill files: holes and slots, with the outline"))
        for f in futs:
            try:
                f.result()
            except Exception as e:
                problems.append(f"a drawing failed: {type(e).__name__}: {e}")
    if L.outline is None:
        problems.append("no board-outline file was recognised: the view is the box of all layers")
    if not L.drills:
        problems.append("no drill file was found: holes are not drawn")
    nrow = len({t[0].rstrip("0123456789") for t in tiles})
    md = [f"# Review images of production files: contact sheet", "",
          f"Script `review_images.py --gerbers`; folder `{os.path.basename(folder)}`; drawn area "
          f"{view[2] - view[0] - 2 * MARGIN:.2f} x {view[3] - view[1] - 2 * MARGIN:.2f} mm. Coordinates are the files' own "
          "(mm, y up). **Bottom views are mirrored: as seen from the bottom.** No board file was used: there are no "
          "designator positions and no 3D renders.", "", "Settings:", ""] + lim.table() + [
          "", "## Files and their roles", "", "| File | Read as |", "|---|---|"]
    md += [f"| `{n}` | {r} |" for n, r in L.files]
    md += ["", "## Whole board", "", "| File | What it shows |", "|---|---|"]
    md += [f"| `{rel}` | {what} |" for sec, rel, what in sorted(made) if sec == "whole"]
    md += ["", f"## Tiles: {nrow} row(s) A.. from the top of the picture, columns 1.. from the left (top view)", "",
           "| Tile | x (mm) | y (mm) | Files (tiles/) |", "|---|---|---|---|"]
    have = {rel for _, rel, _ in made}
    for name, core, drawn in tiles:
        files = [f"`{s}_{name}.png`" for s in ("top", "bottom") if f"tiles/{s}_{name}.png" in have]
        md.append(f"| {name} | {core[0]:.1f} .. {core[2]:.1f} | {core[1]:.1f} .. {core[3]:.1f} | {', '.join(files)} |")
    md += ["", "## Layers", "", "| File | What it shows |", "|---|---|"]
    md += [f"| `{rel}` | {what} |" for sec, rel, what in sorted(made) if sec == "layers"]
    md += ["", "## Not drawn, or not drawn exactly", ""]
    md += [f"- {p}" for p in problems] if problems else ["Nothing: every file was read and drawn exactly."]
    result = "PASS" if not problems else "FAIL (see: not drawn, or not drawn exactly)"
    md += ["", f"**{result}**: {len(made)} images in {time.monotonic() - t0:.0f} s."]
    kicad_io.atomic_write(os.path.join(out, "index.md"), pcb_common.scrub("\n".join(md) + "\n"))
    kicad_io.atomic_write(os.path.join(out, "index.json"), json.dumps(pcb_common.scrub(
        {"script": "review_images.py --gerbers", "result": result, "view": list(view), "px_per_mm": ppm,
         "files": [{"file": n, "role": r} for n, r in L.files], "problems": problems,
         "images": [{"section": s, "file": r, "what": w} for s, r, w in sorted(made)]}), indent=1) + "\n")
    print(f"{result}: {len(made)} images from {len(L.files)} files -> {os.path.join(out, 'index.md')}")
    for p in problems[:20]:
        print("  not drawn / not exact:", p)
    return 0 if result == "PASS" else 1


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Review images of a board (or of production files): renders, plots, zoom tiles, contact sheet.",
                              epilog="Exit codes: 0 complete image set, 1 incomplete, 2 could not run.")
    ap.add_argument("--gerbers", help="a folder of production files: draw them, no board needed")
    ap.add_argument("--panel", help="the panel's board file (default: board.toml [panel] board; with --project also "
                                    "*panel*.kicad_pcb beside the board, else the board in out/panel/board/)")
    ap.add_argument("--flags", nargs="*", help="result JSON files with crop locations (silk_check.json, edge_check.json)")
    ap.add_argument("--px-per-mm", type=float, dest="px_per_mm", help=f"tile scale (default {DEFAULTS['px_per_mm']:.0f})")
    ap.add_argument("--tile-mm", type=float, dest="tile_mm", help=f"tile core size (default {DEFAULTS['tile_mm']:.0f})")
    ap.add_argument("--fast", action="store_true", help="basic render quality (faster)")
    ap.add_argument("--no-render", action="store_true", dest="no_render", help="no 3D renders: plots only (exit code 1)")
    ap.add_argument("--jobs", type=int, help="processes and drawings at once (default: half the cores)")
    a = ap.parse_args(argv)
    job = pcb_common.resolve(a, need_board=not a.gerbers)
    defaults = {k: v for k, v in DEFAULTS.items() if not a.gerbers or k in ("px_per_mm", "tile_mm", "overlap_mm")}
    lim = pcb_common.Limits(job.cfg("review"), defaults, {"px_per_mm": a.px_per_mm, "tile_mm": a.tile_mm})
    if lim["px_per_mm"] <= 0 or lim["tile_mm"] <= 0:
        raise kicad_io.KicadIOError("px_per_mm and tile_mm must be positive")
    _pil()
    if a.gerbers:
        return gerber_mode(job, a, lim)
    if lim["quality"] not in ("high", "basic"):
        raise kicad_io.KicadIOError("[review] quality must be \"high\" or \"basic\"")
    kicad_io.require_kicad()
    return board_mode(job, a, lim)


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
