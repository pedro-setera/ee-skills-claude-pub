# Design rules: panels and their graphics (PG-nn)

Read in phase 2 (panel layout), phase 8 (colour, inks, wording) and phase 9 (the print file). Cite a rule by its ID.

Supplier numbers are "as read 2026-11 on the supplier's public sheet-metal pages and in its order answers":
re-read the live pages and charts before every order and correct the capability sheet. The scripts take rule values
and ink colours from that sheet. The advice on ink choice is **PROVISIONAL** until the first printed parts are seen.

How to read a rule: the rule; **Number** with its source; **Check**; **Why**.

## Layout and wording

### PG-01 Propose the panel layout and the wording; the user accepts or changes
- Rule: draw each panel with its parts and a proposed legend for each: what it is, direction, rating, warning.
  Keep words short and standard. The user confirms wording in phase 8, once.
- Check: the decisions table holds the approved wording with the date; look at the panel views.
- Why: wording changed three times after drawings were made. A legend that states a level or a range is a
  measurement claim: mark it "to be confirmed by measurement" until it is.

### PG-02 Panel-mounted parts must reach
- Rule: for every part that passes a wall, add up: wall + washer + nut, and check the thread or body left over for
  the mating plug. A board-mounted connector must stand far enough out of the board edge to reach the wall's outer
  face, or it needs a panel-type part.
- Number: an example: a 10 mm thread through a 1.5 mm wall, a 1 mm washer and a 2.5 mm nut leaves 5 mm for a plug
  that needs about 4 mm.
- Check: `layout_study.py` panel-part reach rows; `fit_check.py` connector rows; look at a section view with the plug
  mated.
- Why: a board connector and an LED sat "too much inside the board" to reach the wall; the user asked whether a jack
  was long enough for wall, washer and nut "and still have good thread".

### PG-03 A balanced layout
- Rule: centre what can be centred (a fan, a display), align connector groups, keep equal margins to edges and
  between groups. Leave room for a tool on every nut and for fingers on every plug.
- Number: none; check a socket on each nut at the chosen pitch.
- Check: look at the front and rear views; a tool-clearance row per nut in the check list.
- Why: a box was enlarged so that a part could be centred, and a connector group was moved because its legend sat
  too close to the edge.

### PG-04 No engraving on plastic unless asked
- Rule: on printed concept parts legends are shown in views and renders only.
- Check: look.
- Why: the user rejected engraved text on plastic.

## Silkscreen on sheet metal

### PG-05 The supplier's print rules (as read 2026-11; re-read the live page)
- Rule: text at least 2.0 mm high; lines at least 0.2 mm; gap between characters at least 0.3 mm; at least 1.0 mm
  from text to a bend or an outer edge; solid fills, no hatch; the file shows the face as it looks AFTER bending,
  1:1, with the outer contour and holes.
- Number: these four are the capability sheet's `[silk_rules] min_text_height, min_line, min_gap, edge_clearance`.
- Check: `silk_dxf.py` reads its own file back; `sheet_dfm.py` rows S01 to S11.
- Why: letter gaps of 0.008 mm and a print area running into a cut-out were found on the exported file by the
  independent measure.

### PG-06 The margins used (they passed one review without a question)
- Rule: design above the minimums.
- Number: values that passed a supplier review, verify on the live page: capitals at least 2.3 mm; strokes at least 0.25; gaps at least 0.35; counters
  (the holes in letters) at least 0.3; print at least 1.0 from every edge, bend and cut-out, also from windows and
  holes; legends at least 1.5 from the corners of a nut that can turn. Set `[sheet.margins] silk`.
- Check: `sheet_dfm.py` print rows with the margin.
- Why: lower-case letters of a 2.0 mm line fall under the minimum; capitals at 2.3 avoid the argument.

### PG-07 A dark field stops short of a cut-out
- Rule: a printed area cannot reach the edge of a window or hole. Stop it at the clearance and show the user the
  resulting line of bare coat in the render.
- Number: 1.0 mm rule; draw a little over it.
- Check: `sheet_dfm.py` (print over or near a cut-out); look at the render, zoomed.
- Why: the user accepted the 1 mm line as a frame only after seeing it.

### PG-08 Inks and coat colours from the charts only
- Rule: the coat is a name from the supplier's powder or anodizing chart, the same name in every part's finish
  field. Each ink is a name from the ink chart. No RAL, no Pantone, no "or similar", no fallback. Nothing else about
  colour anywhere: not in a remark, not on a drawing, not in a layer name.
- Number: as read 2026-11: 12 ink names and 12 powder names are in `templates/jlccnc-sheet-metal.capability.toml`.
- Check: `silk_dxf.py` refuses an ink that is not on the sheet; `catalogue_scan.py` on the upload folder.
- Why: "a colour-system colour if possible" in a remark stopped one part for a day although its field was right. A
  colour-system ink name was replaced by the supplier with its nearest chart ink.

### PG-09 Compute the contrast of each ink on the coat
- Rule: compute the contrast ratio of every candidate ink on the coat colour. Offer the highest for the main text.
  Show rendered options. Decide final inks on the first samples: chart pictures are not the parts.
