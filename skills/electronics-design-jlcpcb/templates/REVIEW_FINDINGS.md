# <board name>: review <prefix>, <review type>

Review type: <LC lean circuit | LB lean board | S1 schematic datasheet | S2 schematic system | S3 schematic fresh eyes | SC simulation coverage | L1 layout electrical | L2 layout manufacturing | L3 layout mechanical | V1 or V2 visual | SR supplier rules | BU bring-up plan>.
File: `reviews/<prefix>_<NAME>_FINDINGS.md`, for example `LC_CIRCUIT_FINDINGS.md`. Progress file: `reviews/<prefix>_PROGRESS.md`. Crops: `reviews/crops/<prefix>/`.
Reviewer: <agent name>. Model and effort (set explicitly): <model, effort>. Date: <date>.
Reviewed copy: `reviews/frozen/<sch | sim | pcb | files>-r<round>-<first 12 characters>/` (`<round>`: the last completed fix round, 0 when none), full SHA-256 of the netlist, board file or Gerber zip: <value>. The reviewer never wrote in the design folder.

## Verdict
<The verdict words of this review.> <One sentence why.>

Words by review: LC, S1, S2, S3, SC and BU say NOT READY, READY WITH FIXES or READY. LB, L1, L2, L3, V1 and V2 say REJECT, FIX AND RE-REVIEW or OK FOR PROTOTYPE. SR says DO NOT ORDER, ORDER WITH NOTES or ORDER. A reviewer does not state the board's release state: the gate summary decides it from all reviews.

## Summary counts
| Severity | Count |
|---|---|
| blocker | <n> |
| major | <n> |
| minor | <n> |
| note | <n> |

Severity: blocker = board unsafe, dead or unbuildable. major = function or reliability at risk. minor = small risk or inconsistency. note = advice, no action needed.

## Method
<What the reviewer did: own parser, own scripts, recalculations, scenarios walked, simulations re-run (file names), datasheets and references downloaded.>

## Findings
One block per finding. ID: `<prefix>-B<n>` blocker, `<prefix>-MJ<n>` major, `<prefix>-MN<n>` minor, `<prefix>-N<n>` note, numbered per severity; stable for the life of the project.

### <S1-MJ1>  <short title>
- **Severity:** <major>
- **Where:** <sheet, part, net, page, board coordinates, file and line>
- **Evidence:** <datasheet page or table, calculation with tolerances, re-run file, or image crop path>
- **Consequence:** <what happens on the bench or in the field>
- **Proposed fix:** <change, with in-stock part numbers and their class if a part changes>

### <S1-MN1>  <short title>
- **Severity:** <minor>
- **Where:** <...>
- **Evidence:** <...>
- **Consequence:** <...>
- **Proposed fix:** <...>

## Images looked at
Every review opens the images. Say what you saw, not that you looked.
| Image | Crop path | What I saw |
|---|---|---|
| <top render> | <`reviews/crops/<prefix>/top.png`> | <connector J1 clear of the screw, silk readable> |
| <zoom: hole H1> | <`reviews/crops/<prefix>/h1.png`> | <plug body 0.6 mm from the screw head: see <prefix>-MJ2> |

## Coverage statement
- **Checked and found correct:** <list: every chip pin by pin, every set-point, every scenario>.
- **Not checked:** <list, with the reason>.
- **Not covered by any simulation (goes to the bench list):** <list>.

## Edge cases walked
| Scenario | Result | Finding ID |
|---|---|---|
| <Plug-in with the load on> | <ok> | |
| <Source drops out for 20 ms> | <resets once> | <S2-MJ1> |

## Questions the coordinator asked
| Question | Answer |
|---|---|
| <(a) ...> | <...> |
