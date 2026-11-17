# PCB rules: EMC (noise, interference and what suffers from them)

Purpose: the cross-cutting rules that keep a board from disturbing itself and its surroundings; read for every board, at the architecture, at the schematic and at the layout.

Contents
1. How to use this file. 2. Sources, victims and paths: the table. 3. Measures in the schematic.
4. Zones on the board. 5. Separation in the layout. 6. Antennas and their matching network.
7. Audio and other sensitive parts. 8. Cables and enclosure. 9. Compliance: what this skill can and cannot claim. 10. Shield cans.
Then: What to verify, and how. Typical mistakes.

## 1. How to use this file

- Interference is designed out, not filtered out afterwards. The cheap moment is the block diagram; the expensive one is after the samples arrive.
- This file gives the method and the rules that span circuit types. The detail per circuit type is in `power.md`, `mcu-digital.md`, `usb.md`, `rf.md`, `analog.md`, `protection-esd.md` and `general.md`; rules there are cited by ID.
- Three moments: phase 2 writes the table of section 2; phase 5 proves section 3 on the schematic; phases 8 to 10 prove sections 4 to 8 on the board. The system review and the electrical layout review check them.
- Numbers marked "starting point" are where to begin, not pass limits.
- Quality first, then cost (`references/working-rules.md` section 11): a measure the table of section 2 calls for is not dropped to save money. Reach it the cheapest sound way: first what is free and adds quality (zones, placement, short loops, slower edges); a part where the table shows a real risk for this product; and where the need is uncertain, a filter, snubber or shield position left unfitted, so it can be fitted when a measurement asks for it.

## 2. Sources, victims and paths: the table

- EMC-01 MUST list every noise source on the board (a board with no converter, no clock line, no radio and no sensitive input says so in one row, and that row answers EMC-02 to EMC-04): switching converters (their edges, switch node and inductor), clocks and crystals, fast digital buses and display links, motor, relay and solenoid drivers, switching (class-D) audio amplifiers, LED drivers with pulse-width dimming, and every radio transmitter. Why: a source nobody wrote down gets no measure.
- EMC-02 MUST list every sensitive part: antennas and receivers, ADC inputs and references, high-impedance sensor nodes, microphones and audio inputs, crystal oscillators, reset and enable pins, long thin signal lines. Why: the victim decides how much noise is too much.
- EMC-03 MUST write, for every source and victim that can meet, the path and the measure: shared supply or ground impedance (conducted), a fast voltage edge beside a high-impedance node (capacitive), a fast current loop beside another loop (inductive), a cable or slot that radiates or receives. Keep the table in the design note. Why: the measure differs per path; a ferrite does nothing against a magnetic loop.
- EMC-04 MUST list the frequencies that matter: each converter's switching frequency and its harmonics, each clock and its harmonics, against every receive band and every sensitive signal band on the board. Choose converter frequencies and clock rates so that no strong harmonic falls in a receive band, or name the measure. Why: a 400 kHz converter has harmonics all through the AM band, and a 2 MHz converter's run through the short-wave bands into the FM band; a receiver hears what falls in its band.

## 3. Measures in the schematic

- EMC-10 MUST give every wire that leaves the board its filter and protection at the connector, decided line by line: ESD part, series resistor or ferrite, capacitor to ground, a common-mode choke position on external data cables (USB-54). Why: cables are the antennas of the board, in both directions.
- EMC-11 MUST feed every sensitive section (analog, reference, receiver, microphone bias, PLL) through its own filter from the board supply, computed as a filter and never with a ferrite or inductor in its ground return (MCU-04, MCU-07). A low-noise linear regulator after a switching converter is a normal choice for such a rail. Why: shared supply impedance is the commonest path.
- EMC-12 MUST set every fast digital output to the slowest edge that meets its timing, and give long point-to-point clock and bus lines a series resistor position at the driver (MCU-46, MCU-47). Why: emission grows with the edge rate, not the clock rate.
- EMC-13 SHOULD keep provisions that cost only footprints: a snubber position at each switch node, a boot resistor position, a shield-can outline with its ground pads around a radio or a noisy converter, unfitted capacitor positions at cable entries. Why: they allow a fix without a new board.
- EMC-14 SHOULD use a converter's or clock generator's spread-spectrum option when a receive band is at risk, and say so in the design note. Why: it lowers the peak at each harmonic.
- EMC-15 MUST define every input: no floating gate, enable, reset or unused logic-gate input (unused microcontroller pins: `mcu-digital.md` MCU-60); reset and enable lines that travel get a small capacitor at the receiving pin where the maker allows it. Why: a floating or long high-impedance line is a receiver.
- EMC-16 MUST decouple by mounted inductance and check the supply impedance of each demanding rail (PWR-37, PWR-49), and choose band capacitors with their mounting (PWR-38, RF-82). Why: a rail that rings is a source on every pin it feeds.

