---
name: enclosure-cables-jlc
description: Use when the user wants to design, review, print, order or check the mechanical side of an electronic device - an enclosure, box, case, housing, front panel, bracket or stand for one or more boards; a 3D-printed concept box (FDM, at home or at JLC3DP); a folded sheet-metal or CNC-machined case at JLCCNC, with powder coat, anodizing and silkscreen; a bought standard case with cut panels; custom cables, wire harnesses, coax or network cables at LCSC Cable, their lengths measured in the 3D model, their drawings and pin tables; fit, clearance, heat and air flow, shielding and grounding inside a box; fully dimensioned fabrication drawings; a quote or order for such parts, the supplier's questions and production drawings; the fit check when the parts arrive; or an assembly manual. Use it even when the user asks for only one of these steps (only the cables, only a printed box, only a drawing check, only an order) or brings a finished model. It is the mechanical companion of electronics-design-jlcpcb.
---

# Enclosure and cables: from an idea to a printed concept, ordered metal parts and ordered cables

## What this skill is

A gated process with two parts that share one 3D model and one ordering core:

- **Part A, the enclosure:** requirements, a layout study, a parametric model in code built on the real parts' 3D models, a concept that is printed first, then the sheet-metal or CNC version, its fully dimensioned drawings and print (silkscreen) files, the order at JLCCNC, the fit check on arrival.
- **Part B, the cables:** the cable list, each route measured in the same model, drawings in the cable maker's own format, the order at LCSC Cable, the check of the maker's production drawings, the check on arrival.

Enclosures and cables rarely fail for clever reasons. They fail because a remark asked for something the supplier's form does not offer, a print file's CAD colours were read as inks, a hole position was typed by hand, a cable was a few millimetres short, a thin printed bar snapped along its layers, or nobody looked at the picture. Every gate and check below exists because skipping it cost days.

**It is used in several ways,** and any mix: a box and its cables from nothing; only cables; only a printed box; the metal version of a box that already exists; a review of someone's model or drawings with nothing changed; only the order of finished files; only an order that needs watching; only the arrival check.

**Proven range of version 1:** small and medium electronics boxes (up to about 300 mm) printed on the user's own FDM printer; folded sheet metal from JLCCNC and custom cables from LCSC Cable, **proven up to the order and the supplier's review**: the delivered parts are not yet measured. Marked in the files as **PROVISIONAL** (waiting for evidence from real parts) or **not proven by an order** (CNC parts, JLC3DP, a bought standard case): say so to the user when a project uses them. Not covered: injection moulding, die casting, sealed (IP-rated) or pressure enclosures, structural or safety-critical mechanics, mains insulation design.

## Start here, in every session

