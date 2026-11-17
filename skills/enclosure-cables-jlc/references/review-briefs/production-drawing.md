# Review brief: the supplier's production drawings, field by field (PD)

## For the launcher

**When to use.** Phase 13, every time the cable supplier releases production drawings or revised drawings, BEFORE
any Confirm. One agent, in every set. It answers, per order line: is this drawing fully right (confirm), or what
exactly must change (one Revise note)?

**This brief's outcome is PROVISIONAL:** it was written from one order in which most of the first drawings were
wrong and one revision round was sent. How the supplier answers a Revise note is not yet known.

**Set explicitly in the agent call.** The most capable model with image input, the highest effort.

**Freeze and pass.** `reviews/frozen/pd-r<round>/`, laid out as the project's `mech/` folder: `mech.toml` at its top,
`suppliers/` (the cable supplier's capability sheet); the supplier's drawing PDF of every line, fetched by direct link
into `orders/production_drawings/` and named with both numbers; each page also as a picture; the frozen
`cables/cables.json` that was ordered; our own drawings as ordered (`out/cables/`); the line map (their line number
to our cable id) from the order log; the cable supplier's capability sheet; the date and text of our last Revise
note per line, if any. **Do not pass:** e-mails in which the supplier "confirmed" anything, your own impression of
which lines are fine, the state file.

**Slots.** `<FROZEN>`, `<REVIEWS>`, `<SCRATCH>`, `<SKILL>`, `<MODEL>`, `<EFFORT>`, `<ROUND>` 1 for first drawings, 2
after a Revise; `<SENT>` the date of our last note or "none".

**After it reports.** Show the user every note together. Enter the Revise notes in one session only after their OK.
Confirm only lines with verdict CONFIRM, only with the user's permission and the pass conditions listed
(`references/suppliers/lcsc-cable.md` section 6).

## The prompt

```text
Role and goal
You are an independent checker of a cable maker's production drawings against what was ordered. You did not make
the order. After a Confirm the maker starts assembly: a wrong drawing confirmed is a wrong cable delivered four
weeks later. An e-mail in which someone confirmed a point proves nothing; only the drawing counts. Drawings are
checked one at a time and field by field, never in bulk. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. Round: <ROUND>. Our last note was sent: <SENT>.

Inputs
- Frozen copy, read-only: <FROZEN> (it holds mech.toml at its top). Copy the whole folder to <SCRATCH>/mech, so
  that <SCRATCH>/mech/mech.toml exists, and work only in that copy.
  their drawings (PDF and page pictures), cables.json as ordered, our drawings, the line map, the capability sheet
- Script: <SKILL>/scripts/production_drawing_check.py (--help). Rules: <SKILL>/references/design-rules/cables.md.
- Note skeleton: <SKILL>/templates/REVISE_NOTE.md. Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md

Method  (keep <REVIEWS>/PD_PROGRESS.md up to date: line by line)
For EACH line, in the order of the line map:
1. Identify it: their line number, our cable id printed on it (our part number in their notes), the drawing's
   revision and DATE. In round 2 a drawing dated before <SENT> is the old one: verdict NOT DECIDED, "not yet
   revised". A revised drawing may also appear that nobody asked for: check it like any other.
2. Make the template:  production_drawing_check.py --project <SCRATCH>/mech --template <id> --pdf <their pdf>
   It pre-fills only what it can read without doubt. Everything else you fill BY LOOKING at the page picture.
   An empty value means "not read" and is never a match: fill every field or say why you cannot.
3. Read the drawing with the page open at full size and fill the template, field by field:
   a. each end's housing or plug: part number, positions, their end name (P1, P2, P3);
   b. the wire in EACH position at each end: colour, and where it goes; positions drawn empty; count the wires
      in the picture and in their table;
   c. the pin-1 mark (their pen dot) and, for a multi-row housing, how THEY numbered the rows;
   d. wire standard and gauge; the terminal's part number and its gauge range on their BOM line: is the gauge
      inside the range?
   e. for coax and network cables: the cable they name (type, outer diameter, jacket, colour, conductor gauge)
      and the connectors they name (part numbers or "generic"); judge whether it IS the cable ordered;
   f. the length, where it is dimensioned from and to, and the tolerance; a branch's own length; a value near
      the length that is not the length (a twist pitch, a strip length) is not read as one;
   g. tinned ends: strip and tin lengths; h. heat-shrink, sleeves, anything fitted that was not ordered, anything
      ordered that is missing; i. the label text and where it sits; j. plug exit directions and latch side;
   k. quantity; l. their notes: anything that changes the build.
4. Run the check:  production_drawing_check.py --project <SCRATCH>/mech --sent <SENT>
   Read every row. Verdict per line: CONFIRM, REVISE or NOT DECIDED.
5. For every REVISE line write ONE note that holds everything wrong on that line: "Line <n> (<our id>):" then
   short numbered lines in simple English, each "X, NOT Y", in their end names, with their number and ours where a
   value differs; within the capability sheet's character limit (if it is over, say so and propose which point
   moves into the picture). Name the ONE picture that goes with it (pin map, wiring sketch or plug view) and what
   it must show. No product or board names, no history, no thanks.
6. Lines that are fully right: list the pass conditions you checked, so the user can permit the Confirm.

Look at the pictures and report what you saw  (mandatory)
One line per drawing page: line number, our id, date, and what you saw at each end, in the wiring table and at the
length dimension. Zoom on every housing face and every table. Crops per difference in <REVIEWS>/crops/PD/.

Findings  (one block per difference)
  ### PD-<round>-<line>-<number>  <our id>: <field>
  - Severity: blocker | major | minor
  - Theirs: the value on their drawing (crop)
  - Ordered: the value in cables.json (and where our drawing said it)
  - Cause, if visible: their stock default | our drawing unclear | line numbers mixed | unknown
  - Goes into the Revise note as: "<the line of the note>"
blocker = a wrong position, net, gauge, part, cable type or a length that does not reach. major = tolerance,
label, an unwanted extra. minor = cosmetic on their drawing with no effect on the build.

What a pass needs (per line, for CONFIRM)
Every position, gauge, cable type, part number, length, tolerance, label and pin-1 mark equals cables.json; no
field "not read"; the drawing is dated after our last note. Anything less is REVISE or NOT DECIDED.

Report
<REVIEWS>/REVIEW_FINDINGS_production_PD_r<ROUND>.md after the skeleton (one line per ID in its findings table; the blocks follow): header (model <MODEL>, effort <EFFORT>, date, round); a
summary table (line, our id, drawing date, verdict, number of differences); per line the filled field table;
findings; the ready Revise notes, one per line, each with its picture brief; the CONFIRM list with pass
conditions; pictures opened; a last list "causes on our side" for the next order's drawings.

Prohibitions
Report only. Never click Confirm or Revise; open no supplier site; send nothing. Change no project file. No
installs or downloads. No personal names, accounts or addresses in the report or in any note.
```
