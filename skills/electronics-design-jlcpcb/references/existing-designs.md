# Working with an existing design

How to review, improve or continue a circuit or board that already exists: the ways the skill is used, what each kind of input allows, what changes when the design is not yours, and how changes are proposed and applied. Read it in phase 0 whenever the user brings files.

## Contents
1. The ways this skill is used
2. Intake: what did the user bring
3. What changes when the design is not yours
4. Catch-up: what must exist before a later phase can be trusted
5. Proposing and applying changes
6. What the user gets from a review
7. Limits to state honestly
8. Lessons behind this file

## 1. The ways this skill is used

| The user asks | Enter at | It ends with |
|---|---|---|
| "Design a device" | Phase 0, then every phase | Samples powered up |
| "Review my schematic", "check this PCB", "is this ready to order?" | The reviews that fit what was brought (the table in section 3) | The review summary and the findings. Nothing is changed |
| "Review it and fix it" | The same, then a fix round | The corrected copy, the change list, the closure by the reviewers |
| "Here is my schematic: make the PCB and order it" | Phase 7 on the schematic (gate 1), then phases 8 to 15 | Samples powered up |
| "Here is my finished PCB: check it and order it" | Catch-up on the circuit, the phase 10 checks without fixing, phase 11 (gate 2), then 12 to 15 | Samples powered up |
| "Here are my production files: order them" | Phase 12 checks on the files, then 13 | Order placed and watched |
| "Make revision B of this board" | Phase 0 with the old files, the bench findings and the next-revision list; then every phase a change touches | A new frozen revision |
| "Watch my order", "answer the manufacturer", "plan the first power-up" | Phase 14 or 15 alone | That step done |

Any combination is allowed. One rule holds for all: a part of the flow that the request skips keeps its checks as UNKNOWN unless evidence exists, and the summary says so in plain words. A layout review cannot find a wrong circuit; an order check cannot find a wrong layout.

## 2. Intake: what did the user bring

Ask once for the richest form they have: the native project, a netlist export, the BOM with maker part numbers, the datasheet list, the enclosure drawing, earlier review or test records.

| Input | What can be done | What cannot be claimed |
|---|---|---|
| A KiCad project (schematic, board, libraries) | Everything in this skill | Nothing is excluded |
| A project from another tool that the installed KiCad can import (Altium Designer, Eagle, EasyEDA and others: section 2b) | Import a COPY, verify the import, then everything on the import | That the import equals the original until the verification passes. The user's tool stays the master unless they decide to move |
| A schematic as PDF, with a BOM | The schematic reviews by reading, the reference check, a hand-written intent file | ERC, netlist checks, anything about the board. Call it a schematic reading, not a verified schematic |
| A netlist export and a BOM | The netlist intent check, the four netlist screens (`scripts/netlist_check.py --screens`), pin-mapping checks, BOM and stock audit | Readability, set-points drawn on sheets |
| Gerbers, drill, BOM and placement file only | The supplier-rules review, edge check, the placement preview for rotations (they cannot be derived without the board: every polarised part is UNKNOWN until it is checked in JLCPCB's placement preview in phase 13 and at the placement confirmation in phase 14), BOM audit, privacy scan, a visual review from rendered layers | That the circuit or the layout rules are right. Say: "manufacturing check only" |
| Photos or a physical board | The first power-up plan, if the documents exist | Reverse engineering a board is not covered |

When only part of the evidence exists, name the review after what it really was. A PDF-only reading reported as "PCB passed" is a false result.

### 2b. Designs from other tools

KiCad reads the native files of several other tools. What it reads depends on the installed version: `python -I scripts/import_design.py --list` prints the list for this machine. As found with KiCad 9 (2026-11):

| Tool | Board | Schematic |
|---|---|---|
| Altium Designer (`.PcbDoc`, `.SchDoc`, `.PrjPcb`), Altium CircuitStudio and CircuitMaker | By script | Through KiCad's import dialog |
| Autodesk Eagle and Fusion electronics (`.brd`, `.sch`) | By script | Through KiCad's import dialog |
| EasyEDA Standard and Professional | By script | Through KiCad's import dialog |
| CADSTAR archives, P-CAD, SolidWorks PCB, gEDA PCB, Fabmaster | By script | CADSTAR through the dialog; the others from exports |
| OrCAD and Allegro, PADS and Xpedition, and any tool not listed | From exports only | From exports only |

"By script": `scripts/import_design.py` copies the file, converts the copy with KiCad's own reader (the command-line board import of KiCad 10 and newer, or the reader in KiCad's Python on KiCad 9) and saves a KiCad board. "Through KiCad's import dialog": the installed KiCad has no command for it, so the user opens KiCad once and uses its import of a non-KiCad project or schematic on the COPY; give them the three clicks and the path, and continue when they say it is done. "From exports only": ask for what every tool can write: the schematic as PDF, a netlist, the BOM with maker part numbers, Gerbers and drill files, the placement file, and if available an IPC-D-356 netlist, ODB++ or IPC-2581.

