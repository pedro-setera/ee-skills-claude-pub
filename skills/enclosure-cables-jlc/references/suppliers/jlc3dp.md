# Supplier notes: JLC3DP (3D printing as a service)

**Not proven by an order.** No printed part has been ordered from this supplier with this skill. The concept boxes
behind this skill were printed on the user's own FDM printer. **As read 2026-11; re-read the live page before every
order.** Almost nothing below is a number: the numbers must be read on the live pages in phase 1. Say "not proven by
an order" to the user when a project uses this file.

## When it is the right route

- The user has no printer, or the part does not fit the bed, or needs a material the user cannot print.
- A small batch of a part that would be hand-work at home.
- A process that home FDM cannot give: fine detail (resin), strong nylon parts (powder processes), metal.

For a first concept the home printer stays the cheapest and fastest loop (SKILL.md rule 10): a misfit is fixed and
reprinted the same day. With an outside printer every loop costs shipping time. Offer it with its cost and lead time.

## What was read (2026-11)

- The group's CNC site lists 3D printing "via JLC3DP" with processes including resin (SLA), powder-bed nylon (MJF,
  SLS), metal (SLM) and FDM. A starting price well under one USD was advertised for the smallest parts.
- Orders of the group's shops can share one cart and payment (`shipping-and-combine.md`).

Nothing else was read. In particular NOT read: materials per process, colours, smallest wall and hole, tolerances,
largest part, how threads and inserts are handled, lead times, file types, the quote form's fields.

## What to read on the live pages and put into the capability sheet

Make `<project>/mech/suppliers/jlc3dp.capability.toml` in phase 1, with the read date:

| Read | Put into the sheet |
|---|---|
| Processes and the materials of each | `[materials]` (one list per process) |
| Colours and surface options per material | `[finishes]` |
| Design guideline per process: smallest wall, smallest hole, clearance between mating parts, smallest text, largest part | a `[print_rules."<process>"]` section of your own |
| Stated tolerance per process | `[limits] standard_tolerance` |
| File types and the size limit | `[limits]` |
| The quote form: every field in order, the free-text field | `[forms]` |
| Lead time per process, review step, payment cut-off | `[process]`, `[hours]` |

## How the skill's print rules carry over

- `design-rules/fdm-printing.md` is written for FDM on a known printer. For an outside FDM service the layer
  direction rules (FDM-04, FDM-05) still hold, but the print pose is the supplier's choice unless their form lets you
  set it: design so that no pose is weak, or state the pose in a field if one exists (never in a remark that the form
  does not offer).
- For resin and powder processes the FDM overhang and bridge rules do not apply; wall, hole and clearance minimums
  come from the supplier's guideline. Powder-bed parts need escape holes for trapped powder in hollow shapes.
- The test coupon (FDM-21) calibrates one printer. For an outside process, order the coupon WITH the first part, or
  order one part first: hole shrink and fit are unknown until measured.
- `print_check.py` audits against a printer profile. Make a profile for the outside process from the supplier's
  guideline; the slicer rows read "could not run".
- `catalogue_scan.py` works with the new capability sheet: materials and colours only by the supplier's names.

## What is not known

Review behaviour, real lead times, how the totals move, accuracy of delivered parts, how the supplier orients parts.
After the first order, write these into the project's lessons and propose them for this file (phase 16).
