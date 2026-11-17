"""Return path of every fast or sensitive net, measured on the SAVED zone fill, with an overlay image per plane.

What it checks (rule GEN-19 of references/pcb-rules/general.md; GEN-62 uses it for nets that cross a cut)
    For every net listed in board.toml [fast_nets] (clocks, pairs, fast bus lines, RF lines, feedback and
    sense lines):
    coverage      every track and arc of the net is walked in steps of sample_mm (0.1 mm). At each step the
                  whole width of the track is tested, a point every 0.1 mm or less across it, against the copper
                  of the reference nets on the track's reference layer (zone fill, and the pads, tracks and via
                  rings of those nets). A stretch where any of these points has no reference copper below is
                  an uncovered run: its length, its two ends, how much of the track's width is bare, and what
                  lies below instead (no copper, or copper of which net). FAIL: a run longer than max_gap_mm.
                  The part of a run within pad_exempt_mm of the net's own pads and vias is listed, not counted:
                  there the plane is opened for the net's own pin or via barrel.
    edge          the smallest distance from the track's edge to the edge of its reference copper (a plane
                  edge, a slot, a clearance hole), with its place and with three track widths beside it
                  (GEN-08). Reported, not judged.
    layer change  every via where the net goes on to a layer whose reference layer is another one: the
                  distance to the nearest via, or plated through-hole pad, of a reference net that reaches
                  both reference layers. FAIL: farther than via_return_mm, or none.
    images        (the visual layer; made on every run) for every reference layer one picture: the reference
                  copper grey, its gaps white, copper of other nets on that layer pale orange, the listed
                  nets on top in colour with their names, every uncovered run red with a number, the part
                  near own pads orange, every layer-change via with a ring: green when a return via is near,
                  magenta when not. Plus one zoom tile per uncovered run and per failing via.
    A board with no [fast_nets] table (no list at all) ends "No fast or sensitive net declared" with exit code 0
    and says so in its first line, so that the layout ledger can record it.
    A listed name or pattern that matches no net of the board is a finding, exit code 1 ("listed net <entry> is
    not on the board: a name that matches nothing checks nothing"), also when it is one of several and also when
    nothing matches: a typing error must not drop a net from the check silently.

Why it exists (the real failure, told without names)
    A dense board came back from an experienced reviewer: fully routed, rule-clean, tidy, and the ground plane
    was cut under the returns of exactly the signals that needed it, by rows of via clearances, by a fan-out
    and by a neighbouring pour. The rule check sees none of this: every net is connected and every clearance
    is kept. A plane that looks solid at arm's length is proven only net by net.

How it works
    The board is read from a private copy; the saved fill is judged as it is (never refilled: fill and save
    with layout/fill.py first). KiCad's Python reads the items and merges copper; every measurement is plain
    arithmetic on the polygons, so KiCad 9 and KiCad 10 give the same numbers. Coordinates are KiCad's (mm, x to
    the right, y down); all pictures are seen from the top side, also those of the bottom layer.

Usage
    python -I return_path_check.py --project <hardware/board folder>      results in <project>/out/
    python -I return_path_check.py <board.kicad_pcb> --out <folder> --net "/USB_D*" --net CLK [--reference GND]
    options: --net PATTERN (repeatable; replaces [fast_nets] nets), --reference NET (repeatable),
             --max-gap MM, --pad-exempt MM, --via-return MM, --sample MM
    In Git Bash a net name that starts with "/" is rewritten by the shell: set MSYS_NO_PATHCONV=1 or use PowerShell.
    Results: return_path.md, return_path.json, and the pictures in review/return_path/: <layer>.png for every
    reference layer, run<n>_<net>_<layer>.png per uncovered run, via<n>_<net>.png per failing layer change.
    (A sub-folder of review/, because review_images.py clears the PNG files that lie directly in review/.)

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [fast_nets]
    nets = ["/USB_D+", "/USB_D-", "*CLK*", "/RF_*"]   # names, names without their sheet path, or patterns
    reference = ["GND"]            # nets whose copper counts as reference (default: the net with the largest
                                   # filled area on the board, printed)
    max_gap_mm = 0.2               # an uncovered run longer than this fails
    pad_exempt_mm = 1.0            # not counted within this distance of the copper of the net's own pads and vias
    via_return_mm = 2.0            # a return via must be within this distance of a layer-change via
    sample_mm = 0.1                # step along the track
    edge_reach_mm = 5.0            # the distance to the edge of the reference copper is measured up to this
    [fast_nets.reference_layer]    # signal layer = its reference layer (default: the nearest copper layer by
    "F.Cu" = "In1.Cu"              # the layer stack; on two layers the other side; printed)
    [stackup]                      # only for a board file without a layer stack: see impedance_check.py

Exit codes
    0  PASS: no uncovered run longer than max_gap_mm and a return via at every layer change; or no fast or
       sensitive net declared (no list at all)
    1  FAIL: an uncovered run, a layer change without a return via, or a listed net that is not on the board
    2  CANNOT RUN: KiCad's Python or Pillow not found, unreadable board, a layer or setting of board.toml that
       does not fit the board. Never a pass.

Not checked: whether the saved fill is up to date (layout/fill.py --check); whether the list of nets is
complete (the reviewer makes an own list from the schematic); the second plane of an inner layer that lies
between two planes; a return path through parts in series (each net is measured alone); distance and parallel
run to an aggressor (GEN-09); the length of stubs (GEN-42); supply currents (neck_check.py). A plane of a
supply net counts as reference only when it is named in `reference`. And the looking: open every picture.
"""

from __future__ import annotations

import bisect
import fnmatch
import math
import os
import re
import sys

sys.dont_write_bytecode = True      # `python -I` ignores PYTHONDONTWRITEBYTECODE: leave no __pycache__ beside the scripts
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
import sexp  # noqa: E402

DEFAULTS = {"max_gap_mm": 0.2, "pad_exempt_mm": 1.0, "via_return_mm": 2.0, "sample_mm": 0.1, "edge_reach_mm": 5.0}
ACROSS = 0.1                        # mm between the points tested across a track's width
MIN_RUN = 0.01                      # mm: a shorter uncovered stretch is below what the sampling resolves and is not listed
MAX_ROWS = 200                      # uncovered runs listed in the Markdown table (the JSON holds all)
MAX_TILES = 80                      # zoom tiles drawn
MAX_PLOT_MP = 16.0                  # largest overview picture in megapixels (the zoom tiles carry the detail)
SS = 2                              # supersampling of the drawings

C_OUT, C_BOARD, C_PLANE, C_OTHER = (226, 232, 240), (255, 255, 255), (168, 168, 168), (248, 214, 160)
C_EDGE, C_RETURN, C_RUN, C_EXEMPT = (40, 40, 40), (84, 84, 84), (228, 0, 0), (255, 150, 0)
C_OK, C_BAD = (0, 165, 70), (225, 0, 190)
PALETTE = [(25, 85, 205), (0, 135, 150), (125, 55, 190), (150, 95, 20), (20, 60, 115), (90, 118, 0), (175, 60, 135), (70, 70, 70)]


