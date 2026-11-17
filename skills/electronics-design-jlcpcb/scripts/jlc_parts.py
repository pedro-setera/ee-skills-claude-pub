"""Parts at JLCPCB and LCSC: search by name, look-up per LCSC number, dated BOM stock check, audit of the BOM lines.

What it does
    search      for each search text (a maker part number, or words such as "100k NTC 0603"): the first results
                of JLCPCB's parts search, each with its LCSC number, maker part number, package, class, assembly
                stock and prices. This is how a part gets its LCSC number when none is known yet. ONE request
                per text. A result is a candidate, never a choice: the datasheet decides.
    candidates  a first search with filters (category list, package, resistance, basic class) in a free COMMUNITY
                copy of JLCPCB's parts list (jlcsearch.tscircuit.com: not JLCPCB, not LCSC), so that the hunt for a
                cheaper basic part of the same value and package costs no requests at the supplier. ONE request per
                query, to that service only. The result says at the top and in every row that these are CANDIDATES
                from a community copy with its date of reading, not confirmed: class, stock and price are confirmed
                with `lookup` at JLCPCB itself before a part enters the BOM. Its answers go to a file of their own,
                jlc_candidates_answers.json, never into jlc_parts_answers.json; it changes no BOM file, and
                bom-check, line-audit and lookup never read it.
    lookup      for each LCSC number: JLCPCB assembly stock, LCSC retail stock, class (basic / preferred /
                extended), price breaks, maker part number, a life-cycle note when the source gives one, and
                the datasheet link the supplier names (its copy of the maker's document).
    bom-check   a dated stock table for N boards plus spares: the need of every BOM line against the stock that
                will really supply it (assembled parts against JLCPCB's assembly stock; hand-fitted and off-board
                parts against LCSC's retail stock), the short lines, the thin lines, the number of extended
                lines, and the cost split into parts and per-order fees.
    line-audit  the BOM lines shared by more than one designator (so that any value that may ever change can get
                its own line), duplicate designators, fitted parts without an LCSC number or without a maker part
                number. Works on a BOM file, on a netlist, or straight on a schematic. With --offline or --live it
                also says what each LCSC number is (maker, maker part number, package, class), so that a reader can
                set it against the value in the BOM; a number without an answer is UNKNOWN.

    The saved answers: every live answer goes at once into jlc_parts_answers.json in the results folder
    (<project>/out/, or the folder given with --out), per LCSC number: maker, maker part number, description,
    package, class, both stocks, price breaks, and the date and time of the answer. New answers are merged into
    the file; nothing in it is lost. `--offline` reads that same file. Reviewers who are not allowed on the
    supplier's site resolve every LCSC number from it. A search saves every result there too (so a look-up of
    a number that a search found on the same day costs no second request to JLCPCB), and the search itself
    (text, time, number of results, the numbers found) in jlc_parts_searches.json beside it.

Why it exists (real failures, told without names)
    - The two stocks are different numbers for the same part: it can show none at the distributor and plenty in
      the assembly stock, or the reverse, and stock that covers the need can still be thin. A stock check without
      a date, or against the wrong stock, is worth nothing on the order day.
    - A part that shares a BOM line with others cannot be changed alone after the order: only the whole line can,
      so the order waits or the part is reworked by hand on every board.
    - Fast or repeated requests can get the user's address blocked by a distributor. The block falls on the user's
      own address and account. So every request to a supplier's service is paced here, one at a time, for all
      processes on the machine, every answer is saved and reused, and a refusal stops everything.

Usage
    python -I jlc_parts.py --project <hardware/board folder> --live|--offline [F] bom-check [--boards N] [--spares PCT]
    python -I jlc_parts.py --project <hardware/board folder> [--offline | --live] line-audit
    python -I jlc_parts.py --project <hardware/board folder> --live|--offline search [--results N] LM2903DR "100k NTC 0603" ...
    python -I jlc_parts.py --out <folder> --live|--offline [F] lookup C12345 C67890 ...
    python -I jlc_parts.py --project <hardware/board folder> --live|--offline [F] candidates ["<text>"] [--category
              resistors] [--package 0402] [--value 10k] [--basic-only] [--limit N]
    (--project, --out, --live, --offline and --fresh stand BEFORE the word search, candidates, lookup, bom-check or
    line-audit)
    python -I jlc_parts.py --out <folder> bom-check <bom.csv | netlist.net | root.kicad_sch> [--offboard list.csv] ...
    python -I jlc_parts.py --out <folder> line-audit <bom.csv | netlist.net | root.kicad_sch>

    The BOM source may be: a CSV file (JLCPCB's upload format or any table with a designator column), a KiCad
    netlist (kicadsexpr), or a KiCad schematic (it is copied to a private folder and its netlist exported there
    with kicad-cli; the design itself is never touched). The LCSC number is read from the column or symbol field
    named by --lcsc-field (default: the names in LCSC_FIELDS below, any letter case). A missing number is a
    finding, never a crash.

    --offline [FILE] no network. Without FILE: jlc_parts_answers.json of the results folder. FILE may also be a
                     stock table saved by earlier project scripts (rows with lcsc/code, jlc_stock, lcsc_stock,
                     jlc_class, ...). A number that has no saved answer is reported UNKNOWN, never guessed.
    --live           ask the suppliers' public services (no sign-in). Needs the user's yes once per project.
                     Saved answers of the same day are reused; --fresh asks again.
    --save FILE      another file for the live answers (default: jlc_parts_answers.json in the results folder;
                     answers are merged into an existing file).
    --sources jlc,lcsc   which services to ask (default both: the two stocks are both needed).
    --pace S         seconds between two requests to one host (default 3, plus a random 0 to 100 %; never below 1).

    search           one text per argument (quote a text of several words). Each text is ONE request to JLCPCB's
                     parts search and counts against any limit the user set; the first --results results are
                     read (default 10, at most 25), never a second page: when the part wanted is not among
                     them, search again with a narrower text (the full maker part number). A text searched
                     today is not asked again (--fresh asks again). LCSC is not asked: the retail stock comes
                     with `lookup` of the number chosen. With --offline: the saved searches only.

    candidates       one query per run: a text (words or a maker part number; optional with --category), and
                     filters. Without --category: the general search (GET /api/search?q=<text>&limit=100&full=true,
                     plus &package=). With --category (resistors, capacitors, microcontrollers, voltage_regulators):
                     that list (GET /<category>/list.json?search=<text>&package=<p>, plus &resistance=<ohms> for
                     --value, resistors only). The script itself checks every row against every filter: each word
                     of the text must begin a word of the row, the package must be equal, the resistance equal,
                     the class basic with --basic-only. --limit N candidates are shown (default 10, at most 100).
                     A query asked today is not asked again (--fresh asks again). --offline [FILE] reads
                     jlc_candidates_answers.json of the results folder (or FILE in that format) and nothing else;
                     a query without a saved answer is UNKNOWN. --save is refused: the candidates have one file.
                     --community-url sets the address of the community service (never a supplier's host).

    Results (Markdown and JSON twin): parts_search.md, jlc_candidates.md, BOM_STOCK_CHECK.md, bom_line_audit.md,
    parts_lookup.md, in <project>/out/ or in --out.

Pace on supplier hosts (binding for every script that reaches one; fetch_parts.py imports it from here)
    One request at a time per host; at least --pace seconds apart with a random addition; the time of the last
    request per host is kept in a small file in the system temp folder under a lock, so several processes and
    several agents share one pace. HTTP 403 or 429, any other HTTP error, a captcha or "verify" page, "too many
    requests", an empty answer, a sign-in page or a redirect to another host is a REFUSAL: it is never repeated
    in the same run; the script stops at once with exit code 2, and the host is left alone by every process for
    15 minutes. Then one slow request; tell the user. A request that TIMES OUT is repeated once, after the
    normal pause; a second time-out stops the run with exit code 2. Nothing is ever retried in a loop.
    The community service of `candidates` is an outside host too: the same pace, the same stop, the same client
    name; a redirect from it is a refusal and is not followed, and no link in its answers is ever followed.

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [bom]
    file        = "out/netlist.net"     # BOM source (CSV, netlist or schematic), relative to the board folder
    offboard    = "out/bom_offboard.csv"  # parts that are not on the board: housings, crimps, cables, consumables
    lcsc_field  = "LCSC"                # name, or list of names, of the column / symbol field with the LCSC number
    mpn_field   = "MPN"                 # the same for the maker part number
    hand_fit    = ["J9"]                # fitted by hand after assembly: bought at LCSC, checked against LCSC stock
    dnp         = ["R99"]               # not fitted, besides the DNP marks the BOM source carries
    ignore      = ["TP*", "H*"]         # references that are nothing to buy (test points, holes, fiducials)
    boards      = 5
    spares_pct  = 20                    # spares per line in percent ...
    spares_min  = 2                     # ... but at least this many pieces
    extended_fee_usd = 3.0              # fee per extended line and order: read it on the live page, it changes
    max_age_hours = 24                  # bom-check offline: an answer of a BOM line older than this, or without a
                                        # date, makes the check fail as STALE (no limit without the key or
                                        # --max-age-hours; check_all.py always gives one, 24 h by default)
    [bom.shared_ok]                     # LCSC number -> why the designators of this line can never differ
    C12345 = "pull-ups on one rail"
    [parts]
    pace_s = 3

Exit codes
    0  bom-check: every line in stock; line-audit: no finding; lookup: every number found; search: every text
       gave at least one result; candidates: at least one candidate passed the filters (still not confirmed)
    1  findings: a short line, an UNKNOWN line (no answer for its number), a line without an LCSC number, stale
       answers, a shared line without a written reason, a duplicate designator, a number that the source does not
       know, a search text without a result or (offline) without a saved search; candidates: none passed the
       filters (this proves nothing about JLCPCB's own list), or (offline) no saved answer for the query
    2  could not run: no BOM, unreadable file, neither --live nor --offline, KiCad missing for a schematic
       source, a supplier host or the community service refused or did not answer, an answer of a form this
       script does not know. "Could not run" is never a pass.

Not checked: whether a part is right for the circuit (a search result least of all: its maker part number, value,
tolerance, rating and package are set against the datasheet before the number enters the BOM); prices in the cart
(fees, taxes, attrition are estimates); life-cycle status when the service does not give it (read the part page).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import contextlib
import csv
import datetime
import fnmatch
import io
import json
import math
import os
import random
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# The services behind the suppliers' own part search and part page. Both are undocumented and may move:
# they can be set on the command line (--jlc-url, --lcsc-url).
JLC_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
LCSC_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode="
# A free community copy of JLCPCB's parts list with filters, no sign-in; not JLCPCB, not LCSC (`candidates` only).
COMMUNITY_URL = "https://jlcsearch.tscircuit.com"
USER_AGENT = "Mozilla/5.0 (compatible; parts-lookup-script)"       # a generic client name, nothing personal
HTTP_TIMEOUT = 40.0                 # s: one request
PACE_DEFAULT = 3.0                  # s between two requests to one host, before the random addition
PACE_MIN = 1.0                      # s: the pace can be set higher, never lower
REFUSAL_WAIT = 15 * 60              # s: a host that refused is left alone this long by every process
PACE_LOCK_WAIT = 900.0              # s: longest wait for the turn at one host
ANSWERS_NAME = "jlc_parts_answers.json"
ANSWERS_FORMAT = "jlc_parts answers v1"
SEARCHES_NAME = "jlc_parts_searches.json"
SEARCHES_FORMAT = "jlc_parts searches v1"
SEARCH_RESULTS = 10                 # results read per search text: the first page, the size a look-up asks for
SEARCH_RESULTS_MAX = 25
SEARCH_TEXT_MAX = 80                # characters of one search text

# Default names of the column / symbol field that holds the LCSC number and the maker part number (any letter
# case, punctuation ignored). Set others with --lcsc-field / --mpn-field or in board.toml.
LCSC_FIELDS = ["LCSC", "LCSC Part #", "LCSC Part", "LCSC#", "LCSC PN", "LCSC Part Number", "JLCPCB Part #",
               "JLCPCB Part", "JLC Part", "JLCPCB", "LCSC code"]
MPN_FIELDS = ["MPN", "Mfr Part #", "Mfr. Part #", "Manufacturer Part Number", "Manufacturer Part",
              "Manufacturer_Part_Number", "Mfr PN", "MFR_PN", "PartNumber", "Part Number"]
_LCSC_RE = re.compile(r"^C\d{1,10}$")


class CannotRun(Exception):
    """The work could not be done (exit code 2)."""


class Refused(CannotRun):
    """A supplier host refused a request: stop everything; never repeated in the same run."""


class TimedOut(CannotRun):
    """A request got no answer in time. It may be repeated once, after the normal pause; then the run stops."""


def _now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def _stamp(t: datetime.datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def natural(ref: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", ref)]


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# =====================================================================================================================
# Pace on supplier hosts (shared with fetch_parts.py)
# =====================================================================================================================

class _FileLock:
    """Exclusive lock among processes, held through an open file: the system frees it when the process ends."""

    def __init__(self, path: str, timeout: float):
        self.path, self.timeout, self.f = path, timeout, None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "a+b")
        t0 = time.monotonic()
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() - t0 > self.timeout:
                    self.f.close()
                    raise CannotRun(f"another process has held the pace lock {os.path.basename(self.path)} for more "
                                    f"than {self.timeout:.0f} s") from None
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.f.close()
        return False


class HostPace:
    """One request at a time per host, spaced in time, for every process on this machine.

        pace = HostPace(base=3.0)
        with pace.turn("example.com") as slot:       # waits for the host's turn (lock + spacing)
            answer = ask()
            if answer_is_a_refusal:
                slot.refuse("HTTP 429")              # records it for all processes and raises Refused

    The time of the last request and a refusal are kept in <system temp>/supplier-pace/<host>.json (the folder can
    be set with the environment variable SUPPLIER_PACE_DIR). After a refusal no process asks that host again for
    15 minutes: turn() raises Refused without sending anything.
    """

    def __init__(self, base: float = PACE_DEFAULT, folder: str | None = None, lock_wait: float = PACE_LOCK_WAIT):
        self.base = max(PACE_MIN, float(base))
        self.folder = folder or os.environ.get("SUPPLIER_PACE_DIR") or os.path.join(tempfile.gettempdir(),
                                                                                    "supplier-pace")
        self.lock_wait = lock_wait
        self.sent: list[tuple[str, float]] = []          # (host, time) of every request of this process

    def _files(self, host: str) -> tuple[str, str]:
        safe = re.sub(r"[^A-Za-z0-9.-]", "_", host.lower())
        return os.path.join(self.folder, safe + ".json"), os.path.join(self.folder, safe + ".lock")

    @staticmethod
    def _read(path: str) -> dict:
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write(path: str, state: dict) -> None:
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)

    @contextlib.contextmanager
    def turn(self, host: str):
        state_file, lock_file = self._files(host)
        began = time.monotonic()
        while True:
            # The lock is held while the pace file is read and while the request itself runs, never while
            # waiting: so requests cannot overlap, and several waiting processes take turns instead of one
            # process keeping the host to itself.
            with _FileLock(lock_file, self.lock_wait):
                state = self._read(state_file)
                now = time.time()
                until = float(state.get("blocked_until") or 0)
                if until > now:
                    raise Refused(self.message(host, float(state.get("refused_at") or now),
                                               str(state.get("refused_why") or "refused"), sent=False))
                wait = max(float(state.get("next") or 0), float(state.get("last") or 0) + self.base) - now
                if wait > self.lock_wait:
                    raise CannotRun(f"the pace file of {host} asks for a wait of {wait:.0f} s; not waiting that long")
                if wait <= 0:
                    slot = _Slot(self, host, state_file)
                    try:
                        yield slot
                    finally:
                        done = time.time()
                        self.sent.append((host, done))
                        new = {"host": host, "last": done, "next": done + self.base * (1.0 + random.random()),
                               "pid": os.getpid()}
                        if slot.why:
                            new.update(refused_at=done, refused_why=slot.why, blocked_until=done + REFUSAL_WAIT)
                        self._write(state_file, new)
                    return
            if time.monotonic() - began > self.lock_wait:
                raise CannotRun(f"no turn at {host} within {self.lock_wait:.0f} s (other processes are using it)")
            time.sleep(min(wait, 1.0) + random.uniform(0.0, 0.2))

    @staticmethod
    def message(host: str, when: float, why: str, sent: bool = True) -> str:
        at = datetime.datetime.fromtimestamp(when).astimezone()
        free = at + datetime.timedelta(seconds=REFUSAL_WAIT)
        head = f"{host} refused a request at {at:%Y-%m-%d %H:%M:%S} ({why})."
        if not sent:
            head += " Nothing was sent now."
        return (head + f" Not repeated. Wait at least 15 minutes (until {free:%H:%M}), then one slow request; "
                "tell the user. Never look for a way around a refusal or a bot check.")

    def summary(self) -> str:
        if not self.sent:
            return "0 requests sent"
        span = self.sent[-1][1] - self.sent[0][1]
        hosts = sorted({h for h, _ in self.sent})
        return f"{len(self.sent)} request(s) to {', '.join(hosts)} over {span:.0f} s"


class _Slot:
    def __init__(self, pace: HostPace, host: str, state_file: str):
        self.pace, self.host, self.state_file, self.why = pace, host, state_file, ""

    def refuse(self, why: str):
        """Record the refusal for every process and stop."""
        self.why = why
        raise Refused(HostPace.message(self.host, time.time(), why))


def refusal_reason(status: int, body: bytes, final_url: str, asked_url: str) -> str | None:
    """Why an answer counts as a refusal, or None for a usable answer."""
    if status in (403, 429):
        return f"HTTP {status}" + (" too many requests" if status == 429 else " forbidden")
    if status >= 400:
        return f"HTTP {status}"
    asked_host = urllib.parse.urlsplit(asked_url).netloc.lower()
    final_host = urllib.parse.urlsplit(final_url or asked_url).netloc.lower()
    if final_host and final_host != asked_host:
        return f"redirected to {final_host} (a sign-in or check page?)"
    if not body or not body.strip():
        return "empty answer"
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        text = body[:6000].decode("utf-8", errors="replace").lower()
        for mark in ("captcha", "verify", "too many requests", "unusual traffic", "access denied", "sign in",
                     "log in", "login", "robot"):
            if mark in text:
                return f"a page instead of data ('{mark}')"
        return "an answer that is not data"
    if isinstance(data, dict) and "code" in data and str(data.get("code")) not in ("200", "0"):
        msg = str(data.get("message") or data.get("msg") or "")[:80]
        return f"the service answered code {data.get('code')}" + (f": {msg}" if msg else "")
    return None


# =====================================================================================================================
# LIVE PATH: the only code that goes to the network.
# Offline tests reach it only through a local stand-in server (--jlc-url http://127.0.0.1:...).
# =====================================================================================================================

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect comes back as its own status (an answer), and is never followed to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_fetch(method: str, url: str, data: bytes | None, headers: dict, timeout: float = HTTP_TIMEOUT,
               redirects: bool = True):
    """One HTTP request. Returns (status, body, final url). An HTTP error status is an answer, not an exception.
    No answer in time raises TimedOut; no connection at all raises CannotRun. With redirects=False a redirect is
    returned as its status (3xx) and nothing is sent to the address it names."""
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    host = urllib.parse.urlsplit(url).netloc
    opener = urllib.request.urlopen if redirects else urllib.request.build_opener(_NoRedirect).open
    try:
        with opener(req, timeout=timeout) as r:
            return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:
        try:
            body = e.read() or b""
        except OSError:
            body = b""
        return e.code, body, url
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        why = getattr(e, "reason", e)
        if isinstance(e, TimeoutError) or isinstance(why, TimeoutError) or "timed out" in str(why).lower():
            raise TimedOut(f"no answer from {host} within {timeout:g} s") from None
        raise CannotRun(f"no connection to {host} ({why}). Nothing is repeated: run again later; the answers "
                        f"received so far are saved and will be reused") from None


def paced_request(pace: "HostPace", host: str, once):
    """Run once(slot) in the host's turn. A request that TIMES OUT is repeated one time, after the normal pause;
    a second time-out stops the run. A REFUSAL (see refusal_reason) is never repeated."""
    for attempt in (1, 2):
        try:
            with pace.turn(host) as slot:
                return once(slot)
        except TimedOut as e:
            if attempt == 2:
                raise CannotRun(f"{e}, twice. Stopped: no further repeat; the answers received so far are saved. "
                                "Try again later with one slow request; tell the user") from None
            print(f"{e}: one repeat after the normal pause", file=sys.stderr)


def _prices(items, qty_key: str, price_keys: tuple) -> list[list[float]]:
    out = []
    for it in items or []:
        try:
            price = next(float(it[k]) for k in price_keys if it.get(k) not in (None, ""))
            out.append([int(float(it[qty_key])), price])
        except (KeyError, StopIteration, TypeError, ValueError):
            continue
    return sorted(out)


def _lifecycle_hints(raw: dict) -> dict:
    """Fields of an answer whose name suggests a life-cycle statement, as the source gives them (no guessing)."""
    hints = {}
    for k, v in (raw or {}).items():
        lk = k.lower()
        if any(w in lk for w in ("cycle", "discontinu", "nrnd", "obsolet", "eol", "notrecommend", "newdesign")):
            if v not in (None, "", [], {}):
                hints[k] = v
    return hints


def norm_jlc(item: dict | None, asked: str) -> dict:
    """An answer of JLCPCB's parts search in this script's form."""
    if not item:
        return {"asked": asked, "found": False}
    lib = item.get("componentLibraryType")
    cls = "basic" if lib == "base" else ("preferred" if item.get("preferredComponentFlag") else "extended")
    return {"asked": asked, "found": True, "stock": item.get("stockCount"), "class": cls,
            "mpn": item.get("componentModelEn"), "brand": item.get("componentBrandEn"),
            "package": item.get("componentSpecificationEn"), "description": item.get("describe"),
            "prices": _prices(item.get("componentPrices"), "startNumber", ("productPrice",)),
            "loss": item.get("lossNumber"), "min_purchase": item.get("minPurchaseNum"),
            "min_patch": item.get("leastPatchNumber"), "url": item.get("lcscGoodsUrl"),
            "datasheet": item.get("dataManualUrl") or None,     # the supplier's copy of the maker's document
            "lifecycle_hints": _lifecycle_hints(item), "raw": item}


def norm_lcsc(result: dict | None, asked: str) -> dict:
    """An answer of LCSC's product detail in this script's form."""
    if not result:
        return {"asked": asked, "found": False}
    return {"asked": asked, "found": True, "stock": result.get("stockNumber"), "min_buy": result.get("minBuyNumber"),
            "mpn": result.get("productModel"), "brand": result.get("brandNameEn"),
            "package": result.get("encapStandard"),
            "description": result.get("productIntroEn") or result.get("productDescEn"),
            "prices": _prices(result.get("productPriceList"), "ladder", ("usdPrice", "productPrice")),
            "lifecycle_hints": _lifecycle_hints(result), "raw": result}


class Live:
    """Asks the two services, one paced request per part and source."""

    def __init__(self, pace: HostPace, sources: list[str], jlc_url: str = JLC_URL, lcsc_url: str = LCSC_URL,
                 user_agent: str = USER_AGENT, timeout: float = HTTP_TIMEOUT):
        self.pace, self.sources, self.jlc_url, self.lcsc_url = pace, sources, jlc_url, lcsc_url
        self.ua, self.timeout = user_agent, timeout

    def _ask(self, method: str, url: str, data: bytes | None, headers: dict) -> dict:
        def once(slot):
            status, body, final = http_fetch(method, url, data, headers, self.timeout)
            why = refusal_reason(status, body, final, url)
            if why:
                slot.refuse(why)
            return body
        body = paced_request(self.pace, urllib.parse.urlsplit(url).netloc, once)
        return json.loads(body.decode("utf-8", errors="replace"))

    def _jlc_page(self, keyword: str, size: int = 10) -> tuple[list, object, str]:
        """ONE request to JLCPCB's parts search: the first `size` results for the keyword, the total the service
        reports (None when it gives none), and the time of the answer."""
        body = json.dumps({"keyword": keyword, "currentPage": 1, "pageSize": size}).encode()
        d = self._ask("POST", self.jlc_url, body, {"Content-Type": "application/json", "Accept": "application/json",
                                                   "User-Agent": self.ua})
        asked = _stamp()
        try:
            page = d["data"]["componentPageInfo"]
            items = page["list"] or []
            total = page.get("total")
        except (KeyError, TypeError, AttributeError):
            raise CannotRun("JLCPCB's parts search answered in a form this script does not know (the service is "
                            "undocumented and may have changed); read the part pages by hand, slowly") from None
        return items, total, asked

    def jlc(self, code: str) -> dict:
        items, _, asked = self._jlc_page(code)
        return norm_jlc(next((it for it in items if it.get("componentCode") == code), None), asked)

    def jlc_search(self, words: str, size: int = SEARCH_RESULTS) -> dict:
        """The first results of JLCPCB's parts search for a maker part number or words: one request."""
        items, total, asked = self._jlc_page(words, size)
        results = [(str(it["componentCode"]), norm_jlc(it, asked)) for it in items
                   if isinstance(it, dict) and _LCSC_RE.match(str(it.get("componentCode") or ""))]
        return {"words": words, "asked": asked, "size": size, "results": results,
                "total": total if isinstance(total, int) else None}

    def lcsc(self, code: str) -> dict:
        d = self._ask("GET", self.lcsc_url + urllib.parse.quote(code), None,
                      {"Accept": "application/json", "User-Agent": self.ua})
        if not isinstance(d, dict) or "result" not in d:
            raise CannotRun("LCSC's product detail answered in a form this script does not know (the service is "
                            "undocumented and may have changed); read the part pages by hand, slowly")
        return norm_lcsc(d.get("result"), _stamp())


