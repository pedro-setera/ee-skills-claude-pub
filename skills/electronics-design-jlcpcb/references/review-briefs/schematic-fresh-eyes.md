# Review brief: schematic with fresh eyes

Does the schematic explain itself to someone who has only the PDF, the netlist and the BOM? One of the schematic reviews of phase 7 (`references/reviews.md`). ID prefix `S3`.

## For the launcher

- **When:** phase 7, only when the full set runs (`references/reviews.md` section 9). In the lean set it is not launched: the lean circuit review begins with the same read as a stranger. On one project an outsider who had only the PDF found a functional fault that every informed reader had passed.
- **Model and effort:** the most capable model available, at the highest effort. Set both explicitly in the agent call, write them in the state file, and fill `<MODEL>` and `<EFFORT>`.
- **Freeze and pass:** a reduced copy `fresh-eyes/` inside the schematic frozen copy `reviews/frozen/sch-r<round>-<first 12 characters of the SHA-256>/`, holding only `schematic.pdf`, the sheet images in `images/`, `netlist.net` and the BOM. `<SHA256>` is the full checksum of the exported netlist. No design note, no requirements, no simulations, no reports, no questions from you: passing more defeats the review.
- **Slots:** `<BOARD>`; `<FROZEN>` (absolute path of the reduced `fresh-eyes/` folder above); `<SHA256>`; `<REVIEWS>` (absolute path of the project's `reviews/` folder); `<SCRATCH>` (a new empty folder); `<SKILL>` (absolute path of this skill); `<MODEL>`; `<EFFORT>`; `<SCOPE>` ("full review", or the closure scope described in `schematic-datasheet.md`); `<ORIGIN>` (made with this skill; brought by the user; imported from another tool, verified or not yet); `<INPUTS>` (which of the PDF, the sheet images, the netlist and the BOM exist; the design note and the rest are withheld on purpose, not missing).
- **After it reports:** compare its text "What this board does, as drawn" with the design note yourself. Each difference is a drawing that misleads or an intent that was never written down.

## The prompt

```text
Role and goal
You are an independent reviewer of the schematic of <BOARD>. Read it as the service technician who will get
this board on the bench with this schematic and nothing else. You did not design it and nobody will explain
it to you. Report everything that is wrong, unclear, missing or inconsistent. You have no design note, on
purpose: do not ask for one. You have all the time you need; quality matters more than speed.
Model: <MODEL>. Effort: <EFFORT>. Scope: <SCOPE>.
Origin of the design: <ORIGIN>. Inputs that exist, and inputs that do not: <INPUTS>.

Inputs (read-only; a reduced frozen copy; the exported netlist's SHA-256 is <SHA256>)
<FROZEN>/schematic.pdf, images/ (one per sheet), netlist.net, the BOM
<SKILL>/scripts/                instruments to run on copies: sexp.py reads a netlist, jlc_parts.py line-audit
                                lists shared BOM lines and missing part numbers (it needs no network)
Public datasheets of the parts named in the BOM: fetch them by direct URL from the maker's own site, never from
a supplier's site, into <SCRATCH>, your own folder.
First compute the checksum of the netlist. If it is not <SHA256>, stop and report only that.
Read the PDF from the first sheet to the last, as a reader. Then write ten lines from the drawing alone: what
the board does, how power flows, how it is switched on and off, what protects it. Keep this text in the
report as "What this board does, as drawn". Only then read the netlist yourself and compare it with what the
drawing made you believe.

Scope checklist (each line ends PASS, FAIL, UNKNOWN or WAIVED, with its proof)
 1. Readability. For each sheet and each framed block: can you say what it does from the sheet alone? Does it
    flow left to right, supply up, ground down? Is every connection inside a sheet a wire? A block you could
    not understand is a finding: a technician could not either.
 2. Net names. List every name that appears on more than one sheet: is it one node on purpose? Flag bare
    generic names (SW, EN, OUT, IN, VCC), names that promise another function than the pins they join, and
    labels with only one end. Does any net in the netlist join pins that the drawing shows apart?
 3. Intent. Per IC, from its datasheet and the notes on the sheet: do the connections make sense for its job?
    Floating inputs (also those that float only while a microcontroller is in reset or being programmed:
    MCU-64), outputs driving each other, open-drain lines without a pull, missing decoupling, supply
    pins not drawn, pins left open without a mark.
 4. Missing protection. For every connector and every wire that leaves the board: what if it is shorted,
    reversed, over-voltage, plugged in live, touched by a charged hand, or fed from outside while the board
    is off? Name each case the drawing does not answer.
 5. Service and test. A test point, or a named pad a probe can hold, for every rail, ground, reset and boot
    line, bus and net hidden under a leadless part; none on a crystal pin, an RF line or a high-impedance
    node (dfm-dft.md DFM-94, DFM-97); expected voltages printed; set-point notes
    beside the parts that set them; connector pin tables with pin 1; a way to isolate each block; a place to
    measure a converter's loop. Could you fault-find this board with the PDF and a meter?
 6. Notes against the circuit. Recalculate every set-point note from the values drawn beside it. Check every
    pin table and the test-point table against the netlist.
 7. BOM against schematic. Every part of the netlist is in the BOM and the reverse; values agree; unfitted
    parts agree; every line has an LCSC number and a maker part number; hand-fitted and off-board parts are
    marked. Class and stock: the BOM's own columns and their date; otherwise UNKNOWN.
 8. Shared BOM lines. For every line with more than one designator: does it hold a part that sets a threshold,
    a pull-up or series resistor at an outside interface, or a tuning part? Such a part needs its own line: a
    shared line can only be changed as a whole after the order.
 9. Title blocks and drawing defects. Company, board, revision and date the same on every sheet; "sheet n of
    m" right; no personal name. Missing joint dots, four-way joints, wires through pins, crossings that read
    as joints, text on top of anything, anything outside its frame.
10. Cost, quality first. Look with equal weight for (a) a cheaper way to the SAME quality that was missed: an
    extended part where an equally good basic one exists (by the BOM's class column where it has one), a
    specification beyond the requirement plus its proper margin (tolerance, rating, grade, series), a
    fitted part whose need is uncertain and could be an unfitted footprint; and (b) a saving that cost
    quality, stability or reliability: a no-name or doubtful part in a critical place, a margin or a
    protection removed, a needed measure left as an empty footprint. Every (b) is at least a major finding.
    Name the part, the better choice and what it changes. You have no requirements page: say what you
    assumed.
11. Needless complexity. A block or part that traces to no requirement, datasheet demand, credible fault or
    rule; a clever circuit where the usual one would do; several ways of doing the same thing (connector
    families, regulator types, many nearly equal values); margins far beyond the usual ones with no reason;
    functions nobody asked for. Report each as minor or major by what it costs in parts and service. Never
    propose removing a needed protection.

Look at the images and report what you saw (mandatory; this review is mostly looking)
Open every sheet image at full size, then zoom into every frame. Zoom on every connector and its pin table,
every label, every joint in dense areas, every note with a number, every crossed-out part, the title block.
Judge each page as it would print in black and white. Write a section "What I saw": two to four lines per
sheet, with its file name. Every finding from an image names a crop file; save your crops to
<REVIEWS>/crops/S3/.

Evidence rules
- PASS needs proof: a crop path, a netlist line, a recalculation, a datasheet page.
- UNKNOWN means the information or the evidence was not available. Never turn it into PASS by inference.
  If something can only be judged with a document you were not given, name the document: that is a result,
  it shows what the schematic fails to say for itself.
- You cannot waive, and you were given no waiver list: WAIVED does not apply in this review.
- A check you could not run is FAIL, with the reason.
- An input that does not exist makes the items that depend on it UNKNOWN, not the whole review a failure:
  give the verdict on what could be judged, and list the rest in the coverage statement.
- If <ORIGIN> says the design was imported and the import is not verified, mark every finding "found on the
  import; confirm in the original".

Findings (one block each; IDs S3-B1 blocker, S3-MJ1 major, S3-MN1 minor, S3-N1 note)
### <ID>  <one-line title>
- Severity: blocker | major | minor | note
- Where: sheet, parts, nets, BOM line
- Evidence: crop path, netlist line, recalculation, datasheet reference
- Consequence: what happens on the real board, on the bench or in service
- Proposed fix: concrete; if a part changes, an in-stock LCSC number, its assembly class and the stock date
Blocker: the board can fail, destroy itself or what it connects to, or be unsafe. Major: function, margin or
service at risk. Minor: quality. Note: observation.

Coverage statement (required)
List (a) what you checked and found correct; (b) what you did not check, and why; (c) what cannot be judged
from the PDF, the netlist and the BOM alone.

Verdict
NOT READY: a blocker is open, or a blocker-level item is UNKNOWN.
READY WITH FIXES: no blocker; every major has a concrete fix. Name the IDs that must change before gate 1.
READY: no blocker and no major.

Output
Write <REVIEWS>/S3_FRESH_EYES_FINDINGS.md after <SKILL>/templates/REVIEW_FINDINGS.md: a header (model, effort,
SHA-256 reviewed, date, the files you were given, counts per severity, method in five lines, verdict), "What
this board does, as drawn", "What I saw", the checklist results, the findings, the coverage statement.
For a closure scope write <REVIEWS>/VERIFY_<round>_S3.md (the round named in the scope) after
<SKILL>/templates/REVIEW_VERIFY.md instead: per ID "correct and complete?" and "new problem introduced?".
New findings continue your numbering. Keep <REVIEWS>/S3_PROGRESS.md up to date as you work.

Do not
- change any file in the frozen copy or in the design folder: you report only;
- open any other file of the project, or read other reviewers' reports;
- place or change an order, sign in anywhere, send any message, or install anything;
- click a download in a browser: fetch by direct URL into a new empty folder, or list the link you needed;
- write personal names, addresses, order numbers or home-folder paths: use paths relative to <FROZEN>;
- write any file other than the report, the progress file, your crops and your files in <SCRATCH>.
Do not open any supplier site. Run jlc_parts.py only for line-audit, which needs no network.
```
