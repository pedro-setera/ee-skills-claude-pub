# Phase 15: arrival and first power-up

Write and review the first power-up plan before the boards arrive, then guide the user through it so that every protection is proven before anything expensive is connected, and carry the results into the next revision.

## Inputs

- The frozen design: schematic, netlist, BOM, assembly drawing, renders.
- `DESIGN_NOTE.md` (set-points with tolerances, bench list), `sim/RESULTS.md` (expected values, the "only the bench can prove" list), `LAYOUT_RULES_LEDGER.md`.
- `GATE2_SUMMARY.md` (open items, waivers, accepted deviations, unlabelled parts) and every review report's UNKNOWN items and coverage statement.
- `ORDER_LOG.md`: changes that became known after the order, and what the assembler changed.
- `templates/FIRST_POWER_UP.md`, `templates/NEXT_REV.md`, `references/review-briefs/bring-up-plan.md`.
- `references/lessons.md`, section "Phase 15: arrival and first power-up".

## Steps

**Boards designed or ordered outside this skill** (`references/existing-designs.md` section 4). Tell the user first: do not power a board yet. Ask for the schematic, the BOM, the assembly drawing or the board file, and what changed after the order. Recover in short: the one-page description with its `REQ-nn` (the user's confirmation of it is gate 0), every rail with its expected value and tolerance from the datasheets, the protections as they are, and the pads a probe can hold. What cannot be recovered is UNKNOWN in the plan. Step 10a then measures with no forecast to compare with; steps 14b and 14c run only when the user asks. The first check below then reads: the plan existed before the first board was powered.

1. **Write `FIRST_POWER_UP.md` before the boards arrive.** A plan written with the boards on the bench gets skipped. Start it with the goal, the rules for every step, the instruments needed, and the table of test points (with the way to find each unlabelled one on the assembly drawing).
2. **Set the rules for every step.**
   - Bench supply only, always current-limited, until the protections have passed.
   - No real load and no expensive device on the board until then.
   - One board at a time. Stop at the first value outside its range and write it down.
   - Power is fed through the board's input connector, never through a test point; test points are for probes.
3. **Order the plan like this:**
   - **Step 0, known late changes:** every value swap, unfitted part or missing part known since the order. Each has what to do, a numeric pass value and a fallback.
   - **Look:** damage, bridges on fine-pitch parts, connectors seated, every polarised part against the checklist table, DNP pads empty, the marking of any part that exists with two pin orders under similar names. Hand-fit parts go on now, in the written order, each with its orientation rule.
   - **Resistances without power:** each rail to ground, with an expected value and a "stop if" value. Say which way the reading moves while capacitors charge.
   - **Low voltage, current-limited:** the lowest input first, no loads; expected current and rail voltages. Set the first limit above the computed start-up inrush with margin (per regulator C_total x Vout / t_soft-start plus its start-up load, `references/pcb-rules/power.md` PWR-50, referred to the input and summed over the rails that start together), but below the level that damages the weakest part, or ramp the input slowly. Expect a short constant-current excursion at turn-on and log it: a limit below the inrush makes a good board look dead.
   - **Full voltage, tight limit, no loads;** then dummy loads.
   - **Protections, each tripped on purpose** with limited energy and no downstream device, set up as step 5 says: the trip window, how it latches, how it resets. A full-energy fault test is not run here (step 10).
   - **Harness proof with a meter** before the first plug-in: continuity pin by pin, no short between supply and ground, then the levels at the free end before it meets a logic pin.
   - **Real loads, one at a time;** then full load; then the bench list.
   - **Partial power:** the states the isolation links create, which links close together, and the back-feed check of each (`references/pcb-rules/dfm-dft.md` DFM-104).
   - **Quiet line,** on a microcontroller board that has one (`references/pcb-rules/mcu-digital.md` MCU-74): hold it low, then high, while firmware exercises the buses.
4. **Give every step numbers.** Each expected value has a range, a unit and its source (design note, simulation, datasheet), written before the test and not moved afterwards. "Works" is not a pass value. A rail's ripple pass value is the allowed ripple of the design note's rail table.
5. **List the set-up of every step:** supply voltage, current limit and over-voltage protection, chosen to protect the weakest cheap part in that step; the instruments and probe points; every physical connection that must be present (source, load, tie, antenna, termination, cable) and what must not be connected.
   - A current limit does not limit the charge in the supply's own output capacitor, nor the ring of its leads. Per protection step, compute that energy and the ring; put a series resistor in every crowbar and clamp test; connect with the supply output off, then enable it.
   - One power source per step unless the design is made for several. A debug probe that powers the board or senses its rail, a USB cable and the bench supply each count; trace what each would back-feed into the others (the bench supply, the probe, the host) before a second one is connected.
   - On an RF board, bench leads land only at its DC entry, short and paired, and RF is measured only through its coax connectors (`references/pcb-rules/rf.md` RF-27).
6. **Dry-run every test against the schematic.** Is every rail that the tested circuit needs alive in this set-up? Can the stimulus reach the threshold at its worst tolerance? Can the supply deliver more than the trip level, or would its own limit be measured? Then launch the independent review with `references/review-briefs/bring-up-plan.md` and have the reviewer re-check its findings once (`references/reviews.md` section 6). In the lean set this review is offered, not automatic: offer it to the user in one line (next section) when the board has a protection circuit or feeds a load that costs more than the board; where it does not run, record in the state file that the dry run was the designer's own and, if the user declined it, their words. In the full set it always runs.
7. **Prove unknown pins before soldering to them.** A pin whose function is not in the maker's documents is proven with a meter against a known rail and ground, measured again after soldering, with a stop rule if either reading fails.
8. **Separate the two bench limits.** The first-power-up limit protects fresh joints and is tight. Write when it is raised and to what, from the measured running current. Note what the supply's logging cannot see (short peaks) and log every switch into current-limit mode.
9. **Log temperatures with stop limits** in every load and fault test: which parts carry a sensor, the warning level and the stop level. Measure the UNKNOWNs here, for example the air temperature inside the closed enclosure. For a power path or neck on the bench list: hold the current constant for at least 10 minutes, scan the whole path with the camera against a reference of known emissivity, and cross-check with a 4-wire drop hot and cold (`references/pcb-rules/general.md`, What to verify).
9b. **Test the cooling as it was decided** (`references/pcb-rules/thermal.md`): the hottest parts at full load with the enclosure closed, for at least 30 minutes, against the heat table; and, where there is a fan, once more with the fan unplugged: the device must protect itself and tell the user, as the design note says.
10. **Build the bench list** from every review UNKNOWN, every item that no simulation covers, every accepted deviation, every package-limited neck and every load that was never measured. Each becomes a numbered test (`BT-01`, `BT-02` ...) with a pass value. A destructive or hazardous fault test (a fuse clearing, a short at full source current, a battery fault) is not run on the user's bench: where the release table needs it (`references/reviews.md` section 8), it goes to the test owner named there, on sacrificial samples, with the simulated result beside it as support only; until it is done the board stays PROTOTYPE ONLY or a stated limited use. A board whose copper discoloured or smelt burnt in a fault test is retired (`references/pcb-rules/general.md` GEN-28).
10a. **Measure what the device draws** in every operating mode, against the forecast of gate 1 (`GATE1_SUMMARY.md`, power and running time), with numeric pass values written before the test; for a battery device work out the running time again from the measured figures and tell the user the result in plain words.
10b. **Put every requirement on the bench list.** Each `REQ-nn` gets a test that measures it on the real board, with its numeric pass value from the requirements page, or the line "shown by design: <proof>" where no bench can measure it (a 5-year life). The design is validated against what the user asked for, not only against its own calculations.
11. **When the boards arrive, the user does the work and you guide.** Give one step at a time, record expected and measured values in the findings register, and stop on a failure. Before suspecting the design, check the physical connections of that step. Repeat an observation before naming a cause, and change one thing at a time.
12. **Triage late review points** (from an outside reviewer or a review after the order). Check each against the real files and place it in one class: safe as ordered; safe with a bring-up step; fix at the assembler, only while that is still possible; next revision; not applicable. Give the evidence and keep the list short.
13. **Do not rework ordered files on numbers nobody measured.** Schedule the measurement and collect the change for the next batch.
14. **Write `NEXT_REV.md`:** per item the reason, the priority, what to do on the present boards meanwhile, and the evidence to collect on them first.
14b. **Prepare the production release** when the bench tests and the requirements table have passed: fill `templates/PRODUCTION_RELEASE.md` against the one release table (`references/reviews.md` section 8), each applicable row passed, "not applicable" with its fact, or missing with its owner (one board for the user's own use, not sold: one line in the state file replaces the record, `references/reviews.md` section 8). It names the exact files that were built and tested (checksums), the revision, what differs from them in the next build, the open deviations the user accepted, and how each later board is tested. Nothing is released from files that differ from the tested ones without saying so.
14c. **Update the firmware hand-over** with what the bench showed: measured facts, hardware errata of this revision and their work-arounds, open points settled; before production, the firmware owner completes its section 12 (release). Tell the user it changed.
15. **Close the loop.** When every applicable row of the release table is met, the user may sign PRODUCTION APPROVED; you never state it, and while a row is missing you name it and its owner instead of offering the signature. Add the lessons to the project log and propose to the user which of them belong in `references/lessons.md`.

## Questions for the user

- Which bench instruments do you have: current-limited supply, meter, oscilloscope, electronic load, thermal camera or thermocouples?
  - Suggested: I plan for supply, meter and oscilloscope, and mark the rest optional.
  - Why: every test names its instrument; a test without its instrument is listed as UNKNOWN, not skipped.
- (Lean set, a protection circuit or a load that costs more than the board) Shall an independent reviewer check the power-up plan before the boards arrive?
  - Suggested: yes.
  - Why: it checks that every protection test can really trip, so that nothing expensive meets an unproven board.
- `<Late change>`: rework it by hand at step 0, or ask the assembler to change it?
  - Suggested: by hand, if you have the tools for that part size.
  - Why: the assembler path is slow and uncertain once production has started; step 0 has a numeric check and a fallback.
- (Only when every applicable row of the release table is met) All bench tests passed (results attached). Do you sign this revision as PRODUCTION APPROVED?
  - Suggested: `<yes | no, after the P1 items of NEXT_REV.md>`.
  - Why: `<every row passed or not applicable: list>`. Your signature authorizes manufacture; the measurements are the proof.

## Checks before leaving this phase

- [ ] The plan existed before the boards arrived (boards designed or ordered elsewhere: before the first board was powered). Evidence: the date of `FIRST_POWER_UP.md` against the delivery table of `ORDER_LOG.md`, or, for boards from elsewhere, the user's word that no board was powered before.
- [ ] Every step has numeric expected and stop values with their source, the supply limits, and the list of connections. Evidence: the plan, step by step.
- [ ] Where the plan review ran, it states for each protection test that it can trip, with the reasoning, and its findings are closed; otherwise the state file says the dry run was the designer's own, and who declined the review. Evidence: `reviews/BU_BRING_UP_FINDINGS.md` and its closure file `reviews/VERIFY_<round>_BU.md`, or the state-file line.
- [ ] Every UNKNOWN, every item not covered by simulation and every accepted deviation maps to a test number. Evidence: the trace table in the plan.
- [ ] Step 0 has an entry with a pass value and a fallback for every change known since the order. Evidence: section 0 of the plan against the question table of `ORDER_LOG.md`.
- [ ] The measured value of every step done is recorded, as reported by the user. Evidence: the result columns and the findings register of the plan.
- [ ] Temperatures were logged in each load and fault test. Evidence: the temperature log in `out/`.
- [ ] Every late review point has a class and its evidence. Evidence: the triage table of `NEXT_REV.md`.
- [ ] Every requirement `REQ-nn` has a measured result or a named proof by design. Evidence: the requirements table of the plan.
- [ ] The production release record names the tested files by checksum, the revision and the accepted deviations, gives each applicable row of the release table its evidence, "not applicable" or its missing owner, and is signed by the user (one board for own use, not sold: the one line in the state file). Evidence: `PRODUCTION_RELEASE.md`.
- [ ] The lessons were proposed to the user, and the release state changed only with the user's words. Evidence: the message, the decision row of the state file.

## Outputs

- `FIRST_POWER_UP.md` with its trace table and findings register; where the plan review ran, `reviews/BU_BRING_UP_FINDINGS.md` and its closure file `reviews/VERIFY_<round>_BU.md`
- The temperature log and bench photos or readings in `out/`
- `NEXT_REV.md` with the triage table of late review points
- The requirements table of the plan, measured; `PRODUCTION_RELEASE.md` when the user releases the design
- `ORDER_LOG.md` (lessons) and `PROJECT_STATE.md` (results, release state, next action)

## Lessons behind this phase

- A crowbar test as first written could never trip: the circuit that fires it took its supply from a rail that was off in that set-up -> step 6 dry-runs every test and has it reviewed.
- An over-voltage step with a 1.5 A limit would have put tens of watts into a small clamp diode on overshoot; it became a 50 mA limit plus the supply's own over-voltage cut -> step 5.
- Readings were far too low and a board was suspected; a cable had not been connected -> steps 5 and 11 list and check the physical connections first.
- A supply limit from the first-power-up step was left in place for normal running -> step 8.
- A module's power pin was not in its maker's schematic; it was proven with a meter against a known rail before soldering -> step 7.
- A resistor value found wrong after the order became step 0, with a measured pass condition and a bridge as fallback -> step 3.
- An outside reviewer's points were checked against the real files: most were safe or not applicable, none needed a fix at the assembler -> step 12.
- A printed panel legend was questioned on numbers nobody had measured; the ordered parts were left alone and the measurement was scheduled -> step 13.

The full cases are in `references/lessons.md`.
