# Remark for <part> (pasted into the form's remark field, word for word)

Save as `orders/REMARK_<part>.md`. The text between the lines below is what the supplier sees.

## Rules
1. Only what the form fields cannot say. If a field says it, the remark does not.
2. Chart names only, the same names as in the fields. No colour-system numbers or names.
3. Nothing that contradicts a field. Nothing about a feature this part does not have.
4. No requests the supplier covers by its own standard (deburring, thread protection, edge break).
5. No "if possible", "fallback", "preferably", "please confirm", no question, no alternative.
6. No masking and no partial coating, unless the capability sheet shows the supplier offers it.
7. No product, board or project names. Our part number only.
8. Three or four short lines.

## The text

---
```
Part <our part number>.
<Finish as in the field, e.g.: All-over powder coat <chart name>, same batch for parts <numbers>.>
<Hardware: Clinch nuts per the table on the PDF, sheet <n>.>
<Print: file <part>_silk.dxf; layer colour = ink; inks: <chart names>; ink sheet: PDF sheet <n>.>
```
---

For a raw part with no finish and no hardware the whole remark may be: `Part <number>. No finish. Drawing in the archive.`

## Before it goes
- [ ] Every finish and ink word is on the capability sheet of <date>.
- [ ] `scripts/catalogue_scan.py` finds nothing in this file.
- [ ] No line repeats or contradicts a form field (compared with `FIELD_SHEET_enclosure.md`).
- [ ] No line names something this part does not have.
