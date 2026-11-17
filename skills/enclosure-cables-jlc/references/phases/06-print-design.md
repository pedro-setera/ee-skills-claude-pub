# Phase 6: design for printing

Split the box into parts that print well on the user's own printer, audit each part in its print orientation, slice with copies of the user's presets, and make a small test coupon that measures the printer before the big parts are printed.

## Inputs

- The model after phase 4, the cable routes of phase 5 (clamps and exits may add features).
- The printer profile (`[printer] profile` in `mech.toml`, a file in the user's home, outside the skill).
- `scripts/print_check.py`, `scripts/box_toolkit.py` (`print_pose`, `stand`, the `SCREWS` table), `scripts/build.py`.
- `references/design-rules/fdm-printing.md`, `references/suppliers/jlc3dp.md` (outside printing, **not proven by an order**), `references/tools.md`.

## Steps

1. **Ask the print questions** (next section) unless the profile already answers them: material, screws into plastic or inserts, whether supports are welcome. Do not add teardrop holes, tapers or splits by reflex against supports when the user's printer handles supports well: ask first.
2. **Split into parts that print flat.** Typical: a shell with the floor on the bed, a lid with its top face on the bed, brackets with their plate down. Print a bracket separately rather than as a supported outgrowth of a wall. Export each part in its print pose with `box_toolkit.print_pose(part, "<face>")` (the NAMED face of the part's bounding box goes on the bed: front = the face at the smallest y, back = the largest y, left = the smallest x, right = the largest x, top, bottom) into `out/print/<part>.stl` (and STEP), and list them under `[print] parts` in `mech.toml`.
3. **Draw the printer's numbers into the model.** Holes print smaller than drawn: use `hole_shrink_mm` of the profile (the coupon measures it; a common first value is about 0.3 mm). A hole drawn at a screw's size once printed 0.3 mm small and a screw head did not pass its tunnel. Self-tapping pilot holes come from the `SCREWS` table as a start and are corrected by the coupon. Slicer hole compensation stays off: the compensation is in the model, in one place.
4. **Fasteners for a concept:** self-tapping screws straight into plastic. No brass inserts unless the user asks. Posts get a wall thick enough for self-tapping (the toolkit's `stand` has a root flare); a thin post cracks when the screw is driven.
5. **Audit every part in its print orientation:**
   `python -I <skill folder>/scripts/print_check.py --project <project>/mech`
   Rows: inside the bed; overhang faces beyond the profile's limit; bridges; walls thinner than the minimum number of extrusion widths; small sections that start on a large flat face. Apply the rules of `references/design-rules/fdm-printing.md`: no thin part standing on a thick one with a flat step (give it a cone or a taper); no thin vertical bars in an upright wall (a perforated plate with webs instead); walls of at least two extrusion widths. Thin guard bars printed upright once snapped along their layers, and the tips of a bracket's legs snapped at a flat step: a scrapped shell and reprints. After one such finding, audit every other part for the same class of fault. The audit is approximate; a row of this kind is waived only after looking at the slicer preview.
6. **Slice with copies of the user's presets:**
   `python -I <skill folder>/scripts/print_check.py --project <project>/mech --slice`
   The presets named in the profile's `[slicer]` section are copied to a scratch folder; the user's settings are never opened for writing. Rows: time, grams, support moves, the slicer's own overhang, bridge and floating-shell marks. Supports fail the row unless `[print] allow_support = true` (set it when the user said supports are fine). The script makes no preview pictures: open the sliced file in the slicer (or ask the user for screenshots of the layer view at each flagged place) and write what you saw. The slicer is the final judge.
7. **Soft parts (TPU bumpers, feet).** Proven: soft parts printed in TPU 95A fitted well on one printer. Before proposing a spool path or nozzle, read the printer maker's own guide for that exact machine (some feeders must not carry soft filament) and give the nozzle temperature and drying data from the filament maker. Design soft parts with no overhangs beyond 45 degrees and slightly undersize where they stretch over a hard part; record in the profile the clearance that fitted.
8. **Make the test coupon:**
   `python -I <skill folder>/scripts/print_check.py --project <project>/mech --coupon --screws M2.5,M3`
   It writes `out/print/coupon/` (`coupon.stl`, `coupon.step`, `coupon_legend.png`, `coupon.json`): rows of holes from nominal to +0.5 mm per screw size, a self-tapping post per size, an overhang ladder, a tab and slot pair at three clearances. The user prints it first (minutes, a few grams), tries the screws and tabs, and reports which fitted. Write the results into the profile (`hole_shrink_mm`, the clearance that fitted) with the user's OK, rebuild, and re-run the audit.
9. **Write the slicing report** for the gate: per part the orientation, time, grams, supports yes or no, what the previews showed. Add the print settings the model relies on (for example extra bottom layers under stands) as a request to the user, never as a change to their presets.
10. **Rebuild and merge:** `python -I <skill folder>/scripts/build.py --project <project>/mech`, then `check_all.py`. Tell the user the folder of the print files.

## Questions for the user

- Which material for the concept?
  - Suggested: PLA.
  - Why: cheapest and easiest; the concept is thrown away after the fit check.
- Screws straight into the plastic, or brass inserts?
  - Suggested: self-tapping screws into plastic.
  - Why: enough for a concept that is opened a few times; inserts add parts and a soldering-iron step.
- Does your printer handle supports well, or should I design to avoid them?
  - Suggested: tell me; if supports are fine I keep the shapes simple.
  - Why: avoiding supports adds cones and splits that the metal version does not need.
- Will you print the test coupon first (about `<n>` minutes)?
  - Suggested: yes.
  - Why: it measures your printer's hole size and fit clearances before hours of printing.

## Done when

- [ ] Each part is exported in print pose and listed in `[print] parts`. Evidence: `out/print/`, `mech.toml`.
- [ ] The audit ran on every part; each fail is fixed or waived after a look at the slicer preview. Evidence: the `print_check` rows, the waiver lines with picture paths.
- [ ] The slice ran with copies of the user's presets, or the row reads "could not run" and the user sliced and sent the previews. Evidence: the rows; the previews looked at.
- [ ] Holes carry the profile's shrink; no slicer compensation is asked. Evidence: the named values in the model.
- [ ] The coupon files exist and the user was asked to print it first. Evidence: `out/print/coupon/`, the message.
- [ ] The user's slicer settings were not changed. Evidence: the profile's preset files are unchanged (their checksums before and after).

## Outputs

- `out/print/<part>.stl` / `.step` in print pose; `out/print/coupon/`
- The slicing report (in `GATE1_SUMMARY.md`)
- The printer profile with measured values (user profile, outside the skill)

## If something is missing

- No slicer command line: the audit still runs; the user slices and sends the time, the grams and screenshots of the preview at each flagged place; the slice rows stay "could not run".
- No printer profile: built-in defaults are used (bed 220 x 220 x 250, nozzle 0.4) and every row says so; the coupon becomes mandatory before the big parts.
- No printer at all: outside printing at JLC3DP is possible but **not proven by an order**; read its live pages into a capability sheet first.

## Lessons behind this phase

- Thin guard bars printed upright snapped along their layers -> step 5: audit in print orientation, perforated plates instead of bars.
- The tips of a bracket's legs snapped at a flat step onto a thick part -> step 5: cones and tapers; then every other part audited for the same class of fault.
- Holes printed 0.3 mm smaller than drawn and a screw head did not pass its tunnel -> steps 3 and 8: the profile's shrink and the coupon.
- Teardrop holes were added against supports that the user's printer handles well -> step 1: ask first.
- The user forbade any change to the slicer settings -> step 6: copies of the presets only.
- A soft filament was nearly sent through a feeder path that the printer's maker does not allow for it -> step 7: read the maker's guide for that exact machine.

The full cases are in `references/lessons.md`.
