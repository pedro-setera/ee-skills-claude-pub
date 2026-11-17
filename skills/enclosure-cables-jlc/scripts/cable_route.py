"""Cable routes measured in the model: length, smallest bend, straight exits, arrival, clearance, crossings, pictures.

What it does
    Reads `cables/routes.toml`: per cable (and per wire where the wires differ) a start pose, a list of moves and an
    end pose. A pose is a point and the direction in which the wire LEAVES that connector (`p`, `d`), both ends alike.
    Moves: a straight (`{line = 12}`), an exact arc (`{arc = 90, r = 5, axis = [0, 1, 0]}` turns the heading by 90
    degrees about that axis, right-hand; or `toward = [x, y, z]` turns toward a direction), and "go to a pose"
    (`{to = [x, y, z], heading = [..], r = 5}` or `{to_end = true, r = 5}`), solved as arc - straight - arc.
    For every route it computes and writes rows for:
      ARRIVE    the route really ends at the end pose (position and direction tolerance)
      LEN       the centreline length, wire exit to wire exit
      BEND      the smallest bend radius against the cable type's minimum (cables.json `cable_types`, `[cables.types]`,
                built in: wire bundle R 5, network cable 4 x OD; coax by its datasheet in `route.min_bend_r`)
      STRAIGHT  the straight length leaving each connector (default 3 mm; `min_straight = [a, b]` per route)
      CLEAR     the swept cable (radius = half its outer diameter) against every solid of `model/build_model.py: build()`
                and the placed vendor parts, on all cores (the solids named in the route's `allow` are its own
                connectors and are skipped)
      CROSS     two cables do not pass through each other
    It writes the lengths into cables.json: `route.measure_a_mm` (the longest wire) and `route.wires[<key>].a`
    (`measure_b_mm` / `.b` with --second), `route.smallest_r_a`, and one picture per cable (top and side view, the route
    drawn over the model outline) in `<out>/cables/route_<id>.png`. A route that does not arrive writes no length.
    cables.json is rewritten ONLY when its content changes (a second run on the same inputs leaves the file, its checksum and
    its time stamp alone), so a build that lists it as an input does not see it as newer after every run.
    `Turtle` is importable: `from cable_route import Turtle`.

Why it exists (the real failure, told without names)
    Cable lengths guessed from a sketch came out several millimetres off on short stiff cables, and one route ran
    through two other wires. A route drawn in the model as straights and exact arcs gives a length that can be measured
    again by a second person, and a clearance number instead of an impression.

Usage
    python -I cable_route.py [--project <mech folder>] [--out <folder>] [--routes cables/routes.toml] [--cables cables.json]
                             [--second] [--only CAB-01] [--no-model] [--no-write] [--no-pictures]
        --second     write measure_b_mm instead of measure_a_mm (a second routes file measured by someone else)
        --no-model   geometry rows only; the clearance rows read "could not run"
    routes.toml:
        [[cable]]
        id = "CAB-01"
        start = {p = [20, 30, 12], d = [0, 0, 1]}        # wire exit of P1 and the direction the wire leaves it
        end   = {p = [80, 50, 12], d = [0, 0, 1]}        # wire exit of P2 and the direction the wire leaves IT
        moves = [ {line = 6}, {arc = 90, r = 5, toward = [1, 0, 0]}, {to_end = true, r = 5, lead = 6} ]
        allow = ["header_a", "header_b"]                 # the cable's own connector solids (wildcards * ?)
        [[cable.wire]]                                   # optional: one route per wire that differs
        key = "P1.3"
        start = ...   end = ...   moves = [...]
    `lead` in a "to" move = the straight left before the target pose (the connector's straight exit).
    Needs numpy; the model rows need CadQuery (re-runs itself under CADQUERY_PYTHON / [tools] cadquery_python);
    the pictures need matplotlib.

Config keys (mech.toml)
    [cables] routes, file, min_straight_mm = 3.0, arrive_tol_mm = 0.5, arrive_tol_deg = 2.0, clearance_mm = 1.0,
             cable_gap_mm = 0.0, skip_solids = ["name*"]      [cables.types.<name>] od_mm, min_bend_r, min_bend_x_od
    [paths] model, vendor

Exit codes
    0 all rows pass   1 a row failed   2 could not run (no routes file, no numpy) or a row could not run (no model)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import fnmatch
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import cable_common as cc  # noqa: E402

try:
    import numpy as np
except ImportError:                                    # reported in main()
    np = None


def unit(v):
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise ValueError("a direction of zero length")
    return v / n


def angle_between(a, b) -> float:
    return math.acos(max(-1.0, min(1.0, float(np.dot(unit(a), unit(b))))))


# ---------------------------------------------------------------- go-to-pose solver ----------------------------------
def _arc_tip(t, w, r):
    """Offset and angle of an arc of radius r that turns heading t into heading w."""
    c = max(-1.0, min(1.0, float(np.dot(t, w))))
    th = math.acos(c)
    if th < 1e-9:
        return np.zeros(3), 0.0
    if math.pi - th < 1e-6:
        return None, th
    n = unit(w - t * c)
    return r * math.sin(th) * t + r * (1 - math.cos(th)) * n, th


def solve_arc_line_arc(p0, t0, p1, t1, r1, r2):
    """Path p0 (heading t0) -> arc r1 -> straight s along w -> arc r2 -> p1 (heading t1).
    Returns (total length, w, s, angle1 rad, angle2 rad) of the shortest solution found, or None.
    Method: Gauss-Newton on the straight's direction w (two tangent-plane coordinates) and its length s, started from
    the best directions of a scan of the whole sphere."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    t0, t1 = unit(t0), unit(t1)

    def miss(w, s):
        a, _ = _arc_tip(t0, w, r1)
        b, _ = _arc_tip(w, t1, r2)
        if a is None or b is None:
            return None
        return p0 + a + w * s + b - p1

    n = 1500
    k = np.arange(n) + 0.5
    ph = np.arccos(1 - 2 * k / n)
    th = math.pi * (1 + 5 ** 0.5) * k
    W = np.stack([np.cos(th) * np.sin(ph), np.sin(th) * np.sin(ph), np.cos(ph)], axis=1)
    seeds = []
    for w in W:
        a, _ = _arc_tip(t0, w, r1)
        b, _ = _arc_tip(w, t1, r2)
        if a is None or b is None:
            continue
        v = p1 - p0 - a - b
        s = float(np.dot(v, w))
        if s < -0.5:
            continue
        seeds.append((float(np.linalg.norm(v - w * s)), tuple(w), max(s, 0.0)))
    seeds.sort()
    best = None
    for _m, w, s in seeds[:10]:
        w = np.array(w)
        ok = False
        for _ in range(60):
            f = miss(w, s)
            if f is None:
                break
            if np.linalg.norm(f) < 1e-10:
                ok = True
                break
            e1 = unit(np.cross(w, [1.0, 0, 0] if abs(w[0]) < 0.9 else [0, 1.0, 0]))
            e2 = np.cross(w, e1)
            h = 1e-6
            J = np.zeros((3, 3))
            for i, dv in enumerate((e1, e2)):
                f2 = miss(unit(w + h * dv), s)
                if f2 is None:
                    break
                J[:, i] = (f2 - f) / h
            f3 = miss(w, s + h)
            J[:, 2] = (f3 - f) / h
            try:
                dx = np.linalg.lstsq(J, -f, rcond=None)[0]
            except np.linalg.LinAlgError:
                break
            dx[:2] = np.clip(dx[:2], -0.4, 0.4)
            dx[2] = max(-25.0, min(25.0, dx[2]))
            w = unit(w + dx[0] * e1 + dx[1] * e2)
            s = s + dx[2]
        f = miss(w, s)
        if f is not None and np.linalg.norm(f) < 1e-7:
            ok = True
        if ok and s >= -1e-7:
            _, a1 = _arc_tip(t0, w, r1)
            _, a2 = _arc_tip(w, t1, r2)
            cand = (r1 * a1 + max(s, 0.0) + r2 * a2, w, max(s, 0.0), a1, a2)
            if best is None or cand[0] < best[0] - 1e-9:
                best = cand
    return best


