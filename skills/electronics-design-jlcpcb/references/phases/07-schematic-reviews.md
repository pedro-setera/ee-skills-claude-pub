# Phase 7: schematic reviews and gate 1

Have an independent reviewer try to break the schematic, fix what it finds in one round, and bring the user a one-page gate 1 summary in which whatever is still open is named as a risk.

## Inputs

- Everything phases 2 to 6 left: schematic export, netlist, BOM, `DESIGN_NOTE.md`, `REFERENCE_CHECK.md`, `LAYOUT_RULES_LEDGER.md`, the intent file and its report, `sim/`, `vendor/datasheets/`.
- `references/reviews.md` (rules, severities, the fix round and its end rule, waivers, the depth) and the brief `references/review-briefs/lean-circuit.md`; where the depth switches them on, also `schematic-datasheet.md`, `schematic-system.md`, `schematic-fresh-eyes.md`.
- `templates/REVIEW_FINDINGS.md`, `templates/REVIEW_RESPONSE.md`, `templates/REVIEW_VERIFY.md`, `templates/GATE1_SUMMARY.md`.
- The state file: `review_depth`, `depth_facts`, `review_parallel`.
- `references/lessons.md`, section "Phase 7: schematic reviews".

## Steps

**A design the user brought** (`references/existing-designs.md`): its catch-up documents (section 4) come first, and an import from another tool is verified first (`scripts/import_design.py verify`; until it passes, every finding is marked "found on the import"). The findings and the change list (`templates/ECO_LIST.md`) go to the user; nothing is changed without a go that names the changes, and then only on the copy.

