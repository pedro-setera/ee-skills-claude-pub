"""Impedance of the controlled lines, computed from the widths, gaps and layers that are really on the board.

A SECOND METHOD beside the manufacturer's own impedance calculator, never a replacement for it. It uses
closed-form formulas, no field solver: expect about 10 % (the measured deviations are in the table below). Its
job is to catch what a calculator record cannot: a line that was drawn at another width, gap or layer than the
one that was calculated, a neck-down that is too long, a pair that runs apart, a pour that crept beside a line.

What it checks
    For every line of board.toml [impedance] (a net name or pattern, the kind `single` or `diff`, the target in
    ohm and the tolerance in percent):
    geometry    per net and layer: the widths used and the length at each width; the gap to copper of a reference
                net on the same layer, left and right; for a pair the gap between its two lines where they
                run side by side, the share of the length that is coupled at that gap, each line's length and
                their difference; and whether the reference layer really has copper under the line.
    impedance   from that geometry and the board's layer stack (dielectric thickness and relative
                permittivity, copper thickness), with the formula that fits:
                  surface microstrip      Hammerstad and Jensen 1980, with their strip-thickness correction
                  symmetric stripline     Wheeler 1978 (as in Wadell 1991; the section and the likeness to IPC-2141A are from memory, not confirmed)
                  offset stripline        the two half-spaces as halves of two symmetric striplines
                                          (Johnson and Graham 1993, appendix C), or the strip over the nearer
                                          plane alone: the lower of the two
                  pair on an outer layer  Kirschning and Jansen 1984 (static odd mode; differential = 2 x odd)
                  pair on an inner layer  Cohn 1955 (exact for a thin strip), each half-space as above
                  coplanar with ground    Ghione and Naldi 1987 (as in Wadell 1991; section number from memory), used when copper of
                                          a reference net lies on both sides closer than coplanar_within
                                          widths; the lower of this and the microstrip value is taken
                Where two formulas are named, each leaves a part of the field out and therefore reads high
                outside its range: the lower value is the nearer one. Copper thickness enters the stripline,
                pair and coplanar formulas as a wider strip and a narrower gap. Solder mask is NOT in any
                formula: a coat of 0.02 mm lowers a surface line by about 0.5 to 5 % and a surface pair by
                about 4 to 6 % (field solution in the tests; said in the report when the stack has a mask).
    names       an entry of a line's `nets` that matches no net of the board is a finding, exit code 1 ("listed
                net <entry> is not on the board: a name that matches nothing checks nothing"), also when it is
                one of several and also when nothing matches: a typing error must not drop a line from the
                check silently. Only a board with no [impedance] line at all ends "No controlled line
                declared" with exit code 0.
    verdict     PASS inside the tolerance, FAIL outside, for the main width of each net and layer and for
                every stretch at another width that is longer than neck_max_mm (shorter ones are listed with
                their own impedance: GEN-42). UNKNOWN (never a pass) where no formula fits: copper of a
                reference net on one side only, a pair with ground beside it that would change the result, a
                line without copper below it, a geometry outside the range a formula was fitted for.

Why it exists (the real failures, told without names)
    A reviewer of a dense, rule-clean board found no evidence for the impedance of any line: the calculator
    record named a width, the board had been routed at whatever fitted. A coplanar line calculated with and
    without a copper-thickness term can differ by 15 % or more: two methods side by side show such a gap, one
    alone hides it.

Measured accuracy (`python -I impedance_check.py --self-test` repeats the first part)
    Against published worked examples and exact solutions.
    Book, edition and example numbers are cited from memory and were not checked against the printed books;
    every value is re-derived in the tests from the cited formula (in the skill's development tests, not
    shipped). The one exception: the W and s of the Hong and Lancaster table are taken as remembered, and that
    table is met in the odd mode only (see below). The exact solutions are evaluated here:
      surface microstrip    Pozar, Microwave Engineering, 3rd ed., example 3.7 (er 2.20, W/d 3.081: 50 ohm)        +0.04 %
                            Pozar, 4th ed., example 3.7 (alumina er 9.9, W/d 0.9654: 50 ohm; eeff 6.665)   -0.19 %, -0.63 %
                            Ludwig and Bretchko, RF Circuit Design, example 2.5 (er 4.6, w/h 1.8477: 50 ohm)       +0.10 %
      symmetric stripline   Pozar, example 3.5 (er 2.20, b 3.2 mm, W 2.66 mm: 50 ohm)                              -0.39 %
                            Cohn 1954, exact for a thin strip, w/b 0.2, 0.5, 1.0                           -0.01 to -0.29 %
      pair, inner layer     Pozar, example 7.7 (er 2.2, W/b 0.809, S/b 0.306: Z0e 55.28, Z0o 45.23 ohm)     +0.14 %, +0.08 %
      pair, outer layer     Hong and Lancaster, Microstrip Filters for RF/Microwave Applications, section 5.2.2
                            (er 10.2, h 0.635 mm; odd mode of three pairs)                                 +0.01 to +0.77 %
      coplanar with ground  Wen 1969, exact on a thick substrate, as the limit of a far plane                       0.00 %
                            a worked FR-4 example, zero thickness (52.2 ohm)                                    -0.15 %
      offset stripline      no published worked example at hand; only the symmetric case as an identity
    Against a solution of the field (finite differences, in the tests of this script, itself within 0.5 % of
    the exact solutions) on 35 geometries a board really has, WITH copper thickness:
      surface microstrip -0.3 to +0.1 %; symmetric stripline 0.0 to +0.2 %; offset stripline +0.7 to +2.8 %;
      pair on an outer layer -1.1 to +2.1 %; pair on an inner layer +1.7 to +2.3 %;
      coplanar with ground +0.3 to +3.5 %
    Two things that were found on the way and are NOT used as references: the even-mode values of the Hong and
    Lancaster table are about 4 % above both the formula and the field; and a coplanar calculation with the
    copper thickness put into both half-spaces reads about 8 % below the field in a worked example.
    So: bare copper within about 4 % of the field in these cases. With solder mask, etching and the tolerance of
    the board material the honest figure for a real board stays "about 10 %".

Usage
    python -I impedance_check.py --project <hardware/board folder>           result in <project>/out/impedance_check.md
    python -I impedance_check.py <board.kicad_pcb> --out <folder> --single "/RF_*=50" --diff "/USB_D?=90,15"
                                 [--stackup 0.035 1.53/4.45 0.035]
    python -I impedance_check.py --self-test                                  the reference table (needs no KiCad)
    options: --single PATTERN=OHM[,TOLERANCE %], --diff PATTERN=OHM[,TOLERANCE %] (repeatable; they replace the
             lines of board.toml), --stackup (copper thickness, then thickness/er of the dielectric below it, and
             so on down to the last copper layer; only for a board file without a layer stack)
    In Git Bash a net name that starts with "/" is rewritten by the shell: set MSYS_NO_PATHCONV=1 or use PowerShell.

board.toml keys (without a board.toml the defaults apply and are printed)
    [[impedance.line]]             # one table per controlled line or group of lines
    nets = ["/USB_D+", "/USB_D-"]  # names, names without their sheet path, or patterns; a pair: its two nets
    kind = "diff"                  # "single" or "diff"
    target = 90                    # ohm (a pair: differential)
    tolerance = 15                 # percent (default 10)
    neck_max_mm = 3.0              # a stretch at another width fails only when longer than this (default 3.0;
                                   # a USB high-speed pair: as the PHY's guide says, usb.md USB-52)
    skew_max_mm = 1.0              # optional, pairs: largest difference between the two lines' lengths
    reference = { "F.Cu" = "In2.Cu" }   # optional: the reference layer of a signal layer, when it is not the
                                   # neighbouring one (a plane cut-out under an RF line)
    [impedance."/RF_*"]            # short form of the same: kind, target, tolerance
    [impedance]
    coplanar_within = 3.0          # same-layer reference copper closer than this many track widths makes the
                                   # line a coplanar one
    reference = ["GND"]            # nets whose same-layer copper counts for that (default: [fast_nets]
                                   # reference, else the net with the largest filled area, printed)
    sample_mm = 0.1                # step along the tracks
    [stackup]                      # ONLY for a board file without a layer stack (the file's own stack wins)
    copper = [0.035, 0.035]        # mm, every copper layer from top to bottom
    dielectric = [1.53]            # mm, between each two neighbouring copper layers
    epsilon_r = [4.45]             # relative permittivity of each dielectric
    mask = 0.02                    # optional: solder mask thickness, mm;  mask_epsilon_r = 3.5

Exit codes
    0  PASS: every declared line is inside its tolerance; or "No controlled line declared" (no line at all)
    1  FAIL: a line outside its tolerance, a listed net that is not on the board, or UNKNOWN (no formula fits, a
       net without its partner)
    2  CANNOT RUN: KiCad's Python not found, unreadable board, no layer stack in the board file and no [stackup]
       table, a setting that does not fit the board. Never a pass.

Not checked: the manufacturer's own stack (compare the stack printed in the report with the stack-up page of
the order); solder mask; etching (a track is narrower at its top than drawn); loss and dispersion; vias, pads
and connectors on the line; crosstalk; length matching beyond the two lines of a pair. The return path of the
same nets is return_path_check.py.
"""

