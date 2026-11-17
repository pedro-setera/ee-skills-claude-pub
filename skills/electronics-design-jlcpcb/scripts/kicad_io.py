"""Safe access to KiCad and to KiCad files: the one module every other script imports for it.

Why it exists (real failures, told without names)
    - A tool process loaded a board while another tool was rewriting its project file. KiCad's board loader locks
      the project and may rewrite it, so a KiCad message box appeared on the user's screen and a half-written file
      was nearly loaded. Hence: one lock per board among tool processes, writes that are atomic (a temporary name
      in the same folder, then a rename), a completeness check before every load, removal of lock files that a
      crashed tool left behind.
    - Scripts carried the install path of one KiCad version on one machine and stopped working on the next. Hence:
      discovery in one place.
    - A check that crashed half way ended with exit code 1, which the caller read as "findings", or printed nothing
      and was read as a pass. Hence: run_main(), which turns "could not run" into exit code 2, always.
    - KiCad's reader for another tool's board reported every warning as a message box on the user's screen, one
      after the other, with nobody there to click them; a failed internal assertion of KiCad opened a "Debug
      Alert" box in the same way. Hence: quiet_wx() and run_guarded(), used by everything here that starts KiCad.

What it gives (the names below are the public interface; they stay stable)
    Discovery
        find_kicad() -> KiCad | None    .bin_dir .cli .python .version .major .share_dir .symbols_dir
                                        .footprints_dir .ngspice_lib .config_dir .global_table(kind) .source .note
        require_kicad() -> KiCad        the same, or KiCadNotFound; not_found_reason() says why
        kicad_cli(), kicad_python(), kicad_version()
        run_cli(args, timeout=..., cwd=None, check=False)       kicad-cli with a timeout, output captured
        need_kicad_python()             re-launch the running script with KiCad's Python when pcbnew is missing
                                        (under run_guarded; inside KiCad's Python it calls quiet_wx())
        list_installs()                 every KiCad in the standard install places, preferred first
        Order: the environment variable KICAD_BIN (the folder that holds kicad-cli; when it is set it is the ONLY
        place looked at, so a wrong value fails loudly instead of silently picking another KiCad); the system
        path; the standard install places on Windows, macOS and Linux, any version folder: the newest install
        of the proven major version (KiCad 9) first, then the newest of any other version. The version is read
        from `kicad-cli version`. Another major version than the proven one gives a note, never a guess.
    No window, ever
        quiet_wx()                      inside KiCad's Python: KiCad's messages go to stderr and its assertion boxes
                                        are switched off, so nothing can open on the screen and block a script.
                                        need_kicad_python() and load_board() call it; a script of your own that
                                        imports pcbnew directly calls it before its first pcbnew call
        run_guarded(cmd, timeout, env=None, cwd=None, capture=True) -> (exit code, output, blocked)
                                        a child process with a time limit that cannot show a window: on Windows it
                                        runs on a private desktop that is never displayed, and it is stopped with
                                        everything it started when it opens a window there (within 5 s; blocked
                                        then says which, with its text). blocked also says when the time ran out
                                        or Windows could not start the child: such a run is "could not run" (exit
                                        code 2) for every caller, never a result. Safe to call from several
                                        threads at once. run_cli() and need_kicad_python() use it
    Lock and files
        ToolLock(path, timeout=None)    exclusive lock on one board or project (all its files); `with` statement
        clean_locks(path)               remove KiCad lock files and dead temporary files of this board
        incomplete_reason(path), check_complete(path)           is the file whole?
        load_board(path), save_board(board, path, patch=None)   pcbnew, under the lock, atomically; `patch` edits
                                        the project file before it is moved in place, and is never dropped
                                        silently (KiCad 10 writes no project with the first save of a new board)
        atomic_write(path, text), atomic_write_bytes(path, data), atomic_copy(src, dst), atomic_open(path)
        copy_board(src, dst), copy_project(src, dst)            copies; copy_project never writes into `src`
        sha256(path), private_tmp()
    Readers (plain Python, no KiCad needed; any KiCad project, whoever drew it)
        read_netlist(path) -> Netlist   parts, nets, pins of a netlist exported with `kicad-cli sch export netlist`
        schematic_sheets(root) -> list  the sheet instances of a (hierarchical) schematic, in page order
        leaf(net_name), is_named(net_name)
    Project folder (the skill's convention; optional)
        load_settings(project)          board.toml as a dict ({} when there is none)
        project_files(project)          where the schematic, the board and the out/ folder are
    Script frame
        run_main(main)                  exit code of main(); any error it lets through becomes "CANNOT RUN", code 2
        safe_output()                   print() can no longer fail on a character the console cannot show
        add_user_site()                 let a script started with `python -I` import numpy / matplotlib / Pillow
                                        that were installed with `pip install --user`
        KicadIOError, KiCadNotFound, LockTimeout, IncompleteFile, CliError

How a script uses it
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))      # `python -I` does not add the script folder
    import kicad_io
    def main(argv): ...  return 0 (pass), 1 (findings) or 2 (could not run)
    if __name__ == "__main__":
        sys.exit(kicad_io.run_main(main))
    A script that loads a board calls kicad_io.need_kicad_python() first, works on a copy (copy_project,
    copy_board) unless editing is its purpose, and loads and saves only with load_board / save_board.

board.toml keys read here (all optional)
    [project] name        base name of the KiCad files (needed only when the KiCad folder holds several projects)
    [project] kicad_dir   folder of the KiCad project inside the board folder (default "kicad", else the folder itself)
    [project] out_dir     results folder (default "out")

Environment variables: KICAD_BIN (see above); KICAD_IO_LOCK_WAIT (seconds to wait for a board lock, default 1800).

Not a command-line check. `python -I kicad_io.py` prints what discovery found (exit 0 found, 2 not found);
`--json` prints it as JSON.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import contextlib
import fnmatch
import glob
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import IO, Any, Iterator

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import sexp  # noqa: E402

__all__ = [
    "KicadIOError", "KiCadNotFound", "LockTimeout", "IncompleteFile", "CliError",
    "KiCad", "find_kicad", "list_installs", "require_kicad", "not_found_reason", "kicad_cli", "kicad_python", "kicad_version", "run_cli",
    "need_kicad_python", "quiet_wx", "run_guarded", "ToolLock", "clean_locks", "incomplete_reason", "check_complete", "load_board",
    "save_board", "atomic_write", "atomic_write_bytes", "atomic_copy", "atomic_open", "copy_board", "copy_project",
    "sha256", "private_tmp", "Netlist", "NetlistPart", "read_netlist", "schematic_sheets", "leaf", "is_named",
    "load_settings", "project_files", "add_user_site", "safe_output", "run_main", "PROVEN_MAJOR",
]

PROVEN_MAJOR = 9                    # the KiCad major version the scripts were proven on
LOCK_WAIT = float(os.environ.get("KICAD_IO_LOCK_WAIT", "1800"))   # s: a tool may hold a board for a whole stage
FILE_WAIT = 30.0                    # s: a file that is still being written
CLI_TIMEOUT = 600.0                 # s: one kicad-cli call
RELAUNCH_TIMEOUT = 4 * 3600.0       # s: a script re-launched with KiCad's Python
_SYSTEM = platform.system()         # "Windows", "Darwin", "Linux": read at run time, so no branch below is dead code
_WIN = _SYSTEM == "Windows"
_MAC = _SYSTEM == "Darwin"


def _module(name: str) -> Any:
    """Import a module that exists only on some systems or only in KiCad's Python (fcntl, msvcrt, pcbnew)."""
    return importlib.import_module(name)


class KicadIOError(RuntimeError):
    """The work could not be done (missing tool, unreadable or incomplete file, lock not obtained).
    exit_code is what run_main() returns for it: 2, "could not run". A subclass that stands for findings of a
    check (the schematic lint) sets it to 1."""
    exit_code = 2


class KiCadNotFound(KicadIOError):
    pass


class LockTimeout(KicadIOError):
    pass


class IncompleteFile(KicadIOError):
    pass


class CliError(KicadIOError):
    pass


