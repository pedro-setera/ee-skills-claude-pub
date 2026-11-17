# Phase 5: schematic

Draw a schematic a service technician can read, and prove its netlist against an independent statement of intent.

## Inputs

- `DESIGN_NOTE.md`, the BOM, `REFERENCE_CHECK.md` (pin tables, set-points), `LAYOUT_RULES_LEDGER.md`.
- `references/schematic-style.md`: the drawing style, the lint list, the sample-sheet rule; `references/pcb-rules/emc.md`.
- `scripts/schematic/` (`svclib.py`, `symbols.py`, `export.py`), `scripts/netlist_check.py`, `scripts/ratings_check.py`, `scripts/jlc_parts.py`.
- `templates/EXPECTED_CONNECTIVITY.md`, `templates/DESIGN_NOTE.md`.
- `references/lessons.md`, section "Phase 5: schematic".

## Steps

1. Plan the sheets as `references/schematic-style.md` says: an overview sheet, then one sheet per function. Declare the short list of nets that may appear on more than one sheet.
2. Write the intent file by hand as `src/expected_connectivity.toml` (format, rules and skeleton: `templates/EXPECTED_CONNECTIVITY.md`). It states:
   - every intended net as a group of pins under `[nets]`;
   - the pins that must stay unconnected under `[no_connect]`;
   - under `[options]`, the references to ignore, such as mounting holes and fiducials;
   - as comments, the pin functions per IC, with the datasheet table named.
   Write it from the circuit description and the datasheet pin tables. It must not be derived from the generator scripts or from a netlist, or the check compares a mistake with itself. Best is a second agent that writes it from `DESIGN_NOTE.md` and `REFERENCE_CHECK.md` alone.
3. Draw one sample sheet first: a typical function, fully wired, framed, with its notes (a design with a single function sheet shows that sheet). Export it, open the image, run the lint, fix. Give the user its path and carry on; do not wait for a reply.
4. Draw the remaining sheets in the same style, with the generator's lint switched on from the first run. Keep it simple (`references/working-rules.md` section 12): the maker's application circuit as it stands, the usual circuit before a clever one, few different values, one connector family; a part that traces to nothing in the design note's block list is removed before the reviews. Part data (value, footprint, LCSC number, maker part number, fitted or not) comes from one source and is never typed twice.
4b. Where the design has a fan: its connector, its switch or speed control, its speed signal, its supply filter and the temperature sensor at the hot part are on the schematic, and what happens when the fan stops is designed, not hoped (`references/pcb-rules/thermal.md` THM-33, THM-50).
4c. **Test points are parts of the schematic** (`references/pcb-rules/dfm-dft.md` section 10). Make the list now from what the bring-up plan and the bench list will measure (DFM-94): the rails, ground (one point a clip can hold), reset and boot, the buses, the nets hidden under leadless parts or a module; a net that already has a pad a probe can hold uses that pad. Draw each point as a TP part on the sheet of its function (DFM-95); none on a crystal pin, an RF line or a high-impedance node (DFM-97). Start the test-point table on the overview, with the value that is normal at each point. Write the nets that must have a point as the list `required` of the table `[testpoints]` in `board.toml`, the pads used in place of a point as `[[testpoints.pad]]` (`ref`, `pin`), and the normal values as `[testpoints.normal]`: `scripts/testpoint_check.py` reads them in phase 10.
5. Check the pin mapping in three layers for every IC and every polarised part (diodes, LEDs, electrolytic capacitors, transistors, connectors):
   - the symbol's pin names equal the datasheet's pin names;
   - the symbol's pin numbers equal the footprint's pad numbers;
   - those pads are the package pins of the exact BOM part number, variant suffix included.
   Stock symbols are not exempt: one was found with two pin names exchanged.
