# Phase 10: independent checks and the fix round

Fresh agents, working apart, check the files that will be uploaded: against the supplier's live rules, against the catalogue, as the supplier's engineer would read them, against the cable data, and by eye. One fix round, one re-check, then the user approves the frozen design.

## Inputs

- The upload folders `out/upload/<supplier>/`, the field sheets, the remarks, `out/CHECKS.md`, `cables.json`, the board's pin-out or netlist.
- The capability sheets and the suppliers' live rule pages (the reviewers re-read them that day).
- `references/reviews.md`; `references/review-briefs/supplier-rules.md`, `catalogue-and-drawings.md`, `cable-drawings.md`, `visual.md`.
- `scripts/catalogue_scan.py`, `scripts/sheet_dfm.py`, `scripts/drawing_vs_step.py`, `scripts/cable_check.py`, `scripts/check_all.py`, `scripts/build.py`.
- `templates/REVIEW_FINDINGS.md`, `templates/GATE2_SUMMARY.md`.

## Steps

1. **Freeze the candidate.** Run `build.py` and `check_all.py` (no failed and no stale row, or each is listed), then `freeze.py --project <project>/mech --name order-r1 --profile order` (upload folders, field sheets and remarks), `--name order-r1_review --profile review` for the reviewers who read the model and the drawings, and `--name order-r1_visual --profile visual --include "out/cables/drawings/*.png" "out/cables/pictures/*.png"` for the picture-only reviewer. Paste the printed lines into the state file.
2. **Start the lean set of four reviews,** at most two at a time, each a fresh agent on the most capable model at the highest effort (set explicitly, written in the report), with the frozen files and its brief and no conclusions of yours:
   1. **Supplier rules** (`supplier-rules.md`): reads every rule page of the supplier that day and measures the exported STEP, DXF and PDF with its own code. It also corrects the capability sheet where the live page differs.
   2. **Catalogue and drawings, read as the supplier's engineer** (`catalogue-and-drawings.md`): every word in a remark, a PDF, a layer name or a field value that is not a field option or a chart name; and for each drawing, "is there anything I would have to ask?"
   3. **Cable drawings** (`cable-drawings.md`): each drawing against `cables.json` and the board's pin-out, position by position.
   4. **Picture-only** (`visual.md`): the renders, every drawing page, the ink sheet, the print file opened in a plain viewer on a dark background, every cable drawing. It gets pictures and nothing else.
   A raised depth adds a second picture-only review.
3. **Why the first review is not optional.** On one order the builder's own checks all passed; the independent check on the exported files found several failures: bends that were not true cylinders, a nut with no tab under it, a channel 1 mm too narrow, nuts too close to edges, sliver faces, letter gaps under the minimum, print running into a cut-out. After the fixes the supplier asked no geometry question at all.
4. **Why the second one is not optional.** All three questions that held the same order (masking, a non-chart colour, non-chart inks) were already on the project's own open list. The catalogue review treats "if possible" and "fallback" as requests and every non-catalogue word as a blocker.
5. **Collect the findings** in `reviews/` (one `REVIEW_FINDINGS` file per reviewer): severity, evidence, picture crop, the file and place. A report that lists no opened image is sent back.
6. **One fix round.** Fix in the sources (model, artwork, `cables.json`, `mech.toml`, remark), never in an exported file. Run `build.py`, `check_all.py` and `catalogue_scan.py` again. Give each reviewer only its own fixed findings on the new files. Then no further round.
7. **Sort what is left.** A blocker is closed, or accepted by the user in writing as a waiver: write it in `mech/waivers.toml` (`[[waiver]]` with `id` = the row id or a glob, `reason`, `who`, `date`; all four required, see `templates/waivers.example.toml`), and `check_all.py` then prints that row as "waived" with its reason and counts it apart. Nothing is waived by default, and a STALE row is never waived: run the check again first. Everything else still open becomes a named risk at the gate, each with a zoomed picture and one line on what could happen.
8. **Do not send the supplier a question list.** Where a rule is unclear, design to the conservative side and say nothing; their review speaks. The one exception is a single question on something their pages cannot answer, drafted, shown to the user, and sent before the quote.
9. **Estimate the cost** for the gate: the instant quote where it needs no sign-in, the cable estimate where the form shows one, shipping and duties as a range from `references/suppliers/shipping-and-combine.md`. Name each number's source and date. Orders of magnitude: on small orders shipping and duties can match the parts price, and express shipping of a light parcel can cost more than the cables in it.
10. **Gate 2.** Send `GATE2_SUMMARY.md`: conclusion and the one action first; then renders, the drawing list, the ink sheet, the cable drawings, the cost estimate, the evidence status (what was checked, what could not run, which gates were skipped), the open risks with pictures, and the exact folders. The approval comes after the rules check so that nothing changes afterwards. The user approves the frozen design in writing.

