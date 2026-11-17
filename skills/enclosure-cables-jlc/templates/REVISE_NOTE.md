# Revise note for a production drawing (one per line that is wrong)

`scripts/production_drawing_check.py` writes a ready note per cable in `out/cables/production/`. Use this form to check and shorten it. All notes of an order are shown to the user together and entered in ONE round.

## Rules
1. Only lines whose drawing is wrong get a note. A line that is fully right is confirmed, with the user's permission.
2. Start with both numbers: "Line <n> (<our id>)".
3. Short numbered points. Each is "X, NOT Y": what we want first, what the drawing shows second.
4. Within the note's length limit (capability sheet `[limits] revise_chars`; as read 2026-11: 500 characters; re-read).
5. One picture per note (`revise_pictures`): the pin map, a wiring sketch or the plug view, with the same numbers. From `out/cables/pictures/` where one exists.
6. Everything wrong on that line in this one note. Nothing that is already right. No question, no thanks paragraph.
7. No product or board names. Part numbers and supplier codes as on their own drawing.
8. A tolerance tighter than their standard: only where the cable cannot work otherwise, with the reason in five words.

## The note
```
Line <n> (<our id>):
1. P1 position 2: EMPTY, NOT black wire. Black wire goes to P1 position 3.
2. Wire gauge: 26 AWG, NOT 20 AWG (terminal <code> takes 24 to 30).
3. Cable: <the exact cable in words>, NOT <what they drew>.
4. Length <L> mm +-<t>, NOT +-<their t>.
See the picture: pin map of P1 and P2.
```
(The four points are 1-line examples of the usual faults: a wire position, a gauge against the crimp range, a cable type, a tolerance.)

## Before it goes
- [ ] The drawing read is the newest one (its date is after our last note, or it is the first).
- [ ] Every point comes from a failed row of `production_drawing_check.py`; no row that failed is missing.
- [ ] Character count within the limit: <n> of <limit>.
- [ ] The picture shows the same positions and numbers as the note.
- [ ] Both numbers are right against the line map in `ORDER_LOG.md`.
- [ ] The user saw all notes of this round together. Their words, date: <>
- [ ] After entering: the line's status read back from the page (<"modify" or as the page words it>), logged.

## After their new drawing
Run the check again with `--sent <date of this note>`. A line is confirmed only when every field matches.
