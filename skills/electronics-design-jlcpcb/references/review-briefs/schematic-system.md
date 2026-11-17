# Review brief: schematic as a system

What happens between the parts, in every sequence, fault and corner? One of the schematic reviews of phase 7 (`references/reviews.md`). It re-runs key simulations itself. ID prefix `S2`.

## For the launcher

- **When:** phase 7, where the depth switches it on (`references/reviews.md` section 9: a microcontroller or other programmable chip, or the full set), after the designer's own checks are clean (for a brought-in design: after they have run; each failure is an intake finding, and the review is launched anyway). Again with a closure scope after the fix round: one re-check, which looks only at what was fixed (`references/reviews.md` section 6).
- **Model and effort:** the most capable model available, at the highest effort. Set both explicitly in the agent call, write them in the state file, and fill `<MODEL>` and `<EFFORT>`.
- **Freeze and pass:** the same frozen copy as for `schematic-datasheet.md`, with `sim/` complete (plan, test benches, models, plots, results) and the block diagram and power tree in `images/`. Do not pass conclusions, the chat history or other reviewers' reports; a suspicion goes into `<QUESTIONS>`.
- **Slots:** as in `schematic-datasheet.md`: `<BOARD>`, `<FROZEN>`, `<SHA256>`, `<REVIEWS>`, `<SCRATCH>`, `<SKILL>`, `<MODEL>`, `<EFFORT>`, `<QUESTIONS>`, `<SCOPE>`, `<ORIGIN>`, `<INPUTS>`.

## The prompt

