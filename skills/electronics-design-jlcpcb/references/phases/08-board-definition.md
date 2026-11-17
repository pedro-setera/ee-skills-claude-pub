# Phase 8: board definition

Fix everything the layout stands on (outline, holes, connectors, layers, sides, who solders what, panel, silkscreen plan, colour) and get the user's answers to one short list, before any part is placed.

## Inputs

- Gate 1 passed in `PROJECT_STATE.md`, with the checksum of the approved netlist.
- `REQUIREMENTS.md` (enclosure, environment, quantity, concept run or not), `DESIGN_NOTE.md` (area budget of phase 2, power budget, interconnect table), `LAYOUT_RULES_LEDGER.md`, the BOM with packages.
- Enclosure facts when there is one: wall thickness, stands, free heights, neighbours, a drawing or 3D model. The maker's drawing of every connector and of its mating plug.
- `references/pcb-rules/connectors-mechanical.md`, `references/pcb-rules/silkscreen.md`, `references/jlcpcb/capabilities.md`, `references/jlcpcb/assembly.md`.
- `templates/BOARD_DEFINITION.md` (questions Q1 to Q9 and the table of frozen answers), `templates/SILK_ID_BLOCK.md`.
- `references/pcb-rules/emc.md` (zones), `references/working-rules.md` section 11 (quality first, then cost).
- `references/lessons.md`, section "Phase 8: board definition".

## Steps

