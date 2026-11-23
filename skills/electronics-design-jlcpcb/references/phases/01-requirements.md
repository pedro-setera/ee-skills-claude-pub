# Phase 1: requirements

Get every requirement that shapes the design from the user before any concept, write it as a one-page device description with no blank heading, play it back in plain words with a picture, and get the user's confirmation: gate 0. This first exchange decides most of the later rework, so here completeness beats brevity. Always suggest: the user is often not an electronics engineer.

## Inputs

- The user's words so far and the decisions already in the state file.
- Documents of everything the device connects to: mating boards, modules, sensors, antennas, loads, supplies, the enclosure. Photos count.
- `templates/REQUIREMENTS.md`: the page and its completeness checklist.
- `references/working-rules.md` sections 1, 2 and 11 (plain words, asking, cost in every decision).
- `references/lessons.md`, section "Phase 1: requirements".

## Steps

1. **Draft the page before asking anything.** Fill `REQUIREMENTS.md` from what the user already said. Every heading of its completeness checklist ends in one of three states: answered by the user (with the date), an assumption you wrote and the user will see, or "not needed" with a reason. No heading stays blank. A written assumption the user can veto costs them less than a question.
2. **Walk a day in its life.** Describe a typical use from switching on to switching off, step by step, in the user's terms. Each step names the function it uses; a step without one is a missing function. Write the functions as a numbered list in the user's words, one job per line, and a short "out of scope" list: what the device will not do is as useful to the design as what it will. A function the user did not ask for is offered as an option with its cost, never added: the description stays as small as the user's need (`references/working-rules.md` section 12).
3. **Settle the power source first**, before any concept: a battery, the mains, an external DC supply, or a mix.
   - Battery: which kind (a single lithium cell, AA or AAA cells, a coin cell), rechargeable or not, charged how (USB-C is the usual suggestion), capacity or running time between charges, replaceable by the user or built in. Lithium cells are a safety topic: say so, and follow the cell maker's and the charger maker's documents to the letter (`references/pcb-rules/power.md` PWR-55). A cell that cannot be recharged (a coin cell, alkaline cells) must never be charged by another supply, and lithium cells in series or a cell on a plug are safety topics too (PWR-64).
   - Mains: suggest an external certified adapter and low voltage on the board. Mains on the board is outside the proven range and a safety topic: say so.
   - External DC: the voltage range, the connector (USB-C 5 V is the usual suggestion, because everyone has a charger and it is cheap; USB-C with power delivery when more than about 10 W is needed; a barrel jack or a terminal block when the installation needs it), and who supplies the adapter.
   - For every source: lowest and highest voltage, the weakest source that must still work, hot plugging, the faults to survive. Also: must it keep working while charging; what happens when power is lost; how the user switches it on and off. Each source dropped removes its protection parts.
4. **Settle what the person sees, hears and touches:** lights (how many, colours, what each means), buttons and switches (how many, what each does, press or slide, where), display (none, a few digits, a small graphic screen, touch or not, size), sound (none, a beeper, a speaker for voice or music, a microphone), anything the user plugs in or adjusts. A choice the end user sees is the user's: suggest one, never fill it in silently.
5. **Walk every external interface:** each connector, cable, antenna, sensor, button, indicator and module. For each one write:
   - what is on the other side, and who powers it;
   - the level in both directions, and the current;
   - the connector, its mating part, and who supplies the cable;
   - the space it needs, the direction the cable leaves, and whether hands touch it.
6. **Walk every signal chain** from the outside world to the chip and back: antenna or sensor power (a bias tee, a phantom supply), DC blocks, level shifts between separately powered parts, terminations, filters, protection, isolation. Each item found gets four things assigned: its power, its part, its drawing, its mechanical space. An item with one of the four missing is an open row, not a detail for later.
7. **Record where it lives:** size, shape, mounting and enclosure (an existing one, a fixed outline, holes, connectors through a wall, height limits; whether the case is closed or has openings for air; the material now and a possible later one: a metal case changes grounding and antennas); where it is installed; ambient temperature where the board sits (inside an enclosure it is higher than the room), moisture, vibration; who handles it. If the outline depends on an open enclosure decision, say so: the schematic can proceed, the outline waits for phase 8. When a case is named or wanted, ask how the board is held in it: with screws, or sliding into slots or rails (as in extruded aluminium cases), or otherwise. When none is, record the assumption "held by screws or clips, settled with the case at the board definition". Ask whether the board must match a standard format (an Arduino-style board, a Raspberry Pi add-on board, a DIN-rail case): then its outline, holes, header positions and pin-out follow the format's published drawing exactly. A board that slides in needs a free strip along each guided edge, on both sides; with no case drawing yet, record the assumption "3 mm free along each guided edge, both sides, to be confirmed against the case drawing".
8. **Record the performance numbers that matter** (accuracy, speed, range, running time), each with a figure, or "typical for such devices: `<value>`" as an assumption. For a battery device the wanted running time is recorded here; phase 2 computes the autonomy against it.
8a. **Record the reliability expectation:** how long the device must last, how many hours a day it works, what a failure means for the user (an annoyance, a cost, a danger) and whether a failed device is replaced or repaired. Ask it in those words, with a suggested answer ("typical for such devices: 5 years, always on"). It decides part grades, margins and what must be replaceable; without it the design is sized for nothing in particular.
9. **Ask the product behaviour outside normal running.** These are the user's decisions, so give the exact words their customer would see:
   - a source that is too weak: refuse, run with a warning, or run reduced;
   - a fault on an output: latch off or retry;
   - switching off: anything with storage needs a clean shutdown, a visible "shutting down" sign and a timeout for a hung computer;
   - operations that must not lose power, such as a firmware update.
