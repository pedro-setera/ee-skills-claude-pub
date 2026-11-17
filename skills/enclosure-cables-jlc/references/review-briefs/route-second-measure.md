# Review brief: the second measurement of every cable route (R2)

## For the launcher

**When to use.** Phase 5, after your own routes are measured (`cable_route.py` wrote `measure_a_mm`) and BEFORE the
compare. One agent, in every set. It answers: measured again by someone who did not see the first numbers, how long
is each cable?

**Set explicitly in the agent call.** The most capable model, the highest effort.

**Freeze and pass.** `reviews/frozen/routes-r1/`, laid out as the project's `mech/` folder: `mech.toml`, `suppliers/`
(the capability sheets), `model/`, `interface.json` and the board STEP,
`vendor3d/` (the makers' models and drawings of every connector and plug), `out/step/` (the assembly), `out/views/`,
and **a stripped copy of `cables/cables.json`**: every `route` block removed, `length_mm` set to null.
**Do not pass:** `cables/routes.toml`, `out/cables/` (route pictures and lengths), `out/checks/cable_route.json`,
the layout study's rough lengths, anything that states a length.

**Slots.** `<FROZEN>`, `<REVIEWS>`, `<SCRATCH>`, `<SKILL>`, `<MODEL>`, `<EFFORT>`, `<CHOICES>` the user's routing
choices in words (for example "power lead under the board stack; no loops"), copied from the state file.

**After it reports.** Copy its `second_measure.toml` to `cables/second_measure.toml`, then run
`cable_second_measure.py` and `cable_second_measure.py --compare --apply`. Every difference above
`[cables] compare_max_diff_mm` gets a written cause in `route.note`; the longer value is used. Only now may either
side see the other's numbers.

## The prompt

```text
Role and goal
You are the second measurer of the cable routes inside an enclosure. Another person has measured them; you will
not see their routes or numbers, and they have not seen yours. The two results are compared afterwards and the
longer one is ordered, so an honest independent reading is the whole value of your work. A cable ordered a few
millimetres short does not reach; a stiff cable a few millimetres long bends too tightly. Two measurements of a
short coax once differed by several millimetres because one side assumed a connector body length instead of reading the maker's
drawing. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>.

Inputs
- Frozen copy, read-only: <FROZEN> (it holds mech.toml at its top). Copy the whole folder to <SCRATCH>/mech, so
  that <SCRATCH>/mech/mech.toml exists, and work only in that copy.
  cables/cables.json (the cable list: ends, connector parts, wire count, cable type; no lengths),
  model/, out/step/ (the assembly), vendor3d/ (makers' models and drawings), out/views/, interface.json
- The user's routing choices: <CHOICES>
- Scripts: <SKILL>/scripts/cable_second_measure.py (--help), template <SKILL>/templates/second_measure.example.toml
- Rules: <SKILL>/references/design-rules/cables.md (CB-05 to CB-10)
If you find a file that states a route or a length, do not open it; report that it was in your inputs.

Method  (keep <REVIEWS>/R2_PROGRESS.md up to date)
1. For every cable end, find the connector in the model and read its maker's drawing: where exactly does the wire
   leave the body, and in which direction? Write the pose (point and direction, box frame) and its source.
   A pose you had to guess is marked GUESSED with the reason.
2. For every cable choose the route yourself, following <CHOICES>: under boards, no loops, clear of fans and hot
   parts. Decide the bend radius from the cable type and its datasheet value in cables.json, not from habit.
3. Write <SCRATCH>/mech/cables/second_measure.toml after the template: per cable the two poses, the radius, and via points
   only where the route must pass round something. For a harness measure each wire that goes to a different
   position if the positions are more than a few millimetres apart.
4. Run: python -I <SKILL>/scripts/cable_second_measure.py --project <SCRATCH>/mech
   (it reads <SCRATCH>/mech/cables/second_measure.toml; another place needs --poses <file>)
   It solves each route by a method different from the first measurer's and writes the lengths. Read every row.
5. Cross-check three cables by hand: straight pieces plus radius times angle for each arc. Show the sums.
6. Look: for each route, open the views that show both ends and the space between. Is there really room? What
   is the nearest part? Could the cable physically be laid there by hand?

Report for each cable
  id | pose P1 (point, direction, source) | pose P2 | radius used and why | route in words | length mm |
  hand cross-check | nearest part and gap | doubts
Then:
- Poses GUESSED, and what would settle each (a drawing, a measurement by the user with a sketch).
- Cables where a few millimetres more or less change the result (a short stiff cable between fixed ends): say
  what happens at length - D and + D (D = `[tolerance] design_mm` of the cable supplier's capability sheet).
- Cables you could not route within the user's choices, with the reason.
- Connector facts you found that the cable list has wrong (positions, gender, pitch, wire exit side).

Look list  (mandatory)
Name every picture you opened and what you saw at each cable end. Save a crop per doubt in <REVIEWS>/crops/R2/.

Findings  (only for faults in the inputs, one block each)
  ### R2-<letters><number>  <title>
  - Severity: blocker | major | minor | note
  - Evidence: file, value, crop
  - Consequence; Proposed fix
blocker = a cable cannot be routed or a connector fact is wrong. major = a pose is guessed for a short stiff cable.

What a pass needs
Every cable has two sourced poses, a length from the script and a route in words; three hand cross-checks agree
with the script within 1 mm; every guess is listed.

Files to write
<REVIEWS>/R2_SECOND_MEASURE.md (the table and lists above; header with model <MODEL>, effort <EFFORT>, date) and
<REVIEWS>/R2_second_measure.toml (a copy of your <SCRATCH>/mech/cables/second_measure.toml). Nothing else.

Prohibitions
Do not look for, ask for or open the first measurement. Change no project file. No installs, downloads, messages,
supplier sites. No product names in the report: cable ids and end names only.
```
