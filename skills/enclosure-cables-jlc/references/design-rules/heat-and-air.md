# Design rules: heat and air (HA-nn)

Read in phase 2 (the air path decides the layout) and phase 4 (the heat table). Cite a rule by its ID.

Everything this file and `heat_air.py` produce is an ESTIMATE, good to choose a fan size and to compare arrangements
within about 30 to 50 %. The proof is the bench run to a steady temperature (HA-12). This section stays
**PROVISIONAL** until an assembled metal box has been measured against its estimate.

How to read a rule: the rule; **Number** with its source; **Check**; **Why**.

### HA-01 Write the heat table first
- Rule: one row per part that makes heat: watts (typical and worst), its temperature limit, where the number came
  from (datasheet, measurement, the electronics skill's documents). Sum it. Unknown watts are UNKNOWN, not zero.
- Check: `heat_air.py HEAT.toml` writes `heat_table.md`; a starting file is `templates/heat.example.toml`.
- Why: an estimate done once in someone's head, against the fan's free-air number, put a hot board in a box that
  could not cool it.

### HA-02 Draw the air path
- Rule: show on the layout picture where air enters, which parts it passes, and where it leaves. Every hot part lies
  in the path. Heat-sink fins run along the flow. Nothing wide stands directly in front of a fan.
- Number: `heat_air.py` flags a part above `path_min_w` (default 0.5 W) outside every intake-to-fan path.
- Check: `layout_study.py` (fan free zone, intake/swept ratio rows) and `heat_air.py` with `[heat] layout`; look at
  the top and side pictures.
- Why: a fan sat behind a board; the hot part was in still air.

### HA-03 Prefer an exhaust fan to a jet on a sensitive part
- Rule: a fan that pulls air OUT gives a slow, even flow through the box. A fan that blows IN makes a jet. Keep
  oscillators, references, sensors and microphones out of any jet and away from the nearest opening. Shield a
  sensitive part from the stream with a small cover where needed.
- Number: none; keep sensitive parts out of any jet and away from the nearest opening; a small cover is a cheap
  fix.
- Check: `heat_air.py` flag "sensitive part in a fan's stream" (parts tagged sensitive in the layout); look.
- Why: general practice: a jet changes a part's temperature quickly and its value follows; the drift is easily
  blamed on something else.

### HA-04 Intake area at least 1.1 times the fans' swept area (aim 1.1 to 1.5)
- Rule: per group of fans that blow the same way, the sum of the passive openings they draw through (intake vents for
  exhaust fans, exhaust vents for intake fans) is at least 1.1 times the SUM of the group's swept areas (the ring
  between hub and blade tip); 1.1 to 1.5 is the aim. Two fans that share one opening share its area. Above 1.5 is not
  a failure: the row notes "more open area than needed; see shielding SG-01 and dust". Count only the open area of
  a perforated field.
- Number: the range is a starting value: verify.
  Swept area = pi/4 x (D_blade^2 - D_hub^2).
- Check: `heat_air.py` row "intake to swept area ratio", one per direction group (id HEAT-R-<fan names joined
  with +>); `layout_study.py` row per variant (the same rule).
- Why: a guard that covers the fan with bars or a small hole field chokes it. A perforated guard that left well
  under half of the swept ring open was accepted for strength, knowingly.

### HA-05 Never remove a working local fan on a hypothesis
- Rule: a board that ships with its own fan or needs air on one chip keeps that air until a bench run proves the
  replacement. "The case fan will do" is a hypothesis.
- Check: the heat table row of that part shows a measured temperature, or the local fan stays.
- Why: with its small fan removed, a processor became very hot within a minute.

### HA-06 Heat sink plus forced air
- Rule: for a hot chip, a heat sink in moving air beats either alone. Give the sink's height with its tape or pad,
  check the height zone, and say how it is held (clip, screws, tape).
- Number: `heat_air.py` uses the part's `theta_ca`. Without one it still shows an estimate (an ASSUMED 25 K/W
  without and 6 K/W with a heat sink, marked "assumed"), but the row's verdict is "could not run: datasheet theta_ca
  needed", never pass or fail. Get the datasheet figure.
- Check: `heat_air.py` part temperature rows; `fit_check.py` and `parcheck.py` for the sink's height.
- Why: a sink had to be mounted shifted to clear a structure nobody had modelled.

### HA-07 Suggest a fan size, and prefer larger and slower
- Rule: suggest the fan to the user with its size, why, and what it needs (a header, a speed signal, a guard). One
  larger slow fan is quieter than a small fast one at the same flow. The box height often decides the largest fan.
- Number: `heat_air.py` fan suggestion: the smallest size of a generic table (25 to 140 mm, typical free-air flows,
  approximate, real fans differ by a factor of 2) that gives the target rise. Air rise = P / (1206 x Q), Q in m3/s,
  with Q = 0.5 x the free-air figure (the default derate for a box with grilles and boards in the way). Fans that
  blow the same way work in parallel and their free-air flows add; an intake group and an exhaust group are in series
  and the lower of the two group flows is used (a push-pull pair moves the air of one fan, not two).
