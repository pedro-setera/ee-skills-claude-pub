# <device name>: print findings, print <1> of <date>

Printer and material: <from the profile>. Files printed: `out/print/<part>.stl`, checksums in the state file.
Each item: fits or does not, the number where one decides, a photo. Reported by the user; nothing is filled in for them.

## After-print list (in this order)
| # | Item | Picture of what to check | Result | Measured | Photo |
|---|---|---|---|---|---|
| 1 | Coupon: the hole that takes each screw; the tab clearance that fits | `out/print/coupon/coupon_legend.png` | <M3: +0.3 row> | <> | `<path>` |
| 2 | Each part off the bed: warp, layer faults, bridges | | <> | <> | |
| 3 | Each screw by hand into its post; each countersink flush | | <> | <> | |
| 4 | Each connector and panel part through its wall, with washer and nut | | <> | <> | |
| 5 | Each board on its stands, every hole in line | | <> | <> | |
| 6 | Lid on and off; soft frames or feet | | <> | <> | |
| 7 | Each cable (or a stand-in) along its route | | <> | <> | |
| 8 | Closed-box run, temperatures (if wanted) | | <> | <> | |

## Findings and what was changed
| # | Finding | Number | Cause | Change in the model (named value) | Reprint |
|---|---|---|---|---|---|
| <F1> | <M3 pilot hole too tight> | <drawn 2.5, printed 2.2> | <hole shrink> | <`HOLE_SHRINK` 0.3> | <shell only> |

## What fitted and what did not (the metal version reads this)
| Feature | Drawn | Fitted | Keep for metal |
|---|---|---|---|
| <board position> | <origin 30, 4, 6> | <yes> | <yes> |
| <panel jack hole> | <d> | <yes, 0.2 play> | <position yes; size per coating allowance> |

## Printer profile updates (with the user's OK of <date>)
- <hole_shrink_mm 0.3; tab clearance 0.2 per side>

## Open
- [ ] <Item not yet printed or not yet checked>