# ---------------------------------------------------------------- the turtle ----------------------------------------
class Turtle:
    """A cable centreline built from straights and exact circular arcs.

        t = Turtle((0, 0, 0), (0, 0, 1)).line(5).arc(5, 90, toward=(1, 0, 0)).line(20)
        t.length(), t.min_radius(), t.points(0.5), t.p (position), t.h (heading)

    pieces: ("line", p0, p1, length) and ("arc", p0, centre, n, h0, r, angle_rad) with a point on the arc at angle f:
    centre - r n cos f + r h0 sin f."""

    def __init__(self, p, d, name: str = ""):
        self.p = np.asarray(p, float).copy()
        self.h = unit(d)
        self.p0 = self.p.copy()
        self.h0 = self.h.copy()
        self.pieces: list = []
        self.name = name

    def line(self, length: float):
        if length < -1e-9:
            raise ValueError(f"{self.name}: a straight of negative length {length:.3f}")
        if length > 1e-9:
            q = self.p + self.h * length
            self.pieces.append(("line", self.p.copy(), q.copy(), float(length)))
            self.p = q
        return self

    def arc(self, r: float, angle_deg: float, axis=None, toward=None):
        """Turn by angle_deg at radius r: about `axis` (right-hand rule, made perpendicular to the heading) or toward
        the direction `toward`."""
        if r <= 0:
            raise ValueError(f"{self.name}: an arc needs a radius above 0")
        th = math.radians(angle_deg)
        if abs(th) < 1e-12:
            return self
        if axis is not None:
            ax = np.asarray(axis, float)
            ax = ax - self.h * float(np.dot(ax, self.h))
            n = unit(np.cross(unit(ax), self.h))
            if th < 0:
                n, th = -n, -th
        elif toward is not None:
            tw = np.asarray(toward, float)
            n = unit(tw - self.h * float(np.dot(tw, self.h)))
            if th < 0:
                n, th = -n, -th
        else:
            raise ValueError(f"{self.name}: an arc needs 'axis' or 'toward'")
        h0 = self.h.copy()
        c = self.p + r * n
        self.pieces.append(("arc", self.p.copy(), c, n, h0, float(r), float(th)))
        self.p = c - r * n * math.cos(th) + r * h0 * math.sin(th)
        self.h = unit(h0 * math.cos(th) + n * math.sin(th))
        return self

    def to(self, p1, heading, r: float, r2: float | None = None, lead: float = 0.0):
        """Arc r, a straight, arc r2 to the pose (p1, heading of travel there); `lead` = straight kept before p1."""
        r2 = r if r2 is None else r2
        h1 = unit(heading)
        target = np.asarray(p1, float) - h1 * lead
        sol = solve_arc_line_arc(self.p, self.h, target, h1, r, r2)
        if sol is None:
            raise ValueError(f"{self.name}: no arc-straight-arc path of radius {r:g}/{r2:g} to {[round(float(v), 2) for v in target]}")
        _, w, s, a1, a2 = sol
        if a1 > 1e-9:
            self.arc(r, math.degrees(a1), toward=w)
        self.line(s)
        if a2 > 1e-9:
            self.arc(r2, math.degrees(a2), toward=h1)
        self.line(lead)
        return self

    # ---- measures
    def length(self) -> float:
        return float(sum(pc[3] if pc[0] == "line" else pc[5] * pc[6] for pc in self.pieces))

    def min_radius(self) -> float:
        return min((pc[5] for pc in self.pieces if pc[0] == "arc"), default=math.inf)

    def straight_start(self) -> float:
        tot = 0.0
        for pc in self.pieces:
            if pc[0] != "line":
                break
            tot += pc[3]
        return tot

    def straight_end(self) -> float:
        tot = 0.0
        for pc in reversed(self.pieces):
            if pc[0] != "line":
                break
            tot += pc[3]
        return tot

    def points(self, step: float = 0.5):
        pts = [self.p0]
        for pc in self.pieces:
            if pc[0] == "line":
                n = max(1, int(math.ceil(pc[3] / step)))
                for k in range(1, n + 1):
                    pts.append(pc[1] + (pc[2] - pc[1]) * k / n)
            else:
                _, _p0, c, nrm, h0, r, th = pc
                n = max(2, int(math.ceil(r * th / step)))
                for k in range(1, n + 1):
                    f = th * k / n
                    pts.append(c - r * nrm * math.cos(f) + r * h0 * math.sin(f))
        return np.array(pts)

    def text(self) -> str:
        out = []
        for pc in self.pieces:
            if pc[0] == "line":
                out.append(f"{pc[3]:.1f}")
            else:
                out.append(f"arc R{pc[5]:g} x {math.degrees(pc[6]):.0f} deg = {pc[5] * pc[6]:.1f}")
        return " + ".join(out)

    def wire(self):
        """The centreline as a CadQuery wire."""
        import cadquery as cq
        V = cq.Vector
        es = []
        for pc in self.pieces:
            if pc[0] == "line":
                es.append(cq.Edge.makeLine(V(*pc[1]), V(*pc[2])))
            else:
                _, p0, c, nrm, h0, r, th = pc
                done = 0.0
                while done < th - 1e-12:               # arcs above 170 degrees in parts
                    part = min(th - done, math.radians(170))
                    f0, f1, f2 = done, done + part / 2, done + part
                    pt = lambda f: c - r * nrm * math.cos(f) + r * h0 * math.sin(f)   # noqa: E731
                    es.append(cq.Edge.makeThreePointArc(V(*pt(f0)), V(*pt(f1)), V(*pt(f2))))
                    done += part
        return cq.Wire.assembleEdges(es)


