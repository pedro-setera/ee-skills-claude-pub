"""Export a KiCad schematic for checking and reading: netlist, rule check (ERC), PDF, one image per sheet.

It is a pure export tool: it works on a schematic written by this skill's library (svclib.py) and just as well on
any other KiCad schematic, drawn by hand by anybody (hierarchical sheets, any libraries, no part-number fields).

What it does, with kicad-cli only (the KiCad program itself is never opened)
    1. netlist      -> netlist.net (kicadsexpr). Absolute paths are taken out of it (the folder it was built in,
                       a user's profile, does not belong in a project file) and the export time is replaced by the
                       date of the root sheet's title block, so that the same schematic gives the same file and
                       the same checksum every time (--kicad-date keeps KiCad's time stamp).
    2. rule check   -> erc_report.json (KiCad's own JSON, every severity). Errors and warnings are counted by
                       type. ERC with 0 errors is necessary and proves little: it once passed two merged nets.
    3. PDF          -> <board>-schematic.pdf, all sheets.
    4. images       -> schematic-<n>-<sheet>.png, one per sheet in page order, made from the PDF with pdftoppm
                       (or Ghostscript, or mutool, whichever is found). LOOK at them: that is what they are for.
    5. model check  -> only for a schematic written by svclib.py (it leaves <name>.model.json beside the root
                       sheet): the nets that the library worked out from the drawing must be exactly the nets of
                       KiCad's netlist. This proves the library's lint on every export.
    and writes schematic_export.md / schematic_export.json with what was done and what was not checked.

Why on a copy
    KiCad may lock a project and rewrite its files when it loads it. The export therefore runs on a private copy
    of the schematic's folder and writes only into --out. Nothing is ever written into the folder of the input
    design. --in-place runs kicad-cli on the files where they are (needed only when the project reaches for
    libraries outside its own folder through relative paths); then only stale KiCad lock files of that project
    are touched.

Usage
    python -I scripts/schematic/export.py ROOT.kicad_sch --out FOLDER [--name BOARD]
    python -I scripts/schematic/export.py --project hardware/<board>

    --name BOARD        name used in <BOARD>-schematic.pdf (default: the root file's name)
    --dpi N             image resolution (default 200; A3 at 200 dpi is 3307 x 2339 pixels)
    --no-png, --no-pdf  skip the images, or the PDF and the images
    --bw                plot in black and white (a trial print; give another --out)
    --allow-warnings    ERC warnings do not make the result FAIL (errors always do)
    --root-name TEXT    the word for the root sheet in the image names (default "root")
    --in-place          run on the files where they are (see above)
    --kicad-date        keep KiCad's export time in the netlist

board.toml keys (only with --project; all optional)
    [project] name, kicad_dir, out_dir      see kicad_io.py
    [schematic] png_dpi                     default 200
    [schematic] root_name                   default "root" (a project whose page 1 is the overview says "overview")
    [schematic] allow_erc_warnings          default false

Exit codes
    0  everything was exported; ERC shows 0 errors (and 0 warnings, unless allowed); the model check, if there
       was one, agrees
    1  ERC violations, or the library's nets differ from KiCad's netlist
    2  could not run: KiCad not found, schematic unreadable, kicad-cli failed, images asked for but no converter
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import concurrent.futures
import contextlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import kicad_io  # noqa: E402
import sexp  # noqa: E402
from kicad_io import CliError, KicadIOError  # noqa: E402

HEAVY = ("*.step", "*.stp", "*.wrl", "*.zip", "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.gbr", "*.drl", "*.kicad_pcb",
         "*.net", "out", "node_modules")
PNG_TIMEOUT = 300.0


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:40].rstrip("-") or "sheet"


# ---- netlist: no build paths, a stable date ---------------------------------------------------------------------------
def clean_netlist(text: str, project_dir: str, title_date: str | None, kicad: kicad_io.KiCad) -> str:
    """Take absolute paths out of an exported netlist and, when title_date is not None, replace the export time."""
    doc = sexp.Document(text)
    proj = os.path.normcase(os.path.abspath(project_dir))
    sym = os.path.normcase(os.path.abspath(kicad.symbols_dir)) if kicad.symbols_dir else None

    def short(path: str) -> str:
        p = os.path.normcase(os.path.abspath(path)) if (os.path.isabs(path) or re.match(r"^[A-Za-z]:", path)) else None
        if p is None:
            return path                                       # already relative, or a ${VARIABLE} path
        if p == proj or p.startswith(proj + os.sep):
            rel = os.path.relpath(os.path.abspath(path), os.path.abspath(project_dir)).replace(os.sep, "/")
            return "${KIPRJMOD}/" + rel
        if sym and p.startswith(sym + os.sep):
            return "${KICAD%d_SYMBOL_DIR}/%s" % (kicad.major, os.path.basename(path))
        return os.path.basename(path.replace("\\", "/"))

    design = sexp.first(doc.root, "design")
    src = sexp.first(design, "source")
    if src is not None and len(src) > 1:
        doc.set(src, 1, sexp.Q(os.path.basename(str(src[1]).replace("\\", "/"))))
    date = sexp.first(design, "date")
    if title_date is not None and date is not None and len(date) > 1:
        doc.set(date, 1, sexp.Q(title_date))
    for lib in sexp.find(sexp.first(doc.root, "libraries"), "library"):
        uri = sexp.first(lib, "uri")
        if uri is not None and len(uri) > 1:
            new = short(str(uri[1]))
            if new != str(uri[1]):
                doc.set(uri, 1, sexp.Q(new))
    return doc.text()


def title_block_date(root: str) -> str:
    with open(root, encoding="utf-8") as f:
        tree = sexp.parse(f.read())
    return str(sexp.value(sexp.first(tree, "title_block"), "date", ""))


# ---- images ----------------------------------------------------------------------------------------------------------
def find_converter() -> tuple[str, str] | None:
    """(kind, program) of the first PDF-to-PNG converter found: pdftoppm, Ghostscript, mutool."""
    for kind, names in (("pdftoppm", ["pdftoppm"]), ("gs", ["gswin64c", "gswin32c", "gs"]), ("mutool", ["mutool"])):
        for n in names:
            w = shutil.which(n)
            if w:
                return kind, w
    return None


def _page_png(conv: tuple[str, str], pdf: str, page: int, dpi: int, png: str) -> str | None:
    """Render one page; returns None on success, else the reason."""
    kind, exe = conv
    if kind == "pdftoppm":
        cmd = [exe, "-r", str(dpi), "-png", "-f", str(page), "-l", str(page), "-singlefile", pdf, png[:-4]]
    elif kind == "gs":
        cmd = [exe, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=png16m", f"-r{dpi}", f"-dFirstPage={page}",
               f"-dLastPage={page}", f"-sOutputFile={png}", pdf]
    else:
        cmd = [exe, "draw", "-r", str(dpi), "-o", png, pdf, str(page)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=PNG_TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return f"page {page}: {e}"
    if r.returncode != 0 or not os.path.isfile(png) or os.path.getsize(png) == 0:
        return f"page {page}: {kind} failed ({(r.stderr or r.stdout or '').strip()[-200:]})"
    return None


def pdf_pages(pdf: str) -> int:
    with open(pdf, "rb") as f:
        return len(re.findall(rb"/Type\s*/Page\b(?!s)", f.read()))


# ---- model check -----------------------------------------------------------------------------------------------------
def model_check(model_path: str, netlist_path: str) -> dict:
    """The nets the drawing library worked out against KiCad's netlist, as sets of pins."""
    with open(model_path, encoding="utf-8") as f:
        model = json.load(f)
    nl = kicad_io.read_netlist(netlist_path)
    mine = {frozenset(n["pins"]) for n in model.get("nets", []) if n.get("pins")}
    theirs = {frozenset(f"{r}.{p}" for r, p in nodes) for nodes in nl.nets.values() if nodes}
    only_model = sorted(sorted(s) for s in mine - theirs)
    only_kicad = sorted(sorted(s) for s in theirs - mine)
    return {"nets_model": len(mine), "nets_kicad": len(theirs), "ok": not only_model and not only_kicad,
            "only_in_model": only_model[:20], "only_in_kicad": only_kicad[:20]}


