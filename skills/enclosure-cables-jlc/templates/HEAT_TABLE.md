# <device name>: heat table and air path

Every number here is an ESTIMATE (good within 30 to 50 %) from `scripts/heat_air.py` (`out/heat/heat_table.md`). The bench test at the end proves it or corrects it.

## Parts
| Part | Watts | Limit (deg C) | Heat sink | Resistance to air (K/W; source or "assumed") | Estimated (deg C) | Margin | Verdict |
|---|---|---|---|---|---|---|---|
| <processor> | <3.0> | <85> | <yes, 14 x 14 x 6> | <6, data sheet> | <58> | <27> | <pass> |

A part whose resistance is "assumed" is not judged: its row is "could not run" until the data sheet figure is in.

Total: <8 W>. Room temperature assumed: <25 deg C>.

## Air path
Picture: `<out/views/section or layout picture>`
- Intake: <left wall, hex field, open area mm2>
- Exhaust: <rear fan 80 mm, blowing out>
- Intake / fan swept area: <1.3> (rule 1.1 or more, aim 1.1 to 1.5; one value per group of fans that blow the same way)
- In the fan's stream: <nothing sensitive>
- Hot parts outside the path: <none>
- Air temperature rise: <+3 K with the fan | +14 K without>

## Fan and heat-sink decisions
| Decision | Choice | Why | Needed from the board |
|---|---|---|---|
| <case fan> | <80 mm, slow, exhaust> | <quiet, even flow> | <3-pin header, speed signal> |

## Vent groups
| Group | Wall | Pattern | Holes | Open area (mm2) | Complete matrix |
|---|---|---|---|---|---|
| <intake> | <left> | <hex, d 4.0, pitch 5.5> | <65> | <817> | <yes: the whole group moved one row to clear a screw> |

## Bench test (arrival list)
From `out/heat/bench_test_list.md`. Closed box, normal load, run until every point changes less than 0.5 K in 10 minutes.
| Point | Estimated | Limit | Measured | Verdict |
|---|---|---|---|---|
| <processor case> | <58> | <85> | <> | <> |
| <air at the exhaust> | <28> | <> | <> | <> |
