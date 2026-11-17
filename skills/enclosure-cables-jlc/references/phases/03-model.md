# Phase 3: real parts and the model in code

Build the box as a parametric model in code around the makers' own 3D models of every bought part, with one build command that regenerates everything and refuses stale files.

## Inputs

- Gate 0 (the approved arrangement), `LAYOUT_STUDY.md`, `interface.json` and the board's STEP.
- `templates/model_template/` (`build_model.py`, `make_example_board.py`); `scripts/box_toolkit.py`, `scripts/vendor_parts.py`, `scripts/interface_read.py`, `scripts/build.py`, `scripts/views.py`, `scripts/render_blender.py`, `scripts/check_all.py`.
- `references/design-rules/` (the process chosen), `references/interface-electronics.md`, `references/tools.md`.

## Steps

1. **Verify the board interface.** `python -I <skill folder>/scripts/interface_read.py --project <project>/mech` checks the checksums of the board file and of its STEP. A changed board is refused until the electronics side regenerates the file. No board number is typed into the model: stands come from `box_toolkit.stands_from_interface`. Numbers typed by hand once drifted until a connector sat inside a screw's tool space.
2. **Get the maker's model of every bought part.** By direct link only, into `vendor3d/<part>/`, with `source_url` and `licence` in `vendor3d/vendor_parts.toml`; never a download click in a browser (give the user the link when only a click works). Read each file before use. Where no model is published, build the part from the datasheet drawing and write `block_model_reason`. Blocks and plain cylinders once hid a collision and made every render look wrong.
3. **Read the maker's assembly and pin-out page before stacking parts:** which side is up, what sits between what, which screws, which connector gender and pitch. A module was once modelled on the wrong side of its carrier; every render and several manual pages were redone.
4. **Use real fasteners.** A folder of library screws, nuts and standoffs (`[vendor] fasteners`; two files per fastener, full and simple). The skill ships no library; without one the fastener rows read "could not run" (`references/tools.md` says how to make one). No fake cylinders in the assembly.
5. **Write the model.** Copy `templates/model_template/` to `<project>/mech/model/`. Every dimension is a named value. One frame: origin at the outer front-left-bottom corner, x right, y back, z up, millimetres. `build()` returns every solid by name; `PLACEMENTS` says where each board sits; stands are named `stand_<hole>`. Optional: `ASSEMBLY_ORDER`, `COLOURS`, `EXPLODE`. Use the toolkit: `panel_cutouts` (a `"d"` cut-out is a D-hole with ONE flat on the +v side; `flat` is the distance from the round side to the flat, `flat_side` is `"+v"`, `"-v"` or `"both"` for a double-D), `hex_field` (a vent group moves as a whole by whole rows and never drops a hole), `thread_budget`, `print_pose`, `export_step`.
6. **Design so the shape can become sheet metal later,** when that is the path: flat walls, nothing that cannot be folded, the same hole positions. Give mating parts a small clearance, never a tight fit.
7. **Place the real parts and check the list:**
   `python -I <skill folder>/scripts/vendor_parts.py --project <project>/mech --export <project>/mech/out/step/assembly_real.step`
   Every bought part gets a row: real model, block with its reason, or fail.
8. **Set up the one build.** List the steps in `mech.toml` under `[[build.steps]]` (when the project has cables, put the route and compare steps FIRST from the start, with an empty routes file allowed, so that a rewritten `cables.json` never makes the other outputs stale) (model export, vendor parts, fit check, views, renders; later the drawings and cable drawings), each with the outputs it must produce. Then:
   `python -I <skill folder>/scripts/build.py --project <project>/mech`
   The guard fails when an output is missing, older than the run, or older than any input. Repeated "where are the new files?" rounds came from an old assembly file and two output folders; one build and one `out/` folder end that.
9. **Make the standard view set.** `python -I <skill folder>/scripts/views.py --project <project>/mech` writes front, back, top, bottom, left, right, perspective and exploded pictures into `out/views/` (emptied first). With Blender also `python -I <skill folder>/scripts/render_blender.py --project <project>/mech`. Without Blender say that the pictures are not photo-real.
10. **Look at every view** and write what you saw: each hole, connector, cut-out and vent group, zoomed; the colour of each part (brass is gold, not grey); nothing upside down. Then run `python -I <skill folder>/scripts/check_all.py --project <project>/mech` and tell the user the exact folder of every file.
11. **Ask only for measurements nobody else can take,** each with a sketch of what to measure. Wait for the numbers: measured numbers beat assumptions.

## Questions for the user

- Please measure `<dimension>` on `<part>` (sketch attached).
  - Suggested: a calliper reading to 0.1 mm, taken twice.
  - Why: the maker publishes no drawing of it, and a guess here moves a hole.
- The maker's model of `<part>` cannot be fetched by a direct link. Will you download it? (link given)
  - Suggested: yes, into `vendor3d/<part>/`.
  - Why: the real model shows collisions that a block hides.

## Done when

- [ ] The interface checksums verify. Evidence: `out/checks/interface_read.json`.
- [ ] Every bought part has a real model or a written reason; each model file has its source link and licence. Evidence: the rows of `vendor_parts.py`, `vendor3d/vendor_parts.toml`.
- [ ] The maker's assembly page of every stacked part was read. Evidence: one line per part in `DECISIONS.md` with the page title and the date.
- [ ] No board number is typed in the model. Evidence: a search of `model/` for the hole positions finds none.
- [ ] `build.py` ends with exit 0. Evidence: its output and the date.
- [ ] The view set is in one folder and each picture was looked at. Evidence: `out/views/`, the "seen" notes.
- [ ] The user was told where every file is. Evidence: the message.

## Outputs

- `mech/model/build_model.py`; `mech/vendor3d/` with `vendor_parts.toml`
- `out/step/` (parts and assembly), `out/views/`, `out/renders/`, `out/CHECKS.md`
- `mech.toml` with the build steps

## If something is missing

- No CadQuery: this phase cannot run. Offer the install again, or work as a reviewer of the user's own STEP files (the user's CAD tool makes the views, and they are looked at).
- No board STEP: `templates/model_template/make_example_board.py` shows the format. A hand-made `interface.json` from the maker's drawing is accepted with its source written in it; the fit check then reports its checksum row as "could not run".
- No Blender: the plain views of `views.py` are used everywhere, also in the manual.

## Lessons behind this phase

- Board numbers typed into the box model drifted; a connector ended up inside a screw's tool space -> step 1: the interface file with checksums, no typed numbers.
- Block models and plain cylinders hid a collision and made the renders look wrong -> step 2: the makers' own models.
- A module was stacked on the wrong side of its carrier because the maker's assembly page had not been read -> step 3.
- Fake cylinder screws in the assembly were rejected more than once -> step 4: real library fasteners.
- An old assembly file, old views and two output folders caused repeated "where are the new files?" rounds -> step 8: one build with a stale-file guard, one output folder.
- A vent pattern skipped holes to clear a screw and read as a defect -> step 5: `hex_field` moves the whole group.
- A measurement was assumed instead of asked; the user's own numbers then moved a fan mount -> step 11.

The full cases are in `references/lessons.md`.
