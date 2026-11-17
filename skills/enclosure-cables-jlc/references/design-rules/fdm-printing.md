# Design rules: FDM printing (FDM-nn)

Read in phase 6 (design for printing) and by the model reviewer in phase 7. Cite a rule by its ID.

How to read a rule: the rule; **Number** with its source ("from one real project, verify" means one printer, one
material, one box: a starting value, never a constant); **Check** (a script of this skill, or "look"); **Why** (the real
failure, told without names).

The printer's own numbers win over every number here. They live in the user's printer profile (outside the skill) and
come from the test coupon (FDM-21). Never change the user's slicer settings (SKILL.md rule 15).

## Orientation and splitting

### FDM-01 Choose the print pose of every part first, then design for it
- Rule: decide which face lies on the bed before any detail is drawn. Every later rule is judged in that pose.
- Check: `print_check.py PART.step --pose <face>`; look at the slicer preview in that pose.
- Why: a rear panel printed upright made every bar in its grille a tall stack of thin layers. The grille snapped by hand.

### FDM-02 Split the box into parts that print flat with no or little support
- Rule: a U shell (floor + two walls) and a U lid (top + two walls) print flat with almost no support. Print a bracket
  or a clamp as its own part rather than as a supported outgrowth of the shell.
- Check: slicing report of `print_check.py --slice`: support grams per part; look.
- Why: a bracket drawn as part of the shell needed supports everywhere; printed apart, plate down, it needed none.

### FDM-03 Each part fits the bed with margin
- Rule: the part's box in print pose fits the bed of the printer profile.
- Number: profile `[printer] bed`. The script's default without a profile is 220 x 220 x 250 mm.
- Check: `print_check.py`, bed row.
- Why: none from the project; the check is cheap.

## Strength: layers are the weak direction

### FDM-04 No thin part standing on a thick one with a flat step
- Rule: where a narrow section rises from a wide one, join them with a cone or taper of 45 degrees or less from
  vertical and a small fillet at the root. Never a flat step. The same inside a bore: a screw seat is a 45 degree cone,
  not a flat ledge over a hollow.
- Number: from one real project, verify: a leg running into a narrower foot through a 45 degree cone with a small
  root fillet held; the leg's wall was 4 perimeters.
- Check: `print_check.py`, the "thin on thick" step rows (heuristic: they must be LOOKED at in the slicer preview);
  slicer marks "overhang wall" at the step.
- Why: a leg stepped flat from a wider tube to a narrower foot. The foot's first layers had almost nothing under them
  and the leg snapped there on the first assembly.

### FDM-05 No thin upright bars that carry load
- Rule: a feature that prints as a tall, thin stack of layers (a grille bar, a clip, a rib standing on the bed side)
  must not carry load. Replace bars by a perforated plate (FDM-13) or turn the part so the bar prints lying down.
- Number: from one real project, verify: thin upright bars broke; thicker webs in a perforated plate held. Thin bars
  printed FLAT on the bed (continuous extrusions along their length) held.
- Check: `print_check.py` thin-wall rows in print pose; look.
- Why: thin fan-guard bars, printed upward, snapped along their layer lines with a light push.

### FDM-06 Walls at least 2 extrusion widths, structural webs thicker
- Rule: no wall thinner than 2 extrusion lines. Webs between holes, bars and anything that carries load: 5 lines or more.
- Number: profile `[rules] min_wall_lines` (default 2) x `line_width`. A starting value, verify: box walls and webs of
  about 5 extrusion lines with a 0.4 mm nozzle.
- Check: `print_check.py` thin-wall rows (sampled sections: a feature thinner than one sample step can be missed).
- Why: a tube wall of 2 perimeters was the leg that broke in FDM-04.

### FDM-07 Layer counts under and around posts
- Rule: everything that rises from a floor (posts, blocks, panels, ribs) must start on solid material, not on sparse
  infill. Small load-carrying parts print with more walls and full infill.
- Number: a starting value, verify: 0.2 mm layers, 4 walls, 5 top layers, and as many bottom layers as the floor
  thickness divided by the layer height, so that the floor prints solid; small brackets 4 walls and 100 % infill. These are slicer settings: propose them, the user sets them.
- Check: slicer preview section through a post; slicer mark "floating vertical shell".
- Why: with the default 2 walls and 15 % infill the slicer showed a bracket's legs standing on sparse infill.

## Overhangs, bridges, holes

