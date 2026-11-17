"""Drawing library of a wired schematic: a hand layout written as code.

A per-project script (one function per sheet, kept in the project's src/ folder) places each symbol at explicit
coordinates and draws each wire as an explicit route; this module turns that into a KiCad schematic project.
Coordinates are millimetres on the 1.27 mm grid, y grows downward. See example_two_sheets.py for a worked case.

Why it exists
    A schematic of loose symbols joined only by net labels is electrically valid and useless to a person. It also
    hides errors: on one board two different nodes got the same short label on two sheets and became one net;
    the rule check passed and nobody could see it on the page. So the style is wired blocks, and the lint below
    stops the build on exactly that kind of error.

What the library does on its own
  - part data (symbol, value, footprint, LCSC number, maker part number, fitted or not) comes from ONE table that
    the project gives to Doc(parts=...); nothing is typed on a sheet a second time;
  - a wire that ends on another wire, or a pin that sits on a wire, splits that wire there and gets a junction
    dot, so every connection is an end-to-end contact and every dot marks a real connection;
  - identifiers are derived from names and positions, so a rebuild without changes writes the same files;
  - it works out the nets from the drawing itself (wires, pins, labels, supply symbols) and writes them beside
    the schematic (<project>.model.json); export.py compares them with KiCad's netlist, so the lint's own idea
    of the circuit is proven on every export.

The lint (Doc.lint; Doc.write refuses to write when it finds anything). Seven checks, each a defect that passed
the rule check on a real board:
  1  a net name on more than one sheet that is not declared (Doc(global_nets=..., rails=...));
  2  a declared name that is not used (a stale list hides the next duplicate);
  3  one name on two separately drawn nodes ("two drivers under one name"): they would silently become one net;
  4  a part that goes on the board without a footprint;
  5  a label without a partner (an off-sheet connector on one sheet only, a declared label pair drawn once, a
     label that touches no wire);
  6  a wire end that touches nothing;
  7  a pin left open without a no-connect mark (or a no-connect mark on a connected pin).
Also fatal: a part of the table that is on no sheet. Reported but not fatal (unless write(strict_drawing=True)):
drawing findings such as a wire through a symbol or a text, overlapping texts, four-way junctions, overlapping
wires. None of this replaces looking at the exported sheet.

The parts table: {reference: {"sym": "R", "value": "10k", "footprint": "Resistor_SMD:R_0603_1608Metric",
    "lcsc": "C25804", "mpn": "...", "dnp": False, "in_bom": True, "on_board": True, "datasheet": "", "desc": "",
    "fields": {...}}}. "sym" names a symbol of the Library (symbols.py): a short stock name ("R", "C", "D",
    "LED", ...), any KiCad stock symbol as "Library:Symbol", or a symbol the project added (doc.lib.add). A part
    with "sym": None is not drawn (a cable, a screw: it is in the table for the BOM only).

How a project's script finds this library: the script lives in the project (src/), the library in the skill
    folder, so the script takes the skill's scripts folder from its own argument or setting and puts it on the
    import path before `from schematic import svclib, symbols, export`. It never copies the library.

Limits: one unit per symbol (draw a part with several units as one box); nets cross sheets only through declared
supply symbols and off-sheet connectors (global labels), never through hierarchical pins.

Not a command-line tool. It reads no board.toml: everything comes from the project's script.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import copy
import json
import os
import re
import sys
import textwrap
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import kicad_io  # noqa: E402
from schematic import symbols  # noqa: E402
from sexp import Q, dump  # noqa: E402

G = 1.27                     # grid
TS = 1.27                    # text size of references, values, notes
CHAR = 0.94                  # mean advance of KiCad's stroke font, in text heights
LINE = 1.62                  # line pitch of multi-line text, in text heights
PAPER = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0)}
MARGIN = 17.78               # left edge of headings and notes
TITLE_BLOCK = (110.0, 36.0)  # width and height of KiCad's title block, bottom right inside the border

COL_FRAME = (70, 90, 140)    # block frames and their titles
COL_VOLT = (175, 0, 110)     # expected-voltage tags
COL_SET = (20, 20, 20)       # set-points and remarks beside the parts
COL_TEXT = (30, 30, 30)      # notes
COL_DIM = (95, 95, 95)       # small print
COL_DNP = (190, 30, 30)      # the word DNP beside a part that is not fitted

CHECKS = {1: "net name on several sheets, not declared", 2: "declared name not used", 3: "one name on two nodes",
          4: "part without footprint", 5: "label without partner", 6: "wire end touches nothing",
          7: "open pin without no-connect mark", 0: "parts table"}


class LintError(kicad_io.KicadIOError):
    """The lint found something: the schematic was not written. These are findings (exit code 1), not "could not run"."""
    exit_code = 1

    def __init__(self, findings: list[dict]):
        self.findings = findings
        super().__init__(f"schematic lint: {len(findings)} finding(s); nothing was written\n" +
                         "\n".join(f"  [{f['check']} {CHECKS[f['check']]}] {f['sheet']}: {f['text']}" for f in findings))


def g(v: float) -> str:
    s = f"{round(v, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def on_grid(v: float, step: float = G) -> bool:
    return abs(v / step - round(v / step)) < 1e-6


def tw(s: str, size: float = TS, bold: bool = False) -> float:
    """Estimated width of one line of text."""
    return len(s) * size * CHAR * (1.06 if bold else 1.0)


_UNIT = re.compile(r"(?<=[0-9]) (?=(?:[kM]?Ω|[mµ]?[VAs]\b|[kM]?Hz|[kM]\b|°C|mVpp|ms\b))")


def _wrap(s: str, n: int) -> list[str]:
    """Wrap to n characters without parting a number from its unit ('49.9 Ω' stays on one line)."""
    keep = " "
    return [ln.replace(keep, " ") for ln in textwrap.wrap(_UNIT.sub(keep, s), n)] or [""]


def eff(size=TS, justify=None, hide=False, bold=False, italic=False, color=None):
    font = ["font", ["size", g(size), g(size)]]
    if bold:
        font.append(["bold", "yes"])
    if italic:
        font.append(["italic", "yes"])
    if color:
        font.append(["color", str(color[0]), str(color[1]), str(color[2]), "1"])
    e = ["effects", font]
    if justify:
        e.append(["justify"] + justify.split())
    if hide:
        e.append(["hide", "yes"])
    return e


def stroke(width=0.0, kind="default", color=None):
    s = ["stroke", ["width", g(width)], ["type", kind]]
    if color:
        s.append(["color", str(color[0]), str(color[1]), str(color[2]), "1"])
    return s


def _pt(p) -> tuple:
    return (round(p[0], 4), round(p[1], 4))


class Placed:
    """A symbol on a sheet: where its pins and its body are."""

    def __init__(self, ref, key, x, y, sym, kind="part", net=None):
        self.ref, self.key, self.x, self.y = ref, key, x, y
        self.kind, self.net = kind, net             # kind: "part", "power" (net = its global name) or "flag"
        self.pins = {}
        for p in symbols.pins_of(sym):
            self.pins.setdefault(p["num"], (round(x + p["x"], 4), round(y - p["y"], 4), p["ang"], p["name"], p["type"]))
        bx0, by0, bx1, by1 = symbols.body_box(sym)
        self.box = (x + bx0, y - by1, x + bx1, y - by0)          # sheet coordinates: x0, y0 (top), x1, y1 (bottom)

    def p(self, num):
        """Connection point of pin `num`."""
        try:
            q = self.pins[str(num)]
        except KeyError:
            raise KeyError(f"{self.ref}: no pin {num} (pins: {', '.join(self.pins)})") from None
        return (q[0], q[1])

    def pn(self, name):
        """Connection point of the (first) pin called `name`."""
        for q in self.pins.values():
            if q[3] == name:
                return (q[0], q[1])
        raise KeyError(f"{self.ref}: no pin named {name} (names: {', '.join(q[3] for q in self.pins.values())})")

    def _side(self, pick):
        return pick(((q[0], q[1]) for q in self.pins.values()))

    @property
    def top(self):
        return self._side(lambda it: min(it, key=lambda t: t[1]))

    @property
    def bot(self):
        return self._side(lambda it: max(it, key=lambda t: t[1]))

    @property
    def left(self):
        return self._side(lambda it: min(it, key=lambda t: t[0]))

    @property
    def right(self):
        return self._side(lambda it: max(it, key=lambda t: t[0]))


class Sheet:
    def __init__(self, doc, key, page, name, file, heading):
        self.doc, self.key, self.page, self.name, self.file, self.title = doc, key, page, name, file, heading
        self.uuid = doc.uid("sheet", key)
        self.parts: dict[str, Placed] = {}
        self.sym_nodes: list = []
        self.polylines: list[list[tuple]] = []      # wires as drawn
        self.labels: list[dict] = []                # every net name on a wire: kind, name, pt, pair, dir
        self.label_nodes: list = []
        self.nc_pts: list[tuple] = []
        self.gfx: list = []
        self.text_boxes: list[tuple] = []           # (x0, y0, x1, y1, what) for lint
        self.pwr_n = 0
        self.flg_n = 0
        self.index_at: tuple | None = None          # root sheet: where the sheet index stands
        self._an: dict | None = None

    # ---- symbols ----------------------------------------------------------------------------------------------
    @property
    def path(self):
        root = self.doc.root_uuid
        return f"/{root}" if self is self.doc.root else f"/{root}/{self.uuid}"

    def _sym_node(self, lib_key, ref, x, y, props, pin_nums, in_bom=True, on_board=True, dnp=False):
        u = self.doc.uid(self.key, "sym", ref)
        node = ["symbol", ["lib_id", Q(f"{self.doc.lib.name}:{lib_key}")], ["at", g(x), g(y), "0"], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"],
                ["on_board", "yes" if on_board else "no"], ["dnp", "yes" if dnp else "no"], ["uuid", Q(u)]]
        for (k, v, px, py, hide, just, size, bold) in props:
            node.append(["property", Q(k), Q(v), ["at", g(px), g(py), "0"],
                         eff(size=size, justify=just, hide=hide, bold=bold)])
        for pn in pin_nums:
            node.append(["pin", Q(pn), ["uuid", Q(self.doc.uid(u, "pin", pn))]])
        node.append(["instances", ["project", Q(self.doc.project), ["path", Q(self.path), ["reference", Q(ref)],
                                                                    ["unit", "1"]]]])
        self.sym_nodes.append(node)

    def part(self, ref, x, y, op="", ref_at=None, val_at=None, show_value=True, ref_bold=False, sym=None):
        """Place the part `ref` of the parts table at (x, y), its symbol turned by `op` ('' r90 r180 r270, with a
        leading m for mirrored). ref_at / val_at: (x, y, justify) of the two visible texts. sym: another symbol
        than the table names (rare)."""
        if not (on_grid(x) and on_grid(y)):
            raise ValueError(f"{ref}: off the 1.27 mm grid at {x}, {y}")
        d = self.doc.part_data(ref)
        if not (sym or d["sym"]):
            raise ValueError(f"{ref} has no symbol in the parts table (sym=None): such a part is not drawn")
        if ref in self.doc.placed:
            raise ValueError(f"{ref} is placed twice (sheets {self.doc.placed[ref]} and {self.key})")
        self.doc.placed[ref] = self.key
        key, node = self.doc.lib.get(sym or d["sym"], op)
        pl = Placed(ref, key, x, y, node)
        self.parts[ref] = pl
        self._an = None
        rx, ry, rj = ref_at if ref_at else (pl.box[2] + 1.0, y - 0.35, "left bottom")
        vx, vy, vj = val_at if val_at else (pl.box[2] + 1.0, y + 0.35, "left top")
        props = [("Reference", ref, rx, ry, False, rj, TS, ref_bold),
                 ("Value", d["value"], vx, vy, not show_value, vj, TS, False),
                 ("Footprint", d["footprint"], x, y, True, None, TS, False),
                 ("Datasheet", d["datasheet"], x, y, True, None, TS, False),
                 ("Description", d["desc"], x, y, True, None, TS, False)]
        for k, v in d["fields"].items():
            props.append((k, v, x, y, True, None, TS, False))
        nums = sorted(pl.pins, key=lambda t: (len(t), t))
        self._sym_node(key, ref, x, y, props, nums, in_bom=d["in_bom"], on_board=d["on_board"], dnp=d["dnp"])
        self._note_text(ref, rx, ry, rj, TS, f"{ref} ref")
        if show_value:
            self._note_text(d["value"], vx, vy, vj, TS, f"{ref} value")
        if d["dnp"]:                                # not fitted: KiCad crosses and greys the part; say so in words too
            w = tw(ref, TS, ref_bold)
            rj_ = rj or ""
            if "left" in rj_:
                dx, dj = rx + w + 0.9, "left"
            elif "right" in rj_:
                dx, dj = rx - w - 0.9, "right"
            else:
                dx, dj = rx + w / 2 + 0.9, "left"
            vert = "bottom" if "bottom" in rj_ else ("top" if "top" in rj_ else "")
            self.text("DNP", dx, ry, size=1.1, bold=True, color=COL_DNP, justify=(dj + " " + vert).strip())
        return pl

    def _texts_for(self, node, x, y, txt):
        bx0, by0, bx1, by1 = symbols.body_box(node)
        if txt == "right":
            return (x + bx1 + 1.0, y - 0.35, "left bottom"), (x + bx1 + 1.0, y + 0.35, "left top")
        if txt == "left":
            return (x + bx0 - 1.0, y - 0.35, "right bottom"), (x + bx0 - 1.0, y + 0.35, "right top")
        if txt == "above":
            return (x, y - by1 - 0.9 - TS - 0.7, "bottom"), (x, y - by1 - 0.9, "bottom")
        if txt == "below":
            return (x, y - by0 + 0.9, "top"), (x, y - by0 + 0.9 + TS + 0.7, "top")
        if txt == "split":
            return (x, y - by1 - 0.9, "bottom"), (x, y - by0 + 0.9, "top")
        raise ValueError(f"txt '{txt}': use right, left, above, below or split")

    def two(self, ref, x, y, axis, flip=False, txt=None, **kw):
        """A two-pin part (R, C, L, bead, fuse) on axis 'v' or 'h'. Pin 1 points up ('v') or left ('h'); flip=True
        turns the part round (pin 2 up or left). For a polarised capacitor pin 1 is the positive plate.
        txt: where the reference and value go: 'right' 'left' (vertical part), 'above' 'below' 'split' (horizontal)."""
        if axis not in ("v", "h"):
            raise ValueError(f"{ref}: axis '{axis}' (use 'v' or 'h')")
        op = ("r180" if flip else "") if axis == "v" else ("r270" if flip else "r90")
        _, node = self.doc.lib.get(kw.get("sym") or self.doc.part_data(ref)["sym"], op)
        ra, va = self._texts_for(node, x, y, txt or ("right" if axis == "v" else "above"))
        kw.setdefault("ref_at", ra)
        kw.setdefault("val_at", va)
        return self.part(ref, x, y, op, **kw)

    def diode(self, ref, x, y, k, txt=None, **kw):
        """A diode or LED (pin 1 = cathode, as KiCad draws them) with its cathode pointing 'left' 'right' 'up' 'down'."""
        try:
            op = {"left": "", "right": "r180", "up": "r270", "down": "r90"}[k]
        except KeyError:
            raise ValueError(f"{ref}: cathode direction '{k}' (use left, right, up or down)") from None
        _, node = self.doc.lib.get(kw.get("sym") or self.doc.part_data(ref)["sym"], op)
        ra, va = self._texts_for(node, x, y, txt or ("right" if k in ("up", "down") else "above"))
        kw.setdefault("ref_at", ra)
        kw.setdefault("val_at", va)
        return self.part(ref, x, y, op, **kw)

    def tp(self, ref, x, y, txt="right"):
        """A test point standing on (x, y); its reference and its name (the value: what it measures) beside it."""
        if txt == "right":
            ra, va = (x + 1.5, y - 3.55, "left bottom"), (x + 1.5, y - 3.05, "left top")
        else:
            ra, va = (x - 1.5, y - 3.55, "right bottom"), (x - 1.5, y - 3.05, "right top")
        return self.part(ref, x, y, "", ref_at=ra, val_at=va, ref_bold=True)

    def fet(self, ref, x, y, op="", txt=None, **kw):
        """A transistor in its standard pose (KiCad's: control pin left, drain or collector up). op 'm' puts the
        control pin on the right; 'mr180' turns the part upside down. The texts go to the side away from it."""
        txt = txt or ("left" if op == "m" else "right")
        if txt == "right":
            ra, va = (x + 5.4, y - 0.35, "left bottom"), (x + 5.4, y + 0.35, "left top")
        else:
            ra, va = (x - 5.4, y - 0.35, "right bottom"), (x - 5.4, y + 0.35, "right top")
        kw.setdefault("ref_at", ra)
        kw.setdefault("val_at", va)
        return self.part(ref, x, y, op, **kw)

    def ic(self, ref, x, y, op="", **kw):
        """An IC box (symbols.box / symbols.ic): reference in bold and value above its top-left corner."""
        _, node = self.doc.lib.get(kw.get("sym") or self.doc.part_data(ref)["sym"], op)
        bx0, _, _, by1 = symbols.body_box(node)
        kw.setdefault("ref_at", (x + bx0, y - by1 - 3.2, "left bottom"))
        kw.setdefault("val_at", (x + bx0, y - by1 - 0.9, "left bottom"))
        kw.setdefault("ref_bold", True)
        return self.part(ref, x, y, op, **kw)

    def conn(self, ref, x, y, names, op=""):
        """A connector as a pin list (symbols.conn). (x, y): the pin end of its first row. names: {pin number: text
        written in the box beside that pin}. op 'm': pins to the right (a connector at the left edge)."""
        _, node = self.doc.lib.get(self.doc.part_data(ref)["sym"], op)
        bx0, by0, bx1, by1 = symbols.body_box(node)
        left, right, top = x + bx0, x + bx1, y - by1
        if op == "m":                               # reference and value over the box, on the side away from the pins
            ra, va = (left, top - 2.9, "left bottom"), (left, top - 0.9, "left bottom")
        else:
            ra, va = (right, top - 2.9, "right bottom"), (right, top - 0.9, "right bottom")
        pl = self.part(ref, x, y, op, ref_at=ra, val_at=va, ref_bold=True)
        for num, text in names.items():
            py = pl.p(num)[1]
            if op == "m":
                self.text(text, right - 1.2, py, justify="right")
            else:
                self.text(text, left + 1.2, py, justify="left")
        return pl

    def _power(self, name, x, y, value_at, hide_value):
        if not (on_grid(x) and on_grid(y)):
            raise ValueError(f"supply symbol {name} off the grid at {x}, {y}")
        self.pwr_n += 1
        ref = f"#PWR{self.page:02d}{self.pwr_n:03d}"
        key, node = self.doc.lib.get(name, "")
        pl = Placed(ref, key, x, y, node, kind="power", net=name)
        self.parts[ref] = pl
        self._an = None
        props = [("Reference", ref, x, y, True, None, TS, False),
                 ("Value", name, value_at[0], value_at[1], hide_value, None, TS, False),
                 ("Footprint", "", x, y, True, None, TS, False), ("Datasheet", "", x, y, True, None, TS, False),
                 ("Description", f"Supply {name}", x, y, True, None, TS, False)]
        self._sym_node(key, ref, x, y, props, ["1"], in_bom=False, on_board=False)
        if not hide_value:
            self._note_text(name, value_at[0], value_at[1], "", TS, f"rail {name}")
        return pl

    def rail(self, name, x, y):
        """A supply symbol (arrow up) on (x, y). The rail must be declared: Doc(rails=[...])."""
        if name not in self.doc.rails:
            raise ValueError(f"rail '{name}' is not declared (Doc(rails=[...]))")
        return self._power(name, x, y, (x, y - 3.4), False)

    def gnd(self, x, y):
        """A ground symbol on (x, y)."""
        return self._power("GND", x, y, (x, y + 3.5), True)

    def flag(self, x, y, op=""):
        """KiCad's PWR_FLAG (the small diamond): tells the rule check that this net is fed. Not a part.
        op '' points up, 'r270' right, 'r90' left, 'r180' down."""
        self.flg_n += 1
        ref = f"#FLG{self.page:02d}{self.flg_n:03d}"
        key, node = self.doc.lib.get("PWR_FLAG", op)
        pl = Placed(ref, key, x, y, node, kind="flag")
        self.parts[ref] = pl
        self._an = None
        props = [("Reference", ref, x, y, True, None, TS, False), ("Value", "PWR_FLAG", x, y, True, None, TS, False),
                 ("Footprint", "", x, y, True, None, TS, False), ("Datasheet", "~", x, y, True, None, TS, False),
                 ("Description", "Rule-check power flag", x, y, True, None, TS, False)]
        self._sym_node(key, ref, x, y, props, ["1"], in_bom=False, on_board=False)
        return pl

    def nc(self, pt):
        """A no-connect mark on a pin that is meant to stay open."""
        self.nc_pts.append(_pt(pt))
        self._an = None

    # ---- wires and labels -------------------------------------------------------------------------------------
    def wire(self, *pts):
        """A wire through the given points; each step must be horizontal or vertical."""
        pts = [_pt(p) for p in pts]
        if len(pts) < 2:
            raise ValueError("a wire needs at least two points")
        for a, b in zip(pts, pts[1:]):
            if not all(on_grid(v) for v in (a[0], a[1], b[0], b[1])):
                raise ValueError(f"wire off the 1.27 mm grid: {a} -> {b}")
            if (a[0] == b[0]) == (a[1] == b[1]):
                raise ValueError(f"wire step is not straight, or is empty: {a} -> {b}")
        self.polylines.append(pts)
        self._an = None

    def label(self, name, x, y, justify="left", pair=False):
        """A net name on a wire (local label). It NAMES the net. The same name twice on one sheet joins the two
        places: that is a label pair and must be asked for with pair=True on both (use it only where a wire
        would cross a supply row, and list it in the design note)."""
        ang = 0 if justify == "left" else 180
        self.label_nodes.append(["label", Q(name), ["at", g(x), g(y), str(ang)],
                                 eff(justify=("left" if justify == "left" else "right") + " bottom"),
                                 ["uuid", Q(self.doc.uid(self.key, "lb", name, x, y))]])
        self.labels.append({"kind": "local", "name": name, "pt": _pt((x, y)), "pair": pair, "dir": None})
        self._an = None
        w = tw(name)
        x0 = x if justify == "left" else x - w
        self.text_boxes.append((x0, y - TS - 0.3, x0 + w, y - 0.3, f"label {name}"))

    def tag(self, name, x, y, side="right", stub=1.27, pair=False):
        """A net name beside a VERTICAL wire: a short tick out of the wire at (x, y) carries the name, so the text
        stays upright and clear of the wire."""
        xe = x + stub if side == "right" else x - stub
        self.wire((x, y), (xe, y))
        self.label(name, xe, y, justify="left" if side == "right" else "right", pair=pair)

    def offsheet(self, name, x, y, side, kind, caption=None, inline=False, pair=False):
        """An off-sheet connector (KiCad global label) at (x, y) for a signal declared in Doc(global_nets=...).
        side 'L': the flag lies left of the point (a wire leaves to the right); 'R': it lies to the right.
        kind 'in' / 'out' / 'bidi' sets the arrow: 'out' on the one sheet that drives the signal, 'in' where it
        is used. caption: the other sheets and what the signal does there, written under the flag;
        inline=True: on one line above the wire (for flags that stand close under one another)."""
        try:
            shape = {"in": "input", "out": "output", "bidi": "bidirectional"}[kind]
        except KeyError:
            raise ValueError(f"off-sheet connector {name}: kind '{kind}' (use in, out or bidi)") from None
        ang, just = (180, "right") if side == "L" else (0, "left")
        self.label_nodes.append(
            ["global_label", Q(name), ["shape", shape], ["at", g(x), g(y), str(ang)], eff(justify=just),
             ["uuid", Q(self.doc.uid(self.key, "gl", name, x, y))],
             ["property", Q("Intersheetrefs"), Q("${INTERSHEET_REFS}"), ["at", g(x), g(y), "0"],
              eff(justify=just, hide=True)]])
        self.labels.append({"kind": "global", "name": name, "pt": _pt((x, y)), "pair": pair, "dir": kind})
        self._an = None
        w = tw(name) + 4.0
        x0 = x - w if side == "L" else x
        self.text_boxes.append((x0, y - 1.3, x0 + w, y + 1.3, f"off-sheet {name}"))
        if caption and inline:
            one = caption.replace("\n", " ")
            if side == "L":
                self.text(one, x + 1.5, y - 0.6, justify="left bottom", color=COL_DIM, size=1.1)
            else:
                self.text(one, x - 1.5, y - 0.6, justify="right bottom", color=COL_DIM, size=1.1)
        elif caption:                     # under the flag; at the left edge it starts at the sheet margin
            self.text(caption, 12.7 if side == "L" else x0, y + 2.1, justify="left top", color=COL_DIM, size=1.1)

    # ---- graphics and text ------------------------------------------------------------------------------------
    def _note_text(self, s, x, y, justify, size, what, bold=False):
        just = justify or ""
        lines = s.split("\n")
        w = max(tw(ln, size, bold) for ln in lines)
        h = size + (len(lines) - 1) * size * LINE
        if "left" in just:
            x0 = x
        elif "right" in just:
            x0 = x - w
        else:
            x0 = x - w / 2
        if "top" in just:
            y0 = y
        elif "bottom" in just:
            y0 = y - h
        else:
            y0 = y - h / 2
        self.text_boxes.append((x0, y0, x0 + w, y0 + h, what))

    def text(self, s, x, y, size=TS, bold=False, italic=False, color=COL_TEXT, justify="left top"):
        self.gfx.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", g(x), g(y), "0"],
                         eff(size=size, justify=justify, bold=bold, italic=italic, color=color),
                         ["uuid", Q(self.doc.uid(self.key, "txt", s[:40], x, y))]])
        self._note_text(s, x, y, justify, size, f"text {s[:24]!r}", bold)

    def para(self, s, x, y, width, size=TS, color=COL_TEXT, bold=False, italic=False):
        """A paragraph wrapped to `width` mm. Returns the y below it."""
        n = max(8, int(width / (size * CHAR)))
        lines = []
        for part in s.split("\n"):
            lines += _wrap(part, n)
        self.text("\n".join(lines), x, y, size=size, color=color, bold=bold, italic=italic)
        return y + len(lines) * size * LINE + 0.4

    def table(self, x, y, widths, rows, size=TS, pad=0.9):
        """A plain table: rows of cells (a cell may hold line breaks), the first row is the header.
        Returns the y below it."""
        total = sum(widths)
        yy = y
        self.line((x, yy), (x + total, yy), width=0.2, color=COL_TEXT)
        for r, row in enumerate(rows):
            cells = []
            for c, w in zip(row, widths):
                n = max(4, int((w - 2 * pad) / (size * CHAR)))
                ls = []
                for part in str(c).split("\n"):
                    ls += _wrap(part, n)
                cells.append(ls)
            h = max(len(c) for c in cells) * size * LINE + 2 * pad - 0.5
            xx = x
            for c, w in zip(cells, widths):
                self.text("\n".join(c), xx + pad, yy + pad, size=size, bold=(r == 0), color=COL_TEXT)
                xx += w
            yy += h
            self.line((x, yy), (x + total, yy), width=0.2 if r in (0, len(rows) - 1) else 0.1, color=COL_TEXT)
        return yy

    def line(self, *pts, width=0.15, kind="solid", color=None):
        self.gfx.append(["polyline", ["pts"] + [["xy", g(p[0]), g(p[1])] for p in pts], stroke(width, kind, color),
                         ["fill", ["type", "none"]], ["uuid", Q(self.doc.uid(self.key, "ln", pts))]])

    def rect(self, x0, y0, x1, y1, width=0.15, kind="solid", color=None, fill=None):
        f = ["fill", ["type", "none"]] if not fill else ["fill", ["type", "color"],
                                                         ["color", str(fill[0]), str(fill[1]), str(fill[2]), "1"]]
        self.gfx.append(["rectangle", ["start", g(x0), g(y0)], ["end", g(x1), g(y1)], stroke(width, kind, color), f,
                         ["uuid", Q(self.doc.uid(self.key, "rc", x0, y0, x1, y1))]])

    def arrow(self, *pts, width=0.25, color=COL_TEXT, head=1.6):
        """A flow line of a block diagram (not a wire): straight steps, an arrow head at the last point."""
        self.line(*pts, width=width, color=color)
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        dx, dy = (x1 - x0), (y1 - y0)
        n = max(abs(dx), abs(dy)) or 1.0
        ux, uy = dx / n, dy / n
        bx, by = x1 - ux * head, y1 - uy * head
        px, py = -uy * head * 0.4, ux * head * 0.4
        self.gfx.append(["polyline", ["pts", ["xy", g(x1), g(y1)], ["xy", g(bx + px), g(by + py)],
                                      ["xy", g(bx - px), g(by - py)], ["xy", g(x1), g(y1)]],
                         stroke(width, "solid", color), ["fill", ["type", "outline"]],
                         ["uuid", Q(self.doc.uid(self.key, "ah", pts))]])

    def heading(self, title, line=None):
        """The sheet's own heading, top left: the title in large letters and one line saying what the sheet does."""
        self.text(title, MARGIN, 16.0, size=4.0, bold=True, color=COL_FRAME)
        if line:
            self.text(line, MARGIN, 23.5, size=1.5, color=COL_FRAME)

    def frame(self, x0, y0, x1, y1, title, sub=None, title_dx=0.0):
        """A functional block: a dashed frame with its title in capitals inside the top-left corner
        (title_dx moves the title to the right, past a wire that enters there)."""
        self.rect(x0, y0, x1, y1, width=0.2, kind="dash", color=COL_FRAME)
        self.text(title, x0 + 1.8 + title_dx, y0 + 1.6, size=2.0, bold=True, color=COL_FRAME)
        if sub:
            self.text(sub, x0 + 1.8 + title_dx, y0 + 5.0, size=1.27, color=COL_FRAME)

    def vtag(self, x, y, run, stby=None, anchor="left"):
        """Expected DC voltage at a node: a small box, the running value on top, the standby value in brackets."""
        lines = [run] + ([f"({stby})"] if stby is not None else [])
        w = max(tw(ln, TS, True) for ln in lines) + 1.6
        h = 0.9 + len(lines) * TS + (len(lines) - 1) * 0.75 + 0.5
        x0 = x if anchor == "left" else (x - w if anchor == "right" else x - w / 2)
        self.rect(x0, y, x0 + w, y + h, width=0.15, color=COL_VOLT)
        yy = y + 0.7
        for i, ln in enumerate(lines):
            self.gfx.append(["text", Q(ln), ["exclude_from_sim", "no"], ["at", g(x0 + w / 2), g(yy), "0"],
                             eff(size=TS, justify="top", bold=(i == 0), color=COL_VOLT),
                             ["uuid", Q(self.doc.uid(self.key, "vt", ln, x, y, i))]])
            yy += TS + 0.75
        self.text_boxes.append((x0, y, x0 + w, y + h, f"voltage tag {run}"))
        return (x0, y, x0 + w, y + h)

    def setpoint(self, s, x, y, justify="left top", size=TS):
        """A set-point or remark beside the part that sets it."""
        self.text(s, x, y, size=size, italic=True, color=COL_SET, justify=justify)

    def legend(self, x, y, width, states, sample=("3.3 V", "0 V")):
        """The key of a sheet ("how to read this sheet"). states: what the two values of a voltage tag mean on
        this board, for example "running (in brackets: standby)". Returns the y below the box."""
        h = 26.0
        self.rect(x, y, x + width, y + h, width=0.15, color=COL_DIM)
        self.text("HOW TO READ THIS SHEET", x + 2.0, y + 1.8, bold=True)
        self.vtag(x + 2.0, y + 5.6, sample[0], sample[1])
        self.para("Expected DC voltage to GND: " + states, x + 14.0, y + 5.9, width - 16.0)
        self.text("DNP", x + 2.0, y + 13.0, bold=True)
        self.text("Crossed, grey part: not fitted.", x + 14.0, y + 13.0)
        self.text("TPn", x + 2.0, y + 16.6, bold=True)
        self.text("Test point: a pad for a probe.", x + 14.0, y + 16.6)
        self.para("Small diamond on a wire: the rule check's power flag, not a part. X on a pin: not connected.",
                  x + 2.0, y + 20.6, width - 4.0, size=1.1, color=COL_DIM)
        return y + h

    def notes(self, y0, how=(), volts=(), checks=(), sources="", size=1.5, checks_title="CHECKS"):
        """The three boxes under the drawing: HOW IT WORKS ([(heading, text)]), EXPECTED VOLTAGES (table rows, the
        first is the header) with a small-print line naming the sources, and CHECKS ([(heading, text)]).
        Returns the y below them."""
        pw = self.doc.paper_size[0]
        usable = pw - 2 * MARGIN
        c1, c2, c3 = MARGIN, MARGIN + usable * 0.36, MARGIN + usable * 0.70
        w1, w2, w3 = usable * 0.36 - 6.0, usable * 0.34 - 6.0, usable * 0.30
        end1 = end2 = end3 = y0
        if how:
            self.text("HOW IT WORKS", c1, y0, size=2.0, bold=True, color=COL_FRAME)
            yy = y0 + 5.0
            lead = min(26.0, w1 * 0.25)
            for head, body in how:
                self.text(head, c1, yy, size=size, bold=True)
                yy = self.para(body, c1 + lead, yy, w1 - lead, size=size) + 1.0
            end1 = yy
        if volts:
            self.text("EXPECTED VOLTAGES (DC, to GND)", c2, y0, size=2.0, bold=True, color=COL_FRAME)
            n = len(volts[0])
            share = [0.23, 0.17, 0.42, 0.18] if n == 4 else [1.0 / n] * n
            yt = self.table(c2, y0 + 5.0, [w2 * s for s in share], volts, size=size - 0.1)
            end2 = self.para(sources, c2, yt + 1.5, w2, size=1.1, color=COL_DIM) if sources else yt
        if checks:
            self.text(checks_title, c3, y0, size=2.0, bold=True, color=COL_FRAME)
            yy = y0 + 5.0
            for head, body in checks:
                self.text(head, c3, yy, size=size, bold=True)
                yy = self.para(body, c3, yy + size * 1.85, w3, size=size) + 1.4
            end3 = yy
        return max(end1, end2, end3)

    def sheet_index(self, x, y):
        """Root sheet only: where the sheet index (one small box per sub-sheet, with its name) stands."""
        if self is not self.doc.root:
            raise ValueError("the sheet index belongs on the root sheet")
        self.index_at = (x, y)

    # ---- geometry of the drawing: segments, junctions, nodes -------------------------------------------------
    def _pin_points(self):
        pts = {}
        for pl in self.parts.values():
            for num, q in pl.pins.items():
                pts.setdefault((q[0], q[1]), []).append((pl.ref, num))
        return pts

    def _segments(self):
        """Split the drawn wires at every T (a wire end or a pin on another wire).
        Returns (segments, junctions, wire ends per point, pins per point)."""
        segs = set()
        for pl in self.polylines:
            for a, b in zip(pl, pl[1:]):
                segs.add((min(a, b), max(a, b)))
        pinpts = self._pin_points()
        changed = True
        while changed:
            changed = False
            ends = {p for s in segs for p in s} | set(pinpts)
            for s in list(segs):
                (x0, y0), (x1, y1) = s
                inner = [p for p in ends if p != s[0] and p != s[1] and
                         ((x0 == x1 == p[0] and y0 < p[1] < y1) or (y0 == y1 == p[1] and x0 < p[0] < x1))]
                if inner:
                    chain = [s[0]] + sorted(inner) + [s[1]]
                    segs.discard(s)
                    for a, b in zip(chain, chain[1:]):
                        segs.add((a, b))
                    changed = True
        # junction: three or more wire ends, or two wire ends and a pin
        count = {}
        for a, b in segs:
            count[a] = count.get(a, 0) + 1
            count[b] = count.get(b, 0) + 1
        junctions = sorted(p for p, n in count.items() if n >= 3 or (n >= 2 and p in pinpts))
        return sorted(segs), junctions, count, pinpts

    def analyse(self) -> dict:
        """The sheet's nodes: every group of pins, labels and supply symbols joined by drawn wires."""
        if self._an is not None:
            return self._an
        segs, junctions, count, pinpts = self._segments()
        parent: dict[tuple, tuple] = {}

        def find(p):
            parent.setdefault(p, p)
            while parent[p] != p:
                parent[p] = parent[parent[p]]
                p = parent[p]
            return p

        for a, b in segs:
            parent[find(a)] = find(b)
        for p in pinpts:
            find(p)
        floating = []
        for lb in self.labels:
            p = lb["pt"]
            if p in parent:
                lb["at"] = p
                continue
            hit = next((s for s in segs if (s[0][0] == s[1][0] == p[0] and s[0][1] < p[1] < s[1][1])
                        or (s[0][1] == s[1][1] == p[1] and s[0][0] < p[0] < s[1][0])), None)
            lb["at"] = hit[0] if hit else None
            if hit is None:
                floating.append(lb)
        nodes: dict[tuple, dict] = {}

        def node(p):
            return nodes.setdefault(find(p), {"pins": [], "power": set(), "flags": 0, "local": {}, "global": {},
                                              "nc": False, "wires": 0})

        for a, b in segs:
            node(a)["wires"] += 1
        for p, who in pinpts.items():
            n = node(p)
            for ref, num in who:
                pl = self.parts[ref]
                if pl.kind == "power":
                    n["power"].add(pl.net)
                elif pl.kind == "flag":
                    n["flags"] += 1
                else:
                    n["pins"].append((ref, num))
        for lb in self.labels:
            if lb["at"] is not None:
                node(lb["at"])["local" if lb["kind"] == "local" else "global"].setdefault(lb["name"], []).append(lb)
        loose_nc = []
        for p in self.nc_pts:
            if p in parent:
                node(p)["nc"] = True
            else:
                loose_nc.append(p)
        self._an = {"segs": segs, "junctions": junctions, "count": count, "pinpts": pinpts, "nodes": nodes,
                    "find": find, "floating": floating, "loose_nc": loose_nc}
        return self._an

    def build(self) -> str:
        an = self.analyse()
        items = []
        for a, b in an["segs"]:
            items.append(["wire", ["pts", ["xy", g(a[0]), g(a[1])], ["xy", g(b[0]), g(b[1])]], stroke(0, "default"),
                          ["uuid", Q(self.doc.uid(self.key, "w", a, b))]])
        for p in an["junctions"]:
            items.append(["junction", ["at", g(p[0]), g(p[1])], ["diameter", "0"], ["color", "0", "0", "0", "0"],
                          ["uuid", Q(self.doc.uid(self.key, "j", p))]])
        for p in self.nc_pts:
            items.append(["no_connect", ["at", g(p[0]), g(p[1])], ["uuid", Q(self.doc.uid(self.key, "nc", p))]])
        libs = ["lib_symbols"]
        for k in sorted({pl.key for pl in self.parts.values()}):
            s = copy.deepcopy(self.doc.lib.used[k])
            s[1] = Q(f"{self.doc.lib.name}:{k}")
            libs.append(s)
        doc = (["kicad_sch", ["version", "20250114"], ["generator", Q("eeschema")], ["generator_version", Q("9.0")],
                ["uuid", Q(self.doc.root_uuid if self is self.doc.root else self.doc.uid("file", self.key))],
                ["paper", Q(self.doc.paper)], self.doc.title_block(self.title), libs]
               + items + self.label_nodes + self.gfx + self.sym_nodes)
        if self is self.doc.root:
            for s in sorted(self.doc.sheets, key=lambda t: t.page):
                box, number = self.doc.sheet_symbol(s)
                doc += [number, box]
            doc.append(["sheet_instances", ["path", Q("/"), ["page", Q(str(self.page))]]])
        doc.append(["embedded_fonts", "no"])
        return dump(doc) + "\n"

    # ---- drawing findings (not fatal) ---------------------------------------------------------------------------
    def drawing_findings(self) -> list[str]:
        """Mechanical checks of the drawing. They do not replace looking at the sheet."""
        out = []
        an = self.analyse()
        segs, junctions, count, pinpts = an["segs"], an["junctions"], an["count"], an["pinpts"]
        for p in junctions:
            if count.get(p, 0) + len(pinpts.get(p, [])) >= 4:
                out.append(f"four-way junction at {p}: offset one branch")
        cross = []
        hs = [s for s in segs if s[0][1] == s[1][1]]
        vs = [s for s in segs if s[0][0] == s[1][0]]
        for h in hs:
            for v in vs:
                if h[0][0] < v[0][0] < h[1][0] and v[0][1] < h[0][1] < v[1][1]:
                    cross.append((v[0][0], h[0][1]))
        if cross:
            out.append(f"{len(cross)} wire crossing(s) without a joint: {cross}")
        for i, a in enumerate(segs):
            for b in segs[i + 1:]:
                if a[0][1] == a[1][1] == b[0][1] == b[1][1] and max(a[0][0], b[0][0]) < min(a[1][0], b[1][0]):
                    out.append(f"overlapping wires {a} {b}")
                if a[0][0] == a[1][0] == b[0][0] == b[1][0] and max(a[0][1], b[0][1]) < min(a[1][1], b[1][1]):
                    out.append(f"overlapping wires {a} {b}")

        def seg_hits(s, box, pad=0.0):
            (x0, y0), (x1, y1) = s
            bx0, by0, bx1, by1 = box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad
            if bx0 >= bx1 or by0 >= by1:
                return False
            return not (x1 <= bx0 or x0 >= bx1 or y1 <= by0 or y0 >= by1)

        for pl in self.parts.values():
            for s in segs:
                if seg_hits(s, pl.box, 0.15):
                    out.append(f"wire {s} runs through {pl.ref}")
        tb = self.text_boxes
        for b in tb:
            for s in segs:
                if seg_hits(s, b, 0.1) and not b[4].startswith(("label", "off-sheet")):
                    out.append(f"wire {s} under {b[4]}")
        for i, a in enumerate(tb):
            for b in tb[i + 1:]:
                if a[0] < b[2] - 0.1 and b[0] < a[2] - 0.1 and a[1] < b[3] - 0.1 and b[1] < a[3] - 0.1:
                    out.append(f"texts overlap: {a[4]} / {b[4]}")
        for pl in self.parts.values():
            bx = pl.box
            if bx[2] - bx[0] > 12 and bx[3] - bx[1] > 12:
                continue                                        # an IC body: texts may sit inside it on purpose
            for b in tb:
                if bx[0] < b[2] - 0.1 and b[0] < bx[2] - 0.1 and bx[1] < b[3] - 0.1 and b[1] < bx[3] - 0.1:
                    out.append(f"text on a symbol: {b[4]} / {pl.ref}")
        pw, ph = self.doc.paper_size
        for b in tb:
            if b[0] < 10.0 or b[1] < 10.0 or b[2] > pw - 10.0 or b[3] > ph - 10.0:
                out.append(f"outside the sheet border: {b[4]}")
            elif b[2] > pw - 10.0 - TITLE_BLOCK[0] and b[3] > ph - 10.0 - TITLE_BLOCK[1]:
                out.append(f"over the title block: {b[4]}")
        return out


class Doc:
    """The whole schematic: the root sheet (page 1) and its sub-sheets.

        doc = Doc("myboard", title="...", rev="A", date="YYYY-MM-DD", company="...", parts=PARTS,
                  rails=["+5V", "+3V3"], global_nets=["SDA", "SCL"], paper="A4")
        s1 = doc.root_sheet("POWER INPUT")            # page 1 (in a larger project: the overview)
        s2 = doc.sheet("sensor", 2, "SENSOR AND LED")
        ...                                           # place parts, draw wires
        doc.write(folder)                             # lint, then the KiCad project
    """

    def __init__(self, project, title, rev, date, company, comments=(), paper="A4", parts=None, rails=(),
                 global_nets=(), resistor="R_US", lib_name=None, fp_libs=None, lcsc_field="LCSC", mpn_field="MPN"):
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", project or ""):
            raise ValueError("project: the base name of the KiCad files, letters, digits, _ . + - only")
        if paper not in PAPER:
            raise ValueError(f"paper '{paper}' (one of {', '.join(PAPER)})")
        self.project, self.title, self.rev, self.date, self.company = project, title, rev, date, company
        self.comments = list(comments)
        self.paper, self.paper_size = paper, PAPER[paper]
        self.rails = list(rails)
        self.global_nets = list(global_nets)
        self.fp_libs = dict(fp_libs or {})          # {footprint library name: path, e.g. "${KIPRJMOD}/lib/x.pretty"}
        self.lcsc_field, self.mpn_field = lcsc_field, mpn_field
        self.ns = uuid.uuid5(uuid.NAMESPACE_URL, "kicad-schematic:" + project)
        self.root_uuid = self.uid("root")
        self.lib = symbols.Library(lib_name or project + "_sch", resistor=resistor, rails=self.rails)
        self.sheets: list[Sheet] = []
        self.root: Sheet | None = None
        self.placed: dict[str, str] = {}
        self._parts: dict[str, dict] = {}
        for ref, d in (parts or {}).items():
            self.add_part(ref, **d)

    def uid(self, *parts) -> str:
        return str(uuid.uuid5(self.ns, "/".join(str(p) for p in parts)))

    # ---- the parts table ----------------------------------------------------------------------------------------
    def add_part(self, ref, sym=None, value="", footprint="", lcsc="", mpn="", dnp=False, in_bom=True,
                 on_board=True, datasheet="", desc="", fields=None):
        if ref in self._parts:
            raise ValueError(f"{ref} is in the parts table twice")
        f = {}
        if lcsc:
            f[self.lcsc_field] = str(lcsc)
        if mpn:
            f[self.mpn_field] = str(mpn)
        f.update({str(k): str(v) for k, v in (fields or {}).items()})
        self._parts[ref] = {"sym": sym, "value": str(value), "footprint": str(footprint), "dnp": bool(dnp),
                            "in_bom": bool(in_bom), "on_board": bool(on_board), "datasheet": str(datasheet),
                            "desc": str(desc), "fields": f}

    def part_data(self, ref) -> dict:
        try:
            return self._parts[ref]
        except KeyError:
            raise KeyError(f"{ref} is not in the parts table (Doc(parts=...) or doc.add_part)") from None

    # ---- sheets ---------------------------------------------------------------------------------------------------
    def root_sheet(self, heading) -> Sheet:
        if self.root is not None:
            raise ValueError("the root sheet exists already")
        s = Sheet(self, "root", 1, "/", f"{self.project}.kicad_sch", heading)
        s.uuid = self.root_uuid
        self.root = s
        return s

    def sheet(self, key, page, name, file=None, heading=None) -> Sheet:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key) or key == "root" or any(s.key == key for s in self.sheets):
            raise ValueError(f"sheet key '{key}': letters, digits, _ and - only, unique, not 'root'")
        if page == 1 or any(s.page == page for s in self.sheets):
            raise ValueError(f"page {page} is taken (page 1 is the root sheet)")
        s = Sheet(self, key, page, name, file or f"{key}.kicad_sch", heading or f"Sheet {page}: {name}")
        self.sheets.append(s)
        return s

    def all_sheets(self) -> list[Sheet]:
        return ([self.root] if self.root else []) + sorted(self.sheets, key=lambda s: s.page)

    def title_block(self, heading):
        tb = ["title_block", ["title", Q(self.title)], ["date", Q(self.date)], ["rev", Q(self.rev)],
              ["company", Q(self.company)]]
        for i, c in enumerate([heading] + self.comments, 1):
            tb.append(["comment", str(i), Q(c)])
        return tb

    def sheet_symbol(self, s: Sheet):
        """The sheet index entry of a sub-sheet on the root sheet: (KiCad's sheet box, its page number as text)."""
        x, y = self.root.index_at if self.root and self.root.index_at else (MARGIN + 2.54, 40.64)
        i = sorted(self.sheets, key=lambda t: t.page).index(s)
        sy = y + i * 10.16
        box = ["sheet", ["at", g(x), g(sy)], ["size", g(10.16), g(5.08)], ["exclude_from_sim", "no"],
               ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"],
               stroke(0.1524, "solid"), ["fill", ["color", "0", "0", "0", "0.0000"]], ["uuid", Q(s.uuid)],
               ["property", Q("Sheetname"), Q(s.name), ["at", g(x + 12.7), g(sy + 3.2), "0"],
                eff(justify="left bottom", size=1.5)],
               ["property", Q("Sheetfile"), Q(s.file), ["at", g(x + 12.7), g(sy + 3.6), "0"],
                eff(justify="left top", hide=True)],
               ["instances", ["project", Q(self.project), ["path", Q(f"/{self.root_uuid}"),
                                                           ["page", Q(str(s.page))]]]]]
        number = ["text", Q(str(s.page)), ["exclude_from_sim", "no"], ["at", g(x + 5.08), g(sy + 2.54), "0"],
                  eff(size=2.0, bold=True, color=COL_FRAME), ["uuid", Q(self.uid("index", s.key))]]
        return box, number

    # ---- the nets, worked out from the drawing --------------------------------------------------------------------
    def nets(self) -> list[dict]:
        """Every net of the design as the drawing gives it: [{"name", "names", "pins": [(ref, pin)], "nc", "where":
        [(sheet key, node)]}]. Nodes of one sheet that carry the same local label are one net; nodes anywhere that
        carry the same off-sheet name or supply symbol are one net (KiCad's rules)."""
        parent: dict[tuple, tuple] = {}

        def find(k):
            parent.setdefault(k, k)
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        glob: dict[str, tuple] = {}
        for s in self.all_sheets():
            local: dict[str, tuple] = {}
            for root, n in s.analyse()["nodes"].items():
                k = (s.key, root)
                find(k)
                for name in n["local"]:
                    if name in local:
                        parent[find(k)] = find(local[name])
                    local[name] = k
                for name in list(n["global"]) + sorted(n["power"]):
                    if name in glob:
                        parent[find(k)] = find(glob[name])
                    glob[name] = k
        groups: dict[tuple, dict] = {}
        for s in self.all_sheets():
            for root, n in s.analyse()["nodes"].items():
                gr = groups.setdefault(find((s.key, root)), {"globals": set(), "power": set(), "locals": set(),
                                                             "pins": [], "nc": False, "where": []})
                gr["globals"] |= set(n["global"])
                gr["power"] |= n["power"]
                gr["locals"] |= {("/" if s is self.root else f"/{s.name}/") + nm for nm in n["local"]}
                gr["pins"] += n["pins"]
                gr["nc"] = gr["nc"] or n["nc"]
                gr["where"].append((s.key, root))
        out = []
        for gr in groups.values():
            names = sorted(gr["globals"]) + sorted(gr["power"]) + sorted(gr["locals"])
            out.append({"name": names[0] if names else None, "names": names, "nc": gr["nc"], "where": gr["where"],
                        "pins": sorted(gr["pins"], key=lambda p: (p[0], len(p[1]), p[1]))})
        out.sort(key=lambda n: (n["name"] is None, n["name"] or "", n["pins"]))
        return out

    # ---- lint -------------------------------------------------------------------------------------------------------
    def lint(self) -> list[dict]:
        """The seven checks (see the module text). Returns the findings: [{"check": n, "sheet": key, "text": ...}]."""
        F: list[dict] = []

        def add(check, sheet, text):
            F.append({"check": check, "sheet": sheet, "text": text})

        sheets = self.all_sheets()
        declared_sig, declared_rail = set(self.global_nets), set(self.rails) | {"GND"}
        for name in sorted(declared_sig & declared_rail):
            add(1, "-", f"'{name}' is declared both as a rail and as a signal")
        use: dict[str, dict] = {}                   # name -> {sheet key: {"local" / "global" / "power"}}
        for s in sheets:
            an = s.analyse()
            for lb in s.labels:
                use.setdefault(lb["name"], {}).setdefault(s.key, set()).add(lb["kind"])
            for pl in s.parts.values():
                if pl.kind == "power":
                    use.setdefault(pl.net, {}).setdefault(s.key, set()).add("power")

            # 5 / 6 / 7 on the drawing of this sheet
            for lb in an["floating"]:
                add(5, s.key, f"label '{lb['name']}' at {lb['pt']} touches no wire and no pin")
            for p in an["loose_nc"]:
                add(7, s.key, f"no-connect mark at {p} is on no pin")
            attach = {lb["at"] for lb in s.labels if lb["at"] is not None} | {lb["pt"] for lb in s.labels}
            for p, n in an["count"].items():
                if n == 1 and p not in an["pinpts"] and p not in attach and p not in s.nc_pts:
                    add(6, s.key, f"wire end at {p} touches nothing")

            # 3: one name on two separately drawn nodes of this sheet
            for kind, word in (("local", "label"), ("global", "off-sheet connector")):
                where: dict[str, list] = {}
                for root, n in an["nodes"].items():
                    for name, lbs in n[kind].items():
                        where.setdefault(name, []).append((root, lbs))
                for name, places in sorted(where.items()):
                    lbs = [lb for _, ls in places for lb in ls]
                    if len(places) > 1 and not all(lb["pair"] for lb in lbs):
                        add(3, s.key, f"{word} '{name}' is on {len(places)} separately drawn nodes (at "
                                      f"{', '.join(str(lb['pt']) for lb in lbs)}): they would become ONE net. "
                                      f"Rename one, join them with a wire, or ask for the pair with pair=True")
                    if len(places) == 1 and any(lb["pair"] for lb in lbs) and kind == "local":
                        add(5, s.key, f"label '{name}' is declared as a pair (pair=True) but stands on one node only")

        # 1 / 2 / 5: names across sheets
        for name, per in sorted(use.items()):
            kinds = set().union(*per.values())
            on_sheets = ", ".join(sorted(per))
            if "local" in kinds and (name in declared_sig or name in declared_rail):
                bad = sorted(k for k, v in per.items() if "local" in v)
                add(1, bad[0], f"'{name}' is a declared {'rail' if name in declared_rail else 'cross-sheet signal'} but "
                               f"is drawn as a plain label on sheet {', '.join(bad)}: a plain label does not leave its "
                               f"sheet (use the supply symbol or an off-sheet connector)")
            if "global" in kinds and name not in declared_sig:
                add(1, sorted(k for k, v in per.items() if "global" in v)[0],
                    f"off-sheet connector '{name}' is not declared (Doc(global_nets=[...]))")
            if len(per) > 1 and name not in declared_sig and name not in declared_rail:
                add(1, sorted(per)[0], f"net name '{name}' is used on sheets {on_sheets} but is not declared: two "
                                       f"different nodes must not share a name; one node that crosses sheets is "
                                       f"declared in global_nets and drawn with off-sheet connectors")
            if name in declared_sig and "global" in kinds:
                on = sorted(k for k, v in per.items() if "global" in v)
                if len(on) == 1:
                    add(5, on[0], f"off-sheet connector '{name}' has no partner on another sheet")
                dirs = [(s.key, lb["dir"]) for s in sheets for lb in s.labels if lb["kind"] == "global" and lb["name"] == name]
                outs = sorted({k for k, d in dirs if d == "out"})
                if len(outs) > 1:
                    add(3, outs[0], f"'{name}' is marked as an output (driven) on sheets {', '.join(outs)}: two "
                                    f"drivers under one name")
                if len(on) > 1 and all(d == "in" for _, d in dirs):
                    add(5, on[0], f"'{name}' is an input on every sheet ({', '.join(on)}): the sheet that drives it "
                                  f"must mark it 'out' (or 'bidi')")
        for name in sorted(declared_sig):
            if not any("global" in v for v in use.get(name, {}).values()):
                add(2, "-", f"declared cross-sheet signal '{name}' has no off-sheet connector on any sheet")
        for name in sorted(self.rails):
            if not any("power" in v for v in use.get(name, {}).values()):
                add(2, "-", f"declared rail '{name}' is not used on any sheet")

        # 4 and the parts table
        sheet_of = self.placed
        for ref, d in self._parts.items():
            if d["sym"] is None:
                continue
            if ref not in sheet_of:
                add(0, "-", f"{ref} ({d['value']}) is in the parts table but on no sheet")
            elif d["on_board"] and not d["footprint"]:
                add(4, sheet_of[ref], f"{ref} ({d['value']}) has no footprint: it would vanish at the board import "
                                      f"and from the placement file")

        # 6 / 7 on the finished nets
        for n in self.nets():
            sk = n["where"][0][0]
            if not n["pins"]:
                if any(self._sheet(k).analyse()["nodes"][r]["wires"] for k, r in n["where"]):
                    add(6, sk, f"wires{(' named ' + n['name']) if n['name'] else ''} reach no pin of any part")
            elif len(n["pins"]) == 1 and not n["nc"]:
                ref, num = n["pins"][0]
                pname = self._sheet(sheet_of.get(ref, sk)).parts[ref].pins[num][3]
                add(7, sheet_of.get(ref, sk), f"pin {ref}.{num} ({pname}) is connected to no other pin"
                    + (f" (net {n['name']})" if n["name"] else "") + ": wire it, or mark it with nc()")
            elif len(n["pins"]) > 1 and n["nc"]:
                add(7, sk, f"no-connect mark on a connected net ({', '.join(f'{r}.{p}' for r, p in n['pins'][:6])})")
        return F

    def _sheet(self, key) -> Sheet:
        return next(s for s in self.all_sheets() if s.key == key)

    # ---- write ------------------------------------------------------------------------------------------------------
    def write(self, outdir, strict_drawing=False) -> dict:
        """Lint, then write the KiCad project into `outdir`: <project>.kicad_sch (root), one file per sub-sheet,
        lib/<library>.kicad_sym, sym-lib-table, <project>.kicad_pro, and <project>.model.json (the nets as the
        drawing gives them, and the drawing findings). Raises LintError and writes nothing when the lint finds
        anything. Files whose content did not change are not touched. Returns {"files", "drawing", "nets"}."""
        if self.root is None:
            raise ValueError("no root sheet: call root_sheet() first")
        findings = self.lint()
        drawing = {s.key: s.drawing_findings() for s in self.all_sheets()}
        if strict_drawing:
            findings += [{"check": 0, "sheet": k, "text": "drawing: " + t} for k, fl in drawing.items() for t in fl]
        if findings:
            raise LintError(findings)
        files: dict[str, str] = {}
        for s in self.sheets:
            files[s.file] = s.build()
        files[self.root.file] = self.root.build()               # after the sub-sheets: every symbol is in the library
        files[f"lib/{self.lib.name}.kicad_sym"] = self.lib.text()
        files["sym-lib-table"] = ('(sym_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/lib/%s.kicad_sym")'
                                  '(options "")(descr "Symbols of this schematic (written by the schematic writer)"))\n)\n'
                                  % (self.lib.name, self.lib.name))
        if self.fp_libs:
            rows = "".join('  (lib (name "%s")(type "KiCad")(uri "%s")(options "")(descr ""))\n' % (k, v)
                           for k, v in sorted(self.fp_libs.items()))
            files["fp-lib-table"] = "(fp_lib_table\n  (version 7)\n" + rows + ")\n"
        pro = {
            "meta": {"filename": f"{self.project}.kicad_pro", "version": 3},
            "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
            "sheets": [[self.root_uuid, "Root"]] + [[s.uuid, s.name] for s in sorted(self.sheets, key=lambda t: t.page)],
            "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
            "text_variables": {},
        }
        files[f"{self.project}.kicad_pro"] = json.dumps(pro, indent=2) + "\n"
        nets = self.nets()
        model = {"project": self.project, "sheets": [{"key": s.key, "page": s.page, "name": s.name, "file": s.file}
                                                      for s in self.all_sheets()],
                 "lint": {"checks": [CHECKS[i] for i in range(1, 8)], "findings": 0},
                 "drawing_findings": drawing,
                 "nets": [{"name": n["name"], "names": n["names"], "no_connect": n["nc"],
                           "pins": [f"{r}.{p}" for r, p in n["pins"]]} for n in nets if n["pins"]]}
        files[f"{self.project}.model.json"] = json.dumps(model, indent=1, ensure_ascii=False) + "\n"
        os.makedirs(os.path.join(outdir, "lib"), exist_ok=True)
        written = []
        with kicad_io.ToolLock(os.path.join(outdir, f"{self.project}.kicad_pro")):
            kicad_io.clean_locks(os.path.join(outdir, f"{self.project}.kicad_pro"), whole_folder=True)
            for rel, text in files.items():
                path = os.path.join(outdir, *rel.split("/"))
                try:
                    with open(path, encoding="utf-8", newline="") as f:
                        same = f.read() == text
                except OSError:
                    same = False
                if not same:
                    kicad_io.atomic_write(path, text)
                    written.append(rel)
        return {"files": sorted(files), "written": written, "drawing": drawing, "nets": nets,
                "root": os.path.join(outdir, self.root.file)}
