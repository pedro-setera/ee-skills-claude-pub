# Shipping and combined parcels between the group's shops

**As read 2026-11; re-read the live page before every order.** Sources: the shops' FAQ and help pages, and three real
orders that were combined in one parcel (a cable order, one board order and a parts order). The rules of combining
change: read the FAQ page of the day. This file holds no addresses on purpose: **read the warehouse address on the
supplier's FAQ page that day.**

## 1. The shops and what can travel together

| Order | Can share a parcel with | How |
|---|---|---|
| Cable order (cable shop) | ONE board order of the group's board shop; a regular parts order of the parts shop | The board order ships to the parts shop's warehouse; the combine is ticked at the cable or parts checkout |
| Board order (board shop) | A cable or parts order, as above; or other orders of the board shop and its sister shops through the board shop's own "combine shipping" account service | See sections 2 and 3 |
| Case order (CNC and sheet-metal shop) | **Alone, or with another order of the same shop family** to the same address (one cart and one payment with the board shop, the print shop and the standard-parts shop was offered) | Its own checkout |
| Parts order (parts shop) | A paid, not yet packed cable order and its board order | Ticked at the parts checkout |

**A case order does not join the cable parcel.** The cable shop's combine takes only one board order, and a case
takes one to two weeks longer than boards: it would hold the parcel. Ship the case alone, or with another order of
its own shop family in the same week.

## 2. Combining a board order with a cable or parts order

1. **At the board shop's checkout** choose the parts shop's warehouse as the delivery address. Read the address on
   the parts shop's FAQ page about combining orders, that day. **This is set at checkout and cannot be changed
   later.** The leg to the warehouse was a cheap local courier (a few USD).
2. **At the cable (or parts) checkout** tick the board order under "Combine Orders". The page then says to choose a
   shipping method again and re-prices the shipping with the boards' weight.
3. **The proof is that re-priced checkout screen.** Save it in `mech/orders/`. Do not e-mail to confirm: the answer
   took three days and said what the screen had shown.
4. Afterwards the cable order page shows only the final address, not the link. That is normal.
5. **One board order per parcel.** A second board order cannot join.

## 3. A parts order can join

A regular parts order joins the same parcel while the cable order is paid and not yet packed: at the parts checkout
"Combine Orders" lists the waiting batch; tick it and choose the SAME shipping line. On one real case the combined
parcel was re-priced below the shipping already paid, the parts paid no shipping and the difference was credited to
the account. The parts order's detail page then shows a "view combined orders" link listing all the orders: that is
the proof.

**Order the parts the same week as the cables.** On one project the parts order was planned "last, linked to the
cables" and was never placed: after each payment re-read the shipping plan and tick what is done (SKILL.md rule 14).

## 4. The board shop's own combine service

The board shop offers a combine-shipping service as an account setting: paid orders wait in its warehouse for a
limited number of days of free storage and ship together. As read 2026-11: 15 days of free storage (one other
page said 7: read it on the live page), and a case order of the CNC and sheet-metal shop can ship through it with
another order of the same shop family to the same address (section 1). It saves a second express shipment only when
another order really goes the same week.

## 5. The shipping plan (written in phase 11, ticked in phase 13)

One table in the order plan:

| Order | Ships to | Combined with | Shipping line | Set at which checkout | Proof saved | Done |
|---|---|---|---|---|---|---|
| Boards | the parts shop's warehouse (address read on the FAQ that day) | the cable order | local courier | board shop | screen | |
| Cables | the user | boards, parts | the express line chosen | cable shop | re-priced screen | |
| Parts | the user | the cable batch | the same line | parts shop | "view combined orders" | |
| Case | the user | none | express, duties prepaid | case shop | total at the pay step | |

Cables are the critical path (about 4 weeks from request to door): boards that combine with them wait in the
warehouse until the cables are made. Tell the user before they choose.

## 6. Shipping lines, duties and prepaid options

- Express lines (2 to 7 business days) can cost several times a slow direct line (1 to 2 weeks or more). A metal
  case may be billed by volume weight (well above its real weight on one order); prepaid duties come on top.
- **Duties prepaid (DDP) or not.** With a prepaid option the shop collects VAT, duty and the carrier's fee at
  checkout and nothing is due at the door. Without it (the cable shop's terms were FCA) the receiver pays on arrival,
  plus a carrier fee. Show the user both totals where both exist. Suggested: the fastest line at a fair price with
  duties prepaid.
- **The total at the pay step can differ from the review page.** On one case order shipping and duties together rose
  clearly between the two. Read it again (SKILL.md rule 14).
- **Customs rules depend on the destination and change.** The consignee type follows the name on the address. Read
  the supplier's customs page for the user's country that day and put the landed cost (parts, shipping, duties, carrier fee) into the order plan.
- The quote page of the case shop showed shipping only to the account's region: use its shipping calculator page.
- Coupons: check them at each pay step.

## 7. The address

The delivery address is the user's (suggested: the one saved in the account). The agent never types an address
that the user has not given for this order, and never stores one in the skill, in a script or in a file that is
uploaded (SKILL.md rule 20; `privacy_scan.py` on every upload folder).
