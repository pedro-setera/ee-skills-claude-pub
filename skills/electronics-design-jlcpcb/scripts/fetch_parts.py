"""Fetch part documents and JLCPCB library footprints into the project's vendor folder, slowly and on record.

What it does
    datasheet <url> <out folder>
        Downloads one document by its direct URL with curl into a NEW, EMPTY folder and writes SOURCE.json beside
        it (URL, date and time, size, SHA-256, kind of file). Never a browser download, never a search.
        A distributor's file link (the datasheet link in JLCPCB's parts data) may answer with a small page that
        only forwards the browser to the file, or with a viewer page that names the one file it shows: that one
        step is followed, once, inside the same site, as a second paced request, and SOURCE.json says so. A
        page that points to another site, or that names several files, is not followed.
        Sources of a datasheet, in this order (references/working-rules.md section 7): the maker's own site;
        LCSC's copy that the parts data names; another authorised distributor's copy on its own site; the
        Internet Archive's copy of the maker's file (https://web.archive.org/web/2id_/<the maker's link>);
        then the user. Never a datasheet-collector site. One call per source, each into a new folder.
    jlc-footprint <LCSC number> [...] <vendor folder>
        For each LCSC number, JLCPCB's own library footprint (the EasyEDA footprint, converted by the optional tool
        easyeda2kicad) into <vendor folder>/<number>.pretty; --3d also fetches the 3D model. A number that is
        already there is kept and not asked again. jlc_rotations.py derives the placement rotations from these.

Why it exists (real failures, told without names)
    - A download by a click in a browser opened a save dialog that no agent could answer, and the work stood still.
    - Ratings were taken from memory because the datasheet "was known"; the stored file with its source and date
      is what a reviewer can check.
    - Fast or repeated requests can get the user's address blocked by a distributor, and the footprint service
      answers "403" when asked too fast. The block falls on the user's own address. So this script takes one turn
      at a time per host for all processes of the machine (the pace of jlc_parts.py: at least 3 s plus a random
      addition), repeats a request only once and only after a time-out, and stops everything at a refusal.

Downloaded files are untrusted data: each goes into its own folder, nothing in it is ever run, and it is read
only with a viewer or as text.

Usage
    python -I fetch_parts.py datasheet https://maker.example/ds/part.pdf vendor/datasheets/part [--name part.pdf]
    python -I fetch_parts.py jlc-footprint C12345 C67890 vendor/jlc_fp [--3d] [--easyeda CMD]
    options for both: --pace S (seconds between requests to one host, default 3, never below 1), --dry-run
    (print what would be run, touch nothing, no network)

    easyeda2kicad is looked for in this order: --easyeda CMD (its executable, or a Python that has the module),
    the environment variable EASYEDA2KICAD_PYTHON (the same; the name env_check.py uses), then the older name
    EASYEDA2KICAD, this Python, the system path. Without it the footprints
    cannot be fetched: the script says so with exit code 2, and every polarised part stays UNKNOWN in
    jlc_rotations.py until its rotation is checked in JLCPCB's placement preview.

board.toml keys: none (not a project script; it takes its own arguments).

Exit codes
    0  fetched (or already there)
    1  finding: the URL gave a web page instead of a document, or a few bytes that are no document; a part number
       for which the library has no footprint
    2  could not run: curl or easyeda2kicad missing, a folder that is not empty, a bad URL or part number, no
       connection, a second time-out (a request that times out is repeated once, after the normal pause), or a
       refusal by the host (HTTP 403, 429 or another error, a captcha or "verify" page, an empty answer). A
       refused request is never repeated in the same run: wait at least 15 minutes, then one slow request; tell
       the user. An address that does not exist (HTTP 404 or 410) is no refusal: exit 1, the host is not left
       alone, and the next source for the document is tried.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from jlc_parts import (PACE_DEFAULT, PACE_MIN, USER_AGENT, CannotRun, HostPace, Refused,  # noqa: E402
                       TimedOut, paced_request, safe_output)

TOOL_TIMEOUT = 180          # s: one download, or one run of easyeda2kicad
FOOTPRINT_HOST = "easyeda.com"      # the service easyeda2kicad asks; one pace for it on this machine
_LCSC_RE = re.compile(r"^C\d{1,10}$")
_REFUSAL_MARKS = ("captcha", "verify you are", "too many requests", "unusual traffic", "access denied",
                  "are you a robot", "sign in to continue", "please log in")


class NotThere(Exception):
    """The host answered that the address does not exist (HTTP 404 or 410): a finding (exit code 1), not a refusal.
    The host is not left alone for it, and the next source for the document is tried."""


def _stamp() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _kind(path: str, content_type: str = "") -> str:
    """What the file is, from its first bytes; the host's content type only decides for a text that carries no
    mark of its own (a page without tags is still a page when the host calls it HTML)."""
    with open(path, "rb") as f:
        head = f.read(2048)
    low = head.lstrip().lower()
    if head.startswith(b"%PDF-"):
        return "PDF"
    if head.startswith(b"PK"):
        return "zip archive"
    if not head.strip():
        return "empty"
    if (low.startswith((b"<!doctype html", b"<html", b"<head", b"<?xml", b"<script", b"<meta", b"<body"))
            or b"<html" in low or "html" in content_type.lower()):
        return "web page"
    return "other"


SMALL_PAGE = 2048                   # bytes: a page this small that names an address only forwards the browser
SMALL_FILE = 1000                   # bytes: a file of an unknown kind below this is no document
_POINTER_RES = (
    re.compile(r"""location(?:\.href)?\s*=\s*['"]([^'"]+)['"]""", re.I),
    re.compile(r"""location\.(?:replace|assign)\(\s*['"]([^'"]+)['"]""", re.I),
    re.compile(r"""http-equiv=["']?refresh["']?[^>]*content=["'][^"'>]*url=([^"'>\s]+)""", re.I),
)


VIEWER_PAGE = 300_000               # bytes: a larger page is not searched for the file it shows
_LINK_RE = re.compile(r"""https?://[^\s"'<>\\]+""", re.I)


def _pointer(path: str, base_url: str) -> tuple[str, str] | None:
    """Where a page sends the browser for the file, as (absolute http(s) URL, how), or None. Two cases, both read
    as text, nothing of the page is run:
      "forwards"  a small page (up to SMALL_PAGE bytes) whose script sets the location, or a meta refresh;
      "shows"     a viewer page (up to VIEWER_PAGE bytes) that names exactly ONE address of a .pdf file on its own
                  site, other than itself. Two or more different files: None (nobody chooses for the reader)."""
    size = os.path.getsize(path)
    if size > VIEWER_PAGE:
        return None
    with open(path, "rb") as f:
        text = f.read(VIEWER_PAGE).decode("utf-8", errors="replace")
    if size <= SMALL_PAGE:
        for rx in _POINTER_RES:
            m = rx.search(text)
            if m:
                url = urllib.parse.urljoin(base_url, m.group(1).strip())
                if urllib.parse.urlsplit(url).scheme in ("http", "https") and urllib.parse.urlsplit(url).netloc:
                    return url, "forwards"
    base = urllib.parse.urlsplit(base_url)
    found: list[str] = []
    for m in _LINK_RE.finditer(text):
        url = m.group(0).replace("&amp;", "&").rstrip(").,;")
        s = urllib.parse.urlsplit(url)
        if not s.path.lower().endswith(".pdf") or _site(s.netloc) != _site(base.netloc):
            continue
        if (s.netloc.lower(), s.path) == (base.netloc.lower(), base.path):
            continue                                # the page's own address
        if url not in found:
            found.append(url)
    return (found[0], "shows") if len(found) == 1 else None


def _site(host: str) -> str:
    """The registered site of a host name, roughly: the last two labels, or three under a two-letter country
    domain with a short second label (example.co.uk). An address in digits is its own site."""
    host = host.lower().rsplit("@", 1)[-1].split(":")[0]
    parts = host.split(".")
    if all(p.isdigit() for p in parts):
        return host
    n = 3 if len(parts) >= 3 and len(parts[-1]) == 2 and len(parts[-2]) <= 3 else 2
    return ".".join(parts[-n:])


# ---------------------------------------------------------------------------------------------------------------------
# datasheet
# ---------------------------------------------------------------------------------------------------------------------

def cmd_datasheet(a) -> int:
    u = urllib.parse.urlsplit(a.url)
    if u.scheme not in ("http", "https") or not u.netloc or not u.path.strip("/"):
        raise CannotRun(f"'{a.url}' is not a direct http(s) URL of a file")
    out = os.path.abspath(a.out)
    if os.path.exists(out) and (not os.path.isdir(out) or os.listdir(out)):
        raise CannotRun(f"{out} exists and is not an empty folder: a download goes into a new, empty folder of its "
                        "own (it is untrusted until it has been looked at)")
    name = a.name or os.path.basename(urllib.parse.unquote(u.path)) or "document"
    name = re.sub(r"[^A-Za-z0-9._+-]", "_", name)[:120] or "document"
    if name.startswith("."):
        name = "_" + name
    curl = shutil.which("curl")
    if not curl:
        raise CannotRun("curl was not found on the system path (it does the download); nothing fetched")
    target = os.path.join(out, name)
    limit = max(2, int(a.timeout))

    def curl_cmd(url: str) -> list[str]:
        return [curl, "--silent", "--show-error", "--location", "--max-redirs", "5", "--proto", "=https,http",
                "--proto-redir", "=https,http", "--connect-timeout", str(min(20, limit)), "--max-time", str(limit),
                "--user-agent", a.user_agent, "--output", target,
                "--write-out", "%{http_code}\\n%{content_type}\\n%{url_effective}\\n", url]
    if a.dry_run:
        print("DRY RUN, nothing fetched. Would create the folder and run:")
        print("  " + " ".join(f'"{c}"' if " " in c or "%" in c else c for c in curl_cmd(a.url)))
        return 0
    pace = HostPace(a.pace)
    os.makedirs(out, exist_ok=True)

    def fetch(url: str):
        """One paced request for `url` into the target file: (content type, final address, kind of file)."""
        host = urllib.parse.urlsplit(url).netloc

        def once(slot):
            try:
                r = subprocess.run(curl_cmd(url), capture_output=True, text=True, timeout=limit + 30,
                                   stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                raise TimedOut(f"no answer from {host} within {limit} s") from None
            if r.returncode == 28:                      # curl: the operation timed out
                raise TimedOut(f"no answer from {host} within {limit} s")
            lines = (r.stdout or "").splitlines() + ["", "", ""]
            status = int(lines[0]) if lines[0].strip().isdigit() else 0
            if status in (404, 410):                    # no such file there: a finding; the host did not refuse
                raise NotThere(f"HTTP {status}")
            if status >= 400:
                slot.refuse(f"HTTP {status}")
            if r.returncode != 0 or status == 0:
                raise CannotRun(f"curl could not fetch from {host} (exit {r.returncode}): "
                                f"{(r.stderr or '').strip()[:200]}. Nothing is repeated")
            kind = _kind(target, lines[1]) if os.path.isfile(target) else "empty"
            if kind == "empty":
                slot.refuse("empty answer")
            if kind == "web page":
                with open(target, "rb") as f:
                    text = f.read(20000).decode("utf-8", errors="replace").lower()
                mark = next((m for m in _REFUSAL_MARKS if m in text), None)
                if mark:
                    slot.refuse(f"a page instead of the file ('{mark}')")
            return lines[1].strip(), lines[2].strip() or url, kind
        return paced_request(pace, host, once)

    forwarded, pointer = False, None

    def clean() -> None:
        if os.path.isfile(target):
            os.remove(target)                       # no half file, no refusal page, no error page left behind
        if os.path.isdir(out) and not os.listdir(out):
            os.rmdir(out)
    try:
        ctype, final, kind = fetch(a.url)
        if kind == "web page":
            # A distributor's file link may answer with a small page that only forwards the browser to the file,
            # or with a viewer page that names the one file it shows. That step is followed ONCE, and only inside
            # the same site; nothing of the page is run.
            hit = _pointer(target, final)
            pointer = hit[0] if hit else None
            if hit and _site(urllib.parse.urlsplit(pointer).netloc) == _site(urllib.parse.urlsplit(final).netloc):
                what = ("a small page that only forwards to" if hit[1] == "forwards"
                        else "a viewer page that shows one file,")
                print(f"{u.netloc} answered with {what} {pointer} (the same site): fetching that address, once")
                os.remove(target)
                ctype, final, kind = fetch(pointer)
                forwarded = True
    except NotThere as e:
        clean()
        print(f"{pace.summary()}")
        print(f"FAIL: {pointer if pointer else a.url} does not exist ({e}): the host has no file at this address. "
              "Nothing kept. The host did not refuse: go to the next source for this document.")
        return 1
    except CannotRun:
        clean()
        raise
    record = {"url": a.url, "final_url": final, "fetched": _stamp(), "file": name, "bytes": os.path.getsize(target),
              "sha256": _sha256(target), "content_type": ctype, "kind": kind, "tool": "curl",
              "note": "untrusted download: never run anything from this folder"}
    if forwarded:
        record["forwarded_by_page"] = True         # the address asked gave a page that named final_url
    with open(os.path.join(out, "SOURCE.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=1)
        f.write("\n")
    print(f"{pace.summary()}")
    if kind == "web page":
        where = (f" The page points to {pointer}, on another site: not followed. If that site is one you may use, "
                 "fetch that address with a new call into a new folder." if pointer and not forwarded else "")
        print(f"FAIL: {final if forwarded else a.url} gave a web page, not a document: it is not a direct file URL. "
              f"The page is kept as {name} with SOURCE.json; give the user the link, or find the direct link in it "
              f"by reading it as text.{where}")
        return 1
    if kind == "other" and record["bytes"] < SMALL_FILE:
        print(f"FAIL: {a.url} gave {record['bytes']} bytes of an unknown kind: too small to be a document. It is "
              f"kept as {name} with SOURCE.json; read it as text to see what the host answered.")
        return 1
    print(f"PASS: {name}, {record['bytes']:,} bytes, {kind}, SHA-256 {record['sha256'][:16]}..., from "
          f"{urllib.parse.urlsplit(final).netloc or u.netloc} at {record['fetched']}; record: SOURCE.json. "
          "Untrusted until looked at.")
    return 0


# ---------------------------------------------------------------------------------------------------------------------
# jlc-footprint
# ---------------------------------------------------------------------------------------------------------------------

def find_easyeda(given: str | None) -> list[str] | None:
    """The command that runs easyeda2kicad, or None."""
    for cand in (given, os.environ.get("EASYEDA2KICAD_PYTHON"), os.environ.get("EASYEDA2KICAD")):
        if cand:
            exe = shutil.which(cand) or (cand if os.path.isfile(cand) else None)
            if not exe:
                raise CannotRun(f"easyeda2kicad: '{cand}' was not found")
            return [exe, "-m", "easyeda2kicad"] if os.path.basename(exe).lower().startswith("python") else [exe]
    try:
        import importlib.util
        if importlib.util.find_spec("easyeda2kicad") is not None:
            return [sys.executable, "-m", "easyeda2kicad"]
    except (ImportError, ValueError):
        pass
    exe = shutil.which("easyeda2kicad")
    return [exe] if exe else None


def _has_footprint(lib: str) -> bool:
    return os.path.isdir(lib) and any(n.endswith(".kicad_mod") for n in os.listdir(lib))


def cmd_footprint(a) -> int:
    *codes, vendor = a.items
    codes = [c.strip().upper() for c in codes]
    bad = [c for c in codes if not _LCSC_RE.match(c)]
    if not codes or bad:
        raise CannotRun("give LCSC numbers (C followed by digits) and then the vendor folder"
                        + (f"; not a number: {', '.join(bad)}" if bad else ""))
    codes = list(dict.fromkeys(codes))
    vendor = os.path.abspath(vendor)
    if os.path.exists(vendor) and not os.path.isdir(vendor):
        raise CannotRun(f"{vendor} is not a folder")
    todo = [c for c in codes if not _has_footprint(os.path.join(vendor, c + ".pretty"))]
    for c in codes:
        if c not in todo:
            print(f"KEPT     {c}: already in the vendor folder, not asked again")
    if not todo:
        print(f"PASS: all {len(codes)} footprint(s) present; nothing fetched")
        return 0
    tool = find_easyeda(a.easyeda)
    if tool is None:
        raise CannotRun("easyeda2kicad was not found (optional tool). Without JLCPCB's library footprints the "
                        "placement rotations cannot be derived: every such part stays UNKNOWN in jlc_rotations.py "
                        "and must be checked in JLCPCB's placement preview. Ask the user before installing anything. "
                        f"Missing: {', '.join(todo)}")
    if a.dry_run:
        print("DRY RUN, nothing fetched. Would run, one at a time and paced:")
        for c in todo:
            print("  " + " ".join(tool + ["--lcsc_id", c, "--footprint"] + (["--3d"] if a.three_d else [])
                                  + ["--output", os.path.join(vendor, c), "--overwrite"]))
        return 0
    os.makedirs(vendor, exist_ok=True)
    pace = HostPace(a.pace)
    log_path = os.path.join(vendor, "fetch_log.json")
    try:
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)
        if not isinstance(log, list):
            log = []
    except (OSError, ValueError):
        log = []
    failed, in_a_row = [], 0
    try:
        with tempfile.TemporaryDirectory(prefix="fetch-parts-") as empty:
            for c in todo:
                lib = os.path.join(vendor, c)
                cmd = tool + ["--lcsc_id", c, "--footprint"] + (["--3d"] if a.three_d else []) + \
                    ["--output", lib, "--overwrite"]
                def once(slot, c=c, cmd=cmd, lib=lib):
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=max(2, a.timeout), cwd=empty,
                                           stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
                    except subprocess.TimeoutExpired:
                        raise TimedOut(f"easyeda2kicad did not finish in {max(2, a.timeout):g} s for {c}") from None
                    text = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
                    ok = _has_footprint(lib + ".pretty")
                    low = text.lower()
                    mark = next((m for m in ("403", "429", "forbidden") + _REFUSAL_MARKS if m in low), None)
                    if not ok and mark:
                        log.append({"lcsc": c, "when": _stamp(), "result": f"REFUSED ({mark})"})
                        slot.refuse(f"easyeda2kicad reported '{mark}' for {c}")
                    return ok, text

                ok, text = paced_request(pace, FOOTPRINT_HOST, once)
                log.append({"lcsc": c, "when": _stamp(), "result": "fetched" if ok else "no footprint",
                            "tool_output": text[-300:] if not ok else ""})
                if ok:
                    in_a_row = 0
                    print(f"FETCHED  {c}: {', '.join(sorted(os.listdir(lib + '.pretty')))}")
                else:
                    failed.append(c)
                    in_a_row += 1
                    print(f"NO DATA  {c}: the tool wrote no footprint ({text[-160:].replace(chr(10), ' ')})")
                    if in_a_row >= 2:
                        raise CannotRun("two look-ups in a row gave nothing: stopping, the service may be refusing. "
                                        "Nothing is repeated now; wait at least 15 minutes, then one slow request; tell the user")
    finally:
        with open(log_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(log, f, indent=1)
            f.write("\n")
        print(pace.summary())
    if failed:
        print(f"FAIL: no library footprint for {', '.join(failed)}: these parts stay UNKNOWN in jlc_rotations.py "
              "(give each a written rotation after checking it in the placement preview)")
        return 1
    print(f"PASS: {len(codes)} footprint(s) in {vendor}")
    return 0


def main(argv=None) -> int:
    safe_output()
    ap = argparse.ArgumentParser(description="Fetch a datasheet by direct URL, or JLCPCB library footprints by LCSC "
                                             "number. One request at a time, paced; a refused request is never repeated.")
    sub = ap.add_subparsers(dest="cmd")
    ds = sub.add_parser("datasheet", help="one document by direct URL into a new, empty folder")
    ds.add_argument("url")
    ds.add_argument("out", help="new or empty folder for the file and its SOURCE.json")
    ds.add_argument("--name", help="file name to store (default: from the URL)")
    fp = sub.add_parser("jlc-footprint", help="JLCPCB library footprints into <vendor folder>/<number>.pretty")
    fp.add_argument("items", nargs="+", metavar="LCSC ... VENDOR_FOLDER", help="LCSC numbers, then the vendor folder")
    fp.add_argument("--3d", dest="three_d", action="store_true", help="also fetch the 3D model")
    fp.add_argument("--easyeda", metavar="CMD", help="easyeda2kicad's executable, or a Python that has the module")
    for p in (ds, fp):
        p.add_argument("--pace", type=float, default=PACE_DEFAULT,
                       help=f"seconds between requests to one host (default {PACE_DEFAULT:g}, plus a random 0 to "
                            f"100 %%; never below {PACE_MIN:g})")
        p.add_argument("--user-agent", default=USER_AGENT, help="client name sent with the request")
        p.add_argument("--timeout", type=float, default=TOOL_TIMEOUT, help=f"seconds to wait for one answer "
                                                                           f"(default {TOOL_TIMEOUT})")
        p.add_argument("--dry-run", action="store_true", help="print what would be run; no network, nothing written")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_usage(sys.stderr)
        return 2
    try:
        if a.pace < PACE_MIN:
            print(f"pace raised from {a.pace:g} s to the minimum of {PACE_MIN:g} s")
        return cmd_datasheet(a) if a.cmd == "datasheet" else cmd_footprint(a)
    except Refused as e:
        print(f"CANNOT RUN (REFUSED): {e}", file=sys.stderr)
        return 2
    except CannotRun as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
