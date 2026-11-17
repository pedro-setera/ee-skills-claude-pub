"""Hand-stiffness estimate of a flat panel, a flange or an angle section under a point load.

What it does
    For each `[[item]]` of a TOML computes the deflection under a point load (default 20 N, a firm push with a finger) and compares it
    with a guide deflection (default 0.3 mm). Three kinds:
      plate       a flat rectangular panel a x b x t, point load at (xf, yf) as fractions of the sides (default the middle), all four edges
                  "simply" supported (hinged) or "clamped". Thin-plate (Kirchhoff) theory, solved by a finite-difference biharmonic grid
                  (scipy sparse; about 60 cells on the short side, converged to a few %); the simply supported case is cross-checked against
                  the Navier series. The rows of the cross-check are written too.
      cantilever  a flange or tab of length L and width b fixed at one end, load at the free end: w = P L^3 / (3 E I), I = b t^3 / 12.
                  The bend line is taken as rigid (a real bend is a little softer: the estimate is on the stiff side for a short flange).
      angle       an L-section beam (legs leg_a and leg_b, thickness t) over a span L, `support = "cantilever"` (w = P L^3 / 3EI),
                  "simple" (centre load, P L^3 / 48EI) or "fixed" (both ends, P L^3 / 192EI); `axis` = "x" (bending about the axis parallel
                  to leg_a), "y", or "min" (the weak principal axis, default and safe).
    Also written: the stiffness P/w in N/mm and, when the verdict fails, the thickness that would pass (found by bisection with the same model).
    Materials (typical values, APPROXIMATE, E in GPa and Poisson): aluminium 5052 70.3 / 0.33, steel 200 / 0.29, PLA 3.5 / 0.36,
    ABS 2.2 / 0.35, PETG 2.1 / 0.37. Printed plastic is anisotropic and depends on infill and layer direction: take the lower end of the real
    part's value when it matters. Override or add materials with `[stiffness.materials.<name>] E_gpa, nu`.
    Limits: small deflections (w < t), linear elastic, a point load far from the edges (a load within about 2 t of an edge is not covered), no
    ribs or flanges on the plate, no shear deformation (thick plates, t > a/10, come out too stiff), no creep (plastics sag under a held load).

Why it exists (the real failure, told without names)
    The first sheet-metal layout of a box had end walls with free edges that carried panel connectors; by eye they looked fine. An
    estimate showed their corners moving well beyond the guide under a firm push, and within it with short return flanges, so the flanges were
    added before anything was cut. A thirty-second estimate for the panel, the flange and the angle bracket, against a stated guide,
    shows the thin ones early. It is an estimate: feel the real parts.

Usage
    python -I scripts/stiffness.py ITEMS.toml [--project DIR] [--out DIR]
    Importable: plate_deflection(a, b, t, E, nu, load, edges, xf, yf), cantilever_deflection(...), angle_deflection(...), MATERIALS.

Config (the TOML; mm, N)
    [stiffness]  load_n = 20, guide_mm = 0.3, grid = 60
    [stiffness.materials.<name>]  E_gpa = 70.3, nu = 0.33
    [[item]]  name, kind = "plate" | "cantilever" | "angle", material, t, then
              plate: a, b, edges = "simply" | "clamped", xf = 0.5, yf = 0.5
              cantilever: L, b
              angle: leg_a, leg_b, L, support = "cantilever" | "simple" | "fixed", axis = "min" | "x" | "y"
              optional per item: load_n, guide_mm

Exit codes: 0 every item within its guide; 1 an item exceeds it (or the cross-check differs); 2 input missing, unknown material.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import math
import shutil

import mech_common as mc

MATERIALS = {   # E in GPa, Poisson; typical values, approximate
    "aluminium 5052": (70.3, 0.33), "steel": (200.0, 0.29), "pla": (3.5, 0.36), "abs": (2.2, 0.35), "petg": (2.1, 0.37),
}


def plate_deflection(a, b, t, E_mpa, nu, load, edges="simply", xf=0.5, yf=0.5, grid=60) -> float:
    """Deflection in mm at the load point of a rectangular plate (finite-difference biharmonic, Kirchhoff theory)."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    D = E_mpa * t ** 3 / (12.0 * (1.0 - nu ** 2))
    h = min(a, b) / grid
    nx, ny = max(4, int(round(a / h))), max(4, int(round(b / h)))
    h = a / nx if a / nx > b / ny else b / ny        # square cells; the grid covers a x b to within one cell
    s = 1.0 if edges == "clamped" else -1.0           # ghost node: clamped w(-1) = w(1), hinged w(-1) = -w(1)
    idx = {}
    for i in range(1, nx):
        for j in range(1, ny):
            idx[(i, j)] = len(idx)
    stencil = [(0, 0, 20.0), (1, 0, -8.0), (-1, 0, -8.0), (0, 1, -8.0), (0, -1, -8.0), (1, 1, 2.0), (1, -1, 2.0), (-1, 1, 2.0), (-1, -1, 2.0),
               (2, 0, 1.0), (-2, 0, 1.0), (0, 2, 1.0), (0, -2, 1.0)]
    rr, cc, vv = [], [], []
    for (i, j), k in idx.items():
        for di, dj, c in stencil:
            ii, jj, f = i + di, j + dj, 1.0
            if ii < 0:
                ii, f = -ii, f * s
            elif ii > nx:
                ii, f = 2 * nx - ii, f * s
            if jj < 0:
                jj, f = -jj, f * s
            elif jj > ny:
                jj, f = 2 * ny - jj, f * s
            if ii in (0, nx) or jj in (0, ny):
                continue                              # on the edge: w = 0
            rr.append(k)
            cc.append(idx[(ii, jj)])
            vv.append(c * f)
    A = coo_matrix((vv, (rr, cc)), shape=(len(idx), len(idx))).tocsc()
    i0 = min(max(int(round(xf * nx)), 1), nx - 1)
    j0 = min(max(int(round(yf * ny)), 1), ny - 1)
    rhs = np.zeros(len(idx))
    rhs[idx[(i0, j0)]] = load * h * h / D
    w = spsolve(A, rhs)
    return float(w[idx[(i0, j0)]])


