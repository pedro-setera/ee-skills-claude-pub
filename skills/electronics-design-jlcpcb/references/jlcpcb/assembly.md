# JLCPCB assembly

What the assembler does, what it needs from the design, and what a sample batch costs: read at board definition (phase 8) and again when the production files are made (phase 12).

Facts here were read or observed in 2026-11. Re-read the live JLCPCB page before relying on any number, option name or fee.

## Contents
1. Sources
2. Economic or standard assembly
3. Which side, and assembling only some of the boards
4. Edge rails and fiducials
5. Tooling holes
6. Customer panels and mouse bites
7. Component-to-edge distance and overhanging parts
8. Through-hole parts
9. What goes in the BOM and placement file: hand-fit parts and DNP
10. The parts-placement confirmation option
11. Attrition
12. Fees and the cost model of a sample batch
13. Not recorded here
14. Process limits of a part: what to read on the day

## 1. Sources

- **[ORD4]** a 4-layer board, 5 PCBs, 2 assembled, ordered 2026-11.
- **[ORD2]** a 2-layer board as a customer panel, 5 panels, 2 assembled, ordered 2026-11.
- **[PAGES]** JLCPCB pages read 2026-11, by name: "how to add edge rails fiducials for pcb assembly order" and "specifications for adding process edges and positioning holes" (help articles), "mouse bite panelization guide" (blog), and the assembly terms (help article 61).
- **[CAP]** the 4-layer capability notes, 2026-11 (see `capabilities.md`).
- **[EST]** the cost estimate for 5 assembled samples, 2026-11, built from live part prices and the published fees.
- **[ENG]** the assembler's engineering e-mails, 2026-11.
- **[REV]** independent layout and electrical reviews of the two boards, 2026-11.

## 2. Economic or standard assembly

- Both boards were ordered as **Economic** assembly, top side only [ORD4, ORD2].
- Economic was recorded as one-sided [CAP]. Whether two-sided assembly forces Standard, and every other trigger (part types, board size, panel size, fine pitch): not recorded; read the live page.
- **Through-hole parts and the class:** an estimate warned that several through-hole connectors might move the order to Standard, with higher fees [EST]. On the day, the 4-layer order with those connectors on the top side went through as Economic, with JLCPCB soldering the through-hole parts [ORD4]. The estimate had priced that as a through-hole labour line plus per-joint fees; the price lines of the real order were not recorded. Estimate both price paths before deciding; confirm on the form which class the order lands in.

## 3. Which side, and assembling only some of the boards

- Put every assembled part on one side when the design allows: two sides raise the assembly price.
- **Assemble only some boards:** JLCPCB assembled 2 of 5 PCBs with Economic assembly on a 4-layer board; the other 3 arrived bare [ORD4]. On the panel order, 2 of 5 panels were assembled [ORD2].
- Ask early whether the run is a concept run. Size the assembly and every parts cart for the number of assembled boards, not the PCB minimum.

## 4. Edge rails and fiducials

From [PAGES], read 2026-11:
- **Edge rails ("process edges"):** at least 5 mm wide.
- **Fiducials:** 1 mm bare copper with a mask opening of twice the diameter; 3 to 4 along the edges or rails; at least 3.35 mm from the board edge; one page says "1 mm fiducials placed 3.85 mm from the panel edge". The panel on record used 3 fiducials at 3.85 mm (the stricter figure) and left one corner without, so the orientation is unambiguous.

Rails asked of JLCPCB on a single board [ORD4]:
- Parts sat close to the long edges and a connector overhung one short edge, so the plan was 5 mm rails on the two long sides only, the overhanging edge free.
- The sides were stated in the order remark (whether the form had a field for them was not recorded). The engineer then e-mailed to ask whether the remark should be followed or ignored, and the reply had to restate the rail sides [ENG].
- A customer panel with its own rails (section 6) removes that question.

## 5. Tooling holes