from __future__ import annotations

import math
import os
import re
import sys

sys.dont_write_bytecode = True      # `python -I` ignores PYTHONDONTWRITEBYTECODE: leave no __pycache__ beside the scripts
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402
import return_path_check as rp  # noqa: E402   the layer stack, the board as plain data, the polygon index

DEFAULTS = {"coplanar_within": 3.0, "sample_mm": 0.1}
LINE_DEFAULTS = {"tolerance": 10.0, "neck_max_mm": 3.0}
ETA0 = 376.730313668                # ohm: impedance of free space
PLANE_SHARE = 0.9                   # share of a line's length that must have copper on the reference layer below
SIDE_SHARE = 0.5                    # share of a stretch that must have reference copper beside it to count as coplanar
PAIR_REACH = 5.0                    # widths: beyond this gap the two lines of a pair are not side by side
OWN_PAD = 1.0                       # mm around the net's own pads and vias where the plane below is not asked for


# ---- the formulas (plain functions: lengths in one unit, ohm out) ----------------------------------------------------------
def ellipk(k: float) -> float:
    """Complete elliptic integral of the first kind K(k), k the modulus, by the arithmetic-geometric mean."""
    k = min(abs(k), 1.0 - 1e-15)
    a, b = 1.0, math.sqrt(1.0 - k * k)
    for _ in range(60):
        a, b = (a + b) / 2, math.sqrt(a * b)
        if abs(a - b) < 1e-15 * a:
            break
    return math.pi / (2 * a)


def k_ratio(k: float) -> float:
    """K(k) / K(k'), k' = sqrt(1 - k^2)."""
    k = min(max(k, 1e-12), 1.0 - 1e-15)
    return ellipk(k) / ellipk(math.sqrt(1.0 - k * k))


def _hj_z01(u: float) -> float:
    # Hammerstad and Jensen, "Accurate Models for Microstrip Computer-Aided Design", IEEE MTT-S Digest 1980:
    # impedance of a zero-thickness microstrip in air, u = w / h
    f = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
    return ETA0 / (2 * math.pi) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))


def _hj_eeff(u: float, er: float) -> float:
    # the same paper: effective permittivity of a zero-thickness microstrip
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    return (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)


def _hj_du(u: float, th: float, er: float) -> tuple[float, float]:
    # the same paper: widening of the strip for its thickness th = t / h, in air and in the dielectric
    if th <= 0:
        return 0.0, 0.0
    du1 = th / math.pi * math.log(1 + 4 * math.e / (th * (1 / math.tanh(math.sqrt(6.517 * u))) ** 2))
    return du1, 0.5 * (1 + 1 / math.cosh(math.sqrt(max(er - 1, 0.0)))) * du1


def microstrip(w: float, h: float, t: float, er: float) -> tuple[float, float]:
    """Surface microstrip: (impedance, effective permittivity). Hammerstad and Jensen 1980, with thickness."""
    u = w / h
    du1, dur = _hj_du(u, t / h, er)
    u1, ur = u + du1, u + dur
    z = _hj_z01(ur) / math.sqrt(_hj_eeff(ur, er))
    return z, _hj_eeff(ur, er) * (_hj_z01(u1) / _hj_z01(ur)) ** 2


def _strip_dw(w: float, b: float, t: float) -> float:
    # Wheeler, "Transmission-line properties of a stripline between parallel planes", IEEE Trans. MTT-26, 1978
    # (as in Wadell, Transmission Line Design Handbook, 1991; section number from memory): widening of a strip of thickness t
    if t <= 0:
        return 0.0
    x = t / b
    m = 2 / (1 + 2 * x / (3 * (1 - x)))
    return t / math.pi * (1 - 0.5 * math.log((x / (2 - x)) ** 2 + (0.0796 * x / (w / b + 1.1 * x)) ** m))


def stripline(w: float, b: float, t: float, er: float) -> float:
    """Symmetric stripline, the strip centred between planes b apart: impedance. Wheeler 1978."""
    r = (b - t) / (w + _strip_dw(w, b, t))
    return ETA0 / (4 * math.pi * math.sqrt(er)) * math.log(1 + 4 / math.pi * r * (8 / math.pi * r + math.sqrt((8 / math.pi * r) ** 2 + 6.27)))


def stripline_exact(w: float, b: float, er: float) -> float:
    """Zero-thickness symmetric stripline, exact: Cohn, "Characteristic impedance of the shielded-strip
    transmission line", IRE Trans. MTT-2, 1954. Used as a reference only."""
    return ETA0 / (4 * math.sqrt(er)) * k_ratio(1 / math.cosh(math.pi * w / (2 * b)))


def _halves(z_of, h1: float, er1: float, h2: float, er2: float, t: float) -> tuple[float, float]:
    """A strip between two planes at different distances, in two dielectrics: each half-space is taken as half
    of a symmetric stripline with plane distance 2 h + t (Johnson and Graham, High-Speed Digital Design, 1993,
    appendix C, for one dielectric; here each half keeps its own permittivity). z_of(b, er) -> impedance of the
    symmetric line. Returns (impedance, effective permittivity)."""
    c = ca = 0.0
    for h, er in ((h1, er1), (h2, er2)):
        b = 2 * h + t
        c += math.sqrt(er) / z_of(b, er) / 2             # capacitance of one half, times the speed of light
        ca += 1.0 / z_of(b, 1.0) / 2                     # the same half in air
    return 1.0 / math.sqrt(c * ca), c / ca


def _one_plane(h1: float, er1: float, h2: float, er2: float, w: float) -> tuple[float, float]:
    """For a strip between two planes, the view from the nearer plane alone: (its distance, the permittivity
    that a strip over that one plane sees: the two materials weighted by the share of the field that lies
    between strip and plane, taken from Hammerstad and Jensen's effective permittivity)."""
    (hn, en), (_, ef) = sorted(((h1, er1), (h2, er2)))
    q = (_hj_eeff(w / hn, 4.0) - 1) / 3
    return hn, ef * (1 - q) + en * q


def offset_stripline(w: float, h1: float, er1: float, h2: float, er2: float, t: float) -> tuple[float, float]:
    """Stripline with the planes h1 above and h2 below the strip: (impedance, effective permittivity).
    Two models, each of which leaves out a part of the field and therefore reads high: the two half-spaces as
    halves of symmetric striplines (good while the planes are at similar distances), and the strip over the
    nearer plane alone, buried in board material (good when the other plane is far). The lower value is taken."""
    z, e = _halves(lambda b, er: stripline(w, b, t, er), h1, er1, h2, er2, t)
    hn, en = _one_plane(h1, er1, h2, er2, w)
    z1 = _hj_z01(w / hn + _hj_du(w / hn, t / hn, 1.0)[0]) / math.sqrt(en)
    return (z, e) if z <= z1 else (z1, en)


