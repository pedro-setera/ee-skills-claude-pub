# Phase 8: metal version and catalogue finishes

Make the sheet-metal (or CNC) version of the box that has fitted as a print, to the supplier's rules for the chosen thickness, and choose colour, inks and panel wording only from the supplier's charts.

## Inputs

- Gate 1 and `PRINT_FINDINGS.md` (what fitted), or the user's written waiver of the print.
- The capability sheet of the metal supplier, re-read if older than this month (`suppliers/jlccnc-sheet-metal.capability.toml`), with `[sheet_rules."<thickness>"]`, `[limits]`, `[finishes]`, `[ink_rgb]`, `[coat_rgb]`.
- `scripts/box_toolkit.py` (`u_shell`, `bend_sector`, `flange`, `clinch_nut`, `hex_field`, `export_step`), `scripts/sheet_features.py`, `scripts/sheet_dfm.py`, `scripts/stiffness.py`, `scripts/render_blender.py`, `scripts/views.py`.
- `references/design-rules/sheet-metal.md`, `cnc.md` (**not proven by an order**), `panel-graphics.md`, `shielding-and-ground.md`; `references/suppliers/jlccnc-sheet-metal.md`.
- `templates/DECISIONS.md`, `GROUND_MAP.md` of phase 4.

## Steps

1. **Read the positions from the printed model, do not retype them.** The metal model imports the proven model's named values (board position, hole positions, panel cut-outs) and applies named shifts. What fitted in plastic stays where it was.
2. **Pick the thickness and its rule row.** Set `[sheet] thickness` and `supplier` in `mech.toml`. The supplier's values per thickness are data in the capability sheet (outer bend radius, smallest flange, smallest flange after a second bend, hole to bend for round and square holes, U channel width, hole size, hole to hole); your margins go in `[sheet.margins]`. No rule row for the thickness means the check cannot run. Use the margins of `references/design-rules/sheet-metal.md` that passed a real review with no geometry question.
3. **Model real sheet metal.** Every bend a true cylinder (`bend_sector`, `u_shell`), constant thickness, a relief at every bend end, one solid per part. Bends drawn as facets could not be unfolded. No pockets or countersinks in thin sheet. Clinch nuts from the supplier's own list, modelled at real size on their install side and fused into the part (`clinch_nut`); loose fasteners as separate components turn the order into an assembly order. The nut table of the toolkit holds typical values only: replace them with the live page's values in `[[sheet.hardware]]`.
4. **Keep flat parts simple:** rectangles and symmetric outlines. A small plate with an angled outline left three dimensions and several angles undefined; a rectangle did the same job and drew no question.
5. **Give coated parts their coating allowance.** Every hole and cut-out of a coated part is drawn larger by the allowance, as a named value. One past design drew +0.2 mm on cut-outs but left a threaded jack's hole near nominal; the coated hole would have been tight on the thread.

> **PROVISIONAL (waits for evidence):** the coating allowance (first value +0.2 mm per hole and cut-out for powder coat): cut-outs and holes measured after the coat on real parts, and whether nut threads arrive clean.

6. **Finishes are names from the charts, nothing else.** Powder colour: one chart name, the same in every coated part's field. Anodizing: a name from the list. Inks: chart names. Coating is all over: no masking, no colour-system numbers, unless the capability sheet shows the supplier offers them. The ground bonds follow `GROUND_MAP.md` (bare inner parts, toothed washers, a conductive catalogue finish, or scraping as listed hand-work). The words "if possible" after a non-chart colour stopped one part for more than two days.
7. **Measure the rules early, on the exported STEP.** Export one STEP per part with `export_step` into `out/step/`, list them in `[sheet] parts`, then
   `python -I <skill folder>/scripts/sheet_features.py --project <project>/mech --all`
   `python -I <skill folder>/scripts/sheet_dfm.py --project <project>/mech --all`
   Fix until no row fails. Phase 10 repeats this with an independent reviewer; do not leave it all for then.
