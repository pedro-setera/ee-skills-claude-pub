"""Example parametric box model: a 120 x 80 x 40 mm two-part printed box for an invented 60 x 40 mm board.

Copy this folder to <project>/mech/model/ and change the NAMED VALUES below. The contract the scripts rely on:
    build() -> dict of name -> CadQuery shape (every solid of the assembly, in the box frame)
    PLACEMENTS -> where each board sits: {"board": {"origin": [x, y, z], "rot_z": 0}}   (origin = the board's frame
                  origin at its bottom face, in the box frame)
Frame: origin at the outer front-left-bottom corner, x right, y back, z up, mm.
Stands are named "stand_<hole name>" so fit_check.py finds them; lid access holes sit over the board's holes.

Run it alone:  python -I build_model.py          (prints the solids and their volumes)
"""

import os
import sys

sys.dont_write_bytecode = True     # importing the skill's scripts must not leave __pycache__ in the skill folder

_S = os.environ.get("MECH_SCRIPTS") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
if _S not in sys.path:
    sys.path.insert(0, _S)

import box_toolkit as bt  # noqa: E402

# ---- named values ------------------------------------------------------------------------------------------------
W, D, H = 120.0, 80.0, 40.0          # outer size
WALL = 2.0                           # wall, floor and lid thickness
LID_T = 2.0                          # lid plate
LIP = 2.0                            # the lid's lip that dips into the shell
SHELL_H = H - LID_T                  # shell height (the lid plate sits on top)
BOARD_ORIGIN = (30.0, 4.0, 6.0)      # board frame origin (bottom face) in the box
STAND_H = BOARD_ORIGIN[2] - WALL     # stand height from the floor to the board's bottom face
SCREW = "M2.5"
ACCESS_D = 6.5                       # lid hole over each board hole (screwdriver)

PLACEMENTS = {"board": {"origin": list(BOARD_ORIGIN), "rot_z": 0, "column_top": H}}

# a board seen from above is 60 x 40; its interface file lists the holes; the stands come from it when it exists
_HOLES_FALLBACK = {"H1": (4.0, 36.0), "H2": (56.0, 36.0), "H3": (4.0, 4.0), "H4": (56.0, 4.0)}  # board frame, y up


def _interface():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "interface.json")
    if os.path.isfile(p):
        import interface_read as ir
        return ir.load_interface(p)
    return None


def build():
    # shell: a tray with a lip seat
    shell = bt.box(0, 0, 0, W, D, SHELL_H)
    shell = shell.cut(bt.box(WALL, WALL, WALL, W - WALL, D - WALL, SHELL_H + 1))
    # openings: front rectangular connector, back round jack
    shell = bt.panel_cutouts(shell, "front", [{"kind": "rect", "u": 56.0, "v": 9.6, "w": 14.0, "h": 8.0, "r": 0.5}], WALL, (W, D, H))
    shell = bt.panel_cutouts(shell, "back", [{"kind": "round", "u": 100.0, "v": 20.0, "d": 8.0}], WALL, (W, D, H))
    # a vent field in the back wall: a complete matrix that moves as a whole around the jack
    vent = bt.hex_field((12.0, 8.0, 88.0, 32.0), pitch=5.0, d=3.0, cols=8, rows=3,
                        forbid=[(100.0, 20.0, 6.0)], clearance=1.0, edge_margin=1.0)
    shell = bt.panel_cutouts(shell, "back", [{"kind": "round", "u": u, "v": v, "d": 3.0} for u, v in vent], WALL, (W, D, H))
    # stands at the board's holes
    itf = _interface()
    if itf:
        stands = bt.stands_from_interface(itf, WALL, STAND_H, SCREW, placement=PLACEMENTS["board"])
    else:
        stands = {}
        for n, (hx, hy) in _HOLES_FALLBACK.items():
            stands["stand_" + n] = bt.stand((BOARD_ORIGIN[0] + hx, BOARD_ORIGIN[1] + hy, WALL), STAND_H, SCREW)
    # lid: plate + lip, with a screwdriver access hole over each stand
    lid = bt.box(0, 0, SHELL_H, W, D, H).fuse(bt.box(WALL + 0.2, WALL + 0.2, SHELL_H - LIP, W - WALL - 0.2, D - WALL - 0.2, SHELL_H))
    lid = lid.cut(bt.box(WALL + 2.2, WALL + 2.2, SHELL_H - LIP - 1, W - WALL - 2.2, D - WALL - 2.2, SHELL_H - 0.0 + 0.0))
    for st in stands.values():
        c = st.BoundingBox()
        lid = lid.cut(bt.cyl(((c.xmin + c.xmax) / 2, (c.ymin + c.ymax) / 2, SHELL_H - LIP - 1), ACCESS_D, LID_T + LIP + 2))
    out = {"shell": shell, "lid": lid}
    out.update(stands)
    return out


if __name__ == "__main__":
    import mech_common as mc
    mc.reexec_with_cadquery()
    for k, v in build().items():
        print(f"{k:12} volume {v.Volume():9.1f} mm3")
