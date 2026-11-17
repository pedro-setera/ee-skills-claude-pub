# Schematic style: wired blocks a technician can read

How to draw the schematic so that a person can understand, review and service the board from it. Used in phase 5 and by the schematic reviewers.

A schematic of loose symbols joined only by net labels is electrically valid and useless to a human. It also hides errors: on one board two different nodes got the same label on two sheets and became one net, and nobody could see it on the page. The style below makes the circuit visible, and the lint makes that kind of error stop the build.

## Contents
1. Sheet plan
2. Drawing rules
3. Service information on the sheets
4. Title block, colour, privacy
5. How to build it
6. One sample sheet first
7. The lint list
8. Looking at the sheets

## 1. Sheet plan

- **Sheet 1 is the overview:** the block diagram, the power tree, the sheet index, the test-point table, the connector pin tables, the meaning of each indicator. Someone who opens the PDF learns from this sheet what the board does and where to look.
- **Then one sheet per function, in the order the signal or the power flows:** for example input and protection, conversion, control logic, controller, interfaces, outputs and connectors.
- A function is not split over two sheets. A sheet holds two to four related blocks, with room for their notes.
- A connector is drawn on the sheet of the circuit it serves, not on a sheet of connectors.
- One sheet size for the whole set: A3 for dense boards, A4 for small ones.

## 2. Drawing rules

1. **Wires, not labels.** Every connection inside a sheet is a drawn wire.
2. **Flow from left to right.** Inputs and sources on the left, outputs and loads on the right. Feedback runs back underneath.
3. **Higher voltage up, ground down.** Supply rails enter at the top of a block. Ground symbols point down and sit at the bottom.
4. **One titled frame per function.** The title says what the block does and its key figure: "5 V buck converter, 500 kHz".
5. **A dot at every real T-joint.** No four-way crossings: offset one branch, so that a crossing can never be read as a joint.
6. **Labels only where a wire cannot do the job:**
   - supply and ground symbols;
   - the declared signals that leave a sheet;
   - the pin stubs of a large digital part whose pins fan out everywhere (the blocks around it stay wired);
   - a pair of labels inside a sheet, only where the wire would cross a supply row or the whole sheet. List each such pair in the design note as an accepted imperfection.
7. **Net names say what the net is, and each is unique.** `VIN_PROT`, `BUCK_SW`, `EN_5V`, never a bare `SW`, `EN`, `OUT` or `VCC`: two blocks will both want that name. Rail names carry the voltage. Active-low names carry one consistent mark.
8. **Symbols.** Standard symbols for discrete parts, one resistor style on all sheets. ICs are boxes with the pins grouped by function (inputs left, outputs right, supply top, ground bottom), every pin number shown, every pin name as in the datasheet. No hidden supply pins.
9. **Decoupling at its IC.** A capacitor that belongs to a pin is drawn at that pin, not in a bank elsewhere.
10. **Each part shows** its reference, its value, and what a technician needs: the voltage rating of capacitors in power paths, the tolerance of parts that set a threshold. LCSC and maker part numbers are fields of the symbol, not text on the sheet.
11. **Unfitted parts are crossed out** and say why they exist: "not fitted: tuning option".
12. **A no-connect mark on every pin meant to stay open,** so that an accidental open is caught by the checks.
13. **Nothing overlaps:** no text on a symbol, a wire or another text; nothing outside its frame.
14. **One notation for values** on all sheets.

## 3. Service information on the sheets

The sheets carry what a service manual would:

- **Set-point notes beside the parts that set them:** "under-voltage lock-out 4.4 V rising, 4.1 V falling (R3, R4)", with the minimum-to-maximum range where it matters.
- **Expected voltages** at test points and key nodes, for running and for standby.
- **A "how it works" note per frame,** two to four lines.
- **Connector pin tables:** pin, signal, direction, level.
- **The test-point table** on the overview: test point, net, expected value running and in standby. A pad used in place of a test point has its row too (`references/pcb-rules/dfm-dft.md` DFM-94, DFM-99).
- **Bring-up hints:** which link isolates a block, where a loop measurement is injected.

Every number on a sheet comes from the design note, the reference check or a datasheet, through the generator, and is not typed twice. Where no value is known the sheet shows a dash, never a guess. After a fix round the notes on the sheets are part of "search every changed value".

