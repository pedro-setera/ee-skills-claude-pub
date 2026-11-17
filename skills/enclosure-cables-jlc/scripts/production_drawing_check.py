"""The supplier's cable production drawing checked field by field against the cable data file, with a ready revise note.

What it does
    The cable supplier draws its own production drawing of every cable after payment. The agent READS each drawing
    (PDF or picture) and writes what it sees into `supplier_drawing_<id>.toml` (template: --template <id>): the wire
    per position at each end, the gauge, the cable text, the part numbers, the length and its tolerance, the label
    text, whether the pin-1 mark is drawn, the drawing date and the supplier's line number. This script compares that
    file with `cables/cables.json` and writes one row per field: "match" or "differs: ours X, theirs Y":
      LINE, DATE          the supplier's line number is recorded; the drawing is not older than our last revise note
      LEN, TOL            length and tolerance
      LABEL               label text
      CABLE               the cable or wire text (rf / ethernet: judged by the reader, `cable_matches`)
      <end>-PART, -TERM   housing / connector and terminal part numbers; the terminal's printed gauge range takes the wire
      <end>-TIN, -EXIT    tin length; the way an angled plug's cable leaves
      WIRE-<pos>          per wire: position at the other end, colour, gauge; and no wire in a position we keep EMPTY
      PIN1, EXTRAS        the pin-1 mark is drawn; nothing is drawn that was not ordered
      EYE                 values pre-filled from the PDF text were verified by eye
    An empty value in the TOML means "not read": the row reads "could not run", never "match".
    Per cable it writes `<out>/cables/production/REVISE_<id>.txt`: short numbered lines "X, NOT Y" under the header
    "Line <n> (<id>)", within the supplier's character limit (capability sheet `[limits] revise_chars`, default 500),
    and names the ONE picture to attach. The verdict is CONFIRM only when every row matches; otherwise REVISE, or
    NOT DECIDED while fields are unread. A summary goes to `<out>/cables/production/PRODUCTION_DRAWING_CHECK.md`.
    --template <id> --pdf their.pdf also extracts the PDF's text (PyMuPDF) and pre-fills what it can find (length,
    tolerance, date, our label when it is printed verbatim), listed under `prefilled` and marked "pre-filled, verify
    by eye": the check wants `verified_by_eye = true` before those fields can match.

Why it exists (the real failure, told without names)
    Supplier production drawings can come back with wires in the wrong cavities, a gauge outside the crimp's range,
    the supplier's stock cable instead of the one asked, the standard tolerance instead of ours. Checking "in bulk"
    misses these; a row per field does not, and one complete revise note per cable saves a round.

Usage
    python -I production_drawing_check.py --template CAB-01 [--pdf their_drawing.pdf] [--dir <folder>] [--project ...]
    python -I production_drawing_check.py [--project <mech folder>] [--out <folder>] [--dir <folder>] [--only CAB-01]
                                          [--cables cables.json] [--sheet <capability.toml>] [--sent 2026-01-31]
        --dir    where the supplier_drawing_<id>.toml files are (default <project>/orders/production_drawings)
        --sent   date of our last revise note: a drawing dated before it is the old one

Config keys (mech.toml)
    [cables] file, supplier, sheet, deny      capability sheet: [limits] revise_chars = 500, revise_pictures = 1

Exit codes
    0 every row matches (CONFIRM for every cable)   1 a row differs   2 could not run, or fields are unread
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import datetime
import glob
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import cable_common as cc  # noqa: E402

VERIFY = "pre-filled, verify by eye"


def alnum(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0)


def parse_date(s):
    s = str(s or "").strip()
    for f in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d.%m.%Y", "%Y.%m.%d"):
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------- template ------------------------------------------
def pdf_text(path: str) -> str | None:
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError:
            return None
    doc = fitz.open(path)
    return "\n".join(pg.get_text() for pg in doc)


def prefill(c: dict, text: str) -> dict:
    """What can be read from the PDF's text layer. Only values printed in an unmistakable form."""
    out = {}
    m = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\u00b1|\+/-|\+-)\s*(\d+(?:\.\d+)?)", text)
    if len(m) == 1:
        out["length_mm"], out["tol_mm"] = float(m[0][0]), float(m[0][1])
    elif len(m) > 1:
        cand = [x for x in m if float(x[0]) > 5]
        if len(cand) == 1:
            out["length_mm"], out["tol_mm"] = float(cand[0][0]), float(cand[0][1])
    d = re.findall(r"\b(20\d\d[/.-]\d{1,2}[/.-]\d{1,2})\b", text)
    if d:
        ds = sorted({x for x in (parse_date(v.replace(".", "-").replace("/", "-")) for v in d) if x})
        if ds:
            out["drawing_date"] = ds[-1].isoformat()
    lab = str(c.get("label", "")).strip()
    if lab and lab in text:
        out["label"] = lab
    return out