# ---- the layer stack ---------------------------------------------------------------------------------------------------
class Stack:
    """The layer stack from top to bottom. items: dicts {"kind": "copper" | "dielectric" | "mask", "name",
    "t" (thickness in mm, None when not given), "er" (relative permittivity, None when not given)}.
    source: where it was read ("the board file" or "board.toml [stackup]")."""

    def __init__(self, items: list[dict], source: str):
        self.items, self.source = items, source
        self.copper = [it["name"] for it in items if it["kind"] == "copper"]

    def _pos(self, name: str) -> int:
        for i, it in enumerate(self.items):
            if it["kind"] == "copper" and it["name"] == name:
                return i
        raise kicad_io.KicadIOError(f"the layer stack ({self.source}) has no copper layer '{name}': it has {', '.join(self.copper)}")

    def copper_t(self, name: str):
        return self.items[self._pos(name)]["t"]

    def between(self, a: str, b: str) -> dict:
        """What lies between two copper layers: {"h": total distance in mm (dielectrics and any copper layers
        in between), "er": the relative permittivity of the dielectrics as capacitors in series, "parts":
        [(thickness, er), ...], "missing": what the stack does not give}."""
        i, j = sorted((self._pos(a), self._pos(b)))
        h, parts, missing, skipped = 0.0, [], [], []
        for it in self.items[i + 1:j]:
            if it["t"] is None or it["t"] <= 0:
                missing.append(f"thickness of {it['name']}")
                continue
            h += it["t"]
            if it["kind"] == "dielectric":
                if it["er"] is None or it["er"] < 1:
                    missing.append(f"epsilon_r of {it['name']}")
                else:
                    parts.append((it["t"], it["er"]))
            elif it["kind"] == "copper":
                skipped.append(it["name"])
        td = sum(t for t, _ in parts)
        er = td / sum(t / e for t, e in parts) if parts else None
        return {"h": h, "er": er, "parts": parts, "missing": missing, "skipped": skipped}

    def mask(self, top: bool):
        """(thickness, er) of the solder mask over the top or bottom copper, or None when the stack has none."""
        its = [it for it in self.items if it["kind"] == "mask"]
        if not its:
            return None
        cu = [i for i, it in enumerate(self.items) if it["kind"] == "copper"]
        for i, it in enumerate(self.items):
            if it["kind"] == "mask" and ((top and i < cu[0]) or (not top and i > cu[-1])):
                return (it["t"], it["er"])
        return None

    def rows(self) -> list[str]:
        out = ["| Layer | Kind | Thickness (mm) | Relative permittivity |", "|---|---|---|---|"]
        for it in self.items:
            out.append(f"| {it['name']} | {it['kind']} | {'not given' if it['t'] is None else format(it['t'], 'g')} | "
                       f"{'' if it['kind'] == 'copper' else ('not given' if it['er'] is None else format(it['er'], 'g'))} |")
        return out

    def to_list(self) -> list[dict]:
        return [dict(it) for it in self.items]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def stack_from_board(path: str):
    """The layer stack written in a board file (setup, stackup), or None when the file has none."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    i = text.find("(stackup")
    if i < 0:
        return None
    depth, j, in_str, end = 0, i, False, -1
    while j < len(text):
        c = text[j]
        if in_str:
            if c == "\\":
                j += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                end = j
                break
        j += 1
    if end < 0:
        return None
    try:
        tree = sexp.parse(text[i:end + 1])
    except sexp.SexpError:
        return None
    items, n_d = [], 0
    for lay in sexp.find(tree, "layer"):
        name = str(lay[1]) if len(lay) > 1 else "?"
        typ = str(sexp.value(lay, "type", "")).lower()
        subs, cur = [], {}
        for x in lay[2:]:                                               # a dielectric may have several sub-layers
            if x == "addsublayer":
                subs.append(cur)
                cur = {}
            elif isinstance(x, list) and x and x[0] in ("thickness", "epsilon_r") and len(x) > 1:
                cur[x[0]] = _num(x[1])
        subs.append(cur)
        if typ == "copper":
            items.append({"kind": "copper", "name": name, "t": subs[0].get("thickness"), "er": None})
        elif "mask" in typ:
            items.append({"kind": "mask", "name": name, "t": subs[0].get("thickness"), "er": subs[0].get("epsilon_r")})
        elif typ in ("core", "prepreg") or name.lower().startswith("dielectric"):
            n_d += 1
            for k, s in enumerate(subs):
                items.append({"kind": "dielectric", "name": name + (f" ({k + 1})" if len(subs) > 1 else ""),
                              "t": s.get("thickness"), "er": s.get("epsilon_r")})
    if not any(it["kind"] == "copper" for it in items):
        return None
    return Stack(items, "the board file")


def stack_from_settings(cfg: dict, copper_names: list[str]) -> Stack:
    """The layer stack from board.toml [stackup] (for a board file without one):
        copper = [0.035, 0.035]        mm, every copper layer from top to bottom
        dielectric = [1.53]            mm, between each two neighbouring copper layers
        epsilon_r = [4.45]             relative permittivity of each dielectric
        mask = 0.02                    optional: solder mask over the outer copper, mm
        mask_epsilon_r = 3.5           optional"""
    def nums(key, n):
        v = cfg.get(key)
        if not isinstance(v, list) or len(v) != n or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in v):
            raise kicad_io.KicadIOError(f"board.toml [stackup]: '{key}' must be a list of {n} positive number(s) "
                                        f"(the board has {len(copper_names)} copper layers: {', '.join(copper_names)})")
        return [float(x) for x in v]
    n = len(copper_names)
    cu, di, er = nums("copper", n), nums("dielectric", n - 1), nums("epsilon_r", n - 1)
    if any(e < 1 for e in er):
        raise kicad_io.KicadIOError("board.toml [stackup]: epsilon_r cannot be below 1")
    mask = cfg.get("mask")
    mer = cfg.get("mask_epsilon_r")
    items = []
    if isinstance(mask, (int, float)) and mask > 0:
        items.append({"kind": "mask", "name": "top solder mask", "t": float(mask), "er": float(mer) if isinstance(mer, (int, float)) else None})
    for k, name in enumerate(copper_names):
        items.append({"kind": "copper", "name": name, "t": cu[k], "er": None})
        if k < n - 1:
            items.append({"kind": "dielectric", "name": f"dielectric {k + 1}", "t": di[k], "er": er[k]})
    if isinstance(mask, (int, float)) and mask > 0:
        items.append({"kind": "mask", "name": "bottom solder mask", "t": float(mask), "er": float(mer) if isinstance(mer, (int, float)) else None})
    return Stack(items, "board.toml [stackup]")


def read_stack(board_path: str, settings: dict, copper_names: list[str]):
    """(Stack or None, note). The board file's own stack first; board.toml [stackup] only when the file has none.
    The file's stack names its copper layers F.Cu, In1.Cu, ...: they are given the board's own layer names, in
    order. A stack with another number of copper layers than the board is refused (KicadIOError)."""
    st = stack_from_board(board_path)
    cfg = settings.get("stackup")
    if st is not None:
        if len(st.copper) != len(copper_names):
            raise kicad_io.KicadIOError(f"the layer stack of the board file has the copper layers {', '.join(st.copper)}, "
                                        f"the board has {', '.join(copper_names)}")
        names = iter(copper_names)
        for it in st.items:
            if it["kind"] == "copper":
                it["name"] = next(names)
        st.copper = list(copper_names)
        return st, ("board.toml also has a [stackup] table: not used, the board file has its own layer stack"
                    if isinstance(cfg, dict) and cfg else "")
    if isinstance(cfg, dict) and cfg:
        return stack_from_settings(cfg, copper_names), ""
    return None, "the board file has no layer stack and board.toml has no [stackup] table"


# ---- small geometry ----------------------------------------------------------------------------------------------------
def arc_points(sx, sy, mx, my, ex, ey) -> list:
    """An arc given by start, middle and end as a chain of points (chord error under 1 micrometre)."""
    d = 2 * (sx * (my - ey) + mx * (ey - sy) + ex * (sy - my))
    if abs(d) < 1e-12:
        return [(sx, sy), (ex, ey)]
    s2, m2, e2 = sx * sx + sy * sy, mx * mx + my * my, ex * ex + ey * ey
    cx = (s2 * (my - ey) + m2 * (ey - sy) + e2 * (sy - my)) / d
    cy = (s2 * (ex - mx) + m2 * (sx - ex) + e2 * (mx - sx)) / d
    r = math.hypot(sx - cx, sy - cy)
    a0 = math.atan2(sy - cy, sx - cx)
    full = (math.atan2(ey - cy, ex - cx) - a0) % (2 * math.pi)
    mid = (math.atan2(my - cy, mx - cx) - a0) % (2 * math.pi)
    sweep = full if mid <= full else full - 2 * math.pi
    n = max(2, min(1440, int(math.ceil(abs(sweep) / math.sqrt(0.008 / max(r, 1e-6))))))
    pts = [(cx + r * math.cos(a0 + sweep * k / n), cy + r * math.sin(a0 + sweep * k / n)) for k in range(n + 1)]
    pts[0], pts[-1] = (sx, sy), (ex, ey)
    return pts


class Path:
    """A chain of points with its length; at(s) gives the point and the direction at distance s from the start."""

    def __init__(self, pts: list):
        self.pts = pts
        self.cum = [0.0]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(x1 - x0, y1 - y0))
        self.length = self.cum[-1]

    def at(self, s: float):
        s = min(max(s, 0.0), self.length)
        i = min(max(bisect.bisect_right(self.cum, s) - 1, 0), len(self.pts) - 2)
        seg = self.cum[i + 1] - self.cum[i]
        (x0, y0), (x1, y1) = self.pts[i], self.pts[i + 1]
        if seg <= 0:
            return x0, y0, 1.0, 0.0
        f = (s - self.cum[i]) / seg
        return x0 + f * (x1 - x0), y0 + f * (y1 - y0), (x1 - x0) / seg, (y1 - y0) / seg

    def piece(self, s0: float, s1: float) -> list:
        """The points of the chain between two distances."""
        a, b = self.at(s0), self.at(s1)
        mid = [p for p, c in zip(self.pts, self.cum) if s0 < c < s1]
        return [(a[0], a[1])] + mid + [(b[0], b[1])]

    def dist(self, x: float, y: float) -> float:
        return min(pcb_common.pt_seg(x, y, x0, y0, x1, y1) for (x0, y0), (x1, y1) in zip(self.pts, self.pts[1:]))


def _near_seg(px, py, ax, ay, bx, by):
    """(squared distance, nearest point) from a point to a segment."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    qx, qy = ax + t * dx, ay + t * dy
    return (px - qx) ** 2 + (py - qy) ** 2, qx, qy


