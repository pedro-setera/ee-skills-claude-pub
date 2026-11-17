"""A KiCad board from a netlist: outline, holes with keep-outs, free bands, layer count, footprints, net classes.

What it does (a library for a project's src/build_board.py; nothing here is board-specific)
    load_mech(source)        the mechanical input: outline, mounting holes, keep-outs (mech/outline.json or a dict)
    new_board(netlist, mech) a pcbnew BOARD with the copper layer count and thickness, the board-setup minimums,
                             the outline on Edge.Cuts, every net, every part of the netlist as its footprint
                             (reference, value, fields, the link to its symbol, fitted or not), each mounting hole
                             with its keep-out as a rule area, and the free bands of a board held by slots or rails
                             as rule areas (no part, no pad, no copper). Parts wait beside the board until
                             place.py places them. A footprint that cannot be loaded, or a pin of a symbol
                             that has no pad in its footprint, stops the build with its name: no connection
                             of the schematic is dropped silently.
    save(board, path, ...)   saves through kicad_io (lock, atomic write) and writes the minimums, the violation
                             severities and the net classes into the project file, a custom rule file and a layer
                             stack when given. Sections of an existing project file that belong to the schematic
                             are kept. (KiCad 10 writes no project file with the first save of a new board:
                             the board is then loaded and saved once more.)
    rule_area(board, ...)    a keep-out area;  class_rules(netclasses)  rule-file text: one minimum width per class
    net(board, name)         a net by its full name or by its name without the sheet path

Why it exists
    A board typed by hand from a drawing can end up smaller than its parts, or with parts in the rail zone of a
    slide-in case. A board built by a script from the mechanical file and the netlist cannot drift from either,
    and it can be built again.

Where it stops
    Top-side parts only (flip a part yourself with pcbnew). Through vias only. The layer stack is written as a
    table you give; nothing is calculated from it. Footprints come from the project's fp-lib-table, the libraries
    you name and KiCad's stock folder; the user's global library table is not read.

The mechanical input (mm, KiCad's frame: x right, y down, seen from the top side)
    {"outline": {"rect": [x0, y0, x1, y1], "corner_radius": 1.0}          or {"polygon": [[x, y], ...], ...}
     "holes":   [{"name": "H1", "x": 3.5, "y": 3.5, "d": 3.2, "keepout_d": 7.0,     keep-out: head, stand and tool
                  "plated": false, "pad_d": 6.0, "net": "GND"}],                    pad_d and net: plated holes
     "keepouts": [{"kind": "band", "name": "left rail", "edge": "left", "width": 3.0, "span": [a, b]},
                  {"kind": "band", "name": "...", "line": [x0, y0, x1, y1], "width": 3.0},
                  {"kind": "area", "name": "antenna", "rect": [x0, y0, x1, y1], "no": ["parts", "tracks",
                   "vias", "pour"], "layers": ["F.Cu", "B.Cu"]}]}
    A band is the strip of a board edge that a slot or rail of the case holds (rule MECH-06): kept free of parts,
    pads and copper on both sides here, whatever its "sides" entry says (the simple, conservative reading).
    Bands may also stand in board.toml as [[keepout.band]] with the same keys; when board.toml has any, those
    are used. "area": rect or polygon; "no" defaults to all four; "layers" to every copper layer.

board.toml keys read (all optional): [[keepout.band]] as above; [project] kicad_dir through kicad_io.

A library: no exit codes. What cannot be done raises kicad_io.KicadIOError (exit code 2 under kicad_io.run_main).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import fnmatch
import json
import math
import os
import re
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

if __name__ == "__main__":                      # a library: there is nothing to run
    print(__doc__)
    sys.exit(0)

import pcbnew  # noqa: E402

import kicad_io  # noqa: E402
import sexp  # noqa: E402
from drc_run import WANT_ERROR  # noqa: E402
from layout import board_outline, quiet_wx  # noqa: E402

quiet_wx()                                      # no message box, ever (place, copper and route import this module)

# Board-setup minimums in mm. Common values with margin above the manufacturer's limits: read the live capability
# page for the layer count of the day and pass your own.
RULES = {"clearance": 0.15, "track": 0.15, "via_d": 0.6, "via_drill": 0.3, "via_annular": 0.13,
         "hole_to_hole": 0.5, "hole_clearance": 0.25, "edge": 0.3, "silk_text": 1.0, "silk_line": 0.16}
# checks that must be errors on a board that goes to assembly (drc_run.py lists what a project has lower)
ERRORS = tuple(WANT_ERROR) + ("connection_width",)
EDGES = ("left", "right", "top", "bottom")
_SCHEMATIC_KEYS = ("schematic", "sheets", "text_variables", "libraries", "erc", "cvpcb")


def iu(v: float) -> int:
    return pcbnew.FromMM(float(v))


def mm(v: int) -> float:
    return pcbnew.ToMM(v)


def pt(x: float, y: float):
    return pcbnew.VECTOR2I(iu(x), iu(y))


def circle(cx: float, cy: float, d: float, n: int = 64) -> list:
    """A polygon around the circle of diameter d (its flats lie on the circle, so nothing inside is left out)."""
    r = d / 2 / math.cos(math.pi / n)
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def rect(x0: float, y0: float, x1: float, y1: float) -> list:
    return [(min(x0, x1), min(y0, y1)), (max(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1)),
            (min(x0, x1), max(y0, y1))]


def natural(s: str) -> list:
    """Sort key: R2 before R10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def in_poly(x: float, y: float, poly: list) -> bool:
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