Paths that begin with `scripts/`, `templates/` or `references/` are inside this skill's folder. Call scripts by their full path, as `python -I <skill folder>/scripts/<name>.py` (on Windows give the full path of the Python that has CadQuery: a bare `python` may be the store stub). Paths such as `mech/...` are in the user's project (default `<project>/mech/`; when the board lives in `hardware/<board>/`, the board's interface files stay in `hardware/<board>/mech/` and `mech.toml` points to them).

0. **A supplier's deadline comes first.** If a supplier question, a production drawing or a payment step is waiting, read the state file (or create a minimal one) and go straight to `references/phases/13-watch.md`.
1. **Find the state file** `mech/PROJECT_STATE.md`. If it exists, read it, check the listed files against their checksums, continue at "Next action". If not, read `references/phases/00-start.md` and create it.
2. **Read `references/working-rules.md`** once per session.
3. **Run `scripts/env_check.py`** and note what is missing. Ask before installing anything.
4. **Pick the entry phase** with the table in `00-start.md`. A project can enter anywhere.

Read a phase file when its phase starts, not before. Do not work a phase from memory of this page.

## The flow

| # | Phase | Part | Read | Leaves behind | Closed by |
|---|---|---|---|---|---|
| 0 | Start or resume | both | `phases/00-start.md` | State file, tool report | Agent |
| 1 | Requirements and the process choice | both | `phases/01-requirements.md` | One-page description, capability sheets, printer profile | **User confirms the page** |
| 2 | Layout study and first cable list | both | `phases/02-layout.md` | 2-3 arrangements as pictures, comparison table, cable list v1, `outline.json` for the board | **GATE 0: user approves the layout picture** |
| 3 | Real parts and the model in code | A | `phases/03-model.md` | Model, assembly STEP, standard view set, one build command | Agent |
| 4 | Fit, heat, shielding | A | `phases/04-engineering.md` | Check rows, heat table, ground-bond map, arrival test list | Agent |
| 5 | Cables in the model | B | `phases/05-cables.md` | `cables.json`, two route measurements, final lengths | Agent: both measurements agree or each difference has a cause |
| 6 | Design for printing | A | `phases/06-print-design.md` | Print files in print pose, slicing report, test coupon | Agent |
| 7 | Reviews, the print, the fit check | A | `phases/07-print-review.md` | Review reports, print findings, corrected model | **GATE 1: user approves the print files**, prints, reports |
| 8 | Metal version and catalogue finishes | A | `phases/08-metal.md` | One STEP per part, decisions table with costs | **User picks colour, inks, wording** |
| 9 | Production documents | both | `phases/09-documents.md` | Dimensioned PDFs, print file, ink sheet, renders, cable drawings, field sheets | Agent |
| 10 | Independent checks and the fix round | both | `phases/10-checks.md` | Review reports, the frozen candidate | **GATE 2: user approves the frozen design** |
| 11 | Freeze and order plan | both | `phases/11-freeze.md` | Revision, checksums, upload folders, order plan with deadlines | Agent |
| 12 | Quotes and orders | both | `phases/12-order.md` | Order log, line map, totals | **GATE 3: the user pays** |
| 13 | Order watch, production drawings, one revision round | both | `phases/13-watch.md` | Answers, checked production drawings, real lead times | Agent; the user's OK on each message and each Confirm |
| 14 | Arrival and fit check | both | `phases/14-arrival.md` | Incoming check, fit report, next-revision list | User measures; agent reports |
| 15 | Assembly manual | both | `phases/15-manual.md` | Manual as HTML and A4 PDF | Agent; user reads the draft |
| 16 | Lessons back | both | `phases/16-lessons.md` | Project lessons, a dated proposal for this skill | **User OKs each line** |

Never start phase 3 before gate 0, the metal version (phase 8) before the printed concept has fitted (gate 1 and the print findings) unless the user waives the print in writing, any quote before gate 2, or a cable quote before the cable list is frozen: a submitted cable quote cannot be edited.

Entry shortcuts: cables only = 0, 1 (short), 5, 9 to 14. A printed box only = 0 to 7. Finished files that need the order = 9 (documents check) onward.

## Rules that hold in every phase

0. **The most capable model at the highest effort for all engineering work** (modelling, drawings, cable data, reviews), both set explicitly in every agent call and written in its report. Cheaper models only for mechanical work such as file conversion.
1. **Order only what the supplier's forms and charts offer.** The capability sheet of phase 1 is the list. Every word in a remark, a drawing or a layer name that is not a field value or a chart name gets a question from the supplier; "if possible" and "fallback" count as requests. Coating is all over: no masking, no RAL, no Pantone, unless the capability sheet shows the supplier offers it.
2. **One value per item, no questions in files.** No alternatives, no "please confirm", no internal notes on anything a supplier sees.
3. **No number is typed twice.** Board numbers come from `interface.json` with checksums; cable lengths from the model; drawings from the exported STEP; form values from the field sheet.
4. **One build, nothing stale.** After any change run `scripts/build.py`: it runs the build steps that phase 3 lists in `mech.toml` (STEP, views, renders, drawings, cable drawings, manual pictures) and fails on any file older than its inputs. A generator that is not in that list is a defect: add it. Tell the user exactly where each file is.
5. **Check what will be uploaded.** Supplier rules are measured on the exported STEP, DXF and PDF, not on design parameters.
6. **Look at the pictures.** Open every view, render, drawing page, slicer preview and cable drawing and write what you saw: each hole, connector, cut-out, label and vent group, zoomed. Scripts add to looking and never replace it.
7. **The designer never reviews its own work.** Reviews are fresh agents with the frozen files (`scripts/freeze.py`: it refuses a stale build) and the brief, no conclusions.
8. **Every check ends pass, fail, could not run or not applicable, with its proof.** A check that cannot run is never a pass.
9. **Real parts, read from their makers.** Every bought part is its maker's 3D model or is built from its datasheet drawing; every screw is a real library screw; the maker's assembly and pin-out page is read before parts are stacked. A measurement nobody has is asked from the user with a sketch, never guessed.
10. **Print first.** The concept is printed and has fitted before any metal is ordered. The printer's own measured numbers (hole shrink, clearances) come from the test coupon, not from a table.
11. **Freeze before the first quote.** All choices of ends, routes, cable types, colours, inks and wording are made, and the full interconnect check is done, before any quote.
12. **Work to the supplier's working day.** `scripts/supplier_calendar.py` gives the deadlines. Plan one supplier working day per question round.
13. **Answer only what is asked,** for that part or line only, in the same thread, in the supplier's words, with their numbers and ours. No "just to confirm" messages. Do not ask what their site already says.
14. **Check every production drawing and every total before a Confirm or a payment,** field by field. After each payment re-read the shipping plan and tick what is done.
15. **Never without the user:** installing software; sign-in; card data, payment, the final submit of an order (a quote request or a submit-for-review is the user's click too, or the agent's only after the user's recorded go on that exact cart); terms and consent boxes; sending any e-mail, chat line or revision note they have not seen (a standing OK per order counts, recorded in the state file); Confirm on a production drawing; changing their slicer settings; starting a print; buying anything; writing into this skill.
16. **An opinion asked is not a go.** Answer, recommend, wait.
17. **Do not send the supplier question lists.** Design to the conservative side and let their review speak.
18. **Economy.** The cheapest standard part and process that meets the requirement first: a bought standard case before a custom one, a plain rectangle before a shaped part, chart colours before special ones. No tooling. Do not add what was not asked for; offer it with its cost.
19. **Supplier facts age.** Everything in `references/suppliers/` and every capability sheet carries a date. Before an order an independent agent re-reads the live pages.
20. **No private data in this skill or in anything uploaded.** Scrub STEP headers, scan upload folders (`scripts/step_scrub.py`, `scripts/privacy_scan.py`). Messages to suppliers carry no product or board names: End A/B, P1/P2, part numbers.
21. **Downloads by direct link only,** into their own folder, licence noted; never a click in a browser.
22. **Use all CPU cores** for heavy checks and renders, with progress output.
23. **Write state to disk as you go.** Decisions go into the state file with the date and the user's words.
24. **Never invent a fact.** A dimension, a rule value, a part number, a price, a lead time: each comes from a source opened in this project, or it is UNKNOWN.

## Asking the user

Assume the user is not a mechanical engineer. Use everyday words; say what a choice means for the device, its cost and its look. Each question:

```
<the question, one line>
Suggested: <the answer you would choose>
Why: <one line>
```

At most about five questions in a round of phase 1 or 2, at most three decisions in any other message. Show a picture wherever one exists. Lead every report with the conclusion and the one action needed, then a short done / left list, then the exact path of every file named.

| When | What is asked |
|---|---|
| Phase 0 | Installs |
| **Phase 1** | **Requirements, process path, printer and materials, rails or slots** |
| **Phase 2** | **The arrangement; connector or solder at cable ends** |
| Phase 3 | Measurements nobody else can take |
| Phase 4 | Trade-offs with a picture (fan size, vent place) |
| **Phase 5** | **Ends, routes, cable types, colours: once** |
| Phase 6 | Material; screws into plastic or inserts; whether supports are fine on their printer |
| Phase 7 | The print and its findings |
| **Phase 8** | **Colour, inks, panel wording, quantity** |
| Phase 10 | Waivers, with zoomed pictures |
| Phase 12 | Address, shipping line; payment |
| Phase 13 | Each message; each Confirm; watch the mailbox or not |
| Phase 14 | Measurements and photos |
| Phase 16 | Each proposed line |

## Reviews

| Stage | Lean set (default) | Raised set | Briefs in `references/review-briefs/` |
|---|---|---|---|
| Cable routes (phase 5) | 1: the second measurement, written before the first numbers are seen | the same | `route-second-measure.md` |
| Before the print (phase 7) | 2 side by side: the model review; one picture-only review | plus a second model review | `model.md`, `visual.md` |
| Before the order (phase 10) | 4: supplier rules on the exported files; catalogue and drawing read as the supplier's engineer; cable drawings against data and pin-out; one picture-only review | plus a second picture-only review | `supplier-rules.md`, `catalogue-and-drawings.md`, `cable-drawings.md`, `visual.md` |
| Supplier's production drawings (phase 13) | 1: field by field before any Confirm | the same | `production-drawing.md` |
| Arrival plan (phase 14) | 1, offered | 1, run | `arrival-plan.md` |

Facts that raise the set (one is enough; unknown counts as yes): for sale or more than 50 units; mains voltage or a lithium battery inside; a radio that must be shielded or must pass through the box; more than about 15 W of heat; a sealed or splash-proof box (outside the proven range); a batch the user calls costly.

**The end rule.** One review, one fix round, one re-check by the same reviewer, which looks only at what was fixed. A blocker is closed or accepted by the user in writing; everything else still open goes to the user at the gate as a named risk with a zoomed picture. No further round. Run at most 2 reviewers at a time unless the state file says otherwise. Details, the finding format and the release states (CONCEPT PRINT, SAMPLES ONLY, PRODUCTION APPROVED: the last needs the arrival fit check) are in `references/reviews.md`; name the state at every gate.

## The link to the electronics skill

`references/interface-electronics.md` has the whole hand-off. Short form: this skill reads the board from `interface.json` (with the board's and its STEP's checksums, written by the electronics skill's `interface_export.py`) and hands back `outline.json` (outline, holes with keep-outs, edge bands), height zones, connector edges and exits, the cable list with lengths and pin maps, the ground-bond points, fan and heat-sink decisions, and fit findings that name which side must change. Without the electronics skill the same file is filled from the maker's STEP or drawing, with its source written in it.

## When a tool is missing

`references/tools.md` lists each tool, how it is found, how to ask for its install and what to do without it. Short form: without CadQuery the model, fit and drawing checks could not run (reviews of drawings and the order phases still work); without a slicer command line the rule audit runs and the user slices and sends the previews; without Blender the plain views are used and the user is told the pictures are not photo-real; without the browser extension the agent prepares the upload folder and the field sheet and the user types the form.

## Stop when you catch yourself thinking

| Thought | What is true |
|---|---|
| "I will add 'RAL 9006 if possible' to the remark." | Every non-catalogue word is a question and a day. Chart name only. |
| "The supplier will mask these contact areas." | They coat all over unless their own page offers masking. Plan the bonds another way (phase 4). |
| "The layer colours are only CAD colours." | The factory reads every colour as an ink. Layer colour = ink colour; the outline and bend lines get colours of their own (green, yellow dashed), never index 7; run the factory view. |
| "The script says it is clear." | Open the image. Then believe it. |
| "The hole is at 27.25; I will type it in." | Read it from the interface file. Typed numbers drift. |
| "A block will do for this connector." | Get the maker's model. The block hid the collision last time. |
| "I know how this module stacks." | Read the maker's assembly page first. |
| "The drawing has the main dimensions." | Every hole and cut-out from a datum, or the supplier asks. Run the drawing-equals-STEP check. |
| "My own checks pass, so the files are fine." | The independent check on the exported files found several failures the builder's checks missed. |
| "The cable needs plus or minus 1 mm." | The cable maker's floor is +-5 for every cable type (as read 2026-11): a tighter request is drawn at +-5 or costs a question round. Design the cable to work at +-5, the shortest one still covering the route. |
| "Each wire gets its own length." | One length per harness: the longest route plus its allowance. |
| "I will send the quote now and fix the list later." | A submitted cable quote cannot be edited. Freeze first. |
| "Their line 4 is our cable 4." | Record the line map at the quote; write both numbers in every message. |
| "They confirmed it by e-mail, so the drawing will be right." | Only the production drawing counts. Check it field by field. |
| "I will just confirm that we understood each other." | Each extra message re-opens the ticket. Answer only what is asked. |
| "It is Friday evening; I will submit anyway." | It waits for their Monday. Use the calendar. |
| "The total was on the review page." | Read it again at the pay step. |
| "The thin bar is strong enough." | Not when it is a stack of layers printed upright. Audit in print orientation. |
| "The hole is drawn at the screw's size." | Holes print smaller. Use the coupon's number. |
| "I changed one part; the renders are still fine." | Run the build. Stale files cost the user's trust. |
| "The user asked what I think, so I will change it." | Recommend and wait for the go. |
| "I will skip two vent holes to clear the screw." | Move the whole group by whole rows. A gap reads as a defect. |
| "The metal box can be ordered while the print is running." | The print finds what the model cannot. Metal after the fit. |
| "The checkout button is right there." | Payment and consent are the user's. Stop. |
| "The download needs one click." | Direct link, or give the user the link. |
| "I remember this phase." | Read its file. |

## Files of this skill

- `references/working-rules.md`: conduct in every phase. `references/reviews.md`, `references/review-briefs/`: the review system and ready briefs.
- `references/phases/`: one file per phase.
- `references/design-rules/`: `fdm-printing.md`, `sheet-metal.md`, `cnc.md`, `heat-and-air.md`, `shielding-and-ground.md`, `cables.md`, `panel-graphics.md`.
- `references/suppliers/`: `jlccnc-sheet-metal.md`, `jlccnc-cnc.md`, `jlc3dp.md`, `lcsc-cable.md`, `standard-cases.md`, `shipping-and-combine.md`, `order-flow.md`, `after-order.md`. Dated.
- `references/interface-electronics.md`, `references/tools.md`, `references/lessons.md` (real mistakes, each with the check that prevents it).
- `templates/`: skeletons for every project document, the seed capability sheets, the example model and cable data.
- `scripts/`: check and generation tools; `scripts/README.md` lists them by phase. Run `python -I scripts/<name>.py --help`.
- `evals/`: prompts for the skill's own release check; not read during a project.