### FDM-08 Overhangs 45 degrees or less from vertical
- Rule: no unsupported face steeper than the profile's limit. Use chamfers, keels under horizontal posts and teardrop
  or pointed tops on horizontal holes. Where the user accepts supports, say where they go; ask before adding shapes the
  user did not want.
- Number: profile `[rules] max_overhang_deg` (default 45).
- Check: `print_check.py` overhang rows; slicer "overhang wall" marks; the coupon's overhang ladder (30 to 60 degrees).
- Why: horizontal posts had a 90 degree overhang underneath and needed support until a 45 degree keel was added.

### FDM-09 Keep bridges short and say which ones are left
- Rule: flat ceilings over openings are bridges, and so is the roof of a round hole in a vertical wall up to the same
  limit (a field of small vent holes is one passing row). Keep them under the profile's limit or list them for the user as
  "support here" or "accepted bridge".
- Number: profile `[rules] bridge_max_mm` (default 8). From one real project, verify: a bridge a little over that
  limit, over a small cut-out, printed acceptably in PLA; a long window top needed support.
- Check: `print_check.py` bridge notes; slicer "bridge" marks; look at the underside in the preview.
- Why: none broke; the list avoided surprises at the print.

### FDM-10 Draw holes larger by the printer's measured shrink
- Rule: holes and tight pockets print smaller than drawn. Add the coupon's measured value to every hole and pocket.
  Do not also switch on the slicer's hole compensation.
- Number: profile `[rules] hole_shrink_mm`; the code default 0.3 mm on the diameter is a first guess until the
  coupon measures it. That is an example, never a constant.
- Check: coupon rows of holes at nominal +0.0 to +0.5 mm; after-print list (FDM-22).
- Why: a hole drawn 2.4 mm printed 2.1 mm and a screw head did not pass its tunnel. The first shell was scrapped.

### FDM-11 Self-tapping posts: conical, flared at the root, pilot from the coupon
- Rule: a screw post is a cone (wider at the base), with a 45 degree flare where it meets the floor, and the pilot
  hole runs down to the floor so the post prints as a solid-walled tube. Posts carry only the screw's clamp load.
- Number: starting values to calibrate, from `box_toolkit.py` table `SCREWS`: pilot about 0.8 x thread diameter
  (M2 1.6, M2.5 2.0, M3 2.5, M4 3.3), post diameter 5 / 6 / 7 / 9 mm. On a printer that prints holes small, the drawn
  pilots end a few tenths above these: take them from the coupon.
- Check: coupon post per screw size: the screw starts by hand and does not strip; look at a section in the preview.
- Why: a pilot hole that stopped above the floor left a hollow core under a bridged hole bottom.

### FDM-12 Countersinks and counterbores from the real screw
- Rule: measure or read the screw's head diameter and head angle. Draw the cone at that angle and the diameter plus
  the hole shrink. Fan screws are often not 90 degrees.
- Number: measure the head angle; where screws of two head angles may be used, a cone at the smaller angle seats both,
  and a cone at the larger angle leaves the sharper head proud.
- Check: after-print list: the head sits flush or just under; look at the render with the real screw model.
- Why: lid holes drawn without cones left the heads proud; the user wanted them flush.

### FDM-13 Vent grilles are perforated plates with complete patterns
- Rule: a vent is a plate with a regular field of holes, not a row of bars. On a wall that prints upright use
  pointy-top (tall) hexagons whose roofs are 30 degrees from vertical: no bridge, no support. The pattern is complete:
  on a collision move the whole group by whole pitches, never drop single holes.
- Number: a starting value, verify: webs of at least 5 extrusion lines (FDM-06) in a plate thick enough to carry
  them.
- Check: `box_toolkit.hex_field` (shifts the whole group, raises an error when nothing fits); look at every vent group.
- Why: holes left out to clear a screw read as a defect and the user sent the part back.

## Fits

### FDM-14 Mating parts get clearance, never a tight fit
- Rule: parts that slide together or over each other get a designed gap per side. The gap is a named parameter.
- Number: from one real project, verify: a few tenths of a millimetre per side between a shell and its lid fitted on
  one printer.
  Take the real value from the coupon's tab-and-slot pair (three clearances).
- Check: coupon; after-print list: the lid slides on by hand.
- Why: the user had to ask whether the model had any clearance at all. It must be visible as a number.

### FDM-15 Panel-mounted parts: the hole fits the part as PRINTED
- Rule: for every part that passes a wall, the drawn hole is the part's size plus the play wanted plus the shrink.
  A snap-in part needs the maker's own cut-out size after printing.
