# Design rules: cables and harnesses (CB-nn)

Read in phase 2 (first cable list), phase 5 (routes and lengths) and phase 9 (drawings). Cite a rule by its ID.

The supplier-side facts (form fields, stock defaults, tolerances) are in `suppliers/lcsc-cable.md` and in the
project's capability sheet. The parts of this file that wait for cables on a bench are marked **PROVISIONAL**: the
allowance by end type (CB-13) and the outcome of asking for non-default items.

How to read a rule: the rule; **Number** with its source; **Check**; **Why**.

## The list and the choices

### CB-01 Write the cable list early
- Rule: in phase 2, a first list: every cable, from where to where, connector family, number of wires, rough length.
  It includes fan leads, antenna cables, flat cables and anything bought ready-made.
- Check: the cable list template has a row per cable; `layout_study.py` cable rows.
- Why: the user had to ask for "a short list of the cables and where they connect".

### CB-02 Full interconnect check before any drawing
- Rule: before the first cable drawing, walk the whole device once: power to every board, every signal between
  boards, every radio path, every antenna feed and its supply, every fan, every panel part. Compare with the
  electronics skill's interconnect table. A cable found later means a new quote.
- Check: `cable_check.py --netlist pins.csv` (rows NET, KEY); the state file records "interconnect check done" with
  the date.
- Why: one forgotten feed changed cables after the quote was sent. A submitted quote cannot be edited: every
  cable was entered again as a new quote.

### CB-03 The user's choices come once, before any drawing
- Rule: ends (connector or solder), routes (over or under), cable types and colours are asked in one round, with
  suggested answers, and written in the state file.
- Check: the state file has the choices with the date and the user's words.
- Why: four choices arrived after the first drawings: a two-hour redraw.

### CB-04 One connector family; keyed and latching; no consumer cables inside
- Rule: use one crimp-connector family for all internal harnesses where current allows. Prefer keyed, latching
  housings to soldered wires and to consumer cables (a USB patch lead inside a product reads as unprofessional).
  Check gender and pitch on the mating board's own documents. Check live stock of housings and terminals.
- Check: `cable_check.py` rows ENDS and KEY; the stock answer saved in the project.
- Why: the user asked "why two different connector types on one board?", refused a consumer cable inside the box,
  and corrected a header's gender and pitch from the board's documents.

## Routes

### CB-05 Routes go under boards, with no loops, by default
- Rule: route along the floor and under board stacks, not over tall parts. No service loops: each cable is made to
  its route length. Ask before breaking either default.
- Check: route pictures of `cable_route.py` (top and side); look.
- Why: a power lead drawn over a board's connectors was sent back: "under it, not over it".

### CB-06 Measure from wire exit to wire exit
- Rule: a route starts where the wire leaves one connector body and ends where it enters the other. Connector bodies
  are listed apart and added for the overall length. The drawing states the definition in words.
- Number: `cables.json` `length_def`, for example "wire exit of P1 to wire exit of P2".
- Check: `cable_check.py` row LEN; the drawing's length note.
- Why: two measurements differed by several millimetres because each assumed a different connector body length.

### CB-07 A straight exit before the first bend
- Rule: a wire leaves a crimp housing or a plug straight for a few millimetres before it bends.
- Number: `[cables] min_straight_mm` default 3.0 (a starting value: verify). Use the real connector body from
  its maker's drawing.
- Check: `cable_route.py` row STRAIGHT.
- Why: bends drawn from the housing face cannot be made.

### CB-08 Bend radius by cable type
- Rule: every arc of a route is at or above the cable's minimum radius. Coax: the value on its datasheet. Network
  cable: about 4 times its outer diameter. Flat cable: by its maker. Wire bundles: a few diameters.
- Number: built-in types of `cable_common.py`: wire bundle R 5 mm, network 4 x OD, flat 5 x OD, coax none (the
  datasheet radius of the chosen cable must be given in `route.min_bend_r`). The cable maker's stock cables (as read
  2026-11, CB-26): a jacketed RG405 coax up to 2.6 mm outer diameter, radius from its datasheet; a Cat6 24 AWG
  network cable of 5.8 mm, about 23 mm (4 x OD).
