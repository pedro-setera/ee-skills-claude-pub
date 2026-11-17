# The order flow: calendar, windows, and what the agent may click

**As read 2026-11; re-read the live page before every order.** Sources: three real orders at the group's shops (a
sheet-metal case, a set of custom cables, a board with parts). Used in phases 11, 12 and 13. Deadlines come from
`supplier_calendar.py`, never from memory.

## 1. The order calendar

The sequence that would have saved days on the first orders:

1. **Freeze.** The design and every choice of the user (routes, ends, cable types, colours, inks, wording) are
   fixed, and the full interconnect check is done, before any quote (SKILL.md rule 11). Gate 2 is passed.
2. **Boards**, if any travel with the cables: ordered with the parts shop's warehouse as their address
   (`shipping-and-combine.md`). The board order itself belongs to the electronics skill.
3. **Cables first.** They are the critical path: about 4 weeks from request to door. One length per harness that works
   at the design tolerance (+-5) with the standard (+-3) asked, cavity tables and pictures in the maker's format, each non-default as "X, NOT Y", every field
   read back. Record the line-to-cable map the moment the quote is ready.
4. **The case.** Chart names in every field, nothing else about colour or masking, a short remark that contradicts
   nothing, print layers in the ink colours, the ink sheet in the PDF and renders in the ZIP.
5. **The parts order, the same week** as the cables, combined with them.
6. **Answer every question the same supplier day,** only what is asked. Check the totals before paying. After each
   payment tick the shipping plan.
7. **Wait for the cable production drawings** and correct everything in one Revise round. Confirm line by line.

## 2. Supplier working hours

Defaults of `supplier_calendar.py` (as read 2026-11 for the group's shops; set others in `[supplier_hours]` of
`mech.toml` or read them from the capability sheet's `[hours]`):

| Key | Default | Meaning |
|---|---|---|
| `utc_offset` | 8 | The supplier's clock |
| `windows` | 09:30 to 12:00, 13:30 to 18:30 | Working windows |
| `weekdays` | Monday to Friday | Public holidays go into `holidays` |
| `submit_days` | Monday, Tuesday, Wednesday | A question round then still fits the same week |
| `answer_margin_min` | 60 | Answer at least this long before they close |
| `pay_margin_min` | 120 | Pay at least this long before they close |

One shop's quote page stated Monday to Saturday for quotes; answers were seen only in the hours above. A payment
after their evening started production a working day later (as read 2026-11 on one shop's ordering page: re-read).

## 3. The windows

| Step | Do it | Command |
|---|---|---|
| Submit a quote or an order for review | Monday to Wednesday, at least an hour BEFORE their morning opens, so it is first in the queue | `supplier_calendar.py submit-window` |
| Answer a question | The same supplier day, before their close minus the margin | `supplier_calendar.py deadline --answer --at <when it came>` |
| Pay | Before their evening minus the margin | `supplier_calendar.py deadline --pay` |
| Nudge a silent quote | Once, after two business days, timed to land before their morning | `supplier_calendar.py now` |
| The whole plan | A table with the latest local time per step | `supplier_calendar.py plan --steps plan.toml` |

- **Plan one supplier working day per question round.** Promised times on pages and in chats did not hold.
- **Friday work waits for Monday.** A request sent at the weekend waited for their working week. Drawings finished on
  a Friday were released on Monday.
- "It is Friday evening; I will submit anyway" gains nothing and risks a weekend-old question. Hold it, tell the
  user why, and give the Monday time.

## 4. What the agent may do, and where it stops

The user signs in. Then, in phase 12:

| The agent may | The agent stops and hands over |
|---|---|
| Open the quote form; upload the frozen files; set every field from the field sheet | Sign-in, passwords, one-time codes |
| Read every field back and compare with the field sheet (`cable_fieldsheet.py --readback`) | "Submit for Final Quotation" and any final submit, unless the user said in this session to submit this exact cart |
| Name each item with our part number | Any terms, consent or compliance-statement box |
| Save screens of the cart, the quote, the totals into `mech/orders/` | "Secure Checkout", "Submit Order", "Pay", card or wallet data |
| Read the order page, the line statuses and the drawing PDFs (by direct link) | Confirm on a production drawing |
| Show the shipping options and the totals | Sending an e-mail, a chat line or a Revise note the user has not seen (a standing OK per order counts, recorded in the state file) |
| Prepare the combine and the shipping line for the user to see | Choosing the address |

If a click is blocked by the tool's safety system (it was, at a checkout button on one shop), **stop there**. Tell the
user what is ready and what they must click. Never look for a way around a blocked click.

Never ask the supplier what its site already says (the FAQ, the checkout). Never send a question list
(SKILL.md rule 17).

## 5. Field sheets and read-back

- Every form value comes from the field sheet (`cable_fieldsheet.py` for cables; the sheet-metal field sheet from
  the template for the case). No value is typed from memory (SKILL.md rule 3).
- After typing: read the page's own text of every field and compare. Paste it into a file and run the read-back.
  A field that "did not take" is found here, not on the production drawing.
- Record the supplier's line numbers against our part numbers when the quote is ready. Put the map into the order
  log and the state file.

## 6. Browser tool mechanics learned

- The browser extension must be connected with the same account as the session. Each shop may need its own sign-in.
- **File uploads read only the session's own folders.** Copy the upload set into a folder of the session first (the
  project's `mech/out/upload/<supplier>/` when the project is the session's folder).
- **An upload call has a size limit** (about 10 MB per call was seen): attach large files one call at a time. A
  webmail attachment limit (25 MB per mail was seen) applies to answers with files.
- **A page that freezes screenshots is read as text** (page text or find). A zoom of a region may still work when
  the full screenshot does not. A chat inside a frame that page text cannot read is watched by zoom.
- **Read typed text back before sending.** A webmail editor garbled typed text once. Read the body and the
  attachment list from the page's own text, not from a screenshot; clear and retype if needed.
- **Downloads by direct link only** (SKILL.md rule 21): take the PDF's address from the page or the order data and
  fetch it with a command; never click a download button (a save dialog opens that nobody can answer).
- Work at a human pace on supplier sites: one session, no bursts, stop at the first refusal or bot check.
- A bent part shows "manual quote" for up to two minutes after upload. Wait; do not upload again.

## 7. Ending phase 12

The order log holds: the order and quote numbers, the line map, every total with its screen, the shipping plan with
ticks, the deadline of the next step in the supplier's time and the user's. Then phase 13 (`after-order.md`).
