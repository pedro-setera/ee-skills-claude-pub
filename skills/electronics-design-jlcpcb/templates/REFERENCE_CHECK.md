# <board name>: reference check

Every non-passive chip against its datasheet and the maker's reference circuit (typical application, evaluation board schematic and BOM). Fill one block per chip. Mark each changed item "aligned" and say what changed.

Datasheet used: <file in vendor/datasheets/, revision, date>. Evaluation board used: <name or "none published">.
Documents used for a complex part (as `references/phases/04-datasheets.md` step 1 lists them: microcontroller, programmable logic, radio chip or module, display chip, charger and others): hardware design guide <title, document number, revision; sections read; rows it produced> | schematic checklist <...> | layout guide <...> | antenna guide <...> | errata <...>. Or: "none published", searched <where, with which words> on <date>. Or: "pending: asked the user on <date> for <title>".

## <U1 name, part number, package>

### Pin table (from the datasheet pin table, not from our symbol: the rows are the pin report of `scripts/ratings_check.py`, made from `src/datasheet_pins.toml`; only the column OK? is written by hand)
| Pin | Datasheet name | Function | Our net | OK? |
|---|---|---|---|---|
| <1> | <VIN> | <supply input> | <5V_IN> | <yes> |
| <4> | <EN> | <enable, high on, 1.2 V threshold> | <5V_IN via 100 k> | <yes> |
| <EP> | <GND pad> | <thermal and ground> | <GND, 5 vias> | <yes> |

Look-alike pin-outs and suffix variants checked: <yes, part <x> has pin 1 and 2 swapped vs <y>>.

### Pin functions (programmable chip only; `references/reviews.md` section 9)
The pins, functions and results come from `out/pin_function_check.md` (made from `src/pin_use.toml` and the `functions` of `src/datasheet_pins.toml`); the page of the maker's table and the two states are written by hand from the datasheet.
| Pin | Function needed | Maker's table entry (page) | Result | State in reset | State while programmed |
|---|---|---|---|---|---|
| <PA9> | <USART1_TX> | <alternate function 7, table 15 (p. 45)> | <PASS> | <input, floating> | <input, floating> |
<Or: "not a programmable chip".>

### Limits against our corners
| Parameter | Datasheet limit (page) | Our corner | Margin |
|---|---|---|---|
| <Absolute max VIN> | <6.0 V (p. 4)> | <5.5 V plus 8 V TVS clamp> | <check clamp: fail if no margin> |
| <Recommended VIN range> | <2.5 to 5.5 V (p. 4)> | <4.5 to 5.5 V> | <ok> |
| <Output current> | <300 mA (p. 4)> | <peak 150 mA, hot> | <2x> |
| <Junction temperature> | <125 C (p. 4)> | <80 C estimated> | <ok> |

### Supply order, ramp and reset (PWR-63)
| The maker requires (page) | Our circuit guarantees it by | Switching on | Switching off | After a short dip | Proof |
|---|---|---|---|---|---|
| <core 1.2 V before I/O 3.3 V; while the core is below 1.0 V the I/O rail stays below 0.5 V (p. 18)> | <3.3 V regulator enabled by the 1.2 V power-good> | <ok> | <3.3 V falls first: its discharge resistor> | <supervisor holds reset 200 ms> | <SIM-09; BT-07> |
<Or: "one supply, no order stated".>

### Where the chip negotiates or sequences
<Table of what it requests and when, or write "not applicable".>

### Reference circuit against ours
| Item | Maker's reference circuit | Ours | Justified? |
|---|---|---|---|
| <Input capacitor> | <1 uF ceramic> | <10 uF ceramic> | <yes: bulk for hot plug, ESR ok> |
| <Output capacitor> | <2.2 uF min, ESR < 1 ohm> | <4.7 uF X7R> | <yes: 2.2 uF after DC bias> |
| <Feedback divider> | <R1 / R2 for 3.3 V> | <same values> | <aligned> |
| <Part not in the reference> | <none> | <TVS at input> | <yes: connector ESD> |

Evaluation board BOM compared: <differences listed, each justified>.

### Verdict
<Aligned | aligned with <n> justified deviations | open: <item>>. Checked by: <agent or review prefix, such as S1>, <date>.

## Parts added after reviews
| Part | Added in | Reason | Checked against datasheet? |
|---|---|---|---|
| <TVS D3> | <fix round 1> | <finding S2-MJ2> | <yes, p. 3> |
