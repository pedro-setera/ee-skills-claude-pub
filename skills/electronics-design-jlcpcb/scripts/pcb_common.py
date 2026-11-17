"""Shared frame of the board checks: where the inputs and results are, the settings, a private working copy of
a board, a plain-data picture of a board for scripts that cannot import pcbnew, and the result files.

Why it exists
    Every board check answers the same questions before it can start: which board, where do the results go, which
    limits apply, and how do I read the board without touching the user's files. Answered once here, the checks
    cannot disagree about it. A check that reads a board in place can leave KiCad lock files beside it or rewrite
    its project file; a check that crashes half way can be read as a pass. Hence: a private copy for every read,
    and one way to write a result.

What it gives
    io_parser(description, ...)      argparse parser with the two call forms of every project script
    resolve(args, result_name)       -> Job: .board .out .project .settings .cfg(section) .source_note
    Limits(section, defaults, cli)   settings with their origin (command line, board.toml or default), printable
    quiet_wx(), run_guarded()        the same as kicad_io.quiet_wx and kicad_io.run_guarded (no window, ever)
    scrub(text or data)              result files without this machine's folder names
    work_copy(board)                 context manager: a private copy of the board (project and rule file with it);
                                     3D model paths that point beside the original still resolve
    read_board(board_copy, origin)   plain-data picture of a board (dict, mm, KiCad's frame: x right, y down)
    dump_board(pcbnew_board, origin) the same, inside KiCad's Python
    write_result(out, base, md, data)  the Markdown result and its JSON twin, atomically
    header(title, job, script)       the first lines of every Markdown result
    mm(), poly_points(), bbox_of(), box_gap(), pt_box() ...   small geometry helpers

    Run as a program it writes the picture of one board:
        <KiCad python> -I pcb_common.py --dump <board.kicad_pcb> <out.json> [--origin <folder of the original>]

board.toml keys read here (all optional)
    [project] name, kicad_dir, out_dir       see kicad_io
    [holes] refs = ["H1", "H2"]              footprints that are mounting holes (default: found by library or
                                             footprint name, value or reference, or a one-pad footprint with a
                                             single hole of min_d or more)
    [holes] min_d = 2.0                      smallest single hole taken as a mounting hole when not named
    [connectors] refs = ["J*", "P*", "CN*", "X*", "USB*"]   reference patterns of connectors

Exit codes (as a program): 0 written, 2 could not run.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import contextlib
import datetime
import fnmatch
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402

DUMP_TIMEOUT = 900.0
CONNECTOR_PATTERNS = ("J*", "P*", "CN*", "CON*", "X*", "USB*")
HOLE_MIN_D = 2.0
_HOLE_WORDS = ("mountinghole", "mounting_hole", "mount_hole", "mounthole")
_HOLE_REF = re.compile(r"^(H|MH|MK|MP|MNT)\d+$", re.I)


# ---- inputs, outputs, settings ---------------------------------------------------------------------------------------
class Job:
    """What a check works on. board: the board file (None when the script takes other inputs); out: the results
    folder (created); project: the board folder or None; settings: board.toml as a dict ({} without one)."""

    def __init__(self, board, out, project, settings, source_note):
        self.board, self.out, self.project, self.settings, self.source_note = board, out, project, settings, source_note

    def cfg(self, section: str) -> dict:
        v = self.settings.get(section, {})
        return v if isinstance(v, dict) else {}

    def path(self, value: str) -> str:
        """A path from board.toml (relative to the board folder) or from the command line (as given)."""
        if os.path.isabs(value) or not self.project:
            return os.path.abspath(value)
        return os.path.normpath(os.path.join(self.project, value))


def io_parser(description: str, board: bool = True, epilog: str | None = None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description, epilog=epilog,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    if board:
        ap.add_argument("board", nargs="?", help="a .kicad_pcb file (with --out); not needed with --project")
    ap.add_argument("--project", help="the board folder (reads board.toml there; results go to <project>/out/)")
    ap.add_argument("--out", help="results folder (needed without --project)")
    return ap


def resolve(args, need_board: bool = True, sub_out: str = "") -> Job:
    """The Job for parsed arguments. --project: board.toml is read, the board is the project's, results go to
    <project>/out/<sub_out>. Otherwise: the given board and --out. Neither: KicadIOError (exit code 2)."""
    board = getattr(args, "board", None)
    if args.project:
        proj = os.path.abspath(args.project)
        settings = kicad_io.load_settings(proj)
        files = kicad_io.project_files(proj, settings)
        b = os.path.abspath(board) if board else files["pcb"]
        out = os.path.abspath(args.out) if args.out else os.path.join(files["out"], sub_out) if sub_out else files["out"]
        note = "board.toml" if settings else "no board.toml: defaults"
        if need_board and not b:
            raise kicad_io.KicadIOError(f"{proj}: no board file (.kicad_pcb) found in the project")
    else:
        if not args.out:
            raise kicad_io.KicadIOError("give --project <board folder>, or the input file(s) with --out <folder>")
        if need_board and not board:
            raise kicad_io.KicadIOError("give a board file (.kicad_pcb) or --project <board folder>")
        proj, settings, b, out, note = None, {}, (os.path.abspath(board) if board else None), os.path.abspath(args.out), \
            "no board.toml (explicit paths): defaults"
    if b and not os.path.isfile(b):
        raise kicad_io.KicadIOError(f"no such board file: {b}")
    if b and proj is None:
        # never write into the folder of a design that is not a project of this skill
        if os.path.normcase(os.path.abspath(out)) == os.path.normcase(os.path.dirname(b)):
            raise kicad_io.KicadIOError("--out must not be the folder of the input design")
    os.makedirs(out, exist_ok=True)
    # what result files say instead of these folders (see scrub): results must not carry a user's folder names
    inside = proj and os.path.normcase(out).startswith(os.path.normcase(proj) + os.sep)
    _ROOTS[:] = ([(proj, "")] if proj else []) + ([] if inside else [(out, "" if not proj else "<results folder>")]) + \
        ([(os.path.dirname(b), "<design folder>")] if b and not proj else [])
    return Job(b, out, proj, settings, note)


_ROOTS: list[tuple[str, str]] = []              # (a folder, the name result files use for it), set by resolve()


def scrub(obj):
    """A text, or a value for a JSON file, without the absolute folders of this machine. Result files are read
    by other people and by the privacy scan: a path below the board folder (or, without one, below the results
    folder) is written relative to it; KiCad's own library folder becomes <KiCad>, the temporary folder <temp>,
    the user's home folder ~. Nothing else is changed."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [scrub(v) for v in obj]
    if not isinstance(obj, str) or ("\\" not in obj and "/" not in obj):
        return obj
    import tempfile
    kc = kicad_io.find_kicad()
    tmp = tempfile.gettempdir()
    roots = _ROOTS + ([(kc.share_dir, "<KiCad>")] if kc and kc.share_dir else []) + \
        [(tmp, "<temp>"), (os.path.realpath(tmp), "<temp>"), (os.path.expanduser("~"), "~")]
    for root, name in sorted(roots, key=lambda r: len(r[0]), reverse=True):
        for form in {root, root.replace("\\", "/"), root.replace("\\", "\\\\")}:
            if form in obj:
                pre = name + "/" if name else ""
                obj = obj.replace(form + "\\\\", pre).replace(form + "\\", pre).replace(form + "/", pre).replace(form, name or ".")
    return obj


