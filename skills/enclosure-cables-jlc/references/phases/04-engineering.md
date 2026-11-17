# Phase 4: fit, heat, shielding

Prove in the model that every part fits, goes in and comes out; estimate heat and air flow and name the bench test that proves it; plan shielding and the ground bonds with what the supplier's finish really allows.

## Inputs

- The model of phase 3 with real parts, `interface.json`, the board's STEP, the capability sheets ("what is not offered").
- `scripts/fit_check.py`, `scripts/parcheck.py`, `scripts/heat_air.py`, `scripts/stiffness.py`, `scripts/box_toolkit.py` (`vent_area_ratio`, `thread_budget`), `scripts/check_all.py`.
- `templates/HEAT_TABLE.md`, `templates/GROUND_MAP.md`, `templates/heat.example.toml`, `templates/stiffness.example.toml`.
- `references/design-rules/heat-and-air.md`, `shielding-and-ground.md`; `references/interface-electronics.md`.

## Steps

### Fit

1. **Check the board in the box:**
   `python -I <skill folder>/scripts/fit_check.py --project <project>/mech`
   It refuses a STEP whose checksum differs from the interface file. Rows: interference, each hole on its stand, the screw head and the screwdriver column of every hole free up to the lid (the lid needs its access holes), each connector's body against its wall (`[fit.connectors.<ref>]`), the height zones (`[fit.zones]`). Each failing row names the side that must change: the box or the board. This check was added after a connector housing was found over a mounting hole, by eye, twice.
2. **Check every pair of solids on all cores:**
   `python -I <skill folder>/scripts/parcheck.py --project <project>/mech --min-gap 0.5 --allow <project>/mech/model/allow.toml`
   Intended contacts go into the allow file with a bound in mm3 (a stand under a board, a nut in its hole). Every gap under the minimum gets a written reason or a change.
   Expect `--min-gap 0.5` to fail every intended contact (parts on a board, the lid on its walls) and every gap by design (a cap in its hole): list them in `allow.toml`, by pattern where the names are numbered (`ref_main_*`). The solid names are those of the model's `build()`.
3. **Prove the assembly order.** For each part that is inserted along a path (a board tilted in, a cassette lifted out, the lid), run the sweep. The sweep tests against every solid of the model, so a part inserted early meets parts that are fitted later: let the model build only the parts present at each step (for example an environment variable read by `build()` that names the step) and run one sweep per step:
   `python -I <skill folder>/scripts/parcheck.py --project <project>/mech --sweep <solid> --direction 0,0,30 --steps 12`
   Write the order as `ASSEMBLY_ORDER` in the model. A bracket foot once ran under a neighbouring part, so the sub-assembly could not be lifted out; the sweep found it.
4. **Mated plugs and hands.** Give every connector that carries a cable or a plug its mated plug in `mech.toml`: `[fit.connectors.<ref>] plug = [width, height, length]`, the envelope from the maker's drawing (the overmould of a plug is larger than its body: an overmould, for example 12.5 x 6.5 mm, can run into a carrier part while every other row passes), centred on the mating face and reaching outward. `fit_check.py` tests it against every box solid, every board part and the board body (rows `FIT-PLUG-<ref>`). A connector marked `cable = true` or `plug_required = true` with no `plug` is "could not run: mated plug not modelled", never a pass. A plug height that no drawing gives is UNKNOWN: size the headroom with an assumed value, name it as a risk and ask the user to measure one plug. Also check the wrench round every panel nut and the finger room at every latch. Connectors on the top or bottom face are not covered by `fit_check.py` ("could not run"): check them with `parcheck.py` and by looking.
5. **Tolerance stack, by hand.** No script does this. For each fit that depends on a bend or a printed size, write the chain in `DECISIONS.md`: each size with its tolerance from the capability sheet (or the printer profile), the worst case and the root-sum-square, against the clearance. Where the stack eats the clearance, add a slot, a shim or more room. Never design a part that must be pulled into place.
6. **Stiffness of thin walls** (sheet metal, large flat lids): copy `templates/stiffness.example.toml` to `layout/stiffness.toml` and run `python -I <skill folder>/scripts/stiffness.py <project>/mech/layout/stiffness.toml --project <project>/mech`. Guide: under about 0.3 mm at 20 N feels solid. It suggests the thickness or the return flange that would pass. An estimate.

### Heat and air

7. **Fill the heat file** (`layout/heat.toml`): every part with watts and its maximum temperature, `theta_ca` from the data sheet where given, the fans, the vents with their open area, the box. Run
   `python -I <skill folder>/scripts/heat_air.py <project>/mech/layout/heat.toml --project <project>/mech`
   and copy the result into `HEAT_TABLE.md`. Rules: intake area at least 1.1 times the swept area of the fans that blow one way (aim 1.1 to 1.5; more is a note, not a failure); a part without `theta_ca` is "could not run", not a pass; an exhaust fan gives slow even flow, an intake fan gives a jet; no jet on a sensitive part; every hot part inside an air path. Never remove a local fan that works on a hypothesis: propose the change with the bench test that proves it.
