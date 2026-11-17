# <board name>: gate 1 summary (schematic)

**Status: <READY FOR YOUR APPROVAL | NOT READY: <reason>>.** Action needed from you: <approve the schematic, the parts cost and the running time, or answer question 1>.

Write this page in plain words for a user who may not be an electronics engineer (`references/working-rules.md` section 1): everyday words, what each point means for the device and its cost rather than the name of the technique, any technical word explained in a few words the first time. Show the schematic PDF and one picture of the power tree.

## Evidence status
- Evidenced: <the lean circuit review LC, one fix round, re-checked once | plus S1 and SC, switched on by: a switching converter | ...>. Depth: <lean | ...>; facts: <...>.
- Skipped by the user: <none | what, <date>: "<the user's words>">.
- Not checked: <nothing | simulations: none exist, their points are UNKNOWN | "import not verified">.

## What the board does
<Three to five lines.>

Pictures: `<out/<board>-schematic.pdf>`, `<out/power_tree.png>`.

## Check results
| Check | Result | File |
|---|---|---|
| <ERC> | <0 errors, 0 warnings> | <`out/erc_report.json`> |
| <Netlist against hand-written intent> | <PASS, mutation test 3 of 3> | <`out/connectivity_report.md`> |
| <Every part in assembly stock for <5> boards plus spares> | <PASS, <date>> | <`out/BOM_STOCK_CHECK.md`> |
| <Symbol, footprint, BOM pin mapping> | <PASS> | <file> |
| <Pins and ratings against the hand-typed datasheet tables> | <PASS, <n> parts, 0 pins without a rating> | <`out/ratings_check.md`> |
| <Pins, clocks and peripherals (programmable part only)> | <the maker's configuration tool accepts them without a conflict / a minimal initialisation compiles; accepted by <owner> on <date>, where there is an owner / UNKNOWN: no tool file or build yet / not applicable: no programmable part> | <the tool file or the build report> |

## Your requirements, one by one
Every numbered requirement of the device description you confirmed (`REQUIREMENTS.md`, section 14). At this gate the proof is on paper: a calculation, a simulation, a datasheet page. "Met" without a named proof is not written; such a line says UNKNOWN and names its bench test.
| ID | Requirement | Met by (block, parts) | Verified by | Status |
|---|---|---|---|---|
| <REQ-01> | <temperature within +/-0.5 C> | <sensor U3; regulator U2 kept 20 mm away> | <datasheet p. 5 accuracy table; heat table; BT-05 on the board> | <met on paper; measured at bring-up> |
| <REQ-02> | <survives a reversed supply> | <D1, F1> | <SIM-02; review S2> | <met> |

