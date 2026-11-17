"""Symbol library of a wired schematic.

Three kinds of symbols:
  - KiCad's stock symbols for the discrete parts and the supply symbols (flattened copies, so the project needs
    no global library): stock("Device", "C"). They are found through scripts/kicad_io.py (KiCad's symbol folder);
  - the project's ICs and connectors, drawn as service-manual boxes: inputs left, outputs right, supply top,
    ground bottom, every pin with its number and its datasheet name. box() spaces the pins in rows; ic() takes a
    position per pin, so each pin's own network can be drawn beside it without a crossing; conn() draws a
    connector as a pin list;
  - supply rails: rail("+3V3") is KiCad's supply arrow with the rail's own name.

Orientation is "baked": a part drawn horizontally is its own library symbol (R_r90), so every symbol sits in the
sheet at angle 0 and its reference and value are always upright, exactly where the sheet script puts them.

Why a library of its own: a symbol whose pin names differ from the datasheet passed every automatic check once
(a stock symbol had two pin names of a counter exchanged). Drawing each IC from its datasheet pin table, with the
table named in the sheet script, keeps the three layers together: symbol pin name, pin number, footprint pad.

Not a command-line tool. No board.toml keys. The resistor style (one for all sheets) is the Library's
`resistor` argument: "R_US" (zigzag) or "R" (rectangle).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import copy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import kicad_io  # noqa: E402
from sexp import Q, dump, find, first, parse  # noqa: E402

PIN_TYPES = ("input", "output", "bidirectional", "tri_state", "passive", "free", "unspecified", "power_in",
             "power_out", "open_collector", "open_emitter", "no_connect")

# the short names a sheet script may use for stock symbols: name -> (KiCad library, symbol)
STOCK = {
    "C": ("Device", "C"), "C_Polarized": ("Device", "C_Polarized"), "L": ("Device", "L"),
    "D": ("Device", "D"), "D_Schottky": ("Device", "D_Schottky"), "D_Zener": ("Device", "D_Zener"),
    "D_TVS": ("Device", "D_TVS"), "LED": ("Device", "LED"), "FerriteBead": ("Device", "FerriteBead"),
    "Fuse": ("Device", "Fuse"), "Polyfuse": ("Device", "Polyfuse"), "Crystal": ("Device", "Crystal"),
    "TestPoint": ("Connector", "TestPoint"), "MountingHole": ("Mechanical", "MountingHole"),
    "MountingHole_Pad": ("Mechanical", "MountingHole_Pad"), "GND": ("power", "GND"), "PWR_FLAG": ("power", "PWR_FLAG"),
}

_cache: dict[str, dict] = {}


class SymbolError(kicad_io.KicadIOError):
    """A symbol cannot be made (unknown stock symbol, KiCad's libraries not found, a symbol that cannot be turned)."""


# ---- stock symbols (flattened) --------------------------------------------------------------------------------------
def _stock_lib(lib: str) -> dict:
    if lib not in _cache:
        folder = kicad_io.require_kicad().symbols_dir
        if not folder:
            raise SymbolError("KiCad's symbol libraries were not found (set KICAD9_SYMBOL_DIR)")
        path = os.path.join(folder, lib + ".kicad_sym")
        if not os.path.isfile(path):
            raise SymbolError(f"KiCad has no symbol library '{lib}' ({path})")
        with open(path, encoding="utf-8") as f:
            _cache[lib] = {str(s[1]): s for s in find(parse(f.read()), "symbol")}
    return _cache[lib]


def _rename(sym, old: str, new: str):
    sym = copy.deepcopy(sym)
    sym[1] = Q(new)
    for sub in find(sym, "symbol"):
        if sub[1].startswith(old + "_"):
            sub[1] = Q(new + sub[1][len(old):])
    return sym


def stock(lib: str, name: str, newname: str | None = None):
    """A stock symbol of KiCad with 'extends' flattened, renamed to newname."""
    syms = _stock_lib(lib)
    if name not in syms:
        raise SymbolError(f"KiCad's library '{lib}' has no symbol '{name}'")
    s = syms[name]
    ext = first(s, "extends")
    if ext:
        parent = stock(lib, ext[1], ext[1])
        base_ = _rename(parent, ext[1], name)
        base_ = [x for x in base_ if not (isinstance(x, list) and x and x[0] == "property")]
        props = find(s, "property")
        idx = next(i for i, x in enumerate(base_) if isinstance(x, list) and x and x[0] == "symbol")
        s = base_[:idx] + copy.deepcopy(props) + base_[idx:]
    s = copy.deepcopy(s)
    if newname and newname != name:
        s = _rename(s, name, newname)
    return s


def set_prop(sym, key: str, val: str):
    for p in find(sym, "property"):
        if p[1] == key:
            p[2] = Q(val)
            return sym
    idx = next(i for i, x in enumerate(sym) if isinstance(x, list) and x and x[0] == "symbol")
    sym.insert(idx, ["property", Q(key), Q(val), ["at", "0", "0", "0"],
                     ["effects", ["font", ["size", "1.27", "1.27"]], ["hide", "yes"]]])
    return sym


def renumber_pins(sym, mapping: dict[str, str]):
    """Give pins new numbers by their NAME: {"K": "2", "A": "1"} (a part whose package pin-out differs from the
    stock symbol's; name the datasheet page where the sheet script does this)."""
    def walk(n):
        for x in n:
            if isinstance(x, list):
                if x and x[0] == "pin":
                    nm = first(x, "name")[1]
                    if nm in mapping:
                        first(x, "number")[1] = Q(mapping[nm])
                else:
                    walk(x)

    walk(sym)
    return sym


def drop(sym, head: str):
    """Remove a top-level flag such as pin_numbers (so the pin numbers show)."""
    return [x for x in sym if not (isinstance(x, list) and x and x[0] == head)]


# ---- geometry helpers ----------------------------------------------------------------------------------------------
def _f(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pins_of(sym) -> list[dict]:
    """[{num, name, type, x, y, ang, len}] in library coordinates (y up)."""
    res = []

    def walk(n):
        for x in n:
            if isinstance(x, list):
                if x and x[0] == "pin":
                    at = first(x, "at")
                    ln = first(x, "length")
                    res.append({
                        "num": str(first(x, "number")[1]), "name": str(first(x, "name")[1]), "type": str(x[1]),
                        "x": float(at[1]), "y": float(at[2]), "ang": int(float(at[3])) if len(at) > 3 else 0,
                        "len": float(ln[1]) if ln else 0.0,
                    })
                else:
                    walk(x)

    walk(sym)
    return res


def is_power(sym) -> bool:
    """True for a supply symbol (its value names a global net)."""
    return first(sym, "power") is not None


def body_box(sym):
    """Bounding box (x0, y0, x1, y1) of the drawn body in library coordinates (y up), pins excluded."""
    xs, ys = [], []

    def add(x, y):
        xs.append(float(x))
        ys.append(float(y))

    def walk(n):
        for x in n:
            if not isinstance(x, list) or not x:
                continue
            h = x[0]
            if h == "pin" or h == "property":
                continue
            if h in ("polyline", "bezier"):
                for p in find(first(x, "pts"), "xy"):
                    add(p[1], p[2])
            elif h == "rectangle":
                add(*first(x, "start")[1:3])
                add(*first(x, "end")[1:3])
            elif h == "circle":
                c = first(x, "center")
                r = float(first(x, "radius")[1])
                add(float(c[1]) - r, float(c[2]) - r)
                add(float(c[1]) + r, float(c[2]) + r)
            elif h == "arc":
                for k in ("start", "mid", "end"):
                    add(*first(x, k)[1:3])
            else:
                walk(x)

    walk(sym)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def bake(sym, name: str, op: str):
    """A copy of sym, turned: op = '' | 'r90' | 'r180' | 'r270' (counter-clockwise on the sheet), with an optional
    leading 'm' (mirrored left-right first; 'mr180' is therefore a top-bottom flip). Named name + '_' + op."""
    if not op:
        return copy.deepcopy(sym)
    mirror = op.startswith("m")
    try:
        rot = int(op.lstrip("m").lstrip("r") or 0)
    except ValueError:
        rot = -1
    if rot not in (0, 90, 180, 270):
        raise SymbolError(f"{name}: unknown turn '{op}' (use r90, r180, r270, m, mr90, mr180, mr270)")

    def pt(x, y):
        x, y = float(x), float(y)
        if mirror:
            x = -x
        for _ in range(rot // 90):
            x, y = -y, x
        return _f(x), _f(y)

    def ang(a):
        a = int(float(a))
        if mirror:
            a = (180 - a) % 360
        return str((a + rot) % 360)

    out = _rename(sym, str(sym[1]), f"{sym[1]}_{op}")

    def walk(n):
        for x in n:
            if not isinstance(x, list) or not x:
                continue
            h = x[0]
            if h == "property":
                continue
            if h in ("polyline", "bezier"):
                for p in find(first(x, "pts"), "xy"):
                    p[1], p[2] = pt(p[1], p[2])
            elif h == "rectangle":
                for k in ("start", "end"):
                    q = first(x, k)
                    q[1], q[2] = pt(q[1], q[2])
            elif h == "circle":
                q = first(x, "center")
                q[1], q[2] = pt(q[1], q[2])
            elif h == "arc":
                for k in ("start", "mid", "end"):
                    q = first(x, k)
                    q[1], q[2] = pt(q[1], q[2])
                if mirror:  # keep the arc's sense: swap its ends
                    s_, e_ = first(x, "start"), first(x, "end")
                    s_[1], s_[2], e_[1], e_[2] = e_[1], e_[2], s_[1], s_[2]
            elif h == "pin":
                q = first(x, "at")
                q[1], q[2] = pt(q[1], q[2])
                q[3] = ang(q[3])
            elif h == "text":
                raise SymbolError(f"{name}: a symbol with text in its drawing cannot be turned")
            else:
                walk(x)

    walk(out)
    return out


# ---- ICs and connectors as service-manual boxes ------------------------------------------------------------------------
def _eff(size=1.27, hide=False, justify=None, bold=False):
    font = ["font", ["size", _f(size), _f(size)]]
    if bold:
        font.append(["bold", "yes"])
    e = ["effects", font]
    if justify:
        e.append(["justify"] + justify.split())
    if hide:
        e.append(["hide", "yes"])
    return e


def line(*pts, width=0.2):
    """A line for the drawing inside a box (the `gfx` argument of ic() and box())."""
    return ["polyline", ["pts"] + [["xy", _f(x), _f(y)] for x, y in pts],
            ["stroke", ["width", _f(width)], ["type", "default"]], ["fill", ["type", "none"]]]


def ic(name, ref, x0, x1, ytop, ybot, pins, pinlen=5.08, fp="", ds="", desc="", gfx=(), hide_names=False,
       fill="background"):
    """Rectangle symbol. Body from (x0, ytop) to (x1, ybot), library coordinates (y up).
    pins: (number, name, type, side, pos) with side L / R / T / B and pos = y for L and R, x for T and B.
    gfx: extra drawing inside the body (see line())."""
    plist = []
    seen = set()
    for num, pname, etype, side, pos in pins:
        if etype not in PIN_TYPES:
            raise SymbolError(f"{name} pin {num}: unknown pin type '{etype}' (one of {', '.join(PIN_TYPES)})")
        if str(num) in seen:
            raise SymbolError(f"{name}: pin number {num} given twice")
        seen.add(str(num))
        if side == "L":
            at = (x0 - pinlen, pos, 0)
        elif side == "R":
            at = (x1 + pinlen, pos, 180)
        elif side == "T":
            at = (pos, ytop + pinlen, 270)
        elif side == "B":
            at = (pos, ybot - pinlen, 90)
        else:
            raise SymbolError(f"{name} pin {num}: side '{side}' (use L, R, T or B)")
        plist.append(["pin", etype, "line", ["at", _f(at[0]), _f(at[1]), str(at[2])], ["length", _f(pinlen)],
                      ["name", Q(str(pname)), _eff()], ["number", Q(str(num)), _eff()]])
    names = ["pin_names", ["offset", "1.016"]] + ([["hide", "yes"]] if hide_names else [])
    return [
        "symbol", Q(name),
        names,
        ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
        ["property", Q("Reference"), Q(ref), ["at", _f(x0), _f(ytop + 3.2), "0"], _eff(justify="left bottom")],
        ["property", Q("Value"), Q(name), ["at", _f(x0), _f(ytop + 1.2), "0"], _eff(justify="left bottom")],
        ["property", Q("Footprint"), Q(fp), ["at", "0", "0", "0"], _eff(hide=True)],
        ["property", Q("Datasheet"), Q(ds), ["at", "0", "0", "0"], _eff(hide=True)],
        ["property", Q("Description"), Q(desc), ["at", "0", "0", "0"], _eff(hide=True)],
        ["symbol", Q(name + "_0_1"),
         ["rectangle", ["start", _f(x0), _f(ytop)], ["end", _f(x1), _f(ybot)],
          ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", fill]]]] + list(gfx),
        ["symbol", Q(name + "_1_1")] + plist,
    ]


def box(name, ref="U", left=(), right=(), top=(), bottom=(), width=20.32, pitch=5.08, pinlen=5.08, **kw):
    """An IC as a box with its pins in rows. Each side is a list of (number, name, type) or None for an empty
    row, read from top to bottom (left, right) or from left to right (top, bottom).

    The origin is the END of the first left pin (or, with no left pin, of the first right pin): place the part
    with that point on the wire that feeds it. Rows are `pitch` apart (5.08 mm leaves room to draw a part beside
    each pin); the body is `width` wide. Use ic() when single pins need their own positions."""
    rows = max(len(left), len(right), 1)
    x0 = pinlen if left or not right else -(width + pinlen)
    x1 = x0 + width
    ytop, ybot = pitch, -(rows - 1) * pitch - pitch
    pins = []
    for i, p in enumerate(left):
        if p:
            pins.append((p[0], p[1], p[2], "L", -i * pitch))
    for i, p in enumerate(right):
        if p:
            pins.append((p[0], p[1], p[2], "R", -i * pitch))
    for side, plist in (("T", top), ("B", bottom)):
        n = len(plist)
        if n:
            step = 2.54 * max(1, round(width / (n + 1) / 2.54))
            first_x = x0 + round((width - (n - 1) * step) / 2 / 1.27) * 1.27
            for i, p in enumerate(plist):
                if p:
                    pins.append((p[0], p[1], p[2], side, first_x + i * step))
    return ic(name, ref, x0, x1, ytop, ybot, pins, pinlen=pinlen, **kw)


def conn(name, rows, width=22.86, pinlen=5.08, ref="J"):
    """A connector as a pin list: one row per pin, the pin number on the pin; the sheet writes the signal name of
    each row inside the box (Sheet.conn). Pins point left, their ends at x = 0; the first row at y = 0.
    rows: [(pin number, how far below the first row)]. Pin names are Pin_<n>, hidden."""
    ymax = max(off for _, off in rows)
    pins = [(num, f"Pin_{num}", "passive", "L", -off) for num, off in rows]
    return ic(name, ref, pinlen, pinlen + width, 3.81, -ymax - 3.81, pins, pinlen=pinlen, hide_names=True)


def rail(name: str):
    """A supply symbol: the arrow of KiCad's +5V, with the rail's own name. Its value names the (global) net."""
    s = stock("power", "+5V", name)
    set_prop(s, "Value", name)
    set_prop(s, "Description", f"Power symbol creates a global label with name \"{name}\"")
    return s


# ---- the library ---------------------------------------------------------------------------------------------------
class Library:
    """The symbols one schematic uses. Stock symbols are fetched when first asked for; the project's own symbols
    are added with add(). write() saves the library file the schematic sheets refer to."""

    def __init__(self, name: str = "project", resistor: str = "R_US", rails=()):
        self.name = name
        self.resistor = resistor
        self.rails = tuple(rails)
        self.base: dict[str, list] = {}
        self.used: dict[str, list] = {}
        self._source: dict[str, str] = {}       # key in the library file -> the name it was asked for

    def add(self, name: str, sym) -> None:
        """Register a symbol made with box(), ic(), conn() or a changed stock symbol under `name`."""
        if name in self.base:
            raise SymbolError(f"symbol '{name}' is already in the library")
        self.base[name] = sym

    def _base(self, name: str):
        if name not in self.base:
            if name in self.rails:
                self.base[name] = rail(name)
            elif name == "R":
                self.base[name] = stock("Device", self.resistor, "R")
            elif name in STOCK:
                lib, sym = STOCK[name]
                self.base[name] = stock(lib, sym, name)
            elif ":" in name:                       # "Library:Symbol" names any stock symbol of KiCad
                lib, sym = name.split(":", 1)
                self.base[name] = stock(lib, sym, sym)
            else:
                raise SymbolError(f"unknown symbol '{name}': add it to the library (Library.add), name a stock "
                                  f"symbol as 'Library:Symbol', or declare it as a rail")
        return self.base[name]

    def get(self, name: str, op: str = ""):
        """(key in the library file, symbol) of `name` turned by `op`."""
        base = self._base(name)
        own = str(base[1])
        key = f"{own}_{op}" if op else own
        if self._source.setdefault(key, name) != name:
            raise SymbolError(f"symbols '{name}' and '{self._source[key]}' would both be stored as '{key}': "
                              f"register one of them under another name (Library.add)")
        if key not in self.used:
            self.used[key] = bake(base, own, op)
        return key, self.used[key]

    def text(self) -> str:
        head = ["kicad_symbol_lib", ["version", "20241209"], ["generator", Q("schematic_writer")],
                ["generator_version", Q("9.0")]]
        body = [copy.deepcopy(s) for _, s in sorted(self.used.items())]
        return dump(head + body) + "\n"
