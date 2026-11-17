"""A small worked example of the wired-schematic library: one generic circuit on two sheets.

    Sheet 1  USB-C 5 V input (connector, CC pull-downs, resettable fuse, clamp diode) and a 3.3 V regulator
    Sheet 2  host connector with I2C pull-ups, a temperature / humidity sensor, a status LED

It is the pattern for a project's own sheet scripts (kept in the project's src/ folder): the parts table once,
one function per sheet that says where each symbol sits and how each wire runs, then the build: lint, write the
KiCad project, export netlist, rule check, PDF and one image per sheet. Copy it, do not import it.
In a larger project page 1 is the overview (block diagram, power tree, sheet index, test-point and connector
tables) and the circuit starts on page 2; here page 1 already carries a circuit to keep the example short.

Usage
    python -I scripts/schematic/example_two_sheets.py --out FOLDER
        writes FOLDER/kicad/ (the KiCad project) and FOLDER/out/ (netlist.net, erc_report.json,
        example_node-schematic.pdf, schematic-1-root.png, schematic-2-sensor-host-connector-and-status-led.png,
        schematic_export.md / .json)
    --scripts FOLDER  the skill's scripts folder; a copy of this file in a project's src/ folder needs it
    --no-export     only write the KiCad project
    --bw           plot in black and white (to see that the sheets still read without colour)
    --demo-lint     plant the classic defect: a node on sheet 2 gets the name of a different node on sheet 1.
                    The lint must stop the build: nothing is written, exit code 1.

Where the numbers on the sheets come from (in a real project: the design note and the datasheets, each named
here with its table or page; this example uses round figures and says so):
    - VBUS 5.0 V nominal: USB default supply. R1, R2 5.1 kOhm on CC1 / CC2: the pull-downs with which a USB-C
      sink asks a source for 5 V.
    - F1 hold current 0.5 A, D1 5 V stand-off: example values.
    - +3V3 3.3 V: the fixed output of the example regulator U1; 0 V when EN_3V3 is pulled low.
    - LED: (3.3 V - 2.0 V) / 1 kOhm = 1.3 mA with an assumed forward voltage of 2.0 V.
    Pin tables of the ICs (in a real project: copied from each datasheet's pin table, named here):
    - U1, regulator in a 5-pin package: 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT.
    - U2, sensor in a 4-pad package: 1 SDA, 2 SCL, 3 VDD, 4 VSS.
    - J1, USB-C power-only receptacle with 6 contacts: A9 / B9 VBUS, A5 CC1, B5 CC2, A12 / B12 GND, S1 shell
      (the pad names of the footprint in the parts table).

board.toml keys: none (an example; a project's script takes its own settings from its own files).

Exit codes: 0 written and exported, ERC clean; 1 the lint or the rule check found something; 2 could not run.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# The skill's scripts folder. Inside the skill it is the folder above this file. A copy of this file in a project's
# src/ folder must be told where it is: --scripts FOLDER (the path is written once into PROJECT_STATE.md).
_SCRIPTS = next((sys.argv[_i + 1] for _i, _a in enumerate(sys.argv[:-1]) if _a == "--scripts"),
                os.path.dirname(_HERE))
if not os.path.isfile(os.path.join(_SCRIPTS, "kicad_io.py")):
    print("CANNOT RUN: kicad_io.py is not in %r; give the skill's scripts folder with --scripts FOLDER" % _SCRIPTS,
          file=sys.stderr)
    sys.exit(2)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import kicad_io  # noqa: E402
from schematic import export, symbols  # noqa: E402
from schematic.svclib import COL_FRAME, Doc, LintError  # noqa: E402

PROJECT = "example_node"
R0603, C0603, C0805 = ("Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric",
                       "Capacitor_SMD:C_0805_2012Metric")

# The one parts table. In a real project every fitted part also carries its LCSC number (lcsc=...) and maker part
# number (mpn=...); scripts/jlc_parts.py line-audit lists the lines that lack one.
PARTS = {
    "J1": dict(sym="USB_C_POWER", value="USB-C power", desc="USB Type-C receptacle, power only, 6 contacts",
               footprint="Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal"),
    "R1": dict(sym="R", value="5.1k", footprint=R0603, fields={"Tolerance": "1%"}),
    "R2": dict(sym="R", value="5.1k", footprint=R0603, fields={"Tolerance": "1%"}),
    "R3": dict(sym="R", value="0", footprint=R0603, desc="Shell to ground bond"),
    "F1": dict(sym="Polyfuse", value="0.5A PTC", footprint="Fuse:Fuse_1206_3216Metric"),
    "D1": dict(sym="D_Zener", value="TVS 5V", footprint="Diode_SMD:D_SOD-323", desc="Clamp diode, one direction"),
    "C1": dict(sym="C", value="10u 16V", footprint=C0805),
    "R4": dict(sym="R", value="100k", footprint=R0603),
    "U1": dict(sym="LDO_5PIN", value="LDO 3.3V", footprint="Package_TO_SOT_SMD:SOT-23-5",
               desc="Linear regulator 3.3 V with enable"),
    "C2": dict(sym="C", value="1u 10V", footprint=C0603),
    "C3": dict(sym="C", value="10u 10V", footprint=C0805, dnp=True),
    "TP1": dict(sym="TestPoint", value="+3V3", footprint="TestPoint:TestPoint_Pad_D1.5mm", in_bom=False),
    "TP2": dict(sym="TestPoint", value="GND", footprint="TestPoint:TestPoint_Pad_D1.5mm", in_bom=False),
    "J2": dict(sym="HEADER_5", value="host 1x5", footprint="Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"),
    "R5": dict(sym="R", value="4.7k", footprint=R0603),
    "R6": dict(sym="R", value="4.7k", footprint=R0603),
    "U2": dict(sym="RHT_SENSOR", value="RH/T sensor", desc="Temperature and humidity sensor, I2C",
               footprint="Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad"),
    "C4": dict(sym="C", value="100n 16V", footprint=C0603),
    "R7": dict(sym="R", value="1k", footprint=R0603),
    "D2": dict(sym="LED", value="green", footprint="LED_SMD:LED_0603_1608Metric"),
}

RY = 66.04      # sheet 1: the power line, left to right


def add_symbols(doc: Doc) -> None:
    """The project's own symbols: ICs as boxes from their pin tables, connectors as pin lists."""
    doc.lib.add("USB_C_POWER", symbols.conn("USB_C_POWER", [("A9", 0), ("B9", 2.54), ("A5", 10.16), ("B5", 15.24),
                                                             ("A12", 22.86), ("B12", 25.4), ("S1", 33.02)], width=17.78))
    doc.lib.add("LDO_5PIN", symbols.box(
        "LDO_5PIN", left=[("1", "VIN", "power_in"), None, ("3", "EN", "input")],
        right=[("5", "VOUT", "power_out"), None, ("4", "NC", "no_connect")], bottom=[("2", "GND", "power_in")]))
    doc.lib.add("HEADER_5", symbols.conn("HEADER_5", [("1", 0), ("2", 10.16), ("3", 25.4), ("4", 35.56),
                                                       ("5", 45.72)], width=17.78))
    doc.lib.add("RHT_SENSOR", symbols.ic(
        "RHT_SENSOR", "U", 5.08, 30.48, 7.62, -22.86,
        [("1", "SDA", "bidirectional", "L", 0), ("2", "SCL", "input", "L", -15.24),
         ("3", "VDD", "power_in", "T", 22.86), ("4", "VSS", "power_in", "B", 22.86)]))


