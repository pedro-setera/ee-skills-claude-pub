# Phase 3: part selection

Choose every part with an exact orderable number, worst-case margins, live stock and a cost model.

## Inputs

- `DESIGN_NOTE.md`: budgets, protection table, interconnect table.
- `REQUIREMENTS.md`: cost target and ranking, quantity, environment; `references/working-rules.md` sections 11 and 12 (quality first, then cost; just enough, and simple).
- `references/jlcpcb/parts-library.md` and `references/jlcpcb/assembly.md` (dated facts; re-read the live page before relying on a number).
- `scripts/jlc_parts.py`, `scripts/fetch_parts.py`.
- `references/lessons.md`, section "Phase 3: part selection".

## Steps

1. For each block, write the selection criteria before searching: voltage, current at peak, tolerance, temperature range, package. Then list candidates. Criteria written afterwards tend to fit the part already liked.
2. Choose in this order of preference:
   - (a) well known: widely used for exactly this job in this kind of product, from an established maker, with a complete datasheet, an application circuit and preferably an evaluation board or many published designs;
   - (b) in stock at LCSC and in JLCPCB's assembly stock in healthy quantity, with a normal life-cycle status;
   - (c) basic library, then preferred, then extended: each extended line costs a fee per order, so replace it by a basic part whenever an equally good and dependable one does the job, and justify each extended line that stays;
   - (d) price (`references/working-rules.md` section 11): among parts that are well known, from an established maker, genuine, in stock and equally dependable, the cheaper one. Never a clone, a no-name part or a part of doubtful origin, and never a part chosen for being the cheapest when it is less dependable. No specification beyond the requirement plus its proper margin and derating (the usual margins below): the margin is quality and stays; state it.
   An obscure part with a thin datasheet is not used for a critical job (regulators, chargers, protection, microcontrollers, radios, connectors that carry power) when a well-known one is in stock, even if it is cheaper. For jellybean passives and simple discretes any basic-library part with a proper datasheet will do. Say why for every key part in the BOM notes ("the usual choice for ..."), with its price and "a cheaper way to the same quality: found (which) / none found".
2b. **Find the LCSC number of each candidate with the search of `scripts/jlc_parts.py`**, never from memory: `python -I scripts/jlc_parts.py --project <board folder> --live search <maker part number> "<words>" ...` (one text per argument, a text of several words in quotes; result `out/parts_search.md`). A number from memory is not a source: it is searched or looked up before it is written anywhere.
   - Each text is one paced request and reads the first results only. Every result is saved, so the look-up of a number found today costs no second request to JLCPCB.
   - To hunt for a cheaper basic part of a known value and package (common resistors and capacitors above all), first ask the community copy of the parts list, which costs no request at JLCPCB: `python -I scripts/jlc_parts.py --project <board folder> --live candidates --category resistors --package 0402 --value 10k --basic-only`, or for other parts `candidates "100nF 0402" --package 0402 --basic-only` (result `out/jlc_candidates.md`). Its rows are CANDIDATES from a copy kept by others, not confirmed: before a number enters the BOM, `lookup` it at JLCPCB (class, both stocks, price; saved in `out/jlc_parts_answers.json`, the reviewers' only source) and let its datasheet decide. The copy's stock is no stock figure, and an empty candidate list proves nothing: then use `search`. It is an outside host like the supplier's: the user's yes to live look-ups covers it only if it was named, and the same pace and the same stop apply.
   - Search by the full maker part number first. Search by words (`"100k NTC 0603 1%"`) where the criteria of step 1 leave the maker open, and choose among the results in the order of step 2.
   - A result is a candidate, never a choice: its datasheet (phase 4) and the match of step 13 decide.
   - Where the user limited the look-ups, list the texts first, the parts that decide the design first, and count: each new text is one.
   - Never write a search script of your own and never page through the catalogue: a script of your own has no shared pace, and a block falls on the user's address. Where the search does not find a part, change the text (the part number without its packing suffix, an equal part of another established maker); if that fails too, ask the user to search on the supplier's parts page, with the exact text to type and what to send back (the number that starts with C, basic or extended, the stock).
3. Check the stock that will really supply the part: JLCPCB's assembly stock for parts the assembler places, LCSC's retail stock for hand-fitted and off-board parts. The two numbers differ for the same part. Record both with the date and time.
   - Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8). Search and look parts up through `scripts/jlc_parts.py`, which paces its requests and saves every answer for reuse; never a parallel fan-out.
