"""Environment check: which tools of the skill are present on this machine, and what does not work without each.

What it checks
    Core (the skill cannot produce or check a design without them):
        Python 3.11 or newer; KiCad's command line (kicad-cli); KiCad's own Python with the pcbnew module.
    Optional (each row says what is switched off without it):
        KiCad's symbol libraries, KiCad's global library tables (the user's own KiCad settings), ngspice, numpy,
        matplotlib, Pillow, CadQuery, easyeda2kicad, pdftoppm, curl.

Why it exists
    A session once worked for hours before finding that a needed tool was missing, and another reported a check
    as done that had never run. The check runs first in every session, so that a missing tool is said at once and
    its checks are reported as "cannot run" instead of being skipped silently. It installs nothing and uses no
    network: installing is the user's decision.

Usage (it is not a project script: it needs no argument)
    python -I scripts/env_check.py                 the table on the screen
    python -I scripts/env_check.py --json          the same as JSON on the screen
    python -I scripts/env_check.py --out FOLDER    also writes FOLDER/env_check.md and FOLDER/env_check.json
    python -I scripts/env_check.py --project hardware/<board>     the same into the board's results folder
                                                                  (<board>/out/, or board.toml [project] out_dir)

How tools are found
    KiCad: scripts/kicad_io.py (KICAD_BIN, the system path, the standard install places; the proven major version
        first). Every other install found is listed in the note of the KiCad row.
    numpy, matplotlib, Pillow: importable by this Python as the scripts are started (`python -I`), or in the
        user's own site-packages folder, which `python -I` hides (scripts reach it with kicad_io.add_user_site()).
        The versions inside KiCad's Python are shown too, because scripts that load a board run there.
    CadQuery: the interpreter named by the environment variable CADQUERY_PYTHON (CadQuery usually lives in its
        own environment), else this Python, else KiCad's Python.
    easyeda2kicad: the interpreter named by EASYEDA2KICAD_PYTHON, else an `easyeda2kicad` command on the system
        path, else this Python.
    ngspice: the shared library shipped with KiCad, or an `ngspice` command on the system path.
    pdftoppm, curl: the system path.

board.toml keys: only with --project, [project] out_dir (the results folder; default "out"). The folder needs no
KiCad project yet.

Exit codes
    0  every tool is present
    1  the core tools are present, at least one optional tool is missing
    2  a core tool is missing (or too old), or the check itself could not run (also: a board.toml that cannot be read)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import concurrent.futures
import datetime
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

MIN_PYTHON = (3, 11)
PROBE_TIMEOUT = 120.0       # s: one question to one tool


def _run(cmd, timeout=PROBE_TIMEOUT):
    """(exit code or None, stdout + stderr) of a short tool call; never waits longer than the timeout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)


def _row(name, kind, found, version="", where="", needed_for="", without="", note=""):
    return {"tool": name, "class": kind, "found": bool(found), "version": version or "", "where": where or "",
            "needed_for": needed_for, "without_it": without, "note": note or ""}


# ---- the single probes -------------------------------------------------------------------------------------------
def probe_python():
    v = sys.version_info
    ok = (v[0], v[1]) >= MIN_PYTHON
    note = "" if ok else "Python %d.%d or newer is needed (TOML reading is in the standard library from 3.11)" % MIN_PYTHON
    return _row("Python", "core", ok, "%d.%d.%d" % (v[0], v[1], v[2]), sys.executable,
                "every script", "nothing can be checked: stop", note)


def probe_library(dist, module, needed_for, without, kicad_versions):
    """A Python library: visible to an isolated run, or only in the user's site-packages."""
    import importlib.metadata as md
    found, version, where, notes = False, "", "", []
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        spec = None
    if spec is not None:
        found, where = True, "this Python"
        try:
            version = md.version(dist)
        except md.PackageNotFoundError:
            version = "?"
    else:
        try:
            import site
            user = site.getusersitepackages()
        except Exception:
            user = None
        if user and os.path.isdir(user):
            hits = [d for d in md.distributions(path=[user]) if (d.metadata["Name"] or "").lower() == dist.lower()]
            if hits:
                found, version, where = True, hits[0].version, "user site-packages"
                notes.append("hidden from `python -I`: scripts reach it with kicad_io.add_user_site()")
    kv = kicad_versions.get(module)
    notes.append("in KiCad's Python: " + (kv if kv else "missing"))
    return _row(dist, "optional", found, version, where, needed_for, without, "; ".join(notes))