def coupled_microstrip(w: float, s: float, h: float, t: float, er: float) -> tuple[float, float, float, float]:
    """Edge-coupled pair on an outer layer: (even-mode impedance, odd-mode impedance, even and odd effective
    permittivity) of one line. Kirschning and Jansen, "Accurate wide-range design equations for the frequency-
    dependent characteristic of parallel coupled microstrip lines", IEEE Trans. MTT-32, 1984 (static part).
    Thickness: each strip widened and the gap narrowed by Hammerstad and Jensen's widening."""
    u, g = w / h, s / h
    _, dur = _hj_du(u, t / h, er)
    u, g = u + dur, max(g - dur, 0.1 * g)
    e0, z0 = _hj_eeff(u, er), _hj_z01(u) / math.sqrt(_hj_eeff(u, er))
    v = u * (20 + g * g) / (10 + g * g) + g * math.exp(-g)
    ae = 1 + math.log((v ** 4 + (v / 52) ** 2) / (v ** 4 + 0.432)) / 49 + math.log(1 + (v / 18.1) ** 3) / 18.7
    be = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / v) ** (-ae * be)
    ao = 0.7287 * (e0 - (er + 1) / 2) * (1 - math.exp(-0.179 * u))
    bo = 0.747 * er / (0.15 + er)
    co = bo - (bo - 0.207) * math.exp(-0.414 * u)
    do = 0.593 + 0.694 * math.exp(-0.562 * u)
    eo = ((er + 1) / 2 + ao - e0) * math.exp(-co * g ** do) + e0
    q1 = 0.8695 * u ** 0.194
    q2 = 1 + 0.7519 * g + 0.189 * g ** 2.31
    q3 = 0.1975 + (16.6 + (8.4 / g) ** 6) ** -0.387 + math.log(g ** 10 / (1 + (g / 3.4) ** 10)) / 241
    q4 = 2 * q1 / (q2 * (math.exp(-g) * u ** q3 + (2 - math.exp(-g)) * u ** -q3))
    q5 = 1.794 + 1.14 * math.log(1 + 0.638 / (g + 0.517 * g ** 2.43))
    q6 = 0.2305 + math.log(g ** 10 / (1 + (g / 5.8) ** 10)) / 281.3 + math.log(1 + 0.598 * g ** 1.154) / 5.1
    q7 = (10 + 190 * g * g) / (1 + 82.3 * g ** 3)
    q8 = math.exp(-6.5 - 0.95 * math.log(g) - (g / 0.15) ** 5)
    q9 = math.log(q7) * (q8 + 1 / 16.5)
    q10 = (q2 * q4 - q5 * math.exp(math.log(u) * q6 * u ** -q9)) / q2
    ze = z0 * math.sqrt(e0 / ee) / (1 - z0 / ETA0 * math.sqrt(e0) * q4)
    zo = z0 * math.sqrt(e0 / eo) / (1 - z0 / ETA0 * math.sqrt(e0) * q10)
    return ze, zo, ee, eo


def coupled_stripline(w: float, s: float, b: float, t: float, er: float) -> tuple[float, float]:
    """Edge-coupled pair centred between planes b apart: (even-mode, odd-mode impedance) of one line. Cohn,
    "Shielded coupled-strip transmission line", IRE Trans. MTT-3, 1955: exact for a thin strip; thickness as
    Wheeler's widening of each strip, the gap narrowed by the same amount."""
    dw = _strip_dw(w, b, t)
    w, s = w + dw, max(s - dw, 0.1 * s)
    a, c = math.tanh(math.pi * w / (2 * b)), math.tanh(math.pi * (w + s) / (2 * b))
    f = ETA0 / (4 * math.sqrt(er))
    return f / k_ratio(a * c), f / k_ratio(a / c)


def coupled_offset_stripline(w, s, h1, er1, h2, er2, t) -> tuple[float, float]:
    """Edge-coupled pair on an inner layer, planes h1 above and h2 below: (even-mode, odd-mode impedance).
    Per mode the lower of two models, as for the single offset stripline: the two half-spaces (Cohn 1955), and
    the pair over the nearer plane alone, buried in board material (Kirschning and Jansen 1984 in a uniform
    material)."""
    hn, en = _one_plane(h1, er1, h2, er2, w)
    ze1, zo1, _, _ = coupled_microstrip(w, s, hn, t, 1.0)
    ze = _halves(lambda b, er: coupled_stripline(w, s, b, t, er)[0], h1, er1, h2, er2, t)[0]
    zo = _halves(lambda b, er: coupled_stripline(w, s, b, t, er)[1], h1, er1, h2, er2, t)[0]
    return min(ze, ze1 / math.sqrt(en)), min(zo, zo1 / math.sqrt(en))


def coplanar_ground(w: float, g: float, h: float, t: float, er: float) -> tuple[float, float]:
    """Coplanar line with a ground plane h below it (conductor-backed coplanar waveguide), gap g to the ground
    on both sides: (impedance, effective permittivity). Ghione and Naldi, "Coplanar waveguides for MMIC
    applications: effect of upper shielding, conductor backing, finite-extent ground planes, and line-to-line
    coupling", IEEE Trans. MTT-35, 1987 (as in Wadell 1991; section number from memory).
    Thickness: the copper stands in the air above the board, so only the half-space ABOVE the board gets the
    wider strip and narrower gap, by 1.25 t / pi (1 + ln(4 pi w / t)) (the widening of Gupta, Garg, Bahl and
    Bhartia, Microstrip Lines and Slotlines, 2nd ed., section 7.3); the half-space below keeps the drawn sizes.
    This split is this script's own choice. Putting the widening into both half-spaces, as simple calculators do,
    reads 8 to 15 % low against a field solution (seen in the tests of this script); the split reads
    within 2 %."""
    a, b = w / 2, w / 2 + g
    r3 = k_ratio(math.tanh(math.pi * a / (2 * h)) / math.tanh(math.pi * b / (2 * h)))     # below: board material down to the plane
    if t > 0:
        d = min(1.25 * t / math.pi * (1 + math.log(4 * math.pi * w / t)), 0.9 * g)
        a, b = (w + d) / 2, (w + d) / 2 + g - d
    r1 = k_ratio(a / b)                                                                    # above: air, the copper standing in it
    return ETA0 / (2 * math.sqrt((r1 + r3) * (r1 + er * r3))), (r1 + er * r3) / (r1 + r3)


def coplanar_thick(w: float, g: float, er: float) -> float:
    """Coplanar line on a very thick substrate, zero thickness, exact: Wen, "Coplanar waveguide: a surface strip
    transmission line ...", IEEE Trans. MTT-17, 1969. Used as a reference only (the limit of coplanar_ground)."""
    return ETA0 / (4 * math.sqrt((er + 1) / 2) * k_ratio(w / (w + 2 * g)))


