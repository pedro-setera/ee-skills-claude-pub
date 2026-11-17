# After the JLCPCB order

What happens between payment and shipping: order states, engineering questions, the 72-hour placement confirmation, holds, support, timing, and what can no longer change. Read at phase 14.

Facts here were read or observed in 2026-11. Re-read the live JLCPCB page before relying on any number, option name or fee.

## Contents
1. Sources
2. Order states seen and what each means
3. Review before payment
4. The Replace function for BOM lines
5. Engineering questions by e-mail
6. The parts-placement confirmation (72 hours)
7. Order on hold, and how to release it
8. Support form and live chat
9. Typical days between steps
10. What cannot be changed after the order
11. Not recorded here

## 1. Sources

- **[ORD4]** a 4-layer assembled order, 2026-11.
- **[ORD2]** a 2-layer assembled panel order, 2026-11, paid the day after submission.
- **[ENG]** the assembler's engineering e-mails on those orders.
- **[CONF]** the placement confirmations of both orders.
- **[SUP]** the support form and live chat, the same weeks.
- **[SIS]** cable and CNC orders at sister services in the same month.

## 2. Order states seen and what each means

| State | Seen on | What it means | What to do |
|---|---|---|---|
| Under review before payment (exact label not recorded) | [ORD2] | JLCPCB checks the files; payment opens after | watch; tell the user when pay opens |
| "In Production" | [ORD4], [ORD2] | batch accepted; data preparation may still be open | do not read it as "all settled" |
| "Data Preparation", "Advanced option review" | [ORD4], sub-steps | engineers prepare the assembly; questions come from here | answer e-mails within hours |
| On hold, waiting for clarification | [ORD4] | the customer's instructions conflict or are missing | one clear answer, ask for release (section 7) |
| Placement confirmation pending (e-mail) | [ORD4], [ORD2] | 72-hour clock running | check and confirm (section 6) |
| "Completed", then "In Production" | [CONF] | placement confirmed, production continues | screenshot as proof |
| "Shipped" | [ORD2] | handed to a courier (here a local courier to the collection warehouse) | update the shipping plan |

Seen at sister services [SIS], useful when one order waits for another: "Waiting for Confirmation" (quote not yet priced), "Quote Completed", "Drawing in Progress" (production drawings after payment), "File Review", "Pending" (waiting for the customer), "Awaiting Payment" (the pay button appears only after every part of the order is reviewed).

Keep a baseline table of all open orders and report only changes.

**Pace.** Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8). A block locks the user out of the open orders. The watch checks every few hours, never every few minutes, and loads each order page once per check; nothing reloads a page in a loop to wait for a status. Open the order pages and the chat one at a time.

## 3. Review before payment

- [ORD2] entered JLCPCB's review after submission and could be paid only after it passed; [ORD4] was paid at once. The trigger is not recorded (see `order-flow.md` section 4).
- After the review the order total can change; one sister-service order rose slightly after its review [SIS]. Read the total again before telling the user to pay.

## 4. The Replace function for BOM lines

- Seen once [ENG]: an engineer offered to leave one designator unpopulated by using "Replace" on the BOM line on the order page. The button no longer existed: the order was already "In Production".
- Support said that a "Component Replacement" option opens in the live chat at the confirmation step [SUP]; at that step the chat could not open it and passed the request on by e-mail, and the change was never applied. The two statements disagree; treat any part change after payment as uncertain.
- A shared BOM line can only be replaced or left out as a whole (`parts-library.md` section 7).
- Rule: correct the files before ordering. If a change is found after payment, keep a written fallback (hand rework) and put it as step 0 of the first power-up with a numeric pass value.

## 5. Engineering questions by e-mail

Questions met [ENG]:
- "Should the order remark be followed or ignored?" The reply, numbered: parts not to assemble by designator, points that were information only, rails and tooling holes on the long sides only, a request to check SOT-23 pin 1, a polarised capacitor and the diode bands.
- "Your tooling holes are not recognised; may we add our own?" Routine: yes, on the rails, clear of fiducials and mouse bites. Avoided from the start by leaving tooling holes out of the files and choosing "Added by JLCPCB" (`assembly.md` section 5).
- "One designator on a shared BOM line cannot be changed: leave it unpopulated via Replace, or leave the whole line empty?" Leaving the whole line empty was never acceptable.

How to answer:
- Same thread, within hours. Each question costs about a working day in the factory's time zone (GMT+8).
- To the user: the question in 3 to 4 plain lines (what they ask, why, the consequence), one recommended option with the reason, a ready draft, and one yes/no. Supplier e-mails can look alarming; read them for the user in plain words.
- In the draft: one topic; the supplier's own references; every designator named, including the ones that must stay as they are ("leave ONLY Rn unpopulated; every other designator on that line is assembled as usual"); a picture where geometry matters; no product, board or customer names; define any jargon.
- If a decision changed since an earlier message, withdraw the earlier instruction explicitly in the same reply (section 7).
- Send only after the user's yes, from the user's mail, text as approved; check that it is in Sent. List any deviation from the approved text to the user afterwards.

