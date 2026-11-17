"""Production package for JLCPCB from a KiCad board: Gerbers, drill files, BOM, placement file, zip, checksums.

What it does
    From one board file, on private copies (the design folder is never written to):
      1. Gerbers of every copper layer of the board plus paste, silkscreen, mask and outline, and the Excellon
         drill files (plated and non-plated apart) with their drill maps, into <out>/jlc/gerbers/, and a zip of them.
      2. The placement file (CPL) in JLCPCB's upload layout, written from the derivation of jlc_rotations.py:
         rotation and origin of every part from JLCPCB's own footprint. It is written only when every part to
         place has a derived or declared rotation; then a second, fresh derivation is compared with the file.
      3. The BOM in JLCPCB's upload layout (Comment, Designator, Footprint, LCSC Part #) for exactly the parts of
         the placement file: unfitted (DNP) and hand-fitted parts are in neither.
      4. SHA-256 of the board and of every output, in manifest.json (and manifest.md for people), and of every
         input that drove the export: board.toml, the assembly BOM table, each JLCPCB footprint used for a
         rotation, the tools (this script, jlc_rotations.py, jlc_parts.py, kicad_io.py); with the KiCad version
         and the export options. The manifest names exactly which inputs produced the files.
      5. The privacy scan (privacy_scan.py) over every output: no user name, home path or host name leaves the PC.
      6. The freshness gate: no output is older than the board, and the board did not change during the export.
    --check runs only the gate on an existing package: every file of the manifest is there with its checksum,
    none is older than the board, the board is still the one the package was made from, and every input and the
    KiCad version are unchanged (each change is named). It refuses a preview package.
    --preview writes the provisional package for JLCPCB's placement preview into <out>/jlc_preview/, only when the
    one reason for a missing rotation is the unconfirmed bottom-side convention (jlc_rotations.py): every file is
    named PREVIEW-ONLY, the manifest says PREVIEW ONLY - NOT FOR ORDER and lists the waiting parts with their
    candidate angles and the bottom-side checksum to record after the look. Upload it for the preview only,
    record the confirmation in board.toml (phase 11 step 14b), never save it to the cart (remove one made by mistake), export again. The normal export never writes it.

Why it exists (real failures, told without names)
    - Parts that were to be fitted by hand stayed in the placement file and were pasted and placed.
    - Rotations from KiCad's own position file would have turned every three-pin transistor of a board.
    - A reviewed file was changed after the review; its package was stale and nobody saw it.
    - Exported files can carry the system user name in their headers, and such files are easily uploaded to a
      supplier unread.
    - Checks ran on design settings while the exported files were different: what is checked and uploaded must be
      the files of this folder, with their checksums.

Usage
    python -I fab_package.py --project <hardware/board folder>          package in <project>/out/jlc/
    python -I fab_package.py <board.kicad_pcb> --out <folder> [--vendor DIR] [--bom FILE]
                                                                        any KiCad board; package in <folder>/jlc/
    python -I fab_package.py --project <...> --check                    the freshness gate alone
    python -I fab_package.py --project <...> --preview                  preview-only package in <project>/out/jlc_preview/
    python -I fab_package.py --project <...> --out out/panel --name <name>-panel --bom out/panel/<name>-panel-bom.csv out/panel/board/<name>-panel.kicad_pcb
                                                                        the panel's package in out/panel/jlc/ (each copy reads board.toml as its board part)

    Works on any KiCad board, any layer count. Without LCSC numbers or cached JLCPCB footprints the Gerbers,
    drill files and zip are still made; the BOM lists the lines without a number as findings and the placement
    file is not written (nothing is assumed): the result is FAIL with the reasons.
    All coordinates are KiCad's page frame with Y up, the same in Gerbers, drill files and placement file.

board.toml keys (all optional; without a board.toml the defaults apply and are printed)
    [fab]
    name = "myboard"               # base name of the outputs (default: the board file's name)
    subtract_soldermask = false    # true: clip the silkscreen where the solder mask is open (KiCad's plot option)
    extra_layers = []              # more layers to plot, by KiCad's layer names
    [bom] assembly_file, lcsc_field, hand_fit, dnp, ignore     as in jlc_rotations.py and jlc_parts.py
    [rotations] ...                                            as in jlc_rotations.py
    [privacy] patterns, literals, allow                        as in privacy_scan.py

Exit codes
    0  PASS: complete package, placement file equal to a fresh derivation, privacy scan clean, everything fresh
       (--preview: the preview package was written; it is never an order package)
    1  FAIL: a part without a rotation (no placement file), a BOM line without an LCSC number, a privacy hit, a
       stale or changed file or input (--check), a preview package given to --check, a refused --preview
    2  CANNOT RUN: KiCad not found, unreadable board, an export that failed, the results folder inside the design
       folder, no manifest to check. Never a pass.

Not checked here (other scripts do): copper to board edge on the Gerbers (edge_check.py), DRC (drc_run.py),
stock (jlc_parts.py), JLCPCB's current rules (the supplier-rules review), the placement preview on the order page.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import csv
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import privacy_scan  # noqa: E402
from jlc_parts import LCSC_FIELDS, MPN_FIELDS, Bom, natural, read_csv  # noqa: E402
from jlc_parts import CannotRun as _BomError  # noqa: E402

ROT_TIMEOUT = 1800                  # s: one run of jlc_rotations.py
_GERBER_FILE = re.compile(r"\.(g[tbm][lpos0-9]|g\d+|gbr|gbrjob|drl)$", re.I)
NON_COPPER = ["F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "Edge.Cuts"]
TOOLS = ("fab_package.py", "jlc_rotations.py", "jlc_parts.py", "kicad_io.py")   # the code that shapes the outputs
PREVIEW = "PREVIEW-ONLY"            # in the name of every file of a preview package
PREVIEW_PURPOSE = "PREVIEW ONLY - NOT FOR ORDER"


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _mtime(path: str) -> str:
    return datetime.datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat(timespec="seconds")


def copper_layers(board: str) -> list[str]:
    """The copper layers of a board file, top to bottom, read from its (layers ...) list."""
    with open(board, encoding="utf-8", errors="replace") as f:
        head = f.read(200000)
    m = re.search(r"\(layers\b", head)
    if not m:
        raise kicad_io.KicadIOError(f"{os.path.basename(board)}: no layer list found (is it a KiCad board file?)")
    depth, i = 0, m.start()
    while i < len(head):
        if head[i] == "(":
            depth += 1
        elif head[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    names = re.findall(r'"((?:F|B|In\d+)\.Cu)"', head[m.start():i])
    inner = sorted((n for n in names if n.startswith("In")), key=lambda n: int(n[2:-3]))
    out = (["F.Cu"] if "F.Cu" in names else []) + inner + (["B.Cu"] if "B.Cu" in names else [])
    if not out:
        raise kicad_io.KicadIOError(f"{os.path.basename(board)}: no copper layer in its layer list")
    return out


def _cli(args: list[str]) -> str:
    r = kicad_io.run_cli(args, check=True)
    return ((r.stdout or "") + (r.stderr or "")).strip()


def export_gerbers(board: str, tmp: str, layers: list[str], subtract: bool, stem: str) -> str:
    """Gerbers of a copy named <stem>.kicad_pcb (KiCad names the files after the board file)."""
    work = os.path.join(tmp, "g")
    os.makedirs(work)
    copy = os.path.join(work, stem + ".kicad_pcb")
    kicad_io.copy_board(board, copy, lock_source=False)
    out = os.path.join(tmp, "gerbers_g")
    os.makedirs(out)
    _cli(["pcb", "export", "gerbers", "-o", out + os.sep, "--layers", ",".join(layers)]
         + (["--subtract-soldermask"] if subtract else []) + [copy])
    return out


def export_drill(board: str, tmp: str, stem: str) -> str:
    work = os.path.join(tmp, "d")
    os.makedirs(work)
    copy = os.path.join(work, stem + ".kicad_pcb")
    kicad_io.copy_board(board, copy, lock_source=False)
    out = os.path.join(tmp, "gerbers_d")
    os.makedirs(out)
    _cli(["pcb", "export", "drill", "-o", out + os.sep, "--format", "excellon", "--excellon-units", "mm",
          "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", copy])
    return out


def run_rotations(cmd: str, a, cfg: dict, board: str, out: str, extra: list[str]) -> tuple[int, str]:
    """jlc_rotations.py derive / test in its own process (it needs KiCad's Python). Returns (exit code, output)."""
    args = [sys.executable, "-I", os.path.join(_HERE, "jlc_rotations.py"), "--out", out]
    if a.project:
        args += ["--project", a.project]
    if cfg["vendor"]:
        args += ["--vendor", cfg["vendor"]]
    if cfg["bom"]:
        args += ["--bom", cfg["bom"]]
    for f in a.lcsc_field or []:
        args += ["--lcsc-field", f]
    if a.origin:
        args += ["--origin", a.origin]
    args += [cmd, board] + extra
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=ROT_TIMEOUT, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 2, f"jlc_rotations.py {cmd} did not finish in {ROT_TIMEOUT} s"
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def bom_rows(parts: dict, cfg: dict, findings: list[str], notes: list[str]) -> list[list[str]]:
    """Rows of JLCPCB's BOM for exactly the parts that are placed."""
    placed = set(parts)
    rows: list[list[str]] = []
    if cfg["bom"]:
        bom = Bom()
        try:
            read_csv(cfg["bom"], bom, cfg["lcsc_fields"], MPN_FIELDS, "board")
        except _BomError as e:
            raise kicad_io.KicadIOError(str(e)) from None
        notes += bom.notes
        seen: set[str] = set()
        for ln in bom.lines:
            keep = [r for r in ln["refs"] if r in placed]
            dropped = [r for r in ln["refs"] if r not in placed]
            if dropped:
                notes.append(f"BOM table line {ln.get('row', '?')}: left out (not fitted, hand-fitted or not on the "
                             f"board): {', '.join(dropped)}")
            seen.update(keep)
            if keep:
                rows.append([ln["value"], ",".join(keep), ln["footprint"], ln["lcsc"] or ln["bad_number"]])
        missing = sorted(placed - seen, key=natural)
        if missing:
            findings.append("placed on the board but not in the BOM table: " + ", ".join(missing))
        if bom.duplicates:
            findings.append("designators twice in the BOM table: " + ", ".join(bom.duplicates))
    else:
        groups: dict[tuple, dict] = {}
        for ref in sorted(parts, key=natural):
            p = parts[ref]
            key = (p["code"],) if p["code"] else ("", p["value"], p["kicad_footprint"])
            g = groups.setdefault(key, {"refs": [], "values": [], "fp": p["kicad_footprint"], "code": p["code"]})
            g["refs"].append(ref)
            if p["value"] not in g["values"]:
                g["values"].append(p["value"])
        for g in groups.values():
            if len(g["values"]) > 1:
                notes.append(f"BOM line {g['code']}: its designators carry different values "
                             f"({' / '.join(g['values'])}): check the LCSC numbers")
            rows.append([" / ".join(g["values"]), ",".join(g["refs"]), g["fp"], g["code"]])
    without = [r[1] for r in rows if not re.match(r"^C\d+$", r[3] or "")]
    if without:
        findings.append(f"{len(without)} BOM line(s) without a valid LCSC number: " + "; ".join(without)[:400])
    return rows


def _csv_text(rows: list[list[str]]) -> str:
    s = io.StringIO()
    csv.writer(s, lineterminator="\r\n").writerows(rows)
    return s.getvalue()


def _replace_gerbers(src_dirs: list[str], dst: str) -> list[str]:
    if os.path.isdir(dst):
        strange = [n for n in os.listdir(dst) if not _GERBER_FILE.search(n)]
        if strange:
            raise kicad_io.KicadIOError(f"{dst} holds files that are not Gerber or drill files ({', '.join(strange[:3])}); "
                                        "it is not emptied: move them away")
        shutil.rmtree(dst)
    os.makedirs(dst)
    names = []
    for d in src_dirs:
        for n in sorted(os.listdir(d)):
            shutil.copyfile(os.path.join(d, n), os.path.join(dst, n))
            names.append(n)
    return sorted(names)


def file_entry(root: str, rel: str) -> dict:
    p = os.path.join(root, rel)
    return {"file": rel.replace(os.sep, "/"), "bytes": os.path.getsize(p), "sha256": kicad_io.sha256(p),
            "modified": _mtime(p)}


def _where(path: str, jlc: str) -> str | None:
    """Where an input lies, relative to the package folder; None where that path would name folders of the PC
    (another drive, or the user's home folder seen from outside it): the input is then found again by its role."""
    p, j = os.path.abspath(path), os.path.abspath(jlc)
    home = os.path.normcase(os.path.expanduser("~"))
    if os.path.normcase(p).startswith(home + os.sep) and not os.path.normcase(j).startswith(home + os.sep):
        return None
    try:
        return os.path.relpath(p, j).replace(os.sep, "/")
    except ValueError:
        return None


def input_entries(cfg: dict, jlc: str, parts: dict) -> list[dict]:
    """Every input that drove the export, with its SHA-256: board.toml, the assembly BOM table, each JLCPCB
    footprint used for a rotation, the tools. (The board itself is the manifest's "board".)"""
    files = ([("board.toml", cfg["toml"], "board.toml")] if cfg["toml"] else []) + \
            ([("assembly BOM", cfg["bom"], os.path.basename(cfg["bom"]))] if cfg["bom"] else [])
    for code in sorted({p["code"] for p in parts.values() if p.get("code")}):
        mods = sorted({p["jlc_footprint"] for p in parts.values() if p.get("code") == code
                       and p.get("jlc_footprint") and not p["jlc_footprint"].startswith("(")})
        for m in mods:
            rel = f"{code}.pretty/{m}.kicad_mod"
            f = os.path.join(cfg["vendor_dir"] or "", rel)
            if cfg["vendor_dir"] and os.path.isfile(f):
                files.append((f"JLCPCB footprint {code}", f, rel))
    out = [{"role": r, "file": shown, "path": _where(f, jlc), "sha256": kicad_io.sha256(f)} for r, f, shown in files]
    return out + [{"role": f"tool {t}", "file": t, "path": None, "sha256": kicad_io.sha256(os.path.join(_HERE, t))}
                  for t in TOOLS]


def changed_inputs(jlc: str, manifest: dict, cfg: dict) -> list[str]:
    """Inputs that changed since the package was made, each named (empty when none did)."""
    if "inputs" not in manifest:
        return ["the manifest names no inputs (made by an older fab_package.py): export the package again"]
    bad = []
    for e in manifest["inputs"]:
        role = e["role"]
        if role.startswith("tool "):
            p = os.path.join(_HERE, e["file"])
        elif e.get("path"):
            p = os.path.normpath(os.path.join(jlc, e["path"]))
        else:
            p = {"board.toml": cfg["toml"], "assembly BOM": cfg["bom"]}.get(role) or \
                (os.path.join(cfg["vendor_dir"], e["file"]) if cfg["vendor_dir"] and role.startswith("JLCPCB") else None)
        if not p or not os.path.isfile(p):
            bad.append(f"{role} ({e['file']}): not there any more; it is one of the inputs that made the package")
        elif kicad_io.sha256(p) != e["sha256"]:
            bad.append(f"{role} ({e['file']}): changed since the package was made")
    roles = {e["role"] for e in manifest["inputs"]}
    if cfg["toml"] and "board.toml" not in roles:
        bad.append("board.toml: there now, but the package was made without it")
    if cfg["bom"] and "assembly BOM" not in roles:
        bad.append(f"assembly BOM ({os.path.basename(cfg['bom'])}): named now, but the package was made without it")
    return bad


def freshness(jlc: str, board: str, manifest: dict) -> list[str]:
    """Why the package is not fresh (empty when it is)."""
    bad = []
    if not os.path.isfile(board):
        return [f"the board file {os.path.basename(board)} is not there"]
    sha = kicad_io.sha256(board)
    if sha != manifest["board"]["sha256"]:
        bad.append(f"the board changed since the package was made (SHA-256 {sha[:12]}... now, "
                   f"{manifest['board']['sha256'][:12]}... in the manifest)")
    t_board = os.path.getmtime(board)
    for e in manifest.get("outputs", []):
        p = os.path.join(jlc, e["file"])
        if not os.path.isfile(p):
            bad.append(f"{e['file']}: missing")
            continue
        if kicad_io.sha256(p) != e["sha256"]:
            bad.append(f"{e['file']}: changed after the package was made")
        if os.path.getmtime(p) + 1e-6 < t_board:
            bad.append(f"{e['file']}: older than the board ({_mtime(p)} against {_mtime(board)})")
    return bad


def manifest_md(m: dict) -> str:
    pv = m.get("purpose") == PREVIEW_PURPOSE
    out = [f"# {PREVIEW_PURPOSE}: preview package {m['name']}" if pv else f"# Production package: {m['name']}", ""]
    if pv:
        p = m["preview"]
        out += ["**For JLCPCB's placement preview only. Never order it.** Upload it, look at the parts below in the "
                "placement preview, save a crop, never save it to the cart (remove one made by mistake). Then record in board.toml "
                f"`[[rotations.bottom_side_confirmed]]` `bottom_sha256 = \"{p['bottom_sha256']}\"`, `date`, `evidence` "
                "(the crop) and make the order package without --preview.", "",
                "| Waiting part | LCSC | Side | Candidate CPL rot | Candidate X, Y (mm) |", "|---|---|---|---|---|"]
        out += [f"| {r} | {c['code']} | {c['side']} | {c['cpl_rot']:g} | {c['cpl_x']:.3f}, {c['cpl_y']:.3f} |"
                for r, c in p["candidates"].items()] + [""]
    out += [f"**Result: {m['result']}** - made {m['date']} with KiCad {m['kicad_version']} from board "
            f"`{m['board']['file']}` (SHA-256 `{m['board']['sha256']}`, saved {m['board']['modified']}).", ""]
    out += ["| Step | Result | Detail |", "|---|---|---|"]
    for s in m["steps"]:
        out.append(f"| {s['step']} | {s['result']} | {str(s['detail']).replace('|', '/')} |")
    if m["findings"]:
        out += ["", "## Findings", ""] + [f"- {f}" for f in m["findings"]]
    out += ["", "## Files (what is uploaded is what was checked)", "", "| File | Bytes | SHA-256 |", "|---|---|---|"]
    out += [f"| {e['file']} | {e['bytes']} | `{e['sha256']}` |" for e in m["outputs"]]
    out += ["", "## Inputs that produced these files (`--check` fails when one changes)", "",
            "| Input | File | SHA-256 |", "|---|---|---|"]
    out += [f"| board | {m['board']['file']} | `{m['board']['sha256']}` |"]
    out += [f"| {e['role']} | {e['file']} | `{e['sha256']}` |" for e in m.get("inputs", [])]
    out += [f"| KiCad | {m['kicad_version']} | |", "", "Export options: " + "; ".join(
        f"{k} {v}" for k, v in sorted(m.get("options", {}).items())) + "."]
    out += ["", "## Not in the BOM and the placement file", ""]
    np_ = m.get("not_placed", {})
    names = {"dnp": "not fitted (DNP)", "excluded_from_position_files": "excluded from position files in the board",
             "hand_fit": "fitted by hand", "ignored": "ignored", "not_in_bom": "not in the BOM table"}
    lines = [f"- {names[k]}: {', '.join(v)}" for k, v in np_.items() if v]
    out += lines or ["- nothing"]
    out += ["", "## Notes and what was not checked", ""] + [f"- {n}" for n in m["notes"]] + [
        "- copper to board edge on these Gerbers (edge_check.py), DRC (drc_run.py), stock (jlc_parts.py)",
        "- JLCPCB's rules of the day, and every polarised part in the placement preview of the order page",
        "", m["settings"]]
    return "\n".join(out) + "\n"


def settings(a) -> tuple[dict, str, str]:
    toml: dict = {}
    used = []
    if a.project:
        toml = kicad_io.load_settings(a.project)
        used.append("board.toml" if toml else "no board.toml: defaults")
        root = os.path.abspath(a.project)
        try:
            files = kicad_io.project_files(a.project, toml)
            board, out = a.board or files["pcb"], a.out or files["out"]
        except kicad_io.KicadIOError:
            if not a.board:                         # several boards in the project and none named: never guess
                raise
            board = a.board
            out = a.out or os.path.join(root, toml.get("project", {}).get("out_dir", "out"))
    else:
        if not a.board or not a.out:
            raise kicad_io.KicadIOError("give --project <board folder>, or a board file together with --out <folder>")
        used.append("no project folder: defaults and the command line")
        board, out, root = a.board, a.out, None
    if not board or not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"board file not found: {board or '(none in the project folder)'}")
    design = os.path.normcase(os.path.dirname(os.path.abspath(board)))
    if (os.path.normcase(os.path.abspath(out)) + os.sep).startswith(design + os.sep):
        raise kicad_io.KicadIOError("the results folder lies inside the folder of the input design; a design is "
                                    "never written into: choose another folder with --out")
    fab, b = toml.get("fab", {}), toml.get("bom", {})

    def rel(p):
        return os.path.join(root, p) if root and p and not os.path.isabs(p) else p
    lf = b.get("lcsc_field")
    vendor_dir = a.vendor or rel(toml.get("rotations", {}).get("vendor")) or \
        (os.path.join(root, "vendor", "jlc_fp") if root else None)       # as jlc_rotations.py finds it
    cfg = {
        "name": a.name or fab.get("name") or os.path.splitext(os.path.basename(board))[0],
        "subtract": bool(a.subtract_soldermask or fab.get("subtract_soldermask", False)),
        "extra_layers": list(fab.get("extra_layers", [])),
        "vendor": a.vendor, "vendor_dir": vendor_dir if vendor_dir and os.path.isdir(vendor_dir) else None,
        "bom": a.bom or rel(b.get("assembly_file")),
        "toml": os.path.join(root, "board.toml") if root and os.path.isfile(os.path.join(root, "board.toml")) else None,
        "lcsc_fields": a.lcsc_field or ([lf] if isinstance(lf, str) else list(lf or [])) or LCSC_FIELDS,
        "privacy": toml.get("privacy", {}),
    }
    if cfg["bom"] and not os.path.isfile(cfg["bom"]):
        raise kicad_io.KicadIOError(f"BOM table not found: {os.path.basename(cfg['bom'])}")
    cfg["settings_note"] = ("Settings: " + "; ".join(used) + f"; outputs named {cfg['name']}-...; silkscreen "
                            + ("clipped by the solder mask" if cfg["subtract"] else "not clipped by the solder mask")
                            + ("; BOM from " + os.path.basename(cfg["bom"]) if cfg["bom"] else
                               "; BOM and placed parts from the board's own fields") + ".")
    return cfg, board, out


