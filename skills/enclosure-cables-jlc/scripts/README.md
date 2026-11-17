# Scripts of the enclosure and cables skill

Every script is called by its full path with `python -I <skill folder>/scripts/<name>.py`. Run `--help`, or read the docstring at the top of the file: purpose, what it does, why it exists, usage, config keys, exit codes.

Common to all:

- **Project:** `--project <project>/mech` (the folder that holds `mech.toml`; default: searched upward from the current folder). **Output:** `--out` (default `<project>/mech/out`). Nothing is ever written into the skill folder; nothing is downloaded.
- **Exit codes:** 0 = every row passes; 1 = at least one row failed; 2 = could not run (a tool or an input is missing). A check that cannot run is never a pass. Each script prints one headline: `passed N, failed N, could not run N, not applicable N`.
- **Check rows:** each script writes `out/checks/<script>.json` (rows with id, section, check, value, rule, verdict `pass|fail|could_not_run|na`, and the sha256 of its inputs). `check_all.py` merges them into `out/CHECKS.md`; a row whose input changed afterwards is STALE and counts as failed.
- **CadQuery** may live in its own Python: set `[tools] cadquery_python` or the `CADQUERY_PYTHON` environment variable; the scripts that need it re-run themselves under it. Other libraries (numpy, shapely, ezdxf, matplotlib, scipy, Pillow, PyMuPDF, vtk) are imported only where used; a missing one gives exit 2.
- **All cores:** heavy work runs in a process pool (`MECH_WORKERS` sets the count) and gives the same numbers as a serial run.
- **Units and frame:** mm and degrees; origin at the outer front-left-bottom corner of the box, x right, y back, z up.

## By phase

### Phase 0, and every phase

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `env_check.py` | Finds Python, CadQuery, libraries, slicer, Blender, Chrome. Never installs. | `env_check.py --project <mech> [--require cadquery,numpy] [--json]` | the PC -> a table. Exit 1 when a required tool is missing (default: cadquery); a tool the user declined (`[tools] <tool> = "none"`) is shown as declined and never looked for |
| `build.py` | Runs the steps of `[[build.steps]]`, then the stale-file guard. | `build.py --project <mech> [--only step1,step2] [--check-only] [--provisional]` | `mech.toml` -> every listed output; fails on an output that is missing, older than the run or older than an input; when that input was rewritten by a step of this run it names the input and the step and says to move that step before the others; a step that writes both an input and an output is judged by its end time; after a failing step the later outputs read "not run", not STALE |
| `check_all.py` | Merges all check files into one list. | `check_all.py --project <mech> [--only script1,script2] [--json]` | `out/checks/*.json` -> `out/CHECKS.md`, `out/checks_merged.json`. Exit 2 when the only problems are rows that could not run; `waivers.toml` (`[[waiver]]` id or glob, reason, who, date, all required) prints accepted rows as WAIVED, counted apart; a STALE row is never waived |
| `mech_common.py` | Shared helpers (config loading, rows, checksums, worker count). Not run directly. | | |

### Phase 2: layout

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `layout_study.py` | Block layout study before any CAD: up to 3 variants compared. | `layout_study.py <mech>/layout/layout.toml --project <mech> [--variants A,B]` | layout TOML (`templates/layout.example.toml`) -> `out/layout/` pictures per variant, `comparison.md`, `comparison.png` |
| `heat_air.py` | Heat table, air estimates, fan suggestion, bench test list. Estimates only. | `heat_air.py <mech>/layout/heat.toml --project <mech>` | heat TOML (`templates/heat.example.toml`) -> `out/heat/heat_table.md`, `heat_table.json`, `bench_test_list.md`. One intake / swept ratio per direction group of fans (pass from 1.1); parallel fans add, an intake and an exhaust group are in series (lower flow); a part without `theta_ca` is "could not run" |
| `interface_read.py` | Reads the board interface file, verifies its checksums, writes `outline.json`. | `interface_read.py --project <mech>`; `interface_read.py --write-outline desc.toml --out <mech>/outline.json`; `--compare other.json` | `interface.json` + board file + STEP -> rows; a description TOML -> `outline.json`. Exit 1 = stale or different |