def toml_str(s) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def template(c: dict, pre: dict | None, pdf_name: str = "") -> str:
    pre = pre or {}
    keys = [k for k in ("length_mm", "tol_mm", "drawing_date", "label") if k in pre]
    cid = c.get("id", "")

    def val(k, empty, comment):
        if k in pre:
            v = pre[k]
            return (f"{v:g}" if isinstance(v, float) else toml_str(v)) + f"      # {VERIFY}"
        return empty + comment

    L = [f"# What the supplier's production drawing of {cid} shows. Fill every value while READING their drawing;",
         "# never copy from cables.json. Leave a value empty (\"\" or 0) when you could not read it: it then counts as not read.",
         f"cable = {toml_str(cid)}",
         'line = ""                    # the supplier\'s line number of this cable (for example "-2")',
         f"drawing_date = {val('drawing_date', chr(34) * 2, '            # the date printed on their drawing (YYYY-MM-DD)')}",
         f"length_mm = {val('length_mm', '0', '')}",
         f"tol_mm = {val('tol_mm', '0', '')}",
         f"label = {val('label', chr(34) * 2, '                   # the label text as they print it')}",
         'cable_text = ""              # the wire / cable line of their BOM, as printed',
         'cable_matches = ""           # "yes" or "no": is that the cable we ordered (type, diameter, jacket)',
         'pin1_mark = ""               # "yes" or "no": a pin-1 mark is drawn at every housing ("n/a" without housings)',
         'extras = ""                  # "none", or what is drawn that we did not order (sleeves, ties, other parts)',
         f"prefilled = [{', '.join(toml_str(k) for k in keys)}]",
         "verified_by_eye = false      # set true after comparing every pre-filled value with the drawing itself"]
    if pdf_name:
        L.append(f"source = {toml_str(pdf_name)}")
    for e in c.get("ends", []):
        L += ["", f"[ends.{e['id']}]"]
        k = e.get("kind")
        if k == "tinned":
            L.append("tin_mm = 0               # the stripped and tinned length as dimensioned (a \"T = n\" near the length may be a twist pitch)")
        else:
            L.append('part = ""                # housing / connector part number or code as printed')
            if k == "housing":
                L.append('terminal = ""            # terminal part number or code as printed')
                L.append('terminal_awg = ""        # the gauge range printed for that terminal, for example "22-28"')
            import cable_check
            if cable_check.is_angled(e):
                L.append('exit = ""                # the way the cable leaves the plug as drawn: left / right / up / down')
    ws = c.get("wires") or []
    if ws:
        L += ["", "# One [[wire]] per wire AS THEY DREW IT (add or delete blocks to match THEIR drawing).",
              '# from / to = "P1.<position>" / "P2.<position>" (a tinned end: the lead number).']
        for _ in ws:
            L += ["[[wire]]", 'from = ""', 'to = ""', 'colour = ""', "awg = 0", ""]
    return "\n".join(L).rstrip("\n") + "\n"


# ---------------------------------------------------------------- compare -------------------------------------------
class Result:
    def __init__(self, cid):
        self.cid = cid
        self.lines: list[str] = []            # revise lines
        self.need_wiring_picture = False
        self.need_orientation = None


