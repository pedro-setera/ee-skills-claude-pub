"""Finish a routed board: close open connections, tie ground islands, remove dangling vias and track ends.
Every change is kept only when the board is no worse for it.

What it does (on the saved, filled board; in this order)
    finish  For every net that is routed with tracks: connect the pads that are not on the net's main piece of
            copper, from the copper the net already has, with a wider search than the first routing. Where that
            fails: find the cheapest path that may cross other routed nets, rip those, route this net, route the
            ripped nets again; keep it only when fewer nets are open. Locked tracks and vias (hand-planned
            copper), nets with a zone and the nets you name are never ripped.
    tie     For each poured net you name (ground): every piece of its copper (fill, pads, tracks) that holds a pad
            and is not joined to the main piece gets a via where it lies over the main piece on another layer.
            A piece with no such spot is reported, not tied.
    clean   Vias that KiCad reports as dangling are removed; tracks with a free end are cut back to the last
            point where copper of their net joins them, or removed when nothing does.
    After each step the board copy is filled again (fill.py, its own process) and checked with KiCad's rule
    check. The step is written to the board only when the copy has no more unconnected items and no more
    errors than before; otherwise it is dropped and reported. The result compares the first and last check.

Why it exists (real cases, told without names)
    A batch router is repeatable, so the same few connections stay open after every build; closing them by hand
    in the board editor is lost at the next build. Escape vias and stubs laid before routing end up used on one
    layer only, or joined part-way, and the rule check then warns about every one of them. And a clean-up that
    simply deleted what looked unused once opened a net: hence the rule "only when no connection opens",
    measured by the rule check, not assumed.

Where it stops
    It is the grid router of route.py with a wider search: the same limits apply (no fine-pitch escape, no
    matched or controlled tracks). It does not move parts. An island that has no copper of the main piece above
    or below it needs a track drawn by hand. The clean step also works on locked (hand-planned) copper: an
    escape stub or via that nothing uses is cut back or removed, and it cannot know that a via was a planned
    test or stitching point. Look at the list of what was removed.

Usage
    python -I layout/repair.py <board.kicad_pcb> --in-place [--tie GND] [--out <folder>]
    python -I layout/repair.py --project <board folder> --in-place [--tie GND]      results in <project>/out/
    python -I layout/repair.py <board.kicad_pcb> --out <folder> [--tie GND]         repairs a COPY in
                                                                                     <folder>/repaired/
    options: --no-finish, --no-clean, --tie NET (repeatable), --protect NET (repeatable: never ripped),
             --width MM (new tracks of a net without tracks; default 0.2)
    Results: repair.md and repair.json in the results folder.
    From a project script (KiCad's Python):  res = layout.repair.repair(path, tie=["GND"], out=folder)

board.toml keys: [project] name, kicad_dir, out_dir (through kicad_io). No others.

Exit codes
    0  PASS: nothing unconnected and nothing dangling is left
    1  FAIL: something is still open or dangling (listed), or a step had to be dropped and left it so
    2  CANNOT RUN: KiCad not found, unreadable board, a KiCad process that failed, neither --in-place nor --out

Not checked here: everything the rule check does not see (currents, return paths, labels). Run drc_run.py and
the other checks on the result, and look at the render.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import json
import math
import os
import re
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import kicad_io  # noqa: E402
from layout import fill  # noqa: E402

DRC_TIMEOUT = 900.0
WIDE = dict(margins=(4.0, 12.0, 40.0), max_nodes=2_000_000)        # the wider search of the finishing pass
_NET = re.compile(r"\[([^\]]+)\]")


def drc(board_path: str, timeout: float = DRC_TIMEOUT) -> dict:
    """KiCad's rule check on a private copy of a board: {"unconnected", "errors", "dangling": [(type, x, y)],
    "open_nets"}. The fill is judged as it is saved (kicad-cli does not fill again): every repair step fills its
    copy before it is checked."""
    kicad_io.require_kicad()
    with kicad_io.private_tmp("repair-drc-") as tmp:
        copy = os.path.join(tmp, os.path.basename(board_path))
        kicad_io.copy_board(board_path, copy, lock_source=False)
        rep = os.path.join(tmp, "drc.json")
        r = kicad_io.run_cli(["pcb", "drc", "--severity-all", "--format", "json", "--units", "mm", "-o", rep, copy],
                             timeout)
        if not os.path.isfile(rep):
            raise kicad_io.CliError(f"kicad-cli wrote no rule-check report (exit {r.returncode}): "
                                    + ((r.stdout or "") + (r.stderr or "")).strip()[-400:])
        with open(rep, encoding="utf-8") as f:
            d = json.load(f)
    viol, unc = d.get("violations", []), d.get("unconnected_items", [])
    dangling = [(v["type"], i["pos"]["x"], i["pos"]["y"]) for v in viol
                if v.get("type") in ("via_dangling", "track_dangling") for i in v.get("items", [])[:1] if i.get("pos")]
    nets = sorted({m for u in unc for i in u.get("items", []) for m in _NET.findall(i.get("description", ""))})
    return {"unconnected": len(unc), "errors": sum(1 for v in viol if v.get("severity") == "error"),
            "dangling": dangling, "open_nets": nets}


# ---- the steps: each edits a loaded board and says what it did ---------------------------------------------------------
def _finish(b, rules, protect, width, log) -> str:
    from layout import route as R
    r = R.Router(b, rules=rules, tracks=False)
    keep = {r.code(n) for n in protect} | r.zone_codes
    first: dict = {}
    for t in sorted(b.GetTracks(), key=lambda t: (t.GetClass(), t.GetLayer(), t.GetStart().x, t.GetStart().y,
                                                  t.GetEnd().x, t.GetEnd().y)):
        it = r.item_of(t)
        if t.IsLocked() or it[-1] in keep or it[-1] <= 0:
            r.paint_item(it)                                    # fixed: part of the base, never ripped
        else:
            first.setdefault(it[-1], []).append(it)
    r.freeze()
    r.routed = {c: list(v) for c, v in first.items()}
    r.rebuild()
    plan = []
    for code in sorted(r.names, key=lambda c: r.names[c]):
        if code in r.zone_codes or len(r.net_pads(code)) < 2:
            continue
        have = [it[6] for it in first.get(code, []) if it[0] == "track"]
        plan.append((r.names[code], dict(WIDE, width=max(rules["track"], min(have) if have else width))))
    fails = R.route_all(r, plan, log=log, passes=3, protect=[r.names[c] for c in keep if c in r.names])
    changed = [c for c in r.routed if r.routed[c] != first.get(c, [])]
    if not changed:
        return ""
    for t in list(b.GetTracks()):
        if t.GetNetCode() in changed and not t.IsLocked():
            b.Delete(t)
    r._written = {it for c, v in r.routed.items() if c not in changed for it in v}
    n = r.commit()
    return (f"finish: {len(changed)} net(s) changed ({', '.join(kicad_io.leaf(r.names.get(c, str(c))) for c in changed)}), "
            f"{n} tracks and vias written" + (f"; still open: {sorted(fails)}" if fails else ""))


def _tie(b, rules, net, log) -> str:
    import numpy as np
    from layout import route as R
    r = R.Router(b, rules=rules)
    code = r.code(net)
    for z in b.Zones():                                         # the saved fill of the net: copper like any other
        if z.GetIsRuleArea() or z.GetNetCode() != code:
            continue
        for lay in r.cu:
            if not z.IsOnLayer(lay):
                continue
            ps = z.GetFilledPolysList(lay)
            for i in range(ps.OutlineCount()):
                ix0, iy0, m = r.poly_mask(r._chain(ps.Outline(i)))
                for h in range(ps.HoleCount(i)):
                    jx0, jy0, hm = r.poly_mask(r._chain(ps.Hole(i, h)))
                    m[jy0 - iy0:jy0 - iy0 + hm.shape[0], jx0 - ix0:jx0 - ix0 + hm.shape[1]] &= ~hm
                r._paint(r.index[lay], (ix0, iy0, m), code)
    mine = r.own == code
    pieces, left = [], mine.copy()
    while left.any():                                           # every connected piece of the net's copper
        lay, y, x = (int(v[0]) for v in np.nonzero(left))
        comp = r.component(code, [(lay, np.array([[y, x]]))])
        pieces.append(comp)
        left &= ~comp
    if len(pieces) < 2:
        return ""
    pieces.sort(key=lambda c: -int(c.sum()))
    main = pieces[0]
    via_d, drill = rules["via_d"], rules["via_drill"]
    inner = np.stack([~R.dilate(~mine[i], 0.4 / R.G) for i in range(r.n_layers)])     # well inside the copper
    added, missed = [], []
    for piece in pieces[1:]:
        pads = [p for p in r.pads if p.code == code and any(len(c) and piece[lay][c[:, 0], c[:, 1]].any()
                                                            for lay, c in p.cells)]
        if not pads:
            continue                                            # fill alone: KiCad removes it, clean takes its vias
        vfree = r._via_free(code, (0, r.ny - 1, 0, r.nx - 1), via_d, drill, rules["clearance"])
        on_piece, on_main = (piece & inner).any(axis=0), (main & inner).any(axis=0)
        ys, xs = np.nonzero(on_piece & on_main & vfree)
        if len(ys) == 0:
            missed.append(f"{pads[0].ref}.{pads[0].pin}")
            continue
        cx, cy = r.cell(*pads[0].c)
        k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))     # the spot nearest to the piece's pad
        it = ("via", *r.xy(int(xs[k]), int(ys[k])), via_d, drill, code)
        r.add([it])
        main = main | piece
        added.append(f"({it[1]:g}, {it[2]:g}) for {pads[0].ref}.{pads[0].pin}")
    r.commit()
    if not added and not missed:
        return ""
    return f"tie {net}: {len(added)} via(s) added: {', '.join(added) or 'none'}" + (
        f"; islands with no via spot (draw a track by hand): {', '.join(missed)}" if missed else "")


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy), t


def _joins(b, t) -> list:
    """Where copper of t's net touches the track t, as positions 0..1 along it: other tracks' ends on its layer,
    vias, pads; and t's own ends where they lie on another track."""
    import pcbnew
    mm = pcbnew.ToMM
    net, lay, w = t.GetNetCode(), t.GetLayer(), mm(t.GetWidth())
    ax, ay, bx, by = mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y)
    out, me = [], t.m_Uuid.AsString()
    for o in b.GetTracks():
        if o.GetNetCode() != net or o.m_Uuid.AsString() == me:
            continue
        if o.GetClass() == "PCB_VIA":
            d, s = _seg_dist(mm(o.GetPosition().x), mm(o.GetPosition().y), ax, ay, bx, by)
            if d <= mm(o.GetWidth(lay)) / 2 + w / 2:
                out.append(s)
            continue
        if o.GetLayer() != lay:
            continue
        ow = mm(o.GetWidth())
        ox0, oy0, ox1, oy1 = mm(o.GetStart().x), mm(o.GetStart().y), mm(o.GetEnd().x), mm(o.GetEnd().y)
        for px, py in ((ox0, oy0), (ox1, oy1)):
            d, s = _seg_dist(px, py, ax, ay, bx, by)
            if d <= (w + ow) / 2:
                out.append(s)
        for s, (x, y) in ((0.0, (ax, ay)), (1.0, (bx, by))):
            if _seg_dist(x, y, ox0, oy0, ox1, oy1)[0] <= (w + ow) / 2:
                out.append(s)
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net and pad.IsOnLayer(lay):
                for s in (0.0, 1.0):
                    p = pcbnew.VECTOR2I(pcbnew.FromMM(ax + (bx - ax) * s), pcbnew.FromMM(ay + (by - ay) * s))
                    if pad.HitTest(p, pcbnew.FromMM(w / 2)):
                        out.append(s)
    return out


