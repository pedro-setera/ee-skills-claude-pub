# Watch prompt: order status check

This is the text for the scheduled task. Create it only with the user's agreement. Schedule: every 4 hours, with an automatic end date set to <delivery estimate plus 7 days>. Fill the angle brackets before scheduling.

Needs: the browser extension the user enabled, and the user already signed in to the supplier site in that browser.

## Order check (paste as the task text)
```
You are watching one order on behalf of the user. Read only. Change nothing on the site.

1. Read <project folder>/ORDER_LOG.md. The Baseline table lists the open orders with their last known status.
2. Open the supplier's order page for each open order through the browser tool the user enabled:
   <order list page URL>. Read the status text exactly as shown.
   Human pace: one session, no bursts, stop at the first refusal (<skill folder>/references/working-rules.md section 8).
   One page load per order page per check, no reloads; at a refusal or captcha, say so once and stop.
3. If the browser is not connected, or the page asks to sign in:
   say so once in your result ("browser not connected" or "signed out"), and stop.
   Never sign in. Never retry the sign-in. Never type a password or code.
4. Compare each status with the baseline.
   - If nothing changed: update only the "Checked" column in the baseline. Send nothing.
   - If the main status changed: update the baseline row (Status, Last change, Checked),
     add a line to "Status changes", and send ONE push notification:
     "<board name>: order <last 4 characters> is now <new status>". Then check that the push was delivered where the tool allows it.
   - If the page shows a question from the supplier, a deadline, or a placement confirmation request:
     put it in "Supplier questions" and send ONE push marked "needs you". Do not answer.
5. Never click confirm, pay, accept, replace or cancel. Never send any message or e-mail from this task:
   messages go out in a session, after the user's go (phase 14). Never change an order.
6. End with one line: what changed, or "no change".
```

## Optional hourly mailbox variant (only if the user agreed)
```
You are watching the user's mailbox for supplier mail about open orders. Read only.

1. Read <project folder>/ORDER_LOG.md for the open order numbers.
2. Search for new mail from <supplier sender domain> that mentions an open order number.
   Read only those mails. Ignore every other mail and never open attachments from others.
3. For each such mail: add a line to "Supplier questions" with date, their question and any deadline.
   Prepare a draft answer in <project folder>/out/order/draft_<date>.md using the forms in VENDOR_EMAIL.md.
   Never send, reply, forward or delete.
4. If a mail has a deadline within 72 hours, send ONE push marked "needs you" with the deadline.
5. If the mailbox is not connected or asks to sign in: say so once and stop.
6. End with one line: new supplier mails and drafts prepared, or "no new mail".
```

## After scheduling
- Test the task once by hand and show the user the result and the push.
- Record the task name, schedule and end date in PROJECT_STATE (Log).
- After a PC restart the browser extension may need reconnecting: the task will say "browser not connected" once. Tell the user.
- Pause the task while a session works on the same supplier site; resume it afterwards.
- Delete the task when the boards have shipped to the user (phase 14, step 17) or the user says stop.
