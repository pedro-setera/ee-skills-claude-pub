"""Customer panel of one board: N by M copies, rails, mouse-bite bridges, fiducials, tooling holes; the panel's
board, its BOM and placement file, a description (JSON) and a rule file for the panel's own design-rule check.

What it does (on a private copy; the design is never changed)
    - Copies: the board stays where it is (copy 1); further columns to its right, further rows ABOVE it, `gap_mm`
      apart. Copies are numbered row by row. Designators become <ref>_<n>; a reference text that was visible is
      kept on the silkscreen under its old name. The nets of copy n > 1 are renamed <net>_<n> (KiCad would
      otherwise report the copies as unconnected) and the net-class patterns of the project are repeated for
      them.
    - Rails of `rail_mm` on the sides you name, `gap_mm` from the boards, each across the whole panel.
    - Bridges: per board side a list of offsets (mm) from the middle of that edge, positive to the right or
      downwards as KiCad shows the board. A bridge of `bridge_width_mm` crosses the gap to the rail or to the
      neighbouring board; the board's edge is opened there. Every board edge that a bridge joins gets one row of
      `holes` non-plated holes of `hole_d_mm` at `hole_pitch_mm`, the row `hole_offset_mm` outside the edge
      (default: half a hole, so the holes touch the edge and the break leaves almost no nub).
    - Fiducials (bare copper dot, mask opening) on the rails at three corners: top-left, bottom-left and
      bottom-right as KiCad shows the panel, `fid_edge_mm` from the panel side, `fid_end_mm` from the rail's end.
    - Tooling holes: NONE by default, and the result says what the order form must then say ("Tooling holes:
      Added by JLCPCB": the form and the files must agree; rule DFM-20). With `tooling_d_mm = 1.152` (JLCPCB's own
      size when its page was last read): non-plated holes with `tooling_mask_clear_mm` of solder-mask clearance,
      in the middle of a rail's width, `tooling_end_mm` from its end, at the three corners that carry the
      fiducials (`tooling_count = 2`: top-left and bottom-right); the result says "Added by Customer" and that
      this is not proven on a real order. Any other size is REFUSED, unless `tooling_not_jlcpcb` says that the
      panel does not go to JLCPCB: then plain non-plated holes of that size at both ends of every rail.
    - Parts fitted by hand ([bom] hand_fit, --hand-fit) lose their 3D model in the panel, so that renders and
      the supplier's viewer show what the assembly line delivers.
    - Zones and keep-out areas come along; a zone that reaches beyond the board's copper area and a keep-out that
      reaches beyond the outline are cut back (in a panel the copper would flow over the bridges and the
      keep-out would catch the panel's holes). The panel is filled in a process of its own and the saved fill
      is checked (layout/fill.py).
    - The panel is a KiCad project of its own: the board project's footprint library table, the libraries and
      the 3D models it keeps inside the project folder are copied below the panel's folder.
    - The panel's rule file: the board's own rule file with two rules added: every pair of holes keeps the
      board's minimum distance, except inside the mouse-bite sets, which may be as close as you made them. The
      panel project's hole-to-hole minimum is lowered to that value; everything else is the board's project.
    - BOM and placement file of the panel, made from the single board's files (the supplier's upload layout):
      designators suffixed, positions moved by each copy's offset.
    - Guided edges (rule DFM-31): the free bands of the board, the edge strips that a case holds in slots or
      rails, are read as layout/board.py reads them: board.toml [[keepout.band]], else the bands of
      <project>/mech/outline.json. A broken-off bridge leaves a nub, and a nub in a slot jams the board. With a
      board file alone (no --project) the bands are not known, and the result says so.
    REFUSED (exit 1, nothing written): a bridge nearer than `part_clear_mm` to a part that is on the board when
    the panel is broken apart; a bridge on a guided edge (its stretch on the board edge overlaps a free band's
    stretch on that edge), unless `nubs_removed_flush` is set: then the panel is built and the result names the
    bridges whose nubs must be removed flush, for the assembly note; a bridge that does not sit on a straight
    piece of the board's outline, or that overlaps another; a hole row that does not fit its bridge; a board
    without a bridge; a fiducial or tooling hole that does not fit its rail; tooling holes of a size that is
    not JLCPCB's own, unless `tooling_not_jlcpcb` is set.

Why it exists (real cases, told without names)
    A bridge right beside a small part bends the board under it when the panel is broken. Mouse-bite holes
    closer than the board's hole-to-hole rule tempt someone to switch the rule off for all holes, and then a real
    hole conflict passes. A hand-made placement file for several copies is easily off for one copy. Bridges on
    the edges a case guides leave nubs in the slots. Tooling holes of a size other than the assembler's own,
    declared "Added by Customer", can draw an engineering question; with no holes and "Added by JLCPCB" the
    order needs none.

Usage
    python -I panel.py --project <board folder>                 settings from board.toml [panel]; results in
                                                                <project>/out/panel/
    python -I panel.py <board.kicad_pcb> --out <folder> --rows 2 --rails left,right --bridge left=0.0
                       --bridge right=0.0 [more options, see --help]
    Results in the results folder:
        board/<name>-panel.kicad_pcb, .kicad_pro, .kicad_dru    the panel as a KiCad project of its own
        <name>-panel-bom.csv, <name>-panel-cpl.csv              when the single board's files were found
        panel.json, panel.md                                    geometry, distances, rules used, what was not checked
    Then check the panel like any board that is ordered (from the board folder, results in out/panel):
        python -I drc_run.py out/panel/board/<name>-panel.kicad_pcb --out out/panel --no-parity
        python -I jlc_rotations.py --project <board folder> --out out/panel --bom out/panel/<name>-panel-bom.csv
                                   test out/panel/board/<name>-panel.kicad_pcb --cpl out/panel/<name>-panel-cpl.csv
                                   (a second derivation; --project gives the footprint folder, and each copy <ref>_<n>
                                   takes board.toml's declared parts and bottom-side confirmation of <ref>)
        python -I fab_package.py --project <board folder> --out out/panel --name <name>-panel
                                 --bom out/panel/<name>-panel-bom.csv out/panel/board/<name>-panel.kicad_pcb
                                   (the panel's Gerbers in out/panel/jlc/gerbers/, where edge_check.py --project
                                   measures them), and LOOK at a render of it.

board.toml keys (all optional; the command line wins; without a board.toml the defaults apply and are printed)
    [panel]
    columns = 1                 rows = 2
    gap_mm = 2.0                # between boards, and between boards and rails
    rails = ["left", "right"]   # sides of the panel that get a rail (default: none)
    rail_mm = 5.0
    bridge_width_mm = 5.0
    hole_d_mm = 0.6             holes = 5           hole_pitch_mm = 1.0        hole_offset_mm = 0.3
    part_clear_mm = 2.0         # a bridge keeps this distance to the courtyard (without one: the pads) of every
                                # part that is fitted before the panel is broken apart. The default is the
                                # starting point of rule DFM-31 (about 2 mm), not a supplier's figure.
    nubs_removed_flush = false  # true: bridges on guided edges are allowed; the result then names them, and the
                                # assembly note must say that their nubs are removed flush (rule DFM-31)
    fiducial_d_mm = 1.0         fiducial_mask_d_mm = 2.0       fid_edge_mm = 3.85      fid_end_mm = 6.0
    tooling_d_mm = 1.152        # no default: without it no tooling hole is drawn, and the order form says
                                # "Tooling holes: Added by JLCPCB". 1.152 (within 0.005): JLCPCB's own kind, order
                                # form "Added by Customer", not proven on a real order. Any other size: refused.
    tooling_mask_clear_mm = 0.148   # solder-mask clearance around a 1.152 mm hole (opening 1.448 mm, both sides)
    tooling_count = 3           # 3: the corners of the fiducials; 2: top-left and bottom-right
    tooling_end_mm = 2.5        # hole centre from the rail's end; always in the middle of the rail's width
    tooling_not_jlcpcb = false  # true: the panel does not go to JLCPCB; holes of any tooling_d_mm, plain, at both
                                # ends of every rail (for JLCPCB other sizes can draw an engineering question)
    bom = "out/jlc/x-bom.csv"   cpl = "out/jlc/x-cpl.csv"      # default: <project>/out/jlc/<name>-bom.csv, -cpl.csv
    [panel.bridges]             # offsets in mm from the middle of each board edge
    left = [0.0]                right = [0.0]       top = []       bottom = []
    [bom] hand_fit = ["J1"]     dnp = ["R9"]        # as in fab_package.py: not on the board when the panel is broken
    [[keepout.band]]            # the free bands (guided edges), with the keys layout/board.py reads: name, width,
    name = "upper slot"         # and edge (left, right, top, bottom; optional span) or line. When board.toml has
    edge = "top"  width = 1.5   # none, the "keepouts" of <project>/mech/outline.json with "kind": "band" are used.
    [fab] name = "myboard"      # base name of the single board's BOM and placement file
    [project] name, kicad_dir, out_dir (through kicad_io)
    The defaults are common values that matched the supplier's pages when this script was written (as read in
    2026-11: rails 5 mm, gap 2 mm, holes 0.6 mm in sets of 5 at 1.0 mm, fiducials 1 mm with a 2 mm opening 3.85 mm
    from the panel side). Supplier rules age: read the live pages before every order.

Exit codes
    0  PASS: the panel was built, its saved fill passed the check, the tables were written or were not asked for
    1  FAIL: refused (see above), a failed fill check, a BOM or placement file that does not fit the board
    2  CANNOT RUN: KiCad not found, unreadable board, an outline that is not one closed shape, no settings. Never a pass.

Where it stops, and what is not checked here
    One board type per panel; rectangular grid; no V-cut panels (gap_mm must be larger than 0); top-side
    fiducials only. A bridge needs a straight outline piece on the board's bounding box. The supplier's rules
    for panels (sizes, rails, fiducials, minimum slot width) are not known to this script: an independent
    reader checks the panel against the live pages. Custom rules that name nets apply to copy 1 only (the
    other copies' nets carry a suffix): run the board's own checks on the single board. Not checked here: the
    rule check of the panel (drc_run.py with the rule file written here), copper to the panel's edges on the
    Gerbers (edge_check.py), the placement file against the supplier's own footprints (jlc_rotations.py).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import csv
import datetime
import io
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402

SIDES = ("left", "right", "top", "bottom")
OPPOSITE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
# board.toml [panel] key, default, help. The defaults: common values (see the head of this file).
KEYS = [("columns", 1, "copies side by side"), ("rows", 1, "copies above each other"),
        ("gap_mm", 2.0, "space between boards and between boards and rails"),
        ("rail_mm", 5.0, "width of a rail"), ("bridge_width_mm", 5.0, "width of a bridge along the board edge"),
        ("hole_d_mm", 0.6, "mouse-bite hole diameter"), ("holes", 5, "mouse-bite holes per row"),
        ("hole_pitch_mm", 1.0, "mouse-bite hole pitch"),
        ("hole_offset_mm", None, "hole row outside the board edge (default: half a hole diameter)"),
        ("part_clear_mm", 2.0, "smallest distance of a bridge to a fitted part (the starting point of rule DFM-31)"),
        ("fiducial_d_mm", 1.0, "fiducial copper diameter"), ("fiducial_mask_d_mm", 2.0, "fiducial mask opening"),
        ("fid_edge_mm", 3.85, "fiducial centre from the panel side"), ("fid_end_mm", 6.0, "fiducial centre from the rail's end"),
        ("tooling_d_mm", None, "tooling hole diameter (no default: none is drawn; 1.152 is JLCPCB's own, any other "
                               "size needs --tooling-not-jlcpcb)"),
        ("tooling_mask_clear_mm", 0.148, "solder-mask clearance around a 1.152 mm tooling hole"),
        ("tooling_count", 3, "1.152 mm tooling holes: 3 (the fiducials' corners) or 2 (top-left, bottom-right)"),
        ("tooling_end_mm", 2.5, "tooling hole centre from the rail's ends")]
MB, FID, TH = "PANEL_MB", "PANEL_FID", "PANEL_TH"          # references of the panel's own footprints
JLC_TOOLING_D = 1.152                                      # mm: JLCPCB's own tooling hole when its page was last read
CORNERS = (("top-left", "left", "top"), ("bottom-left", "left", "bottom"), ("bottom-right", "right", "bottom"))
#           the panel corners that carry a fiducial: none at the top right, so the orientation is unambiguous
NM = 1_000_000                                             # KiCad's unit: nanometres


class Refused(kicad_io.KicadIOError):
    """The panel as asked for must not be built: a finding (exit code 1), not "could not run"."""
    exit_code = 1


def nm(v: float) -> int:
    return int(round(float(v) * NM))


def mm(v: int) -> float:
    return round(v / NM, 6)


# ---- settings ----------------------------------------------------------------------------------------------------------
def _option(key: str) -> str:
    return "--" + key.removesuffix("_mm").replace("_", "-")


def read_settings(a, toml: dict) -> tuple[dict, list]:
    """The panel's settings from board.toml [panel] and the command line (which wins); the defaults that were used."""
    t = toml.get("panel", {}) if isinstance(toml.get("panel"), dict) else {}
    cfg, defaults = {}, []
    for key, default, _ in KEYS:
        val = getattr(a, key)
        if val is None:
            val = t.get(key)
        if val is None:
            val = default
            if default is not None:
                defaults.append(f"{key} = {default}")
        cfg[key] = val
    if cfg["hole_offset_mm"] is None:
        cfg["hole_offset_mm"] = cfg["hole_d_mm"] / 2
        defaults.append(f"hole_offset_mm = {cfg['hole_offset_mm']:g} (half a hole)")
    rails = a.rails.split(",") if a.rails is not None else t.get("rails", [])
    cfg["rails"] = [s.strip() for s in rails if s.strip()]
    bridges = {s: [float(v) for v in (t.get("bridges", {}) or {}).get(s, [])] for s in SIDES}
    for item in a.bridge or []:
        side, _, offs = item.partition("=")
        if side not in SIDES or not offs:
            raise kicad_io.KicadIOError(f"--bridge {item}: write SIDE=OFFSET[,OFFSET...] with SIDE one of {', '.join(SIDES)}")
        bridges[side] = [float(v) for v in offs.split(",")]
    cfg["bridges"] = bridges
    bom = toml.get("bom", {}) if isinstance(toml.get("bom"), dict) else {}
    cfg["hand_fit"] = sorted(set(bom.get("hand_fit", [])) | {r.strip() for x in a.hand_fit or [] for r in x.split(",") if r.strip()})
    cfg["dnp"] = sorted(set(bom.get("dnp", [])))
    cfg["nubs_removed_flush"] = bool(a.nubs_removed_flush or t.get("nubs_removed_flush", False))
    cfg["tooling_not_jlcpcb"] = bool(a.tooling_not_jlcpcb or t.get("tooling_not_jlcpcb", False))
    bad = [s for s in cfg["rails"] if s not in SIDES]
    if bad:
        raise kicad_io.KicadIOError(f"rails: {bad} is not one of {', '.join(SIDES)}")
    for key in ("columns", "rows", "holes"):
        if int(cfg[key]) != cfg[key] or cfg[key] < 1:
            raise kicad_io.KicadIOError(f"{key} must be a whole number of 1 or more")
        cfg[key] = int(cfg[key])
    if cfg["tooling_count"] not in (2, 3):
        raise kicad_io.KicadIOError("tooling_count must be 2 or 3")
    cfg["tooling_count"] = int(cfg["tooling_count"])
    for key, _, _ in KEYS:
        least = -1e-9 if key in ("hole_offset_mm", "tooling_mask_clear_mm") else 0
        if key.endswith("_mm") and cfg[key] is not None and not float(cfg[key]) > least:
            raise kicad_io.KicadIOError(f"{key} must be larger than 0" + (
                " (a panel without a gap, a V-cut panel, is not made here)" if key == "gap_mm" else ""))
    unused = ("tooling_",) if not cfg["tooling_d_mm"] else () if own_tooling(cfg) else ("tooling_mask", "tooling_count")
    return cfg, [d for d in defaults if not d.startswith(unused)] if unused else defaults


