"""Privacy scan: no user name, home-folder path or host name in any file that leaves the PC.

What it checks
    Every given file (and every file under every given folder) is searched for
      - the name of the current user (login name, display name, the home folder's name and its short 8.3 form,
        with the usual spellings of a blank: "_", ".", "%20", "+", none), and each word of a multi-word name;
      - the current home-folder path, with either kind of slash;
      - any user-folder path at all (C:\\Users\\<name>, /home/<name>, /Users/<name>): somebody else's is a leak too;
      - the host name of this machine;
      - extra patterns from the command line or from board.toml (a company name, a customer, an order number).
    It reads text files, the text headers of STEP, Gerber, drill, CSV and KiCad files, PDF metadata (plain and
    hexadecimal strings, compressed streams), the compressed text chunks of PNG images, gzip files, and the members
    of zip archives (names and contents, archives inside archives too), in UTF-8 and in UTF-16.

Why it exists
    Exporters write the operating-system user name, the host name and absolute paths into file headers, and such
    files are easily uploaded to a supplier unread. A scan of every outgoing file costs seconds. Fix the exporter
    setting, export again, scan again; do not only edit the file.

Usage
    python -I privacy_scan.py --project <hardware/board folder>
        scans the project's KiCad folder and results folder (board.toml [project] kicad_dir and out_dir, found as
        every project script finds them; default "kicad" and "out"), or the folders named in [privacy] scan, and
        writes privacy_scan.md and privacy_scan.json into the results folder. A scan folder that does not exist
        makes the scan CANNOT RUN, with its name: it is never left out silently
    python -I privacy_scan.py <file or folder> [...] [--out <folder>]
        scans the given paths; with --out it also writes privacy_scan.md and privacy_scan.json into <folder>
        (never into a KiCad design folder that is being scanned)
    options: --pattern REGEX (repeatable), --literal TEXT (repeatable), --allow REGEX (repeatable),
             --exclude GLOB (repeatable), --no-name-parts, --jobs N, --quiet
    The report never repeats what it found: the matched text is replaced by a marker such as [USER NAME], so the
    report can be shared.

board.toml keys (all optional; without a board.toml the defaults below apply and are printed)
    [project] kicad_dir, out_dir     the default scan folders and the report folder (see kicad_io.py)
    [privacy]
    scan     = ["kicad", "out"]      # folders or files, relative to the project folder (default: the KiCad folder
                                     # and the results folder of [project])
    patterns = []                    # extra regular expressions (not case-sensitive)
    literals = []                    # extra plain texts (not case-sensitive)
    allow    = []                    # regular expressions; a hit whose line matches one is listed as allowed
    exclude  = []                    # file-name patterns (fnmatch) that are not scanned; they are listed
    name_parts = true                # also search each word (4 letters or more) of a multi-word user name

Exit codes
    0  no hit in any file
    1  at least one hit (each listed with file, place and line number)
    2  the scan could not run or was incomplete: no input, a file that could not be read, a bad pattern.
       "Could not run" is never a pass.

Not checked (the report says so too): the picture content of images, text in fonts or drawings, encrypted PDF
content, archive formats other than zip and gzip.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import datetime
import fnmatch
import gzip
import io
import json
import os
import re
import socket
import sys
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MAX_MEMBER = 400 * 1024 * 1024      # bytes: a larger archive member or stream is not unpacked (listed as not checked)
MAX_DEPTH = 3                       # archives inside archives
MAX_HITS_PER_FILE = 40              # listed per file; the count is always complete
REPORT_NAMES = ("privacy_scan.md", "privacy_scan.json")
DEFAULT_SCAN = ["kicad", "out"]
PUBLIC_NAMES = ("Public", "Default", "Default User", "All Users", "Shared")
# account names that are ordinary words in design files: searched only as part of a path, never alone
GENERIC_NAMES = {"user", "users", "admin", "administrator", "root", "owner", "guest", "default", "test", "tester",
                 "dev", "developer", "build", "builder", "runner", "home", "pc", "ubuntu", "debian", "pi", "kicad",
                 "student", "lab", "work", "office", "public", "shared", "temp", "system", "local", "desktop"}


# ---------------------------------------------------------------------------------------------------------------
# what to search for
# ---------------------------------------------------------------------------------------------------------------

def _short_name(path: str) -> str | None:
    """The 8.3 form of a Windows path (tools write it into temp paths), or None."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 1024)
        return buf.value if 0 < n < 1024 else None
    except Exception:  # noqa: BLE001 - no short name is not an error
        return None


