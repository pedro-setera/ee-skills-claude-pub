# Phase 0: start or resume

Find out what already exists, check the tools, create or read the state file, and enter the project at the right phase. A supplier's deadline that is already running comes before everything else.

## Inputs

- The user's request and whatever they bring: an idea, a board, a model, drawings, a quote, an open order, a parcel.
- `<project>/mech/PROJECT_STATE.md` if it exists.
- `references/working-rules.md` (once per session), `references/tools.md`, `references/interface-electronics.md`.
- `scripts/env_check.py`, `scripts/check_all.py`, `scripts/interface_read.py`; `templates/PROJECT_STATE.md`, `templates/mech.example.toml`.

## Steps

1. **Look for a running deadline first.** Ask, or read in the state file: is a supplier question, a production drawing or a payment step waiting? If yes, create a minimal state file (step 4, only the order block) and go to `13-watch.md` now. The rest of this phase is done afterwards. A request that waited over a weekend cost working days on one order.
2. **Find the project folder.** Default `<project>/mech/`. When a board lives in `hardware/<board>/`, its interface files stay in `hardware/<board>/mech/` and `mech.toml` points to them (`[paths] interface`). Never work inside the skill folder; nothing is written there.
3. **Check the tools.** Run:
   `python -I <skill folder>/scripts/env_check.py --project <project>/mech`
   It lists Python, CadQuery, the helper libraries, a slicer command line, Blender and Chrome. It never installs. Run it again after step 4 has written `mech.toml` with the user's `[tools]` answers: a path the user gives, or a tool the user refuses, is known only from there. A tool the user does not want used is written `slicer = "none"` (likewise `blender`, `chrome`) in `[tools]`: the table then says "declined by the user" (not missing), no script looks for that tool or uses it, and the rows that need it read "could not run". Write the table into the state file. For each missing tool say what then cannot run (`references/tools.md`) and ask before any install. A model check that did not run was once reported as "fine"; a missing tool gives a "could not run" row, never a pass.
