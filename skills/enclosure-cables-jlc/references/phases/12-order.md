# Phase 12: quotes and orders

Fill each supplier's form from the field sheet, read every field back, record the supplier's line numbers against ours, check the totals three times, and stop at the payment page for the user.

## Inputs

- The frozen revision with its checksums; gate 2 approved, or skipped with the user's words recorded.
- `orders/ORDER_PLAN.md`, `orders/ORDERING_CHECKLIST.md`, `orders/ORDER_LOG.md`, `orders/FIELD_SHEET_enclosure.md`, `orders/REMARK_<part>.md`, `out/cables/FIELD_SHEET_cables.md`, `out/upload/<supplier>/`.
- `references/suppliers/order-flow.md` (each site step by step, dated; re-read the live page as you go), `lcsc-cable.md`, `jlccnc-sheet-metal.md`, `shipping-and-combine.md`; `references/working-rules.md`, `references/tools.md`.
- `scripts/cable_fieldsheet.py` (`--readback`), `scripts/supplier_calendar.py`; a browser the user has signed in to.

## Steps

The sites themselves (field names, where a file attaches, what a status means) are described in `references/suppliers/order-flow.md`. This file holds the procedure around them. Work at a person's pace: one session, no bursts, stop at the first refusal.

1. **Check the preconditions.** The files in the upload folder hash to the frozen checksums. The capability sheets were re-read by an independent agent this week (phase 10). The order plan is decided and today is inside a submit window: `python -I <skill folder>/scripts/supplier_calendar.py now --project <project>/mech`. The user is reachable for sign-in, choices and payment. Requests sent at the weekend or at the supplier's night wait for their next working morning.
2. **Hand-over: sign-in and browser.** The user signs in to each site (a cable site may need its own sign-in); you never type a password. Test that your browser tool can attach a file before the first upload. Uploads read only folders the tool may see: copy the upload set there first. If the tool cannot attach, the user clicks each upload button: give the folder and the file names in order.
3. **Cables first: enter each cable from the field sheet.** One cart item per cable. Forms for coax and network cables may hold only drawings, a requirements field and a quantity (as read 2026-11; re-read), so their quote lines read generic: judge those cables only on the production drawing. Name the item with our cable number and name. Put each non-default first in the requirements field as "X, NOT Y", then "CUST P/N: `<our id>`", and nothing else. Upload the drawing and the pin-map and orientation pictures with the quote, not in a later e-mail: an orientation picture sent afterwards cost an e-mail round, while the same picture was understood in a quarter of an hour.
4. **Read back every field of every cart item** before the quote is requested. Copy what the page shows into a text file and run
   `python -I <skill folder>/scripts/cable_fieldsheet.py --project <project>/mech --readback <pasted.txt>`
   A length field once did not take at the first try, and a gauge that was right in the form was drawn differently later; only the read-back shows the first kind. Click by element, never by screen coordinates.
5. **Request the cable quote on the user's go.** Show the cart summary; the request is the user's click, or yours after their go on that exact cart, because a submitted quote cannot be edited. It asks for a quote only; it is not a payment.
6. **Record the line map the moment the quote is ready.** The supplier numbers the lines itself; the entry order does not fix them. Fill the line map table of `ORDER_LOG.md`: supplier line, our cable id, quantity, price. On one order "cable 4" in a supplier's question meant their line 4, which was another cable; the answer was applied to the wrong one, a multi-wire harness, and found only at the drawings. From now on every message writes both: "line 4 (`<our id>`)".
7. **The case: upload part by part from the field sheet.** Material, thickness as the form reads it, finish, the SAME chart name in every coated part's finish field, the print option and its file, hardware, quantity, product description, the remark pasted from `orders/REMARK_<part>.md` word for word. Where a PDF has no field of its own, the PDF inside the part's archive reaches the reviewer (as read 2026-11; re-read). A bent part may show "manual quote" for a minute or two after upload: that is normal.
8. **Read back every field of every part** into the "seen" slots of `ORDERING_CHECKLIST.md` and save a screenshot per part in `orders/screens/`. Read every box on the page, also those you did not touch.
9. **Submit the case for review on the user's go,** inside the submit window. Each part has its own reviewer and the order waits for the slowest part. The supplier may send no "review completed" message: start the watch of phase 13 and come back when the pay step opens. "Submit" is not payment.
10. **Place the loose-parts order the same week** and join it to the combined parcel as the plan says. Tick it in `ORDER_PLAN.md`.
11. **Shipping, address, combine.** Show the shipping options as a table (method, days, price, who pays the duties), the suggested one first. The address is a preset of the account or typed by the user. Set the destination and the combine option exactly as the plan says; the page's own re-priced shipping or "combined orders" view is the proof: save that screen, and do not e-mail to confirm it. Repeat the destination to the user in plain words.
12. **Read the total three times:** at the quote, after the review, and again at the pay step. Write all three in the totals table of `ORDER_LOG.md` with the parts of each (parts, shipping, duties, discount). On one order the total rose clearly between review and payment (shipping and duties were re-priced); nobody had read it again. Check the coupons the page offers and report which one saves most.
13. **Do not write to the supplier in this phase** unless they asked something. No "just to confirm" message; nothing that their page, their help pages or the checkout already says. A question about combining orders took three days to get a yes that the checkout had already shown.
14. **Hand-over: consent boxes.** Terms, compliance and consent boxes are the user's. Name each one; tell the user when one arrives ticked.
15. **Hand-over: stop at the payment page.** Send the summary: per order the items, quantities, the line map, shipping method, destination in plain words, the total with its parts against the estimate, the pay-by time (`python -I <skill folder>/scripts/supplier_calendar.py deadline --pay --project <project>/mech`), and the evidence status (gates evidenced, gates skipped, checks that could not run). Card data, the final submit and the payment click are theirs. If a tool refuses a click such as checkout, do not look for another way: give the user the click list and the expected total.
16. **After the user says it is paid, verify and record.** Read the status on the order page (not an automatic e-mail), save a screenshot, record references, date and the paid total with its parts in `ORDER_LOG.md` and the state file, and say why it differs from the estimate. Set gate 3 for that order.
17. **After each payment, re-read the whole shipping plan and tick what is done.** Say what is next and its deadline.
18. **If the site shows an error, stop.** Do not retry blindly and do not submit twice. Read what the site saved, tell the user, and prefer a clean new entry to a half-saved one.