class Limits:
    """Settings of one check with their origin: command line, then board.toml, then the default.

        lim = Limits(job.cfg("silk"), {"min_height": 1.0, ...}, {"min_height": args.min_height})
        lim["min_height"]; lim.table() -> Markdown lines "| setting | value | from |" """

    def __init__(self, section: dict, defaults: dict, cli: dict | None = None):
        self.values, self.origin = {}, {}
        cli = cli or {}
        for k, d in defaults.items():
            if cli.get(k) is not None:
                self.values[k], self.origin[k] = cli[k], "command line"
            elif k in section:
                v = section[k]
                if isinstance(d, float) and isinstance(v, int) and not isinstance(v, bool):
                    v = float(v)
                if d is not None and not isinstance(v, type(d)) and not (isinstance(d, float) and isinstance(v, float)):
                    raise kicad_io.KicadIOError(f"board.toml: '{k}' must be of type {type(d).__name__}, got {v!r}")
                self.values[k], self.origin[k] = v, "board.toml"
            else:
                self.values[k], self.origin[k] = d, "default"

    def __getitem__(self, k):
        return self.values[k]

    def table(self) -> list[str]:
        out = ["| Setting | Value | From |", "|---|---|---|"]
        for k, v in self.values.items():
            out.append(f"| `{k}` | {json.dumps(v) if not isinstance(v, str) else v} | {self.origin[k]} |")
        return out

    def to_dict(self) -> dict:
        return {k: {"value": v, "from": self.origin[k]} for k, v in self.values.items()}


