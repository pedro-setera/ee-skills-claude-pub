# The hand-off with the electronics skill

This skill is the mechanical companion of `electronics-design-jlcpcb`. The two share two files in the board's `mech`
folder and nothing else is typed across. This page lists the hand-off in both directions, file by file and key by
key, the order of the two skills' phases, and what to do when there is no electronics skill.

Rule behind it: **no number is typed twice** (SKILL.md rule 3). Board numbers typed by hand into a box model drifted
over several layout rounds; a connector ended up inside a screw's tool space and the user found it on the screen.

## 1. Where the files live

```
<project>/hardware/<board>/mech/outline.json      written by THIS skill (the mechanical input of the board)
<project>/hardware/<board>/mech/interface.json    written by the electronics skill (generated from the board)
<project>/hardware/<board>/out/3d/<board>.step    written by the electronics skill (the same run)
<project>/mech/mech.toml                          [paths] interface = "../hardware/<board>/mech/interface.json"
```

With one board and no `hardware/` folder both files sit in `<project>/mech/`. With several boards there is one pair
per board and `mech.toml` lists each.

## 2. From this skill to the board: `outline.json`

Written in phase 2 (first version, for gate 0) and updated whenever the box changes what the board may be:
`python -I <skill folder>/scripts/interface_read.py --write-outline desc.toml --out <.../mech/outline.json>`.
The electronics skill reads it in its board-definition phase (its phase 8) and its layout helper and board checks
read the same file.

| Key | Content | Comes from |
|---|---|---|
| `outline.rect` or `outline.polygon` | The board's outline in the board's own frame | The layout study of phase 2 |
| `outline.corner_radius` | Corner radius | The same |
| `holes[]`: `name`, `x`, `y`, `d` | Each mounting hole: position and drill | The stands of the box |
| `holes[].keepout_d` | Diameter that must stay free of parts and copper: the largest of screw head, stand and tool, plus a margin | `[defaults] screw, margin, tool_d` and the `SCREWS` table of `box_toolkit.py`; give `keepout_d` directly when you know better |
| `holes[].plated`, `pad_d`, `net` | Which holes must be plated and on which net (ground bonds), which must stay unplated | The ground-bond map of phase 4 |
| `keepouts[]` with `kind = "band"`: `name`, `edge` (or `line`), `width`, `span` | A free band along an edge that sits in a rail or slot | The case profile's drawing (`suppliers/standard-cases.md`) |
| `keepouts[]` with `kind = "area"`: `name`, `rect` or `polygon`, `no`, `layers` | Any other area where parts or tracks may not be: under a lid screw block, behind a panel part | The model |

Handed over beside the file, as text for the electronics skill's board definition (this skill's layout study and
gate 0 summary hold them):

- height zones above and below the board (the tallest part allowed, per zone);
- for each connector that must reach a wall: which board edge, the exit direction, how far its mating face must
  stand from the edge, the wall thickness, and the thread budget of each part that passes a wall (wall + washer +
  nut + thread left);
- the cable list with lengths, connector part numbers and pin maps (`cables/cables.json`; a pin list as
  `connector,pin,net` for `cable_check.py --netlist` comes back from the electronics side);
- the ground-bond points: which holes must be plated and grounded, which must not;
- fan and heat-sink decisions: a fan header (2, 3 or 4 pins), a speed signal, a heat sink's footprint and height;
- the shipping plan: cables are the critical path, so the board order and the loose parts are planned around them.

## 3. From the board to this skill: `interface.json`

Written by the electronics skill's `scripts/interface_export.py --project <board folder>` (its phases 8, 9 and 10)
and read here only through `interface_read.py`. Never edit it by hand when a board file exists.

| Key | Content | Used here by |
|---|---|---|
| `board_file`, `board_file_sha256` | The board file and its checksum | `interface_read.py`: a changed board gives exit 1 "regenerate the interface" |
| `step_file`, `step_sha256` | The exported board STEP and its checksum | `fit_check.py`: refuses when the STEP differs |
| `units`, `frame` (`description`, `origin`, `y`, `offset`, `kicad_origin_in_this_frame`) | The frame of every number in the file | `interface_read.to_box` and `step_transform` |
| `outline_box`, `size`, `outline` | The outline box and polygon | stands, walls, the compare with `outline.json` |
| `thickness` | Board thickness | stand heights, slots |
| `holes[]`: `name`, `x`, `y`, `d`, `plated`, `net` | Every mounting hole as built | `box_toolkit.stands_from_interface`; the ground-bond map |
| `connectors[]`: `ref`, `value`, `side`, `x`, `y`, `rotation`, `box`, `body_box`, `body_z`, `height` | Every connector: pad box, the box of its whole 3D body with what hangs over the edge, its height | wall cut-outs; `fit_check.py` connector rows |
| `parts[]` | Further named parts (LEDs, switches) with the same keys | cut-outs for them |
| `tallest_part` (per side, and per named zone when the board defines zones) | The tallest part | height checks |
| `heights_measured` | False when the 3D bodies could not be measured | a height row "could not run" |
| `notes` | Warnings of the export | read them |

