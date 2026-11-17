"""Merges the check files of every script into one CHECKS.md, with the headline counted apart.

What it does
    Reads `<out>/checks/*.json` (written by the other scripts: {"script","date","inputs":[{path,sha256}],"rows":[...]}),
    compares the recorded sha256 of every input with the file as it is now, and writes `<out>/CHECKS.md` grouped by
    section. A check file whose input changed (or vanished) after it was written is STALE and all its rows count as
    failed. Headline: passed N, failed N (stale ones included), could not run N, not applicable N, waived N, each
    counted apart.
    Waivers: `<project>/waivers.toml` (or --waivers FILE) lists the rows the user has accepted as named risks:
        [[waiver]]
        id = "HEAT-02"            # a row id, or a glob such as "PRT-OVH-*" (a bare "*" is refused)
        reason = "why this is accepted"
        who = "who accepted it"
        date = "2026-01-01"       # YYYY-MM-DD
    All four keys are required; a waiver without one is refused (exit 2, nothing written). A row that FAILED or COULD NOT
    RUN and whose id matches a waiver is printed "waived" with the reason, who and date, and counted apart ("waived N"):
    the exit code ignores it. A passing row, a not-applicable row and a STALE row are never waived (a stale result says
    nothing about the current files: run the check again, then waive what still fails). A waiver that matches no failed
    row is listed as unused. Nothing is waived unless that file says so.

Why it exists (the real failure, told without names)
    A passing result file from before a board change was still in the folder and was read as today's result. A check
    that cannot run was likewise counted as a pass in a summary line. Counting the four verdicts apart, and tying each
    result to the checksums of what it looked at, closes both. The opposite failure: two rows the user had accepted in
    writing as named risks stayed red in every later headline, so each gate summary listed them by hand; a machine-readable
    waiver (who, when, why) keeps them visible and counted apart without hiding them.

Usage
    python -I check_all.py [--project <mech folder>] [--out DIR] [--json] [--only script1,script2] [--waivers FILE]
    The CHECKS.md and a copy of the merged data (checks_merged.json) are written to the out folder.
    --waivers: the waiver file (default <project>/waivers.toml, used when it exists)

Config keys (mech.toml)
    [paths] out

Exit codes
    0 nothing failed, stale or could not run (waived rows do not count)   1 at least one failed or stale row
    2 only "could not run" rows, no check file found, or a waiver file that is not valid (a waiver without id, reason, who or date)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import datetime
import fnmatch
import glob
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

MARK = {"pass": "PASS", "fail": "FAIL", "could_not_run": "COULD NOT RUN", "na": "n/a", "stale": "STALE (counts as failed)", "waived": "WAIVED"}
WAIVER_KEYS = ("id", "reason", "who", "date")


def load_waivers(path: str) -> list[dict]:
    """The `[[waiver]]` entries of a waivers.toml: dicts with id, reason, who, date (strings). Raises MechError when the file is not
    valid TOML, an entry lacks one of the four keys or has it empty, the date is not YYYY-MM-DD, or an id is only wildcards."""
    doc = mc.load_toml(path)
    raw = doc.get("waiver", [])
    if not isinstance(raw, list):
        raise mc.MechError(f"{path}: use [[waiver]] tables (id, reason, who, date)")
    out = []
    for n, w in enumerate(raw, 1):
        if not isinstance(w, dict):
            raise mc.MechError(f"{path}: waiver {n} is not a table")
        label = f"waiver {n}" + (f" ({w['id']})" if w.get("id") else "")
        for k in WAIVER_KEYS:
            v = w.get(k)
            if isinstance(v, (datetime.date, datetime.datetime)):
                v = v.strftime("%Y-%m-%d")
            if not isinstance(v, str) or not v.strip():
                raise mc.MechError(f"{path}: {label} needs {k} (every waiver needs id, reason, who and date)")
            w = dict(w, **{k: v.strip()})
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", w["date"]):
            raise mc.MechError(f"{path}: {label}: date must be YYYY-MM-DD, not {w['date']!r}")
        if not w["id"].strip("*?"):
            raise mc.MechError(f"{path}: {label}: id {w['id']!r} would waive every row; name the rows (a row id, or a glob such as HEAT-*)")
        out.append({k: w[k] for k in WAIVER_KEYS})
    return out


def load_checks(out_dir: str, only=None) -> list[dict]:
    res = []
    for p in sorted(glob.glob(os.path.join(out_dir, "checks", "*.json"))):
        try:
            d = mc.load_json(p)
        except ValueError:
            res.append({"script": os.path.basename(p), "date": "", "inputs": [], "rows": [], "stale": ["the check file is not valid JSON"], "file": p})
            continue
        if only and d.get("script") not in only:
            continue
        stale = []
        for i in d.get("inputs", []):
            path, rec = i.get("path"), i.get("sha256")
            if rec is None:
                continue
            if not path or not os.path.isfile(path):
                stale.append(f"input missing now: {path}")
            elif mc.sha256(path) != rec:
                stale.append(f"input changed since the check ran: {path}")
        d["stale"], d["file"] = stale, p
        res.append(d)
    return res


def merge(checks: list[dict], waivers=()) -> tuple[list[dict], dict]:
    """Merge the rows of every check file. `waivers` (from load_waivers): a row that failed or could not run, in a current
    (not stale) check file, whose id matches a waiver's id (exact or glob) is shown "waived" and counted apart. Each waiver
    dict gets "matched" = the number of rows it waived."""
    rows, c = [], {"pass": 0, "fail": 0, "could_not_run": 0, "na": 0, "waived": 0}
    for w in waivers:
        w["matched"] = 0
    for d in checks:
        for r in d.get("rows", []):
            r = dict(r)
            r["script"] = d.get("script")
            r["stale"] = d["stale"]
            r["shown"] = "stale" if d["stale"] and r["verdict"] != "na" else r["verdict"]
            if r["shown"] in ("fail", "could_not_run"):
                w = next((w for w in waivers if fnmatch.fnmatchcase(str(r["id"]), w["id"])), None)
                if w:
                    w["matched"] += 1
                    r["waived"] = {k: w[k] for k in WAIVER_KEYS}
                    r["was"] = r["shown"]
                    r["shown"] = "waived"
            c["fail" if r["shown"] == "stale" else r["shown"]] += 1
            rows.append(r)
        if d["stale"] and not d.get("rows"):
            c["fail"] += 1
    return rows, c


def headline(c) -> str:
    return f"passed {c['pass']}, failed {c['fail']}, could not run {c['could_not_run']}, not applicable {c['na']}, waived {c['waived']}"


def render(checks, rows, c, waivers=()) -> str:
    L = ["# CHECKS", "", f"**Headline: {headline(c)}.**", "",
         "A check that could not run is not a pass. A check file older than its inputs is STALE and counts as failed. "
         "A row marked WAIVED failed or could not run and is accepted in waivers.toml (reason, who and date below); it is counted apart.", ""]
    L += ["| Script | Date | Inputs | State |", "|---|---|---|---|"]
    for d in checks:
        L.append(f"| {d.get('script')} | {d.get('date', '')} | {len(d.get('inputs', []))} | " + ("STALE: " + "; ".join(d["stale"]) if d["stale"] else "current") + " |")
    L.append("")
    secs = {}
    for r in rows:
        secs.setdefault(r["section"], []).append(r)
    for sec in sorted(secs):
        L += [f"## {sec}", "", "| ID | Check | Value | Rule | Verdict | Script |", "|---|---|---|---|---|---|"]
        for r in secs[sec]:
            cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
            mark = f"**{MARK[r['shown']]}**"
            if r["shown"] == "waived":
                w = r["waived"]
                mark += f" (was {MARK[r['was']]}): {w['reason']} -- {w['who']}, {w['date']}"
            L.append(f"| {cell(r['id'])} | {cell(r['check'])} | {cell(r['value'])} | {cell(r['rule'])} | {cell(mark)} | {r['script']} |")
        L.append("")
    if waivers:
        L += ["## Waivers", "", "| Row id | Rows waived | Reason | Who | Date |", "|---|---|---|---|---|"]
        for w in waivers:
            cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
            L.append(f"| {cell(w['id'])} | {w['matched']}" + ("" if w["matched"] else " (unused: no failed row has this id)") +
                     f" | {cell(w['reason'])} | {cell(w['who'])} | {w['date']} |")
        L.append("")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge out/checks/*.json into CHECKS.md.", epilog="Exit: 0 clean, 1 failed or stale, 2 could not run only.")
    mc.add_std_args(ap)
    ap.add_argument("--only")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--waivers", help="waiver file (default <project>/waivers.toml when it exists): [[waiver]] id, reason, who, date")
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
        wpath = a.waivers or os.path.join(job.project, "waivers.toml")
        if a.waivers and not os.path.isfile(wpath):
            raise mc.MechError(f"waiver file not found: {wpath}")
        waivers = load_waivers(wpath) if os.path.isfile(wpath) else []
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    checks = load_checks(job.out, set(a.only.split(",")) if a.only else None)
    if not checks:
        print(f"could not run: no check files in {os.path.join(job.out, 'checks')}; run the check scripts first")
        return 2
    rows, c = merge(checks, waivers)
    mc.atomic_write(os.path.join(job.out, "CHECKS.md"), render(checks, rows, c, waivers))
    mc.atomic_write(os.path.join(job.out, "checks_merged.json"), json.dumps({"counts": c, "waivers": waivers, "rows": rows}, indent=1))
    for r in rows:
        if r["shown"] in ("fail", "stale"):
            print(f"[{MARK[r['shown']]}] {r['script']} {r['id']} {r['check']}: {r['value']}")
        elif r["shown"] == "waived":
            w = r["waived"]
            print(f"[WAIVED] {r['script']} {r['id']} {r['check']}: {r['value']}  (was {MARK[r['was']]}; {w['reason']} -- {w['who']}, {w['date']})")
    for w in waivers:
        if not w["matched"]:
            print(f"note: waiver {w['id']} matches no failed or could-not-run row (unused)")
    print(f"{headline(c)}  -> {os.path.join(job.out, 'CHECKS.md')}")
    if c["fail"]:
        return 1
    return 2 if c["could_not_run"] else 0


if __name__ == "__main__":
    sys.exit(main())