### Phases 3 and 4: model, fit, heat, shielding

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `box_toolkit.py` | CadQuery helpers imported by the project's model: `cyl`, `box`, `stadium`, `slot`, `rrect`, `csk_hole`, `stand`, `stands_from_interface`, `hex_field`, `vent_area_ratio`, `panel_cutouts`, `thread_budget`, `bend_sector`, `u_shell`, `flange`, `clinch_nut`, `print_pose`, `export_step`, `load_model`. | `box_toolkit.py --selftest` | imported with `sys.path.insert(0, os.environ["MECH_SCRIPTS"])`; `print_pose(part, face)` puts the NAMED face on the bed; `panel_cutouts` kind `d` = a D-hole with one flat (`flat_side` +v, -v or both); `export_step` writes AP203 by default |
| `vendor_parts.py` | Places the makers' STEP files; one row per bought part (real model, block with reason, or fail). | `vendor_parts.py --project <mech> [--export out/step/assembly_real.step] [--list]` | `vendor3d/vendor_parts.toml` + STEP files -> placed parts, rows, a BREP cache |
| `fit_check.py` | Fit of the board's STEP in the box: checksum, interference, holes on stands, screw head and tool column per hole, connectors against walls, height zones. | `fit_check.py --project <mech> [--board NAME] [--no-hash]` | model + `interface.json` + board STEP -> rows that name the side to change; `[fit.connectors.<ref>] plug = [w, h, length]` tests the mated plug against every solid and board part (rows FIT-PLUG); `cable = true` without `plug` is "could not run" |
| `parcheck.py` | All-core interference, gap and insertion-sweep checks on the model's solids. | `parcheck.py --project <mech> --min-gap 0.5 --allow allow.toml`; `parcheck.py --project <mech> --sweep <solid> --direction 0,0,30 --steps 12` | model -> rows |
| `stiffness.py` | Hand-stiffness estimate of plates, flanges, angle sections (guide 0.3 mm at 20 N). | `stiffness.py <mech>/layout/stiffness.toml --project <mech>` | items TOML (`templates/stiffness.example.toml`) -> `out/stiffness/` |
| `views.py` | Standard view set: six orthographic views with overall sizes, perspective, exploded, sections. | `views.py --project <mech> [--only front,top]` | model -> `out/views/*.png`, a `camera.json` beside each (the folder is emptied first); `--only` redraws the named views and keeps the others |
| `render_blender.py` | Photo renders with the finish table (chart colours). | `render_blender.py --project <mech> [--shots iso,top] [--samples N] [--job-only]` | model -> `out/renders/`. Exit 2 without Blender (use `views.py`); `--shots` takes `[[render.shot]]` names or a preset (front-left, front-right, rear-left, rear-right, front, back, top, left, right); an unknown name is exit 2; no picture made is never a pass; `[tools] blender = "none"` = could not run |

### Phase 5: cables

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `cable_route.py` | First measure: routes as straights and exact arcs, clearance, bend radius, crossings. | `cable_route.py --project <mech> [--only CAB-01] [--no-model] [--second]` | `cables/routes.toml` + model -> `route.measure_a_mm` in `cables.json`, `out/cables/route_<id>.png`; `cables.json` is rewritten only when its content changes |
| `cable_second_measure.py` | Second measure by another method; comparison; the design length. | `cable_second_measure.py --project <mech>`; then `cable_second_measure.py --project <mech> --compare --apply` | `cables/second_measure.toml` -> `measure_b_mm`; compare -> `length_mm` and rows CMP, DESIGN, LENGTH, TOL, REACH, SBEND, FRESH; the design length is raised to the reach floor (shortest path at the minimum radius + the design tolerance) when that is longer; REACH and SBEND are judged at the design tolerance (`[tolerance] design_mm`, else the widest standard value) and also show the result at the tolerance asked; `cables.json` is written only when its content changes |
| `cable_check.py` | Checks `cables.json` alone and against a netlist. | `cable_check.py --project <mech> [--netlist pins.csv]` | `cables.json` + capability sheet (+ CSV `connector,pin,net`) -> rows ENDS, AWG, CAV, LEN, TOL, LABEL, SPEC, NONDEF, ROWS, ANGLE, EXTRA, TEXT, NET, KEY; CODES fails a blank or placeholder (TBD, UNKNOWN) part number or supplier code; ANGLE wants a coded `exit` and the picture; TEXT flags board, PCB, module in a name or label |
| `cable_common.py` | Shared cable helpers. Not run directly. | | |

