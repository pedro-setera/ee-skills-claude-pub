# PCB rules: RF

Purpose: layout rules for simple 50 ohm RF paths on JLCPCB standard stacks: lines, grounding, connectors, DC blocks and bias tees, matching, antennas, modules, shielding, keeping switching noise out of receive bands, and filters (choosing, simulating and laying them out).

Contents
1. Placement priority
2. Stack and line geometry
3. Ground and via fences
4. Connectors and cable landings
5. DC blocks and bias tees
6. Matching pads
7. Antennas and keep-outs
8. Modules from the maker's guide
9. Shielding provisions
10. Keeping switching noise out of receive bands
11. Questions for each datasheet
12. Filters
13. What to verify, and how; typical mistakes

Version 1's proven range is simple 50 ohm RF up to a few GHz: lines, connectors, bias tees, matching, modules, ready filter parts and filters of discrete inductors and capacitors (section 12). Above about 2.5 GHz compute the line loss (RF-07). Filters made of copper, couplers, power amplifiers and anything above about 6 GHz are outside it: say so in phase 1. The board-wide source-and-victim table, zones and cables are in `emc.md`; its antenna rules (EMC-40 to EMC-45) and section 7 here say the same.

## 1. Placement priority

1. RF connectors and antennas at the positions the enclosure fixes.
2. The RF path as one short, straight line: connector, protection, DC block, matching, RF part.
3. The bias-tee choke and its cold-end capacitor at the line.
4. The RF part's decoupling at its pins, with a band bypass at every supply and bias node (RF-85).
5. Fence and stitching vias, planned before anything else is routed nearby.
6. Noise sources (converters, inductors, clocks) as far from the RF path and the antenna as the board allows.

Why: every millimetre of RF line and every gap in its ground costs loss or match; the rest of the board can move.

## 2. Stack and line geometry

