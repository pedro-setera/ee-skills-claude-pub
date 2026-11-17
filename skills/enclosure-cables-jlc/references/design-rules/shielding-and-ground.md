# Design rules: shielding and ground bonds (SG-nn)

Read in phase 4 (the ground-bond map and the arrival test list) and phase 8 (the metal version). Cite a rule by its ID.

This file is **PROVISIONAL**: the bond methods of SG-06 and the continuity target of SG-07 wait for an assembled
metal box to be measured. The aperture and seam rules are general practice with approximate formulas. They give a
first design, not a compliance result: a product that must pass a radio or emission test needs that test.

A radio that must be shielded, or must pass through the box, raises the review set (SKILL.md, Reviews).

How to read a rule: the rule; **Number** with its source; **Check**; **Why**.

### SG-01 Apertures against the wavelength
- Rule: for the highest frequency that matters, list every opening by its LONGEST dimension: windows, connector
  cut-outs, slots, vent holes, gaps in seams. A slot shields by its length, not its area.
- Number: general practice, approximate: wavelength in mm = 300000 / f in MHz. A single slot of length L shields
  about 20 x log10(wavelength / (2 x L)) dB: nothing at half a wavelength, about 14 dB at a tenth, about 20 dB at a
  twentieth. General practice: holes far below a tenth of the wavelength; any opening near half a wavelength is
  listed as the main leak to test.
- Check: an aperture table in the check list: opening, longest dimension, fraction of the wavelength, verdict or
  "test on arrival". Not scripted. Look at every face.
- Why: the largest opening of a box was missed until the independent review.

### SG-02 Many small holes instead of one large opening
- Rule: a vent is a field of small round holes, never long slots, when the box must shield.
- Number: see SG-01. General practice, approximate:
  N equal holes that lie within about half a wavelength of each other leak about 20 x log10(sqrt(N)) = 10 x log10(N)
  dB more than one of them (100 holes: about 20 dB less shielding than one hole). Count the field, not one hole, in
  the aperture table.
- Check: `box_toolkit.hex_field`; the aperture table.
- Why: the printed concept's slots were replaced by hole fields in metal for this reason and for looks.

### SG-03 Seams and screw pitch
- Rule: a seam between two metal parts is a slot between its points of contact. Contact needs bare metal on bare
  metal, pressed together. The distance between screws (or contact points) is the slot length of SG-01.
- Number: none proven: contact points far closer than half a wavelength, bare bands pulled together between them;
  test on arrival.
- Check: the ground-bond map marks every seam, its contact method and its screw pitch; the arrival test (SG-09).
- Why: with an all-over coat the lid of the first metal design floated electrically: no seam had contact.

### SG-04 Gaskets only where they are compressed, never where parts slide
- Rule: a conductive gasket works when squeezed straight between two faces. On a face that another part slides over,
  it is scraped off.
- Check: `parcheck.py` sweep of the lid's assembly path against the gasket solids; look at the assembly order.
- Why: side gaskets were drawn on a lid that slides down over them; the independent review caught it.

### SG-05 Panel jacks instead of board-edge connectors through oversize holes
- Rule: a radio-frequency connector soldered on a board and poking through an oversize panel hole leaves a ring-shaped
  gap and no shell bond. Use a panel (bulkhead) jack bonded to the wall, joined to the board by a short coax, and
  terminate unused ports.
- Check: `fit_check.py` connector rows; the ground-bond map row per jack; `layout_study.py` panel-part reach.
- Why: the user saw "a lot of extra room around the holes, making it easy for the signal to leak" on a concept.

### SG-06 Bonding with an all-over coating (PROVISIONAL)
- Rule: suppliers coat all over unless their own page offers masking (SKILL.md rule 1). Decide in phase 4, for every
  bond, which of these makes the contact, and write it in the ground-bond map:
  1. Bare inner parts: brackets and plates inside stay uncoated and carry the bond.
  2. Internal-tooth lock washers under jack flanges and screw heads: the teeth bite through the coat.
  3. A conductive finish, only if it is on the capability sheet (for example a conductive anodizing).
  4. Scraping the coat off named seats at assembly: listed as hand-work with its minutes, a step in the manual, and a
     tap of the right size for coated threads.
