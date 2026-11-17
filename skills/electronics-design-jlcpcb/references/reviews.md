# The review system

Who reviews, on what, how findings are written, how they are closed, and what a gate may claim. The ready-to-send prompts are in `references/review-briefs/`.

## Contents
1. Why reviews are independent
2. The reviews, their prefixes and files
3. Launching a review
4. Evidence rules
5. Finding format and severity
6. The fix round and the end rule
7. Waivers and accepted deviations
8. Reviewer verdicts and release states
9. Depth
10. Merging the two visual reviews

## 1. Why reviews are independent

The designer checks what the designer thought of. On real boards, independent reviewers found a net that would have destroyed the board, many parts that would have been placed rotated, and a protection that could not protect, all after the designer's own checks were clean. So:

- The designer never reviews its own work, and never in its own context.
- A reviewer is a fresh agent. It gets the frozen files and no conclusions.
- Reviewers of the same stage do not see each other's reports.
- A reviewer reports only. It changes nothing in the design.
- A reviewer uses its own reading of the files and its own scripts where it re-computes something. A check against the generator's own source proves nothing.
- The same holds for a design the user brings. You did not design it, but your own reading is the intake, not the review: the gates still need these briefs run by fresh agents on a frozen copy (`references/existing-designs.md`).

## 2. The reviews, their prefixes and files

Which of these run on a board is decided in section 9. The lean set (LC; LB with one picture-only review V1; SR) is the default; the others run when a fact about the board switches them on.

| Prefix | Review, and when | Brief | Findings file in `reviews/` |
|---|---|---|---|
| LC | Lean circuit review (phase 7) | `lean-circuit.md` | `LC_CIRCUIT_FINDINGS.md` |
| LB | Lean board review (phase 11) | `lean-board.md` | `LB_BOARD_FINDINGS.md` |
| SR | Supplier rules (end of phase 11, on the draft order files, before the user is asked for gate 2) | `supplier-rules.md` | `SR_SUPPLIER_RULES_FINDINGS.md` |
| BU | Bring-up plan (phase 15) | `bring-up-plan.md` | `BU_BRING_UP_FINDINGS.md` |
| S1 | Schematic: datasheet (phase 7) | `schematic-datasheet.md` | `S1_DATASHEET_FINDINGS.md` |
| S2 | Schematic: system (phase 7) | `schematic-system.md` | `S2_SYSTEM_FINDINGS.md` |
| S3 | Schematic: fresh eyes (phase 7) | `schematic-fresh-eyes.md` | `S3_FRESH_EYES_FINDINGS.md` |
| SC | Simulation coverage (end of phase 6) | `simulation-coverage.md` | `SC_SIM_COVERAGE_FINDINGS.md` |
| L1 | Layout: electrical (phase 11) | `layout-electrical.md` | `L1_ELECTRICAL_FINDINGS.md` |
| L2 | Layout: manufacturing (phase 11) | `layout-manufacturing.md` | `L2_MANUFACTURING_FINDINGS.md` |
| L3 | Layout: mechanical (phase 11) | `layout-mechanical.md` | `L3_MECHANICAL_FINDINGS.md` |
| V1, V2 | Visual, from images only (phase 11): one agent in the lean set, two working apart in the full set | `visual.md` | `V1_VISUAL_FINDINGS.md`, `V2_VISUAL_FINDINGS.md` |

What each one looks at:
- **LC:** the whole circuit in one pass, what kills a board first: every chip pin and limit against its datasheet, the faults that can really happen, the set-points, then one read of the drawing as a stranger.
- **LB:** the whole board in one pass, what kills a batch first: footprints, pin mapping, rotations and polarity, the exported files against JLCPCB's rules, currents and returns, the fit in the case. It opens the images it needs as evidence; how the board looks to the eye is left to V1.
- **SR:** the live rule pages against the exported files.
- **BU:** whether each test can trip what it tests.
- **S1:** every chip pin by pin, the maker's circuit, limits at our corners, set-points recalculated, pin mapping from symbol to footprint to BOM part.
- **S2:** interactions, every fault per branch, edge cases, connectors; re-runs key simulations itself.
- **S3:** the PDF, netlist and BOM only, read as a service technician would.
- **SC:** what was not simulated; whether models and limits are honest. It runs at the end of phase 6 on its own freeze and is closed there, so the phase 7 reviewers see the completed test set. It runs only when section 9 switches it on and simulations exist: for a brought-in design without simulations it is listed as "not done", its points are UNKNOWN, and its absence alone does not force a REJECT.
- **L1:** the rules ledger, currents, return paths, noise.
- **L2:** footprints, polarity, rotations, the exported files against JLCPCB's rules.
- **L3:** holes, 3D bodies with their plugs, heights, access, enclosure fit.
- **V1, V2:** images only, no board file and no reports: silkscreen, labels, polarity marks, legends, renders, zooms, as the eye sees them.

