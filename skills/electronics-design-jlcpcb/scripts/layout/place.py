"""Placement from a description: fixed parts, blocks around an anchor, a packer for the small parts, label room.

What it does (a library for a project's src/build_board.py)
    p = Placer(board, mech)
    p.fixed({"J1": (x, y, rot), ...})                 parts at given places (connectors, holes, parts at a wall)
    p.block(anchor, {"C3": (dx, dy, rot), ...}, rot)  a group drawn once, placed relative to an anchor: a point,
                                                      a placed part "U1", or one of its pads ("U1", "3"); `rot`
                                                      (0, 90, 180, 270) turns the whole group around the anchor
    p.reserve((x0, y0, x1, y1), "name")               an area the packer and the labels leave free (hand tracks,
                                                      a pour, the information block, a routing channel)
    p.pack([(ref, anchor_ref, anchor_pin, own_pin, radius), ...])
                                                      each part as near as possible to its anchor pin, its own
                                                      pin `own_pin` toward it, inside `radius` mm (then twice
                                                      and three times that); nearest first, never over another
                                                      courtyard, a hole keep-out, a free band, a keep-out area
                                                      for parts, a reserved area or the board edge
    p.finish()                                        labels placed, the report (a dict) returned
    p.plot("placement.png")                           a picture to LOOK at: courtyards, pads, labels, holes with
                                                      keep-outs, bands, reserved areas (needs Pillow)

    Label room: every placed part gets a box for its reference text beside its courtyard (above, below, right,
    left; then turned 90 degrees), clear of courtyards, other labels, holes, bands and reserved areas, and the
    text is put there. The packer prefers, inside the radius, the nearest spot where the label fits as well: the
    radius is the electrical limit and wins over the label. A part placed by hand on the label of an earlier part
    makes that label look for a new spot. A part without a legal label spot keeps its place, its reference text
    is hidden, and it is listed ("unlabelled"): it then needs a place on the assembly drawing.

Why it exists
    A packer that knew nothing of labels left parts without room for a reference text and put labels on vias;
    a part dropped on a hand track closed the escape of a fine-pitch chip. Placement by description keeps every
    fixed coordinate in one table that comes from the mechanical file, and the reserved areas keep the packer
    off what was planned by hand.

Where it stops
    Top side only. Rotations in steps of 90 degrees. The packer is greedy: it places in the order given and
    never moves an earlier part, so give the critical parts (decoupling, feedback) first, with a small radius,
    and fix by hand every part that forms an escape corridor. It reads courtyards: a footprint without one is
    placed by its bounding box and named in the report. It does not judge the electrical quality of a place.

board.toml keys: none (everything comes from the project's script). A library: no exit codes; what cannot be
done raises kicad_io.KicadIOError.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import math
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

STEP = 0.25                 # mm: the packer's search grid
LABEL_END = 0.5             # mm added at both ends of a label when it is compared with other labels (1 mm end to end)


def _turn(dx: float, dy: float, rot: float) -> tuple:
    """A vector turned by KiCad's rotation angle (counter-clockwise as seen on the board, y pointing down)."""
    a = math.radians(rot)
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


def _hit(a: tuple, b: tuple, gap: float = 0.0) -> bool:
    return a[0] < b[2] + gap and a[2] > b[0] - gap and a[1] < b[3] + gap and a[3] > b[1] - gap


def _segs_cross(p, q, r, s) -> bool:
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return side(p, q, r) * side(p, q, s) < 0 and side(r, s, p) * side(r, s, q) < 0


def rect_hits_poly(box: tuple, poly: list) -> bool:
    """Does the rectangle (x0, y0, x1, y1) touch the polygon (overlap, contain, or lie inside)?"""
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if any(B.in_poly(x, y, poly) for x, y in corners) or any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in poly):
        return True
    n = len(poly)
    return any(_segs_cross(corners[i], corners[(i + 1) % 4], poly[j], poly[(j + 1) % n])
               for i in range(4) for j in range(n))


