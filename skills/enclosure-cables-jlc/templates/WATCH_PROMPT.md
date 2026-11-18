# Watch prompt (the text of the scheduled order check)

Offered in phase 13 and started only on the user's yes. Interval: every <4> hours; every 30 minutes only while cable production drawings are being revised (the lines return one by one and wait silently for a mail question), back to hours after the last Confirm. Fill the brackets, then use the text below as the task.

---

You are checking open orders for the project in `<project>/mech`. Read `<project>/mech/orders/ORDER_LOG.md` first: the baseline table, the line map, the standing OKs.

Rules:
1. Open each order page ONCE, at a person's pace. Orders: <label: page>, <label: page>. If the browser is not connected or the site shows a sign-in page, say so once and stop. Never sign in. Never type a password.
2. Read the status in the page's own words, the held parts or lines, and any message or drawing that is new. Read by page text; use a screenshot only when the text cannot be read.
3. Compare with the baseline. If nothing changed, write only the "Checked" time into the baseline and say nothing.
4. If something changed: update the baseline and the status-change table, and send ONE short notice: order label, old status, new status, what is needed from the user, and the deadline in local time from
   `python -I <skill folder>/scripts/supplier_calendar.py deadline --answer --at <ISO time of the change> --project <project>/mech`
   (for a payment step use `--pay`).
5. A new supplier question: open every attachment (a question may be only a picture, and a second mail may follow minutes later) and copy its exact text into the question table, with their number and ours from the line map. Draft nothing here; the main session drafts and shows it.
6. New production drawings: note each line's drawing date and its drawing status in the order-detail data (modify, wait_confirm, confirm; a new date folder in the PDF address is a new drawing); fetch nothing by clicking a download; the main session checks them field by field. Close the browser tab after each check.
7. Never click Pay, Confirm, Revise, Submit, Cancel, a terms box or a chat send. Never change an order.
8. An "automatic payment failed" or similar mail is not an alarm by itself: report what the order page shows.
9. End the watch by itself when every order shows delivered: write the delivery data into the log and say that the task can be deleted.

Report format (only when something changed):
```
<order label>: "<old status>" -> "<new status>".
Needed: <what, from whom>. Deadline: <local date and time>.
Log updated: <project>/mech/orders/ORDER_LOG.md
```

---

## Before starting it
- [ ] The user said yes to the watch. Their words, date: <>
- [ ] The interval is hours (30 minutes only during a cable drawing revision). [ ] It was run once by hand and the result shown to the user.
- [ ] The mailbox check, if wanted, is a separate opt-in: it reads only the suppliers' mails about these orders, drafts, and never sends.
- [ ] Recorded in the state file: the task's name, so that it can be deleted at delivery.
