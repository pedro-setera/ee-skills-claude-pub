# PCB rules: heat and cooling (thermal study, copper, heat sinks, fans)

Purpose: decide for every part that gets warm how its heat leaves, with numbers, and say when a heat sink or a fan must be proposed to the user, and which size.

Contents
1. When to read this file. 2. The thermal study. 3. The cooling ladder. 4. Heat sinks. 5. Fans.
6. Air and the enclosure. 7. What a fan needs from the circuit. Then: What to verify, and how. Typical mistakes.

## 1. When to read this file

- Read it when any part loses more than about 0.5 W, when the heat table of the design note shows a part within 25 C of its limit, when the board lives in a closed or hot enclosure, or when the design has a processor, programmable logic, a radio power amplifier, a motor driver, a charger, power LEDs or a converter of more than a few watts.
- A board where no part passes about 0.1 W writes "no part above 0.1 W" in the heat table and is done with this file.
- The copper and via rules for regulators and exposed pads are in `power.md` (PWR-20 to PWR-22, PWR-62) and `general.md` (GEN-33). This file adds the study and what comes after copper.
- Numbers marked "estimate" or "starting point" are where to begin, not pass limits. Every figure of a real part comes from its datasheet (`SKILL.md` rule 18).

## 2. The thermal study

- THM-01 MUST start from the worst case of the loss, found over the whole operating envelope, not at one corner: both ends of the input range, every load and operating mode, the highest clock and activity, temperature and the tolerances that move the loss. The worst corner depends on the circuit: a linear regulator at the highest input; a boost at the lowest input and full load, where its input and switch currents are largest (I_in about I_out x V_out / (V_in x efficiency), TI SNVA731 section 3.1). For a part whose loss depends on how it is configured or programmed (programmable logic, processors, radio power amplifiers), take the figure from the maker's power estimate for this design's worst case (the maker's estimator, or the tables of the datasheet), never the "typical" of its first page. Where it cannot be estimated, write UNKNOWN with an assumed upper bound and a bench measurement. Why: the worst corner is not always the highest input, the loss of a programmable part depends on what it is made to do, and the first page shows a light case.
- THM-02 MUST use the temperature of the air at the part, not of the room: the hottest surroundings of the requirements page plus the rise inside the enclosure caused by everything in it. Estimate for a closed box without a fan: rise = total loss / (h x outer surface in free air; a face that lies on a table or against a wall does not count), with h about 5 W per square metre per degree as a starting point, radiation included: about 3.5 for plastic, about 5.5 for painted or anodised metal; a bright bare-metal surface is no better than plastic; up to about 10 only where the hot parts are bonded to a metal wall. Label it an estimate and measure it at bring-up. Why: the air in a closed box sits 10 to 30 C above the room, and the datasheet's figures assume open air.
- THM-03 MUST compute the junction temperature along the path the heat really takes and write the path down. Cooled by its board: T_junction = T_air + P x theta_JA, with a theta_JA for the copper this board gives the part (PWR-21, PWR-62), not the datasheet's test-board figure (how to get it: THM-05). Cooled by a heat sink: T_junction = T_air + P x (theta_JC + theta_interface + theta_sink-to-air). Why: the wrong path gives a comfortable number for a part that is cooking.
- THM-04 MUST hold a margin: the junction at least 15 C below its absolute maximum, and inside the recommended operating range where the maker states one (starting point). A device that must last many years always-on aims lower. The neighbours count too: electrolytic capacitors, batteries, sensors, crystals and plastic connectors have lower limits than silicon; check each one within about 10 mm of a hot part at the temperature it will see. Why: the maximum is a survival figure, not a working point; a capacitor's life roughly halves for every 10 C.
- THM-05 MUST get the theta_JA of THM-03 for this board, never from the first page: (a) from the maker's curve of theta_JA against copper area, where the datasheet has one; (b) otherwise bound it: junction to board from the datasheet (theta_JB, or theta_JC of the pad), plus board to air, which in still air cannot be lower than about 500 / A in C per watt, A being the board area the heat can spread into in square centimetres with both faces open (about 10 W per square metre per degree per face; estimate; copper farther than about 30 mm from the part adds little). A 30 x 40 mm board cannot shed 1 W for less than about 40 C of rise, whatever the copper. Label every temperature estimate as nominal, optimistic (the part can only be hotter) or conservative (it can only be cooler), with its assumptions. The bound of (b) is optimistic: a board at one temperature, both faces open, no neighbour heating it. It can only reject: if the margin of THM-04 fails even with it, copper cannot fix it and the next rung of the ladder is due now. It never passes a part: a PASS needs a conservative estimate with its uncertainty stated (for example only the copper the pad really reaches, one face, the low end of h, the neighbours' heat added), or a measurement; until then the row is UNKNOWN with a bench test. At the bench the junction is the reading on top of the case plus P x psi_JT, and only where psi_JT applies: no heat sink on the part, the datasheet's psi_JT for a board and air flow like this one (it changes with both), the reading at the centre of the top by a fine thermocouple (36 gauge or finer) or an emissivity-corrected infrared reading (TI SPRA953D section 3). Why: the heat table, the cooling ladder and the gate's question "does anything overheat?" all stand on this one number, a best case that passes proves nothing about the real case, and a figure that is not in the datasheet must not be invented.