## 4. Zones on the board

- EMC-20 MUST draw a zone map before placement: power conversion; digital; analog and sensors; radio and antenna; connectors. A board with a single zone says so in one line. Keep it in the design note and place by it. Why: distance and order are the cheapest filters.
- EMC-21 MUST let power enter at one side and flow through protection and conversion to the loads without crossing the analog or radio zone; signals flow along their chain without doubling back through a noisy zone. Why: currents that cross a quiet zone bring their noise with them.
- EMC-22 MUST keep converters, inductors, clocks and fast buses away from the antenna, from sensitive inputs and from connectors they do not serve; where the board is too small for distance, use the other side of a ground plane, a shield provision, or a slower edge, and write which. Why: on a small board the measure must be named, not hoped for.
- EMC-23 SHOULD group connectors on one edge or one side where the mechanics allow it. Why: cables leaving from opposite ends of a board make it the middle of a dipole.

## 5. Separation in the layout

- EMC-30 MUST route every signal over an unbroken reference and inside its edge (GEN-02, GEN-08), and keep aggressors from victims by a spacing judged against the height above the reference (GEN-09). Why: return paths decide coupling.
- EMC-31 MUST NOT run a power track, a switching node, a clock or a fast bus under, over or beside an antenna and its keep-out, a crystal, a microphone or audio input line, a high-impedance sensor node, an ADC input or a reference, on any layer without a solid ground plane between them; where a ground plane lies between, still keep switching power copper out from directly under these parts. Why: the plane helps but does not make a noisy conductor harmless at close range.
- EMC-32 MUST place the vias that carry power or switching current between layers inside the power zone, each with its return via beside it, never in the analog or radio zone and never in a row that cuts a plane (GEN-17). Why: a layer change injects its current into whatever the via passes.
- EMC-33 MUST keep each switching loop small and on one layer as its own rules say (`power.md` section on the hot loop) and keep the switch-node copper as small as its current allows. Why: loop area and node area are the two terms of a converter's emission.
- EMC-34 MUST keep clock lines short, away from board edges and connectors, with no stub, and route a crystal's two lines as its rules say with nothing under it (`mcu-digital.md`). Why: clocks are narrow-band sources that show up as spurs in receivers.
- EMC-35 SHOULD keep low-level analog and audio lines short, away from digital and power lines, crossing them at right angles when they must cross, with a guard ring only where the maker's layout shows one. Why: parallel length is what couples.
- EMC-36 MUST keep fills on signal layers stitched or absent (GEN-18) and every ground area tied to the plane. Why: an unstitched copper finger is a resonator.

## 6. Antennas and their matching network

- EMC-40 MUST follow the antenna maker's or module maker's layout exactly: the keep-out area with no copper on any layer, no parts, no tracks, no screws, battery, shield, cable or other metal inside or close above and below it; the position at the board edge or corner; the size of the ground plane the antenna is specified with. Write the datasheet page in the ledger. Why: an antenna is tuned together with the copper and metal around it.
- EMC-41 MUST give the antenna feed a three-part matching network position at the antenna (RF-52): shunt, series, shunt (a pi network), parts close together, each shunt pad with its own ground via beside it. Fit the maker's values at first; where none are given, fit a zero-ohm series part and leave the shunts unfitted. Why: the enclosure, the battery and a hand detune every antenna, and the network is how it is brought back to 50 ohm.
- EMC-42 MUST plan the tuning: the match is measured and adjusted on the bench with the board in its real enclosure, with the battery and cables in place; until then the antenna's performance is UNKNOWN and is listed as such at the gate. Why: values from a datasheet are for the maker's test board, not for this product.
- EMC-43 SHOULD provide a way to measure: a small coaxial connector position or a pad pattern for a test cable in the feed, selectable by the series part. Why: without it the match cannot be seen.
- EMC-44 MUST route the feed as a controlled 50 ohm line on one layer, as short as possible, with ground vias along it, and no via in the path unless its effect is estimated (`rf.md`). Why: the feed is part of the antenna.
- EMC-45 MUST keep a certified radio module's antenna, feed and ground exactly as its maker's document shows, and tell the user when the design departs from it. Why: the module's radio approval covers that layout only.
- EMC-46 MUST keep noise sources away from the antenna as EMC-22 and EMC-31 say, and check each source's harmonics against the antenna's band (EMC-04). Why: the antenna is the most sensitive receiver input on the board.

## 7. Audio and other sensitive parts

