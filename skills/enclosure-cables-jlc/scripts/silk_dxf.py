"""Silkscreen file: an artwork description + the face outlines -> one DXF per part, ONE LAYER PER INK in the ink's colour.

What it does
    Reads an artwork file (TOML or JSON): per face its texts (font file, cap height, position), lines, rectangles,
    circles and polygons, each with an ink NAME from the supplier's ink chart. It writes
      <out>/silk/<part>_silk.dxf    the faces side by side, each as seen from outside (a rear face is therefore
                                    mirrored against the front), 1:1 in mm, text as outlines (no text entities);
      <out>/silk/<part>_silk.json   the element list (id, ink, box per face and in the file) for the drawing
                                    book's position sheet, the ink sheet and the rule measure.
    Layers
      - one layer per ink, named with the chart ink name in upper case with underscores ("Light Green" -> LIGHT_GREEN),
        the layer AND every entity on it in the ink's true colour from the capability sheet's [ink_rgb] (plus the
        nearest indexed colour for old viewers, never 7, never a reference colour);
      - two REFERENCE layers, kept for the person who reads the file and never printed: OUTLINE_NOT_PRINTED (the face
        outline and its cut-outs: continuous) and BEND_LINE_NOT_PRINTED (the bend lines: DASHED). How they are kept
        from being read as print: (1) the layer name ends in _NOT_PRINTED; (2) each has a colour of its own, set by
        layer (entities BYLAYER): [silk] outline_colour (default AutoCAD index 3, green) and bend_colour (default
        index 2, yellow); NEVER index 7 or 0 (a plain viewer shows 7 as white, and one factory read it as white ink),
        never a white index, never the colour of an ink layer of the same file (silk_dxf REFUSES that: exit 1, nothing
        written); (3) only open LINE and ARC entities: no closed polyline, no circle, no hatch, so nothing on them is
        a fillable shape; (4) the ink sheet (ink_sheet.py) lists both layers as "NOT printed" and states the inks.
        --outline corners writes only corner ticks on the outline layer, --outline none nothing.
    The DXF header names neither the writing tool nor a person: `$LASTSAVEDBY` (the library writes its own name there)
    and the other author-type variables are blanked, so `privacy_scan.py` finds nothing in the header.
    An ink that is not on the capability sheet's chart ([finishes] inks) or has no [ink_rgb] is REFUSED: nothing is
    written, exit 1. After writing, the file is read back and measured against [silk_rules] (smallest line, gap,
    text height, distance to edges, cut-outs and bend lines) with the measure of sheet_dfm.py.

Why it exists (the real failure, told without names)
    A print file used the CAD program's default colours. The factory read each colour as an ink: black text on
    the default "white" index was about to be printed white, and a magenta helper outline of a no-print area
    stopped the part in production with "we have no magenta ink". A closed shape in any colour is a print to the
    person preparing the screen. So: layer colour = ink colour, named as on the chart, and nothing else closed. The
    first answer to that was to leave the outline and bend-line layers on the default index 7 so that they had "no
    colour"; the factory view then drew them WHITE, and a picture-only reviewer rightly called white a second ink.
    A corrected file kept the cut edges on one layer in green and the bend lines on
    another in yellow, dashed, BYLAYER, open lines and arcs only, and the ink sheet listed both as "NOT printed":
    no supplier question was raised about them. So the reference layers have colours of their own, never index 7,
    and never the colour of an ink. And the DXF library wrote its own name into the file header ($LASTSAVEDBY), which
    the privacy scan of the upload folder flags as an author; the header is blanked.

Usage
    python -I silk_dxf.py --art <artwork.toml|json> [--capability <sheet>] [--outline open|corners|none]
                          [--project <mech folder>] [--out <folder>]
    Artwork file
        part = "base"            gap = 20.0   (between faces in the file)
        [[faces]]
        name = "FRONT"
        features = "out/drawings/base.features.json"    panel = "FRONT"     # outline, cut-outs, bends from the STEP
        # or by hand: outline = [[x, y], ...]; cutouts = [ {circle = [x, y, d]}, {rect = [x, y, w, h]},
        #             {points = [[x, y], ...]} ]; bend_lines = [[x0, y0, x1, y1]]; mirror = true (flip x: a face
        #             given in the part's frame that is seen from behind)
        [[faces.elements]]       # positions in the face's frame as seen: X right, Y up, from its lower-left datum
        kind = "text"; text = "POWER"; x = 20; y = 30; size = 3.0 (cap height); anchor = "l|m|r"; ink = "Black"
               font = "C:/path/font.ttf" (default: the DejaVu Sans shipped with matplotlib); spacing = 0.0
        kind = "line"; from = [x, y]; to = [x, y]; width = 0.4; ink = "..."
        kind = "rect"; x, y, w, h (x, y = lower-left); r = 0; stroke = 0.3 (a frame; without it: filled); ink
        kind = "circle"; x, y, d; stroke (optional); ink          kind = "polygon"; points = [[x, y], ...]; ink
    Needs ezdxf, shapely, numpy, matplotlib (for the letter outlines), scipy.

Config keys
    mech.toml  [sheet] supplier; [sheet.margins] silk = 0.0
               [silk] outline_layer = "OUTLINE_NOT_PRINTED", bend_layer = "BEND_LINE_NOT_PRINTED" (both must end in
                      non_print_suffix = "_NOT_PRINTED"), outline_colour = 3 (green), bend_colour = 2 (yellow)
                      (AutoCAD colour indexes 1..255; 0 and 7 and the white indexes are refused),
                      text_gap = (min_gap + margin + 0.05: letters are moved apart to keep it)
    capability sheet  [finishes] inks; [ink_rgb]; [silk_rules] min_text_height, min_line, min_gap, edge_clearance

Exit codes
    0 the file was written and every rule row passes     1 an ink is not on the chart, or a reference layer is
    refused (index 7 or 0 or white, the colour of an ink layer of the same file, a name that does not end in
    _NOT_PRINTED): nothing written; or a rule row failed     2 could not run (no artwork, no capability sheet, a
    library or a font file missing, a colour value that is no index 1..255)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import json
import math
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

OUTLINE, BEND = "OUTLINE_NOT_PRINTED", "BEND_LINE_NOT_PRINTED"
SUFFIX = "_NOT_PRINTED"
# The reference layers' own colours (AutoCAD colour indexes): green cut edges, yellow dashed bend lines. Never index 7.
OUTLINE_ACI, BEND_ACI = 3, 2
ACI_NAMES = {1: "red", 2: "yellow", 3: "green", 4: "cyan", 5: "blue", 6: "magenta"}
# DXF header variables that name the writing tool or a person; blanked so that the file carries neither ($FINGERPRINTGUID and
# $VERSIONGUID are random identifiers, not names, and stay)
HEADER_NAMING = ("$LASTSAVEDBY", "$AUTHOR", "$LASTUPDATEDBY", "$CREATEDBY", "$PROJECTNAME")


def blank_header(doc) -> list:
    """Blank the header variables of an ezdxf document that name the writing tool or a user: the fixed list HEADER_NAMING, and any
    other text variable that contains the library's name. Returns the names that held something."""
    done = []
    names = list(doc.header.varnames())
    for k in names:
        v = doc.header.get(k)
        if isinstance(v, str) and v and (k in HEADER_NAMING or "ezdxf" in v.lower()) and "GUID" not in k:
            doc.header[k] = ""
            done.append(k)
    for k in HEADER_NAMING:                           # a name the header does not hold yet is not created
        if k in doc.header and doc.header.get(k):
            doc.header[k] = ""
            done.append(k)
    return done