def _trim(b) -> int:
    """Cut back or remove every track that has a free end. Returns the number of changes."""
    import pcbnew
    total = 0
    for _ in range(20):                                         # a cut can leave the next piece with a free end
        b.BuildConnectivity()
        conn, n = b.GetConnectivity(), 0
        for t in list(b.GetTracks()):
            if t.GetClass() != "PCB_TRACK" or not conn.TestTrackEndpointDangling(t, False):
                continue
            js = _joins(b, t)
            at_a, at_b = any(s < 1e-6 for s in js), any(s > 1 - 1e-6 for s in js)
            mid = [s for s in js if 1e-6 <= s <= 1 - 1e-6]
            a, e = t.GetStart(), t.GetEnd()

            def at(s):
                return pcbnew.VECTOR2I(int(round(a.x + (e.x - a.x) * s)), int(round(a.y + (e.y - a.y) * s)))
            if at_a and at_b:                                   # both ends lie on copper of the net and KiCad still
                b.Delete(t)                                     # calls it loose: a piece that lies on ONE other
            elif at_a and mid:                                  # item (a track drawn twice, a stub inside a pad)
                t.SetEnd(at(max(mid)))                          # free end at the far side: back to the last join
            elif at_b and mid:
                t.SetStart(at(min(mid)))
            elif not mid:
                b.Delete(t)                                     # nothing joins it part-way: a loose piece
            else:
                continue
            n += 1
            b.BuildConnectivity()
            conn = b.GetConnectivity()
        total += n
        if not n:
            break
    return total


