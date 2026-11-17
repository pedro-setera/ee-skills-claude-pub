"""A small grid router for the nets that are left after the hand-planned copper. For simple and medium boards.

What it does (a library for a project's src/build_board.py)
    r = Router(board, rules=...)       reads the board: outline, keep-out areas, pads, holes, silkscreen texts, the
                                       copper that is already there (hand tracks, vias, planned pours)
    r.keep_spokes("GND")               room for the thermal spokes of through-hole pins of a poured net
    r.fanout("GND")                    a via beside every SMD pad of a poured net, before anything else is routed
    plan = make_plan(r, classes=[...]) the route order: named classes first, then long nets, then short ones
    left = route_all(r, plan)          routes, then rips up and retries around the failures; returns what is open
    r.commit()                         writes the new tracks and vias into the board (once, at the end)

    How it routes: a 0.1 mm grid over the board, one raster per copper layer that holds the owner of every grid
    point (a net, free, or forbidden). A net is connected pad by pad, nearest first; each connection is an A-star
    search from all copper the net already has to the next pad, through points that keep clearance + half the
    track width + 0.08 mm from everything else (the other copper grown by a disc). Moves: eight directions on a
    layer, a through via between layers. Cost: length times the layer's weight, plus a fixed cost per via. The
    path becomes tracks at 0, 45 and 90 degrees; stair steps are replaced by straight runs where those are free.
    A pad that already has copper (a hand-made stub, the rest of a net that was cut) is reached at any point
    of that copper, so a stub is continued and not drawn over.
    A zone with priority 0 is taken as a fill that gives way to tracks (a ground fill): its net is not routed,
    its pads get fan-out vias. A zone with a higher priority is planned copper: other nets go around it and its
    own net may start from it.

Why it exists
    The last third of a board's nets are short, plain connections; drawing them by hand in a generated board is
    slow and not repeatable. Routing them by a rule (power and crossing nets first, long nets before short ones)
    left far fewer open connections than the other order.

WHERE IT STOPS (do not use it there)
    - No length matching, no differential-pair routing, no impedance control: a USB pair, a clock that must
      match, an RF line or a memory bus is drawn by hand (copper.py) from its own rules, never given to this
      router.
    - No escape of ball-grid packages and no fine-pitch escape: it cannot pass a track between pads closer than
      about 0.55 mm edge to edge. Escape dense pins by hand first (short stubs, vias), then let it continue
      from the stubs.
    - It does not know the return-path rule (GEN-19: unbroken ground under every fast or sensitive net). It
      changes layers and crosses a gap in the ground when that is shorter. Such nets are routed by hand first.
    - Through vias only; no blind, buried or micro vias; no via in a pad. Tracks at 0 / 45 / 90 degrees on a
      0.1 mm grid; no arcs, no teardrops, no neck-down at a pad. A track ends on the grid inside a pad or on
      another track, not at its centre.
    - It knows widths and clearances, not currents, return paths or noise: it will run a track under a switching
      node or split a ground fill if nothing forbids it. Say what is forbidden with keep-out areas and planned
      pours before it runs, and check the result (drc_run.py, zone_check.py, the render).
    - Plain Python: seconds for a small board, minutes for a medium one (about 150 parts); beyond that, or on a
      board denser than about 60 percent, it leaves nets open. An open net is reported, never hidden.
    - Inner layers are taken as planes: tracks go on the outer layers unless route_layers says otherwise.

board.toml keys: none. A library: no exit codes; what cannot be done raises kicad_io.KicadIOError.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import fnmatch
import heapq
import math
import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

if __name__ == "__main__":                      # a library: there is nothing to run
    print(__doc__)
    sys.exit(0)

import numpy as np  # noqa: E402
import pcbnew  # noqa: E402

import kicad_io  # noqa: E402
from layout import board as B  # noqa: E402

G = 0.1                     # mm: the routing grid
RM = 0.08                   # mm: raster margin added to every clearance (0.05 gave real rule violations)
DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def _disk(r_cells: float) -> list:
    rc = int(math.ceil(r_cells))
    return [(dx, dy) for dy in range(-rc, rc + 1) for dx in range(-rc, rc + 1)
            if dx * dx + dy * dy <= r_cells * r_cells + 1e-9]


def dilate(mask, r_cells: float):
    """A boolean raster grown by a disc of that radius (in grid cells)."""
    if r_cells <= 0:
        return mask.copy()
    out = mask.copy()
    h, w = mask.shape
    for dx, dy in _disk(r_cells):
        if dx == 0 and dy == 0:
            continue
        ys0, ys1 = max(0, -dy), min(h, h - dy)
        xs0, xs1 = max(0, -dx), min(w, w - dx)
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] |= mask[ys0:ys1, xs0:xs1]
    return out


class _Pad:
    __slots__ = ("ref", "pin", "cells", "c", "code", "smd", "layer", "drill")

    def __init__(self, ref, pin, cells, c, code, smd, layer, drill):
        self.ref, self.pin, self.cells, self.c, self.code, self.smd, self.layer, self.drill = \
            ref, pin, cells, c, code, smd, layer, drill


class Router:
    """See the head of this file. rules: the board's minimums (board.RULES keys). route_layers: layer names
    where tracks may go (default: the two outer layers). layer_cost: {layer name: weight}; default 1.0 for the top
    layer and 1.8 for the others, so that the far side stays as whole as it can (it usually carries the ground).
    tracks=False: do not read the tracks and vias that are on the board (repair.py paints them itself)."""

    def __init__(self, board, *, rules: dict | None = None, route_layers: list | None = None,
                 layer_cost: dict | None = None, tracks: bool = True, silk_gap: float = 0.1):
        self.b = board
        self.rules = dict(B.RULES, **(rules or {}))
        self.cu = B.copper_layers(board)                        # KiCad layer numbers, top to bottom
        self.n_layers = len(self.cu)
        self.index = {lay: i for i, lay in enumerate(self.cu)}
        self.rl = sorted(self.index[B.layer_id(board, n)] for n in route_layers) if route_layers else \
            sorted({0, self.n_layers - 1})
        outline = B.board_outline(board)
        if outline is None:
            raise kicad_io.KicadIOError("router: the board outline on Edge.Cuts is not one closed shape")
        bb = outline.BBox()
        self.x0, self.y0 = B.mm(bb.GetX()) - 0.6, B.mm(bb.GetY()) - 0.6
        self.nx = int(round((B.mm(bb.GetRight()) + 0.7 - self.x0) / G)) + 1
        self.ny = int(round((B.mm(bb.GetBottom()) + 0.7 - self.y0) / G)) + 1
        self._xs = self.x0 + np.arange(self.nx) * G
        self._ys = self.y0 + np.arange(self.ny) * G
        shape = (self.n_layers, self.ny, self.nx)
        self.own = np.zeros(shape, np.int32)                    # 0 free, -1 forbidden, > 0 the net that owns it
        self.smd = np.zeros(shape[1:], bool)                    # SMD pad copper on any side: no via there
        self.hole = np.zeros(shape[1:], bool)                   # every drilled hole
        self.hole_net = np.zeros(shape[1:], np.int32)           # its net (-1: none)
        self.keepouts: list = []                                # (layer indices, polygon): no track may enter
        self.no_vias: list = []                                 # polygons: no via may enter
        self._keep_masks: dict = {}                             # those, grown by half a width, as rasters
        self.silk = np.zeros(shape[1:], bool)                   # silkscreen texts: no via under them
        self.zband = np.zeros(shape, bool)                      # the rim of a planned pour: never a starting point
        self.weight = np.full(shape, 1.8, np.float32)
        self.weight[self.rl[0]] = 1.0
        for name, w in (layer_cost or {}).items():
            self.weight[self.index[B.layer_id(board, name)]] = w
        self.silk_gap = silk_gap
        self.zone_codes: set = set()                            # nets with any zone: their pads are joined by it
        self.fanned: set = set()
        self._src = None
        self.base = None
        self.fixed: list = []                                   # items made before the first routing: never ripped
        self.routed: dict = {}                                  # net code -> items of the routing
        self._written: set = set()
        # the board edge and everything outside it
        inside = np.zeros(shape[1:], bool)
        for i in range(outline.OutlineCount()):
            self._or(inside, self.poly_mask(self._chain(outline.Outline(i))))
            for h in range(outline.HoleCount(i)):
                ix0, iy0, m = self.poly_mask(self._chain(outline.Hole(i, h)))
                inside[iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]] &= ~m
        self.own[:, dilate(~inside, (self.rules["edge"] + 0.05) / G)] = -1
        # keep-out areas: the board's (hole keep-outs, free bands, hand-drawn rule areas) and the footprints' own
        for z in list(board.Zones()) + [z for fp in board.GetFootprints() for z in fp.Zones()]:
            if z.GetIsRuleArea():
                self.keep(self._chain(z.Outline().Outline(0)), [self.index[lay] for lay in self.cu if z.IsOnLayer(lay)],
                          tracks=z.GetDoNotAllowTracks(), vias=z.GetDoNotAllowVias())
        self.pads: list[_Pad] = []
        self.names: dict = {}                                   # net code -> net name, of every net with a pad
        for fp in sorted(board.GetFootprints(), key=lambda f: B.natural(f.GetReference())):
            for p in fp.Pads():
                self._add_pad(fp.GetReference(), p)
        for fp in board.GetFootprints():
            for t in list(fp.GetFields()) + [g for g in fp.GraphicalItems() if g.GetClass() == "PCB_TEXT"]:
                self._add_text(t)
        for d in board.GetDrawings():
            if d.GetClass() == "PCB_TEXT":
                self._add_text(d)
        # copper zones: priority 0 gives way; a higher priority is planned copper; a teardrop (KiCad keeps them
        # as small zones) is copper of its net like a track, and does not make that net a poured one
        for z in sorted((z for z in board.Zones() if not z.GetIsRuleArea()), key=lambda z: -z.GetAssignedPriority()):
            code, tear = z.GetNetCode(), bool(getattr(z, "IsTeardropArea", lambda: False)())
            if not tear:
                self.zone_codes.add(code)
            if (z.GetAssignedPriority() < 1 and not tear) or code <= 0:
                continue
            poly = self._chain(z.Outline().Outline(0))
            for lay in self.cu:
                if z.IsOnLayer(lay):
                    self.paint_poly(self.index[lay], poly, code)
                    if not tear:
                        self._zone_band(self.index[lay], poly)
        if tracks:
            for t in sorted(board.GetTracks(), key=lambda t: (t.GetClass(), t.GetLayer(), t.GetStart().x,
                                                               t.GetStart().y, t.GetEnd().x, t.GetEnd().y)):
                self.paint_item(self.item_of(t))

    # ---- raster helpers ----------------------------------------------------------------------------------------
    @staticmethod
    def _chain(c) -> list:
        return [(B.mm(c.CPoint(j).x), B.mm(c.CPoint(j).y)) for j in range(c.PointCount())]

    @staticmethod
    def _or(arr, masked) -> None:
        ix0, iy0, m = masked
        arr[iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]] |= m

    def cell(self, x: float, y: float) -> tuple:
        return int(round((x - self.x0) / G)), int(round((y - self.y0) / G))

    def xy(self, ix: int, iy: int) -> tuple:
        return round(self.x0 + ix * G, 4), round(self.y0 + iy * G, 4)

    def _window(self, x0, y0, x1, y1):
        ix0, iy0 = max(0, int(math.floor((x0 - self.x0) / G))), max(0, int(math.floor((y0 - self.y0) / G)))
        ix1 = min(self.nx - 1, int(math.ceil((x1 - self.x0) / G)))
        iy1 = min(self.ny - 1, int(math.ceil((y1 - self.y0) / G)))
        return ix0, iy0, self._xs[ix0:ix1 + 1][None, :], self._ys[iy0:iy1 + 1][:, None]

    def poly_mask(self, pts: list, grow: float = 0.0) -> tuple:
        """Grid points inside a polygon: (ix0, iy0, boolean array [iy, ix]). grow: mm of extra window."""
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        ix0, iy0, gx, gy = self._window(min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow)
        inside = np.zeros((gy.shape[0], gx.shape[1]), bool)
        for i in range(len(pts)):
            (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % len(pts)]
            if ya == yb:
                continue
            inside ^= ((ya > gy) != (yb > gy)) & (gx < xa + (gy - ya) * (xb - xa) / (yb - ya))
        return ix0, iy0, inside

    def seg_mask(self, xa, ya, xb, yb, r) -> tuple:
        """Grid points within r of a segment."""
        ix0, iy0, gx, gy = self._window(min(xa, xb) - r, min(ya, yb) - r, max(xa, xb) + r, max(ya, yb) + r)
        dx, dy = xb - xa, yb - ya
        ll = dx * dx + dy * dy
        if ll == 0:
            d2 = (gx - xa) ** 2 + (gy - ya) ** 2
        else:
            t = np.clip(((gx - xa) * dx + (gy - ya) * dy) / ll, 0, 1)
            d2 = (gx - (xa + t * dx)) ** 2 + (gy - (ya + t * dy)) ** 2
        return ix0, iy0, d2 <= r * r + 1e-9

    def code(self, netname: str) -> int:
        return B.net(self.b, netname).GetNetCode()

    def _paint(self, layer: int, masked, code: int, over: bool = False) -> None:
        ix0, iy0, m = masked
        sub = self.own[layer, iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]]
        sub[m if over else m & (sub == 0)] = code

    def paint_poly(self, layer: int, pts: list, code: int) -> None:
        self._paint(layer, self.poly_mask(pts), code)

    def _zone_band(self, layer: int, pts: list, w: float = 0.3) -> None:
        """The fill may stop short of a pour's outline (clearances, corners): no connection ends in that rim."""
        ix0, iy0, m = self.poly_mask(pts, 1.0)
        self.zband[layer, iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]] |= m & dilate(~m, w / G)

    def keep(self, poly: list, layers: list | None = None, tracks: bool = True, vias: bool = True) -> None:
        """A keep-out area: no track may enter it on these layers (indices, default all), no via may enter it.
        The router reads the board's own keep-out areas by itself; this adds one for the router alone."""
        if tracks:
            self.keepouts.append((list(range(self.n_layers)) if layers is None else list(layers), list(poly)))
        if vias:
            self.no_vias.append(list(poly))
        self._keep_masks.clear()

    def _grown(self, polys: list, by: float):
        """The grid points within `by` mm of any of the polygons (grown exactly, then rasterised)."""
        mask = np.zeros((self.ny, self.nx), bool)
        for poly in polys:
            ps = pcbnew.SHAPE_POLY_SET()
            ps.NewOutline()
            for x, y in poly:
                ps.Append(B.iu(x), B.iu(y))
            ps.Inflate(B.iu(by + 0.02), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, B.iu(0.005))
            for i in range(ps.OutlineCount()):
                one = np.zeros(mask.shape, bool)
                self._or(one, self.poly_mask(self._chain(ps.Outline(i))))
                for h in range(ps.HoleCount(i)):
                    ix0, iy0, m = self.poly_mask(self._chain(ps.Hole(i, h)))
                    one[iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]] &= ~m
                mask |= one
        return mask

    def no_track(self, layer: int, width: float):
        """Where the centre of a track of this width may not be on a layer, because of the keep-out areas."""
        key = (layer, round(width * 1000))
        if key not in self._keep_masks:
            self._keep_masks[key] = self._grown([p for lays, p in self.keepouts if layer in lays], width / 2)
        return self._keep_masks[key]

    def no_via(self, via_d: float):
        """Where the centre of a via of this diameter may not be, because of the keep-out areas."""
        key = ("via", round(via_d * 1000))
        if key not in self._keep_masks:
            self._keep_masks[key] = self._grown(self.no_vias, via_d / 2)
        return self._keep_masks[key]

    def _add_pad(self, ref: str, p) -> None:
        code = p.GetNetCode() if p.GetNetCode() > 0 else -1     # a pad without a net is an obstacle
        smd = p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
        cells, layer = [], None
        for lay in self.cu:
            if not p.IsOnLayer(lay):
                continue
            li = self.index[lay]
            layer = li if layer is None else layer
            poly = p.GetEffectivePolygon(lay, pcbnew.ERROR_INSIDE)
            for oi in range(poly.OutlineCount()):
                ix0, iy0, m = masked = self.poly_mask(self._chain(poly.Outline(oi)))
                self._paint(li, masked, code, over=True)
                iys, ixs = np.nonzero(m)
                cells.append((li, np.stack([iys + iy0, ixs + ix0], 1)))
                if smd:
                    self._or(self.smd, masked)
        drill = 0.0
        if p.HasHole():
            drill = B.mm(max(p.GetDrillSize().x, p.GetDrillSize().y))
            self._mark_hole(B.mm(p.GetPosition().x), B.mm(p.GetPosition().y), drill, code)
        c = (B.mm(p.GetPosition().x), B.mm(p.GetPosition().y))
        if code > 0:
            self.names[code] = str(p.GetNetname())
        self.pads.append(_Pad(ref, p.GetNumber(), cells, c, code, smd, layer, drill))

    def _add_text(self, t) -> None:
        if t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and t.IsVisible():
            bb = t.GetBoundingBox()
            self._or(self.silk, self.poly_mask(B.rect(B.mm(bb.GetX()), B.mm(bb.GetY()), B.mm(bb.GetRight()),
                                                      B.mm(bb.GetBottom()))))

    def _mark_hole(self, x, y, drill, code) -> None:
        ix0, iy0, m = masked = self.seg_mask(x, y, x, y, drill / 2)
        self._or(self.hole, masked)
        self.hole_net[iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]][m] = code

    def item_of(self, t) -> tuple:
        """A track or via of the board as a router item."""
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            return ("via", B.mm(p.x), B.mm(p.y), B.mm(t.GetWidth(self.cu[0])), B.mm(t.GetDrillValue()), t.GetNetCode())
        s, e = t.GetStart(), t.GetEnd()
        return ("track", self.index.get(t.GetLayer(), 0), B.mm(s.x), B.mm(s.y), B.mm(e.x), B.mm(e.y),
                B.mm(t.GetWidth()), t.GetNetCode())

    def paint_item(self, it: tuple) -> None:
        if it[0] == "track":
            _, lay, xa, ya, xb, yb, w, code = it
            self._paint(lay, self.seg_mask(xa, ya, xb, yb, w / 2), code)
        else:
            _, x, y, d, drill, code = it
            for lay in range(self.n_layers):                    # a through via: copper on every layer
                self._paint(lay, self.seg_mask(x, y, x, y, d / 2), code)
            self._mark_hole(x, y, drill, code)

    def add(self, items: list) -> None:
        """Items made outside a net's routing (fan-out, stitching, hand copper): painted and kept."""
        for it in items:
            self.paint_item(it)
        if self.base is None:
            self.fixed += items
        else:
            for it in items:
                self.routed.setdefault(it[-1], []).append(it)

    def keep_spokes(self, netname: str, margin: float = 0.6) -> None:
        """Hold a ring of `margin` mm around every through-hole pad of a poured net free of other nets on the
        routing layers, so that the pour's thermal spokes can form (a pad left with one spoke is a rule error)."""
        code = self.code(netname)
        for p in self.pads:
            if p.code == code and p.drill and not p.smd:
                rad = max(max(np.ptp(c[:, 0]), np.ptp(c[:, 1])) + 1 for _, c in p.cells) * G / 2 + margin
                for lay in self.rl:
                    self._paint(lay, self.seg_mask(p.c[0], p.c[1], p.c[0], p.c[1], rad), code)

    # ---- state for rip-up --------------------------------------------------------------------------------------
    def freeze(self) -> None:
        """Everything painted so far (pads, pours, hand copper, fan-out) can never be ripped up."""
        self.base, self.base_hole, self.base_hole_net = self.own.copy(), self.hole.copy(), self.hole_net.copy()

    def rebuild(self) -> None:
        self.own, self.hole, self.hole_net = self.base.copy(), self.base_hole.copy(), self.base_hole_net.copy()
        for code in sorted(self.routed):
            for it in self.routed[code]:
                self.paint_item(it)

    def rip(self, code: int) -> None:
        self.routed.pop(code, None)
        self.rebuild()

    def commit(self) -> int:
        """Write the router's tracks and vias into the board. Call it once, when the routing is finished."""
        n = 0
        for it in self.fixed + [it for code in sorted(self.routed) for it in self.routed[code]]:
            if it in self._written:
                continue
            self._written.add(it)
            if it[0] == "track":
                _, lay, xa, ya, xb, yb, w, code = it
                if abs(xa - xb) < 1e-6 and abs(ya - yb) < 1e-6:
                    continue
                t = pcbnew.PCB_TRACK(self.b)
                t.SetStart(B.pt(xa, ya))
                t.SetEnd(B.pt(xb, yb))
                t.SetWidth(B.iu(w))
                t.SetLayer(self.cu[lay])
            else:
                _, x, y, d, drill, code = it
                t = pcbnew.PCB_VIA(self.b)
                t.SetPosition(B.pt(x, y))
                t.SetViaType(pcbnew.VIATYPE_THROUGH)
                t.SetLayerPair(self.cu[0], self.cu[-1])
                t.SetWidth(B.iu(d))
                t.SetDrill(B.iu(drill))
            t.SetNetCode(code)
            self.b.Add(t)
            n += 1
        return n

    # ---- routing one net ---------------------------------------------------------------------------------------
    def net_pads(self, code: int) -> list:
        return [p for p in self.pads if p.code == code]

    def route_net(self, netname: str, width: float = 0.2, clear: float | None = None, via_d: float | None = None,
                  via_drill: float | None = None, via_cost: float = 25.0, layers: list | None = None,
                  margins: tuple = (3.0, 8.0, 20.0), pins: list | None = None, max_nodes: int = 400_000,
                  soft: bool = False, layer_cost: dict | None = None, avoid: tuple = ()):
        """Connect the pads of one net that are not connected yet. width: track width; clear: clearance to other
        copper; layers: indices of the layers to use (default: the routing layers); margins: how far around the
        two ends the search may go (mm), tried in turn; pins: only these (ref, pin) pads (a wide branch first);
        layer_cost: {layer index: weight} for this net; avoid: rectangles (x0, y0, x1, y1) this net may not
        enter. Returns (items, errors). soft=True finds the cheapest path that may cross ripped-able copper and
        returns (the net codes it crosses, errors) without laying anything."""
        if self.base is None:
            self.freeze()
        o = dict(width=width, clear=self.rules["clearance"] if clear is None else clear,
                 via_d=self.rules["via_d"] if via_d is None else via_d,
                 via_drill=self.rules["via_drill"] if via_drill is None else via_drill, via_cost=via_cost,
                 layers=list(self.rl if layers is None else layers), max_nodes=max_nodes, soft=soft,
                 layer_cost=layer_cost or {}, avoid=avoid)
        code = self.code(netname)
        if soft:
            self.soft_cells, self.soft_paths = [], []
        pads = self.net_pads(code)
        outside = []                                            # pads left out by `pins`, not yet on the net's copper
        if pins is not None:
            want = {(str(r), str(p)) for r, p in pins}
            outside = [p for p in pads if (p.ref, p.pin) not in want and not self._touched(code, p.cells)]
            pads = [p for p in pads if (p.ref, p.pin) in want]
        if not pads or (len(pads) < 2 and pins is None):
            return (set() if soft else []), []
        # pads that touch copper of the net count as connected, but only those on ONE connected piece of it:
        # hand-made stubs at both ends of a net are two pieces that still need a track
        touched = [p for p in pads if self._touched(code, p.cells)]
        self._src = None
        if len(touched) >= 2 and code not in self.zone_codes:
            comp = self.component(code, touched[0].cells)
            grp = [p for p in touched if any(len(c) and comp[lay][c[:, 0], c[:, 1]].any() for lay, c in p.cells)]
            if len(grp) < len(touched):
                touched, self._src = grp, comp
        order = list(touched) if touched else [pads[0]]
        rest = [p for p in pads if p not in order]
        n_start = len(order)
        while rest:
            k = min(range(len(rest)), key=lambda i: min(math.dist(rest[i].c, q.c) for q in order))
            order.append(rest.pop(k))
        items, errs, crossed = [], [], set()
        connected = order[:n_start]
        for idx, p in enumerate(order[n_start:]):
            ok = False
            pending = order[n_start + idx + 1:] + outside
            piece = None                                        # the copper this pad already has (a hand-made stub,
            if self._src is not None:                           # the rest of a net that was cut): reaching any
                piece = self.component(code, p.cells)           # point of it connects the pad
                if (piece & self._src).any():                   # an earlier connection has joined it already
                    connected.append(p)
                    continue
            for m in margins:
                res = self._connect(code, connected, p, o, m, pending, piece)
                if res is None:
                    continue
                if soft:
                    crossed |= res
                    if self._src is not None:                   # nothing is painted in soft mode: the piece joins
                        self._src |= self.component(code, p.cells)
                else:
                    items += res
                    if self._src is not None:
                        self._src = self.component(code, order[0].cells)
                ok = True
                break
            if not ok:
                errs.append(f"{netname}: {p.ref}.{p.pin} not reached")
            connected.append(p)
        self._src = None
        if soft:
            return crossed, errs
        self.routed.setdefault(code, []).extend(items)
        return items, errs

    def component(self, code: int, seeds: list):
        """Cells (layers x ny x nx) of the net's copper that are connected to the seed cells: 4-connected on a
        layer, layers joined at the net's drilled holes (vias and through-hole pads)."""
        m = self.own == code
        full = np.zeros(m.shape, bool)
        ys, xs = np.nonzero(m.any(axis=0))
        if len(ys) == 0:
            return full
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        mm_ = m[:, y0:y1 + 1, x0:x1 + 1]
        link = (self.hole & (self.hole_net == code))[y0:y1 + 1, x0:x1 + 1]
        reach = np.zeros_like(mm_)
        for lay, c in seeds:
            if len(c):
                ok = (c[:, 0] >= y0) & (c[:, 0] <= y1) & (c[:, 1] >= x0) & (c[:, 1] <= x1)
                reach[lay, c[ok, 0] - y0, c[ok, 1] - x0] = True
        reach &= mm_
        while True:
            prev = int(reach.sum())
            for _ in range(30):
                g = reach.copy()
                g[:, 1:, :] |= reach[:, :-1, :]
                g[:, :-1, :] |= reach[:, 1:, :]
                g[:, :, 1:] |= reach[:, :, :-1]
                g[:, :, :-1] |= reach[:, :, 1:]
                reach = g & mm_
            reach |= (reach.any(axis=0) & link)[None] & mm_
            if int(reach.sum()) == prev:
                break
        full[:, y0:y1 + 1, x0:x1 + 1] = reach
        return full

    def _touched(self, code: int, cells: list) -> bool:
        for lay, c in cells:
            if len(c) == 0:
                continue
            ys, xs = c[:, 0], c[:, 1]
            y0, x0 = max(0, ys.min() - 3), max(0, xs.min() - 3)
            y1, x1 = min(self.ny - 1, ys.max() + 3), min(self.nx - 1, xs.max() + 3)
            win = self.own[lay, y0:y1 + 1, x0:x1 + 1]
            pm = np.zeros(win.shape, bool)
            pm[ys - y0, xs - x0] = True
            if np.any(win[dilate(pm, 1.5) & ~pm] == code):
                return True
        return False

    def _via_free(self, code, win, via_d, via_drill, clear, base=False):
        """Where a via of this net may stand inside the window (iy0, iy1, ix0, ix1)."""
        iy0, iy1, ix0, ix1 = win
        own = (self.base if base else self.own)[:, iy0:iy1 + 1, ix0:ix1 + 1]
        hole = (self.base_hole if base else self.hole)[iy0:iy1 + 1, ix0:ix1 + 1]
        vfree = ~dilate(((own != 0) & (own != code)).any(axis=0), (clear + via_d / 2 + RM) / G)
        vfree &= ~dilate(hole, (self.rules["hole_to_hole"] + via_drill / 2 + RM) / G)
        vfree &= ~dilate(self.smd[iy0:iy1 + 1, ix0:ix1 + 1], (via_d / 2 + 0.1) / G)
        vfree &= ~self.no_via(via_d)[iy0:iy1 + 1, ix0:ix1 + 1]
        vfree &= ~dilate(self.silk[iy0:iy1 + 1, ix0:ix1 + 1], (via_d / 2 + self.silk_gap) / G)
        return vfree

    def _connect(self, code, connected, target, o, margin, pending, piece=None, penalty: float = 40.0):
        soft, layers, width = o["soft"], o["layers"], o["width"]
        pts = np.concatenate([c for p in connected for _, c in p.cells] + [c for _, c in target.cells])
        mg = int(margin / G)
        iy0, iy1 = max(0, pts[:, 0].min() - mg), min(self.ny - 1, pts[:, 0].max() + mg)
        ix0, ix1 = max(0, pts[:, 1].min() - mg), min(self.nx - 1, pts[:, 1].max() + mg)
        h, w = iy1 - iy0 + 1, ix1 - ix0 + 1
        win = (slice(iy0, iy1 + 1), slice(ix0, ix1 + 1))
        r = (o["clear"] + width / 2 + RM) / G
        hn = self.hole_net[win]
        holes = dilate((hn != 0) & (hn != code), (self.rules["hole_clearance"] + width / 2 + 0.05) / G)
        free, softm = {}, {}
        for lay in layers:
            other = (self.own[lay][win] != 0) & (self.own[lay][win] != code)
            if soft:
                base = self.base[lay][win]
                free[lay] = ~(dilate((base != 0) & (base != code), r) | holes)
                softm[lay] = dilate(other, r) & free[lay]
            else:
                free[lay] = ~dilate(other, r) & ~holes
            free[lay] &= ~self.no_track(lay, width)[win]
        for (ax0, ay0, ax1, ay1) in o["avoid"]:
            (cx0, cy0), (cx1, cy1) = self.cell(ax0, ay0), self.cell(ax1, ay1)
            ya, yb, xa, xb = max(cy0 - iy0, 0), min(cy1 - iy0 + 1, h), max(cx0 - ix0, 0), min(cx1 - ix0 + 1, w)
            if ya < yb and xa < xb:
                for lay in layers:
                    free[lay][ya:yb, xa:xb] = False
        vfree = self._via_free(code, (iy0, iy1, ix0, ix1), o["via_d"], o["via_drill"], o["clear"], base=soft)
        vsoft = None
        # a point right beside other copper costs a little more: tracks then run straight past a round obstacle
        # instead of following its raster outline in small steps
        wt = {lay: self.weight[lay][win] * o["layer_cost"].get(lay, 1.0) + 0.5 * (dilate(~free[lay], 1.5) & free[lay])
              for lay in layers}
        if soft:
            for lay in layers:
                wt[lay] = wt[lay] + softm[lay] * penalty
            # a via on or near ripped-able copper costs the penalty too, and counts as crossing it
            vsoft = ~self._via_free(code, (iy0, iy1, ix0, ix1), o["via_d"], o["via_drill"], o["clear"])
        tmask = np.zeros((self.n_layers, h, w), bool)           # the target and the pads still to come: no sources
        for p in [target] + list(pending):
            for lay, c in p.cells:
                yy, xx = c[:, 0] - iy0, c[:, 1] - ix0
                ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
                tmask[lay, yy[ok], xx[ok]] = True
        src = set()
        for lay in layers:
            cand = (self.own[lay][win] == code) & free[lay] & ~tmask[lay] & ~self.zband[lay][win]
            if self._src is not None:
                cand &= self._src[lay][win]
            ys, xs = np.nonzero(cand)
            src.update(zip([lay] * len(ys), ys.tolist(), xs.tolist()))
        tgt = set()
        for lay, c in target.cells:
            if lay in free:
                for yy, xx in c.tolist():
                    yy, xx = yy - iy0, xx - ix0
                    if 0 <= yy < h and 0 <= xx < w and free[lay][yy, xx]:
                        tgt.add((lay, yy, xx))
        if piece is not None:                                   # ... or any free point of the copper it already has
            for lay in layers:
                ys, xs = np.nonzero(piece[lay][win] & free[lay] & ~self.zband[lay][win])
                tgt.update(zip([lay] * len(ys), ys.tolist(), xs.tolist()))
        if not tgt:                                             # a tiny pad between close neighbours: its centre
            cx, cy = self.cell(*target.c)
            tgt.update((lay, cy - iy0, cx - ix0) for lay, _ in target.cells if lay in free)
        if not src:                                             # the first pad has no free cell: the pad centres
            for p in connected:
                cx, cy = self.cell(*p.c)
                src.update((lay, cy - iy0, cx - ix0) for lay, _ in p.cells if lay in free)
        src -= tgt
        if not src or not tgt:
            return None
        tys, txs = [t[1] for t in tgt], [t[2] for t in tgt]
        ty0, ty1, tx0, tx1 = min(tys), max(tys), min(txs), max(txs)
        minw = min(float(wt[lay].min()) for lay in layers)

        def hfun(y, x):
            dy = 0 if ty0 <= y <= ty1 else (ty0 - y if y < ty0 else y - ty1)
            dx = 0 if tx0 <= x <= tx1 else (tx0 - x if x < tx0 else x - tx1)
            a, b = (dx, dy) if dx > dy else (dy, dx)
            return (a + 0.4142 * b) * minw

        gscore, came, heap = {}, {}, []
        for s in sorted(src):
            gscore[s] = 0.0
            heapq.heappush(heap, (hfun(s[1], s[2]), 0.0, s))
        found, nodes = None, 0
        via_cost, many = o["via_cost"], len(layers) > 1
        while heap:
            _, g, s = heapq.heappop(heap)
            if g > gscore.get(s, 1e18):
                continue
            if s in tgt:
                found = s
                break
            nodes += 1
            if nodes > o["max_nodes"]:
                break
            lay, y, x = s
            fr, wl = free[lay], wt[lay]
            for dx, dy, c in DIRS:
                ny_, nx_ = y + dy, x + dx
                if 0 <= ny_ < h and 0 <= nx_ < w and fr[ny_, nx_]:
                    if dx and dy and not (fr[y, nx_] or fr[ny_, x]):
                        continue
                    ns = (lay, ny_, nx_)
                    ng = g + c * 0.5 * (wl[y, x] + wl[ny_, nx_])
                    if ng < gscore.get(ns, 1e18):
                        gscore[ns], came[ns] = ng, s
                        heapq.heappush(heap, (ng + hfun(ny_, nx_), ng, ns))
            if many and vfree[y, x]:
                for l2 in layers:
                    if l2 != lay and free[l2][y, x]:
                        ns = (l2, y, x)
                        ng = g + via_cost + (penalty if vsoft is not None and vsoft[y, x] else 0.0)
                        if ng < gscore.get(ns, 1e18):
                            gscore[ns], came[ns] = ng, s
                            heapq.heappush(heap, (ng + hfun(y, x), ng, ns))
        if found is None:
            return None
        path = [found]
        while path[-1] in came:
            path.append(came[path[-1]])
        path.reverse()
        if soft:
            return self._crossed(code, path, softm, vsoft, r, o, iy0, ix0)
        path = [(lay, int(y + iy0), int(x + ix0)) for lay, y, x in path]
        return self._emit(code, path, width, o["via_d"], o["via_drill"], {lay: (free[lay], iy0, ix0) for lay in layers})

    def _crossed(self, code, path, softm, vsoft, r, o, iy0, ix0) -> set:
        """The nets whose ripped-able copper a soft path runs through."""
        crossed = set()

        def rippable(a, b, ya, xa, lay):
            win = self.own[lay, ya:a, xa:b]
            bwin = self.base[lay, ya:a, xa:b]
            return np.unique(win[(win > 0) & (win != code) & (bwin == 0)]).tolist()
        rr = int(math.ceil(r)) + 1
        for lay, y, x in path:
            if softm[lay][y, x]:
                crossed.update(rippable(y + iy0 + rr + 1, x + ix0 + rr + 1, max(0, y + iy0 - rr), max(0, x + ix0 - rr), lay))
        rv2 = int(math.ceil(max((o["clear"] + o["via_d"] / 2 + RM) / G,
                                (self.rules["hole_to_hole"] + o["via_drill"] / 2 + RM) / G))) + 1
        for (l1, y1, x1), (l2, _, _) in zip(path, path[1:]):
            if l1 != l2 and vsoft[y1, x1]:                      # a via here: what it sits on is ripped too
                ya, xa = max(0, y1 + iy0 - rv2), max(0, x1 + ix0 - rv2)
                for lay in range(self.n_layers):
                    crossed.update(rippable(y1 + iy0 + rv2 + 1, x1 + ix0 + rv2 + 1, ya, xa, lay))
                hwin = self.hole_net[ya:y1 + iy0 + rv2 + 1, xa:x1 + ix0 + rv2 + 1]
                hb = self.base_hole[ya:y1 + iy0 + rv2 + 1, xa:x1 + ix0 + rv2 + 1]
                crossed.update(np.unique(hwin[(hwin > 0) & (hwin != code) & ~hb]).tolist())
        cells = [(lay, y + iy0, x + ix0) for lay, y, x in path]
        self.soft_cells += cells
        self.soft_paths.append(cells)
        return crossed

    @staticmethod
    def _line_free(a, b, free_full) -> bool:
        fr, iy0, ix0 = free_full
        (y0, x0), (y1, x1) = a, b
        n = max(abs(y1 - y0), abs(x1 - x0))
        for i in range(n + 1):
            yy = y0 + round((y1 - y0) * i / n) - iy0 if n else y0 - iy0
            xx = x0 + round((x1 - x0) * i / n) - ix0 if n else x0 - ix0
            if not (0 <= yy < fr.shape[0] and 0 <= xx < fr.shape[1]) or not fr[yy, xx]:
                return False
        return True

    def _one_bend(self, pts: list, ff) -> list:
        """Corner points with stair steps taken out: from each corner, the farthest later corner that one straight
        and one diagonal leg (in either order) reach through free points replaces everything between."""
        out, i = [pts[0]], 0
        while i < len(pts) - 1:
            hit = None
            for j in range(len(pts) - 1, i + 1, -1):
                (y0, x0), (y1, x1) = pts[i], pts[j]
                dy, dx = int(y1 - y0), int(x1 - x0)
                s, sy, sx = min(abs(dy), abs(dx)), (dy > 0) - (dy < 0), (dx > 0) - (dx < 0)
                for c in ((y0 + s * sy, x0 + s * sx), (y1 - s * sy, x1 - s * sx)):
                    if self._line_free(pts[i], c, ff) and self._line_free(c, pts[j], ff):
                        hit = (j, c)
                        break
                if hit:
                    break
            if hit:
                if hit[1] not in (pts[i], pts[hit[0]]):
                    out.append(hit[1])
                out.append(pts[hit[0]])
                i = hit[0]
            else:
                out.append(pts[i + 1])
                i += 1
        return out

    def _emit(self, code, path, width, via_d, via_drill, free_full) -> list:
        """A cell path as tracks and vias: runs per layer, stair steps replaced by straight 0/45/90 lines."""
        runs, vias, cur = [], [], [path[0]]
        for p in path[1:]:
            if p[0] != cur[-1][0]:
                runs.append(cur)
                vias.append((p[1], p[2]))
                cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        items = []
        for run in runs:
            lay = run[0][0]
            pts = [(p[1], p[2]) for p in run]
            simp, i = [pts[0]], 0
            while i < len(pts) - 1:                             # from i, jump to the farthest j on a free line
                j = len(pts) - 1
                while j > i + 1:
                    dy, dx = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
                    if (dy == 0 or dx == 0 or abs(dy) == abs(dx)) and self._line_free(pts[i], pts[j], free_full[lay]):
                        break
                    j -= 1
                simp.append(pts[j])
                i = j
            simp = self._one_bend(simp, free_full[lay])
            for a, b in zip(simp, simp[1:]):
                it = ("track", lay, *self.xy(a[1], a[0]), *self.xy(b[1], b[0]), width, code)
                items.append(it)
                self.paint_item(it)
        for (y, x) in vias:
            it = ("via", *self.xy(x, y), via_d, via_drill, code)
            items.append(it)
            self.paint_item(it)
        return items

    # ---- a via beside every SMD pad of a poured net (ground) ---------------------------------------------------
    def fanout(self, netname: str, width: float = 0.3, clear: float | None = None, via_d: float | None = None,
               via_drill: float | None = None, rmax: float = 1.5, skip: tuple = ()) -> list:
        """Give every SMD pad of the net its own via within rmax mm, joined by a short track on the pad's layer.
        Call it before the routing (the pads then keep their return path) and again after it for the pads that
        found no room the first time. skip: (ref, pin) pads that get their via by hand. Returns the pads that
        are still without a via, as text."""
        code = self.code(netname)
        clear = self.rules["clearance"] if clear is None else clear
        via_d = self.rules["via_d"] if via_d is None else via_d
        via_drill = self.rules["via_drill"] if via_drill is None else via_drill
        errs = []
        for k, p in enumerate(self.pads):
            if p.code != code or not p.smd or (p.ref, p.pin) in skip or k in self.fanned:
                continue
            res = self._fanout_one(code, p, width, clear, via_d, via_drill, rmax)
            if res is None:
                errs.append(f"{netname}: no fan-out via for {p.ref}.{p.pin}")
            else:
                self.fanned.add(k)
                self.add(res)
        return errs

    def _fanout_one(self, code, p, width, clear, via_d, via_drill, rmax):
        cx, cy = p.c
        (ix0, iy0), (ix1, iy1) = self.cell(cx - rmax - 1, cy - rmax - 1), self.cell(cx + rmax + 1, cy + rmax + 1)
        ix0, iy0, ix1, iy1 = max(ix0, 0), max(iy0, 0), min(ix1, self.nx - 1), min(iy1, self.ny - 1)
        vfree = self._via_free(code, (iy0, iy1, ix0, ix1), via_d, via_drill, clear)
        own = self.own[p.layer, iy0:iy1 + 1, ix0:ix1 + 1]
        hn = self.hole_net[iy0:iy1 + 1, ix0:ix1 + 1]
        tfree = ~dilate((own != 0) & (own != code), (clear + width / 2 + RM) / G) & \
            ~dilate((hn != 0) & (hn != code), (self.rules["hole_clearance"] + width / 2 + 0.05) / G)
        tfree &= ~self.no_track(p.layer, width)[iy0:iy1 + 1, ix0:ix1 + 1]
        pc = np.concatenate([c for lay, c in p.cells if lay == p.layer])
        ys, xs = np.nonzero(vfree)
        cand = sorted((math.hypot(self.x0 + (xx + ix0) * G - cx, self.y0 + (yy + iy0) * G - cy), yy + iy0, xx + ix0)
                      for yy, xx in zip(ys.tolist(), xs.tolist()))
        ff = (tfree, iy0, ix0)
        for d, vy, vx in cand[:400]:
            if d > rmax:
                break
            k = np.argmin((pc[:, 0] - vy) ** 2 + (pc[:, 1] - vx) ** 2)      # the pad cell nearest to the via
            py, px = int(pc[k, 0]), int(pc[k, 1])
            dy, dx = vy - py, vx - px
            if dy == 0 or dx == 0 or abs(dy) == abs(dx):
                pts = [(py, px), (vy, vx)]
            else:                                               # a diagonal, then a straight piece
                s = min(abs(dy), abs(dx))
                pts = [(py, px), (py + s * (1 if dy > 0 else -1), px + s * (1 if dx > 0 else -1)), (vy, vx)]
            if not all(self._line_free(a, b, ff) for a, b in zip(pts, pts[1:])):
                continue
            items = [("track", p.layer, *self.xy(a[1], a[0]), *self.xy(b[1], b[0]), width, code)
                     for a, b in zip(pts, pts[1:]) if a != b]
            return items + [("via", *self.xy(vx, vy), via_d, via_drill, code)]
        return None

    def via_spots(self, netname: str, pitch: float, region: list | None = None, inside_pour: bool = False,
                  via_d: float | None = None, via_drill: float | None = None, gap: float = 0.2) -> list:
        """Vias of a net on a grid of `pitch` mm wherever every layer is free of other nets (stitching), inside
        `region` (a polygon, default the whole board). inside_pour: only where the first routing layer already
        is this net (vias that tie a planned pour to its copy on another layer). Returns the items; they are
        painted and kept like a fan-out."""
        code = self.code(netname)
        via_d = self.rules["via_d"] if via_d is None else via_d
        via_drill = self.rules["via_drill"] if via_drill is None else via_drill
        ok = self._via_free(code, (0, self.ny - 1, 0, self.nx - 1), via_d, via_drill, gap)
        if inside_pour:
            ok &= self.own[self.rl[0]] == code
        if region is not None:
            ix0, iy0, m = self.poly_mask(region)
            inside = np.zeros(ok.shape, bool)
            inside[iy0:iy0 + m.shape[0], ix0:ix0 + m.shape[1]] = m
            ok &= ~dilate(~inside, (via_d / 2 + 0.1) / G)
        xs = [p[0] for p in region] if region else [self.x0, self.x0 + self.nx * G]
        ys = [p[1] for p in region] if region else [self.y0, self.y0 + self.ny * G]
        items = []
        y = min(ys) + pitch / 2
        while y < max(ys):
            x = min(xs) + pitch / 2
            while x < max(xs):
                ix, iy = self.cell(x, y)
                if 0 <= ix < self.nx and 0 <= iy < self.ny and ok[iy, ix]:
                    it = ("via", *self.xy(ix, iy), via_d, via_drill, code)
                    items.append(it)
                    jx0, jy0, m = self.seg_mask(it[1], it[2], it[1], it[2], via_d + self.rules["hole_to_hole"])
                    ok[jy0:jy0 + m.shape[0], jx0:jx0 + m.shape[1]][m] = False
                x += pitch
            y += pitch
        self.add(items)
        return items