def sheet1(doc: Doc):
    s = doc.root_sheet("Sheet 1: USB-C 5 V input and 3.3 V regulator")
    y = lambda d: round(RY + d, 4)                                                    # noqa: E731
    s.heading("1   USB-C 5 V INPUT AND 3.3 V REGULATOR",
              "A USB-C source delivers 5 V (VBUS). F1 and D1 protect the input; U1 makes the 3.3 V rail for sheet 2.")
    s.legend(205.0, 12.0, 80.0, "board running. In brackets: regulator switched off (EN_3V3 low).")
    s.text("SHEETS", 210.82, 47.5, bold=True, color=COL_FRAME)
    s.sheet_index(213.36, 53.34)

    # ---- USB-C input and protection --------------------------------------------------------------------------
    s.frame(20.32, y(-22.86), 113.03, y(38.1), "USB-C INPUT AND PROTECTION", "5 V from a USB-C source, 0.5 A")
    J1 = s.conn("J1", 45.72, RY, {"A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2", "A12": "GND", "B12": "GND",
                                  "S1": "SHELL"}, op="m")
    F1 = s.two("F1", 63.5, RY, "h", txt="above")
    s.wire(J1.p("A9"), F1.left)                                   # VBUS, straight into the fuse
    s.wire(J1.p("B9"), (49.53, y(2.54)), (49.53, RY))             # the second VBUS contact joins it
    s.label("VBUS", 50.8, RY)
    s.vtag(44.45, y(-10.5), "5.0 V")
    s.setpoint("F1: resettable fuse,\nholds 0.5 A", 58.42, y(-13.5))
    # CC1 / CC2: one pull-down each
    R2 = s.two("R2", 55.88, y(19.05), "v")
    R1 = s.two("R1", 66.04, y(13.97), "v")
    s.wire(J1.p("A5"), R1.top)
    s.wire(J1.p("B5"), R2.top)
    s.gnd(*R1.bot)
    s.text("CC PULL-DOWNS", 76.2, y(11.2), bold=True, color=COL_FRAME)
    s.setpoint("R1, R2 5.1 kΩ: a USB-C\nsource then supplies 5 V", 76.2, y(13.6))
    # ground contacts and the rule check's flag for the ground net
    s.wire(J1.p("A12"), R2.bot)
    s.wire(J1.p("B12"), (50.8, y(25.4)), (50.8, y(22.86)))
    s.gnd(*R2.bot)
    s.flag(48.26, y(22.86))
    # shell: bonded to ground through R3
    R3 = s.two("R3", 58.42, y(33.02), "h", txt="above")
    s.wire(J1.p("S1"), R3.left)
    s.wire(R3.right, (67.31, y(33.02)))
    s.gnd(67.31, y(33.02))
    s.setpoint("R3 0 Ω: shell bonded to ground", 76.2, y(32.4))
    # behind the fuse: the +5V rail with the clamp diode and the input capacitor
    s.flag(71.12, RY)
    s.rail("+5V", 77.47, RY)
    D1 = s.diode("D1", 85.09, y(3.81), k="up")
    C1 = s.two("C1", 99.06, y(3.81), "v")
    s.gnd(*D1.bot)
    s.gnd(*C1.bot)

    # ---- 3.3 V regulator -----------------------------------------------------------------------------------------
    s.frame(115.57, y(-22.86), 203.2, y(38.1), "3.3 V REGULATOR", "U1: linear regulator, enabled unless EN_3V3 is pulled low")
    U1 = s.ic("U1", 127.0, RY)
    s.wire(F1.right, U1.p(1))                                     # the +5V rail, straight into U1 VIN
    R4 = s.two("R4", 120.65, y(3.81), "v")
    s.wire(R4.bot, (120.65, y(10.16)), U1.p(3))
    s.wire((120.65, y(10.16)), (120.65, y(43.18)), (33.02, y(43.18)))
    s.offsheet("EN_3V3", 33.02, y(43.18), "L", "in", "from sheet 2:\nhost connector J2 pin 5")
    s.text("ENABLE", 123.19, y(25.4), bold=True, color=COL_FRAME)
    s.setpoint("R4 pulls EN to +5V: the rail is on\nuntil the host pulls EN_3V3 low", 123.19, y(27.8))
    s.gnd(*U1.p(2))
    s.nc(U1.p(4))
    s.setpoint("NC: leave open", 153.67, y(12.7))
    C2 = s.two("C2", 165.1, y(3.81), "v")
    C3 = s.two("C3", 180.34, y(3.81), "v")
    s.wire(U1.p(5), (195.58, RY))                                 # the +3V3 rail
    s.gnd(*C2.bot)
    s.gnd(*C3.bot)
    s.rail("+3V3", 172.72, RY)
    s.setpoint("C3: place for a second\noutput capacitor", 177.8, y(13.0))
    s.tp("TP1", 195.58, RY)
    s.vtag(193.0, y(-13.5), "3.3 V", "0 V", anchor="right")
    t = s.tp("TP2", 195.58, y(22.86))
    s.wire(t.p(1), (195.58, y(25.4)))
    s.gnd(195.58, y(25.4))

    # ---- notes ---------------------------------------------------------------------------------------------------
    s.notes(120.0, how=[
        ("Input", "A USB-C source sees the 5.1 kΩ pull-downs R1 and R2 on CC1 and CC2 and switches 5 V onto VBUS. "
                  "F1 limits a fault current; D1 clamps surges; C1 is the input capacitor."),
        ("Regulator", "U1 makes 3.3 V from +5V. R4 holds EN high, so the rail is on as soon as 5 V is present; "
                      "the host on sheet 2 can pull EN_3V3 low to switch the rail off."),
        ("Not fitted", "C3 is a place for a second output capacitor."),
    ], volts=[
        ["TEST POINT", "NET", "RUNNING", "EN LOW"],
        ["J1 A9, B9", "VBUS", "5.0 V", "5.0 V"],
        ["F1 pin 2", "+5V", "5.0 V", "5.0 V"],
        ["TP1", "+3V3", "3.3 V", "0 V"],
        ["TP2", "GND", "0 V", "0 V"],
    ], sources="Example values (see the header of example_two_sheets.py). A dash would mean: no value is known.",
        checks=[
        ("Unpowered, meter to GND", "+5V and +3V3 (TP1): no short to GND (TP2)."),
        ("5 V applied", "TP1 reads 3.3 V. With J2 pin 5 tied to GND it reads 0 V."),
    ])
    return s


