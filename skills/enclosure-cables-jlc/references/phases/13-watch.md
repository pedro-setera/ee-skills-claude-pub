# Phase 13: order watch, production drawings, one revision round

Watch each order with its deadline in the supplier's time, answer questions the same supplier day and only what is asked, check the cable maker's production drawings field by field, and put everything wrong into one revision round. A waiting question, drawing or payment starts at its own step at once.

## Inputs

- `orders/ORDER_LOG.md` (references, line map, totals, shipping plan), `orders/ORDER_PLAN.md`, the frozen files, `cables/cables.json`, the field sheets.
- `references/suppliers/after-order.md` (statuses, signals, times between steps; dated, re-read the live pages), `shipping-and-combine.md`, `lcsc-cable.md`.
- `scripts/supplier_calendar.py`, `scripts/production_drawing_check.py`, `scripts/ink_sheet.py`, `scripts/silk_dxf.py`.
- `templates/WATCH_PROMPT.md`, `templates/SUPPLIER_MESSAGE.md`, `templates/REVISE_NOTE.md`; `references/review-briefs/production-drawing.md`.
- A browser the user has signed in to; scheduling and mailbox tools if they exist (`references/tools.md`).

## Steps

**An order placed outside this skill:** ask the user for the exact files that were uploaded, from their own copy, copy and hash them, and rebuild the order log and the line map from the order page. Without the files "the drawing is right" is UNKNOWN: report what you see and the user confirms.

### The watch

1. **Take a baseline.** Open every order page and fill the baseline table of `ORDER_LOG.md`: order, status in the page's own words, held parts, ships to, last change. For each open step compute the deadline: `python -I <skill folder>/scripts/supplier_calendar.py deadline --answer --at <ISO time the message came> --project <project>/mech` (or `--pay`). From now on report only changes.
2. **Offer the watch** (`templates/WATCH_PROMPT.md`): every few hours (every 30 minutes only while cable drawings are being revised, step 16b), each order page loaded once, one push when a status changes, ending by itself at delivery. Offer the mailbox check as an opt-in that drafts and never sends. If the browser is signed out the watch says so once and stops; it never signs in.
3. **Know the signals, and check before raising an alarm.** A metal order may send no "review completed" message: on one order the only signal was an "automatic payment failed" mail, and the pay button appears only after every part is reviewed. A held part shows a pending status on the order page until the answer is processed. Read the page first, then report.
4. **Promise nothing.** Pass the supplier's time statements on as "the supplier says". Plan one supplier working day per question round. Real steps seen on one metal order: plain parts approved about half a day after a night submit, a part with questions more than two days; planned by the order page: raw parts 4 days, coated 6, coated and printed 7; the print step alone then took 2 to 3 days after the coat, and the order shipped with its slowest part.

### A supplier question

5. **Summarise for the user in three lines:** what they ask, why, what follows from each option. One recommendation. A draft from `templates/SUPPLIER_MESSAGE.md`.
6. **Answer only what is asked, for that part or line only, in the same thread, in their words,** with their number and ours on every line. No extra sentence, no "just to confirm", no second topic. Half the question rounds on one case were caused by the customer's own extra lines.
7. **A question about artwork or inks is answered with corrected files, not with text:** a new print file (`silk_dxf.py`), the ink sheet and a factory view (`ink_sheet.py`), a render. A text answer with a picture was not enough once; the factory asked for a new drawing and a render, one more round on the held part.
8. **Read every new thread about the part before calling it closed.** Two people at one supplier answered the same question in separate threads minutes apart, one with thanks and one with a new request.
9. **Show the message before it goes,** unless a standing OK for that order is recorded. After typing in a web mail or chat, read the body and the attachment list back from the page's own text before Send: typed text was once garbled by the page. Afterwards check that it is in the sent folder and log it. Attachments are copied to a folder the browser tool can read and respect the size limits.
10. **Do not ask for confirmations by e-mail after payment.** A supplier's "fully noted and confirmed" covered several points; only one reached the drawings. Only the production drawing counts.
11. **One nudge, well timed.** When a quote or review is past the supplier's own stated time (for a cable quote: none after two business days), send one short nudge timed to land just before their morning opens (`supplier_calendar.py submit-window`). Ask once per order for a standing OK for such nudges.

### Cable production drawings

12. **Fetch each line's drawing** by its direct link (never a download click) into `orders/production_drawings/`, named with both numbers. Note each drawing's date: a "revised drawing ready" mail once arrived minutes after the first drawings, before any feedback had been sent.
13. **Read each drawing field by field, never in bulk.** Start a fresh reviewer with `references/review-briefs/production-drawing.md`. For each cable:
    `python -I <skill folder>/scripts/production_drawing_check.py --project <project>/mech --template <id> --pdf <their drawing.pdf>`
    writes `supplier_drawing_<id>.toml`; the reviewer fills it while looking at the drawing: the wire per position at each end, the gauge, the cable text, the part numbers, the length and its tolerance, the label text, the pin-1 mark, the date, the supplier's line number. An empty value means "not read" and is never a match.
14. **Run the check:**
    `python -I <skill folder>/scripts/production_drawing_check.py --project <project>/mech --sent <date of our last note>`
    Per cable the verdict is CONFIRM, REVISE or NOT DECIDED, with a ready note. On one order most of the drawings were wrong: wires in the wrong positions, a gauge outside the crimp's range, a standard cable instead of the thin one asked, a jacketed coax and generic connectors instead of the named ones, and the standard tolerance instead of the one asked.