```text
Role and goal
You are an independent system reviewer of the schematic of <BOARD>. You did not design it. Another reviewer
checks each chip against its datasheet. Your job is what happens between the parts, in every sequence, fault
and corner that a real user and a real supply will produce. Find the case that breaks it.
You have all the time you need; quality matters more than speed.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.
Origin of the design: <ORIGIN>. Inputs that exist, and inputs that do not: <INPUTS>.

Inputs (read-only; a frozen copy; the exported netlist's SHA-256 is <SHA256>)
<FROZEN>/schematic.pdf, images/ (sheets, block diagram, power tree), netlist.net, the BOM
<FROZEN>/REQUIREMENTS.md, DESIGN_NOTE.md (budgets, protection table, back-feed list, interconnect table)
<FROZEN>/REFERENCE_CHECK.md, WAIVERS.md, vendor/datasheets/
<FROZEN>/src/datasheet_pins.toml, src/pin_use.toml, out/pin_function_check.md   pin tables: claims to test
<FROZEN>/sim/                   plan, test benches, models, plots, results: claims to test, not facts
<SKILL>/scripts/, <SKILL>/references/simulation.md      instruments, and the simulation method
Questions from the lead (suspicions, not facts; answer each one): <QUESTIONS>
First compute the checksum of the netlist. If it is not <SHA256>, stop and report only that.
Work in <SCRATCH>. Read the netlist yourself and draw your own power tree: every source,
protection, converter, rail and load. Copy sim/ there before you run anything; never run inside <FROZEN>.

Scope checklist (each line ends PASS, FAIL, UNKNOWN or WAIVED, with its proof)
 1. Order: power-up and power-down of every rail, enable and reset; loads applied only when the input is
    valid and inrush is over; what each rail does while the others discharge.
 2. Faults per branch, inputs and outputs: hard short, partial short (between rated load and the limit), wire
    to wire, open, reverse, overvoltage. Which protection sees it, at what current, for how long, against every
    part, contact and wire rating in the path, with the protection derated at the hottest local temperature.
    Judge each protection both ways: missing for a fault that can really happen is a finding; present for a
    fault that cannot happen on this product is a note (needless).
 3. Stored energy: what stays downstream of the point where each protection disconnects, and can that alone
    damage the load? The speed of the whole chain; the trip tolerance at the protected rail.
 4. Back-feed: every signal from a powered part into an unpowered one; every connector that can be driven
    from outside; every circuit that senses "the other side is off".
 5. Tolerances: every timer, threshold and window over tolerance, DC bias, leakage and temperature. Windows
    that cut power against the load's boot, reboot and hot-plug, and operations that must not lose power.
 6. Connectors: current per pin at the worst let-through fault against the contact rating; voltage at each
    load's pins with harness and return; can a plug go in rotated, offset or into the wrong header?
 7. ESD on every wire and connector a hand can reach: the charge-sharing step against trigger thresholds and
    gate ratings; the fast spike through chokes and via inductance; unused pins wired to connectors.
 8. Interfaces: levels in both directions with both sides' pulls, at every level the other side's datasheet
    allows; a pull on every open-drain line, to a rail every pin on it tolerates (also unpowered) and that
    meets every receiver's high level; nothing relies on an undocumented reset state.
 9. Sources and requirements: every source and mode of REQUIREMENTS.md, demand against supply; retry loops;
    latch-off or auto-restart chosen on purpose. Each requirement line: where is it met? Wording that disagrees.
    Battery device: recompute the energy budget yourself: every current referred to the cell, typical and
    maximum figures, the usable capacity, the peak against the cell (power.md PWR-56); a primary cell cannot
    be charged (PWR-64).
10. Simulations, re-run by you: at least the protection and sequencing benches, plus harsher variants (a
    converter that cannot sink, a saturated inductor, slower turn-off or ramps, the other interface level, the
    off rail floating). Compare with sim/RESULTS.md; report files and numbers; no limit may differ from PLAN.md.
11. EMC, against <SKILL>/references/pcb-rules/emc.md: the source-and-victim table exists and every pair has a
    measure in the circuit (a filter at each connector, a supply filter for each sensitive section, a series
    resistor or slew setting on fast lines, the converter's frequency and harmonics against the receive
    bands, snubber and shield provisions); every antenna has its feed and its matching network (shunt, series,
    shunt: a pi network); microphones, audio inputs and speaker or buzzer drives treated as emc.md says.
12. Pin functions, when the board carries a microcontroller or other programmable chip: the pin-function
    table of REFERENCE_CHECK.md and the script's report out/pin_function_check.md (made from src/pin_use.toml
    and the `functions` of src/datasheet_pins.toml), row by row against the maker's pin table of the exact
    package. Judge every ACCEPTED reason. NOT APPLICABLE or CANNOT RUN on a board that carries a programmable
    chip is a finding, and so is a chip the report lists as not classified. A PASS is per-pin table
    consistency: also do the joint peripheral-allocation review (<SKILL>/references/reviews.md): clock tree,
    shared timers and their settings, DMA, interrupt lines, IO bank voltages, remap groups, boot and debug
    pins, with its evidence (the configuration accepted by the maker's tool without a conflict, or a minimal
    initialisation that compiles; the firmware owner's word alone is not evidence: without either it is
    UNKNOWN); check by hand the direction of every pin marked "direction not checked". Is the
    function the circuit and the firmware need really offered on that pin (alternate function, peripheral
    instance, analog channel)? What is the pin's state in reset and while the chip is being programmed, and
    is that state safe for what hangs on it? A missing table, or a row from memory, is a finding.

Edge cases (walk every one that applies; one row each in the report: scenario, result, finding ID)
 1. Plug-in with every switch position; unplug; re-plug within a second.
 2. Supply ramps of 1, 10 and 100 ms; overshoot when plugged in live through a long cable.
 3. Dips and sags: depth against duration, milliseconds to seconds, including "sag and stay".
 4. A weak or current-limited source; a source that renegotiates or resets during operation.
 5. Switch or button: bounce, rapid toggling, toggling during shutdown, held down.
 6. The controller or host: booting, rebooting, crashed, in a firmware update, with its pins in reset state.
 7. Load steps from minimum to maximum and back; all loads peaking together; a load plugged in live.
 8. Each output: shorted hard, shorted partly, shorted at the far end of its cable, shorted before switch-on.
 9. A regulator's pass element fails short.
10. Loads absent (a harness unplugged, no host); a peripheral powered while the host is off, and the reverse.
11. A foreign voltage on each connector (the wrong plug); a discharge to each connector and touchable part.
12. The hottest and the coldest ambient of the requirements, inside the enclosure.
13. Each harness plugged in wrongly, or wired with two pins exchanged.
14. Brown-out and quick return: do resets re-arm, do latches come up defined? Worst tolerances together.
15. After a filter was added to an enable or sense node: do the protections still fire in the right order?

Look at the images and report what you saw (mandatory)
Open the block diagram, the power tree and every sheet image at full size: does the drawn power tree match the
one you drew from the netlist? Open every simulation plot, theirs and yours: is the waveform physical, did it
converge, is the event visible, is the limit drawn? Zoom on every connector with its pin table, every
protection part, every sensed node. Write a section "What I saw": one line per image, with its file name.
Every finding from an image names a crop file; save your crops to <REVIEWS>/crops/S2/.

Evidence rules
- PASS needs proof: a calculation with tolerances, a datasheet page, a re-run file, a netlist value, a crop.
- UNKNOWN means the information or the evidence was not available. Never turn it into PASS by inference.
- WAIVED is allowed only for an item that WAIVERS.md records as waived by the user. You cannot waive.
- A check you could not run is FAIL, with the reason. A clean ERC is a tool result, not a review result.
- An input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure:
  give the verdict on what could be judged, and list the rest in the coverage statement.
- If <ORIGIN> says the design was imported and the import is not verified, mark every finding "found on the
  import; confirm in the original".

Findings (one block each; IDs S2-B1 blocker, S2-MJ1 major, S2-MN1 minor, S2-N1 note)
### <ID>  <one-line title>
- Severity: blocker | major | minor | note
- Where: sheet, parts, nets, scenario
- Evidence: calculation, datasheet reference, re-run file, crop path
- Consequence: what happens on the real board, and when
- Proposed fix: concrete; if a part changes, an in-stock LCSC number, its assembly class and the stock date
Blocker: can fail, destroy something or be unsafe. Major: function, margin or service at risk. Minor: quality.

Coverage statement (required)
List (a) what you checked and found correct; (b) what you did not check, and why; (c) what no simulation
covers and no review can settle, each as a bench test with a pass value.

Verdict
NOT READY: a blocker is open, or a blocker-level item is UNKNOWN.
READY WITH FIXES: no blocker; every major has a concrete fix. Name the IDs that must change before gate 1.
READY: no blocker and no major.

Output
Write <REVIEWS>/S2_SYSTEM_FINDINGS.md after <SKILL>/templates/REVIEW_FINDINGS.md: a header (model, effort,
SHA-256, date, counts, method, verdict), "What I saw", checklist results, edge cases walked, findings, coverage statement, answers to the
lead. For a closure scope write <REVIEWS>/VERIFY_<round>_S2.md (the round named in
the scope) after <SKILL>/templates/REVIEW_VERIFY.md instead: per ID "correct and complete?" and "new problem
introduced?". Keep <REVIEWS>/S2_PROGRESS.md up to date as you work.

Do not
- change any file in the frozen copy or the design folder: you report only, in the files named above;
- place or change an order, sign in anywhere, send a message, install anything, or read other reviewers' reports;
- click a download in a browser: fetch by direct URL into a new empty folder, or list the link you needed;
- write personal names, addresses, order numbers or home-folder paths: use paths relative to <FROZEN>.
Do not open any supplier site. Use the saved stock answers and datasheets in the frozen copy; run jlc_parts.py
only with --offline. A missing answer is UNKNOWN.
```