6. Export with `python -I scripts/schematic/export.py --project <board folder>`: `out/netlist.net`, `out/erc_report.json`, `out/<board>-schematic.pdf`, one image per sheet `out/schematic-<n>-<sheet>.png`. ERC must show 0 errors and 0 warnings. That is necessary and proves little: ERC once passed two merged nets because every pin on them was passive.
7. Run `python -I scripts/netlist_check.py --project <board folder>` on the exported netlist against the intent file (result `out/connectivity_report.md`):
   - every group is exactly one net, with no pin missing and none extra;
   - every pin of every part is in a group or in the unconnected list;
   - every part has a footprint.
   Then run it with `--self-test`: it plants three defects in copies of the netlist, two nets merged, one net split and a no-connect pin connected, and must fail each. A check that cannot fail proves nothing.
7b. Run `python -I scripts/ratings_check.py --project <board folder>` (result `out/ratings_check.md`). It reads the exported netlist and `src/datasheet_pins.toml` (phase 4, step 4) and reports: a pin whose number or name on the symbol differs from the datasheet's; a pin of the part that the symbol lacks, or the reverse; a pin that sits on a supply or signal whose worst-case value is outside its recommended range (a finding) or beyond its absolute maximum (a blocker); and every pin of a chip that has no rating typed in (UNKNOWN: zero of these at gate 1 for every chip, transistor and polarised part). It is the machine's half of the pin check of step 5 and of the limits check of phase 4; the reviewers do the other half from the datasheets, with their own table.
   - **A board with a microcontroller or any other programmable chip:** write what the design uses each of its pins for into `src/pin_use.toml` (`templates/PIN_USE.md`), have the functions the maker's table offers on each pin typed into that part's block of `src/datasheet_pins.toml` (`templates/DATASHEET_PINS.md` rule 4c, `programmable = true`), and run `python -I scripts/pin_function_check.py --project <board folder>` (result `out/pin_function_check.md`). It fails a function the pin does not have, two jobs on one pin, one single function on two pins, an output on an input-only pin, and a reset-sampled, debug or oscillator pin used for something else without a written reason. Zero FAIL and zero UNKNOWN at gate 1. A module that runs its maker's fixed firmware carries `programmable = false`.
7c. Recalculate the power forecast from the parts as drawn: the power budget (typical and peak, per rail and from the source) and, for a battery device, the energy budget per operating mode, now with the real currents of the chosen parts from their datasheets: each regulator's own current, pull-ups and dividers that draw all the time, the lights, the sleep current of every chip. Every current is referred to the cell (through a switching converter the cell current is the rail current times the rail voltage, divided by the cell voltage and the efficiency), and the running time is given twice: typical figures at room temperature, and maximum figures at the hottest surroundings; the user is told the lower one (PWR-56). Result: the average current, and either the running time with the chosen battery or the battery needed for the running time the user asked for (`references/pcb-rules/power.md` PWR-56). Shares of time that the firmware or the use will decide are written as assumptions the user can see ("transmits 1 % of the time"). The user sees and agrees to it at gate 1; the battery's kind, capacity, size and connector are inputs of phase 8 and do not change after it without a new board definition.
7d. **A board with a programmable part: agree the hardware and firmware interface before gate 1.** The evidence for the allocation of pins, clock sources and peripheral instances (`out/pin_function_check.md` with the clocks, timers, DMA channels and interrupts each job takes) is the maker's configuration tool file for this exact part, accepted by the tool without a conflict, or a minimal initialisation that compiles for it (keep the file and its report). Where there is a firmware owner (phase 1), record their acceptance, with the date, beside it; their word alone is not the evidence. This joint review finds what the pin-function check cannot: a timer, a channel or a clock that two jobs need at once. Without the evidence the allocation is UNKNOWN at gate 1. No programmable part: "not applicable".
8. Recalculate every set-point from the values as drawn, read from the netlist or BOM, not from the design note: nominal, minimum and maximum with tolerances, referred to the output. Compare with the phase 4 table and the requirement, and print the result beside the parts that set it.
9. Check every interface to another board or module, in both directions and at every level the other side's datasheet allows (for example 3.3 V and 5 V):
   - the level that arrives at each receiver through any series resistor, against the receiver's own pull-up or pull-down, compared with its input thresholds;
   - the edge time against the bit time;
   - the pull of every open-drain line. Pull an open-drain line up to a rail that every pin on the line tolerates, also while that device is unpowered, and that meets every receiver's high-level input voltage; otherwise use a level shifter;
   - the state of each input while the other side boots or is unpowered.
   A series resistor added for protection is sized with the other side's pull known. If it is unknown, bound it, give the resistor its own BOM line, and add a bench item.
