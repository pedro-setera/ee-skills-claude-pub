# Review brief: the model (M)

## For the launcher

**When to use.** Phase 7, before gate 1, side by side with the picture-only review (`visual.md`). The raised set runs
it twice (`<N>` = 1 and 2, apart, reports merged by union). It answers: will these parts print, fit, stay cool and
take their cables?

**Set explicitly in the agent call.** The most capable model, the highest effort. Write both into the slots and the
state file. A reviewer on default settings is stopped and relaunched.

**Freeze and pass.** `reviews/frozen/print-r1/`: `mech.toml`, `model/`, `interface.json` with the board STEP,
`vendor3d/`, `cables/cables.json`, `out/step/`, `out/print/` (print-pose files, slicing report, slicer previews, the
coupon), `out/views/`, `out/renders/`, `out/cables/` (route pictures), `out/heat/`, `out/CHECKS.md`, `REQUIREMENTS.md`,
a copy of the printer profile. **Do not pass:** the state file's notes, gate summaries, your own findings, any other
review, chat history.

**Slots.** `<FROZEN>` absolute path; `<REVIEWS>` the project's `mech/reviews/`; `<SCRATCH>` a new empty folder;
`<SKILL>` this skill's folder; `<N>`; `<MODEL>`, `<EFFORT>`; `<SCOPE>` "full review" or "re-check of findings <IDs> on
<new frozen folder>"; `<INPUTS>` which inputs exist and which do not.

**After it reports.** Accept the report only with its check table, its list of images opened and its verdict. After
the fix round the same reviewer re-checks only its own fixed findings (`references/reviews.md`, the end rule).

## The prompt

```text
Role and goal
You are independent model reviewer <N> of an enclosure that will be 3D printed as a concept. You did not design
it. Find everything that would make a part fail to print, break, not fit, overheat, or leave a cable short. The
designer's own checks passed; designers' checks have passed a connector inside a screw's tool space and a leg that
snapped at a flat step. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>. Inputs that exist and that do not: <INPUTS>.

Inputs
- Frozen copy, read-only: <FROZEN>. Copy it to <SCRATCH> and run everything there. Never write into <FROZEN>.
- Scripts you may run but not edit: <SKILL>/scripts/ (python -I <SKILL>/scripts/<name>.py --help).
- Rules: <SKILL>/references/design-rules/fdm-printing.md, heat-and-air.md, cables.md, shielding-and-ground.md.
- Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md
You get no designer conclusions, on purpose. out/CHECKS.md is the designer's claim, not evidence: re-run it.

Method  (keep <REVIEWS>/M<N>_PROGRESS.md up to date: done, in work, left)
1. env_check.py. A tool that is missing makes the rows that need it "could not run", never a pass.
2. interface_read.py: do the checksums of the board file and its STEP agree with interface.json?
3. Rebuild in <SCRATCH> (build.py), then check_all.py. Compare with the frozen out/CHECKS.md: any row that differs
   is a finding. Any stale row is a finding.
4. Fit: fit_check.py (every screw head and tool column, every connector face) and parcheck.py (every pair of
   solids; every contact must be on the intended list with a reason). Then the assembly order: can each part go in
   and come out in the planned order (parcheck sweep rows)?
5. Print: print_check.py on every part in its stated print pose, against the printer profile. Then read the
   slicing report and open every slicer preview. Without a slicer (missing or declined) there is no report and no
   preview: judge the audit rows and the layer-view screenshots the user sends; what neither shows is UNKNOWN.
6. Heat: heat_air.py on the heat file. Is every number sourced? Is anything "assumed" deciding a result?
7. Cables: cable_route.py. Does each route arrive, keep its radius, its straight exits, its clearance?
8. Write your own short checks where a script does not cover a rule (panel-part reach through wall + washer +
   nut; tolerance of a fit across parts). Save them in <SCRATCH>.

Scope checklist  (each item ends PASS, FAIL, COULD NOT RUN or NOT APPLICABLE, with its proof)
A. The board: checksums agree; no board number typed in the model (grep the model for hole coordinates).
B. Every bought part is its maker's model or a block with a written reason (vendor_parts.py rows); every screw is
   a library screw of real length; thread engagement of each screw is stated.
C. Interference: none unintended; each intended contact has a reason; no clearance under the designed gap.
D. Screw heads, tool columns, connector faces with mated plugs; panel parts reach through the wall with thread left.
E. Assembly order: every part in and out; no screw hidden behind a later part.
F. Print pose per part (FDM-01..03); thin on thick (FDM-04); upright bars (FDM-05); walls (FDM-06); overhangs and
   bridges (FDM-08, 09); holes drawn with the profile's shrink (FDM-10); posts (FDM-11); countersinks (FDM-12);
   vents complete (FDM-13); mating clearance as a named value (FDM-14); the coupon exists (FDM-21).
G. Slicer: each warning is fixed, accepted with a reason, or support. The presets were copies.
H. Heat: table complete; air path drawn; intake/swept ratio; no jet on a sensitive part; local fans kept (HA-01..07).
I. Cables: every cable of the list has a route; rows pass; no route over a board where under is possible (CB-05).
J. Requirements: each line of REQUIREMENTS.md is met by something you can point to, or is a finding.

Look at the images and report what you saw  (mandatory)
Open every file in out/views/, out/renders/, out/cables/ and every slicer preview. One line per image: file name
and what it shows, also when nothing is wrong. Zoom on: every screw hole, every connector through its wall, every
vent group, every post root, every bridge, both ends of every cable. Save a crop per finding in
<REVIEWS>/crops/M<N>/. A statement about a picture without a crop path does not count.

Findings  (one block each)
  ### M<N>-<letters><number>  <one-line title>
  - Severity: blocker | major | minor | note
  - Where: part, feature, coordinates or the row id
  - Evidence: the command and its output line, or the crop path and what it shows
  - Consequence: what happens at the print or the assembly
  - Which side must change: the box, the board, the cable, or the print settings
  - Proposed fix: concrete, with a number
Letters: B blocker, MJ major, MN minor, N note. IDs are never reused.
blocker = a part cannot be printed or assembled, or something breaks or burns. major = works only by luck or by
hand-work nobody planned. minor = a rule missed with margin left. note = cosmetic.

What a pass needs
No blocker; no blocker-level item "could not run"; every FAIL row has a finding; every image has its line.
Verdict, in these words: REJECT | FIX AND RE-CHECK | OK FOR THE CONCEPT PRINT.

Report
Write <REVIEWS>/REVIEW_FINDINGS_print_M<N>.md after the skeleton (one line per ID in its findings table; the blocks follow): header (review type; model <MODEL>, effort <EFFORT>; date;
the frozen folder and the sha256 of the assembly STEP); verdict; counts of passed, failed, could not run, not
applicable; the check table; findings; images opened; what you could not judge and what would settle it.
For a re-check scope answer, per ID: "fixed and complete?" and "new problem introduced?" in the re-check section of the same file.

Prohibitions
Report only. Change no project file. No installs, downloads, messages, sign-ins or supplier sites. Do not open
another reviewer's report. No personal names, accounts, addresses or order numbers in the report; paths relative
to <FROZEN>.
```