def own_tooling(cfg: dict) -> bool:
    """True when the tooling holes asked for are JLCPCB's own kind (its size, within 0.005 mm)."""
    return bool(cfg["tooling_d_mm"]) and abs(cfg["tooling_d_mm"] - JLC_TOOLING_D) <= 0.005 + 1e-9


# ---- the geometry: plain numbers in nanometres, KiCad's frame (x right, y down) ---------------------------------------
def band_stretch(poly: list, side: str, box: tuple):
    """The piece of one side of the board's box that a free band covers: (lo, hi) along that side, or None.
    poly: the band's strip, a convex four-corner polygon (as layout/board.py makes it)."""
    x0, y0, x1, y1 = box
    upright = side in ("left", "right")
    fixed = {"left": x0, "right": x1, "top": y0, "bottom": y1}[side]
    seen = []
    for i in range(len(poly)):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
        (af, av), (bf, bv) = ((ax, ay), (bx, by)) if upright else ((ay, ax), (by, bx))     # (across, along) the side
        if abs(af - fixed) <= 1000:                                      # a corner of the strip on this side's line
            seen.append(av)
        elif abs(bf - fixed) > 1000 and (af - fixed) * (bf - fixed) < 0:  # an edge of the strip crosses the line
            seen.append(av + (bv - av) * (fixed - af) / (bf - af))
    if not seen:
        return None
    lo, hi = max(min(seen), y0 if upright else x0), min(max(seen), y1 if upright else x1)
    return (int(round(lo)), int(round(hi))) if hi - lo > 1000 else None


