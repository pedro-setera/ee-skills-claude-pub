# PCB rules: design for manufacture and test

Purpose: rules that let a prototype assembler build the board first time and let you test it: assembly side, edges and rails, fiducials, panels, vias, mask and paste, rings and edges, footprints and rotations, router clean-up, test points, bring-up provisions and the assembly drawing.

Contents
1. Assembly side and who places what
2. Component-to-edge distance and rails
3. Fiducials and tooling holes
4. Panels and mouse bites
5. Vias: in pads, tenting and plugging
6. Solder mask and paste
7. Annular ring, drills and copper to edge
8. Footprints, courtyards, rotations and orientations
9. Router artefacts
10. Test points
11. Bring-up provisions
12. Assembly drawing and hand-fit parts
13. What to verify, and how; typical mistakes

Fabricator and assembler numbers change: take them from `references/jlcpcb/capabilities.md` and `references/jlcpcb/assembly.md`, and measure the exported files against them (`references/review-briefs/supplier-rules.md`).

## 1. Assembly side and who places what

- DFM-01 MUST place every assembled part on one side by default. Why: one-sided assembly is the cheaper service at JLCPCB; a second side changes the service and the price.
- DFM-02 MUST decide in phase 8 which parts the assembler places and which are fitted by hand. Through-hole parts may move the order to a dearer service: estimate both paths. Why: on a small run the price difference can exceed the cost of the parts.
- DFM-03 MUST keep through-hole leads short where they sit near the enclosure floor, and keep part bodies off the bottom side. Why: long leads touch the enclosure, and bottom bodies break the one-side service.

## 2. Component-to-edge distance and rails

- DFM-10 MUST keep part bodies the assembler's minimum distance from the edges its conveyor holds, or add rails on those edges (`references/jlcpcb/assembly.md`). Why: parts 0.4 mm from the edge of a small board forced a customer panel with rails.
- DFM-115 SHOULD keep parts that crack or drift when the board bends (large ceramic capacitors, crystals, small sensors, ball-grid packages) away from where it bends: mounting screws, break-off bridges, connectors pushed by hand, press-in parts. Turn a ceramic capacitor near such a place so that its long side lies along the bending line, not across it. Only where the part cannot move: a relief slot between the source of the strain and the part (`general.md` GEN-61, GEN-63). Why: a cracked ceramic capacitor is a short that shows weeks later.
- DFM-11 MUST put rails only on edges that may be held, never on an edge with an overhanging part, and state the held edges in two lines of order remark. One proven board used 5 mm rails on its long sides only. Why: a rail on an overhang edge collides with the overhanging part.

## 3. Fiducials and tooling holes

- DFM-20 MUST provide the fiducials the assembler requires, and MUST NOT draw tooling holes into a board or panel for JLCPCB assembly: leave them out and choose "Tooling holes: Added by JLCPCB" in the order form, so that the form and the files agree (`references/jlcpcb/assembly.md` section 5). A customer panel carries 3 fiducials on its rails and nothing else there. A board with an antenna keep-out, an isolation barrier or another area that must stay undrilled is ordered with rails or as a panel, so that JLCPCB's holes go into the rails. Only when the user needs tooling holes in the files: JLCPCB's own size and positions, read on its live pages that day, never a size from one page against another or from memory, and the user is told that this is not proven. Why: without fiducials the machine cannot register the board; 2 mm holes at the rail ends, the size of one of the assembler's own pages, were not found by its engineer, and the question cost an e-mail round after payment.
- DFM-21 SHOULD add local fiducials near fine-pitch parts only when the assembler asks for them. Why: they take board area and add little beside the global ones.

## 4. Panels and mouse bites

- DFM-30 MUST generate a panel from the board with `scripts/panel.py`, refill every copy's zones under the board's rules, run DRC and `scripts/edge_check.py` on the panel, and check that the panel placement file equals the board's moved by each copy's offset. Why: a panel is a new board; its fill, edges and positions must be checked again.
- DFM-31 MUST keep parts at least about 2 mm from a breakaway bridge (starting point) and write "cut, never bend" in the assembly note. On an edge guided by slots or rails (`connectors-mechanical.md` MECH-06) the break-off tabs leave nubs: put the bridges outside the free band (on an edge that is not guided), or have the nubs removed flush and say so in the assembly note. Why: a ferrite 0.4 mm from a bridge would have cracked when the board was snapped out, and a nub in a rail jams the board.
- DFM-32 MUST leave hand-fit parts out of the panel's 3D render and placement file. Why: a panel render showed a hand-fit connector reaching into the next board.
- DFM-33 SHOULD put bridges away from fragile parts, offset on each end. One proven pattern: 5 mm bridges of five 0.6 mm holes, 0.4 mm apart. Why: bridges next to fragile parts crack them when the board is snapped out.

