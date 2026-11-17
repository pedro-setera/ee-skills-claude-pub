# <board name>: expected connectivity (intent file)

The intent file is a hand-written statement of which pins must be one net. The netlist check compares the exported netlist against it.

## Rules for writing it
1. Write it from the circuit description and the datasheet pin tables. **Never generate it from the schematic source or the generator.** A netlist compared with its own generator proves nothing.
2. Every pin of every part appears exactly once: in one group of pins that form exactly one net (`[nets]`), or in the "must stay unconnected" list (`[no_connect]`). Parts with no electrical job (mounting holes, fiducials) may be listed under `[options]` to be ignored.
3. Group names are descriptive only. The check compares which pins are joined, not net names. A group has at least two pins: a pin that connects to nothing belongs in `[no_connect]`.
4. Write the pin functions per IC as comments, with the datasheet table named next to every pin-function line, so a reviewer can verify it.
5. Passive pins: list them in the group they belong to. A part with no listed pin fails the check.
6. Keep it in `src/expected_connectivity.toml` (TOML; a pin is written as reference dot pin number, `"U1.3"`) and give it to the schematic reviewers as an independent source.
7. The check cannot find intent errors (a wrong idea written down twice). It does not replace the datasheet review.

## Skeleton
```toml
# Written by hand from the circuit description and datasheet pin tables.
# NOT generated from the schematic source.
#
# Pin functions from the datasheets (package pin: function), one line per IC
# <U2>: 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT    <datasheet, Table 4-1>
# <Q1>: 1 G, 2 S, 3 D                        <datasheet, p. 2>

# Intended nets: group name -> the pins that must be exactly one net
[nets]
"<5 V input>" = ["<J1.1>", "<C1.1>", "<U2.1>", "<U2.3>", "<R1.1>"]   # EN tied to VIN by R1
"<3.3 V rail>" = ["<U2.5>", "<C2.1>", "<U1.n>", "<R3.1>"]
"<ground>" = ["<J1.4>", "<C1.2>", "<C2.2>", "<U2.2>", "<U1.n>"]

# Pins that must stay unconnected, with the reason
[no_connect]
pins = [
    "<U2.4>",    # <no-connect pin, datasheet says leave open>
]

# References the check ignores
[options]
ignore = ["<H1>", "<H2>", "<FID1>"]   # <mounting holes, fiducials>; a pattern such as "H*" is allowed
```

## What the check reports
- Pins in the netlist that are in no group (missing intent).
- Pins in a group that sit on a different net (wrong connection).
- Two groups that landed on one net (a short between intended nets).
- A group split over two nets (an open).
- A listed no-connect pin that is connected.
- Parts in the netlist that are not in the file.

Output: `out/connectivity_report.md` with a per-IC pin table (pin, pin name, net), read against the pin functions noted above.

## Mutation self-test (required)
Before the check counts, prove it can fail. `python -I scripts/netlist_check.py --project <board folder> --self-test` plants three defects in copies of the netlist:
1. Two nets merged (for example ground and the 3.3 V rail). The check must report FAIL.
2. One net split (a pin cut off). The check must report FAIL.
3. A listed no-connect pin connected. The check must report FAIL. (A design with no no-connect pin gets "does not apply" here; then two of two is the full result.)
4. Record the three results here: <date, check version, the three outcomes>.

A check that passes a planted defect is a defect of the check.

## Status
| Item | Value |
|---|---|
| Intent file written by | <agent or user, date> |
| Sources named for every IC | <yes / no> |
| Check result on netlist <sha256> | <PASS / FAIL> |
| Mutation test | <3 of 3 failed as expected> |