def header(title: str, job: Job, script: str, board: str | None = None) -> list[str]:
    """First lines of a Markdown result: what was checked, when, with which KiCad and which settings."""
    b = board or job.board
    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    kc = kicad_io.find_kicad()
    lines = [f"# {title}", "", f"Script `{script}`, run {when}; settings: {job.source_note}."]
    if b:
        lines.append(f"Board `{os.path.basename(b)}`, SHA-256 `{kicad_io.sha256(b)}`"
                     + (f"; KiCad {kc.version}." if kc else "."))
    if kc and kc.note:
        lines.append(f"Note: {kc.note}.")
    return lines + [""]


def write_result(out: str, base: str, md: list[str] | str, data: dict) -> tuple[str, str]:
    """Write <out>/<base>.md and <out>/<base>.json (without this machine's folders: see scrub); returns both paths."""
    os.makedirs(out, exist_ok=True)
    text = md if isinstance(md, str) else "\n".join(md) + "\n"
    p_md, p_js = os.path.join(out, base + ".md"), os.path.join(out, base + ".json")
    kicad_io.atomic_write(p_md, scrub(text))
    kicad_io.atomic_write(p_js, json.dumps(scrub(data), indent=1, ensure_ascii=False) + "\n")
    return p_md, p_js


def verdict(n_fail: int, n_unknown: int = 0) -> str:
    if n_fail:
        return "FAIL"
    return "FAIL (UNKNOWN items are not a pass)" if n_unknown else "PASS"


# ---- working copy ----------------------------------------------------------------------------------------------------
_MODEL = re.compile(r'(\(model\s+")(\$\{KIPRJMOD\}|\$\(KIPRJMOD\))')


@contextlib.contextmanager
def work_copy(board: str, prefix: str = "board-check-"):
    """A private copy of the board (its project and rule file with it) in a temporary folder of this process;
    yields the copy's path. 3D models named relative to the project (${KIPRJMOD}) are pointed at the original
    folder, so renders and STEP exports of the copy still find them. Nothing is written beside the original."""
    with kicad_io.private_tmp(prefix) as tmp:
        copy = os.path.join(tmp, os.path.basename(board))
        kicad_io.copy_board(board, copy, lock_source=False)
        origin = os.path.dirname(os.path.abspath(board)).replace("\\", "/")
        with open(copy, encoding="utf-8", newline="") as f:
            txt = f.read()
        new = _MODEL.sub(lambda m: m.group(1) + origin, txt)
        if new != txt:
            kicad_io.atomic_write(copy, new)
        yield copy


# ---- small geometry (boxes are (x0, y0, x1, y1) in mm) ------------------------------------------------------------------
def box_gap(a, b) -> float:
    """Distance between two boxes (0 when they touch or overlap)."""
    return math.hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))


def pt_box(x, y, bx) -> float:
    return math.hypot(max(bx[0] - x, 0.0, x - bx[2]), max(bx[1] - y, 0.0, y - bx[3]))


