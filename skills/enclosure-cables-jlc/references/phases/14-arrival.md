# Phase 14: arrival and fit check

Write the incoming check before the parcel arrives, then let the user measure and assemble in a fixed order, and turn every result into "fits" or "does not" with a number and a photo.

> **PROVISIONAL (waits for evidence):** this whole phase. The measure lists and the order of the fit check are designed from the drawings and from the checks of the model; they have not yet been proven on a first real arrival and assembly. What will be measured then: whether each planned measurement really finds the fault it is meant to find, the time it takes, and which items were missing from the lists.

## Inputs

- The frozen revision: drawings (`out/drawings/`), `drawing_manifest.json`, the ink sheet, `cables.json`, the cable drawings, the confirmed production drawings.
- `HEAT_TABLE.md` with `out/heat/bench_test_list.md`, `GROUND_MAP.md`, the arrival test list of phase 4, `PRINT_FINDINGS.md`.
- `templates/INCOMING_CHECK.md`, `templates/FIT_REPORT.md`, `templates/NEXT_REV.md`; `references/review-briefs/arrival-plan.md`.
- The capability sheets (the supplier's own tolerances are the pass limits).

## Steps

1. **Write the incoming check while the order is in production** (`arrival/INCOMING_CHECK.md`). Per metal part, from the drawing's own numbers:
   - count and condition (dents, scratches, bent flanges);
   - 3 to 6 key sizes that decide the fit (overall length and width, the distance between the mounting faces, one flange height), each with the drawing value and the supplier's tolerance;
   - the positions of the holes that locate boards and panel parts, measured from the drawing's datum;
   - every cut-out that takes a part, measured AFTER the coat;
   - every nut: present, on the right side, the thread clean (a screw by hand); taps ready where the coat entered a thread;
   - the bend angles by a square; the coat colour and gloss against the chart name; every ink against the chart; the print position against two reference edges; anything coated that was drawn bare, or the reverse.
2. **Per cable:** count; the length between the points the drawing defines, against length and tolerance; every position by continuity against the wiring table (both directions, and no connection to a neighbour); the gauge and cable type by eye and by the print on the jacket; the connector part numbers where marked; the label text and its place; the pin-1 mark; angled plugs against the orientation picture; a gentle pull on every crimp.
3. **Give every item its tool and its pass limit** (calliper, steel rule, multimeter, a screw of the right size) and a photo instruction. Write the list in the order of unpacking, so that the user measures once.
4. **Offer the review of the plan.** One fresh agent (`references/review-briefs/arrival-plan.md`) asks of each planned measurement: can it really show the fault it is meant to find? Lean depth offers it; raised depth runs it.
5. **When the parcel arrives, the user measures and photographs;** you record. Each result is "fits" or "does not" with the measured number. Do not fill a number the user did not report. Photos go to `arrival/photos/`.
6. **Report shortfalls to the supplier only on the user's decision,** with the rules of phase 13: their order and part numbers, the drawing value against the measured value, one picture, a short numbered message, shown first.
7. **Run the assembly fit in the model's order** (`ASSEMBLY_ORDER`), recording in `arrival/FIT_REPORT.md`:
   1. every board on its stands, every screw by hand;
   2. every panel part through its wall with washer and nut, and the thread left for the plug;
   3. every connector's mating plug from outside;
   4. each cable along its route: reaches both ends, its slack, its smallest bend, nothing pinched by the lid;
   5. the lid on and off, the gaps, the screw alignment;
   6. the planned hand-work (scraping, washers, taps), with the minutes it took.
8. **Run the electrical and physical tests of the arrival list:** ground continuity at every bond of `GROUND_MAP.md` (under 1 ohm); polarity of every power cable before anything is plugged in (a lead folded the wrong way once swapped supply and ground inside a closed box); the heat run to a steady state with the lid closed, logging the points of the bench test list against the estimate; the radio through the closed box, if there is one, against the pass number of its test plan; stiffness by hand against the estimate.
9. **Write the fit report:** conclusion first (usable as it is, usable with hand-work, or not), then the table. Each "does not" names the cause as far as known (design, drawing, supplier, tolerance) and which side must change: the box, the cable or the board.
10. **Write the next-revision list** (`arrival/NEXT_REV.md`): one line per change, its evidence, and the phase it re-enters. Fit findings that touch the board go to the electronics side.
11. **Feed the numbers back:** measured coat build-up, real cable lengths against the order, hand-work minutes, real temperatures. They are the evidence that the PROVISIONAL lines of phases 4, 5, 8 and 13 wait for; propose them in phase 16.

## Questions for the user

- Shall a fresh reviewer check the arrival plan before the parcel comes?
  - Suggested: yes when the batch is costly or for sale; otherwise optional.
  - Why: it asks whether each measurement can really catch its fault; it costs little while you wait.
- Please measure and photograph the items of the list, in its order.
  - Suggested: one sitting, calliper and multimeter at hand.
  - Why: the list follows the unpacking and then the assembly, so nothing is handled twice.
- `<part>` is out of the supplier's tolerance (`<drawing value>` against `<measured>`). Report it to the supplier, or use it?
  - Suggested: `<use with the named hand-work | report>`.
  - Why: `<what a claim costs in days against what the fault costs>`.

## Done when

- [ ] `INCOMING_CHECK.md` existed before the parcel arrived, every item with its drawing value, tolerance, tool and photo instruction. Evidence: the file's date.
- [ ] Every item has "fits" or "does not", the measured number and a photo, as reported by the user. Evidence: the filled file, `arrival/photos/`.
- [ ] Every cable has its length and a full continuity table. Evidence: the cable section.
- [ ] The assembly fit ran in the model's order; the hand-work minutes are written. Evidence: `FIT_REPORT.md`.
- [ ] Continuity, polarity, the heat run and the radio test (if any) each ended pass, fail or could not run, with numbers. Evidence: the test table.
- [ ] Every "does not" is a line in `NEXT_REV.md` with its owner side, or accepted by the user. Evidence: the file.

## Outputs

- `arrival/INCOMING_CHECK.md`, `arrival/FIT_REPORT.md`, `arrival/NEXT_REV.md`, `arrival/photos/`
- The measured numbers for phase 16
- `PROJECT_STATE.md`: arrival status, next action

## If something is missing

- No calliper or multimeter: the check shrinks to counts, screws by hand and assembly; the missing rows read "could not run", never "fits".
- Only cables or only the case arrived: check what is there; the assembly fit waits and the state file says for what.

## Lessons behind this phase

- A power lead folded the wrong way inside a closed box swapped supply and ground -> step 8: polarity before plugging in.
- Zones drawn bare were ordered from a supplier that coats all over, and threads can hold coat -> step 1: nuts tried with a screw, taps ready, bare or coated noted.
- Cable lengths were trusted from the order confirmation -> step 2: measured against the drawing, pin maps by continuity.
- A heat estimate was taken as a result -> step 8: the run to a steady state, the numbers next to the estimate.
- The lists above come from the design side and still wait for a first real arrival (see the PROVISIONAL line).

The full cases are in `references/lessons.md`.
