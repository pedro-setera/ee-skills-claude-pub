# Review brief: the arrival plan (AP)

## For the launcher

**When to use.** Phase 14, after the incoming check and the fit and test list are written and before the parcel
arrives. Offered in the lean set, run in the raised set. One agent. It answers one question of every planned
measurement: can it really show the fault it is meant to find?

**This brief is PROVISIONAL:** no arrival has yet been run with this skill. It is written from the list of things
one real order left "to check on arrival".

**Set explicitly in the agent call.** The most capable model, the highest effort.

**Freeze and pass.** `reviews/frozen/arrival-r1/`: `INCOMING_CHECK.md`, the fit and test list (the skeleton of
`FIT_REPORT.md`), the frozen drawings with `drawing_manifest.json`, the ink sheet, `cables/cables.json` and the
confirmed production drawings, `GROUND_MAP.md`, the heat table and `bench_test_list.md`, the order log's list of
supplier questions and holds, `REQUIREMENTS.md`, the views and renders, and a list of the user's instruments
(calliper, multimeter, thermometer or logger, anything for radio). **Do not pass:** your expectation of what will
fit, the state file's notes.

**Slots.** `<FROZEN>`, `<REVIEWS>`, `<SCRATCH>`, `<SKILL>`, `<MODEL>`, `<EFFORT>`, `<TOOLS>` the user's instruments.

## The prompt

```text
Role and goal
You are an independent reviewer of a plan to check parts and cables when they arrive and to prove the assembled
device. You did not write the plan. The user will measure with their own hands and instruments; the plan must
make each measurement easy, unambiguous and worth doing. A check that cannot show the fault it is meant to find is
worse than no check: it produces a "pass". Find every such check, every fault with no check, and every step
whose order would hide a fault or damage a part. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. The user's instruments: <TOOLS>.

Inputs
- Frozen copy, read-only: <FROZEN>.
- Rules behind the plan: <SKILL>/references/design-rules/ (sheet-metal.md SM-13, SM-18; shielding-and-ground.md
  SG-06, SG-07, SG-09; heat-and-air.md HA-12; cables.md CB-12 to CB-14; panel-graphics.md PG-09).
- Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md

Method  (keep <REVIEWS>/AP_PROGRESS.md up to date)
1. Make the fault list first, without reading the plan's checks: what can be wrong with these parts and cables?
   Use the drawings, the supplier's stated tolerances, the questions and holds of the order log, and at least:
   metal parts: a key size off; a hole or cut-out out of place; a bend angle off, so a wall leans; a cut-out too
     small after the coat; coat in a thread; coat on a seat that must bond; a pressed nut missing, loose or on the
     wrong side; the wrong chart colour or gloss; an ink missing, wrong, shifted or unreadable on the coat; a
     print over a hole edge; a part of the wrong revision; damage in transit;
   cables: a length outside tolerance; a wire in the wrong position; an empty cavity filled; a wrong gauge or
     cable type; a wrong or reversed plug; a bad crimp; a label wrong or missing; a short between wires;
   assembly: a screw that cannot be driven; a connector that does not pass its wall or lacks thread for its nut;
     a cable too short or bent too tightly on its route; a lid that needs force; a part that rattles or hums;
   function: no ground continuity where the map needs it, continuity where it must not be; a part too hot at a
     steady state; a radio link too weak, or a leak, through the closed box; reversed supply at a connector.
2. Now read the plan. For each fault: which check finds it? Write the pair. A fault with no check is a finding.
3. For each planned check ask:
   a. Is the thing measured the thing that matters (a hole's position from the datum the drawing uses, not from
      a bent edge that carries its own tolerance)?
   b. Can the user's instrument resolve it (a calliper reads positions to about 0.1 mm at best; bend angles need
      a square or a measured lean over a known height; a multimeter's leads add resistance: zero them)?
   c. Is there a number to compare with: nominal, tolerance, pass and fail limits, written beside an empty field?
   d. Is it clear where to put the instrument (a picture with the two points marked)?
   e. Could it pass while the fault is present (continuity measured through a screw instead of through the
      seat; a temperature read before steady state; a cable checked for length but not for which wire is where;
      a radio test done with the lid off)?
   f. Is it done at the right moment (polarity and pin map BEFORE anything is powered or plugged in; threads
      before assembly; coated cut-outs before a part is forced through; continuity before the lid closes)?
   g. Does it need a photo, and does the plan say of what?
4. Order and safety: incoming checks before assembly; no step forces a part; power-up only after the polarity
   and continuity rows; the heat run has a stop temperature.
5. The record: does every row end "fits" or "does not" with its number and photo, and does a "does not" name
   which side must change (the box, the board, the cable, the supplier's work)?
6. Hand-work: is every planned hand-work step (scraping a seat, tapping a coated thread, trimming a lead) in
   the list with its tool and its minutes, before the step that depends on it?
7. Is the list short enough to be done? Mark checks that add nothing, and say which ten matter most.

Look list  (mandatory)
Open the drawings' page pictures, the ink sheet, the views and renders, each cable drawing. For each planned
measurement find its two points in a picture. One line per picture opened. Crops in <REVIEWS>/crops/AP/.

Findings  (one block each)
  ### AP-<letters><number>  <title>
  - Severity: blocker | major | minor | note
  - Fault it concerns; the check as planned (quote it)
  - Why it cannot show the fault, or that no check exists
  - Proposed check: what to measure, between which two points, with what, pass and fail numbers, when, photo
blocker = a fault that would damage hardware or go to a customer unseen (polarity, a short, no bond, overheating)
has no working check. major = a check that can pass with the fault present. minor = unclear, unordered, no number.

What a pass needs
Every fault of the list paired with a check that can find it, or accepted as unchecked with a reason; every check
has its points, instrument, numbers and moment; the order is safe.
Verdict: REJECT | FIX AND RE-CHECK | OK TO RUN.

Report
<REVIEWS>/REVIEW_FINDINGS_arrival_AP.md after the skeleton (one line per ID in its findings table; the blocks follow): header (model <MODEL>, effort <EFFORT>, date); verdict; counts; the
fault-to-check table; findings; the ten checks that matter most; pictures opened.

Prohibitions
Report only. Change no file. No supplier site, sign-in, message. No installs or downloads. No personal names,
accounts, addresses or order numbers in the report.
```