def _display_name() -> str | None:
    """The account's full name as programs write it into "author" fields, or None."""
    try:
        if os.name == "nt":
            import ctypes
            size = ctypes.c_ulong(512)
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.secur32.GetUserNameExW(3, buf, ctypes.byref(size)) and buf.value.strip():
                return buf.value.strip()
            return None
        import pwd
        gecos = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].strip()  # type: ignore[attr-defined]
        return gecos or None
    except Exception:  # noqa: BLE001
        return None


def environment_facts() -> dict:
    """User names, home folder and host name of this machine. Separate, so that a test can pass its own."""
    names: list[str] = []
    try:
        import getpass
        names.append(getpass.getuser())
    except Exception:  # noqa: BLE001
        pass
    for var in ("USERNAME", "USER", "LOGNAME"):
        if os.environ.get(var):
            names.append(os.environ[var])
    home = os.path.expanduser("~")
    homes = []
    if home and home != "~":
        homes.append(home)
        names.append(os.path.basename(home.rstrip("\\/")))
        short = _short_name(home)
        if short and short.lower() != home.lower():
            homes.append(short)
            names.append(os.path.basename(short.rstrip("\\/")))
    disp = _display_name()
    if disp:
        names.append(disp)
    hosts = []
    for h in (socket.gethostname(), os.environ.get("COMPUTERNAME"), os.environ.get("HOSTNAME")):
        if h:
            hosts.append(h.split(".")[0])
    return {"names": _unique(names), "homes": _unique(homes), "hosts": _unique(hosts)}


def _unique(items):
    seen, out = set(), []
    for i in items:
        k = i.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(i.strip())
    return out


def _name_variants(name: str) -> list[str]:
    out = [name]
    if " " in name:
        for sep in ("_", ".", "%20", "+", "-", ""):
            out.append(name.replace(" ", sep))
    return out


class Token:
    """One thing to search for: a label, a marker for the redacted report, and compiled byte patterns."""

    def __init__(self, label: str, marker: str, patterns: list[re.Pattern], shown: str):
        self.label, self.marker, self.patterns, self.shown = label, marker, patterns, shown


def _lit(text: str, word: bool = False) -> list[re.Pattern]:
    """Byte patterns for a plain text; ASCII letters match in either case.

    UTF-8 always (as a whole word when `word` is set). Text in UTF-16 is found through the copy of the data with
    its zero bytes removed (see _segments), so extra UTF-16 and Latin-1 forms are needed only for letters outside
    ASCII.
    """
    raw = re.escape(text.encode("utf-8"))
    if word:
        raw = rb"(?<![A-Za-z0-9])" + raw + rb"(?![A-Za-z0-9])"
    pats = [re.compile(raw, re.I)]
    if not text.isascii():
        for enc in ("utf-16-le", "utf-16-be", "latin-1"):
            try:
                pats.append(re.compile(re.escape(text.encode(enc)), re.I))
            except UnicodeError:
                continue
    return pats


def _mask(text: str) -> str:
    return (text[:1] + "*" * (len(text) - 1)) if text else ""


