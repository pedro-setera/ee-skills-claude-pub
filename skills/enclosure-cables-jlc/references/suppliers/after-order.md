# After the order: questions, messages, production holds, the watch

**As read 2026-11; re-read the live page before every order.** Sources: the question rounds of one sheet-metal order
and one cable order. Used in phase 13. The cable revision round's outcome is **PROVISIONAL**
(`lcsc-cable.md`).

## 1. When a question arrives

1. **Read every thread about that part.** Two people may write about one question in separate threads within
   minutes. Decide only when all are read.
2. **Give the user three lines:** what they ask, what it means for the part, the one recommended answer.
3. **Draft an answer to exactly what is asked** (section 2). Show it. Send only after the user's OK, or under a
   standing OK for this order that is written in the state file.
4. **Answer the same supplier day** (`supplier_calendar.py deadline --answer`). After their close it waits a day.
5. **Log it:** time in, time out, the question, the answer, the cause (ours or theirs), the cost in days.
6. **Trace the cause.** Nearly every question of the first orders was a word in a remark or a drawing that was not a
   catalogue value. Fix the generator, not only the answer, so the next revision cannot ask for it again.

## 2. Message style

- **Only what is asked.** For that part or line only. No second topic, no "also", no "just to confirm".
- **In the same thread,** as a reply.
- **In their words.** Use the names on their form and in their question ("clinch nut", not "fastener").
- **Name the part by both numbers:** theirs and ours. For cables: "line -2 (CAB-01)".
- **Short numbered lines in simple English.** For a correction: "X, NOT Y".
- **Their number and ours** when a value is discussed: "Your drawing: 80 +-5. Required: 85 +-3."
- **One picture** where a picture says it: a pin map, a plug view, an ink table. No product or board names in it:
  End A / End B, P1 / P2, part numbers (SKILL.md rule 20).
- **For artwork, send corrected FILES, not an explanation** (section 3).
- **No names of people, no order history, no apology paragraphs.**
- Template: `templates/SUPPLIER_MESSAGE.md`; for a cable drawing: `templates/REVISE_NOTE.md`.

Model answers:

```
Re: <their subject>
Part <their part number> (<our part number>):
1. Powder coat all over: yes.
```

```
Line -5 (CAB-05):
1. P1 is a 4-position housing, NOT 2-position.
2. P1 wires in positions 1 and 4. Positions 2 and 3 EMPTY.
3. Wire 26 AWG, NOT 20 AWG (terminal range 24-30 AWG).
See picture.
```

What went wrong before, each costing a round:

- An answer "yes, all over" that added a line about keeping nut threads clean, on a part with no nuts. The reviewer
  asked what nuts.
- An extra mail "please confirm both parts are in the same batch". The reviewer asked which parts were meant.
- An answer to "cable 4" for OUR cable 4. Their "4" was their line 4, a different cable. A wrong length was applied
  to a multi-wire harness and found only on the production drawing.
- A text explanation of which file colour meant which ink. The factory asked for a new drawing and a render instead.

## 3. Production holds

A hold after payment stops only the held part, but the order ships with its slowest part.

- **A print (ink) question:** answer with a corrected set, made in minutes from the ordered file: the print file with
  every ink layer named and coloured as its chart ink and no other colour; a one-page ink sheet (`ink_sheet.py`);
  front and rear renders. Geometry is not changed: the part is already cut.
- **A colour question:** the chart name only.
- **A geometry question:** the supplier's proposal in their words, our yes or no, and nothing else. A change to a
  part that is already cut is a new part: say so to the user with the cost.
- When an order is on hold for our decision: one short message with the decision and "please release the order to
  production" is enough.
- The order page shows the held part as pending until the answer is processed. Check the page after the answer; a
  thank-you mail from one person does not mean the other thread is closed.
- Frozen files stay frozen. What was sent for an answer is saved beside the order as its own dated folder; the next
  order gets a new revision letter.

## 4. Cable production drawings

`lcsc-cable.md` section 6 and `review-briefs/production-drawing.md`. In short: check every line field by field
(`production_drawing_check.py`), put everything wrong on a line into one Revise note with one picture, confirm only
a line that is fully right, and only with the user's permission. Do not confirm specifications by e-mail after
payment: they do not reach the drawing.

## 5. Payments and totals

- "Submit" is not payment on a review-first shop. After the review an automatic payment may be tried and fail; the
  user then pays by hand.
- Read the total, the shipping line and the coupons again at the pay step.
- After each payment re-read the whole shipping plan and tick what is done (`shipping-and-combine.md` section 5).

## 6. The watch

Every open quote, review, drawing and shipment is on the watch with its deadline in the supplier's time and the
user's (`templates/WATCH_PROMPT.md`).

| Watch | Signal | Then |
|---|---|---|
| Quote requested | status "quote completed", or a question mail | record the line map; show the total; gate 3 |
| No quote after 2 business days | nothing | one nudge, timed before their morning |
| Case in review | a part "pending", a question mail, the pay button | section 1; or gate 3 |
| Paid, cables | "drawing need approval" | the field-by-field check |
| Revise sent | "revised drawing ready" | check again, only the revised lines plus each drawing's date |
| In production | a hold, a step that stops moving | section 3 |
| Shipped | tracking | write the incoming check (phase 14) before the parcel arrives |

- There may be no mail when a review completes: the watch reads the order page, not only the mailbox.
- Ask the user once whether the agent may watch the mailbox, or only the order pages.
- A watch that has a deadline and no owner is a lost day: the state file names who watches (the agent on a schedule,
  or the user).
- Record real times as they happen: they become the next project's plan (phase 16).

## 7. What never happens here without the user

Sending any message they have not seen; Confirm; accepting a supplier's proposed change; payment; a terms box
(SKILL.md rule 15).
