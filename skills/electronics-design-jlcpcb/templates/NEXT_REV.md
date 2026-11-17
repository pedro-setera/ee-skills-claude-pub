# <board name>: next revision list

One row per item for the next revision. Fill it from findings that were not fixed, bring-up results, outside review points and your own notes.

Priority: P1 = fix before any further order. P2 = fix when the layout is next opened. P3 = nice to have.

## List
| Item | Why | Priority | What to do on the current boards meanwhile | Source |
|---|---|---|---|---|
| <Series resistor in the sensor data line> | <ringing seen at 100 MHz on the scope> | <P1> | <fit a 33 ohm 0603 by hand on every board> | <bring-up BT-04> |
| <Test point for the 3.3 V rail has no silk label> | <no room on rev A> | <P3> | <use the assembly drawing> | <waiver W-1> |
| <Mounting hole too close to the connector> | <plug hits the screw head> | <P2> | <use a pan-head screw> | <review L3-MJ2> |

Source column: bring-up test (`BT-<nn>`), finding ID (`<prefix>-<severity><number>`), waiver, user request.

## Outside review points, triaged
When someone outside the project sends a review, check each point against the design and the ordered files.
| Point | Verdict | Evidence | Action |
|---|---|---|---|
| <1: no reverse protection on the input> | <safe as ordered> | <SIM-04 in `sim/RESULTS.md`, diode D1 in the netlist> | <none> |
| <2: no pull-up on a reset pin> | <safe with a bring-up step> | <datasheet p. 11, internal 50 k> | <measure at BT-02> |
| <3: connector too small for the current> | <next revision> | <0.8 A vs 1 A rating, little margin> | <note> |
| <4: missing footprint note> | <fix at the assembler> | <placement preview> | <message drafted> |

Verdict values: safe as ordered, safe with a bring-up step, fix at the assembler, next revision, not applicable.

## Lessons for the next design
- <What to do differently in the schematic, the parts, the layout or the order.>
- <Proposed for the skill's lessons only with the user's OK, generic wording.>

## Carry-over checklist for rev <B>
- [ ] Every item above decided: do or drop, with a reason.
- [ ] New requirements from the user collected in REQUIREMENTS.
- [ ] Parts that went out of stock replaced, with reference check redone.
- [ ] A new PROJECT_STATE with revision <B> started; the old one archived.
