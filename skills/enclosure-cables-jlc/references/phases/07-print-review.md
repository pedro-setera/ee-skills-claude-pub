# Phase 7: reviews, the print, the fit check

Have fresh reviewers check the model and the pictures, fix once, let the user approve and print, then turn what fitted and what did not into corrections of the model. Metal is designed only after the printed box has fitted.

## Inputs

- The frozen candidate: model, `out/step/`, `out/views/`, `out/renders/`, `out/print/`, the slicer previews, `out/CHECKS.md`, `cables.json` with the route pictures.
- `references/reviews.md`, `references/review-briefs/model.md`, `references/review-briefs/visual.md`; `templates/REVIEW_FINDINGS.md`, `templates/GATE1_SUMMARY.md`, `templates/PRINT_FINDINGS.md`.
- The review depth in the state file (lean: two reviewers side by side; raised: plus a second model review).

## Steps

1. **Freeze the candidate.** Run `python -I <skill folder>/scripts/build.py --project <project>/mech` and `check_all.py`; then `python -I <skill folder>/scripts/freeze.py --project <project>/mech --name print-r1 --profile review --include "out/print/**"` and, for the picture-only reviewer, `--name print-r1_visual --profile visual --include "out/print/*.png"` plus its two text files. It refuses a stale build or a stale check row, copies the files into `reviews/frozen/print-r1/`, writes `print-r1.MANIFEST.sha256` beside it and prints the lines for the `frozen:` block of the state file: paste them. A review of files that changed underneath it proves nothing.
2. **Start the reviewers,** at most two at a time, each a fresh agent on the most capable model at the highest effort, both set explicitly and written in the report. Give the frozen files and the brief, no conclusions:
   - the model review (`review-briefs/model.md`): fit, printability in print orientation, heat, cable routes;
   - the picture-only review (`review-briefs/visual.md`): it gets the views, renders and slicer previews and nothing else.
   The designer never reviews its own work. Reviews by scripts and imagination once missed a connector over a screw hole and wrong details in renders; the user found the same fault twice.
3. **Read the reports.** Each finding has a severity, the evidence, and a picture crop. A report that lists no image it opened is sent back.
4. **One fix round.** Fix in the model, run the build, and give each reviewer only its own fixed findings to re-check on the new files. No further round. A blocker is closed, or accepted by the user in writing. Everything else still open goes to the gate as a named risk with a zoomed picture.
5. **Gate 1.** Send `GATE1_SUMMARY.md`: the conclusion and the one action first (print the coupon, then these parts), the print file list with folder, orientation, time and grams, the open risks with pictures, the settings the model relies on. The user approves the print files in writing. Starting a print is always the user's.
6. **Give the print order and the after-print list** (in `PRINT_FINDINGS.md`), in this order, with a picture per item:
   1. the coupon: which hole takes each screw, which tab clearance fits;
   2. each part off the bed: warp, layer faults, bridges;
   3. each screw driven by hand into its post; each countersink flush;
   4. each connector and panel part through its wall, with washer and nut;
   5. each board on its stands, every hole in line;
   6. the lid on and off; the fit of soft frames or feet;
   7. each cable along its route, when cables or stand-ins exist;
   8. the first power-up run with the lid closed, when the user wants it (temperatures logged).
7. **Record the findings as numbers.** For every item: fits or does not, the measured value, a photo. Ask for a calliper reading where a number decides (printed hole against drawn hole). A first printed shell was scrapped for three reasons at once (holes small, a head tunnel too tight, a post too close to a flat cable); each became a named value in the model.
8. **Put the findings back into the model.** Change named values, never one-off patches; write each change in `DECISIONS.md`. Update the printer profile with the user's OK. Run the build and the audit again. Reprint only what changed.
9. **Write what fitted and what did not** at the end of `PRINT_FINDINGS.md`: the positions and clearances that are now proven are the ones the metal version reads in phase 8.
10. **Close the phase** when the printed box has fitted, or the user accepts the open items in writing. The metal design does not start while a print is still running: the print finds what the model cannot.

## Questions for the user

- Do you approve these print files? (summary, pictures, time and grams)
  - Suggested: yes, coupon first.
  - Why: both reviews are closed; the open risks are listed with pictures.
- The reviewer found `<finding>` (picture). Fix it before the print, or accept it?
  - Suggested: `<fix, or accept with the reason>`.
  - Why: `<what it costs either way>`.
- Please report each item of the after-print list with a photo.
  - Suggested: in the order given.
  - Why: the order follows the assembly, so one visit to the bench covers it.
- May I write the measured hole size and clearance into your printer profile?
  - Suggested: yes.
  - Why: the next project then starts from your printer's real numbers.

## Gate 1 checklist

- [ ] The candidate was frozen and hashed before the reviews. Evidence: `reviews/frozen/print-r1/`, the checksums in the state file.
- [ ] The model review and the picture-only review ran apart, model and effort stated. Evidence: the two reports.
- [ ] Each report lists the images it opened and what was seen, with crops. Evidence: the reports.
- [ ] One fix round; each fix re-checked by the reviewer who raised it. Evidence: the re-check sections.
- [ ] No blocker is open; each remaining finding is a named risk with a picture. Evidence: `GATE1_SUMMARY.md`.
- [ ] The build is current and the files' folder was told to the user. Evidence: the build output, the message.
- [ ] The user approved the print files. Evidence: their words and the date.

## Done when (after the print)

- [ ] Every item of the after-print list has "fits" or "does not", a number where one decides, and a photo. Evidence: `PRINT_FINDINGS.md`.
- [ ] Every "does not" is a changed named value, or a line in `NEXT_REV.md`, or accepted by the user. Evidence: `DECISIONS.md`.
- [ ] The printer profile holds the measured values. Evidence: the profile, the user's OK.
- [ ] The corrected model builds with no stale file. Evidence: the build output.

## Outputs

- `mech/reviews/` (reports, frozen copies), `mech/GATE1_SUMMARY.md`
- `mech/PRINT_FINDINGS.md`, the corrected model, the calibrated printer profile
- `PROJECT_STATE.md`: gate 1, the findings status, the waiver if the print was waived

## If something is missing

- The user waives the print: record their words. Phase 8 may start, every later summary says "print not evidenced", and the fit risks are named at gate 2.
- Only one reviewer can run: run them one after the other; never merge the two briefs into one agent.

## Lessons behind this phase

- Reviews by scripts and imagination missed a connector over a screw hole and wrong render details -> step 2: a reviewer that sees only pictures.
- The designer's own check passed files that a fresh reader failed -> step 2: fresh agents with a brief and no conclusions.
- Review rounds without an end delayed a print by days -> step 4: one fix round, one re-check.
- A first printed shell was scrapped for three faults that one coupon would have shown -> steps 5 and 6: the coupon first.
- Print findings were fixed as one-off patches and came back in the next version -> step 8: named values only.
- The metal design was started while the print was still running, and then changed -> step 10.

The full cases are in `references/lessons.md`.