## Questions for the user

- Ship to the address preset `<label>` of your account?
  - Suggested: yes.
  - Why: it is the account's default; please check that it is current.
- Which shipping line? (table)
  - Suggested: the fastest at a fair price with duties prepaid, where offered.
  - Why: no bill at the door and fewer customs delays.
- The cart is complete and read back (summary). May I request the quote? It cannot be edited afterwards.
  - Suggested: yes.
  - Why: every field equals the field sheet; today is inside their working week.
- The page needs the box `<label>` ticked to continue. Will you tick it?
  - Suggested: yes, you tick it.
  - Why: consent boxes are yours; I go on as soon as it is done.

## Gate 3 checklist

- [ ] The uploaded files hash to the frozen checksums. Evidence: the hashes taken just before the upload.
- [ ] Every field of every item reads back as the field sheet says. Evidence: the `cable_readback` rows; the "seen" and "proof" slots of `ORDERING_CHECKLIST.md`.
- [ ] Every item is named with our part number, and the pictures went up with the quote. Evidence: the cart screenshots.
- [ ] The line map is recorded. Evidence: the table in `ORDER_LOG.md`, dated at the quote.
- [ ] The total was read at quote, review and pay step, and each change is explained or flagged. Evidence: the totals table.
- [ ] The destination and the combine setting equal the plan, with the proof screen saved. Evidence: `orders/screens/`.
- [ ] The agent stopped at the payment page; every consent box is listed with who ticked it. Evidence: the log entry.
- [ ] After payment the status was read on the page and the shipping plan was re-read and ticked. Evidence: the screenshot; `ORDER_PLAN.md`.

## Outputs

- `orders/ORDER_LOG.md`: references, line map, totals at three steps, landed cost (private data stays in this project file)
- `orders/ORDERING_CHECKLIST.md`, every box ticked or "not applicable: reason"; `orders/screens/`
- `PROJECT_STATE.md`: gate 3 per order, open orders with their deadlines, the standing OKs

## If something is missing

- No browser tool: the user types each form from the field sheet and pastes back what the page shows; the read-back and the totals check are done on the pasted text.
- A site freezes screenshots: read it by page text or by finding elements; a zoom of a region may still work.
- A file is too large for one upload call: attach files one call at a time, within the limits on the capability sheet.
- CNC parts or outside printing: the same procedure; their order flow is **not proven by an order**, so read each page slowly and expect questions.

## Lessons behind this phase

- A supplier's "cable 4" was their line 4, another cable; the answer changed the wrong harness -> step 6: the line map.
- A form field did not take its value at the first try -> step 4: read back every field.
- The total rose clearly between review and payment and nobody read it again -> step 12.
- An e-mail asked what the checkout already showed and took three days to be answered -> step 13.
- A tool refused the checkout click; the user finished with a short click list -> step 15: never work around it.
- A picture sent after the quote cost an extra round -> step 3: pictures with the quote.

The full cases are in `references/lessons.md`.
