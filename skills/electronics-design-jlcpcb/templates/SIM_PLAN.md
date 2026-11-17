# <board name>: simulation plan

Plan written: <date>. The same date is in the state file; it is the proof that the limits came first.

Written before any run. **Pass limits are written here first and never moved.** If a test fails, the design changes or it becomes a named deviation (see `sim/RESULTS.md`): asked of the user when it changes what they get, otherwise ruled on by the designer and listed at the gate. A limit that was derived wrongly is not edited: the correct test gets a new ID, the old row stays with its FAIL, and the user is told with the next message. This plan is kept as `sim/PLAN.md`.

Engine: <ngspice 45>. Runner: <script>, private temp folder per process, parallel. A run counts only after the convergence check.

## Rules for the plan
- One row per question, with its ID `SIM-01`, `SIM-02` ... (a changed test gets the next free ID). The extent: every fault in the DESIGN_NOTE protection table, and what a calculation cannot answer (start-up and power-down timing, loop stability, hot plug with the real cable, the order in which protections act). What a calculation settles (set-points and tolerance corners, dividers, losses) stays in the design note and is named in the coverage matrix. A test whose result could change no decision is not in the plan.
- Limits come from datasheets and the requirements, not from the first result.
- Models: maker model if one exists; otherwise a behavioural model built from the datasheet and calibrated on a published measurement. Ceramic capacitors at their DC-bias value. Real loads and harness included.
- Write the source of every model.

## Plan
| ID | Block | Question | Test | Pass limit (written first) |
|---|---|---|---|---|
| <SIM-01> | <3.3 V rail> | <does it start cleanly from 5 V?> | <transient, 0 to 5 V in 1 ms> | <rail within 3.2 to 3.4 V by 5 ms, overshoot < 100 mV> |
| <SIM-02> | <input protection> | <does a 20 V charger harm the load?> | <20 V step with 1 m cable inductance> | <load pin < 6.0 V, TVS peak current < 20 A> |
| <SIM-03> | <sensor supply> | <does a short on the header latch or recover?> | <0.1 ohm short for 1 s, then removed> | <input current < 1.5 A, rail recovers in < 100 ms> |

Model per test, kept apart so each table fits five columns:
| ID | Model | Source of the model | Tolerance corners run | Plot file |
|---|---|---|---|---|
| <SIM-01> | <behavioural LDO> | <datasheet p. 8, calibrated on the load-step figure p. 12> | <R 1 %, C -20 %, T -40/85> | <`sim/out/sim-01.png`> |
| <SIM-02> | <maker TVS model> | <maker website, file name, date> | <TVS min and max clamp> | <`sim/out/sim-02.png`> |

## Coverage matrix
Every row of the DESIGN_NOTE protection table must appear here with its test; every block and bench-risk with its test or its reason (calculated in the design note, maker's circuit inside its conditions, bench test).
| Item from the design note | Covered by | Or: reason it cannot be simulated |
|---|---|---|
| <Reverse polarity> | <SIM-04> | |
| <ESD on the connector> | | <needs the bench: no model of the IEC gun> |

## Known model limits
- <Encrypted maker model: behavioural stand-in used, loop phase margin not provable here.>

## Coverage audit
<Not run: the depth of this board is lean and no fact switches the audit on (`depth_facts` in the state file). | Run, switched on by <the fact>, on <the power simulations | the whole campaign>: the independent coverage review (SC) at the end of phase 6, on its own freeze: `reviews/SC_SIM_COVERAGE_FINDINGS.md`, <date>; one fix round, one re-check. Missing cases found and added: <finding IDs such as SC-MJ1, and the new test IDs>. Still open, to the user at gate 1: <IDs or none>.>
