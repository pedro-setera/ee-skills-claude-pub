# <board name>: datasheet pins and ratings (the machine-readable table)

Kept as `src/datasheet_pins.toml`. It says, in a form a script can read, what each maker's datasheet says about each pin, and what the design can put on each supply and signal level at the worst case. `scripts/ratings_check.py` compares it with the exported netlist every time the schematic changes (phase 5, step 7b; again in phase 10).

## Rules for writing it
1. **Type it from the datasheet, never from the symbol or the schematic.** A table copied from the drawing agrees with the drawing and proves nothing. Best is a second agent that gets only the datasheets and the BOM.
2. One block per exact part number (suffix included), naming the datasheet file, its revision and the page of the pin table and of the ratings table.
3. Every pin of the package appears once, with the number and the name exactly as the datasheet prints them. Pins the datasheet calls NC or "do not connect" are listed too.
4. Ratings: the absolute maximum, and the recommended operating range, as the datasheet gives them. A rating that depends on another pin ("VIN + 0.3 V") is written relative to that pin. A pin with no rating in the datasheet says so (`no_rating = "p. 4: not specified"`), so that "forgotten" and "not given" are told apart.
4a. A pin marked "leave open", and a pin on a net whose level is exactly 0 V (a ground pin), need no rating. A pin that the datasheet says MUST be connected carries `connect = "required"`. A rating relative to a pin on another net is checked with the two nets independent (a maximum with this pin's net at its highest and the other at its lowest, a minimum the other way round) unless `[tracks]` says how one follows the other (rule 5a). An absolute one is also checked with the other net off (0 V) where that net's level reaches 0 V (`transient_min = 0.0`); where the table does not say, and that state would break it, the result is UNKNOWN. Connector pins that the symbol only numbers ("Pin_1") are not compared by name. Further keys the script reads: `alias` (other names the symbol may use for the pin), `abs_min_rel`, `rec_min_rel`, `rec_max_rel`, `transient_min`, and the table `[tracks]` (rule 5a). An unknown key, or a placeholder left in angle brackets, is a finding.
4b. Default levels (`references/pcb-rules/mcu-digital.md` MCU-64, MCU-65). Every control input (enable, shutdown, chip select, reset, driver-enable, write-protect, mode, address, a gate or base) carries the key `input`: `"none"` when the part holds the pin by nothing of its own, or only by a pull that firmware must switch on; `"up"` or `"down"` when the datasheet guarantees a pull inside that works without firmware. A part whose signal pins are high-impedance while it is in reset, being programmed or not yet started (a microcontroller, programmable logic, a module that runs its own firmware) carries `io_hiz_in_reset = true` in its block; a single pin is set apart with the pin key `hiz_in_reset = true` or `false`. Every pin may carry `function`: what the pin does, in a few of the datasheet's words; the report prints it, so that it serves as the pin table of the reference check.
4c. Pin functions (`scripts/pin_function_check.py`). The block of every chip (reference U or IC with 8 pins or more; `board.toml [pin_functions] chip_prefixes`, `chip_min_pins`) says `programmable = true` (a microcontroller, programmable logic, any chip that runs the project's firmware or configuration) or `programmable = false` (a fixed function, or a module that runs its maker's fixed firmware); a chip without either is UNKNOWN, and "not applicable" needs every chip classified. Each of its pins carries `functions`: everything the maker's table of pin functions lists for that pin of this exact package (the pin's name and aliases count too); `functions = []` for a pin with one fixed function (supply, ground, reset). Limits, only where the datasheet states them: `input_only = true`, `open_drain_only = true`, `analog = true` (the pin has a converter or comparator channel; without it an analogue use fails), `sampled_at_reset = {level = "<level it needs, and what that selects>", function = "<its name in that role>"}`, `debug = "<its debug function>"`, `oscillator = "<its oscillator function>"`. A function that the datasheet allows on several pins at once is listed in the block: `on_several_pins = ["MCO"]`. Optional, only where the datasheet states it, never guessed from a function's name: `function_modes` (a sub-table with `source = "<table, page>"` and per function its mode, `"in"` for a receive input, `"out"`, `"both"`, `"open drain"` for a bus line, `"analog"`, or a list; a use against the mode fails, a used function without a mode is reported as "direction not checked"); `resources = {TIM1 = ["TIM1_CH1", "TIM1_CH2"]}` (functions that share one resource of the chip: their uses must give the same `setting`); `pin_sets` (per peripheral, two or more sets of pin = function, such as its default and its remapped pins: a peripheral takes all its pins from one set). What the design uses each pin for is a file of its own, `src/pin_use.toml` (`templates/PIN_USE.md`), written from the design and not from the datasheet.
5. Levels: a supply or the ground counts for "tied" and "held by" only under the name of its own net in `[levels]`; a signal that merely carries a level name in `[nets]` is no supply. A net is named in full, or without its sheet path when that is unique; a net without a name is given by one of its pins (`"U1.3" = ...`). The off state of a switched rail is `transient_min`, not `min`. An ESD pulse is not typed as a level: it is judged in the design note by `references/pcb-rules/protection-esd.md` ESD-02, ESD-03 and ESD-23. For every supply and every signal level of the design, the lowest and the highest value in normal use, and the highest and lowest during switching on, off, plugging and faults (from the requirements page, the protection table and the simulations, each named). Every number is finite (nan and inf are findings) and no minimum is above its maximum.
5a. `[tracks]`: how a net follows another, in every state (switching on and off included): `"<net>" = {net = "<the net it follows>", offset = [<lowest V>, <highest V>], source = "<why>"}`, i.e. net = the other + offset. Only where it is true: a line pulled up to, or driven from, the supply its pin is rated against; a switch output against its input. Several: a list of such tables. A key that is a level of `[levels]` and no net holds for every net `[nets]` gives that level (one line for the logic lines of a domain: `"IO_3V3"`). Without a source, with offsets that are not two finite numbers in order, or where the levels contradict it, it is not applied and is a finding. An input from an independently powered source gets no line: give the supply its off state.
6. A typing error here passes the script. The schematic reviewer (LC, or S1 where it runs) compares this file with the datasheets line by line for every chip.