Where several reviewers look at one stage, they have different angles on purpose: identical briefs tend to find the same things. Each reviewer is still free to report anything it sees.

Each review keeps a progress file `reviews/<prefix>_PROGRESS.md` and puts its image crops in `reviews/crops/<prefix>/`.

## 3. Launching a review

1. **Freeze.** Copy the files under review to `reviews/frozen/<stage>-r<round>-<first 12 characters of the SHA-256>/`. `<stage>` is `sch`, `sim`, `pcb` or `files`; `<round>` is the number of the last completed fix round, counted over the whole project (0 when none has happened yet). The checksum is of the exported netlist for `sch` and for `sim` (the simulation-coverage freeze), of the board file for `pcb`, and of the Gerber archive for `files` (production files brought by the user, with no board). The supplier-rules and bring-up-plan reviews use a `pcb` freeze, or `files` when there is no board. Write the full checksum in the state file. A review of files that are about to change is wasted: stop running reviews when the copper under them is being redone.
2. **Generate the images first** for any review that looks at a board: `python -I scripts/review_images.py --project <board folder>`. Look at them yourself and fix the obvious before spending a review.
3. **Add to the frozen copy:** `WAIVERS.md` (the Waivers table of the state file); the saved supplier answers `jlc_parts_answers.json` and `BOM_STOCK_CHECK.md`, because reviewers stay off the supplier's site and resolve every part number from these (a number with no saved answer is UNKNOWN); for board reviews the `review/` folder with `index.md` and `designators.csv`; for the picture-only reviewer (two of them in the full set) a reduced copy `reviews/frozen/<name>_visual/` that holds the images, `SILK_ID_BLOCK.md` and `WAIVERS.md` and nothing else. Only when the full set runs: for the fresh-eyes reviewer a reduced `fresh-eyes/` folder inside the `sch` freeze (PDF, sheet images, netlist, BOM).
4. **Fill the brief's slots.** Required in every brief: `<SKILL>` (this skill's folder), `<BOARD>`, `<FROZEN>`, `<SHA256>`, `<REVIEWS>`, `<SCRATCH>`, `<MODEL>`, `<EFFORT>`, `<SCOPE>` (the full review, or the closure of named IDs), `<ORIGIN>` (made with this skill; brought by the user; imported from another tool, verified or not yet) and `<INPUTS>` (which of design note, reference check, rules ledger, simulations, block diagram and enclosure data exist, and which do not). Where a brief needs them: `<EXTRA>` (the lean briefs: which other reviewers run beside this one, and the scope left to them), `<N>` (1 or 2 for the visual agents), `<ENCLOSURE>`, `<INSTRUMENTS>`, `<QUESTIONS>`. Tell the reviewer honestly what is missing: an input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure.
5. **Set the model and effort explicitly:** the most capable model available, the highest effort. Write both in the launch note in the state file.
6. **Run at most `review_parallel` reviewers at once** (default 2).
7. **Do not pass conclusions.** Extra points go into `<QUESTIONS>` and are introduced as "suspicions, not facts; check them like anything else".

## 4. Evidence rules

- Every item a reviewer checks ends as PASS, FAIL, UNKNOWN or WAIVED.
- PASS needs proof: the datasheet section, table or figure; a calculation with tolerances; a measured value from the file; a re-run output; an image crop with its path.
- UNKNOWN means the information or evidence was not available. It is never turned into PASS by inference. An UNKNOWN on a blocker-level item blocks the gate. Every other UNKNOWN is listed in the gate summary with the bench test that will settle it; the user's approval of the gate is the acceptance of that list. The agent never settles an UNKNOWN on its own.
- A check that could not run is FAIL with the reason.
- Every claim about an image names the crop file.
- The full checksum of the reviewed files is written in the report header.
- Every review ends with a coverage statement: what was checked and found correct, what was not checked and why, and which points no simulation or review can settle (they go to the bench list).
- A clean ERC or DRC is recorded as a tool result, not as a review result.

