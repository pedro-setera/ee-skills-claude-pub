# JLCPCB order flow

The order for PCBs with assembly on JLCPCB's site, step by step as it went on two real orders, with what to set, what to read back and the pitfalls met: read at phase 13.

Facts here were read or observed in 2026-11. Re-read the live JLCPCB page before relying on any number, option name or fee.

## Contents
1. Sources
2. Preconditions
3. The steps (1 to 21)
4. Daily cut-off and review before payment
5. What the agent never does here

## 1. Sources

- **[ORD4]** a 4-layer board, 5 PCBs, 2 assembled, Economic, 2026-11; payable at once.
- **[ORD2]** a 2-layer customer panel, 5 panels, 2 assembled, shipped to a collection warehouse, 2026-11; payable after a file review.
- **[SIS]** a cable order and a CNC order at sister services in the same month, where the step is the same.

Option names are the ones seen then. The form changes: read every label on the day and write the value you set into the ordering checklist.

## 2. Preconditions

All must hold before step 1:
- Gate 2 approved, or skipped by the user with their words recorded (for example production files brought with no board: "manufacturing check only"). The upload folder holds the Gerber and drill zip, the BOM, the placement (CPL) file, the fab notes and, where a board exists, the rotation table; their checksums equal the checksums of the files that were checked.
- The supplier-rules review has measured the exported files against the live pages.
- The stock check ran today (`parts-library.md`): every assembled line in assembly stock for the boards plus attrition.
- The ordering checklist is filled: every option and its value, the remark text, the customs text, the expected price range.
- A question asked before the order, if any (only the one of `references/working-rules.md` section 9, never in the remark), has its answer, scope and date in `ORDER_LOG.md`.
- The shipping plan for all orders is decided (`combined-shipping.md`). This order's destination is set at its checkout and cannot change later.
- **The user signs in** to the JLCPCB account. The agent never types a password.
- **The browser can upload files.** Seen once (2026-11): a built-in browser pane could not upload, and the user clicked each upload button; a browser extension could. Test this before a multi-file order.
- After a PC restart the browser extension stays disconnected until the user reconnects it. Check the connection first and tell the user at once if a tool is down.

## 3. The steps

Click options by their page element, never by screen coordinates. After each group, read every value back from the page.

**Pace.** Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8). A block also locks the user out of the account and the order being placed. No reload to wait for a review or a price.

**Step 1. Upload the Gerber zip.**
- Set: the zip from the upload folder, through the Gerber upload button ("Add gerber file" in 2026-11). Only the zip was accepted [ORD4].
- Read back: the layer count and board size JLCPCB detected. [ORD4] showed the right layer count and the board size to 0.01 mm. Compare both with the fab notes to 0.1 mm.
- Pitfall: if the detected size or layer count differs, stop. A missing inner layer or a wrong outline shows here first.

**Step 2. Base options.**
- Set: base material, layers, PCB quantity (5 is the minimum), different designs (1), delivery format ("Panel by Customer" for a panel made in KiCad, single board otherwise).
- Read back: the quantity counts panels when the delivery format is a panel.

**Step 3. Stack and copper.**
- Set: thickness, outer copper, the published stack (for example JLC04161H-7628 on 4 layers) and the layer order from the fab notes. Impedance control only if the design planned it (`capabilities.md` section 4).

**Step 4. Finish, mask, silk, vias.**
- Set: ENIG or lead-free HASL (`capabilities.md` section 5); mask and silk colour; via covering as the order form offers it for this layer count on the day (tented or plugged), never untented by accident.
- Pitfall [ORD4]: "tented" was not offered on 4 layers; "plugged" was free. A coordinate click picked "Untented" by mistake; clicking the element fixed it.

**Step 5. Remaining PCB fields.**
- Set: "Mark on PCB" ("specify position" or "Remove Mark"), outline tolerance, castellated holes, edge plating, gold fingers (all "No" unless designed).

**Step 6. Read every tick box on the page.**
- Read back: every checkbox and radio button, including those you did not touch.
- Pitfall [ORD4]: the assembly terms box was already ticked by default. The agent did not tick it. Neither tick nor untick such a box; tell the user it is pre-ticked, because accepting terms is the user's act.

**Step 7. Assembly options.**
- Set, as the checklist says: assembly on; the class ("Economic" on [ORD4]); the side or sides; assembly quantity (smaller than the PCB quantity if only some boards are assembled); tooling holes "Added by JLCPCB", and the files carry none (`assembly.md` section 5; "Added by Customer" only for a panel that carries JLCPCB's own kind of hole at the user's wish, which is not proven); "Confirm parts placement: Yes" (`assembly.md`).
- Read back: the class the order landed in (Economic or Standard) and the assembled quantity.

**Step 8. Upload the BOM and the placement file.**
- Set: the two files from the upload folder (the user clicks the upload buttons if the browser cannot).
- Read back: the number of BOM lines and placements JLCPCB parsed, against the files.

**Step 9. Select and match every BOM line.**
- Set: every line ticked; each line's LCSC number equal to the BOM's.
- Pitfall [ORD4]: a warning "some lines have no part selected" came from one unticked connector row; the order could not go on until every line was ticked and matched.

**Step 10. Read the exact reason of each warning.**
- Read back: open every warning and copy its text into the order log.
- Pitfall [ORD4]: after selecting all, the remaining warning was only a special-component fee of a few cents per piece on one connector, not a missing part. Do not treat a warning as a blocker, or as harmless, before reading it.

