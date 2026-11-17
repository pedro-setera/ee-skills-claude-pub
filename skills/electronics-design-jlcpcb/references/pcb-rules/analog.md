# PCB rules: analog and mixed-signal

Purpose: layout rules for references, sensitive nodes, guarding, ADC inputs, amplifiers and current sensing, ground strategy on mixed-signal boards, thermal gradients, sensors and shield returns.

Contents
1. Placement priority
2. References and sensitive nodes
3. Guarding and leakage
4. ADC inputs and anti-alias filters
5. Amplifiers and current sensing
6. Ground strategy for mixed-signal boards
7. Thermal gradients and sensors
8. Shields and cable returns
9. Questions for each datasheet
10. What to verify, and how; typical mistakes

Converter feedback and single-point grounds are in `power.md`; this file covers the rest of the quiet circuits.

## 1. Placement priority

1. Reference and ADC decoupling at their pins.
2. Anti-alias filters at the ADC inputs; feedback parts at amplifier inputs.
3. Shunts with their Kelvin sense tracks; matched parts side by side.
4. Sensors where the quantity they measure is, away from heat.
5. The analog area as a whole, placed so that no digital or power return current passes under it.

Why: the analog result is set by a few picofarads, microvolts and degrees at these spots.

## 2. References and sensitive nodes

Microphones, audio inputs and speaker or buzzer drives are in `emc.md` (audio section).

- ANA-01 MUST place a voltage reference's capacitors at its pins, within the capacitance and ESR range the maker gives for stability. Why: some references oscillate outside that range.
- ANA-02 MUST route a reference to its loads on its own track (Kelvin), never through a track that carries load current. Why: a few milliohms of shared copper become an offset.
- ANA-03 MUST keep high-impedance nodes (feedback dividers, timer RCs, sensor inputs, reference dividers) short and compact, with the divider's parts adjacent, away from switch nodes, clocks, power current and ESD discharge paths. Why: coupled noise on a high-impedance node becomes a false trip, a reset or an offset.
- ANA-04 MUST NOT hang a test-point stub on a high-impedance node; probe on a component pad and say so in the bring-up plan. Why: a stub is an antenna and a capacitive load on the node.
- ANA-05 SHOULD keep leakage-sensitive parts (megohm resistors, long-time RCs) away from board edges and connectors, where flux and moisture collect, and put a cleaning note in the assembly document. Why: board leakage adds to the part's own leakage.

## 3. Guarding and leakage

- ANA-10 SHOULD surround very-high-impedance inputs (sub-nanoamp currents or tens of megohms and more) with a guard ring driven at the node's own potential, on both layers, connected as the amplifier maker shows. Why: no voltage across the guard means no leakage current across it.
- ANA-11 MUST keep a guard ring continuous and connected only to its driving point; a guard tied to ground is a shield, not a guard, and must be designed as one. Why: a guard at another potential than the node drives leakage instead of stopping it.
- ANA-12 SHOULD keep solder mask on guarded areas unless the maker's guide says to open it, and keep the area free of vias. Why: mask openings collect contamination, and vias break the guard.

## 4. ADC inputs and anti-alias filters

