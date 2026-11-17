# <board name>: order log

**Order references stay in this project file only.** Never copy them into the skill, a template, a public repository or an e-mail to anyone but the supplier.

The baseline table is the watch task's memory. The watch reads it, compares, and updates it. Keep one row per order.

## Baseline
| Order | Status | Ships to | Last change | Checked |
|---|---|---|---|---|
| <PCB and assembly order no.> | <In production> | <city, country> | <date time> | <date time> |
| <Parts order no.> | <Packing> | <city, country> | <date time> | <date time> |

Status values are written exactly as the order page shows them.

## Status changes
| Date time | Order | From | To | Note |
|---|---|---|---|---|
| <date time> | <no.> | <Waiting for review> | <In production> | <push sent, delivery confirmed: yes> |

## Shipping plan
Decided in phase 12, before the first payment. Rows in the order the orders are placed; the order that joins the others is placed last.
| Order | Ships to | Travels with | Fallback date |
|---|---|---|---|
| <1: PCB and assembly> | <the parts supplier's collection warehouse (fixed at its checkout)> | <waits there for the loose parts> | <the loose parts are paid by <date>, while it waits> |
| <2: loose parts, placed last> | <city, country> | <joins the board order> | <if the cable quote is not paid by <date>, the parts join the boards without it> |

## Supplier questions and answers
One topic per row. The agent drafts in VENDOR_EMAIL form. A message is sent by the user, or by the agent only after the user's go on that exact text; afterwards the agent lists any deviation from the approved text in the Result column.
| Date | Their question | Our answer (approved text; sent by) | Deadline | Result |
|---|---|---|---|---|
| <date> | <Is the connector overhang intended?> | <Yes, it is on purpose (picture attached); sent by <the user / the agent after the go of <date>>> | <72 h> | <accepted; deviations: none> |

Status nudges for this order (asked once in phase 14): standing permission <yes, "<quote>", <date> | no: every nudge is drafted and shown first>. Supplier's own stated time: <quote, date>. Anything with a commercial effect always needs a fresh go.

## Instructions to the supplier
Every instruction given outside the form fields (order remark, reply, ticket), so that a later message never contradicts an active one.
| Date | Instruction | Still active, or withdrawn on |
|---|---|---|
| <date> | <do not assemble J3; it is fitted by hand> | <active> |

## Placement confirmation
| Date | Parts checked | Crops saved | Permission wording and date | Status after |
|---|---|---|---|---|
| <date> | <all polarised parts> | <`out/order/crops/`> | "<quote>", <date> | <proof screenshot path> |

## Landed cost
| Item | Estimate | Actual | Note |
|---|---|---|---|
| Parts | <x> | <x> | |
| PCB and assembly | <x> | <x> | <fee lines> |
| Shipping | <x> | <x> | <combined or separate> |
| Duties and tax | <x> | <x> | <paid at delivery or in cart> |
| **Total** | <x> | <x> | |

## Delivery
| Item | Value |
|---|---|
| Shipped | <date> |
| Tracking | <number, carrier> |
| Arrived | <date> |
| Count and condition | <5 boards, no damage> |

## Lessons for the next order
| What happened | What it cost | What to do next time |
|---|---|---|
| <A box for a free option was ticked by default> | <10 USD> | <read every box in the cart> |

Proposed to the skill's lessons only with the user's OK, and with no names or numbers.
