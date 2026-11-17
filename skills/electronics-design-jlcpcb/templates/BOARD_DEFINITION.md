# <board name>: board definition (phase 8)

Asked once, after gate 1 and before any routing. Ask at most five at a time, in the shape below, in everyday words (`references/working-rules.md` section 1). Every answer shows its price effect at the sample quantity and later, as an estimate; suggest what the circuit needs, and the cheaper choice only where two are equally good for it (`references/working-rules.md` section 11). When the user says "as suggested", write the suggested answers into the frozen table. Nothing is routed until the outline, holes and layer count are frozen.

Replace each default with a value derived from this device. Keep the reason to one line.

## Questions
**Q1. Board size and mounting holes**
Suggested: <rectangle 40 x 30 mm, no slots, 4 holes M3 (3.2 mm) 3.5 mm in from each corner, keep-outs for screw head, stand-off and driver on both sides>
Why: <a rectangle is cheapest and panelises easily; keep-outs stop a part from covering a screw>

**Q2. One side or two sides of parts**
Suggested: <parts on the top side only>
Why: <the assembler's one-side option is cheaper; two sides add a second setup and a second preview>

**Q3. Number of layers**
Suggested: <4 layers for a board with a switching converter, a radio or a sensitive analog input: L1 parts, signals and supply copper; L2 solid ground; L3 ground as well; L4 signals and supplies, with a ground via beside every signal via that changes between L1 and L4. 2 layers for a converter only when its maker shows a 2-layer layout with its measured results (an evaluation board on 2 layers), that layout is copied (hot loop, ground, keep-outs) and no receiver, antenna or sensitive analog input shares the board; 2 layers for a simple board with none of these>
Why: <a ground plane next to the parts performs better (PWR-05): every signal has its return one via away, and a ground via to the plane 0.2 mm below has about a tenth of the inductance of a through via on a 2-layer board; a supply plane on L3 would add almost no decoupling; the stack is the supplier's standard one. Price difference: about <amount> for the samples and <amount> per board later (estimate, confirm on the live quote)>

**Q4. Solder mask colour and surface finish**
Suggested: <green mask, lead-free HASL (RoHS); ENIG if there is fine-pitch QFN or BGA; leaded HASL only if you state that the product has no RoHS need>
Why: <green is the standard colour and the one proven on real orders; another colour can change price, lead time or assembly options: read the live page before suggesting it; ENIG gives flat pads for fine pitch>

**Q5. Which parts the assembler places**
Suggested: <every SMD part; through-hole parts only if the assembler's through-hole service is offered; connectors that need hand fitting stay off the BOM and placement file>
Why: <hand-fit parts left in the files get placed wrongly or flagged; leaving them out keeps the order clean>

**Q6. Silkscreen identification**
Suggested: <company name, device model, revision, date code, connector and pin names, polarity marks, LED meaning; text at least 1.0 mm high; line: 0.15 mm was the published minimum as read in 2026-11; use 0.16 mm or more for new work and re-read the live minimum; see SILK_ID_BLOCK.md>
Why: <a bare board with no mark is hard to bring up and impossible to support>

**Q7. Panel, rails, fiducials**
Suggested: <supplier's own panel rule, 5 mm rails on the two long sides only, fiducials as the supplier requires; no tooling holes in the files: the order form says "Tooling holes: Added by JLCPCB">
Why: <the supplier's rules decide; deviations cost time>

**Q8. Places of connectors, lights, buttons and switches, and cable directions**
Suggested: <each connector on the edge that faces what it connects to, cables leaving outward by the shortest way; lights, buttons and switches on the side the user sees and reaches; plug and wall section view in the drawing>
Why: <short cables that cross nothing; a plug that hits a wall or a screw is only found in a 3D view of the real plug>

**Q9. Enclosure, if any, and how the board is held**
Suggested: <give the enclosure drawing or STEP; otherwise treat the outline as free. A board that slides into slots or rails keeps a free band along each guided edge, both sides: the slot depth plus about 1 mm>
Why: <an enclosure drawn later forces a new outline>

## Frozen answers
| Q | Question | Answer | Date | The user's words |
|---|---|---|---|---|
| <Q1> | <Size and holes> | <40 x 30 mm, 4 x M3> | <date> | "<quote>" |
| <Q3> | <Layers> | <2> | <date> | "<quote>" |

Outline file (the mechanical input; its keys: `scripts/layout/README.md`, section "The mechanical input"): `mech/outline.json`, sha256 <value>. Interface file (generated from the board): `mech/interface.json`, board and 3D sha256 <values>; board STEP in `out/3d/`.

## Stack, thickness, assembly side and panel
Frozen with the answers above. The production files and the order form take these values from here.
| Item | Value | From |
|---|---|---|
| Layer count and stack | <2 layers, the supplier's standard stack, read on <date>> | <Q3> |
| Board thickness | <1.6 mm> | <supplier standard, confirmed with Q3> |
| Assembly side | <top only> | <Q2> |
| Panel | <yes: 2 x 2 copies, 5 mm rails on the long sides; no tooling holes in the files, order form "Tooling holes: Added by JLCPCB"> | <Q7> |
| Test access | <hand probes only, no fixture | spring-pin fixture: all its points on the bottom side, 2.54 mm apart, locating holes H1 and H3, the programming lines among them> | <the phase 1 answer, the quantity> |
| Held by slots or rails | <no | long edges in the case's 2 mm slots: 3 mm free bands on both sides; width 40.0 -0.2 mm against the case's 40.5 mm; section drawing at path; ground touches the case: no> | <Q9, case drawing> |

## Area budget (input to the outline)
| Item | Area (mm2) |
|---|---|
| Sum of courtyards | <420> |
| Fill target | <60 percent of the board> |
| Routing channels and keep-outs | <200> |
| Board area needed | <>= 1000 vs 1200 available> |

## Freeze
Frozen on <date> after the user's answers. Changing any frozen row after routing starts needs the user's word and a new layout.
