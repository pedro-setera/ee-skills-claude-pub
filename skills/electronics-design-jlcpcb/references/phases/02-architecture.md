# Phase 2: architecture and budgets

Fix the blocks, the power tree, the protections and the interconnects with numbers, before any part is chosen in detail.

## Inputs

- `REQUIREMENTS.md`, confirmed by the user (gate 0).
- Datasheets, manuals, drawings or photos of everything the board connects to: mating boards, modules, loads, supplies.
- `templates/DESIGN_NOTE.md`; `references/pcb-rules/` for the circuit types on the board, `emc.md` always.
- `references/working-rules.md` sections 11 and 12 (quality first, then cost; just enough, and simple).
- `references/lessons.md`, section "Phase 2: architecture and budgets".

## Steps

**Quality first, then cost** (`references/working-rules.md` section 11). Safety, the function the user confirmed, stability and reliability come first and are never reduced to save money. When they are met, ask of every block and every protection: can the same result, at the same quality and reliability, be had for less (parts, board area, an extended-part fee)? If yes, take the cheaper way. If the cheaper way lowers quality, stability, reliability or function, it is not a saving. A protection or measure that a credible fault or the table of noise sources calls for is fitted; it is not left out for cost. "Footprint only" is for provisions whose need is uncertain, not for known needs.

**Just enough, and simple** (`references/working-rules.md` section 12). Choose the simplest architecture that meets every requirement. Every block traces to a requirement, a datasheet demand or a credible fault of the protection table; a block that traces to nothing is removed. Protection answers the faults that can really happen to this product. Nothing here removes a required margin, protection, check or review.

1. **Start only on a confirmed page.** While gate 0 is not recorded, or the power source block of `REQUIREMENTS.md` is open, do not draw the block diagram: go back to phase 1. Then draw the block diagram as a picture, with the list of blocks and what each traces to: every block, every signal between blocks with its direction, every connector at the edge, every external thing it talks to. Draw the power tree as a second picture: sources, protections, converters, rails, loads, with voltage and current on each arrow. Pictures are what the user approves and what reviewers read first.
2. Write the budgets, each number with its source (datasheet page, measurement, or a stated bound). A board with one regulator and no fast load writes one line per rail, and when no part loses more than about 0.1 W the heat table is the one line "no part above 0.1 W"; block diagram and power tree may then be one picture:
   - Current per rail, typical and peak, per load. A load nobody has measured is bounded from vendor data and goes on the bench list; it is never guessed silently.
   - Voltage at each load's own pins at the worst corner: regulator tolerance, load step, board copper, contacts, harness, and the return path.
   - Source budget: for every source and every mode it may run in (for example each voltage a negotiating supply may offer), the input current and power against what the source may deliver.
   - Heat: the loss in every converter, regulator, limiter and series part, and the temperature inside the enclosure. If that is unknown, write UNKNOWN with the assumed value and a bench item. Start the heat table of the design note here: one row per part above about 0.1 W, its loss at the worst case, the temperature it may reach, and how much copper it will need (`references/pcb-rules/power.md` PWR-21, PWR-62). Phase 8 reserves that copper; phase 9 fills in what the board really gives. For every part above about 0.5 W, or within 25 C of its limit, do the thermal study now (`references/pcb-rules/thermal.md`): the worst-case loss, the air inside the enclosure, the junction temperature with a margin; then go up the cooling ladder one step at a time (lose less, copper, a path into the case, a heat sink, a fan) and stop at the first step that holds the margin. A heat sink or a fan is decided here, not at the layout: it needs height, holes, air openings, power and a connector. When the study asks for one, propose it to the user with its size and what it costs in money, height, noise and upkeep.
   - Rail table: per rail its voltage, transient current, allowed ripple and target impedance (allowed dynamic voltage in volts / load step in amperes, with its frequency range and observation point), and per regulator the total effective capacitance it starts into, against its datasheet maximum and its minimum current limit during soft-start (`references/pcb-rules/power.md` PWR-49, PWR-50). The allowed dynamic voltage is also the bench pass value.
   - Ratings are compared with peaks, never with averages.
   - Energy budget, for a battery device (`references/pcb-rules/power.md` PWR-56): a table of operating modes (active, idle, sleep, transmitting, charging), the current of each from datasheet figures at the real supply voltage, the share of time in each, the average current, plus the regulators' quiescent current and the cell's self-discharge. Every current is referred to the cell (through a switching converter the cell current is the rail current times the rail voltage, divided by the cell voltage and the efficiency), and the running time is given twice: typical figures at room temperature, and maximum figures at the hottest surroundings; the user is told the lower one (PWR-56). Autonomy = usable capacity / average current, the usable capacity being the rated one derated for temperature, ageing, the circuit's cut-off voltage and the discharge rate (start from 70 to 80 % of the rated capacity, an estimate). Also the peak current against what the cell can deliver, and the charge time from the charge current (PWR-57). Compare with the wanted running time and tell the user in plain words ("about 30 hours per charge"); if it misses, take the options (a bigger cell, lower consumption, sleep modes) to the user.
