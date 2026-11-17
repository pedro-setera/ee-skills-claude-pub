# <board name>: what the design uses each pin of each programmable part for

Kept as `src/pin_use.toml`. The designer writes it in phase 5, from the design and never from the datasheet: one line per connected pin of every microcontroller, programmable-logic chip or other part that runs the project's firmware. `scripts/pin_function_check.py` compares it with what the maker's pin-function table offers on that pin (the `functions` and limits typed into `src/datasheet_pins.toml`, `templates/DATASHEET_PINS.md` rule 4c) and with the exported netlist. It is also the start of the firmware hand-over (`templates/FIRMWARE_HANDOVER.md`).

When the file is missing, the script ends "cannot run" and prints a skeleton with one line per connected pin and its net: copy it and fill it in.

## Rules for writing it
1. One table per programmable part, named by its designator.
2. `function` is ONE of the functions the datasheet lists for that pin, in the datasheet's spelling (for a plain port pin: the pin's name).
3. `direction` is `in`, `out`, `both`, `open drain` or `analog`.
4. `purpose` is free text: what the pin does on this board, and where the signal goes. It becomes the column "Function on this board" of the firmware hand-over.
5. `reason` is needed only when the pin is sampled at reset, or belongs to the debug port or the oscillator, and is used for something else: say what holds the pin at the level it needs during reset, or why the debug port or oscillator is not needed.
6. A pin whose datasheet entry is `functions = []` (supply, ground, reset) needs no line.
7. `setting` only for a function that the datasheet table lists in `resources`: what this use needs from that resource (a timer's frequency), in the same words on every pin of the resource.

## Skeleton
```toml
# What this design uses each pin of each programmable part for. Written from the design, not from the datasheet.

[<U1>]                                            # one table per programmable part, named by its designator
"<6>"  = {function = "<USART2_TX>", direction = "<out>", purpose = "<serial data to the host, J2 pin 3>"}
"<14>" = {function = "<I2C1_SCL>", direction = "<open drain>", purpose = "<sensor bus clock>", reason = "<R9 holds the pin low during reset; the bus is idle until the firmware runs>"}
"<19>" = {function = "<TIM1_CH1>", direction = "<out>", purpose = "<fan PWM>", setting = "<25 kHz>"}
```

## What the check does and does not prove
- It fails: a connected pin without a line here; a line for a pin that does not exist; a function the pin does not offer; two jobs on one pin; one single-instance function on two pins; an output on an input-only pin; an analogue use on a pin without it; a reset-sampled, debug or oscillator pin used for something else without a `reason`; and, only where the datasheet table declares it: a direction against the function's mode; two uses of one resource at different settings; a peripheral whose pins mix two pin sets. A chip whose block says neither `programmable = true` nor `false` is UNKNOWN.
- A PASS is per-pin table consistency, not proof that the firmware's whole pin, clock and peripheral configuration can be built. The clock tree, DMA, interrupt lines, IO bank voltages, functions that exclude each other beyond what the table declares, the level a reset-sampled pin needs and the state of pins in reset and during programming belong to the joint peripheral-allocation review (`references/reviews.md`).
- It trusts both tables as typed: the system reviewer compares them with the maker's pin table of the exact package, row by row.
