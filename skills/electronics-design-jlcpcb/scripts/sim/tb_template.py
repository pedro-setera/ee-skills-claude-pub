"""Test bench skeleton: copy it to <project>/sim/tb_<block>.py and replace the example by the block's own tests.

How a bench is built (keep this order; it is what makes the results worth something)
    1. THE LIMITS FIRST. Every test is declared at the top with its question and its pass limits, each limit with
       the place it comes from (a requirement, a datasheet page). They are the rows of sim/PLAN.md, copied here
       before the first run. A limit is a number with a unit at the point where the specification applies. It is
       never changed after a run: a test that fails changes the design, or becomes a named deviation that the user
       accepts. A limit so wide that the test cannot fail is not a limit.
    2. The netlists: the real circuit with its real values, written as functions so that corners can be run.
       Capacitors at their DC-bias value, inductors with their resistance, real sources (cable, current limit),
       real loads. Every model names its source in a comment. Quote every path in an .include line.
    3. One measure function per test: it runs the simulation, writes the plot, and returns the measured numbers.
       It does not judge. ngs.run() raises when the run did not converge: such a test has no numbers.
    4. ngs.run_tests() judges each test against its declared limits, prints one line per test and writes
       out/<bench>_results.json. Exit code 0 only when every test passes.
    Then: open every plot, write what you saw into sim/RESULTS.md, and copy the limits there unchanged.

    Test IDs have the form SIM-<nn>. Plot files are named by the test ID.

A maker's model (a file from a maker's site, kept in sim/models/ with its source and date)
    - The runner scans the netlist and every file it includes before the simulator sees them, and REFUSES a file
      that carries commands or names files outside sim/ (exit code 2). Check a model the moment it is
      downloaded:  python -I <skill>/scripts/sim/ngs.py scan sim/models/<file>
    - A model written for PSpice or LTspice: set COMPAT below (ps or psa for PSpice, lt or lta for LTspice,
      ltps or ltpsa for both; the final "a" also translates this bench's own netlist). Every result states the
      mode. A mode changes numbers, so the first test of such a bench is a calibration: the bench reproduces
      one figure of the part's datasheet at the datasheet's conditions, with the limit
          ngs.calibration("v_ref", datasheet=2.495, tolerance=0.055, unit="V", source="<document>, table <n>")
      Only when that row passes are the other rows of this model worth reading.

Run it
    python -I tb_<block>.py [--out <folder>] [--runner <skill>/scripts/sim] [--compat <mode>]
    or the whole suite at once, all cores:   python -I <skill>/scripts/sim/ngs.py suite <project>/sim
    The bench finds the runner (ngs.py, plot.py) through --runner, the environment variable SIM_RUNNER (set by
    `suite`), or its own folder.
    The mode in force: this bench's own --compat; else COMPAT when it is not "off"; else the mode of
    `ngs.py suite --compat` (handed on in SIM_COMPAT); else off.

The example below is a complete, working bench of a generic RC low-pass: replace it.
Exit codes: 0 every test PASS; 1 a test FAIL or NOT CONVERGED; 2 CANNOT RUN (no ngspice, runner not found).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.splitext(os.path.basename(__file__))[0]


def _find_runner() -> None:
    """Make ngs.py and plot.py importable: --runner, SIM_RUNNER, or this folder."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--runner")
    known, _ = ap.parse_known_args()
    for folder in (known.runner, os.environ.get("SIM_RUNNER"), HERE):
        if folder and os.path.isfile(os.path.join(folder, "ngs.py")):
            if folder not in sys.path:
                sys.path.insert(0, folder)
            return
    print("CANNOT RUN: the simulation runner (ngs.py) was not found; give --runner <skill>/scripts/sim or set "
          "SIM_RUNNER", file=sys.stderr)
    sys.exit(2)


_find_runner()
import ngs  # noqa: E402
import plot  # noqa: E402

OUT = os.path.join(HERE, "out")
COMPAT = "off"          # ngspice compatibility mode of this bench: off, ps, psa, lt, lta, ltps or ltpsa (see above);
                        # a mode other than off wins over `ngs.py suite --compat`

# =====================================================================================================================
# 1. The circuit values of this block (from the schematic; say where each comes from)
# =====================================================================================================================
V_STEP = 5.0            # V, the source's nominal voltage (requirement R-xx)
R = 1000.0              # ohm, 1 % part
C = 1.0e-6              # F at its DC bias (maker's curve, page n), not the nominal value
TAU = R * C


# =====================================================================================================================
# 2. Netlists, as functions of the corner that is run
# =====================================================================================================================
def rc_netlist(r: float = R, c: float = C, v: float = V_STEP) -> str:
    return f"""RC low-pass, step from 0 to {v} V in 1 ns
* ideal source: say so; a real source would add its cable and its current limit
V1 in 0 PWL(0 0 1n {v})
R1 in out {r}
C1 out 0 {c}
.tran {TAU / 100} {5 * TAU}
"""


