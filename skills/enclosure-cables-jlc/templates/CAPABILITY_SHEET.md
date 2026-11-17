# How to read a supplier's pages into a capability sheet

A capability sheet is `<project>/mech/suppliers/<id>.capability.toml`: the list of what the supplier's forms and charts offer, with the date it was read. Later phases may order only what is on it. Start from the seed in `templates/` (`jlccnc-sheet-metal.capability.toml`, `lcsc-cable.capability.toml`), then re-read every value on the live pages. A value that was not read stays marked "assumed".

## Procedure

1. Open the supplier's quote form (as far as it shows without an order) and every help, guideline and FAQ page it links. List each page in `[meta] sources`.
2. Read the form field by field. For each field write its label and its options exactly as shown.
3. Read the charts (colours, inks, finishes). Copy the names letter by letter. A name that is not on the chart cannot be ordered.
4. Read the design-rule tables per thickness or process. Copy the numbers with their units.
5. Write what is NOT offered where the pages say so (or where a chart simply has no such option).
6. Set `[meta] read_date` and `status = "read live <YYYY-MM-DD>"` (a seed copied from the skill says `status = "seed"`: every gate summary then says "capability sheet NOT confirmed live" and the order plan carries it as a blocker). Before an order an independent agent re-reads the pages and corrects the sheet.

## What to look for

### Any supplier
- [ ] Working hours and time zone; holidays announced. -> `[hours]` (and `[supplier_hours]` in `mech.toml`)
- [ ] File types, the largest file, how many files per item or upload, how an archive must be built. -> `[limits]`
- [ ] Every free-text field of the form and its length limit. -> `[forms]`, `[limits]`
- [ ] The standard tolerances, and what happens when a tighter one is asked. -> `[limits] standard_tolerance`, `[tolerance]`
- [ ] The order steps and their names as the page words them (quote, review, pay, production, shipped). -> `[process]`
- [ ] Whether a submitted quote or order can be edited. -> `[process]`
- [ ] Shipping lines, who pays the duties, combine options. -> notes; details in `references/suppliers/shipping-and-combine.md`

### Sheet metal and machined parts
- [ ] Materials and tempers by the form's own names; thickness list. -> `[materials]`
- [ ] Largest and smallest part size. -> `[limits] max_length`
- [ ] Per thickness: bend radius, smallest flange, smallest flange after a second bend, hole edge to bend (round, square), U channel width. -> `[sheet_rules."<t>"]`
- [ ] Smallest hole, hole to hole, hole to edge. -> `[limits]`
- [ ] Hardware (press-in nuts, studs, standoffs): the list by code, hole size, edge and bend distances, the smallest sheet. -> `[[sheet.hardware]]` in `mech.toml`
- [ ] Finishes by name: powder chart (colour and gloss names), anodizing list, others. -> `[finishes]`
- [ ] Is masking offered? Partial coating? Colour-system numbers? Write "no" when the page does not offer it.
- [ ] Coating thickness, if stated.
- [ ] Printing (silkscreen, laser marking): ink chart, how it is priced, file format, smallest text height, line, gap, distance to edges. -> `[finishes] inks`, `[silk_rules]`
- [ ] An RGB value per chart colour and ink, from the supplier's own swatch picture (approximate). -> `[coat_rgb]`, `[ink_rgb]`
- [ ] Which form field takes the drawing PDF and which the print file.
- [ ] Countersinks, pockets, threads: offered in this thickness or not.

### Cables
- [ ] The form per cable family (harness, coax, network, other): which fields exist. Families with only "drawings + remark + quantity" need the drawing to carry everything. -> `[forms.<family>]`
- [ ] The standard length tolerance. -> `[tolerance] standard_mm`
- [ ] The stock defaults when nothing is said: wire type, cable type, connector make, pin order, sleeves. -> `[[stock_defaults]]`
- [ ] How two-row housings are numbered on their drawings; how pin 1 is marked. -> `[process]`
- [ ] The production-drawing step: Confirm and Revise per line, the note's length, pictures per note. -> `[limits] revise_chars, revise_pictures`
- [ ] Connectors they do not stock but make (for example moulded angled plugs).

### Printing service (when the concept is printed outside)
- [ ] Processes and materials by name; largest part; smallest wall and hole; tolerances; finishes; file types.

## Head of every sheet

```toml
[meta]
supplier = "<name>"
read_date = "<YYYY-MM-DD>"
sources = ["<page title or address>", "..."]
note = "as read <date>; re-read the live page before every order"
```
