"""Privacy scan: no personal data in any file that leaves the PC (upload folders) or in the skill folder.

What it does
    Scans every given file and every file under every given folder for: user-profile paths (C:\\Users\\<name>,
    /home/<name>, /Users/<name>), the name of the current user and the host name of this machine, e-mail addresses,
    phone numbers (a leading + and 8 or more digits, or the usual grouped forms, in text), the author and
    organisation values in a STEP header (FILE_NAME), the author fields of PDF, PNG and DXF metadata, and every line of
    an optional user-supplied deny list (words, one per line, or `re:` patterns). It reads text files, STEP headers,
    PDF metadata (PyMuPDF when present), PNG text chunks, DXF header variables, zip members (3MF, archives) and, for
    other binary files, their printable strings. The report never repeats what it found: the text is replaced by a
    marker such as [E-MAIL], so the report can be shared.
    Exit 1 on any hit.

Why it exists (the real failure, told without names)
    Exporters write the operating-system user name, the host name and absolute paths into file headers. Such files
    are easily uploaded to a supplier unread: nobody opens them as text. A scan of every outgoing file costs seconds.

Usage
    python -I privacy_scan.py <file or folder> [...] [--deny deny.txt] [--allow REGEX] [--out DIR] [--no-current-user]
    python -I privacy_scan.py --project <mech folder>      scans <project>/out/upload (default) and [privacy] scan
    options: --exclude GLOB (repeatable), --jobs N, --quiet

Config keys (mech.toml)
    [privacy] scan = ["out/upload"], deny_file = "deny.txt", allow = ["noreply@"], exclude = ["*.png.meta"]
    [project] company = "..."   (the only organisation name allowed in a STEP header)

Exit codes
    0 no hit   1 at least one hit   2 could not run (no input, unreadable path)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import fnmatch
import getpass
import io
import os
import re
import socket
import struct
import zipfile
import zlib
from concurrent.futures import ProcessPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

SYSTEM_USERS = {"public", "default", "all users", "default user", "defaultuser0", "shared", "guest", "user", "username", "name",
                "<user>", "%username%", "yourname", "you", "me", "runner", "root", "$user"}
RX_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]+users[\\/]+|/home/|/users/)([a-z0-9_][^\\/\s'\"<>:|*?()]{1,})")
RX_MAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
RX_PHONE = re.compile(r"(?<![\w.])(?:\+\d{1,3}[\s.-]?(?:\(?\d{1,4}\)?[\s.-]?){2,5}\d{2,4}|\(\d{2,4}\)[\s.-]?\d{3,4}[\s.-]?\d{3,4})(?![\w.])")
RX_STEP_NAME = re.compile(r"FILE_NAME\s*\((.*?)\)\s*;", re.S)
TEXT_EXT = {".txt", ".md", ".json", ".toml", ".csv", ".html", ".htm", ".xml", ".svg", ".py", ".yaml", ".yml", ".cfg", ".ini", ".dxf",
            ".step", ".stp", ".gcode", ".obj", ".mtl", ".tsv", ".log", ".rst", ".bat", ".ps1", ".sh", ".kicad_pcb", ".net", ".scad"}
MAX_TEXT = 40_000_000


def _marker(kind):
    return f"[{kind}]"


def _names():
    names = set()
    try:
        u = getpass.getuser()
        names.add(u)
    except Exception:
        pass
    home = os.path.basename(os.path.expanduser("~"))
    if home:
        names.add(home)
    for n in list(names):
        for sep in (" ", "_", ".", "-"):
            names.update(p for p in n.split(sep) if len(p) >= 5 and sep in n)
        if " " in n:
            names.add(n.replace(" ", "")); names.add(n.replace(" ", "_")); names.add(n.replace(" ", "%20"))
    host = socket.gethostname()
    return {n for n in names if len(n) >= 3}, host


class Scanner:
    def __init__(self, deny=(), allow=(), current_user=True, company=""):
        self.company = company.strip().lower()
        self.names, self.host = _names() if current_user else (set(), "")
        self.deny_lit = [d.lower() for d in deny if not d.startswith("re:")]
        self.deny_rx = [re.compile(d[3:], re.I) for d in deny if d.startswith("re:")]
        self.allow = [re.compile(x, re.I) for x in allow]
        self.rx_names = re.compile("|".join(re.escape(n) for n in sorted(self.names, key=len, reverse=True)), re.I) if self.names else None
        self.rx_host = re.compile(r"(?<![A-Za-z0-9])" + re.escape(self.host) + r"(?![A-Za-z0-9])", re.I) if len(self.host) >= 4 else None

    def _allowed(self, line):
        return any(r.search(line) for r in self.allow)

    def scan_text(self, text, where=""):
        """-> list of (kind, line number). Matched text is never returned."""
        hits = []
        for n, line in enumerate(text.splitlines(), 1):
            if self._allowed(line):
                continue
            for m in RX_PATH.finditer(line):
                if m.group(1).lower() not in SYSTEM_USERS:
                    hits.append(("USER-FOLDER PATH", n))
            if self.rx_names and self.rx_names.search(line):
                hits.append(("USER NAME", n))
            if self.rx_host and self.rx_host.search(line):
                hits.append(("HOST NAME", n))
            if RX_MAIL.search(line):
                hits.append(("E-MAIL", n))
            if RX_PHONE.search(line):
                hits.append(("PHONE NUMBER", n))
            low = line.lower()
            if any(d in low for d in self.deny_lit) or any(r.search(line) for r in self.deny_rx):
                hits.append(("DENY-LIST WORD", n))
        return hits

    # ---- formats ------------------------------------------------------------------------------------------------
    def step_header(self, text):
        hits = []
        head = text.split("ENDSEC;", 1)[0]
        m = RX_STEP_NAME.search(head)
        if m:
            fields = re.findall(r"\(([^()]*)\)", m.group(1))     # author list, then organisation list
            for k, f in enumerate(fields[:2]):
                val = f.replace("'", "").strip()
                if re.search(r"[A-Za-z0-9]", val) and not (k == 1 and self.company and val.lower() == self.company):
                    hits.append(("STEP HEADER AUTHOR" if k == 0 else "STEP HEADER ORGANIZATION", 0))
        for n, line in enumerate(head.splitlines(), 1):
            if re.search(r"PERSON|ORGANI[ZS]ATION", line, re.I) and re.search(r"'[^']*[A-Za-z0-9][^']*'", line):
                if not (self.company and self.company in line.lower()):
                    hits.append(("STEP HEADER PERSON/ORGANIZATION", n))
        return hits

    def png(self, data):
        hits = []
        pos = 8
        while pos + 8 <= len(data):
            ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
            body = data[pos + 8:pos + 8 + ln]
            pos += 12 + ln
            txt = None
            if typ == b"tEXt":
                txt = body.decode("latin-1", "replace")
            elif typ == b"zTXt":
                try:
                    k, rest = body.split(b"\0", 1)
                    txt = k.decode("latin-1") + "\0" + zlib.decompress(rest[1:]).decode("utf-8", "replace")
                except Exception:
                    pass
            elif typ == b"iTXt":
                try:
                    k, rest = body.split(b"\0", 1)
                    flag, _m = rest[0], rest[1]
                    rest = rest[2:]
                    _l, rest = rest.split(b"\0", 1)
                    _t, rest = rest.split(b"\0", 1)
                    txt = k.decode("latin-1") + "\0" + (zlib.decompress(rest) if flag else rest).decode("utf-8", "replace")
                except Exception:
                    pass
            if txt:
                key = txt.split("\0", 1)[0].lower()
                if key in ("author", "artist", "copyright", "creator", "owner") and txt.split("\0", 1)[-1].strip():
                    hits.append(("PNG METADATA AUTHOR", 0))
                hits += [(k, 0) for k, _n in self.scan_text(txt.replace("\0", " "))]
            if typ == b"IEND":
                break
        return hits

    def pdf(self, path, data):
        hits = []
        try:
            import pymupdf as fitz
            doc = fitz.open(stream=data, filetype="pdf")
            md = doc.metadata or {}
            for k in ("author", "creator", "producer", "title", "subject", "keywords"):
                v = (md.get(k) or "").strip()
                if not v:
                    continue
                if k == "author":
                    hits.append(("PDF METADATA AUTHOR", 0))
                else:
                    hits += [(h, 0) for h, _n in self.scan_text(v)]
            for pg in doc:
                hits += [(h, 0) for h, _n in self.scan_text(pg.get_text())]
            doc.close()
        except ImportError:
            hits.append(("PDF NOT READ (PyMuPDF missing): metadata not checked", 0))
        except Exception as e:
            hits.append((f"PDF UNREADABLE ({type(e).__name__})", 0))
        # raw strings too: Info dictionaries not compressed
        txt = data.decode("latin-1", "replace")
        for m in re.finditer(r"/Author\s*\(([^)]*)\)", txt):
            if m.group(1).strip():
                hits.append(("PDF METADATA AUTHOR", 0))
        return hits

    def dxf(self, text):
        hits = []
        lines = text.splitlines()
        for i, ln in enumerate(lines[:-1]):
            if ln.strip() in ("$LASTSAVEDBY", "$AUTHOR", "$LASTSAVEDBY ") and i + 2 < len(lines) and lines[i + 2].strip():
                hits.append(("DXF HEADER AUTHOR", i + 3))
        return hits

    def scan_bytes(self, name, data, depth=0):
        ext = os.path.splitext(name)[1].lower()
        hits = []
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            hits += self.png(data)
        elif data[:5] == b"%PDF-":
            hits += self.pdf(name, data)
        elif data[:2] == b"PK" and depth < 2:
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
                for zi in z.infolist():
                    if zi.is_dir() or zi.file_size > MAX_TEXT:
                        continue
                    hits += [(f"{k} (in {zi.filename})", n) for k, n in self.scan_bytes(zi.filename, z.read(zi), depth + 1)]
                    hits += [("USER NAME (in a member name)", 0)] if self.rx_names and self.rx_names.search(zi.filename) else []
            except zipfile.BadZipFile:
                hits.append(("ZIP UNREADABLE", 0))
            return hits
        if ext in (".png", ".pdf", ".zip", ".3mf"):
            pass
        if data[:2] == b"\xff\xfe" or data[:2] == b"\xfe\xff":
            text = data.decode("utf-16", "replace")
        elif ext in TEXT_EXT or b"\0" not in data[:4096]:
            text = data[:MAX_TEXT].decode("utf-8", "replace")
        else:                                              # binary: its printable strings
            text = "\n".join(m.group().decode("latin-1") for m in re.finditer(rb"[\x20-\x7e]{6,}", data[:MAX_TEXT]))
        if ext in (".step", ".stp") or text.startswith("ISO-10303"):
            hits += self.step_header(text)
        if ext == ".dxf":
            hits += self.dxf(text)
        hits += self.scan_text(text)
        return hits


def _scan_file(args):
    path, deny, allow, cur, company = args
    sc = Scanner(deny, allow, cur, company)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return path, None, str(e)
    hits = sc.scan_bytes(path, data)
    nm = sc.rx_names.search(os.path.basename(path)) if sc.rx_names else None
    if nm:
        hits.append(("USER NAME (in the file name)", 0))
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return path, out, ""


SHOWN = {}          # file path -> the name shown in the report: relative to the scanned folder, never an absolute path


def collect_files(paths, excludes=()):
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
            SHOWN[p] = os.path.basename(p)
        elif os.path.isdir(p):
            for r, ds, fs in os.walk(p):
                ds[:] = [d for d in ds if d not in (".git", "__pycache__")]
                for f in fs:
                    full = os.path.join(r, f)
                    files.append(full)
                    SHOWN[full] = os.path.relpath(full, p).replace("\\", "/")
        else:
            raise mc.MechError(f"not a file or folder: {p}")
    return sorted(f for f in files if not any(fnmatch.fnmatch(os.path.basename(f), x) for x in excludes))


def scan(paths, deny=(), allow=(), excludes=(), current_user=True, jobs=None, company=""):
    files = collect_files(paths, excludes)
    tasks = [(f, list(deny), list(allow), current_user, company) for f in files]
    n = min(jobs or mc.workers(), max(len(tasks), 1))
    if n > 1 and len(tasks) > 8:
        with ProcessPoolExecutor(n) as ex:
            res = list(ex.map(_scan_file, tasks, chunksize=4))
    else:
        res = [_scan_file(t) for t in tasks]
    return files, res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scan files for personal data before they leave the PC.", epilog="Exit: 0 clean, 1 hit, 2 could not run.")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--project")
    ap.add_argument("--out")
    ap.add_argument("--deny", help="file with one word per line (or re:PATTERN) that must not appear")
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--company", default="", help="the organisation name that may stand in a STEP header (default: [project] company)")
    ap.add_argument("--no-current-user", action="store_true")
    ap.add_argument("--jobs", type=int)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    paths, deny, allow, excl, out = list(a.paths), [], list(a.allow), list(a.exclude), a.out
    try:
        if a.project or not paths:
            job = mc.resolve(a)
            pc = job.cfg.get("privacy", {})
            if not paths:
                paths = [mc.rel_to_project(job.cfg, p) for p in pc.get("scan", ["out/upload"])]
            allow += pc.get("allow", [])
            excl += pc.get("exclude", [])
            if pc.get("deny_file") and not a.deny:
                a.deny = mc.rel_to_project(job.cfg, pc["deny_file"])
            out = out or job.out
            a.company = a.company or job.cfg.get("project", {}).get("company", "")
        if a.deny:
            with open(a.deny, encoding="utf-8") as f:
                deny = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        files, res = scan(paths, deny, allow, excl, not a.no_current_user, a.jobs, a.company)
    except (mc.MechError, OSError) as e:
        print("could not run:", e)
        return 2
    rows = mc.Rows()
    unread = [(p, e) for p, h, e in res if h is None]
    n = 0
    for p, h, e in res:
        if h is None:
            continue
        for kind, line in h:
            n += 1
            rows.add(f"PRV-{n:03d}", "privacy", SHOWN.get(p, os.path.basename(p)),
                     f"{_marker(kind)}" + (f" at line {line}" if line else ""), "no personal data in files that leave the PC", "fail")
    for p, e in unread:
        rows.add(f"PRV-U{len(rows.rows)}", "privacy", p, f"could not be read: {e}", "every file is read", "could_not_run")
    if not files:
        rows.add("PRV-000", "privacy", "files to scan", "none found in " + ", ".join(paths), "at least one file", "could_not_run")
    elif not rows.rows:
        rows.add("PRV-000", "privacy", f"{len(files)} file(s) scanned", "no hit", "no personal data", "pass")
    if not a.quiet:
        rows.print_table(only_bad=True)
    if out:
        rows.write(out, "privacy_scan.py", [])
    print(rows.headline() + f"  ({len(files)} files)")
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
