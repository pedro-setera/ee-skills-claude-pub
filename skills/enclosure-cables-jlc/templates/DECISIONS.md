# <device name>: decisions

One row per choice, with its options and cost effect. Costs carry their source and date. The user's words are quoted. An opinion asked is not a go.

## Design decisions with costs
| # | Topic | Options (cost effect) | Recommended, why | Chosen | The user's words, date |
|---|---|---|---|---|---|
| <D1> | <sheet thickness> | <1.2 (base) / 1.5 (+x) / 2.0 (+y)> | <1.5: stiff enough at 20 N> | <1.5> | "<quote>", <date> |
| <D2> | <coat colour> | <chart names> | <"<chart name>"> | <> | |
| <D3> | <inks> | <chart names, contrast of each on the coat> | <highest contrast> | <> | |
| <D4> | <print faces and wording> | <front only / front and rear> | <> | <> | |
| <D5> | <nuts and feet> | <> | <> | <> | |
| <D6> | <quantity> | <1 set / 2 sets (+clearly less than a second full price)> | <2> | <> | |

## Panel wording (accepted on <date>)
| Face | Text | Height (mm) | Ink | Position |
|---|---|---|---|---|
| <FRONT> | <POWER> | <3.0> | <chart name> | <under the switch> |

## Makers' assembly pages read (before stacking parts)
| Part | Page title | Read on | What it fixed |
|---|---|---|---|
| <module and its carrier> | <"Assembly guide"> | <date> | <which way the module sits> |

## Tolerance stacks
| Fit | Chain (each size with its tolerance and source) | Worst case | Root-sum-square | Clearance | Verdict |
|---|---|---|---|---|---|
| <lid over tray sides> | <2 bends +-1 deg over 50 mm; cut +-0.1> | <+-1.0> | <+-0.6> | <0.5 per side, slots take 1.0> | <pass with slots> |

## Changes of named values
| Date | Value | From | To | Why (evidence) |
|---|---|---|---|---|
| <date> | <`STAND_H`> | <4.0> | <4.5> | <print finding F3> |

## Small gaps and allowed contacts
| Pair | Gap or overlap | Why it is fine |
|---|---|---|
| <stand_H1 / board> | <touching> | <the board sits on it> |
