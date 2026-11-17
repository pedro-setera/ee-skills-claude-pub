# Phase 0: start or resume

Find or create the project state, check the tools, and decide where the project enters the flow.

Paths that begin with `scripts/`, `templates/` or `references/` are inside this skill's folder, not in the user's project; call scripts by their full path. Paths such as `hardware/<board>/` are in the user's project.

## Inputs

- The user's request, in their own words.
- The user's project folder, if there is one: any schematic, board, production files or order references in it.
- `SKILL.md` and `references/working-rules.md`, read in this session.
- `templates/PROJECT_STATE.md`, `scripts/env_check.py`, `references/tools.md`; when the user brings files, `references/existing-designs.md` and `scripts/import_design.py`.
- `references/lessons.md`, section "Phase 0: start or resume".

## Steps

**A manufacturer's deadline comes first.** If a placement confirmation or an engineering question is waiting, create a minimal state file (board name, order references, the event and its deadline), skip the rest of this phase, and go straight to the step of `references/phases/14-watch.md` for that event. Finish this phase after it is answered.

1. Look for `hardware/<board>/PROJECT_STATE.md` in the user's project. If several boards exist and the request does not name one, ask which. If the user has no project folder yet, propose one and a short board name (lower case, no spaces) and use them once agreed.
2. If the state file exists, resume. Do this in order, before any design work:
   - Read the whole file: the header, the decisions, the open questions, the waivers, the agents listed as running, "Next action".
   - Recompute the SHA-256 of every file named under `frozen:` and compare. A changed frozen file means the reviews done on it no longer cover it. Stop and say which file changed; do not continue at "Next action" until the user decides: restore the file, or freeze again and run a scoped re-review.
   - Check each gate flag against its evidence: the gate summary file and the user's approval words with a date. A flag without evidence counts as open.
   - Read the progress file of every agent listed as running. An agent that is gone restarts from its progress file, not from zero.
   - Run the tool check of step 4 and compare its versions with the recorded ones. A newer KiCad saves files in a newer format, and that cannot be undone. Report it and do not save project files with it before the user agrees.
   - Tell the user in three lines: where the project stands, the next action, what changed since the last session. Then continue at "Next action".
3. If there is no state file, create the folder tree below and copy `templates/PROJECT_STATE.md` into it. Fill the header: phase 0, all gates open, `review_depth: lean` until phase 1 decides the depth from the facts (`references/reviews.md` section 9), `review_parallel: 2`. Create `board.toml` (it may start empty); its tables are written in the phase that knows their content, and `references/tools.md` section 4 lists them all with the step that writes each.
4. Run `python -I scripts/env_check.py`. Keep its report in `out/` and copy the versions into the state file. For each missing tool, read in `references/tools.md` what the gap disables and what to do without it. Exit code 1 means only that something optional is missing; read which. A common case on a fresh KiCad install: the row "KiCad global library tables" is missing because KiCad was never opened. It does not affect schematics made here (they carry their own library); for a design the user brings, ERC then warns about every stock symbol, and those warnings come from the machine, not from the design. The tables appear when the user opens KiCad once and accepts its default libraries; a script never creates them.
5. Ask before installing anything: one question that lists every install with its version and official source. An install changes the user's machine; that is theirs to allow.
5b. Ask once, with the installs if any, for the yes to live part look-ups: JLCPCB's public parts search, LCSC's product and file servers, and the community copy jlcsearch.tscircuit.com, at the human pace of `references/working-rules.md` section 8. Record the answer; without it the user does the look-ups (`references/phases/03-parts.md` step 2b).
6. Decide the way of use and the entry phase from the table below. Write the row that applied into the state file (`way_of_use:` and the log).
7. **When the user brings files,** read `references/existing-designs.md` first and follow it. When the user's folder is the KiCad project itself, the project tree of this skill is a new folder beside their files, proposed and agreed as in step 1. The user's files are never modified:
   - Ask once for the richest form they have (its section 2) and, for a design from another tool, that tool's own exports (netlist, BOM, drill and Gerber files) for the import check.
   - Copy them into the project tree before anything opens them, and work on the copy; KiCad can rewrite a project when it loads it. Record under `source:` in the state file the original path, the tool and format, the date copied and the checksums.
   - A design from another tool (its section 2b): `python -I scripts/import_design.py --list` shows what the installed KiCad reads; `board <file> --out kicad/` imports a copy of the board; `schematic <file>` prepares a copy and prints the clicks for KiCad's own import dialog; `verify <imported board>` compares the import with the user's own exports (netlist, BOM, drill, Gerbers). Until it passes, every finding reads "found on the import; confirm in the original". The user's tool stays the master unless they move the design.
   - Decide the depth yourself, from the facts of `references/reviews.md` section 9 read on what was brought (the parts list, the layer count, the finest pitch, what the user says the board is for). The lean set for each kind of input is in section 3 of `references/existing-designs.md`. One fact is enough; what you cannot rule out counts as present. Tell the user the depth and its facts in one line with your first message; they may overrule it. Do not ask it as a question.
   - List which documents of the earlier phases exist and which are missing. A missing document is a missing proof: the checks it would carry are UNKNOWN, not PASS. Recover the catch-up documents its section 4 names for the entry phase.
   - Record the way of use, the source, the import result and every gate the user chose to skip, with their words.
