# Phase 2: layout study and first cable list

Arrange block models of every part in two or three ways, compare them in one table with pictures, list every cable, and let the user pick. Nothing is modelled in detail before the picture is approved.

## Inputs

- `REQUIREMENTS.md` (confirmed), the capability sheets, `interface.json` if a board exists.
- `scripts/layout_study.py`, `scripts/heat_air.py`, `scripts/interface_read.py`; `templates/layout.example.toml`, `templates/heat.example.toml`.
- `templates/LAYOUT_STUDY.md`, `templates/CABLE_LIST.md`, `templates/GATE0_SUMMARY.md`.
- `references/design-rules/heat-and-air.md`, `shielding-and-ground.md`, `cables.md`; `references/interface-electronics.md`.

## Steps

1. **Collect the block sizes.** Every part is a box with its real outer size from its maker's drawing, its heat in watts, its tags (`noisy`, `sensitive`) and its connectors with the face they sit on. Panel-mounted parts get `panel = true`. Write them once in `<project>/mech/layout/layout.toml` (copy `templates/layout.example.toml`).
2. **Draw two or three arrangements** as `[variant.A]`, `[variant.B]`, `[variant.C]` (three at most; the script refuses a fourth). Vary what matters: which face carries which connector, where the fan and the vents are, which parts are neighbours.
3. **Run the study:**
   `python -I <skill folder>/scripts/layout_study.py <project>/mech/layout/layout.toml --project <project>/mech`
   It writes a top and a side picture per variant and `comparison.md` / `comparison.png` into `out/layout/`: volume, footprint, cable lengths, intake to swept area ratio, clashes, the fan's free zone, the distance between noisy and sensitive parts, the reach of each panel part. Cable routes here are right-angle estimates; a blocked cable is reported, not re-routed.