Verify every import before trusting it. An importer is a translator and can lose things:

1. **Counts:** parts, pads, nets, layers, board size and drill count of the import against the same numbers from the original tool's own exports (BOM, netlist, drill file).
2. **Nets:** the netlist of the imported schematic against a netlist exported from the original tool (`scripts/netlist_compare.py`), and against the nets of the imported board (schematic-to-board parity).
3. **Copper and holes:** the imported board's layers against the user's own Gerbers and drill files where they exist; look at both as images, layer by layer.
4. **Known weak spots of imports:** copper pours need a refill and can differ; design rules do not carry over, so set the rule file anew; text sizes and fonts shift; 3D models and custom pad shapes can be lost; special parts of the source tool (rooms, variants, embedded items) do not exist in KiCad.
5. Write the result in the state file. Until it passes, every finding on the import is marked "found on the import; confirm in the original".

Who is the master: the user's own tool, unless they decide to move the design to KiCad. A review of an import reports findings by designator, net and coordinates so the user can fix them in their tool; changes go back as a change list (section 5). If the design continues with this skill (layout by this skill, production files from KiCad), the verified import becomes the master from that point; say so and record it.

## 3. What changes when the design is not yours

1. **Never modify the user's files.** Copy them into the project's `hardware/<board>/` tree, record the source path, the date and the checksums in the state file, and work on the copy. Loading a KiCad project can rewrite it, so the copy comes before the first load.
   - **Mind the KiCad version.** A newer KiCad saves files in a format the older one cannot open. Read the version in the file's first lines before opening it, work on it with the same major version the user works with, and write that version in the state file. If only a newer KiCad than the user's is installed here, review on the copy and tell the user that a changed copy handed back will need their KiCad to be updated; do not hand back files they cannot open.
2. **A review request is not a request to change.** Report, propose, wait. Changes need a go, and the go names which changes.
3. **Independence still holds.** You are not the designer here, but your own reading is the intake, not the review. The gates need the review briefs run by fresh agents on a frozen copy, exactly as for a design made with this skill.
4. **Respect the user's style.** Do not redraw a schematic or re-route a board to taste. Poor readability is a minor finding, unless it hides a defect: a schematic joined only by net names gets the duplicate-name check on its netlist, and a hit is a blocker.
5. **Choices already made are inputs.** Parts, connectors, stack and outline stand unless a finding with evidence says otherwise.
6. **No evidence means UNKNOWN.** "It was already reviewed" without a file is not evidence. Offer to run the missing gate; skipping it is the user's decision, recorded with their words.
7. **Parts may not be LCSC parts.** Map the BOM to LCSC numbers: the exact maker part number first; for passives the same value, size, tolerance and rating; an equivalent for any other part only with the user's OK. List what JLCPCB cannot place.
8. **Decide the depth at intake; do not ask it.** The lean set is the default for a brought design as for a new one: one independent reviewer for the circuit; for the board one reviewer and, beside it, one picture-only reviewer; the supplier-rules review before an order. Read the facts of `references/reviews.md` section 9 on what was brought (the parts list, the layer count, the finest pitch, the highest voltage and current, what the board is for): each fact switches on only the extra review its row names, one fact is enough, and what the files do not let you rule out counts as present. Tell the user the depth and its facts in one line with the first message; they may overrule it. A lean review closes its gate like any review.

Which reviews the lean set holds depends on what was brought (prefixes as in `references/reviews.md`):