# ---- the mechanical input ----------------------------------------------------------------------------------------------
class Mech:
    """Outline, holes and keep-outs of a board. outline: corner points (before rounding); radius; bbox
    (x0, y0, x1, y1); holes: dicts name, x, y, d, keepout_d, plated, pad_d, net; bands: dicts name, width, poly
    (the strip itself) and area (the strip, reaching 0.5 mm past the edge); areas: dicts name, poly, no, layers;
    notes: what was assumed."""

    def __init__(self, data: dict, bands: list | None = None):
        self.notes: list[str] = []
        o = data.get("outline")
        if not isinstance(o, dict) or not (o.get("rect") or o.get("polygon")):
            raise kicad_io.KicadIOError('mechanical input: "outline" needs "rect": [x0, y0, x1, y1] or "polygon"')
        try:
            self.outline = rect(*[float(v) for v in o["rect"]]) if o.get("rect") else \
                [(float(x), float(y)) for x, y in o["polygon"]]
            self.radius = float(o.get("corner_radius", 0.0))
        except (TypeError, ValueError):
            raise kicad_io.KicadIOError("mechanical input: the outline is not a list of numbers") from None
        if len(self.outline) < 3:
            raise kicad_io.KicadIOError("mechanical input: the outline needs three corners or more")
        xs, ys = [p[0] for p in self.outline], [p[1] for p in self.outline]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.holes = []
        for i, h in enumerate(data.get("holes", [])):
            try:
                hole = {"name": str(h.get("name", f"H{i + 1}")), "x": float(h["x"]), "y": float(h["y"]),
                        "d": float(h["d"]), "plated": bool(h.get("plated", False)), "net": h.get("net")}
            except (KeyError, TypeError, ValueError):
                raise kicad_io.KicadIOError(f"mechanical input: hole {i + 1} needs x, y and d (mm)") from None
            hole["pad_d"] = float(h.get("pad_d", hole["d"] + 1.6))
            if h.get("keepout_d") is None:
                self.notes.append(f"hole {hole['name']}: no keepout_d given (screw head, stand and tool decide "
                                  "it); only the hole itself is kept free")
            hole["keepout_d"] = float(h.get("keepout_d") or hole["d"])
            self.holes.append(hole)
        raw = data.get("keepouts", [])
        raw = [k for k in raw if isinstance(k, dict)] if isinstance(raw, list) else []
        band_src = bands if bands else [k for k in raw if k.get("kind", "band") == "band"
                                        and ("edge" in k or "line" in k)]
        self.bands = [self._band(i, k) for i, k in enumerate(band_src)]
        self.areas = []
        for i, k in enumerate(k for k in raw if k.get("kind") == "area"):
            poly = rect(*k["rect"]) if k.get("rect") else [(float(x), float(y)) for x, y in k.get("polygon", [])]
            if len(poly) < 3:
                raise kicad_io.KicadIOError(f"mechanical input: keep-out area {i + 1} needs rect or polygon")
            self.areas.append({"name": str(k.get("name", f"area {i + 1}")), "poly": poly,
                               "no": set(k.get("no", ("parts", "tracks", "vias", "pour"))),
                               "layers": k.get("layers")})

    def _band(self, i: int, k: dict) -> dict:
        name = str(k.get("name", f"band {i + 1}"))
        try:
            width = float(k["width"])
        except (KeyError, TypeError, ValueError):
            raise kicad_io.KicadIOError(f"keep-out band '{name}': width (mm) is missing") from None
        x0, y0, x1, y1 = self.bbox
        if k.get("line"):
            ln = [float(v) for v in k["line"]]
            if len(ln) != 4:
                raise kicad_io.KicadIOError(f"keep-out band '{name}': line needs [x0, y0, x1, y1]")
        elif k.get("edge") in EDGES:
            e = k["edge"]
            a, b = (y0, y1) if e in ("left", "right") else (x0, x1)
            if k.get("span"):
                a, b = max(a, min(k["span"])), min(b, max(k["span"]))
            ln = {"left": [x0, a, x0, b], "right": [x1, a, x1, b], "top": [a, y0, b, y0], "bottom": [a, y1, b, y1]}[e]
        else:
            raise kicad_io.KicadIOError(f"keep-out band '{name}': give edge (left, right, top, bottom) or line")
        length = math.hypot(ln[2] - ln[0], ln[3] - ln[1])
        if width <= 0 or length <= 0:
            raise kicad_io.KicadIOError(f"keep-out band '{name}': width and length must be positive")
        ux, uy = (ln[2] - ln[0]) / length, (ln[3] - ln[1]) / length
        nx, ny = -uy, ux                                                # the normal that points into the board
        if nx * ((x0 + x1) / 2 - (ln[0] + ln[2]) / 2) + ny * ((y0 + y1) / 2 - (ln[1] + ln[3]) / 2) < 0:
            nx, ny = -nx, -ny

        def strip(out: float) -> list:
            return [(ln[0] - nx * out, ln[1] - ny * out), (ln[2] - nx * out, ln[3] - ny * out),
                    (ln[2] + nx * width, ln[3] + ny * width), (ln[0] + nx * width, ln[1] + ny * width)]
        return {"name": name, "width": width, "poly": strip(0.0), "area": strip(0.5)}