def check_one(c: dict, sd: dict, rows: mc.Rows, sent, src: str) -> Result:
    cid = str(c.get("id", ""))
    sec = f"cable {cid}"
    res = Result(cid)
    pre = set(sd.get("prefilled") or [])
    eye = bool(sd.get("verified_by_eye"))

    def row(code, check, ours, theirs, same, revise=None, unread=None):
        """One field. `unread` True -> could not run."""
        rid = f"{cid}-{code}"
        if unread if unread is not None else blank(theirs):
            rows.add(rid, sec, check, f"not read (ours: {ours})", "read on the supplier's drawing and equal to ours", "could_not_run")
            return
        if same:
            rows.add(rid, sec, check, f"match: {theirs}", "equal to cables.json", "pass")
        else:
            rows.add(rid, sec, check, f"differs: ours {ours}, theirs {theirs}", "equal to cables.json", "fail")
            if revise:
                res.lines.append(revise)

    # line and date
    line = str(sd.get("line", "")).strip()
    rows.add(f"{cid}-LINE", sec, "supplier's line number recorded", line or "not recorded", "both numbers go into every message",
             "pass" if line else "could_not_run")
    dd = parse_date(sd.get("drawing_date"))
    if dd is None:
        rows.add(f"{cid}-DATE", sec, "drawing date", "not read", "the date printed on their drawing", "could_not_run")
    elif sent and dd < sent:
        rows.add(f"{cid}-DATE", sec, "drawing date", f"{dd} is before our revise note of {sent}: this is the old drawing", "not older than our last note", "fail")
    else:
        rows.add(f"{cid}-DATE", sec, "drawing date", str(dd), "not older than our last note" if sent else "recorded", "pass")
    # length, tolerance, label
    L, tol = c.get("length_mm"), c.get("tol_mm")
    tl, tt = sd.get("length_mm"), sd.get("tol_mm")
    row("LEN", "length", f"{cc.fmt(L)} mm", f"{tl:g} mm" if not blank(tl) else "", not blank(tl) and abs(float(tl) - float(L)) < 1e-6,
        f"Length {cc.fmt(L)} mm, NOT {tl:g} mm." if not blank(tl) else None)
    row("TOL", "length tolerance", f"+-{cc.fmt(tol)} mm", f"+-{tt:g} mm" if not blank(tt) else "", not blank(tt) and abs(float(tt) - float(tol)) < 1e-6,
        f"Length tolerance +-{cc.fmt(tol)} mm, NOT +-{tt:g} mm." if not blank(tt) else None)
    lab = str(c.get("label", "")).strip()
    tlab = str(sd.get("label", "")).strip()
    row("LABEL", "label text", f"'{lab}'", f"'{tlab}'" if tlab else "", tlab == lab, f"Label text \"{lab}\", NOT \"{tlab}\".")
    # cable
    cm = str(sd.get("cable_matches", "")).strip().lower()
    ctext = str(sd.get("cable_text", "")).strip()
    kind = c.get("type")
    if kind in ("rf", "ethernet", "other") and not (c.get("wires") or []):
        want = next((nd for nd in c.get("non_defaults") or [] if str(nd.get("item", "")).lower() == "cable"), None)
        ours = (want or {}).get("want") or c.get("cable_spec", "")
        row("CABLE", "cable", ours, ctext or cm, cm in ("yes", "y", "true"), f"Cable: {ours}, NOT {ctext or 'the cable drawn'}.",
            unread=cm not in ("yes", "y", "true", "no", "n", "false") or not ctext)
    else:
        std = str(c.get("wire_standard", "UL1007"))
        if not ctext:
            row("CABLE", "wire standard", std, "", False)
        else:
            row("CABLE", "wire standard", std, ctext, alnum(std) in alnum(ctext), f"Wire {std}, NOT {ctext}.")
    # ends
    import cable_check
    their_ends = sd.get("ends") or {}
    for e in c.get("ends", []):
        te = their_ends.get(e["id"]) or {}
        k = e.get("kind")
        if k == "tinned":
            tin = te.get("tin_mm")
            row(f"{e['id']}-TIN", f"{e['id']} tin length", f"{cc.fmt(e.get('tin_mm') or 0)} mm", f"{tin:g} mm" if not blank(tin) else "",
                not blank(tin) and abs(float(tin) - float(e.get("tin_mm") or 0)) < 1e-6, f"{e['id']} tinned {cc.fmt(e.get('tin_mm') or 0)} mm, NOT {tin:g} mm." if not blank(tin) else None)
            continue
        p = e.get("part") or {}
        tp = str(te.get("part", "")).strip()
        ours = " / ".join(x for x in (p.get("mpn", ""), p.get("supplier_code", "")) if x)
        same = bool(tp) and any(alnum(x) and alnum(x) in alnum(tp) for x in (p.get("mpn", ""), p.get("supplier_code", "")))
        row(f"{e['id']}-PART", f"{e['id']} part number", ours, tp, same, f"{e['id']}: {ours}, NOT {tp}.")
        if same is False and tp:
            res.need_wiring_picture = res.need_wiring_picture or k == "housing"
        if k == "housing":
            t = e.get("terminal") or {}
            tt_ = str(te.get("terminal", "")).strip()
            ours = " / ".join(x for x in (t.get("mpn", ""), t.get("supplier_code", "")) if x)
            same = bool(tt_) and any(alnum(x) and alnum(x) in alnum(tt_) for x in (t.get("mpn", ""), t.get("supplier_code", "")))
            row(f"{e['id']}-TERM", f"{e['id']} terminal", ours, tt_, same, f"{e['id']} terminal: {ours}, NOT {tt_}.")
            rng = re.findall(r"\d+", str(te.get("terminal_awg", "")))
            if len(rng) >= 2:
                lo, hi = sorted((int(rng[0]), int(rng[1])))
                drawn = sorted({int(w.get("awg")) for w in (sd.get("wire") or []) if not blank(w.get("awg"))
                                and e["id"] in (cc.split_ref(w.get("from", ""))[0], cc.split_ref(w.get("to", ""))[0])})
                bad = [g for g in drawn if not lo <= g <= hi]
                if not drawn:
                    rows.add(f"{cid}-{e['id']}-RANGE", sec, f"{e['id']} terminal range against the drawn gauge", f"range {lo}-{hi} AWG, no drawn gauge read",
                             "the drawn gauge is inside the printed range", "could_not_run")
                else:
                    rows.add(f"{cid}-{e['id']}-RANGE", sec, f"{e['id']} terminal range against the drawn gauge",
                             f"drawn {drawn} AWG, terminal range {lo}-{hi} AWG" + (": OUTSIDE the range" if bad else ""),
                             "the drawn gauge is inside the printed range", "fail" if bad else "pass")
            else:
                rows.add(f"{cid}-{e['id']}-RANGE", sec, f"{e['id']} terminal range against the drawn gauge", "range not read",
                         "the drawn gauge is inside the printed range", "could_not_run")
        if cable_check.is_angled(e):
            ex = str(te.get("exit", "")).strip().lower()
            want = str(e.get("exit", "")).strip().lower()
            row(f"{e['id']}-EXIT", f"{e['id']} cable exit of the angled plug", want, ex, ex == want,
                f"{e['id']}: cable leaves {want.upper()}, NOT {ex.upper()}.")
            if ex and ex != want:
                res.need_orientation = e["id"]
    # wires
    ours_w = c.get("wires") or []
    theirs_w = [w for w in (sd.get("wire") or []) if not blank(w.get("from")) or not blank(w.get("to"))]
    if ours_w:
        first = c["ends"][0]["id"]

        def keyed(ws):
            out = {}
            for w in ws:
                a, b = str(w.get("from", "")).strip(), str(w.get("to", "")).strip()
                if cc.split_ref(a)[0] != first and cc.split_ref(b)[0] == first:
                    a, b = b, a
                out.setdefault(a, []).append((b, str(w.get("colour", "")).strip().lower(), w.get("awg")))
            return out

        ko, kt = keyed(ours_w), keyed(theirs_w)
        wiring_bad = False
        if not theirs_w:
            for a in ko:
                rows.add(f"{cid}-WIRE-{a}", sec, f"wire at {a}", "not read", "position, colour and gauge as in cables.json", "could_not_run")
        else:
            for a, lst in ko.items():
                b, col, awg = lst[0]
                got = kt.get(a)
                if not got:
                    rows.add(f"{cid}-WIRE-{a}", sec, f"wire at {a}", f"differs: ours {a} -> {b} {col} {awg} AWG, theirs: no wire at {a}", "as in cables.json", "fail")
                    wiring_bad = True
                    continue
                tb, tcol, tawg = got[0]
                diffs = []
                if tb != b:
                    diffs.append(f"goes to {tb}, ours {b}")
                    wiring_bad = True
                if tcol and tcol != col:
                    diffs.append(f"colour {tcol}, ours {col}")
                    wiring_bad = True
                if not blank(tawg) and awg is not None and int(tawg) != int(awg):
                    diffs.append(f"{int(tawg)} AWG, ours {int(awg)} AWG")
                unread = (not tcol) or blank(tawg)
                if diffs:
                    rows.add(f"{cid}-WIRE-{a}", sec, f"wire at {a}", "differs: " + "; ".join(diffs), "position, colour and gauge as in cables.json", "fail")
                elif unread:
                    rows.add(f"{cid}-WIRE-{a}", sec, f"wire at {a}", "colour or gauge not read", "position, colour and gauge as in cables.json", "could_not_run")
                else:
                    rows.add(f"{cid}-WIRE-{a}", sec, f"wire at {a}", f"match: {a} -> {b} {col} {int(awg)} AWG", "as in cables.json", "pass")
            extra = [a for a in kt if a not in ko]
            # positions we keep EMPTY at any end, used by them
            empties = []
            for e in c.get("ends", []):
                for pos in cc.empty_positions(e):
                    ref = f"{e['id']}.{pos}"
                    if any(ref in (str(w.get("from", "")).strip(), str(w.get("to", "")).strip()) for w in theirs_w):
                        empties.append(ref)
            if extra or empties:
                wiring_bad = True
                rows.add(f"{cid}-WIRE-EXTRA", sec, "no wire where we have none", f"differs: theirs has a wire at {', '.join(sorted(set(extra + empties)))}",
                         "EMPTY positions stay empty; no added wire", "fail")
            else:
                rows.add(f"{cid}-WIRE-EXTRA", sec, "no wire where we have none", f"match: {len(theirs_w)} wires, EMPTY positions empty", "EMPTY positions stay empty", "pass")
            awg_o = sorted({int(w["awg"]) for w in ours_w if isinstance(w.get("awg"), (int, float))})
            awg_t = sorted({int(w["awg"]) for w in theirs_w if not blank(w.get("awg"))})
            if awg_t and awg_o and awg_t != awg_o:
                res.lines.append(f"Wire {'/'.join(map(str, awg_o))} AWG, NOT {'/'.join(map(str, awg_t))} AWG.")
            if wiring_bad:
                res.need_wiring_picture = True
                second = [e["id"] for e in c["ends"][1:]]
                parts = []
                for w in sorted(ours_w, key=lambda w: (cc.split_ref(w["from"])[0], cc.split_ref(w["from"])[1] if isinstance(cc.split_ref(w["from"])[1], int) else 0)):
                    fa, fb = cc.split_ref(w["from"]), cc.split_ref(w["to"])
                    parts.append(f"{fa[1]}-{fb[1] if len(second) == 1 else w['to']} {w.get('colour', '')}")
                emp = [f"{e['id']} position {', '.join(map(str, cc.empty_positions(e)))} EMPTY" for e in c["ends"] if cc.empty_positions(e)]
                theirs_s = ", ".join(f"{cc.split_ref(a)[1]}-{(cc.split_ref(l[0][0])[1] if len(second) == 1 else l[0][0])}" for a, l in sorted(kt.items()))
                res.lines.insert(0, f"Wiring {first}-{second[0] if len(second) == 1 else 'ends'} per our picture: " + ", ".join(parts) + ("; " + "; ".join(emp) if emp else "")
                                 + f". NOT {theirs_s}.")
    # pin-1 mark and extras
    has_h = any(e.get("kind") == "housing" for e in c.get("ends", []))
    p1 = str(sd.get("pin1_mark", "")).strip().lower()
    if not has_h:
        rows.add(f"{cid}-PIN1", sec, "pin-1 mark drawn", "no housing", "a mark at position 1 of every housing", "na")
    elif p1 in ("yes", "y", "true"):
        rows.add(f"{cid}-PIN1", sec, "pin-1 mark drawn", "match: drawn", "a mark at position 1 of every housing", "pass")
    elif p1 in ("no", "n", "false"):
        rows.add(f"{cid}-PIN1", sec, "pin-1 mark drawn", "differs: ours a mark at position 1, theirs none", "a mark at position 1 of every housing", "fail")
        res.lines.append("Mark position 1 of each housing with a dot.")
    else:
        rows.add(f"{cid}-PIN1", sec, "pin-1 mark drawn", "not read", "a mark at position 1 of every housing", "could_not_run")
    ex = str(sd.get("extras", "")).strip()
    if not ex:
        rows.add(f"{cid}-EXTRAS", sec, "nothing drawn that was not ordered", "not read", "write \"none\" or what is drawn", "could_not_run")
    elif ex.lower() in ("none", "no", "nothing"):
        rows.add(f"{cid}-EXTRAS", sec, "nothing drawn that was not ordered", "match: none", "nothing added", "pass")
    else:
        rows.add(f"{cid}-EXTRAS", sec, "nothing drawn that was not ordered", f"differs: theirs adds {ex}", "nothing added", "fail")
        res.lines.append(f"NO {ex}.")
    # pre-filled values
    if pre:
        rows.add(f"{cid}-EYE", sec, "pre-filled values verified by eye", f"{', '.join(sorted(pre))}: " + ("verified" if eye else VERIFY),
                 "verified_by_eye = true after comparing with the drawing itself", "pass" if eye else "could_not_run")
    return res