# ---- discovery -------------------------------------------------------------------------------------------------------
class KiCad:
    """One KiCad installation."""

    def __init__(self, bin_dir: str, cli: str, version: str, source: str):
        self.bin_dir, self.cli, self.version, self.source = bin_dir, cli, version, source
        self._python: str | None = None
        self._python_looked = False

    @property
    def major(self) -> int:
        m = re.match(r"\s*(\d+)", self.version or "")
        return int(m.group(1)) if m else 0

    @property
    def note(self) -> str:
        """Empty for the proven major version; otherwise what the caller should tell the user."""
        if self.major == PROVEN_MAJOR:
            return ""
        return (f"KiCad {self.version or '(version unreadable)'} found; the scripts are proven on KiCad {PROVEN_MAJOR}: "
                f"file formats and command-line options may differ, results need a second look")

    @property
    def root(self) -> str:
        """The folder above bin (Windows, Linux prefix) or the application's Contents folder (macOS)."""
        return os.path.dirname(self.bin_dir.rstrip("\\/"))

    @property
    def share_dir(self) -> str | None:
        cands = [os.path.join(self.root, "share", "kicad"), os.path.join(self.root, "SharedSupport"),
                 "/usr/share/kicad", "/usr/local/share/kicad"]
        return next((c for c in cands if os.path.isdir(c)), None)

    def _lib_dir(self, env: str, sub: str) -> str | None:
        for name in (f"KICAD{self.major}_{env}", f"KICAD_{env}"):
            v = os.environ.get(name)
            if v and os.path.isdir(v):
                return v
        s = self.share_dir
        return os.path.join(s, sub) if s and os.path.isdir(os.path.join(s, sub)) else None

    @property
    def config_dir(self) -> str:
        """The user's settings folder of this KiCad version (it holds the global library tables). It may not exist."""
        home = os.environ.get("KICAD_CONFIG_HOME")
        if home:
            return home
        m = re.match(r"\s*(\d+)\.(\d+)", self.version or "")
        ver = f"{m.group(1)}.{m.group(2)}" if m else str(self.major)
        if _WIN:
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "kicad")
        elif _MAC:
            base = os.path.expanduser("~/Library/Preferences/kicad")
        else:
            base = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "kicad")
        return os.path.join(base, ver)

    def global_table(self, kind: str) -> str | None:
        """The user's global library table ("sym" or "fp"), or None when there is none. Without the symbol table
        the rule check warns about every stock-library symbol of a hand-drawn schematic; without the footprint
        table, about every footprint. KiCad writes them when the program is first opened; a script never does."""
        path = os.path.join(self.config_dir, f"{kind}-lib-table")
        return path if os.path.isfile(path) else None

    @property
    def symbols_dir(self) -> str | None:
        return self._lib_dir("SYMBOL_DIR", "symbols")

    @property
    def footprints_dir(self) -> str | None:
        return self._lib_dir("FOOTPRINT_DIR", "footprints")

    @property
    def python(self) -> str | None:
        """KiCad's own Python (the one that can import pcbnew), or None."""
        if not self._python_looked:
            self._python = _find_python(self)
            self._python_looked = True
        return self._python

    @property
    def ngspice_lib(self) -> str | None:
        """The ngspice shared library shipped with (or beside) KiCad, or None."""
        pats = [os.path.join(self.bin_dir, "ngspice.dll"), os.path.join(self.bin_dir, "libngspice*.dll"),
                os.path.join(self.root, "Frameworks", "libngspice*.dylib"),
                os.path.join(self.root, "lib*", "libngspice.so*"), os.path.join(self.root, "lib", "*", "libngspice.so*"),
                "/usr/lib/libngspice.so*", "/usr/lib64/libngspice.so*", "/usr/lib/*/libngspice.so*",
                "/usr/local/lib/libngspice.so*", "/usr/local/lib/libngspice*.dylib", "/opt/homebrew/lib/libngspice*.dylib"]
        for p in pats:
            hit = sorted(glob.glob(p))
            if hit:
                return hit[0]
        return None

    def to_dict(self) -> dict:
        return {"bin_dir": self.bin_dir, "cli": self.cli, "version": self.version, "major": self.major,
                "source": self.source, "python": self.python, "share_dir": self.share_dir,
                "symbols_dir": self.symbols_dir, "footprints_dir": self.footprints_dir,
                "ngspice_lib": self.ngspice_lib, "config_dir": self.config_dir,
                "global_sym_table": self.global_table("sym"), "global_fp_table": self.global_table("fp"),
                "note": self.note}


_CLI_NAMES = ("kicad-cli.exe", "kicad-cli.com") if _WIN else ("kicad-cli", "kicad.kicad-cli")
_found: dict[tuple, tuple] = {}


def _cli_in(folder: str) -> str | None:
    for n in _CLI_NAMES:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            return p
    return None


def _read_version(cli: str) -> str | None:
    try:
        r = subprocess.run([cli, "version"], capture_output=True, text=True, timeout=60, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"\d+\.\d+(?:\.\d+)?(?:[-~+.\w]*)", r.stdout or "")
    return m.group(0) if r.returncode == 0 and m else None


def _ver_key(name: str) -> tuple:
    nums = re.findall(r"\d+", name)
    return (1, tuple(int(n) for n in nums)) if nums else (0, ())


def _standard_dirs() -> list[str]:
    """bin folders of the standard install places, newest version folder first."""
    out: list[str] = []
    if _WIN:
        roots = []
        for var, sub in (("LOCALAPPDATA", "Programs"), ("ProgramFiles", ""), ("ProgramW6432", ""),
                         ("ProgramFiles(x86)", "")):
            base = os.environ.get(var)
            if base:
                roots.append(os.path.join(base, sub, "KiCad") if sub else os.path.join(base, "KiCad"))
        vers = []
        for r in dict.fromkeys(roots):
            if os.path.isdir(r):
                for v in os.listdir(r):
                    b = os.path.join(r, v, "bin")
                    if os.path.isdir(b):
                        vers.append((_ver_key(v), b))
        out = [b for _, b in sorted(vers, key=lambda t: t[0], reverse=True)]
    elif _MAC:
        apps = glob.glob("/Applications/KiCad*/KiCad.app") + glob.glob("/Applications/KiCad.app") + \
            glob.glob(os.path.expanduser("~/Applications/KiCad*/KiCad.app"))
        out = [os.path.join(a, "Contents", "MacOS") for a in sorted(apps, key=_ver_key, reverse=True)]
    else:
        out = ["/usr/bin", "/usr/local/bin", "/opt/kicad/bin", "/snap/bin", "/var/lib/flatpak/exports/bin",
               os.path.expanduser("~/.local/bin")]
    return out


def find_kicad(refresh: bool = False) -> KiCad | None:
    """The KiCad to use, or None. The answer is kept per process for the same KICAD_BIN and PATH."""
    key = (os.environ.get("KICAD_BIN"), os.environ.get("PATH"))
    if not refresh and key in _found:
        return _found[key][0]
    kc, why = None, ""
    forced = os.environ.get("KICAD_BIN")
    if forced:
        cli = _cli_in(forced) if os.path.isdir(forced) else None
        if cli is None:
            why = f"KICAD_BIN is set to '{forced}', which holds no kicad-cli (unset it to search the usual places)"
        else:
            ver = _read_version(cli)
            if ver is None:
                why = f"'{cli}' (from KICAD_BIN) does not answer `kicad-cli version`"
            else:
                kc = KiCad(os.path.abspath(forced), cli, ver, "KICAD_BIN")
    else:
        for n in _CLI_NAMES:
            w = shutil.which(n)
            if w:
                d = os.path.dirname(os.path.realpath(w))
                cli = _cli_in(d) or w
                ver = _read_version(cli)
                if ver:
                    kc = KiCad(d, cli, ver, "system path")
                break
        if kc is None:
            installs = list_installs()
            if installs:
                kc = installs[0]
        if kc is None:
            why = "no kicad-cli on the system path or in the standard install places (set KICAD_BIN to its folder)"
    _found[key] = (kc, why)
    return kc


def list_installs() -> list[KiCad]:
    """Every KiCad in the standard install places, in the order of preference: first the installs of the proven
    major version (newest first), then the others (newest first). A newer major version is not taken ahead of the
    proven one on its own: its Python would save a board in the newer file format, which the user's older KiCad
    cannot open again. Set KICAD_BIN to choose another install."""
    out = []
    for d in _standard_dirs():
        cli = _cli_in(d)
        ver = _read_version(cli) if cli else None
        if cli and ver:
            out.append(KiCad(d, cli, ver, "standard install place"))
    out.sort(key=lambda k: (k.major == PROVEN_MAJOR, _ver_key(k.version)), reverse=True)
    return out


def require_kicad() -> KiCad:
    kc = find_kicad()
    if kc is None:
        raise KiCadNotFound(not_found_reason())
    return kc


def not_found_reason() -> str:
    """Why find_kicad() found nothing ('' when it found KiCad)."""
    find_kicad()
    return _found[(os.environ.get("KICAD_BIN"), os.environ.get("PATH"))][1]


def kicad_cli() -> str:
    return require_kicad().cli


def kicad_version() -> str:
    return require_kicad().version