## Is the circuit right? Evidence line by line
A clean rule check shows that the drawing is consistent, not that the circuit is right. Each question below is answered in at least two independent ways (a script on the files, a calculation or simulation, a reviewer against the datasheet). A line with no direct evidence says UNKNOWN and names the bench test; it is never left out and never written as a pass.
| Question | By script or calculation | By an independent reviewer | Result |
|---|---|---|---|
| Is every pin of every part the pin the maker's datasheet says (symbol, footprint and the exact part number)? | <`out/ratings_check.md`: pin numbers and names of <n> parts against the hand-typed datasheet tables; `out/connectivity_report.md`> | <LC, pin by pin> | <PASS> |
| Does every pin stay inside its recommended range, and far from its absolute maximum, at the worst case and during switching on, off and plugging? | <`out/ratings_check.md`: worst-case voltage of each net against each pin on it; SIM-nn for the transients> | <LC> | <PASS / UNKNOWN, BT-nn> |
| Do the supplies come up and go down in the order and at the speed each chip requires? | <the sequence table of `REFERENCE_CHECK.md`; SIM-nn start-up and brown-out> | <LC> | <PASS / no chip on this board requires an order> |
| Does every set value hold with the tolerances of its parts, over temperature and supply range? | <set-point table (minimum, nominal, maximum); SIM-nn at the corners> | <LC> | <PASS> |
| Does every control input (enable, chip select, reset, gate) sit at a safe level while its driver is in reset, unpowered or being programmed, and can any powered part feed an unpowered one? | <`out/ratings_check.md`: 0 inputs that can float; the default-level table and the back-feed list of the design note> | <LC> | <PASS> |
| Is every fault of the protection table really covered? | <SIM-nn per fault, with the stress in the protecting part> | <LC> | <PASS / UNKNOWN, BT-nn> |
| Which blocks have no simulation and no worst-case calculation? | <list, each with the reason (calculated, maker's circuit, bench test)> | <LC> | <none / <n> listed under Open items> |

## Reviews: what each found and how it was fixed
| Review | Counts (blocker / major / minor / note) | Fixed how | Status |
|---|---|---|---|
| <LC lean circuit review> | <0 / 2 / 5 / 3> | <R3 value, TVS part changed> | <re-checked once: 9 closed, 1 open as a named risk> |
| <S1 datasheet review, switched on by: a switching converter> | <0 / 1 / 2 / 1> | <inductor rating> | <re-checked once: all closed> |

One fix round, one re-check (a second round only where the full set runs). The one change that mattered most: <one line in plain words>.

## Simulations
<n> tests, <n> pass, <n> deviations (listed below: those you are asked about, and those the designer ruled on). The simulations changed: <one line>.
Not covered, goes to the bench: <list>. Detail: `sim/RESULTS.md`.

## Power and running time
What the device draws, and how long it runs, calculated from the parts on this schematic (`DESIGN_NOTE.md`, power budget and energy budget). It is a forecast; the first boards are measured against it.
| Mode | Current | Share of the time | Where the figure comes from |
|---|---|---|---|
| <Measuring and sending> | <45 mA> | <1 %> | <radio datasheet p. 12; assumed: one reading every 10 minutes> |
| <Sleeping> | <18 uA> | <99 %> | <sum of the sleep currents of U1, U3, the regulator and the dividers> |

- Average, at the cell: <0.47 mA typical at room temperature; 0.9 mA with the datasheets' maximum figures at 40 C>. Peak: <120 mA for 2 ms>, against what the source can give: <500 mA>. The running time below uses the higher average, and <70 %> of the cell's rated capacity.
- Battery: <one lithium cell, 1200 mAh, <size>>. Running time: **about <n days> per charge**; you asked for <m days>. <Or: for the <m days> you asked for, the battery must hold at least <c mAh>: chosen <...>.> Charging takes about <h hours> from <USB-C, 500 mA>.
- <Not battery powered: it draws <x W> typically and <y W> at most, from <a 5 V USB supply that gives 2.5 W>.>
- These depend on how the device is used or programmed: <how often it measures; how long the light stays on>.
**Your approval of this gate fixes the battery (kind, capacity, size, connector) for the PCB.** A different battery afterwards means a new board definition.

## Cost of the sample batch
| Item | Amount |
|---|---|
| Parts for <5> boards plus spares | <x> |
| Per-order fees (setup, extended parts) | <x> |
| PCB | <x> |
| Shipping and tax (estimate) | <x> |
| **Total** | <x> |

Against your target of <z> per board (`references/working-rules.md` section 11, quality first, then cost): <x> now at <5> boards, <y> at <100>.
| Biggest cost driver | Per board | A cheaper way to the same quality |
|---|---|---|
| <U2 regulator, extended line> | <0.40 plus the fee> | <found: a basic part with the same accuracy and dropout, taken; or none found> |
Kept as an unfitted footprint because its need is uncertain: <snubber C30>. <Quality and the target cannot both be met: your options, a higher cost, fewer features or a named limitation | none>.

The priced parts list, line by line: `<out/BOM_STOCK_CHECK.md>`. You saw a first figure of <x> on <date> (cost check); it is now <y> (<why it changed>).
**Your approval of this gate also says: go ahead with the PCB at this parts cost.** If the cost is not acceptable, say so now; after this point a cheaper design means a new schematic.

## Open items and deviations
Only an UNKNOWN on a blocker-level item blocks this gate. Every other UNKNOWN is listed here with the bench test that will settle it; your approval of the gate accepts this list. A FAIL or deviation that changes what you get is never accepted with the gate: it is asked below, on its own.
| Item | What it is | Your decision |
|---|---|---|
| <Open after the re-check: LC-MJ2> | <what it is, what is known and not known; bench test BT-06 with its pass value> | <accept with the test / change the design at this cost> |
| <Deviation SIM-05, changes what you get> | <resets once on a 20 ms dip> | <accept / change> |
| <Deviation SIM-09, ruled on by the designer> | <a rise time 0.2 us over my own limit; no effect on the function: reason> | <accepted with the gate> |
| <Limit corrected: SIM-11 replaced by SIM-14> | <the limit was derived at the wrong point; the old result failed, the new one passes; you were told on <date>> | <accepted with the gate> |
| <UNKNOWN: loop stability of the converter, no model> | <bench test BT-03> | <accepted with the gate> |

## Questions for you (each item that changes what you get, at most three per message, more in later rounds; everything else on this page is accepted with the gate)
<Question>
Suggested: <answer>
Why: <reason>

## Frozen state
Netlist sha256 <value>, reviewed in `reviews/frozen/sch-r<round>-<first 12 characters>/`. Design note: `DESIGN_NOTE.md`. After your approval no schematic change happens without your word.