def load_mech(source, settings: dict | None = None) -> Mech:
    """The mechanical input from a dict, a JSON file, or a board folder (then <folder>/mech/outline.json, and the
    [[keepout.band]] entries of its board.toml when there are any)."""
    if isinstance(source, dict):
        return Mech(source, (settings or {}).get("keepout", {}).get("band"))
    path = source
    if os.path.isdir(source):
        path = os.path.join(source, "mech", "outline.json")
        settings = settings if settings is not None else kicad_io.load_settings(source)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise kicad_io.KicadIOError(f"mechanical input {path}: {e}") from None
    return Mech(data, (settings or {}).get("keepout", {}).get("band"))


# ---- pieces of a board -------------------------------------------------------------------------------------------------
def copper_layers(board) -> list[int]:
    """The copper layers of a board, top to bottom (KiCad's layer numbers)."""
    return [lay for lay in pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()).CuStack()]


def layer_id(board, name) -> int:
    """A layer number from its name ("F.Cu", "In1.Cu", "B.Cu", "F.SilkS", ...) or from the number itself."""
    if isinstance(name, int):
        return name
    lay = board.GetLayerID(name)
    if lay < 0:
        raise kicad_io.KicadIOError(f"no such layer: {name}")
    return lay


def net(board, name: str):
    """The net of that name: the full name first, then the name without its sheet path when exactly one net has it."""
    ni = board.FindNet(name)
    if ni is not None:
        return ni
    names = {str(p.GetNetname()) for fp in board.GetFootprints() for p in fp.Pads()}
    hits = sorted(n for n in names if kicad_io.leaf(n) == name)
    if len(hits) != 1:
        raise kicad_io.KicadIOError(f"net '{name}': " + ("not on the board" if not hits else
                                                         "several nets end in that name: " + ", ".join(hits)))
    return board.FindNet(hits[0])