15. **Put everything wrong into ONE revision round.** Revise only what breaks fit or function: a tighter twist pitch than drawn, and a parts-list count that disagreed with the drawing and the test lines, were accepted without a round. Per line a note from `templates/REVISE_NOTE.md`: short numbered lines, "X, NOT Y", both numbers, one picture (pin map, wiring sketch or plug view) within the note's length and picture limits on the capability sheet. Show all notes to the user together, then enter them in one session.
16. **Confirm only a line that is fully right,** with the user's permission and written pass conditions: every position, gauge, cable type, part number, length, tolerance, label and pin-1 mark equals `cables.json`, and the drawing is dated after our last note. Confirm starts the assembly of that line. Save a screenshot of the new status.

16b. **Watch the revised lines every 30 minutes** while drawings are being revised: they come back line by line, and a line that needs a decision waits silently for an e-mail question. Read the order-detail data (each line's drawing status: modify = in revision, wait_confirm = to review, confirm = done; a new drawing shows as a new date folder in the line's PDF address), check each returned line at once, confirm it as soon as it is fully right and the user has said OK (step 16; SKILL.md rule 15), and close the browser tab after each check. Back to the slow watch after the last Confirm.
16c. **Answer questions in ONE reply.** A question may come only as a picture attachment, and a second mail may follow minutes later: open every attachment, read the whole thread, then answer every open question in one reply, line and cable named on each point (`suppliers/after-order.md` section 1). A line mix-up may come back: correct it in words each time and repeat the right value.
16d. **On a delay caused by their questions,** one short polite note in the same thread on what the delay costs the project was answered within hours and moved the order forward. Once, not as a habit.

> **The revision round (2026-11):** one Revise round; the lines came back one by one; some were right the next day, others waited on e-mail questions that settled the +-5 floor and the maker's only stock cables (`suppliers/lcsc-cable.md`). **PROVISIONAL:** the real production start and delivery dates after the Confirm.

### Always

17. **After each payment and each status change, re-read the shipping plan and tick it.** Check on the joining order's page that the orders are linked; the page is the proof.
18. **Use the waiting time:** write `arrival/INCOMING_CHECK.md` (phase 14) and the manual draft (phase 15) before the parcel arrives.
19. **Keep the order log:** every status change, question, answer, date and cost; for each supplier question the form field, file or remark that caused it. Close the watch at delivery: delete the scheduled task, record the delivery data and the duties paid, tell the user in one line.

## Questions for the user

- Shall I check the order pages every few hours (every 30 minutes while cable drawings are being revised) and tell you only when a status changes?
  - Suggested: yes, ending by itself at delivery.
  - Why: you hear about each step without asking, and nothing when nothing changes.
- The supplier asks `<question>` about `<their number> (<our number>)`. Send this answer? (draft)
  - Suggested: yes, today before `<local time>`.
  - Why: `<reason for the recommended option>`; after that time it costs a day.
- `<n>` of `<m>` production drawings are wrong (table). Send these revision notes? (drafts with pictures)
  - Suggested: yes, all in one round.
  - Why: each extra round costs at least a day on the longest lead time of the project.
- May I click Confirm on line `<n> (<our id>)` if every one of these conditions holds: `<the pass conditions>`?
  - Suggested: yes.
  - Why: the drawing matches field by field; Confirm starts its production.

## Done when

- [ ] The baseline exists and each later report lists only differences, each open step with its deadline in local time. Evidence: `ORDER_LOG.md`.
- [ ] Every supplier message has its draft, the user's go (or the standing OK), the sent copy read back, and answers only what was asked. Evidence: the question table, `orders/messages/`.
- [ ] Every production drawing has a filled `supplier_drawing_<id>.toml` and a verdict. Evidence: `orders/production_drawings/`, the `production_drawing_check` rows.
- [ ] All corrections went in one round; each note names both numbers and has one picture. Evidence: the notes as sent.
- [ ] Each Confirm has the user's permission, the pass conditions and a proof screenshot. Evidence: the log entry.
- [ ] The shipping plan is ticked after every payment. Evidence: `ORDER_PLAN.md`.
- [ ] The log has the timeline, the real lead times, the paid totals and the cause of every question. Evidence: the file.

## Outputs

- `orders/ORDER_LOG.md`: baseline, changes, questions and answers, drawing checks, landed cost, delivery
- `orders/production_drawings/`, `orders/messages/`, `out/cables/production/`
- `PROJECT_STATE.md`: order status, standing permissions, next action

## If something is missing

- No browser tool: the user pastes the status text and sends each drawing; the checks run the same way; the user clicks Revise and Confirm.
- A chat window sits in a frame that page text cannot read: watch it by zooming on its region.
- A site freezes screenshots: use page text and element search; drawing links and statuses can be read from the order page's data.

## Lessons behind this phase

- Half the question rounds on one case were caused by the customer's own extra sentences -> step 6.
- The only sign that a review had ended was a "payment failed" mail -> step 3: watch the page.
- A supplier confirmed several points by e-mail and only one reached the drawings -> step 10.
- Most of the production drawings were wrong, and were first read as a batch -> steps 13 and 14: field by field.
- A revised drawing arrived before any feedback had been sent and was nearly taken for the answer -> step 12: the drawing date.
- Two people at a supplier answered one question in two threads -> step 8.
- Typed text in a web mail arrived garbled -> step 9: read back before Send.

The full cases are in `references/lessons.md`.
