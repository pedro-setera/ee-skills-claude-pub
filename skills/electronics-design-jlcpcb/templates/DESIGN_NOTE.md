# <board name>: design note, revision <A>

One note for the schematic stage. Every number here is recalculated from the drawn values after each change. After any fix, search this file for every changed value.

## 1. Status
| Item | Done | Left |
|---|---|---|
| <Concept and blocks> | <yes> | |
| <BOM and stock> | <yes, dated <date>> | <re-check on order day> |
| <Simulations> | <5 of 7> | <SIM-06, SIM-07> |

## 2. Concept in blocks
Every block traces to a requirement, a datasheet demand, a credible fault or a rule; a block that traces to nothing is removed (`references/working-rules.md` section 12).
| Block | What it is | Set-point | Traces to |
|---|---|---|---|
| <1. Input protection> | <fuse 1 A at J1, then a TVS with 6.0 V standoff> | <trip above 1.5 A> | <REQ-02; protection table rows 1 and 2> |
| <2. 3.3 V regulator> | <LDO from 5 V, 3.31 V nominal (3.22 to 3.39 V worst case), 300 mA> | <feedback divider 47 k / 15 k> | <REQ-01, REQ-05; the supply of the sensor and the MCU, datasheets p. 3> |
| <3. Sensor and MCU> | <I2C 400 kHz, pull-ups 4.7 k> | | <REQ-01, REQ-02> |

## 3. BOM summary and cost of the sample batch
| Group | Parts | Class (basic / preferred / extended) | Cost for <5> boards | Note |
|---|---|---|---|---|
| <Passives> | <20> | <basic> | <1.10> | |
| <ICs> | <3> | <2 extended> | <4.20> | <extended fee per line> |

Per-order fees are not per-part: list them apart.
| Fee | Amount | Applies when |
|---|---|---|
| <PCB, <5> pcs> | <x> | always |
| <Setup and stencil> | <x> | assembly |
| <Extended-part fee x lines> | <x> | per extended line |
Stock date: <date>. Source: `out/BOM_STOCK_CHECK.md`.

Cost against the target (`references/working-rules.md` section 11, quality first, then cost): <x> per board at <5>, <y> at <100>, target <z>.
| Cost driver (the biggest) | Per board | A cheaper way to the same quality | Found? |
|---|---|---|---|
| <U2 LDO, extended line> | <0.40 plus the fee> | <a basic LDO, same pin-out, accuracy, dropout and maker standing> | <found, taken> |
Kept as an unfitted footprint because its need is uncertain: <snubber C30>. If quality and the target cannot both be met, the user is told in plain words with the options (a higher cost, fewer features, a named limitation) and decides.

## 4. Power budget
| Rail or load | Typical | Peak | Voltage at the load | Note |
|---|---|---|---|---|
| <3.3 V MCU> | <15 mA> | <40 mA> | <3.28 V> | <incl. trace drop> |
| <Total from the source> | <60 mA> | <150 mA> | | <standby <x> uA> |

Rail table: target impedance Z_target [ohm] = allowed dynamic voltage [V] / load step [A] (or V_rail x fraction / step), with its frequency range and observation point; the allowed dynamic voltage is the bench pass value (`power.md` PWR-49, PWR-50).
| Rail and voltage | Load step (A) | Dynamic allowance (V) | Target impedance (ohm), range, observation point | Total capacitance driven (effective, vs regulator maximum) |
|---|---|---|---|---|
| <3V3, 3.3 V> | <0.2 A> | <3 %, 99 mV> | <0.5 ohm> | <18 uF vs 100 uF max> |