Visual inspection is part of every review, not only the visual one. The brief lists the images to open. The reviewer zooms on every mounting hole, every connector with its mating plug and cable exit, every label group, the information block, and reports what it saw.

## 5. Finding format and severity

```
### <ID>  <one-line title>
- Severity: blocker | major | minor | note
- Where: <sheet, parts, nets> or <board coordinates, designators, layer>
- Evidence: <datasheet reference, calculation, measured value, crop path, re-run file>
- Consequence: <what happens on the real board>
- Proposed fix: <concrete; if a part changes, an in-stock part number with its assembly class>
```

**ID:** `<prefix>-<severity letter><number>`, with the letters `B` (blocker), `MJ` (major), `MN` (minor), `N` (note). Examples: `LC-MJ3`, `LB-B1`, `S1-MN4`. IDs are stable for the life of the project; documents and fix records refer to them. No other ID form is used.

| Severity | Meaning | Gate effect |
|---|---|---|
| Blocker | The board can fail, be unsafe, be unmanufacturable, or be assembled wrong | Gate cannot pass until it is closed, or the user accepts it in writing |
| Major | Function, margin or serviceability at risk | Fixed in the fix round; if it is still open after the re-check it goes to the user at the gate as a named risk with its bench test |
| Minor | Quality, neatness, low-risk improvement | Fix when cheap; otherwise record the reason |
| Note | Observation, no action required | Recorded |

A report opens with: reviewer model and effort, the checksum, counts per severity, method, verdict. The template is `templates/REVIEW_FINDINGS.md`; the lean circuit review writes its report in the form its brief sets.

## 6. The fix round and the end rule

Fix rounds are numbered over the whole project: 1, 2, 3 and so on.

1. Collect all findings of the stage into one response file `reviews/RESPONSE_<round>.md` (`templates/REVIEW_RESPONSE.md`): per ID, what will be done, or why not.
2. Change the design source. Do not patch outputs.
3. Regenerate and re-run: ERC, netlist intent check, `ratings_check.py`, `pin_function_check.py` (a programmable chip), BOM and stock; for a board also DRC with parity and the check suite (`scripts/check_all.py`).
4. Re-run the affected simulations. Add a case for a scenario a reviewer said was missing only when it belongs to the simulation extent of this board (`references/simulation.md` section 2); otherwise it becomes a bench test.
5. Correct the documents: search for every changed value.
6. Re-render the images and look at them.
7. Freeze again (`-r<round>-`) and send each fix back to the reviewer who raised it: the same brief with a closure `<SCOPE>`. Each finder writes `reviews/VERIFY_<round>_<prefix>.md` (`templates/REVIEW_VERIFY.md`), whose table has a column "new problem introduced?".

**The end rule.** A review that may always open one more round never ends: each pass finds something finer, and none of it is wrong. So every stage ends like this:

1. **One review, one fix round, one re-check** by the same reviewer. Where a fact of section 9 switched on "a second fix round" (the full set), a second fix round and a second re-check are allowed, and no third.
2. **The re-check looks only at what was fixed.** For each of its own IDs the reviewer answers "correct and complete?" and "new problem introduced?". It may raise a new finding only if a fix caused it; it does not hunt again through what it already reviewed.
3. **A blocker must be closed, or accepted by the user in writing.** Work on an open blocker goes on, that ID alone, fix and re-check, until it is closed or the user has accepted it with the date and their words. Nothing else stops the work.
4. **Everything still open after the re-check goes to the user at the gate** as a named risk: what it is, what is known and not known, the bench test for the first boards with its pass value, and the choice. Nothing is argued closed by the designer, and nothing is counted as accepted before the user has said so.
5. **A lean reviewer has a time budget,** stated in its brief (about 30 minutes for a lean review and for the picture-only review beside it); a reviewer of the full set has none. The first page of every report is the report: the verdict, the blockers and majors each with its evidence, and what was not covered.

