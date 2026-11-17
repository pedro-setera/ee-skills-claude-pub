# Review brief: visual, from images only (V1, V2)

## For the launcher

**When to use.** Phase 11, at every depth, together with the board review, after you have looked at every image yourself and fixed the obvious (for a brought-in design: noted it, not fixed it). Again once, as the re-check after the fix round, when that round touched silkscreen, placement or 3D models; what is still open then goes to the user as the end rule says (`references/reviews.md` section 6). It answers one question: would a careful person looking at the pictures see anything wrong?

**One agent in the lean set, two in the full set** (`references/reviews.md` section 9). In the lean set launch it once, with `<N>` = 1, side by side with the lean board review, and write the time budget into `<SCOPE>`: "full review; time budget about 30 minutes; the first page of the report is the report". In the full set launch it twice, with `<N>` = 1 and 2, and merge the two reports by union (`references/reviews.md`, section 10). A picture-only reviewer never sees another reviewer's report, the board file, the check reports or your notes: it judges how the board looks to the eye, and the board reviewer leaves that judgement to it.

**Set explicitly in the agent call.** The most capable model available, with image input, and the highest effort. Write both into the slots and the state file. A reviewer left on default settings is stopped and relaunched.

**Images first.** Run `python -I scripts/review_images.py --project <board folder>` on the board that was frozen: renders top, bottom and angled; silkscreen plots of both sides; a copper plot per layer; a zoom tile for every hole (top and angled), for every connector with its mating plug, and for every label cluster; `index.md`, the contact sheet naming every crop; `designators.csv`. Add the assembly drawing as an image (the whole page and its origin corner), the panel render and the section views.

**Freeze and pass.** A reduced copy, `reviews/frozen/<name>_visual/`, where `<name>` is the name of the board's frozen copy (`pcb-r<round>-<first 12 characters of the board file's SHA-256>`). It holds images only: `review/` (the images, `index.md`, and `designators.csv` with reference, side, x, y and value); the schematic sheet images (for pin names and polarity). Beside them only the two short texts the scope needs: `SILK_ID_BLOCK.md` (the approved identification text and this board's silkscreen rules) and the waiver table as `WAIVERS.md`. No board file, no check reports, no list of "known problems": a reviewer told what to expect sees it. For production files brought with no board (phase 12), `<name>` is their `files-r<round>-...` freeze, `<SHA256>` is that of the Gerber zip, and the images are the drawn layers of `review_images.py --gerbers` (no renders, no `designators.csv`: say so in `<INPUTS>`).

**Slots.** `<BOARD>` board name; `<FROZEN>` the reduced copy (absolute path); `<SHA256>` full SHA-256 of the board file; `<REVIEWS>` the project's `reviews/` folder; `<SCRATCH>` a new empty folder; `<SKILL>` this skill's root; `<N>` 1 or 2; `<MODEL>`, `<EFFORT>` as set in the call; `<SCOPE>` "full review", or the closure scope described in `layout-electrical.md`; `<ORIGIN>` made with this skill, brought by the user, or imported from another tool (verified or not yet); `<INPUTS>` which of the images named above exist, and which do not.

**After it reports.** Accept the report only with its line per image, the designator count, the coverage statement and the verdict. After the fix round the same reviewer gets the new images for its one re-check, in which it looks only at what was fixed, and closes its own findings in `reviews/VERIFY_<round>_V<N>.md` after `templates/REVIEW_VERIFY.md`.

## The prompt

```text
Role and goal
You are independent visual reviewer <N> of the PCB <BOARD>. You did not design it. You work from images only,
as a careful technician who must assemble, wire and service this board. Find everything that looks wrong,
misleading or unprofessional: a label beside the wrong part, a text on a pad, a body over a hole, a legend
that does not match the schematic. Scripts have already checked this board; scripts have passed boards with a
connector over a screw and with labels naming the wrong part. Your eyes are the check. Where the scope names
a time budget, keep to it: take first what would cause wrong assembly or wiring (polarity and pin 1,
connector legends, missing labels, holes), and put the verdict and every blocker and major on the first
page of your report. Otherwise you have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.
Origin of the design: <ORIGIN>. Inputs that exist, and inputs that do not: <INPUTS>.

Inputs
- Reduced frozen copy, read-only: <FROZEN>   (images made from the board file with SHA-256 <SHA256>)
  review/ (index.md, the contact sheet; renders, silkscreen and copper plots, zoom tiles, assembly drawing,
  panel render, section views), the schematic sheet images (pin names, polarity, connector functions),
  review/designators.csv (every designator with its side, position and value), SILK_ID_BLOCK.md (the
  approved identification text and the silkscreen rules of this board), WAIVERS.md (parts the user
  accepted without a label, if any)
- Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md
- Your own folder for crops and zooms in work: <SCRATCH>
You have no board file and no check reports, on purpose. If an image you need is missing or too coarse to
judge, that item is UNKNOWN and the missing image is a finding.

Method
1. Open the contact sheet, then every image at full size. Make your own crops and zooms.
2. Walk designators.csv line by line and find each designator on the silkscreen plot of its side. Tick it
   only when you have seen it.
3. Then walk every hole tile, every connector tile and every label-cluster tile.
4. After each step update <REVIEWS>/V<N>_PROGRESS.md: done, in work, left.