- ANA-20 MUST place the anti-alias RC at the ADC input pin, with its capacitor's ground taken to the ADC's ground at the pin. Size the capacitor to supply the sampling charge and the resistor so the input settles within the acquisition time (use the ADC maker's application note; record the numbers in the design note). Why: the sampling capacitor kicks charge back into the input, and the filter capacitor must absorb it.
- ANA-21 MUST decouple the ADC reference pin at the pin with the maker's values and keep the reference track away from digital lines. Why: reference noise scales every conversion.
- ANA-22 MUST route a differential input as a symmetric pair, filter parts included, so both lines see the same parasitics. Why: asymmetry turns common-mode noise into a differential error.
- ANA-23 SHOULD keep fast digital lines and converter switch nodes away from ADC inputs, and check whether converter or clock frequencies alias into the measured band. Why: an aliased tone looks like a real signal.
- ANA-24 MUST set the anti-alias filter from the sampling rate fs and the measured band's top edge f_band: its corner lies between f_band and fs / 2, its gain error at f_band is counted in the error budget, and its attenuation at fs - f_band (the lowest frequency that folds back into the band) keeps the noise there below the error budget. A single RC sized for the kick-back (ANA-20) falls off at only 20 dB per decade: compute it, and add a stage or raise fs where it falls short. Record the numbers in the design note. Why: noise near fs folds into the band and cannot be told from the signal afterwards.
- ANA-25 MUST choose the ADC reference on purpose and count it in the error budget: ratiometric (the sensor and the ADC share one supply or reference, so its tolerance cancels) or absolute (a reference whose initial tolerance, drift and noise enter the budget). An absolute measurement against the analog supply carries that supply's tolerance in the budget. Why: a supply with a few percent tolerance puts that error into every absolute reading.

## 5. Amplifiers and current sensing

- ANA-30 MUST decouple every amplifier supply pin at the pin, and compute any bead or resistor filter on an analog supply as in `mcu-digital.md` MCU-04. Why: supply noise and oscillation start at an undecoupled pin.
- ANA-31 MUST place feedback parts at the inverting input, on the shortest path, to keep that node's capacitance low. For fast amplifiers, open the plane under that node only as the maker shows. Why: extra capacitance at the inverting input erodes phase margin.
- ANA-32 MUST connect a current-sense shunt with Kelvin sense: the sense tracks leave the inner edges of the shunt pads (or its sense terminals), run together as a close pair to the amplifier, and get their filter at the amplifier. Why: the shunt's pads and solder carry load current and add their own drop.
- ANA-33 MUST keep the shunt's load current out of the amplifier's and the reference's ground. Why: milliohms of shared ground become millivolts of error.

- ANA-34 MUST check that every amplifier and comparator input stays inside the input common-mode range, and every output inside its swing into the real load, at the lowest supply and at both ends of the signal. "Rail-to-rail" is read from the table, not from the title. Why: an input a few hundred millivolts outside the range clips or inverts, and a rail-to-rail output stops tens to hundreds of millivolts short of the rail under load.

## 6. Ground strategy for mixed-signal boards

- ANA-40 MUST use one solid ground plane for the whole board and partition by placement: analog parts in one area, digital parts in another, power conversion where its current never crosses the analog area. Why: a cut plane forces return currents into detours that radiate and couple.
- ANA-41 MUST NOT split the plane into separate analog and digital halves unless the chip maker's datasheet or hardware design guide asks for it expressly for that part (`general.md` GEN-64). If it does, join them at the one point the datasheet names and prove it with the cut test of `power.md` (PWR-18). Why: two ties make a loop, and none leaves one half floating.
- ANA-42 MUST connect the AGND and DGND pins of a mixed-signal chip to the same plane at the chip, as most makers ask, unless the datasheet says otherwise, and never through a ferrite or inductor (`mcu-digital.md` MCU-07). Why: the chip's grounds meet inside it; a split or a bead between its pins adds noise.
- ANA-43 MUST NOT route digital or power current under the analog area; check the return path of every digital line that passes near it. Why: return current flows under its own signal and through whatever lies there.
- ANA-44 SHOULD place an ADC or other mixed-signal chip on the boundary of the two areas, analog pins facing the analog side. Why: then no signal of one side crosses the other's area.

## 7. Thermal gradients and sensors

- ANA-50 MUST keep precision parts (references, matched resistor pairs, shunts, sensor front ends) away from heat sources: regulators, converters, power resistors, PTCs, and hot copper (any track or pour with a worksheet rise above about 10 C; `power.md` PWR-43). Why: drift with temperature, and gradients across a pair.
- ANA-51 SHOULD place matched parts side by side, in the same orientation, with the same copper around them, and keep differential inputs symmetric. Why: joints of dissimilar metals act as thermocouples (microvolts per degree); they cancel only when both ends are at the same temperature.
- ANA-52 MUST place temperature and humidity sensors as their maker's guide says: away from heat sources (hot copper included, ANA-50), exposed to the air they must measure, often with a slot or little copper around them for thermal isolation; no coating or glue over the sensor opening. Why: a sensor in the board's heat measures the board, not the air.
- ANA-53 MUST write temperature-sensitive placements (references, PTCs, sensors) and their minimum distances to heat sources into the layout requirements before placement. Why: moving them after routing costs a re-route.

## 8. Shields and cable returns

- ANA-60 MUST terminate cable shields at the connector, to chassis or ground as decided for the board (`protection-esd.md`). For low-frequency sensor cables, ground the shield at one end unless an EMC test asks for both. Why: a shield grounded at both ends with a voltage between them carries current into the signal.
- ANA-61 MUST give each analog cable signal its own return pin, adjacent to it; never share the return with a power load. Why: load current in a shared return becomes signal error.
- ANA-62 SHOULD filter analog inputs that come from cables at the connector (RC, or ferrite and capacitor), together with their ESD protection. Why: cables bring noise and ESD straight into the most sensitive inputs.

## 9. Questions for each datasheet

Write each answer, with its page, into `LAYOUT_RULES_LEDGER.md`:
- Reference: capacitance and ESR range for stability, noise, load regulation, thermal hysteresis, layout advice.
- ADC: sampling capacitance, acquisition time, recommended input RC, reference decoupling, the AGND and DGND advice; reference options with their tolerance, drift and noise.
- Amplifier: decoupling, input capacitance, stability with capacitive load, layout of the inverting input, guard connection.
- Current-sense amplifier: Kelvin layout, filter position, common-mode range.
- Sensor: placement, thermal isolation, cut-outs, exposure, protection during assembly and cleaning.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Amplifier and comparator inputs and outputs (ANA-34) | Input common-mode range and output swing at the lowest supply, from the datasheet's table, against both ends of the signal | Table in the design note |
| Reference and ADC decoupling at pins | Distance table from the board | Table, crops |
| Anti-alias filter and reference in the budget | Corner and attenuation at fs - f_band against the error budget; reference tolerance, drift and noise, or the ratiometric argument | Calculation in the design note |
| No digital or power return under the analog area | Copper plots of every layer, net highlight of nearby digital lines | Annotated plots |
| Single plane, or a proven single point | Plane plots; cut test if a split is required | Plots, cut-test report |
| Kelvin sense on shunts and references | Close-up copper crop of each shunt and reference track | Crops |
| High-impedance nodes clean | Crops of each node; check no test-point stub | Crops |
| Thermal placement | Distances from heat sources, hot copper of the worksheet included, to precision parts and sensors | Distance table, render |
| Sensor per maker's guide | Ledger line against the board; render | Ledger, render |

## Typical mistakes

- A test point on a current-limit setting pin had to go: there was no room at the pin, and a remote point would have hung a stub on a sensitive node. The bring-up plan now probes the resistor pad.
- A shunt reference rated to 85 C and the output PTCs sat near a converter; they had to move, and the distances were then written into the layout requirements.
- A long timeout built from a leaky RC and a commercial-grade timer ranged from 18 s to never over leakage, DC bias and threshold spread; long timeouts now come from a counter.
- A converter's quiet feedback ground joined the plane at three points instead of one; a cut test on a copy found it.
- Common in the field: a plane split into analog and digital halves with a digital line crossing the slit; the return detoured around the slit and coupled into the analog input.
