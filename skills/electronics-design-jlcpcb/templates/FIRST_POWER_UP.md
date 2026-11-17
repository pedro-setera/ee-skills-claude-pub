# <board name>, rev <A>: first power-up

**Goal:** prove each board safe before anything expensive touches it. Work in order. **Stop at the first value outside its range**, write it down, and do not continue.
One person, one board at a time.

## Rules for every step
1. Bench supply only, always current-limited, until the step "real source".
2. No downstream device (anything this board feeds or drives) on the board until the protection steps pass. Then add them one at a time.
3. No downstream device during any fault test, except dummy loads named in the test.
4. Logic levels are measured at the free end of a harness before it meets a real device.
5. Temperatures: a thermocouple or IR camera on <U2, L1, the regulator> during every load or fault test. Stop limit: <85 C>.
6. Every step lists what is connected and what must NOT be connected. A step without both is not a step.
7. Power is fed through the board's input connector, never through a test point by a hand probe or a clip. Test points are for probes. (A production fixture may feed the board through points made for that: `references/pcb-rules/dfm-dft.md` DFM-92.)
8. Connect the supply with its output off, then enable it: a hot plug rings to about twice the set voltage. The current limit does not limit the charge in the supply's own output capacitor: in every clamp and crowbar test a series resistor sits between supply and board, sized from that energy.
9. One power source per step unless the design is made for several. A debug probe that powers the board or senses its rail, a USB cable and the bench supply each count; before a second one is connected, trace what it would back-feed into the others (the bench supply, the probe, the host).

## You need
- <Bench supply with current limit, a multimeter, a scope with a 10x probe, clip leads, dummy loads: <2.2 ohm / 10 W>, a magnifier>.
- Harnesses: <list, built and pin-checked, not yet plugged in>.

## Test points (probes only, never a power feed)
From `out/testpoints.md` (written by `scripts/testpoint_check.py`, with the normal values of `[testpoints.normal]` in `board.toml`). A pad used in place of a test point has its row too.
| Name | Net | Where | Normal, running / standby |
|---|---|---|---|
| <TP1> | <5V_IN> | <top, left of J1> | <4.75 to 5.25 V / the same> |
| <TP2> | <3V3> | <top, beside U2> | <3.22 to 3.39 V / 0 V> |
| <J3 pin 2> | <SWDIO> | <top, header J3> | <logic, 3.3 V> |

## Trace table: every UNKNOWN to a test
Every UNKNOWN from the reviews and the simulations, every item no simulation covers and every accepted deviation maps to a test number below (`BT-01`, `BT-02` ..., section 7).
| Source (finding or simulation ID) | UNKNOWN item | Test number |
|---|---|---|
| <L1-MJ2> | <temperature inside the closed enclosure> | <BT-02> |
| <SIM-04 in `sim/RESULTS.md`, bench-only list> | <loop phase margin of the converter> | <BT-03> |

## 0. Known late changes (read before anything else)
Connected: meter leads only. NOT connected: any supply, harness or downstream device.
| Change | Numeric pass value | Fallback if it fails |
|---|---|---|
| <R7 changed from 10 k to 4.7 k after fix round 2; check on the board> | <R7 reads 4.7 k +/-1 %> | <replace by hand, spare in the kit> |

## 1. Look before power (magnifier, 5 min)
- [ ] Polarised parts as on the silk: <C5 +, D1 band, U1 pin 1 dot>.
- [ ] Hand-fitted parts present and oriented: <J2>. Do-not-fit parts absent: <R9, C12>.
- [ ] No solder bridges on fine pitch <U1>; no solder balls; no lifted part.
Connected: nothing, board unpowered. NOT connected: any supply, harness or downstream device.

## 2. Resistances without power (meter, black lead on ground)
| From to ground | Expected | Stop if |
|---|---|---|
| <5V_IN> | <more than 10 kohm> | <less than 100 ohm> |
| <3V3> | <more than 1 kohm> | <less than 50 ohm> |
Connected: meter leads only. NOT connected: any supply, harness or downstream device.

