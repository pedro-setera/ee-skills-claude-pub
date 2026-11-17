# PCB rules: silkscreen

Purpose: label rules proven on real boards: plan labels before routing, minimums, ownership, clearances, groups, waivers for parts without a spot, polarity marks, legends, test-point names, hidden fields and the information block.

Contents
1. Plan labels before routing
2. Minimums
3. Designators belong to their own part
4. Clearances, measured on bounding boxes
5. Labels on one line, groups and leaders
6. When a part has no legal label spot
7. Polarity and pin-1 marks
8. Connector legends and test-point names
9. Hidden fields
10. Information block and order-number mark
11. What to verify, and how; typical mistakes

Silkscreen was the largest source of review rounds on the boards behind this skill: several visual rounds on one board. Most of that work disappears when labels are planned with placement.

## 1. Plan labels before routing

- SILK-01 MUST plan label positions with placement, BEFORE routing, and let the router keep vias at least 0.1 mm from every planned label. Why: one board ended routing with dozens of labels over vias.
- SILK-02 MUST count label room in the area budget (phases 2 and 8). A 1.0 mm label of three characters needs about 2.5 x 1.2 mm plus clearances (starting point). Why: on one board several parts ended with no legal label spot because no room was budgeted.
- SILK-03 MUST let electrical placement win. Move a part for its label only when the part is not electrically critical, and have the move re-checked by the layout reviewer. Why: a label never justifies a worse hot loop.
- SILK-04 SHOULD reserve the information block's area (open, via-free, track-free) at placement time. Why: an information block squeezed among connector labels was one of the user's findings.

## 2. Minimums

- SILK-10 MUST meet the fabricator's silkscreen minimums: text height 1.0 mm as the floor; line width: 0.15 mm was the minimum recorded in 2026-11; use 0.16 mm or more for new work and re-read the live minimum (`references/jlcpcb/capabilities.md`) before the order. Use one size for designators (1.0 mm high, 0.16-0.17 mm line); only the texts of SILK-13 go larger. Why: smaller text is blurred or dropped by the fabricator, and a line drawn exactly at a recorded minimum may sit just under the live one.
- SILK-11 MUST widen library silk lines and marks that are below the line minimum, or remove them. Why: libraries carried 0.12 mm lines and 0.06 mm pin-1 circles that the fabricator drops or clips.
- SILK-12 MUST set silkscreen text height and thickness as DRC errors (`general.md` GEN-53). Why: DRC then stops a text that is too small at once.
- SILK-13 SHOULD use about 1.2 mm text with a 0.16 mm or wider line for connector titles, test-point names and the information block where the label budget allows; 1.0 mm stays the floor (SILK-10). Why: text about eight strokes high reads clearly; 1.0 mm is the fabricator's minimum, not a target.

## 3. Designators belong to their own part

- SILK-20 MUST give every part a designator on its own side, next to it and lined up with it (within about 0.8 mm), readable after assembly, never hidden under the body. Why: a label under its part is gone after assembly.
- SILK-21 MUST make each label's centre nearer its own part than any other part, by at least 0.2 mm, and never place it between two other parts' bodies. Why: labels that read as the wrong part's were the most frequent visual finding.
- SILK-22 SHOULD use two text orientations only (reading from the bottom edge or from the right edge). Why: a technician reads the board from two sides, not four.

## 4. Clearances, measured on bounding boxes

These are house rules, deliberately stricter than the fabricator's minimums, and proven on two boards (starting points that worked):

| Between a label and | Minimum | Why |
|---|---|---|
| Any pad, its own part's included | 0.2 mm | Registration error; ink on a pad spoils the joint |
| Holes, pegs, through-hole pads, footprint marks, other footprints' texts | 0.5 mm | Clipped or unreadable next to drills and marks |
| Via copper | 0.1 mm, and no text over a via | Text over a via reads broken |
| Board edge | 0.4 mm for text, 0.2 mm for outlines | Clipped at the edge |
| Another text | 0.25 mm | Texts merge |
| Part outline line to another part's pad | 0.15 mm | The fabricator clips closer silk |
| Part outline line to its own part's pads | not on the pad; 0.15 mm for footprints of 0.5 mm pitch or finer (judged in the visual review) | The stock library footprints keep about 0.09 mm, and the fabricator clips what reaches the pad |
| Part outline line over a via | allowed over a covered via (listed); 0.1 mm from an uncovered one | Ink on a covered via is only cosmetic; on bare copper it is clipped |
| Footprint marks to vias | 0.2 mm | A mark on a via is lost |

- SILK-30 MUST hold these on each text's bounding box (the stricter reading) and print the stroke distance beside it. Why: a check on strokes passed where a reviewer measuring the boxes found text almost touching via copper.
- SILK-31 SHOULD use the bounding box plus about 0.1 mm as the router keep-out, not KiCad's text frame. Why: the frame is about 0.35 mm larger on each side and pushed fence and stitching vias out on one rebuild.

## 5. Labels on one line, groups and leaders

