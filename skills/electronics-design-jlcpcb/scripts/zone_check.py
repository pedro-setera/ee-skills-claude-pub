"""Ground pour check on the SAVED zone fill: islands, vias per island, webs between holes, stitching, single point.

What it checks (experimental: lighter tests than the other checks)
    islands       every piece of filled ground copper on every layer: its area, the vias and through-hole pads of
                  its net that tie it to the other layers, the surface pads it holds. While the net has copper
                  on another layer: a piece with no pad and no via (an orphan), or with no via and no through-hole
                  pad at all, is a finding at any size; a piece with ties, but fewer than min_vias, is a finding
                  when its longest extent is island_one_tie_max_mm or more, and a listed note when it is shorter.
    webs          on plane layers: the copper left between the clearances of two neighbouring holes (vias, pins)
                  of other nets, measured on the fill along the line between the two holes (a hole of the plane's
                  own net is part of the plane and makes no clearance). Holes whose webs are under the zone's
                  minimum width form one opening in the plane. Two holes with an opening shorter than
                  web_pair_max_mm are a listed note (no track passes between them anyway); three or more holes
                  in a row, or a longer opening, are a finding: a slot under every signal that crosses it.
                  Plane layers: the inner layers where a ground zone covers 70 % of the board; an outer layer
                  only when board.toml names it (planes = [...]). When NO layer is judged as a plane (the usual
                  2-layer board without that key) the web check is UNKNOWN, which is not a pass: name the ground
                  side in planes. An outer layer with a pour that is not named, on a board that has inner planes,
                  is only said to be not judged.
    near          a ground via within a given distance of named pads (an RF entry, a decoupling pad)
    fence         the count of vias beside the tracks of named nets, against the planned count
    stitching     (RF boards, optional) the largest distance from any point of a ground pour on an outer layer to
                  its nearest ground via, against grid / sqrt(2): the farthest point of a square grid of that pitch
    single point  (optional) in a COPY the named bridge is closed with a no-pour rectangle and the zones are
                  refilled in a separate process; the named pads must then be separate from the rest of the net.
                  If they are still joined, the island has a second tie.

Why it exists (real failures, told without names)
    A refill after a clearance change removed stitching vias' copper and left islands tied by one small via. A
    row of via clearances merged into a slot in the ground plane under a signal. An island that was meant to
    join the ground at one point had a second tie. The rule check counts none of these: it only says whether
    the copper is connected.

Usage
    python -I zone_check.py --project <hardware/board folder>          result in <project>/out/zone_check.md
    python -I zone_check.py <board.kicad_pcb> --out <folder> [--stitch-grid MM]
    The board is read from a private copy; the saved fill is judged as it is (no refill), except in the copy of
    the single-point test.

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [zone]
    nets = ["GND"]             # the ground nets (default: every net whose name ends in GND, GNDA, GNDD, VSS or is "0")
    min_vias = 2
    island_one_tie_max_mm = 5.0   # a piece with fewer ties than min_vias: a finding from this length, listed below it
    min_web = 0.25             # mm (default: the smallest minimum width of the zones on that layer)
    web_reach = 3.0            # mm: holes farther apart are not neighbours
    web_pair_max_mm = 2.5      # two holes whose clearances join: listed when the opening is shorter than this
    planes = ["B.Cu"]          # outer layers that are reference planes (default: none; inner layers are found by
                               # the share of the board that a ground zone covers on them)
    plane_layers = ["In1.Cu"]  # instead of both: the complete list of the layers that are checked for webs
    sample = 0.25              # mm: sampling step of the stitching report
    [zone.stitching]
    grid = 3.3                 # mm (about lambda_g / 20 at the highest RF frequency); layers = ["F.Cu", "B.Cu"]
    [[zone.near]]
    pad = "J1.1"   max = 1.0   # a ground via within max mm of this pad's centre
    [[zone.fence]]
    nets = ["/RF_LINE*"]   within = 1.5   planned = 8   # vias within 1.5 mm of these nets' tracks; planned is optional
    [[zone.single_point]]
    name = "quiet ground island"
    layer = "In1.Cu"
    close = [20.0, 30.0, 21.0, 30.5]                    # rectangle over the bridge, KiCad frame (mm)
    pads = ["U1.5", "R4.2"]                             # pads that must come apart from the rest
    rest = "J1.2"                                       # a pad of the rest of the net

Exit codes
    0  PASS; 1  FAIL: any finding; 2  CANNOT RUN: KiCad's Python not found, unreadable board, a pad or layer of
    board.toml that is not on the board. A board without any ground zone: exit 1, "no ground zone found" (UNKNOWN).
    A board on which no layer is judged as a plane: exit 1, the web check is UNKNOWN (see webs above).

Not checked: whether the fill is up to date with the zone outlines (refill and save, then run this); thermal
spokes; a row of stitching vias along the board edges and around RF sections (look at the copper plots); the
return path of any single signal.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402

DEFAULTS = {"min_vias": 2, "island_one_tie_max_mm": 5.0, "min_web": -1.0, "web_reach": 3.0, "web_pair_max_mm": 2.5,
            "sample": 0.25}
GND_NAME = re.compile(r"(^|/)(A|D|P|S|R)?(GND|VSS)(A|D|P|S|\d|_\w+)?$|^0$", re.I)
MAX_LISTED = 60
FLANK = 2.0                         # mm to each side of a gap between two holes that must hold plane copper
PLANE_SHARE = 0.7                   # a layer whose ground fill covers this share of the board is taken as a plane
NO_PLANE = "no plane layer is judged: on a 2-layer board name the ground side in `planes`"
REFILL_TIMEOUT = 1800.0


def _pt_seg(px, py, ax, ay, bx, by):
    return pcb_common.pt_seg(px, py, ax, ay, bx, by)


class Board:
    def __init__(self, board):
        import pcbnew
        self.p, self.b = pcbnew, board
        self.mm = pcbnew.ToMM
        self.cu = list(board.GetEnabledLayers().CuStack())
        self.name = {lid: board.GetLayerName(lid) for lid in self.cu}
        self.vias, self.pads = [], []
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                q = t.GetPosition()
                self.vias.append({"x": self.mm(q.x), "y": self.mm(q.y), "pos": q, "net": str(t.GetNetname()),
                                  "drill": self.mm(t.GetDrill()), "d": self.mm(t.GetWidth(pcbnew.F_Cu)),
                                  "layers": {lid for lid in self.cu if t.IsOnLayer(lid)}})
        for f in board.GetFootprints():
            for pad in f.Pads():
                q = pad.GetPosition()
                self.pads.append({"ref": f.GetReference(), "num": str(pad.GetNumber()), "x": self.mm(q.x), "y": self.mm(q.y),
                                  "pos": q, "net": str(pad.GetNetname()), "hole": bool(pad.HasHole()),
                                  "drill": self.mm(pad.GetDrillSize().x) if pad.HasHole() else 0.0,
                                  "plated": pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
                                  "layers": {lid for lid in self.cu if pad.IsOnLayer(lid)}, "obj": pad})

    def layer(self, name):
        for lid, n in self.name.items():
            if n == name or str(self.p.LayerName(lid)) == name:
                return lid
        raise kicad_io.KicadIOError(f"board.toml names the layer '{name}'; the board has {', '.join(self.name.values())}")

    def pad(self, spec):
        ref, _, num = spec.partition(".")
        for p in self.pads:
            if p["ref"] == ref and p["num"] == num:
                return p
        raise kicad_io.KicadIOError(f"board.toml names the pad '{spec}', which is not on the board")

    def fill(self, net, lid):
        """The merged filled copper of a net's zones on one layer (SHAPE_POLY_SET) and the zones' smallest minimum width."""
        acc, minw, n = self.p.SHAPE_POLY_SET(), None, 0
        for z in self.b.Zones():
            if z.GetIsRuleArea() or str(z.GetNetname()) != net or not z.IsOnLayer(lid):
                continue
            n += 1
            fp = z.GetFilledPolysList(lid)
            for i in range(fp.OutlineCount()):
                k = acc.AddOutline(fp.Outline(i))
                for h in range(fp.HoleCount(i)):
                    acc.AddHole(fp.Hole(i, h), k)
            w = self.mm(z.GetMinThickness())
            minw = w if minw is None else min(minw, w)
        if n:
            acc.Simplify()
        return acc, minw, n

    def island(self, ps, i):
        one = self.p.SHAPE_POLY_SET()
        one.AddOutline(ps.Outline(i))
        for h in range(ps.HoleCount(i)):
            one.AddHole(ps.Hole(i, h))
        return one

    def net_copper(self, net, lid):
        """All copper of a net on one layer, merged: zone fill, pads, tracks, via rings."""
        acc, _, _ = self.fill(net, lid)
        err = self.p.FromMM(0.005)
        for p in self.pads:
            if p["net"] == net and lid in p["layers"]:
                p["obj"].TransformShapeToPolygon(acc, lid, 0, err, self.p.ERROR_INSIDE)
        for t in self.b.GetTracks():
            if str(t.GetNetname()) == net and t.IsOnLayer(lid):
                t.TransformShapeToPolygon(acc, lid, 0, err, self.p.ERROR_INSIDE)
        acc.Simplify()
        return acc

    def clusters(self, net):
        """Which pieces of a net's copper are joined (through the layers by vias and through-hole pads).
        Returns a function: pad -> cluster id (None when the pad is on no copper piece)."""
        pieces = {}                 # (lid, index) -> island polyset
        for lid in self.cu:
            ps = self.net_copper(net, lid)
            for i in range(ps.OutlineCount()):
                pieces[(lid, i)] = self.island(ps, i)
        parent = {k: k for k in pieces}

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        def where(pos, lid):
            for (ll, i), one in pieces.items():
                if ll == lid and one.Contains(pos, -1, self.p.FromMM(0.01)):
                    return (ll, i)
            return None

        for item in [v for v in self.vias if v["net"] == net] + [p for p in self.pads if p["net"] == net and p["hole"] and p["plated"]]:
            hit = [k for k in (where(item["pos"], lid) for lid in item["layers"]) if k]
            for k in hit[1:]:
                parent[find(k)] = find(hit[0])

        def cluster_of(pad):
            for lid in pad["layers"]:
                k = where(pad["pos"], lid)
                if k:
                    return find(k)
            return None
        return cluster_of


def cut_len(polys, ax, ay, bx, by):
    """Length of the segment a -> b that lies inside the polygons (even-odd over their contours)."""
    ln = math.hypot(bx - ax, by - ay)
    if ln <= 0:
        return 0.0
    ux, uy = (bx - ax) / ln, (by - ay) / ln
    ts = []
    for c in polys:
        n = len(c)
        for i in range(n):
            (x1, y1), (x2, y2) = c[i], c[(i + 1) % n]
            d1 = -(x1 - ax) * uy + (y1 - ay) * ux
            d2 = -(x2 - ax) * uy + (y2 - ay) * ux
            if (d1 <= 0 < d2) or (d2 <= 0 < d1):
                f = d1 / (d1 - d2)
                ts.append((x1 + f * (x2 - x1) - ax) * ux + (y1 + f * (y2 - y1) - ay) * uy)
    ts.sort()
    w = 0.0
    for k in range(0, len(ts) - 1, 2):
        a, e = max(ts[k], 0.0), min(ts[k + 1], ln)
        if e > a:
            w += e - a
    return w


def opening_len(polys, ax, ay, bx, by, min_web, reach):
    """Length of the opening in the polygons (the plane) on the line through a and b that holds the middle between
    them: from the plane copper before a's clearance to the plane copper behind b's. Copper shorter than min_web on
    that line is no web and is passed over. Looked at up to `reach` past each of the two points."""
    ln = math.hypot(bx - ax, by - ay)
    if ln <= 0:
        return 0.0
    ux, uy = (bx - ax) / ln, (by - ay) / ln
    ts = []
    for c in polys:
        n = len(c)
        for i in range(n):
            (x1, y1), (x2, y2) = c[i], c[(i + 1) % n]
            d1 = -(x1 - ax) * uy + (y1 - ay) * ux
            d2 = -(x2 - ax) * uy + (y2 - ay) * ux
            if (d1 <= 0 < d2) or (d2 <= 0 < d1):
                f = d1 / (d1 - d2)
                ts.append((x1 + f * (x2 - x1) - ax) * ux + (y1 + f * (y2 - y1) - ay) * uy)
    ts.sort()
    mid, left, right = ln / 2, -reach, ln + reach
    for k in range(0, len(ts) - 1, 2):
        a, e = ts[k], ts[k + 1]
        if e - a < min_web:
            continue
        if e <= mid:
            left = max(left, e)
        elif a >= mid:
            right = min(right, a)
        else:
            return 0.0                                                  # the middle lies in plane copper
    return right - left


def refill_closed(path, layer_name, box) -> int:
    """(own process) Add a no-pour rectangle on one layer of the board at `path`, refill every zone, save."""
    import pcbnew
    b = kicad_io.load_board(path)
    lid = Board(b).layer(layer_name)
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    ls.AddLayer(lid)
    z.SetLayerSet(ls)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    (getattr(z, "SetDoNotAllowZoneFills", None) or z.SetDoNotAllowCopperPour)(True)     # KiCad 10 / KiCad 9
    for setter in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowFootprints"):
        getattr(z, setter)(False)
    z.SetZoneName("zone_check: bridge closed (test)")
    b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    kicad_io.save_board(b, path)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 7 and argv[0] == "--refill-closed":
        kicad_io.need_kicad_python()
        pcb_common.quiet_wx()
        return refill_closed(argv[1], argv[2], [float(v) for v in argv[3:7]])
    ap = pcb_common.io_parser("Ground pour check on the saved fill: islands, vias per island, webs between holes, stitching.",
                              epilog="Exit codes: 0 pass, 1 findings, 2 could not run.")
    ap.add_argument("--stitch-grid", type=float, dest="grid", help="stitching grid in mm for the stitching report")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                           # no message box, ever: warnings go to stderr
    job = pcb_common.resolve(a)
    cfg = job.cfg("zone")
    L = pcb_common.Limits(cfg, DEFAULTS)
    fails, unknown, notes, no_plane = [], [], [], ""
    md = pcb_common.header("Ground pour check on the saved fill", job, "zone_check.py")
    data = {"script": "zone_check.py", "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board),
            "limits": L.to_dict(), "islands": [], "webs": [], "near": [], "fence": [], "stitching": [], "single_point": [],
            "crops": []}
    with pcb_common.work_copy(job.board, "zone-check-") as copy:
        board = kicad_io.load_board(copy)
        B = Board(board)
        bb = board.GetBoardEdgesBoundingBox()
        board_area = max(B.mm(bb.GetWidth()) * B.mm(bb.GetHeight()), 1e-6)
        zone_nets = sorted({str(z.GetNetname()) for z in board.Zones() if not z.GetIsRuleArea() and str(z.GetNetname())})
        nets = [n for n in zone_nets if (n in cfg["nets"] or kicad_io.leaf(n) in cfg["nets"])] if cfg.get("nets") else \
            [n for n in zone_nets if GND_NAME.search(n)]
        md += [f"Ground nets: {', '.join(nets) or 'none found'} "
               f"({'board.toml' if cfg.get('nets') else 'by name; set [zone] nets when it is another'}); zones on the board belong to: "
               f"{', '.join(zone_nets) or 'no net'}. {len(B.vias)} vias. Coordinates: KiCad's (mm).", "", "Settings:", ""] + L.table() + [""]
        if not nets:
            unknown.append("no ground zone found: nothing was checked")
        # ---- islands
        md += ["## Islands of filled ground copper", "",
               f"Rule: a piece must hold a pad or a via; when its net has copper on another layer it must be tied by at least "
               f"{L['min_vias']} vias or plated through-hole pads of its net. A piece with ties, but fewer, is a finding when it "
               f"is {L['island_one_tie_max_mm']:g} mm long or longer (its longest extent) and a listed note when it is shorter; "
               f"a piece with no tie is a finding at any size.", "",
               "| Net | Layer | Piece | Area (mm2) | x (mm) | y (mm) | Vias | Through-hole pads | Surface pads | Result |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        fills, pieces = {}, {}
        for net in nets:
            layers_with = [lid for lid in B.cu if B.fill(net, lid)[2]]
            nvias = [v for v in B.vias if v["net"] == net]
            npads = [p for p in B.pads if p["net"] == net]
            for lid in layers_with:
                ps, minw, _ = B.fill(net, lid)
                fills[(net, lid)] = (ps, minw)
                for i in range(ps.OutlineCount()):
                    one = B.island(ps, i)
                    o = ps.Outline(i)
                    obb = o.BBox()
                    area = one.Area() / 1e12
                    nv = sum(1 for v in nvias if lid in v["layers"] and one.Contains(v["pos"], -1, B.p.FromMM(v["d"] / 2)))
                    nt = sum(1 for p in npads if p["hole"] and p["plated"] and one.Contains(p["pos"], -1, B.p.FromMM(0.05)))
                    ns = sum(1 for p in npads if not p["hole"] and lid in p["layers"] and one.Contains(p["pos"], -1, B.p.FromMM(0.05)))
                    res, why = "PASS", ""
                    if nv + nt + ns == 0 or (len(layers_with) > 1 and nv + nt < L["min_vias"]):
                        # the fill alone is short of ties: count those of the whole copper piece it belongs to
                        # (the fill with the pads and tracks of its net that touch it, thermal spokes included)
                        if (net, lid) not in pieces:
                            pc = B.net_copper(net, lid)
                            pieces[(net, lid)] = [B.island(pc, k) for k in range(pc.OutlineCount())]
                        first = o.CPoint(0)
                        piece = next((q for q in pieces[(net, lid)] if q.Contains(first, -1, B.p.FromMM(0.02))), None)
                        if piece is not None:
                            pv = sum(1 for v in nvias if lid in v["layers"] and piece.Contains(v["pos"], -1, B.p.FromMM(0.02)))
                            pt = sum(1 for p in npads if p["hole"] and p["plated"] and piece.Contains(p["pos"], -1, B.p.FromMM(0.02)))
                            pn = sum(1 for p in npads if not p["hole"] and lid in p["layers"] and piece.Contains(p["pos"], -1, B.p.FromMM(0.02)))
                        else:
                            pv = pt = pn = 0
                        if pv + pt + pn == 0:
                            res, why = "FAIL", "orphan: holds no pad and no via, and touches none through a track"
                        elif len(layers_with) > 1 and pv + pt == 0:
                            res, why = "FAIL", "not tied to another layer: no via and no through-hole pad in the copper piece it belongs to"
                        elif len(layers_with) > 1 and pv + pt < L["min_vias"]:
                            ext = B.mm(max(obb.GetWidth(), obb.GetHeight()))
                            why = (f"tied by {pv + pt} via(s) or through-hole pad(s), fewer than {L['min_vias']} (counted over the "
                                   f"whole copper piece it belongs to); {ext:.1f} mm long")
                            if ext >= L["island_one_tie_max_mm"] - 1e-6:
                                res, why = "FAIL", why + f" (a finding from {L['island_one_tie_max_mm']:g} mm)"
                            else:
                                res, why = "NOTE", why + f": shorter than {L['island_one_tie_max_mm']:g} mm, listed"
                        else:
                            why = f"ties counted over the copper piece it belongs to: {pv} via(s), {pt} through-hole pad(s), {pn} surface pad(s)"
                    cx, cy = B.mm(obb.Centre().x), B.mm(obb.Centre().y)
                    md.append(f"| {net} | {B.name[lid]} | {i} | {area:.1f} | {B.mm(obb.GetLeft()):.2f} .. {B.mm(obb.GetRight()):.2f} | "
                              f"{B.mm(obb.GetTop()):.2f} .. {B.mm(obb.GetBottom()):.2f} | {nv} | {nt} | {ns} | {res}{': ' + why if why else ''} |")
                    data["islands"].append({"net": net, "layer": B.name[lid], "piece": i, "area": round(area, 2), "vias": nv,
                                            "tht": nt, "smd": ns, "box": [round(B.mm(v), 2) for v in (obb.GetLeft(), obb.GetTop(), obb.GetRight(), obb.GetBottom())],
                                            "result": res})
                    if res == "NOTE":
                        notes.append(f"island: {net} on {B.name[lid]}, piece {i} ({area:.1f} mm2 at ({cx:.1f}, {cy:.1f})): {why}")
                    if res == "FAIL":
                        fails.append(f"island: {net} on {B.name[lid]}, piece {i} ({area:.1f} mm2 at ({cx:.1f}, {cy:.1f})): {why}")
                        data["crops"].append({"name": f"island_{B.name[lid]}_{i}", "frame": "kicad", "x": round(cx, 2), "y": round(cy, 2),
                                              "size": max(8.0, min(30.0, 1.5 * B.mm(max(obb.GetWidth(), obb.GetHeight())))), "why": why})
        # ---- webs between neighbouring holes on plane layers
        md += ["", "## Copper webs between neighbouring holes on plane layers", ""]
        outer = {B.cu[0], B.cu[-1]}
        covered = {lid for (net, lid), (ps, _) in fills.items() if ps.Area() / 1e12 >= PLANE_SHARE * board_area}
        if cfg.get("plane_layers"):
            planes = [B.layer(n) for n in cfg["plane_layers"]]
        else:                                   # inner layers by coverage; an outer layer only when it is named
            planes = sorted((covered - outer) | {B.layer(n) for n in cfg.get("planes", [])})
        left = sorted(B.name[lid] for lid in (covered & outer) - set(planes))
        if not planes and nets:                 # nothing is judged as a plane: the web check did not happen. Never a pass
            no_plane = NO_PLANE
            unknown.append(f"webs: {NO_PLANE} (no inner layer where a ground zone covers {PLANE_SHARE:.0%} of the board, and "
                           f"[zone] planes names no layer" + (f"; a ground pour covers {', '.join(left)}" if left else "") + ")")
            md.append(f"**UNKNOWN**: {NO_PLANE}. No inner layer carries a ground zone over {PLANE_SHARE:.0%} of the board and "
                      f"[zone] planes names no layer" + (f"; a ground pour covers {', '.join(left)}" if left else "") +
                      ", so no copper web between neighbouring holes was measured. This is not a pass.")
            md.append("")
        elif left:
            md.append(f"Not judged as a plane: {', '.join(left)} (an outer layer with a ground pour over {PLANE_SHARE:.0%} of the "
                      f"board; name it in [zone] planes when signals take it as their reference).")
            md.append("")
        for lid in planes:
            for (net, ll), (ps, minw) in fills.items():
                if ll != lid:
                    continue
                lim = L["min_web"] if L["min_web"] > 0 else (minw or 0.25)
                conts = [c for poly in pcb_common.poly_points(ps) for c in poly]
                holes = [(v["x"], v["y"], v["drill"], v["net"], "via") for v in B.vias if lid in v["layers"]] + \
                        [(p["x"], p["y"], p["drill"], p["net"], f"{p['ref']}.{p['num']}") for p in B.pads if p["hole"]]
                grid = {}
                for k, h in enumerate(holes):
                    grid.setdefault((int(h[0] // L["web_reach"]), int(h[1] // L["web_reach"])), []).append(k)
                pairs, worst, bad = 0, None, []
                for k, h in enumerate(holes):
                    gx, gy = int(h[0] // L["web_reach"]), int(h[1] // L["web_reach"])
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            for j in grid.get((gx + dx, gy + dy), ()):
                                if j <= k:
                                    continue
                                g = holes[j]
                                dist = math.hypot(h[0] - g[0], h[1] - g[1])
                                if dist > L["web_reach"] or dist < 1e-6 or h[3] == net or g[3] == net:
                                    continue
                                # nearer neighbours on the same line hide this pair: only direct neighbours count
                                if any(m not in (k, j) and _pt_seg(holes[m][0], holes[m][1], h[0], h[1], g[0], g[1]) < 0.05
                                       for ddx in (-1, 0, 1) for ddy in (-1, 0, 1) for m in grid.get((gx + ddx, gy + ddy), ())):
                                    continue
                                web = cut_len(conts, h[0], h[1], g[0], g[1])
                                # both flanks of the gap must be plane copper: two holes inside another net's pour,
                                # or at the plane's rim, are no slot in the plane
                                mx, my = (h[0] + g[0]) / 2, (h[1] + g[1]) / 2
                                nx, ny = -(g[1] - h[1]) / dist, (g[0] - h[0]) / dist
                                if min(cut_len(conts, mx + sg * nx * 0.3, my + sg * ny * 0.3, mx + sg * nx * FLANK, my + sg * ny * FLANK)
                                       for sg in (1, -1)) < 0.3:
                                    continue
                                pairs += 1
                                rec = (web, h, g)
                                if worst is None or web < worst[0]:
                                    worst = rec
                                if web < lim - 1e-6:
                                    bad.append(rec)
                # holes joined by webs under the minimum (merged clearances included) form one opening in the plane
                par = {}

                def root(k):
                    par.setdefault(k, k)
                    while par[k] != k:
                        par[k] = par[par[k]]
                        k = par[k]
                    return k
                for _, h, g in bad:
                    par[root(h[:2])] = root(g[:2])
                groups = {}
                for k in list(par):
                    groups.setdefault(root(k), []).append(k)
                found, listed = [], []
                for members in groups.values():
                    if len(members) == 2:                               # a pair: the opening along the line through both holes
                        (ax, ay), (bx_, by_) = members
                        length = opening_len(conts, ax, ay, bx_, by_, lim, L["web_reach"])
                    else:                                               # a row: from the first hole to the last
                        length = max(math.hypot(a[0] - b[0], a[1] - b[1]) for a in members for b in members)
                    rec = {"holes": len(members), "length": round(length, 2), "x": round(sum(q[0] for q in members) / len(members), 2),
                           "y": round(sum(q[1] for q in members) / len(members), 2)}
                    if len(members) >= 3 or length >= L["web_pair_max_mm"] - 1e-6:
                        found.append(dict(rec, result="FINDING"))
                    else:
                        listed.append(dict(rec, result="NOTE"))
                found.sort(key=lambda r: (-r["holes"], -r["length"]))
                listed.sort(key=lambda r: -r["length"])
                res = "PASS" if not found else "FAIL"
                wtxt = (f"narrowest web {worst[0]:.3f} mm between {worst[1][4]} at ({worst[1][0]:.2f}, {worst[1][1]:.2f}) and "
                        f"{worst[2][4]} at ({worst[2][0]:.2f}, {worst[2][1]:.2f})") if worst else "no pair of neighbouring holes"
                md.append(f"- {net} on {B.name[lid]}: {pairs} pairs of neighbouring holes (up to {L['web_reach']} mm apart); {wtxt}; "
                          f"minimum {lim:.3f} mm: **{res}**" + (f" ({len(bad)} webs under the minimum, {sum(1 for w in bad if w[0] <= 1e-6)} "
                                                              f"of them merged clearances: {len(found)} opening(s) of three or more holes "
                                                              f"in a row or of {L['web_pair_max_mm']:g} mm or more, {len(listed)} pair(s) "
                                                              f"with a shorter opening, listed)" if bad else ""))
                for r in found[:MAX_LISTED]:
                    md.append(f"  - FINDING: {r['holes']} holes whose clearances join, {r['length']:.1f} mm "
                              f"{'from the first hole to the last' if r['holes'] >= 3 else 'of opening'}, around ({r['x']:.2f}, {r['y']:.2f})")
                for r in listed[:MAX_LISTED]:
                    md.append(f"  - listed: 2 holes, opening {r['length']:.1f} mm, around ({r['x']:.2f}, {r['y']:.2f})")
                if found:
                    big = found[0]
                    fails.append(f"webs: {net} on {B.name[lid]}: {len(found)} opening(s) in the plane of three or more holes in a row or "
                                 f"of {L['web_pair_max_mm']:g} mm or more (the largest: {big['holes']} holes, {big['length']:.1f} mm, around "
                                 f"({big['x']:.2f}, {big['y']:.2f}))")
                    data["crops"].append({"name": f"web_{B.name[lid]}", "frame": "kicad", "x": big["x"], "y": big["y"],
                                          "size": max(8.0, min(30.0, 2.0 * big["length"])),
                                          "why": f"largest opening in the plane on {B.name[lid]}: {big['holes']} holes, {big['length']:.1f} mm"})
                if listed:
                    notes.append(f"webs: {net} on {B.name[lid]}: {len(listed)} pair(s) of holes whose clearances join into an opening "
                                 f"shorter than {L['web_pair_max_mm']:g} mm (the longest {listed[0]['length']:.1f} mm): listed")
                data["webs"].append({"net": net, "layer": B.name[lid], "pairs": pairs, "min_web": lim, "narrowest": worst[0] if worst else None,
                                     "under": [[round(w, 3), round(h[0], 2), round(h[1], 2), round(g[0], 2), round(g[1], 2)] for w, h, g in bad[:500]],
                                     "openings": found + listed, "result": res})
        # ---- a via near named pads
        gvias = [v for v in B.vias if v["net"] in nets]
        if cfg.get("near"):
            md += ["", "## A ground via near named pads", "", "| Pad | Nearest ground via (mm) | Limit (mm) | Result |", "|---|---|---|---|"]
            for n in cfg["near"]:
                pad = B.pad(n["pad"])
                d = min((math.hypot(v["x"] - pad["x"], v["y"] - pad["y"]) for v in gvias), default=float("inf"))
                ok = d <= float(n["max"]) + 1e-6
                md.append(f"| {n['pad']} | {d:.2f} | {float(n['max']):g} | {'PASS' if ok else 'FAIL'} |")
                data["near"].append({"pad": n["pad"], "distance": round(d, 3) if math.isfinite(d) else None, "max": float(n["max"]), "ok": ok})
                if not ok:
                    fails.append(f"near: no ground via within {float(n['max']):g} mm of {n['pad']} (nearest {d:.2f} mm)")
        # ---- fence vias
        if cfg.get("fence"):
            md += ["", "## Vias beside the tracks of named nets (fence)", "", "| Nets | Within (mm) | Vias | Planned | Result |", "|---|---|---|---|---|"]
            for fz in cfg["fence"]:
                pats = fz.get("nets", [])
                tr = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and
                      (pcb_common.matches(str(t.GetNetname()), pats) or pcb_common.matches(kicad_io.leaf(str(t.GetNetname())), pats))]
                within = float(fz.get("within", 1.5))
                segs = [(B.mm(t.GetStart().x), B.mm(t.GetStart().y), B.mm(t.GetEnd().x), B.mm(t.GetEnd().y)) for t in tr]
                count = sum(1 for v in B.vias if segs and min(_pt_seg(v["x"], v["y"], *s) for s in segs) <= within)
                planned = fz.get("planned")
                ok = bool(segs) and (planned is None or count >= int(planned))
                md.append(f"| {', '.join(pats)} | {within:g} | {count} | {planned if planned is not None else '-'} | "
                          f"{'PASS' if ok else 'FAIL'}{'' if segs else ': no track of these nets'} |")
                data["fence"].append({"nets": pats, "within": within, "count": count, "planned": planned, "ok": ok})
                if not ok:
                    fails.append(f"fence: {count} via(s) within {within:g} mm of {', '.join(pats)}" +
                                 (f", planned {planned}" if planned is not None else ": no track of these nets on the board"))
        # ---- stitching
        st = cfg.get("stitching", {}) if isinstance(cfg.get("stitching"), dict) else {}
        grid_mm = a.grid or st.get("grid")
        if grid_mm:
            lim = float(grid_mm) / math.sqrt(2.0)
            st_layers = [B.layer(n) for n in st["layers"]] if st.get("layers") else [B.cu[0], B.cu[-1]]
            md += ["", f"## Stitching of the ground pours on outer layers: grid {float(grid_mm):g} mm", "",
                   f"The largest distance from any point of a pour to its nearest ground via or plated ground pin must not pass "
                   f"{lim:.2f} mm (the farthest point of a square grid of {float(grid_mm):g} mm pitch). Sampled every {L['sample']} mm.", "",
                   "| Net | Layer | Piece | Area (mm2) | Farthest point from a via (mm) | at (x, y) | Limit (mm) | Result |", "|---|---|---|---|---|---|---|---|"]
            step = L["sample"]
            for (net, lid), (ps, _) in fills.items():
                if lid not in st_layers:
                    continue
                ties = [(v["x"], v["y"]) for v in B.vias if v["net"] == net and lid in v["layers"]] + \
                       [(p["x"], p["y"]) for p in B.pads if p["net"] == net and p["hole"] and p["plated"]]
                cell = max(float(grid_mm), 1.0)
                tg = {}
                for x, y in ties:
                    tg.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
                for i in range(ps.OutlineCount()):
                    one = B.island(ps, i)
                    obb = ps.Outline(i).BBox()
                    x0, y0, x1, y1 = B.mm(obb.GetLeft()), B.mm(obb.GetTop()), B.mm(obb.GetRight()), B.mm(obb.GetBottom())
                    far = (0.0, None)
                    y = y0 + step / 2
                    while y < y1:
                        x = x0 + step / 2
                        while x < x1:
                            if one.Contains(B.p.VECTOR2I(B.p.FromMM(x), B.p.FromMM(y))):
                                best, ring = float("inf"), 1
                                gx, gy = int(x // cell), int(y // cell)
                                while True:
                                    for ix in range(gx - ring, gx + ring + 1):
                                        for iy in range(gy - ring, gy + ring + 1):
                                            for tx, ty in tg.get((ix, iy), ()):
                                                d = math.hypot(tx - x, ty - y)
                                                if d < best:
                                                    best = d
                                    if best <= ring * cell or ring * cell > 1000:
                                        break
                                    ring += 1
                                if best > far[0]:
                                    far = (best, (x, y))
                            x += step
                        y += step
                    if far[1] is None:
                        continue
                    ok = far[0] <= lim
                    ftxt = f"{far[0]:.2f}" if math.isfinite(far[0]) else "no via at all"
                    md.append(f"| {net} | {B.name[lid]} | {i} | {one.Area() / 1e12:.1f} | {ftxt} | ({far[1][0]:.2f}, {far[1][1]:.2f}) | {lim:.2f} | "
                              f"{'PASS' if ok else 'FAIL'} |")
                    data["stitching"].append({"net": net, "layer": B.name[lid], "piece": i, "farthest": round(far[0], 3) if math.isfinite(far[0]) else None,
                                              "at": [round(far[1][0], 2), round(far[1][1], 2)], "limit": round(lim, 3), "ok": ok})
                    if not ok:
                        fails.append(f"stitching: {net} on {B.name[lid]}, piece {i}: a point at ({far[1][0]:.2f}, {far[1][1]:.2f}) is {ftxt} mm "
                                     f"from the nearest ground via (limit {lim:.2f} mm)")
                        data["crops"].append({"name": f"stitch_{B.name[lid]}_{i}", "frame": "kicad", "x": round(far[1][0], 2), "y": round(far[1][1], 2),
                                              "size": 2.5 * float(grid_mm), "why": f"farthest point from a ground via: {ftxt} mm"})
        # ---- single-point test
        for sp in cfg.get("single_point", []):
            name = sp.get("name", "single point")
            md += ["", f"## Single-point test: {name}", ""]
            net = B.pad(sp["pads"][0])["net"]
            rest = B.pad(sp["rest"]) if sp.get("rest") else next((p for p in B.pads if p["net"] == net and f"{p['ref']}.{p['num']}" not in sp["pads"]), None)
            if rest is None:
                raise kicad_io.KicadIOError(f"single-point test '{name}': no other pad of net {net} to compare with")
            before = B.clusters(net)
            cr = before(rest)
            joined = [s for s in sp["pads"] if before(B.pad(s)) == cr and cr is not None]
            if len(joined) != len(sp["pads"]):
                apart = [s for s in sp["pads"] if s not in joined]
                md.append(f"**FAIL**: on the board as it is, {', '.join(apart)} are not joined to {rest['ref']}.{rest['num']} at all: "
                          "the island is not connected, or the pads are not the island's.")
                fails.append(f"single point '{name}': {', '.join(apart)} not joined to the rest of {net} on the board as it is")
                continue
            with kicad_io.private_tmp("zone-check-sp-") as tmp:
                work = os.path.join(tmp, os.path.basename(copy))
                kicad_io.copy_board(copy, work, lock_source=False)
                cmd = [sys.executable, "-I", "-B", os.path.abspath(__file__), "--refill-closed", work, sp["layer"]] + [str(float(v)) for v in sp["close"]]
                rc, text, blocked = pcb_common.run_guarded(cmd, REFILL_TIMEOUT)
                if blocked or rc != 0:
                    raise kicad_io.KicadIOError("the refill of the single-point test failed: " + (blocked or text.strip()[-500:]))
                B2 = Board(kicad_io.load_board(work))
                after = B2.clusters(net)
                cr2 = after(B2.pad(f"{rest['ref']}.{rest['num']}"))
                still = [s for s in sp["pads"] if after(B2.pad(s)) == cr2]
            ok = not still
            c = sp["close"]
            md.append(f"In a copy, the bridge on {sp['layer']} was closed by a no-pour rectangle ({c[0]:g}, {c[1]:g}) .. ({c[2]:g}, {c[3]:g}) and "
                      f"every zone was refilled in a separate process. Pads {', '.join(sp['pads'])} against the rest of {net} "
                      f"(reference pad {rest['ref']}.{rest['num']}): " +
                      ("**PASS**: all of them came apart: the bridge is their only tie." if ok else
                       f"**FAIL**: still joined: {', '.join(still)}: the island has another tie, or the rectangle does not cover the bridge."))
            data["single_point"].append({"name": name, "pads": sp["pads"], "still_joined": still, "ok": ok})
            if not ok:
                fails.append(f"single point '{name}': {', '.join(still)} still joined to the rest of {net} with the bridge closed")
    result = pcb_common.verdict(len(fails), len(unknown))
    if fails or unknown:
        md += ["", "## Findings", ""] + [f"- FAIL: {x}" for x in fails] + [f"- UNKNOWN: {x}" for x in unknown]
    if notes:
        md += ["", f"## Notes: listed, not failed ({len(notes)})", ""] + [f"- {x}" for x in notes]
    md += ["", "## Not checked", "",
           "Whether the saved fill is up to date (refill and save first); thermal spokes; a row of vias along the board edges "
           "and around each RF section; the return path of any single signal" +
           ("" if grid_mm else "; the stitching grid (give [zone.stitching] grid for an RF board)") +
           ("" if cfg.get("single_point") else "; a single-point ground (give [[zone.single_point]] when the design has one)") + ".",
           "", f"**Result: {result}** ({len(fails)} finding(s), {len(unknown)} unknown, {len(notes)} note(s))"
           + (f": {no_plane}" if no_plane else "")]
    data["result"], data["failures"], data["unknown"], data["notes"] = result, fails, unknown, notes
    data["webs_result"] = "UNKNOWN" if no_plane else ("FAIL" if any(w["result"] == "FAIL" for w in data["webs"]) else
                                                      "PASS" if data["webs"] else "NOT CHECKED")
    p_md, _ = pcb_common.write_result(job.out, "zone_check", md, data)
    for x in fails[:30]:
        print("FAIL ", x)
    for x in unknown[:10]:
        print("UNKNOWN ", x)
    print(f"{result}: {len(fails)} finding(s), {len(unknown)} unknown, {len(notes)} note(s); {len(data['islands'])} islands, "
          f"{len(data['webs'])} plane fills checked for webs" + (f"; {no_plane}" if no_plane else "") + f" -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