def plan(cfg: dict, info: dict) -> dict:
    """Where everything goes. info: "box" of the board, "sides" {side: [(lo, hi)]} the straight outline pieces on
    each side of the box, "parts" [(ref, box)] fitted when the panel is broken, "bands" [{"name", "stretch":
    {side: (lo, hi)}}] the free bands (guided edges). Raises Refused with every reason."""
    x0, y0, x1, y1 = info["box"]
    w, h = x1 - x0, y1 - y0
    gap, rail, bw = nm(cfg["gap_mm"]), nm(cfg["rail_mm"]), nm(cfg["bridge_width_mm"])
    hd, pitch, hoff = nm(cfg["hole_d_mm"]), nm(cfg["hole_pitch_mm"]), nm(cfg["hole_offset_mm"])
    cols, rows, rails = cfg["columns"], cfg["rows"], cfg["rails"]
    why: list[str] = []
    notes: list[str] = []
    copies = [{"n": r * cols + c + 1, "column": c, "row": r, "dx": c * (w + gap), "dy": -r * (h + gap)}
              for r in range(rows) for c in range(cols)]
    at = {(c["column"], c["row"]): c for c in copies}
    ax0, ax1, ay1 = x0, x0 + cols * w + (cols - 1) * gap, y1
    ay0 = y1 - rows * h - (rows - 1) * gap
    px0, px1 = ax0 - (gap + rail if "left" in rails else 0), ax1 + (gap + rail if "right" in rails else 0)
    py0, py1 = ay0 - (gap + rail if "top" in rails else 0), ay1 + (gap + rail if "bottom" in rails else 0)
    rail_box = {"left": (px0, py0, px0 + rail, py1), "right": (px1 - rail, py0, px1, py1),
                "top": (px0, py0, px1, py0 + rail), "bottom": (px0, py1 - rail, px1, py1)}
    rail_box = {s: rail_box[s] for s in SIDES if s in rails}
    if (cfg["holes"] - 1) * pitch + hd > bw:
        why.append(f"a row of {cfg['holes']} holes of {cfg['hole_d_mm']:g} mm at {cfg['hole_pitch_mm']:g} mm is longer than "
                   f"the bridge is wide ({cfg['bridge_width_mm']:g} mm)")
    if hoff + hd / 2 > gap:
        why.append(f"the hole row ({cfg['hole_offset_mm']:g} mm outside the edge) does not fit the gap of {cfg['gap_mm']:g} mm")

    def neighbour(c: dict, side: str):
        col, row = c["column"] + {"left": -1, "right": 1}.get(side, 0), c["row"] + {"top": 1, "bottom": -1}.get(side, 0)
        return at.get((col, row)) or ("rail" if side in rails else None)

    def foot_ok(side: str, lo: int, hi: int) -> bool:                    # in the board's own frame
        return any(a <= lo and hi <= b for a, b in info["sides"][side])

    def distance(side: str, lo: int, hi: int):                          # the nearest fitted part to a bridge's foot
        fixed = {"left": x0, "right": x1, "top": y0, "bottom": y1}[side]
        best = (None, None)
        for ref, (bx0, by0, bx1, by1) in info["parts"]:
            if side in ("left", "right"):
                d = math.hypot(max(bx0 - fixed, fixed - bx1, 0), max(by0 - hi, lo - by1, 0))
            else:
                d = math.hypot(max(bx0 - hi, lo - bx1, 0), max(by0 - fixed, fixed - by1, 0))
            if best[0] is None or d < best[0]:
                best = (d, ref)
        return best

    bridges: dict = {}
    feet: dict = {}                                                      # (copy n, side) -> [(lo, hi)] panel frame
    for c in copies:
        bx0, by0, bx1, by1 = x0 + c["dx"], y0 + c["dy"], x1 + c["dx"], y1 + c["dy"]
        for side in SIDES:
            other = neighbour(c, side)
            for off in cfg["bridges"][side]:
                if other is None:
                    notes.append(f"copy {c['n']}, {side}: nothing faces this edge (no rail, no board): the bridge at "
                                 f"{off:g} mm is not made")
                    continue
                mid = (by0 + by1) // 2 if side in ("left", "right") else (bx0 + bx1) // 2
                lo, hi = mid + nm(off) - bw // 2, mid + nm(off) - bw // 2 + bw
                box = {"left": (bx0 - gap, lo, bx0, hi), "right": (bx1, lo, bx1 + gap, hi),
                       "top": (lo, by0 - gap, hi, by0), "bottom": (lo, by1, hi, by1 + gap)}[side]
                ends = [(c, side)] + ([(other, OPPOSITE[side])] if other != "rail" else [])
                br = bridges.setdefault(box, {"id": f"B{len(bridges) + 1}", "box": box, "feet": [], "nearest": (None, None),
                                              "guided": []})
                for cc, s in ends:
                    shift = cc["dy"] if s in ("left", "right") else cc["dx"]
                    if (cc["n"], s) in [(f["copy"], f["side"]) for f in br["feet"]]:
                        continue
                    for band in info.get("bands", []):                  # a nub on a guided edge jams the board
                        on = band["stretch"].get(s)
                        if on and lo - shift < on[1] and on[0] < hi - shift:
                            if band["name"] not in br["guided"]:
                                br["guided"].append(band["name"])
                            if not cfg["nubs_removed_flush"]:
                                why.append(f"copy {cc['n']}, {s} edge: the bridge at offset {off:g} mm lies on a guided edge "
                                           f"(free band '{band['name']}'): its nub would stand in the slot or rail. Put the "
                                           "bridge on an edge that is not guided, or set nubs_removed_flush = true and "
                                           "have the nubs removed flush (rule DFM-31)")
                    if not foot_ok(s, lo - shift, hi - shift):
                        why.append(f"copy {cc['n']}, {s} edge: the bridge at {mm(lo - shift):g} .. {mm(hi - shift):g} mm does "
                                   "not sit on one straight piece of the outline on that side of the board's box")
                    d, ref = distance(s, lo - shift, hi - shift)
                    if d is not None and (br["nearest"][0] is None or d < br["nearest"][0]):
                        br["nearest"] = (d, ref)
                    if d is not None and d < nm(cfg["part_clear_mm"]) - 1:
                        why.append(f"copy {cc['n']}, {s} edge: the bridge at offset {off:g} mm is {mm(d):.3f} mm from {ref} "
                                   f"(limit part_clear_mm = {cfg['part_clear_mm']:g}): move the bridge or the part")
                    br["feet"].append({"copy": cc["n"], "side": s, "span": (lo, hi)})
                    feet.setdefault((cc["n"], s), []).append((lo, hi))
    for (n, side), spans in feet.items():
        spans.sort()
        if any(b[0] <= a[1] for a, b in zip(spans, spans[1:])):
            why.append(f"copy {n}, {side} edge: two bridges overlap or touch")
    for c in copies:
        if not any((c["n"], s) in feet for s in SIDES):
            why.append(f"copy {c['n']} has no bridge: it would fall out of the panel")
    # one row of holes at every board edge that a bridge joins
    bites = []
    for br in bridges.values():
        for f in br["feet"]:
            c = copies[f["copy"] - 1]
            centre = (f["span"][0] + f["span"][1]) // 2
            along = [centre + int(round((i - (cfg["holes"] - 1) / 2) * pitch)) for i in range(cfg["holes"])]
            fixed = {"left": x0 + c["dx"] - hoff, "right": x1 + c["dx"] + hoff, "top": y0 + c["dy"] - hoff,
                     "bottom": y1 + c["dy"] + hoff}[f["side"]]
            pts = [(fixed, v) if f["side"] in ("left", "right") else (v, fixed) for v in along]
            bites.append({"ref": f"{MB}{len(bites) + 1}", "copy": f["copy"], "side": f["side"], "holes": pts})
    # fiducials at three corners, each on a rail; tooling holes in the rails
    fids, tooling = [], []
    fe, fend, fr = nm(cfg["fid_edge_mm"]), nm(cfg["fid_end_mm"]), nm(cfg["fiducial_mask_d_mm"]) // 2
    for name, sx, sy in CORNERS:
        ex, ey = (px0, 1) if sx == "left" else (px1, -1), (py0, 1) if sy == "top" else (py1, -1)
        if sx in rail_box:                                               # on the upright rail
            pt, r = (ex[0] + ex[1] * fe, ey[0] + ey[1] * fend), rail_box[sx]
        elif sy in rail_box:
            pt, r = (ex[0] + ex[1] * fend, ey[0] + ey[1] * fe), rail_box[sy]
        else:
            notes.append(f"fiducial {name}: no rail at that corner, not placed")
            continue
        if not (r[0] <= pt[0] - fr and pt[0] + fr <= r[2] and r[1] <= pt[1] - fr and pt[1] + fr <= r[3]):
            why.append(f"fiducial {name}: its mask opening of {cfg['fiducial_mask_d_mm']:g} mm does not fit the rail "
                       f"{cfg['fid_edge_mm']:g} mm from the panel side")
        fids.append(pt)
    own, td = own_tooling(cfg), cfg["tooling_d_mm"]
    if td and not own and not cfg["tooling_not_jlcpcb"]:
        why.append(f"tooling holes of {td:g} mm are not JLCPCB's: other sizes can draw an engineering question. "
                   'Leave them out (order form "Added by JLCPCB"), or use 1.152 mm, or set tooling_not_jlcpcb = '
                   "true for a panel that does not go to JLCPCB.")
    elif td:
        te, reach = nm(cfg["tooling_end_mm"]), nm(td) // 2 + (nm(cfg["tooling_mask_clear_mm"]) if own else 0)

        def spot(s: str, first: bool) -> tuple:                         # middle of the rail's width, `te` from one end
            r = rail_box[s]
            if s in ("left", "right"):
                return (r[0] + r[2]) // 2, r[1] + te if first else r[3] - te
            return r[0] + te if first else r[2] - te, (r[1] + r[3]) // 2
        spots = []
        if own:                                                         # JLCPCB's kind: at the fiducials' corners
            for name, sx, sy in CORNERS if cfg["tooling_count"] == 3 else (CORNERS[0], CORNERS[2]):
                s = sx if sx in rail_box else sy if sy in rail_box else None
                if s is None:
                    notes.append(f"tooling hole {name}: no rail at that corner, not placed")
                else:
                    spots.append((s, spot(s, sy == "top" if s in ("left", "right") else sx == "left")))
        else:                                                           # not for JLCPCB: both ends of every rail
            spots = [(s, spot(s, first)) for s in rail_box for first in (True, False)]
        for s, pt in spots:
            r = rail_box[s]
            if not (r[0] < pt[0] - reach and pt[0] + reach < r[2] and r[1] < pt[1] - reach and pt[1] + reach < r[3]):
                why.append(f"tooling hole of {td:g} mm does not fit the {s} rail")
            elif pt not in tooling:
                tooling.append(pt)
        if own and cfg["tooling_not_jlcpcb"]:
            notes.append(f"tooling_not_jlcpcb is set, but {td:g} mm is JLCPCB's own size: the holes are drawn as JLCPCB's kind")
    if not rail_box:
        notes.append("no rails: no fiducials and no tooling holes on this panel")
    if why:
        raise Refused("the panel is refused, nothing was written:\n  " + "\n  ".join(dict.fromkeys(why)))
    if not tooling:
        tooling_line = 'Tooling holes: none in the files. Order form: "Tooling holes: Added by JLCPCB".'
    elif own:
        tooling_line = (f'Tooling holes: {len(tooling)} x {td:g} mm in the files. Order form: "Tooling holes: Added by '
                        'Customer". Not proven on a real order: JLCPCB may still ask to add its own. Positions are this '
                        "script's, not JLCPCB's: read its live page.")
    else:
        tooling_line = (f"Tooling holes: {len(tooling)} x {td:g} mm, not JLCPCB's kind (tooling_not_jlcpcb). For JLCPCB "
                        'the order form would have to say "Added by JLCPCB" and the engineer will ask.')
    guided = [br for br in bridges.values() if br["guided"]]
    line = ""
    if guided:                                                          # allowed by nubs_removed_flush: say what it costs
        line = (f"bridges {', '.join(br['id'] for br in guided)} lie on guided edges "
                f"({', '.join(dict.fromkeys(n for br in guided for n in br['guided']))}): their nubs must be removed "
                "flush; write this into the assembly note (DFM-31)")
        notes.append(line)
    return {"copies": copies, "box": (px0, py0, px1, py1), "rails": rail_box, "bridges": list(bridges.values()),
            "feet": feet, "bites": bites, "fiducials": fids, "tooling": tooling, "notes": notes, "guided_line": line,
            "tooling_line": tooling_line,
            "tooling_mask_clear": nm(cfg["tooling_mask_clear_mm"]) if tooling and own else None}