## 5. Vias: in pads, tenting and plugging

- DFM-40 MUST keep vias out of SMD pads. No via in an SMD pad, except thermal vias inside an exposed thermal pad as the maker's drawing shows (drill and pitch from the datasheet); keep the paste windows between them, cover them on the far side where the fabricator offers it, and exempt those footprints from the via-to-pad rule by name. Any other via in or touching a pad is allowed only filled and capped, ordered on purpose (as read in 2026-11, JLCPCB fills and caps via-in-pad free from 6 layers and charges for it on 4). Add the DRC rule "via hole to SMD pad" (the hole keeps its own annular ring from every SMD pad, any net) as an error. Why: an open via in a pad wicks solder (the rule caught three such vias on one board); the maker's thermal vias are the exception because the part's thermal ratings assume them, and the paste between them still makes the joint.
- DFM-41 MUST choose via covering as the order form offers it for this layer count on the day (tented or plugged); never untented by accident. As read in 2026-11 (capabilities file): plugged vias were the free default from 4 layers and tented vias were not offered there; 2-layer boards could be tented. Why: the covering decides whether vias beside pads stay covered.
- DFM-42 SHOULD use the fabricator's no-extra-cost via size (as read in 2026-11: 0.3 mm drill, 0.6 mm pad), and larger vias only where current needs them. Why: smaller vias cost more, and larger ones take routing room.
- DFM-43 MUST, where vias are open (neither tented nor plugged), keep at least the fabricator's minimum mask web between every SMD pad and any via ring, joining pad and via by a short neck (about 0.5 mm; starting point); covered vias may sit at the ring rule of DFM-40. Why: an open via beside a pad wicks or bridges solder.

## 6. Solder mask and paste

- DFM-50 MUST check the mask web between fine-pitch pads against the fabricator's minimum for the chosen mask colour and copper weight and use the pad definition the maker recommends (solder-mask-defined or not). Why: a web below the minimum disappears and fine-pitch pins bridge.
- DFM-51 MUST draw the mask openings with the clearance they need (typically 0.05 mm per side, or solder-mask-defined where the maker says so), then order the mask "as per Gerber, no extra expansion". Why: an added expansion opens the tented vias beside pads and removes thin webs, and openings drawn 1:1 with the pads let the mask's registration error (about +-0.05 mm; estimate) cover pad edges.
- DFM-52 MUST use the maker's paste pattern for exposed pads (windowpane, often 50-80 % coverage) and give hand-fit pads no paste. Why: full paste on an exposed pad floats the part, and paste on hand-fit pads leaves solder blobs.
- DFM-53 SHOULD give both pads of a small passive similar copper (spokes on the pour side) where one pad sits on a large pour. Why: uneven heating tombstones small parts.

## 7. Annular ring, drills and copper to edge

- DFM-60 MUST take ring, drill, plated-slot, hole-to-hole and hole-to-copper minimums from the capabilities file and keep a margin beyond each. Why: a design at the minimum fails on the fabricator's tolerance.
- DFM-61 MUST measure copper to edge on the exported Gerbers with `scripts/edge_check.py`, board and panel, corners and arcs included. Draw zones inside the edge and set the rule before the first fill (`general.md` GEN-56). As read in 2026-11: 0.2 mm minimum, 0.3 mm recommended. Why: the board file can say one thing while the Gerbers say another.
- DFM-114 SHOULD keep the copper roughly even: about the same copper area on the layers that mirror each other in the stack, and no large bare area beside a large solid pour on one layer; where a large area stays empty on a board longer than about 100 mm (starting point), or on any board thinner than 1.6 mm, fill it with ground pour stitched to the plane (`general.md` GEN-18). Why: uneven copper heats, shrinks and plates unevenly, so the board bows or twists in the oven and fine-pitch parts lift.
- DFM-62 SHOULD keep 1.6 mm unless a mechanical fact forces a thinner board; on a thinner board, balance the copper between the sides (as balance, not as a performance fill) and keep a 4-layer stack symmetric. Why: a thin board with a solid plane on one side and sparse copper on the other bows and twists.

