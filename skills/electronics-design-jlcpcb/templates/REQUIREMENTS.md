# <board name>: requirements (one page)

Status: <draft | confirmed by the user on <date> (gate 0)>. Fill in plain words for a user who may not be an electronics engineer (`references/working-rules.md` section 1): everyday words, what a choice means for the device and its cost, any technical word explained the first time. If a line is unknown, write "unknown, assumed <x>" and list it in PROJECT_STATE open questions.

Picture of the device as the user will meet it (outside, lights, buttons, connectors) and a first block sketch: `<out/device_sketch.png>`.

## 0. Completeness checklist
No row stays blank. Source: user (with the date), assumed (the user sees it in section 12), or not needed (with the reason).
| Heading | Answer or assumption | Source |
|---|---|---|
| What it is for, who uses it, where and how often | <a desk sensor for office staff, always on> | <user, <date>> |
| What it must do (numbered functions, section 1) | <3 functions> | <user> |
| A day in its life, switch-on to switch-off (section 1) | <written; every function used> | <assumed, shown> |
| Every input and output, with the documents of what it connects to (sections 4 and 11) | <USB-C power, one sensor> | <user> |
| Power source (section 2) | <USB-C charger, 5 V> | <user> |
| What the person sees, hears and touches (section 3) | <one green light, no button> | <assumed, shown> |
| Size, shape, mounting, enclosure, where installed; temperature, moisture, vibration (section 5) | <40 x 30 mm, no enclosure, indoors 0 to 50 C> | <user> |
| How the board is held: screws, or slots or rails of the case (section 5) | <slides into an extruded aluminium case: 3 mm free along each guided edge, both sides, to be confirmed against the case drawing> | <assumed, shown> |
| Performance numbers: accuracy, speed, range, running time (section 6) | <temperature +/-0.5 C, every 10 s> | <user> |
| How long it must last, how hard it works, and what a failure means (section 6) | <5 years, always on; a failure means a service visit> | <user> |
| Cost target per assembled board, now and later; quantity now and later (section 7) | <good quality at the lowest cost; 5 now, 100 later> | <user> |
| Priorities when wishes conflict (section 7) | <cost, then size> | <user> |
| What it must NOT do, out of scope (section 13) | <no battery, no wireless> | <user> |
| What the user already has or prefers: parts, module, firmware, enclosure, a similar product | <none> | <not needed: nothing given> |
| Firmware, and who writes it | <the user> | <user> |
| Who assembles and tests the boards, and with which tools | <ordered fully assembled; the user has a multimeter> | <user> |
| Sale and markets (regulatory flags, section 8) | <concept run, not for sale> | <user> |
| Deadline | <none> | <not needed: none stated> |

## 1. What the device does
<Two or three lines: who uses it, where, and the one job it must do.>

Functions, in the user's words:
1. <Measure temperature and humidity every 10 s>
2. <Report over USB serial>

A day in its life: <plugged in -> light on -> reading every 10 s -> the laptop reads it -> unplugged>. Every step uses a function above.

## 2. Power source (settled before any concept)
- Runs from: <a battery | the mains through an external certified adapter | an external DC supply | a mix>.
- Battery: <kind: single lithium cell, AA or AAA, coin cell>; <rechargeable, charged by USB-C | not rechargeable>; <capacity or running time between charges>; <replaceable by the user | built in>. A lithium cell is a safety topic.
- External DC: <voltage range>; connector <USB-C 5 V | USB-C with power delivery above about 10 W | barrel jack | terminal block>; adapter supplied by <the user's customer | in the box>.
- Mains on the board: <no | yes: beyond the proven range and a safety topic>.
- Works while charging: <yes | no>. When power is lost: <stops, no data kept>. Switched on and off by: <plugging in | a slide switch | a button>.

## 3. What the person sees, hears and touches
| Item | Choice | Meaning or action |
|---|---|---|
| Lights | <one green LED> | <on = powered> |
| Buttons and switches | <none> | |
| Display | <none> | |
| Sound | <none> | |
| Plugged in or adjusted | <USB-C cable> | |

## 4. Inputs and outputs
| Interface | Direction | Level or rating | Connector | Note |
|---|---|---|---|---|
| <USB-C power> | in | <5 V, 0.5 A max> | <USB-C receptacle> | <no data lines used> |
| <Sensor bus> | in/out | <3.3 V I2C> | <on board> | <address 0x44> |

Power sources:
| Source | Voltage range | Current | Fault to survive |
|---|---|---|---|
| <USB charger> | <4.5 to 5.5 V> | <0.5 A> | <reverse plug, 20 V charger, hot plug> |

