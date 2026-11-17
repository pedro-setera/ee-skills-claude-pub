# <board name>: review summary

<One line first: the verdict and the one action needed from the user.>
Example: "Not ready to order: 1 blocker and 3 major findings. Decide on the change list below."

## What was reviewed

| Item | Value |
|---|---|
| Inputs | <KiCad project / imported project / schematic PDF + BOM / Gerbers + BOM + placement file> |
| Source and date | <path given by the user>, copied <date> |
| Checksum of the reviewed copy | <sha256> |
| Depth | <lean: LC, LB, V1, SR> or <lean plus <the extra reviews>, switched on by <the facts>> or <the full set: S1, S2, S3 ...> |
| Reviewers | <most capable model, highest effort, set explicitly> |

## What was NOT reviewed, and why

- <Example: the board layout: only the schematic PDF was provided.>
- <Example: gate 1 has no evidence; the user chose to skip it on <date>: "<their words>".>

A reading from a PDF is not a verified schematic.

## Verdict

| Review | Verdict | Blocker | Major | Minor and notes |
|---|---|---|---|---|
| <S1 datasheet> | <NOT READY> | <1> | <2> | <4 + 3> |

## The findings that matter most

<Three to six items, most severe first. A picture for each one that can be shown.>

1. **<ID> <title>.** <What is wrong, one line.> <What happens on the real board, one line.> Picture: `reviews/crops/<prefix>/<file>.png`. Fix: <one line>.

All findings: `reviews/<prefix>_<NAME>_FINDINGS.md`.

## Proposed changes

The full list is `ECO_LIST.md`. In short:

| Change | Answers | Effect on cost or stock | Suggested |
|---|---|---|---|
| <E-01: own BOM line for the tuning resistor> | <S3-MJ2> | <none> | <apply> |

Nothing has been changed. Changes are made on a copy and only after your go.

## What only the bench can settle

- <Example: converter stability at full load: no vendor model; bench test BT-07 in the first power-up plan.>

## Files

- Findings and crops: `reviews/`
- Change list: `ECO_LIST.md`
- State: `PROJECT_STATE.md`
