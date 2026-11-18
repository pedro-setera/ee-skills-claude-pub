# Phase 4: datasheets and rules

Read every datasheet in full and turn it into project documents: the reference check with pin tables and limits, the protocol tables, and the layout rules ledger.

## Inputs

- The BOM with the datasheet path of every line; `DESIGN_NOTE.md`.
- `templates/REFERENCE_CHECK.md`, `templates/LAYOUT_RULES_LEDGER.md`.
- `scripts/fetch_parts.py`; `references/pcb-rules/` (the questions to ask of each datasheet, by circuit type).
- `references/lessons.md`, section "Phase 4: datasheets and rules".

## Steps

1. Fetch the documents of every part that is not a plain passive, by direct URL with `scripts/fetch_parts.py`, into `vendor/datasheets/`:
   - the datasheet;
   - the evaluation board's user guide with its schematic and its BOM, where one exists;
   - the application notes the datasheet points to;
   - for the parts of an RF path (a filter part, the inductors and capacitors of a filter or a matching network), the maker's S-parameter or SPICE model files, into `vendor/models/` (`references/pcb-rules/rf.md` RF-94);
   - **for every complex part, the maker's hardware design guide.** Complex parts are microcontrollers and processors, programmable logic, radio chips and radio modules (cellular, satellite navigation, Wi-Fi, Bluetooth, sub-gigahertz), display and video chips, USB power-delivery controllers, Ethernet and other line transceivers, audio codecs and switching amplifiers, battery chargers and fuel gauges, motor drivers, and any part with more than about 20 pins or with a radio in it. (A small serial memory of 8 pins is not one; memory buses are outside the proven range.) The datasheet of such a part is not enough: the maker puts what the board must do in a second document, under names such as "hardware design guide", "hardware design manual", "hardware integration manual", "hardware development guide", "getting started with hardware development", "board design guidelines", "PCB layout guidelines", "pin connection guidelines", "schematic checklist", "hardware design checklist", "system integration manual", "antenna design guide", the oscillator design guide, a "reference design" with its schematic and layout, the family reference manual (the reset state of the pins, the boot modes and the clock tree are there, not in the datasheet of most microcontrollers), the boot-loader note (which pins the boot code drives), and the errata sheet. They are often NOT linked from the datasheet: search the maker's product page and its document list for them (a web search by part family and these names finds the page; the file itself comes from the maker). Write "none published" only after such a search, with where you looked and the words you used;
   - the maker's design guides for the chip, where they exist: the decoupling or power-supply guide, the board-layout guide, the guide for each fast interface it uses. Their tables are requirements, not reading matter: the decoupling table goes into the reference check (`references/pcb-rules/mcu-digital.md` MCU-08), every layout rule into the ledger.
   Never click a download in a browser. Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8); the script fetches one file at a time and keeps every file for reuse. Some makers give these documents only after a free registration or on request: signing in and asking is the user's (`SKILL.md` rule 9). If a site blocks the fetch, take the next source in the order of `references/working-rules.md` section 7 (the maker, LCSC's copy, another authorised distributor's copy, the Internet Archive's copy of the maker's file; never a collector site, never a way around the block). If no source gives the document, or it wants a sign-in, tell the user in plain words what to get (the exact title, document number and revision), where (the page link), how (which button, which form), and where to put it (`vendor/datasheets/<part>/`), and what waits for it. Until it is there the block around that part is not designed from memory (`SKILL.md` rule 18). In short: give the user the exact link, mark the part "datasheet pending" (its checks are UNKNOWN) and go on with the others.
2. Read each datasheet whole, not only the first page and the typical application:
   - the absolute maximum ratings and the recommended operating conditions;
   - the electrical tables with their test conditions;
   - the description of every feature and mode;
   - the application and layout sections, the footnotes, the family comparison table;
   - the package drawing and the land pattern.
   Read each hardware design guide whole as well, and turn every "must", "shall", "recommended" and every checklist line of it into a row: circuit items into the reference check, layout items into the ledger, pins and limits into `src/datasheet_pins.toml`, the order of supplies into the sequence table, boot and strap pins into the pin table of `REFERENCE_CHECK.md`, marked for the firmware hand-over (written in phase 7). Record per document which sections were read and how many rows came out of it; a guide that produced no row was not read.
   For passives with a job (inductors, PTCs, ferrites, power and timing capacitors) read the curves: DC bias, derating over temperature, saturation, impedance over frequency.
