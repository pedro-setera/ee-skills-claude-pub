# Phase 11: board reviews and gate 2

Have fresh agents review the frozen board (one from the files, one from the pictures alone), fix what they find in one round, collect the user's waivers, and bring the user a gate 2 summary with an honest release state, in which whatever is still open is named as a risk.

## Inputs

- `out/CHECKS.md` on the saved board (phase 10), every row PASS or NOT APPLICABLE, or a FAIL, CANNOT RUN or UNKNOWN that phase 10 permits and lists for gate 2; for a brought-in board, `out/CHECKS.md` as it came out, every failure recorded as an intake finding.
- The board, schematic, netlist, rule file, trial package, interface file, 3D model, ledger, datasheets and the image set in `out/review/`.
- `references/reviews.md` (read it now) and the briefs `references/review-briefs/lean-board.md` and `visual.md`; where the depth switches them on, also `layout-electrical.md`, `layout-manufacturing.md`, `layout-mechanical.md`.
- `review_depth`, `depth_facts` and `review_parallel` from `PROJECT_STATE.md`.
- `templates/REVIEW_FINDINGS.md`, `templates/REVIEW_RESPONSE.md`, `templates/REVIEW_VERIFY.md`, `templates/GATE2_SUMMARY.md`.
- `references/lessons.md`, section "Phase 11: layout and visual reviews".

## Steps

**A board the user brought** (`references/existing-designs.md`): its catch-up documents (section 4: gate 1 evidence or the skip decision, parity, the ledger, the footprint audit, outline and stack confirmed by the user) come first, and an import from another tool is verified first (`scripts/import_design.py verify`; until it passes, every finding is marked "found on the import"). The findings and the change list (`templates/ECO_LIST.md`) go to the user; nothing is changed without a go that names the changes, and then only on the copy.