## 3. First power with a current limit
Connected: bench supply through the input connector, + to <J1 pin 1>, - to <J1 pin 4>, output off while connecting; meter probes on <TP2> and ground. Set <5.0 V, limit 100 mA>: above the computed start-up inrush with margin (<18 uF x 3.3 V / 1 ms soft-start = 60 mA, plus about 15 mA of start-up load = 75 mA; an LDO passes it to the input 1:1>, from the design note's rail table), and below what would harm the weakest part.
NOT connected: any load, harness or downstream device; no supply lead on a test point; no debug probe or USB cable.
A short constant-current blip at turn-on, while the capacitors charge, is expected: log it.
| Check | Expected | Result |
|---|---|---|
| Input current | <3 to 12 mA> | |
| <3V3> | <3.22 to 3.39 V> | |

## 4. Protections proven before loads
Each test must be able to trip what it tests. Use limits written here, no more. Per test, compute the energy in the supply's output capacitor and size the series resistor from it (rule 8).
| Test | Connected | NOT connected | Pass value |
|---|---|---|---|
| <Reverse polarity, 5 V, 50 mA limit> | <supply reversed on J1 through a 10 ohm series resistor, output off while connecting> | <any load or downstream device> | <input current below 5 mA> |
| <Over-voltage clamp D2: raise the supply slowly, watching TP1, until the input current passes 10 mA; stop when TP1 reaches 7.7 V (D2's breakdown maximum 7.37 V plus 0.3 V; every part on the rail is rated 8 V or more); limit 20 to 50 mA. The supply reads higher than TP1 by the drop in the series resistor and in any series diode> | <supply on J1 through a 10 ohm series resistor; probe on TP1 (5V_IN)> | <any load or downstream device; no supply on a test point> | <conduction starts (input current above 10 mA) with TP1 between 6.67 and 7.37 V, and TP1 never passes 7.7 V> |

If the clamp's breakdown maximum plus margin is not below the absolute maximum of every part on the protected rail, run the test before those parts are fitted, or, where that cannot be done, state the simulated result as support only and list the test as missing with its owner (`references/reviews.md` section 8). A reading on a regulator's output proves nothing about the clamp: measure the protected rail itself.

## 5. Harness checks with a meter
For each harness: continuity pin to pin, no shorts between pins, the voltage on each pin at the free end. Only then plug it in.
Connected: the harness on the board, meter at its free end. NOT connected: the device at the far end of the harness.
| Harness | Pin proof | Voltage at the free end | Result |
|---|---|---|---|
| <Sensor cable> | <1-1, 2-2, 3-3, 4-4> | <1 = 3.3 V> | |

## 6. Real source and loads, one at a time
| Step | Add | Connected | NOT connected | Expected |
|---|---|---|---|---|
| <6.1> | <real USB charger, no load> | <charger to J1> | <bench supply, sensor, any load> | <3V3 in range, input below 20 mA> |
| <6.2> | <sensor on J2> | <charger to J1, 4-pin cable to J2> | <bench supply, any other load> | <current rises 1 to 5 mA> |

## 7. Full bench test table
| ID | Test | Connected / NOT connected | Pass value | Result |
|---|---|---|---|---|
| <BT-01> | <3V3 unloaded> | <supply on J1 / any load> | <3.22 to 3.39 V> | |
| <BT-02> | <1 h at full load, temperature rise> | <supply on J1, dummy load on J2 / sensor> | <below 40 K> | |

## 7b. The requirements, measured
Every numbered requirement of `REQUIREMENTS.md` (section 14), measured on the real board against the value written there, before the test. Where no bench can measure it, the proof by design is named.
| ID | Requirement and pass value | Test (BT-nn) or proof by design | Measured | Result |
|---|---|---|---|---|
| <REQ-01> | <temperature within +/-0.5 C, 0 to 50 C> | <BT-05: against a reference thermometer at 3 temperatures> | <+0.3, +0.2, -0.1 C> | <PASS> |
| <REQ-04> | <lasts 5 years always on> | <by design: heat table, capacitor life calculation> | <not measurable on the bench> | <shown by design> |

## 8. Fallback
- <Rail wrong: remove the regulator's load, measure again, replace the part from the spare kit.>
- <Board dead on step 3: photograph both sides, stop, write the finding in the register, move to the next board only with the user's word.>

## Findings register
| ID | Board no. | Step | What happened | Action |
|---|---|---|---|---|
| <P-1> | <1> | <3> | <3V3 at 3.1 V> | <R7 swapped, retest> |
