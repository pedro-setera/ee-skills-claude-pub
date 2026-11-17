# <board name>: silkscreen identification block (proposal)

The agent proposes this text. The user accepts it or changes it. Nothing here is invented by the agent for legal use: the company name, safety text and any certification mark are the user's to give.

Rules for all silk text: at least 1.0 mm high; line: 0.15 mm was the published minimum as read in 2026-11; use 0.16 mm or more for new work and re-read the live minimum; no text on pads, vias or holes, one reference next to its own part, readable from the board's main orientation (or from two, stated).

## Proposed text
| Item | Proposed text | Why | User's answer |
|---|---|---|---|
| Company name | <as the user gives it, no personal name> | <ownership, support> | <accept / change> |
| Device model | <name and code> | <identifies the board in a box of boards> | |
| Revision | <Rev A> | <matches PROJECT_STATE and the order> | |
| Date code | <2026-11 or YYWW> | <traces the batch> | |
| Order-number mark | <the supplier's mark, placed where it asks> | <keeps the supplier from printing a number on a real mark> | |
| Connector names | <J1 PWR, J2 SENSOR> | <so the cable goes on the right header> | |
| Pin names | <1 V, 2 SDA, 3 SCL, 4 G> | <wrong pin order burns parts> | |
| Polarity | <+ at C1, band at D1, dot at pin 1 of U1> | <assembly and inspection> | |
| LED meaning | <D2 green: power; D3 red: fault> | <bring-up reading> | |
| Safety notes | <only if true for this device: max input voltage, hot surface> | <user's call, wording from the user> | |

Reference designators: shown for <every part | important parts only>. Parts without a label (too small or no room) are named on the assembly drawing: <list>. This needs a user waiver if any are on the list.

## Placement notes
| Item | Where | Check |
|---|---|---|
| Info block | <open area on the top, lower left, 20 x 8 mm free of parts and vias> | <image crop> |
| Order-number mark | <bottom side, flat area, clear of text> | <image crop> |
| Pin legends | <beside each connector, outside the plug footprint> | <crop against schematic> |
| Polarity and pin-1 marks | <visible with the part fitted, which in practice means outside the body outline> | <3D view> |
| Test point names | <next to the point, or listed on the assembly drawing> | <crop> |

## Looks to check in the image
- Each designator is beside its own part and touches nothing.
- Group texts do not read as one word.
- No text on a via or hole.
- Pin 1 marks match the schematic symbols.
- The info block is neat and fully inside the board.

## Result
Accepted by the user on <date>: "<quote>". Frozen into the layout as `<silk block file>`.
