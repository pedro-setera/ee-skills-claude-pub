# Phase 9: production documents

Generate everything a supplier will see: fully dimensioned drawings from the exported STEP, the print file with its ink sheet, renders, the cable drawings in the cable maker's format, the remark, and a field sheet with the value of every form field. Nothing in these files is typed twice, and nothing in them asks a question.

## Inputs

- Case: `out/step/<part>.step` (phase 8), `DECISIONS.md`, the metal supplier's capability sheet.
- Cables: `cables/cables.json` with final lengths (phase 5), the cable supplier's capability sheet.
- `scripts/sheet_features.py`, `silk_dxf.py`, `drawing_book.py`, `drawing_vs_step.py`, `sheet_dfm.py`, `ink_sheet.py`, `catalogue_scan.py`, `cable_drawings.py`, `cable_check.py`, `cable_fieldsheet.py`, `build.py`.
- `templates/FIELD_SHEET_enclosure.md`, `templates/REMARK.md`; `references/suppliers/jlccnc-sheet-metal.md`, `lcsc-cable.md`, `order-flow.md`; `references/design-rules/panel-graphics.md`, `cables.md`.

## Steps

### Case

1. **Read the features from the exported STEP:**
   `python -I <skill folder>/scripts/sheet_features.py --project <project>/mech --all`
   One `out/drawings/<part>.features.json` per part: panels with datums, holes, slots, cut-outs, patterns, hardware, bends, the flat pattern (reference only).
2. **Write the print file** when a part is printed. Describe the artwork in `silk/<part>_art.toml` (texts, lines, shapes, each with its ink by chart name) and run
   `python -I <skill folder>/scripts/silk_dxf.py --project <project>/mech --art <project>/mech/silk/<part>_art.toml`
   One layer per ink, named with the chart name, layer and shapes in that ink's true colour; outline and bend lines on two reference layers named `*_NOT_PRINTED`, each with a colour of its own (default: outline green, index 3; bend lines yellow, index 2, dashed; `[silk] outline_colour` / `bend_colour`), BYLAYER, open lines and arcs only, never index 7 or 0 and never an ink's colour (the script refuses that); text as outlines. An ink that is not on the chart is refused. On one order the factory read the CAD colours as inks: black text on the default colour (shown white on a dark screen) was nearly printed white, and a magenta "no print" outline stopped the part in production for "no magenta ink".
3. **Write the drawing books:**
   `python -I <skill folder>/scripts/drawing_book.py --project <project>/mech --all`
   One PDF per part: general sheet, one sheet per panel with every hole and cut-out from the datums, pattern tables, hardware table, bends, flat pattern, print positions. Tolerances and notes come verbatim from `[drawing]` in `mech.toml`: write only what the capability sheet states; no finish or colour word is added by the script. Put a render of the part next to the PDF (the book has no 3D view).
4. **Prove that the drawing equals the STEP:**
   `python -I <skill folder>/scripts/drawing_vs_step.py --project <project>/mech --all`
   It rebuilds every feature from the printed numbers and matches it to the STEP, and checks that every edge loop is covered. Drawings with "the main dimensions" drew a full round of questions before; fully dimensioned ones drew none.
5. **Measure the supplier's rules on what will be uploaded:**
   `python -I <skill folder>/scripts/sheet_dfm.py --project <project>/mech --all` (includes the print-file rules: text height, line width, gaps, distance to edges, bends and cut-outs, one ink per place).
6. **Make the ink sheet and the factory view:**
   `python -I <skill folder>/scripts/ink_sheet.py --project <project>/mech --dxf <project>/mech/out/silk/<part>_silk.dxf --coat "<chart name>"`
   `python -I <skill folder>/scripts/ink_sheet.py --project <project>/mech --factory-view --dxf <project>/mech/out/silk/<part>_silk.dxf`
   The ink sheet shows both faces 1:1 in the real ink colours on the coat colour, the ink table and the no-print zones (drawn on the sheet only, never in the DXF). The ink sheet also lists the reference layers as "NOT printed" with their colour. The factory view is the DXF as a plain viewer shows it on a dark background: the ink layers are the inks; the two reference layers are drawn dashed in their own colour (green, yellow) and labelled "NOT PRINTED (reference)"; any other colour, and anything white, would be read as an ink and fails. Look at both. A text answer about inks was not enough for one factory; they asked for a new drawing and a render. Send both with the order.
7. **Write the remark per part** from `templates/REMARK.md` into `orders/REMARK_<part>.md`: only what the fields cannot say, in the supplier's words, chart names, nothing that contradicts a field, no request the supplier applies by its own standard anyway. A remark line about nuts on a part with no nuts re-opened a ticket.
8. **Fill the field sheet** `orders/FIELD_SHEET_enclosure.md`: per part, the value of every field of the quote form as the capability sheet lists them (`[forms]`), and which file goes into which field. Form values are read from here in phase 12, never from memory.
9. **Assemble the upload folder** `out/upload/<supplier>/`: per part the STEP, the PDF, the print DXF, the ink sheet and the renders of the finished part, named after the part, in the packaging the supplier's page asks for (as read 2026-11 for JLCCNC sheet metal: one archive per part held all files and reached the reviewer; re-read the live page).

### Cables