## 3. The cooling ladder

- THM-10 MUST go up the ladder one rung at a time and stop at the first rung that meets THM-04, writing the temperature reached at each rung tried into the heat table:
  1. Lose less: a more efficient part or converter, a smaller voltage drop, a lower clock or supply.
  2. Spread it in the board: copper area, thermal vias, an inner plane (PWR-20 to PWR-22, PWR-62).
  3. Into the enclosure: a thermal pad from the part or the board to a metal wall or base.
  4. A heat sink in still air.
  5. Moving air: a fan for the enclosure, or a fan on the part's heat sink.
  Why: each rung costs more money, height and assembly work than the one below, and a fan is the only rung with a moving part: it wears out, makes noise, draws dust and needs power. But when rungs 1 to 4 do not reach the margin, propose the fan. Do not ship a part that runs at its limit in order to avoid one, and do not add a heat sink or a fan that the numbers do not ask for.
- THM-11 MUST bring the decision to the user as soon as it reaches rung 3, 4 or 5, at the block diagram (phase 2), as ONE recommended solution with its size worked out first (a heat sink by its degrees per watt, THM-20; a fan by its flow and its frame, THM-30 and THM-31). A list of options without a recommendation and a size is not a proposal. The proposal has these six lines, each with its number:
  1. Without help: `<part>` reaches about `<x>` C inside the case; its limit is `<y>` C, and we stay 15 C under it.
  2. Proposed: `<a heat sink of about <n> C per watt, <size> | a <40> x <40> x <10> mm fan for <5> V moving about <m> cubic metres per hour, on a heat sink | a thermal pad to the metal case>`, with the air coming in at `<side>` and leaving at `<side>` through openings of `<size>`.
  3. With it: about `<z>` C.
  4. It costs: `<money>`, `<height>` mm, a sound of about `<n>` dBA, and `<a fan that wears in about <years> | nothing to maintain>`.
  5. If the fan stops: `<what the device does and how the user is told>`.
  6. Otherwise: `<the alternative: a less powerful part, a larger or a metal case>`.
  Why: it changes the enclosure, the height, the sound and the price of the device; those are the user's, and they can only judge a concrete size.

## 4. Heat sinks

- THM-20 MUST size a heat sink from the resistance it needs: theta_sink-to-air at most (T_junction allowed - T_air) / P - theta_JC - theta_interface. Choose it from the sink maker's curve for the air it will really get (still air, or the speed of the fan's air), mounted the way it will be mounted: in still air the fins stand vertical. Why: a sink's catalogue figure holds for one air speed and one orientation.
- THM-21 MUST settle how the sink is held and what it touches: a clip, push pins or screws, with their holes and keep-outs on both sides of the board; adhesive thermal tape only for small, light sinks; the thermal pad or paste as a BOM line with its thickness and its resistance; the sink's height in the height zones and in the 3D model, with nothing tall in its way; and whether the metal is isolated or tied to ground, as the chip maker says (a floating sink over a fast chip radiates). A sink is usually fitted by hand after the board is tested. Why: a sink that cannot be fixed, or that touches a neighbour, is found at assembly.

## 5. Fans