def revise_note(res: Result, line: str, limit: int) -> tuple[str, bool]:
    head = f"Line {line or '?'} ({res.cid}):"
    body = " ".join(f"{i}. {ln}" for i, ln in enumerate(res.lines, 1))
    note = f"{head} {body}".strip()
    return note, len(note) <= limit


def run(job, a) -> tuple[mc.Rows, list, list]:
    data, cpath = cc.load_cables(job, a.cables)
    cap, cap_path = cc.capability(job, a.sheet)
    limit, lwhy = cc.limit(cap, "revise_chars", 500)
    cfg = cc.cable_cfg(job)
    deny = list(cfg.get("deny") or []) + ([job.cfg["project"]["name"]] if str(job.cfg["project"].get("name", "")).strip() else [])
    d = a.dir or os.path.join(job.project, "orders", "production_drawings")
    files = sorted(glob.glob(os.path.join(d, "supplier_drawing_*.toml")))
    by_id = {c.get("id"): c for c in data["cables"]}
    sent = parse_date(a.sent) if a.sent else None
    if a.sent and sent is None:
        raise mc.MechError(f"--sent {a.sent}: not a date (YYYY-MM-DD)")
    rows = mc.Rows()
    outd = os.path.join(job.out, "cables", "production")
    made, seen = [], set()
    md = ["# Production drawing check", "", "| Our id | Supplier line | Verdict | Differs | Not read | Note (characters) | Picture to attach |", "|---|---|---|---|---|---|---|"]
    notes_md = []
    for f in files:
        sd = mc.load_toml(f)
        cid = str(sd.get("cable", "")) or os.path.basename(f)[len("supplier_drawing_"):-5]
        if a.only and cid != a.only:
            continue
        c = by_id.get(cid)
        if c is None:
            rows.add(f"{cid}-FILE", f"cable {cid}", "the file belongs to a cable", f"{os.path.basename(f)}: no cable '{cid}' in cables.json", "the id of a cable", "fail")
            continue
        seen.add(cid)
        n0 = len(rows.rows)
        res = check_one(c, sd, rows, sent, f)
        mine = rows.rows[n0:]
        nf = sum(1 for r in mine if r["verdict"] == "fail")
        nu = sum(1 for r in mine if r["verdict"] == "could_not_run")
        line = str(sd.get("line", "")).strip()
        pic = ""
        if nf:
            note, fits = revise_note(res, line, int(limit))
            bad = cc.text_findings(note, deny)
            pics = os.path.join(job.out, "cables", "pictures")
            if res.need_wiring_picture:
                pic = os.path.join(pics, f"{cid}_wiring.png")
            elif res.need_orientation:
                pic = os.path.join(pics, f"{cid}_{res.need_orientation}_orientation.png")
            p = os.path.join(outd, f"REVISE_{cid}.txt")
            mc.atomic_write(p, note + "\n")
            made.append(p)
            rows.add(f"{cid}-NOTE", f"cable {cid}", "revise note", f"{len(note)} characters" + ("" if fits else ": too long, shorten by hand") + ("; " + "; ".join(bad) if bad else ""),
                     f"<= {limit} characters ({lwhy}); no question or request word", "pass" if fits and not bad else "fail")
            if pic:
                rows.add(f"{cid}-PICTURE", f"cable {cid}", "the one picture to attach", os.path.basename(pic) + ("" if os.path.isfile(pic) else " (NOT MADE: run cable_drawings.py)"),
                         "one picture per revise note", "pass" if os.path.isfile(pic) else "could_not_run")
            verdict = "REVISE"
        else:
            verdict = "CONFIRM" if nu == 0 else "NOT DECIDED (fields not read)"
            old = os.path.join(outd, f"REVISE_{cid}.txt")
            if os.path.isfile(old):
                os.remove(old)
        rows.add(f"{cid}-VERDICT", f"cable {cid}", "verdict", verdict + (f": {nf} field(s) differ, {nu} not read" if verdict != "CONFIRM" else ": every field matches"),
                 "CONFIRM only when every row matches", "pass" if verdict == "CONFIRM" else ("fail" if nf else "could_not_run"))
        md.append(f"| {cid} | {line or '(not recorded)'} | **{verdict}** | {nf} | {nu} | "
                  + (f"`REVISE_{cid}.txt` ({len(revise_note(res, line, int(limit))[0])} of {limit})" if nf else "-") + f" | {os.path.basename(pic) if pic else '-'} |")
        if nf:
            notes_md += ["", f"Revise note for line {line or '?'} ({cid}):", "", "```", revise_note(res, line, int(limit))[0], "```"]
    for cid in by_id:
        if cid not in seen and (not a.only or cid == a.only):
            rows.add(f"{cid}-VERDICT", f"cable {cid}", "verdict", f"no supplier_drawing_{cid}.toml in {os.path.relpath(d, job.project).replace(os.sep, '/')}: the drawing was not read", "every cable's production drawing is read",
                     "could_not_run")
    md += notes_md
    md += ["", "Confirm only a line whose verdict is CONFIRM; send every REVISE note of the order in one round, one picture per cable.", ""]
    p = os.path.join(outd, "PRODUCTION_DRAWING_CHECK.md")
    mc.atomic_write(p, "\n".join(md))
    made.append(p)
    return rows, [cpath] + files + ([cap_path] if cap else []), made


