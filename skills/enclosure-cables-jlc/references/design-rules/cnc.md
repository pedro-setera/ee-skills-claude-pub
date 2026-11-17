# Design rules: CNC-machined parts (CNC-nn)

**Not proven by an order: written from general practice and the supplier's pages; re-read them.** No part designed
with this file has been ordered, reviewed by a supplier or measured. Say so to the user when a project uses it.
Supplier numbers are "as read 2026-11 on the supplier's public CNC design guide and quote tool". Before any CNC quote
an independent agent reads every live rule page (`review-briefs/supplier-rules.md`) and the project's capability sheet
for CNC is filled from them (`suppliers/jlccnc-cnc.md` lists what to read).

Use CNC only where sheet metal cannot make the part (economy rule, SKILL.md rule 18): a heat spreader, a thick
bracket, a block with pockets, a front plate with a recess. A milled box costs several times a folded one.

How to read a rule: the rule; **Number** with its source; **Check**; **Why**.

### CNC-01 Decide what must be milled, and keep it small
- Rule: list the features that need milling (pocket, recess, countersink, thick section). If none, use sheet metal.
- Number: a rough guide from one supplier's public price points in 2026-11, not a quote: a milled box cost 3 to 6
  times the folded one of the same size. Read the live quote.
- Check: the process table of phase 1; look.
- Why: economy. No failure from the project.

### CNC-02 Internal corners have a radius
- Rule: every inside corner of a pocket has a radius the tool can cut. A square inside corner cannot be milled.
  Where a square part must sit in a pocket, relieve the corners ("dog bones") or round the part.
- Number: as read 2026-11, re-read: R = depth/10 + 0.5 mm for a pocket of that depth (30 deep needs R 3.5); pockets
  up to 3 mm deep may have R 0.5.
- Check: no script in this skill measures it. Look at every pocket; list each inside radius against its depth in the
  check list. Row verdict "could not run" until someone has measured the exported STEP.
- Why: general practice.

### CNC-03 Pocket depth against tool diameter
- Rule: keep pockets shallow against their narrowest width.
- Number: as read 2026-11, re-read: best at 2 to 3 times the tool diameter; 5 times or more needs special tools.
- Check: look; list in the check list.
- Why: general practice (deep narrow pockets chatter and cost).

### CNC-04 Wall and floor thickness
- Rule: no thin walls or floors left standing after milling.
- Number: as read 2026-11, re-read: metal walls 0.8 mm recommended, 0.5 mm absolute minimum. For a floor under a
  pocket and for plastics: read it on the live page.
- Check: look; a section view through each pocket.
- Why: general practice (thin walls move under the cutter).

### CNC-05 Holes: standard drill sizes, limited depth
- Rule: use standard drill diameters. Keep hole depth moderate against diameter. Flat-bottomed holes cost more than
  drilled ones.
- Number: depth limit per diameter: read it on the live page (not in the notes this skill was written from).
- Check: look; the hole table on the drawing.
- Why: general practice.

### CNC-06 Threads
- Rule: model the tap-drill hole, not the thread. Put thread size and depth on the 2D drawing and set the form's
  thread field to yes. Leave unthreaded depth at the bottom of a blind hole.
- Number: as read 2026-11, re-read: M3 is modelled as a 2.5 mm hole; thread length up to 3 x diameter; in blind
  holes leave at least 0.5 x diameter unthreaded.
- Check: the drawing's thread table against the model's holes; look.
- Why: the supplier's page says threads are made strictly from the 2D drawing: a thread only in the 3D model is not cut.

### CNC-07 Tolerances: only from the supplier's standard list
- Rule: the default tolerance class for everything. A tighter value only on the few dimensions that need it, chosen
  from the form's own list and marked on the drawing. Never a value that is not on the list (SKILL.md rule 1).
- Number: as read 2026-11, re-read: default ISO 2768 medium; the quote tool offered +-0.10, +-0.05 and +-0.02 for
  areas marked on the drawing.
- Check: `catalogue_scan.py` with the CNC capability sheet (`[limits] standard_tolerance`); look.
- Why: at the cable supplier a tolerance tighter than standard was silently drawn at the standard. Assume the same
  until an order proves otherwise.

### CNC-08 Where the form and the drawing differ, the form wins
- Rule: every form field and the drawing say the same thing. Fill the field sheet from the same data as the drawing.
- Number: as read 2026-11: the supplier's ordering guide says the web selections prevail over the drawing.
- Check: the field sheet read back against the drawing in phase 12.
- Why: general; it removes one question.

### CNC-09 Finishes from the chart only
- Rule: finish, colour and gloss are names from the supplier's CNC finish list and colour chart. No RAL, no Pantone,
  no "similar to". Marking (laser or UV print) needs a 2D file at 1:1.
- Number: as read 2026-11, re-read: bead blasting, anodizing in nine named colours (matte or glossy), conductive
  anodizing, hardcoat anodizing (colours come out darker), brushing on flat faces only, UV printing in eight named
  colours, laser marking in one tone. Anodizing excluded bead blasting by default. Threaded holes below M5 were not
  anodized (plugged).
- Check: `catalogue_scan.py`; the decisions table shows only chart names.
- Why: a colour-system name in a remark stopped a sheet-metal part in review for a day.

### CNC-10 Marking limits
- Rule: UV print and laser marking have their own minimum text and margins. Treat them like silkscreen
  (`panel-graphics.md`) with the CNC page's numbers.
- Number: as read 2026-11, re-read: UV print: avoid text under 6 pt (about 2.1 mm), lines at least 0.176 mm; laser
  marking: 3 mm margin.
- Check: look; no script measures CNC marking files (`sheet_dfm.py` measures sheet-metal print files only).
- Why: general.

### CNC-11 Conductive surfaces for ground bonds
- Rule: an anodized part does not conduct. For a bond choose a conductive finish only if it is on the capability
  sheet, or plan the bond as in `shielding-and-ground.md` SG-06.
- Check: the ground-bond map of phase 4.
- Why: the same lesson as SM-14.

### CNC-12 One body per file, drawing with every toleranced feature
- Rule: one part per STEP. The 2D drawing carries threads, tolerances, marking and surface roughness asks. Multi-body
  files and more than a small quantity leave the instant quote and go to a manual quote.
- Number: as read 2026-11, re-read: no automatic quote above 20 pieces, for multi-body files or unrecognised features.
- Check: `step_scrub.py --check`, `privacy_scan.py`; look at the drawing.
- Why: general.

### CNC-13 What this skill cannot check for CNC
`sheet_features.py`, `sheet_dfm.py`, `drawing_book.py` and `drawing_vs_step.py` are written for folded sheet. For a
milled part: `fit_check.py`, `parcheck.py`, `views.py`, `render_blender.py`, `stiffness.py` (plate and cantilever),
`catalogue_scan.py`, `step_scrub.py` and `privacy_scan.py` work; the rule measure and the dimensioned drawing do not.
Write those rows as "could not run", make the drawing in a CAD tool or by hand, and let the supplier-rules reviewer
measure the STEP with its own code.
