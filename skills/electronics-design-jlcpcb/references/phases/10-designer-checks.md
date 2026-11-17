# Phase 10: designer's checks

Prove with the designer's own check suite, run on the saved and exported files, and by looking at every image, that the board is worth an independent review.

## Inputs

- The saved, filled board of phase 9, its rule file, the gate 1 schematic and netlist, the BOM.
- `LAYOUT_RULES_LEDGER.md`, `BOARD_DEFINITION.md`, `SILK_ID_BLOCK.md`, `mech/interface.json`.
- `templates/CHECKS.md`, `references/pcb-rules/dfm-dft.md`, `references/pcb-rules/silkscreen.md`, `references/jlcpcb/capabilities.md`.
- The scripts named in the table below, and `scripts/check_all.py`, which runs them all. Each reads the project's `board.toml`; run `python -I scripts/<name>.py --help` first.
- `references/lessons.md`, section "Phase 10: designer's checks".

## Steps

**A board the user brought** (`references/existing-designs.md` section 4): run steps 1 to 5 and 8 on the copy, record every failure as an intake finding, and fix nothing; steps 6 and 7 run only on a go that names the changes.

1. **Make a trial export.** Run `scripts/fab_package.py` on the saved board into `out/jlc/` (and, if there is a panel, `scripts/panel.py` into `out/panel/` and `scripts/fab_package.py` on the panel board into `out/panel/jlc/`, as in phase 12 step 4). The manufacturing checks need the files that would be uploaded. This package is a trial; phase 12 makes the final one. Run `scripts/interface_export.py` as well, and the live stock check of phase 3, step 13, on the same day: the suite reads only the saved answers.
2. **Run the whole suite** with `python -I scripts/check_all.py --project <board folder>`. It runs every script below and writes the one-page result `out/CHECKS.md`. Every check reads the saved board or the exported files, never design parameters or an earlier result. What each check cannot see is listed in `references/tools.md` section 4: carry every "cannot" that matters for this board into `out/CHECKS.md` as UNKNOWN. Four of them change what you do first: `zone_check.py` judges the fill as saved (fill and save first); `neck_check.py` is UNKNOWN without a named power path; `testpoint_check.py` is UNKNOWN without `required` and `fixture`; `ratings_check.py` passes a typing error in the table. A row that does not apply to this board is written NOT APPLICABLE with its reason; it is neither PASS nor UNKNOWN.

   | Check | Script | Passes when |
   |---|---|---|
   | Schematic unchanged, ERC, netlist intent | `scripts/schematic/export.py`, `scripts/netlist_check.py` | netlist checksum equals gate 1; ERC 0; intent PASS, and its mutation self-test fails as it must |
   | Netlist of today against the one of gate 1 | `scripts/netlist_compare.py` | identical to `[netlist_compare] reference`: references, values, footprints, pins, nets |
   | DRC, all severities, schematic parity | `scripts/drc_run.py` | 0 errors, 0 unconnected, parity 0; every warning explained in writing. "Parity 0" counts only when a schematic was given (without one the script says CANNOT RUN). It does not judge the saved zone fill: `scripts/zone_check.py` and `scripts/edge_check.py` do |
   | Footprints | `scripts/fp_audit.py` | no courtyard smaller than its pads or body |
   | Silkscreen | `scripts/silk_check.py` | text height and line; clearances measured on bounding boxes; each label nearest its own part; each name of a group text beside its own part; unlabelled parts listed |
   | Copper to edge | `scripts/edge_check.py` | measured on the exported Gerbers, board and panel, at or above the rule |
   | Currents and necks | `scripts/neck_check.py` | no neck under its current; the drop at each load within its budget |
   | Ground | `scripts/zone_check.py`, the cut test or net-tie check of phase 9 | no island without vias; the planned stitching count is there; the single point holds |
   | Pins and ratings | `scripts/ratings_check.py` | run again on the final netlist: every pin as the datasheet names it, inside its recommended range at the worst case; no pin without a rating |
   | Pin functions | `scripts/pin_function_check.py` | run again on the final netlist: every pin of every programmable part PASS, or accepted with its written reason; not applicable only when every chip's block says `programmable = false` |
   | Line impedance | `scripts/impedance_check.py` | every controlled line (USB high speed, RF, any line with a target in `board.toml`) is within its tolerance, computed from the widths, gaps and layers that are on the board; the manufacturer's calculator record agrees; a listed name that is not on the board is a finding |
   | Return paths of fast and sensitive nets | `scripts/return_path_check.py` | no listed net runs over a gap in its ground layer; every layer change has a ground via beside it; the overlay images were opened |
   | Heat | the heat table of `DESIGN_NOTE.md` | every part above about 0.1 W has its row with the copper and vias measured on the board; the hottest part keeps the margin of THM-04 under its limit, with the air at the part (the hottest surroundings plus the rise in the case), or is UNKNOWN with a bench test |
   | 3D bodies | `scripts/body_check.py` | every body inside its courtyard; no body, mated plug or cable exit in any hole's keep-out column; nothing in the free bands along slot or rail edges on either side (bodies, courtyards, solder joints, exposed copper), its edge bands checked and both sides looked at |
   | Test points | `scripts/testpoint_check.py` | every point of the schematic's list is on the board; pad size, spacing, distance to tall parts and side as `references/pcb-rules/dfm-dft.md` DFM-96 and DFM-98; a ground point near each group; the table `out/testpoints.md` is written and both overview images were opened. Run it after `scripts/body_check.py`, whose result gives the heights of the neighbours |
   | Placement rotations | `scripts/jlc_rotations.py` | a derivation row for every placed part; the re-derive test agrees. Bottom-side parts not yet seen in JLCPCB's preview are UNKNOWN with their candidate angles until phase 11 step 14b |
   | Stock | `scripts/jlc_parts.py bom-check` | every line in stock for the boards plus spares, dated today: the row of `check_all.py` fails when an answer it uses is older than `[bom] max_age_hours` (24 h by default) or has no date; refresh with `scripts/jlc_parts.py --project <board folder> --live bom-check` (the user's yes) |
   | Panel | `scripts/panel.py`, `scripts/drc_run.py` | panel DRC clean; the panel's placement file equals the board's, shifted by each copy's offset |
   | Privacy | `scripts/privacy_scan.py` | no user name, home path or host name in any design or output file |
   | Interface and freshness | `scripts/interface_export.py`, `scripts/fab_package.py` | checksums equal the saved board and the exported 3D model; no output older than its sources |
   | Simulations | `scripts/sim/ngs.py` | re-run when a value changed since gate 1 or the layout added a long power path; limits as written before |

3. **Hold these rules for the suite.**
   - A check that cannot run is FAIL, with the reason. If `scripts/body_check.py` has no 3D kernel, it says FAIL "cannot run" and the visual and mechanical reviews carry the point with zoomed renders of every hole; it is never "skipped".
   - Each report names the checksum of the file it read. All checksums equal the saved board's.
   - Pass limits are the ones written in the rules. A failing check changes the board, not the limit.
4. **Prove every custom check with a planted defect.** For each check or DRC rule written or changed for this project: run it on a copy that holds the defect (it must fail) and on the good board (it must pass). Examples: narrow a pour to a neck; push a label onto a pad; pull copper to the edge; drop a via into a pad; merge two nets. A check without this proof supports no claim.
5. **Generate the images** with `scripts/review_images.py` into `out/review/` (contact sheet `out/review/index.md`, designator list `out/review/designators.csv`), plus the assembly drawing, the panel render and the section views. Open each one and write one line on what you saw, with the crop path.

   | Image | Look for |
   |---|---|
   | Renders, top and bottom | bodies over holes, pads or edges; missing or shifted models; wrong colours; polarity marks visible |
   | Render at an angle | heights, mated plugs, cable exits, parts under an overhang |
   | Tile of each hole, top and angled | nothing in the keep-out; a free path for the screw head and the tool |
   | Tile of each connector | pin 1; the legend against the schematic, pin by pin; room for the mated plug and its latch |
   | Tile of each antenna, crystal and sensitive input | the keep-out clear on every layer; the matching network at the feed; no switching copper, clock or fast line under or beside it; parts in their zones (`references/pcb-rules/emc.md`) |
   | Silkscreen plot, each side, and each label cluster | every label beside its own part; two labels reading as one word; text on pads or vias; fields that should be hidden; the information block in open space |
   | Copper plot, each layer | the plane in one piece; a clean band along the edge; necks; fingers and islands; switch-node size; acute angles, stubs and loops left by a router |
   | Assembly drawing | every reference readable inside its own part, the origin corner included; the drawing fits its page |
   | Panel render | rails on the right edges; bridges away from parts; no hand-fit part reaching into the next board; fiducials; no tooling holes of our own (DFM-20) |
   | Section views | the plug fully mated; flange and wall as drawn in phase 8 |
   | Simulation plots, if re-run | a converged run before any number is used |

6. **Fix what the checks and the images show.** After the last change, run the whole suite again and render again: a fix in one place moves things in another.
7. **Make the documents agree with the board.** Search every document for each value that changed (design note, ledger, board definition, ordering and bring-up drafts). Copy tables from the script reports instead of retyping them. Take the revision text from one place. Regenerate pin legends from the current netlist.
7b. **Do the final cross-check, one chain per requirement,** and record the chains in `out/CHECKS.md` (phase 11 copies them into the gate 2 summary). Take each `REQ-nn` and follow it through every document to the board: the requirement, the block and calculation in the design note, the datasheet page behind the number, the simulation and its limit, the value on the schematic, the part in the BOM, the copper or the dimension on the board, the mechanical drawing. Every link must say the same number. A chain that breaks (a limit that changed in one place only, a value on the sheet that the calculation never saw, a height the case drawing does not know) is a finding, fixed before the reviews.
8. **Complete `out/CHECKS.md`** (written by `scripts/check_all.py` in the shape of `templates/CHECKS.md`; write by hand only from the heading "Planted-defect proof for each new custom check" downward: the script keeps that part and writes everything above it anew): one page; per check the script, the result and the evidence file; the planted-defect table; the images looked at; the root cause of any defect that got through an earlier check. List every UNKNOWN (for example the temperature inside the enclosure) with the bench test that will settle it, and the parts without a label. You settle no UNKNOWN yourself: the list goes into the gate 2 summary, and the user's approval of the gate is the acceptance of that list.

## Questions for the user

None.

## Checks before leaving this phase

- [ ] `out/CHECKS.md` has a row for every check of step 2 with its result and evidence file; no blank row, none "skipped". Evidence: the file.
- [ ] Every report names the same board checksum, equal to the file on disk now. Evidence: the checksum line of each report.
- [ ] Every custom check or rule has a planted-defect result and a good-board result. Evidence: the planted-defect table of `out/CHECKS.md`.
- [ ] The edge check measured the exported Gerbers. Evidence: `out/edge_check.md` naming the Gerber files and the minimum distance.
- [ ] Every hole and every connector has its tile, and every image has a "what I saw" line. Evidence: the images table with crop paths.
- [ ] The EMC measures of `references/pcb-rules/emc.md` hold on the saved board: every antenna, crystal and sensitive input has its tile and passes. Evidence: the EMC row of `out/CHECKS.md` and its crops.
- [ ] The stock report is dated today. Evidence: `out/BOM_STOCK_CHECK.md`.
- [ ] Every changed value was searched in all documents. Evidence: the list of searched values with 0 stale hits.
- [ ] No output is older than its sources. Evidence: the freshness result of `scripts/fab_package.py`.
- [ ] Every UNKNOWN has a planned bench test and is on the list for the gate 2 summary. Evidence: the UNKNOWN list in `out/CHECKS.md`.

## Outputs

- `out/CHECKS.md`
- `out/`: one Markdown report and one JSON result per script
- `out/review/` and `out/review/crops/`: the image set, its contact sheet `out/review/index.md`, `out/review/designators.csv` and the crops
- `out/jlc/` and `out/panel/`: the trial package (not for ordering)
- `PROJECT_STATE.md`: next action phase 11

## Lessons behind this phase

- DRC reported 0 edge violations while the saved board and the Gerbers had copper to the outline: the fill had been saved before the edge rule existed -> the edge check measures the exported Gerbers.
- A script reported a part clear while the render showed a connector over a screw -> step 5 has a tile for every hole, and the 3D check tests bodies.
- The first single-point ground test reported FAIL on every board, good or bad: the checker was wrong -> step 4 gives every check a good and a bad control.
- The claim "DRC covers the widths of the pours" was written down and was false -> a claim names its check and that check's planted-defect proof.
- The references of several unlabelled parts were piled at the origin of the assembly drawing while all checks were clean -> step 5 looks at the drawing, the origin corner included.
- A panel render showed a hand-fitted connector reaching into the next board -> step 5 looks at the panel.
- The designer measured silkscreen clearance on the strokes and passed it; the reviewer measured the text boxes and found text almost touching via copper -> the silkscreen check uses bounding boxes.
- Reviewers found stale tables and legends in three rounds running -> step 7 searches the documents after every change.

The full cases are in `references/lessons.md`.