def build_tokens(facts: dict | None = None, patterns=(), literals=(), name_parts: bool = True) -> list[Token]:
    """The search list, most specific first (a later token does not report a place an earlier one covers)."""
    facts = facts or environment_facts()
    sep = rb"(?:[\\/]|%5[Cc]|%2[Ff])+"
    tokens: list[Token] = []
    for home in facts.get("homes", []):
        parts = [p for p in re.split(r"[\\/]+", home) if p]
        if len(parts) >= 2:
            body = sep.join(re.escape(p.encode("utf-8")).replace(rb"\ ", rb"(?:\ |%20|\+|_)") for p in parts)
            tokens.append(Token("home-folder path of this user", "[HOME PATH]",
                                [re.compile((sep if home.startswith(("/", "\\")) else rb"") + body, re.I)],
                                _mask(home)))
    others = "|".join(re.escape(n) for n in PUBLIC_NAMES).encode()
    tokens.append(Token("a user-folder path", "[USER FOLDER PATH]", [
        re.compile(rb"(?<![A-Za-z0-9])[A-Za-z]:" + sep + rb"(?:Users|Documents and Settings)" + sep
                   + rb"(?!(?:" + others + rb")(?:[\\/\"'\s]|$))[^\\/:*?\"<>|\r\n\x00]{1,64}", re.I),
        re.compile(rb"(?:(?<![\w.:/~\\-])|(?<=file://)|(?<=file:))/(?:home|Users)/(?!(?:" + others
                   + rb")(?:[/\"'\s]|$))[^/\s:*?\"<>|\x00]{1,64}"),
    ], "C:\\Users\\<name>, /home/<name>, /Users/<name>"))
    for name in facts.get("names", []):
        if len(name) < 3 or name.lower() in GENERIC_NAMES:
            continue                       # too short or an ordinary word: found through the path patterns only
        pats = []
        for v in _name_variants(name):
            pats += _lit(v, word=True)
        tokens.append(Token("user name", "[USER NAME]", pats, _mask(name)))
    if name_parts:
        seen = set()
        for name in facts.get("names", []):
            words = [w for w in re.split(r"[\s._-]+", name)
                     if len(w) >= 4 and not w.isdigit() and w.lower() not in GENERIC_NAMES]
            if len(words) < 2:
                continue
            for w in words:
                if w.lower() in seen:
                    continue
                seen.add(w.lower())
                tokens.append(Token("part of the user name", "[USER NAME PART]", _lit(w, word=True), _mask(w)))
    for host in facts.get("hosts", []):
        if len(host) >= 3 and host.lower() not in GENERIC_NAMES | {"localhost"}:
            tokens.append(Token("host name", "[HOST NAME]", _lit(host, word=True), _mask(host)))
    for i, text in enumerate(literals, 1):
        if text:
            tokens.append(Token(f"extra text {i}", f"[EXTRA TEXT {i}]", _lit(text), _mask(text)))
    for i, rx in enumerate(patterns, 1):
        tokens.append(Token(f"extra pattern {i}", f"[EXTRA PATTERN {i}]",
                            [re.compile(rx.encode("utf-8"), re.I)], rx))
    return tokens


# ---------------------------------------------------------------------------------------------------------------
# reading files
# ---------------------------------------------------------------------------------------------------------------

def _is_text(data: bytes) -> bool:
    return b"\x00" not in data[:8192]


def _segments(data: bytes, depth: int, notes: list[str], label: str = ""):
    """Yield (where, bytes, is_text) for the data itself and for everything packed inside it.

    Every piece that holds zero bytes is yielded a second time with them removed: that turns UTF-16 text (Windows
    files, PDF and image metadata) into plain text, whatever its byte order, and keeps its line numbers.
    """
    for where, seg, is_text in _pieces(data, depth, notes, label):
        yield where, seg, is_text
        if b"\x00" in seg:
            yield (where + " (read as UTF-16 text)").strip(), seg.replace(b"\x00", b""), seg[:2] in (b"\xff\xfe",
                                                                                                    b"\xfe\xff")