Heat table: one row per part that dissipates more than about 0.1 W or sits near its temperature limit (regulators, converters and their inductors, drivers, power resistors, clamps, chargers). Worst case: the corner of THM-01 over the whole envelope (a boost at the lowest input and full load), the hottest surroundings of the requirements page. The thermal resistance is the one for the copper this board really gives the part, not the datasheet's test-board figure (`power.md` PWR-21, PWR-62). Phase 9 fills in the copper and vias; the layout review recomputes the table.
| Part | Dissipation, worst case (formula) | Path for the heat (package, copper area, vias) | Estimated temperature with the air at the part (<hottest surroundings> plus the rise in the case, THM-02) | Limit, less the margin of THM-04 | Proof |
|---|---|---|---|---|---|
| <U2 regulator> | <(12.6 - 3.3) V x 0.04 A = 0.37 W> | <SOT-223 tab on 300 mm2 of copper, 6 vias to the ground plane; about 60 C/W (maker's curve of theta_JA against copper area, p. <n>; or the bound of THM-05: optimistic, so UNKNOWN with a bench test)> | <60 + 0.37 x 60 = 82 C> | <125 C junction; 105 C for the capacitor 3 mm away> | <calculation; BT-06 thermocouple on the tab> |

Cooling decision for every part above about 0.5 W or within 25 C of its limit (`references/pcb-rules/thermal.md`): the steps of the cooling ladder tried, with the temperature each one gives, and the first one that holds the margin.
| Part | Loss, worst case (source) | Air at the part (hottest surroundings + rise in the case) | Copper only | Path into the case | Heat sink | Fan | Decision | With the fan stopped |
|---|---|---|---|---|---|---|---|---|
| <U5 motor driver> | <2.0 W (maker's power estimate for this design, worst case)> | <40 + 16 = 56 C (estimate)> | <100 C: at the limit> | <no metal case> | <the largest sink that fits the 10 mm height: 12 C/W in still air: 92 C: margin too small (about 8.5 C/W would hold it, and does not fit)> | <40 mm fan on that sink (3 C/W at the fan's air speed, sink maker's curve): 74 C> | <heat sink <part> with a 40 x 40 x 10 mm 5 V fan; agreed by the user on <date>> | <U5's own protection switches it off at 100 C; the fan's speed signal raises an alarm> |

Energy budget, for a battery-powered device: one row per operating mode (active, idle, sleep, transmitting, charging), each current from the datasheets at the real supply voltage and referred to the cell (`references/pcb-rules/power.md` PWR-56: through a switching converter, rail current x rail voltage / (cell voltage x efficiency)). Two results: typical figures at room temperature, and maximum figures at the hottest surroundings.
| Mode | Current (source) | Share of time | Average | Note |
|---|---|---|---|---|
| <Transmitting> | <45 mA at 3.7 V (radio datasheet p. 12)> | <1 %> | <0.45 mA> | <peak 120 mA vs the cell's 500 mA> |

Average current = the sum of the Average column, plus the regulators' quiescent current and the cell's self-discharge. Autonomy = usable capacity / average current; usable capacity is the rated capacity derated for temperature, ageing, the circuit's cut-off voltage and the discharge rate (start from 70 to 80 % of the rated capacity, an estimate). Also: peak current against what the cell can deliver; charge time from the charge current. Result told to the user in plain words ("about <n> hours per charge") against the wanted running time of the requirements page.

## 5. Protection per fault
One row per connector and per fault. The third column is the energy map: the stored energy downstream of the point where the protection acts, and whether the protection still covers it. The Protection column also says fitted, footprint only or left out, and why.
| Fault (connector or rail) | Protection (where it sits) | Acts on which stored energy | Speed and tolerance | Proof |
|---|---|---|---|---|
| <Reverse polarity (J1)> | <series diode D1 at J1, fitted> | <none stored upstream; C1 behind D1 never sees reverse> | <instant; Vf 0.3 to 0.5 V> | <SIM-02> |
| <Over-voltage (5 V rail)> | <TVS D2 at the protected rail; fuse F1 upstream, rated to open on D2's current under a sustained over-voltage; both fitted> | <clamps C1 and C2 (about 20 uF at 5 V) as well as the input> | <ns; standoff 6.0 V (above the rail's 5.5 V maximum); breakdown 6.67 to 7.37 V at 10 mA; clamp <x> V at <y> A from the clamp or TLP curve, below the 8 V absolute maximum of every part on the rail> | <SIM-03> |
| <ESD 8 kV contact (J1)> | <ESD diode to ground at J1, fitted> | <discharge only> | <ns; clamp per datasheet p. <n>> | <review> |

## 6. Noise sources and sensitive parts (EMC)
Which part disturbs which, by which path, and the measure against it (`references/pcb-rules/emc.md`). The Measure column also says whether a shield can is fitted, footprint only or not needed, and why (section 10 of that file). Phase 8 turns it into the zone map of the board: power conversion, digital, analog and sensors, radio and antenna, connectors.
| Source | Sensitive part | Path | Measure | Zone |
|---|---|---|---|---|
| <Charger ripple on VBUS (J1)> | <sensor U4: its supply and its reading> | <conducted along the 5 V rail> | <LDO U2 with its ripple rejection checked at the charger's frequency; 10 uF and 100 nF at U4> | <connectors, left edge; sensor, right edge> |

## 7. Back-feed list
Every signal between parts with separate supplies, and every connector pin that can be driven from outside.
| Path | Current and what it holds up | Measure | Proof |
|---|---|---|---|
| <Powered sensor SDA into the unpowered MCU> | <0.3 mA through the pin clamp; holds 3V3 at 1.2 V> | <1 k series resistor, R12 on its own BOM line> | <SIM-05> |

## 8. Interconnect per connector
| Connector | Pins and function | Current per pin vs contact rating | Keying, gender, pitch | Mating part |
|---|---|---|---|---|
| <J2> | <1 V, 2 SDA, 3 SCL, 4 G> | <0.01 A vs 1 A> | <polarised, header, 2.5 mm> | <housing, C-number> |

## 9. Harness per connector
| Connector | Wire and length | Voltage drop | Mis-plug analysis | Pin proof before the first plug-in |
|---|---|---|---|---|
| <J2 sensor cable> | <AWG 26, 0.3 m> | <12 mV at 5 mA, supply and return> | <keyed, cannot mate rotated or offset> | <meter, pin to pin, then the levels at the free end> |

## 10. Buy or design
| Block | Ready module (price at sample quantity and at volume, date) | Own design (cost per unit, effort, prototype rounds) | Decision and reason |
|---|---|---|---|
| <USB-C power input> | <none found well documented> | <0.40 per unit, no extra round> | <own design: cheaper and documented> |

## 11. Area budget (input to phase 8)
| Item | Value |
|---|---|
| Passive size | <0603> |
| Sum of courtyards | <420 mm2> |
| Fill target | <at most 60 percent> |
| Routing channels and label room | <200 mm2> |
| Minimum board area | <about 900 mm2> |

## 12. Test and bring-up provisions
| Provision | Designators | Purpose |
|---|---|---|
| <Test point per rail and key signal> | <TP1 to TP5> | <probe points for the first power-up> |
| <Zero-ohm link per block> | <R20, R21> | <power each block alone> |
| <Injection resistor in the converter feedback> | <R22> | <loop measurement> |
| <Unfitted tuning and fallback positions> | <C30, R23> | <snubber; fallback path unfitted until proven on the bench> |

## 13. Calculations with tolerances
| Quantity | Formula and values | Typical | Worst low / high | Limit |
|---|---|---|---|---|
| <Regulator output> | <0.8 V +/-1 % x (1 + R1/R2), R1 47 k, R2 15 k, 1 % resistors> | <3.31 V> | <3.22 / 3.39 V> | <3.0 to 3.6 V> |
| <Capacitor at DC bias> | <10 uF, 5 V bias> | <6.5 uF> | <5.2 uF> | <min 4 uF> |

## 14. Interface specification
<Pin table for the host or cable: signal, direction, level, pull, state at reset, never-write list.>

Default levels of the control inputs on the board (`references/pcb-rules/mcu-digital.md` MCU-64, MCU-65): what each one sees while its driver is in reset, unpowered or being programmed.
| Line | Input of | Safe level | Held there by | Source |
|---|---|---|---|---|
| <EN_5V> | <U3 pin 4, enable, active high> | <low: converter off> | <R12, 100 k to ground> | <U3 datasheet p. 8: no internal pull> |
| <FLASH_CS> | <U5 pin 1, chip select, active low> | <high: not selected> | <R14, 10 k to 3.3 V> | <U5 datasheet p. 6> |
| <RADIO_NRST> | <U7 pin 12, reset, active low> | <high: running> | <internal pull-up, 70 to 130 k, works without firmware> | <U7 datasheet p. 11> |

## 15. Critical technical risks, assumptions and open risks
First the three to five risks most likely to sink the design (phase 2, step 13b), worst first; then the assumptions. Each has a way and a time to be retired.
| ID | Risk or assumption | Consequence if wrong | Retired how, and when | State |
|---|---|---|---|---|
| <RISK-01> | <critical: the sensor's accuracy of REQ-01 depends on self-heating from the regulator 8 mm away> | <reading 1 to 2 C high> | <heat table now; sensor at the far edge in phase 8; BT-05 against a reference thermometer> | <open> |
| <RISK-02> | <assumption: load never above 200 mA> | <regulator hot> | <BT-03> | <open> |

## 16. Bench tests (numbered BT-01, BT-02 ...)
| ID | Test | Pass value |
|---|---|---|
| <BT-01> | <3.3 V rail unloaded, 5.0 V in> | <3.22 to 3.39 V (section 13, worst case)> |

## 17. Files
<Paths: schematic, netlist, BOM, simulations, reviews, images.>