## 8. Footprints, courtyards, rotations and orientations

- DFM-70 MUST check every footprint against the maker's land pattern (pitch, pads, drill, pin 1) with `scripts/fp_audit.py`, and against the assembler's own footprint for its part number (pad error 0.1 mm or less; starting point). Why: generic library lands differed from the makers' for an inductor and a small regulator.
- DFM-71 MUST make every courtyard cover its pads and body plus a margin, keep courtyard rules as DRC errors, and draw real courtyards on custom parts. Why: library courtyards that followed the body were smaller than the pads, so overlaps went unseen.
- DFM-72 MUST derive every placement rotation and origin from the assembler's own footprint with `scripts/jlc_rotations.py` (phase 12), matching two-pin polarised parts by their polarity mark, not by pad number. Why: a generic rotation table would have placed every three-pin transistor wrong and an electrolytic reversed.
- DFM-73 SHOULD place polarised parts in a few common orientations. Why: faster optical and visual inspection.
- DFM-105 MUST change a reference designator only in the schematic and update the board from it; a connector's or jumper's function goes on the board as a silkscreen text, never as a changed designator. Why: the BOM and the placement file carry the designators, and parts whose designators were changed on the board alone were left unfitted at assembly.

## 9. Router artefacts

- DFM-80 MUST find and remove after automatic routing: acute angles, slots narrower than the clearance, dog-legs, stubs, loops and dangling vias; set a minimum zone width. 45-degree corners are a convention, not a pass criterion. Why: acid traps, slivers and dangling vias hurt yield and noise, and DRC may pass them.
- DFM-81 MUST run DRC with schematic parity after every routing stage, not only at the end: no unconnected item but the nets not yet routed, 0 at the end. Why: a gap found late costs a re-route.

## 10. Test points