- THM-30 MUST size a fan from the air it has to move: flow = 3.0 x P / dT in cubic metres per hour (1.76 x P / dT in CFM), where P is the loss to carry away in watts and dT the rise allowed for the air between inlet and outlet in C (10 C; starting point; this dT is then the enclosure rise of THM-02). Choose a fan whose free-air flow is 1.5 to 2 times that (estimate), because a fan in an enclosure delivers only part of its free-air figure; for a dense or filtered enclosure read the fan's pressure curve or measure. For a fan on a part's heat sink, take the pair from the sink maker's resistance at that fan's air speed (THM-20). Why: a fan chosen by its size alone moves a fraction of the air the calculation assumed.
- THM-31 MUST suggest a size to the user: the largest fan that fits the space, because a larger fan moves the same air more slowly, more quietly and for longer. Usual frames are 25, 30, 40, 50, 60, 80, 92 and 120 mm square, 10 to 25 mm thick, for 5 V or 12 V. Typical free-air flow, as a first guide only (estimates; the fan's datasheet decides): 25 to 30 mm, 3 to 8 cubic metres per hour; 40 mm, 8 to 17; 50 to 60 mm, 14 to 40; 80 mm, 40 to 80; 92 mm, 60 to 100; 120 mm, 80 to 170. Why: the user needs a size to judge the space, the sound and the price.
- THM-32 MUST choose the fan as a part with a limited life: the bearing and the rated life at the temperature it will see (ball or fluid bearings outlast sleeve bearings in heat and when the shaft stands vertical), the noise figure against what the user accepts, the voltage of a rail the board has, three wires (speed signal) or four (speed control) where the design watches or controls it, from an established maker. It is a BOM line and usually fitted by hand. Why: in most devices that have one, the fan is the first part to fail.
- THM-33 MUST design for the day the fan stops: the hot part shuts down or slows down safely by itself (its own thermal protection, or a temperature sensor with a comparator or the firmware), and the device tells the user (the fan's speed signal or a temperature alarm). Write into the design note what happens with the fan stopped, and test it on the bench. Why: a device that depends silently on its fan fails silently when the fan does.

## 6. Air and the enclosure

- THM-40 MUST give the air a path: an inlet and an outlet on opposite sides, each at least as large as the fan's own opening (estimate); the air passes the hot parts on its way; no short cut from the outlet back to the inlet; parts that dislike heat (sensors, electrolytic capacitors, batteries) upstream of the hot ones; no tall part shading the hot one. In still air the hot parts sit high and near the openings. In a sealed enclosure a fan only stirs the air: the heat must still leave through the walls (rung 3), and the design note says so. A dust filter costs flow and needs cleaning: the user decides. Why: a fan without a path heats its own inlet.
- THM-41 MUST put the cooling into the board definition (phase 8): the sink's outline, holes and keep-outs, the fan's place and the direction of the air, the openings the enclosure needs, the heights. Why: a heat sink or a fan found at the layout does not fit the outline that was frozen.

## 7. What a fan needs from the circuit

- THM-50 MUST treat the fan as a load and as a source of noise: its running and its start-up current, from its datasheet, in the power budget; a keyed connector with its pin table; a capacitor at the connector and a series part where the noise table asks for one; a clamp where a transistor switches it (`power.md`, section 10); speed control and speed signal wired as the fan's specification says, the speed signal pulled up to the logic rail when the fan runs from a higher one; the fan as a row of the noise table (`emc.md` section 2), kept away from microphones, sensors and radio inputs. A temperature sensor sits at the hot part, or the part's own sensor is read. What the firmware must do (the speed against the temperature, the alarm) goes into the firmware hand-over. Why: a fan is a small motor on the supply rail, and its control is part of the product's behaviour.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Worst-case loss of every hot part, with its source | The heat table against the datasheets and the maker's power estimate | Heat table rows with pages |
| Air temperature at the part | Enclosure-rise estimate; later the bench measurement | The calculation; BT number |
| Junction temperature and margin, for each rung tried | The calculation of THM-03 with the copper, the sink and the air of this design | Heat table |
| Neighbours within about 10 mm of a hot part | Their temperature limits against the estimate | List with limits |
| Heat sink: resistance, fixing, interface, height, electrical state | Sink maker's curve; `scripts/body_check.py`; the mechanical review | Curve page, report, crop |
| Fan: flow needed, fan chosen, size told to the user, life, noise | The calculation of THM-30; the fan's datasheet | Calculation, datasheet page, the user's answer |
| Air path and openings | Section drawing or picture with arrows | The picture |
| Fan stopped | Design note statement; bench test with the fan unplugged | Statement; BT number and result |
| On the real board | Thermocouple or thermal camera on the hottest parts, enclosure closed, hottest surroundings or corrected to them, the duty cycle of real use with the neighbours running (and with the fan stopped, THM-33), at least 30 minutes | Temperature log |

## Typical mistakes

- Common in the field: the junction temperature computed with the room's temperature and the datasheet's test-board figure, for a part in a closed box on a small board: the real part ran 30 C hotter.
- Common in the field: a part left at a few degrees under its maximum because "it is inside the limit".
- Common in the field: a fan added with no inlet or outlet, or blowing at a wall.
- Common in the field: a fan chosen by frame size, in an enclosure whose resistance cut its flow to a third.
- Common in the field: a device with no reaction to a stopped fan.
- Common in the field: a heat sink and a fan on a part that loses 0.3 W, because it "felt warm".
