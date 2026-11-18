# <device name>: cable list, version <1>

The list for people. The data for scripts is `cables/cables.json` (phase 5); the two must say the same.
Frozen on <date> (no change after the first quote: a submitted cable quote cannot be edited).

## Interconnect check
Every connector of every board and every panel part ends in a cable, or has a reason.
- [ ] Power <done by: , date: >
- [ ] Signals
- [ ] Radio (coax)
- [ ] Supply carried on a signal or coax cable
- [ ] Fans
- [ ] Ground and shield bonds
- [ ] Display, buttons, lamps

| Connector | On | Goes to | Cable | Or: not cabled, because |
|---|---|---|---|---|
| <J1> | <main board> | <panel power jack> | <CAB-01> | |

## The cables
| ID | Name | From (P1) | To (P2) | Type | Wires | Gauge | Max current | Length (mm) | Tol | Label |
|---|---|---|---|---|---|---|---|---|---|---|
| <CAB-01> | <power> | <housing, 2 positions> | <tinned 4 mm> | <harness> | <2> | <22> | <2 A> | <rough 120 | final 132> | <+-5> | <CAB-01 POWER> |

## The user's choices (asked once, before any drawing)
| Topic | Choice | The user's words, date |
|---|---|---|
| Ends: connector or tinned | <per cable> | "<quote>", <date> |
| Routes | <under the boards, no loops> | |
| Cable types | <wire standard, coax type, network cable type> | |
| Colours | <per wire, per jacket> | |
| Ends trimmed at assembly | <which> | |

## Lengths (from phase 5)
| ID | First measure | Second measure | Difference and its cause | Allowance or floor | Ordered length | Works at the design tolerance (+-D) |
|---|---|---|---|---|---|---|
| <CAB-01> | <121.4> | <120.9> | <0.5> | <+10: tinned end trimmed at assembly (above the route floor, +5)> | <132> | <yes: reach and bend rows pass> |

## Parts per cable (live stock on <date>)
| ID | End | Housing or plug (maker part, supplier code) | Terminal (maker part, supplier code, wire range) | In stock |
|---|---|---|---|---|
| <CAB-01> | <P1> | <> | <22 to 28 AWG> | <yes, date> |
