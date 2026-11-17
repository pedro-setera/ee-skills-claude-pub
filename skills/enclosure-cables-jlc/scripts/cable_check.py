"""Checks the cable data file alone, and against the board's pin-out when a netlist is given.

What it does
    Reads `cables/cables.json` and writes one row per check and cable:
      ENDS    ends are named P1, P2, P3 ...; every wire starts and ends at a known end
      CODES   every housing, plug and jack has its `mpn` and `supplier_code`, and every housing's terminal too: none empty,
              none a placeholder ("TBD", "UNKNOWN", "n/a" ...); `wire_code` / `cable_code` / `bom_extra` codes, when given,
              are not placeholders either. A drawing with a blank code cannot be quoted, so this row blocks the stage.
      AWG     every wire's gauge is inside its terminal's range at both ends
      CAV     every housing position is either wired or listed EMPTY; no position used twice; none beyond the housing;
              wires + empty positions = positions of the housing
      LEN     ONE length per cable (no per-wire lengths), a length definition, and a tolerance that is not tighter than
              the supplier's standard
      LABEL   label text present and short
      SPEC    rf and ethernet cables have the cable written out in words (`cable_spec`)
      NONDEF  every stock default of the supplier (capability sheet `[[stock_defaults]]`) is either listed in
              `non_defaults` as want / not, or accepted in `accept_defaults`
      ROWS    housings with more than one row carry the numbering words and a picture
      ANGLE   angled plugs (`angled = true`, or a right-angle / 90 degree part) carry an orientation text, a coded `exit`
              (left, right, up, down: the drawing sketch is made from it) and a picture file that exists
      EXTRA   no loose extras in a cable order
      TEXT    no question mark, "please", "if possible", alternatives or names from the deny list in any text; and the
              words "board", "PCB" and "module" in a cable's `name` or `label` (they reach the supplier: End A/B, P1/P2
              and part numbers only, never the name of a part of the product)
      NET     (with --netlist) each wire joins the same net at both ends, two wires are not swapped, housings are keyed,
              the housing has as many positions as the board connector has pins
    --netlist takes a CSV with the columns connector,pin,net (exported from the electronics side). An end is tied to its
    board connector by `"mates": "J2"` in cables.json; a position maps to the pin of the same number unless the end has
    `"pin_map": {"1": "A1"}`.

Why it exists (the real failure, told without names)
    A harness was drawn by the supplier with a wire in a cavity that had to stay empty, another with a gauge outside
    the crimp's range, and a tolerance tighter than standard was silently drawn at the standard value. Each of these was
    decidable from the cable data before anything was sent. A later set of cable data passed every row with "TBD" in
    each supplier code and with a right-angle plug that had no exit direction; a harness named after the board it plugs
    into reached the supplier in the title block. All three are decided here now.

Usage
    python -I cable_check.py [--project <mech folder>] [--out <folder>] [--cables cables.json] [--netlist pins.csv]
                             [--sheet suppliers/<id>.capability.toml] [--only CAB-01]

Config keys (mech.toml)
    [cables] file, supplier, sheet, tol_mm, label_max_chars, show_signals, deny      [project] name (added to the deny list)

Exit codes
    0 all rows pass   1 a row failed   2 could not run (no cable file) or a row could not run (no capability sheet)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import csv
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import cable_common as cc  # noqa: E402

EXITS = ("left", "right", "up", "down")        # the coded exit directions cable_drawings.py can draw
ANGLED_RX = re.compile(r"\b90\s*(?:deg|degree|\u00b0)|right[- ]angle|\bangled\b|\belbow\b", re.I)
TIGHT_TEXT = "the supplier draws its standard tolerance silently; design for it"


def is_angled(end: dict) -> bool:
    if "angled" in end:
        return bool(end["angled"])
    p = end.get("part") or {}
    return bool(ANGLED_RX.search(" ".join(str(p.get(k, "")) for k in ("mpn", "description"))))


def _picture_ok(pic: str, base: str) -> bool:
    return bool(pic) and os.path.isfile(pic if os.path.isabs(pic) else os.path.join(base, pic))


def read_netlist(path: str) -> dict:
    """{connector: {pin: net}} from a CSV connector,pin,net (header optional, ';' or ',')."""
    out: dict = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        text = f.read()
    delim = ";" if text.count(";") > text.count(",") else ","
    for row in csv.reader(text.splitlines(), delimiter=delim):
        row = [c.strip() for c in row]
        if len(row) < 3 or not row[0] or row[0].startswith("#"):
            continue
        if row[0].lower() in ("connector", "ref", "reference") and row[1].lower() in ("pin", "pad", "position"):
            continue
        out.setdefault(row[0], {})[row[1]] = row[2]
    return out


def check_cable(c: dict, rows: mc.Rows, cfg: dict, cap, std_tol, deny, base: str, netlist=None) -> None:
    cid = str(c.get("id", "?"))
    sec = f"cable {cid}"

    def add(code, check, value, rule, ok, verdict=None):
        rows.add(f"{cid}-{code}", sec, check, value, rule, verdict or ("pass" if ok else "fail"))

    ends = c.get("ends") or []
    wires = c.get("wires") or []
    kind = c.get("type", "other")

    # ---- ENDS
    bad = []
    ids = [e.get("id") for e in ends]
    if len(ends) < 2:
        bad.append("fewer than 2 ends")
    for i in ids:
        if not re.fullmatch(r"P[1-9]\d?", str(i or "")):
            bad.append(f"end named '{i}'")
    if len(set(ids)) != len(ids):
        bad.append("an end id is used twice")
    for w in wires:
        for side in ("from", "to"):
            e, pos = cc.split_ref(w.get(side, ""))
            if e not in ids:
                bad.append(f"wire {w.get('from')} -> {w.get('to')}: unknown end '{e}'")
            elif pos is None:
                bad.append(f"wire {w.get('from')} -> {w.get('to')}: no position at {side}")
    if not str(c.get("name", "")).strip():
        bad.append("no name")
    if not isinstance(c.get("qty"), int) or c.get("qty", 0) < 1:
        bad.append("qty is not a whole number >= 1")
    add("ENDS", "ends and wire references", "; ".join(bad) or f"{len(ends)} ends, {len(wires)} wires", "ends P1, P2 ...; every wire end known", not bad)

    # ---- CODES
    bad, n = [], 0
    for e in ends:
        if e.get("kind") not in ("housing", "plug", "jack"):
            continue
        eid, p = e.get("id"), e.get("part") or {}
        for key in ("mpn", "supplier_code"):
            n += 1
            why = cc.code_problem(p.get(key))
            if why:
                bad.append(f"{eid} part.{key} {why}")
        if e.get("kind") == "housing":
            t = e.get("terminal") or {}
            for key in ("mpn", "supplier_code"):
                n += 1
                why = cc.code_problem(t.get(key))
                if why:
                    bad.append(f"{eid} terminal.{key} {why}" if t else f"{eid}: the housing has no terminal (terminal.{key} {why})")
    for key in ("wire_code", "cable_code"):
        if str(c.get(key, "") or "").strip():
            n += 1
            why = cc.code_problem(c.get(key))
            if why:
                bad.append(f"{key} {why}")
    for i, x in enumerate(c.get("bom_extra") or []):
        if str(x.get("supplier_code", "") or "").strip():
            n += 1
            why = cc.code_problem(x.get("supplier_code"))
            if why:
                bad.append(f"bom_extra[{i}].supplier_code {why}")
    if n or bad:
        add("CODES", "part numbers and supplier codes filled in", "; ".join(bad) or f"{n} code(s) present, none a placeholder",
            "every housing, plug, jack and terminal has its mpn and supplier_code: not empty, not TBD / UNKNOWN / n/a", not bad)
    else:
        add("CODES", "part numbers and supplier codes filled in", "no housing, plug or jack on this cable", "mpn and supplier_code of every part", True, "na")

    # ---- AWG
    if wires or kind == "harness":
        bad, n = [], 0
        for w in wires:
            awg = w.get("awg")
            if not isinstance(awg, (int, float)):
                bad.append(f"wire {w.get('from')} -> {w.get('to')}: no AWG")
                continue
            for side in ("from", "to"):
                e = cc.end_of(c, cc.split_ref(w.get(side, ""))[0])
                if not e or e.get("kind") != "housing":
                    continue
                t = e.get("terminal") or {}
                if not isinstance(t.get("awg_min"), (int, float)) or not isinstance(t.get("awg_max"), (int, float)):
                    bad.append(f"{e.get('id')}: the terminal has no AWG range")
                    continue
                lo, hi = sorted((t["awg_min"], t["awg_max"]))
                n += 1
                if not lo <= awg <= hi:
                    bad.append(f"wire {w.get(side)} is {awg:g} AWG, terminal {t.get('mpn', '')} takes {lo:g}-{hi:g} AWG")
        if kind == "harness" and not wires:
            bad.append("a harness without wires")
        add("AWG", "wire gauge against each terminal's range", "; ".join(dict.fromkeys(bad)) or f"{n} wire ends inside the range",
            "AWG inside the terminal's range at both ends", not bad)
    else:
        add("AWG", "wire gauge against each terminal's range", "no single wires", "AWG inside the terminal's range", True, "na")

    # ---- CAV
    bad, seen = [], 0
    for e in ends:
        if e.get("kind") != "housing":
            if e.get("kind") == "tinned":
                at = cc.wires_at(c, e.get("id"))
                for pos, ws in at.items():
                    if len(ws) > 1:
                        bad.append(f"{e['id']} lead {pos} used {len(ws)} times")
                if not isinstance(e.get("tin_mm"), (int, float)):
                    bad.append(f"{e['id']}: tinned end without tin_mm")
            continue
        n = cc.end_positions(e)
        if n < 1:
            bad.append(f"{e.get('id')}: housing without part.positions")
            continue
        seen += 1
        at = cc.wires_at(c, e.get("id"))
        empty = cc.empty_positions(e)
        for pos, ws in sorted(at.items(), key=lambda kv: str(kv[0])):
            if not isinstance(pos, int) or pos < 1 or pos > n:
                bad.append(f"{e['id']} position {pos} is not in 1..{n}")
            if len(ws) > 1:
                bad.append(f"{e['id']} position {pos} used {len(ws)} times")
            if pos in empty:
                bad.append(f"{e['id']} position {pos} is wired AND listed EMPTY")
        for pos in empty:
            if pos < 1 or pos > n:
                bad.append(f"{e['id']} EMPTY position {pos} is not in 1..{n}")
        for pos in range(1, n + 1):
            if pos not in at and pos not in empty:
                bad.append(f"{e['id']} position {pos} is neither wired nor listed EMPTY")
        used = len([p for p in at if isinstance(p, int) and 1 <= p <= n])
        if used + len(set(empty)) != n and not any(b.startswith(e["id"]) for b in bad):
            bad.append(f"{e['id']}: {used} wires + {len(set(empty))} EMPTY is not {n} positions")
    if seen or bad:
        add("CAV", "housing positions: wired or EMPTY, none twice", "; ".join(bad) or f"{seen} housing(s) complete",
            "every position wired or listed EMPTY; no position used twice", not bad)
    else:
        add("CAV", "housing positions: wired or EMPTY, none twice", "no multi-position housing", "every position accounted for", True, "na")

    # ---- LEN
    bad = []
    L = c.get("length_mm")
    if not isinstance(L, (int, float)) or L <= 0:
        bad.append("no length_mm")
    elif abs(L - round(L)) > 1e-9:
        bad.append(f"length {L} is not a whole mm")
    per = [w for w in wires if any(k in w for k in ("length_mm", "length", "len_mm"))]
    if per:
        bad.append(f"{len(per)} wire(s) carry their own length: one length per cable (the longest wire's)")
    if not str(c.get("length_def", "")).strip():
        bad.append("no length_def (what the length spans)")
    add("LEN", "one length per cable", "; ".join(bad) or f"{cc.fmt(L)} mm, {c.get('length_def')}",
        "one length_mm (whole mm) with its definition; no per-wire lengths", not bad)
    tol = c.get("tol_mm")
    if not isinstance(tol, (int, float)) or tol <= 0:
        add("TOL", "length tolerance", "no tol_mm", f"+-{std_tol[0]:g} mm or wider ({std_tol[1]})", False)
    elif tol < std_tol[0] - 1e-9:
        add("TOL", "length tolerance", f"+-{tol:g} mm is tighter than the standard +-{std_tol[0]:g} mm: {TIGHT_TEXT}",
            f"not tighter than +-{std_tol[0]:g} mm ({std_tol[1]})", False)
    else:
        add("TOL", "length tolerance", f"+-{tol:g} mm", f"not tighter than +-{std_tol[0]:g} mm ({std_tol[1]})", True)

    # ---- LABEL
    lab = str(c.get("label", "")).strip()
    mx = int(cfg["label_max_chars"])
    bad = []
    if not lab:
        bad.append("no label text")
    elif len(lab) > mx:
        bad.append(f"label '{lab}' has {len(lab)} characters")
    if lab and "\n" in lab:
        bad.append("label has a line break")
    add("LABEL", "label text", "; ".join(bad) or f"'{lab}'", f"present, one line, at most {mx} characters", not bad)

    # ---- SPEC
    if kind in ("rf", "ethernet"):
        spec = str(c.get("cable_spec", "")).strip()
        add("SPEC", "cable written out in words", spec or "no cable_spec", "rf / ethernet cables name the exact cable (type, diameter, jacket)",
            len(spec) >= 10)
    else:
        add("SPEC", "cable written out in words", "harness: the wire is in the form fields", "rf / ethernet only", True, "na")

    # ---- NONDEF
    nds = c.get("non_defaults") or []
    bad = [f"entry {i + 1} has no 'want' or no 'not'" for i, nd in enumerate(nds)
           if not str(nd.get("want", "")).strip() or not str(nd.get("not", "")).strip()]
    if cap is None:
        add("NONDEF", "supplier stock defaults covered", "no capability sheet: the supplier's stock defaults are unknown",
            "every stock default is in non_defaults (want / not) or in accept_defaults", False, "could_not_run")
    else:
        sd = [d for d in (cap.get("stock_defaults") or []) if kind in (d.get("applies") or [kind])]
        have = {str(nd.get("item", "")).strip().lower() for nd in nds}
        acc = {str(a).strip().lower() for a in (c.get("accept_defaults") or [])}
        for d in sd:
            it = str(d.get("item", "")).strip().lower()
            if it == "tolerance":
                continue                       # the TOL row decides it
            if it not in have and it not in acc:
                bad.append(f"stock default '{d.get('item')}' ({d.get('default')}) is neither in non_defaults nor in accept_defaults")
        add("NONDEF", "supplier stock defaults covered", "; ".join(bad) or f"{len(sd)} stock default(s) of the sheet covered, {len(nds)} non-default(s) written",
            "every stock default is in non_defaults (item, want, not) or in accept_defaults", not bad)

    # ---- ROWS / ANGLE
    multi = [e for e in ends if cc.end_rows(e) > 1]
    if multi:
        bad = []
        for e in multi:
            if len(str((e.get("part") or {}).get("numbering", "")).strip()) < 10:
                bad.append(f"{e['id']}: no numbering words")
            if not _picture_ok(e.get("picture", ""), base):
                bad.append(f"{e['id']}: no pin-map picture file")
        add("ROWS", "multi-row housing: numbering words and picture", "; ".join(bad) or f"{len(multi)} housing(s) with words and picture",
            "words such as 'pin 2 is NEXT TO pin 1, other row' and a picture", not bad)
    else:
        add("ROWS", "multi-row housing: numbering words and picture", "no multi-row housing", "words and a picture", True, "na")
    ang = [e for e in ends if is_angled(e)]
    if ang:
        bad = []
        for e in ang:
            if len(str(e.get("orientation", "")).strip()) < 5:
                bad.append(f"{e['id']}: no orientation text")
            ex = str(e.get("exit", "") or "").strip().lower()
            if not ex:
                bad.append(f"{e['id']}: no exit direction (exit = {' | '.join(EXITS)})")
            elif ex not in EXITS:
                bad.append(f"{e['id']}: exit '{e.get('exit')}' is not one of {', '.join(EXITS)}")
            if not _picture_ok(e.get("picture", ""), base):
                bad.append(f"{e['id']}: no orientation picture file")
        add("ANGLE", "angled plug: orientation, exit direction and picture", "; ".join(bad) or f"{len(ang)} angled end(s) with orientation, exit and picture",
            "which way the cable leaves, in words, a coded exit (left, right, up, down) and a picture file that exists", not bad)
    else:
        add("ANGLE", "angled plug: orientation and picture", "no angled plug", "orientation and a picture", True, "na")

    # ---- EXTRA
    ex = c.get("extras") or c.get("loose") or []
    add("EXTRA", "no loose extras", f"{len(ex)} extra item(s): buy them in the parts order" if ex else "none",
        "a cable order holds cables only; loose parts come back fitted", not ex)

    # ---- TEXT
    bad = []
    for where, text in cc.supplier_texts(c, bool(cfg["show_signals"])):
        for f in cc.text_findings(text, deny):
            bad.append(f"{where}: {f}")
        if where in ("name", "label"):            # both reach the supplier (title block, form item name, label): P1/P2, End A/B, part numbers only
            for f in cc.product_word_findings(text):
                bad.append(f"{where}: {f}")
    add("TEXT", "texts free of questions, requests and names", "; ".join(bad) or "clean",
        "no question mark, please, if possible, alternatives, loose extras, deny-list names; no 'board', 'PCB' or 'module' in the name or label", not bad)

    # ---- NET
    if netlist is not None:
        bad, n, na = [], 0, 0
        nets = {}
        for w in wires:
            pair = []
            for side in ("from", "to"):
                eid, pos = cc.split_ref(w.get(side, ""))
                e = cc.end_of(c, eid) or {}
                ref = e.get("mates")
                if not ref:
                    pair.append(None)
                    continue
                pin = str((e.get("pin_map") or {}).get(str(pos), pos))
                if ref not in netlist:
                    bad.append(f"{eid} mates {ref}: not in the netlist")
                    pair.append(None)
                elif pin not in netlist[ref]:
                    bad.append(f"{w.get(side)}: {ref} has no pin {pin} in the netlist")
                    pair.append(None)
                else:
                    pair.append(netlist[ref][pin])
            nets[(w.get("from"), w.get("to"))] = pair
        swapped = set()
        keys = list(nets)
        for i in range(len(keys)):
            a = nets[keys[i]]
            if None in a or a[0] == a[1]:
                continue
            for j in range(i + 1, len(keys)):
                b = nets[keys[j]]
                if None not in b and a[0] == b[1] and a[1] == b[0]:
                    swapped.update((keys[i], keys[j]))
                    bad.append(f"wires {keys[i][0]} and {keys[j][0]} are SWAPPED: {a[0]} / {a[1]}")
        for k, pair in nets.items():
            if None in pair:
                na += 1
                continue
            n += 1
            if pair[0] != pair[1] and k not in swapped:
                bad.append(f"wire {k[0]} -> {k[1]} joins net {pair[0]} to net {pair[1]}")
        if n == 0 and not bad:
            add("NET", "wires against the board netlist", "no wire has a board connector at both ends (\"mates\")", "same net at both ends", True, "na")
        else:
            add("NET", "wires against the board netlist", "; ".join(dict.fromkeys(bad)) or f"{n} wire(s) join the same net at both ends"
                + (f", {na} with one end off the boards" if na else ""), "same net at both ends; no two wires swapped", not bad)
        bad, n = [], 0
        for e in ends:
            ref = e.get("mates")
            if not ref or e.get("kind") != "housing":
                continue
            n += 1
            if not (e.get("part") or {}).get("keyed"):
                bad.append(f"{e['id']} ({ref}): the housing is not marked keyed (part.keyed = true once checked on the datasheet)")
            if ref in netlist and len(netlist[ref]) != cc.end_positions(e):
                bad.append(f"{e['id']}: {cc.end_positions(e)} positions, {ref} has {len(netlist[ref])} pins in the netlist")
        if n:
            add("KEY", "housings keyed and as large as the board connector", "; ".join(bad) or f"{n} housing(s) keyed, pin counts equal",
                "keyed housing; positions = pins of the mating connector", not bad)
        else:
            add("KEY", "housings keyed and as large as the board connector", "no housing mates a board connector", "keyed housing", True, "na")


def run(job, args) -> mc.Rows:
    rows = mc.Rows()
    data, path = cc.load_cables(job, getattr(args, "cables", None))
    cfg = cc.cable_cfg(job)
    cap, cap_path = cc.capability(job, getattr(args, "sheet", None))
    std = cc.standard_tolerance(cap, cfg)
    deny = list(cfg.get("deny") or [])
    pname = str(job.cfg["project"].get("name", "")).strip()
    if pname:
        deny.append(pname)
    netlist = None
    inputs = [path] + ([cap_path] if cap else [])
    if getattr(args, "netlist", None):
        if not os.path.isfile(args.netlist):
            raise mc.MechError(f"no netlist at {args.netlist}")
        netlist = read_netlist(args.netlist)
        inputs.append(args.netlist)
    ids = [c.get("id") for c in data["cables"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    badid = [i for i in ids if not i or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", str(i))]
    rows.add("FILE-IDS", "file", "cable ids", (f"used twice: {dup}; " if dup else "") + (f"not usable as a part number: {badid}" if badid else "")
             or f"{len(ids)} cables, ids unique", "every cable has its own id (letters, digits, - _ .)", "fail" if dup or badid or not ids else "pass")
    for c in data["cables"]:
        if getattr(args, "only", None) and c.get("id") != args.only:
            continue
        check_cable(c, rows, cfg, cap, std, deny, os.path.dirname(path), netlist)
    rows._inputs = inputs
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Checks cables.json alone and against a board netlist.",
                                 epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--cables", help="the cable data file (default [cables] file)")
    ap.add_argument("--netlist", help="CSV connector,pin,net from the electronics side")
    ap.add_argument("--sheet", help="capability sheet of the cable supplier")
    ap.add_argument("--only", help="check one cable id")
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
        rows = run(job, a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(job.out, "cable_check.py", rows._inputs)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
