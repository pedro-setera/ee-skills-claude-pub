# <board name>: closure of fix round <round>, review <prefix>

Written by the reviewer who raised the findings, never by the designer, and saved as `reviews/VERIFY_<round>_<prefix>.md`. Same model and effort rules as the review. This is the one re-check of the stage: it looks only at what was fixed, and it raises a new finding only if a fix caused it (`references/reviews.md` section 6).
Reviewer: <agent name>. Model and effort (set explicitly): <model, effort>. Date: <date>.
Findings: `reviews/<prefix>_<NAME>_FINDINGS.md`. Response: `reviews/RESPONSE_<round>.md`.
New frozen copy: `reviews/frozen/<sch | sim | pcb | files>-r<round>-<first 12 characters>/`, full SHA-256 <value>.

## Verdict
<The verdict words of this review, as in the findings file: NOT READY | READY WITH FIXES | READY, or REJECT | FIX AND RE-REVIEW | OK FOR PROTOTYPE, or DO NOT ORDER | ORDER WITH NOTES | ORDER.> Closure: <all closed | open items remain>. <One sentence.>

## Method
<Old versus new: netlist or board diff with the reviewer's own parser; re-runs of the intent check and ERC; simulations re-run with extended cases (file names); documents searched for every changed value.>

## Closure table
One row for every ID in the findings and every ID in the response.
| ID | Correct and complete? | New problem introduced? | Evidence | Status |
|---|---|---|---|---|
| <S2-MJ1> | <yes> | <no> | <diff line, re-run `sim/out/sim-01.png`> | <closed> |
| <S2-MN1> | <yes, justification accepted> | <no> | <datasheet p. 8> | <closed> |
| <S2-MJ2> | <partly: delay is 80 ms at the cold corner> | <yes: see S2-MN3> | <re-run file> | <open> |

Status values: closed, open, reopened.

## New findings caused by the fixes
Same format as the review. IDs continue the review's own numbering: the next free `<prefix>-B<n>`, `-MJ<n>`, `-MN<n>` or `-N<n>`. Only findings that a fix caused belong here. A new blocker is fixed and re-checked alone; the others go to the user at the gate as named risks. They do not start another round, except the second one of the full set.

### <S2-MN3>  <short title>
- **Severity:** <minor>
- **Where:** <...>
- **Evidence:** <...>
- **Consequence:** <...>
- **Proposed fix:** <...>

## Images looked at after the fix
| Image | Crop path | What I saw |
|---|---|---|
| <re-rendered top view> | <`reviews/crops/<prefix>/top_r<round>.png`> | <R4 silk label readable, no overlap> |

## Judgement of the checks themselves
- Intent check: <what it can and cannot find, mutation test seen>.
- Each simulation: <model, limit, did the limit stay unchanged since the plan?>.
- Checks that cannot run are FAIL: <list, none or items>.

## Coverage statement
- **Re-checked and correct:** <list>.
- **Not re-checked:** <list, with reason>.

## Result for the next step
| Item | Value |
|---|---|
| Open items | <n> |
| For each open item: the risk in one line, and the bench test (or check at order time) with its pass value | <ID: risk; BT-nn, pass value> |
| New blockers or majors | <n> |
| Free recommendations (no change needed) | <list> |
| Do my findings still block the gate? (the gate itself is decided from all reviews) | <yes / no> |
