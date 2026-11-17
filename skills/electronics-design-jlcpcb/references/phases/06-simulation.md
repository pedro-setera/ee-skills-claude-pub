# Phase 6: simulation campaign

Answer by simulation what a calculation cannot answer about the circuit, and every fault of the protection table, against limits fixed in advance; name what only the bench can prove.

## Inputs

- The exported netlist and its checksum; `DESIGN_NOTE.md` (budgets, protection table, back-feed list, set-points); `REFERENCE_CHECK.md`.
- `references/simulation.md`: the method, the test types, the model rules, the results format.
- `templates/SIM_PLAN.md`, `templates/SIM_RESULTS.md`; `scripts/sim/` (`ngs.py`, `plot.py`, `tb_template.py`).
- `references/review-briefs/simulation-coverage.md` for the audit, only where the depth of this board switches it on (`references/reviews.md` section 9), and the edge-case list in `references/review-briefs/schematic-system.md`.
- `references/lessons.md`, section "Phase 6: simulation campaign".

## Steps

1. Check the engine. `scripts/env_check.py` reports whether ngspice is present. If it is missing, follow `references/tools.md`: the affected points become UNKNOWN, each with a bench test and a numeric pass value, listed in the gate 1 summary for the user to accept with the gate. LTspice is asked for only when a maker's model exists for it alone.
2. Write `sim/PLAN.md` before any run: one row per question, with its ID (`SIM-01`, `SIM-02` ...), the block, the question, the test (stimulus and corners) and the pass limit.
   - Each limit is a number taken from a requirement or a datasheet limit, at the point where that limit applies: at the load's pins, or at the source, as the specification defines it.
   - Record the plan's date at the top of `sim/PLAN.md` and in the state file. It is the proof that the limits came first.
3. Build the plan from lists, so that nothing depends on what comes to mind, and keep it to the extent of `references/simulation.md` section 2: a test for what a calculation cannot answer, and for every fault of the protection table. Go through:
   - every row of the protection table: each fault on the branch where it can really happen. Each gets a test;
   - every block of the block diagram: a test only where a calculation in the design note cannot answer how it behaves (timing, stability, a filter with its cable, the order in which things act). A maker's circuit used inside its datasheet conditions gets one line saying so;
   - every row of the back-feed list and every edge case of the system review brief that can really happen on this board: a test where a calculation cannot settle it, otherwise the calculation;
   - every set-point: calculated at its minimum, nominal and maximum in the design note; simulated only where the calculation leaves a doubt, and for every deviation in `REFERENCE_CHECK.md` that is justified "by simulation".
   A block or row without a test gets its reason in the coverage matrix: "calculated in the design note, section <n>", "maker's circuit inside its conditions", or "bench test `BT-<nn>`". Before adding a test, ask which decision its result could change; if none, do not run it (`references/working-rules.md` section 12).
4. Choose and write the models as `references/simulation.md` says: the maker's model where it runs; otherwise a behavioural model built from the datasheet and calibrated on a published measurement; capacitors at their DC-bias value; real loads with their harness; unpowered parts as floating rails. The calibration run is the first test of each behavioural model and has its own limit.
5. Write one test bench per block from `scripts/sim/tb_template.py`. Each test states its limit before the run and writes a plot and a results file.
6. Run the suite in parallel with `scripts/sim/ngs.py`. Each process gets its own temporary folder; shared temporary files once made parallel runs corrupt each other.
7. Check convergence before using any number: a clean simulator log, the run reached its end time, and the plot looks physical. Open every plot and write what you saw. A run that did not converge has no result: fix the bench and run again. A bench that cannot be made to converge becomes an UNKNOWN with a bench test and a numeric pass value (`references/simulation.md` section 6), listed at gate 1.
8. Judge each test against the plan. On a FAIL there are two honest ways out, and the limit is not moved in either:
   - change the design: back to phase 5 (regenerate, ERC, netlist check), then re-run the affected tests;
   - keep it as a named deviation with its consequence. A deviation that changes what the user gets (a function, a limit they stated, the cost, a risk of losing a board) is asked of the user. Any other you rule on yourself, with the reason in `sim/RESULTS.md`, and list in the gate 1 summary; the user's approval of the gate accepts that list (`references/working-rules.md` section 2).
   If a limit turns out to be derived wrongly, do not edit it: write down what was wrong, add a new test with the correct derivation under a new ID, keep the old test with its FAIL in the summary table, and tell the user of the correction with the next message (`references/simulation.md` section 2).