# ---- reference points ------------------------------------------------------------------------------------------------------
MIL = 0.0254
REFERENCES = [
    # (formula, source, how the expected value was obtained, the calculation, expected ohm, allowed deviation in %)
    ("surface microstrip", "Pozar, Microwave Engineering, 3rd ed., example 3.7: er 2.20, d 1.27 mm, W/d 3.081, zero thickness",
     "published worked example (a synthesis for 50 ohm), cited from memory", lambda: microstrip(3.081 * 1.27, 1.27, 0, 2.20)[0], 50.0, 2.0),
    ("surface microstrip", "Pozar, Microwave Engineering, 4th ed., example 3.7: alumina er 9.9, d 0.5 mm, W/d 0.9654, zero thickness",
     "published worked example (a synthesis for 50 ohm), cited from memory", lambda: microstrip(0.9654 * 0.5, 0.5, 0, 9.9)[0], 50.0, 2.0),
    ("surface microstrip", "Ludwig and Bretchko, RF Circuit Design: Theory and Applications, example 2.5: FR-4 er 4.6, h 40 mil, w/h 1.8477",
     "published worked example (a synthesis for 50 ohm), cited from memory", lambda: microstrip(1.8477 * 40 * MIL, 40 * MIL, 0, 4.6)[0], 50.0, 2.0),
    ("surface microstrip, effective permittivity", "the same example of Pozar, 4th ed.: effective permittivity 6.665",
     "published worked example, cited from memory", lambda: microstrip(0.9654 * 0.5, 0.5, 0, 9.9)[1], 6.665, 2.0),
    ("symmetric stripline", "Pozar, Microwave Engineering, example 3.5: er 2.20, b 3.2 mm, W 2.66 mm, zero thickness",
     "published worked example (a synthesis for 50 ohm), cited from memory", lambda: stripline(2.66, 3.2, 0, 2.20), 50.0, 2.0),
    ("symmetric stripline", "Cohn 1954, exact solution for a thin strip: w/b 0.2, er 4.3",
     "exact published formula, evaluated here with elliptic integrals", lambda: stripline(0.2, 1.0, 0, 4.3), stripline_exact(0.2, 1.0, 4.3), 1.0),
    ("symmetric stripline", "Cohn 1954, exact solution for a thin strip: w/b 0.5, er 4.3",
     "exact published formula, evaluated here with elliptic integrals", lambda: stripline(0.5, 1.0, 0, 4.3), stripline_exact(0.5, 1.0, 4.3), 1.0),
    ("symmetric stripline", "Cohn 1954, exact solution for a thin strip: w/b 1.0, er 4.3",
     "exact published formula, evaluated here with elliptic integrals", lambda: stripline(1.0, 1.0, 0, 4.3), stripline_exact(1.0, 1.0, 4.3), 1.0),
    ("offset stripline", "the symmetric case of the same formula: w 0.2, 0.3 above and below, er 4.3, t 0.018",
     "identity (no published worked example at hand): must equal the symmetric stripline", lambda: offset_stripline(0.2, 0.3, 4.3, 0.3, 4.3, 0.018)[0],
     stripline(0.2, 0.618, 0.018, 4.3), 0.01),
    ("pair on an inner layer, even mode", "Pozar, Microwave Engineering, example 7.7: er 2.2, b 3.2 mm, W/b 0.809, S/b 0.306: Z0e 55.28 ohm",
     "published worked example (the book takes W and S from a design program), cited from memory", lambda: coupled_stripline(0.809 * 3.2, 0.306 * 3.2, 3.2, 0, 2.2)[0], 55.28, 2.0),
    ("pair on an inner layer, odd mode", "the same example of Pozar: Z0o 45.23 ohm (differential 90.46 ohm)",
     "published worked example (the book takes W and S from a design program), cited from memory", lambda: coupled_stripline(0.809 * 3.2, 0.306 * 3.2, 3.2, 0, 2.2)[1], 45.23, 2.0),
    # The even-mode targets of the same table (82.94, 61.16, 58.18 ohm) are NOT reference points: this formula and
    # the field solution of the tests both read about 4 % below them. The check uses the odd mode only.
    ("pair on an outer layer, odd mode", "Hong and Lancaster, Microstrip Filters for RF/Microwave Applications, section 5.2.2 (er 10.2, h 0.635 mm): "
     "W 0.385, s 0.161 mm for Z0o 37.61 ohm",
     "published design table, cited from memory", lambda: coupled_microstrip(0.385, 0.161, 0.635, 0, 10.2)[1], 37.61, 3.0),
    ("pair on an outer layer, odd mode", "the same table: W 0.575, s 0.540 mm for Z0o 42.37 ohm",
     "published design table, cited from memory", lambda: coupled_microstrip(0.575, 0.540, 0.635, 0, 10.2)[1], 42.37, 3.0),
    ("pair on an outer layer, odd mode", "the same table: W 0.595, s 0.730 mm for Z0o 43.87 ohm",
     "published design table, cited from memory", lambda: coupled_microstrip(0.595, 0.730, 0.635, 0, 10.2)[1], 43.87, 3.0),
    ("pair on an outer layer", "the uncoupled limit of the same formula: gap 10 heights, w 0.3, h 0.2, er 4.4",
     "identity: both modes must approach the single line", lambda: coupled_microstrip(0.3, 2.0, 0.2, 0, 4.4)[1], microstrip(0.3, 0.2, 0, 4.4)[0], 1.0),
    # A worked example WITH copper thickness put into both half-spaces is not a reference point: its thickness term
    # reads about 8 % below a field solution of the same line (see coplanar_ground()).
    ("coplanar with ground", "a worked FR-4 example, without copper thickness: w 1.2, gap 0.3, h 1.0, er 4.3: 52.2 ohm",
     "a worked example made with the same published formula: proves the implementation, not the formula", lambda: coplanar_ground(1.2, 0.3, 1.0, 0, 4.3)[0], 52.2, 0.5),
    ("coplanar with ground", "Wen 1969, exact solution on a thick substrate: w 0.5, gap 0.2, er 4.4 (ground 100 mm below)",
     "exact published formula for the limit of a far ground plane, evaluated here", lambda: coplanar_ground(0.5, 0.2, 100.0, 0, 4.4)[0], coplanar_thick(0.5, 0.2, 4.4), 0.5),
]


def self_test() -> int:
    """Print the reference table; exit code 0 when every point is within its allowed deviation."""
    bad = 0
    print("Reference points of impedance_check.py (formula | source | how obtained | expected | computed | deviation | allowed)")
    for formula, source, how, calc, expected, allowed in REFERENCES:
        exp = expected() if callable(expected) else expected
        got = calc()
        dev = 100 * (got - exp) / exp
        ok = abs(dev) <= allowed
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'} | {formula} | {source} | {how} | {exp:.3f} | {got:.3f} | {dev:+.2f} % | {allowed:g} %")
    print(f"{'PASS' if not bad else 'FAIL'}: {len(REFERENCES) - bad} of {len(REFERENCES)} reference points within their allowed deviation")
    return 0 if not bad else 1


# ---- the lines of board.toml ---------------------------------------------------------------------------------------------
def read_lines(cfg: dict, single: list, diff: list) -> list[dict]:
    """The declared lines: [{"nets": [...], "kind", "target", "tolerance", "neck_max_mm", "skew_max_mm", "reference": {}}]."""
    raw = []
    if single or diff:
        for kind, items in (("single", single or []), ("diff", diff or [])):
            for item in items:
                pat, _, val = item.rpartition("=")
                parts = val.split(",")
                try:
                    target = float(parts[0])
                    tol = float(parts[1]) if len(parts) > 1 else None
                except ValueError:
                    pat = ""
                if not pat:
                    raise kicad_io.KicadIOError(f"--{kind} {item!r}: write PATTERN=OHM or PATTERN=OHM,TOLERANCE")
                same = next((r for r in raw if r["kind"] == kind and r["target"] == target and r.get("tolerance") == tol), None)
                if same:
                    same["nets"].append(pat)
                else:
                    raw.append({"nets": [pat], "kind": kind, "target": target, **({"tolerance": tol} if tol is not None else {})})
    else:
        lines = cfg.get("line", [])
        if not isinstance(lines, list):
            raise kicad_io.KicadIOError("board.toml: [[impedance.line]] must be an array of tables")
        raw += [dict(x) for x in lines if isinstance(x, dict)]
        raw += [dict(v, nets=[k]) for k, v in cfg.items() if isinstance(v, dict) and "target" in v]
    out = []
    for n, r in enumerate(raw, 1):
        nets = r.get("nets")
        nets = [nets] if isinstance(nets, str) else nets
        kind = r.get("kind")
        if not isinstance(nets, list) or not nets or not all(isinstance(x, str) for x in nets) or kind not in ("single", "diff"):
            raise kicad_io.KicadIOError(f"board.toml [impedance], line {n}: needs nets (a list of names or patterns) and kind = \"single\" or \"diff\"")
        line = {"nets": nets, "kind": kind, "reference": r.get("reference", {})}
        for key, default in (("target", None), ("tolerance", LINE_DEFAULTS["tolerance"]), ("neck_max_mm", LINE_DEFAULTS["neck_max_mm"]),
                             ("skew_max_mm", -1.0)):
            v = r.get(key, default)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or (key in ("target", "tolerance") and v <= 0):
                raise kicad_io.KicadIOError(f"board.toml [impedance], line {n} ({', '.join(nets)}): '{key}' must be a positive number")
            line[key] = float(v)
        if not isinstance(line["reference"], dict):
            raise kicad_io.KicadIOError(f"board.toml [impedance], line {n}: 'reference' must be a table: signal layer = \"reference layer\"")
        out.append(line)
    return out


_POL = re.compile(r"^(.*?)(_?[PN]|[+-])$")


def pair_up(nets: list) -> tuple[list, list]:
    """The pairs among net names: ([(positive, negative)], [nets without a partner]). Two nets alone are a pair
    whatever their names; more are paired by KiCad's endings (+ and -, P and N, _P and _N)."""
    if len(nets) == 2:
        return [tuple(sorted(nets, key=lambda n: (not n.endswith(("+", "P", "p")), n)))], []
    base = {}
    for n in nets:
        m = _POL.match(n)
        if m:
            base.setdefault((m.group(1), m.group(2)[:-1]), {})["p" if m.group(2)[-1] in "+P" else "n"] = n
    pairs = [(d["p"], d["n"]) for d in base.values() if len(d) == 2]
    used = {n for p in pairs for n in p}
    return pairs, [n for n in nets if n not in used]