def _imports_pcbnew(py: str) -> bool:
    try:
        r = subprocess.run([py, "-c", "import pcbnew"], capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _find_python(kc: KiCad) -> str | None:
    cands = [os.path.join(kc.bin_dir, "python.exe"),
             os.path.join(kc.root, "Frameworks", "Python.framework", "Versions", "Current", "bin", "python3"),
             os.path.join(kc.bin_dir, "python3")]
    for c in cands:
        if os.path.isfile(c):
            return c
    if not _WIN:                                    # Linux: the system Python carries pcbnew
        for name in ("python3", "python"):
            w = shutil.which(name)
            if w and _imports_pcbnew(w):
                return w
    return None


def kicad_python() -> str:
    py = require_kicad().python
    if not py:
        raise KiCadNotFound("KiCad's own Python (with the pcbnew module) was not found beside kicad-cli")
    return py


def run_cli(args: list[str], timeout: float = CLI_TIMEOUT, cwd: str | None = None,
            check: bool = False) -> subprocess.CompletedProcess:
    """Run kicad-cli with `args`, under the guard (see run_guarded). Output is captured as text. A timeout, a window
    that the command opens, a kicad-cli that Windows could not start, or (with check=True) a non-zero exit code
    raises CliError; the process is not left running."""
    cmd = [kicad_cli()] + [str(a) for a in args]
    try:
        rc, out, err, blocked = _guarded(cmd, timeout, None, cwd, True, True)
    except KicadIOError as e:
        raise CliError(f"kicad-cli could not be started: {e}") from None
    if blocked:
        raise CliError(f"kicad-cli {' '.join(str(a) for a in args[:3])} ... gave no result: {blocked}")
    r = subprocess.CompletedProcess(cmd, rc, out, err)
    if check and r.returncode != 0:
        tail = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()[-1500:]
        raise CliError(f"kicad-cli {' '.join(str(a) for a in args[:3])} ... failed (exit {r.returncode}): {tail}")
    return r


def need_kicad_python(timeout: float = RELAUNCH_TIMEOUT) -> None:
    """Call first in a script that imports pcbnew. Returns when pcbnew can be imported here; otherwise runs the
    same command line again with KiCad's Python and exits with that run's exit code (2 when that is impossible)."""
    try:
        _module("pcbnew")
    except ImportError:
        pass
    else:
        quiet_wx()                  # from here on KiCad's messages go to stderr: no box can open and block the script
        return
    if os.environ.get("KICAD_IO_RELAUNCHED") == "1":
        print("CANNOT RUN: pcbnew cannot be imported, even with KiCad's Python", file=sys.stderr)
        sys.exit(2)
    try:
        py = kicad_python()
    except KicadIOError as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        sys.exit(2)
    env = dict(os.environ, KICAD_IO_RELAUNCHED="1")
    try:
        rc, _, blocked = run_guarded([py, "-I", "-B", os.path.abspath(sys.argv[0])] + sys.argv[1:], timeout, env=env,
                                     capture=False)             # -B: no __pycache__ beside the scripts
    except KicadIOError as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        sys.exit(2)
    if blocked:
        print(f"CANNOT RUN: the run with KiCad's Python gave no result: {blocked}", file=sys.stderr)
        sys.exit(2)
    sys.exit(rc)


# ---- no window, ever ---------------------------------------------------------------------------------------------------
# Two things keep every window of KiCad off the user's screen. quiet_wx(): inside KiCad's Python, messages and
# failed assertions of KiCad go to stderr or are dropped instead of opening a box. run_guarded(): a child process
# (kicad-cli, KiCad's Python, anything they start) runs on a private Windows desktop that is never displayed, is
# stopped if it opens a window there (nobody could answer it), and has a time limit.
_WX_LOG = None                      # kept alive: the log target that replaces the message boxes
GUARD_DESKTOP = "kicad-tool-"       # name prefix of the private desktop
_GUARD_API = None                   # the Windows calls of the guard, set up once
_GUARD_DESK = None                  # (handle, name for a child or None, is it private?) of this process
_GUARD_LOCK = threading.RLock()     # one thread at a time makes the desktop and starts a child (see _desktop, _guarded)
_NOT_STARTED = (0xC0000142, 0xC0000135, 0xC000007B, 0xC0000139)   # Windows could not set the process up (its DLLs)


def quiet_wx() -> str:
    """Call before the first pcbnew call that can warn (loading or importing a board). KiCad's readers report
    through the wxWidgets log, and in KiCad's Python every such message becomes a modal message box on the
    user's screen that blocks the script until somebody clicks it; a failed internal assertion of KiCad becomes
    a "Debug Alert" box in the same way. This sends the log to stderr, where the caller can collect it, and
    switches the assertion boxes off (KiCad's own programs do not show them either). Safe to call more than
    once. Returns what was done (a short text), for the record."""
    global _WX_LOG
    try:
        import wx
    except Exception as e:                                              # noqa: BLE001  no wxPython in this Python
        return f"wx not importable ({type(e).__name__}): the log could not be redirected"
    done = []
    try:
        if _WX_LOG is None:
            _WX_LOG = wx.LogStderr()
        wx.Log.SetActiveTarget(_WX_LOG)
        wx.Log.SetLogLevel(wx.LOG_Info)
        done.append("wx log sent to stderr")
    except Exception as e:                                              # noqa: BLE001
        try:
            wx.Log.EnableLogging(False)
            done.append(f"wx log switched off (stderr target failed: {e})")
        except Exception as e2:                                         # noqa: BLE001
            done.append(f"the wx log could not be redirected ({e2})")
    try:
        wx.DisableAsserts()
        done.append("assertion boxes off")
    except Exception as e:                                              # noqa: BLE001
        done.append(f"assertion boxes could not be switched off ({e})")
    return "; ".join(done)


def _win():
    """The Windows calls of the guard (kernel32, user32) with their argument types; None on other systems."""
    global _GUARD_API
    if _GUARD_API is not None or os.name != "nt":
        return _GUARD_API
    with _GUARD_LOCK:
        if _GUARD_API is not None:
            return _GUARD_API
        import ctypes
        from ctypes import wintypes as w
        k32, u32 = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("user32", use_last_error=True)
        h, ptr = w.HANDLE, ctypes.POINTER
        for fn, res, args in (
                (k32.CreateJobObjectW, h, [w.LPVOID, w.LPCWSTR]), (k32.AssignProcessToJobObject, w.BOOL, [h, h]),
                (k32.SetInformationJobObject, w.BOOL, [h, ctypes.c_int, w.LPVOID, w.DWORD]),
                (k32.QueryInformationJobObject, w.BOOL, [h, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]),
                (k32.TerminateJobObject, w.BOOL, [h, w.UINT]), (k32.TerminateProcess, w.BOOL, [h, w.UINT]),
                (k32.CloseHandle, w.BOOL, [h]), (k32.ResumeThread, w.DWORD, [h]),
                (k32.WaitForSingleObject, w.DWORD, [h, w.DWORD]), (k32.GetExitCodeProcess, w.BOOL, [h, ptr(w.DWORD)]),
                (k32.GetCurrentThreadId, w.DWORD, []), (k32.GetConsoleWindow, h, []), (k32.SetErrorMode, w.UINT, [w.UINT]),
                (k32.CreateProcessW, w.BOOL, [w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL, w.DWORD, w.LPVOID,
                                              w.LPCWSTR, w.LPVOID, w.LPVOID]),
                (u32.CreateDesktopW, h, [w.LPCWSTR, w.LPCWSTR, w.LPVOID, w.DWORD, w.DWORD, w.LPVOID]),
                (u32.CloseDesktop, w.BOOL, [h]), (u32.GetThreadDesktop, h, [w.DWORD]), (u32.SetThreadDesktop, w.BOOL, [h]),
                (u32.GetUserObjectInformationW, w.BOOL, [h, ctypes.c_int, w.LPVOID, w.DWORD, ptr(w.DWORD)]),
                (u32.IsWindowVisible, w.BOOL, [w.HWND]), (u32.GetWindowThreadProcessId, w.DWORD, [w.HWND, ptr(w.DWORD)]),
                (u32.GetWindowTextW, ctypes.c_int, [w.HWND, w.LPWSTR, ctypes.c_int]),
                (u32.SendMessageTimeoutW, w.LPARAM, [w.HWND, w.UINT, w.WPARAM, w.LPVOID, w.UINT, w.UINT, w.LPVOID])):
            fn.restype, fn.argtypes = res, args
        enum = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        u32.EnumDesktopWindows.argtypes, u32.EnumChildWindows.argtypes = [h, enum, w.LPARAM], [w.HWND, enum, w.LPARAM]
        _GUARD_API = (ctypes, w, k32, u32, enum)
    return _GUARD_API


def _desktop():
    """(handle, name to give a child or None, private?) of the desktop the children of this process run on.
    A process that already runs on a private desktop (it was started by a guard) keeps its children there. Else
    a private desktop is made once for this process; Windows removes it when the last process on it has ended.
    When that is not possible the children stay on the user's desktop and are only watched: (handle, None, False).
    One thread at a time: two threads of one process that made the desktop at the same moment (a script that
    starts two kicad-cli runs at once) left a desktop that no child could open, and every child of that process
    then ended at its start with Windows status 0xC0000142."""
    global _GUARD_DESK
    with _GUARD_LOCK:
        if _GUARD_DESK is not None:
            return _GUARD_DESK
        ctypes, w, k32, u32, _ = _win()
        mine = u32.GetThreadDesktop(k32.GetCurrentThreadId())
        buf, need = ctypes.create_unicode_buffer(256), w.DWORD()
        u32.GetUserObjectInformationW(mine, 2, buf, ctypes.sizeof(buf), ctypes.byref(need))        # UOI_NAME
        if buf.value.startswith(GUARD_DESKTOP):
            _GUARD_DESK = (mine, None, True)
        else:
            name = f"{GUARD_DESKTOP}{os.getpid()}"
            made = u32.CreateDesktopW(name, None, None, 0, 0x10000000, None)                          # GENERIC_ALL
            _GUARD_DESK = (made, name, True) if made else (mine, None, False)
    return _GUARD_DESK


class _Group:
    """A child process and everything it starts, as one group: its visible windows can be listed and all of it
    can be stopped at once. Windows: a job object, which the system also closes (stopping the group) when this
    process dies. Elsewhere: the child's own session; windows cannot be seen there."""

    def __init__(self):
        self.job, self.pid = None, 0
        if _win():
            ctypes, w, k32, _, _ = _win()

            class Basic(ctypes.Structure):
                _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("LimitFlags", w.DWORD), ("c", ctypes.c_size_t),
                            ("d", ctypes.c_size_t), ("e", w.DWORD), ("f", ctypes.c_size_t), ("g", w.DWORD), ("h", w.DWORD)]

            class Extended(ctypes.Structure):   # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
                _fields_ = [("Basic", Basic), ("io", ctypes.c_uint64 * 6), ("m", ctypes.c_size_t * 4)]

            job = k32.CreateJobObjectW(None, None)
            if job:
                info = Extended()
                info.Basic.LimitFlags = 0x2000                          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                    self.job = job
                else:
                    k32.CloseHandle(job)

    def add(self, process_handle, pid: int) -> None:
        self.pid = pid
        if self.job and not _win()[2].AssignProcessToJobObject(self.job, process_handle):
            _win()[2].CloseHandle(self.job)                             # no job for this child: it is watched alone
            self.job = None

    def pids(self) -> set:
        if not self.job:
            return {self.pid}
        ctypes, w, k32, _, _ = _win()

        class Ids(ctypes.Structure):            # JOBOBJECT_BASIC_PROCESS_ID_LIST
            _fields_ = [("assigned", w.DWORD), ("listed", w.DWORD), ("ids", ctypes.c_size_t * 1024)]
        ids = Ids()
        k32.QueryInformationJobObject(self.job, 3, ctypes.byref(ids), ctypes.sizeof(ids), None)
        return {int(ids.ids[i]) for i in range(min(ids.listed, 1024))} | {self.pid}

    def windows(self, desk) -> list[tuple]:
        """The visible top-level windows of the group's processes on the desktop `desk`: each as (handle, its
        title and the texts it shows). Looked up by a thread that joins that desktop first: a window can only
        be asked from its own desktop."""
        ctypes, w, _, u32, enum = _win()
        pids, found = self.pids(), []

        def look():
            u32.SetThreadDesktop(desk)
            hwnds = []

            def each(hwnd, _lparam):
                wpid = w.DWORD()
                u32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                if wpid.value in pids and u32.IsWindowVisible(hwnd):
                    hwnds.append(hwnd)
                return True
            u32.EnumDesktopWindows(desk, enum(each), 0)
            for hwnd in hwnds:
                texts = []

                def child(c, _lparam):
                    buf = ctypes.create_unicode_buffer(600)
                    u32.SendMessageTimeoutW(c, 0x000D, 600, buf, 0x0002, 300, None)     # WM_GETTEXT, SMTO_ABORTIFHUNG
                    if buf.value.strip():
                        texts.append(" ".join(buf.value.split()))
                    return True
                title = ctypes.create_unicode_buffer(256)
                u32.GetWindowTextW(hwnd, title, 256)
                u32.EnumChildWindows(hwnd, enum(child), 0)
                found.append((hwnd, (title.value or "untitled window") + (": " + " | ".join(texts) if texts else "")))
            found.sort(key=lambda t: t[1] == "untitled window")         # the windows that say something first
        t = threading.Thread(target=look, daemon=True)
        t.start()
        t.join(5)
        return found

    def stop(self, process_handle=None, proc=None) -> None:
        """Stop the child and everything it started."""
        if self.job:
            _win()[2].TerminateJobObject(self.job, 1)
        if process_handle:
            _win()[2].TerminateProcess(process_handle, 1)
        if proc is not None:
            if os.name != "nt":
                import signal
                with contextlib.suppress(OSError):
                    os.killpg(proc.pid, signal.SIGKILL)
            with contextlib.suppress(OSError):
                proc.kill()

    def close(self) -> None:
        if self.job:
            _win()[2].CloseHandle(self.job)                             # also stops whatever the child left running
            self.job = None