## 4. Title block, colour, privacy

- The title block names the company the user gives (never a person), the board, the revision, the date, the sheet title and "sheet n of m". The revision string lives in one place and the build copies it to every sheet.
- Colour is welcome for frames and notes, but the set must print in black and white. Export once in grey and look.
- No personal name and no user folder path in any field or in the PDF's properties. Run `scripts/privacy_scan.py` on the PDF before it is shared.

## 5. How to build it

- **A hand layout written as code.** One script per sheet in the project's `src/` folder says where each symbol sits, how each wire runs and what the notes say.
- **The library.** The sheet scripts use `scripts/schematic/svclib.py` (placement on a grid, wires with junction dots, labels, supply symbols, frames, tables, notes, lint) and `scripts/schematic/symbols.py`. `scripts/schematic/export.py` writes the netlist, the ERC report, the PDF and one image per sheet. `scripts/schematic/example_two_sheets.py` is the pattern: copy it into the project's `src/` folder, do not import it. A project script lives outside this skill, so it must be told where the skill's `scripts` folder is: it takes the folder from its `--scripts <folder>` argument, as the example does, and stops with "cannot run" when the library is not there. Write the full path of the skill's `scripts` folder into `PROJECT_STATE.md` once (`skill_scripts:`), so every later session uses the same one.
- **One source for part data.** Value, footprint, LCSC number, maker part number and fitted state come from one table and reach both schematic and BOM from there.
- **The header of each sheet script names the source of every number on its sheet.**
- **Same input, same files.** Identifiers are derived from names and positions, so a rebuild without changes alters no file. Checksums stay meaningful and a diff shows only real changes.
- **Command line only.** Use KiCad's command-line tool for export and checks, never the graphical program in automated work.
- **A schematic drawn by hand in the editor** follows the same rules. The lint items that need the drawing are then checked by eye; the netlist-level checks still run.
- **A redraw of an existing schematic** leaves the original untouched in its folder and is accepted only when `scripts/netlist_compare.py` reports the two netlists identical: references, values, footprints, pins and nets.

## 6. One sample sheet first

1. Pick the sheet with the most typical dense function.
2. Draw it completely: frame, wires, notes, tables, title block.
3. Export it. Open the image at full size, zoom into the densest area, run the lint, fix what you see.
4. Check the grey export.
5. Give the user the full path and continue with the next sheets. If style feedback comes, apply it to the sample first.

A style problem found on one sheet costs minutes. Found after six sheets, it costs the six sheets.

## 7. The lint list

The build stops on any of these seven. Each exists because the defect it names passed ERC.

| Lint | Why it matters |
|---|---|
| A net name on more than one sheet that is not declared global | Two nodes become one net; this merged a switching node with a signal input |
| A declared global name that is no longer used | A stale list hides the next duplicate |
| Two different drivers given one name | The same error inside one sheet |
| A part without a footprint | It vanishes at board import and from the placement file |
| A label with no partner | An open net that looks connected |
| A wire end that touches nothing | An open net that looks connected |
| A pin left unconnected without a no-connect mark | Intended and accidental opens look the same |

A fitted part without an LCSC number and a maker part number cannot be ordered or checked for stock. That check is not part of the lint: `scripts/jlc_parts.py line-audit` runs it on the BOM.

Two more checks belong with the lint and run on the exported netlist: `scripts/netlist_check.py` against the hand-written intent file `src/expected_connectivity.toml`, and its per-IC table of pin, pin name and net, read against the datasheet pin function noted in the intent file, which shows a symbol whose pin names differ from the datasheet.

## 8. Looking at the sheets

Open every sheet image. A clean lint does not make a sheet readable. Write one or two lines per sheet on what you saw, against these questions:

- Can each block be followed from left to right without reading a label?
- Does any crossing read as a joint, or is a dot missing?
- Does any text sit on a symbol, a wire or another text?
- Does each set-point note agree with the values drawn beside it?
- Is every IC pin numbered and named, and are supply pins drawn?
- Are unfitted parts crossed out?
- Does a net name appear on two sheets, and is that intended?
- Is the title block right on every sheet: company, revision, date, sheet count?
- Is the grey export still readable?

List what you chose to leave imperfect in the design note, with the reason. A disclosed imperfection is a decision; an undisclosed one is a defect a reviewer will find.