def sheet2(doc: Doc, demo_lint: bool = False):
    s = doc.sheet("sensor", 2, "SENSOR, HOST CONNECTOR AND STATUS LED")
    s.heading("2   SENSOR, HOST CONNECTOR AND STATUS LED",
              "The host reads the sensor over I2C through J2 and can switch the 3.3 V rail off. D2 shows that the rail is on.")
    s.legend(205.0, 12.0, 80.0, "board running. In brackets: regulator switched off (EN_3V3 low).")

    # ---- host connector and I2C pull-ups -----------------------------------------------------------------------
    s.frame(20.32, 43.18, 101.6, 116.84, "HOST CONNECTOR AND I2C PULL-UPS")
    J2 = s.conn("J2", 50.8, 60.96, {"1": "+3V3", "2": "SDA", "3": "SCL", "4": "GND", "5": "EN_3V3"}, op="m")
    s.wire(J2.p(1), (58.42, 60.96))
    s.rail("+3V3", 58.42, 60.96)
    s.wire(J2.p(4), (58.42, 96.52))
    s.gnd(58.42, 96.52)
    s.wire(J2.p(5), (63.5, 106.68))
    s.offsheet("EN_3V3", 63.5, 106.68, "R", "out", "to sheet 1:\nregulator U1 EN")
    R5 = s.two("R5", 78.74, 67.31, "v")
    R6 = s.two("R6", 91.44, 82.55, "v")
    s.rail("+3V3", *R5.top)
    s.rail("+3V3", *R6.top)

    # ---- sensor ----------------------------------------------------------------------------------------------------
    s.frame(104.14, 43.18, 167.64, 116.84, "TEMPERATURE / HUMIDITY SENSOR")
    U2 = s.ic("U2", 114.3, 71.12)
    s.wire(J2.p(2), U2.p(1))                                      # SDA, with R5 standing on it
    s.wire(J2.p(3), U2.p(2))                                      # SCL, with R6 standing on it
    s.label("SDA", 63.5, 71.12)
    s.label("SCL", 63.5, 86.36)
    C4 = s.two("C4", 149.86, 59.69, "v")
    s.wire(U2.p(3), (137.16, 53.34))
    s.rail("+3V3", 137.16, 53.34)
    s.wire((137.16, 55.88), (149.86, 55.88))                      # the decoupling capacitor, at the supply pin
    s.gnd(*C4.bot)
    s.gnd(*U2.p(4))
    s.vtag(152.4, 48.5, "3.3 V", "0 V")
    s.setpoint("3.3 V logic; pull-ups R5, R6\nat the host connector", 109.22, 104.14)

    # ---- status LED --------------------------------------------------------------------------------------------------
    s.frame(170.18, 43.18, 210.82, 116.84, "STATUS LED")
    R7 = s.two("R7", 186.69, 64.77, "v")
    D2 = s.diode("D2", 186.69, 77.47, k="down")
    s.rail("+3V3", *R7.top)
    s.wire(R7.bot, D2.top)
    s.gnd(*D2.bot)
    # --demo-lint: the LED node gets the name of the connector side of the fuse on sheet 1: two nodes, one name
    s.tag("VBUS" if demo_lint else "LED_A", 186.69, 71.12, side="left")
    s.vtag(172.72, 61.5, "≈2.0 V", "0 V")
    s.setpoint("lit while +3V3 is on\n(3.3 V - 2 V) / 1 kΩ ≈ 1.3 mA", 173.99, 88.9)

    s.notes(124.0, how=[
        ("Host", "J2 carries the 3.3 V rail, the I2C bus and EN_3V3. R5 and R6 are the bus pull-ups."),
        ("Sensor", "U2 answers on the I2C bus. C4 is its decoupling capacitor, drawn at its supply pin."),
        ("LED", "D2 is lit through R7 while +3V3 is present."),
    ], volts=[
        ["TEST POINT", "NET", "RUNNING", "EN LOW"],
        ["J2 pin 1", "+3V3", "3.3 V", "0 V"],
        ["J2 pins 2, 3", "SDA, SCL", "3.3 V idle", "0 V"],
        ["D2 anode", "LED_A", "≈2.0 V", "0 V"],
    ], sources="Example values (see the header of example_two_sheets.py).", checks=[
        ("5 V applied", "D2 is lit. SDA and SCL idle at 3.3 V."),
    ])
    return s


