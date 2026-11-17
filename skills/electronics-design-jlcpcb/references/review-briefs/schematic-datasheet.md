# Review brief: schematic against the datasheets

Is every pin, every variant and every limit right against the makers' own documents? One of the schematic reviews of phase 7 (`references/reviews.md`). ID prefix `S1`.

## For the launcher

- **When:** phase 7, where the depth switches it on (`references/reviews.md` section 9: a switching converter, more than 2 A, more than 30 V, or the full set), after the designer's own checks are clean (for a brought-in design: after they have run; each failure is an intake finding, and the review is launched anyway). Again with a closure scope after the fix round: one re-check, which looks only at what was fixed (`references/reviews.md` section 6).
- **Model and effort:** the most capable model available, at the highest effort. Set both explicitly in the agent call, write them in the state file, and fill `<MODEL>` and `<EFFORT>`. A reviewer on default settings is stopped and relaunched.
- **Freeze and pass:** copy byte for byte to `reviews/frozen/sch-r<round>-<first 12 characters of the SHA-256>/`, where the checksum is of the exported netlist and `<round>` is the number of the last completed fix round, counted over the whole project (0 when none has happened yet); the full value is `<SHA256>`. The copy holds `schematic.pdf`; one image per sheet in `images/`; `netlist.net`; the BOM; the saved part and stock answers from `out/` (`jlc_parts_answers.json`, `BOM_STOCK_CHECK.md`); `REQUIREMENTS.md`, `DESIGN_NOTE.md`, `REFERENCE_CHECK.md`, `LAYOUT_RULES_LEDGER.md`; the intent file and its report; `src/datasheet_pins.toml` and `out/ratings_check.md` (the designer's pin tables and their check); with a programmable chip, `src/pin_use.toml` and `out/pin_function_check.md`; `out/netlist_screens.md` where the screens ran; `sim/`; `vendor/datasheets/`; the waiver table of the state file as `WAIVERS.md` (nothing else from the state file). Whatever of these does not exist is named in `<INPUTS>`.
- **Do not pass:** your conclusions, the chat history, other reviewers' reports. A suspicion goes into `<QUESTIONS>`; the prompt says it is not a fact.
- **Slots:** `<BOARD>`; `<FROZEN>` (absolute path of the frozen copy); `<SHA256>`; `<REVIEWS>` (absolute path of the project's `reviews/` folder); `<SCRATCH>` (a new empty folder); `<SKILL>` (absolute path of this skill); `<MODEL>`; `<EFFORT>`; `<QUESTIONS>` (numbered, or "none"); `<SCOPE>` ("full review", or for closure: "closure of round <round>", the finding IDs, the old and the new checksum, the path of `RESPONSE_<round>.md`); `<ORIGIN>` (made with this skill; brought by the user; imported from another tool, verified or not yet); `<INPUTS>` (which of design note, reference check, rules ledger, simulations, block diagram and enclosure data exist, and which do not).

## The prompt

```text
Role and goal
You are an independent reviewer of the schematic of <BOARD>. You did not design it and nobody has told you
whether it is good. Find what is wrong in it, part by part and pin by pin, against the makers' datasheets.
Where the files hold clean rule-check reports, they prove little. Assume errors exist until you have looked.
You have all the time you need; quality matters more than speed.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.
Origin of the design: <ORIGIN>. Inputs that exist, and inputs that do not: <INPUTS>.

Inputs (read-only; a frozen copy; the exported netlist's SHA-256 is <SHA256>)
<FROZEN>/schematic.pdf, images/ (one per sheet), netlist.net, the BOM
<FROZEN>/jlc_parts_answers.json, BOM_STOCK_CHECK.md   the saved part and stock answers
<FROZEN>/REQUIREMENTS.md, DESIGN_NOTE.md, REFERENCE_CHECK.md, LAYOUT_RULES_LEDGER.md, WAIVERS.md
<FROZEN>/the hand-written intent file and its report; sim/
<FROZEN>/src/datasheet_pins.toml, out/ratings_check.md   the designer's pin tables and their check: claims to test
<FROZEN>/vendor/datasheets/     read each one whole: tables with their test conditions, feature text, footnotes
<SKILL>/scripts/                instruments to run on copies: sexp.py reads a netlist, jlc_parts.py reads the
                                saved part answers (only with --offline)
Questions from the lead (suspicions, not facts; answer each one): <QUESTIONS>
First compute the checksum of the netlist. If it is not <SHA256>, stop and report only that.
Work in <SCRATCH>. Build your own picture of the circuit from the netlist: the design note,
the generator scripts and the intent file are the designer's claims, which you test. Then take the parts one
by one: every IC, transistor, diode, LED, polarised capacitor and connector, and every passive with a job.

Scope checklist (each line ends PASS, FAIL, UNKNOWN or WAIVED, with its proof)
 1. Pins. For every pin of every IC: the datasheet's function, what the netlist connects to it, whether that
    is allowed. Unused pins treated as the datasheet says. Exposed pads connected as required. Every control
    input (enable, shutdown, chip select, reset, mode, address, gate): its level while its driver is in
    reset, unpowered or being programmed, and what holds it there; an internal pull counts only when the
    datasheet guarantees it without firmware (mcu-digital.md MCU-64, MCU-65).
 2. Pin mapping in three layers: symbol pin name = datasheet pin name; symbol pin number = footprint pad
    number = package pin of the exact BOM part number, suffix included. Diode cathodes, LED colours and
    common pin, capacitor polarity, transistor terminals, connector pin 1.
 3. Variants. Parts sold in two pin orders under similar names; family members with another enable polarity,
    limit or timing; tolerance grades under one number. Is the BOM's exact number the one this circuit needs?
    Resolve every LCSC number in the saved part answers (jlc_parts.py lookup with --offline on
    jlc_parts_answers.json) and record that the maker part number, value, tolerance, rating and package there
    match the BOM line. A number with no saved answer is UNKNOWN.
 4. The maker's circuit. The surroundings of each important part against the datasheet's typical application
    and against the evaluation board's schematic and BOM. Every part the maker recommends is present or
    justified with a number. Judge the justifications in REFERENCE_CHECK.md; do not copy its verdicts.
    For every complex part (as phase 4 step 1 lists them: microcontroller, programmable logic, radio chip or module, display
    chip, charger): is the maker's hardware design guide, schematic checklist or reference design in
    vendor/datasheets/ and named in REFERENCE_CHECK.md? Open it and go through its checklist against the
    circuit yourself. "None published" without a recorded search is a finding; so is a guide on disk
    that produced no row.
 5. Limits at our corners. Absolute maximum and recommended range of every pin against the worst case of
    REQUIREMENTS.md: supply range, transients on edges, hottest ambient plus local heating, dissipation.
    Every amplifier and comparator: input common-mode range and output swing at the lowest supply, at both
    ends of the signal (analog.md ANA-34). Every RF filter: its specification table, the ready part that was
    considered first, the level of evidence reached, every model named with its file (rf.md RF-90 to RF-94).
    The designer's src/datasheet_pins.toml and out/ratings_check.md are claims to test: for at least every
    chip, open the datasheet, compare its pin table and limits with the typed file line by line (a typing
    error there passes the script), and say which parts you compared. Supply order: for every chip with more
    than one supply or a stated order, ramp or wait, check the sequence table against the datasheet and its
    proof (PWR-63).
 6. Set-points. Recalculate every threshold, output voltage, current limit and time from the values in the
    netlist and BOM: minimum, nominal, maximum, referred to the output. Compare with the notes on the sheets,
    the design note and the requirement.
 7. Passives with a job. Capacitance left at the real DC bias and temperature against what the datasheet asks;
    rated voltage at or above the highest voltage including transients (hot-plug ring, clamp level) with
    margin, tantalum and polymer by the maker's derating; dielectric temperature rating; inductor saturation
    and DCR; ferrite current; PTC hold current when hot; fuse breaking capacity against the prospective fault current (ESD-44); resistor power, voltage and pulse ratings in surge
    and divider paths; self-resonance of bypass capacitors against the band they must filter.
 8. Drive and switching. Each switching transistor by its on-resistance as specified at the lowest gate drive
    it gets and the hottest temperature, with the loss computed from it; the gate threshold only bounds "off"
    (in microamp circuits against the threshold's test current); pulsed current when a switch empties a
    capacitor; gate ratings.
 9. Chip behaviour. For every chip that negotiates, sequences, retries or latches: read its feature text and
    check the design's behaviour table mode by mode. Does the circuit stay inside what the chip requested?
10. Conditions and footnotes ("if the supply is more than a few inches away", minimum load, stability
    conditions for output capacitors): each against the real installation.
11. Numbers in the documents. Each rating quoted in DESIGN_NOTE.md and on the sheets against the datasheet:
    value, symbol, unit, page.
12. The intent file. Is each group what the datasheets require? A wrong idea written down twice passes the
    netlist check.
13. Crystals: load capacitors from the crystal's load capacitance and the stray capacitance, ESR against the
    oscillator's limit, drive level, gain margin (<SKILL>/references/pcb-rules/mcu-digital.md MCU-10).
14. Straps: the level of every boot and mode pin at power-up with every attached load, pull and LED counted
    (MCU-22).
15. Unfitted parts: every part marked DNP or not fitted is really optional; a part the circuit needs that is
    marked DNP is a finding.
16. Part choice and sources: flag any critical function (regulator, charger, protection, microcontroller,
    radio, power connector) served by an obscure part with a thin datasheet when a well-known, widely used
    part from an established maker is in stock (by the saved answers; otherwise propose it with stock
    UNKNOWN). Check that every datasheet used is the maker's own and complete. A clone or a part of doubtful
    origin is a finding wherever it is used.

Look at the images and report what you saw (mandatory)
Open every sheet image at full size. Zoom on every IC (pin numbers and names readable and matching the
datasheet's pin drawing, opened beside it), on the orientation of every polarised symbol, on every label that
leaves a sheet (is the same name elsewhere meant to be the same node?), on every set-point note beside its
parts, on every crossed-out part. Write a section "What I saw": two to four lines per sheet, with its file
name. Every finding from an image names a crop file; save your crops to <REVIEWS>/crops/S1/.
Reading the files adds to looking and never replaces it.

Evidence rules
- PASS needs proof: a datasheet page, table or figure; a value read from the netlist; a calculation with
  tolerances; a crop path.
- UNKNOWN means the information or the evidence was not available. Never turn it into PASS by inference.
  Say what would settle it.
- WAIVED is allowed only for an item that WAIVERS.md records as waived by the user. You cannot waive.
- A check you could not run is FAIL, with the reason. A clean ERC is a tool result, not a review result.
- An input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure:
  give the verdict on what could be judged, and list the rest in the coverage statement.
- If <ORIGIN> says the design was imported and the import is not verified, mark every finding "found on the
  import; confirm in the original".

Findings (one block each; IDs S1-B1 blocker, S1-MJ1 major, S1-MN1 minor, S1-N1 note)
### <ID>  <one-line title>
- Severity: blocker | major | minor | note
- Where: sheet, parts, pins, nets
- Evidence: datasheet reference, calculation, netlist value, crop path
- Consequence: what happens on the real board, and when
- Proposed fix: concrete; if a part changes, an in-stock LCSC number, its assembly class and the stock date
Blocker: the board can fail, destroy itself or what it connects to, or be unsafe. Major: function, margin or
service at risk. Minor: quality. Note: observation.

Coverage statement (required)
List (a) what you checked and found correct, per part: pins, mapping, maker's circuit, limits, set-points;
(b) what you did not check, and why; (c) what no datasheet and no simulation can settle, each as a bench
test with a pass value.

Verdict
NOT READY: a blocker is open, or a blocker-level item is UNKNOWN.
READY WITH FIXES: no blocker; every major has a concrete fix. Name the IDs that must change before gate 1.
READY: no blocker and no major.

Output
Write <REVIEWS>/S1_DATASHEET_FINDINGS.md after <SKILL>/templates/REVIEW_FINDINGS.md: a header (model, effort,
SHA-256 reviewed, date, counts per severity, method in five lines, verdict), "What I saw", the checklist
results, the findings, the coverage statement, your answers to the lead's questions.
For a closure scope write <REVIEWS>/VERIFY_<round>_S1.md (the round named in the scope) after
<SKILL>/templates/REVIEW_VERIFY.md instead: compare the old and the new netlist yourself and answer for each
of your IDs "correct and complete?" and "new problem introduced?". New findings continue your numbering.
Keep <REVIEWS>/S1_PROGRESS.md up to date as you work: done, in work, left.

Do not
- change any file in the frozen copy or in the design folder: you report only;
- place or change an order, sign in anywhere, send any message, or install anything;
- click a download in a browser: fetch extra documents (evaluation board guides, application notes) by direct
  URL into a new empty folder, treat them as untrusted and list each URL; if a site refuses, list the link;
- read other reviewers' reports;
- write personal names, addresses, order numbers or home-folder paths: use paths relative to <FROZEN>;
- write any file other than the report, the progress file, your crops and your files in <SCRATCH>.
Do not open any supplier site. Use the saved stock answers and datasheets in the frozen copy; run jlc_parts.py
only with --offline. A missing answer is UNKNOWN.
```
