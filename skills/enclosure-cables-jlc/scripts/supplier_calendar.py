"""Deadlines in a supplier's working time (their clock, your clock).

What it does
    Knows a supplier's working windows (default UTC+8, 09:30-12:00 and 13:30-18:30, Monday to Friday, optional
    holidays) and answers, for any moment:
      now              is the supplier open; the next opening in UTC and in local time
      submit-window    the next Monday-to-Wednesday opening: submit before it, so the request is first in their queue
      deadline --answer  the latest local time to answer a message that came in at --at, the same supplier day
      deadline --pay     the latest local time to pay, before their evening
      plan             a table of an order plan: step, latest local time (steps from a TOML file or the default three)
    Pure standard library. The local time zone is the PC's, converted with the system's own rules FOR THAT DATE (so a deadline
    after a clock change shows the clock of that day, not today's offset), or --local-tz, an IANA name, when tzdata is present.

Why it exists (the real failure, told without names)
    Requests sent at the weekend or at night in the supplier's country wait for their next working morning. Every
    step now has a deadline in the supplier's own hours, written before the step starts.

Usage
    python -I supplier_calendar.py now [--at ISO]
    python -I supplier_calendar.py submit-window [--at ISO] [--lead-minutes 60]
        when the send-by time has already passed but the supplier has not opened yet, it prints "send now" and the window's
        close (the supplier's opening)
    python -I supplier_calendar.py deadline --answer|--pay [--at ISO] [--margin MINUTES]
    python -I supplier_calendar.py plan [--steps plan.toml] [--at ISO]
        plan.toml: [[plan]] step = "Submit the cable quote", kind = "submit|answer|pay", at = "ISO time the step becomes due" (optional)
    common: [--project <mech folder>] [--sheet <capability.toml>] [--local-tz Asia/Tokyo] [--json]
    --at takes an ISO time; without a zone it is read as LOCAL time; "2026-01-01T10:00+08:00" is read as given.
    --sheet takes the supplier's hours from the `[hours]` block (utc_offset, windows, weekdays) of a capability sheet, when
    mech.toml has no `[supplier_hours]`; the first line printed says which source was used (mech.toml, the sheet, or the
    built-in default).

Config keys (mech.toml)
    [supplier_hours]  utc_offset = 8, windows = [["09:30", "12:00"], ["13:30", "18:30"]], weekdays = [0, 1, 2, 3, 4]
                      (Monday = 0), holidays = ["2026-10-01"], answer_margin_min = 60, pay_margin_min = 120, submit_days = [0, 1, 2]
    (the same keys may stand in `[hours]` of a capability sheet, given with --sheet; mech.toml wins when it has the block)

Exit codes
    0 answered   2 could not run (bad time or config)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import datetime as dt
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

DEFAULT = {"utc_offset": 8.0, "windows": [["09:30", "12:00"], ["13:30", "18:30"]], "weekdays": [0, 1, 2, 3, 4], "holidays": [],
           "answer_margin_min": 60, "pay_margin_min": 120, "submit_days": [0, 1, 2]}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Hours:
    def __init__(self, cfg=None):
        c = dict(DEFAULT)
        c.update(cfg or {})
        self.tz = dt.timezone(dt.timedelta(hours=float(c["utc_offset"])))
        self.windows = [(self._t(a), self._t(b)) for a, b in c["windows"]]
        self.weekdays = set(c["weekdays"])
        self.holidays = {dt.date.fromisoformat(h) for h in c["holidays"]}
        self.c = c

    @staticmethod
    def _t(s):
        h, m = s.split(":")
        return dt.time(int(h), int(m))

    def working_day(self, d: dt.date) -> bool:
        return d.weekday() in self.weekdays and d not in self.holidays

    def spans(self, d: dt.date):
        return [(dt.datetime.combine(d, a, self.tz), dt.datetime.combine(d, b, self.tz)) for a, b in self.windows]

    def is_open(self, t: dt.datetime) -> bool:
        t = t.astimezone(self.tz)
        return self.working_day(t.date()) and any(a <= t < b for a, b in self.spans(t.date()))

    def next_opening(self, t: dt.datetime) -> dt.datetime:
        """The start of the next window that begins after t (t itself when it is the exact start of one)."""
        t = t.astimezone(self.tz)
        d = t.date()
        for _ in range(400):
            if self.working_day(d):
                for a, _b in self.spans(d):
                    if a >= t:
                        return a
            d += dt.timedelta(days=1)
        raise mc.MechError("no working day found within 400 days: check the weekdays and holidays")

    def day_open_close(self, d):
        s = self.spans(d)
        return s[0][0], s[-1][1]

    def supplier_day_of(self, t: dt.datetime) -> dt.date:
        """The supplier day a moment belongs to: the day itself when it is a working day and not after closing;
        otherwise the next working day."""
        t = t.astimezone(self.tz)
        d = t.date()
        for _ in range(400):
            if self.working_day(d) and (d > t.date() or t < self.day_open_close(d)[1]):
                return d
            d += dt.timedelta(days=1)
        raise mc.MechError("no working day found within 400 days")

    def submit_window(self, t, lead_min=60):
        """The next opening that falls on a Mon-Wed (submit_days) working day: (opening, send_by)."""
        t = t.astimezone(self.tz)
        d = t.date()
        sd = set(self.c["submit_days"])
        for _ in range(400):
            if self.working_day(d) and d.weekday() in sd:
                o = self.day_open_close(d)[0]
                if o > t:
                    return o, o - dt.timedelta(minutes=lead_min)
            d += dt.timedelta(days=1)
        raise mc.MechError("no Monday-to-Wednesday working day found within 400 days")

    def deadline(self, t, margin_min):
        """Latest moment to act on the supplier day of t: that day's closing minus the margin. When the margin
        leaves no time (t already past it) the next working day is used."""
        t = t.astimezone(self.tz)
        d = self.supplier_day_of(t)
        last = self.day_open_close(d)[1] - dt.timedelta(minutes=margin_min)
        if t > last:
            d = self.supplier_day_of(dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0, 0), self.tz))
            last = self.day_open_close(d)[1] - dt.timedelta(minutes=margin_min)
        return d, last


def load_hours(project, sheet):
    """(config dict for Hours, text saying where it came from). mech.toml [supplier_hours] first, then the `[hours]` block of the
    capability sheet given with --sheet, else the built-in default."""
    cfg = {}
    if project or os.path.isfile("mech.toml"):
        try:
            cfg = mc.load_config(mc.find_project(project)).get("supplier_hours", {}) or {}
        except mc.MechError:
            cfg = {}
    if cfg:
        extra = f" ({sheet} not used: mech.toml has the block)" if sheet else ""
        return cfg, "mech.toml [supplier_hours]" + extra
    if sheet:
        if not os.path.isfile(sheet):
            raise mc.MechError(f"capability sheet not found: {sheet}")
        h = mc.load_toml(sheet).get("hours") or {}
        h = {k: v for k, v in h.items() if k in DEFAULT}
        if not h:
            raise mc.MechError(f"{sheet} has no [hours] block with utc_offset, windows, weekdays")
        return h, f"{sheet} [hours]"
    return {}, "built-in default (UTC+8, 09:30-12:00 and 13:30-18:30, Monday to Friday)"


def _local_tz(name):
    """The named zone, or None = the PC's own zone, whose rules `to_local` applies per date (never one fixed offset)."""
    if name:
        try:
            import zoneinfo
            return zoneinfo.ZoneInfo(name)
        except Exception as e:
            raise mc.MechError(f"time zone {name!r} not available: {e} (tzdata missing? use the PC's own zone by omitting --local-tz)")
    return None


