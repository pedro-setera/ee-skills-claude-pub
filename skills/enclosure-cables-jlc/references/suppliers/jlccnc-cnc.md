# Supplier notes: JLCCNC, CNC machining

**Not proven by an order.** No CNC part has been ordered with this skill. Everything below was read on the supplier's
public pages. **As read 2026-11; re-read the live page before every order.** Say "not proven by an order" to the user
when a project uses this file. The design rules are in `design-rules/cnc.md`.

## What was read (2026-11)

- Services: 3-, 4- and 5-axis milling, turning, EDM. Minimum order 1 piece.
- Materials: aluminium 6061 and 7075; brass, copper, a stainless steel, a carbon steel; plastics (ABS, FR4, PA6, PC,
  PMMA, POM and one more). Sheet-metal 5052 is not a CNC material there.
- Size: largest part about 1100 x 600 x 500 mm; a smallest size applies to special shapes. Read both on the live page.
- Finishes for aluminium: bead blasting, anodizing (nine named colours, matte or glossy, also with bead blasting or
  brushing), conductive anodizing, hardcoat anodizing, brushing (flat faces only), UV printing (eight named colours),
  laser marking (one tone, needs a 2D file). No powder coat on the CNC list.
- Tolerance: default ISO 2768 medium. The quote tool offered +-0.10, +-0.05 and +-0.02 for areas marked on the
  drawing.
- Appearance grades: three (standard, strict, premium) with different roughness.
- Build time in the tool's demo: three speeds (about 3, 6 and 11 days) at three prices.
- Payment: either review before payment, or automatic payment for small orders.
- The automatic quote is "for reference only" and is not given above 20 pieces, for multi-body files, for
  unrecognised features or for EDM: those go to a manual quote, said to come within a day.
- Where the 2D drawing and the web selections differ, the web selections prevail.
- Threads, marking, tolerances and roughness are made strictly from the 2D drawing.
- The production clock stops while a question from their engineer is open.
- Prices rose in 2026-05 with material and tooling costs: old price notes are worthless.

## What to read on the live pages and put into the capability sheet

Make `<project>/mech/suppliers/jlccnc-cnc.capability.toml` in phase 1, with the read date, from:

| Read | Put into the sheet |
|---|---|
| The CNC quote tool: material list | `[materials]` |
| The quote tool: finish list, colours per finish, gloss | `[finishes] anodize, other`; the colour names exactly as written |
| The colour chart pictures (anodizing, UV print) | `[coat_rgb]`, `[ink_rgb]`, marked approximate |
| The CNC design guideline: corner radius, wall, pocket depth, thread rules, hole depth | a `[cnc_rules]` section of your own (no script reads it; the reviewer does) |
| The tolerance options and what "standard" means | `[limits] standard_tolerance`, `[tolerances]` |
| Size limits | `[limits]` |
| The ordering guideline: what needs a 2D drawing, which wins on conflict | `[process]` |
| The marking design page: smallest text, line, margin, file type | a `[marking_rules]` section of your own |
| The quote form: every field in order, which are free text | `[forms]` |
| How-to-order: payment modes, review time, cut-off hour for payment | `[process]`, `[hours]` |

`catalogue_scan.py` reads `[finishes]`, `[materials]`, `[ink_rgb]` and `[limits] standard_tolerance` from any
capability sheet, so the catalogue check works for CNC. The sheet-metal measure scripts do not (`cnc.md` CNC-13).

## What is not known

Whether their CNC review behaves like the sheet-metal review (one reviewer per part, no "review completed" mail);
real lead times; how totals move between review and payment; whether a tight tolerance is questioned or silently
relaxed; how UV print files are read (assume the sheet-metal lesson: layer colour = ink colour). After the first CNC
order, write these into the project's lessons and propose them for this file (phase 16).
