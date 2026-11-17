# Phase 16: lessons back

Write down what this project taught: what fitted and what did not, every supplier question with its cause, the real lead times and costs. Then propose to the user, line by line, what is general enough to go into the skill. Nothing is written into the skill without their OK, and nothing private goes in.

## Inputs

- `orders/ORDER_LOG.md` (timeline, questions, totals, delivery), `orders/ORDER_PLAN.md`.
- `PRINT_FINDINGS.md`, `arrival/FIT_REPORT.md`, `arrival/NEXT_REV.md`, `DECISIONS.md`, the review reports, the waivers in the state file.
- The capability sheets as corrected during the project; the printer profile.
- `references/lessons.md` (to see what is already there), `scripts/privacy_scan.py`.

## Steps

1. **Fill "Lessons for the next order" in the order log.** For every supplier question: what they asked, the form field, file word or remark line that caused it, what it cost in supplier days, and what to do next time. For every surprise in a total: the amount and its cause as far as known.
2. **Write the real times.** Per order: request, quote, review, payment, each question round, production start, shipping, door. Next to each, the time the plan had assumed. These numbers are what the next order plan should use.
3. **Write the real costs.** Parts, shipping, duties and taxes, fees: estimate against actual, per order and per finished unit.
4. **Write what fitted and what did not.** From the print findings and the fit report: each clearance, hole size, cable length and bend that is now proven, and each that failed, with its number. This is the most valuable page for the next revision.
5. **Collect the evidence the PROVISIONAL lines wait for:** the coating build-up measured in holes and cut-outs; the real colours and inks against the chart; cable lengths against the order and the slack on each route; how the revision round went and which note forms worked; ground continuity and the minutes of hand-work; temperatures against the estimate; whether the incoming check lists found what they were meant to find; which manual pages changed.
6. **Write the project's own lessons file** `mech/LESSONS.md`: the items of steps 1 to 5 in the project's words, with its names and numbers. It stays in the project.
7. **Sort what is general.** A lesson is general when it would happen again on another device: a rule margin, a form behaviour, a checklist line, a capability value, a measured allowance. A lesson about this device's own parts stays in the project.
8. **Write the dated proposal** `mech/SKILL_PROPOSAL_<date>.md`: one line per proposed change, each with the target file of the skill (`references/lessons.md`, a design-rules file, a supplier file, a capability seed, a template, a phase file), the exact text, and the evidence. Write each as "what happened, told without names" plus "the check that prevents it". Supplier facts carry their date and "re-read the live page".
9. **Strip everything private.** No personal names, no supplier staff names, no addresses, phone numbers or e-mail addresses, no order or quote numbers, no account data, no product, board or project names, no paths of the user's PC. Prices only as rough orders of magnitude marked as one past order. Run `python -I <skill folder>/scripts/privacy_scan.py <project>/mech/SKILL_PROPOSAL_<date>.md --deny <deny list with the project's names>` and read the file once more by eye.
10. **Ask the user's OK on each line.** Show the lines in groups of at most three decisions per message. Accepted lines are written into the skill only by the user's word (or by the user); rejected lines stay in the project file with the reason.
11. **Update the user's profile** with their OK: the printer's measured numbers, the clearances that fitted, the soft-material path that worked.
12. **Close the project state:** every order delivered or its open step named; the next revision's entry phase from `NEXT_REV.md`; the proposal's status.

## Where a proposed line goes

| Kind of lesson | Target in the skill | Form |
|---|---|---|
| A real mistake and the check that prevents it | `references/lessons.md` | what happened, without names; the phase and step that now catch it |
| A rule margin that passed or failed a real review | `references/design-rules/<file>.md` | the value, the thickness or process, "passed one review on <month>" |
| A form field, a status, a time between steps | `references/suppliers/<file>.md` | the fact, "as read <month>; re-read the live page" |
| A chart name, a limit, a stock default | the seed capability sheet in `templates/` | the key and value, dated |
| A tick box that was missing | a template (`ORDERING_CHECKLIST.md`, `INCOMING_CHECK.md`, ...) | the box with its "seen" and "proof" slot |
| A measured number that answers a PROVISIONAL line | the phase file that carries the line | the number, how it was measured, on how many parts |
| A step that was missing or wrong | the phase file | the step text and the failure behind it |

## Questions for the user

- May I add this line to the skill? (the line, its target file, the evidence)
  - Suggested: `<yes | keep in the project only>`.
  - Why: `<it would happen again on any device | it is about this device only>`.
- May I update your printer profile with the measured values of this project?
  - Suggested: yes.
  - Why: the next project starts from your printer's real numbers.

## Done when

- [ ] Every supplier question has its cause and its "next time" line. Evidence: the lessons table of `ORDER_LOG.md`.
- [ ] Real times and costs stand next to the planned ones. Evidence: the two tables.
- [ ] "What fitted and what did not" is written with numbers. Evidence: `mech/LESSONS.md`.
- [ ] The proposal names a target file, the text and the evidence for every line, and the privacy scan of it is clean. Evidence: the file, the scan rows.
- [ ] The user answered each line. Evidence: their words per line, dated.
- [ ] Nothing was written into the skill without that OK. Evidence: the skill folder's file dates against the OK dates.

## Outputs

- `mech/LESSONS.md` (project, private)
- `mech/SKILL_PROPOSAL_<date>.md` (generic, scanned) with the user's answer per line
- The updated user profile; `PROJECT_STATE.md` closed or pointing to the next revision

## If something is missing

- The project stopped before the arrival: write the lessons of the phases that ran; the PROVISIONAL lines stay as they are, and the proposal says which evidence is still missing.
- The user has no time for the proposal: leave it in the project, dated; ask again at the start of the next project.

## Lessons behind this phase

- Lessons written weeks later missed the cause of half the supplier questions -> steps 1 to 3 are filled from the order log while it is fresh.
- A lessons file carried order numbers and staff names and could not be shared -> step 9: strip and scan before anything is proposed.
- Supplier facts were written as timeless rules and were stale at the next order -> step 8: every fact with its date.
- A rule was added to a shared file without being asked for -> step 10: the user's OK on each line.
- What fitted and what did not was known only to the person at the bench -> step 4: written with numbers.

The full cases are in `references/lessons.md`.
