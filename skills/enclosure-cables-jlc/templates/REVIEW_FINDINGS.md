# Review findings: <stage>, <which review>

Save as `reviews/REVIEW_FINDINGS_<stage>_<review>.md`. Written by the reviewer, a fresh agent that did not design the part. The brief is in `references/review-briefs/`.

- Reviewer: <agent label>. Model and effort (set explicitly): <most capable model, highest effort>.
- Stage: <before the print | before the order | production drawings | arrival plan>. Brief: `<file>`.
- Frozen files reviewed: `reviews/frozen/<folder>/`, checksums: <first 12 characters of each sha256>.
- Date: <>. Supplier pages read today (supplier-rules review only): <titles, dates>.

## Headline
Blockers <n>, major <n>, minor <n>, notes <n>. Checks: passed <n>, failed <n>, could not run <n>, not applicable <n>.

## Images opened, and what was seen
A report with no opened image is not accepted.
| Image | What I looked at | What I saw | Crop |
|---|---|---|---|
| `out/views/front.png` | <each hole, connector, label> | <jack hole 2 sits 1 mm from the lid screw boss> | `reviews/crops/<file>.png` |
| `out/drawings/pages/<part>-p2.png` | <every dimension table> | <> | |
| `out/silk/<part>_factory_view.png` | <every colour on the dark background> | <only the n ink colours> | |

## Findings
| ID | Severity | Where (file, page, feature) | Finding | Evidence (number, rule, picture) | Suggested fix |
|---|---|---|---|---|---|
| <F-01> | <blocker> | <tray.step, rear wall> | <hole 0.8 mm closer to the bend than the supplier's minimum> | <measured 3.7, rule 4.5; crop> | <move the hole or lengthen the flange> |

Severity: **blocker** = the order or print must not go; **major** = likely a question, a failure or a redo; **minor** = worth fixing in the fix round; **note** = for the next revision.

## Could not check
| What | Why | What would make it checkable |
|---|---|---|
| <> | <> | <> |

## Re-check after the fix round (the same reviewer, only what was fixed)
| ID | Fix seen in (new file, checksum) | Result | Still open: goes to the gate as |
|---|---|---|---|
| <F-01> | <> | <closed> | |
| <F-04> | <> | <not closed> | <a named risk with a zoomed picture> |

No further round after this one.