# ---- measuring the geometry ------------------------------------------------------------------------------------------------
def weighted_mode(values: list, step: float = 0.005):
    """The most common value of [(value, weight)] in bins of `step`, refined to the weighted mean of the values
    within one step of it; None for an empty list."""
    if not values:
        return None
    bins = {}
    for v, wt in values:
        bins[round(v / step)] = bins.get(round(v / step), 0.0) + wt
    top = max(bins, key=lambda k: bins[k]) * step
    near = [(v, wt) for v, wt in values if abs(v - top) <= step]
    return sum(v * wt for v, wt in near) / sum(wt for _, wt in near)


def stretches(tracks: list) -> list:
    """Tracks of one net, layer and width as connected stretches: [(length, [track, ...])], longest first."""
    parent = list(range(len(tracks)))

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    ends = {}
    for k, t in enumerate(tracks):
        for q in (t["path"].pts[0], t["path"].pts[-1]):
            ends.setdefault((round(q[0], 3), round(q[1], 3)), []).append(k)
    for same in ends.values():
        for k in same[1:]:
            parent[find(k)] = find(same[0])
    groups = {}
    for k, t in enumerate(tracks):
        groups.setdefault(find(k), []).append(t)
    return sorted(((sum(t["path"].length for t in g), g) for g in groups.values()), key=lambda x: -x[0])


class Geometry:
    """Measures the tracks of one net on one layer at one width."""

    def __init__(self, pic, side_idx, plane_idx: dict, L):
        self.pic, self.side_idx, self.plane_idx, self.L = pic, side_idx, plane_idx, L

    def measure(self, tracks: list, w: float, partner: list, refs: list, pair: bool = False) -> dict:
        """tracks: of one net, layer and width; pair: the net is one line of a pair, and partner holds the other
        line's tracks on the same layer (none: the two never run side by side there); refs: the reference
        layers whose copper must lie under the line."""
        step = self.L["sample_mm"]
        reach = w / 2 + self.L["coplanar_within"] * w
        total = sum(t["path"].length for t in tracks)
        left, right, gaps, under = [], [], [], {r: 0.0 for r in refs}
        n_side = [0.0, 0.0]
        asked = 0.0                                                     # length where the plane below is asked for
        layer, net = tracks[0]["layer"], tracks[0]["net"]
        idx = self.side_idx.get(layer)
        own_vias = [v for v in self.pic.vias if v["net"] == net and layer in v["layers"]]
        own_pads = [p for p in self.pic.pads if p["net"] == net and layer in p["layers"]]
        for t in tracks:
            path = t["path"]
            n = max(1, int(math.ceil(path.length / step)))
            ds = path.length / n
            near = [p for p in partner if pcb_common.box_gap(p["box"], t["box"]) <= PAIR_REACH * w + p["w"]]
            bx = (t["box"][0] - OWN_PAD, t["box"][1] - OWN_PAD, t["box"][2] + OWN_PAD, t["box"][3] + OWN_PAD)
            vias = [v for v in own_vias if bx[0] - v["d"] <= v["x"] <= bx[2] + v["d"] and bx[1] - v["d"] <= v["y"] <= bx[3] + v["d"]]
            pads = [self.pic.pad_poly(p, layer) for p in own_pads if pcb_common.box_gap(p["box"], bx) == 0]
            for i in range(n):
                x, y, ux, uy = path.at((i + 0.5) * ds)
                if not (any(math.hypot(v["x"] - x, v["y"] - y) - v["d"] / 2 <= OWN_PAD for v in vias)
                        or any(rp.poly_dist(lp, x, y) <= OWN_PAD for polys in pads for lp in polys)):
                    asked += ds                                         # at its own pads and vias the plane is opened for them
                    for r in refs:
                        if self.plane_idx[r].contains(x, y):
                            under[r] += ds
                if idx is not None:
                    for k, (store, sign) in enumerate(((left, 1), (right, -1))):
                        hit = idx.nearest(x, y, reach, side=(ux, uy, sign))
                        if hit is not None:
                            store.append((max(0.0, hit[0] - w / 2), ds))
                            n_side[k] += ds
                if near:
                    best = min(((p["path"].dist(x, y) - p["w"] / 2 - w / 2, p["w"]) for p in near), key=lambda v: v[0])
                    if best[0] <= PAIR_REACH * w:
                        gaps.append((max(0.0, best[0]), ds, best[1]))
        out = {"layer": layer, "width": w, "length": total, "side": {}, "under": {r: (under[r] / asked if asked > 0 else None) for r in refs}}
        for name, store, k in (("left", left, 0), ("right", right, 1)):
            share = n_side[k] / total if total else 0.0
            out["side"][name] = {"share": share, "gap": weighted_mode(store) if store else None,
                                 "min": min((v for v, _ in store), default=None)}
        if pair:
            g = weighted_mode([(v, wt) for v, wt, _ in gaps])
            tol = max(0.02, 0.1 * g) if g is not None else 0.0
            coupled = sum(wt for v, wt, _ in gaps if g is not None and abs(v - g) <= tol)
            pw = weighted_mode([(pwid, wt) for v, wt, pwid in gaps if g is not None and abs(v - g) <= tol], 0.001)
            out["pair"] = {"gap": g, "coupled": coupled / total if total else 0.0, "beside": sum(wt for _, wt, _ in gaps) / total if total else 0.0,
                           "partner_width": pw, "min_gap": min((v for v, _, _ in gaps), default=None)}
        return out


# ---- from geometry to impedance --------------------------------------------------------------------------------------------
def _range_note(u, g=None) -> str:
    """Why a geometry lies outside what the formulas were fitted for and checked against ('' when inside). Single
    lines: width / height 0.02 to 50. Pairs on an outer layer (Kirschning and Jansen give 0.1 to 10 for both
    ratios; checked here down to 0.095): width / height and gap / height 0.095 to 10."""
    bad = []
    lo, hi = (0.02, 50.0) if g is None else (0.095, 10.0)
    if not lo <= u <= hi:
        bad.append(f"width / height {u:.3f} outside {lo:g} to {hi:g}")
    if g is not None and not lo <= g <= hi:
        bad.append(f"gap / height {g:.3f} outside {lo:g} to {hi:g}")
    return "; ".join(bad)


