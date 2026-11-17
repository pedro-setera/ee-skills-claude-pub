# JLCPCB parts library and LCSC

How to choose parts from JLCPCB's assembly library and LCSC, how to read stock, class and price per LCSC number, and why every placement rotation is derived from JLCPCB's own footprint.

Facts here were read or observed in 2026-11. Re-read the live JLCPCB page before relying on any number, option name or fee.

## Contents
1. Sources
2. Basic, preferred and extended parts
3. Two stocks: JLCPCB assembly stock and LCSC retail stock
4. Looking up stock, class and price per LCSC number
5. Life cycle and catalogue status
6. Minimum quantities, price breaks and small-order fees at LCSC
7. One BOM line per value that may change
8. Placement rotation and origin from JLCPCB's own footprint
9. Cases met
10. The assembler's engineer may still correct a rotation
11. Not recorded here

## 1. Sources

- **[API]** JLCPCB's public parts-search data (the service behind the assembly cart's part search), queried by a BOM and stock script, 2026-11. No sign-in.
- **[LCSC]** LCSC's product-detail data per part code, the same script and month; LCSC carts built then.
- **[DER]** the rotation derivation of a 4-layer board, repeated on a 2-layer panel, 2026-11.
- **[REV]** independent schematic and layout reviews, 2026-11.
- **[CONF]** the assembler's parts-placement confirmations, 2026-11.
- **[COM]** a free community copy of JLCPCB's parts list (jlcsearch.tscircuit.com), read by `scripts/jlc_parts.py candidates`, 2026-11. Not JLCPCB: candidates only.

## 2. Basic, preferred and extended parts

- The parts data gives each part a library type. Type "base" is a **basic** part; any other type is **extended**; an extended part with the preferred flag set is a **preferred** part [API].
- An extended part costs a fee per part type, once per order: about USD 3 each in 2026-11. On a 5-sample estimate, the extended-type fees were about 40 % of the total (seen once, 2026-11). Whether preferred parts pay that fee: not recorded; read the live page.
- **Basic first.** For every line, look for a basic part that meets the requirement before accepting an extended one. A reviewer queried the parts data and found a basic +/-0.5 % shunt reference where the design text said no basic one existed: no fee, and a tighter trip point [REV].
- Justify each remaining extended line against its fee in the BOM: the function needs it and no basic equivalent exists, or it can be left unfitted (DNP) in the first samples. Quality first, then cost (`references/working-rules.md` section 11): a basic part replaces an extended one only when it is equally good and dependable, and never replaces a well-known part for a critical job (`phases/03-parts.md`).

## 3. Two stocks: JLCPCB assembly stock and LCSC retail stock

- JLCPCB assembles from its own assembly stock. LCSC sells from its retail stock. For the same part code they are different numbers.
- Seen once (2026-11): two common capacitors or resistors showed 0 at LCSC and plenty in JLCPCB's assembly stock. They were kept, because assembly stock is what feeds the assembly [API, LCSC].
- The reverse (retail stock but no assembly stock) is equally possible since the stocks are separate; it was not met on these orders. Read both, always.
- **Gate rule used:** a part JLCPCB places needs assembly stock >= the need; a part bought for hand fitting or off-board use needs LCSC stock >= the need. Record both stocks for every line, with date and time.
- **Need** = parts per board x boards + spares: 20 % spares, at least 2, per line, or JLCPCB's own attrition count (section 4).
- **Flag thin lines:** stock under 10 x the need [REV], or under 50 x the number of boards. Met: a USB-C receptacle with a few hundred in stock for a need of a few; a current-limit switch whose stock barely covered the batch plus attrition, replaced by a pin-compatible part with ample stock.
- Re-run the stock check on the order day, before the cart, and again if the payment waits a day or more.

## 4. Looking up stock, class and price per LCSC number

These look-ups need no sign-in; `scripts/jlc_parts.py` follows this method.

**When no LCSC number is known yet** (a new design, a replacement part): the same parts search takes a maker part number or words as its keyword and answers with the first matching parts and their part codes. `scripts/jlc_parts.py search` asks it with one request per text, reads the first page only, and saves the search and every result (`phases/03-parts.md` step 2b). Search by the full maker part number first. A result is a candidate: the datasheet decides. Seen live once (2026-11, a new design): ten maker part numbers and series names (a comparator's full part number, a fuse series, a connector's number with its dash, a switch series) each gave the matching parts with their codes and the total the service counts, up to 25 results in one request, with no refusal at the script's pace. A text that is only the start of a part number finds the whole family: read the suffixes. A text of several words has not been tried live, and how the service orders its results is not recorded.

