# PCB rules: USB

Purpose: layout rules for USB-C receptacles, CC lines, USB-PD controllers, VBUS protection, shield treatment, the USB 2.0 data pair and ESD placement.

Contents
1. Placement priority
2. USB-C receptacle footprints and mechanics
3. Contacts, CC lines and resistors
4. USB-PD controllers
5. VBUS protection and inrush
6. Shield and chassis
7. USB 2.0 differential pair
8. ESD placement
9. Questions for each datasheet
10. What to verify, and how; typical mistakes

USB 3.x and faster links are outside version 1's proven range: say so in phase 1. Power-path parts after the receptacle (eFuse, filter, converter) follow `power.md`; clamp sizing follows `protection-esd.md`.

## 1. Placement priority

1. The receptacle, at the position the enclosure fixes (from the interface file).
2. ESD parts for the data and CC lines, right behind the receptacle pins.
3. The VBUS chain in the order of `protection-esd.md` section 1 for power inputs: a fuse or PTC first where a sustained over-voltage on VBUS is credible (a faulty or non-compliant source, a cable fault), then the VBUS TVS; where it is not credible, the VBUS TVS right behind the pins. Then the eFuse or load switch, wherever USB-31 (bulk capacitance on VBUS) or the fault table needs one.
4. The CC resistors, or the PD controller with its CC and VIN capacitors.
5. The USB PHY or the microcontroller's USB pins, with series resistors if the part needs them, as close as the mechanics allow.

Why: surge and ESD current must be stopped before it travels across the board, but a sustained fault must open a fuse, not burn the TVS; the data pair is shortest when the PHY sits near the connector.

## 2. USB-C receptacle footprints and mechanics

- USB-01 MUST take the footprint from the maker's drawing for the exact part number: signal pads, plated slots for the shell legs, locating pegs, the PCB edge line and the mating face position. Compare with `scripts/fp_audit.py`. Why: one receptacle's drawing puts the board edge several millimetres in front of its locating holes; placed by eye, its front legs would have left the board.
- USB-02 MUST choose the mounting style (top mount, mid mount, vertical, or a panel type whose shell passes the edge) from the enclosure, and prove in a section view that the real plug mates fully through the wall. The USB-C plug overmold can be up to 12.35 x 6.5 mm. Why: a receptacle set behind a thick wall cannot take the plug.
- USB-03 MUST anchor the shell with its soldered through-hole legs or tabs, and agree any flange overhang and wall land with the enclosure design (`connectors-mechanical.md`). Why: plug forces lever on the shell and must not reach the signal pads.
- USB-04 MUST check the shell slots against the fabricator's plated-slot minimum (see `references/jlcpcb/capabilities.md`) and that the assembler can place the part. Why: a slot below the minimum is refused or made differently.
- USB-05 MUST check the receptacle's current and temperature rating against the worst current the upstream protection lets through. Why: a 3 A receptacle behind a 4 A limiter is not protected.

## 3. Contacts, CC lines and resistors

