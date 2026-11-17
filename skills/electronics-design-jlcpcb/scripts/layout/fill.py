"""Zone fill in its own process, then a check of the file that was saved.

What it does
    Fill:   loads the board with its project and rule file (in a fresh KiCad process), fills every zone, saves.
    Check:  loads the SAVED file again in another fresh process and, for every copper zone and layer,
              - compares the fill that is in the file with a fresh fill made now, under the rules as they are
                now (the area that differs must be zero): a fill that was saved before a rule applied, or
                before the last track was laid, is stale;
              - measures the smallest distance of the saved fill to the board edge against the board's own
                copper-to-edge minimum (board setup). KiCad fills by the custom rule file where that has an
                edge_clearance rule, also a smaller one: then a new fill cannot cure the finding, and the
                result says that the two files disagree;
              - reports a zone that was never filled.
    A fill run always ends with the check. --check runs the check alone and changes nothing.

Why it exists (real failures, told without names)
    A board's zones were filled and saved before the copper-to-edge rule was in the project. The rule check
    reported a clean board, while the file on disk, and the Gerbers plotted from it, had copper up to the
    outline. Seen again in the tests of this script: the rule check of KiCad 9 does not report a saved fill
    that lies too near the board edge (KiCad 10's does), and neither version fills again by itself. Nothing
    compared the saved fill with the rules until a reviewer measured the Gerbers. A second reason for the
    separate process: filling inside a long script that had already edited the board crashed KiCad's filler;
    a fresh process that only loads, fills and saves does not.

Usage
    python -I layout/fill.py <board.kicad_pcb> --in-place            fill that board, save it, check it
    python -I layout/fill.py --project <board folder> --in-place     the project's board; results in <project>/out/
    python -I layout/fill.py <board.kicad_pcb> --out <folder>        fill a COPY in <folder>/filled/ (the design
                                                                     is not touched), check the copy
    python -I layout/fill.py <board.kicad_pcb> --check --out <folder>    check only (on a private copy)
    python -I layout/fill.py --project <board folder> --check
    options: --timeout S (one KiCad process, default 1800)
    Results: fill_check.md and fill_check.json in the results folder.
    From a project script:  import layout.fill;  res = layout.fill.fill(path)   (fills in place, returns the
    check's result as a dict; res["result"] is "PASS" or "FAIL").

board.toml keys: [project] name, kicad_dir, out_dir (through kicad_io). No others.

Exit codes
    0  PASS: every zone filled, the saved fill equals a fresh fill, the fill keeps the edge minimum
    1  FAIL: a stale fill, a zone never filled, fill nearer to the edge than the board's minimum
    2  CANNOT RUN: KiCad not found, unreadable board, a KiCad process that failed or ran out of time, neither
       --in-place nor --out. Never a pass.

Not checked here: clearances inside the fill and thermal spokes (drc_run.py), necks in a pour
(neck_check.py), islands and stitching (zone_check.py), the exported Gerbers (edge_check.py). A board without
zones passes with the note "no zones".
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import kicad_io  # noqa: E402

TIMEOUT = 1800.0
AREA_TOL = 0.001            # mm2: two fills of one board under one set of rules differ by nothing


# ---- the two stages: each runs alone in a fresh KiCad process ----------------------------------------------------------
def _stage_fill(board_path: str) -> dict:
    import pcbnew
    b = kicad_io.load_board(board_path)
    zones = [z for z in b.Zones() if not z.GetIsRuleArea()]
    b.BuildConnectivity()
    ok = bool(pcbnew.ZONE_FILLER(b).Fill(b.Zones())) if zones else True
    kicad_io.save_board(b, board_path)
    return {"filled": ok, "zones": len(zones)}


def _minus(a, b):
    import pcbnew
    out = pcbnew.SHAPE_POLY_SET(a)
    try:
        out.BooleanSubtract(b)
    except TypeError:                                           # an older KiCad wants the mode
        out.BooleanSubtract(b, pcbnew.SHAPE_POLY_SET.PM_FAST)
    return out


def _stage_check(board_path: str) -> dict:
    import pcbnew
    from layout import board_outline
    b = kicad_io.load_board(board_path)
    limit = pcbnew.ToMM(b.GetDesignSettings().m_CopperEdgeClearance)
    edge = board_outline(b)
    ring = None
    if edge is not None:
        ring = pcbnew.SHAPE_POLY_SET(edge)                      # everything just outside the board
        ring.Inflate(pcbnew.FromMM(5), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.002))
        ring = _minus(ring, edge)
    zones = [z for z in b.Zones() if not z.GetIsRuleArea()]
    cu = [lay for lay in pcbnew.LSET.AllCuMask(b.GetCopperLayerCount()).CuStack()]
    saved = {}
    for i, z in enumerate(zones):
        for lay in cu:
            if z.IsOnLayer(lay):
                saved[(i, lay)] = (pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(lay)), bool(z.IsFilled()))
    b.BuildConnectivity()
    if zones:
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())                   # a fresh fill, in memory only
    def edge_gap(ps):
        """Smallest distance of a fill to the board edge in mm (None: nothing to measure)."""
        if ring is None or not ps.OutlineCount():
            return None
        touch = pcbnew.SHAPE_POLY_SET(ps)
        touch.BooleanIntersection(ring)
        if touch.OutlineCount():
            return 0.0
        pts = [ps.Outline(k).CPoint(j) for k in range(ps.OutlineCount()) for j in range(ps.Outline(k).PointCount())]
        rpts = [ring.Outline(k).CPoint(j) for k in range(ring.OutlineCount())
                for j in range(ring.Outline(k).PointCount())]
        d2 = min([ring.SquaredDistance(v) for v in pts] + [ps.SquaredDistance(v) for v in rpts])
        return round(pcbnew.ToMM(int(d2 ** 0.5)), 4)

    rows = []
    for (i, lay), (old, was_filled) in saved.items():
        z = zones[i]
        new = z.GetFilledPolysList(lay)
        diff = (_minus(old, new).Area() + _minus(new, old).Area()) / 1e12
        gap = edge_gap(old)
        why = []
        if not was_filled:
            why.append("never filled")
        if diff > AREA_TOL:
            why.append(f"the saved fill differs from a fresh fill by {diff:.3f} mm2 (stale: fill and save again)")
        if gap is not None and gap < limit - 0.001:
            why.append(f"saved fill {gap:.3f} mm from the board edge, the board's minimum is {limit:.3f} mm")
            fresh = edge_gap(new)
            if fresh is not None and fresh < limit - 0.001:     # a new fill will not cure it
                why.append(f"a fresh fill is also only {fresh:.3f} mm from the edge: KiCad fills nearer than the "
                           "board's minimum, as it does when an edge_clearance rule of the custom rule file "
                           "overrides it; make the project file and the rule file say the same")
        rows.append({"zone": str(z.GetZoneName()) or f"zone {i + 1}", "net": str(z.GetNetname()),
                     "layer": str(b.GetLayerName(lay)), "saved_area_mm2": round(old.Area() / 1e12, 3),
                     "fresh_area_mm2": round(new.Area() / 1e12, 3), "difference_mm2": round(diff, 4),
                     "edge_gap_mm": gap, "result": "FAIL" if why else "PASS", "why": why})
    return {"edge_limit_mm": limit, "outline_closed": ring is not None, "zones": rows}


def _stage(argv: list[str]) -> int:
    """Entry of a stage process: fill.py --stage fill|check <board> <result.json>."""
    from layout import quiet_wx
    stage, board, result = argv
    quiet_wx()                                                  # no message box, ever: KiCad's log goes to stderr
    res = _stage_fill(board) if stage == "fill" else _stage_check(board)
    kicad_io.atomic_write(result, json.dumps(res))
    return 0


def _run_stage(stage: str, board: str, timeout: float) -> dict:
    with kicad_io.private_tmp("fill-") as tmp:
        result = os.path.join(tmp, "result.json")
        cmd = [kicad_io.kicad_python(), "-I", os.path.abspath(__file__), "--stage", stage, board, result]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise kicad_io.KicadIOError(f"zone {stage}: the KiCad process did not finish in {timeout:.0f} s") from None
        if r.returncode != 0 or not os.path.isfile(result):
            tail = ((r.stdout or "") + (r.stderr or "")).strip()[-800:]
            raise kicad_io.KicadIOError(f"zone {stage}: the KiCad process failed (exit {r.returncode}): {tail}")
        with open(result, encoding="utf-8") as f:
            return json.load(f)


# ---- the public calls --------------------------------------------------------------------------------------------------
def check(board_path: str, timeout: float = TIMEOUT) -> dict:
    """Check the saved fill of a board (on a private copy: nothing is written beside it). Returns the result."""
    kc = kicad_io.require_kicad()
    with kicad_io.private_tmp("fill-check-") as tmp:
        copy = os.path.join(tmp, os.path.basename(board_path))
        kicad_io.copy_board(board_path, copy, lock_source=False)
        res = _run_stage("check", copy, timeout)
    bad = [z for z in res["zones"] if z["result"] != "PASS"]
    res.update(check="fill_check", board=os.path.basename(board_path), board_sha256=kicad_io.sha256(board_path),
               kicad_version=kc.version, date=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
               result="FAIL" if bad else "PASS",
               not_checked=(["KiCad " + kc.version + ": " + kc.note] if kc.note else []) + (
                   [] if res["outline_closed"] else ["distance of the fill to the board edge: the outline on "
                                                     "Edge.Cuts is not one closed shape"]) + [
                   "clearances inside the fill and thermal spokes (drc_run.py)", "necks in a pour (neck_check.py)",
                   "islands and stitching (zone_check.py)", "the exported Gerbers (edge_check.py)"])
    return res


def fill(board_path: str, timeout: float = TIMEOUT) -> dict:
    """Fill every zone of the board IN PLACE (its own process), save, then check the saved file. Returns the
    check's result with "filled_zones" added."""
    done = _run_stage("fill", os.path.abspath(board_path), timeout)
    res = check(board_path, timeout)
    res["filled_zones"] = done["zones"]
    if not done["filled"]:
        res["result"] = "FAIL"
        res["zones"].append({"zone": "(all)", "net": "", "layer": "", "result": "FAIL",
                             "why": ["KiCad's zone filler reported a failure"]})
    return res