8. If the project is under version control, propose storing `hardware/` byte for byte (line-ending conversion off for that folder only) and apply it on the user's go, before the first board file is stored. Never change their version-control settings silently. A converted file has a new checksum, and the checksum is the proof that the file ordered is the file reviewed.
9. Agree the working frame and record it with the date and the user's words:
   - the gates that lie ahead of the entry point (schematic, PCB, payment): nothing passes one without their approval;
   - the events they want a notice for, from one list: a gate is ready; a payment is waiting; the manufacturer asks something or needs a confirmation; the order's main status changes; the boards ship. And the channel. The order and mailbox watches are asked once, in phase 14;
   - the folder where they open files;
   - the limit for costly agents running at once (default 2).
   When the project starts at phase 1, put these into the phase 1 question round instead of asking twice.
10. Write "Next action" as one concrete step, and tell the user what happens next. A new design's first real step is phase 1: getting every requirement, with suggestions, until the page has no blank heading and the user confirms it (gate 0); no concept starts before that.

### Way of use and entry phase

| Way of use (what exists or is asked) | Enter at | Before going on |
|---|---|---|
| New design: an idea, a wish list, a specification or chosen key chips | 1, then 2 | From written material, fill the requirements page and ask only the gaps |
| Next revision | 0 with the old files, the bench findings and `NEXT_REV.md`; then every phase a change touches | A new revision in the state file, the old one archived |
| Anything the user brings: a schematic, a board, production files, an order placed elsewhere, boards on the bench; to review, fix, continue or order | The row of the table of ways of use in `references/existing-designs.md` section 1 (a finished board, for example: catch-up on the circuit, the phase 10 checks without fixing, then phase 11) | Step 7, and the catch-up documents of its section 4. Simulations of a brought-in design are offered, not required. With boards on the bench: say at once that no board is powered before the plan exists |
| A manufacturer's deadline is pending | 14, at the step for that event | The paragraph above step 1 |

When an earlier gate has no evidence, say it plainly and recommend running that gate's reviews first: a layout check cannot find a wrong circuit. Skipping a gate is the user's decision. Record their words under "Gates skipped by the user" in the state file; every later summary says "gate N not evidenced" in its "Evidence status" block.

### Project folder (created in the user's project, never inside this skill)

```
<project>/hardware/<board>/
  PROJECT_STATE.md      phase, gates, decisions with the user's words, open questions, next action, checksums
  board.toml            the per-project settings the scripts read
  REQUIREMENTS.md  DESIGN_NOTE.md  REFERENCE_CHECK.md  LAYOUT_RULES_LEDGER.md
  BOARD_DEFINITION.md  SILK_ID_BLOCK.md
  kicad/                the KiCad project: schematic sheets, board, rule file, libraries
  src/                  this project's generator scripts; expected_connectivity.toml (the hand-written intent file);
                        datasheet_pins.toml (the hand-typed pin and rating tables)
  vendor/datasheets/  vendor/jlc_fp/  vendor/3d/
  sim/                  PLAN.md, test benches, models, out/, RESULTS.md
  reviews/              frozen/<sch|sim|pcb|files>-r<round>-<first 12 of sha256>/, <prefix>_<NAME>_FINDINGS.md,
                        <prefix>_PROGRESS.md, crops/<prefix>/, RESPONSE_<round>.md, VERIFY_<round>_<prefix>.md
  mech/                 outline.json (the mechanical input), interface.json (generated from the board)
  out/                  CHECKS.md, script reports, review/ (images for reviews), jlc/ (upload folder), panel/,
                        order/ and order/crops/ (order screenshots), 3d/ (STEP and renders)
  GATE1_SUMMARY.md  GATE2_SUMMARY.md  ORDERING_CHECKLIST.md  FIRST_POWER_UP.md
  FIRMWARE_HANDOVER.md  PRODUCTION_RELEASE.md  ORDER_LOG.md  NEXT_REV.md
  AUDIT_SUMMARY.md  ECO_LIST.md        for a design that was brought in (review, change list)
```

## Questions for the user

