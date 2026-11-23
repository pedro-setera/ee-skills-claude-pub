# JLCPCB capabilities

What the fabricator can make, as far as two real orders recorded it: use it to write the board's rule file before layout and to fill the PCB part of the order form.

Facts here were read or observed in 2026-11. Re-read the live JLCPCB page before relying on any number, option name or fee.

## Contents
1. Sources and how to use this file
2. Capability table
3. Via covering depends on the layer count
4. Standard stacks, copper weights and impedance control
5. Surface finish: lead-free HASL or ENIG
6. Solder mask and silkscreen
7. Quantities, board size and price steps
8. Order-number mark
9. Other PCB form fields seen
10. Where the sources disagree
11. Not recorded here: read the live capabilities page

## 1. Sources and how to use this file

Source tags used below:
- **[CAP]** JLCPCB's 4-layer standard capabilities, copied into a board's layout check in 2026-11. The exact page name was not recorded.
- **[ORD4]** seen on the order form while ordering a 4-layer board with assembly, 2026-11.
- **[ORD2]** the order-form notes of a 2-layer board ordered as a customer panel, written 2026-11 with the line "check the option names on the day".
- **[FAB]** the 4-layer board's fab notes and ordering checklist, 2026-11.
- **[REV]** independent layout reviews of those two boards, 2026-11.

How to use it:
- Set the KiCad rule file from section 2 with margin above every minimum. The boards on record used 0.15 / 0.15 mm track and space where 0.09 / 0.09 mm was allowed, and kept copper 0.25 to 0.30 mm from the edge where 0.2 mm was allowed. Margin costs nothing on a sample board and removes a class of engineering questions.
- Before the order, the supplier-rules reviewer re-reads the live capabilities page and measures the exported Gerbers and drill file against it. A value in this file is never the final check.
- Measure on the exported files, not on design settings. On the 2-layer board, KiCad's DRC reported the copper 0.3 mm clear of the edge, while the saved zone fill and the Gerbers had copper touching the outline: the fill had been saved before the rule existed, and DRC refills a copy [REV, 2026-11].

## 2. Capability table

| Item | Value as recorded | Source |
|---|---|---|
| Track width / spacing, 4 layers | >= 0.09 / 0.09 mm | [CAP] |
| Track width / spacing, 2 layers | not recorded | read the live page |
| Inner plane clearance, 4 layers | >= 0.2 mm | [CAP] |
| Via drill / via pad diameter, multilayer | >= 0.15 / 0.25 mm | [CAP] |
| Via drill / pad at no extra cost | 0.3 / 0.6 mm | [CAP] |
| Annular ring | not stated as its own figure; the via minimum implies 0.05 mm | derived; read the live page |
| Minimum hole-wall plating | not recorded; read the live page; until then UNKNOWN in the worksheet, with a stated conservative assumption | - |
| Hole to hole | >= 0.5 mm | [CAP] |
| Copper to board edge | >= 0.2 mm; 0.3 mm recommended | [CAP] |
| Plated hole (PTH) drill | >= 0.3 mm | [CAP] |
| Plated slot width | >= 0.5 mm | [CAP] |
| Non-plated hole (NPTH) | >= 0.5 mm | [CAP] |
| Solder-mask web between pads | >= 0.1 mm | [CAP] |
| Silkscreen text height | >= 1.0 mm | [CAP] |
| Silkscreen line width (and text stroke) | 0.15 mm was the minimum recorded in 2026-11; use 0.16 mm or more for new work and re-read the live minimum | [CAP] |
| Outline tolerance | +/-0.2 mm, "regular" | [ORD2] |
| Board thickness tolerance | +/-10 % | [REV], 2-layer board |
| Lowest PCB price step | board <= 100 x 100 mm | [CAP] |
| Finishes offered (as recorded) | lead-free HASL, ENIG | [CAP] |
| Material on the 4-layer stack | FR-4, TG155 | [FAB] |

Notes on the table:
- The thickness tolerance matters for edge-mount connectors whose legs straddle the board: check the leg gap against 1.6 mm +/-10 % and test-fit before soldering [REV].
- Library footprints often carry 0.12 mm silk lines. Widen them to 0.16 mm or more in the build, or they fall below the minimum [REV].

## 3. Via covering depends on the layer count

