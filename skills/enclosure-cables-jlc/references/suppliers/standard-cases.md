# Supplier notes: a bought standard case with cut end panels

**Not proven by an order.** No standard case has been ordered or machined with this skill. The facts below were read
on one shop's public pages. **As read 2026-11; re-read the live page before every order.** One real failure with such
a case (from an earlier project of a user) is told in section 3: it is the reason for a question in phase 1.

## 1. When it is the cheapest route

A stock extruded aluminium case (a tube, one piece or split, with flat end plates) or a stock moulded plastic case
is the first option of the process choice (SKILL.md rule 18):

- the board or boards fit a stock profile, sliding in its slots or standing on a base plate;
- all connectors, any display and any fan can sit on the two END plates (or the moulded case's flat faces);
- the look of a stock profile is acceptable; no special colour is needed;
- the quantity is small and there is no budget for custom sheet metal.

Rough orders of magnitude read in 2026-11, not quotes: a stock extruded case for a small box started at a few
USD; two custom end plates in sheet metal or CNC cost more than the case. Holes in the extruded
shell itself (vents, a top inlet) need machining of the shell: a manual quote at the case shop, and the saving shrinks.

It is the wrong route when the layout needs openings on the long faces, when the stock height wastes much space, or
when a board cannot have free edges for the slots (section 3).

## 2. What exists (as read 2026-11)

- A sister shop of the JLC group (JLCMC) sells about 140 stock extruded cases in 6063 aluminium, one-piece and
  split, sandblasted or brushed and anodized (natural or black), in a list of fixed lengths per profile, with end
  plates. Laser or UV marking was offered. A "custom enclosure" category takes a manual quote.
- Such a case can share a parcel with a part order of the group's CNC shop (`shipping-and-combine.md`).
- End plates can be ordered as custom sheet-metal or CNC parts from the case maker's drawing of the hole pattern.

## 3. Rails and slots: the keep-out on the board edge

**The failure.** A board was designed for an extruded case with board slots about 2 mm deep. Parts stood closer than
2 mm to the board's long edges. The board would not slide in: it jammed on the rails. The board had to be laid out
again.

**The rule.** In phase 1 ask: "Does any board slide in rails or slots?" If yes:

1. Read the slot from the maker's profile drawing: slot depth, slot width, slot height above the floor, slot pitch.
2. The board's thickness plus tolerance must fit the slot width.
3. Along each edge that sits in a slot, a **free band** on BOTH faces of the board: slot depth plus a margin, with no
   part, no pad of a tall part, no solder joint that stands proud. Through-hole pins near the edge count.
4. The board's width is the distance between slot roots minus a sliding clearance, not the inside width between ribs.
5. Hand the bands to the electronics side in `outline.json` as `keepouts` of `kind = "band"`
   (`interface-electronics.md`; written by `interface_read.py --write-outline`, `[[bands]]`).
6. Draw the cross-section of the profile with the board and its tallest parts before the board layout is frozen.

Check: `fit_check.py` with the profile modelled from the maker's drawing; look at the section view.

## 4. What to check on the maker's drawing

| Item | Why |
|---|---|
| Inside width between ribs AND at slot roots | They differ by several millimetres; the board uses one, the parts the other |
| Inside height, and the height of each slot above the floor | The tallest part per side must clear floor and roof from its slot |
| Slot width | Board thickness with tolerance |
| Slot pitch | Which slots the layout can use |
| Wall thickness | Thread budget of panel parts on the shell; screw length |
| End-plate thickness and its screw pattern (bosses in the profile) | Every panel part's reach (`design-rules/panel-graphics.md` PG-02); the plate drawing |
| Fixed lengths offered | The board length plus connector overhang must match one |
| Tolerance of the cut length | Fit of the board between the end plates |
| Finish and colour of the stock part, and whether end plates match | Look; a ground bond through anodized faces does not exist (`design-rules/shielding-and-ground.md` SG-06) |
| How the two halves of a split profile join | Seam contact for shielding |
| Whether a 3D model can be downloaded by direct link | Real parts rule (SKILL.md rule 9); otherwise build it from the drawing |

Write the profile's numbers into the project with the page address and the date. A measurement the drawing does
not give is asked from the user with a sketch, or the case is bought and measured before the board is frozen.

## 5. Cut end panels

- A flat end plate is the simplest custom part there is: a rectangle with holes (`design-rules/sheet-metal.md` SM-10).
  It goes through the same drawing, rule and catalogue checks as any sheet part.
- Read the stock plate's screw pattern from the maker's drawing; do not measure it from a picture.
- Printed legends on the plate follow `design-rules/panel-graphics.md`.
- A moulded plastic case with holes cut by the user is hand-work: list the minutes and the tools, or have a shop
  quote the machining.

## 6. What to put into the capability sheet

Make `<project>/mech/suppliers/<shop>.capability.toml` in phase 1: the profile code and its fixed lengths
(`[materials]`), the stock finishes by their names (`[finishes]`), the order form's fields (`[forms]`), the read date.
The part itself is a bought part in `vendor3d/vendor_parts.toml` with its source address and licence.

## 7. What is not known

Real accuracy of a stock profile, the real slot dimensions against the drawing, lead time of a custom-length cut,
how shell machining is quoted. After the first order, write these into the project's lessons (phase 16).