def _clean(b, dangling, only=None) -> str:
    """Remove the dangling vias the rule check named (only: one of them) and trim the free track ends."""
    vias = 0
    for kind, x, y in ([only] if only else dangling):
        if kind != "via_dangling":
            continue
        for t in list(b.GetTracks()):
            if t.GetClass() == "PCB_VIA" and abs(t.GetPosition().x / 1e6 - x) < 0.01 and \
                    abs(t.GetPosition().y / 1e6 - y) < 0.01:
                b.Delete(t)
                vias += 1
                break
    ends = _trim(b) if not only or only[0] == "track_dangling" else 0
    return f"clean: {vias} dangling via(s) removed, {ends} free track end(s) cut back or removed" if vias or ends else ""


def _class_clearance(board_path: str) -> float:
    """The largest clearance of the net classes in the board's project file, in mm (0 when it cannot be read)."""
    try:
        with open(board_path[:-len(".kicad_pcb")] + ".kicad_pro", encoding="utf-8") as f:
            classes = json.load(f).get("net_settings", {}).get("classes", [])
        return max([float(c.get("clearance") or 0) for c in classes if isinstance(c, dict)] + [0.0])
    except (OSError, ValueError, TypeError, AttributeError):
        return 0.0


# ---- the frame: a step is kept only when the board is no worse -----------------------------------------------------------
def _attempt(board_path: str, edit, state: dict, log) -> str:
    """Apply `edit(board) -> text` on a private copy, fill and check the copy, and write it over the board only
    when it has no more unconnected items and no more errors than `state`. Returns what was done ('' nothing)."""
    with kicad_io.private_tmp("repair-") as tmp:
        work = os.path.join(tmp, os.path.basename(board_path))
        kicad_io.copy_board(board_path, work, lock_source=False)
        b = kicad_io.load_board(work)
        what = edit(b)
        if not what:
            return ""
        kicad_io.save_board(b, work)
        fill.fill(work)
        now = drc(work)
        if now["unconnected"] > state["unconnected"] or now["errors"] > state["errors"]:
            log(f"DROPPED ({what}): it would leave {now['unconnected']} unconnected (before {state['unconnected']}) "
                f"and {now['errors']} errors (before {state['errors']})")
            return "DROPPED: " + what
        with kicad_io.ToolLock(board_path):
            kicad_io.atomic_copy(work, board_path)
        state.update(now)
        log(what + f" -> unconnected {now['unconnected']}, errors {now['errors']}")
        return what


