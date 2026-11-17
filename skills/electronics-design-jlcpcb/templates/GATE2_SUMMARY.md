# <board name>: gate 2 summary (PCB)

**Status: <READY FOR YOUR APPROVAL | NOT READY: <reason>>.** Release state: **<REJECT | PROTOTYPE ONLY>**.
Action needed from you: <approve the PCB, or decide waiver W-1>.

Reviewed board: `kicad/<board>.kicad_pcb`, sha256 <value>, frozen as `reviews/frozen/pcb-r<round>-<first 12 characters>/`. The same checksum is in the interface file, the production zip and PROJECT_STATE. If they differ, this page is void.

Release states (the one table: `references/reviews.md` section 8): REJECT = do not order. PROTOTYPE ONLY = your permission to order a few samples for testing, not for sale or volume. PRODUCTION APPROVED is never given at this gate: it needs measurements on real boards, then your signature. Your approval is permission, not proof: what is UNKNOWN stays UNKNOWN until it is measured. The release state is decided on this page from all reviews; no single reviewer states it.

Write this page in plain words for a user who may not be an electronics engineer (`references/working-rules.md` section 1): everyday words, what each point means for the device and its cost rather than the name of the technique, any technical word explained in a few words the first time.

## Evidence status
- Evidenced: <gate 1 on <date>; the lean board review LB and the picture-only review V1, one fix round, each re-checked once | plus L1, switched on by: a 2.4 GHz radio | ...>. Depth: <lean | ...>; facts: <...>.
- Skipped by the user: <none | gate 1, <date>: "<the user's words>">.
- Not checked: <nothing | the circuit: no schematic review ("gate 1 not evidenced") | "import not verified">.

## What the board looks like
<Two lines: size, layers, sides, connectors.> Pictures: top `<out/review/top.png>`, bottom `<out/review/bottom.png>`, 3D `<out/review/angle.png>`.

## Check results
| Check | Result | File |
|---|---|---|
| <DRC with schematic parity> | <0 errors, 0 unconnected> | <`out/drc_summary.txt`> |
| <Intent check on the exported netlist> | <PASS> | <file> |
| <Silkscreen, edge, copper necks, 3D bodies> | <PASS all> | <`out/CHECKS.md`> |
| <Rotations derived and re-derived> | <PASS> | <`out/jlc/rotations.md`> |
| <Stock on <date>, all lines> | <PASS> | <`out/BOM_STOCK_CHECK.md`> |

## Your requirements, one by one
The same list as at gate 1 (`REQUIREMENTS.md`, section 14), now against the board: size and fit, connectors, heat, currents, anything the layout decides. A requirement that only a real board can show says so and names its bench test.
| ID | Requirement | Met by | Verified by | Status |
|---|---|---|---|---|
| <REQ-03> | <fits the case: 40 x 30 mm, parts at most 8 mm high> | <outline, tallest part C4 at 6.5 mm> | <`out/body_check.md`; section view; review L3> | <met> |
| <REQ-01> | <temperature within +/-0.5 C> | <as at gate 1; sensor at the cool edge> | <heat table recomputed; BT-05> | <met on paper; measured at bring-up> |