One combined round costs less than several small ones. If a designer's ruling differs from a reviewer's proposal, write the ruling and its reason in the response; the reviewer accepts or objects at the re-check.

After the last round, check stock again the same day and update the cost.

## 7. Waivers and accepted deviations

- A waiver is the user's decision, never the designer's or the reviewer's. It is permission, not evidence: an item it covers stays as unproven as it was (section 8).
- Present it with a zoomed picture, the options, and a suggested answer.
- Record it in the state file and in the gate summary with the date and the user's words.
- A simulation or test that fails its limit stays a FAIL. If the user accepts it, it is listed as an accepted deviation with the reason. The limit is not moved.

## 8. Reviewer verdicts and release states

A single reviewer gives a verdict on what it reviewed, in these words:

| Reviews | Verdict words |
|---|---|
| LC, S1, S2, S3, SC, BU | `NOT READY` / `READY WITH FIXES` / `READY` |
| LB, L1, L2, L3, V1, V2 | `REJECT` / `FIX AND RE-REVIEW` / `OK FOR PROTOTYPE` |
| SR | `DO NOT ORDER` / `ORDER WITH NOTES` / `ORDER` |

The **release state** of a board is a gate-level statement, written in `GATE2_SUMMARY.md` from all reviews together, and in `PRODUCTION_RELEASE.md` after the bench. A single reviewer does not state it. **This section is the one release table of the skill;** every other file points here and adds no rule of its own.

Three things are kept apart:
- **Permission to order engineering samples:** the user's approval of gate 2. State PROTOTYPE ONLY.
- **Authorization to manufacture:** the user's signature on `PRODUCTION_RELEASE.md`. State PRODUCTION APPROVED.
- **Technical or compliance validation:** the evidence in the tables below. The user's approval, waiver or signature is permission, never validation.

| State | When | Rests on (classes below) |
|---|---|---|
| REJECT | A blocker open and not accepted by the user in writing; a blocker-level item UNKNOWN; a review or check that the depth of section 9 or the chosen way of use requires and that could have run was not run | - |
| PROTOTYPE ONLY | All blockers closed or accepted by the user in writing; every major closed, or put to the user as a named risk with its bench test and accepted with the gate; files frozen. It permits a few samples for testing, not for sale or volume; a limited use the user states in writing (who, where, how many) is written beside the state. The best state first samples can reach | 1 and 3; 5 where the depth calls for it |
| PRODUCTION APPROVED | Every applicable row of the table below passed, or written "not applicable: `<the fact>`"; no blocker or major open, except a deviation the user accepted with its reason that is not safety-critical (listed in the record); files frozen under revision control; then the user signs | those of PROTOTYPE ONLY, plus 6 for every row a measurement can settle |

**What PRODUCTION APPROVED needs, scaled to the board.** A row applies only when its fact is on the board. No certificate and no test is asked where no fact calls for it.

| Row | Applies when | Evidence | Owner |
|---|---|---|---|
| Every `REQ-nn` and every bench test `BT-nn` | always | measured against the limit written before (6); "shown by design" only where no bench can measure it (`phases/15-bring-up.md` step 10b) | the user, guided |
| Destructive or hazardous fault tests: a fuse clearing, a short at full source current, a battery fault | a protection must clear a fault that can hurt a person or start a fire | 6 on sacrificial samples; a simulation (5) supports it, never replaces it | an equipped lab or a competent engineer the user names, never a beginner's ordinary bench |
| Emissions, radio and product safety | the flags of `phases/01-requirements.md` step 13 call for them in the markets the user named | the report those markets require | the user's test house or compliance owner; this skill certifies nothing |
| Firmware frozen | a programmable part | `templates/FIRMWARE_HANDOVER.md` section 12 complete | the firmware owner |
| Released files are the tested files | always | checksums, `templates/PRODUCTION_RELEASE.md` section 1 | the agent |
| A test for every later board | more boards than the tested ones will be built | `templates/PRODUCTION_RELEASE.md` section 6 | the user or the assembler |