10. **Record the cost target** (`references/working-rules.md` section 11, quality first, then cost): the target cost per assembled board at the first quantity and at the later quantity; if the user cannot say, a class in plain words with what each means ("good quality at the lowest cost": the cheapest way that keeps quality, stability and reliability, no premium part without a written reason, no accessory that was not asked for; "mid-range"; "performance first"). Record the quantity now and later, and whether this is a concept run or goes on sale: sample quantities and the number of assembled boards follow from it. Ask the user to rank cost against size, running time and features; the ranking decides conflicts later. If quality and the cost target cannot both be met, do not lower quality quietly: tell the user in plain words, with the options (a higher cost, fewer features, or a named limitation they accept), and let them decide.
11. **Hear the wishes that drive cost:** layer count, parts on one side or two, which parts the user solders by hand, silkscreen content (name, revision, date code, labels), a size limit. Record them as wishes with their price effect; phase 8 decides, when the chips' own layout needs are known.
12. **Record what the user already has or prefers:** parts, a module, firmware, an enclosure, a similar product to compare with; the firmware and who writes it; a deadline, if any.
13. **Set the regulatory flags:** mains, a radio transmitter, lithium charging, a safety function, sale and the markets (`references/pcb-rules/emc.md`: radio and emission rules then apply). This skill does not certify anything; note what the user must arrange. When a product safety standard applies, creepage comes from it and the board is outside the proven range: say so (`references/pcb-rules/protection-esd.md` ESD-74).
14. **Rate the complexity** with the table below and write the range statement into the page.
15. **Decide the depth** from the facts of `references/reviews.md` section 9, read on the description as it stands: a switching converter, more than 2 A, more than 30 V; a radio, an antenna, a satellite-navigation receiver, a signal above 100 MHz; a fast bus; mains, lithium charging, a fault that can hurt a person or start a fire; a microcontroller or other programmable chip; fine parts or more than 2 layers; for sale, more than 50 boards, a batch the user calls costly. Each fact switches on only the extra review its row names. One fact is enough. What the description does not let you rule out counts as present: a "module", a "sensor board" or a "small supply" may hold a radio, a programmable chip or a converter, so ask what it is or count it. The size of the board decides nothing. Write the depth and its facts into the page and the state file (`review_depth`, `depth_facts`). It is not a question to the user: it is shown in one line at the play-back (step 18), and the user may overrule it. It is decided again at gate 1 and gate 2 from what the design has become, moves up by itself, and never down without the user's yes.
16. **Fill the process section:** the gates, the notification events (from the one list of phase 0, step 9) and the channel. These are the frame of phase 0, step 9: ask them in this round, not twice, and record the answers in the state file. The order and mailbox watches are asked once, in phase 14.
17. **Ask in short rounds until no heading is blank.** At most about five questions per round, most important first: what it does and its power source; then the person's side and the mechanics; then the rest. Each question in everyday words, with a suggested answer and a reason a non-engineer can weigh, numbered so that "all as suggested" is a valid reply. Do not ask what the user already said or what you can safely decide; do not stop while a blank could change the design. Where the user is unsure, offer two or three concrete options with what each means for cost, size and use, and recommend one. Where a requirement is unrealistic or two conflict, say so now, in plain words, with the alternatives.
17b. **Number what must be true.** Turn every statement of the page that the finished device must meet into one testable line with its number or condition (`REQ-01`, `REQ-02` ...; section 14 of the page). A wish that cannot be tested ("robust", "fast") is asked back until it has a number or a condition. These IDs are followed through the design note, the gate summaries and the bring-up.
18. **Play it back: gate 0.** Show the one-page description in plain words; a simple picture of the device as the user will meet it (the outside with its lights, buttons and connectors) and a first block sketch (how such pictures are made: `references/tools.md` section 4); the list of assumptions; the out-of-scope list; and one line with the review depth and the facts behind it ("Depth: lean. Facts: no radio, no converter, 12 V, 0.5 A, 5 boards, own use."), which the user may overrule. The user confirms or corrects; fold the corrections in and show it again. Record the confirmation as gate 0 (`gate0` in the state file) with the date and the user's words. Phase 2 does not start without it. The catch-up of a brought-in design uses the same page.
19. **Changes later come back through this page:** update it, show what the change costs (parts, time, re-reviews), get the user's OK, then continue.