1. Collect the LCSC numbers from the schematic source (every part with a code; DNP parts listed with a need of 0) and from the off-board list (hand-fit parts, cable parts, fasteners).
2. For each code, query JLCPCB's parts search with the code as the keyword, and keep only the result whose part code equals it exactly. Fields used: assembly stock count, library type, preferred flag, maker part number, brand, package, price ladder (start quantity and unit price), attrition count, minimum purchase quantity, minimum patch quantity, and the LCSC product link.
3. For each code, read LCSC's product-detail data. Fields used: retail stock, minimum buy quantity, USD price ladder, maker part number, brand.
4. Order quantity = per-board count x boards + attrition, raised to the minimum purchase and minimum patch quantities. Price it at the ladder step that quantity reaches.
5. Write a dated table: kind (assembled, hand-fit, off-board), designators with DNP marked, part, LCSC number, need, LCSC stock, assembly stock, class, unit price at 10, OK.
6. Write the JLCPCB BOM upload file from the same data, columns `Comment, Designator, Footprint, LCSC Part #`. A line that groups several designators carries the maker part number as its comment, not a function text, so two lines never read the same.

**Pace.** Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8). The block falls on the user's address and account. A burst of fast catalogue page loads can get the address blocked for a while, and the footprint service answered 403 when asked too fast (2026-11). Look-ups go through the paced scripts, and every answer is saved and reused.

Practicalities met:
- A code not found is reported, never skipped.
- Both services are undocumented and may change: in 2026-11 JLCPCB answered a POST to the supplier's public parts-search service, and LCSC a product `detail` service taking the product code. If they fail, read the part pages in the browser at the pace above and record the numbers by hand with the date.
- The parts data names a datasheet link for almost every part: the supplier's copy of the maker's document (`datasheet` in the saved answers). Asked by a script, that link does not answer with the file: seen 2026-11, one form of the link answered with a page of 140 bytes whose script forwards the browser, the other with a viewer page that names the file; in both the file itself lies on the supplier's file server. `scripts/fetch_parts.py` follows that one step inside the same site and records both addresses. Two parts of 19 had no such link, only a link that expires.
- Makers' own document servers often refuse a script (HTTP 403 seen 2026-11 on a large maker's server for a plain request). That is a refusal like any other: not repeated, not worked around. The supplier's copy is then the source; the full order of sources is in `references/working-rules.md` section 7. Seen the same day: a connector whose drawing the supplier did not hold came from the Internet Archive's copy of the maker's own file, in one request.

**Candidates with filters, without asking JLCPCB.** `scripts/jlc_parts.py candidates` asks a community copy of the parts list, which filters by category list, package, resistance and basic class, so the hunt for a cheaper basic part of the same value and package costs no request at the supplier. Its answers are kept apart (`out/jlc_candidates_answers.json`) and never used as stock or class: every candidate is confirmed with `lookup` before it enters the BOM. Seen live once (2026-11, three requests, no refusal) [COM]: the resistor list ignored the search text and answered its 100 rows of most stock; it applied `package` exactly; it read `resistance=10k` as 10 ohm (the script sends plain numbers and checks every row itself); 91 of its 100 rows of 0402 resistors had no stock in the copy, a basic part among them, so the copy's stock is no stock figure. The general search matched words loosely ("10k" found a 110 kOhm part; the script drops such rows). The lists of capacitors, microcontrollers and regulators were not read live: their form is taken from an outside description, and the script stops with "cannot run" on a form it does not know.

## 5. Life cycle and catalogue status

- LCSC marks some parts "not recommended for new designs" (NRND). Seen once (2026-11) on an off-board header housing: kept for the samples, with a production alternative listed. Check every line, off-board parts included.
- A maker's own store may list a part as a "non-catalog model, contact sales" while distributors still show it. Seen once on an RF part: the active catalogue sibling was chosen. Check the maker's status and stock at two distributors before a part enters the BOM.
- Which field of the parts data carries the life-cycle status: not recorded; read the part page.
- Give the user the LCSC number, maker part number and link for every recommended part; a part name alone is not enough to find it.

## 6. Minimum quantities, price breaks and small-order fees at LCSC

- LCSC sells some parts only from a minimum or at price breaks. Small headers were in the cart at 10 or 20 because of price breaks when 1 per unit was needed [LCSC]. Cart quantity = need per unit x units + spares; mark the lines rounded up for a price break.
- **Small-order handling fee:** at 2 pieces of one switch, LCSC added a USD 3 handling fee to the line; at 3 pieces the fee disappeared, so the third piece cost less than nothing. Later, adding two cheap jacks pushed the cart over a threshold and removed a USD 3 fee (seen once, 2026-11). The records do not say whether the threshold is per line or per cart, nor its value: read the cart. Round up when the extra parts cost less than the fee.
- JLCPCB's own minimums: the parts data gives a minimum purchase and a minimum patch quantity per part, and JLCPCB buys at least that many for the assembly (section 4).
- Packs of fasteners and connectors are often larger than the need: count the whole pack in the cost.

## 7. One BOM line per value that may change

- JLCPCB's BOM groups designators by part. After the order, one designator of a shared line could not be changed or left out: only the whole line, or new design files (the engineer's e-mail; see `after-order.md`). The line held several resistors of one value; only one of them had to change.
- Before ordering, give every designator whose value, fit or part may change its own BOM line: a distinct LCSC part of the same footprint, or a DNP line. Pull-ups, dividers and set-point resistors are the usual candidates; re-check each against every datasheet it touches before the order.
- The extended-part fee pushes toward sharing lines. Share only values that can never change.

