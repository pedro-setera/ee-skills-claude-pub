# Phase 15: assembly manual

Make the assembly manual from the model's own assembly order: one picture per step with call-outs, one to three lines of text, the fasteners at true scale, and the one thing that goes wrong marked in red. Correct it after the real assembly.

> **PROVISIONAL (waits for evidence):** this whole phase. The scripts and the page layout are proven on a made-up device; the procedure has not yet been corrected by a first real assembly done from the manual. What will be measured then: whether every screw, connector and cable went in in the planned order, the assembly time, and which pages had to change.

## Inputs

- The model with `ASSEMBLY_ORDER`, the sweeps of phase 4 (each insertion proven), the real parts and fasteners, `cables.json`.
- `out/views/`, `out/renders/` (current: run the build first), the camera files beside each picture.
- `scripts/views.py`, `scripts/render_blender.py`, `scripts/annotate.py`, `scripts/manual_build.py`; `templates/steps.example.toml`, `templates/manual.css`.
- `arrival/FIT_REPORT.md` when the real assembly has happened; the makers' assembly pages of the bought parts.

## Steps

1. **Take the steps from the model, not from memory.** The order is `ASSEMBLY_ORDER`; each step that inserts a part along a path was proven by a sweep in phase 4. A first manual once had the wrong order and the wrong number of screws to secure; the model's insertion check gave the right instruction ("tilt the board in").
2. **Write `manual/steps.toml`** (copy `templates/steps.example.toml`): the parts list, then per step a title, one to three lines of at most 120 characters, the parts and fasteners it adds with quantities, the tools, an optional `warning` (the one thing that goes wrong), `threadlocker = true` where needed, and `open = [...]` for anything not yet verified.
3. **Make one picture per step.** Add shots or views that show the step: the parts already fitted, the new part, the direction of motion. Use `[[views.section]]` or `[[render.shot]]` in `mech.toml`, then run `views.py` or `render_blender.py` through the build. Without Blender the plain views are used.
4. **Add the call-outs.** One spec file per picture in `manual/callouts/` (`[image]`, `[[callout]]` with anchors in model millimetres, `[[arrow]]`, `[warning]`), then
   `python -I <skill folder>/scripts/annotate.py --project <project>/mech <project>/mech/manual/callouts/step01.toml`
   Anchors are projected with the picture's camera file, so a call-out points at the real place. A row fails when boxes overlap or leave the picture. Output: `out/manual/annotated/<name>.png`.
5. **Real fasteners, true scale.** Name each fastener by size and head ("M3 x 8 pan head"); the manual draws them at true size on the parts page. Pictures with fake screws were once called unusable and redone.
6. **Wiring steps come from the cable data.** Each cable by its label text, from which connector to which, with the polarity or pin-1 mark shown. A fan pin-out drawn from memory was once wrong on a wiring sheet; read the maker's page.
7. **Build the manual:**
   `python -I <skill folder>/scripts/manual_build.py <project>/mech/manual/steps.toml --project <project>/mech --pdf --png`
   It writes `out/manual/assembly-manual.html` (self-contained), the A4 PDF and one picture per page in `out/manual/pages/`. Rows: every step has a picture; no picture is older than the model; text length; parts used equal parts listed; the step order follows `ASSEMBLY_ORDER`; tool icons known; the count of OPEN items.
8. **Look at every page picture** and write what you saw: the picture comes first and shows the step, the call-outs point at the right parts, nothing is cut off, the warning is the red one. Pictures first: a picture with an overlay and a simpler line does more than a paragraph.
9. **Keep customer documents apart.** This manual is for the person who assembles. Pictures for a user guide show the closed device, not its inside, and are a separate document.
10. **Correct after the real assembly.** Walk `FIT_REPORT.md`: every step that went differently, every extra hand-work step with its minutes, every warning the assembly taught. Close the OPEN items, then build with `--strict` (an open item then fails).
11. **Put the manual into the one build** so it is regenerated after any model change, and tell the user where the HTML and the PDF are.

## Rules for every step page

- The picture comes first and fills most of the step; the text is one to three short lines under it.
- The new part is in its own colour, the parts already fitted are grey, the direction of motion is an arrow.
- Every part and fastener named in the text has a call-out on the picture, and the counts agree.
- Exact names in bold: the part number, the connector's label, the screw size.
- At most one warning per step: the one thing that goes wrong, in the red frame.
- Threadlocker, where needed, is marked on the screws it applies to, not in a general note.
- No product secrets and no customer-facing wording: this is a workshop document.

## Questions for the user

Nothing to decide. Ask for a read:

- Please read the draft pages (PDF, `<n>` pages). Is any step unclear or in the wrong order?
  - Suggested: read it once at the bench with the parts at hand.
  - Why: you are the first person to assemble from it; a wrong page found now costs minutes.

## Done when

- [ ] Every step of `steps.toml` follows `ASSEMBLY_ORDER` and has a picture that is not older than the model. Evidence: the `manual_build` rows.
- [ ] Every call-out picture passed its rows. Evidence: the `annotate` rows.
- [ ] The parts and fastener totals of the manual equal the model's parts list. Evidence: the "parts used" row.
- [ ] Every page picture was looked at. Evidence: the "seen" notes with page numbers.
- [ ] After the real assembly: no OPEN item is left and `--strict` passes. Evidence: the headline.
- [ ] The user read the draft. Evidence: their words and the date.

## Outputs

- `mech/manual/steps.toml`, `mech/manual/callouts/`
- `out/manual/assembly-manual.html`, `assembly-manual.pdf`, `pages/`, `annotated/`

## If something is missing

- No Chrome or Edge: the HTML is still written; the PDF part reads "could not run"; the user prints the HTML from their browser.
- No Blender: the plain views are used and the manual says nothing about it; tell the user the pictures are not photo-real.
- No `ASSEMBLY_ORDER` in the model: the order row is "not applicable"; write the order into the model first rather than only into the manual.

## Lessons behind this phase

- A first manual had the wrong step order and the wrong screws to secure; the model's insertion check gave the right one -> step 1.
- Pages with fake screws and a part in the wrong place were called unusable and redone -> steps 3 and 5: pictures from the current model with real fasteners.
- A wiring sheet had two fan connectors swapped -> step 6: wiring from the cable data and the makers' pages.
- Long paragraphs were not read; a picture with an overlay and one line was -> step 8.
- Pictures older than the model stayed in a manual after a change -> step 7: the "fresh" row, and the manual in the one build.
- The procedure still waits for a first real assembly from the manual (see the PROVISIONAL line).

The full cases are in `references/lessons.md`.
