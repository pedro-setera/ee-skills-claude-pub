# <board name>: hardware facts for the firmware (hand-over), revision <A>

**State: <DRAFT after gate 1 (schematic approved; pins can still move until the PCB is approved) | FINAL after gate 2, board sha256 <value> | UPDATED after bring-up on <date> | RELEASED for production on <date> (section 12)>.**
Kept as `FIRMWARE_HANDOVER.md` in the board folder. Written for whoever writes the firmware, a person or an agent, who has not seen the design: everything they need about the hardware in one place, so that they do not have to read the schematic to find a pin.

Rules for writing it:
1. Every line comes from a file of this project and names it (the netlist, the datasheet page, the design note, the requirements page). Nothing from memory; what is not known says UNKNOWN and who settles it (`SKILL.md` rule 18).
2. The pin table is generated from the exported netlist (`python -I scripts/netlist_check.py --project <board folder> --pins`), then completed by hand from the datasheets. After every change of the schematic it is generated again and compared. For a programmable part, the columns pin, pin name, net, function on this board, direction and the peripheral to use are copied from the per-part table of `out/pin_function_check.md` (`scripts/pin_function_check.py`).
3. Plain, exact words. No private data.
4. Tell the user each time this file is new or changed: where it is and what changed.

## 1. The programmable parts
| Part | Exact part number, package | Clock | Supply | Programming and debug |
|---|---|---|---|---|
| <U1 microcontroller> | <maker number with suffix, QFN-32 (datasheet file, revision)> | <crystal Y1 8.000 MHz, 10 ppm, load 12 pF; no 32 kHz crystal> | <3.3 V, analog supply filtered (L1, C7)> | <SWD on J3 (pin table below); UART bootloader on TP5 / TP6; BOOT0 pulled low by R9, high via TP7> |

Fitted options the firmware must match: <the inductor of the chip's internal converter fitted or not; 32 kHz crystal fitted or not; the oscillator's drive setting for Y1; external flash, size>. How the board revision is read: <resistor code on PB12 to PB14 | not readable: fixed in the build>.
Boot and strap pins: <pin, level at reset, what it selects, how to change it (datasheet page)>. Reset: <source, how long held, button or supervisor>.
Firmware owner: <who writes and loads it>. Pins, clocks and peripherals accepted: <by the owner on <date> | a minimal configuration compiles in <the maker's tool>, report <file>>. Bring-up image, before the order: <file: clock running, one output toggling, the debug port answering | owner and date>.
Unused pins: <how the firmware must set them, as the datasheet says (page)>. Internal pulls the hardware relies on: <pin, pull-up or pull-down, from when it must be on | none: every default level is held by a resistor on the board>.

## 2. Pin map (one row per pin of each programmable part)
| Pin | Pin name (datasheet) | Net | Function on this board | Direction | Active level | Pull or drive on the board | State wanted at reset and in sleep | Peripheral to use | Drive or slew setting; I/O voltage, 5 V tolerant or not | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| <12> | <PA5> | <LED_STATUS> | <green status light D2> | <out> | <high = on> | <1 k series to the LED> | <low (off)> | <GPIO, or timer channel for dimming> | <lowest drive; 3.3 V, not 5 V tolerant> | <2 mA> |
| <13> | <PA6> | <BTN_TEST> | <test button SW1> | <in> | <low = pressed> | <10 k pull-up R4, 100 nF C9> | <input> | <GPIO with interrupt> | <3.3 V, not 5 V tolerant> | <debounced by RC, about 1 ms> |
| <20> | <PB6> | <I2C_SCL> | <sensor bus clock> | <open drain> | | <4.7 k pull-up R6 to 3.3 V> | <released> | <I2C1> | <open drain; 3.3 V> | <400 kHz maximum (sensor datasheet p. 9)> |
| <25> | <PB1> | <not connected> | <free> | | | | <configure as analog or output low (datasheet p. 71)> | | | |

Pins that must NEVER be driven in a certain way: <both halves of a bridge on together; an output against a fixed level; a pin above its rail>. Registers and settings that must never be written: <a setting that disables the debug port; a clock or supply option the board does not have>. Pin states required BEFORE a rail is switched off, so that nothing back-feeds it (design note, back-feed list): <UART TX to the peripheral low before its rail goes off>. Outputs that must reach a safe level before anything else runs: <heater off, load switch off>.

## 3. Buses and the parts on them
| Bus | Pins | Speed and mode | Device | Address or chip select | Datasheet | Note |
|---|---|---|---|---|---|---|
| <I2C1> | <PB6, PB7> | <up to 400 kHz> | <U3 temperature and humidity sensor> | <0x44> | <file, p. 9> | <first reading 2 ms after power-up> |
| <UART1> | <PA9 TX, PA10 RX> | <3.3 V levels, no flow control> | <J2 host connector> | | | <connector pin table below> |

