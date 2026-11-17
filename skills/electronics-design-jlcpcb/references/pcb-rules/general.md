# PCB rules: general

Purpose: the method, words, worksheet and checklists that apply to every board; read this file before any circuit-type file.

Contents
1. How to use this rule base. 2. Requirement words, severities and results. 3. Mandatory order of work.
4. Return paths. 5. Copper fill. 6. Current, voltage-drop and heating worksheet. 7. High-current vias.
8. Impedance control: where it applies and where it does not. 9. KiCad specifics.
10. Acceptance checklist skeleton. 11. Required outputs of a layout review. 12. Release states.
Then: What to verify, and how. Typical mistakes. Background reading.

## 1. How to use this rule base

- Read `thermal.md` when a part runs warm (its first section says when): the thermal study and the steps after copper, up to a heat sink or a fan.
- Read this file and `emc.md`, the cross-cutting EMC file read for every board (source-and-victim table, zones, antennas, audio parts, cables, compliance), then the file of every circuit type on the board: `power.md`, `mcu-digital.md`, `usb.md`, `rf.md`, `analog.md`, `protection-esd.md`, `connectors-mechanical.md`, `silkscreen.md`, `dfm-dft.md`.
- These files say what to do per circuit type, what to verify and how. They never replace a datasheet. Component rules come from each part's datasheet, layout guide and evaluation board, and go into the project's `LAYOUT_RULES_LEDGER.md` (phase 4) with the page and how each will be checked. Each circuit-type file lists the questions to ask of every datasheet; write the answers into the ledger.
- Order of authority: the part's datasheet and the fabricator's current capabilities, then this rule base, then habits and internet tables. When a datasheet overrides a rule here, write the reason in the ledger.
- A number marked "starting point" is where to begin, not a pass limit. Pass limits come from a calculation, a datasheet or the user's requirement, written before the check runs.
- Fabricator facts (track, space, drill, ring, mask web, silkscreen, copper to edge, stacks) are not fixed here: take them from JLCPCB's current capabilities page (see `references/jlcpcb/capabilities.md`). A number given "as read in 2026-11" is re-checked before an order.
- Before a review, collect: native board, schematic and rule files; footprints and 3D models; the BOM with maker part numbers; the enclosure or a dimensioned drawing; the fabricator's stack and finished copper; the assembler's rules; the load budget (continuous, peak, start-up, fault, and the voltage each load needs at its own pins). With only a schematic PDF, run a pre-layout requirements review and say so; never report "PCB passed".
- When the user brings an external review standard, give every one of its rules an owner (layout, electrical, visual, mechanical fit, bench) and a status with evidence; write each deviation with its reason. Why: a rule with no owner is never checked.

## 2. Requirement words, severities and results

| Word | Meaning | If not met |
|---|---|---|
| MUST | Required for acceptance | FAIL, or a written waiver from the user |
| SHOULD | Preferred practice | Write the trade-off and show it is equivalent |
| MAY | Allowed option, no preference | Nothing |

| Severity | Meaning | Effect on the gate |
|---|---|---|
| Blocker | Will not work, damages itself or its loads, or cannot be built | Gate closed until fixed or waived by the user |
| Major | Works badly, fails at a corner, or costly to fix later | As `references/reviews.md` section 5: fixed in the fix round, or put to the user at the gate as a named risk with its bench test |
| Minor | Quality, serviceability, looks; low risk | Fix if cheap, otherwise record it |

- A note is an observation, not a defect (`references/reviews.md`). Every rule ends PASS, FAIL, UNKNOWN or WAIVED, with evidence: a file, a measured value or an image crop. UNKNOWN is never PASS: write what is missing and who can supply it (inferred passes hid the worst defects on record). A check that cannot run is FAIL "cannot run", never skipped.
- WAIVED needs the user's words in the state file, the exact item, its impact and a crop. A blanket "known issue" is not a waiver.

Quality first, then cost (`references/working-rules.md` section 11):
- A MUST rule stands, always.
- A SHOULD rule is followed by default: these practices are what make a circuit stable and dependable. It is set aside only when it brings nothing for this product (the reason is written in the design note), never because it costs. When in doubt, keep the footprint.
- Cost is won only where nothing is lost: the cheaper of two equally good and equally dependable parts or methods; no specification beyond the requirement plus its proper margin; free measures first (placement, zoning, short loops, edge rates, routing order); an unfitted footprint where the need is uncertain.

Just enough, and simple (`references/working-rules.md` section 12):
- The simplest layout and the fewest parts, layers, vias and special processes that still meet every MUST and the SHOULDs that apply.
- Margins as the usual margins table of `references/phases/03-parts.md` gives them: not less, and not much more without a written reason.
- Every measure answers a named source, victim or fault of this board.
- Simplicity never removes a required margin, protection or check.

## 3. Mandatory order of work

Work and review in this order. A later step never repairs an earlier one.