def probe_kicad():
    """Rows for kicad-cli, KiCad's Python, the symbol libraries, ngspice; and the library versions in KiCad's Python."""
    cli_need = "schematic and board files, ERC, DRC, netlist, Gerbers, drill, 3D export, renders"
    cli_without = "stop after phase 4: the design exists on paper only"
    py_need = "every script that loads a board (pcbnew): layout checks, production files, layout helpers"
    py_without = "no board can be read or written by script: stop after phase 4"
    try:
        import kicad_io
    except Exception as e:                                               # the module itself is broken or missing
        msg = "scripts/kicad_io.py could not be imported: %s" % e
        return ([_row("KiCad command line (kicad-cli)", "core", False, needed_for=cli_need, without=cli_without, note=msg),
                 _row("KiCad Python (pcbnew)", "core", False, needed_for=py_need, without=py_without, note=msg)], {}, None)
    rows, libs = [], {}
    try:
        kc = kicad_io.find_kicad()
        why = "" if kc else kicad_io.not_found_reason()
    except Exception as e:
        kc, why = None, str(e)
    if kc is None:
        rows.append(_row("KiCad command line (kicad-cli)", "core", False, needed_for=cli_need, without=cli_without, note=why))
        rows.append(_row("KiCad Python (pcbnew)", "core", False, needed_for=py_need, without=py_without,
                         note="looked for beside kicad-cli"))
        rows.append(_row("KiCad symbol libraries", "optional", False, needed_for="stock symbols of the schematic writer",
                         without="every symbol must be drawn in the project's own library"))
        return rows, libs, None
    notes = [kc.note] if kc.note else []
    try:
        others = [k for k in kicad_io.list_installs() if os.path.normcase(k.bin_dir) != os.path.normcase(kc.bin_dir)]
    except Exception:
        others = []
    if others:
        notes.append("also installed: " + ", ".join("%s (%s)" % (k.version, k.bin_dir) for k in others)
                     + "; set KICAD_BIN to use another one")
    rows.append(_row("KiCad command line (kicad-cli)", "core", True, kc.version, kc.cli + " [" + kc.source + "]",
                     cli_need, cli_without, "; ".join(notes)))
    py = kc.python
    pcbnew_ver = ""
    if py:
        code = ("import json\nout = {}\n"
                "try:\n import pcbnew\n out['pcbnew'] = pcbnew.Version()\nexcept Exception as e:\n out['pcbnew_error'] = str(e)\n"
                "import importlib.metadata as md\n"
                "for mod, dist in (('numpy', 'numpy'), ('matplotlib', 'matplotlib'), ('PIL', 'pillow'), ('cadquery', 'cadquery')):\n"
                " try:\n  out[mod] = md.version(dist)\n except Exception:\n  pass\n"
                "print('ENVCHECK' + json.dumps(out))\n")
        rc, out = _run([py, "-I", "-c", code])
        line = next((ln for ln in out.splitlines() if ln.startswith("ENVCHECK")), "")
        if line:
            libs = json.loads(line[len("ENVCHECK"):])
            pcbnew_ver = libs.get("pcbnew", "")
        if pcbnew_ver:
            rows.append(_row("KiCad Python (pcbnew)", "core", True, pcbnew_ver, py, py_need, py_without))
        else:
            rows.append(_row("KiCad Python (pcbnew)", "core", False, "", py, py_need, py_without,
                             "found, but `import pcbnew` failed: " + (libs.get("pcbnew_error") or out[-200:])))
    else:
        rows.append(_row("KiCad Python (pcbnew)", "core", False, needed_for=py_need, without=py_without,
                         note="no Python beside kicad-cli, and no python3 on the path can import pcbnew"))
    sym = kc.symbols_dir
    have_sym = bool(sym) and os.path.isfile(os.path.join(sym, "Device.kicad_sym"))
    rows.append(_row("KiCad symbol libraries", "optional", have_sym, kc.version if have_sym else "", sym or "",
                     "stock symbols (resistor, capacitor, supply symbols ...) of the schematic writer",
                     "every symbol must be drawn in the project's own library",
                     "" if have_sym else "Device.kicad_sym not found (set KICAD%d_SYMBOL_DIR)" % kc.major))
    tables = [(k, kc.global_table(k)) for k in ("sym", "fp")]
    missing = [k + "-lib-table" for k, p in tables if not p]
    rows.append(_row("KiCad global library tables", "optional", not missing, "", kc.config_dir,
                     "the rule check (ERC) of a schematic that uses KiCad's stock libraries by name (most "
                     "hand-drawn designs; not the schematics written by this skill, which carry their own library)",
                     "ERC warns about every stock symbol or footprint ('library not in the configuration'): such "
                     "warnings come from this machine, not from the design",
                     ("missing: " + ", ".join(missing) + ". KiCad writes them when the program is opened once and "
                      "its default libraries are accepted; a script never does") if missing else ""))
    return rows, libs, kc