### Complexity rating

| Item | Inside the proven range | Beyond it |
|---|---|---|
| Layers | Up to 6 | More than 6 |
| Digital | Microcontrollers; I2C, SPI, UART; USB 2.0 | Memory buses, multi-gigabit links, fine-pitch BGA |
| Power | Low-voltage DC conversion and protection | Anything connected to mains voltage |
| RF | Simple 50 ohm lines to a connector or a module | RF chains that need field simulation to design |
| Any other circuit type (analog, sensors, protection) | It has a rule file in `references/pcb-rules/` | It has none |

Range statement, one of the two, written into the page and said to the user:

- "This board is inside the range this process is proven on."
- "This board goes beyond the proven range in: `<items>`. I can continue, but the work on those items is experimental and needs a human engineer's review before any order."

## Questions for the user

Ask in everyday words: say what a choice means for the device and its cost rather than naming the technique, explain any technical word in a few words the first time, and give the suggested answer with a reason a non-engineer can weigh (`references/working-rules.md` section 1). Never ask about passives, footprints, internal voltages or tools. Review depth is not asked: you decide it from the facts (step 15) and show it at the play-back. The number of costly agents at once is a cost decision and is asked; how reviews are otherwise organised is not. Typical questions, each only if the answer is not already known:

- What should it run from: a battery, a plug-in adapter, or both?
  - Suggested: `<a USB-C charger, 5 V: everyone has one and it is cheap | a built-in rechargeable cell charged over USB-C, about <n> hours per charge>`.
  - Why: the power source shapes the whole board; every extra source adds protection parts, tests and cost.
- What will a person see, press and hear on it?
  - Suggested: `<one green light for "on", one button to switch on and off, no display, no sound>`.
  - Why: each light, button or screen is a part, a hole in the case and a cost; these are your customer's choices.
- Where will it run: temperature, inside which enclosure, handled by whom?
  - Suggested: `<inferred>`; if the inside temperature is unknown, I write an assumed value, mark it UNKNOWN and put its measurement on the bench list.
  - Why: part ratings, fuses and timers are chosen for the hottest case.
- (Only when a case is named or wanted) How will the board be held in its case: with screws, or does it slide into grooves of the case, or something else?
  - Suggested: tell me the case (maker and model, or a drawing) and I take the measures from it.
  - Why: a board that slides in needs a free strip along its edges, on both sides; parts in that strip stop it from going in.
- What should the device do when `<the source is too weak / an output is shorted / it is switched off while busy>`?
  - Suggested: `<one behaviour, with the words the customer sees>`.
  - Why: this is product behaviour; the circuit follows from it.
- What may one finished board cost, now and later? How many boards, how many assembled? Is this a concept run, or will they be sold?
  - Suggested: `<good quality at the lowest cost>`; concept run, 5 boards, 2 of them assembled.
  - Why: every part is tested against the target; 5 is the usual board minimum, and assembling 2 keeps the first-sample cost low and leaves bare spares.
- (Only when more than a few tens of boards are planned later) Will the later boards be programmed and tested one by one by hand, or on a test jig at the assembler?
  - Suggested: by hand for the first series; I keep the board ready for a jig.
  - Why: a jig reaches only one side of the board, so that side is decided before the layout.
- When the boards arrive, should they come fully assembled, or can you solder a few larger parts yourself? Do you have a multimeter?
  - Suggested: fully assembled; a multimeter is enough.
  - Why: it decides which parts I may choose and how the first test is done.
- If it needs a small programmable chip, who writes and loads its program?
  - Suggested: `<I design it without one | I write a hand-over page for your programmer>`.
  - Why: a chip that needs a program is of no use without someone to program it.
- How long must it last, how many hours a day does it work, and what does a failure mean for its user?
  - Suggested: typical for such devices: `<5 years, always on; a failure is an annoyance>`.
  - Why: it decides the grade of the parts and what must be replaceable.