9b. **Default levels** (`references/pcb-rules/mcu-digital.md` MCU-64, MCU-65). For every control input on the board (enable, shutdown, chip select, reset, driver-enable, write-protect, mode, address, gate or base) write the row: the line; its level while its driver is in reset, unpowered or being programmed; what holds it there (a resistor, an internal pull with its datasheet page, a hard tie); and that this level is the safe one. A line with a driver is not thereby defined: a microcontroller's pins are high-impedance until its firmware runs. Enter the keys `input` and `io_hiz_in_reset` in `src/datasheet_pins.toml`, so that `scripts/ratings_check.py` lists every input that can float.
10. Check the schematic-level EMC measures against `references/pcb-rules/emc.md` section 3 and the design note's table of noise sources: a filter and protection at the connector for every wire that leaves the board; an own filtered supply for each sensitive section; the slowest edge that meets timing, with a series resistor position on long clock and bus lines; no floating input; the footprint-only provisions (snubber, shield outline, spare filter positions). An antenna gets its three-part matching network footprint at the feed, as section 6 there says. Write the result per row of the table.
11. Open every sheet image and write what you saw, sheet by sheet, against the list in `references/schematic-style.md`. Fix and export again until the notes hold nothing to fix.
12. Regenerate the BOM from the schematic. Compare it with the phase 3 BOM and explain each difference. Run `scripts/jlc_parts.py line-audit` again (it also flags a fitted part without an LCSC number and a maker part number); re-run `bom-check` if any part changed. Give every value that may change its own line now, before gate 1: later phases only audit, and a split after a gate needs the user's go and a fix round.
13. Complete `DESIGN_NOTE.md`:
    - the concept in numbered blocks with the key set-points; the calculations with tolerances; the power budget;
    - the interface specification: a pin table with direction, level, pull and state at reset, and the sequence;
    - the harness per connector: wire, length, voltage drop, mis-plug analysis, and how each pin is proven before the first plug-in;
    - assumptions and risks; the numbered bench tests; the drawing imperfections accepted, and why.
14. Record in the state file: the netlist checksum, the ERC result, the netlist check result with its group count, the self-test result.

For a schematic that came from the user, do not redraw it without their go. Run steps 2, 4c (its result as a proposal on the change list) and 5 to 14 on it as it is, record what fails as intake findings without fixing it (a needed BOM split goes on the change list too), list where it departs from the style, and recommend.

## Questions for the user

None. Show the sample sheet early with its full path so the user can look while the work continues. If they ask for a style change, apply it to the sample sheet first.

## Checks before leaving this phase

