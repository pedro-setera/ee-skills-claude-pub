# <device name>: mechanical project state

Read this file first in every session. Update it at every decision, every gate and every agent start or end.
A cold-start session must be able to continue from this file alone.

```yaml
device: <device name>
revision: <A>
way_of_use: <box and cables from nothing>   # box and cables from nothing | cables only | printed box only | metal version of an
                                            # existing box | review only | order finished files | watch an order | arrival check
parts_in_scope: <A enclosure, B cables>
process_path: <printed concept, then folded sheet metal>   # standard case with cut panels | printed box only |
                                            # printed concept then sheet metal | CNC (not proven by an order)
phase: <0-16>                               # the phase now being worked
entry_phase: <1>                            # and why: <one line>
source:                                     # only for files brought by the user; their files are never modified
  origin: <made here | brought by the user>
  copied: <date>
  sha256: {<file>: <sha256>}
gate0: {passed: false, date: null}          # layout picture approved by the user (phase 2)
gate1: {passed: false, date: null}          # print files approved by the user (phase 7)
print_fitted: {done: false, date: null, waived: null}   # the printed box has fitted, or the user's waiver in writing
gate2: {passed: false, date: null}          # frozen design approved by the user (phase 10)
gate3: {}                                   # per order: {<order label>: {paid: false, date: null}}
review_depth: <lean | raised>               # decided from the facts, again at every gate; up by itself, never down without the user's yes
depth_facts: <not for sale, 2 units, no mains, no battery, no radio, 8 W, batch not costly>   # each yes, no or unknown; unknown counts as yes
review_parallel: 2
skill_scripts: <full path of this skill's scripts folder>
printer_profile: <full path, in the user's home, outside the skill | none>
tools:
  cadquery: <2.x | missing>
  slicer: <name and path | missing>
  blender: <version | missing>
  chrome: <found | missing>
  browser_extension: <connected | missing>
capability_sheets:                          # supplier id: read date
  <jlccnc-sheet-metal>: <YYYY-MM-DD>
  <lcsc-cable>: <YYYY-MM-DD>
frozen:                                     # file: full sha256, written when a gate or a review freezes it
  <reviews/frozen/<set>.MANIFEST.sha256>: <sha256>      # the lines freeze.py prints, pasted as they are
  <out/upload/<supplier>/<file>>: <sha256>
standing_ok:                                # per order, the user's words and the date; nothing is assumed
  <order label>: {messages: <no | "quote", date>, nudges: <no | "quote", date>}
orders:                                     # references live ONLY in this project file and in orders/ORDER_LOG.md
  - {supplier: <name>, label: <cables>, ref: <order no.>, status: <status>, next_step: <what>, deadline_local: <date time>}
```

## Next action
<One line: the single next thing to do, who does it, and which file to open.>

## What exists
| Item | Path | State |
|---|---|---|
| Board interface file | `<path>` | <checksums verify | stale | none> |
| Model | `model/build_model.py` | <builds | none> |
| Printed parts | <which> | <fitted | findings open | none> |
| Cable data | `cables/cables.json` | <lengths final | draft | none> |
| Drawings, upload folders | `out/upload/` | <frozen rev A | none> |
| Quotes and orders | `orders/ORDER_LOG.md` | <none> |

## Decisions
| Date | Decision | The user's words |
|---|---|---|
| <2026-01-05> | <arrangement B> | "<quote, as said>" |

## Open questions for the user
- [ ] <Question, one line.> Suggested: <answer>. Why: <reason>. Asked on <date>.

## Waivers and named risks
| ID | What is waived or open | Reason | Picture | The user's words, date |
|---|---|---|---|---|
| <W-1> | <vent group 2 mm off centre> | <clears a screw boss> | `<crop path>` | "<quote>", <date> |

A failed or could-not-run check is never waived by the agent. Only the user waives it, in writing, here.

## Gates skipped by the user
A skipped gate's checks stay not evidenced, and every later summary says so.
| Gate | Date | The user's words |
|---|---|---|
| <the print before metal> | <date> | "<quote>" |

## Agents running
| Agent | Task | Model and effort (set explicitly) | Started |
|---|---|---|---|
| <R1> | <picture-only review, before the print> | <most capable model, highest effort> | <date time> |

At most `review_parallel` reviewers at once. After every agent report, list the running agents.

## Log
Newest first. One line per event: date, phase, what happened, file touched.
- <2026-01-05> <phase 3> <model builds, 9 views looked at> `out/views/`