- SILK-40 MUST keep labels of different parts on one line at least 1.0 mm apart, end to end. Why: two short labels side by side (for example "R1" and "C2") read as one word ("R1C2") on two different boards.
- SILK-41 MAY label a tight cluster (a decoupling row, a feedback divider) as a labelled group: one aligned line just outside the cluster, each label on its own part's row or column. Test each name of a group text against its own part. Never generate automatic neighbour texts. Why: automatic group texts put names beside the wrong parts.
- SILK-42 MAY use a short leader line (about 3 mm or less; groups 4 mm or less) from the part to a free spot, when it crosses no other part. Why: a leader that crosses a part points at the wrong one.

## 6. When a part has no legal label spot

Try, in this order:
1. another legal spot for the label;
2. a labelled group or a leader;
3. moving the part, only if it is not electrically critical, with a re-check;
4. a waiver from the user.

- SILK-50 MUST bring waivers to the user as one list, each part with a zoomed crop (silk, pads, fabrication references and vias in distinct colours) and a suggested answer. Never leave a part unlabelled silently. Why: the user decides what the service technician will lack.
- SILK-51 MUST give every unlabelled part a readable reference on the assembly drawing, on the fabrication layer, inside its own body and as large as fits. Plot the assembly drawing and look at it: the whole page and the origin corner. Why: on one board, the references of the unlabelled parts were piled up at the board origin.

## 7. Polarity and pin-1 marks

- SILK-60 MUST give every polarised part exactly one pin-1 or polarity mark, visible with the part fitted, which in practice means outside the body outline. Remove second tiny marks on pads. Why: the fabricator clips marks on pads, and two marks confuse.
- SILK-61 MUST use the part's own convention (cathode band, LED cathode or colour, capacitor "+", IC dot or triangle) and check each polarised part again in the assembler's placement preview before payment (`references/phases/13-order.md`). Why: the assembler places by its own marks; a mismatch shows only in its preview.
- SILK-62 MUST mark a connector with symmetric pins at its housing's asymmetric feature (`connectors-mechanical.md` MECH-42). Why: a symmetric header fits both ways.
- SILK-63 SHOULD label LED colours and what each indicator state means, where space allows. Why: the user reads the indicator, not the schematic.

## 8. Connector legends and test-point names

- SILK-70 MUST generate pin legends from the current netlist: one label centred on each pad, checked against the schematic, and one title per connector (for example "J5 DISPLAY"). Regenerate after every pin-out or harness change. Why: one legend was shifted by one pin, and another still named a pin that a harness change had removed.
- SILK-71 MUST give each test point one text: reference over net (for example "TP3" over "3V3"). Why: two separate texts drift apart and read as other parts' labels.
- SILK-72 SHOULD move a long connector pin list into the information block rather than squeeze it between pin rows. Why: titles between pin rows were read as pin names.

## 9. Hidden fields

- SILK-80 MUST hide every non-reference field (distributor number, maker part number, assembly fields) or move it to a fabrication layer. Why: such fields printed on the top silkscreen of one board.
- SILK-81 MUST look at the silkscreen plots of both sides after every change, not only at the check report. Why: the checks once passed group texts that named the wrong parts.

## 10. Information block and order-number mark

- SILK-90 MUST place an information block in a large open area, via-free and track-free: board name, revision, date code, the company name the user gives (never a personal name unless the user asks), short safety or back-feed notes, and the order-number mark if used. Rotate it to fit, keep it readable and centred in its area, clear of connector labels; the bottom side is fine. Why: the block identifies the board for service and for the next revision.
- SILK-91 MUST decide how the fabricator's order number is handled. JLCPCB prints one on the board unless the order says otherwise; the current options (a marked position on the silkscreen, or removal) and their names and fees are in `references/jlcpcb/capabilities.md`. Reserve open space for it if a marked position is chosen. Why: otherwise the number lands wherever the fabricator finds room, perhaps across a label.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Heights, lines, clearances, ownership, group names, unlabelled list | `scripts/silk_check.py` (bounding boxes, strokes listed) | Report in `out/` |
| Silk rules in DRC | `scripts/drc_run.py` with silk-to-pad and text-size errors | DRC report |
| Labels read as their own part | A picture-only review from images (`references/review-briefs/visual.md`); two of them, working apart, in the full set | Visual reports with crop names |
| Image set | `scripts/review_images.py`: silk plots both sides, zoom tiles per label cluster, hole and connector crops | Contact sheet, tiles |
| Pin legends | Legend text per pad against the netlist | Legend table |
| Unlabelled parts | User waiver list with crops; assembly drawing plotted and looked at | State-file entry, crops, drawing |
| Polarity marks | Crops of every polarised part; later the assembler's preview | Crops, preview tiles |

## Typical mistakes

- The user's first 3D look showed labels colliding with other parts, an information block squeezed among connector labels, and a hole half covered by a connector; no script of that time caught any of them.
- Several labels read as the wrong part's: a test-point name nearer another point's net text, two resistor names side by side reading as one word.
- Automatic group texts put names beside the wrong parts; the visual re-review found them on images after the checks passed.
- A pin legend was shifted by one pin.
- Library silk lines of 0.12 mm and pin-1 circles of 0.06 mm sat below the fabricator's minimum.
- A designer's check measured strokes and passed; the reviewer measured bounding boxes and found text almost touching via copper.
- Distributor and part-number fields printed on the top silkscreen.
- Several parts had no legal label spot after every attempt; the user waived them in writing, with crops, and their references went onto the assembly drawing.