- Number: PROVISIONAL, none measured yet: list the minutes per box from a timed trial.
- Check: the ground-bond map has a method per bond and no row "masked by the supplier"; `catalogue_scan.py` finds no
  "mask" word; the continuity test (SG-07).
- Why: the first design relied on masked zones. The supplier does no masking; the whole bond design became hand
  scraping after the order was placed.

### SG-07 Continuity target under 1 ohm, measured at assembly
- Rule: before the lid goes on, measure from the case to each board's ground, each jack shell and the lid. The value
  and the meter go into the fit report.
- Number: target under 1 ohm (general practice for a low-frequency bond; it does not prove radio-frequency
  shielding). PROVISIONAL until measured on a real box.
- Check: a row per bond in the arrival test list; the user measures.
- Why: a bond that is drawn but not measured was the state of the first design.

### SG-08 Know where a ground must NOT bond
- Rule: the ground-bond map also lists the holes and shells that stay isolated: unplated mounting holes, a connector
  shell bonded on the board through a part, anything the electronics side says must float. Their seats stay coated.
- Check: the ground-bond map against the electronics skill's list of grounded holes (`interface.json`: each hole's
  `plated` and `net`); look.
- Why: bonding every standoff seat would have tied a deliberately isolated shell to the case.

### SG-09 A radio inside a metal box needs a test plan
- Rule: an antenna inside a closed metal box barely reaches out. A transmitter inside must not leak. Either way, write
  the test before the metal is ordered: what is measured, with what, from where, pass value, and the fallback (an
  external antenna on a panel jack, a non-metal window, a film on a display window, a ferrite on a cable).
- Number: none; "does it work at 3 to 5 m" is a user-level test, not a measurement.
- Check: the arrival test list has the radio rows; the gate 2 summary names the risk.
- Why: general practice: an antenna inside a closed metal box barely reaches out, and the cheap test is easy to skip.

### SG-10 The foil-wrapped concept is a cheap early test
- Rule: wrap the printed concept box in aluminium foil, close the seams with tape, and run the link or the leak test.
  It is crude and pessimistic at seams, but it costs nothing and comes weeks before the metal.
- Check: a row in the print findings.
- Why: the test is cheap and early; skipped, the risk moves to the first metal samples.

### SG-11 Keyed, polarity-safe connectors
- Rule: every internal power connector is keyed and cannot be mated reversed or one pin off. Mark polarity next to
  any solder joint or screw terminal. Leads that can fold onto each other inside a closed box are tied or sleeved.
- Check: `cable_check.py` rows KEY and ENDS (with `--netlist`); look at each connector tile.
- Why: an unkeyed lead was folded inside a closed concept box, reversed supply and ground, and burnt.

### SG-12 Cables are apertures too
- Rule: every cable that leaves a shielded box carries noise out unless it is filtered or bonded at the wall. List the
  leaving cables and what is done at each (bonded shell, filter on the board, ferrite as a fallback).
- Check: the ground-bond map; the electronics skill's interconnect table.
- Why: a ferrite on a power cable was listed as the fallback if the leak test fails.

### SG-13 Maintenance
- Rule: bare contact zones dull with time. Say in the manual how to check (the continuity test) and clean them.
- Check: the manual has the line.
- Why: none yet.

## The ground-bond map

One table, written in phase 4 and kept through phase 15:

| Bond | Where | Method (SG-06) | Hand-work, minutes | Must NOT bond? | Test at assembly |
|---|---|---|---|---|---|
| lid to tray | side seams | bare inner bands, screws every N mm | ... | no | under 1 ohm |
| jack shell | front wall | internal-tooth washer inside | 0 | no | under 1 ohm |
| board mounting hole H1 | floor | none | 0 | yes (unplated) | open circuit |

It goes back to the electronics skill as "which holes must be plated and grounded" (`interface-electronics.md`).