1. Run the designer's own checks fresh, on the files as they are now: ERC 0 and 0, lint clean, netlist check passing with its self-test, `ratings_check.py` and (a programmable chip) `pin_function_check.py` passing, the full simulation suite (and, where the depth switched the coverage audit on, that audit closed by its end rule in phase 6), the stock report dated today, every sheet image looked at. A review spent on a design that fails its own checks is wasted. For a brought-in design: run these checks, record every failure as an intake finding (it goes into the review summary), do not fix anything, mark missing simulations UNKNOWN, and launch the reviews anyway.
1b. Decide the depth again, on the circuit as it is drawn now (`references/reviews.md` section 9): go through the facts, one by one, with the parts list open. One fact is enough; what you cannot rule out counts as present; the depth moves up by itself and never down without the user's yes. Write the depth and the facts into the state file (`review_depth`, `depth_facts`) and, if they changed since gate 0, tell the user in one line.
2. Freeze. Copy the files under review to `reviews/frozen/sch-r<round>-<first 12 characters of the SHA-256>/`. The checksum is the SHA-256 of the exported netlist; `<round>` is the number of the last completed fix round, counted over the whole project (0 when none has happened yet). The state file and every review header hold the full value. The copy holds everything the briefs list, `src/datasheet_pins.toml` and `out/ratings_check.md` included: a reviewer never reads the design folder, so a file that is not in the copy cannot be reviewed.
   - The copy holds what the briefs list: `schematic.pdf`, the sheet images with the block diagram and power tree in `images/`, `netlist.net`, the BOM, the requirements, the design note, the reference check, the ledger, the intent file and its report, `src/pin_use.toml` and `out/pin_function_check.md` (a programmable chip), `out/netlist_screens.md` (where the screens ran), `sim/`, `vendor/datasheets/`, the saved supplier answers `out/jlc_parts_answers.json` and `out/BOM_STOCK_CHECK.md` (reviewers do not use the supplier's site), and the waiver table of the state file as `WAIVERS.md`.
   - Only when the full set runs: inside it, make a reduced copy `fresh-eyes/` for the fresh-eyes reviewer: PDF, sheet images, netlist and BOM only.
   - Reviewers never read the design folder. Leave the design alone while reviews run, so that findings map to the frozen files.
3. Launch the review, or the reviews, of the depth decided in step 1b, from their briefs:

   | Review | Runs when | ID prefix | Findings file in `reviews/` |
   |---|---|---|---|
   | Lean circuit | always, except when the full set runs | `LC` | `LC_CIRCUIT_FINDINGS.md` |
   | Datasheet | a switching converter, more than 2 A, more than 30 V; the full set | `S1` | `S1_DATASHEET_FINDINGS.md` |
   | System | a microcontroller or other programmable chip; the full set | `S2` | `S2_SYSTEM_FINDINGS.md` |
   | Fresh eyes | the full set | `S3` | `S3_FRESH_EYES_FINDINGS.md` |

   - When an extra reviewer runs beside the lean one, fill the lean brief's `<EXTRA>` slot with that reviewer and the scope left to it; otherwise write "none".

   - Fill each brief's slots with paths inside the frozen copy, `<ORIGIN>` and `<INPUTS>` included: where the design comes from, and which inputs exist and which do not. Send the brief as the whole prompt.
   - Set the most capable model and the highest effort explicitly in each agent call, and note both in the state file.
   - Pass no conclusions. Doubts of your own go in as questions, with the sentence that they are suspicions, not facts.
   - Reviewers do not see each other's reports.
   - Run at most `review_parallel` at once (default 2).
   - Without sub-agents: one fresh session per review, one after the other, and say so in the summary.
4. Check each launch: read the model and effort back from the agent's first progress note. A reviewer on default settings is stopped and relaunched.
5. Accept a report only if it is complete in the form its brief sets: for the lean circuit review, its first page as its brief lists it and a crop for every finding that rests on an image; for the others, reviewed checksum, model and effort, counts, method, findings in the standard format, the table of images looked at with crop paths and what was seen, the coverage statement, the verdict. Send an incomplete report back to its author.
   - **Review only:** once these reports are accepted, run the rest of the set for what was brought (`references/existing-designs.md` section 3; with a board, phase 11 comes next, without its fix round). After the last review of the set, write `templates/AUDIT_SUMMARY.md` and the change list `templates/ECO_LIST.md`, give them to the user and stop. The fix-round steps run only on a go that names the changes.
6. Run the one combined fix round for all reports (`references/reviews.md`, section 6):
   - Write `reviews/RESPONSE_<round>.md`: one row per finding ID, none skipped. Blockers and majors are fixed, or solved another way with evidence. Minors are fixed or justified in a line. Notes are read and answered. The round number counts over the whole project.
   - Fix each finding the simplest sound way (`references/working-rules.md` section 12): first ask whether the cause can be removed instead of a part added. A part added because of a review names the credible fault it answers, and the design note records it.
   - Change the design source, never an output. Update the intent file by hand for each intended change.
   - Regenerate and re-run: ERC, lint, netlist check with self-test, `ratings_check.py`, `pin_function_check.py` (a programmable chip), BOM, line audit, stock for new parts.
   - Re-run the affected simulations. A scenario a reviewer called missing gets a test, limit first, when it belongs to the extent of the campaign (a fault that can really happen, something a calculation cannot answer); otherwise it gets a calculation or a bench test, and the response says which.
   - Search every document for each changed value, reference and part number, and correct it: design note, reference check, ledger, notes on the sheets.
   - Export the images again and look at them.
   - Freeze again as `sch-r<round>-<first 12 characters>` with this round's number. The round in the name keeps the folders apart when the netlist did not change (only documents or simulations did).
7. The one re-check, by the finder. Each reviewer verifies its own findings on the new frozen copy: a diff of old against new netlist, its own re-runs, and for every ID "correct and complete?" and "new problem introduced?". It looks only at what was fixed and may raise a new finding only if a fix caused it. It writes `reviews/VERIFY_<round>_<prefix>.md`. Continue the same agent where possible; otherwise launch a fresh one with the same brief and its closure scope, plus the findings file and the response.
8. End the stage by the end rule (`references/reviews.md` section 6). Do not open another round, and do not argue a finding closed yourself:
   - a blocker still open: fix it and have the finder re-check that ID alone, until it is closed or the user has accepted it in writing;
   - everything else still open, and any new finding of the re-check: one row each in the gate summary as a named risk, with what is known, what is not, the bench test for the first boards with its pass value, and the user's choice;
   - a second fix round and re-check only where a fact switched it on (the full set), and no third.
9. Bring every FAIL or deviation the design keeps that changes what the user gets (a function, a limit they stated, the cost, a risk of losing a board) to the user on its own, as a waiver request: the item, the evidence (a crop or a number), the consequence, the options, a suggestion; at most three in one message, the rest in further rounds. Record the answer with the user's words. A waiver is never the designer's or a reviewer's to give. List every other FAIL and deviation with your ruling, and every UNKNOWN with the bench test that will settle it, in the gate summary; the user's approval of the gate is the acceptance of that list (`SKILL.md` rule 9), and an UNKNOWN on a blocker-level item blocks the gate.
10. On the day of the summary, check stock again and update the cost: fixes add parts, and added protection parts are often extended lines.
11. Write `GATE1_SUMMARY.md` in plain words, with the status, the one action and what the approval covers on the first screen; the tables follow. Fill its two evidence tables from files, never from memory: "Your requirements, one by one" (every `REQ-nn`: the block that meets it, the proof, the status) and "Is the circuit right?" (pins, ratings, supply order, worst case, faults, what has no evidence). A line without a named proof is UNKNOWN with its bench test. The rest of the page:
    - what the board does, in three to five lines;
    - the check results with their files;
    - what each review found and how it was fixed: counts per severity, the rounds, the one change that mattered most;
    - the simulations: how many, what they changed, which models are stand-ins;
    - the power and running-time block, from step 7c of phase 5: the forecast per mode, the average, the battery and the running time against what the user asked for (or the consumption against the supply), the assumptions that use or firmware decide; the user's approval fixes the battery for the PCB;
    - the cost block (`references/working-rules.md` section 11), which ends with the line that the approval of this gate is also the go for the PCB at this parts cost and names the priced parts list: cost per board now and at the later quantity against the target, per-order fees apart; the biggest cost drivers, each with whether a cheaper way to the same quality was found; what was kept as an unfitted footprint because its need is uncertain; and, if quality and the target cannot both be met, the options for the user to decide;
    - what the re-check left open, as named risks; accepted deviations, the deviations you ruled on, waivers and every UNKNOWN with its bench test. Each item that changes what the user gets is asked on its own (step 9: at most three per message, in rounds); the rest are accepted with the gate, and the page says so;
    - the evidence status: what was checked, what was skipped with the user's words, what was not checked;
    - what a schematic review cannot prove (footprints, placement rotation, harness wiring) and the bench tests planned for the first boards;
    - the frozen netlist checksum and the path of the schematic PDF.
12. Put the summary and the PDF where the user opens files, check they are newer than their sources, send the agreed notice, and ask for approval. Say in the request what the approval covers: the schematic, the parts cost, and the battery and running time (or the power drawn).
13. On approval, record the user's words and date, set `gate1` in the state file, store the approved netlist checksum, and write the path of the approved netlist in its frozen copy as `reference` under `[netlist_compare]` of `board.toml`. From here on the schematic changes only with the user's go.
14. **Write the firmware hand-over, as a draft** (`templates/FIRMWARE_HANDOVER.md`), when the board carries a part that is programmed (a microcontroller, programmable logic, a module with its own firmware); otherwise note "no firmware" in the state file. It gives whoever writes the firmware, a person or an agent, everything about the hardware in one place: the pin map generated from the approved netlist (`python -I scripts/netlist_check.py --project <board folder> --pins`) and completed from the datasheets, the buses and addresses, the analog scalings, what the firmware switches and in which order, what the user must see and press, the debug and programming access, the limits the code must keep. Every line names its source; nothing from memory. Tell the user that it is ready, where it is (`FIRMWARE_HANDOVER.md` in the board folder), and that it is a draft: pins can still move until the PCB is approved, so firmware work can start but pin numbers are not final.

## Questions for the user

- (A design the user brought, before the freeze) Is this one-page description of what the board must do right? It was recovered from your files and words.
  - Suggested: confirm, or correct the lines marked "assumed".
  - Why: the reviewers judge the circuit against it; a wrong description gives a wrong verdict.
- Finding `<ID>` stays as it is: `<what, in one line>`. Accept it?
  - Suggested: `<accept with this bench test / change the design at this cost>`.
  - Why: `<consequence in plain words>`. Shown with the crop or the number.
- Do you approve the schematic, the parts cost of `<x>` per board, and the battery and running time (or the power it draws), so that the layout can start?
  - Suggested: approve.
  - Why: `<n>` findings closed; `<k>` still open, each named with its bench test; `<m>` simulations pass; cost `<x>`.

## Checks before leaving this phase

- [ ] The frozen copies exist and their checksums are in the state file. Evidence: `reviews/frozen/`, the `frozen:` block.
- [ ] The depth was decided again on the circuit as drawn and is in the state file with its facts; the reviews that ran are the ones it names, and each was a fresh agent given only the frozen path. Evidence: `review_depth`, `depth_facts`; the saved brief texts, the "agents" table of the state file.
- [ ] Each findings file is complete in the form its brief sets (step 5): model and effort, the checksum, the verdict, what was covered and what not, a crop path for every finding from an image, and the table of images where the brief asks for it. Evidence: the files.
- [ ] `RESPONSE_<round>.md` has a row for every ID of every review. Evidence: the ID lists compared.
- [ ] Every ID was re-checked once by the reviewer who raised it, with "new problem introduced?" answered; no blocker is open unless the user accepted it in writing; every other open ID is a row of the gate summary with its bench test. Evidence: the `VERIFY_<round>_<prefix>.md` files; the open IDs compared with the summary's rows.
- [ ] After the last change: ERC 0 and 0, netlist check passing with its self-test, `ratings_check.py` and (a programmable chip) `pin_function_check.py` passing, the full simulation suite re-run on the final netlist. Evidence: reports dated after the last source change, all on the same netlist checksum.
- [ ] Every changed value was searched in all documents. Evidence: the list of searched values with 0 stale hits.
- [ ] The stock report is dated the day of the summary and covers the planned quantity; the cost table is updated. Evidence: `out/BOM_STOCK_CHECK.md`, the cost section.
- [ ] Every waiver and accepted deviation carries the user's words and date. Evidence: the waivers table of the state file.
- [ ] `GATE1_SUMMARY.md` has the status, the one action and what the approval covers on its first screen, in plain words, sits in the user's folder and is newer than its sources. Evidence: the file and its time.
- [ ] The user's approval and the approved netlist checksum are recorded. Evidence: `gate1` and the decision row; `[netlist_compare] reference` in `board.toml`.
- [ ] Review only, instead of the gate: the intake findings, `AUDIT_SUMMARY.md` and the change list went to the user, and the copy is unchanged. Evidence: the files, and the copy's checksum equal to the freeze.

## Outputs

- `reviews/frozen/sch-r<round>-<first 12 characters>/` for each round
- `reviews/LC_CIRCUIT_FINDINGS.md` (and, where the depth switched them on, `S1_DATASHEET_FINDINGS.md`, `S2_SYSTEM_FINDINGS.md`, `S3_FRESH_EYES_FINDINGS.md`), each with its progress file `reviews/<prefix>_PROGRESS.md` and crops in `reviews/crops/<prefix>/`
- `reviews/RESPONSE_<round>.md`, `reviews/VERIFY_<round>_<prefix>.md`
- `GATE1_SUMMARY.md`, the dated stock report, the state file with gate 1 set

## Lessons behind this phase

- A schematic was reported ready with ERC clean and one of five sheets read closely. The first independent review found a merged net that would have destroyed the board, and four major faults -> no gate 1 without the independent reviews.
- The second review, on the fixed design, still found two major faults (back-feed through a serial line, unprotected partial shorts). The verification round then showed that one fix failed at the other signal level the peripheral's datasheet allows -> every fix goes back to its finder, and the re-check asks whether the fix is complete and whether it brought a new problem.
- A filter capacitor added as a fix changed the order in which two protections fired and made the written behaviour wrong -> closure asks "new problem introduced?", and every changed value is searched in all documents.
- A review agent was started on default effort and had to be stopped and relaunched -> model and effort are set in the call and read back.
- On a simple board the reviews went round after round; every pass found something finer, none of it wrong, and the gate was not reached -> one review, one fix round, one re-check; what is open then goes to the user as a named risk.
- Reviewers were given the designer's six doubts, marked as not to be taken as given, and still found the faults the designer had not thought of -> doubts go in as questions, conclusions never.
- An outside reviewer who saw only the schematic PDF raised points; several did not apply because the other files were missing, and one was a real functional fault everyone else had missed -> every circuit review begins with a read of the drawing as a stranger (the full set gives it a reviewer of its own), and each report states what its author could see.
- Fixes added protection parts; the sample cost rose by about a quarter and new extended lines appeared -> stock and cost are checked again before the summary.
- The user asked whether there would be smoke at the first power-on -> the summary says what a schematic review cannot prove and which bench tests cover it.

The full cases are in `references/lessons.md`.