4. **Size the box from the minima before any picture is approved.** When the path includes metal, read
   `design-rules/sheet-metal.md` SM-03, SM-04, SM-11, SM-15, SM-16 now: hole and cut-out distances from a bend (to the
   tangent line), nut centres from bends and edges, flange heights. They set the gap between a board and the walls,
   the stand height under an edge connector's cut-out and the inner size; a layout approved without them is undone in
   phase 8, after the print. Over every vertical header with a plug, leave room for the cable: plug height + 3 mm
   straight + the bend radius + half the cable diameter + 1 mm below the lid. Model each screwdriver column and each
   keep-out as an extra block so the clash rows see it. Write these minima in `LAYOUT_STUDY.md`, and keep the same
   gaps and stand heights in the printed concept so the metal version changes nothing. (`layout_study.py` works in
   the box's INNER frame, origin at the inner front-left-bottom corner; the model uses the outer corner.)
5. **Check the reach of every panel part by its numbers:** wall thickness + washer + nut + the thread left for the plug must fit inside the part's thread length (`box_toolkit.thread_budget` repeats this on the model in phase 3). A panel jack once looked fine in the picture and had too little thread left once wall, washer and nut were counted.
6. **Get a first heat number per variant.** Copy `templates/heat.example.toml` to `layout/heat.toml`, set `layout` and `variant`, and run
   `python -I <skill folder>/scripts/heat_air.py <project>/mech/layout/heat.toml --project <project>/mech`
   It suggests a fan size and the intake area, and flags a sensitive part in a fan's stream. It is an estimate, good within 30 to 50 %.
7. **Open every picture and write what you see** in `LAYOUT_STUDY.md`: the air path from intake to exhaust, what stands in front of the fan, where each cable runs and whether it can run under the boards, which connector a hand must reach. A jet of fan air on a sensitive part is easily missed and costly to find later; "no jet on a sensitive part" is a row, and it is also looked at.
8. **Write the first cable list** (`templates/CABLE_LIST.md`): every cable, from where to where, connector family, number of wires, current, rough length from the study. Go through power, signals, radio and antenna feed one by one so that none is forgotten: a forgotten cable later forced a whole quote to be entered again. Prefer one keyed, latching connector family. No consumer cables as internal wiring.
9. **Recommend one arrangement** with its reason, and write down the rejected ones with theirs. Let the box grow rather than complicate the board: a plain rectangular board costs less than one with cut-outs.
10. **Hand the mechanical input to the board** when the board is still to be designed. Write `layout/outline_desc.toml` (outline, holes with their screw, free bands along rail edges, keep-out areas) and run
   `python -I <skill folder>/scripts/interface_read.py --write-outline <project>/mech/layout/outline_desc.toml --out <project>/mech/outline.json`
   The keep-out of each hole is the largest of screw head, stand and tool, plus a margin. Also hand over the height zones and the edge and exit direction of each connector (`references/interface-electronics.md`).
11. **Gate 0.** Send `GATE0_SUMMARY.md`: the recommended picture first, then the table, the cable list and the open questions. The user approves the picture in writing. An opinion asked is not a go: answer, recommend, wait.

## Questions for the user

- Which arrangement? (pictures A, B, C and the table)
  - Suggested: `<the one you recommend>`.
  - Why: `<its strongest row: shortest cables, clear air path, smallest box>`.
- Cable ends: a connector, or soldered to the board?
  - Suggested: keyed latching connectors of one family at both ends.
  - Why: no reversed plug and no soldering at assembly; a reversed power lead once burnt out inside a closed box.
- Which face is the front, and what must be reachable with the lid closed?
  - Suggested: `<your reading of the requirements>`.
  - Why: it fixes the panel layout before any detail is drawn.
- One larger fan or several small ones? (only when the heat table needs a fan; with a picture)
  - Suggested: one larger, slower fan.
  - Why: quieter at the same air flow.

## Gate 0 checklist

- [ ] Two or three variants were run; every row of the comparison ends pass, fail or could not run. Evidence: `out/layout/comparison.md`, `out/checks/layout_study.json`.
- [ ] Every picture was opened and described. Evidence: the "seen" lines of `LAYOUT_STUDY.md`.
- [ ] Every panel part has its reach numbers. Evidence: the reach rows and the sums in `LAYOUT_STUDY.md`.
- [ ] The cable list covers power, signals, radio and antenna feed, each ticked. Evidence: `CABLE_LIST.md` v1.
- [ ] A first heat number exists and is called an estimate. Evidence: `out/heat/heat_table.md`.
- [ ] `outline.json` was handed over, or "the board exists" is written. Evidence: the file and its date.
- [ ] The user approved one arrangement. Evidence: their words and the date in the state file.

## Outputs

- `mech/layout/layout.toml`, `heat.toml`; the pictures and the comparison in `out/layout/`
- `mech/LAYOUT_STUDY.md`, `mech/CABLE_LIST.md` (v1), `mech/GATE0_SUMMARY.md`
- `mech/outline.json` for the electronics skill
- `PROJECT_STATE.md`: gate 0

## If something is missing

- A part has no drawing: ask the user for its size with a sketch of what to measure. Until then its block is marked UNKNOWN and no variant can pass.
- Cables only: skip steps 1 to 6 and 8; write the cable list and go to phase 5.

## Lessons behind this phase

- A full model was built before the arrangement was agreed, and was redone after the user saw the first picture -> this phase: pictures of two or three block arrangements first.
- A panel jack had too little thread left once wall, washer and nut were counted -> step 4.
- A sensitive part sat in a fan's jet -> step 6: "no jet on a sensitive part" is a row and is looked at.
- A cable was forgotten until after the quote -> step 7: the list is walked by power, signals, radio and antenna feed.
- Two connector families on one board, and a consumer cable as internal power wiring, were both rejected by the user -> step 7.
- The user asked for an opinion and the design was changed -> step 10: an opinion asked is not a go.

The full cases are in `references/lessons.md`.