def layer_name(ink):
    return "_".join(str(ink).upper().split())


def hex_rgb(h):
    h = str(h).strip().lstrip("#")
    if len(h) != 6:
        raise mc.MechError(f"[ink_rgb]: {h!r} is not a colour like #1A2B3C")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def nearest_aci(rgb, exclude=()):
    """The indexed colour nearest to rgb, never 7 (a viewer shows 7 as white or black), never 0 / 256, and never one of
    `exclude` (the reference layers' indexes: an ink must not share an index with a reference layer)."""
    from ezdxf import colors

    best = None
    for i in range(1, 256):
        if i == 7 or i in exclude:
            continue
        c = colors.aci2rgb(i)
        d = (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2
        if best is None or d < best[0]:
            best = (d, i)
    return best[1]


# ---------------------------------------------------------------- reference layers -----------------------------------
def aci_rgb(i):
    from ezdxf import colors

    c = colors.aci2rgb(i)
    return (c[0], c[1], c[2])


def colour_index(sk, key, default):
    """An AutoCAD colour index from [silk] <key>. A value that is no whole number 1..255 (or 0) is a bad configuration
    (could not run), not a refusal of the artwork."""
    v = sk.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255:
        raise mc.MechError(f"[silk] {key} = {v!r} is no AutoCAD colour index (a whole number 1..255; 3 = green, 2 = yellow)")
    return v


def aci_text(i):
    return f"index {i}" + (f" ({ACI_NAMES[i]})" if i in ACI_NAMES else "")


def reference_problems(sk, inks, mode):
    """(outline index, bend index, problems) of the two reference layers. A problem REFUSES the file (nothing is written):
    a colour that is index 7 or 0 or shows white (a plain viewer draws it as a white ink), a colour equal to the colour of an
    ink layer of the same file (`inks` = {ink name: rgb}), a layer name that does not end in the non-print suffix, or two
    layers that are one. With `--outline none` there are no reference layers and nothing to refuse."""
    o_aci = colour_index(sk, "outline_colour", OUTLINE_ACI)
    b_aci = colour_index(sk, "bend_colour", BEND_ACI)
    if mode == "none":
        return o_aci, b_aci, []
    suffix = str(sk.get("non_print_suffix", SUFFIX))
    lay_out, lay_bend = sk.get("outline_layer", OUTLINE), sk.get("bend_layer", BEND)
    probs = []
    for lay, aci, key in ((lay_out, o_aci, "outline_colour"), (lay_bend, b_aci, "bend_colour")):
        if not str(lay).upper().endswith(suffix.upper()):
            probs.append(f"layer {lay}: the name of a reference layer must end in {suffix} (the factory then knows it is not printed)")
        if aci in (0, 7):
            probs.append(f"layer {lay}: [silk] {key} = {aci} is the default index, which a plain viewer draws WHITE and a factory "
                         "reads as a white ink; use another index (3 green, 2 yellow)")
        elif aci_rgb(aci) == (255, 255, 255):
            probs.append(f"layer {lay}: [silk] {key} = {aci} shows white, read as a white ink; use another index")
        for ink, rgb in inks.items():
            if aci not in (0, 7) and tuple(rgb) == aci_rgb(aci):
                probs.append(f"layer {lay}: its colour, {aci_text(aci)}, is also the colour of the ink layer {layer_name(ink)} "
                             f"({ink}); set [silk] {key} to an index no ink uses")
    if str(lay_out).upper() == str(lay_bend).upper():
        probs.append("[silk] outline_layer and bend_layer are the same layer")
    clash = [layer_name(i) for i in inks if layer_name(i).upper() in (str(lay_out).upper(), str(lay_bend).upper())]
    if clash:
        probs.append("a reference layer has the name of an ink layer: " + ", ".join(clash))
    return o_aci, b_aci, probs


# ---------------------------------------------------------------- letters --------------------------------------------
_CAP = {}


def _font_prop(font):
    from matplotlib.font_manager import FontProperties, findfont

    if font:
        if not os.path.isfile(font):
            raise mc.MechError(f"font file not found: {font}")
        return FontProperties(fname=font)
    return FontProperties(fname=findfont(FontProperties(family="DejaVu Sans")))


def _glyph(ch, prop, size=1000.0):
    """(geometry at `size` units per em, advance) of one character."""
    from matplotlib.textpath import TextPath, TextToPath
    from shapely.geometry import Polygon

    g = Polygon()
    if not ch.isspace():
        try:
            rings = TextPath((0, 0), ch, size=size, prop=prop).to_polygons(closed_only=True)
        except (AttributeError, ValueError):       # a character without an outline
            rings = []
        for ring in rings:
            if len(ring) >= 4:
                g = g.symmetric_difference(Polygon(ring).buffer(0))
    adv = TextToPath().get_text_width_height_descent(ch, prop, ismath=False)[0] * size / prop.get_size_in_points()
    return g, adv


def text_geom(s, x, y, cap, prop, anchor="l", spacing=0.0, min_gap=0.0):
    """A text line as one geometry: baseline y, anchor x, cap height `cap` mm; every letter at least min_gap from
    the one before. Returns (geometry, measured cap height)."""
    from shapely import affinity
    from shapely.ops import unary_union

    key = prop.get_file()
    if key not in _CAP:
        hg, _a = _glyph("H", prop)
        _CAP[key] = hg.bounds[3] - hg.bounds[1]
    k = cap / _CAP[key]
    shapes, pen, prev = [], 0.0, None
    for ch in s:
        g, adv = _glyph(ch, prop)
        if not g.is_empty:
            q = affinity.translate(affinity.scale(g, k, k, origin=(0, 0)), pen, 0)
            if prev is not None and min_gap > 0:
                d = q.distance(prev)
                if d < min_gap:
                    q = affinity.translate(q, min_gap - d + 0.005, 0)
                    pen += min_gap - d + 0.005
            shapes.append(q)
            prev = q
        else:
            prev = None
        pen += adv * k + spacing
    if not shapes:
        raise mc.MechError(f"text {s!r}: the font has no outline for it")
    width = max(q.bounds[2] for q in shapes)
    dx = {"l": 0.0, "m": -width / 2, "r": -width}[anchor]
    geom = affinity.translate(unary_union(shapes), x + dx, y)
    caps = [q.bounds[3] - q.bounds[1] for q, ch in zip(shapes, [c for c in s if not c.isspace()]) if ch.isupper() or ch.isdigit()]
    return geom, (max(caps) if caps else max(q.bounds[3] - q.bounds[1] for q in shapes))


def element_geom(el, min_gap):
    """(geometry, extra info) of one artwork element in the face's frame."""
    from shapely.geometry import LineString, Point, Polygon, box

    kind = el.get("kind")
    if kind == "text":
        g, cap = text_geom(str(el["text"]), float(el["x"]), float(el["y"]), float(el["size"]), _font_prop(el.get("font")),
                           el.get("anchor", "l"), float(el.get("spacing", 0.0)), min_gap)
        return g, {"text": str(el["text"]), "cap_height": round(cap, 3)}
    if kind == "line":
        return LineString([el["from"], el["to"]]).buffer(float(el["width"]) / 2, cap_style=2, join_style=2), {}
    if kind == "rect":
        g = box(float(el["x"]), float(el["y"]), float(el["x"]) + float(el["w"]), float(el["y"]) + float(el["h"]))
        r = float(el.get("r", 0))
        if r > 0:
            g = g.buffer(-r).buffer(r, 16)
        if el.get("stroke"):
            g = g.buffer(float(el["stroke"]) / 2, join_style=2 if r == 0 else 1).difference(
                g.buffer(-float(el["stroke"]) / 2, join_style=2 if r == 0 else 1))
        return g, {}
    if kind == "circle":
        g = Point(float(el["x"]), float(el["y"])).buffer(float(el["d"]) / 2, 48)
        if el.get("stroke"):
            g = g.buffer(float(el["stroke"]) / 2, 48).difference(g.buffer(-float(el["stroke"]) / 2, 48))
        return g, {}
    if kind == "polygon":
        return Polygon(el["points"]).buffer(0), {}
    raise mc.MechError(f"unknown element kind {kind!r} (text, line, rect, circle, polygon)")


# ---------------------------------------------------------------- faces ----------------------------------------------
def face_shape(fc, base):
    """{"outline": [rings], "cutouts": [("circle", x, y, d) | ("ring", pts)], "bends": [(p, q)]} in the face frame."""
    out = {"outline": [], "cutouts": [], "bends": []}
    if fc.get("features"):
        fp = fc["features"] if os.path.isabs(fc["features"]) else os.path.join(base, fc["features"])
        if not os.path.isfile(fp):
            raise mc.MechError(f"face {fc.get('name')}: features file not found: {fp}")
        feats = mc.load_json(fp)
        panel = next((p for p in feats["panels"] if p["name"] == fc.get("panel", fc.get("name"))), None)
        if panel is None:
            raise mc.MechError(f"face {fc.get('name')}: no panel {fc.get('panel', fc.get('name'))!r} in {fp}")
        out["outline"] = [f["path"] for f in panel["faces"]]
        for f in panel["features"]:
            out["cutouts"].append(("circle", f["u"], f["v"], f["d"]) if f["kind"] == "hole" else ("ring", f["path"]))
        for p in panel["patterns"]:
            out["cutouts"] += [("circle", u, v, p["d"]) for u, v in p["holes"]]
        for h in panel["hardware"]:
            if h.get("hole") or h.get("model_d"):
                out["cutouts"].append(("circle", h["u"], h["v"], h.get("model_d") or h["hole"]))
        out["bends"] = [(b["p"], b["q"]) for b in panel["bend_lines"]]
    else:
        if not fc.get("outline"):
            raise mc.MechError(f"face {fc.get('name')}: give 'features' + 'panel', or an 'outline' point list")
        xs = [p[0] for p in fc["outline"]]
        w0, w1 = min(xs), max(xs)
        mir = bool(fc.get("mirror"))

        def mx(x):
            return (w0 + w1 - x) if mir else x

        out["outline"] = [[[mx(x), y] for x, y in fc["outline"]]]
        for c in fc.get("cutouts", []):
            if "circle" in c:
                out["cutouts"].append(("circle", mx(c["circle"][0]), c["circle"][1], c["circle"][2]))
            elif "rect" in c:
                x, y, w, h = c["rect"]
                x = mx(x) - (w if mir else 0)
                out["cutouts"].append(("ring", [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]))
            else:
                out["cutouts"].append(("ring", [[mx(x), y] for x, y in c["points"]]))
        out["bends"] = [([mx(b[0]), b[1]], [mx(b[2]), b[3]]) for b in fc.get("bend_lines", [])]
    return out


def _ring_lines(msp, pts, dx, layer):
    """A closed ring as separate LINE entities (collinear points merged): never a closed polyline."""
    from shapely.geometry import LinearRing

    ring = LinearRing(pts).simplify(0.002)
    cs = list(ring.coords)
    for a, b in zip(cs[:-1], cs[1:]):
        msp.add_line((a[0] + dx, a[1]), (b[0] + dx, b[1]), dxfattribs={"layer": layer})


def write_dxf(path, part, faces, inks, mode, lay_out=OUTLINE, lay_bend=BEND, out_aci=OUTLINE_ACI, bend_aci=BEND_ACI):
    """faces: [{"shape", "dx", "geoms": {ink: geometry in face frame}}]; inks: {name: rgb}. The reference layers get their own
    colour indexes (out_aci, bend_aci), set by layer: never 7 or 0 (raises), entities BYLAYER."""
    import ezdxf
    from ezdxf import colors, units

    if mode != "none" and (out_aci in (0, 7) or bend_aci in (0, 7)):
        raise mc.MechError("a reference layer must not use colour index 7 or 0: a plain viewer shows it as a white ink")
    doc = ezdxf.new("R2010", setup=["linetypes"])
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    blank_header(doc)                  # the library writes its own name into $LASTSAVEDBY: no tool name, no user name in the file
    msp = doc.modelspace()
    if mode != "none":
        doc.layers.add(lay_out, color=out_aci, linetype="Continuous")
        doc.layers.add(lay_bend, color=bend_aci, linetype="DASHED")
    layers = {}
    for ink, rgb in inks.items():
        lay = layer_name(ink)
        aci = nearest_aci(rgb, exclude=(out_aci, bend_aci) if mode != "none" else ())
        doc.layers.add(lay, color=aci, true_color=colors.rgb2int(rgb))
        layers[lay] = {"ink": ink, "rgb": "#%02X%02X%02X" % rgb, "aci": aci}
    for fc in faces:
        dx, shp = fc["dx"], fc["shape"]
        if mode == "open":
            for ring in shp["outline"]:
                _ring_lines(msp, ring, dx, lay_out)
            for c in shp["cutouts"]:
                if c[0] == "circle":
                    for a0 in (0, 180):
                        msp.add_arc((c[1] + dx, c[2]), c[3] / 2, a0, a0 + 180, dxfattribs={"layer": lay_out})
                else:
                    _ring_lines(msp, c[1], dx, lay_out)
            for p, q in shp["bends"]:
                msp.add_line((p[0] + dx, p[1]), (q[0] + dx, q[1]), dxfattribs={"layer": lay_bend})
        elif mode == "corners":
            x0, y0, x1, y1 = fc["bbox"]
            tk = 5.0
            for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
                msp.add_line((cx + dx, cy), (cx + dx + sx * tk, cy), dxfattribs={"layer": lay_out})
                msp.add_line((cx + dx, cy), (cx + dx, cy + sy * tk), dxfattribs={"layer": lay_out})
        for ink, geom in fc["geoms"].items():
            lay = layer_name(ink)
            rgb, aci = inks[ink], layers[lay]["aci"]
            att = {"layer": lay, "color": aci, "true_color": colors.rgb2int(rgb)}
            for g in (geom.geoms if hasattr(geom, "geoms") else [geom]):
                if g.geom_type != "Polygon" or g.is_empty:
                    continue
                ext = [(x + dx, y) for x, y in g.exterior.coords]
                msp.add_lwpolyline(ext[:-1], close=True, dxfattribs=att)
                h = msp.add_hatch(color=aci, dxfattribs={"layer": lay})
                h.set_solid_fill(color=aci, rgb=colors.RGB(*rgb))
                h.paths.add_polyline_path(ext[:-1], is_closed=True, flags=1)
                for r in g.interiors:
                    hole = [(x + dx, y) for x, y in r.coords]
                    msp.add_lwpolyline(hole[:-1], close=True, dxfattribs=att)
                    h.paths.add_polyline_path(hole[:-1], is_closed=True, flags=16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc.saveas(path)
    return layers


# ---------------------------------------------------------------- main -----------------------------------------------
def load_art(path):
    if path.lower().endswith(".json"):
        return mc.load_json(path)
    return mc.load_toml(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="artwork description -> print DXF, one layer per chart ink")
    mc.add_std_args(ap)
    ap.add_argument("--art", required=False)
    ap.add_argument("--capability")
    ap.add_argument("--outline", choices=("open", "corners", "none"), default="open")
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    for lib in ("ezdxf", "shapely", "numpy", "matplotlib", "scipy"):
        mc.require_module(lib, "silk_dxf.py")
    import matplotlib
    matplotlib.use("Agg")
    import sheet_dfm

    if not args.art or not os.path.isfile(args.art):
        print(f"could not run: no artwork file ({args.art}); give --art <file.toml|json>", file=sys.stderr)
        return 2
    cap_path = sheet_dfm.find_capability(job, args.capability)
    if not cap_path or not os.path.isfile(cap_path):
        print(f"could not run: no capability sheet ({cap_path}); give --capability or set [sheet] supplier",
              file=sys.stderr)
        return 2
    rows = mc.Rows()
    try:
        cap = mc.load_toml(cap_path)
        art = load_art(os.path.abspath(args.art))
        part = art.get("part") or os.path.splitext(os.path.basename(args.art))[0]
        chart = {str(i): i for i in (cap.get("finishes") or {}).get("inks") or []}
        rgbs = cap.get("ink_rgb") or {}
        used = []
        for fc in art.get("faces", []):
            for el in fc.get("elements", []):
                if el.get("ink") not in used:
                    used.append(el.get("ink"))
        bad = [i for i in used if i not in chart]
        norgb = [i for i in used if i in chart and i not in rgbs]
        rows.add(f"SD-{part}-01", f"silk:{part}", "every ink of the artwork is a name on the supplier's ink chart",
                 "inks: " + ", ".join(str(i) for i in used) + ("; NOT on the chart: " + ", ".join(str(i) for i in bad)
                                                             if bad else "")
                 + ("; no [ink_rgb] colour for: " + ", ".join(norgb) if norgb else ""),
                 "chart names only: " + ", ".join(chart), "pass" if not bad and not norgb and used else "fail")
        if bad or norgb or not used:
            rows.write(job.out, "silk_dxf.py", [args.art, cap_path])
            rows.print_table(only_bad=True)
            print("REFUSED: nothing was written. Use an ink name from the chart (the capability sheet's [finishes] "
                  "inks), exactly as written there.")
            print(rows.headline())
            return 1
        inks = {i: hex_rgb(rgbs[i]) for i in used}
        sk = job.cfg.get("silk", {})
        o_aci, b_aci, ref_probs = reference_problems(sk, inks, args.outline)
        lay_out, lay_bend = sk.get("outline_layer", OUTLINE), sk.get("bend_layer", BEND)
        if args.outline == "none":
            ref_value, ref_verdict = "no reference layers (--outline none)", "na"
        else:
            ref_value = ("; ".join(ref_probs) if ref_probs else
                         f"{lay_out}: {aci_text(o_aci)}, continuous; {lay_bend}: {aci_text(b_aci)}, dashed; "
                         "no ink layer of this file has either colour")
            ref_verdict = "fail" if ref_probs else "pass"
        rows.add(f"SD-{part}-REF", f"silk:{part}", "the reference layers (outline, bend lines) have a colour of their own: "
                 "never index 7 or 0, never an ink's colour, names end in " + str(sk.get("non_print_suffix", SUFFIX)),
                 ref_value, "own colour by layer, not 7 / 0 / white, not an ink's colour; open lines and arcs only", ref_verdict)
        if ref_probs:
            rows.write(job.out, "silk_dxf.py", [args.art, cap_path])
            rows.print_table(only_bad=True)
            print("REFUSED: nothing was written. The reference layers must not look like an ink: set [silk] outline_colour / "
                  "bend_colour to colour indexes that are not 7, not 0 and not the colour of an ink used in this file.")
            print(rows.headline())
            return 1
        margin = float((job.cfg.get("sheet", {}).get("margins") or {}).get("silk", 0))
        srules = cap.get("silk_rules") or {}
        text_gap = float(sk.get("text_gap", float(srules.get("min_gap", 0)) + margin + (0.05 if srules.get("min_gap") else 0)))
        base = job.project
        faces, cursor, gap = [], 0.0, float(art.get("gap", 20.0))
        man_faces = []
        n_el = 0
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        for fc in art.get("faces", []):
            shp = face_shape(fc, base)
            xs = [p[0] for r in shp["outline"] for p in r]
            ys = [p[1] for r in shp["outline"] for p in r]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            dx = cursor - bbox[0]
            geoms, els = {}, []
            for el in fc.get("elements", []):
                n_el += 1
                g, extra = element_geom(el, text_gap)
                geoms.setdefault(el["ink"], []).append(g)
                b = g.bounds
                els.append({"id": el.get("id") or f"E{n_el}", "kind": el["kind"], "ink": el["ink"],
                            "bbox": [round(v, 3) for v in b],
                            "bbox_file": [round(b[0] + dx, 3), round(b[1], 3), round(b[2] + dx, 3), round(b[3], 3)],
                            **extra})
            geoms = {k: unary_union(v) for k, v in geoms.items()}
            faces.append({"shape": shp, "dx": dx, "geoms": geoms, "bbox": bbox})
            cuts = []
            for c in shp["cutouts"]:
                if c[0] == "circle":
                    cuts.append([[round(c[1] + c[3] / 2 * math.cos(a * math.pi / 24), 3),
                                  round(c[2] + c[3] / 2 * math.sin(a * math.pi / 24), 3)] for a in range(48)])
                else:
                    cuts.append(c[1])
            man_faces.append({"name": fc.get("name", f"FACE {len(faces)}"), "offset": [round(dx, 3), 0.0],
                              "bbox": [round(v, 3) for v in bbox], "outline": shp["outline"], "cutouts": cuts,
                              "elements": els})
            cursor += (bbox[2] - bbox[0]) + gap
        d = os.path.join(job.out, "silk")
        dxf = os.path.join(d, f"{part}_silk.dxf")
        layers = write_dxf(dxf, part, faces, inks, args.outline, lay_out, lay_bend, o_aci, b_aci)
        man = {"script": "silk_dxf", "part": part, "dxf": os.path.basename(dxf), "inks": list(inks), "layers": layers,
               "outline_layer": lay_out if args.outline != "none" else None,
               "bend_layer": lay_bend if args.outline == "open" else None, "outline_mode": args.outline,
               "reference_layers": ({lay_out: {"colour_index": o_aci, "linetype": "Continuous", "printed": False},
                                     lay_bend: {"colour_index": b_aci, "linetype": "DASHED", "printed": False}}
                                    if args.outline != "none" else {}),
               "faces": man_faces}
        jpath = os.path.join(d, f"{part}_silk.json")
        mc.atomic_write(jpath, json.dumps(man, indent=1) + "\n")
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    except KeyError as e:
        print(f"could not run: the artwork file lacks the key {e}", file=sys.stderr)
        return 2
    rows.add(f"SD-{part}-02", f"silk:{part}", "one layer per ink, named and coloured as the chart ink",
             "; ".join(f"{k} = {v['ink']} {v['rgb']}" for k, v in layers.items()), "layer name = chart name, true colour",
             "pass")
    if args.outline == "open":
        for rid, check, value, rule, verdict in sheet_dfm.measure_silk(dxf, jpath, part, cap, sk, margin):
            rows.add(rid.replace("DFM-", "SD-"), f"silk:{part}", check, value, rule, verdict)
    else:
        rows.add(f"SD-{part}-03", f"silk:{part}", "rule measure on the written file",
                 f"not possible with --outline {args.outline}: the file has no face outline", "run with --outline open",
                 "could_not_run")
    rows.write(job.out, "silk_dxf.py", [args.art, cap_path, dxf])
    rows.print_table(only_bad=True)
    print(f"{part}: {n_el} elements on {len(faces)} face(s), inks {', '.join(inks)} -> {dxf}")
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