class PolyIndex:
    """Copper of one layer as polygons with holes ([[outer, hole, ...], ...], points in mm, the polygons not
    overlapping): is a point on the copper, and how far is the nearest edge of the copper."""
    ROW, CELL = 0.25, 0.5

    def __init__(self, polys: list):
        self.rows: dict[int, list] = {}
        self.cells: dict[tuple, list] = {}
        self.edges = 0
        xs, ys = [], []
        for poly in polys:
            for loop in poly:
                n = len(loop)
                if n < 3:
                    continue
                for k in range(n):
                    (x1, y1), (x2, y2) = loop[k], loop[(k + 1) % n]
                    if x1 == x2 and y1 == y2:
                        continue
                    e = (x1, y1, x2, y2)
                    self.edges += 1
                    xs += (x1, x2)
                    ys += (y1, y2)
                    if y1 != y2:
                        for r in range(int(math.floor(min(y1, y2) / self.ROW)), int(math.floor(max(y1, y2) / self.ROW)) + 1):
                            self.rows.setdefault(r, []).append(e)
                    ln = math.hypot(x2 - x1, y2 - y1)
                    if ln <= self.CELL:                                 # a short edge: the cells of its box
                        cells = {(cx, cy) for cx in range(int(math.floor(min(x1, x2) / self.CELL)), int(math.floor(max(x1, x2) / self.CELL)) + 1)
                                 for cy in range(int(math.floor(min(y1, y2) / self.CELL)), int(math.floor(max(y1, y2) / self.CELL)) + 1)}
                    else:                                               # a long edge: the cells along it, and their neighbours
                        cells, m = set(), int(math.ceil(ln / (self.CELL / 2)))
                        for q in range(m + 1):
                            cx = int(math.floor((x1 + (x2 - x1) * q / m) / self.CELL))
                            cy = int(math.floor((y1 + (y2 - y1) * q / m) / self.CELL))
                            cells.update((cx + a, cy + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
                    for c in cells:
                        self.cells.setdefault(c, []).append(e)
        self.box = (min(xs), min(ys), max(xs), max(ys)) if xs else None

    def contains(self, x: float, y: float) -> bool:
        inside = False
        for x1, y1, x2, y2 in self.rows.get(int(math.floor(y / self.ROW)), ()):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside

    def nearest(self, x: float, y: float, reach: float, side=None):
        """(distance, x, y) of the nearest point of any copper edge within `reach`, or None. side: (ux, uy, sign)
        keeps only points on one side of the line through (x, y) with direction (ux, uy): sign +1 left of it
        in KiCad's frame turned by +90 degrees (-uy, ux), -1 the other side."""
        cx, cy = int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))
        best, bx, by = float("inf"), 0.0, 0.0
        rmax = int(math.ceil(reach / self.CELL)) + 1
        for r in range(rmax + 1):
            if r == 0:
                ring = [(cx, cy)]
            else:
                ring = [(cx + a, cy + b) for a in range(-r, r + 1) for b in (-r, r)] + \
                       [(cx + a, cy + b) for a in (-r, r) for b in range(-r + 1, r)]
            for c in ring:
                for x1, y1, x2, y2 in self.cells.get(c, ()):
                    d2, qx, qy = _near_seg(x, y, x1, y1, x2, y2)
                    if d2 < best:
                        if side is not None and ((qx - x) * -side[1] + (qy - y) * side[0]) * side[2] <= 0:
                            continue
                        best, bx, by = d2, qx, qy
            if best <= (r * self.CELL) ** 2:
                break
        d = math.sqrt(best) if best < float("inf") else None
        return (d, bx, by) if d is not None and d <= reach else None


def poly_has(loops: list, x: float, y: float) -> bool:
    """Is the point inside a polygon given as [outer, hole, ...]?"""
    return pcb_common.inside(x, y, loops[0]) and not any(pcb_common.inside(x, y, h) for h in loops[1:])


def poly_dist(loops: list, x: float, y: float) -> float:
    """Distance from a point to a polygon's copper (0 inside)."""
    if poly_has(loops, x, y):
        return 0.0
    best = float("inf")
    for loop in loops:
        n = len(loop)
        for k in range(n):
            best = min(best, pcb_common.pt_seg(x, y, loop[k][0], loop[k][1], loop[(k + 1) % n][0], loop[(k + 1) % n][1]))
    return best


def match_nets(patterns: list, names: list) -> tuple[list, list]:
    """The net names that a list of names or patterns selects: the full name, the name without its sheet path,
    or a pattern (*, ?) of either. Returns (the selected names in the board's order, the patterns that match
    no net)."""
    hit, dead = set(), []
    for pat in patterns:
        got = [n for n in names if n and (n == pat or kicad_io.leaf(n) == pat or fnmatch.fnmatchcase(n, pat)
                                          or fnmatch.fnmatchcase(kicad_io.leaf(n), pat))]
        if not got:
            dead.append(pat)
        hit.update(got)
    return [n for n in names if n in hit], dead


def short(net: str) -> str:
    """A net's name for a picture or a table cell: without its sheet path."""
    return kicad_io.leaf(net) or net or "(no net)"


