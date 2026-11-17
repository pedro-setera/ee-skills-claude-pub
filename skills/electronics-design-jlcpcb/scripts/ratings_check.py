"""Pins and ratings: the exported netlist against the hand-typed datasheet table (src/datasheet_pins.toml).

What it checks (schematic stage; no board and no KiCad needed)
    The netlist that KiCad exports from the schematic, against a table that a person typed from the makers'
    datasheets (format: templates/DATASHEET_PINS.md). Per part and pin:
      pins          a pin number the symbol has and the table lacks, or the reverse (FINDING)
      names         the symbol's pin name against the datasheet's (FINDING). Compared after removing letter case,
                    spaces and underscores, overbar marks (~{X}, ~X) and inversion marks (a leading / ! \\ or
                    lower-case n before a capital, a trailing # or *); a pin may carry `alias = ["..."]`. A symbol
                    pin without a name of its own ("", "~", its number, "Pin_<number>") is not compared: counted.
                    The symbol's names are read from the netlist's list of library parts (KiCad 10 writes the
                    pin number behind every name in the nets: "VIN_1").
      levels        the worst case of the net on the pin against its recommended range (FINDING, without
                    transients) and its absolute maximum and minimum (BLOCKER, transients included). A rating
                    relative to another pin (abs_max_rel = {to = "VIN", plus = 0.3}) is resolved through that
                    pin's net. The same net passes. Two different nets are INDEPENDENT unless [tracks] declares
                    how one follows the other: a maximum is checked with the pin's net at its highest and the
                    other net at its lowest, a minimum the other way round; with [tracks], at the worst point
                    its offset allows. Recommended ratings alike, without transients.
      off state     an absolute relative rating also holds with the other net at 0 V: checked as part of the
                    above when that net's level reaches 0 V (transient_min = 0.0: a domain that can be off while
                    the pin's net is driven); when it does not, and the pin's net would break the rating then:
                    UNKNOWN (the table does not say whether that state occurs).
      leave open    a pin marked connect = "leave open" that is connected; connect = "required" and not connected
      default level (rule MCU-64, MCU-65) for every pin that carries input = "none" | "up" | "down":
                    "none": PASS "tied" when its net is a supply or ground of [levels]; PASS "held by R7 to GND"
                    when a fitted two-pin resistor joins its net to such a net; else, when no other pin of the
                    net can drive it (inputs, capacitors and test points do not; pins of parts marked
                    io_hiz_in_reset do not while that part is in reset): FINDING "can float while U1 is in
                    reset: no pull on <net>"; when the only other pins are connector pins: FINDING "can float:
                    its only source is connector J2 pin 5, and the cable may be unplugged"; when another part's
                    pin is on the net: a NOTE "driven by U5 pin 3; not checked whether it is always active" (not
                    a pass: an open-drain or three-state output is judged by hand).
                    "up" / "down": PASS "held by its own pull"; a resistor pulling the other way: a NOTE with both.
                    The pin key hiz_in_reset = true | false sets one pin apart from its part's io_hiz_in_reset.
      pin table     per part: pin, datasheet name, function (the pin key `function`, free text, never a finding;
                    an empty cell without it) and net: the rows of the pin table of the reference check.
      UNKNOWN       a chip, transistor, diode, LED, polarised capacitor or connector with no block; a pin with no
                    rating and no `no_rating` note; a net with no level where a rated pin sits.

Why it exists (the real failure, told without names)
    An experienced engineer reviewed a dense board that was fully routed, rule-clean and looked professional,
    and found no direct evidence that any pin was the pin of the datasheet or stayed inside its ratings. The
    rule check compares the schematic with itself; a symbol drawn with two pins swapped passes it, a 5 V signal
    on a 3.6 V pin passes it, and an enable input that floats while the microcontroller is in reset passes it
    because "the net has a driver". This check compares with an INDEPENDENT statement and can fail.

Usage
    python -I ratings_check.py --project <hardware/board folder>       netlist out/netlist.net, table
                                                                       src/datasheet_pins.toml; results in out/
    python -I ratings_check.py NETLIST.net TABLE.toml --out FOLDER     any exported netlist (kicadsexpr)
    option: --mpn-field NAME (repeatable): the symbol field that holds the maker part number
    Results: ratings_check.md and ratings_check.json.

The table (TOML; every key: templates/DATASHEET_PINS.md)
    [levels]  "<name>" = {min, max, transient_max, transient_min, source}     worst case of each supply and level
    [nets]    "<net>" = "<level name>"  or  {min, max, transient_max, transient_min, source}
              A net is named by its full name, or by its name without the sheet path, or (a net without a name)
              by one of its pins: "U1.3". A net whose own name is a key of [levels] needs no line here.
    [parts."<maker part number>"]  refs = ["U2"], io_hiz_in_reset = true, datasheet = "..."
    [parts."<maker part number>".pins]  "<number>" = {name, alias, function = "<what the pin does>", abs_max, abs_min,
              rec_max, rec_min, abs_max_rel | abs_min_rel | rec_max_rel | rec_min_rel = {to = "<pin name or number>",
              plus = V}, no_rating = "p. 4: not specified", connect = "leave open" | "required",
              input = "none"|"up"|"down", hiz_in_reset = true|false}
    [tracks]  "<net>" = {net = "<the net it follows>", offset = [<lowest V>, <highest V>], source = "..."}
              <net> = <the net it follows> + a value from the lowest to the highest offset, in every state
              (switching on and off included); a list of such tables when a net follows several. The key is
              named like a key of [nets], or is a level of [levels] that is no net: then it holds for every net
              that [nets] gives that level. Not applied, and a FINDING: no source, an offset that is not two
              finite numbers in order, or levels of the two nets that contradict it.
    A part is matched by `refs`, and by its maker part number field when that equals the block's name or one
    of its words is the block's name ("TI LM358DR"). A pin that is marked "leave open", or that sits on a
    net whose level is exactly 0 V (the reference the ratings are measured from), needs no rating.
    Every number must be finite: TOML reads nan and inf as numbers, and a comparison with nan is always false,
    so such a value is a FINDING (naming the block, pin or level, and the key), never a pass; a minimum above
    its maximum likewise.

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [ratings]
    netlist     = "out/netlist.net"            # relative to the board folder
    table       = "src/datasheet_pins.toml"
    mpn_field   = "MPN"                        # name or list of names (default: [bom] mpn_field, then the names
                                               # jlc_parts.py knows)
    need_block  = ["U", "IC", "Q", "D", "LED", "ZD", "J", "P", "CN", "CON", "X", "USB"]
                                               # reference prefixes of parts that need a block (polarised
                                               # capacitors are found by their symbol, whatever the prefix list)
    skip        = ["J9", "H*"]                 # references that need no block (listed in the report)
    resistors   = ["R"]                        # reference prefixes of resistors that can be a pull
    not_drivers = ["C", "TP", "J", "P", "CN", "CON", "X", "USB"]
                                               # reference prefixes of parts that never drive a net: capacitors,
                                               # test points and connectors (the cable may be unplugged)

Exit codes
    0  PASS: no blocker, no finding, no UNKNOWN (notes do not fail)
    1  FAIL: anything of those; every one is listed with its part, pin and net
    2  CANNOT RUN: no netlist, no table, a table that is not valid TOML, no --out. Never a pass.

Not checked: whether the table is typed correctly (a typing error passes: the schematic reviewer compares it with
the datasheets), its relations ([tracks]) and off states included; currents, power, timing, thresholds; a current
that a datasheet allows into a pin beyond a relative rating; the value of a pull resistor and the level of a
divider; pulls through a resistor network or through a second part; whether a driver is always active; any pin
without the key `input`. No rating database, no reading of PDF files, no level guessed from a net name.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import datetime
import fnmatch
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import jlc_parts  # noqa: E402
import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
import sexp  # noqa: E402
from kicad_io import KicadIOError  # noqa: E402

PREFIX_KIND = {"U": "chip", "IC": "chip", "Q": "transistor", "D": "diode", "ZD": "diode", "LED": "LED",
               "J": "connector", "P": "connector", "CN": "connector", "CON": "connector", "X": "connector",
               "USB": "connector"}
POLARISED = re.compile(r"(?<!un)(?<!non)(?<!non[- ])polari[sz]ed|electrolytic|tantal|^CP\d*(_|$)", re.I)
MPN_FIELDS = list(jlc_parts.MPN_FIELDS)     # the field names of the maker part number: one list, the BOM script's
LIMITS = ("abs_max", "abs_min", "rec_max", "rec_min")
PIN_KEYS = {"name", "alias", "function", "no_rating", "connect", "input", "hiz_in_reset"} | set(LIMITS) | {k + "_rel" for k in LIMITS} | \
    {"functions", "input_only", "open_drain_only", "analog", "sampled_at_reset", "debug", "oscillator"}   # read by pin_function_check.py
CONNECTORS = [p for p, kind in PREFIX_KIND.items() if kind == "connector"]
NOT_DRIVERS = ["C", "TP"] + CONNECTORS      # a capacitor and a test point hold no level; a cable may be unplugged
LEVEL_KEYS = {"min", "max", "transient_max", "transient_min", "source"}
TRACK_KEYS = {"net", "offset", "source"}
PART_KEYS = {"refs", "io_hiz_in_reset", "datasheet", "pins", "programmable", "on_several_pins", "function_modes", "resources", "pin_sets"}   # the last five: pin_function_check.py
OPEN, REQUIRED = "leave open", "required"
EPS = 1e-9
MAX_LISTED = 60


def _nat(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _not_finite(v) -> str:
    """"" for a finite number, else why not. TOML reads nan and inf as numbers, and every comparison with nan is
    false: such a value would pass every check it takes part in."""
    if not _is_num(v):
        return "is not a number"
    return "" if math.isfinite(v) else f"is {v}: not a finite number"


def _v(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") + " V"


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def prefix(ref: str) -> str:
    m = re.match(r"[A-Za-z_]+", ref)
    return m.group(0).upper() if m else ""


def norm_name(s: str) -> str:
    """A pin name without letter case, spaces, underscores, overbar and inversion marks."""
    s = re.sub(r"~\{([^}]*)\}", r"\1", str(s).strip()).replace("~", "")
    s = re.sub(r"[#*]+$", "", re.sub(r"^[/!\\]+", "", s))
    if re.match(r"n[A-Z]", s):
        s = s[1:]
    return re.sub(r"[\s_]+", "", s).upper()


def is_generic(name: str, num: str) -> bool:
    """A symbol pin without a name of its own: nothing to compare with the datasheet."""
    n = norm_name(num)
    return norm_name(name) in ("", n, "PIN" + n)


def symbol_pin_names(path: str, nl) -> dict:
    """{(reference, pin number): the pin's name on the symbol}, read from the netlist's own list of library parts.
    The nets of a netlist carry the name too, but KiCad 10 writes the pin number behind it there ("VIN_1"); a
    name is taken from the nets only for a part whose library part the netlist does not list, and then without
    such an ending."""
    try:
        with open(path, encoding="utf-8") as f:
            tree = sexp.parse(f.read())
    except (OSError, sexp.SexpError, UnicodeDecodeError) as e:
        raise KicadIOError(f"{path}: not a readable netlist ({e})") from None
    lib = {}
    for lp in sexp.find(sexp.first(tree, "libparts") or [], "libpart"):
        lib[(str(sexp.value(lp, "lib", "")), str(sexp.value(lp, "part", "")))] = {
            str(sexp.value(p, "num", "")): str(sexp.value(p, "name", "")) for p in sexp.find(sexp.first(lp, "pins") or [], "pin")}
    names = {}
    for (ref, num), (_, shown, _) in nl.pins.items():
        part = nl.parts.get(ref)
        known = lib.get((part.lib, part.part), {}) if part else {}
        names[(ref, num)] = known[num] if num in known else (shown[:-len(num) - 1] if shown.endswith("_" + num) and shown != "_" + num else shown)
    return names


# ---- the table -------------------------------------------------------------------------------------------------------
class Table:
    """datasheet_pins.toml as plain data. errors: mistakes inside the file; they fail the check (a typing error in
    a key must not read as "no rating")."""

    def __init__(self, path: str):
        try:
            import tomllib
        except ImportError:
            raise KicadIOError("reading the datasheet table needs Python 3.11 or newer (tomllib)") from None
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except OSError as e:
            raise KicadIOError(f"the datasheet table cannot be read: {e}") from None
        except tomllib.TOMLDecodeError as e:
            raise KicadIOError(f"{os.path.basename(path)}: not valid TOML: {e}") from None
        self.path, self.errors = path, []
        self.levels: dict[str, dict] = {}
        self.nets: dict[str, object] = {}
        self.parts: dict[str, dict] = {}
        self.tracks: dict[str, list] = {}
        for k in data:
            if k not in ("levels", "nets", "parts", "tracks"):
                self.errors.append(f"unknown table [{k}] (known: levels, nets, parts, tracks)")
        for name, v in (data.get("levels") or {}).items():
            lvl = self._level(v, f"[levels] \"{name}\"")
            if lvl:
                lvl["name"] = name
                self.levels[name] = lvl
        for name, v in (data.get("nets") or {}).items():
            if isinstance(v, str):
                if v not in self.levels:
                    self.errors.append(f"[nets] \"{name}\" names the level \"{v}\", which [levels] does not have")
                else:
                    self.nets[name] = v
            else:
                lvl = self._level(v, f"[nets] \"{name}\"")
                if lvl:
                    lvl["name"] = "its own range"
                    self.nets[name] = lvl
        for mpn, blk in (data.get("parts") or {}).items():
            self._part(mpn, blk)
        tracks = data.get("tracks") or {}
        if not isinstance(tracks, dict):
            self.errors.append("[tracks] must be a table: \"<net>\" = {net = \"<the net it follows>\", offset = [<V>, <V>], source = \"...\"}")
            tracks = {}
        for name, v in tracks.items():
            many = isinstance(v, list)
            rels = [self._track(r, f"[tracks] \"{name}\"" + (f" (relation {i + 1})" if many else "")) for i, r in enumerate(v if many else [v])]
            if any(rels):
                self.tracks[name] = [r for r in rels if r]
        for where in list(self.levels) + list(self.nets) + list(self.parts) + list(tracks):
            if re.fullmatch(r"<.*>", where.strip()):
                self.errors.append(f"\"{where}\" is still a placeholder of the template")

    def _level(self, v, where: str):
        if not isinstance(v, dict) or not _is_num(v.get("min")) or not _is_num(v.get("max")):
            self.errors.append(f"{where}: needs {{min = <V>, max = <V>}} (numbers)")
            return None
        bad = sorted(set(v) - LEVEL_KEYS)
        if bad:
            self.errors.append(f"{where}: unknown key(s) {', '.join(bad)} (known: {', '.join(sorted(LEVEL_KEYS))})")
        for k in ("min", "max", "transient_max", "transient_min"):
            if k in v and _not_finite(v[k]):
                self.errors.append(f"{where}: {k} {_not_finite(v[k])}")
                return None
        if v["min"] > v["max"]:
            self.errors.append(f"{where}: min is above max")
        if v.get("transient_min", -math.inf) > v.get("transient_max", math.inf):
            self.errors.append(f"{where}: transient_min is above transient_max")
        lo, hi = float(v["min"]), float(v["max"])
        return {"min": lo, "max": hi, "tmin": min(lo, float(v.get("transient_min", lo))),
                "tmax": max(hi, float(v.get("transient_max", hi))), "source": str(v.get("source", ""))}

    def _track(self, r, where: str):
        """One relation of [tracks]: {net, offset = [lo, hi], source}. None, and an error, when it cannot be applied."""
        if not isinstance(r, dict) or not isinstance(r.get("net"), str) or not r["net"].strip():
            self.errors.append(f"{where}: needs {{net = \"<the net it follows>\", offset = [<V>, <V>], source = \"<why>\"}}: not applied")
            return None
        bad = sorted(set(r) - TRACK_KEYS)
        if bad:
            self.errors.append(f"{where}: unknown key(s) {', '.join(bad)} (known: {', '.join(sorted(TRACK_KEYS))})")
        off = r.get("offset")
        if not isinstance(off, list) or len(off) != 2:
            self.errors.append(f"{where}: offset must be [<lowest V>, <highest V>]: not applied")
            return None
        why = next((f"offset {_not_finite(x)}" for x in off if _not_finite(x)), "")
        if not why and off[0] > off[1]:
            why = f"offset [{off[0]}, {off[1]}]: the first number is above the second"
        if not why and not (isinstance(r.get("source"), str) and r["source"].strip()):
            why = "no source (where the relation comes from)"
        if why:
            self.errors.append(f"{where}: {why}: not applied")
            return None
        return {"net": r["net"].strip(), "lo": float(off[0]), "hi": float(off[1]), "source": r["source"].strip()}

    def _part(self, mpn: str, blk) -> None:
        where = f"[parts.\"{mpn}\"]"
        if not isinstance(blk, dict) or not isinstance(blk.get("pins"), dict) or not blk["pins"]:
            self.errors.append(f"{where}: needs a table of pins ({where[:-1]}.pins])")
            return
        bad = sorted(set(blk) - PART_KEYS)
        if bad:
            self.errors.append(f"{where}: unknown key(s) {', '.join(bad)} (known: {', '.join(sorted(PART_KEYS))})")
        refs = blk.get("refs", [])
        if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
            self.errors.append(f"{where}: refs must be a list of designators")
            refs = []
        if not isinstance(blk.get("io_hiz_in_reset", False), bool):
            self.errors.append(f"{where}: io_hiz_in_reset must be true or false")
        pins = {}
        for num, p in blk["pins"].items():
            pw = f"{where} pin {num}"
            if not isinstance(p, dict) or not isinstance(p.get("name"), str) or not p["name"].strip():
                self.errors.append(f"{pw}: needs name = \"<the datasheet's pin name>\"")
                continue
            bad = sorted(set(p) - PIN_KEYS)
            if bad:
                self.errors.append(f"{pw}: unknown key(s) {', '.join(bad)}")
            q = {"name": p["name"], "alias": [], "limits": {}, "rel": {}, "no_rating": None, "connect": None, "input": None,
                 "function": " ".join(str(p.get("function", "")).replace("|", "/").split()),   # free text: never a finding
                 "hiz": None}
            if "hiz_in_reset" in p:
                if isinstance(p["hiz_in_reset"], bool):
                    q["hiz"] = p["hiz_in_reset"]
                else:
                    self.errors.append(f"{pw}: hiz_in_reset must be true or false")
            if "alias" in p:
                if isinstance(p["alias"], list) and all(isinstance(a, str) for a in p["alias"]):
                    q["alias"] = list(p["alias"])
                else:
                    self.errors.append(f"{pw}: alias must be a list of names")
            for k in LIMITS:
                if k in p:
                    if not _is_num(p[k]):
                        self.errors.append(f"{pw}: {k} must be a number (a rating relative to another pin: {k}_rel)")
                    elif _not_finite(p[k]):
                        self.errors.append(f"{pw}: {k} {_not_finite(p[k])}")
                    else:
                        q["limits"][k] = float(p[k])
                r = p.get(k + "_rel")
                if r is not None:
                    if not (isinstance(r, dict) and isinstance(r.get("to"), str) and _is_num(r.get("plus")) and set(r) <= {"to", "plus"}):
                        self.errors.append(f"{pw}: {k}_rel needs {{to = \"<pin name or number>\", plus = <V>}}")
                    elif _not_finite(r["plus"]):
                        self.errors.append(f"{pw}: {k}_rel plus {_not_finite(r['plus'])}")
                    else:
                        q["rel"][k] = (r["to"], float(r["plus"]))
            for lo, hi in (("abs_min", "abs_max"), ("rec_min", "rec_max")):
                if lo in q["limits"] and hi in q["limits"] and q["limits"][lo] > q["limits"][hi]:
                    self.errors.append(f"{pw}: {lo} {_v(q['limits'][lo])} is above {hi} {_v(q['limits'][hi])}")
            if "no_rating" in p:
                if isinstance(p["no_rating"], str) and p["no_rating"].strip():
                    q["no_rating"] = p["no_rating"]
                else:
                    self.errors.append(f"{pw}: no_rating must say where the datasheet gives none (\"p. 4: not specified\")")
            if "connect" in p:
                c = str(p["connect"]).strip().lower()
                c = REQUIRED if c in ("required", "must connect", "connect") else c
                if c in (OPEN, REQUIRED):
                    q["connect"] = c
                else:
                    self.errors.append(f"{pw}: connect must be \"{OPEN}\" or \"{REQUIRED}\", not \"{p['connect']}\"")
            if "input" in p:
                if p["input"] in ("none", "up", "down"):
                    q["input"] = p["input"]
                else:
                    self.errors.append(f"{pw}: input must be \"none\", \"up\" or \"down\", not \"{p['input']}\"")
            if re.fullmatch(r"<.*>", p["name"].strip()):
                self.errors.append(f"{pw}: the name \"{p['name']}\" is still a placeholder of the template")
            pins[str(num)] = q
        part = {"refs": refs, "hiz": blk.get("io_hiz_in_reset") is True,
                "datasheet": str(blk.get("datasheet", "")), "pins": pins}
        for num, q in pins.items():                                     # a relative rating must name a pin of the block
            for k, (to, _) in q["rel"].items():
                if not rel_pins(part, to):
                    self.errors.append(f"{where} pin {num}: {k}_rel names the pin \"{to}\", which the block does not have")
        self.parts[mpn] = part


def rel_pins(part: dict, to: str) -> list:
    """The pin numbers of a block that a relative rating refers to: by name or alias, else by number."""
    t = norm_name(to)
    hits = [n for n, p in part["pins"].items() if t in {norm_name(p["name"])} | {norm_name(a) for a in p["alias"]}]
    return hits or ([to] if to in part["pins"] else [])


# ---- netlist and table together --------------------------------------------------------------------------------------
class Design:
    def __init__(self, nl, tab: Table, cfg: dict):
        self.nl, self.tab, self.cfg = nl, tab, cfg
        self.blockers, self.findings, self.unknown, self.notes = [], [], [], []
        self.no_level: dict[str, list] = {}         # net without a level -> the pins waiting for it
        self.level: dict[str, dict] = {}            # net -> level
        self.level_from: dict[str, str] = {}        # net -> where the level comes from
        self.supply: set = set()                    # nets that are a supply or ground of [levels]
        self.mapped: dict[str, str] = {}            # net -> the level name [nets] gives it
        self._levels()
        self.rel: dict[tuple, tuple] = {}           # (net, other net) -> (lowest, highest offset, text): net = other + offset
        self.rel_used: list[dict] = []              # the relations of [tracks] as applied, for the report
        self._tracks()
        self.block: dict[str, str] = {}             # reference -> block name
        self._match()

    def nets_of_key(self, key: str, pins: bool = True) -> list:
        nl = self.nl
        if key in nl.nets:
            return [key]
        hits = [n for n in nl.nets if kicad_io.leaf(n) == key]
        if hits or not pins:
            return hits
        m = re.fullmatch(r"([^.\s]+)\.([^.\s]+)", key)
        return [nl.pins[(m.group(1), m.group(2))][0]] if m and (m.group(1), m.group(2)) in nl.pins else []

    def _levels(self) -> None:
        tab = self.tab
        for key, v in tab.nets.items():
            nets = self.nets_of_key(key)
            if not nets:
                self.notes.append(f"table: [nets] \"{key}\" fits no net of the netlist (renamed or removed?)")
            elif len(nets) > 1:
                tab.errors.append(f"[nets] \"{key}\" fits {len(nets)} nets ({', '.join(sorted(nets))}): write the full names")
            elif nets[0] in self.level:
                tab.errors.append(f"[nets] gives the net {nets[0]} two levels (\"{key}\" and {self.level_from[nets[0]]})")
            else:
                self.level[nets[0]] = tab.levels[v] if isinstance(v, str) else v
                self.level_from[nets[0]] = f"[nets] \"{key}\"" + (f" = \"{v}\"" if isinstance(v, str) else "")
                if isinstance(v, str):
                    self.mapped[nets[0]] = v
        for key, lvl in tab.levels.items():
            nets = self.nets_of_key(key, pins=False)
            if len(nets) > 1:
                tab.errors.append(f"[levels] \"{key}\" fits {len(nets)} nets ({', '.join(sorted(nets))}): give each its line in [nets]")
                continue
            for n in nets:
                self.supply.add(n)
                if n not in self.level:
                    self.level[n], self.level_from[n] = lvl, f"[levels] \"{key}\""

    def _tracks(self) -> None:
        """[tracks]: net = other net + an offset from lo to hi. Checked against the two levels before it is used."""
        tab = self.tab
        for key, rels in tab.tracks.items():
            nets = self.nets_of_key(key)
            if len(nets) > 1:
                tab.errors.append(f"[tracks] \"{key}\" fits {len(nets)} nets ({', '.join(sorted(nets))}): write the full name")
                continue
            if not nets and key in tab.levels:                              # a level: every net that [nets] gives it
                nets = sorted(n for n, name in self.mapped.items() if name == key)
            if not nets:
                self.notes.append(f"table: [tracks] \"{key}\" fits no net of the netlist (renamed or removed?)")
                continue
            for r in rels:
                others = self.nets_of_key(r["net"])
                if len(others) != 1:
                    tab.errors.append(f"[tracks] \"{key}\": net = \"{r['net']}\" fits {len(others) or 'no'} net(s) of the netlist: not applied")
                    continue
                for s in nets:
                    self._relate(key, s, others[0], r)

    def _relate(self, key: str, s: str, n: str, r: dict) -> None:
        lo, hi = r["lo"], r["hi"]
        ls, ln = self.level.get(s), self.level.get(n)
        if s == n:
            self.tab.errors.append(f"[tracks] \"{key}\": {s} cannot follow itself: not applied")
            return
        for a, b in (("min", "max"), ("tmin", "tmax")):                 # the two levels must allow the relation
            if ls and ln and (ls[b] > ln[b] + hi + EPS or ls[a] < ln[a] + lo - EPS):
                x = ls[b] if ls[b] > ln[b] + hi + EPS else ls[a]
                self.tab.errors.append(f"[tracks] \"{key}\": the levels contradict it: {s} reaches {_v(x)}, but {n} with the offset "
                                       f"{lo:+g} .. {hi:+g} V allows {_v(ln[a] + lo)[:-2]} .. {_v(ln[b] + hi)}"
                                       f"{' (transients included)' if a == 'tmin' else ''}: not applied")
                return
        if (s, n) in self.rel:                                          # declared twice: both hold
            lo, hi = max(lo, self.rel[(s, n)][0]), min(hi, self.rel[(s, n)][1])
            if lo > hi + EPS:
                self.tab.errors.append(f"[tracks] \"{key}\": {s} and {n} are related twice, and the two offsets do not overlap: not applied")
                return
        text = f"{s} = {n} {lo:+g} .. {hi:+g} V by [tracks]"
        self.rel[(s, n)], self.rel[(n, s)] = (lo, hi, text), (-hi, -lo, text)
        self.rel_used.append({"net": s, "follows": n, "offset": [r["lo"], r["hi"]], "from": key, "source": r["source"]})

    def mpn(self, ref: str) -> str:
        fields = {_key(k): v for k, v in self.nl.parts[ref].fields.items()}
        return next((fields[k].strip() for k in (_key(n) for n in self.cfg["mpn_fields"]) if fields.get(k, "").strip()), "")

    def _match(self) -> None:
        nl, tab = self.nl, self.tab
        for name, blk in tab.parts.items():
            refs = []
            for r in blk["refs"]:
                if r in nl.parts:
                    refs.append(r)
                    have = self.mpn(r)
                    if have and _key(name) not in _key(have) and _key(have) not in _key(name):
                        self.findings.append(f"{r}: the table's block is for \"{name}\", the netlist's part number field says "
                                             f"\"{have}\": a table for another part proves nothing")
                else:
                    self.findings.append(f"table: the block \"{name}\" names {r}, which the netlist does not have")
            for r in nl.parts:
                have = self.mpn(r).upper()
                if r not in refs and have and (have == name.strip().upper() or name.strip().upper() in have.split()):
                    refs.append(r)
            if not refs:
                self.notes.append(f"table: no part of the netlist carries the block \"{name}\"")
            for r in refs:
                if r in self.block and self.block[r] != name:
                    tab.errors.append(f"{r} fits two blocks: \"{self.block[r]}\" and \"{name}\"")
                else:
                    self.block[r] = name

    def kind(self, ref: str) -> str:
        """Why a part needs a block ("chip", "connector", ...), or "" when it needs none."""
        p = self.nl.parts[ref]
        if any(fnmatch.fnmatchcase(ref, pat) for pat in self.cfg["skip"]) or not self.nl.pins_of(ref):
            return ""                                                   # left out by board.toml, or a part without a pin
        if POLARISED.search(p.part) or POLARISED.search(p.description):
            return "polarised capacitor"
        pre = prefix(ref)
        return (PREFIX_KIND.get(pre, "part") if pre in self.cfg["need_block"] else "")

    def others(self, ref: str, num: str) -> list:
        net = self.nl.pins[(ref, num)][0]
        return sorted((x for x in self.nl.nets[net] if x != (ref, num)), key=lambda x: (_nat(x[0]), _nat(x[1])))

    def lvl_text(self, net: str) -> str:
        lv = self.level.get(net)
        if lv is None:
            return "no level"
        extra = ([f"down to {_v(lv['tmin'])}"] if lv["tmin"] < lv["min"] else []) + ([f"up to {_v(lv['tmax'])}"] if lv["tmax"] > lv["max"] else [])
        return f"{_v(lv['min'])[:-2]} .. {_v(lv['max'])}" + (f" (transient {', '.join(extra)})" if extra else "")


def pin_text(ref: str, num: str, name: str = "") -> str:
    return f"{ref} pin {num}" + (f" ({name})" if name else "")


def _breaks(x: float, limit: float, upper: bool) -> bool:
    return (x > limit + EPS) if upper else (x < limit - EPS)


def worst_point(d: Design, net: str, onet: str, upper: bool, absolute: bool) -> tuple:
    """Where a rating of net relative to onet comes closest to breaking: (level of net, level of onet, relation or
    None). Without a relation the two nets are independent: a maximum is worst with net at its highest and onet at
    its lowest, a minimum the other way round. A relation of [tracks] (net = onet + lo .. hi) narrows that."""
    lv, olv = d.level[net], d.level[onet]
    s_lo, s_hi = (lv["tmin"], lv["tmax"]) if absolute else (lv["min"], lv["max"])
    n_lo, n_hi = (olv["tmin"], olv["tmax"]) if absolute else (olv["min"], olv["max"])
    rel = d.rel.get((net, onet))
    if upper:
        if rel and rel[1] < s_hi - n_lo:
            n = min(n_hi, s_hi - rel[1])
            return n + rel[1], n, rel
        return s_hi, n_lo, rel
    if rel and rel[0] > s_lo - n_hi:
        n = max(n_lo, s_lo - rel[0])
        return n + rel[0], n, rel
    return s_lo, n_hi, rel


def off_value(d: Design, net: str, onet: str, upper: bool):
    """The worst level of net while onet is off (0 V), for an absolute rating whose other net the table never gives
    0 V; None when it does (then the worst point above already holds that state)."""
    lv, olv = d.level[net], d.level[onet]
    if (olv["tmin"] <= EPS) if upper else (olv["tmax"] >= -EPS):
        return None
    rel = d.rel.get((net, onet))
    if upper:
        return min(lv["tmax"], rel[1]) if rel else lv["tmax"]
    return max(lv["tmin"], rel[0]) if rel else lv["tmin"]


def check_limits(d: Design, ref: str, num: str, pin: dict, blk: dict) -> tuple[str, list]:
    """The level of the pin's net against the pin's limits. Returns (cell text, [limit texts])."""
    nl = d.nl
    net = nl.pins[(ref, num)][0]
    who = pin_text(ref, num, pin["name"])
    connected = bool(d.others(ref, num))
    has_rating = bool(pin["limits"] or pin["rel"])
    lv = d.level.get(net)
    shown = []
    for k, x in pin["limits"].items():
        shown.append(f"{k} {_v(x)}")
    for k, (to, plus) in pin["rel"].items():
        shown.append(f"{k} {to} {'+' if plus >= 0 else '-'} {_v(abs(plus))}")
    if pin["connect"] == OPEN:
        return "leave open", shown
    if not has_rating:
        if pin["no_rating"]:
            return f"no rating in the datasheet ({pin['no_rating']})", shown
        if lv is not None and lv["tmin"] == 0.0 and lv["tmax"] == 0.0:
            return "on the 0 V reference: needs no rating", shown
        d.unknown.append(f"{who}: no rating in the table and no `no_rating` note")
        return "UNKNOWN: no rating", shown
    if not connected:
        return "not connected: nothing to compare", shown
    if lv is None:
        d.no_level.setdefault(net, []).append(who)
        return "UNKNOWN: the net has no level", shown
    verdict = "OK"
    for k in LIMITS:
        absolute, upper = k.startswith("abs"), k.endswith("max")
        value = (lv["tmax"] if absolute else lv["max"]) if upper else (lv["tmin"] if absolute else lv["min"])
        limits = []                                                   # (level of the pin's net, limit, how it was made)
        if k in pin["limits"]:
            limits.append((value, pin["limits"][k], ""))
        if k in pin["rel"]:
            to, plus = pin["rel"][k]
            for other in rel_pins(blk, to):
                if (ref, other) not in nl.pins:
                    continue                                            # reported as a pin the symbol lacks
                onet = nl.pins[(ref, other)][0]
                sign = f"{'+' if plus >= 0 else '-'} {_v(abs(plus))}"
                if onet == net:
                    if (plus < -EPS) if upper else (plus > EPS):
                        limits.append((value, value + plus, f"{to} {sign}, and the pin is on the net of {to} itself"))
                    continue
                olv = d.level.get(onet)
                if olv is None:
                    d.no_level.setdefault(onet, []).append(f"{who} (its rating refers to pin {other}, {to})")
                    verdict = "UNKNOWN: the net of the pin it refers to has no level"
                    continue
                s, n, rel = worst_point(d, net, onet, upper, absolute)
                how = f"{to} {sign} with {to} at {_v(n)} on net {onet}"
                if rel:
                    how += f"; {rel[2]}"
                else:
                    edge = (olv["tmax"] if absolute else olv["max"]) if upper else (olv["tmin"] if absolute else olv["min"])
                    how += (f", its {'lowest' if upper else 'highest'}: no relation of [tracks] ties {net} to {onet}, so the two are "
                            f"independent" + (f"; {'above' if upper else 'below'} {_v(edge + plus)} even with {to} at its "
                                              f"{'highest' if upper else 'lowest'}, {_v(edge)}" if _breaks(s, edge + plus, upper) else ""))
                limits.append((s, n + plus, how))
                off = off_value(d, net, onet, upper) if absolute and not _breaks(s, n + plus, upper) else None
                if off is not None and _breaks(off, plus, upper):
                    d.unknown.append(f"{who} on net {net}: its {k.replace('_', ' ')} is {to} {sign}; with {onet} off (0 V), {net} at "
                                     f"{_v(off)} would break it. The table does not say whether {onet} can be off while {net} is "
                                     f"driven: give {onet} its off state (transient_min = 0.0), or declare in [tracks] how {net} follows it")
                    verdict = "UNKNOWN: the off state of the net it refers to is not in the table" if verdict == "OK" else verdict
        for value, limit, how in limits:
            if not _breaks(value, limit, upper):
                continue
            what = {"abs_max": "above the absolute maximum", "abs_min": "below the absolute minimum",
                    "rec_max": "above the recommended maximum", "rec_min": "below the recommended minimum"}[k]
            text = (f"{who} on net {net}: {'worst case ' if absolute else ''}{_v(value)}"
                    f"{' (transients included)' if absolute else ''} is {what} {_v(limit)}" + (f" ({how})" if how else ""))
            if absolute:
                d.blockers.append(text)
                verdict = "BLOCKER"
            else:
                d.findings.append(text)
                verdict = verdict if verdict == "BLOCKER" else "FINDING"
    return verdict, shown


def default_level(d: Design, ref: str, num: str, pin: dict) -> dict:
    """What holds a control input while nothing drives it (MCU-64, MCU-65)."""
    nl, cfg = d.nl, d.cfg
    net = nl.pins[(ref, num)][0]
    who = pin_text(ref, num, pin["name"])
    others = d.others(ref, num)
    row = {"ref": ref, "pin": num, "name": pin["name"], "net": net, "input": pin["input"], "held_by": [], "parts_in_reset": []}

    def end(verdict, text):
        row["verdict"], row["text"] = verdict, text
        if verdict == "FINDING":
            d.findings.append(f"{who}: {text}")
        elif verdict == "NOTE":
            d.notes.append(f"{who}: {text}")
        return row

    def direction(n):
        lv = d.level.get(n)
        return "down" if lv and lv["tmax"] <= 0 else "up" if lv and lv["min"] > 0 else "unclear"

    pulls, unfitted = [], []
    for r, p in others:
        if prefix(r) in cfg["resistors"] and len(nl.pins_of(r)) == 2:
            far = next(nl.pins[(r, q)][0] for q in nl.pins_of(r) if q != p)
            if far in d.supply and far != net:
                (unfitted if nl.parts[r].dnp else pulls).append((r, nl.parts[r].value, far, direction(far)))
    row["held_by"] = [f"{r} ({val}) to {far}" for r, val, far, _ in pulls]
    held = " and ".join(row["held_by"])
    dnp_text = "".join(f"; {r} to {far} is marked not fitted and does not count" for r, _, far, _ in unfitted)
    if pin["input"] in ("up", "down"):
        against = [f"{r} ({val}) to {far}" for r, val, far, way in pulls if way != pin["input"]]
        if against:
            return end("NOTE", f"its own pull-{pin['input']} and {' and '.join(against)} pull against each other on {net}: "
                               f"a divider; compute the level (MCU-65)")
        if net in d.supply and direction(net) != pin["input"]:
            return end("NOTE", f"tied to {net} against its own pull-{pin['input']}: the level is defined, a small current flows")
        return end("PASS", f"held by its own pull-{pin['input']}" + (f", and by {held}" if held else "") + dnp_text)
    if pin["connect"] == OPEN:
        return end("PASS", "left open as the datasheet asks")
    if net in d.supply:
        return end("PASS", f"tied to {net}")
    if pulls:
        ways = {w for _, _, _, w in pulls}
        return end("PASS", f"held by {held}" + (": a divider; compute the level" if len(ways) > 1 else "") + dnp_text)
    if not others:
        return end("FINDING", f"can float: not connected, and no pull of its own{dnp_text}")
    in_reset, drivers, plugs = [], [], []
    for r, p in others:
        blk = d.tab.parts.get(d.block.get(r, ""))
        tpin = blk["pins"].get(p) if blk else None
        if r in nl.parts and nl.parts[r].dnp:
            continue                                                    # a part that is not fitted drives nothing
        floats = tpin["hiz"] if tpin and tpin["hiz"] is not None else bool(blk and blk["hiz"])     # the pin's own key wins
        if floats:
            in_reset.append(r)
        elif (tpin and tpin["input"]) or set(nl.pins[(r, p)][2].split("+")) & {"input", "power_in", "no_connect"}:
            continue                                                    # an input drives nothing
        elif prefix(r) in cfg["not_drivers"]:
            if PREFIX_KIND.get(prefix(r)) == "connector":               # no source while the cable is unplugged
                plugs.append(f"{r} pin {p}")
        elif prefix(r) in cfg["resistors"] and len(nl.pins_of(r)) == 2:
            far = next(nl.pins[(r, q)][0] for q in nl.pins_of(r) if q != p)
            drivers.append(f"{r} (to net {far}, which is no supply of [levels])")
        else:
            drivers.append(f"{r} pin {p}" + (f" ({d.sym[(r, p)]})" if not is_generic(d.sym[(r, p)], p) else ""))
    row["parts_in_reset"] = sorted(set(in_reset), key=_nat)
    row["connectors"] = plugs
    resets = ", ".join(row["parts_in_reset"])
    if drivers:
        return end("NOTE", f"no pull on {net}; driven by {', '.join(drivers)}; not checked whether it is always active"
                           + (f" (also on the net: {resets}, high-impedance in reset)" if resets else "") + dnp_text)
    if plugs:
        return end("FINDING", ("can float: its only source is connector " if len(plugs) == 1 else "can float: its only sources are connectors ")
                   + ", ".join(plugs) + f", and the cable may be unplugged (no pull on {net}"
                   + (f"; {resets} high-impedance in reset" if resets else "") + f"; MCU-65){dnp_text}")
    if resets:
        return end("FINDING", f"can float while {resets} {'is' if len(row['parts_in_reset']) == 1 else 'are'} in reset: "
                              f"no pull on {net}{dnp_text}")
    return end("FINDING", f"can float: no pull on {net} and nothing on it that drives{dnp_text}")


def settings(job, a) -> dict:
    cfg = job.cfg("ratings")
    mpn = a.mpn_field or cfg.get("mpn_field") or job.cfg("bom").get("mpn_field") or MPN_FIELDS
    out = {"mpn_fields": [mpn] if isinstance(mpn, str) else list(mpn),
           "mpn_from": "command line" if a.mpn_field else "board.toml" if (cfg.get("mpn_field") or job.cfg("bom").get("mpn_field")) else "default"}
    for key, default in (("need_block", list(PREFIX_KIND)), ("skip", []),
                         ("resistors", ["R"]), ("not_drivers", NOT_DRIVERS)):
        v = cfg.get(key, default)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise KicadIOError(f"board.toml [ratings] {key} must be a list of texts")
        out[key] = [x.upper() for x in v] if key != "skip" else v
        out[key + "_from"] = "board.toml" if key in cfg else "default"
    return out


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Pins and ratings: the exported netlist against the hand-typed datasheet table.", board=False,
                              epilog="Exit codes: 0 pass, 1 findings or UNKNOWN items, 2 could not run.")
    ap.add_argument("netlist", nargs="?", help="the exported netlist (kicadsexpr); not needed with --project")
    ap.add_argument("table", nargs="?", help="the datasheet table (TOML); not needed with --project")
    ap.add_argument("--mpn-field", action="append", help="symbol field that holds the maker part number (repeatable)")
    a = ap.parse_args(argv)
    job = pcb_common.resolve(a, need_board=False)
    rc = job.cfg("ratings")
    if job.project:
        files = kicad_io.project_files(job.project, job.settings)
        p_net = os.path.abspath(a.netlist) if a.netlist else job.path(rc["netlist"]) if rc.get("netlist") else os.path.join(files["out"], "netlist.net")
        p_tab = os.path.abspath(a.table) if a.table else job.path(rc["table"]) if rc.get("table") else os.path.join(files["src"], "datasheet_pins.toml")
    else:
        if not a.netlist or not a.table:
            raise KicadIOError("give --project <board folder>, or NETLIST.net and TABLE.toml with --out <folder>")
        p_net, p_tab = os.path.abspath(a.netlist), os.path.abspath(a.table)
    if not os.path.isfile(p_net):
        raise KicadIOError(f"no netlist {p_net}: export it first (scripts/schematic/export.py)")
    if not os.path.isfile(p_tab):
        raise KicadIOError(f"no datasheet table {p_tab}: type it from the datasheets (templates/DATASHEET_PINS.md)")
    cfg = settings(job, a)
    nl = kicad_io.read_netlist(p_net)
    tab = Table(p_tab)
    d = Design(nl, tab, cfg)
    d.sym = symbol_pin_names(p_net, nl)

    parts, inputs = [], []
    for ref in sorted(d.block, key=_nat):
        name = d.block[ref]
        blk = tab.parts[name]
        sym = nl.pins_of(ref)
        rows = []
        for num in sorted(set(sym) | set(blk["pins"]), key=_nat):
            pin = blk["pins"].get(num)
            if num not in sym:
                d.findings.append(f"{pin_text(ref, num, pin['name'])}: the datasheet table has this pin, the symbol has not")
                rows.append({"pin": num, "datasheet": pin["name"], "function": pin["function"], "symbol": None, "net": None,
                             "names": "MISSING ON THE SYMBOL", "level": "", "limits": [], "verdict": "not on the symbol"})
                continue
            net, sname = nl.pins[(ref, num)][0], d.sym[(ref, num)]
            if pin is None:
                d.findings.append(f"{pin_text(ref, num, sname)} on net {net}: the symbol has this pin, the datasheet table "
                                  f"(block \"{name}\") has not")
                rows.append({"pin": num, "datasheet": None, "function": "", "symbol": sname, "net": net, "names": "MISSING IN THE TABLE",
                             "connected": bool(d.others(ref, num)), "level": d.lvl_text(net), "limits": [], "verdict": "not in the table"})
                continue
            if is_generic(sname, num):
                names = "symbol has no name"
            elif norm_name(sname) in {norm_name(pin["name"])} | {norm_name(x) for x in pin["alias"]}:
                names = "same"
            else:
                names = "DIFFERENT"
                d.findings.append(f"{pin_text(ref, num)} on net {net}: the symbol calls it \"{sname}\", the datasheet table "
                                  f"\"{pin['name']}\"" + (f" (aliases: {', '.join(pin['alias'])})" if pin["alias"] else ""))
            connected = bool(d.others(ref, num))
            if pin["connect"] == OPEN and connected:
                d.findings.append(f"{pin_text(ref, num, pin['name'])}: the datasheet says leave open, but it is on net {net} with "
                                  + ", ".join(f"{r}.{p}" for r, p in d.others(ref, num)[:6]))
            if pin["connect"] == REQUIRED and not connected:
                d.findings.append(f"{pin_text(ref, num, pin['name'])}: the datasheet demands a connection, but it is not connected")
            verdict, shown = check_limits(d, ref, num, pin, blk)
            rows.append({"pin": num, "datasheet": pin["name"], "function": pin["function"], "symbol": sname, "net": net, "names": names,
                         "connected": connected, "level": d.lvl_text(net) if connected else "", "limits": shown, "verdict": verdict,
                         "hiz_in_reset": pin["hiz"]})
            if pin["input"]:
                inputs.append(default_level(d, ref, num, pin))
        parts.append({"ref": ref, "block": name, "value": nl.parts[ref].value, "datasheet": blk["datasheet"],
                      "io_hiz_in_reset": blk["hiz"], "pins": rows})
    apart = [f"{p['ref']} pin {r['pin']} = {'true' if r['hiz_in_reset'] else 'false'}" for p in parts for r in p["pins"]
             if r.get("hiz_in_reset") is not None]
    need = [(r, d.kind(r)) for r in sorted(nl.parts, key=_nat) if d.kind(r)]
    for ref, kind in need:
        if ref not in d.block:
            d.unknown.append(f"{ref} ({kind}, {nl.parts[ref].value or 'no value'}, {len(nl.pins_of(ref))} pins): no block in the table")
    for net in sorted(d.no_level):
        d.unknown.append(f"net {net}: no level in the table ([levels] or [nets]); waiting for it: {', '.join(d.no_level[net][:8])}"
                         + (" ..." if len(d.no_level[net]) > 8 else ""))
    d.findings = [f"table: {e}" for e in tab.errors] + d.findings

    # ---- the report
    n_pins = sum(len(p["pins"]) for p in parts)
    n_generic = sum(1 for p in parts for r in p["pins"] if r["names"] == "symbol has no name")
    n_in = {k: sum(1 for r in inputs if r["input"] == k) for k in ("none", "up", "down")}
    skipped = sorted((r for r in nl.parts if any(fnmatch.fnmatchcase(r, pat) for pat in cfg["skip"])), key=_nat)
    bad = len(d.blockers) + len(d.findings)
    result = "FAIL" if bad else ("FAIL (UNKNOWN items are not a pass)" if d.unknown else "PASS")
    md = ["# Pins and ratings against the hand-typed datasheet table", "",
          f"Script `ratings_check.py`, run {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}; "
          f"settings: {job.source_note}.",
          f"Netlist `{os.path.basename(p_net)}`, SHA-256 `{kicad_io.sha256(p_net)}` ({nl.tool or 'tool not named'}); "
          f"table `{os.path.basename(p_tab)}`, SHA-256 `{kicad_io.sha256(p_tab)}`.", "",
          f"**Result: {result}**: {len(d.blockers)} blocker(s), {len(d.findings)} finding(s), {len(d.unknown)} UNKNOWN, "
          f"{len(d.notes)} note(s).", "",
          f"- Parts with a block: {len(parts)}; parts that need one: {len(need)} "
          f"({', '.join(sorted({k for _, k in need})) or 'none'}); without one: {sum(1 for r, _ in need if r not in d.block)}.",
          f"- Pins compared: {n_pins}; of them {n_generic} where the symbol has no name of its own (number checked only).",
          f"- Control inputs declared in the table (key `input`): {len(inputs)} ({n_in['none']} without a pull of their own, "
          f"{n_in['up']} with a pull-up, {n_in['down']} with a pull-down inside). A pin without the key is NOT checked for "
          f"its default level.",
          f"- Parts whose pins are high-impedance in reset (`io_hiz_in_reset`): "
          f"{', '.join(p['ref'] for p in parts if p['io_hiz_in_reset']) or 'none declared'}; single pins set apart "
          f"(`hiz_in_reset`): {', '.join(apart) or 'none'}.",
          "- A connector pin is no source by default: the cable may be unplugged (MCU-65 asks for a resistor there).",
          f"- A rating relative to a pin on another net: the two nets are independent (opposite extremes) unless `[tracks]` "
          f"relates them ({len(d.rel_used)} relation(s) applied); an absolute one also with the other net off (0 V), and UNKNOWN "
          f"where the table does not say whether that state occurs.",
          "- The table is a person's statement of the datasheets. A typing error in it passes this check: the schematic "
          "reviewer compares it with the datasheets.", "",
          "| Setting | Value | From |", "|---|---|---|",
          f"| maker part number field | {', '.join(cfg['mpn_fields'])} | {cfg['mpn_from']} |",
          f"| `need_block` (reference prefixes; polarised capacitors by their symbol) | {', '.join(cfg['need_block'])} | {cfg['need_block_from']} |",
          f"| `skip` | {', '.join(cfg['skip']) or '-'}" + (f" (left out: {', '.join(skipped)})" if skipped else "") + f" | {cfg['skip_from']} |",
          f"| `resistors` (can be a pull) | {', '.join(cfg['resistors'])} | {cfg['resistors_from']} |",
          f"| `not_drivers` (never drive a net) | {', '.join(cfg['not_drivers'])} | {cfg['not_drivers_from']} |", ""]
    for title, items, tag in (("Blockers (beyond an absolute maximum)", d.blockers, "BLOCKER"), ("Findings", d.findings, "FINDING"),
                              ("UNKNOWN (none of these at gate 1)", d.unknown, "UNKNOWN"),
                              ("Notes (not counted)", d.notes, "NOTE")):
        md += [f"## {title}", ""] + ([f"- {tag}: {x}" for x in items] or ["None."]) + [""]
    md += ["## Default levels of control inputs (MCU-64, MCU-65)", ""]
    if inputs:
        md += ["| Pin | Net | Pull inside | Result | What holds it |", "|---|---|---|---|---|"]
        md += [f"| {pin_text(r['ref'], r['pin'], r['name'])} | {r['net']} | {r['input']} | {r['verdict']} | {r['text']} |" for r in inputs]
    else:
        md.append("The table declares no control input (no pin carries `input`): NOT CHECKED. Every enable, shutdown, chip "
                  "select, reset, driver-enable, write-protect, mode and address pin, and every gate or base, needs the key.")
    md += ["", "## Per part", ""]
    for p in parts:
        md += [f"### {p['ref']}: {p['block']}" + (" (pins high-impedance in reset)" if p["io_hiz_in_reset"] else ""), "",
               f"Value on the schematic: {p['value'] or '-'}. Datasheet: {p['datasheet'] or 'NOT NAMED in the table'}.", "",
               "Pin table (the rows of the pin table of the reference check; its column \"OK?\" is written by hand there):", "",
               "| Pin | Datasheet name | Function | Our net |", "|---|---|---|---|"]
        for r in p["pins"]:
            net = "-" if r["net"] is None else r["net"] if r.get("connected") else "not connected"
            md.append(f"| {r['pin']} | {r['datasheet'] or '(not in the table)'} | {r['function']} | {net}"
                      + (" (NOT ON THE SYMBOL)" if r["net"] is None else "") + " |")
        md += ["", "The check:", "",
               "| Pin | Datasheet name | Symbol name | Names | Net | Level of the net | Limits of the pin | Result |",
               "|---|---|---|---|---|---|---|---|"]
        for r in p["pins"]:
            md.append(f"| {r['pin']} | {r['datasheet'] or '-'} | {(r['symbol'] if r['symbol'] is not None else '-') or '(none)'} | {r['names']} | "
                      f"{r['net'] or '-'} | {r['level'] or '-'} | {'; '.join(r['limits']) or '-'} | {r['verdict']} |")
        md.append("")
    md += ["## Levels used", "", "| Net | Level | From | Source named in the table |", "|---|---|---|---|"]
    for net in sorted(d.level, key=_nat):
        md.append(f"| {net} | {d.lvl_text(net)} | {d.level_from[net]} | {d.level[net]['source'] or '-'} |")
    md += ["", "## Relations used (`[tracks]`)", ""]
    md += (["| Net | Follows | Offset | Declared by | Source |", "|---|---|---|---|---|"]
           + [f"| {t['net']} | {t['follows']} | {t['offset'][0]:+g} .. {t['offset'][1]:+g} V | [tracks] \"{t['from']}\" | "
              f"{t['source'].replace('|', '/')} |" for t in d.rel_used] if d.rel_used else
           ["None: two different nets are taken as independent."])
    md += ["", "## Not checked", "",
           "Whether the table is typed correctly, its relations (`[tracks]`) and off states included; currents, power, timing "
           "and thresholds; a current that a datasheet allows into a pin beyond a relative rating; the value of a pull "
           "resistor and the level of a divider; pulls through a resistor network or a second part; whether a driver is "
           "always active; any pin without the key `input`; the parts that need no block by their reference and have none "
           f"({sum(1 for r in nl.parts if r not in d.block and not d.kind(r))} of {len(nl.parts)} parts).",
           "", f"**Result: {result}** ({len(d.blockers)} blocker(s), {len(d.findings)} finding(s), {len(d.unknown)} UNKNOWN)"]
    data = {"script": "ratings_check.py", "netlist": os.path.basename(p_net), "netlist_sha256": kicad_io.sha256(p_net),
            "table": os.path.basename(p_tab), "table_sha256": kicad_io.sha256(p_tab), "result": result,
            "settings": {k: v for k, v in cfg.items()}, "counts": {"parts_with_block": len(parts), "parts_needing_block": len(need),
                                                                  "pins": n_pins, "pins_without_symbol_name": n_generic,
                                                                  "control_inputs": len(inputs), "inputs_by_pull": n_in},
            "blockers": d.blockers, "findings": d.findings, "unknown": d.unknown, "notes": d.notes,
            "default_levels": inputs, "can_float": [r for r in inputs if r["verdict"] == "FINDING"], "parts": parts,
            "levels": {n: dict(d.level[n], **{"from": d.level_from[n]}) for n in sorted(d.level, key=_nat)}, "tracks": d.rel_used}
    p_md, _ = pcb_common.write_result(job.out, "ratings_check", md, data)
    for tag, items in (("BLOCKER", d.blockers), ("FINDING", d.findings), ("UNKNOWN", d.unknown)):
        for x in items[:MAX_LISTED]:
            print(f"{tag:8} {x}")
    print(f"{result}: {len(d.blockers)} blocker(s), {len(d.findings)} finding(s), {len(d.unknown)} UNKNOWN, {len(d.notes)} note(s); "
          f"{len(parts)} part(s) with a block, {n_pins} pins, {len(inputs)} control input(s) -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
