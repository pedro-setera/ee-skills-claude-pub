"""Reads the board interface file of the electronics skill, verifies its checksums, and writes the mechanical input back.

What it does
    - Reads `mech/interface.json` (outline, thickness, holes, connectors, named parts, tallest parts, the SHA-256 of the
      board file and of the board STEP) and prints a summary.
    - Verifies the checksums when the files are reachable (the paths in the file are relative to the file): a changed
      board or STEP gives exit 1 "regenerate the interface". Unreachable files are reported as not verified.
    - `--compare other.json`: outline box and holes equal within 0.011 mm?
    - `--write-outline desc.toml`: writes `outline.json` (the mechanical input of the electronics skill's board
      definition) from a small TOML description: outline, holes with the keep-out diameter (screw head, stand, tool),
      edge bands, keep-out areas.
    - Importable: `load_interface(path) -> dict`, `to_box(interface, placement) -> f(x, y, z)`,
      `step_transform(interface, placement) -> list of operations` (used by fit_check.py).

Why it exists (the real failure, told without names)
    The numbers of a board (hole positions, a connector's mating face, the tallest part) were typed by hand into the
    box model and drifted from the board over several layout rounds; a connector ended up inside a screw's tool space.
    One generated file with both checksums, read by one reader, makes a stale file visible at once.

Usage
    python -I interface_read.py [--project <mech folder>] [interface.json]
    python -I interface_read.py ... --compare other.json
    python -I interface_read.py --write-outline desc.toml [--out outline.json]
    desc.toml:
        [outline]   rect = [x0, y0, x1, y1]  (or polygon = [[x, y], ...]),  corner_radius = 1.0
        [defaults]  screw = "M2.5", margin = 0.5, tool_d = 6.0      # keep-out = max(head, stand, tool) + margin
        [[holes]]   name = "H1", x = 5, y = 5, d = 2.7, plated = false, screw = "M3", stand_d = 6.0, tool_d = 6.0, keepout_d = 9.0
        [[bands]]   name = "rail", edge = "left", width = 1.5, span = [0, 40]     (or line = [x0, y0, x1, y1])
        [[areas]]   name = "lid screw", rect = [x0, y0, x1, y1], no = ["parts", "tracks"]
    Placement of a board in the box (used by to_box): {"origin": [x, y, z], "rot_z": 0, "y_flip": "auto"}: origin is
    the box-frame position of the board's frame origin at its bottom face; an interface frame with y down is turned so
    that the board seen from the top has its top edge at the back (higher y).

Config keys (mech.toml)
    [paths] interface (default interface.json)

Exit codes
    0 read, checksums agree (or not reachable)   1 a checksum differs / --compare differs   2 could not run
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402


def load_interface(path) -> dict:
    """The interface dict (a wrapper with an "interface" key is unwrapped). Raises mc.MechError."""
    path = str(path)
    if not os.path.isfile(path):
        raise mc.MechError(f"no interface file at {path}")
    try:
        d = mc.load_json(path)
    except ValueError as e:
        raise mc.MechError(f"{path} is not valid JSON: {e}")
    d = d.get("interface", d)
    for k in ("outline_box", "holes"):
        if k not in d:
            raise mc.MechError(f"{path}: the key '{k}' is missing; this is not an interface file")
    d["_path"] = os.path.abspath(path)
    return d


def _file(itf, key):
    rel = itf.get(key)
    if not rel:
        return None
    return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(os.path.dirname(itf["_path"]), rel))


def step_path(itf) -> str | None:
    return _file(itf, "step_file")


def verify(itf, rows: mc.Rows) -> None:
    for what, kfile, ksha in (("board file", "board_file", "board_file_sha256"), ("board STEP", "step_file", "step_sha256")):
        p, rec = _file(itf, kfile), itf.get(ksha)
        cid = "IF-BRD" if what == "board file" else "IF-STP"
        if not rec:
            rows.add(cid, "interface", f"{what} checksum recorded", "none in the file", "the file records a SHA-256", "fail")
        elif not p or not os.path.isfile(p):
            rows.add(cid, "interface", f"{what} unchanged", f"not reachable at {p}", "checksum equal to the recorded one", "na")
        else:
            now = mc.sha256(p)
            rows.add(cid, "interface", f"{what} unchanged", "equal" if now == rec else f"changed (file {now[:12]}, recorded {rec[:12]})",
                     "checksum equal to the recorded one; if changed: regenerate the interface", "pass" if now == rec else "fail")


# ---------------------------------------------------------------- frames ---------------------------------------------
def _y_down(itf) -> bool:
    return str(itf.get("frame", {}).get("y", "up")) == "down"


def _flip(itf, placement) -> bool:
    f = (placement or {}).get("y_flip", "auto")
    return _y_down(itf) if f == "auto" else bool(f)


def to_box(itf, placement=None):
    """f(x, y, z) of the interface frame -> the box frame. placement: origin [x, y, z], rot_z (deg), y_flip."""
    import math
    pl = placement or {}
    ox, oy, oz = pl.get("origin", (0.0, 0.0, 0.0))
    a = math.radians(pl.get("rot_z", 0.0))
    ca, sa = math.cos(a), math.sin(a)
    b = itf["outline_box"]
    s = b[1] + b[3]
    flip = _flip(itf, pl)

    def f(x, y, z=0.0):
        yy = s - y if flip else y
        return (ox + x * ca - yy * sa, oy + x * sa + yy * ca, oz + z)
    return f


def step_transform(itf, placement=None) -> list:
    """Operations that bring the board's STEP (exported by the electronics skill: x as in the board file, y negated,
    z = 0 at the bottom face) into the box frame: a list of ("mirror_xz",) | ("translate", x, y, z) | ("rotate_z", deg)."""
    pl = placement or {}
    fr = itf.get("frame", {})
    ops = []
    k = fr.get("kicad_origin_in_this_frame")
    top_left = str(fr.get("origin", "")).startswith("top-left")
    if k is not None:
        if top_left:
            ops.append(("mirror_xz",))                     # y_if = -Y + oy
        ops.append(("translate", k[0], k[1], 0.0))
    if _flip(itf, pl):
        b = itf["outline_box"]
        ops += [("mirror_xz",), ("translate", 0.0, b[1] + b[3], 0.0)]
    if pl.get("rot_z"):
        ops.append(("rotate_z", pl["rot_z"]))
    o = pl.get("origin", (0.0, 0.0, 0.0))
    ops.append(("translate", o[0], o[1], o[2]))
    return ops


# ---------------------------------------------------------------- summary / compare ----------------------------------
def summary(itf) -> list[str]:
    b = itf["outline_box"]
    L = [f"outline box {b}, {b[2] - b[0]:.2f} x {b[3] - b[1]:.2f} mm, thickness {itf.get('thickness')}, "
         f"frame: {itf.get('frame', {}).get('origin', '?')}, y {itf.get('frame', {}).get('y', '?')}",
         f"{len(itf['holes'])} mounting hole(s): " + "; ".join(f"{h['name']} ({h['x']}, {h['y']}) d {h['d']}" + ("" if h.get("plated") is None else (" plated" if h["plated"] else "")) for h in itf["holes"])]
    conns = itf.get("connectors", [])
    L.append(f"{len(conns)} connector(s):")
    for c in conns:
        L.append(f"   {c['ref']:6} side {c.get('side')}  box {c.get('box')}  height {c.get('height')}")
    parts = itf.get("parts", [])
    if parts:
        L.append(f"{len(parts)} named part(s): " + ", ".join(p["ref"] for p in parts))
    t = itf.get("tallest_part") or {}
    L.append("tallest: " + ("; ".join(f"{k} {v.get('ref')} {v.get('height')} mm" for k, v in t.items()) if t else "not measured"))
    for n in itf.get("notes", []):
        L.append("note: " + str(n))
    return L


def compare(a, b) -> list[str]:
    diffs = []
    if any(abs(x - y) > 0.011 for x, y in zip(a["outline_box"], b["outline_box"])):
        diffs.append(f"outline box {a['outline_box']} against {b['outline_box']}")
    oh = {h["name"]: h for h in b.get("holes", [])}
    for h in a["holes"]:
        o = oh.get(h["name"])
        if o is None:
            diffs.append(f"hole {h['name']} is not in the other file")
        elif max(abs(o["x"] - h["x"]), abs(o["y"] - h["y"]), abs(o["d"] - h["d"])) > 0.011:
            diffs.append(f"hole {h['name']}: ({h['x']}, {h['y']}) d {h['d']} against ({o['x']}, {o['y']}) d {o['d']}")
    names = {h["name"] for h in a["holes"]}
    diffs += [f"hole {n} of the other file is not in this one" for n in oh if n not in names]
    ca, cb = {c["ref"]: c for c in a.get("connectors", [])}, {c["ref"]: c for c in b.get("connectors", [])}
    for r in sorted(set(ca) | set(cb)):
        if r not in ca or r not in cb:
            diffs.append(f"connector {r} is only in one file")
        elif any(abs(x - y) > 0.011 for x, y in zip(ca[r]["box"], cb[r]["box"])):
            diffs.append(f"connector {r} box {ca[r]['box']} against {cb[r]['box']}")
    return diffs


# ---------------------------------------------------------------- outline.json ---------------------------------------
def make_outline(desc: dict) -> dict:
    """Build the mechanical input from the description dict (see the module docstring)."""
    import box_toolkit as bt
    out = {}
    o = desc.get("outline")
    if not o or not ("rect" in o or "polygon" in o):
        raise mc.MechError("the description needs [outline] rect = [x0, y0, x1, y1] or polygon = [[x, y], ...]")
    out["outline"] = {k: o[k] for k in ("rect", "polygon", "corner_radius") if k in o}
    dflt = desc.get("defaults", {})
    margin = float(dflt.get("margin", 0.5))
    holes = []
    for i, h in enumerate(desc.get("holes", [])):
        screw = h.get("screw", dflt.get("screw", "M2.5"))
        sd = bt.SCREWS.get(screw)
        if sd is None and "keepout_d" not in h:
            raise mc.MechError(f"hole {h.get('name', i + 1)}: unknown screw {screw!r} and no keepout_d")
        head = h.get("head_d", sd["head_d"] if sd else 0.0)
        stand = h.get("stand_d", sd["post_d"] if sd else 0.0)
        tool = h.get("tool_d", dflt.get("tool_d", 6.0))
        ko = h.get("keepout_d", round(max(head, stand, tool) + margin, 2))
        e = {"name": h.get("name", f"H{i + 1}"), "x": h["x"], "y": h["y"], "d": h["d"], "keepout_d": ko}
        for k in ("plated", "pad_d", "net"):
            if k in h:
                e[k] = h[k]
        holes.append(e)
    out["holes"] = holes
    ko = []
    for b in desc.get("bands", []):
        e = {"kind": "band", "name": b["name"], "width": b["width"]}
        for k in ("edge", "span", "line"):
            if k in b:
                e[k] = b[k]
        if "edge" not in e and "line" not in e:
            raise mc.MechError(f"band {b['name']}: give edge or line")
        ko.append(e)
    for a in desc.get("areas", []):
        e = {"kind": "area", "name": a["name"]}
        for k in ("rect", "polygon", "no", "layers"):
            if k in a:
                e[k] = a[k]
        if "rect" not in e and "polygon" not in e:
            raise mc.MechError(f"area {a['name']}: give rect or polygon")
        ko.append(e)
    out["keepouts"] = ko
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read the board interface file, verify its checksums, write outline.json.",
                                 epilog="Exit codes: 0 ok, 1 stale or different, 2 could not run.")
    ap.add_argument("interface", nargs="?", help="interface.json (default <project>/interface.json)")
    ap.add_argument("--project")
    ap.add_argument("--out", help="output folder for the check file; with --write-outline the outline.json path")
    ap.add_argument("--compare")
    ap.add_argument("--write-outline", metavar="DESC.TOML")
    a = ap.parse_args(argv)
    try:
        if a.write_outline:
            desc = mc.load_toml(a.write_outline)
            data = make_outline(desc)
            target = a.out or os.path.join(os.path.dirname(os.path.abspath(a.write_outline)), "outline.json")
            if os.path.isdir(target):
                target = os.path.join(target, "outline.json")
            mc.atomic_write(target, json.dumps(data, indent=1) + "\n")
            print(f"wrote {target}: {len(data['holes'])} hole(s), {len(data['keepouts'])} keep-out(s)")
            return 0
        if a.interface:
            ipath, out = a.interface, os.path.abspath(a.out or os.path.join(os.path.dirname(os.path.abspath(a.interface)), "out"))
        else:
            job = mc.resolve(a)
            ipath, out = mc.path_of(job.cfg, "interface"), job.out
        itf = load_interface(ipath)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows = mc.Rows()
    verify(itf, rows)
    for ln in summary(itf):
        print(ln)
    if a.compare:
        try:
            other = load_interface(a.compare)
        except mc.MechError as e:
            print("could not run:", e)
            return 2
        d = compare(itf, other)
        for x in d:
            print("DIFFERENT:", x)
        rows.add("IF-CMP", "interface", "compared with " + os.path.basename(a.compare), "equal" if not d else f"{len(d)} difference(s)",
                 "outline, holes and connectors equal", "pass" if not d else "fail")
    rows.print_table(only_bad=False)
    rows.write(out, "interface_read.py", [ipath] + [p for p in (_file(itf, "board_file"), _file(itf, "step_file")) if p])
    print(rows.headline())
    if rows.counts()["fail"]:
        print("the interface file is stale or different: regenerate the interface in the electronics skill and read it again")
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