# =====================================================================================================================
# Saved answers
# =====================================================================================================================

def _parse_time(text) -> datetime.datetime | None:
    if not text:
        return None
    s = str(text).strip().replace(" UTC", "+00:00")
    for cand in (s, s.replace(" ", "T", 1)):
        try:
            t = datetime.datetime.fromisoformat(cand)
            return t if t.tzinfo else t.astimezone()
        except ValueError:
            continue
    return None


def _rows_to_parts(data: dict) -> dict:
    """Stock tables saved by earlier project scripts ({"date"|"time": ..., "rows": [...]}) in this script's form."""
    asked = str(data.get("date") or data.get("time") or "")
    parts: dict[str, dict] = {}
    for r in data.get("rows", []):
        code = r.get("lcsc") or r.get("code")
        if not code or not _LCSC_RE.match(str(code)):
            continue
        p = parts.setdefault(code, {})
        jlc_stock = r.get("jlc_stock", r.get("stock"))
        cls = r.get("jlc_class", r.get("class"))
        if cls:
            cls = {"preferred ext": "preferred", "base": "basic", "expand": "extended"}.get(cls, cls)
        if jlc_stock is not None or cls:
            j = {"asked": asked, "found": True, "stock": jlc_stock, "class": cls, "mpn": r.get("mpn"),
                 "brand": r.get("brand"), "package": r.get("package"), "url": r.get("url"),
                 "prices": sorted([q, r[k]] for q, k in ((1, "p1"), (10, "p10"), (100, "p100"))
                                  if isinstance(r.get(k), (int, float)))}
            p["jlc"] = j
        if "lcsc_stock" in r and r.get("lcsc_stock") is not None:
            prices = []
            if isinstance(r.get("usd10"), (int, float)):
                prices = [[10, float(r["usd10"])]]
            m = re.match(r"\s*([\d.]+)\s*@\s*(\d+)", str(r.get("price") or ""))
            if m:
                prices = [[int(m.group(2)), float(m.group(1))]]
            p["lcsc"] = {"asked": asked, "found": True, "stock": r.get("lcsc_stock"),
                         "min_buy": r.get("lcsc_min", r.get("lcsc_min_order")), "mpn": r.get("mpn"),
                         "brand": r.get("brand"), "prices": prices}
    return parts


