"""Layout helpers: building blocks for a project's own board script (src/build_board.py). A first pass, not an
automatic layout tool.

    board    a KiCad board from a netlist: outline, holes with keep-outs, free bands, layer count, footprints
    place    fixed parts, blocks around an anchor, a packer for the small parts, label room, a placement plot
    copper   hand-planned copper from a description: zones, tracks, vias, keep-outs, stitching vias
    route    a grid router for what is left (simple and medium boards only: read its limits)
    repair   close what the router left open, tie ground islands, remove dangling vias and track ends
    fill     zone fill in its own process, then a check of the saved file

Ported from the tools of one board and tested lightly: treat every result as a first pass, run the checks
(scripts/drc_run.py and the others) on the saved board, and look at the render. The rules, checks and reviews of
the skill do not depend on these helpers. How to use them, the lessons on route order and escapes, and the limits:
README.md in this folder.

All coordinates are KiCad's own: millimetres, x to the right, y downwards, as the board editor shows them.
board, place, copper and route need KiCad's Python (pcbnew): a project script calls kicad_io.need_kicad_python()
before it imports them. fill.py and repair.py are also command-line tools that start KiCad's Python themselves;
from a script, fill.fill() runs under any Python and repair.repair() needs KiCad's.

No window, ever: quiet_wx() sends KiCad's log to stderr. Every helper here calls it before its first pcbnew call;
a script of your own that uses pcbnew directly calls layout.quiet_wx() first.
board_outline() is the one call for a board's outline that works in KiCad 9 and KiCad 10.
"""

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

_WX_LOG = None                      # kept alive: the log target that replaces KiCad's message boxes


def board_outline(board):
    """The outline of a board as KiCad builds it from Edge.Cuts: a SHAPE_POLY_SET, or None when the drawing is
    not closed. (KiCad 10 wants a second argument, "infer an outline when there is none": never.)"""
    import pcbnew
    ps = pcbnew.SHAPE_POLY_SET()
    try:
        ok = board.GetBoardPolygonOutlines(ps)
    except TypeError:
        ok = board.GetBoardPolygonOutlines(ps, False)
    return ps if ok and ps.OutlineCount() else None


def quiet_wx() -> str:
    """Call before the first pcbnew call of a process. In KiCad's Python every message of KiCad's wxWidgets log
    (a font that is missing, a file of another version, a footprint that warns) becomes a modal message box on
    the user's screen that blocks the script until somebody clicks it. This sends the log to stderr instead.
    Returns what was done, as a short text. Safe to call again and in a Python without wxPython."""
    global _WX_LOG
    if _WX_LOG is not None:
        return "wx log already sent to stderr"
    try:
        import wx
    except Exception as e:                                      # noqa: BLE001  no wxPython in this Python
        return f"wx not importable ({type(e).__name__}): nothing to redirect"
    try:
        wx.DisableAsserts()                                     # a failed assertion inside KiCad opens a box too
    except Exception:                                           # noqa: BLE001
        pass
    try:
        _WX_LOG = wx.LogStderr()
        wx.Log.SetActiveTarget(_WX_LOG)
        wx.Log.SetLogLevel(wx.LOG_Info)                         # errors, warnings and messages; no debug chatter
        return "wx log sent to stderr"
    except Exception as e:                                      # noqa: BLE001
        try:
            wx.Log.EnableLogging(False)
            return f"wx log switched off (the stderr target failed: {e})"
        except Exception as e2:                                 # noqa: BLE001
            return f"the wx log could not be redirected ({e2})"
