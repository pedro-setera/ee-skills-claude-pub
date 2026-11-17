# <board name>, rev <A>: ordering checklist (JLCPCB, PCB and assembly)

Nothing is ordered until every box is ticked, or answered "not applicable: <reason>" (for example a board check when the user brought production files with no board). The agent stops at the order summary or the payment page. The user submits the order and pays.
Files: `out/jlc/` (Gerbers and drill zip, BOM, placement file, fab notes, rotation table `rotations.md` where a board exists, `manifest.json`). Upload-folder zip sha256: <value>.

Read the live supplier pages first (an independent agent). Rules below are the ones read on <date>.

Every box has a slot: `[ ] <item> | seen: <value as shown on the site> | proof: <screenshot path>`.

## Evidence status (copied into the hand-over message before payment)
- Gates evidenced: <gate 1 on <date>, gate 2 on <date> | none>.
- Gates skipped by the user: <gate 2, <date>: "<the user's words>" | none>.
- Not checked: <nothing | "manufacturing check only": circuit and layout rules not reviewed | "import not verified" | placement rotations UNKNOWN until the preview>.

## 1. Board options
- [ ] Layers <2>, stack <as the supplier lists it>, thickness <1.6 mm>, copper <1 oz> | seen: <> | proof: <>
- [ ] Surface finish <HASL lead-free | ENIG> | seen: <> | proof: <>
- [ ] Solder mask <colour>, "as per Gerber, no extra expansion" where a web is thin | seen: <> | proof: <>
- [ ] Via covering as the order form offers it for this layer count on the day (tented or plugged); never untented by accident; no via-in-pad unless stated (thermal vias in exposed pads are the one exception, DFM-40) | seen: <> | proof: <>
- [ ] Board size and quantity as detected: <40 x 30 mm, 5 pcs> | seen: <> | proof: <>
- [ ] Edge rails or panel as decided (<5 mm rails on the long sides, or none>) | seen: <> | proof: <>
- [ ] Tooling holes: "Added by JLCPCB", and the files carry none (<or: "Added by Customer", the panel carries JLCPCB's own kind of hole at the user's wish>) | seen: <> | proof: <>
- [ ] Overhangs or special edges stated in the remark: <none | part and amount> | seen: <> | proof: <>
- [ ] Order-number mark placed where the silkscreen shows it | seen: <> | proof: <>
- [ ] No default box left ticked that we did not choose (read every one) | seen: <> | proof: <>

## 2. Assembly options
- [ ] Side(s): <top only> | seen: <> | proof: <>
- [ ] Standard or economic assembly: <as decided, with the reason> | seen: <> | proof: <>
- [ ] Parts left unplaced (DNP, hand-fit): <list>; not in BOM or placement file | seen: <> | proof: <>
- [ ] Every BOM line selected and matched to its LCSC number; each warning's exact reason read: <list> | seen: <> | proof: <>
- [ ] Extended-part count and fee as expected: <n lines, x> | seen: <> | proof: <>
- [ ] Placement confirmation option: <yes | no>, wording agreed with the user | seen: <> | proof: <>
- [ ] Remark to the supplier: <two or three plain lines, nothing that contradicts a form field> | seen: <> | proof: <>
- [ ] Process limits of the parts where they matter (phase 12 step 3b): <none | U1 moisture level covered by the assembler's process as read on <date>; X-ray ordered for U2; J3 hand-fit, not reflow-rated> | seen: <> | proof: <>
- [ ] Question to the supplier before the order (phase 12 step 5b): <none | the one question; answer, scope and date in ORDER_LOG.md> | seen: <> | proof: <>

## 3. Placement preview, every polarised part
Open the supplier's preview. Zoom each part, save a crop, compare to the silkscreen mark (or the user's assembly drawing). For production files brought with no board, every rotation is UNKNOWN until it is seen right here; a wrong one goes back to phase 12.
- [ ] <Diodes and LEDs: cathode on the silk bar> (<D1 to D4>) | seen: <> | proof: <crop>
- [ ] <Electrolytic or tantalum capacitors: + on the silk +> (<C5>) | seen: <> | proof: <crop>
- [ ] <Transistors and SOT packages: pin 1 on the pin-1 mark> (<Q1, U3>) | seen: <> | proof: <crop>
- [ ] <ICs: dot on the pin-1 mark> (<U1, U2>) | seen: <> | proof: <crop>
- [ ] <Connectors: mouth toward the edge, pin 1 square pad> (<J1, J2>) | seen: <> | proof: <crop>
- [ ] Bottom side (two-sided assembly; else "not applicable: one side"): convention confirmed in the preview-only upload before gate 2, recorded for this bottom side (`[[rotations.bottom_side_confirmed]]`) | seen: <date> | proof: <crop>

## 4. Before paying
- [ ] Stock re-checked the same day for <5> boards plus the supplier's attrition: all lines in stock | seen: <date, time> | proof: <`out/BOM_STOCK_CHECK.md`>
- [ ] Checksum of the uploaded files equals the checksum of the files that were checked: <zip, BOM, placement file> | seen: <values> | proof: <>
- [ ] Board sha256 matches PROJECT_STATE, the interface file and GATE2_SUMMARY | seen: <value> | proof: <>
- [ ] Production files are newer than the board and unchanged since the supplier-rules review | seen: <> | proof: <>
- [ ] Programmable part (phase 12 step 6b): <programming and debug access on the board; bring-up image <file | owner, date> | not applicable: no programmable part> | seen: <> | proof: <>
- [ ] Cost in the cart matches the estimate: <x> vs <y> (difference explained) | seen: <> | proof: <>
- [ ] Coupon with the biggest saving applied and reported (coupons may not stack); shipping method chosen and address checked by the user | seen: <> | proof: <>
- [ ] Shipping plan: this order ships <together with | apart from> others; combine rules read | seen: <> | proof: <>

## 5. After payment (agent, in the same session)
- [ ] Status verified on the order page; order reference and landed total written to ORDER_LOG and PROJECT_STATE
- [ ] Watch offered; started on the user's yes, or declined (see WATCH_PROMPT)