- EMC-50 MUST treat a microphone line as a high-impedance, low-level input: short, away from converters, digital lines and antennas, over solid ground; filter the microphone's bias supply with a resistor and capacitor at the microphone; add a small capacitor (a starting point of 10 to 33 pF) from each microphone line to ground at the amplifier input where a radio transmitter is on the board. Why: a transmitter's bursts are demodulated in the input stage and heard as a buzz.
- EMC-51 MUST treat a digital microphone's clock and data as fast digital lines: series resistor position at the driver, short, away from the antenna. Why: its clock is a continuous source.
- EMC-52 MUST treat the outputs of a switching (class-D) amplifier as switch nodes: the two output tracks short, wide, together as a pair, away from antennas, microphones and analog inputs; a ferrite and capacitor filter position at the amplifier when the speaker leads are longer than the maker's limit; the amplifier's supply decoupled at its pins with a bulk capacitor sized for the peak current. Why: the speaker leads radiate the switching edges.
- EMC-53 MUST give a magnetic buzzer, a relay, a motor or any coil its freewheel diode or clamp at the coil (PWR-59), and drive a piezo sounder through the circuit its maker shows. Why: an unclamped coil produces a voltage spike at every switch-off.
- EMC-54 SHOULD keep a speaker or any permanent magnet away from magnetic sensors, compasses and reed switches, and say the distance in the design note. Why: the static field shifts their reading.
- EMC-55 MUST keep the return current of a speaker amplifier, a motor or an LED string out of the reference of microphones, sensors and ADC inputs by placement: the load's supply and return leave from the power zone, not through the analog zone. Why: milliohms of shared ground become millivolts in a microvolt signal.

## 8. Cables and enclosure

- EMC-60 MUST give every cable its return in the same connector, next to its fast signals (GEN-07), and place the filter parts of EMC-10 at the connector, before the signal travels across the board. Why: a filter far from the entry lets the noise in first.
- EMC-61 MUST decide how each cable shield and each metal connector shell is tied to ground, by the rules of its interface (`usb.md`, `protection-esd.md`), and decide how a metal enclosure is bonded to the board. Why: an undecided shield is an antenna.
- EMC-62 SHOULD keep an unshielded cable that carries switching current (motor, LED string, speaker) as a twisted or closely paired run, and say so in the cable notes. Why: the loop area of the cable radiates.

## 9. Compliance: what this skill can and cannot claim

- EMC-70 MUST record in the requirements whether the product will be sold and in which markets, because radio and emission rules then apply. Why: it decides how much provision is worth its cost.
- EMC-71 MUST state at gate 2: "EMC: designed by these rules; not measured." Emission and immunity can only be shown by measurement. Recommend a pre-compliance measurement before any production run, and tell the user that a product with a radio needs either a certified module used as its maker prescribes or its own certification. Why: an agent cannot certify, and a user who believes otherwise is let down later.

## 10. Shield cans

A shield can is a thin metal cover soldered to ground over one block of the board. With the ground plane below it, it forms a closed metal box that keeps the block's noise in, or outside noise out. It is the measure for a pair of the table (section 2) that distance, filtering and slower edges cannot settle. It is not a default.