def check_only(board: str, jlc: str, cfg: dict) -> int:
    mf = os.path.join(jlc, "manifest.json")
    if not os.path.isfile(mf):
        print(f"CANNOT RUN: no manifest.json in {jlc}: make the package first", file=sys.stderr)
        return 2
    with open(mf, encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("purpose") == PREVIEW_PURPOSE:
        print(f"FAIL  {PREVIEW_PURPOSE}: this package was made with --preview for JLCPCB's placement preview; it is "
              "never an order package")
        print("freshness gate: FAIL - a preview package is refused as an order package")
        return 1
    kc = kicad_io.require_kicad()
    bad = freshness(jlc, board, manifest) + changed_inputs(jlc, manifest, cfg)
    if kc.version != manifest.get("kicad_version"):
        bad.append(f"KiCad version: {kc.version} now, {manifest.get('kicad_version')} made the package")
    for b in bad:
        print("FAIL  " + b)
    print(f"freshness gate: {'PASS' if not bad else 'FAIL'} - {len(manifest.get('outputs', []))} file(s) and "
          f"{len(manifest.get('inputs', []))} input(s) of the manifest against board {os.path.basename(board)}; the "
          f"package itself was {manifest.get('result')}")
    return 1 if bad else 0


def preview_refusal(rot: dict) -> str:
    """Why no preview package may be made ('' when it may: the one reason for UNKNOWN is the bottom-side convention)."""
    if rot["result"] == "PASS":
        return "no part waits for the bottom-side confirmation: make the order package without --preview"
    if rot.get("bottom_side", {}).get("only_reason"):
        return ""
    other = sorted((r for r, p in rot["parts"].items() if p["status"] in ("UNKNOWN", "FAIL") and not p.get("candidate")),
                   key=natural)
    why = [f"{r} ({rot['parts'][r].get('reason', '')[:70]})" for r in other[:8]] + \
          [f"{r} (in the BOM table, not on the board)" for r in rot.get("in_bom_not_on_board", [])]
    return ("the preview package is only for parts that wait for the bottom-side convention; settle these first: "
            + "; ".join(why or ["the derivation failed (jlc_rotations.py)"]))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Gerbers, drill, BOM, placement file, zip, checksums, privacy scan and "
                                             "freshness gate for a JLCPCB order. Exit 0 pass, 1 findings, 2 could not run.")
    ap.add_argument("board", nargs="?", help="board file (.kicad_pcb); not needed with --project")
    ap.add_argument("--project", help="hardware/board folder (reads board.toml, writes into <project>/out/)")
    ap.add_argument("--out", help="results folder when no project folder is used (the package goes to <out>/jlc/)")
    ap.add_argument("--vendor", help="folder with cached JLCPCB footprints (default <project>/vendor/jlc_fp)")
    ap.add_argument("--bom", help="BOM table (CSV) that decides which designators are assembled")
    ap.add_argument("--lcsc-field", action="append", help="footprint field or BOM column with the LCSC number")
    ap.add_argument("--origin", choices=["bbox", "mean"], help="origin fit of the rotations (default bbox)")
    ap.add_argument("--name", help="base name of the output files (default: the board's name)")
    ap.add_argument("--subtract-soldermask", action="store_true", help="clip the silkscreen where the mask is open")
    ap.add_argument("--check", action="store_true", help="only the freshness gate on an existing package")
    ap.add_argument("--preview", action="store_true", help="the provisional package for JLCPCB's placement preview "
                    "only (bottom-side convention), in <out>/jlc_preview/: PREVIEW ONLY, NOT FOR ORDER")
    a = ap.parse_args(argv)
    cfg, board, out = settings(a)
    jlc = os.path.join(out, "jlc_preview" if a.preview else "jlc")
    if a.check:
        return check_only(board, jlc, cfg)
    kc = kicad_io.require_kicad()
    mark = f"-{PREVIEW}" if a.preview else ""
    name = cfg["name"] + mark
    board_sha, board_time = kicad_io.sha256(board), _mtime(board)
    layers = copper_layers(board) + NON_COPPER + cfg["extra_layers"]
    print(cfg["settings_note"])
    findings: list[str] = []
    notes: list[str] = [kc.note] if kc.note else []
    steps: list[dict] = []
    nxt = ""
    for old in (f"{name}-cpl.csv", f"{name}-bom.csv", f"{name}-gerbers.zip", "manifest.json", "manifest.md",
                f"NOT_FOR_ORDER-{PREVIEW}.txt", f"privacy_scan-{PREVIEW}.md", f"privacy_scan-{PREVIEW}.json"):
        if os.path.isfile(os.path.join(jlc, old)):
            os.remove(os.path.join(jlc, old))             # an old file must not survive a run that cannot renew it
    with kicad_io.private_tmp("fab-package-") as tmp:
        stem = os.path.splitext(os.path.basename(board))[0] + mark
        with ThreadPoolExecutor(max_workers=3) as ex:        # three independent processes, results as in a serial run
            f_g = ex.submit(export_gerbers, board, tmp, layers, cfg["subtract"], stem)
            f_d = ex.submit(export_drill, board, tmp, stem)
            f_r = ex.submit(run_rotations, "derive", a, cfg, board, os.path.join(tmp, "rot"), [])
            g_dir, d_dir = f_g.result(), f_d.result()
            rot_code, rot_text = f_r.result()
        rot_json = os.path.join(tmp, "rot", "jlc", "rotations.json")
        rot = None
        if rot_code in (0, 1) and os.path.isfile(rot_json):
            with open(rot_json, encoding="utf-8") as f:
                rot = json.load(f)
        if a.preview:                                       # written only for the bottom-side convention
            if rot is None:
                raise kicad_io.KicadIOError("the rotations could not be derived: "
                                            + (rot_text.splitlines()[-1] if rot_text else "no output"))
            refused = preview_refusal(rot)
            if refused:
                if os.path.isdir(os.path.join(jlc, "gerbers")):      # no Gerbers of an older preview stay behind
                    _replace_gerbers([], os.path.join(jlc, "gerbers"))
                    os.rmdir(os.path.join(jlc, "gerbers"))
                print("FAIL  " + refused)
                print(f"preview package: NOT WRITTEN - {refused[:120]}")
                return 1
        os.makedirs(jlc, exist_ok=True)
        gerbers = [n for n in os.listdir(g_dir) if not n.lower().endswith(".gbrjob")]
        if len(gerbers) != len(layers):
            findings.append(f"{len(layers)} layers asked for, {len(gerbers)} Gerber files written")
        drills = sorted(n for n in os.listdir(d_dir) if n.lower().endswith(".drl"))
        if not drills:
            findings.append("no drill file written")
        names = _replace_gerbers([g_dir, d_dir], os.path.join(jlc, "gerbers"))
        steps.append({"step": "Gerbers", "result": "PASS" if len(gerbers) == len(layers) else "FAIL",
                      "detail": f"{len(gerbers)} layers: {', '.join(layers)}"})
        steps.append({"step": "Drill files", "result": "PASS" if drills else "FAIL",
                      "detail": ", ".join(drills) + " (Excellon, mm, plated and non-plated apart) and drill maps"})
        zpath = os.path.join(jlc, f"{name}-gerbers.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for n in names:
                z.write(os.path.join(jlc, "gerbers", n), n)
        steps.append({"step": "Zip", "result": "PASS", "detail": f"{name}-gerbers.zip, {len(names)} files"})

        # rotations, placement file, BOM
        if rot is not None and not a.preview:
            for n in ("rotations.json", "rotations.md"):
                kicad_io.atomic_copy(os.path.join(tmp, "rot", "jlc", n), os.path.join(jlc, n))
        cannot = None
        if rot is None:
            cannot = "the rotations could not be derived: " + (rot_text.splitlines()[-1] if rot_text else "no output")
            steps.append({"step": "Rotations", "result": "CANNOT RUN", "detail": cannot})
            steps.append({"step": "Placement file", "result": "NOT WRITTEN", "detail": "no derivation"})
            steps.append({"step": "BOM", "result": "NOT WRITTEN", "detail": "no derivation"})
        else:
            c = rot["counts"]
            wait = rot.get("bottom_side", {}).get("parts", []) if a.preview else []
            steps.append({"step": "Rotations", "result": PREVIEW_PURPOSE if a.preview else rot["result"],
                          "detail": f"{c['placed']} parts to place: {c['derived']} derived, {c['declared']} declared, "
                                    f"{c['unknown']} UNKNOWN, {c['pad_error_above_tolerance']} not fitting"
                                    + (f"; waiting for the bottom-side confirmation: {', '.join(wait)}" if a.preview
                                       else " (jlc/rotations.md)")})
            notes += rot.get("notes", [])
            if a.preview:
                import jlc_rotations
                cpl = os.path.join(jlc, f"{name}-cpl.csv")
                n_rows = jlc_rotations.write_cpl(cpl, rot["parts"], candidates=True)
                steps.append({"step": "Placement file", "result": PREVIEW_PURPOSE,
                              "detail": f"{name}-cpl.csv, {n_rows} rows, of which {len(wait)} candidate(s) on the "
                                        "bottom side; no second derivation (a preview file)"})
                kicad_io.atomic_write(os.path.join(jlc, f"NOT_FOR_ORDER-{PREVIEW}.txt"), (
                    f"{PREVIEW_PURPOSE}\r\n\r\nThis folder was made with fab_package.py --preview for JLCPCB's placement "
                    "preview only. Upload it, look at the bottom-side parts in the placement preview, save a crop, "
                    "never save it to the cart (remove one made by mistake). Never order it. Record the confirmation in board.toml "
                    f"([[rotations.bottom_side_confirmed]] bottom_sha256 = \"{rot['bottom_side']['sha256']}\", date, "
                    "evidence) and make the order package without --preview.\r\n"))
            elif rot["result"] == "PASS":
                import jlc_rotations
                cpl = os.path.join(jlc, f"{name}-cpl.csv")
                n_rows = jlc_rotations.write_cpl(cpl, rot["parts"])
                t_code, t_text = run_rotations("test", a, cfg, board, os.path.join(tmp, "rot_test"), ["--cpl", cpl])
                ok = t_code == 0
                steps.append({"step": "Placement file", "result": "PASS" if ok else "FAIL",
                              "detail": f"{name}-cpl.csv, {n_rows} rows; second derivation: "
                                        + (t_text.splitlines()[-1] if t_text else "no output")})
                if not ok:
                    findings.append("the placement file differs from a fresh derivation: " + t_text[-400:])
            else:
                unknown = sorted((r for r, p in rot["parts"].items() if p["status"] == "UNKNOWN"), key=natural)
                why = (f"{len(unknown)} part(s) without a rotation: " + ", ".join(unknown[:40])
                       + (" ..." if len(unknown) > 40 else "")) if unknown else "the derivation failed (see jlc/rotations.md)"
                findings.append("placement file NOT written (nothing is assumed): " + why)
                if not rot["parts"]:
                    findings.append("no part to place was found on the board")
                steps.append({"step": "Placement file", "result": "NOT WRITTEN", "detail": why[:300]})
                if rot.get("bottom_side", {}).get("only_reason"):
                    nxt = ("these parts wait only for the bottom-side convention: make the preview package with --preview "
                           "(PREVIEW ONLY, NOT FOR ORDER), look at them in JLCPCB's placement preview, record the "
                           "confirmation in board.toml (bottom-side checksum "
                           f"{rot['bottom_side']['sha256'][:12]}..., jlc/rotations.md) and export again")
                    notes.append(nxt)
            rows = bom_rows(rot["parts"], cfg, findings, notes)
            kicad_io.atomic_write(os.path.join(jlc, f"{name}-bom.csv"),
                                  _csv_text([["Comment", "Designator", "Footprint", "LCSC Part #"]] + rows))
            n_refs = sum(len(r[1].split(",")) for r in rows)
            bom_ok = not any("BOM" in f or "placed on the board" in f for f in findings)
            steps.append({"step": "BOM", "result": "PASS" if bom_ok else "FAIL",
                          "detail": f"{name}-bom.csv, {len(rows)} lines, {n_refs} designators"
                                    + (f" (placement file: {c['placed']} parts)" if rot["result"] == "PASS" else "")})
            if rot["result"] == "PASS" and n_refs != c["placed"]:
                findings.append(f"the BOM has {n_refs} designators, the placement file {c['placed']}")

    # checksums, manifest, privacy scan, freshness
    outputs = sorted(os.path.relpath(os.path.join(dp, n), jlc) for dp, _, fs in os.walk(jlc) for n in fs
                     if n not in ("manifest.json", "manifest.md"))
    manifest = {
        "check": "fab_package", "name": name, "purpose": PREVIEW_PURPOSE if a.preview else "order",
        "date": _now(), "kicad_version": kc.version,
        "board": {"file": os.path.basename(board), "sha256": board_sha, "modified": board_time,
                  "bytes": os.path.getsize(board)},
        "inputs": input_entries(cfg, jlc, (rot or {}).get("parts", {})),
        "options": {"name": cfg["name"], "subtract_soldermask": cfg["subtract"], "extra_layers": cfg["extra_layers"],
                    "origin": a.origin or "board.toml or default", "lcsc_field": cfg["lcsc_fields"],
                    "bom": os.path.basename(cfg["bom"]) if cfg["bom"] else None,
                    "vendor": os.path.basename(os.path.abspath(cfg["vendor_dir"])) if cfg["vendor_dir"] else None,
                    "preview": a.preview},
        "layers": layers, "steps": steps, "findings": findings, "notes": notes,
        "not_placed": (rot or {}).get("not_placed", {}), "settings": cfg["settings_note"],
        "outputs": [file_entry(jlc, rel) for rel in outputs],
    }
    if a.preview and rot is not None:
        manifest["preview"] = {"bottom_sha256": rot["bottom_side"]["sha256"], "candidates": {
            r: {k: rot["parts"][r][k] for k in ("code", "side", "cpl_rot", "cpl_x", "cpl_y")}
            for r in rot["bottom_side"]["parts"]}}
    manifest["result"] = "PENDING"
    kicad_io.atomic_write(os.path.join(jlc, "manifest.json"), json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    p = cfg["privacy"]
    scan = privacy_scan.scan_paths([jlc], patterns=p.get("patterns", []), literals=p.get("literals", []),
                                   allow=p.get("allow", []), name_parts=bool(p.get("name_parts", True)))
    if a.preview:                       # the report goes into the preview folder, its name marked as well
        with kicad_io.private_tmp("fab-preview-") as tmp:
            for src in privacy_scan.write_report(scan, tmp):
                base, ext = os.path.splitext(os.path.basename(src))
                kicad_io.atomic_copy(src, os.path.join(jlc, f"{base}-{PREVIEW}{ext}"))
    else:
        privacy_scan.write_report(scan, out)
    steps.append({"step": "Privacy scan", "result": scan["result"],
                  "detail": f"{scan['hits']} hit(s) in {scan['files_scanned']} files (privacy_scan.md)"})
    if scan["result"] != "PASS":
        findings.append(f"privacy scan: {scan['result']}, {scan['hits']} hit(s): see privacy_scan.md")
    stale = freshness(jlc, board, manifest) + changed_inputs(jlc, manifest, cfg)
    steps.append({"step": "Freshness", "result": "PASS" if not stale else "FAIL",
                  "detail": "no output older than the board; the board and the other inputs did not change during "
                            "the export" if not stale else "; ".join(stale)[:300]})
    findings += stale
    manifest["result"] = "CANNOT RUN" if cannot else ("FAIL" if findings else (PREVIEW_PURPOSE if a.preview else "PASS"))
    kicad_io.atomic_write(os.path.join(jlc, "manifest.json"), json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    kicad_io.atomic_write(os.path.join(jlc, "manifest.md"), manifest_md(manifest))
    for s in steps:
        print(f"{s['result']:11} {s['step']}: {s['detail']}")
    for finding in findings:
        print("FAIL  " + finding)
    if nxt:
        print("NEXT  " + nxt)
    print(f"{'preview package' if a.preview else 'production package'}: {manifest['result']} - "
          f"{len(manifest['outputs'])} files in {jlc}; board SHA-256 {board_sha[:16]}...; manifest.json, manifest.md")
    return {"PASS": 0, "FAIL": 1, PREVIEW_PURPOSE: 0}.get(manifest["result"], 2)


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
