# Supplier notes: LCSC Cable (custom harnesses, coax and network cables)

**As read 2026-11; re-read the live page before every order.** Sources: the supplier's quote form and order pages,
its production drawings, and one real order. One order is one data point. The machine-readable
copy is the capability sheet (`templates/lcsc-cable.capability.toml`, copied to `<project>/mech/suppliers/`).

**PROVISIONAL:** the outcome of a revision round. On the order behind this page most of the first production
drawings were wrong and one revision round was sent; whether the supplier then accepted each non-default item (cable
types, a tight tolerance, empty cavities, named connectors) is not yet known. So is everything
about the delivered cables: real lengths, crimps, labels, import duty.

## 1. The path through the site

Customize, then a service class, then a segment: **Terminal Harness**, **Ethernet Cable**, **RF Cable**, **Others**.
"Submit for Final Quotation" asks for a quote only: no payment. The site shows its own estimate only for harnesses.
The cable shop needs its own sign-in.

**A submitted quote cannot be edited.** "Edit" changes only the PO number. A change means a new quote with every
cable entered again, and two quote numbers to track. Freeze the cable list first (SKILL.md rule 11).

## 2. The form segments and their fields

| Segment | Fields | What follows |
|---|---|---|
| Terminal Harness | Item name; Side A and Side B (housing and terminal by the supplier's part code, or "Tinned" with a tin length); wire standard (UL type); AWG; ONE wire length; colour (a multi-colour choice plus a note); twisted; pinout ("Other (per drawing)"); drawings; More Requirements; quantity or production volume; PO number | The quote line reflects the fields |
| RF Cable | Item name; drawings; More Requirements; quantity | **No fields for cable or connectors.** The quote line always reads generic. Only the production drawing shows what will be made |
| Ethernet Cable | Item name; drawings; More Requirements; quantity | The same. Angled plugs are moulded by the supplier, not bought parts |
| Others | Item name; drawings; More Requirements; quantity | |

- Files: up to 5 per item, each under 15 MB (PDF, PNG, JPG and others).
- The More Requirements length limit was not recorded: the seed sheet assumes 500 characters. Read it on the live page.
- Name each item with our part number. Add `CUST P/N: <our id>` in More Requirements: their drawings print it.
- Read back every field of every cart item before submitting (`cable_fieldsheet.py --readback`). A length field
  did not take at the first try on one order.
- The field sheet and More Requirements text come from `cable_fieldsheet.py`, never typed from memory.

## 3. Stock defaults seen

For anything that is not a form field the supplier uses its stock default, even when a drawing or a remark says
otherwise. Seen on one order:

| Item | Their default |
|---|---|
| Tolerance | +-5 mm drawn when a tighter value than standard was asked |
| Pin-out of a harness | Wires in positions 1, 2, 3, 4 in order at both ends; no empty cavity |
| Short coax | A jacketed semi-flexible coax of 2.6 mm outer diameter (a bare family name was read as this) |
| Coax connectors | Generic connectors bought by the production line, not the named part numbers |
| Network cable | A standard round 24 AWG patch cable, not a slim one |
| Network plugs | Straight moulded plugs unless a picture shows the exits |
| Loose extras | Fitted on the wires |
| Two-row housing numbering | 1..n down one row, n+1..2n down the other |

Write each non-default first in More Requirements and on the drawing as "X, NOT Y" (`design-rules/cables.md` CB-21).
`cable_check.py` (row NONDEF) wants every default either countered or accepted.

Got right the first time: housings and terminals given by the supplier's part code; label texts (printed on
heat-shrink); tinned ends and their lengths; angled plug exits once shown a picture; a simple two-wire lead.

## 4. Tolerances

Standard +-3 or +-5 mm. A tighter value is **not questioned**: the standard is drawn silently, and even a +-3
request can come back +-5. Design to +-5 (`[tolerance] design_mm`, PROVISIONAL) and ask +-3
(`design-rules/cables.md` CB-12). One length per harness: the bundle is threaded through the housing, then
crimped, so per-wire lengths are not made and a per-wire table brings a question.

## 5. Statuses, from quote to production

1. **Waiting for Confirmation**: the request is with the supplier. A question may come by e-mail.
2. **Quote Completed**: an automatic "order confirmation" mail. The pay button stays open for some weeks. The supplier numbers the lines itself: **record the line-to-cable map now** (the entry order does not fix
   it) and write both numbers in every message, as "line -2 (CAB-01)".
3. Payment (the user's).
4. **Drawing in Progress**: about 3 business days.
5. **Drawing need Approval**: an automatic "drawing confirmation" mail. Each line has its own production drawing PDF.
6. **Confirm or Revise, per line.** A revised line shows as modified; an automatic "revised drawing ready" mail
   follows.
7. Production after Confirm: 10 business days were quoted.

The supplier's process is fixed: asking for drawings before payment was ignored.

## 6. Confirm and Revise

- **Confirm** opens a notice that assembly begins after the click. Confirm only a line that is fully right. Confirm
  is the user's decision (SKILL.md rule 15).
- **Revise** takes a note of at most 500 characters and ONE picture (PNG, JPG or PDF) per line.
- Check every drawing field by field first (`production_drawing_check.py`, `review-briefs/production-drawing.md`):
  wire per position, gauge against the crimp range, cable type, part numbers, length, tolerance, label text, pin-1
  mark, and the drawing's date. A "revised drawing" mail once arrived minutes after the first drawing, before any
  feedback was sent.
- Put everything wrong on a line into ONE note: short numbered lines, "X, NOT Y", their end names (P1, P2), one
  picture (pin map, wiring sketch or plug view). `production_drawing_check.py` writes the note; it flags a note above
  the limit and does not shorten it.
- Their pin-1 mark on a housing is a pen dot at cavity 1.
- **Do not settle specifications by e-mail after payment.** Customer service "noted and confirmed" several points on
  one order; only one reached the drawings. Wait for the drawings and fix everything in one Revise round.

## 7. Typical times (one order, 2026-11)

| Step | Seen |
|---|---|
| Quote | 1 to 3 business days, plus one per question. A request sent at the weekend waited for their working week |
| Reply to an e-mail | half a working day to a day; over a weekend from Friday to Monday; minutes for a clear picture |
| Drawings after payment | about 3 business days; drawings finished on a Friday were released on Monday |
| One Revise round | at least 1 business day |
| Production after Confirm | 10 business days quoted |
| Express shipping | 3 to 7 days |
| **Request to door** | **about 4 weeks** |

Cables are the critical path of a box project: start them first (`order-flow.md`). If no quote has come after two
business days, send one short nudge timed to land before their morning. Working hours: 09:30 to 12:00 and 13:30 to
18:30, UTC+8, Monday to Friday (the defaults of `supplier_calendar.py`).

## 8. Money (rough, from one past order)

- Small cables cost a few USD each.
- Express shipping of a parcel of a few hundred grams cost more than the cables. A slow line cost much less.
- Terms were FCA: duties and taxes are paid on arrival. The amount is not yet known.
- Checkout has a compliance-statement box (a terms box: the user's), then card, wallet or wire.

## 9. Combined shipping

A cable order can travel with one board order and with a parts order of the group's parts shop
(`shipping-and-combine.md`). Plan it before the first checkout: it cannot be changed later.

## 10. Browser notes for this site

- The site can freeze screenshots: read it as page text (`order-flow.md` section 6).
- Each line's drawing PDF address and status are in the order-detail data: download by direct link, never by a click.
- File uploads read only the session's own folders: copy the upload set there first.
