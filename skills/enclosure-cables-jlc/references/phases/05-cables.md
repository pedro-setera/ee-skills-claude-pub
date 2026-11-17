# Phase 5: cables in the model

Fix the final cable list, put every cable into one data file, measure each route twice in the 3D model, and set one length per cable that works at the design tolerance (the widest tolerance the maker may draw). Nothing is drawn or quoted before the user's choices are in.

## Inputs

- `CABLE_LIST.md` v1, the model with real parts (or measured poses when there is no model), the board's pin-out and netlist.
- The cable supplier's capability sheet (`suppliers/lcsc-cable.capability.toml`, dated) and `references/suppliers/lcsc-cable.md`.
- `scripts/cable_route.py`, `scripts/cable_second_measure.py`, `scripts/cable_check.py`; `templates/cables.example.json`, `templates/routes.example.toml`, `templates/second_measure.example.toml`.
- `references/design-rules/cables.md`, `references/review-briefs/route-second-measure.md`.

## Steps

1. **Run the full interconnect check.** Walk every board connector and every panel part: power, signals, radio, antenna feed, fans, ground. Each must end in a cable of the list or be marked "not cabled, because". A forgotten cable was found after a quote was submitted; a submitted quote cannot be edited, so every cable was entered again.
2. **Ask the user's choices once, before any drawing** (next section): ends, routes, cable types, colours. On one project the choices came after the first drawings and cost a two-hour redraw.
3. **Choose connectors and wires with live stock.** Each housing and terminal by maker part number and supplier code, read on the day. Check each crimp terminal's wire range against the wire gauge and write `awg_min` / `awg_max` into the data: a wire thicker than the terminal's range was later drawn into its crimp. Check the gender and pitch against the board's own documents. Reuse what the user owns.
4. **Write `cables/cables.json`** (copy `templates/cables.example.json`; the schema is in `scripts/README.md`). One entry per cable: ends P1, P2 (P3 for a branch), the wires position to position with colour and gauge, empty cavities listed, the numbering of two-row housings in words, the label text, every item that differs from the supplier's stock default as `{"item", "want", "not"}`. Describe a non-default cable in full words (construction, jacket or none, outer diameter), never by a bare type name: the maker's stock cable of the same type name was a thicker, jacketed variant. This file is the single source for routes, drawings, form values and the later production-drawing check.
5. **Measure each route (first measure).** Write `cables/routes.toml`: for each cable the wire exit of each connector as a point and the direction in which the wire leaves it, then the moves (straights and arcs at the real bend radius). Route under the boards and with no loops unless the user chose otherwise. Before the first route: every connector that carries a cable has its mated plug in the model (phase 4 step 4; an assumed size is named as a risk), because the clearance rows see only solids that exist; a per-route `min_straight` shorter than the default needs a written reason from the plug's drawing. Never put the lid or a wall in `skip_solids`: one cable passed through the lid while it was skipped. The cable's own connector solids go in the route's `allow` (the solid names of the model's `build()`, also listed in `out/views/views_manifest.json`). Compare pin 1 at both ends in the box frame: where it is mirrored (pin 1 at the left of one header and at the right of the other), the wires cross, so measure one route per wire and say so on the drawing. Then:
   `python -I <skill folder>/scripts/cable_route.py --project <project>/mech`
   Rows per route: arrives at the end pose, length, smallest bend radius, the straight exit at each connector (3 mm by default), clearance to every solid, no crossing of another cable. It writes `measure_a_mm` into `cables.json` and a top and side picture per route in `out/cables/`. Look at each picture.
6. **Second measure by a fresh agent.** Start one reviewer with `references/review-briefs/route-second-measure.md`, the model and the cable list, and NOT `routes.toml` or the first numbers. It writes `cables/second_measure.toml` (poses and radius, its own reading of the model) and runs
   `python -I <skill folder>/scripts/cable_second_measure.py --project <project>/mech`
   which uses a different method and writes `measure_b_mm`. Two measurements of a short coax once differed by several millimetres: one had assumed the connector body length instead of reading the real part's drawing.
7. **Compare and set the length:**
   `python -I <skill folder>/scripts/cable_second_measure.py --project <project>/mech --compare --apply`
   The longer measure is used. A difference above `compare_max_diff_mm` (2 mm) fails until its cause is written in the cable's `route.note`. Rows also check that the cable still reaches at length minus the design tolerance, and that a stiff cable (coax, network) keeps its bend radius in an S at minus, nominal and plus the design tolerance.
