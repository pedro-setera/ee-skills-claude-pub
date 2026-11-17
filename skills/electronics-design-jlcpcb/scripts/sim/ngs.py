"""Run ngspice test benches from Python: one engine per process, parallel benches, a convergence check that fails
loudly, and pass limits that are written before the run.

What it gives
    run(netlist, vectors, analysis=None, timeout=None)   one simulation in this process; returns
                                                         {"time" | "frequency" | "sweep": array, "<vector>": array, ...}
    run_many(benches, workers=None, timeout=None)        many simulations at once, each in its own process with its
                                                         own engine; the same numbers as a serial run, in the same order
    Limit, Test, run_tests(...)                          a test declares its pass limit before it runs; the verdict
                                                         and the results JSON come from that declaration
    scan_file(path, models=()), scan_netlist(text, models=())
                                                         the scan of a model file or a netlist and of every file
                                                         it includes, without running anything (see "The scan")
    calibration(quantity, datasheet, tolerance, ...)     a Limit that is a datasheet figure with its tolerance: the
                                                         row a maker's model needs before it is trusted
    set_compat(mode), COMPAT_MODES                       the compatibility mode (see "Compatibility mode")
    engine()                                             which ngspice was found, and its version
    tmpdir()                                             a temporary folder that belongs to this process alone
    command line:  python -I ngs.py engine               what was found (exit 2 when no ngspice)
                   python -I ngs.py self-test            an RC step against its formula; a bench that cannot converge
                   python -I ngs.py suite <folder or tb_*.py ...> [--jobs N] [--timeout S] [--out DIR] [--compat MODE]
                                                         every test bench script in its own process, all cores
                   python -I ngs.py scan <model file ...> [--models DIR ...]
                                                         the scan alone, for a model that was just downloaded:
                                                         exit 0 nothing refused, 1 REFUSED, 2 could not be scanned

    The engine is the ngspice shared library that comes with KiCad, found through kicad_io (the environment
    variable NGSPICE_LIB names another one). The netlist is handed over in memory and the vectors are read from
    memory: no file is written, so parallel runs cannot disturb each other, and a path with a blank cannot break
    a run. A test bench that needs files of its own puts them into tmpdir(). Quote every path in an .include line.

Why it exists (real failures, told without names)
    - A run that had stopped with "timestep too small" still left numbers behind, and a result table was nearly
      built from them. Here such a run raises ConvergenceError; there is no result to use.
    - Parallel runs shared temporary file names and corrupted each other; a file still held open by the engine
      could not be removed. Hence: nothing on disk, one engine per process.
    - A pass limit was widened after a test had failed. Here the limit is part of the test's declaration, is
      written into the results file next to the measured value, and the verdict is computed from it.
    - A simulation that never ended blocked a whole suite. Every run has a time limit; a process that does not
      come back is killed.
    - A model file from a maker's site is not only read by the simulator, it is executed: a command block in it
      starts a shell, writes files, loads code. The rule "read it before using it" was enforced by nobody. Here
      every netlist and every file it includes is scanned before the engine sees it.
    - Makers write models for PSpice or LTspice. Run in ngspice's own mode, some of their expressions are read
      differently and give other numbers without any error: (-2 V)**3 is +8 V. Here the compatibility mode is a
      setting, and the mode in force stands in every result.

The scan (run(), run_many() and `scan` apply it; there is no switch that turns it off)
    Scanned: the netlist and, recursively, every file named by a line that starts with .inc (.include, .inc,
    .incpslt) or by .lib, found the way ngspice finds it (the current folder first, then the folder of the
    including file). REFUSED, with the file, the line number and the line:
    - a command block (.control ... .endc) in an included file, whatever it holds; a first line *ng_script;
      an init file (.spiceinit, spice.rc) in the folder the engine starts in: ngspice executes all of these;
    - in a command block of the bench's own netlist: every command that is not in HARMLESS_COMMANDS (so shell,
      source, codemodel, osdi, load, write, wrdata, cd, set, edit, circbyline, the loops and all others), every
      line with > < ; or a backquote (output into a file, input from a file, a second command, a shell), and a
      continuation line;
    - a code model that starts a program (d_process) or loads a compiled library (d_cosim); a .sndparam or
      .sndprint line (they write a file);
    - an include, or the data file of a .model line (file=, input_file=, state_file=), outside the allowed
      folders: in an included file every absolute path; anywhere a network address, the home folder (~), a
      path whose target is not inside the folder of the calling bench script, a folder given with models=, the
      runner's tmpdir() or the folder of the including file; an include loop; includes nested deeper than
      MAX_INCLUDE_DEPTH.
    CANNOT RUN (not a refusal): an included file that is not there or is not text; a .lib line whose file name
    holds a blank (this ngspice cuts it at the blank). A refused model is corrected by hand in a copy (the
    lines removed, the change written down) or not used.
    Let pass on purpose: harmless commands in the bench's own netlist; data files of code models inside the
    allowed folders (they are read as numbers, not scanned); a sound file named by a source (file(...)); the
    user's own init file in the home folder; the commands a bench script gives itself with cmd(). The scan is a
    guard against the known ways, not a sandbox: read a downloaded model as well.

Compatibility mode (for models written for PSpice or LTspice)
    Modes: off (default), ps, psa, lt, lta, ltps, ltpsa: ngspice's `ngbehavior` (manual, "Compatibility"). ps is
    PSpice, lt is LTspice, a final "a" applies the translation to the whole netlist instead of the included
    files alone. The runner sets it before every netlist is read and checks the engine's own note of it.
    Which mode a bench runs in: its own --compat on its command line; else its own mode (COMPAT in
    tb_template.py, handed to run_tests(..., compat=MODE)) where that is other than off; else the mode of
    `suite --compat` (handed on in SIM_COMPAT); else off. run(..., compat=MODE) sets it for one run. The mode in force
    stands in every result line, in each row and at the top of every results file, and as "_compat" in every
    result of run(). A mode changes numbers: calibrate on a datasheet figure first, with a row whose limit is
    calibration(quantity, datasheet, tolerance, unit, source); the row records measured value, datasheet value,
    tolerance and the verdict.

Convergence check (run() and run_many() apply it; a failed check raises, it never returns numbers)
    - the engine's log names no error, no singular matrix, no "timestep too small", no failed or aborted analysis,
      no iteration limit;
    - a transient analysis reached its end time;
    - every returned value is a finite number, and no vector is empty.
    Looking at the plot stays the human's part: a run can converge to nonsense.

board.toml keys: none. Environment: NGSPICE_LIB (path of the shared library), KICAD_BIN (see kicad_io),
SIM_RUNNER (the folder of this file, set by `suite` for the test benches it starts), SIM_COMPAT (the mode of
`suite --compat`, for the benches whose own mode is off: they give run_tests() no mode).

Exit codes of the command line and of run_tests()
    0  every test PASS
    1  a test FAIL or NOT CONVERGED (`scan`: a file was REFUSED)
    2  CANNOT RUN: no ngspice, no numpy, a bench script that did not finish in time or crashed, a netlist or a
       model that the scan REFUSED, an included file that is missing, a mode that does not exist
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import atexit
import ctypes
import dataclasses
import datetime
import glob
import json
import math
import os
import pickle
import queue
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import kicad_io  # noqa: E402

DEFAULT_TIMEOUT = 600.0             # s: one simulation
SUITE_TIMEOUT = 3600.0              # s: one test bench script
KILL_GRACE = 30.0                   # s: a worker that does not come back this long after its time limit is killed
MEM_PER_WORKER_MB = 400             # free memory reserved per parallel engine

# What a log line must not say. The engine keeps going after some of these and leaves partial vectors behind.
_FATAL = re.compile(
    r"timestep too small|time step too small|singular matrix|no convergence|convergence (?:problem|failed)"
    r"|iteration limit reached|simulation\(s\) aborted|simulation aborted|analysis (?:failed|aborted)"
    r"|transient op failed|dc solution failed|gmin stepping failed|source stepping failed|op failed"
    r"|\berror\b|\bfatal\b|doanalyses", re.I)
_SUFFIX = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "mil": 25.4e-6, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12,
           "f": 1e-15}


class NgspiceError(RuntimeError):
    """The engine could not do what was asked (bad netlist, unknown vector)."""


class NgspiceNotFound(NgspiceError):
    """No ngspice shared library: nothing can be simulated (CANNOT RUN, never a pass)."""


class ConvergenceError(NgspiceError):
    """The run did not converge, did not finish, or gave values that are not numbers. It has no result."""

    def __init__(self, message: str, log: list[str] | None = None):
        super().__init__(message)
        self.log = log or []


class SimTimeout(ConvergenceError):
    """The run did not finish within its time limit."""


class ScanError(NgspiceError):
    """The netlist or a file it includes could not be scanned (a missing include, a file that is not text):
    CANNOT RUN, never a pass."""


class ModelRefused(ScanError):
    """The scan found something the simulator would execute or a path outside the allowed folders: the netlist
    does not reach the engine. The message starts with REFUSED and names the file, the line number and the line."""


# ---------------------------------------------------------------------------------------------------------------------
# the scan: what a netlist and the files it includes may make the simulator do
# ---------------------------------------------------------------------------------------------------------------------

MAX_INCLUDE_DEPTH = 10
INIT_FILES = (".spiceinit", "spice.rc")      # ngspice executes one of these from the folder it starts in
# What a command block in the bench's own netlist may hold. None of these starts a program, loads code, reads or
# writes a file, changes the folder, sets a variable of the engine, builds a circuit or loops (a loop that does not
# end would hang the load, outside the time limit). All others are refused.
HARMLESS_COMMANDS = frozenset(
    "alter alterparam compose define destroy display echo let meas option options print save setplot settype "
    "strcmp undefine unlet version if else end".split())
_NETLIST = "the netlist of the bench"
_INCLUDE = re.compile(r"\.(inc\w*|lib\w*)(?:\s+(.*))?$", re.I)       # ngspice takes every word that starts with .inc
_FILE_PARAM = re.compile(r"""\b(file|input_file|state_file)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s()]+))""", re.I)
_RUNS_CODE = {"d_process": "a code model that starts an external program",
              "d_cosim": "a code model that loads a compiled library"}


def _refuse(where: str, n: int, why: str, line: str):
    raise ModelRefused(f"REFUSED: {where}, line {n}: {why} | {line.strip()[:160]}")


def _inside(path: str, folder: str) -> bool:
    a, b = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(folder))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:                                   # another drive
        return False


def _caller_dir() -> str | None:
    """The folder of the script that called the runner. A netlist handed over in memory has no folder of its own:
    for the rule "the folder of the including file" the bench script that wrote it stands in."""
    mine = os.path.normcase(os.path.abspath(__file__))
    f = sys._getframe(1)
    while f is not None and os.path.normcase(os.path.abspath(f.f_code.co_filename)) == mine:
        f = f.f_back
    if f is None or not os.path.isfile(f.f_code.co_filename):
        return None
    return os.path.dirname(os.path.abspath(f.f_code.co_filename))


def _allowed(models, start: str | None) -> list[str]:
    """The folders a netlist may include from: `start`, the folders named with models=, the private tmpdir()."""
    extra = [models] if isinstance(models, str) else [str(m) for m in (models or ())]
    for m in extra:
        if not os.path.isdir(m):
            raise ScanError(f"the model folder {m} does not exist")
    return [os.path.realpath(p) for p in ([start] if start else []) + extra + ([_tmp] if _tmp else [])]


def _words(rest: str) -> list[str]:
    """The file name and the section of an include line, read as ngspice reads them: a name in quotes ends at
    the closing quote, any other at the next blank; an end-of-line comment ends the line."""
    out: list[str] = []
    rest = rest.strip()
    while rest and rest[0] not in "$;" and len(out) < 2:
        if rest[0] in "\"'":
            end = rest.find(rest[0], 1)
            if end < 0:
                raise ValueError("a quote that is not closed")
            out.append(rest[1:end])
            rest = rest[end + 1:]
            rest = rest[re.match(r"\S*", rest).end():].strip()    # what is glued to the quote is dropped, as there
        else:
            m = re.match(r"\S+", rest)
            out.append(m.group(0))
            rest = rest[m.end():].strip()
    return out


def _locate(name: str, folder: str | None, roots: list[str], where: str, n: int, line: str,
            maybe: bool = False) -> str | None:
    """The file that ngspice would read for `name`, or None when there is none. Refuses a name that leaves the
    allowed folders. `folder` is the folder of the including file (None for the netlist of the bench). `maybe`:
    the word may be no file name at all (.lib with one word starts a section); then only a file that exists
    is judged. A network address is refused before anything on the disk or the network is touched."""
    if re.match(r"\\\\|//|[a-z][a-z0-9+.-]+://", name, re.I):
        _refuse(where, n, "a network address as a file name", line)
    if name.startswith("~"):
        _refuse(where, n, "a file name in the home folder (~)", line)
    allowed = roots + ([folder] if folder else [])
    cwd = os.getcwd()
    absolute = bool(re.match(r"[a-z]:|[\\/]", name, re.I))
    cands =[name] if absolute else [os.path.join(cwd, name)] + ([os.path.join(folder, name)] if folder else [])
    found = next((c for c in cands if os.path.isfile(c)), None)          # ngspice's order: the current folder first
    if maybe and found is None:
        return None
    if absolute and folder:
        _refuse(where, n, "an absolute path in an included file (a model names its files beside itself)", line)
    if not absolute and not any(_inside(os.path.join(folder or cwd, name), a) for a in allowed):
        _refuse(where, n, "a path outside the folders allowed for models (the folder of the bench script, "
                          "folders named with models=, the folder of the including file)", line)
    if found is None:
        return None
    real = os.path.realpath(found)
    if not any(_inside(real, a) for a in allowed):
        _refuse(where, n, f"the simulator would read {real}, which is outside the folders allowed for models"
                + (" (it looks in the current folder first)" if folder and found == cands[0] else ""), line)
    return real


def _read_lines(path: str) -> list[str]:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ScanError(f"{path}: cannot be read ({e.strerror or e})") from None
    if b"\0" in data:
        raise ScanError(f"{path}: not a text file (binary or encrypted): it cannot be scanned, so it is not used")
    return re.split(r"\r\n|\n|\r", data.decode("latin-1"))


def _scan(lines: list[str], where: str, folder: str | None, roots: list[str], chain: list[str], seen: list[str]) -> None:
    """Scan the lines of one file (`folder` is its folder) or of the bench's netlist (`folder` is None), then
    every file it includes. `chain` is the list of files that led here, `seen` every file read so far."""
    block = False                                        # inside .control ... .endc of the bench's own netlist
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        low = line.lower()
        if n == 1 and low.startswith("*ng_script"):
            _refuse(where, n, "a first line that makes ngspice execute the whole text as commands", line)
        if not line or line.startswith("*"):
            continue
        if low.startswith(".control"):
            if folder is not None:
                _refuse(where, n, "a command block in an included file: ngspice would execute it", line)
            if low != ".control":
                _refuse(where, n, "text behind .control", line)
            block = True
        elif low.startswith(".endc"):
            block = False
        elif block:
            word = re.match(r"[a-z_]\w*", low)
            if not word or word.group(0) not in HARMLESS_COMMANDS:
                _refuse(where, n, f"the command '{word.group(0) if word else line[:1]}' is not one a netlist may give "
                                  "the simulator (it could start a program, load code, read or write a file); give "
                                  "it from the bench script, or leave it out", line)
            bad = next((c for c in "`;<>" if c in line), None)
            if bad:
                _refuse(where, n, f"a command line with {bad} (output into a file, input from a file, a second "
                                  "command or a shell); write gt and lt for a comparison", line)
        elif low.startswith(".snd"):
            _refuse(where, n, "a line that writes a sound file", line)
        else:
            m = _INCLUDE.match(line)
            if not m:
                continue
            lib = m.group(1).lower().startswith("lib")
            try:
                names = _words(m.group(2) or "")
            except ValueError as e:
                raise ScanError(f"{where}, line {n}: {e} | {line[:160]}") from None
            if not names:
                continue                                 # ngspice reports the missing name itself
            if lib and " " in names[0]:
                raise ScanError(f"{where}, line {n}: a .lib line cannot name a file with a blank in its path (this "
                                f"ngspice cuts the name at the blank); use .include, or a path without a blank | {line[:160]}")
            section = lib and len(names) > 1             # .lib <file> <section>; .lib <name> alone starts a section
            real = _locate(names[0], folder, roots, where, n, line, maybe=lib and not section)
            if real is None:
                if lib and not section:
                    continue
                raise ScanError(f"{where}, line {n}: the included file '{names[0]}' was not found | {line[:160]}")
            if real in chain:
                if not section:
                    _refuse(where, n, "an include loop: " + " -> ".join(
                        os.path.basename(p) for p in chain[chain.index(real):] + [real]), line)
                continue
            if real in seen:
                continue
            if len(chain) >= MAX_INCLUDE_DEPTH:
                _refuse(where, n, f"includes nested more than {MAX_INCLUDE_DEPTH} deep", line)
            seen.append(real)
            _scan(_read_lines(real), real, os.path.dirname(real), roots, chain + [real], seen)
    logical: list[list] = []                             # continuation lines joined: a .model line can span several
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+") and logical:
            logical[-1][1] += " " + line[1:]
        else:
            logical.append([n, line])
    for n, line in logical:
        for word, why in _RUNS_CODE.items():
            if re.search(rf"\b{word}\b", line, re.I):
                _refuse(where, n, f"{why} ({word})", line)
        if line.lower().startswith(".model"):
            for m in _FILE_PARAM.finditer(line):
                _locate(m.group(2) or m.group(3) or m.group(4), folder, roots, where, n, line)


def scan_netlist(netlist: str, models=(), _roots: list[str] | None = None) -> list[str]:
    """Scan a netlist held in memory and every file it includes; nothing is run. Returns the files read.
    Raises ModelRefused (see "The scan" at the top) or ScanError (a missing include, a file that is not text).
    Includes may point into the folder of the calling script, into `models` (a folder or a list of folders)
    and into tmpdir()."""
    roots = _roots if _roots is not None else _allowed(models, _caller_dir())
    seen: list[str] = []
    _scan(re.split(r"\r\n|\n|\r", netlist), _NETLIST, None, roots, [], seen)
    return seen


def scan_file(path: str, models=()) -> list[str]:
    """Scan a model file as an included file (so a command block in it is refused) and every file it includes;
    nothing is run. Returns the files read, `path` first. Includes may point into the file's own folder and
    into `models`."""
    if not os.path.isfile(path):
        raise ScanError(f"{path}: no such file")
    real = os.path.realpath(path)
    seen = [real]
    _scan(_read_lines(real), real, os.path.dirname(real), _allowed(models, None), [real], seen)
    return seen


# ---------------------------------------------------------------------------------------------------------------------
# the compatibility mode
# ---------------------------------------------------------------------------------------------------------------------

COMPAT_MODES = ("off", "ps", "psa", "lt", "lta", "ltps", "ltpsa")
_compat = ["off"]                   # the mode of this process: the bench's setting
_modes_used: list[str] = []         # the modes of the runs since run_tests() started its current test


def _mode(mode) -> str:
    m = "off" if mode is None or mode == "" else str(mode).strip().lower()
    if m not in COMPAT_MODES:
        raise ValueError(f"compat {mode!r} is not a compatibility mode: use one of {', '.join(COMPAT_MODES)}")
    return m


def set_compat(mode) -> str:
    """Set the compatibility mode for the runs of this process that name none; returns it. ValueError when it
    is not one of COMPAT_MODES."""
    _compat[0] = _mode(mode)
    return _compat[0]


# ---------------------------------------------------------------------------------------------------------------------
# numpy (hidden by `python -I` when it lives in the user's site-packages)
# ---------------------------------------------------------------------------------------------------------------------

def numpy():
    """The numpy module. `python -I` hides a numpy that was installed for the user alone; this finds it again, so
    a test bench writes `np = ngs.numpy()` instead of `import numpy as np`."""
    try:
        import numpy as _np
    except ImportError:
        kicad_io.add_user_site()
        try:
            import numpy as _np
        except ImportError:
            raise NgspiceError("numpy is not installed for this Python: the simulation runner needs it") from None
    return _np


_numpy = numpy


# ---------------------------------------------------------------------------------------------------------------------
# the engine: one per process
# ---------------------------------------------------------------------------------------------------------------------

class _VecInfo(ctypes.Structure):
    _fields_ = [("v_name", ctypes.c_char_p), ("v_type", ctypes.c_int), ("v_flags", ctypes.c_short),
                ("v_realdata", ctypes.POINTER(ctypes.c_double)), ("v_compdata", ctypes.c_void_p),
                ("v_length", ctypes.c_int)]


_SendChar = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
_SendStat = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
_Exit = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
_BGRun = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

LOG: list[str] = []                 # the engine's output of the current run
_lock = threading.RLock()
_lib = None
_info: dict = {}
_done = threading.Event()           # set when the background analysis has ended
_started = threading.Event()
_tmp: str | None = None
_seq = [0]


@_SendChar
def _send_char(msg, ident, user):
    LOG.append((msg or b"").decode(errors="replace"))
    return 0


@_SendStat
def _send_stat(msg, ident, user):
    return 0


@_Exit
def _exit(status, unload, quit_, ident, user):
    LOG.append(f"stderr Error: the engine asked to exit (status {status})")
    _done.set()
    return 0


@_BGRun
def _bg(not_running, ident, user):
    if not_running:
        _done.set()
    else:
        _started.set()
    return 0


def find_library() -> str:
    """The ngspice shared library: NGSPICE_LIB, else the one that comes with KiCad, else the system's."""
    forced = os.environ.get("NGSPICE_LIB")
    if forced:
        if not os.path.isfile(forced):
            raise NgspiceNotFound(f"NGSPICE_LIB is set to '{forced}', which is not a file")
        return forced
    kc = kicad_io.find_kicad()
    if kc is not None and kc.ngspice_lib:
        return kc.ngspice_lib
    import ctypes.util
    found = ctypes.util.find_library("ngspice")
    if found:
        return found
    raise NgspiceNotFound("no ngspice shared library found (it comes with KiCad; "
                          + (kicad_io.not_found_reason() or "KiCad was found, but without ngspice")
                          + "). Without it the simulation points are UNKNOWN and go to the bench list")


