# <device name>, rev <A>: incoming check

> **PROVISIONAL (waits for evidence):** this list is designed from the drawings; it has not yet been proven on a real arrival. After use, note which items found a fault and which were missing.

Written BEFORE the parcel arrives. The user measures and photographs; the agent records. Every result is "fits" or "does not" with the number. An item that was not measured stays empty; it is never "fits".
Tools: calliper, steel rule, square, multimeter with a continuity beeper, one screw of each thread size, the taps for coated threads.
Pass limits are the supplier's own tolerances (capability sheet of <date>): <linear +-x, bend +-y, angle +-z, holes +-w>.

## Parcel
- [ ] Count per part and per cable equals the order. Counted: <>
- [ ] Damage in transport: <none | what, photo>

## Metal parts (one block per part)
### <part number and name>, drawing `out/drawings/<part>.pdf`
| # | What | Where on the drawing | Drawing value | Tolerance | Measured | Result | Photo |
|---|---|---|---|---|---|---|---|
| 1 | Overall length | <GENERAL sheet> | <> | <> | <> | <> | |
| 2 | Overall width | | <> | <> | <> | <> | |
| 3 | Distance between the mounting faces | | <> | <> | <> | <> | |
| 4 | Hole <ID> from datum, X and Y | <panel sheet> | <> | <> | <> | <> | |
| 5 | Cut-out <ID> size AFTER the coat | | <> | <> | <> | <> | |
| 6 | Bend angles by the square | | <90> | <> | <> | <> | |
| 7 | Each nut: present, right side, a screw runs in by hand | <hardware table> | <n nuts> | | <> | <> | |
| 8 | Coat colour and gloss against the chart name | | <"chart name"> | | <> | <> | |
| 9 | Each ink against the chart; text sharp and complete | <ink sheet> | <chart names> | | <> | <> | |
| 10 | Print position from two edges | <silkscreen sheet> | <> | <> | <> | <> | |
| 11 | Surfaces: scratches, coat runs, bare spots | | | | <> | <> | |

Coat build-up measured in one hole (drawn against measured): <> (this number goes back to the skill, phase 16).

## Cables (one block per cable)
### <our id> (supplier line <n>), drawing `out/cables/drawings/<id>.pdf`
| # | What | Drawing value | Measured | Result | Photo |
|---|---|---|---|---|---|
| 1 | Length between the points the drawing defines | <L +-t> | <> | <> | |
| 2 | Label text and place | <> | <> | <> | |
| 3 | Connector part numbers (where marked); pin-1 mark | <> | <> | <> | |
| 4 | Cable or wire type and gauge (print on the jacket) | <> | <> | <> | |
| 5 | Angled plugs against the orientation picture | <> | <> | <> | |
| 6 | Gentle pull on every crimp | | <> | <> | |

Continuity, both directions, and no connection to a neighbour:
| P1 position | Colour | P2 position (drawing) | Beeps at | Result |
|---|---|---|---|---|
| <1> | <red> | <1> | <> | <> |
| <3> | EMPTY | | <nothing> | <> |

## Summary
| Item | Fits | Does not | Not measured |
|---|---|---|---|
| Metal parts | <> | <> | <> |
| Cables | <> | <> | <> |

Shortfalls to report to the supplier (the user decides): <none | which, drawing value against measured, photo>.
