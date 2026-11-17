"""Compare two KiCad netlists: are they the same circuit, pin for pin?

What it checks (NEW against REFERENCE)
    1. the same set of references;
    2. per reference: the same value, footprint, part-number fields (default LCSC and MPN), DNP state,
       "not in BOM" and "not on board" state;
    3. per pin: the same pin name, and the same electrical type;
    4. the nets as sets of pins: every net joins exactly the same pins;
    5. the net names, for nets the designer named (a label or a supply symbol). Names are compared without their
       sheet path, because a redraw may regroup the sheets: '/Buck/BOOT' and '/Power/BOOT' are both 'BOOT'.

Why it exists
    A schematic was drawn a second time, as a readable wired drawing, after the board had been ordered from the
    first one. A redraw is only worth anything if it is provably the same circuit: one swapped pin in the new
    drawing and a technician measures at the wrong place, or the next board revision is built from a circuit that
    never existed. The same question comes up when a schematic is cleaned up, re-annotated, moved to other
    libraries or imported from another tool. "It looks the same" is not a result; this comparison is.

It reads netlists exported by KiCad from any project, whoever drew it (hierarchical sheets, labels, supply
symbols, parts with several units, designs without part-number fields):
    kicad-cli sch export netlist --format kicadsexpr -o netlist.net <root>.kicad_sch
(scripts/schematic/export.py does that.)

Usage
    python -I scripts/netlist_compare.py NEW.net REFERENCE.net --out FOLDER [options]
    python -I scripts/netlist_compare.py --project hardware/<board> [options]

    --ignore-names       do not compare net names (check 5); the pin sets still decide
    --full-names         compare net names with their sheet path
    --ignore-pin-types   do not compare the electrical type of pins (two symbol libraries may differ there)
    --fields A,B         the part-number fields to compare (default LCSC,MPN; a field absent on both sides is equal;
                         give an empty string to compare none)
    --partial            NEW may hold fewer references (a redraw in progress): compare what it holds; the result
                         is then PARTIAL-IDENTICAL at best, and that counts as a pass

Results: FOLDER/netlist_compare.md and FOLDER/netlist_compare.json (with --project: the results folder, <board>/out/
or [project] out_dir).

board.toml keys (only with --project; all optional)
    [project] kicad_dir, out_dir  see kicad_io.py; the results folder is out_dir (default "out")
    [netlist_compare] new         the netlist under test (default "netlist.net" in the results folder)
    [netlist_compare] reference   the netlist to compare against (needed, unless given on the command line)
    [netlist_compare] fields      list of part-number fields (default ["LCSC", "MPN"])
    [netlist_compare] ignore_names, full_names, ignore_pin_types   true / false
    Paths are relative to the board folder.

Exit codes
    0  IDENTICAL (with --partial also PARTIAL-IDENTICAL)
    1  DIFFERENT: the differences are listed
    2  the comparison could not run (a file is missing or is not a KiCad netlist, no --out)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
from kicad_io import Netlist, is_named, leaf  # noqa: E402

DEFAULT_FIELDS = ("LCSC", "MPN")


def _pin_key(p: tuple) -> tuple:
    return (p[0], len(p[1]), p[1])


def _pins_text(pins) -> str:
    return ", ".join(f"{r}.{p}" for r, p in sorted(pins, key=_pin_key))


def compare(new: Netlist, ref: Netlist, *, partial: bool = False, fields=DEFAULT_FIELDS, names: str = "leaf",
            pin_types: bool = True) -> tuple[list[dict], dict]:
    """The differences (each {"check": 1..5, "text": ...}) and the counts. names: 'leaf', 'full' or 'none'."""
    diffs: list[dict] = []

    def add(check: int, text: str) -> None:
        diffs.append({"check": check, "text": text})

    new_refs, ref_refs = set(new.parts), set(ref.parts)
    extra, missing = sorted(new_refs - ref_refs), sorted(ref_refs - new_refs)
    if extra:
        add(1, f"references only in NEW: {', '.join(extra)}")
    if missing and not partial:
        add(1, f"references only in REFERENCE: {', '.join(missing)}")
    common = sorted(new_refs & ref_refs)

    # 2. part data
    for r in common:
        a, b = new.parts[r], ref.parts[r]
        pairs: list[tuple[str, object, object]] = [("value", a.value, b.value), ("footprint", a.footprint, b.footprint)]
        pairs += [(f"field {f}", a.fields.get(f, ""), b.fields.get(f, "")) for f in fields]
        pairs += [("DNP", a.dnp, b.dnp), ("not in BOM", a.exclude_from_bom, b.exclude_from_bom),
                  ("not on board", a.exclude_from_board, b.exclude_from_board)]
        for what, x, y in pairs:
            if x != y:
                add(2, f"{r}: {what} is {x!r} in NEW, {y!r} in REFERENCE")

    # 3. pins of the common references
    cset = set(common)
    new_pins = {k for k in new.pins if k[0] in cset}
    ref_pins = {k for k in ref.pins if k[0] in cset}
    for k in sorted(ref_pins - new_pins, key=_pin_key):
        add(3, f"pin {k[0]}.{k[1]} is missing in NEW")
    for k in sorted(new_pins - ref_pins, key=_pin_key):
        add(3, f"pin {k[0]}.{k[1]} is not in REFERENCE")
    both = new_pins & ref_pins
    for k in sorted(both, key=_pin_key):
        _, f1, t1 = new.pins[k]
        _, f2, t2 = ref.pins[k]
        if f1 != f2:
            add(3, f"pin {k[0]}.{k[1]}: name {f1!r} in NEW, {f2!r} in REFERENCE")
        if pin_types and t1 != t2:
            add(3, f"pin {k[0]}.{k[1]}: type {t1!r} in NEW, {t2!r} in REFERENCE")

    # 4. the nets as pin sets (cut down to the pins both sides have)
    def groups(nl: Netlist) -> dict:
        out = {}
        for name, nodes in nl.nets.items():
            g = frozenset(n for n in nodes if n in both)
            if g:
                out[g] = name
        return out

    ref_groups, new_groups = groups(ref), groups(new)
    for g, name in sorted(ref_groups.items(), key=lambda kv: kv[1]):
        if g not in new_groups:
            where = sorted({new.pins[n][0] for n in g})
            add(4, f"REFERENCE net {name} joins [{_pins_text(g)}]; in NEW these pins are on: {', '.join(where)}")
    for g, name in sorted(new_groups.items(), key=lambda kv: kv[1]):
        if g not in ref_groups:
            where = sorted({ref.pins[n][0] for n in g})
            add(4, f"NEW net {name} joins [{_pins_text(g)}]; in REFERENCE these pins are on: {', '.join(where)}")

    # 5. names of the nets that match as pin sets
    named = 0
    if names != "none":
        show = (lambda s: s) if names == "full" else leaf
        for g, name in sorted(ref_groups.items(), key=lambda kv: kv[1]):
            if g not in new_groups:
                continue
            other = new_groups[g]
            if not is_named(name) and not is_named(other):
                continue                                    # both names are KiCad's own: nothing to compare
            named += 1
            if show(other) != show(name):
                add(5, f"net {show(name)} of REFERENCE is called {show(other)} in NEW ([{_pins_text(g)}])")

    counts = {"refs_new": len(new_refs), "refs_reference": len(ref_refs), "refs_common": len(common),
              "pins_new": len(new.pins), "pins_reference": len(ref.pins), "pins_compared": len(both),
              "nets_new": len(new.nets), "nets_reference": len(ref.nets), "nets_compared": len(ref_groups),
              "names_compared": named}
    return diffs, counts


def verdict(diffs: list, counts: dict, partial: bool) -> str:
    if diffs:
        return "DIFFERENT"
    full = (counts["refs_new"] == counts["refs_reference"] == counts["refs_common"]
            and counts["pins_compared"] == counts["pins_reference"] == counts["pins_new"])
    if full:
        return "IDENTICAL"
    return "PARTIAL-IDENTICAL" if partial else "DIFFERENT"


def _show_path(path: str, base: str) -> str:
    """A path for the report: relative to the report folder when it is near, else the file name alone (a report
    must not carry a user's folder names)."""
    try:
        rel = os.path.relpath(os.path.abspath(path), base).replace("\\", "/")
    except ValueError:
        return os.path.basename(path)
    return rel if rel.count("../") <= 3 else os.path.basename(path)


CHECKS = {1: "References (the same set)", 2: "Part data (value, footprint, part-number fields, DNP, not in BOM, not on board)",
          3: "Pins (present, name, type)", 4: "Nets as pin sets", 5: "Net names"}


def report_md(res: dict) -> str:
    c, o = res["counts"], res["options"]
    L = ["# Netlist compare", "", f"**Result: {res['result']}**" + (" (counts as a pass: --partial)"
                                                                    if res["result"] == "PARTIAL-IDENTICAL" else ""), "",
         "| | NEW | REFERENCE |", "|---|---|---|",
         f"| File | `{res['new']['file']}` | `{res['reference']['file']}` |",
         f"| SHA-256 | `{res['new']['sha256']}` | `{res['reference']['sha256']}` |",
         f"| Made by | {res['new']['tool'] or '-'} | {res['reference']['tool'] or '-'} |",
         f"| References | {c['refs_new']} | {c['refs_reference']} |",
         f"| Pins | {c['pins_new']} | {c['pins_reference']} |",
         f"| Nets (single-pin nets included) | {c['nets_new']} | {c['nets_reference']} |", "",
         "| # | Check | Compared | Result |", "|---|---|---|---|"]
    per = {k: [d for d in res["differences"] if d["check"] == k] for k in CHECKS}
    amount = {1: f"{c['refs_new']} against {c['refs_reference']}", 2: f"{c['refs_common']} references",
              3: f"{c['pins_compared']} of {c['pins_reference']} pins", 4: f"{c['nets_compared']} nets",
              5: f"{c['names_compared']} named nets"}
    for k, title in CHECKS.items():
        if k == 5 and o["names"] == "none":
            L.append(f"| 5 | {title} | - | NOT CHECKED (--ignore-names) |")
            continue
        t = title
        if k == 2:
            t = (f"Part data (value, footprint, fields {', '.join(o['fields']) or 'none'}, DNP, not in BOM, "
                 f"not on board)")
        if k == 3 and not o["pin_types"]:
            t = "Pins (present, name; type NOT CHECKED: --ignore-pin-types)"
        if k == 5:
            t = "Net names (" + ("with sheet path" if o["names"] == "full" else "without sheet path") + ")"
        L.append(f"| {k} | {t} | {amount[k]} | {'PASS' if not per[k] else f'**FAIL** ({len(per[k])})'} |")
    L.append("")
    if res["result"] == "PARTIAL-IDENTICAL":
        L += ["NEW holds fewer references than REFERENCE. The checks cover the pins NEW contains (each net of "
              "REFERENCE cut down to these pins). This is not a full comparison.", ""]
    if res["differences"]:
        L += [f"## Differences ({len(res['differences'])})", ""]
        L += [f"- [{d['check']}] {d['text']}" for d in res["differences"]]
        L.append("")
    L += ["## Not checked", "",
          "- The drawing itself: sheets, positions, wires, texts, symbol graphics.",
          "- Fields other than those named above; datasheet links; descriptions.",
          "- Whether a footprint's pads fit the part: the footprint NAME is compared, not its geometry.",
          "- Whether either circuit is right: two netlists with the same mistake are identical. The independent "
          "check is `netlist_check.py` against the hand-written intent file.", ""]
    L.append("Method: `scripts/netlist_compare.py` (its header lists the five checks).")
    return "\n".join(L) + "\n"


def run(new_path: str, ref_path: str, out: str, *, partial=False, fields=DEFAULT_FIELDS, names="leaf",
        pin_types=True, quiet=False) -> tuple[int, dict]:
    new, ref = kicad_io.read_netlist(new_path), kicad_io.read_netlist(ref_path)
    diffs, counts = compare(new, ref, partial=partial, fields=fields, names=names, pin_types=pin_types)
    v = verdict(diffs, counts, partial)
    os.makedirs(out, exist_ok=True)
    res: dict = {"script": "netlist_compare.py", "result": v,
           "new": {"file": _show_path(new_path, out), "sha256": kicad_io.sha256(new_path), "tool": new.tool},
           "reference": {"file": _show_path(ref_path, out), "sha256": kicad_io.sha256(ref_path), "tool": ref.tool},
           "options": {"partial": partial, "fields": list(fields), "names": names, "pin_types": pin_types},
           "counts": counts, "differences": diffs}
    code = 0 if v == "IDENTICAL" or (partial and v == "PARTIAL-IDENTICAL") else 1
    res["exit_code"] = code
    kicad_io.atomic_write(os.path.join(out, "netlist_compare.md"), report_md(res))
    kicad_io.atomic_write(os.path.join(out, "netlist_compare.json"), json.dumps(res, indent=2) + "\n")
    if not quiet:
        for d in diffs[:60]:
            print(f"  - [{d['check']}] {d['text']}")
        if len(diffs) > 60:
            print(f"  ... {len(diffs) - 60} more in the report")
        print(f"references {counts['refs_new']}/{counts['refs_reference']}, pins compared {counts['pins_compared']}"
              f"/{counts['pins_reference']}, nets compared {counts['nets_compared']} (named {counts['names_compared']}), "
              f"differences {len(diffs)}")
        print(("PASS " if code == 0 else "FAIL ") + v)
        print("report:", os.path.join(out, "netlist_compare.md"))
    return code, res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Compare two KiCad netlists (kicadsexpr): references, part data, pins, nets as pin sets, net "
                    "names. Prints IDENTICAL or DIFFERENT with the list of differences.",
        epilog="Exit codes: 0 identical; 1 different; 2 could not run. Results: netlist_compare.md and "
               "netlist_compare.json in --out (with --project: in the results folder, <board>/out/ or [project] "
               "out_dir).")
    ap.add_argument("new", nargs="?", help="the netlist under test")
    ap.add_argument("reference", nargs="?", help="the netlist to compare against")
    ap.add_argument("--project", metavar="BOARD_FOLDER", help="board folder with board.toml; results go to its results "
                                                              "folder (out/ or [project] out_dir)")
    ap.add_argument("--out", metavar="FOLDER", help="folder for the results")
    ap.add_argument("--ignore-names", action="store_true", help="do not compare net names")
    ap.add_argument("--full-names", action="store_true", help="compare net names with their sheet path")
    ap.add_argument("--ignore-pin-types", action="store_true", help="do not compare the electrical type of pins")
    ap.add_argument("--fields", metavar="A,B", help="part-number fields to compare (default LCSC,MPN; '' for none)")
    ap.add_argument("--partial", action="store_true", help="NEW may hold fewer references than REFERENCE")
    a = ap.parse_args(argv)

    cfg: dict = {}
    new_path, ref_path, out = a.new, a.reference, a.out
    if a.project:
        settings = kicad_io.load_settings(a.project)
        cfg = settings.get("netlist_compare", {})
        files = kicad_io.project_files(a.project, settings)
        out = out or files["out"]
        if new_path and not ref_path:                       # one path with --project: it is the reference
            new_path, ref_path = None, new_path
        new_path = new_path or (os.path.join(a.project, cfg["new"]) if cfg.get("new")
                                else os.path.join(files["out"], "netlist.net"))      # the results folder: [project] out_dir
        if not ref_path and cfg.get("reference"):
            ref_path = os.path.join(a.project, cfg["reference"])
    if not new_path or not ref_path:
        print("CANNOT RUN: give NEW.net and REFERENCE.net with --out FOLDER, or --project with a reference "
              "(on the command line or as [netlist_compare] reference in board.toml)", file=sys.stderr)
        return 2
    if not out:
        print("CANNOT RUN: give --out FOLDER for the results (or --project)", file=sys.stderr)
        return 2
    if a.fields is not None:
        fields = tuple(f.strip() for f in a.fields.split(",") if f.strip())
    else:
        fields = tuple(cfg.get("fields", DEFAULT_FIELDS))
    names = "none" if (a.ignore_names or cfg.get("ignore_names")) else (
        "full" if (a.full_names or cfg.get("full_names")) else "leaf")
    pin_types = not (a.ignore_pin_types or cfg.get("ignore_pin_types"))
    code, _ = run(new_path, ref_path, out, partial=a.partial, fields=fields, names=names, pin_types=pin_types)
    return code


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