| Brought | Lean set | Not done, and said so |
|---|---|---|
| Schematic only (project, or PDF with BOM) | LC | Everything about a board |
| Schematic and board, "before I order" | LC, LB, V1, SR | Bench behaviour |
| Board only, no schematic | LB as far as copper shows, V1, SR | The circuit: UNKNOWN |
| Production files only | SR; V1 from the layers drawn by `scripts/review_images.py --gerbers` | Circuit and layout rules: "manufacturing check only" |

The facts raise these rows exactly as for a new design: an extra reviewer (S1, S2, L1, L2) beside the lean one, or the full set (S1, S2, S3, SC, L1, L2, L3, V1, V2, SR, BU). SC runs only where a fact switches it on and simulations exist. The end rule holds here too (`references/reviews.md` section 6): on a go that names the changes, one fix round and one re-check.

Before the reviews, run the designer's checks of the stage on the copy (ERC, the intent check if an intent file was recovered, DRC with parity, the check suite) and record every failure as an intake finding. Do not fix anything, and do not hold the reviews back because a check failed: the failures are part of what the user asked to learn.

When the design has no intent file, run `python -I scripts/netlist_check.py --project <board folder> --screens` (it reads `out/netlist.net` and the waivers of `src/netlist_screens_waivers.toml`) at intake, right after the netlist export and before the review briefs are written. It looks for four usual slips: a two-pin part shorted out, a supply pin fed only through capacitors, a rail fed only through an open or unfitted link, a pin alone on its net without a no-connect mark. Its results are leads, not findings: hand `out/netlist_screens.md` to the circuit reviewers as an intake file, and each lead and each "not checked" line becomes a question they confirm or dismiss in their findings. A lead the user confirms as intended is waived, with the user's reason, in `src/netlist_screens_waivers.toml`. "No leads" is not a review; write it in the state file as "screens: no leads, `<n>` not checked".

## 4. Catch-up: what must exist before a later phase can be trusted

Later phases lean on documents that earlier phases would have written. For an existing design they are recovered by reading, not designed. Keep them short.

This is the only catch-up table of the skill; phase 0 points here. "Read" names the phase file whose method applies; do its steps as far as they recover facts, and skip the steps that design.

| Before | Recover first, and where the method is | Why |
|---|---|---|
| Schematic reviews (phase 7) | The one-page description of what the board must do, written from the user's words and files and confirmed by them (what the files cannot answer, such as the quantity, the cost target, the case, and who assembles and tests, is asked as in phase 1): this confirmation is gate 0 for a brought-in design, and its statements are numbered `REQ-nn` like any other (read `phases/01-requirements.md`, `templates/REQUIREMENTS.md`). The block diagram, power tree, protection table and back-feed list as they ARE in the design (read `phases/02-architecture.md`). The BOM with maker part numbers and its LCSC mapping and dated stock (read `phases/03-parts.md`). Datasheets and the reference check of the main chips (read `phases/04-datasheets.md`). The intent file, written from the description and the datasheet pin tables, never copied from the netlist (read `phases/05-schematic.md`). For a microcontroller or other programmable chip, `src/pin_use.toml`, the `functions` in `src/datasheet_pins.toml` and the pin-function table of the reference check (read `phases/05-schematic.md` step 7b). Until the intent file exists, the netlist screens (`netlist_check.py --screens`) are the only mechanical look at the connections | Reviewers judge against intent. Without it they can only say the drawing agrees with itself |
| Simulations (phase 6) | Offered, not required: "run a simulation campaign on this circuit?" If yes, read `phases/06-simulation.md`. If no, every point a simulation would settle is UNKNOWN | Some defects only show in simulation or on the bench |
| Layout by this skill (phases 8 and 9) | Gate 1 evidence, or the user's recorded decision to skip it; the layout rules ledger (read `phases/04-datasheets.md`); the design-note tables that phases 8 to 10 read, as far as the schematic shows them: area budget, noise sources, heat table, power budget, interconnect table (read `phases/02-architecture.md`); `src/datasheet_pins.toml` for every chip, transistor and polarised part; the test-point list of `phases/05-schematic.md` step 4c: pads that already serve are named in `[testpoints]` of `board.toml`, missing points go on the change list. A schematic that exists only as a PDF or a picture has no netlist: it is redrawn, with the user's go, before any layout | The ledger is what the layout must follow |
| Layout reviews (phase 11) | All of the first row in short; schematic-to-board parity; the ledger; the footprint audit and real 3D models (read `phases/09-layout.md` step on footprints); outline, holes, stack and height limits read from the board and confirmed by the user (read `phases/08-board-definition.md`); the checks of `phases/10-designer-checks.md` run without fixing; gate 1 evidence or the skip decision | A layout can be perfect for the wrong circuit |
| Production files and order (phases 12, 13) | Gate 2 evidence or the skip decision; LCSC mapping and dated stock; rotations derived where a board exists, otherwise UNKNOWN and checked in the placement preview | The order is the last point where an error is cheap |
| Order watch (phase 14) | The order references and a baseline in the order log; for an order placed elsewhere, the exact files that were uploaded | Only changes are reported, and a placement can only be checked against the files |
| First power-up (phase 15) | The bench list from whatever reviews exist; the plan and, where it ran, its review | Tests must be able to trip what they test |

