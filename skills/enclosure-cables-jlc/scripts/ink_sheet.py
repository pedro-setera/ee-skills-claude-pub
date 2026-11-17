"""Ink sheet and factory view: the print DXF shown as it will be printed, and as a plain viewer shows it.

What it does
    Ink sheet (default): one PDF sheet + a PNG. Every face 1:1 in the real ink colours on the coat colour, an
    ink table (DXF layer -> chart ink -> a swatch on the coat colour, with the contrast ratio), then the
    REFERENCE layers of the file (outline, bend lines: every layer that is no ink) each with its colour swatch
    and "NOT printed", the no-print zones dashed and named (from mech.toml; they are drawn on this sheet ONLY,
    never in the DXF), and the line "Print ONLY <n> inks: <chart names>. Lines on <layer names> are references
    and are NOT printed." It goes into the upload set beside the DXF, so the person preparing the screens does
    not have to guess from layer colours.
    Factory view (--factory-view): a PNG of the DXF as a plain viewer shows it on a DARK background, every entity
    in its resolved display colour (the entity's true colour, else its index, else its layer's; index 7 is shown
    WHITE). The header names the ink layers the factory reads as inks; the reference layers (every layer that is
    no ink, normally OUTLINE_NOT_PRINTED and BEND_LINE_NOT_PRINTED) are drawn dashed in their own colour and the
    legend says "<layer>: NOT PRINTED (reference)". A legend lists every distinct colour seen and the layers it
    comes from. Check rows:
      - every ink layer shows exactly one colour, the chart colour of its ink;
      - every visible colour belongs to exactly one ink layer (a reference layer is none);
      - every reference layer has a colour of its own: not index 7 or 0 or white (a plain viewer draws it as a
        white ink), set by layer (entities BYLAYER), never the colour (or colour index) of an ink layer, named
        *_NOT_PRINTED; a coloured entity or layer anywhere else outside an ink layer fails;
      - no closed shape (closed polyline, circle, hatch, solid) on a reference layer;
      - no text, dimension, block or image entity anywhere (text must be outlines);
      - every layer in use is an ink layer or ends in _NOT_PRINTED; no layer name asks for a colour system or a
        process the chart does not offer.
    The default pair, green cut edges and yellow dashed bend lines (silk_dxf.py), passes. Somebody must LOOK at
    both pictures; the rows cannot see a wrong word or a mirrored face.

Why it exists (the real failure, told without names)
    A factory opened a print file whose layers had the CAD defaults. It read colours as inks: the black text was
    on colour index 7, shown white on their dark screen, and was queued as white ink; a magenta outline of a
    no-print area stopped the part with "no magenta ink". The part was held in production. Nobody had opened the
    file in a plain viewer on a dark background before the order. The first version of this picture then drew the
    outline and bend-line layers on index 7 as white lines under a header that said "every colour you see will be
    read as an ink", and passed them: a picture-only reviewer rightly called that a white ink. A corrected file
    put the cut edges on a green layer and the bend lines on a yellow dashed one, and its ink sheet listed both
    as "NOT printed": no question came back about them.

Usage
    python -I ink_sheet.py --dxf <part_silk.dxf> --coat "<chart name>" [--coat-rgb "#RRGGBB"] [--silk-json <file>]
                           [--capability <sheet>] [--part NAME] [--project <mech folder>] [--out <folder>]
    python -I ink_sheet.py --factory-view --dxf <part_silk.dxf> [--capability <sheet>] [--background "#212830"]
        --coat        the coat colour's name on the supplier's chart (printed as given); its RGB from the
                      capability sheet's [coat_rgb] or from --coat-rgb
        --silk-json   the element list of silk_dxf.py (default: the DXF's name with .json): face names
        outputs       <out>/silk/<part>_ink_sheet.pdf + .png ; <out>/silk/<part>_factory_view.png
    Needs ezdxf, matplotlib, shapely, numpy, scipy.

Config keys
    mech.toml  [project] company, rev; [sheet] supplier
               [silk] coat = "", notes = [ "text printed unchanged", ... ]
                      no_print = [ {face = "REAR", name = "label area", rect = [x, y, w, h]} ]   # face frame
                      outline_layer, bend_layer, non_print_suffix = "_NOT_PRINTED"
                      (the reference colours are set by silk_dxf.py; this script reads them from the DXF)
                      min_contrast = 3.0     # optional: an ink under this contrast on the coat colour fails
    capability sheet  [finishes] inks; [ink_rgb]; [coat_rgb]

Exit codes
    0 written, every row passes     1 a row failed (a reference layer on index 7 or white, a closed shape on a
    reference layer, a reference layer in an ink's colour, a coloured entity outside an ink layer, an ink not on the
    chart)     2 could not run (no DXF, no capability sheet, no coat colour, a library missing)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import datetime
import os
import re
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

PT = 25.4 / 72.0
PAGES = [("A4", 297.0, 210.0), ("A3", 420.0, 297.0), ("A2", 594.0, 420.0), ("A1", 841.0, 594.0)]
BAD_WORDS = [("a colour system (RAL)", r"\bRAL\b"), ("a colour system (Pantone)", r"PANTONE|\bPMS\b"),
             ("masking", r"MASK"), ("a fallback", r"FALL.?BACK|IF.?POSSIBLE")]


def layer_name(ink):
    return "_".join(str(ink).upper().split())


def hex_rgb(h):
    h = str(h).strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "#%02X%02X%02X" % tuple(int(v) for v in rgb)


def luminance(rgb):
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def patch_of(poly, dx=0.0, dy=0.0, **kw):
    """A shapely polygon with holes as one matplotlib patch."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    from shapely.geometry.polygon import orient

    poly = orient(poly, 1.0)
    verts, codes = [], []
    for ring in [poly.exterior] + list(poly.interiors):
        cs = list(ring.coords)
        verts += [(x + dx, y + dy) for x, y in cs]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(cs) - 2) + [Path.CLOSEPOLY]
    return PathPatch(Path(verts, codes), **kw)