| Step | Content | Why in this place |
|---|---|---|
| 1 Electrical feasibility | Power budget, voltage at each load, contact currents, fault energy | Layout cannot fix a wrong budget |
| 2 Mechanical | Outline, holes, keep-outs, connectors locked to the enclosure | Routing on a moving outline is thrown away |
| 3 Critical placement | Hot loops, protection at connectors, feedback, crystals, RF, decoupling, by the ledger | Local parasitics decide whether it works |
| 4 Power and return routing | Continuous and pulse currents, loop inductance, necks, heat paths | Width and returns set heat and drop |
| 5 Sensitive signals | Feedback, references, clocks, buses, CC, RF | They must avoid what steps 3 and 4 made noisy |
| 6 Planes and noise | Refill, islands, cuts, return paths, emissions into victim bands | The fill hides and creates defects |
| 7 Manufacturing | DRC, fabricator and assembler rules on the exported files | The factory builds the exports |
| 8 Evidence | Worksheets, images, crops, reports, bench list | No evidence, no pass |

- When two needs collide: electrical wins over mechanical, mechanical over silkscreen. Ask the user only when a cosmetic need would cost an electrical constraint.
- One clean DRC is not a review. DRC cannot prove power integrity, stability, pin-out, current capacity, heat or fit.

## 4. Return paths

