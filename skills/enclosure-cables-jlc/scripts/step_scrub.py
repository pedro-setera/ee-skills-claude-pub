"""STEP header scrub: no personal name, user name, host name or path in the header of a STEP that leaves the PC.

What it does
    Reads the text header of each STEP file and the person / organisation entities of its data section, and
      - reports what it found: FILE_NAME (name, author, organization, preprocessor, originating system,
        authorization), FILE_DESCRIPTION, every PERSON and ORGANIZATION entity; and anywhere in the file: the
        current user's login name, the home-folder name, the host name; and any path in the header
        (a drive letter path, a network share, /home/..., /Users/...);
      - rewrites (default): author, organization and authorization become the company from mech.toml
        ([project] company) or empty; the originating system becomes empty; the file name loses its folder; the
        PERSON and ORGANIZATION entities get the company (entity numbers and all geometry stay byte for byte);
        the cleaned copy goes to <out>/step_clean/<name> (or over the file with --in-place);
      - --check only reports, and exits 1 when a personal-looking value or a path is present.
    "Personal-looking": an author, organization, authorization, originating system, PERSON or ORGANIZATION text
    that is not empty and is not the configured company (or one of --allow); a user, home-folder or host name; a
    path. A kernel's own placeholders ("Author", "Unknown", its product name) are not personal. The report shows
    header values as they are; a user or host name found elsewhere is shown as a marker,
    not repeated.

Why it exists (the real failure, told without names)
    A CAD kernel writes the operating-system user name and the host name into every STEP it exports (author,
    organization, PERSON). Such files are easily uploaded to a supplier unread, and an uploaded file cannot be
    called back.

Usage
    python -I step_scrub.py <file.step|folder> [...] [--check] [--in-place] [--company TEXT] [--allow TEXT ...]
                            [--keep-system] [--project <mech folder>] [--out <folder>]
        --check        report only; exit 1 if something personal-looking or a path is present
        --in-place     rewrite the given files themselves (default: copies in <out>/step_clean/)
        --company      overrides [project] company ("" = empty fields)
        --allow        a text that may stay (repeatable), e.g. a kernel name in the originating-system field
        --keep-system  leave the originating-system field as it is (it is still checked)
    Folders are searched for *.step and *.stp (not below the output folder).

Config keys (mech.toml)
    [project] company = ""          [scrub] allow = [ "text", ... ]

Exit codes
    0 nothing personal-looking found (after the rewrite, when rewriting)     1 --check found something, or a value
    survived the rewrite     2 could not run (no file given, a file is not a STEP file or cannot be read)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import getpass
import os
import re
import socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mech_common as mc  # noqa: E402

PATH_RE = re.compile(r"(?i)(?:\b[a-z]:[\\/]{1,2}[^'\s;]+|\\\\[^'\s;\\]+\\[^'\s;]+|/(?:home|Users|mnt|media|root)/[^'\s;]+)")
STR_RE = re.compile(r"'((?:[^']|'')*)'")
ENT_RE = re.compile(rb"(#\d+\s*=\s*)(PERSON|ORGANIZATION)(\s*\()((?:[^;']|'(?:[^']|'')*')*)(\)\s*;)")
QUOTE = "'"
# placeholders a CAD kernel writes when it knows nothing: not personal (they are still replaced by the rewrite)
NEUTRAL = re.compile(r"(?i)^(author|unknown|none|n/?a|-|open ?cascade(\s+[\w.]+)*)$")


def split_args(body):
    """The top-level arguments of an entity body (the text between its outer brackets)."""
    out, depth, cur, in_s, i = [], 0, "", False, 0
    while i < len(body):
        c = body[i]
        if in_s:
            cur += c
            if c == QUOTE:
                if i + 1 < len(body) and body[i + 1] == QUOTE:
                    cur += QUOTE
                    i += 1
                else:
                    in_s = False
        elif c == QUOTE:
            in_s = True
            cur += c
        elif c == "(":
            depth += 1
            cur += c
        elif c == ")":
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    if cur.strip() or out:
        out.append(cur.strip())
    return out


def strings_of(arg):
    return [m.replace(QUOTE * 2, QUOTE) for m in STR_RE.findall(arg)]


def q(s):
    return QUOTE + s.replace(QUOTE, QUOTE * 2) + QUOTE


def header_span(text, name):
    """(start, end, body) of NAME( ... ); in the header, string-aware."""
    m = re.search(r"\b" + name + r"\s*\(", text)
    if not m:
        return None
    i, depth, in_s = m.end(), 1, False
    while i < len(text) and depth:
        c = text[i]
        if in_s:
            if c == QUOTE:
                if i + 1 < len(text) and text[i + 1] == QUOTE:
                    i += 1
                else:
                    in_s = False
        elif c == QUOTE:
            in_s = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    semi = text.find(";", i - 1)
    return m.start(), (semi + 1 if semi >= 0 else i), text[m.end():i - 1]


def identity():
    """[(marker, text)] of this machine's user, home-folder and host names (3 letters or more)."""
    out = []
    try:
        out.append(("[USER NAME]", getpass.getuser()))
    except Exception:
        pass
    out.append(("[HOME FOLDER NAME]", os.path.basename(os.path.expanduser("~").rstrip("\\/"))))
    out.append(("[HOST NAME]", socket.gethostname()))
    for k in ("USERNAME", "USER", "COMPUTERNAME"):
        if os.environ.get(k):
            out.append(("[USER NAME]" if "USER" in k else "[HOST NAME]", os.environ[k]))
    seen, res = set(), []
    for mk, v in out:
        v = (v or "").strip()
        if len(v) >= 3 and v.lower() not in seen:
            seen.add(v.lower())
            res.append((mk, v))
    return res