3. Write a pin table per IC from the datasheet's pin table, not from the symbol: pin, name, function, our net, verdict. Type each pin once, in `src/datasheet_pins.toml` (`templates/DATASHEET_PINS.md`), with its function in a few of the datasheet's words (key `function`): the pin table of the reference check is then the report of `scripts/ratings_check.py` (pin, name, function, net), completed in phase 5 step 7b once the netlist exists, and only the verdict column is written by hand. For unused pins write what the datasheet tells you to do with them. For every control input (enable, shutdown, chip select, reset, mode, address, gate) write the pull inside the part: which way, its minimum and maximum, and whether it works without firmware (`references/pcb-rules/mcu-digital.md` MCU-64, MCU-65); for a microcontroller or programmable logic, which pins are high-impedance in reset. Add one line on look-alike pin-outs and suffix variants.
4. Compare limits with our corners, pin by pin: the absolute maximum and the recommended range, against our worst case including transients (an input pushed above its rail on an edge, an output pulled below ground by an inductive load) and the hottest ambient. Staying inside the absolute maximum is not enough; the recommended range is the design target. Plain LEDs, connectors and anything that is no part (a cable landing) need no pin block of their own when `[ratings]` of `board.toml` says so (`skip`, `need_block`; `templates/DATASHEET_PINS.md`, last paragraph), each with one word of reason.
   - The limits go into the same file, `src/datasheet_pins.toml` (format and rules: `templates/DATASHEET_PINS.md`): per part number, each pin's number and name as the datasheet prints them, its absolute maximum and its recommended range, with the page; and per supply and signal level of the design, its lowest and highest value at the worst case, transients included. Type it from the datasheet, never from the symbol. Phase 5 runs `scripts/ratings_check.py` on it: a machine then compares every pin of the drawn circuit with what the maker says, every time the schematic changes.
5. Do the reference check for every important part: each surrounding part of the maker's typical application and of the evaluation board, against ours. Every row ends "same", "aligned" (we changed ours to match) or justified with a number or a page. Every part the maker calls recommended is present or justified. Where a deviation cannot be justified, align.
6. Check conditional clauses against the real installation: "if the supply is more than a few inches away", "for capacitive loads above", "with a minimum load of". Each one is a row.
7. Where a chip has more than one supply, or its datasheet states an order, a ramp speed or a wait (core before I/O, a rail that must never exceed another, reset held until the supplies are steady, enable only after an input is valid), write the sequence table: the maker's requirement with its page, how our circuit guarantees it when switching on, switching off and after a short supply dip (an enable chain, a power-good signal, a supervisor, an RC delay with its tolerance), and its proof (a start-up simulation with all rails, or a bench test with a scope) (`references/pcb-rules/power.md` PWR-63). Where a chip negotiates, sequences or retries, write its behaviour as a table read from the feature description: what it requests, when, what it falls back to, when it resets, what it does on a fault. For a supply that negotiates, make one row per mode the source may offer: what the chip requests there, our worst load, the margin. Prove that the device never draws more than it requested.
8. Write the set-point table: for every value set by resistors or capacitors, the formula, the datasheet page, and the nominal, minimum and maximum with part tolerances, referred to the output. Phase 5 recalculates it from the drawn values.
9. Fill the layout rules ledger: one row per rule that a datasheet or a layout guide sets. Each row has an ID (`LR-01`, `LR-02` ...), the part, the rule in a few of the maker's words, the page, and how it will be checked in phase 10 (a script, a measured distance, an image crop). Look in each datasheet for:
   - which capacitor closes the hot loop for this topology (a buck's input, a boost's output; `references/pcb-rules/power.md` section 2), and where it sits;
   - what must stay short, and how the feedback is routed;
   - where analog and power ground join;
   - the thermal pad and its vias, keep-outs, copper area for heat;
   - the maker's advice on the layer stack;
   - each digital driver's rise time at its fast corner, with its source (datasheet, IBIS model, or an assumption marked ASSUMED: `references/pcb-rules/mcu-digital.md` MCU-48), and the slowest drive or slew setting that meets timing, also written into the design note for layout and firmware (MCU-46).
   Add the rules every board gets, from the template.
10. Record the land pattern and the 3D model source per part:
    - The page of the maker's land pattern, and JLCPCB's own footprint fetched into `vendor/jlc_fp/` (paced as in step 1). Note where the two differ; the maker's pattern is the reference for power magnetics and fine pitch.
    - The 3D model in `vendor/3d/`, and its origin against the footprint's origin, for the check in phase 9. A part with no real model is listed as a stand-in.