- Test points are ruled in several files: which nets (`mcu-digital.md` MCU-70 to MCU-74), labels (`silkscreen.md` SILK-71), stubs on fast nets (`general.md` GEN-42), a slipping probe (`protection-esd.md` ESD-71), reach in the enclosure (`connectors-mechanical.md` MECH-62). This section adds the list, the sizes, the production fixture and the table. Its sizes are starting points; where a fixture maker is known, its rules decide.
- DFM-90 MUST place test points where a probe reaches them with the board mounted, on the assembled side of a one-sided board (the points of a production fixture follow DFM-98 and may all lie on the other side: the fixture uses them before the board is mounted), with a ground point near each group, labelled as in `silkscreen.md`. Why: a test point under a cable or on the hidden side is never used.
- DFM-91 MUST provide a short-loop ground beside every switch node and ripple measurement point. Why: a long probe ground lead invents overshoot.
- DFM-92 MUST write in every procedure that no power is fed through a test point by a hand probe or a clip. A production fixture may feed power through points made for it: named in the test-point table, the current per spring pin inside the pin's rating, ground on at least as many pins. Why: test points are not rated for current and probes slip.
- DFM-93 SHOULD give every node whose ripple or noise is on the bench list a probe-specific footprint (signal and ground at the spacing of the probe's ground spring) or an unfitted coaxial footprint grounded at the node, with both labelled. Why: a probe fitted to its footprint picks up far less than one with a ground lead.
- DFM-94 MUST decide the test points at the schematic (phase 5), as a list made from what will be measured, not at the layout from the room that is left. One row per measurement of the bring-up plan and the bench list, and at least: every supply rail at its regulator's output, and the input behind its protection; ground, with at least one point a clip can hold; reset, boot straps, enable and power-good lines; the debug and bootloader lines where they have no connector; each bus the firmware will have to debug (I2C, SPI, UART); every net that ends only under leadless parts or a module and has no pad a probe can touch. A net that already has a pad a probe can hold (a connector or header pin, a through-hole pin, the lead of a leaded package, the pad of a 0603 or larger part) uses that pad: name it in the test-point table and add no point. Why: a measurement without a place to probe ends on a fine-pitch pin; a point on every net costs room, adds stubs and is never used.
- DFM-95 MUST draw every test point as a part on the schematic, with a reference (TP1, TP2, ...) and its net; a bare pad is marked as not in the BOM and not in the placement file. Why: a pad added only on the board is lost at the next update from the schematic, and the test-point table is made from the netlist.
- DFM-96 MUST size and space test points for the probe that will touch them (starting points): a round pad free of solder mask and of paste, 1.5 mm across where there is room and never under 1.0 mm; 2.54 mm from centre to centre, which a hand probe and a standard spring pin can both use, and never under 1.27 mm; 1 mm clear of any part body; 3 mm clear of parts taller than about 5 mm, which shade the probe (5 mm for the points of a fixture); and, for the points of a fixture, 3 mm clear of the board edge. A ground point, and any rail that a clip must hold during a measurement, gets a loop or a hook (a BOM line: a surface-mount type is placed by the machine, a through-hole loop is fitted by hand); every other point is a bare pad and costs nothing. A via counts as a test point only when it is drawn as one: uncovered, of this size, labelled. Why: a pad that a probe slips off, or cannot reach between two tall parts, is not a test point.
- DFM-97 MUST keep a test point from changing what it measures. On a fast net the pad lies on the track itself, not on a branch (stub length: `general.md` GEN-42; a USB high-speed pair takes no branch at all, `usb.md` USB-52). No point on a crystal pin, on an RF line or an antenna feed, or on a high-impedance node (a divider of hundreds of kilohms, a feedback or current-limit setting pin, a sensor input): read such a value through the firmware or behind a buffer, or probe a part's pad at the bench and write that into the bring-up plan (`mcu-digital.md` MCU-72). Where a point is needed on a node that only dislikes capacitance, a series resistor of 1 to 10 kilohm (starting point) at the node keeps the pad and the cable off it. On a switch node only the probe footprint of DFM-93. Why: the pad's copper and the probe's capacitance and resistance become part of the circuit: a 10 megohm probe on a megohm divider reads several percent low, and a few picofarads stop a watch crystal.
- DFM-98 MUST settle the test access for the series in the board definition (phase 8), from the quantity and from the user's answer on how later boards are programmed and tested (phase 1). Where a spring-pin fixture is planned or likely (more than a few tens of boards; estimate): every point the fixture needs on ONE side, the side without tall parts where possible; the rails, ground, reset and the programming and serial lines among them, so that one fixture programs and tests; two unplated holes far apart for the fixture's locating pins (the mounting holes may serve; size and tolerance from the fixture maker), with about 5 mm free of parts round each; the points spread over the board, so that the spring pins do not bow it; spacing as DFM-96; and from the first series board on the points do not move. For a concept run or a handful of boards none of this is added: hand-probe points only, and the board definition says "no fixture". Why: a fixture reaches one side cheaply and is built from the positions of the points; points on both sides, or moved between two revisions, mean a new layout or a new fixture.
- DFM-99 MUST keep ONE test-point table and never type it from memory: reference, net, side and position, and what is normal there (value with its tolerance, running and in standby; the instrument where it matters). `scripts/testpoint_check.py` writes it from the board as `out/testpoints.md`. The normal values are typed once, in `[testpoints.normal]` of `board.toml`, each with its source (the set-point table of the design note); the script copies them into the table, and the bring-up plan and the firmware hand-over copy that table. The table on the schematic overview is the list of phase 5. A pad used in place of a point (DFM-94) has its row too. Why: whoever services the board years later has the board and this page.

## 11. Bring-up provisions

- DFM-100 SHOULD add zero-ohm links or jumpers that separate a supply from its loads for every block that must be brought up on its own (a converter, a protection circuit, a costly or risky load, or any block whose fault would hide the others'), so blocks power up one at a time: each link upstream of all that block's decoupling and bulk capacitors, never between a supply pin and its capacitor, on a footprint that also takes a low-value sense resistor (drop at most about 100 mV at the block's load), with a probe point on each side. Why: a fault then shows on one block, not on the whole board, and a sense resistor shows the block's current and inrush.
- DFM-101 SHOULD add a loop-injection resistor in each converter's feedback (`power.md` PWR-15) and unfitted tuning footprints: snubber, boot resistor, extra filter capacitors, RF matching. Why: each is a cheap fix at bring-up instead of a respin.
- DFM-102 MUST give every value that may change its own BOM line (or a DNP line). Why: a resistor that shared a line with others could not be changed alone at the assembler.
- DFM-103 MUST leave unfitted any fallback path that can cut power, until the bench proves it. Why: a fallback that misfires at boot can cut the power every time.
- DFM-104 MUST list the partial-power states the links create, run the back-feed check of `mcu-digital.md` MCU-52 on each, and mark in the bring-up plan which links must close together. Why: a block powered alone can be driven through its inputs by a powered neighbour.

## 12. Assembly drawing and hand-fit parts

- DFM-110 MUST generate the assembly drawing and look at it: every reference inside its own body, polarity visible, the page readable. Why: it is the only map for parts without a silk label.
- DFM-111 MUST exclude hand-fit parts from the assembler's BOM and placement file ("exclude from position files"), give their pads no paste, and list them, with their soldering order, in the assembly document. Why: the assembler would otherwise try to place them, and the person fitting them needs the list.
- DFM-112 SHOULD name the IPC class wanted in the fab notes, and list each drill size once on the drawing, plated or unplated, with finished size and tolerance. Why: a drill file alone does not say which holes are the enclosure's mounting holes.
- DFM-113 MUST connect every hand-soldered through-hole pin to an inner ground plane, or any large pour, through a thermal relief with at least 2 spokes sized for its current (`general.md` GEN-12), not solidly, unless its current needs solid copper and the soldering method is planned for it (preheat, a larger iron) and written in the assembly document. Why: solid connections to the two inner planes of a 4-layer board sink the iron's heat, and the joint stays cold.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Copper to edge on exports | `scripts/edge_check.py` on board and panel Gerbers | Report with per-layer minimum |
| Via in pad, rings, drills, courtyards | `scripts/drc_run.py` with the template rules; the exposed-pad footprints exempted by name, each against its maker's drawing | DRC report, exemption list |
| Mask openings | Opening minus pad per side on the exported mask layer, against the clearance drawn | Measured table |
| Thermal reliefs on hand-fit pins | Inner-layer copper plots at every hand-fit through-hole pin | Crops |
| Footprints and assembler lands | `scripts/fp_audit.py`; overlay with the assembler footprint | Table with pad error |
| Rotations and origins | `scripts/jlc_rotations.py` derive and test; preview tiles at order time | Derivation table, test result |
| Panel | `scripts/panel.py`, panel DRC, panel placement test, panel render | Panel files, reports, render |
| Edge distance and rails | Part-to-edge distances against the assembler's rule | Distance list, order remark text |
| Test points | `scripts/testpoint_check.py`: every point of the schematic's list is on the board, pad size, spacing, distance to tall parts, side, a ground point near each group; renders with the board mounted | `out/testpoint_check.md`, `out/testpoints.md`, renders |
| Bring-up links | BOM lines for tunable parts; link position against the block's capacitors; partial-power table | BOM extract, table |
| Open vias beside pads | Mask web between each SMD pad and an open via ring, on the exported mask layer | Measured minimum, crops |
| Fab notes and drill list | IPC class named; each drill size once, plated or unplated, finished size and tolerance | Fab notes, drawing |
| Assembly drawing | Plot and look, origin corner included | PDF and crops |

## Typical mistakes

- A generic rotation table turned every SOT-23 by the wrong angle: all would have been placed wrong, and an electrolytic reversed. A two-pin diode would have been wrong too, because the assembler's footprint numbered its cathode as pad 2.
- Three vias sat in or touching SMD pads; a new DRC rule found exactly those three.
- Parts sat 0.4 mm from the edges of a small board; it became a panel with rails on two ends.
- A ferrite sat 0.4 mm from a mouse-bite bridge; the bridge moved to leave about 2 mm.
- A resistor on a shared BOM line had to change after the order; the line could not be split.
- Library courtyards smaller than the pads hid overlaps from the courtyard check.
- The assembly drawing piled the references of the unlabelled parts at the board origin.
- Common in the field: test points added at the end of the layout where room was left: the rails had none, and the ones that existed sat under a cable.
- Common in the field: test pads of 0.5 mm in a tight row between tall parts: connected, clean in the rule check, and no probe could hold them.
- Common in the field: test points on both sides of a board that later went onto a one-sided fixture.
- Common in the field: a test point on a crystal pin or on a megohm divider: the board worked until someone measured it.