8. **Vent patterns are complete matrices.** `box_toolkit.hex_field` moves the whole group by whole rows on a collision. A pattern that skipped two holes to clear a screw read as a defect and was redone.
9. **Suggest the fan and heat sink with sizes,** and hand the board side what it needs (a fan header, a speed signal). State every number as an estimate and attach `out/heat/bench_test_list.md`: closed box, run to a steady state, log points, thresholds.

> **PROVISIONAL (waits for evidence):** steady-state temperatures of a real assembled metal box against the estimate of `heat_air.py`, and the stiffness felt by hand against `stiffness.py`.

### Shielding and ground

10. **Openings and seams** (`references/design-rules/shielding-and-ground.md`): each opening against the wavelength of the highest frequency that matters, seams bonded metal to metal at a stated screw pitch, the largest window named as the main aperture. A panel connector soldered to a board and poking through an oversize hole leaks; prefer a panel-mounted jack on a short cable.
11. **Plan the ground bonds from what the finish allows.** Read the capability sheet: with an all-over coating and no masking, a bond is one of: a bare inner part that carries the contact; toothed washers that bite through the coat; a conductive finish from the catalogue; scraping, listed as hand-work with its minutes per box. Draw each bond in `GROUND_MAP.md`: point, parts joined, method, the test (continuity under 1 ohm at assembly). On one design several masked contact zones were drawn and checked, then the supplier coated all over: the whole plan became scraping by hand.
12. **Give every hole of a coated part its coating allowance** (phase 8 holds the value) and plan taps for coated threads.
13. **A radio inside a metal box gets a test plan** before metal is ordered: where the antenna is, what passes through, a cheap test (for example the printed box wrapped in foil), the pass number. It goes on the arrival test list.

> **PROVISIONAL (waits for evidence):** minutes of hand-work per box for scraped or washer bonds, and whether each planned bond reaches continuity under 1 ohm on real coated parts.

14. **Merge and look.** `python -I <skill folder>/scripts/check_all.py --project <project>/mech` writes `out/CHECKS.md`. Open the section views (`[[views.section]]`, then `views.py`) at every tight place and write what you saw. Hand fit findings that need a board change to the electronics side with the row and a picture.

## Questions for the user

- `<trade-off, with a picture>`: one 80 mm fan or two 50 mm?
  - Suggested: one 80 mm.
  - Why: quieter at the same air flow, and one part less.
- The finish coats all over. Bond the ground through toothed washers, or scrape `<n>` seats by hand (about `<m>` minutes per box)?
  - Suggested: toothed washers on bare inner parts.
  - Why: no hand-work that someone can forget; the scraping time grows with every unit.
- This fit needs the board to change (`<row>`, picture). Change the board, or the box?
  - Suggested: `<the cheaper side>`.
  - Why: `<its cost in days and money>`.

## Done when

- [ ] `fit_check.py`, the pair check and each sweep ran; every row is pass, or a named finding with its owner. Evidence: `out/CHECKS.md`, the headline counts.
- [ ] Every allowed contact has a bound and a reason; every small gap has a reason. Evidence: `model/allow.toml`, `DECISIONS.md`.
- [ ] The tolerance stack of every bend-dependent or print-dependent fit is written. Evidence: `DECISIONS.md`.
- [ ] `HEAT_TABLE.md` has every part, the air path picture, the fan suggestion and the words "estimate". Evidence: the file, `out/heat/bench_test_list.md`.
- [ ] `GROUND_MAP.md` has every bond with its method and test, and uses nothing the capability sheet does not offer. Evidence: the file against the sheet.
- [ ] The arrival test list exists (heat run, continuity, radio, stiffness by hand). Evidence: the list in `HEAT_TABLE.md` and `GROUND_MAP.md`.
- [ ] Section views were looked at. Evidence: the "seen" notes with picture paths.

## Outputs

- `out/CHECKS.md`; `out/heat/heat_table.md`, `bench_test_list.md`; `out/stiffness/`
- `mech/HEAT_TABLE.md`, `mech/GROUND_MAP.md`, the stack-up and the fit findings in `mech/DECISIONS.md`
- Hand-back to the electronics side: ground-bond holes, fan and heat-sink decisions, fit findings

## Lessons behind this phase

- A connector housing over a mounting hole was found by the user, by eye, twice -> step 1: the screw head and tool column of every hole.
- A bracket foot ran under a neighbouring part, so a sub-assembly could not be lifted out -> step 3: insertion sweeps.
- Bend tolerances moved the top of a wall by more than the lid's clearance -> step 5: the stack is written, and a slot or shim added.
- A local fan was removed on a hypothesis and the part overheated within minutes -> step 7.
- Masked ground zones were designed and checked, then the supplier coated all over -> step 11: bonds planned from what the finish allows.
- A board-mounted coax jack poking through an oversize panel hole leaked signal -> step 10.

The full cases are in `references/lessons.md`.