def inspect(data, company, allow):
    """{"fields": [(where, value, personal?)], "hits": [(marker, count)], "paths": [...]} of a STEP file's bytes."""
    text = data.decode("latin-1")
    end = text.find("ENDSEC;")
    if not text.lstrip().startswith("ISO-10303-21") or end < 0:
        raise mc.MechError("not a STEP file (no ISO-10303-21 header)")
    head = text[:end]
    ok_vals = {v.lower() for v in ([company] if company else []) + list(allow)}

    def personal(v):
        v = v.strip()
        return bool(v) and v.lower() not in ok_vals and not NEUTRAL.match(v)

    fields = []
    fn = header_span(head, "FILE_NAME")
    if fn:
        a = split_args(fn[2])
        names = ["name", "time stamp", "author", "organization", "preprocessor version", "originating system",
                 "authorization"]
        for k, nm in enumerate(names):
            if k >= len(a):
                break
            for v in strings_of(a[k]) or [""]:
                if nm in ("author", "organization", "authorization", "originating system"):
                    fields.append((f"FILE_NAME {nm}", v, personal(v)))
                elif nm == "name":
                    fields.append((f"FILE_NAME {nm}", v, "/" in v or "\\" in v))
                else:
                    fields.append((f"FILE_NAME {nm}", v, False))
    fd = header_span(head, "FILE_DESCRIPTION")
    if fd:
        for v in strings_of(fd[2]):
            fields.append(("FILE_DESCRIPTION", v, bool(PATH_RE.search(v))))
    paths = PATH_RE.findall(head)
    for m in ENT_RE.finditer(data):
        body = m.group(4).decode("latin-1")
        vals = [v for v in strings_of(body) if v.strip()]
        fields.append((f"{m.group(1).decode().split('=')[0].strip()} {m.group(2).decode()}", " | ".join(vals),
                       any(personal(v) for v in vals)))
        paths += PATH_RE.findall(body)
    low = text.lower()
    hits = []
    for mk, v in identity():
        if v.lower() in ok_vals:
            continue
        n = len(re.findall(r"(?<![a-z0-9])" + re.escape(v.lower()) + r"(?![a-z0-9])", low))
        if n:
            hits.append((mk, n))
    return {"fields": fields, "hits": hits, "paths": sorted(set(paths))}


def scrub(data, company, keep_system):
    """The file's bytes with the header and the person / organisation entities rewritten."""
    text = data.decode("latin-1")
    end = text.find("ENDSEC;")
    head, rest = text[:end], text[end:]
    fn = header_span(head, "FILE_NAME")
    if fn:
        a = split_args(fn[2])
        while len(a) < 7:
            a.append(QUOTE * 2)
        nm = (strings_of(a[0]) or [""])[0]
        a[0] = q(re.split(r"[\\/]", nm)[-1])
        a[2] = "(" + q(company) + ")"
        a[3] = "(" + q(company) + ")"
        if not keep_system:
            a[5] = QUOTE * 2
        a[6] = q(company)
        head = head[:fn[0]] + "FILE_NAME(" + ",".join(a) + ");" + head[fn[1]:]
    fd = header_span(head, "FILE_DESCRIPTION")
    if fd and PATH_RE.search(fd[2]):
        head = head[:fd[0]] + "FILE_DESCRIPTION(" + PATH_RE.sub("", fd[2]) + ");" + head[fd[1]:]
    out = (head + rest).encode("latin-1")
    cb = q(company).encode("latin-1", "replace")
    empty = (QUOTE * 2).encode()

    def ent(m):
        if m.group(2) == b"PERSON":          # id, last name, first name, middle names, titles: all personal
            new = [empty, cb, empty, b"$", b"$", b"$"]
        else:
            new = [empty, cb, empty]
        return m.group(1) + m.group(2) + m.group(3) + b",".join(new) + m.group(5)

    return ENT_RE.sub(ent, out)