9. Record the stress, not only the outcome: in every protection test the peak current, the energy and the I2t in the protecting part against its ratings, and the voltage at every load connector.
10. Write `sim/RESULTS.md` from the template (`references/simulation.md`, section 8): each result beside its unchanged limit, what the simulations changed in the design, the accepted deviations, the models and their sources, the limits of the campaign, and the table "what only the bench can prove". Copy that table's items into the bench tests of `DESIGN_NOTE.md` (`BT-<nn>`), each with a numeric pass value.
11. Run the coverage audit, only where the depth of this board switches it on (`references/reviews.md` section 9: a switching converter, more than 2 A, more than 30 V, or the full set; read the facts again now, on the circuit as drawn). In the lean default there is no audit: go to step 13; the lean circuit reviewer of phase 7 reads the plan and the results.
    - Freeze the schematic export, the design note, the reference check, the datasheets and `sim/` to the audit's own copy `reviews/frozen/sim-r<round>-<first 12 characters of the netlist's SHA-256>/`, where `<round>` is the number of the last completed fix round, counted over the whole project (0 when none has happened yet).
    - Launch a fresh agent with `references/review-briefs/simulation-coverage.md`, model and effort set explicitly. It looks for what was not simulated, judges models and limits, and re-runs a sample itself. Where the fact switched on only the power simulations, say so in its `<SCOPE>`.
12. Close the audit here, by the end rule (`references/reviews.md` section 6), so that the phase 7 reviewers see the completed test set: one fix round (add and run the cases it found missing that belong to the extent, limit first; answer each finding in `reviews/RESPONSE_<round>.md`), then one re-check in which the auditor looks only at what was fixed and writes `reviews/VERIFY_<round>_SC.md`. A blocker is closed or accepted by the user in writing; whatever else is still open goes to the user at gate 1 as a named risk with its bench test. No further round, unless the full set switched on a second one. Its report goes into the gate 1 summary.
13. Keep the suite runnable. It runs again in full on the final schematic after the fix round of phase 7, and again when the layout adds long power paths whose resistance and inductance matter.

## Questions for the user

None by default. Two cases need the user (a failed limit only when it changes what they get; the rest you rule on and list at the gate):

- LTspice is missing. It is needed because `<maker>` publishes the model of `<part>` only for it. May I install it?
  - Suggested: install it from the maker's official page.
  - Why: without it the part is simulated with a behavioural stand-in and its loop or timing stays a bench item.
- (Only when it changes a function, a limit the user stated, the cost, or a risk of losing a board) Test `<ID>` fails its limit: `<limit>` against `<result>`. Accept it as a named deviation, or change the design?
  - Suggested: `<the option you would choose, with its cost>`.
  - Why: `<the consequence in plain words: what the device does in that case, and that nothing is damaged, or what is>`.

## Checks before leaving this phase

- [ ] `sim/PLAN.md` is dated before the first run and every row has a numeric limit with its derivation. Evidence: the file, the state file log, the first results file's time.
- [ ] Every protection row maps to a test; every block, back-feed row and applicable edge case maps to a test or to its reason (calculated, maker's circuit inside its conditions, bench test). No test is in the plan whose result could change no decision. Evidence: the coverage matrix of the plan.
- [ ] Every model names its source, and every behavioural model has a calibration test with its result. Evidence: the models table.
- [ ] Ceramic capacitors are entered at their DC-bias value. Evidence: a table of nominal against used value.
- [ ] The whole suite ran; no bench was skipped, except one that is UNKNOWN with its bench test (no engine, or no convergence), listed for gate 1. Evidence: the run log with one line per test.
- [ ] Every result used comes from a run that converged, and every plot was opened. Evidence: the log, and the plot notes in `sim/RESULTS.md`.
- [ ] The limits in the results equal the limits in the plan. Evidence: a line-by-line comparison; changed tests have new IDs and a reason. A test whose limit was corrected still stands in the summary with its FAIL, and the user was told with the next message. Evidence: the summary table, the message.
- [ ] Every result is PASS, FAIL, a deviation the user accepted (with their words), a deviation you ruled on (with the reason, and its line in the gate summary), or UNKNOWN with its bench test (no engine, or no convergence), listed for gate 1; "not converged or not run" without that UNKNOWN row is 0. Evidence: the summary table.
- [ ] Every protection test records the stress in the protecting part and the voltage at each load connector. Evidence: the results rows.
- [ ] The bench-only table exists and its items are in the bench tests of `DESIGN_NOTE.md`. Evidence: both files.
- [ ] The depth facts were read again on the circuit as drawn, and the state file says whether the coverage audit is switched on. Where it is: it ran on a frozen copy, with model and effort stated, had one fix round and one re-check, and what it left open is listed for gate 1 as named risks. Evidence: `depth_facts` in the state file; `reviews/SC_SIM_COVERAGE_FINDINGS.md` and `reviews/VERIFY_<round>_SC.md`.

## Outputs

- `sim/PLAN.md`, the test benches and models in `sim/`, plots and result files in `sim/out/`, `sim/RESULTS.md`
- Where the coverage audit is switched on: `reviews/SC_SIM_COVERAGE_FINDINGS.md` and its closure file `reviews/VERIFY_<round>_SC.md`
- `DESIGN_NOTE.md` updated: design changes, bench tests

## Lessons behind this phase

- A power circuit reached its first review on hand calculations. Simulation then changed it in several places: a damping capacitor moved to the other side of a filter, output capacitors added, a faster clamp, a larger diode among them -> the campaign runs before the reviews.
- A pass level was lowered so that a supply-dip test passed. A reviewer rejected it: the specification's limit applied at the source, before the cable drop -> limits are written first, derived at the right point and never moved; that test stayed a recorded failure, accepted as a deviation.
- A hot-plug run with an ideal switch had not converged; only the plot showed it -> convergence is checked and every plot is opened before a number is used.
- An unpowered part was modelled as an ideal 0 V source and the transistors without sub-threshold conduction, which hid a back-feed fault -> unpowered parts are floating rails with their own load, and microamp circuits get worst-case device corners.
- Four scenarios were missing until a reviewer listed them: slow supply ramps, a sustained sag, a back-powered host, partial shorts -> the plan is built from lists, and on a power board an independent audit looks for what is absent.
- On a simple low-voltage board an audit of the simulations ran pass after pass; each pass asked for a finer case than the last, none of them wrong, and none would have changed the first samples -> the extent is fixed (what a calculation cannot answer, and the protection table), the audit runs only where a fact switches it on, and it ends after one fix round and one re-check.
- A PTC model derated more gently than the datasheet's table and hid that the part would trip at its working temperature -> models are fitted to the datasheet's hot corner, and the model's limits are written beside the result.
- The makers' models of the two main power chips were encrypted for one vendor's simulator -> a behavioural model, a calibration on the maker's published measurement, and a bench item for what the model cannot show.
- A protection simulation assumed a pull-up value that made the normal data path fail; nobody had simulated the function itself -> beside every protection test that changes a signal path there is a test of normal function.

The full cases are in `references/lessons.md`.
