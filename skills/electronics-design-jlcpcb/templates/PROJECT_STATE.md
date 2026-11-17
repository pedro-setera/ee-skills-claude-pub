# <board name>: project state

Read this file first in every session. Update it at every decision, every gate and every agent start or end.
A cold-start session must be able to continue from this file alone.

```yaml
board: <board name>
revision: <A>
way_of_use: <new design>          # new design | review only | review and fix | continue from the user's schematic |
                                  # continue from the user's board | order existing files | next revision | watch or bring-up only
source:                           # the rest only for a design brought by the user; their files are never modified
  origin: <made here | brought by the user>
  original_path: <path as the user gave it>
  tool_and_format: <Altium Designer, .PcbDoc>
  copied: <date>
  sha256: {<file>: <sha256>}      # of the originals, taken when copied
  import_verified: <yes | no | not an import>
phase: <0-15>                     # the phase now being worked
gate0: {passed: false, date: null}   # requirements page confirmed by the user (phase 1)
gate1: {passed: false, date: null}   # schematic approved by the user
gate2: {passed: false, date: null, release: null}   # PCB approved; release REJECT | PROTOTYPE ONLY (optionally "limited use: <who, where, how many>") | PRODUCTION APPROVED (references/reviews.md section 8)
gate3: {passed: false, date: null}   # the user paid
review_depth: <lean | lean + S1 SC | lean + L1 | lean + S2 | lean + L2 | full>   # decided by the agent from the facts (references/reviews.md section 9), again at every gate; up by itself, never down without the user's yes
depth_facts: <no radio, no converter, 12 V, 0.5 A, 5 boards, own use>   # each fact yes, no or unknown; unknown counts as yes; overruled by the user: <no | date, their words>
review_parallel: 2
skill_scripts: <full path of this skill's scripts folder>   # project scripts in src/ are called with --scripts <this path>
tools:
  kicad: <9.0.x>
  ngspice: <45>
  python: <3.12>
  browser_extension: <connected | missing>
frozen:                           # file: full sha256, written when a gate or a review freezes it
  schematic_netlist: <sha256>     # review copies: reviews/frozen/sch-r<round>-... and sim-r<round>-<first 12 of sha256>/
  board: <sha256>                 # review copy: reviews/frozen/pcb-r<round>-<first 12 of sha256>/
  upload_folder_zip: <sha256>     # production files brought with no board: reviews/frozen/files-r<round>-<first 12 of sha256>/
orders:                           # references live ONLY in this project file
  - {supplier: JLCPCB, ref: <order no.>, status: <status>, placed: <date>}
```

## Next action
<One line: the single next thing to do, who does it, and which file to open.>

## Decisions
| Date | Decision | The user's words |
|---|---|---|
| <2026-01-05> | <USB-C power only, no battery option> | "<quote, as said>" |

## Open questions for the user
- [ ] <Question, one line.> Suggested: <answer>. Why: <reason>. Asked on <date>.

## Waivers
| ID | What is waived | Reason | The user's words, date |
|---|---|---|---|
| <W-1> | <12 passive parts without silk label> | <no room, shown on the assembly drawing> | "<quote>", <date> |

A FAIL or UNKNOWN is never waived by the agent. Only the user waives it, in writing, here.

## Gates skipped by the user
A skipped gate's checks stay UNKNOWN, and every later summary says "gate N not evidenced".
| Gate | Date | The user's words |
|---|---|---|
| <gate 1: schematic reviews> | <date> | "<quote>" |

## Agents running
| Agent | Task | Model and effort (set explicitly) | Progress file | Started |
|---|---|---|---|---|
| <LC> | <lean circuit review> | <most capable model, highest effort> | `reviews/<prefix>_PROGRESS.md` | <date time> |

At most `review_parallel` reviewers at once. After every agent report, list the running agents and refill at once.
An agent without a progress file is not allowed to start.

## Log
Newest first. One line per event: date, phase, what happened, file touched.
- <2026-01-05> <phase 5> <schematic sheet 2 written, ERC 0> `kicad/<board>.kicad_sch`
