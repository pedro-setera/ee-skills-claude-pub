# Combined shipping, cables and fabricated parts

How to ship a JLCPCB order together with LCSC parts or LCSC cable assemblies in one parcel, and the ordering lessons from sister services (custom cables, sheet-metal parts) that generalise. Read before the first payment of a project (phase 12) and at each later checkout.

Facts here were read or observed in 2026-11. Re-read the live JLCPCB page before relying on any number, option name or fee.

## Contents
1. Sources
2. What combining means
3. Conditions as recorded
4. The sequence that works
5. What the checkout shows when it works
6. When the page shows no link
7. Hold times
8. Fallback date
9. The three-line explanation for the user
10. Sister services: custom cables and fabricated metal parts
11. Not recorded here

## 1. Sources

- **[HELP]** LCSC's help page on combining LCSC and JLCPCB orders, read twice in 2026-11.
- **[PCB]** the checkout of a 2-layer JLCPCB order set to ship to LCSC's collection warehouse, 2026-11.
- **[CAB]** the checkout of an LCSC cable order combined with that PCB order, and its order page after payment, 2026-11.
- **[ORD4]** a 4-layer JLCPCB order paid before the conditions were known, 2026-11.
- **[CNC]** JLCCNC's account-centre page on combined shipping, read 2026-11, and a sheet-metal order of 2026-11.

## 2. What combining means

- The JLCPCB order is shipped first to LCSC's collection warehouse in Hong Kong (the collection warehouse address given in LCSC's help page). It waits there.
- The LCSC order (parts, or cables from LCSC's cable service) is placed last and names the waiting PCB order at its checkout.
- One parcel then leaves the warehouse for the user, by the courier chosen on the LCSC order, with shipping priced on the combined weight.
- It saves one international shipment and one customs clearance. It costs time: the boards wait for the slowest order.

## 3. Conditions as recorded

From [HELP], 2026-11:
- Same account and same currency; the combined order cannot be split afterwards; no combining for delivery to mainland China.
- The JLCPCB order must ship to LCSC's Hong Kong warehouse. The destination is set at the JLCPCB checkout and **cannot be changed after checkout** [HELP, confirmed by JLCPCB's own rule on [ORD4]].
- The orders to be combined must already be paid. They are linked at the checkout of the **last** order.
- Only one JLCPCB order can join: LCSC "can't combine multiple" PCB orders (as read 2026-11).
- Linking works only while the earlier order is paid and not yet packed.
- An earlier reading also listed "same address" as a condition. The mechanism ships the PCB order to the warehouse, so this most likely refers to the final delivery address; the records do not settle it. Confirm on the LCSC checkout.

Account checks before building carts:
- **Separate address books:** LCSC keeps its own, apart from JLCPCB's. Check the account's default shipping address in every storefront before building a cart; a default in mainland China blocks combining.
- **Quotes do not link:** an LCSC parts checkout could not link to a cable order that was still a quote. Link to paid orders only.
- JLC3DP (3D printing) shares the cart with JLCPCB; whether JLCCNC joins that cart was unconfirmed (read on the help pages the same day).

## 4. The sequence that works

1. Before the first payment, read the combine conditions end to end and write one shipping plan for all orders: order, status, destination, who joins whom. Seen once [ORD4]: an order paid with a direct address before the conditions were read could only ship alone, or be cancelled and redone.
2. JLCPCB order: set the delivery address to the LCSC collection warehouse at its checkout. Read it back in the summary and tell the user (`order-flow.md` step 18).
3. Wait until every order to be joined is paid (cables: after the quote is priced).
4. Place the joining LCSC order **last**. LCSC parts ship 1 to 2 days after payment, so ordering them early defeats the plan.
5. At its checkout, tick the combine option and select the PCB order (section 5).
6. Record the link in the order log and verify it after payment (section 6).

## 5. What the checkout shows when it works

On [CAB]:
- A "Combine Orders" box. Ticking it listed the PCB order shipped to the warehouse; it was selected.
- All shipping options were re-priced for the combined weight, and the shipping method had to be chosen again.
- The options, with delivery days: an economy line 7 to 15 days, 4PX 5 to 23, FedEx Economy 4 to 8, FedEx International Priority 3 to 7, DHL 3 to 7, UPS 3 to 7. All were FCA: duties and taxes paid by the buyer on delivery. Prices depend on weight and destination; read them on the day.
- Present the options as a table (days, price, duty terms) with one suggestion: the cheapest that meets the user's date.
- A "Customer Compliance Statement" box had to be ticked to submit. It is a declaration: the user ticks it, or names it and tells you to, each time.
- "Submit Order" created the order and led to the payment page (PayPal, card, wire). That button and the payment are the user's: the agent stops at the summary before it.

