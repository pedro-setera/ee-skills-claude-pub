"""Run the whole check suite of a board and write the one-page result: out/CHECKS.md.

What it does
    Runs every check script of the skill on one board folder, several at once where they cannot disturb each
    other, and writes `out/CHECKS.md` in the shape of templates/CHECKS.md: one row per check with the script,
    the result (PASS, FAIL, CANNOT RUN, NOT APPLICABLE) and the evidence file. The headline counts the four
    apart, for example "NOT PASSED: 4 passed, 4 failed, 12 could not run, 3 not applicable", and one line says
    what the checks that could not run need (the board folder, the schematic, the Gerbers, or their own rows).
    A check that could not run is never a pass: it keeps the suite from passing exactly as a failed one does.
    Every script reads the saved board or the exported files itself; nothing is taken from an earlier result.
    The JSON twin `out/CHECKS.json` holds the same counts, the commands, exit codes, times and the last lines
    each script printed.

    Order: first the schematic export (it writes the netlist that others read), then all other checks at once,
    then the rows that only read other rows' results (the edge-band row), then the privacy scan over the
    finished results folder. The board file's checksum is taken before and after: a board that changed during
    the run fails the whole page.

    What stays the designer's: the rows marked BY HAND (the heat table, the EMC look at the tiles), and the
    three sections under the table (planted-defect proof, images looked at, root causes). Whatever the designer
    wrote there in an earlier CHECKS.md is kept when the page is written again.

Why it exists (real failures, told without names)
    Checks were run one by one, some on an older board file than others, and a summary was typed by hand from
    memory: "all clean" while two reports belonged to the board before the last fix. One command, one run, one
    board checksum, one page ends that. And a check that silently did not run looked like a pass: here it is
    a row that says CANNOT RUN, never counted as a pass. On a design brought in without a board folder most rows
    cannot run, and a headline "16 FAIL" read as sixteen faults in the user's board: so could not run is counted
    apart from failed.

Usage
    python -I check_all.py --project <hardware/board folder>             everything; out/CHECKS.md
    python -I check_all.py <board.kicad_pcb> --out <folder> [--schematic ROOT.kicad_sch] [--gerbers FOLDER]
                                                                          a design without a board folder: the
                                                                          checks that need only these inputs
    options: --only a,b / --skip a,b (row keys; the page is then marked INCOMPLETE), --list (print the rows),
             --jobs N (checks at once; default half the cores), --timeout S (per check; default 3600)
    Before it: the trial export (fab_package.py; with a panel also panel.py and fab_package.py on the panel board into out/panel/jlc/) and interface_export.py, whose
    files several rows read. No row goes to a supplier's site: the stock row reads the saved answers only, and
    fails when an answer it uses is older than [bom] max_age_hours or has no date; refresh them first with
    `python -I scripts/jlc_parts.py --project <board folder> --live bom-check` (with the user's yes).

board.toml keys read here (all optional; every script reads its own keys)
    [project] name, kicad_dir, out_dir       see kicad_io.py
    [bom] max_age_hours = 24                 the stock row: hours that a saved supplier answer may be old (default
                                             24, "dated today"); handed to jlc_parts.py as --max-age-hours
    [panel] ...                              a panel is expected when this table exists (see panel.py)
    [check_all] skip = ["sim"]               rows that this project leaves out, by key (they are listed as left
                                             out, and the page is INCOMPLETE)

Exit codes
    0  every check that applies ran and passed
    1  a check failed or could not run, a row was left out, or the board changed during the run
    2  CANNOT RUN: no board folder or board file, a row key that does not exist

Adding a row (a later check script)
    Append a Row to ROWS: its place on the page (the order number: rows are sorted by it; leave gaps), a short
    key, the texts of the first two columns, the evidence file, and the command as a list that starts with the
    script's name. The call form is added for you: `--project <folder>`, or for a design without a board
    folder the board (explicit="board") or the root schematic (explicit="schematic") with `--out` (without
    `explicit` the row says that it needs a board folder); put "{io}" into the list where these arguments
    belong when that is not the end. Optional: stage (1 before the others, 2 with the others, 3 for a row that
    reads other rows' results of the same run, 4 after all), applies(ctx) -> "" or why the row does not apply,
    detail(ctx) -> the numbers for the result column, read from the script's JSON twin (for a row without a
    command: the pair (state, text)). A row whose key ROWS already has replaces the earlier row: no row twice.
        Row(125, "mycheck", "What it checks, in a few words", "`my_check.py`", "out/my_check.md", ["my_check.py"]),

Not checked by this script: whether a limit in board.toml is the right one; anything a row says is BY HAND;
the images (review_images.py makes them; looking is the designer's and the reviewers' work).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import glob
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402

ROW_TIMEOUT = 3600.0
STOCK_MAX_AGE_H = 24.0      # h: the stock row fails on saved supplier answers older than this ([bom] max_age_hours)
_PATH = re.compile(r"""(?<![\w.~>])(?:[A-Za-z]:[\\/]+|/)(?:[^\\/\s"'`|<>:*?]+[\\/]+)+([^\\/\s"'`|<>:*?]+)""")  # any other absolute path
HAND_SECTIONS = "## Planted-defect proof for each new custom check"
HAND_TEMPLATE = [
    HAND_SECTIONS,
    "| Check | Defect planted in a copy | Check failed as expected? |", "|---|---|---|",
    "| <`silk_check.py`> | <text moved onto a pad> | <yes> |", "",
    "## Images the designer looked at",
    "| Image | Path | What I saw and fixed |", "|---|---|---|",
    "| <Top 3D, bottom 3D, angled> | <`out/review/`> | <label R4 touched a via, moved> |",
    "| <Silkscreen plot, copper plots> | <`out/review/`> | <ok> |",
    "| <Zoom tiles: every hole, connector, label cluster> | <`out/review/`, named in `out/review/index.md`> | <ok> |", "",
    "## Root cause of any defect that got through earlier",
    "<One line per defect: what, why the earlier check missed it, which check now catches it.>"]


class Ctx:
    """What a run works on. mode "project": a board folder; mode "explicit": single files and an --out folder."""

    def __init__(self, mode, project, board, schematic, gerbers, out, settings):
        self.mode, self.project, self.board, self.schematic = mode, project, board, schematic
        self.gerbers, self.out, self.settings = gerbers, out, settings
        self.name = os.path.splitext(os.path.basename(board))[0] if board else (os.path.basename(project) if project else "board")
        self.rows: dict[str, dict] = {}         # key -> result of the rows that have run

    def p(self, *parts: str) -> str:
        """A path below the board folder (project mode) or below --out."""
        return os.path.join(self.project if self.mode == "project" else self.out, *parts)

    def clean(self, text: str) -> str:
        """Text for the page: a path below the board folder becomes relative (pcb_common.scrub), any other
        absolute path is cut to its last part. The page lies in the results folder, which the privacy scan reads."""
        return _PATH.sub(r".../\1", pcb_common.scrub(text))

    def json(self, name: str):
        """A script's JSON twin from the results folder, or None."""
        try:
            with open(os.path.join(self.out, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None


class Row:
    """One row of CHECKS.md. cmd: the command after `python -I scripts/` as a list, or a function
    ctx -> list of such lists (several commands for one row); None for a row that runs nothing."""

    def __init__(self, order, key, check, script, evidence, cmd=None, explicit=None, stage=2, applies=None, detail=None,
                 by_hand=False):
        self.order, self.key, self.check, self.script, self.evidence = order, key, check, script, evidence
        self.cmd, self.explicit, self.stage, self.applies, self.detail, self.by_hand = cmd, explicit, stage, applies, detail, by_hand


# ---- what some rows need to know ---------------------------------------------------------------------------------------
def _panel_board(ctx):
    hits = sorted(glob.glob(os.path.join(glob.escape(ctx.out), "panel", "board", "*.kicad_pcb")))
    return hits[0] if len(hits) == 1 else None


def _panel_applies(ctx):
    if ctx.mode != "project":
        return "a panel is checked from its board folder (--project)"
    if _panel_board(ctx) or "panel" in ctx.settings:
        return ""
    return "the project has no panel (no [panel] table in board.toml, no out/panel/)"


def _panel_cmds(ctx):
    board = _panel_board(ctx)
    if not board:
        raise kicad_io.KicadIOError("board.toml has a [panel] table but out/panel/board/ holds no panel board: run panel.py first")
    pdir = os.path.join(ctx.out, "panel")
    cmds = [["drc_run.py", board, "--out", pdir, "--no-parity"]]
    bom, cpl = glob.glob(os.path.join(glob.escape(pdir), "*-bom.csv")), glob.glob(os.path.join(glob.escape(pdir), "*-cpl.csv"))
    if len(bom) == 1 and len(cpl) == 1:
        vendor = ctx.p(str(ctx.settings.get("rotations", {}).get("vendor", os.path.join("vendor", "jlc_fp"))))
        cmds.append(["jlc_rotations.py", "--project", ctx.project, "--out", pdir, "--bom", bom[0], "--vendor", vendor, "test", board, "--cpl", cpl[0]])
    else:
        raise kicad_io.KicadIOError("out/panel/ holds no single panel BOM and placement file to derive again: run panel.py "
                                    "after fab_package.py")
    return cmds


def _pinfn_applies(ctx):
    """"" when the pin-function row applies, else why not (no programmable part declared). The script itself knows;
    it is asked only where the real script stands beside this file. Anything that cannot be said means "applies":
    the script then runs and gives its own result."""
    if ctx.mode != "project":
        return ""
    try:
        with open(os.path.join(_HERE, "pin_function_check.py"), encoding="utf-8") as f:
            if "def not_applicable(" not in f.read():
                return ""
        import pin_function_check
        return pin_function_check.not_applicable(ctx.project) or ""
    except Exception:                                               # noqa: BLE001 - never let this helper stop the suite
        return ""


def _stock_limit(ctx) -> float:
    """[bom] max_age_hours of board.toml, else 24: the age in hours that a saved supplier answer may have."""
    bom = ctx.settings.get("bom", {})
    v = bom.get("max_age_hours", STOCK_MAX_AGE_H) if isinstance(bom, dict) else STOCK_MAX_AGE_H
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        raise kicad_io.KicadIOError(f"board.toml [bom] max_age_hours must be a number of hours, not {v!r}")
    return float(v)


def _stock_cmds(ctx):
    return [["jlc_parts.py", "{io}", "--offline", "bom-check", "--max-age-hours", f"{_stock_limit(ctx):g}"]]


def _stock_detail(ctx):
    """The counts of the stock check, and the age of the saved answers it used against the limit; when they are too
    old (or carry no date), the command that refreshes them."""
    js = ctx.json("BOM_STOCK_CHECK.json")
    c, limit, age = js["counts"], _stock_limit(ctx), js.get("answers_age_hours")
    text = (f"{c['in_stock']} of {c['lines']} line(s) in stock, {c['short']} short, {c['unknown']} UNKNOWN, "
            f"{c['no_number']} without a valid LCSC number")
    if js["stale"]:
        return ("STALE: " + (f"the saved answers are {age:.0f} h old, over the limit of {limit:g} h" if age is not None
                             else "the saved answers carry no date")
                + "; refresh them with `python -I scripts/jlc_parts.py --project <board folder> --live bom-check` "
                  "(the user's yes); " + text)
    return text + (f"; saved answers {age:.0f} h old (limit {limit:g} h)" if age is not None else "")


def _sim_applies(ctx):
    if ctx.mode != "project":
        return "simulations belong to a board folder (--project)"
    return "" if glob.glob(os.path.join(glob.escape(ctx.p("sim")), "tb_*.py")) else \
        "no test bench (sim/tb_*.py) in the board folder"


def _edge_cmd(ctx):
    if ctx.mode == "project":
        return [["edge_check.py", "--project", ctx.project]]
    if not ctx.gerbers:
        raise kicad_io.KicadIOError("no Gerber folder was given (--gerbers): the exported files cannot be measured")
    return [["edge_check.py", "--gerbers", ctx.gerbers, "--out", ctx.out]]


def _edge_detail(ctx):
    js = ctx.json("edge_check.json")
    parts = []
    for run in js["runs"]:
        mins = [f"{r['min']:.3f}" if r["min"] is not None else "far" for r in run["layers"]]
        parts.append(f"{run['which']}: min {min(mins)} mm over {len(mins)} copper layers (limit {run['limit']:.2f})")
    return "; ".join(parts)


def _silk_detail(ctx):
    js = ctx.json("silk_check.json")
    return f"{len(js['findings'])} finding(s), {len(js['info']['unlabelled'])} part(s) without a label, {len(js['info']['waived'])} waived"


def _body_detail(ctx):
    js = ctx.json("body_check.json")
    if js.get("outline_unknown"):
        return "UNKNOWN: " + js["outline_unknown"]
    if js["bodies"] is None:
        return "no CadQuery: bodies were not measured; the visual review must carry it"
    return f"{len(js['bodies'])} bodies, {len(js['holes'])} hole rows, {len(js['failures'])} failure(s), {len(js['unknown'])} unknown"


def _bands(ctx):
    """The edge-band row: nothing is run; the results of body_check.py (check D) and edge_check.py are read."""
    body, edge = ctx.json("body_check.json"), ctx.json("edge_check.json")
    if body is None:
        return "CANNOT RUN", "body_check.py wrote no result"
    if body.get("outline_unknown"):
        return "CANNOT RUN", "UNKNOWN: " + body["outline_unknown"] + ": the bands cannot be drawn"
    edge_rows = [b for run in (edge or {}).get("runs", []) for r in run["layers"] for b in r.get("bands", [])]
    if body["bands_result"] == "NOT CHECKED" and not edge_rows:
        return "NOT APPLICABLE", ("no edge band is defined (board.toml [[keepout.band]] or the keepouts of mech/outline.json): "
                                  "say in the board definition how the board is held")
    bad = [b["name"] for b in body["bands"] if b["result"] == "FAIL"] + \
          sorted({b["name"] + " (copper to edge)" for b in edge_rows if b["result"] == "FAIL"})
    text = f"{len(body['bands'])} band(s)" + (f", {len(edge_rows)} copper-to-edge row(s)" if edge_rows else "")
    if bad:
        return "FAIL", text + ": " + ", ".join(bad)
    if not all(b["bodies_measured"] for b in body["bands"]):
        return "CANNOT RUN", text + ": courtyards, pads and exposed copper are clear, but part bodies were not measured (no CadQuery)"
    return "PASS", text + ": no body, courtyard, solder joint or exposed copper inside"


ROWS = [
    Row(10, "erc", "ERC; netlist, PDF and sheet images exported", "`schematic/export.py`", "out/erc_report.json",
        ["schematic/export.py"], explicit="schematic", stage=1),
    Row(20, "drc", "DRC, all severities, with schematic parity", "`drc_run.py`", "out/drc_summary.txt", ["drc_run.py"], explicit="board"),
    Row(30, "intent", "Netlist against intent, with the mutation self-test", "`netlist_check.py`", "out/connectivity_report.md",
        ["netlist_check.py", "{io}", "--self-test"]),
    Row(35, "pinfn", "Pin functions of every programmable part: the use table against the datasheet table",
        "`pin_function_check.py`", "out/pin_function_check.md", ["pin_function_check.py"], applies=_pinfn_applies),
    Row(40, "netlist", "Netlist of today against the reference netlist (the schematic of the gate)", "`netlist_compare.py`",
        "out/netlist_compare.md", ["netlist_compare.py"]),
    Row(50, "stock", "BOM stock, all lines, from saved supplier answers no older than [bom] max_age_hours (24 h by default)",
        "`jlc_parts.py bom-check`", "out/BOM_STOCK_CHECK.md", _stock_cmds, detail=_stock_detail),
    Row(60, "lines", "BOM line audit: shared lines, LCSC and maker part numbers", "`jlc_parts.py line-audit`", "out/bom_line_audit.md",
        ["jlc_parts.py", "{io}", "line-audit"]),
    Row(70, "footprints", "Footprints: numbers for the comparison with the maker drawings, and flags", "`fp_audit.py` plus review",
        "out/fp_audit.md", ["fp_audit.py"], explicit="board"),
    Row(80, "rotations", "Rotations derived again and compared with the placement file", "`jlc_rotations.py`", "out/jlc/rotations.md",
        ["jlc_rotations.py", "{io}", "test"]),
    Row(90, "silk", "Silkscreen size, clearances, label ownership", "`silk_check.py`", "out/silk_check.md", ["silk_check.py"],
        explicit="board", detail=_silk_detail),
    Row(100, "edge", "Copper to edge on the exported Gerbers (board and panel)", "`edge_check.py`", "out/edge_check.md", _edge_cmd,
        explicit="gerbers", detail=_edge_detail),
    Row(110, "necks", "Current worksheet and copper necks", "`neck_check.py`", "out/current_worksheet.md", ["neck_check.py"], explicit="board"),
    Row(120, "ground", "Ground islands, webs between holes, stitching", "`zone_check.py`", "out/zone_check.md", ["zone_check.py"],
        explicit="board"),
    Row(121, "ratings", "Pins and ratings against the hand-typed datasheet tables", "`ratings_check.py`", "out/ratings_check.md",
        ["ratings_check.py"]),
    Row(122, "impedance", "Impedance of the controlled lines, from the board's own widths and layers", "`impedance_check.py`",
        "out/impedance_check.md", ["impedance_check.py"], explicit="board"),
    Row(123, "returns", "Return paths of the fast and sensitive nets (`[fast_nets]`)", "`return_path_check.py`",
        "out/return_path.md, out/review/return_path/", ["return_path_check.py"], explicit="board"),
    Row(124, "testpoints", "Test points: pad size, spacing, clearances, coverage of the required nets, fixture",
        "`testpoint_check.py`", "out/testpoint_check.md, out/testpoints.md", ["testpoint_check.py"], explicit="board",
        stage=3),                                                       # stage 3: it reads out/body_check.json of this run
    Row(130, "heat", "Heat table recomputed with the board's copper and vias", "design note, section 4", "DESIGN_NOTE.md", by_hand=True),
    Row(140, "bodies", "3D bodies, hole keep-outs, mated plugs", "`body_check.py`", "out/body_check.md", ["body_check.py"], explicit="board",
        detail=_body_detail),
    Row(150, "bands", "Edge keep-out bands (board held by slots or rails): bodies, courtyards, solder joints, exposed copper, copper to edge",
        "`body_check.py` check D, `edge_check.py`", "out/body_check.md, out/edge_check.md", stage=3, detail=_bands),
    Row(160, "panel", "Panel: DRC with its own rule file; placement file derived again", "`panel.py`, `drc_run.py`, `jlc_rotations.py`",
        "out/panel/", _panel_cmds, applies=_panel_applies),
    Row(170, "interface", "Interface file and 3D model against the saved board", "`interface_export.py --check`",
        "mech/interface.json, out/3d/", ["interface_export.py", "{io}", "--check"]),
    Row(180, "sim", "Simulation suite, run again", "`sim/ngs.py suite`", "sim/out/suite_results.json",
        lambda ctx: [["sim/ngs.py", "suite", ctx.p("sim"), "--out", ctx.p("sim", "out")]], applies=_sim_applies),
    Row(190, "emc", "EMC: zones, antenna keep-out and matching network, nothing noisy under or beside a sensitive part "
        "(`references/pcb-rules/emc.md`)", "tiles, looked at", "out/review/", by_hand=True),
    Row(200, "privacy", "Privacy scan of the design and of every output", "`privacy_scan.py`", "out/privacy_scan.md", ["privacy_scan.py"],
        stage=4),
    Row(210, "fresh", "Production files fresh against the board", "`fab_package.py --check`", "out/jlc/manifest.json",
        ["fab_package.py", "{io}", "--check"]),
]


# ---- running -----------------------------------------------------------------------------------------------------------
def commands(row: Row, ctx: Ctx) -> list[list[str]]:
    """The command lines of a row for this call form; KicadIOError when the row cannot be run this way."""
    if callable(row.cmd):
        cmds = row.cmd(ctx)
    else:
        cmds = [list(row.cmd)]
    if ctx.mode == "project":
        io = ["--project", ctx.project]
    elif row.explicit == "board":
        io = [ctx.board, "--out", ctx.out]
    elif row.explicit == "schematic":
        if not ctx.schematic:
            raise kicad_io.KicadIOError("no schematic was given (--schematic)")
        io = [ctx.schematic, "--out", ctx.out]
    elif row.explicit == "gerbers":
        io = []
    else:
        raise kicad_io.KicadIOError("this check needs a board folder (--project)")
    out = []
    for c in cmds:
        if "{io}" in c:
            i = c.index("{io}")
            c = c[:i] + io + c[i + 1:]
        elif not callable(row.cmd):
            c = c + io
        out.append([os.path.join(_HERE, *c[0].split("/"))] + [str(x) for x in c[1:]])
    return out


_VERDICT = re.compile(r"\b(PASS|FAIL|CANNOT RUN|IDENTICAL|DIFFERENT|UNKNOWN|REFUSED)\b")


def table() -> list:
    """The rows of the page, in its order. A row that comes later in ROWS with a key that is already there
    replaces the earlier one (another file that appends a row which this file has by now does not double it)."""
    return sorted({r.key: r for r in ROWS}.values(), key=lambda r: r.order)


def summary_line(text: str) -> str:
    """The line of a script's output that carries its verdict (the last such line), without paths."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    hit = next((ln for ln in reversed(lines) if _VERDICT.search(ln) and not ln.startswith(("report:", "record:"))),
               lines[-1] if lines else "")
    hit = re.sub(r"\s*->\s*\S.*$", "", hit)
    hit = re.sub(r"^(PASS|FAIL|CANNOT RUN)\b\s*[:\-]?\s*", "", hit)
    return hit.replace("|", "/")[:220]


def run_row(row: Row, ctx: Ctx, timeout: float) -> dict:
    res = {"key": row.key, "state": "", "detail": "", "commands": [], "exit": [], "seconds": 0.0, "tail": ""}
    t0 = time.monotonic()
    try:
        if row.applies:
            why = row.applies(ctx)
            if why:
                res["state"], res["detail"] = "NOT APPLICABLE", why
                return res
        if row.cmd is None:                                             # a row that reads other rows' results
            res["state"], res["detail"] = row.detail(ctx)
            return res
        worst, texts = 0, []
        for cmd in commands(row, ctx):
            res["commands"].append(ctx.clean("python -I " + " ".join(os.path.relpath(c, _HERE) if c.startswith(_HERE) else c for c in cmd)))
            rc, text, blocked = pcb_common.run_guarded([sys.executable, "-I", "-B"] + cmd, timeout)      # -B: no __pycache__
            text = "\n".join(ln for ln in text.splitlines() if "image handler" not in ln and "memory leak" not in ln)
            if blocked:
                rc, text = 2, text + f"\nCANNOT RUN: the check gave no result: {blocked}"
            elif rc not in (0, 1, 2):
                rc, text = 2, text + f"\nCANNOT RUN: the script ended with exit code {rc}"
            res["exit"].append(rc)
            texts.append(text)
            worst = max(worst, rc)
        res["state"] = ("PASS", "FAIL", "CANNOT RUN")[worst]
        res["tail"] = ctx.clean("\n".join(t.strip()[-1500:] for t in texts))
        res["detail"] = "; ".join(s for s in (summary_line(ctx.clean(t)) for t in texts) if s)
        if row.detail and worst < 2:
            try:
                res["detail"] = row.detail(ctx)
            except (TypeError, KeyError, ValueError, AttributeError):   # the JSON twin is not what this row expects
                pass
    except kicad_io.KicadIOError as e:
        res["state"], res["detail"] = "CANNOT RUN", ctx.clean(str(e))
    finally:
        res["seconds"] = round(time.monotonic() - t0, 1)
    return res


def count_states(results) -> dict:
    """The rows of a run counted apart: passed, failed, could not run, not applicable, left out, by hand."""
    states = [r["state"] for r in results]
    return {"passed": states.count("PASS"), "failed": states.count("FAIL"), "could_not_run": states.count("CANNOT RUN"),
            "not_applicable": states.count("NOT APPLICABLE"), "left_out": states.count("LEFT OUT"),
            "by_hand": states.count("BY HAND")}


def headline(overall: str, c: dict) -> str:
    """'NOT PASSED: 4 passed, 4 failed, 12 could not run, 3 not applicable': the four kinds apart, so that checks
    that could not run (a design without a board folder) do not read as faults in the board."""
    return (f"{overall}: {c['passed']} passed, {c['failed']} failed, {c['could_not_run']} could not run, "
            f"{c['not_applicable']} not applicable" + (f", {c['left_out']} left out" if c["left_out"] else ""))


_NEEDS = (("needs a board folder", "the board folder: give it with `--project <board folder>`"),
          ("no schematic was given", "the root schematic: give it with `--schematic <root.kicad_sch>`"),
          ("no Gerber folder was given", "the exported Gerbers: give them with `--gerbers <folder>`"))


def cannot_run_needs(results: list) -> str:
    """One line on what the rows that could not run need ('' when none): grouped by the input that was missing; the
    rest stopped on their own (a missing tool, an unreadable file, a time limit), and their rows say why."""
    groups: dict[str, list[str]] = {}
    for key, res in results:
        if res["state"] != "CANNOT RUN":
            continue
        what = next((need for word, need in _NEEDS if word in res["detail"]), "")
        groups.setdefault(what, []).append(key)
    parts = []
    for _, need in _NEEDS:
        keys = sorted(groups.get(need, []))
        if keys:
            parts.append(f"{len(keys)} need{'s' if len(keys) == 1 else ''} {need} ({', '.join(keys)})")
    own = sorted(groups.get("", []))
    if own:
        one = len(own) == 1
        parts.append(f"{len(own)} stopped on {'its' if one else 'their'} own: read {'its row' if one else 'their rows'} and "
                     f"the lines quoted under the table ({', '.join(own)})")
    return "; ".join(parts)


def old_page(path: str):
    """(rows by check text, hand-written sections) of an earlier CHECKS.md; ({}, None) without one."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}, None
    rows = {}
    for ln in text.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.startswith("|") and len(cells) == 4:
            rows[cells[0]] = ln
    i = text.find(HAND_SECTIONS)
    return rows, (text[i:].rstrip("\n").splitlines() if i >= 0 else None)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run the whole check suite of a board and write the one-page out/CHECKS.md.",
                                 epilog="Exit codes: 0 every check passed, 1 a check failed or could not run, 2 could not start.")
    ap.add_argument("board", nargs="?", help="a .kicad_pcb file (with --out); not needed with --project")
    ap.add_argument("--project", help="the board folder (board.toml there; results in <project>/out/)")
    ap.add_argument("--out", help="results folder (needed without --project)")
    ap.add_argument("--schematic", help="without --project: the root schematic, for the checks that need one")
    ap.add_argument("--gerbers", help="without --project: the folder of exported Gerbers, for the edge check")
    ap.add_argument("--only", help="run only these rows (comma-separated keys)")
    ap.add_argument("--skip", help="leave these rows out (comma-separated keys)")
    ap.add_argument("--list", action="store_true", help="print the rows with their keys and stop")
    ap.add_argument("--jobs", type=int, help="checks at once (default: half the cores)")
    ap.add_argument("--timeout", type=float, default=ROW_TIMEOUT, help=f"seconds per check (default {ROW_TIMEOUT:.0f})")
    a = ap.parse_args(argv)
    rows = table()
    if a.list:
        for r in rows:
            print(f"{r.key:11} {r.check}  [{r.script}]" + ("  (by hand)" if r.by_hand else ""))
        return 0
    job = pcb_common.resolve(a)
    ctx = Ctx("project" if job.project else "explicit", job.project, job.board,
              os.path.abspath(a.schematic) if a.schematic else None, os.path.abspath(a.gerbers) if a.gerbers else None,
              job.out, job.settings)
    keys = {r.key for r in rows}
    only = {k.strip() for k in a.only.split(",")} if a.only else None
    skip = {k.strip() for k in (a.skip.split(",") if a.skip else [])} | set(job.cfg("check_all").get("skip", []))
    unknown = ((only or set()) | skip) - keys
    if unknown:
        raise kicad_io.KicadIOError(f"no such row: {', '.join(sorted(unknown))} (see --list)")
    sha_before = kicad_io.sha256(job.board)
    t0 = time.monotonic()
    todo = [r for r in rows if not r.by_hand and (only is None or r.key in only) and r.key not in skip]
    for r in rows:
        if r.by_hand:
            ctx.rows[r.key] = {"key": r.key, "state": "BY HAND", "detail": "", "commands": [], "exit": [], "seconds": 0.0, "tail": ""}
        elif r not in todo:
            ctx.rows[r.key] = {"key": r.key, "state": "LEFT OUT", "detail": "left out of this run (--only, --skip or board.toml [check_all] skip)",
                               "commands": [], "exit": [], "seconds": 0.0, "tail": ""}
    jobs = a.jobs or max(2, (os.cpu_count() or 4) // 2)
    for stage in sorted({r.stage for r in todo}):
        batch = [r for r in todo if r.stage == stage]
        with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(batch)))) as pool:
            for r, res in zip(batch, pool.map(lambda r: run_row(r, ctx, a.timeout), batch)):
                ctx.rows[r.key] = res
                print(f"{res['state']:14} {r.key:11} {res['seconds']:7.1f} s  {res['detail'][:150]}", flush=True)
    changed = kicad_io.sha256(job.board) != sha_before
    counts = count_states(ctx.rows.values())
    n_fail = counts["failed"] + counts["could_not_run"]                 # either keeps the suite from passing
    n_left, n_hand = counts["left_out"], counts["by_hand"]
    ok = not n_fail and not n_left and not changed
    overall = "ALL PASS" if ok else ("NOT PASSED" if n_fail else "INCOMPLETE")
    head = headline(overall, counts)
    needs = cannot_run_needs([(r.key, ctx.rows[r.key]) for r in rows])
    # ---- the page
    p_md = os.path.join(job.out, "CHECKS.md")
    old_rows, hand = old_page(p_md)
    netlist = os.path.join(job.out, "netlist.net")
    kc = kicad_io.find_kicad()
    how = f"--project {os.path.basename(job.project)}" if job.project else f"{os.path.basename(job.board)} --out ..."
    md = [f"# {ctx.name}: designer's checks, one page", "",
          f"Result of the whole check suite on the saved and exported files, kept as `out/CHECKS.md`. Run by "
          f"`python -I scripts/check_all.py {how}` on {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
          f"{' with KiCad ' + kc.version if kc else ''}. Board sha256 `{sha_before}`. Netlist sha256 "
          f"`{kicad_io.sha256(netlist) if os.path.isfile(netlist) else 'no netlist in the results folder'}`.", "",
          f"**Overall: {head}.**"
          + (f" {n_left} row(s) were left out of this run, so the page is not the whole suite." if n_left else "")
          + (f" {n_hand} row(s) are the designer's to fill in by hand and are not counted." if n_hand else "")
          + " Anything that failed or could not run keeps the suite from passing: could not run is never a pass. A check "
          "on design parameters instead of the exported file does not count for manufacturing rows."]
    if needs:
        md += ["", f"**Could not run, and what it needs:** {needs}."]
    if changed:
        md += ["", "**The board file changed while the checks ran: nothing on this page can be trusted. Save, then run again.**"]
    md += ["", "| Check | Script | Result | Evidence file |", "|---|---|---|---|"]
    for r in rows:
        res = ctx.rows[r.key]
        if r.by_hand:
            keep = old_rows.get(r.check)
            md.append(keep if keep and "BY HAND" not in keep else
                      f"| {r.check} | {r.script} | BY HAND: fill in what you measured or saw | `{r.evidence}` |")
            continue
        cell = res["state"] + (": " + res["detail"].replace("|", "/").replace("\n", " ") if res["detail"] else "")
        ev = ", ".join(f"`{e.strip()}`" for e in r.evidence.split(","))
        md.append(f"| {r.check} | {r.script} | {cell} | {ev} |")
    bad = [(r, ctx.rows[r.key]) for r in rows if ctx.rows[r.key]["state"] in ("FAIL", "CANNOT RUN") and ctx.rows[r.key]["tail"]]
    if bad:
        md += ["", "## What the failing checks said (their last lines; the evidence files hold everything)", ""]
        for r, res in bad:
            lines = [ln for ln in res["tail"].splitlines() if ln.strip()][-4:]
            md.append(f"- **{r.key}** ({res['state']}): " + " / ".join(ln.strip()[:200] for ln in lines))
    md += [""] + (hand or HAND_TEMPLATE)
    kicad_io.atomic_write(p_md, "\n".join(md) + "\n")
    data = {"script": "check_all.py", "result": overall, "headline": head, "counts": counts,
            "could_not_run_needs": needs.replace("`", ""), "board": os.path.basename(job.board), "sha256": sha_before,
            "board_changed_during_run": changed, "seconds": round(time.monotonic() - t0, 1),
            "rows": [dict(ctx.rows[r.key], check=r.check, script=r.script, evidence=r.evidence) for r in rows]}
    kicad_io.atomic_write(os.path.join(job.out, "CHECKS.json"), json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    if needs:
        print("could not run, and what it needs: " + needs.replace("`", ""))
    print(head + (", THE BOARD CHANGED DURING THE RUN" if changed else "") + f", {time.monotonic() - t0:.0f} s -> {p_md}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