def probe_ngspice(kc):
    need = "the simulation campaign (phase 6)"
    without = "simulated points are UNKNOWN; they go to the bench list and gate 1 says so"
    lib = kc.ngspice_lib if kc else None
    exe = shutil.which("ngspice")
    if lib:
        return _row("ngspice", "optional", True, "shipped with KiCad " + kc.version, lib, need, without,
                    ("command on the path: " + exe) if exe else "shared library (run through scripts/sim/ngs.py)")
    if exe:
        rc, out = _run([exe, "--version"])
        ver = next((w for ln in out.splitlines() for w in ln.split() if w[:1].isdigit() or w.startswith("ngspice-")), "")
        return _row("ngspice", "optional", True, ver, exe, need, without, "command on the path")
    return _row("ngspice", "optional", False, needed_for=need, without=without)


def _probe_py_module(py, module, dist):
    rc, out = _run([py, "-I", "-c", "import importlib.metadata as md, %s; print('V=' + md.version('%s'))" % (module, dist)])
    line = next((ln for ln in out.splitlines() if ln.startswith("V=")), "")
    return line[2:] if rc == 0 and line else None


def probe_cadquery(kc, kicad_libs):
    need = "body_check.py: 3D bodies against holes and courtyards; 3D models of parts"
    without = ("body_check.py reports FAIL 'cannot run'; the mechanical and visual reviews carry the item with "
               "zoomed renders of every hole")
    named = os.environ.get("CADQUERY_PYTHON")
    if named:
        ver = _probe_py_module(named, "cadquery", "cadquery") if os.path.isfile(named) else None
        if ver:
            return _row("CadQuery", "optional", True, ver, named + " [CADQUERY_PYTHON]", need, without)
        return _row("CadQuery", "optional", False, "", named, need, without,
                    "CADQUERY_PYTHON is set, but that interpreter cannot import cadquery")
    if importlib.util.find_spec("cadquery") is not None:
        return _row("CadQuery", "optional", True, _probe_py_module(sys.executable, "cadquery", "cadquery") or "?",
                    "this Python", need, without)
    if kicad_libs.get("cadquery"):
        return _row("CadQuery", "optional", True, kicad_libs["cadquery"], "KiCad's Python", need, without)
    return _row("CadQuery", "optional", False, needed_for=need, without=without,
                note="not in this Python; if it lives in its own environment, set CADQUERY_PYTHON to that interpreter")