def polys(g):
    return [q for q in (list(g.geoms) if hasattr(g, "geoms") else [g]) if q.geom_type == "Polygon" and not q.is_empty]


ACI_NAMES = {1: "red", 2: "yellow", 3: "green", 4: "cyan", 5: "blue", 6: "magenta", 7: "default/white"}


def aci_text(i):
    return f"index {i}" + (f" ({ACI_NAMES[i]})" if i in ACI_NAMES else "")


def reference_layers(doc, lay_of, cfg_silk):
    """The reference layers of a print file: every layer that is no ink layer and holds at least one entity (normally the
    outline and the bend lines). The configured outline and bend layers come first. Each: {layer, rgb (as a plain viewer
    shows the first entity), how, aci (the layer's index), linetype (the layer's), n (entities), types}."""
    on = {}
    for e in doc.modelspace():
        if e.dxf.layer not in lay_of:
            on.setdefault(e.dxf.layer, []).append(e)
    first = [cfg_silk.get("outline_layer", "OUTLINE_NOT_PRINTED"), cfg_silk.get("bend_layer", "BEND_LINE_NOT_PRINTED")]
    out = []
    for lay in [x for x in first if x in on] + sorted(x for x in on if x not in first):
        rgb, how = resolved_colour(on[lay][0], doc)
        la = doc.layers.get(lay) if lay in doc.layers else None
        out.append({"layer": lay, "rgb": rgb, "how": how, "aci": abs(la.color) if la is not None else 7,
                    "linetype": la.dxf.linetype if la is not None else "Continuous", "n": len(on[lay]),
                    "types": sorted({e.dxftype() for e in on[lay]})})
    return out


