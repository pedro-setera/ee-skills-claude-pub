# Phase 11: freeze and order plan

Turn the approved candidate into a frozen revision with checksums and clean file headers, and write the order plan: what is ordered first, what ships with what, and every step's deadline in the supplier's working time.

## Inputs

- Gate 2 with the user's words; the upload folders `out/upload/<supplier>/`; the field sheets and remarks.
- `scripts/step_scrub.py`, `scripts/privacy_scan.py`, `scripts/catalogue_scan.py`, `scripts/supplier_calendar.py`, `scripts/build.py`, `scripts/check_all.py`.
- `templates/ORDER_PLAN.md`, `templates/ORDERING_CHECKLIST.md`, `templates/ORDER_LOG.md`.
- `references/suppliers/shipping-and-combine.md`, `order-flow.md`, `lcsc-cable.md`, `jlccnc-sheet-metal.md`; `references/lessons.md`.

## Steps

1. **Check that everything is chosen.** Ends, routes, cable types, colours, inks, wording, quantities: each has one value in `DECISIONS.md` or `cables.json`, and the interconnect check of phase 5 is ticked. Any open choice stops the freeze. A submitted cable quote cannot be edited (as read 2026-11: its Edit changes only the purchase-order number; re-read): one forgotten cable meant entering all cables again as a new quote.
2. **Give the revision letter.** Set `[project] rev` in `mech.toml` and `rev` in `cables.json`, then run `python -I <skill folder>/scripts/build.py --project <project>/mech` so that every drawing carries it. Files that were ordered are frozen for good; the next batch gets the next letter.
3. **Clean the STEP headers:**
   `python -I <skill folder>/scripts/step_scrub.py <project>/mech/out/upload --in-place --company "<company or empty>"`
   then `python -I <skill folder>/scripts/step_scrub.py <project>/mech/out/upload --check`. The CAD kernel writes the PC's user name and host into the header by default; one upload carried a personal name that could not be taken back.
4. **Scan the upload folders for private data:**
   `python -I <skill folder>/scripts/privacy_scan.py --project <project>/mech`
   Text, STEP and DXF headers, PDF and PNG metadata, archives. No names, no paths, no product or board names (add those to the deny list in `[privacy] deny_file`). Run `catalogue_scan.py` once more on the final folders.
5. **Archive and hash.** Pack each supplier's folder exactly as it will be uploaded, (into `out/upload/`), then run `freeze.py --project <project>/mech --name rev-<letter> --profile order`: it refuses what is stale, copies the set to `reviews/frozen/rev-<letter>/`, writes `rev-<letter>.MANIFEST.sha256` and prints the lines for the `frozen` block of the state file. Phase 12 uploads only files that hash to these values.
6. **Write the order plan** (`orders/ORDER_PLAN.md`):
   - **Cables first.** They are the critical path: about four weeks from the request to the door on one past order (quote, drawings, one revision round, production, transport).
   - **Then the case.** It is reviewed part by part and waits for its slowest part.
   - **Then the loose parts** (connectors, screws, feet), the same week, so that they travel with the cables. A parts order planned for the combined parcel was once simply never placed, and was found five days later.
   - **Boards,** when the electronics skill orders them in the same weeks, are planned around the cables.
7. **Write the shipping and combine plan** from `references/suppliers/shipping-and-combine.md` (dated; re-read the live pages): which order ships to which address or collection warehouse, which order joins which, and what proves the link on the page. A destination set at one supplier's checkout cannot be changed afterwards. A metal order with a finish can take one to two weeks and would hold a combined parcel: ship it alone or only with orders of the same supplier. Each row gets a tick box and a fallback date.
8. **Compute the deadlines in the supplier's time:**
   `python -I <skill folder>/scripts/supplier_calendar.py submit-window --project <project>/mech`
   `python -I <skill folder>/scripts/supplier_calendar.py plan --steps <project>/mech/orders/plan.toml --project <project>/mech`
   Submit Monday to Wednesday before their morning opens, so the request is first in the queue. Answer a question the same supplier day. Pay before their evening. Work sent on their Friday evening or weekend waits for Monday. Plan one supplier working day per question round; their own time statements ("2 to 3 hours") did not hold. Set holidays in `[supplier_hours] holidays`.
9. **Estimate the landed cost** per order: parts, shipping, duties and taxes, payment fees; who pays the duties (prepaid in the cart, or on arrival). Write the estimate next to an empty "actual" column in the order log.
10. **Fill the ordering checklist** (`orders/ORDERING_CHECKLIST.md`) from the template: every form value with its "seen" and "proof" slot, per order. Start `orders/ORDER_LOG.md` from its template.
11. **Check the user's time.** The plan names when the user is needed: sign-in, address and shipping choice, payment, and one OK per message unless a standing OK for that order is recorded. Agree the days.

## Questions for the user

Nothing, normally. Two only when they are not yet answered:

- For this order, may I send answers to the supplier's questions without showing you each one first, as long as they change nothing about price, design or delivery?
  - Suggested: no for the first order with a supplier; yes later, per order.
  - Why: each answer the same supplier day saves a day; with the standing OK I still show you anything that changes the order.
- The plan needs you on `<day>` for sign-in and payment (about `<n>` minutes each). Does that fit?
  - Suggested: `<the Monday to Wednesday slot>`.
  - Why: a request that lands before their morning is reviewed that day; a Friday request waits for Monday.

## Done when

- [ ] No open choice; the interconnect check is ticked. Evidence: `DECISIONS.md`, `CABLE_LIST.md`.
- [ ] The revision letter is on every drawing and in `cables.json`. Evidence: the title blocks.
- [ ] `step_scrub.py --check` and `privacy_scan.py` are clean on the upload folders. Evidence: their rows.
- [ ] Every file to upload has its sha256 in the state file, and a frozen copy exists. Evidence: the `frozen` block, `reviews/frozen/rev-<letter>/`.
- [ ] `ORDER_PLAN.md` has the sequence (cables first), the combine plan with tick boxes and fallback dates, and a deadline per step in local time. Evidence: the file, the calendar output.
- [ ] The landed cost estimate is written with its sources. Evidence: `ORDER_LOG.md`.
- [ ] `ORDERING_CHECKLIST.md` is filled up to the "seen" slots. Evidence: the file.

## Outputs

- The frozen revision: `reviews/frozen/rev-<letter>/`, checksums in `PROJECT_STATE.md`
- `orders/ORDER_PLAN.md`, `orders/ORDERING_CHECKLIST.md`, `orders/ORDER_LOG.md` (started)
- Clean upload folders `out/upload/<supplier>/`

## If something is missing

- Only one supplier (cables only, case only): the plan still gets the calendar and the landed cost; the combine section says "ships alone".
- The user cannot be reached in the submit window: move the submit to the next window; do not submit into a weekend.

## Lessons behind this phase

- A personal name and a private host name sat in the header of uploaded 3D files -> step 3.
- A quote was submitted before the cable list was final and had to be entered again -> step 1.
- Requests sent at the weekend and at the supplier's night waited for days -> step 8: the calendar.
- A parts order planned for the combined parcel was never placed -> steps 6 and 7: tick boxes and fallback dates.
- A supplier's "2 to 3 hours" took a day, more than once -> step 8: one working day per round.
- A coated part with a print took the longest and would have held a combined parcel -> step 7.

The full cases are in `references/lessons.md`.