def _short(path: str) -> str:
    """A form of the path without blanks, where the system has one (the engine splits commands at blanks)."""
    if " " not in path or os.name != "nt":
        return path
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 1024)
    return buf.value if 0 < n < 1024 and " " not in buf.value else path


def _init():
    """Load and start the engine once per process."""
    global _lib
    if _lib is not None:
        return _lib
    with _lock:
        if _lib is not None:
            return _lib
        for name in INIT_FILES:
            init = os.path.join(os.getcwd(), name)
            if os.path.isfile(init):
                raise ModelRefused(f"REFUSED: {init}: an init file in the folder the simulator starts in; ngspice "
                                   "would execute every line of it as a command before the first netlist. Move it "
                                   "away (the compatibility mode is the bench's COMPAT setting, not an init file)")
        path = find_library()
        folder = os.path.dirname(os.path.abspath(path))
        if os.name == "nt" and os.path.isdir(folder):
            os.add_dll_directory(folder)
        try:
            lib = ctypes.CDLL(path)
        except OSError as e:
            raise NgspiceNotFound(f"the ngspice library {os.path.basename(path)} could not be loaded: {e}") from None
        lib.ngSpice_Command.argtypes = [ctypes.c_char_p]
        lib.ngSpice_Command.restype = ctypes.c_int
        lib.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        lib.ngSpice_Circ.restype = ctypes.c_int
        lib.ngGet_Vec_Info.argtypes = [ctypes.c_char_p]
        lib.ngGet_Vec_Info.restype = ctypes.POINTER(_VecInfo)
        lib.ngSpice_CurPlot.restype = ctypes.c_char_p
        lib.ngSpice_AllVecs.argtypes = [ctypes.c_char_p]
        lib.ngSpice_AllVecs.restype = ctypes.POINTER(ctypes.c_char_p)
        lib.ngSpice_running.restype = ctypes.c_bool
        lib.ngSpice_Init(_send_char, _send_stat, _exit, None, None, _bg, None)
        models = 0
        roots = [os.path.dirname(folder), folder]
        cands = [os.path.join(r, sub, "ngspice") for r in roots for sub in ("lib", "lib64", os.path.join("PlugIns", "sim"))]
        cands += ["/usr/lib/ngspice", "/usr/lib64/ngspice", "/usr/local/lib/ngspice"] + glob.glob("/usr/lib/*/ngspice")
        for d in cands:
            cms = sorted(glob.glob(os.path.join(d, "*.cm")))
            if not cms:
                continue
            for cm in cms:
                p = _short(cm)
                if " " in p:                         # no blank-free form: use a private copy
                    p = os.path.join(tmpdir(), os.path.basename(cm))
                    if not os.path.exists(p):
                        shutil.copyfile(cm, p)
                if " " not in p:
                    lib.ngSpice_Command(("codemodel " + p.replace(os.sep, "/")).encode())
                    models += 1
            break
        LOG.clear()
        lib.ngSpice_Command(b"version -s")
        m = re.search(r"ngspice-(\d+(?:\.\d+)*)", " ".join(LOG))
        _info.update(library=os.path.basename(path), version=("ngspice-" + m.group(1)) if m else "ngspice (version not read)",
                     code_models=models)
        LOG.clear()
        _lib = lib
    return _lib