- Check: `cable_route.py` row BEND; `cable_second_measure.py` (REACH at the minimum radius).
- Why: a thicker flexible coax could not be used at all: its radius needed more straight room than the box had.

### CB-09 Clearance and crossings
- Rule: every route keeps a gap to every solid and does not pass through another cable.
- Number: `[cables] clearance_mm` default 1.0.
- Check: `cable_route.py` rows CLEAR and CROSS (clearance ignores the cable's own connector solids along the whole
  route: look at the ends).
- Why: a first route crossed two wires of another harness.

### CB-10 Two independent measurements; the longer wins
- Rule: a second agent measures every route from the model without seeing the first numbers
  (`review-briefs/route-second-measure.md`). The compare takes the longer value. Every difference above the limit has
  a written cause in `route.note`.
- Number: `[cables] compare_max_diff_mm` default 2.0.
- Check: `cable_second_measure.py --compare --apply` rows CMP, DESIGN, FRESH.
- Why: the two measurements of one real project differed on several cables; each difference had a real cause (a body
  length, a pin row). One length was still wrong at the supplier for another reason (CB-18).

## Lengths

### CB-11 ONE length per harness
- Rule: all wires of one harness get the same length: the longest route plus its allowance. Shorter routes bow a
  little. No per-wire length table.
- Check: `cable_check.py` row LEN; `cables.json` has no per-wire length.
- Why: the maker threads the whole bundle through the housing, then crimps. Per-wire lengths brought a question and
  a day.

### CB-12 Design to the maker's tolerance floor
- Rule: ask the maker's tightest guaranteed tolerance, ask exactly that on the drawing, and design every cable to
  work over nominal +- that value. Never ask for less: a tighter value is drawn at the floor without a word, or
  costs a question round.
- Number: as read 2026-11: +-5 mm for every cable type, RF coax included (the maker's own statement;
  `[tolerance] standard_mm` and `design_mm` of the capability sheet).
- Check: `cable_check.py` row TOL ("the supplier draws its standard tolerance silently; design for it");
  `cable_second_measure.py` row TOL (the value asked) and rows REACH and SBEND at L - D, L, L + D, D = the design
  tolerance.
- Why: tighter tolerances asked on drawings came back drawn at +-5 with no question; a tighter one asked in a
  revision note cost a question round, and the maker then wrote that +-5 is the tightest it can guarantee.