def boundary(material: list, boards: list) -> list:
    """The outline of rails and bridges as segments (x0, y0, x1, y1): on a grid through every corner, each edge
    between a cell of material and an empty cell; edges toward a board's box are left open (the bridge joins it)."""
    xs = sorted({v for r in material + boards for v in (r[0], r[2])})
    ys = sorted({v for r in material + boards for v in (r[1], r[3])})

    def kind(i: int, j: int) -> int:
        if not (0 <= i < len(xs) - 1 and 0 <= j < len(ys) - 1):
            return 0
        cx, cy = xs[i] + xs[i + 1], ys[j] + ys[j + 1]                     # twice the cell's centre: whole numbers
        for value, rects in ((1, material), (2, boards)):
            if any(2 * r[0] < cx < 2 * r[2] and 2 * r[1] < cy < 2 * r[3] for r in rects):
                return value
        return 0
    cell = {(i, j): kind(i, j) for i in range(-1, len(xs)) for j in range(-1, len(ys))}
    segs = []
    for upright in (True, False):
        lines, steps = (xs, ys) if upright else (ys, xs)
        for i, fixed in enumerate(lines):
            start = None
            for j in range(len(steps) - 1):
                a, b = (cell[(i - 1, j)], cell[(i, j)]) if upright else (cell[(j, i - 1)], cell[(j, i)])
                on = {a, b} == {0, 1}
                if on and start is None:
                    start = steps[j]
                if start is not None and (not on or j == len(steps) - 2):
                    end = steps[j + 1] if on else steps[j]
                    segs.append((fixed, start, fixed, end) if upright else (start, fixed, end, fixed))
                    start = None
    return segs


def rule_text(own: str, board_min: float, bite_min: float) -> str:
    """The panel's rule file: the board's own rules between two added ones. KiCad takes the LAST rule that
    matches, so the mouse-bite rule stands at the end and the general one right after the version line."""
    first = (f'(rule "panel: holes keep the board\'s minimum, except inside a mouse-bite set"\n  (severity error)\n'
             f"  (condition \"!(A.memberOfFootprint('{MB}*') && B.memberOfFootprint('{MB}*'))\")\n"
             f"  (constraint hole_to_hole (min {board_min:g}mm)))\n")
    last = (f'(rule "panel: holes of a mouse-bite set"\n  (severity error)\n'
            f"  (condition \"A.memberOfFootprint('{MB}*') && B.memberOfFootprint('{MB}*')\")\n"
            f"  (constraint hole_to_hole (min {bite_min:g}mm)))\n")
    m = re.search(r"^[ \t]*\(\s*version\s+\d+\s*\)[ \t]*\r?\n?", own, re.M)
    head, body = (own[:m.end()], own[m.end():]) if m else ("(version 1)\n", own)
    return head.rstrip("\r\n") + "\n\n" + first + "\n" + body.strip("\r\n") + ("\n\n" if body.strip() else "") + last


# ---- the tables: from the single board's files ---------------------------------------------------------------------------
def _read_csv(path: str) -> list:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.reader(f) if r]


def _csv_text(rows: list) -> str:
    s = io.StringIO()
    csv.writer(s, lineterminator="\r\n").writerows(rows)
    return s.getvalue()