def plate_series(a, b, t, E_mpa, nu, load, xf=0.5, yf=0.5, terms=199) -> float:
    """Navier double series, simply supported plate, point load at (xf a, yf b): exact within the thin-plate theory."""
    D = E_mpa * t ** 3 / (12.0 * (1.0 - nu ** 2))
    x0, y0 = xf * a, yf * b
    tot = 0.0
    for m in range(1, terms + 1, 2):
        for n in range(1, terms + 1, 2):
            den = (m * m / (a * a) + n * n / (b * b)) ** 2
            tot += math.sin(m * math.pi * x0 / a) ** 2 * math.sin(n * math.pi * y0 / b) ** 2 / den
    return 4.0 * load / (math.pi ** 4 * D * a * b) * tot


def cantilever_deflection(L, b, t, E_mpa, load) -> float:
    return load * L ** 3 / (3.0 * E_mpa * b * t ** 3 / 12.0)


def angle_inertia(leg_a, leg_b, t):
    """(Ix, Iy, Imin) of an L section about its centroid. Leg a lies along x at the bottom, leg b stands along y at the left."""
    A1, A2 = leg_a * t, (leg_b - t) * t
    x1, y1 = leg_a / 2.0, t / 2.0
    x2, y2 = t / 2.0, t + (leg_b - t) / 2.0
    A = A1 + A2
    cx, cy = (A1 * x1 + A2 * x2) / A, (A1 * y1 + A2 * y2) / A
    Ix = leg_a * t ** 3 / 12 + A1 * (y1 - cy) ** 2 + t * (leg_b - t) ** 3 / 12 + A2 * (y2 - cy) ** 2
    Iy = t * leg_a ** 3 / 12 + A1 * (x1 - cx) ** 2 + (leg_b - t) * t ** 3 / 12 + A2 * (x2 - cx) ** 2
    Ixy = A1 * (x1 - cx) * (y1 - cy) + A2 * (x2 - cx) * (y2 - cy)
    avg, dif = (Ix + Iy) / 2, math.hypot((Ix - Iy) / 2, Ixy)
    return Ix, Iy, avg - dif


def angle_deflection(leg_a, leg_b, t, L, E_mpa, load, support="cantilever", axis="min") -> float:
    Ix, Iy, Imin = angle_inertia(leg_a, leg_b, t)
    I = {"x": Ix, "y": Iy, "min": Imin}[axis]
    k = {"cantilever": 3.0, "simple": 48.0, "fixed": 192.0}[support]
    return load * L ** 3 / (k * E_mpa * I)


def material(name: str, extra: dict):
    key = name.strip().lower()
    for k, v in (extra or {}).items():
        if k.strip().lower() == key:
            return float(v["E_gpa"]), float(v.get("nu", 0.33))
    alias = {"aluminium": "aluminium 5052", "aluminum": "aluminium 5052", "al5052": "aluminium 5052", "5052": "aluminium 5052"}
    key = alias.get(key, key)
    if key in MATERIALS:
        return MATERIALS[key]
    raise mc.MechError(f"unknown material '{name}': known {sorted(MATERIALS)}; add [stiffness.materials.\"{name}\"] E_gpa, nu")


def item_deflection(it: dict, t: float, E_mpa: float, nu: float, load: float, grid: int) -> float:
    k = it["kind"]
    if k == "plate":
        return plate_deflection(float(it["a"]), float(it["b"]), t, E_mpa, nu, load, it.get("edges", "simply"), float(it.get("xf", 0.5)), float(it.get("yf", 0.5)), grid)
    if k == "cantilever":
        return cantilever_deflection(float(it["L"]), float(it["b"]), t, E_mpa, load)
    if k == "angle":
        if t >= min(float(it["leg_a"]), float(it["leg_b"])):
            raise mc.MechError(f"item {it.get('name')}: thickness {t} is not smaller than the legs")
        return angle_deflection(float(it["leg_a"]), float(it["leg_b"]), t, float(it["L"]), E_mpa, load, it.get("support", "cantilever"), it.get("axis", "min"))
    raise mc.MechError(f"item {it.get('name')}: kind must be plate, cantilever or angle")


