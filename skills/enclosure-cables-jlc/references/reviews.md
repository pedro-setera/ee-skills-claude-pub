# Reviews: the system

How reviews are chosen, launched, read and closed in this skill. The ready briefs are in `review-briefs/`. The phase
files (5, 7, 10, 13, 14) say when; this file says how.

## 1. Why reviews exist

- The designer never reviews its own work (SKILL.md rule 7). Designers' checks look at what the designer meant.
  On one order the builder's checks all passed and an independent measure of the exported files found several
  failures.
- Scripts add to looking and never replace it (rule 6). Reviews "by scripts and imagination" passed a connector
  over a screw hole and wrong details in renders; the user found the same fault twice.
- A reviewer is a fresh agent with the frozen files and the brief, and no conclusions.

## 2. The lean set (default) and the raised set

| Stage | Lean set | Raised set | Briefs |
|---|---|---|---|
| Cable routes (phase 5) | 1: the second measurement, written before the first numbers are seen | the same | `route-second-measure.md` |
| Before the print (phase 7) | 2 side by side: the model review; one picture-only review | plus a second model review | `model.md`, `visual.md` |
| Before the order (phase 10) | 4: supplier rules on the exported files; catalogue and drawings read as the supplier's engineer; cable drawings against data and pin-out; one picture-only review | plus a second picture-only review | `supplier-rules.md`, `catalogue-and-drawings.md`, `cable-drawings.md`, `visual.md` |
| Supplier's production drawings (phase 13) | 1: field by field before any Confirm | the same | `production-drawing.md` |
| Arrival plan (phase 14) | 1, offered | 1, run | `arrival-plan.md` |

A project that has no cables drops the cable reviews; a cables-only project drops the model and supplier-rules
reviews of the case. Nothing else is dropped without the user's written waiver.

## 3. Facts that raise the set

One is enough. Unknown counts as yes. Write the facts and the chosen depth in the state file in phase 1.

- for sale, or more than 50 units;
- mains voltage or a lithium battery inside;
- a radio that must be shielded, or must pass through the box (a radio inside whose antenna is outside on a coax,
  with no shielding requirement, is NOT this fact);
- more than about 15 W of heat;
- a sealed or splash-proof box (outside the proven range of this skill: say so to the user as well);
- a batch the user calls costly.

Lean is the default because one model review, one picture-only review and the supplier-rules check found
everything that mattered on the first real box, and the end rule keeps the time bounded.

## 4. Launching a review

1. **Freeze first.** Run `build.py` and `check_all.py`, then `freeze.py --project <mech> --name <name> --profile
   review|visual|order` (`print-r1`, `routes-r1`, `order-r1`, `pd-r<round>`, `arrival-r1`; the picture-only reviewer
   gets a `<name>_visual` set made with `--profile visual`; add what a brief lists beyond the profile with
   `--include`); it refuses a stale build or check row; paste the lines it prints into the state file. A review of files that change underneath it proves
   nothing. Leave the design alone while reviews run.
2. **Fill the brief's slots** with absolute paths and send the brief as the whole prompt. Pass files, never
   conclusions. No reviewer sees another's report.
3. **Set the most capable model and the highest effort explicitly** in the agent call (rule 0), write both in the
   state file, and read them back from the reviewer's report header. A reviewer on default settings is stopped and
   relaunched. When the most capable model cannot be used (a budget rule, a pause), the review may run on a smaller
   model only with the user's OK: write it in the report header and the state file, and the release state stays at
   CONCEPT PRINT until the review is repeated on the most capable model.
   Plan about 15 to 40 minutes of wall time per review; the second measure and the supplier-rules review take longest.
4. **At most 2 reviewers at a time** unless the state file says otherwise. Start the next as soon as one reports.
5. **One agent on a supplier's site at a time** (the supplier-rules reviewer). Human pace.
6. Each reviewer keeps a progress file (`reviews/<ID>_PROGRESS.md`: done, in work, left). A reviewer whose progress
   file has not moved is checked, then stopped and relaunched. No stale or forgotten agents.

## 5. Reading a report

Accept a report only when it has:

- the header: review type, model and effort, date, the frozen folder and checksums;
- the verdict in the brief's words;
- counts of passed, failed, could not run and not applicable, apart;
- its check table with a proof per row;
- **the list of images it opened, with what was seen and crop paths.** A report that lists no opened image is sent
  back;
- findings in the format below.

A check that could not run is never a pass (rule 8). "Could not run" on a blocker-level item is itself a blocker
until it runs or the user accepts it in writing.