class Placer:
    """See the head of this file. gap: free space between courtyards (mm); edge: courtyard to board edge;
    hole_margin: courtyard to a hole's keep-out circle; labels: place reference texts (False: leave them as the
    footprints have them); label_h, label_line: text height and line width; label_gap: label to courtyards."""

    def __init__(self, board, mech, *, gap: float = 0.3, edge: float = 0.5, hole_margin: float = 0.3,
                 labels: bool = True, label_h: float = 1.0, label_line: float = 0.16, label_gap: float = 0.25):
        self.b, self.mech = board, mech
        self.gap, self.edge, self.hole_margin = gap, edge, hole_margin
        self.labels_on, self.label_h, self.label_line, self.label_gap = labels, label_h, label_line, label_gap
        self.outline = o = B.outline_polygon(board)
        turns = [(o[i][0] - o[i - 1][0]) * (o[(i + 1) % len(o)][1] - o[i][1]) -
                 (o[i][1] - o[i - 1][1]) * (o[(i + 1) % len(o)][0] - o[i][0]) for i in range(len(o))]
        self._convex = all(v >= -1e-9 for v in turns) or all(v <= 1e-9 for v in turns)
        self.holes =[(h["x"], h["y"], max(h["keepout_d"], h["d"]) / 2) for h in mech.holes]
        # areas where no part may stand: the free bands and every rule area of the board that forbids footprints
        self.no_parts = [[(B.mm(o.CPoint(i).x), B.mm(o.CPoint(i).y)) for i in range(o.PointCount())]
                         for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowFootprints()
                         for o in [z.Outline().Outline(0)]]
        self.reserved: list[tuple] = []          # (name, (x0, y0, x1, y1))
        self.placed: dict[str, tuple] = {}       # ref -> (x, y, rot)
        self.boxes: dict[str, tuple] = {}        # ref -> courtyard box
        self.labels: dict[str, tuple] = {}       # ref -> (box, angle)
        self.unlabelled: list[str] = []
        self.failed: list[tuple] = []            # (ref, why)
        self.notes: list[str] = list(mech.notes)
        self._shapes: dict = {}
        hole_refs = {h["name"] for h in mech.holes}
        for fp in board.GetFootprints():         # mounting holes are placed by new_board(): their keep-outs hold
            if fp.GetReference() in hole_refs:   # the room, so they need no courtyard box and no label here
                self.placed[fp.GetReference()] = (B.mm(fp.GetPosition().x), B.mm(fp.GetPosition().y),
                                                  fp.GetOrientationDegrees())
                fp.Reference().SetVisible(False)

    # ---- geometry of one footprint -----------------------------------------------------------------------------
    def _fp(self, ref: str):
        fp = self.b.FindFootprintByReference(ref)
        if fp is None:
            raise kicad_io.KicadIOError(f"placement: no part {ref} on the board")
        return fp

    def _shape(self, ref: str, rot: float):
        """(courtyard box, {pad number: (dx, dy)}) of a part turned to `rot`, relative to its position."""
        fp = self._fp(ref)
        key = (fp.GetFPIDAsString(), ref if not fp.GetFPIDAsString() else "")
        if key not in self._shapes:
            fp.BuildCourtyardCaches()
            cy = fp.GetCourtyard(pcbnew.F_CrtYd)
            if cy.OutlineCount():
                bb = cy.BBox()
            else:
                bb = fp.GetBoundingBox(False)
                self.notes.append(f"{ref}: footprint without a courtyard, placed by its bounding box")
            pos, r0 = fp.GetPosition(), fp.GetOrientationDegrees()
            cs = [_turn(B.mm(x - pos.x), B.mm(y - pos.y), -r0) for x in (bb.GetX(), bb.GetRight())
                  for y in (bb.GetY(), bb.GetBottom())]
            pads: dict[str, tuple] = {}
            for p in fp.Pads():
                pads.setdefault(p.GetNumber(), _turn(B.mm(p.GetPosition().x - pos.x), B.mm(p.GetPosition().y - pos.y), -r0))
            self._shapes[key] = (cs, pads)
        cs, pads = self._shapes[key]
        tc = [_turn(x, y, rot) for x, y in cs]
        box = (min(c[0] for c in tc), min(c[1] for c in tc), max(c[0] for c in tc), max(c[1] for c in tc))
        return box, {n: _turn(x, y, rot) for n, (x, y) in pads.items()}

    def pad_xy(self, ref: str, pin: str) -> tuple:
        """Where a pad of a placed part is."""
        if ref not in self.placed:
            raise kicad_io.KicadIOError(f"placement: {ref} is not placed yet (it anchors another part)")
        x, y, rot = self.placed[ref]
        pads = self._shape(ref, rot)[1]
        if str(pin) not in pads:
            raise kicad_io.KicadIOError(f"placement: {ref} has no pad {pin}")
        return x + pads[str(pin)][0], y + pads[str(pin)][1]

    # ---- what is free ------------------------------------------------------------------------------------------
    def _inside(self, box: tuple, margin: float) -> bool:
        g = (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)
        corners = [(g[0], g[1]), (g[2], g[1]), (g[2], g[3]), (g[0], g[3])]
        if not all(B.in_poly(x, y, self.outline) for x, y in corners):
            return False
        if self._convex:                         # corners inside a convex outline: the whole box is inside
            return True
        n = len(self.outline)
        return not any(_segs_cross(corners[i], corners[(i + 1) % 4], self.outline[j], self.outline[(j + 1) % n])
                       for i in range(4) for j in range(n))

    def _clear_of_areas(self, box: tuple, hole_margin: float) -> bool:
        for hx, hy, r in self.holes:
            cx, cy = min(max(hx, box[0]), box[2]), min(max(hy, box[1]), box[3])
            if math.hypot(cx - hx, cy - hy) < r + hole_margin:
                return False
        if any(_hit(box, r) for _, r in self.reserved):
            return False
        return not any(rect_hits_poly(box, poly) for poly in self.no_parts)

    def free(self, box: tuple, ignore: str = "", gap: float | None = None) -> bool:
        """May a courtyard stand here?"""
        gap = self.gap if gap is None else gap
        if any(r != ignore and _hit(box, o, gap) for r, o in self.boxes.items()):
            return False
        if any(r != ignore and _hit(box, lb, 0.2) for r, (lb, _) in self.labels.items()):
            return False
        return self._clear_of_areas(box, self.hole_margin) and self._inside(box, self.edge)

    # ---- labels ------------------------------------------------------------------------------------------------
    def _label_size(self, ref: str) -> tuple:
        t = self._fp(ref).Reference()
        t.SetTextSize(pcbnew.VECTOR2I(B.iu(self.label_h), B.iu(self.label_h)))
        t.SetTextThickness(B.iu(self.label_line))
        t.SetTextAngleDegrees(0)
        return B.mm(t.GetBoundingBox().GetWidth()), self.label_h + self.label_line

    def _label_spot(self, ref: str, box: tuple):
        """A free box for the reference text beside the courtyard `box`: (label box, angle) or None."""
        w, h = self._label_size(ref)
        g = self.label_gap
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        cands = [((cx - w / 2, box[1] - g - h, cx + w / 2, box[1] - g), 0),          # above
                 ((cx - w / 2, box[3] + g, cx + w / 2, box[3] + g + h), 0),          # below
                 ((box[2] + g, cy - h / 2, box[2] + g + w, cy + h / 2), 0),          # right
                 ((box[0] - g - w, cy - h / 2, box[0] - g, cy + h / 2), 0),          # left
                 ((box[2] + g, cy - w / 2, box[2] + g + h, cy + w / 2), 90),         # right, turned
                 ((box[0] - g - h, cy - w / 2, box[0] - g, cy + w / 2), 90)]         # left, turned
        for lb, ang in cands:
            if any(r != ref and _hit(lb, o, 0.2) for r, o in self.boxes.items()):
                continue
            wide = (lb[0] - LABEL_END, lb[1], lb[2] + LABEL_END, lb[3]) if ang == 0 else \
                (lb[0], lb[1] - LABEL_END, lb[2], lb[3] + LABEL_END)
            if any(r != ref and _hit(wide, o, 0.1) for r, (o, _) in self.labels.items()):
                continue
            if self._clear_of_areas(lb, 0.2) and self._inside(lb, 0.2):
                return lb, ang
        return None

    def _write_label(self, ref: str) -> None:
        t = self._fp(ref).Reference()
        if ref not in self.labels:
            t.SetVisible(False)
            return
        (x0, y0, x1, y1), ang = self.labels[ref]
        t.SetLayer(pcbnew.F_SilkS)
        t.SetVisible(True)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        t.SetTextAngleDegrees(ang)
        t.SetPosition(B.pt((x0 + x1) / 2, (y0 + y1) / 2))

    # ---- placing -----------------------------------------------------------------------------------------------
    def _set(self, ref: str, x: float, y: float, rot: float, label: bool = True, spot=None) -> None:
        fp = self._fp(ref)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(B.pt(x, y))
        box0 = self._shape(ref, rot)[0]
        self.placed[ref] = (round(x, 4), round(y, 4), rot % 360)
        self.boxes[ref] = (x + box0[0], y + box0[1], x + box0[2], y + box0[3])
        self.labels.pop(ref, None)
        if not (self.labels_on and label):
            return
        # a part placed by hand may land on the label of an earlier part: that label looks for a new spot
        moved = [r for r, (lb, _) in self.labels.items() if _hit(lb, self.boxes[ref], 0.2)]
        for r in moved:
            del self.labels[r]
        for r in [ref] + moved:
            found = (spot if r == ref else None) or self._label_spot(r, self.boxes[r])
            if found:
                self.labels[r] = found
                if r in self.unlabelled:
                    self.unlabelled.remove(r)
            elif r not in self.unlabelled:
                self.unlabelled.append(r)
            self._write_label(r)

    def fixed(self, table: dict) -> None:
        """Parts at given places: {ref: (x, y, rotation)}. They are placed as told, also where the packer would
        refuse (a connector that hangs over the edge); finish() reports every courtyard that then overlaps."""
        for ref, (x, y, rot) in table.items():
            self._set(ref, x, y, rot)

    def block(self, anchor, table: dict, rot: float = 0) -> None:
        """A group placed relative to an anchor: {ref: (dx, dy, rotation)} as drawn with the anchor at (0, 0);
        `rot` turns the whole group. anchor: (x, y), a placed part "U1", or one of its pads ("U1", "3")."""
        if isinstance(anchor, str):
            ax, ay = self.placed[anchor][:2] if anchor in self.placed else self.pad_xy(anchor, "1")
        elif isinstance(anchor[0], str):
            ax, ay = self.pad_xy(anchor[0], anchor[1])
        else:
            ax, ay = anchor
        for ref, (dx, dy, r) in table.items():
            tx, ty = _turn(dx, dy, rot)
            self._set(ref, ax + tx, ay + ty, r + rot)

    def reserve(self, box: tuple, name: str = "") -> None:
        x0, y0, x1, y1 = box
        self.reserved.append((name, (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))))

    def pack(self, entries: list) -> list:
        """Place each (ref, anchor ref, anchor pin, own pin, radius[, gap]) in the order given. Returns the parts
        that found no place (also kept in the report)."""
        failed = []
        for e in entries:
            ref, aref, apin, own, radius = e[:5]
            gap = e[5] if len(e) > 5 else None
            if ref in self.placed:
                continue
            try:
                ax, ay = self.pad_xy(aref, apin)
                shapes = {rot: self._shape(ref, rot) for rot in (0, 90, 180, 270)}
                if str(own) not in shapes[0][1]:
                    raise kicad_io.KicadIOError(f"{ref} has no pad {own}")
            except kicad_io.KicadIOError as err:
                failed.append((ref, str(err)))
                continue
            best = None                                          # nearest free spot, with or without a label
            for k in (1, 2, 3):
                best = self._search(ref, ax, ay, str(own), radius * k, shapes, gap, (k - 1) * radius)
                if best:
                    if k > 1:
                        self.notes.append(f"{ref}: no room within {radius:g} mm of {aref}.{apin}; placed within "
                                          f"{radius * k:g} mm")
                    break
            if best is None:
                failed.append((ref, f"no room within {3 * radius:g} mm of {aref}.{apin}"))
                continue
            x, y, rot, spot = best
            self._set(ref, x, y, rot, spot=spot)
        self.failed += failed
        return failed

    def _search(self, ref, ax, ay, own, radius, shapes, gap, r_min):
        n = int(radius / STEP)
        offs = sorted((math.hypot(i * STEP, j * STEP), i * STEP, j * STEP)
                      for i in range(-n, n + 1) for j in range(-n, n + 1))
        first = None
        for d, ox, oy in offs:
            if d > radius:
                break
            if d < r_min - STEP:
                continue
            for rot in (0, 90, 180, 270):
                box0, pads = shapes[rot]
                x, y = ax + ox - pads[own][0], ay + oy - pads[own][1]
                box = (x + box0[0], y + box0[1], x + box0[2], y + box0[3])
                if not self.free(box, gap=gap):
                    continue
                if not self.labels_on:
                    return x, y, rot, None
                spot = self._label_spot(ref, box)
                if spot:
                    return x, y, rot, spot
                first = first or (x, y, rot, None)
        return first

    # ---- results -----------------------------------------------------------------------------------------------
    def unplaced(self) -> list:
        return sorted((fp.GetReference() for fp in self.b.GetFootprints() if fp.GetReference() not in self.placed),
                      key=B.natural)

    def finish(self) -> dict:
        """The report: what is placed, what failed, what has no label, what overlaps."""
        overlaps = []
        refs = sorted(self.boxes, key=B.natural)
        for i, a in enumerate(refs):
            overlaps += [(a, c) for c in refs[i + 1:] if _hit(self.boxes[a], self.boxes[c])]
        outside = [r for r in refs if not self._inside(self.boxes[r], 0.0)]
        banned = [r for r in refs if any(rect_hits_poly(self.boxes[r], p) for p in self.no_parts)]
        return {"placed": self.placed, "boxes": self.boxes, "labels": {r: list(v[0]) + [v[1]] for r, v in self.labels.items()},
                "unlabelled": sorted(self.unlabelled, key=B.natural), "failed": self.failed, "unplaced": self.unplaced(),
                "courtyards_overlap": overlaps, "courtyard_over_the_edge": outside,
                "courtyard_in_a_free_band_or_keep_out": banned, "reserved": self.reserved, "notes": self.notes,
                "ok": not (self.failed or self.unplaced() or overlaps or banned)}

    def plot(self, path: str, window: tuple | None = None, scale: float | None = None) -> str:
        """A picture of the placement (PNG). window: (x0, y0, x1, y1) in mm, default the whole board; scale:
        pixels per mm. Open it and look: this is the first place where a wrong rotation or a blocked channel
        shows."""
        kicad_io.add_user_site()
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise kicad_io.KicadIOError("the placement plot needs the Pillow library") from None
        x0, y0, x1, y1 = window or (self.mech.bbox[0] - 2, self.mech.bbox[1] - 2, self.mech.bbox[2] + 2,
                                    self.mech.bbox[3] + 2)
        s = scale or max(8.0, min(40.0, 2400.0 / max(x1 - x0, y1 - y0)))
        img = Image.new("RGB", (int((x1 - x0) * s) + 1, int((y1 - y0) * s) + 1), "white")
        dr = ImageDraw.Draw(img, "RGBA")
        try:
            font = ImageFont.load_default(size=max(9, int(0.8 * s)))
        except TypeError:                                        # an older Pillow: one fixed size
            font = ImageFont.load_default()

        def xy(x, y):
            return (x - x0) * s, (y - y0) * s

        def box(b, **kw):
            dr.rectangle([xy(b[0], b[1]), xy(b[2], b[3])], **kw)
        dr.polygon([xy(*p) for p in self.outline], fill=(232, 244, 232, 255), outline=(0, 100, 0, 255))
        for poly in self.no_parts:
            dr.polygon([xy(*p) for p in poly], fill=(230, 120, 120, 90), outline=(200, 60, 60, 255))
        for name, r in self.reserved:
            box(r, fill=(255, 200, 80, 110), outline=(200, 140, 0, 255))
        for h in self.mech.holes:
            for d, kw in ((max(h["keepout_d"], h["d"]), dict(outline=(220, 0, 0, 255), fill=(255, 0, 0, 30))),
                          (h["d"], dict(outline=(0, 0, 0, 255), fill=(255, 255, 255, 255)))):
                dr.ellipse([xy(h["x"] - d / 2, h["y"] - d / 2), xy(h["x"] + d / 2, h["y"] + d / 2)], **kw)
        for fp in self.b.GetFootprints():
            if fp.GetReference() not in self.placed:
                continue
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                box((B.mm(bb.GetX()), B.mm(bb.GetY()), B.mm(bb.GetRight()), B.mm(bb.GetBottom())),
                    fill=(190, 60, 60, 255) if p.GetNumber() == "1" else (150, 150, 150, 255))
        for ref, b in self.boxes.items():
            box(b, outline=(0, 0, 160, 255))
            if ref not in self.labels:
                dr.text(xy((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), ref, fill=(200, 0, 0, 255), font=font, anchor="mm")
        for ref, (lb, ang) in self.labels.items():
            box(lb, outline=(0, 140, 200, 255))
            dr.text(xy((lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2), ref, fill=(0, 0, 0, 255), font=font, anchor="mm")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        img.save(path)
        return path
