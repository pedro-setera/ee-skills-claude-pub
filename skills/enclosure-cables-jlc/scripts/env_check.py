"""Finds the tools the enclosure and cable phases need and says which phases cannot run without each one.

What it does
    Looks for: Python (this one), CadQuery (this interpreter or the one named in CADQUERY_PYTHON / [tools]
    cadquery_python / a venv beside the project), the libraries numpy, shapely, ezdxf, matplotlib, scipy, Pillow,
    PyMuPDF and vtk, a slicer command line (Bambu Studio, OrcaSlicer, PrusaSlicer, in the usual install places and
    in [tools]), Blender, and Chrome or Edge. Prints one table: tool, found / MISSING / declined, version or place,
    and the phases that cannot run without it. It never installs, downloads or opens a network connection.
    A tool the user does not want used is written `[tools] slicer = "none"` (likewise `blender = "none"`, `chrome = "none"`):
    that is "declared absent". The table then says "declined by the user" (neither found nor missing), the tool is NOT
    looked for on the PC, and every script that would use it treats it as absent (`print_check.py --slice` gives
    could-not-run rows and runs nothing; `render_blender.py` exits 2). `is_declined(cfg, key)` is the one test they share.
    Run it again after mech.toml names [tools]: a run before mech.toml exists cannot know a path or a refusal.

Why it exists (the real failure, told without names)
    A session began a model build, found halfway that the CAD library lived in another Python, and then wrote the
    rest of the checks as "passed" because the import error was swallowed. Looking first, and naming what a missing
    tool blocks, keeps a missing tool from turning into a silent pass. In another session the user answered "no slicer
    may be used", mech.toml said so, and the script still found a slicer on the PC and ran it: a "no" must be recorded
    in a form that auto-detection cannot override.

Usage
    python -I env_check.py [--project <mech folder>] [--json] [--require cadquery,numpy]
    --require: the tools that must be present; exit 1 when one is missing or declined (default: cadquery)
    --json: one object per tool: tool, found, declined, detail, blocks

Config keys (mech.toml)
    [tools] cadquery_python, blender, slicer, slicer_kind, chrome   (slicer, blender, chrome: a path, "" = look for it, or
            "none" = the user declined it)

Exit codes
    0 every required tool is present   1 a required tool is missing or declined   (a missing or declined optional tool is only reported)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import glob
import json
import os
import shutil
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

LIBS = {  # import name: (pip name, phases that cannot run without it)
    "numpy": ("numpy", "print audit, section checks, drawings"),
    "shapely": ("shapely", "print audit (thin walls, steps), flat patterns, silkscreen"),
    "ezdxf": ("ezdxf", "DXF read/write: silkscreen files, catalogue scan of layers"),
    "matplotlib": ("matplotlib", "legend and review pictures, ink sheet, coupon legend"),
    "scipy": ("scipy", "route measurement, some geometry checks"),
    "PIL": ("Pillow", "pictures: crops, ink sheet"),
    "fitz": ("PyMuPDF", "PDF text for the catalogue scan, drawing pages to PNG, drawing book"),
    "vtk": ("vtk", "optional viewers"),
}

PROGRAM_DIRS = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")] + ["/Applications", "/usr/bin", "/usr/local/bin", "/opt"]

SLICERS = [  # kind, label, executable globs relative to a program dir, PATH names
    ("bambu", "Bambu Studio", ["Bambu Studio/bambu-studio.exe", "BambuStudio/bambu-studio.exe", "BambuStudio.app/Contents/MacOS/BambuStudio", "Programs/Bambu Studio/bambu-studio.exe"], ["bambu-studio", "BambuStudio"]),
    ("orca", "OrcaSlicer", ["OrcaSlicer/orca-slicer.exe", "Programs/OrcaSlicer/orca-slicer.exe", "OrcaSlicer.app/Contents/MacOS/OrcaSlicer"], ["orca-slicer", "OrcaSlicer"]),
    ("prusa", "PrusaSlicer", ["Prusa3D/PrusaSlicer/prusa-slicer-console.exe", "Prusa3D/PrusaSlicer/prusa-slicer.exe", "PrusaSlicer.app/Contents/MacOS/PrusaSlicer"], ["prusa-slicer-console", "prusa-slicer", "PrusaSlicer"]),
]
BROWSERS = [("Chrome", ["Google/Chrome/Application/chrome.exe", "Google Chrome.app/Contents/MacOS/Google Chrome"], ["google-chrome", "chrome"]),
            ("Edge", ["Microsoft/Edge/Application/msedge.exe", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge"], ["microsoft-edge", "msedge"])]


DECLINED = "none"


def is_declined(cfg, key) -> bool:
    """True when mech.toml says `[tools] <key> = "none"` (key: slicer, blender or chrome): the user declined that tool.
    A declined tool is never auto-detected and no script uses it."""
    v = ((cfg or {}).get("tools", {}) or {}).get(key, "")
    return isinstance(v, str) and v.strip().lower() == DECLINED


def _find(globs, names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    for d in PROGRAM_DIRS:
        if not d:
            continue
        for g in globs:
            hits = glob.glob(os.path.join(d, g))
            if hits:
                return hits[0]
    return None


def find_slicer(cfg=None):
    """(kind, path) of a slicer CLI: [tools] slicer first, then the usual places. (None, None) when there is none, or when
    the user declined it (`[tools] slicer = "none"`: never auto-detected)."""
    if is_declined(cfg, "slicer"):
        return None, None
    t = (cfg or {}).get("tools", {})
    if t.get("slicer") and os.path.isfile(t["slicer"]):
        kind = t.get("slicer_kind") or next((k for k, _l, g, _n in SLICERS if any(os.path.basename(x).lower() in os.path.basename(t["slicer"]).lower() for x in g)), "")
        if not kind:
            b = os.path.basename(t["slicer"]).lower()
            kind = "bambu" if "bambu" in b else "orca" if "orca" in b else "prusa" if "prusa" in b else ""
        return kind, t["slicer"]
    for kind, _label, globs, names in SLICERS:
        p = _find(globs, names)
        if p:
            return kind, p
    return None, None


def find_blender(cfg=None):
    if is_declined(cfg, "blender"):
        return None
    t = (cfg or {}).get("tools", {})
    if t.get("blender") and os.path.isfile(t["blender"]):
        return t["blender"]
    p = shutil.which("blender")
    if p:
        return p
    for d in PROGRAM_DIRS[:2]:
        if d:
            hits = sorted(glob.glob(os.path.join(d, "Blender Foundation", "Blender*", "blender.exe")), reverse=True)
            if hits:
                return hits[0]
    mac = "/Applications/Blender.app/Contents/MacOS/Blender"
    return mac if os.path.isfile(mac) else None


def _run_version(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return (r.stdout or r.stderr).strip().splitlines()[0][:80] if (r.stdout or r.stderr).strip() else ""
    except Exception:
        return ""


def _libs_of(py):
    code = ("import importlib,json;o={}\n"
            "for n in %r:\n"
            " try:\n"
            "  m=importlib.import_module(n);o[n]=getattr(m,'__version__','')or'?'\n"
            " except Exception:\n"
            "  o[n]=None\n"
            "print(json.dumps(o))") % (list(LIBS) + ["cadquery"],)
    try:
        r = subprocess.run([py, "-I", "-W", "ignore", "-c", code], capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {}


def collect(cfg=None) -> list[dict]:
    rows = []
    v = sys.version.split()[0]
    rows.append({"tool": "Python 3.10+", "found": sys.version_info >= (3, 10), "declined": False, "detail": f"{v} at {sys.executable}", "blocks": "every script"})
    cq_py = mc.find_cadquery_python(cfg)
    libs = _libs_of(cq_py or sys.executable) if (cq_py or True) else {}
    cqv = libs.get("cadquery")
    rows.append({"tool": "CadQuery", "found": bool(cq_py and cqv is not None), "declined": False, "detail": (f"{cqv} in {cq_py}" if cq_py and cqv is not None else
                 "not found: set CADQUERY_PYTHON or [tools] cadquery_python, or `uv venv` + `uv pip install cadquery` (ask first)"),
                 "blocks": "phases 3, 4, 5, 6, 7 (model, fit, pair checks, print audit), 8, 9 (STEP work)"})
    for n, (pip, blocks) in LIBS.items():
        ver = libs.get(n)
        rows.append({"tool": pip, "found": ver is not None, "declined": False, "detail": (f"{ver} (in the CadQuery Python)" if ver is not None else f"not found: pip install {pip}"), "blocks": blocks})
    kind, sl = find_slicer(cfg)
    rows.append(_row("Slicer CLI", cfg, "slicer", bool(sl), f"{kind}: {sl}" if sl else
                     'none found (Bambu Studio, OrcaSlicer, PrusaSlicer): set [tools] slicer to its path, or to "none" if no slicer may be used',
                     "phase 6 slicer run (the rule audit still runs; you slice by hand)"))
    bl = find_blender(cfg)
    rows.append(_row("Blender", cfg, "blender", bool(bl), (f"{_run_version([bl, '--version']) or 'found'} at {bl}" if bl else
                     'not found (set [tools] blender to its path, or to "none" to decline it)'),
                     "photo renders and manual pictures (plain engineering views still work)"))
    ch = None
    t = (cfg or {}).get("tools", {})
    if is_declined(cfg, "chrome"):
        pass
    elif t.get("chrome") and os.path.isfile(t["chrome"]):
        ch = ("configured", t["chrome"])
    else:
        for label, globs, names in BROWSERS:
            p = _find(globs, names)
            if p:
                ch = (label, p)
                break
    rows.append(_row("Chrome or Edge", cfg, "chrome", bool(ch), f"{ch[0]}: {ch[1]}" if ch else 'not found (set [tools] chrome to its path, or to "none" to decline it)',
                     "forms and the order watch (the browser extension is checked by the agent)"))
    return rows


def _row(tool, cfg, key, found, detail, blocks) -> dict:
    """One table row for a tool that mech.toml can decline: a declined tool is neither found nor missing."""
    if is_declined(cfg, key):
        return {"tool": tool, "found": False, "declined": True, "detail": f'declined by the user ([tools] {key} = "none"); not looked for',
                "blocks": blocks}
    return {"tool": tool, "found": found, "declined": False, "detail": detail, "blocks": blocks}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Find the tools of the enclosure skill; never installs.", epilog="Exit: 0 ok, 1 a required tool is missing.")
    ap.add_argument("--project")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require", default="cadquery")
    a = ap.parse_args(argv)
    cfg = None
    try:
        cfg = mc.load_config(mc.find_project(a.project))
    except mc.MechError:
        pass
    rows = collect(cfg)
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        w = max(len(r["tool"]) for r in rows)
        print(f"{'tool':{w}}  status    detail  [blocks when missing]")
        for r in rows:
            if r.get("declined"):
                print(f"{r['tool']:{w}}  declined  {r['detail']}\n{'':{w}}            not used, so this is done by hand or skipped: {r['blocks']}")
            else:
                print(f"{r['tool']:{w}}  {'found   ' if r['found'] else 'MISSING '}  {r['detail']}" + ("" if r["found"] else f"\n{'':{w}}            cannot run without it: {r['blocks']}"))
    need = [x.strip().lower() for x in a.require.split(",") if x.strip()]
    missing = [r["tool"] for r in rows if not r["found"] and not r.get("declined") and r["tool"].lower() in need]
    declined = [r["tool"] for r in rows if r.get("declined") and r["tool"].lower() in need]
    if missing:
        print("required and missing:", ", ".join(missing))
    if declined:
        print("required but declined by the user:", ", ".join(declined))
    return 1 if (missing or declined) else 0


if __name__ == "__main__":
    sys.exit(main())