## 6. The parts-placement confirmation (72 hours)

**The e-mail:** "Please confirm parts placement". Confirm within 72 hours, or the order goes into production as it is [CONF]. It came between 1 and 4 days after payment on the two orders. Check the inbox and the order page daily after payment.

**How to check** (the method used on both orders):
1. Open the order page and its placement viewer.
2. Overview of the whole board first; then systematic strips of the top side, then the bottom side, then the 3D view.
3. For every part: designator, LCSC code and position against the BOM and placement file; pin 1 or polarity of every IC, diode, LED, polarised capacitor, transistor and connector against the silkscreen mark.
4. DNP parts show as bare pads; hand-fit parts are absent; nothing is missing or extra.
5. Open "Show Revised Items": the engineer's changes. On [ORD4] the engineer had turned a buck converter by 90 degrees to match JLCPCB's production library; it was accepted after checking that pin 1 still landed on pad 1.
6. Save a zoomed crop per polarised part and look at it. Narrate progress ("12 of 15 top strips done, no finding") so the user is not watching a silent screen.
- Do not assume an e-mailed instruction reached the placement team: on [ORD4] a part asked by e-mail to change was still shown as the original.
- For an order placed outside this skill, check against the exact files that were uploaded and a polarity reference from the user; without them nothing is confirmed by the agent (`phases/14-watch.md`).

**The confirm page:** it offered "Yes, proceed to production" and a path to ask for modifications with a remark [CONF].

**Permission and proof:**
- Clicking confirm is a confirmation on the manufacturer's site: it needs the user's explicit permission, once per order.
- Write the pass conditions into the brief: every part correct, every pin 1 and polarity correct, every DNP unplaced, nothing missing or extra, every engineer change harmless. If anything fails, do not confirm: report with the crops and a short draft message.
- After confirming, screenshot the new status ("Completed", then "In Production") and file it in the order log.
- Touch nothing else on the page: no terms, payment or options.

## 7. Order on hold, and how to release it

- **Cause seen once [ORD4]:** one e-mail asked to leave a part unfitted; a later decision kept the part as placed, and the first request was not withdrawn. The two instructions contradicted each other and JLCPCB put the order on hold.
- **Release:** one short e-mail in the same thread with the decision ("keep the part as originally planned") and "please release the order to production", plus a polite live-chat note. It cost about one day.
- **Prevention:** when a decision changes, withdraw the earlier instruction explicitly and at once. If the user prefers to leave a contradiction open, tell them plainly that it may cause a hold.

## 8. Support form and live chat

- **Support form [SUP]:** the topic dropdown snapped to a wrong topic the first time and was corrected before sending. After sending, a success note appeared but the form kept its text, so it looked unsent; the browser's network log showed that exactly one request had succeeded. Replies go to the account's e-mail, not to the page.
- **Live chat:** on a weekend day it said nobody was online for assembly orders; retry on a working day. When open, the agent passed the request to the engineers without a time frame.
- **How to use the chat:** collect the order references first; one short, polite message per topic; keep the chat open and watch for the reply; expect no time frame. JLCPCB's chat also forwarded questions about LCSC's cable service to that team.
- **When:** a nudge is reasonable once the supplier is past its own stated time, or when an order is on hold and the answer has been sent. Every chat message and e-mail goes out only with the user's go; a user may give a standing permission for polite status nudges, recorded in the state file.

## 9. Typical days between steps

| Step | [ORD4] 4-layer | [ORD2] 2-layer panel |
|---|---|---|
| Submitted to paid | same day | next morning, after review |
| Paid to first engineering question | 2 days (the remark), then 3 to 4 days (shared line) | day of payment (tooling holes) |
| Paid to placement e-mail | 3 to 4 days | 1 day |
| Confirmation, hold and release | all on the same day | confirmed on day 1, no hold |
| Later milestones | PCBs due about 3 days after confirmation, then assembly | shipped to the warehouse within 4 days of payment |

- Plan 3 to 4 days between payment and settled production for assembled boards. Supplier time frames ("2 to 3 hours", "today") are estimates; never promise the user a date from a supplier statement.
- Engineers work in GMT+8 and were off at night; an answer sent after their working day is read the next morning there. Convert their hours to the user's time zone when planning replies.

## 10. What cannot be changed after the order

- One designator of a shared BOM line: only the whole line can be replaced or left out [ENG].
- The shipping address: it is fixed at checkout. This decides combined shipping (`combined-shipping.md`).
- BOM parts once the order is "In Production": the Replace button is gone.
- The production files: once ordered they are frozen; the next batch gets a new revision letter.

## 11. Not recorded here

- The exact JLCPCB label of the pre-payment review state; its usual duration.
- Whether the 72-hour window counts working days or calendar hours, and what happens on weekends.
- Whether a remark on the confirm page is acted on before production.
- Support chat opening hours.
