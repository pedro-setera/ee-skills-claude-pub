"""Order status baseline: remember the last known state of every open order and report only what changed.

What it does
    Keeps a small JSON file with one entry per order: a reference label, the main status exactly as the order
    page words it, where it ships to, and the page's own "last change" text. `update` compares new values with
    that baseline, prints one line per order that changed and nothing when nothing changed, and stores the new
    state together with a history of the changes.

Why it exists
    An order watch that reports every check trains its reader to ignore it, and one that re-reads its own earlier
    messages to decide what is new gets it wrong after a lost context. With a baseline on disk the watch can say
    nothing for days and then exactly one line when the status moves. The exit code tells a scheduled task whether
    a notification is due.

Usage
    python -I status_diff.py --project <hardware/board folder> update --order LABEL --status "TEXT"
                             [--ships-to "TEXT"] [--last-change "TEXT"] [--note "TEXT"]
    python -I status_diff.py --project <...> update --from new_values.json [--complete]
    python -I status_diff.py --project <...> show
    python -I status_diff.py --project <...> close --order LABEL
    python -I status_diff.py --baseline <file.json> ...        the same with an explicit baseline file

    --project keeps the baseline in <results folder>/order/status_baseline.json and writes the table for people to
    <results folder>/order/status_baseline.md (the results folder: <project>/out/, or board.toml [project] out_dir).
    With --baseline FILE the table is written beside FILE (same name, .md) or into --out <folder>.

    new_values.json:  {"orders": [{"label": "...", "status": "...", "ships_to": "...", "last_change": "..."}]}
    --complete        the new values list every open order: an order of the baseline that is missing from them
                      is reported (and counts as a main change)

    The first `update` creates the baseline and prints one line saying so (exit 0).
    The label is whatever names the order for the user (the last characters of the order number are enough).
    Order references are private: the baseline lives in the user's project, never in the skill.

board.toml keys: only with --project, [project] out_dir (the results folder; default "out").

Exit codes
    0  nothing changed (nothing printed), or only secondary fields changed (ships to, last change, note: printed)
    1  the main status of at least one order changed, an order is new, or (with --complete) an order is missing:
       one line per order is printed; a notification is due
    2  could not run: no baseline location given, unreadable or damaged baseline, bad input, a board.toml that
       cannot be read
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FORMAT = "order status baseline v1"
FIELDS = (("status", "status"), ("ships_to", "ships to"), ("last_change", "last change"), ("note", "note"))
MAIN = "status"


class CannotRun(Exception):
    pass


def _norm(text) -> str:
    """Two status texts are the same when they differ only in blanks or letter case."""
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def now_text(now: str | None = None) -> str:
    return now or datetime.datetime.now().astimezone().isoformat(timespec="minutes")


def load(path: str) -> dict | None:
    """The baseline, or None when the file does not exist yet. A damaged file is an error, never an empty start."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise CannotRun(f"baseline {os.path.basename(path)} cannot be read: {e}") from e
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("orders"), dict):
        raise CannotRun(f"baseline {os.path.basename(path)} is not an '{FORMAT}' file")
    data.setdefault("history", [])
    data.setdefault("closed", {})
    return data


