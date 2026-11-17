# <board name>: simulation results

This file is kept as `sim/RESULTS.md`. Plan: `sim/PLAN.md`. Schematic netlist checksum used: <sha256>. Date: <date>. Engine and version: <ngspice 45>.

Rules: the limits below are copied from the plan, unchanged. Open every plot and write what you saw. A run that did not converge has no result; fix the bench first.

## Summary
| Count | Value |
|---|---|
| Tests in the plan | <n> |
| Pass | <n> |
| Fail | <n> |
| Accepted deviation | <n> |
| Not converged or not run | <n> (must be 0 at gate 1) |

## Results
| ID | Limit (from the plan) | Result | Plot file | Verdict |
|---|---|---|---|---|
| <SIM-01> | <rail 3.2 to 3.4 V by 5 ms> | <3.31 V at 2.4 ms, overshoot 40 mV> | <`sim/out/sim-01.png`> | <PASS> |
| <SIM-02> | <load pin < 6.0 V> | <6.4 V for 50 ns> | <`sim/out/sim-02.png`> | <FAIL: TVS changed, re-run as SIM-06> |
| <SIM-06> | <load pin < 6.0 V> | <5.2 V> | <`sim/out/sim-06.png`> | <PASS> |

Plot notes (what I saw): <SIM-01: smooth rise, no ringing. SIM-02: spike at the cable-inductance edge, clipped by the TVS.>

## What the simulations changed in the design
| Test | Finding | Design change |
|---|---|---|
| <SIM-02> | <TVS clamp too high> | <D1 changed to a 5 V standoff part> |

## Accepted deviations
Only with the user's words. A deviation is a named exception to a limit, not a moved limit.
| ID | Limit missed | By how much | Consequence | The user's words, date |
|---|---|---|---|---|
| <SIM-05> | <dip ride-through 20 ms> | <15 ms at the low corner> | <sensor resets once, no damage> | "<quote>", <date> |

## Re-runs by reviewers
| Review | Test re-run | Agreed with ours? |
|---|---|---|
| <review prefix: S2 or SC> | <SIM-01, SIM-03> | <yes within 10 mV> |

## What only the bench can prove
| Item | Why no simulation can show it | Bench test ID |
|---|---|---|
| <Layout parasitics and emissions> | <no layout at gate 1> | <BT-06> |
| <Real sensor start-up behaviour> | <no model> | <BT-02> |
| <ESD with a real gun> | <no model> | <BT-07> |

## Models and sources
| Model | File | Source and date |
|---|---|---|
| <TVS> | <`sim/models/tvs.lib`> | <maker, <date>> |

## Limits of this campaign
<Short list: what the models do not represent.>
