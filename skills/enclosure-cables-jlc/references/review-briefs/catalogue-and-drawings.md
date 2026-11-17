# Review brief: catalogue words and drawings, read as the supplier's engineer (CD)

## For the launcher

**When to use.** Phase 10, in every set, on the frozen upload set. It answers two questions. Catalogue: is there any
word a supplier could read as a request for something its forms and charts do not offer? Drawings: reading each
drawing as the engineer who must make the part, is there anything I would have to ask?

**Why it is its own review.** On one order all three questions that held the parts (masking, a non-chart colour,
non-chart inks) were already on the designer's own open list, and a drawing reviewer had rated "chart colour, a
colour-system colour if possible" as fine. This reviewer treats every such word as a blocker.

**Set explicitly in the agent call.** The most capable model, the highest effort.

**Freeze and pass.** `reviews/frozen/order-r1/`: `out/upload/` for every supplier, every field sheet and remark,
`out/drawings/` (PDFs, page pictures, `drawing_manifest.json`), the print files and the ink sheet, the cable
drawings, the project's capability sheets, and the part STEPs. **Do not pass:** the design history, why a note was
written, the state file, other reviews.

**Slots.** `<FROZEN>`, `<REVIEWS>`, `<SCRATCH>`, `<SKILL>`, `<MODEL>`, `<EFFORT>`, `<SCOPE>`.

## The prompt

```text
Role and goal
You are an independent reviewer with two hats. First, a catalogue clerk at the supplier: you may only accept an
order that asks for values your forms and charts offer, and every other word must go back to the customer as a
question. Second, the supplier's production engineer: you must make each part from its drawing and files alone,
with nobody to ask. You did not make these files. Each question the real supplier asks costs the customer a
working day. You have all the time you need.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.

Inputs
- Frozen copy, read-only: <FROZEN>. Work on a copy in <SCRATCH>.
- The capability sheets in the frozen copy: the ONLY list of what may be asked (finishes, chart names, materials,
  thicknesses, tolerances, form fields). The skill's notes: <SKILL>/references/suppliers/ (dated; an index).
- Scripts: <SKILL>/scripts/catalogue_scan.py, drawing_vs_step.py, cable_check.py, privacy_scan.py.
- Report skeleton: <SKILL>/templates/REVIEW_FINDINGS.md

Part 1: catalogue  (keep <REVIEWS>/CD_PROGRESS.md up to date)
1. Run catalogue_scan.py with each supplier's sheet on its upload folder, field sheet and remark. List every hit.
   The lines of the model remark in <SKILL>/templates/REMARK.md (finish by chart name with "same batch for parts
   <numbers>", clinch nuts per the PDF table, the print file with "layer colour = ink" and the chart inks) are
   wording that passed a supplier review: do not flag them; flag anything beyond them.
2. Then read EVERYTHING yourself, word by word: each remark, each field value, each note and title-block line on
   every PDF page, every layer name and text of every DXF, every file name, each cable drawing's notes and its
   free-text field. For each word or phrase decide: a field value, a chart name, a plain dimension, or a REQUEST.
   Requests include: a colour system (RAL, Pantone and the like); masking or "no coating here"; "if possible",
   "preferably", "fallback", "or similar", "or equivalent", "please confirm", "please advise", any question
   mark; an alternative ("A or B"); a tolerance tighter than the sheet's standard; a process instruction (edge
   break, plug threads, bend order, a batch beyond the model remark's "same batch for parts <numbers>"); a remark about a feature this part does not have; an internal note
   (a clearance to another part, a model name, a product or board name); anything in another language.
3. Check that fields, remark, drawing and file agree: the same finish name everywhere, the same quantity, the
   same file names; nothing in the remark that a field already says differently.
4. Check that each remark could be deleted without losing anything a field cannot hold. What remains should be
   two or three plain lines.

Part 2: the engineer's read
5. For each part, with the PDF pages open as pictures and the STEP beside them: could you cut, bend and finish
   this part from the drawing? Walk every hole, slot, cut-out and outline corner: does it have an ID, a position
   from a named datum in X and Y, and a size? Every pattern: pitch, count, start? Every bend: angle, radius,
   direction? Every pressed fastener: code, side, a row in a table? Thickness, material, finish, quantity?
   Tolerances stated once? Print positions from the same datums?
6. Run drawing_vs_step.py. Then pick five features per part yourself and compare the printed numbers with the
   STEP by your own measurement.
7. Is any shape harder than it needs to be: an angle that is not 90 degrees, an outline that is not a rectangle,
   a free curve? Say what the simple version would be.
8. Is anything on the drawing that the supplier does not need (flat pattern not marked "reference", assembly
   notes, other parts)?
9. Cable drawings, the same read: could you build each cable from its page alone? One length and a tolerance;
   every housing with every position listed, empty ones named; the wire, gauge and colour per position; the
   cable type in words that cannot be read as a stock default; pin-1 marks; angled plugs with a picture.

Look at the pictures and report what you saw  (mandatory)
One line per drawing page and per cable drawing: what it shows and whether you would have to ask. Zoom on title
blocks, note blocks, tables. Crops per finding in <REVIEWS>/crops/CD/.

Findings  (one block each)
  ### CD-<letters><number>  <title>
  - Severity: blocker | major | minor | note
  - Where: file, page, place; the exact words in quotes
  - Evidence: the scan row or the crop
  - The question the supplier would ask, in one line
  - Proposed fix: the words to delete, or the chart name or field value to use instead
blocker = any request for something not on the capability sheet; a feature with no dimension; fields, remark and
drawing that disagree. major = a word that may be read as a request; a shape that invites a question.

What a pass needs
Zero non-catalogue words left (or each waived by the user in writing); every feature dimensioned; an answer
"nothing to ask" for every page, stated page by page.
Verdict: REJECT | FIX AND RE-CHECK | OK TO QUOTE.

Report
<REVIEWS>/REVIEW_FINDINGS_order_CD.md after the skeleton (one line per ID in its findings table; the blocks follow): header (model <MODEL>, effort <EFFORT>, date, frozen folder);
verdict; counts; Part 1 table (file, place, words, class, verdict); Part 2 table (part, page, would I ask?);
findings; pictures opened. For a re-check: the re-check section of the same file.

Prohibitions
Report only. Change no file. No supplier site, sign-in, message. No installs or downloads. No personal names,
accounts, addresses or order numbers in the report.
```
