# <device name>, rev <A>: ordering checklist (case and cables)

Nothing is ordered until every box is ticked, or answered "not applicable: <reason>". The agent stops at the payment page. The user pays.
Every box has a slot: `[ ] <item> | seen: <value as shown on the site> | proof: <screenshot path>`.

## Evidence status (copied into the hand-over message before payment)
- Gates evidenced: <gate 0, gate 1, print fitted, gate 2, with dates | none>.
- Gates skipped by the user: <which, date, "their words" | none>.
- Could not run: <which checks | none>. PROVISIONAL or not-proven items used: <which | none>.

## 1. Before any quote (the freeze)
- [ ] Every choice is made: ends, routes, cable types, colours, inks, wording, quantities | seen: <DECISIONS.md date> | proof: <>
- [ ] Full interconnect check ticked: power, signals, radio, antenna feed, fans, ground | seen: <> | proof: <CABLE_LIST.md>
- [ ] Capability sheets re-read by an independent agent this week | seen: <read dates> | proof: <review report>
- [ ] Files hash to the frozen checksums | seen: <> | proof: <>
- [ ] STEP headers clean; privacy scan clean; catalogue scan clean | seen: <headlines> | proof: <out/CHECKS.md>
- [ ] Today is inside a submit window (Monday to Wednesday, before their morning) | seen: <supplier_calendar output> | proof: <>
- [ ] The lessons file was read (`references/lessons.md`, and the project's own) | seen: <date> | proof: <>

## 2. Cable quote (one item per cable)
- [ ] Item named with our cable number and name | seen: <> | proof: <>
- [ ] Every form field equals `out/cables/FIELD_SHEET_cables.md`; read-back run (`cable_fieldsheet.py --readback`) | seen: <headline> | proof: <>
- [ ] One length per harness; tolerance at the supplier's standard | seen: <> | proof: <>
- [ ] Requirements field: each non-default first, as "X, NOT Y", then "CUST P/N: <id>", nothing else | seen: <> | proof: <>
- [ ] Drawing, pin-map picture and orientation picture uploaded WITH the quote (count and size within the limits) | seen: <file list> | proof: <>
- [ ] Every housing has a cavity table with the EMPTY positions; two-row numbering said in words and shown | seen: <> | proof: <drawing pages>
- [ ] Each crimp's wire range covers the wire gauge | seen: <AWG rows> | proof: <>
- [ ] No loose extras in the cable order | seen: <> | proof: <>
- [ ] No product or board names in any item, file or note | seen: <> | proof: <>
- [ ] The user's go for the quote request (it cannot be edited afterwards) | seen: <"their words", date> | proof: <>
- [ ] Line map recorded the moment the quote is ready | seen: <ORDER_LOG.md> | proof: <screenshot>

## 3. Case quote (per part)
- [ ] The part's archive holds STEP, PDF, print file, ink sheet, renders | seen: <> | proof: <>
- [ ] Every field equals `orders/FIELD_SHEET_enclosure.md` | seen: <> | proof: <>
- [ ] The SAME coat chart name in every coated part; nothing else about colour anywhere | seen: <> | proof: <>
- [ ] Inks by chart name; print file layers in the ink colours; factory view looked at | seen: <> | proof: <out/silk/>
- [ ] Remark pasted word for word; it contradicts no field and names nothing the part does not have | seen: <> | proof: <>
- [ ] No masking, no partial coating, no colour-system word, no "if possible" | seen: <catalogue scan> | proof: <>
- [ ] No default box left ticked that we did not choose (every box read) | seen: <> | proof: <>
- [ ] The user's go to submit for review | seen: <"their words", date> | proof: <>

## 4. Shipping and totals
- [ ] Shipping options shown to the user as a table; choice recorded | seen: <> | proof: <>
- [ ] Destination and combine setting equal `ORDER_PLAN.md`; the page's own proof saved; no e-mail sent to confirm it | seen: <> | proof: <>
- [ ] Total read at the quote | seen: <> | proof: <>
- [ ] Total read after the review | seen: <> | proof: <>
- [ ] Total read again at the pay step; every change explained or flagged | seen: <> | proof: <>
- [ ] Coupons on the page checked; the best one reported | seen: <> | proof: <>
- [ ] Consent and terms boxes: named to the user, ticked by the user | seen: <which, who> | proof: <>
- [ ] Stopped at the payment page; summary sent with the pay-by time | seen: <> | proof: <>

## 5. After each payment (agent, the same session)
- [ ] Status read on the order page (not from an automatic mail); references and paid total in `ORDER_LOG.md` | seen: <> | proof: <>
- [ ] The whole shipping plan re-read and ticked; the next order of the plan placed or dated | seen: <> | proof: <ORDER_PLAN.md>
- [ ] Watch offered; started on the user's yes, or declined (`WATCH_PROMPT.md`) | seen: <> | proof: <>
- [ ] No "just to confirm" message sent; specs are checked on the production drawing only | seen: <> | proof: <>
