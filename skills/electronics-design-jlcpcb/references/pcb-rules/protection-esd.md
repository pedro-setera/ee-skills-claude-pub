# PCB rules: protection and ESD

Purpose: rules for TVS and ESD parts, reverse-polarity and over-voltage protection, fuses and PTCs, back-feed, chassis bonding and spacing, so that every wire that leaves the board is protected.

Contents
1. Placement priority
2. Every wire that leaves the board
3. TVS and ESD parts at the connector
4. Clamp voltage against downstream ratings
5. Reverse polarity and over-voltage
6. Fuses and PTCs
7. Back-feed
8. Chassis bonding options
9. Spacing and probing
10. Questions for each datasheet
11. What to verify, and how; typical mistakes

The protection table and the energy map are made in phase 2 (`references/phases/02-architecture.md`); this file turns them into copper. USB-specific points are in `usb.md`, crowbars in `power.md`.

## 1. Placement priority

Signal lines: the ESD diodes or the clamp at the pins first, before any other part (ESD-10).

Power inputs, in this order from the pins inward:
1. A small ESD clamp at the pins, if wanted. It is allowed ahead of the fuse only when no reversed or sustained over-voltage can make it conduct (bidirectional, standoff above both).
2. The fuse or PTC, where reverse connection or sustained over-voltage is credible.
3. The reverse-polarity element, wherever reverse connection is credible (a barrel jack, screw terminals, bare wires, a battery holder, a cell on a plug (`power.md` PWR-64), any connector that can be mated or wired reversed); only an input that physically cannot be reversed (a keyed polarised connector whose mate this project wires, USB-C) needs none.
4. The power TVS.
5. The eFuse or load switch, then the filter and the bulk capacitance.
6. The protected circuit.

Where neither reverse connection nor sustained over-voltage is credible, the power TVS may sit at the pins like a signal clamp.

Why: transient current must be clamped where it enters. But a source that is reversed or stays too high drives a TVS at the pins forward or holds it in breakdown, with nothing upstream to open: it fails, usually short, and a battery then feeds a hard short. With the fuse first, the fuse opens instead.

## 2. Every wire that leaves the board

- ESD-01 MUST list every wire that leaves the board (power, data, buttons, switches, sensors, LEDs on cables, antenna feeds, shields) in the protection table: the threat (ESD, surge, reverse connection, over-voltage, short to a neighbour wire), the protecting part, and what it protects. Why: a switch wire with no clamp could turn a device on by itself.
- ESD-02 MUST compute the charge-sharing step on every unclamped input: V = V_esd * 150 pF / (150 pF + C_node), using the IEC 61000-4-2 source capacitance of 150 pF. Compare it with trigger thresholds and gate ratings; add node capacitance or a clamp. Why: one 8 kV contact discharge would have put about 17 V on FET gates.
- ESD-03 MUST include the nanosecond inductive part for any sensitive IC behind a filter or choke: an 8 kV contact discharge has a first peak of about 30 A with a sub-nanosecond rise, so every nanohenry of trace or via adds tens of volts. Simulate it with the via and trace inductance (`references/simulation.md`). Why: the slow charge-sharing figure alone once hid about 10 V on a 6 V part for 2.4 ns.
- ESD-04 SHOULD treat button, switch and sensor wires as ESD and noise entries: a clamp or RC at the connector wherever the charge-sharing step (ESD-02) or the input's own rating (ESD-23) shows the input needs one (then it is a MUST by those rules), a glitch filter at the input, a defined default level. Why: a switch wire is a long antenna into a high-impedance input.

## 3. TVS and ESD parts at the connector