# ---------------------------------------------------------------- the ink sheet --------------------------------------
def ink_sheet(dxf, part, cap, cfg, coat_name, coat_rgb, sjson, out_dir, rows):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from shapely.geometry import Polygon

    import ezdxf
    import sheet_dfm

    sk = cfg.get("silk", {})
    chart = list((cap.get("finishes") or {}).get("inks") or [])
    lay_of = {layer_name(i): i for i in chart}
    rgbs = {i: hex_rgb(v) for i, v in (cap.get("ink_rgb") or {}).items()}
    data = sheet_dfm.read_print(dxf, list(lay_of), sk.get("outline_layer", "OUTLINE_NOT_PRINTED"),
                                sk.get("bend_layer", "BEND_LINE_NOT_PRINTED"))
    refs = reference_layers(ezdxf.readfile(dxf), lay_of, sk)
    faces = sorted(data["faces"], key=lambda f: f.bounds[0])
    inks = {lay: g for lay, g in data["inks"].items() if not g.is_empty}
    rid = f"IS-{part}"
    rows.add(f"{rid}-01", f"ink sheet:{part}", "the DXF has face outlines and ink layers",
             f"{len(faces)} face(s), inks: " + (", ".join(lay_of[k] for k in inks) or "none"), ">= 1 face, >= 1 ink",
             "pass" if faces and inks else "fail")
    if not faces or not inks:
        return None
    missing = [lay_of[k] for k in inks if lay_of[k] not in rgbs]
    rows.add(f"{rid}-02", f"ink sheet:{part}", "every ink has its colour on the capability sheet",
             "missing [ink_rgb]: " + (", ".join(missing) or "none"), "none missing", "pass" if not missing else "fail")
    if missing:
        return None
    names = {}
    man = mc.load_json(sjson) if sjson and os.path.isfile(sjson) else None
    if man:
        for fc in man.get("faces", []):
            names[round(fc["bbox"][0] + fc["offset"][0], 1)] = (fc["name"], fc["offset"][0])
    x0 = min(f.bounds[0] for f in faces)
    y0 = min(f.bounds[1] for f in faces)
    x1 = max(f.bounds[2] for f in faces)
    y1 = max(f.bounds[3] for f in faces)
    w, h = x1 - x0, y1 - y0
    n_rows = len(inks) + (len(refs) + 1 if refs else 0)         # ink rows + the reference heading and its rows
    notes = [str(n) for n in sk.get("notes", [])]
    only = f"Print ONLY {len(inks)} ink{'s' if len(inks) != 1 else ''}: {', '.join(lay_of[k] for k in inks)}." + (
        f" Lines on {', '.join(r['layer'] for r in refs)} are references and are NOT printed." if refs else " No other ink.")
    only_lines = textwrap.wrap(only, 135)
    below = 30 + 9 * (n_rows + 1) + 6 * (len(notes) + 3 + len(only_lines))
    page = next(((nm, pw, ph) for nm, pw, ph in PAGES if w + 40 <= pw and h + below + 50 <= ph), None)
    scale = 1.0
    if page is None:
        page = PAGES[-1]
        scale = min((page[1] - 40) / w, (page[2] - below - 50) / h)
    pname, pw, ph = page
    fig = plt.figure(figsize=(pw / 25.4, ph / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, pw)
    ax.set_ylim(0, ph)
    ax.axis("off")
    ax.add_patch(Rectangle((8, 8), pw - 16, ph - 16, fill=False, lw=0.9, ec="black"))

    def t(x, y, s, fs=9, **k):
        ax.text(x, y, s, fontsize=fs, family="DejaVu Sans", **k)

    pr = cfg.get("project", {})
    t(14, ph - 20, f"{part}: SILKSCREEN INKS", 15, weight="bold")
    head = "   ".join(x for x in (pr.get("company", ""), f"rev {pr.get('rev', '')}" if pr.get("rev") else "",
                                  datetime.date.today().isoformat(), f"file: {os.path.basename(dxf)}") if x)
    t(14, ph - 27, head, 8.5)
    ox = (pw - w * scale) / 2 - x0 * scale
    oy = ph - 44 - h * scale - y0 * scale
    coat = tuple(v / 255 for v in coat_rgb)

    def X(x):
        return ox + x * scale

    def Y(y):
        return oy + y * scale

    from shapely import affinity

    def place(g):
        return affinity.translate(affinity.scale(g, scale, scale, origin=(0, 0)), ox, oy)

    for k, f in enumerate(faces):
        ax.add_patch(patch_of(place(f), fc=coat, ec="#555555", lw=0.35, zorder=1))
        nm = names.get(round(f.bounds[0], 1), (f"FACE {k + 1}", None))[0]
        t(X(f.bounds[0]), Y(f.bounds[3]) + 2.5, f"{nm}, as seen from outside, " + ("1 : 1" if scale == 1.0 else
                                                                                   f"scale 1 : {1 / scale:.2f}"), 9,
          weight="bold")
    for b in data["bends"]:
        xs, ys = b.xy
        ax.plot([X(v) for v in xs], [Y(v) for v in ys], color="#555555", lw=0.4, ls=(0, (5, 3)), zorder=2)
    for lay, g in inks.items():
        col = tuple(v / 255 for v in rgbs[lay_of[lay]])
        for q in polys(g):
            ax.add_patch(patch_of(place(q), fc=col, ec="none", zorder=3))
    # no-print zones: on this sheet only
    zones = []
    for z in sk.get("no_print", []):
        off = next((o for nm, o in names.values() if nm == z.get("face")), None)
        if off is None and len(faces) == 1:
            off = 0.0
        if off is None:
            zones.append((z, None))
            continue
        zx, zy, zw, zh = z["rect"]
        ax.add_patch(Rectangle((X(zx + off), Y(zy)), zw * scale, zh * scale, fill=False, ec="black", lw=0.6,
                               ls=(0, (3, 2)), zorder=5))
        ax.text(X(zx + off + zw / 2), Y(zy + zh / 2), f"NO PRINT\n{z.get('name', '')}", ha="center", va="center",
                fontsize=6.5, zorder=6)
        zones.append((z, off))
    lost = [z.get("name", "?") for z, off in zones if off is None]
    hit = []
    allink = None
    from shapely.ops import unary_union
    from shapely.geometry import box
    allink = unary_union(list(inks.values()))
    for z, off in zones:
        if off is not None:
            zx, zy, zw, zh = z["rect"]
            a = allink.intersection(box(zx + off, zy, zx + off + zw, zy + zh)).area
            if a > 1e-4:
                hit.append(f"{z.get('name', '?')} ({a:.2f} mm2)")
    if sk.get("no_print"):
        rows.add(f"{rid}-03", f"ink sheet:{part}", "no print inside a no-print zone",
                 f"{len(zones)} zone(s); printed inside: " + (", ".join(hit) or "none")
                 + ("; face not found for: " + ", ".join(lost) if lost else ""), "none",
                 "fail" if hit else ("could_not_run" if lost else "pass"))
    # the ink table, then the reference layers
    ty = oy + y0 * scale - 16
    tx = 14
    used = [lay_of[k] for k in inks]
    t(tx, ty, f"PRINT ONLY {len(used)} INK{'S' if len(used) != 1 else ''}", 12, weight="bold")
    cols = [("DXF layer", 0), ("Ink (name on the ink chart)", 48), ("Printed on the coat", 104), ("Contrast", 150)]
    for nm, dxc in cols:
        t(tx + dxc, ty - 9, nm, 9, weight="bold")
    ax.plot([tx, tx + 175], [ty - 10.5, ty - 10.5], color="black", lw=0.4)
    for k, lay in enumerate(inks):
        ink = lay_of[lay]
        y = ty - 9 * (k + 2)
        t(tx, y, lay, 9)
        t(tx + 48, y, ink, 9)
        ax.add_patch(Rectangle((tx + 104, y - 2), 28, 6.5, fc=coat, ec="black", lw=0.3))
        ax.add_patch(Rectangle((tx + 108, y - 0.3), 20, 3.1, fc=tuple(v / 255 for v in rgbs[ink]), ec="none"))
        c = contrast(rgbs[ink], coat_rgb)
        t(tx + 150, y, f"{c:.1f} : 1" + ("  LOW" if c < 3 else ""), 9, color="#b00020" if c < 3 else "black")
    if refs:
        y = ty - 9 * (len(inks) + 2)
        ax.plot([tx, tx + 175], [y + 5.5, y + 5.5], color="black", lw=0.4)
        t(tx, y, "Reference layers: NOT printed (the colour is only what a DXF viewer shows)", 9, weight="bold")
        for j, r in enumerate(refs):
            y = ty - 9 * (len(inks) + 3 + j)
            white = "default" in r["how"] or tuple(r["rgb"]) == (255, 255, 255)
            t(tx, y, r["layer"], 9)
            t(tx + 48, y, "NOT printed (reference)", 9)
            ax.add_patch(Rectangle((tx + 104, y - 2), 28, 6.5, fc="#212830", ec="black", lw=0.3))
            ax.plot([tx + 107, tx + 129], [y + 1.25, y + 1.25], color=tuple(v / 255 for v in r["rgb"]), lw=1.4,
                    ls="-" if str(r["linetype"]).upper() in ("CONTINUOUS", "BYLAYER", "BYBLOCK") else (0, (4, 2.5)))
            t(tx + 150, y, (aci_text(r["aci"]) if r["how"].startswith("layer index") else to_hex(r["rgb"]))
              + ("  WHITE" if white else "") + (", dashed" if str(r["linetype"]).upper() not in
                                                 ("CONTINUOUS", "BYLAYER", "BYBLOCK") else ""), 9,
              color="#b00020" if white else "black")
    ny = ty - 9 * (n_rows + 2) - 3
    lines = only_lines + [f"Coat colour shown: {coat_name}. Colours on this sheet are a screen picture of the chart colours.",
                          "Grey outlines and dashed bend lines on this sheet: for position only, not printed."
                          + (" Dashed black boxes: no-print zones." if zones else "")]
    for s_ in lines + [f"{i + 1}. {n}" for i, n in enumerate(notes)]:
        t(tx, ny, s_, 8.5, weight="bold" if s_ in only_lines else "normal")
        ny -= 6
    cmin = sk.get("min_contrast")
    low = [lay_of[k] for k in inks if cmin is not None and contrast(rgbs[lay_of[k]], coat_rgb) < float(cmin)]
    rows.add(f"{rid}-04", f"ink sheet:{part}", "contrast of every ink on the coat colour (1 = invisible, 21 = black on white)",
             "; ".join(f"{lay_of[k]} {contrast(rgbs[lay_of[k]], coat_rgb):.1f}" for k in inks),
             f">= {cmin} : 1 ([silk] min_contrast)" if cmin is not None else "no [silk] min_contrast set: reported only; "
             "under 3 : 1 is marked LOW on the sheet", ("pass" if not low else "fail") if cmin is not None else "na")
    os.makedirs(out_dir, exist_ok=True)
    pdf = os.path.join(out_dir, f"{part}_ink_sheet.pdf")
    fig.savefig(pdf, metadata={"Title": f"{part} silkscreen inks", "Author": pr.get("company", ""), "Creator": "ink_sheet",
                               "Producer": "", "CreationDate": None})
    png = os.path.join(out_dir, f"{part}_ink_sheet.png")
    fig.savefig(png, dpi=110)
    plt.close(fig)
    rows.add(f"{rid}-05", f"ink sheet:{part}", "sheet written at 1 : 1",
             f"page {pname} landscape, scale " + ("1 : 1" if scale == 1.0 else f"1 : {1 / scale:.2f} (too large for A1)"),
             "1 : 1", "pass" if scale == 1.0 else "fail")
    return pdf, png


# ---------------------------------------------------------------- the factory view -----------------------------------
def resolved_colour(e, doc):
    """((r, g, b), how) as a plain viewer shows the entity: true colour, else index, else the layer's; 7 = white."""
    from ezdxf import colors

    if e.dxf.hasattr("true_color"):
        return tuple(colors.int2rgb(e.dxf.true_color)), "entity true colour"
    aci = e.dxf.get("color", 256)
    how = f"entity index {aci}"
    if aci == 256:
        lay = doc.layers.get(e.dxf.layer) if e.dxf.layer in doc.layers else None
        if lay is not None and lay.rgb is not None:
            return tuple(lay.rgb), "layer true colour"
        aci = abs(lay.color) if lay is not None else 7
        how = f"layer index {aci}"
    if aci in (0, 7) or aci > 255:
        return (255, 255, 255), how + " (default: white on a dark screen)"
    return tuple(colors.aci2rgb(aci)), how


def is_closed(e):
    t = e.dxftype()
    if t in ("HATCH", "SOLID", "CIRCLE", "TRACE", "3DFACE", "MPOLYGON"):
        return True
    if t == "LWPOLYLINE":
        pts = list(e.get_points("xy"))
        return bool(e.closed) or (len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6)
    if t == "POLYLINE":
        return bool(e.is_closed)
    if t == "ELLIPSE":
        return abs((e.dxf.end_param - e.dxf.start_param) - 6.283185307) < 1e-6
    if t == "SPLINE":
        return bool(e.closed)
    if t == "ARC":
        return abs(((e.dxf.end_angle - e.dxf.start_angle) % 360.0)) < 1e-9 and e.dxf.end_angle != e.dxf.start_angle
    return False


def factory_view(dxf, part, cap, cfg, background, out_dir, rows):
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf import path as zpath
    from matplotlib.patches import Rectangle
    from shapely.geometry import Polygon

    sk = cfg.get("silk", {})
    suffix = sk.get("non_print_suffix", "_NOT_PRINTED")
    chart = list((cap.get("finishes") or {}).get("inks") or [])
    lay_of = {layer_name(i): i for i in chart}
    rgbs = {i: hex_rgb(v) for i, v in (cap.get("ink_rgb") or {}).items()}
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    ents = list(msp)
    seen = {}            # rgb -> {layer: count}
    per_layer = {}       # layer -> {rgb: count}
    sample = {}          # (layer, rgb) -> how the colour of the first such entity was resolved
    on_layer = {}        # layer -> [entities]
    closed_non = {}
    forbidden = {}
    draw = []
    for e in ents:
        lay = e.dxf.layer
        t = e.dxftype()
        if t in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "INSERT", "DIMENSION", "LEADER", "MLEADER", "IMAGE", "ACAD_TABLE"):
            forbidden[t] = forbidden.get(t, 0) + 1
        rgb, how = resolved_colour(e, doc)
        seen.setdefault(rgb, {}).setdefault(lay, 0)
        seen[rgb][lay] += 1
        per_layer.setdefault(lay, {}).setdefault(rgb, 0)
        per_layer[lay][rgb] += 1
        sample.setdefault((lay, rgb), how)
        on_layer.setdefault(lay, []).append(e)
        if lay not in lay_of and is_closed(e):
            closed_non.setdefault(lay, {}).setdefault(t, 0)
            closed_non[lay][t] += 1
        draw.append((e, rgb))
    ink_lays = [lay for lay in per_layer if lay in lay_of]
    first = [sk.get("outline_layer", "OUTLINE_NOT_PRINTED"), sk.get("bend_layer", "BEND_LINE_NOT_PRINTED")]
    ref_lays = [lay for lay in per_layer if lay not in lay_of]          # the reference layers: every layer that is no ink
    ref_lays = [x for x in first if x in ref_lays] + sorted(x for x in ref_lays if x not in first)
    # ---- the picture
    xs, ys, items = [], [], []
    for e, rgb in draw:
        col = tuple(v / 255 for v in rgb)
        is_ref = e.dxf.layer not in lay_of
        try:
            if e.dxftype() == "HATCH":
                g = Polygon()
                for bp in e.paths:
                    pts = [(v.x, v.y) for v in zpath.from_hatch_boundary_path(bp).flattening(0.01)]
                    if len(pts) >= 3:
                        g = g.symmetric_difference(Polygon(pts).buffer(0))
                for q in polys(g):
                    items.append(("fill", q, col, False))
                    xs += [q.bounds[0], q.bounds[2]]
                    ys += [q.bounds[1], q.bounds[3]]
            else:
                pts = [(v.x, v.y) for v in zpath.make_path(e).flattening(0.01)]
                if len(pts) >= 2:
                    items.append(("line", pts, col, is_ref))
                    xs += [p[0] for p in pts]
                    ys += [p[1] for p in pts]
        except Exception:
            forbidden[e.dxftype()] = forbidden.get(e.dxftype(), 0) + 1
    if not xs:
        rows.add(f"FV-{part}-00", f"factory view:{part}", "the DXF has drawable entities", "none", ">= 1", "fail")
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    leg_rows = sum(len(lays) for lays in seen.values())       # one legend line per colour and layer
    fw = 16.0
    sc = (fw * 25.4 - 20) / max(w, 1)
    head = [f"{os.path.basename(dxf)}: as a plain viewer shows it (dark background, colour index 7 = white).",
            f"Read as INKS: {', '.join(ink_lays) or 'none'} ({len(ink_lays)} ink layer{'s' if len(ink_lays) != 1 else ''})."
            + (f" Dashed lines on {', '.join(ref_lays)} are REFERENCES, NOT PRINTED." if ref_lays else
               " No reference layers in this file.")
            + " Any other colour you see here would be read as an ink."]
    head = [ln for h_ in head for ln in textwrap.wrap(h_, 150)]
    top = 12.0 + 5.5 * len(head)
    fh = (h * sc + top + 14 + 9 * (leg_rows + 2)) / 25.4
    fig = plt.figure(figsize=(fw, fh), facecolor=background)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=background)
    W, H = fw * 25.4, fh * 25.4
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ox, oy = 10 - x0 * sc, H - top - h * sc - y0 * sc
    from shapely import affinity
    for kind, g, col, is_ref in items:
        if kind == "fill":
            ax.add_patch(patch_of(affinity.translate(affinity.scale(g, sc, sc, origin=(0, 0)), ox, oy), fc=col,
                                  ec="none", zorder=2))
        elif is_ref:                                 # a reference layer: drawn dashed, whatever its linetype in the file
            ax.plot([ox + p[0] * sc for p in g], [oy + p[1] * sc for p in g], color=col, lw=0.9, ls=(0, (5, 3)), zorder=3)
        else:
            ax.plot([ox + p[0] * sc for p in g], [oy + p[1] * sc for p in g], color=col, lw=0.7, zorder=3)
    for k, ln in enumerate(head):
        ax.text(10, H - 8 - 5.5 * k, ln, color="white", fontsize=10, family="DejaVu Sans",
                weight="bold" if k == 0 else "normal")

    # the colours of the ink layers (true colour and index), to tell a reference layer apart from them
    ink_rgbs = {}
    for lay in ink_lays:
        for rgb in list(per_layer[lay]) + [rgbs.get(lay_of[lay])]:
            if rgb is not None and lay not in ink_rgbs.setdefault(tuple(rgb), []):
                ink_rgbs[tuple(rgb)].append(lay)

    def indexes(lay):
        """The colour indexes a viewer that ignores true colour shows on a layer's entities."""
        la = doc.layers.get(lay) if lay in doc.layers else None
        base = abs(la.color) if la is not None else 7
        return {base if e.dxf.get("color", 256) == 256 else e.dxf.get("color", 256) for e in on_layer.get(lay, [])} or {base}

    ink_aci = {}
    for lay in ink_lays:
        for i in indexes(lay):
            ink_aci.setdefault(i, []).append(lay)

    def ref_faults(lay):
        """What is wrong with the colour or the name of a reference layer: [(short tag, sentence)] (empty = fine)."""
        out = []
        for rgb in per_layer[lay]:
            how = sample[(lay, rgb)]
            if "default" in how or tuple(rgb) == (255, 255, 255):
                out.append(("SHOWN WHITE = A WHITE INK", f"{lay}: shown WHITE ({how.split(' (')[0]}), a white ink to the factory"))
            elif not how.startswith("layer"):
                out.append(("OWN COLOUR, NOT BYLAYER", f"{lay}: entities carry their own colour ({how}); reference entities "
                                                       "must be BYLAYER"))
            if tuple(rgb) in ink_rgbs:
                out.append(("SAME COLOUR AS INK " + ", ".join(ink_rgbs[tuple(rgb)]),
                            f"{lay}: shows {to_hex(rgb)}, the colour of ink layer {', '.join(ink_rgbs[tuple(rgb)])}"))
        both = sorted(i for i in indexes(lay) if i in ink_aci and i != 7)
        if both:
            out.append(("SAME INDEX AS INK " + ", ".join(ink_aci[both[0]]),
                        f"{lay}: colour index {both[0]} is also used by ink layer {', '.join(ink_aci[both[0]])}"))
        if not lay.upper().endswith(suffix.upper()):
            out.append((f"NOT NAMED *{suffix}", f"{lay}: a layer that is no ink must be named *{suffix}"))
        return out

    ly = oy + y0 * sc - 12
    ax.text(10, ly, "COLOURS SEEN IN THE FILE", color="white", fontsize=10, weight="bold", family="DejaVu Sans")
    y = ly
    for rgb, lays in sorted(seen.items(), key=lambda kv: -sum(kv[1].values())):
        for j, (lay, n) in enumerate(sorted(lays.items())):
            y -= 9
            if j == 0:
                ax.add_patch(Rectangle((10, y - 1.5), 14, 6, fc=tuple(v / 255 for v in rgb), ec="#888888", lw=0.4))
            if lay in lay_of:
                ok = rgbs.get(lay_of[lay]) == rgb
                what = f"{lay} ({n} entities): ink '{lay_of[lay]}'" + ("" if ok else "  WRONG COLOUR FOR THIS INK")
            elif lay.upper().endswith(suffix.upper()):
                bad = ref_faults(lay)
                what = f"{lay} ({n} entities): NOT PRINTED (reference)" + ("  <- PROBLEM: " + "; ".join(sorted({b[0] for b in bad}))
                                                                        if bad else "")
            else:
                what = f"{lay} ({n} entities): NOT AN INK LAYER, NOT NAMED *{suffix}"
            if j == 0:
                ax.text(28, y, to_hex(rgb), color="white", fontsize=9, family="DejaVu Sans")
            ax.text(52, y, what, color="white", fontsize=9, family="DejaVu Sans")
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, f"{part}_factory_view.png")
    fig.savefig(png, dpi=110, facecolor=background)
    plt.close(fig)

    # ---- the rows
    sec = f"factory view:{part}"
    wrong = []
    for lay in ink_lays:
        want = rgbs.get(lay_of[lay])
        cols = per_layer[lay]
        if want is None or set(cols) != {want}:
            wrong.append(f"{lay}: shows " + ", ".join(to_hex(c) for c in cols) + f", chart {to_hex(want) if want else 'none'}")
    rows.add(f"FV-{part}-01", sec, "every ink layer shows exactly one colour: its chart ink's",
             f"{len(ink_lays)} ink layer(s): " + (", ".join(ink_lays) or "none") + ("; " + "; ".join(wrong) if wrong else ""),
             "layer colour = [ink_rgb] of its ink", "pass" if ink_lays and not wrong else "fail")
    shared = [to_hex(rgb) + " on " + " + ".join(sorted(l for l in lays if l in lay_of)) for rgb, lays in seen.items()
              if sum(1 for l in lays if l in lay_of) > 1]
    rows.add(f"FV-{part}-02", sec, "every visible colour belongs to exactly one ink layer (a reference layer is none)",
             f"{len(seen)} colour(s) seen" + ("; shared: " + "; ".join(shared) if shared else ""), "one colour, one ink",
             "pass" if not shared else "fail")
    faults = []
    for lay in ref_lays:
        faults += [long_ for _short, long_ in ref_faults(lay)]
    for la in doc.layers:            # a coloured layer with nothing on it that is neither an ink nor a reference layer
        nm = la.dxf.name
        if nm in lay_of or nm in ("0", "Defpoints") or nm in per_layer or nm.upper().endswith(suffix.upper()):
            continue
        if la.rgb is not None or abs(la.color) != 7:
            faults.append(f"{nm}: the layer itself is coloured (no entity on it) and is not named *{suffix}")
    ref_desc = []
    for lay in ref_lays:
        cols = sorted({(aci_text(sorted(indexes(lay))[0]) if sample[(lay, rgb)].startswith("layer index") else to_hex(rgb))
                       for rgb in per_layer[lay]})
        ref_desc.append(f"{lay} " + "/".join(cols))
    rows.add(f"FV-{part}-03", sec, "every reference layer (a layer that is no ink) has a colour of its own: not index 7 or white, "
             "by layer, not an ink's colour, named *" + suffix,
             (f"{len(ref_lays)} reference layer(s): " + ", ".join(ref_desc) if ref_lays else "no reference layers in the file")
             + (f"; {len(faults)} fault(s): " + "; ".join(faults[:8]) if faults else ""),
             "own colour by layer (default: green outline, yellow dashed bend lines); never 7 / 0 / white, never an ink's colour",
             "pass" if not faults else "fail")
    cl = [f"{lay}: " + ", ".join(f"{n} {t}" for t, n in ts.items()) for lay, ts in closed_non.items()]
    rows.add(f"FV-{part}-04", sec, "no closed shape on a reference layer (a closed shape is read as a print)",
             f"{sum(sum(ts.values()) for ts in closed_non.values())}" + (": " + "; ".join(cl[:8]) if cl else ""),
             "0: open lines and arcs only", "pass" if not cl else "fail")
    rows.add(f"FV-{part}-05", sec, "no text, dimension, block or image entity (text must be outlines)",
             ", ".join(f"{n} {t}" for t, n in forbidden.items()) or "none", "none", "pass" if not forbidden else "fail")
    odd = [lay for lay in per_layer if lay not in lay_of and not lay.upper().endswith(suffix.upper())]
    words = []
    for lay in doc.layers:
        for what, pat in BAD_WORDS:
            if re.search(pat, lay.dxf.name.replace("_", " "), re.I):
                words.append(f"{lay.dxf.name}: {what}")
    rows.add(f"FV-{part}-06", sec, f"every layer in use is a chart ink or ends in {suffix}; no layer name asks for "
             "what the chart does not offer", ("other layers in use: " + ", ".join(odd) if odd else "layers in use: "
                                               + ", ".join(sorted(per_layer)))
             + ("; words: " + "; ".join(words) if words else ""), "ink layers + *" + suffix + " only",
             "pass" if not odd and not words else "fail")
    return png


