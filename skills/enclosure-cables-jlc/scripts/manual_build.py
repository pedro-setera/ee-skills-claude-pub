"""Assembly manual from a step list: self-contained HTML, optional A4 PDF and page pictures, with checks.

What it does
    Reads `manual/steps.toml` (ordered steps: title, 1 to 3 text lines, a picture or a `shot` reference, parts added with quantities, fasteners
    with size, tool icon names, an optional `warning` = the one thing that goes wrong, an optional `threadlocker`, optional OPEN items) and writes
    `<out>/manual/assembly-manual.html`: cover, contents, a parts-and-tools page (parts, fasteners at true scale, tools: all SUMMED from the steps),
    the steps with the picture first, and a numbered list of every OPEN item. Pictures are embedded, so the file is self-contained. The A4 print
    stylesheet is `templates/manual.css` (a copy at `<project>/manual/manual.css` wins).
    --pdf   prints `<out>/manual/assembly-manual.pdf` with headless Chrome or Edge (found by `[tools] chrome`, then the usual places); without
            one the HTML is still written and the exit code is 2 for the PDF part only.
    --png   renders every PDF page to `<out>/manual/pages/page-NN.png` (PyMuPDF) so that each page can be LOOKED at.
    A `shot = "name"` is looked up as `<name>.png` in `<out>/manual/annotated/`, then `<out>/renders/`, then `<out>/views/`.
    Check rows (`<out>/checks/manual_build.json`):
      picture           every step has a picture that exists
      fresh             the picture is not older than the model (the model file and the .py files next to it)
      text              1 to 3 text lines per step, each at most 120 characters
      parts used        every entry of the parts list is used in some step and every part a step adds is in the list; summed quantities match
      order             the order in which the steps add parts follows the model's ASSEMBLY_ORDER (from `<out>/views/views_manifest.json`, else read from the
                        model file without running it); "na" when the model has none
      tools             every tool icon name is known
      open items        listed (a count); the manual is not final while any remain (the row is "pass" with the count so it is visible; --strict fails it)

Why it exists (the real failure, told without names)
    A manual was drawn once from an early model; after two design changes its pictures showed a lid with the wrong screw pattern, a part was missing
    from its parts list, and no one had checked the step order against the insertion order the model had proven. Generating it from one step file,
    with the pictures tied to the model's time, makes every one of those a failed row.

Usage
    python -I scripts/manual_build.py [STEPS.toml] [--project DIR] [--out DIR] [--pdf] [--png] [--strict] [--dpi N]

Config (steps.toml; mech.toml supplies the model path and `[tools] chrome`)
    [manual]  title, subtitle = "Assembly manual", company = "", revision = "A", edition = "YYYY-MM-DD", cover_picture = shot or file (optional),
              model = path of the model file (default [paths] model), max_px = 1600 (widest embedded picture),
              per_page = 2 (steps per A4 page: 2, or 1 for big pictures)
    [[part]]  name, qty, model = "solid name in the model" (default the name, lower case)
    [[step]]  title, text = ["line", ...], shot = "name" | picture = "file", parts = [{name, qty, model}], fasteners = [{name = "M3 x 8 pan head",
              qty, drive = "hex"}], tools = ["hex 2.0"] (or tool = "..."; the first word is the icon), warning = "text", threadlocker = true,
              open = ["text"]
    Tool icons: hex, torx, cross, slotted, nut, spanner, pliers, tweezers, crimp, solder, hand.

Exit codes: 0 HTML (and the PDF/PNG when asked) made and every row passes; 1 a row failed; 2 steps file missing, or Chrome/Edge missing for --pdf/--png.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ast
import base64
import glob
import html
import io
import json
import re
import shutil
import subprocess
import tempfile

import mech_common as mc

ICONS = {
    "hex": '<circle cx="10" cy="10" r="9" fill="#d8dce3" stroke="#1d2330"/><polygon points="10,5 14.3,7.5 14.3,12.5 10,15 5.7,12.5 5.7,7.5" fill="#1d2330"/>',
    "torx": '<circle cx="10" cy="10" r="9" fill="#d8dce3" stroke="#1d2330"/><path d="M10 4.5 L11.6 7.2 L14.8 7.2 L13.2 10 L14.8 12.8 L11.6 12.8 L10 15.5 L8.4 12.8 L5.2 12.8 L6.8 10 L5.2 7.2 L8.4 7.2 Z" fill="#1d2330"/>',
    "cross": '<circle cx="10" cy="10" r="9" fill="#d8dce3" stroke="#1d2330"/><path d="M8.6 4.5h2.8v4.1h4.1v2.8h-4.1v4.1h-2.8v-4.1h-4.1v-2.8h4.1z" fill="#1d2330"/>',
    "slotted": '<circle cx="10" cy="10" r="9" fill="#d8dce3" stroke="#1d2330"/><rect x="4" y="8.6" width="12" height="2.8" fill="#1d2330"/>',
    "nut": '<polygon points="10,1.5 17.4,5.8 17.4,14.2 10,18.5 2.6,14.2 2.6,5.8" fill="#d8dce3" stroke="#1d2330"/><circle cx="10" cy="10" r="3.6" fill="#fff" stroke="#1d2330"/>',
    "spanner": '<path d="M13.5 2.2a4.3 4.3 0 0 0-4 5.6L3 14.3a1.9 1.9 0 0 0 2.7 2.7l6.5-6.5a4.3 4.3 0 0 0 5.6-4l-2.6 2.2-2.2-.6-.6-2.2z" fill="#d8dce3" stroke="#1d2330" stroke-linejoin="round"/>',
    "pliers": '<path d="M4 17 L9 9 M16 17 L11 9 M7.5 9 C6 6 7 3 10 2 C13 3 14 6 12.5 9 Z" fill="#d8dce3" stroke="#1d2330" stroke-width="1.4" stroke-linejoin="round"/>',
    "tweezers": '<path d="M10 2 L5 18 M10 2 L15 18" stroke="#1d2330" stroke-width="2" fill="none"/><path d="M10 2 L7.5 10 M10 2 L12.5 10" stroke="#d8dce3" stroke-width="1" fill="none"/>',
    "crimp": '<rect x="3" y="8" width="14" height="5" rx="1.5" fill="#d8dce3" stroke="#1d2330"/><path d="M6 8 V4 M14 8 V4 M6 13 V17 M14 13 V17" stroke="#1d2330" stroke-width="1.6"/>',
    "solder": '<path d="M3 17 L12 8" stroke="#1d2330" stroke-width="2.4"/><path d="M12 8 L16 4" stroke="#e8590c" stroke-width="2.4"/><circle cx="16.5" cy="3.5" r="1.8" fill="#e8590c"/>',
    "hand": '<path d="M6 17 V9 M9 17 V5 M12 17 V5 M15 17 V8 M6 12 L4 9" stroke="#1d2330" stroke-width="2" fill="none" stroke-linecap="round"/>',
}


def icon_svg(name: str) -> str:
    return f'<svg viewBox="0 0 20 20" class="ic" aria-hidden="true">{ICONS[name]}</svg>'


def fastener_svg(name: str) -> str:
    """A side view of a screw drawn at 1:1 in millimetres from a name like 'M3 x 8 pan head' (empty when the size cannot be read)."""
    m = re.search(r"[Mm](\d+(?:\.\d+)?)\s*[x\u00d7]\s*(\d+(?:\.\d+)?)", name)
    if not m:
        return ""
    d, l = float(m.group(1)), float(m.group(2))
    head_d, head_h = 1.9 * d, 0.65 * d
    w, h = l + head_h + 0.6, head_d + 0.6
    cy = h / 2
    thread = "".join(f'<line x1="{head_h + 0.3 + k * 0.5 * d:.2f}" y1="{cy - d / 2:.2f}" x2="{head_h + 0.3 + k * 0.5 * d + 0.25 * d:.2f}" y2="{cy + d / 2:.2f}" stroke="#5b6475" stroke-width="0.12"/>'
                     for k in range(int(l / (0.5 * d))))
    return (f'<svg class="scr" width="{w:.2f}mm" height="{h:.2f}mm" viewBox="0 0 {w:.2f} {h:.2f}" aria-label="{html.escape(name)} at true size">'
            f'<rect x="0.3" y="{cy - head_d / 2:.2f}" width="{head_h:.2f}" height="{head_d:.2f}" rx="{0.25 * d:.2f}" fill="#c9ced6" stroke="#1d2330" stroke-width="0.15"/>'
            f'<rect x="{head_h + 0.3:.2f}" y="{cy - d / 2:.2f}" width="{l:.2f}" height="{d:.2f}" fill="#dfe3e8" stroke="#1d2330" stroke-width="0.15"/>{thread}</svg>')


# ---------------------------------------------------------------- reading --------------------------------------------
def tool_names(step: dict) -> list:
    t = list(step.get("tools", []) or [])
    if step.get("tool"):
        t.append(step["tool"])
    return [str(x).strip() for x in t if str(x).strip()]


def tool_icon(t: str) -> str:
    return t.split()[0].lower()


def text_lines(step: dict) -> list:
    t = step.get("text", [])
    if isinstance(t, str):
        t = t.split("\n")
    return [str(x) for x in t if str(x).strip()]


def find_picture(step: dict, base: str, out: str) -> str | None:
    if step.get("picture"):
        p = step["picture"] if os.path.isabs(step["picture"]) else os.path.join(base, step["picture"])
        return p if os.path.isfile(p) else p
    s = step.get("shot")
    if s:
        for d in (os.path.join(out, "manual", "annotated"), os.path.join(out, "renders"), os.path.join(out, "views")):
            p = os.path.join(d, s + ".png")
            if os.path.isfile(p):
                return p
        return os.path.join(out, "manual", "annotated", s + ".png")
    return None


def assembly_order(out: str, model_path: str) -> list | None:
    """ASSEMBLY_ORDER from the views manifest, else read (not executed) from the model file."""
    mp = os.path.join(out, "views", "views_manifest.json")
    if os.path.isfile(mp):
        try:
            o = mc.load_json(mp).get("assembly_order")
            if o:
                return list(o)
        except Exception:
            pass
    if model_path and os.path.isfile(model_path):
        try:
            tree = ast.parse(open(model_path, encoding="utf-8").read())
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("ASSEMBLY_ORDER", "assembly_order") for t in node.targets):
                    return [str(x) for x in ast.literal_eval(node.value)]
        except Exception:
            return None
    return None


def model_mtime(model_path: str) -> float | None:
    if not model_path or not os.path.isfile(model_path):
        return None
    d = os.path.dirname(os.path.abspath(model_path))
    return max([os.path.getmtime(model_path)] + [os.path.getmtime(p) for p in glob.glob(os.path.join(d, "*.py"))])


def embed(path: str, max_px: int) -> str:
    from PIL import Image
    im = Image.open(path)
    if im.width > max_px:
        im = im.resize((max_px, round(im.height * max_px / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode in ("RGBA", "LA", "P"):
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.convert("RGB").save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- checks ---------------------------------------------
def run_checks(doc: dict, base: str, out: str, model_path: str, strict: bool, rows: mc.Rows) -> None:
    steps = doc.get("step", [])
    plist = doc.get("part", [])
    mt = model_mtime(model_path)
    for i, s in enumerate(steps, 1):
        sid = f"MAN-S{i:02d}"
        pic = find_picture(s, base, out)
        if pic is None:
            rows.add(f"{sid}-PIC", "manual", f"step {i} '{s.get('title', '')}' has a picture", "no picture or shot", "every step has a picture", "fail")
        elif not os.path.isfile(pic):
            rows.add(f"{sid}-PIC", "manual", f"step {i} '{s.get('title', '')}' picture exists", f"missing: {pic}", "file exists", "fail")
        else:
            rows.add(f"{sid}-PIC", "manual", f"step {i} picture exists", os.path.basename(pic), "file exists", "pass")
            if mt is None:
                rows.add(f"{sid}-FRESH", "manual", f"step {i} picture newer than the model", "model file not found", "picture not older than the model", "could_not_run")
            else:
                pm = os.path.getmtime(pic)
                rows.add(f"{sid}-FRESH", "manual", f"step {i} picture newer than the model", f"{(pm - mt):+.0f} s against the model",
                         "picture not older than the model (regenerate it)", "pass" if pm + 2.0 >= mt else "fail")
        lines = text_lines(s)
        long_ = [l for l in lines if len(l) > 120]
        rows.add(f"{sid}-TEXT", "manual", f"step {i} text", f"{len(lines)} line(s)" + (f", {len(long_)} longer than 120 characters" if long_ else ""),
                 "1 to 3 lines of at most 120 characters", "pass" if 1 <= len(lines) <= 3 and not long_ else "fail")
        for t in tool_names(s):
            if tool_icon(t) not in ICONS:
                rows.add(f"{sid}-TOOL", "manual", f"step {i} tool '{t}'", "unknown icon", f"one of {', '.join(sorted(ICONS))}", "fail")
    # parts
    listed = {str(p["name"]): p for p in plist}
    used: dict[str, int] = {}
    for s in steps:
        for p in s.get("parts", []) or []:
            used[p["name"]] = used.get(p["name"], 0) + int(p.get("qty", 1))
    unused = [n for n in listed if n not in used]
    undeclared = [n for n in used if n not in listed]
    rows.add("MAN-PARTS-USED", "manual", "every part of the parts list is used in a step", ", ".join(unused) if unused else f"{len(listed)} of {len(listed)} used",
             "no unused part", "fail" if unused else "pass")
    rows.add("MAN-PARTS-LISTED", "manual", "every part a step adds is in the parts list", ", ".join(undeclared) if undeclared else "all listed", "no unlisted part",
             "fail" if undeclared else "pass")
    bad = [f"{n}: list {int(listed[n].get('qty', 1))}, steps {used[n]}" for n in listed if n in used and used[n] != int(listed[n].get("qty", 1))]
    rows.add("MAN-PARTS-QTY", "manual", "summed quantities of the steps equal the parts list", "; ".join(bad) if bad else "all equal", "equal", "fail" if bad else "pass")
    # order
    order = assembly_order(out, model_path)
    if not order:
        rows.add("MAN-ORDER", "manual", "step order follows the model's ASSEMBLY_ORDER", "the model has none", "needs ASSEMBLY_ORDER in the model", "na")
    else:
        seq = []
        for s in steps:
            for p in s.get("parts", []) or []:
                m = str((listed.get(p["name"]) or p).get("model") or p.get("model") or p["name"].lower())
                if m in order and m not in seq:
                    seq.append(m)
        pos = [order.index(m) for m in seq]
        ok = pos == sorted(pos)
        rows.add("MAN-ORDER", "manual", "step order follows the model's ASSEMBLY_ORDER", " > ".join(seq) if seq else "no part of the order appears in the steps",
                 "model order: " + " > ".join(order), "pass" if ok and seq else "fail")
    n_open = sum(len(s.get("open", []) or []) for s in steps)
    rows.add("MAN-OPEN", "manual", "OPEN items", f"{n_open} open", "none open for a final manual" if strict else "listed at the end of the manual",
             "pass" if (n_open == 0 or not strict) else "fail")


# ---------------------------------------------------------------- html -----------------------------------------------
def build_html(doc: dict, base: str, out: str, css: str) -> str:
    m = {"title": "Assembly", "subtitle": "Assembly manual", "company": "", "revision": "A", "edition": "", "max_px": 1600}
    m.update(doc.get("manual", {}))
    steps = doc.get("step", [])
    esc = html.escape
    maxpx = int(m["max_px"])
    parts_sum: dict[str, dict] = {}
    fast_sum: dict[str, dict] = {}
    tools_sum: dict[str, list] = {}
    for i, s in enumerate(steps, 1):
        for p in s.get("parts", []) or []:
            e = parts_sum.setdefault(p["name"], {"qty": 0, "steps": []})
            e["qty"] += int(p.get("qty", 1))
            e["steps"].append(i)
        for f in s.get("fasteners", []) or []:
            e = fast_sum.setdefault(f["name"], {"qty": 0, "steps": [], "drive": f.get("drive", ""), "tl": False})
            e["qty"] += int(f.get("qty", 1))
            e["steps"].append(i)
            e["tl"] = e["tl"] or bool(s.get("threadlocker"))
        for t in tool_names(s):
            tools_sum.setdefault(t, []).append(i)
    o = [f"<!doctype html><html lang=\"{esc(str(m.get('lang', 'en')))}\"><head><meta charset=\"utf-8\"><title>{esc(m['title'])} - {esc(m['subtitle'])}</title>",
         "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">", f"<style>{css}</style></head><body class=\"pp{1 if int(m.get('per_page', 2)) == 1 else 2}\">"]
    hero = ""
    if m.get("cover_picture"):
        cp = find_picture({"shot": m["cover_picture"]} if not os.path.splitext(m["cover_picture"])[1] else {"picture": m["cover_picture"]}, base, out)
        if cp and os.path.isfile(cp):
            hero = f'<div class="hero"><img alt="" src="{embed(cp, maxpx)}"></div>'
    o.append(f'<section class="cover"><div class="top"><h1>{esc(m["title"])}</h1><div class="sub">{esc(m["subtitle"])}</div></div>{hero}'
             f'<div class="meta"><span>{esc(m["company"])}</span><span>Revision {esc(str(m["revision"]))}</span><span>{esc(str(m["edition"]))}</span></div></section>')
    toc = "".join(f'<li><span class="n">{i}</span>{esc(s.get("title", ""))}</li>' for i, s in enumerate(steps, 1))
    o.append(f'<section class="page"><h2 class="sec">Contents</h2><ol class="toc">{toc}</ol></section>')
    # parts / fasteners / tools
    t = ['<section class="page"><h2 class="sec">Parts, fasteners and tools</h2>', "<h3>Parts</h3><table><tr><th>Part</th><th class=\"num\">Qty</th><th>Steps</th></tr>"]
    for n, e in parts_sum.items():
        t.append(f"<tr><td>{esc(n)}</td><td class=\"num\">{e['qty']}</td><td>{', '.join(map(str, e['steps']))}</td></tr>")
    t.append("</table>")
    if fast_sum:
        t.append("<h3>Fasteners (drawn at true size)</h3><table><tr><th>Fastener</th><th class=\"num\">Qty</th><th>Drive</th><th>Steps</th><th>1:1</th></tr>")
        for n, e in fast_sum.items():
            drv = (icon_svg(e["drive"]) + esc(e["drive"])) if e["drive"] in ICONS else esc(e["drive"])
            tl = ' <span class="chip tl">threadlocker</span>' if e["tl"] else ""
            t.append(f"<tr><td>{esc(n)}{tl}</td><td class=\"num\">{e['qty']}</td><td>{drv}</td><td>{', '.join(map(str, sorted(set(e['steps']))))}</td><td>{fastener_svg(n)}</td></tr>")
        t.append("</table>")
    if tools_sum:
        t.append("<h3>Tools</h3><table><tr><th>Tool</th><th>Steps</th></tr>")
        for n, st in tools_sum.items():
            ic = icon_svg(tool_icon(n)) if tool_icon(n) in ICONS else ""
            t.append(f"<tr><td>{ic}{esc(n)}</td><td>{', '.join(map(str, sorted(set(st))))}</td></tr>")
        t.append("</table>")
    t.append("</section>")
    o.append("".join(t))
    # steps
    open_no = 0
    open_list = []
    o.append('<section class="steps">')
    for i, s in enumerate(steps, 1):
        pic = find_picture(s, base, out)
        img = (f'<div class="pic"><img alt="{esc(s.get("title", ""))}" src="{embed(pic, maxpx)}"></div>' if pic and os.path.isfile(pic)
               else f'<div class="missing">PICTURE MISSING: {esc(os.path.basename(pic) if pic else "none given")}</div>')
        text = "".join(f"<p>{esc(l)}</p>" for l in text_lines(s))
        chips = []
        for p in s.get("parts", []) or []:
            chips.append(f'<span class="chip"><b>{int(p.get("qty", 1))} x</b> {esc(p["name"])}</span>')
        for f in s.get("fasteners", []) or []:
            tlc = " tl" if s.get("threadlocker") else ""
            chips.append(f'<span class="chip fast{tlc}"><b>{int(f.get("qty", 1))} x</b> {esc(f["name"])} {fastener_svg(f["name"])}</span>')
        for tl in tool_names(s):
            ic = icon_svg(tool_icon(tl)) if tool_icon(tl) in ICONS else ""
            chips.append(f'<span class="chip tool">{ic}{esc(tl)}</span>')
        if s.get("threadlocker"):
            chips.append('<span class="chip tl">medium threadlocker on the thread</span>')
        warn = f'<div class="warn"><span class="bang">!</span><span>{esc(s["warning"])}</span></div>' if s.get("warning") else ""
        opens = ""
        for ot in s.get("open", []) or []:
            open_no += 1
            open_list.append((open_no, i, ot))
            opens += f'<div class="open"><b>OPEN {open_no}</b> {esc(ot)}</div>'
        o.append(f'<article class="step" id="s{i}"><header><span class="no">{i}</span><h3>{esc(s.get("title", ""))}</h3></header>{img}'
                 f'<div class="body"><div class="text">{text}</div><div class="chips">{"".join(chips)}</div>{warn}{opens}</div></article>')
    o.append("</section>")
    ol = "".join(f"<li><b>OPEN {n}</b>, step {st}: {esc(tx)}</li>" for n, st, tx in open_list) or "<li>None.</li>"
    o.append(f'<section class="page"><h2 class="sec">Open items</h2><ol class="openlist" style="list-style:none;padding:0">{ol}</ol>'
             f'<p class="note">The manual is final when this list is empty and every picture was checked against the built product.</p></section>')
    o.append("</body></html>")
    return "".join(o)


# ---------------------------------------------------------------- chrome ---------------------------------------------
def find_chrome(cfg: dict) -> str | None:
    if str(cfg.get("tools", {}).get("chrome", "")).strip().lower() == "none":
        return None                                  # declined by the user ([tools] chrome = "none"): never looked for
    c = [cfg.get("tools", {}).get("chrome", ""), os.environ.get("CHROME", "")]
    for pf in (os.environ.get("ProgramFiles", "C:/Program Files"), os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")):
        c += [os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"), os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe")]
    c += [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
          "/usr/bin/microsoft-edge"]
    for n in ("chrome", "google-chrome", "chromium", "msedge"):
        w = shutil.which(n)
        if w:
            c.append(w)
    for x in c:
        if x and os.path.isfile(x):
            return x
    return None


def print_pdf(chrome: str, html_path: str, pdf_path: str) -> bool:
    prof = tempfile.mkdtemp(prefix="manual_chrome_")
    try:
        url = "file:///" + os.path.abspath(html_path).replace("\\", "/").lstrip("/")
        cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", f"--user-data-dir={prof}", "--no-pdf-header-footer",
               "--virtual-time-budget=20000", f"--print-to-pdf={os.path.abspath(pdf_path)}", url]
        if os.path.isfile(pdf_path):
            os.remove(pdf_path)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=180)
        return os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 1000
    except Exception:
        return False
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def run(args) -> int:
    try:
        job = mc.resolve(args)
    except mc.MechError:
        if not (args.steps and args.out):
            raise
        job = mc.Job(os.getcwd(), mc.load_config(os.getcwd()), os.path.abspath(args.out))
    cfg = job.cfg
    steps_path = args.steps or os.path.join(job.project, "manual", "steps.toml")
    if not os.path.isfile(steps_path):
        print(f"could not run: steps file not found: {steps_path}", file=sys.stderr)
        return 2
    mc.require_module("PIL", "pictures")
    doc = mc.load_toml(steps_path)
    if not doc.get("step"):
        print(f"could not run: {steps_path} has no [[step]]", file=sys.stderr)
        return 2
    base = os.path.dirname(os.path.abspath(steps_path))
    out = job.out
    mm = doc.get("manual", {}).get("model")
    model_path = (mm if mm and os.path.isabs(mm) else os.path.join(job.project, mm)) if mm else mc.path_of(cfg, "model")
    rows = mc.Rows()
    run_checks(doc, base, out, model_path, args.strict, rows)
    css_path = next((p for p in (os.path.join(base, "manual.css"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "manual.css")) if os.path.isfile(p)), None)
    if css_path is None:
        print("could not run: templates/manual.css not found", file=sys.stderr)
        return 2
    css = open(css_path, encoding="utf-8").read()
    mdir = os.path.join(out, "manual")
    os.makedirs(mdir, exist_ok=True)
    html_path = os.path.join(mdir, "assembly-manual.html")
    mc.atomic_write(html_path, build_html(doc, base, out, css))
    print(f"wrote {html_path} ({os.path.getsize(html_path) // 1024} KiB)")
    code_extra = 0
    pdf_path = os.path.join(mdir, "assembly-manual.pdf")
    if args.pdf or args.png:
        chrome = find_chrome(cfg)
        if not chrome:
            print("could not run: no Chrome or Edge found for the PDF (set [tools] chrome); the HTML is written", file=sys.stderr)
            rows.add("MAN-PDF", "manual", "PDF printed", "no Chrome or Edge", "needs a Chromium browser", "could_not_run")
        elif not print_pdf(chrome, html_path, pdf_path):
            rows.add("MAN-PDF", "manual", "PDF printed", "the browser wrote no PDF", "PDF exists", "fail")
        else:
            try:
                try:
                    import pymupdf as fitz
                except ImportError:
                    import fitz
                d = fitz.open(pdf_path)
                n = d.page_count
                rows.add("MAN-PDF", "manual", "PDF printed", f"{n} A4 pages, {os.path.getsize(pdf_path) // 1024} KiB", "PDF exists", "pass")
                if args.png:
                    pdir = os.path.join(mdir, "pages")
                    if os.path.isdir(pdir):
                        shutil.rmtree(pdir)
                    os.makedirs(pdir)
                    for k in range(n):
                        d[k].get_pixmap(dpi=args.dpi).save(os.path.join(pdir, f"page-{k + 1:02d}.png"))
                    print(f"wrote {n} page pictures to {pdir}: LOOK at every one")
                d.close()
            except ImportError:
                rows.add("MAN-PDF", "manual", "PDF printed", f"written, {os.path.getsize(pdf_path) // 1024} KiB", "PDF exists", "pass")
                if args.png:
                    rows.add("MAN-PNG", "manual", "page pictures", "PyMuPDF missing", "needs PyMuPDF (fitz)", "could_not_run")
    rows.write(out, "manual_build.py", [steps_path, model_path])
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="assembly manual from steps.toml")
    ap.add_argument("steps", nargs="?", help="steps TOML (default <project>/manual/steps.toml)")
    mc.add_std_args(ap)
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--png", action="store_true", help="page pictures of the PDF (implies --pdf)")
    ap.add_argument("--strict", action="store_true", help="OPEN items fail the check")
    ap.add_argument("--dpi", type=int, default=80)
    args = ap.parse_args(argv)
    try:
        return run(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