# ---- the board as plain data (KiCad's Python reads; everything after is arithmetic) --------------------------------------
class Picture:
    """What the two line checks need of a loaded board: tracks (arcs as chains of points), vias, pads, the
    filled area of every net, and merged copper as polygons. Lengths in mm, KiCad's frame."""

    def __init__(self, board):
        import pcbnew
        self.p, self.b = pcbnew, board
        mm = pcbnew.ToMM
        self.cu = list(board.GetEnabledLayers().CuStack())
        self.name = {lid: str(board.GetLayerName(lid)) for lid in self.cu}
        self.layers = [self.name[lid] for lid in self.cu]
        self.lid = {n: lid for lid, n in self.name.items()}
        self.alias = {str(pcbnew.LayerName(lid)): self.name[lid] for lid in self.cu}      # F.Cu -> the board's own name for it
        self.tracks, self.vias, self.pads = [], [], []
        self._track_obj, self._via_obj = [], []
        for t in board.GetTracks():
            cls = t.GetClass()
            net = str(t.GetNetname())
            if cls == "PCB_VIA":
                q = t.GetPosition()
                on = [self.name[lid] for lid in self.cu if t.IsOnLayer(lid)]
                self.vias.append({"x": mm(q.x), "y": mm(q.y), "net": net, "d": mm(t.GetWidth(pcbnew.F_Cu)),
                                  "drill": mm(t.GetDrill()), "layers": on})
                self._via_obj.append(t)
                continue
            lid = t.GetLayer()
            if lid not in self.name:
                continue
            s, e = t.GetStart(), t.GetEnd()
            if cls == "PCB_ARC":
                m = t.GetMid()
                pts = arc_points(mm(s.x), mm(s.y), mm(m.x), mm(m.y), mm(e.x), mm(e.y))
            else:
                pts = [(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]
            path = Path(pts)
            if path.length < 1e-6:
                continue
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            self.tracks.append({"net": net, "layer": self.name[lid], "w": mm(t.GetWidth()), "path": path, "arc": cls == "PCB_ARC",
                                "box": (min(xs), min(ys), max(xs), max(ys))})
            self._track_obj.append(t)
        for f in board.GetFootprints():
            for pad in f.Pads():
                q = pad.GetPosition()
                on = [self.name[lid] for lid in self.cu if pad.IsOnLayer(lid)]
                if not on:
                    continue
                self.pads.append({"ref": str(f.GetReference()), "num": str(pad.GetNumber()), "net": str(pad.GetNetname()),
                                  "x": mm(q.x), "y": mm(q.y), "layers": on, "hole": bool(pad.HasHole()),
                                  "plated": pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH, "box": pcb_common.bbox_of(pad), "obj": pad,
                                  "poly": {}})
        self.zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
        self.fill_area: dict[str, float] = {}
        self.zone_layers: dict[str, set] = {}       # layer name -> nets with a zone on it
        self.unfilled = 0
        for z in self.zones:
            net = str(z.GetNetname())
            if not z.IsFilled():
                self.unfilled += 1
            for lid in self.cu:
                if z.IsOnLayer(lid):
                    self.fill_area[net] = self.fill_area.get(net, 0.0) + z.GetFilledPolysList(lid).Area() / 1e12
                    self.zone_layers.setdefault(self.name[lid], set()).add(net)
        self.nets = sorted(({t["net"] for t in self.tracks} | {v["net"] for v in self.vias} | {p["net"] for p in self.pads}
                            | set(self.fill_area)) - {""}, key=pcb_common.natural)
        ps, note = pcb_common.board_outline(board)
        self.outline = pcb_common.poly_points(ps) if ps is not None else []
        self.outline_note = note
        bb = board.GetBoardEdgesBoundingBox()
        self.box = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
        if self.box[2] - self.box[0] <= 0 or self.box[3] - self.box[1] <= 0:
            fb = board.ComputeBoundingBox(False)
            self.box = (mm(fb.GetX()), mm(fb.GetY()), mm(fb.GetRight()), mm(fb.GetBottom()))

    def layer_name(self, name: str):
        """The board's name of a copper layer given by that name or by KiCad's standard name (F.Cu, In1.Cu, B.Cu);
        None when the board has no such layer."""
        return name if name in self.lid else self.alias.get(name)

    def merged(self, nets, layer: str, items: bool = True) -> list:
        """The copper of the named nets on one layer, merged: zone fill and, with items, their pads, tracks and
        via rings. nets None: every net (zone fill only makes sense then). Polygons as [[outer, hole, ...], ...]."""
        p, lid = self.p, self.lid[layer]
        acc = p.SHAPE_POLY_SET()
        for z in self.zones:
            if z.IsOnLayer(lid) and (nets is None or str(z.GetNetname()) in nets):
                fp = z.GetFilledPolysList(lid)
                for i in range(fp.OutlineCount()):
                    k = acc.AddOutline(fp.Outline(i))
                    for h in range(fp.HoleCount(i)):
                        acc.AddHole(fp.Hole(i, h), k)
        if items and nets is not None:
            err = p.FromMM(0.002)
            for pad in self.pads:
                if pad["net"] in nets and layer in pad["layers"]:
                    pad["obj"].TransformShapeToPolygon(acc, lid, 0, err, p.ERROR_INSIDE)
            for t, obj in zip(self.tracks, self._track_obj):
                if t["net"] in nets and t["layer"] == layer:
                    obj.TransformShapeToPolygon(acc, lid, 0, err, p.ERROR_INSIDE)
            for v, obj in zip(self.vias, self._via_obj):
                if v["net"] in nets and layer in v["layers"]:
                    obj.TransformShapeToPolygon(acc, lid, 0, err, p.ERROR_INSIDE)
        if acc.OutlineCount():
            acc.Simplify()
        return pcb_common.poly_points(acc)

    def pad_poly(self, pad: dict, layer: str) -> list:
        """The copper of a pad on one layer as polygons [[outer, hole, ...], ...]."""
        if layer not in pad["poly"]:
            ps = self.p.SHAPE_POLY_SET()
            pad["obj"].TransformShapeToPolygon(ps, self.lid[layer], 0, self.p.FromMM(0.002), self.p.ERROR_INSIDE)
            pad["poly"][layer] = pcb_common.poly_points(ps)
        return pad["poly"][layer]


def reference_nets(pic: Picture, wanted: list) -> tuple[list, str]:
    """(the reference nets, how they were chosen). wanted: names or patterns; empty: the net with the largest
    filled area."""
    if wanted:
        hit, dead = match_nets(wanted, pic.nets)
        if not hit:
            raise kicad_io.KicadIOError(f"the reference net(s) {', '.join(wanted)} are not on the board")
        return hit, "as given" + (f"; no net matches {', '.join(dead)}" if dead else "")
    area = {n: a for n, a in pic.fill_area.items() if n and a > 0}
    if not area:
        return [], "the board has no filled zone of any net: nothing can be a reference"
    net = max(area, key=lambda n: area[n])
    return [net], f"the net with the largest filled area ({area[net]:.0f} mm2); name others in `reference`"


def reference_layers(pic: Picture, stack, ref_nets: list, given: dict) -> tuple[dict, dict]:
    """({signal layer: reference layer}, {signal layer: how it was chosen}) for every copper layer."""
    L = pic.layers
    named = {}
    for k, v in given.items():
        a, b = pic.layer_name(k), pic.layer_name(v)
        if a is None or b is None or a == b:
            raise kicad_io.KicadIOError(f"board.toml [fast_nets.reference_layer]: \"{k}\" = \"{v}\" does not fit the board's "
                                        f"copper layers ({', '.join(L)})")
        named[a] = b
    given = named
    ref_area = {}
    for z in pic.zones:
        if str(z.GetNetname()) in ref_nets:
            for lid in pic.cu:
                if z.IsOnLayer(lid):
                    ref_area[pic.name[lid]] = ref_area.get(pic.name[lid], 0.0) + z.GetFilledPolysList(lid).Area() / 1e12
    out, why = {}, {}
    for i, name in enumerate(L):
        if name in given:
            out[name], why[name] = given[name], "board.toml"
            continue
        if len(L) < 2:
            continue
        cand = [L[j] for j in (i - 1, i + 1) if 0 <= j < len(L)]
        if len(cand) == 1:
            out[name], why[name] = cand[0], ("the other side" if len(L) == 2 else "the neighbouring layer")
            continue
        dist = {}
        if stack is not None:
            for c in cand:
                bt = stack.between(name, c)
                if not [m for m in bt["missing"] if m.startswith("thickness")]:
                    dist[c] = bt["h"]
        if len(dist) == 2 and abs(dist[cand[0]] - dist[cand[1]]) > 1e-3:
            best = min(cand, key=lambda c: dist[c])
            out[name], why[name] = best, f"the nearest copper layer by the stack ({dist[best]:.3f} mm against {dist[[c for c in cand if c != best][0]]:.3f} mm)"
        else:
            best = max(cand, key=lambda c: ref_area.get(c, 0.0))
            out[name], why[name] = best, ("both neighbours are equally near" if len(dist) == 2 else "no usable layer stack") + \
                ": the neighbour with more reference copper; set [fast_nets.reference_layer] when it is the other one"
    return out, why


# ---- measuring -----------------------------------------------------------------------------------------------------------
def scan(path: Path, step: float, state) -> list:
    """Walk a path in steps and return its stretches [(s0, s1, code, share)]: code as state(s) gives it, the
    borders between two codes refined by bisection; share: the largest second value of state() in the stretch."""
    n = max(1, int(math.ceil(path.length / step)))
    ss = [path.length * i / n for i in range(n + 1)]
    st = [state(s) for s in ss]
    out, s0, cur, share = [], 0.0, st[0][0], st[0][1]
    for i in range(1, n + 1):
        if st[i][0] != cur:
            a, b = ss[i - 1], ss[i]
            for _ in range(12):
                m = (a + b) / 2
                if state(m)[0] == cur:
                    a = m
                else:
                    b = m
            out.append((s0, (a + b) / 2, cur, share))
            s0, cur, share = (a + b) / 2, st[i][0], st[i][1]
        else:
            share = max(share, st[i][1])
    out.append((s0, path.length, cur, share))
    return out


class Below:
    """What copper lies at a point of a layer, beside the reference nets: the nets of zone fills, tracks, pads, vias."""

    def __init__(self, pic: Picture, layer: str, skip: list):
        self.pic, self.layer = pic, layer
        self.fills, self.polys = {}, {}
        for net in sorted(pic.zone_layers.get(layer, ())):
            if net not in skip:
                polys = pic.merged([net], layer, items=False)
                if polys:
                    self.fills[net], self.polys[net] = PolyIndex(polys), polys
        self.tracks = [t for t in pic.tracks if t["layer"] == layer and t["net"] not in skip]
        self.pads = [p for p in pic.pads if layer in p["layers"] and p["net"] not in skip]
        self.vias = [v for v in pic.vias if layer in v["layers"] and v["net"] not in skip]

    def at(self, x: float, y: float) -> set:
        nets = set()
        for net, idx in self.fills.items():
            b = idx.box
            if b and b[0] <= x <= b[2] and b[1] <= y <= b[3] and idx.contains(x, y):
                nets.add(net)
        for t in self.tracks:
            b, r = t["box"], t["w"] / 2
            if b[0] - r <= x <= b[2] + r and b[1] - r <= y <= b[3] + r and t["path"].dist(x, y) <= r:
                nets.add(t["net"])
        for p in self.pads:
            b = p["box"]
            if b[0] <= x <= b[2] and b[1] <= y <= b[3] and any(poly_has(lp, x, y) for lp in self.pic.pad_poly(p, self.layer)):
                nets.add(p["net"])
        for v in self.vias:
            if math.hypot(v["x"] - x, v["y"] - y) <= v["d"] / 2:
                nets.add(v["net"])
        return nets


def measure(pic: Picture, nets: list, ref_nets: list, ref_of: dict, L) -> dict:
    """Coverage, edge distance and layer changes of the listed nets. Returns the plain result (see main)."""
    step, exempt_r, reach = L["sample_mm"], L["pad_exempt_mm"], L["edge_reach_mm"]
    ref_polys, ref_idx, below = {}, {}, {}

    def idx_of(layer):
        if layer not in ref_idx:
            ref_polys[layer] = pic.merged(ref_nets, layer) if ref_nets else []
            ref_idx[layer] = PolyIndex(ref_polys[layer])
        return ref_idx[layer]

    rows, pieces, exempt_parts = [], [], []
    for net in nets:
        own_pads = [p for p in pic.pads if p["net"] == net]
        own_vias = [v for v in pic.vias if v["net"] == net]
        by_layer = {}
        for ti, t in enumerate(pic.tracks):
            if t["net"] == net:
                by_layer.setdefault(t["layer"], []).append(ti)
        for layer in [n for n in pic.layers if n in by_layer]:
            ref = ref_of.get(layer)
            row = {"net": net, "layer": layer, "reference_layer": ref, "length": 0.0, "uncovered": 0.0, "exempt": 0.0,
                   "widths": sorted({round(pic.tracks[ti]["w"], 4) for ti in by_layer[layer]}),
                   "edge": None, "edge_at": None, "edge_beyond": reach, "edge_n": 0, "runs": []}
            rows.append(row)
            if ref is None:
                row["length"] = sum(pic.tracks[ti]["path"].length for ti in by_layer[layer])
                row["uncovered"] = row["length"]
                continue
            idx = idx_of(ref)
            for ti in by_layer[layer]:
                t = pic.tracks[ti]
                path, w = t["path"], t["w"]
                k = max(1, int(math.ceil(w / ACROSS - 1e-9)))
                offs = [-w / 2 + w * j / k for j in range(k + 1)]
                bx = (t["box"][0] - exempt_r - w, t["box"][1] - exempt_r - w, t["box"][2] + exempt_r + w, t["box"][3] + exempt_r + w)
                near_pads = [pic.pad_poly(p, layer) for p in own_pads if layer in p["layers"] and pcb_common.box_gap(p["box"], bx) == 0]
                near_vias = [v for v in own_vias if layer in v["layers"] and bx[0] <= v["x"] <= bx[2] and bx[1] <= v["y"] <= bx[3]]

                def exempt(x, y):
                    for v in near_vias:
                        if math.hypot(v["x"] - x, v["y"] - y) - v["d"] / 2 <= exempt_r:
                            return True
                    for polys in near_pads:
                        for lp in polys:
                            if poly_dist(lp, x, y) <= exempt_r:
                                return True
                    return False

                def state(s):
                    x, y, ux, uy = path.at(s)
                    bare = sum(1 for o in offs if not idx.contains(x - uy * o, y + ux * o))
                    if not bare:
                        return 0, 0.0
                    return (2 if exempt(x, y) else 1), bare / len(offs)

                row["length"] += path.length
                for s0, s1, code, share in scan(path, step, state):
                    if code == 1:
                        row["uncovered"] += s1 - s0
                        pieces.append({"net": net, "layer": layer, "ref": ref, "track": ti, "s0": s0, "s1": s1, "share": share,
                                       "w": w, "pts": path.piece(s0, s1), "open0": s0 <= 1e-9, "open1": s1 >= path.length - 1e-9})
                    elif code == 2:
                        row["exempt"] += s1 - s0
                        exempt_parts.append({"net": net, "layer": layer, "ref": ref, "w": w, "pts": path.piece(s0, s1)})
                    else:                                               # covered: how near is the edge of the reference copper
                        n = max(1, int(math.ceil((s1 - s0) / step)))
                        for i in range(n + 1):
                            x, y, _, _ = path.at(s0 + (s1 - s0) * i / n)
                            if exempt(x, y):
                                continue
                            hit = idx.nearest(x, y, reach + w / 2)
                            row["edge_n"] += 1
                            if hit is not None:
                                d = max(0.0, hit[0] - w / 2)
                                if row["edge"] is None or d < row["edge"]:
                                    row["edge"], row["edge_at"] = d, (x, y)
    # ---- runs: the uncovered pieces of one net and layer that meet at a track end are one run
    parent = list(range(len(pieces)))

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    ends = {}
    for k, pc in enumerate(pieces):
        for is_open, pt in ((pc["open0"], pc["pts"][0]), (pc["open1"], pc["pts"][-1])):
            if is_open:
                ends.setdefault((pc["net"], pc["layer"], round(pt[0], 3), round(pt[1], 3)), []).append(k)
    for same in ends.values():
        for k in same[1:]:
            parent[find(k)] = find(same[0])
    groups = {}
    for k in range(len(pieces)):
        groups.setdefault(find(k), []).append(k)
    runs = []
    for ks in groups.values():
        pcs = [pieces[k] for k in ks]
        length = sum(pc["s1"] - pc["s0"] for pc in pcs)
        if length < MIN_RUN:
            continue
        ends_ = [pc["pts"][0] for pc in pcs] + [pc["pts"][-1] for pc in pcs]
        a, b = max(((p, q) for p in ends_ for q in ends_), key=lambda pq: math.hypot(pq[0][0] - pq[1][0], pq[0][1] - pq[1][1]))
        big = max(pcs, key=lambda pc: pc["s1"] - pc["s0"])
        mid = pic.tracks[big["track"]]["path"].at((big["s0"] + big["s1"]) / 2)
        layer, ref = pcs[0]["layer"], pcs[0]["ref"]
        if ref not in below:
            below[ref] = Below(pic, ref, ref_nets)
        found, bare, idx = {}, 0, ref_idx[ref]
        samples = 0
        for pc in pcs:                                                  # what lies below the bare points of the run
            path, w = pic.tracks[pc["track"]]["path"], pc["w"]
            k = max(1, int(math.ceil(w / ACROSS - 1e-9)))
            n = max(1, min(12, int(math.ceil((pc["s1"] - pc["s0"]) / step))))
            for i in range(n + 1):
                x, y, ux, uy = path.at(pc["s0"] + (pc["s1"] - pc["s0"]) * (i + 0.5) / (n + 1))
                for j in range(k + 1):
                    o = -w / 2 + w * j / k
                    qx, qy = x - uy * o, y + ux * o
                    if idx.contains(qx, qy):
                        continue
                    samples += 1
                    got = below[ref].at(qx, qy)
                    if not got:
                        bare += 1
                    for g in got:
                        found[g] = found.get(g, 0) + 1
        xs, ys = [q[0] for pc in pcs for q in pc["pts"]], [q[1] for pc in pcs for q in pc["pts"]]
        runs.append({"net": pcs[0]["net"], "layer": layer, "reference_layer": ref, "length": length, "from": a, "to": b,
                     "at": (mid[0], mid[1]), "share": max(pc["share"] for pc in pcs), "width": max(pc["w"] for pc in pcs),
                     "below_nets": sorted(found, key=lambda g: -found[g]), "below_bare": bare > 0, "below_samples": samples,
                     "pieces": [pc["pts"] for pc in pcs], "box": (min(xs), min(ys), max(xs), max(ys)), "branches": len(pcs)})
    runs.sort(key=lambda r: (-r["length"], r["net"], r["at"]))
    for n, r in enumerate(runs, 1):
        r["no"] = n
        r["fail"] = r["length"] > L["max_gap_mm"] + 1e-9
        for row in rows:
            if row["net"] == r["net"] and row["layer"] == r["layer"]:
                row["runs"].append(n)
    # ---- layer changes
    ref_set = set(ref_nets)
    returns = [{"x": v["x"], "y": v["y"], "net": v["net"], "layers": set(v["layers"]), "what": "via"} for v in pic.vias if v["net"] in ref_set] + \
              [{"x": p["x"], "y": p["y"], "net": p["net"], "layers": set(p["layers"]), "what": f"pad {p['ref']}.{p['num']}"}
               for p in pic.pads if p["net"] in ref_set and p["hole"] and p["plated"]]
    changes, plain = [], 0
    for net in nets:
        tr = [t for t in pic.tracks if t["net"] == net]
        smd = [p for p in pic.pads if p["net"] == net and not p["hole"]]
        for v in pic.vias:
            if v["net"] != net:
                continue
            on = set()
            for t in tr:
                b, r = t["box"], max(t["w"] / 2, 0.02)
                if b[0] - r <= v["x"] <= b[2] + r and b[1] - r <= v["y"] <= b[3] + r and t["path"].dist(v["x"], v["y"]) <= r:
                    on.add(t["layer"])
            for p in smd:
                b = p["box"]
                if b[0] <= v["x"] <= b[2] and b[1] <= v["y"] <= b[3]:
                    for layer in p["layers"]:
                        if any(poly_has(lp, v["x"], v["y"]) for lp in pic.pad_poly(p, layer)):
                            on.add(layer)
            on = [n for n in pic.layers if n in on]
            refs = sorted({ref_of.get(n) for n in on} - {None}, key=pic.layers.index)
            if len(on) < 2 or len(refs) < 2:
                plain += 1
                continue
            need = set(refs)
            best = None
            for r in returns:
                if need <= r["layers"]:
                    d = math.hypot(r["x"] - v["x"], r["y"] - v["y"])
                    if best is None or d < best[0]:
                        best = (d, r)
            ok = best is not None and best[0] <= L["via_return_mm"] + 1e-9
            changes.append({"net": net, "x": v["x"], "y": v["y"], "layers": on, "references": refs, "d": v["d"],
                            "nearest": best[0] if best else None, "nearest_what": (best[1]["what"] + " of " + best[1]["net"]) if best else None,
                            "nearest_at": (best[1]["x"], best[1]["y"]) if best else None, "ok": ok})
    changes.sort(key=lambda c: (c["ok"], c["net"], c["x"], c["y"]))
    for n, c in enumerate(changes, 1):
        c["no"] = n
    for ref in {r["reference_layer"] for r in rows if r["reference_layer"]}:
        if ref not in below:
            below[ref] = Below(pic, ref, ref_nets)
    return {"rows": rows, "runs": runs, "exempt_parts": exempt_parts, "changes": changes, "plain_vias": plain,
            "ref_polys": ref_polys, "returns": returns, "below": below}


# ---- pictures ------------------------------------------------------------------------------------------------------------
def _pil():
    kicad_io.add_user_site()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise kicad_io.KicadIOError("the Pillow library is needed to draw the overlay pictures (pip install pillow)") from None
    Image.MAX_IMAGE_PIXELS = None
    return Image, ImageDraw, ImageFont


def _font(size: int):
    _, _, ImageFont = _pil()
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                                                   # an older Pillow: its fixed small font
        return ImageFont.load_default()


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9+-]+", "_", str(s)).strip("_") or "x"