1. **Start from the mechanics.** Write down where the board sits, what holds it, what is beside, above and below it, and where each cable goes. With no enclosure, record "free board" and the size limit the user gave. With an enclosure that also holds other boards, a display or cables, agree where this board sits and which way each connector, light and button faces in the 3D assembly (the companion skill `enclosure-cables-jlc`, or the user's own CAD) before the outline is frozen: for every board, not only a tight one (`references/pcb-rules/connectors-mechanical.md` MECH-07). The outline decides everything that follows.
   - A board that slides into slots or rails of its case (an extruded aluminium case, for example) follows rule MECH-06 (boards held by slots or rails) in `references/pcb-rules/connectors-mechanical.md`: a free band along each guided edge, on both sides, of the slot depth plus a margin (start from 1 mm more than the slot depth); board width and thickness checked against the case drawing with their tolerances; the tallest parts on each side against the inside height at the slot level; a cross-section of the case profile with the board, to scale, drawn before the freeze; and a decision whether ground touches the case through the rail.
2. **Check the area budget against the outline.** Sum the courtyards of all parts, add room for the labels and for one wide routing channel between the functional blocks. Aim at 55 to 60 percent fill or less on a one-sided board with power parts. Plot a rough placement sketch as evidence. An outline smaller than its own parts was once frozen and cost two layouts. Draw the zone map on the same sketch, from the design note's table of noise sources (`references/pcb-rules/emc.md` section 4): power conversion, digital, analog and sensors, radio and antenna, connectors; power enters at one side and reaches the loads without crossing the analog or radio zone; an antenna sits where its maker's keep-out fits (EMC-40). Write the zones into the design note.
3. **Draw the outline.** Every slot or inner cut-out that a requirement does force (an isolation barrier, a sensor's thermal isolation, a part passing through) gets its ledger row and the manufacturer's slot limits read from the live page (`references/pcb-rules/general.md` GEN-61, GEN-63). Prefer a plain rectangle with rounded corners. No slots, notches, tongues or inner cut-outs unless a mechanical fact forces one: cut shapes cost more and make necks that block routing. Check the size against JLCPCB's price steps (within 100 x 100 mm was the lowest step as read in 2026-11; `references/jlcpcb/capabilities.md`).
4. **Place the mounting holes.** For each: position, diameter, plated or not. Give every hole a keep-out on both sides, wide enough for the screw head, the top of the stand and the tool that turns the screw, coming straight down. Inside it, and in the column above it, there is no part body, no mated plug, no cable exit, and no copper if the hole is unplated. Write the three sizes that set the diameter. If a metal enclosure may come later, offer plated holes on ground and unfitted pads for a chassis bond now: free today, a new revision later.
5. **Fix every connector, light, button and switch:** edge, position, orientation, pin 1, cable direction, and where the cable ends. Choose each place from where its cable goes and who touches it (`references/pcb-rules/connectors-mechanical.md` MECH-26): the connector on the edge that faces what it connects to, by the shortest route, with no cable crossing another cable, a plug or a screw; the wire entry of every terminal free of the part in front of it; lights, buttons, switches and the display on the side the user sees and reaches. On a free board these places are a proposal for the user, never a silent choice. Record a block for each: the body plus the mated plug. No block may reach a hole keep-out or a fastener's tool path. Reject here any plug that can go in reversed or one row off.
6. **Prove every part that passes through a wall** (connector, LED, switch) with a section view drawn to scale: the real part on the board, the real wall thickness, the real mating plug fully inserted. Draw it with the enclosure CAD or a 3D tool when one is there, otherwise as a dimensioned 2D section from the makers' drawings.
   - Take the board edge from the maker's "PCB edge" line. Model flanges that hang past the edge.
   - A plug with an overmould needs a hole or pocket that lets it seat (a USB Type-C overmould may be up to 12.35 x 6.5 mm).
   - For a threaded jack write the thread budget: thread length minus wall, washer and nut must leave what the mating plug needs. State the thickest panel that still works.
   - For an edge-mount part compare its leg gap with the board thickness tolerance.
   - These parts are mechanical interfaces. A "similar" substitute later goes through this step again.
7. **Set height zones** above and below the board: the limit per zone and what causes it. A board with no enclosure and no height limit says so in one line. Include leads that stick out below. A shield can decided in phase 2 goes onto the zone map and into the height zones now: its outline, its height, the room for its ground land and vias all round, and where nets may cross its wall (`references/pcb-rules/emc.md` section 10). A heat sink or a fan decided in phase 2 goes in here too: the sink's outline, holes and keep-outs on both sides, the fan's place, the direction of the air as arrows, the openings the enclosure needs, the heights (`references/pcb-rules/thermal.md` THM-41).
8. **Generate the interface file.** Write the outline, holes and keep-outs as agreed into `mech/outline.json` (the mechanical input), the free bands along slot or rail edges included. The keys of this file (outline, holes with their keep-out diameter, edge bands, other keep-out areas) are listed in `scripts/layout/README.md`, section "The mechanical input"; the layout helper and the board checks read the same file, so it is written once. Draw them and the fixed connectors in the KiCad board, then run `python -I scripts/interface_export.py --project <board folder>`. It writes `mech/interface.json` with the outline, holes, connector positions and heights, plus the checksums of the board file and of the exported 3D model, and the board STEP in `out/3d/`. The enclosure side reads only this file; nothing is typed by hand. Where the design inputs and the generated file differ, the generated file is the truth. For a small board in a tight enclosure, have this outline-only board checked in the 3D assembly before any layout work.
9. **Choose the layers from the chips' datasheets** (the stack goes into the board file; where it cannot, into `[stackup]` of `board.toml`). Read the layout section of each main chip in the ledger. A board with a switching converter gets 4 layers, because a ground plane next to the parts is the better-performing choice (`references/pcb-rules/power.md` PWR-05). 2 layers are accepted only when all three hold: the converter's own maker shows a 2-layer layout with its measured results (an evaluation board on 2 layers); that layout is copied (hot loop, ground, keep-outs); and no receiver, antenna or sensitive analog input shares the board. In every other case 4 layers. A board with a radio or a sensitive analog input also gets 4 layers by default; 2 layers when the module or chip maker shows a 2-layer host layout and it is copied, or when the error budget shows that the analog input is not at risk, with the reason written in the design note. A simple board with none of these may be 2 layers. Show the user the price difference in either case: 2 layers often save little on a few samples and can cost a full re-route.
   - 4 layers follow the plan of `references/pcb-rules/general.md` GEN-03: L1 parts, signals and supply copper; L2 solid ground; L3 ground as well; L4 signals and supplies, with a ground via beside every signal via that changes between L1 and L4. Supply copper on L3 only as a local pour the current worksheet or a datasheet layout needs, never as the reference of a fast or sensitive L4 net, and recorded in the ledger. The reason for the ground pair: a ground via to the plane 0.2 mm below has about a tenth of the inductance of a through via on a 1.6 mm 2-layer board (estimate), and a supply plane between two inner layers about 1 mm apart adds almost no decoupling.
   - 2 layers carrying a single RF block: each RF shunt ground gets 2 or more vias (`references/pcb-rules/rf.md` RF-14).
   - 6 layers when 4 are not enough (GEN-03): L1 signals and parts, L2 ground, L3 signals (or power), L4 power, L5 ground, L6 signals: every signal layer next to a ground plane, both outer signal layers over ground; take the real stack and thicknesses from JLCPCB's page. Where L3 lies nearer to L4 than to L2, L4 is ground as well and the supplies are pours on L3 (GEN-03).
   - Use one of JLCPCB's standard stack-ups and name it. Write the layer plan: what each layer carries, and no tracks on the planes.
10. **Choose the assembly side.** All parts on one side is the cheaper assembly type at JLCPCB (as read in 2026-11; `references/jlcpcb/assembly.md` records what is known about the dearer type; re-read the live page). If two sides or many through-hole parts are needed, estimate both price paths.
11. **Decide who solders each part.** Mark every BOM line: placed by the assembler, hand-soldered by the user, or off-board (`hand_fit` and `dnp` in `[bom]` of `board.toml`). A hand-soldered part leaves the BOM and the placement file, goes into the off-board parts list, and gets hand-solder room: access for the iron, longer pads, a keep-out around its pads, a written solder order.
12. **Decide the panel.** A small board, or one with parts near the edges that the assembly line holds, needs rails or a customer panel. Use JLCPCB's own rules, cited by page name (`references/jlcpcb/assembly.md`; as read in 2026-11: rails at least 5 mm wide, 1 mm fiducials in a 2 mm mask opening, break-away bridges of at least five 0.6 mm holes; re-read the live page).
   - No tooling holes in the panel: JLCPCB adds its own when the order form says "Tooling holes: Added by JLCPCB" (`references/jlcpcb/assembly.md` section 5; `references/pcb-rules/dfm-dft.md` DFM-20). A panel's own holes of another size can draw an engineering question and an e-mail round after payment. Write the form choice into the board definition, so that the order (phase 13) sets it.
   - Rails go only on edges with no overhanging part and no cable exit. Keep parts about 2 mm or more from any bridge.
   - Build the panel with `python -I scripts/panel.py --project <board folder>` (settings in `[panel]` of `board.toml`; `references/tools.md` section 4). A bridge on an edge that a slot or rail of the case guides leaves a nub there: put the bridges on an edge that is not guided, or decide that the nubs are removed flush and write it into the assembly note (`references/pcb-rules/dfm-dft.md` DFM-31).
12b. **Decide the test access** (`references/pcb-rules/dfm-dft.md` DFM-98): hand probes only, for a concept run or a handful of boards; or a spring-pin fixture, for the series the user plans. With a fixture: the side its points lie on, their spacing, the two locating holes, the programming lines among the points. Write it as a row of `BOARD_DEFINITION.md`, and as the keys `fixture = true` or `false`, `fixture_side` and `fixture_holes` of the table `[testpoints]` in `board.toml`; without the key the test-point check stays UNKNOWN.
13. **Fix the silkscreen plan before layout** (`references/pcb-rules/silkscreen.md`):
   - text at least 1.0 mm high; for the line, 0.15 mm was the published minimum as read in 2026-11; use 0.16 mm or more for new work and re-read the live minimum;
   - every part has its reference next to its own part; a test point carries one text, reference over net name;
   - clearances: 0.2 mm to pads, 0.5 mm to holes and through-hole pads, 0.1 mm to vias, 1.0 mm end to end between labels of different parts on one line;
   - one pin-1 or polarity mark per polarised part, visible with the part fitted, which in practice means outside the body outline; connector pin legends generated from the netlist;
   - an area reserved for the information block: open, with no vias, tracks or other labels; rotate the block if that is what fits;
   - the position of the manufacturer's order-number mark, or its removal (`references/jlcpcb/order-flow.md`).
14. **Propose the identification text** with `templates/SILK_ID_BLOCK.md`: the company name the user gives (never a person's name), device model, board name, revision, date, connector names with pin names, polarity and voltage range at power inputs, the meaning of each LED, test-point names, and any warning the board needs.
15. **Propose colour and finish.** Suggest green: green is the standard colour and the one proven on real orders; another colour can change price, lead time or assembly options: read the live page before suggesting it. The default finish is lead-free HASL (RoHS); ENIG where parts of 0.5 mm pitch or less, contact surfaces or flatness need it; leaded HASL only if the user states that the product has no RoHS need.
16. **Ask the user** (next section) with pictures: an outline preview showing holes, keep-outs, connector blocks and cable arrows, every light, button, switch and the display connector with its name, and each section view. Show every board choice with its price effect (layers, size, finish, one or two assembled sides, special processes) in round numbers at the sample quantity and at the later quantity, marked as an estimate to be confirmed on the live quote (`references/working-rules.md` section 11). Suggest the choice that gives the circuit what it needs; where two are equally good for the circuit, the cheaper. Never suggest the cheaper choice when it fails a requirement, a rule or a proper margin.
17. **Freeze.** Write the answers into the table of `BOARD_DEFINITION.md` and into the state file, with the date and the user's words. From here the outline, the layer count and the silkscreen plan change only by coming back to this phase.

## Questions for the user

The questions are Q1 to Q9 of `templates/BOARD_DEFINITION.md`, asked in two rounds of about five, each with its picture and its price effect. On a board at the lean depth with no fact raised, state Q2, Q3, Q4, Q5 and Q7 as assumptions the user can veto, and ask Q1, Q6, Q8 and Q9. Ask in everyday words: say what a choice means for the device and its cost rather than naming the technique, explain any technical word in a few words the first time, and give the suggested answer with a reason a non-engineer can weigh (`references/working-rules.md` section 1). "All as suggested" is a valid answer. Drop a question that the requirements already answer.

Round 1, mechanics and cost:

- Q9. Is there an enclosure, and can you give its drawing or 3D model?
  - Suggested: `<use the drawing you gave | treat the outline as free within <W> x <H> mm>`.
  - Why: an enclosure drawn later forces a new outline and a new layout.
- Q1. Board size and holes: a plain rectangle of `<W> x <H>` mm with `<n>` holes for `<screw>`, each with a `<D>` mm keep-out on both sides?
  - Suggested: yes.
  - Why: the parts fill `<N>` percent of it; cut-outs cost more and squeeze the routing; the keep-out covers the screw head, the stand and the screwdriver.
- Q8. Connectors, lights, buttons and switches placed as in the picture, with the cables leaving as the arrows show?
  - Suggested: as drawn.
  - Why: each connector sits on the edge that faces what it connects to, so each cable takes the shortest way without crossing a screw or another plug; the lights and buttons are on the side you see and reach; the section view shows each plug mating through its wall.
- Q3. How many copper layers?
  - Suggested: `<4: L1 parts, signals and supply copper; L2 solid ground; L3 ground as well; L4 signals and supplies | 2>`.
  - Why: `<the board has a switching converter, a radio or a sensitive analog input, and a ground plane next to the parts performs better; the extra cost is about <amount> for the samples and <amount> per board later (estimate) | nothing on this board needs a plane, and 2 layers save about <amount>>`.
- Q2. May all parts sit on one side?
  - Suggested: yes, the top side only.
  - Why: one-sided assembly is the cheaper type at JLCPCB.

Round 2, assembly and appearance:

- Q5. Which parts does JLCPCB place?
  - Suggested: every surface-mount part; you solder `<list>` by hand.
  - Why: having JLCPCB fit `<list>` adds about `<amount>`; hand-fit parts stay out of the BOM and the placement file.
- Q7. Panel and rails? (ask only when it changes the quantity or the cost)
  - Suggested: `<a panel of <n> boards with rails on two ends | rails on the long sides | none>`.
  - Why: `<parts sit <x> mm from the edges the assembly line holds>`; with a panel the order counts panels.
- Q4. Solder mask colour and surface finish?
  - Suggested: green; `<lead-free HASL | ENIG>`.
  - Why: green is the standard colour and the one proven on real orders; another colour can change price, lead time or assembly options; `<lead-free HASL is the RoHS default and no fine-pitch part needs more | the 0.5 mm pitch parts need flat pads>`.
- Q6. Is this identification text right (proposal attached)?
  - Suggested: as proposed.
  - Why: company, model, revision and date identify the board for service; pin names and polarity prevent wiring mistakes.
- Only when a metal enclosure is possible: add a chassis-ground option now?
  - Suggested: yes: plated holes on ground and unfitted bond parts.
  - Why: free now; it avoids a new board revision later.

Never ask about track widths, via sizes, passive sizes or router settings.

## Checks before leaving this phase

- [ ] The area budget is a table: courtyard sum, allowance for labels and channel, fill percent. Evidence: the table in `BOARD_DEFINITION.md`, `out/placement_sketch.png`.
- [ ] The zone map is drawn and written into the design note; every noise source and sensitive part of its table has a zone. Evidence: the zones on `out/placement_sketch.png`, the design note.
- [ ] Every board choice was shown with its price effect, and the layer count follows PWR-05. Evidence: the questions as asked, the frozen-answers table.
- [ ] The outline preview shows the outline, holes, keep-outs on both sides, connector blocks, cable arrows, every light, button, switch and the display connector, and height zones; each connector's edge is the one facing its cable's target, or the reason why not is written. Evidence: `out/review/outline_preview.png`, one line on what it shows.
- [ ] A board held by slots or rails has its free bands from the case drawing, and the cross-section of the case profile with the board was drawn before the freeze. Evidence: the section drawing `out/review/section_case.png`, the bands in `mech/outline.json`.
- [ ] Each hole keep-out diameter is derived from the head, stand and tool sizes. Evidence: the hole entries of `mech/outline.json` with the three sizes.
- [ ] Each wall-passing part has a section view with the plug fully mated; its edge, flange and thread numbers cite the maker's drawing page. Evidence: `out/review/section_<ref>.png`, the thread budget table.
- [ ] The interface file was written by the script and its board checksum equals the board file's. Evidence: both checksums printed side by side.
- [ ] The stack-up is a named JLCPCB standard stack, with the date the page was read; each chip's layer advice is quoted with its datasheet page; the layer plan follows GEN-03, or each deviation is in the ledger. Evidence: the layer section of `BOARD_DEFINITION.md`.
- [ ] Every BOM line is marked assembler, hand or off-board; each hand-soldered part has its keep-out and solder order. Evidence: the marked BOM table.
- [ ] The panel decision cites JLCPCB's rule pages by name and date. Evidence: the panel section.
- [ ] The test access is decided from the quantity and the user's answer: hand probes only, or a fixture side with its locating holes. Evidence: the row of `BOARD_DEFINITION.md`.
- [ ] The silkscreen plan gives the reserved area of the information block in coordinates. Evidence: `SILK_ID_BLOCK.md`.
- [ ] Every answer of the user is recorded with date and words, and the identification text is approved. Evidence: the frozen-answers table, the decisions table of the state file.
- [ ] With an enclosure: the outline-only board passed a fit check in the project's own enclosure CAD (this skill has no fit-check tool), or the fit check is FAIL "cannot run" and goes to the mechanical review with the section views. Evidence: the fit result, or the FAIL with the section views.

## Outputs

- `BOARD_DEFINITION.md`: the decisions with reasons, the answered question list, area budget, stack-up and layer plan, sides, who solders what, panel, colour, finish
- `SILK_ID_BLOCK.md`: the approved identification text and this board's silkscreen rules
- `mech/outline.json` (the mechanical input), and `mech/interface.json` with the board STEP in `out/3d/` (generated, never edited by hand)
- `kicad/<board>.kicad_pcb` holding only the outline, holes, keep-outs and fixed connectors
- `out/review/outline_preview.png`, `out/review/section_<ref>.png`, `out/placement_sketch.png`
- `PROJECT_STATE.md`: answers recorded, outline frozen, next action phase 9

## Lessons behind this phase

- An outline was frozen with no area budget and was smaller than the courtyards alone; the next shape had a narrow neck that every long net had to pass -> step 2 sums the area and step 3 refuses necks.
- Two layers were chosen to save a few dollars; the router left open nets and the board was redone with more layers -> step 9 gives a board with a switching converter, a radio or a sensitive analog input four layers with both inner layers ground, and shows the price.
- A connector body covered a mounting screw -> step 4 keeps a column clear above every hole, on both sides.
- A board for a slide-in case had parts inside the rail zone along its side edges and could not go in -> step 1 reserves the free bands from the case drawing before the outline is frozen.
- A panel connector and an LED sat too far inside the board; a plug could not mate through the wall -> step 6 asks for a section view with the real plug.
- Spare screw terminals were put in a second row behind the main connectors; two of their wire entries were half blocked by the parts in front, found only by the picture review -> step 5 places each connector from where its wire or cable goes and keeps every wire entry free.
- Board numbers were typed by hand into the enclosure model -> step 8 generates one file with checksums.
- Parts sat too close to the edges the assembly line holds, found only at review -> step 12 plans rails or a panel before layout.
- The manufacturer did not find a panel's own tooling holes (its own pages give different sizes) and asked to add its own -> step 12 leaves tooling holes out, and the order form says "Added by JLCPCB".
- The information block ended squeezed among connector labels, and several parts found no room for a label -> steps 2 and 13 reserve label room first.

The full cases are in `references/lessons.md`.
