# <device name>, rev <A>: order plan

Written in phase 11, before the first quote. Re-read in full after EVERY payment, and ticked.
Times come from `scripts/supplier_calendar.py` (supplier hours: `[supplier_hours]` in `mech.toml`, as read on <date>).

## Blockers before the first quote
Each one closed, or accepted by the user in writing, before any quote. Typical: a capability sheet not re-read live
(seed only); a part number or supplier code still blank; a dimension still UNKNOWN; a review ended FIX AND RE-CHECK.
| # | Blocker | Closed by | Done |
|---|---|---|---|
| B1 | <> | <> | |

## Rules of the calendar
- Submit Monday to Wednesday, before the supplier's morning opens.
- Answer a question the same supplier day. Pay before their evening.
- Work sent on their Friday evening or weekend waits for Monday.
- One supplier working day per question round. Their own time statements are not promises.
- Supplier holidays in the coming weeks: <none | dates>.

## Sequence (cables first: the longest lead time)
| # | Step | Who | Latest (local time) | Supplier time | Done |
|---|---|---|---|---|---|
| 1 | Freeze: every choice made, interconnect check ticked | agent | <> | | [ ] |
| 2 | Cables: enter the quote, read back, request it | agent, user's go | <local time> | <Mon 09:00> | [ ] |
| 3 | Cables: line map recorded when the quote is ready | agent | <> | | [ ] |
| 4 | Cables: pay | user | <> | <before their evening> | [ ] |
| 5 | Case: upload, read back, submit for review | agent, user's go | <> | | [ ] |
| 6 | Case: answer review questions the same day | agent, user's OK | <> | | [ ] |
| 7 | Case: read the total again, pay | user | <> | | [ ] |
| 8 | Loose parts: order the same week, join the parcel | agent, user pays | <> | | [ ] |
| 9 | Cables: production drawings checked, ONE revision round | agent, user's OK | <about 3 working days after payment> | | [ ] |
| 10 | Cables: Confirm line by line | user's permission | <> | | [ ] |
| 11 | Boards (electronics skill), if in the same weeks | | <> | | [ ] |

Expected door dates: cables <about 4 weeks after the request, on one past order>; case <>; parts <>.

## Shipping and combine plan
Rules read on <date> from the suppliers' pages (`references/suppliers/shipping-and-combine.md`). A destination set at a checkout cannot be changed later.
| Order | Ships to | Travels with | Set where | Proof on the page | Fallback date | Done |
|---|---|---|---|---|---|---|
| Cables | <home address> | <loose parts; boards> | <cable checkout> | <"combined orders" view, screenshot> | | [ ] |
| Loose parts | <joins the cable parcel> | <cables> | <parts checkout: combine option, same shipping line> | <re-priced shipping, screenshot> | <if the cables are packed before <date>: ships alone> | [ ] |
| Boards | <the collection warehouse of the plan> | <cables> | <board checkout> | <> | <> | [ ] |
| Case | <home address, alone> | <nothing: its finish takes longest> | <case checkout> | | | [ ] |

- [ ] After the cable payment: plan re-read, loose-parts order placed or dated.
- [ ] After the case payment: plan re-read.
- [ ] After the parts payment: the combine link is visible on the order page.

## Landed cost estimate
| Order | Parts | Shipping | Duties and tax (paid where) | Fees | Total | Source, date |
|---|---|---|---|---|---|---|
| Cables | <> | <> | <on arrival> | <> | <> | <> |
| Case | <> | <> | <prepaid in the cart> | <> | <> | <> |
| Loose parts | <> | <> | <> | <> | <> | <> |

## When the user is needed
| Day | For what | About |
|---|---|---|
| <Mon> | <sign-in at both sites; go for the cable quote> | <15 min> |
| <> | <payment of the cables> | <5 min> |