10. **Draw the cables in the maker's own format:**
    `python -I <skill folder>/scripts/cable_drawings.py --project <project>/mech`
    One page per cable in `out/cables/drawings/` plus `cables_all.pdf`: ends P1/P2/P3, a wiring table "P1 position (colour) -> P2 position" with one row per cavity, a cavity table for every housing that lists every position including the EMPTY ones, a numbered housing face, one length with its tolerance, the label, each non-default as "X, NOT Y". Pin-map and orientation pictures go to `out/cables/pictures/`. On one order most of the production drawings came back wrong because the maker fell back on its stock defaults; cavity tables and "X, NOT Y" lines are the cure.
11. **Say two-row numbering in words and with a picture** ("pin 2 is NEXT TO pin 1, other row"); the maker numbers down one row and then the other unless told. Angled plugs get an orientation picture ("End A exits RIGHT, latch underneath").
12. **Check the data against the drawings:** `python -I <skill folder>/scripts/cable_check.py --project <project>/mech --netlist <pins.csv>` (after step 10: it wants the pictures to exist).
13. **Write the cable field sheet:** `python -I <skill folder>/scripts/cable_fieldsheet.py --project <project>/mech` gives `out/cables/FIELD_SHEET_cables.md`: per cable every form field, the files to upload, and the "More Requirements" text (numbered non-defaults plus the customer part number, nothing else). Forms for coax and network cables hold only drawings, a remark and a quantity (as read 2026-11; re-read): for those the drawing carries everything.
14. **Copy the cable upload set** to `out/upload/lcsc-cable/` (drawings and pictures per cable, within the file count and size limits of the capability sheet).

### Both

15. **Scan for words that are not catalogue values:**
    `python -I <skill folder>/scripts/catalogue_scan.py --sheet <project>/mech/suppliers/<id>.capability.toml <project>/mech/out/upload/<supplier> <project>/mech/orders`
    It flags request words ("if possible", "fallback", "please confirm"), colour-system names, masking, tolerances tighter than the standard, and layer names. Delete each hit or waive it with a reason. No internal notes, no questions, no alternatives, no product or board names in any file a supplier sees.
16. **Put all of this into the one build**, with `step_scrub.py --in-place` on `out/step/` as the step right after the export and before the drawings (the drawing's footer records the STEP checksum; a scrub made afterwards gives the uploaded file another checksum than the one on its drawing) (`[[build.steps]]` with their outputs), run `build.py` and `check_all.py`, then open every PDF page (`out/drawings/pages/`), the ink sheet, the factory view and every cable drawing, and write what you saw.

## Questions for the user

Nothing, normally. Only when a field has no value on the capability sheet:

- The form asks `<field>` and offers `<options>`. Which one?
  - Suggested: `<option>`.
  - Why: `<what it means for cost or look>`.

## Done when

- [ ] One PDF per part; `drawing_vs_step.py` passes for every part. Evidence: sections `drawing:` and `drawing=step:` of `out/CHECKS.md`.
- [ ] `sheet_dfm.py` passes on the exported STEP and DXF. Evidence: sections `dfm:` and `silk:`.
- [ ] The factory view shows only the chart ink colours plus the two reference layers (green outline, yellow dashed bend lines, "NOT PRINTED (reference)" in the legend; nothing white) and was looked at. Evidence: the `FV-` rows, the picture, the "seen" note.
- [ ] The ink sheet and renders are in the upload folder. Evidence: the folder listing.
- [ ] One drawing per cable, every housing with its cavity table; `cable_check.py` passes. Evidence: the rows, the pages looked at.
- [ ] Both field sheets exist and every field has one value. Evidence: `orders/FIELD_SHEET_enclosure.md`, `out/cables/FIELD_SHEET_cables.md`.
- [ ] `catalogue_scan.py` is clean, or each hit is waived with a reason. Evidence: its rows, `catalogue_waivers.toml`.
- [ ] The build is current. Evidence: the `build.py` output.

## Outputs

- `out/drawings/` (PDFs, page pictures, `drawing_manifest.json`), `out/silk/` (DXF, ink sheet, factory view)
- `out/cables/drawings/`, `out/cables/pictures/`, `out/cables/FIELD_SHEET_cables.md`
- `orders/FIELD_SHEET_enclosure.md`, `orders/REMARK_<part>.md`
- `out/upload/<supplier>/`, one folder per supplier

## If something is missing

- Finished files brought by the user: run steps 4 to 6, 12 and 15 on their files as far as the formats allow; what cannot be measured is "could not run" and goes to the reviewers of phase 10 as a named gap.
- A free-curve cut-out: the drawing book cannot dimension it and fails the row; replace it with lines and arcs.
- CNC parts: the sheet scripts do not apply; the drawing is made by hand to the same rule (every feature from a datum) and reviewed in phase 10. **Not proven by an order.**

## Lessons behind this phase

- The factory read CAD layer colours as inks; a part was held in production -> steps 2 and 6: layer colour = ink colour, and the factory view is looked at.
- A text answer about inks was not enough; the factory asked for a new drawing and a render -> step 6: the ink sheet and renders go up with the order.
- Drawings with missing dimensions drew a full round of corrections -> steps 3 and 4.
- Most of the cable production drawings came back at the maker's stock defaults -> steps 10 and 11: cavity tables, "X, NOT Y", pictures.
- A two-row housing was numbered down one row by the maker and across the rows by the board -> step 11.
- A remark line about a feature the part did not have re-opened a ticket -> step 7.
- Internal notes (clearances, part names) on a drawing sent to a supplier drew questions -> step 15.

The full cases are in `references/lessons.md`.