4. Compute the need per line: boards times quantity per board, plus attrition and spares. A line with less than about ten times the need in stock is thin: name an in-stock alternate for it now.
5. Check the life cycle of every line, off-board parts included: reject "not recommended for new designs", end-of-life and non-catalogue parts, also for a prototype. A prototype built on a dying part is redesigned before it is sold.
6. Lock the exact variant: the full part number with its suffix for package, grade, pin-out, output voltage and enable polarity. Before calling anything a drop-in, read the family comparison table.
   - LEDs and arrays: common anode or common cathode, against the way the circuit drives them.
   - Look-alike pin-outs: some small regulators, references and transistors exist in two pin orders under near-identical names. Check the pin order of the exact number.
   - Grades: where two tolerance grades are sold under one part number, confirm the grade with the distributor or design for the worse one.
6b. **Check that the part suits the assembly process,** only where it matters, from its datasheet: the soldering it allows (reflow, wave, by hand); its moisture sensitivity level and floor life; its allowed number of reflow cycles; its peak temperature (some connectors, batteries, modules and displays do not stand reflow: take the reflow-rated variant, or fit it by hand); whether it may be washed; and for hidden joints (pads under the body, leadless or ball-grid packages) how they are inspected and reworked. Note it in the BOM notes; phase 12 checks it against the assembler (`references/jlcpcb/assembly.md` section 14).
7. Select for the worst case, not the typical one, with the usual margins of the table below (`references/working-rules.md` section 12: just enough, and simple):
   - Current limiter: its minimum limit must exceed the worst load current with margin, and its maximum limit must stay within the connector and wire rating. A load nobody measured is bounded from vendor data and goes on the bench list.
   - PTC: the hold current at the hottest local temperature must cover the load's peak; the trip current must stay within the contact rating. Size each PTC to its own load, not to a line already in the BOM; its maximum voltage and fault current and its tripped-state current (ESD-45).
   - Timers: a long timeout on a leaky RC spreads with threshold tolerance, capacitor tolerance, DC bias and leakage at high temperature. Use a counter or an oscillator.
   - Capacitors: the effective value at the real DC bias and temperature; the dielectric's temperature rating against the local temperature; a rated voltage at or above the highest voltage the part sees, transients included (a hot-plug ring, the clamp level of the protection ahead of it), with margin; tantalum and polymer parts derated as their maker says. Resistors in surge and divider paths: their voltage and pulse ratings.
   - Transistors used as switches: chosen by the on-resistance specified at the lowest gate drive and the hottest temperature, with the loss computed from it. The threshold voltage only bounds "off", and its minimum at the datasheet's test current is no "off" guarantee at microamps. Check the pulsed current when a switch empties a capacitor.
   - TVS: the standoff voltage at or above the highest continuous voltage with tolerance, never set from transients; the clamp voltage at the real transient current against the downstream ratings as `references/pcb-rules/protection-esd.md` ESD-21 sorts them (sustained and surge: the absolute maximum; ESD: the pin's pulse level or the maker-qualified pair).
   - Linear regulators (`references/pcb-rules/power.md` PWR-54): the lowest voltage at the input pin (the source minimum less every drop ahead of it) minus the maximum dropout at full load and the hottest temperature stays at or above the output the load needs. After a switching converter, compare the ripple rejection at the switching frequency with the ripple allowed on the rail.
   - Switching converters (PWR-52, PWR-53): the shortest on-time (for a buck Vout / (Vin,max x f)) stays above the part's minimum on-time, and the duty at the lowest input below its maximum duty; the highest input, transients included, below the absolute maximum; compensation computed where it is external; ripple injection where a constant-on-time or hysteretic part runs on ceramic output capacitors only; capacitor ripple-current ratings against the computed ripple; the inductor as PWR-08 says.
   - Battery cells and chargers: as PWR-55, PWR-57, PWR-58 and PWR-64 say (cell protection, charge current, power path).
   - Temperature grade: from the air at the part (`references/pcb-rules/thermal.md` THM-02) plus a margin; industrial where that passes about 60 C or is not known.
   - Amplifiers and comparators: the input common-mode range and the output swing at the lowest supply, against both ends of the signal (`references/pcb-rules/analog.md` ANA-34).
   - Switches used for signals: the minimum current the contacts need.
   - Ratings against the peak, including the gain spread of anything that amplifies. The average on a label is not a rating.
8. Consolidate values to cut the number of lines, with one firm exception: any part whose value may change gets its own BOM line, even when it is the same part as its neighbours. That covers set-point resistors, pull-ups and series resistors in interfaces to parts not fully documented, and tuning parts. Make these lines now: a shared line can only be changed or left out as a whole after the order, and a split after gate 1 needs the user's go.
9. Make everything a BOM line: unfitted positions, parts the user fits by hand (marked as not assembled and bought with the off-board parts), connectors' mating housings and crimps, wire, screws, standoffs, heat sinks and fans with their fixings and thermal pads, and consumables such as foam, gasket, tape and thermal pads, each with source, price and how it is made. Mark lines "buy now" or "BOM only" when the user defers a purchase.
10. Give every line its exact LCSC number, the maker's part number, a link, the class, and the path of its datasheet. A recommendation without the LCSC number is not usable: the user must be able to find the part.
11. For a second source (an equivalent part from another established maker; never a clone or a part of doubtful origin), compare the tables that matter (for a clamp: the clamping curve and derating) and the footprint before accepting it.
12. Build the cost model and show what drives the cost:
    - per-part cost apart from per-order fees (setup, stencil, the fee per extended line, hand-soldered joints, shipping, tax);
    - totals with and without tax, at the sample quantity and at a volume quantity;
    - both price paths when through-hole parts or a second side could move the order from economic to standard assembly;
    - attrition and minimum order quantities;
    - small-order fee thresholds at the retailer: round a quantity up when the extra parts cost less than the fee they remove.
13. Run the BOM stock check, `python -I scripts/jlc_parts.py --project <board folder> --live bom-check <board folder>/out/<the BOM>.csv --boards <n>` (every option of the script stands before the word `bom-check`; only the sub-command's own options, such as `--boards`, stand after it; `--help` shows the arguments), for the planned number of boards plus spares, paced as in step 3. No netlist exists yet, so give the phase 3 BOM file as the argument; do not set `[bom] file` in `board.toml` for it, or it would shadow the netlist from phase 5 on. Exit code 2 means it could not run: read the message; when it says the site refused, stop all access and tell the user. Keep its dated report `out/BOM_STOCK_CHECK.md`. Run its line audit, `python -I scripts/jlc_parts.py --project <board folder> line-audit <board folder>/out/<the BOM>.csv` (result `out/bom_line_audit.md`): it flags every line shared by several designators and every fitted part without an LCSC number and a maker part number. Act on every flag. Both save every live answer to `out/jlc_parts_answers.json`: the reviewers may not use the supplier's site and resolve every LCSC number from that file, so a number with no saved answer is UNKNOWN to them. Then look up every LCSC number on the assembler's part page (the saved answers) and record that its maker part number, value, tolerance, rating and package match the BOM line: a wrong variant in the right package passes every footprint check.
14. Fetch each datasheet now, by direct URL, with `scripts/fetch_parts.py`, at the same pace. Phase 4 reads them. Take the sources in the order of `references/working-rules.md` section 7, each with one call of the script into a new folder:
    - (1) the maker's own document. Many makers' sites refuse a script: that is a refusal, never worked around; go on.
    - (2) LCSC's copy: the link is `datasheet` in `out/jlc_parts_answers.json`, listed by `jlc_parts.py lookup`. The script follows the supplier's forwarding or viewer page to the file.
    - (3) another authorised distributor's copy: search for the exact part number and take a direct link to the file on the distributor's own site.
    - (4) the Internet Archive's copy of the maker's file: `python -I scripts/fetch_parts.py datasheet "https://web.archive.org/web/2id_/<the maker's link>" <new folder>`.
    - (5) the user, only when none of these gives the document: every link in one message, and the folder to save into.
    Never a datasheet-collector site. Whatever the source, check on the first page that it is the maker's document for this exact part number, and note its revision and date and where the file came from: a copy can be old or of a sister part. Exit code 1 of the script (a page instead of the file, an address that does not exist) means "next source"; exit code 2 with a refusal means that host is left alone. For the key chips and every module, look now for the maker's hardware design guide and reference design (`references/phases/04-datasheets.md`, step 1): a complex part whose maker publishes none, or whose documents cannot be had, is a weaker choice than an equal part that is well documented, and that is a reason to choose the other.
14b. **The cost check: show the user the priced parts list.** The parts decide the price of a board far more than the bare PCB does, so the user sees it before the schematic, the simulations and the reviews are spent on the design. Show, in plain words: every BOM line with its unit price at the sample quantity and its line total, the dearest lines first (`out/BOM_STOCK_CHECK.md`); the parts cost per board at the sample quantity and at the later quantity; the per-order fees apart; a first estimate of the whole order (boards, assembly, shipping, tax), marked as an estimate; all of it against their target; and for the three dearest lines whether a cheaper way to the same quality exists. If the cost is within the target the user confirmed at gate 0, send it as information and go on; they can stop you. If it is above the target, or no target was given (a class without a figure counts as no target), stop and ask for their go, with the options (`references/working-rules.md` section 11): a cheaper way to the same quality, fewer features, a named limitation, or the higher cost. Never lower quality quietly. Record the figure and the user's words in the state file. The user's agreement to the final figure is part of gate 1.
15. Write the BOM summary and the cost into `DESIGN_NOTE.md`. Stock is checked again at every gate and on the order day; say so in the state file's next actions.

### Usual margins (starting points; the part's datasheet or its maker's derating guide overrules; less than this needs a reason, and so does much more)

| Part | Margin | Note |
|---|---|---|
| Ceramic capacitor | Rated voltage about 2 x the working voltage where size allows, at least 1.5 x | Capacitance checked at that DC bias |
| Aluminium electrolytic | Rated voltage at least 1.25 x the working voltage | Ripple current within its rating at temperature |
| Tantalum (manganese dioxide) | Rated voltage 2 x the working voltage | Polymer types by their maker's guide |
| Resistor | At most about 50 to 60 % of rated power at the hottest ambient | Its voltage rating respected |
| Discrete diodes and transistors | At most about 80 % of the rated voltage (reverse, drain-source, collector-emitter, gate), transients included; about 70 to 80 % of rated current | Junction as `references/pcb-rules/thermal.md` THM-04; a TVS standoff by ESD-20 |
| ICs | Steady state and every repeated switching edge inside the recommended operating range at the worst supply tolerance; one-off transients (hot plug, surge, a fault) below the absolute maximum (the maker's own gap between the two is the margin); about 70 to 80 % of rated output current | Junction as THM-04; checked pin by pin by `scripts/ratings_check.py` |
| Inductor | Saturation current above the converter's peak current, as its datasheet asks | PWR-08 |
| Connector contact | The normal peak at most about 70 to 80 % of its rated current | The worst sustained let-through fault of phase 2 stays within the rating at temperature (`references/pcb-rules/connectors-mechanical.md` MECH-23) |
| Fuse or resettable fuse | Hold current about 1.25 to 1.5 x the highest normal current at the hottest ambient | It must still open on the fault, and break the prospective fault current at the circuit's DC or AC voltage (ESD-44) |
| Regulator | Load at most about 70 to 80 % of its rating | With the heat computed |
| Copper | By the current worksheet | Phase 9 |

## Questions for the user

None by default. Part choices are yours to make; record each non-obvious one as an assumption the user can veto. Ask only in these cases:

- No in-stock part meets a requirement. `<Requirement>` cannot be met as written; which way should it give?
  - Suggested: `<the cheaper relaxation, with its effect>`.
  - Why: this re-opens a line of the requirements page, which the user owns.
- (Cost check, step 14b; always shown, asked when above the target or when no target was given) The parts for one board cost `<x>` at `<5>` boards and `<y>` at `<100>`; the whole first order is about `<z>` (estimate). Go ahead at this cost?
  - Suggested: `<yes | the cheaper option, with what it changes>`.
  - Why: the parts are most of the price; this is the moment to stop or change course cheaply.
- A part breaks the price position or forces standard assembly. Accept `<part>` at `<extra cost>`?
  - Suggested: `<yes | a cheaper way to the same quality, if one was found>`.
  - Why: it changes the cost of every order.
- (A design the user brought) `<part>` has no identical in-stock part at LCSC. Use `<equivalent>`, which differs in `<what>`?
  - Suggested: `<yes, with the comparison of step 11 | no: buy the part apart and fit it by hand>`.
  - Why: a part that is not identical changes their design; that is theirs to accept.

When the user proposes a part, run the same checks on it (variant, pin-out, stock, life cycle) before accepting it, and report what they showed.

## Checks before leaving this phase

- [ ] Every BOM line has an LCSC number, a maker part number, a link, a class and a datasheet path. Evidence: the BOM file in `out/`; `out/bom_line_audit.md` with no fitted part missing a number.
- [ ] Every LCSC number resolves on the assembler's part page to the BOM line's maker part number, value, tolerance, rating and package. Evidence: the match column of the BOM; `out/jlc_parts_answers.json` holds an answer for every number.
- [ ] Every key part says why it was chosen, with its price and whether a cheaper way to the same quality was found; no part is specified beyond its requirement plus its stated margin. Evidence: the BOM notes.
- [ ] The stock report is dated today; assembled parts are checked against assembly stock, hand-fit and off-board parts against retail stock; every line covers the need with attrition. Evidence: `out/BOM_STOCK_CHECK.md`.
- [ ] Every thin line has a named in-stock alternate. Evidence: the report's notes.
- [ ] No line is flagged not-for-new-designs, end-of-life or non-catalogue. Evidence: the life-cycle column.
- [ ] Every extended line is justified or replaced. Evidence: the justification column; the count of extended lines.
- [ ] Every polarised or multi-variant part has its variant checked against the circuit. Evidence: the variant column with the datasheet page.
- [ ] Every part with a process limit (soldering, moisture level, reflow cycles, heat, washing, hidden joints) has it noted. Evidence: the BOM notes.
- [ ] Each limiter (minimum and maximum), each PTC (hot hold and trip), each timer, each DC-biased capacitor, each capacitor's rated voltage, each switch transistor's loss, each TVS's standoff and clamp, and each regulator's dropout or on-time limit has a computed margin. Evidence: the calculation rows in `DESIGN_NOTE.md` with page numbers.
- [ ] Every rating was compared with a peak, and the peak has a source. Evidence: the same rows.
- [ ] Parts whose value may change are on their own lines. Evidence: the list of such designators and `out/bom_line_audit.md`.
- [ ] Consumables, hand-fit and off-board parts are BOM lines with source and price. Evidence: the off-board section of the BOM.
- [ ] The cost table separates per-part cost from per-order fees and shows both assembly price paths where they exist. Evidence: the cost section of `DESIGN_NOTE.md`.
- [ ] The priced parts list was shown to the user, and their go is recorded where the cost is above the target or no target was given. Evidence: the message, the decision row of the state file.

## Outputs

- The BOM in `out/` (the assembler's upload format and a readable table), off-board parts included
- `out/BOM_STOCK_CHECK.md`, dated; `out/bom_line_audit.md`; `out/jlc_parts_answers.json` (every live answer, for the reviewers); `out/parts_search.md` and `out/jlc_parts_searches.json` when parts were searched by name
- `DESIGN_NOTE.md`: BOM summary, cost model, worst-case calculations
- `vendor/datasheets/` filled

## Lessons behind this phase

- A current limiter was picked for a load whose current nobody had measured, and only a handful were in stock -> the minimum limit is checked against a bounded load, and stock before the part enters the schematic.
- A resettable fuse held only about half its rated current at the hottest local temperature, less than the load's peak -> hold current is read at the hottest local temperature.
- A shutdown timer on an RC with ordinary capacitors and a commercial-grade timer chip ranged from seconds to never -> worst-case timing, counter-based timers, the temperature grade from the air at the part.
- An LED suggested by the user was common cathode where the drive needed common anode; the first pick before it was out of stock -> variant and live stock are checked on every part, whoever proposes it.
- A shunt reference family has two pin orders under similar names and two accuracy grades under one number -> the exact number is locked and the worse grade assumed.
- One resistor that later had to change shared a BOM line with others; after the order only the whole line could be changed -> an own line for any value that may change.
- A part was first sized on the average level; the worst-case peak with gain spread was far higher, and the first candidate turned out to be non-catalogue -> ratings against peaks, and a life-cycle check before a part enters the BOM.
- For a few assembled samples the per-order fees outweighed the parts, and the extended-part fees alone were a large share of the estimate -> basic first, and a cost table that shows the fees apart.

The full cases are in `references/lessons.md`.