def run_guarded(cmd: list[str], timeout: float, env: dict | None = None, cwd: str | None = None,
                capture: bool = True) -> tuple[int, str, str]:
    """Run a child process that must never show a window, never wait for a click and never outlive its time.
    Returns (exit code, output, blocked). blocked is '' or the reason the child gave no result: the time limit,
    a window that the child or anything it started opened (with the window's title and text), or that Windows
    could not start it. A caller treats a blocked run as "could not run" (exit code 2), never as a result.

    Windows: the child and everything it starts run on a private desktop, which is never displayed, so nothing
    of theirs can appear on the user's screen; a window opened there is seen within a tenth of a second and
    the whole group is stopped, because nobody could answer it. Guards run inside each other (a suite runs a
    check that runs kicad-cli): each tells its child how deep it is (KICAD_IO_GUARD) and an outer guard gives
    a window one second more than the guard inside it (5 s at most), so that the guard nearest to it stops
    only its own child and its caller can report which step it was. Where no private desktop can be made the
    window is on the screen and the group is stopped at once. Other systems: the time limit only.
    Everywhere: the child is stopped together with everything it started, also when this process is killed.
    capture=True: output is stdout and stderr together, as text. capture=False: the child writes straight to
    this process's own output, and the returned output is ''. The child never gets keyboard input."""
    rc, out, _, blocked = _guarded(cmd, timeout, env, cwd, capture, False)
    return rc, out, blocked