11. Copy every rating into the documents with its symbol, unit and page. Label anything taken from a sister part's datasheet as an inference and give it a bench item.
12. Feed back what the reading changed: parts the reference circuits require, changed values, a different variant. New parts go through phase 3 (variant, worst case, stock) before they enter the BOM.

## Questions for the user

None. A blocked download is a request, not a decision: give the user the link and the folder to put the file in, and continue.

## Checks before leaving this phase

- [ ] Every non-passive BOM line has its datasheet in `vendor/datasheets/`; each missing one is named and its part marked UNKNOWN. Evidence: the file list against the BOM.
- [ ] `REFERENCE_CHECK.md` has a block per important part naming the datasheet revision and the evaluation board used, or "none published". Evidence: the file.
- [ ] Every complex part has its maker's hardware design guide on disk and read, with the rows it produced; or "none published" with the search recorded; or "documents pending" with the user asked and the part's checks UNKNOWN. Evidence: the "Documents used" line of each block in `REFERENCE_CHECK.md`, the files in `vendor/datasheets/`.
- [ ] Every reference row is "same", "aligned" or justified with a number or a page; no row is empty. Evidence: the tables.
- [ ] Each IC has its pins typed from the datasheet's table, and a line on look-alike pin-outs (the pin table with our nets follows in phase 5 step 7b). Evidence: `src/datasheet_pins.toml`; the look-alike line of `REFERENCE_CHECK.md`.
- [ ] `src/datasheet_pins.toml` holds every chip, transistor and polarised part with pin numbers, names, absolute maximum and recommended range, typed from the datasheet, and the worst-case value of every supply and signal level. Evidence: the file, with a page per part.
- [ ] Every chip with more than one supply, or a stated order, ramp or wait, has its sequence table with the mechanism and the proof; the others say "one supply, no order stated". Evidence: `REFERENCE_CHECK.md`.
- [ ] Each pin's recommended range and absolute maximum are compared with our corner; nothing sits outside the recommended range without a written reason. Evidence: the limits tables.
- [ ] Each negotiating or sequencing chip has its behaviour table, and each mode shows a positive margin or a defined reduced behaviour. Evidence: the tables.
- [ ] Every conditional clause found has a row with our installation's value. Evidence: the rows.
- [ ] The set-point table gives formula, page, and minimum, nominal and maximum. Evidence: the calculations section of `DESIGN_NOTE.md`.
- [ ] Every ledger row has a page number and a check method; none says "later". Evidence: `LAYOUT_RULES_LEDGER.md`.
- [ ] Land pattern source and 3D source are recorded per part; stand-ins are named. Evidence: the list.
- [ ] Every download was a direct URL into a new folder. Evidence: the list of URLs with dates.

## Outputs

- `REFERENCE_CHECK.md`
- `LAYOUT_RULES_LEDGER.md` (rules and check methods; the results are filled in phases 9 and 10)
- `vendor/datasheets/`, `vendor/jlc_fp/`, `vendor/3d/`
- `DESIGN_NOTE.md` updated: set-point table, changed parts

## Lessons behind this phase

- A negotiating supply chip requests its set current at whatever voltage it selects; a check of the set-point alone misses that it can then draw more than the source's contract allows -> protocol behaviour is written as a table, one row per mode.
- The first design was compared with no evaluation board. A later check found a series resistor, two line capacitors, an output capacitor and a Schottky diode that the makers' boards carry and the design lacked -> the reference check covers the typical application and the evaluation board's schematic and BOM.
- A required 1 uF input capacitor kept only 0.35 to 0.5 uF at its working voltage in the chosen size -> required capacitance is checked at DC bias.
- A maker's clause about bulk capacitance for a distant supply was not addressed with the supply far from the chip -> conditional clauses are rows of the check.
- A supply rail's budget was taken from a limit that applied to signal pins, and an energy rating was quoted as a pulsed-current rating -> ratings are copied with symbol, unit and page; inferences are labelled.
- Layout guidance lived in the designer's head, and reviewers had to rediscover it chip by chip -> the ledger gives every rule a page and a check method before layout starts.
- Supplier sites refused automated downloads, and a browser download opened a save dialog no agent could operate -> direct URL only; otherwise the link goes to the user.
- Imported 3D models with their origin at pin 1 later hid a connector over a mounting screw -> the model's source and origin are recorded here and checked in layout.

The full cases are in `references/lessons.md`.
