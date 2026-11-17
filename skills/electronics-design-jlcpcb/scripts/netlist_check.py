"""Netlist against intent: does the exported netlist join exactly the pins that a person said must be joined?

What it checks
    The netlist that KiCad exports from the schematic, against a hand-written intent file:
      1. every group of pins in the intent file is exactly ONE net: no pin of the group on another net (an open),
         no pin missing from the netlist, no pin on that net that the group does not list;
      2. no two groups share a net (a short between two intended nets);
      3. every pin listed as "must stay unconnected" is alone on its net;
      4. every pin of every part in the netlist is in a group or in the unconnected list (nothing unaccounted),
         and every part has at least one listed pin, unless its reference is under [options] ignore;
      5. every part that goes on the board has a footprint.
    It also writes, per IC, transistor, connector and polarised part, a table of pin, pin name (as the symbol
    has it), net and what else is on that net, so that a person can hold it against the datasheet pin table.

Why it exists
    Two different nodes on two sheets once carried the same short net name and silently became one net. The
    rule check passed. The first "netlist check" passed too, because it compared the netlist with the
    generator's own source: the mistake with itself. So the
    comparison must be against an INDEPENDENT statement, written from the circuit description and the datasheet
    pin tables, and the check must prove that it can fail (the self-test).

It works on a netlist exported from any KiCad schematic, whoever drew it (hierarchical sheets, labels, supply
symbols, parts with several units, no part-number fields):
    kicad-cli sch export netlist --format kicadsexpr -o netlist.net <root>.kicad_sch
(scripts/schematic/export.py does that.)

The intent file (TOML, written by hand; template: templates/EXPECTED_CONNECTIVITY.md)
    # Pin functions from the datasheets go here as comments, one line per IC, with the datasheet table named:
    # U2: 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT    (maker's datasheet, table "Pin functions")

    [nets]                          # group name -> the pins that must be exactly one net
    "5 V input"  = ["J1.1", "C1.1", "U2.1", "U2.3", "R1.1"]
    "3.3 V rail" = ["U2.5", "C2.1", "R3.1"]
    "ground"     = ["J1.4", "C1.2", "C2.2", "U2.2"]

    [no_connect]                    # pins that must stay unconnected
    pins = ["U2.4"]

    [options]                       # references left out of the "every pin accounted for" rule
    ignore = ["H1", "H2", "FID1"]   # mounting holes, fiducials ("H*" also works)

    A pin is written reference, dot, pin number: "U1.3", "J1.A5". Group names only describe; the check compares
    which pins are joined, never net names. Every pin appears once. Never generate this file from the schematic.

Usage
    python -I scripts/netlist_check.py NETLIST.net INTENT.toml --out FOLDER      the check
    python -I scripts/netlist_check.py --project hardware/<board>                the same from the board folder
        ... --self-test             after the check, plant three defects in copies of the netlist (two nets
                                    merged; one net split; a no-connect pin connected) and require that each
                                    copy FAILS with a new mismatch. --keep FOLDER keeps the three copies.
    python -I scripts/netlist_check.py --names NETLIST.net --out FOLDER [--schematic ROOT.kicad_sch] [--declared A,B]
                                    for a design that came from elsewhere: list the net names that span more
                                    than one sheet (one name, ONE net: is that meant on every sheet?) and the
                                    names used on several sheets for SEPARATE nets (were they meant to be one?)
    python -I scripts/netlist_check.py --pins NETLIST.net --out FOLDER
                                    only the pin tables (a listing for a datasheet review, not a check)
    python -I scripts/netlist_check.py --screens NETLIST.net --out FOLDER [--waivers FILE] [--ground A,B]
    python -I scripts/netlist_check.py --screens --project hardware/<board>
                                    four screens that need NO intent file, for a design brought in from elsewhere
                                    (see below); they give LEADS for the reviewer, not verdicts

The screens (--screens)
    A design brought in by a user has no intent file, so nothing mechanical looked at its connections before the
    reviewers did. Four cheap screens find the usual slips:
      S1  a two-pin part with both pins on one net: it is shorted out and does nothing (a net tie, and a jumper
          drawn bridged, are not reported);
      S2  a supply pin with no path for direct current: its net, and every net reached from it through two-pin
          parts that pass direct current (never into a ground net), hold nothing but capacitors, supply inputs and
          inputs (a supply fed through a ferrite or a resistor from a real source is not reported);
      S3  a rail fed only through an open or unfitted link: with every part fitted and every link closed something
          feeds it, but with the parts marked not fitted left out and the jumpers drawn open left open, nothing does;
      S4  a net with one pin only that is not marked as not connected (a pin left floating, or a label with no
          partner).
    Each lead names the parts, pins and nets, says why it may be a fault and what would make it harmless. What the
    screens cannot tell (a jumper whose state is not drawn, supply pins that the library does not type as power
    input, no ground net recognised, jumper blocks with more pins) is listed as NOT CHECKED, never as a pass. How
    supply pins, capacitors, parts not fitted, jumpers and their states, links and sources are recognised is
    written into every report (RELIES_ON below).
    Waivers (--waivers FILE, TOML): [[waive]] finding = "S4:J3.*" (screen, colon, the part, pin or net; * and ?
    allowed), reason = "..." (required: a waiver without a reason is not applied). A waived lead is still listed,
    as WAIVED with its reason; a waiver that matches nothing is listed as stale.

Results (with --project: in the results folder, <board>/out/ or [project] out_dir)
    connectivity_report.md / .json      the check (and the self-test, when asked)
    net_names.md / .json                --names
    pin_table.md / .json                --pins
    netlist_screens.md / .json          --screens

board.toml keys (only with --project; all optional; paths relative to the board folder)
    [project] kicad_dir, out_dir    see kicad_io.py; the results folder is out_dir (default "out")
    [netlist_check] netlist         default "netlist.net" in the results folder
    [netlist_check] intent          default "src/expected_connectivity.toml"
    [netlist_check] screen_waivers  --screens: the waiver file; default "src/netlist_screens_waivers.toml" when it exists
    [netlist_check] screen_ground   --screens: net-name patterns of the ground nets; default GND, *GND*, VSS, VSS*,
                                    *VSS, 0V, EARTH*, *EARTH, CHASSIS*, GROUND* (only names the designer gave)
    [schematic] global_nets         net names declared to span sheets (used by --names)

Exit codes
    0  PASS (with --self-test: the check passes AND every planted defect was caught; --names: nothing to review;
       --pins: the listing was written; --screens: no lead that is not waived; items NOT CHECKED may remain, and
       they are listed: they are not a pass)
    1  FAIL: mismatches are listed (with --self-test also: a planted defect was not caught; --names: names to review;
       --screens: leads to review)
    2  could not run: a file is missing or unreadable, the intent file is not valid TOML, no --out; with --self-test
       also: no defect could be planted; --screens: the netlist or the waiver file cannot be read
    The third defect of the self-test needs a no-connect pin in the intent file; a design without one is tested
    with the other two, and the report says so.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import fnmatch
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import sexp  # noqa: E402
from kicad_io import KicadIOError, Netlist, is_named, leaf  # noqa: E402

Pin = tuple  # (reference, pin number)


def _nat(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _pk(p: Pin) -> tuple:
    return (_nat(p[0]), _nat(p[1]))


def _pt(p: Pin) -> str:
    return f"{p[0]}.{p[1]}"


def _pins(ps) -> str:
    return ", ".join(_pt(p) for p in sorted(ps, key=_pk))


# ---- the intent file -------------------------------------------------------------------------------------------------
class Intent:
    def __init__(self, path: str):
        self.path = path
        self.nets: dict[str, list[Pin]] = {}
        self.no_connect: list[Pin] = []
        self.ignore: list[str] = []
        self.errors: list[str] = []         # mistakes inside the file (a pin listed twice ...): they fail the check
        try:
            import tomllib
        except ImportError:
            raise KicadIOError("reading the intent file needs Python 3.11 or newer (tomllib)") from None
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise KicadIOError(f"{path}: not valid TOML: {e}") from None
        for key in data:
            if key not in ("nets", "no_connect", "options"):
                self.errors.append(f"unknown section [{key}] (known: [nets], [no_connect], [options])")
        nets = data.get("nets", {})
        if not isinstance(nets, dict):
            raise KicadIOError(f"{path}: [nets] must be a table of group name = [pins]")
        seen: dict[Pin, str] = {}

        def pin(text, where: str) -> Pin | None:
            if not isinstance(text, str) or "." not in text or text.startswith(".") or text.endswith("."):
                self.errors.append(f"{where}: {text!r} is not a pin (write reference.pin, for example \"U1.3\")")
                return None
            ref, num = text.strip().split(".", 1)
            p = (ref.strip(), num.strip())
            if p in seen:
                self.errors.append(f"pin {_pt(p)} is listed twice: in {seen[p]} and in {where}")
                return None
            seen[p] = where
            return p

        for name, members in nets.items():
            if not isinstance(members, list):
                raise KicadIOError(f"{path}: group '{name}' must be a list of pins, for example [\"U1.3\", \"R1.1\"]")
            got = [q for q in (pin(m, f"group '{name}'") for m in members) if q is not None]
            self.nets[name] = got
            if len(members) < 2:
                self.errors.append(f"group '{name}' has {len(members)} pin(s): a net joins at least two; a pin that "
                                   f"must stay open belongs under [no_connect]")
        nc = data.get("no_connect", {})
        if not isinstance(nc, dict) or not isinstance(nc.get("pins", []), list):
            raise KicadIOError(f"{path}: [no_connect] must hold pins = [\"U1.7\", ...]")
        for key in nc:
            if key != "pins":
                self.errors.append(f"[no_connect] has an unknown key '{key}' (only: pins)")
        self.no_connect = [q for q in (pin(m, "[no_connect]") for m in nc.get("pins", [])) if q is not None]
        opt = data.get("options", {})
        if not isinstance(opt, dict) or not isinstance(opt.get("ignore", []), list):
            raise KicadIOError(f"{path}: [options] must hold ignore = [\"H1\", ...]")
        for key in opt:
            if key != "ignore":
                self.errors.append(f"[options] has an unknown key '{key}' (only: ignore)")
        self.ignore = [str(x) for x in opt.get("ignore", [])]

    def ignored(self, ref: str) -> bool:
        return any(fnmatch.fnmatchcase(ref, pat) for pat in self.ignore)


# ---- the check -------------------------------------------------------------------------------------------------------
def _net_label(nl: Netlist, name: str) -> str:
    n = len(nl.nets.get(name, ()))
    return f"{name} ({n} pin{'s' if n != 1 else ''})"


def check(nl: Netlist, intent: Intent) -> dict:
    """Compare; returns {"mismatches": [{"kind", "text"}], "groups": [...], "no_connect": [...], "counts": {...}}."""
    mm: list[dict] = []

    def add(kind: str, text: str) -> None:
        mm.append({"kind": kind, "text": text})

    for e in intent.errors:
        add("intent file", e)
    group_of: dict[Pin, str] = {p: g for g, ps in intent.nets.items() for p in ps}
    nc_set = set(intent.no_connect)

    # 1. every group is one net
    groups = []
    net_groups: dict[str, list[str]] = {}
    for g, ps in intent.nets.items():
        missing = [p for p in ps if p not in nl.pins]
        there = [p for p in ps if p in nl.pins]
        nets = sorted({nl.pins[p][0] for p in there})
        ok = not missing and len(nets) == 1
        for p in missing:
            why = "that reference is not in the netlist" if p[0] not in nl.parts else \
                f"{p[0]} has the pins {', '.join(nl.pins_of(p[0])) or '(none)'}"
            add("pin not in the netlist", f"group '{g}' lists {_pt(p)}: {why}")
        if len(nets) > 1:
            parts = "; ".join(f"{_pins(p for p in there if nl.pins[p][0] == n)} on {n}" for n in nets)
            add("open", f"group '{g}' is split over {len(nets)} nets: {parts}")
        for n in nets:
            net_groups.setdefault(n, []).append(g)
        groups.append({"group": g, "pins": len(ps), "nets": nets, "ok": ok})

    # 2. no two groups on one net; nothing else on a group's net
    for n, gs in sorted(net_groups.items()):
        if len(gs) > 1:
            add("short", f"groups {', '.join(repr(g) for g in gs)} are ONE net ({n}): a short between intended nets")
            for row in groups:
                if row["group"] in gs:
                    row["ok"] = False
        extra = [p for p in nl.nets[n] if p not in group_of]
        for p in sorted(extra, key=_pk):
            if p in nc_set:
                continue                                    # reported once, under 3
            if intent.ignored(p[0]):
                continue
            add("pin not in the intent", f"{_pt(p)} is on net {n} (group {', '.join(repr(g) for g in gs)}), "
                                          f"but no group lists it")
            for row in groups:
                if row["group"] in gs:
                    row["ok"] = False

    # 3. pins that must stay unconnected
    ncs = []
    for p in intent.no_connect:
        if p not in nl.pins:
            add("pin not in the netlist", f"[no_connect] lists {_pt(p)}: " + (
                "that reference is not in the netlist" if p[0] not in nl.parts else
                f"{p[0]} has the pins {', '.join(nl.pins_of(p[0])) or '(none)'}"))
            ncs.append({"pin": _pt(p), "net": "", "ok": False})
            continue
        n = nl.pins[p][0]
        others = [q for q in nl.nets[n] if q != p]
        if others:
            add("no-connect pin connected", f"{_pt(p)} must stay unconnected, but it is on net {n} with {_pins(others)}")
        ncs.append({"pin": _pt(p), "net": n, "ok": not others})

    # 4. every pin of every part is accounted for
    listed = set(group_of) | nc_set
    loose: dict[str, list[Pin]] = {}
    for p in nl.pins:
        if p not in listed and not intent.ignored(p[0]) and len(net_groups.get(nl.pins[p][0], ())) == 0:
            loose.setdefault(p[0], []).append(p)
    for ref in sorted(loose, key=_nat):
        where = "; ".join(f"{_pt(p)} on {_net_label(nl, nl.pins[p][0])}" for p in sorted(loose[ref], key=_pk))
        add("pin not in the intent", f"{ref}: in no group and not under [no_connect]: {where}")
    listed_refs = {p[0] for p in listed}
    for ref in sorted(nl.parts, key=_nat):
        if ref not in listed_refs and not intent.ignored(ref) and not nl.pins_of(ref):
            add("part not in the intent", f"{ref} ({nl.parts[ref].value}) has no pin in the netlist and is not "
                                           f"under [options] ignore")
    for pat in intent.ignore:
        if not any(fnmatch.fnmatchcase(r, pat) for r in nl.parts):
            add("intent file", f"[options] ignore names '{pat}', which matches no reference in the netlist")

    # 5. footprints
    for ref in sorted(nl.parts, key=_nat):
        part = nl.parts[ref]
        if not part.footprint and not part.exclude_from_board:
            add("no footprint", f"{ref} ({part.value}) has no footprint: it would vanish at the board import")

    counts = {"parts": len(nl.parts), "nets": len(nl.nets), "pins": len(nl.pins), "groups": len(intent.nets),
              "group_pins": len(group_of), "no_connect": len(intent.no_connect),
              "ignored_refs": sorted((r for r in nl.parts if intent.ignored(r)), key=_nat),
              "pins_accounted": len([p for p in nl.pins if p in listed]),
              "pins_ignored": len([p for p in nl.pins if p not in listed and intent.ignored(p[0])])}
    return {"mismatches": mm, "groups": groups, "no_connect": ncs, "counts": counts}


def pin_tables(nl: Netlist, many: int = 12) -> list[dict]:
    """Per part worth a look (more than two pins, or pins with names): [{ref, value, footprint, pins: [...]}]."""
    out = []
    for ref in sorted(nl.parts, key=_nat):
        nums = nl.pins_of(ref)
        named = [n for n in nums if nl.pins[(ref, n)][1] not in ("", "~", n)]
        if len(nums) <= 2 and not named:
            continue
        rows = []
        for n in sorted(nums, key=_nat):
            net, func, typ = nl.pins[(ref, n)]
            others = sorted((q for q in nl.nets[net] if q != (ref, n)), key=_pk)
            if not others:
                also = "(not connected)"
            elif len(others) > many:
                also = f"{len(others)} other pins"
            else:
                also = ", ".join(_pt(q) + (f"({nl.pins[q][1]})" if nl.pins[q][1] not in ("", "~", q[1]) else "")
                                 for q in others)
            rows.append({"pin": n, "name": func or "-", "type": typ, "net": net, "also": also})
        part = nl.parts[ref]
        out.append({"ref": ref, "value": part.value, "footprint": part.footprint, "units": part.units, "pins": rows})
    return out


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|")


def _pin_tables_md(tables: list[dict]) -> list[str]:
    L = []
    for t in tables:
        L += [f"### {t['ref']}: {t['value']} (`{t['footprint'] or 'NO FOOTPRINT'}`)", "",
              "| Pin | Pin name | Type | Net | Also on this net |", "|---|---|---|---|---|"]
        L += [f"| {_cell(r['pin'])} | {_cell(r['name'])} | {r['type']} | {_cell(r['net'])} | {_cell(r['also'])} |"
              for r in t["pins"]]
        L.append("")
    return L


def _show(path: str, base: str) -> str:
    try:
        rel = os.path.relpath(os.path.abspath(path), base).replace("\\", "/")
    except ValueError:
        return os.path.basename(path)
    return rel if rel.count("../") <= 3 else os.path.basename(path)


def report_md(res: dict) -> str:
    c = res["counts"]
    bad = res["mismatches"]
    L = ["# Connectivity report: netlist against the hand-written intent", "",
         f"- Netlist: `{res['netlist']['file']}` ({res['netlist']['tool'] or 'tool not named'}), SHA-256 "
         f"`{res['netlist']['sha256']}`: {c['parts']} parts, {c['pins']} pins, {c['nets']} nets "
         f"(single-pin nets included).",
         f"- Intent: `{res['intent']['file']}`, SHA-256 `{res['intent']['sha256']}`: {c['groups']} groups with "
         f"{c['group_pins']} pins, {c['no_connect']} pin(s) that must stay unconnected, "
         f"{len(c['ignored_refs'])} ignored references"
         + (f" ({', '.join(c['ignored_refs'])})" if c["ignored_refs"] else "") + ".",
         f"- Pins accounted for: {c['pins_accounted']} of {c['pins']}"
         + (f" ({c['pins_ignored']} belong to ignored references)" if c["pins_ignored"] else "") + ".",
         f"- **Result: {res['result']}** ({len(bad)} mismatch{'es' if len(bad) != 1 else ''}).", ""]
    if bad:
        L += ["## Mismatches", ""]
        L += [f"- **{m['kind']}**: {m['text']}" for m in bad]
        L.append("")
    st = res.get("self_test")
    if st is not None:
        L += ["## Mutation self-test (can the check fail?)", "",
              f"**{res['self_test_result']}**", "",
              "| Planted defect in a copy of the netlist | Expected | Got | New mismatch reported |", "|---|---|---|---|"]
        for s in st:
            want = "-" if s["got"] == "DOES NOT APPLY" else "FAIL"
            L.append(f"| {_cell(s['defect'])} | {want} | {s['got']} | {_cell(s['evidence'])} |")
        L.append("")
    L += ["## Groups", "", "| Expected group | Pins | KiCad net | Result |", "|---|---|---|---|"]
    for g in res["groups"]:
        nets = ", ".join(f"`{n}`" for n in g["nets"]) or "-"
        L.append(f"| {_cell(g['group'])} | {g['pins']} | {_cell(nets)} | {'PASS' if g['ok'] else '**FAIL**'} |")
    L.append("")
    if res["no_connect"]:
        L += ["## Pins that must stay unconnected", "", "| Pin | KiCad net | Result |", "|---|---|---|"]
        L += [f"| {n['pin']} | `{_cell(n['net']) or '-'}` | {'PASS' if n['ok'] else '**FAIL**'} |" for n in res["no_connect"]]
        L.append("")
    L += ["## Not checked", "",
          "- Whether the intent is right. A wrong idea written into the intent file and drawn the same way passes. "
          "That is the datasheet review's job.",
          "- Whether a symbol's pin NAMES and NUMBERS are those of the datasheet and of the footprint's pads: read "
          "the tables below against the pin functions noted in the intent file and against the footprint.",
          "- Values, ratings, part numbers, the drawing.", "",
          "## Per part: every pin, its name in the symbol, its net and what else is on that net", "",
          "Parts with more than two pins, and two-pin parts whose pins have names (diodes, polarised capacitors). "
          "Compare the pin names with the datasheet pin table.", ""]
    L += _pin_tables_md(res["pin_tables"])
    L.append("Method: `scripts/netlist_check.py` (its header lists the checks).")
    return "\n".join(L) + "\n"


# ---- the self-test: plant defects in copies of the netlist ------------------------------------------------------------
def _plain(node):
    return [_plain(x) if isinstance(x, list) else x for x in node]


def _net_nodes(doc: sexp.Document) -> tuple[dict, dict]:
    """{net name: net node}, {(ref, pin): (net name, node node)} of a netlist document."""
    nets: dict = {}
    where: dict = {}
    for n in sexp.find(sexp.first(doc.root, "nets"), "net"):
        name = str(sexp.value(n, "name", ""))
        nets.setdefault(name, n)
        for nd in sexp.find(n, "node"):
            where[(str(sexp.value(nd, "ref", "")), str(sexp.value(nd, "pin", "")))] = (name, nd)
    return nets, where


def plant(text: str, kind: str, nl: Netlist, intent: Intent) -> tuple[str | None, str]:
    """A copy of the netlist text with one defect; (None, reason) when this design offers no place for it."""
    doc = sexp.Document(text)
    nets, where = _net_nodes(doc)
    whole = [(g, ps) for g, ps in intent.nets.items()
             if len(ps) >= 2 and all(p in nl.pins for p in ps) and len({nl.pins[p][0] for p in ps}) == 1]
    whole.sort(key=lambda t: (-len(t[1]), t[0]))
    if kind == "merge":
        if len(whole) < 2:
            return None, "fewer than two groups that are whole nets"
        (ga, pa), (gb, pb) = whole[0], whole[1]
        na, nb = nl.pins[pa[0]][0], nl.pins[pb[0]][0]
        if na == nb:
            return None, "the two largest groups are already one net"
        doc.replace(nets[na], _plain(nets[na]) + [_plain(x) for x in sexp.find(nets[nb], "node")])
        doc.remove(nets[nb])
        return doc.text(), f"two nets merged: '{ga}' ({na}) and '{gb}' ({nb})"
    if kind == "split":
        if not whole:
            return None, "no group that is a whole net"
        g, ps = whole[0]
        p = sorted(ps, key=_pk)[-1]
        name, node = where[p]
        doc.remove(node)
        doc.insert_after(nets[name], ["net", ["code", sexp.Q("99999")], ["name", sexp.Q("self-test-split")],
                                      ["class", sexp.Q("Default")], _plain(node)])
        return doc.text(), f"one net split: {_pt(p)} cut off '{g}' ({name})"
    if kind == "connect":
        if not intent.no_connect:
            return None, "does not apply: the intent lists no no-connect pin"
        cands = [p for p in sorted(intent.no_connect, key=_pk) if p in nl.pins and len(nl.nets[nl.pins[p][0]]) == 1]
        if not cands or not whole:
            return None, "the intent lists no no-connect pin that is open in this netlist"
        p = cands[0]
        g, ps = whole[0]
        target = nl.pins[ps[0]][0]
        name, node = where[p]
        doc.replace(nets[target], _plain(nets[target]) + [_plain(node)])
        doc.remove(nets[name])
        return doc.text(), f"a no-connect pin connected: {_pt(p)} joined to '{g}' ({target})"
    raise ValueError(kind)


def self_test(netlist_path: str, nl: Netlist, intent: Intent, base: dict, keep: str | None) -> list[dict]:
    with open(netlist_path, encoding="utf-8", newline="") as f:
        text = f.read()
    seen = {m["text"] for m in base["mismatches"]}
    out = []
    with kicad_io.private_tmp("netlist-selftest-") as tmp:
        folder = keep or tmp
        os.makedirs(folder, exist_ok=True)
        for kind in ("merge", "split", "connect"):
            new_text, what = plant(text, kind, nl, intent)
            if new_text is None:
                na = what.startswith("does not apply")
                out.append({"defect": {"merge": "two nets merged", "split": "one net split",
                                       "connect": "a no-connect pin connected"}[kind] + f": {what}",
                            "got": "DOES NOT APPLY" if na else "NOT PLANTED", "caught": False, "evidence": "-", "file": ""})
                continue
            path = os.path.join(folder, f"selftest_{kind}.net")
            kicad_io.atomic_write(path, new_text)
            res = check(kicad_io.read_netlist(path), intent)
            new = [m for m in res["mismatches"] if m["text"] not in seen]
            caught = bool(new)
            out.append({"defect": what, "got": "FAIL" if caught else "PASS (defect NOT caught)", "caught": caught,
                        "evidence": (f"{new[0]['kind']}: {new[0]['text']}"[:220] + (f" (+{len(new) - 1} more)"
                                                                                    if len(new) > 1 else "")) if new else "-",
                        "file": os.path.basename(path) if keep else ""})
    return out


# ---- --names: net names across sheets -----------------------------------------------------------------------------------
def _label_kinds(root: str) -> dict[str, set]:
    """{net name: {"power symbol" | "global label" | "hierarchical label" | "label"}} from the schematic files."""
    kinds: dict[str, set] = {}
    for path in sorted({s["file"] for s in kicad_io.schematic_sheets(root)}):
        with open(path, encoding="utf-8") as f:
            tree = sexp.parse(f.read())
        power = {str(s[1]) for s in sexp.find(sexp.first(tree, "lib_symbols"), "symbol") if sexp.first(s, "power") is not None}
        for head, word in (("global_label", "global label"), ("hierarchical_label", "hierarchical label"), ("label", "label")):
            for lb in sexp.find(tree, head):
                if len(lb) > 1:
                    kinds.setdefault(str(lb[1]), set()).add(word)
        for sym in sexp.find(tree, "symbol"):
            if str(sexp.value(sym, "lib_id", "")) in power:
                for pr in sexp.find(sym, "property"):
                    if len(pr) > 2 and pr[1] == "Value":
                        kinds.setdefault(str(pr[2]), set()).add("power symbol")
    return kinds


def names_listing(nl: Netlist, declared: list[str], schematic: str | None = None) -> dict:
    kinds = _label_kinds(schematic) if schematic else None
    sheet_file = {p.sheet: p.sheet_file for p in nl.parts.values()}
    one, same = [], []
    used_declared = set()
    by_leaf: dict[str, list[str]] = {}
    hier = 0
    for name, nodes in nl.nets.items():
        if not is_named(name) or not nodes:
            continue
        sheets = sorted({nl.parts[r].sheet for r, _ in nodes if r in nl.parts})
        if name.startswith("/"):
            by_leaf.setdefault(leaf(name), []).append(name)
            if len(sheets) > 1:
                hier += 1                                   # joined through sheet pins: a drawn connection
            continue
        if len(sheets) < 2:
            continue
        types = {nl.pins[n][2].split("+")[0] for n in nodes}
        if kinds is not None:
            k = kinds.get(name, set())
            supply = "power symbol" in k
            how = ", ".join(sorted(k)) or "not found in the sheets"
        else:
            supply = bool(types & {"power_in", "power_out"})
            how = "has supply pins" if supply else "no supply pin on it"
        if name in declared:
            status = "DECLARED"
            used_declared.add(name)
        else:
            status = "SUPPLY" if supply else "REVIEW"
        one.append({"name": name, "sheets": sheets, "pins": len(nodes), "how": how, "status": status})
    for lf, names in sorted(by_leaf.items()):
        if len(names) < 2:
            continue
        places = sorted({n.rsplit("/", 1)[0] + "/" for n in names})
        files = {sheet_file.get(p, p) for p in places}
        repeated = len(files) == 1 and len(places) > 1 and all(p in sheet_file for p in places)
        same.append({"name": lf, "nets": sorted(names), "status": "REPEATED SHEET" if repeated else "REVIEW"})
    stale = sorted(d for d in declared if d not in used_declared)
    rank = {"REVIEW": 0, "DECLARED": 1, "SUPPLY": 2}
    one.sort(key=lambda r: (rank[str(r["status"])], str(r["name"])))
    review = len([r for r in one if r["status"] == "REVIEW"]) + len([r for r in same if r["status"] == "REVIEW"]) + len(stale)
    return {"one_net_many_sheets": one, "same_name_separate_nets": same, "declared_not_used": stale,
            "joined_through_sheet_pins": hier, "to_review": review, "sheets": len({p.sheet for p in nl.parts.values()}),
            "label_source": "schematic files" if kinds is not None else "netlist only (pin types)"}


def names_md(res: dict) -> str:
    L = ["# Net names across sheets", "",
         f"- Netlist: `{res['netlist']['file']}`, SHA-256 `{res['netlist']['sha256']}`; {res['sheets']} sheet(s) "
         f"with parts; supply names recognised from: {res['label_source']}.",
         f"- **Result: {'PASS: nothing to review' if not res['to_review'] else 'FAIL: ' + str(res['to_review']) + ' name(s) to review'}**", "",
         "A name that is global (a global label or a supply symbol) is ONE net on every sheet where it appears, "
         "with no line drawn between the sheets. Two different nodes that were given the same name are then "
         "shorted, and no rule check sees it. Go through the REVIEW rows: is it the same node on every sheet?",
         "Confirmed names are passed with `--declared` (or `[schematic] global_nets` in board.toml).", "",
         "## One name, one net, more than one sheet", "",
         "| Net name | Status | Pins | Named by | Sheets |", "|---|---|---|---|---|"]
    for r in res["one_net_many_sheets"]:
        L.append(f"| `{_cell(r['name'])}` | {'**REVIEW**' if r['status'] == 'REVIEW' else r['status']} | {r['pins']} | "
                 f"{r['how']} | {_cell(', '.join(r['sheets']))} |")
    if not res["one_net_many_sheets"]:
        L.append("| (none) | | | | |")
    L += ["", "SUPPLY: named by a supply symbol (or, without the schematic files, a net with supply pins): expected "
          "to span sheets, still worth one look. DECLARED: confirmed by the designer.", ""]
    if res["declared_not_used"]:
        L += ["**Declared names that no longer span sheets (a stale list hides the next duplicate): "
              + ", ".join(f"`{d}`" for d in res["declared_not_used"]) + "**", ""]
    L += ["## The same name on several sheets, but SEPARATE nets", "",
          "Local labels with the same text on different sheets are not connected. If they were meant to be one "
          "node, the circuit is open there.", "",
          "| Name | Status | The separate nets |", "|---|---|---|"]
    for r in res["same_name_separate_nets"]:
        L.append(f"| `{_cell(r['name'])}` | {'**REVIEW**' if r['status'] == 'REVIEW' else r['status']} | "
                 f"{_cell(', '.join(r['nets']))} |")
    if not res["same_name_separate_nets"]:
        L.append("| (none) | | |")
    L += ["", "REPEATED SHEET: the same sheet file used more than once; each copy has its own nets by design.", "",
          "## Not checked", "",
          f"- {res['joined_through_sheet_pins']} net(s) span sheets through sheet pins (hierarchical labels): those "
          f"are drawn connections and are not listed.",
          "- Nets that KiCad named itself (no label).",
          "- Whether a name says what the net is.", "",
          "Method: `scripts/netlist_check.py --names`."]
    return "\n".join(L) + "\n"


# ---- --screens: four screens that need no intent file ------------------------------------------------------------------
SCREENS = [("S1", "A two-pin part with both pins on one net (shorted out, it does nothing)"),
           ("S2", "A supply pin with no path for direct current (its net holds only capacitors and other supply inputs)"),
           ("S3", "A rail fed only through an open or unfitted link"),
           ("S4", "A net with one pin only, not marked as not connected")]
GROUND_DEFAULT = ["GND", "*GND*", "VSS", "VSS*", "*VSS", "0V", "EARTH*", "*EARTH", "CHASSIS*", "GROUND*"]
SCREEN_WAIVERS_DEFAULT = os.path.join("src", "netlist_screens_waivers.toml")
_DNP_WORDS = re.compile(r"(?i)\b(DNP|DNF|DNI|NOPOP|NO[ _-]?POP|NOT[ _-]?(FITTED|POPULATED|MOUNTED|PLACED)|UNFITTED|"
                        r"DO[ _-]?NOT[ _-]?(FIT|POPULATE|PLACE|MOUNT|STUFF))\b")
_CAP_SYMBOL = re.compile(r"(?i)^(C|CP|CP1|C_Small|CP_Small|CP1_Small|C_Polari[sz]ed\w*|C_US|CP_US|Capacitor\w*|C_Trim\w*|"
                         r"C_Variable\w*)$")
_SUPPLY_NAME = re.compile(r"(?i)^((A|D|P|IO|IO_)?V(CC|DD)\w*|VIN\d*|VBAT\w*|VSUP\w*|VS\+?|V\+)$")
_NO_FIT_FIELDS = ("dnp", "dnf", "dni", "do not populate", "do not fit", "not fitted", "nofit", "no pop", "nopop")
_FIT_FIELDS = ("populate", "populated", "fitted", "fit", "mount", "mounted", "assemble", "place", "stuff")
_NO = ("0", "no", "n", "false", "-")
RELIES_ON = [
    "Supply input: a pin whose electrical type in the netlist (from its symbol) is `power_in`. Pin NAMES are not trusted "
    "as a type: pins named like a supply (VCC, VDD, VIN, ...) but typed otherwise are listed under Not checked.",
    "Not connected on purpose: the pin type `no_connect` (from the library), or `+no_connect`, which KiCad adds when a "
    "no-connect flag sits on the pin.",
    "Capacitor: a part with two pins whose reference prefix is C, or whose library symbol is a capacitor (C, C_Small, CP, "
    "C_Polarized, ...), or whose description says capacitor (a feed-through capacitor has three pins and is not one).",
    "Not fitted: KiCad's do-not-populate mark (`dnp`), 'exclude from board', a value or field that says DNP, DNF, DNI, "
    "NOPOP, NOT FITTED, DO NOT POPULATE (and the like), a field named DNP or DNF that is set, or a field named Populate, "
    "Fitted or Mount set to no. 'Exclude from BOM' alone is NOT taken as not fitted (KiCad sets it on net ties and test "
    "points too). Parts not fitted are left out of the 'as fitted' walk, and their supply pins are not screened.",
    "Jumper: reference prefix JP or SJ, or 'Jumper' in the symbol, library or footprint name. Its state comes from the "
    "symbol name, then the footprint name, then the value: Open or NO = open; Bridged, Closed, Shorted or NC = closed; "
    "Bridged12, Bridged123 for three-pin jumpers (pin 2 is the middle). Symbol and footprint that disagree, or no mark "
    "at all: the state is unknown, and what depends on it is listed as not checked.",
    "Net tie: a symbol or footprint whose name starts with NetTie, or the reference prefix NT.",
    "Links (screens 2 and 3 walk through them, both ways): jumpers, net ties and every other two-pin part that is not a "
    "capacitor, connector, battery, test point, mounting hole or fiducial (resistors, ferrites, inductors, fuses, "
    "diodes, switches, ...). A walk never enters a ground net (net names matched by the ground patterns).",
    "What can feed a rail: a pin of a connector (prefix J, P, X, CN, CON, or a Conn/Connector symbol, library or "
    "footprint) or of a battery (BT, BAT, Battery), a pin typed `power_out`, and any other pin of a part with more than "
    "two pins, except pins typed `power_in`, `input` or not connected. This is generous on purpose: a lead is raised "
    "only where nothing at all could deliver direct current.",
]


def _prefix(ref: str) -> str:
    m = re.match(r"[A-Za-z_]+", ref)
    return m.group(0).upper() if m else ""


def _fp_parts(fp: str) -> tuple[str, str]:
    """(library, name) of a footprint 'Library:Name'."""
    return (fp.split(":", 1)[0], fp.split(":", 1)[1]) if ":" in fp else ("", fp)


def _part_kind(p, npins: int) -> str:
    """net tie, jumper, test point, mounting hole, fiducial, battery, connector, capacitor, two-pin or other."""
    pre, sym, lib, desc = _prefix(p.ref), p.part, p.lib, p.description.lower()
    fpl, fpn = _fp_parts(p.footprint)
    names = [sym.lower(), fpl.lower(), fpn.lower()]
    if pre == "NT" or any(n.startswith("nettie") for n in names):
        return "net tie"
    if pre in ("JP", "SJ") or "jumper" in " ".join(names + [lib.lower()]):
        return "jumper"
    if pre == "TP" or any(n.startswith("testpoint") for n in names):
        return "test point"
    if pre in ("H", "MH") or any(n.startswith("mountinghole") for n in names):
        return "mounting hole"
    if pre == "FID" or any(n.startswith("fiducial") for n in names):
        return "fiducial"
    if pre in ("BT", "BAT") or any(n.startswith("battery") for n in names):
        return "battery"
    if pre in ("J", "P", "X", "CN", "CON", "XS", "XP") or sym.lower().startswith("conn") or \
            lib.lower().startswith("connector") or fpl.lower().startswith("connector"):
        return "connector"
    if npins == 2 and (pre == "C" or _CAP_SYMBOL.match(sym) or ("capacitor" in desc and "feed" not in desc)):
        return "capacitor"
    return "two-pin" if npins == 2 else "other"


def _not_fitted(p) -> str:
    """Why the part is not fitted, or ''."""
    if p.dnp:
        return "KiCad's do-not-populate mark"
    if p.exclude_from_board:
        return "excluded from the board"
    if _DNP_WORDS.search(p.value or ""):
        return f"its value says '{p.value}'"
    for k, v in p.fields.items():
        kl, vl = k.strip().lower(), str(v).strip().lower()
        if kl in ("footprint", "datasheet", "description", "value", "reference"):
            continue
        if kl in _NO_FIT_FIELDS:
            if vl not in ("",) + _NO:
                return f"its field '{k}' is '{v}'"
        elif kl in _FIT_FIELDS:
            if vl in _NO:
                return f"its field '{k}' is '{v}'"
        elif _DNP_WORDS.search(str(v)):
            return f"its field '{k}' is '{v}'"
    return ""


def _marks(text: str) -> str:
    """'open', 'closed' or '' from one name: Open / NO = open; Bridged / Closed / Shorted / NC = closed."""
    t = text or ""
    closed = bool(re.search(r"(?i)bridged|closed|shorted", t) or re.search(r"(^|_)NC(_|$)", t))
    opened = bool(re.search(r"(?i)(?<![a-z])open", t) or re.search(r"(^|_)NO(_|$)", t))
    if closed == opened:
        return ""
    return "closed" if closed else "open"


def _jumper_links(p, pins: list[str]) -> tuple[list[tuple], str]:
    """The links of a jumper: [(pin a, pin b, "closed" | "open" | "unknown", how it was read)], and '' or why the
    jumper is not modelled (more than three pins, or three pins that are not 1, 2, 3)."""
    fpn = _fp_parts(p.footprint)[1]
    reads = [("symbol", p.part), ("footprint", fpn), ("value", p.value)]
    said = [(where, name, _marks(name)) for where, name in reads]
    sym_fp = [s for s in said[:2] if s[2]]
    if len(sym_fp) == 2 and sym_fp[0][2] != sym_fp[1][2]:
        state, how = "unknown", f"symbol '{p.part}' and footprint '{fpn}' disagree"
    elif sym_fp:
        state, how = sym_fp[0][2], f"{sym_fp[0][0]} '{sym_fp[0][1]}'"
    elif said[2][2]:
        state, how = said[2][2], f"value '{p.value}'"
    else:
        state, how = "unknown", f"no open or bridged mark in symbol '{p.part}', footprint '{fpn}' or value '{p.value}'"
    if len(pins) == 2:
        return [(pins[0], pins[1], state, how)], ""
    if len(pins) == 3 and sorted(pins) == ["1", "2", "3"]:
        m = re.search(r"(?i)bridged(?:2bar)?(\d{2,3})", p.part) or re.search(r"(?i)bridged(?:2bar)?(\d{2,3})", fpn)
        if m:
            digits = m.group(1)
            st12 = "closed" if "12" in digits else "open"
            st23 = "closed" if "23" in digits else "open"
            how3 = f"'{m.group(0)}'"
            return [("1", "2", st12, how3), ("2", "3", st23, how3)], ""
        s3 = state if state == "open" else "unknown"
        return [("1", "2", s3, how), ("2", "3", s3, how)], ""
    return [], f"a jumper with {len(pins)} pins ({', '.join(pins)}) is not modelled"


class _Design:
    """What the screens know about each part and pin of a netlist."""

    def __init__(self, nl: Netlist, ground: list[str]):
        self.nl = nl
        self.pins_of = {ref: nl.pins_of(ref) for ref in nl.parts}
        self.kind = {ref: _part_kind(p, len(self.pins_of[ref])) for ref, p in nl.parts.items()}
        self.unfit = {ref: _not_fitted(p) for ref, p in nl.parts.items()}
        self.ground ={n for n in nl.nets if is_named(n)            # not KiCad's own names: unconnected-(J1-GND-Pad5)
                       and any(fnmatch.fnmatchcase(leaf(n).upper(), g.upper()) for g in ground)}
        self.typed = any(t[2] for t in nl.pins.values())
        self.links: list[dict] = []
        self.unmodelled: list[str] = []
        for ref in sorted(nl.parts, key=_nat):
            k, pins = self.kind[ref], self.pins_of[ref]
            if k == "jumper":
                pairs, why = _jumper_links(nl.parts[ref], pins)
                if why:
                    self.unmodelled.append(f"{ref} ({why})")
                    self.kind[ref] = "other"
            elif k == "net tie" and len(pins) == 2:
                pairs = [(pins[0], pins[1], "closed", "a net tie")]
            elif k == "two-pin":
                pairs = [(pins[0], pins[1], "closed", "a two-pin part")]
            else:
                continue
            for a, b, state, how in pairs:
                self.links.append({"ref": ref, "a": a, "b": b, "na": nl.pins[(ref, a)][0], "nb": nl.pins[(ref, b)][0],
                                   "state": state, "how": how, "unfit": self.unfit[ref]})
        self.at: dict[str, list[dict]] = {}
        for lk in self.links:
            self.at.setdefault(lk["na"], []).append(lk)
            if lk["nb"] != lk["na"]:
                self.at.setdefault(lk["nb"], []).append(lk)
        self.linked = {lk["ref"] for lk in self.links}

    def base(self, pin: Pin) -> str:
        return self.nl.pins[pin][2].split("+")[0]

    def no_connect(self, pin: Pin) -> bool:
        t = self.nl.pins[pin][2]
        return t.split("+")[0] == "no_connect" or t.endswith("+no_connect")

    def supply_in(self, pin: Pin) -> bool:
        return self.base(pin) == "power_in" and not self.no_connect(pin)

    def feed(self, pin: Pin) -> bool:
        """Could this pin deliver direct current to its net (whether the part is fitted is asked apart)?"""
        k = self.kind[pin[0]]
        if k in ("connector", "battery"):
            return True
        if k in ("capacitor", "test point", "mounting hole", "fiducial", "two-pin", "net tie") or pin[0] in self.linked:
            return False
        b = self.base(pin)
        if b == "power_out":
            return True
        return b not in ("power_in", "input", "no_connect") and not self.no_connect(pin)

    def walk(self, start: str, model: str) -> tuple[bool, list[str], list[Pin], list[dict]]:
        """From net `start`, through the links that conduct in `model`, never into a ground net:
        model "all" (every part fitted, every link closed), "fitted" (parts not fitted left out, open links open,
        links of unknown state closed), "fitted-strict" (the same, links of unknown state open).
        Returns (fed?, nets reached, feeding pins found, links crossed)."""
        seen, todo, feeds, crossed = {start}, [start], [], []
        while todo:
            n = todo.pop()
            for p in sorted(self.nl.nets[n], key=_pk):
                if self.feed(p) and (model == "all" or not self.unfit[p[0]]):
                    feeds.append(p)
            for lk in self.at.get(n, []):
                if model != "all" and (lk["unfit"] or lk["state"] == "open" or
                                       (lk["state"] == "unknown" and model == "fitted-strict")):
                    continue
                other = lk["nb"] if lk["na"] == n else lk["na"]
                if other in self.ground or other in seen:
                    continue
                crossed.append(lk)
                seen.add(other)
                todo.append(other)
        return bool(feeds), sorted(seen, key=_nat), feeds, crossed


def _pin_desc(nl: Netlist, p: Pin) -> str:
    name = nl.pins[p][1]
    return _pt(p) + (f" ({name})" if name not in ("", "~", p[1]) else "")


def _supply_desc(nl: Netlist, pins: list[Pin]) -> str:
    """'U2.1 (VDD), U2.3 (VDDA) of U2 (MCU_X); U3.1 (VDD) of U3 (SENSOR_X)'."""
    by: dict[str, list[Pin]] = {}
    for q in sorted(pins, key=_pk):
        by.setdefault(q[0], []).append(q)
    return "; ".join(f"{', '.join(_pin_desc(nl, q) for q in qs)} of {r} ({nl.parts[r].value if r in nl.parts else '?'})"
                     for r, qs in sorted(by.items(), key=lambda t: _nat(t[0])))


def _link_desc(lk: dict, here: set) -> str:
    other = lk["nb"] if lk["na"] in here else lk["na"]
    why = f"not fitted: {lk['unfit']}" if lk["unfit"] else (
        f"drawn open: {lk['how']}" if lk["state"] == "open" else f"state unknown: {lk['how']}")
    return f"{lk['ref']} ({why}) to {other}"


def screen(nl: Netlist, ground: list[str]) -> dict:
    """The four screens. Returns {"findings": [...], "not_checked": [...], "status": {screen: text}, "facts": {...}}."""
    D = _Design(nl, ground)
    found: list[dict] = []
    nc: list[dict] = []
    status = {s: "" for s, _ in SCREENS}

    def add(scr: str, subject: str, text: str, why: str, harmless: str, parts, pins, nets) -> None:
        found.append({"id": f"{scr}:{subject}", "screen": scr, "subject": subject, "text": text, "why": why,
                      "harmless": harmless, "parts": sorted(set(parts), key=_nat), "pins": [_pt(p) for p in sorted(set(pins), key=_pk)],
                      "nets": list(dict.fromkeys(nets)), "waived": False, "waiver_reason": ""})

    def other_pins(n: str, skip) -> list[Pin]:
        return sorted((q for q in nl.nets[n] if q not in skip), key=_pk)

    # S1: a two-pin part with both pins on one net
    for ref in sorted(nl.parts, key=_nat):
        pins = D.pins_of[ref]
        if len(pins) != 2:
            continue
        na, nb = nl.pins[(ref, pins[0])][0], nl.pins[(ref, pins[1])][0]
        if na != nb:
            continue
        k, part = D.kind[ref], nl.parts[ref]
        state = next((lk["state"] for lk in D.links if lk["ref"] == ref), "")
        if k == "net tie" or (k == "jumper" and state == "closed"):
            continue
        what = {"jumper": f"a jumper ({'drawn open' if state == 'open' else 'state not drawn'})", "capacitor": "a capacitor",
                "connector": "a connector"}.get(k, "")
        others = len(nl.nets[na]) - 2
        add("S1", ref, f"both pins of {ref} ({part.value}{', ' + what if what else ''}) are on net {na}"
                       f"{f' (with {others} other pin(s))' if others else ' (and nothing else)'}: the part is shorted out "
                       f"and does nothing",
            "one end was probably meant for another net (a wire or label on the wrong pin, a supply symbol on the wrong side)",
            "the part is meant to sit on one node (a bridged link, two contacts in parallel, a part kept for a later "
            "change); a jumper that is meant to be closed is drawn bridged" if k == "jumper" else
            "the part is meant to sit on one node (two contacts in parallel, a link kept for a later change); otherwise "
            "move one end to its own net",
            [ref], [(ref, pins[0]), (ref, pins[1])], [na])

    # S2 and S3: the supply inputs of fitted parts
    supply: dict[str, list[Pin]] = {}
    for p in nl.pins:
        if D.supply_in(p) and not D.unfit[p[0]]:
            supply.setdefault(nl.pins[p][0], []).append(p)
    if not D.typed:
        status["S2"] = status["S3"] = "NOT CHECKED: the netlist carries no pin types"
    elif not supply:
        status["S2"] = status["S3"] = "NOT CHECKED: no pin of a fitted part is typed power input"
    s2_nets = set()
    if not status["S2"]:
        for n in sorted(supply, key=_nat):
            if len(nl.nets[n]) < 2:
                continue                                            # a lone supply pin: screen 4 names it
            fed, reached, _, crossed = D.walk(n, "all")
            if fed:
                continue
            s2_nets.add(n)
            sp = sorted(supply[n], key=_pk)
            walked = {lk["ref"] for lk in crossed}
            rest = [q for m in reached for q in other_pins(m, set(sp)) if q[0] not in walked]
            caps = [q for q in rest if D.kind[q[0]] == "capacitor"]
            else_ = [q for q in rest if D.kind[q[0]] != "capacitor"]
            beyond = f"; through {', '.join(sorted({lk['ref'] for lk in crossed}, key=_nat))} it reaches only " \
                     f"{', '.join(m for m in reached if m != n)}" if crossed else ""
            text = (f"supply input(s) {_supply_desc(nl, sp)} on net {n}; besides them the net holds "
                    f"{('only the capacitor pin(s) ' + _pins(caps)) if caps else 'no capacitor'}"
                    f"{(' and ' + ', '.join(_pin_desc(nl, q) + ' (' + (D.base(q) or 'no type') + ')' for q in else_)) if else_ else ''}"
                    f"{beyond}: nothing there can deliver direct current")
            add("S2", n, text, "the chip gets no supply on this pin: a capacitor (or another supply input) passes no direct "
                               "current",
                "the supply arrives by a way the netlist does not show (a wire, another board through a connector that is "
                "not drawn); or the part with these pins is itself the way in (an edge connector or a plug-in module "
                "whose library types its supply pins as power input); or a pin here that is typed power input really "
                "delivers the supply (a regulator output drawn as an input: check the pin names)",
                [q[0] for q in sp + caps + else_] + [lk["ref"] for lk in crossed], sp, reached)
    if not status["S3"]:
        for n in sorted(supply, key=_nat):
            if n in D.ground or n in s2_nets or len(nl.nets[n]) < 2:
                continue                                            # every other rail is fed with all parts fitted (S2)
            sp = sorted(supply[n], key=_pk)
            fed, reached, _, _ = D.walk(n, "fitted")
            here = set(reached)
            if not fed:
                block = [lk for m in reached for lk in D.at.get(m, [])
                         if (lk["unfit"] or lk["state"] == "open") and not ({lk["na"], lk["nb"]} <= here)
                         and ({lk["na"], lk["nb"]} - here) - D.ground]
                block = list({id(lk): lk for lk in block}.values())
                gone = sorted({q for m in reached for q in nl.nets[m] if D.feed(q) and D.unfit[q[0]]}, key=_pk)
                parts = [_link_desc(lk, here) for lk in sorted(block, key=lambda x: _nat(x["ref"]))] + \
                    [f"{_pin_desc(nl, q)} of {q[0]} ({nl.parts[q[0]].value}, not fitted: {D.unfit[q[0]]})" for q in gone]
                add("S3", n, f"supply input(s) {_supply_desc(nl, sp)} on net {n}, which is fed only through "
                             f"{'; '.join(parts) or 'parts that are not fitted'}: as drawn and fitted, nothing delivers "
                             f"direct current to this rail",
                    "as fitted, the chip(s) on this rail get no supply",
                    "the link is meant to be closed or fitted at assembly (a solder bridge made by hand, a part fitted "
                    "later: then the assembly notes say so), or the rail is fed by a way the netlist does not show",
                    [q[0] for q in sp] + [lk["ref"] for lk in block] + [q[0] for q in gone], sp,
                    reached + sorted({lk["na"] for lk in block} | {lk["nb"] for lk in block}, key=_nat))
                continue
            strict, reached2, _, _ = D.walk(n, "fitted-strict")
            if not strict:
                unknown = sorted({lk["ref"] for m in reached2 for lk in D.at.get(m, []) if lk["state"] == "unknown"
                                  and not lk["unfit"]}, key=_nat)
                how = "; ".join(f"{r}: {next(lk['how'] for lk in D.links if lk['ref'] == r)}" for r in unknown)
                nc.append({"screen": "S3", "text": f"{n} ({_pins(sp)}): its only fitted feed passes {', '.join(unknown)}, "
                                                   f"whose state (open or bridged) the drawing does not show ({how}): if "
                                                   f"it is open, this rail has no supply"})
    # S4: a net with one pin, not marked as not connected
    for n in sorted(nl.nets, key=_nat):
        if len(nl.nets[n]) != 1:
            continue
        p = next(iter(nl.nets[n]))
        if D.no_connect(p):
            continue
        part = nl.parts.get(p[0])
        typ = nl.pins[p][2] or "type not given"
        if is_named(n):
            text = (f"{_pin_desc(nl, p)} of {p[0]} ({part.value if part else '?'}) is the only pin on net {n}: a label "
                    f"with no partner")
            why = "the label at the other end is misspelt or missing, so the connection is open"
        else:
            text = f"{_pin_desc(nl, p)} of {p[0]} ({part.value if part else '?'}, {typ}) is connected to nothing and has " \
                   f"no no-connect mark"
            why = "a wire or label was forgotten, so the pin floats"
        if D.supply_in(p):
            why += "; it is a supply input: the chip gets no supply on this pin"
        add("S4", _pt(p), text, why, "the pin is meant to stay open (a spare pin, an unused contact): mark it with a "
                                     "no-connect flag, or waive it with the reason", [p[0]], [p], [n])
    if not D.typed:
        nc.append({"screen": "S4", "text": "the netlist carries no pin types, so no-connect marks cannot be read: every lone "
                                           "pin is listed"})

    # what the screens cannot tell
    for ref in sorted(nl.parts, key=_nat):
        if D.kind[ref] != "other" or len(D.pins_of[ref]) < 3:
            continue
        named = [q for q in ((ref, n) for n in D.pins_of[ref]) if _SUPPLY_NAME.match(nl.pins[q][1] or "")
                 and D.base(q) not in ("power_in", "power_out")]
        if named:
            nc.append({"screen": "S2, S3", "text": f"{ref} ({nl.parts[ref].value}): pin(s) "
                       f"{', '.join(_pin_desc(nl, q) + ' typed ' + (D.base(q) or 'nothing') for q in named)} are named "
                       f"like supply pins but not typed power input: their supply was not screened"})
    if D.unmodelled:
        nc.append({"screen": "S1, S3", "text": "jumpers not modelled: " + "; ".join(D.unmodelled)})
    if supply and not D.ground:
        nc.append({"screen": "S2, S3", "text": f"no net name matches the ground patterns ({', '.join(ground)}): screens 2 and "
                                               f"3 walked through parts into every net, so a rail may look fed through a "
                                               f"part to ground; name the ground nets with --ground"})
    found.sort(key=lambda f: (f["screen"], _nat(f["subject"])))
    facts = {"supply_inputs": sum(len(v) for v in supply.values()), "supply_nets": len(supply),
             "capacitors": sum(1 for k in D.kind.values() if k == "capacitor"),
             "links": len(D.links), "ground_nets": sorted(D.ground, key=_nat), "ground_patterns": ground,
             "not_fitted": {r: w for r, w in sorted(D.unfit.items(), key=lambda t: _nat(t[0])) if w},
             "jumpers": {lk["ref"] + (f" {lk['a']}-{lk['b']}" if len(D.pins_of[lk["ref"]]) > 2 else ""): lk["state"]
                         for lk in D.links if D.kind[lk["ref"]] == "jumper"}}
    return {"findings": found, "not_checked": nc, "status": status, "facts": facts}


def read_waivers(path: str) -> list[dict]:
    """The waiver file: [[waive]] finding = "S4:J3.*", reason = "...". KicadIOError when it cannot be read."""
    try:
        import tomllib
    except ImportError:
        raise KicadIOError("reading the waiver file needs Python 3.11 or newer (tomllib)") from None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise KicadIOError(f"{path}: not valid TOML: {e}") from None
    extra = [k for k in data if k != "waive"]
    if extra or not isinstance(data.get("waive", []), list):
        raise KicadIOError(f"{path}: a waiver file holds only [[waive]] tables (finding = \"S4:J3.2\", reason = \"...\"); "
                           f"found {', '.join(extra) or 'waive that is not a list of tables'}")
    return [w if isinstance(w, dict) else {"finding": str(w)} for w in data.get("waive", [])]


def apply_waivers(findings: list[dict], waivers: list[dict]) -> dict:
    """Mark the waived findings. Returns {"applied": [...], "stale": [...], "not_applied": [...]}."""
    out = {"applied": [], "stale": [], "not_applied": []}
    for w in waivers:
        pat, reason = str(w.get("finding", "")).strip(), str(w.get("reason", "")).strip()
        m = re.match(r"(?i)^(S[1-4])\s*:\s*(.+)$", pat)
        if not m:
            out["not_applied"].append({"finding": pat, "why": "not a finding: write S1 to S4, a colon, then the part, pin or "
                                                              "net (wildcards * and ? allowed)"})
            continue
        if not reason:
            out["not_applied"].append({"finding": pat, "why": "no written reason: a waiver needs one"})
            continue
        scr, subj = m.group(1).upper(), m.group(2).strip()
        hit = []
        for f in findings:                                      # the subject (part, net or pin), its pins, its nets
            if f["screen"] == scr and any(fnmatch.fnmatchcase(x, subj) for x in [f["subject"]] + f["pins"] + f["nets"]):
                f["waived"], f["waiver_reason"] = True, reason
                hit.append(f["id"])
        (out["applied"] if hit else out["stale"]).append({"finding": pat, "reason": reason, "matched": hit})
    return out


def screens_md(res: dict) -> str:
    act = [f for f in res["findings"] if not f["waived"]]
    wv = [f for f in res["findings"] if f["waived"]]
    nc = res["not_checked"]
    if act:
        head = f"LEADS: {len(act)} to review"
    else:
        head = "NO LEADS: the four screens found nothing"
    tail = [f"{len(wv)} more waived" if wv else "", f"{len(nc)} item(s) not checked" if nc else ""]
    L = ["# Netlist screens: four usual slips, found without an intent file", "",
         f"- Netlist: `{res['netlist']['file']}` ({res['netlist']['tool'] or 'tool not named'}), SHA-256 "
         f"`{res['netlist']['sha256']}`: {res['counts']['parts']} parts, {res['counts']['pins']} pins, "
         f"{res['counts']['nets']} nets.",
         f"- **Result: {head}**" + (f" ({'; '.join(t for t in tail if t)})" if any(tail) else "") + ".",
         "- These are leads for the reviewer, not verdicts: each may be harmless, and its last line says what would make "
         "it so. \"Nothing found\" is not a review of the connections: the screens look for four kinds of slip only, and "
         "what they could not tell is listed under Not checked.", "",
         "| Screen | What it looks for | Result |", "|---|---|---|"]
    for scr, title in SCREENS:
        st = res["screens"][[s["screen"] for s in res["screens"]].index(scr)]
        L.append(f"| {scr[1]} | {title} | {_cell(st['status'])} |")
    L.append("")
    if res["findings"]:
        L += ["## Leads", ""]
        for scr, title in SCREENS:
            these = [f for f in res["findings"] if f["screen"] == scr]
            if not these:
                continue
            L += [f"### Screen {scr[1]}: {title}", ""]
            for f in these:
                tag = f"WAIVED: {f['waiver_reason']}" if f["waived"] else "lead"
                L += [f"- **{f['id']}** ({tag}): {f['text']}.",
                      f"  - Why it may be a fault: {f['why']}.",
                      f"  - Harmless if: {f['harmless']}."]
            L.append("")
    L += ["## Not checked", ""]
    L += [f"- ({n['screen']}) {n['text']}." for n in nc] or ["- Nothing: each screen could judge everything it looks at."]
    L.append("")
    w = res["waivers"]
    L += ["## Waivers", ""]
    if not w.get("file"):
        L.append("- No waiver file (give one with `--waivers FILE`, or name it in board.toml: [netlist_check] screen_waivers).")
    else:
        L.append(f"- File `{w['file']}`: {len(w['applied'])} applied, {len(w['stale'])} matching nothing, "
                 f"{len(w['not_applied'])} not applied.")
        L += [f"- Matches nothing (stale, remove it or fix it): `{x['finding']}` ({x['reason']})" for x in w["stale"]]
        L += [f"- NOT APPLIED: `{x['finding']}`: {x['why']}" for x in w["not_applied"]]
    fa = res["facts"]
    L += ["", "## What the screens rely on", "",
          f"Found in this netlist: {fa['supply_inputs']} supply input pin(s) on {fa['supply_nets']} net(s), "
          f"{fa['capacitors']} capacitor(s), {fa['links']} link(s), ground nets: "
          f"{', '.join(fa['ground_nets']) or 'none'} (patterns {', '.join(fa['ground_patterns'])}), not fitted: "
          f"{', '.join(f'{r} ({w_})' for r, w_ in fa['not_fitted'].items()) or 'none'}, jumpers: "
          f"{', '.join(f'{r} {s}' for r, s in fa['jumpers'].items()) or 'none'}.", ""]
    L += [f"- {t}" for t in RELIES_ON]
    L += ["", "Method: `scripts/netlist_check.py --screens` (its header lists the screens)."]
    return "\n".join(L) + "\n"


# ---- command line ----------------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Check a KiCad netlist against a hand-written intent file (groups of pins that must be exactly "
                    "one net; pins that must stay unconnected; every pin accounted for). With --self-test it also "
                    "proves that the check can fail.",
        epilog="Exit codes: 0 pass; 1 mismatches (or an uncaught planted defect, or names to review, or screen leads); "
               "2 could not run. Results go to --out (with --project: to the results folder, <board>/out/ or "
               "[project] out_dir). The intent file format is "
               "described at the top of this script and in templates/EXPECTED_CONNECTIVITY.md; the screens and their "
               "waiver file too.")
    ap.add_argument("netlist", nargs="?", help="netlist exported by KiCad (kicadsexpr)")
    ap.add_argument("intent", nargs="?", help="the hand-written intent file (TOML)")
    ap.add_argument("--project", metavar="BOARD_FOLDER", help="board folder; netlist and intent from their usual places")
    ap.add_argument("--out", metavar="FOLDER", help="folder for the results")
    ap.add_argument("--self-test", action="store_true", help="plant three defects in copies of the netlist; each must fail")
    ap.add_argument("--keep", metavar="FOLDER", help="with --self-test: keep the three defective copies there")
    ap.add_argument("--names", action="store_true", help="list net names that span sheets (no intent file needed)")
    ap.add_argument("--schematic", metavar="ROOT.kicad_sch", help="with --names: read the label kinds from the sheets")
    ap.add_argument("--declared", metavar="A,B", help="with --names: names confirmed to span sheets")
    ap.add_argument("--pins", action="store_true", help="only write the per-part pin tables (no intent file needed)")
    ap.add_argument("--screens", action="store_true",
                    help="four screens that need no intent file (a two-pin part shorted out; a supply pin fed only through "
                         "capacitors; a rail fed only through an open or unfitted link; a net with one pin): leads for the "
                         "reviewer, not verdicts")
    ap.add_argument("--waivers", metavar="FILE", help="with --screens: waivers, each with a written reason (TOML, [[waive]])")
    ap.add_argument("--ground", metavar="A,B", help="with --screens: net-name patterns of the ground nets (replace the "
                                                     "defaults " + ", ".join(GROUND_DEFAULT) + ")")
    a = ap.parse_args(argv)

    netlist, intent_path, out = a.netlist, a.intent, a.out
    declared = [d.strip() for d in (a.declared or "").split(",") if d.strip()]
    waivers_path, ground = a.waivers, [g.strip() for g in (a.ground or "").split(",") if g.strip()]
    if a.screens and (a.names or a.pins or a.self_test):
        print("CANNOT RUN: --screens is a listing of its own: give it without --names, --pins or --self-test", file=sys.stderr)
        return 2
    if a.project:
        cfg_all = kicad_io.load_settings(a.project)
        cfg = cfg_all.get("netlist_check", {})
        files = kicad_io.project_files(a.project, cfg_all)
        out = out or files["out"]
        netlist = netlist or (os.path.join(a.project, cfg["netlist"]) if cfg.get("netlist")
                              else os.path.join(files["out"], "netlist.net"))      # the results folder: [project] out_dir
        intent_path = intent_path or os.path.join(a.project, cfg.get("intent", os.path.join("src", "expected_connectivity.toml")))
        declared += [str(x) for x in cfg_all.get("schematic", {}).get("global_nets", [])]
        if not waivers_path:
            named = cfg.get("screen_waivers")
            path = os.path.join(a.project, named or SCREEN_WAIVERS_DEFAULT)
            if named or os.path.isfile(path):
                waivers_path = path
        ground = ground or [str(x) for x in cfg.get("screen_ground", [])]
    if not netlist:
        print("CANNOT RUN: give the netlist (and the intent file) with --out FOLDER, or --project BOARD_FOLDER",
              file=sys.stderr)
        return 2
    if not out:
        print("CANNOT RUN: give --out FOLDER for the results (or --project)", file=sys.stderr)
        return 2
    nl = kicad_io.read_netlist(netlist)
    if a.screens:
        waivers = read_waivers(waivers_path) if waivers_path else []
    os.makedirs(out, exist_ok=True)
    head = {"file": _show(netlist, out), "sha256": kicad_io.sha256(netlist), "tool": nl.tool}

    if a.screens:
        res = screen(nl, ground or list(GROUND_DEFAULT))
        wres = apply_waivers(res["findings"], waivers)
        wres["file"] = _show(waivers_path, out) if waivers_path else ""
        act = [f for f in res["findings"] if not f["waived"]]
        n_waived = len(res["findings"]) - len(act)
        rows = []
        for scr, title in SCREENS:
            mine = [f for f in res["findings"] if f["screen"] == scr]
            live = len([f for f in mine if not f["waived"]])
            st = res["status"][scr] or ((f"{live} lead(s)" if live else "nothing found")
                                        + (f", {len(mine) - live} waived" if len(mine) > live else ""))
            rows.append({"screen": scr, "title": title, "status": st, "leads": live, "waived": len(mine) - live})
        res.update({"script": "netlist_check.py --screens", "netlist": head, "result": "LEADS" if act else "NO LEADS",
                    "exit_code": 1 if act else 0, "screens": rows, "waivers": wres, "relies_on": RELIES_ON,
                    "counts": {"parts": len(nl.parts), "pins": len(nl.pins), "nets": len(nl.nets)}})
        kicad_io.atomic_write(os.path.join(out, "netlist_screens.md"), screens_md(res))
        kicad_io.atomic_write(os.path.join(out, "netlist_screens.json"), json.dumps(res, indent=2) + "\n")
        for f in res["findings"]:
            print(f"  {'WAIVED' if f['waived'] else 'LEAD':6} {f['id']}: {f['text']}"[:400])
        for n in res["not_checked"]:
            print(f"  NOT CHECKED ({n['screen']}): {n['text']}"[:400])
        for x in wres["not_applied"]:
            print(f"  WAIVER NOT APPLIED {x['finding']}: {x['why']}")
        for x in wres["stale"]:
            print(f"  WAIVER MATCHES NOTHING {x['finding']}")
        extra = (f" ({n_waived} more waived)" if n_waived else "") + \
            (f"; {len(res['not_checked'])} item(s) not checked" if res["not_checked"] else "")
        if act:
            print(f"LEADS: {len(act)} for the reviewer{extra}; leads, not verdicts")
        else:
            print(f"NO LEADS: the four screens found nothing{extra}; this is not a review of the connections")
        print("report:", os.path.join(out, "netlist_screens.md"))
        return res["exit_code"]

    if a.names:
        res = names_listing(nl, declared, a.schematic)
        res.update({"script": "netlist_check.py --names", "netlist": head, "exit_code": 1 if res["to_review"] else 0})
        kicad_io.atomic_write(os.path.join(out, "net_names.md"), names_md(res))
        kicad_io.atomic_write(os.path.join(out, "net_names.json"), json.dumps(res, indent=2) + "\n")
        for r in res["one_net_many_sheets"]:
            print(f"  {r['status']:8} {r['name']}: one net on {len(r['sheets'])} sheets, {r['pins']} pins ({r['how']})")
        for r in res["same_name_separate_nets"]:
            print(f"  {r['status']:8} {r['name']}: {len(r['nets'])} separate nets with this name")
        for d in res["declared_not_used"]:
            print(f"  REVIEW   {d}: declared, but it does not span sheets")
        print(("PASS" if not res["to_review"] else "FAIL") + f": {res['to_review']} name(s) to review")
        print("report:", os.path.join(out, "net_names.md"))
        return res["exit_code"]

    if a.pins:
        tables = pin_tables(nl)
        md = ["# Pin tables (a listing from the netlist, not a check)", "",
              f"- Netlist: `{head['file']}`, SHA-256 `{head['sha256']}`: {len(nl.parts)} parts, {len(nl.pins)} pins, "
              f"{len(nl.nets)} nets.",
              "- Parts with more than two pins, and two-pin parts whose pins have names. Hold each table against "
              "the datasheet pin table of the exact part number.", ""] + _pin_tables_md(tables)
        kicad_io.atomic_write(os.path.join(out, "pin_table.md"), "\n".join(md) + "\n")
        kicad_io.atomic_write(os.path.join(out, "pin_table.json"),
                              json.dumps({"script": "netlist_check.py --pins", "netlist": head, "parts": tables}, indent=2) + "\n")
        print(f"LISTING written (not a check): {len(tables)} parts in", os.path.join(out, "pin_table.md"))
        return 0

    if not intent_path:
        print("CANNOT RUN: no intent file given. Write it by hand from the circuit description and the datasheet "
              "pin tables (templates/EXPECTED_CONNECTIVITY.md); it must not be generated from the schematic.",
              file=sys.stderr)
        return 2
    intent = Intent(intent_path)
    res = check(nl, intent)
    res.update({"script": "netlist_check.py", "netlist": head,
                "intent": {"file": _show(intent_path, out), "sha256": kicad_io.sha256(intent_path)},
                "result": "PASS" if not res["mismatches"] else "FAIL", "pin_tables": pin_tables(nl)})
    code = 1 if res["mismatches"] else 0
    if a.self_test:
        st = self_test(netlist, nl, intent, res, a.keep)
        caught = len([s for s in st if s["caught"]])
        planted = len([s for s in st if s["got"] not in ("NOT PLANTED", "DOES NOT APPLY")])
        missing = len([s for s in st if s["got"] == "NOT PLANTED"])
        na = len([s for s in st if s["got"] == "DOES NOT APPLY"])
        res["self_test"] = st
        tail = f"; {na} defect does not apply to this design" if na else ""
        if caught < planted:
            res["self_test_result"] = (f"SELF-TEST FAIL: only {caught} of {planted} planted defects made the check "
                                       f"fail: the check is defective" + tail)
            code = 1
        elif missing or not planted:
            res["self_test_result"] = (f"SELF-TEST CANNOT RUN: {missing} of {len(st)} defects could not be planted "
                                       f"(the check itself must pass first)" + tail)
            code = code or 2
        else:
            res["self_test_result"] = f"SELF-TEST PASS: {caught} of {planted} planted defects made the check fail" + tail
    res["exit_code"] = code
    kicad_io.atomic_write(os.path.join(out, "connectivity_report.md"), report_md(res))
    kicad_io.atomic_write(os.path.join(out, "connectivity_report.json"), json.dumps(res, indent=2) + "\n")
    c = res["counts"]
    for m in res["mismatches"][:60]:
        print(f"  - {m['kind']}: {m['text']}")
    if len(res["mismatches"]) > 60:
        print(f"  ... {len(res['mismatches']) - 60} more in the report")
    print(f"{res['result']}: {len(res['mismatches'])} mismatches; {c['groups']} groups, {c['no_connect']} no-connect "
          f"pin(s), {c['pins_accounted']} of {c['pins']} pins accounted for, {c['parts']} parts")
    if a.self_test:
        for s in res["self_test"]:
            print(f"  self-test: {s['defect']} -> {s['got']}")
        print(res["self_test_result"])
    print("report:", os.path.join(out, "connectivity_report.md"))
    return code


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
