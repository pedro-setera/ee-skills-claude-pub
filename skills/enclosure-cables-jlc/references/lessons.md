# Lessons: real mistakes, what each cost, and the check that now prevents it

Every row is something that really happened on the projects this skill was written from, told without names.
"Top 16 #n" marks the sixteen that cost the most time or money, in their rank. Three of them (#3, #8, #16)
had two parts and appear on two rows each.

How to use it: when a phase tempts you to skip a check, find the row. When a project produces a new lesson, phase 16
proposes it to the user for this file, rewritten without names, order numbers or project words.

## Phase 1: requirements and the process choice

| # | What happened | What it cost | Phase and check that prevents it |
|---|---|---|---|
| L-01 | Things were asked that the supplier's forms and charts do not offer: masked zones, a colour-system coat colour "if possible", a colour-system ink with a fallback. All three were already on the project's own open-points list. (Top 16 #1) | About 2 days before payment, a hold in production, and the whole ground-bond design turned into hand scraping | 1: the capability sheet is the only list. 8: chart names only. 10: `catalogue_scan.py` and `review-briefs/catalogue-and-drawings.md` |
| L-02 | First supplier notes, written from a blog page, advised "ask for masked contact areas". The supplier does not mask | The wrong advice became the design | 1: the capability sheet is filled from the forms and charts, dated. 10: an independent agent re-reads the live pages (`review-briefs/supplier-rules.md`) |
| L-03 | On an earlier project a board with parts within 2 mm of its edge jammed in the 2 mm rails of an extruded case | A new board layout | 1: the question "does any board slide in rails or slots?". `suppliers/standard-cases.md` section 3; bands in `outline.json` |
| L-04 | Premium parts and an accessory kit were proposed that the requirements did not ask for; frames that needed a mould were proposed | Proposals thrown away; the user's trust | Rule 18 economy; 1: the price position on the requirements page |
| L-05 | The first plan said "cable quote in 24 hours, 5 to 7 working days". Real: about 4 weeks to the door | A plan built on wrong dates; boards waiting in a warehouse | `suppliers/lcsc-cable.md` section 7; 11: cables first |

## Phase 2: layout and the first cable list

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-06 | A board-mounted connector and an LED sat too far inside the board to reach the wall; a jack's thread length through wall, washer and nut was not known | A part change and a board change | 2: panel-part reach (`layout_study.py`); `design-rules/panel-graphics.md` PG-02 |
| L-07 | Two connector families on one board; a consumer cable planned inside the box; wires to be soldered where a connector fitted | Redesign of the harnesses | 2: the cable-end question; `design-rules/cables.md` CB-04 |
| L-08 | A board was given cut-outs to fit a small box, where a slightly larger box allowed a plain rectangle and a centred fan | A dearer board; then the box was enlarged anyway | 2: the comparison table of 2 to 3 arrangements shows board shape and cost |
| L-09 | A part was chosen that was out of stock | A late part change | Live stock check before choosing (rule 24; `design-rules/cables.md` CB-04) |
| L-10 | Heavy modelling started before the user had seen any picture | Work redone after the first look | 2: block study and gate 0 before phase 3 |

## Phase 3: real parts and the model

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-11 | Block models and plain cylinders stood in for bought parts and screws; a module was stacked the wrong way because the maker's assembly page was not read. (Top 16 #14) | All renders and several manual pages redone, twice | 3: `vendor_parts.py` rows (real model, or block with a written reason); real library screws; the maker's page first (rule 9) |
| L-12 | Board numbers typed by hand into the box model drifted from the board. (Top 16 #16) | A connector inside a screw's tool space, found by the user | 3: `interface.json` with checksums; `interface_read.py`; `fit_check.py` refuses a changed board |
| L-13 | After a change, an old assembly, old views and a second output folder were left. (Top 16 #13) | Repeated "where are the new files?" rounds | Rule 4: `build.py` with the stale-file guard; `check_all.py`; one output folder |
| L-14 | A connector housing sat over a mounting hole. The user had reported it once already | The same fault found twice by the user | `fit_check.py` screw-head and tool-column rows; the picture-only review |
| L-15 | Connector 3D models had their origin at pin 1: in the board STEP they sat up to 4 mm off their footprints | A fit check that would have passed a wrong board | `fit_check.py`: connector bodies in the STEP against the interface's boxes |
| L-16 | A screw was placed where no driver could reach it after the next part went in | A printed clamp invented at assembly time | 4: tool columns at each step of the assembly order; `parcheck.py` sweeps |
| L-17 | A dimension of a bought part was assumed instead of measured or read | Parts that did not line up | Rule 9: ask the user to measure, with a sketch; list every provided dimension that was used |

## Phase 4: fit, heat, shielding

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-18 | A board's own small fan was removed on the idea that the case fan would do | The chip was very hot within a minute | `design-rules/heat-and-air.md` HA-05 |
| L-19 | A sensitive part sat in a fan's jet | Days of fault-finding in the wrong place | HA-03; `heat_air.py` stream flag |
| L-20 | Holes were dropped from a vent pattern to clear a screw | The part was sent back as ugly | `box_toolkit.hex_field` moves the whole group; FDM-13, SM-19 |
| L-21 | A wiring sheet had the 3-wire and the 4-wire fan swapped | Caught by the user at the bench | HA-08: the maker's pin-out page read first |
| L-22 | Ground bonds were designed as masked bare zones. With an all-over coat no designed bond was left; the lid floated | Hand scraping at assembly; taps for coated threads | `design-rules/shielding-and-ground.md` SG-06, SG-07; the ground-bond map |
| L-23 | A wireless link inside a metal box is easily planned without a test | The risk moves to the first samples | SG-09, SG-10 (the foil-wrapped concept) |
| L-24 | A part held between two bent sheet parts was over-constrained in height | Found by the independent review; shims added | `design-rules/sheet-metal.md` SM-18: the tolerance stack, never pull sheet with a screw |
| L-25 | Conductive gaskets were drawn on faces a lid slides over | Found by the independent review | SG-04 |
| L-26 | An unkeyed supply lead was folded inside a closed concept box and mated reversed | A burnt lead | SG-11; `cable_check.py` KEY; 14: polarity before power |
| L-27 | Board-edge coax connectors poked through oversize panel holes | A leak path the user pointed out | SG-05: panel jacks |

## Phase 5: cables in the model

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-28 | A cable was forgotten, and the user's choices of ends and routes came after the first drawings. A submitted quote cannot be edited. (Top 16 #4) | All cables re-entered as a new quote; a two-hour redraw; two quote numbers to track | 5: the full interconnect check and the choices first (CB-02, CB-03); 11: freeze |
| L-29 | Tolerances tighter than the maker's standard were silently drawn at the standard (+-5, its floor for every cable type); per-wire lengths brought a question. (Top 16 #15) | A marginal bend on a short coax; a question round | CB-11, CB-12; `cable_check.py` TOL; `cable_second_measure.py` REACH |
| L-30 | Two measurements of a short coax differed by several millimetres: one side had assumed a connector body length | An afternoon to find which was right | CB-06; `review-briefs/route-second-measure.md`: poses from the maker's drawing, with source |
| L-31 | A panel jack group was moved a few millimetres after the cables were ordered | An ordered short coax left with a marginal S-bend | CB-14, CB-15; the FRESH row; freeze before the quote |
| L-32 | A lead was routed over a board's connectors | Sent back: "under, not over" | CB-05 |
| L-33 | A header's gender and pitch were taken from a datasheet photo; the photo scaled to the wrong pitch | A wrong housing nearly ordered; the user measured the part | CB-04: the mating board's documents; ask the user to measure |
| L-34 | A flexible coax was planned whose bend radius needed more straight room than the box had | A change of cable type | CB-08: the radius from the datasheet before the route |
| L-87 | Lengths were designed at +-1 to +-3, and a crimped cable at route + 2; the maker's floor is +-5 for every cable type, RF included, and a tighter revision note cost a question round | Every length raised to route + 5; days of delay | CB-12, CB-13: design for +-5, the shortest cable still covering the route; `cable_second_measure.py` DESIGN (route floor) |
| L-88 | Cable types the maker does not stock were designed; one needed a custom mould | E-mail questions, routes re-checked for the stock cables | CB-26: design for the maker's only stock; `cable_check.py` NONDEF |

## Phases 6 and 7: print design, reviews, the print

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-35 | Printed parts broke: thin upright bars in a grille; a thin leg on a flat step. Holes printed 0.3 mm small. (Top 16 #11) | A scrapped shell and reprints | 6: `print_check.py` audit in print pose, the slicer's warnings, the coupon; FDM-04, FDM-05, FDM-10 |
| L-36 | Reviews were done by scripts and imagination: a connector over a screw hole, wrong details in renders. (Top 16 #12) | The same fault found twice by the user | 7 and 10: the picture-only reviewer; rule 6 |
| L-37 | The first full shell was the test piece: holes small, a head tunnel too tight, a post too close to a flat cable | The shell went into the bin | FDM-21: the coupon first; each misfit a named value |
| L-38 | A soft filament was planned without reading how that printer feeds it | The user feared a jam and stopped the plan | FDM-17: the printer maker's own guide first |
| L-39 | An agent was about to change slicer settings | Stopped by the user | Rule 15; `print_check.py --slice` works on copies |
| L-40 | Engraved text was proposed on plastic | Rejected | FDM-24, PG-04 |
| L-41 | Drawings and views made by a weaker model were sloppy and nobody had looked at them | A full redo | Rule 0; rule 6 |

## Phases 8 and 9: the metal version and the production documents

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-42 | The factory read the print file's CAD layer colours as inks: black text on the default index colour would have been printed white; a magenta "no print" outline stopped the part ("no magenta ink"). (Top 16 #2) | A part held in production; more than one answer round | 9: `silk_dxf.py` (layer colour = ink), the ink sheet and renders in the upload; 10: `ink_sheet.py --factory-view` and the picture-only review; PG-10 to PG-14 |
| L-43 | Drawings had missing dimensions; one part had an angled outline with undefined angles. (Top 16 #9) | A full drawing round before the quote | 8: simple outlines (SM-10); 9: `drawing_book.py` and `drawing_vs_step.py` |
| L-44 | A jack hole was drawn at its clearance size with no allowance for the coat | Holes that would need opening by hand | SM-13 (PROVISIONAL) |
| L-45 | Pockets, lands and countersinks of the printed concept were carried into thin sheet | Each needed a new answer | SM-09 |
| L-46 | A second ink was chosen from a colour system; the supplier substituted its nearest chart ink. A chart ink close to the coat's own colour was too light to read | An ink nobody had chosen on purpose | PG-08, PG-09: chart inks, contrast computed, final inks on samples |
| L-47 | A printed field ran to the edge of a cut-out; letter gaps were under the minimum | Found by the independent measure | `sheet_dfm.py` print rows; PG-05 to PG-07 |
| L-48 | STEP headers carried a personal name and a private machine address. (Top 16 #16) | Uploaded files that cannot be recalled | 11: `step_scrub.py`, `privacy_scan.py` |
| L-49 | Remarks asked for plugged threads and edge breaks; the supplier has its own standard | A question | `suppliers/jlccnc-sheet-metal.md` section 5: the remark model |
| L-50 | A panel legend stated a value that nobody had measured | A label that may be wrong on the samples | PG-01: "to be confirmed by measurement" |
| L-51 | Cable drawings carried internal notes (a clearance to a model part), a question with an alternative, and our own end names instead of the maker's | The only question of the quote; a translation at revise time | CB-16, CB-23; `cable_drawings.py` WORDS |
| L-52 | A coax was named by its bare family name; a slim network cable was only described | The maker drew its stock versions of both | CB-21: "X, NOT Y"; `cable_check.py` NONDEF |
| L-53 | Housings with empty positions had no cavity table; the rule was written only as a remark. (Top 16 #3) | Wires drawn in the wrong positions | CB-17; `cable_check.py` CAV |
| L-54 | "Plus two loose heat-shrink sleeves" was asked in a cable order | They came back fitted on the wires | CB-22 |
| L-55 | The orientation of mirror-image angled plugs was shown only by sketches on the drawing | An extra message and a render | CB-19: the picture with the quote |
| L-56 | Renders showed feet upside down and identical jacks drawn differently | Found by the user | The picture-only review, items B and D |

## Phase 10: independent checks

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-57 | The builder's own checks all passed; an independent measure of the exported files found several failures. (Top 16 #10) | Nothing: a failed supplier review was avoided, and the order got zero geometry questions | 10: `review-briefs/supplier-rules.md`; rule 5 |
| L-58 | A reviewer playing the supplier's engineer rated "chart colour, a colour-system colour if possible" as fine | The question that held a part for a day | `review-briefs/catalogue-and-drawings.md`: every non-catalogue word is a blocker |
| L-59 | Reviewers checked the print file's layer names and geometry, not what a viewer shows | See L-42 | The factory view in the picture-only review |

## Phases 11 and 12: freeze, quotes, orders

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-60 | Requests were sent at the weekend and at night in the supplier's country; Friday work waited for Monday. (Top 16 #6) | Working days idle, and half a day per step | 11: `supplier_calendar.py`; `suppliers/order-flow.md` section 3 |
| L-61 | The supplier's line numbers were not ours: an answer for "cable 4" was applied to another cable. (Top 16 #5) | A wrong length on a multi-wire harness, found only on the drawings | 12: the line map at the quote; both numbers in every message |
| L-62 | The total rose between review and payment. (Top 16 #8) | A clear rise over the total shown | 12: the total read again at the pay step |
| L-63 | A parts order planned for the same parcel was never placed. (Top 16 #8) | A late parts order | 13: the shipping plan ticked after each payment |
| L-64 | A form field did not take the typed value; a gauge set in the form came back different on the drawing | A wrong value sent | 12: read every field back (`cable_fieldsheet.py --readback`) |
| L-65 | An e-mail asked the supplier to confirm a combined shipment that the checkout screen had already shown | Three days for a yes | `suppliers/shipping-and-combine.md`: the re-priced screen is the proof |
| L-66 | The agent tried to go on at a checkout button that the safety system had blocked | Nothing, it stopped; the rule was written | `suppliers/order-flow.md` section 4 |
| L-67 | A wrong product category stood on the field sheet | Found by the independent check | The field sheet is reviewed in phase 10 |
| L-68 | An open quote had no deadline and no owner; the user had to remind the agent | A day | 13: the watch with deadlines |
| L-69 | Coupons offered at payment were not looked at | Money left unused | 12: coupons checked at the pay step |
| L-70 | On the board order, one resistor of a BOM line shared by several designators had to change after ordering; the assembler can change only the whole line | Three days of messages and an order on hold | The electronics skill's rule: a value that may change gets its own BOM line before ordering. Named here because the box order waited for it |
| L-70a | The board assembler's "please confirm parts placement" mail gives a fixed number of hours (72 were seen); after that the order goes into production as it is | A rotated part would have been built unchecked | The electronics skill's order watch. Named here because one calendar holds all three orders |

## Phase 13: the order watch

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-71 | Our own extra lines re-opened tickets: a line about nuts on a part with no nuts; a "just to confirm" mail. (Top 16 #7) | Half the question rounds on the case; most cable e-mails were avoidable | 13: answer only what is asked (`suppliers/after-order.md` section 2) |
| L-72 | Most of the cable production drawings came back wrong: pin positions, a gauge outside the crimp range, stock cable types, the standard tolerance. (Top 16 #3) | A revision round of a day or more on the critical path | 13: `production_drawing_check.py`, `review-briefs/production-drawing.md`, one Revise round |
| L-73 | Several points were "noted and confirmed" by e-mail after payment; only one reached the drawings | E-mails and a day | Only the production drawing counts |
| L-74 | An ink question was answered with a text and a picture; the factory then asked for a new drawing and a render | One more round on a held part | Answer artwork questions with corrected files; send the ink sheet and renders with the order |
| L-75 | Two people wrote about one question in separate threads within minutes; one thread looked closed | Nearly a missed request | Read every thread about the part |
| L-76 | A "revised drawing ready" mail arrived minutes after the first drawings, before any feedback | Confusion about which drawing was current | Check each drawing's date |
| L-77 | No "review completed" mail came; the only sign was a failed automatic payment | Two hours | The watch reads the order page |
| L-78 | Promised times ("10 to 60 minutes", "2 to 3 hours") were planned with | A plan that slipped daily | Rule 12: one supplier working day per question round |
| L-89 | A supplier question came as an e-mail holding only a picture, and an "addition" mail with another question followed minutes later | A question nearly missed | Open every attachment, read the whole thread, answer every open question in ONE reply (`suppliers/after-order.md` section 1) |
| L-90 | A value given for one cable was applied to another line, and the same mix-up came back a week later | One more round | Correct it in words each time and repeat the right value; both numbers on every line |
| L-91 | Revised cable drawings came back line by line; lines that needed a decision waited silently for a mail question | Lines idle for hours unnoticed | 13: watch the order data every 30 minutes during a drawing revision (`templates/WATCH_PROMPT.md`) |
| L-92 | After days of questions, one short polite note on the delay and its cost to the project was sent in the same thread | Nothing: a quick answer, and the order moved forward | 13: once, after a delay caused by questions |
| L-93 | Deviations that change nothing (a tighter twist pitch than drawn, a parts-list count unlike the drawing and test lines) were on a revised drawing | Nothing: accepted without a round | `review-briefs/production-drawing.md`: revise only what breaks fit or function |
| L-94 | A printed part took 2 to 3 more days after its powder coat; the whole case order shipped only when that part was done; the live chat gave a date, not a faster run | The case later than the tool's standard days | `suppliers/jlccnc-sheet-metal.md` section 7: plan 2 to 3 days for print after the coat |

## Phases 14 and 15: arrival and the manual

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-79 | Manual pages were long text with pictures of block parts and a wrong stack | Pages redone | 15: pictures first, real models, steps from the model's assembly order (`manual_build.py`) |
| L-80 | What was to be checked on arrival existed only as scattered notes | Nothing yet; the parts had not arrived | 14: the incoming check written before the parcel; `review-briefs/arrival-plan.md` |

## Working rules

| # | What happened | What it cost | Check |
|---|---|---|---|
| L-81 | A question "what do you think?" was taken as an order to change the design | Changes undone | `working-rules.md` section 2 |
| L-82 | Long answers hid what was done and what was left | The user lost track of the work | `working-rules.md` section 1 |
| L-83 | Agents were left running or hung, and a forgotten job was found later | Wasted hours; doubt about every "done" | `working-rules.md` section 5 |
| L-84 | A download was started by clicking in a browser; a save dialog opened that nobody could answer | A stuck session | Rule 21 |
| L-85 | A long job ran on one core with no progress output | It looked hung and was killed | Rule 22 |
| L-86 | The user was asked things a datasheet or the supplier's site could answer | Irritation | `working-rules.md` section 1 |

## Still open (not lessons yet)

These wait for evidence and are marked PROVISIONAL in the files they touch: whether drawn bare zones came coated;
clean nut threads; the real coat and ink colours; cut-outs after the coat; the hand-work minutes for ground bonds
and the continuity reached; each cable's real length, crimps and labels;
the import duty; the heat run against the estimate; the radio through the closed box; which manual pages change
after the first real assembly.