# ---- the export ------------------------------------------------------------------------------------------------------
def export(root: str, out: str, *, name: str | None = None, dpi: int = 200, png: bool = True, pdf: bool = True,
           bw: bool = False, allow_warnings: bool = False, root_name: str = "root", in_place: bool = False,
           kicad_date: bool = False, quiet: bool = False) -> dict:
    root = os.path.abspath(root)
    if not os.path.isfile(root):
        raise KicadIOError(f"no such schematic: {root}")
    kc = kicad_io.require_kicad()
    why = kicad_io.incomplete_reason(root)
    if why:
        raise KicadIOError(f"schematic not readable: {why}")
    sheets = kicad_io.schematic_sheets(root)
    name = name or os.path.splitext(os.path.basename(root))[0]
    out = os.path.abspath(out)
    src_dir = os.path.dirname(root)
    if os.path.normcase(out) == os.path.normcase(src_dir) and not in_place:
        raise KicadIOError("--out is the schematic's own folder: give another folder (results never go beside the input)")
    os.makedirs(out, exist_ok=True)
    steps: list[dict] = []

    def step(what: str, result: str, detail: str) -> None:
        steps.append({"step": what, "result": result, "detail": detail})
        if not quiet:
            print(f"{result:10} {what}: {detail}")

    res: dict = {"script": "schematic/export.py", "schematic": os.path.basename(root), "board": name,
                 "kicad": kc.version, "kicad_note": kc.note, "mode": "in place" if in_place else "private copy",
                 "sheets": [{"page": s["page"], "name": s["name"], "file": os.path.basename(s["file"])} for s in sheets],
                 "outputs": {}, "steps": steps}
    if kc.note:
        step("KiCad version", "NOTE", kc.note)

    with contextlib.ExitStack() as stack:
        tmp = stack.enter_context(kicad_io.private_tmp("sch-export-"))
        if in_place:
            work_root, work_dir = root, src_dir
            stack.enter_context(kicad_io.ToolLock(root))        # no other tool of ours touches the project meanwhile
            kicad_io.clean_locks(root, whole_folder=True)
        else:
            base = os.path.commonpath([os.path.dirname(s["file"]) for s in sheets])
            if os.path.dirname(base) == base:
                raise KicadIOError("the sheets of this schematic share no folder: run with --in-place")
            work_dir = os.path.join(tmp, "project")
            kicad_io.copy_project(base, work_dir, ignore=kicad_io.COPY_IGNORE + HEAVY)
            work_root = os.path.join(work_dir, os.path.relpath(root, base))
            work_dir = os.path.dirname(work_root)
        tout = os.path.join(tmp, "out")
        os.makedirs(tout)

        # 1. netlist
        t_net = os.path.join(tout, "netlist.net")
        kicad_io.run_cli(["sch", "export", "netlist", "--format", "kicadsexpr", "-o", t_net, work_root], check=True)
        if not os.path.isfile(t_net):
            raise CliError("kicad-cli wrote no netlist")
        with open(t_net, encoding="utf-8", newline="") as f:
            text = clean_netlist(f.read(), work_dir, None if kicad_date else title_block_date(root), kc)
        net_path = os.path.join(out, "netlist.net")
        kicad_io.atomic_write(net_path, text)
        nl = kicad_io.read_netlist(net_path)
        res["outputs"]["netlist"] = {"file": "netlist.net", "sha256": kicad_io.sha256(net_path), "parts": len(nl.parts),
                                     "nets": len(nl.nets), "pins": len(nl.pins)}
        nofp = sorted(r for r, p in nl.parts.items() if not p.footprint and not p.exclude_from_board)
        step("netlist", "DONE", f"netlist.net: {len(nl.parts)} parts, {len(nl.pins)} pins, {len(nl.nets)} nets"
             + (f"; {len(nofp)} part(s) without a footprint" if nofp else ""))
        res["outputs"]["netlist"]["parts_without_footprint"] = nofp

        # 2. rule check
        t_erc = os.path.join(tout, "erc_report.json")
        kicad_io.run_cli(["sch", "erc", "--format", "json", "--severity-all", "--units", "mm", "-o", t_erc, work_root],
                         check=True)
        with open(t_erc, encoding="utf-8") as f:
            erc = json.load(f)
        erc["source"] = os.path.basename(str(erc.get("source", "")).replace("\\", "/"))
        kicad_io.atomic_write(os.path.join(out, "erc_report.json"), json.dumps(erc, indent=2) + "\n")
        counts = {"error": 0, "warning": 0, "excluded": 0}
        by_type: dict[str, dict] = {}
        for sh in erc.get("sheets", []):
            for v in sh.get("violations", []):
                sev = "excluded" if v.get("excluded") else str(v.get("severity", "warning"))
                counts[sev] = counts.get(sev, 0) + 1
                t = by_type.setdefault(str(v.get("type", "?")), {"severity": sev, "count": 0, "example": ""})
                t["count"] += 1
                if not t["example"]:
                    items = "; ".join(str(i.get("description", "")) for i in v.get("items", [])[:2])
                    t["example"] = f"{v.get('description', '')} [{sh.get('path', '')}: {items}]"
        res["outputs"]["erc"] = {"file": "erc_report.json", "errors": counts["error"], "warnings": counts["warning"],
                                 "excluded": counts["excluded"], "by_type": by_type}
        erc_bad = counts["error"] > 0 or (counts["warning"] > 0 and not allow_warnings)
        step("rule check (ERC)", "FAIL" if erc_bad else "PASS",
             f"{counts['error']} errors, {counts['warning']} warnings"
             + (f", {counts['excluded']} excluded" if counts["excluded"] else "")
             + ("; limit: 0 errors" + (", warnings allowed" if allow_warnings else ", 0 warnings")))
        if not quiet:
            for typ, t in sorted(by_type.items(), key=lambda kv: -kv[1]["count"]):
                print(f"             {t['severity']:8} {t['count']:4} x {typ}: {t['example'][:150]}")
        machine = [k for k, typ in (("sym", "lib_symbol_issues"), ("fp", "footprint_link_issues"))
                   if typ in by_type and not kc.global_table(k)]
        if machine:
            res["outputs"]["erc"]["note"] = (
                "This machine has no global " + " and no global ".join(k + "-lib-table" for k in machine)
                + f" in {os.path.basename(os.path.dirname(kc.config_dir))}/{os.path.basename(kc.config_dir)}: "
                "'library not in the configuration' warnings then come from the machine's KiCad settings, not from "
                "the design. Judge them after KiCad's default library tables exist (env_check.py reports this).")
            step("rule check (ERC)", "NOTE", res["outputs"]["erc"]["note"])

        # 3. PDF and 4. images
        cannot: list[str] = []
        if pdf:
            t_pdf = os.path.join(tout, "sch.pdf")
            cmd = ["sch", "export", "pdf", "--no-background-color", "-o", t_pdf] + (["--black-and-white"] if bw else [])
            kicad_io.run_cli(cmd + [work_root], check=True)
            if not os.path.isfile(t_pdf):
                raise CliError("kicad-cli wrote no PDF")
            pdf_name = f"{name}-schematic.pdf"
            kicad_io.atomic_copy(t_pdf, os.path.join(out, pdf_name))
            pages = pdf_pages(t_pdf)
            res["outputs"]["pdf"] = {"file": pdf_name, "pages": pages, "black_and_white": bw}
            step("PDF", "DONE", f"{pdf_name}: {pages} page(s) for {len(sheets)} sheet(s)")
            if png:
                conv = find_converter()
                if conv is None:
                    cannot.append("images: no PDF-to-PNG converter found (pdftoppm, Ghostscript or mutool)")
                    step("images", "CANNOT RUN", cannot[-1])
                else:
                    known = pages == len(sheets)
                    n = pages if pages else len(sheets)
                    names = []
                    for i in range(n):
                        word = (root_name if sheets[i]["name"] == "/" else slug(sheets[i]["name"])) if known else "page"
                        names.append(f"schematic-{i + 1}-{word}.png")
                    workers = max(1, min(n, os.cpu_count() or 1))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                        errs = list(ex.map(lambda i: _page_png(conv, t_pdf, i + 1, dpi, os.path.join(tout, names[i])),
                                           range(n)))
                    failed = [e for e in errs if e]
                    if failed:
                        cannot.append("images: " + "; ".join(failed))
                        step("images", "CANNOT RUN", cannot[-1])
                    else:
                        for old in glob.glob(os.path.join(out, "schematic-*-*.png")):
                            if os.path.basename(old) not in names:
                                os.remove(old)                      # an image of a sheet that no longer exists
                        for nm in names:
                            kicad_io.atomic_copy(os.path.join(tout, nm), os.path.join(out, nm))
                        res["outputs"]["png"] = {"files": names, "dpi": dpi, "converter": conv[0]}
                        step("images", "DONE", f"{len(names)} PNG at {dpi} dpi with {conv[0]}: {', '.join(names)}"
                             + ("" if known else " (page count differs from the sheet list: named by page)"))
            else:
                step("images", "NOT DONE", "--no-png")
        else:
            step("PDF and images", "NOT DONE", "--no-pdf")

        # 5. model check
        model = os.path.splitext(root)[0] + ".model.json"
        mc = None
        if os.path.isfile(model):
            mc = model_check(model, net_path)
            res["model_check"] = mc
            step("model check", "PASS" if mc["ok"] else "FAIL",
                 f"nets worked out from the drawing: {mc['nets_model']}; nets in KiCad's netlist: {mc['nets_kicad']}"
                 + ("" if mc["ok"] else f"; differ: only in the model {mc['only_in_model'][:3]}, only in KiCad "
                                        f"{mc['only_in_kicad'][:3]}"))
        else:
            res["model_check"] = None
            step("model check", "NOT DONE", "no <name>.model.json beside the schematic (not written by svclib.py)")

    code = 2 if cannot else (1 if (erc_bad or (mc is not None and not mc["ok"])) else 0)
    res["cannot_run"] = cannot
    res["exit_code"] = code
    res["result"] = {0: "PASS", 1: "FAIL", 2: "CANNOT RUN"}[code]
    res["not_checked"] = [
        "Whether the circuit is right: ERC knows pin types, not intent. Run netlist_check.py against the hand-written "
        "intent file.",
        "Whether the sheets can be read: open every image and write what you saw.",
        "Part numbers, stock, footprints against the parts' drawings.",
    ]
    kicad_io.atomic_write(os.path.join(out, "schematic_export.json"), json.dumps(res, indent=2) + "\n")
    kicad_io.atomic_write(os.path.join(out, "schematic_export.md"), report_md(res))
    if not quiet:
        print(f"{res['result']}: results in {out}")
    return res


