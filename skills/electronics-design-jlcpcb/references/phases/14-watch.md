# Phase 14: order and e-mail watch

Watch the order and the mailbox until the boards ship, answer the manufacturer fast and exactly, and treat the placement confirmation as a real check.

A pending placement confirmation or engineering question starts at once at its own step (6 or 7), after the intake below when the order was placed outside this skill; the baseline and the watch offers (steps 1 to 4) follow afterwards.

## Inputs

- `ORDER_LOG.md` with the order references, the options and the shipping plan (private data stays in that file).
- The frozen upload folder, `ORDERING_CHECKLIST.md`, the rotation table, the BOM with its DNP and hand-fit lists; for an order placed outside this skill, the files of the intake below.
- `references/jlcpcb/after-order.md` (order states, the replace function, confirmation, hold, chat, days between steps; dated, re-read the live pages), `references/jlcpcb/combined-shipping.md`.
- `scripts/status_diff.py`, `templates/WATCH_PROMPT.md`, `templates/VENDOR_EMAIL.md`.
- A browser the user has signed in to. Scheduling, push and mailbox tools if they exist (`references/tools.md`).
- `references/lessons.md`, section "Phase 14: order and e-mail watch".

## Steps

**An order placed outside this skill** (`references/existing-designs.md` section 4): ask the user for the exact BOM, placement file and Gerbers that were uploaded, from their own copy (the order page offers them only as browser downloads, which this skill does not click), and a polarity reference (the assembly drawing or the board file). Copy them into the project and record their checksums. Without them "right part, right polarity" is UNKNOWN: do not click confirm; report what the viewer shows, with the crops, and the user confirms.

1. **Take a baseline.** Open every order page and fill the baseline table of `ORDER_LOG.md`: order, status as the page words it, ships to, last change. The scheduled task reads and updates this table, so it is the one baseline (`scripts/status_diff.py` only helps a check by hand). From now on report only changes; when nothing changed, say nothing.
2. **Offer the watch** (next section). The order check runs every 4 hours as a scheduled task whose text is `templates/WATCH_PROMPT.md`; it sends one push when the main status changes, and ends by itself. The interval is hours, never minutes, and each check loads each order page once. Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8). If the browser is not connected or the user is signed out, it says so once and stops; it never tries to sign in. Run it once by hand and show the user the result. Pause it while a session works on the same site (another order, step 6, step 11) and resume it afterwards: one session on a supplier's site at a time.
3. **Offer the mailbox check, opt-in, hourly.** It reads only the manufacturer's mails about the open orders, prepares drafts and never sends. Anything with a deadline gets a push.
4. **Check that each push arrived,** where the tool shows delivery. "Sent" is not "delivered": a channel once failed silently.
5. **Know the rhythm, and promise nothing.** As seen on recent orders (dated in `references/jlcpcb/after-order.md`, section 9): the first engineering question and the placement confirmation request came between the day of payment and 4 days after; plan 3 to 4 days from payment to settled production of assembled boards. "In production" may at first mean only that the order was accepted while the data is still being prepared. Each question round costs about a working day in the manufacturer's time zone. Pass their own time statements on as "the manufacturer says", never as a date.
6. **Confirm the parts placement as a full check.** When the request arrives, a clock runs (72 hours as read in 2026-11; after that the order is built as it is). Start at once, in a session the user can follow. Without a browser tool: ask the user for a screenshot of each strip of the preview, check them the same way against the files, and the user clicks to confirm.
   - Ask permission to click confirm once per order, with written pass conditions: every part is the right one in the right place; every pin 1 and polarity is right; every DNP and hand-fit part is unplaced; nothing is missing or extra; every change by the assembler is harmless. Otherwise you report and do not click. You accept nothing else on that page: no terms, no payment, no options.
   - Work in this order: the overview; every strip of the top side; every strip of the bottom side; the 3D view. For each part: designator, LCSC number, position, pin 1, polarity. Save a crop per strip and say where you are.
   - Open the list of items the assembler revised. An IC turned by 90 degrees to fit their library is normal; verify that pin 1 still lands on pad 1 of the footprint.
   - Do not assume that an e-mailed instruction reached the placement team. Look for its effect in the viewer.
   - All conditions met and permission given: click confirm, take a screenshot of the new status as proof, record both. Otherwise send the user the crops and a short draft message.
