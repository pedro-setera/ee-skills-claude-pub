# Phase 1: requirements and the process choice

Write one page that says what the box and its cables must do, choose how they will be made, and read what each supplier's forms and charts really offer. Later phases may use only what is on those capability sheets.

## Inputs

- The state file with the inventory of phase 0; the board's requirements page and `interface.json` if a board exists.
- `templates/REQUIREMENTS.md`, `templates/CAPABILITY_SHEET.md`, `templates/PRINTER_PROFILE.toml`; the seed sheets `templates/jlccnc-sheet-metal.capability.toml` and `templates/lcsc-cable.capability.toml`.
- `references/suppliers/` (dated notes: `jlccnc-sheet-metal.md`, `jlccnc-cnc.md`, `jlc3dp.md`, `lcsc-cable.md`, `standard-cases.md`); `references/design-rules/` for the vocabulary.
- A browser for the suppliers' public pages (reading only; this phase needs no sign-in).

## Steps

1. **Draft the one page** from what is already known (`templates/REQUIREMENTS.md`): what goes inside, which connector is on which face, where it is used, how it should look, how many, the price position, heat in watts per part, radio or shielding needs, how it is opened for service, what the user already owns. Mark every unknown as UNKNOWN; do not guess a number.
2. **Ask the hidden-constraint questions early** (next section, at most about five in a round). The one about rails matters most: a board that slid in the rails of an extruded case jammed because parts stood closer than 2 mm to the board edge, and the board had to be designed again. A free band on the board edge must be known before the board outline is fixed.
3. **Offer the process path, in this order, with rough costs:**
   1. A bought standard case with cut panels (`references/suppliers/standard-cases.md`; **not proven by an order**).
   2. A printed box only, on the user's printer.
   3. A printed concept, then folded sheet metal at JLCCNC (the proven path of this skill).
   4. CNC-machined parts (`references/suppliers/jlccnc-cnc.md`; **not proven by an order**). Printing outside at JLC3DP (`jlc3dp.md`) is also **not proven by an order**.

   The cheapest standard path that meets the requirement comes first. Say what each means for cost, look, shielding and time. No moulds and no tooling. On a small first order, shipping and duties can cost as much as the parts: show the user a live quote.
4. **Read the capability sheets live.** For each supplier on the chosen path copy the seed sheet to `<project>/mech/suppliers/<id>.capability.toml` and re-read the live pages as `templates/CAPABILITY_SHEET.md` describes: materials, thicknesses, finishes, the powder chart, the anodizing list, the ink chart, the largest size, the form fields, the standard tolerances, the file types. Set `[meta] read_date` to today and list the pages in `sources`. Every seed value is "as read 2026-11; re-read the live page". A value that was not read stays marked "assumed". On one order three requests (masking, a colour by a colour-system number, an ink by a colour-system name) were not in the supplier's catalogue; each cost a question round, and one turned the whole ground-bond design into hand work.
5. **Write what is NOT offered** in plain words in `REQUIREMENTS.md` (for example: coating is all over, no masking; colours by chart name only; no tolerance tighter than the cable maker's standard). Phases 4, 5 and 8 design from this list.
6. **Fill the printer profile** when none exists: ask the printer questions once and write `~/.claude/enclosure-cables/PRINTER_PROFILE.toml` from the template (only after the yes of phase 0). Leave the measured values empty; the test coupon of phase 6 fills them. Record which slicer the user uses and the names of their presets. Their settings are never changed.
7. **Set the review depth facts** now that they are known: for sale or more than 50 units; mains voltage or a lithium battery inside; a radio that must be shielded or must pass through the box; more than about 15 W; a batch the user calls costly. Write each as yes, no or unknown.
8. **Show the page and ask for the confirmation.** Lead with the process path and the three numbers that drive it (size class, quantity, watts). The user confirms the page in writing; record their words and the date.

## Questions for the user

- How will the box be made?
  - Suggested: print the concept at home first, then folded aluminium sheet.
  - Why: the print proves the fit for the price of filament; sheet metal is the cheapest metal box and it shields radio. If a bought standard case of the right size exists, it is cheaper still.
- Which printer, bed size, nozzle and materials do you have, and which slicer? (asked once, kept in your profile)
  - Suggested: the material you print most, for the concept.
  - Why: the concept is thrown away after the fit check; the easiest material is the right one.
- For every part that passes a wall (jack, plug, switch, LED): its thread length, nut across flats and thickness,
  washer, body length behind the panel, and what the mating plug needs in front of it. Ask for the maker's drawing
  or a measurement with a sketch; a value nobody has is UNKNOWN and is named as a risk.
  - Why: the reach check (phase 2) and the cable routes (phase 5) need these numbers before the box size is fixed.
- Does any board slide in rails or slots?
  - Suggested: no rails; boards on stands with screws.
  - Why: rails need a free band along the board edge, and that changes the board.
- How many units now, and is it for sale?
  - Suggested: 2 sets for a first batch.
  - Why: the second set adds little cost and gives a spare; "for sale" raises the review depth.
- Is there a radio inside? Must it be shielded, or must it pass through the box?
  - Suggested: tell me which; a radio inside a metal box gets a test plan.
  - Why: metal blocks radio; it is cheap to plan for and costly to find after the order.

## Done when

- [ ] `REQUIREMENTS.md` has no empty heading; every unknown is written UNKNOWN with who will supply it. Evidence: the file.
- [ ] The process path is chosen and recorded with the user's words. Evidence: the decisions table of the state file.
- [ ] One capability sheet per supplier on the path, `read_date` today, sources listed, the "not offered" list written. Evidence: `suppliers/*.capability.toml`, `REQUIREMENTS.md`.
- [ ] The printer profile exists outside the skill, or the user declined it (then the defaults are used and the rows say so). Evidence: the path in `mech.toml`.
- [ ] The review depth facts are written, unknown counted as yes. Evidence: the state file.
- [ ] The user confirmed the page. Evidence: their words and the date.

## Outputs

- `mech/REQUIREMENTS.md`
- `mech/suppliers/<id>.capability.toml`, dated
- `~/.claude/enclosure-cables/PRINTER_PROFILE.toml` (user profile, outside the skill)
- `PROJECT_STATE.md`: the path, the facts, the confirmation

## If something is missing

- Cables only: the page shrinks to the cable part (from where to where, currents, environment, quantity) plus the cable supplier's capability sheet.
- No browser: use the seed sheets, keep every value marked "as read 2026-11, not re-read", and say at gate 2 that the capability was not confirmed live. The independent re-read of phase 10 is then a blocker for the order.

## Lessons behind this phase

- Masking, a colour by a colour-system number and an ink by a colour-system name were designed in and then refused: none was in the supplier's catalogue -> steps 4 and 5: the capability sheet first, and a written list of what is not offered.
- A board that slid in case rails jammed on parts near its edge and was designed again -> step 2 asks about rails before the outline is fixed.
- Premium parts and an accessory kit were offered beyond what the requirements asked -> step 3: the cheapest standard path first, extras only as an offer with their cost.
- A mould-based part was proposed and dropped for its tooling cost -> step 3: no moulds, no tooling.
- Supplier values copied from an old note were wrong on the day of the order -> step 4: every value carries its read date.

The full cases are in `references/lessons.md`.