def rule_area(board, poly: list, layers=None, *, tracks: bool = True, vias: bool = True, pour: bool = True,
              footprints: bool = False, pads: bool = False, name: str = ""):
    """A keep-out area (KiCad: rule area) over the polygon. layers: names or numbers, default every copper layer.
    The flags say what is NOT allowed inside. KiCad's DRC enforces it and the zone fill stays out of it."""
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for lay in (layers or copper_layers(board)):
        ls.AddLayer(layer_id(board, lay))
    z.SetLayerSet(ls)
    o = z.Outline()
    o.NewOutline()
    for x, y in poly:
        o.Append(iu(x), iu(y))
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    (getattr(z, "SetDoNotAllowZoneFills", None) or z.SetDoNotAllowCopperPour)(pour)     # KiCad 10 / KiCad 9
    z.SetDoNotAllowFootprints(footprints)
    z.SetDoNotAllowPads(pads)
    z.SetZoneName(name)
    board.Add(z)
    return z


def draw_outline(board, pts: list, radius: float = 0.0, width: float = 0.1) -> None:
    """The outline on Edge.Cuts: straight segments, every corner rounded with `radius` (a true arc)."""
    def shape(kind):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(kind)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(iu(width))
        board.Add(s)
        return s
    n = len(pts)
    ends = []                                                   # per corner: where the edge arrives and leaves
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        a, c = (p0[0] - p1[0], p0[1] - p1[1]), (p2[0] - p1[0], p2[1] - p1[1])
        la, lc = math.hypot(*a), math.hypot(*c)
        if radius <= 0:
            ends.append((p1, p1))
            continue
        a, c = (a[0] / la, a[1] / la), (c[0] / lc, c[1] / lc)
        half = math.acos(max(-1.0, min(1.0, a[0] * c[0] + a[1] * c[1]))) / 2
        t = radius / math.tan(half)                             # corner to the tangent points
        if t > min(la, lc) / 2 + 1e-9:
            raise kicad_io.KicadIOError(f"outline: corner radius {radius} mm does not fit the edge at "
                                        f"({p1[0]:g}, {p1[1]:g})")
        bis = (a[0] + c[0], a[1] + c[1])
        lb = math.hypot(*bis)
        k = radius / math.sin(half) - radius                    # corner to the middle of the arc
        t0, t1 = (p1[0] + a[0] * t, p1[1] + a[1] * t), (p1[0] + c[0] * t, p1[1] + c[1] * t)
        arc = shape(pcbnew.SHAPE_T_ARC)
        arc.SetArcGeometry(pt(*t0), pt(p1[0] + bis[0] / lb * k, p1[1] + bis[1] / lb * k), pt(*t1))
        ends.append((t0, t1))
    for i in range(n):
        s = shape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*ends[i][1]))
        s.SetEnd(pt(*ends[(i + 1) % n][0]))


def outline_polygon(board) -> list:
    """The board outline as drawn on Edge.Cuts: the corner points of its outer contour (arcs as short chords)."""
    ps = board_outline(board)
    if ps is None:
        raise kicad_io.KicadIOError("the board outline on Edge.Cuts is not one closed shape")
    o = ps.Outline(0)
    return [(mm(o.CPoint(i).x), mm(o.CPoint(i).y)) for i in range(o.PointCount())]