- **4 layers [ORD4]:** "tented" was not offered on the form. "Plugged" was offered at no extra cost and was chosen. "Untented" was also offered; a click by screen coordinates selected it by mistake, and clicking the option by its element fixed it.
- **2 layers [ORD2]:** "tented" was planned and chosen.
- **Via in pad [FAB]:** epoxy-filled and capped via-in-pad (POFV) was recorded as free from 6 layers up and a paid option on 4 layers. Both boards avoided via-in-pad: a thermal bar took its vias at its end, and a DRC rule kept every via hole an annular ring away from any SMD pad. The one exception is thermal vias inside an exposed thermal pad as the maker's drawing shows (`../pcb-rules/dfm-dft.md` DFM-40).
- **Why it matters:** an open via beside a pad can wick solder away from the joint. The 4-layer board asked for "solder mask as per Gerber, no extra expansion" so that vias laid tangent to their pads stayed covered (section 6).
- Write the via-covering choice in the ordering checklist as "as the order form offers it for this layer count on the day (tented or plugged); never untented by accident", and read the offered options at the order.

## 4. Standard stacks, copper weights and impedance control

The 4-layer board used JLCPCB's published stack **JLC04161H-7628**, 1.6 mm [FAB, 2026-11]:

| Layer | Material | Thickness | Dielectric constant |
|---|---|---|---|
| L1 outer copper | 1 oz finished | 0.035 mm | - |
| Prepreg 7628 | glass and resin | 0.2104 mm | 4.4 |
| L2 inner copper | 0.5 oz | 0.0152 mm | - |
| Core | incl. inner copper | 1.065 mm | 4.6 |
| L3 inner copper | 0.5 oz | 0.0152 mm | - |
| Prepreg 7628 | glass and resin | 0.2104 mm | 4.4 |
| L4 outer copper | 1 oz finished | 0.035 mm | - |

- The order form asks for the layer order. Keep it in the board's fab-notes file and set it on the form from there: L1 = F_Cu, L2 = In1_Cu, L3 = In2_Cu, L4 = B_Cu [FAB].
- Inner copper on the standard 4-layer stack is 0.5 oz: use it in every current and voltage-drop calculation for inner pours [CAP].
- The 2-layer board was 1.6 mm, 1 oz [ORD2].
- **When 4 layers:** A board with a switching converter gets 4 layers, because a ground plane next to the parts is the better-performing choice (PWR-05). 2 layers are accepted only when all three hold: the converter's own maker shows a 2-layer layout with its measured results (an evaluation board on 2 layers); that layout is copied (hot loop, ground, keep-outs); and no receiver, antenna or sensitive analog input shares the board. In every other case 4 layers. A board with a radio or a sensitive analog input also gets 4 layers by default (the exits are in `../phases/08-board-definition.md` step 9). A simple board with none of these may be 2 layers. Show the user the price difference in either case. With 4 layers both inner layers are ground (layer plan in `../pcb-rules/general.md` GEN-03): L2 and L3 sit about 1.07 mm apart on this stack, so a supply plane there adds almost no decoupling. On the record the extra cost was estimated as small (estimate, 2026-11), and the converter maker recommended 4 layers.
- **Impedance control:** a 4-layer board without controlled lines needed none [FAB]. A 2-layer board had a short 50 ohm line computed from the stack, with no impedance control ordered; two calculation methods differed by several ohms (`../pcb-rules/rf.md` RF-01). Order controlled impedance only when a line needs a guaranteed value; otherwise compute it from the published stack and state the uncertainty. The option's price, tolerance and lead time: not recorded. Rules for when it applies are in `../pcb-rules/general.md` and `../pcb-rules/rf.md`.

## 5. Surface finish: lead-free HASL or ENIG

