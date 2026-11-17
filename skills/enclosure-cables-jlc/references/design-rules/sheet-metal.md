# Design rules: folded sheet metal (SM-nn)

Read in phase 8 (metal version) and by the supplier-rules reviewer in phase 10. Cite a rule by its ID.

Every supplier number below is "as read 2026-11 on the supplier's public help pages": re-read the live page before
every order and correct the project's capability sheet (`<project>/mech/suppliers/*.capability.toml`). The scripts take
the rule VALUES from that sheet, never from this page. "Margin that passed" means: one real order went
through the supplier's review with zero geometry questions at this value. One order: verify.

Sections waiting for the first parts on a bench are marked **PROVISIONAL**.

## The supplier's table (as read 2026-11; re-read the live page)

| Thickness t | Outer bend R | Min flange, single bend | Min flange, second bend | Round hole edge to bend | Square hole edge to bend |
|---|---|---|---|---|---|
| 1.0 | 1.8 | 3.8 | 5.5 | 3.3 | 3.8 |
| 1.2 | 2.0 | 5.0 | 6.5 | 3.6 | 5.0 |
| 1.5 | 2.75 | 6.0 | 8.5 | 4.5 | 6.0 |
| 2.0 | 3.7 | 8.0 | 10 | 6.0 | 8.0 |
| 2.5 | 5.0 | 10 | 12 | 7.5 | 10 |
| 3.0 | 6.0 | 13 | 19 | 9.0 | 13 |

- Thickness list for all sheet materials: 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0 mm. Model only these.
  The bend table as read has no row for 0.5, 0.8, 4.0, 5.0 and 6.0: read it on the live page.
- Aluminium sheet: 5052. Longest part: 800 mm.
- Holes: diameter at least t/2 and at least 1.0 mm. Hole to hole (web): at least 1.0 mm.
- U channel: inside width at least 12 mm for t 1 to 2 mm.
- Tolerances: general +-0.2, cutting +-0.1, bending +-0.3, bend angle +-1.0 degree, holes and threads +-0.1.
- Welding is not included by default.

## Geometry rules

### SM-01 One thickness, from the list
- Rule: one thickness per part, a value of the capability sheet's `[materials] thickness`.
- Check: `sheet_features.py` row SF-..-02; `sheet_dfm.py`. The quote tool reads the thickness from the STEP.
- Why: there is no thickness field on the form; a wrong solid is quoted as drawn.

### SM-02 Bends are true cylinders at the table's radius
- Rule: every bend in the STEP is a cylindrical face with the table's outer radius (inner = outer minus t). No sharp
  folds, no faceted or spline bends. `box_toolkit.u_shell`, `bend_sector` and `flange` make them.
- Check: `sheet_features.py` (sharp bends are listed and failed); `sheet_dfm.py`; look at a bend, zoomed.
- Why: the builder's checks looked at design parameters. The independent measure of the exported STEP found bends
  that were not cylinders; the supplier's file reader would have refused them.

### SM-03 Flanges and second bends
- Rule: a leg with one bend (a flange) at least the table's single-bend value, measured as its LOWEST reach along the
  whole bend (a tab narrower than the bend does not count). A leg between two bends (a U's floor, a Z's middle leg, a
  wall between a floor bend and a lip bend) at least the second-bend value.
- Number: margin that passed: second bend at least 8.5 at t 1.5 (the table value itself); very small brackets with
  both legs at least 6.0 were bent without a question; a lid closure with flanges at the single-bend minimum plus 0.5
  on both opposite edges of a wide floor passed against the single-bend 6.0 with no geometry question.
- Check: `sheet_dfm.py`, margins from `[sheet.margins] flange, flange_second`; every row says which reading it used.
- Why: a lip designed at 7 mm between two bends was 1.5 mm short of the second-bend value.