## 4. Analog inputs and outputs
| Signal | Pin, channel | What it measures | Scaling (formula with the part values and tolerances) | Range | Source impedance and settling | Reference |
|---|---|---|---|---|---|---|
| <VIN_SENSE> | <PA1, ADC channel 1> | <input voltage> | <V_in = V_adc x (R1 + R2) / R2 = V_adc x 11.0, +-2 % worst case with 1 % resistors> | <0 to 30 V -> 0 to 2.73 V> | <9.1 k; sample time at least <x> (datasheet p. <n>)> | <internal 3.3 V supply, +-1 %> |

## 5. Power: what the firmware controls and must respect
- Rails and who switches them: <EN_5V (PA8, high = on) enables the 5 V converter; wait for PG_5V (PA11, high = good), typically 2 ms>.
- Order and waits the hardware requires (`REFERENCE_CHECK.md`, supply order): <sensor rail on, wait 1 ms, then the first bus access>.
- Sleep and wake: <which parts can be switched off, their wake-up times, the wake sources (button, timer)>. The running time promised to the user assumes: <sleep current <x> uA, active <y> ms every <z> s> (`GATE1_SUMMARY.md`, power and running time): the firmware must meet these or the running time changes.
- Brown-out and power loss: <threshold, what must be saved, how long the supply holds>.
- USB: <the pull-up on D+ is switched on only while VBUS is sensed on <pin> (`references/pcb-rules/usb.md` USB-34) | not a USB device with its own supply>.
- Battery: <how the charge state is read, charge status pins, what to do when the cell is low or too hot>.
- Cooling (`references/pcb-rules/thermal.md` THM-33, THM-50): <the fan's speed against the temperature read at <sensor>; the temperature at which the alarm is raised and the one at which the hot part is slowed or switched off; how a stopped fan is seen (speed signal) and what the device then does | no fan and no temperature limit to keep>.

## 6. What the user sees, hears and presses (from the requirements page)
| Element | Behaviour the user was promised | Requirement |
|---|---|---|
| <Green light D2> | <on = powered; blinks once a second when the fan is stuck> | <REQ-05> |
| <Button SW1> | <fan at full speed while pressed> | <REQ-06> |

## 7. Connectors and test points the firmware developer uses
| Connector or point | Pin | Signal | Level | Note |
|---|---|---|---|---|
| <J3 debug> | <the maker's standard 10-pin debug header: 1 VREF, 2 SWDIO, 3 GND, 4 SWCLK, 5 GND, 6 SWO, 7 key, 8 NC, 9 GND, 10 NRST> | | <3.3 V> | <1.27 mm 2 x 5; cable <part>> |
| <TP5, TP6> | | <UART bootloader TX, RX> | <3.3 V> | <position: top side, near U1 (assembly drawing)> |

## 8. Timing and limits from the datasheets that the code must keep
- <Sensor U3: at most one measurement per second to avoid self-heating (datasheet p. 6).>
- <Fan output: PWM 25 kHz, open drain, never above 5 V on the control line (fan specification).>
- <Flash endurance, start-up time of the crystal, watchdog source.>

## 9. Requirements the firmware must implement
| ID | Requirement | Hardware that serves it |
|---|---|---|
| <REQ-01> | <temperature every 10 s within +-0.5 C> | <U3 on I2C1; self-heating note above> |

## 10. Known hardware facts and errata of this revision
<None yet | found at bring-up on <date>: <the 32 kHz crystal is not fitted on revision A: use the internal oscillator>.> Chip errata that touch this design: <maker's errata sheet, item, work-around>.

## 11. Open points
| Item | Who settles it | Until then |
|---|---|---|
| <UNKNOWN: the fan's tachometer pulses per turn> | <bench test BT-08> | <assume 2> |

## 12. Release, before production
Completed by the firmware owner before `PRODUCTION_RELEASE.md` is signed (`references/reviews.md` section 8).
| Item | Value |
|---|---|
| Executable file and its sha256 | <file, hash> |
| Source revision, build command, toolchain name and version | <tag; command; compiler and version> |
| Bootloader, option bytes or fuses (read-out protection, brown-out level, boot source) | <values, and how they are set> |
| Programming command and tool | <command line; probe> |
| Recovering a board that no longer starts or answers | <the maker's way: boot pin, erase under reset, built-in bootloader> |
| Calibration data: format, where it is stored, how it is written per board | <... / none> |
| Functional-test image | <file, hash / the product image> |
| Secure provisioning (keys, locked debug port), only where the product needs it | <... / not needed: <reason>> |

Sources used: <netlist sha256, `REFERENCE_CHECK.md`, `DESIGN_NOTE.md` section 14, `src/datasheet_pins.toml`, `REQUIREMENTS.md`, the datasheets named above>.