def probe_easyeda():
    need = "jlc_rotations.py and fetch_parts.py: JLCPCB library footprints and 3D models"
    without = ("rotations cannot be derived: every polarised part is UNKNOWN and is checked in JLCPCB's placement "
               "preview and at the placement confirmation")
    named = os.environ.get("EASYEDA2KICAD_PYTHON")
    if named:
        ver = _probe_py_module(named, "easyeda2kicad", "easyeda2kicad") if os.path.isfile(named) else None
        if ver:
            return _row("easyeda2kicad", "optional", True, ver, named + " [EASYEDA2KICAD_PYTHON]", need, without)
        return _row("easyeda2kicad", "optional", False, "", named, need, without,
                    "EASYEDA2KICAD_PYTHON is set, but that interpreter cannot import easyeda2kicad")
    exe = shutil.which("easyeda2kicad")
    if exe:
        return _row("easyeda2kicad", "optional", True, "", exe, need, without, "command on the path")
    if importlib.util.find_spec("easyeda2kicad") is not None:
        return _row("easyeda2kicad", "optional", True,
                    _probe_py_module(sys.executable, "easyeda2kicad", "easyeda2kicad") or "?", "this Python", need, without)
    return _row("easyeda2kicad", "optional", False, needed_for=need, without=without,
                note="not on the path; if it lives in its own environment, set EASYEDA2KICAD_PYTHON to that interpreter")


def probe_command(name, args, needed_for, without):
    exe = shutil.which(name)
    if not exe:
        return _row(name, "optional", False, needed_for=needed_for, without=without, note="not on the system path")
    rc, out = _run([exe] + args, timeout=30)
    ver = ""
    for word in out.replace("\n", " ").split():
        if word[:1].isdigit() and "." in word:
            ver = word.strip(",;")
            break
    return _row(name, "optional", True, ver, exe, needed_for, without)


# ---- the whole check -------------------------------------------------------------------------------------------------
def collect():
    rows = [probe_python()]
    kicad_rows, kicad_libs, kc = probe_kicad()
    rows += kicad_rows
    lib_rows = [
        ("numpy", "numpy", "geometry checks (copper necks, zones), simulation results",
         "the check that needs it reports FAIL 'cannot run'"),
        ("matplotlib", "matplotlib", "plots: simulation results, review images, block diagram",
         "the plot or check that needs it reports FAIL 'cannot run'"),
        ("pillow", "PIL", "image tiles and contact sheets of the review images",
         "review_images.py reports FAIL 'cannot run'"),
    ]
    jobs = [lambda: probe_ngspice(kc)]
    jobs += [lambda d=d, m=m, n=n, w=w: probe_library(d, m, n, w, kicad_libs) for d, m, n, w in lib_rows]
    jobs += [lambda: probe_cadquery(kc, kicad_libs), probe_easyeda,
             lambda: probe_command("pdftoppm", ["-v"], "schematic PDF pages to PNG (schematic/export.py)",
                                   "PNG pages come from another converter if one is found, else only PDF and SVG"),
             lambda: probe_command("curl", ["--version"], "downloads by direct URL (datasheets, footprints)",
                                   "use any other HTTP client that takes a direct URL")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(2, min(len(jobs), os.cpu_count() or 2))) as ex:
        rows += [f.result() for f in [ex.submit(j) for j in jobs]]       # submit order = table order
    for r in rows:
        if r["tool"] == "pillow":
            r["tool"] = "Pillow"
    core_missing = [r["tool"] for r in rows if r["class"] == "core" and not r["found"]]
    opt_missing = [r["tool"] for r in rows if r["class"] == "optional" and not r["found"]]
    code = 2 if core_missing else (1 if opt_missing else 0)
    verdict = ("FAIL: core tool missing: " + ", ".join(core_missing)) if core_missing else (
        "PASS for the core tools; optional tools missing: " + ", ".join(opt_missing) if opt_missing
        else "PASS: every tool is present")
    return {"script": "env_check.py", "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "system": "%s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
            "result": verdict, "exit_code": code, "core_missing": core_missing, "optional_missing": opt_missing,
            "tools": rows}