def report_md(res: dict) -> str:
    o = res["outputs"]
    L = ["# Schematic export", "",
         f"- Schematic: `{res['schematic']}` ({len(res['sheets'])} sheet(s)); KiCad {res['kicad']}; run on: {res['mode']}.",
         f"- **Result: {res['result']}** (exit code {res['exit_code']})", "",
         "| Step | Result | Detail |", "|---|---|---|"]
    for s in res["steps"]:
        L.append(f"| {s['step']} | {s['result']} | {s['detail'].replace('|', '/')} |")
    L += ["", "## Sheets", "", "| Page | Sheet | File |", "|---|---|---|"]
    L += [f"| {s['page']} | {s['name']} | `{s['file']}` |" for s in res["sheets"]]
    L.append("")
    if "netlist" in o:
        L += [f"Netlist `netlist.net`: SHA-256 `{o['netlist']['sha256']}`.", ""]
        if o["netlist"]["parts_without_footprint"]:
            L += ["**Parts without a footprint:** " + ", ".join(o["netlist"]["parts_without_footprint"]), ""]
    if "erc" in o and o["erc"]["by_type"]:
        L += ["## ERC violations by type", "", "| Type | Severity | Count | First one |", "|---|---|---|---|"]
        for typ, t in sorted(o["erc"]["by_type"].items(), key=lambda kv: -kv[1]["count"]):
            L.append(f"| {typ} | {t['severity']} | {t['count']} | {t['example'].replace('|', '/')[:300]} |")
        L.append("")
        if o["erc"].get("note"):
            L += ["Note: " + o["erc"]["note"], ""]
    L += ["## Not checked", ""] + [f"- {t}" for t in res["not_checked"]] + [""]
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Export a KiCad schematic (made by this skill or by anybody): netlist, ERC report (JSON), PDF, "
                    "one PNG per sheet. Runs kicad-cli on a private copy; writes only into --out.",
        epilog="Exit codes: 0 exported and ERC clean; 1 ERC violations (or the drawing library's nets differ from "
               "KiCad's); 2 could not run. Result names: netlist.net, erc_report.json, <board>-schematic.pdf, "
               "schematic-<n>-<sheet>.png, schematic_export.md / .json.")
    ap.add_argument("schematic", nargs="?", help="the root sheet (<name>.kicad_sch)")
    ap.add_argument("--project", metavar="BOARD_FOLDER", help="board folder; the schematic is found in its KiCad folder")
    ap.add_argument("--out", metavar="FOLDER", help="folder for the results")
    ap.add_argument("--name", metavar="BOARD", help="name used in <BOARD>-schematic.pdf")
    ap.add_argument("--dpi", type=int, help="image resolution (default 200)")
    ap.add_argument("--no-png", action="store_true", help="no images")
    ap.add_argument("--no-pdf", action="store_true", help="no PDF and no images")
    ap.add_argument("--bw", action="store_true", help="plot in black and white")
    ap.add_argument("--allow-warnings", action="store_true", help="ERC warnings do not fail the export")
    ap.add_argument("--root-name", metavar="TEXT", help="word for the root sheet in the image names (default root)")
    ap.add_argument("--in-place", action="store_true", help="run kicad-cli on the files where they are")
    ap.add_argument("--kicad-date", action="store_true", help="keep KiCad's export time in the netlist")
    a = ap.parse_args(argv)

    cfg: dict = {}
    root, out, name = a.schematic, a.out, a.name
    if a.project:
        settings = kicad_io.load_settings(a.project)
        cfg = settings.get("schematic", {})
        files = kicad_io.project_files(a.project, settings)
        root = root or files["sch"]
        out = out or files["out"]
        name = name or files["name"]
        if not root:
            print(f"CANNOT RUN: no schematic {files['name']}.kicad_sch in {files['kicad_dir']}", file=sys.stderr)
            return 2
    if not root or not out:
        print("CANNOT RUN: give ROOT.kicad_sch with --out FOLDER, or --project BOARD_FOLDER", file=sys.stderr)
        return 2
    res = export(root, out, name=name, dpi=a.dpi or int(cfg.get("png_dpi", 200)), png=not a.no_png, pdf=not a.no_pdf,
                 bw=a.bw, allow_warnings=a.allow_warnings or bool(cfg.get("allow_erc_warnings", False)),
                 root_name=a.root_name or str(cfg.get("root_name", "root")), in_place=a.in_place,
                 kicad_date=a.kicad_date)
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