def legend(img, lines: list):
    """The picture with lines of text under it (black on white)."""
    Image, ImageDraw, _ = _pil()
    font = _font(15)
    width = max(img.width, 640)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    wrapped = []
    for ln in lines:                                                    # wrap to the picture's width
        cur = ""
        for word in ln.split(" "):
            if cur and probe.textlength(cur + " " + word, font=font) > width - 12:
                wrapped.append(cur)
                cur = "    " + word
            else:
                cur = (cur + " " + word) if cur else word
        wrapped.append(cur)
    out = Image.new("RGB", (width, img.height + 22 * len(wrapped) + 6), (255, 255, 255))
    out.paste(img.convert("RGB"), (0, 0))
    dr = ImageDraw.Draw(out)
    for k, ln in enumerate(wrapped):
        dr.text((6, img.height + 3 + 22 * k), ln, fill=(0, 0, 0), font=font)
    return out


def draw_layer(pic: Picture, res: dict, ref: str, view: tuple, ppm: float, colour: dict, only_run=None, only_via=None):
    """One reference layer with the listed nets that run over it. view: (x0, y0, x1, y1) in mm; returns an image."""
    Image, ImageDraw, _ = _pil()
    x0, y0, x1, y1 = view
    s = ppm * SS
    size = (max(1, int(round((x1 - x0) * s))), max(1, int(round((y1 - y0) * s))))
    img = Image.new("RGB", size, C_OUT if pic.outline else C_BOARD)
    dr = ImageDraw.Draw(img)

    def px(q):
        return ((q[0] - x0) * s, (q[1] - y0) * s)

    def seen(box, pad=0.0):
        return not (box[2] + pad < x0 or box[0] - pad > x1 or box[3] + pad < y0 or box[1] - pad > y1)

    def poly(loops, fill, hole):
        if len(loops[0]) >= 3 and seen(pcb_common.poly_box(loops[0])):
            dr.polygon([px(q) for q in loops[0]], fill=fill)
            for h in loops[1:]:
                if len(h) >= 3:
                    dr.polygon([px(q) for q in h], fill=hole)

    def line(pts, fill, w_mm, min_px=2.0, round_ends=True):
        wd = max(w_mm * s, min_px * SS)
        pp = [px(q) for q in pts]
        dr.line(pp, fill=fill, width=max(1, int(round(wd))), joint="curve")
        if round_ends:                                                  # a track ends round; a marked stretch ends where it ends
            r = wd / 2
            for a in (pp[0], pp[-1]):
                dr.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), fill=fill)

    def disc(x, y, r_mm, fill, min_px=1.5):
        c, r = px((x, y)), max(r_mm * s, min_px * SS)
        dr.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=fill)

    def area(p):
        b = pcb_common.poly_box(p[0])
        return (b[2] - b[0]) * (b[3] - b[1])

    for p in sorted(pic.outline, key=area, reverse=True):
        poly(p, C_BOARD, C_OUT)
    # zone fill of other nets on this layer; the reference copper through a mask (its holes must not wipe out
    # what lies in them); then the tracks, pads and vias of other nets, which lie in the plane's gaps
    for polys in res["below"][ref].polys.values():
        for p in sorted(polys, key=area, reverse=True):
            poly(p, C_OTHER, C_BOARD)
    mask = Image.new("L", size, 0)
    mdr = ImageDraw.Draw(mask)
    for p in sorted(res["ref_polys"].get(ref, []), key=area, reverse=True):
        if len(p[0]) >= 3 and seen(pcb_common.poly_box(p[0])):
            mdr.polygon([px(q) for q in p[0]], fill=255)
            for h in p[1:]:
                if len(h) >= 3:
                    mdr.polygon([px(q) for q in h], fill=0)
    img.paste(C_PLANE, (0, 0, size[0], size[1]), mask)
    del mask, mdr
    for t in res["below"][ref].tracks:
        if seen(t["box"], t["w"]):
            line(t["path"].pts, C_OTHER, t["w"], 1.0)
    for pd in res["below"][ref].pads:
        if seen(pd["box"]):
            for lp in pic.pad_poly(pd, ref):
                poly(lp, C_OTHER, C_BOARD)
    for v in res["below"][ref].vias:
        if x0 - 1 <= v["x"] <= x1 + 1 and y0 - 1 <= v["y"] <= y1 + 1:
            disc(v["x"], v["y"], v["d"] / 2, C_OTHER, 1.0)
    for r in res["returns"]:
        if ref in r["layers"] and x0 - 1 <= r["x"] <= x1 + 1 and y0 - 1 <= r["y"] <= y1 + 1:
            disc(r["x"], r["y"], 0.22, C_RETURN)
    for p in sorted(pic.outline, key=area, reverse=True):
        for lp in p:
            if len(lp) >= 2:
                dr.line([px(q) for q in lp] + [px(lp[0])], fill=C_EDGE, width=max(2, int(0.06 * s)))
    # the listed nets that refer to this layer: their own pads as outlines, their tracks filled
    for pd in pic.pads:
        if pd["net"] in colour and seen(pd["box"]):
            for layer in pd["layers"]:
                if res["ref_of"].get(layer) == ref:
                    for lp in pic.pad_poly(pd, layer):
                        if len(lp[0]) >= 3:
                            dr.line([px(q) for q in lp[0]] + [px(lp[0][0])], fill=colour[pd["net"]], width=max(2 * SS, int(0.04 * s)))
                    break
    labels = {}
    for t in pic.tracks:
        if t["net"] in colour and res["ref_of"].get(t["layer"]) == ref and seen(t["box"], t["w"]):
            line(t["path"].pts, colour[t["net"]], t["w"])
            key = (t["net"], t["layer"])
            if key not in labels or t["path"].length > labels[key][0]:
                labels[key] = (t["path"].length, t)
    for e in res["exempt_parts"]:
        if e["ref"] == ref:
            line(e["pts"], C_EXEMPT, e["w"] * 0.6, 2.0, round_ends=False)
    for r in res["runs"]:
        if r["reference_layer"] == ref and seen(r["box"], r["width"]):
            for pts in r["pieces"]:
                line(pts, C_RUN, r["width"], 4.0, round_ends=False)
    for c in res["changes"]:
        if ref in c["references"] and x0 - 2 <= c["x"] <= x1 + 2 and y0 - 2 <= c["y"] <= y1 + 2:
            col = C_OK if c["ok"] else C_BAD
            if c["nearest_at"] and c["ok"]:
                dr.line([px((c["x"], c["y"])), px(c["nearest_at"])], fill=col, width=max(2, int(0.05 * s)))
            cx, cy = px((c["x"], c["y"]))
            r = max((c["d"] / 2 + 0.25) * s, 7 * SS)
            dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=max(3 * SS, int(0.1 * s)))
    img = img.resize((max(1, size[0] // SS), max(1, size[1] // SS)), Image.LANCZOS)
    # ---- text, at the final scale
    dr = ImageDraw.Draw(img)

    def fx(q):
        return ((q[0] - x0) * ppm, (q[1] - y0) * ppm)

    font = _font(int(max(12, min(22, 0.5 * ppm))))
    signal_layers = {t["layer"] for (_, _), (_, t) in labels.items()}
    for (net, layer), (_, t) in sorted(labels.items()):
        x, y, ux, uy = t["path"].at(t["path"].length / 2)
        cx, cy = fx((x - uy * (t["w"] / 2 + 0.25), y + ux * (t["w"] / 2 + 0.25)))
        text = short(net) + (f" [{layer}]" if len(signal_layers) > 1 else "")
        dr.text((cx + 3, cy + 3), text, fill=colour[net], font=font, stroke_width=3, stroke_fill=(255, 255, 255))
    mfont = _font(int(max(13, min(20, 0.45 * ppm))))
    for r in res["runs"]:
        if r["reference_layer"] == ref and seen(r["box"], 1.0):
            cx, cy = fx(r["at"])
            tx, ty = cx + 16, cy - 22
            dr.line([(cx, cy), (tx, ty)], fill=C_RUN, width=2)
            text = str(r["no"])
            tb = dr.textbbox((0, 0), text, font=mfont)
            w, h = tb[2] - tb[0] + 10, tb[3] - tb[1] + 8
            dr.rounded_rectangle((tx - 2, ty - h, tx + w, ty + 2), radius=5, fill=(255, 255, 255), outline=C_RUN, width=2)
            dr.text((tx + 4 - tb[0], ty - h + 4 - tb[1]), text, fill=C_RUN, font=mfont)
    for c in res["changes"]:
        if ref in c["references"] and x0 <= c["x"] <= x1 and y0 <= c["y"] <= y1 and (not c["ok"] or only_via == c["no"]):
            cx, cy = fx((c["x"], c["y"]))
            dr.text((cx + 12, cy + 8), f"V{c['no']}", fill=C_BAD if not c["ok"] else C_OK, font=mfont, stroke_width=3, stroke_fill=(255, 255, 255))
    return img


def clear_pictures(out_dir: str) -> None:
    """Remove the pictures of an earlier run: they must not stay beside a newer result."""
    if os.path.isdir(out_dir):
        for old in os.listdir(out_dir):
            if old.endswith(".png"):
                os.remove(os.path.join(out_dir, old))


def pictures(pic: Picture, res: dict, out_dir: str, L, nets: list) -> tuple[list, list]:
    """Write the overview of every reference layer and the zoom tiles. Returns (rows for the report, notes)."""
    os.makedirs(out_dir, exist_ok=True)
    clear_pictures(out_dir)
    colour = {n: PALETTE[k % len(PALETTE)] for k, n in enumerate(nets)}
    made, notes = [], []
    bx = pic.box
    view = (bx[0] - 1.5, bx[1] - 1.5, bx[2] + 1.5, bx[3] + 1.5)
    w_mm, h_mm = view[2] - view[0], view[3] - view[1]
    ppm = min(max(40.0, min(120.0, 1600.0 / max(w_mm, h_mm))), math.sqrt(MAX_PLOT_MP * 1e6 / max(w_mm * h_mm, 1e-6)))
    refs = [n for n in pic.layers if n in {r["reference_layer"] for r in res["rows"] if r["reference_layer"]}]
    for ref in refs:
        over = sorted({r["layer"] for r in res["rows"] if r["reference_layer"] == ref}, key=pic.layers.index)
        img = draw_layer(pic, res, ref, view, ppm, colour)
        n_runs = sum(1 for r in res["runs"] if r["reference_layer"] == ref)
        lines = [f"Return paths: reference layer {ref} under the listed nets on {', '.join(over)}; seen from the top side; {ppm:.0f} px/mm; "
                 f"x {view[0]:.1f}..{view[2]:.1f}, y {view[1]:.1f}..{view[3]:.1f} mm",
                 f"grey: copper of {', '.join(short(n) for n in res['ref_nets']) or 'no net'} (the reference); white: no copper; "
                 f"pale orange: copper of other nets; dark dots: return vias",
                 f"coloured: the listed nets; RED with a number: uncovered run ({n_runs} here); orange: uncovered near the net's own "
                 f"pads and vias (not counted)",
                 f"rings: layer change; green = a return via within {L['via_return_mm']:g} mm (line to it), magenta = none"]
        rel = f"{safe_name(ref)}.png"
        legend(img, lines).save(os.path.join(out_dir, rel))
        made.append({"file": rel, "what": f"reference layer {ref} under {', '.join(over)}: {n_runs} uncovered run(s), "
                                          f"{sum(1 for c in res['changes'] if ref in c['references'])} layer change(s)", "layer": ref})
    drawn = 0
    for r in sorted(res["runs"], key=lambda r: (not r["fail"], r["no"])):
        if drawn >= MAX_TILES:
            notes.append(f"{len(res['runs']) - drawn} uncovered run(s) have no zoom tile (only the first {MAX_TILES} are drawn): see the overview")
            break
        b = r["box"]
        side = min(40.0, max(6.0, 2.5 * max(b[2] - b[0], b[3] - b[1]) + 2 * r["width"]))
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        tv = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
        tp = min(160.0, 900.0 / side)
        img = draw_layer(pic, res, r["reference_layer"], tv, tp, colour, only_run=r["no"])
        rel = f"run{r['no']:03d}_{safe_name(short(r['net']))}_{safe_name(r['layer'])}.png"
        legend(img, [f"run {r['no']}: {short(r['net'])} on {r['layer']} over {r['reference_layer']}: {r['length']:.2f} mm uncovered at "
                     f"({r['at'][0]:.2f}, {r['at'][1]:.2f}); below: {below_text(r)}",
                     f"window {side:.0f} mm, centre ({cx:.2f}, {cy:.2f}), {tp:.0f} px/mm; grey = reference copper, white = no copper, "
                     f"pale orange = other nets"]).save(os.path.join(out_dir, rel))
        r["tile"] = rel
        drawn += 1
    for c in res["changes"]:
        if c["ok"]:
            continue
        side = max(8.0, 3 * L["via_return_mm"])
        tv = (c["x"] - side / 2, c["y"] - side / 2, c["x"] + side / 2, c["y"] + side / 2)
        tp = min(160.0, 900.0 / side)
        ref = c["references"][0]
        img = draw_layer(pic, res, ref, tv, tp, colour, only_via=c["no"])
        rel = f"via{c['no']:03d}_{safe_name(short(c['net']))}.png"
        near = f"nearest return via {c['nearest']:.2f} mm away" if c["nearest"] is not None else "no return via on the board"
        legend(img, [f"V{c['no']}: {short(c['net'])} changes from {' to '.join(c['layers'])} at ({c['x']:.2f}, {c['y']:.2f}): {near} "
                     f"(limit {L['via_return_mm']:g} mm)",
                     f"shown over {ref}; window {side:.0f} mm, {tp:.0f} px/mm"]).save(os.path.join(out_dir, rel))
        c["tile"] = rel
    return made, notes


def below_text(r: dict) -> str:
    nets = [f"copper of {short(n)}" for n in r["below_nets"]]
    if r["below_bare"] or not nets:
        nets = ["no copper"] + nets
    return ", ".join(nets)


# ---- the check -------------------------------------------------------------------------------------------------------------
def _f(v, nd=2):
    return f"{v:.{nd}f}"


def main(argv: list[str]) -> int:
    ap = pcb_common.io_parser("Return path of every fast or sensitive net on the saved fill (rule GEN-19), with an overlay "
                              "picture per reference layer.", epilog="Exit codes: 0 pass (or no such net declared), 1 findings, "
                                                                     "2 could not run.")
    ap.add_argument("--net", action="append", help="net name or pattern to check (repeatable); replaces [fast_nets] nets")
    ap.add_argument("--reference", action="append", help="reference net (repeatable); replaces [fast_nets] reference")
    ap.add_argument("--max-gap", type=float, dest="max_gap_mm", help="mm: an uncovered run longer than this fails")
    ap.add_argument("--pad-exempt", type=float, dest="pad_exempt_mm", help="mm around the net's own pads and vias that is not counted")
    ap.add_argument("--via-return", type=float, dest="via_return_mm", help="mm: largest distance from a layer change to a return via")
    ap.add_argument("--sample", type=float, dest="sample_mm", help="mm: step along the tracks")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                               # no message box, ever: warnings go to stderr
    job = pcb_common.resolve(a)
    cfg = job.cfg("fast_nets")
    L = pcb_common.Limits(cfg, DEFAULTS, vars(a))
    if L["sample_mm"] <= 0 or L["sample_mm"] > 1.0 or L["max_gap_mm"] < 0 or L["pad_exempt_mm"] < 0 or L["via_return_mm"] <= 0:
        raise kicad_io.KicadIOError("settings out of range: sample_mm in (0, 1], max_gap_mm and pad_exempt_mm not negative, via_return_mm positive")
    patterns = a.net if a.net else cfg.get("nets", [])
    wanted_ref = a.reference if a.reference else cfg.get("reference", [])
    given_layers = cfg.get("reference_layer", {})
    for what, v in (("nets", patterns), ("reference", wanted_ref)):
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise kicad_io.KicadIOError(f"board.toml [fast_nets]: '{what}' must be a list of net names or patterns")
    if not isinstance(given_layers, dict) or not all(isinstance(v, str) for v in given_layers.values()):
        raise kicad_io.KicadIOError("board.toml [fast_nets.reference_layer] must be a table: signal layer = \"reference layer\"")
    title = "Return paths of the fast and sensitive nets (GEN-19), on the saved fill"
    data = {"script": "return_path_check.py", "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board),
            "declared": bool(patterns), "patterns": patterns, "limits": L.to_dict(), "nets": [], "runs": [], "layer_changes": [],
            "images": [], "crops": [], "failures": [], "notes": []}
    pic_dir = os.path.join(job.out, "review", "return_path")
    with pcb_common.work_copy(job.board, "return-path-") as copy:
        pic = Picture(kicad_io.load_board(copy))
        nets, dead = match_nets(patterns, pic.nets) if patterns else ([], [])
        # a listed name that matches nothing is a finding: a typing error must not drop a net from the check silently
        missing = [f"listed net {d} is not on the board: a name that matches nothing checks nothing" for d in dead]
        if not patterns:                                                # no list at all: nothing to prove, and that is said
            why = ("board.toml has no [fast_nets] table and no --net was given" if not cfg else "the list of [fast_nets] is empty")
            first = f"**No fast or sensitive net declared**: {why}. Nothing was measured; record this in the layout ledger (GEN-19)."
            md = [f"# {title}", "", first, ""] + pcb_common.header(title, job, "return_path_check.py")[2:] + \
                 ["Settings:", ""] + L.table() + ["", f"The board has {len(pic.nets)} nets, {len(pic.tracks)} tracks and arcs, {len(pic.vias)} vias.",
                                                   "", "**Result: PASS** (no fast or sensitive net declared)"]
            data.update(result="PASS", declared=False, why=why, unmatched=dead)
            clear_pictures(pic_dir)
            p_md, _ = pcb_common.write_result(job.out, "return_path", md, data)
            print(f"PASS: no fast or sensitive net declared ({why}) -> {p_md}")
            return 0
        if not nets:                                                    # a list, and not one entry of it is on the board
            first = (f"**Result: FAIL**: none of the {len(patterns)} listed net(s) is on the board ({', '.join(patterns)}): nothing was measured. "
                     f"Check the spelling against the board's net names.")
            md = [f"# {title}", "", first, ""] + pcb_common.header(title, job, "return_path_check.py")[2:] + \
                 ["Settings:", ""] + L.table() + ["", f"The board has {len(pic.nets)} nets, {len(pic.tracks)} tracks and arcs, {len(pic.vias)} vias.",
                                                   "", "## Findings", ""] + [f"- FAIL: {x}" for x in missing] + ["", first]
            data.update(result="FAIL", unmatched=dead, nets_checked=[], failures=missing)
            clear_pictures(pic_dir)
            p_md, _ = pcb_common.write_result(job.out, "return_path", md, data)
            for x in missing:
                print("FAIL ", x)
            print(f"FAIL: 0 net(s) checked; {len(dead)} listed name(s) match no net -> {p_md}")
            return 1
        Image, _, _ = _pil()                                            # before the work: without Pillow there is no result
        ref_nets, ref_how = reference_nets(pic, wanted_ref)
        clash = [n for n in nets if n in ref_nets]
        if clash:
            raise kicad_io.KicadIOError(f"{', '.join(clash)}: listed as a fast net and as a reference net at the same time")
        stack, stack_note = read_stack(job.board, job.settings, pic.layers)
        ref_of, ref_why = reference_layers(pic, stack, ref_nets, given_layers)
        res = measure(pic, nets, ref_nets, ref_of, L)
        res["ref_of"], res["ref_nets"] = ref_of, ref_nets
        images, pic_notes = pictures(pic, res, pic_dir, L, nets)
    # ---- the report
    rows, runs, changes = res["rows"], res["runs"], res["changes"]
    fails, notes = list(missing), list(pic_notes)
    if not ref_nets:
        fails.append(f"no reference copper: {ref_how}")
    elif pic.unfilled:
        notes.append(f"{pic.unfilled} zone(s) of the board are saved unfilled: the result holds for the file as it is; fill and save "
                     f"(layout/fill.py), then run again")
    for r in runs:
        if r["fail"]:
            fails.append(f"run {r['no']}: {r['net']} on {r['layer']}: {r['length']:.2f} mm without reference copper on {r['reference_layer']} "
                         f"at ({r['at'][0]:.2f}, {r['at'][1]:.2f}) (limit {L['max_gap_mm']:g} mm); below: {below_text(r)}")
    for c in changes:
        if not c["ok"]:
            near = f"the nearest is {c['nearest']:.2f} mm away ({c['nearest_what']})" if c["nearest"] is not None else \
                "there is none that reaches " + " and ".join(c["references"])
            fails.append(f"V{c['no']}: {c['net']} changes from {' to '.join(c['layers'])} at ({c['x']:.2f}, {c['y']:.2f}) and its reference from "
                         f"{' to '.join(c['references'])}: no return via within {L['via_return_mm']:g} mm; {near}")
    for row in rows:
        if row["reference_layer"] is None:
            fails.append(f"{row['net']} on {row['layer']}: the board has one copper layer: no reference layer")
    if stack_note and len(pic.layers) > 2:
        notes.append(stack_note + ": reference layers were chosen without thicknesses")
    result = "FAIL" if fails else "PASS"
    total = sum(r["length"] for r in rows)
    unc = sum(r["uncovered"] for r in rows)
    n_bad_runs = sum(1 for r in runs if r["fail"])
    n_bad_vias = sum(1 for c in changes if not c["ok"])
    first = (f"**Result: {result}**: {len(nets)} net(s), {total:.1f} mm of track; {unc:.2f} mm without reference copper below in {len(runs)} run(s), "
             f"{n_bad_runs} longer than {L['max_gap_mm']:g} mm; {len(changes)} layer change(s), {n_bad_vias} without a return via within "
             f"{L['via_return_mm']:g} mm." + (f" {len(dead)} listed name(s) match no net: {', '.join(dead)}." if dead else ""))
    md = [f"# {title}", "", first, ""] + pcb_common.header(title, job, "return_path_check.py")[2:]
    md += ["Settings:", ""] + L.table() + [
        "", f"Listed nets ({'--net' if a.net else 'board.toml [fast_nets] nets'}): {', '.join(f'`{p}`' for p in patterns)}; on the board: "
            f"{', '.join(f'`{n}`' for n in nets)}.",
        f"Reference nets: {', '.join(f'`{n}`' for n in ref_nets) or 'none'} ({ref_how}).", "",
        "Reference layer of each signal layer that carries a listed net:", ""]
    for layer in [n for n in pic.layers if any(r["layer"] == n for r in rows)]:
        md.append(f"- {layer}: {ref_of.get(layer, 'none')} ({ref_why.get(layer, 'the board has one copper layer')})")
    md += ["", "## Nets", "",
           f"Sampled every {L['sample_mm']:g} mm along each track and every {ACROSS:g} mm or less across its width. Uncovered: at least one "
           f"point of the width has no copper of a reference net below. Edge: the smallest distance from the track's edge to the edge of "
           f"the reference copper (measured up to {L['edge_reach_mm']:g} mm; not judged; GEN-08 asks for the larger of three track widths "
           f"and three heights above the reference).", "",
           "| Net | Layer | Reference layer | Width (mm) | Length (mm) | Uncovered, counted (mm) | Uncovered near own pads and vias, not counted (mm) "
           "| Runs | Edge of the reference copper (mm) | at (x, y) | Three widths (mm) | Result |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        bad = [n for n in row["runs"] if runs[n - 1]["fail"]]
        edge = "none: no reference layer" if row["reference_layer"] is None else \
            _f(row["edge"]) if row["edge"] is not None else \
            (f"more than {row['edge_beyond']:g}" if row["edge_n"] else "not measured: no covered stretch outside the exempt distance")
        at = f"({row['edge_at'][0]:.2f}, {row['edge_at'][1]:.2f})" if row["edge_at"] else "-"
        md.append(f"| {row['net']} | {row['layer']} | {row['reference_layer'] or 'none'} | {', '.join(format(w, 'g') for w in row['widths'])} | "
                  f"{_f(row['length'])} | {_f(row['uncovered'])} | {_f(row['exempt'])} | {len(row['runs'])} | {edge} | {at} | "
                  f"{3 * max(row['widths']):.2f} | {'FAIL: run ' + ', '.join(str(n) for n in bad) if bad or row['reference_layer'] is None else 'PASS'} |")
        data["nets"].append({"net": row["net"], "layer": row["layer"], "reference_layer": row["reference_layer"], "widths": row["widths"],
                             "length": round(row["length"], 3), "uncovered": round(row["uncovered"], 3), "exempt": round(row["exempt"], 3),
                             "runs": row["runs"], "edge": None if row["edge"] is None else round(row["edge"], 3),
                             "edge_points_measured": row["edge_n"],
                             "edge_at": [round(v, 3) for v in row["edge_at"]] if row["edge_at"] else None,
                             "result": "FAIL" if bad or row["reference_layer"] is None else "PASS"})
    md += ["", "## Uncovered runs", ""]
    if not runs:
        md.append("None: every listed net has reference copper under its whole width, outside the exempt distance of its own pads and vias.")
    else:
        md += [f"A run longer than {L['max_gap_mm']:g} mm fails. Width share: the largest part of the track's width that is bare at one place. "
               f"A stretch shorter than {MIN_RUN:g} mm is not listed.", "",
               "| No | Net | Layer | Over | From (x, y) | To (x, y) | Length (mm) | Width share | Below | Result | Zoom tile |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in runs[:MAX_ROWS]:
            md.append(f"| {r['no']} | {r['net']} | {r['layer']} | {r['reference_layer']} | ({r['from'][0]:.2f}, {r['from'][1]:.2f}) | "
                      f"({r['to'][0]:.2f}, {r['to'][1]:.2f}) | {_f(r['length'])} | {'the whole width' if r['share'] >= 0.999 else format(r['share'], '.0%')} | "
                      f"{below_text(r)} | {'FAIL' if r['fail'] else 'listed (not longer than the limit)'} | "
                      f"{'`review/return_path/' + r['tile'] + '`' if r.get('tile') else '-'} |")
        if len(runs) > MAX_ROWS:
            md.append(f"\n{len(runs) - MAX_ROWS} more run(s) are in the JSON result.")
    for r in runs:
        data["runs"].append({"no": r["no"], "net": r["net"], "layer": r["layer"], "reference_layer": r["reference_layer"],
                             "length": round(r["length"], 3), "from": [round(v, 3) for v in r["from"]], "to": [round(v, 3) for v in r["to"]],
                             "at": [round(v, 3) for v in r["at"]], "width_share": round(r["share"], 3), "below_nets": r["below_nets"],
                             "below_no_copper": r["below_bare"], "pieces": r["branches"], "result": "FAIL" if r["fail"] else "listed",
                             "tile": r.get("tile")})
        data["crops"].append({"name": f"return_run{r['no']}", "frame": "kicad", "x": round(r["at"][0], 2), "y": round(r["at"][1], 2),
                              "size": round(max(8.0, 2.5 * max(r["box"][2] - r["box"][0], r["box"][3] - r["box"][1])), 1),
                              "why": f"{short(r['net'])}: {r['length']:.2f} mm without reference copper on {r['reference_layer']}"})
    md += ["", "## Layer changes", ""]
    if not changes:
        md.append(f"None: no via of a listed net joins two layers with different reference layers ({res['plain_vias']} via(s) of the listed "
                  f"nets join one layer only or two layers with the same reference).")
    else:
        md += [f"A via where a listed net goes on to a layer with another reference layer needs a via or plated through-hole pad of a "
               f"reference net within {L['via_return_mm']:g} mm (centre to centre) that reaches both reference layers.", "",
               "| No | Net | At (x, y) | Layers | Reference layers | Nearest return via (mm) | What | Result | Zoom tile |", "|---|---|---|---|---|---|---|---|---|"]
        for c in changes:
            md.append(f"| V{c['no']} | {c['net']} | ({c['x']:.2f}, {c['y']:.2f}) | {' / '.join(c['layers'])} | {' / '.join(c['references'])} | "
                      f"{'none' if c['nearest'] is None else _f(c['nearest'])} | {c['nearest_what'] or '-'} | {'PASS' if c['ok'] else 'FAIL'} | "
                      f"{'`review/return_path/' + c['tile'] + '`' if c.get('tile') else '-'} |")
            data["layer_changes"].append({"no": c["no"], "net": c["net"], "at": [round(c["x"], 3), round(c["y"], 3)], "layers": c["layers"],
                                          "references": c["references"], "nearest": None if c["nearest"] is None else round(c["nearest"], 3),
                                          "nearest_what": c["nearest_what"], "result": "PASS" if c["ok"] else "FAIL", "tile": c.get("tile")})
            if not c["ok"]:
                data["crops"].append({"name": f"return_via{c['no']}", "frame": "kicad", "x": round(c["x"], 2), "y": round(c["y"], 2),
                                      "size": 8.0, "why": f"{short(c['net'])}: layer change without a return via within {L['via_return_mm']:g} mm"})
        if res["plain_vias"]:
            md.append(f"\n{res['plain_vias']} more via(s) of the listed nets join one layer only, or two layers with the same reference layer: not judged.")
    md += ["", "## Pictures (open every one and follow each net from end to end)", ""]
    for im in images:
        md.append(f"- `review/return_path/{im['file']}`: {im['what']}")
    n_tiles = sum(1 for r in runs if r.get("tile")) + sum(1 for c in changes if c.get("tile"))
    md.append(f"- {n_tiles} zoom tile(s) in `review/return_path/` (named in the tables above)" if n_tiles else "- no zoom tile: no uncovered run and no failing layer change")
    data["images"] = [{"file": "review/return_path/" + im["file"], "what": im["what"]} for im in images]
    if fails or notes:
        md += ["", "## Findings", ""] + [f"- FAIL: {x}" for x in fails] + [f"- note: {x}" for x in notes]
    md += ["", "## Not checked", "",
           "Whether the saved fill is up to date (`layout/fill.py --check`); whether the list of nets is complete; the second plane of an "
           "inner layer between two planes; a return path through parts in series (each net is measured alone); the distance and parallel "
           "run to an aggressor (GEN-09); the length of stubs (GEN-42); supply currents (`neck_check.py`). A plane of a supply net counts "
           "as reference only when it is named in `reference`. The pictures are not looked at by this script.",
           "", first]
    data.update(result=result, nets_checked=nets, unmatched=dead, reference_nets=ref_nets, reference_how=ref_how,
                reference_layers={k: {"reference": v, "why": ref_why.get(k, "")} for k, v in ref_of.items() if any(r["layer"] == k for r in rows)},
                stack=stack.to_list() if stack else None, stack_source=stack.source if stack else None,
                totals={"length": round(total, 3), "uncovered": round(unc, 3), "runs": len(runs), "runs_failed": n_bad_runs,
                        "layer_changes": len(changes), "layer_changes_failed": n_bad_vias, "plain_vias": res["plain_vias"]},
                failures=fails, notes=notes)
    p_md, _ = pcb_common.write_result(job.out, "return_path", md, data)
    for x in fails[:30]:
        print("FAIL ", x)
    for x in notes[:10]:
        print("note ", x)
    print(f"{result}: {len(nets)} net(s), {total:.1f} mm; {unc:.2f} mm uncovered in {len(runs)} run(s) ({n_bad_runs} over {L['max_gap_mm']:g} mm); "
          f"{len(changes)} layer change(s), {n_bad_vias} without a return via; {len(images)} picture(s)"
          + (f"; {len(dead)} listed name(s) match no net" if dead else "") + f" -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
