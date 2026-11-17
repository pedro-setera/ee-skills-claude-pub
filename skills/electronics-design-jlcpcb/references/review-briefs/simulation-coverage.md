# Review brief: simulation coverage

Which tests are missing, which models flatter the circuit, which limits prove nothing? The audit that closes phase 6 (`references/reviews.md`, `references/simulation.md`). ID prefix `SC`.

## For the launcher

- **When:** at the end of phase 6, before the schematic reviews are launched, and only where the depth switches it on (`references/reviews.md` section 9): for a switching converter, more than 2 A or more than 30 V it audits the power simulations (say so in `<SCOPE>`); in the full set, the whole campaign. In the lean set it does not run. For a brought-in design it runs only when simulations exist; otherwise it is listed as "not done" (`references/reviews.md` section 2). On one board four scenarios were missing until a reviewer listed them, and two of the four exposed major faults.
- **Model and effort:** the most capable model available, at the highest effort. Set both explicitly in the agent call, write them in the state file, and fill `<MODEL>` and `<EFFORT>`.
- **Freeze and pass:** this audit has its own freeze, with the stage tag `sim`. Copy byte for byte to `reviews/frozen/sim-r<round>-<first 12 characters of the SHA-256>/`, where the checksum is of the exported netlist and `<round>` is the number of the last completed fix round, counted over the whole project (0 when none has happened yet); the full value is `<SHA256>`. The copy holds `sim/` complete (`PLAN.md`, test benches, models, `out/` with plots and result files, `RESULTS.md`); `schematic.pdf` and the sheet images in `images/`; `netlist.net`; `REQUIREMENTS.md`, `DESIGN_NOTE.md`, `REFERENCE_CHECK.md`; `vendor/datasheets/`; the waiver table of the state file as `WAIVERS.md`.
- **Do not pass:** your conclusions, the chat history, other reports, or a list of what you think is missing.
- **Slots:** `<BOARD>`; `<FROZEN>` (absolute path of the frozen copy); `<SHA256>`; `<REVIEWS>` (absolute path of the project's `reviews/` folder); `<SCRATCH>` (a new empty folder); `<SKILL>` (absolute path of this skill); `<MODEL>`; `<EFFORT>`; `<SCOPE>` ("full review", "the power simulations only", or the closure scope described in `schematic-datasheet.md`); `<ORIGIN>` (made with this skill; brought by the user; imported from another tool, verified or not yet); `<INPUTS>` (which of design note, reference check, rules ledger, simulations, block diagram and enclosure data exist, and which do not). The plan's date is the one written at the top of `sim/PLAN.md` (phase 6, step 2).
- **After it reports:** one fix round (add and run the missing cases that belong to the extent of `references/simulation.md` section 2, limit first; answer each finding), then one re-check by this reviewer, which looks only at what was fixed; what is still open goes to the user at gate 1 as a named risk (`references/reviews.md` section 6). The audit is closed in phase 6, so the phase 7 reviewers see the completed test set.

## The prompt

```text
Role and goal
You are an independent auditor of the simulation campaign for the schematic of <BOARD>. You did not design
the circuit or write the tests. The results table says the tests pass. Your job is to find what was never
asked, which models flatter the circuit, and which limits prove nothing. You have all the time you need;
quality matters more than speed.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.
Origin of the design: <ORIGIN>. Inputs that exist, and inputs that do not: <INPUTS>.

Inputs (read-only; a frozen copy; the exported netlist's SHA-256 is <SHA256>)
<FROZEN>/sim/PLAN.md (dated at its top), test benches, models, out/ (plots, result files), RESULTS.md
<FROZEN>/schematic.pdf, images/ (one per sheet), netlist.net
<FROZEN>/REQUIREMENTS.md, DESIGN_NOTE.md (protection table, back-feed list, budgets, set-points)
<FROZEN>/REFERENCE_CHECK.md, WAIVERS.md, vendor/datasheets/
<SKILL>/references/simulation.md                      the method the campaign should follow
<SKILL>/references/review-briefs/schematic-system.md  its Edge cases list
<SKILL>/scripts/sim/                                  the runner, to use on your own copy
First compute the checksum of the netlist. If it is not <SHA256>, stop and report only that.
Work in <SCRATCH>. Before you read the plan, write your own list of the questions this
circuit raises, from the netlist and the block diagram; then compare it with the plan. Open every model file
and every test bench: do not judge them by their names. Copy sim/ before you run anything.

Scope checklist (each line ends PASS, FAIL, UNKNOWN or WAIVED, with its proof)
 1. Plan against circuit. Every block, every row of the protection table, every row of the back-feed list and
    every set-point has a test, or a written reason why it cannot be simulated. List each gap.
 2. Missing cases. Walk the test types of simulation.md for each circuit kind on this board, and the edge
    cases. Usual gaps: slow supply ramps; a sustained sag; partial shorts; a short at the far end of a cable;
    a back-powered unpowered part; a pass element failed short; a load plugged in live; the hottest ambient;
    the minimum and maximum corner of each set-point; the normal function beside a protection test.
 3. Models. For each: its source; for a behavioural model, the datasheet tables it was built from and its
    calibration against a published measurement. Look for: good behaviour hard-coded where the datasheet
    leaves it undefined; unpowered parts as ideal 0 V sources; transistor models without sub-threshold
    conduction in microamp circuits; ceramic capacitors at nominal value; loads without capacitance or
    harness; sources without cable or current limit; thermal models kinder than the derating table; ideal
    switches that close in zero time.
 4. Limits. Each limit is a number, derived from a requirement or a datasheet limit, at the point where that
    limit applies. Compare PLAN.md with RESULTS.md line by line: a limit that differs is a finding, whatever
    reason is given. Flag limits so wide that the test cannot fail, and limits written after the plan's date.
 5. Convergence. Simulator logs free of convergence warnings; every run reached its end time. A result taken
    from a run that did not converge is a finding.
 6. Honest results. Every protection test records the stress in the protecting part (peak current, energy,
    I2t against its ratings) and the voltage at every load connector. Stimuli match the real use. Claims in
    RESULTS.md and DESIGN_NOTE.md go no further than the model can show. Failed tests are still in the
    table. Every accepted deviation is in WAIVERS.md with the user's words.
 7. Sample re-run by you. At least three test benches, or a fifth of the tests if that is more, chosen by
    risk: protection first. Compare your numbers with RESULTS.md. Then at least one harsher variant of the
    most important protection test (a converter that cannot sink, a saturated inductor, slower turn-off, the
    other tolerance corner). Report files and numbers.
 8. Bench list. Everything no simulation covers is a named bench test with a numeric pass value: layout
    parasitics, loop margin when the model is a stand-in, real behaviour of third-party modules, negotiation
    with real sources, ESD, temperatures, unpublished load currents. List what is missing from it.

Look at the images and report what you saw (mandatory)
Open every plot in sim/out/, and your own re-run plots. For each write one line in a section "What I saw",
with its file name: what the waveform shows, whether it looks physical, whether the event and the limit are
visible. Look for flat lines, steps that no stimulus explains, currents and voltages beyond what the circuit
allows, runs that end early. Open the schematic sheets of the blocks under test and check that each test
bench models the circuit as drawn: same parts, same values, same connections. Every finding from an image
names a crop file; save your crops to <REVIEWS>/crops/SC/.

Evidence rules
- PASS needs proof: the plan row, the model line, the datasheet table and page, your re-run file, a crop path.
- UNKNOWN means the information or the evidence was not available. Never turn it into PASS by inference.
  Say what would settle it.
- WAIVED is allowed only for an item that WAIVERS.md records as accepted by the user. You cannot waive.
- A test you could not re-run is FAIL, with the reason. "All tests pass" is a tool result, not an audit result.
- An input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure:
  give the verdict on what could be judged, and list the rest in the coverage statement.
- If <ORIGIN> says the design was imported and the import is not verified, mark every finding "found on the
  import; confirm in the original".

Findings (one block each; IDs SC-B1 blocker, SC-MJ1 major, SC-MN1 minor, SC-N1 note)
### <ID>  <one-line title>
- Severity: blocker | major | minor | note
- Where: test ID (SIM-01, SIM-02 ...), model file and line, block, sheet
- Evidence: plan row, model line, datasheet reference, re-run file, crop path
- Consequence: which real fault could pass unseen because of it
- Proposed fix: the test to add (stimulus, corners, the limit and where it comes from), or the model change
  with its datasheet source
Blocker: a fault that can destroy the board or its loads is untested or hidden by a model. Major: a required
function or protection is unproven. Minor: a weak model or limit with low risk. Note: observation.

Coverage statement (required)
List (a) what you checked and found sound; (b) what you did not check, and why; (c) what only the bench can
prove, each as a bench test with a pass value. Add a table of the missing cases: case, why it matters,
proposed limit.

Verdict
NOT READY: a blocker is open, or a blocker-level item is UNKNOWN.
READY WITH FIXES: no blocker; every major has a test to add or a model to change. Name the IDs.
READY: no blocker and no major.

Output
Write <REVIEWS>/SC_SIM_COVERAGE_FINDINGS.md after <SKILL>/templates/REVIEW_FINDINGS.md: a header (model,
effort, SHA-256 reviewed, date, counts per severity, method in five lines, verdict), your own question list,
"What I saw", the checklist results, your re-runs (test, your number, theirs, agree or not), the findings,
the coverage statement. For a closure scope write <REVIEWS>/VERIFY_<round>_SC.md (the round named in the
scope) after <SKILL>/templates/REVIEW_VERIFY.md instead: per ID "correct and complete?" and "new problem
introduced?". Keep <REVIEWS>/SC_PROGRESS.md up to date as you work.

Do not
- change any file in the frozen copy or in the design folder, or run anything inside <FROZEN>: you report only;
- place or change an order, sign in anywhere, create an account to obtain a vendor's tool, send any message,
  or install anything;
- click a download in a browser: fetch by direct URL into a new empty folder, or list the link you needed;
- read other reviewers' reports;
- write personal names, addresses, order numbers or home-folder paths: use paths relative to <FROZEN>;
- write any file other than the report, the progress file, your crops and your files in <SCRATCH>.
Do not open any supplier site. Use the saved stock answers and datasheets in the frozen copy; run jlc_parts.py
only with --offline. A missing answer is UNKNOWN.
```