1. **Check that a review is worth its cost now.** Phase 10 is clean, and no decision that changes the copper is pending (layer count, outline, a connector move). Reviews of copper that is about to change are wasted; if such a decision arrives while reviews run, stop them. For a brought-in design: run the phase 10 checks on the copy, record every failure as an intake finding (it goes into the review summary), do not fix anything, mark missing simulations UNKNOWN, and launch the reviews anyway.
1b. **Decide the depth again, on the board as it is now** (`references/reviews.md` section 9): go through the facts one by one, with the BOM, the layer count and the finest pitch in front of you. One fact is enough; what you cannot rule out counts as present; up by yourself, never down without the user's yes. Write the depth and the facts into the state file and, if they changed since gate 1, tell the user in one line.
2. **Freeze by checksum.** Take the SHA-256 of the board file. Copy the files each brief lists, with `board.toml`, `REQUIREMENTS.md`, the saved supplier answers `out/jlc_parts_answers.json` and `out/BOM_STOCK_CHECK.md` (reviewers do not use the supplier's site) and the Waivers table of the state file as `WAIVERS.md`, to `reviews/frozen/pcb-r<round>-<first 12 characters of the SHA-256>/`, byte for byte; `<round>` is the number of the last completed fix round, counted over the whole project (0 when none has happened yet). Record the full checksum in the state file; every review header carries it too. Reviewers never read the design folder.
3. **Generate the images into the frozen copy** with `scripts/review_images.py`: its `review/` folder with `index.md` (the contact sheet naming every crop) and `designators.csv`. Add the assembly drawing, panel render and section views. Make a second, reduced copy for the picture-only reviewer (two of them in the full set), `reviews/frozen/<name>_visual/`, where `<name>` is the frozen copy's name: images only (`review/` and the schematic sheet images), plus `SILK_ID_BLOCK.md` and `WAIVERS.md`, nothing else.
4. **Launch the review, or the reviews, of the depth decided in step 1b** from their briefs:

   | Review | Runs when | ID prefix | Findings file in `reviews/` |
   |---|---|---|---|
   | Lean board | always, except when the full set runs | `LB` | `LB_BOARD_FINDINGS.md` |
   | Picture-only (visual) | always, started side by side with the board review: one agent, `V1` | `V1` | `V1_VISUAL_FINDINGS.md` |
   | Layout, electrical | a radio, an antenna, a satellite-navigation receiver, a signal above 100 MHz, a fast bus; the full set | `L1` | `L1_ELECTRICAL_FINDINGS.md` |
   | Layout, manufacturing | fine parts (pitch under 0.5 mm, pads under the body), more than 2 layers; the full set | `L2` | `L2_MANUFACTURING_FINDINGS.md` |
   | Layout, mechanical | the full set | `L3` | `L3_MECHANICAL_FINDINGS.md` |
   | Second picture-only reviewer, working apart | the full set | `V2` | `V2_VISUAL_FINDINGS.md` |

   - The picture-only reviewer gets the reduced copy and nothing else: no board file, no report of the board reviewer, no notes of yours. How the board looks to the eye (silkscreen, labels, polarity marks, legends, renders) is its judgement; the lean board reviewer opens images only as evidence for its own findings, so the two do not repeat each other. In the lean set put the time budget into its `<SCOPE>` (`references/review-briefs/visual.md`).
   - When an extra reviewer runs beside the lean one, fill the lean brief's `<EXTRA>` slot with that reviewer and the scope left to it; otherwise write "none".

   - Fill each brief's slots with paths inside the frozen copy, `<ORIGIN>` and `<INPUTS>` included (where the design comes from; which inputs exist and which do not), and send the brief as the whole prompt.
   - Set the most capable model and the highest effort explicitly in every call, write both in the state file, and read them back from the agent's first progress note. A reviewer on default settings is stopped and relaunched.
   - Run at most `review_parallel` at a time; start the next as soon as one reports.
   - Pass files, never conclusions. No reviewer sees another's report.
   - With an enclosure, the lean board reviewer (in the full set: `L3`) also judges the fit: give it the enclosure data and the fit result made in the project's own CAD from `mech/interface.json` of this checksum, or the FAIL "cannot run" with the section views.
   - Without sub-agents: one fresh session per review, one after the other, and say so in the summary.
5. **Leave the design alone while reviews run.** Findings must map to the frozen files.
6. **Accept a report only if it is complete:** the checksum reviewed, model and effort, counts, findings in the standard format, the table of images looked at with crop paths and what was seen, the coverage statement, the verdict. Send an incomplete report back to its author.
   - **Review only:** once the reports are accepted, run the supplier-rules review if the set holds it (`references/review-briefs/supplier-rules.md` on a package exported from the copy with `scripts/fab_package.py`, or on the user's own production files for an import; nothing else of phase 12). Then write `templates/AUDIT_SUMMARY.md` and the change list `templates/ECO_LIST.md`, give them to the user and stop. The fix-round steps run only on a go that names the changes.
7. **Collect all findings in one response file,** `reviews/RESPONSE_<round>.md`, the round numbered over the whole project: one row per finding ID, what will be done, or why not. Where two visual reviewers ran (the full set), merge their reports by union: a finding from either one counts.
8. **Rule on conflicts in writing.** Electrical placement wins over a label. When your ruling differs from a reviewer's proposal, write the ruling and its reason; the reviewer accepts or objects at the closure.
9. **Do the one combined fix round** for all findings, each fixed the simplest sound way (`references/working-rules.md` section 12): first ask whether the cause can be removed instead of a part added; a part added because of a review names the credible fault it answers, and the design note records it. Change the source, rebuild, run the whole phase 10 suite again, render again, look at every changed spot, and search the documents for every changed value. A fix that would change the schematic goes to the user first.
10. **Have each finding closed by the reviewer who raised it,** on a new frozen copy `pcb-r<round>-<first 12 characters>` with its new checksum, sent the same brief with a closure `<SCOPE>`: for every ID, "correct and complete?" and "new problem introduced?". The reviewer looks only at what was fixed, may raise a new finding only if a fix caused it, and writes `reviews/VERIFY_<round>_<prefix>.md`.
10b. **End the stage by the end rule** (`references/reviews.md` section 6). Do not open another round, and do not argue a finding closed yourself: a blocker still open is fixed and re-checked, that ID alone, until it is closed or the user has accepted it in writing; everything else still open, and any new finding of the re-check, becomes a row of the gate summary as a named risk with its bench test (or its check at order time) and the user's choice. A second fix round and re-check only where a fact switched it on (the full set), and no third.
11. **Keep the checksums straight.** If a small fix follows a closure, the final board has a new checksum. The summary names the checksum each review saw, and the difference to the final board is listed, looked at, and re-reviewed if it touches copper, footprints or silkscreen.
12. **Bring waivers to the user as one list.** Anything you propose to leave as it is, typically parts with no legal label spot, is shown with a zoomed crop per item, the options (accept; accept a closer or longer label; move parts, which means another route and review round) and a suggested answer. Record the answer with the date and the user's words. A failed limit that the user accepts is listed as an accepted deviation; the limit itself is not moved.
13. **Give every unlabelled part a readable reference on the assembly drawing,** inside its own body. Look at the drawing. Tell the bring-up plan how to find those parts.
14. **Check stock again on the day of the report** with `scripts/jlc_parts.py`: assembled parts against JLCPCB's assembly stock, hand-fit and off-board parts against LCSC, for the boards plus spares. For a short line, propose an in-stock equivalent before the gate: a part change after gate 1 needs the user's go, and on a brought-in design an equivalent that is not identical needs their OK. If it changes a value or a footprint it goes through the fix round.
14b. **Run the supplier-rules review before the gate,** so that the user approves the board once, knowing what every review found, and no finding changes the board after the approval. Run steps 1 to 7 of phase 12 now (`references/phases/12-production-files.md`), on the board as it stands after the re-checks: the export, the rotations, the BOM audit, the panel, the fab notes, the checks that read exports, then the supplier-rules review with its one fix round and one re-check under the end rule. Two-sided assembly: when the export stops only because the bottom-side convention is unconfirmed (phase 12, step 2), make the preview package (`scripts/fab_package.py --preview`) and upload it as for an order, with the hand-overs of phase 13 (sign-in, consent boxes), only up to the placement viewer (`references/jlcpcb/order-flow.md` steps 1 to 11): never saved to the cart, never paid; a cart item made by mistake is removed. Look at every part its manifest lists, top and bottom, save the crops to `out/order/crops/`, record `[[rotations.bottom_side_confirmed]]` (phase 12, step 2) and export again; only then run the supplier-rules review, on the complete package. Where those steps say "the approved board", read "the board as it stands now": the package is a draft, and nothing is frozen for the order before gate 2. A fix that changes the board goes through step 11 (new checksum; the difference listed, looked at, and re-reviewed if it touches copper, footprints or silkscreen). Review only, and production files brought with no board: as step 6 and phase 12 say.
15. **Write `GATE2_SUMMARY.md`** in plain words, the pictures and the one action first, with its two evidence tables filled from files: "Your requirements, one by one" (every `REQ-nn` against the board, filled from the chains of phase 10, step 7b) and "Will it work?" (signals, radio, currents, supplies, heat, noise, manufacture); a line without a named proof is UNKNOWN with its bench test. The page holds: the status line with the release state; the evidence status (gates evidenced or skipped with the user's words, what was not checked); the table of checks; the rules ledger counts; per review what was found and how each finding was closed; what the re-check left open, as named risks with their bench tests; the rulings; the waivers with the user's words; the cost block (`references/working-rules.md` section 11): cost per board now and at the later quantity against the target, per-order fees apart; the biggest cost drivers, each with whether a cheaper way to the same quality was found; what was kept as an unfitted footprint because its need is uncertain; and, if quality and the target cannot both be met, the options for the user to decide; the files with their checksums; every UNKNOWN with the bench test that will settle it.
16. **State the release state honestly** from the one release table (`references/reviews.md` section 8): REJECT or PROTOTYPE ONLY; a `DO NOT ORDER` finding of the supplier-rules review counts as a blocker. PRODUCTION APPROVED is never given here.
17. **Ask for gate 2.** Put the summary and the pictures where the user opens files, name the one action (approve the PCB), and wait. An opinion or a question from the user is not the approval; the approval accepts the listed UNKNOWNs and their bench tests. On approval, record the user's words and date and the approved board checksum.
18. **Bring the firmware hand-over to its final state** after the approval: generate the pin map again from the final netlist and compare it with the draft (list every pin that moved), add what the layout fixed (connector and test-point positions, the programming connector), set its state to FINAL with the board checksum, and tell the user where it is and what changed since the draft.

## Questions for the user

Waivers and the gate itself; for a design the user brought, also the two intake questions below.

- (A board the user brought, before the freeze) Are the outline, holes, stack and height limits as read from your files right (picture attached)?
  - Suggested: confirm, or correct the values marked.
  - Why: the mechanical and manufacturing reviews judge against them.
- (A design the user brought) `<part>` is short or not at LCSC. Use `<equivalent>`, which differs in `<what>`?
  - Suggested: `<yes | no: buy the part apart and fit it by hand>`.
  - Why: a part that is not identical changes their design; that is theirs to accept.
- `<n>` parts have no room for a silkscreen label (crops attached). Accept them with their references on the assembly drawing only?
  - Suggested: accept.
  - Why: moving them means another routing and review round; each stays findable on the drawing.
- Finding `<ID>` stays as it is: `<what, in one line>`. Accept it?
  - Suggested: `<accept with this bench test | change the board at this cost>`.
  - Why: `<consequence in plain words>`. Shown with the crop or the number.
- Do you approve this PCB for ordering as PROTOTYPE ONLY?
  - Suggested: approve.
  - Why: the review was re-checked on checksum `<first 12 characters>`; `<n>` waivers; `<k>` points still open, each named with its bench test.

## Checks before leaving this phase

- [ ] The depth was decided again on the board as it is and is in the state file with its facts; every review it names has a report naming model, effort and the checksum reviewed, with its images table, coverage statement and verdict. Evidence: `review_depth`, `depth_facts`; the findings files.
- [ ] `RESPONSE_<round>.md` has a row for every ID of every review. Evidence: the ID lists compared.
- [ ] Every ID was re-checked once by the reviewer who raised it, with "new problem introduced?" answered; no blocker is open unless the user accepted it in writing; every other open ID is a row of the gate summary with its bench test. Evidence: the `VERIFY_<round>_<prefix>.md` files; the open IDs compared with the summary's rows.
- [ ] The final board's checksum is recorded, and its difference to the last reviewed board is empty or re-reviewed. Evidence: the `frozen:` block of the state file, the difference list.
- [ ] The check suite was run again on the final board: every row PASS or NOT APPLICABLE, or a FAIL, CANNOT RUN or UNKNOWN that phase 10 permits and lists for gate 2. Evidence: `out/CHECKS.md` with the final checksum.
- [ ] Every waiver and accepted deviation carries a crop path, the date and the user's words. Evidence: the waivers table of the state file.
- [ ] Each unlabelled part has a readable reference on the assembly drawing. Evidence: a crop of the drawing per part.
- [ ] The stock report carries the date of the gate report. Evidence: `out/BOM_STOCK_CHECK.md`.
- [ ] The interface file and the 3D model carry the final board's checksum; with an enclosure, the fit check passed on them, or its FAIL "cannot run" went to the board reviewer (`LB`, or `L3` in the full set) with the section views. Evidence: the checksums, the fit result.
- [ ] The supplier-rules review ran on the draft order package before the user was asked for gate 2; its findings were re-checked once, and its result is in the gate summary. Evidence: `reviews/SR_SUPPLIER_RULES_FINDINGS.md`, `reviews/VERIFY_<round>_SR.md`, the row "Can it be made and assembled as drawn?" of the summary.
- [ ] `GATE2_SUMMARY.md` states the release state, and the user's approval is recorded. Evidence: the file, `gate2` and the decision row of the state file.
- [ ] Review only, instead of the gate: the intake findings, `AUDIT_SUMMARY.md` and the change list went to the user, and the copy is unchanged. Evidence: the files, and the copy's checksum equal to the freeze.

## Outputs

- `reviews/frozen/pcb-r<round>-<first 12 characters>/` and its `_visual` copy for each reviewed state
- `reviews/LB_BOARD_FINDINGS.md` and `V1_VISUAL_FINDINGS.md` (and, where the depth switched them on, `L1_ELECTRICAL_FINDINGS.md`, `L2_MANUFACTURING_FINDINGS.md`, `L3_MECHANICAL_FINDINGS.md`, `V2_VISUAL_FINDINGS.md`), each with its progress file `reviews/<prefix>_PROGRESS.md` and crops in `reviews/crops/<prefix>/`
- `reviews/RESPONSE_<round>.md`, `reviews/VERIFY_<round>_<prefix>.md`
- The draft order package in `out/jlc/` (and `out/panel/`; for two-sided assembly the preview package `out/jlc_preview/` and its crops in `out/order/crops/`), `reviews/SR_SUPPLIER_RULES_FINDINGS.md` and its closure file `reviews/VERIFY_<round>_SR.md`
- The waiver crops in `out/review/crops/`, the corrected assembly drawing, the dated stock report
- `GATE2_SUMMARY.md`; the state file with gate 2, the release state, the waivers and the approved board checksum

## Lessons behind this phase

- After clean designer checks, an independent review found that many small transistors and diodes would be placed rotated and one electrolytic reversed -> the board review of step 4 always derives the rotations again by itself.
- Two layout reviews were running when the layer count changed; they were stopped -> step 1.
- The board that was ordered was two small fix rounds later than the one re-reviewed -> step 11 names every checksum and covers the difference.
- Label checks passed, and the visual reviews still found four labels reading as the wrong part and a pin legend shifted by one pin -> step 4 always runs a picture-only review, by an agent that sees the images and nothing else; the full set runs two, working apart.
- Group labels made by a script put a name beside the wrong part; removing them left three parts unlabelled -> steps 12 and 13 take such parts to the user and onto the assembly drawing.
- All reviewers' findings went into one fix round, then scoped closures: one round less than fixing review by review -> steps 9 and 10.
- Four reviewers on a small two-layer board repeated each other and added no fault that would have cost the batch beyond what one careful reviewer and the designer's checks had found -> one board reviewer and one picture-only reviewer by default, more only where a fact about the board calls for them (step 1b).
- One part had barely enough stock for the batch, found on the review day -> step 14.
- A user approved a board, and only then did the check against the manufacturer's rules run on its order files: a finding there could have changed a board that was already approved -> step 14b runs that review before the gate, on a draft package.
- A simulation limit had been moved so that a test passed; a layout reviewer caught it -> step 12 records accepted deviations and never moves limits.

The full cases are in `references/lessons.md`.
