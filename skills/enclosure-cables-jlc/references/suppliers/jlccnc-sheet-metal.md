# Supplier notes: JLCCNC, sheet metal

**As read 2026-11; re-read the live page before every order.** Sources: the supplier's public help pages and quote
tool, and one real order. One order is one data point. The machine-readable copy of these facts is the capability sheet
(`templates/jlccnc-sheet-metal.capability.toml`, copied to `<project>/mech/suppliers/` and corrected in phase 1).
Where this page and the live site differ, the live site wins and the difference goes into the project's lessons.

Still **PROVISIONAL** (waiting for parts on a bench): whether zones drawn as bare came coated, clean nut threads, the
real coat and ink colours against the chart, cut-outs after the coat, the real lead time after a production hold.

## 1. Services

- Laser cutting, bending (right-angle, U, V, step, hem), pressed hardware (clinch nuts, studs, standoffs), riveting.
  Laser welding only on request: "not included by default".
- No extrusion. A sister shop of the group sells stock extruded cases (`standard-cases.md`).
- Minimum order: 1 piece. Instant online quote from a STEP file, then an engineer's review before payment.
- Sheet-metal orders are submitted first and paid after approval.

## 2. Materials and thicknesses

- Aluminium 5052. Also stainless (two grades), cold-rolled steel, galvanized steel: their rules were not read.
- Thicknesses: 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0 mm. Longest part 800 mm.
- The design rules per thickness: `design-rules/sheet-metal.md` and the capability sheet's `[sheet_rules]`.

## 3. Finishes and the two charts

There are two charts. Order by their names only.

- **The powder-coat chart** (12 names, as read 2026-11): Black Glossy, Black Matte, Gray Glossy,
  Gray Matte, Blue Glossy, Blue Matte, Green Glossy, Green Matte, Yellow Glossy, Red Glossy, White Glossy, White Matte.
- **The silkscreen ink chart** (12 names): Black, White, Gray, Brown, Yellow, Orange, Red, Dark Blue, Light Green,
  Dark Green, Light Blue, Sky Blue.
- Anodizing for aluminium sheet: Natural, Black, Silver, Dark Gray, Red, Pink, Sky Blue, Dark Green, Champagne; matte
  or glossy. Also conductive anodizing and hardcoat anodizing (colour range not read). Laser marking (one tone).
- **No RAL, no Pantone.** A colour-system name is not made: the supplier asks, or substitutes its nearest chart
  colour.
- **No partial coating, no masking.** The factory coats all over. Plan ground bonds another way
  (`design-rules/shielding-and-ground.md` SG-06).
- Silkscreen is a second finish on top of the first, one screen per ink, printed on the cured coat.
- Hardware is pressed before the coat by the supplier's own standard. Ask nothing about plugged threads.
- Colours seen on the chart picture are approximate: a chart name can read as another hue on the screen; the
  chart's "Gray" ink is light. Judge on the first samples.

## 4. The quote form, field by field

| Field | What it holds | Notes |
|---|---|---|
| Upload | The 3D file, or a ZIP | One ZIP per part worked: STEP (AP203) + PDF drawing + print DXF, all named as the part. Up to 10 files per upload were accepted (the help page read 20), each under 100 MB |
| Material / Type | Aluminium, then the alloy | |
| Thickness | No field | The tool reads it from the STEP |
| Surface Finish | First finish: type, chart colour, matte or glossy; or none | The same chart name on every part that must match |
| + Add finish | Silkscreen (colour mode: one ink, two inks, or "customized" for three and more) with its own file field; or laser marking | One silkscreen file per part: put all printed faces in one DXF |
| Threads and Tapped Holes | Yes or No | Yes opens "+ Add file" for the drawing with the hardware table. No gives no file field: the PDF inside the ZIP still reaches the reviewer |
| Quantity | Per part | |
| Product Desc | A category | Bent parts: the bending/welding category. Flat parts: the flat category. A wrong category is a question |
| Build time | Standard, or faster where offered | With a finish the standard was 5 days |
| Remark | Free text | See section 5 |

A bent part shows "manual quote" for half a minute to two minutes after upload. That is normal.
The quote page may show shipping only to the account's region: use the supplier's shipping calculator page for the
real destination.

## 5. The remark

The remark only adds what the fields cannot say, in the supplier's words, and contradicts nothing. Model
(`catalogue_scan.py` must pass on it):