def box_union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def pts_box(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _orient(ax, ay, bx, by, cx, cy):
    v = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return 0 if abs(v) < 1e-15 else (1 if v > 0 else -1)


def seg_seg(a, b):
    """Distance between two segments (ax, ay, bx, by); 0 when they cross."""
    (ax, ay, bx, by), (cx, cy, dx, dy) = a, b
    o1, o2 = _orient(ax, ay, bx, by, cx, cy), _orient(ax, ay, bx, by, dx, dy)
    o3, o4 = _orient(cx, cy, dx, dy, ax, ay), _orient(cx, cy, dx, dy, bx, by)
    if o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4):
        return 0.0
    return min(pt_seg(ax, ay, cx, cy, dx, dy), pt_seg(bx, by, cx, cy, dx, dy), pt_seg(cx, cy, ax, ay, bx, by),
               pt_seg(dx, dy, ax, ay, bx, by))


def inside(px, py, poly):
    c = False
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if (ay > py) != (by > py) and px < (bx - ax) * (py - ay) / (by - ay) + ax:
            c = not c
    return c


def poly_box(p):
    xs, ys = [q[0] for q in p], [q[1] for q in p]
    return (min(xs), min(ys), max(xs), max(ys))


def poly_dist(a, b, far=99.0):
    """Distance between two polygons (point lists); 0 when they touch or overlap."""
    if inside(a[0][0], a[0][1], b) or inside(b[0][0], b[0][1], a):
        return 0.0
    best = far
    na, nb = len(a), len(b)
    for i in range(na):
        ea = (a[i][0], a[i][1], a[(i + 1) % na][0], a[(i + 1) % na][1])
        for j in range(nb):
            d = seg_seg(ea, (b[j][0], b[j][1], b[(j + 1) % nb][0], b[(j + 1) % nb][1]))
            if d < best:
                best = d
                if d == 0.0:
                    return 0.0
    return best


def poly_circle(p, cx, cy, r):
    """Distance between a polygon and a circle; 0 when they touch or overlap."""
    if inside(cx, cy, p):
        return 0.0
    n = len(p)
    return max(0.0, min(pt_seg(cx, cy, p[i][0], p[i][1], p[(i + 1) % n][0], p[(i + 1) % n][1]) for i in range(n)) - r)


# ---- edge keep-out bands (a board that slides in slots or rails) ---------------------------------------------------------
EDGES = ("left", "right", "top", "bottom")