The board STEP's frame: x as in the board file, y negated, z = 0 at the board's bottom face. Place the board in the
box with `{"origin": [x, y, z], "rot_z": 0, "y_flip": "auto"}`.

From the electronics skill's documents (not from the file): the interconnect table (connector, pins, current per
pin, keying), the heat per part and its limit, the requirements page (environment, quantity, price position), the
makers' drawings of the mating plugs.

## 4. The checks that guard the hand-off

| Check | Command | Fails when |
|---|---|---|
| The interface belongs to the board on disk | `interface_read.py` | a checksum differs |
| The board met its mechanical input | `interface_read.py --compare <other interface.json>`; outline and holes of `interface.json` against `outline.json` | outline or a hole moved more than 0.011 mm |
| The board fits the box | `fit_check.py` | interference; a hole off its stand; a board part in a screw head's space or a tool column; a connector off its wall cut-out; a part above its height zone |
| Each failure names a side | the row's rule text | "box" or "board" must change |
| Nothing stale | `build.py`, `check_all.py` | any output older than `interface.json` |

A fit finding goes back to the electronics side as one line: the row, the number, and which side must change.
**After any board change: regenerate the interface, run the build, read the fit rows.** Views, renders and drawings
are made only from a board that fits.

## 5. The two skills side by side

| Step | Electronics skill | This skill | Passes |
|---|---|---|---|
| 1 | Requirements, architecture (its early phases) | 0, 1: requirements, process choice | The requirements page; heat per part; the interconnect table as it stands |
| 2 | | 2: layout study, first cable list; **gate 0** | `outline.json` v1, height zones, connector edges and exits |
| 3 | Schematic and its reviews | 3: the model with a placeholder board built from `outline.json` (the build marked provisional) | Connector choices back and forth: family, keying, panel-type parts |
| 4 | Board definition (its phase 8): reads `outline.json`, writes the outline-only board and `interface.json` | 3, 4: fit check on the outline-only board | First real `interface.json`; fit findings |
| 5 | Layout (its phase 9), exports `interface.json` and the STEP again | 4, 5: fit, heat, ground map; cables measured | Fit findings; the ground-bond holes; the cable and pin list |
| 6 | Designer checks and layout reviews (its phases 10, 11): its board reviewer judges the fit from this skill's fit result | 6, 7: print design, **gate 1**, the print | The fit result of the frozen board checksum |
| 7 | Its gate 2, board order | 8 to 10: metal version, documents, checks, **gate 2** | The shipping plan: boards that travel with the cables go to the parts shop's warehouse |
| 8 | Order watch, bring-up | 11 to 13: freeze, orders, watch | Order numbers in each state file |
| 9 | First power-up | 14, 15: arrival, fit, manual | Measured temperatures, continuity, what did not fit and which side changes |

The cable quote needs the board's connectors frozen: do not request it before the electronics side has passed its
schematic reviews and the connector positions are in `interface.json`.

## 6. Without the electronics skill

A bought board, a module, or a board designed elsewhere: fill the same `interface.json` by hand, with the same keys,
and write the source in it.

1. Get the maker's STEP by direct link (licence noted), or build the board from the maker's dimensioned drawing.
   `templates/model_template/make_example_board.py` shows a complete file with an invented board.
2. Fill `outline`, `thickness`, `holes`, `connectors` (with `body_box` and `height` measured on the STEP), `frame`.
   Put the page address or drawing number and the date into `notes`. Set `step_sha256` from the STEP on disk; set
   `board_file_sha256` to the checksum of the drawing or leave the board file unreachable (reported as "not
   verified", never as a pass).
3. A dimension the maker does not give is measured by the user from a sketch that marks the two points, and noted
   as "measured by the user, <date>".
4. Read the maker's assembly and pin-out page before stacking anything on the board (SKILL.md rule 9).
5. `outline.json` is then not handed to anyone: skip it, or keep it as the record of the keep-outs the box assumes.
6. The pin list for `cable_check.py --netlist` is typed once from the maker's pin-out page into `pins.csv`, with the
   page saved beside it, and checked by the cable-drawings reviewer against that page.

## 7. What is not exchanged

No machine-readable interconnect table comes from the electronics skill today: its interconnect table is a text
table in its design notes, and its interface export carries no pin nets. Until it does, the pin list is a CSV made
once from that table and reviewed (`review-briefs/cable-drawings.md`).
