"""Design-rule check of a KiCad board with schematic parity and all severities, on a private copy.

What it does
    Copies the KiCad project to a private folder, runs `kicad-cli pcb drc --schematic-parity --severity-all` on
    the copy, and writes KiCad's own report (drc.json) and a summary (drc_summary.txt, drc_summary.json): errors,
    warnings, unconnected items, schematic-parity items, with the board's checksum, the KiCad version and the
    rule file. Any of them fails the check. It also proves three things that KiCad does not tell:
      - that the custom rule file (<board>.kicad_dru) was loaded. KiCad drops the WHOLE file without a word when
        one rule has a syntax error and then reports a clean board. The proof is a second run on another copy
        whose rule file has a canary rule added at its end: the canary must fire.
      - that schematic parity really ran (without a schematic beside the board KiCad reports "0" parity items).
      - which checks the project has switched off ("ignore" in the violation severities): they are listed as
        not checked.
      - which footprints the rule file exempts from a rule by name (`!B.memberOfFootprint('U7')`), above all from
        the rule "no via in an SMD pad" (allowed only for thermal vias inside an exposed thermal pad, as the
        maker's drawing shows them). Each is listed with the reason that board.toml gives, or as "no reason
        written", so that a reviewer sees every exemption.

Why it exists (real failures, told without names)
    - A board passed DRC while two pads of the schematic were not on it: parity had not been run.
    - A rule check was run with errors only; the warnings held a courtyard overlap that became a part that could
      not be fitted.
    - A custom rule file with one misplaced comment silently lost every rule. Nothing in the report showed it.
    - A tool once loaded a board in place while another was writing it; hence the copy.
    A clean DRC is necessary and never sufficient: it is not a review.

Usage
    python -I drc_run.py --project <hardware/board folder>        results in <project>/out/
    python -I drc_run.py <board.kicad_pcb> --out <folder>         any KiCad board; results in <folder>
    options: --no-parity (a board without a schematic, a panel: parity is then listed as not checked),
             --timeout S (one kicad-cli run, default 900)

    The design folder is never written to. kicad-cli judges the copper zones as they are saved and never fills
    them itself, and KiCad 9 reports no saved fill that lies too near the board edge: a zone fill that was
    saved before a rule existed can lie too close to the edge in the file and in the Gerbers while this check is
    clean. Fill and save before the export (layout/fill.py), and measure the exported Gerbers (edge_check.py).

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [drc]
    parity    = true              # false: as --no-parity
    timeout_s = 900
    [drc.via_in_pad_exempt]       # footprints that the rule file exempts from "via hole to SMD pad", with the reason
    U7 = "exposed pad with the maker's 3 x 3 thermal vias, 0.3 mm drill (datasheet page 31)"
    [[drc.accept]]                # a warning the user has accepted in writing; errors cannot be accepted here
    type     = "lib_footprint_mismatch"       # KiCad's violation type
    contains = "J3"                           # text that the violation's description or items must contain
    reason   = "footprint edited on purpose: longer pads for hand soldering"
    approved = "user, YYYY-MM-DD"

Exit codes
    0  PASS: no error, no warning (or only accepted ones), nothing unconnected, parity clean, rule file proven
    1  FAIL: any of them, or a rule file that KiCad did not load
    2  CANNOT RUN: KiCad not found, unreadable board, kicad-cli failed, parity could not run (no schematic or
       not fully annotated) although it was asked for. Never a pass.

Not checked (the summary says so too): the conditions of custom rules (a rule with a mistyped condition never
fires: prove each rule once on a copy that contains the defect); anything set to "ignore" in the project;
the saved zone fill and the exported Gerbers (edge_check.py measures those).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402

TIMEOUT = 900.0
MAX_LISTED = 60                     # detail lines per group in the text summary; the JSON holds everything
CANARY = ('\n(rule "drc_run canary 1: the rule file was loaded"\n  (severity error)\n'
          '  (constraint hole_size (min 1000mm)))\n'
          '(rule "drc_run canary 2: the rule file was loaded"\n  (severity error)\n'
          '  (constraint track_width (min 1000mm)))\n')
_CANARY_HIT = re.compile(r"1000\.0+ mm")
# checks that should be errors on a board that goes to assembly; listed when the project has them lower
WANT_ERROR = ("courtyards_overlap", "missing_courtyard", "pth_inside_courtyard", "npth_inside_courtyard",
              "starved_thermal", "copper_sliver", "silk_overlap", "silk_over_copper", "text_height",
              "text_thickness", "track_width", "clearance", "hole_clearance", "copper_edge_clearance",
              "annular_width", "drill_out_of_range", "via_dangling", "track_dangling", "unconnected_items",
              "shorting_items", "tracks_crossing", "footprint_symbol_mismatch", "net_conflict", "missing_footprint",
              "extra_footprint", "duplicate_footprints")


def rule_file_faults(text: str) -> list[str]:
    """Faults that make KiCad drop a custom rule file: found by reading it, before KiCad is asked."""
    faults = []
    depth, in_str, first = 0, False, None
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not in_str and (not stripped or stripped.startswith("#")):
            continue
        if first is None:
            first = stripped
        i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == "\\":
                    i += 1
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    faults.append(f"line {n}: a ')' too many")
                    depth = 0
            elif ch == "#":
                faults.append(f"line {n}: a '#' comment after a rule on the same line (a comment must stand on "
                              "its own line)")
                break
            i += 1
    if first is None:
        faults.append("the file holds no rule")
    elif not re.match(r"\(\s*version\s+\d+\s*\)", first):
        faults.append("the first entry is not (version 1)")
    if in_str:
        faults.append("a text in quotes is not closed")
    if depth > 0:
        faults.append(f"{depth} '(' not closed")
    return faults


_RULE = re.compile(r'\(\s*rule\s+"((?:[^"\\]|\\.)*)"')
_MEMBER = re.compile(r"(!\s*)?[AB]\.memberOfFootprint\(\s*'([^']*)'\s*\)")


def rule_exemptions(text: str) -> list[dict]:
    """Footprints that a rule file takes out of a rule by name: every memberOfFootprint('...') that stands under a
    "not". Returns [{"rule": name, "pattern": text, "via_in_pad": bool}]. A reading aid for reviewers, not a
    parser of the rule language."""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    body = "\n".join(lines)
    out = []
    starts = [(m.start(), m.group(1)) for m in _RULE.finditer(body)]
    for i, (pos, name) in enumerate(starts):
        block = body[pos:starts[i + 1][0] if i + 1 < len(starts) else len(body)]
        via_rule = bool(re.search(r"physical_hole_clearance|hole_clearance", block)) and "'Via'" in block \
            and "'SMD'" in block
        for cond in re.findall(r'\(\s*condition\s+"((?:[^"\\]|\\.)*)"', block):
            for m in _MEMBER.finditer(cond):
                before = cond[:m.start()]
                negated = bool(m.group(1)) or before.count("!(") > 0 and before.count("(") > before.count(")")
                if negated:
                    out.append({"rule": name, "pattern": m.group(2), "via_in_pad": via_rule})
    return out


def _items(v: dict) -> str:
    out = []
    for i in v.get("items", []):
        pos = i.get("pos") or {}
        where = f" @({pos.get('x', 0):.3f}, {pos.get('y', 0):.3f})" if pos else ""
        out.append(f"{i.get('description', '')}{where}")
    return "; ".join(out)


def _line(group: str, v: dict) -> str:
    return f"{group} {v.get('type', '')} | {v.get('description', '')} | {_items(v)}"[:400]


def _accepted(v: dict, accept: list[dict]) -> dict | None:
    if v.get("severity") != "warning":
        return None
    text = (v.get("description", "") + " " + _items(v)).lower()
    for a in accept:
        if a.get("type") == v.get("type") and str(a.get("contains", "")).lower() in text \
                and str(a.get("reason", "")).strip():
            return a
    return None


def run(board: str, out: str, parity: bool, accept: list[dict], timeout: float, note: str,
        exempt_reasons: dict | None = None) -> dict:
    """Run the check. Returns the summary dictionary (also written as drc_summary.json)."""
    kc = kicad_io.require_kicad()
    src_dir = os.path.dirname(os.path.abspath(board))
    stem = os.path.splitext(os.path.basename(board))[0]
    res: dict = {"check": "drc_run", "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                 "board": os.path.basename(board), "board_sha256": kicad_io.sha256(board),
                 "kicad_version": kc.version, "settings": note, "not_checked": [], "cannot_run": []}
    if kc.note:
        res["not_checked"].append(kc.note)
    with kicad_io.private_tmp("drc-run-") as tmp:
        copy_dir = os.path.join(tmp, "project")
        kicad_io.copy_project(src_dir, copy_dir)
        copy = os.path.join(copy_dir, os.path.basename(board))
        sch = os.path.join(copy_dir, stem + ".kicad_sch")
        dru = os.path.join(copy_dir, stem + ".kicad_dru")
        pro = os.path.join(copy_dir, stem + ".kicad_pro")
        if parity and not os.path.isfile(sch):
            res["cannot_run"].append(f"schematic parity: no schematic {stem}.kicad_sch beside the board (give "
                                     "--no-parity to check the board alone)")
            parity = False
        res["parity_ran"] = parity
        report = os.path.join(tmp, "drc.json")
        args = ["pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", report]
        if parity:
            args.insert(2, "--schematic-parity")
        # the custom rule file: read it, and prepare a second copy with a canary rule at its end
        rule: dict = {"file": None, "sha256": None, "loaded": None, "faults": []}
        can_report = os.path.join(tmp, "canary.json")
        can_board = None
        if os.path.isfile(dru):
            with open(dru, encoding="utf-8", errors="replace") as f:
                text = f.read()
            rule.update(file=stem + ".kicad_dru", sha256=kicad_io.sha256(dru), faults=rule_file_faults(text))
            rule["exemptions"] = rule_exemptions(text)
            can_dir = os.path.join(tmp, "canary")
            os.makedirs(can_dir)
            for ext in (".kicad_pcb", ".kicad_pro"):
                if os.path.isfile(os.path.join(copy_dir, stem + ext)):
                    shutil.copyfile(os.path.join(copy_dir, stem + ext), os.path.join(can_dir, stem + ext))
            with open(os.path.join(can_dir, stem + ".kicad_dru"), "w", encoding="utf-8", newline="\n") as f:
                f.write(text.rstrip("\n") + "\n" + CANARY)
            can_board = os.path.join(can_dir, stem + ".kicad_pcb")
        # the check and the canary proof are two independent processes on two copies: run them at once
        with ThreadPoolExecutor(max_workers=2) as ex:
            main_run = ex.submit(kicad_io.run_cli, args + [copy], timeout)
            can_run = ex.submit(kicad_io.run_cli, ["pcb", "drc", "--severity-error", "--format", "json", "--units",
                                                    "mm", "-o", can_report, can_board], timeout) if can_board else None
            r = main_run.result()
            if can_run is not None:
                can_run.result()
        said = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        if not os.path.isfile(report):
            raise kicad_io.CliError(f"kicad-cli wrote no DRC report (exit {r.returncode}): {said[-600:]}")
        with open(report, encoding="utf-8") as f:
            data = json.load(f)
        if parity and not re.search(r"Found \d+ schematic parity", said):
            why = "KiCad could not read the schematic's netlist"
            if "annotated" in said:
                why += " (parity needs a fully annotated schematic)"
            res["cannot_run"].append(f"schematic parity: {why}")
            res["parity_ran"] = False
        os.makedirs(out, exist_ok=True)
        kicad_io.atomic_copy(report, os.path.join(out, "drc.json"))

        # did KiCad load the custom rule file? The canary rule must have fired.
        if can_board:
            fired = False
            if os.path.isfile(can_report):
                with open(can_report, encoding="utf-8") as f:
                    fired = any(_CANARY_HIT.search(v.get("description", "")) for v in json.load(f).get("violations", []))
            if fired:
                rule["loaded"] = True
            else:
                has_items = bool(re.search(r"\(\s*(segment|via|arc)\b|\(drill\b", open(copy, encoding="utf-8",
                                                                                         errors="replace").read()))
                rule["loaded"] = False if (has_items or rule["faults"]) else None
        res["rule_file"] = rule
        reasons = {str(k): str(v) for k, v in (exempt_reasons or {}).items()}
        found = rule.get("exemptions", [])
        via = sorted({e["pattern"] for e in found if e["via_in_pad"]})
        res["exemptions"] = {
            "via_in_pad": [{"footprint": p, "reason": reasons.get(p)} for p in via],
            "other_rules": [{"rule": r, "footprint": p} for r, p in dict.fromkeys(
                (e["rule"], e["pattern"]) for e in found if not e["via_in_pad"])],
            "listed_but_not_in_rule_file": sorted(k for k in reasons if k not in via),
        }

        ignored, lower = [], []
        if os.path.isfile(pro):
            try:
                with open(pro, encoding="utf-8") as f:
                    sev = json.load(f).get("board", {}).get("design_settings", {}).get("rule_severities", {})
            except (OSError, ValueError):
                sev = {}
                res["not_checked"].append("the project file could not be read: its violation severities are unknown")
            ignored = sorted(k for k, v in sev.items() if v == "ignore")
            lower = sorted(k for k in WANT_ERROR if sev.get(k) == "warning")
        else:
            res["not_checked"].append("no project file beside the board: KiCad's default severities and board "
                                      "setup were used")
        res["ignored_checks"] = ignored
        res["checks_only_warning"] = lower

    viol = data.get("violations", [])
    errors = [v for v in viol if v.get("severity") == "error"]
    warnings: list[dict] = []
    accepted: list[dict] = []
    for v in viol:
        if v.get("severity") == "warning":
            a = _accepted(v, accept)
            (accepted if a else warnings).append(dict(v, accepted_reason=a.get("reason"), approved=a.get("approved"))
                                                 if a else v)
    exclusions = [v for v in viol if v.get("severity") not in ("error", "warning")]
    unconnected = data.get("unconnected_items", [])
    par = data.get("schematic_parity", []) if res["parity_ran"] else []
    res["counts"] = {"errors": len(errors), "warnings": len(warnings), "accepted_warnings": len(accepted),
                     "unconnected": len(unconnected), "parity": len(par) if res["parity_ran"] else None,
                     "exclusions": len(exclusions)}
    res["by_type"] = {f"{sev} {t}": n for (sev, t), n in sorted(Counter(
        (v.get("severity", "?"), v.get("type", "?")) for v in viol + unconnected + par).items())}
    rule = res["rule_file"]
    rule_fail = rule["file"] is not None and rule["loaded"] is False
    findings = len(errors) + len(warnings) + len(unconnected) + len(par) + (1 if rule_fail else 0)
    if rule["file"] is None:
        res["not_checked"].append("no custom rule file (.kicad_dru): only KiCad's board-setup constraints were checked")
    elif rule["loaded"] is None:
        res["not_checked"].append("that the custom rule file was loaded could not be proven (the board has no "
                                  "track and no hole for the canary rule)")
    else:
        res["not_checked"].append("the conditions of the custom rules: a rule with a mistyped condition never "
                                  "fires; prove each rule once on a copy with the defect")
    if not parity and not any(c.startswith("schematic parity") for c in res["cannot_run"]):
        res["not_checked"].append("schematic parity (switched off: --no-parity or board.toml)")
    if ignored:
        res["not_checked"].append("checks set to 'ignore' in the project file: " + ", ".join(ignored))
    if exclusions:
        res["not_checked"].append(f"{len(exclusions)} violation(s) excluded in the project file: each needs a "
                                  "written waiver")
    res["not_checked"] += ["whether the saved zone fill is up to date: kicad-cli judges the fill as it is saved and "
                           "never fills (fill and save first, then measure the exported Gerbers with edge_check.py)",
                           "the exported Gerbers"]
    res["result"] = "FAIL" if findings else ("CANNOT RUN" if res["cannot_run"] else "PASS")
    res["details"] = {"errors": errors, "warnings": warnings, "accepted_warnings": accepted,
                      "unconnected": unconnected, "parity": par, "exclusions": exclusions}
    return res


def summary_text(res: dict) -> str:
    c, rule = res["counts"], res["rule_file"]
    parity = "asked" if res["parity_ran"] else "NOT run"
    out = [f"DRC, all severities, schematic parity {parity}: {res['result']}",
           f"board: {res['board']}   SHA-256: {res['board_sha256']}",
           f"KiCad {res['kicad_version']}, run on a private copy, {res['date']}"]
    if rule["file"] is None:
        out.append("custom rule file: none")
    else:
        state = {True: "loaded (proven: a canary rule added to a second copy fired)",
                 False: "NOT LOADED: KiCad ignored every rule of this file without a message",
                 None: "loading not proven"}[rule["loaded"]]
        out.append(f"custom rule file: {rule['file']}   SHA-256: {rule['sha256']}   {state}")
        out += [f"   rule file fault: {f}" for f in rule["faults"]]
    out += [f"errors: {c['errors']}", f"warnings: {c['warnings']}", f"unconnected items: {c['unconnected']}",
            "schematic parity: " + (str(c["parity"]) if c["parity"] is not None else (
                "CANNOT RUN" if any(x.startswith("schematic parity") for x in res["cannot_run"])
                else "not checked (switched off)")),
            f"accepted warnings (board.toml, each with its reason): {c['accepted_warnings']}",
            f"exclusions stored in the project file: {c['exclusions']}"]
    out += [f"CANNOT RUN: {x}" for x in res["cannot_run"]]
    ex = res["exemptions"]
    if ex["via_in_pad"]:
        out.append('exempted in the rule file from "no via in an SMD pad" (allowed only for thermal vias inside an '
                   "exposed thermal pad, as the maker's drawing shows them):")
        out += [f"   - {e['footprint']}: " + (e["reason"] or "NO REASON WRITTEN in board.toml [drc.via_in_pad_exempt]")
                for e in ex["via_in_pad"]]
    else:
        out.append('exempted from "no via in an SMD pad": none')
    if ex["listed_but_not_in_rule_file"]:
        out.append("listed in board.toml [drc.via_in_pad_exempt] but not exempted in the rule file (the rule still "
                   "applies to them): " + ", ".join(ex["listed_but_not_in_rule_file"]))
    if ex["other_rules"]:
        out.append("footprints named as exceptions in other rules: "
                   + "; ".join(f"{e['footprint']} in \"{e['rule']}\"" for e in ex["other_rules"]))
    if res["by_type"]:
        out.append("by type: " + ", ".join(f"{k} {n}" for k, n in res["by_type"].items()))
    if res["checks_only_warning"]:
        out.append("set to 'warning' in the project, error is advised (they still fail this run as warnings): "
                   + ", ".join(res["checks_only_warning"]))
    out.append("not checked:")
    out += [f"   - {x}" for x in res["not_checked"]]
    out.append(res["settings"])
    d = res["details"]
    for group, items in (("ERROR", d["errors"]), ("UNCONNECTED", d["unconnected"]), ("PARITY", d["parity"]),
                         ("WARNING", d["warnings"]), ("ACCEPTED", d["accepted_warnings"]),
                         ("EXCLUDED", d["exclusions"])):
        if items:
            out.append("")
        for v in items[:MAX_LISTED]:
            line = _line(group, v)
            if group == "ACCEPTED":
                line += f" | accepted: {v.get('accepted_reason')} ({v.get('approved') or 'no approval noted'})"
            out.append(line)
        if len(items) > MAX_LISTED:
            out.append(f"{group} ... and {len(items) - MAX_LISTED} more (all in drc.json)")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="KiCad DRC with schematic parity and all severities on a private copy; "
                                             "proves that the custom rule file was loaded. Exit 0 pass, 1 findings, "
                                             "2 could not run.")
    ap.add_argument("board", nargs="?", help="board file (.kicad_pcb); not needed with --project")
    ap.add_argument("--project", help="hardware/board folder (reads board.toml, writes into <project>/out/)")
    ap.add_argument("--out", help="results folder when no project folder is used")
    ap.add_argument("--no-parity", action="store_true", help="do not compare with the schematic (listed as not checked)")
    ap.add_argument("--timeout", type=float, help=f"seconds for one kicad-cli run (default {TIMEOUT:g})")
    a = ap.parse_args(argv)
    cfg: dict = {}
    if a.project:
        toml = kicad_io.load_settings(a.project)
        cfg = toml.get("drc", {})
        try:
            files = kicad_io.project_files(a.project, toml)
            board, out = a.board or files["pcb"], a.out or files["out"]
        except kicad_io.KicadIOError:
            if not a.board:                         # several boards in the project and none named: never guess
                raise
            board = a.board
            out = a.out or os.path.join(os.path.abspath(a.project), toml.get("project", {}).get("out_dir", "out"))
        note = "settings: " + ("board.toml" if toml else "no board.toml: defaults")
    else:
        if not a.board or not a.out:
            print("CANNOT RUN: give --project <board folder>, or a board file together with --out <folder>",
                  file=sys.stderr)
            return 2
        board, out = a.board, a.out
        note = "settings: no project folder: defaults and the command line"
    if not board or not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"board file not found: {board or '(none in the project folder)'}")
    design = os.path.normcase(os.path.dirname(os.path.abspath(board)))
    if (os.path.normcase(os.path.abspath(out)) + os.sep).startswith(design + os.sep):
        raise kicad_io.KicadIOError("the results folder lies inside the folder of the input design; a design that "
                                    "is only read is never written into: choose another folder with --out")
    parity = not a.no_parity and bool(cfg.get("parity", True))
    timeout = a.timeout if a.timeout is not None else float(cfg.get("timeout_s", TIMEOUT))
    accept = [x for x in cfg.get("accept", []) if isinstance(x, dict)]
    exempt = cfg.get("via_in_pad_exempt", {})
    exempt = exempt if isinstance(exempt, dict) else {str(x): "" for x in exempt}
    note += f"; parity {'on' if parity else 'off'}; time limit {timeout:g} s; accepted warnings listed: {len(accept)}"
    res = run(board, out, parity, accept, timeout, note, exempt)
    text = summary_text(res)
    kicad_io.atomic_write(os.path.join(out, "drc_summary.txt"), text)
    kicad_io.atomic_write(os.path.join(out, "drc_summary.json"), json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    head = text.split("\nnot checked:")[0]
    print(head)
    d = res["details"]
    for group, items in (("ERROR", d["errors"]), ("UNCONNECTED", d["unconnected"]), ("PARITY", d["parity"]),
                         ("WARNING", d["warnings"])):
        for v in items[:12]:
            print(_line(group, v))
        if len(items) > 12:
            print(f"{group} ... and {len(items) - 12} more")
    print(note)
    print(f"DRC: {res['result']} - {res['counts']['errors']} error(s), {res['counts']['warnings']} warning(s), "
          f"{res['counts']['unconnected']} unconnected, parity "
          f"{res['counts']['parity'] if res['counts']['parity'] is not None else 'not checked'}; summary "
          f"{os.path.join(out, 'drc_summary.txt')}")
    return {"PASS": 0, "FAIL": 1}.get(res["result"], 2)


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
