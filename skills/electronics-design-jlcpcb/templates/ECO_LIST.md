# <board name>: change list

Changes proposed for an existing design. Nothing here is applied until the user gives a go that names the changes. Changes are made on the project's copy, never on the user's original files.

Reviewed copy: `<path>`, checksum `<sha256>`. Original: `<path given by the user>`.

## Changes

| ID | Change | Answers finding | Applied by | Status |
|---|---|---|---|---|
| <E-01> | <R12 10 k -> 1 k; own BOM line, LCSC C..... basic, in stock on <date>> | <S2-MJ1> | <agent, by script> | <proposed / approved <date> / applied / verified / declined> |
| <E-02> | <Add a TVS diode at J3 pin 2, footprint SOD-323> | <S2-B1> | <user, in their tool> | <proposed> |

## Detail per change

### <E-01> <title>
- What changes: <parts, values, nets, footprints, copper, silkscreen text>
- Why: <finding ID and one line>
- Effect: <BOM lines, cost, stock, extended-part count, board area, re-routing needed>
- Suggested: <apply / apply in the next revision / decline>, because <one line>
- Who applies it: <agent on the copy, by script> or <user in their own tool> and why
- How it is verified: <netlist difference shows only this change; image before and after; simulation SIM-04 re-run; closure by the S2 reviewer>

## The user's decision

| Date | Changes approved | Changes declined | The user's words |
|---|---|---|---|
| <date> | <E-01, E-03> | <E-02> | "<quote>" |

## Proof after applying

- Netlist difference: `out/netlist_compare.md`: <exactly the approved changes, nothing else>
- Images: `out/review/` before and after: <crop names>
- Checks re-run: <ERC, intent check, DRC with parity, check suite>: `out/CHECKS.md`
- Closure by the finders: `reviews/VERIFY_<round>_<prefix>.md`

## Hand-back

- Changed copy: `<path>`, checksum `<sha256>`
- How to bring the changes into the original: <replace these files / apply these edits by hand>
