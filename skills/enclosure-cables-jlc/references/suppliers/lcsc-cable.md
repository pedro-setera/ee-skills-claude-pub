# Supplier notes: LCSC Cable (custom harnesses, coax and network cables)

**As read 2026-11; re-read the live page before every order.** Sources: the supplier's quote form and order pages,
its production drawings, and one real order. One order is one data point. The machine-readable
copy is the capability sheet (`templates/lcsc-cable.capability.toml`, copied to `<project>/mech/suppliers/`).

**The revision round (2026-11):** most of the first production drawings were wrong and one Revise round was sent.
The lines came back one by one: some were right and confirmed the next day; others waited on e-mail questions that
settled three facts: +-5 mm is their floor for every cable type, RF included; their only RF coax is blue RG405; a
slim network cable with moulded angled plugs needs a custom mould (section 3). **PROVISIONAL:** everything about the
delivered cables (real lengths, crimps, labels, import duty).

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
| Tolerance | +-5 mm for every cable type, RF coax included: their floor (their own statement). A tighter request is drawn at +-5 without a word, or costs a question round |
| Pin-out of a harness | Wires in positions 1, 2, 3, 4 in order at both ends; no empty cavity |
| Short coax | Blue FEP-jacketed RG405, outer diameter 2.2 to 2.6 mm (size for 2.6). **Their only RF coax** |
| Coax connectors | Generic connectors bought by the production line, not the named part numbers |
| Network cable | Standard round Cat6, 24 AWG, outer diameter 5.8 mm. With moulded angled plugs a slim 28 AWG cable (OD 3.8) needs a custom mould at a high cost (or the line is refunded) |
| Network plugs | Straight moulded plugs unless a picture shows the exits |
| Loose extras | Fitted on the wires |
| Two-row housing numbering | 1..n down one row, n+1..2n down the other |

Write each non-default first in More Requirements and on the drawing as "X, NOT Y" (`design-rules/cables.md` CB-21).
`cable_check.py` (row NONDEF) wants every default either countered or accepted. **Three defaults are their only stock**
(the tolerance, the RF coax, the network cable): design for them from the start and accept them (CB-26); "X, NOT Y"
cannot buy what they do not make.

Got right the first time: housings and terminals given by the supplier's part code; label texts (printed on
heat-shrink); tinned ends and their lengths; angled plug exits once shown a picture; a simple two-wire lead.

Harmless deviations are accepted without a round: a tighter twist pitch than drawn, a parts list whose terminal
count disagrees with the drawing and the test lines. Revise only what breaks fit or function.

## 4. Tolerances

**+-5 mm is their floor, for every cable type, RF coax included** (their own statement: the tightest they can
reliably guarantee; for harnesses a tighter one brings a higher risk of deviation). Tighter requests came back drawn
at +-5 without a word, and a tighter Revise note then cost a question round of days. Ask +-5, never less, and design
every cable to work over nominal +-5 with its minimum still covering the route (`design-rules/cables.md` CB-12,
CB-13). One length per harness: the bundle is threaded through the housing, then crimped, so per-wire lengths are
not made and a per-wire table brings a question.

## 5. Statuses, from quote to production

1. **Waiting for Confirmation**: the request is with the supplier. A question may come by e-mail.
2. **Quote Completed**: an automatic "order confirmation" mail. The pay button stays open for some weeks. The supplier numbers the lines itself: **record the line-to-cable map now** (the entry order does not fix
   it) and write both numbers in every message, as "line -2 (CAB-01)".
3. Payment (the user's).
4. **Drawing in Progress**: about 3 business days.
5. **Drawing need Approval**: an automatic "drawing confirmation" mail. Each line has its own production drawing PDF.
6. **Confirm or Revise, per line.** A revised line shows as modified; an automatic "revised drawing ready" mail
   follows. Revised drawings come back line by line, and a line that needs a decision waits silently for an e-mail
   question: watch the order-detail data every 30 minutes instead of waiting for mails (each line's drawing status:
   modify = in revision, wait_confirm = to review, confirm = done; a new drawing shows as a new date folder in the
   line's PDF address). Confirm each line as soon as it is fully right and the user has said OK (SKILL.md rule 15);
   close the browser tab after each check.
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
- **Their questions come by e-mail, sometimes only as a picture attachment, and in bursts** (a second "addition" mail
  a few minutes after the first). Open every attachment and read the whole thread, then answer every open question
  in ONE reply, naming line and cable on each point.
- **A line mix-up comes back.** A value given for one cable was applied to another line, and the same mix-up
  returned a week later. Correct it in words each time ("that length was for line -A, not line -B") and repeat
  the right value.
- **A short polite note on the delay and what it costs the project,** in the same thread, was answered within hours
  and moved the order forward. Once, not as a habit.
- **Do not settle specifications by e-mail after payment.** Customer service "noted and confirmed" several points on
  one order; only one reached the drawings. Wait for the drawings and fix everything in one Revise round.

## 7. Typical times (one order, 2026-11)

| Step | Seen |
|---|---|
| Quote | 1 to 3 business days, plus one per question. A request sent at the weekend waited for their working week |
| Reply to an e-mail | half a working day to a day; over a weekend from Friday to Monday; minutes for a clear picture |
| Drawings after payment | about 3 business days; drawings finished on a Friday were released on Monday |
| One Revise round | at least 1 business day; lines come back one by one; a question on a line adds a day |
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
