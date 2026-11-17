# Phase 13: order at JLCPCB

Fill the JLCPCB order from the frozen folder, read every option back, check the placement preview, and stop at the order summary or the payment page for the user.

## Inputs

- The frozen upload folder `out/jlc/` (and `out/panel/`) with its checksums in `PROJECT_STATE.md`.
- `ORDERING_CHECKLIST.md`, the shipping plan and the lessons section of `ORDER_LOG.md`.
- `references/jlcpcb/order-flow.md` (the site step by step, dated; re-read the live page as you go), `references/jlcpcb/assembly.md`, `references/jlcpcb/combined-shipping.md`.
- `scripts/jlc_parts.py`; a browser the user has signed in to; `templates/ORDER_LOG.md`.
- `references/lessons.md`, section "Phase 13: order at JLCPCB".

## Steps

The site itself (field names, what to set, what to read back, the pitfalls met) is described only in `references/jlcpcb/order-flow.md`, steps 1 to 21; the step numbers in brackets below point there. This file holds the procedure around it: preconditions, hand-overs to the user, what to verify and what to record.

Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8).

1. **Check the preconditions** (`order-flow.md` section 2). Gate 2 is approved, or skipped by the user with their words recorded. The files in the upload folder hash to the checksums of the files that were checked, and come from the tool that holds the master (the user's own tool for an imported design that was only reviewed; the user's own files when they brought production files). The supplier-rules review is closed. The stock check of today passes (`scripts/jlc_parts.py bom-check`). The shipping plan is decided. The user is reachable for sign-in, choices and payment.
2. **Hand-over: sign-in and browser.** The user signs in; you never type a password. Test that your browser tool can attach a file to an upload field before the first upload. If it cannot, the user clicks each upload button: give the folder path and the file names in order. Say at once when the tool is down.
3. **Ask the quantity** (next section) before the first page, unless the user has already stated it: it sets the stock need and the price.
4. **Upload and verify the board** (step 1). Compare the detected size and layer count with the board (for the user's own production files, with the fab notes) and save a screenshot in `out/order/`. A difference means a wrong or broken file: stop.
5. **Set and read back the board options** (steps 2 to 5) from the checklist. Click by element reference, never by screen coordinates. After each group write the values the page shows in the "seen" slots of the checklist. Via covering: as the order form offers it for this layer count on the day (tented or plugged); never untented by accident. Where the form does not offer the option the checklist names, take another only if price and function are the same, and say so; otherwise stop and ask the user.
6. **Hand-over: consent boxes** (step 6). Read every box on the page, also those you did not touch. Terms, consent and compliance boxes are the user's: do not tick or untick them, and tell the user when one arrives ticked. If the page needs one to continue, name it: they tick it, or they name the box and tell you to.
7. **Set the assembly and upload its files** (steps 7 and 8) as the checklist says, with the parts-placement confirmation on: it gives the check of phase 14. Record the assembly type the order landed in and the line and placement counts the page parsed.
8. **Verify the BOM page line by line** (steps 9 and 10) against the frozen BOM: every line selected, each matched to the intended LCSC number, the designator count per line. Copy the exact reason of every warning into `ORDER_LOG.md`. A shortfall or a proposed substitute stops the order and goes to the user.
9. **Verify the placement preview** (step 11): the whole board, then strip by strip, top and bottom, against the "what to see" line of the checklist for every polarised part; unfitted and hand-fit parts absent. Save a zoomed crop of each strip in `out/order/crops/` and say where you are ("strip 7 of 15, no finding"). For the user's own production files every polarised part is UNKNOWN until seen here. A wrong rotation or polarity, or a wrong part (its change needs the user's go first), sends the work back to phase 12 (a change of the board file goes through gate 2 again, as its opening says): correct the source (for the user's own files, through the change list), re-run the rotation test where there is a board, export again, have the supplier-rules reviewer close it on the new files, write the new checksums into the checklist, and tell the user. Then the order starts again. A fix made only in the viewer leaves the frozen files wrong.
9b. **Bottom side** (two-sided assembly): its convention was confirmed before gate 2 by the preview-only upload of phase 11 step 14b; step 9 looks at both sides like every other part.
10. **Enter the remark and the customs description** (steps 12 to 14): the remark from the fab notes, word for word; a generic customs description with no product or board name. Ask the user if none fits.
11. **Read the cart** (step 15) against the checklist and the estimate.
12. **Coupons and shipping** (steps 16 and 17): apply the coupon with the biggest saving and report which it was; show the shipping options as a table, the cheapest that meets the user's date suggested first, and ask (next section).
13. **Hand-over: address** (step 18). Use an address preset of the account, or let the user type it; never type personal data or edit the address book. With combined shipping the destination is the collection warehouse of the plan, set now. Repeat the destination to the user in plain words.
14. **Hand-over: stop at the order summary or the payment page** (steps 19 and 20). The button that creates the order ("Submit Order", "Place order"), paid or not, is the user's: where it comes before the payment page, stop at the summary before it. Send the summary: the option table, quantity, BOM lines and warnings with their reasons, coupon, shipping method, destination in plain words, the landed total with its parts (parts, assembly, fees, shipping, duties) against the cost target, any fee of the payment method, and the cut-off time if one applies. Add the evidence status of the checklist: which gates are evidenced, which were skipped (with the user's words and date), and what was not checked ("manufacturing check only", "import not verified"). Notify the user and check that the notice arrived. Card data and the payment click are theirs. If the tool refuses a click such as checkout, do not look for another way: give the user the click list (`order-flow.md` step 20) and the expected total, and guide them. If the submitted order goes into the manufacturer's file review before it can be paid (`order-flow.md` section 4), start the watch of phase 14 and tell the user when the pay button appears.
15. **After the user says it is paid, verify and record** (step 21). Read the status on the order page, not an automatic e-mail, and save a screenshot in `out/order/`. Record in `ORDER_LOG.md` and the state file: the order references, date, options, shipping choice and the landed total with its parts. Compare it with the estimate of phase 12 and say why it differs. Set gate 3.
16. **Prepare the other orders of the shipping plan** in the planned sequence, the joining order last, each up to the hand-over of step 14 (the user submits and pays), and check on its page that the orders are linked (`references/jlcpcb/combined-shipping.md`).
17. **If the site shows an error at any step, stop.** Do not retry blindly and do not submit twice. Read what the site has saved, tell the user, and prefer a clean new submission to editing a half-saved one.