def tables(bom: str, cpl: str, copies: list, refs: set) -> tuple[str, str, list]:
    """(BOM text, placement text, problems) of the panel from the single board's files in the supplier's upload
    layout: BOM with a Designator column; placement file with Designator, Mid X, Mid Y (Mid Y = -y of KiCad)."""
    why = []
    b, c = _read_csv(bom), _read_csv(cpl)

    def col(rows, name, what):
        low = [h.strip().lower() for h in rows[0]] if rows else []
        if name not in low:
            why.append(f"{what}: no column '{name}' (the supplier's upload layout is expected)")
            return None
        return low.index(name)
    bd, cd, cx, cy = col(b, "designator", "BOM"), col(c, "designator", "placement file"), \
        col(c, "mid x", "placement file"), col(c, "mid y", "placement file")
    if why:
        return "", "", why
    out_b, out_c = [b[0]], [c[0]]
    for row in b[1:]:
        names = [r.strip() for r in row[bd].split(",") if r.strip()]
        why += [f"BOM: {r} is not a part of the board" for r in names if r not in refs]
        out_b.append(row[:bd] + [",".join(f"{r}_{k['n']}" for r in names for k in copies)] + row[bd + 1:])

    def moved(text: str, by: float) -> str:
        num = text.strip().removesuffix("mm")
        places = len(num.partition(".")[2])
        return f"{float(num) + by:.{places}f}" + ("mm" if text.strip().endswith("mm") else "")
    for row in c[1:]:
        ref = row[cd].strip()
        if ref not in refs:
            why.append(f"placement file: {ref} is not a part of the board")
            continue
        for k in copies:
            new = list(row)
            new[cd], new[cx], new[cy] = f"{ref}_{k['n']}", moved(row[cx], mm(k["dx"])), moved(row[cy], -mm(k["dy"]))
            out_c.append(new)
    return _csv_text(out_b), _csv_text(out_c), why


# ---- the board: everything below needs KiCad's Python ---------------------------------------------------------------------
def _segment(b, pcbnew, a, c, width):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
    s.SetEnd(pcbnew.VECTOR2I(int(c[0]), int(c[1])))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(width)
    b.Add(s)
    return s


def _copy(item):
    """A copy of a board item with its own identity (KiCad 10 asks whether to add it to the item's group: no)."""
    try:
        return item.Duplicate().Cast()
    except TypeError:
        return item.Duplicate(False).Cast()


def read_board(b, pcbnew, cfg: dict) -> dict:
    """What the plan needs from the board (a private copy): the box of its outline, the straight outline pieces on
    each side of the box (rectangles and polygons on Edge.Cuts are first turned into segments), the parts."""
    from layout import board_outline
    ps = board_outline(b)
    if ps is None or ps.OutlineCount() != 1:
        raise kicad_io.KicadIOError("the outline on Edge.Cuts is not one closed shape (a panel needs exactly one board)")
    bb = ps.BBox()
    box = (bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom())
    edges = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetClass() == "PCB_SHAPE"]
    width = max([d.GetWidth() for d in edges] + [nm(0.05)])
    for d in list(edges):                                                # shapes with straight sides become segments
        if d.GetShape() == pcbnew.SHAPE_T_POLY:
            o = d.GetPolyShape().Outline(0)
            pts = [(o.CPoint(i).x, o.CPoint(i).y) for i in range(o.PointCount())]
        elif d.GetShape() == pcbnew.SHAPE_T_RECTANGLE and not (hasattr(d, "GetCornerRadius") and d.GetCornerRadius()):
            pts = [(p.x, p.y) for p in d.GetRectCorners()]
        else:
            continue
        edges.remove(d)
        edges += [_segment(b, pcbnew, pts[i], pts[(i + 1) % len(pts)], width) for i in range(len(pts))]
        b.Delete(d)
    sides: dict = {s: [] for s in SIDES}
    side_shapes = []
    for d in edges:
        if d.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        (xa, ya), (xb, yb) = (d.GetStart().x, d.GetStart().y), (d.GetEnd().x, d.GetEnd().y)
        side = None
        if abs(xa - xb) <= 1000 and ya != yb:
            side = "left" if abs(xa - box[0]) <= 1000 else "right" if abs(xa - box[2]) <= 1000 else None
            span = (min(ya, yb), max(ya, yb))
        elif abs(ya - yb) <= 1000 and xa != xb:
            side = "top" if abs(ya - box[1]) <= 1000 else "bottom" if abs(ya - box[3]) <= 1000 else None
            span = (min(xa, xb), max(xa, xb))
        if side:
            sides[side].append(span)
            side_shapes.append(d)
    parts, off = [], set(cfg["hand_fit"]) | set(cfg["dnp"])
    for fp in b.GetFootprints():
        if fp.GetReference() in off or fp.IsDNP() or not any(p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH for p in fp.Pads()):
            continue
        fp.BuildCourtyardCaches()
        boxes = [c.BBox() for c in (fp.GetCourtyard(pcbnew.F_CrtYd), fp.GetCourtyard(pcbnew.B_CrtYd)) if c.OutlineCount()]
        boxes = boxes or [p.GetBoundingBox() for p in fp.Pads()]
        parts.append((fp.GetReference(), (min(q.GetX() for q in boxes), min(q.GetY() for q in boxes),
                                          max(q.GetRight() for q in boxes), max(q.GetBottom() for q in boxes))))
    return {"box": box, "sides": sides, "side_shapes": side_shapes, "parts": parts, "width": width, "outline": ps,
            "refs": {fp.GetReference() for fp in b.GetFootprints()},
            "edge_clearance": b.GetDesignSettings().m_CopperEdgeClearance,
            "hole_to_hole": b.GetDesignSettings().m_HoleToHoleMin}


def read_bands(project: str | None, toml: dict, box: tuple) -> tuple[list, str]:
    """The free bands of the board (edge strips that a case holds in slots or rails), read as layout/board.py
    reads them: board.toml [[keepout.band]], else the bands of <project>/mech/outline.json; laid on the box of the
    board file's own outline. Returns ([{"name", "width_mm", "stretch": {side: (lo, hi)}}], where they come from).
    A board file alone has no place to say them: ([], "free bands not known: a board file alone")."""
    if not project:
        return [], "free bands not known: a board file alone"
    from layout import board as B
    given = (toml.get("keepout", {}) or {}).get("band") if isinstance(toml.get("keepout"), dict) else None
    keepouts, source = [], "board.toml"
    if not given:
        path = os.path.join(project, "mech", "outline.json")
        if not os.path.isfile(path):
            return [], "no free band is defined (no [[keepout.band]] in board.toml, no mech/outline.json)"
        try:
            with open(path, encoding="utf-8") as f:
                keepouts = json.load(f).get("keepouts", [])
        except (OSError, ValueError, AttributeError) as e:
            raise kicad_io.KicadIOError(f"{path}: {e}") from None
        keepouts = [k for k in keepouts if isinstance(k, dict) and k.get("kind", "band") == "band"] \
            if isinstance(keepouts, list) else []
        source = "mech/outline.json"
    mech = B.Mech({"outline": {"rect": [mm(v) for v in box]}, "keepouts": keepouts}, given or None)
    bands = []
    for band in mech.bands:
        poly = [(nm(x), nm(y)) for x, y in band["poly"]]
        on = {s: st for s in SIDES for st in [band_stretch(poly, s, box)] if st}
        bands.append({"name": band["name"], "width_mm": band["width"], "stretch": on})
    return bands, (f"free bands from {source}" if bands else f"no free band is defined in {source}")


def _feature(b, pcbnew, ref: str, value: str, pts: list, d: int, mask: int = 0, clear: int | None = None):
    """A footprint of the panel itself (not in the BOM, not placed): non-plated holes (clear: their solder-mask
    clearance, else the board's own), or a fiducial when `mask`."""
    fp = pcbnew.FOOTPRINT(b)
    fp.SetReference(ref)
    fp.SetValue(value)
    for f in (fp.Reference(), fp.Value()):
        f.SetVisible(False)
        f.SetLayer(pcbnew.F_Fab)
    for mark in (fp.SetBoardOnly, fp.SetExcludedFromBOM, fp.SetExcludedFromPosFiles, fp.SetAllowMissingCourtyard):
        mark(True)
    b.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(int(pts[0][0]), int(pts[0][1])))
    for x, y in pts:
        p = pcbnew.PAD(fp)
        p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.VECTOR2I(d, d))
        if mask:                                                         # bare copper dot, mask opening around it
            p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            ls = pcbnew.LSET()
            ls.AddLayer(pcbnew.F_Cu)
            ls.AddLayer(pcbnew.F_Mask)
            p.SetLayerSet(ls)
            p.SetLocalSolderMaskMargin((mask - d) // 2)
        else:
            p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            p.SetDrillSize(pcbnew.VECTOR2I(d, d))
            p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())                 # all copper layers and both mask layers
            if clear is not None:
                p.SetLocalSolderMaskMargin(clear)
        p.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
        fp.Add(p)
    return fp