## 6. Finding format and severities

```
### <ID>-<letters><number>  <one-line title>
- Severity: blocker | major | minor | note
- Where: part, feature, file, page, row
- Evidence: the command and its output, or the crop path and what it shows
- Consequence: what happens at the print, the supplier, the assembly or the customer
- Which side must change: the box, the board, the cable, the documents, the print settings
- Proposed fix: concrete, with a number or the exact words
```

IDs: the review's letters (M, V, R2, SR, CD, WD, PD, AP; with a number where a review runs twice: M1, V2), then
B, MJ, MN or N and a running number. IDs are never reused. Skeleton: `templates/REVIEW_FINDINGS.md`, saved as
`reviews/REVIEW_FINDINGS_<stage>_<review>.md`: its findings table gets one line per ID, the blocks give the detail.

| Severity | Meaning | At the gate |
|---|---|---|
| blocker | A part cannot be made, printed or assembled; something breaks, burns or is unsafe; a supplier question or a refused file is certain; a wrong cable would be built | Closed, or accepted by the user in writing |
| major | Works only by luck or unplanned hand-work; a supplier question is likely; a customer would see a defect | Fixed, or a named risk with a zoomed picture |
| minor | A rule missed with margin left; unclear, crowded, uneven | Fixed when cheap, else listed |
| note | Cosmetic, or advice | Listed |

## 7. The end rule

One review, one fix round, one re-check by the same reviewer, which looks only at what was fixed.

1. Collect all findings of the stage. Merge duplicates by union; keep every ID.
2. Fix in the sources (model, artwork, `cables.json`, `mech.toml`, remark), never in an exported file. Run
   `build.py`, `check_all.py`, `catalogue_scan.py`. Freeze again as `<name>` with the next round number.
3. Give each reviewer only its own fixed findings and the new frozen files. It answers per ID: "fixed and
   complete?" and "new problem introduced?" in the re-check section of its own findings file.
4. **No further round.** A blocker is closed or accepted by the user in writing. Everything else still open goes to
   the user at the gate as a named risk with a zoomed picture and one line on what could happen.
5. If the fix round changed geometry that another reviewer had passed, say so at the gate; do not start a new
   review cycle unless the user asks for one.

## 8. Release states

State the release state at every gate, from all reviews together. A single review's verdict is about that review.

| State | Means | Needs |
|---|---|---|
| **CONCEPT PRINT** | The print files may be printed as a throw-away concept | Gate 1: the model and picture-only reviews closed by the end rule; the coupon exists; the user's approval of the print files |
| **SAMPLES ONLY** | Metal parts and cables may be ordered as first samples (a few sets, not for sale) | The printed concept has fitted (or the user waived the print in writing); gate 2: the phase 10 reviews closed by the end rule; every waiver written; gate 3 paid by the user |
| **PRODUCTION APPROVED** | The same revision may be ordered again as a batch | **The arrival fit**: the samples of this revision were measured, assembled and tested (phase 14: every fit row "fits", ground continuity, the heat run, the radio test where there is one), and every "does not" was fixed in a new revision that was itself checked. Never from drawings alone |

Sections of this skill marked PROVISIONAL or "not proven by an order" cap a project at SAMPLES ONLY until the
project's own samples have proven them. Say so at the gate.

A supplier-rules review that could not read the live pages (no browser, no network) ends "OK AGAINST THE SEED, LIVE
READ STILL OPEN": never OK TO QUOTE. The order plan then carries the live read as a blocker before the first quote.

Every gate summary carries an evidence status: what was checked, what could not run, which gates were skipped and
by whose words, which review set ran.

## 9. Waivers

Only the user waives, in writing, for one named finding or one named gate, with the reason. The agent records the
words and the date in the state file. A reviewer never waives. A waived print (metal ordered without a printed
concept) is written in the state file and repeated on the gate 2 summary.

## 10. Without sub-agents

When the session cannot start agents: one fresh session per review, one after the other, each started with only the
brief and the frozen folder, and say so in the gate summary ("reviews run as separate sessions, not as parallel
agents"). If even that is not possible, the designer runs the brief's method itself, labels the result
"self-review, not independent", and the release state cannot go beyond CONCEPT PRINT without the user's written
acceptance of that limit. The second route measurement is the one review that loses all value when done by the
same session: then the user is told, and the compare is replaced by a larger allowance that the user approves.

## 11. What reviews never do

Change a file; send anything to a supplier; sign in; install or download (except saving public rule pages); see
each other's reports; see the designer's conclusions; waive.