- Number: an example: a threaded jack in a hole drawn about 0.45 mm over its thread printed with a little play.
- Check: `fit_check.py` connector rows; after-print list.
- Why: see FDM-10.

## Materials

### FDM-16 Material by job
- Rule: PLA for the concept (cheap, easy, thrown away). ABS, ASA or PETG when the part sits near heat or in a car.
  Ask the user which they have; some users rule one out.
- Number: typical softening points, approximate, verify on the filament's datasheet: PLA about 55 to 60 C, PETG about
  75 to 80 C, ABS and ASA about 95 to 105 C. ABS shrinks more: print enclosed, with a brim on long edges.
- Check: the heat table of phase 4 against the material; look.
- Why: a bracket sat over hot heat sinks; PLA was accepted for the concept only.

### FDM-17 Soft TPU parts (bumpers, feet)
- Rule: read the printer maker's own TPU guide for the spool path and nozzle before proposing anything. Dry the spool.
  Design with no overhangs: every wall vertical or leaning 45 degrees at most, a wide face on the bed. Nothing thin:
  keep sections at 3 mm or more. Print the part slightly undersize so it stretches on.
- Number: PROVEN on one printer, verify on yours: TPU 95A, fed by the path the printer maker's guide allows, printed
  and fitted; soft stretch-on parts drawn a few tenths smaller per side; the nozzle temperature from the spool's
  label.
- Check: slice with the printer maker's TPU preset copy: no support, no "overhang wall"; look at the layer preview.
- Why: the user feared a wrong spool path would jam the printer; the maker's guide settled it before the first print.

## Slicing, coupon, after the print

### FDM-18 Slice with copies of the user's presets
- Rule: `print_check.py --slice` copies the presets named in the printer profile to a work folder under `out/print/slice/` and slices with
  the copies. Report time, grams and support per part.
- Check: the slicing report. Without a slicer command line, with `[tools] slicer = "none"` (declined), or with a profile
  that does not name every preset the slicer needs, the rows read "could not run" and nothing is sliced: the user slices and sends
  the previews.
- Why: the user forbade any change to the slicer's settings.

### FDM-19 Read the slicer's warnings
- Rule: read "overhang wall", "floating vertical shell" and "bridge" marks from the G-code and list each as fixed,
  accepted with a reason, or support.
- Check: `print_check.py --slice` rows; the real option names of each slicer are verified on the first real run.
- Why: the marks showed the leg tips of FDM-04 before the reprint; nobody had read them before the first print.

### FDM-20 Look at the previews
- Rule: open the layer preview of every part: a section through each post, each vent group, each screw seat, each
  bridge. Write what was seen.
- Check: look (SKILL.md rule 6).
- Why: scripts passed parts that a single look at the sliced layers showed to be hollow under a post.

### FDM-21 Print the test coupon before the big parts
- Rule: `print_check.py --coupon` writes a small coupon: hole rows per screw size, one self-tapping post per size, an
  overhang ladder, a tab-and-slot pair at three clearances. The user prints it, tries the real screws and reports. The
  results go into the printer profile.
- Number: profile `[coupon] thickness` (default 3.0), `screws`.
- Check: `coupon.json` and the legend picture; the user's measured values written into the profile with the date.
- Why: the first full shell was the test piece. It went into the bin.

### FDM-22 The after-print checklist
- Rule: give the user this list in order, with a picture per item:
  1. Each tapping hole: its screw starts by hand. If it turns freely, reprint with the pilot 0.2 mm smaller.
  2. Each countersink: the head sits flush or just under.
  3. Each pass-through: every connector, LED and switch through its wall; plugs seat fully.
  4. Each board on all its posts; the display or window part flat on its panel.
  5. The lid: slides on by hand, holes line up.
  6. Overall: no warp, bridges clean, vents whole.
- Check: the user's answers and photos go into the print findings; each "does not fit" names the model parameter.
- Why: findings told from memory a day later lost two of the misfits.

### FDM-23 Concept prints are throw-away
- Rule: do not polish a concept part. Fix the model, reprint the part that failed, write down what fitted.
- Check: the print findings list "fitted" and "did not fit" per item.
- Why: the metal version reads its positions from the printed one; an unrecorded fit is a guess.

### FDM-24 No engraved text on printed parts unless asked
- Rule: legends on a concept print are shown in views and renders, not embossed or engraved.
- Check: look.
- Why: the user rejected engraving on plastic. See `panel-graphics.md` PG-04.