- ESD-10 MUST place the ESD parts of signal lines at the connector pins, before any other part, with the line passing through the part's pad (flow-through) and no stub. On a power input follow the order of section 1: only a small ESD clamp may sit ahead of the fuse; the power TVS sits behind the fuse and the reverse-polarity element, as close to them as the parts allow, still flow-through. Why: a clamp placed after a stub lets the edge in first, and a power TVS ahead of the fuse is destroyed by the first reversed or sustained fault.
- ESD-11 MUST connect the clamp's ground pin to the plane by a short, wide path with its own via (or vias) at the pad. Why: the return inductance adds to the clamp voltage.
- ESD-12 MUST keep the discharge path (pin, clamp, ground via, plane, chassis or cable return) short and out of quiet grounds and sensitive areas. Why: currents of tens of amperes in nanoseconds bounce every ground they cross.
- ESD-13 MUST NOT place a clamp where the discharge has to cross the board to reach it. Why: the discharge couples into everything on its way.

## 4. Clamp voltage against downstream ratings

- ESD-20 MUST choose the standoff voltage at or above the highest continuous voltage, tolerance included (for example vSafe5V maximum 5.5 V; a 20 V USB PD contract 21 V), never from transients: the hot-plug ring, surge and ESD are what the clamp handles (ESD-21). For an input that must ride through a sustained over-voltage by disconnecting (ESD-31), the clamp ahead of the disconnect stands off the sustained fault voltage and clamps below the disconnect's absolute maximum; a low-standoff clamp belongs behind the disconnect. Why: a clamp that conducts in normal use overheats or corrupts the signal, and a standoff raised to cover the ring clamps far above the downstream ratings.
- ESD-21 MUST compare the clamp voltage at the current of each transient (from the clamp curve or TLP data, not the "kV" headline) with the downstream pin's rating for that kind of stress, negative limits included:

  | Stress | Compared with | Where the pin has no such figure |
  |---|---|---|
  | DC and sustained (normal levels; a fault that lasts, such as a short to a neighbour wire or CC to VBUS) | The pin's absolute maximum | - |
  | Surge and hot-plug ring (microseconds) | The pin's transient or surge rating where the datasheet gives one | Its absolute maximum |
  | ESD (nanoseconds) | The pin's pulse (TLP) failure level, or the protection part and layout its maker qualifies for that pin, with the layout's inductance (ESD-03) | Not shown either way: write the uncertainty, take the maker's guidance, and let the system test decide; never assume an allowance above the DC maximum |
  | System level | IEC 61000-4-2 on the finished product, at the required level and performance criterion | A bench-list item |

  Why: a standoff just above the rail does not keep a part rated near that rail safe during the clamp; and a DC absolute maximum is a DC figure, while a TLP pulse lasts about 100 ns (TI, ESD Essentials: How to Select ESD Protection), so a nanosecond residual above the DC maximum neither proves damage nor, without pulse data, safety.
- ESD-22 MUST check pulse power and energy for surge and for the hot-plug ring, and leakage at the highest working voltage. Why: pulse energy, not the ESD rating, decides whether a power TVS survives.
- ESD-23 MUST decide explicitly whether an external part is needed, and write the decision and its reason. The chip's own HBM and CDM figures are handling ratings of the bare chip (the human-body test discharges 100 pF through 1.5 kilohm: about 5 A at 8 kV), not system ratings: they never justify leaving a pin that leaves the board on a cable, or that the user can touch on the finished product, without protection (a service header or a test point inside the case is handled with ESD care and follows `mcu-digital.md` MCU-33) (the system test of ESD-03 discharges 150 pF through 330 ohm: about 30 A at 8 kV). Only a pin that its datasheet rates to IEC 61000-4-2 at the level the product needs, in the circuit the datasheet shows, may go without; otherwise ESD-02 and ESD-03 against the pin's ratings as ESD-21 sorts them decide. Why: "no clamp needed" must be a calculation, not a hope, and "8 kV HBM" read as "survives 8 kV" is the usual way a clamp gets removed.
- ESD-24 MUST, when substituting a clamp for stock reasons, compare the clamp and derating tables and the footprint before accepting the substitute. Why: pin-compatible clamps differ in clamp voltage and derating.

## 5. Reverse polarity and over-voltage