def write_template(job, a) -> int:
    data, _ = cc.load_cables(job, a.cables)
    c = next((x for x in data["cables"] if x.get("id") == a.template), None)
    if c is None:
        print(f"could not run: no cable '{a.template}' in cables.json")
        return 2
    pre = None
    if a.pdf:
        if not os.path.isfile(a.pdf):
            print("could not run: no PDF at", a.pdf)
            return 2
        text = pdf_text(a.pdf)
        if text is None:
            print("  note: PyMuPDF is missing, nothing pre-filled")
        else:
            pre = prefill(c, text)
            print(f"  pre-filled from the PDF text ({VERIFY}): {', '.join(sorted(pre)) or 'nothing found'}")
    d = a.dir or os.path.join(job.project, "orders", "production_drawings")
    p = os.path.join(d, f"supplier_drawing_{a.template}.toml")
    if os.path.isfile(p) and not a.force:
        print(f"could not run: {p} exists (use --force to overwrite)")
        return 2
    mc.atomic_write(p, template(c, pre, os.path.basename(a.pdf) if a.pdf else ""))
    print("  wrote", p)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Supplier's production drawing checked field by field.", epilog="Exit codes: 0 all match, 1 differs, 2 could not run / not read.")
    mc.add_std_args(ap)
    ap.add_argument("--cables", help="the cable data file")
    ap.add_argument("--sheet", help="capability sheet of the cable supplier")
    ap.add_argument("--dir", help="folder of the supplier_drawing_<id>.toml files (default <project>/orders/production_drawings)")
    ap.add_argument("--template", metavar="ID", help="write an empty supplier_drawing_<ID>.toml to fill while reading their drawing")
    ap.add_argument("--pdf", help="with --template: their PDF, to pre-fill what its text layer holds")
    ap.add_argument("--force", action="store_true", help="with --template: overwrite an existing file")
    ap.add_argument("--only", help="one cable id")
    ap.add_argument("--sent", help="date of our last revise note (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    try:
        job = mc.resolve(a)
        if a.template:
            return write_template(job, a)
        rows, inputs, made = run(job, a)
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    rows.print_table(only_bad=True)
    rows.write(job.out, "production_drawing_check.py", inputs)
    for p in made:
        print("  wrote", p)
    print(rows.headline())
    return rows.exit_code()


if __name__ == "__main__":
    sys.exit(main())