def build(b, pcbnew, cfg: dict, info: dict, p: dict, local: set) -> list:
    """Turn the loaded copy of the board into the panel. Returns notes; `local` receives the names of the 3D
    models that the footprints take from the board's own project folder."""
    notes = []
    for d in info["side_shapes"]:                                        # the outline pieces that bridges may open
        b.Delete(d)
    fps, tracks = list(b.GetFootprints()), list(b.GetTracks())
    zones, drawings = list(b.Zones()), list(b.GetDrawings())
    clip_test, clip = pcbnew.SHAPE_POLY_SET(info["outline"]), pcbnew.SHAPE_POLY_SET(info["outline"])
    edge = info["edge_clearance"]
    clip_test.Deflate(max(edge - nm(0.05), 0), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, nm(0.002))
    clip.Deflate(edge, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, nm(0.002))
    for z in zones:                                                      # what was drawn beyond the board: in a panel
        area = z.GetIsRuleArea()                                         # a zone's copper would flow over a bridge,
        over = pcbnew.SHAPE_POLY_SET(z.Outline())                        # a keep-out would catch the panel's holes
        over.BooleanSubtract(info["outline"] if area else clip_test)
        if over.Area() > 1e9:                                            # 0.001 mm2
            z.Outline().BooleanIntersection(info["outline"] if area else clip)
            z.UnFill()
            notes.append(f"{'keep-out' if area else 'zone'} '{z.GetZoneName() or z.GetNetname()}' reached beyond "
                         + ("the board's outline" if area else "the board's copper area")
                         + ": in the panel its outline is cut back to it")

    def keep_name(fp, old: str) -> None:                                 # the silkscreen keeps the board's own names
        ref = fp.Reference()
        if ref.IsVisible():
            t = pcbnew.PCB_TEXT(fp)
            t.SetText(old)
            t.SetLayer(ref.GetLayer())
            t.SetAttributes(ref.GetAttributes())
            t.SetPosition(ref.GetPosition())
            fp.Add(t)
            ref.SetVisible(False)
    for c in p["copies"][1:]:
        shift, nets = pcbnew.VECTOR2I(int(c["dx"]), int(c["dy"])), {}

        def net(item, n=c["n"], nets=nets):
            if item.GetNetCode() <= 0:
                return
            name = f"{item.GetNetname()}_{n}"
            if name not in nets:
                nets[name] = pcbnew.NETINFO_ITEM(b, name)
                b.Add(nets[name])
            item.SetNet(nets[name])
        for fp in fps:
            d = _copy(fp)
            b.Add(d)
            d.Move(shift)
            for pad in d.Pads():
                net(pad)
            old = fp.GetReference()
            d.SetReference(f"{old}_{c['n']}")
            keep_name(d, old)
        for src in tracks + zones + drawings:
            d = _copy(src)
            b.Add(d)
            d.Move(shift)
            if src in tracks or (src in zones and not src.GetIsRuleArea()):
                net(d)
    for fp in fps:
        old = fp.GetReference()
        fp.SetReference(f"{old}_1")
        keep_name(fp, old)
    hand = set(cfg["hand_fit"])
    for fp in b.GetFootprints():
        if fp.GetReference().rsplit("_", 1)[0] in hand:
            fp.Models().clear()                                          # fitted after the panel is broken apart
        else:                                                            # models kept inside the board's project
            local.update(str(m.m_Filename) for m in fp.Models() if str(m.m_Filename).startswith("${KIPRJMOD}"))
    # the outline: each copy's side pieces with the bridges' feet left open, then rails and bridges
    x0, y0, x1, y1 = info["box"]
    for c in p["copies"]:
        for side in SIDES:
            fixed = {"left": x0 + c["dx"], "right": x1 + c["dx"], "top": y0 + c["dy"], "bottom": y1 + c["dy"]}[side]
            shift = c["dy"] if side in ("left", "right") else c["dx"]
            cuts = sorted(p["feet"].get((c["n"], side), []))
            for lo, hi in info["sides"][side]:
                marks = [lo + shift] + [v for cut in cuts if lo + shift <= cut[0] and cut[1] <= hi + shift for v in cut] \
                    + [hi + shift]
                for a, e in zip(marks[0::2], marks[1::2]):
                    if e > a:
                        _segment(b, pcbnew, (fixed, a) if side in ("left", "right") else (a, fixed),
                                 (fixed, e) if side in ("left", "right") else (e, fixed), info["width"])
    boards = [(x0 + c["dx"], y0 + c["dy"], x1 + c["dx"], y1 + c["dy"]) for c in p["copies"]]
    for s in boundary(list(p["rails"].values()) + [br["box"] for br in p["bridges"]], boards):
        _segment(b, pcbnew, s[:2], s[2:], info["width"])
    for m in p["bites"]:
        _feature(b, pcbnew, m["ref"], "mouse bites", m["holes"], nm(cfg["hole_d_mm"]))
    for i, pt in enumerate(p["fiducials"]):
        _feature(b, pcbnew, f"{FID}{i + 1}", "fiducial", [pt], nm(cfg["fiducial_d_mm"]), nm(cfg["fiducial_mask_d_mm"]))
    for i, pt in enumerate(p["tooling"]):
        _feature(b, pcbnew, f"{TH}{i + 1}", "tooling hole", [pt], nm(cfg["tooling_d_mm"]), clear=p["tooling_mask_clear"])
    return notes


def bring_libraries(src_dir: str, dst_dir: str, models: set) -> list:
    """Make the panel a project of its own: the board project's footprint library table with the libraries it
    keeps inside the project folder, and the 3D models that footprints take from there, at the same places
    below the panel's folder. Without them the rule check warns about every footprint and renders show no
    bodies. Returns notes."""
    import shutil
    notes = []
    want = set(models)
    table = os.path.join(src_dir, "fp-lib-table")
    if os.path.isfile(table):
        with open(table, encoding="utf-8") as f:
            text = f.read()
        want |= set(re.findall(r'\(uri\s+"(\$\{KIPRJMOD\}[^"]*)"', text))
        kicad_io.atomic_write(os.path.join(dst_dir, "fp-lib-table"), text)
    for name in sorted(want):
        rel = os.path.normpath(name.replace("${KIPRJMOD}", ".", 1))
        src, dst = os.path.join(src_dir, rel), os.path.join(dst_dir, rel)
        if rel.startswith("..") or os.path.isabs(rel) or not os.path.exists(src):
            notes.append(f"{name}: not brought into the panel's folder (not inside the board's project folder, or missing)")
        elif os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
    return notes