def edge_bands(job: "Job", bbox) -> tuple[list[dict], str]:
    """The edge keep-out bands of a project: (bands, where they come from). Read from board.toml [[keepout.band]];
    when there is none, from the "keepouts" list of <project>/mech/outline.json (entries with "kind": "band").

        name    = "left rail"
        edge    = "left"              # left, right, top or bottom of the board's box, as seen in the top view
        line    = [x0, y0, x1, y1]    # instead of edge: a segment in KiCad's frame (mm); the band lies on the side
                                      # of the line toward the board's centre
        width   = 3.0                 # mm from the edge (or line) that must stay free
        sides   = "both"              # "top", "bottom" or "both" (default)
        span    = [a, b]              # optional, with edge: only between these coordinates along the edge (y for
                                      # left and right, x for top and bottom)
        copper_to_edge = 2.0          # optional: copper-to-edge limit along this edge (edge_check.py)
        allow_exposed_copper = false  # true: exposed copper in the band is reported, not failed
        height  = 8.0                 # optional: mm above each named side that the band reaches (body_check.py);
                                      # not given: no limit, any part body over the band counts

    Each band comes back with "line" (the guided edge as a segment), "length", "poly" (its four corners) and "box"."""
    raw, src = job.cfg("keepout").get("band", []), "board.toml"
    if not raw and job.project:
        path = os.path.join(job.project, "mech", "outline.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError) as e:
                raise kicad_io.KicadIOError(f"{path}: {e}") from None
            raw = [k for k in data.get("keepouts", []) if isinstance(k, dict) and k.get("kind", "band") == "band"
                   and ("edge" in k or "line" in k)] if isinstance(data.get("keepouts"), list) else []
            src = "mech/outline.json"
    out = []
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    for i, r in enumerate(raw):
        name = str(r.get("name", f"band {i + 1}"))
        try:
            width = float(r["width"])
        except (KeyError, TypeError, ValueError):
            raise kicad_io.KicadIOError(f"keep-out band '{name}': width (mm) is missing") from None
        sides = r.get("sides", "both")
        if width <= 0 or sides not in ("both", "top", "bottom"):
            raise kicad_io.KicadIOError(f"keep-out band '{name}': width must be positive and sides top, bottom or both")
        if "line" in r:
            ln = [float(v) for v in r["line"]]
            if len(ln) != 4:
                raise kicad_io.KicadIOError(f"keep-out band '{name}': line needs [x0, y0, x1, y1]")
        elif r.get("edge") in EDGES:
            e = r["edge"]
            a, b = (bbox[1], bbox[3]) if e in ("left", "right") else (bbox[0], bbox[2])
            if r.get("span"):
                a, b = max(a, min(r["span"])), min(b, max(r["span"]))
            ln = {"left": [bbox[0], a, bbox[0], b], "right": [bbox[2], a, bbox[2], b],
                  "top": [a, bbox[1], b, bbox[1]], "bottom": [a, bbox[3], b, bbox[3]]}[e]
        else:
            raise kicad_io.KicadIOError(f"keep-out band '{name}': give edge (left, right, top, bottom) or line")
        length = math.hypot(ln[2] - ln[0], ln[3] - ln[1])
        if length <= 0:
            raise kicad_io.KicadIOError(f"keep-out band '{name}': the edge stretch has no length")
        ux, uy = (ln[2] - ln[0]) / length, (ln[3] - ln[1]) / length
        nx, ny = -uy, ux
        if nx * (cx - (ln[0] + ln[2]) / 2) + ny * (cy - (ln[1] + ln[3]) / 2) < 0:
            nx, ny = -nx, -ny                                          # the normal points into the board
        poly = [(ln[0], ln[1]), (ln[2], ln[3]), (ln[2] + nx * width, ln[3] + ny * width),
                (ln[0] + nx * width, ln[1] + ny * width)]
        out.append({"name": name, "edge": r.get("edge", "line"), "width": width, "sides": sides, "line": ln,
                    "length": length, "u": (ux, uy), "n": (nx, ny), "poly": poly, "box": poly_box(poly),
                    "copper_to_edge": float(r["copper_to_edge"]) if r.get("copper_to_edge") is not None else None,
                    "height": float(r["height"]) if r.get("height") is not None else None,
                    "allow_exposed_copper": bool(r.get("allow_exposed_copper", False))})
    return out, src


def band_reach(band: dict, poly) -> float | None:
    """How near a polygon comes to the guided edge of a band: its smallest distance from the edge line, measured
    into the board, over the part of the polygon that lies along the band's stretch; None when the polygon is not
    along that stretch. Negative: it hangs over the edge. Under the band's width: it is inside the band."""
    (ux, uy), (nx, ny), ln, length = band["u"], band["n"], band["line"], band["length"]
    uv = [((x - ln[0]) * ux + (y - ln[1]) * uy, (x - ln[0]) * nx + (y - ln[1]) * ny) for x, y in poly]
    vs = [v for u, v in uv if -1e-9 <= u <= length + 1e-9]
    n = len(uv)
    for i in range(n):
        (u0, v0), (u1, v1) = uv[i], uv[(i + 1) % n]
        for lim in (0.0, length):
            if (u0 - lim) * (u1 - lim) < 0:
                vs.append(v0 + (v1 - v0) * (lim - u0) / (u1 - u0))
    return min(vs) if vs else None


def matches(ref: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(ref, p) for p in patterns)


def natural(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# ---- no window, ever: the two helpers live in kicad_io.py, for every script; these names stay for the board checks
quiet_wx = kicad_io.quiet_wx
run_guarded = kicad_io.run_guarded


# ---- pcbnew side (KiCad's Python only) ---------------------------------------------------------------------------------
def _pcbnew():
    import pcbnew
    return pcbnew


def mm(v) -> float:
    return _pcbnew().ToMM(v)


def poly_points(ps) -> list:
    """SHAPE_POLY_SET -> [[outer, hole, ...], ...] with points in mm."""
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        loops = [[(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())]]
        for h in range(ps.HoleCount(i)):
            hh = ps.Hole(i, h)
            loops.append([(mm(hh.CPoint(k).x), mm(hh.CPoint(k).y)) for k in range(hh.PointCount())])
        out.append(loops)
    return out


def bbox_of(item) -> tuple:
    bb = item.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))