def board_only(fp) -> None:
    """Mark a footprint as a feature of the board itself: not in the BOM, not placed, no courtyard asked for."""
    fp.SetBoardOnly(True)
    fp.SetExcludedFromBOM(True)
    fp.SetExcludedFromPosFiles(True)
    fp.SetAllowMissingCourtyard(True)


def hole_footprint(board, name: str, x: float, y: float, d: float, plated: bool = False, pad_d: float = 0.0,
                   net_item=None):
    """A mounting hole that is on the board only (not in the BOM, not placed): one drilled pad."""
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(name)
    fp.SetValue("mounting hole")
    for f in (fp.Reference(), fp.Value()):
        f.SetVisible(False)
        f.SetLayer(pcbnew.F_Fab)
    board_only(fp)
    board.Add(fp)
    fp.SetPosition(pt(x, y))
    p = pcbnew.PAD(fp)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetDrillSize(pcbnew.VECTOR2I(iu(d), iu(d)))
    if plated:
        p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetNumber("1")
        p.SetSize(pcbnew.VECTOR2I(iu(pad_d), iu(pad_d)))
        p.SetLayerSet(pcbnew.PAD.PTHMask())
        if net_item is not None:
            p.SetNet(net_item)
    else:
        p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        p.SetSize(pcbnew.VECTOR2I(iu(d), iu(d)))
        p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
    p.SetPosition(pt(x, y))
    fp.Add(p)
    return fp


# ---- footprints --------------------------------------------------------------------------------------------------------
def footprint_libs(kicad_dir: str | None = None, extra: dict | None = None) -> dict:
    """Where footprint libraries are: {nickname: folder}. From the project's fp-lib-table (kicad_dir), then
    `extra`; a nickname found in neither is looked for in KiCad's stock footprint folder."""
    libs: dict[str, str] = {}
    kc = kicad_io.find_kicad()
    stock = kc.footprints_dir if kc else None
    table = os.path.join(kicad_dir, "fp-lib-table") if kicad_dir else None
    if table and os.path.isfile(table):
        try:
            with open(table, encoding="utf-8") as f:
                tree = sexp.parse(f.read())
        except (OSError, sexp.SexpError) as e:
            raise kicad_io.KicadIOError(f"{table}: {e}") from None
        for lib in sexp.find(tree, "lib"):
            uri = str(sexp.value(lib, "uri", "")).replace("${KIPRJMOD}", kicad_dir)
            if "FOOTPRINT_DIR}" in uri and stock:
                uri = os.path.join(stock, uri.split("}", 1)[1].lstrip("/\\"))
            libs[str(sexp.value(lib, "name", ""))] = os.path.normpath(uri)
    libs.update(extra or {})
    libs[""] = stock or ""
    return libs


def load_footprint(fpid: str, libs: dict):
    """The footprint "Library:Name" from the libraries of footprint_libs(). KicadIOError when it is not there."""
    lib, _, name = fpid.partition(":")
    folder = libs.get(lib) or (os.path.join(libs.get("", ""), lib + ".pretty") if libs.get("") else "")
    fp = None
    if name and folder and os.path.isdir(folder):
        try:
            fp = pcbnew.FootprintLoad(folder, name)
        except Exception:                                       # pcbnew raises its own error types for a bad file
            fp = None
    if fp is None:
        raise kicad_io.KicadIOError(f"footprint '{fpid}' not found" + (f" in {folder}" if folder else
                                                                       ": its library is not known"))
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def silk_minimums(fp, line: float, text: float) -> None:
    """Every silkscreen line of a footprint at least `line` wide and every silkscreen text at least `text` high
    (stock libraries draw thinner lines than the manufacturer prints)."""
    for g in list(fp.GraphicalItems()) + list(fp.GetFields()):
        if g.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        if g.GetClass() in ("PCB_TEXT", "PCB_FIELD"):
            if g.GetTextHeight() < iu(text) - 1:
                g.SetTextSize(pcbnew.VECTOR2I(iu(text), iu(text)))
            if g.GetTextThickness() < iu(line) - 1:
                g.SetTextThickness(iu(line))
        elif g.GetClass() == "PCB_SHAPE" and 0 < g.GetWidth() < iu(line) - 1:
            g.SetWidth(iu(line))