- **ENIG** was chosen for the 4-layer board because it carried several leadless fine-pitch parts at 0.45 to 0.5 mm pitch (QFN and DFN) [FAB, 2026-11].
- **Lead-free HASL** was chosen for the 2-layer board: the cheapest standard finish, with no such parts on it [ORD2, 2026-11].
- Rule: the default finish is lead-free HASL (RoHS); ENIG where fine pitch or flatness needs it (the 4-layer board's leadless fine-pitch parts); leaded HASL only if the user states that the product has no RoHS need. The price difference between them: not recorded.

## 6. Solder mask and silkscreen

- **Mask "as per Gerber, no extra expansion" [FAB]:** the 4-layer board's Gerbers had mask openings equal to the pads (pad-to-mask clearance 0), and the order told JLCPCB not to grow them, so the tented vias beside pads stayed covered and the 0.12 mm mask webs between 0.5 mm-pitch pads survived. Openings equal to the pads let the mask's registration error (about +/-0.05 mm) cover pad edges: draw the openings with the needed clearance (typically 0.05 mm per side, or solder-mask-defined where the maker says), then order no extra expansion (`../pcb-rules/dfm-dft.md` DFM-51). The exact form field for this: not recorded; it went into the order notes.
- **Mask web:** >= 0.1 mm [CAP], for the green mask and 1 oz outer copper of that board. The page gives a larger minimum for some colours (black and white) and for heavier copper: read the value for the chosen colour and copper before the pads of a fine-pitch part are fixed (`../pcb-rules/dfm-dft.md` DFM-50). Where a maker recommends non-solder-mask-defined pads on a part, keep that and check the web still meets the minimum.
- **Colours:** both boards were green mask with white silk [FAB, ORD2]. Which colours are offered, and whether a colour other than green changes lead time, price or assembly options: not recorded. Ask the user at board definition whether a non-green mask is wanted, with the suggestion "green" and the reason "green is the standard colour and the one proven on real orders; another colour can change price, lead time or assembly options: read the live page before suggesting it".
- **Silkscreen:** every text >= 1.0 mm high; 0.15 mm was the minimum stroke and line recorded in 2026-11; use 0.16 mm or more for new work and re-read the live minimum [CAP]. Silk-to-pad and silk-to-via distances are in `../pcb-rules/silkscreen.md`.

## 7. Quantities, board size and price steps

- **Minimum PCB quantity: 5** [ORD2, "JLC's minimum"]. For a customer panel the count is panels, not the boards on them.
- **Assembled quantity can be smaller than the PCB quantity:** 2 of 5 boards (4-layer) and 2 of 5 panels (2-layer) were assembled; the rest arrived bare. Details in `assembly.md`.
- **Size step:** a board over 100 mm on one side leaves the lowest price step [CAP]. If the outline is still free, a board within 100 x 100 mm is cheaper.
- **Outline shape:** a plain rectangle with no slots was chosen for cost. The fabricator's own pricing of slots and odd shapes: not recorded.

## 8. Order-number mark

The form has a field for the order-number mark ("Mark on PCB" in the 2-layer notes). Options recorded:
- **"Specify position"** [FAB, ORD4]: draw the text "JLCJLCJLCJLC" on a silkscreen layer where the number may go. The 4-layer board put it on the bottom silkscreen inside its information block.
- **"Remove Mark"** [ORD2]: chosen for the small 2-layer board, which had no room.
- Any fee for "Remove Mark", and where the number goes if neither is chosen: not recorded.
- Reserve the mark's place in the silkscreen plan at board definition; it is a text like any other and must not touch pads or vias.

## 9. Other PCB form fields seen

From the 2-layer notes [ORD2, 2026-11]; names may have changed:
- Base material FR-4; layers; dimensions (detected from the Gerbers); PCB quantity; "different designs: 1".
- **Delivery format:** "Panel by Customer" for a panel made in KiCad; single board otherwise.
- Thickness 1.6 mm; outer copper 1 oz; mask colour; silk colour.
- Surface finish; via covering; outline tolerance.
- Castellated holes, edge plating, gold fingers: all "No".
- Remark field: see `order-flow.md`, step 13.

## 10. Where the sources disagree

- **Via covering on 4 layers:** the ordering checklist and fab notes, written before the order, said "vias tented". The form offered plugged (free) or untented, not tented [ORD4]. Trust the form: write via covering as the order form offers it for this layer count on the day (tented or plugged); never untented by accident.
- **Edge clearance for assembly:** see `assembly.md` section 7 (2.5 mm from the held edge, and "parts within 3 to 5 mm of an edge need rails", two figures from two places).
- **Tooling-hole size:** two of JLCPCB's own pages gave different sizes (1.152 mm in a FAQ, 2 mm in the article on process edges), and 2 mm holes in a customer panel were not found by its engineer, whose e-mail named no size. Rule: no tooling holes in the files, "Tooling holes: Added by JLCPCB" in the form (`assembly.md` section 5).

## 11. Not recorded here: read the live capabilities page

- Track and space, minimum drill and annular ring for 1, 2 and 6+ layer boards.
- Minimum hole-wall (barrel) plating, needed by the via area check (`../pcb-rules/general.md` GEN-32).
- Minimum and maximum board size; thickness options other than 1.6 mm; copper weights other than 1 oz outer and 0.5 oz inner.
- Finishes other than lead-free HASL and ENIG; ENIG gold thickness; the price of each finish.
- Mask colours offered and their effect on lead time, price and assembly; silk colours.
- Impedance-control option: stacks, tolerance, price.
- Via-in-pad price on 4 layers; tenting rules per layer count after 2026-11.
- Slot, cut-out and castellation rules; hole-size tolerance; maximum panel size.
- Standard lead times and expedited options.
- Stack names for 6 layers and up.