# ---------------------------------------------------------------- routes file ---------------------------------------
def _pose(d, what):
    if not isinstance(d, dict) or "p" not in d or "d" not in d:
        raise mc.MechError(f"{what}: a pose needs p = [x, y, z] and d = [dx, dy, dz]")
    return np.asarray(d["p"], float), unit(d["d"])


def load_routes(path: str) -> list[dict]:
    """[{cable, key ('' = the whole cable), start, end, moves, allow, min_straight}]"""
    doc = mc.load_toml(path)
    out = []
    for c in doc.get("cable", []):
        cid = c.get("id")
        if not cid:
            raise mc.MechError(f"{path}: a [[cable]] without id")
        base = {"allow": list(c.get("allow", [])), "min_straight": c.get("min_straight")}
        if "moves" in c:
            out.append({"cable": cid, "key": "", "start": c.get("start"), "end": c.get("end"), "moves": c["moves"], **base})
        for w in c.get("wire", []):
            out.append({"cable": cid, "key": str(w.get("key", "")), "start": w.get("start", c.get("start")),
                        "end": w.get("end", c.get("end")), "moves": w.get("moves", []),
                        "allow": list(w.get("allow", base["allow"])), "min_straight": w.get("min_straight", base["min_straight"])})
    return out


def build_route(rd: dict) -> tuple:
    """(Turtle, end point, end leaving-direction). Raises ValueError / MechError with the reason."""
    name = rd["cable"] + (f" wire {rd['key']}" if rd["key"] else "")
    p0, d0 = _pose(rd["start"], name + " start")
    p1, d1 = _pose(rd["end"], name + " end")
    t = Turtle(p0, d0, name)
    for i, m in enumerate(rd["moves"]):
        if "line" in m:
            t.line(float(m["line"]))
        elif "arc" in m:
            t.arc(float(m["r"]), float(m["arc"]), axis=m.get("axis"), toward=m.get("toward"))
        elif m.get("to_end"):
            t.to(p1, -d1, float(m["r"]), m.get("r2"), float(m.get("lead", 0.0)))
        elif "to" in m:
            if "heading" not in m:
                raise mc.MechError(f"{name}: move {i + 1} 'to' needs heading = [..] (the direction of travel there)")
            t.to(m["to"], m["heading"], float(m["r"]), m.get("r2"), float(m.get("lead", 0.0)))
        else:
            raise mc.MechError(f"{name}: move {i + 1} is not line, arc, to or to_end")
    return t, p1, d1