def shape_box(shape) -> tuple:
    bb = shape.BBox()
    return (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))


def board_outline(board):
    """(SHAPE_POLY_SET or None, note). None when the Edge.Cuts drawing is not a closed outline."""
    pcbnew = _pcbnew()
    ps = pcbnew.SHAPE_POLY_SET()
    try:
        try:
            ok = board.GetBoardPolygonOutlines(ps)
        except TypeError:                                               # KiCad 10: a second argument, "infer an outline
            ok = board.GetBoardPolygonOutlines(ps, False)               # if necessary": never, an outline is not guessed
    except Exception as e:                                              # an outline KiCad cannot chain
        return None, f"the board outline could not be built ({e})"
    if not ok or ps.OutlineCount() == 0:
        return None, "the Edge.Cuts drawing is not a closed outline"
    return ps, ""


def side_layers(side: str) -> dict:
    """Layer ids of one side: 'top' or 'bottom'."""
    p = _pcbnew()
    if side == "top":
        return {"cu": p.F_Cu, "silk": p.F_SilkS, "fab": p.F_Fab, "crtyd": p.F_CrtYd, "mask": p.F_Mask, "paste": p.F_Paste}
    return {"cu": p.B_Cu, "silk": p.B_SilkS, "fab": p.B_Fab, "crtyd": p.B_CrtYd, "mask": p.B_Mask, "paste": p.B_Paste}


def fp_side(fp) -> str:
    return "bottom" if fp.IsFlipped() else "top"


def fp_body_box(fp):
    """The part body seen from above: the box of the footprint's fabrication-layer drawing on its own side
    (texts left out), or None when the footprint has none."""
    lay = side_layers(fp_side(fp))["fab"]
    boxes = [bbox_of(g) for g in fp.GraphicalItems()
             if g.GetLayer() == lay and g.GetClass() not in ("PCB_TEXT", "PCB_FIELD", "PCB_TEXTBOX")]
    return box_union(boxes)


def fp_courtyard(fp):
    """(polygons, box) of the courtyard on the footprint's own side; ([], None) without a courtyard.
    The polygon is KiCad's own (the one its rule check uses): the centre line of the courtyard drawing, less
    0.005 mm. The box is the box of that polygon's points. (KiCad's own box of this shape is larger by the width
    of the courtyard lines on every side, 0.05 mm for the usual line: it is not used.)"""
    try:
        fp.BuildCourtyardCaches()
    except Exception:
        pass
    c = fp.GetCourtyard(side_layers(fp_side(fp))["crtyd"])
    if c.OutlineCount() == 0:
        return [], None
    polys = poly_points(c)
    pts = [p for poly in polys for p in poly[0]]
    return polys, (pts_box(pts) if pts else shape_box(c))


def fp_part_box(fp):
    """Body plus pads: what a label must sit next to. Falls back to the courtyard, then to the pads alone."""
    body = fp_body_box(fp) or fp_courtyard(fp)[1]
    return box_union([body] + [bbox_of(p) for p in fp.Pads()])


def is_mounting_hole(fp_info: dict, cfg: dict) -> bool:
    """A footprint that is a mounting hole: named in board.toml; or recognised by its library, footprint name,
    value or reference (and it has a drilled hole); or a footprint with one single drilled position of
    [holes] min_d or more and no second pad number (a one-pad part used as a mounting hole)."""
    refs = cfg.get("refs")
    if refs:
        return matches(fp_info["ref"], refs)
    drilled = [p for p in fp_info["pads"] if p["drill"]]
    if not drilled:
        return False
    lib, _, name = fp_info["lib"].lower().rpartition(":")
    named = lib.replace("_", "") in ("mountinghole", "mountingholes") or name.startswith(_HOLE_WORDS) or         fp_info["value"].lower().startswith(_HOLE_WORDS) or bool(_HOLE_REF.match(fp_info["ref"]))
    if named:
        return True
    spots = {(round(p["x"], 2), round(p["y"], 2)) for p in drilled}
    numbers = {p["num"] for p in fp_info["pads"]}
    return len(spots) == 1 and len(numbers) <= 1 and min(drilled[0]["drill"]) >= float(cfg.get("min_d", HOLE_MIN_D))