3. Build the protection table: one row per connector and per fault (reverse polarity, overvoltage, hard short, partial short, a pass element failed short, ESD, hot plug, back-feed). The fault kinds that are not credible at a connector (no battery, no cable, a keyed plug whose mate this project wires; a cell on a plug stays reversible: `references/pcb-rules/power.md` PWR-64) are named together in one row for that connector, not argued one by one. A battery gets its own rows: cell over-charge, over-discharge and over-current, charge current against the source and the heat, cell temperature, reverse battery, a fuse at the cell whose DC breaking capacity covers the cell's short-circuit current, charger back-feed into an unpowered controller (`references/pcb-rules/power.md` PWR-55, PWR-57, PWR-58, PWR-64). Each row names:
   - the protection, where it sits, how fast it acts, and its tolerance;
   - the stored energy that remains downstream of the point where it disconnects. This column is the energy map;
   - fitted, footprint only (its need is uncertain), or left out (no credible fault), and why.
   If the remaining energy alone can damage the load, the protection must clamp at the protected rail. A protection that acts upstream of the stored energy protects nothing. Power-input order (`references/pcb-rules/protection-esd.md` section 1): an optional small bidirectional ESD clamp, the fuse or PTC where reverse connection or a sustained over-voltage is credible, the reverse-polarity element, the power TVS, the eFuse, the filter and the bulk capacitance. A TVS standoff is at or above the highest continuous voltage, tolerance included (for example vSafe5V maximum 5.5 V; a 20 V USB PD contract 21 V), never from transients. On signal lines the ESD clamp sits at the pins first.
4. Give every branch that leaves the board, or feeds a load that can fault on its own, its own limiter or resettable fuse. The protection table decides which branches need one: a branch with a credible fault gets it, and the cost target of phase 1 does not remove it; write the reason for every branch left without. Size it so that it holds the load's peak at the hottest local temperature and trips below the rating of the contacts and wire in that branch. An input-side limiter sees the output current divided by the conversion ratio and cannot protect the outputs. A current setting in software is not protection.
5. Analyse back-feed. List every signal between parts with separate supplies: a powered peripheral into an unpowered host, an external voltage on a connector, a port that can source power.
   - For each: the path, the current, what it holds up, and the measure (a series resistor, a load on the sensed rail, a blocking part, or a label where a part would break the main function).
   - Any circuit that detects "the other side is off" must still work with every such path present.
6. Write the table of noise sources and sensitive parts (`references/pcb-rules/emc.md` section 2): which part disturbs which, by which path, and the measure against it; the converter and clock frequencies against every receive band. For every source and victim decide whether a shield can is needed: fitted, footprint only, or not needed with the reason (`references/pcb-rules/emc.md` section 10); a can is a part with a price, a height and heat under it, so it is decided here and not found out at the layout. It goes into the design note; phase 8 turns it into the zone map of the board.
7. Build the interconnect table, one row per connector:
   - Gender, keying, pitch and pin numbering of the mating part, each taken from the mating part's documents, a photo or a meter check. Never from memory, and never from the user's memory alone for a destructive pin.
   - Current per pin at the worst fault the protection lets through, against the contact rating. Use two contacts for a rail when one is not enough.
   - Mis-plug: can the plug go in rotated, offset by a row, or into the wrong header? Where a mis-mate would destroy something, an unkeyed plug is rejected.
   - Wire gauge against the crimp's range, cable direction, and who makes the cable.