## Will it work? Evidence line by line
A board that is fully routed and passes the rule check is connected and can be made. Whether it works well is shown here, one line per question. A line with no evidence says UNKNOWN and names the bench test; it is never left out and never written as a pass.
| Question | Evidence | Result |
|---|---|---|
| Do the fast and sensitive signals arrive clean? | <unbroken ground under each one: `out/return_path.md` and the overlay images; line impedance of each controlled line from the board's own widths and layers: `out/impedance_check.md` beside the manufacturer's calculator record; pair lengths and gaps: `out/drc_summary.txt`; stubs listed> | <PASS / FAIL / UNKNOWN, BT-nn / no such signals on this board> |
| Does the radio part do what it was designed for? | <line widths and gaps for this layer stack; matching network positions; antenna keep-out against the antenna maker's drawing; the cascade estimate SIM-nn> | <designed by the rules; NOT measured: BT-nn (network analyser, range or sensitivity test) / no radio on this board> |
| Do the currents have enough copper, there and back? | <`out/current_worksheet.md`: narrowest copper, vias and contacts per power path and its return, at the peak the protection lets through> | <PASS> |
| Do the supplies stay steady? | <decoupling against each maker's guide: the table in the ledger; rail table of the design note; simulation SIM-nn> | <PASS / UNKNOWN, BT-nn> |
| Does anything overheat? | <heat table of the design note, recomputed with the copper and vias on the board; the cooling as decided (copper only, heat sink <part>, fan <size>) and what happens with the fan stopped> | <hottest part <x> C with <y> C air at the part, against <z> C less the margin of THM-04 / UNKNOWN, BT-nn> |
| Is the protection where the faults enter? | <each clamp, fuse and filter at its connector, its return path short: ledger rows of `protection-esd.md`, crops> | <PASS> |
| Can it be programmed, tested and serviced? | <`out/testpoint_check.md`, `out/testpoints.md`; the debug connector reachable with the board mounted; the bring-up image ready, or its owner and date> | <PASS, <n> points> |
| Does it stay quiet and is it left undisturbed? | <noise table and zone map followed: ledger, the board review> | <designed by the rules; NOT measured: BT-nn or a test house if the product needs approval> |
| Can it be made and assembled as drawn? | <the manufacturer's rules measured on the exported files: `out/CHECKS.md`; supplier-rules review SR; the process limits of the parts where they matter, against the assembler (phase 12 step 3b)> | <PASS> |

## Rules ledger
PASS <n>, FAIL <n>, UNKNOWN <n>, WAIVED <n>. Gate 2 needs FAIL 0 and no UNKNOWN on a blocker-level item; every other UNKNOWN is listed under Open items with its bench test. File: `LAYOUT_RULES_LEDGER.md`.

## Reviews: what each found and how it was fixed
| Review | Counts (blocker / major / minor / note) | Fixed how | Status |
|---|---|---|---|
| <LB lean board review> | <0 / 2 / 5 / 3> | <rotation of Q1 re-derived, wider neck on the 5 V path> | <re-checked once: 9 closed, 1 open as a named risk> |
| <V1 picture-only review> | <0 / 1 / 4 / 2> | <labels moved, one text off a via> | <re-checked once: all closed> |
| <L1 layout electrical, switched on by: a 2.4 GHz radio> | <0 / 1 / 2 / 1> | <ground vias beside the antenna feed> | <re-checked once: all closed> |

Scoped re-reviews on the named checksum: <review, date, result>.

## Waivers (your decisions)
| ID | What | Why | Your words |
|---|---|---|---|
| <W-1> | <6 parts have no silk label> | <no room> | "<quote>" |

## Cost
| Item | Amount |
|---|---|
| Parts, assembly, PCB, shipping, tax (landed estimate) | <x> |
| Change since gate 1 | <+/- x> |

Against your target of <z> per board (`references/working-rules.md` section 11, quality first, then cost): <x> now at <5> boards, <y> at <100>.
| Biggest cost driver | Per board | A cheaper way to the same quality |
|---|---|---|
| <U2 regulator, extended line> | <0.40 plus the fee> | <found: a basic part with the same accuracy and dropout, taken; or none found> |
Kept as an unfitted footprint because its need is uncertain: <snubber C30>. <Quality and the target cannot both be met: your options, a higher cost, fewer features or a named limitation | none>.

## Open items
Only an UNKNOWN on a blocker-level item blocks this gate. Every other UNKNOWN, from the ledger, the checks and the reviews, is listed here with the bench test that will settle it; your approval of the gate accepts this list.
| Item | Plan |
|---|---|
| <Open after the re-check: LB-MJ1> | <what is known and not known; bench test BT-04 with its pass value, or the check at order time> |
| <Item> | <bench test BT-04 / next revision> |

## Questions for you (at most three; the rest of this page is accepted with the gate)
<Question>
Suggested: <answer>
Why: <reason>