- EMC-72 MUST decide for every source and every victim of the table whether it gets a can (a board with no radio and no high-gain stage: no can, one line), at the architecture (phase 2), and write it in the Measure column: fitted, footprint only, or not needed with the reason. Consider one when: a radio receiver's front end (amplifier, filter, mixer: satellite navigation, cellular, sub-gigahertz, 2.4 GHz) shares the board with a switching converter, a processor, a display or fast memory; a radio chip transmits and is not a module that already carries its own can; an oscillator or synthesiser must stay clean; a converter or a fast digital block sits within a few centimetres of an antenna or a receiver and cannot move; a high-gain or very-high-impedance analog stage works in a noisy enclosure; the chip or module maker's reference design has one. Usually not needed: a certified module with its own can; a board in a closed metal enclosure with no victim inside it; a pair that the zones, the filters and the edges already settle. Why: fitted blindly a can is cost, height and trapped heat; left out where it was needed it is a new board.
- EMC-73 SHOULD, when the need is uncertain, lay the can's land pattern and leave the can unfitted on the samples (EMC-13), and decide by measurement at bring-up. Why: the footprint costs nothing; adding it later is a new board.
- EMC-74 MUST build the box from the can and the board together: a solid ground plane on the next layer under the whole shielded area (the floor of the box); a ground land on the surface under the can's walls, as the can maker's drawing shows; and vias from that land to the plane all the way round, no further apart than lambda / 20 at the highest frequency that matters (`rf.md` RF-15: about 3.3 mm at 2.4 GHz; 2 to 3 mm when that frequency is not known; starting point). Why: a can on a land with a few vias is a lid on a box with no floor, and every gap between vias is a slot that leaks.
- EMC-75 MUST take every net through the wall on purpose: on an inner layer under the wall, or through the openings the can maker provides, with the land interrupted there only as wide as needed; no surface track runs under a soldered wall. Supplies and slow signals are filtered where they cross (a capacitor to the shield's ground at the wall; a ferrite or a resistor in series where the table asks for it); an RF line crosses as a controlled line with ground vias on both sides. Why: one unfiltered wire through the wall carries out what the can keeps in.
- EMC-76 MUST size the can from the parts and the frequency: the inner height clears the tallest part (by 0.5 mm; starting point); over an RF line the lid is at least about 5 times the line's height above its plane away, and 1 to 2 mm over RF inductors (estimates), because a close lid detunes them; the largest inner dimension stays below half a wavelength in air at the highest frequency that matters (about 60 mm at 2.5 GHz, 30 mm at 5 GHz), or the box gets an inner wall or absorber; holes and gaps in the can are smaller than lambda / 20. An antenna and its keep-out are never under or beside a can (EMC-40). Why: a box of the wrong size resonates, and a lid too close changes the circuit under it.
- EMC-77 SHOULD use a two-piece can (a soldered frame and a lid that clips on) on samples and wherever parts under it must be reached: the tuning parts of a matching network, anything to inspect, probe or rework. A one-piece can is the cheaper choice once the design is proven. Why: a one-piece can must be unsoldered to change one capacitor.
- EMC-78 MUST treat the can as a part and the space under it as closed: a BOM line with the maker's part number; the land pattern from the can maker's drawing, audited like any footprint; a 3D model with its real height in the body check and the enclosure check; test points of the nets inside placed outside the can; nothing that needs programming or inspection under a one-piece can; the labels of the parts under it on the assembly drawing; the parts under it in the heat table with still air (an estimate), or their heat led into the plane. Find out in phase 3 whether the assembler can place it (in its parts library and in stock); if not, it is a hand-fit part, fitted after the board is tested. Why: a can hides, heats and blocks what is under it, and one that the line cannot place stops the order.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Source and victim table complete, each pair with its path and measure | Read against the block diagram and BOM | The table in the design note |
| Harmonics against receive bands | Calculation per source | The frequency list in the design note |
| A filter and protection at every cable entry | Schematic read, connector by connector | Connector table with its parts |
| Sensitive rails filtered, no part in a ground return | Schematic read; rail table | Rail table; filter calculation |
| Zone map followed | Placement image against the map | Image with the zones marked |
| Nothing noisy under or beside antenna, crystal, microphone, sensor, ADC input | `scripts/review_images.py` tiles of each such part, all layers | Crops named in the review |
| Power and switching vias inside the power zone | Copper plots per layer | Crops |
| Antenna keep-out and ground size as the maker shows | Board against the datasheet drawing; all layers | Crop and datasheet page |
| Matching network position, shunt ground vias, feed line | Board and schematic | Crop; ledger row |
| Antenna tuned in the enclosure | Bench, network analyser | UNKNOWN until measured; bench test number |
| Audio: bias filter, input capacitors, amplifier output pair, coil clamps | Schematic and board read | Crops; ledger rows |
| A shield can decided for every source and victim (fitted, footprint only, not needed) | The Measure column of the table | The table in the design note |
| Shield land, vias all round, ground floor below; every crossing on purpose and filtered; no surface track under a wall | Copper plots and crops around the can, every layer; via pitch measured | Crops with the pitch |
| Can height, size, parts and test points under it | `scripts/body_check.py`; the can maker's drawing | Report, crop |
| Statement "designed by rules, not measured" | Gate 2 summary | The summary |

## Typical mistakes

- A converter placed beside the antenna because the board was small, with no measure named: the receiver lost sensitivity and only the bench showed it.
- A capacitor chosen "for the radio band" by its value: with its mounting it resonated far below the band and did nothing.
- A ferrite put in a chip's ground pin "to keep noise out": it raised the chip's ground bounce.
- A matching network left out to save three parts: the antenna could not be tuned in the enclosure and the range was a fraction of the expected one.
- Copper poured under a chip antenna by the fill, on an inner layer nobody looked at.
- A microphone line routed past a radio module: a buzz at every transmission.
- A relay coil without its diode: the microcontroller reset at every switch-off.
- A filter placed near the chip instead of at the connector: the cable's noise crossed half the board first.
- Common in the field: a shield can on a land with one via at each corner, or with supply tracks entering unfiltered: it changed nothing.