### Phase 6: printing

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `print_check.py` | Rule audit in print pose; slicer run on copies of the user's presets; test coupon. | `print_check.py --project <mech>`; `... --slice`; `... --coupon --screws M2.5,M3`; `print_check.py part.step --pose bottom --profile <PRINTER_PROFILE.toml>` | `[print] parts` or `out/print/*.stl` + the printer profile -> rows; `out/print/coupon/` (`coupon.stl`, `coupon.step`, `coupon_legend.png`, `coupon.json`). It makes no slicer preview pictures; overhang rows are grouped per class above 5 regions; the roof of a round hole up to `bridge_max_mm` is a bridge; `--slice` works under `out/print/slice/` and is "could not run" when the slicer is declined, missing, or a preset is not named |

### Phases 8 to 11: metal, documents, checks, freeze

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `sheet_features.py` | Reads a sheet-metal STEP: panels, datums, holes, cut-outs, patterns, hardware, bends, flat pattern. | `sheet_features.py --project <mech> --all` (or `--step part.step --name N`) | `out/step/<part>.step` -> `out/drawings/<part>.features.json` |
| `silk_dxf.py` | Print file: one layer per chart ink in the ink's true colour; text as outlines. | `silk_dxf.py --project <mech> --art <mech>/silk/<part>_art.toml [--outline open\|corners\|none]` | artwork TOML + capability sheet -> `out/silk/<part>_silk.dxf`, `<part>_silk.json`. Refuses an ink that is not on the chart; the DXF header names no tool and no user; the outline and bend lines go on two reference layers `*_NOT_PRINTED` in colours of their own (`[silk] outline_colour` 3 green, `bend_colour` 2 yellow dashed), BYLAYER, open lines and arcs; index 7 / 0 / white, an ink's colour or a name without the suffix is refused (row REF) |
| `drawing_book.py` | Fully dimensioned PDF per part and the manifest of every printed number. | `drawing_book.py --project <mech> --all` | features JSON -> `out/drawings/<part>.pdf`, `pages/*.png`, `drawing_manifest.json` |
| `drawing_vs_step.py` | Rebuilds every feature from the printed numbers and matches it to the STEP. | `drawing_vs_step.py --project <mech> --all [--tol 0.05]` | manifest + STEP + PDF -> rows; a hole row prints the printed and the STEP-measured diameter |
| `sheet_dfm.py` | Measures the supplier's sheet-metal and print rules on the exported STEP and DXF. | `sheet_dfm.py --project <mech> --all` | STEP + DXF + capability sheet -> rows `DFM-...`, `S..`. Flanges are measured at their lowest point along the bend; hole and hardware distances to a bend read to the tangent line by default and print both readings; a rule value missing from the capability sheet gives "could not run" |
| `ink_sheet.py` | Ink sheet (faces 1:1 in ink colours on the coat colour, ink table, contrast); factory view (the DXF on a dark background). | `ink_sheet.py --project <mech> --dxf out/silk/<part>_silk.dxf --coat "<chart name>"`; `ink_sheet.py --project <mech> --factory-view --dxf ...` | DXF -> `out/silk/<part>_ink_sheet.pdf` / `.png`, `<part>_factory_view.png`; the ink sheet lists the reference layers as "NOT printed"; the factory view draws them dashed in their own colour and fails a reference layer on index 7 / white, closed, in an ink's colour or not named `*_NOT_PRINTED` |
| `catalogue_scan.py` | Flags words in remarks, PDFs, DXF layer names and text files that are not catalogue values. | `catalogue_scan.py --sheet <mech>/suppliers/<id>.capability.toml <folder or file> [...] [--waivers catalogue_waivers.toml]` | upload folders + capability sheet -> rows. Exit 1 = a hit. "layer colour = ink" (the model remark's phrase) is accepted |
| `step_scrub.py` | Cleans or checks STEP headers (author, organisation, paths, host). | `step_scrub.py <folder> --in-place --company "<text>"`; `step_scrub.py <folder> --check` | STEP files -> cleaned files (default: copies in `out/step_clean/`) |
| `privacy_scan.py` | Scans files that leave the PC for personal data. | `privacy_scan.py --project <mech>` (scans `out/upload`); `privacy_scan.py <file or folder> --deny deny.txt` | files -> rows. Exit 1 = a hit |
| `freeze.py` | Freezes a set of files for a review or an order: refuses a stale build or check row, copies the profile's files, writes the checksums, prints the lines for the state file. | `freeze.py --project <mech> --name print-r1 --profile review\|visual\|order [--include GLOB ...]` | current build and checks -> `reviews/frozen/<name>/` (laid out as the mech folder) and `reviews/frozen/<name>.MANIFEST.sha256`. Exit 1 = stale or missing output or stale check; 2 = the set exists (never overwritten) or could not run |
| `cable_drawings.py` | Cable drawings in the maker's format (P1/P2, wiring table, cavity tables, "X, NOT Y" notes). | `cable_drawings.py --project <mech> [--only CAB-01]` | `cables.json` -> `out/cables/drawings/*.pdf` / `.png`, `cables_all.pdf`, `out/cables/pictures/`; the label is drawn at `label_position`; placeholder text fails row PLACEHOLDER (the drawing is still written); `note_internal` is never drawn; a single coax has no wiring picture |
| `cable_fieldsheet.py` | The value of every field of the cable quote form; the read-back check. | `cable_fieldsheet.py --project <mech>`; `cable_fieldsheet.py --project <mech> --readback pasted.txt` | `cables.json` + capability sheet -> `out/cables/FIELD_SHEET_cables.md`; pasted form text -> rows |
| `supplier_calendar.py` | Deadlines in a supplier's working hours. | `supplier_calendar.py now`; `submit-window`; `deadline --answer --at <ISO>`; `deadline --pay`; `plan --steps plan.toml` (all with `--project <mech>`, optional `--sheet <capability.toml>`, `--local-tz`, `--json`) | `[supplier_hours]`, else `[hours]` of `--sheet` (the first line says which) -> times in UTC and in the PC's local clock of that date; `submit-window` says "send now" when the send-by time has passed. Exit 0 or 2 |

### Phase 13: production drawings

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `production_drawing_check.py` | The cable maker's production drawing against `cables.json`, field by field. | `production_drawing_check.py --project <mech> --template CAB-01 --pdf theirs.pdf`; fill the file; `production_drawing_check.py --project <mech> [--sent YYYY-MM-DD]` | `orders/production_drawings/supplier_drawing_<id>.toml` -> verdict CONFIRM / REVISE / NOT DECIDED and a ready note in `out/cables/production/`. An empty value = not read = could not run |

### Phase 15: manual

| Script | Purpose | Usual command | Inputs -> outputs |
|---|---|---|---|
| `annotate.py` | Call-outs, arrows and the red warning frame on a picture, anchored in model millimetres. | `annotate.py --project <mech> <mech>/manual/callouts/step01.toml` | spec TOML + picture + camera file -> `out/manual/annotated/<name>.png` |
| `manual_build.py` | The assembly manual from an ordered steps file. | `manual_build.py <mech>/manual/steps.toml --project <mech> --pdf --png [--strict]` | steps TOML (`templates/steps.example.toml`) -> `out/manual/assembly-manual.html`, `.pdf`, `pages/page-NN.png` |

## Order of use

- **Freezing:** `freeze.py` before every review (phases 5, 7, 10, 13, 14) and for the revision (phase 11); it refuses what is stale.

- **Case, phase 9:** `sheet_features` -> `silk_dxf` (when printed) -> `drawing_book` -> `drawing_vs_step` -> `sheet_dfm` -> `ink_sheet` and `ink_sheet --factory-view` -> `catalogue_scan` -> (phase 11) `step_scrub`, `privacy_scan`.
- **Cables:** `cable_route` -> `cable_second_measure` -> `cable_second_measure --compare --apply` -> `cable_drawings` -> `cable_check` (it wants the pictures of the drawings to exist) -> `cable_fieldsheet` -> after typing the form `cable_fieldsheet --readback` -> after payment `production_drawing_check`.

## Known limits (say them to the user when they matter)

- `fit_check.py`: flat walls of an axis-aligned box; the connector face rows on the top or bottom wall are "could not run" (the mated plug is tested on all six walls; it is an envelope box from the maker's drawing); no tolerance stack (done by hand in phase 4).
- `print_check.py`: the audit is approximate (sampled sections); the slicer run was proven only against a stand-in slicer, so verify its command line on the first real run; no preview pictures.
- `vendor_parts.py`: no fastener library is shipped; without one the fastener rows are "could not run".
- `heat_air.py`, `stiffness.py`: estimates (heat within 30 to 50 %); each row says "prove on the bench". A part without `theta_ca` is "could not run".
- `sheet_features.py` / `sheet_dfm.py`: bends other than 90 degrees and hems are not tested; relief size and outline steps near a bend are not measured; hardware values in the toolkit are typical and must be replaced from the supplier's page.
- `drawing_book.py`: prints `[project] name` in the page header: keep it a neutral code. No 3D view of the part: put a render next to the PDF.
- `cable_drawings.py`: at most three ends per cable; connectors are schematic boxes.
- `cable_route.py` and the compare: a change of the model or of a cable's diameter after the measure is not detected by the rows: re-run the route step in the build.
- There is no script for the order watch baseline or for packing the upload archives (`freeze.py` makes the frozen sets and their checksums): these are done by hand as the phase files say.

## mech.toml: every key

The complete annotated example is `templates/mech.example.toml`. Sections and the scripts that read them:

| Section | Keys | Read by |
|---|---|---|
| `[project]` | `name` (neutral code), `company`, `rev` | all drawing, scrub and cable scripts |
| `[tools]` | `cadquery_python`, `blender`, `slicer`, `slicer_kind`, `chrome` | `env_check`, every CadQuery script, `print_check`, `render_blender`, `manual_build` |
| `[printer]` | `profile` (path outside the skill) | `print_check` |
| `[paths]` | `model`, `interface`, `out`, `cables`, `vendor` | all |
| `[build]`, `[[build.steps]]` | `inputs`; per step `name`, `cmd`, `outputs`, `timeout`, `ok_codes` | `build` |
| `[fit]`, `[fit.zones]`, `[fit.connectors.<ref>]` | `board`, `interface`, `stand_prefix`, `hole_tol`, `screw_head_d`, `screw_head_h`, `driver_d`, `column_top`, `wall`, `skip`; zones `max`, `rect`; connectors `wall`, `flush`, `face_offset`, `gap_min`, `gap_max` | `fit_check` |
| `[parcheck]` | `min_gap`, `allow`, `skip` | `parcheck` |
| `[vendor]` | `bought`, `cache`, `fasteners` | `vendor_parts` |
| `[print]` | `parts`, `allow_support`, `step_verdict` | `print_check` |
| `[views]`, `[views.colours]`, `[views.explode]`, `[[views.section]]` | `long_px`, `margin_px`, `tolerance`, `angle`, `fov_deg`, `azimuth_deg`, `elevation_deg`, `explode_gap`, `dims`, `titles`, `hide`, `skip`; section `name`, `axis`, `at`, `keep` | `views` |
| `[render]`, `[render.finish.<part>]`, `[[render.shot]]` | `samples`, `resolution`, `background`, `floor`, `device`, `fov_deg`, `margin`, `transparent`, `threads`, `stl_tolerance`; finish `colour`, `roughness`, `metallic`; shot `name`, `preset` or `azimuth`, `elevation`, `distance`, `target` | `render_blender` |
| `[sheet]`, `[sheet.margins]`, `[[sheet.hardware]]` | `thickness`, `supplier`, `material`, `k_factor`, `pattern_min`, `bottom_view`, `panel_names`, `allowed_bend_angles`, `hole_to_bend_from`, `parts` (`name`, `step`, `silk_dxf`, `finish`, `qty`, `title`); margins `flange`, `flange_second`, `hole_to_bend`, `hardware_edge`, `hardware_bend`, `u_inside`, `hole_to_hole`, `silk`; hardware `code`, `thread`, `hole_d`, `body_d`, `edge_min`, `bend_min` | `sheet_features`, `drawing_book`, `drawing_vs_step`, `sheet_dfm`, `silk_dxf`, `ink_sheet` |
| `[drawing]` | `tolerances`, `notes`, `page`, `check_tol` | `drawing_book`, `drawing_vs_step` |
| `[silk]` | `coat`, `notes`, `no_print`, `outline_layer`, `bend_layer`, `outline_colour`, `bend_colour`, `non_print_suffix`, `text_gap`, `min_contrast`, `allow_ink_overlap` | `silk_dxf`, `ink_sheet`, `sheet_dfm` |
| `[catalogue]` | `sheet`, `scan`, `deny_file`, `waivers` | `catalogue_scan` |
| `[privacy]` | `scan`, `deny_file`, `allow`, `exclude` | `privacy_scan` |
| `[scrub]` | `allow` | `step_scrub` |
| `[supplier_hours]` | `utc_offset`, `windows`, `weekdays`, `holidays`, `answer_margin_min`, `pay_margin_min`, `submit_days` | `supplier_calendar` |
| `[cables]`, `[cables.types.<name>]` | `file`, `routes`, `second`, `supplier`, `sheet`, `min_straight_mm`, `arrive_tol_mm`, `arrive_tol_deg`, `clearance_mm`, `cable_gap_mm`, `compare_max_diff_mm`, `allowance_crimped_mm`, `allowance_trimmed_mm`, `tol_mm`, `label_max_chars`, `show_signals`, `deny`, `skip_solids`, `po_number`; type `od_mm`, `min_bend_r`, `min_bend_x_od`, `stiff` | all cable scripts |

Files with their own format (not in `mech.toml`): the layout, heat and stiffness TOMLs, `vendor3d/vendor_parts.toml`, the artwork file of `silk_dxf.py`, `cables/routes.toml`, `cables/second_measure.toml`, the call-out specs, `manual/steps.toml`, the `--write-outline` description, the `plan.toml` of `supplier_calendar.py`, and the printer profile (`templates/PRINTER_PROFILE.toml`). Each format is in its script's docstring, and an example is in `templates/` where one exists.

Capability sheet keys read by the scripts: `[meta] supplier, read_date, sources`; `[finishes] powder, anodize, inks, other`; `[materials] sheet, thickness`; `[limits] max_length, hole_d_min, hole_d_min_t_factor, hole_to_hole, u_inside_min, tiny_face, tiny_edge, standard_tolerance` (sheet metal) and `more_requirements_chars, files_max, file_max_mb, file_types, revise_chars, revise_pictures` (cables); `[sheet_rules."<thickness>"] outer_bend_r, min_flange, min_flange_second, hole_to_bend_round, hole_to_bend_square`; `[silk_rules] min_text_height, min_line, min_gap, edge_clearance`; `[ink_rgb]`, `[coat_rgb]`; `[tolerance] standard_mm, design_mm`; `[hours] utc_offset, windows, weekdays` (`supplier_calendar.py --sheet`); `[[stock_defaults]] item, default, applies`; `[forms.<harness|rf|ethernet|other>] name, note, fields`.

## cables.json: the schema

One file is the single source for routes, drawings, form values and the production-drawing check. Example: `templates/cables.example.json`.

```
{"project": "", "rev": "A",
 "cable_types": {"<name>": {"od_mm": 1.32, "min_bend_r": 6.0, "min_bend_x_od": 4.0, "stiff": true}},
 "cables": [{
   "id": "CAB-01", "name": "", "type": "harness|rf|ethernet|other", "qty": 5, "rev": "A",
   "label": "text printed on the cable", "label_position": "15 mm from P1",
   "wire_standard": "UL1007", "twisted": false, "colour": "jacket colour (rf, ethernet)",
   "length_mm": 65, "tol_mm": 3, "length_def": "wire exit of P1 to wire exit of P2",
   "ends": [{
     "id": "P1", "kind": "housing|tinned|plug|jack",
     "part": {"mpn": "", "supplier_code": "", "positions": 5, "rows": 1,
              "numbering": "words, e.g. pin 2 is NEXT TO pin 1, other row", "numbering_order": "zigzag|rows",
              "keyed": true, "description": "", "short": "text under a plug in the schematic"},
     "terminal": {"mpn": "", "supplier_code": "", "awg_min": 22, "awg_max": 28},
     "empty": [3], "tin_mm": 4, "trim_at_assembly": true,
     "angled": true, "exit": "left|right|up|down", "latch": "up|down", "orientation": "words",
     "picture": "file, relative to the cables folder",
     "mates": "J2", "pin_map": {"1": "A1"}, "branch_length_mm": 120}],
   "wires": [{"from": "P1.1", "to": "P2.3", "colour": "red", "awg": 24, "signal": "+5V"}],
   "cable_spec": "rf and ethernet: the exact cable in words",
   "non_defaults": [{"item": "cable", "want": "X", "not": "Y"}],
   "accept_defaults": ["pinout"], "notes": ["extra drawing note"],
   "bom_extra": [{"role": "", "description": "", "supplier_code": "", "qty": 1}],
   "extras": [],
   "route": {"cable_type": "wire_bundle", "od_mm": 3.4, "min_bend_r": null, "allowance_mm": null,
             "note": "written cause of a difference between the two measures"}}]}
```

Notes on the fields:

- `cable_types`: built in are `wire_bundle` (radius 5), `network` (4 x outer diameter), `flat` (5 x outer diameter); a coax has no built-in value: give its data sheet radius.
- `ends`: two, or three for a branch (the third end carries `branch_length_mm`). A tinned end is addressed as `P2.<lead number>` in `wires`. `trim_at_assembly` defaults to true for tinned ends and selects the larger allowance. `mates` names the board connector for the netlist check; `pin_map` translates positions when the board numbers them differently.
- `wires`: no per-wire length. One length per cable.
- `non_defaults`: `item` ties the line to a `[[stock_defaults]] item` of the capability sheet; every stock default must be either overridden here or listed in `accept_defaults`.
- `extras` must stay empty: loose extras are bought in the parts order.
- `route.min_bend_r` (data sheet value) wins over the cable type; `route.allowance_mm` wins over the end-type rule.
- Written by the scripts into `route`, never by hand: `measure_a_mm`, `measure_b_mm`, `wires` (per-wire measures), `smallest_r_a`, `a_source`, `second`, `design_length_mm`.

## The printer profile

`PRINTER_PROFILE.toml` lives in the user's home (`~/.claude/enclosure-cables/`), never in the skill. Keys read by `print_check.py`: `[printer] name, bed, nozzle, line_width, layer_height`; `[rules] max_overhang_deg, bridge_max_mm, min_wall_lines, hole_shrink_mm (default 0.3, a first guess until the coupon measured it), section_step, min_overhang_area, step_small_mm, min_flat_area`; `[slicer] machine, process, filament` (Bambu, Orca) or `config` (Prusa); `[coupon] thickness, screws`. The template adds sections for people (materials, clearances that fitted, the soft-material path) that no script reads.