def as_markdown(res):
    L = ["# Environment check", "", "- Date: %s" % res["date"], "- System: %s" % res["system"],
         "- **Result: %s** (exit code %d)" % (res["result"], res["exit_code"]), "",
         "| Tool | Class | Found | Version | Needed for | Without it |", "|---|---|---|---|---|---|"]
    for r in res["tools"]:
        L.append("| %s | %s | %s | %s | %s | %s |" % (r["tool"], r["class"], "PASS" if r["found"] else "**MISSING**",
                                                       r["version"] or "-", r["needed_for"], r["without_it"]))
    L += ["", "## Where each tool was found, and notes", ""]
    for r in res["tools"]:
        L.append("- **%s**: %s%s" % (r["tool"], ("`%s`" % r["where"]) if r["where"] else "not found",
                                     (". " + r["note"]) if r["note"] else ""))
    L += ["", "Not checked here: the browser extension, push notifications, scheduled tasks, mailbox access and "
          "sub-agents (they belong to the agent's own tool set, see references/tools.md); LTspice.", "",
          "Nothing was installed and no network was used. Ask the user before installing anything."]
    return "\n".join(L) + "\n"


def as_table(res):
    rows = res["tools"]
    w = max(len(r["tool"]) for r in rows)
    wv = max(len(r["version"] or "-") for r in rows)
    L = ["%-*s  %-8s  %-7s  %-*s  %s" % (w, "TOOL", "CLASS", "FOUND", wv, "VERSION", "NEEDED FOR")]
    for r in rows:
        L.append("%-*s  %-8s  %-7s  %-*s  %s" % (w, r["tool"], r["class"], "PASS" if r["found"] else "MISSING", wv,
                                                  r["version"] or "-", r["needed_for"]))
        if not r["found"]:
            L.append("%-*s  without it: %s" % (w, "", r["without_it"]))
        if r["where"]:
            L.append("%-*s  at: %s" % (w, "", r["where"]))
        if r["note"]:
            L.append("%-*s  note: %s" % (w, "", r["note"]))
    L += ["", "RESULT: %s (exit code %d)" % (res["result"], res["exit_code"])]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Environment check of the electronics-design skill: finds KiCad, Python libraries and helper "
                    "tools, and says what does not work without each. Installs nothing, uses no network.",
        epilog="Exit codes: 0 every tool present; 1 core present, an optional tool missing; 2 a core tool missing. "
               "Environment variables: KICAD_BIN (folder of kicad-cli), CADQUERY_PYTHON and EASYEDA2KICAD_PYTHON "
               "(interpreters of the environments that hold those libraries).")
    ap.add_argument("--json", action="store_true", help="print the result as JSON instead of the table")
    ap.add_argument("--out", metavar="FOLDER", help="also write env_check.md and env_check.json into FOLDER")
    ap.add_argument("--project", metavar="BOARD_FOLDER", help="also write them into the board's results folder "
                                                              "(BOARD_FOLDER/out/, or board.toml [project] out_dir)")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):         # a folder name the console cannot show must not stop the check
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            pass
    out = a.out
    if not out and a.project:                       # the results folder as every project script finds it
        try:
            import kicad_io
            out = os.path.join(a.project, kicad_io.load_settings(a.project).get("project", {}).get("out_dir", "out"))
        except Exception as e:                      # an unreadable board.toml: never guess the folder
            print("CANNOT RUN: board.toml cannot be read: %s" % e, file=sys.stderr)
            return 2
    res = collect()
    if out:
        try:
            os.makedirs(out, exist_ok=True)
            for name, text in (("env_check.md", as_markdown(res)), ("env_check.json", json.dumps(res, indent=2) + "\n")):
                tmp = os.path.join(out, "~tmp%d_%s" % (os.getpid(), name))
                with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                os.replace(tmp, os.path.join(out, name))
        except OSError as e:
            print("CANNOT RUN: the result could not be written: %s" % e, file=sys.stderr)
            return 2
    print(json.dumps(res, indent=2) if a.json else as_table(res))
    if out and not a.json:
        print("written: %s, %s" % (os.path.join(out, "env_check.md"), os.path.join(out, "env_check.json")))
    return res["exit_code"]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:                               # the check itself broke: that is "could not run", never a pass
        import traceback
        traceback.print_exc()
        print("CANNOT RUN: env_check.py stopped on an internal error (above)", file=sys.stderr)
        sys.exit(2)
