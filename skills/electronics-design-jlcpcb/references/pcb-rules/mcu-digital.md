# PCB rules: microcontrollers and digital circuits

Purpose: layout rules for microcontrollers and logic: decoupling, clocks, reset and boot, debug, low-speed buses, power-domain crossings, unused pins and test points.

Contents
1. Placement priority
2. Decoupling per supply pin
3. Crystals and oscillators
4. Reset and boot pins
5. Debug and programming connectors
6. I2C, SPI and UART
7. Level compatibility and back-powering between power domains
8. Unused pins, open-drain lines and default levels
9. Test points
10. Questions for each datasheet
11. What to verify, and how; typical mistakes

Memory buses, fine-pitch BGA and multi-gigabit links are outside version 1's proven range: say so in phase 1 and treat such a board as experimental work that needs a human engineer's review.

## 1. Placement priority

1. Decoupling capacitors at their supply pins, and the core-regulator capacitor (VCAP, VCORE) if the part has one.
2. The crystal or oscillator and its load capacitors at the clock pins.
3. Reset and boot-strap parts at their pins.
4. The debug connector at the board edge, reachable with the board mounted.
5. Bus pull-ups, series resistors and level shifters, close to the bus owner or the connector they serve.
6. Everything else, then test points.

Why: decoupling and clock parts depend on millimetres; buses and pull-ups do not.

## 2. Decoupling per supply pin

- MCU-01 MUST give every supply pin its own capacitor at that pin, of the maker's value where the datasheet sets one (often 100 nF), mounted for the lowest loop inductance (`power.md` PWR-37), with a ground via at the capacitor's ground pad. Why: a shared or distant capacitor does not decouple the pin it skips.
- MCU-02 MUST let the supply reach the capacitor pad first and then the pin, on short copper as wide as the pad, with the capacitor on the same side as the part, so that no via sits between the pin and the capacitor; its ground pad goes to the plane through its own via at the pad (MCU-01). The far side only where the part's maker shows it or a ball-grid package leaves no room on the near side, with that via counted in the loop. Never feed the pin first and hang the capacitor on a long stub. Why: the copper's loop inductance, not distance alone, decides what the capacitor does at high frequency.
- MCU-03 MUST add the bulk capacitor per rail the maker asks for (often 4.7-10 uF) near the part, sized for load steps by `power.md` PWR-51 where the part draws bursts. Why: it covers the slower load steps the small capacitors cannot.
- MCU-04 MUST follow the maker's filter for the analog supply and reference pins and keep their ground at the part's ground pins. Put the bead or resistor between the board rail and the pin's capacitor; compute the corner f0 = 1 / (2 pi sqrt(L C)) from the bead's low-frequency inductance and the effective capacitance, check Q (bead resistance plus ESR against sqrt(L / C)) and add a damping resistor where Q is well above 1, check the DC drop at the pin's maximum current, and record the numbers. Why: noise on the analog supply appears in every conversion, and an undamped filter rings at its corner.
- MCU-05 MUST give a core-regulator pin exactly the capacitance and ESR range the datasheet states. Why: a wrong VCAP capacitor makes the core supply oscillate or fail to start.
- MCU-06 SHOULD keep a pad-to-pin table for every decoupling capacitor of a fine-pitch part: distance, track width and squares. Why: the reviewer can then accept or reject each connection on its inductance.
- MCU-08 MUST take the decoupling of any chip whose maker publishes a decoupling or power-supply design guide (programmable logic, processors, radio chips and modules, fast converters, many microcontrollers) from that guide: the number, value and package of capacitors per supply rail and per pin group, the bulk capacitors, and where they sit. Copy the guide's table into the reference check, give each row its capacitors on the schematic, and record every deviation with its reason and its proof (the rail's target impedance, `power.md` PWR-49). Count each capacitor at its effective value under the rail's DC voltage (`power.md` PWR-34). Why: "100 nF at every pin" is a habit, not a design; a chip with several rails and fast edges needs the mix its maker measured, and too few, too small or wrongly placed capacitors show up only as random faults on the bench.
- MCU-07 MUST NOT put a ferrite bead or inductor in series with a chip's ground pin, or between ground nets that carry signal returns (AGND to GND included); filter on the supply side only, with the capacitor at the pin to the chip's ground. Why: the bead becomes a shared return impedance and raises ground bounce.

