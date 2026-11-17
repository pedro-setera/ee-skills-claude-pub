# <device name>, rev <A>: field sheet for the case order (<supplier>)

The value of every field of the quote form, per part. Phase 12 fills the form from this sheet and reads every field back; nothing is typed from memory.
Field names as read on the live form on <date> (capability sheet `suppliers/<id>.capability.toml`). A field the form does not have is not on this sheet: nothing is asked in its place.

## Rules for every value
- A finish, colour or ink is the chart name, letter by letter. The SAME coat name in every coated part.
- One value per field. No alternatives, no "if possible", no questions.
- The remark is `orders/REMARK_<part>.md`, pasted word for word.

## Parts
| Field (as the form words it) | <part 1: tray> | <part 2: lid> | <part 3> |
|---|---|---|---|
| File to upload (archive: STEP + PDF + print file + ink sheet + renders) | `out/upload/<supplier>/<part>.zip` | <> | <> |
| Item name (our part number) | <P-01 tray> | <P-02 lid> | <> |
| Process or category | <bent sheet metal> | <> | <> |
| Material | <as the form names it> | <> | <> |
| Thickness | <1.5 (read from the STEP if the form has no field)> | <> | <> |
| Surface finish 1 | <powder coat, "<chart name>"> | <the same> | <none> |
| Surface finish 2 (print) | <silkscreen, colour mode <n inks>; file `<part>_silk.dxf`> | <none> | <none> |
| Threads or hardware | <yes; PDF attached here: `<part>.pdf`> | <no> | <> |
| Tolerance option | <standard> | <> | <> |
| Quantity | <2> | <2> | <> |
| Product description (customs) | <generic, no product name> | <> | <> |
| Build time option | <standard> | <> | <> |
| Remark | `orders/REMARK_<part>.md` | <> | <> |

## Read-back (phase 12)
| Part | Every field equals this sheet | Seen on | Screenshot |
|---|---|---|---|
| <tray> | [ ] | <date time> | `orders/screens/<file>` |
| <lid> | [ ] | | |

## Totals seen
| Step | Parts | Shipping | Duties | Total | Seen on |
|---|---|---|---|---|---|
| Instant quote | <> | <> | <> | <> | <> |
| After the review | <> | <> | <> | <> | <> |
| At the pay step | <> | <> | <> | <> | <> |