```
All-over powder coat <chart colour>, same batch for <part>, <part>. Clinch nuts per the PDF table.
Silkscreen: <file name>; layer colour = ink; inks <chart names>; see the ink legend on sheet <N>.
```

For a raw inside part: `Raw 5052, no finish, deburred. Drawing in the ZIP.` That text raised no question.

Leave out: colour-system names, "if possible", "fallback", masking, "threads plugged", "edge break", anything about
a part that does not apply to THIS part.

## 6. Review behaviour

- **Each part has its own reviewer, and the order waits for the slowest.** The part that was held was not the
  unusual one: another part with the same remark passed. Splitting the order would not help; clean text on every
  part does.
- **No "review completed" mail.** The only signal was a mail that an automatic payment had failed. Watch the order
  page: the pay button appears only after every part is reviewed. A held part shows as pending with "a confirmation
  e-mail has been sent to you".
- Questions arrive by e-mail with a subject that names the part's own number. Two people may answer the same
  question in separate threads: read every new thread about the part before deciding it is closed.
- The live chat on the order page reaches the same team. It does not speed up a review; on a slow production step
  it gives a date, not a faster run.
- **The file review does not check the print file's inks.** That question came at the print step, after payment,
  during production (`design-rules/panel-graphics.md` PG-10 to PG-14).

## 7. Times seen (one order, 2026-11)

| Step | Seen | Plan with |
|---|---|---|
| Review of a plain part | about 12 hours after a submit at their night | the same working day when submitted before their morning |
| Their reply to one of our answers | under an hour inside their hours | |
| The review step after each answer | 16 to 24 hours | one working day per question (SKILL.md rule 12) |
| A part with questions | more than two days in review | |
| Promised times on page and chat | "10 to 60 minutes", "2 to 3 hours" | are estimates |
| Production: raw parts / powder / powder + silkscreen | 4 / 6 / 7 days, as planned by the order page | the tool said "standard 5 days" |
| Silkscreen after the powder coat | 2 to 3 days on its own | plan 2 to 3 days for a printed part; the whole order ships only when its slowest part is done |
| To the shipping centre, then express | about 1 day, then 2 to 4 days | |

A payment after their evening starts production a working day later (`order-flow.md`).

## 8. How the total moved

- Instant quote to reviewed quote: a little more (items the instant quote had missed were added).
- **Review page to pay step: a clear rise of the total**, all of it in shipping and duties. The reason
  was not recorded. Read the shipping line and the total again at the pay step (SKILL.md rule 14).
- Coupons were offered at payment and not used: check them.
- Rough orders of magnitude from that one past order: a second set cost clearly less than a second full price; the
  coat and the print were most of the largest part's line.

## 9. What they asked about, and what passed without questions

Asked (each cost about one of their working days):

1. "Partial powder coating": the drawing showed masked zones.
2. "The colour must be from the chart": the remark said a colour-system name "if possible". The field was right.
3. "No such ink": the print file's CAD layer colours were read as inks (black text on the default index 7 nearly
   became white ink; a closed magenta helper shape). A corrected file with the cut edges on a green layer and the
   bend lines on a yellow dashed layer, BYLAYER, open lines and arcs only, and an ink sheet that listed both as "NOT
   printed", drew no question about them. Whether the factory ignores a layer by its name is NOT known: never
   use index 7 in a print file.
4. Two more rounds were self-made: an answer that added a line about nuts on a part with no nuts, and an extra
   "please confirm" mail.

Passed with zero geometry questions (margins in `design-rules/sheet-metal.md`): holes 0.5 beyond the hole-to-bend
minimum; nuts 7.5 from a bend; second bends at 8.5; a U of 12.5 inside; very small bent brackets; tray and lid as
separate parts; capitals 2.3 high with gaps of 0.35; print 1.0 from cut-outs; fully dimensioned PDFs; AP203 STEP;
pressed nuts of the CLS family modelled in the STEP and named in a table.

## 10. Before an order: read these live pages into the capability sheet

Sheet-metal fabrication guidelines (the bend table is a picture); file requirements; supported materials; the
appearance standard; the quote tool's finish lists; both charts; the shipping calculator; the combine-orders help
page; the customs page for the destination. An independent agent does this
(`review-briefs/supplier-rules.md`).