# ---- the route order ---------------------------------------------------------------------------------------------------
def make_plan(router: Router, classes: list | None = None, default: dict | None = None, long_span: float = 30.0,
              long_layer_cost: dict | None = None, skip: tuple = ()) -> list:
    """The route order as a list of (net name, options of Router.route_net).

    classes: routed first, in this order: dicts with "nets" (names or patterns, with or without the sheet path)
             and any option of route_net (width, clear, pins, layer_cost, avoid, ...). Put the wide power nets
             first, then the few nets that must cross the board before others close their way.
    default: options of every other net (default width 0.2 mm).
    Then come the long nets (pads more than long_span mm apart, longest first, with long_layer_cost when given:
    {layer index: weight}, to send them to the far side), then the short ones, shortest first.
    Nets with a zone (joined by their pour), nets with fewer than two pads, and `skip` are left out."""
    default = dict({"width": 0.2}, **(default or {}))
    todo = {c: n for c, n in router.names.items() if c not in router.zone_codes and len(router.net_pads(c)) >= 2
            and not any(fnmatch.fnmatchcase(n, s) or fnmatch.fnmatchcase(kicad_io.leaf(n), s) for s in skip)}
    plan = []
    for cls in classes or []:
        opts = {k: v for k, v in cls.items() if k != "nets"}
        for pat in cls["nets"]:
            for c in sorted(todo, key=lambda c: todo[c]):
                if fnmatch.fnmatchcase(todo[c], pat) or fnmatch.fnmatchcase(kicad_io.leaf(todo[c]), pat):
                    plan.append((todo[c], opts))
                    if "pins" not in opts:                      # a branch: the rest of the net comes later
                        del todo[c]
    rest = []
    for c, n in todo.items():
        pads = router.net_pads(c)
        rest.append((max(abs(a.c[0] - b.c[0]) + abs(a.c[1] - b.c[1]) for a in pads for b in pads), n))
    longs = sorted((x for x in rest if x[0] >= long_span), reverse=True)
    shorts = sorted(x for x in rest if x[0] < long_span)
    plan += [(n, dict(default, layer_cost=long_layer_cost) if long_layer_cost else default) for _, n in longs]
    plan += [(n, default) for _, n in shorts]
    return plan


