"""Writes an invented 60 x 40 mm example board for trying the fit check: interface.json (the format of the electronics
skill) and the board's STEP, with checksums. Not a design: a fixture.

    python -I make_example_board.py <mech folder> [--tall] [--part-at-hole] [--shift-hole MM]
      --tall            a 14 mm tall capacitor (over the 12 mm zone limit: the height row fails)
      --part-at-hole    a part over hole H1's screw-head space (the head row fails)
      --shift-hole MM   the stand of H1 is built MM away from the hole (the stand row fails): this only moves the
                        HOLE in the interface; the model keeps the old stand

Frame as the electronics skill writes it: x right, y DOWN from the top-left corner of the outline; the STEP in the
board file's frame (x as in the file, y negated, z = 0 at the bottom face); kicad_origin_in_this_frame records the shift.
"""

import argparse
import json
import os
import sys

sys.dont_write_bytecode = True     # importing the skill's scripts must not leave __pycache__ in the skill folder
_S = os.environ.get("MECH_SCRIPTS") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
if _S not in sys.path:
    sys.path.insert(0, _S)

import mech_common as mc  # noqa: E402


def make(mech_dir, tall=False, part_at_hole=False, shift_hole=0.0):
    import cadquery as cq
    os.makedirs(os.path.join(mech_dir, "3d"), exist_ok=True)
    ox, oy = 100.0, 100.0                          # the board file's coordinates of the outline's top-left corner
    holes = [("H1", 4.0, 4.0), ("H2", 56.0, 4.0), ("H3", 4.0, 36.0), ("H4", 56.0, 36.0)]   # interface frame, y down
    # parts in the interface frame: (ref, x0, y0, x1, y1, z0, z1)
    parts = [("J1", 20.0, 34.0, 32.0, 42.0, 1.6, 5.6),           # hangs 2 mm over the bottom edge (the front of the box)
             ("C1", 40.0, 10.0, 46.0, 16.0, 1.6, 1.6 + (14.0 if tall else 9.0)),
             ("U1", 24.0, 8.0, 32.0, 16.0, 1.6, 4.0)]
    if part_at_hole:
        parts.append(("U2", 1.0, 1.0, 8.0, 7.0, 1.6, 6.0))       # over hole H1
    shapes = []
    body = cq.Workplane("XY").box(60, 40, 1.6, centered=False).translate((ox, -(oy + 40), 0)).val()
    shapes.append(body)
    for ref, x0, y0, x1, y1, z0, z1 in parts:
        # interface (x, y down) -> file frame (x + ox, y_k = y + oy) -> STEP (X = x_k, Y = -y_k)
        shapes.append(cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((ox + x0, -(oy + y1), z0)).val())
    step = os.path.join(mech_dir, "3d", "example_board.step")
    cq.exporters.export(cq.Workplane("XY").add(cq.Compound.makeCompound(shapes)), step, "STEP")
    hs = [{"name": n, "x": x + (shift_hole if n == "H1" else 0.0), "y": y, "d": 2.7, "plated": False, "net": None} for n, x, y in holes]
    conns = [{"ref": "J1", "value": "USB", "side": "top", "x": 26.0, "y": 38.0, "rotation": 0, "box": [20.0, 34.0, 32.0, 40.0],
              "body_box": [20.0, 34.0, 32.0, 42.0], "body_z": [1.6, 5.6], "height": 4.0}]
    itf = {"generated_by": "make_example_board.py", "board_file": "example.board", "board_file_sha256": "0" * 64,
           "step_file": "3d/example_board.step", "step_sha256": mc.sha256(step), "units": "mm",
           "frame": {"description": "example", "origin": "top-left corner of the outline box", "y": "down", "offset": [0.0, 0.0],
                     "kicad_origin_in_this_frame": [-ox, -oy]},
           "outline_box": [0.0, 0.0, 60.0, 40.0], "size": [60.0, 40.0], "outline": [[[0, 0], [60, 0], [60, 40], [0, 40]]],
           "thickness": 1.6, "holes": hs, "connectors": conns, "parts": [], "heights_measured": True,
           "tallest_part": {"top": {"ref": "C1", "height": 14.0 if tall else 9.0}}, "notes": []}
    p = os.path.join(mech_dir, "interface.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(itf, f, indent=1)
    return p, step


if __name__ == "__main__":
    mc.reexec_with_cadquery()
    ap = argparse.ArgumentParser()
    ap.add_argument("mech_dir")
    ap.add_argument("--tall", action="store_true")
    ap.add_argument("--part-at-hole", action="store_true")
    ap.add_argument("--shift-hole", type=float, default=0.0)
    a = ap.parse_args()
    print(*make(a.mech_dir, a.tall, a.part_at_hole, a.shift_hole), sep="\n")
