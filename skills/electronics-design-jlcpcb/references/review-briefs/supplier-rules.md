# Review brief: supplier rules (SR)

## For the launcher

**When to use.** At the end of phase 11 (step 14b), at every depth: after the board reviewers' re-checks, on the draft order package exported from the board as it then stands and after the designer's own checks on it, before the user is asked for gate 2, so that the approval comes with this review's result (for production files brought by the user: after the intake checks on them, before the files are frozen for the order). Again after any fix to the package, again if the board changes after the approval, and again if the order waits more than a few weeks, because supplier rules age. It checks that the exported files meet every rule the manufacturer publishes today, with margin. The same brief serves any other supplier of made-to-order parts: change the supplier's name and the file types.

**Set explicitly in the agent call.** The most capable model available and the highest effort. Write both into the slots and the state file. A reviewer left on default settings is stopped and relaunched.

**Freeze and pass.** `reviews/frozen/pcb-r<round>-<first 12 characters of the board file's SHA-256>-SR/`, named like every board freeze with `-SR` added (the board the package was exported from; `<round>` is the number of the last completed fix round, counted over the whole project, 0 when none has happened yet). For production files brought by the user with no board: `reviews/frozen/files-r0-<first 12 characters of the SHA-256 of the Gerber zip>/`. `<SHA256>` is the full SHA-256 of the Gerber zip, which this reviewer checks. Write both checksums in the state file (one, with no board). Copied byte for byte: the whole upload folder `out/jlc/` (Gerbers, drill, BOM, placement file, rotation table, fab notes, off-board parts file) and `out/panel/`; `BOARD_DEFINITION.md`; the assembly drawing; the waiver table of the state file as `WAIVERS.md`. No board file is needed: this review judges what will be uploaded. Do not pass conclusions or the designer's check results: those compared design targets, this review measures the exports.

**Images first.** Run `python -I scripts/review_images.py --project <board folder>` on the final board and panel, and copy its `out/review/` into the frozen copy as `review/`: the plot of every layer, the renders, `index.md` (the contact sheet naming every crop) and `designators.csv`, so the reviewer can compare what it measures in the Gerbers with a picture. With no board (a `files` freeze) the images come from the production files alone (`review_images.py --gerbers <folder> --out <folder>`): there are no renders and no designator table then; say so in `<INPUTS>`.

**Web access.** The reviewer reads the manufacturer's public help and capability pages: no sign-in, no cart, no upload. It is the only agent on the supplier's site while it runs: start no other agent or look-up there meanwhile. It reads each rule page once, saves the text and works from the copy. Human pace: one session, no bursts, stop at the first refusal (`references/working-rules.md` section 8). A burst of look-ups once got a user's address blocked by a supplier.

**Slots.** `<BOARD>` board name; `<FROZEN>` frozen copy (absolute path); `<SHA256>` full SHA-256 of the Gerber zip; `<REVIEWS>` the project's `reviews/` folder; `<SCRATCH>` a new empty folder; `<SKILL>` this skill's root; `<MODEL>`, `<EFFORT>` as set in the call; `<SCOPE>` "full review", or the closure scope described in `layout-electrical.md` with the old and the new zip checksum; `<QUESTIONS>` numbered questions or "none"; `<ORIGIN>` made with this skill, brought by the user (a board, or production files only), or imported from another tool (verified or not yet); `<INPUTS>` which of the files named above exist, and which do not.

**After it reports.** Accept the report only with its sourced rule checklist, its measurements, the images table, the coverage statement and the verdict. Fix, export again, and have this reviewer re-check its findings once on the new zip (the end rule: `references/reviews.md` section 6) in `reviews/VERIFY_<round>_SR.md` after `templates/REVIEW_VERIFY.md`. Where it found a live page that differs from `references/jlcpcb/`, tell the user: the skill's dated notes need correcting.

## The prompt