def route_all(router: Router, plan: list, log=print, passes: int = 5, protect: tuple = ()) -> dict:
    """Route every entry of the plan, then rip up and retry around the failures: for each open net, find the
    cheapest path that may cross routed copper, rip the nets it crosses, route this net, then the ripped ones
    again; keep the result only when fewer nets are open than before. protect: nets that are never ripped.
    Returns {net name: [what is still open]}; an empty dict means every net of the plan is connected."""
    fails = {}
    for name, kw in plan:
        _, e = router.route_net(name, **kw)
        if e:
            fails[name] = e
        else:
            fails.pop(name, None)
    log(f"first pass: {len(fails)} of {len({n for n, _ in plan})} nets with open connections: {sorted(fails)}")
    params: dict = {}
    for n, kw in plan:                                          # a net may have several entries (branches first)
        params.setdefault(n, []).append(kw)
    code2name = {router.code(n): n for n in params}
    keep = {router.code(n) for n in protect}

    def reroute(n):
        errs = []
        for kw in params[n]:
            _, errs = router.route_net(n, **kw)                 # the last entry covers every pin
        return errs
    for k in range(passes):
        if not fails:
            break
        improved = False
        for name in list(fails):
            if name not in fails:
                continue
            snap = {c: list(v) for c, v in router.routed.items()}
            code = router.code(name)
            router.rip(code)
            last = {kk: v for kk, v in params[name][-1].items() if kk not in ("margins", "pins")}
            crossed, _ = router.route_net(name, soft=True, margins=(4.0, 12.0, 30.0), **last)
            victims = [code2name[c] for c in sorted(crossed) if c in code2name and c not in keep and c != code]
            for v in victims:
                router.routed.pop(router.code(v), None)
            router.rebuild()
            newf = {n: e for n in [name] + victims for e in [reroute(n)] if e}
            if len(newf) < len([n for n in [name] + victims if n in fails]):
                for n in [name] + victims:
                    fails.pop(n, None)
                fails.update(newf)
                improved = True
            else:
                router.routed = snap
                router.rebuild()
        log(f"rip-up pass {k + 1}: {len(fails)} nets with open connections: {sorted(fails)}")
        if not improved:
            break
    return fails