def _pieces(data: bytes, depth: int, notes: list[str], label: str):
    yield label, data, _is_text(data)
    if depth >= MAX_DEPTH:
        return
    if data[:2] == b"PK" and zipfile.is_zipfile(io.BytesIO(data)):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if z.comment:
                    yield (label + " zip comment").strip(), z.comment, True
                for info in z.infolist():
                    inner = (label + " > " if label else "member ") + info.filename
                    yield inner + " (member name)", info.filename.encode("utf-8"), True
                    if info.is_dir():
                        continue
                    if info.file_size > MAX_MEMBER:
                        notes.append(f"{inner}: larger than {MAX_MEMBER // 2**20} MB, not unpacked")
                        continue
                    try:
                        body = z.read(info)
                    except Exception as e:  # noqa: BLE001 - encrypted or damaged member
                        notes.append(f"{inner}: could not be unpacked ({type(e).__name__})")
                        continue
                    yield from _pieces(body, depth + 1, notes, inner)
        except zipfile.BadZipFile:
            notes.append((label or "file") + ": damaged zip archive, read as plain bytes only")
    elif data[:2] == b"\x1f\x8b":
        try:
            body = gzip.GzipFile(fileobj=io.BytesIO(data)).read(MAX_MEMBER + 1)
            if len(body) > MAX_MEMBER:
                notes.append((label or "file") + ": gzip content too large, not unpacked")
            else:
                yield from _pieces(body, depth + 1, notes, (label + " > gzip content").strip(" >"))
        except Exception as e:  # noqa: BLE001
            notes.append(f"{label or 'file'}: gzip content could not be unpacked ({type(e).__name__})")
    elif b"%PDF-" in data[:1024]:
        yield from _pdf_pieces(data, notes, label)
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        yield from _png_pieces(data, label)


_PDF_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.S)
_PDF_HEX = re.compile(rb"<([0-9A-Fa-f\s]{8,8192})>")
_PDF_OCTAL = re.compile(rb"\\([0-7]{1,3})")


def _pdf_strings(body: bytes, where: str):
    """The strings of a PDF part in readable form: hexadecimal strings decoded, octal escapes resolved."""
    hexes = []
    for h in _PDF_HEX.finditer(body):
        digits = re.sub(rb"\s+", b"", h.group(1))
        try:
            hexes.append(bytes.fromhex((digits + b"0" * (len(digits) % 2)).decode("ascii")))
        except ValueError:
            continue
    if hexes:
        yield where + " hexadecimal strings", b"\n".join(hexes), False
    if _PDF_OCTAL.search(body):
        yield where + " strings with escapes resolved", _PDF_OCTAL.sub(
            lambda m: bytes([int(m.group(1), 8) & 255]), body), False


def _pdf_pieces(data: bytes, notes: list[str], label: str):
    """PDF metadata hides in hexadecimal or escaped strings and in compressed streams (object streams, XMP)."""
    failed = 0
    for n, m in enumerate(_PDF_STREAM.finditer(data), 1):
        raw = m.group(1)
        if len(raw) > MAX_MEMBER:
            continue
        try:
            body = zlib.decompressobj().decompress(raw, MAX_MEMBER)
        except zlib.error:
            failed += 1
            continue
        where = (label + f" PDF stream {n}").strip()
        yield where, body, _is_text(body)
        yield from _pdf_strings(body, where)
    yield from _pdf_strings(data, (label + " PDF").strip())
    if b"/Encrypt" in data:
        notes.append((label or "PDF") + ": the PDF is encrypted, its strings were not read")
    elif failed:
        notes.append(f"{label or 'PDF'}: {failed} stream(s) are not deflate-compressed (images, fonts); "
                     "read as plain bytes only")


def _png_pieces(data: bytes, label: str):
    pos = 8
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        try:
            if kind == b"zTXt" and b"\x00" in body:
                key, rest = body.split(b"\x00", 1)
                yield (label + " PNG text " + key.decode("latin-1")).strip(), zlib.decompress(rest[1:]), True
            elif kind == b"iTXt" and body.count(b"\x00") >= 4:
                key, rest = body.split(b"\x00", 1)
                if rest[:1] == b"\x01":
                    text = rest[2:].split(b"\x00", 2)[2]
                    yield (label + " PNG text " + key.decode("latin-1")).strip(), zlib.decompress(text), True
        except (zlib.error, IndexError):
            continue
        if kind == b"IEND":
            break


