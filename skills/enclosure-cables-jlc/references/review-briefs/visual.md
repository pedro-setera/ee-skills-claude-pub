# Review brief: visual, from pictures only (V)

## For the launcher

**When to use.** Phase 7 (before the print) and phase 10 (before the order), in every set, after you have looked at
every picture yourself. The raised set of phase 10 runs it twice (`<N>` = 1 and 2, apart, merged by union). It
answers one question: would a careful person looking at the pictures see anything wrong?

**Set explicitly in the agent call.** The most capable model with image input, the highest effort. Write both into
the slots and the state file.

**Freeze and pass: pictures only.** A reduced copy, `reviews/frozen/print-r1_visual/` or `order-r1_visual/`, made with `freeze.py --profile visual`
(pictures of `out/views`, `out/renders`, `out/drawings/pages`, `out/silk` and the route pictures of `out/cables`; add
the others of this list with `--include`, and the two texts):

- Phase 7: `out/views/` (front, back, top, bottom, left, right, perspective, exploded, sections), `out/renders/`,
  the slicer previews, the route pictures of `out/cables/`, the coupon legend.
- Phase 10, in addition: every page of every drawing as a picture (`out/drawings/pages/`), the ink sheet picture,
  **the factory view** (`ink_sheet.py --factory-view`: the print file on a dark background), every cable drawing as
  a picture, the pictures that go into the upload. For a metal part also: all six faces, a section through the
  clinch nuts, a view with the lid off showing the screws and the parts inside (`views.py` `[[views.section]]` and
  `[views] hide`): without them the reviewer cannot judge screws, nuts and what is inside.
- Two short texts only: `PANEL_TEXT.md` (the approved wording per panel, the chosen coat and ink names) and
  `PARTS_SEEN.md` (a plain list of the parts that should be visible, with counts: screws, feet, jacks, vents).

**Do not pass:** models, STEP files, check reports, drawings' data files, the state file, any conclusion.

**Slots.** `<FROZEN>`, `<REVIEWS>`, `<SCRATCH>`, `<SKILL>`, `<N>`, `<MODEL>`, `<EFFORT>`, `<STAGE>` "before the print"
or "before the order", `<SCOPE>` "full review" or "re-check of findings <IDs>: old pictures <folder>, new <folder>".

**After it reports.** Accept only a report with one line per picture and a crop per finding.

## The prompt

```text
Role and goal
You are independent visual reviewer <N> of an enclosure and its cables, stage: <STAGE>. You did not design it. You
work from pictures only, as a careful technician who must build it and as a customer who will look at it. Find
everything that looks wrong, misleading, unfinished or unprofessional. Scripts have checked this design; scripts
have passed a connector over a screw hole, feet drawn upside down, a jack unlike its twin, and a print file whose
black text would have been printed white. Your eyes are the check. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.

Inputs
- Reduced frozen copy, read-only: <FROZEN> (pictures; PANEL_TEXT.md; PARTS_SEEN.md)
- Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md
- Your folder for crops and zooms: <SCRATCH>
You have no model and no check reports, on purpose. If a picture you need is missing or too coarse, that item is
UNKNOWN and the missing picture is a finding.

Method  (keep <REVIEWS>/V<N>_PROGRESS.md up to date)
1. List every picture. Open each at full size. Make your own crops and zooms.
2. Walk PARTS_SEEN.md: find each part in at least one picture and count it. Tick only what you saw.
3. Walk every face of the box: front, back, left, right, top, bottom, inside with the lid off.
4. Stage "before the order": walk every drawing page, the ink sheet, the factory view, every cable drawing.

Scope checklist  (each item ends PASS, FAIL, UNKNOWN or NOT APPLICABLE, with the crop that shows it)
Box, both stages
A. Every screw hole: a real screw, the right head, flush or seated; nothing over the hole; a tool can reach it.
B. Every connector, switch, LED, jack: through its wall, centred in its cut-out, enough thread or body outside,
   its plug has room; twins look alike.
C. Every vent group: a complete regular pattern, no hole missing, none cut by an edge, none behind a part.
D. Feet, frames, soft parts: the right way up, in place, touching what they should.
E. Parts inside: nothing floating, nothing passing through another part, cables under boards and not across fans.
F. Colours and materials look like what PANEL_TEXT.md names; metal looks like metal, a screen shows a screen.
G. Exploded and section views: the stack order makes sense; nothing is left over.
H. Balance: groups centred or aligned, equal margins, nothing crowded against an edge.
Print stage
I. Slicer previews: thin stacks, flat steps under thin parts, unsupported overhangs, long bridges, sparse infill
   under a post, support where the plan says none.
Order stage
J. Drawing pages: every hole and cut-out has an ID and a row; no text over text or over geometry; no clipped
   table; views match the renders (count the holes).
K. Words on any page, picture or file name: anything that reads as a request, a question, a colour system, a
   masking zone, a person or a product name.
L. The ink sheet: each legend where PANEL_TEXT.md says, spelled right, readable on the coat colour, clear of
   holes, edges and bends; the ink table lists only the named inks.
M. The factory view: every colour on an INK layer is an ink the factory will print (its header names those layers).
   The two REFERENCE layers (outline, bend lines) are drawn dashed in a colour of their own, normally green and
   yellow; the legend says "NOT PRINTED (reference)" and the ink sheet lists them as "NOT printed". Is there any
   other colour, any white line, or a reference colour that is also the colour of an ink in the ink table? Any closed outline that is not meant to be printed? Is black text shown black?
N. Cable drawings: ends named P1, P2; one length with a tolerance; a cavity table for every housing with EMPTY
   positions; a pin-1 mark; an orientation picture for angled plugs; colours in the table match the picture.
O. Would you be content to hand this to a customer?

Look at the pictures and report what you saw  (mandatory; it is the whole review)
- One line per picture: file name and what it shows, also when nothing is wrong.
- Every screw hole, connector, cut-out, label and vent group has its own line, zoomed.
- State the counts: parts in PARTS_SEEN.md, parts found.
- Save a crop per finding in <REVIEWS>/crops/V<N>/. A statement without a crop path does not count.

Evidence rules
PASS = you saw it, name the picture. FAIL = you saw the defect, name the crop. UNKNOWN = the pictures do not show
it; say which picture would settle it; never a pass by assumption. An item you did not look at is FAIL "not
inspected".

Findings  (one block each)
  ### V<N>-<letters><number>  <one-line title>
  - Severity: blocker | major | minor | note
  - Where: face or page, and the place on it
  - Evidence: the crop path and what it shows
  - Consequence: what the builder, the supplier or the customer would do or think
  - Proposed fix: concrete
Letters: B, MJ, MN, N. blocker = wrong assembly, a wrong print, or a supplier question for certain. major = reads
as a defect to a customer, or likely a supplier question. minor = crowded, uneven. note = cosmetic.

What a pass needs
No blocker; no blocker-level item UNKNOWN; a line for every picture.
Verdict: REJECT | FIX AND RE-CHECK | OK.

Report
<REVIEWS>/REVIEW_FINDINGS_<print or order>_V<N>.md after the skeleton (one line per ID in its findings table; the blocks follow): header (stage; model <MODEL>, effort <EFFORT>; date; the frozen
folder); verdict; counts per severity; findings; pictures looked at (picture, crop, what I saw); what pictures
cannot show. For a re-check: the re-check section of the same file, old against new picture per ID.

Prohibitions
Report only. Do not ask for or open models, check reports or another review. No installs, downloads, messages,
sign-ins, supplier sites. No personal names or order numbers in the report.
```