8. **Stiffness and stack.** Re-run `stiffness.py` for lids and free walls (return flanges where a corner is springy) and redo the tolerance stack of phase 4 with the sheet's bend and angle tolerances.
9. **Propose the panel wording and graphics** (`references/design-rules/panel-graphics.md`): every label, its position and size, as a table the user accepts or changes. Label what is certain; a value that still waits for a measurement is not printed as fact.
10. **Render the options in the real chart colours.** Set `[render.finish.<part>] colour = "<chart name>"` (resolved through `[coat_rgb]` / `[ink_rgb]` of the capability sheet) and run `python -I <skill folder>/scripts/render_blender.py --project <project>/mech`. Show two or three colour and ink options side by side. The contrast of each ink on the coat colour is computed by `ink_sheet.py` in phase 9; aim for the highest. A chart ink close to the coat's own colour can be nearly invisible on it.

> **PROVISIONAL (waits for evidence):** the finish and ink advice (which chart inks read well on which coat colour, how close the chart swatches are to the real parts): compared on the first delivered samples. Suggest deciding the final inks of a larger batch on the samples.

11. **Write the decisions table with costs** (`DECISIONS.md`): thickness, material, finish, inks, print faces, nuts, feet, quantity, each with its options, its cost effect and the choice. Use the instant quote for costs where it needs no sign-in; mark each number with its date. Orders of magnitude from one past order only: a second set cost clearly less than a second full price; a print in three or more inks cost clearly more per part than one in one or two.
12. **Rebuild, merge, look.** `build.py`, `check_all.py`, then every view and render: each hole, nut, relief, vent group and label, zoomed.

## Questions for the user

- Colour of the box and inks of the print? (renders of the options, chart names)
  - Suggested: `<coat chart name>` with `<ink chart name>` for the text: the highest contrast.
  - Why: only chart names can be ordered; the pictures show the chart colours, and the real samples decide the next batch.
- The panel wording (table and picture). Accept, or change which lines?
  - Suggested: as proposed.
  - Why: every label was checked against the requirements; a changed word after the order costs a new print file.
- How many sets?
  - Suggested: 2.
  - Why: the second set adds little, and it is a spare for the fit check.
- (CNC or another finish, only if asked) This is **not proven by an order** in this skill. Go on with it?
  - Suggested: sheet metal unless a part cannot be folded.
  - Why: every sheet-metal step here was proven up to a real order and the supplier's review (the delivered parts
    are still to be measured: see the PROVISIONAL lines).

## Done when

- [ ] Positions come from the proven model by import. Evidence: the metal model's imports, no retyped board numbers.
- [ ] `sheet_features.py` and `sheet_dfm.py` pass for every part on the exported STEP. Evidence: `out/CHECKS.md` sections `features:` and `dfm:`.
- [ ] Every finish word is a chart name of the dated capability sheet. Evidence: `DECISIONS.md` against the sheet.
- [ ] Coated parts carry the coating allowance as a named value. Evidence: the model.
- [ ] The ground bonds use only what the finish allows. Evidence: `GROUND_MAP.md`, updated.
- [ ] The user picked colour, inks, wording and quantity. Evidence: their words and the date in the state file.
- [ ] Renders show the chosen chart colours and were looked at. Evidence: `out/renders/`, the "seen" notes.

## Outputs

- `out/step/<part>.step`, one solid per part
- `mech/DECISIONS.md` with costs and the user's choices
- Updated `GROUND_MAP.md`, `HEAT_TABLE.md` (vent areas of the metal version), renders

## If something is missing

- The path is a bought standard case with cut panels: only the panels are modelled; read the case maker's drawing for the panel size and the cut-out rules (`references/suppliers/standard-cases.md`; **not proven by an order**).
- No rule row for the wanted thickness: read it from the live page into the capability sheet, or choose a listed thickness.

## Lessons behind this phase

- Bends drawn as facets could not be unfolded by the maker's tool -> step 3: true cylinders.
- A plate with an angled outline left dimensions and angles undefined; a rectangle drew no question -> step 4.
- A non-chart colour followed by "if possible" held one part for more than two days -> step 6.
- A hole for a threaded jack was drawn with too little room for the coat -> step 5.
- A chart ink close to the coat's own colour was too light to read, and an ink asked by a colour-system name was replaced by the nearest chart ink -> steps 6 and 10: chart names, contrast shown before choosing.
- Nuts too close to edges and bends were found only by the independent check -> step 7: measure early on the exported STEP.

The full cases are in `references/lessons.md`.