def _excerpt(seg: bytes, start: int, end: int, tokens: list[Token], is_text: bool) -> str:
    """The line around a hit with every searched text replaced by its marker (the report must stay clean)."""
    if is_text:
        a = seg.rfind(b"\n", 0, start) + 1
        b = seg.find(b"\n", end)
        b = len(seg) if b < 0 else b
        a, b = max(a, start - 100), min(b, end + 100)
    else:
        a, b = max(0, start - 40), min(len(seg), end + 40)
    piece = seg[a:b]
    for t in tokens:
        for p in t.patterns:
            piece = p.sub(t.marker.encode("ascii"), piece)
    text = piece.decode("utf-8", errors="replace")
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()[:240]


def scan_bytes(data: bytes, tokens: list[Token], allow: list[re.Pattern], notes: list[str]) -> tuple[list, int, int]:
    """Search one file's bytes. Returns (hits, total count, allowed count)."""
    hits: list[dict] = []
    total, allowed = 0, 0
    for where, seg, is_text in _segments(data, 0, notes):
        covered: list[tuple[int, int]] = []
        for t in tokens:
            for p in t.patterns:
                for m in p.finditer(seg):
                    s, e = m.span()
                    if any(s < ce and e > cs for cs, ce in covered):
                        continue
                    covered.append((s, e))
                    if allow:
                        a = seg.rfind(b"\n", 0, s) + 1
                        b = seg.find(b"\n", e)
                        line = seg[a:len(seg) if b < 0 else b]
                        if any(x.search(line) for x in allow):
                            allowed += 1
                            continue
                    total += 1
                    if len(hits) < MAX_HITS_PER_FILE:
                        hits.append({
                            "where": where,
                            "line": (seg.count(b"\n", 0, s) + 1) if is_text else None,
                            "offset": s,
                            "what": t.label,
                            "text": _excerpt(seg, s, e, tokens, is_text),
                        })
    hits.sort(key=lambda h: (h["where"], h["offset"]))
    return hits, total, allowed


def _scan_one(args):
    """Worker: one file. Module-level so that a process pool can call it."""
    path, rel, spec, allow_rx = args
    tokens = build_tokens(spec["facts"], spec["patterns"], spec["literals"], spec["name_parts"])
    allow = [re.compile(a.encode("utf-8"), re.I) for a in allow_rx]
    notes: list[str] = []
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return {"file": rel, "error": f"could not be read: {e.__class__.__name__}", "hits": [], "count": 0,
                "allowed": 0, "notes": [], "bytes": 0}
    hits, total, allowed = scan_bytes(data, tokens, allow, notes)
    name_hits, name_total, _ = scan_bytes(rel.replace("\\", "/").encode("utf-8"), tokens, allow, [])
    for h in name_hits:
        h.update(where="file name", line=None)
    return {"file": rel, "error": None, "hits": name_hits + hits, "count": total + name_total, "allowed": allowed,
            "notes": notes, "bytes": len(data)}


def collect(paths: list[str], exclude: list[str]) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """(absolute path, shown path) of every file, the excluded ones, and the inputs that do not exist."""
    files, skipped, missing = [], [], []
    for p in paths:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            cand = [(p, os.path.basename(p))]
        elif os.path.isdir(p):
            base = os.path.basename(p.rstrip("\\/")) or p
            cand = []
            for root, dirs, names in os.walk(p):
                dirs.sort()
                for n in sorted(names):
                    full = os.path.join(root, n)
                    cand.append((full, os.path.join(base, os.path.relpath(full, p)).replace("\\", "/")))
        else:
            missing.append(p)
            continue
        for full, rel in cand:
            name = os.path.basename(full)
            if name in REPORT_NAMES or any(fnmatch.fnmatch(name, g) or fnmatch.fnmatch(rel, g) for g in exclude):
                skipped.append(rel)
            else:
                files.append((full, rel))
    seen, out = set(), []
    for full, rel in files:
        if full not in seen:
            seen.add(full)
            out.append((full, rel))
    return out, skipped, missing


