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
  datasheet radius of the chosen cable must be given in `route.min_bend_r`).
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

### CB-12 Design to the widest tolerance the maker may draw
- Rule: ask the maker's standard tolerance and design every cable to work at the design tolerance (the widest one
  the maker may draw). A tighter one is not questioned: it is silently drawn at the standard. Keep a tight tolerance only where it is essential, say why on the drawing, and plan a revision
  round for it.
- Number: as read 2026-11: +-3 or +-5 mm (`[tolerance] standard_mm` of the capability sheet). The checks design for
  `[tolerance] design_mm` (seed: 5, PROVISIONAL: a branch asked at +-3 came back +-5; set 3 only after a production
  drawing shows +-3 held), else for the widest standard value. The drawing asks the narrowest standard (+-3).
- Check: `cable_check.py` row TOL ("the supplier draws its standard tolerance silently; design for it");
  `cable_second_measure.py` row TOL (the value asked) and rows REACH and SBEND at L - D, L, L + D, D = the design
  tolerance; their text also shows the result at the tolerance asked.
- Why: cables asked at +-1 and a branch asked at +-3 came back drawn at +-5, with no question.

### CB-13 Allowance by end type, and the reach floor (PROVISIONAL)
- Rule: design length = the larger of (longer measurement + allowance) and (the shortest path at the cable's minimum
  radius + the design tolerance D), rounded up to a whole millimetre, so that the shortest cable the maker may deliver
  still reaches. Crimped or plugged at both ends: a small allowance. An end that is trimmed and soldered at assembly:
  a generous one, cut to fit.
- Number: PROVISIONAL starting values, cables not yet on the bench: `allowance_crimped_mm` 2.0,
  `allowance_trimmed_mm` 10.0; D = 5 (`[tolerance] design_mm`). Where the second measure gives the reach
  (`route.second.reach_mm`) and the floor wins, the DESIGN row says "raised from <a> to <b> so the shortest cable the
  maker may deliver (L - D) still reaches" (the example harness: 65 to 67 mm; the example coax: 50 to 51). Without
  second-measure data there is no floor. A `route.allowance_mm` set by hand sets the first term; the floor still
  applies.
- Check: `cable_second_measure.py` rows DESIGN, LENGTH and REACH. REACH fails only when a length was forced below the
  design length by hand; SBEND at L + D stays the real limit (CB-14).
- Why: the first rule (route + 2, +-2) met a maker that works at +-3 and +-5; a crimped cable 2 mm longer than its
  route is up to 3 mm too short at -5.

### CB-14 Short stiff cables between two fixed ends: the S-bend risk
- Rule: a short coax or network cable between two fixed connectors on parallel axes takes an S. A few millimetres
  too long tightens the S below the minimum radius; too short and it does not reach. If no whole-millimetre length
  works at the design tolerance (the SBEND row at L + D says so), change the design: more offset, a longer run, an end trimmed at assembly, a more
  flexible cable. Do not tighten the tolerance.
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
  bare cable the route was designed for. A slim network cable came back as the standard thick one.

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