def _guarded(cmd, timeout, env, cwd, capture, split) -> tuple[int, str, str, str]:
    """run_guarded with stdout and stderr apart when `split`: (exit code, stdout, stderr, blocked)."""
    cmd = [str(c) for c in cmd]
    group = _Group()
    if not _win():
        return _guarded_plain(cmd, timeout, env, cwd, capture, split, group)
    msvcrt = _module("msvcrt")
    ctypes, w, k32, u32, _ = _win()
    desk, desk_name, private = _desktop()
    depth = int(os.environ.get("KICAD_IO_GUARD", "0")) if os.environ.get("KICAD_IO_GUARD", "0").isdigit() else 0
    grace = 1.0 * max(0, 5 - depth) if private else 0.0     # seconds a window may stay: see run_guarded

    class StartupInfo(ctypes.Structure):        # STARTUPINFOW
        _fields_ = [("cb", w.DWORD), ("r1", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR), ("pos", w.DWORD * 7),
                    ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("r2", w.WORD), ("r3", w.LPVOID), ("hStdInput", w.HANDLE),
                    ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]

    class ProcessInfo(ctypes.Structure):        # PROCESS_INFORMATION
        _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]

    fds, files = [], []

    def handle(fd):
        """The handle of a file descriptor, made inheritable; the descriptor is closed after the start."""
        fds.append(fd)
        os.set_inheritable(fd, True)
        return msvcrt.get_osfhandle(fd)

    def own(stream):
        try:
            stream.flush()
            return handle(os.dup(stream.fileno()))
        except (AttributeError, OSError, ValueError):                   # no real stream behind it
            return handle(os.open(os.devnull, os.O_WRONLY))

    def to_file():
        fd, path = tempfile.mkstemp(prefix="kicad-tool-out-")
        files.append(path)
        return handle(fd)

    si, pi = StartupInfo(), ProcessInfo()
    with _GUARD_LOCK:                           # one start at a time: a child inherits every handle that is inheritable at
        try:                                    # this moment, and must not get the output file of another thread's child
            si.cb, si.dwFlags = ctypes.sizeof(si), 0x100                    # STARTF_USESTDHANDLES
            si.lpDesktop = desk_name
            si.hStdInput = handle(os.open(os.devnull, os.O_RDONLY))
            if capture:
                si.hStdOutput = to_file()
                si.hStdError = to_file() if split else si.hStdOutput
            else:
                si.hStdOutput, si.hStdError = own(sys.stdout), own(sys.stderr)
            flags = 0x00000004 | 0x00000400                                 # CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT
            if capture or not k32.GetConsoleWindow():
                flags |= 0x08000000                                         # CREATE_NO_WINDOW: no console window of its own
            env = dict(os.environ if env is None else env, KICAD_IO_GUARD=str(depth + 1))
            block = ctypes.create_unicode_buffer("".join(f"{k}={v}\0" for k, v in env.items()) + "\0")
            line = ctypes.create_unicode_buffer(subprocess.list2cmdline(cmd))
            mode = k32.SetErrorMode(0x8003)     # the child inherits it: Windows shows no box of its own when the child
            try:                                # cannot start or crashes (no critical-error, fault or file-open box)
                k32.SetErrorMode(mode | 0x8003)
                ok = k32.CreateProcessW(None, line, None, None, True, flags, block, cwd, ctypes.byref(si), ctypes.byref(pi))
                err = ctypes.get_last_error()
            finally:
                k32.SetErrorMode(mode)
        finally:
            for fd in fds:
                with contextlib.suppress(OSError):
                    os.close(fd)
    if not ok:
        group.close()
        for path in files:
            with contextlib.suppress(OSError):
                os.remove(path)
        raise KicadIOError(f"could not start {os.path.basename(cmd[0])}: {ctypes.FormatError(err).strip()}")
    t0, blocked, seen = time.monotonic(), "", {}
    try:
        group.add(pi.hProcess, pi.pid)
        k32.ResumeThread(pi.hThread)
        while k32.WaitForSingleObject(pi.hProcess, 100) == 0x102:      # WAIT_TIMEOUT: still running
            if time.monotonic() - t0 > timeout:
                blocked = f"it did not finish in {timeout:.0f} s"
            else:
                wins, now = group.windows(desk), time.monotonic()
                seen = {h: seen.get(h, now) for h, _ in wins}           # each window has its own clock
                if any(now - t >= grace for t in seen.values()):
                    blocked = ("it opened a window" + (", kept off the screen on a private desktop" if private else " on the screen")
                               + " (" + "; ".join(text for _, text in wins[:3])[:900] + ")")
            if blocked:
                group.stop(pi.hProcess)
                k32.WaitForSingleObject(pi.hProcess, 10000)
                break
        code = w.DWORD(1)
        k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
        if not blocked and code.value in _NOT_STARTED:
            blocked = f"it could not start (Windows status {code.value:#010x}: the process could not be set up)"
    finally:
        if k32.WaitForSingleObject(pi.hProcess, 0) == 0x102:           # this process was interrupted: leave nothing behind
            group.stop(pi.hProcess)
        group.close()
        k32.CloseHandle(pi.hThread)
        k32.CloseHandle(pi.hProcess)
    texts = []
    for path in files:
        text = ""
        with contextlib.suppress(OSError):
            with open(path, "rb") as f:
                text = f.read().decode("utf-8", errors="replace").replace("\r\n", "\n")
        texts.append(text)
        for _ in range(40):                                             # a stopped process lets go of the file a moment later
            try:
                os.remove(path)
                break
            except OSError:
                time.sleep(0.05)
    texts += ["", ""]
    return code.value, texts[0], texts[1], blocked


def _guarded_plain(cmd, timeout, env, cwd, capture, split, group) -> tuple[int, str, str, str]:
    """_guarded where there is no private desktop to use (not Windows): the time limit and the group stop."""
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE if capture else None,
                             stderr=(subprocess.PIPE if split else subprocess.STDOUT) if capture else None,
                             stdin=subprocess.DEVNULL, env=env, cwd=cwd, start_new_session=True)
    except OSError as e:
        raise KicadIOError(f"could not start {os.path.basename(cmd[0])}: {e}") from None
    group.pid = p.pid
    out, blocked = (b"", b""), ""
    try:
        try:
            out = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            blocked = f"it did not finish in {timeout:.0f} s"
            group.stop(proc=p)
            out = p.communicate()
    finally:
        if p.poll() is None:
            group.stop(proc=p)
    return p.returncode, (out[0] or b"").decode("utf-8", errors="replace"), (out[1] or b"").decode("utf-8", errors="replace"), blocked


# ---- the lock --------------------------------------------------------------------------------------------------------
_KICAD_EXT = (".kicad_pcb", ".kicad_sch", ".kicad_pro", ".kicad_prl", ".kicad_dru")
_LOCK_BYTE = 1 << 30                # Windows: the locked byte lies far behind the text, so the text stays readable


def _base(path: str) -> str:
    """The path without its KiCad extension: one base names a board with all its files."""
    for ext in _KICAD_EXT:
        if path.lower().endswith(ext):
            return path[:-len(ext)]
    return os.path.splitext(path)[0]


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if _WIN:
        ctypes = _module("ctypes")
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)                     # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259                       # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


class ToolLock:
    """Exclusive lock on one board or project (every file that shares its base name) among tool processes.

        with ToolLock(board_path):            # waits up to `timeout` seconds (default LOCK_WAIT), then LockTimeout
            ...

    The lock is a file `.<name>.toollock` beside the board, held through an operating-system file lock, so a
    process that dies releases it at once and a file left behind is not a lock. The file names its holder (process
    number, start time) for the message of a waiting tool. Re-entrant inside one process (not per thread)."""

    _held: dict[str, list] = {}       # lock file -> [count, file descriptor]
    _guard = threading.RLock()

    def __init__(self, path: str, timeout: float | None = None, poll: float = 0.2):
        b = _base(os.path.abspath(path))
        self.file = os.path.join(os.path.dirname(b), "." + os.path.basename(b) + ".toollock")
        self.timeout = LOCK_WAIT if timeout is None else float(timeout)
        self.poll = poll

    # -- operating-system lock on an open file
    @staticmethod
    def _os_lock(fd: int) -> None:
        if _WIN:
            msvcrt = _module("msvcrt")
            os.lseek(fd, _LOCK_BYTE, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)                  # OSError when another process holds it
        else:
            fcntl = _module("fcntl")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _os_unlock(fd: int) -> None:
        try:
            if _WIN:
                msvcrt = _module("msvcrt")
                os.lseek(fd, _LOCK_BYTE, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl = _module("fcntl")
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass

    def _try(self) -> int | None:
        """The file descriptor that now holds the lock, or None when another process holds it."""
        fd = os.open(self.file, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            self._os_lock(fd)
        except OSError:
            os.close(fd)
            return None
        try:
            if not _WIN and os.stat(self.file).st_ino != os.fstat(fd).st_ino:
                raise FileNotFoundError(self.file)                  # the last holder removed the file we locked
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, f"pid {os.getpid()} since {time.strftime('%Y-%m-%dT%H:%M:%S')}\n".encode())
        except OSError:
            self._os_unlock(fd)
            os.close(fd)
            return None
        return fd

    def holder(self) -> str:
        """Who holds the lock, as written in the lock file ('' when unknown)."""
        try:
            with open(self.file, encoding="utf-8", errors="replace") as f:
                return f.read(200).strip()
        except OSError:
            return ""

    def acquire(self) -> "ToolLock":
        with ToolLock._guard:
            h = ToolLock._held.get(self.file)
            if h:
                h[0] += 1
                return self
        t0 = time.monotonic()
        denied: str | None = None
        while True:
            try:
                fd = self._try()
                denied = None
            except OSError as e:                    # folder missing or read-only; on Windows also a file being deleted
                fd, denied = None, str(e)
                if not os.path.isdir(os.path.dirname(self.file)) or time.monotonic() - t0 > 5.0:
                    raise KicadIOError(f"cannot create the lock file {self.file}: {e}") from None
            if fd is not None:
                with ToolLock._guard:
                    ToolLock._held[self.file] = [1, fd]
                return self
            waited = time.monotonic() - t0
            if waited >= self.timeout:
                who = self.holder() or denied or "another process"
                raise LockTimeout(f"{self.file} is held by {who}; gave up after {waited:.0f} s")
            time.sleep(self.poll)

    def release(self) -> None:
        with ToolLock._guard:
            h = ToolLock._held.get(self.file)
            if not h:
                return
            h[0] -= 1
            if h[0]:
                return
            del ToolLock._held[self.file]
            fd = h[1]
        if _WIN:
            self._os_unlock(fd)
            os.close(fd)
            with contextlib.suppress(OSError):
                os.remove(self.file)                # fails while a waiting process has it open: then it is theirs
        else:
            with contextlib.suppress(OSError):
                os.remove(self.file)                # removed while still locked: a waiter notices and retries
            os.close(fd)

    def __enter__(self) -> "ToolLock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()


def clean_locks(path: str, whole_folder: bool = False) -> list[str]:
    """Remove what a crashed run left beside this board: KiCad's own lock files (`~<name>.kicad_*.lck`) and this
    module's temporary files whose process is gone. Call it under the ToolLock, so no tool of ours holds them.
    whole_folder=True: the lock files of every KiCad file in the folder (the sheets of a hierarchical schematic).
    Returns the removed paths. Do not call it on a project that is open in the KiCad program."""
    b = _base(os.path.abspath(path))
    d, n = os.path.dirname(b), os.path.basename(b)
    gone = []
    pats = [os.path.join(d, "~*.kicad_*.lck")] if whole_folder else \
        [os.path.join(d, "~" + glob.escape(n) + ext + ".lck") for ext in (".kicad_pro", ".kicad_pcb", ".kicad_sch")]
    for pat in pats:
        for f in glob.glob(pat):
            with contextlib.suppress(OSError):
                os.remove(f)
                gone.append(f)
    for f in glob.glob(os.path.join(d, "~tmp*_*")):
        m = re.match(r"~tmp(\d+)_", os.path.basename(f))
        if m and not _pid_alive(int(m.group(1))):
            with contextlib.suppress(OSError):
                os.remove(f)
                gone.append(f)
    return gone


# ---- completeness ----------------------------------------------------------------------------------------------------
_HEADS = {".kicad_pcb": "(kicad_pcb", ".kicad_sch": "(kicad_sch", ".kicad_sym": "(kicad_symbol_lib",
          ".kicad_wks": "(kicad_wks", ".net": "(export"}
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"', re.S)


def incomplete_reason(path: str) -> str | None:
    """None when the file is whole; otherwise what is wrong. S-expression files (.kicad_pcb, .kicad_sch,
    .kicad_sym, .kicad_mod, .kicad_dru, .net): the expected head, balanced parentheses, closed strings.
    .kicad_pro / .kicad_prl / .json: valid JSON. A board (.kicad_pcb) is checked with its project and rule file."""
    ext = os.path.splitext(path)[1].lower()
    try:
        with open(path, encoding="utf-8", newline="") as f:
            txt = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return f"{path}: {e}"
    if ext in (".kicad_pro", ".kicad_prl", ".json"):
        try:
            json.loads(txt)
        except ValueError as e:
            return f"{path}: not valid JSON ({e})"
        return None
    body = txt
    if ext == ".kicad_dru":
        body = re.sub(r"(?m)^\s*#.*$", "", body)
    body = _STRING.sub("", body)
    head = _HEADS.get(ext)
    if not body.strip():
        return f"{path}: empty"
    if head and not body.lstrip().startswith(head):
        return f"{path}: does not start with {head}"
    if '"' in body:
        return f"{path}: a string is not closed"
    if body.count("(") != body.count(")") or not body.rstrip().endswith(")"):
        return f"{path}: incomplete s-expression ({body.count('(')} '(' against {body.count(')')} ')')"
    if ext == ".kicad_pcb":
        for comp in (".kicad_pro", ".kicad_dru"):
            c = _base(path) + comp
            if os.path.exists(c):
                why = incomplete_reason(c)
                if why:
                    return why
    return None


def check_complete(path: str, wait: float = FILE_WAIT) -> None:
    """Return when the file (a board: with its project and rule file) is whole; a file that is still being
    written is waited for up to `wait` seconds, then IncompleteFile is raised, so KiCad never gets to show a dialog."""
    t0 = time.monotonic()
    while True:
        why = incomplete_reason(path)
        if why is None:
            return
        if time.monotonic() - t0 >= wait:
            raise IncompleteFile(f"not loading: {why}")
        time.sleep(0.5)


# ---- atomic writes ---------------------------------------------------------------------------------------------------
def _tmp_name(path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(path)), f"~tmp{os.getpid()}_" + os.path.basename(path))