## Questions for the user

- Do you approve this design for ordering? (summary with pictures and cost)
  - Suggested: yes.
  - Why: the four reviews are closed; the open risks are `<n>`, each shown.
- Finding `<id>` cannot be fixed without `<cost>` (zoomed picture). Fix, or accept as a risk?
  - Suggested: `<fix | accept>`.
  - Why: `<what happens in the worst case, and what the fix costs in days>`.
- A check could not run (`<which>`, `<why>`). Go on without it?
  - Suggested: no for a supplier-rules check; yes for `<a named minor one>`.
  - Why: a check that cannot run is not a pass; you decide knowing that.

## Gate 2 checklist

- [ ] The candidate was frozen and hashed before the reviews. Evidence: `reviews/frozen/order-r1/`, the checksums.
- [ ] The supplier-rules reviewer read the live pages that day and measured the exported files with its own code. Evidence: its report: page list with date, the measured rows.
- [ ] The catalogue review found no non-catalogue word, or each is removed. Evidence: its report, a clean `catalogue_scan.py`.
- [ ] Each cable drawing was compared with the data file and the pin-out, position by position. Evidence: the cable review report.
- [ ] The picture-only review opened every page, the ink sheet, the dark-viewer picture and the renders. Evidence: its image list with crops.
- [ ] One fix round, each fix re-checked by its reviewer; the build is current after it. Evidence: the re-check sections, the `build.py` output.
- [ ] Headline of `out/CHECKS.md`: passed, failed, could not run, not applicable, each counted apart; no failed row left without a waiver in `waivers.toml` (the headline's "waived N"). Evidence: the file.
- [ ] The capability sheets carry today's (or this week's) read date. Evidence: `[meta] read_date`.
- [ ] The user approved the frozen design. Evidence: their words and the date.

## Outputs

- `mech/reviews/`: four (or five) reports with picture crops, the frozen copies
- `mech/GATE2_SUMMARY.md`; waivers in `PROJECT_STATE.md`
- The frozen candidate: the upload folders that phase 11 will hash and archive

## If something is missing

- Review only (nothing to change): stop after step 5; hand the reports to the user; fixing is theirs.
- No way to read the live pages: the supplier-rules review is "could not run"; say at the gate that the rules are as read on the sheet's date, and let the user decide.
- Cables only or case only: run the reviews that apply (cables: 2, 3 and 4; case: 1, 2 and 4).

## Lessons behind this phase

- The builder's own checks passed; the independent check on the exported files found several failures -> step 2, review 1.
- All three supplier questions of one order were on the project's own open list and went out anyway -> step 2, review 2, and the catalogue scan.
- A reviewer was handed the designer's conclusions and repeated them -> step 2: the frozen files and the brief only.
- The user approved, then a rules fix changed the files -> step 10: the approval comes after the rules check.
- A question list sent to a supplier before an order cost days and answered little -> step 8.
- A check that could not run was counted as passed in a summary -> the gate checklist: four counts, apart.

The full cases are in `references/lessons.md`.