- USB-10 MUST connect every VBUS contact and every GND contact of both rows with copper sized for the current; bridge the two VBUS groups with enough copper and vias. Why: an orphaned contact carries nothing and its neighbours carry its share.
- USB-11 MUST join D+ to D+ (A6, B6) and D- to D- (A7, B7) right at the receptacle, with the shortest stubs (at high speed within the limit of USB-52), when USB data is used. Why: otherwise the device works in one plug orientation only.
- USB-12 MUST give a sink its own Rd (5.1 kohm, USB-C specification) on CC1 and on CC2, or use the controller's internal ones. Never one resistor for both lines. Why: a shared resistor makes C-to-C chargers refuse to supply power.
- USB-13 MUST give a source the Rp from the USB-C specification table for the current it advertises, and define its role and cable. Why: an always-hot source receptacle and a C-to-C cable would put the board's supply onto a laptop's port.
- USB-14 MUST keep CC lines short, over continuous ground, away from switch nodes and inductors. They carry PD signalling and are not a 90 ohm pair. Why: the edges are slow, but a noisy CC line breaks negotiation.
- USB-15 MUST leave unused data pins of a power-only receptacle unconnected, or protect them. Why: an unused wire to the outside is only an ESD path.
- USB-16 MUST size a sink's current from what the source has offered, never from attachment alone, and write in the design note what the sink draws in each state of this table:

  | State | How the sink knows | Current it may draw |
  |---|---|---|
  | Not attached, or detached | No valid VBUS, or the CC pins open | None; back to its standby load (USB-23) |
  | Attached with its two Rd, nothing read | VBUS valid | The default USB power as its USB 2.0 or 3.x specification defines it: 100 mA (150 mA for 3.x) until a host configures the sink, then 500 mA or 900 mA at most |
  | Type-C current read | A CC-logic part or comparators read the source's Rp level on CC (1.5 A or 3 A) | The advertised current, followed when the advertisement changes |
  | PD contract | The controller holds an accepted request | The contract's current at the contract's voltage (USB-20), within the cable's rating; after a hard reset, a detach or a renegotiation it falls back to the rows above until the new contract |

  A sink with only two Rd resistors that needs more than the default (a 5 V, 3 A load) adds a current detector or limits its draw (a charger's input-current setting, a load switch) to the default. Why: two Rd resistors make the source switch VBUS on; they do not tell the sink how much it may take (TI TUSB322I datasheet, sections 6.3.2.2 and 6.3.3).
- USB-17 MUST declare the product's USB power scope in the design note: 5 V only; PD up to 20 V and 100 W (Standard Power Range, SPR); or PD at 28, 36 or 48 V up to 240 W (Extended Power Range, EPR, USB PD Revision 3.1 or later), with the PD revision implemented. Rate VBUS, CC and their protection for the highest voltage of that scope with its tolerance, plus the faults the fault table names for it (a non-compliant source, a damaged cable). An EPR product checks its controller, cable, connector, protection and spacing (`protection-esd.md` ESD-73) at its EPR voltage; a 5 V-only or SPR product is not rated for 48 V by default. Why: a blanket "up to 21 V" under-specifies an EPR design and over-specifies a 5 V gadget (USB Promoter Group, USB PD Revision 3.1 announcement, 2021).

## 4. USB-PD controllers

- USB-20 MUST read the controller's protocol-behaviour section and write a table: what it requests at each voltage a source offers, what it falls back to, when it resets. Prove for every offered voltage that the board never draws more than it requested. Why: one sink requested its set current at whatever voltage it picked, so the board over-drew its contract below the top voltage; two schematic reviews missed it.
- USB-21 MUST place the controller's VIN filter (series resistor and capacitor) and CC capacitors at its pins, as on the maker's evaluation board, and keep its I2C lines away from switch nodes and the unfiltered VBUS. Why: the controller reads small CC voltages and must not be upset by switching noise.
- USB-22 MUST rate CC parts for the highest VBUS of the declared scope (USB-17): a damaged cable can short CC to VBUS. Choose the CC ESD part's standoff and check the controller's CC absolute maximum. Why: a CC clamp rated for 5 V dies at the first such short.
- USB-23 MUST hold downstream converters off until the input is valid and the inrush is done. Why: a sink that loads the bus during negotiation exceeds its standby limit.
- USB-24 MUST write into the design note any controller register that triggers a renegotiation, and keep firmware away from it unless the system is re-qualified. Why: a stray write can ask the charger for a voltage the board was not built for.

## 5. VBUS protection and inrush

- USB-30 MUST place the VBUS TVS at the connector entry, behind nothing but the fuse or PTC where section 1 asks for one, with a short broad loop to ground. Choose its standoff from the highest continuous VBUS including tolerance (vSafe5V maximum 5.5 V; a 20 V PD contract 21 V), never from the hot-plug ring (USB-32). Where the input rides through a sustained over-voltage by disconnecting (`protection-esd.md` ESD-20, ESD-31), the TVS ahead of the switch stands off that voltage (the highest VBUS of the declared scope, USB-17, or the fault voltage the fault table names) and clamps below the switch's absolute maximum. Check its clamp at the ring, surge and ESD currents against the downstream ratings as `protection-esd.md` ESD-21 sorts them, and its pulse energy against the ring (ESD-20 to ESD-22). Why: a standoff raised to cover the ring clamps far above the parts behind it (often rated 6 V on a 5 V port), and a standoff just above 20 V does not keep 20 V-rated parts safe during the clamp.
- USB-31 MUST keep the capacitance directly on VBUS within the USB specification's limit for the role (look up the current figure; it is small, about 10 uF for a sink at attach), and put larger bulk behind an eFuse or load switch with controlled inrush. Why: large capacitance on VBUS draws an inrush the source may refuse.
- USB-32 MUST expect hot-plug overshoot: cable inductance and the input ceramics can ring to nearly twice VBUS. Check it in simulation. The TVS at the entry clamps it (its standoff stays at the continuous VBUS, USB-30); add damping where the clamped peak still exceeds a downstream absolute maximum, and rate every part on VBUS, capacitors included, above the clamped peak. Why: the ring passes the TVS standoff by design, and whatever the clamp leaves reaches every part on VBUS.
- USB-33 MUST place the eFuse or load switch, which the board has wherever USB-31 or the fault table needs one, close after the TVS, then the input filter (`power.md`). Keep protection discharge current out of the controller's analog and CC ground. Why: discharge current in that ground shifts the CC thresholds.

- USB-34 MUST, in a device with its own supply, sense VBUS and switch the pull-up on D+ (or D-) on only while VBUS is present. Why: a pull-up on a dead bus feeds the host through its data line and breaks the bus's rules for attaching.

## 6. Shield and chassis

- USB-40 MUST decide the shell treatment from the enclosure and write it in the design note. Default: shell on ground, as the USB-C specification expects. For a metal enclosure, or where one may come later (phase 2, step 13): shell on a chassis net, bonded to ground at one point beside the connector, with unfitted RC positions (for example 1 Mohm and a 1-10 nF high-voltage capacitor) in parallel. Make the bond low-inductance (USB-41): two or more parallel 0603 or larger 0 ohm parts, fitted by default, on wide copper, each with several vias, beside the shell tabs. With the bond unfitted, the high-voltage capacitor is the ESD path: size and rate it for that (`protection-esd.md` ESD-60). Why: the footprints cost nothing and avoid a respin when the enclosure changes, and a single 0 ohm part with its via sets the inductance of the shell's discharge path.
- USB-41 MUST give the shell's ground or chassis connection low inductance: several vias at the shell tabs, and an unbroken plane under the connector. Why: a strike on the shell must reach ground without crossing the board.
- USB-42 MUST NOT run shell or chassis copper through sensitive areas, and MUST NOT tie it to an undefined metal part of the enclosure. Why: shell current then flows through the circuits it should bypass.

## 7. USB 2.0 differential pair

- USB-50 MUST decide by speed. High speed (480 Mbit/s): follow the PHY's or controller's layout guide and the connector maker's, and route the pair as a controlled 90 ohm differential pair, +-15 %, wherever practical, also on a short run; a stretch that cannot be controlled (the pins of the receptacle or the chip, an ESD part's pads) is kept short and recorded. Full and low speed on a small board work without impedance control, but still route the pair together, equal in length, over solid ground. Why: high-speed edges make a few centimetres a transmission line, and the discontinuities of connector, ESD part, pads and vias add up even on a short run; full-speed edges do not.
- USB-51 MUST take width and gap from the fabricator's impedance calculator for the actual stack (`references/jlcpcb/capabilities.md`); record inputs and result. On 2-layer 1.6 mm boards an edge-coupled microstrip pair at 90 ohm is very wide: use a coplanar pair with ground, or 4 layers. When the controlled-impedance option is ordered, give the pair a width no other track on that layer uses and write layer, width, gap and target in the order remark. Why: a guessed width misses 90 ohm by far on a thick dielectric, and the fabricator finds controlled lines by their width.
- USB-52 MUST keep the pair on one layer over an unbroken reference (its distance to the reference edge and the board outline as in `general.md` GEN-08), away from clocks and switch nodes, other signals at least three line widths away (starting point), and length-matched within the pair to the chip maker's figure (often about 1 mm). If a layer change cannot be avoided, change both lines together with a ground via beside them. At high speed, no branch hangs on the pair: test access sits on the line itself (`dfm-dft.md` DFM-97); the stub that joining the two D+ and the two D- contacts makes (USB-11) stays within the stricter of the PHY maker's and the connector maker's limits (for example 2.5 mm or less in TI's Type-C guidance, SSZTC87); any other unavoidable stub or neck-down follows the PHY's guide, or is justified by a channel or eye simulation. `general.md` GEN-42 grants no allowance here: a 10 to 12 mm test-point branch is a finding, removed or justified by that simulation. Why: stubs, gaps and skew turn the differential signal into reflections and common-mode noise.
- USB-53 MUST name the nets so KiCad treats them as a pair (suffixes P and N, or + and -) and add custom rules for width, gap, uncoupled length and skew (`scripts/drc_run.py`). Why: the router and DRC treat two lines as a pair only when told.
- USB-54 MUST keep the pair mirror-symmetric: nothing (no via, no part) between the two lines; series parts (the PHY's resistors at the PHY, ESD) as a mirrored pair with equal pad entries; every pad, via, neck, ESD part and test pad on one line has its twin on the other; length matched per segment between vias and bends, corrected where the error arises, not only in total. On a port with a detachable external cable, reserve a common-mode choke position at the connector with a zero-ohm bypass fitted on samples. Why: any asymmetry turns the differential signal into common-mode current on the cable, the DRC sees only total skew, and the position lets emissions be fixed without a new board.

## 8. ESD placement

- USB-60 MUST place the ESD array for the data and CC lines at the receptacle, before series resistors and the PHY, with each line running through the array's pads (flow-through), no stubs. For high speed choose a capacitance below about 1 pF per line, or the maker's figure. Why: a stub before the clamp lets the edge in first, and extra capacitance closes the eye.
- USB-61 MUST connect the ESD part's ground pin to the plane through its own via at the pad. Why: at an 8 kV contact discharge each nanohenry of trace and via adds about 35 V (`protection-esd.md` ESD-03).
- USB-62 MUST keep the data and CC pins' DC and sustained levels, a CC-to-VBUS short included (USB-22), within their absolute maximum, and for ESD use the pairing the PHY's or controller's maker recommends (its ESD part and layout), or compare the ESD part's clamp voltage at the test current (TLP data) with the protected pin's pulse (TLP) failure level, as `protection-esd.md` ESD-21 sorts the stresses. Where the pin has no pulse data, write that uncertainty in the design note; either way the system-level ESD test on the bench list decides. Why: a clamp above the pin's pulse failure level is not shown to protect it; a nanosecond residual above a DC absolute maximum does not by itself mean damage, and an unqualified combination below it is not proven safe either.

## 9. Questions for each datasheet

Write each answer, with its page, into `LAYOUT_RULES_LEDGER.md`:
- Receptacle: where is the PCB edge line; slot and peg sizes; board thickness range; mating face position; current and temperature rating; is a panel or mid-mount variant available in stock?
- PD controller: what it requests at each offered voltage, fallback rules, CC capacitors, VIN filter, standby limit, which registers renegotiate.
- PHY or MCU USB pins: series resistors, impedance, length matching, stub limits, recommended ESD part and layout, pulse (TLP) failure level of the pins.
- Sink without PD: how it reads the source's current advertisement (USB-16). Any USB power input: the declared scope and PD revision (USB-17).
- ESD array: capacitance per line, clamp at the IEC 61000-4-2 test current, standoff, recommended flow-through footprint.
- VBUS TVS: standoff, clamp at peak pulse current, pulse power, leakage at the highest VBUS.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Pull-up of a device with its own supply (USB-34) | Schematic: VBUS is sensed, and the pull-up is switched by it or by firmware that reads it; the firmware hand-over says so | Schematic crop, hand-over line |
| Footprint against the maker's drawing | `scripts/fp_audit.py`; overlay with the drawing | Audit table, crop |
| Plug mates through the wall | Section view with the real plug; `scripts/interface_export.py` data into the project's own CAD fit check, or FAIL "cannot run" carried to the mechanical review with the section views | Section image, fit report or the FAIL line |
| Both contact rows connected; CC resistors separate | `scripts/netlist_check.py` against the expected connectivity | Check report |
| PD request table per voltage | Datasheet behaviour section against the load budget | Table in the design note |
| TVS and ESD at the connector, flow-through | Copper crops; distance from the receptacle pins; VBUS chain order against `protection-esd.md` section 1 | Crops with dimensions |
| VBUS TVS standoff and clamp | Continuous VBUS with tolerance against the standoff; clamp at the ring, surge and ESD currents against each downstream absolute maximum; hot-plug simulation | Calculation, plot |
| Data pair geometry | Calculator record; `scripts/impedance_check.py` on the width, gap and layer that are on the board; DRC with pair rules; `scripts/return_path_check.py` for the ground under the pair | Record, `out/impedance_check.md`, DRC report, `out/return_path.md` |
| Pair symmetry and stubs | Crops of the pair with every part, pad and via; skew per segment between vias and bends; stub lengths against USB-52 (no branch at high speed) | Crops, segment table |
| Sink current and power scope (USB-16, USB-17) | The state table in the design note against the load budget; the declared scope against the VBUS and CC ratings | Design-note lines |
| Shell treatment | Schematic and board crops of the bond footprints (two or more 0 ohm parts, their vias) | Design-note line, crop |

## Typical mistakes

- A PD sink asked for the same current at every voltage it picked, so the device drew more than its contract at lower voltages. Found only at the layout gate, after two schematic reviews.
- The receptacle sat too far inside the board; a plug could not mate through the thick enclosure wall. It became a panel-type receptacle whose shell passes the board edge.
- A panel-type receptacle's flange hung below the board top and had to sit past the routed edge; the edge was pulled back and the wall got a small land.
- A power-only receptacle had its data pins wired to the PD chip: no function, and a direct ESD path.
- An output was an always-hot USB-C source receptacle; a C-to-C cable to a laptop would have fed the laptop's port. It became a two-wire harness.
- An eFuse limit above a new 3 A receptacle's rating let a fault exceed the contacts; the limit had to be lowered when the part changed.
- Common in the field: one 5.1 kohm resistor shared by CC1 and CC2, so C-to-C chargers supply nothing.