## Skeleton
```toml
# Typed by hand from the datasheets in vendor/datasheets/. NOT generated from the symbols.

# Worst case of every supply and signal level, transients included, with its source
[levels]
"<+5V>"  = {min = 4.5, max = 5.5, transient_max = 6.5, source = "<requirements: 5 V +-10 %; hot plug SIM-03>"}
"<+3V3>" = {min = 3.2, max = 3.4, source = "<regulator U2 tolerance, set-point table>"}
"<GND>"  = {min = 0.0, max = 0.0}

# Nets that carry a level under another name, or have their own range
[nets]
"<VBUS>"   = "<+5V>"
"<EN_3V3>" = {min = 0.0, max = 5.5, source = "<pulled to VBUS by R1>"}
"<SDA>"    = "<+3V3>"

# How a net follows another (only where true; otherwise two nets are independent: rule 5a)
[tracks]
"<EN_3V3>" = {net = "<+5V>", offset = [-5.5, 0.0], source = "<R1 pulls it up to +5V; the host only pulls it low>"}

# One block per exact part number
[parts."<maker part number, suffix included>"]
refs = ["<U2>"]                                   # the designators that carry this part
# io_hiz_in_reset = true                          # for a microcontroller or programmable logic: its signal pins float until its firmware runs
# programmable = true                             # a part that runs the project's firmware: pin_function_check.py checks it (rule 4c)
# programmable = false                            # every other chip (8 pins or more): rule 4c
# resources = {TIM1 = ["<TIM1_CH1>", "<TIM1_CH2>"]}   # functions sharing one resource: one setting for all its uses
#   then each of its pins lists what the maker's pin-function table offers, for example:
#   "6"  = {name = "<PA2>", abs_max = 4.0, functions = ["<USART2_TX>", "<TIM2_CH3>", "<ADC_IN2>"], analog = true}
#   "14" = {name = "<PB8>", abs_max = 4.0, functions = ["<BOOT0>", "<I2C1_SCL>"], sampled_at_reset = {level = "<low: start from the main flash>", function = "<BOOT0>"}}
#   "15" = {name = "<PA13>", abs_max = 4.0, functions = ["<SWDIO>"], debug = "<SWDIO>"}
# [parts."<...>".function_modes]   source = "<table 6, p. 31>", "<UART2_RX>" = "in"
# [parts."<...>".pin_sets.<UART2>]   default = {"<6>" = "<UART2_TX>"}, remap = {"<19>" = "<UART2_TX>"}
datasheet = "<vendor/datasheets/<file>.pdf, rev <D>, pins p. <3>, ratings p. <4>>"

[parts."<maker part number, suffix included>".pins]
"1" = {name = "<VIN>",  abs_max = 6.5, rec_min = 2.3, rec_max = 6.0}
"2" = {name = "<GND>"}
"3" = {name = "<EN>",   abs_max_rel = {to = "<VIN>", plus = 0.3}, abs_min = -0.3, input = "none"}   # a control input without a pull inside
"4" = {name = "<NC>",   connect = "leave open"}
"5" = {name = "<VOUT>", abs_max = 6.5}
```