8. **Apply the length rule.** One length per harness: the longest route plus its allowance, for all wires (the short wires bow). The maker threads the whole bundle and then crimps; a per-wire length table triggered a question. Allowance: +2 mm for a cable crimped at both ends, +10 mm where an end is tinned and trimmed at assembly (`allowance_crimped_mm`, `allowance_trimmed_mm`). Where the second measure gives the reach, the length is raised to the shortest path at the minimum radius plus the design tolerance when that is longer (the DESIGN row says "raised from ... to ..."). Design every cable to work at the design tolerance D of the capability sheet (`[tolerance] design_mm`, else the widest standard value: as read 2026-11 +-5 mm; the drawing asks the narrowest standard, +-3; re-read the live page). A tighter value asked on a drawing was drawn at the standard without a word, and even a +-3 request can come back +-5. The compare raises a design length that would not reach at L - D and says so. A short stiff cable that cannot pass at L + D needs a design change (more offset, a trimmed end, a more flexible cable), not a tighter number.

> **PROVISIONAL (waits for evidence):** the +2 mm (crimped) and +10 mm (trimmed) allowances and the reach rule, against real delivered cables: each cable's real length against the order, its slack and bend on its route.

9. **Check the data:**
   `python -I <skill folder>/scripts/cable_check.py --project <project>/mech --netlist <pins.csv>`
   Rows: ends, part numbers and supplier codes present (CODES: no blank, TBD or UNKNOWN), gauge against crimp range, cavities, length, tolerance, label, cable spec, non-defaults against the supplier's stock defaults, row numbering, angled plugs (orientation text, coded exit, picture file), no loose extras, no forbidden words (also "board", "PCB", "module" in a cable's name or label); with the netlist (CSV `connector,pin,net` from the electronics side) each wire against the nets and the keying. Loose extras do not belong in a cable order: "two loose sleeves" came back fitted on the wires.
10. **Hand back to the electronics side:** the cable and pin list with lengths and connector part numbers (`references/interface-electronics.md`).

## Questions for the user

Ask these together, once, with the route pictures.

- Each cable end: connector or tinned wire? (table per cable)
  - Suggested: a keyed connector wherever the board has one.
  - Why: no soldering at assembly and no reversed lead.
- The routes (pictures): under the boards, no loops. Agree, or change one?
  - Suggested: as drawn.
  - Why: a clean inside, and the lengths are exact for these routes.
- Cable types and colours (table: wire standard and gauge, coax type, network cable type, jacket and wire colours)?
  - Suggested: `<the list, with the maker's stock default named where you accept it>`.
  - Why: anything not named becomes the maker's default; anything changed after the quote means a new quote.
- May any end be trimmed at assembly?
  - Suggested: yes for tinned ends.
  - Why: it lets the cable be ordered 10 mm long and removes the tolerance risk.

## Done when

- [ ] The interconnect check lists every connector with its cable or its reason. Evidence: the table in `CABLE_LIST.md`.
- [ ] The user's choices are recorded with their words, before any drawing. Evidence: the state file, dated.
- [ ] Every route arrives, keeps its radius and its clearance. Evidence: the `cable_route` rows, the route pictures looked at.
- [ ] The second measure was written without the first numbers. Evidence: the reviewer's report (model and effort stated), `cables/second_measure.toml`.
- [ ] Both measures agree, or each difference has a written cause. Evidence: the compare rows, `route.note`.
- [ ] One length per cable, working at the design tolerance (+-5 as read 2026-11). Evidence: the LENGTH, TOL, REACH and SBEND rows.
- [ ] `cable_check.py` ends with no failed row; rows that could not run are named. Evidence: the headline.

## Outputs

- `mech/cables/cables.json` (final lengths), `routes.toml`, `second_measure.toml`
- `out/cables/route_<id>.png`, check rows
- `mech/CABLE_LIST.md` final; the pin and cable list for the electronics side

## If something is missing

- No 3D model (cables only): the user measures each pose (wire exit point and direction) with a sketch per connector; `cable_route.py --no-model` gives the geometry rows and the clearance rows read "could not run". Say so, and add trim allowance where an end allows it.
- No netlist: `cable_check.py` runs without `--netlist`; the pin maps are then checked by reading the board's pin-out page, by a fresh agent in phase 10.

## Lessons behind this phase

- A cable was forgotten and the user's choices came after the first drawings: every cable was entered again and redrawn -> steps 1 and 2.
- Two measurements of one short coax differed by several millimetres (an assumed connector length) -> steps 6 and 7: a second measure made blind, the longer one used, each difference explained.
- A per-wire length table drew a question; the maker crimps a whole bundle at one length -> step 8.
- Tolerances tighter than the maker's standard were silently drawn at the standard -> step 8: design for the standard.
- A wire gauge outside its crimp's range reached a production drawing -> step 3 and the gauge row of step 9.
- Loose extras ordered with a cable came back fitted on its wires -> step 9.

The full cases are in `references/lessons.md`.