def repair(board_path: str, *, finish: bool = True, tie: tuple = (), clean: bool = True, protect: tuple = (),
           rules: dict | None = None, width: float = 0.2, out: str | None = None, log=print) -> dict:
    """Repair the board IN PLACE (see the head of this file). Needs KiCad's Python. rules: the minimums for new
    copper (default: the board's own board-setup minimums, and for the clearance the largest clearance of its
    net classes). Returns the result; with `out` it also writes repair.md and repair.json there."""
    import pcbnew  # noqa: F401  (a clear error here when this is not KiCad's Python)
    from layout import board as B                               # (it also sends KiCad's log to stderr: no window)
    b0 = kicad_io.load_board(board_path)
    ds = b0.GetDesignSettings()
    own = {"clearance": ds.m_MinClearance, "track": ds.m_TrackMinWidth, "via_d": ds.m_ViasMinSize,
           "via_drill": ds.m_MinThroughDrill, "hole_to_hole": ds.m_HoleToHoleMin,
           "hole_clearance": ds.m_HoleClearance, "edge": ds.m_CopperEdgeClearance}
    r = dict(B.RULES, **{k: pcbnew.ToMM(v) for k, v in own.items() if v > 0}, **(rules or {}))
    if "clearance" not in (rules or {}):                        # a net class may ask for more than the board minimum:
        r["clearance"] = max(r["clearance"], _class_clearance(board_path))      # new copper keeps the largest
    del b0
    before = drc(board_path)
    state, steps = dict(before), []
    if finish and state["unconnected"]:
        steps.append(_attempt(board_path, lambda b: _finish(b, r, protect, width, log), state, log))
    for net in tie:
        steps.append(_attempt(board_path, lambda b, n=net: _tie(b, r, n, log), state, log))
    for _ in range(6 if clean else 0):                          # a removed via can leave its stub with a free end
        if not state["dangling"]:
            break
        todo = list(state["dangling"])
        done = _attempt(board_path, lambda b: _clean(b, todo), state, log)
        if done.startswith("DROPPED"):                          # all at once opened something: one at a time
            done = "; ".join(x for x in (_attempt(board_path, lambda b, d=d: _clean(b, todo, d), state, log)
                                         for d in todo[:40]) if x)
        steps.append(done)
        if not done or state["dangling"] == todo:
            break
    steps = [s for s in steps if s]
    ok = state["unconnected"] == 0 and not state["dangling"]
    res = {"check": "repair", "board": os.path.basename(board_path), "board_sha256": kicad_io.sha256(board_path),
           "kicad_version": kicad_io.kicad_version(),
           "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "before": before, "after": state, "steps": steps, "result": "PASS" if ok else "FAIL",
           "summary": f"unconnected {before['unconnected']} -> {state['unconnected']}, errors {before['errors']} -> "
                      f"{state['errors']}, dangling {len(before['dangling'])} -> {len(state['dangling'])}; "
                      f"{len([s for s in steps if not s.startswith('DROPPED')])} step(s) kept, "
                      f"{len([s for s in steps if s.startswith('DROPPED')])} dropped"}
    if out:
        os.makedirs(out, exist_ok=True)
        kicad_io.atomic_write(os.path.join(out, "repair.md"), markdown(res))
        kicad_io.atomic_write(os.path.join(out, "repair.json"), json.dumps(res, indent=1) + "\n")
    return res