def load_answers(path: str) -> dict:
    """{LCSC number: {"jlc": {...}, "lcsc": {...}}} from a saved file of any known form."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise CannotRun(f"saved answers {os.path.basename(path)} cannot be read: {e}") from None
    if isinstance(data, dict) and data.get("format") == ANSWERS_FORMAT and isinstance(data.get("parts"), dict):
        return data["parts"]
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        parts = _rows_to_parts(data)
        if parts:
            return parts
    raise CannotRun(f"{os.path.basename(path)} is not a file of saved answers this script knows "
                    f"('{ANSWERS_FORMAT}', or a stock table with rows)")


def save_answers(path: str, parts: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"format": ANSWERS_FORMAT, "written": _stamp(), "parts": parts}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def load_searches(path: str) -> dict:
    """{search text in lower case: {"words", "asked", "size", "total", "codes"}}; {} when no search was saved."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise CannotRun(f"saved searches {os.path.basename(path)} cannot be read: {e}") from None
    if isinstance(data, dict) and data.get("format") == SEARCHES_FORMAT and isinstance(data.get("searches"), dict):
        return data["searches"]
    raise CannotRun(f"{os.path.basename(path)} is not a file of saved searches this script knows ('{SEARCHES_FORMAT}')")


def save_searches(path: str, searches: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"format": SEARCHES_FORMAT, "written": _stamp(), "searches": searches}, f, indent=1,
                  ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


class Answers:
    """The answers for a run: from a saved file (offline) or from the services with a same-day cache (live)."""

    def __init__(self, offline: str | None, live: Live | None, save_path: str | None, fresh: bool):
        self.offline, self.live, self.save_path, self.fresh = offline, live, save_path, fresh
        self.parts: dict[str, dict] = {}
        self.reused = 0
        if offline:
            self.parts = load_answers(offline)
        elif save_path and os.path.exists(save_path):
            self.parts = load_answers(save_path)

    @property
    def mode(self) -> str:
        return "offline" if self.offline else "live"

    def get(self, code: str) -> dict:
        """The flat answer for one LCSC number (see flatten)."""
        part = self.parts.setdefault(code, {}) if self.live else self.parts.get(code, {})
        if self.live:
            today = _now().date()
            for src in self.live.sources:
                have = part.get(src)
                t = _parse_time(have.get("asked")) if have else None
                if have and not self.fresh and t and t.astimezone().date() == today:
                    self.reused += 1
                    continue
                part[src] = self.live.jlc(code) if src == "jlc" else self.live.lcsc(code)
                if self.save_path:
                    save_answers(self.save_path, self.parts)       # after every answer: a stopped run keeps them
        return flatten(code, part)


def flatten(code: str, part: dict) -> dict:
    j, lc = part.get("jlc") or {}, part.get("lcsc") or {}
    hints = {}
    for src, rec in (("JLCPCB", j), ("LCSC", lc)):
        for k, v in (rec.get("lifecycle_hints") or {}).items():
            hints[f"{src} {k}"] = v
    if part.get("lifecycle"):
        hints["note"] = part["lifecycle"]
    return {
        "lcsc": code,
        "mpn": lc.get("mpn") or j.get("mpn"), "brand": lc.get("brand") or j.get("brand"),
        "package": j.get("package") or lc.get("package"),
        "description": j.get("description") or lc.get("description"),
        "jlc_asked": j.get("asked"), "jlc_found": j.get("found"), "jlc_stock": j.get("stock"),
        "jlc_class": j.get("class"), "jlc_prices": j.get("prices") or [], "jlc_loss": j.get("loss"),
        "jlc_min_purchase": j.get("min_purchase"), "jlc_min_patch": j.get("min_patch"),
        "lcsc_asked": lc.get("asked"), "lcsc_found": lc.get("found"), "lcsc_stock": lc.get("stock"),
        "lcsc_min": lc.get("min_buy"), "lcsc_prices": lc.get("prices") or [],
        "lifecycle": hints, "url": j.get("url"),
        "datasheet": j.get("datasheet") or (j.get("raw") or {}).get("dataManualUrl") or None,
    }


def price_at(ladder: list, qty: float) -> tuple[float | None, str]:
    """Unit price at a quantity from a price ladder, and a note when the quantity is below the first break."""
    if not ladder:
        return None, ""
    best = None
    for q, p in sorted(ladder):
        if q <= qty:
            best = p
    if best is None:
        q0, p0 = sorted(ladder)[0]
        return p0, f"below the first price break ({q0} pcs)"
    return best, ""


# =====================================================================================================================
# BOM lines
# =====================================================================================================================

def _split_refs(cell: str) -> list[str]:
    out = []
    for tok in re.split(r"[,;\s]+", (cell or "").strip()):
        if not tok:
            continue
        m = re.match(r"^([A-Za-z_#]+)(\d+)\s*(?:-|\.\.)\s*([A-Za-z_#]*)(\d+)$", tok)
        if m and (not m.group(3) or m.group(3) == m.group(1)) and int(m.group(4)) >= int(m.group(2)):
            out += [f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(4)) + 1)]
        else:
            out.append(tok)
    return out


def _truthy(cell) -> bool:
    return str(cell or "").strip().lower() in ("1", "x", "y", "yes", "true", "dnp", "do not populate", "not fitted")


def _kind(text: str, default: str) -> str:
    t = (text or "").lower()
    if "hand" in t:
        return "hand-fit"
    if "off" in t or "cable" in t or "harness" in t:
        return "off-board"
    if any(w in t for w in ("jlc", "board", "smd", "assembl", "smt")):
        return "board"
    return default


class Bom:
    """BOM lines and what was learnt while reading them."""

    def __init__(self):
        self.lines: list[dict] = []
        self.notes: list[str] = []
        self.sources: list[str] = []
        self.duplicates: list[str] = []
        self.skipped: list[str] = []
        self.has_mpn = False
        self.kind_of_source = ""
        self.hand_fit: set[str] = set()

    def line(self, **kw) -> dict:
        ln: dict = {"lcsc": "", "bad_number": "", "value": "", "mpn": "", "footprint": "", "refs": [], "dnp": [],
                    "kind": "board", "qty": None, "item": "", "source": "", "values": []}
        ln.update(kw)
        self.lines.append(ln)
        return ln


def _number(cell: str) -> tuple[str, str, str]:
    """(LCSC number, malformed text, source text) from a cell."""
    text = (cell or "").strip()
    if not text:
        return "", "", ""
    if _LCSC_RE.match(text.upper()):
        return text.upper(), "", ""
    if re.match(r"^[Cc]\s*\d", text) or re.match(r"^\d+$", text):
        return "", text, ""                                  # looks like a number but is not one
    return "", "", text                                      # a source in words ("generic", a shop)


def read_csv(path: str, bom: Bom, lcsc_fields: list[str], mpn_fields: list[str], default_kind: str) -> None:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise CannotRun(f"BOM {os.path.basename(path)} cannot be read: {e}") from None
    first = text.splitlines()[0] if text.strip() else ""
    delim = max(",;\t", key=first.count) if first else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 1:
        raise CannotRun(f"BOM {os.path.basename(path)} is empty")
    head = [_key(c) for c in rows[0]]

    def col(names):
        for n in names:
            if _key(n) in head:
                return head.index(_key(n))
        return None

    c_ref = col(["Designator", "Designators", "Reference", "References", "Reference(s)", "Refs", "Ref", "RefDes"])
    c_item = col(["Item", "Name"])
    c_lcsc = col(lcsc_fields)
    c_val = col(["Comment", "Value", "Part", "Designation", "Description"])
    c_fp = col(["Footprint", "Package"])
    c_qty = col(["Qty per board", "Qty/board", "Qty per set", "Qty per unit", "Quantity per PCB", "Qty", "Quantity"])
    c_kind = col(["Kind", "Assembly", "Fitted by"])
    c_dnp = col(["DNP", "Do not populate", "Do not place"])
    c_mpn = col(mpn_fields)
    if c_ref is None and c_item is None:
        raise CannotRun(f"BOM {os.path.basename(path)}: no designator column (looked for Designator, Reference, "
                        f"Refs, Item); its columns are: {', '.join(rows[0])}")
    if c_lcsc is None:
        bom.notes.append(f"{os.path.basename(path)}: no column for the LCSC number (looked for: "
                         f"{', '.join(lcsc_fields)}); every line counts as 'no LCSC number'")
    if c_mpn is not None:
        bom.has_mpn = True

    def cell(row, c):
        return row[c].strip() if c is not None and c < len(row) else ""

    seen: dict[str, int] = {}
    for n, row in enumerate(rows[1:], 2):
        refs = _split_refs(cell(row, c_ref))
        code, bad, source = _number(cell(row, c_lcsc))
        whole_dnp = _truthy(cell(row, c_dnp))
        kind = _kind(cell(row, c_kind), default_kind)
        qty = None
        item = cell(row, c_item)
        if not refs:
            if not item and not cell(row, c_val):
                continue
            kind = _kind(cell(row, c_kind), "off-board")
            try:
                qty = float(cell(row, c_qty).replace(",", ".")) if cell(row, c_qty) else 1.0
            except ValueError:
                qty = 1.0
                bom.notes.append(f"{os.path.basename(path)} row {n}: quantity '{cell(row, c_qty)}' not understood, 1 used")
        for r in refs:
            seen[r] = seen.get(r, 0) + 1
        bom.line(lcsc=code, bad_number=bad, source=source, value=cell(row, c_val), mpn=cell(row, c_mpn),
                 footprint=cell(row, c_fp), refs=[] if whole_dnp else refs, dnp=refs if whole_dnp else [],
                 kind=kind, qty=qty, item=item, row=n, file=os.path.basename(path))
    bom.duplicates += sorted((r for r, k in seen.items() if k > 1), key=natural)


def read_netlist(path: str, bom: Bom, lcsc_fields: list[str], mpn_fields: list[str]) -> None:
    import kicad_io
    try:
        net = kicad_io.read_netlist(path)
    except kicad_io.KicadIOError as e:
        m = re.search(r"reference (\S+) appears twice", str(e))
        if m:
            bom.duplicates.append(m.group(1))
            bom.notes.append(f"the netlist names {m.group(1)} twice: annotate the schematic; the lines below are "
                             "incomplete until then")
            return
        raise CannotRun(str(e)) from None
    except OSError as e:
        raise CannotRun(f"netlist cannot be read: {e}") from None
    want_l = [_key(n) for n in lcsc_fields]
    want_m = [_key(n) for n in mpn_fields]
    groups: dict[tuple, dict] = {}
    any_field = False
    for ref in sorted(net.parts, key=natural):
        p = net.parts[ref]
        if ref.startswith("#"):
            continue
        fields = {_key(k): v for k, v in p.fields.items()}
        raw = next((fields[k] for k in want_l if fields.get(k, "").strip()), "")
        if any(k in fields for k in want_l):
            any_field = True
        mpn = next((fields[k] for k in want_m if fields.get(k, "").strip()), "")
        if any(k in fields for k in want_m):
            bom.has_mpn = True
        if p.exclude_from_bom and ref not in bom.hand_fit:
            bom.skipped.append(ref)
            continue
        code, bad, source = _number(raw)
        fp = p.footprint.split(":")[-1]
        kind = "hand-fit" if ref in bom.hand_fit else "board"
        key = (code or f"{p.value}|{fp}|{bad}{source}", kind)
        g = groups.get(key)
        if g is None:
            g = groups[key] = bom.line(lcsc=code, bad_number=bad, source=source, value=p.value, mpn=mpn,
                                       footprint=fp, kind=kind, file=os.path.basename(path))
        (g["dnp"] if p.dnp else g["refs"]).append(ref)
        if p.value not in g["values"]:
            g["values"].append(p.value)
        if mpn and not g["mpn"]:
            g["mpn"] = mpn
    if not any_field:
        bom.notes.append(f"no part of the netlist has a field for the LCSC number (looked for: "
                         f"{', '.join(lcsc_fields)}; set another name with --lcsc-field)")