## 6. When the page shows no link

- After payment the cable order page showed only the final address and no link to the PCB order [CAB], which leaves it unclear how the boards will arrive.
- Then: explain the plan in three lines (section 9), and draft a short e-mail asking the supplier to confirm in writing that the parcel will include the PCB order. Send it only with the user's go. The supplier's answer: not recorded.
- Do not e-mail about what the rules page already states; each e-mail round costs about a day.

## 7. Hold times

- **JLCPCB and LCSC combine:** a hold of 7 days was recorded once without its source page: treat it as uncertain and read the live page.
- **LCSC warehouse:** how long it holds a PCB parcel before an LCSC order claims it was not found in the written rules [HELP].
- **JLCCNC's own combined shipping:** it saves shipping only if another order to the same address is placed within 15 days [CNC]. This is a different service and a different rule from the LCSC combine.

## 8. Fallback date

- Set a date for every dependency in the plan. If the slow order (a cable quote, a sheet-metal review) is not paid by that date, place the LCSC parts order combined with the PCB order only, and let the slow order ship alone.
- Write the date in the shipping plan and tell the user when it applies.

## 9. The three-line explanation for the user

Give it, with a small flow picture, at the moment the plan is chosen:
1. The boards go first to LCSC's collection warehouse in Hong Kong, not to you.
2. They wait there until the LCSC order that names them is ready.
3. Then one parcel leaves for your address, with the courier you chose on the LCSC order.

## 10. Sister services: custom cables and fabricated metal parts

Lessons that generalise beyond the cable service and the sheet-metal service used in 2026-11:
- **Type the specification into the form fields, not only into the drawing.** A cable quote came back with generic lines although the PDF drawings were exact. In the fields give the cable type in words, each connector's maker part number and LCSC code, every angle and exit direction, wire colours and gauge.
- **One length per harness.** The cable maker threads the whole bundle through the housing: every wire of one harness is cut to one length. Give the longest route plus bend allowance.
- **Standard tolerances.** The cable maker's standard was +/-3 mm or +/-5 mm; tighter values trigger a question. Keep +/-1 mm only where essential and say why on the drawing.
- **Check the quote and the production drawings.** Cable production drawings came after payment, for confirmation; nothing is made before that. Compare every line with the original drawings.
- **Colours and finishes from the supplier's own chart,** with the same chart name in every part's finish field. A remark "RAL ... if possible" stopped a part in review for 2 days.
- **No partial coating.** The sheet-metal factory powder-coated all over and could not mask; grounding contacts were scraped at assembly instead. Ask early whether masking is possible; otherwise design contacts that do not depend on bare metal.
- **The remark never contradicts a form field,** and adds only what the fields cannot say.
- **One order waits for its slowest part.** The pay button appeared only after every part was reviewed. A new or unusual part may be better ordered alone.
- **Drawings fully dimensioned from datums:** every hole and cut-out from named reference edges, pattern tables, flat pattern, inserts and print positions, tolerances; then an automatic check that every 3D feature has a drawing dimension, and a reviewer playing the supplier's engineer.
- **Only one print file and one PDF per part** were accepted by the sheet-metal instant quote [CNC]. Run an instant quote early, without paying, to learn such limits.
- **Scrub file headers before upload.** STEP headers can carry the system user name and a private host address from the CAD tool's defaults.
- **Prefer cancel-and-resubmit to editing a quote** when the form errors (seen once: "The static resource is unavailable. Please refresh the page" sent nothing). Stop and do not retry blindly.
- **Response times on record:** the cable quote took 3 days plus one question against a 48-hour working-day target; e-mails to the cable team were answered in about a day; no weekend work. Lead time was stated as 10 business days after the drawings are confirmed.

## 11. Not recorded here

- The LCSC warehouse's hold time before claiming; the source of the 7-day JLCPCB-LCSC figure.
- Whether the LCSC combine needs the same final address or the same account address.
- Whether JLCCNC orders can join a JLCPCB or LCSC parcel.
- The supplier's written answer confirming the combined parcel.
- Whether the warehouse charges storage or handling.
