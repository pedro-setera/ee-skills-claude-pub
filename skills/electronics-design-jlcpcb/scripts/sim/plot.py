"""Plots for simulation test benches: one PNG per test, readable in grey, with the pass limit drawn in.

What it gives
    panels(path, data, keys, title, ...)     stacked traces over one time axis (start-up, load step, fault)
    xy(path, series, title, xlabel, ylabel)  curves over any axis, linear or logarithmic (impedance, sweeps)

    Both draw limit lines and event markers, label every axis with its unit, and return the path they wrote.
    Give each plot the test ID and the corner in its title, and name the file by the test ID.

Why it exists
    A run that had not converged showed itself on its plot (a flat line, a jump that no stimulus explains) before
    anybody used its numbers; a limit that is drawn in the plot cannot be moved quietly in a table. Every plot
    is opened and described in the results file: a script never replaces looking.

Rules the helpers follow
    - traces differ by line style as well as by colour, so that a grey print still reads;
    - the time axis picks s, ms or us by itself and says which;
    - a limit is a dashed horizontal line with its value in the legend; an event is a dotted vertical line.

Needs matplotlib and numpy (found also when `python -I` hides the user's site-packages). No board.toml keys.
Not a command-line tool.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
for _p in (_HERE, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import kicad_io  # noqa: E402

STYLES = ["-", "--", "-.", ":"]
COLOURS = ["#1b3a5c", "#b3441e", "#3d7a3d", "#6a4c93", "#555555", "#9a7b00"]


class PlotUnavailable(RuntimeError):
    """matplotlib or numpy is missing: the plot cannot be written (say so in the results, never skip silently)."""


def _plt():
    try:
        import matplotlib
    except ImportError:
        kicad_io.add_user_site()
        try:
            import matplotlib
        except ImportError:
            raise PlotUnavailable("matplotlib is not installed for this Python: no plot written") from None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    return plt, np


def _time_scale(span: float) -> tuple[float, str]:
    if span >= 5:
        return 1.0, "s"
    if span >= 5e-3:
        return 1e3, "ms"
    if span >= 5e-6:
        return 1e6, "us"
    return 1e9, "ns"


def panels(path: str, data: dict, keys: list, title: str, labels: dict | None = None, limits: dict | None = None,
           events: list | None = None, xlim: tuple | None = None, x: str = "time") -> str:
    """Stacked panels over one axis.

    data     result of ngs.run(): arrays under "time" and under each vector name
    keys     one panel per entry; an entry may be a list of vector names drawn together in one panel
    labels   {vector name: "V_OUT (V)"}: axis and legend text with the unit
    limits   {vector name: [(value, "text"), ...]}: dashed horizontal lines in that vector's panel
    events   [(time in seconds, "text"), ...]: dotted vertical lines in every panel
    xlim     (start, end) in seconds: a zoom; the y axes then fit the zoomed part
    """
    plt, np = _plt()
    labels, limits = labels or {}, limits or {}
    t = np.asarray(data[x], dtype=float)
    span = (xlim[1] - xlim[0]) if xlim else (float(t[-1] - t[0]) if len(t) else 1.0)
    k, unit = _time_scale(span) if x == "time" else (1.0, "")
    rows = [[key] if isinstance(key, str) else list(key) for key in keys]
    fig, axs = plt.subplots(len(rows), 1, figsize=(11, 1.7 * len(rows) + 1.2), sharex=True, squeeze=False)
    axs = axs[:, 0]
    mask = (t >= xlim[0]) & (t <= xlim[1]) if xlim else np.ones(len(t), dtype=bool)
    for ax, row in zip(axs, rows):
        lo, hi = None, None
        for n, name in enumerate(row):
            y = np.real(np.asarray(data[name]))
            ax.plot(t * k, y, STYLES[n % len(STYLES)], color=COLOURS[n % len(COLOURS)], lw=1.2,
                    label=labels.get(name, name))
            if mask.any():
                lo = float(y[mask].min()) if lo is None else min(lo, float(y[mask].min()))
                hi = float(y[mask].max()) if hi is None else max(hi, float(y[mask].max()))
            for value, text in limits.get(name, []):
                ax.axhline(value, color="#000000", ls=(0, (6, 3)), lw=0.9, label=f"limit: {text}")
                lo, hi = (value if lo is None else min(lo, value)), (value if hi is None else max(hi, value))
        for when, text in events or []:
            ax.axvline(when * k, color="#444444", ls=":", lw=0.9)
        if lo is not None and hi is not None:
            pad = 0.06 * (hi - lo) or 0.05 * (abs(hi) or 1.0)
            ax.set_ylim(lo - pad, hi + pad)
        ax.set_ylabel(labels.get(row[0], row[0]), fontsize=8)
        ax.grid(alpha=0.35)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=7, loc="best")
    for when, text in events or []:
        axs[0].annotate(text, (when * k, 1.0), xycoords=("data", "axes fraction"), fontsize=7, rotation=90,
                        va="top", ha="right")
    axs[-1].set_xlabel(f"time ({unit})" if x == "time" else x, fontsize=8)
    if xlim:
        axs[-1].set_xlim(xlim[0] * k, xlim[1] * k)
    fig.suptitle(title, fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def xy(path: str, series: list, title: str, xlabel: str, ylabel: str, logx: bool = False, logy: bool = False,
       hlines: list | tuple = (), vlines: list | tuple = (), xlim: tuple | None = None,
       ylim: tuple | None = None) -> str:
    """Curves over any axis.

    series   [(x values, y values, "legend text"), ...]
    hlines   [(value, "text"), ...]: limits, dashed       vlines   [(value, "text"), ...]: events, dotted
    """
    plt, np = _plt()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for n, (xs, ys, text) in enumerate(series):
        ax.plot(np.asarray(xs, dtype=float), np.real(np.asarray(ys)), STYLES[n % len(STYLES)],
                color=COLOURS[n % len(COLOURS)], lw=1.3, label=text)
    for value, text in hlines:
        ax.axhline(value, color="#000000", ls=(0, (6, 3)), lw=0.9, label=f"limit: {text}")
    for value, text in vlines:
        ax.axvline(value, color="#444444", ls=":", lw=0.9, label=text)
    if logx:
        ax.set_xscale("log")
    if logy:
        ax.set_yscale("log")
    if xlim:
        ax.set_xlim(*xlim)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.35, which="both")
    ax.legend(fontsize=8)
    ax.set_title(title, fontsize=10, loc="left")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(__doc__)