def schematic_netlist(sch: str, tmp: str) -> str:
    """Export the netlist of a schematic from a private copy of its project. The design is not touched."""
    import kicad_io
    try:
        kicad_io.require_kicad()
        copy = os.path.join(tmp, "project")
        kicad_io.copy_project(os.path.dirname(os.path.abspath(sch)), copy)
        out = os.path.join(tmp, "netlist.net")
        kicad_io.run_cli(["sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                          os.path.join(copy, os.path.basename(sch))], check=True)
    except kicad_io.KicadIOError as e:
        raise CannotRun(f"the netlist of {os.path.basename(sch)} could not be exported: {e}") from None
    if not os.path.isfile(out):
        raise CannotRun(f"kicad-cli wrote no netlist for {os.path.basename(sch)}")
    return out


def read_bom(path: str, cfg: dict, tmp: str, offboard: str | None = None) -> Bom:
    bom = Bom()
    bom.hand_fit = set(cfg["hand_fit"])
    if not os.path.isfile(path):
        raise CannotRun(f"BOM source not found: {os.path.basename(path)}")
    low = path.lower()
    if low.endswith(".kicad_sch"):
        bom.kind_of_source = "schematic"
        read_netlist(schematic_netlist(path, tmp), bom, cfg["lcsc_fields"], cfg["mpn_fields"])
    else:
        with open(path, "rb") as f:
            head = f.read(200).lstrip()
        if head.startswith(b"(export"):
            bom.kind_of_source = "netlist"
            read_netlist(path, bom, cfg["lcsc_fields"], cfg["mpn_fields"])
        elif head.startswith(b"(kicad_sch"):
            bom.kind_of_source = "schematic"
            read_netlist(schematic_netlist(path, tmp), bom, cfg["lcsc_fields"], cfg["mpn_fields"])
        else:
            bom.kind_of_source = "BOM table"
            read_csv(path, bom, cfg["lcsc_fields"], cfg["mpn_fields"], "board")
    bom.sources.append(f"{os.path.basename(path)} ({bom.kind_of_source})")
    # the project's own lists: not fitted, fitted by hand, nothing to buy
    for ln in bom.lines:
        keep = []
        for r in ln["refs"]:
            if any(fnmatch.fnmatchcase(r, pat) for pat in cfg["ignore"]):
                bom.skipped.append(r)
            elif r in cfg["dnp"]:
                ln["dnp"].append(r)
            else:
                keep.append(r)
        ln["refs"] = keep
    split = []
    for ln in bom.lines:                                     # a hand-fitted designator leaves its shared line
        hand = [r for r in ln["refs"] if r in bom.hand_fit]
        if hand and ln["kind"] == "board":
            rest = [r for r in ln["refs"] if r not in bom.hand_fit]
            if rest:
                ln["refs"] = rest
                new = dict(ln, refs=hand, dnp=[], kind="hand-fit")
                split.append(new)
            else:
                ln["kind"] = "hand-fit"
    bom.lines += split
    bom.lines = [ln for ln in bom.lines if ln["refs"] or ln["dnp"] or ln["qty"]]
    if offboard:
        if not os.path.isfile(offboard):
            raise CannotRun(f"off-board list not found: {os.path.basename(offboard)}")
        have = {ln["lcsc"] for ln in bom.lines if ln["lcsc"]}
        off = Bom()
        read_csv(offboard, off, cfg["lcsc_fields"], cfg["mpn_fields"], "off-board")
        for ln in off.lines:
            if ln["lcsc"] and ln["lcsc"] in have:
                bom.notes.append(f"off-board item '{ln['item'] or ln['value']}' ({ln['lcsc']}) is already a line "
                                 "of the board's BOM: counted once")
                continue
            if ln["kind"] == "board":
                ln["kind"] = "off-board"
            bom.lines.append(ln)
        bom.notes += off.notes
        bom.sources.append(f"{os.path.basename(offboard)} (off-board list)")
    return bom


def refs_text(ln: dict) -> str:
    parts = sorted(ln["refs"], key=natural)
    s = ", ".join(parts) if parts else (ln["item"] if not ln["dnp"] else "")
    if ln["dnp"]:
        s += (", " if s else "") + "DNP: " + ", ".join(sorted(ln["dnp"], key=natural))
    return s


def part_text(ln: dict, ans: dict | None = None) -> str:
    return (ans or {}).get("mpn") or ln["mpn"] or ln["value"] or ln["item"] or ""


def md_cell(text) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


# =====================================================================================================================
# Commands
# =====================================================================================================================

def _write(out_dir: str, name: str, md: str, data: dict) -> str:
    os.makedirs(out_dir, exist_ok=True)
    for path, text in ((os.path.join(out_dir, name + ".md"), md),
                       (os.path.join(out_dir, name + ".json"), json.dumps(data, indent=1, ensure_ascii=False) + "\n")):
        tmp = f"{path}.tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    return os.path.join(out_dir, name + ".md")


def _mode_lines(answers: Answers, pace: HostPace | None, cfg: dict) -> tuple[list[str], dict]:
    """How the answers were obtained: for the head of every report."""
    info: dict = {"mode": answers.mode}
    if answers.offline:
        times = [t for p in answers.parts.values() for s in ("jlc", "lcsc")
                 if (t := _parse_time((p.get(s) or {}).get("asked")))]
        newest, oldest = (max(times), min(times)) if times else (None, None)
        age_h = (_now() - oldest).total_seconds() / 3600 if oldest else None
        info.update(answers_file=os.path.basename(answers.offline), answers_from=_stamp(oldest) if oldest else None,
                    answers_to=_stamp(newest) if newest else None, age_hours=round(age_h, 1) if age_h else None)
        when = f"{oldest:%Y-%m-%d %H:%M}" if oldest else "an unknown time"
        line = (f"**Offline: saved answers of {when}** (file `{os.path.basename(answers.offline)}`"
                + (f", {age_h:.0f} h old" if age_h is not None else "") + "). This is not today's stock.")
        return [line], info
    assert answers.live is not None and pace is not None
    src = " and ".join({"jlc": "JLCPCB's parts search", "lcsc": "LCSC's product data"}[s] for s in answers.live.sources)
    info.update(sources=answers.live.sources, requests=len(pace.sent), reused_same_day=answers.reused,
                span_s=round(pace.sent[-1][1] - pace.sent[0][1], 1) if pace.sent else 0.0, pace_s=pace.base)
    line = (f"**Live answers** from {src}, public, no sign-in: {pace.summary()}; {answers.reused} answer(s) of today "
            f"reused from the saved file; pace {pace.base:g} s plus a random 0 to 100 %.")
    if len(answers.live.sources) < 2:
        line += " Sources not asked: " + ", ".join(sorted({"jlc", "lcsc"} - set(answers.live.sources))) + "."
    return [line], info


def cmd_search(a, cfg, answers: Answers, pace, out_dir: str) -> int:
    """LCSC numbers by maker part number or words: one paced request per text, everything saved and reused."""
    size = a.results
    if not 1 <= size <= SEARCH_RESULTS_MAX:
        raise CannotRun(f"--results takes 1 to {SEARCH_RESULTS_MAX} (the first page of the search; a narrower text "
                        "finds more than a longer list)")
    texts: list[str] = []
    for w in a.words:
        w = " ".join(str(w).split())
        if not w:
            raise CannotRun("an empty search text: give a maker part number or words, one text per argument")
        if len(w) > SEARCH_TEXT_MAX:
            raise CannotRun(f"a search text of more than {SEARCH_TEXT_MAX} characters: '{w[:30]}...'")
        if w.casefold() not in (t.casefold() for t in texts):
            texts.append(w)
    spath = os.path.join(out_dir, SEARCHES_NAME)
    searches = load_searches(spath)
    today = _now().date()
    reused = 0
    found: list[dict] = []
    for w in texts:
        key = w.casefold()
        rec = searches.get(key)
        if answers.live:
            t = _parse_time(rec.get("asked")) if rec else None
            if rec and not answers.fresh and t and t.astimezone().date() == today and int(rec.get("size") or 0) >= size:
                reused += 1
            else:
                got = answers.live.jlc_search(w, size)
                for code, norm in got["results"]:
                    answers.parts.setdefault(code, {})["jlc"] = norm
                rec = {"words": w, "asked": got["asked"], "size": size, "total": got["total"],
                       "codes": [code for code, _ in got["results"]]}
                searches[key] = rec
                if answers.save_path:                               # after every answer: a stopped run keeps them
                    save_answers(answers.save_path, answers.parts)
                save_searches(spath, searches)
        if rec is None:
            found.append({"words": w, "state": "unknown", "asked": None, "total": None, "results": []})
            continue
        rows = []
        for code in list(rec.get("codes") or [])[:size]:
            j = (answers.parts.get(code) or {}).get("jlc") or {}
            rows.append({"lcsc": code, "mpn": j.get("mpn"), "brand": j.get("brand"), "package": j.get("package"),
                         "class": j.get("class"), "stock": j.get("stock"), "prices": j.get("prices") or [],
                         "description": j.get("description"), "url": j.get("url"), "asked": j.get("asked"),
                         "datasheet": j.get("datasheet") or (j.get("raw") or {}).get("dataManualUrl") or None,
                         "saved": bool(j)})
        found.append({"words": rec.get("words") or w, "state": "results" if rows else "none",
                      "asked": rec.get("asked"), "total": rec.get("total"), "results": rows})

    if answers.offline:
        head = (f"**Offline: saved searches** (file `{SEARCHES_NAME}`, their results from "
                f"`{os.path.basename(answers.offline)}`). Nothing was asked now; this is not today's stock.")
        info: dict = {"mode": "offline", "searches_file": SEARCHES_NAME}
    else:
        assert pace is not None
        head = (f"**Live answers** from JLCPCB's parts search, public, no sign-in: {pace.summary()}; {reused} "
                f"search(es) of today reused from the saved file; pace {pace.base:g} s plus a random 0 to 100 %. "
                "Each new search text was ONE request.")
        info = {"mode": "live", "requests": len(pace.sent), "reused_same_day": reused, "pace_s": pace.base}
    md = ["# Parts search", "", f"Run: {_stamp()}.", "", head, "",
          f"Read per text: the first {size} results, in the order the supplier gives them."]
    none = [f["words"] for f in found if f["state"] == "none"]
    unknown = [f["words"] for f in found if f["state"] == "unknown"]

    def ladder(lst):
        return ", ".join(f"{q}+: {p:g}" for q, p in lst[:3]) or "-"
    for f in found:
        total = f["total"] if f["total"] is not None else "an unknown number"
        md += ["", f"## `{md_cell(f['words'])}`", ""]
        if f["state"] == "unknown":
            md.append("UNKNOWN: no saved search for this text. Search it once with `--live` (one request; needs "
                      "the user's yes).")
            print(f"search \"{f['words']}\": UNKNOWN, no saved search for this text")
            continue
        if f["state"] == "none":
            md.append(f"**No result** (answer of {f['asked']}). Try the maker part number without its packing "
                      "suffix, or another maker's equal part; a part that JLCPCB does not stock cannot be placed.")
            print(f"search \"{f['words']}\": no result (answer of {f['asked']})")
            continue
        md += [f"{len(f['results'])} of {total} result(s), answer of {f['asked']}.", "",
               "| LCSC number | Maker part | Maker | Package | Class | JLCPCB assembly stock | Price, USD | Description |",
               "|---|---|---|---|---|---|---|---|"]
        print(f"search \"{f['words']}\": {len(f['results'])} of {total} result(s), answer of {f['asked']}")
        for r in f["results"]:
            if not r["saved"]:
                md.append(f"| {r['lcsc']} | no saved answer for this number | | | | | | |")
                print(f"  {r['lcsc']:10} no saved answer for this number")
                continue
            desc = str(r["description"] or "")
            md.append(f"| {r['lcsc']} | {md_cell(r['mpn'] or '')} | {md_cell(r['brand'] or '')} | "
                      f"{md_cell(r['package'] or '')} | {r['class'] or '-'} | {r['stock']} | {ladder(r['prices'])} | "
                      f"{md_cell(desc[:140] + ('...' if len(desc) > 140 else ''))} |")
            print(f"  {r['lcsc']:10} {str(r['class'] or '-'):9} stock {r['stock']}  {r['brand'] or ''} {r['mpn'] or ''}  "
                  f"{r['package'] or ''}  {ladder(r['prices'])}")
    verdict = "PASS" if not none and not unknown else "FAIL"
    md += ["", f"**Result: {verdict}** - {len(found) - len(none) - len(unknown)} of {len(found)} text(s) with results"
           + (f"; no result for: {', '.join(none)}" if none else "")
           + (f"; UNKNOWN (no saved search): {', '.join(unknown)}" if unknown else "") + ".", "",
           "How to read this:",
           "- A result is a candidate, never a choice. Before a number enters the BOM, set its maker part number, "
           "value, tolerance, rating and package against the part's datasheet, and read both stocks with "
           "`lookup` (a search gives JLCPCB's assembly stock only).",
           f"- Only the first {size} results of each text were read. When the part wanted is not among them, search "
           "with a narrower text (the full maker part number), never page after page.",
           "- Every new search text is one request to the supplier and counts against any limit the user set.",
           f"- This report holds the texts of this run only. Every search made for this folder stays in "
           f"`{SEARCHES_NAME}`; `--offline search <texts>` writes them out again without a request.",
           "", "Not checked: whether any result suits the circuit; LCSC's retail stock; the life cycle."]
    data = {"check": "parts_search", "result": verdict, "date": _stamp(), **info, "results_per_text": size,
            "searches": found, "no_result": none, "unknown": unknown}
    path = _write(out_dir, "parts_search", "\n".join(md) + "\n", data)
    print(f"parts search: {verdict}"
          + (f"; no result for: {', '.join(none)}" if none else "")
          + (f"; UNKNOWN (no saved search): {', '.join(unknown)}" if unknown else "")
          + f"; {head.replace('**', '')}")
    print(f"report {path}")
    return 0 if verdict == "PASS" else 1


def cmd_lookup(a, cfg, answers: Answers, pace, out_dir: str) -> int:
    codes = []
    for c in a.codes:
        c = c.strip().upper()
        if not _LCSC_RE.match(c):
            raise CannotRun(f"'{c}' is not an LCSC number (C followed by digits)")
        if c not in codes:
            codes.append(c)
    rows = [answers.get(c) for c in codes]
    head, info = _mode_lines(answers, pace, cfg)
    md = ["# Parts look-up", "", f"Run: {_stamp()}.", ""] + head + [
        "", "| LCSC | Maker part | Class | JLCPCB assembly stock | LCSC stock | Price breaks, USD (JLCPCB / LCSC) "
        "| Life cycle | Answer of |", "|---|---|---|---|---|---|---|---|"]
    missing = []
    for r in rows:
        known = r["jlc_found"] or r["lcsc_found"]
        if not known:
            missing.append(r["lcsc"])

        def ladder(lst):
            return ", ".join(f"{q}+: {p:g}" for q, p in lst[:6]) or "-"
        life = "; ".join(f"{k}: {v}" for k, v in r["lifecycle"].items()) or "not given by the source"
        asked = " / ".join(x for x in (r["jlc_asked"], r["lcsc_asked"]) if x) or "no answer"
        stock_j = "NOT FOUND" if r["jlc_found"] is False else ("no answer" if r["jlc_found"] is None else r["jlc_stock"])
        stock_l = "NOT FOUND" if r["lcsc_found"] is False else ("no answer" if r["lcsc_found"] is None else r["lcsc_stock"])
        md.append(f"| {r['lcsc']} | {md_cell((r['brand'] or '') + ' ' + (r['mpn'] or ''))} | {r['jlc_class'] or '-'} | "
                  f"{stock_j} | {stock_l} | {ladder(r['jlc_prices'])} / {ladder(r['lcsc_prices'])} | {md_cell(life)} | "
                  f"{asked} |")
    verdict = "PASS" if not missing else "FAIL"
    md += ["", f"**Result: {verdict}** - {len(rows) - len(missing)} of {len(rows)} number(s) found"
           + (f"; no data for: {', '.join(missing)}" if missing else "") + ".", "",
           "Datasheet links that the supplier names (its copy of the maker's document; fetch one with "
           "`fetch_parts.py datasheet <link> <new folder>` where the maker's own site refuses a script):"]
    md += [f"- {r['lcsc']}: {r['datasheet']}" if r.get("datasheet") else f"- {r['lcsc']}: none named"
           for r in rows]
    md += ["", "Not checked: whether the part suits the circuit; the life cycle when the source gives none "
           "(read the part page); whether a datasheet link shows the document of this exact part."]
    data = {"check": "parts_lookup", "result": verdict, "date": _stamp(), **info, "parts": rows, "missing": missing}
    path = _write(out_dir, "parts_lookup", "\n".join(md) + "\n", data)
    for r in rows:
        print(f"{r['lcsc']:10} {str(r['jlc_class'] or '-'):9} JLCPCB {r['jlc_stock']}  LCSC {r['lcsc_stock']}  "
              f"{r['mpn'] or ''}  (answer of {r['jlc_asked'] or r['lcsc_asked'] or 'none'})")
    print(f"parts look-up: {verdict}; {head[0].replace('**', '')}")
    print(f"report {path}")
    return 0 if verdict == "PASS" else 1


def cmd_bom_check(a, cfg, answers: Answers, pace, out_dir: str, tmp: str) -> int:
    bom = read_bom(cfg["bom_file"], cfg, tmp, cfg["offboard"])
    boards, pct, smin = cfg["boards"], cfg["spares_pct"], cfg["spares_min"]
    rows = []
    for ln in bom.lines:
        per = ln["qty"] if not ln["refs"] and ln["qty"] is not None and not ln["dnp"] else len(ln["refs"])
        base = per * boards
        need = int(math.ceil(round(base + max(smin, pct * base / 100.0), 6))) if per else 0
        ans = answers.get(ln["lcsc"]) if ln["lcsc"] else None
        row: dict = {"kind": ln["kind"], "refs": refs_text(ln), "lcsc": ln["lcsc"], "source": ln["source"] or ln["bad_number"],
               "part": part_text(ln, ans), "per_board": per, "need": need, "jlc_stock": None, "lcsc_stock": None,
               "jlc_class": None, "unit_usd": None, "price_note": "", "cost_usd": None, "asked": None,
               "lifecycle": "", "thin": False, "order_qty": need}
        if ans is None:
            row["status"] = ("NO NUMBER" if ln["kind"] == "board" and need else "GENERIC") if not ln["bad_number"] \
                else "BAD NUMBER"
        else:
            row.update(jlc_stock=ans["jlc_stock"], lcsc_stock=ans["lcsc_stock"], jlc_class=ans["jlc_class"],
                       lifecycle="; ".join(f"{k}: {v}" for k, v in ans["lifecycle"].items()))
            use_jlc = ln["kind"] == "board"
            found, stock = (ans["jlc_found"], ans["jlc_stock"]) if use_jlc else (ans["lcsc_found"], ans["lcsc_stock"])
            row["asked"] = ans["jlc_asked"] if use_jlc else ans["lcsc_asked"]
            if need == 0:
                row["status"] = "OK"
            elif found is None or (found and stock is None):
                row["status"] = "UNKNOWN"
            elif found is False:
                row["status"] = "NOT FOUND"
            else:
                row["status"] = "OK" if stock >= max(need, 1) else "SHORT"
                row["thin"] = row["status"] == "OK" and stock < 10 * need
            if use_jlc and need:
                q = per * boards + int(ans["jlc_loss"] or 0)
                row["order_qty"] = max(need if not ans["jlc_loss"] else q, int(ans["jlc_min_purchase"] or 0),
                                       int(ans["jlc_min_patch"] or 0))
            ladder = (ans["jlc_prices"] or ans["lcsc_prices"]) if use_jlc else (ans["lcsc_prices"] or ans["jlc_prices"])
            unit, note = price_at(ladder, row["order_qty"])
            row.update(unit_usd=unit, price_note=note,
                       cost_usd=round(unit * row["order_qty"], 4) if unit is not None and need else None)
        rows.append(row)
    order = {"board": 0, "hand-fit": 1, "off-board": 2}
    rows.sort(key=lambda r: (order.get(r["kind"], 3), r["status"] == "OK", r["jlc_class"] != "extended",
                             natural(r["refs"])))
    n = {s: sum(1 for r in rows if r["status"] == s) for s in
         ("OK", "SHORT", "NOT FOUND", "UNKNOWN", "NO NUMBER", "BAD NUMBER", "GENERIC")}
    short = n["SHORT"] + n["NOT FOUND"]
    head, info = _mode_lines(answers, pace, cfg)
    # the age that counts: of the answers this check judged by, not of every answer in the file (an old search
    # result for a part that left the BOM must not make a refreshed check stale); an answer without a date is stale
    used = [r for r in rows if r["need"] and r["status"] in ("OK", "SHORT", "NOT FOUND")]
    times = [_parse_time(r["asked"]) for r in used]
    age = (_now() - min(times)).total_seconds() / 3600 if used and None not in times else None
    stale = bool(answers.offline and cfg["max_age_hours"] is not None and used
                 and (age is None or age > cfg["max_age_hours"]))
    refresh = (f"python -I scripts/jlc_parts.py {'--project <board folder>' if a.project else '--out <folder>'} --live "
               f"bom-check{'' if a.project else ' <BOM>'}")
    stale_text = ((f"The oldest saved answer used here is {age:.0f} h old, over the limit of {cfg['max_age_hours']:g} h"
                   if age is not None else "The saved answers used here carry no date")
                  + f": STALE. Refresh them with `{refresh}` (needs the user's yes)") if stale else ""
    bad = short + n["UNKNOWN"] + n["NO NUMBER"] + n["BAD NUMBER"]
    verdict = "PASS" if not bad and not stale else "FAIL"
    fitted = [r for r in rows if r["kind"] == "board" and r["need"]]
    cls = {c: sum(1 for r in fitted if r["jlc_class"] == c) for c in ("basic", "preferred", "extended")}
    cost_board = sum(r["cost_usd"] or 0 for r in rows if r["kind"] == "board")
    cost_other = sum(r["cost_usd"] or 0 for r in rows if r["kind"] != "board")
    unpriced = [r["refs"] for r in rows if r["need"] and r["cost_usd"] is None]
    fee = cfg["extended_fee_usd"]
    fees = [(f"extended lines: {cls['extended']} x USD {fee:g}", cls["extended"] * fee)] if fee is not None else []
    fees += [(name, usd) for name, usd in cfg["fees"]]

    md = [f"# BOM stock check ({_stamp()})", "",
          f"Need: **{boards} board(s) plus spares** ({pct:g} % per line, at least {smin}). "
          f"BOM from: {'; '.join(bom.sources)}.", ""] + head + [
          "", "**Rule:** a part the assembler places (kind `board`) needs JLCPCB's own assembly stock; a part bought "
          "for hand fitting (`hand-fit`) or for use off the board (`off-board`) needs LCSC's retail stock. Both "
          "stocks are shown for every line.", "",
          f"**Result: {verdict}** - {n['OK']} line(s) in stock, {short} short, {n['UNKNOWN']} UNKNOWN (no "
          f"{'saved ' if answers.offline else ''}answer for the number), "
          f"{n['NO NUMBER'] + n['BAD NUMBER']} assembled line(s) without a valid LCSC number, {n['GENERIC']} generic "
          f"(no LCSC number, not checked)." + (f" {stale_text}." if stale else ""), "",
          "| Kind | Refs | Part | LCSC | Need | LCSC stock | JLCPCB stock | Class | USD each | Answer of | OK |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    word = {"OK": "yes", "SHORT": "**NO: short**", "NOT FOUND": "**NO: not found**",
            "UNKNOWN": "**UNKNOWN: no saved answer**" if answers.offline else "**UNKNOWN: no answer**",
            "NO NUMBER": "**no LCSC number**", "BAD NUMBER": "**not an LCSC number**", "GENERIC": "generic"}
    for r in rows:
        usd = "" if r["unit_usd"] is None else f"{r['unit_usd']:.4f}".rstrip("0").rstrip(".")
        md.append(f"| {r['kind']} | {md_cell(r['refs'])} | {md_cell(r['part'])} | {r['lcsc'] or md_cell(r['source'])} | "
                  f"{r['need']} | {'' if r['lcsc_stock'] is None else r['lcsc_stock']} | "
                  f"{'' if r['jlc_stock'] is None else r['jlc_stock']} | {r['jlc_class'] or ''} | {usd} | "
                  f"{r['asked'] or ''} | {word[r['status']]} |")
    thin = [r for r in rows if r["thin"]]
    if thin:
        md += ["", "**Thin stock** (in stock, but under 10 times the need; order soon or name a second source): "
               + "; ".join(f"{r['refs']} {r['lcsc']} ({r['jlc_stock'] if r['kind'] == 'board' else r['lcsc_stock']} "
                           f"for {r['need']})" for r in thin) + "."]
    life = [r for r in rows if r["lifecycle"]]
    if life:
        md += ["", "**Life-cycle notes given by the source:** " + "; ".join(f"{r['refs']} {r['lcsc']}: {r['lifecycle']}"
                                                                             for r in life) + "."]
    md += ["", "## Cost split (an estimate; the cart decides)", "",
           "| Item | USD |", "|---|---|",
           f"| Parts the assembler places ({len(fitted)} lines: {cls['basic']} basic, {cls['preferred']} preferred, "
           f"{cls['extended']} extended) | {cost_board:.2f} |",
           f"| Parts bought at LCSC (hand-fit and off-board) | {cost_other:.2f} |"]
    for name, usd in fees:
        md.append(f"| Per order: {md_cell(name)} | {usd:.2f} |")
    md.append(f"| **Total of the above** | **{cost_board + cost_other + sum(u for _, u in fees):.2f}** |")
    md += ["", "Quantities priced: the need above; for assembled parts the assembler's own attrition and minimum "
           "quantities where the answer gives them. " + ("" if fee is not None else "The fee per extended line is "
           "not set (read it on the live page and give --extended-fee): extended lines are counted, not priced. ")
           + ("Lines without a price: " + "; ".join(unpriced) + "." if unpriced else "")]
    notes = list(bom.notes)
    if bom.skipped:
        notes.append("left out (excluded from the BOM in the design, or on the ignore list): "
                     + ", ".join(sorted(set(bom.skipped), key=natural)))
    md += ["", "## Not checked", "", "- whether each part suits the circuit; second sources",
           "- fees, taxes and shipping of the real cart",
           "- life cycle, unless a note is shown above (read the part page)"] + [f"- {x}" for x in notes]
    md += ["", "Settings: " + cfg["settings_note"]]
    data = {"check": "bom_stock_check", "result": verdict, "date": _stamp(), "boards": boards, "spares_pct": pct,
            "spares_min": smin, **info, "stale": stale, "max_age_hours": cfg["max_age_hours"],
            "answers_age_hours": round(age, 1) if age is not None else None,
            "counts": {"lines": len(rows), "in_stock": n["OK"], "short": short, "unknown": n["UNKNOWN"],
                       "no_number": n["NO NUMBER"] + n["BAD NUMBER"], "generic": n["GENERIC"]},
            "classes": cls, "cost_usd": {"assembled_parts": round(cost_board, 2), "lcsc_parts": round(cost_other, 2),
                                         "fees": [{"name": k, "usd": v} for k, v in fees]},
            "rows": rows, "thin": [r["refs"] for r in thin], "notes": notes, "bom_sources": bom.sources}
    path = _write(out_dir, "BOM_STOCK_CHECK", "\n".join(md) + "\n", data)
    for r in rows:
        if r["status"] not in ("OK", "GENERIC"):
            print(f"{r['status']:10} {r['kind']:9} {r['refs'][:50]}  {r['lcsc'] or r['source']}  need {r['need']}  "
                  f"JLCPCB {r['jlc_stock']}  LCSC {r['lcsc_stock']}")
    print(cfg["settings_note"])
    print(head[0].replace("**", ""))
    if stale:
        print(stale_text)
    print(f"BOM stock check: {verdict} - {n['OK']} in stock, {short} short, {n['UNKNOWN']} UNKNOWN, "
          f"{n['NO NUMBER'] + n['BAD NUMBER']} without a valid LCSC number, {n['GENERIC']} generic; "
          f"{cls['extended']} extended line(s); report {path}")
    return 0 if verdict == "PASS" else 1


def cmd_line_audit(a, cfg, out_dir: str, tmp: str, answers: Answers | None = None, pace=None) -> int:
    bom = read_bom(cfg["bom_file"], cfg, tmp, None)
    shared: list[tuple[dict, str | None]] = []
    accepted: list[tuple[dict, str | None]] = []
    no_number: list[dict] = []
    bad_number: list[dict] = []
    no_mpn: list[dict] = []
    mixed: list[dict] = []
    by_code: dict[str, list] = {}
    for ln in bom.lines:
        fitted = sorted(ln["refs"], key=natural)
        if not fitted:
            continue
        if ln["lcsc"]:
            by_code.setdefault(ln["lcsc"], []).append(ln)
        if ln["bad_number"]:
            bad_number.append(ln)
        elif not ln["lcsc"] and ln["kind"] == "board":
            no_number.append(ln)
        if bom.has_mpn and not ln["mpn"]:
            no_mpn.append(ln)
        if len(ln["values"]) > 1:
            mixed.append(ln)
        if len(fitted) > 1:
            why = cfg["shared_ok"].get(ln["lcsc"]) if ln["lcsc"] else None
            (accepted if why else shared).append((ln, why))
    twice = {c: lns for c, lns in by_code.items() if len(lns) > 1}
    # what each LCSC number is, from saved or live answers (never guessed)
    resolved: list[dict] = []
    head: list[str] = []
    info: dict = {"mode": "numbers not resolved"}
    if answers is not None:
        for code in sorted(by_code, key=natural):
            ans = answers.get(code)
            asked = ans["jlc_found"] is not None or ans["lcsc_found"] is not None
            state = "found" if (ans["jlc_found"] or ans["lcsc_found"]) else ("NOT FOUND" if asked else "UNKNOWN")
            resolved.append({
                "lcsc": code, "state": state,
                "refs": sorted({r for ln in by_code[code] for r in ln["refs"]}, key=natural),
                "value": " / ".join(dict.fromkeys(ln["value"] for ln in by_code[code] if ln["value"])),
                "maker": ans["brand"], "mpn": ans["mpn"], "description": ans["description"],
                "package": ans["package"], "class": ans["jlc_class"],
                "answer_of": ans["jlc_asked"] or ans["lcsc_asked"]})
        head, info = _mode_lines(answers, pace, cfg)
    unknown = [e for e in resolved if e["state"] == "UNKNOWN"]
    not_found = [e for e in resolved if e["state"] == "NOT FOUND"]
    findings = len(shared) + len(bom.duplicates) + len(no_number) + len(bad_number) + len(no_mpn) + len(unknown) \
        + len(not_found)
    verdict = "PASS" if not findings else "FAIL"

    def row(ln):
        return (f"| {len(ln['refs'])} | {md_cell(', '.join(sorted(ln['refs'], key=natural)))} | "
                f"{md_cell(ln['value'] or ln['mpn'])} | {md_cell(ln['footprint'])} | {ln['lcsc'] or '(none)'} |")
    md = [f"# BOM line audit ({_stamp()})", "", f"Source: {'; '.join(bom.sources)}. {len(bom.lines)} line(s), "
          f"{sum(len(ln['refs']) for ln in bom.lines)} fitted designator(s).", "",
          f"**Result: {verdict}** - {len(shared)} shared line(s) without a written reason, {len(accepted)} shared "
          f"with a reason, {len(bom.duplicates)} duplicate designator(s), {len(no_number)} fitted line(s) without an "
          f"LCSC number, {len(bad_number)} with a malformed number, "
          + (f"{len(no_mpn)} without a maker part number." if bom.has_mpn else
             "maker part numbers not checked (the source has no such column or field).")
          + (f" LCSC numbers resolved: {len(resolved) - len(unknown) - len(not_found)} of {len(resolved)}; "
             f"{len(unknown)} UNKNOWN (no {'saved ' if answers.offline else ''}answer), {len(not_found)} not known "
             "to the source." if answers is not None else " LCSC numbers were not resolved in this run.")]
    md += [""] + head
    md += ["", "## Lines shared by more than one designator", "",
           "After the order a shared line can be changed or left out only as a whole. Give every designator whose "
           "value, fit or part may ever change its own line (another LCSC number of the same footprint, or a DNP "
           "line). For a line that can never change, write the reason into board.toml under `[bom.shared_ok]`.", ""]
    if shared:
        md += ["| Count | Designators | Value | Footprint | LCSC |", "|---|---|---|---|---|"]
        md += [row(ln) for ln, _ in sorted(shared, key=lambda t: -len(t[0]["refs"]))]
    else:
        md.append("None without a reason.")
    if accepted:
        md += ["", "Shared, with the project's reason:", "", "| Count | Designators | Value | LCSC | Reason |",
               "|---|---|---|---|---|"]
        md += [f"| {len(ln['refs'])} | {md_cell(', '.join(sorted(ln['refs'], key=natural)))} | {md_cell(ln['value'])} | "
               f"{ln['lcsc']} | {md_cell(why)} |" for ln, why in accepted]
    md += ["", "## Duplicate designators", "",
           (", ".join(bom.duplicates) + " appear more than once.") if bom.duplicates else "None."]
    md += ["", "## Fitted lines without an LCSC number", ""]
    if no_number or bad_number:
        md += ["| Count | Designators | Value | Footprint | LCSC |", "|---|---|---|---|---|"]
        md += [row(ln) for ln in no_number]
        md += [row(dict(ln, lcsc=f"not a number: {ln['bad_number']}")) for ln in bad_number]
    else:
        md.append("None.")
    if bom.has_mpn:
        md += ["", "## Fitted lines without a maker part number", ""]
        md += (["| Count | Designators | Value | Footprint | LCSC |", "|---|---|---|---|---|"] + [row(ln) for ln in no_mpn]) \
            if no_mpn else ["None."]
    if answers is not None:
        md += ["", "## What each LCSC number is", "",
               "Set the maker part against the value in the BOM: a copied or mistyped number is a wrong part on "
               "every board. UNKNOWN means that no answer is saved for the number; it is not a pass.", "",
               "| LCSC | Designators | Value in the BOM | Maker and maker part | Package | Class | Answer of |",
               "|---|---|---|---|---|---|---|"]
        for e in resolved:
            what = {"UNKNOWN": "**UNKNOWN: no saved answer**" if answers.offline else "**UNKNOWN: no answer**",
                    "NOT FOUND": "**NOT FOUND at the source**"}.get(
                        e["state"], " ".join(x for x in (e["maker"], e["mpn"]) if x) or "(no maker part in the answer)")
            if e["state"] == "found" and e["description"]:
                what += f" ({str(e['description'])[:70]})"
            refs = ", ".join(e["refs"][:10]) + (" ..." if len(e["refs"]) > 10 else "")
            md.append(f"| {e['lcsc']} | {md_cell(refs)} | {md_cell(e['value'])} | {md_cell(what)} | "
                      f"{md_cell(e['package'] or '')} | {e['class'] or ''} | {e['answer_of'] or ''} |")
    notes = list(bom.notes)
    if answers is None:
        notes.append("the LCSC numbers were not resolved (give --offline to read the saved answers, or --live): "
                     "whether each number is the intended part is not checked")
    if twice:
        notes.append("the same LCSC number on several lines (the assembler treats them as one part type): "
                     + "; ".join(f"{c} on {len(v)} lines" for c, v in sorted(twice.items())))
    if mixed:
        notes.append("one LCSC number carries different values (a copied number?): " + "; ".join(
            f"{ln['lcsc'] or '(none)'}: {' / '.join(ln['values'])} ({', '.join(sorted(ln['refs'], key=natural)[:6])})"
            for ln in mixed))
    if bom.skipped:
        notes.append("left out (excluded from the BOM in the design, or on the ignore list): "
                     + ", ".join(sorted(set(bom.skipped), key=natural)))
    dnp = sorted({r for ln in bom.lines for r in ln["dnp"]}, key=natural)
    if dnp:
        notes.append("not fitted (DNP), not audited: " + ", ".join(dnp))
    md += ["", "## Notes and what was not checked", ""] + [f"- {x}" for x in notes] + [
        "- whether a shared value may change is the designer's judgement: this audit only lists the lines",
        "", "Settings: " + cfg["settings_note"]]

    def brief(ln):
        return {"refs": sorted(ln["refs"], key=natural), "value": ln["value"], "footprint": ln["footprint"],
                "lcsc": ln["lcsc"], "mpn": ln["mpn"]}
    data = {"check": "bom_line_audit", "result": verdict, "date": _stamp(), "sources": bom.sources,
            "lines": len(bom.lines), "shared": [brief(ln) for ln, _ in shared],
            "shared_accepted": [dict(brief(ln), reason=why) for ln, why in accepted], "duplicates": bom.duplicates,
            "no_lcsc_number": [brief(ln) for ln in no_number],
            "malformed_number": [dict(brief(ln), text=ln["bad_number"]) for ln in bad_number],
            "mpn_checked": bom.has_mpn, "no_mpn": [brief(ln) for ln in no_mpn], "notes": notes, **info,
            "numbers_resolved": answers is not None, "numbers": resolved,
            "unknown_numbers": [e["lcsc"] for e in unknown], "not_found_numbers": [e["lcsc"] for e in not_found]}
    path = _write(out_dir, "bom_line_audit", "\n".join(md) + "\n", data)
    for ln, _ in sorted(shared, key=lambda t: -len(t[0]["refs"])):
        print(f"SHARED  {len(ln['refs'])} designators on one line: {', '.join(sorted(ln['refs'], key=natural))}  "
              f"{ln['value']}  {ln['lcsc'] or '(no LCSC number)'}")
    for d in bom.duplicates:
        print(f"DUPLICATE  {d}")
    for ln in no_number:
        print(f"NO LCSC NUMBER  {', '.join(sorted(ln['refs'], key=natural)[:12])}  {ln['value']}")
    for ln in bad_number:
        print(f"NOT AN LCSC NUMBER  '{ln['bad_number']}'  {', '.join(sorted(ln['refs'], key=natural)[:12])}")
    for ln in no_mpn:
        print(f"NO MAKER PART NUMBER  {', '.join(sorted(ln['refs'], key=natural)[:12])}  {ln['value']}")
    for e in unknown:
        print(f"UNKNOWN  {e['lcsc']}: no {'saved ' if answers is not None and answers.offline else ''}answer  "
              f"({', '.join(e['refs'][:12])}  {e['value']})")
    for e in not_found:
        print(f"NOT FOUND  {e['lcsc']}: the source does not know this number  ({', '.join(e['refs'][:12])}  {e['value']})")
    if head:
        print(head[0].replace("**", ""))
    print(cfg["settings_note"])
    print(f"BOM line audit: {verdict} - {len(shared)} shared line(s) without a reason, {len(bom.duplicates)} "
          f"duplicate(s), {len(no_number) + len(bad_number)} without a valid LCSC number, "
          + (f"{len(no_mpn)} without a maker part number" if bom.has_mpn else "maker part numbers not checked")
          + (f", {len(unknown)} UNKNOWN number(s), {len(not_found)} not known to the source" if answers is not None
             else ", LCSC numbers not resolved")
          + f"; report {path}")
    return 0 if verdict == "PASS" else 1


# =====================================================================================================================
# Candidates from a community copy of the parts list (`candidates`). Its answers live in a file of their own and are
# never read by bom-check, line-audit or the look-ups: the reviewers' source holds only what JLCPCB itself answered.
# =====================================================================================================================

CANDIDATES_NAME = "jlc_candidates"                    # the result: jlc_candidates.md and .json
CANDIDATES_ANSWERS_NAME = "jlc_candidates_answers.json"
CANDIDATES_FORMAT = "jlc_candidates answers v1"
COMMUNITY_ROWS = 100                # rows asked of the general search (its own default); a list sends up to 100
CANDIDATES_SHOWN = 10
# The category lists this script knows, with the (query parameter, row column) of their value filter, or None
# when the value column of that list is not known. Seen on the resistor list when this script was written
# (2026-11): the search text was ignored, `package` was applied exactly, and `resistance=10k` was read as 10 ohm
# (a plain number is sent here).
CANDIDATE_CATEGORIES = {"resistors": ("resistance", "resistance"), "capacitors": None, "microcontrollers": None,
                        "voltage_regulators": None}
SUPPLIER_DOMAINS = ("jlcpcb.com", "lcsc.com", "szlcsc.com", "easyeda.com")
_ROW_NEEDS = (("lcsc", int), ("mfr", str), ("package", str), ("is_basic", bool))
_OHM_MULT = {"": 1.0, "R": 1.0, "r": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "m": 1e-3, "G": 1e9}


def supplier_host(url: str) -> bool:
    """True when the address belongs to a supplier (the candidate search never asks one)."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in SUPPLIER_DOMAINS)


def parse_ohms(text: str) -> float:
    """A resistance as written on a schematic: 10k, 4k7, 4.7k, 100R, 100, 1M, 10m (milliohm), with or without 'ohm'."""
    s = re.sub(r"(?i)\s*(ohms?|Ω)$", "", str(text).strip()).replace("Ω", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([RrkKMmG]?)(\d*)", s)
    if not m or (m.group(3) and ("." in m.group(1) or not m.group(2))):
        raise CannotRun(f"--value '{text}' is not a resistance this script reads (examples: 10k, 4k7, 4.7k, 100R, 1M)")
    return round(float(m.group(1) + ("." + m.group(3) if m.group(3) else "")) * _OHM_MULT[m.group(2)], 9)


def _plain_number(x: float) -> str:
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.12g}"


def community_query(text: str, category: str | None, package: str | None, value_param) -> str:
    """Path and query string of the ONE request of a candidate search; also the key of its saved answer."""
    if category:
        path, params = f"/{category}/list.json", ([("search", text)] if text else [])
    else:
        path, params = "/api/search", [("q", text), ("limit", str(COMMUNITY_ROWS)), ("full", "true")]
    if package:
        params.append(("package", package))
    if value_param:
        params.append(value_param)
    return path + ("?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote) if params else "")


def community_rows(data, category: str | None) -> list:
    """The rows of an answer, or CannotRun when its form is not the one known (the service is not ours)."""
    key = category or "components"
    rows = data.get(key) if isinstance(data, dict) else None
    tail = (" The service is not ours and may have changed: nothing was saved and no list was written. Search "
            "JLCPCB's own list with `search` instead, or read the community page by hand.")
    if not isinstance(rows, list):
        got = ", ".join(map(str, list(data)[:6])) if isinstance(data, dict) else type(data).__name__
        raise CannotRun(f"the community service answered in a form this script does not know (expected a list "
                        f"'{key}', got: {got or 'an empty object'})." + tail)
    for n, r in enumerate(rows, 1):
        bad = [f for f, t in _ROW_NEEDS if not isinstance(r, dict) or not isinstance(r.get(f), t)
               or (t is int and isinstance(r.get(f), bool))]
        if bad:
            raise CannotRun(f"the community service answered in a form this script does not know (row {n} has no "
                            f"usable {', '.join(bad)})." + tail)
    return rows


def load_candidate_answers(path: str) -> dict:
    """{request: {"asked", "service", "query", "rows"}} of a saved candidates file."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise CannotRun(f"saved candidate answers {os.path.basename(path)} cannot be read: {e}") from None
    if isinstance(data, dict) and data.get("format") == CANDIDATES_FORMAT and isinstance(data.get("queries"), dict):
        return data["queries"]
    raise CannotRun(f"{os.path.basename(path)} is not a file of saved candidate answers ('{CANDIDATES_FORMAT}'); "
                    f"`candidates` never reads or writes {ANSWERS_NAME}")


def save_candidate_answers(path: str, queries: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"format": CANDIDATES_FORMAT, "written": _stamp(),
                   "source": "a community copy of JLCPCB's parts list (not JLCPCB, not LCSC): candidates only, not "
                             "confirmed; never read by bom-check, line-audit or lookup",
                   "queries": queries}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def ask_community(pace: HostPace, url: str, user_agent: str, timeout: float):
    """ONE paced GET to the community service. A redirect is not followed; any refusal stops everything."""
    def once(slot):
        status, body, final = http_fetch("GET", url, None, {"Accept": "application/json", "User-Agent": user_agent},
                                         timeout, redirects=False)
        if 300 <= status < 400:
            slot.refuse(f"HTTP {status}: a redirect, not followed")
        why = refusal_reason(status, body, final, url)
        if why:
            slot.refuse(why)
        return body
    body = paced_request(pace, urllib.parse.urlsplit(url).netloc, once)
    return json.loads(body.decode("utf-8", errors="replace"))


def _row_text(r: dict) -> str:
    """The description of a row; a list row without one is described by its attributes."""
    desc = str(r.get("description") or "").strip()
    if desc:
        return desc
    try:
        attrs = json.loads(r.get("attributes") or "{}")
    except (TypeError, ValueError):
        return ""
    if not isinstance(attrs, dict):
        return ""
    return "; ".join(f"{k}: {v}" for k, v in attrs.items() if isinstance(v, (str, int, float)))[:160]


def _words_match(r: dict, words: list[str]) -> bool:
    """Every word of the text begins a word of the row (so '10k' finds '10kOhm', never '110kOhm')."""
    hay = " ".join(str(x) for x in (f"C{r.get('lcsc')}", r.get("mfr"), r.get("package"), r.get("description"),
                                    r.get("attributes")) if x).casefold()
    return all(re.search(r"(?<![\w.])" + re.escape(w), hay) for w in words)


def _class(r: dict) -> str:
    return "basic" if r.get("is_basic") is True else ("preferred" if r.get("is_preferred") is True else "extended")


def cmd_candidates(a, cfg, out_dir: str) -> int:
    """Candidates by words and filters from the community copy: one paced request, saved in a file of its own."""
    text = " ".join(str(a.text or "").split())
    category = (a.category or "").strip().lower() or None
    package = " ".join(str(a.package or "").split()) or None
    if len(text) > SEARCH_TEXT_MAX:
        raise CannotRun(f"a search text of more than {SEARCH_TEXT_MAX} characters: '{text[:30]}...'")
    if category is not None and category not in CANDIDATE_CATEGORIES:
        raise CannotRun(f"unknown category '{category}'; the lists known here: {', '.join(CANDIDATE_CATEGORIES)}. "
                        "Without --category the general search covers every part")
    if not text and not category:
        raise CannotRun("give a search text (words such as \"10k 0402\", or a maker part number), or --category "
                        "with its filters")
    if not 1 <= a.limit <= COMMUNITY_ROWS:
        raise CannotRun(f"--limit takes 1 to {COMMUNITY_ROWS} (the candidates shown)")
    if package and (len(package) > 40 or not package.isprintable()):
        raise CannotRun("--package takes a package name of up to 40 characters, as the parts list writes it (0402, "
                        "SOT-23-5)")
    value, value_param, value_col = None, None, None
    if a.value is not None:
        spec = CANDIDATE_CATEGORIES.get(category) if category else None
        if not spec:
            raise CannotRun("--value works with --category resistors only (the one list whose value column is known: "
                            "resistance in ohms). For other parts put the value into the search text of the general "
                            "search, e.g. \"100nF 0402\"")
        value = parse_ohms(a.value)
        value_param, value_col = (spec[0], _plain_number(value)), spec[1]
    if a.save:
        raise CannotRun(f"`candidates` keeps its answers in {CANDIDATES_ANSWERS_NAME} of the results folder and "
                        f"nowhere else (never in {ANSWERS_NAME}, the reviewers' source): leave out --save")
    if (a.offline is not None) == bool(a.live):
        raise CannotRun("choose one: --offline [saved candidate answers] (no network), or --live (one paced request "
                        "to the community copy of the parts list)")
    base = str(a.community_url or "").rstrip("/")
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise CannotRun(f"--community-url '{base}' is not an http(s) address")
    if supplier_host(base):
        raise CannotRun("--community-url names a supplier's host: `candidates` asks only the community copy (JLCPCB "
                        "itself is asked with `search` and `lookup`, at their pace)")
    key = community_query(text, category, package, value_param)
    saved_path = os.path.join(out_dir, CANDIDATES_ANSWERS_NAME)
    pace, reused = None, False
    if a.offline is not None:
        src = a.offline or saved_path
        if not os.path.isfile(src):
            raise CannotRun(f"no saved candidate answers ({CANDIDATES_ANSWERS_NAME}) in {os.path.dirname(src)}: run "
                            "once with --live, or name a file after --offline")
        rec = load_candidate_answers(src).get(key)
        answers_file = os.path.basename(src)
    else:
        queries = load_candidate_answers(saved_path) if os.path.isfile(saved_path) else {}
        rec = queries.get(key)
        t = _parse_time(rec.get("asked")) if isinstance(rec, dict) else None
        reused = bool(rec and not a.fresh and t and t.astimezone().date() == _now().date())
        if not reused:
            if cfg["pace"] < PACE_MIN:
                print(f"pace raised from {cfg['pace']:g} s to the minimum of {PACE_MIN:g} s")
            pace = HostPace(cfg["pace"])
            data = ask_community(pace, base + key, a.user_agent, max(1.0, a.timeout))
            rows = community_rows(data, category)                  # an unknown form stops here: nothing is saved
            rec = queries[key] = {"asked": _stamp(), "service": parts.netloc, "query": key, "rows": rows}
            save_candidate_answers(saved_path, queries)
        answers_file = CANDIDATES_ANSWERS_NAME
    if rec is not None and not isinstance(rec, dict):
        raise CannotRun(f"{answers_file}: the saved answer of {key} is not in the known form")
    rows = community_rows({category or "components": rec.get("rows")}, category) if rec else []
    service = (rec or {}).get("service") or parts.netloc
    read = (rec or {}).get("asked")
    t = _parse_time(read)
    read_txt = f"{t:%Y-%m-%d %H:%M}" if t else "an unknown time"

    words = text.casefold().split()
    kept = []
    for r in rows:
        if package and str(r["package"]).strip().casefold() != package.casefold():
            continue
        if value is not None:
            v = r.get(value_col)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or abs(v - value) > 1e-9 * max(1.0, value):
                continue
        if a.basic_only and r["is_basic"] is not True:
            continue
        if words and not _words_match(r, words):
            continue
        kept.append(r)
    shown = kept[:a.limit]
    status = f"CANDIDATE: community copy read {read_txt}, not confirmed"
    cands = [{"lcsc": f"C{r['lcsc']}", "mpn": r["mfr"], "package": r["package"], "class": _class(r),
              "stock_in_copy": r.get("stock"), "price_usd_in_copy": r.get("price", r.get("price1")),
              "description": _row_text(r), "status": status, "read": read} for r in shown]

    asked = [f"text \"{text}\"" if text else "no text", f"category {category}" if category else "general search",
             f"package {package}" if package else "any package"]
    asked += ([f"value {a.value} ({_plain_number(value)} ohm)"] if value is not None else [])
    asked += ["basic only" if a.basic_only else "any class"]
    if a.offline is not None:
        head = f"**Offline: saved answer of {read_txt}** (file `{answers_file}`). Nothing was asked now."
    elif reused:
        head = (f"**Live**: the saved answer of today ({read_txt}) reused from `{answers_file}`; 0 requests sent "
                "(--fresh asks again).")
    else:
        head = (f"**Live answer** of the community service {service}, public, no sign-in: {pace.summary()}; pace "
                f"{pace.base:g} s plus a random 0 to 100 %. Saved in `{answers_file}`.")
    md = [f"# Part candidates ({_stamp()})", "",
          f"**CANDIDATES, not confirmed.** From a community copy of JLCPCB's parts list ({service}, kept by others: "
          f"not JLCPCB, not LCSC), read {read_txt}. Its class, stock and price may be old or missing. Before a part "
          "enters the BOM, read its class, stock and price at JLCPCB itself with the paced look-up "
          "(`jlc_parts.py --live lookup <C numbers>`), and let its datasheet decide that it suits the circuit. This "
          "list changes no BOM file and is never read by `bom-check` or `line-audit`.", "", head, "",
          f"Query: {'; '.join(asked)} (request `{key}`)."]
    if rec is None:
        verdict = "FAIL"
        md += ["", "**Result: FAIL** - UNKNOWN: no saved answer for this query. Ask it once with `--live` (one "
               "request to the community service)."]
    else:
        md += ["", f"The service sent {len(rows)} row(s); {len(kept)} passed the filters (the words of the text, "
               f"package, value, basic only); showing the first {len(shown)}, in the order the service gives them."]
        if kept:
            verdict = "PASS"
            md += ["", f"**Result: PASS (candidates found, not confirmed)** - {len(kept)} candidate(s).", "",
                   "| # | LCSC number | Maker part | Package | Class (copy) | Stock (copy) | Price, USD (copy) | "
                   "Description | Status |", "|---|---|---|---|---|---|---|---|---|"]
            for i, c in enumerate(cands, 1):
                stock = "none in the copy" if c["stock_in_copy"] in (None, 0) else c["stock_in_copy"]
                price = "-" if c["price_usd_in_copy"] is None else f"{c['price_usd_in_copy']:g}"
                d = c["description"]
                md.append(f"| {i} | {c['lcsc']} | {md_cell(c['mpn'])} | {md_cell(c['package'])} | {c['class']} | "
                          f"{stock} | {price} | {md_cell(d[:110] + ('...' if len(d) > 110 else ''))} | {status} |")
        else:
            verdict = "FAIL"
            md += ["", f"**Result: FAIL** - no candidate after the filters ({len(rows)} row(s) from the service). "
                   "This proves nothing: the copy can be incomplete or old. Change the text or the filters, or "
                   "search JLCPCB's own list with `search`."]
    md += ["", "How to read this:",
           "- Every row is a candidate from a copy kept by others. Class, stock and price are confirmed at JLCPCB "
           "itself with `lookup` (paced; its answers go to jlc_parts_answers.json, the reviewers' source) before "
           "a number enters the BOM.",
           "- The words of the text are checked by this script on every row: each must begin a word of the row "
           "(LCSC number, maker part, package, description, attributes).",
           "- Seen on the live service when this script was written (2026-11): a category list ignored the search "
           "text; a value written '10k' was read as 10 (this script sends plain numbers and checks each row); most "
           "rows of one list had no stock in the copy, a basic part among them.",
           "", "Not checked: whether a part suits the circuit; JLCPCB's and LCSC's stock and class today; the life "
           "cycle; prices in the cart.", "", "Settings: " + cfg["settings_note"]]
    data = {"check": "jlc_candidates", "result": verdict, "date": _stamp(), "confirmed": False,
            "source": "community copy of JLCPCB's parts list (not JLCPCB, not LCSC)", "service": service,
            "read": read, "mode": "offline" if a.offline is not None else "live",
            "requests": len(pace.sent) if pace else 0, "reused_same_day": reused, "answers_file": answers_file,
            "query": {"text": text, "category": category, "package": package, "value": a.value,
                      "value_number": value, "basic_only": bool(a.basic_only), "limit": a.limit, "request": key},
            "unknown": rec is None, "rows_from_service": len(rows) if rec is not None else None,
            "rows_kept": len(kept), "candidates": cands,
            "confirm_with": "python -I jlc_parts.py --live lookup " + " ".join(c["lcsc"] for c in cands)}
    path = _write(out_dir, CANDIDATES_NAME, "\n".join(md) + "\n", data)
    for c in cands:
        print(f"  {c['lcsc']:10} {c['class']:9} {str(c['package'])[:14]:14} stock in the copy {c['stock_in_copy']}  "
              f"{c['mpn']}")
    if rec is None:
        print(f"candidates \"{text or category}\": UNKNOWN, no saved answer for this query")
    print(cfg["settings_note"])
    print(head.replace("**", ""))
    print(f"CANDIDATES from a community copy, not confirmed (confirm with `lookup`): {verdict} - "
          + (f"{len(kept)} of {len(rows)} row(s) passed the filters" if rec is not None else "UNKNOWN")
          + f"; report {path}")
    return 0 if verdict == "PASS" else 1


# =====================================================================================================================
# Settings and command line
# =====================================================================================================================

def _as_list(v) -> list:
    return [] if v is None else ([v] if isinstance(v, str) else list(v))


def settings(a) -> dict:
    """Command line over board.toml over defaults; the note says which were used."""
    import kicad_io
    toml = {}
    used = []
    if a.project:
        try:
            toml = kicad_io.load_settings(a.project)
        except kicad_io.KicadIOError as e:
            raise CannotRun(str(e)) from None
        used.append("board.toml" if toml else "no board.toml: defaults")
    else:
        used.append("no project folder: defaults and the command line")
    b = toml.get("bom", {})
    cfg = {
        "lcsc_fields": a.lcsc_field or _as_list(b.get("lcsc_field")) or LCSC_FIELDS,
        "mpn_fields": a.mpn_field or _as_list(b.get("mpn_field")) or MPN_FIELDS,
        "hand_fit": set(_as_list(b.get("hand_fit")) + [r for x in a.hand_fit for r in _split_refs(x)]),
        "dnp": set(_as_list(b.get("dnp")) + [r for x in a.dnp for r in _split_refs(x)]),
        "ignore": _as_list(b.get("ignore")) + a.ignore,
        "boards": a.boards if getattr(a, "boards", None) is not None else int(b.get("boards", 5)),
        "spares_pct": a.spares if getattr(a, "spares", None) is not None else float(b.get("spares_pct", 20)),
        "spares_min": a.spares_min if getattr(a, "spares_min", None) is not None else int(b.get("spares_min", 2)),
        "extended_fee_usd": a.extended_fee if getattr(a, "extended_fee", None) is not None
        else b.get("extended_fee_usd"),
        "max_age_hours": a.max_age_hours if getattr(a, "max_age_hours", None) is not None else b.get("max_age_hours"),
        "shared_ok": dict(b.get("shared_ok", {})),
        "fees": [],
        "pace": a.pace if a.pace is not None else float(toml.get("parts", {}).get("pace_s", PACE_DEFAULT)),
        "bom_file": None, "offboard": None,
    }
    for item in getattr(a, "fee", []) or []:
        name, _, usd = item.partition("=")
        try:
            cfg["fees"].append((name.strip(), float(usd)))
        except ValueError:
            raise CannotRun(f"--fee wants NAME=USD, got '{item}'") from None
    for item in getattr(a, "accept_shared", []) or []:
        code, _, why = item.partition("=")
        cfg["shared_ok"][code.strip().upper()] = why.strip() or "accepted on the command line"
    if cfg["boards"] < 1 or cfg["spares_pct"] < 0 or cfg["spares_min"] < 0:
        raise CannotRun("--boards must be 1 or more; spares cannot be negative")
    bom_arg = getattr(a, "bom", None)
    if a.cmd in ("bom-check", "line-audit"):
        if bom_arg:
            cfg["bom_file"] = bom_arg
        elif a.project:
            cand = [os.path.join(a.project, b["file"])] if b.get("file") else []
            try:
                files = kicad_io.project_files(a.project, toml)
                cand += [os.path.join(files["out"], "netlist.net")] + ([files["sch"]] if files["sch"] else [])
            except kicad_io.KicadIOError as e:           # no (single) KiCad project there: an exported netlist will do
                net = os.path.join(a.project, toml.get("project", {}).get("out_dir", "out"), "netlist.net")
                if not cand and not os.path.isfile(net):
                    raise CannotRun(f"{e}; and no BOM source is named in board.toml ([bom] file)") from None
                cand.append(net)
            cfg["bom_file"] = next((c for c in cand if c and os.path.isfile(c)), cand[0] if cand else None)
            used.append(f"BOM source {os.path.basename(cfg['bom_file'] or '?')}")
        if not cfg["bom_file"]:
            raise CannotRun("no BOM source: give a BOM file, a netlist or a schematic, or --project")
        off = getattr(a, "offboard", None) or (os.path.join(a.project, b["offboard"]) if a.project and b.get("offboard")
                                               else None)
        cfg["offboard"] = off
    cfg["settings_note"] = (f"{'; '.join(used)}; LCSC number read from: {', '.join(cfg['lcsc_fields'][:4])}"
                            + (" ..." if len(cfg["lcsc_fields"]) > 4 else "")
                            + (f"; {cfg['boards']} boards, spares {cfg['spares_pct']:g} % (at least {cfg['spares_min']})"
                               if a.cmd == "bom-check" else "")
                            + (f"; hand-fit: {', '.join(sorted(cfg['hand_fit'], key=natural))}" if cfg["hand_fit"] else "")
                            + (f"; ignored: {', '.join(cfg['ignore'])}" if cfg["ignore"] else ""))
    return cfg


def _results_folder(a, bom_file: str | None) -> str:
    import kicad_io
    if a.out:
        out = os.path.abspath(a.out)
    elif a.project:
        try:
            out = kicad_io.project_files(a.project)["out"]
        except kicad_io.KicadIOError:
            out = os.path.join(os.path.abspath(a.project), "out")
    else:
        raise CannotRun("give --project <board folder>, or input paths together with --out <folder>")
    if a.out and bom_file and os.path.isfile(bom_file):
        design = os.path.normcase(os.path.dirname(os.path.abspath(bom_file)))
        if (os.path.normcase(out) + os.sep).startswith(design + os.sep) and any(
                n.lower().endswith((".kicad_sch", ".kicad_pcb", ".kicad_pro")) for n in os.listdir(design)):
            raise CannotRun("--out lies inside the folder of the input design; a design that is only read is never "
                            "written into: choose another folder")
    return out


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
    ap = argparse.ArgumentParser(description="JLCPCB / LCSC parts: search by name, candidates from a community copy "
                                             "(not confirmed), look-up, BOM stock check, BOM line audit. Exit 0 pass, "
                                             "1 findings, 2 could not run.")
    ap.add_argument("--project", help="hardware/board folder (reads board.toml, writes into <project>/out/)")
    ap.add_argument("--out", help="results folder when no project folder is used")
    ap.add_argument("--offline", metavar="FILE", nargs="?", const="",
                    help=f"no network: read saved answers (without FILE: {ANSWERS_NAME} of the results folder)")
    ap.add_argument("--live", action="store_true", help="ask the suppliers' public services (needs the user's yes)")
    ap.add_argument("--fresh", action="store_true", help="live: ask again even when an answer of today is saved")
    ap.add_argument("--save", metavar="FILE", help=f"live: another file for the answers (default {ANSWERS_NAME} in "
                                                   "the results folder; merged into an existing file)")
    ap.add_argument("--sources", default="jlc,lcsc", help="live: services to ask, of jlc and lcsc (default both)")
    ap.add_argument("--pace", type=float, help=f"live: seconds between requests to one host (default "
                                               f"{PACE_DEFAULT:g}, plus a random 0 to 100 %%; never below {PACE_MIN:g})")
    ap.add_argument("--jlc-url", default=JLC_URL, help="address of JLCPCB's parts search (it is undocumented and may move)")
    ap.add_argument("--lcsc-url", default=LCSC_URL, help="address of LCSC's product detail (the same)")
    ap.add_argument("--community-url", default=COMMUNITY_URL,
                    help=f"candidates: address of the community copy of the parts list (default {COMMUNITY_URL}; "
                         "never a supplier's host)")
    ap.add_argument("--user-agent", default=USER_AGENT, help="client name sent with live requests")
    ap.add_argument("--timeout", type=float, default=HTTP_TIMEOUT, help=f"live: seconds to wait for one answer "
                                                                        f"(default {HTTP_TIMEOUT:g})")
    ap.add_argument("--lcsc-field", action="append", help="column or symbol field with the LCSC number (repeatable; "
                                                          "default: " + ", ".join(LCSC_FIELDS[:5]) + ", ...)")
    ap.add_argument("--mpn-field", action="append", help="column or symbol field with the maker part number")
    ap.add_argument("--hand-fit", action="append", default=[], help="designators fitted by hand (comma list)")
    ap.add_argument("--dnp", action="append", default=[], help="designators not fitted, besides the marks in the BOM")
    ap.add_argument("--ignore", action="append", default=[], help="reference pattern that is nothing to buy, e.g. 'TP*'")
    sub = ap.add_subparsers(dest="cmd")
    se = sub.add_parser("search", help="LCSC numbers by maker part number or words: the first results of JLCPCB's "
                                       "parts search, one request per text")
    se.add_argument("words", nargs="+", help="one search text per argument, e.g. LM2903DR \"100k NTC 0603\"")
    se.add_argument("--results", type=int, default=SEARCH_RESULTS,
                    help=f"results read per text (default {SEARCH_RESULTS}, at most {SEARCH_RESULTS_MAX})")
    ca = sub.add_parser("candidates", help="a first search for candidate parts, with filters, in a community copy of "
                                           "JLCPCB's parts list (not confirmed; confirm with lookup)")
    ca.add_argument("text", nargs="?", help="words such as \"10k 0402\" or a maker part number (optional with --category)")
    ca.add_argument("--category", help=f"one list of the community copy: {', '.join(CANDIDATE_CATEGORIES)}")
    ca.add_argument("--package", help="exact package, as the parts list writes it (0402, SOT-23-5)")
    ca.add_argument("--value", help="with --category resistors: the resistance (10k, 4k7, 100R)")
    ca.add_argument("--basic-only", action="store_true", help="only parts of JLCPCB's basic class (in the copy)")
    ca.add_argument("--limit", type=int, default=CANDIDATES_SHOWN,
                    help=f"candidates shown (default {CANDIDATES_SHOWN}, at most {COMMUNITY_ROWS})")
    lk = sub.add_parser("lookup", help="stock, class and prices of LCSC numbers")
    lk.add_argument("codes", nargs="+", help="LCSC numbers (C12345)")
    bc = sub.add_parser("bom-check", help="dated stock table for N boards plus spares")
    bc.add_argument("bom", nargs="?", help="BOM table (CSV), KiCad netlist or root schematic")
    bc.add_argument("--offboard", help="CSV list of the off-board parts")
    bc.add_argument("--boards", type=int, help="number of boards (default 5)")
    bc.add_argument("--spares", type=float, help="spares per line in percent (default 20)")
    bc.add_argument("--spares-min", type=int, help="spares per line, at least (default 2)")
    bc.add_argument("--extended-fee", type=float, help="fee in USD per extended line and order (from the live page)")
    bc.add_argument("--fee", action="append", default=[], metavar="NAME=USD", help="another per-order fee (repeatable)")
    bc.add_argument("--max-age-hours", type=float, help="offline: a saved answer of a BOM line older than this many "
                                                        "hours, or without a date, fails the check as STALE")
    la = sub.add_parser("line-audit", help="shared lines, duplicate designators, missing LCSC numbers")
    la.add_argument("bom", nargs="?", help="BOM table (CSV), KiCad netlist or root schematic")
    la.add_argument("--accept-shared", action="append", default=[], metavar="LCSC=REASON",
                    help="a shared line that can never change, with the reason (repeatable)")
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, tok in enumerate(argv):          # `--offline` without a file name, directly before the sub-command
        if tok == "--offline" and (i + 1 == len(argv) or argv[i + 1].startswith("-")
                                   or argv[i + 1] in ("search", "candidates", "lookup", "bom-check", "line-audit")):
            argv[i] = "--offline="
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_usage(sys.stderr)
        return 2
    try:
        cfg = settings(a)
        out_dir = _results_folder(a, cfg["bom_file"])
        if a.cmd == "candidates":                           # its own answers file; never the reviewers' one
            return cmd_candidates(a, cfg, out_dir)
        with tempfile.TemporaryDirectory(prefix="jlc-parts-") as tmp:
            offline = a.offline
            if offline == "":                               # --offline without a file: the default answers file
                offline = os.path.join(out_dir, ANSWERS_NAME)
                if not os.path.isfile(offline):
                    raise CannotRun(f"no saved answers ({ANSWERS_NAME}) in {out_dir}: run once with --live (needs "
                                    "the user's yes), or name a file after --offline")
            if a.cmd == "line-audit" and offline is None and not a.live:
                return cmd_line_audit(a, cfg, out_dir, tmp)
            if (offline is not None) == bool(a.live):
                raise CannotRun("choose one: --offline [saved answers] (no network), or --live (asks the suppliers' "
                                "public services, paced; needs the user's yes once)")
            pace, live = None, None
            if a.live:
                if cfg["pace"] < PACE_MIN:
                    print(f"pace raised from {cfg['pace']:g} s to the minimum of {PACE_MIN:g} s")
                sources = [s.strip().lower() for s in a.sources.split(",") if s.strip()]
                if not sources or any(s not in ("jlc", "lcsc") for s in sources):
                    raise CannotRun("--sources takes jlc, lcsc or both")
                if a.cmd == "search":
                    sources = ["jlc"]                       # a search asks JLCPCB's parts search only
                pace = HostPace(cfg["pace"])
                live = Live(pace, sources, a.jlc_url, a.lcsc_url, a.user_agent, max(1.0, a.timeout))
            answers = Answers(offline, live, (a.save or os.path.join(out_dir, ANSWERS_NAME)) if a.live else None,
                              a.fresh)
            try:
                if a.cmd == "search":
                    return cmd_search(a, cfg, answers, pace, out_dir)
                if a.cmd == "lookup":
                    return cmd_lookup(a, cfg, answers, pace, out_dir)
                if a.cmd == "line-audit":
                    return cmd_line_audit(a, cfg, out_dir, tmp, answers, pace)
                return cmd_bom_check(a, cfg, answers, pace, out_dir, tmp)
            finally:
                if pace is not None:
                    print(f"live: {pace.summary()}; answers saved in {answers.save_path}")
    except Refused as e:
        print(f"CANNOT RUN (REFUSED): {e}", file=sys.stderr)
        return 2
    except CannotRun as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
