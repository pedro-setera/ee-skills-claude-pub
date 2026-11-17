"""Hand-planned copper from a description: zones, tracks, vias, keep-out areas, stitching vias.

What it does (a library for a project's src/build_board.py)
    apply(board, plan)       lays everything a description names, in this order: keep-outs, zones, tracks, vias
    zone(), track(), via(), keepout()      the same, one item at a time
    stitch(router, "GND", pitch)           vias of a net on a grid wherever every layer is free (after routing)

    The description is plain data, so the planned copper of a board is one table that can be read and reviewed:
        {"keepouts": [{"rect": [x0, y0, x1, y1], "layers": ["B.Cu"], "no": ["tracks"], "name": "under L1"}],
         "zones":    [{"net": "GND", "layer": "B.Cu"},                         the whole board: a fill
                      {"net": "+5V", "layer": "F.Cu", "polygon": [[x, y], ...], "priority": 1}],
         "tracks":   [{"net": "VBUS", "layer": "F.Cu", "width": 0.5, "points": [[x, y], ...]}],
         "vias":     [{"net": "GND", "at": [x, y], "d": 0.6, "drill": 0.3}]}
    Coordinates in mm, KiCad's frame (x right, y down). A net is named in full or without its sheet path.
    A zone without a polygon covers the board, drawn inside the edge clearance. Priority 0 (the default) is a
    fill that gives way: the router crosses it and KiCad cuts it back. Priority 1 or more is planned copper: the
    router goes around it. Tracks and vias laid here are locked: repair.py never rips locked copper.

Why it exists
    The copper that decides whether a board works is planned, not searched: the pours and the hot loop of a
    converter as its datasheet draws them, the escapes of fine-pitch pins, a feed that must not close the last
    gap of a long net, the keep-out under an inductor. On one board a wide feed laid by the router closed the
    last millimetre of a long net; drawn by hand on its own path, it never did again.

Where it stops
    It draws what it is told: no check of a width against a current, of a loop area or of a return path (the
    current worksheet and the reviews do that). Zones are outlines until fill.py fills them. Straight segments
    only: no arcs, no teardrops.

board.toml keys: none. A library: no exit codes; what cannot be done raises kicad_io.KicadIOError.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

if __name__ == "__main__":                      # a library: there is nothing to run
    print(__doc__)
    sys.exit(0)

import pcbnew  # noqa: E402

import kicad_io  # noqa: E402
from layout import board as B  # noqa: E402

keepout = B.rule_area               # keepout(board, polygon, layers, tracks=, vias=, pour=, footprints=, name=)
_CONNECT = {"solid": pcbnew.ZONE_CONNECTION_FULL, "thermal": pcbnew.ZONE_CONNECTION_THERMAL,
            "tht_thermal": pcbnew.ZONE_CONNECTION_THT_THERMAL}


def board_polygon(board, inset: float) -> list:
    """The board outline moved `inset` mm inwards (corners chamfered), as a list of points."""
    ps = B.board_outline(board)
    if ps is None:
        raise kicad_io.KicadIOError("the board outline on Edge.Cuts is not one closed shape")
    ps.Deflate(B.iu(inset), pcbnew.CORNER_STRATEGY_CHAMFER_ALL_CORNERS, B.iu(0.005))
    if ps.OutlineCount() == 0:
        raise kicad_io.KicadIOError(f"nothing is left of the board outline {inset} mm inside its edge")
    o = ps.Outline(0)
    return [(B.mm(o.CPoint(i).x), B.mm(o.CPoint(i).y)) for i in range(o.PointCount())]


def zone(board, net: str, layer, polygon: list | None = None, *, priority: int = 0, clearance: float = 0.2,
         min_width: float = 0.25, connect: str = "tht_thermal", inset: float | None = None, name: str = ""):
    """A copper zone (an outline; fill.py fills it). polygon None: the whole board, `inset` mm inside the edge
    (default: the board's copper-to-edge minimum). connect: how pads of the net join it: "tht_thermal" (SMD pads
    solid, through-hole pads through spokes), "solid" (power pours), "thermal"."""
    if polygon is None:
        edge = B.mm(board.GetDesignSettings().m_CopperEdgeClearance)
        polygon = board_polygon(board, edge if inset is None else inset)
    z = pcbnew.ZONE(board)
    z.SetLayer(B.layer_id(board, layer))
    z.SetNet(B.net(board, net))
    o = z.Outline()
    o.NewOutline()
    for x, y in polygon:
        o.Append(B.iu(x), B.iu(y))
    z.SetAssignedPriority(priority)
    z.SetPadConnection(_CONNECT[connect])
    z.SetMinThickness(B.iu(min_width))
    z.SetLocalClearance(B.iu(clearance))
    z.SetThermalReliefGap(B.iu(0.3))
    z.SetThermalReliefSpokeWidth(B.iu(0.5))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName(name or f"{kicad_io.leaf(net)} {board.GetLayerName(B.layer_id(board, layer))}")
    board.Add(z)
    return z


def track(board, net: str, layer, width: float, points: list, locked: bool = True) -> list:
    """Straight track segments through the points."""
    out = []
    ni, lay = B.net(board, net), B.layer_id(board, layer)
    for (xa, ya), (xb, yb) in zip(points, points[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(B.pt(xa, ya))
        t.SetEnd(B.pt(xb, yb))
        t.SetWidth(B.iu(width))
        t.SetLayer(lay)
        t.SetNet(ni)
        t.SetLocked(locked)
        board.Add(t)
        out.append(t)
    return out


def via(board, net: str, x: float, y: float, d: float = 0.6, drill: float = 0.3, locked: bool = True):
    """A through via."""
    cu = B.copper_layers(board)
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(B.pt(x, y))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(cu[0], cu[-1])
    v.SetWidth(B.iu(d))
    v.SetDrill(B.iu(drill))
    v.SetNet(B.net(board, net))
    v.SetLocked(locked)
    board.Add(v)
    return v


def apply(board, plan: dict) -> dict:
    """Lay the copper of a description (see the head of this file). Returns the counts."""
    for k in plan.get("keepouts", []):
        poly = B.rect(*k["rect"]) if k.get("rect") else [tuple(p) for p in k["polygon"]]
        no = set(k.get("no", ("tracks", "vias", "pour")))
        keepout(board, poly, k.get("layers"), tracks="tracks" in no, vias="vias" in no, pour="pour" in no,
                footprints="parts" in no, name=k.get("name", ""))
    for z in plan.get("zones", []):
        opts = {k: v for k, v in z.items() if k in ("priority", "clearance", "min_width", "connect", "inset", "name")}
        zone(board, z["net"], z["layer"], [tuple(p) for p in z["polygon"]] if z.get("polygon") else None, **opts)
    for t in plan.get("tracks", []):
        track(board, t["net"], t["layer"], t["width"], [tuple(p) for p in t["points"]])
    for v in plan.get("vias", []):
        via(board, v["net"], v["at"][0], v["at"][1], v.get("d", 0.6), v.get("drill", 0.3))
    return {k: len(plan.get(k, [])) for k in ("keepouts", "zones", "tracks", "vias")}


def stitch(router, net: str, pitch: float = 2.5, region: list | None = None, inside_pour: bool = False, **kw) -> int:
    """Stitching vias of a net on a grid of `pitch` mm wherever every copper layer is free of other nets, clear
    of pads, holes, keep-outs and silkscreen texts (router: a layout.route.Router that has read the board and
    its routing). region: a polygon, default the whole board. inside_pour: only inside a planned pour of the
    net (vias that tie it to its copy on another layer). The vias are written by router.commit(). Returns how
    many were laid. Stitch after the routing and before the fill; fill.py then shows what they tie together."""
    return len(router.via_spots(net, pitch, region, inside_pour, **kw))