- Check: `heat_air.py` rows; the user's choice in the decisions table.
- Why: the user asked the skill to say "add this fan, this size, with or without a heat sink" instead of leaving it open.

### HA-08 Read the fan's own pin-out and connector
- Rule: read the maker's page for each fan: 2, 3 or 4 wires, pin order, voltage, lead length and exit corner. Hand
  the header need to the electronics side. Route the lead like any cable (`cables.md` CB-05).
- Check: the maker's page saved in the project; the cable list has a row per fan lead.
- Why: a wiring sheet had the 3-wire and the 4-wire fan swapped; the user caught it at assembly.

### HA-09 Vents: where, and how they are made
- Rule: place intakes so the air crosses the hot parts on its way to the fan. Vents are complete regular fields
  (`fdm-printing.md` FDM-13, `sheet-metal.md` SM-19). Slots narrow enough that nothing drops in. Show the vents in the
  standard views: the user must see where they are.
- Number: a starting value, verify: slots a few millimetres wide; round holes of a few mm on a hex pitch, webs at
  least the supplier's minimum.
- Check: `box_toolkit.hex_field`; look at every face in the view set.
- Why: the user could not find the vents in the first pictures and asked for five views.

### HA-10 Vents against shielding
- Rule: a vent is also an aperture. Many small holes shield far better than one slot of the same area, but a field
  of N holes leaks about 10 x log10(N) dB more than one of its holes (`shielding-and-ground.md` SG-02). Check each
  opening against `shielding-and-ground.md` SG-01.
- Number: see SG-01.
- Check: the shielding rows of phase 4.
- Why: the same field of small holes served air and shielding in the metal version.

### HA-11 A fan on a plate: mass and vibration
- Rule: a fan hung from a plate or bracket needs its centre of mass inside the supports and a plate stiff enough not
  to hum at the fan's speed.
- Number: an example, verify: a plate's first bending mode estimated near 1.5 kHz against a fan at 50 Hz (3000 rpm)
  is safe. General practice, approximate: compare the mode also with the blade-pass frequency (number
  of blades x rpm / 60, often 5 to 10 times the shaft frequency: 7 blades at 50 Hz give 350 Hz) and its double,
  and keep it well away from all of them. Listen on the first sample.
- Check: `stiffness.py` for the plate; look; the arrival test list.
- Why: none failed; listed as an arrival check.

### HA-12a Judge parts, not the air
- Rule: the verdict that matters is each part's temperature against its own limit (a data-sheet `theta_ca` and
  maximum). The air-rise target (`target_rise_k`, default 10 K) is a project parameter, not a requirement: set it
  from the parts' limits and the room temperature, and write why. Ask for the parts' limits first; a small sealed box
  fails a generic 10 K easily while every part is far inside its limit.
- Check: `heat_air.py` part rows ("could not run" until the data-sheet figure is in); the decisions table.
- Why: a sealed 1.5 W box failed the default target although no part limit was known.

### HA-12 Estimates are estimates: the bench run proves them
- Rule: every heat row says "estimate, prove on the bench". The arrival test list holds the run: closed box, worst
  load, log each listed temperature until it changes less than 0.5 K in 10 minutes, compare with the estimate, once
  more in a warm room if the device will see one.
- Number: steady-state rule from `heat_air.py` (`bench_test_list.md`); thresholds per part from its limit minus
  `margin_k` (default 10 K).
- Check: `bench_test_list.md` has an empty "measured" column per row; phase 14 fills it.
- Why: SKILL.md rule 8: a check that cannot run is never a pass. A heat estimate is not a measurement.

### HA-13 Without a fan
- Rule: a closed box with no fan loses heat through its walls and, with low and high vents, by stack flow. Put intake
  vents low and exhaust vents high.
- Number: `heat_air.py` natural-convection row (wall transfer with h_in 4 and h_out 8 W/m2K, stack flow with Cd 0.6,
  solved for the air rise). Order of magnitude only.
- Check: `heat_air.py`; the bench run.
- Why: general practice.

## What `heat_air.py` computes, and its limits

Computes: total power; air temperature rise with fans; natural-convection rise without; part temperature from air
temperature plus watts times theta; the intake-to-swept ratio per direction group of fans; a fan suggestion; path and stream flags from a layout
study; the bench test list.

Limits, all stated in its docstring: one air temperature for the whole box (well mixed); steady state; all power is
assumed to heat the air; no fan curves (free-air figure times the derate); no filter pressure drop; no altitude
correction (air thins about 1 % per 100 m); no sun load; assumed thetas where none is given (those rows are "could not run"); a generic fan table. It
compares arrangements and sizes a fan. It does not replace the run.

## Asking the user

Only trade-offs, with a picture and the suggested answer first. Example: "One 80 mm fan or two 50 mm? Suggested: one
80 mm. Why: quieter at the same air flow." Heat above about 15 W raises the review set (SKILL.md, Reviews).