def data_section(data):
    """The data section without the PERSON / ORGANIZATION entities: must be equal before and after."""
    return ENT_RE.sub(b"", data[data.find(b"ENDSEC;"):])


def collect(paths, out_dir):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _d, fs in os.walk(p):
                if out_dir and os.path.abspath(root).startswith(os.path.abspath(out_dir)):
                    continue
                files += [os.path.join(root, f) for f in sorted(fs) if f.lower().endswith((".step", ".stp"))]
        else:
            files.append(p)
    return files


def problems(rep):
    return ([w for w, _v, pers in rep["fields"] if pers] + [mk for mk, _n in rep["hits"]]
            + ["a path"] * len(rep["paths"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="clean or check the header of STEP files")
    mc.add_std_args(ap)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--company")
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--keep-system", action="store_true")
    args = ap.parse_args(argv)
    try:
        job = mc.resolve(args)
    except mc.MechError as e:
        if not (args.check or args.in_place or args.out):
            print(f"could not run: {e}", file=sys.stderr)
            return 2
        here = os.getcwd()                 # no project: --check, --in-place or --out work on their own
        job = mc.Job(here, mc.load_config(here), os.path.abspath(args.out or os.path.join(here, "out")))
    company = args.company if args.company is not None else job.cfg.get("project", {}).get("company", "")
    allow = list(args.allow) + list(job.cfg.get("scrub", {}).get("allow", []))
    clean_dir = os.path.join(job.out, "step_clean")
    files = collect(args.paths, clean_dir)
    if not files:
        print("could not run: give at least one STEP file or a folder with STEP files", file=sys.stderr)
        return 2
    rows = mc.Rows()
    inputs = []
    for k, f in enumerate(files):
        name = os.path.basename(f)
        try:
            with open(f, "rb") as fh:
                data = fh.read()
            rep = inspect(data, company, allow)
        except (OSError, mc.MechError) as e:
            rows.add(f"SC-{k + 1}-00", f"scrub:{name}", "the file can be read as STEP", str(e), "a STEP file",
                     "could_not_run")
            continue
        inputs.append(f)
        print(f"{name}:")
        for where, v, pers in rep["fields"]:
            print(f"   {'!!' if pers else '  '} {where}: {v!r}")
        for mk, n in rep["hits"]:
            print(f"   !! {mk} occurs {n} time(s) in the file")
        for p in rep["paths"]:
            print(f"   !! a path in the header: {p!r}")
        found = problems(rep)
        if args.check:
            rows.add(f"SC-{k + 1}-01", f"scrub:{name}", "no personal-looking value and no path in the STEP header",
                     f"{len(found)} found" + (": " + ", ".join(sorted(set(found))) if found else ""), "0",
                     "pass" if not found else "fail")
            continue
        new = scrub(data, company, args.keep_system)
        dst = f if args.in_place else os.path.join(clean_dir, name)
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        tmp = dst + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(new)
        os.replace(tmp, dst)
        left = problems(inspect(new, company, allow))
        rows.add(f"SC-{k + 1}-01", f"scrub:{name}", "header rewritten; nothing personal-looking left",
                 f"found {len(found)}, left {len(left)}" + (": " + ", ".join(sorted(set(left))) if left else "")
                 + f" -> {dst}", "0 left", "pass" if not left else "fail")
        same = data_section(data) == data_section(new)
        rows.add(f"SC-{k + 1}-02", f"scrub:{name}", "the geometry is untouched (data section equal but for PERSON / "
                 "ORGANIZATION)", "equal" if same else "DIFFERENT", "equal", "pass" if same else "fail")
    rows.write(job.out, "step_scrub.py", inputs)
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
