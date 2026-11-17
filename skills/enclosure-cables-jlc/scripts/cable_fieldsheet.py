"""The value for every field of the cable supplier's quote form, per cable, and the read-back comparison.

What it does
    Reads `cables/cables.json` and the cable supplier's capability sheet (`[forms.<segment>]`: the fields each form
    segment has, in form order; `[limits]`: character and file limits) and writes `<out>/cables/FIELD_SHEET_cables.md`:
    per cable the form segment, the item name "<id> <name>", the value for every field in form order, the
    "More Requirements" text (non-defaults first as "X, NOT Y", then "CUST P/N: <id>"), the files to upload, and an
    empty line-map table (supplier line number <-> our id) to fill the moment the quote is ready.
    A harness form holds: side A / side B (housing and terminal by supplier code, or "Tinned" with a tin length), wire
    standard, AWG, ONE length, colour, twisted, pinout "per drawing", files, more requirements. An rf or ethernet form
    holds only drawings, more requirements and quantity: everything else must be on the drawing and in the note.
    Rows: every form field has a value; the note is within the form's character limit and free of request words; the
    files exist, are of an allowed type and within the count and size limits; one AWG and one length fit the form.
    --readback pasted.txt compares what the agent read back from the filled form with the sheet, one row per field.
    pasted.txt:
        [CAB-01]
        Wire length (mm): 65
        AWG: 24
        ...                       (key = the field's label or key, any case; one section per cable)

Why it exists (the real failure, told without names)
    A length typed into the form did not take at the first try, and a gauge in the form differed from the gauge on the
    drawing; a submitted quote cannot be edited, so the whole cable list was entered again. Values that come from the
    one data file, and a read-back of every field before submitting, end both.

Usage
    python -I cable_fieldsheet.py [--project <mech folder>] [--out <folder>] [--cables cables.json]
                                  [--sheet suppliers/<id>.capability.toml] [--only CAB-01] [--readback pasted.txt]

Config keys (mech.toml)
    [cables] file, supplier, sheet, deny, po_number = ""        [project] name (added to the deny list)

Exit codes
    0 all rows pass   1 a row failed   2 could not run (no cable file, no capability sheet with [forms])
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import cable_common as cc  # noqa: E402


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_")


def more_requirements(c: dict) -> str:
    """Non-defaults first, each as "X, NOT Y", then the customer part number. Nothing else."""
    out = [f"{i}. {ln.rstrip('.')}." for i, ln in enumerate(cc.non_default_lines(c), 1)]
    out.append(f"CUST P/N: {c.get('id', '')}")
    return " ".join(out)


def files_of(c: dict, out_dir: str) -> list[str]:
    cid = str(c.get("id", ""))
    d = os.path.join(out_dir, "cables")
    fs = [os.path.join(d, "drawings", f"{cid}_{slug(c.get('name', ''))}".rstrip("_") + ".pdf")]
    multi = any(cc.end_rows(e) > 1 for e in c.get("ends", []))
    empty = any(cc.empty_positions(e) for e in c.get("ends", []))
    if multi or empty or len(c.get("wires") or []) > 2:
        fs.append(os.path.join(d, "pictures", f"{cid}_wiring.png"))
    import cable_check
    for e in c.get("ends", []):
        if cable_check.is_angled(e):
            fs.append(os.path.join(d, "pictures", f"{cid}_{e['id']}_orientation.png"))
    return fs


def side(c: dict, idx: int) -> dict:
    ends = c.get("ends", [])
    if idx >= len(ends):
        return {"housing": "", "terminal": "", "tin": ""}
    e = ends[idx]
    if e.get("kind") == "tinned":
        return {"housing": "Tinned", "terminal": "", "tin": f"{cc.fmt(e.get('tin_mm') or 0)} mm"}
    p, t = e.get("part") or {}, e.get("terminal") or {}
    return {"housing": f"{p.get('supplier_code', '')} ({p.get('mpn', '')})".strip(), "terminal": f"{t.get('supplier_code', '')} ({t.get('mpn', '')})".strip() if t else "",
            "tin": ""}


def values(c: dict, out_dir: str, po: str = "") -> tuple[dict, list[str]]:
    """key -> value for every field key this script knows, and the problems found while deriving them."""
    probs = []
    ws = c.get("wires") or []
    awgs = sorted({w.get("awg") for w in ws if isinstance(w.get("awg"), (int, float))})
    cols = list(dict.fromkeys(str(w.get("colour", "")) for w in ws))
    if len(awgs) > 1:
        probs.append(f"the form holds ONE AWG and the wires are {awgs}")
    if len(c.get("ends", [])) > 2:
        probs.append("the form holds two sides; the third end is on the drawing only: write it in More Requirements")
    a, b = side(c, 0), side(c, 1)
    v = {
        "item_name": f"{c.get('id', '')} {c.get('name', '')}".strip(),
        "side_a_housing": a["housing"], "side_a_terminal": a["terminal"], "side_a_tin": a["tin"],
        "side_b_housing": b["housing"], "side_b_terminal": b["terminal"], "side_b_tin": b["tin"],
        "wire_standard": str(c.get("wire_standard", "UL1007")) if ws else "",
        "awg": (f"{awgs[0]:g}" if len(awgs) == 1 else ", ".join(f"{x:g}" for x in awgs)) if ws else "",
        "length": cc.fmt(c["length_mm"]) if isinstance(c.get("length_mm"), (int, float)) else "",
        "colour": (cols[0] if len(cols) == 1 else "MultiColor: " + ", ".join(cols) + " (per drawing)") if ws else "",
        "twisted": ("Yes" if c.get("twisted") else "No") if ws else "",
        "pinout": "Other (per drawing)" if ws else "",
        "files": "; ".join(os.path.basename(f) for f in files_of(c, out_dir)),
        "more_requirements": more_requirements(c),
        "quantity": str(c.get("qty", "")),
        "po_number": po,
    }
    return v, probs


NOT_USED = "(leave empty)"
OPTIONAL = {"po_number"}


def field_value(f: dict, v: dict) -> str | None:
    """The value of one form field: fixed by the sheet, known from cables.json, or None (unknown key)."""
    if "fixed" in f:
        return str(f["fixed"])
    k = f.get("key")
    if k not in v:
        return None
    return v[k]


def norm(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u00b1", "+-")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(?:mm|pcs|awg)?", s)
    if m:
        return f"{float(m.group(1)):g}"
    return s.strip(" .;")


def parse_readback(path: str) -> dict:
    """{cable id: {normalised key: value}}"""
    out, cur = {}, None
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            m = re.fullmatch(r"\s*\[(.+?)\]\s*", line)
            if m:
                cur = out.setdefault(m.group(1).strip(), {})
                continue
            if cur is None or ":" not in line:
                continue
            k, val = line.split(":", 1)
            cur[norm_key(k)] = val.strip()
    return out


def norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(k).lower())


def run(job, a) -> tuple[mc.Rows, list, str | None]:
    data, cpath = cc.load_cables(job, a.cables)
    cap, cap_path = cc.capability(job, a.sheet)
    if cap is None or not isinstance(cap.get("forms"), dict):
        raise mc.MechError(f"no capability sheet with [forms] at {cap_path}: copy the seed from the skill's templates into suppliers/ and re-read the live form")
    cfg = cc.cable_cfg(job)
    deny = list(cfg.get("deny") or []) + ([job.cfg["project"]["name"]] if str(job.cfg["project"].get("name", "")).strip() else [])
    lim_chars, w1 = cc.limit(cap, "more_requirements_chars", 500)
    lim_files, w2 = cc.limit(cap, "files_max", 5)
    lim_mb, w3 = cc.limit(cap, "file_max_mb", 15)
    types = [str(x).lower() for x in cc.limit(cap, "file_types", ["pdf", "png", "jpg", "jpeg"])[0]]
    rows = mc.Rows()
    back = parse_readback(a.readback) if a.readback else None
    md = ["# Field sheet: cables", "",
          f"Supplier: {cap.get('meta', {}).get('supplier', '')} (capability sheet read {cap.get('meta', {}).get('read_date', 'no date')}; re-read the live form first).",
          "Type every value exactly as written; read every field back before submitting (`cable_fieldsheet.py --readback`).",
          "A submitted quote cannot be edited: the cable list must be frozen first.", ""]
    for c in data["cables"]:
        cid = str(c.get("id", ""))
        if a.only and cid != a.only:
            continue
        sec = f"cable {cid}"
        seg = c.get("type", "other")
        form = cap["forms"].get(seg) or cap["forms"].get("other")
        if not form or not form.get("fields"):
            rows.add(f"{cid}-FORM", sec, "form segment", f"the capability sheet has no [forms.{seg}]", "a form segment with its fields", "could_not_run")
            continue
        v, probs = values(c, job.out, str(cfg.get("po_number", "") or ""))
        md += [f"## {cid} {c.get('name', '')}", "", f"Form segment: **{form.get('name', seg)}**" + (f" ({form['note']})" if form.get("note") else ""), "",
               "| # | Field | Value |", "|---|---|---|"]
        missing = []
        fields = []
        for i, f in enumerate(form["fields"], 1):
            val = field_value(f, v)
            lab = f.get("label", f.get("key", ""))
            if val is None:
                missing.append(lab)
                shown = "(not derived from cables.json: decide by hand)"
            elif val == "":
                shown = NOT_USED
                side_key = f.get("key", "")
                if side_key not in OPTIONAL and not side_key.endswith(("_tin", "_terminal")):
                    missing.append(lab)
            else:
                shown = val
            fields.append((f, lab, val))
            md.append(f"| {i} | {lab} | {shown.replace('|', '/')} |")
        md.append("")
        rows.add(f"{cid}-FIELDS", sec, f"a value for every field of the {form.get('name', seg)} form", "; ".join(["no value: " + ", ".join(missing)] if missing else [])
                 or f"{len(form['fields'])} fields", "every field of the form has its value", "fail" if missing else "pass")
        if probs:
            rows.add(f"{cid}-ONE", sec, "one value per form field", "; ".join(probs), "one AWG, one length, two sides", "fail")
        else:
            rows.add(f"{cid}-ONE", sec, "one value per form field", "one AWG, one length", "one AWG, one length, two sides", "pass")
        note = v["more_requirements"]
        bad = cc.text_findings(note, deny)
        md += ["More Requirements (paste as one block):", "", "```", note, "```", f"{len(note)} of {lim_chars} characters.", ""]
        rows.add(f"{cid}-NOTE-LEN", sec, "More Requirements length", f"{len(note)} characters", f"<= {lim_chars} ({w1})", "pass" if len(note) <= int(lim_chars) else "fail")
        rows.add(f"{cid}-NOTE-TEXT", sec, "More Requirements wording", "; ".join(bad) or "non-defaults as 'X, NOT Y', then the part number",
                 "no question, request word, alternative or deny-list name", "fail" if bad else "pass")
        has_pn = f"CUST P/N: {cid}" in note
        nd_first = not cc.non_default_lines(c) or note.startswith("1. " + cc.non_default_lines(c)[0][:20])
        rows.add(f"{cid}-NOTE-PN", sec, "part number and non-defaults in the note", "CUST P/N present, non-defaults first" if has_pn and nd_first else "missing",
                 "non-defaults first, then CUST P/N: <id>", "pass" if has_pn and nd_first else "fail")
        fs = files_of(c, job.out)
        md += ["Files to upload:", ""]
        badf = []
        for fpath in fs:
            ok = os.path.isfile(fpath)
            size = os.path.getsize(fpath) / 1e6 if ok else 0.0
            md.append(f"- `{os.path.relpath(fpath, job.out).replace(os.sep, '/')}`" + (f" ({size:.2f} MB)" if ok else " (NOT MADE YET: run cable_drawings.py)"))
            if not ok:
                badf.append(f"{os.path.basename(fpath)} does not exist")
            elif size > float(lim_mb):
                badf.append(f"{os.path.basename(fpath)} is {size:.1f} MB")
            if os.path.splitext(fpath)[1].lstrip(".").lower() not in types:
                badf.append(f"{os.path.basename(fpath)}: type not accepted")
        if len(fs) > int(lim_files):
            badf.append(f"{len(fs)} files, the form takes {lim_files}")
        md.append("")
        rows.add(f"{cid}-FILES", sec, "files to upload", "; ".join(badf) or f"{len(fs)} file(s)", f"exist, <= {lim_files} files ({w2}), <= {lim_mb} MB each ({w3}), types {', '.join(types)}",
                 "fail" if badf else "pass")
        if back is not None:
            got = back.get(cid)
            if got is None:
                rows.add(f"{cid}-RB", sec, "read-back of the form", f"no [{cid}] section in the pasted text", "every field read back", "fail")
                continue
            for f, lab, val in fields:
                key = f.get("key", "")
                g = got.get(norm_key(lab), got.get(norm_key(key)))
                want = "" if val in (None,) else val
                rid = f"{cid}-RB-{key or norm_key(lab)}"
                if key == "files":
                    wantset = sorted(norm(x) for x in want.split(";") if x.strip())
                    gotset = sorted(norm(x) for x in re.split(r"[;,]", g or "") if x.strip())
                    rows.add(rid, sec, f"read-back: {lab}", "match" if wantset == gotset else f"differs: sheet {wantset}, form {gotset}", "the form shows the sheet's files",
                             "pass" if wantset == gotset else "fail")
                    continue
                if g is None:
                    if want == "":
                        rows.add(rid, sec, f"read-back: {lab}", "empty on the sheet, not read back", "the form shows the sheet's value", "na")
                    else:
                        rows.add(rid, sec, f"read-back: {lab}", f"not read back (sheet: {want[:60]})", "every field read back", "fail")
                    continue
                ok = norm(g) == norm(want) or (want == "" and norm(g) in ("", "-", "none", "empty"))
                rows.add(rid, sec, f"read-back: {lab}", "match" if ok else f"differs: sheet '{want[:80]}', form '{g[:80]}'", "the form shows the sheet's value",
                         "pass" if ok else "fail")
    md += ["## Line map (fill the moment the quote is ready)", "",
           "The supplier numbers the lines itself; the entry order does not fix them. Name both numbers in every message: \"line -2 (CAB-01)\".", "",
           "| Supplier line | Our id | Name | Checked on (date) |", "|---|---|---|---|"]
    for c in data["cables"]:
        if a.only and c.get("id") != a.only:
            continue
        md.append(f"|  | {c.get('id', '')} | {c.get('name', '')} |  |")
    md.append("")
    path = None
    if not a.readback:
        path = os.path.join(job.out, "cables", "FIELD_SHEET_cables.md")
        mc.atomic_write(path, "\n".join(md))
    return rows, [cpath, cap_path] + ([a.readback] if a.readback else []), path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Field sheet of the cable quote form, and the read-back check.", epilog="Exit codes: 0 pass, 1 fail, 2 could not run.")
    mc.add_std_args(ap)
    ap.add_argument("--cables", help="the cable data file")
    ap.add_argument("--sheet", help="capability sheet of the cable supplier")
    ap.add_argument("--only", help="one cable id")
    ap.add_argument("--readback", help="text file with the values read back from the form")
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
        if a.readback and not os.path.isfile(a.readback):
            raise mc.MechError(f"no read-back file at {a.readback}")
        rows, inputs, path = run(job, a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(job.out, "cable_readback.py" if a.readback else "cable_fieldsheet.py", inputs)
    if path:
        print("  wrote", path)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