- If cost, size, running time and features pull apart, which comes first?
  - Suggested: `<cost, then running time, then size>`.
  - Why: the ranking settles later conflicts without another question.
- (Only when the user has shown such knowledge; otherwise write "none stated" as an assumption) Do you have fixed wishes for layers, assembly side or silkscreen content?
  - Suggested: none now; I propose them at the board definition.
  - Why: the chips' layout needs are not known yet, and a wish like "2 layers to save money" may save very little.
- I will stop for your approval at the schematic, at the PCB and at payment, and send a notice when a gate is ready, a payment is waiting, the manufacturer asks something or needs a confirmation, the order's main status changes, and the boards ship. Agreed?
  - Suggested: yes, by `<channel>`; I run at most two of the expensive independent checks at a time; files in `<folder>`.
  - Why: three stops cover every decision with cost or a permanent effect; the rest runs without you.
- (Only when beyond the range) Continue as experimental work with a human engineer's review?
  - Suggested: yes for a concept run, no for anything to be sold.
  - Why: the checks and rules of this process are not proven for those items.

## Checks before leaving this phase

- [ ] No heading of the completeness checklist is blank: each is answered, a visible assumption, or "not needed" with a reason. Evidence: the checklist table of `REQUIREMENTS.md`.
- [ ] The day-in-its-life walk-through uses every function, and every function appears in it. Evidence: the walk-through and the numbered function list.
- [ ] The power source block and the block of what the person sees, hears and touches are settled. Evidence: those blocks, with the user's answers or the confirmed assumptions.
- [ ] Every external interface has a row with power, part, drawing and mechanical space. An unknown cell says UNKNOWN and is listed in the state file's open questions. Evidence: the interface checklist.
- [ ] Every signal that leaves the board was walked end to end. Evidence: one line per chain naming what it needs (bias, DC block, level shift, protection) or "nothing".
- [ ] Every supply source has its voltage range, current and faults to survive; dropped sources are listed as not supported. Evidence: the power-sources table.
- [ ] The reliability expectation is recorded (life, use, what a failure means, replace or repair). Evidence: section 6 of the page.
- [ ] A device with a programmable chip names who writes and loads its firmware. Evidence: the row "Firmware, and who writes it" of the page and a decision row.
- [ ] Every requirement is one testable line with an ID. Evidence: section 14 of the page; no line without a number or a condition.
- [ ] The cost target or class, the ranking, the quantity and concept-or-sale are in the user's words. Evidence: decision rows.
- [ ] The complexity table is filled and the range statement was shown. If beyond: the user's acceptance. Evidence: the page and a decision row.
- [ ] The depth was decided from the facts, each fact answered yes, no or unknown (unknown counted as yes), shown to the user in one line at the play-back, and is in the state file header. Evidence: `review_depth`, `depth_facts`, the play-back message.
- [ ] Gates and notification events are recorded. Evidence: the process section and decision rows.
- [ ] The page, the picture, the assumptions and the out-of-scope list were played back, and the user confirmed them: gate 0. Evidence: status line "confirmed by the user on `<date>`", `gate0` and the user's words in the state file.

## Outputs

- `REQUIREMENTS.md`, confirmed, with its completeness checklist and the picture of the device (`out/device_sketch.png`)
- `PROJECT_STATE.md` updated: gate 0, review depth and its facts, decisions, open questions, next action

## Lessons behind this phase

- A power feed that an external part needed was forgotten until the board was ordered -> the day-in-its-life walk finds missing functions, every signal chain is walked, and every external interface gets power, part, drawing and space before any board is designed.
- A second supply input was planned, then dropped by the user in one sentence -> the power source is settled first; a design started on a guessed supply carries parts for a source nobody needs, and a dropped source takes its protection with it.
- Premium parts and accessories were proposed because the cost target was never written down -> the cost target and the ranking are written here, and every part and accessory is tested against them (`references/working-rules.md` section 11).
- Orders were sized for more assembled units than the concept stage needed -> concept-or-sale and the assembled quantity are asked here.
- "Two layers, one side, to save money" arrived late; the saving turned out small and the layout was redone on more layers -> cost-driving wishes are heard early with their price effect and decided in phase 8.
- The user wanted to stay out of the process and was still asked about details a file already answered -> only what cannot be inferred is asked; the rest is an assumption open to veto.
- A clean shutdown, its visible sign and a timeout came up only in discussion -> behaviour outside normal running is asked as product decisions.
- An enclosure material decided after the first layout changed the grounding -> present and planned enclosures are part of the page.

The full cases are in `references/lessons.md`.