## 3. Crystals and oscillators

- MCU-10 MUST compute load capacitors from the crystal's load capacitance and the stray capacitance: C1 = C2 = 2 * (CL - C_stray), with C_stray about 2-5 pF (starting point). Check the oscillator's gain margin with the MCU maker's oscillator design note. Why: wrong load capacitance shifts the frequency, and a low gain margin gives a crystal that starts on the bench and fails in the cold.
- MCU-11 MUST place the crystal and its capacitors within a few millimetres of the clock pins, on the same layer, with the capacitors' grounds joined and taken to the part's ground by a short path. Why: long tracks add stray capacitance and pick-up to a high-impedance loop.
- MCU-12 MUST NOT route any other signal between the crystal and the MCU, or under the crystal on the adjacent layer. Why: the oscillator node is high impedance and picks up anything nearby.
- MCU-13 SHOULD surround the crystal area with ground pour tied by vias, and keep it away from switching converters, inductors, connectors and board edges. Why: noise injection and board flex both shift or stop the oscillator.
- MCU-15 MUST place a packaged oscillator, or any clock source, beside the pin it drives, and treat its output as the fastest edge on the board: one load per output unless the receiving chip's guide shows otherwise; a series resistor position at the oscillator's output pin (start with 22 to 33 ohm, or the line impedance minus the driver's output impedance); its supply filtered and decoupled at its own pin; the clock track short, on one layer, over unbroken ground, with no stub and no via where one can be avoided (a via gets a ground via beside it); away from board edges, connectors, cable exits, antennas and converters. Record the distance from the source to its load and what lies beside the track. Why: a clock is the strongest narrow-band noise source on most boards, and one placed for routing convenience radiates from every centimetre and every cable near it.
- MCU-14 MAY use a packaged oscillator or MEMS oscillator where a crystal's margin is doubtful; it still needs its own decoupling at its pin. Why: an oscillator always starts; a marginal crystal may not.

## 4. Reset and boot pins

- MCU-20 MUST give the reset pin the pull-up and capacitor the maker shows, at the pin. Why: a long reset trace picks up noise and resets the part at random.
- MCU-21 MUST strap boot and mode pins through resistors (for example 10 kohm), not hard ties, with a pad or jumper to change the state. Why: a hard tie cannot be changed when the bootloader entry turns out to be needed.
- MCU-22 MUST check every boot and mode pin's level at power-up with the external circuits attached. Why: a peripheral, a pull-up on a shared line or an LED can pull a strap the wrong way.
- MCU-23 MUST give every input that can remove power or reset the system a defined default and a glitch filter. Why: a short glitch at boot once could cut the power of a whole device.
- MCU-24 MUST protect a reset or button line that leaves the board as a cable signal, unless its pin has the IEC rating of `protection-esd.md` ESD-23. Why: a wire on a reset line is an ESD path straight into the part.

## 5. Debug and programming connectors

- MCU-30 MUST provide the debug interface the part needs (for example SWD: SWDIO, SWCLK, reset, target voltage, ground) on a standard, keyed footprint with pin 1 marked, or a cable-free pad footprint that needs no part. Why: a standard pin-out fits the probe without an adapter, and a key prevents a reversed plug.
- MCU-31 MUST place it where a probe or plug fits with the board mounted in its enclosure, clear of tall parts and cables. Why: firmware is reloaded in the enclosure far more often than on the bench.
- MCU-32 SHOULD bring out the UART or USB bootloader pins as well: always reachable, as test pads or a connector footprint, with the connector fitted where firmware is loaded through it in service. Why: a second way in recovers a board whose debug port was locked or misconfigured.
- MCU-33 SHOULD add series resistors on debug lines that leave the device in the field, and MUST add ESD protection if the connector is user-reachable, unless the pin has the IEC rating of `protection-esd.md` ESD-23. Why: field debug cables bring ESD and ground offsets.

## 6. I2C, SPI and UART

- MCU-40 MUST size I2C pull-ups from the bus capacitance (parts, tracks and cables): R_max = t_r / (0.8473 * C_bus) and R_min = (VDD - VOL_max) / I_OL, with t_r 1000 ns at 100 kHz, 300 ns at 400 kHz, and I_OL 3 mA at VOL 0.4 V for those modes. Why: too weak gives slow edges and errors; too strong exceeds the drivers.
- MCU-41 MUST fit exactly one set of pull-ups per bus segment. Pull an open-drain line up to a rail that every pin on the line tolerates, also while that device is unpowered, and that meets every receiver's high-level input voltage; otherwise use a level shifter. Why: a pull-up to a higher rail drives a low-voltage pin above its maximum or back-powers an off device (MCU-52), and one to a lower rail can miss a receiver's high level.
- MCU-42 MUST route I2C as two ordinary signals over a continuous ground reference, away from switch nodes and power current, not as a controlled-impedance pair. Why: I2C edges are slow; a nearby return matters, impedance does not.
- MCU-43 SHOULD route SPI clocks short, away from sensitive analog, with the series-resistor footprint of MCU-47 at the driver on any clock that runs more than a few centimetres or off the board, even below the line limit. Why: it damps ringing on fast edges.
- MCU-44 MUST name UART nets by direction at one device (for example HOST_TX) and check that every TX meets an RX. Why: crossed or doubled TX lines are the most common UART error.
- MCU-45 MUST check device addresses and chip-select defaults on every shared bus. Why: two parts on one address, or a chip select floating at boot, block the bus.
- MCU-46 MUST take each digital net's rise time from the driver's datasheet or IBIS model at its fast corner, never from the clock rate, and set each output to the slowest drive or slew setting that meets its timing; write both into the design note as inputs for layout (line limit, stubs, termination) and firmware. Why: the edge, not the clock, sets line limits, termination and emissions, and a slower edge is the cheapest EMI fix.
- MCU-47 MUST give every point-to-point digital net longer than the line limit (`general.md` section 8) a series-resistor footprint at the driver (Z0 minus the driver's output resistance; 22-33 ohm to start), with its receivers at the far end only; route a multi-load net as a daisy chain without branches, stubs within `general.md` GEN-42. Why: controlled impedance without termination still rings, and a receiver near the driver sees a half-height step.
- MCU-48 MUST, where the datasheet gives no rise time at the fast corner (only a maximum, which is the slow limit, or nothing), take it from the part's IBIS model: the output's ramp at its fastest column (normally `max`, the strong corner), which is measured from 20 to 80 % of the swing into the model's own test load (often 50 ohm); the 10 to 90 % rise time that the line limit uses is about 4/3 of it (a straight ramp). With neither, assume a fast edge and write it as ASSUMED in the design note: about 1 ns for a microcontroller pin at its strongest drive, about 0.3 ns for a processor, FPGA or fast-interface pin (estimates; faster parts exist). A slower drive setting counts only from the moment the firmware sets it; a boot loader may drive the pin at its default. Why: a datasheet maximum says how slow an edge may be, not how fast it is, and a line limit taken from it is several times too long.

## 7. Level compatibility and back-powering between power domains

- MCU-50 MUST check every signal between devices in both directions: VOH against VIH and VOL against VIL, at the worst supply corners, with every pull-up and pull-down, including the ones inside the parts. Why: a protective series resistor once met a strong internal pull-up at the receiver, so a logic low arrived as about half the supply and data failed.
- MCU-51 MUST use every interface level the other device's datasheet allows (for example a "3.3 V" module that may also drive 5 V TTL), not the one assumed elsewhere. Why: a back-power fix that held at 3.3 V failed at the 5 V level the same module was allowed to drive.
- MCU-52 MUST list every signal from a powered device into a device that can be off. Through its input clamp diodes the off device's rail rises; that can keep it half alive or defeat a power-off sense. Fix with series resistors, a load on the sensed rail, a buffer with power-off protection, or a level shifter. Why: a back-fed device can stay half alive and never reset.
- MCU-53 MUST check open-drain outputs from external modules for internal pull-ups to a higher rail. Why: a 5 V internal pull-up drives a 3.3 V pin and back-powers an off host.
- MCU-54 SHOULD place level shifters and series resistors at the domain boundary, close to the device that needs protecting. Why: the protection then also covers the track between the domains.

## 8. Unused pins, open-drain lines and default levels

- MCU-60 MUST handle every unused pin as its datasheet says (often analog input, or output low). Never leave a CMOS logic input floating; tie unused gate inputs to a rail. Unused pins of a microcontroller are set by the firmware as the datasheet says, without a resistor each; that instruction goes into the firmware hand-over. An unused operational amplifier or comparator is wired as its maker says; where the maker says nothing, by its kind, every connection inside the part's documented ranges:
  - Operational amplifier: a stable closed loop, its input at a defined level inside the input common-mode range (often mid-supply) and its output inside its swing. A unity-gain-stable part may be a follower; a decompensated part gets the minimum gain its datasheet requires, a current-feedback part the feedback resistor its datasheet gives.
  - Comparator: never a follower (it is not compensated for negative feedback and can oscillate). Hold its inputs at a defined difference larger than its offset, both inside the common-mode range and the differential input limit, so the output rests at one level; leave a push-pull output unconnected, never tied to a rail, and treat an open-drain output as its datasheet says.

  Why: a floating CMOS input draws current and can oscillate, and a comparator wired as a follower can oscillate too.
- MCU-61 MUST leave pins marked "NC" or "do not connect" unconnected unless the datasheet says to ground them. Why: NC pins may be connected inside the part.
- MCU-62 MUST give every open-drain line a pull-up on the board, so its level is defined while the other side boots. Pull an open-drain line up to a rail that every pin on the line tolerates, also while that device is unpowered, and that meets every receiver's high-level input voltage; otherwise use a level shifter (MCU-41). Why: a floating shutdown line triggered events at random.
- MCU-64 MUST give every control input a defined, safe level in every state of whatever drives it: running, in reset, unpowered, being programmed, and starting up before the firmware has set its pins (the pins of a microcontroller or of programmable logic are high-impedance then). Control inputs are every enable, shutdown, chip select, reset, driver-enable, write-protect, mode and address pin, and every gate or base (`power.md` PWR-61). Where the pin has no pull of its own, fit a resistor to the safe level (the level at which nothing starts, drives a bus, is selected or is erased), or a hard tie when the pin never changes. Keep the table in the design note: line, safe level, what holds it there, datasheet page. Why: a pin that floats during reset enables a converter, selects a memory or drives a shared bus for a moment at every start; the rule check does not see it, because the net has a driver.
- MCU-65 MUST read, for every such pin, whether the part has a pull inside: which way, how strong (minimum and maximum, not the typical), and whether it works without firmware. An internal pull that the datasheet guarantees without firmware counts, and no part is added. One that only firmware can switch on does not count before the firmware runs; it may serve a signal that stays on the board and matters only while the firmware runs, and is then written into the firmware hand-over with its pin. A line that leaves the board or runs long gets a resistor even beside an internal pull. Value (starting point): 10 kilohm; up to 100 kilohm where the standby current counts, after checking that the pin's leakage across it keeps the level inside the input threshold; an internal pull in the other direction forms a divider: compute the level (MCU-50). Add no pull to a line that is always driven while its receiver is powered, and none against the level a strap needs (MCU-22). Why: internal pulls are tens of kilohms, vary by a factor of two or more, and many exist only after the firmware has set them.
- MCU-63 MUST NOT wire unused protocol pins to a connector (for example data pins on a power-only USB receptacle). Why: an unused wire to the outside is an ESD path with no purpose.

## 9. Test points

- MCU-70 MUST give a test point, or a named pad a probe can hold (`dfm-dft.md` DFM-94), to every rail, reset, boot strap, debug line and every key signal, with a ground test point near each group; on a fast net the test pad sits on the track, not on a branch (`dfm-dft.md` DFM-97; a USB high-speed pair: `usb.md` USB-52). The list, the sizes, the production fixture and the table: `dfm-dft.md` section 10 (DFM-94 to DFM-99). Why: without them, bring-up means probing fine-pitch pins.
- MCU-71 MUST place test points where a probe reaches them with the board mounted, on the assembled side of a one-sided board, with room for a probe tip between neighbours (sizes: `dfm-dft.md` DFM-96; the points of a production fixture: DFM-98). Why: a test point that cannot be reached in the enclosure does not exist.
- MCU-72 MUST NOT hang a test-point stub on a sensitive node (oscillator, high-impedance analog, current-limit setting); probe on a component pad instead. Why: the stub picks up noise and loads the node.
- MCU-73 MUST label each test point with one text, reference over net (`silkscreen.md`). Why: a test point named only by number sends the technician to the drawing.
- MCU-74 SHOULD give one spare output a test point with a ground point beside it as a quiet line, and the bring-up plan a step that holds it low, then high, while firmware exercises the buses. Why: a pin held still shows ground bounce, crosstalk and supply noise at the die.

## 10. Questions for each datasheet

Write each answer, with its page, into `LAYOUT_RULES_LEDGER.md`:
- How many supply pins, which capacitor on each, and what does the maker's hardware design guide add (VCAP, analog filters)?
- What crystal load capacitance, ESR limit and drive level does the oscillator accept? Is there an oscillator design note?
- What reset circuit, and which pins set the boot mode? What are their internal pulls and default states?
- What are the input and output levels, and the internal pull-ups and pull-downs, of every pin that meets another device? Does each internal pull work without firmware, and what are its minimum and maximum?
- Which pins are high-impedance during reset, during programming and until the firmware sets them?
- What rise time does each output reach at its fastest corner, and which drive or slew settings exist?
- Is any pin 5 V tolerant only while powered?
- How must unused pins be handled? Which pins are "NC" versus "connect to ground"?
- What is the debug interface and its recommended connector?
- Does the reference board add series resistors, ferrites or ESD parts the typical circuit omits?

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| One capacitor per supply pin, at the pin | Netlist pin list against placed capacitors; distance and squares table from the board | Table, crops |
| Supply filters; no bead in a ground return | Corner, Q and DC drop from the bead's data; netlist search for beads and inductors touching a ground net | Calculation in the design note, list |
| Rise times, drive settings, termination | Rise time at the fast corner per net with its source (datasheet, IBIS ramp, or ASSUMED: MCU-48); series footprints on nets above the line limit; stub lengths | Design-note table, crops |
| Crystal area clean | Copper plots of the crystal area on all layers | Crops of each layer |
| Boot and reset straps | Schematic and netlist check of every strap; power-up levels with external circuits | Strap table |
| Bus pull-ups | Calculation with bus capacitance; count of pull-ups per segment; pull-up rail against every pin's maximum, powered and unpowered, and every receiver's high-level input | Calculation in the design note |
| Default levels of control inputs | The table of MCU-64 against each datasheet; `scripts/ratings_check.py` lists every input that can float while its driver is high-impedance | Table in the design note, `out/ratings_check.md` |
| Domain crossings | Table of every signal between domains with levels both ways and off-state behaviour | Interface table, simulation if needed |
| UART directions | `scripts/netlist_check.py` against the hand-written expected connectivity | Check report |
| Test-point reach | Renders with the board in its enclosure, probe paths | Renders with crop names |
| Debug connector access | 3D view with mating plug and enclosure | Render |

## Typical mistakes

- A series resistor added to protect a data line blocked the data: the receiver's internal pull-up made the low level too high. It shared a BOM line with other parts, so it could not be changed alone at the assembler.
- A powered peripheral's UART idled high into a switched-off processor. The processor's rail rose through its clamp diodes, and the power-off sense never fired.
- A sensor's open-drain output had an internal pull-up to 5 V and would have driven a 3.3 V GPIO and back-powered the off processor.
- An open-drain shutdown line had no pull-up on the board; it floated while the host booted, and an edge-triggered handler missed an early event.
- Common in the field: an enable or chip-select pin driven only by a microcontroller pin, without a resistor: the rule check was clean, and the converter started or the memory was selected for a moment at every reset and during programming.
- Common in the field: a pull-up added "so that it does not float" on a strap pin that has an internal pull-down: the part started in the wrong mode.
- Unused USB data pins of a power-only receptacle were wired to a chip: no function, and a direct ESD path.
- A host GPIO used as a fallback power-off input could cut the power at every boot if the bootloader drove it high for a few milliseconds. Such fallback paths are fitted only after a bench proof.