def _replace(tmp: str, path: str) -> None:
    """os.replace, patient with a reader that holds the target open for a moment (Windows)."""
    for i in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 39:
                raise
            time.sleep(0.05)


@contextlib.contextmanager
def atomic_open(path: str, mode: str = "w", encoding: str | None = "utf-8",
                newline: str | None = "") -> Iterator[IO[Any]]:
    """Open a temporary file beside `path` for writing; on a clean exit it replaces `path` in one step. When the
    block raises, or the process dies inside it, `path` is untouched (a dead temporary file is removed by
    clean_locks). mode "w": a text file, write str (line ends are written as given); mode "wb": write bytes."""
    if mode not in ("w", "wb"):
        raise ValueError("atomic_open writes: mode 'w' or 'wb'")
    tmp = _tmp_name(path)
    f: IO[Any]
    if mode == "wb":
        f = open(tmp, "wb")
    else:
        f = open(tmp, "w", encoding=encoding, newline=newline)
    try:
        yield f
        f.flush()
        os.fsync(f.fileno())
        f.close()
        _replace(tmp, path)
    except BaseException:
        f.close()
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def atomic_write(path: str, text: str, encoding: str = "utf-8") -> None:
    """Write text to `path` so that a reader sees the old file or the new one, never a part. Line ends are
    written exactly as they are in `text`."""
    if not isinstance(text, str):
        raise TypeError("atomic_write takes text; use atomic_write_bytes for bytes")
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Write bytes to `path` so that a reader sees the old file or the new one, never a part."""
    tmp = _tmp_name(path)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def atomic_copy(src: str, dst: str) -> None:
    """Copy one file byte for byte; `dst` appears complete or not at all."""
    tmp = _tmp_name(dst)
    try:
        shutil.copyfile(src, tmp)
        _replace(tmp, dst)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def sha256(path: str) -> str:
    """SHA-256 of a file's bytes, as 64 hexadecimal characters."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@contextlib.contextmanager
def private_tmp(prefix: str = "kicad-tool-"):
    """A temporary folder that belongs to this process alone; removed at the end of the block."""
    d = tempfile.mkdtemp(prefix=prefix)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---- boards (pcbnew) -------------------------------------------------------------------------------------------------
def load_board(path: str, timeout: float | None = None):
    """pcbnew.LoadBoard, safely: under the board's tool lock, crashed runs' lock files removed, files checked
    complete. Needs KiCad's Python (see need_kicad_python). Use it on a board the script owns or on a copy."""
    pcbnew = _module("pcbnew")
    quiet_wx()                          # a warning of the loader goes to stderr, never into a message box
    with ToolLock(path, timeout):
        clean_locks(path)
        check_complete(path)
        b = pcbnew.LoadBoard(path)
        clean_locks(path)
    return b


def _name_project(pro: str, name: str) -> None:
    """KiCad saved the project under a temporary file name and wrote that name into it (meta.filename): put the
    real name there. Only that one value is touched; the rest of the file stays as KiCad wrote it."""
    with open(pro, encoding="utf-8", newline="") as f:
        text = f.read()
    tmp = os.path.basename(pro)
    olds = "|".join(re.escape(v) for v in {json.dumps(tmp), json.dumps(tmp, ensure_ascii=False)})
    new = re.sub(r'("filename"\s*:\s*)(?:' + olds + ")", lambda m: m.group(1) + json.dumps(name, ensure_ascii=False), text)
    if new != text:
        with open(pro, "w", encoding="utf-8", newline="") as f:
            f.write(new)


def save_board(board, path: str, patch=None, timeout: float | None = None) -> None:
    """pcbnew.SaveBoard, atomically: board and project are saved under temporary names in the same folder
    (`patch(project_path)`, if given, edits the temporary project), then moved over the real files. The project
    file's own note of its name (meta.filename) is set to the real name, not the temporary one.
    A patch is never dropped silently: KiCad 10 writes no project file with the first save of a board that never
    had one (the stand-in project it gives such a board is read-only). So when `patch` is given and there is no
    project file, the saved copy is loaded from a second temporary name and saved once more: a board loaded
    from a file gets a project that KiCad does write. If there is still none (a project that another program
    holds open is read-only too), the save fails with KicadIOError and nothing is replaced."""
    pcbnew = _module("pcbnew")
    path = os.path.abspath(path)
    d, n = os.path.dirname(path), os.path.basename(_base(path))
    tmpb = os.path.join(d, f"~tmp{os.getpid()}_{n}")
    tmp2 = os.path.join(d, f"~tmp{os.getpid()}b_{n}")
    with ToolLock(path, timeout):
        try:
            pcbnew.SaveBoard(tmpb + ".kicad_pcb", board)
            why = incomplete_reason(tmpb + ".kicad_pcb")
            if why:
                raise IncompleteFile(f"the saved board is not complete, nothing replaced: {why}")
            if patch is not None and not os.path.exists(tmpb + ".kicad_pro"):
                quiet_wx()
                _replace(tmpb + ".kicad_pcb", tmp2 + ".kicad_pcb")
                pcbnew.SaveBoard(tmpb + ".kicad_pcb", pcbnew.LoadBoard(tmp2 + ".kicad_pcb"))
                why = incomplete_reason(tmpb + ".kicad_pcb")
                if why:
                    raise IncompleteFile(f"the saved board is not complete, nothing replaced: {why}")
                if not os.path.exists(tmpb + ".kicad_pro"):
                    raise KicadIOError("KiCad wrote no project file for this board, so its project settings could not be "
                                       "set; nothing was replaced")
            if os.path.exists(tmpb + ".kicad_pro"):
                _name_project(tmpb + ".kicad_pro", n + ".kicad_pro")
                if patch is not None:
                    patch(tmpb + ".kicad_pro")
                _replace(tmpb + ".kicad_pro", _base(path) + ".kicad_pro")
            if os.path.exists(tmpb + ".kicad_dru"):
                _replace(tmpb + ".kicad_dru", _base(path) + ".kicad_dru")
            _replace(tmpb + ".kicad_pcb", path)
        finally:
            for tmp in (tmpb, tmp2):
                for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".kicad_prl"):
                    with contextlib.suppress(OSError):
                        os.remove(tmp + ext)
                for ext in (".kicad_pro.lck", ".kicad_pcb.lck"):
                    with contextlib.suppress(OSError):
                        os.remove(os.path.join(d, "~" + os.path.basename(tmp) + ext))