- RF-01 MUST take the 50 ohm geometry from the fabricator's impedance calculator for the chosen standard stack (see `references/jlcpcb/capabilities.md`), with copper thickness and solder mask. Cross-check with a second method and record both. Why: one grounded coplanar line on a 2-layer board was computed once without copper thickness and once with a thickness correction that was too strong; the two results lay about 15 % apart, and two later calculations (closed form, and a field solution) fell between them. The line was inside 50 ohm +-10 % either way, and one method alone would not have shown the difference.
- RF-02 SHOULD use grounded coplanar waveguide on 2-layer boards, so the line stays narrow enough for 0402 parts; on 4 layers a line over the layer-2 plane is narrow and simple. Expect about +-10 % from fabrication. Why: a 50 ohm microstrip on 1.6 mm FR-4 is about 3 mm wide, far wider than the pads it must meet.
- RF-03 MUST keep the width constant along the line and keep pads close to the line width. Where a part's pad or pin is much wider than the line, calculate a ground cut-out under it, or taper the line to it rather than step it, with an estimate of the transition. Why: every width step is a reflection, and a gradual change reflects less.
- RF-04 MUST use mitred or curved corners, never sharp right angles, and record the line length as a fraction of the wavelength. Why: a sharp corner adds capacitance, and the length tells whether the line matters at all.
- RF-05 MUST decide per RF line, microstrip or grounded coplanar, and make the copper match: a coplanar line gets exactly its calculated gap; a microstrip keeps every same-layer pour, track and foreign pad at least 3 line widths away (more than a zone's default clearance). The distance to the edge of the reference plane and to the board outline follows `general.md` GEN-08. Never let a fill decide the type. Why: on a coplanar line the pour edge is part of the line, and pour edges near a microstrip lower its impedance.
- RF-06 SHOULD decide whether to order controlled-impedance fabrication only for lines longer than about a tenth of a wavelength; short lines on a prototype rarely need the paid option. If ordered, mark the lines as in `usb.md` USB-51 (a width of their own; layer, width, gap and target in the remark). Why: below about a tenth of a wavelength a small impedance error costs almost nothing.
- RF-07 MUST record the stack's dielectric constant and loss tangent at the operating frequency. Above about 2.5 GHz on standard FR-4 (estimate), compute each RF line's insertion loss and keep lines short; above about 6 GHz, or when the budget needs low-loss material, the board is outside the proven range. Why: FR-4 loss grows with frequency and can eat the link margin.
- RF-08 MUST list every stub on an RF line (bias tap, unfitted shunt or ESD pads, test pads) with its electrical length at every band and harmonic present, treat it as a shunt capacitance (open) or inductance (shorted), and keep it far below a quarter wavelength at the highest. Why: a stub harmless at one band can sit near a quarter wavelength at another or at a harmonic.

## 3. Ground and via fences

- RF-10 MUST keep solid, unbroken ground under the whole RF path; no other signal under or beside it on any layer. Why: the return flows right under the line; a gap or a crossing forces it around.
- RF-11 MUST stitch the coplanar grounds to the reference plane with a fence of vias on both sides, at most the smaller of lambda_g / 20 and about 10 drill diameters apart (3 mm for a 0.3 mm drill; starting point), toward 4 diameters near transitions and above about 3 GHz, each via about one drill diameter back from the pour edge facing the line. lambda_g = c / (f * sqrt(eps_eff)); on FR-4 at 2.4 GHz it is about 65 mm. One proven board kept every point of the line within 3 mm of a ground via (well inside lambda_g / 20 at its frequency). Why: widely spaced vias let the side grounds resonate and the line radiate.
- RF-12 MUST put ground vias on both sides of every transition: connector launch, part pads, cable landing. Why: the return current crowds at every discontinuity.
- RF-13 MUST count fence and stitching vias after every rebuild against the planned count (`scripts/zone_check.py`). Why: a refill, a text keep-out or a clearance change removes vias silently.
- RF-14 MUST give every RF part's ground pad its own via at the pad, and each RF shunt ground (matching shunt, ESD diode, bypass, connector legs) 2 or more vias on a 2-layer 1.6 mm board. Count via inductance in matching and resonance estimates (`general.md` GEN-30: about 1.3 nH through 1.6 mm, 0.1 nH to a plane 0.2 mm below). Keep an RF line on one layer; a layer change needs its via estimated (L and C) and a ring of ground vias. Why: a shared or distant via adds inductance in series with the part, and 1.3 nH is about 20 ohm at 2.4 GHz.
- RF-15 MUST stitch every ground pour on every layer of an RF board to the reference plane on a grid no coarser than lambda_g / 20 at the highest RF frequency (about 3.3 mm at 2.4 GHz), with a row along the board edges and around each RF section, counted by `scripts/zone_check.py`. Why: a quarter wavelength on FR-4 is only about 17 mm at 2.4 GHz, so most boards are electrically large.

## 4. Connectors and cable landings

- RF-20 MUST take the connector footprint and the recommended board launch (centre pad, ground clearance, leg pads, vias) from the maker's drawing. Why: the launch is tuned together with the connector; a generic footprint mismatches it.
- RF-21 MUST compute the launch: centre-pad width and its gap to ground set its impedance; the line leaves the pin pad straight back. Why: the pin pad is usually the worst mismatch on the path.
- RF-22 MUST check an edge-launch connector's leg gap against the board thickness and its tolerance (take the tolerance from `references/jlcpcb/capabilities.md`), and test-fit one part before soldering a batch. Why: the legs clamp the board; a thick board does not fit and a thin one tilts the connector.
- RF-23 MUST write a thread budget for a panel connector from its drawing: flange, wall, washer, nut and the mating plug's engagement; state the maximum panel thickness it allows. Why: a short thread leaves the antenna plug half engaged.
- RF-24 MUST land a soldered coax on a ground pad full of vias for the shield, a short dielectric gap, and a centre pad at line width; check the cable's minimum bend radius against the route in 3D. Why: a cable bent tighter than its radius changes impedance or breaks.
- RF-25 MUST treat hand-soldered RF connectors as hand-fit parts: no paste, out of the assembler's files, room for the iron (`dfm-dft.md`). Why: the assembler does not fit them, and the iron needs space.
- RF-26 MUST treat the centre pin of a through-hole or vertical connector as a via: launch on the layer the maker shows, keep the maker's ground clearance around the pin on every layer, and ring the pin with ground vias. Why: the pin's barrel is a stub and a discontinuity at GHz.
- RF-27 SHOULD give an RF board a defined DC entry (a connector, or a supply pad with its ground pad beside it) with a band bypass, a broadband bypass, and a ferrite or choke where the feed enters the RF area; bench leads land only there, and RF is measured only through the coax connectors (phase 15). Why: bench leads become antennas and a second ground path.

## 5. DC blocks and bias tees

- RF-30 MUST choose the DC-block capacitor by its impedance in the band from the maker's S-parameter data (series resonance near the band is ideal), C0G, small case; place it in line with no stub. Why: at GHz a capacitor's impedance is set by its parasitic inductance, not its value.
- RF-31 MUST choose the choke by its impedance in the band (far above 50 ohm, typically hundreds of ohms): for a narrow band a self-resonance inside the band blocks best; for a wide or multi-band path, put it just above the top band and check several hundred ohms over every band, the lowest included. Use the maker's land pattern (smaller pads, less capacitance); tap the line with the shortest stub. Why: a choke above its self-resonance acts as a capacitor, and a long stub resonates.
- RF-32 MUST place the choke's cold-end capacitor right at the choke, with its ground via AT the capacitor's ground pad. Why: on a fast ESD edge the choke and that via's inductance form a divider; with the via a millimetre away, an IC behind it saw more than its rating for nanoseconds.
- RF-33 MUST protect the DC feed: a current limiter whose MINIMUM limit exceeds the worst load current (bound an unmeasured antenna from vendor data and measure it on the bench), filtering so RF does not reach the feed, and an ESD analysis at the nanosecond scale (`protection-esd.md`). Why: a limiter below the antenna's current starves it, and RF on the feed detunes the path.
- RF-34 MUST check the DC voltage at the remote load over cable length and rail tolerance, and publish the supported cable range. Why: a remote amplifier below its minimum supply loses gain.

## 6. Matching pads

- RF-40 SHOULD put a pi or L matching footprint between an RF connector and the RF part: series part fitted (0 ohm or the reference value), shunt parts unfitted, all on the line without stubs, shunt grounds through vias at the pads. An antenna feed always gets its pi network (RF-52). Why: matching is tuned on the bench without a respin.
- RF-41 MUST start from the RF part's reference matching network and values when the maker gives them. Why: it is the measured starting point; bench tuning moves from there.

## 7. Antennas and keep-outs

- RF-50 MUST place a chip, trace or module antenna exactly as the maker's guide says (position on the board edge or corner, minimum ground plane size) and follow the maker's antenna keep-out exactly: no copper on any layer, no parts, no tracks (above all no power or switching tracks), no screws, battery or other metal. Why: copper, ground or metal in the wrong place detunes the antenna and shadows its pattern, and a switching track there couples straight into the receiver.
- RF-51 MUST check the keep-out of RF-50 as a volume in 3D with the enclosure, cables and tall parts included (`scripts/body_check.py` and renders). Why: screws, batteries and enclosure parts enter the keep-out from above or below, where a 2D check does not look.
- RF-52 MUST give every antenna feed a three-part matching network footprint, shunt, series, shunt (a pi network), right at the antenna: fitted at first with the maker's values, or, where the maker gives none, a series zero-ohm part with both shunts unfitted; tuned on the bench in the real enclosure. Each shunt pad has its own ground via beside it. Why: the enclosure, the ground plane and nearby parts shift the antenna's resonance, and only a footprint already on the board lets it be tuned without a respin.

## 8. Modules from the maker's guide

- RF-87 MUST decide a shield can for every radio block that is not an already shielded module, by `emc.md` section 10, and keep the can's walls and lid clear of RF lines, inductors and the antenna as that section says. Why: a receiver beside a converter or a processor loses sensitivity that no later filter gives back.
- RF-60 MUST follow the module maker's hardware design guide: land pattern, ground vias under the module, RF pin routing, keep-outs, decoupling and the supply's peak current. Put the guide's figures in the ledger. A certified radio module keeps the module maker's antenna layout unchanged (antenna or antenna connector, feed, matching, keep-out), or its certification no longer covers the product. Why: the module's performance and certification assume that layout.
- RF-61 MUST NOT route under a module's RF section or antenna unless the guide allows it. Why: a track there couples straight into the receiver or the antenna.

## 9. Shielding provisions

- RF-70 SHOULD add a shield-can frame footprint (a ground ring with dense vias) around a sensitive receiver or a noisy converter where the decision of RF-87 and `emc.md` EMC-72 is "footprint only"; the can can stay unfitted on samples and be fitted if a test asks for it. Why: a can added later needs its footprint on the board already.
- RF-71 SHOULD keep a ground ring with dense vias around sensitive RF sections even without a can. Why: the ring stops surface currents from carrying noise into the section.

## 10. Keeping switching noise out of receive bands

- RF-80 MUST list the receive bands and the noise sources (converter edges and harmonics, clocks, buses, display links) and write which harmonics or edges fall in band. A converter's switching frequency is far below GHz, but its fast edges are not. Why: a noise source that is not named is not kept away.
- RF-81 MUST keep converters, inductors and clocks away from the RF path, the antenna and RF cables, and keep converter hot loops small (`power.md`). Why: distance is the cheapest filter.
- RF-82 MUST place bypass capacitors chosen by mounted self-resonance in the victim band at every cable exit near the RF part or antenna, each with its own ground via. Compute the resonance with the maker's ESL plus pads, track and via (a 10 pF C0G 0402 that resonates near 2.2 GHz alone falls to about 1.2 GHz through one via of a 1.6 mm board; estimate): use 2 or more vias, a smaller value or a plane close below. One part covers a narrow window (roughly +-6 %; estimate): for a wide band or several bands fit one part per band or staggered values, and simulate them with the larger capacitor so no parallel peak lands in a victim band (`power.md` PWR-38). Choose ferrites by their impedance at the band. Why: a part chosen at low frequency does nothing in the band, and the via can set the resonance.
- RF-83 MUST treat every cable as an antenna: pair power with its return in the connector; reduce noise at its source first, and add common-mode filtering at the exit only when a test calls for it. Why: a cable radiates whatever current its return pin does not carry.
- RF-84 MUST agree with the user a baseline and an acceptance threshold for receiver degradation (for example carrier-to-noise or noise floor) and test with the real receiver and antenna in the real enclosure: board off, light load, full load. Never invent an "allowed dB". Why: only the user's application sets how much degradation is acceptable.
- RF-85 MUST give every supply and bias node of an RF stage (supply pins, bias-resistor tops, choke cold ends, control pins next to the RF path) at least one capacitor whose mounted self-resonance lies in the band, at the pin with its own ground via, besides the maker's low-frequency values; record value and resonance per node. Why: a capacitor that resonates below the band is an inductor in the band.
- RF-86 MUST feed each RF stage (amplifier, mixer, oscillator or synthesiser supply group) by its own short branch from a common decoupled node, its band bypass at the stage pin, plus a choke or ferrite chosen by impedance in the band where isolation matters; never chain stages along one supply track. Why: a shared feed couples the stages and can cause gain ripple or oscillation.

## 11. Questions for each datasheet

Write each answer, with its page, into `LAYOUT_RULES_LEDGER.md`:
- RF part: port impedance, reference layout and matching, DC allowed on the RF pin, ESD rating per pin (HBM and CDM: handling ratings only, `protection-esd.md` ESD-23).
- Connector: launch footprint, return loss versus frequency, board thickness range, thread length.
- Capacitors and inductors: S-parameters, self-resonance, current rating at temperature.
- Filter part: its S-parameter file, the impedance it expects at each port, its reference layout and matching parts, its power rating, its loss and rejection over temperature.
- Antenna or module: keep-out size, ground plane size, placement examples, matching values, enclosure effects, supply peaks; for a certified module, the antenna layouts its certification covers.
- Fabricator stack: dielectric constant and loss tangent at the operating frequency, thickness per layer, finished copper, mask thickness.

## 12. Filters

- RF-90 MUST write the filter's specification as a table before choosing anything: the band to pass, with the loss and ripple allowed in it; each frequency to reject, with its attenuation in dB and where that number comes from (the level of the interferer against what the next stage stands); source and load impedance; the power it must stand; group delay only where the signal needs it. Why: a filter without numbers cannot be judged, and "as much as possible" buys a part that is too large, too lossy or too dear.
- RF-91 MUST look for a ready filter part first (a SAW, BAW or ceramic filter of an established maker) and take it when one meets the table: simulated with the maker's own measured S-parameter file, matched and laid out exactly as the maker's reference shows. A filter of discrete inductors and capacitors is built only where no part fits, or at low frequencies where it is the simple and cheap way. A filter drawn in copper is outside the proven range. Why: at hundreds of megahertz and above, a ready part gives a response that a handful of small parts on FR-4 cannot match, and it is one BOM line with a guaranteed curve instead of five with tolerances.
- RF-92 MUST say which level of evidence the filter has reached, in the simulation results and at the gate. Level 1, ideal parts: the result of the synthesis; never evidence by itself. Level 2, real parts: every inductor and capacitor with its maker's model or its datasheet figures (RF-94), the pads, each ground via with its inductance (`general.md` GEN-30), the track pieces between the parts as lines, and a tolerance run. Level 3, measured: the board on a network analyser. Level 2 is required for every filter before gate 1. Where one via's inductance is more than a few percent of the filter's own inductors (as a rule above about 300 MHz; estimate), level 2 is still not proof: the response is UNKNOWN until level 3, with its bench test and its tuning positions (RF-96). Why: the same five values are three different filters as ideal parts, as real parts and on a real board; at 2.4 GHz a 1.3 nH coil is mostly its pads and vias.
- RF-93 MUST compute the response by script, in two independent ways, and plot both against the table as a mask: (a) the cascade of the parts' S-parameters or chain matrices in Python (numpy; `scikit-rf` reads the makers' Touchstone files and cascades them, where it is installed); (b) an AC analysis of the same circuit in ngspice with the parts' equivalent circuits. Where the two differ by more than 0.5 dB in the pass band or 3 dB in the stop band (starting points), find out why before going on. A discrete filter's values come from the standard prototypes (Butterworth, Chebyshev, elliptic: SciPy, or the closed-form tables), are then rounded to values that can be bought, and the rounded circuit is the one that is simulated. No graphical tool is needed and none is used. Why: a transfer function is not a circuit, and one tool's curve has no check.
- RF-94 MUST take every part model from its maker (S-parameter or SPICE files, fetched in phase 4 into `vendor/models/`) and name the file in the results. A part without one gets a model from its datasheet figures (self-resonant frequency; Q or series resistance at a stated frequency), labelled as such; never a model from memory (`SKILL.md` rule 18). Choose inductors by their Q and self-resonance at the band (self-resonance at least about 3 times the highest frequency to pass; estimate) and capacitors in C0G. Why: the part's own resonance and loss set the insertion loss and the skirts.
- RF-95 MUST lay a discrete filter out as one straight chain: input and output at opposite ends; neighbouring inductors at right angles, never side by side; every shunt part with its own ground via right at its pad, never one via shared with its neighbour; unbroken ground under the whole filter; no other track through or under it; a shield can where the table asks for more than about 50 dB of rejection (estimate; `emc.md` section 10). A ready filter part follows its maker's drawing, its ground pads and the distance between its input and output lines included. Why: coupling between coils and a shared ground via carry the stop band round the filter.
- RF-96 MUST make the filter measurable and tunable: a way to connect a network analyser at its input and at its output (a small coaxial test connector footprint, or pads for a soldered coaxial cable, each behind a 0 ohm link that cuts the chain; stub lengths by RF-08), and unfitted positions where tuning is expected (`dfm-dft.md` DFM-101). Its bench test measures the loss in the pass band and the rejection at each frequency of the table. Why: a filter that cannot be measured stays UNKNOWN for the life of the product.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Filter: specification, ready part considered, level of evidence (RF-90 to RF-92) | The table; the search for a ready part with the reason for the choice; the level stated in the simulation results | Table, decision row, results page |
| Filter response, two ways, with tolerances (RF-93, RF-94) | The Python cascade and the ngspice run against the mask; the tolerance run; every model named with its file | Plots, model list |
| Filter layout and test access (RF-95, RF-96) | Crops of the chain, the ground vias and the test positions; on the real board a network analyser | Crops; bench test number and result |
| Line impedance | Fabricator calculator plus a second method, with copper and mask; `scripts/impedance_check.py` on the widths, gaps and layers that are on the board | Calculation record, `out/impedance_check.md` |
| Fence and transition vias | `scripts/zone_check.py`: fence count, nearest via to each RF pad, stitching grid of every pour | Report, crops |
| Band bypass per supply and bias node; feed per stage | Table: node, value, mounted resonance, window; supply-branch crops | Table, crops |
| Line type and stubs | Pour distance per microstrip; stub list with electrical length per band and harmonic | Crops, list |
| Ground under the RF path | Copper plots of every layer along the path | Annotated plots |
| Launch and cable landing | Close-up crops; launch impedance estimate | Crops, estimate |
| Antenna keep-out | Copper plots of all layers (no copper, parts or tracks); 3D with enclosure, screws and battery | Plots, renders |
| Antenna matching | Pi network footprint (shunt, series, shunt) at the antenna; fitted values or the zero-ohm start; a ground via beside each shunt pad | Crops, BOM lines |
| ESD into the RF part | Nanosecond simulation with via inductance (`references/simulation.md`) | Plot, peak voltage and duration |
| Noise in the band | Bench plan with the real receiver: off, light, full load | Test plan, then results |