### SM-04 Holes and cut-outs keep their distance from a bend
- Rule: measure from the hole's edge to the bend's tangent line on the hole's own leg (the strict reading, the
  script's default) and add a margin. The other leg's outer face (tangent line + outer radius) is the lenient
  reading: use it only as a recorded decision when space forces it (`[sheet] hole_to_bend_from = "outer_face"`).
  Every row prints both numbers. Slots, windows and steps of the outline use the square-hole value.
- Number: margin that passed: table value + 0.5 mm measured to the OTHER leg's outer face (round holes 5.0, slots and
  windows 6.5 at t 1.5, that is 2.25 and 3.75 from the tangent line). The strict reading needs the outer radius
  (2.75 at t 1.5) more.
- Check: `sheet_dfm.py` (`[sheet] hole_to_bend_from`, `[sheet.margins] hole_to_bend`). Steps of the OUTLINE near a bend
  are not measured by the script: look.
- Why: the supplier's page does not say from where the distance is taken. The lenient reading plus 0.5 passed a
  supplier review; the strict reading cannot be questioned (SKILL.md rule 17).

### SM-05 Hole size and webs
- Rule: no hole under max(t/2, 1.0); webs between holes at least 1.0 (better at least t).
- Check: `sheet_dfm.py` (`[limits] hole_d_min, hole_d_min_t_factor, hole_to_hole`).
- Why: none in the project; from the supplier's table.

### SM-06 U channels wide enough for the tool
- Rule: the inside of any U at least the supplier's value plus a margin.
- Number: margin that passed: 12.5 mm inside at t 1.5 (rule 12).
- Check: `sheet_dfm.py` (`[limits] u_inside_min`, `[sheet.margins] u_inside`).
- Why: a small U bracket was 1 mm too narrow for the rule; found by the independent check, not by the builder.

### SM-07 Reliefs at every bend end
- Rule: where a bend ends inside the sheet, or two bends meet at a corner, cut a relief so the sheet does not continue
  past the bend end.
- Number: from one real project, verify: width at least t, reaching at least 0.5 mm past the bend's tangent line;
  1.5 wide and 1.0 past the bend line was used where there was room. General practice gives width t and depth t + R.
- Check: `sheet_dfm.py` relief rows (presence only, not size); look at every corner.
- Why: a second bend ended at a step with no relief; the supplier-rules reviewer raised it as a major.

### SM-08 One solid per file, no slivers
- Rule: one part = one STEP = one solid, as bent, in mm. No face under 0.01 mm2 and no edge under 0.1 mm (they come
  from near-coincident cuts and break file readers).
- Number: the two limits are the reviewer's own values from one project, not a supplier figure.
- Check: `sheet_features.py` (one solid); `sheet_dfm.py` (`[limits] tiny_face, tiny_edge`).
- Why: faces under 0.1 mm were found in the exported file; they had passed every design check.

### SM-09 No countersinks, no pockets, no recesses in thin sheet
- Rule: through-cuts only. Use pan or button heads into clinch nuts. A label goes flat on the surface.
- Number: an M3 90 degree head needs about 1.7 mm of depth: more than a 1.5 mm sheet.
- Check: `sheet_features.py` (every wide face must be one side of a wall); look.
- Why: the printed concept had pockets, lands and countersinks; each needed a new answer in sheet metal.

### SM-10 Simple rectangles and symmetric outlines
- Rule: a flat part is a rectangle with rounded corners unless function forbids it. Angles are 90 degrees.
- Check: `drawing_book.py` row DB-..-01 (a free-curve cut-out fails); the "supplier's engineer" read of phase 10.
- Why: a small plate with an angled outline left three dimensions and undefined angles on its drawing. As a rectangle
  it worked the same and raised no question.

## Hardware