## Questions for the user

Ask in everyday words: say what a choice means for the order and its cost rather than naming the technique, explain any technical word in a few words the first time, and give the suggested answer with a reason a non-engineer can weigh (`references/working-rules.md` section 1).

- How many boards, and how many of them assembled? (only if the user has not said)
  - Suggested: 5 boards, 2 assembled.
  - Why: 5 is the usual minimum; first samples are for testing, and bare spare boards cost little.
- Which shipping method? (table: method, days, price, duty terms)
  - Suggested: `<the cheapest that arrives by your date, with taxes and duties prepaid where offered>`.
  - Why: it meets your date at the lowest cost; prepaid duties mean no bill at delivery and fewer customs delays.
- Ship to the address preset `<label>` of your account?
  - Suggested: yes.
  - Why: it is the one the account shows as default; please check that it is current.
- (Only if no generic text fits) Which customs description should the parcel carry?
  - Suggested: `<a generic description and its code, with no product or board name>`.
  - Why: the declaration is made in your name.
- The page needs the box `<label>` ticked to continue. Will you tick it?
  - Suggested: yes, you tick it.
  - Why: consent boxes are yours; I continue as soon as it is done.

## Checks before leaving this phase

- [ ] The files uploaded hash to the checksums of the files that were checked. Evidence: the hashes taken just before the upload against the `frozen:` block (or `source:` for the user's own files).
- [ ] The detected size and layer count on the page equal the board's. Evidence: a screenshot in `out/order/`.
- [ ] Every option reads back as wanted. Evidence: the "seen" and "proof" slots of `ORDERING_CHECKLIST.md`, all filled.
- [ ] The BOM page shows as many selected lines as the frozen BOM has, and each warning's reason is written down. Evidence: the line counts and the warning texts in `ORDER_LOG.md`.
- [ ] Every preview strip of both sides was looked at, and every polarised part passed. Evidence: the crops in `out/order/crops/`, the ticked preview section of the checklist.
- [ ] The stock report is dated today. Evidence: `out/BOM_STOCK_CHECK.md`.
- [ ] The summary went to the user with the total's parts, the destination and the evidence status; quantity and shipping choice are recorded. Evidence: the summary text, the decision rows with the user's words.
- [ ] The agent stopped at the order summary or the payment page, the user pressed the button that created the order, and every consent box is listed with who ticked it. Evidence: the log entry and its screenshot.
- [ ] After payment the order status was read and recorded. Evidence: the status screenshot; references and landed total in `ORDER_LOG.md` and the state file.

## Outputs

- `ORDER_LOG.md`: the order entry with the options, the BOM and preview results, the landed cost and the references (private data stays in this project file)
- `out/order/`: screenshots of the read-back, the summary and the status; `out/order/crops/`: the preview strips
- `out/BOM_STOCK_CHECK.md` of the order day
- `ORDERING_CHECKLIST.md` with every box ticked or answered "not applicable" with its reason; `PROJECT_STATE.md` with gate 3 and the order entry

## Lessons behind this phase

- A click by screen coordinates selected the wrong via option; the read-back caught it -> step 5 clicks by element and reads every value back.
- The BOM page warned that some lines had no part selected: one connector's row was unticked. The next warning looked the same and was a fee of a few cents -> step 8 compares the page with the BOM line by line and reads the exact reason of each warning.
- The agent's browser could not attach files, found only when the first upload was due -> step 2 tests it first.
- A tool refused the checkout click on one order; the agent gave the user four steps and the expected total, and the user finished the order -> step 14.
- A box for the assembly terms arrived ticked by default -> step 6 reads every box and leaves consent to the user.
- The destination had been set to a collection warehouse but was not in the summary; the user had to ask -> steps 13 and 14 state the destination in plain words.
- The total grew by a quarter at payment because a faster shipping method was chosen there -> step 15 records the landed total and the reason.
- A supplier's form failed with an error while a submitted request was being edited, and sent nothing; the user chose to cancel it and submit a fresh one -> step 17.

The full cases are in `references/lessons.md`.