- GEN-19 MUST name the fast and sensitive nets before routing (clocks, USB and other pairs, memory and bus lines with fast edges, RF lines, feedback and sensor lines; the list `[fast_nets]` in `board.toml`) and prove each one's return path after it: for the whole run the neighbouring reference layer has unbroken ground copper under the track (no gap, slot, merged via clearances or plane edge), and every via where the net changes its reference has a ground via beside it. Measure it with `scripts/return_path_check.py` (length of each net over a gap, distance from each layer change to the nearest ground via) and look at the overlay image of each plane layer with these nets drawn on it. A board with no such net says so in the ledger. Why: a plane that looks solid at arm's length can be cut under exactly the net that needs it, by a row of vias, a fan-out or a neighbouring pour; a routed, rule-clean board shows nothing of it.
- GEN-01 MUST trace the outgoing AND the returning current of every power net and every signal that matters. Why: a wide supply track with a narrow or detoured return is not a high-current path.
- GEN-02 MUST keep a continuous reference plane under sensitive and fast signals. At an unavoidable gap crossing: both sides ground, bridge with copper or ground vias; different nets, a stitching capacitor sized by impedance beside the crossing, about 1 nF in a small package with its own vias, mounted inductance about 1 nH or less for a 1 ns edge (starting point); for faster edges and clocks, re-route. Why: a distant return makes a loop antenna, and a large or distant capacitor does nothing.
- GEN-03 MUST know each routing layer's reference. Default 4-layer plan: L1 parts, signals and supply copper; L2 solid ground; L3 ground as well; L4 signals and supplies, with a ground via beside every signal via that changes between L1 and L4. Supply copper on L3 only as a local pour the current worksheet or a chip's datasheet layout needs (for example under the same net's top pour), never the reference of a fast or sensitive L4 net, recorded in the ledger as a deviation. Do not run signals along a pour boundary. Default 6-layer plan: L1 signals and parts, L2 ground, L3 signals (or power), L4 power, L5 ground, L6 signals: every signal layer next to a ground plane, both outer signal layers over ground; take the real stack and thicknesses from JLCPCB's page (`references/jlcpcb/capabilities.md`). Read the stack first: where L3 lies nearer to L4 than to L2 (usual on a 1.6 mm 6-layer build), make L4 ground as well and put the supplies on L3 as pours, or keep every fast or sensitive net off L3. Why: the return follows the nearest plane; on the standard 1.6 mm stack L2 and L3 are about 1 mm apart, so a supply plane there adds almost no decoupling, and every return crossing it excites the plane pair in the hundreds of MHz to GHz range.
- GEN-04 MUST keep high-frequency loops (hot loops, gate drives, protection discharge) local and out of reference, sensitive and cable grounds. Why: ground bounce causes resets and false trips.
- GEN-05 MUST give every decoupling, converter and ESD-clamp ground pad its own via at the pad, and every high-current ground terminal its own via on the current's path; a signal via that changes reference plane gets a ground via beside it (GEN-03). Why: a shared via adds its inductance to every part that uses it, and a universal via pitch is not a design.
- GEN-06 MUST keep the solid ground plane layer free of tracks. On 2 layers, keep the bottom one continuous ground with only short cross-unders, never under a hot loop or a fast signal: each about 12 mm or less (starting point), several short ones rather than one long one, a ground strap on the other layer over any longer gap where signals cross it; record each cross-under length. Why: one track across a plane cuts the return of everything above it, and all signals over one gap share its detour.
- GEN-07 MUST give every wire that leaves the board a return pin in the same connector, and in board-to-board connectors and ribbon cables a return pin next to each clock and each small group of fast signals. Place clocks, fast buses and switching converters away from connectors and cable exits; route no fast net past a connector it does not serve. Why: cables are the antennas; a shared or missing return, or a fast edge near the exit, drives current onto them.
- GEN-08 MUST keep every fast or sensitive line (USB pair, clock, RF line) inside the edge of its reference copper and away from the board outline by at least the larger of three line widths and three heights above the reference (estimate: a 0.25 mm track 1.5 mm above the plane of a 2-layer board needs about 4.5 mm); where a line must pass a plane edge or cut-out, record it in the ledger. Why: the return current spreads beside the track over a width set by its height above the plane, not only under it.
- GEN-09 SHOULD space a fast aggressor (clock, switch node, fast edge) from a sensitive victim by at least 3 times the victim's height above its reference plane (estimate: about 0.6 mm on the standard 4-layer stack, about 4.5 mm on a 1.6 mm 2-layer board), keep the parallel run short, and record distance and parallel length. Why: height, not line width, sets the coupling.

## 5. Copper fill

- GEN-10 MUST refill and inspect all zones after every substantial placement or routing change: islands, spokes, corner necks, via obstructions, broken planes. Why: one moved track can cut a pour in two.
- GEN-11 MUST tie every ground island with at least 2 vias, one toward each end, or remove it (`scripts/zone_check.py`), and MUST NOT count a distant island joined by one small via as a current path. A piece shorter than about 5 mm with one via is listed, not failed (starting point: a twentieth of a wavelength on FR-4 in the low gigahertz range; on a board with radio the pitch of `rf.md` RF-15 decides). Beside an RF line, an antenna or its keep-out, a crystal or a high-impedance node, every one-tie piece is a finding at any length. Why: an island is an antenna; the via, not the pour, sets the capacity.
- GEN-12 MUST give every thermal relief at least 2 live spokes on every layer, sized for the pad's current. Why: a big-looking pour may connect through one thin spoke.
- GEN-13 SHOULD avoid slots and long cuts in the ground plane (stitching vias around a slot do not restore the return across it), and SHOULD NOT cut broad holes under noisy nodes by default: follow the maker's layout example. Why: a slot forces the return around it, and a hole removes the plane's shielding. Slot and segment methods belong to boards without a continuous reference and are not used here; the only exceptions are those of GEN-64 (a cut a datasheet asks for, such as the analog-ground island of `power.md` PWR-17; an isolation barrier), with no track crossing the gap.
- GEN-14 SHOULD set a minimum zone width (0.4 mm worked on a proven board; starting point). Why: it removes fingers and slivers.
- GEN-15 MUST NOT run two long tracks side by side along an edge of a fill layer with parts behind them. Why: they fence off an island no via can reach.
- GEN-16 MUST draw zone outlines inside the edge clearance, set the edge rule before the first fill, fill last, and check the saved fill and the Gerbers (section 9). Why: a fill saved before the edge rule put copper on the outline of one board.
- GEN-17 MUST leave on every plane layer a copper web of at least the minimum zone width (GEN-14) between the clearances of neighbouring holes (via rows, fan-outs, header and connector pins), or stagger or move the row. Two holes whose clearances join into an opening shorter than about 2.5 mm are listed; three or more holes in a row, or a longer opening, are a finding (starting points). Plane layers are the inner layers that one net's zone covers, and an outer layer only when `board.toml` names it (`planes`); on a 2-layer board the ground side is named there, and without it the result is UNKNOWN, never a pass. Any opening counts under a net of the list of GEN-19 (`scripts/return_path_check.py` measures it), under a converter's hot loop and switch node, under the return of an ESD clamp, in the ground beside a chip antenna and in a narrow ground neck: the script lists the openings, the reviewer judges these places. Why: merged clearances are a slot under every signal that crosses them, and the minimum-width setting deletes narrow webs silently.
- GEN-18 MUST treat a ground fill on a signal layer as optional, never as a substitute for the plane: if one is used, stitch it to the plane along its length and at the end of every finger (on RF boards at the pitch of `rf.md` RF-15), and remove fingers that cannot be stitched. Why: a finger tied at one point resonates, and a fill hides necks and orphan islands.

Cuts in the board and in the copper. A slot, a cut-out, a moat or a split plane is a tool for one job. Used without that job it interrupts the return path of whatever crosses it, radiates like a slot antenna, and weakens the board.

| Kind of cut | Its job | Right when | Wrong when |
|---|---|---|---|
| Slot through the board between two conductors | Lengthens the path along the surface (creepage) | An isolation or safety requirement asks for more surface distance than the board gives (`protection-esd.md` ESD-75) | To "separate grounds" |
| Slot or cut-out around a part for heat | Keeps the board's heat from a sensor or a reference, or lets air pass | The part maker's guide shows it (`analog.md` ANA-52), or the heat table shows a gradient that matters. It is no moat as long as no net crosses it and the plane stays whole on its far side; otherwise GEN-64 | By habit |
| Mechanical cut-out or slot | Lets a part, a plug, a light pipe or a tool through; relieves strain beside a fragile part | The mechanics force it (`connectors-mechanical.md` MECH-03; `dfm-dft.md` DFM-115) | For looks |
| Cut-out in a plane under a part | Takes copper away where the part maker's drawing wants none: an antenna keep-out, under an inductor, under an RF pad, under an amplifier input | The maker's drawing shows it, or, under a pad of an RF line, the calculation of `rf.md` RF-03 gives it; at that size, with its ledger row (GEN-61; `emc.md` EMC-40, `power.md` PWR-07, `rf.md` RF-03, `analog.md` ANA-31) | Larger than drawn, or under anything the drawing does not name |
| Moat: a gap in a plane around one block | Forces every current of that block over one bridge | Only when the chip maker's datasheet or hardware design guide asks for it expressly for that part, or it is the barrier of an isolated interface (ESD-75); see GEN-64 | In every other case. To keep "digital noise" from an analog area, partition by placement on one solid plane (`analog.md` ANA-40, ANA-41) |
| Split plane joined at one point | As the moat | Only under the same two conditions as the moat (GEN-64; `power.md` PWR-17, `analog.md` ANA-41) | In every other case; never as a board-wide star (`power.md` PWR-19) |
| Guard ring | Takes up leakage current around a very-high-impedance node | Sub-nanoamp or tens-of-megohm nodes (`analog.md` ANA-10 to ANA-12) | Around ordinary signals |

The chassis copper of a connector shell (`protection-esd.md` ESD-60, `usb.md` USB-40) is a net of its own beside ground, not a plane split.

- GEN-61 MUST give every slot, cut-out, moat and plane split a row in the ledger: its job, the requirement or datasheet page behind it, and its proof on the board. A cut with no job is removed. Why: every cut costs a return path, stiffness or money; one that nobody can explain is a defect waiting for the net that crosses it.
- GEN-64 MUST NOT cut a moat into a plane or split a plane, on any layer, unless one of two conditions holds: (a) the datasheet or hardware design guide of a chip or module on the board asks for it expressly for that part, in words or in its layout drawing, and the ledger row cites the page; or (b) it is the barrier of an isolated interface or supply (`protection-esd.md` ESD-75). Nothing else allows one: not habit, not "analog and digital", not a general textbook, not a reviewer's preference. Without (a) or (b) the board keeps one solid ground plane and the blocks are separated by placement. A moat or split without one of the two is a blocker of the layout review. Why: a cut plane breaks the return path of whatever crosses it and radiates like a slot antenna; the cases where a cut helps are few, and the chip's maker names them.
- GEN-62 MUST route no net across a moat or a split except over its bridge, list the nets that cross, and prove it with `scripts/return_path_check.py` (GEN-19). Why: a track across the gap has no return under it; its current goes round the gap and the loop radiates.
- GEN-63 MUST draw slots and inner cut-outs of the board on the outline layer with inner corners rounded for the milling tool; take the smallest milled slot width and corner radius from the manufacturer's capability page (not recorded in `references/jlcpcb/capabilities.md`: read the live page; UNKNOWN until then); keep copper on every layer back from the cut by the edge clearance (`scripts/edge_check.py` measures it) and parts back as from any edge; and name the slots in one line of the order remark. Why: a slot narrower than the tool is widened or left out, and copper at a milled edge is cut open.

## 6. Current, voltage-drop and heating worksheet

There is no universal right track width. Size each conductor from its current, pulse, allowed rise, finished copper, surroundings, length and drop budget. Build the worksheet with `scripts/neck_check.py`; keep it in `out/`.

| Input, per segment | Meaning | Source |
|---|---|---|
| I_cont; I_peak and t_pulse | Worst RMS current lasting more than about a minute; worst transient, inrush or fault pulse until the protection acts | Load budget; simulation |
| L; w_min | Path length with detours; narrowest effective width anywhere, minus the fabricator's width tolerance | The board; `scripts/neck_check.py` |
| t | Minimum finished copper per layer | Fabricator stack (`references/jlcpcb/capabilities.md`) |
| T_amb; dT; dV_allowed | Local ambient; allowed rise; drop budget for positive plus return | Requirements; UNKNOWN until measured |
| Vias | Count, drill, minimum hole-wall plating (UNKNOWN until read), arrangement at each layer change | The board; the fabricator |

Resistance of a uniform conductor, all dimensions in metres:

    R20 = rho * L / (w * t),   rho = 1.724e-8 ohm m (foil)
    RT  = R20 * (1 + 0.00393 * (T - 20)),   dV = I * RT,   P = I^2 * RT
    R_total = sum(rho * Li / (wi * ti)) + R_vias + R_contacts + R_wires + R_parts

Via barrels and plated outer copper: carry rho up to about twice the foil value and report the drop at that bound. Rise and hot resistance feed each other: compute the rise, take RT at T_local plus the rise, repeat until the rise moves less than 0.5 C. At fixed current this settles at dT = dT0 / (1 - 0.00393 * dT0) (dT0: rise at cold resistance) and runs away as 0.00393 * dT0 nears 1.

Example, illustration only: 3 A through 2.0 x 40 mm of 35 um copper gives 9.9 mOhm, 29.6 mV, 0.089 W at 20 C, about 20 % more at 70 C. This is DC resistance only; it says nothing about loop inductance or temperature rise.

- GEN-20 MUST use IPC-2152 as the method for current versus heating, or a layout-aware thermal solver, or a bench measurement. Label an IPC-2152 rise without planes an upper bound, an IPC-2221 chart value an estimate. Rate inner copper with the same relation at its real thickness, never at half capacity as old charts did. Never size, pass or fail a track, pour, neck or via on current density (A/mm2). Why: old charts and web calculators are not IPC-2152, and current density ignores the shape and cooling that set temperature.
- GEN-21 MUST rate the positive path and its return. Why: ground is copper with resistance, not a symbol.
- GEN-22 MUST treat pads, necks, spokes, via rings, package pins and connector pins as series bottlenecks, and add series sections in series and parallel layers in parallel, explicitly, for resistance and drop. Rate the heating of stacked copper as one conductor of summed thickness over the shared width, carrying the full current. Why: a short neck can dominate heating while the pour looks wide, and stacked layers heat one shared footprint.
- GEN-23 MUST budget the drop from the regulator output to the load pins and back: copper, protection parts, ferrites, contacts at end of life, harness at temperature. Check regulator minimum output minus worst drop at peak current and high temperature against the load's minimum. Never quote a capability from heating alone. Why: a trace can survive thermally and still drop too much.
- GEN-24 SHOULD start with 50-75 mV of board copper, positive plus return, at a heavy-load connector (starting point; the real limit is the load's minimum voltage). Why: a budget set early leaves room for contacts and harness.
- GEN-25 MUST size each branch for the sum of its simultaneous downstream loads. Why: one net name does not mean one current, nor one width.
- GEN-26 MUST compute a short neck's resistance, drop and loss exactly and report its temperature as a bound, from the parent copper's rise (low) to the long-track IPC-2152 rise at the neck width (high). PASS only on the high value; otherwise widen the neck, add a parallel path, or put a plane or copper several times its width directly under it on the next layer (vias stitched along a track add almost nothing). A package-limited neck (a pad narrower than its current wants) that still fails is accepted only with an infrared bench check. Why: a long-track chart overstates a short neck, ignoring the neck understates it, and only another package widens a pad.
- GEN-27 MUST write the allowed rise beside every width, chosen from the hottest neighbour, the enclosure and the laminate, and keep an unknown interior temperature UNKNOWN: calculate with a conservative value and put the measurement on the bench list. Why: an assumed value written as fact hides the worksheet's biggest uncertainty.
- GEN-28 MUST check every fault, inrush and crowbar pulse through each track, neck and via adiabatically: temperature from the time integral of I^2, the cross-section, copper's volumetric heat capacity and rho(T), starting hot, kept below a written limit (default: the laminate's Tg). A current lasting over about a minute is continuous; for a shorter one take the smaller of the adiabatic and the steady-state rise. Copper behind a current limiter carries the limit current for the whole limit time, or continuously if it retries. Copper is never the protection: the worst let-through stays far below its fusing current, and a board whose copper discoloured in a fault test is retired. Why: steady-state charts say nothing about pulses, and copper near fusing fails unpredictably.
- GEN-29 MUST pass heating and drop on the worst finished geometry (width minus the fabricator's tolerance, minimum finished thickness) and the iterated hot resistance, nominal beside worst. Flag a conductor where 0.00393 * dT0 exceeds about 0.2; FAIL "runaway" when the iteration does not settle within a few passes. Why: narrow copper is steep, so the tolerance alone can turn a PASS into a FAIL, and heating feeds itself through the resistance.

Starting widths, starting points only (short outer copper, 1 oz finished, FR-4, still air, no planes; about 10 C rise figures; not verified ampacity):

| Continuous current | Starting width, 1 oz outer | Note |
|---|---|---|
| up to 0.1 A | 0.2-0.25 mm | Robust manufacturable width |
| 0.1-0.5 A | 0.3-0.5 mm | |
| 0.5-1 A | 0.5-0.8 mm | Check heat on long runs |
| 1-2 A | 0.8-1.2 mm | |
| 2-3 A | 1.5-2.0 mm | Prefer a local pour |
| 3-4 A | 2.5-3.0 mm | Review fault pulses |
| 4-5 A | 3.0-4.0 mm or a pour | Review fault pulses |
| 5-6 A | 4-5 mm or a pour | Short broad pours beat long tracks |

- For the same DC resistance, 0.5 oz needs about twice the width and 2 oz about half; the thermal rating does not double with copper weight, and heavier copper limits fine-pitch spacing, so agree it with the fabricator and assembler. Nominal: 0.5 oz about 17.5 um, 1 oz about 35 um, 2 oz about 70 um. Inner layers are often thinner (as read in 2026-11: 0.5 oz inner on JLCPCB's standard 4-layer stack). Design to a declared maximum interior ambient; 10 C rise is a first target, not a mandate: 40 C carries nearly twice the current at the same width (estimate).

## 7. High-current vias and layer changes

- GEN-30 MUST keep a converter's highest di/dt connections on one layer without vias where a direct path exists. Why: each via adds loop inductance, about 0.1 nH down to a plane 0.2 mm below and about 1.3 nH through a 1.6 mm board (estimates).
- GEN-31 MUST use several plated vias in parallel where current changes layer, sized by GEN-32 and spread across the full width of the current flow. Why: there is no universal "1 A via", and vias on one edge of a pour share badly.
- GEN-32 MUST size the vias of a power path at each layer change by area: combined barrel cross-section pi * t * (d - t) (t the fabricator's minimum hole-wall plating, d the drill) at least half the cross-section of the narrowest copper joined, and at least two vias. Evidence: the area ratio and the vias' resistance, never an ampere rating of a via. Until the wall plating is read it is UNKNOWN: use a conservative value stated as an assumption, never the surface copper. Better still, keep the high current on one layer. Why: a via's temperature follows the copper around it, and an ampere figure for a via is a current-density model; pulses go through GEN-28.
- GEN-33 MUST place the thermal vias a datasheet asks for inside the exposed pad as the exception of `dfm-dft.md` DFM-40 allows, landing in copper of the exposed pad's own net per the datasheet pin table (`power.md` PWR-20). Why: an open via in a pad wicks solder away unless the paste windows sit between the vias, and some exposed pads are VIN, SW or drain, or must float, so a via into the ground plane would short them.
- GEN-34 MUST check that every power and stitching via lands in its intended plane. Why: a via inside a plane cut-out reaches nothing.

## 8. Impedance control: where it applies and where it does not

Controlled impedance is for electrically long lines, not a mark of quality. Rule of thumb: control it when a line is longer than about one sixth of the distance its edge travels during the rise time (about 15 cm per ns on FR-4). Take the rise time from the driver's datasheet at its fast corner, never from the clock rate (`mcu-digital.md` MCU-46).

| Net type | Target | Controlled impedance? |
|---|---|---|
| Power, ground, converter input and output | Low DC resistance, low loop inductance | No |
| Converter switch node | Small area, short, wide enough for RMS current | No; a 50 ohm target is wrong |
| USB-C CC lines (PD signalling) | Short, referenced, ESD at the connector | No; never a 90 ohm pair |
| USB 2.0 D+/D- | 90 ohm differential, +-15 % | High speed: yes; full speed on a short board: usually not (`usb.md`) |
| I2C, UART, slow SPI, reset, buttons | Nearby reference, controlled rise time | Only if rise time, length or a test demands it |
| RF lines and antenna feeds | 50 ohm, or the part's stated impedance | Yes (`rf.md`) |

- GEN-40 MUST take line geometry from the fabricator's impedance calculator for the actual stack, with copper thickness and solder mask; record inputs and result. Never guess. Why: on 2-layer 1.6 mm FR-4 a 50 ohm microstrip is about 3 mm wide; over a thin inner prepreg it is a fraction of that.
- GEN-41 MUST start a new stack and impedance review when an RF or high-speed signal is added to a board that had none. Why: the old stack was chosen without impedance in mind.
- GEN-42 MUST measure and record each stub, branch, test pad or neck-down on a fast net, and use its electrical length to decide how deep to look: shorter than about 25 mm per ns of rise time (estimate) it is normally negligible on a general logic net; longer, simulate it or remove it. This screen is not an interface's acceptance limit: a link with its own channel rules (the PHY's or connector maker's layout guide, the interface standard) follows those, and the screen never accepts a stub they forbid. USB high speed: `usb.md` USB-52. Why: a measurable screen replaces a ban nobody can check, but a generic rise-time rule does not know a receiver's eye or a connector's own discontinuity.

## 9. KiCad specifics

- GEN-50 MUST put every net in a named net class (power classes by current, switch node, input, sensitive feedback, control, CC, RF, ground) and derive each class's width from the worksheet, not from its name. Why: classes are how DRC finds each net's width rule.
- GEN-51 MUST NOT treat a net class's width as proof: hand-narrowed segments and overrides keep their width. Write minimum-width rules in the custom rule file (`track_width` on every layer, `connection_width` for zones) and set them as errors. Why: on one board the classes existed but the width checks were warnings, so DRC enforced nothing.
- GEN-52 MUST know the limits of `connection_width`: it did not see a deliberately narrowed neck inside a pour, and it reads pads and via rings as connections, so a floor can never exceed the net's narrowest pad. Why: a DRC pass says nothing about pour necks; measure pours with `scripts/neck_check.py`.
- GEN-53 MUST set as errors: widths, copper slivers, starved thermals (at least 2 spokes), missing courtyards, holes inside courtyards, courtyard overlaps, silkscreen to pad, silkscreen text height and thickness, and "via hole to SMD pad" (the hole keeps its own annular ring from every SMD pad, any net). No via in an SMD pad, except thermal vias inside an exposed thermal pad as the maker's drawing shows (drill and pitch from the datasheet); keep the paste windows between them, cover them on the far side where the fabricator offers it, and exempt those footprints from the via-to-pad rule by name (`dfm-dft.md` DFM-40). The rule template `jlcpcb.kicad_dru` that comes with `scripts/drc_run.py` holds these. Why: warnings get ignored; errors stop the gate.
- GEN-54 MUST prove every custom rule on a known-good and a known-bad copy before trusting it. Why: one rule form flagged many correct vias; a first neck check passed the defect it was written for.
- GEN-55 MUST run DRC with schematic parity and all severities after the last netlist update and refill (`scripts/drc_run.py`): 0 errors, 0 unconnected, parity 0, every warning explained. Write the board checksum, KiCad version, rule file, finished copper and BOM variant into every check report. Why: parity catches board and schematic drifting apart, and a report without the checksum proves nothing about the ordered board.
- GEN-56 MUST NOT take a clean DRC as proof of the saved fill. The command-line check judges the fill as saved, and KiCad 9 does not report a saved fill too near the board edge; a check run with a refill option or from a script fills a copy in memory while the board file and Gerbers keep an older fill. Reload with the project rules, refill, save, then measure copper to edge on the exported Gerbers (`scripts/edge_check.py`). Why: the factory builds the Gerbers, not the DRC's copy.
- GEN-57 MUST inspect zone connection mode and spoke width on every power path and on every pad of a power or protection part. Why: a power pad can hang on thin spokes inside a big pour.
- GEN-58 MUST run the 3D check: images of every connector with its mating side, and `scripts/body_check.py`. Why: 2D DRC does not see collisions or an offset 3D model origin.
- GEN-59 MUST keep a modified library footprint as a project copy with its own name, and use project-relative paths for models and libraries. Why: library mismatch reports, silent reverts, and personal paths in shared files.
- GEN-60 MUST load and save boards only through the safe file layer (`scripts/kicad_io.py`), one tool process per board file. Why: two processes on one file left stale locks and a dialog on the user's screen.

## 10. Acceptance checklist skeleton

Copy into the review. Each row gets PASS, FAIL, UNKNOWN or WAIVED with its evidence; a blank is not PASS. Add one row per ledger rule.

| ID | Item | Severity | Evidence |
|---|---|---|---|
| AC-01 | Schematic, netlist and BOM match the board under review | Blocker | Parity report, checksums |
| AC-02 | Power budget per source mode, voltage at every load pin, current per contact at worst fault | Blocker | Budget and interconnect tables |
| AC-03 | Fault and stored-energy map covered, with stress in the protecting parts | Blocker | Fault table, simulation results |
| AC-04 | Stack and finished copper declared; deviations from maker layouts recorded | Blocker | Stack note, ledger |
| AC-05 | Outline, holes, keep-outs, connectors match the interface file; 3D fit with mated plugs; enclosure fit by the project's own CAD, or FAIL "cannot run" carried to the mechanical review | Blocker | `scripts/body_check.py`, section views, fit report or the FAIL line |
| AC-06 | Every ledger rule met; decoupling and protection at their pins | Blocker | Ledger with crops, distance table |
| AC-07 | Hot loops compact, switch nodes small; sense from the right node; single points proven by a cut test | Blocker | Close-up crops, cut-test report |
| AC-08 | Worksheet complete for every power path and its return, at worst geometry and hot resistance, pulses included; narrowest copper measured | Blocker | Worksheet, `scripts/neck_check.py` report |
| AC-09 | Layer changes carry parallel vias with area ratio and resistance stated (GEN-32) | Major | Worksheet, via counts |
| AC-10 | Reference planes and return paths for sensitive signals, measured net by net (GEN-19); impedance control only where it applies | Major | `out/return_path.md`, overlay images, calculator record |
| AC-11 | No orphan islands, starved spokes or slivers after the final fill | Major | `scripts/zone_check.py`, plots |
| AC-12 | DRC all severities with parity: zero unexplained items | Blocker | `scripts/drc_run.py` report |
| AC-13 | Copper to edge on the exported Gerbers, board and panel | Blocker | `scripts/edge_check.py` report |
| AC-14 | Footprints, pin 1, polarity and placement rotations against makers and assembler | Blocker | `scripts/fp_audit.py`, rotation test |
| AC-15 | Mask, paste, via-in-pad, fine-pitch webs, edge rails | Major | Fab checklist on exports |
| AC-16 | Silkscreen rules met and the visual reviews closed | Major | `scripts/silk_check.py`, visual reports |
| AC-17 | Test points reachable with the board mounted; every unprovable point on the bench list | Major | Crops, bench list |
| AC-18 | EMC: source-and-victim table complete, each pair has its measure, zone map followed (`emc.md`) | Major | Source-and-victim table, zone map, crops |

## 11. Required outputs of a layout review

1. Revision and assumptions: schematic revision, board checksum, size, stack, finished copper, interior temperature, fabricator, assembler, sources, every UNKNOWN.
2. Rule-by-rule table: ID, severity, status, location (net, part, coordinates), evidence, measured or calculated value, requirement and source, fix.
3. The current, drop and heating worksheet with both returns, vias, contacts and the voltage at each load.
4. Images after the final refill: every copper layer, close-ups of each hot loop, the input protection and each connector fan-out; plane maps; 3D fit, mated connectors, fastener paths, section views.
5. The DRC and manufacturing report on the exported files, with numbered waivers only; the bench list for what layout cannot prove (temperatures, ripple, stability, emissions, faults).
6. A correction plan: blockers first, then noise and heat, then manufacture and service; schematic changes marked as needing the user's approval; then the release statement. A claim like "all traces are wide enough" without geometry and numbers is invalid.

## 12. Release states

The release states and what each needs are in one place: the one release table, `references/reviews.md` section 8. This rule base sets no release rule of its own; its results (PASS, FAIL, UNKNOWN, WAIVED, with the severities of section 2) are the evidence that table reads.

## What to verify, and how

| Item | Method or script | Evidence to keep |
|---|---|---|
| Rule severities and custom rules | Read the rule file; run each rule on a good and a planted-bad copy; list the footprints exempted from "via hole to SMD pad" by name | Rule file, both results, exemption list |
| DRC and parity | `scripts/drc_run.py` after the last refill | JSON and summary in `out/` |
| Pour necks and the worksheet | `scripts/neck_check.py` (worst geometry, hot resistance, neck bounds, pulses, via area ratio), with a planted narrow neck that must fail | Worksheet, neck table, mutation result |
| Ground islands and stitching; narrowest copper web between two holes on plane layers | `scripts/zone_check.py` on the saved fill | Island table with via counts, web table |
| Return path of every fast or sensitive net (GEN-19) | `scripts/return_path_check.py` with the net list of `board.toml`, proven on a copy with a planted slot under one net; the overlay image per plane layer | `out/return_path.md`, overlay images, notes of what was seen |
| Layer plan, gap crossings, plane-edge distances, stub lengths | Copper plots of every layer; fast nets highlighted with measured distances and lengths | Annotated plots, ledger lines |
| Bench thermal check of a power path | 10 minutes or more at constant current; camera scan of the whole path against a known-emissivity reference; 4-wire drop hot and cold, average rise dT = (R_hot / R_cold - 1) * (254.5 + T_cold - 20), T_cold the copper temperature at the cold reading in C | Images, readings, bench test ID |
| Saved fill to edge | `scripts/edge_check.py` on the exported Gerbers | Edge report, corner crops |
| 3D fit and model origins | `scripts/body_check.py`, `scripts/fp_audit.py`, renders | Reports, renders with crop names |
| Everything above, by eye | `scripts/review_images.py`; open every image and write what you saw | Contact sheet, crop list, notes |

## Typical mistakes

- DRC reported 0 while the saved fill and the Gerbers had copper up to the outline: the fill on disk was older than the edge rule, and the rule check did not show it.
- A deliberately narrowed neck in a power pour passed the connection-width check; only a geometric cut found it.
- Net classes were set, but the width checks were warnings, and a custom rule let ground pins connect with a single spoke.
- A worksheet summed series sections as if they were parallel. An unknown enclosure temperature was used as if measured; it stays UNKNOWN until the bench.
- Two long bottom tracks along an edge fenced off a ground island; elsewhere a ground via sat in the plane's cut-out and reached nothing.
- A "verified" claim compared the design with its own generator, and another check reported FAIL on every board because the checker was wrong. Give every check a positive and a negative control.
- Common in the field: a narrow track carried its current for a long time, then ran away and fused at a few percent more; near its limit, copper fails without warning.

## Background reading

These books informed the rules; the rules are stated in this skill's own words.
- Bogatin, *Bogatin's Practical Guide to Prototype Breadboard and PCB Design*.
- Brooks and Adam, *PCB Design Guide to Via and Trace Currents and Temperatures*.
- Bogatin, *Signal and Power Integrity - Simplified*.
- Li, *RF Circuit Design*.