- ESD-30 MUST, wherever reverse connection is credible (section 1), fit reverse-polarity protection and choose the method by drop and cost (series Schottky, P-channel MOSFET, ideal-diode controller) and place it after the fuse, before the power TVS and the bulk capacitance (section 1). A P-channel MOSFET goes drain to the input, source to the load, so its body diode conducts in normal polarity; gate to ground through a resistor, with a gate-source zener when the input can exceed the gate-source maximum. Verify that orientation in the schematic and on the footprint's pin numbers. The MOSFET does not block back-feed once it is on (ESD-50). A unidirectional TVS ahead of the reverse element is against section 1: a reversed input drives it forward. Why: placed after the bulk capacitors, the protection would leave them exposed to the reversed input, and a MOSFET fitted backwards passes the reversed input through its body diode.
- ESD-31 MUST place over-voltage disconnects (eFuse over-voltage lockout, switch) close to the inlet, and a clamp or crowbar at the protected rail when stored energy below the disconnect can damage the load on its own (`power.md` PWR-48). Why: a disconnect far from the inlet lets the over-voltage reach more of the board.
- ESD-32 MUST write each protection's response chain (sense, delay, switch-off) and trip tolerance, and check the order in which protections fire for sags, dips and surges. Why: a filter added on one enable pin changed which protection fired first, and the device latched off instead of restarting.

## 6. Fuses and PTCs