def scan_paths(paths: list[str], patterns=(), literals=(), allow=(), exclude=(), name_parts: bool = True,
               jobs: int | None = None, facts: dict | None = None) -> dict:
    """Scan files and folders. Returns the result dictionary (also what the JSON report holds)."""
    facts = facts or environment_facts()
    tokens = build_tokens(facts, patterns, literals, name_parts)        # also proves the patterns compile
    for a in allow:
        re.compile(a)
    files, skipped, missing = collect(paths, list(exclude))
    spec = {"facts": facts, "patterns": list(patterns), "literals": list(literals), "name_parts": name_parts}
    work = [(full, rel, spec, list(allow)) for full, rel in files]
    size = sum(os.path.getsize(f) for f, _ in files if os.path.exists(f))
    jobs = jobs or min(os.cpu_count() or 1, len(work))
    if jobs > 1 and len(work) >= 8 and size > 4 * 2**20:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_scan_one, work, chunksize=max(1, len(work) // (jobs * 4))))
    else:
        results = [_scan_one(w) for w in work]
    results.sort(key=lambda r: r["file"])
    hit_files = [r for r in results if r["count"]]
    unread = [r for r in results if r["error"]]
    notes = [f"{r['file']}: {n}" for r in results for n in r["notes"]]
    if not files:
        verdict = "CANNOT RUN"
    elif hit_files:
        verdict = "FAIL"
    elif unread or missing:
        verdict = "CANNOT RUN"
    else:
        verdict = "PASS"
    return {
        "check": "privacy_scan",
        "result": verdict,
        "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "files_scanned": len(results) - len(unread),
        "bytes_scanned": sum(r["bytes"] for r in results),
        "files_with_hits": len(hit_files),
        "hits": sum(r["count"] for r in results),
        "allowed": sum(r["allowed"] for r in results),
        "searched_for": [{"what": t.label, "shown": t.shown} for t in tokens],
        "files": [{"file": r["file"], "hits": r["count"], "listed": r["hits"]} for r in hit_files],
        "unreadable": [{"file": r["file"], "why": r["error"]} for r in unread],
        "missing_inputs": [os.path.basename(m) for m in missing],
        "excluded": skipped,
        "not_checked": ["picture content of images", "text drawn as graphics or held in fonts",
                        "archive formats other than zip and gzip"] + notes,
    }


# ---------------------------------------------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------------------------------------------

def markdown(res: dict) -> str:
    out = ["# Privacy scan", "",
           f"**Result: {res['result']}** - {res['hits']} hit(s) in {res['files_with_hits']} of "
           f"{res['files_scanned']} file(s), {res['bytes_scanned']:,} bytes, {res['date']}.", ""]
    if res["result"] == "CANNOT RUN":
        why = []
        if not res["files_scanned"]:
            why.append("no file to scan")
        if res["unreadable"]:
            why.append(f"{len(res['unreadable'])} file(s) could not be read")
        if res["missing_inputs"]:
            why.append("input not found: " + ", ".join(res["missing_inputs"]))
        out += ["The scan is incomplete: " + "; ".join(why) + ". This is not a pass.", ""]
    elif res["missing_inputs"]:
        out += ["Input not found, so not scanned: " + ", ".join(res["missing_inputs"]) + ". Without the hits this "
                "scan would still not be a pass.", ""]
    out += ["Searched for (shown masked, so that this report can be shared):", ""]
    counts: dict[str, int] = {}
    for s in res["searched_for"]:
        counts[s["what"]] = counts.get(s["what"], 0) + 1
    shown = set()
    for s in res["searched_for"]:
        if s["what"] in shown and s["what"].startswith(("user name", "part of", "host", "home")):
            continue
        shown.add(s["what"])
        n = counts[s["what"]]
        out.append(f"- {s['what']}: `{s['shown']}`" + (f" and {n - 1} more spelling(s) or name(s)" if n > 1 and
                                                       s["what"].startswith(("user name", "part of", "host", "home"))
                                                       else ""))
    out.append("")
    if res["files"]:
        out += ["## Hits", "", "| File | Where | Line | What | Text (the find is replaced by a marker) |",
                "|---|---|---|---|---|"]
        for f in res["files"]:
            for h in f["listed"]:
                line = str(h["line"]) if h["line"] is not None else f"byte {h['offset']}"
                text = h["text"].replace("|", "\\|")
                out.append(f"| {f['file']} | {h['where'] or 'content'} | {line} | {h['what']} | `{text}` |")
            if f["hits"] > len(f["listed"]):
                out.append(f"| {f['file']} | | | | ... and {f['hits'] - len(f['listed'])} more hit(s) |")
        out.append("")
    if res["allowed"]:
        out += [f"Allowed by an `allow` pattern (not counted as hits): {res['allowed']}.", ""]
    if res["unreadable"]:
        out += ["## Files that could not be read", ""] + [f"- {u['file']}: {u['why']}" for u in res["unreadable"]] + [""]
    if res["excluded"]:
        out += ["## Not scanned (excluded)", ""] + [f"- {e}" for e in res["excluded"]] + [""]
    out += ["## Not checked", ""] + [f"- {n}" for n in res["not_checked"]] + [""]
    return "\n".join(out)


def write_report(res: dict, out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    md, js = os.path.join(out_dir, REPORT_NAMES[0]), os.path.join(out_dir, REPORT_NAMES[1])
    for path, text in ((md, markdown(res)), (js, json.dumps(res, indent=1, ensure_ascii=False) + "\n")):
        tmp = path + f".tmp{os.getpid()}"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    return md, js


def exit_code(res: dict) -> int:
    return {"PASS": 0, "FAIL": 1}.get(res["result"], 2)


def _in_design_folder(out_dir: str, paths: list[str]) -> bool:
    """True when out_dir is a scanned folder (or lies in one) that holds a KiCad design: never write there."""
    out = os.path.normcase(os.path.abspath(out_dir))
    for p in paths:
        root = os.path.normcase(os.path.abspath(p))
        if not os.path.isdir(root) or not (out + os.sep).startswith(root + os.sep):
            continue
        d = out
        while True:
            if os.path.isdir(d) and any(n.lower().endswith((".kicad_pcb", ".kicad_sch", ".kicad_pro"))
                                        for n in os.listdir(d)):
                return True
            if d == root or os.path.dirname(d) == d:
                break
            d = os.path.dirname(d)
    return False


def _settings(project: str | None) -> tuple[dict, dict, str]:
    """board.toml, its [privacy] table, and a note saying where the settings came from."""
    if not project:
        return {}, {}, "no project folder: defaults"
    path = os.path.join(project, "board.toml")
    if not os.path.isfile(path):
        return {}, {}, "no board.toml in the project folder: defaults"
    import tomllib
    with open(path, "rb") as f:
        toml = tomllib.load(f)
    return toml, toml.get("privacy", {}), "settings from board.toml"


def _project_folders(project: str, toml: dict) -> tuple[str, str]:
    """The KiCad folder and the results folder of a board folder, as every project script finds them
    (kicad_io.project_files: board.toml [project] kicad_dir and out_dir)."""
    import kicad_io
    try:
        files = kicad_io.project_files(project, toml)
        return files["kicad_dir"], files["out"]
    except kicad_io.KicadIOError:          # no single KiCad project there: the folders as board.toml names them
        cfg = toml.get("project", {})
        return (os.path.join(project, cfg.get("kicad_dir", DEFAULT_SCAN[0])),
                os.path.join(project, cfg.get("out_dir", DEFAULT_SCAN[1])))


def _shown(path: str, project: str) -> str:
    try:
        return os.path.relpath(path, project).replace("\\", "/")
    except ValueError:                     # another drive
        return os.path.basename(path)


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
    ap = argparse.ArgumentParser(description="Search files for the user name, home-folder paths, the host name "
                                             "and extra patterns. Exit 0 clean, 1 on a hit, 2 when it could not run.")
    ap.add_argument("paths", nargs="*", help="files or folders to scan")
    ap.add_argument("--project", help="hardware/board folder: scans its KiCad folder and results folder (or the "
                                      "folders of board.toml [privacy] scan), writes privacy_scan.md into the "
                                      "results folder")
    ap.add_argument("--out", help="folder for privacy_scan.md and privacy_scan.json")
    ap.add_argument("--pattern", action="append", default=[], help="extra regular expression (repeatable)")
    ap.add_argument("--literal", action="append", default=[], help="extra plain text (repeatable)")
    ap.add_argument("--allow", action="append", default=[], help="regular expression: a hit on a matching line "
                                                                "is listed as allowed, not counted")
    ap.add_argument("--exclude", action="append", default=[], help="file-name pattern not to scan (repeatable)")
    ap.add_argument("--no-name-parts", action="store_true", help="do not search single words of the user name")
    ap.add_argument("--jobs", type=int, help="worker processes (default: all cores when the work is large)")
    ap.add_argument("--quiet", action="store_true", help="print only the result line")
    a = ap.parse_args(argv)

    if not a.project and not a.paths:
        print("CANNOT RUN: give files or folders to scan, or --project <board folder>", file=sys.stderr)
        return 2
    try:
        toml, cfg, note = _settings(a.project)
    except Exception as e:  # noqa: BLE001 - unreadable settings file
        print(f"CANNOT RUN: board.toml could not be read: {e}", file=sys.stderr)
        return 2
    paths, out_dir = list(a.paths), a.out
    if a.project:
        kicad_dir, results = _project_folders(a.project, toml)
        out_dir = out_dir or results
        if not paths:                      # every folder is scanned; one that does not exist makes it CANNOT RUN
            paths = [os.path.join(a.project, p) for p in cfg["scan"]] if cfg.get("scan") else [kicad_dir, results]
            note += "; scanned: " + ", ".join(_shown(p, a.project) for p in paths)
    if a.out and _in_design_folder(out_dir, paths):
        print("CANNOT RUN: the report folder lies inside the KiCad design that is scanned; choose another folder "
              "with --out (a design that is only read is never written into)", file=sys.stderr)
        return 2
    try:
        res = scan_paths(paths, patterns=a.pattern + list(cfg.get("patterns", [])),
                         literals=a.literal + list(cfg.get("literals", [])),
                         allow=a.allow + list(cfg.get("allow", [])),
                         exclude=a.exclude + list(cfg.get("exclude", [])),
                         name_parts=not a.no_name_parts and bool(cfg.get("name_parts", True)), jobs=a.jobs)
    except re.error as e:
        print(f"CANNOT RUN: bad pattern: {e}", file=sys.stderr)
        return 2
    res["settings"] = note
    md = write_report(res, out_dir)[0] if out_dir else None
    if not a.quiet:
        print(note)
        for f in res["files"]:
            for h in f["listed"]:
                line = f"line {h['line']}" if h["line"] is not None else f"byte {h['offset']}"
                where = f" [{h['where']}]" if h["where"] else ""
                print(f"HIT  {f['file']}{where} {line}: {h['what']}: {h['text']}")
        for u in res["unreadable"]:
            print(f"CANNOT READ  {u['file']}: {u['why']}")
        for m in res["missing_inputs"]:
            print(f"NOT FOUND  {m}")
    print(f"privacy scan: {res['result']} - {res['hits']} hit(s) in {res['files_with_hits']} of "
          f"{res['files_scanned']} file(s)" + (f"; report {md}" if md else "; no report written (no --out)"))
    return exit_code(res)


if __name__ == "__main__":
    sys.exit(main())