def save(path: str, data: dict) -> None:
    """Write atomically: a watch that is interrupted must not leave half a baseline."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def compare(base: dict | None, new_orders: list[dict], when: str, complete: bool = False) -> tuple[dict, list[str], bool]:
    """Apply new values. Returns (new baseline, lines to print, main status changed)."""
    created = base is None
    data = base or {"format": FORMAT, "created": when, "orders": {}, "history": [], "closed": {}}
    lines: list[str] = []
    main_changed = False
    seen = set()
    for new in new_orders:
        label = _clean(new.get("label"))
        if not label:
            raise CannotRun("an order without a label")
        if label in seen:
            raise CannotRun(f"order {label} is given twice")
        seen.add(label)
        if new.get("status") is None or not _clean(new.get("status")):
            raise CannotRun(f"order {label}: no status given")
        old = data["orders"].get(label)
        if old is None:
            entry = {k: _clean(new.get(k)) for k, _ in FIELDS}
            entry.update(since=when, checked=when)
            data["orders"][label] = entry
            data["history"].append({"when": when, "order": label, "field": MAIN, "from": None,
                                    "to": entry[MAIN]})
            if not created:
                lines.append(f'{label}: new order in the baseline, status "{entry[MAIN]}"')
                main_changed = True
            continue
        parts = []
        for key, name in FIELDS:
            if key not in new or new[key] is None:
                continue                              # a field that was not read stays as it is
            value = _clean(new[key])
            if _norm(value) == _norm(old.get(key)):
                continue
            parts.append((key, f'{name} "{old.get(key) or ""}" -> "{value}"'))
            data["history"].append({"when": when, "order": label, "field": key, "from": old.get(key) or "",
                                    "to": value})
            old[key] = value
            if key == MAIN:
                old["since"] = when
                main_changed = True
        old["checked"] = when
        if parts:
            parts.sort(key=lambda p: p[0] != MAIN)    # the main status first
            lines.append(f"{label}: " + "; ".join(text for _, text in parts))
    if complete:
        for label, old in data["orders"].items():
            if label not in seen:
                lines.append(f'{label}: not in the new values any more (last status "{old.get(MAIN, "")}")')
                data["history"].append({"when": when, "order": label, "field": "listed", "from": "yes", "to": "no"})
                main_changed = True
    data["checked"] = when
    if created:
        lines.insert(0, f"baseline created: {len(data['orders'])} order(s)")
    return data, lines, main_changed


def markdown(data: dict) -> str:
    def cell(text):
        return str(text or "").replace("|", "\\|")
    out = ["# Order status baseline", "",
           f"Last check: {data.get('checked', '')}. Status texts are written as the order page shows them.", "",
           "## Baseline", "", "| Order | Status | Ships to | Last change | Checked |", "|---|---|---|---|---|"]
    for label, o in data["orders"].items():
        out.append(f"| {cell(label)} | {cell(o.get('status'))} | {cell(o.get('ships_to'))} | "
                   f"{cell(o.get('last_change'))} | {cell(o.get('checked'))} |")
    if not data["orders"]:
        out.append("| (no open order) | | | | |")
    out += ["", "## Status changes", "", "| Date time | Order | Field | From | To |", "|---|---|---|---|---|"]
    for h in data.get("history", []):
        frm = "(new)" if h.get("from") is None else h.get("from")
        out.append(f"| {cell(h['when'])} | {cell(h['order'])} | {cell(h['field'])} | {cell(frm)} | {cell(h['to'])} |")
    if data.get("closed"):
        out += ["", "## Closed orders", "", "| Order | Last status | Closed |", "|---|---|---|"]
        for label, o in data["closed"].items():
            out.append(f"| {cell(label)} | {cell(o.get('status'))} | {cell(o.get('closed'))} |")
    return "\n".join(out) + "\n"


def write_markdown(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown(data))
    os.replace(tmp, path)


def _new_values(a) -> list[dict]:
    if a.from_file:
        try:
            with open(a.from_file, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise CannotRun(f"new values {os.path.basename(a.from_file)} cannot be read: {e}") from e
        orders = data.get("orders") if isinstance(data, dict) else data
        if not isinstance(orders, list) or not all(isinstance(o, dict) for o in orders):
            raise CannotRun('new values: expected {"orders": [{"label": ..., "status": ...}, ...]}')
        return orders
    if not a.order or a.status is None:
        raise CannotRun("update needs --order LABEL and --status TEXT, or --from FILE")
    new = {"label": a.order, "status": a.status}
    for key, value in (("ships_to", a.ships_to), ("last_change", a.last_change), ("note", a.note)):
        if value is not None:
            new[key] = value
    return [new]


def safe_output() -> None:
    """Make print() unable to fail on a character the console cannot show. Output to a pipe or a file is written
    as UTF-8; on a console its own encoding stays and an unknown character is shown as an escape."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
            else:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None) -> int:
    safe_output()
    ap = argparse.ArgumentParser(description="Keep a baseline of order states and print only what changed. "
                                             "Exit 1 when the main status of an order changed.")
    ap.add_argument("--project", help="hardware/board folder: the baseline is <results folder>/order/"
                                      "status_baseline.json (<project>/out/, or board.toml [project] out_dir)")
    ap.add_argument("--baseline", help="explicit baseline file (JSON)")
    ap.add_argument("--out", help="folder for the Markdown table (default: beside the baseline)")
    ap.add_argument("--now", help="date and time text to record (default: the clock); for repeatable tests")
    sub = ap.add_subparsers(dest="cmd")
    up = sub.add_parser("update", help="compare new values with the baseline, print the changes, store them")
    up.add_argument("--order", help="reference label of one order")
    up.add_argument("--status", help="main status, as the order page words it")
    up.add_argument("--ships-to", dest="ships_to")
    up.add_argument("--last-change", dest="last_change", help="the page's own date text of the last change")
    up.add_argument("--note")
    up.add_argument("--from", dest="from_file", help="JSON file with the new values of several orders")
    up.add_argument("--complete", action="store_true", help="the new values list every open order")
    sub.add_parser("show", help="print the baseline and the status changes as a Markdown table")
    cl = sub.add_parser("close", help="move an order out of the baseline (delivered or cancelled)")
    cl.add_argument("--order", required=True)
    a = ap.parse_args(argv)

    if not a.cmd:
        ap.print_usage(sys.stderr)
        return 2
    if a.baseline:
        path = a.baseline
    elif a.project:
        try:                                         # the results folder as every project script finds it
            import kicad_io
            results = kicad_io.load_settings(a.project).get("project", {}).get("out_dir", "out")
            path = os.path.join(a.project, results, "order", "status_baseline.json")
        except Exception as e:                       # an unreadable board.toml: never guess the folder
            print(f"CANNOT RUN: board.toml cannot be read: {e}", file=sys.stderr)
            return 2
    else:
        print("CANNOT RUN: give --project <board folder> or --baseline <file.json>", file=sys.stderr)
        return 2
    md = os.path.join(a.out, os.path.splitext(os.path.basename(path))[0] + ".md") if a.out \
        else os.path.splitext(path)[0] + ".md"
    when = now_text(a.now)
    try:
        base = load(path)
        if a.cmd == "show":
            if base is None:
                raise CannotRun("no baseline yet: run update first")
            sys.stdout.write(markdown(base))
            return 0
        if a.cmd == "close":
            if base is None or a.order not in base["orders"]:
                raise CannotRun(f"order {a.order} is not in the baseline")
            entry = base["orders"].pop(a.order)
            entry["closed"] = when
            base["closed"][a.order] = entry
            base["history"].append({"when": when, "order": a.order, "field": "listed", "from": "open",
                                    "to": "closed"})
            save(path, base)
            write_markdown(md, base)
            print(f'{a.order}: closed (last status "{entry.get(MAIN, "")}")')
            return 0
        data, lines, main_changed = compare(base, _new_values(a), when, complete=a.complete)
        save(path, data)
        write_markdown(md, data)
    except CannotRun as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    return 1 if main_changed else 0


if __name__ == "__main__":
    sys.exit(main())