## 5. Environment, size, enclosure
- Temperature: <0 to 50 C>. Humidity: <non-condensing>. Vibration: <none>. Installed: <on a desk>.
- Board size: <40 x 30 mm>, layers wished: <2>. Enclosure: <none | drawing at path>. Mounting holes: <4 x M3>.
- Held by: <screws | slots or rails of the case along <edges>: a free strip along each guided edge, both sides, from the case drawing (3 mm assumed until then)>.
- Connector edges and cable directions: <USB-C at the left edge>.

## 6. Performance numbers
| Quantity | Value | Source |
|---|---|---|
| <Running time per charge> | <not needed: mains powered> | |
| <Temperature accuracy> | <+/-0.5 C> | <user> |

Reliability expectation:
- Expected life: <5 years>. Use: <always on | <n> hours a day | a few times a year>.
- A failure means: <an annoyance | a cost: a service visit, a lost day | a danger to people or property: a safety topic, say so>.
- When it fails it is: <replaced whole | repaired: which parts must be reachable and replaceable>.
- What wears out or ages in such a device (electrolytic capacitors, relays, connectors, fans, batteries, flash memory): <the user's expectation, or "typical for such devices" as an assumption>.

## 7. Cost, quantity, priorities
- Cost target per assembled board: <x at 5, y at 100 | good quality at the lowest cost | mid-range | performance first> (`references/working-rules.md` section 11: quality first, then cost).
- If quality and this target cannot both be met, the agent does not lower quality quietly: it tells the user in plain words with the options (a higher cost, fewer features, or a named limitation they accept), and the user decides.
- Quantity: <5 samples, 2 assembled>; later <100>. Concept run: <yes | no>. Later boards programmed and tested: <by hand | on a spring-pin fixture | not decided>.
- Ranking when wishes conflict: <1 cost, 2 size, 3 running time, 4 features>.

## 8. Rules and markets
- Sale and markets: <none | where>. Regulatory flags: <none | radio | mains | lithium | safety label | export>. Not certified by this skill; note what the user must do.

## 9. Complexity rating against the skill's proven range
Proven: up to 6 layers, microcontrollers, analog, power, sensors, USB 2.0, simple 50 ohm RF.
| Item | Value | Inside the range? |
|---|---|---|
| Layers | <2> | <yes> |
| Fastest signal | <I2C 400 kHz> | <yes> |
| Highest voltage | <5 V> | <yes> |
Rating: <inside | beyond: say so, continue only as experimental with a human engineer's review>.

## 10. Process agreed with the user
- Review depth, decided from the facts and shown with this page: <lean | lean plus <the extra reviews> | the full set>. Facts: <no radio, no converter, 12 V, 0.5 A, 5 boards, own use>. Overruled by the user: <no | date, their words>.
- Gates agreed: schematic, PCB, payment; nothing passes one without the user's approval. Asked in this round, or in phase 0 on a late entry; recorded in PROJECT_STATE decisions.
- Notification events agreed, from one list: <a gate is ready; a payment is waiting; the manufacturer asks something or needs a confirmation; the order's main status changes; the boards ship>. Channel: <push | none>.
- Order and mailbox watch: asked once, in phase 14.

## 11. External-interface checklist
Every interface that leaves the board. No row may stay empty before phase 2 ends.
| Interface | Power | Part (maker number) | Drawing | Mechanical space |
|---|---|---|---|---|
| <Sensor cable> | <3.3 V, 5 mA from board> | <JST XH 4-pin, C-number> | <maker drawing path> | <plug 12 mm high, cable exits up> |
| <Antenna, if any> | <bias current, DC block present?> | <part> | <drawing> | <clearance> |

Also list: level shifts between separately powered parts, and who supplies each cable.

## 12. Assumptions the user has seen
| Assumption | Why | Confirmed |
|---|---|---|
| <Indoors only, 0 to 50 C> | <a desk device> | <yes, <date>> |

## 13. Out of scope
- <What the device will not do in this revision.>

## 14. The requirements, numbered
Every statement above that must be true of the finished device, as one testable line with its number or condition. These numbers are followed to the end: the gate summaries show where each one is met and how it was verified, and the bring-up measures each one on the real board.
| ID | Requirement | From section |
|---|---|---|
| <REQ-01> | <Measures temperature every 10 s, within +/-0.5 C between 0 and 50 C> | <1, 6> |
| <REQ-02> | <Survives a reversed supply and a 20 V charger without damage> | <4> |
| <REQ-03> | <Fits the case: 40 x 30 mm, parts at most 8 mm high> | <5> |
| <REQ-04> | <Lasts 5 years always on> | <6> |