### SM-11 Clinch nuts and studs: from the supplier's list, verify on the supplier's page
- Rule: choose the fastener code from the supplier's hardware page for this thickness. Metric only. Draw the sheet
  hole at the catalogue size. Keep the centre away from free edges and bends by the catalogue minimum plus a margin.
  Never on or over a bend. Check that the supplier lists the LENGTH you need (pressed standoffs come in few lengths).
- Number: as read 2026-11, verify on the supplier's page: nut family CLS, CLS-M3-2 in a 4.25 mm hole (body
  6.3 x 1.5), CLS-M4-2 in a 5.40 mm hole (body 7.9 x 2.0), listed for t of 1.4 and more. Centre to a free edge: the
  catalogue minimum is 4.8 (M3) and 6.9 (M4); 5.1 and 7.2 (+0.3 margin) passed a supplier review. Centre to a bend:
  the supplier's page said 7 (from where was not stated); 7.5 to the other leg's outer face passed a supplier review.
  `sheet_dfm.py` measures it to the tangent line by default (strict, as SM-04; 2.75 more at t 1.5 than the outer-face
  reading). Put the catalogue values in `[[sheet.hardware]]` and the margins in `[sheet.margins]`. The
  `CLINCH_NUTS` table in `box_toolkit.py` holds the same catalogue values: verify.
- Check: `sheet_dfm.py` hardware rows (`[[sheet.hardware]] code, hole_d, body_d, edge_min, bend_min`,
  `[sheet.margins] hardware_edge, hardware_bend`). Tool reach for pressing after bending is not checked: look.
- Why: nuts sat too close to an edge, and one had no tab of metal round it; found by the independent check.

### SM-12 Hardware is modelled, named, and pressed before the coat
- Rule: model each nut or stud at its real size on its install side, fused into the sheet solid (separate components
  turn the order into an assembly order). Name it at its hole in a table on the drawing. Tick the form's thread field
  and attach the drawing there. Ask nothing about plugging threads: the supplier presses before the coat by its own
  standard.
- Check: `sheet_features.py` hardware; `drawing_book.py` hardware table; `drawing_vs_step.py`.
- Why: the supplier's page says threads not shown on the 2D drawing are not made. A remark about "threads plugged"
  on a part with no nuts caused a question round.

## Coating and bonding

### SM-13 Coating allowance in cut-outs (PROVISIONAL)
- Rule: a coat makes every hole smaller. Add an allowance to every hole and cut-out of a coated part that a part must
  pass or a thread must enter.
- Number: PROVISIONAL, to be confirmed on the parts: +0.2 mm on the diameter for powder coat. A hole drawn at
  thread + 0.25 mm closes to about thread + 0.1 after the coat; draw about thread + 0.45.
- Check: the decisions table lists the allowance; look at each cut-out's dimension on the drawing; arrival check.
- Why: a jack hole drawn without the allowance would need opening by hand.

### SM-14 The coat is all over: plan the ground bonds another way
- Rule: draw no masking zones and ask for none unless the capability sheet shows the supplier offers masking. Plan
  bonds as in `shielding-and-ground.md` SG-06.
- Check: `catalogue_scan.py` (flags "mask"); look at every drawing sheet.
- Why: masking zones on the drawing stopped a part in review for a day; the factory coats all over.

## Construction

### SM-15 Tray and lid (numbers PROVISIONAL)
- Rule: the cheapest closed box is two U parts: a tray (floor + front + rear) and a lid (top + both sides), ordered as
  separate parts. Inside parts stay raw (unseen, conductive, cheaper).
- Number: PROVISIONAL, from one real project, passed the supplier's review, not yet assembled: the lid a little longer than
  the tray at each end (about a sheet thickness); a small gap between lid and side flange (a few tenths of a mm).
- Check: `fit_check.py`, `parcheck.py`; the tolerance stack (SM-18).
- Why: the same split as the printed concept kept every position.