# ---------------------------------------------------------------- model ---------------------------------------------
def dist_task(t):
    """(route name, solid name) -> distance between the centreline and the solid (worker process)."""
    import parcheck
    a, b = t
    return float(parcheck._shape(a).distance(parcheck._shape(b)))


def load_scene(job):
    """All solids of the model and the placed vendor parts: (name -> shape, [input paths]). Raises MechError."""
    import parcheck
    shapes, _meta, mpath = parcheck.load_model_shapes(job)
    inputs = [mpath]
    vp = mc.path_of(job.cfg, "vendor")
    if os.path.isfile(vp):
        try:
            import vendor_parts
            placed, _col = vendor_parts.place_all(job)
            for k, v in placed.items():
                shapes[k if k not in shapes else "vendor:" + k] = v
            inputs.append(vp)
        except Exception as e:                           # a broken vendor table must not hide the model
            print(f"  note: vendor parts not loaded ({e})")
    return shapes, inputs


def clearances(routes: dict, scene: dict, margin: float) -> dict:
    """routes: name -> (Turtle, od, allow patterns). Returns name -> [(solid, clearance mm)] sorted nearest first
    (clearance = centreline distance minus the cable radius), solids farther than `margin` + 5 mm left out."""
    import parcheck
    shapes, tasks = {}, []
    for rn, (tu, od, allow) in routes.items():
        w = tu.wire()
        shapes["route::" + rn] = w
        bb = w.BoundingBox()
        for sn, s in scene.items():
            if any(fnmatch.fnmatchcase(sn, a) for a in allow):
                continue
            if parcheck._bb_gap(bb, s.BoundingBox()) > od / 2 + margin + 5.0:
                continue
            shapes[sn] = s
            tasks.append(("route::" + rn, sn))
    out = {rn: [] for rn in routes}
    if not tasks:
        return out
    with parcheck.Pool(shapes) as pool:
        res = pool.map(dist_task, tasks, "clearance")
    for (rn, sn), d in zip(tasks, res):
        rn = rn[len("route::"):]
        out[rn].append((sn, d - routes[rn][1] / 2))
    for rn in out:
        out[rn].sort(key=lambda x: x[1])
    return out