- [ ] ERC: 0 errors, 0 warnings. Evidence: `out/erc_report.json`.
- [ ] Lint, seven checks: no net name on more than one sheet unless declared global, no declared global name that is no longer used, no two different drivers under one name, no part without a footprint, no label without a partner, no wire end that touches nothing, no open pin without a no-connect mark. Evidence: the lint output.
- [ ] The netlist check passes. Evidence: `out/connectivity_report.md` with the counts of groups and unconnected pins.
- [ ] The intent file was written independently. Evidence: its header naming who wrote it and from which documents.
- [ ] The self-test fails all planted defects. Evidence: the three results recorded with the date.
- [ ] A board with a microcontroller or any other programmable chip: the pin-function check passes, with every pin of every programmable part PASS or accepted with its written reason, and no FAIL and no UNKNOWN. "Not applicable" is right only when every chip's block says `programmable = false`. Evidence: `out/pin_function_check.md`, `src/pin_use.toml`, and `programmable = true` in that part's block of `src/datasheet_pins.toml`.
- [ ] A board with a programmable part: the maker's tool accepted the configuration of pins, clocks and peripherals without a conflict, or a minimal initialisation compiles, with the firmware owner's acceptance where there is an owner; otherwise the allocation is UNKNOWN, listed for gate 1. Evidence: the tool file or the build report, the row of `GATE1_SUMMARY.md` and the decision row of the state file.
- [ ] The pin and rating check passes: every pin as the datasheet names it, every pin inside its recommended range at the worst case, no pin of a chip, transistor or polarised part without a rating. Evidence: `out/ratings_check.md`, and the header of `src/datasheet_pins.toml` naming the datasheet and page per part.
- [ ] The three-layer pin mapping holds for every IC and polarised part. Evidence: the per-IC pin table of the connectivity report, with the datasheet table named per part.
- [ ] Every set-point recalculated from drawn values is inside its window at minimum and maximum. Evidence: the calculations table, and the notes on the sheets showing the same numbers.
- [ ] Every control input has a defined, safe level while its driver is in reset, unpowered or being programmed; every internal pull relied on is marked in that table for the firmware hand-over. Evidence: the default-level table of the design note; the list "can float" of `out/ratings_check.md` is empty.
- [ ] Every interface level is inside the receiver's thresholds in both directions and at every allowed level. Evidence: the interface table with the computed levels.
- [ ] Every row of the table of noise sources has its schematic measure, and every antenna its matching network footprint. Evidence: the EMC result in the design note, against `references/pcb-rules/emc.md`.
- [ ] Every rail, ground, reset and boot line, bus and net hidden under a leadless part has a test point or a named pad, drawn on the schematic; none sits on a crystal pin, an RF line or a high-impedance node. Evidence: the test-point table on the overview.
- [ ] Every sheet image was opened. Evidence: the "what I saw" notes per sheet.
- [ ] The sample sheet came first. Evidence: the state file log entry with its path.
- [ ] The BOM from the schematic equals the phase 3 BOM plus explained changes; value-critical parts are on their own lines. Evidence: the diff and `out/bom_line_audit.md`.
- [ ] The stock report carries today's date if any part changed. Evidence: `out/BOM_STOCK_CHECK.md`.
- [ ] `DESIGN_NOTE.md` has every section of step 13, with numbered bench tests. Evidence: the file.

## Outputs

- `kicad/`: the schematic project
- `src/`: the per-sheet generator scripts and the intent file `expected_connectivity.toml`
- `out/`: `netlist.net`, `erc_report.json`, `<board>-schematic.pdf`, `schematic-<n>-<sheet>.png`, `connectivity_report.md`, the BOM, `bom_line_audit.md`
- `DESIGN_NOTE.md`, complete for the schematic stage

## Lessons behind this phase

- Two different nodes on two sheets carried the same short name. The generator made every cross-sheet name global, so a converter's switching node was joined to a switch input. ERC passed. At first power-on a resistor would have burnt and the input voltage would have reached a small transistor's gate -> the generator refuses a net name on more than one sheet unless it is declared.
- The check that reported "all nets match" compared the netlist with the generator's own source: the mistake with itself -> the check runs against a hand-written intent file, and a self-test proves it can fail.
- A schematic of loose symbols joined only by labels was valid and unreadable; the user asked for one a person can service from, and it had to be drawn a second time -> wired blocks from the first sheet.
- A stock symbol named two pins of a counter chip the other way round than the datasheet, and the checker compared neither names nor pads -> the pin mapping is checked in three layers.
- A protection resistor in a data line was sized with an assumed pull-up on the other side; with the real one a logic low arrived too high -> interface levels are computed in both directions from the other side's datasheet.
- A diode had no footprint and would have vanished at board import and from the placement file -> the lint fails on any part without a footprint.
- A documented trip range was too narrow because a tolerance was not referred to the output -> set-points are recalculated from the drawn values at the output node.
- In that redraw, one sample sheet was drawn and judged before the other five, and the user saw the first page while the rest was in work; six sheets took about two and a half hours -> one sample sheet first.

The full cases are in `references/lessons.md`.
