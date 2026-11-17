---
name: electronics-design-jlcpcb
description: Use when the user wants to design, review, improve, order or bring up electronics hardware - a new device or circuit board from an idea; a review, audit or check of an existing schematic or PCB (their own or someone else's; a KiCad project, an Altium, Eagle or EasyEDA project, or exports such as PDF, netlist and Gerbers from any other tool) before layout or before ordering; fixing or improving an existing design or making its next revision; a schematic, a KiCad PCB layout, part selection at LCSC or JLCPCB, circuit simulation (SPICE), Gerber / BOM / placement (CPL) files; a PCB or assembled-board (PCBA) order at JLCPCB, watching such an order, answering the manufacturer's engineering questions or placement confirmation; or the first power-up of new boards. Use it even when the user asks for only one of these steps, brings a finished schematic or board, or wants any mix of review and design.
---

# Electronics design: from an idea to assembled samples from JLCPCB

## What this skill is

A gated process for taking any electronic device from its first idea to assembled sample boards ordered at JLCPCB, watched until they arrive, and powered up safely.

Boards rarely fail for clever reasons. They fail because two signals shared a net name, a transistor was placed rotated, a value that had to change sat on a shared BOM line, a connector's 3D body covered a screw, or nobody looked at the picture. Every gate, check and review below exists because skipping it cost days or would have scrapped boards on real projects. The cases are in `references/lessons.md`.

**It is used in several ways,** and any mix of them: designing a device from nothing; reviewing an existing schematic or board and reporting, with nothing changed; reviewing and then fixing; taking the user's finished schematic through layout and order; checking and ordering a finished board; ordering existing production files; making the next revision; or only watching an order or planning a first power-up. Whenever the user brings files, read `references/existing-designs.md` in phase 0: it says what each kind of input allows, what must be recovered before a later phase can be trusted, and how changes are proposed and applied. Three rules for brought-in designs: never modify the user's files (work on a copy); a review request is not a request to change; a part of the flow that is skipped stays UNKNOWN and is said out loud.

**Proven range of version 1:** boards up to 6 layers with microcontrollers, analog circuits, power conversion, sensors, USB 2.0 and simple 50 ohm RF (with ready filter parts and filters of discrete parts). For memory buses, fine-pitch BGA, multi-gigabit links or mains voltage, say plainly in phase 1 that the board is beyond the proven range, and continue only if the user accepts it as experimental work that needs a human engineer's review.

## Start here, in every session

Paths in this skill that begin with `scripts/`, `templates/` or `references/` are inside this skill's own folder, not in the user's project. Call scripts by their full path. Paths such as `hardware/<board>/...` are in the user's project; if the user has no project folder yet, propose one and a short board name.

0. **A manufacturer's deadline comes first.** If the user brings a placement confirmation or an engineering question that is waiting, read the state file, or create a minimal one, and go straight to that step of `references/phases/14-watch.md`; do the rest of this list afterwards.
1. **Find the project state file** `hardware/<board>/PROJECT_STATE.md` in the user's project. If it exists, read it, check that the files it lists still match their checksums, and continue at its "Next action". If it does not, read `references/phases/00-start.md` and create it. The state file is what lets a long project survive a lost context; a session that works without it repeats old mistakes.
2. **Read `references/working-rules.md`** once per session. It holds how to talk to the user, what is never done without them, and how agents, downloads and files are handled.
3. **Run the environment check** (`python -I <this skill's folder>/scripts/env_check.py`) and note what is missing. Ask before installing anything.
4. **Pick the way of use and the entry phase.** A project can enter anywhere: an idea, a finished schematic that needs reviews, a finished board that needs the order, an order that needs watching. The table in `00-start.md` decides the entry; `references/existing-designs.md` governs everything the user brought.

Read a phase file when its phase starts, not before. Do not work a phase from memory of this page.

If a general skill for exploring ideas or for planning is also active, phases 1 and 2 of this skill are that conversation for the device itself: use them, and do not question the user twice.

## The flow

| # | Phase | Read | Leaves behind | Closed by |
|---|---|---|---|---|
| 0 | Start or resume | `phases/00-start.md` | State file, tool report | Agent |
| 1 | Requirements | `phases/01-requirements.md` | One-page device description with no blank, picture of the device, assumptions, complexity rating | Agent |
| | **GATE 0** | | The played-back description | **User confirms: "this is the device I want"** |
| 2 | Architecture and budgets | `phases/02-architecture.md` | Block diagram, power tree, budgets, protection and interconnect tables | **User OKs the block diagram** |
| 3 | Part selection | `phases/03-parts.md` | BOM with LCSC numbers, class, dated stock, cost; the priced parts list shown to the user | Agent; the user's go when the cost is above their target, or no target was given |
| 4 | Datasheets and rules | `phases/04-datasheets.md` | Reference check, layout rules ledger | Agent |
| 5 | Schematic | `phases/05-schematic.md` | Wired schematic, netlist intent check, design note | Agent |
| 6 | Simulation campaign | `phases/06-simulation.md` | Results with plots, bench-only list | Agent; the coverage audit where the depth switches it on |
| 7 | Schematic reviews | `phases/07-schematic-reviews.md` | Findings, responses, closures | The reviewer's re-check; what stays open goes to the user at the gate |
| | **GATE 1** | | Gate 1 summary + PDF; then the firmware hand-over (draft) | **User approves the schematic, the parts cost, and the battery and running time** |
| 8 | Board definition | `phases/08-board-definition.md` | Frozen outline, stack, silkscreen plan | **User answers the list** |
| 9 | Layout and 3D | `phases/09-layout.md` | Board, 3D model, renders | Agent |
| 10 | Designer's checks | `phases/10-designer-checks.md` | One-page check result | Every check passes, or is a FAIL or UNKNOWN that phase 10 permits, listed for gate 2 |
| 11 | Board reviews, then the draft order files and the supplier-rules review | `phases/11-layout-reviews.md` | Findings, closures, waivers | The reviewer's re-check; what stays open goes to the user at the gate |
| | **GATE 2** | | Gate 2 summary + pictures; then the firmware hand-over (final) | **User approves the PCB** |
| 12 | Production files | `phases/12-production-files.md` | Frozen upload folder, ordering checklist, cost | The files equal the ones the supplier-rules review saw before gate 2 |
| 13 | Order at JLCPCB | `phases/13-order.md` | Cart ready, options read back | Agent stops at the order summary or the payment page |
| | **GATE 3** | | | **User pays** |
| 14 | Order and e-mail watch | `phases/14-watch.md` | Order log, drafts | Boards shipped |
| 15 | Arrival and first power-up | `phases/15-bring-up.md` | Power-up plan, findings, the requirements measured, next-revision list, production release record | User's bench results; the user signs the release |

Never start phase 2 before gate 0, phase 8 before gate 1, phase 12 before gate 2 (except its draft run in phase 11 step 14b), or any routing before the outline of phase 8 is frozen. A layout built on an unsettled outline or layer count gets thrown away.

## Rules that hold in every phase

0. **The most capable model at the highest effort, for all engineering work.** Every agent that plans, selects parts, draws a schematic, simulates, lays out a board or reviews any of it runs on the most capable Claude model available, at its highest reasoning effort, and both are set explicitly in the agent call (when this was written: Claude Fable 5.2 at extra-high effort; when a more capable model exists, use that one). This holds for the session itself: if this session runs on a lesser model or a lower effort, say so to the user before any design work and suggest switching. Only a chore with no engineering judgement in it, such as the scheduled order-status check, may run on a cheaper model. A cheaper or faster model on design work is how boards get scrapped.
1. **A gate is a checklist with evidence.** Never tell the user something is "ready" on a clean rule check alone. A clean ERC passed a schematic that would have destroyed itself at first power-on. The same holds for a board: one that routes completely, passes the rule check and looks professional shows that it is connected and can be made, nothing more. That signals arrive clean, that supplies stay steady, that nothing overheats and that the board stays quiet each need their own evidence (a calculation, a simulation, a table measured on the board file), and what has none is UNKNOWN with the bench test that settles it. The gate 2 summary shows this evidence line by line.
2. **Every rule ends PASS, FAIL, UNKNOWN or WAIVED, with its proof:** a file, a measured value, an image crop. UNKNOWN is never PASS. A check that cannot run is FAIL, not skipped.
3. **Pass limits are written before the test runs and never moved afterwards.** If a test fails, the design changes or the user accepts a named deviation. A limit that was derived wrongly is corrected under a new test ID; the failed row stays in the summary, and the user is told of the correction with the next message.
4. **The designer never reviews its own work.** Reviews are done by fresh agents that get the frozen files and no conclusions. A check must compare against an independent statement of intent; a netlist compared with its own generator proves nothing. Hunt for errors; do not collect confirmations. The points that kill boards are each verified in at least two independent ways (a script on the files, eyes on an image, a reviewer against the datasheet): the pin-out of every part, absolute maximum and recommended ratings on every pin, the order in which supplies come up and go down, every current path and its return, the impedance of controlled lines, the ground under fast signals, and every constraint a datasheet or design guide sets. ERC and DRC stay necessary and prove little.
5. **Look at the pictures.** Open every render, plot and crop and write what you saw. Scripts add to looking and never replace it: a script once reported a part clear while the render showed a connector over a screw.
6. **Check what will be uploaded.** Manufacturing checks run on the exported Gerbers, drill, BOM and placement files, not on design parameters.
7. **Keep the user's load small.** Ask only for decisions with cost, safety or a permanent effect. Decide the rest, write down the assumption, and let the user veto.
8. **An opinion asked is not a go.** When the user asks what you think, answer and recommend, then wait.
9. **Never without the user:** installing software; sign-in and passwords; card data and payment; ticking terms or consent boxes; sending any e-mail or chat message (a standing permission for short status nudges, asked once per order in phase 14, counts); confirming anything on the manufacturer's site; changing a schematic, a part or a BOM line after gate 1; accepting a FAIL or UNKNOWN (every UNKNOWN, and every deviation that does not change what the user gets, is listed at the gate with the bench test that settles it, and the user's approval of the gate accepts that list; a deviation that changes what the user gets is asked on its own; an UNKNOWN on a blocker-level item blocks the gate). If a tool refuses a click such as checkout, the user does it and you guide; never work around a block.
10. **Do not send the manufacturer question lists.** Design to the conservative side, put two or three plain lines in the order remark, and let their review flag real problems. Long question lists are not answered and cost days. One narrow exception: when a single open fact decides whether the board can be built or accepted and no conservative choice is right whichever way they read it, one short, specific question goes before the order, with the user's yes (`references/working-rules.md` section 9).
11. **Supplier facts age.** Everything in `references/jlcpcb/` carries a date. Before an order, an independent agent re-reads the live pages and measures the exported files against them.
12. **No private data in this skill.** Names, addresses, order numbers and account details live only in the user's project files. Scan every file for personal names and paths before it leaves the PC.
13. **Use JLCPCB and LCSC at a human pace.** One session on a supplier's site at a time, never two agents on it at once. Load a page, read it, then act; several seconds between page loads and searches, never a burst. Look parts up through the paced script, save every answer and work from the saved copy. At the first sign of a block (a refusal, a captcha, "too many requests", an empty page) stop all access to that site, tell the user, and wait; never retry in a loop and never work around a bot check. A blocked address also locks the user out of their own account and their open orders (`references/working-rules.md` section 8).
14. **Quality first, then cost.** The aim is a high-quality circuit and board at a good price, never a cheap circuit. Safety, the function the user confirmed, stability and reliability come first and are never reduced to save money. When they are met, ask of every part and every method: can the same result, at the same quality and reliability, be had for less? If yes, take the cheaper way; if the cheaper way lowers quality, stability, reliability or function, it is not a saving. Genuine parts from established makers only: never a clone, a no-name part or a part of doubtful origin, however cheap. If quality and the user's cost target cannot both be met, say so and let the user decide; never lower quality quietly. Show the cost per board against the target at gates 1 and 2 (`references/working-rules.md` section 11).
15. **Just enough, and simple.** Do not overdo. Meet every requirement with the proper engineering margin, not less and not more; protect against the faults that can really happen, not every fault that can be imagined; add no function the user did not ask for. Prefer the simplest design that does the job. Every block and part must trace to a requirement, a datasheet demand, a credible fault or a rule; what traces to nothing is removed. Simplicity is never a reason to drop a required margin, protection, check or review: quality first, then the simplest way to it, then the cheapest (`references/working-rules.md` section 12).
16. **Noise and interference are designed out from the block diagram on.** List what makes noise and what suffers from it, give every pair its measure in the schematic, zone the board, keep power and switching copper away from antennas, microphones, sensors and crystals, give every antenna its keep-out and its matching network. The rules are `references/pcb-rules/emc.md`, read for every board. EMC designed by rules is not EMC measured: say so at gate 2.
17. **Write state to disk as you go.** Decisions go into the state file with their date and the user's words. Every agent writes a progress file. Brief agents with files, not with conversation.
18. **Never invent a fact.** A specification, a pin number or name, a footprint dimension, an electrical limit, a part number, a price or stock figure, a simulation or test result: each comes from a source opened in this project (a datasheet page, a file, a measurement, a saved supplier answer, the user's words), and the source is written beside it. What has no source is UNKNOWN: say so, and say how it will be found out. What you remember about a part is not a source; a similar part's datasheet is an inference and is labelled as one.

## Asking the user

**Assume the user is not an electronics engineer** unless they show otherwise. Use everyday words; say what a choice means for the device, its cost and its use rather than naming the technique; explain a technical word in a few words the first time; never make the user feel they should have known. An engineer will tell you to go deeper, and then you do.

**The first conversation decides the project.** In phase 1, completeness beats brevity: the one-page device description must have no blank before any design starts (every heading answered, filled by an assumption the user can see, or marked not needed), and the user's confirmation of that page, played back with a simple picture of the device, is gate 0. The checklist and the questions are in `references/phases/01-requirements.md`. A device built on a guessed requirement is the most expensive mistake there is; a later change of requirement goes back through this page.

**Two things are always settled with the user before any concept or block diagram,** when they did not say them: how the device is powered, and everything a person sees, hears or touches on it. A wrong guess here lets the user down however good the circuit is.

When the user is asked, and what:

| When | What is asked |
|---|---|
| Phase 0 | Installs; live part look-ups; on a late entry also whether a missing gate's reviews are run first, the gates and notifications; the other short permissions that `00-start.md` lists |
| **Phase 1** | **The requirements, in short rounds** |
| **Phase 2** | **The key chips; cooling, battery and ready modules where they arise** |
| Phase 3 | The go on the priced parts list, when it is above the target or no target was given |
| **Phase 8** | **The board definition list** |
| Phase 12 | One parcel or several, before the first payment |
| **Phase 13** | **The order choices** |
| Phase 14 | Order watch, mailbox watch, the confirm click, status nudges |
| Phase 15 | Which instruments exist; the bring-up plan review where it is offered |
| A design the user brings | The richest form of the files they have and, for an import, the exports of their own tool; confirmation of the recovered one-page description and of the board facts read from their files; their OK before a part is replaced by one that is not identical |

Outside these, ask only for waivers and for anything under rule 9. A deviation (a test that misses its limit, a figure that moved) goes to the user only when it changes what they get: a function, a limit they stated, the cost, or a risk of losing a board. The rest you decide, and list in the gate summary. Do not ask again what the user has already said (a quantity, a colour, a part).

Each question has this shape. A question round of phase 1 or phase 8 holds no more than about five; any other message asks for at most three decisions and puts the rest into a file it names (`references/working-rules.md` sections 1 and 2):

```
<the question, one line>
Suggested: <the answer you would choose>
Why: <one line>
```

Lead every report with the conclusion and the one action needed, then a short done / left list. Show a picture where one exists. Give the exact path of every file you name.

## Reviews

The lean set is the default for every board, new or brought. Facts about the board raise it.

| Stage | Lean set (default) | The full set | Briefs in `references/review-briefs/` |
|---|---|---|---|
| Circuit | 1: the lean circuit review | 3: datasheet, system, fresh eyes; plus the simulation coverage audit | `lean-circuit.md`; `schematic-*.md`, `simulation-coverage.md` |
| Board | 2, side by side: the lean board review, and one picture-only review that sees the images and nothing else | 3: electrical, manufacturing, mechanical (with the enclosure fit); plus 2 picture-only reviews working apart | `lean-board.md`, `visual.md`; `layout-*.md` |
| Before the board approval | supplier rules, on the draft order files: the user approves the board once, knowing every review's result | the same | `supplier-rules.md` |
| Bring-up plan | offered when the board has a protection circuit or feeds a costly load | 1 | `bring-up-plan.md` |

**Depth is decided by you, from written facts** (`references/reviews.md` section 9, read at phase 1 and at every gate). Each fact switches on only the extra review it calls for:

| A fact on the board | What it switches on |
|---|---|
| A switching converter, more than 2 A, or more than 30 V | the datasheet review as its own reviewer, and the audit of the power simulations |
| A radio, an antenna, a satellite-navigation receiver, or any signal above 100 MHz | the electrical board review as its own reviewer |
| A fast bus (USB high speed, Ethernet, memory, camera or display link) | the electrical board review as its own reviewer |
| Mains, lithium charging, or a fault that can hurt a person or start a fire | the full set, and a second fix round |
| A microcontroller or any other programmable chip | the pin-function check, and the system review as its own reviewer |
| Fine parts (pitch under 0.5 mm, pads under the body) or more than 2 layers | the manufacturing review as its own reviewer |
| For sale, more than 50 boards, or a batch the user calls costly | the full set, and a second fix round |

One fact is enough. Unknown counts as yes. Decide again at every gate from what the design has become. Move up by yourself, never down without the user's yes. Show the depth and its facts in one line at the first approval and record both in the state file; the user may overrule.

**The end rule.** One review, one fix round, one re-check by the same reviewer, which looks only at what was fixed. A blocker must be closed or accepted by the user in writing; everything else still open after the re-check goes to the user at the gate as a named risk with a bench test. A second fix round only where a fact above switched it on. A review loop without an end finds something finer on every pass and never reaches the gate.

- Every review runs as rule 0 says, with model and effort set in the agent call and written in the report. A reviewer left on a default setting is a defect: stop it and launch it again.
- Run at most 2 reviewers at a time unless the state file's `review_parallel` says otherwise.
- If sub-agents are not available, each review runs in a fresh session that gets only the frozen files and the brief, one at a time: start it with whatever the app offers for a new session, or ask the user to open one and paste the brief. Say in the gate summary that it was done this way. If no fresh session can be had, the gate waits. Never review silently in the designer's own context.

The rules, finding format, severities and release states are in `references/reviews.md`; its section 8 is the one release table.

## When a tool is missing

`references/tools.md` lists every tool, how to detect it, how to ask for its install, and what to do without it. The short form: without KiCad the skill stops after phase 4; without a SPICE engine the affected points are marked UNKNOWN, moved to the bench list and named at gate 1; without a browser extension the user clicks from a prepared list; without push or scheduling the watch runs only when asked. Say what is not running; never pretend a check ran.

## Stop when you catch yourself thinking

| Thought | What is true |
|---|---|
| "ERC and DRC are clean, so it is ready." | Clean rule checks passed the worst errors on record. Run the gate checklist. |
| "The script says it is clear." | Open the image. Then believe it. |
| "It is fully routed and looks clean, so it will work." | A tidy board proves it is connected. Clean signals, steady supplies, heat and noise each need their own number or picture; without one the item is UNKNOWN. |
| "I designed it, so I can review it quickly myself." | A self-review finds what you already thought of. Launch the independent review. |
| "It is only a small board, so the lean set will do." | Size decides nothing. Go through the facts; one fact is enough, and what you cannot rule out counts as present. |
| "One more review round will make it safer." | The end rule: one fix round, one re-check. A blocker is closed or accepted by the user; the rest goes to the user as a named risk with its bench test. |
| "I will ask the user about this failed test limit too." | Only when it changes what they get: a function, a limit they stated, cost, or a risk of losing a board. Decide the rest and list it in the gate summary. |
| "I will just adjust the limit so the test passes." | The limit was the requirement. Change the design or ask for a named deviation. |
| "This value can share the BOM line with the others." | If it may ever change, it gets its own line. A shared line cannot be split after the order. |
| "A generic rotation table is good enough." | Derive each rotation from JLCPCB's own footprint and check the preview. |
| "The outline is nearly settled; I can start routing." | Freeze phase 8 first. |
| "I will ask the supplier these eight questions." | Assume the conservative side and submit. Only one fact that decides whether the board can be built, with no conservative way round it, earns one question, with the user's yes. |
| "The checkout button is right there." | Payment and consent are the user's. Stop. |
| "The user asked what I think, so I will make the change." | Recommend and wait for the go. |
| "The download needs one click in the browser." | Fetch by direct URL, or give the user the link. |
| "I will check these forty parts quickly, in parallel." | One paced session. A burst gets the user's address blocked, and their orders with it. |
| "The site refused once; I will just try again." | Stop, tell the user, wait. A retry loop turns a short block into a long one. |
| "I remember this phase." | Read its file. |
| "The datasheet is enough for this module." | For a microcontroller, a radio or any complex part the maker's hardware design guide holds what the datasheet leaves out. Find it; if it cannot be had, ask the user for it. |
| "I will show the cost at the end." | Parts are most of the price. Show the priced parts list as soon as it exists; the user agrees to it before any PCB work. |
| "A slot here will separate the grounds." | No. One solid ground plane, partitioned by placement. A moat or split only where the chip maker's own document asks for it expressly, or as an isolation barrier. |
| "I know this chip; pin 3 is the enable." | Open the datasheet of the exact part number. Memory is not a source; a fact without a source is UNKNOWN. |
| "It is under its maximum temperature, so it is fine." | The maximum is a survival figure. Do the study with the air inside the box and a margin; if copper is not enough, propose a heat sink or a fan, with its size. |
| "One more protection cannot hurt." | It is one more part to buy, place, test and fail. Which fault that can really happen is it for? |
| "A cleverer circuit would be more elegant." | The usual circuit from the maker's datasheet first. Clever must do something the usual one cannot. |
| "Twice the margin is safer." | The proper margin is the safe one. More needs a reason, as less does. |
| "I will add this feature; the user will like it." | Offer it with its cost. Do not add what was not asked for. |
| "The dearer part must be the better choice." | Not by itself. If a cheaper part from an established maker does the same job with the same margin, take it. |
| "It is cheaper with this unknown brand." | Never a clone, a no-name or a doubtful part. A saving that lowers quality or reliability is not a saving. |
| "It is cheaper without the protection, the margin or the check." | Safety, function, stability and reliability come first. Look for the same quality by a cheaper way, or tell the user what the quality costs. |
| "The target price cannot be met, so I will cut a corner." | Do not lower quality quietly. Show the user the options and let them decide. |
| "A faster model will do for this part of the design." | Rule 0. All engineering work runs on the most capable model at the highest effort. |
| "They did not say how it is powered; USB will be fine." | Ask. Power and everything the person sees, hears or touches are settled with the user first. |
| "The user will know what an LDO is." | Assume they do not. Say what it does for their device. |
| "They asked for a review; I will fix it while I am there." | Report and propose. Change only on a go that names the changes, and only on a copy. |
| "Their board passes my layout checks, so it is fine to order." | No evidence for the circuit means UNKNOWN. Say so and offer the missing gate. |

## Files of this skill

- `references/working-rules.md`: conduct in every phase.
- `references/existing-designs.md`: reviewing, improving or continuing a design the user brings.
- `references/phases/`: one file per phase.
- `references/reviews.md`, `references/review-briefs/`: the review system and ready briefs.
- `references/pcb-rules/`: layout rules by circuit type; component rules come from each datasheet. `general.md` (layers, widths, vias, grounds), `power.md` (regulators, converters, batteries and chargers), `mcu-digital.md`, `usb.md`, `rf.md` (antennas, matching, 50 ohm lines), `analog.md`, `protection-esd.md` (input protection and its order, fuses, TVS), `connectors-mechanical.md` (connectors, holes, case and rails), `silkscreen.md`, `dfm-dft.md` (manufacture and test), `thermal.md` (heat: the thermal study, heat sinks and fans, read when a part runs warm), and `emc.md` for noise and interference on every board.
- `references/jlcpcb/`: capabilities, assembly, parts library, order flow, after the order, combined shipping. Dated.
- `references/schematic-style.md`, `references/simulation.md`, `references/tools.md`.
- `references/lessons.md`: real mistakes, each with the check that prevents it.
- `templates/`: skeletons for every project document.
- `scripts/`: check and generation tools. Run them with `python -I scripts/<name>.py --help`.
- Companion skill `enclosure-cables-jlc`: the box, the cables and their JLCCNC / LCSC Cable orders. Hand the board over with `scripts/interface_export.py` (it writes `mech/interface.json`); take back the keep-outs, connector exits and cable lengths.
