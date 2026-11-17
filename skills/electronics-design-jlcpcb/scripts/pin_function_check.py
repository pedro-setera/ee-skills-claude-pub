"""Pin functions: what the design uses each pin of a programmable part for, against what the datasheet says the pin can do.

What a PASS covers
    Per-pin table consistency: each used pin's function against what the hand-typed datasheet table lists for that pin, one
    job per pin, the pin's own limits; the direction of a function and shared resources only where the table declares them.
    It is not proof that the firmware's whole pin, clock and peripheral configuration can be built: the clock tree, DMA,
    interrupt lines, IO bank voltages and functions that exclude each other inside the chip are outside the checked scope and
    belong to the joint peripheral-allocation review. The report says so in its head, its result line and "Not checked".

What it checks (schematic stage; no board and no KiCad needed)
    Three files: the netlist that KiCad exports from the schematic; the hand-typed datasheet table
    (src/datasheet_pins.toml, the table ratings_check.py reads, with the keys below added per pin); and the use
    table (src/pin_use.toml), in which the designer writes, for every connected pin of every programmable part,
    the function wanted and the direction. Every pin of every checked part gets ONE result:
      1 use entry     a connected pin without a use entry (FAIL); a use entry for a pin the part does not have,
                      or for a pin that the netlist connects to nothing (FAIL). A pin with one fixed function
                      (`functions = []`: a supply, ground, a reset pin) needs no entry.
      2 function      the function wanted is not among the pin's `functions`, its name or its aliases (FAIL, with
                      the pins that do offer it). No `functions` list for the pin: UNKNOWN, never PASS.
      3 one job       two functions written for one pin (FAIL); one function claimed by two pins (FAIL on both),
                      unless the block lists it in `on_several_pins` or it is the name of several pins (VDD).
      4 direction     an output, a two-way or an open-drain use on an `input_only` pin; a push-pull use (out,
                      both) on an `open_drain_only` pin; an analogue use on a pin without `analog = true` (FAIL).
      5 chip's own    a pin that the chip samples at reset, or that belongs to the debug port or to the
                      oscillator, used for another function: FAIL, or ACCEPTED when its use entry carries
                      `reason = "..."` (listed with the reason). Used for its own job: PASS, and the text says
                      what the datasheet demands (the level at reset is NOT checked here). A reset-sampled pin
                      with other functions and no `function` in `sampled_at_reset`: every use needs a reason.
      6 no data       a checked part without a block, or whose block has no `functions` on any pin: CANNOT RUN,
                      exit code 2, with what to type and from which datasheet table. The same when there is a
                      programmable part and no use table: the report then holds a skeleton to fill in.
      7 mode          only where the block gives `function_modes` (with its `source`): a use whose direction is not
                      the mode of its function (a receive input used as "out") is FAIL; the mode "both" fits in, out
                      and both. A used function without a mode: its direction is NOT CHECKED (said on the pin and
                      counted in the result line), never a pass for it. No direction is guessed from a name.
      8 shared        only where the block declares them: pins whose functions share one entry of `resources` (the
                      channels of one timer, a clock output) need the same `setting` in their use entries (FAIL when
                      they differ, UNKNOWN when one is missing); a peripheral of `pin_sets` takes all its used pins
                      from one set (FAIL when its uses mix two sets). Without them nothing is inferred: the report
                      says so.
    Coverage. Every chip of the netlist (reference U or IC with 8 pins or more; settable) must be classified: its block
    says `programmable = true` or `programmable = false`. A chip without a block, or whose block says neither (and that
    nothing else marks): UNKNOWN, exit code 1, naming the chip and what to type.
    Which parts are checked: every part whose block says `programmable = true`; a block without that key counts when it
    says `io_hiz_in_reset = true` or when one of its pins carries `functions` (it is then classified too);
    `programmable = false` leaves a part out (a module that runs its maker's firmware); `--ref U3` checks a part whatever
    its block says. NOT APPLICABLE ("no programmable part declared", exit code 0) only when every chip is classified and
    none is checked; the chips of the netlist are named.

Why it exists (the real failure, told without names)
    A schematic gave a microcontroller pin a job that the pin cannot do: a serial transmit line on a pin without
    the transmit function of that port, an analogue input on a pin without a converter channel, a signal on the
    pin the chip reads at reset to choose its start mode. The electrical rule check saw nothing, because the
    symbol only says "bidirectional". Such a fault is found when the firmware is written, after the boards are
    ordered. Until now the comparison was a table filled in by hand; here it is made by a script that can fail.

Usage
    python -I pin_function_check.py --project <hardware/board folder>     netlist out/netlist.net, tables
                                                                          src/datasheet_pins.toml and
                                                                          src/pin_use.toml; results in out/
    python -I pin_function_check.py NETLIST.net TABLE.toml USE.toml --out FOLDER
    options: --ref REF (repeatable): check this part too; --mpn-field NAME (repeatable): the symbol field that
             holds the maker part number; --chip-prefix P (repeatable) and --chip-min-pins N: what counts as a chip
    Results: pin_function_check.md and pin_function_check.json. The per-part table has the first columns of the
    pin map of templates/FIRMWARE_HANDOVER.md (pin, pin name, net, function on this board, direction).

The datasheet table (TOML; the other keys of the file belong to ratings_check.py and are not read here)
    [parts."<maker part number>"]  refs = ["U1"], datasheet = "...", io_hiz_in_reset = true,
              programmable = true | false, on_several_pins = ["MCO"],
              resources = {TIM1 = ["TIM1_CH1", "TIM1_CH2"]}       functions that share one resource of the chip
    [parts."<maker part number>".function_modes]      source = "<datasheet table or page>", UART2_RX = "in",
              UART2_TX = "out", I2C1_SDA = "open drain", ADC_IN0 = "analog", SWDIO = "both" (or a list of modes)
    [parts."<maker part number>".pin_sets.UART2]       default = {"6" = "UART2_TX", "7" = "UART2_RX"},
              remap = {"19" = "UART2_TX", "20" = "UART2_RX"}  two or more sets; a peripheral takes its pins from one
    [parts."<maker part number>".pins]  "<number>" = {name, alias,
              functions = ["USART1_TX", "TIM1_CH2"]   everything the maker's table of pin functions lists for the
                                                      pin; the name and the aliases count too; [] = one fixed function
              input_only = true, open_drain_only = true, analog = true,
              sampled_at_reset = {level = "low: start from the main flash", function = "BOOT0"},
              debug = "SWDIO", oscillator = "OSC_IN"}   the function that is the chip's own job on this pin
    A part is matched by `refs`, or by its maker part number field when that equals the block's name.

The use table (TOML; one table per programmable part, named by its designator)
    [U1]
    "17" = {function = "USART1_TX", direction = "out", purpose = "serial data to the host", reason = "...", setting = "..."}
    function: one of the pin's functions (a plain port pin: the pin's name). direction: in, out, both,
    open drain, analog (also: input, output, analogue). purpose: free text, the column "Function on this board"
    of the firmware hand-over. reason: only for check 5. setting: only for a function of a declared resource: what
    this use needs from it (a timer's frequency), the same words on every pin of one resource. Names and settings are
    compared without letter case, spaces and "_".

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [pin_functions]
    netlist   = "out/netlist.net"              # relative to the board folder
    table     = "src/datasheet_pins.toml"
    use       = "src/pin_use.toml"
    mpn_field = "MPN"                          # name or list of names (default: [ratings] mpn_field, then [bom]
                                               # mpn_field, then the names jlc_parts.py knows)
    chip_prefixes = ["U", "IC"]                # what counts as a chip that the table must classify: these reference
    chip_min_pins = 8                          # prefixes, with this many pins or more

Exit codes
    0  PASS: every pin of every checked part is PASS or ACCEPTED and every chip is classified; or NOT APPLICABLE
    1  FAIL: a pin is FAIL or UNKNOWN, a chip is not classified, or one of the two tables has a mistake; each is listed
    2  CANNOT RUN: no netlist, no datasheet table, a file that cannot be read, no function data for a checked
       part, no use table, no --out, a wrong chip rule. Never a pass.

Not checked: the clock tree, DMA, interrupt lines, IO bank voltages, functions that exclude each other inside the chip
beyond the declared `resources` and `pin_sets` (the joint peripheral-allocation review); whether the two tables are typed
correctly (the schematic reviewers compare them with the datasheet and with the design); whether the level a
reset-sampled pin needs is really held (ratings_check.py: default levels); the state of a pin in reset and while the chip
is programmed; voltages (ratings_check.py); drive strength, speed, 5 V tolerance; whether the table is of the exact
package that is fitted; a pin that the table has and the symbol lacks, and the spelling of the keys of the datasheet
table (ratings_check.py reports both). Uses ratings_check.py for the pin names of the symbols and the names of the part
number field.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import datetime
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
import ratings_check  # noqa: E402   (the symbol's own pin names; the field names of the maker part number)
from kicad_io import KicadIOError  # noqa: E402

DIRECTIONS = {"in": "in", "input": "in", "out": "out", "output": "out", "push-pull": "out", "push pull": "out",
              "both": "both", "in/out": "both", "inout": "both", "io": "both", "bidirectional": "both",
              "open drain": "open drain", "open-drain": "open drain", "od": "open drain",
              "analog": "analog", "analogue": "analog"}
USE_KEYS = ("function", "direction", "purpose", "reason", "setting")
CHIP_PREFIXES = ("U", "IC")         # what counts as a chip that the table must classify (settable)
CHIP_MIN_PINS = 8
RULE = (CHIP_PREFIXES, CHIP_MIN_PINS)
RANK = {"PASS": 0, "ACCEPTED": 1, "UNKNOWN": 2, "FAIL": 3}
MAX_LISTED = 60
TEMPLATE = "templates/DATASHEET_PINS.md"
EXAMPLE = '"17" = {name = "PA9", functions = ["USART1_TX", "TIM1_CH2"]}'
COVERS = ("per-pin table consistency: each used pin's function against what the datasheet table lists for that pin, one job "
          "per pin and the pin's own limits; the direction of a function and shared resources (one timer, one pin set) only "
          "where the table declares them")
OUTSIDE = "the clock tree, DMA, interrupt lines, IO bank voltages and functions that exclude each other inside the chip"


def _nat(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def norm(name: str) -> str:
    """A function name without letter case, spaces and underscores ("usart1 tx" is "USART1_TX")."""
    return re.sub(r"[\s_]+", "", str(name)).upper()


def jobs(value) -> list:
    """The functions a use entry asks for: one is right; "A / B", "A, B", "A and B" or a list are several."""
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in re.split(r"\s*(?:/|,|;|&|\s\+\s|\sand\s)\s*", str(value)) if x.strip()]


def _cell(text) -> str:
    return " ".join(str(text).replace("|", "/").split()) or "-"


def _load_toml(path: str, what: str) -> dict:
    try:
        import tomllib
    except ImportError:
        raise KicadIOError(f"reading {what} needs Python 3.11 or newer (tomllib)") from None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except OSError as e:
        raise KicadIOError(f"{what} cannot be read: {e}") from None
    except tomllib.TOMLDecodeError as e:
        hint = " (a pin typed twice in one table? One pin has one job)" if "overwrite" in str(e).lower() else ""
        raise KicadIOError(f"{what} {os.path.basename(path)}: not valid TOML: {e}{hint}") from None


# ---- the datasheet table: only the keys of this check ------------------------------------------------------------------
class Table:
    """The blocks of datasheet_pins.toml as this check needs them. Keys of ratings_check.py are left alone.
    parts: {block name: {refs, programmable (True, False or None), hiz, datasheet, several, pins, modes, modes_source,
    shared, sets, errors}}"""

    def __init__(self, path: str):
        data = _load_toml(path, "the datasheet table")
        self.path = path
        self.parts: dict[str, dict] = {}
        blocks = data.get("parts") or {}
        for mpn, blk in (blocks.items() if isinstance(blocks, dict) else []):
            if isinstance(blk, dict):
                self.parts[mpn] = self._part(mpn, blk)

    @staticmethod
    def _part(mpn: str, blk: dict) -> dict:
        where = f"[parts.\"{mpn}\"]"
        errors = []
        refs = blk.get("refs", [])
        if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
            refs = []                                                   # ratings_check.py reports the wrong type
        prog = blk.get("programmable")
        if prog is not None and not isinstance(prog, bool):
            errors.append(f"{where}: programmable must be true or false")
            prog = None
        several = blk.get("on_several_pins", [])
        if not isinstance(several, list) or not all(isinstance(x, str) for x in several):
            errors.append(f"{where}: on_several_pins must be a list of function names")
            several = []
        pins = {}
        raw = blk.get("pins") if isinstance(blk.get("pins"), dict) else {}
        for num, p in raw.items():
            if not isinstance(p, dict):
                continue
            pw = f"{where} pin {num}"
            q = {"name": p["name"].strip() if isinstance(p.get("name"), str) else "",
                 "alias": [a for a in p.get("alias", []) if isinstance(a, str)] if isinstance(p.get("alias"), list) else [],
                 "functions": None, "input_only": False, "open_drain_only": False, "analog": False, "own": []}
            if "functions" in p:
                if isinstance(p["functions"], list) and all(isinstance(x, str) and x.strip() for x in p["functions"]):
                    q["functions"] = [x.strip() for x in p["functions"]]
                else:
                    errors.append(f"{pw}: functions must be a list of function names, for example [\"USART1_TX\", \"TIM1_CH2\"], "
                                  f"or [] for a pin with one fixed function")
            if isinstance(p.get("function"), list):
                errors.append(f"{pw}: `function` holds a list; the list of what the pin can do is the key `functions`")
            for k in ("input_only", "open_drain_only", "analog"):
                if k in p:
                    if isinstance(p[k], bool):
                        q[k] = p[k]
                    else:
                        errors.append(f"{pw}: {k} must be true or false")
            can = offered(q)
            for k, what in (("debug", "a pin of the debug port"), ("oscillator", "a pin of the oscillator")):
                if k in p:
                    if isinstance(p[k], str) and p[k].strip():
                        q["own"].append({"key": k, "what": f"{what} ({p[k].strip()})", "function": p[k].strip()})
                        if q["functions"] is not None and norm(p[k]) not in can:
                            errors.append(f"{pw}: {k} names \"{p[k]}\", which is not among the pin's functions")
                    else:
                        errors.append(f"{pw}: {k} must name the pin's function in that role, for example {k} = "
                                      f"\"{'SWDIO' if k == 'debug' else 'OSC_IN'}\"")
            if "sampled_at_reset" in p:
                s = p["sampled_at_reset"]
                if (isinstance(s, dict) and isinstance(s.get("level"), str) and s["level"].strip() and set(s) <= {"level", "function"}
                        and isinstance(s.get("function", ""), str)):
                    fn = s.get("function", "").strip()
                    q["own"].append({"key": "sampled_at_reset", "what": f"sampled at reset by the chip (it needs: {s['level'].strip()})",
                                     "function": fn})
                    if fn and q["functions"] is not None and norm(fn) not in can:
                        errors.append(f"{pw}: sampled_at_reset names \"{fn}\", which is not among the pin's functions")
                else:
                    errors.append(f"{pw}: sampled_at_reset needs {{level = \"<the level the pin needs at reset, and what it "
                                  f"selects>\"}}, with function = \"<its name in that role>\" when the datasheet gives one")
            pins[str(num)] = q
        anywhere = set().union(*(offered(q) for q in pins.values()))
        modes, source = Table._modes(where, blk.get("function_modes"), anywhere, errors)
        return {"refs": refs, "programmable": prog, "hiz": blk.get("io_hiz_in_reset") is True,
                "datasheet": " ".join(str(blk.get("datasheet", "")).split()), "several": {norm(x) for x in several},
                "pins": pins, "errors": errors, "has_functions": any(q["functions"] is not None for q in pins.values()),
                "modes": modes, "modes_source": source, "shared": Table._shared(where, blk.get("resources"), anywhere, errors),
                "sets": Table._sets(where, blk.get("pin_sets"), pins, errors)}

    @staticmethod
    def _modes(where: str, fm, anywhere: set, errors: list) -> tuple[dict, str]:
        """function_modes: ({function: {modes}}, source). Without a source no mode is used."""
        if fm is None:
            return {}, ""
        if not isinstance(fm, dict):
            errors.append(f"{where}: function_modes must be a table: {{source = \"<datasheet table and page>\", UART2_RX = \"in\"}}")
            return {}, ""
        source = " ".join(fm["source"].split()) if isinstance(fm.get("source"), str) else ""
        if not source:
            errors.append(f"{where}: function_modes needs source = \"<the datasheet table or page that gives these modes>\"; "
                          f"without it no mode is used")
        modes = {}
        for fn, v in fm.items():
            if fn == "source":
                continue
            vals = v if isinstance(v, list) else [v]
            got = {DIRECTIONS.get(" ".join(x.lower().split())) if isinstance(x, str) else None for x in vals}
            if not vals or None in got:
                errors.append(f"{where}: function_modes {fn} = {json.dumps(v)}: a mode is in, out, both, open drain or analog, "
                              f"or a list of them")
            elif norm(fn) not in anywhere:
                errors.append(f"{where}: function_modes names {fn}, which no pin of the block offers")
            elif source:
                modes[norm(fn)] = got
        return modes, source

    @staticmethod
    def _shared(where: str, rv, anywhere: set, errors: list) -> dict:
        """resources: {function: resource name}."""
        shared = {}
        if rv is None:
            return shared
        if not isinstance(rv, dict):
            errors.append(f"{where}: resources must be a table, for example {{TIM1 = [\"TIM1_CH1\", \"TIM1_CH2\"]}}")
            return shared
        for res, fns in rv.items():
            if not isinstance(fns, list) or not fns or not all(isinstance(x, str) and x.strip() for x in fns):
                errors.append(f"{where}: resources {res} must list the functions that share it, for example [\"TIM1_CH1\", \"TIM1_CH2\"]")
                continue
            for f in fns:
                if norm(f) not in anywhere:
                    errors.append(f"{where}: resources {res} names {f}, which no pin of the block offers")
                elif shared.get(norm(f), res) != res:
                    errors.append(f"{where}: {f} is listed in two resources ({shared[norm(f)]} and {res}): one function, one resource")
                else:
                    shared[norm(f)] = res
        return shared

    @staticmethod
    def _sets(where: str, pv, pins: dict, errors: list) -> dict:
        """pin_sets: {peripheral: {set name: {(pin number, function)}}}."""
        sets = {}
        if pv is None:
            return sets
        if not isinstance(pv, dict):
            errors.append(f"{where}: pin_sets must be a table of peripherals, each with two or more sets of pin = function")
            return sets
        for per, groups in pv.items():
            if not (isinstance(groups, dict) and len(groups) >= 2 and all(
                    isinstance(g, dict) and g and all(isinstance(f, str) for f in g.values()) for g in groups.values())):
                errors.append(f"{where}: pin_sets {per} needs two or more sets, each a table of pin = function, for example "
                              f"{{default = {{\"6\" = \"UART2_TX\"}}, remap = {{\"19\" = \"UART2_TX\"}}}}")
                continue
            sets[per] = {}
            for name, members in groups.items():
                sets[per][name] = set()
                for num, f in members.items():
                    q = pins.get(str(num))
                    if q is None or norm(f) not in offered(q):
                        errors.append(f"{where}: pin_sets {per} {name}: pin {num} "
                                      + ("is not in the block" if q is None else f"does not offer {f}"))
                    else:
                        sets[per][name].add((str(num), norm(f)))
        return sets

    def marked(self, name: str) -> str:
        """Why the table itself asks for this block to be checked, or "" when it does not."""
        blk = self.parts[name]
        if blk["programmable"] is True:
            return "programmable = true"
        if blk["programmable"] is None and blk["hiz"]:
            return "io_hiz_in_reset = true"
        if blk["programmable"] is None and blk["has_functions"]:
            return "its pins carry `functions`"
        return ""


def offered(pin: dict) -> set:
    return {norm(x) for x in (pin["functions"] or []) + [pin["name"]] + pin["alias"] if x}


# ---- the use table -------------------------------------------------------------------------------------------------------
def read_use(path: str) -> tuple[dict, list]:
    """({designator: {pin number: entry}}, mistakes that belong to no pin)."""
    data = _load_toml(path, "the use table")
    use, errors = {}, []
    for ref, tab in data.items():
        if not isinstance(tab, dict):
            errors.append(f"use table: \"{ref}\" must be a table named by a designator, [{ref}], with one line per pin")
            continue
        if re.fullmatch(r"<.*>", ref.strip()):
            errors.append(f"use table: [{ref}] is still a placeholder of the template")
            continue
        use[ref] = {str(num): entry for num, entry in tab.items()}
    return use, errors


def match_blocks(nl, tab: Table, mpn_fields: list) -> tuple[dict, list, list]:
    """{designator: block name}, mistakes, notes: by `refs`, else by the maker part number field (as ratings_check.py).
    A block that is marked for this check and fits no part is a mistake: it must never end as "not applicable"."""
    def key(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())

    def mpn(ref):
        fields = {key(k): v for k, v in nl.parts[ref].fields.items()}
        return next((fields[k].strip() for k in (key(n) for n in mpn_fields) if fields.get(k, "").strip()), "")

    block, errors, notes = {}, [], []
    for name, blk in tab.parts.items():
        refs = [r for r in blk["refs"] if r in nl.parts]
        if tab.marked(name):
            errors += [f"table: the block \"{name}\" names {r}, which the netlist does not have" for r in blk["refs"] if r not in nl.parts]
        for r in nl.parts:
            have = mpn(r).upper()
            if r not in refs and have and (have == name.strip().upper() or name.strip().upper() in have.split()):
                refs.append(r)
        if not refs and tab.marked(name) and not blk["refs"]:
            errors.append(f"table: the block \"{name}\" is marked for this check ({tab.marked(name)}), but no part of the netlist "
                          f"carries it: a block is matched by refs = [\"U1\"], or by a part number field of the symbol "
                          f"({', '.join(mpn_fields[:3])} ...) that equals the block's name")
        for r in refs:
            if r in block and block[r] != name:
                errors.append(f"table: {r} fits two blocks: \"{block[r]}\" and \"{name}\"")
            else:
                block[r] = name
    return block, errors, notes


def classify(nl, tab: Table, fields: list, named: list, rule: tuple) -> tuple:
    """(block, errors, notes, checked, open): checked [(designator, block name or None, why it is checked)]; open: the chips
    of the netlist that the table does not classify, [(designator, block name or None)] (no block, or a block that says
    neither programmable = true nor false and that nothing else marks)."""
    block, errors, notes = match_blocks(nl, tab, fields)
    checked = []
    for ref in sorted(nl.parts, key=_nat):
        name = block.get(ref)
        why = "--ref" if ref in named else (tab.marked(name) if name else "")
        if why:
            checked.append((ref, name, why))
    done = {r for r, _, _ in checked}
    unclassified = [(r, block.get(r)) for r in chip_refs(nl, rule)
                    if r not in done and not (block.get(r) and tab.parts[block[r]]["programmable"] is False)]
    return block, errors, notes, checked, unclassified


def open_text(nl, ref: str, name, table: str) -> str:
    """What to type for a chip that the table does not classify."""
    if name is None:
        return (f"{chip_label(nl, ref)}: no block in {table}, so nothing says whether it runs firmware: type its block from the maker's "
                f"datasheet ({TEMPLATE}) with programmable = true (it runs the project's firmware or configuration; then the "
                f"`functions` of its pins) or programmable = false (a fixed function, or its maker's own firmware)")
    return (f"{chip_label(nl, ref)}: its block \"{name}\" says neither programmable = true nor programmable = false: write the one "
            f"that is true ({TEMPLATE}, rule 4c)")


def chip_refs(nl, rule: tuple = RULE) -> list:
    """The chips of a netlist (a reference prefix of the rule, at least its number of pins), the largest first."""
    prefixes, least = {p.upper() for p in rule[0]}, rule[1]
    found = []
    for ref in nl.parts:
        n = len(nl.pins_of(ref))
        m = re.match(r"[A-Za-z_]+", ref)
        if n >= least and m and m.group(0).upper() in prefixes:
            found.append((-n, _nat(ref), ref))
    return [r for _, _, r in sorted(found)]


def chip_label(nl, ref: str) -> str:
    part = nl.parts[ref]
    names = [x for x in dict.fromkeys((part.value, part.part)) if x]
    return f"{ref} ({' / '.join(names) or 'no value'}, {len(nl.pins_of(ref))} pins)"


def rule_text(rule: tuple) -> str:
    return f"reference {' or '.join(rule[0])}, {rule[1]} pins or more"


def chips(nl, rule: tuple = RULE) -> list:
    """The larger chips of a netlist: ["U5 (PIC16F54, 18 pins)", ...], the largest first."""
    return [chip_label(nl, r) for r in chip_refs(nl, rule)]


def chips_text(nl, rule: tuple = RULE, limit: int = 12) -> str:
    c = chips(nl, rule)
    if not c:
        return f"the netlist has no chip ({rule_text(rule)})"
    return (f"chips of the netlist ({rule_text(rule)}): " + ", ".join(c[:limit])
            + (f" and {len(c) - limit} more" if len(c) > limit else ""))


def chip_rule(cfg: dict, prefixes=None, least=None) -> tuple[tuple, str]:
    """What counts as a chip that the table must classify, and where that comes from: ((prefixes, pins), origin)."""
    p, p_from = CHIP_PREFIXES, "default"
    if prefixes:
        p, p_from = tuple(prefixes), "command line"
    elif "chip_prefixes" in cfg:
        v = cfg["chip_prefixes"]
        p, p_from = (tuple([v]) if isinstance(v, str) else tuple(v) if isinstance(v, list) else ()), "board.toml"
    if not p or not all(isinstance(x, str) and re.fullmatch(r"[A-Za-z_]+", x) for x in p):
        raise KicadIOError(("--chip-prefix" if p_from == "command line" else "board.toml [pin_functions] chip_prefixes")
                           + ' must be reference prefixes (letters), for example ["U", "IC"]')
    n, n_from = CHIP_MIN_PINS, "default"
    if least is not None:
        n, n_from = least, "command line"
    elif "chip_min_pins" in cfg:
        n, n_from = cfg["chip_min_pins"], "board.toml"
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise KicadIOError(("--chip-min-pins" if n_from == "command line" else "board.toml [pin_functions] chip_min_pins")
                           + " must be a whole number of pins, 1 or more, for example 8")
    return (p, n), (p_from if p_from == n_from else f"{p_from} (prefixes), {n_from} (pins)")


# ---- one part ------------------------------------------------------------------------------------------------------------
def check_part(nl, sym: dict, ref: str, blk: dict, entries: dict) -> list:
    """One row per pin of the part (and per use entry for a pin it does not have): the result and why."""
    on_part = nl.pins_of(ref)
    rows, claims = [], {}
    names_on = {}                                                       # a name that several pins carry (VDD) is no single function
    for q in blk["pins"].values():
        names_on[norm(q["name"])] = names_on.get(norm(q["name"]), 0) + 1
    for num in sorted(set(on_part) | set(entries), key=_nat):
        tp, entry = blk["pins"].get(num), entries.get(num)
        row = {"pin": num, "name": tp["name"] if tp else "", "net": None, "connected": False, "purpose": "", "direction": "",
               "function": "", "reason": "", "setting": "", "direction_check": "", "msgs": [], "_fn": "", "_dir": ""}
        rows.append(row)

        def say(state, text, row=row):
            row["msgs"].append((state, text))

        if num not in on_part:
            say("FAIL", f"the use table names this pin, but {ref} has no such pin in the netlist (its pins: "
                        f"{', '.join(sorted(on_part, key=_nat)[:3])} ... {sorted(on_part, key=_nat)[-1] if on_part else '-'})")
            continue
        net = nl.pins[(ref, num)][0]
        row["net"], row["connected"] = net, len(nl.nets[net]) > 1
        row["name"] = row["name"] or sym[(ref, num)]
        own = tp["own"] if tp else []
        if entry is None:
            if not row["connected"]:
                say("PASS", "not connected, not used")
            elif tp and tp["functions"] == []:
                say("PASS", f"one fixed function ({row['name']}): needs no use entry"
                    + "".join(f"; {o['what']}: not checked here" for o in own))
            else:
                say("FAIL", f"connected to net {net}, but no use entry: write what the design uses this pin for"
                    + ("" if tp and tp["functions"] is not None else "; the datasheet table has no function list for it either "
                       "(`functions`; [] for a pin with one fixed function)"))
            continue
        if not isinstance(entry, dict):
            say("FAIL", "its use entry must be {function = \"<one of the pin's functions>\", direction = \"in | out | both | "
                        "open drain | analog\"}")
            continue
        bad = sorted(set(entry) - set(USE_KEYS))
        if bad:
            say("FAIL", f"unknown key(s) {', '.join(bad)} in its use entry (known: {', '.join(USE_KEYS)})")
        row["purpose"] = str(entry.get("purpose", ""))
        row["reason"] = entry["reason"].strip() if isinstance(entry.get("reason"), str) else ""
        row["setting"] = entry["setting"].strip() if isinstance(entry.get("setting"), str) else ""
        if "setting" in entry and not row["setting"]:
            say("FAIL", "setting must be text: what this use needs from the shared resource, for example \"20 kHz\"")
        wanted = jobs(entry.get("function", ""))
        row["function"] = " / ".join(wanted)
        d = DIRECTIONS.get(" ".join(str(entry.get("direction", "")).lower().split()))
        row["direction"] = d or str(entry.get("direction", ""))
        if not row["connected"]:
            say("FAIL", f"the use table gives this pin a job ({row['function'] or 'no function named'}), but the netlist "
                        f"connects it to nothing")
        if d is None:
            say("FAIL", f"direction \"{entry.get('direction', '')}\" is none of: in, out, both, open drain, analog")
        if not wanted or any(re.fullmatch(r"<.*>", w) for w in wanted):
            say("FAIL", "its use entry names no function: function = \"<one of the pin's functions, or the pin's name>\"")
            continue
        if len(wanted) > 1:
            say("FAIL", f"two jobs on one pin ({' and '.join(wanted)}): one pin has one job")
            continue
        fn = wanted[0]
        row["_fn"] = norm(fn)
        claims.setdefault(norm(fn), []).append(row)
        if d is not None:                                               # check 7: the mode of the function, where the table gives it
            m = blk["modes"].get(norm(fn))
            if m is None:
                row["direction_check"] = "NOT CHECKED"
                row["_dir"] = f"direction not checked: the table gives no sourced mode for {fn} (`function_modes`), outside the checked scope"
            elif d in m or (d in ("in", "out") and "both" in m):
                row["direction_check"] = "PASS"
                row["_dir"] = f"direction {d} fits the mode of {fn} in the table ({' or '.join(sorted(m))})"
            else:
                row["direction_check"] = "FAIL"
                shown = " or ".join(f'"{x}"' for x in sorted(m))
                say("FAIL", f"{fn} is {shown} in the table's function modes ({blk['modes_source']}); the use says \"{d}\"")
        if tp is None:
            say("UNKNOWN", f"the datasheet table has no entry for this pin: cannot say whether it offers {fn}")
            continue
        if tp["functions"] is None:
            say("UNKNOWN", f"no function list for this pin in the datasheet table (`functions`): cannot say whether it offers {fn}")
        elif norm(fn) not in offered(tp):
            where = [f"pin {n} ({q['name']})" for n, q in sorted(blk["pins"].items(), key=lambda x: _nat(x[0])) if norm(fn) in offered(q)]
            say("FAIL", f"the datasheet table does not offer {fn} on this pin (it offers: "
                        f"{', '.join(dict.fromkeys([tp['name']] + tp['alias'] + tp['functions']))}); "
                        + (f"{fn} is offered on {', '.join(where)}" if where else f"no pin of the block offers {fn}"))
        if d in ("out", "both", "open drain") and tp["input_only"]:
            say("FAIL", f"an input-only pin cannot be used as \"{d}\"")
        if d in ("out", "both") and tp["open_drain_only"]:
            say("FAIL", f"an open-drain-only pin cannot drive high: the push-pull use \"{d}\" needs another pin (a line that is "
                        f"only pulled low: direction = \"open drain\", with a pull-up)")
        if d == "analog" and not tp["analog"]:
            say("FAIL", "an analogue use, but the datasheet table gives this pin no analogue function (`analog = true` is not set)")
        for o in own:
            home = o["function"] or (tp["name"] if tp["functions"] == [] else "")     # a one-function pin: its name is that job
            if home and norm(home) == norm(fn):
                say("PASS", f"its own job: {o['what']}"
                    + ("; whether that level is held is not checked here" if o["key"] == "sampled_at_reset" else ""))
            elif row["reason"]:
                say("ACCEPTED", f"{o['what']}, used for {fn}: accepted with the written reason: {row['reason']}")
            else:
                say("FAIL", f"{o['what']}, but used for {fn}: no written reason (reason = \"...\" in its use entry: what makes "
                            f"this safe)")
        if not row["msgs"]:
            say("PASS", f"{fn} is offered on this pin")
    for key, claimed in claims.items():
        if len(claimed) > 1 and key not in blk["several"] and names_on.get(key, 0) < 2:
            for row in claimed:
                also = ", ".join(f"pin {r['pin']}" for r in claimed if r is not row)
                row["msgs"].append(("FAIL", f"{row['function']} is also claimed by {also}: one function, one pin (a function that "
                                            f"the datasheet allows on several pins at once is listed in `on_several_pins` of its block)"))
    shared_resources(rows, blk)
    for row in rows:
        msgs = sorted(row.pop("msgs"), key=lambda m: -RANK[m[0]])
        row["result"] = msgs[0][0]
        texts = list(dict.fromkeys(t for _, t in msgs))
        if row["direction_check"] in ("PASS", "NOT CHECKED"):
            texts.append(row["_dir"])
        row["text"] = "; ".join(texts)
        del row["_fn"], row["_dir"]
    return rows


def shared_resources(rows: list, blk: dict) -> None:
    """Check 8, only as the block declares it: one setting per shared resource; one pin set per peripheral."""
    used = [r for r in rows if r["_fn"]]

    def others(r, group):
        return ", ".join(f"pin {o['pin']} ({o['function']})" for o in group if o is not r)

    groups = {}
    for r in used:
        if r["_fn"] in blk["shared"]:
            groups.setdefault(blk["shared"][r["_fn"]], []).append(r)
    for res, group in groups.items():
        if len(group) < 2:
            continue
        if any(not r["setting"] for r in group):
            for r in group:
                if not r["setting"]:
                    r["msgs"].append(("UNKNOWN", f"{r['function']} shares {res} with {others(r, group)}: write setting = \"<what this "
                                                 f"use needs from {res}, for example its frequency>\" in each of their use entries"))
        elif len({norm(r["setting"]) for r in group}) > 1:
            listing = "; ".join(f"pin {r['pin']} ({r['function']}): \"{r['setting']}\"" for r in group)
            for r in group:
                r["msgs"].append(("FAIL", f"{res} is one resource of the chip, shared by {listing}: the settings differ, and one "
                                          f"{res} has one setting"))
        else:
            for r in group:
                r["msgs"].append(("PASS", f"shares {res} with {others(r, group)} at the same setting ({r['setting']})"))
    for per, sets in blk["sets"].items():
        names = {f for s in sets.values() for _, f in s}
        desc = "; ".join(f"{n}: pins {', '.join(sorted({p for p, _ in s}, key=_nat))}" for n, s in sets.items())
        placed, common = [], None
        for r in (r for r in used if r["_fn"] in names):
            inside = {n for n, s in sets.items() if (r["pin"], r["_fn"]) in s}
            if not inside:
                r["msgs"].append(("UNKNOWN", f"the pin sets of {per} in the table ({desc}) do not list {r['function']} on this pin"))
                continue
            placed.append((r, inside))
            common = inside if common is None else common & inside
        if len(placed) < 2:
            continue
        if common:
            for r, _ in placed:
                r["msgs"].append(("PASS", f"{per} takes all its pins from one pin set: here the pin set {' or '.join(sorted(common))}"))
        else:
            mix = ", ".join(f"pin {r['pin']} {r['function']} ({' or '.join(sorted(inside))})" for r, inside in placed)
            for r, _ in placed:
                r["msgs"].append(("FAIL", f"{per} takes all its pins from one pin set ({desc}); here its uses mix the sets: {mix}"))


# ---- inputs --------------------------------------------------------------------------------------------------------------
def inputs(job, a) -> dict:
    """Where the three files are, and where each path comes from: {key: (path or None, shown, origin)}."""
    cfg = job.cfg("pin_functions")
    files = kicad_io.project_files(job.project, job.settings) if job.project else None
    defaults = {"netlist": ("out", "netlist.net"), "table": ("src", "datasheet_pins.toml"), "use": ("src", "pin_use.toml")}
    out = {}
    for key, (folder, name) in defaults.items():
        given = getattr(a, key, None)
        if given:
            out[key] = (os.path.abspath(given), os.path.basename(given), "command line")
        elif files and cfg.get(key):
            if not isinstance(cfg[key], str):
                raise KicadIOError(f"board.toml [pin_functions] {key} must be a path")
            out[key] = (job.path(cfg[key]), cfg[key].replace("\\", "/"), "board.toml")
        elif files:
            out[key] = (os.path.join(files[folder], name), f"{os.path.basename(files[folder])}/{name}", "default")
        else:
            out[key] = (None, "not given", "-")
    return out


def mpn_fields(cli, settings: dict) -> tuple[list, str]:
    def section(name):
        v = settings.get(name, {})
        return v if isinstance(v, dict) else {}
    for value, origin in ((cli, "command line"), (section("pin_functions").get("mpn_field"), "board.toml"),
                          (section("ratings").get("mpn_field"), "board.toml [ratings]"), (section("bom").get("mpn_field"), "board.toml [bom]")):
        if value:
            return ([value] if isinstance(value, str) else [str(v) for v in value]), origin
    return list(ratings_check.MPN_FIELDS), "default"


def not_applicable(project: str) -> str:
    """For check_all.py (a row's `applies`): why this check does not apply to a board folder, or "" when it
    applies, and also "" when that cannot be said (no table or no netlist, a file that cannot be read, a chip that the
    table does not classify): the script itself then runs and gives its own result."""
    try:
        settings = kicad_io.load_settings(project)
        files = kicad_io.project_files(project, settings)
        cfg = settings.get("pin_functions", {}) if isinstance(settings.get("pin_functions", {}), dict) else {}

        def path(key, folder, name):
            return os.path.normpath(os.path.join(project, cfg[key])) if isinstance(cfg.get(key), str) else os.path.join(files[folder], name)

        p_tab = path("table", "src", "datasheet_pins.toml")
        if not os.path.isfile(p_tab):
            return ""
        tab = Table(p_tab)
        if any(tab.marked(name) for name in tab.parts):
            return ""
        nl = kicad_io.read_netlist(path("netlist", "out", "netlist.net"))
        rule, _ = chip_rule(cfg)
        _, errors, _, checked, unclassified = classify(nl, tab, mpn_fields(None, settings)[0], [], rule)
        if checked or errors or unclassified:
            return ""
        return (f"no programmable part declared in {os.path.basename(p_tab)} (every chip's block says programmable = false); "
                f"{chips_text(nl, rule)}")
    except (KicadIOError, OSError):
        return ""


def skeleton(nl, sym: dict, checked: list, tab: Table) -> list:
    """Lines of a use table to fill in: every connected pin of every checked part that needs an entry."""
    lines = ["# What this design uses each pin of each programmable part for. Written by the designer, from the design.",
             "# function: one of the pin's functions in the datasheet table (a plain port pin: the pin's name).",
             "# direction: in, out, both, open drain, analog. purpose: what it does on this board (free text).",
             "# setting: only for a function of a shared resource that the table declares (`resources`): what this use needs",
             "#   from it, for example a timer's frequency, in the same words on every pin of that resource."]
    for ref, name, _ in checked:
        lines += ["", f"[{ref}]"]
        for num in sorted(nl.pins_of(ref), key=_nat):
            net = nl.pins[(ref, num)][0]
            tp = tab.parts[name]["pins"].get(num)
            if len(nl.nets[net]) > 1 and not (tp and tp["functions"] == []):
                shown = (tp["name"] if tp and tp["name"] else sym[(ref, num)]) or "?"
                lines.append(f"{json.dumps(num):<4} = {{function = \"\", direction = \"\"}}   # {shown}, net {net}")
    return lines


def scope_lines(data: dict, tab: Table) -> tuple[str, list]:
    """The scope of this run: (the words for the result line, the lines for "Not checked")."""
    c, lines, declared, open_dir = data["counts"], [], [], []
    for p in data["parts"]:
        nums = [r["pin"] for r in p["pins"] if r["direction_check"] == "NOT CHECKED"]
        if nums:
            open_dir.append(f"{p['ref']} pin{'s' if len(nums) > 1 else ''} {', '.join(nums)}")
    if open_dir:
        lines.append(f"- Direction of the function used, not checked (no sourced mode in `function_modes`): {'; '.join(open_dir)}.")
    for p in data["parts"]:
        blk = tab.parts[p["block"]] if p["block"] else {"shared": {}, "sets": {}}
        res = sorted(set(blk["shared"].values()))
        if res or blk["sets"]:
            declared += res + sorted(blk["sets"])
            lines.append(f"- Shared resources of {p['ref']}, checked only as the table declares them: "
                         + "; ".join(x for x in (f"resources {', '.join(res)}" if res else "",
                                                 f"pin sets {', '.join(sorted(blk['sets']))}" if blk["sets"] else "") if x) + ".")
        else:
            lines.append(f"- Shared resources of {p['ref']}: none declared in the datasheet table (`resources`, `pin_sets`): two uses "
                         f"of one timer or of two pin sets of one peripheral are not checked; nothing is inferred.")
    used = c["direction_checked"] + c["direction_not_checked"]
    words = (f"direction not checked on {c['direction_not_checked']} used pin(s)" if c["direction_not_checked"]
             else f"direction checked on all {used} used pin(s)" if used else "no used pin to compare")
    words += "; " + (f"shared resources as declared: {', '.join(declared)}" if declared else "no shared resource declared")
    return words, lines


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Pin functions: the use of every pin of a programmable part against the hand-typed datasheet table.",
                              board=False, epilog="Exit codes: 0 pass or not applicable, 1 a pin is FAIL or UNKNOWN or a chip is "
                                                  "not classified, 2 could not run.")
    ap.add_argument("netlist", nargs="?", help="the exported netlist (kicadsexpr); not needed with --project")
    ap.add_argument("table", nargs="?", help="the datasheet table (TOML); not needed with --project")
    ap.add_argument("use", nargs="?", help="the use table (TOML); not needed with --project")
    ap.add_argument("--ref", action="append", default=[], help="check this part too, whatever its block says (repeatable)")
    ap.add_argument("--mpn-field", action="append", help="symbol field that holds the maker part number (repeatable)")
    ap.add_argument("--chip-prefix", action="append", help="reference prefix of a chip that the table must classify (repeatable; "
                                                           "default U and IC)")
    ap.add_argument("--chip-min-pins", type=int, help=f"a part with this many pins or more counts as a chip (default {CHIP_MIN_PINS})")
    a = ap.parse_args(argv)
    job = pcb_common.resolve(a, need_board=False)
    rule, rule_from = chip_rule(job.cfg("pin_functions"), a.chip_prefix, a.chip_min_pins)
    src = inputs(job, a)
    p_net, p_tab, p_use = src["netlist"][0], src["table"][0], src["use"][0]
    if not p_net:
        raise KicadIOError("give --project <board folder>, or NETLIST.net TABLE.toml USE.toml with --out <folder>")
    if not os.path.isfile(p_net):
        raise KicadIOError(f"no netlist {p_net}: export it first (scripts/schematic/export.py)")
    nl = kicad_io.read_netlist(p_net)
    sym = ratings_check.symbol_pin_names(p_net, nl)     # KiCad 10 writes the pin number behind the name in the nets
    missing = [r for r in a.ref if r not in nl.parts]
    if missing:
        raise KicadIOError(f"--ref {', '.join(missing)}: the netlist has no such part")
    if not p_tab or not os.path.isfile(p_tab):
        raise KicadIOError(("no datasheet table was given" if not p_tab else f"no datasheet table {p_tab}")
                           + f": it cannot be said which part is programmable or what its pins can do. Type the table from the "
                             f"datasheets ({TEMPLATE}), with programmable = true in the block of every microcontroller or "
                             f"programmable logic part and the `functions` of each of its pins, and programmable = false in the "
                             f"block of every other chip. To look at: {chips_text(nl, rule)}")
    tab = Table(p_tab)
    fields, fields_from = mpn_fields(a.mpn_field, job.settings)
    block, errors, notes, checked, unclassified = classify(nl, tab, fields, a.ref, rule)
    open_items = [open_text(nl, r, n, os.path.basename(p_tab)) for r, n in unclassified]

    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    head = ["# Pin functions of the programmable parts: the use table against the datasheet table", "",
            f"Script `pin_function_check.py`, run {when}; settings: {job.source_note}.",
            f"Netlist `{os.path.basename(p_net)}`, SHA-256 `{kicad_io.sha256(p_net)}` ({nl.tool or 'tool not named'}); "
            f"datasheet table `{os.path.basename(p_tab)}`, SHA-256 `{kicad_io.sha256(p_tab)}`"
            + (f"; use table `{os.path.basename(p_use)}`, SHA-256 `{kicad_io.sha256(p_use)}`." if p_use and os.path.isfile(p_use)
               else "; no use table."), "",
            f"**What a PASS covers:** {COVERS}. It does not prove that the firmware's whole pin, clock and peripheral configuration "
            f"can be built: {OUTSIDE} are outside the checked scope and belong to the joint peripheral-allocation review "
            f"(`references/reviews.md`).", ""]
    setup = ["| Setting | Value | From |", "|---|---|---|"] + \
            [f"| {label} | {src[k][1]} | {src[k][2]} |"
             for k, label in (("netlist", "netlist"), ("table", "datasheet table"), ("use", "use table"))] + \
            [f"| maker part number field | {', '.join(fields)} | {fields_from} |",
             f"| what counts as a chip (its block must say programmable = true or false) | {rule_text(rule)} | {rule_from} |",
             f"| parts named with `--ref` | {', '.join(a.ref) or '-'} | {'command line' if a.ref else '-'} |", ""]
    data = {"script": "pin_function_check.py", "netlist": os.path.basename(p_net), "netlist_sha256": kicad_io.sha256(p_net),
            "table": os.path.basename(p_tab), "table_sha256": kicad_io.sha256(p_tab),
            "use": os.path.basename(p_use) if p_use and os.path.isfile(p_use) else None,
            "scope": {"covers": COVERS, "outside": OUTSIDE + ": the joint peripheral-allocation review"},
            "counts": {"parts_checked": len(checked), "pins": 0, "pass": 0, "accepted": 0, "fail": 0, "unknown": 0,
                       "direction_checked": 0, "direction_not_checked": 0, "chips_not_classified": len(unclassified)},
            "parts": [], "fail": [], "unknown": [], "accepted": [], "notes": notes, "chips": chips(nl, rule),
            "chip_rule": {"prefixes": list(rule[0]), "min_pins": rule[1], "from": rule_from}}
    unclassified_body = (["## Chips that the datasheet table does not classify (UNKNOWN)", ""] + [f"- UNKNOWN: {x}" for x in open_items]
                         + [""]) if open_items else []

    def finish(result: str, summary: str, body: list, code: int) -> int:
        data["result"], data["summary"] = result, summary
        md = head + [f"**Result: {result}**: {summary}", ""] + setup + body
        p_md, _ = pcb_common.write_result(job.out, "pin_function_check", md, data)
        print(f"{result}: {summary} -> {p_md}")
        return code

    # ---- nothing to check, and every chip classified
    if not checked and not errors and not unclassified:
        summary = (f"no programmable part declared in {os.path.basename(p_tab)} (no block says programmable = true, every chip's "
                   f"block says programmable = false, and no part was named with --ref); {chips_text(nl, rule)}")
        return finish("NOT APPLICABLE", summary,
                      ["## Why", "", "Every chip of the netlist has a block that says programmable = false, so there is no pin "
                       "function to compare. If one of the chips below runs firmware or a configuration (a microcontroller, "
                       "programmable logic, a radio chip with its own program), write `programmable = true` in its block and type "
                       f"the `functions` of its pins ({TEMPLATE}); then this check applies.", ""]
                      + [f"- {c}" for c in chips(nl, rule)] + ["", *(f"- NOTE: {n}" for n in notes)], 0)

    # ---- check 6: no function data, or no use table: could not run
    todo = []
    for ref, name, why in checked:
        part = nl.parts[ref]
        if name is None:
            todo.append(f"{ref} ({part.value or 'no value'}, {len(nl.pins_of(ref))} pins) has no block in the datasheet table: type its "
                        f"block ({TEMPLATE}) from the maker's datasheet of the exact part number, with the `functions` of each pin: "
                        f"{EXAMPLE}")
        elif not tab.parts[name]["has_functions"]:
            ds = tab.parts[name]["datasheet"]
            todo.append(f"{ref} (block \"{name}\", checked because: {why}): no pin of the block carries `functions`. Type, for every "
                        f"pin, what the maker's table of pin functions lists for it (\"Pin definitions\", \"Alternate functions\"; "
                        + (f"the block names its datasheet: {ds}" if ds else "the block names no datasheet: add datasheet = \"...\"")
                        + f"), for example {EXAMPLE}; a pin with one fixed function (supply, ground, reset): functions = []. "
                          f"A part whose pins cannot be given another function (a module with its maker's firmware): programmable = false")
    if todo:
        for t in todo:
            print(f"CANNOT RUN: {t}")
        for x in open_items:
            print(f"UNKNOWN  {x}")
        return finish("CANNOT RUN", f"{len(todo)} part(s) without function data; nothing was compared",
                      ["## What to type before this check can run", ""] + [f"- {t}" for t in todo] + [""] + unclassified_body, 2)
    if checked and (not p_use or not os.path.isfile(p_use)):
        where = "no use table was given" if not p_use else f"no use table {src['use'][1]}"
        print(f"CANNOT RUN: {where}: write src/pin_use.toml, one line per connected pin of "
              f"{', '.join(r for r, _, _ in checked)} (the skeleton is in the report)")
        for x in open_items:
            print(f"UNKNOWN  {x}")
        return finish("CANNOT RUN", f"{where}; nothing was compared",
                      ["## The use table to write (src/pin_use.toml)", "",
                       "Fill in the function wanted (one of the pin's `functions` in the datasheet table, or the pin's name for a "
                       "plain port pin) and the direction of every line; delete nothing. A pin that is not connected has no line.", "",
                       "```toml"] + skeleton(nl, sym, checked, tab) + ["```", ""] + unclassified_body, 2)

    # ---- the comparison
    use, use_errors = read_use(p_use) if checked else ({}, [])
    errors += use_errors
    refs_checked = {r for r, _, _ in checked}
    for ref in use:
        if ref not in refs_checked:
            errors.append(f"use table: [{ref}] is " + ("not a part of the netlist" if ref not in nl.parts else
                          "not a checked part: write programmable = true in its block of the datasheet table, or remove the table"))
    for ref, name, why in checked:
        blk = tab.parts[name]
        errors += [f"table: {e}" for e in blk["errors"]]
        rows = check_part(nl, sym, ref, blk, use.get(ref, {}))
        data["parts"].append({"ref": ref, "block": name, "value": nl.parts[ref].value, "datasheet": blk["datasheet"],
                              "checked_because": why, "pins": rows})
        for r in rows:
            who = f"{ref} pin {r['pin']}" + (f" ({r['name']})" if r["name"] else "")
            key = {"PASS": "pass", "ACCEPTED": "accepted", "FAIL": "fail", "UNKNOWN": "unknown"}[r["result"]]
            data["counts"][key] += 1
            data["counts"]["pins"] += 1
            if r["direction_check"]:
                data["counts"]["direction_not_checked" if r["direction_check"] == "NOT CHECKED" else "direction_checked"] += 1
            if key != "pass":
                data[key].append(f"{who}: {r['text']}")
            if r["reason"] and "accepted with the written reason" not in r["text"]:
                notes.append(f"{who}: its use entry carries a reason (\"{r['reason']}\"), but nothing on this pin needs one")
            if r["setting"] and norm(r["function"]) not in blk["shared"]:
                notes.append(f"{who}: its use entry carries setting = \"{r['setting']}\", but the datasheet table declares no shared "
                             f"resource for {r['function']} (`resources`): it was compared with nothing")
    data["fail"] = errors + data["fail"]
    data["unknown"] = open_items + data["unknown"]
    c = data["counts"]
    n_fail = len(data["fail"])
    result = pcb_common.verdict(n_fail, c["unknown"] + len(open_items))
    labels = ", ".join(chip_label(nl, r) for r, _ in unclassified[:6]) + (" ..." if len(unclassified) > 6 else "")
    scope_words, scope_body = scope_lines(data, tab)
    if checked:
        summary = (f"{c['parts_checked']} part(s) checked, {c['pins']} pins: {c['pass']} PASS, {c['accepted']} accepted, {c['fail']} FAIL, "
                   f"{c['unknown']} UNKNOWN" + (f"; {len(errors)} mistake(s) in the tables" if errors else "")
                   + (f"; {len(unclassified)} chip(s) not classified (UNKNOWN): {labels}" if unclassified else "")
                   + f"; per-pin table consistency only ({scope_words}), not the whole pin, clock and peripheral configuration "
                     f"(joint peripheral-allocation review)")
    else:
        summary = (f"no part checked; {len(unclassified)} chip(s) of the netlist not classified in {os.path.basename(p_tab)} (UNKNOWN): "
                   f"{labels}: each needs a block that says programmable = true or programmable = false"
                   + (f"; {len(errors)} mistake(s) in the tables" if errors else ""))
    body = []
    for title, items, tag in (("FAIL", data["fail"], "FAIL"), ("UNKNOWN (not a pass)", data["unknown"], "UNKNOWN"),
                              ("Accepted, each with its written reason", data["accepted"], "ACCEPTED"), ("Notes (not counted)", notes, "NOTE")):
        body += [f"## {title}", ""] + ([f"- {tag}: {x}" for x in items] or ["None."]) + [""]
    body += ["## Per part", ""]
    for p in data["parts"]:
        body += [f"### {p['ref']}: {p['block']}", "",
                 f"Value on the schematic: {p['value'] or '-'}. Checked because: {p['checked_because']}. Datasheet: "
                 f"{p['datasheet'] or 'NOT NAMED in the table'}.", "",
                 "The first five columns are those of the pin map of the firmware hand-over (`FIRMWARE_HANDOVER.md`, section 2); "
                 "\"Function wanted\" is its \"Peripheral to use\".", "",
                 "| Pin | Pin name (datasheet) | Net | Function on this board | Direction | Function wanted | Result | Why |",
                 "|---|---|---|---|---|---|---|---|"]
        for r in p["pins"]:
            net = "(no such pin)" if r["net"] is None else r["net"] if r["connected"] else "not connected"
            body.append(f"| {r['pin']} | {_cell(r['name'])} | {_cell(net)} | {_cell(r['purpose'])} | {_cell(r['direction'])} | "
                        f"{_cell(r['function'])} | {r['result']} | {_cell(r['text'])} |")
        body.append("")
    body += ["## Not checked", "",
             f"Outside the checked scope, for the joint peripheral-allocation review (`references/reviews.md`): {OUTSIDE}; whether "
             "the firmware's whole pin, clock and peripheral configuration can be built. Also not checked: whether the two tables "
             "are typed correctly (the schematic reviewers compare them with the datasheet and with the design); whether the level "
             "that a reset-sampled pin needs is really held (ratings_check.py, default levels); the state of a pin in reset and "
             "while the chip is programmed; voltages (ratings_check.py); drive strength, speed, 5 V tolerance; whether the table is "
             "of the exact package that is fitted; any part that the table does not mark as programmable.", ""] + scope_body + [""]
    for tag, items in (("FAIL", data["fail"]), ("UNKNOWN", data["unknown"]), ("ACCEPTED", data["accepted"])):
        for x in items[:MAX_LISTED]:
            print(f"{tag:8} {x}")
    return finish(result, summary, body, 0 if result == "PASS" else 1)


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
