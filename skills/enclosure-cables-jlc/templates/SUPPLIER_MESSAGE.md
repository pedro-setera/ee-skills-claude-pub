# Messages to a supplier

The agent drafts. **A message is shown to the user before it goes,** unless a standing OK for that order is recorded in the state file. Afterwards the agent reads the sent text back from the page and lists any difference from the approved text.

## Rules for every message
1. **Answer only what was asked,** for that part or line only. No second topic, no new question, no "just to confirm".
2. **Same thread.** Their subject line unchanged.
3. **Their words and their numbers, with ours:** "line 2 (CAB-01)", "part 2 (P-02)". The order number and the part number on every line.
4. **Short numbered lines** in simple English. A correction is written "X, NOT Y".
5. **One picture** that shows the thing in question, with the same numbers on it.
6. **No product, board or project names.** End A / End B, P1 / P2, part numbers.
7. **Chart names only** for colours and inks. Nothing the capability sheet does not offer.
8. **A question about artwork is answered with corrected files** (print file, ink sheet, render), not with text.
9. **Never ask what their site, help pages or checkout already say.** Never send a list of questions.
10. Do not write on their Friday evening or weekend and expect an answer; send it to land before their morning.

## Form 1: answer to a question
```
Subject: <their subject line, unchanged>

Hello,

Order <no.>, <their number> (<our number>):
1. <Answer in their words: the value, the chart name, yes or no.>
2. <Only if needed: "X, NOT Y".>
See the picture: <what is marked>.

Thank you.
```
1-line example: "Order <no.>, part 2 (P-02): 1. Powder coat colour: <chart name>, all over. Thank you."

## Form 2: corrected files for an artwork or ink question
```
Subject: <their subject line, unchanged>

Hello,

Order <no.>, <their number> (<our number>): new files attached.
1. <file>.dxf: each layer is one ink; layer colour = ink colour; inks: <chart names>. Only <n> inks.
2. <file>_ink_sheet.pdf: both faces in the ink colours, with the ink table.
3. <file>.png: the finished part. <What in the picture is not printed.>
Please use these files, NOT the earlier print file.

Thank you.
```

## Form 3: withdrawal of an earlier instruction
```
Subject: <same thread>

Hello,

Order <no.>, <their number> (<our number>): please ignore my message of <date> about <topic>.
New instruction: <what to do now>.

Thank you.
```

## Form 4: status nudge (only when they are past their own stated time)
```
Subject: <same thread>

Hello,

Order <no.> shows "<status>" since <date>. Is anything needed from my side?

Thank you.
```

## Checklist before sending
- [ ] One topic; only what was asked. [ ] Same thread. [ ] Both numbers on every line.
- [ ] "X, NOT Y" for every correction. [ ] One picture attached, the numbers on it.
- [ ] No product or board names; no personal data in the text or the picture.
- [ ] Nothing contradicts a form field or an active instruction (`ORDER_LOG.md`).
- [ ] The user saw it (or the standing OK covers it). [ ] The typed text and the attachment list were read back from the page before Send.
- [ ] Sent inside their working day; deadline noted: <local date and time>. [ ] Logged in `ORDER_LOG.md`.