# =====================================================================================================================
# 3. Measure functions: run, plot, return numbers. They do not judge.
# =====================================================================================================================
def measure_step() -> dict:
    np = ngs.numpy()
    r = ngs.run(rc_netlist(), ["v(out)", "v(in)"])
    t, v = r["time"], r["v(out)"]
    plot.panels(os.path.join(OUT, "SIM-01.png"), r, [["v(out)", "v(in)"]],
                "SIM-01: RC step response, nominal values",
                labels={"v(out)": "V_OUT (V)", "v(in)": "V_IN (V)"},
                limits={"v(out)": [(0.99 * V_STEP, "settled: 99 % of the step")]},
                events=[(TAU, "one time constant"), (5 * TAU, "end")])
    return {"v_out_at_tau": float(np.interp(TAU, t, v)), "v_out_end": float(v[-1]),
            "overshoot": float(v.max() - V_STEP)}


def measure_corners() -> dict:
    """The same step at the tolerance corners, all at once: each corner in its own process."""
    np = ngs.numpy()
    corners = {"slow (R +1 %, C +20 %)": (R * 1.01, C * 1.2), "fast (R -1 %, C -20 %)": (R * 0.99, C * 0.8)}
    res = ngs.run_many([{"name": k, "netlist": rc_netlist(r, c), "vectors": ["v(out)"]} for k, (r, c) in corners.items()])
    bad = [x for x in res if not x["_converged"]]
    if bad:
        raise ngs.ConvergenceError("corner run without a result: " + "; ".join(f"{x['_name']}: {x['_error']}" for x in bad))
    slow, fast = res
    plot.xy(os.path.join(OUT, "SIM-02.png"),
            [(x["time"] * 1e3, x["v(out)"], x["_name"]) for x in res],
            "SIM-02: RC step response at the tolerance corners", "time (ms)", "V_OUT (V)",
            hlines=[(0.95 * V_STEP, "95 % of the step")], vlines=[(4.0, "4 ms: the limit applies here")])
    return {"v_out_at_4ms_slow": float(np.interp(4e-3, slow["time"], slow["v(out)"])),
            "v_out_at_4ms_fast": float(np.interp(4e-3, fast["time"], fast["v(out)"]))}


# =====================================================================================================================
# 4. THE TESTS AND THEIR LIMITS: written before the first run, copied from sim/PLAN.md, never moved afterwards
# =====================================================================================================================
TESTS = [
    ngs.Test(
        id="SIM-01",
        question="Does the output follow the step as the formula says, without overshoot?",
        limits=(
            ngs.Limit("v_out_at_tau", lo=V_STEP * (1 - math.exp(-1)) - 0.02, hi=V_STEP * (1 - math.exp(-1)) + 0.02,
                      unit="V", why="first-order response at one time constant, +/- 20 mV"),
            ngs.Limit("overshoot", hi=0.005, unit="V", why="a first-order network cannot overshoot"),
            ngs.Limit("v_out_end", lo=0.99 * V_STEP, unit="V", why="settled within 1 % after five time constants"),
        ),
        measure=measure_step, plot="SIM-01.png"),
    ngs.Test(
        id="SIM-02",
        question="Is the output above 95 % of the step after 4 ms at both tolerance corners?",
        limits=(
            ngs.Limit("v_out_at_4ms_slow", lo=0.95 * V_STEP, unit="V", why="requirement R-xx: ready within 4 ms"),
            ngs.Limit("v_out_at_4ms_fast", lo=0.95 * V_STEP, unit="V", why="requirement R-xx: ready within 4 ms"),
        ),
        measure=measure_corners, plot="SIM-02.png"),
]


def main() -> int:
    global OUT
    ap = argparse.ArgumentParser(description=f"Test bench {BENCH}: limits first, then the run.")
    ap.add_argument("--out", default=OUT, help="folder for the plots and the results file")
    ap.add_argument("--runner", help="folder of ngs.py and plot.py")
    ap.add_argument("--compat", help="run in this compatibility mode: it wins over the bench's own COMPAT and over "
                                     "the mode of `ngs.py suite --compat`; the results state the mode that was in force")
    a = ap.parse_args()
    OUT = os.path.abspath(a.out)
    os.makedirs(OUT, exist_ok=True)
    own = COMPAT if COMPAT and COMPAT != "off" else None        # a bench's own mode wins over `suite --compat`
    return ngs.run_tests(BENCH, TESTS, OUT, compat=a.compat or own)    # None: the suite's mode (SIM_COMPAT), else off


if __name__ == "__main__":
    sys.exit(main())
