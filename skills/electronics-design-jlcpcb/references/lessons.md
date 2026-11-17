# Lessons: real mistakes and the checks that prevent them

This file collects real mistakes from earlier hardware projects (boards, cable harnesses, an enclosure), each with what it cost and the check that prevents it.
Every entry happened, or was caught just before it would have cost boards, days or money.
Read the section of the phase you are in before you start the phase, and again before you leave it.
Search this file whenever something feels like "it is probably fine": a nominal value, a script that passed, a part that looks the same, a supplier who will surely understand.
Each check names the skill script, review or gate that enforces it; where none is named, the check is yours to do by hand.

## Contents

- [The fifteen costliest](#the-fifteen-costliest)
- [Phase 0: start or resume](#phase-0-start-or-resume)
- [Phase 1: requirements](#phase-1-requirements)
- [Phase 2: architecture and budgets](#phase-2-architecture-and-budgets)
- [Phase 3: part selection](#phase-3-part-selection)
- [Phase 4: datasheets and rules](#phase-4-datasheets-and-rules)
- [Phase 5: schematic](#phase-5-schematic)
- [Phase 6: simulation campaign](#phase-6-simulation-campaign)
- [Phase 7: schematic reviews](#phase-7-schematic-reviews)
- [Phase 8: board definition](#phase-8-board-definition)
- [Phase 9: layout and 3D](#phase-9-layout-and-3d)
- [Phase 10: designer's checks](#phase-10-designers-checks)
- [Phase 11: layout and visual reviews](#phase-11-layout-and-visual-reviews)
- [Phase 12: production files](#phase-12-production-files)
- [Phase 13: order at JLCPCB](#phase-13-order-at-jlcpcb)
- [Phase 14: order and e-mail watch](#phase-14-order-and-e-mail-watch)
- [Phase 15: arrival and first power-up](#phase-15-arrival-and-first-power-up)
- [Working with the user](#working-with-the-user)
- [Working with agents and tools](#working-with-agents-and-tools)
- [Working with suppliers](#working-with-suppliers)
- [Adding a lesson](#adding-a-lesson)

## The fifteen costliest

Ranked by what each cost, or would have cost had nobody caught it. The full entries are in the phase sections.

| Rank | What went wrong | What it cost | Phase and check that prevents it |
|---|---|---|---|
| 1 | Two different nets had the same name on two sheets; the generator made the name global and merged them. ERC passed (all pins passive) and a netlist check compared the design with its own source. | At first power-on a resistor would burn and the input voltage would reach a small MOSFET gate. Caught by the first independent review. | Phase 5: generator refuses duplicate names; `scripts/netlist_check.py` against hand-written intent, with its mutation self-test. |
| 2 | Placement rotations came from a generic correction table: every SOT-23 part wrong, the input electrolytic reversed, a diode wrong by pad-number matching. | Every assembled board scrapped. Caught by the second layout review. | Phase 12: `scripts/jlc_rotations.py` from JLCPCB's own footprints; phase 13 preview check per polarised part. |
| 3 | Layout started on an outline with no area budget, then on a congested L-shape on 2 layers, while the enclosure was still changing. | Two layouts thrown away, hours of routing lost, a restart on a new outline and 4 layers. | Phases 2 and 8: area budget; outline, holes and stack frozen before any routing. |
| 4 | A block of the signal chain (a power feed an external part needed) had no part, power or space until after the board was ordered. | Extra design work and a further order. | Phase 1: interface and signal-chain checklist. |
| 5 | A protection resistor in a data line was sized without the receiver's internal pull-up, and shared one BOM line with other resistors. | Order on hold and days of e-mails. | Phase 5: levels both ways with internal pulls; phase 3: own BOM line for any value that may change. |
| 6 | A powered peripheral back-fed the switched-off processor through a signal line; the power-off sense never fired. | A device that never switches off in its normal wiring. | Phase 2: back-feed table; phase 6: off rails modelled floating. |
| 7 | The USB-PD sink controller requests its set current at whatever voltage it picks; the schematic reviews missed it. | The device would have over-drawn its contract on some chargers; found only at gate 2. | Phase 4: protocol behaviour table, checked in the schematic-datasheet review. |
| 8 | Over-voltage protection switched off the input, upstream of a large bulk capacitance still charged to the input voltage. | A shorted converter switch would still have destroyed every low-voltage load. | Phase 2: energy map per protection; clamp at the protected rail. |
| 9 | Output fault gaps: no short protection, soft shorts unprotected, fuses that hold too little when warm, one branch with no limiter. | Overheated contacts and beads, brown-out loops; one gap found only after the reviews. | Phase 2: fault table per branch with derated protection; phase 6: partial-short simulations. |
| 10 | The copper fill was saved before the edge rule; DRC said 0 while the Gerbers had copper to the outline. | Fab rejection or shorts at the edge; caught by the layout review. | Phase 10: `scripts/edge_check.py` on the exported Gerbers. |
| 11 | Connector 3D models had their origin at pin 1; a body sat millimetres off, over a mounting screw, while a script said it was clear. | Enclosure assembly failure; the user found it on a render. | Phases 9 and 10: `scripts/body_check.py` plus the visual review. |
| 12 | A long shutdown timer used a leaky RC and a commercial-grade timer chip in a warm box. | Timeout from seconds to never: unsafe shutdowns or a device that never turns off. | Phase 3: worst-case timing; counter-based timer; temperature grade. |
| 13 | Library footprints wrong: 2.54 instead of 2.50 mm pitch, a part with no footprint, generic land patterns, courtyards smaller than pads. | Headers that would not insert; a part silently dropped from assembly. | Phase 9: `scripts/fp_audit.py`; phase 5 lint for missing footprints. |
| 14 | A converter's quiet ground tied to main ground at three points, and DRC blind to narrow necks in power pours; both claimed covered. | Noise in a sensitive band and hidden current bottlenecks. | Phases 9 and 10: cut test with `scripts/zone_check.py`; `scripts/neck_check.py` with a planted neck. |
| 15 | Labels placed after routing with no space planned: several visual rounds, group texts naming the wrong parts, parts left unlabelled. | Many fix rounds and a less serviceable board. | Phases 8 and 9: label space in the area budget, labels before routing; `scripts/silk_check.py`; two visual reviews. |

## Phase 0: start or resume

### Rules and decisions kept only in the conversation
- Happened: Standing rules the user had already given (model and effort set explicitly for design agents, a limit on parallel expensive agents) were forgotten in later sessions and had to be given again; the one restart that went smoothly had a handoff file listing what was final, the open issues and the state of every file.
- Cost: relaunched agents, repeated instructions, and a user who had to police the process.
- Check: Read or create `PROJECT_STATE.md` first in every session. Write each decision and standing rule there with its date and the user's words, and keep "next action" current before any pause.

### A late entry skipped the reviews
- Happened: One board got its first deep, pin-by-pin review only after it was paid for, and an outside review of its schematic also arrived after the order; too late for anything they found to be fixed in the files.
- Cost: late changes and a next-revision list that a review before the order would have emptied.
- Check: When a project enters with an existing schematic or board, use the entry table in `phases/00-start.md`: a design with no review record enters at its reviews (phase 7 or 11), never straight at the order.

### "Update from library" run on a project from an older KiCad
- Happened: Reported from other projects: a design made with an older KiCad version was opened in a newer one and its symbols or footprints were refreshed with "update from library". The newer library carried other pin numbers, pin names or pads under the same part name, and the update rewired or re-padded the design without any message.
- Cost: a board that passes every rule check and is wired wrongly, found only on the bench.
- Check: Never run "update symbols from library" or "update footprints from library" on a project made with an older KiCad version without a copy made first and a netlist comparison before and after (`scripts/netlist_compare.py`; for footprints also the pad positions against the copy). A difference that is not an intended change means the update is undone.

### Tool gaps found at the moment they were needed
- Happened: The built-in browser pane could not upload files, the maker's converter and eFuse SPICE models were encrypted for another simulator, and the browser extension lost its connection after a reboot; each was discovered in the middle of an order or a simulation.
- Cost: hours of delay at the order, and behavioural models built in a hurry.
- Check: Run `scripts/env_check.py` at the start and write in the state file what each missing tool disables. Arrange an upload-capable browser before phase 13 and check the extension's connection after every restart.

## Phase 1: requirements

### A block of the signal chain was forgotten
- Happened: An external part needed a power feed; it was noted early as "provided elsewhere" and never revisited, so no part, power source, drawing or space existed when the board was ordered.
- Cost: extra design work and a further order.
- Check: Fill the interface and signal-chain checklist in `REQUIREMENTS.md`: for every external interface list power, part, drawing and mechanical space, including power for active external parts, DC blocks and level shifts. Do not order any board while an interface block is unassigned.

### Supply sources pinned down late
- Happened: A second supply input stayed in the plan until the user dropped it after design work had started, and the charger table for the USB-PD input missed the 12 V level that a common official charger offers.
- Cost: protection work for a source that never came, and a missing case found only by an outside review.
- Check: List every supply source and environment in phase 1 (bench, charger types, power banks, vehicle). For USB-PD, write a charger matrix with every standard voltage level and the weakest chargers that must still work.

### Cost-driving choices asked after the design started
- Happened: Two copper layers, parts on one side only, the silkscreen identification content and the build quantity were raised by the user only after work began; the first carts were sized for more assembled units than the concept stage needed.
- Cost: a reworked layout plan and carts that had to be cut down.
- Check: Ask in phase 1, each with a suggested answer and reason: layer count, assembly sides, silkscreen content, mask colour, and whether this is a concept run. Suggest 5 bare PCBs with 2 assembled for a first sample, and size every cart to the assemblies plus spares.

### The price position was never written down
- Happened: For a cost-driven design the agent proposed premium parts and accessories nobody had asked for; the user rejected them.
- Cost: wasted research and rejected proposals.
- Check: Write the price position in one line in `REQUIREMENTS.md` and test every part and accessory against it. Start from the cheapest standard part that meets the real need; a premium part needs a written reason. Propose extras; never add parts or accessories the user did not ask for.

### Degraded modes and user-visible behaviour left open
- Happened: What the device does on an under-powered charger, what the user sees while the hardware shuts the device down, and whether a long firmware write may be cut by the shutdown timer were all left to the designer and surfaced late.
- Cost: a power-off path that could interrupt a non-interruptible operation, found late.
- Check: List degraded modes, user-visible indications with exact wording, and every long non-interruptible operation. The user decides each from a recommended option; phase 2 checks every hardware power-off path against the list and adds a "hold power" input where needed.

### Gates and notifications agreed late
- Happened: The user had to define the gates (schematic plus cost, layout, 3D plus fab files) and the events worth a notification after work had started, and wanted no other interruptions.
- Cost: unclear hand-over points and repeated "where are we" questions.
- Check: In phase 1 agree the three gates, what the user decides and what the agent decides, and the notification events; record them in `PROJECT_STATE.md`.

### Future enclosure material not asked
- Happened: The enclosure material was asked only after the first schematic; a possible metal case needed a chassis-ground option (0 ohm plus DNP capacitor and 1 Mohm positions, plated and unplated mounting holes) that had to be added late.
- Cost: a late schematic change; without it, a respin for the metal case.
- Check: Ask in phase 1 whether a metal enclosure may follow. If yes, phase 2 adds a chassis-ground option and an antenna plan; on the first board it costs almost nothing.

## Phase 2: architecture and budgets

### Protection upstream of the stored energy
- Happened: The output over-voltage detector turned off the input eFuse, but a large bulk capacitance charged to the input voltage sat downstream of that switch and could still dump into the low-voltage rail through a shorted high-side FET (about twice the rail voltage for up to a millisecond); the detector was also slow and its trip window wide.
- Cost: a shorted converter would have destroyed every low-voltage load; fixed with a crowbar at the protected rail.
- Check: Draw an energy map for every protection: the stored energy between the disconnect point and the protected rail, the whole response-time chain and the trip tolerance. If that energy alone can damage the load, clamp at the protected rail. The schematic-system review checks the map and phase 6 simulates the failure.

### No fault table per output
- Happened: The input eFuse could not see an output short through the step-down ratio, the converter hiccupped at several times the rated load current forever, and soft shorts of about an ohm pushed several times a contact's rating through it; one load's branch still had no limiter after the reviews because a software current setting had been counted as protection.
- Cost: overheated contacts and ferrite beads, brown-out loops, and one gap found late.
- Check: Write a fault table per output: hard short, partial short across the gap between rated load and converter limit, wire to wire. Name for each the protection that sees it, the current, the time, and every part, contact and wire rating in the path; an input-side limiter sees the output current divided by the conversion ratio, and software is not protection.

### Back-feed through a signal into a switched-off domain
- Happened: A powered peripheral's serial line idling high lifted the switched-off processor's 3.3 V rail to over a volt through its clamp diodes, so the power-off sense never fired; the same pattern appeared with a sensor's pull-up into a GPIO and with a load switch without reverse blocking, which let an outside DC source on an output connector hold the whole device on.
- Cost: a device that never switches off in its normal wiring; found only by the second schematic review.
- Check: List every signal and port between separately powered parts and, for each, the path that can power the off side. Load sensed rails, add series resistors, choose reverse-blocking switches or label the port. The schematic-system review checks the list and phase 6 simulates it with off rails modelled as floating.

### Power cut before the host had finished
- Happened: The host's GPIO reset the power latch before the operating system's last device shutdown, so the host's storage never got its shutdown notice; the halt input had no glitch filter, and a power-cut timing window also applied to boot and reboot dips.
- Cost: a risk of corrupted storage and of a power cut at every boot; reworked at review.
- Check: Trigger the cut from a hardware-defined "host finished" signal (the host's own rail going off) or a hook that runs after storage shutdown. Give every input that can remove power a glitch filter and a defined default, check every window against boot, reboot and hot-plug transients, and fit fallback cut paths as DNP until the bench proves them.

### Connector contact current at the worst fault
- Happened: A header pin and a wire-to-board contact each carried a peak above their rating, and an eFuse limit just above a connector's rating at nominal (further above with tolerance; higher still in an earlier version) sat in front of that connector; a cable sold as a data cable had no current rating at all.
- Cost: contacts overheating under fault; limit values and a cable changed at review.
- Check: In the interconnect table, compare the current per contact at the worst fault the protection lets through, using tolerance ranges, never nominal values. Use two contacts per rail where needed, feed secondary loads from the board rather than through another board, and buy only cables with a stated current rating.

### Voltage at the load pins not budgeted
- Happened: At the low tolerance corner during a load step the host saw less than its under-voltage threshold at its input pins, and on the bench a wire path of a fraction of an ohm left it little margin; a remote load at the end of a long thin cable got less than its minimum supply.
- Cost: the host flagged a low supply under load, and a harness length rule was added late.
- Check: Budget the voltage to the LOAD pins: regulator tolerance, load step, board copper, contacts, harness both ways and the return. Fix harness length and gauge in the interconnect table, and publish the supported cable range for remote loads.

### Plugs that fit the wrong way
- Happened: A small housing on a larger unshrouded header could be offset or turned, putting the supply on a GPIO; another plug could sit turned 180 degrees with the supply on ground or on a logic pin, and a 2-pin header still fitted turned round.
- Cost: a destructive mis-plug risk at every assembly; designs changed to soldered wires, full-width housings and orientation marks.
- Check: Do a mis-plug analysis for every connector and harness. Never use an unkeyed plug where any mis-mate is destructive; use one latching, polarised connector family, mark pin 1 at both ends, and add a silk orientation mark that matches the housing's asymmetric feature.

### Mating side and connector role taken on trust
- Happened: A crimp housing was picked female for a header that is also female, and a hole pitch was accepted as "surely 2 mm" without a drawing; a USB-C receptacle was used as an always-hot 5 V output, so a C-to-C cable to a laptop would have put the board's 5 V on its VBUS.
- Cost: a part chosen twice, a harness redesigned, a standard connector misused.
- Check: Confirm gender, pitch, pin numbering and keying from the mating board's drawing or a photo before choosing a part. Do not use a standard connector whose implied role differs from the real one, and for each harness state the role and required termination of every pin under that connector's standard.

### Buy or design decided without numbers
- Happened: Two loose modules were weighed against an own board only late in the work; later a "merge all boards into one" idea could be answered only with a BOM and design-cost comparison.
- Cost: a late architecture change.
- Check: Fill the buy-or-design table in phase 2: per-unit cost at several volumes, design effort and prototype rounds, availability of documented ready modules. Recommend, then wait for the user's go.

### No area budget
- Happened: The first outline was smaller than the parts' courtyards alone, and with routing the board needed about two-thirds more area than the courtyards.
- Cost: the outline changed twice and two layouts were thrown away.
- Check: Before the mechanical outline is frozen, sum the courtyards after the passive-size decision, aim for at most 55 to 60 percent fill on a one-sided power board, add routing channels and label space, and hand the result to phase 8.

## Phase 3: part selection

### Stock and lifecycle not checked per line
- Happened: An LED with zero stock was kept "anyway", a current limiter had barely enough stock for the batch plus attrition, an off-board header housing was not recommended for new designs, and another chosen part was a non-catalog item; two passives showed 0 at LCSC but plenty in JLCPCB's assembly stock.
- Cost: parts changed after the full design, and the user's trust in the BOM.
- Check: Run `scripts/jlc_parts.py` on every line, off-board parts included: assembled parts against JLCPCB assembly stock, hand-fit and off-board parts against LCSC; need = boards x per-board count x (1 + attrition) plus spares; lifecycle status; flag any line under 10x the need. Date the report and re-run it on the gate 2 day and the order day.

### A part named by description only
- Happened: A switch was recommended as "in stock at LCSC" by maker and series name; it could not be found without its reference.
- Cost: the user's time and a choice the design had not checked.
- Check: Give every recommended part its LCSC number, maker part number and link, plus one verified alternate. Write the mounting orientation (for example a vertical switch, ON up) next to switches and connectors.

### LED variant and pad map unchecked
- Happened: The substitute bicolour LED was common cathode while the low-side drive needed common anode, and the dual-colour side LED's library pad map was unverified, so an anode could have landed on a cathode pad.
- Cost: a wrong part nearly ordered.
- Check: Check common anode against common cathode against the driver topology, and map every pad of a multi-die LED or array to the maker's drawing before the part enters the schematic.

### A limiter's minimum below the load
- Happened: A feed to an external load used a load switch whose minimum current limit lay inside the range such loads typically draw, while the load's own current had never been measured.
- Cost: a possibly unpowered load; the part changed after the full design.
- Check: Make the MINIMUM trip of every limiter exceed the worst load current with margin. Bound an unknown load from vendor data, write it as an assumption, and put its measurement on the bench list.

### Timing and capacitance taken at nominal
- Happened: A shutdown timer built from a 555 and X5R capacitors ran from its design time to many times longer or never, from threshold spread, DC-bias loss and diode leakage doubling every 10 deg C; a required 1 uF input capacitor in 0603 X5R kept only 0.35 to 0.5 uF at its working voltage.
- Cost: unsafe shutdowns or a device that never turns off; replaced by a counter-based timer.
- Check: Compute worst-case timing over threshold spread, capacitor tolerance, DC bias and leakage at the maximum temperature, and build long timeouts from a counter or oscillator, not a leaky RC. For every capacitance a datasheet requires, check the effective value at the real bias and temperature.

### Temperature derating ignored
- Happened: In a box assumed at 50 deg C the design used a 0 to 70 deg C timer chip, 85 deg C X5R capacitors next to the converter and an 80 deg C USB-C receptacle carrying its full rated current; a resettable fuse held only about half its rated current at 70 deg C, less than its load, while a small load got a fuse rated about ten times its current because that BOM line already existed.
- Cost: nuisance trips when warm, or faults that never trip; several parts changed at review.
- Check: Write the enclosure ambient as UNKNOWN until measured and design to a stated assumption. Check temperature grade, lifetime and derating at the local temperature; size each PTC to its own load (hold above the load at the maximum local temperature, trip below the contact and wire rating); write placement constraints for heat-sensitive protection parts into the layout rules ledger.

### Ratings sized on the average
- Happened: A part was first sized on a typical figure printed on a label, while the worst-case continuous level was far higher, and higher again with tolerance spread.
- Cost: a part that would have run beyond its rating; caught only because the user challenged it.
- Check: Size every rating on peak and worst case (gain spread, tolerance, fault), never on a typical or average figure, and write which one each published spec states.

### A "drop-in" substitute that was not
- Happened: Load switches of one family differ (one has no blanking, another an active-high enable); TL431-class references in SOT-23 come in different pin orders and two accuracy grades under one marking; a cheaper TVS clone had different clamp tables, and a "similar" edge-mount connector would not have fitted the ordered board and the panel wall.
- Cost: hidden function and fit changes, caught in reviews.
- Check: Before any substitution read the family comparison table, compare clamp and derating tables and re-verify the pin order. For a part that mates the board to a case, check thread length, flange thickness, leg length and pin height against the board and the wall. List every substitution to the user.

### A value that had to change shared a BOM line
- Happened: A resistor whose value later had to change shared one BOM line (one LCSC part) with other designators; after the order the assembler could only change or leave out the whole line.
- Cost: the order on hold and days of e-mails.
- Check: Give any designator whose value may change, be left unfitted or be substituted its own BOM line, even with the same part number; share a line only for values that can never change. `scripts/jlc_parts.py` lists shared lines for the phase 12 BOM audit.

### Cost shown as parts only
- Happened: For 5 assembled samples the parts were a small share while fixed fees dominated (an extended-part fee per part type, setup, stencil, through-hole work, shipping, VAT), and through-hole connectors could move the order to the dearer assembly type; thermal tape, foam and gaskets had no BOM line at all.
- Cost: an estimate that rose by about a quarter as reviews added parts, and a heatsink left unfitted for lack of tape.
- Check: Build the cost model with per-part and per-order costs apart, count extended lines and look for a basic or preferred equivalent of each, price both assembly types, use retailer handling-fee thresholds, and give every consumable and hand-made item a BOM line with source, price and method.

## Phase 4: datasheets and rules

### The maker's reference circuit was not compared
- Happened: Each key chip was compared with its maker's application circuit and evaluation board only after the user asked; the comparison found an eFuse output missing its recommended ceramic and Schottky, a PD controller missing its input series resistor and CC capacitors, and missing bypass and boot parts.
- Cost: a full extra round of fixes and re-simulations.
- Check: Fill `REFERENCE_CHECK.md` for every key chip against the datasheet AND the evaluation board's schematic and BOM: every recommended or "should" part is present or its absence is justified. The schematic-datasheet review repeats it independently.

### Protocol behaviour misread
- Happened: The USB-PD sink controller requests its set current at whatever voltage it selects, so on some chargers the device would have drawn more than its contract, and the design loaded the input during the voltage transition; the schematic reviews had checked the current setting but not this rule.
- Cost: an over-drawn contract found only at gate 2, and a resistor changed late.
- Check: For every chip that negotiates or sequences, write its behaviour as a table: what it requests at each level, what it falls back to, when it resets. Prove per level that the load never exceeds the request, and gate downstream converters on "input valid".

### Look-alike pin orders
- Happened: TL431-class shunt references in SOT-23 exist as REF-K-A and K-REF-A under similar names, so after the order the protection reference had to be traced from symbol through footprint and BOM part to the assembler's preview.
- Cost: a reversed protection IC if wrong; hours of tracing after the order.
- Check: Write a pin table per IC from the exact part number's datasheet, lock that part number, and check symbol to footprint to BOM to assembly preview for every IC and polarised part. Repeat it on any substitution.

### Only the absolute maximum checked
- Happened: A pull-up sat above a pin's recommended range though below its absolute maximum, and a timer input was driven above its own supply through a clamp diode on every OFF edge.
- Cost: parts working outside their recommended range in normal use.
- Check: Check every pin against the RECOMMENDED operating range in normal operation, every repeated switching edge and its injected current included, not only against the absolute maximum; only one-off events (hot plug, surge, a fault) are judged against the absolute maximum.

### Conditional clauses skipped
- Happened: A load-switch datasheet asks for bulk capacitance "if the supply is more than a few inches away" while the supply was several times that far and the effective capacitance was small; an LDO maker showed only electrolytic output capacitors and gave no ceramic stability statement.
- Cost: possible droop and instability, caught as review notes.
- Check: Read every conditional clause and stability condition against the real installation (cable length, source impedance, output capacitor ESR) and prove it by simulation or a bench item.

### Rail capacity from the wrong table
- Happened: A host 3.3 V budget was taken from a limit that concerns signal pins, and a load's under-voltage threshold was taken from another product's datasheet.
- Cost: budgets nobody could defend; both became bench checks.
- Check: Use the rail's own specification for the exact model. Label every inferred limit (for example one taken from a related part) as inferred, and put its measurement on the bench list.

### Ratings copied without their conditions
- Happened: A MOSFET's avalanche energy was written as its pulsed current and an inductor's saturation current one ampere above the datasheet's value; fuse hold figures were wrong with their datasheets missing, and a limiter's short-circuit current was taken at the spec point though its curve shows 12 to 14 percent more at full drop.
- Cost: wrong margins in the design note, corrected at review.
- Check: Copy every rating with its symbol, unit, conditions and page, read fault stress from the curves, and store every datasheet in `vendor/datasheets/` (fetched with `scripts/fetch_parts.py`).

### Layout rules not collected from the datasheets
- Happened: The converter's single-point quiet ground, decoupling distances and switch-node area were first checked at the layout review, which found the quiet ground tied in three places and capacitors 3 to 4 mm from their pins.
- Cost: a layout fix round.
- Check: Write `LAYOUT_RULES_LEDGER.md` in phase 4 with each datasheet layout rule, its page and how it will be checked. The layout-electrical review checks it rule by rule.

### 3D models and land patterns of unknown origin
- Happened: A summary claimed "real supplier models" while some bought parts were still plain blocks; maker sites blocked automated downloads, and imported connector models had their origin at pin 1.
- Cost: wrong fit pictures and a connector drawn over a screw.
- Check: Record per part the source of its land pattern and 3D model (maker, JLCPCB/LCSC library, or built from the drawing), fetch by LCSC number with `scripts/fetch_parts.py`, say plainly which parts are still stand-ins, and where a site blocks the download take the next source (`references/working-rules.md` section 7) before giving the user the link.

## Phase 5: schematic

### Two nets merged by a shared name
- Happened: The converter switch node and a switch-wire node were both named SW on different sheets, and the generator made every cross-sheet name global, merging them; ERC passed because all pins were passive, and an "all connections match" check compared the netlist with its own generator.
- Cost: at first power-on a resistor would burn and the input voltage would reach a small MOSFET gate; caught by the first independent review.
- Check: Make the generator fail on a net name used on two sheets that is not in an explicit global list (and on stale list entries). Check the exported netlist with `scripts/netlist_check.py` against the hand-written expected connectivity, never against the design source, and keep its mutation self-test (a merged net must fail).

### Connectivity check blind to pin names and pads
- Happened: The connectivity check compared neither symbol pin names with the datasheet nor symbol pins with footprint pads; a counter IC's symbol had two pin names swapped, and an ESD diode had no footprint, so it would have vanished from the board and the placement file.
- Cost: errors found only by a reviewer working by hand.
- Check: Check three layers: intended net, pin function name, footprint pad number. The schematic lint fails on any part without a footprint, and the schematic-datasheet review compares symbol pin names with the datasheet table.

### A schematic only a machine could read
- Happened: The generated sheets scattered parts and joined them only through net labels, so the user could not read or service them, and the same style had hidden the merged net; the redraw as wired blocks took about 2.5 hours with one sample sheet first and a netlist equality gate.
- Cost: a full redraw after the order.
- Check: Draw wired functional blocks from the start per `schematic-style.md`, with expected voltages, thresholds beside the parts that set them, and connector pin tables. Approve one sample sheet first, and gate any redraw with `scripts/netlist_compare.py` against the reference netlist plus ERC.

### Logic levels checked one way only
- Happened: A series protection resistor from a processor's TX to a peripheral's RX blocks data when the peripheral's internal pull-up is too strong for it (the two form a divider), and a back-feed fix sized for 3.3 V levels failed at the 5 V TTL level the peripheral's datasheet also allows; an open-drain shutdown line had no pull-up on the board.
- Cost: a change after the order, and a line floating during boot.
- Check: For every interface compute VOL and VIH at the receiver with its internal pulls, in both directions, at every level the counterpart's datasheet allows, before the BOM is frozen. Pull an open-drain line up to a rail that every pin on the line tolerates, also while that device is unpowered, and that meets every receiver's high-level input voltage; otherwise use a level shifter.

### Reset that did not re-arm after a brown-out
- Happened: The power-on reset capacitor kept its charge after a brief input loss, so the latch state after a brown-out was random; the auto-start margin was about 1 ms and turned negative when a CMOS timer replaced the bipolar one.
- Cost: a device that might not start; fixed at review.
- Check: Give every power-on reset a discharge path and test it after short drop-outs. Recompute every timing margin when a part is swapped between bipolar and CMOS versions.

### A filter changed the order of protections
- Happened: A capacitor added on an enable pin made the eFuse under-voltage lockout 100 to 200 ms slower than the converter's enable, so a sustained sag ended in the fault latch instead of the documented automatic restart.
- Cost: a device that latched off where the documents said it restarts.
- Check: After adding a filter on any enable or UVLO node, recheck the order in which protections fire for dips, sags and drop-outs, and correct the documented behaviour.

### ESD on wires that leave the board
- Happened: A negative step of 3.7 V on the switch wire turned the device on and an 8 kV discharge put about 17 V on FET gates; on a small board only the slow charge-sharing part was computed, while the choke and a capacitor's ground-via inductance put 10.5 V for 2.4 ns on a 6 V IC.
- Cost: possible damage or false switching; fixed at review.
- Check: For every wire that leaves the board, do the ESD budget: the charge-sharing step against thresholds and gate ratings, and the nanosecond inductive transient with the real via inductance. Put the ground via at the capacitor pad, add a TVS where needed, and leave unused protocol pins (such as USB data on a power-only connector) unconnected.

### A threshold voltage read as a guarantee
- Happened: A 2N7002-class MOSFET's Vth of 1.0 to 2.5 V is specified at 250 uA, so at microamp hold currents it conducts 0.1 to 0.3 V lower; a 3.3 V GPIO drove such a MOSFET, and another MOSFET dumped a 10 uF capacitor at 1 to 2.5 A against a 0.8 A pulse rating.
- Cost: part of the never-off defect, and marginal switching.
- Check: Never treat Vth at the test current as an "off" guarantee for microamp circuits; design for at least 10x the hold current or use a comparator. Use a logic-level FET with Vth(max) well below the drive, and add series resistance wherever a switch discharges a capacitor.

### No tuning provisions; bypass at the wrong band
- Happened: The converter had no boot resistor, snubber or loop-injection footprints, and the 1 nF connector capacitors self-resonate near 200 MHz, so nothing filtered the victim band far above that.
- Cost: no way to tune emissions on the bench without a respin.
- Check: Reserve 0 ohm or DNP footprints for a boot resistor, a switch-node RC snubber and a loop-injection resistor. Choose bypass capacitors by their self-resonance at the victim band, computed with their mounting: pads, track and ground via shift the resonance well below the bare part's value (`references/pcb-rules/power.md` PWR-38, `rf.md` RF-82).

### Set-points not recalculated from the drawn values
- Happened: A crowbar trip range was stated too narrow because the reference current error was counted at the REF node instead of at the output (times the divider ratio); the real range was about one and a half times as wide.
- Cost: a protection window wider than documented.
- Check: Recompute every set-point from the values actually drawn, with tolerance stacks referred to the output node; the schematic-datasheet review recomputes them independently.

## Phase 6: simulation campaign

### Simulation only after the user asked
- Happened: The first schematic went to the gate on hand calculation alone; once asked, a few dozen simulations found the input-filter margin, the back-feed, an undersized clamp diode and the output capacitor count.
- Cost: a whole gate repeated.
- Check: Write `sim/PLAN.md` for every power and protection block with the pass limit before the run, run it with `scripts/sim/ngs.py`, and turn every item no simulation covers (protocol behaviour, ESD, emissions, real host rails) into a named bench test. The simulation-coverage review audits the plan against the circuit.

### A pass limit moved to make a test pass
- Happened: A dip test's pass level was moved by applying the source's valid-voltage rule at the board, ignoring nearly a volt of cable and contact drop.
- Cost: a failing case hidden until the layout review reopened it as a deviation.
- Check: Derive every limit from the spec at the right reference point and write it before the run. Never move a limit; a failure becomes a design change or a written deviation the user accepts.

### The model could not show the defect
- Happened: The back-feed simulations used level-1 MOSFETs with no sub-threshold conduction and the unpowered part's rail as an ideal 0 V source, so the defect was invisible; a behavioural 555 forced reset below 2 V and hid an undefined latch region.
- Cost: a never-off device passed simulation.
- Check: Model switched-off domains as floating rails with their own load and every back-feed path, add sub-threshold corners for microamp circuits, and never let a behavioural model hard-code benign behaviour where the datasheet leaves it undefined; write it down as a model limit.

### Stimuli too narrow
- Happened: Power-up was tested with one 1 ms ramp, dips only up to 20 ms, faults only as hard shorts and set-points only at nominal; slow ramps of 20 ms or more failed to start, a sustained sag latched off and partial shorts ran unprotected.
- Cost: four missing scenarios found by the second review.
- Check: Sweep ramp times from 1 to 100 ms, dips by depth times duration including "sag and stay", partial shorts at every output, and every set-point at its minimum, nominal and maximum corners.

### Model limits not listed
- Happened: The averaged buck model could sink large currents (the real part cannot), the inductor never saturated, the eFuse model switched off in 0.1 us against 25 us real, and the PTC model derated more gently than the datasheet table; the maker's models were encrypted, and a long power pour's parasitics were never fed back.
- Cost: optimistic results in the protection simulations.
- Check: List every model limit beside its result and re-run critical protection cases with pessimistic variants. Fit thermal models to the derating table at the maximum local temperature, calibrate behavioural models on a published measurement, and re-run with long power-path parasitics after layout.

### Protection simulated without the protector's stress
- Happened: The crowbar simulation recorded neither the crowbar FET's peak current, I2t and energy nor the voltage at each load connector, and "about 50 A" in the notes was wrong (0.9 kA in the zero-inductance model).
- Cost: an unverified clamp device and connector overshoot found after the order.
- Check: Record for every protection simulation the stress in the protecting device (peak, I2t, energy against SOA and avalanche rating) and the voltage at every load connector; size freewheel and clamp diodes from the simulated fault current.

### A protection simulation contradicted the function
- Happened: The back-feed simulation assumed a peripheral pull-up as strong as the chosen series resistor, a pair that blocks the data, a function nobody simulated.
- Cost: a change after the order.
- Check: Make stimuli match the functional requirement, and beside every protection simulation that changes a signal path, check the normal logic levels too.

### Runs that did not run cleanly
- Happened: A first hot-plug run had not converged (an ideal switch) and pre-charged the load through the switch's off-resistance; parallel runs collided on shared temp files, and model paths with spaces broke the includes.
- Cost: wrong numbers that nearly reached the design note.
- Check: Look at every plot before using a number, ramp ideal switches and add bleed resistors. Run each process in its own temp folder and quote every model path; `scripts/sim/ngs.py` does both and checks convergence.

### Input filter against the converter
- Happened: The damping electrolytic sat on the eFuse side of the input filter, so with a stiff source the filter resonance peaked only 6.5 dB below the buck's negative input resistance; on the converter side it gave 16.5 dB.
- Cost: a possibly oscillating input stage.
- Check: For every switching converter with an input filter, simulate the filter's output impedance against the converter's negative input resistance at minimum input voltage and maximum power, over source impedance, ESR and DC-bias corners.

## Phase 7: schematic reviews

### Ready on ERC alone
- Happened: The first schematic gate was presented as ready with ERC at zero errors and a self-consistent netlist check, while only one of the sheets had been read closely and no independent review had run.
- Cost: the critical merged net would have reached layout.
- Check: Never call a schematic ready on ERC. Gate 1 is the checklist in `phases/07-schematic-reviews.md` with the three schematic reviews closed; state exactly what was and was not reviewed.

### Reviews without an edge-case scope
- Happened: The user had to remind the agent that reviews must cover interactions and edge cases; the written list (power-up and power-down order, charger events, switch abuse, host crash, load steps, output shorts, weak chargers, power banks, ESD, 50 deg C ambient) then drove most findings.
- Cost: without it, the back-feed and soft-short defects would have stayed.
- Check: Write the edge-case list into the schematic-system brief and require a scenario table in the findings.

### Reviewers fed the designer's conclusions
- Happened: Reviews worked when run on a frozen copy, report-only, with the designer's doubts listed but marked "not taken as given"; the strongest reviewer parsed the netlist with its own code and re-ran the simulations from its own scripts.
- Cost: a reviewer who accepts the designer's claims re-checks nothing.
- Check: Freeze a copy by checksum, give reviewers files and no conclusions, keep them from seeing each other's reports, and require them to re-run key simulations themselves.

### Fixes not re-checked by the finder
- Happened: The verification round after two schematic reviews closed all findings but one and found several new ones caused by the fixes; on the layout side, separate fix rounds per reviewer were slower than one combined round.
- Cost: new defects that the designer's own closure would have missed.
- Check: Fix all findings in one combined round with a response table per ID. Each fix is re-checked by the reviewer who raised it ("correct, complete, new problem introduced?"), and new findings start the next round.

### One part changed, its limits not rechecked
- Happened: A new USB-C receptacle was placed behind an eFuse limit above its rating; the limit was then lowered, which changed the behaviour with one charger type.
- Cost: a late trade-off that a full recheck would have weighed earlier.
- Check: Whenever a part or connector changes, recheck every limit, protection and simulation that involves it. After any schematic change re-run ERC, the connectivity check, the affected simulations and the stock check.

### Documents drifted from the design
- Happened: After fix rounds the harness pin legend, a keep-out size, the rotation table and bring-up rows still showed old values and the new revision letter was missing from the title block; a note claimed a latch "powers up defined" where the model had forced it.
- Cost: wrong bench instructions and lost trust in the documents.
- Check: After every fix round search every document for each changed value, keep the revision string in one place, generate tables from the same data as the outputs, and never claim more than the evidence shows.

## Phase 8: board definition

### Routing started on an unsettled outline
- Happened: An L-shaped board was routed while the enclosure was still changing; when the user asked for a deeper box and a rectangle, the routing, silk positions and placement scripts, all written in the old coordinates, were lost.
- Cost: hours of routing and a restart.
- Check: Freeze the outline, holes with keep-outs, connector edges and cable directions, height zones and layer stack before any routing, and derive script coordinates from mechanical anchors. For a small board in a tight space, fit-check an outline-only proposal in the 3D assembly before circuit work.

### Outline with slots, an L-shape and a neck
- Happened: The L-board had a slot for a lid screw block and a narrow neck that every long control net had to cross; most of a night went into that congestion, and raising all boards to one stand height removed the slot.
- Cost: a higher fab price and an abandoned layout.
- Check: Prefer a plain rectangle with no slots, and solve mechanical conflicts with stand heights or keep-outs. Reject any outline with a neck narrower than the planned routing channel.

### Two layers on a switching board
- Happened: Two layers were chosen to save money on a board with a multi-ampere buck beside a sensitive circuit, the router left nets for hand routing, and moving to 4 layers cost little on 5 samples; fab options also changed with the layer count (no tented vias on 4 layers, free filled via-in-pad only from 6).
- Cost: a full re-route.
- Check: A board with a switching converter gets 4 layers, because a ground plane next to the parts is the better-performing choice (PWR-05). 2 layers are accepted only when all three hold: the converter's own maker shows a 2-layer layout with its measured results (an evaluation board on 2 layers); that layout is copied (hot loop, ground, keep-outs); and no receiver, antenna or sensitive analog input shares the board. In every other case 4 layers. A board with a radio or a sensitive analog input also gets 4 layers by default (the exits are in `phases/08-board-definition.md` step 9). A simple board with none of these may be 2 layers. Show the user the price difference in either case. Where 4 layers are chosen, both inner layers are ground (GEN-03). Read the via covering and via-in-pad options for the chosen layer count in `jlcpcb/capabilities.md` before planning thermal vias.

### A mounting hole under a connector
- Happened: A connector's body partly covered a mounting hole, and on the next board the hole keep-outs were not the full diameter on every copper layer, a via and tracks sat inside one and a fuse courtyard touched another.
- Cost: a screw that cannot be fitted; found by the user on a render.
- Check: Give every hole a keep-out on both sides big enough for screw head, stand and screwdriver, on every copper layer, as a polygon that circumscribes the circle; no body, mating housing, cable exit, track or via inside. `scripts/body_check.py` and the layout-mechanical review check it in 3D.

### Parts in the rail zone of a slide-in case
- Happened: A board for a slide-in extruded case had parts inside the rail zone along its side edges.
- Cost: the first sample could not be inserted; the board was laid out again.
- Check: Ask at the start how the board is held. Reserve the free bands from the case drawing before the outline is frozen, draw the section of the case profile with the board, and check the edge bands on both sides (`scripts/body_check.py`, and by looking).

### Panel connectors not checked through the real wall
- Happened: The USB-C jack and LED sat too far inside the board for a plug to seat through a thick rear wall; the maker's PCB-edge line for the receptacle lay millimetres in front of its locating holes, and a thin flange hung below the board top.
- Cost: a layout change and a raised land added to the wall.
- Check: For every connector that mates through a panel, draw a section with the real mating plug (overmold included), derive the board edge from the maker's edge line and model overhanging flanges. For threaded panel connectors write a thread budget (wall, washer, nut, mating plug) with the maximum panel thickness, and pick round or D-shaped holes from the drawing before the cut-outs freeze.

### Interface numbers typed by hand into the case CAD
- Happened: Board outline, holes and connector positions were passed to the enclosure model by hand, so a board edit could silently break the wall cut-outs for a connector and a light.
- Cost: a fit that no check protected.
- Check: Generate one interface file from the board with `scripts/interface_export.py` (outline, holes, connector faces, heights, with board and STEP checksums); the case model reads only that file, and a fit check fails on any mismatch.

### Mechanical data guessed
- Happened: A panel-part hole was a guess where the datasheet gave another size, and a third-party module stack was built in the wrong order without reading the maker's assembly guide; a vendor 3D model also showed a different cable than the real module, and a heatsink in the model was lower than the one bought.
- Cost: a full regeneration of the 3D set and every picture made from it.
- Check: Mark every dimension as sourced (drawing, caliper) or estimated, and take cut-outs from the drawing. Build third-party stacks from the maker's assembly guide, check modules for parts on both faces and pins below, prefer the user's photos over vendor models for cable positions, and reconcile the model with the part actually bought.

### Fastener access not modelled
- Happened: One screw could not be reached because a lid screw block sat in the screwdriver line, a pan head touched a pin header, and connector spacing left less than the wrench width for the nuts; a screw assumed to be M2 was really M2.5.
- Cost: a clamp and a new assembly order invented during assembly.
- Check: Model the screwdriver line and wrench space for every fastener, write a fastener list (type, length, head diameter) checked against neighbouring parts, write the assembly order, and ask the user to measure fasteners where they are assumed.

### Assembly scope and edge rules decided late
- Happened: Through-hole parts were moved to hand soldering late, and on a small board parts sat 0.4 mm from the edges while the assembler needs bodies at least 2.5 mm from the edges its conveyor holds, which forced a panel with rails.
- Cost: a panel design and new pads late in the flow.
- Check: Ask in phase 8 which parts the assembler places, give hand-solder parts long pads and keep-outs, and check the assembler's edge-clearance rule so rails or a panel are planned at once.

### No room planned for silkscreen
- Happened: The information block was squeezed among connector labels, and after all relocations several parts had no legal spot for a label.
- Cost: several visual review rounds and written waivers.
- Check: Make the silkscreen plan part of phase 8: propose the identification block (company, model, revision, date code), reserve a free area for it, and count label space in the area budget.

### Connectors placed without looking at their wires
- Happened: On a small two-layer board the spare screw terminals were put in a second row behind the main connectors; the body of the connector in front stood just before their wire entries.
- Cost: a fix round that could only half free them, and a written limit to thin wires.
- Check: Choose each connector's edge and place from where its cable or wire goes (shortest route, nothing crossed, every wire entry free), put lights and buttons where the user sees and reaches them, and show all of them in the outline picture the user confirms (`pcb-rules/connectors-mechanical.md` MECH-26; with an enclosure, MECH-07).

## Phase 9: layout and 3D

### Library footprints trusted
- Happened: Library footprints for a 2.5 mm pitch header family used 2.54 mm (a long header's end pins about a quarter millimetre off) and wrong hole sizes; two inductor land patterns and the SC-70 and 0402 wirewound patterns differed from the makers' recommendations.
- Cost: headers that would not insert.
- Check: Audit every footprint against the maker's drawing with `scripts/fp_audit.py` (pitch, pads, drill, pin 1), use the maker's land pattern for power magnetics and record the drawing, confirm the assembler's footprint lands within 0.1 mm, and save any modified library footprint as a project copy with its own name.

### Courtyard smaller than the part
- Happened: Several imported courtyards followed the body and were smaller than the pads, so the courtyard check could not see a part placed on those pads, and a bent LED's lens lay outside its courtyard.
- Cost: overlaps no check could see.
- Check: Make every courtyard cover the pads and the whole 3D body, bent or overhanging parts included, plus a margin; `scripts/fp_audit.py` flags smaller ones.

### 3D model origin at pin 1
- Happened: Imported connector models had their origin at pin 1 and were placed with no offset, so one connector body sat millimetres toward a mounting hole in the 3D file while its pads and courtyard were right; a script reported it clear.
- Cost: a connector over a screw; the user found it on a render.
- Check: Verify each imported model's origin and rotation against the footprint, run `scripts/body_check.py` (every body inside its courtyard, nothing in a hole's keep-out cylinder, mated housings and cable exits at least 1 mm away), and look at the renders.

### Decoupling placed after everything else
- Happened: Band bypass capacitors and a controller's decoupling ended 3 to 4 mm from their pins, and the input capacitors' ground ends did not face power ground.
- Cost: weaker filtering, accepted as deviations.
- Check: Place decoupling first, at its pin, each with its own ground via; keep a measured pad-to-pin table and a hot-loop orientation table, and record the physical limit when a target cannot be met.

### Ground integrity under the converter
- Happened: The first layout had tracks on the plane under the buck and a larger switch node than needed, and long parallel tracks fenced off a ground island no via could reach; fingers and small isolated copper pieces stayed after the fill.
- Cost: noise risk and a layout round.
- Check: Keep a solid reference plane under every switching loop with no tracks on plane layers, minimise the switch-node copper, avoid long parallel tracks that fence off pour, set a minimum zone width, and run `scripts/zone_check.py` after every fill.

### Quiet ground tied at three points
- Happened: The converter's analog ground joined the main ground at three points instead of one, because a via poked 0.15 mm past the island and a resistor pad straddled its edge; one power-ground via sat in the island's cut-out and never reached the plane.
- Cost: noise in a sensitive band; found by the second layout review.
- Check: Prove every single-point ground with a cut test: close the one bridge in a copy, refill, and confirm the quiet copper becomes unconnected (`scripts/zone_check.py`). Verify that every power and stitching via lands in its intended plane.

### Wide feeds routed last
- Happened: A wide supply feed on the bottom layer blocked the last millimetre of a long bus net, the autorouter struggled on the final connections, and a router clearance margin of 0.05 mm produced real DRC errors.
- Cost: hours of lifting and re-routing.
- Check: Route in order: pours and wide nets by hand, hand-picked crossing nets, long control nets, then the short nets by router. Set router clearance to the rule plus half the track width plus a margin, and run DRC after every routing stage.

### Track width checked at nominal current
- Happened: The input band ran at 0.9 times the width needed at the current-limit maximum, and the eFuse output left through a sub-millimetre stub; the input track ran 13 to 17 deg C warm.
- Cost: hot copper, fixed with a parallel copy on another layer and pour necks with thermal vias.
- Check: Fill the current and voltage-drop worksheet at the maximum current the protection allows, counting parallel layers and both paths; let power pours reach package pads directly; run `scripts/neck_check.py`.

### RF return vias missing
- Happened: The nearest ground via to a coax landing's centre pad was several millimetres away, and a rebuild placed only part of the planned fence vias because the text keep-outs used KiCad's enlarged text frame.
- Cost: a broken RF return, found at review.
- Check: Place ground vias along every RF line at the spacing of `references/pcb-rules/rf.md` RF-11 and on both sides of each transition, and count fence and stitching vias after every rebuild against the planned number (`scripts/zone_check.py`).

### Labels placed after routing
- Happened: Dozens of silk texts ended over vias because the router knew nothing of the labels, and a protection transistor later had to move to free a label column, with a re-check by the layout reviewer.
- Cost: label churn through several visual rounds.
- Check: Place labels before routing and keep vias at least 0.1 mm from planned labels. Electrical placement always wins over labels; raise only the cases where a silk need conflicts with an electrical constraint.

## Phase 10: designer's checks

### DRC clean, Gerbers with copper at the edge
- Happened: The fill was saved before the 0.30 mm edge rule applied; KiCad's DRC reported 0, while the board file and the Gerbers had copper up to the outline. (The command-line check judges the saved fill but, in KiCad 9, reports no fill that is too near the edge; a check that refills works on a copy in memory. Either way the file on disk was never judged.)
- Cost: fab rejection or shorts at the edge.
- Check: Run `scripts/edge_check.py` on the exported Gerbers of board and panel, corner arcs included, and stop on any failure; set the rules before the first fill and draw zones inside the edge.

### DRC rules too soft
- Happened: DRC enforced no power track widths (connection width and slivers were only warnings), a custom rule let through-hole ground pins connect with a single thermal spoke, and the courtyard checks were switched off.
- Cost: defects DRC would never report.
- Check: Run `scripts/drc_run.py` with the `jlcpcb.kicad_dru` template: net-class widths per layer as errors, at least 2 live spokes per layer, courtyard rules as errors, schematic parity, all severities.

### A rule that never fired
- Happened: A board's custom rule "silkscreen text to pads" carried a layer line that matched nothing, so it never fired, and nobody had planted a violation to see it. KiCad also drops a whole rule file without a message when one line has a syntax error, and reports a clean board; and with no schematic given it reports schematic parity as 0.
- Cost: a "0 errors" result that checked nothing.
- Check: `scripts/drc_run.py` proves with a planted violation that the rule file loaded and says CANNOT RUN when parity has no schematic; plant one violation per custom rule on a copy after every edit of the rule file (phase 9, step 3).

### DRC blind to pour necks
- Happened: KiCad's connection-width check does not see necks in pours, so a deliberately narrowed neck passed and a power input entered a part's land on a thin track; the current worksheet also added two series sections as if they were in parallel.
- Cost: hidden current bottlenecks behind a "DRC covers the pours" claim.
- Check: Run `scripts/neck_check.py`, which cuts each power path's copper every 0.1 mm and rates the narrowest cut with series and parallel explicit; prove it flags a planted narrow neck; record package-limited necks with an infrared bench check.

### A checker trusted without controls
- Happened: The first single-point-ground cut test reported FAIL on every board because it wrote a polygon KiCad could not read, and a custom via rule flagged many fan-out vias that were tangent by design.
- Cost: hours chasing false results.
- Check: Give every new check a planted-defect copy that must fail and a known-good copy that must pass before trusting it, and keep both in the check suite.

### Vias in or touching pads
- Happened: Vias overlapped or touched SMD pads (a ground pad, a capacitor pad, a test point), and a stitching via landed on a load switch's ON pad.
- Cost: solder wicking and a stuck enable; fixed before the order.
- Check: Add the DRC rule "via hole at least its annular ring away from every SMD pad, any net", prove it on a board known to contain the defect, and reject vias in or touching any pad, except thermal vias inside an exposed thermal pad as the maker's drawing shows (DFM-40).

### Router artefacts and an open net
- Happened: After routing, a narrow slot loop, an acute stub, a sharp V and hundreds of staircase segments remained, and a 3.3 V net was left unconnected to a pull-up pad.
- Cost: acid traps and a missing connection caught only by parity.
- Check: After every routing stage run DRC with schematic parity and no unconnected item but the nets not yet routed (zero at the end), and detect acute angles, slots, stubs and loops with the layout helpers' clean-up stage.

### Silkscreen measured the lenient way
- Happened: The designer measured silk-to-via on the strokes and passed, while the reviewer measured text bounding boxes and found text almost touching via copper; library silk lines of 0.12 mm were below the fab minimum, and LCSC and part-number fields printed on the top silk.
- Cost: clipped or unreadable silk and another fix round.
- Check: Run `scripts/silk_check.py` on bounding boxes: silk to pad 0.2 mm, to holes and through-hole pads 0.5 mm, to vias 0.1 mm, to the edge 0.4 mm for text and 0.2 mm for outlines, text at least 1.0 mm high; line: 0.15 mm was the minimum recorded in 2026-11, use 0.16 mm or more for new work and re-read the live minimum. Widen library silk to the fab minimum and move non-reference fields off the silk layers.

### Script said clear, the picture said otherwise
- Happened: Courtyard and clearance scripts passed a connector over a screw and the label placer passed group texts that named the wrong parts; the assembly drawing piled references at the board origin while all checks were clean.
- Cost: defects only eyes found.
- Check: Run `scripts/review_images.py` and open every render, plot, crop, the assembly drawing and the panel render; write what you saw with crop paths. Allow only named mating contacts with volume limits in clash checks, and treat a check that cannot run as FAIL, never as skipped.

## Phase 11: layout and visual reviews

### No review of the board pictures
- Happened: The first layout reached the user with labels colliding with parts, the information block squeezed and a hole covered; once two independent reviewers worked from images only, they found major label problems the scripts had passed.
- Cost: the user acting as the visual inspector.
- Check: Run two visual reviews from images only (renders top, bottom and angled; silk and copper plots; zoomed crops of every hole, connector and label cluster) per `review-briefs/visual.md`, and fix and re-render until they find nothing.

### Labels that read as another part's
- Happened: Labels such as "TP4 3V3" and "R21 U2" read as one name or as the wrong part's, one designator was stacked on another, and automatic group texts such as "R7 R30" put a name beside the wrong part.
- Cost: a board a technician would misread.
- Check: Enforce ownership: each label's centre at least 0.2 mm nearer its own part than any other, at least 1.0 mm end to end between labels of different parts on one line, one text per test point, no automatic group texts (`scripts/silk_check.py` plus the visual review).

### Pin legend off by one
- Happened: A connector's pin legend was shifted by one pin, and another legend still named a pin role that a harness change had removed.
- Cost: wrong wiring by anyone reading the board.
- Check: Generate pin legends from the current netlist, one label centred on each pad, and check them against the schematic in the visual review.

### Polarity marks missing, doubled or on vias
- Happened: An IC had no pin-1 mark outside its body, a library footprint carried a second tiny pin-1 dot on the pad that the fab would clip, and an LED's colour mark sat on a tented via.
- Cost: orientation errors at hand assembly and inspection.
- Check: Give every polarised part exactly one visible pin-1 or polarity mark outside the body and at least 0.2 mm from vias; the visual review checks each one.

### Reviews ran on copper about to change
- Happened: Two layout reviews were running when the board moved from 2 to 4 layers and had to be stopped; later two fix rounds came after the last re-review, so the reviewed board was not the one to be ordered.
- Cost: wasted reviews, and nearly an order of an unreviewed board.
- Check: Freeze the board by checksum before each review, stop in-flight reviews when the copper changes, name the checksum in every review and in the order, and scope each re-review to the difference.

### Gate 2 without a written checklist
- Happened: The user had to insist that the PCB be accepted only after every kind of review; a review standard the user supplied was then mapped section by section to an owner with PASS, FAIL, UNKNOWN or WAIVED and evidence.
- Cost: a gate that otherwise depended on memory.
- Check: Close gate 2 only on the written checklist (designer's checks, electrical, simulations re-run, layout, visual, mechanical fit, fix rounds closed by the finder, same-day stock). If the user supplies a standard, build a coverage map in which an empty or UNKNOWN row blocks the gate.

### Waivers asked one at a time
- Happened: Parts with no legal silk spot were brought to the user in several batches before one zoomed list was approved, and their fabrication references were then found piled at the corner of the assembly drawing.
- Cost: repeated interruptions and a wrong assembly drawing.
- Check: Bring all waivers to the user once, as a list with zoomed crops, give every unlabelled part its reference on the assembly drawing at the part's centre, and look at the drawing.

### A board that looked finished
- Happened: Reported from other projects: a dense board with programmable logic, fast memory and several supplies, produced by an AI agent, was fully routed, passed the rule checks and looked professional. An experienced engineer's adversarial review found: gaps in the ground plane under signal returns, a poor layout of the memory termination, decoupling capacitors that did not follow the chip maker's guide, too little copper and too few vias around a regulator, questionable routing of a USB pair and placement of an oscillator, and noise risks; and no direct evidence for worst-case circuit behaviour, signal and supply quality, heat or noise.
- Cost: a board that would have been ordered on its looks; faults of this kind show up as random failures on the bench or in the field.
- Check: A routed, rule-clean board is connected, nothing more. Each of pin-out, ratings, supply order, current paths, line impedance, ground under fast signals, decoupling per the maker's guide, heat and noise gets its own evidence in at least two independent ways (script, image, reviewer), shown line by line in the gate summaries (`templates/GATE1_SUMMARY.md`, `templates/GATE2_SUMMARY.md`); what has none is UNKNOWN with a bench test (GEN-19, MCU-08, MCU-15, PWR-62, PWR-63; `scripts/ratings_check.py`, `scripts/return_path_check.py`, `scripts/impedance_check.py`).

## Phase 12: production files

### Rotations from a generic correction table
- Happened: Placement rotations came from a community correction table, so every SOT-23 part would have been placed 90 degrees off (the right correction was 180 degrees against JLCPCB's own footprints) and the input electrolytic reversed.
- Cost: every assembled board scrapped; caught by the second layout review.
- Check: Derive every rotation and origin from JLCPCB's own footprint for the exact part number, pin 1 on pin 1, with `scripts/jlc_rotations.py`; its test re-derives and compares, and the layout-manufacturing review re-derives independently.

### Polarised parts matched by pad number; origins differ
- Happened: JLCPCB's footprint for a Schottky numbered its cathode as pad 2, so matching by pad number would have turned it 180 degrees; some wire-to-board headers needed a body-centre origin, a SOT-89 regulator numbered its tab differently, and one part's X position was off by the centroid convention.
- Cost: reversed diodes and offset parts.
- Check: Match two-pin polarised parts by their polarity mark, fit on unambiguous pads where numbering differs, take the origin convention from JLCPCB's library, and read the pad error per part in the `scripts/jlc_rotations.py` report.

### Stored files changed by line-ending conversion
- Happened: Version control converted line endings in the board and STEP files, so their checksums no longer matched those recorded in the interface file and the reviews.
- Cost: a checksum mismatch just before paying, and doubt about which board was reviewed.
- Check: Store board and production files byte-exact (no text conversion for the hardware folder), and before paying confirm that the checksum of the files sent equals the checksum of the files reviewed.

### Personal data inside exported files
- Happened: Exported STEP headers carried the operating-system user name and the machine name, and board files carried absolute paths into a personal folder.
- Cost: personal data in files bound for a manufacturer, and a failing repository test.
- Check: Run `scripts/privacy_scan.py` on every file before it leaves the PC (Gerber, drill, BOM, placement, STEP, PDF); fix the exporter, not only the file; use project-relative paths.

### Hand-fitted parts left in the assembly files
- Happened: Hand-soldered through-hole parts and a hand-bent LED had to be removed from the BOM and placement file while their pads still had paste, and the panel render showed a hand-fitted connector reaching into the next board.
- Cost: unwanted assembly charges or parts placed twice.
- Check: Mark hand-fit parts "exclude from position files" and DNP in the assembly BOM, remove paste from their pads, list them in the assembly document, and give them no 3D model in the panel.

### Panel by own rules, not the fab's
- Happened: The panel's own tooling holes (of the size one of the assembler's pages gives, while another of its pages gives a different size) were not found by the assembler, whose engineer asked to add its standard ones, and a ferrite sat 0.4 mm from a mouse-bite bridge.
- Cost: an engineering query, and a part that could crack at depanelling.
- Check: Build panels with `scripts/panel.py` with the fiducials JLCPCB asks for and no tooling holes of its own, choose "Tooling holes: Added by JLCPCB" in the order form, keep parts at least 2 mm from break-away bridges, generate panel outputs from the board, and run panel DRC and a panel placement test.

### Shipping conditions read after the first payment
- Happened: The rule that an LCSC order joins a JLCPCB order only if that order ships to LCSC's warehouse was read after the board was paid, and the address cannot change after checkout; a hold period was also stated wrongly as 15 days instead of 7.
- Cost: the first board shipped alone at full freight.
- Check: Before the first payment read the combine-shipping rules end to end (destination, order state, time limits, which orders may join) and decide sequence and addresses for all orders in `ORDERING_CHECKLIST.md`, with a fallback date for each dependency. After checkout verify that the order pages link the orders, or get it confirmed in writing.

### Supplier rules checked on design targets
- Happened: A sheet-metal design passed the builder's own checks, but an independent reviewer who read every rule page and measured the exported files found several failures, among them a nut with no metal under it, a channel 1 mm too narrow and drawings older than the parts.
- Cost: a failed manufacturer inspection, avoided only by that review.
- Check: Run the supplier-rules review on the exported files: harvest every rule page into a sourced checklist, measure the exports with margins beyond the minimums, check that drawings are newer than the parts, and end with PAY, PAY WITH NOTES or DO NOT PAY YET. Repeat it when the supplier changes the process.

### Order choices not written down
- Happened: Edge rails on the long sides only (a connector overhangs one edge), solder mask "as per Gerber, no extra expansion", an expected pitch query and the panel choices were worked out by reviewers instead of an order checklist.
- Cost: a risk of mask opening beside fine pads and an avoidable engineering question.
- Check: Write `ORDERING_CHECKLIST.md` per board: every option with its value, mask expansion and via covering, rails and which edges may be held, overhanging parts, and two or three remark lines that answer known queries in advance.

### Landed cost unknown
- Happened: The sample estimate rose about 25 percent through review fixes, and at payment a faster shipping option and import duty raised another order's total by about a quarter.
- Cost: surprises for the user at the payment page.
- Check: Write a landed-cost estimate per order (PCB, assembly, parts, fees, shipping, duties) before ordering, and record the real total in `ORDER_LOG.md` after payment.

## Phase 13: order at JLCPCB

### An option set by a coordinate click
- Happened: A click by screen coordinates selected untented vias instead of the intended plugged option; it was caught only because every value was read back.
- Cost: a wrong fab option nearly ordered.
- Check: Click by element reference, never by coordinates, and read back every option on the page against `ORDERING_CHECKLIST.md` before saving to the cart.

### A BOM line left unselected
- Happened: The BOM step warned that some lines had no part selected because one connector row was unticked, while the warning on another line was only a small special-component fee.
- Cost: a part that would not have been assembled.
- Check: Select and match every BOM line before continuing, read the exact reason of each warning, and record it in `ORDER_LOG.md`.

### Polarised parts not checked in the order preview
- Happened: The placement preview at the order was the last chance to catch rotation errors, and it was checked part by part only after a review had found the rotation-table bug.
- Cost: scrapped boards whenever the preview is skipped.
- Check: Zoom strip by strip through the placement preview, top and bottom, for every IC, diode, LED, polarised capacitor, transistor and connector against its silk mark, and save the crops.

### Consent boxes and the checkout button
- Happened: The assembly terms box was already ticked by default, a compliance statement box had to be ticked to submit a cable order, and a safety block refused the agent's click on checkout at another shop.
- Cost: none, because nobody worked around them.
- Check: Never tick terms or consent boxes yourself; point out pre-ticked ones and ask. Stop at checkout or payment, give the user the exact steps and the expected total, and never work around a refused click.

### Address and destination wrong or unspoken
- Happened: A storefront's default shipping address was out of date, LCSC and JLCPCB kept separate address books, and a board order set to ship to a consolidation warehouse was not mentioned to the user.
- Cost: a blocked consolidation.
- Check: Check the shipping address in every storefront separately before building carts, and show the destination of every order in the summary given to the user.

### Coupons, fees and duty terms not compared
- Happened: Two coupons did not stack, the preselected payment method carried a small fee that a card avoided, and the shipping options differed in whether import VAT and duties were prepaid.
- Cost: small overpayments and a later duty bill.
- Check: Compare coupons, payment fees and the own-freight-account option, and present shipping as a table (days, price, duty terms) with one recommendation, preferring duties included (IOSS in the EU).

### Cut-off time and status after payment
- Happened: Paying before the fab's daily cut-off decided whether production started the same day, and after payment an automatic "payment failed" mail arrived before the payment was confirmed.
- Cost: a lost day if missed, and confusion over a stale mail.
- Check: Tell the user the cut-off time at the hand-over. After payment read the order page, verify the status changed, and record the order references and landed total in `PROJECT_STATE.md`.

## Phase 14: order and e-mail watch

### The 72-hour placement confirmation
- Happened: Three days after the order the assembler mailed that parts placement was done and must be confirmed within 72 hours or production would proceed as is; the review in the viewer found one IC the assembler had rotated 90 degrees (pin 1 still on pad 1) and a value change e-mailed days earlier that had not reached the placement team.
- Cost: a whole batch at stake within three days, and a user watching a silent screen during the long check.
- Check: Look for this mail daily after payment. Review the viewer (overview, then every strip top and bottom, then 3D) for part, position, pin 1 and polarity, DNP parts really unplaced and each assembler change; save the crops and report progress as "strips done of total".

### Confirm clicked without defined conditions
- Happened: The user authorised the agent to click Confirm, and the agent narrowed it to "only if every part, pin 1 and polarity are right, the DNP part is not placed, nothing is missing or extra and any assembler change is harmless", with a proof screenshot afterwards.
- Cost: none; without conditions, a confirmation of a wrong placement.
- Check: Ask the user once per order for permission to click Confirm, write the pass conditions into the brief, require a screenshot of the new status, and touch nothing else (terms, payment, options).

### A part change after the order
- Happened: A part value had to change after payment; the support form gave no clear confirmation, live chat could not take the request, and the "component replacement" step was gone once the order was in production.
- Cost: days of messages.
- Check: Freeze values before ordering. If a change is still needed, use the order's own remark or the replacement step at placement confirmation, quote both LCSC numbers, verify the request was received, and add the hand-rework fallback to step 0 of `FIRST_POWER_UP.md`.

### Contradictory instructions
- Happened: The user decided to accept a part as placed, but the earlier e-mail asking for a change was not withdrawn, so the assembler put the order on hold for clarification.
- Cost: about a day of delay and a third message.
- Check: When a decision changes, withdraw the earlier instruction in the same thread at once and explicitly, and tell the user plainly when their choice leaves a contradiction open.

### An engineering question answered loosely or slowly
- Happened: The assembler asked how to leave one designator unfitted from a shared BOM line; the reply that worked named the designator to leave out and stated that every other designator on the line stays fitted.
- Cost: each round trip with the assembler cost about a day.
- Check: Summarise the question in 3 to 4 lines, recommend one option with the reason, attach a ready short draft and ask one yes or no; answer within minutes of the go, name every designator that must stay fitted, and list any deviation from the approved text after sending.

### Monitoring that reported noise or missed changes
- Happened: Order checks without a baseline repeated the same states, a push notification was not delivered, and the browser extension had silently disconnected after a reboot.
- Cost: noise for the user and missed messages.
- Check: Make a baseline of all orders on the first check in ORDER_LOG.md's table, report only changes, set an auto-expiry, verify that each push was delivered, and check the browser connection on every round; say at once when a tool is down.

### Asking every time before a status nudge
- Happened: The agent asked twice whether to nudge support about a review already past the supplier's own stated time, until the user ordered it; the nudges that followed were short, polite and one topic each, with order numbers collected first.
- Cost: a day lost waiting for permission for a low-risk message.
- Check: At the order, ask once for a standing permission for short status nudges and record it. Nudge only when the supplier is past its stated time and the status is stuck on its side, one topic per message.

### Supplier dates passed on as promises
- Happened: Stated windows of 2 to 3 hours or "today" were estimates, and assembled boards took 3 to 4 days from payment to production.
- Cost: dates the user planned around and then lost.
- Check: Plan 3 to 4 days from payment to production for assembled boards, tell the user the supplier's working hours, and never pass a supplier's estimate on as a promise.

### Order lessons not written down
- Happened: After a long back-and-forth with several suppliers, the user asked for every detail to be noted so the next order would not repeat it.
- Cost: the same questions again on the next order.
- Check: After every order write the supplier's questions and the form fields that caused them into `ORDER_LOG.md`, read it before the next order, and propose general lessons for this file.

## Phase 15: arrival and first power-up

### "No smoke" expected from a schematic review
- Happened: After approving the schematic the user asked whether first power-up would be free of smoke, while risks a schematic review cannot catch (footprints, pin 1, placement rotation, a hand-crimped cable on the wrong pin) were still open.
- Cost: boards lost when those risks are forgotten.
- Check: Never promise a safe first power-up from schematic review; plan `FIRST_POWER_UP.md` and rely on the footprint, rotation and harness checks of phases 10 to 12.

### A bring-up test that could not trip
- Happened: The crowbar test as written could never trip because the standby rail it needed was not powered in that step, and many tests from the review standard were missing until the electrical reviewer added them.
- Cost: a protection believed proven that was never exercised.
- Check: Dry-run each step against the schematic: is every rail the test needs powered, and can the test trigger what it tests? Derive the rows from the bench-only list and any standard's test matrix; the bring-up-plan review checks both.

### Bench limits set for the wrong purpose
- Happened: An over-voltage step with a generous current limit could have cooked the input TVS on overshoot, a first-power-up limit was left in place for normal running that needs more, and the supply logged only a couple of samples per second so spikes were invisible.
- Cost: a damaged clamp or false current-limit trips.
- Check: For each step state the current limit and OVP that protect the weakest part in that step, keep first-power-up limits apart from running limits, log CV and CC mode changes, and write the instrument's sampling limit beside its readings.

### Bring-up order missing steps
- Happened: An outside review found no low-voltage-only step, protections not proven before loads were connected, and logic levels not measured at the harness before meeting a GPIO; test gear also needed its range and calibration date checked.
- Cost: loads exposed to unproven protection.
- Check: Order the plan: unpowered checks and resistances, lowest voltage with a current limit, protections with dummy loads, levels at the harness, then loads one at a time. Check each instrument's range and calibration before the session.

### A known post-order change not in step 0
- Happened: A part value that had to change after the order could not be changed at the assembler; the swap by hand became step 0 with a numeric pass condition and a fallback.
- Cost: a dead function on a board if the swap is forgotten.
- Check: Put every known post-order change (value swap, DNP part, missing part) as step 0 of `FIRST_POWER_UP.md` with a numeric pass condition and a fallback.

### Pins and harnesses trusted before first connection
- Happened: A header on a bought board was not shown in its maker's schematic and had to be proven with a meter before soldering, and a crimped branch with two pins swapped would short a 3.3 V rail; a hand-wiring sheet also swapped two similar parts whose wire of the same colour is the supply on one and a signal on the other.
- Cost: a dead board or part if trusted.
- Check: Prove every undocumented pin with a meter against a known rail, with a stop rule, before soldering and again after. Check every harness pin by pin before its first plug-in, and draw wiring sheets from the assembler's view with pin 1 marked, colours quoted from each part's own datasheet and "CHECK" where unverified.

### The setup blamed before it was checked
- Happened: Weak readings were blamed on a board until it turned out a cable was not connected, and resets were blamed on firmware but disappeared with thicker supply wires; a level change was blamed on a nearby device after a single plug event.
- Cost: hours chasing design faults that were setup faults.
- Check: List the physical connections (antenna, termination, cables, final-style power wiring) for every step and verify them first, measure the supply at the load, and repeat a suspected event while changing one variable at a time.

### Temperatures not logged
- Happened: On a small board a held short makes the limiter cycle and heat its neighbours toward thermal shutdown, which only a soak test with thermocouples can show; the bench sessions that went well logged hot-part temperatures every 30 s with alert and stop limits.
- Cost: a heat failure found late, or not at all.
- Check: Log the hot parts' temperatures with alert and stop limits during every power test, and soak retry-mode faults with thermocouples on the neighbours (pass at or below their ratings).

### Procedure text never executed
- Happened: An assembly manual said a no-short resistance reading "falls" where charging capacitors make it rise, put a ground check on a connector shell that may not be grounded, and described a process that had never run on a real unit.
- Cost: wrong conclusions at the bench.
- Check: Verify every check statement (reading direction, reference point) against the design, keep only executed steps in the main procedure, and mark unproven ones as such.

### Outside review points unsorted
- Happened: An outside review's points, made from the schematic PDF alone, arrived after payment; a check with the real files sorted most as safe, safe with a bring-up step or not applicable (the review had assumed the wrong layer count), and none as needing a fix at the assembler.
- Cost: hasty changes to ordered files when points are not sorted.
- Check: Triage every outside point with the real board files, simulations and datasheets as safe as ordered, safe with a bring-up step, fix at the assembler, or next revision. Measure before changing anything already ordered, and collect the rest in `NEXT_REV.md`.

## Working with the user

### An opinion taken as a go
- Happened: While discussing cooling, the agent started redesigning a bracket, and the user stopped it because only an opinion had been asked.
- Cost: wasted work and lost trust.
- Check: For a design question give the analysis and a recommendation, then wait for an explicit go before changing any file.

### Questions that were not needed
- Happened: The user was asked to re-confirm a finish already in the BOM for parts not yet bought, to confirm a placeholder colour, and twice whether to nudge support, and was offered "now or later" instead of a recommendation.
- Cost: needless interruptions of the user.
- Check: Ask only for decisions with cost, safety or a permanent effect; decide the rest, record the assumption and let the user veto. Bundle needed decisions into one numbered list with a suggested answer and reason each, so the user can reply "all as suggested", and record standing permissions once with the hard limits beside them.

### "Ready" before the file was there
- Happened: Board files existed only on a designer's branch and reports only in a working copy, a STEP file was a day older than the rest, and a PDF called ready could not overwrite the old one because a viewer held a lock.
- Cost: the user opening old files and asking where things were.
- Check: Say "ready" only when the file is in the folder the user opens and newer than its sources, give its full path, and list outputs with their times; if a file is locked, publish under a new name and say so.

### Long reports that hid the answer
- Happened: Status questions ("where are we, what is missing") recurred; long narratives hid the answer.
- Cost: the user's time and confidence.
- Check: Lead with the conclusion and the one action needed, then a done, running and waiting list; give a percent and the remaining steps when asked; show the first finished page early; keep notifications to a one-line heads-up with the content in the chat.

### The user became the tester
- Happened: The user found a connector over a screw, colliding labels, a stale STEP file and a wrong module stack before any reviewer did.
- Cost: trust, and defects that would have shipped.
- Check: Run the reviews and checks and look at every picture before showing work; never hand over anything the user would be the first to inspect.

### A summary that claimed more than was done
- Happened: A summary said real supplier 3D models were used while stand-ins remained, and a schematic was called ready when only one of its sheets had been read closely.
- Cost: decisions taken on a false picture.
- Check: Say exactly what was and was not done, list stand-ins and unchecked items, and report UNKNOWN as UNKNOWN.

### Measurements asked piece by piece
- Happened: Fastener sizes, component heights and mounting offsets were assumed and then corrected one at a time by the user's caliper readings.
- Cost: several redesign loops.
- Check: List every dimension needed with its datum edges, ask once, design for tolerance where the value stays uncertain, and continue other work while the user measures.

## Working with agents and tools

### Model and effort left on defaults
- Happened: A schematic agent was launched on default effort despite a standing rule; the user noticed, and it was stopped after two minutes and relaunched with model and effort set explicitly.
- Cost: lost time and a rule the user had to repeat.
- Check: Set model and effort explicitly in every design, schematic, layout and review brief, state them back when launching, verify them in the agent's log, and write "no deadline" for design and research work.

### An agent that produced pictures without looking
- Happened: Panel drawings from a spawned agent came back sloppy because it never rendered and inspected its own views before reporting.
- Cost: a full restart of the drawing work.
- Check: Write in every brief that the agent renders, opens and inspects its images and iterates before reporting, and names the crops it looked at.

### Too many expensive agents at once
- Happened: Several expensive reviewers were started at once beyond the parallel limit and had to be paused; their progress files let them resume without loss.
- Cost: paused work and wasted tokens.
- Check: Run at most the parallel limit in the state file (default 2 expensive agents), announce the order, and make every agent write a progress file so it can be paused and resumed.

### Waits and processes left running
- Happened: A runaway shell used a full core for hours, loops waited forever on crashed logs, old watchers and a long sleep remained, and a forgotten command waited for keyboard input.
- Cost: a loaded PC and slower jobs.
- Check: Give every wait a timeout that ends with its job, never run commands that can wait on input, and after each agent finishes sweep both the operating-system processes and the harness's background-task list.

### Downloads through the browser
- Happened: An agent opened a datasheet PDF in the browser and triggered a save dialog nobody could click, maker sites blocked automated downloads of datasheets and 3D models, and a burst of fast parts searches got the address blocked by a distributor.
- Cost: stuck dialogs, missing models and a temporary block.
- Check: Fetch files by direct URL with `scripts/fetch_parts.py` or curl into a new folder and treat them as untrusted; pace supplier pages several seconds apart and stop at bot checks; where a site blocks you, take the next source in the order of `references/working-rules.md` section 7, and give the user the link only when none gives the file.

### Two processes on one KiCad file
- Happened: Tool processes loaded a board while its project file was being rewritten, so a dialog appeared on the user's screen and stale lock files stayed behind.
- Cost: interrupted work and a risk of a corrupted board file.
- Check: Do every board read and write through `scripts/kicad_io.py` (lock per board, stale-lock cleanup, completeness check, atomic write), and copy someone else's project before opening it.

### Heavy jobs on one core
- Happened: Clash checks ran for hours on one core, and a later run with one worker per core exhausted memory; capping workers by free memory nearly halved a long job with identical results.
- Cost: hours of waiting, then a crashed run.
- Check: Split CPU-heavy checks across cores with the worker count capped by free memory, keep results identical to a serial run, and print progress.

## Working with suppliers

### A question list to the manufacturer
- Happened: The plan was to send a machining shop a list of questions about its rules, and the user stopped it because such lists rarely get answers.
- Cost: days of silence if sent.
- Check: Design to the conservative side of every ambiguous rule, put two or three plain lines in the order remark, and let the supplier's review raise real problems. Only a single fact that decides buildability, with no conservative way round it, may be asked, once, before the order (`references/working-rules.md` section 9).

### Long mails with product names and mixed items
- Happened: A reply about one part also carried a note about another and mixed up two part numbers, which caused another question round; a clarification named internal boards, where a neutral "End A / End B" with a picture works better.
- Cost: an extra round trip, and more product detail shared than needed.
- Check: Write one item per mail in a few short lines, with the supplier's own part references, jargon defined, no product or board names, and a labelled picture; copy attachments to a folder the browser can upload from.

### Replies not approved or not fast
- Happened: Mails worked when the agent drafted, the user approved the exact text, and the agent sent it and checked the Sent folder; a time-critical reply handed to a hidden sub-agent stalled while the user saw nothing happen.
- Cost: about a day per slow reply.
- Check: Draft, get approval of the exact text, send, confirm it is in Sent, and list any deviation. Do time-critical replies in the main session the same day, and combine answers to save round trips.

### Remarks that contradict the form
- Happened: A "this colour if possible" remark stopped a part for two days because it contradicted the finish field, and a cable quote came back with generic lines because the exact specs lived only in the PDF drawing.
- Cost: two days on hold and a corrective mail.
- Check: Type exact specs and part numbers into the form fields, keep every remark consistent with every field, take colours only from the supplier's chart, and check the quote lines against the drawing before paying.

### Cable lengths without bends or tolerance
- Happened: Cable lengths had to follow the real 3D route with bend radii, and a second agent measuring blind agreed within 1.5 mm; the harness service then required one length per harness with a tolerance, and a later connector move had to be checked against cables already ordered.
- Cost: unusable cables if guessed.
- Check: Measure along the 3D route with real bend radii, add a second blind measurement, give one length per harness with plus or minus 3 mm unless there is a reason, and check any later connector move against the ordered lengths.

### Cable ends ambiguous
- Happened: An angled plug can be made with the cable leaving left or right and the supplier's photo could not show which, and a keyed header chosen for one end forced a thinner wire gauge to fit its crimps.
- Cost: a clarification round and a gauge change.
- Check: Define each connector's orientation against a datum (latch side, exit direction, nose view) and verify it against both mating boards; check wire gauge against the crimp range; prefer pre-crimped keyed assemblies to soldered wires; check the supplier's production drawing before confirming it.

### Drawings not fully dimensioned
- Happened: Drawings for a sheet-metal case lacked hole positions from datum edges, vent pattern data, bend radii and a thread table, and the user predicted the supplier's engineers would ask for each.
- Cost: an expected round of questions.
- Check: Dimension every hole and cut-out from datum edges with pattern tables, the flat pattern and a thread or press-nut table, and check automatically that every feature has a dimension. Run an instant quote early to learn the file and field limits, and have a reviewer play the manufacturer's engineer.

### Bare-metal contact assumed
- Happened: A ground path relied on bare-metal areas under the powder coat, but the shop could not mask partially, so the contacts had to be scraped at assembly with a continuity check.
- Cost: extra assembly time on every unit.
- Check: When grounding or shielding depends on a bare-metal area, mark it on the drawings with a table and its purpose and ask early whether the supplier can mask; otherwise plan scraping and a 1 ohm continuity check.

### Supplier sites used at machine speed
- Happened: A parts-search agent loaded many distributor catalogue pages in quick succession and the address was blocked for a while; the footprint service answered "forbidden" when asked too fast during the rotation work.
- Cost: a temporary block that also stopped the user's own browsing and orders, and a stalled rotation derivation.
- Check: Use supplier sites at a human pace (`references/working-rules.md` section 8): one session and one agent per site, look-ups through `scripts/jlc_parts.py` and `scripts/fetch_parts.py` with saved answers, seconds between page loads, and at any refusal or captcha stop, tell the user and wait before one slow retry.

### A site form error retried
- Happened: A quote revision failed with a "static resource unavailable" error and sent nothing, and the user chose to cancel the quote and submit a fresh one instead of editing it.
- Cost: none, because nothing was retried blindly.
- Check: When a supplier form errors, stop, check what was actually sent, and prefer cancel-and-resubmit to editing an order or quote.

### A cheaper shop chosen on price alone
- Happened: A comparison at another distributor found a cheaper switch but an out-of-stock header, a pin-compatible LED about five times dimmer, extra freight and VAT; another shop stocked only a few of the fastener types.
- Cost: wasted searches, and a wrong LED had the parts moved.
- Check: Compare an alternative shop on stock, equivalent electrical and optical specs, and landed cost with freight and VAT; rank by "fits the board already ordered" first; skip shops that cover too little of the list.

## Adding a lesson

After every project, and after every order log entry that taught something new, propose new lessons to the user. Never add one silently: show the proposed entries, say which section each belongs to, and add them only after the user's go.

Use exactly this form:

```
### <short name of the lesson>
- Happened: <1-2 sentences, technically specific, anonymous>
- Cost: <what it cost or would have cost, short>
- Check: <the rule or check that prevents it, imperative; name the skill script or review that enforces it when one exists>
```

Rules for a new lesson:
- Assign it to one phase (0 to 15) or to one of the three "working with" sections. If an existing entry covers the same root cause, extend that entry instead of adding a new one.
- Keep it general: describe the circuit or the step ("a USB-PD sink controller", "the panel connector", "a current-limit switch"); give a chip part number only where it makes the lesson clearer.
- Keep the numbers that make it technical (voltages, currents, distances, days), and drop the ones that identify the project.
- No private data: no project or product names, no people's names, no company names other than JLCPCB, LCSC, JLCCNC and chip makers, no order numbers, addresses, e-mail addresses, phone numbers or prices of specific orders.
- If a lesson is important enough to change the order of the fifteen costliest, propose the new ranking too.