def markdown(res: dict) -> str:
    out = ["# Zone fill: the saved file against a fresh fill", "",
           f"**Result: {res['result']}** - board `{res['board']}` (SHA-256 `{res['board_sha256']}`), KiCad "
           f"{res['kicad_version']}, {res['date']}.", ""]
    if "filled_zones" in res:
        out += [f"This run filled {res['filled_zones']} zone(s) in its own process and saved the board first.", ""]
    if not res["zones"]:
        out += ["The board has no copper zones: nothing to compare.", ""]
    else:
        out += [f"Limit: difference to a fresh fill 0 mm2 (tolerance {AREA_TOL} mm2); fill to board edge at "
                f"least {res['edge_limit_mm']:.3f} mm (the board's own minimum).", "",
                "| Zone | Net | Layer | Saved fill mm2 | Fresh fill mm2 | Difference mm2 | To the edge mm | Result |",
                "|---|---|---|---|---|---|---|---|"]
        for z in res["zones"]:
            gap = "not measured" if z.get("edge_gap_mm") is None else f"{z['edge_gap_mm']:.3f}"
            out.append(f"| {z['zone']} | {z['net']} | {z['layer']} | {z.get('saved_area_mm2', '')} | "
                       f"{z.get('fresh_area_mm2', '')} | {z.get('difference_mm2', '')} | {gap} | {z['result']}"
                       + ("".join(": " + w for w in z["why"])) + " |")
        out.append("")
    out += ["## Not checked", ""] + [f"- {n}" for n in res["not_checked"]]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if argv[:1] == ["--stage"]:
        return _stage(argv[1:])
    ap = argparse.ArgumentParser(description="Fill the zones of a KiCad board in a process of its own, save, then "
                                             "check the saved file against a fresh fill and the edge minimum. "
                                             "Exit 0 pass, 1 findings, 2 could not run.")
    ap.add_argument("board", nargs="?", help="board file (.kicad_pcb); not needed with --project")
    ap.add_argument("--project", help="hardware/board folder (results in <project>/out/)")
    ap.add_argument("--out", help="results folder when no project folder is used")
    ap.add_argument("--in-place", action="store_true", help="fill and save the board itself")
    ap.add_argument("--check", action="store_true", help="only check the saved fill; change nothing")
    ap.add_argument("--timeout", type=float, default=TIMEOUT, help=f"seconds for one KiCad process (default {TIMEOUT:g})")
    a = ap.parse_args(argv)
    if a.project:
        files = kicad_io.project_files(a.project)
        board, out = a.board or files["pcb"], a.out or files["out"]
    else:
        board, out = a.board, a.out
    if not board or not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"board file not found: {board or '(give a board file or --project)'}")
    if not out and not a.in_place:
        raise kicad_io.KicadIOError("give --project <board folder>, or a board file with --out <folder> (a filled "
                                    "copy goes there) or with --in-place (the board itself is filled)")
    if a.check:
        res = check(board, a.timeout)
    elif a.in_place:
        res = fill(board, a.timeout)
    else:                                                       # the design is not ours to change: fill a copy
        copy = os.path.join(out, "filled", os.path.basename(board))
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        kicad_io.copy_board(board, copy, lock_source=False)
        res = fill(copy, a.timeout)
        res["filled_copy"] = copy
    out = out or os.path.dirname(os.path.abspath(board))        # --in-place without --out: beside the board
    os.makedirs(out, exist_ok=True)
    kicad_io.atomic_write(os.path.join(out, "fill_check.md"), markdown(res))
    kicad_io.atomic_write(os.path.join(out, "fill_check.json"), json.dumps(res, indent=1) + "\n")
    for z in res["zones"]:
        print(f"{z['result']:5} {z['zone']} [{z['net']}] {z['layer']}: saved {z.get('saved_area_mm2')} mm2, differs "
              f"from a fresh fill by {z.get('difference_mm2')} mm2 (limit {AREA_TOL}), {z.get('edge_gap_mm')} mm to "
              f"the edge (limit {res['edge_limit_mm']:.3f})" + "".join("; " + w for w in z["why"]))
    if res.get("filled_copy"):
        print("filled copy:", res["filled_copy"])
    print(f"zone fill: {res['result']} - {len(res['zones'])} zone layer(s) checked on the saved file; "
          f"{os.path.join(out, 'fill_check.md')}")
    return 0 if res["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