- **Rule:** a board or panel for JLCPCB assembly carries NO tooling holes of its own, and the order form says "Tooling holes: Added by JLCPCB". The form field and the files must agree: "Added by Customer" makes JLCPCB look in the files for its own kind of hole.
- **What happened [ORD2; ENG]:** the customer panel carried non-plated holes of 2.0 mm at the rail ends (the size that the page "specifications for adding process edges and positioning holes" gives), and the form said "Added by Customer". After the order was paid the engineer wrote that the holes added by the customer could not be found, suggested adding holes to the company's own requirements, and asked whether that was acceptable. The e-mail named no size. The reply: yes, add them on the rails, clear of the fiducials and the mouse-bite bridges, and keep the board's long edges free; JLCPCB confirmed the next morning. Cost: an e-mail round of most of a day. Such an e-mail can look alarming; it is routine and harmless, since the holes go in the waste rails.
- **What worked [ORD4]:** no tooling holes in the files and "Added by JLCPCB" in the form: no question about holes.
- **JLCPCB's own figures, read in 2026-11 [PAGES]; two of its pages disagree.** A FAQ on tooling holes: non-plated holes of 1.152 mm with 0.148 mm solder-mask clearance, two to three of them near the corners, for assembly orders only. The page on process edges: "2 mm tooling holes" (beside 5 mm process edges and 1 mm fiducials 3.85 mm from the panel edge). The 2 mm holes were the ones not found. The exact positions JLCPCB uses are not recorded here.
- **Only when the user needs the holes in the files** (their own fixture, another assembler's line): read both live pages that day; draw non-plated holes of JLCPCB's own size (1.152 mm with 0.148 mm mask clearance when last read), two or three near the corners of the rails, at the positions the live page gives; choose "Added by Customer"; and tell the user that this is not proven on a real order and may still bring the question. Never draw a hole of another size as a tooling hole for JLCPCB, and never settle a conflict between two pages by picking one.
- Keep the rails free for JLCPCB's holes: nothing on them but the fiducials and the ends of the bridges.
- A board without rails: where JLCPCB puts its own holes is not recorded here. A board with an antenna keep-out, an isolation barrier or any other area that must stay undrilled is ordered with rails or as a panel, so that the holes go into the rails.

## 6. Customer panels and mouse bites

Used when a board is too small, or its parts too close to the edges, for the assembly line [ORD2]:
- Example: a panel of a very small board, 5 mm rails on two ends, boards 2.0 mm apart; delivery format "Panel by Customer"; no depanelling by JLCPCB requested.
- **Mouse bites [PAGES, blog]:** 0.60 mm holes in sets of 5 to 8 (never fewer than 5); hole edge to hole edge 0.35 to 0.4 mm (minimum 0.3); at least 2 symmetric sets for boards up to 30 mm wide; spacing between units typically 1.6 or 2 mm, minimum 1.2 mm.
- Keep every part at least about 2 mm from a bridge. A ferrite 0.4 mm from a bridge would have cracked on snap-off; the bridge moved and the assembly note says "cut the bridges, never bend" [REV].
- Generate the panel's BOM and placement file from the board: designators become `<ref>_1`, `<ref>_2`, `<ref>_3`, and each copy's placement equals the board's moved by its offset. Run the panel's own DRC and a placement test.
- The panel's DRC needs one custom rule: holes 0.5 mm apart except inside a mouse-bite set.
- Hand-fit parts carry no 3D model in the panel render (a hand-fitted connector was drawn reaching into the next board).

## 7. Component-to-edge distance and overhanging parts

- **Assembly terms (help article 61), read 2026-11:** component bodies at least 2.5 mm from the edge the line holds. The 2-layer board had parts 0.4 mm from its edges, so it became a customer panel with rails; on the panel the parts sat well beyond that from the rails' outer edges [PAGES, REV].
- **Capability notes [CAP], 2026-11:** "parts within 3 to 5 mm of an edge need rails". This is a wider band than the 2.5 mm in the terms; the records do not reconcile them. Use the larger figure, or add rails.
- **Parts past the board edge** need JLCPCB's agreement [CAP]. A panel-type connector on the 4-layer board overhung the routed edge: declare it in the remark as intended, and keep rails off that edge.

## 8. Through-hole parts

Two ways were used:
- **JLCPCB solders them** (same side as the SMD parts) [ORD4]: several connectors; the estimate priced a per-joint through-hole fee and a labour line [EST]. Check on the form that they do not move the order to Standard (section 2).
- **Left out and hand-soldered by the user** [ORD2]: two connectors, left out to save the through-hole assembly cost. Give such parts longer pads and a keep-out for the iron (2.5 mm around the connector's pads on record), and put them in the LCSC parts cart.

## 9. What goes in the BOM and placement file: hand-fit parts and DNP

- **Hand-fit parts** (through-hole left out, a part fitted by hand with bent leads): not in the BOM, not in the placement file, no paste on their pads ("exclude from position files" in KiCad). List them in the assembly document with their orientation rule, and buy them at LCSC. The stock gate checks them against LCSC retail stock, not assembly stock.
- **DNP (do not populate):** the footprint stays on the board; the part is left out of the BOM and the placement file. In the placement viewer a DNP part must show as bare pads (see `after-order.md`).
- **One BOM line per value that may change.** A line shared by several designators can only be changed or left out as a whole after the order. Details in `parts-library.md` section 7.
- Write every hand-fit and DNP decision into the ordering checklist with the designators, so the remark and any later e-mail name the same parts.

## 10. The parts-placement confirmation option

- The form asks whether to confirm the parts placement. Both orders set **"Confirm parts placement: Yes"** [ORD4, ORD2].
- After payment, an e-mail asks for the confirmation; the confirmation must be given within 72 hours, or the order goes into production as it is.
- It is the last chance to see JLCPCB's actual placement, including any rotation its engineer changed. Procedure and permissions: `after-order.md` section 6.

## 11. Attrition

- JLCPCB buys more of each part than placed. The parts data carries a per-part attrition count, a minimum purchase quantity and a minimum patch quantity; the order quantity is per-board count x boards + attrition, raised to those minimums (see `parts-library.md` section 4).
- The stock gate uses: assembly stock >= per-board count x boards + attrition, with margin. The project's stock script added 20 % spares, at least 2, per line.
- A part whose stock barely covered the batch plus attrition was flagged and swapped for a pin-compatible part with ample stock [REV].
- What happens to leftover parts after assembly: not recorded.

## 12. Fees and the cost model of a sample batch

Fee structure as recorded for Economic assembly [EST, 2026-11]; the amounts are approximate rates, not a price of any order:
- **Setup fee:** once per order (about USD 8).
- **Stencil fee:** once per order (about USD 1.5).
- **Extended-part fee:** once per order for each extended part type (about USD 3 each). Basic parts carry none (`parts-library.md`).
- **Joints:** a fee per SMD joint (a fraction of a cent) and per through-hole joint (about 1.5 cents), plus a through-hole labour line.
- **Special-component fee:** seen as a warning at the BOM step for one connector, a few cents per piece [ORD4]. It was a fee, not a missing part.
- **Parts:** at the price step reached by the order quantity, attrition and minimums included.
- Then PCB, shipping and import VAT.

The cost model, from the 5-sample estimate:

| Item | Share of the estimate | Driven by |
|---|---|---|
| Fixed assembly fees (setup, stencil, extended parts, labour) | about half | number of extended part types |
| of which: extended-part fees | about 40 % of the total | count of extended types |
| Parts for 5 boards | about a third | attrition, minimums |
| PCB, joints, shipping | the rest | size, layers, courier |

- For the same board, 5 samples were estimated at about four times the per-board cost of a 100-board run, before shipping and VAT.
- Show the user this split: per-part cost against per-order fees, and the count of extended parts (`references/working-rules.md` section 11).
- Cut the fixed part first: basic substitutes for extended lines; extended parts not needed in the first samples left unfitted; hand-fit through-hole parts if that avoids a class change.
- The extended-part fee pushes toward sharing BOM lines. Share a line only for values that can never change.
- Record the landed total after payment: the shipping and tax choice at checkout can raise it (`order-flow.md`).

## 13. Not recorded here

- The full list of what forces Standard assembly; two-sided assembly rules and prices.
- Current setup, stencil, joint and extended-part fees; whether preferred parts pay the extended-part fee.
- Minimum and maximum board or panel size for the assembly line; maximum part height.
- Whether JLCPCB returns or keeps leftover parts; options for consigned (customer-supplied) parts.
- Depanelling service and its price; conformal coating; X-ray or test options.

## 14. Process limits of a part: what to read on the day

Phase 3 (step 6b) notes, for the parts where it matters, what process each part needs; phase 12 (step 3b) checks it against the assembler before the freeze. None of the assembler's answers is recorded here: check each on the live page on the day. Where the page does not settle a fact that decides whether the board can be built or accepted, that is the one question of `references/working-rules.md` section 9.
- How each part is soldered: reflow, wave or by hand, for through-hole parts and for a second side.
- Moisture-sensitive parts: that the assembler's controlled storage and baking cover their level and floor life. Get their assurance; never write a baking recipe of your own.
- Reflow passes: whether a two-sided board sends the first side through the oven again, against each part's allowed number of cycles.
- Parts that do not stand reflow heat (some connectors, batteries, modules, displays): whether the assembler places them, or they are fitted by hand.
- Cleaning: whether boards are washed, and with what, against parts that must stay dry or clean (an open sensor, a buzzer, an unsealed switch).
- Hidden joints (pads under the body, leadless and ball-grid packages): how they are inspected and reworked, and whether X-ray inspection is offered, at what price, and ordered. It is never assumed included.