def min_gap(a, b) -> float:
    """Smallest distance between two point lists (n x 3)."""
    best = math.inf
    for i in range(0, len(a), 400):
        d = np.linalg.norm(a[i:i + 400, None, :] - b[None, :, :], axis=2)
        best = min(best, float(d.min()))
    return best


def _outline_segments(scene: dict, max_edges: int = 6000):
    """Sampled edges of every solid as n x 3 arrays (a bounding box for very large shapes)."""
    segs = []
    for _name, s in scene.items():
        es = s.Edges()
        if len(es) > max_edges:
            b = s.BoundingBox()
            x0, x1, y0, y1, z0, z1 = b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax
            for z in (z0, z1):
                segs.append(np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]]))
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                segs.append(np.array([[x, y, z0], [x, y, z1]]))
            continue
        for e in es:
            n = 2 if e.geomType() == "LINE" else 13
            try:
                segs.append(np.array([[v.x, v.y, v.z] for v in (e.positionAt(k / (n - 1)) for k in range(n))]))
            except Exception:
                pass
    return segs


def picture(path: str, title: str, items: list, segs, note: str = "", names=None, targets=(), hits=None, others=()) -> None:
    """Top view and side view of one cable's routes over the model outline. items: [(label, Turtle, colour)];
    names: solid -> (xmin, xmax, ymin, ymax, zmin, zmax); targets: the required end points; hits: solids too near."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    allp = np.vstack([t.points(0.5) for _l, t, _c in items])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    side = 0 if (hi[0] - lo[0]) >= (hi[1] - lo[1]) else 1          # the side view looks along the shorter extent
    if segs:
        mp = np.vstack(segs)
        mlo, mhi = mp.min(axis=0), mp.max(axis=0)
    else:
        mlo, mhi = lo - 10, hi + 10
    mlo, mhi = np.minimum(mlo, lo) - 4, np.maximum(mhi, hi) + 4
    fig, axs = plt.subplots(1, 2, figsize=(15, 7.2), dpi=110)
    views = [((0, 1), "TOP VIEW (x right, y back)", "x (mm)", "y (mm)"),
             ((side, 2), f"SIDE VIEW ({'x' if side == 0 else 'y'} right, z up)", f"{'x' if side == 0 else 'y'} (mm)", "z (mm)")]
    for ax, ((i, j), ttl, xl, yl) in zip(axs, views):
        for s in segs:
            ax.plot(s[:, i], s[:, j], color="#6f7a86", lw=0.7, zorder=1)
        if (i, j) == (0, 1) and names and len(names) <= 30:
            for nm, b in names.items():
                ax.text(b[0] + 0.4, b[3] - 0.4, nm, fontsize=6.5, color="#4a5560", ha="left", va="top", zorder=2)
        for nm in (hits or ()):
            if names and nm in names:
                b = names[nm]
                ax.add_patch(plt.Rectangle((b[2 * i], b[2 * j]), b[2 * i + 1] - b[2 * i], b[2 * j + 1] - b[2 * j], fill=False, ec="#e07000", lw=1.6, ls="--", zorder=6))
        for tp in targets:
            ax.plot([tp[i]], [tp[j]], marker="x", color="black", ms=9, mew=1.8, zorder=7)
        for ot in others:
            op = ot.points(0.5)
            ax.plot(op[:, i], op[:, j], color="#555555", lw=1.3, ls=(0, (4, 2)), zorder=3)
        for lab, t, col in items:
            pts = t.points(0.3)
            ax.plot(pts[:, i], pts[:, j], color="white", lw=5.0, zorder=3, solid_capstyle="round")
            ax.plot(pts[:, i], pts[:, j], color=col, lw=2.6, zorder=4, solid_capstyle="round")
            ax.plot([pts[0, i]], [pts[0, j]], "o", color=col, ms=7, zorder=5)
            ax.plot([pts[-1, i]], [pts[-1, j]], "s", color=col, ms=7, zorder=5)
        ax.set_xlim(mlo[i], mhi[i])
        ax.set_ylim(mlo[j], mhi[j])
        ax.set_aspect("equal")
        ax.set_title(ttl, fontsize=11)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.grid(True, color="#e6e9ec", lw=0.5, zorder=0)
    handles = [plt.Line2D([0], [0], color=col, lw=2.6, label=lab) for lab, _t, col in items]
    handles += [plt.Line2D([0], [0], marker="o", color="#444444", lw=0, label="start (wire exit)"),
                plt.Line2D([0], [0], marker="s", color="#444444", lw=0, label="where the route ends"),
                plt.Line2D([0], [0], marker="x", color="black", lw=0, mew=1.8, label="required end (wire exit)")]
    if others:
        handles.append(plt.Line2D([0], [0], color="#555555", lw=1.3, ls=(0, (4, 2)), label="the other cables"))
    if hits:
        handles.append(plt.Line2D([0], [0], color="#e07000", lw=1.6, ls="--", label="nearer than the clearance"))
    fig.legend(handles=handles, loc="lower center", ncol=min(4, len(handles)), fontsize=9, frameon=False)
    fig.suptitle(title + (f"\n{note}" if note else ""), fontsize=12)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.14 + 0.03 * ((len(handles) - 1) // 4), wspace=0.14)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, metadata={"Software": ""})
    plt.close(fig)


PALETTE = ["#d62222", "#1f5fd0", "#1e9a3c", "#f08a1c", "#7d3fc0", "#0aa3a3", "#b0307a", "#6b6b00"]


# ---------------------------------------------------------------- run -----------------------------------------------
def run(job, a) -> tuple[mc.Rows, list]:
    cfg = cc.cable_cfg(job)
    rpath = mc.rel_to_project(job.cfg, a.routes or cfg["routes"])
    if not os.path.isfile(rpath):
        raise mc.MechError(f"no routes file at {rpath}")
    data, cpath = cc.load_cables(job, a.cables)
    types = cc.cable_types(data, cfg)
    by_id = {c.get("id"): c for c in data["cables"]}
    defs = [r for r in load_routes(rpath) if not a.only or r["cable"] == a.only]
    rows = mc.Rows()
    inputs = [rpath]            # not cables.json: this script writes into it (the FRESH row of the comparison guards it)
    rsha = mc.sha256(rpath)
    built = {}                                            # route name -> dict
    for rd in defs:
        rn = rd["cable"] + ("/" + rd["key"] if rd["key"] else "")
        sec = f"cable {rd['cable']}"
        cable = by_id.get(rd["cable"])
        if cable is None:
            rows.add(f"{rn}-ARRIVE", sec, "route belongs to a cable", "no such cable id in cables.json", "the id of a cable", "fail")
            continue
        try:
            t, p1, d1 = build_route(rd)
        except (ValueError, mc.MechError) as e:
            rows.add(f"{rn}-ARRIVE", sec, "route arrives at its end pose", f"the route cannot be built: {e}", "arrives", "fail")
            continue
        perr = float(np.linalg.norm(t.p - p1))
        aerr = math.degrees(angle_between(t.h, -d1))
        ok = perr <= float(cfg["arrive_tol_mm"]) and aerr <= float(cfg["arrive_tol_deg"])
        rows.add(f"{rn}-ARRIVE", sec, "route arrives at its end pose", f"off by {perr:.2f} mm and {aerr:.1f} deg",
                 f"within {cfg['arrive_tol_mm']:g} mm and {cfg['arrive_tol_deg']:g} deg", "pass" if ok else "fail")
        L = t.length()
        rows.add(f"{rn}-LEN", sec, "centreline length, wire exit to wire exit", f"{L:.2f} mm ({t.text()})",
                 "measured only when the route arrives", "pass" if ok else "fail")
        rmin, why = cc.min_bend(cable, types)
        found = t.min_radius()
        if rmin is None:
            rows.add(f"{rn}-BEND", sec, "smallest bend radius", f"R {found:.2f}; no minimum known: {why}", "at or above the cable's minimum", "could_not_run")
        else:
            rows.add(f"{rn}-BEND", sec, "smallest bend radius", "no bend" if math.isinf(found) else f"R {found:.2f} mm",
                     f">= R {rmin:g} ({why})", "pass" if found >= rmin - 1e-6 else "fail")
        ms = rd["min_straight"]
        ms = [float(cfg["min_straight_mm"])] * 2 if ms is None else ([float(ms)] * 2 if isinstance(ms, (int, float)) else [float(ms[0]), float(ms[1])])
        s0, s1 = t.straight_start(), t.straight_end()
        rows.add(f"{rn}-STRAIGHT", sec, "straight length leaving each connector", f"start {s0:.2f} mm, end {s1:.2f} mm",
                 f">= {ms[0]:g} mm at the start, >= {ms[1]:g} mm at the end", "pass" if s0 >= ms[0] - 1e-6 and s1 >= ms[1] - 1e-6 else "fail")
        od, odwhy = cc.cable_od(cable, types)
        built[rn] = {"t": t, "cable": rd["cable"], "key": rd["key"], "arrives": ok, "len": L, "od": od, "odwhy": odwhy,
                     "allow": rd["allow"], "sec": sec, "target": p1}

    # ---- clearance against the model
    scene, segs = None, []
    if a.no_model:
        why = "--no-model"
    else:
        try:
            scene, sin = load_scene(job)
            inputs += sin
            skip = cfg.get("skip_solids") or []
            scene = {k: v for k, v in scene.items() if not any(fnmatch.fnmatchcase(k, s) for s in skip)}
            why = ""
        except mc.MechError as e:
            why = str(e)
        except Exception as e:
            why = f"the model did not build: {type(e).__name__}: {e}"
    margin = float(cfg["clearance_mm"])
    if scene is None:
        for rn, b in built.items():
            rows.add(f"{rn}-CLEAR", b["sec"], "swept cable against the model", f"not measured: {why}", f">= {margin:g} mm to every solid", "could_not_run")
    else:
        todo = {rn: (b["t"], b["od"], b["allow"]) for rn, b in built.items() if b["od"] is not None}
        res = clearances(todo, scene, margin) if todo else {}
        for rn, b in built.items():
            if b["od"] is None:
                rows.add(f"{rn}-CLEAR", b["sec"], "swept cable against the model", f"no cable diameter: {b['odwhy']}", f">= {margin:g} mm", "could_not_run")
                continue
            near = res.get(rn, [])
            hits = [(s, c) for s, c in near if c < margin - 1e-6]
            b["hits"] = [s for s, _c in hits]
            if hits:
                val = "; ".join(f"{s}: {c:.2f} mm" + (" (passes through)" if c < 0 else "") for s, c in hits[:6])
            elif near:
                val = f"nearest {near[0][0]}: {near[0][1]:.2f} mm"
            else:
                val = f"nothing within {margin + 5:g} mm"
            rows.add(f"{rn}-CLEAR", b["sec"], f"swept cable (OD {b['od']:g}) against {len(scene)} solids", val,
                     f">= {margin:g} mm to every solid except its own connectors ({', '.join(b['allow']) or 'none listed'})",
                     "fail" if hits else "pass")
        if not a.no_pictures:
            try:
                segs = _outline_segments(scene)
            except Exception:
                segs = []

    # ---- crossings
    gap = float(cfg["cable_gap_mm"])
    names = [rn for rn in built if built[rn]["od"] is not None]
    pts = {rn: built[rn]["t"].points(0.25) for rn in names}
    n = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            x, y = built[names[i]], built[names[j]]
            if x["cable"] == y["cable"]:
                continue                                   # wires of one cable lie together
            n += 1
            d = min_gap(pts[names[i]], pts[names[j]]) - (x["od"] + y["od"]) / 2
            rows.add(f"CROSS-{names[i]}-{names[j]}", "crossings", f"{names[i]} against {names[j]}", f"{d:.2f} mm between the two cables",
                     f">= {gap:g} mm (they do not pass through each other)", "pass" if d >= gap - 0.02 else "fail")
    if n == 0:
        rows.add("CROSS-000", "crossings", "cables against each other", "fewer than two routed cables", "no two cables cross", "na")

    # ---- results into cables.json
    key_len = "b" if a.second else "a"
    changed = False
    for cid in dict.fromkeys(b["cable"] for b in built.values()):
        mine = {rn: b for rn, b in built.items() if b["cable"] == cid}
        cable = by_id[cid]
        if not all(b["arrives"] for b in mine.values()):
            continue
        r = cable.setdefault("route", {})
        wires = r.setdefault("wires", {})
        for b in mine.values():
            if b["key"]:
                wires.setdefault(b["key"], {})[key_len] = round(b["len"], 2)
        if not wires:
            r.pop("wires", None)
        r[f"measure_{key_len}_mm"] = round(max(b["len"] for b in mine.values()), 2)
        r[f"smallest_r_{key_len}"] = None if all(math.isinf(b["t"].min_radius()) for b in mine.values()) else \
            round(min(b["t"].min_radius() for b in mine.values()), 2)
        if not a.second:
            r["a_source"] = {"routes_sha256": rsha}
        changed = True
    if changed and not a.no_write:
        if cc.save_cables(cpath, data):
            print(f"  wrote route.measure_{key_len}_mm into {cpath}")
        else:
            print(f"  {cpath} unchanged: not rewritten")

    # ---- pictures
    pics = []
    if not a.no_pictures and built:
        try:
            for cid in dict.fromkeys(b["cable"] for b in built.values()):
                mine = [(rn, b) for rn, b in built.items() if b["cable"] == cid]
                items = [(f"{rn}: {b['len']:.2f} mm" + ("" if b["arrives"] else " (DOES NOT ARRIVE)"), b["t"], PALETTE[k % len(PALETTE)])
                         for k, (rn, b) in enumerate(mine)]
                p = os.path.join(job.out, "cables", f"route_{cid}{'_second' if a.second else ''}.png")
                names = None
                if scene is not None:
                    names = {}
                    for k_, s_ in scene.items():
                        bb = s_.BoundingBox()
                        names[k_] = (bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax)
                picture(p, f"Route of {cid}", items, segs, "" if scene is not None else "model not loaded: route only", names,
                        targets=[b["target"] for _rn, b in mine], hits=sorted({h for _rn, b in mine for h in b.get("hits", [])}),
                        others=[b["t"] for b in built.values() if b["cable"] != cid])
                pics.append(p)
        except ImportError:
            print("  note: matplotlib is missing, no route pictures")
    return rows, inputs + [], pics


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cable routes measured in the model.", epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--routes", help="routes file (default [cables] routes = cables/routes.toml)")
    ap.add_argument("--cables", help="the cable data file")
    ap.add_argument("--second", action="store_true", help="write measure_b_mm instead of measure_a_mm")
    ap.add_argument("--only", help="one cable id")
    ap.add_argument("--no-model", action="store_true", help="geometry rows only")
    ap.add_argument("--no-write", action="store_true", help="do not write into cables.json")
    ap.add_argument("--no-pictures", action="store_true")
    a = ap.parse_args(argv)
    if not a.no_model:
        mc.reexec_with_cadquery()
    if np is None:
        print("could not run: the Python library 'numpy' is missing")
        return 2
    try:
        job = mc.resolve(a)
        rows, inputs, pics = run(job, a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(job.out, "cable_route_second.py" if a.second else "cable_route.py", inputs)
    for p in pics:
        print("  picture:", p)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