def compute(kind: str, geo: dict, stack, pic, line: dict, coplanar_within: float) -> dict:
    """The impedance of one measured geometry. Returns {"z": estimate, "lo", "hi": the range when no single
    formula fits (else both equal z), "formula", "notes": [...], "unknown": reason or ""}."""
    layer, w = geo["layer"], geo["width"]
    L = pic.layers
    i = L.index(layer)
    outer = i in (0, len(L) - 1)
    res = {"z": None, "lo": None, "hi": None, "formula": "", "notes": [], "unknown": ""}
    t = stack.copper_t(layer)
    if t is None:
        t = 0.0
        res["notes"].append("the stack gives no copper thickness for this layer: computed for a thin strip (reads high)")
    given = line["reference"].get(layer)
    refs = [given] if given else ([L[1] if i == 0 else L[-2]] if outer else [L[i - 1], L[i + 1]])
    hs = []
    for r in refs:
        bt = stack.between(layer, r)
        if bt["missing"] or bt["er"] is None or bt["h"] <= 0:
            res["unknown"] = f"the layer stack ({stack.source}) does not give " + (", ".join(bt["missing"]) or f"a dielectric between {layer} and {r}")
            return res
        if bt["skipped"]:
            res["notes"].append(f"reference {r} is not the neighbouring layer: {', '.join(bt['skipped'])} lies between and is taken as absent there")
        hs.append((bt["h"], bt["er"]))
    for r in refs:
        share = geo["under"].get(r)
        if share is None:
            res["notes"].append(f"the whole stretch lies within {OWN_PAD:g} mm of the net's own pads and vias: whether {r} has copper below was not asked")
        elif share < PLANE_SHARE:
            res["unknown"] = (f"the reference layer {r} has copper under only {share:.0%} of this length: the formulas assume a plane "
                              f"(see return_path_check.py; set `reference` of the line when another layer is the reference)")
            return res
    side = geo["side"]
    beside = [n for n in ("left", "right") if side[n]["share"] >= SIDE_SHARE and side[n]["gap"] is not None]
    if not outer:                                                       # ---- inner layer
        (h1, e1), (h2, e2) = hs if len(hs) == 2 else (hs[0], hs[0])
        if len(hs) == 1:
            res["notes"].append(f"only {refs[0]} is given as reference: computed as if the same plane lay at the same distance on the other side")
        sym = abs(h1 - h2) < 1e-4 and abs(e1 - e2) < 1e-6
        if beside:
            res["notes"].append("copper of a reference net lies beside the line on this inner layer (" +
                                ", ".join(f"{n} {side[n]['gap']:.3f} mm" for n in beside) + "): it lowers the impedance; not computed")
        if kind == "single":
            res["z"] = stripline(w, 2 * h1 + t, t, e1) if sym else offset_stripline(w, h1, e1, h2, e2, t)[0]
            res["formula"] = "symmetric stripline (Wheeler 1978)" if sym else "offset stripline (two half-spaces, Wheeler 1978)"
            rng = _range_note(w / (h1 + h2 + t))
        else:
            s = geo["pair"]["gap"]
            if s <= 0:
                res["unknown"] = "the two lines of the pair touch (gap 0)"
                return res
            w2 = (w + (geo["pair"]["partner_width"] or w)) / 2
            zo = coupled_stripline(w2, s, 2 * h1 + t, t, e1)[1] if sym else coupled_offset_stripline(w2, s, h1, e1, h2, e2, t)[1]
            res["z"] = 2 * zo
            res["formula"] = "edge-coupled stripline pair (Cohn 1955" + ("" if sym else ", two half-spaces") + ")"
            rng = _range_note(w2 / (h1 + h2 + t))
        res["lo"] = res["hi"] = res["z"]
        if rng:
            res["unknown"] = "outside the range of the formula: " + rng
        return res
    h, er = hs[0]                                                       # ---- outer layer
    mask = stack.mask(i == 0)
    if mask and mask[0]:
        res["notes"].append(f"solder mask ({mask[0]:g} mm" + (f", er {mask[1]:g}" if mask[1] else "") + ") is not in the formula: the real value is "
                            + ("about 4 to 6 % lower" if kind == "diff" else "about 0.5 to 5 % lower") + " (a 0.02 mm coat in a field solution)")
    z_ms = microstrip(w, h, t, er)[0]
    if kind == "single":
        if len(beside) == 2:
            gl, gr = side["left"]["gap"], side["right"]["gap"]
            g = (gl + gr) / 2
            z_cp = coplanar_ground(w, g, h, t, er)[0]
            res["z"] = min(z_cp, z_ms)
            res["lo"] = res["hi"] = res["z"]
            res["formula"] = (f"coplanar with ground, gap {g:.3f} mm (Ghione and Naldi 1987)" if z_cp < z_ms else
                              f"surface microstrip (Hammerstad and Jensen 1980); the copper beside it at {g:.3f} mm does not lower it in this model")
            res["notes"].append(f"as a plain microstrip this width reads {z_ms:.1f} ohm; as a coplanar line with ground {z_cp:.1f} ohm; the lower one is taken")
            if abs(gl - gr) > 0.25 * g:
                z2 = [min(coplanar_ground(w, x, h, t, er)[0], z_ms) for x in (gl, gr)]
                res["lo"], res["hi"] = min(z2), max(z2)
                res["notes"].append(f"the gaps differ (left {gl:.3f}, right {gr:.3f} mm): the range is for the smaller and the larger gap on both sides")
            if g <= 0 or coplanar_ground(w, g, h, 0, er)[0] <= 0:
                res["unknown"] = "the gap to the copper beside the line is zero"
        elif len(beside) == 1:
            g = side[beside[0]]["gap"]
            z_cp = min(coplanar_ground(w, g, h, t, er)[0], z_ms)
            res["lo"], res["hi"] = z_cp, z_ms
            res["z"] = 2 * z_cp * z_ms / (z_cp + z_ms)
            res["formula"] = f"between coplanar with ground (gap {g:.3f} mm on both sides) and surface microstrip"
            res["notes"].append(f"copper of a reference net lies on the {beside[0]} side only ({g:.3f} mm): no closed formula; the value lies between "
                                f"{z_cp:.1f} ohm (the same gap on both sides) and {z_ms:.1f} ohm (none)")
        else:
            res["z"] = res["lo"] = res["hi"] = z_ms
            res["formula"] = "surface microstrip (Hammerstad and Jensen 1980)"
        rng = _range_note(w / h)
    else:
        s = geo["pair"]["gap"]
        if s <= 0:
            res["unknown"] = "the two lines of the pair touch (gap 0)"
            return res
        w2 = (w + (geo["pair"]["partner_width"] or w)) / 2
        _, zo, _, _ = coupled_microstrip(w2, s, h, t, er)
        res["z"] = res["lo"] = res["hi"] = 2 * zo
        res["formula"] = "edge-coupled microstrip pair (Kirschning and Jansen 1984)"
        if beside:
            g = min(side[n]["gap"] for n in beside)
            ratio = min(1.0, coplanar_ground(w2, g, h, t, er)[0] / microstrip(w2, h, t, er)[0])
            res["lo"] = 2 * zo * ratio
            res["z"] = 2 * zo * (3 + ratio) / 4
            res["notes"].append(f"copper of a reference net lies beside the pair ({g:.3f} mm): a coplanar pair is not computed; the value lies between "
                                f"{res['lo']:.1f} ohm (the single-line ratio of a coplanar line to a microstrip applied in full) and {res['hi']:.1f} ohm (no effect)")
        rng = _range_note(w2 / h, s / h)
    if rng and not res["unknown"]:
        res["unknown"] = "outside the range of the formula: " + rng
    return res


def judge(res: dict, target: float, tol: float) -> str:
    if res["unknown"] or res["z"] is None:
        return "UNKNOWN"
    lo_ok = abs(res["lo"] - target) <= tol * target / 100 + 1e-9
    hi_ok = abs(res["hi"] - target) <= tol * target / 100 + 1e-9
    if lo_ok and hi_ok:
        return "PASS"
    if (res["lo"] > target and res["hi"] > target) or (res["lo"] < target and res["hi"] < target):
        if not lo_ok and not hi_ok:
            return "FAIL"
    return "UNKNOWN"


