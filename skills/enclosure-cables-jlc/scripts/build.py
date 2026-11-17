"""One build command: runs the build steps of mech.toml in order, then the stale-file guard.

What it does
    Runs every `[[build.steps]]` of mech.toml in order and stops at the first failure. Then the guard: every expected
    output (the union of the steps' `outputs`, globs allowed) must exist, be newer than the start of this run, and be
    newer than every declared input (model files, interface.json, cables.json, [build] inputs). Each stale or missing
    file is listed; any of them is exit 1. Writes a build report (step, seconds, outputs with size and time) to
    `<out>/build/BUILD_REPORT.md` and `.json`, and the rows to `<out>/checks/build.json`.

Why it exists (the real failure, told without names)
    After a change, one old assembly file, old views and a second output folder stayed behind and were handed on as
    current; "where are the new files?" cost several rounds. One command that regenerates everything and refuses a file
    older than the model makes that impossible to miss.
    When an output is older than an input that a STEP of this very run rewrote (a step that writes `cables.json` after
    the steps that read it), the message names that input and the step, and says to move that step before the others:
    the guard cannot be satisfied by running again until the order is fixed. Such an input is judged by the END time of
    the step that wrote it, and the outputs of that same step are not reported against it: a step that writes a STEP file
    and then the JSON that records its checksum is first in the list and is not stale. Outputs of a step that ran
    AFTER the writer are current by definition. The windows (start and end of every step) of the last run are kept in
    `<out>/build/BUILD_REPORT.json`, so `--check-only` afterwards judges the same way and does not turn that step red again.
    When a step fails, the steps after it are not run, and their outputs are listed as "not run (an earlier step failed)":
    they are not judged, so they are not reported STALE.

Usage
    python -I build.py [--project <mech folder>] [--check-only] [--provisional] [--only step1,step2]
    --check-only    do not run the steps; only the guard (existence and age against the inputs; the "newer than this
                    run" test needs a run and is skipped)
    --provisional   mark the outputs: writes <out>/build/PROVISIONAL.txt listing them (a normal run removes it)
    A step's cmd is a list or a string. Placeholders: {python} this Python, {cq_python} the Python that has CadQuery,
    {scripts} the skill's scripts folder, {project} the mech folder. The step runs in the project folder with
    MECH_SCRIPTS set. Paths in outputs and inputs are relative to the project folder.

Config keys (mech.toml)
    [[build.steps]]  name = "model", cmd = ["{cq_python}", "-I", "{scripts}/fit_check.py"], outputs = ["out/checks/fit_check.json"],
                     timeout = 3600
    [build]  inputs = ["model/**/*.py", "interface.json", "cables/cables.json"]    (the default list; only existing files count)
    [paths]  out

Exit codes
    0 steps ran and every output is current   1 a step failed or a file is stale/missing   2 could not run (no steps, bad config)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import glob
import json
import os
import shlex
import subprocess
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

DEFAULT_INPUTS = ["model/**/*.py", "interface.json", "cables/cables.json"]
SLACK = 0.002          # seconds of file-time resolution tolerated


def expand(project: str, patterns) -> list[str]:
    out = []
    for p in patterns:
        full = p if os.path.isabs(p) else os.path.join(project, p)
        hits = glob.glob(full, recursive=True)
        out += [h for h in hits if os.path.isfile(h)]
    return sorted(set(os.path.normpath(h) for h in out))


def _fmt_cmd(cmd, project, cq_py):
    subs = {"{python}": sys.executable, "{cq_python}": cq_py or sys.executable, "{scripts}": _HERE, "{project}": project}

    def sub(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return s
    if isinstance(cmd, str):
        parts = shlex.split(cmd, posix=(os.name != "nt"))
        parts = [x[1:-1] if len(x) > 1 and x[0] == x[-1] == '"' else x for x in parts]
    else:
        parts = list(cmd)
    return [sub(str(x)) for x in parts]


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def writer_of(project: str, steps: list[dict], windows, path: str, mtime: float):
    """The step that wrote `path` during this run: the step that lists it in `outputs` (globs allowed), else the step whose
    run window (start, end) contains `mtime`. None when neither is found."""
    for st in steps:
        for pat in st.get("outputs", []):
            full = pat if os.path.isabs(pat) else os.path.join(project, pat)
            if _same_path(full, path) or (any(c in pat for c in "*?[") and path in [os.path.normpath(h) for h in glob.glob(full, recursive=True)]):
                return st["name"]
    for name, t0, t1 in windows or []:
        if t0 - SLACK <= mtime <= t1 + SLACK:
            return name
    return None


def guard(project: str, steps: list[dict], inputs: list[str], t_start: float | None, windows=None, not_run=(), last_start=None) -> list[dict]:
    """One dict per expected output: {path, exists, mtime, size, problems[]}. `windows` = [(step name, start, end)] of this run
    (used to name the step that rewrote an input, and to judge an output against that step's END time). `not_run` = names of
    the steps that were not run because an earlier one failed: their outputs are not judged (not_run = True, one problem line).
    With no run now (--check-only), `windows` and `last_start` are those of the last run (from BUILD_REPORT.json), and an input
    written during that run is judged the same way."""
    in_times = [(p, os.path.getmtime(p)) for p in inputs]
    order = [st["name"] for st in steps]
    ends = {name: t1 for name, _t0, t1 in windows or []}
    ref_start = t_start if t_start is not None else last_start
    ref_end = max(ends.values()) if ends else None
    when = "this run" if t_start is not None else "the last build"
    res = []
    for st in steps:
        pats = st.get("outputs", [])
        for pat in pats:
            full = pat if os.path.isabs(pat) else os.path.join(project, pat)
            if st["name"] in not_run:
                res.append({"step": st["name"], "path": os.path.normpath(full), "exists": None, "mtime": None, "size": None, "not_run": True,
                            "problems": ["not run (an earlier step failed)"]})
                continue
            hits = [h for h in glob.glob(full, recursive=True) if os.path.isfile(h)] if any(c in pat for c in "*?[") else ([full] if os.path.isfile(full) else [])
            if not hits:
                res.append({"step": st["name"], "path": os.path.normpath(full), "exists": False, "mtime": None, "size": None,
                            "problems": ["expected output does not exist"]})
                continue
            for h in hits:
                m = os.path.getmtime(h)
                pr = []
                if t_start is not None and m < t_start - SLACK:
                    pr.append("older than the start of this build (the step did not write it)")
                newer = [(p, t) for p, t in in_times if m < t - SLACK and not _same_path(p, h)]
                causes = []                                # (path, time, rewritten in this run?, writer step)
                for p, t in newer:
                    is_fresh = ref_start is not None and t >= ref_start - SLACK and (t_start is not None or (ref_end is not None and t <= ref_end + SLACK))
                    w = writer_of(project, steps, windows, p, t) if is_fresh else None
                    if w is not None and (w not in ends or w not in order):
                        w = None                           # a step that did not run (or is no longer in the list) cannot have written it
                    if w is not None:
                        if w == st["name"]:
                            continue                       # this very step wrote the input and the output: not its own staleness
                        if order.index(st["name"]) > order.index(w) or m >= ends[w] - SLACK:
                            continue                       # the output is newer than the step that wrote the input (or ran after it)
                    causes.append((p, t, is_fresh, w))
                if causes:
                    # an input rewritten during the run (after the run started) is the cause to name, with the step that wrote it
                    fresh = [c for c in causes if c[2]]
                    p, t, is_fresh, w = max(fresh or causes, key=lambda x: x[1])
                    rel = os.path.relpath(p, project)
                    if is_fresh:
                        who = f"rewritten during {when} by step '{w}'" if w else f"rewritten during {when} by a step that is not named in [[build.steps]]"
                        pr.append(f"older than the input {rel}, {who}: move that step before the others")
                    else:
                        pr.append(f"older than the input {rel}")
                res.append({"step": st["name"], "path": os.path.normpath(h), "exists": True, "mtime": m, "size": os.path.getsize(h), "problems": pr})
    return res


def load_last_run(path: str):
    """(start, windows) of the last run recorded in BUILD_REPORT.json: windows = [(step, start, end)]. (None, []) when there is none."""
    try:
        d = mc.load_json(path)
        return float(d["started"]), [(w["step"], float(w["start"]), float(w["end"])) for w in d.get("windows", [])]
    except (OSError, ValueError, KeyError, TypeError):
        return None, []


def _stamp(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else "-"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the build steps of mech.toml, then the stale-file guard.",
                                 epilog="Exit: 0 current, 1 failed or stale, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--provisional", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    cfg = job.cfg
    steps = cfg.get("build", {}).get("steps", [])
    if not isinstance(steps, list) or not steps:
        print("could not run: mech.toml has no [[build.steps]] (name, cmd, outputs)")
        return 2
    for i, s in enumerate(steps):
        if "name" not in s or ("cmd" not in s and not a.check_only):
            print(f"could not run: build step {i + 1} needs a name and a cmd")
            return 2
    if a.only:
        wanted = set(a.only.split(","))
        steps = [s for s in steps if s["name"] in wanted]
    declared = cfg.get("build", {}).get("inputs", DEFAULT_INPUTS)
    inputs = expand(job.project, declared)
    inputs += [p for p in (mc.path_of(cfg, "interface"), mc.path_of(cfg, "cables")) if os.path.isfile(p) and p not in inputs]
    inputs = sorted(set(os.path.normpath(p) for p in inputs))
    rows = mc.Rows()
    report = []
    windows = []
    not_run = []
    t_start = None
    if not a.check_only:
        cq_py = mc.find_cadquery_python(cfg)
        env = dict(os.environ, MECH_SCRIPTS=_HERE, PYTHONDONTWRITEBYTECODE="1")
        t_start = time.time()
        for n, st in enumerate(steps, 1):
            cmd = _fmt_cmd(st["cmd"], job.project, cq_py)
            print(f"[{n}/{len(steps)}] {st['name']}: {' '.join(cmd)}", flush=True)
            t0 = time.time()
            try:
                r = subprocess.run(cmd, cwd=job.project, env=env, timeout=float(st.get("timeout", 3600)), stdin=subprocess.DEVNULL)
                rc = r.returncode
            except subprocess.TimeoutExpired:
                rc = -9
            except OSError as e:
                print("could not start:", e)
                rc = -1
            dt = time.time() - t0
            windows.append((st["name"], t0, t0 + dt))
            report.append({"step": st["name"], "seconds": round(dt, 1), "returncode": rc})
            ok = rc in (0,) or (rc in st.get("ok_codes", []))
            rows.add(f"BLD-{n:02d}", "build", f"step {st['name']}", f"exit {rc}, {dt:.1f} s", "exit 0", "pass" if ok else "fail")
            if not ok:
                print(f"STOP: step '{st['name']}' failed (exit {rc}); later steps were not run")
                for m, s2 in enumerate(steps[n:], n + 1):
                    rows.add(f"BLD-{m:02d}", "build", f"step {s2['name']}", "not run", "a step before it failed", "could_not_run")
                    not_run.append(s2["name"])
                break
    out_build = os.path.join(job.out, "build")
    last_start = None
    if a.check_only:
        last_start, windows = load_last_run(os.path.join(out_build, "BUILD_REPORT.json"))      # judge by the last run's windows
    g = guard(job.project, steps, inputs, t_start, windows, not_run, last_start)
    stale = 0
    for i, x in enumerate(g, 1):
        rel = os.path.relpath(x["path"], job.project)
        if x.get("not_run"):                       # the step never ran: not stale, not judged
            rows.add(f"OUT-{i:03d}", "outputs", rel, "not run (an earlier step failed)", "exists, newer than this run and than every input", "could_not_run")
            print(f"not run: {rel} (an earlier step failed)")
            continue
        bad = bool(x["problems"])
        stale += bad
        rows.add(f"OUT-{i:03d}", "outputs", rel, "ok, " + f"{x['size']} bytes, {_stamp(x['mtime'])}" if not bad else "; ".join(x["problems"]),
                 "exists, newer than this run and than every input", "fail" if bad else "pass")
        if bad:
            print(f"STALE: {rel}: {'; '.join(x['problems'])}")
    md = ["# Build report", "", f"Project `{job.project}`, {_stamp(time.time())}" + (", provisional" if a.provisional else ""), "",
          "| Step | Seconds | Exit |", "|---|---|---|"] + [f"| {r['step']} | {r['seconds']} | {r['returncode']} |" for r in report] + \
         ["", "| Output | Step | Size | Written | Problem |", "|---|---|---|---|---|"] + \
         [f"| {os.path.relpath(x['path'], job.project)} | {x['step']} | {x['size'] if x['size'] is not None else '-'} | {_stamp(x['mtime'])} | {'; '.join(x['problems']) or '-'} |" for x in g] + \
         ["", f"Inputs ({len(inputs)}): " + ", ".join(os.path.relpath(p, job.project) for p in inputs[:40])]
    mc.atomic_write(os.path.join(out_build, "BUILD_REPORT.md"), "\n".join(md) + "\n")
    mc.atomic_write(os.path.join(out_build, "BUILD_REPORT.json"), json.dumps(
        {"steps": report, "outputs": g, "inputs": inputs, "started": t_start if t_start is not None else last_start,
         "windows": [{"step": n, "start": t0, "end": t1} for n, t0, t1 in windows]}, indent=1))
    prov = os.path.join(out_build, "PROVISIONAL.txt")
    if a.provisional:
        mc.atomic_write(prov, "PROVISIONAL build " + _stamp(time.time()) + ": these outputs are not frozen.\n" + "\n".join(x["path"] for x in g) + "\n")
    elif not a.check_only and os.path.isfile(prov):
        os.remove(prov)
    rows.write(job.out, "build.py", inputs)
    print(rows.headline())
    if rows.counts()["fail"] or stale:
        return 1
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