def thickness_for(it, E_mpa, nu, load, guide, grid) -> float | None:
    """Smallest thickness (mm) meeting the guide, by bisection between the item's t and 20 x t."""
    t0 = float(it["t"])
    lo, hi = t0, t0 * 20.0
    if it["kind"] == "angle":                      # the section stops being an angle when the thickness reaches half a leg
        hi = min(hi, 0.5 * min(float(it["leg_a"]), float(it["leg_b"])))
        if hi <= t0:
            return None
    if item_deflection(it, hi, E_mpa, nu, load, grid) > guide:
        return None
    for _ in range(30):
        mid = (lo + hi) / 2
        if item_deflection(it, mid, E_mpa, nu, load, grid) > guide:
            lo = mid
        else:
            hi = mid
    return hi


def run(args) -> int:
    try:
        job = mc.resolve(args)
    except mc.MechError:
        if not args.out:
            raise
        job = mc.Job(os.getcwd(), mc.load_config(os.getcwd()), os.path.abspath(args.out))
    if not os.path.isfile(args.items):
        print(f"could not run: file not found: {args.items}", file=sys.stderr)
        return 2
    mc.require_module("numpy", "plate solution")
    mc.require_module("scipy", "plate solution")
    cfg = mc.load_toml(args.items)
    sc = {"load_n": 20.0, "guide_mm": 0.3, "grid": 60}
    sc.update(cfg.get("stiffness", {}))
    mats = sc.get("materials", {})
    items = cfg.get("item", [])
    if not items:
        raise mc.MechError("no [[item]] entries")
    rows = mc.Rows()
    # the solver proves itself against the series first
    a, b, t, E, nu = 100.0, 100.0, 1.0, 70300.0, 0.33
    fd, se = plate_deflection(a, b, t, E, nu, 20.0, "simply", 0.5, 0.5, int(sc["grid"])), plate_series(a, b, t, E, nu, 20.0)
    err = abs(fd - se) / se
    rows.add("STF-SELF", "stiffness", "plate solver against the Navier series (100 x 100 x 1 mm, simply supported)", f"{fd:.4f} vs {se:.4f} mm, {err * 100:.1f} %", "<= 3 %",
             "pass" if err <= 0.03 else "fail")
    table = ["| Item | Kind | Material | t mm | Deflection mm | Stiffness N/mm | Guide mm | Thickness that passes |", "|---|---|---|---|---|---|---|---|"]
    for i, it in enumerate(items, 1):
        name = it.get("name", f"item{i}")
        Eg, nu_ = material(it["material"], mats)
        E_mpa = Eg * 1000.0
        load = float(it.get("load_n", sc["load_n"]))
        guide = float(it.get("guide_mm", sc["guide_mm"]))
        w = item_deflection(it, float(it["t"]), E_mpa, nu_, load, int(sc["grid"]))
        ok = w <= guide
        need = None if ok else thickness_for(it, E_mpa, nu_, load, guide, int(sc["grid"]))
        tail = "" if ok else (f"; thickness {need:.2f} mm would pass" if need else "; no thickness up to 20 x passes: add a rib or a flange")
        rows.add(f"STF-{i:02d}", "stiffness", f"{name} ({it['kind']}, {it['material']}, t {it['t']} mm) under {load:g} N", f"{w:.3f} mm, {load / w:.1f} N/mm{tail}",
                 f"<= {guide:g} mm (hand estimate, approximate material values)", "pass" if ok else "fail")
        table.append(f"| {name} | {it['kind']} | {it['material']} | {it['t']} | {w:.3f} | {load / w:.1f} | {guide:g} | {'ok' if ok else (format(need, '.2f') if need else 'none')} |")
    outd = os.path.join(job.out, "stiffness")
    if os.path.isdir(outd):
        shutil.rmtree(outd, ignore_errors=True)
    os.makedirs(outd, exist_ok=True)
    mc.atomic_write(os.path.join(outd, "stiffness_table.md"), "# Stiffness estimate\n\nHand estimates with approximate typical material values; point load "
                    f"{sc['load_n']:g} N, guide {sc['guide_mm']:g} mm. Prove on the first print or sample by pushing and measuring with a dial gauge.\n\n" + "\n".join(table) + "\n")
    rows.write(job.out, "stiffness.py", [args.items])
    rows.print_table(only_bad=True)
    print(f"table in {outd}")
    print(rows.headline())
    return rows.exit_code()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="hand-stiffness estimate")
    ap.add_argument("items", help="TOML with [[item]] entries")
    mc.add_std_args(ap)
    args = ap.parse_args(argv)
    try:
        return run(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