def _symbol_paths(path: str) -> dict:
    """{reference: the footprint's link to its symbol} from the netlist (sheet path + the symbol's identifier)."""
    with open(path, encoding="utf-8") as f:
        tree = sexp.parse(f.read())
    out = {}
    for c in sexp.find(sexp.first(tree, "components"), "comp"):
        own = sexp.first(c, "tstamps")
        out[str(sexp.value(c, "ref", ""))] = str(sexp.value(sexp.first(c, "sheetpath"), "tstamps", "/")) + \
            (str(own[1]) if own and len(own) > 1 else "")
    return out


# ---- the board ---------------------------------------------------------------------------------------------------------
def new_board(netlist, mech: Mech, *, layers: int = 2, thickness: float = 1.6, rules: dict | None = None,
              kicad_dir: str | None = None, libs: dict | None = None, only: list | None = None):
    """A new board (see the head of this file). netlist: a file exported by KiCad (kicadsexpr) or None for a
    board with outline, holes and keep-outs only. kicad_dir: the project's KiCad folder (its fp-lib-table).
    libs: more footprint libraries {nickname: folder}. only: reference patterns; other parts are left out (the
    outline-only board of the board definition takes just the fixed connectors).
    Every footprint that cannot be loaded, and every pin of a symbol that has no pad in its footprint, is named
    in one KicadIOError: nothing is built on a netlist that the footprints cannot carry."""
    r = dict(RULES, **(rules or {}))
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(layers)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(iu(thickness))
    ds.m_MinClearance, ds.m_TrackMinWidth = iu(r["clearance"]), iu(r["track"])
    ds.m_ViasMinSize, ds.m_MinThroughDrill = iu(r["via_d"]), iu(r["via_drill"])
    ds.m_ViasMinAnnularWidth, ds.m_CopperEdgeClearance = iu(r["via_annular"]), iu(r["edge"])
    ds.m_HoleClearance, ds.m_HoleToHoleMin = iu(r["hole_clearance"]), iu(r["hole_to_hole"])
    draw_outline(b, mech.outline, mech.radius)
    nl = kicad_io.read_netlist(netlist) if isinstance(netlist, str) else netlist
    nets = {}
    for name in sorted(nl.nets if nl else []):
        ni = pcbnew.NETINFO_ITEM(b, name)
        b.Add(ni)
        nets[name] = ni
    if nl:
        paths = _symbol_paths(nl.path)
        table = footprint_libs(kicad_dir, libs)
        missing = []
        x0, y0, x1, y1 = mech.bbox
        n_parked = 0
        for ref in sorted(nl.parts, key=natural):
            part = nl.parts[ref]
            if part.exclude_from_board or (only and not any(fnmatch.fnmatchcase(ref, p) for p in only)):
                continue
            try:
                if not part.footprint:
                    raise kicad_io.KicadIOError("no footprint assigned in the schematic")
                fp = load_footprint(part.footprint, table)
            except kicad_io.KicadIOError as e:
                missing.append(f"{ref}: {e}")
                continue
            fp.SetReference(ref)
            fp.SetValue(part.value)
            b.Add(fp)
            fp.SetPosition(pt(x1 + 8 + 7 * (n_parked // 8), y0 + 6 * (n_parked % 8)))     # parked beside the board
            n_parked += 1
            fp.SetPath(pcbnew.KIID_PATH(paths.get(ref, "")))
            fp.SetSheetname(part.sheet)
            fp.SetSheetfile(part.sheet_file)
            for key, val in part.fields.items():
                if val and key not in ("Footprint", "Reference", "Value"):
                    fp.SetField(key, val)
                    f = next((x for x in fp.GetFields() if x.GetName() == key), None)
                    if f is not None and key not in ("Datasheet", "Description"):
                        f.SetVisible(False)
                        f.SetLayer(pcbnew.F_Fab)
            if part.dnp:
                fp.SetDNP(True)
                fp.SetExcludedFromPosFiles(True)
            if part.exclude_from_bom:
                fp.SetExcludedFromBOM(True)
                fp.SetExcludedFromPosFiles(True)
            for p in fp.Pads():
                hit = nl.pins.get((ref, p.GetNumber()))
                if hit:
                    p.SetNet(nets[hit[0]])
            have = {str(p.GetNumber()) for p in fp.Pads()}
            lost = [pin for pin in nl.pins_of(ref) if pin not in have]
            if lost:                                            # a connection of the schematic would vanish silently
                missing.append(f"{ref}: pin {', '.join(lost)} of the symbol has no pad in footprint '{part.footprint}' "
                               f"(its pads: {', '.join(sorted(have - {''}, key=natural))})")
            silk_minimums(fp, r["silk_line"], r["silk_text"])
        if missing:
            raise kicad_io.KicadIOError("the board cannot be built from this netlist:\n  " + "\n  ".join(missing))
    for h in mech.holes:
        fp = b.FindFootprintByReference(h["name"])
        if fp is not None:                                      # the hole is a part of the schematic
            fp.SetPosition(pt(h["x"], h["y"]))
        else:
            hole_footprint(b, h["name"], h["x"], h["y"], h["d"], h["plated"], h["pad_d"],
                           net(b, h["net"]) if h["plated"] and h.get("net") else None)
        # unplated: no copper at all around the screw; plated: the pour may reach the pad, tracks and vias may not
        rule_area(b, circle(h["x"], h["y"], max(h["keepout_d"], h["d"] + 2 * r["hole_clearance"])),
                  pour=not h["plated"], name=f"keep-out {h['name']}")
    for band in mech.bands:
        rule_area(b, band["area"], footprints=True, pads=True, name=f"free band: {band['name']}")
    for a in mech.areas:
        rule_area(b, a["poly"], a["layers"], tracks="tracks" in a["no"], vias="vias" in a["no"],
                  pour="pour" in a["no"], footprints="parts" in a["no"], name=a["name"])
    return b


def class_rules(netclasses: dict) -> str:
    """Custom-rule text for a .kicad_dru file: the minimum track width of each net class that names one
    ({"POWER": {"nets": [...], "track": 0.5, "track_min": 0.4}}; track_min defaults to track). Append it to the
    project's copy of scripts/jlcpcb.kicad_dru in place of that file's EXAMPLE rules."""
    out = []
    for name, c in netclasses.items():
        w = c.get("track_min", c.get("track"))
        if w:
            out += [f'(rule "net class {name}: track width"', "  (severity error)",
                    f"  (condition \"A.NetClass == '{name}'\")", f"  (constraint track_width (min {w:g}mm)))", ""]
    return "\n".join(out)


def _patch_project(tmp_pro: str, real_pro: str, r: dict, netclasses: dict | None) -> None:
    with open(tmp_pro, encoding="utf-8") as f:
        d = json.load(f)
    if os.path.isfile(real_pro):                                # the schematic's part of an existing project stays
        try:
            with open(real_pro, encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, ValueError):
            old = {}
        for k in _SCHEMATIC_KEYS:
            if k in old:
                d[k] = old[k]
        if netclasses is None and "net_settings" in old:
            d["net_settings"] = old["net_settings"]
    d.setdefault("meta", {})["filename"] = os.path.basename(real_pro)
    ds = d.setdefault("board", {}).setdefault("design_settings", {})
    ds.setdefault("rules", {}).update({
        "min_clearance": r["clearance"], "min_track_width": r["track"], "min_via_diameter": r["via_d"],
        "min_through_hole_diameter": r["via_drill"], "min_via_annular_width": r["via_annular"],
        "min_copper_edge_clearance": r["edge"], "min_hole_clearance": r["hole_clearance"],
        "min_hole_to_hole": r["hole_to_hole"], "min_text_height": r["silk_text"],
        "min_text_thickness": r["silk_line"]})
    sev = ds.setdefault("rule_severities", {})
    for k in ERRORS:
        sev[k] = "error"
    if netclasses is not None:
        ns = d.setdefault("net_settings", {})
        default = next((c for c in ns.get("classes", []) if c.get("name") == "Default"), {"name": "Default"})
        default.update(clearance=r["clearance"], track_width=max(r["track"], 0.2), via_diameter=r["via_d"],
                       via_drill=r["via_drill"])
        classes, patterns = [default], []
        for i, (name, c) in enumerate(netclasses.items()):
            classes.append(dict(default, name=name, priority=i, clearance=c.get("clearance", r["clearance"]),
                                track_width=c.get("track", default["track_width"]),
                                via_diameter=c.get("via_d", r["via_d"]), via_drill=c.get("via_drill", r["via_drill"])))
            for pat in c.get("nets", []):
                patterns.append({"netclass": name, "pattern": pat})
                if "/" not in pat and "*" not in pat:           # a plain name also matches the net inside a sheet
                    patterns.append({"netclass": name, "pattern": "*/" + pat})
        ns["classes"], ns["netclass_patterns"] = classes, patterns
    kicad_io.atomic_write(tmp_pro, json.dumps(d, indent=2) + "\n")


def write_stackup(path: str, stack: list, finish: str = "") -> None:
    """Write a layer stack into a saved board file. stack: top to bottom, dicts with "name" (a KiCad layer name
    for copper, mask, paste and silkscreen; "dielectric 1", ... between copper layers), "type" ("copper",
    "core", "prepreg", "Top Solder Mask", ...) and optional "thickness" (mm), "material", "epsilon_r",
    "loss_tangent". Take the numbers from the manufacturer's stack for the layer count of the day."""
    new = ["stackup"]
    for lay in stack:
        item = ["layer", sexp.Q(str(lay["name"])), ["type", sexp.Q(str(lay["type"]))]]
        if lay.get("thickness") is not None:
            item.append(["thickness", f"{lay['thickness']:g}"])
        if lay.get("material"):
            item.append(["material", sexp.Q(str(lay["material"]))])
        for key in ("epsilon_r", "loss_tangent"):
            if lay.get(key) is not None:
                item.append([key, f"{lay[key]:g}"])
        new.append(item)
    if finish:
        new.append(["copper_finish", sexp.Q(finish)])
    new.append(["dielectric_constraints", "no"])
    with kicad_io.ToolLock(path):
        doc = sexp.Document.load(path)
        setup = doc.find_all("setup")
        if not setup:
            raise kicad_io.KicadIOError(f"{path}: no (setup ...) section to put the layer stack in")
        old = sexp.first(setup[0], "stackup")
        if old is not None:
            doc.replace(old, new)
        else:
            doc.insert_before(next(c for c in setup[0] if isinstance(c, list)), new)
        kicad_io.atomic_write(path, doc.text())
        kicad_io.check_complete(path)


def save(board, path: str, rules: dict | None = None, netclasses: dict | None = None, dru: str | None = None,
         stack: list | None = None, finish: str = "") -> None:
    """Save a board made by new_board(): atomically, under the board's lock, with its project file (minimums,
    severities; net classes {name: {"nets": [patterns], "track": w, "clearance": c, "via_d": d, "via_drill": h}}).
    dru: the text of the custom rule file to write beside it. stack, finish: see write_stackup()."""
    r = dict(RULES, **(rules or {}))
    base = path[:-len(".kicad_pcb")] if path.lower().endswith(".kicad_pcb") else os.path.splitext(path)[0]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if dru is not None:
        kicad_io.atomic_write(base + ".kicad_dru", dru)
    done = []

    def patch(tmp: str) -> None:
        _patch_project(tmp, base + ".kicad_pro", r, netclasses)
        done.append(tmp)
    kicad_io.save_board(board, path, patch=patch)
    if not done:                                                # KiCad 10 writes no project file for a board that
        kicad_io.save_board(kicad_io.load_board(path), path, patch=patch)       # never had one: load it, save again
    if stack:
        write_stackup(path, stack, finish)