4. **Create the state file** from `templates/PROJECT_STATE.md` when none exists: the way of use, the entry phase, the tools, the review depth facts as far as known (unknown counts as yes). Copy `templates/mech.example.toml` to `<project>/mech/mech.toml` and delete the sections the project does not use.
5. **When a state file exists,** read it fully, then check the frozen files against the checksums it lists (any sha256 tool) and run `python -I <skill folder>/scripts/check_all.py --project <project>/mech`: a STALE row means a file changed after its check. Report every difference before doing anything else, then continue at "Next action".
6. **Take the inventory.** Fill the table "What exists" of the state file: the board interface file (do its checksums verify? `python -I <skill folder>/scripts/interface_read.py --project <project>/mech`), a model, printed parts, drawings, cable data, capability sheets and their dates, quotes, orders. Files the user brings are copied into the project and their checksums recorded; the originals are never changed.
7. **Find the user profile.** Look for `~/.claude/enclosure-cables/PRINTER_PROFILE.toml` (in the user's home folder, outside the skill). If it exists, point `[printer] profile` in `mech.toml` to it and show the user its values in three lines. If not, phase 1 asks the printer questions; ask before creating the folder and the file. The profile holds the user's printer, materials and measured numbers, so they are asked once and reused in every project.
8. **Pick the entry phase** with the table below and write it into the state file with the reason. Say in one line what is skipped and what is therefore not evidenced.
9. **Set the review depth** from the facts (SKILL.md, "Reviews"): lean by default; one raising fact, or one unknown, raises it. Write the facts and the result into the state file.

## Entry table

| The user brings | Enter at | Checked first |
|---|---|---|
| A supplier question, a production drawing to confirm, a payment waiting | 13 | The order page and the deadline (`supplier_calendar.py now`); then the order log is rebuilt from the page |
| Only an idea, or a board and the wish for a box | 1 | The board's interface file, if a board exists |
| A board from the electronics skill, nothing mechanical | 1 (short), then 2 | The checksums of `interface.json`; the board's requirements page |
| A chosen arrangement, no model | 3 | Gate 0 is recorded with the user's words; if not, the picture and the approval of phase 2 first |
| A model in code, or a STEP of a box | 4 | It builds; real parts or blocks (`vendor_parts.py --list`); the views are looked at |
| Only cables (the box exists) | 1 (short), 5, then 9 to 14 | A model or measured poses for the routes; the source of each pin-out |
| Only a printed box | 0 to 7 | The printer profile |
| A printed box that fitted, now wants metal | 8 | The print findings are written; gate 1 is recorded, or the user's waiver in writing |
| A finished metal model, no drawings | 9 | The capability sheet is dated this month; each STEP is one solid |
| Finished files that need the order | 9 (documents check), then 10 | The checks of phase 10 on the user's files; nothing is uploaded unchecked |
| A review of someone's model or drawings, nothing to change | 10 (reviews only) | Files copied and hashed; the report names findings, the user decides |
| An order placed elsewhere that needs watching | 13 | The files that were uploaded, from the user's own copy; without them every Confirm is the user's |
| A parcel on the table | 14 | The drawings and the cable data that were ordered (frozen copies) |

## Project layout

```
<project>/mech/
  mech.toml  PROJECT_STATE.md  REQUIREMENTS.md  DECISIONS.md  LAYOUT_STUDY.md  CABLE_LIST.md
  HEAT_TABLE.md  GROUND_MAP.md  PRINT_FINDINGS.md  GATE0_SUMMARY.md  GATE1_SUMMARY.md  GATE2_SUMMARY.md
  interface.json  outline.json   board interface (in) and the mechanical input for the board (out)
  model/build_model.py           the parametric model: build() returns every solid
  layout/                        layout.toml, heat.toml, stiffness.toml, outline_desc.toml
  vendor3d/                      makers' STEP files, vendor_parts.toml, fasteners/
  cables/                        cables.json, routes.toml, second_measure.toml
  silk/                          artwork files for silk_dxf.py
  manual/                        steps.toml, call-out specs
  suppliers/                     <id>.capability.toml, dated
  reviews/                       review reports, frozen copies
  out/                           generated: step/ views/ renders/ drawings/ silk/ cables/ print/ heat/ layout/
                                 manual/ checks/ upload/<supplier>/ CHECKS.md
  orders/                        ORDER_PLAN.md ORDERING_CHECKLIST.md ORDER_LOG.md FIELD_SHEET_enclosure.md
                                 REMARK_<part>.md messages/ screens/ production_drawings/
  arrival/                       INCOMING_CHECK.md FIT_REPORT.md NEXT_REV.md photos/
```

## Questions for the user

- May I install `<tool>` (free) in its own Python environment?
  - Suggested: yes, CadQuery with its helper libraries.
  - Why: the model, the fit checks and the drawings are then made by scripts and can be rebuilt after any change.
- May I create `~/.claude/enclosure-cables/` in your home folder for your printer profile?
  - Suggested: yes.
  - Why: your printer and materials are asked once and reused in every project; nothing about you is stored in the skill.
- Is anything waiting at a supplier right now (a question, a drawing, a payment)?
  - Suggested: tell me first if so.
  - Why: each supplier day lost is a day on the delivery.

## Done when

- [ ] No supplier deadline is open, or phase 13 was started first. Evidence: the user's answer or the order page, dated, in the state file.
- [ ] The tool table is in the state file, each missing or declined tool with what could not run. Evidence: the `env_check.py` output.
- [ ] The state file exists with the way of use, the entry phase and its reason, the inventory and the review depth facts. Evidence: the file.
- [ ] `mech.toml` exists and `[printer] profile` points outside the skill, or the profile is marked "asked in phase 1". Evidence: the file.
- [ ] Every file brought by the user is copied and hashed. Evidence: the `source` block of the state file.
- [ ] An existing project: the checksums verify and `check_all.py` shows no STALE row, or each one is reported. Evidence: the headline.

## Outputs

- `mech/PROJECT_STATE.md`, `mech/mech.toml`
- The tool report (in the state file)
- The user profile folder, only with the user's yes

## If something is missing

- No CadQuery and no install allowed: reviews of drawings and the order phases still work; every model, fit and drawing check reads "could not run". Say so at every gate.
- No board interface file: fill `interface.json` by hand from the maker's STEP or drawing with the same keys, and write its source in it (`references/interface-electronics.md`).
- No state file but work exists: rebuild the state from the files and the order pages, and mark every gate "not evidenced" until the user confirms it in writing.

## Lessons behind this phase

- A supplier's request had been waiting over a weekend while the session set up tools: working days were lost -> step 1 looks for a running deadline before anything else.
- A session that lost its context spent an hour finding out which files were current -> steps 4 to 6: one state file with checksums, read first.
- A check was reported as fine although its tool was missing -> step 3: a missing tool is "could not run".
- The printer questions were asked again in every project -> step 7: one user profile in the user's home, outside the skill.

The full cases are in `references/lessons.md`.