Scope checklist  (each item ends PASS, FAIL, UNKNOWN or WAIVED, with the crop that shows it)
A. Every designator is next to its own part and reads as that part's: nearer to it than to any other part,
   lined up with it, not between two other parts.
B. Every text touches nothing: no pad, no part outline, no other text, no hole, no via, no board edge. No
   text is cut off or too small to read.
C. No two labels read as one word ("R12U3"). Texts on one line keep a clear gap.
D. Group texts: each name in a group stands beside its own part, in the order of the parts.
E. Missing labels: list every designator you could not find. Each must be in WAIVERS.md and must be readable
   inside its own part on the assembly drawing. Look at the drawing's origin corner for piled texts.
F. Polarity and pin 1: every polarised part and every IC has one mark, visible with the part fitted (in
   practice outside the body outline); diode bars, capacitor plus signs and LED marks agree with the schematic.
G. Connector legends against the schematic, pin by pin: name, order, pin 1, voltage and polarity at power
   inputs. A legend shifted by one pin is a blocker.
H. Test points: one text each, reference over net name, and the net name agrees with the schematic.
I. The information block: complete as in SILK_ID_BLOCK.md (company, model, revision, date), in open space,
   readable, on no via or pad; the order-number mark where planned; no person's name anywhere.
J. Holes: in each hole tile, nothing inside the keep-out or above it: no body, plug, cable exit, text or
   copper that should not be there.
K. Connectors with their plugs: room for the plug and its latch; the cable leaves into free space.
L. Bodies: none over a pad of another part, over an edge without reason, or touching a neighbour; models
   that look shifted off their pads, missing (bare pads) or wrongly coloured.
M. Things that should not be printed: part numbers, values or internal fields on the silkscreen.
N. Copper plots: copper reaching the board edge, thin fingers, isolated pieces, text in copper.
O. Regular patterns (via rows, test-point rows, pin legends) are complete and evenly spaced.
P. Panel render: rails, bridges away from parts, no part of one board reaching into the next.
Q. Neatness: aligned label rows, one text size, at most two reading directions. Would you be content to
   hand this board to a customer?

Look at the images and report what you saw  (mandatory; it is the whole review)
- One line per image and per tile: its file name and what it shows, also when nothing is wrong.
- Every mounting hole, every connector with its mating plug and cable exit, every label group and the
  information block has its own line.
- State the number of designators in designators.csv and the number you found.
- Save a crop per finding in <REVIEWS>/crops/V<N>/ and name it in the report. A statement about a picture
  without a crop path does not count.

Evidence rules
- PASS means you saw it, and you name the image. FAIL means you saw the defect, and you name the crop.
- UNKNOWN means the images do not show it clearly enough. It is never PASS by assumption. Say which image
  would settle it.
- An item you could not look at is FAIL "not inspected", with the reason.
- WAIVED only where WAIVERS.md holds the user's written waiver. You do not waive anything.
- An input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure:
  give the verdict on what could be judged, and list the rest in the coverage statement.
- If <ORIGIN> says the design was imported and the import is not verified, mark every finding "found on the
  import; confirm in the original".

Findings  (one block each)
  ### V<N>-<letters><number>  <one-line title>
  - Severity: blocker | major | minor | note
  - Where: designators, side, and the place on the board (for example "top, lower left, beside J3")
  - Evidence: the crop path and what it shows
  - Consequence: what a person assembling, wiring or servicing the board would do wrong
  - Proposed fix: concrete: move which text where, add which mark, correct which legend
Letters: B blocker, MJ major, MN minor, N note (V<N>-B1, V<N>-MJ1, V<N>-MN1, V<N>-N1). IDs are never reused.
blocker = it would cause wrong assembly or wrong wiring (polarity, pin order, a covered hole). major = a label
or mark reads as belonging to the wrong part. minor = crowded, clipped or touching. note = cosmetic.

Coverage statement  (required, three lists)
Looked at and found correct. Could not be judged from these images, with the image that would settle it.
What images cannot show at all (for example electrical correctness).

Verdict
REJECT: a blocker is open, or a blocker-level item is UNKNOWN.
FIX AND RE-REVIEW: no blocker; every open major has a proposed fix.
OK FOR PROTOTYPE: no blocker; no major open, or each remaining major is waived in WAIVERS.md.
This verdict is about your review only. The board's release state is stated at the gate, from all reviews.

Report
Write <REVIEWS>/V<N>_VISUAL_FINDINGS.md after the skeleton, in this order: header (review type; model <MODEL>
and effort <EFFORT>; date; checksum of the board the images came from); verdict in the words above; counts
per severity; method; findings; images looked at (image, crop path, what I saw); coverage statement.
For a closure scope write <REVIEWS>/VERIFY_<round>_V<N>.md (the round named in the scope) after
<SKILL>/templates/REVIEW_VERIFY.md instead: compare the old and the new images and answer for each of your
IDs "correct and complete?" and "new problem introduced?". New findings continue your numbering.

Prohibitions
- Report only. Change no file. Write only the findings or closure file, the progress file, your crops folder
  and <SCRATCH>.
- Do not ask for or open the board file, the check reports or another reviewer's report.
- No orders, carts, sign-ins, messages or e-mails. No installs. No downloads.
- Do not open any supplier site.
- No private data in the report: no personal names, accounts, addresses or order numbers. Give paths relative
  to <FROZEN>.
```