## 8. Placement rotation and origin from JLCPCB's own footprint

**Why:** JLCPCB places each part at the position and rotation in the placement (CPL) file, measured against the footprint in its own library for that LCSC number, not against the KiCad footprint. Library footprints differ in their 0-degree orientation, their origin and sometimes their pad numbering. A generic community rotation table would have placed every three-pin transistor and diode 90 degrees wrong and an electrolytic capacitor reversed: the whole batch scrapped [REV]. KiCad's own export does not know JLCPCB's library either.

**Method** (`scripts/jlc_rotations.py`):
1. Fetch JLCPCB's library footprint for every LCSC code in the BOM (the EasyEDA footprint, with easyeda2kicad) into `vendor/jlc_fp/`, at the pace of section 4, reusing saved footprints.
2. For each part, turn JLCPCB's footprint by 0, 90, 180 or 270 degrees and move it until its pads land on ours, **pin 1 on pin 1**, pads matched by number. The rotation and the origin that give the least pad error are the CPL values. A fit needs at least two matched pads at different places, a counterpart for every pad of both footprints, and no other turn that fits as well on other pins (else the part is AMBIGUOUS, UNKNOWN).
3. Match **every two-pin part with a polarised footprint by its polarity mark**, read in both footprints (band, outline closed at one end, plus sign, chamfered corners; pin 1 = a diode's cathode, a capacitor's plus), not by pad number; a missing or contradictory mark leaves the part UNKNOWN.
4. Where the two libraries number pads differently, fit on the pads that mean the same pin (cases in section 9).
5. Write the table (part, LCSC, JLCPCB footprint, KiCad rotation, CPL rotation, CPL and KiCad positions, largest pad error) and generate the CPL from it.
6. **Test:** a second run re-derives everything and compares it with the CPL that will be uploaded; any mismatch fails. Report the largest pad miss per part; library variants differ in lead span, so misses of a few tenths of a millimetre were normal; each part has its own limit, 0.75 x the smaller side of the pads involved, at most 0.6 mm, and above it the part FAILs. The test proves consistency with the derivation, not physical correctness.
7. A part with no library data (a non-polar 1206 fuse) is declared with a written reason: DECLARED, NOT MEASURED, and it is checked in the placement preview.
8. For a panel, derive again on the panel itself, with `--project` (the footprint folder; each copy `<ref>_<n>` keeps the declarations and the bottom-side confirmation of `<ref>`).
9. Bottom-side parts: candidates until seen in a preview-only upload (`fab_package.py --preview`); the confirmation is bound to the checksum of the bottom-side mapping.

Then look at every polarised part in JLCPCB's placement viewer before paying (`order-flow.md` step 11).

## 9. Cases met

| Part | What JLCPCB's library does | What a shortcut would have done | Rule |
|---|---|---|---|
| SOT-23 transistors, diodes, references | footprint turned 180 deg from KiCad's | a community table gave -90 deg: all wrong | derive each one |
| Input electrolytic | correction 0 | the table gave +180 deg: reversed | polarised capacitors included |
| Schottky diode, SMA package | numbers the cathode pad 2 | matching by pad number turns it 180 deg | match two-pin polarised parts by their mark |
| SOT-89 regulator | pad 2 is the tab, origin at the tab's centre | our origin on the middle lead: offset | fit on outer leads 1 and 3 |
| PDFN 5 x 6 MOSFET | drain pins numbered 5 to 8 plus tab | our single drain pad does not match | fit on pins 1 to 4 |
| 4-pin wire-to-board headers | 180 deg, origin at the body centre (pin 1 + 3.81 mm) | origin at pin 1: shifted | take the origin from the library |
| USB-C receptacle | origin at the pad and slot centroid | other anchors shift it | take the origin from the library |
| 2.50 mm-pitch wire-to-board headers | library pitch 2.54 mm, the real part 2.50 mm | pad error about 0.26 mm | keep the true pitch; expect a query |
| SOIC-8 and SOIC-16 | +270 deg from KiCad's | - | derive each one |

Source: [DER] and [REV], 2026-11. A 2-layer part's X position was also off by the centroid convention until the fit used the pad patterns' bounding boxes [REV, 2026-11].

## 10. The assembler's engineer may still correct a rotation

- At the placement confirmation, JLCPCB's engineer had turned a buck converter in a leadless package by 90 degrees, because the CPL angle did not match JLCPCB's production library. The EasyEDA pattern of that part was itself turned 90 degrees and offset 0.08 mm from the one used in production [CONF, 2026-11].
- The change was correct. It was accepted only after checking in the viewer that pin 1 still landed on the design's pad 1.
- So: expect revised items, open each one, and verify pin 1 against the pads, never against the angle number.

## 11. Not recorded here

- Whether preferred parts pay the extended-part fee; the current fee per extended type.
- How life-cycle status is encoded in the parts data.
- The value of LCSC's small-order handling-fee threshold, and whether it is per line or per cart.
- Rate limits of either data service.
- Whether the community copy's class matches JLCPCB's on the day, and how old its data is.
- Whether JLCPCB's production library always matches the EasyEDA footprint (one case on record says not).