def engine() -> dict:
    """{"library": file name, "version": "ngspice-NN", "code_models": count}. NgspiceNotFound when there is none."""
    _init()
    return dict(_info)


def tmpdir() -> str:
    """A temporary folder of this process alone (removed when the process ends)."""
    global _tmp
    if _tmp is None:
        _tmp = tempfile.mkdtemp(prefix=f"ngs_{os.getpid()}_")
        atexit.register(shutil.rmtree, _tmp, True)
    return _tmp


def tmpfile(suffix: str = "") -> str:
    """A new file name in tmpdir()."""
    _seq[0] += 1
    return os.path.join(tmpdir(), f"f{_seq[0]:06d}{suffix}")


def cmd(text: str) -> int:
    """One engine command (for the few things run() does not cover)."""
    return _init().ngSpice_Command(text.encode())


def spice_number(text: str) -> float:
    """'60u' -> 6e-5, '1meg' -> 1e6, '10ms' -> 0.01, '2.5e-3' -> 0.0025."""
    m = re.match(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)\s*([a-z]*)", text.strip().lower())
    if not m:
        raise ValueError(f"not a SPICE number: {text!r}")
    value, tail = float(m.group(1)), m.group(2)
    for suf in ("meg", "mil", "t", "g", "k", "m", "u", "n", "p", "f"):
        if tail.startswith(suf):
            return value * _SUFFIX[suf]
    return value


