# <board name>: production release record, revision <A>

**Status: <DRAFT | RELEASED by the user on <date>: "<the user's words>">.** Release state: **<PROTOTYPE ONLY | PROTOTYPE ONLY, limited use: <who, where, how many> | PRODUCTION APPROVED>**, from the one release table (`references/reviews.md` section 8). Only the user releases; the agent prepares this page and never states PRODUCTION APPROVED itself. The user's signature authorizes manufacture; it is not technical validation and does not stand in for a missing row of section 2.

Write it in plain words (`references/working-rules.md` section 1). One page.

## 1. What is released
The files below are the ones that were built and tested. A build from other files is a new revision and is tested again.
| Item | File | sha256 |
|---|---|---|
| Schematic (PDF and KiCad project) | <`out/<board>-schematic.pdf`, `kicad/`> | <value> |
| Board file | <`kicad/<board>.kicad_pcb`> | <value> |
| Upload folder (Gerbers, drill, BOM, placement file) | <`out/jlc/<zip>`> | <value> |
| Panel, if any | <`out/panel/`> | <value> |
| Off-board parts list (cables, housings, screws) | <file> | <value> |
| Firmware, if any: the release items of `FIRMWARE_HANDOVER.md` section 12 | <file, version> | <value> |
| Assembly drawing and 3D model | <files> | <value> |

Revision on the board's silkscreen: <A, date code>. Order it was built in: <the entry of `ORDER_LOG.md`, no account data here>.

## 2. What was proven on the real boards
- Boards built: <5>. Boards tested: <5>. Passed: <5>.
- Requirements table: <all REQ-nn passed or shown by design: `FIRST_POWER_UP.md` section 7b>.
- Bench tests: <BT-01 to BT-12 passed; file>.
- The other rows of the release table: each passed with its evidence, "not applicable" with its fact, or missing with its owner. One missing row keeps the state at PROTOTYPE ONLY or a stated limited use.

| Row | Result | Evidence, or owner of what is missing |
|---|---|---|
| Destructive or hazardous fault tests | <passed on <n> sacrificial boards / not applicable: no protection must clear a fault that can hurt a person or start a fire / missing> | <report file / the lab or engineer the user named> |
| Emissions, radio, product safety | <passed / not applicable: own use, not placed on a market / missing for sale> | <report file / the user's test house> |
| Firmware frozen | <complete / not applicable: no programmable part / missing> | <`FIRMWARE_HANDOVER.md` section 12 / the firmware owner> |

## 3. Deviations and waivers the user accepted
A safety-critical item is never listed here as accepted: it is a missing row of section 2.
| ID | What | Why it is acceptable | The user's words |
|---|---|---|---|
| <W-1> | <6 parts without a label> | <no room; assembly drawing shows them> | "<quote>" |

## 4. Changes for the next build
| Item | Change | Why | Needs a new review? |
|---|---|---|---|
| <R7> | <10 k to 12 k> | <BT-05: set-point 2 % low> | <yes: scoped fix round> |
<Or: "none: the next build uses exactly the files of section 1".> A change of the schematic, a part or the board makes a new revision letter, passes its fix round and reviews, and gets its own record.

## 5. Parts: what may be substituted
| Line | Released part | Allowed second source (an equivalent from an established maker, compared table by table) | Not allowed |
|---|---|---|---|
| <U2> | <maker part number> | <none compared yet> | <any part without a full datasheet> |
Stock was last checked on <date>. Before every new order the stock check and the supplier-rules review run again (`references/phases/12-production-files.md`).

## 6. How each later board is tested
<The short production test: what is measured on every board, with its pass values, taken from the bring-up plan: supply current at rest, each rail, the function check. Who does it: <the manufacturer's functional test, if ordered | the user on arrival>.>

## 7. Where everything is kept
<The project folder and its revision tag or archive name; who holds a second copy.> Private data (names, addresses, order numbers) stays in the project files, never in this skill.
