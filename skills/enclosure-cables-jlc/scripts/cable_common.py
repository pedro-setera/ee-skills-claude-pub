"""Shared helpers of the cable scripts: the cable data file, the cable type table, the supplier's capability sheet, text rules.

What it does
    - `load_cables(job)` / `save_cables(path, data)`: read and write `cables/cables.json` (the single cable data file).
      `save_cables` writes ONLY when the content changes (returns True when it wrote): a run that finds nothing new leaves the
      file, its checksum and its time stamp alone, so a build that lists the file as an input is not made stale by a re-run.
    - `cable_cfg(job)`: the `[cables]` keys of mech.toml merged over the defaults below.
    - `capability(job)`: the cable supplier's capability sheet (`suppliers/<id>.capability.toml`) or None.
    - `end_of`, `split_ref`, `end_positions`, `wires_at`, `empty_positions`: reading ends and wires.
    - `min_bend(cable, types)`: the smallest allowed bend radius of a cable from its type (bundle, coax, network ...).
    - `allowance(cable, cfg)`: the length added to the measured route, by how the ends are finished.
    - `standard_tolerance(cap, cfg)`: the supplier's standard length tolerance (the narrowest of `[tolerance] standard_mm`):
      what a drawing may ask for without being "tighter than the standard".
    - `design_tolerance(cap, cfg)`: the tolerance the REACH and SBEND checks design for: `[tolerance] design_mm` when the sheet has
      it, else the WIDEST of `standard_mm`. The supplier may draw any of its standard tolerances whatever was asked (asked
      tighter, drawn at +-5), so a design that only works at +-3 is not safe.
    - `text_findings(text, deny)`: question marks, request words and product-looking names in a text.
    - `placeholder_in(text)`: the placeholder phrase ("TBD", "UNKNOWN", "to verify", "to read" ...) found in a text, or None;
      `code_problem(value)`: why a part number or supplier code is not usable ("empty", "placeholder 'TBD'"), or None.
    - `product_word_findings(text)`: the words "board", "PCB", "module" in a text that reaches the supplier (a cable's name and
      label may carry End A/B, P1/P2 and part numbers only, never the name of a part of the product).
    - `label_position(cable)`: where the cable's label is drawn, from `label_position` ("15 mm from P1", "30 % of the length
      from P2", "middle"): (end id, fraction of the length from that end, text) or (None, None, why it is unreadable).
    - `non_default_lines(cable)`: every non-default as "X, NOT Y".
    No command line (`python -I cable_common.py --selftest` runs a quick self test).

Why it exists (the real failure, told without names)
    The cable drawings, the order form values and the check of the supplier's own drawings were typed three times from
    three places; a gauge in the form differed from the gauge on the drawing. One data file read by one loader ends that.

Usage (from a sibling script)
    import cable_common as cc
    data, path = cc.load_cables(job);  cfg = cc.cable_cfg(job);  cap, cap_path = cc.capability(job)

Config keys (mech.toml)
    [cables] file = "cables/cables.json", routes = "cables/routes.toml", second = "cables/second_measure.toml",
             supplier = "lcsc-cable" (sheet: suppliers/<supplier>.capability.toml, or sheet = "path"),
             min_straight_mm = 3.0, arrive_tol_mm = 0.5, arrive_tol_deg = 2.0, clearance_mm = 1.0, cable_gap_mm = 0.0,
             compare_max_diff_mm = 2.0, allowance_crimped_mm = 2.0, allowance_trimmed_mm = 10.0, tol_mm = 3.0,
             label_max_chars = 24, show_signals = false, deny = ["word", ...], skip_solids = ["name*"]
    [cables.types.<name>] od_mm, min_bend_r, min_bend_x_od      (a cable type; cables.json "cable_types" wins)
    [project] company, rev

Exit codes
    none (library); the self test exits 0 or 1
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import copy
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402

DEFAULTS = {
    "file": "cables/cables.json", "routes": "cables/routes.toml", "second": "cables/second_measure.toml",
    "supplier": "lcsc-cable", "sheet": "",
    "min_straight_mm": 3.0, "arrive_tol_mm": 0.5, "arrive_tol_deg": 2.0, "clearance_mm": 1.0, "cable_gap_mm": 0.0,
    "compare_max_diff_mm": 2.0, "allowance_crimped_mm": 2.0, "allowance_trimmed_mm": 10.0, "tol_mm": 3.0,
    "label_max_chars": 24, "show_signals": False, "deny": [], "skip_solids": [], "types": {},
}

# cable types: the smallest bend radius as a fixed value or as a multiple of the outer diameter.
# "coax" has no value on purpose: it comes from the cable's datasheet (route.min_bend_r in cables.json).
BUILTIN_TYPES = {
    "wire_bundle": {"min_bend_r": 5.0},          # loose hook-up wires of a harness
    "network": {"min_bend_x_od": 4.0},           # twisted-pair network cable: 4 x outer diameter
    "flat": {"min_bend_x_od": 5.0},
    "coax": {},
}
TYPE_OF_KIND = {"harness": "wire_bundle", "ethernet": "network", "rf": "coax", "other": "wire_bundle"}

# insulated wire outer diameter by AWG (typical hook-up wire, mm): used only when route.od_mm is not given
WIRE_OD = {18: 2.1, 20: 1.8, 22: 1.6, 24: 1.4, 26: 1.3, 28: 1.2, 30: 1.1}

COLOURS = {"red": "#d62222", "black": "#151515", "white": "#f4f4f4", "yellow": "#f2d21b", "green": "#1e9a3c",
           "blue": "#1f5fd0", "orange": "#f08a1c", "brown": "#7a4a22", "grey": "#8c8c8c", "gray": "#8c8c8c",
           "violet": "#7d3fc0", "purple": "#7d3fc0", "pink": "#f08cb4", "silver": "#c8c8c8", "natural": "#e6dfc8"}

REQUEST_WORDS = [
    ("question mark", re.compile(r"\?")),
    ("request word 'please'", re.compile(r"\bplease\b|\bkindly\b", re.I)),
    ("request word 'if possible'", re.compile(r"\bif (?:it is )?possible\b|\bif you can\b|\bfallback\b|\bfall back\b|\bor similar\b|"
                                              r"\bor equivalent\b|\bpreferabl[ey]\b|\bideally\b", re.I)),
    ("question to the supplier", re.compile(r"\b(?:confirm|advise|let us know|can you|could you)\b", re.I)),
    ("alternative offered", re.compile(r"\botherwise\b|\bif not\b|\balternativ", re.I)),
    ("loose extra", re.compile(r"\bloose\b|\bspare\b|\bextra (?:pcs|pieces|parts)\b", re.I)),
]


def cable_cfg(job) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    for k, v in (job.cfg.get("cables") or {}).items():
        cfg[k] = v
    return cfg


def cables_path(job) -> str:
    p = (job.cfg.get("cables") or {}).get("file") or job.cfg["paths"].get("cables") or DEFAULTS["file"]
    return mc.rel_to_project(job.cfg, p)


def load_cables(job, path: str | None = None):
    p = path or cables_path(job)
    if not os.path.isfile(p):
        raise mc.MechError(f"no cable data file at {p}")
    try:
        data = mc.load_json(p)
    except json.JSONDecodeError as e:
        raise mc.MechError(f"{p}: not valid JSON: {e}")
    if not isinstance(data, dict) or not isinstance(data.get("cables"), list):
        raise mc.MechError(f'{p}: expected {{"cables": [...]}}')
    return data, p


def save_cables(path: str, data: dict) -> bool:
    """Write the cable file only when its content changes; True when it was written. Compares the new JSON text with the
    file's (and, for a file with the same content in another layout, the parsed content), so an unchanged result keeps the
    file byte-identical and its modification time as it was."""
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    try:
        with open(path, encoding="utf-8", newline="") as f:
            old = f.read()
    except OSError:
        old = None
    if old is not None:
        if old == text:
            return False
        try:
            if json.loads(old) == data:
                return False
        except ValueError:
            pass
    mc.atomic_write(path, text)
    return True


def capability(job, sheet: str | None = None):
    """(sheet dict, path) or (None, tried path)."""
    cfg = cable_cfg(job)
    p = sheet or cfg.get("sheet") or os.path.join("suppliers", f"{cfg['supplier']}.capability.toml")
    p = mc.rel_to_project(job.cfg, p)
    if not os.path.isfile(p):
        return None, p
    return mc.load_toml(p), p


def standard_tolerance(cap, cfg) -> tuple[float, str]:
    """(mm, where it came from)."""
    if cap:
        t = (cap.get("tolerance") or {}).get("standard_mm")
        if isinstance(t, list) and t:
            return float(min(t)), "capability sheet"
        if isinstance(t, (int, float)):
            return float(t), "capability sheet"
    return float(cfg["tol_mm"]), "default (no capability sheet value)"


def design_tolerance(cap, cfg) -> tuple[float, str]:
    """(mm, where it came from): the tolerance the checks design for. `[tolerance] design_mm` of the sheet when present, else
    the widest value of `[tolerance] standard_mm`, else the `tol_mm` default."""
    if cap:
        tol = cap.get("tolerance") or {}
        d = tol.get("design_mm")
        if isinstance(d, (int, float)) and not isinstance(d, bool) and d > 0:
            return float(d), "capability sheet design_mm"
        t = tol.get("standard_mm")
        if isinstance(t, list) and t:
            return float(max(t)), "widest standard_mm of the capability sheet"
        if isinstance(t, (int, float)):
            return float(t), "capability sheet"
    return float(cfg["tol_mm"]), "default (no capability sheet value)"


def limit(cap, key: str, default):
    if cap and key in (cap.get("limits") or {}):
        return cap["limits"][key], "capability sheet"
    return default, "default (not on the capability sheet)"


# ---------------------------------------------------------------- ends and wires -------------------------------------
def split_ref(ref: str):
    """'P1.3' -> ('P1', 3); 'P2' -> ('P2', None)."""
    ref = str(ref).strip()
    if "." in ref:
        a, b = ref.split(".", 1)
        try:
            return a, int(b)
        except ValueError:
            return a, b
    return ref, None


def end_of(cable: dict, end_id: str):
    for e in cable.get("ends", []):
        if e.get("id") == end_id:
            return e
    return None


def end_positions(end: dict) -> int:
    return int(((end or {}).get("part") or {}).get("positions") or 0)


def end_rows(end: dict) -> int:
    return int(((end or {}).get("part") or {}).get("rows") or 1)


def wires_at(cable: dict, end_id: str) -> dict:
    """position -> list of wires landing there, for one end."""
    out: dict = {}
    for w in cable.get("wires", []):
        for side in ("from", "to"):
            e, pos = split_ref(w.get(side, ""))
            if e == end_id:
                out.setdefault(pos, []).append(w)
    return out


def empty_positions(end: dict) -> list:
    return [int(x) for x in (end.get("empty") or [])]


def is_trimmed(end: dict) -> bool:
    """An end that is cut to fit and soldered at assembly."""
    if "trim_at_assembly" in end:
        return bool(end["trim_at_assembly"])
    return end.get("kind") == "tinned"


def allowance(cable: dict, cfg: dict) -> tuple[float, str]:
    r = cable.get("route") or {}
    if isinstance(r.get("allowance_mm"), (int, float)):
        return float(r["allowance_mm"]), "route.allowance_mm"
    if any(is_trimmed(e) for e in cable.get("ends", [])):
        return float(cfg["allowance_trimmed_mm"]), "an end trimmed and soldered at assembly"
    return float(cfg["allowance_crimped_mm"]), "fixed at both ends"


def cable_types(data: dict, cfg: dict) -> dict:
    t = copy.deepcopy(BUILTIN_TYPES)
    for src in (cfg.get("types") or {}, data.get("cable_types") or {}):
        for k, v in src.items():
            t.setdefault(k, {})
            t[k].update(v)
    return t


def cable_type(cable: dict) -> str:
    return (cable.get("route") or {}).get("cable_type") or TYPE_OF_KIND.get(cable.get("type", "other"), "wire_bundle")


def cable_od(cable: dict, types: dict):
    """Outer diameter of the swept cable (mm) and where it came from, or (None, why)."""
    r = cable.get("route") or {}
    if isinstance(r.get("od_mm"), (int, float)):
        return float(r["od_mm"]), "route.od_mm"
    t = types.get(cable_type(cable), {})
    if isinstance(t.get("od_mm"), (int, float)):
        return float(t["od_mm"]), "cable type"
    ws = cable.get("wires") or []
    if ws:
        ods = [WIRE_OD.get(int(w.get("awg") or 0)) for w in ws]
        if all(ods):
            n = len(ods)
            d = max(ods)
            return round(d * (1.0 if n == 1 else 1.2 * n ** 0.5), 2), f"{n} wire(s) of {d} mm (typical insulation diameter)"
    return None, "no route.od_mm and no cable type diameter"


def min_bend(cable: dict, types: dict):
    """(radius mm, rule text) or (None, why)."""
    r = cable.get("route") or {}
    if isinstance(r.get("min_bend_r"), (int, float)):
        return float(r["min_bend_r"]), "route.min_bend_r (datasheet)"
    name = cable_type(cable)
    t = types.get(name)
    if t is None:
        return None, f"cable type '{name}' is not in the type table"
    if isinstance(t.get("min_bend_r"), (int, float)):
        return float(t["min_bend_r"]), f"type {name}"
    if isinstance(t.get("min_bend_x_od"), (int, float)):
        od, _ = cable_od(cable, types)
        if od is None:
            return None, f"type {name} is {t['min_bend_x_od']:g} x OD and the cable has no od_mm"
        return float(t["min_bend_x_od"]) * od, f"type {name}: {t['min_bend_x_od']:g} x OD {od:g}"
    return None, f"type {name} has no value: take the minimum bend radius from the cable's datasheet into route.min_bend_r"


# ---------------------------------------------------------------- text ----------------------------------------------
def text_findings(text: str, deny=()) -> list[str]:
    """What is wrong in a text that goes to the supplier (empty list = clean)."""
    out = []
    if not text:
        return out
    for name, rx in REQUEST_WORDS:
        m = rx.search(text)
        if m:
            out.append(f"{name}: '{m.group(0)}'")
    low = text.lower()
    for d in deny or ():
        d = str(d).strip()
        if d and re.search(r"(?<![a-z0-9])" + re.escape(d.lower()) + r"(?![a-z0-9])", low):
            out.append(f"name on the deny list: '{d}'")
    return out


PLACEHOLDER_RX = re.compile(
    r"\b(?:tbd|tbc|tba|unknown|unspecified|placeholder|todo|fixme|xxx+)\b"
    r"|\bto (?:be )?(?:verif(?:y|ied)|read|confirm(?:ed)?|decided?|determined?|checked|filled(?: in)?)\b"
    r"|\bfrom memory\b|\?\?+", re.I)
EMPTY_CODES = {"", "-", "--", "---", "?", "x", "xx", "n/a", "na", "n.a.", "none", "null", "nil", "tbd", "tbc", "tba", "unknown", "todo"}
PRODUCT_RX = re.compile(r"\b(board|pcb|module)s?\b", re.I)


def placeholder_in(text) -> str | None:
    """The placeholder phrase in a text ("TBD", "UNKNOWN", "to verify", "to read" ...), or None."""
    m = PLACEHOLDER_RX.search(str(text or ""))
    return m.group(0) if m else None


def code_problem(value) -> str | None:
    """Why a part number or a supplier code cannot be used: "empty" or "placeholder 'TBD'"; None when it looks like a code."""
    v = str(value if value is not None else "").strip()
    if not v:
        return "is empty"
    if v.lower().strip(" .:;") in EMPTY_CODES or re.fullmatch(r"[-_?.x\s]+", v, re.I):
        return f"is a placeholder ('{v}')"
    ph = placeholder_in(v)
    return f"is a placeholder ('{ph}')" if ph else None


def product_word_findings(text) -> list[str]:
    """The words board / PCB / module in a text (name or label of a cable): the supplier gets End A/B, P1/P2 and part numbers only."""
    return [f"the word '{m.group(0)}' names a part of the product" for m in PRODUCT_RX.finditer(str(text or ""))][:1]


LABEL_POS_RX = re.compile(
    r"^\s*(?:(?P<mid>(?:at\s+)?(?:the\s+)?(?:middle|centre|center)(?:\s+of\s+the\s+(?:cable|length))?)"
    r"|(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>mm|%|percent)\s*(?:of\s+the\s+(?:cable\s+)?length\s+)?from\s+(?:the\s+)?(?P<end>P[1-9]))\s*\.?\s*$", re.I)


def label_position(cable: dict):
    """Where the label sits on the cable, from `label_position`: (end id, fraction of the length counted from that end, text).
    Readable forms: "<n> mm from P1|P2", "<n> % of the length from P1|P2", "middle" (also "at the middle of the cable").
    An empty value gives the default (the first end, 30 %, text ""). An unreadable one (or a distance beyond the length)
    gives (None, None, the reason)."""
    ends = [e.get("id") for e in cable.get("ends", [])]
    first = ends[0] if ends else "P1"
    raw = str(cable.get("label_position", "") or "").strip()
    if not raw:
        return first, 0.30, ""
    m = LABEL_POS_RX.match(raw)
    if not m:
        return None, None, (f"label_position '{raw}' is not readable: write '<n> mm from P1' (or P2), '<n> % of the length from P1' "
                            "(or P2) or 'middle'")
    if m.group("mid"):
        return first, 0.5, raw
    end, n, unit = m.group("end").upper(), float(m.group("n")), m.group("unit").lower()
    if end not in ends[:2]:
        return None, None, f"label_position '{raw}' names {end}, which is not one of the two ends the length spans ({', '.join(map(str, ends[:2]))})"
    if unit == "mm":
        L = cable.get("length_mm")
        if not isinstance(L, (int, float)) or L <= 0:
            return None, None, f"label_position '{raw}' is in mm but the cable has no length_mm"
        if n > L:
            return None, None, f"label_position '{raw}' is beyond the cable's length of {fmt(L)} mm"
        return end, n / float(L), raw
    if n > 100:
        return None, None, f"label_position '{raw}' is above 100 %"
    return end, n / 100.0, raw


def non_default_lines(cable: dict) -> list[str]:
    out = []
    for nd in cable.get("non_defaults") or []:
        w, n = str(nd.get("want", "")).strip(), str(nd.get("not", "")).strip()
        if w and n:
            out.append(f"{w}, NOT {n}")
        elif w:
            out.append(w)
    return out


def supplier_texts(cable: dict, show_signals: bool = False) -> list[tuple[str, str]]:
    """(where, text) of every text of a cable that reaches the supplier."""
    out = [("name", cable.get("name", "")), ("label", cable.get("label", "")), ("label_position", cable.get("label_position", "")),
           ("length_def", cable.get("length_def", "")), ("cable_spec", cable.get("cable_spec", ""))]
    for i, nd in enumerate(cable.get("non_defaults") or []):
        out.append((f"non_defaults[{i}].want", str(nd.get("want", ""))))
        out.append((f"non_defaults[{i}].not", str(nd.get("not", ""))))
    for i, n in enumerate(cable.get("notes") or []):
        out.append((f"notes[{i}]", str(n)))
    for e in cable.get("ends", []):
        p = e.get("part") or {}
        for k in ("numbering", "description"):
            out.append((f"{e.get('id')}.part.{k}", str(p.get(k, "") or "")))
        out.append((f"{e.get('id')}.orientation", str(e.get("orientation", "") or "")))
        out.append((f"{e.get('id')}.name", str(e.get("name", "") or "")))
    for w in cable.get("wires", []):
        out.append((f"wire {w.get('from')} colour", str(w.get("colour", ""))))
        if show_signals:
            out.append((f"wire {w.get('from')} signal", str(w.get("signal", ""))))
    return [(a, b) for a, b in out if b]


def fmt(v: float, nd: int = 1) -> str:
    s = f"{v:.{nd}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _selftest() -> int:
    c = {"type": "harness", "wires": [{"from": "P1.1", "to": "P2.2", "awg": 24}, {"from": "P1.2", "to": "P2.1", "awg": 24}],
         "ends": [{"id": "P1", "kind": "housing", "part": {"positions": 3}}, {"id": "P2", "kind": "tinned"}], "route": {}}
    assert split_ref("P1.3") == ("P1", 3) and split_ref("P2") == ("P2", None)
    assert sorted(wires_at(c, "P1")) == [1, 2]
    assert allowance(c, DEFAULTS)[0] == 10.0
    t = cable_types({}, DEFAULTS)
    assert min_bend(c, t)[0] == 5.0
    assert min_bend({"type": "rf", "route": {}}, t)[0] is None
    assert min_bend({"type": "ethernet", "route": {"od_mm": 4.0}}, t)[0] == 16.0
    assert text_findings("Use blue wire?") and text_findings("please use blue") and not text_findings("Blue wire, NOT black")
    assert text_findings("the Acme box", ["acme"]) and not text_findings("the acmex box", ["acme"])
    assert placeholder_in("UNKNOWN: to read on the live page") and placeholder_in("maker part from memory") and not placeholder_in("SMA plug, solder")
    assert code_problem("") and code_problem("TBD") and code_problem("unknown") and code_problem("n/a") and code_problem(None) and not code_problem("C0000001")
    assert product_word_findings("Button board harness") and product_word_findings("PCB lead") and not product_word_findings("Sensor harness")
    pc = {"length_mm": 50, "ends": [{"id": "P1"}, {"id": "P2"}]}
    assert label_position(dict(pc, label_position="15 mm from P2")) == ("P2", 0.3, "15 mm from P2")
    assert label_position(dict(pc, label_position="middle"))[:2] == ("P1", 0.5) and label_position(dict(pc, label_position="somewhere near"))[0] is None
    assert design_tolerance({"tolerance": {"standard_mm": [3, 5]}}, DEFAULTS)[0] == 5.0
    assert design_tolerance({"tolerance": {"standard_mm": [3, 5], "design_mm": 4}}, DEFAULTS)[0] == 4.0
    assert design_tolerance(None, DEFAULTS)[0] == 3.0 and standard_tolerance({"tolerance": {"standard_mm": [3, 5]}}, DEFAULTS)[0] == 3.0
    print("cable_common selftest ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
