"""Catalogue word scan: flags every word of an upload set that is not a catalogue value of the supplier's capability sheet.

What it does
    Reads the capability sheet (`suppliers/<id>.capability.toml`: finishes, inks, materials, limits, ink_rgb) and scans
    the upload set: remark and notes text files, field-sheet TOML/MD/CSV/JSON, PDF text (PyMuPDF when present), DXF layer
    names and TEXT/MTEXT (ezdxf when present, else the raw DXF text). One row per hit, with file, page or line and the
    words around it:
      (a) request words that are not catalogue values: RAL, Pantone, PMS, mask / masking, "if possible", "fallback",
          "or equivalent", "or similar", "please confirm", "please advise", TBD, a question mark, and a tolerance
          tighter than the sheet's standard tolerance;
      (b) colour, finish, ink or material words that are not on the sheet's lists;
      (c) product-looking names from a user deny list (one per line, or re:PATTERN).
    The model remark of templates/REMARK.md says "layer colour = ink": that phrase states HOW the silkscreen layers are
    coloured (each layer's colour is its ink); it is not a colour value and is accepted ("layer color = ink" too).
    "layer colour = Magenta" is still flagged.
    Exit 1 on any hit that is not waived in `catalogue_waivers.toml` with a reason.

Why it exists (the real failure, told without names)
    A job was sent with a masking request, an RAL colour and a Pantone ink, none of which the supplier's form or chart
    offers; the order was put on hold and the grounding had to be planned again. A word that is
    not a field value or a chart name is a request, and a request costs a day.

Usage
    python -I catalogue_scan.py --sheet suppliers/<id>.capability.toml <folder or file> [...] [--deny deny.txt]
                                [--waivers catalogue_waivers.toml] [--project <mech folder>] [--out DIR]
    waivers: [[waiver]] file = "remark.txt", match = "if possible", reason = "why this one is fine"
             (file: base name or glob; match: text that must appear in the hit's words; both optional; reason required)

Config keys (mech.toml)
    [catalogue] sheet = "suppliers/x.capability.toml", scan = ["out/upload"], deny_file, waivers = "catalogue_waivers.toml"
    capability sheet: [limits] standard_tolerance = 0.5   (mm; a stated tolerance below it is flagged)

Exit codes
    0 no unwaived hit   1 at least one unwaived hit   2 could not run (no sheet, no input)
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import fnmatch
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

REQUEST_WORDS = [
    ("RAL colour", re.compile(r"(?<![A-Za-z])RAL(?![A-Za-z])\s*-?\s*\d{0,4}", re.I)),
    ("Pantone", re.compile(r"(?<![A-Za-z])Pantone(?![A-Za-z])|(?<![A-Za-z])PMS(?![A-Za-z])\s*\d*", re.I)),
    ("masking", re.compile(r"(?<![A-Za-z])mask(?:ed|ing|s)?(?![A-Za-z])", re.I)),
    ("hedged request", re.compile(r"\bif possible\b|\bfallback\b|\bor equivalent\b|\bor similar\b|\bas far as possible\b|\bif you can\b", re.I)),
    ("question to the supplier", re.compile(r"\bplease (?:confirm|advise)\b|\bkindly (?:confirm|advise)\b|\bcould you (?:confirm|advise)\b", re.I)),
    ("open item", re.compile(r"\bTBD\b|\bTBC\b|\bto be (?:decided|confirmed|defined)\b", re.I)),
    ("question mark", re.compile(r"\?")),
]
COLOUR_WORDS = ["black", "white", "gray", "grey", "silver", "red", "blue", "green", "yellow", "orange", "purple", "pink", "brown", "gold",
                "bronze", "magenta", "cyan", "beige", "transparent", "matte", "matt", "glossy", "gloss", "satin", "textured",
                "anodized", "anodised", "anodize", "powder", "chrome", "nickel", "zinc", "galvanized", "polished", "brushed"]
MATERIAL_WORDS = ["aluminium", "aluminum", "steel", "stainless", "brass", "copper", "titanium", "abs", "pla", "petg", "tpu", "nylon", "acrylic", "pom", "peek"]
TOL_RX = re.compile(r"(?:\u00b1|\+/-|\+-|\u00b1)\s*(\d+(?:[.,]\d+)?)\s*(mm|\u00b5m|um)?", re.I)
LAYER_INK_OK = re.compile(r"\blayer\s+colou?r\s*=\s*ink\b", re.I)     # the model remark's phrase, not a colour value
KV_RX = re.compile(r"\b(colou?r|finish|ink|coating|coat|material)\s*[:=]\s*([A-Za-z][A-Za-z0-9 \-/]{1,40}?)(?=[,;.\n\r]|$)", re.I | re.M)
TEXT_EXT = {".txt", ".md", ".toml", ".csv", ".json", ".yaml", ".yml", ".html", ".htm", ".tsv", ".rst"}


def _walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k != "meta":
                yield from _walk_strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _walk_strings(v)


class Sheet:
    def __init__(self, data: dict):
        self.data = data
        vals = []
        for sect in ("finishes", "materials", "ink_rgb"):
            d = data.get(sect, {})
            vals += list(_walk_strings(d)) + ([k for k in d] if sect == "ink_rgb" else [])
        self.values = [v for v in vals if not re.fullmatch(r"#[0-9a-fA-F]{6}", v)]
        self.vocab = set(re.findall(r"[a-z]+", " ".join(self.values).lower()))
        keys = {k.lower() for sect in ("finishes", "materials") for k in data.get(sect, {})}    # the sheet's own category words
        for k in keys:
            self.vocab.add(k)
            if k.startswith("anodi"):
                self.vocab.update(("anodize", "anodized", "anodise", "anodised"))
            if k in ("inks", "ink"):
                self.vocab.update(("ink", "inks"))
        lim = data.get("limits", {})
        self.std_tol = lim.get("standard_tolerance", data.get("tolerances", {}).get("standard"))

    def has_phrase(self, p: str) -> bool:
        p = p.strip().lower()
        return any(p == v.lower() or v.lower().startswith(p) or p.startswith(v.lower()) for v in self.values)


def _ctx(text, m, w=28):
    a, b = max(0, m.start() - w), min(len(text), m.end() + w)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def scan_text(sheet: Sheet, text: str, deny_lit, deny_rx):
    """-> list of (kind, line, words)"""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        for kind, rx in REQUEST_WORDS:
            for m in rx.finditer(line):
                hits.append((kind, n, _ctx(line, m)))
        for m in TOL_RX.finditer(line):
            v = float(m.group(1).replace(",", "."))
            if (m.group(2) or "mm").lower() in ("um", "\u00b5m"):
                v /= 1000.0
            if sheet.std_tol is not None and v < float(sheet.std_tol) - 1e-9:
                hits.append(("tolerance tighter than the sheet's standard", n, f"{_ctx(line, m)} (sheet standard {sheet.std_tol} mm)"))
        okspans = [m.span() for m in LAYER_INK_OK.finditer(line)]
        for m in KV_RX.finditer(line):
            val = m.group(2).strip()
            if val.lower() == "ink" and any(a <= m.start() and m.end() <= b + 1 for a, b in okspans):
                continue                                    # "layer colour = ink": how the layers are coloured, not which colour
            if val and not sheet.has_phrase(val) and not re.fullmatch(r"\d+(\.\d+)?", val):
                hits.append(("value not on the sheet's lists", n, _ctx(line, m)))
        low = line.lower()
        reported = set()
        for w in COLOUR_WORDS + MATERIAL_WORDS:
            if w in sheet.vocab or w in reported:
                continue
            m = re.search(r"\b" + re.escape(w) + r"\b", low)
            if m:
                reported.add(w)
                hits.append(("colour/finish/material word not on the sheet", n, _ctx(line, re.search(re.escape(w), line, re.I) or m)))
        for d in deny_lit:
            if d in low:
                hits.append(("deny-list name", n, f"matches deny entry #{deny_lit.index(d) + 1}"))
        for i, r in enumerate(deny_rx):
            if r.search(line):
                hits.append(("deny-list name", n, f"matches deny pattern #{i + 1}"))
    return hits


def read_file(path):
    """-> list of (location label prefix, text) segments."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            import pymupdf as fitz
        except ImportError:
            return [("", None, "PDF skipped: PyMuPDF is missing")]
        doc = fitz.open(path)
        segs = [(f"page {i + 1}", pg.get_text(), "") for i, pg in enumerate(doc)]
        doc.close()
        return segs
    if ext == ".dxf":
        try:
            import ezdxf
            doc = ezdxf.readfile(path)
            segs = [("layers", "\n".join(l.dxf.name for l in doc.layers), "")]
            txt = []
            for e in doc.modelspace():
                if e.dxftype() == "TEXT":
                    txt.append(e.dxf.text)
                elif e.dxftype() == "MTEXT":
                    txt.append(e.text)
                txt.append("")
            segs.append(("text", "\n".join(txt), ""))
            segs.append(("entity layers", "\n".join(sorted({e.dxf.layer for e in doc.modelspace()})), ""))
            return segs
        except ImportError:
            return [("raw dxf", open(path, encoding="utf-8", errors="replace").read(), "ezdxf missing: raw text read, layer names not separated")]
        except Exception as e:
            return [("", None, f"DXF unreadable: {e}")]
    if ext in TEXT_EXT:
        return [("", open(path, encoding="utf-8", errors="replace").read(), "")]
    return []