## Typical mistakes

- A line computed without copper thickness, and again with a thickness correction that was too strong, gave two results about 15 % apart; a second method fell between them. Always include copper and mask, and always compute a second way (`scripts/impedance_check.py`).
- The nearest ground via to a coax landing's centre pad was several millimetres away, a break in the RF return. Two vias were added beside the pad.
- A rebuild placed only part of the planned fence and stitching vias, because text keep-outs used KiCad's large text frame. Vias are now counted after every rebuild.
- An ESD analysis of a choke-fed input computed only the slow charge sharing and concluded the IC was safe; a nanosecond simulation showed about 10 V for 2.4 ns on a 6 V part. The cold-end capacitor's via moved onto its pad.
- A current limiter's minimum limit was never compared with the remote load's current, which nobody had measured; a part with a higher minimum replaced it.
- 1 nF bypass capacitors at cable exits self-resonated near 200 MHz and did nothing in the receive band; small C0G parts resonant in the band were added beside them.
- Common in the field: a dozen bypass values at an RF supply pin, all resonating below the band, changed nothing; one part resonant in the band fixed it.
- Common in the field: ground poured beside microstrip lines made them unmodelled coplanar lines and pushed an amplifier out of range; clearing it to over three line widths restored it.
- Common in the field: a filter taken from a calculator's ideal curve: on the board it passed several dB less and rejected 20 dB less than the curve.
- Common in the field: five small parts where one ready filter part did the job better and cheaper.
- Common in the field: two neighbouring inductors side by side, or two shunt parts on one ground via: the stop band went round the filter.