Ask only those that apply, in one numbered round.

- Which board should I work on? (only when several exist and the request does not say)
  - Suggested: the one changed most recently, named with its path.
  - Why: it is the likeliest; working on the wrong board wastes a session.
- `<tool> <version>` is missing. It is needed for `<what>`. May I install it?
  - Suggested: install it from `<official source>`.
  - Why: without it `<what will not run>`. Use the wording of `references/tools.md`.
- May I look parts up live at JLCPCB's public parts search, LCSC's product and file servers and the community copy jlcsearch.tscircuit.com, slowly, one request at a time?
  - Suggested: yes.
  - Why: stock, prices and datasheets come from there; without it you look each part up yourself.
- Which files of this design can you give me? (when the user brings a design)
  - Suggested: the native project folder; for a design from another tool also its own netlist, BOM, drill and Gerber exports.
  - Why: the richest form allows the most checks, and the tool's own exports prove that an import is faithful.
- No independent review of the circuit is on record for this board. Run the schematic reviews first? (late entry only)
  - Suggested: yes.
  - Why: layout checks cannot find a wrong circuit, and a wrong circuit scraps every board.
- (Production files only) No review of the circuit or the layout is on record, and these files alone cannot be reviewed for either. Order on a manufacturing check only, or give me the design files first?
  - Suggested: the design files if you have them; otherwise order, and every summary says "manufacturing check only".
  - Why: this check finds files that cannot be made, not a wrong circuit.
- I will stop for your approval at `<the gates ahead: the schematic, the PCB, payment>`, and send a notice when a gate is ready, a payment is waiting, the manufacturer asks something or needs a confirmation, the order's main status changes, and the boards ship. Agreed? (late entry only, naming only the gates that lie ahead; otherwise asked in phase 1)
  - Suggested: yes, I run at most two of the expensive independent checks at a time, files in `<folder>`.
  - Why: these stops cover every decision with cost or a permanent effect; the rest runs without you.

## Checks before leaving this phase

- [ ] The state file exists at `hardware/<board>/PROJECT_STATE.md` and its header is filled. Evidence: the file.
- [ ] The tool report is saved and every missing tool is listed with what it disables. Evidence: the report in `out/`, the `tools:` block of the state file.
- [ ] Every install was approved by the user or not done; the answer on live look-ups is recorded. Evidence: the decision rows with date and words.
- [ ] The way of use and the entry phase are recorded with the table row that applied. Evidence: `way_of_use:` and the log of the state file.
- [ ] On resume: every frozen checksum was recomputed. Evidence: the list of files with match or mismatch in the log.
- [ ] On resume: every gate flag has its summary file and approval words, or is set back to open. Evidence: the state file.
- [ ] Brought files are copies made before anything opened them, and the originals are untouched; the source, the import result, the depth with its facts and every skipped gate are recorded. Evidence: the `source:` block and the "Gates skipped by the user" table of the state file, the originals' modification times unchanged.
- [ ] The gates, the notification events, the user's folder and the parallel limit are recorded, or, when the project starts at phase 1, put on the list for the phase 1 question round. Evidence: decision rows with the user's words, or the open questions of the state file.
- [ ] "Next action" is one concrete step that names a file. Evidence: the state file.

## Outputs

- `hardware/<board>/PROJECT_STATE.md`
- The folder tree above, and `board.toml` with the settings known so far
- The tool report of `scripts/env_check.py` in `out/` (Markdown and JSON)
- For brought files: their copies in `kicad/` (with the import record for a design from another tool; production files without a board in `out/jlc/`), and the list of missing earlier documents in the state file

## Lessons behind this phase

- A long project lost its working context several times; it went on only because decisions and state were on disk -> the state file is read or created before anything else, in every session.
- Board files stored through a line-ending conversion no longer matched the checksum the reviewers had seen -> resume recomputes every checksum, and byte-exact storage is proposed for the hardware folder.
- A tool loaded a board while another process was rewriting its project; a dialog opened on the user's screen and stale lock files stayed behind -> existing projects are copied before they are opened, and every load goes through `scripts/kicad_io.py`.
- A schematic was once reported ready on tool checks alone, with one sheet of five read closely -> a gate flag without its summary and the user's words counts as open, also for work adopted mid-way.
- Four costly reviewers were started at once and had to be paused for cost -> the parallel limit is agreed here and kept in the state file.
- Finished files sat in a work folder the user never opens, and the user had to ask where things stood -> the user's folder and the notification events are agreed at the start.
- No simulator had been set up, so a first schematic went out on hand calculations until the user asked about it -> the tool check runs first and says what each missing tool disables; installs wait for a yes.

The full cases are in `references/lessons.md`.