def is_connector(fp_info: dict, cfg: dict) -> bool:
    return matches(fp_info["ref"], cfg.get("refs", CONNECTOR_PATTERNS))


def _model_path(name: str, origin: str, kc) -> str | None:
    """The file a footprint's 3D model name points at, or None when it cannot be found."""
    def sub(m):
        var = m.group(1) or m.group(2)
        if var == "KIPRJMOD":
            return origin
        if os.environ.get(var):
            return os.environ[var]
        if re.fullmatch(r"KICAD\d*_3DMODEL_DIR|KISYS3DMOD", var) and kc and kc.share_dir:
            return os.path.join(kc.share_dir, "3dmodels")
        return m.group(0)
    path = re.sub(r"\$\{(\w+)\}|\$\((\w+)\)", sub, name)
    if not os.path.isabs(path):
        path = os.path.join(origin, path)
    path = os.path.normpath(path)
    stem = os.path.splitext(path)[0]
    for cand in (path, stem + ".step", stem + ".stp", stem + ".STEP", stem + ".wrl"):
        if os.path.isfile(cand):
            return cand
    return None


def dump_board(board, origin: str) -> dict:
    """The plain-data picture of a loaded board. origin: the folder of the ORIGINAL board file (for ${KIPRJMOD})."""
    pcbnew = _pcbnew()
    kc = kicad_io.find_kicad()
    ps, note = board_outline(board)
    if ps is not None:
        loops = poly_points(ps)
        allpts = [p for poly in loops for p in poly[0]]
        bbox = pts_box(allpts)
        outline = {"ok": True, "polygons": loops, "note": ""}
    else:
        eb = board.GetBoardEdgesBoundingBox()
        bbox = (mm(eb.GetX()), mm(eb.GetY()), mm(eb.GetRight()), mm(eb.GetBottom()))
        if bbox[2] - bbox[0] <= 0 or bbox[3] - bbox[1] <= 0:
            fb = board.ComputeBoundingBox(False)
            bbox = (mm(fb.GetX()), mm(fb.GetY()), mm(fb.GetRight()), mm(fb.GetBottom()))
            note += "; no Edge.Cuts drawing: the box of all items is used"
        outline = {"ok": False, "polygons": [], "note": note}
    cu = [board.GetLayerName(lay) for lay in board.GetEnabledLayers().CuStack()]
    d = {"file": os.path.basename(board.GetFileName()), "kicad": pcbnew.GetBuildVersion(), "bbox": list(bbox),
         "outline": outline, "thickness": mm(board.GetDesignSettings().GetBoardThickness()), "copper_layers": cu,
         "footprints": [], "vias": [], "holes": []}
    attr_name = {pcbnew.PAD_ATTRIB_PTH: "pth", pcbnew.PAD_ATTRIB_SMD: "smd", pcbnew.PAD_ATTRIB_NPTH: "npth",
                 pcbnew.PAD_ATTRIB_CONN: "conn"}
    for fp in board.GetFootprints():
        side = fp_side(fp)
        lay = side_layers(side)
        pos = fp.GetPosition()
        cpoly, cbox = fp_courtyard(fp)
        pads = []
        for p in fp.Pads():
            pp = p.GetPosition()
            ds = p.GetDrillSize()
            drill = [mm(ds.x), mm(ds.y)] if p.HasHole() and ds.x > 0 else None
            on = [n for n, lid in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)) if p.IsOnLayer(lid)]
            plated = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
            pads.append({"num": str(p.GetNumber()), "net": str(p.GetNetname()), "x": mm(pp.x), "y": mm(pp.y),
                         "drill": drill, "plated": plated, "kind": attr_name.get(p.GetAttribute(), "other"),
                         "layers": "".join(on), "box": list(bbox_of(p))})
            if drill:
                d["holes"].append({"x": mm(pp.x), "y": mm(pp.y), "d": drill[0], "d2": drill[1], "plated": plated,
                                   "ref": fp.GetReference(), "pad": str(p.GetNumber()), "net": str(p.GetNetname())})
        models = []
        for m in fp.Models():
            models.append({"file": str(m.m_Filename), "resolved": _model_path(str(m.m_Filename), origin, kc),
                           "offset": [m.m_Offset.x, m.m_Offset.y, m.m_Offset.z],
                           "rotation": [m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z],
                           "scale": [m.m_Scale.x, m.m_Scale.y, m.m_Scale.z], "show": bool(m.m_Show)})
        a = fp.GetAttributes()
        kind = "smd" if a & pcbnew.FP_SMD else ("tht" if a & pcbnew.FP_THROUGH_HOLE else "other")
        ref = fp.Reference()
        d["footprints"].append({
            "ref": fp.GetReference(), "value": fp.GetValue(), "lib": fp.GetFPID().GetUniStringLibId(), "side": side,
            "x": mm(pos.x), "y": mm(pos.y), "rot": fp.GetOrientationDegrees(), "kind": kind,
            "dnp": bool(fp.IsDNP()), "exclude_pos": bool(fp.IsExcludedFromPosFiles()),
            "exclude_bom": bool(fp.IsExcludedFromBOM()), "board_only": bool(a & pcbnew.FP_BOARD_ONLY),
            "body": list(fp_body_box(fp)) if fp_body_box(fp) else None,
            "courtyard": cpoly, "courtyard_box": list(cbox) if cbox else None,
            "box": list(fp_part_box(fp) or (mm(pos.x), mm(pos.y), mm(pos.x), mm(pos.y))),
            "ref_on_silk": bool(ref.IsVisible() and ref.GetLayer() == lay["silk"]),
            "pads": pads, "models": models})
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            d["vias"].append({"x": mm(p.x), "y": mm(p.y), "d": mm(t.GetWidth(pcbnew.F_Cu)), "drill": mm(t.GetDrill()),
                              "net": str(t.GetNetname())})
    d["footprints"].sort(key=lambda f: natural(f["ref"]))
    return d