Write into the state file which documents were recovered, which are missing, and which gates the user chose to skip. Every later summary carries an "Evidence status" line: gates evidenced or skipped, and what was not checked.

## 5. Proposing and applying changes

1. Turn the findings into a change list (`templates/ECO_LIST.md`): per change its ID, the finding IDs it answers, what changes (parts, nets, footprints, copper, text), the effect on BOM, cost and stock, who applies it, and how it will be verified.
2. Show the list with a recommendation per item. Wait for the go.
3. Apply on the copy, never on the user's master:
   - **Small, mechanical changes** (a value, a part number, a footprint assignment, an unfitted flag, a silkscreen text) can be made by script through KiCad's own interfaces.
   - **Structural changes** to a hand-drawn schematic or a hand-routed board (new parts, new nets, moved parts, new copper) are done either by the user in their own tool from the change list, or by you on the copy. Say which you suggest and why: a person who owns the drawing usually keeps it cleaner.
4. Prove every applied change: the netlist difference (`scripts/netlist_compare.py`) must show exactly the listed changes and nothing else; before and after images for anything on the board.
5. Then run a normal fix round: ERC, intent check, DRC with parity, the check suite, affected simulations, closure by the reviewer who raised each finding (`references/reviews.md` section 6).
6. Hand back the changed copy, the change list with its status, the differences, and how to bring them into the user's master. Whether to replace their files is their decision.

If the work goes on with this skill after the review (for example the PCB from their schematic), the copy becomes the project's master from that gate on. Say so and record it.

## 6. What the user gets from a review

- `AUDIT_SUMMARY.md` (`templates/AUDIT_SUMMARY.md`): one page. The verdict in the reviewers' words; what was reviewed (inputs, checksum) and what was not; the top findings with pictures; counts per severity; the change list in short; what only the bench can settle.
- The findings files with their crops, and the change list.
- On request, for a design with a programmed part: the firmware hand-over (`templates/FIRMWARE_HANDOVER.md`), written from the reviewed netlist and the datasheets.
- No statement beyond the verdict words. A reviewed board is at best PROTOTYPE ONLY; a schematic reading from a PDF is not a gate.

## 7. Limits to state honestly

- A design in a tool with no import path into KiCad is reviewed from its exports only.
- An imported design is a translation. Findings on it are confirmed in the original before they are acted on, and production files for an order come from the original tool unless the user moved the design to KiCad.
- A board outside the proven range (see SKILL.md) is reviewed as experimental; say which parts of it the reviews could not judge.
- Firmware is not reviewed; its hardware side is: pins, boot and programming access, levels.
- Reverse engineering a physical board is not covered.

## 8. Lessons behind this file

- A reviewer who had only a schematic PDF assumed the wrong layer count and raised points that did not apply -> tell every reviewer exactly which inputs exist, and make assumptions visible.
- A deep review was run after the order instead of before it -> offer the missing gate at intake, before any money is spent.
- A project entered at the layout with no record of a schematic review; the layout checks were clean and the circuit error stayed -> missing gates are UNKNOWN and are said out loud.
- A redrawn schematic was accepted only because an automatic comparison showed the same parts, pins and nets as the ordered board -> every applied change is proven by a difference list, not by a statement.
- A tool loaded a board while another process rewrote its project -> existing projects are copied before they are opened.