### SM-16 Lid closure (numbers PROVISIONAL)
- Rule: the lid's sides close on a low flange along the tray's floor edges, with taller tabs at the screws carrying
  clinch nuts. Avoid edge meeting edge: the flange runs the whole depth and rises to the tabs on 45 degree tapers.
  Lid screws sit low on the sides. The lid must go on straight down by hand. The flange's height is its LOWEST point
  along the bend (SM-03): the tabs do not count.
- Number: PROVISIONAL, from one real project, passed the supplier's review, not yet assembled: flange at the
  single-bend minimum plus 0.5, taller tabs at the screws, nut 7.5 from the bend (to the other leg's outer face).
- Check: `parcheck.py` sweep of the lid; look at the closed seam in the render.
- Why: a first proposal left the lid's edge resting on the tray's edge.

### SM-17 Return flanges for stiffness
- Rule: a free wall edge is soft. A short return flange stiffens it. Estimate before and after.
- Number: guide: under about 0.3 mm at a 20 N push feels solid. An estimate, verify: short return flanges brought
  springy corners down to about that guide (to be felt on the parts).
- Check: `stiffness.py` (thin-plate estimate, no ribs: an estimate).
- Why: the first metal layout had end walls that would have rocked under a connector.

### SM-18 Tolerance stack on bends
- Rule: a wall of height h moves at its top by about h x 0.0175 per degree of bend error, plus the bending tolerance.
  Write the stack for every fit that crosses a bend: lid on tray, screws to nuts, a part held by two bent parts. Where
  two bent parts hold one part, one side seats and the other is shimmed. Never pull sheet metal into place with a screw.
- Number: with +-1.0 degree and +-0.3: a 50 mm wall moves about +-1.2 at its top (0.9 from the angle plus 0.3).
- Check: a row per fit in the check list (not scripted: `fit_check.py` has no tolerance stack).
- Why: a part held between a floor bracket and a crossbar on two bent ears was over-constrained in height; the
  independent review found it and shims fixed it.

### SM-19 Vent matrices are complete
- Rule: as FDM-13: a regular field; on a collision the whole group moves by whole pitches.
- Number: a starting value, verify: round holes of a few mm on a hex pitch, webs at least the supplier's minimum.
- Check: `box_toolkit.hex_field`; `drawing_book.py` pattern tables; look.
- Why: see FDM-13.

### SM-20 Feet (numbers PROVISIONAL)
- Rule: four bought feet on clinch nuts in the floor. The centre of mass lies well inside the feet rectangle.
- Number: PROVISIONAL, from one real project, not yet assembled: nuts of the feet's thread; the centre of mass well inside.
- Check: look at the low front render: are the feet the right way up?
- Why: a render showed the feet upside down; nobody had looked.

## Files

### SM-21 STEP export and header scrub
- Rule: export AP203 (the supplier's recommended schema, as read 2026-11), one part per file, with
  `box_toolkit.export_step(shape, path, company)` (AP203 by default; the written `FILE_SCHEMA` must name
  `CONFIG_CONTROL_DESIGN`). Scrub the header:
  CAD kernels write the PC's user and host names into it.
- Check: `step_scrub.py --check`; `privacy_scan.py` on the upload folder.
- Why: uploaded files carried a personal name and a private machine address in their headers.

### SM-22 The flat pattern is reference only
- Rule: print the flat pattern on the drawing marked "reference". The supplier unfolds the STEP with its own bend
  table and chooses the bend order.
- Number: `sheet_features.py` default K factor 0.44.
- Check: `sheet_features.py` row SF-..-06 (blank area x t within 3 % of the volume).
- Why: none; it stops a question.

### SM-23 What an independent measure found (several failures; the kinds recorded)
Non-cylindrical bends; a nut with no tab; a U 1 mm too narrow; nuts too close to edges; faces under 0.1 mm; letter gaps
under the minimum; print running into a cut-out; stale drawings; a wrong product category on the field sheet. All had
passed the builder's own checks, which looked at design targets and not at the exported files (SKILL.md rule 5).