7. **Answer engineering questions the same day.** To the user: three or four lines (what they ask, why, what follows from each option), one recommendation with its reason, a ready draft from `templates/VENDOR_EMAIL.md`, and one yes or no. In the draft, name every designator and both LCSC numbers when a part changes, and say what stays as it is ("leave only R`<n>` unfitted; all other designators of that line are assembled as usual"). Answer only what was asked, in the same thread.
8. **Nothing goes out without the user's go.** You draft. The message is sent by the user, or by you only after the user's go on that exact text (status nudges: step 11). Afterwards check that it is in the sent folder and list every deviation from the approved text.
9. **When a decision changes, withdraw the old instruction in the same thread, at once and in plain words.** Two instructions that contradict each other put an order on hold for a day. If the user prefers to leave the old one standing, say that this risk exists. For an order on hold, one short message is enough: the decision, and "please release the order to production".
10. **Treat late part changes as slow and uncertain.** The replace function for a BOM line disappears once the order is in production, and a shared line can only change as a whole (`references/jlcpcb/after-order.md`, sections 4 and 10). When the user can rework by hand, prefer a step 0 in the bring-up plan, and write the fallback down.
11. **Use the support chat for a stalled review.** Have the order references ready before opening it. Open the chat and the order pages one at a time, at a person's pace. One topic per message; polite and short; keep the chat open and watch for the reply. Expect a promise without a date. Ask the user once per order for a standing permission to send short, polite status nudges when the supplier is past its own stated time, and record it in the state file. With it, a nudge needs no fresh permission. Without it, every nudge is drafted and shown first. Anything with a commercial effect (a change, a cancellation, a fee, an upgrade) always needs a fresh go.
12. **Write supplier messages without product or board names.** Say "the board" and name the designators; "End A / End B" only for cables. A picture where geometry matters, a few short lines, and attachments copied to a folder the browser can read.
13. **Check before raising an alarm.** An automatic "payment failed" mail once arrived an hour before the payment went through. Read the order page first. Report price changes after a review with the old and new total.
14. **Follow the combined shipment.** Check on the joining order's page that the orders are linked. If the page shows no link, ask the supplier to confirm in writing (a draft for the user). Act on the fallback dates of the plan.
15. **Use the waiting time for phase 15:** write `FIRST_POWER_UP.md` before the boards arrive, with its review where phase 15 step 6 calls for it.
16. **Keep the order log.** Every status change, question, answer and date goes into `ORDER_LOG.md`. When the order has shipped, fill "Lessons for the next order": each question the supplier asked and the form field, file or remark that caused it, and how long each step took. Read that section before the next order. Propose to the user what is general enough for `references/lessons.md`; never add it silently.
17. **Close the watch** when the boards have shipped to the user (with combined shipping, the joined parcel): record the delivery data in `ORDER_LOG.md`, delete the scheduled task, tell the user in one line.

## Questions for the user

- Shall I check the order page every 4 hours and push you only when the main status changes?
  - Suggested: yes, until the boards have shipped to you.
  - Why: you hear about each step without asking, and nothing when nothing changes.
- Shall I also check your mailbox every hour for the manufacturer's mails and prepare draft answers (never sent)?
  - Suggested: yes.
  - Why: the placement confirmation has a 72-hour clock, and each late answer costs a working day.
- May I click Confirm on the placement page if every one of these conditions holds: `<the pass conditions>`?
  - Suggested: yes.
  - Why: the clock runs; I keep a crop of every strip and a screenshot of the result.
- For this order, may I send short, polite status nudges in your name when the manufacturer is past its own stated time?
  - Suggested: yes.
  - Why: low risk; without it I show you each nudge first; anything that changes the order still comes to you first.
- The manufacturer asks `<question>`. Send this answer (draft attached)?
  - Suggested: yes.
  - Why: `<the reason for the recommended option>`.

## Checks before leaving this phase

- [ ] The baseline table exists, and each later report lists only differences. Evidence: the baseline and status-change tables of `ORDER_LOG.md`.
- [ ] Each push has delivery evidence, or the note that this tool cannot show delivery. Evidence: the note column of the status-change table.
- [ ] The placement confirmation was a full check with permission and proof. Evidence: a crop per strip of both sides in `out/order/crops/`, the revised-items list with the pad check of each, the user's words, the proof screenshot.
- [ ] Each supplier message has its draft, the user's go, the sent copy and the list of deviations. Evidence: the question table of `ORDER_LOG.md`, the drafts in `out/order/`.
- [ ] No two active instructions to the supplier contradict each other. Evidence: the list of instructions, each marked active or withdrawn.
- [ ] `ORDER_LOG.md` has the timeline and the lessons section. Evidence: the file.
- [ ] The scheduled task is deleted; the shipped status and the delivery data are recorded. Evidence: the task list, the delivery table.

## Outputs

- `ORDER_LOG.md`: baseline, status changes, questions and answers, placement confirmation, landed cost, delivery, lessons
- `out/order/`: drafts, pictures for messages; `out/order/crops/`: the placement crops and the proof screenshot
- `PROJECT_STATE.md`: order status, standing permissions, next action phase 15

## Lessons behind this phase

- A decision changed and the earlier request was left standing; the manufacturer held the order to ask which one applied: a day lost -> step 9.
- The assembler turned one IC by 90 degrees against the submitted file; it was right for their library -> step 6 verifies each revised item against the pads.
- A value change asked for by e-mail had not reached the placement team: the old value was still in the viewer -> step 6 looks for the effect of every instruction.
- The user watched a silent screen during a long viewer check and could not tell whether the agent was still working -> step 6 says where it is, strip by strip.
- The agent asked more than once whether it might nudge a supplier that was already past its own time -> step 11 asks once for a standing permission.
- One reply answered about two parts at once and mixed their names; it cost another question round -> steps 7 and 11: one topic, the supplier's own references.
- A notification was "sent" and never arrived -> step 4.
- Time statements such as "two to three hours" or "today" are estimates -> step 5 never turns them into promises.

The full cases are in `references/lessons.md`.