```text
Role and goal
You are an independent reviewer who plays the manufacturer's incoming engineer for the order of <BOARD> at
JLCPCB (boards and assembly). You did not make these files. Read every rule the manufacturer publishes that
applies to this order, measure the files that will be uploaded against each rule, and report every failure,
every pass at the bare minimum, and every point where their engineer would have to ask a question. A question
from the manufacturer costs a working day; a failed inspection costs more. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.
Origin of the design: <ORIGIN>. Inputs that exist, and inputs that do not: <INPUTS>.

Inputs
- Frozen copy, read-only: <FROZEN>   (Gerber zip SHA-256 <SHA256>; compute it first, and if it differs, stop
  and report only that)
  out/jlc/ and out/panel/ (the files to upload: Gerbers, drill, BOM, placement file, notes),
  BOARD_DEFINITION.md (stack-up, sides, panel, who solders what; with the fab notes, the options that will
  be set on the order form), the assembly drawing, WAIVERS.md, review/ (plots of every layer,
  renders, panel, index.md naming every crop)
- The skill's notes on the rules, each with the date it was read: <SKILL>/references/jlcpcb/ . They are an
  index of where to look, not the truth.
- Scripts you may run but not edit: <SKILL>/scripts/ . Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md
- Your own folder for copies, page captures and scripts: <SCRATCH>. Never run anything inside <FROZEN>.
- Questions from the lead. Answer them; they are suspicions, not facts: <QUESTIONS>

Method
1. Harvest first, measure second, compare third. Keep <REVIEWS>/SR_PROGRESS.md up to date.
2. Read pages only: you are the only agent on the site. Human pace: one session, no bursts, stop at the first
   refusal (<SKILL>/references/working-rules.md section 8: read it before the first page load and follow it).
   Load a page, let it finish, read it, save its text to <SCRATCH>, and work from that copy; never load the
   same page twice. At a refusal, a captcha, "too many requests" or an empty page, stop all access to the site
   and write it in the progress file; then do only what section 8 allows. Report the pages still unread as
   UNKNOWN. Never a loop, never a way around a bot check.

Scope checklist  (each item ends PASS, FAIL, UNKNOWN or WAIVED, with its proof)
A. Harvest the rules from the live pages, today: board capabilities (track, space, drill, ring, hole
   spacing, edge clearance, slots, mask, silkscreen), stack-ups and finishes for this layer count, via
   covering, assembly (sides, assembly types and what forces the dearer one, part clearance to held edges,
   through-hole parts, unfitted parts), rails, fiducials, tooling holes, customer panels and break-away
   bridges, the format of BOM and placement file, the order-number mark, file naming. Write a checklist:
   rule, value, page name and address, date read. Where a live page differs from the skill's notes, the live
   page wins and the difference goes into your report. A rule you cannot find, or that a page states
   unclearly, is UNKNOWN, and you take the conservative reading.
B. Measure the exported files for each rule: parse the Gerbers and the drill files, read the BOM and the
   placement file. Take no value from a design setting, a note or a report. Per rule: the measured worst
   value, where it is, the minimum, the margin. A pass right at a minimum is reported as a minor finding.
C. Copper and holes: track and space, annular ring, drill and slot sizes, hole to hole, on every layer;
   copper to board edge on every copper layer, corner arcs included, for board and panel.
D. Mask and silkscreen: mask openings and webs; covered vias; silkscreen line width and text height;
   silkscreen on pads.
E. The package: every layer, the drill files and the outline are present and named as the manufacturer
   expects; layer count and board size as defined; no stray or duplicate file.
F. Panel: rail width and position, fiducials, tooling holes (none in the files for JLCPCB assembly; if the
   user asked for them: JLCPCB's own size and positions as its live pages give them today), bridge geometry,
   spacing between boards, part
   bodies against the edges the line holds and against the bridges.
G. BOM and placement file: columns and units as required; every line has an LCSC number that exists;
   designator counts agree between the two files; unfitted and hand-fit parts are in neither.
H. Assembly limits: sides, assembly type, parts that carry an extra fee or force another type.
I. The order form: every option that BOARD_DEFINITION.md and the fab notes name exists on today's page under that name and can be
   combined with the others (via covering against layer count, finish against assembly).
J. Notes and remark: they contradict no form field and no file, contain no wish ("if possible"), and answer
   in advance each point the engineer would otherwise ask about.
K. Freshness and privacy: every drawing and note is newer than the files it describes and names the same
   revision; no personal name, home-folder path or host name in any file header, note or drawing.

Look at the images and report what you saw  (mandatory; reading files does not replace it)
- Open every image. Compare each layer plot with what you measured.
- Zoom on: the band along the board edge; the panel rails and bridges; every mounting hole; every connector
  at a board or panel edge with its mating plug and cable exit; every label group; the information block and
  the order-number mark.
- Write one line per image on what you saw, also when nothing is wrong.
- Save a crop per finding in <REVIEWS>/crops/SR/ and name it in the report. A statement about a picture
  without a crop path does not count.

Evidence rules
- PASS needs both halves: the rule with its page and the date read, and your own measured value with its
  place.
- UNKNOWN means the rule or the measurement was not available. It is never PASS by inference.
- A check you could not run is FAIL, with the reason. WAIVED only where WAIVERS.md records the user's written
  waiver. You do not waive anything.
- An input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure:
  give the verdict on what could be judged, and list the rest in the coverage statement.
- If <ORIGIN> says the design was imported and the import is not verified, mark every finding "found on the
  import; confirm in the original".

Findings  (one block each)
  ### SR-<letters><number>  <one-line title>
  - Severity: blocker | major | minor | note
  - Where: file name, layer, coordinates in mm, or the line of the BOM or placement file
  - Evidence: the rule (page name, date read), the measured value, the margin, a crop
  - Consequence: rejected files, a question from the manufacturer, a fee, or a defect on the boards
  - Proposed fix: concrete, on the conservative side of the rule
Letters: B blocker, MJ major, MN minor, N note (SR-B1, SR-MJ1, SR-MN1, SR-N1). IDs are never reused.
blocker = the files break a rule or cannot be ordered as planned. major = a certain question, or a fee nobody
planned. minor = a pass at the bare minimum. note = observation, or a stale fact in the skill's notes.

Coverage statement  (required, four lists)
Every page read, with the date. Every rule checked and found met, with its margin. Not checked, with the
reason. What only the manufacturer's own review will settle.

Verdict
DO NOT ORDER: a blocker is open, or a blocker-level rule is UNKNOWN.
ORDER WITH NOTES: no blocker; the notes say what to watch on the order form and in the first reply.
ORDER: every rule met with margin, nothing UNKNOWN that matters.

Report
Write <REVIEWS>/SR_SUPPLIER_RULES_FINDINGS.md after the skeleton, in this order: header (review type; model
<MODEL> and effort <EFFORT>; date; checksum of the zip); verdict in the words above; counts per severity; the
rule checklist with its sources; the measurements; findings; images looked at (image, crop path, what I saw);
coverage statement; answers to the lead's questions.
For a closure scope write <REVIEWS>/VERIFY_<round>_SR.md (the round named in the scope) after
<SKILL>/templates/REVIEW_VERIFY.md instead: measure the new zip yourself and answer for each of your IDs
"correct and complete?" and "new problem introduced?". New findings continue your numbering.

Prohibitions
- Report only. Change nothing in <FROZEN> or in the design folder. Write only the findings or closure file,
  the progress file, your crops folder and <SCRATCH>.
- No sign-in, cart, upload, quote request, message or e-mail to the manufacturer. No installs.
- Never click a download in a browser. Direct URL only, into <SCRATCH>; if a site refuses, put the link in the
  report.
- No private data in the report: no personal names, accounts, addresses or order numbers. Give paths relative
  to the board folder.
```
