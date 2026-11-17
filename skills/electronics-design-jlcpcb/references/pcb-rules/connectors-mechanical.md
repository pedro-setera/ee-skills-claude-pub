# PCB rules: connectors and mechanical fit

Purpose: rules that make the board fit its enclosure, its cables and its tools: outline, holes and keep-outs, connector datums, panel connectors, mating housings, 3D bodies, heights, tool access, hand-soldered parts, overhangs and the shared interface file.

Contents
1. Mechanical first
2. Mounting holes and keep-outs
3. Connector datums and selection
4. Panel connectors and section views
5. Mating housings, cables and mis-plugging
6. 3D bodies, courtyards and model origins
7. Height zones and tool access
8. Hand-soldered parts
9. Board-edge overhangs
10. One generated interface file
11. Questions for each maker's drawing
12. What to verify, and how; typical mistakes

## 1. Mechanical first

- MECH-01 MUST freeze the outline, holes, connector positions and height zones in phase 8, before any routing (`references/phases/08-board-definition.md`). Why: on one board, routing on an unsettled outline was thrown away twice.
- MECH-02 MUST, for a small board in a tight enclosure, get an outline-only proposal checked in the 3D assembly (enclosure, neighbouring boards, cables) before placing circuits. Why: in a tight fit the outline decides, and the circuit follows.
- MECH-03 SHOULD use a plain rectangle with rounded corners; no slots, notches or tongues unless the enclosure forces them. Why: cut shapes cost money and create routing necks.
- MECH-04 MUST check the area budget before freezing: the sum of courtyards after the package-size decision, label room, and routing channels. A fill of 55-60 % or less worked for a one-sided power board (starting point). Why: an outline smaller than its parts' courtyards was frozen once and cost two layouts.
- MECH-05 MUST plan one wide routing channel between functional blocks, and reject an outline with a neck narrower than the planned bus. Why: every long control net once had to pass a narrow neck, and hours of routing were lost.
- MECH-06 MUST find out how the board is held before the outline is frozen: screws on stands, slots or rails of an extruded case, card guides, clips. For a board that slides into slots or rails, take from the case maker's drawing the slot depth, the slot width and the distance between the slots, and reserve a free band along each guided edge, on BOTH sides of the board and over the board's whole length: no part body, no courtyard, no solder joint or through-hole lead, no label that must stay readable, and no exposed copper (a metal rail would short it; keep copper out of the band, or under solder mask and back from the edge). Band width: the slot depth plus a margin (starting point: 1 mm more than the slot depth; with no drawing yet, 3 mm per guided edge, marked as an assumption to confirm). Also check: the board width against the slot distance with the fabricator's outline tolerance; the board thickness with its tolerance against the slot width; the height of the tallest parts on each side against the inside of the case at that slot level; rounded or chamfered leading corners; whether the board's ground must touch the case through the rail or must stay isolated from it. Why: a part in the rail zone stops the board from going in, and the whole board must be laid out again.
- MECH-07 MUST, when the enclosure also holds other boards, a display or cables, agree where the board sits and which way each connector, light and button faces in the 3D assembly (the companion skill `enclosure-cables-jlc`, or the user's own CAD) before the outline is frozen, for every board and not only a tight one. Why: the place of a connector decides the length and the route of its cable, and it cannot move once the board is routed.

## 2. Mounting holes and keep-outs

- MECH-10 MUST size each hole from its screw (for example 2.7 mm for M2.5; starting point) and decide plated or unplated with the chassis plan (`protection-esd.md` ESD-61). Why: a tight hole binds the screw; a loose one lets the board shift against its connectors.
- MECH-11 MUST give every hole a keep-out on both sides, large enough for the screw head, washer, stand and screwdriver: no part body, mating housing or cable exit inside it, from below the board to the tool's height. One proven board used a 9 mm cylinder for M2.5 from 3 mm below to 12 mm above the board; take the real values from the stand and the tool. Why: a connector over a screw head was found only on a render.
- MECH-12 MUST keep copper of every layer out of an unplated hole's keep-out, with a keep-out polygon that circumscribes the circle, and no track or via of any net inside. Why: KiCad stores circles as polygons; an inscribed one cuts into the keep-out.
- MECH-13 MUST keep courtyards at least 0.3 mm outside every hole keep-out (starting point), and hole-to-hole and hole-to-copper at the fabricator's minimums (`references/jlcpcb/capabilities.md`). Why: a courtyard touching a keep-out means a body next to the screw.

## 3. Connector datums and selection

- MECH-20 MUST place every connector from its maker's drawing: pin 1, locating pegs, PCB edge line and mating face; check pitch, pad and drill with `scripts/fp_audit.py`. Why: a library header used a 2.54 mm pitch for a 2.50 mm part, and its long version would not have inserted.
- MECH-21 MUST derive the board edge at each edge connector from the maker's PCB edge line, not from the body outline. Why: the shell legs and the mating face are positioned from that line.
- MECH-22 MUST confirm gender, pitch, pin numbering and keying from the mating part's documentation or a photo before choosing the part; prove undocumented pin-outs with a meter on the real part. Why: a housing was once chosen for a mating header of the same gender.
- MECH-23 MUST check each contact's current at the worst current the protection lets through against its rating at temperature; use two contacts per rail when one is marginal. Why: a contact carrying fault current past its rating heats and fails.
- MECH-24 SHOULD use one latching connector family on the board; justify each exception by what sits on the other end of the cable. Why: one family means one crimp tool and fewer harness mistakes.
- MECH-25 MUST give a board-to-board connector or ribbon cable a return pin next to each clock and each small group of fast signals, not one shared ground at the end, and keep fast circuits away from connectors they do not serve (`general.md` GEN-07). Why: a shared return pin couples every fast edge into its neighbours.
- MECH-26 MUST choose each connector's edge and position from where its cable goes: on the edge that faces its target, by the shortest route, with no cable crossing another cable, a mated plug or a fastener, and the wire entry of every terminal free of the part in front of it. Lights, buttons, switches and a display sit on the side the user sees and reaches. On a board with no enclosure the places are proposed to the user in the outline picture and frozen with their answer; a place that departs from this rule has its reason written. Why: a connector on the wrong edge costs a longer cable that crosses the board for the life of the product; one board had two wire entries half blocked by the connectors in front of them.

## 4. Panel connectors and section views

- MECH-30 MUST draw a section view through every panel connector with the real mating plug (overmold, latch, nut) through the real wall, and state wall thickness, pocket, mating depth and clearance. Why: a receptacle too far inside the board could not take its plug through a thick wall.
- MECH-31 MUST model flanges and shells that pass the routed edge, and agree a land or recess with the enclosure design. Why: a flange below the board top hits the wall unless edge and wall are agreed.
- MECH-32 MUST align LEDs and light pipes with their wall holes and check them visible from outside. Why: an indicator hidden behind the wall is useless.
- MECH-33 MUST write a thread budget for every threaded panel connector (`rf.md` RF-23). Why: a short thread leaves the plug half engaged.

## 5. Mating housings, cables and mis-plugging

- MECH-40 MUST treat the mated housing (body plus plug), the latch release and the cable exit with its bend radius as keep-outs, at least 1 mm from hole keep-outs and other bodies (starting point), checked in 3D. Why: the plug and its cable need more room than the header.
- MECH-41 MUST NOT use an unkeyed plug where any mis-mate (rotated, offset by a row or a pin) is destructive. Use keyed, full-width housings and mark pin 1 at both ends. Why: a reversed or offset plug can put the supply on a signal pin.
- MECH-42 MUST give a connector with symmetric pins an orientation mark that matches its housing's asymmetric feature, and an assembly step. Why: a symmetric header fits both ways; only the mark tells which is right.
- MECH-43 MUST put a continuity check of every harness, before its first plug-in, into the bring-up plan. Why: a crimp on the wrong pin is a dead short at the first plug-in.
- MECH-44 SHOULD measure cable lengths along the real 3D route with real bend radii, and have a second person or agent measure without seeing the first numbers. Why: lengths taken in a straight line come out too short around bends.

## 6. 3D bodies, courtyards and model origins

- MECH-50 MUST make every courtyard enclose its pads and its whole 3D body, bent or overhanging parts included, plus a margin. Why: courtyard checks only see what the courtyard covers.
- MECH-51 MUST check every imported 3D model's origin and rotation against its footprint. Library models often put their origin at pin 1, not the body centre. Why: an offset model puts the body where no courtyard check looks.
- MECH-52 MUST run `scripts/body_check.py`: every body inside its courtyard; no body in any hole's keep-out cylinder; mated housings and cable exits clear. If its 3D library is missing, it reports FAIL "cannot run" and the visual review carries the check. Why: courtyard checks alone missed a connector over a screw.
- MECH-53 MUST look at renders of every hole and connector, zoomed, and write what was seen. Why: a script once reported a part clear while the render showed a connector over a screw.

## 7. Height zones and tool access

- MECH-60 MUST define height zones from the enclosure (lid, display, other boards, cables passing above) and keep every part, plug included, within its zone; export the tallest part per zone. Why: the lid and the boards above set the heights, not the parts library.
- MECH-61 MUST check tool access for every fastener: a straight screwdriver path with no cable or part across it, and the assembly order that makes it possible. Why: a cable once crossed a screwdriver path.
- MECH-62 MUST check that test points and debug connectors are reachable with the board mounted. Why: bring-up and service happen in the enclosure.

## 8. Hand-soldered parts

- MECH-70 MUST give hand-soldered parts room for the iron: their courtyard is the iron's clearance (one proven board: 1.8 mm behind the pads and 1.0 mm outside the legs of a connector), with no SMD part inside, and longer pads where the maker allows. Why: an iron that touches a neighbour damages it.
- MECH-71 MUST write the soldering order when one hand-fit part blocks another. Why: the wrong order makes a joint impossible to reach.
- MECH-72 MUST give hand-fit parts no paste and keep them out of the assembler's BOM and placement file (`dfm-dft.md`). Why: otherwise the assembler pastes or places them.
- MECH-73 MUST connect each hand-soldered through-hole pin to an inner ground plane, or any large pour, through a thermal relief (`dfm-dft.md` DFM-113). Why: solid connections to the two inner planes of a 4-layer board sink the iron's heat, and the joint stays cold.

## 9. Board-edge overhangs

- MECH-80 MUST declare parts that pass the board edge to the fabricator and assembler, keep rails off that edge, and check the panel render (`dfm-dft.md`). Why: the conveyor and the panel both need that edge free.
- MECH-81 MUST check edge-mount connectors against the board thickness tolerance (`rf.md` RF-22). Why: the leg gap fits only a range of board thicknesses.

## 10. One generated interface file

- MECH-90 MUST generate one interface file from the board with `scripts/interface_export.py`: outline, holes, connector positions and mating faces, LEDs, tallest part per zone, with the board and STEP checksums. The enclosure design reads only this file. Why: numbers typed by hand into an enclosure model drifted from the board.
- MECH-91 MUST re-run the export after every board change, and the enclosure fit check with the project's own CAD (this skill provides none; without one, the fit item is FAIL "cannot run" and goes to the mechanical review with the section views), and fail the enclosure build when the checksums differ. Why: an enclosure built for an older board fits nothing.
- MECH-92 MUST store board and STEP files byte-exact (no line-ending conversion), so the checksums stay valid up to the order. Why: a line-ending conversion once changed the files and broke the recorded checksums.

## 11. Questions for each maker's drawing

Write each answer, with its page, into `LAYOUT_RULES_LEDGER.md`:
- Where are the datums: pin 1, pegs, PCB edge line, mating face?
- What are the pitch, pads, drills and plating, and which board thickness range fits?
- What is the mated height, the latch-release space, the cable exit direction and the bend radius?
- What current per contact at our temperature, how many mating cycles, which keying?
- What panel cut-out and thread length, and what maximum panel thickness?
- Where does the 3D model come from, and where is its origin?

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Footprints against drawings | `scripts/fp_audit.py` table compared with each drawing | Audit table, drawing page refs |
| Return pins in board-to-board pin-outs | Pin table: each clock and fast group beside a return pin | Pin table |
| Bodies, holes, mated housings | `scripts/body_check.py` | Report with nearest distances |
| Board held by slots or rails | A cross-section drawing of the case profile with the board and its tallest parts, to scale; `scripts/body_check.py` with the edge bands | The drawing, the check result |
| Model origins | Body-in-courtyard check plus renders per connector | Report, renders |
| Holes and keep-outs on all layers | Copper plots per layer, zoom per hole (`scripts/review_images.py`) | Hole crops |
| Panel connectors | Section view with the real plug and wall | Section image with dimensions |
| Enclosure fit | `scripts/interface_export.py` and the project's own CAD fit check, or FAIL "cannot run" carried to the mechanical review with the section views | Interface file, fit report or the FAIL line, checksums |
| Hand-soldered pins on planes | Copper plots of the inner layers at every hand-fit through-hole pin: thermal relief, spokes | Crops |
| Tool and probe access | Renders in the enclosure with tool paths | Renders with crop names |

## Typical mistakes

- The first outline was smaller than the sum of the courtyards; the next shape was too congested. Two layouts were thrown away before a larger rectangle on 4 layers.
- A library 3D model had its origin at pin 1, so a connector body sat millimetres toward a mounting screw in 3D while pads and courtyards were right. The courtyard checks passed; the user found it on a render.
- After that fix, the connector's mated housing was only 0.75 mm from the hole keep-out; it moved 0.6 mm.
- A bent LED's lens lay outside its courtyard.
- A housing was picked without checking that the mating header was also female; the next proposal could be plugged in turned round, putting the supply on ground. It became soldered wires with a meter check first.
- A two-pin header could be fitted turned round; a silk notch matching the housing's slotted wall and an assembly step fixed it.
- A cable crossed a screwdriver path; found in the fit check.
- Parts sat within the rail zone of a slide-in extruded case: the first sample jammed, and the board was designed again.