def load_waivers(path):
    if not path or not os.path.isfile(path):
        return []
    w = mc.load_toml(path).get("waiver", [])
    for x in w:
        if not str(x.get("reason", "")).strip():
            raise mc.MechError(f"{path}: every waiver needs a reason ({x})")
    return w


def waived(w, relfile, words):
    for x in w:
        fi, ma = x.get("file"), x.get("match")
        if fi and not (fnmatch.fnmatch(os.path.basename(relfile), fi) or fnmatch.fnmatch(relfile, fi)):
            continue
        if ma and ma.lower() not in words.lower():
            continue
        return x["reason"]
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Flag request words that are not catalogue values.", epilog="Exit: 0 clean, 1 hit, 2 could not run.")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--sheet")
    ap.add_argument("--deny")
    ap.add_argument("--waivers")
    ap.add_argument("--project")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        paths, sheet_p, deny_p, wav_p, out = list(a.paths), a.sheet, a.deny, a.waivers, a.out
        if a.project or not (paths and sheet_p):
            job = mc.resolve(a)
            cc = job.cfg.get("catalogue", {})
            sheet_p = sheet_p or (mc.rel_to_project(job.cfg, cc["sheet"]) if cc.get("sheet") else None)
            paths = paths or [mc.rel_to_project(job.cfg, p) for p in cc.get("scan", ["out/upload"])]
            deny_p = deny_p or (mc.rel_to_project(job.cfg, cc["deny_file"]) if cc.get("deny_file") else None)
            wav_p = wav_p or (mc.rel_to_project(job.cfg, cc["waivers"]) if cc.get("waivers") else None)
            if not wav_p and os.path.isfile(os.path.join(job.project, "catalogue_waivers.toml")):
                wav_p = os.path.join(job.project, "catalogue_waivers.toml")
            out = out or job.out
        if not sheet_p or not os.path.isfile(sheet_p):
            raise mc.MechError("no capability sheet: give --sheet suppliers/<id>.capability.toml")
        sheet = Sheet(mc.load_toml(sheet_p))
        deny = []
        if deny_p:
            deny = [ln.strip() for ln in open(deny_p, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
        deny_lit = [d.lower() for d in deny if not d.startswith("re:")]
        deny_rx = [re.compile(d[3:], re.I) for d in deny if d.startswith("re:")]
        wv = load_waivers(wav_p)
        files = []
        for p in paths:
            if os.path.isfile(p):
                files.append(p)
            elif os.path.isdir(p):
                for r, _ds, fs in os.walk(p):
                    files += [os.path.join(r, f) for f in fs]
            else:
                raise mc.MechError(f"not a file or folder: {p}")
    except (mc.MechError, OSError) as e:
        print("could not run:", e)
        return 2
    rows = mc.Rows()
    n = scanned = 0
    for f in sorted(files):
        segs = read_file(f)
        if not segs:
            continue
        scanned += 1
        for label, text, note in segs:
            if text is None:
                rows.add(f"CAT-U{n}", "catalogue", os.path.basename(f), note, "every file in the set is read", "could_not_run")
                continue
            for kind, line, words in scan_text(sheet, text, deny_lit, deny_rx):
                n += 1
                loc = f"{label} line {line}" if label else f"line {line}"
                why = waived(wv, f, words)
                rows.add(f"CAT-{n:03d}", "catalogue", f"{os.path.basename(f)} ({loc}): {kind}", f"\"{words}\"",
                         "only field values and catalogue names" + (f"; WAIVED: {why}" if why else ""), "pass" if why else "fail")
    if sheet.std_tol is None:
        rows.add("CAT-TOL", "catalogue", "tolerances against the sheet's standard", "the sheet has no [limits] standard_tolerance", "a standard tolerance on the sheet", "could_not_run")
    if scanned == 0:
        rows.add("CAT-000", "catalogue", "files to scan", "no readable file found", "at least one file", "could_not_run")
    elif not any(r["id"].startswith("CAT-0") and r["verdict"] in ("fail", "pass") and r["id"] != "CAT-000" for r in rows.rows) and n == 0:
        rows.add("CAT-000", "catalogue", f"{scanned} file(s) scanned", "no request word, no value off the sheet", "only catalogue values", "pass")
    rows.print_table(only_bad=True)
    if out:
        rows.write(out, "catalogue_scan.py", [sheet_p] + ([wav_p] if wav_p and os.path.isfile(wav_p) else []))
    print(rows.headline() + f"  ({scanned} files)")
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
