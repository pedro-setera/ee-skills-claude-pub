# <board name>: response to fix round <round>

Written by the designer after the reviews of a stage: one combined response per fix round, saved as `reviews/RESPONSE_<round>.md`. Rounds are numbered over the whole project (1, 2, 3 ...). One row for every finding ID, none skipped.
Findings files answered: `reviews/<prefix>_<NAME>_FINDINGS.md` of each review in this round (for example `S1_DATASHEET_FINDINGS.md`, `S2_SYSTEM_FINDINGS.md`). Date: <date>.
Design checksum after the fixes: <full SHA-256>. New frozen copy: `reviews/frozen/<sch | sim | pcb | files>-r<round>-<first 12 characters>/`.

## Rules
- blockers and majors: fix, or deviate with evidence (a calculation, a simulation, a datasheet page). Never "will not do" without a reason.
- minors: fix, or justify in one line.
- notes: read and say what was decided.
- A deviation from the reviewer's proposed fix is allowed if the problem is solved. Say what was done instead.
- Changes beyond the review are listed at the bottom.

## Response by finding
| ID | Severity | Decision (fixed / deviated / justified / noted) | What I did | Where |
|---|---|---|---|---|
| <S1-MJ1> | <major> | <fixed> | <R4 changed 10 k to 4.7 k, set-point recalculated> | <`kicad` sheet 2; DESIGN_NOTE 7> |
| <S1-MN1> | <minor> | <justified> | <the 1 mA leakage is below the 50 mA load, no effect> | <DESIGN_NOTE 7> |
| <S2-MJ1> | <major> | <deviated> | <added a 100 ms delay instead of the proposed second regulator; simulation SIM-06 shows margin 2x> | <SIM-06 results> |

## Fix round checklist
Tick each step, with the file or command.
- [ ] Design source edited: <file>.
- [ ] Generator re-run: ERC <0>, netlist exported, intent check <PASS>, BOM updated, stock re-checked <date>.
- [ ] Affected simulations re-run, and new tests added for every scenario the reviewer said was missing: <IDs>.
- [ ] Documents corrected: every changed value searched in all files (DESIGN_NOTE, REFERENCE_CHECK, ledger, summaries).
- [ ] Images re-rendered and looked at: <paths>.
- [ ] New checksum written to PROJECT_STATE; files frozen again as `<sch | sim | pcb | files>-r<round>-<first 12 characters>`.

## Changes beyond the review
| Change | Why | Checked how |
|---|---|---|
| <Added test point on the 3.3 V rail> | <bench test BT-01 needs it> | <netlist diff, ERC> |

## Questions for the user raised by the fixes
- [ ] <Question.> Suggested: <answer>. Why: <reason>.

## Next step
Send each finding back to the reviewer who raised it, with the same brief and a closure scope. Each finder re-checks its own findings once in `reviews/VERIFY_<round>_<prefix>.md`, looking only at what was fixed. This is the one fix round of the stage (a second only where the full set runs): a blocker still open is fixed and re-checked alone until it is closed or the user accepts it in writing; everything else still open goes to the user at the gate as a named risk with its bench test (`references/reviews.md` section 6).
