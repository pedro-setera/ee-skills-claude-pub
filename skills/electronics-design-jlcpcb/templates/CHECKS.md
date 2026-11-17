# <board name>: designer's checks, one page

Result of the whole check suite on the saved and exported files, kept as `out/CHECKS.md`. Run by `python -I scripts/check_all.py --project <board folder>` on <date>. Board sha256 <value>. Netlist sha256 <value>.

**Overall: <ALL PASS | NOT PASSED | INCOMPLETE>: <n> passed, <n> failed, <n> could not run, <n> not applicable.** Anything that failed or could not run keeps the suite from passing: could not run is never a pass. Where a row could not run, one line says what it needs (for example the board folder, given with `--project`). A check on design parameters instead of the exported file does not count for manufacturing rows.

| Check | Script | Result | Evidence file |
|---|---|---|---|
| <ERC> | <`schematic/export.py`> | <0 errors> | <`out/erc_report.json`> |
| <DRC, all severities, with schematic parity> | <`drc_run.py`> | <0 errors, 0 warnings, 0 unconnected> | <`out/drc_summary.txt`> |
| <Netlist against intent> | <`netlist_check.py`> | <PASS> | <`out/connectivity_report.md`> |
| <Netlist of today against the one of gate 1 (`[netlist_compare] reference`)> | <`netlist_compare.py`> | <IDENTICAL> | <`out/netlist_compare.md`> |
| <BOM stock, all lines, <n> boards plus spares> | <`jlc_parts.py bom-check`> | <PASS, <date>> | <`out/BOM_STOCK_CHECK.md`> |
| <BOM line audit: shared lines, LCSC and maker part numbers> | <`jlc_parts.py line-audit`> | <PASS> | <`out/bom_line_audit.md`> |
| <Footprints against maker drawings> | <`fp_audit.py` plus review> | <PASS> | <`out/fp_audit.md`> |
| <Rotations derived and re-derived> | <`jlc_rotations.py`> | <PASS> | <`out/jlc/rotations.md`> |
| <Silkscreen size and clearances> | <`silk_check.py`> | <PASS> | <`out/silk_check.md`> |
| <Copper to edge on exported Gerbers> | <`edge_check.py`> | <min <0.4> mm, PASS> | <`out/edge_check.md`> |
| <Current worksheet and copper necks> | <`neck_check.py`> | <PASS> | <`out/current_worksheet.md`> |
| <Ground islands and stitching> | <`zone_check.py`> | <PASS> | <`out/zone_check.md`> |
| <Pins and ratings against the hand-typed datasheet tables; control inputs that can float> | <`ratings_check.py`> | <PASS, 0 pins without a rating, 0 inputs that can float> | <`out/ratings_check.md`> |
| <Pin functions of every programmable part: the use table against the datasheet table> | <`pin_function_check.py`> | <PASS, every pin PASS or accepted with its reason; or NOT APPLICABLE: no programmable part> | <`out/pin_function_check.md`> |
| <Impedance of the controlled lines, from the board's own widths and layers> | <`impedance_check.py`> | <USB pair 88 ohm against 90 +-15 %; or "no controlled line"> | <`out/impedance_check.md`> |
| <Return paths of the fast and sensitive nets (`[fast_nets]`)> | <`return_path_check.py`> | <PASS: <n> nets, 0 mm over a gap; or "no such net on this board"> | <`out/return_path.md`, overlay images> |
| <Test points: size, spacing, clearances, coverage of the required nets, fixture> | <`testpoint_check.py`> | <PASS, <n> points> | <`out/testpoint_check.md`, `out/testpoints.md`, overview images> |
| <Heat table recomputed with the board's copper and vias> | <design note, section 4> | <hottest part <x> C with <y> C air at the part, against <z> C less the margin of THM-04> | <`DESIGN_NOTE.md`> |
| <3D bodies and keep-outs> | <`body_check.py`> | <PASS or FAIL: cannot run> | <`out/body_check.md`> |
| <Panel: DRC, placement file equals the board's shifted per copy> | <`panel.py`, `drc_run.py`> | <PASS> | <`out/panel/`> |
| <Interface file and 3D model against the saved board> | <`interface_export.py`> | <PASS, checksums equal> | <`mech/interface.json`, `out/3d/`> |
| <Simulation suite, re-run after the layout added the 5 V path> | <`sim/ngs.py`> | <PASS, <n> tests, limits as written before> | <`sim/RESULTS.md`> |
| <EMC: zones, antenna keep-out and matching network, shield-can land and vias, nothing noisy under or beside a sensitive part (`references/pcb-rules/emc.md`)> | <tiles, looked at> | <PASS> | <`out/review/crops/`> |
| <Privacy scan of every output> | <`privacy_scan.py`> | <PASS> | <`out/privacy_scan.md`> |
| <Production files fresh against the board> | <`fab_package.py`> | <PASS> | <`out/jlc/manifest.json`> |

## Planted-defect proof for each new custom check
| Check | Defect planted in a copy | Check failed as expected? |
|---|---|---|
| <`silk_check.py`> | <text moved onto a pad> | <yes> |

## Images the designer looked at
| Image | Path | What I saw and fixed |
|---|---|---|
| <Top 3D, bottom 3D, angled> | <`out/review/`> | <label R4 touched a via, moved> |
| <Silkscreen plot, copper plots> | <`out/review/`> | <ok> |
| <Zoom tiles: every hole, connector, label cluster> | <`out/review/`, named in `out/review/index.md`> | <ok> |

## Root cause of any defect that got through earlier
<One line per defect: what, why the earlier check missed it, which check now catches it.>

## UNKNOWN, each with its bench test
Every item that no check could prove: from the checks above, and every "cannot" of `references/tools.md` section 4 that matters for this board.
| Item | Why it is UNKNOWN | Bench test |
|---|---|---|
| <temperature of U2 at full load> | <no heights or air temperature measured yet> | <BT-05> |

## Requirements, chain by chain
One row per `REQ-nn` (phase 10, step 7b): every link says the same number, or the row is a finding.
| ID | Requirement | Design note | Datasheet | Simulation | Schematic value | BOM part | On the board | Chain |
|---|---|---|---|---|---|---|---|---|
| <REQ-01> | <temperature within +/-0.5 C> | <block 3, error budget> | <sensor p. 4> | <SIM-06> | <R7 10 k 0.1 %> | <line 12> | <sensor 22 mm from U2, `out/body_check.md`> | <holds> |