- Number: approximate, from the chart-picture colours, computed as `ink_sheet.py` does (WCAG ratio): a dark ink on a
  light coat gives the highest ratio (a real black ink is a little lighter than pure black, so a little less); a
  pale ink on a light coat can stay under 2:1 (too weak for text, fine for a line). A chart ink close to the coat's
  own colour can be too light to read.
- Check: `ink_sheet.py` contrast row (fails only when `[silk] min_contrast` is set); look at the ink sheet.
- Why: the second ink was chosen from a screen picture; whether it reads on the real part is still to be seen.

### PG-10 Layer colour = ink colour
- Rule: in the print file each ink has one layer, named with the chart name, and the layer and every entity on it
  have the true colour of that ink. Black ink is drawn black, not in the CAD "white/black" index colour.
- Number: `[ink_rgb]` of the capability sheet; approximate values from the chart picture.
- Check: `silk_dxf.py` (layers `BLACK`, `RED`, ..., never index 7 for anything in the file); `ink_sheet.py --factory-view`
  rows FV.
- Why: the factory read CAD layer colours as inks. Black text on the default index colour shows white on a dark
  screen: it was nearly printed white.

### PG-11 Reference layers have a colour of their own; nothing else is coloured; no closed shapes
- Rule: the cut edges (outline and cut-outs) and the bend lines go on two reference layers, `OUTLINE_NOT_PRINTED` and
  `BEND_LINE_NOT_PRINTED` (names end in `_NOT_PRINTED`): open lines and arcs only, every entity BYLAYER, the outline
  green (AutoCAD index 3), the bend lines yellow (index 2) DASHED. NEVER the default index 7 or 0 (a plain viewer
  draws it white and a factory reads white as an ink), never white, never the colour of an ink layer of the same
  file, never a closed shape. No "sticker area" or "no print" outline in the file: such zones go on the PDF's ink
  sheet only. The ink sheet lists both layers as "NOT printed".
- Number: a corrected print file with the cut edges on a green layer and the bend lines on a yellow dashed one,
  BYLAYER, open lines and arcs only, and an ink sheet that listed both as "NOT printed", passed a supplier review
  with no question about them (the questions were about index-7 text and a closed magenta helper shape).
- Check: `silk_dxf.py` row REF (refuses index 7 / 0 / white, an ink's colour, a name not ending `_NOT_PRINTED`);
  `ink_sheet.py --factory-view` rows FV-03 (colour of the reference layers), FV-04 (a closed shape fails), FV-06
  (layer names).
- Why: a magenta "no print here" rectangle stopped production: "we have no magenta ink".

### PG-12 One print file per part, letters as outlines
- Rule: one file per part with all its printed faces side by side. No text entities: letters are filled outlines.
  Faces are named on the PDF, not in the file.
- Number: as read 2026-11: the quote tool takes one silkscreen file per part.
- Check: `silk_dxf.py`; `ink_sheet.py --factory-view` (a text entity fails).
- Why: fonts are not embedded in such files; a missing font changes every glyph.

### PG-13 The ink sheet and renders go WITH the order
- Rule: upload, with the part: a one-page ink sheet (each face 1:1 in the real ink colours on the coat colour, an
  ink table "layer -> chart ink -> swatch", the reference layers listed as "NOT printed" with their colour, no-print
  zones dashed and named, the line "Print ONLY <n> inks: <names>. Lines on <layers> are references and are NOT
  printed.") and front and
  rear renders of the finished part with a note on what in them is not printed.
- Check: `ink_sheet.py` rows IS; the upload folder list in the field sheet.
- Why: the print step asked for exactly these two things after a text answer was not enough: one more round on a
  held part.

### PG-14 The dark-viewer factory view
- Rule: before upload, look at the print file as the factory will: a plain viewer, dark background. Every colour on an
  ink layer will be read as an ink; the two reference layers are drawn dashed in a colour of their own (green,
  yellow) and the legend says "NOT PRINTED (reference)"; any other colour, and anything white, is a fault. `ink_sheet.py --factory-view` makes that picture and checks it; open it anyway.
- Number: default background `#212830`.
- Check: rows FV-..-01 to 06; look; the picture-only reviewer gets this picture.
- Why: the supplier's file review does not check inks. The question came only during production and held the part.

### PG-15 What silkscreen costs
- Rule: tell the user how the supplier prices print before they choose inks.
- Number: from one past order, rough: priced per part by colour mode (one or two inks one price, three or more inks
  a higher price), not per face or per ink; a small amount per part.
- Check: the decisions table shows the cost of each option.
- Why: economy; three or more inks cost clearly more than one or two.

### PG-16 Stickers and serial numbers
- Rule: fixed text is printed. Variable text (serial, code) is a sticker on plain coat. Reserve its area on the ink
  sheet, not in the print file (PG-11).
- Check: look.
- Why: see PG-11.

## Other marking (not proven by an order)

Laser marking (one tone, set by material and finish) and UV printing (CNC parts) exist on the supplier's lists as
read 2026-11. Their rules differ: read them on the live page (`cnc.md` CNC-10).