def build(demo_lint: bool = False) -> Doc:
    doc = Doc(PROJECT, title="Example sensor node: wired-schematic example", rev="A", date="2026-01-01",
              company="Example Company", comments=["A worked example of scripts/schematic; not a product"],
              paper="A4", parts=PARTS, rails=["+5V", "+3V3"], global_nets=["EN_3V3"])
    add_symbols(doc)
    sheet1(doc)
    sheet2(doc, demo_lint)
    return doc


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Worked example of the wired-schematic library: a USB-C 5 V input with a 3.3 V regulator "
                    "(sheet 1) and a sensor with a status LED (sheet 2). Writes the KiCad project and exports it.",
        epilog="Exit codes: 0 written and exported, ERC clean; 1 lint or ERC findings; 2 could not run.")
    ap.add_argument("--out", metavar="FOLDER", help="where to write: FOLDER/kicad (project) and FOLDER/out (exports)")
    ap.add_argument("--scripts", metavar="FOLDER", help="the skill's scripts folder (needed by a copy of this file "
                    "that lives in a project's src/ folder)")
    ap.add_argument("--no-export", action="store_true", help="only write the KiCad project")
    ap.add_argument("--bw", action="store_true", help="plot in black and white")
    ap.add_argument("--demo-lint", action="store_true", help="plant a duplicate net name: the lint must stop the build")
    a = ap.parse_args(argv)
    if not a.out:
        print("CANNOT RUN: give --out FOLDER", file=sys.stderr)
        return 2
    doc = build(a.demo_lint)
    try:
        res = doc.write(os.path.join(a.out, "kicad"))
    except LintError as e:
        print(f"FAIL lint: {e}")
        return 1
    print(f"PASS lint: 7 checks, 0 findings; {len(res['files'])} files in {os.path.join(a.out, 'kicad')} "
          f"({len(res['written'])} changed)")
    for key, found in res["drawing"].items():
        for f in found:
            print(f"  drawing [{key}] {f}")
    if a.no_export:
        return 0
    return export.export(res["root"], os.path.join(a.out, "out"), name=PROJECT, bw=a.bw)["exit_code"]


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