def _tran_stop(netlist: str, analysis: str | None) -> float | None:
    """The end time of the transient analysis that will run, or None when it is not a transient analysis."""
    line = None
    if analysis:
        if analysis.strip().lower().startswith("tran"):
            line = analysis.strip()
    else:
        for ln in netlist.splitlines():
            if ln.strip().lower().startswith(".tran"):
                line = ln.strip()[1:]
    if not line:
        return None
    parts = line.split()
    try:
        return spice_number(parts[2])
    except (IndexError, ValueError):
        return None


def _vector(lib, np, name: str):
    info = lib.ngGet_Vec_Info(name.encode())
    if not info:
        return None
    v = info.contents
    n = int(v.v_length)
    if n <= 0:
        return np.zeros(0)
    if v.v_flags & 2 and v.v_compdata:                                   # complex values: (re, im) pairs
        return np.frombuffer(ctypes.string_at(v.v_compdata, n * 16), dtype=np.complex128).copy()
    return np.ctypeslib.as_array(v.v_realdata, shape=(n,)).copy()


def run(netlist: str, vectors: list[str], analysis: str | None = None, timeout: float | None = None,
        check: bool = True, accept: tuple = (), models=(), compat: str | None = None,
        _roots: list[str] | None = None) -> dict:
    """Simulate one netlist in this process and return the vectors as numpy arrays.

    netlist   the circuit as text, without a .control section; its own .tran / .ac / .dc line runs unless
              `analysis` gives a command ("tran 1u 10m", "ac dec 50 10 1meg", "op"). It is scanned first, with
              every file it includes: ModelRefused or ScanError when it must not or cannot run
    models    a folder, or a list of folders, that the netlist may include from, beside the folder of the
              calling script (and what lies below it) and tmpdir()
    compat    the compatibility mode of this one run (one of COMPAT_MODES); None: the mode of the bench
    vectors   names or expressions ("v(out)", "i(vin)", "v(a)-v(b)"); the result holds them under the same text in
              lower case, plus the scale: "time", "frequency" or "sweep"
    timeout   seconds; a run that takes longer is stopped and raises SimTimeout (default DEFAULT_TIMEOUT)
    check     True (default): a run that failed the convergence check raises ConvergenceError and returns nothing.
              False: for finding out why; the result then carries "_converged": False and "_errors"
    accept    texts of log messages that are known and harmless for THIS bench (for example a start-up aid that
              failed before another one found the operating point). A log line that holds one of them does not
              fail the check; it is returned under "_accepted" and must be named, with the reason, in the results
              file. Never use it to pass a run that stopped early: the end-time and number checks still apply.
    Also in the result: "_log" (the engine's output), "_engine", "_converged", "_compat" (the mode in force).
    """
    np = _numpy()
    mode = _compat[0] if compat is None else _mode(compat)
    scan_netlist(netlist, _roots=_roots if _roots is not None else _allowed(models, _caller_dir()))
    lib = _init()
    limit = DEFAULT_TIMEOUT if timeout is None else float(timeout)
    with _lock:
        lib.ngSpice_Command(b"destroy all")
        lib.ngSpice_Command(b"remcirc")
        lib.ngSpice_Command(b"set sourcepath = ( . )")   # includes are found where the scan looked, nowhere else
        lib.ngSpice_Command(b"unset ngbehavior" if mode == "off" else f"set ngbehavior={mode}".encode())
        _modes_used.append(mode)
        LOG.clear()
        lines = [ln for ln in netlist.replace("\r\n", "\n").split("\n")]
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            raise NgspiceError("empty netlist")
        if lines[-1].strip().lower() != ".end":
            lines.append(".end")
        arr = (ctypes.c_char_p * (len(lines) + 1))(*[ln.encode() for ln in lines], None)
        lib.ngSpice_Circ(arr)
        load_log = list(LOG)
        bad = [ln for ln in load_log if re.search(r"\berror\b|unknown subckt|could not find|no such", ln, re.I)]
        if bad:
            raise NgspiceError("the netlist was not accepted: " + " | ".join(x.strip() for x in bad[:4]))
        said = next((ln for ln in load_log if "ompatibility mode" in ln), None)      # the engine's own note
        if said is not None:
            flags = set(said.split(":")[-1].split()) if "selected:" in said else set()
            want = {f for f in ("ps", "lt") if f in mode} | ({"a"} if mode.endswith("a") else set())
            if flags != want:
                raise NgspiceError(f"compat {mode} was asked for, but the engine says: {said.strip()}")
        _done.clear()
        _started.clear()
        lib.ngSpice_Command(("bg_" + (analysis or "run")).encode())
        t0 = time.monotonic()
        while not _done.wait(0.02):
            if _started.is_set() and not lib.ngSpice_running():
                break                                 # ended without the end notice
            if not _started.is_set() and time.monotonic() - t0 > 5.0 and not lib.ngSpice_running():
                break                                 # never started: the log says why
            if time.monotonic() - t0 > limit:
                lib.ngSpice_Command(b"bg_halt")
                _done.wait(10.0)
                log = list(LOG)
                lib.ngSpice_Command(b"destroy all")
                lib.ngSpice_Command(b"remcirc")
                raise SimTimeout(f"the simulation did not finish in {limit:g} s and was stopped", log)
        while lib.ngSpice_running():                  # the notice comes a moment before the thread has ended
            time.sleep(0.001)
        log = list(LOG)
        hits = [ln.strip() for ln in log if _FATAL.search(ln)]
        accepted = [ln for ln in hits if any(a and a.lower() in ln.lower() for a in accept)]
        errors = [ln for ln in hits if ln not in accepted]
        res: dict = {"_log": log, "_engine": _info.get("version", ""), "_accepted": accepted, "_compat": mode}
        plot = (lib.ngSpice_CurPlot() or b"").decode()
        scale_name, scale_key = None, None
        if plot.startswith("tran"):
            scale_name, scale_key = "time", "time"
        elif plot.startswith(("ac", "noise", "sp")):
            scale_name, scale_key = "frequency", "frequency"
        elif plot.startswith("dc"):
            names, i = [], 0
            allv = lib.ngSpice_AllVecs(plot.encode())
            while allv and allv[i]:
                names.append(allv[i].decode())
                i += 1
            scale_name = next((n for n in names if n.endswith("-sweep")), None)
            scale_key = "sweep"
        if scale_name:
            v = _vector(lib, np, scale_name)
            if v is not None:
                res[scale_key] = v.real.copy() if np.iscomplexobj(v) else v
        for i, expr in enumerate(vectors):
            LOG.clear()
            lib.ngSpice_Command(f"let ngs_out_{i} = {expr}".encode())
            v = _vector(lib, np, f"ngs_out_{i}")
            if v is None:
                why = " | ".join(x.strip() for x in LOG[-3:]) or "the engine gave no reason"
                errors.append(f"vector {expr!r} does not exist after the run ({why})")
                continue
            res[expr.lower()] = v
        stop = _tran_stop(netlist, analysis)
        if stop is not None and "time" in res:
            t = res["time"]
            if len(t) == 0 or float(t[-1]) < stop * (1 - 1e-9) - 1e-18:
                errors.append(f"the transient analysis stopped at {float(t[-1]) if len(t) else 0.0:g} s of {stop:g} s")
        for key, v in res.items():
            if key.startswith("_"):
                continue
            if len(v) == 0:
                errors.append(f"vector {key!r} is empty")
            elif not np.all(np.isfinite(v)):
                errors.append(f"vector {key!r} holds values that are not finite numbers")
        res["_converged"] = not errors
        res["_errors"] = errors
        if errors and check:
            raise ConvergenceError("the run has no result: " + " | ".join(dict.fromkeys(errors))[:900], log)
        return res