# ---- the check -------------------------------------------------------------------------------------------------------------
def _stack_arg(vals: list, layers: list) -> dict:
    """--stackup 0.035 1.53/4.45 0.035 -> the [stackup] table."""
    cu, di, er = [], [], []
    try:
        for k, v in enumerate(vals):
            if k % 2 == 0:
                cu.append(float(v))
            else:
                a, _, b = v.partition("/")
                di.append(float(a))
                er.append(float(b))
    except ValueError:
        raise kicad_io.KicadIOError("--stackup: write copper thickness, then thickness/er of the dielectric below it, and so on: "
                                    "0.035 1.53/4.45 0.035") from None
    return {"copper": cu, "dielectric": di, "epsilon_r": er}


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    ap = pcb_common.io_parser("Impedance of the controlled lines from the widths, gaps and layers on the board: a second method beside "
                              "the manufacturer's calculator (closed-form formulas, about 10 %).",
                              epilog="Exit codes: 0 pass (or no controlled line declared), 1 a line outside its tolerance or UNKNOWN, 2 could not run.")
    ap.add_argument("--single", action="append", metavar="PATTERN=OHM[,TOL]", help="a single-ended line (repeatable)")
    ap.add_argument("--diff", action="append", metavar="PATTERN=OHM[,TOL]", help="a pair: the pattern matches its two nets (repeatable)")
    ap.add_argument("--stackup", nargs="+", metavar="VALUE", help="for a board file without a layer stack: 0.035 1.53/4.45 0.035")
    ap.add_argument("--self-test", action="store_true", help="print the reference table of the formulas and stop")
    a = ap.parse_args(argv)
    kicad_io.need_kicad_python()
    pcb_common.quiet_wx()                                               # no message box, ever: warnings go to stderr
    job = pcb_common.resolve(a)
    cfg = job.cfg("impedance")
    L = pcb_common.Limits(cfg, DEFAULTS)
    if L["coplanar_within"] < 0 or not 0 < L["sample_mm"] <= 1.0:
        raise kicad_io.KicadIOError("settings out of range: coplanar_within not negative, sample_mm in (0, 1]")
    lines = read_lines(cfg, a.single, a.diff)
    title = "Impedance of the controlled lines, from the board's own widths, gaps and layer stack"
    head = ("A second method beside the manufacturer's impedance calculator, never a replacement for it: closed-form formulas, no field "
            "solver, about 10 % (the measured deviations at reference points: `impedance_check.py --self-test`). Where the two "
            "disagree by more than the tolerance, stop and find out why.")
    data = {"script": "impedance_check.py", "board": os.path.basename(job.board), "sha256": kicad_io.sha256(job.board),
            "declared": bool(lines), "limits": L.to_dict(), "lines": [], "rows": [], "failures": [], "unknown": [], "notes": []}
    with pcb_common.work_copy(job.board, "impedance-") as copy:
        pic = rp.Picture(kicad_io.load_board(copy))
        matched = []
        for ln in lines:
            nets, dead = rp.match_nets(ln["nets"], pic.nets)
            matched.append((ln, nets, dead))
        # a listed name that matches nothing is a finding: a typing error must not drop a line from the check silently
        missing = [f"listed net {d} is not on the board: a name that matches nothing checks nothing" for _, _, dead in matched for d in dead]
        if not lines:                                                   # no line at all: nothing to compute, and that is said
            why = "board.toml has no [impedance] table and no --single or --diff was given"
            first = f"**No controlled line declared**: {why}. Nothing was computed."
            md = [f"# {title}", "", first, "", head, ""] + pcb_common.header(title, job, "impedance_check.py")[2:] + \
                 ["**Result: PASS** (no controlled line declared)"]
            data.update(result="PASS", declared=False, why=why)
            p_md, _ = pcb_common.write_result(job.out, "impedance_check", md, data)
            print(f"PASS: no controlled line declared ({why}) -> {p_md}")
            return 0
        if not any(nets for _, nets, _ in matched):                     # lines, and not one of their nets is on the board
            first = (f"**Result: FAIL**: none of the nets of the {len(lines)} declared line(s) is on the board "
                     f"({'; '.join(', '.join(ln['nets']) for ln in lines)}): nothing was computed. Check the spelling against the board's net names.")
            md = [f"# {title}", "", first, "", head, ""] + pcb_common.header(title, job, "impedance_check.py")[2:] + \
                 ["## Findings", ""] + [f"- FAIL: {x}" for x in missing] + ["", first]
            data.update(result="FAIL", failures=missing,
                        lines=[{"nets_declared": ln["nets"], "kind": ln["kind"], "target": ln["target"], "tolerance": ln["tolerance"],
                                "nets": [], "unmatched": dead} for ln, _, dead in matched])
            p_md, _ = pcb_common.write_result(job.out, "impedance_check", md, data)
            for x in missing:
                print("FAIL ", x)
            print(f"FAIL: 0 geometry row(s); {len(missing)} listed name(s) match no net -> {p_md}")
            return 1
        settings = dict(job.settings)
        if a.stackup:
            settings["stackup"] = _stack_arg(a.stackup, pic.layers)
        stack, stack_note = rp.read_stack(job.board, settings, pic.layers)
        if stack is None:
            raise kicad_io.KicadIOError(f"{stack_note}: the impedance cannot be computed without dielectric thickness and relative permittivity. "
                                        f"Enter the stack in KiCad's board setup, or write [stackup] into board.toml (see --help)")
        if len(pic.layers) < 2:
            raise kicad_io.KicadIOError("the board has one copper layer: there is no reference plane to compute against")
        wanted_ref = cfg.get("reference") or job.cfg("fast_nets").get("reference") or []
        if not isinstance(wanted_ref, list):
            raise kicad_io.KicadIOError("board.toml [impedance]: 'reference' must be a list of net names")
        ref_nets, ref_how = rp.reference_nets(pic, wanted_ref)
        all_nets = [n for _, nets, _ in matched for n in nets]
        side_idx, plane_idx = {}, {}
        for layer in {t["layer"] for t in pic.tracks if t["net"] in all_nets}:
            polys = pic.merged([n for n in ref_nets if n not in all_nets], layer) if ref_nets else []
            side_idx[layer] = rp.PolyIndex(polys) if polys else None
        for layer in pic.layers:
            plane_idx[layer] = rp.PolyIndex(pic.merged(None, layer, items=False))
        geo = Geometry(pic, side_idx, plane_idx, L)
        rows, fails, unknown, notes = [], list(missing), [], []
        if stack_note:
            notes.append(stack_note)
        for ln, nets, dead in matched:
            label = ", ".join(ln["nets"])
            entry = {"nets_declared": ln["nets"], "kind": ln["kind"], "target": ln["target"], "tolerance": ln["tolerance"],
                     "neck_max_mm": ln["neck_max_mm"], "nets": nets, "unmatched": dead, "pairs": [], "lengths": {}}
            data["lines"].append(entry)
            if not nets:
                continue
            named = {}
            for k, v in ln["reference"].items():
                la, lb = pic.layer_name(k), pic.layer_name(v)
                if la is None or lb is None or la == lb:
                    raise kicad_io.KicadIOError(f"board.toml [impedance], line {label}: reference \"{k}\" = \"{v}\" does not fit the board's "
                                                f"copper layers ({', '.join(pic.layers)})")
                named[la] = lb
            ln["reference"] = named
            if ln["kind"] == "diff":
                pairs, alone = pair_up(nets)
                for n in alone:
                    unknown.append(f"{n}: declared as part of a pair ({label}) but no partner net was found (endings + and -, P and N, _P and _N)")
                units = [(p, q) for p, q in pairs] + [(q, p) for p, q in pairs]
                for p, q in pairs:
                    lp = sum(t["path"].length for t in pic.tracks if t["net"] == p)
                    lq = sum(t["path"].length for t in pic.tracks if t["net"] == q)
                    entry["pairs"].append({"positive": p, "negative": q, "length_positive": round(lp, 3), "length_negative": round(lq, 3),
                                           "difference": round(abs(lp - lq), 3)})
                    if ln["skew_max_mm"] >= 0 and abs(lp - lq) > ln["skew_max_mm"] + 1e-9:
                        fails.append(f"pair {p} / {q}: the two lines differ by {abs(lp - lq):.2f} mm in length (limit {ln['skew_max_mm']:g} mm; "
                                     f"{lp:.2f} and {lq:.2f} mm, tracks only)")
            else:
                units = [(n, None) for n in nets]
            for net, partner in units:
                mine = [t for t in pic.tracks if t["net"] == net]
                entry["lengths"][net] = round(sum(t["path"].length for t in mine), 3)
                if not mine:
                    unknown.append(f"{net}: declared ({label}) but it has no track on the board")
                    continue
                for layer in [n for n in pic.layers if any(t["layer"] == n for t in mine)]:
                    on = [t for t in mine if t["layer"] == layer]
                    by_w = {}
                    for t in on:
                        by_w.setdefault(round(t["w"], 4), []).append(t)
                    main_w = max(by_w, key=lambda w: sum(t["path"].length for t in by_w[w]))
                    i = pic.layers.index(layer)
                    given = ln["reference"].get(layer)
                    refs = [given] if given else ([pic.layers[1] if i == 0 else pic.layers[-2]] if i in (0, len(pic.layers) - 1)
                                                   else [pic.layers[i - 1], pic.layers[i + 1]])
                    for w in sorted(by_w, key=lambda w: -sum(t["path"].length for t in by_w[w])):
                        other = [t for t in pic.tracks if t["net"] == partner and t["layer"] == layer] if partner else []
                        g = geo.measure(by_w[w], w, other, refs, pair=bool(partner))
                        parts = stretches(by_w[w])
                        longest = parts[0][0]
                        mid = parts[0][1][0]["path"].at(parts[0][1][0]["path"].length / 2)
                        if partner and (g["pair"]["gap"] is None or g["pair"]["coupled"] <= 0):
                            res = {"z": None, "lo": None, "hi": None, "formula": "", "notes": [],
                                   "unknown": f"no stretch of {partner} runs beside it on {layer} within {PAIR_REACH:g} widths: not a coupled pair here"}
                        else:
                            res = compute(ln["kind"], g, stack, pic, ln, L["coplanar_within"])
                        v = judge(res, ln["target"], ln["tolerance"])
                        is_main = w == main_w
                        short_neck = not is_main and longest <= ln["neck_max_mm"] + 1e-9
                        state = v if not short_neck else ("PASS" if v == "PASS" else "listed")
                        row = {"line": label, "kind": ln["kind"], "net": net, "partner": partner, "layer": layer, "width": w, "main_width": main_w,
                               "length": g["length"], "longest_stretch": longest, "stretches": len(parts), "at": (mid[0], mid[1]),
                               "geo": g, "res": res, "verdict": v, "state": state, "target": ln["target"], "tolerance": ln["tolerance"],
                               "refs": refs, "neck_max_mm": ln["neck_max_mm"]}
                        rows.append(row)
                        what = (f"{net}" + (f" (pair with {partner})" if partner else "") + f" on {layer}: {g['length']:.2f} mm at width {w:g} mm"
                                + ("" if is_main else f" (main width {main_w:g} mm; longest stretch {longest:.2f} mm at ({mid[0]:.2f}, {mid[1]:.2f}))"))
                        if state == "FAIL":
                            rng = f"{res['z']:.1f}" if res["lo"] == res["hi"] else f"{res['lo']:.1f} to {res['hi']:.1f}"
                            fails.append(f"{what}: {rng} ohm{' differential' if partner else ''}, target {ln['target']:g} ohm +-{ln['tolerance']:g} % "
                                         f"({res['formula']})")
                        elif state == "UNKNOWN":
                            unknown.append(f"{what}: " + (res["unknown"] or f"{res['lo']:.1f} to {res['hi']:.1f} ohm, target {ln['target']:g} ohm "
                                                                             f"+-{ln['tolerance']:g} %: the range crosses the limit; " + "; ".join(res["notes"][-1:])))
    # ---- the report
    result = pcb_common.verdict(len(fails), len(unknown))
    n_pass = sum(1 for r in rows if r["state"] == "PASS")
    first = (f"**Result: {result}**: {len(rows)} geometry row(s) of {len({r['net'] for r in rows})} net(s); {n_pass} inside the tolerance, "
             f"{len(fails)} finding(s), {len(unknown)} UNKNOWN.")
    md = [f"# {title}", "", first, "", head, ""] + pcb_common.header(title, job, "impedance_check.py")[2:]
    md += ["Settings:", ""] + L.table() + ["", f"Layer stack ({stack.source}); compare it with the manufacturer's stack-up page for the order:", ""] + stack.rows()
    md += ["", f"Copper of these nets on a line's own layer makes it a coplanar line when it is closer than {L['coplanar_within']:g} widths: "
               f"{', '.join(f'`{n}`' for n in ref_nets) or 'none'} ({ref_how}).", "", "## Declared lines", "",
           "| Line (nets or patterns) | Kind | Target (ohm) | Tolerance | Nets on the board | Stretch at another width fails when longer than (mm) |", "|---|---|---|---|---|---|"]
    for e in data["lines"]:
        md.append(f"| {', '.join(e['nets_declared'])} | {e['kind']} | {e['target']:g} | +-{e['tolerance']:g} % | {', '.join(e['nets']) or 'none'} | {e['neck_max_mm']:g} |")
    md += ["", "## Geometry found and impedance", "",
           "Per net, layer and width. Side gap: to copper of a reference net on the same layer (the usual gap along the stretch; `-` when "
           "less than half of the stretch has such copper within reach). Under: share of the length with copper on the reference layer below "
           f"(any net), not counting the {OWN_PAD:g} mm around the net's own pads and vias. A pair is listed once from each of its two lines.", "",
           "| Net | Layer | Width (mm) | Length (mm) | Longest stretch (mm) | Reference layer: under | Side gap left / right (mm) | Pair gap (mm) | Coupled share "
           "| Formula | Result (ohm) | Target (ohm) | Verdict |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        g, res = r["geo"], r["res"]
        sd = " / ".join(f"{g['side'][n]['gap']:.3f}" if g["side"][n]["share"] >= SIDE_SHARE and g["side"][n]["gap"] is not None else "-" for n in ("left", "right"))
        pr = g.get("pair")
        z = "-" if res["z"] is None or res["unknown"] else (f"{res['z']:.1f}" if res["lo"] == res["hi"] else f"{res['lo']:.1f} to {res['hi']:.1f}")
        verdict = {"PASS": "PASS", "FAIL": "FAIL", "UNKNOWN": "UNKNOWN: " + (res["unknown"] or "the range crosses the limit"),
                   "listed": f"listed: {r['verdict']} for a stretch of {r['longest_stretch']:.2f} mm, not longer than {r['neck_max_mm']:g} mm"}[r["state"]]
        md.append(f"| {r['net']} | {r['layer']} | {r['width']:g}{'' if r['width'] == r['main_width'] else ' (main ' + format(r['main_width'], 'g') + ')'} | "
                  f"{r['length']:.2f} | {r['longest_stretch']:.2f} | {', '.join(f'{k}: ' + ('not asked' if v is None else format(v, '.0%')) for k, v in g['under'].items())} | {sd} | "
                  f"{'-' if not pr or pr['gap'] is None else format(pr['gap'], '.3f')} | {'-' if not pr else format(pr['coupled'], '.0%')} | "
                  f"{res['formula'] or '-'} | {z} | {r['target']:g} +-{r['tolerance']:g} % | {verdict} |")
        data["rows"].append({"line": r["line"], "kind": r["kind"], "net": r["net"], "partner": r["partner"], "layer": r["layer"], "width": r["width"],
                             "main_width": r["main_width"], "length": round(r["length"], 3), "longest_stretch": round(r["longest_stretch"], 3),
                             "stretches": r["stretches"], "at": [round(v, 3) for v in r["at"]], "reference_layers": r["refs"],
                             "under": {k: (None if v is None else round(v, 3)) for k, v in g["under"].items()},
                             "side": {n: {"share": round(g["side"][n]["share"], 3), "gap": None if g["side"][n]["gap"] is None else round(g["side"][n]["gap"], 4),
                                          "min": None if g["side"][n]["min"] is None else round(g["side"][n]["min"], 4)} for n in ("left", "right")},
                             "pair": None if not pr else {k: (None if v is None else round(v, 4)) for k, v in pr.items()},
                             "formula": res["formula"], "ohm": None if res["z"] is None else round(res["z"], 2),
                             "ohm_low": None if res["lo"] is None else round(res["lo"], 2), "ohm_high": None if res["hi"] is None else round(res["hi"], 2),
                             "target": r["target"], "tolerance": r["tolerance"], "verdict": r["state"], "why_unknown": res["unknown"], "notes": res["notes"]})
    pairs = [p for e in data["lines"] for p in e["pairs"]]
    if pairs:
        md += ["", "## Pairs: length of each line (tracks only, vias not counted)", "",
               "| Positive | Negative | Length positive (mm) | Length negative (mm) | Difference (mm) |", "|---|---|---|---|---|"]
        md += [f"| {p['positive']} | {p['negative']} | {p['length_positive']:.2f} | {p['length_negative']:.2f} | {p['difference']:.2f} |" for p in pairs]
    row_notes = []
    for r in rows:
        for n in r["res"]["notes"]:
            text = f"{r['net']} on {r['layer']}, width {r['width']:g} mm: {n}"
            if text not in row_notes:
                row_notes.append(text)
    if fails or unknown or notes or row_notes:
        md += ["", "## Findings", ""] + [f"- FAIL: {x}" for x in fails] + [f"- UNKNOWN: {x}" for x in unknown] + \
              [f"- note: {x}" for x in notes] + [f"- note: {x}" for x in row_notes]
    md += ["", "## Not checked", "",
           "The manufacturer's own stack (compare the table above with the stack-up page of the order); solder mask; etching (a track is "
           "narrower at its top than drawn); loss and dispersion; vias, pads and connectors on the line; crosstalk; length matching beyond "
           "the two lines of a pair; the return path (`return_path_check.py`). A result here does not replace the manufacturer's calculator record.",
           "", first]
    data.update(result=result, stack=stack.to_list(), stack_source=stack.source, reference_nets=ref_nets, failures=fails, unknown=unknown,
                notes=notes + row_notes)
    p_md, _ = pcb_common.write_result(job.out, "impedance_check", md, data)
    for x in fails[:30]:
        print("FAIL ", x)
    for x in unknown[:30]:
        print("UNKNOWN ", x)
    shown = "; ".join(f"{kicad_io.leaf(r['net'])} {r['layer']} w {r['width']:g}: " + (f"{r['res']['z']:.1f} ohm" if r["res"]["z"] is not None and not r["res"]["unknown"] else "?")
                      for r in rows if r["width"] == r["main_width"])[:300]
    print(f"{result}: {len(rows)} geometry row(s), {len(fails)} finding(s), {len(unknown)} UNKNOWN; {shown} -> {p_md}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
