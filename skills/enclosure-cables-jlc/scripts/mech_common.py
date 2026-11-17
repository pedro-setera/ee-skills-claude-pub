"""Shared helpers of the enclosure scripts: check rows, checksums, mech.toml, CadQuery interpreter, workers.

What it does
    - `Rows`: the list of check rows of one script (id, section, check, value, rule, verdict), with the headline line,
      the exit code and the writer of `<out>/checks/<script>.json` (the file `check_all.py` merges).
    - `sha256(path)`, `load_config(project)` (mech.toml with defaults), `find_project(arg)`, `resolve(args)`.
    - `reexec_with_cadquery()`: run the calling script again under another Python that has CadQuery.
    - `workers()`: the number of worker processes (MECH_WORKERS or all cores).

Why it exists (the real failure, told without names)
    Every check script used to print its own kind of summary, so a check that could not run looked like a pass
    when the summaries were read together, and an old result file was trusted after the model had changed. One
    row format with four verdicts and the checksum of every input makes both visible.

Usage (from a script, after `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`)
    import mech_common as mc
    job = mc.resolve(args)                       # project folder, config, out folder
    rows = mc.Rows()
    rows.add("FIT-01", "fit", "board against box", "0.0 mm3", "must be 0", "pass")
    rows.write(job.out, "fit_check.py", [interface_path, model_path])
    print(rows.headline()); sys.exit(rows.exit_code())
    This module has no command line; `python -I mech_common.py --selftest` runs a quick self test.

Config keys (mech.toml, all optional; the defaults are in DEFAULTS)
    [project] name, company, rev     [tools] cadquery_python, blender, slicer, slicer_kind, chrome
    [printer] profile                [build] steps                [paths] model, interface, out, cables, vendor

Exit codes of `Rows.exit_code()`
    0 every row passes (or is not applicable)   1 at least one row failed
    2 nothing failed but at least one row could not run (never a pass)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import copy
import datetime
import hashlib
import json
import os
import subprocess

# child processes (build steps, the project model) find the skill scripts through this variable
os.environ.setdefault("MECH_SCRIPTS", os.path.dirname(os.path.abspath(__file__)))

VERDICTS = ("pass", "fail", "could_not_run", "na")

DEFAULTS = {
    "project": {"name": "", "company": "", "rev": "A"},
    "tools": {"cadquery_python": "", "blender": "", "slicer": "", "slicer_kind": "", "chrome": ""},
    "printer": {"profile": ""},
    "build": {"steps": []},
    "paths": {"model": "model/build_model.py", "interface": "interface.json", "out": "out",
              "cables": "cables/cables.json", "vendor": "vendor3d/vendor_parts.toml"},
}


class MechError(Exception):
    """A problem the user must fix (missing input, bad config): scripts print it and exit 2."""


# ---------------------------------------------------------------- rows ----------------------------------------------
class Rows:
    """The check rows of one script. verdict: pass | fail | could_not_run | na."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, id: str, section: str, check: str, value, rule, verdict: str) -> dict:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}, not {verdict!r}")
        row = {"id": str(id), "section": str(section), "check": str(check), "value": _plain(value),
               "rule": _plain(rule), "verdict": verdict}
        self.rows.append(row)
        return row

    def counts(self) -> dict:
        c = {v: 0 for v in VERDICTS}
        for r in self.rows:
            c[r["verdict"]] += 1
        return c

    def headline(self) -> str:
        c = self.counts()
        return f"passed {c['pass']}, failed {c['fail']}, could not run {c['could_not_run']}, not applicable {c['na']}"

    def exit_code(self) -> int:
        c = self.counts()
        if c["fail"]:
            return 1
        if c["could_not_run"]:
            return 2
        return 0

    def failed(self) -> list[dict]:
        return [r for r in self.rows if r["verdict"] == "fail"]

    def extend(self, other: "Rows") -> None:
        self.rows.extend(other.rows)

    def print_table(self, only_bad: bool = False, file=None) -> None:
        file = file or sys.stdout
        for r in self.rows:
            if only_bad and r["verdict"] in ("pass", "na"):
                continue
            print(f"[{r['verdict'].upper():13}] {r['id']:10} {r['check']}: {r['value']}  (rule: {r['rule']})", file=file)

    def write(self, out_dir: str, script: str, inputs=()) -> str:
        """Write <out_dir>/checks/<script>.json; `inputs` are paths (missing ones are recorded with sha256 null)."""
        name = os.path.splitext(os.path.basename(script))[0]
        d = os.path.join(out_dir, "checks")
        os.makedirs(d, exist_ok=True)
        ins = []
        for p in inputs:
            p = str(p)
            ins.append({"path": os.path.abspath(p).replace("\\", "/"), "sha256": sha256(p) if os.path.isfile(p) else None})
        data = {"script": name, "date": now_utc(), "inputs": ins, "rows": self.rows}
        path = os.path.join(d, name + ".json")
        atomic_write(path, json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        return path


def _plain(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (int, str)) or v is None or isinstance(v, bool):
        return v
    try:
        json.dumps(v)
        return v
    except TypeError:
        return str(v)


# ---------------------------------------------------------------- files ---------------------------------------------
def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def atomic_write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _toml_loads(text: str) -> dict:
    try:
        import tomllib as t
    except ImportError:                       # Python 3.10
        try:
            import tomli as t                  # type: ignore
        except ImportError:
            raise MechError("reading TOML needs Python 3.11+ (or the 'tomli' package on 3.10)")
    return t.loads(text)


def load_toml(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read().decode("utf-8-sig")
    try:
        return _toml_loads(raw)
    except MechError:
        raise
    except Exception as e:                     # TOMLDecodeError
        raise MechError(f"{path}: not valid TOML: {e}")


# ---------------------------------------------------------------- project / config -----------------------------------
def find_project(arg: str | None = None) -> str:
    """The mech folder (the one holding mech.toml). `arg` may be that folder, its parent (which has mech/mech.toml),
    or None: search upward from the current folder."""
    cands = []
    if arg:
        a = os.path.abspath(arg)
        cands = [a, os.path.join(a, "mech")]
    else:
        d = os.getcwd()
        while True:
            cands += [d, os.path.join(d, "mech")]
            nd = os.path.dirname(d)
            if nd == d:
                break
            d = nd
    for c in cands:
        if os.path.isfile(os.path.join(c, "mech.toml")):
            return c
    if arg and os.path.isdir(os.path.abspath(arg)):
        return os.path.abspath(arg)            # a folder without mech.toml: defaults apply
    raise MechError("no mech.toml found" + (f" at {arg}" if arg else " here or above") + "; give --project <mech folder>")


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(project: str) -> dict:
    """mech.toml merged over DEFAULTS. A missing file gives the defaults. Adds cfg['_project'] (absolute folder)."""
    p = os.path.join(project, "mech.toml")
    cfg = _merge(DEFAULTS, load_toml(p) if os.path.isfile(p) else {})
    cfg["_project"] = os.path.abspath(project)
    return cfg


def path_of(cfg: dict, key: str) -> str:
    """Absolute path of a [paths] entry (relative ones are under the project folder)."""
    v = cfg["paths"].get(key) or DEFAULTS["paths"].get(key, "")
    return v if os.path.isabs(v) else os.path.normpath(os.path.join(cfg["_project"], v))


def rel_to_project(cfg: dict, p: str) -> str:
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(cfg["_project"], p))


class Job:
    def __init__(self, project: str, cfg: dict, out: str):
        self.project, self.cfg, self.out = project, cfg, out


def add_std_args(ap) -> None:
    ap.add_argument("--project", help="the mech folder (holds mech.toml); default: search upward from here")
    ap.add_argument("--out", help="output folder (default <project>/out, or [paths] out)")


def resolve(args) -> Job:
    project = find_project(getattr(args, "project", None))
    cfg = load_config(project)
    out = getattr(args, "out", None) or path_of(cfg, "out")
    return Job(project, cfg, os.path.abspath(out))


# ---------------------------------------------------------------- CadQuery -------------------------------------------
def have_cadquery() -> bool:
    try:
        import cadquery  # noqa: F401
        return True
    except Exception:
        return False


def _candidate_pythons(cfg: dict | None) -> list[str]:
    c = [os.environ.get("CADQUERY_PYTHON", "")]
    if cfg:
        c.append(cfg.get("tools", {}).get("cadquery_python", ""))
        proj = cfg.get("_project", "")
        for sub in (".venv", "venv", "cadvenv"):
            for exe in (os.path.join("Scripts", "python.exe"), os.path.join("bin", "python")):
                c.append(os.path.join(proj, sub, exe))
                c.append(os.path.join(os.path.dirname(proj), sub, exe))
    return [x for x in c if x and os.path.isfile(x)]


def find_cadquery_python(cfg: dict | None = None) -> str | None:
    """The interpreter that has CadQuery: this one, or CADQUERY_PYTHON / [tools] cadquery_python / a venv next to
    the project. None when there is none."""
    if have_cadquery():
        return sys.executable
    for p in _candidate_pythons(cfg):
        try:
            r = subprocess.run([p, "-I", "-c", "import cadquery"], capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        except Exception:
            continue
        if r.returncode == 0:
            return p
    return None


def _project_from_argv(argv: list[str]) -> str | None:
    for i, a in enumerate(argv):
        if a == "--project" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--project="):
            return a.split("=", 1)[1]
    return None


def reexec_with_cadquery(cfg: dict | None = None) -> None:
    """Call at the top of a script that needs CadQuery. Returns when CadQuery imports here. Otherwise re-runs the
    same command line under the interpreter named by CADQUERY_PYTHON or [tools] cadquery_python and exits with its
    exit code. With none: prints one line and exits 2."""
    if have_cadquery():
        return
    if os.environ.get("MECH_REEXEC") == "1":
        print("could not run: the interpreter named as CadQuery Python cannot import cadquery", file=sys.stderr)
        sys.exit(2)
    if cfg is None:
        try:
            cfg = load_config(find_project(_project_from_argv(sys.argv[1:])))
        except Exception:
            cfg = None
    py = find_cadquery_python(cfg)
    if not py or py == sys.executable:
        print("could not run: CadQuery is not installed for this Python. Set CADQUERY_PYTHON or [tools] cadquery_python "
              "in mech.toml to a Python that has it (python scripts/env_check.py shows what was found).", file=sys.stderr)
        sys.exit(2)
    env = dict(os.environ, MECH_REEXEC="1", PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([py, "-I", "-B", os.path.abspath(sys.argv[0])] + sys.argv[1:], env=env, stdin=subprocess.DEVNULL)
    sys.exit(r.returncode)


def require_module(name: str, why: str = ""):
    """Import a library lazily; exit 2 with a clear line when it is missing."""
    try:
        return __import__(name)
    except ImportError:
        print(f"could not run: the Python library '{name}' is missing" + (f" ({why})" if why else "")
              + "; install it into the interpreter you use (python scripts/env_check.py lists what is found)", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------- cores ---------------------------------------------
def workers() -> int:
    try:
        n = int(os.environ.get("MECH_WORKERS", "") or 0)
    except ValueError:
        n = 0
    return max(1, n or (os.cpu_count() or 1))


def _selftest() -> int:
    r = Rows()
    r.add("T-1", "t", "a", 1.23456789, "x", "pass")
    r.add("T-2", "t", "b", "n/a", "x", "na")
    assert r.exit_code() == 0
    r.add("T-3", "t", "c", "?", "x", "could_not_run")
    assert r.exit_code() == 2
    r.add("T-4", "t", "d", "bad", "x", "fail")
    assert r.exit_code() == 1 and r.headline() == "passed 1, failed 1, could not run 1, not applicable 1"
    print("mech_common selftest ok:", r.headline())
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