- **A waiver never makes evidence.** A safety-critical item (its failure can hurt a person or start a fire) that is UNKNOWN stays UNKNOWN whatever the user accepts or signs: the acceptance may let samples be ordered and tested, and the item blocks PRODUCTION APPROVED until its evidence exists.
- **A simulation supports a physical test and never silently replaces it.** A required test not done is named in the record with its owner, and the board stays PROTOTYPE ONLY or a stated limited use.
- An agent never states PRODUCTION APPROVED, and never offers the signature while a row is missing: it names the row and its owner. An untested board is not production ready because the rule checks are clean.

**Evidence classes.** A class proves only what its row says.

| # | Class | Proves | Does not prove |
|---|---|---|---|
| 1 | A script that ran and passed | what its report says it checked, on the inputs it names | anything outside that scope; a script that could not run is FAIL |
| 2 | A second run of the same algorithm | consistency | correctness |
| 3 | An independent review against the source documents | that a fresh reader found no error in what it covered | a measurement |
| 4 | The supplier accepting the files | that they can make them as they read them | that the board works or is safe |
| 5 | A simulation or a calculation | the model's result in the cases run, within its limits | the real board |
| 6 | A measurement on a real board, by the user or a test owner | what was measured, on those boards, in that set-up, against a limit written before | the yield or field life of a series, from a few samples |
| - | The user's approval, waiver or signature | permission | anything technical |

**Five cases, worked.** Each is a board after its bench tests, for which production is asked; everything not named passed. Phase 15 and `templates/PRODUCTION_RELEASE.md` reach the same state.

| Case | State | Missing evidence | Owner |
|---|---|---|---|
| A fuse must clear a short that could start a fire; its clearing was only simulated | PROTOTYPE ONLY, or a stated limited use | the clearing test at the full prospective fault current, on sacrificial samples | an equipped lab or a competent engineer the user names |
| For sale in a market that requires emissions evidence; nothing measured | PROTOTYPE ONLY | the emissions report for those markets | the user's test house |
| A resistor without a silk label, accepted as waiver W-1 and shown on the assembly drawing | PRODUCTION APPROVED once the user signs | none; the waiver is listed in the record | - |
| One board for the user's own use, not sold | PROTOTYPE ONLY, limited use "one unit, own use, not sold"; one line in the state file replaces the record | none for that use; a safety-critical UNKNOWN stays named with its owner | the user |
| A revision whose applicable rows all passed, firmware frozen, files equal to the tested ones | PRODUCTION APPROVED once the user signs | none | the user signs; the agent prepares the record |

## 9. Depth

How many reviewers a board gets is decided by the agent from written facts about the board, never from a feeling and never from its size alone. The lean set is the default for every board, new or brought. A fact raises it, and only as far as that fact calls for.

**The lean set (the default):**

| Stage | Lean set |
|---|---|
| Circuit (phase 7) | 1: `LC`, the lean circuit review (pins and limits against the datasheets, faults, one read as a stranger) |
| Board (phase 11) | 2, started side by side: `LB`, the lean board review (manufacture, electrical, fit in the case), and `V1`, one picture-only review, which sees the images and nothing else (no board file, no report of the board reviewer, no notes of the designer) |
| Before the board approval (end of phase 11, step 14b) | `SR`, the supplier-rules review, on the draft order files: the user approves the board knowing its result |
| Bring-up plan (phase 15) | `BU` is offered when the board has a protection circuit or feeds a costly load |

Simulations in the lean set: only what a calculation cannot answer, and the faults of the protection table; no coverage audit (`references/simulation.md` section 2).

A lean review is a real review: a fresh agent, a frozen copy, the most capable model at the highest effort, and it closes its gate like any review. Never below one independent review of the circuit, and one of the board with one picture-only review beside it. Each of them has its time budget, one fix round and one re-check under the end rule of section 6.

**The facts that raise the depth.** Each fact switches on only what its row names, on top of the lean set:

| A fact on the board | What it switches on |
|---|---|
| A switching converter, more than 2 A in any path, or more than 30 V anywhere | `S1` (the datasheet review) as its own reviewer, and `SC`, the audit of the power simulations |
| A radio, an antenna, a satellite-navigation receiver, or any signal above 100 MHz | `L1` (the electrical board review: impedance, return paths) as its own reviewer |
| A fast bus (USB high speed, Ethernet, a memory bus, a camera or display link) | `L1` as its own reviewer |
| Mains, lithium charging, or a fault that can hurt a person or start a fire | the full set, and a second fix round |
| A microcontroller or any other programmable chip | the pin-function check (below), and `S2` (the system review) as its own reviewer |
| Fine parts (a pitch under 0.5 mm, or pads under the body) or more than 2 layers | `L2` (the manufacturing review) as its own reviewer |
| For sale, more than 50 boards, or a batch the user calls costly | the full set, and a second fix round |