def read_board(board_copy: str, origin: str | None = None, timeout: float = DUMP_TIMEOUT) -> dict:
    """The plain-data picture of a board file. Use it on a copy the script owns (see work_copy). With pcbnew at
    hand the board is loaded here; otherwise KiCad's Python is started for it."""
    origin = origin or os.path.dirname(os.path.abspath(board_copy))
    try:
        _pcbnew()
    except ImportError:
        pass
    else:
        quiet_wx()
        return dump_board(kicad_io.load_board(board_copy), origin)
    with kicad_io.private_tmp("board-dump-") as tmp:
        js = os.path.join(tmp, "board.json")
        cmd = [kicad_io.kicad_python(), "-I", "-B", os.path.abspath(__file__), "--dump", board_copy, js, "--origin", origin]
        rc, text, blocked = run_guarded(cmd, timeout)
        if blocked or rc != 0 or not os.path.isfile(js):
            raise kicad_io.KicadIOError(f"the board could not be read with KiCad's Python: {blocked or text.strip()[-800:]}")
        with open(js, encoding="utf-8") as f:
            return json.load(f)


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Write the plain-data picture of a board (run with KiCad's Python).")
    ap.add_argument("--dump", nargs=2, metavar=("BOARD", "JSON"), required=True)
    ap.add_argument("--origin", help="folder of the original board (for 3D models named relative to the project)")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    quiet_wx()
    board, out = a.dump
    data = dump_board(kicad_io.load_board(board), a.origin or os.path.dirname(os.path.abspath(board)))
    kicad_io.atomic_write(out, json.dumps(data))
    return 0


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(_main))