def _patch_project(pro: str, final_name: str, copies: list, bite_min: float) -> dict:
    """The panel's project file: the board's own, with the net classes also for the copies' nets and the
    hole-to-hole minimum lowered to the mouse bites' distance. Returns what was set."""
    with open(pro, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("meta", {})["filename"] = final_name
    ns = d.setdefault("net_settings", {})
    pats = ns.get("netclass_patterns") or []
    ns["netclass_patterns"] = pats + [dict(q, pattern=f"{q['pattern']}_{c['n']}") for c in copies[1:] for q in pats
                                      if isinstance(q, dict) and q.get("pattern")]
    given = ns.get("netclass_assignments") or {}
    if given:
        ns["netclass_assignments"] = dict(given, **{f"{k}_{c['n']}": v for c in copies[1:] for k, v in given.items()})
    rules = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    was = rules.get("min_hole_to_hole")
    rules["min_hole_to_hole"] = min(float(was), bite_min) if was is not None else bite_min
    kicad_io.atomic_write(pro, json.dumps(d, indent=2) + "\n")
    return {"min_hole_to_hole_board_mm": was, "min_hole_to_hole_panel_mm": rules["min_hole_to_hole"]}


def markdown(res: dict) -> str:
    c = res["settings"]
    out = ["# Customer panel", "",
           f"**Result: {res['result']}** - board `{res['board']}` (SHA-256 `{res['board_sha256']}`), KiCad "
           f"{res['kicad_version']}, {res['date']}.", "",
           f"- Panel: {res['panel_mm'][0]:g} x {res['panel_mm'][1]:g} mm, {c['columns']} x {c['rows']} boards of "
           f"{res['board_mm'][0]:g} x {res['board_mm'][1]:g} mm, gap {c['gap_mm']:g} mm; rails: "
           f"{', '.join(res['rails']) or 'none'}" + (f" ({c['rail_mm']:g} mm)" if res["rails"] else ""),
           f"- Panel board: `{res['panel_board']}` (SHA-256 `{res['panel_sha256']}`), rule file `{res['rule_file']}`",
           f"- Bridges: {len(res['bridges'])}, {c['bridge_width_mm']:g} mm wide; mouse bites: {len(res['mouse_bites'])} rows of "
           f"{c['holes']} holes of {c['hole_d_mm']:g} mm at {c['hole_pitch_mm']:g} mm ({res['rules']['bite_edge_to_edge_mm']:g} mm "
           f"edge to edge), rows {c['hole_offset_mm']:g} mm outside the board edge",
           f"- Fiducials: {len(res['fiducials'])} ({c['fiducial_d_mm']:g} mm copper, {c['fiducial_mask_d_mm']:g} mm opening)",
           f"- {res['tooling_holes_note']}" + ("" if not res["tooling_holes"] else " At (mm) " + ", ".join(
               f"{x:g} / {y:g}" for x, y in res["tooling_holes"]) + (
               f"; solder-mask opening {res['tooling_mask_opening_mm']:g} mm on both sides."
               if res["tooling_mask_opening_mm"] else "; solder-mask opening: the board's own clearance.")),
           f"- Parts fitted by hand (no 3D model in the panel): {', '.join(c['hand_fit']) or 'none'}",
           "- Guided edges: " + res["free_bands"]["source"] + "".join(
               f"; {b['name']} ({', '.join(f'{s} edge {v[0]:g} .. {v[1]:g} mm' for s, v in b['stretch_mm'].items())})"
               for b in res["free_bands"]["bands"])]
    if res["guided_bridges"]:
        out += ["", f"**{res['guided_bridges']}**"]
    out += ["", "| Check | Measured | Limit | Result |", "|---|---|---|---|"]
    out += [f"| {r['check']} | {r['measured']} | {r['limit']} | {r['result']} |" for r in res["checks"]]
    out += ["", "## Bridges", "", "| Bridge | x0, y0, x1, y1 mm | Joins | Nearest fitted part | Distance mm | On a guided edge |",
            "|---|---|---|---|---|---|"]
    for br in res["bridges"]:
        joins = "; ".join(f"copy {f['copy']} {f['side']}" for f in br["feet"])
        dist = "no part" if br["part_distance_mm"] is None else f"{br['part_distance_mm']:.3f}"
        out.append(f"| {br['id']} | {', '.join(f'{v:g}' for v in br['box'])} | {joins} | {br['nearest_part'] or ''} | {dist} | "
                   f"{', '.join(br['guided_bands']) or 'no'} |")
    out += ["", "## Rules of the panel", "",
            f"- hole to hole: {res['rules']['hole_to_hole_mm']:g} mm for every pair of holes (the board's minimum), "
            f"{res['rules']['bite_min_mm']:g} mm inside a mouse-bite set; the panel project's own minimum is "
            f"{res['rules']['min_hole_to_hole_panel_mm']:g} mm",
            "- prove both rules once on a copy: two ordinary holes too close and two mouse-bite holes too close must "
            "each give an error (KiCad drops a whole rule file for one syntax error, without a word)"]
    if res["defaults_used"]:
        out += ["", "## Defaults used (common values: read the supplier's live pages)", ""]
        out += [f"- {d}" for d in res["defaults_used"]]
    if res["notes"]:
        out += ["", "## Notes", ""] + [f"- {n}" for n in res["notes"]]
    out += ["", "## Not checked", ""] + [f"- {n}" for n in res["not_checked"]]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Customer panel of a KiCad board: copies, rails, mouse-bite bridges, "
                                             "fiducials, tooling holes, the panel's BOM, placement file and rule "
                                             "file. Exit 0 built, 1 refused or a failed check, 2 could not run.")
    ap.add_argument("board", nargs="?", help="board file (.kicad_pcb); not needed with --project")
    ap.add_argument("--project", help="hardware/board folder (board.toml [panel]; results in <project>/out/panel/)")
    ap.add_argument("--out", help="results folder when no project folder is used")
    for key, default, text in KEYS:
        kind = int if isinstance(default, int) else float
        ap.add_argument(_option(key), dest=key, type=kind, metavar="N" if kind is int else "MM",
                        help=text + (f" (default {default})" if default is not None else ""))
    ap.add_argument("--rails", help="sides with a rail, for example left,right (default: none)")
    ap.add_argument("--bridge", action="append", metavar="SIDE=OFFSET[,OFFSET]",
                    help="bridges on one board side, offsets in mm from the middle of that edge; repeat per side")
    ap.add_argument("--hand-fit", action="append", metavar="REF[,REF]", help="parts fitted by hand after the panel is broken")
    ap.add_argument("--nubs-removed-flush", action="store_true",
                    help="allow bridges on guided edges (free bands); the result names them for the assembly note")
    ap.add_argument("--tooling-not-jlcpcb", action="store_true",
                    help="the panel does not go to JLCPCB: tooling holes of any --tooling-d, at both ends of every rail")
    ap.add_argument("--bom", help="the single board's BOM (CSV in the supplier's upload layout)")
    ap.add_argument("--cpl", help="the single board's placement file (CSV in the supplier's upload layout)")
    ap.add_argument("--name", help="base name of the panel's files (default: the board file's name)")
    ap.add_argument("--timeout", type=float, default=1800.0, help="seconds for the fill process (default 1800)")
    a = ap.parse_args(argv)
    toml: dict = {}
    if a.project:
        toml = kicad_io.load_settings(a.project)
        files = kicad_io.project_files(a.project, toml)
        board, out = a.board or files["pcb"], a.out or os.path.join(files["out"], "panel")
    else:
        if not a.board or not a.out:
            raise kicad_io.KicadIOError("give --project <board folder>, or a board file together with --out <folder>")
        board, out = a.board, a.out
    if not board or not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"board file not found: {board or '(none in the project folder)'}")
    board, out = os.path.abspath(board), os.path.abspath(out)
    design = os.path.normcase(os.path.dirname(board))
    if (os.path.normcase(out) + os.sep).startswith(design + os.sep):
        raise kicad_io.KicadIOError("the results folder lies inside the folder of the input design; a design is "
                                    "never written into: choose another folder with --out")
    cfg, defaults = read_settings(a, toml)
    stem = os.path.basename(board)[:-len(".kicad_pcb")] if board.lower().endswith(".kicad_pcb") else \
        os.path.splitext(os.path.basename(board))[0]
    name = a.name or stem
    fab_name = (toml.get("fab", {}) or {}).get("name", stem)
    t = toml.get("panel", {}) if isinstance(toml.get("panel"), dict) else {}
    src = {k: getattr(a, k) or (os.path.join(a.project, t[k]) if a.project and t.get(k) else None) or
           (os.path.join(files["out"], "jlc", f"{fab_name}-{k}.csv") if a.project else None) for k in ("bom", "cpl")}

    kicad_io.need_kicad_python()                                        # from here on: KiCad's own Python
    from layout import fill, quiet_wx
    quiet_wx()                                                          # no message box, ever
    import pcbnew
    kc = kicad_io.require_kicad()
    panel_dir = os.path.join(out, "board")
    panel = os.path.join(panel_dir, f"{name}-panel.kicad_pcb")
    with kicad_io.private_tmp("panel-") as tmp:
        copy = os.path.join(tmp, os.path.basename(board))
        kicad_io.copy_board(board, copy, lock_source=False)
        b = kicad_io.load_board(copy)
        info = read_board(b, pcbnew, cfg)
        info["bands"], band_source = read_bands(a.project, toml, info["box"])
        p = plan(cfg, info)                                             # Refused: nothing has been written
        local: set = set()
        notes = p["notes"] + build(b, pcbnew, cfg, info, p, local)
        bite_e2e = cfg["hole_pitch_mm"] - cfg["hole_d_mm"]
        bite_min = round(bite_e2e - 0.05, 4)
        board_min = mm(info["hole_to_hole"])
        own_dru = copy[:-len(".kicad_pcb")] + ".kicad_dru"
        own = ""
        if os.path.isfile(own_dru):
            with open(own_dru, encoding="utf-8") as f:
                own = f.read()
        os.makedirs(panel_dir, exist_ok=True)
        for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru", ".kicad_prl"):   # an older panel of the same name
            if os.path.exists(panel[:-len(".kicad_pcb")] + ext):
                os.remove(panel[:-len(".kicad_pcb")] + ext)
        notes += bring_libraries(os.path.dirname(board), panel_dir, local)
        kicad_io.atomic_write(panel[:-len(".kicad_pcb")] + ".kicad_dru", rule_text(own, board_min, bite_min))
        set_ = {}

        def patch(pro: str) -> None:
            set_.update(_patch_project(pro, os.path.basename(panel)[:-len(".kicad_pcb")] + ".kicad_pro", p["copies"], bite_min))
        kicad_io.save_board(b, panel, patch=patch)
        if not set_:                                                    # KiCad 10 writes no project file for a board
            kicad_io.save_board(kicad_io.load_board(panel), panel, patch=patch)     # that came without one
    filled = fill.fill(panel, a.timeout)                                # its own process; the saved fill is checked
    checks = [{"check": "smallest distance of a bridge to a fitted part",
               "measured": "no part" if not info["parts"] else
               f"{min(mm(br['nearest'][0]) for br in p['bridges']):.3f} mm", "limit": f"{cfg['part_clear_mm']:g} mm or more",
               "result": "PASS"},
              {"check": "saved zone fill of the panel (layout/fill.py)", "measured": f"{len(filled['zones'])} zone layer(s), "
               + ("no difference to a fresh fill" if filled["result"] == "PASS" else "; ".join(
                   w for z in filled["zones"] for w in z["why"])[:300]),
               "limit": f"equal to a fresh fill; {filled['edge_limit_mm']:g} mm to the edge", "result": filled["result"]}]
    if a.project:                                                       # with a board file alone the bands are not known
        on_band = [br["id"] for br in p["bridges"] if br["guided"]]
        checks.insert(1, {"check": "bridges on guided edges (rule DFM-31)",
                          "measured": f"{len(on_band)} of {len(p['bridges'])} bridges on a free band; {band_source}"
                          + ("; nubs_removed_flush is set" if on_band else ""),
                          "limit": "none, or nubs_removed_flush set and the nubs removed flush", "result": "PASS"})
    else:
        notes.append(band_source + " (with --project the bands of board.toml or mech/outline.json are read and a "
                     "bridge on a guided edge is refused)")
    # the tables of the panel
    written = {"bom": None, "cpl": None}
    if src["bom"] and src["cpl"] and os.path.isfile(src["bom"]) and os.path.isfile(src["cpl"]):
        bom_text, cpl_text, why = tables(src["bom"], src["cpl"], p["copies"], info["refs"])
        if why:
            checks.append({"check": "BOM and placement file of the panel", "measured": "; ".join(why)[:400],
                           "limit": "every designator is a part of the board", "result": "FAIL"})
        else:
            for k, text in (("bom", bom_text), ("cpl", cpl_text)):
                written[k] = os.path.join(out, f"{name}-panel-{k}.csv")
                kicad_io.atomic_write(written[k], text)
            checks.append({"check": "BOM and placement file of the panel", "measured": f"{len(cpl_text.splitlines()) - 1} "
                           f"placements from {os.path.basename(src['cpl'])}, moved by each copy's offset",
                           "limit": "every designator is a part of the board", "result": "PASS"})
    else:
        notes.append("BOM and placement file of the panel: NOT WRITTEN (the single board's files were not found: "
                     + ", ".join(os.path.basename(v) for v in src.values() if v) + "; give --bom and --cpl)"
                     if any(src.values()) else
                     "BOM and placement file of the panel: NOT WRITTEN (give --bom and --cpl, the single board's files)")
    px0, py0, px1, py1 = p["box"]
    res = {"check": "panel", "result": "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL",
           "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "kicad_version": kc.version,
           "board": os.path.basename(board), "board_sha256": kicad_io.sha256(board),
           "panel_board": f"board/{os.path.basename(panel)}", "panel_sha256": kicad_io.sha256(panel),
           "rule_file": f"board/{os.path.basename(panel)[:-len('.kicad_pcb')]}.kicad_dru",
           "frame": "KiCad's own: mm, x to the right, y downwards (a placement file's Mid Y is -y)",
           "settings": cfg, "defaults_used": defaults,
           "board_box": [mm(v) for v in info["box"]], "board_mm": [mm(info["box"][2] - info["box"][0]), mm(info["box"][3] - info["box"][1])],
           "panel_box": [mm(v) for v in p["box"]], "panel_mm": [mm(px1 - px0), mm(py1 - py0)],
           "copies": [{"n": c["n"], "column": c["column"], "row": c["row"], "dx_mm": mm(c["dx"]), "dy_mm": mm(c["dy"])}
                      for c in p["copies"]],
           "rails": {s: [mm(v) for v in r] for s, r in p["rails"].items()},
           "bridges": [{"id": br["id"], "box": [mm(v) for v in br["box"]],
                        "feet": [{"copy": f["copy"], "side": f["side"], "span_mm": [mm(v) for v in f["span"]]} for f in br["feet"]],
                        "nearest_part": br["nearest"][1],
                        "part_distance_mm": None if br["nearest"][0] is None else round(mm(br["nearest"][0]), 4),
                        "guided_bands": br["guided"]}
                       for br in p["bridges"]],
           "free_bands": {"source": band_source,
                          "bands": [{"name": bd["name"], "width_mm": bd["width_mm"],
                                     "stretch_mm": {s: [mm(v) for v in st] for s, st in bd["stretch"].items()}}
                                    for bd in info["bands"]]},
           "guided_bridges": p["guided_line"] or None,
           "mouse_bites": [{"ref": m["ref"], "copy": m["copy"], "side": m["side"], "holes_mm": [[mm(x), mm(y)] for x, y in m["holes"]]}
                           for m in p["bites"]],
           "fiducials": [[mm(x), mm(y)] for x, y in p["fiducials"]], "tooling_holes": [[mm(x), mm(y)] for x, y in p["tooling"]],
           "tooling_holes_note": p["tooling_line"],
           "tooling_mask_opening_mm": None if p["tooling_mask_clear"] is None else
           round(cfg["tooling_d_mm"] + 2 * cfg["tooling_mask_clear_mm"], 4),
           "rules": dict(set_, hole_to_hole_mm=board_min, bite_min_mm=bite_min, bite_edge_to_edge_mm=round(bite_e2e, 4)),
           "fill": {k: filled[k] for k in ("result", "edge_limit_mm", "zones")}, "checks": checks,
           "bom": os.path.basename(written["bom"]) if written["bom"] else None,
           "cpl": os.path.basename(written["cpl"]) if written["cpl"] else None, "notes": notes,
           "not_checked": (["KiCad " + kc.version + ": " + kc.note] if kc.note else []) + (
               [] if a.project else ["bridges on guided edges (rule DFM-31): " + band_source]) + [
               "the rule check of the panel: drc_run.py <panel board> --out <results> --no-parity (with the rule file written here)",
               "copper to the panel's edges on the exported Gerbers: fab_package.py --project <board folder> --out "
               "<results> --name <name>-panel --bom <panel bom> <panel board> writes them to <results>/jlc/gerbers, "
               "then edge_check.py --project <board folder>",
               "the placement file against the supplier's own footprints (jlc_rotations.py --project <board folder> "
               "--out <results> --bom <panel bom> test <panel board> --cpl <panel cpl>; --project gives the footprint "
               "folder)",
               "the supplier's rules for panels of the day (sizes, rails, fiducials, slot width): an independent reader "
               "checks the panel against the live pages",
               "custom rules that name nets apply to copy 1 only: the board's own checks run on the single board"]}
    kicad_io.atomic_write(os.path.join(out, "panel.json"), json.dumps(res, indent=1) + "\n")
    kicad_io.atomic_write(os.path.join(out, "panel.md"), markdown(res))
    for c in checks:
        print(f"{c['result']:5} {c['check']}: {c['measured']} (limit: {c['limit']})")
    for n in notes:
        print("note:", n)
    print(p["tooling_line"])
    print(f"panel: {res['result']} - {res['panel_mm'][0]:g} x {res['panel_mm'][1]:g} mm, {len(p['copies'])} boards, "
          f"{len(p['bridges'])} bridges, {len(p['fiducials'])} fiducials, {len(p['tooling'])} tooling holes; {panel}; "
          f"{os.path.join(out, 'panel.md')}")
    return 0 if res["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
