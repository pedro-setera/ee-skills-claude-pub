"""Wired-schematic writer of the electronics-design skill.

    svclib    the drawing library (Doc, Sheet) with the lint that stops the build
    symbols   the symbol library (stock symbols, IC boxes, connectors, rails)
    export    netlist, rule check, PDF and one image per sheet, for this library's projects and for any other KiCad schematic
    example_two_sheets   a small worked example

Sheet scripts of a project put this package's parent folder (scripts/) on the import path and write
`from schematic import svclib, symbols`.
"""

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started