def complex_run(netlist: str, vectors: list[str], timeout: float | None = None) -> dict:
    """An AC analysis: "frequency" and complex vectors. The same as run(); kept as a name of its own."""
    return run(netlist, vectors, timeout=timeout, _roots=_allowed((), _caller_dir()))


# ---------------------------------------------------------------------------------------------------------------------
# many benches at once: one process and one engine each
# ---------------------------------------------------------------------------------------------------------------------

def free_memory_mb() -> float | None:
    """Free physical memory in MB, or None when the system does not say."""
    try:
        if os.name == "nt":
            class _Mem(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _Mem()
            m.dwLength = ctypes.sizeof(_Mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullAvailPhys / 2**20
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024
    except (OSError, AttributeError, ValueError):
        pass
    return None


def worker_count(jobs: int, asked: int | None = None) -> int:
    """All cores, but no more than the jobs, the free memory and what was asked for."""
    n = min(jobs, os.cpu_count() or 1)
    free = free_memory_mb()
    if free is not None:
        n = min(n, max(1, int(free // MEM_PER_WORKER_MB)))
    if asked:
        n = min(n, asked)
    return max(1, n)


def _send(stream, obj) -> None:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    stream.write(struct.pack("<Q", len(data)))
    stream.write(data)
    stream.flush()


def _recv(stream):
    head = stream.read(8)
    if len(head) < 8:
        return None
    (n,) = struct.unpack("<Q", head)
    data = stream.read(n)
    return pickle.loads(data) if len(data) == n else None


def _worker_main() -> int:
    """A worker process: jobs in through stdin, results out through the original stdout. Whatever the engine or
    a library prints goes to stderr, so it cannot damage the results."""
    out = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    inp = sys.stdin.buffer
    while True:
        job = _recv(inp)
        if job is None:
            return 0
        try:
            res = run(job["netlist"], job["vectors"], job.get("analysis"), job.get("timeout"),
                      accept=tuple(job.get("accept") or ()), compat=job.get("compat"), _roots=job.get("roots") or [])
            res.pop("_log", None)
            _send(out, ("ok", res))
        except Exception as e:  # noqa: BLE001 - every failure goes back to the parent as data
            _send(out, ("err", {"_error": str(e), "_kind": type(e).__name__, "_converged": False,
                                "_log": getattr(e, "log", [])[-40:]}))


class _Worker:
    def __init__(self, results: "queue.Queue"):
        self.proc = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "--worker"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.job: int | None = None
        self.since = 0.0
        self.reader = threading.Thread(target=self._read, args=(results,), daemon=True)
        self.reader.start()

    def _read(self, results):
        while True:
            try:
                msg = _recv(self.proc.stdout)
            except Exception:  # noqa: BLE001
                msg = None
            results.put((self, msg))
            if msg is None:
                return

    def give(self, index: int, job: dict) -> None:
        self.job, self.since = index, time.monotonic()
        _send(self.proc.stdin, job)

    def stop(self) -> None:
        try:
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(5)


def run_many(benches: list[dict], workers: int | None = None, timeout: float | None = None, models=()) -> list[dict]:
    """Simulate many benches at once. Each bench: {"netlist": text, "vectors": [...], "analysis": None, "name": "",
    "accept": (), "compat": None} (the last four are optional; see run()). `models`: as for run().

    Every netlist is scanned here, before any process starts: ModelRefused or ScanError when one of them must not
    or cannot run. Returns the results in the order of the benches. A bench that failed gives {"_converged":
    False, "_error": text, "_kind": name of the error} and no numbers. Every bench runs in a fresh engine of its
    own process, so the numbers are those of a serial run. A process that does not answer within the time limit
    is killed and its bench is reported as timed out; no process is left behind."""
    _numpy()
    roots = _allowed(models, _caller_dir())
    modes = [_compat[0] if b.get("compat") is None else _mode(b["compat"]) for b in benches]
    for b in benches:
        scan_netlist(b["netlist"], _roots=roots)
    find_library()                                       # fail here, once, when there is no engine
    limit = DEFAULT_TIMEOUT if timeout is None else float(timeout)
    n = len(benches)
    out: list[dict | None] = [None] * n
    if n == 0:
        return []
    results: queue.Queue = queue.Queue()
    pool = [_Worker(results) for _ in range(worker_count(n, workers))]
    todo = list(range(n))[::-1]
    try:
        while any(r is None for r in out):
            for w in pool:
                if w.job is None and todo and w.proc.poll() is None:
                    i = todo.pop()
                    w.give(i, {"netlist": benches[i]["netlist"], "vectors": benches[i]["vectors"],
                               "analysis": benches[i].get("analysis"), "timeout": limit,
                               "accept": benches[i].get("accept"), "compat": modes[i], "roots": roots})
            try:
                got = results.get(timeout=0.2)
            except queue.Empty:
                got = None
            if got is not None and got[0].job is not None:
                sender, msg = got
                i = sender.job
                if msg is None:                           # the process ended without an answer
                    out[i] = {"_converged": False, "_kind": "WorkerDied",
                              "_error": "the simulation process ended without a result (the engine crashed?)"}
                    pool[pool.index(sender)] = _Worker(results)
                else:
                    out[i] = msg[1]
                    sender.job = None
            now = time.monotonic()
            for k, w in enumerate(pool):
                if w.job is not None and now - w.since > limit + KILL_GRACE:
                    out[w.job] = {"_converged": False, "_kind": "SimTimeout",
                                  "_error": f"no answer within {limit + KILL_GRACE:g} s: the process was killed"}
                    w.job = None
                    w.proc.kill()
                    pool[k] = _Worker(results)
    finally:
        for w in pool:
            w.stop()
    done = [r if r is not None else {"_converged": False, "_kind": "NoResult", "_error": "no result"} for r in out]
    for i, r in enumerate(done):
        r.setdefault("_name", benches[i].get("name", f"bench {i + 1}"))
        r.setdefault("_compat", modes[i])
    _modes_used.extend(modes)
    return done


# ---------------------------------------------------------------------------------------------------------------------
# tests with limits that are written first
# ---------------------------------------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Limit:
    """A pass limit for one measured quantity: lo <= value <= hi (either side may be open). `why` names where the
    limit comes from (a requirement, a datasheet page). It cannot be changed after it was made."""
    quantity: str
    lo: float | None = None
    hi: float | None = None
    unit: str = ""
    why: str = ""

    def __post_init__(self):
        if self.lo is None and self.hi is None:
            raise ValueError(f"limit for {self.quantity!r} has neither a lower nor an upper bound: that is no limit")
        if self.lo is not None and self.hi is not None and self.lo > self.hi:
            raise ValueError(f"limit for {self.quantity!r}: lower bound above upper bound")

    def text(self) -> str:
        u = f" {self.unit}" if self.unit else ""
        if self.lo is not None and self.hi is not None:
            return f"{self.lo:g} <= {self.quantity} <= {self.hi:g}{u}"
        return f"{self.quantity} >= {self.lo:g}{u}" if self.lo is not None else f"{self.quantity} <= {self.hi:g}{u}"

    def ok(self, value) -> bool:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(v) and (self.lo is None or v >= self.lo) and (self.hi is None or v <= self.hi)


@dataclasses.dataclass(frozen=True)
class Calibration(Limit):
    """A Limit that is a figure of the part's datasheet with its tolerance. Made with calibration()."""
    datasheet: float = math.nan
    tolerance: float = math.nan

    def text(self) -> str:
        u = f" {self.unit}" if self.unit else ""
        return f"{self.quantity} = {self.datasheet:g} +/- {self.tolerance:g}{u} (datasheet)"


def calibration(quantity: str, datasheet: float, tolerance: float, unit: str = "", source: str = "") -> Calibration:
    """The limit of a calibration row: the bench reproduces one figure of the part's datasheet at the datasheet's
    own conditions, and the model must give it within `tolerance` (an absolute value, in `unit`). `source` names
    the document and the table or figure. Use it as the limit of a normal Test, before any test that relies on
    a maker's model run in a compatibility mode or on a behavioural model; the results row then records the
    measured value, the datasheet value, the tolerance and PASS or FAIL."""
    datasheet, tolerance = float(datasheet), float(tolerance)
    if not (math.isfinite(datasheet) and math.isfinite(tolerance) and tolerance > 0):
        raise ValueError(f"calibration of {quantity!r}: a datasheet value and a tolerance above zero are needed")
    if not source.strip():
        raise ValueError(f"calibration of {quantity!r}: name the source (document, table or figure) of the value")
    return Calibration(quantity, datasheet - tolerance, datasheet + tolerance, unit,
                       "calibration on a datasheet figure: " + source.strip(), datasheet, tolerance)


@dataclasses.dataclass(frozen=True)
class Test:
    """One test of a bench. `limits` are written here, before anything runs. `measure` is a function without
    arguments that runs the simulation and returns {"quantity": value, ...} (and may write a plot); its values
    are judged against the limits by run_tests(), not by the function itself."""
    id: str
    question: str
    limits: tuple
    measure: Callable[[], dict]
    plot: str = ""

    def __post_init__(self):
        if not self.limits or not all(isinstance(x, Limit) for x in self.limits):
            raise ValueError(f"test {self.id}: declare at least one Limit before the run")
        if not callable(self.measure):
            raise ValueError(f"test {self.id}: measure must be a function")


def run_tests(bench: str, tests: list[Test], out_dir: str, declared: str | None = None,
              compat: str | None = None) -> int:
    """Run the tests of one bench, judge each against its declared limits, write <out_dir>/<bench>_results.json
    and print one line per test. Returns the exit code (0 all PASS, 1 FAIL or NOT CONVERGED, 2 CANNOT RUN).

    compat   the compatibility mode of the bench (one of COMPAT_MODES). None (tb_template.py gives None when its
             COMPAT is off and no --compat was given): the mode of `suite --compat` (SIM_COMPAT), else off. Every
             line and every row states the mode its runs were really made in."""
    os.makedirs(out_dir, exist_ok=True)
    getattr(kicad_io, "safe_output", lambda: None)()        # a unit sign in a question must not stop the bench
    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    asked = compat if compat is not None else os.environ.get("SIM_COMPAT") or "off"
    try:
        mode = set_compat(asked)
        eng = engine()
    except ValueError as e:
        mode, eng = f"{asked} (not a mode)", {"version": None, "error": str(e)}
    except NgspiceError as e:
        mode, eng = _compat[0], {"version": None, "error": str(e)}
    rows = []
    for t in tests:
        row: dict = {"id": t.id, "question": t.question, "limits": [{"limit": x.text(), "from": x.why} for x in t.limits],
               "plot": t.plot, "measured": None, "verdict": None, "detail": "", "compat": mode}
        _modes_used.clear()
        if eng.get("version") is None:
            row.update(verdict="CANNOT RUN", detail=eng.get("error", "no engine"))
        else:
            try:
                measured = t.measure()
                missing = [x.quantity for x in t.limits if x.quantity not in measured]
                if missing:
                    row.update(verdict="FAIL", measured=_plain(measured),
                               detail="the test did not measure: " + ", ".join(missing))
                else:
                    failed = [f"{x.text()} but {x.quantity} = {float(measured[x.quantity]):g}" for x in t.limits
                              if not x.ok(measured[x.quantity])]
                    row.update(verdict="FAIL" if failed else "PASS", measured=_plain(measured), detail="; ".join(failed))
            except ConvergenceError as e:               # no numbers: a run that did not converge has no result
                row.update(verdict="NOT CONVERGED", detail=str(e)[:600])
            except NgspiceNotFound as e:
                row.update(verdict="CANNOT RUN", detail=str(e))
            except ScanError as e:                      # refused by the scan, or an include that is missing
                row.update(verdict="CANNOT RUN", detail=str(e)[:900])
            except NgspiceError as e:
                row.update(verdict="NOT CONVERGED", detail="the bench could not run: " + str(e)[:500])
            except Exception as e:  # noqa: BLE001 - a fault of the bench script is not a verdict on the circuit
                import traceback
                where = traceback.extract_tb(e.__traceback__)[-1]
                row.update(verdict="CANNOT RUN", detail=f"the bench script failed: {type(e).__name__}: {e} "
                                                        f"(line {where.lineno} of {os.path.basename(where.filename)})")
        if _modes_used:                                 # the modes the runs of this test were really made in
            row["compat"] = " + ".join(dict.fromkeys(_modes_used))
        got = row["measured"] or {}
        cal = [{"quantity": x.quantity, "measured": got.get(x.quantity), "datasheet": x.datasheet,
                "tolerance": x.tolerance, "unit": x.unit, "source": x.why,
                "verdict": ("PASS" if x.ok(got[x.quantity]) else "FAIL") if x.quantity in got else row["verdict"]}
               for x in t.limits if isinstance(x, Calibration)]
        if cal:
            row["calibration"] = cal
        rows.append(row)
        shown = "; ".join(f"{k} = {v:g}" if isinstance(v, float) else f"{k} = {v}" for k, v in (row["measured"] or {}).items())
        print(f"{row['verdict']:13} {t.id}  {t.question}  [limit: {'; '.join(x.text() for x in t.limits)}]"
              + f"  [compat {row['compat']}]"
              + (f"  measured: {shown}" if shown else "") + (f"  ({row['detail']})" if row["detail"] else ""))
    count = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("PASS", "FAIL", "NOT CONVERGED", "CANNOT RUN")}
    n_cal = sum(1 for r in rows if r.get("calibration"))
    result = {"bench": bench, "limits_written": declared or started, "run_started": started,
              "run_finished": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
              "engine": eng.get("version"), "compat": mode, "calibration_rows": n_cal, "counts": count, "tests": rows,
              "note": "limits are part of each test's declaration and were fixed before the run; a test that did "
                      "not converge has no measured values; compat is the ngspice compatibility mode the runs "
                      "were made in (off: none): a number of a mode other than off is to be trusted only after a "
                      "calibration row on a datasheet figure has passed with the same model in the same mode"}
    path = os.path.join(out_dir, f"{bench}_results.json")
    tmp = path + f".tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)
    print(f"{bench}: {count['PASS']} PASS, {count['FAIL']} FAIL, {count['NOT CONVERGED']} NOT CONVERGED, "
          f"{count['CANNOT RUN']} CANNOT RUN; compat {mode}"
          + (f", {n_cal} calibration row(s)" if n_cal or mode != "off" else "") + f"; results {path}")
    if count["CANNOT RUN"]:
        return 2
    return 1 if count["FAIL"] or count["NOT CONVERGED"] else 0


def _plain(measured: dict) -> dict:
    out: dict = {}
    for k, v in measured.items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# a suite of test bench scripts, each in its own process
# ---------------------------------------------------------------------------------------------------------------------

def run_suite(scripts: list[str], workers: int | None = None, timeout: float = SUITE_TIMEOUT,
              out_dir: str | None = None, compat: str | None = None) -> list[dict]:
    """Run test bench scripts (tb_*.py) at once, each with `python -I`, and collect their exit codes.
    A script that does not finish in `timeout` seconds is killed and reported as CANNOT RUN. `compat` is handed
    to the scripts in SIM_COMPAT; each result names the mode its script stated ("compat")."""
    env = dict(os.environ, SIM_RUNNER=_HERE)
    if compat is not None:
        env["SIM_COMPAT"] = _mode(compat)
    n = worker_count(len(scripts), workers)
    todo = list(enumerate(scripts))[::-1]
    running: list[tuple[int, str, subprocess.Popen, float, str]] = []
    out: list[dict | None] = [None] * len(scripts)
    while todo or running:
        while todo and len(running) < n:
            i, s = todo.pop()
            logf = tmpfile(".log")
            args = [sys.executable, "-I", os.path.abspath(s)] + (["--out", out_dir] if out_dir else [])
            with open(logf, "wb") as lf:
                p = subprocess.Popen(args, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                     cwd=os.path.dirname(os.path.abspath(s)))
            running.append((i, s, p, time.monotonic(), logf))
        time.sleep(0.1)
        for item in list(running):
            i, s, p, t0, logf = item
            code = p.poll()
            took = time.monotonic() - t0
            if code is None and took <= timeout:
                continue
            if code is None:
                p.kill()
                p.wait(10)
                code, verdict = 2, f"CANNOT RUN (killed after {timeout:g} s)"
            else:
                verdict = {0: "PASS", 1: "FAIL"}.get(code, "CANNOT RUN")
            with open(logf, encoding="utf-8", errors="replace") as lf:
                tail = lf.read().strip().splitlines()[-25:]
            stated = [m.group(1) for m in (re.search(r"; compat ([^;,]+)", ln) for ln in tail) if m]
            out[i] = {"script": os.path.basename(s), "exit": code, "verdict": verdict, "seconds": round(took, 1),
                      "compat": stated[-1] if stated else "not stated", "output": tail}
            running.remove(item)
    return out  # type: ignore[return-value]


# ---------------------------------------------------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------------------------------------------------

RC_STEP = """RC step: 1 kohm and 1 uF, a 5 V step at t = 0
V1 in 0 PWL(0 0 1n 5)
R1 in out 1k
C1 out 0 1u
.tran 10u 5m
"""
NO_SOLUTION = """a node whose value has no solution: it must be 0 when it is above 0.5 and 1 when it is below
B1 out 0 V = v(out) > 0.5 ? 0 : 1
R1 out 0 1k
.tran 10u 1m
"""


def _self_test() -> int:
    np = numpy()
    r = run(RC_STEP, ["v(out)"])
    v1 = float(np.interp(1e-3, r["time"], r["v(out)"]))
    want = 5 * (1 - math.exp(-1))
    ok = abs(v1 - want) < 0.01
    print(f"{'PASS' if ok else 'FAIL'}  RC step: v(out) at one time constant = {v1:.4f} V, formula {want:.4f} V, "
          f"limit +/- 0.01 V ({_info.get('version')}, compat {r['_compat']})")
    try:
        run(NO_SOLUTION, ["v(out)"], timeout=60)
        print("FAIL  a bench that cannot converge returned numbers")
        ok = False
    except ConvergenceError as e:
        print(f"PASS  a bench that cannot converge is refused (compat {_compat[0]}): {str(e)[:110]}")
    return 0 if ok else 1


def _scan_files(files: list[str], models: list[str]) -> int:
    """`scan`: each model file with all it includes; nothing is run. 0 nothing refused, 1 REFUSED, 2 cannot scan."""
    worst = 0
    for f in files:
        try:
            read = scan_file(f, models)
            print(f"PASS  scan {f}: {len(read)} file(s) read, nothing refused"
                  + ("" if len(read) == 1 else ": " + ", ".join(read)))
        except ModelRefused as e:
            print(f"{e}  [scan of {f}: do not use this file as it is]")
            worst = max(worst, 1)
        except ScanError as e:
            print(f"CANNOT RUN: scan of {f}: {e}")
            worst = 2
    return worst


def main(argv: list[str]) -> int:
    if argv[:1] == ["--worker"]:
        return _worker_main()
    import argparse
    ap = argparse.ArgumentParser(description="ngspice runner: engine, self-test, or a suite of test bench scripts.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("engine", help="which ngspice was found")
    sub.add_parser("self-test", help="an RC step against its formula; a bench that cannot converge must be refused")
    su = sub.add_parser("suite", help="run test bench scripts (tb_*.py) at once, each in its own process")
    su.add_argument("paths", nargs="+", help="folders (their tb_*.py) or scripts")
    su.add_argument("--jobs", type=int, help="processes at once (default: all cores, limited by free memory)")
    su.add_argument("--timeout", type=float, default=SUITE_TIMEOUT, help="seconds per script")
    su.add_argument("--out", help="results folder handed to every script as --out, and for suite_results.json")
    su.add_argument("--compat", choices=COMPAT_MODES, help="compatibility mode for the benches whose own mode (COMPAT) "
                    "is off; a bench that sets another mode keeps it, and a bench's own --compat wins over both "
                    "(default: each bench's own mode, else off)")
    sc = sub.add_parser("scan", help="scan model files and every file they include; nothing is run")
    sc.add_argument("files", nargs="+", help="model files (a command block in them is refused)")
    sc.add_argument("--models", action="append", default=[], metavar="DIR",
                    help="a further folder that includes may point into (each file's own folder always is one)")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_usage(sys.stderr)
        return 2
    if a.cmd == "scan":
        return _scan_files(a.files, a.models)
    try:
        info = engine()
    except NgspiceError as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2
    if a.cmd == "engine":
        print(f"{info['version']}  library {info['library']}  code models loaded: {info['code_models']}")
        return 0
    if a.cmd == "self-test":
        return _self_test()
    scripts: list[str] = []
    for p in a.paths:
        if os.path.isdir(p):
            scripts += sorted(glob.glob(os.path.join(p, "tb_*.py")))
        elif os.path.isfile(p):
            scripts.append(p)
        else:
            print(f"CANNOT RUN: {p} not found", file=sys.stderr)
            return 2
    if not scripts:
        print("CANNOT RUN: no test bench script (tb_*.py) found", file=sys.stderr)
        return 2
    t0 = time.monotonic()
    res = run_suite(scripts, a.jobs, a.timeout, a.out, a.compat)
    for r in res:
        print(f"{r['verdict']:28} {r['script']}  ({r['seconds']} s)  [compat {r['compat']}]")
        if r["exit"] != 0:
            for line in r["output"][-6:]:
                print("      " + line)
    bad = [r for r in res if r["exit"] == 1]
    cannot = [r for r in res if r["exit"] not in (0, 1)]
    out_dir = a.out or os.path.dirname(os.path.abspath(scripts[0]))
    summary = {"date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "engine": info["version"],
               "compat_option": a.compat, "seconds": round(time.monotonic() - t0, 1), "scripts": res,
               "result": "CANNOT RUN" if cannot else ("FAIL" if bad else "PASS")}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "suite_results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1)
        f.write("\n")
    print(f"suite: {summary['result']} - {len(res) - len(bad) - len(cannot)} of {len(res)} bench script(s) passed, "
          f"{len(bad)} failed, {len(cannot)} could not run, {summary['seconds']} s, {info['version']}")
    return 2 if cannot else (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