def to_local(t, local):
    """A moment in local time. With a named zone: that zone's rules at that moment. Without one (None): `t.astimezone()`, the
    system's rules for THAT date; a time without a zone is read as system local time. Never the offset of today applied to every date."""
    return t.astimezone() if local is None else t.astimezone(local)


def parse_at(s, local):
    if not s:
        return to_local(dt.datetime.now(dt.timezone.utc), local)
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        raise mc.MechError(f"cannot read the time {s!r}; use ISO like 2026-01-01T10:00 or 2026-01-01T10:00+08:00")
    if t.tzinfo is None:
        return t.astimezone() if local is None else t.replace(tzinfo=local)
    return t


def _fmt(t, hours, local):
    u, s, l = t.astimezone(dt.timezone.utc), t.astimezone(hours.tz), to_local(t, local)
    return f"{DAYS[l.weekday()]} {l:%Y-%m-%d %H:%M} local  ({DAYS[s.weekday()]} {s:%H:%M} supplier, {u:%Y-%m-%d %H:%M} UTC)"


DEFAULT_PLAN = [{"step": "Submit the quote request", "kind": "submit"}, {"step": "Answer the supplier's question", "kind": "answer"},
                {"step": "Pay the order", "kind": "pay"}]


def plan(hours, local, now, steps):
    out = []
    for st in steps:
        at = parse_at(st["at"], local) if st.get("at") else now
        k = st.get("kind", "answer")
        if k == "submit":
            o, by = hours.submit_window(at)
            note = f"supplier opens {o.astimezone(hours.tz):%a %H:%M}"
            if at > by:
                note = f"SEND NOW, the send-by time has passed; the window closes when the supplier opens, {o.astimezone(hours.tz):%a %H:%M} their time"
            out.append({"step": st["step"], "kind": k, "latest": by, "note": note})
        elif k in ("answer", "pay"):
            d, last = hours.deadline(at, hours.c["answer_margin_min" if k == "answer" else "pay_margin_min"])
            out.append({"step": st["step"], "kind": k, "latest": last, "note": f"supplier day {DAYS[d.weekday()]} {d}"})
        else:
            raise mc.MechError(f"unknown step kind {k!r} (submit, answer, pay)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deadlines in a supplier's working hours.", epilog="Exit: 0 ok, 2 could not run.")
    ap.add_argument("command", choices=["now", "submit-window", "deadline", "plan"])
    ap.add_argument("--at")
    ap.add_argument("--project")
    ap.add_argument("--local-tz")
    ap.add_argument("--sheet", help="capability sheet whose [hours] block gives the supplier's hours (used when mech.toml has no [supplier_hours])")
    ap.add_argument("--answer", action="store_true")
    ap.add_argument("--pay", action="store_true")
    ap.add_argument("--margin", type=int)
    ap.add_argument("--lead-minutes", type=int, default=60)
    ap.add_argument("--steps")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        cfg, source = load_hours(a.project, a.sheet)
        hours = Hours(cfg)
        local = _local_tz(a.local_tz)
        now = parse_at(a.at, local)
        print("supplier hours from: " + source)
        res = {"hours_source": source}
        if a.command == "now":
            o = hours.next_opening(now)
            res.update({"open": hours.is_open(now), "next_opening": o})
            print(("OPEN" if res["open"] else "CLOSED") + f" at {_fmt(now, hours, local)}")
            print("next opening: " + _fmt(o, hours, local))
        elif a.command == "submit-window":
            o, by = hours.submit_window(now, a.lead_minutes)
            send_now = now > by
            res.update({"opening": o, "send_by": by, "send_now": send_now, "window_closes": o})
            print("supplier opens: " + _fmt(o, hours, local))
            if send_now:
                print("SEND NOW:       the send-by time (" + _fmt(by, hours, local) + ") has passed; the window closes when the supplier opens: "
                      + _fmt(o, hours, local))
            else:
                print("send by:        " + _fmt(by, hours, local))
        elif a.command == "deadline":
            if a.answer == a.pay:
                raise mc.MechError("give exactly one of --answer or --pay")
            m = a.margin if a.margin is not None else hours.c["answer_margin_min" if a.answer else "pay_margin_min"]
            d, last = hours.deadline(now, m)
            res.update({"supplier_day": d, "latest": last})
            print(f"{'answer' if a.answer else 'pay'} by: " + _fmt(last, hours, local) + f"   (supplier day {DAYS[d.weekday()]} {d}, margin {m} min before closing)")
        else:
            steps = DEFAULT_PLAN
            if a.steps:
                steps = mc.load_toml(a.steps).get("plan", [])
                if not steps:
                    raise mc.MechError(f"{a.steps} has no [[plan]] steps")
            rows = plan(hours, local, now, steps)
            res["plan"] = rows
            print(f"{'Step':36} Latest local time")
            for r in rows:
                print(f"{r['step']:36} {_fmt(r['latest'], hours, local)}   [{r['note']}]")
        if a.json:
            print(json.dumps(res, default=str, indent=1))
        return 0
    except (mc.MechError, KeyError, ValueError) as e:
        print("could not run:", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