def markdown(res: dict) -> str:
    b, a = res["before"], res["after"]
    out = ["# Repair of a routed board", "",
           f"**Result: {res['result']}** - board `{res['board']}` (SHA-256 after the repair `{res['board_sha256']}`), "
           f"KiCad {res['kicad_version']}, {res['date']}.", "",
           "Pass limit: 0 unconnected items and 0 dangling vias or track ends after the repair. A step is kept only "
           "when the rule check of the filled copy shows no more unconnected items and no more errors than before it.",
           "", "| | Before | After |", "|---|---|---|",
           f"| Unconnected items | {b['unconnected']} | {a['unconnected']} |",
           f"| Rule-check errors | {b['errors']} | {a['errors']} |",
           f"| Dangling vias and track ends | {len(b['dangling'])} | {len(a['dangling'])} |",
           f"| Nets with an open connection | {', '.join(b['open_nets']) or 'none'} | {', '.join(a['open_nets']) or 'none'} |",
           "", "## Steps", ""]
    out += [f"- {s}" for s in res["steps"]] or ["- nothing to do"]
    if a["dangling"]:
        out += ["", "## Still dangling", ""] + [f"- {k} at ({x:.3f}, {y:.3f})" for k, x, y in a["dangling"]]
    out += ["", "## Not checked", "", "- anything the rule check does not see: currents, return paths, labels; "
            "run drc_run.py and the other checks on the result and look at the render"]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Close open connections, tie ground islands and remove dangling vias "
                                             "and track ends of a routed KiCad board; a change is kept only when the "
                                             "board is no worse. Exit 0 pass, 1 findings, 2 could not run.")
    ap.add_argument("board", nargs="?", help="board file (.kicad_pcb); not needed with --project")
    ap.add_argument("--project", help="hardware/board folder (results in <project>/out/)")
    ap.add_argument("--out", help="results folder when no project folder is used")
    ap.add_argument("--in-place", action="store_true", help="repair the board itself")
    ap.add_argument("--tie", action="append", default=[], metavar="NET", help="a poured net whose islands are tied")
    ap.add_argument("--protect", action="append", default=[], metavar="NET", help="a net that is never ripped up")
    ap.add_argument("--no-finish", action="store_true", help="do not route open connections")
    ap.add_argument("--no-clean", action="store_true", help="do not remove dangling vias and track ends")
    ap.add_argument("--width", type=float, default=0.2, help="width of new tracks of a net that has none (mm)")
    a = ap.parse_args(argv)
    if a.project:
        files = kicad_io.project_files(a.project)
        board, out = a.board or files["pcb"], a.out or files["out"]
    else:
        board, out = a.board, a.out
    if not board or not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"board file not found: {board or '(give a board file or --project)'}")
    if not out and not a.in_place:
        raise kicad_io.KicadIOError("give --project <board folder>, or a board file with --out <folder> (a repaired "
                                    "copy goes there) or with --in-place (the board itself is repaired)")
    kicad_io.need_kicad_python()                                # from here on: KiCad's own Python
    if not a.in_place:                                          # the design is not ours to change: repair a copy
        copy = os.path.join(out, "repaired", os.path.basename(board))
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        kicad_io.copy_board(board, copy, lock_source=False)
        board = copy
        print("working on the copy", copy)
    res = repair(board, finish=not a.no_finish, tie=tuple(a.tie), clean=not a.no_clean, protect=tuple(a.protect),
                 width=a.width, out=out or os.path.dirname(os.path.abspath(board)))
    print(f"repair: {res['result']} - {res['summary']}")
    return 0 if res["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
