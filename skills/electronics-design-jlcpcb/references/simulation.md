# Simulation: the campaign method

How to plan, model, run and report the simulations of phase 6, and how reviewers re-run them. A campaign is a list of questions with limits written first. A single "it works" run is not one.

On one board, simulation changed the design in several places before any copper existed, and showed two faults that hand calculation had missed. On the same board a moved limit, a run that had not converged and a model that was too kind each nearly passed a defect. The rules below come from both.

## Contents
1. The engine
2. The plan
3. Test types by circuit kind
4. Models: sources and honesty
5. Test benches and parallel runs
6. Convergence check
7. Plots
8. The results file
9. What only the bench can prove
10. Re-runs

## 1. The engine

- **ngspice first.** It ships with KiCad, runs from the command line and in parallel, and is driven from Python by `scripts/sim/ngs.py`.
- **Every netlist and every included file is scanned before it runs.** `scripts/sim/ngs.py` refuses (exit 2, the word REFUSED, file, line number, line) a model that carries a command block, starts a program, loads code, writes a file or includes from outside `sim/` (section 4).
- **A maker's model for PSpice or LTspice: try ngspice's compatibility mode before another simulator.** Set `COMPAT` in the bench (`ps`/`psa` PSpice, `lt`/`lta` LTspice, `ltps`/`ltpsa` both; the final `a` also translates the bench's own netlist), or `--compat` on the bench or on `ngs.py suite`. Which mode wins: the bench's own `--compat`, then its `COMPAT` when it is not `off`, then `ngs.py suite --compat`, else off. Without the mode such a model can give other numbers with no error: `v**3` at -2 V is +8 V in ngspice's own mode and -8 V in `lt`. Install LTspice only when the model still does not load or does not calibrate.
- **The mode stands in every result line and results file.** A number is never quoted without it.
- **LTspice when a maker's model needs it.** Some makers publish models that run only there. Ask before installing, and note in the results which tests ran in which engine.
- **Encrypted models tied to a vendor's own simulator** cannot run in either. Do not create an account to get that tool; sign-in is the user's. Keep the model file in `sim/` for the user, build a behavioural model (section 4), and add a bench item for what it cannot show.
- **Plain numeric work** (Python with numpy) for RF cascades, line impedance and tolerance Monte Carlo. For RF filters also SciPy (the standard filter prototypes, optimisation) and `scikit-rf` (reading the makers' Touchstone files, cascading, plotting), where they are installed (`references/tools.md` section 1); ngspice is the second, independent method.
- **No engine at all:** every affected question is UNKNOWN and moves to the bench list with a numeric pass value. Say so at gate 1.

## 2. The plan

**The extent: what gets a test.** A simulation is run for a question that a calculation cannot answer, and for every fault in the protection table of the design note. Nothing else by default:

- A set-point, a divider, a threshold, a current limit, a power loss: calculate it at its tolerance corners in the design note. A calculation that settles the question needs no simulation beside it.
- A maker's circuit used inside its datasheet conditions: one line saying so. It is simulated only where this design leaves those conditions.
- What a calculation cannot answer gets a test: start-up and power-down with their timing, a loop's stability, what a filter and a cable do together when plugged in live, an oscillator's frequency with real parts, the order in which protections act.
- Every fault of the protection table gets a test, each on the branch where it can really happen. A fault that is not in the table is not simulated; if a reviewer shows that it can really happen on this product, it enters the table first.
- A question that neither a calculation nor a model can settle is a bench test (section 9), not a longer campaign.

A campaign that keeps growing finds finer and finer cases and never reaches the gate. When a test is proposed, by you or by a reviewer, ask which decision its result could change. If none, it is not run.

**The coverage audit** (`SC`, an independent agent that looks for what was not simulated) runs only where the depth of the board switches it on (`references/reviews.md` section 9: a switching converter, more than 2 A, more than 30 V, or the full set), and then on the power simulations or on the whole campaign as that row says. In the lean default no audit runs: the lean circuit reviewer reads the plan and the results and re-runs a sample.

`sim/PLAN.md` (from `templates/SIM_PLAN.md`) is written before the first run. It has three tables:

| Table | Columns | Rule |
|---|---|---|
| Plan | ID, block, question, test, pass limit | One row per question, ID `SIM-01`, `SIM-02` ...; the limit is written first |
| Models | ID, model, source, corners run, plot file | Every model names where it comes from |
| Coverage matrix | Item of the design note, covered by, or the reason it cannot be simulated | No protection row and no risk is left without one of the two |

Rules for limits:

- A limit is a number with a unit, taken from a requirement or a datasheet limit.
- It applies at the point the specification names: at the load's pins, at the source, at the pin of the part. A limit checked at the wrong point is a different limit.
- It is written before the run and never moved. A failed test changes the design or becomes a named deviation. A deviation that changes what the user gets (a function, a limit they stated, the cost, a risk of losing a board) is asked of the user on its own; any other is ruled on by the designer, with the reason, and listed in the gate summary (`references/working-rules.md` section 2).
- A limit that turns out to be derived wrongly (at the wrong point, from the wrong figure) is not edited. Write down what was wrong, add a new test with the correct derivation under the next free ID, and keep the old test with its FAIL in the summary table, marked "limit corrected, see `SIM-<nn>`". Tell the user of the correction with the next message, in one line: which limit, why it was wrong, the old and the new result. A corrected limit that nobody was told about looks, afterwards, exactly like a limit moved to make a test pass.
- A limit so wide that the test cannot fail is not a limit.
- A set-point that is simulated is run at its minimum, nominal and maximum tolerance corner.

## 3. Test types by circuit kind

Use this as a menu for the plan; take every row that fits the board.

| Circuit kind | Tests to consider | Limits come from |
|---|---|---|
| Input protection, hot-swap, electronic fuse | Start-up inrush and junction temperature at each slew corner; under- and over-voltage thresholds by a slow sweep; hard short at the output; the inductive kick at a fast trip; hot plug of a live source through cable inductance; a load peak above the limit against the blanking time | Absolute maximum and safe operating area of the part; the source's rating |
| Switching converter | Calibration against a maker's measured figure; start-up at lowest and highest input into the total effective capacitance it drives (`references/pcb-rules/power.md` PWR-50); load steps up and down, read at the load's pins behind the harness; damping against the output capacitance at DC bias; input filter impedance against the converter's negative input resistance at lowest input and full power; the minimum on-time at the highest input and the maximum duty at the lowest; the input's clamped transient against the absolute maximum; loop phase margin where the compensation is external, and the ripple-injection network where the control scheme needs one (PWR-52, PWR-53); for a boost, the plug-in inrush and an output short with the regulator off (PWR-66) | The loads' voltage window; the load's under-voltage threshold; the maker's stability guidance, minimum on-time, maximum duty and absolute maximum input |
| Linear regulator, reference | Stability with the chosen output capacitor's ESR; start-up into the total capacitance it drives; drop-out at lowest input and full load, at the hottest temperature; rejection of a converter's ripple at the real headroom where it follows one (`references/pcb-rules/power.md` PWR-54); dissipation | The datasheet's stable region, dropout and maximum output capacitance; the load's window; the rail's allowed ripple |
| Supply rails and decoupling | Rail impedance with a 1 A AC source over the rail's frequency range, where PWR-49 calls for it (below about 1 ohm on a digital rail, or a rail whose own load or noise need sets a range); load steps with the regulator and its bulk capacitors; a band capacitor beside the larger one, with mounted inductance, for a parallel peak in any victim band | Target impedance in ohms, its frequency range, observation point and dynamic allowance in volts, from the design note's rail table (`references/pcb-rules/power.md` PWR-38, PWR-49 to PWR-51) |
| Sequencing, latches, timers, resets | The order of the supplies of every chip that requires one (`pcb-rules/power.md` PWR-63): all rails with their real capacitance, switching on, switching off and a short dip, against the datasheet's order, largest difference and wait; plug-in in every switch position; contact bounce; supply ramps from 1 to 100 ms at worst corners; brown-out and quick return (does the reset re-arm?); timers over threshold, capacitor and leakage corners; glitches on every input that can remove power; the rail dips of a rebooting load | Timing windows of the requirements; the load's boot and shutdown times |
| Output protection | Per output: hard short, partial short between rated load and the limit, short at the far end of the cable, short present at switch-on. A pass element failed short. PTC behaviour at the hottest ambient. Supply dips as a matrix of depth and duration, including "sag and stay" | Contact, wire and bead ratings; absolute maximum of every load; energy rating of the clamp |
| Back-feed, mixed supplies | A powered peripheral into an unpowered host at every allowed interface level; an external voltage on each connector | The "off" threshold of any sensing circuit; absolute maximum of the unpowered part |
| ESD on wires and connectors | The charge-sharing step against trigger thresholds and gate ratings; the nanosecond inductive spike through chokes and via inductance | Pin and gate ratings. A real discharge test stays a bench item |
| Analog signal chain | Gain and offset over tolerances (Monte Carlo); noise; filter response; settling into a converter input; stability with a capacitive load | The accuracy budget of the requirements |
| Digital interfaces, timing | Logic levels in both directions through series resistors with both sides' pulls; rise time against bus capacitance and bit time; reset and enable timing | Input thresholds and timing tables of both sides |
| RF filter (`references/pcb-rules/rf.md` section 12) | The response with real part models, pads, ground vias and track pieces, computed two ways (Python cascade and ngspice) and plotted against the mask; a tolerance Monte Carlo; the level of evidence reached, stated in words | The filter's specification table (RF-90): loss in the pass band, attenuation at each frequency to reject |
| RF estimates | Line impedance from the stack with its tolerance; insertion and return loss of the cascade with its tracks, pads and vias modelled, and a tolerance Monte Carlo; self-resonance of chokes and capacitors with their mounting against the band | The link budget. Estimates only; a network analyser confirms |

In every protection test record the stress in the protecting part (peak current, energy, I2t against its ratings) and the voltage at every load connector, not only "it tripped". Beside every protection test that alters a signal path, run a test of the normal function with the same values.

RF filters, the steps in order (`references/pcb-rules/rf.md` RF-90 to RF-96): (1) the specification table, written before any choice; (2) the search for a ready filter part: when one fits, its maker's S-parameter file is the model and step 3 is skipped; (3) for a discrete filter, the values from a standard prototype, rounded to values that can be bought; (4) every part's model from its maker, the pads, ground vias and track pieces added; (5) the response by a Python cascade and again by ngspice, both plotted against the mask; (6) the tolerance run; (7) the statement of the level reached and, where the layout decides, the bench test that settles it. All of it runs as scripts in `sim/`, so that it can be repeated after every change of a value.

RF notes: model every track between RF parts as a line of its real length and impedance, and every shunt part with its pads and ground-via inductance; compare with the lumped-only result and start bench matching from the full model. In the Monte Carlo give each passive its real tolerance grade (absolute pF for small capacitors), run 50 to 100 cases, state loss and match from the spread plus a margin, never from the nominal, and tighten only the part that dominates the spread.

## 4. Models: sources and honesty

Order of preference:

1. The maker's own model, used as it is. Record the file, the source page and the date.
1a. The maker's model for PSpice or LTspice, run in ngspice's compatibility mode (section 1), after it has passed a calibration row.
2. The maker's model for another simulator, run there if the user allows the install.
3. A behavioural model built from the datasheet: thresholds, timings and limits with their spreads as parameters, each block naming its table or figure. Calibrate it on a published measurement, for example the load-step plot of the maker's reference design: reproduce the maker's conditions, compare, then run our values. The calibration is a test with its own limit.
4. An ideal element, with the reason and what it means for the result.

Honesty rules:

- **Undefined stays undefined.** A model must not hard-code good behaviour where the datasheet leaves it open, such as a latch's state below its minimum supply. That becomes a bench item, not a pass.
- **Ceramic capacitors at their DC-bias value.** As orders of magnitude: a 22 uF 25 V part at 5 V may be 13 uF, a 10 uF 50 V part at 20 V 5 uF, a small-case 1 uF 50 V part at 20 V 0.4 uF. Read the maker's curve for the real part.
- **Real loads:** resistance, input capacitance, step profile, harness resistance and inductance, contacts. Not an ideal current source.
- **Real sources:** cable resistance and inductance, the source's current limit, its allowed voltage range.
- **Unpowered parts are floating rails** with their own load and clamp paths, not ideal 0 V sources. An ideal source hides every back-feed fault.
- **Microamp circuits get a worst-case transistor corner.** A simple transistor model does not conduct below threshold; a real one does.
- **Inductors carry their DCR,** and their saturation in fault tests.
- **Thermal models are fitted to the datasheet's derating table** at the hottest local temperature, not to the 25 C point.
- **Protection tests also run pessimistic variants:** a converter that cannot sink current, a saturated inductor, a slower turn-off than typical.
- **Say what is applied and what is modelled.** A fault timing forced by the test bench is a stimulus, not a model result.
- **List each model's limits beside the result,** and claim no more than the model can show.
- **Scan a model the moment it is downloaded:** `python -I scripts/sim/ngs.py scan sim/models/<file>`. A model is executed by the simulator, not only read. Keep models in `sim/models/`; a bench that includes from another folder names it (`ngs.run(..., models=[folder])`). The runner scans again before every run, and the scan cannot be switched off. It is a guard, not a sandbox: you still read a downloaded model before using it.
- **REFUSED means: do not use the file as it is.** Read the named line. Either do not use the model, or correct a copy by hand: remove the named lines (a command block, a model that starts a program), keep the original beside it, and write the change into the Models table of `sim/PLAN.md` (file, lines removed, why, date). Never work around the scan (no renamed keyword, no include from the bench's Python).
- **Calibrate on a datasheet figure first.** A model run in a compatibility mode, and every behavioural model, gets a calibration test before any other: the bench reproduces one figure of the part's datasheet at the datasheet's conditions; its limit is `ngs.calibration(quantity, datasheet value, tolerance, unit, source)`. The row records measured value, datasheet value, tolerance and PASS or FAIL. While it fails, the other rows of that model are not results. Nothing forces a bench in a mode to have such a row: the summary line shows the count, and a count of 0 beside a mode is a finding.
- **The mode reproduces the other simulator; it is not "more exact".** In `ps` the exponential is a straight line above an exponent of 14 (e^20 reads 8.4e6 instead of 4.85e8), as in PSpice. Use a mode only for the models that were written for it, and say which tests ran in which mode.
- **No init file beside a bench.** A `.spiceinit` or `spice.rc` in `sim/` is executed by ngspice at start; the runner refuses to start there. The mode is `COMPAT`, not an init file.

## 5. Test benches and parallel runs

- One test bench script per block, started from `scripts/sim/tb_template.py`, kept in `sim/`. Each test declares its limit before it runs and writes a plot and a results file to `sim/out/`.
- Run the whole suite in parallel with `scripts/sim/ngs.py`, using all cores, capped by free memory. Each process works in its own temporary folder; shared temporary files once made parallel runs corrupt each other.
- Quote every model path. A path with a space breaks an unquoted include line. A `.lib <file> <section>` line cannot take a path with a blank, quoted or not: use `.include`, or a path relative to `sim/`.
- Fix the seed of every Monte Carlo run, so that a re-run gives the same numbers.
- A parallel run must give the same results as a serial one. No waiting loop without a timeout; no process left behind.

## 6. Convergence check

No number is used before its run passes all of these:

- The simulator's log has no convergence warning, no "time step too small", no aborted analysis.
- The run reached its end time.
- The plot looks physical: no jump that is not a stimulus, no current or voltage far outside what the circuit's resistances and supplies allow, no flat line where something should move.
- For fault tests, a hand estimate (charge balance, energy) agrees within a stated factor.

Usual cures: ramp ideal switches over a real time, give floating nodes a bleed resistor, add ESR and DCR, let supplies ramp instead of starting at full voltage. A run that did not converge has no result; fix the bench. If the usual cures do not make it converge, the test leaves the simulation list: write its row as UNKNOWN with a numbered bench test (`BT-nn`) and a numeric pass value, as for a part with no model, and list it at gate 1 for the user to accept. It is never a pass, and it does not stay in the table as "not converged".

## 7. Plots

One plot per test in `sim/out/`, named by the test ID (`sim-07.png`). Axes with units, the pass limit drawn as a line, markers at the events, the ID and the corner in the title, a second zoomed plot for fast events, readable in grey. Open every plot and write what you saw; a non-converged run showed itself on its plot before anyone used its numbers.

## 8. The results file

`sim/RESULTS.md` (from `templates/SIM_RESULTS.md`) names the netlist checksum, the date and the engine version. It holds, in this order:

1. The summary counts. "Not converged or not run" must be 0 at gate 1. Every test ever run is counted, the failed ones and the ones whose limit was corrected included.
2. Each result beside its limit, copied unchanged from the plan, with the plot file and the verdict; then the plot notes.
3. What the simulations changed in the design.
4. The deviations: those the user accepted, each with their words; those the designer ruled on, each with the reason; and every corrected limit, with the old test, the new test and the date the user was told.
5. The re-runs by reviewers, and whether they agreed.
6. What only the bench can prove.
7. The models: file, source and date.
8. The limits of the campaign: what the models do not represent.

A failed test that led to a design change stays in the table, followed by its re-run under a new ID (the next free `SIM-<nn>`). So does a test whose limit was corrected: its failed row is never removed from the summary.

## 9. What only the bench can prove

Every question no simulation can settle becomes a named bench test (`BT-<nn>`) with a numeric pass value. Typical items:

- layout parasitics, ringing and emissions;
- the loop's phase margin when the converter model is a stand-in (measured through the injection resistor);
- how third-party modules really behave: pin states at reset, rails at power-off, start-up current;
- negotiation with real sources, as a matrix of the sources the requirements name;
- load currents nobody has published;
- ESD with a real discharge;
- temperatures inside the enclosure;
- the RF line and connector on a network analyser, and sensitivity with real signals;
- anything the documents label as an inference.

## 10. Re-runs

- **By reviewers.** The circuit reviewer (the lean circuit reviewer, or the system reviewer and the coverage auditor where the depth switched them on) copies `sim/` to its own folder and re-runs a sample, adding harsher variants. Independent runs of the same test should agree within millivolts; if they do not, one of them is wrong.
- **After the fix round.** The full suite runs again on the final netlist; partial re-runs miss side effects.
- **After layout.** Add the resistance, inductance and capacitance of long power paths to the stability and fault tests and run them again.