# ---------------------------------------------------------------- main -----------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="ink sheet PDF/PNG of a print DXF, or its factory view")
    mc.add_std_args(ap)
    ap.add_argument("--dxf")
    ap.add_argument("--part")
    ap.add_argument("--capability")
    ap.add_argument("--coat")
    ap.add_argument("--coat-rgb")
    ap.add_argument("--silk-json")
    ap.add_argument("--factory-view", action="store_true")
    ap.add_argument("--background", default="#212830")
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    for lib in ("ezdxf", "matplotlib", "shapely", "numpy", "scipy"):
        mc.require_module(lib, "ink_sheet.py")
    import sheet_dfm

    if not args.dxf or not os.path.isfile(args.dxf):
        print(f"could not run: no DXF ({args.dxf}); give --dxf <file>", file=sys.stderr)
        return 2
    cap_path = sheet_dfm.find_capability(job, args.capability)
    if not cap_path or not os.path.isfile(cap_path):
        print(f"could not run: no capability sheet ({cap_path}); give --capability or set [sheet] supplier",
              file=sys.stderr)
        return 2
    try:
        cap = mc.load_toml(cap_path)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    dxf = os.path.abspath(args.dxf)
    part = args.part or re.sub(r"_silk$", "", os.path.splitext(os.path.basename(dxf))[0])
    out_dir = os.path.join(job.out, "silk")
    rows = mc.Rows()
    try:
        if args.factory_view:
            res = factory_view(dxf, part, cap, job.cfg, args.background, out_dir, rows)
            script = "ink_sheet_factory_view.py"
            if res:
                print(f"{part}: factory view -> {res}  (LOOK at it: every colour there is an ink to the factory)")
        else:
            coat = args.coat or job.cfg.get("silk", {}).get("coat", "")
            crgb = args.coat_rgb or (cap.get("coat_rgb") or {}).get(coat)
            if not coat or not crgb:
                print("could not run: give --coat \"<chart name>\" with its colour in the capability sheet's [coat_rgb] "
                      "(or --coat-rgb \"#RRGGBB\")", file=sys.stderr)
                return 2
            sjson = os.path.abspath(args.silk_json) if args.silk_json else os.path.splitext(dxf)[0] + ".json"
            res = ink_sheet(dxf, part, cap, job.cfg, coat, hex_rgb(crgb), sjson, out_dir, rows)
            script = "ink_sheet.py"
            if res:
                print(f"{part}: ink sheet -> {res[0]} and {res[1]}  (LOOK at the PNG)")
    except Exception as e:  # a DXF that cannot be read
        if e.__class__.__name__ in ("DXFStructureError", "DXFError", "OSError", "UnicodeDecodeError"):
            print(f"could not run: {dxf}: {e}", file=sys.stderr)
            return 2
        raise
    rows.write(job.out, script, [dxf, cap_path])
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