def copy_board(src: str, dst: str, lock_source: bool = True) -> None:
    """Copy a board with its project and rule file, each file atomically, under the tool locks.
    lock_source=False: write nothing beside `src` (a project that is not ours); the copy is then checked complete."""
    locks = [ToolLock(dst)] + ([ToolLock(src)] if lock_source else [])
    with contextlib.ExitStack() as st:
        for lk in locks:
            st.enter_context(lk)
        check_complete(src)
        sb, db = _base(src), _base(dst)
        for ext in (".kicad_pro", ".kicad_dru"):
            if os.path.exists(sb + ext):
                atomic_copy(sb + ext, db + ext)
        atomic_copy(src, dst)
        check_complete(dst)


COPY_IGNORE = ("~*", "*.lck", ".*.toollock", "*-backups", "_autosave-*", "*.kicad_prl", "fp-info-cache", "*.bak",
               "*-bak", "*.tmp", ".git", ".svn", ".hg", "__pycache__", ".history")
_CHECKED_EXT = (".kicad_pcb", ".kicad_sch", ".kicad_sym", ".kicad_mod", ".kicad_dru", ".kicad_pro", ".net")


def copy_project(src: str, dst: str, *, overwrite: bool = False, ignore: tuple = COPY_IGNORE) -> dict[str, str]:
    """Copy a KiCad project folder for work that must not touch the original (a review, a test, a check).

    src: the project folder, or any file in it. dst: a folder; it is created, and must be empty unless
    overwrite=True. Sub-folders (libraries) come along; lock files, backups, local view settings (.kicad_prl),
    caches and version-control folders do not. Nothing is written into `src`, not even a lock file. Every copied
    file is compared with its source by SHA-256, and KiCad files are checked complete; a file that was being
    written during the copy is copied again (for up to FILE_WAIT seconds).
    Returns {path relative to dst, with '/': SHA-256}."""
    src = os.path.abspath(src)
    if os.path.isfile(src):
        src = os.path.dirname(src)
    dst = os.path.abspath(dst)
    if not os.path.isdir(src):
        raise KicadIOError(f"copy_project: no such folder {src}")
    a, b = os.path.normcase(src) + os.sep, os.path.normcase(dst) + os.sep
    if a.startswith(b) or b.startswith(a):
        raise KicadIOError("copy_project: source and destination must not lie inside one another")
    if os.path.isdir(dst) and os.listdir(dst) and not overwrite:
        raise KicadIOError(f"copy_project: {dst} is not empty (give overwrite=True to copy into it)")
    os.makedirs(dst, exist_ok=True)

    def skip(name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in ignore)

    done: dict[str, str] = {}
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(x for x in dirs if not skip(x) and not os.path.islink(os.path.join(root, x)))
        rel = os.path.relpath(root, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for name in sorted(files):
            if skip(name):
                continue
            s, d = os.path.join(root, name), os.path.join(out, name)
            t0 = time.monotonic()
            while True:
                atomic_copy(s, d)
                h = sha256(d)
                why = None
                if h != sha256(s):
                    why = f"{s} changed while it was copied"
                elif name.lower().endswith(_CHECKED_EXT):
                    why = incomplete_reason(d) if not name.lower().endswith(".kicad_pcb") else _single_incomplete(d)
                if why is None:
                    break
                if time.monotonic() - t0 >= FILE_WAIT:
                    raise IncompleteFile(f"copy_project: {why}")
                time.sleep(0.5)
            done[os.path.relpath(d, dst).replace(os.sep, "/")] = h
    return done


def _single_incomplete(path: str) -> str | None:
    """incomplete_reason for a board file alone (its companions are checked as their own files)."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            body = _STRING.sub("", f.read())
    except (OSError, UnicodeDecodeError) as e:
        return f"{path}: {e}"
    if not body.lstrip().startswith("(kicad_pcb") or '"' in body or body.count("(") != body.count(")"):
        return f"{path}: incomplete s-expression"
    return None


# ---- readers ---------------------------------------------------------------------------------------------------------
def leaf(name: str) -> str:
    """A net's own name without its sheet path: '/Sheet name/BOOT' -> 'BOOT'; 'VBUS' -> 'VBUS'."""
    return name.rsplit("/", 1)[-1]


def is_named(name: str) -> bool:
    """True for a net named by the designer (a label or a power symbol), False for a name KiCad made up."""
    lf = leaf(name)
    return not (lf.startswith("unconnected-(") or lf.startswith("Net-(") or lf.startswith("N$"))


class NetlistPart:
    """One component of a netlist."""

    def __init__(self, ref: str):
        self.ref = ref
        self.value = ""
        self.footprint = ""
        self.fields: dict[str, str] = {}        # the symbol's fields (LCSC, MPN, whatever the design uses)
        self.dnp = False
        self.exclude_from_bom = False
        self.exclude_from_board = False
        self.lib = ""
        self.part = ""
        self.description = ""
        self.sheet = ""                         # the sheet instance, e.g. "/" or "/Power supply/"
        self.sheet_file = ""                    # the sheet's file name
        self.units = 1                          # how many units the symbol has in its library


class Netlist:
    """A KiCad netlist (kicadsexpr format) as plain data.

        parts   {reference: NetlistPart}
        nets    {net name: set of (reference, pin number)}
        pins    {(reference, pin number): (net name, pin function, pin type)}
        sheets  [(sheet instance name, file name)] in page order
    Pins are identified by their number; a part with several units appears once."""

    def __init__(self, path: str):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                tree = sexp.parse(f.read())
        except sexp.SexpError as e:
            raise KicadIOError(f"{path}: not a readable netlist ({e})") from None
        except UnicodeDecodeError as e:
            raise KicadIOError(f"{path}: not a text file ({e})") from None
        if not tree or tree[0] != "export" or sexp.first(tree, "components") is None:
            raise KicadIOError(f"{path}: not a KiCad netlist in kicadsexpr format "
                               f"(export it with: kicad-cli sch export netlist --format kicadsexpr)")
        design = sexp.first(tree, "design")
        self.tool = str(sexp.value(design, "tool", ""))
        self.source = str(sexp.value(design, "source", ""))
        self.sheets: list[tuple[str, str]] = []
        for sh in sexp.find(design, "sheet"):
            tb = sexp.first(sh, "title_block")
            self.sheets.append((str(sexp.value(sh, "name", "")), str(sexp.value(tb, "source", ""))))
        units = {}
        for lp in sexp.find(sexp.first(tree, "libparts"), "libpart"):
            key = (str(sexp.value(lp, "lib", "")), str(sexp.value(lp, "part", "")))
            units[key] = max(1, len(sexp.find(sexp.first(lp, "units"), "unit")))
        self.parts: dict[str, NetlistPart] = {}
        for c in sexp.find(sexp.first(tree, "components"), "comp"):
            p = NetlistPart(str(sexp.value(c, "ref", "")))
            p.value = str(sexp.value(c, "value", ""))
            p.footprint = str(sexp.value(c, "footprint", ""))
            for f in sexp.find(sexp.first(c, "fields"), "field"):
                p.fields[str(sexp.value(f, "name", ""))] = str(f[2]) if len(f) > 2 else ""
            for pr in sexp.find(c, "property"):
                name = str(sexp.value(pr, "name", ""))
                if name == "dnp":
                    p.dnp = True
                elif name == "exclude_from_bom":
                    p.exclude_from_bom = True
                elif name == "exclude_from_board":
                    p.exclude_from_board = True
                elif name == "Sheetfile":
                    p.sheet_file = str(sexp.value(pr, "value", ""))
                elif name and name not in p.fields and not name.startswith("ki_") and name != "Sheetname":
                    p.fields[name] = str(sexp.value(pr, "value", ""))
            ls = sexp.first(c, "libsource")
            p.lib = str(sexp.value(ls, "lib", ""))
            p.part = str(sexp.value(ls, "part", ""))
            p.description = str(sexp.value(ls, "description", ""))
            p.units = units.get((p.lib, p.part), 1)
            p.sheet = str(sexp.value(sexp.first(c, "sheetpath"), "names", ""))
            if p.ref in self.parts:
                raise KicadIOError(f"{path}: reference {p.ref} appears twice in the netlist (annotate the schematic)")
            self.parts[p.ref] = p
        self.nets: dict[str, set] = {}
        self.pins: dict[tuple, tuple] = {}
        for n in sexp.find(sexp.first(tree, "nets"), "net"):
            name = str(sexp.value(n, "name", ""))
            nodes = self.nets.setdefault(name, set())
            for nd in sexp.find(n, "node"):
                key = (str(sexp.value(nd, "ref", "")), str(sexp.value(nd, "pin", "")))
                if key in self.pins and self.pins[key][0] != name:
                    raise KicadIOError(f"{path}: pin {key[0]}.{key[1]} is on two nets "
                                       f"({self.pins[key][0]} and {name})")
                nodes.add(key)
                self.pins[key] = (name, str(sexp.value(nd, "pinfunction", "")), str(sexp.value(nd, "pintype", "")))

    def net_of(self, ref: str, pin) -> str:
        return self.pins[(ref, str(pin))][0]

    def pins_of(self, ref: str) -> list[str]:
        return sorted((p for (r, p) in self.pins if r == ref), key=lambda s: (len(s), s))


def read_netlist(path: str) -> Netlist:
    """Read a netlist exported by KiCad (kicadsexpr). KicadIOError when the file is not one; OSError when it
    cannot be opened."""
    return Netlist(path)


def _natural(s: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def schematic_sheets(root: str) -> list[dict]:
    """The sheet instances of a schematic, the root first, then in page order (as KiCad plots them).

    Each: {"page": "2", "name": "Power supply", "path": "/Power supply/", "file": absolute path of the sheet's
    file, "uuid_path": "/<root uuid>/<sheet uuid>"}. A file drawn once and used twice gives two instances.
    Reads the files only; KiCad is not needed. KicadIOError when a file is missing or unreadable."""
    root = os.path.abspath(root)
    cache: dict[str, list] = {}

    def load(path: str) -> list:
        if path not in cache:
            try:
                with open(path, encoding="utf-8") as f:
                    cache[path] = sexp.parse(f.read())
            except OSError as e:
                raise KicadIOError(f"schematic sheet not readable: {e}") from None
            except sexp.SexpError as e:
                raise KicadIOError(f"{path}: {e}") from None
            if not cache[path] or cache[path][0] != "kicad_sch":
                raise KicadIOError(f"{path}: not a KiCad schematic file")
        return cache[path]

    top = load(root)
    root_uuid = str(sexp.value(top, "uuid", ""))
    page1 = "1"
    for inst in sexp.find(sexp.first(top, "sheet_instances"), "path"):
        if len(inst) > 1 and inst[1] == "/":
            page1 = str(sexp.value(inst, "page", "1"))
    out = [{"page": page1, "name": "/", "path": "/", "file": root, "uuid_path": "/" + root_uuid}]

    def descend(path: str, uuid_path: str, name_path: str, depth: int) -> None:
        if depth > 32:
            raise KicadIOError(f"{root}: sheets nested deeper than 32 levels (a sheet that contains itself?)")
        for sh in sexp.find(load(path), "sheet"):
            props = {str(p[1]): str(p[2]) for p in sexp.find(sh, "property") if len(p) > 2}
            name = props.get("Sheetname", props.get("Sheet name", ""))
            fname = props.get("Sheetfile", props.get("Sheet file", ""))
            if not fname:
                continue
            fpath = os.path.normpath(os.path.join(os.path.dirname(path), fname))
            up = uuid_path + "/" + str(sexp.value(sh, "uuid", ""))
            page = ""
            for proj in sexp.find(sexp.first(sh, "instances"), "project"):
                for inst in sexp.find(proj, "path"):
                    if len(inst) > 1 and str(inst[1]) == uuid_path:
                        page = str(sexp.value(inst, "page", ""))
            np_ = name_path + name + "/"
            out.append({"page": page, "name": name, "path": np_, "file": fpath, "uuid_path": up})
            descend(fpath, up, np_, depth + 1)

    descend(root, "/" + root_uuid, "/", 0)
    order = {id(s): i for i, s in enumerate(out)}
    out.sort(key=lambda s: (0 if s["page"] else 1, _natural(s["page"]), order[id(s)]))   # pages, then drawing order
    return out


# ---- project folder --------------------------------------------------------------------------------------------------
def load_settings(project: str) -> dict:
    """board.toml of a board folder as a dict; {} when there is none. KicadIOError when it cannot be read
    (also on a Python older than 3.11, which has no TOML reader)."""
    path = os.path.join(project, "board.toml")
    if not os.path.isfile(path):
        return {}
    try:
        import tomllib
    except ImportError:
        raise KicadIOError("reading board.toml needs Python 3.11 or newer") from None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise KicadIOError(f"{path}: {e}") from None


def project_files(project: str, settings: dict | None = None) -> dict:
    """Where things are in a board folder: {"project", "kicad_dir", "name", "pro", "sch", "pcb", "out", "src"}.
    "sch" / "pcb" / "pro" are None when the file does not exist. KicadIOError when the KiCad folder holds several
    projects and board.toml does not say which ([project] name)."""
    project = os.path.abspath(project)
    if not os.path.isdir(project):
        raise KicadIOError(f"no such board folder: {project}")
    cfg = (settings if settings is not None else load_settings(project)).get("project", {})
    kdir = os.path.join(project, cfg["kicad_dir"]) if cfg.get("kicad_dir") else (
        os.path.join(project, "kicad") if os.path.isdir(os.path.join(project, "kicad")) else project)
    name = cfg.get("name")
    if not name:
        pros = sorted(glob.glob(os.path.join(kdir, "*.kicad_pro")))
        if not pros:
            pros = sorted(p for p in glob.glob(os.path.join(kdir, "*.kicad_sch"))
                          if os.path.exists(_base(p) + ".kicad_pcb")) or sorted(glob.glob(os.path.join(kdir, "*.kicad_pcb")))
        if len(pros) != 1:
            raise KicadIOError(f"{kdir}: {len(pros)} KiCad projects found; name the one to use in board.toml "
                               f"([project] name = \"...\")")
        name = os.path.basename(_base(pros[0]))
    base = os.path.join(kdir, name)

    def have(ext: str) -> str | None:
        return base + ext if os.path.isfile(base + ext) else None

    return {"project": project, "kicad_dir": kdir, "name": name, "pro": have(".kicad_pro"), "sch": have(".kicad_sch"),
            "pcb": have(".kicad_pcb"), "out": os.path.join(project, cfg.get("out_dir", "out")),
            "src": os.path.join(project, "src")}


# ---- script frame ----------------------------------------------------------------------------------------------------
def add_user_site() -> str | None:
    """Make the user's own site-packages folder importable again. `python -I` hides it, and that is where
    `pip install --user` puts numpy, matplotlib and Pillow when Python itself is installed for all users. A script
    that needs such a library calls this before the import. The folder goes to the END of the import path, so
    it can never shadow the standard library or a sibling module. Returns the folder added, or None."""
    import site
    try:
        d = site.getusersitepackages()
    except Exception:                                                   # no home folder, embedded Python
        return None
    if d and os.path.isdir(d) and d not in sys.path:
        site.addsitedir(d)
        return d
    return None


def safe_output() -> None:
    """Make print() unable to fail on a character the console cannot show (a part value with an ohm sign on a
    Windows console). Output that goes to a pipe or a file is written as UTF-8; on a console the console's own
    encoding stays and an unknown character is shown as an escape."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="backslashreplace")           # type: ignore[union-attr]
            else:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")   # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def run_main(main, argv: list[str] | None = None) -> int:
    """Run a script's main(argv) and return its exit code. Whatever main lets through (a missing tool, an
    unreadable file, a bug) is reported as CANNOT RUN with exit code 2: it is never a pass and never "findings".

        if __name__ == "__main__":
            sys.exit(kicad_io.run_main(main))
    """
    safe_output()
    try:
        rc = main(sys.argv[1:] if argv is None else argv)
        return 0 if rc is None else int(rc)
    except SystemExit as e:
        if e.code is None or isinstance(e.code, int):
            return 0 if e.code is None else e.code
        print(f"CANNOT RUN: {e.code}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("CANNOT RUN: interrupted", file=sys.stderr)
        return 2
    except KicadIOError as e:
        code = 1 if e.exit_code == 1 else 2
        print(("FAIL: " if code == 1 else "CANNOT RUN: ") + str(e), file=sys.stderr)
        return code
    except OSError as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2
    except Exception:                                                   # a bug is not a finding either
        traceback.print_exc()
        print("CANNOT RUN: the script stopped on an internal error (above)", file=sys.stderr)
        return 2


def _main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    kc = find_kicad()
    if "--json" in argv:
        print(json.dumps(kc.to_dict() if kc else {"found": False}, indent=2))
        return 0 if kc else 2
    if kc is None:
        print("CANNOT RUN: " + not_found_reason())
        return 2
    for k, v in kc.to_dict().items():
        print(f"{k:15} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(run_main(_main))
