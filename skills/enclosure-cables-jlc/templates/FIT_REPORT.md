# <device name>, rev <A>: fit report

> **PROVISIONAL (waits for evidence):** the order and the tests of this report are designed, not yet proven on a first real assembly.

**Conclusion:** <usable as it is | usable with the hand-work below | not usable: why>. **The one action:** <>.
Assembled on <date> by <the user>, in the model's order (`ASSEMBLY_ORDER`). Every row is the user's report: fits or does not, the number, a photo.

## Assembly fit
| # | Step | Result | Number | Photo | Cause if it does not fit | Side to change |
|---|---|---|---|---|---|---|
| 1 | Every board on its stands; every screw by hand | <> | <> | | | <box | board> |
| 2 | Every panel part through its wall, washer and nut; thread left for the plug | <> | <mm of thread> | | | |
| 3 | Every mating plug from outside | <> | | | | |
| 4 | Each cable on its route: reaches, slack, smallest bend, not pinched | <> | <slack mm> | | | <cable | box> |
| 5 | Lid on and off; gaps; screw alignment | <> | <gap mm> | | | |
| 6 | Planned hand-work (scraping, washers, taps) | <> | <minutes> | | | |

## Cables on their routes
| Cable | Ordered length | Real length | Slack on the route | Bend | Result |
|---|---|---|---|---|---|
| <id> | <> | <> | <> | <> | <> |

## Tests
| Test | Pass limit | Estimated | Measured | Result |
|---|---|---|---|---|
| Polarity of every power cable, before plugging in | <right pin, right voltage> | | <> | <> |
| Ground continuity at each bond of `GROUND_MAP.md` | <under 1 ohm> | | <> | <> |
| Heat run, lid closed, to a steady state: <point> | <limit> | <from HEAT_TABLE.md> | <> | <> |
| Radio through the closed box (if any) | <pass number of the test plan> | | <> | <> |
| Stiffness by hand: <wall> | <feels solid> | <mm at 20 N> | <> | <> |

## Times
- Assembly: <minutes>. Hand-work on the metal: <minutes per box>. Planned: <>.

## What fitted and what did not
| Feature | As designed | Result | Goes to |
|---|---|---|---|
| <panel holes after the coat> | <d> | <tight on the part> | <NEXT_REV line 1> |

## Manual pages to change
- <page or step, what was different in reality>