**The full set:** S1, S2, S3, SC, L1, L2, L3, V1, V2, plus SR and BU, plus the enclosure fit inside L3 when there is an enclosure. When the full set runs, LC and LB are not launched: its own reviewers carry their scope, and the picture-only review runs twice (V1 and V2, working apart).

**The pin-function check:** a table in `REFERENCE_CHECK.md` with one row for every pin of the programmable chip: the function the circuit and the firmware need on that pin; the entry of the maker's pin table that offers this function on this pin of this exact package (alternate function, peripheral instance, analog channel); the state of the pin in reset and while the chip is being programmed. The designer writes it from the datasheet of the exact part number; `S2` checks it row by row. The comparison itself is made by `scripts/pin_function_check.py` from `src/pin_use.toml` (what the design uses each pin for) and the `functions` of `src/datasheet_pins.toml` (what the maker's table offers): its report `out/pin_function_check.md` is that table, and the state of each pin in reset and while the chip is programmed is still added by hand. The script trusts both tables as typed, which is why the reviewer compares them with the datasheet. A PASS of the script is per-pin table consistency only. **The joint peripheral-allocation review** (`S2`, for every programmable chip, before gate 1): all uses of the chip together: the clock tree and its sources, timers and clock outputs shared by several pins and their settings, DMA channels and requests, interrupt lines, IO bank voltages, pin groups that move together (remaps), boot and debug pins, and the direction of every pin the report marks "not checked". When the firmware sets up the pins, its evidence is the maker's configuration tool file for the exact part, accepted without conflict, or a minimal initialisation that compiles for it; the firmware owner's acceptance, where there is an owner, is recorded with it and is no evidence alone; without either the allocation is UNKNOWN at the gate.

**How the depth is decided**

1. **One fact is enough.** A board with one fact gets that row's extras. Several facts add up. No number of "it is only a small board" outweighs a fact.
2. **Unknown counts as yes.** If the description, the parts list and the datasheets do not let you say that a fact is absent, it is present. A module or a chip you have not opened the datasheet of counts as carrying every fact it could carry (a "sensor module" may hold a radio and a converter).
3. **Decide again at every gate** (gate 0, gate 1, gate 2), from what the design has become, not from what was planned. A board that grew a radio, a converter, a fast bus or a programmable chip moves up at once, and what the new fact switches on is run, also for a stage that was already passed.
4. **Up by yourself, never down.** The depth is lowered only on the user's word, recorded with the date and their words.
5. **Show it in one line** at the first approval (gate 0), with the facts behind it: "Depth: lean. Facts: no radio, no converter, 12 V, 0.5 A, 5 boards, own use." or "Depth: lean, plus the electrical board review. Fact: a 2.4 GHz radio module." Record the depth and the facts in the state file (`review_depth`, `depth_facts`), and again at every gate where they changed.
6. **The user may overrule it** in either direction. Raising costs time; say how much. Lowering is their risk; say which reviews will then not run and what they would have looked at.

**When an extra reviewer runs beside a lean review,** fill the lean brief's `<EXTRA>` slot with the extra reviewers and the scope left to them. The lean reviewer skips those items and says so in its coverage statement. Reviewers of one stage do not see each other's reports.

**Which reviews for a brought-in design** depends on what was brought: the table is in `references/existing-designs.md` section 3, and the facts above raise it in the same way. A review that cannot run for lack of input (for example the board review when only a schematic exists) is not "required": the summary names it as not done.

## 10. Merging the two visual reviews

Only when the full set runs; in the lean set there is one picture-only reviewer and nothing to merge. The two visual reviewers work apart from the same images with the same brief. Merge by union: a finding from either one counts. Where they disagree on whether something is a defect, look at the crop yourself and, if it is a matter of taste or a waiver, show it to the user. Do not average them away.
