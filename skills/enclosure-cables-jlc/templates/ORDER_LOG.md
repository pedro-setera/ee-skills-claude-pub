# <device name>: order log

**Order references stay in this project file only.** Never copy them into the skill, a template, a public repository or a message to anyone but the supplier.

The baseline table is the watch's memory. The watch reads it, compares, and updates it. One row per order.

## Baseline
| Order (label, ref) | Supplier | Status (the page's own words) | Held parts or lines | Ships to | Next step, deadline (local) | Checked |
|---|---|---|---|---|---|---|
| <cables, no.> | <> | <Drawing need approval> | <lines 2, 5> | <city, country> | <revise notes by <date time>> | <date time> |
| <case, no.> | <> | <In review> | <lid> | <> | <> | <> |

## Status changes
| Date time | Order | From | To | Note |
|---|---|---|---|---|
| <> | <> | <In review> | <Waiting for payment> | <told the user; pay by <time>> |

## Line map (recorded the moment the quote is ready)
The supplier numbers the lines itself. Every message names both: "line <n> (<our id>)".
| Supplier line | Our id | Name | Qty | Price | Drawing status |
|---|---|---|---|---|---|
| <-1> | <CAB-04> | <fan lead> | <2> | <> | <confirmed on <date>> |
| <-2> | <CAB-01> | <main harness> | <2> | <> | <revise sent <date>> |

## Totals at three steps
| Order | Step | Parts | Shipping | Duties | Discount | Total | Seen on | Why it changed |
|---|---|---|---|---|---|---|---|---|
| <case> | Quote | <> | <> | <> | <> | <> | <> | |
| <case> | After review | <> | <> | <> | <> | <> | <> | <+ hardware> |
| <case> | Pay step | <> | <> | <> | <> | <> | <> | <shipping re-priced> |

## Shipping plan (copy of the ticks in ORDER_PLAN.md)
| Order | Ships to | Travels with | Proof | Done |
|---|---|---|---|---|
| <> | <> | <> | `orders/screens/<file>` | [ ] |

## Supplier questions and answers
One topic per row. A message is shown to the user first, unless a standing OK for that order is recorded below.
| Date | Their number (ours) | Their question | What caused it (field, file word, remark line) | Our answer (approved text; sent by) | Deadline | Result |
|---|---|---|---|---|---|---|
| <> | <part 2 (P-02 lid)> | <colour must come from the chart> | <a non-chart colour word in the remark> | <"Colour: <chart name>."; sent by the user> | <same day, <time>> | <released next day> |

Standing OK for this order: messages <no | "quote", date>; nudges <no | "quote", date>. Anything that changes price, design or delivery always needs a fresh go.

## Instructions to the supplier
Every instruction given outside the form fields, so that a later message never contradicts an active one.
| Date | Instruction | Still active, or withdrawn on |
|---|---|---|
| <> | <> | <active> |

## Production drawings (cables)
| Line (our id) | Drawing date | Verdict (CONFIRM / REVISE / NOT DECIDED) | What was wrong | Revise note sent | Confirmed (permission, proof) |
|---|---|---|---|---|---|
| <-2 (CAB-01)> | <> | <REVISE> | <position 2 and 3 swapped; tolerance> | <date, picture file> | <> |

Rounds needed: <1>. Confirmed lines: <n of m>.

## Landed cost
| Order | Item | Estimate | Actual | Note |
|---|---|---|---|---|
| <> | Parts | <> | <> | |
| <> | Shipping | <> | <> | <combined or alone> |
| <> | Duties and tax | <> | <> | <in the cart | on arrival> |
| <> | **Total** | <> | <> | |

## Timeline (real lead times)
| Order | Requested | Quote | Paid | Questions (rounds) | Drawings | Production start | Shipped | Arrived |
|---|---|---|---|---|---|---|---|---|
| <> | <> | <> | <> | <> | <> | <> | <> | <> |

## Delivery
| Order | Shipped | Carrier, tracking | Arrived | Count and condition | Duties paid |
|---|---|---|---|---|---|
| <> | <> | <> | <> | <> | <> |

## Lessons for the next order
| What happened | What it cost | What to do next time |
|---|---|---|
| <A remark line named a feature the part does not have> | <1 supplier day> | <catalogue scan on the remark; one remark per part> |

Proposed to the skill's lessons only with the user's OK, and with no names or numbers (phase 16).