8. Use one latching, keyed connector family for the cables made for this board. Each exception is justified by what sits on the other end. Use a standard connector only in its standard role: a connector whose shape promises a role it does not have invites a wrong cable.
9. Decide the panel interface for connectors that cannot sit at the wall (bulkhead part and pigtail, or a board-edge part made for panels). The dimensions come from the part's drawing in phase 8.
10. Make the buy-or-design table for every block that exists as a ready module (an RF filter counts: a ready filter part comes before a filter of discrete parts, `references/pcb-rules/rf.md` RF-91): module price against the own design's cost per unit at the sample quantity and at volume, the design effort and prototype rounds, and how well the module is documented. Search for ready modules before proposing a custom block. Recommend, then wait for the user's go.
11. Make the area budget: a first parts list, the passive size (for example 0402 or 0603), the sum of the courtyards, a fill target (at most about 55 to 60 % for a one-sided power board), routing channels between blocks, room for labels. The result is a minimum area for phase 8. Do not choose an outline here.
12. Plan test and bring-up provisions now; they are parts on the schematic:
    - a test point per rail and per key signal (on a sensitive analog node probe the part's pad instead of adding a stub); the full list is made at the schematic from what will be measured, and a planned production fixture decides their side (`references/pcb-rules/dfm-dft.md` section 10);
    - zero-ohm links for every block that must be brought up on its own (a converter, a protection circuit, a costly or risky load, or any block whose fault would hide the others') (`references/pcb-rules/dfm-dft.md` DFM-100);
    - an injection resistor in each converter's feedback for a loop measurement, fitted at 10 to 51 ohm so that no rework is needed before the measurement;
    - unfitted footprints for tuning (boot resistor, snubber, filter values);
    - any fallback path that can cut power is unfitted by default until proven on the bench.
13. If a metal enclosure may come later, add a chassis-ground option now: a chassis net for connector shells and chosen mounting holes, joined to circuit ground at one point through a fitted link, with unfitted positions for a capacitor and a resistor. It costs almost nothing and saves a new board.
13b. Name the critical technical risks: the three to five things most likely to sink this design (the hardest requirement, the tightest margin, the part known least, the block never built before, the one source of a key part). For each write what happens if it goes wrong, and how and when it is retired: a calculation now, a simulation in phase 6, an early test on the maker's evaluation board, a second part kept ready, a bench test with a number. Retire the worst one first, before effort goes into the rest. A design with no risk named has not been looked at hard enough; a simple board may have one or two, and that is said.
14. Ask the key-chip question for the few chips that shape the design (microcontroller, converter controller, data converter, radio, FPGA): does the user have a preferred part, or may you choose? Suggest one with the reason. Do not ask this for any other part.
15. Write all of the above into `DESIGN_NOTE.md`. Show the user the two pictures with at most three questions per message. With them, tell the user the looked-up price of the few parts that will dominate the cost (key chips, modules, the battery, a display), and that the full priced parts list follows after part selection: a project that is not affordable should show it here, not after the schematic. Record the OK.

## Questions for the user

Ask in everyday words: say what a choice means for the device and its cost rather than naming the technique, explain any technical word in a few words the first time, and give the suggested answer with a reason a non-engineer can weigh (`references/working-rules.md` section 1).

- For `<key chip role>`: do you have a preferred part?
  - Suggested: `<part>`, chosen by me.
  - Why: `<in stock at JLCPCB, basic or preferred class, maker's reference design available, known to the user's software>`.
- Buy `<module>` or design the block on the board?
  - Suggested: `<one of them>`, with the cost table.
  - Why: `<price per unit at the sample quantity and at volume, risk, documentation>`.
- (Cooling) `<Part>` would reach about `<x>` C inside the case; its limit is `<y>` C. Add `<a heat sink of <size> | a <40> mm fan, with a heat sink | a thermal pad to the metal case>`?
  - Suggested: `<the first step of the cooling ladder that holds the margin, with its size>`.
  - Why: it then runs at about `<z>` C; it costs `<money>`, `<height>`, and for a fan a sound of `<n>` dBA and a part that wears in about `<years>`; the alternative is `<a less powerful part | a larger or metal case>`.
- (Battery) It runs about `<n>` hours per charge; you wanted `<m>`. Which way?
  - Suggested: `<a bigger cell, +<cost> and +<size> | lower consumption by <measure>>`.
  - Why: the energy budget shows `<average current>` against `<usable capacity>`.
- With `<source mode>` the device cannot run at full load. What should it do?
  - Suggested: `<run reduced with this message / stay off with this sign>`.
  - Why: the budget shows `<demand>` against `<supply>`; this is behaviour the customer sees.
- Is the block diagram right?
  - Suggested: approve.
  - Why: every interface of the requirements page appears in it; parts are chosen from it next.

## Checks before leaving this phase

- [ ] The block diagram and the power tree exist as images and were opened and looked at. Evidence: `out/block_diagram.png`, `out/power_tree.png`, two lines on what each shows.
- [ ] Every rail has typical and peak current, each with a source. Unknown loads carry a bound and a bench item. Evidence: the power budget table.
- [ ] The voltage at each load's pins at the worst corner meets the load's minimum. Evidence: the calculation rows with harness and return included.
- [ ] Every rail has its target impedance, and every regulator's start-up capacitance is within its datasheet maximum and current limit. Evidence: the rail table.
- [ ] Every part above about 0.1 W has a row in the heat table with its worst-case loss, its estimated temperature with the air at the part (the hottest surroundings plus the rise in the case, THM-02) and its limit less the margin of THM-04. Evidence: the heat table.
- [ ] Every part above about 0.5 W or within 25 C of its limit has its thermal study and its cooling decision (copper only, a path into the case, a heat sink, a fan with its size), and a heat sink or fan was put to the user. Evidence: the heat table with the step reached, the decision row.
- [ ] For every source mode, demand is within supply or the reduced behaviour is defined. Evidence: the source table.
- [ ] A battery device has its energy budget, and the autonomy was told to the user against the wanted running time. Evidence: the energy budget table, the decision row.
- [ ] The protection table has a row for every connector and every fault (or one row per connector for the kinds that are not credible there), with location, speed, tolerance, remaining energy, and fitted, footprint only or left out with the reason. No empty cell. Evidence: the table.
- [ ] Every noise source and sensitive part is in the EMC table with its path and measure. Evidence: the table in the design note.
- [ ] The critical technical risks are named, each with its consequence and how and when it is retired. Evidence: section 15 of the design note.
- [ ] Every requirement `REQ-nn` is met by a named block or budget line. Evidence: the "traces to" column of the block list; no requirement without a block, no block without a requirement.
- [ ] Every branch that leaves the board or can fault on its own has its own limiter or resettable fuse, or a written reason. Evidence: the branch list and the protection table.
- [ ] The back-feed list covers every signal between separately powered parts and every connector that can be driven from outside. Evidence: the list with a measure per row.
- [ ] Gender, keying, pitch and pin 1 of every connector cite a document page, photo or measurement. Evidence: the interconnect table.
- [ ] Current per pin at the worst let-through fault is within the contact rating. Evidence: the same table.
- [ ] No plug can mate rotated or offset where that would be destructive. Evidence: the mis-plug column.
- [ ] The buy-or-design table carries prices with a date. Evidence: the table.
- [ ] The area budget states a minimum area and how it was computed. Evidence: the section in the design note.
- [ ] Test and bring-up provisions are listed. Evidence: the list.
- [ ] Simplicity: no block or part could be taken away with every requirement still met at the same margin and reliability. Evidence: the trace column of the block list in the design note.
- [ ] The user's OK on the block diagram and the key-chip answers are recorded. Evidence: decision rows with date and words.

## Outputs

- `DESIGN_NOTE.md`: concept in blocks, power budget with the rail table and the energy budget, protection per fault with the energy map, the table of noise sources and sensitive parts, back-feed list, interconnect per connector, buy-or-design table, area budget, test and bring-up provisions, assumptions and risks, first bench tests
- `out/block_diagram.png`, `out/power_tree.png`
- `PROJECT_STATE.md` updated

## Lessons behind this phase

- An overvoltage protection switched off upstream while a large bulk capacitance charged to the input voltage sat below it; a shorted converter would still have dumped that charge into the low-voltage loads -> the energy map, and a clamp at the protected rail.
- A powered peripheral's signal line fed an unpowered processor through its pin clamps and held its rail up, so the off-detection never fired and the device never switched off -> back-feed is analysed for every signal between separately powered parts.
- A partial short on a cable drew several times a contact's rating and tripped nothing -> a PTC or limiter per branch, sized between the load's peak and the contact rating.
- A female housing was chosen for a header that was itself female; the next proposal could be plugged in rotated and would have put 5 V on a ground pin -> gender, keying and pin numbers come from the mating part's documents, and a plug that can mis-mate destructively is rejected.
- Two connector families appeared on one board and the user asked why -> one latching family, exceptions justified in the table.
- Two loose modules cost several times an own board; no ready combined module was documented well enough to trust -> buy-or-design is decided with a cost table, after a search.
- The first outline was smaller than the sum of the part courtyards, and the next shape was too congested: two layouts were thrown away -> an area budget before any outline.
- Where a metal enclosure may come later, a chassis-ground option on the first board costs almost nothing -> provisions for known futures are made now.

The full cases are in `references/lessons.md`.
