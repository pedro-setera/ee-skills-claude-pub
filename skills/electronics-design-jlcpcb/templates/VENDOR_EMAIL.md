# Vendor e-mail forms

The agent drafts these. **A message is sent by the user, or by the agent only after the user's go on that exact text;** afterwards the agent lists any deviation from the approved text.

## Rules for every message
1. **No product or board names.** Say "the board" and the order number if the thread needs it. No project or customer names.
2. **A picture**: one annotated image of the thing in question, saved as `out/order/<name>.png`.
3. **Every designator named.** Write "J1, J2" and not "the connectors".
4. **One topic per message.** A second topic is a second message.
5. Answer only what was asked. Do not volunteer new questions.
6. Few lines. Plain English. No apology or filler.
7. Never send a list of questions. Take the conservative side and say so in the order remark. One exception: the single pre-order question of `references/working-rules.md` section 9.
8. Reply in the existing thread, so the order stays linked.
9. Remove personal data from the picture and the text before it goes (scan it).

## Form 1: answer to an engineering question
```
Subject: <their subject line, unchanged>

Hello,

<Their question in one short line.>
Answer: <yes / no / the value>. <One line of reason.>
See the picture: <designators> are marked.

Thank you.
```
Worked example: "Question: pin 1 of U3 looks rotated. Answer: the placement is correct, pin 1 is at the dot in the picture. Please continue with the order."

## Form 2: withdrawal of an earlier instruction
Use when a decision changed after an instruction was sent. Send it in the same thread as the old one.
```
Subject: <same thread>

Hello,

Please ignore my earlier message of <date> about <topic>.
New instruction: <what to do now>, <designators>.
See the picture.

Thank you.
```
Worked example: "Please ignore my message about leaving R9 and C12 unfitted. Fit both. See the picture."

## Form 3: polite status nudge
Only when the supplier is past its own stated time (recorded in ORDER_LOG). Phase 14 asks the user once per order for a standing permission to send such short, polite nudges: with it, a nudge needs no fresh permission; without it, every nudge is drafted and shown first. Anything with a commercial effect always needs a fresh go.
```
Subject: <same thread>

Hello,

Order <no.> shows "<status>" since <date>. Is anything needed from my side?

Thank you.
```

## Checklist before sending
- [ ] One topic. [ ] Every designator named. [ ] Picture attached. [ ] No product or board names.
- [ ] No contradiction with the order form fields. [ ] Logged in ORDER_LOG (date, question, answer).
- [ ] Deadline noted: <date and time> (for a question with a time limit).
