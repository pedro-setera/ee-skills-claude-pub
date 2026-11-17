# <board name>: layout rules ledger

Every layout rule that a datasheet, a maker's layout guide or the project sets, one row each. Written in phase 4 from the datasheets, filled in phase 9 and 10, checked by the layout reviewers.

Result values: PASS, FAIL, UNKNOWN, WAIVED. UNKNOWN is never PASS. A check that cannot run is FAIL.
Evidence is a file, a measured value or an image crop. "Looks fine" is not evidence.
A waiver needs the user's words (see PROJECT_STATE, Waivers).

How to find rules: for each chip ask the datasheet and the maker's layout guide these questions: which capacitor closes the hot loop for this topology (a buck's input, a boost's output; `references/pcb-rules/power.md` section 2) and where must it sit, what must stay short, what must stay away, what is the thermal pad plan, which pins are sensitive, which copper area is needed, which keep-outs apply.

| ID | Part | Rule | Datasheet page | How it will be checked |
|---|---|---|---|---|
| <LR-01> | <U2 3.3 V regulator> | <input capacitor within 3 mm of VIN pin, ground via beside it> | <p. 18> | <script: distance from pad to pad, plus crop> |
| <LR-02> | <U2> | <thermal pad (GND in the pin table, p. 3): at least 4 vias, 0.3 mm, to the ground plane> | <p. 19> | <script: via count in pad; crop of the pad> |
| <LR-03> | <J1 USB-C> | <no top-layer track under the shell; L2 ground unbroken> | <p. 6> | <image: top copper and L2 plots, zoom crop> |
| <LR-04> | <board> | <ground plane unbroken under the sensor bus> | <project rule> | <script: zone islands; image: plane plot> |

Table above lists the first four columns. The result columns follow in the second table, same IDs, so each table stays within five columns. IDs run `LR-01`, `LR-02` ... over the whole ledger, the rules every board gets included.

| ID | Result | Evidence (file or crop path) | Waiver ref | Checked by and date |
|---|---|---|---|---|
| <LR-01> | <PASS> | <`out/review/crops/u2_cin.png`, measured 2.1 mm> | | <designer, 2026-01-05> |
| <LR-02> | <UNKNOWN> | <not yet routed> | | |
| <LR-03> | <FAIL> | <shell keep-out crossed, `out/review/crops/j1.png`> | | |
| <LR-04> | <WAIVED> | <slot at the connector, crop <path>> | <W-2> | <user, date> |

## Rules every board gets (not from a datasheet)
| ID | Rule | How checked |
|---|---|---|
| <LR-05> | <No via in an SMD pad, except thermal vias inside an exposed thermal pad as the maker's drawing shows (drill and pitch from the datasheet); keep the paste windows between them, cover them on the far side where the fabricator offers it, and exempt those footprints from the via-to-pad rule by name> | <DRC rule "via hole to SMD pad" with the named exemptions, plus a Gerber check> |
| <LR-06> | <Every decoupling, converter and ESD-clamp ground pad has its own via at the pad, every high-current ground terminal its own via (GEN-05); other ground pads a via or a short fan-out> | <zone script> |
| <LR-07> | <Silk text at least 1.0 mm high; line: 0.15 mm was the published minimum as read in 2026-11; use 0.16 mm or more for new work and re-read the live minimum; off pads and holes> | <silk script plus image> |
| <LR-08> | <Copper to board edge at least the supplier's minimum plus margin> | <edge check on the exported Gerbers> |
| <LR-09> | <Every net's finished width and drop checked against its current worksheet> | <neck script> |

## Summary
| Result | Count |
|---|---|
| PASS | <n> |
| FAIL | <n> (gate 2 needs 0) |
| UNKNOWN | <n> (each listed with its bench test) |
| WAIVED | <n> (each with the user's words) |

An empty row, or an UNKNOWN on a blocker-level rule, blocks gate 2. Every other UNKNOWN is listed in the gate 2 summary with the bench test that will settle it; the user's approval of the gate accepts that list.