### CB-13 The shortest cable still covers the route; allowance by end type (PROVISIONAL)
- Rule: a cable shorter than its route is the one fault that cannot be fixed in the box. Design length = the
  largest of (longer measurement + allowance by end type), (longer measurement + the design tolerance D: the route
  floor) and (the shortest path at the cable's minimum radius + D: the reach floor), rounded up to a whole
  millimetre, so the shortest cable the maker may deliver (L - D) still covers the route. Both ends fixed (coax
  between two jacks, a network cable between two sockets): route + D; the extra length up to route + 2D becomes one
  more bend at assembly, so the model must show room for it (SBEND at L + D, CB-14). An end trimmed and soldered at
  assembly: route + a generous allowance, cut to fit. A crimped harness: one length (CB-11), its minimum at least
  the longest wire's route; a branch to a third connector has its own single length by the same rule.
- Number: PROVISIONAL starting values, cables not yet on the bench: `allowance_crimped_mm` 2.0,
  `allowance_trimmed_mm` 10.0; D = 5 (`[tolerance] design_mm`), so crimped or plugged at both ends gives route + 5
  and a trimmed end route + 10. When a floor wins, the DESIGN row says "raised from <a> to <b> so the shortest cable
  the maker may deliver (L - D) is still as long as the measured route" (or "still reaches" for the reach floor).
  A `route.allowance_mm` set by hand sets the first term; the floors still apply.
- Check: `cable_second_measure.py` rows DESIGN, LENGTH and REACH. REACH fails only when a length was forced below the
  design length by hand; SBEND at L + D stays the real limit (CB-14).
- Why: the first rule (route + 2, +-2) met a maker whose floor is +-5: a cable 2 mm longer than its route is up to
  3 mm too short at -5, and every length had to be raised after the maker refused a tighter tolerance.

### CB-14 Short stiff cables between two fixed ends: the S-bend risk
- Rule: a short coax or network cable between two fixed connectors on parallel axes takes an S. A few millimetres
  too long tightens the S below the minimum radius; too short and it does not reach. If no whole-millimetre length
  works at the design tolerance (the SBEND row at L + D says so), change the design: more offset, a longer run, an end trimmed at assembly, a more
  flexible cable. Do not tighten the tolerance: it cannot be bought (CB-12).
- Number: an example: 1 mm more length can take a short coax from a comfortable radius to below its minimum.
- Check: `cable_second_measure.py` row SBEND (planar S between parallel axes only).
- Why: after a panel group moved a few millimetres, an already ordered short coax was left with a marginal bend.

### CB-15 Moving a panel part changes its cables
- Rule: after any move of a connector, run the build and read the route rows before saying "the cables still fit".
- Check: `build.py` (stale guard); FRESH row of the compare. The steps that write `cables.json` (route, compare with
  `--apply`) come first in `[[build.steps]]`; they rewrite it only when its content changes.
- Why: see CB-14.

## Drawings (the maker's own format)

### CB-16 Ends P1, P2, P3 and a wiring table
- Rule: name the ends P1 / P2 / P3. One wiring table, "P1 position (colour) -> P2 position", one row per cavity.
  State the wire standard and gauge. Check each wire's gauge against the terminal's crimp range. Every housing,
  plug, jack and terminal carries its maker part number and its supplier code: a blank or placeholder code (TBD,
  UNKNOWN) blocks the stage. A single coax has no wiring table: its drawing says "centre to centre, shield to
  shield".
- Number: crimp ranges are on the terminal's datasheet and on the maker's BOM line (for example one common 2.5 mm
  pitch terminal takes 22 to 28 AWG and one 2.0 mm pitch terminal 24 to 30 AWG: verify).
- Check: `cable_check.py` rows CODES and AWG; `cable_drawings.py` rows DRAW, OVERLAP, FIT, WORDS, PLACEHOLDER.
- Why: a wire thicker than the terminal's range was drawn into its crimp.

### CB-17 A cavity table for EVERY housing, EMPTY positions included
- Rule: list every position of every housing: wire colour or the word EMPTY. Add a picture of the housing face with
  position 1 marked.
- Check: `cable_check.py` row CAV; look at each cavity table against the wiring table.
- Why: a housing with an empty middle position came back with a wire in it; a housing with two empty positions came
  back wired in order and listed as a smaller part. Both rules had been written as remarks only.

### CB-18 Multi-row housings: numbering in words AND a picture
- Rule: a two-row housing is numbered by its mating header. Say it in words ("pin 2 is NEXT TO pin 1, in the other
  row") and show the pin-map picture.
- Number: as seen 2026-11: the maker's default numbers a 2 x n housing 1..n down one row and n+1..2n down the other.
- Check: `cable_check.py` row ROWS (the picture file must exist).
- Why: the two numberings differ for all pins but pin 1.

### CB-19 Angled plugs: an orientation picture with the quote
- Rule (the `picture` path in `cables.json` is relative to the folder of `cables.json`, e.g.
  `../out/cables/pictures/<file>.png`): for every angled or side-exit plug, a picture: which way the cable leaves at each end, where the latch is, and a
  coded `exit` (left, right, up, down) in the data; the sketch on the drawing is made from it.
  Upload it with the quote, not in a later message.
- Check: `cable_check.py` row ANGLE (orientation text, coded exit, picture file that exists); the field sheet's file list.
- Why: mirror-image right-angle plugs needed an extra message and a render. The picture was understood in minutes.

### CB-20 Labels
- Rule: a short label per cable (our part number, the end it belongs to), its position stated as "<n> mm from P1"
  (or P2), "<n> % of the length from P1" or "middle" (`label_position`; the drawing puts the label there). No
  product or board names (SKILL.md rule 20): "board", "PCB" and "module" are not allowed in a cable's `name` or
  `label`, which reach the supplier in the title block, the form's item name and on the cable.
- Number: `[cables] label_max_chars` default 24.
- Check: `cable_check.py` rows LABEL and TEXT (deny list from `[project] name` and `[cables] deny`, plus the words
  board, PCB, module); `cable_drawings.py` row LABELPOS (an unreadable position fails).
- Why: labels came back right the first time; a product name in a label would have gone to a supplier.

### CB-21 Exact cable wording: "X, NOT Y"
- Rule: for every item where you want something other than the maker's stock default, write what you want and what
  you do not want, in the form "X, NOT Y", first in the free-text field and on the drawing. Never a bare family name.
- Number: stock defaults as seen 2026-11 are in the capability sheet's `[[stock_defaults]]`.
- Check: `cable_check.py` rows SPEC and NONDEF (every stock default is either in `non_defaults` or in
  `accept_defaults`).
- Why: a bare coax family name was read as the maker's stock version of that family: jacketed and thicker than the
  bare cable the route was designed for. A slim network cable came back as the standard thick one. Both then proved
  to be the maker's only stock (CB-26): "X, NOT Y" gets what the maker makes, not what it does not.

### CB-22 No loose extras
- Rule: a cable order holds cables. Spare heat-shrink, spare terminals and loose parts go into the parts order.
- Check: `cable_check.py` row EXTRA (`extras` must stay empty).
- Why: "plus two loose heat-shrink sleeves" came back fitted on the wires.

### CB-23 One value per item, nothing internal
- Rule: no alternatives, no "please confirm", no questions, no clearance notes, no model part names on a drawing.
  No placeholder text ("TBD", "UNKNOWN", "to verify", "to read"): a note for yourself goes in `note_internal` (on
  the cable or its part), which is never drawn.
- Check: `cable_drawings.py` rows WORDS and PLACEHOLDER; `catalogue_scan.py` on the upload folder.
- Why: "please confirm +-2; if not, use the other column" invited the only question of the quote.

### CB-26 Design for the maker's only stock
- Rule: where the maker stocks one cable for a type, design the route, the bend radii and the clearances for that
  cable from the start, and accept it as a default. A cable it does not stock means a custom tool (a mould for
  moulded plugs) at a high cost, or the line refunded: budget it with the user before the quote, or buy a ready-made
  cable instead (an angled patch cable).
- Number: as read 2026-11 (capability sheet `[[stock_defaults]]`): RF coax only blue FEP-jacketed RG405, 2.2 to
  2.6 mm (size for 2.6); network cable with moulded 90-degree plugs only Cat6 24 AWG, 5.8 mm (a slim 28 AWG of
  3.8 mm needs a custom mould).
- Check: `cable_check.py` row NONDEF (the stock cable in `accept_defaults`); `cable_route.py` rows BEND and CLEAR with
  the stock diameter and radius; the cable-drawing review (h).
- Why: cable types the maker does not stock came back as e-mail questions after the first revision round, one with
  a custom-mould price, and the routes had to be checked again for the stock cables.

## Quick formulas

### CB-24 Voltage drop
- Rule: drop = current x resistance of the go and return wires. Compare with what the load tolerates.
- Number: copper, standard tables, approximate: 20 AWG 0.033, 22 AWG 0.053, 24 AWG 0.084, 26 AWG 0.134, 28 AWG
  0.213 ohm per metre. Example: 300 mm of 24 AWG at 1 A, go and return: about 50 mV.
- Check: a row per power cable in the check list.
- Why: a length limit set by habit was waived once the drop was written down.

### CB-25 Radio-frequency loss
- Rule: loss = cable loss per metre at the frequency x length + a little per connector. Loss per metre scales about
  with the square root of the frequency. Take the figure from the cable's datasheet.
- Number: take the loss per metre at your frequency from the datasheet; a cable of a few centimetres with two
  connectors adds a small fraction of a dB.
- Check: a row per radio cable in the check list.
- Why: none failed; the number answers "does the short cable matter?".