## What the check reports
- A pin number the symbol has and the datasheet does not, or the reverse.
- A pin whose name on the symbol is not the datasheet's name.
- A pin on a net whose worst-case level is outside its recommended range (a finding) or beyond its absolute maximum (a blocker), transients included.
- A relative rating broken at the opposite extremes of two independent nets, or with the other net off (blocker or finding); UNKNOWN where the table gives the other net no off state and that state would break it.
- A number that is nan or inf, or a minimum above its maximum (a finding: such a table never passes).
- A pin marked "leave open" that is connected, or the reverse where the datasheet demands a connection.
- "Can float": a pin with `input = "none"` whose net is no supply, has no resistor to a supply or to ground, and has no driver other than pins of parts marked `io_hiz_in_reset` (a finding, naming the pin and the part whose reset leaves it floating). An input held by a resistor or by its own pull is listed with what holds it. A resistor that pulls against a pull inside the part is listed with both, for the level calculation.
- Limits of "can float": a connector pin does not count as a driver (the cable may be unplugged: MCU-65 asks for a resistor there). A net driven only by an open-drain or switchable three-state output is listed as "driven by", never as held: judge it by hand. `io_hiz_in_reset` holds for the whole part; a single pin that the part pulls or drives during reset or from its boot code carries `hiz_in_reset = false`, and one that floats on a part without the key carries `hiz_in_reset = true`.
- A chip, transistor, diode, polarised capacitor or connector with no block, a pin with no rating, a net with no level: UNKNOWN, listed. At gate 1 there are none. A reference that is no part (a cable landing drawn as a connector) is named in `skip`.
- A designator whose maker part number does not contain the name of its block: a finding (a table for another part proves nothing).

Settings, table `[ratings]` of `board.toml` (all optional): `netlist` and `table` (the two input files, when they are not at their usual places), `mpn_field`, `need_block` (the reference prefixes that must have a block), `skip` (references that need none), `resistors` (prefixes that count as pull resistors, default `R`; only two-pin parts count), `not_drivers` (prefixes that never drive a net, default `C`, `TP` and the connector prefixes).

## Status
| Item | Value |
|---|---|
| Typed by | <agent or user, date; from which datasheets> |
| Compared with the datasheets by | <LC, or S1 where it runs; date> |
| Check result on netlist <sha256> | <PASS / FAIL / <n> UNKNOWN> |
| Planted-defect proof | <a swapped pin name, a 5 V level on a 3.6 V pin: both failed as they must> |