**Step 11. The placement viewer.**
- Check: overview first, then every polarised part zoomed against its silkscreen mark: every IC pin 1, diode band, LED, polarised capacitor, transistor, connector; DNP parts absent; hand-fit parts absent. Save a crop per part and look at it.
- Pitfall: rotations come from `parts-library.md` section 8; for production files brought with no board they are UNKNOWN until seen right here. A wrong part or rotation is not fixed in the viewer: it goes back to phase 12 (`phases/13-order.md` step 9). The viewer is the last look before money; at the later placement confirmation the engineer may still change things (`after-order.md`).
- A preview-only upload (two-sided assembly, `phases/11-layout-reviews.md` step 14b) ends here: it is never saved to the cart (step 15) or paid.

**Step 12. Expected engineering query.**
- If the design carries a known oddity (for example a header whose real pitch differs from JLCPCB's library pitch, or a connector that overhangs the edge on purpose), state it in the remark so the engineer does not have to ask.

**Step 13. Order remark.**
- Set: two or three plain lines, prepared in the checklist, that add only what the form fields cannot say. Example (2-layer panel): rails and mouse bites only on the two short ends; the long edges are final routed edges; hold the panel by its rails.
- Pitfalls: a remark must never contradict a form field; it is not a place for questions. On [ORD4] a remark with several points (hand-fit parts, rail sides, an intended overhang) led the engineer to ask whether to follow or ignore it, which cost an e-mail round. Fewer, plainer lines; anything the panel design can say for itself (the rails) goes into the panel instead, and the tooling holes are the form field's (`assembly.md` section 5).

**Step 14. Customs description.**
- Set: a generic description with its customs (HS) code, as the form offers [ORD4]. No product or board names.

**Step 15. Save to cart and read the cart.**
- Read back: layers, quantity, finish, assembly class, assembled quantity, rails or panel, price. Compare the price with the expected range in the checklist; ask before going on if it is outside.

**Step 16. Coupons.**
- Read every coupon offered; they may not stack (seen once, 2026-11). Apply the one with the biggest saving and report which; this is no question for the user.

**Step 17. Shipping and tax terms.**
- Show the user the options as a table and suggest one: the cheapest that meets the user's date, with import taxes and duties prepaid when offered.

| Terms seen | Who pays import tax | When | Seen on |
|---|---|---|---|
| IOSS (an example: EU delivery with the tax prepaid) | the buyer, inside the checkout total | before shipping | JLCPCB [ORD4], CNC [SIS] |
| DDP | the seller collects it at checkout | before shipping | CNC quote [SIS] |
| FCA | the buyer, billed by the courier | on delivery | cable checkout [SIS] |

- Courier and price lists change per destination and weight: read them on the day.
- Read the tax line on the checkout page and record what it says; the records of one order disagreed on whether the tax was inside the total.
- Pitfall [SIS]: the shipping chosen at payment raised one order's total by about a quarter over the quote. Record the landed total after payment, not the cart total.
- Check that an option to ship on the customer's own courier account is not selected [ORD4].

**Step 18. Address.**
- Use the address preset in the account, or the one the user types. The agent does not edit the user's address book. Check the account's default shipping address before building a cart.
- Read back the destination in the order summary and repeat it to the user, above all when the order ships to a collection warehouse (`combined-shipping.md`); seen once: a warehouse destination set but not said.
- Each storefront keeps its own address book (JLCPCB and LCSC separately).

**Step 19. Payment method and fees.**
- Read back: the preselected method and any fee it adds (seen once: about USD 1 on one method); tell the user, who chooses. There was no terms checkbox on the payment page [ORD4].

**Step 20. Hand-over: stop at the order summary or the payment page.**
- The button that creates the order ("Submit Order", "Place order"), paid or not, is the user's (`references/working-rules.md` section 3). Where it comes before the payment page, stop at the summary before it.
- Send the user one message: what is in the order, the total with shipping and taxes, the destination, the payment deadline if a cut-off applies (section 4), the evidence status of the ordering checklist, and what they need to do. Notify by the channel agreed in the state file and check that it arrived.
- The user enters the card and pays. If the tool refuses a click before that point (seen once at a sister service, 2026-11: a "Secure Checkout" button), do not work around it: give the user the exact steps (open the cart, choose the saved address, choose the shipping, pay) and the expected total.

**Step 21. After payment.**
- Verify that the order status changed (for example to "In Production") and save a screenshot.
- Record in `ORDER_LOG.md` and the state file: the order reference and the assembly reference, the date and time of payment, the destination, and the landed total split into PCB, assembly, shipping and taxes.
- Pitfall: an automatic "payment failed" e-mail arrived before a payment that then succeeded on one 2026-11 order. Trust the order page, not that e-mail.
- Offer the watch (`after-order.md`, phase 14); it starts on the user's yes.

## 4. Daily cut-off and review before payment

- **Cut-off:** on [ORD2], paying before 10:00 decided whether production started the same day. The time zone was not recorded; read it on the page. Put the deadline in the hand-over message.
- **Review before payment:** [ORD2] went into JLCPCB's file review after it was submitted (the user's click, step 20); the pay button became usable only after the review passed. [ORD4] was payable at once. What triggers the review (the customer panel, the collection-warehouse destination, or something else) is not recorded. Watch the order page and tell the user when payment opens.

## 5. What the agent never does here

- Type a password or sign in for the user.
- Enter card data or press the pay button, or the button that creates an order, paid or not.
- Tick a terms, compliance or consent box without the user's explicit word for that box.
- Work around a refused click.
- Choose a courier or an option with cost beyond the checklist without asking, or an option the checklist does not name unless price and function are the same (coupons: the biggest saving is applied and reported).
- Edit the user's address book.
- Click option groups by screen coordinates.
- Order on a stock check from a previous day, or on files whose checksum differs from the checksum of the files that were checked.
- Send a chat message or e-mail to the supplier without the user's go.