- ESD-40 MUST put a fuse or PTC upstream of a power TVS where a sustained over-voltage or reverse connection is credible (section 1), rated to open on the current the TVS draws in that fault before the TVS exceeds its pulse rating (the fuse's time-current curve against the TVS's pulse curve), and able to break that current (ESD-44). A PTC serves here only where ESD-45 holds: the current it passes once tripped keeps the TVS within its steady power rating. Why: a TVS is built for pulses, not for sustained over-voltage.
- ESD-41 MUST rate every fuse and PTC: hold current at the maximum local temperature at or above the maximum load; trip current and time within the contact, wire and copper ratings (copper by the adiabatic pulse check of `general.md` GEN-28; copper is never the protection); voltage rating, DC or AC as the circuit is, at or above the maximum; resistance counted in the drop budget; then ESD-44 for a fuse and ESD-45 for a PTC. Why: protection that trips above the wire's rating protects nothing.
- ESD-44 MUST check that every fuse can break the largest fault current at its place. Write the prospective short-circuit current there: the source's voltage over the sum of the source's internal resistance (a cell at the lowest internal resistance its datasheet gives; a supply's current limit only where it is dependable) and the path's resistance (wiring, contacts, copper), each value with its source. The fuse's breaking (interrupting) capacity at the circuit's voltage, DC for DC (an AC rating says nothing about DC), stays at or above it; its clearing time and let-through I^2t stay within what the wiring, the copper (GEN-28) and the protected parts withstand. A fuse whose breaking capacity is below the prospective current FAILS even when hold current, trip current and voltage pass. Why: a fuse asked to break more than its rating can keep arcing or rupture instead of clearing; batteries and stiff supplies are where that happens.
- ESD-45 MUST check a PTC beyond hold and trip: its maximum voltage and maximum fault current against the worst fault at its place (ESD-44's prospective current); its rating and trip time at the local temperature; the current it still passes once tripped (from its tripped-state power or leakage in the datasheet), and what that current does downstream: a TVS held in conduction, a failed load shorted, a cell still discharging, each kept within its steady rating; its reset behaviour and fault endurance (number of trips) as the datasheet gives them. A tripped PTC is not an isolating disconnect: where the downstream circuit must be dead, use a fuse or a switch. Why: a PTC only limits current, so a residual current can keep a clamp or a fault hot, and a fault above its maximum current or voltage can destroy it.
- ESD-42 MUST place PTCs away from heat sources, hot copper included (a track or pour with a worksheet rise above about 10 C), and give them the copper their datasheet's ratings assume (`power.md` PWR-43). Why: heat lowers the hold current and causes nuisance trips.
- ESD-43 MUST cover per branch: hard short; partial short, swept for each branch from R = V / I_limit,max to R = V / I_rated (the fault currents between the limiter's highest limit and the rated load); and short between neighbour wires of a harness. Why: partial shorts heat contacts without tripping anything, and one fixed resistance is a hard short on one branch and the rated load on another.

## 7. Back-feed

- ESD-50 MUST find, for every load switch, regulator and connector, the current path when an outside source drives the board's output or a signal pin, and decide explicitly: blocking diode, ideal diode, series resistor, or a written warning. Why: a DC source on an output connector once lifted an off processor's rail and kept a whole device on.

## 8. Chassis bonding options

- ESD-60 MUST decide where chassis meets circuit ground. For a metal enclosure, or where one may come later (phase 2, step 13), put connector shells and the plated mounting holes near the connectors on a chassis net, bonded to ground at one point beside the main connector, with unfitted footprints for a resistor (for example 1 Mohm) and a high-voltage capacitor (for example 1-10 nF) in parallel. Make the bond low-inductance: two or more parallel 0603 or larger 0 ohm parts, fitted by default, on wide copper, each with several vias, beside the shell tabs. With the bond unfitted, the high-voltage capacitor is the ESD path: size and rate it for that. Why: the options cost nothing on the first board and avoid a respin when the enclosure changes, and a single 0 ohm part with its via sets the inductance of the discharge path.
- ESD-61 MUST decide plated or unplated for each mounting hole: plated on chassis or ground where an ESD path to a metal enclosure is wanted; unplated, with no copper in its keep-out, everywhere else (`connectors-mechanical.md`). Why: a plated hole on ground ties the circuit to whatever the screw touches.
- ESD-62 MUST NOT tie circuit ground to an undefined metal part of an enclosure. Why: the bond would then depend on assembly, paint and screws.

## 9. Spacing and probing

- ESD-70 MUST use the larger of the fabricator's minimum clearance and IPC-2221B Table 6-1 (0.13 mm between uncoated pads and terminations) only where neighbouring conductors differ by 15 V or less between exposed copper (pads, terminations, copper without mask), or by 30 V or less elsewhere; above that, ESD-73. Keep more space between input or surge zones and quiet nets where room allows (0.5 mm is a starting point, not a safety value). Do not import mains spacing tables; mains voltage is outside version 1's range (ESD-74). Why: the fabricator's minimum is a manufacturing limit, not a voltage rating, and mains tables answer other hazards and waste area on low-voltage boards.
- ESD-71 MUST place test points on input rails so a slipping probe cannot bridge them to a fine-pitch or low-voltage pin. Why: one slip can put the input voltage on a low-voltage pin.
- ESD-72 MUST analyse mis-plugging of every connector and harness (`connectors-mechanical.md`). Why: an offset or reversed plug is a fault no clamp absorbs.
- ESD-73 MUST, above 15 V between exposed copper, or above 30 V anywhere (a 20 V USB PD input, 24 V and 48 V rails, surge or flyback peaks, clamp nodes), take the spacing from IPC-2221B Table 6-1 for the conductor's location and coating and set it as a net-class clearance. Commonly cited values; check the table: uncoated pads and terminations 0.13 mm up to 15 V, 0.25 mm at 16-30 V, 0.4 mm at 31-50 V; uncoated bare conductors 0.6 mm above 30 V; conductors under solder mask 0.13 mm up to 100 V. Why: a 20 V or 24 V rail at the fabricator's 0.1 mm on exposed pads fails the table.
- ESD-75 MUST, where two parts of the board are isolated from each other (an isolated interface or supply: a digital isolator, an optocoupler, an isolated converter, a transformer), keep the barrier empty: no copper on any layer, no track, plane or via, across the gap between the two sides, as wide as the isolating part's own distance between its two pin rows; only parts rated for the barrier bridge it (the isolator, the transformer, a rated safety capacitor); each side has its own ground and its own reference plane (the one plane split that is always justified; `general.md` GEN-64 (b)). A slot milled through the board under the isolating part lengthens the path along the surface (creepage), never the distance through air (clearance), and it counts only when it is wider than the standard's minimum (commonly cited: 1 mm for normal indoor conditions; check the standard) and longer than the row of pads it separates. Where the barrier protects people (mains, or a voltage the product standard calls hazardous), its distances come from that standard and a qualified engineer (ESD-74). Why: one ground pour or one inner-layer track across the barrier removes the isolation the part was bought for, and a slot that is too narrow counts as no slot.
- ESD-74 MUST treat IPC-2221B as a clearance table only. When a product safety standard applies (higher voltages, mains-referenced circuits; for example IEC 62368-1), creepage comes from that standard, and the board is outside this skill's proven range: say so in phase 1 and leave the spacing to a qualified engineer. Why: creepage along the surface and clearance through air answer different failures, and only the product standard says what makes the product safe.

## 10. Questions for each datasheet

Write each answer, with its page, into `LAYOUT_RULES_LEDGER.md`:
- TVS or ESD part: standoff, breakdown, clamp at its peak pulse current and at IEC 61000-4-2 levels (TLP curve), capacitance, leakage, pulse power, recommended layout.
- Protected IC: absolute maximum per pin including transient and negative limits; its pulse (TLP) failure level, or the ESD part and layout its maker qualifies; HBM and CDM ratings (handling only, ESD-23), and any system-level rating (IEC 61000-4-2) with the circuit it holds for.
- Fuse or PTC: hold and trip versus temperature, time-current curve, voltage rating (DC or AC), resistance range. Fuse: breaking capacity at our voltage, I^2t. PTC: maximum voltage and fault current, current or power once tripped, reset behaviour, trip endurance.
- Reverse-polarity MOSFET: gate-source maximum, body-diode behaviour, safe operating area, which pad is drain and which is source.
- eFuse or switch: over-voltage threshold and response time, reverse blocking, behaviour after a fault (latch or retry).

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Every wire in the protection table | Netlist list of connector pins against the table | Protection table with no blank row |
| Clamp at the pins, flow-through, own ground via | Close-up crop per connector; distance pin to clamp | Crops with dimensions |
| Order on each power input (fuse, reverse element, power TVS) | Schematic order per input; board crop; the TVS's fault current against the fuse curve | Crops, calculation |
| Reverse-polarity MOSFET orientation | Schematic and footprint pin numbers: drain to the input, source to the load | Crop with pin numbers |
| Standoff and clamp against downstream ratings | Continuous voltage with tolerance against the standoff; clamp at the ring, surge and ESD currents from datasheet curves, each against the rating ESD-21 names for that stress; nanosecond simulation where needed; missing pulse data written as such | Calculation, plot |
| Fuse and PTC rating at temperature | Derating table at the local temperature, hot copper nearby included; fault table with the partial-short sweep per branch; prospective short-circuit current per fuse against its breaking capacity; a PTC's fault limits and tripped-state current; adiabatic copper check of the let-through | Table in the design note, worksheet |
| Spacing above 15 V on exposed copper, above 30 V anywhere | Net-class clearances against IPC-2221B Table 6-1 for location and coating | Class table, DRC report |
| Back-feed paths | Simulation with the off domain as a floating rail | Plot, residual voltage |
| Chassis option | Board crop of the bond footprints (two or more 0 ohm parts, their vias); hole plating list | Crop, list |
| Mis-plug | Analysis per harness; keyed connectors in 3D | Analysis, renders |

## Typical mistakes

- A wire to a panel switch had no clamp: a negative step of a few volts turned the device on with the switch off, and an 8 kV contact discharge would have put about 17 V on FET gates.
- A small board computed only the slow charge sharing for ESD; the nanosecond transient put about 10 V on a 6 V-rated IC until the capacitor's ground via moved onto its pad.
- A CC-line ESD part was chosen from a "24 V ESD" headline; its standoff and clamp had to be checked against the controller's CC rating.
- The only stocked TVS of the planned type had a handful of parts in stock; a pin-compatible substitute was accepted only after comparing clamp tables.
- Overvoltage protection cut the input upstream, while the capacitors below still held enough energy to damage the load; a clamp at the protected rail was added.
- A chassis-bond option was placed on the first board because the enclosure might become metal; the bond resistor ended up fitted by default, which the connector standard expects.
