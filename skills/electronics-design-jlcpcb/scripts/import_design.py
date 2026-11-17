"""Bring a design made in another tool into KiCad for review, on a copy, and verify the import.

What it does
    --list                 the board formats the installed KiCad can read (from its reader plugins; formats that
                           are write-only in this KiCad, found by trial, are left out)
    board <file> --out <folder>
                           copies the source file, reads the COPY with KiCad's own reader (the command
                           `kicad-cli pcb import` when the KiCad in use is version 10 or newer, else the reader
                           in KiCad's Python), refills the zones in a separate process, saves a KiCad board and
                           writes an import record: source path, format, SHA-256 of source and result, KiCad
                           version, which reader was used, counts (footprints, pads, nets, copper layers, drill
                           hits, tracks, zones, board size) and everything the reader said.
    verify <imported board> [--netlist F] [--bom F] [--drill F ...] [--gerbers FOLDER]
                           compares the import with exports of the ORIGINAL tool: nets pin by pin (KiCad,
                           Protel/Altium, PADS, IPC-D-356 and Eagle netlists), the part list against the BOM,
                           drill hits per diameter against the drill files, board size and copper layer count
                           against the Gerbers. PASS, FAIL or UNKNOWN per comparison. With the netlist of the
                           imported SCHEMATIC it is the schematic-to-board parity of the import.
    schematic <file> --out <folder>
                           no installed KiCad has a command to import a foreign schematic: the script prepares
                           a COPY and prints the exact clicks for KiCad's own import dialog and the two commands
                           to run afterwards.
    The user's original is never touched: only copies are opened.

Why it exists
    Designs to review arrive from Altium, Eagle, EasyEDA and other tools. An importer is a translator and can
    lose things: pours need a refill and can differ, rules do not carry over, custom pads and 3D models can be
    lost. A review of an unverified import reports the importer's mistakes as the designer's.

Usage
    python -I import_design.py --list
    python -I import_design.py board <file> --out <folder> [--format HINT] [--no-refill]
    python -I import_design.py verify <board.kicad_pcb> [--netlist F] [--bom F] [--drill F ...] [--gerbers FOLDER] [--out FOLDER]
    python -I import_design.py schematic <file> --out <folder>
    Not a project script: no --project, no board.toml.

Exit codes
    0  --list printed; board: imported and saved; verify: every comparison that was asked for is PASS;
       schematic: the copy is prepared (the import itself is still to do by hand)
    1  board: imported, but the reader gave warnings or the zones could not be refilled (read the record);
       verify: a comparison is FAIL or UNKNOWN, or nothing was given to compare with
    2  CANNOT RUN: KiCad not found, a file KiCad cannot read, an unreadable input; also a file that KiCad's
       importer converted into a board that KiCad itself cannot read back (the record then says how to finish
       the import in KiCad's editor). Never a pass.

Which KiCad reads what
    The readers differ between KiCad versions, and a file can defeat one of them. When the KiCad in use cannot
    read a file, the script says so and names a newer KiCad if one is installed (KICAD_BIN chooses it). A board
    written by a newer KiCad cannot be opened by an older one: after such an import the whole project continues
    with the newer KiCad. Nothing appears on the screen in any case: KiCad's log goes to stderr and into the
    record, and every KiCad process runs under kicad_io.run_guarded.

Limits: the importer's own losses (text sizes and fonts, custom pad shapes, 3D models, design rules) are not
measured here; a refilled pour can differ from the original's. Until `verify` passes, every finding on the
import is "found on the import; confirm in the original".
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True     # no __pycache__ in the skill folder, however this file is started

import argparse
import csv
import datetime
import json
import os
import re
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import kicad_io  # noqa: E402
import pcb_common  # noqa: E402

STAGE_TIMEOUT = 600.0               # s for one stage in KiCad's Python
NATIVE = ("KICAD_SEXP", "LEGACY")
SKIP = ("PCB_FILE_UNKNOWN", "FILE_TYPE_NONE")
KNOWN = {            # plugin name -> (what it is, file extensions as people know them)
    "ALTIUM_DESIGNER": ("Altium Designer", ".PcbDoc"), "ALTIUM_CIRCUIT_STUDIO": ("Altium CircuitStudio", ".CSPcbDoc"),
    "ALTIUM_CIRCUIT_MAKER": ("Altium CircuitMaker", ".CMPcbDoc"), "CADSTAR_PCB_ARCHIVE": ("CADSTAR PCB archive", ".cpa"),
    "EAGLE": ("Autodesk Eagle / Fusion electronics (XML, version 6 or newer)", ".brd"), "EASYEDA": ("EasyEDA Standard", ".json"),
    "EASYEDAPRO": ("EasyEDA Professional", ".epro, .zip"), "FABMASTER": ("Fabmaster", ".txt, .fab"), "GEDA_PCB": ("gEDA PCB", ".pcb"),
    "PCAD": ("P-CAD 200x ASCII", ".pcb"), "SOLIDWORKS_PCB": ("SolidWorks PCB", ".SWPcbDoc"), "IPC2581": ("IPC-2581", ".xml"),
    "ODBPP": ("ODB++", ".zip, .tgz"), "PADS": ("PADS ASCII", ".asc"), "ALLEGRO": ("Cadence Allegro", ".brd")}
REF_COLS = ("designator", "designators", "reference", "references", "refdes", "ref", "refs", "parts", "part reference", "reference(s)")


# ---- stages that run with KiCad's Python (each in its own process) ---------------------------------------------------
def _counts(board) -> dict:
    import pcbnew
    mm = pcbnew.ToMM
    pads = holes = 0
    drill = {}
    nets = {}
    refs = []
    for fp in board.GetFootprints():
        refs.append(fp.GetReference())
        for p in fp.Pads():
            pads += 1
            if p.HasHole():
                holes += 1
                d = round(mm(p.GetDrillSize().x), 2)
                drill[d] = drill.get(d, 0) + 1
            n = str(p.GetNetname())
            if n:
                nets.setdefault(n, []).append([fp.GetReference(), str(p.GetNumber())])
    vias = 0
    tracks = 0
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias += 1
            d = round(mm(t.GetDrill()), 2)
            drill[d] = drill.get(d, 0) + 1
        else:
            tracks += 1
    bb = board.GetBoardEdgesBoundingBox()
    return {"footprints": len(refs), "pads": pads, "nets": len(nets), "copper_layers": board.GetCopperLayerCount(),
            "drill_hits": holes + vias, "vias": vias, "tracks": tracks, "zones": len(list(board.Zones())),
            "board_size_mm": [round(mm(bb.GetWidth()), 3), round(mm(bb.GetHeight()), 3)],
            "drill_by_diameter": {f"{k:.2f}": v for k, v in sorted(drill.items())}, "refs": sorted(refs), "net_pins": nets}


def stage_load(src: str, dst: str, report: str) -> int:
    import pcbnew
    out = {"ok": False, "error": "", "format": "", "counts": None}
    try:
        t = pcbnew.PCB_IO_MGR.FindPluginTypeFromBoardPath(src)
        out["format"] = str(pcbnew.PCB_IO_MGR.ShowType(t))
        with open(report, "w", encoding="utf-8") as f:
            json.dump(out, f)                                           # so a crash of the reader leaves the format behind
        if out["format"].upper().startswith("UNKNOWN") or t in (getattr(pcbnew.PCB_IO_MGR, "PCB_FILE_UNKNOWN", 0),
                                                              getattr(pcbnew.PCB_IO_MGR, "FILE_TYPE_NONE", -1)):
            out["error"] = "no reader of this KiCad recognises the file"
            board = None
        else:
            # the type is given: with a file name alone KiCad's Python takes every foreign file for its old .brd format
            board = pcbnew.LoadBoard(src, t)
        if board is None:
            out["error"] = out["error"] or "its reader for this format returned no board and gave no reason"
        else:
            pcbnew.SaveBoard(dst, board)
            out["ok"], out["counts"] = True, _counts(board)
    except Exception as e:                                              # noqa: BLE001  whatever the reader raises
        out["error"] = str(e).strip()[:1500]
    with open(report, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return 0


def stage_refill(path: str) -> int:
    import pcbnew
    board = kicad_io.load_board(path)
    if board is None:
        print("KiCad's Python returned no board for this file", file=sys.stderr)
        return 1
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    kicad_io.save_board(board, path)
    return 0


def stage_count(path: str, report: str) -> int:
    board = kicad_io.load_board(path)
    if board is None:
        print("KiCad's Python returned no board for this file", file=sys.stderr)
        return 1
    with open(report, "w", encoding="utf-8") as f:
        json.dump(_counts(board), f)
    return 0


def stage_list(report: str, tmp: str) -> int:
    """The reader plugins of this KiCad; IPC-2581 and ODB++ by trial on a small board written here."""
    import pcbnew
    m = pcbnew.PCB_IO_MGR
    rows = []
    trial = {}
    try:
        b = pcbnew.BOARD()
        for (x0, y0), (x1, y1) in (((0, 0), (20, 0)), ((20, 0), (20, 10)), ((20, 10), (0, 10)), ((0, 10), (0, 0))):
            s = pcbnew.PCB_SHAPE(b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x0), pcbnew.FromMM(y0)))
            s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetWidth(pcbnew.FromMM(0.1))
            b.Add(s)
        small = os.path.join(tmp, "trial.kicad_pcb")
        pcbnew.SaveBoard(small, b)
        for name, args, fname in (("IPC2581", ["pcb", "export", "ipc2581"], "trial.xml"), ("ODBPP", ["pcb", "export", "odb"], "trial.zip")):
            if not hasattr(m, name):
                continue
            path = os.path.join(tmp, fname)
            r = kicad_io.run_cli(args + ["-o", path, small], timeout=300)
            if r.returncode != 0 or not os.path.exists(path):
                trial[name] = "not tried: this KiCad could not write a file to try with"
                continue
            trial[name] = "read" if m.FindPluginTypeFromBoardPath(path) == getattr(m, name) else \
                "write-only in this KiCad (found by trial: no reader accepts the file it writes)"
    except Exception as e:                                              # noqa: BLE001
        trial["_error"] = str(e)[:300]
    for name in sorted(n for n in dir(m) if n.isupper() and not n.startswith("_") and n not in SKIP):
        t = getattr(m, name)
        if not isinstance(t, int):
            continue
        rows.append({"plugin": name, "kicad_name": str(m.ShowType(t)), "native": name in NATIVE, "trial": trial.get(name, "")})
    with open(report, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "error": trial.get("_error", "")}, f)
    return 0


def _stage(args: list[str], timeout: float | None = None):
    """Run one stage with KiCad's Python; returns (exit code, output). A crash of the reader is an exit code. The
    child sends KiCad's log to stderr (pcb_common.quiet_wx) and is killed if it opens a window or runs too long:
    nothing may ever appear on the user's screen."""
    cmd = [kicad_io.kicad_python(), "-I", "-B", os.path.abspath(__file__)] + args
    rc, text, blocked = pcb_common.run_guarded(cmd, timeout or STAGE_TIMEOUT)
    out = "\n".join(ln for ln in text.splitlines() if ln.strip() and "memory leak" not in ln and "no destructor found" not in ln
                    and "image handler" not in ln)
    if blocked:
        return -1, (out + "\n" if out else "") + "STOPPED: the run with KiCad's Python gave no result: " + blocked
    return rc, out


def _messages(text: str) -> list[str]:
    """The importer's own messages out of a stage's output: the log lines, without clock time, without this
    script's own line about the log and without the lines of a Python traceback."""
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith(("wx log: ", "Traceback (most recent", "File \"", "~", "^")) or ln.startswith("CANNOT RUN: the script stopped"):
            continue
        ln = re.sub(r"^\d\d:\d\d:\d\d: ", "", ln)
        if ln not in out:
            out.append(ln)
    return out


# ---- --list ----------------------------------------------------------------------------------------------------------
def cmd_list() -> int:
    kc = kicad_io.require_kicad()
    with kicad_io.private_tmp("import-list-") as tmp:
        rep = os.path.join(tmp, "list.json")
        rc, out = _stage(["--stage-list", rep, tmp], 600)
        if not os.path.isfile(rep):
            raise kicad_io.KicadIOError("the reader plugins of KiCad's Python could not be listed: " + out[-400:])
        with open(rep, encoding="utf-8") as f:
            data = json.load(f)
    print(f"Board formats that KiCad {kc.version} can read (reader plugins of its Python):")
    left_out = []
    for r in data["rows"]:
        what, ext = KNOWN.get(r["plugin"], (r["kicad_name"], "?"))
        if r["native"]:
            continue
        if r["trial"].startswith("write-only") or r["trial"].startswith("not tried"):
            left_out.append(f"  {what} ({r['kicad_name']}): {r['trial']}")
            continue
        print(f"  {what:60} {ext:16} {'(reads its own export: tried)' if r['trial'] == 'read' else ''}")
    print("  KiCad's own boards (.kicad_pcb, and the legacy .brd format)")
    if left_out:
        print("Listed by KiCad but not readable:")
        print("\n".join(left_out))
    if kc.major >= 10:
        r = kicad_io.run_cli(["pcb", "import", "--help"], timeout=60)
        m = re.search(r"Input format hint: ([^\n(]+)", r.stdout or "")
        print(f"This KiCad also has the command `kicad-cli pcb import`" + (f" (format hints: {m.group(1).strip()})" if m else "")
              + "; `import_design.py board` uses it.")
    else:
        print("This KiCad has no `kicad-cli pcb import` command (KiCad 10 and newer have it): the Python reader is used.")
    print("Schematics of other tools: no command-line import in any installed KiCad; see `import_design.py schematic`.")
    if data.get("error"):
        print("note: the read trial could not be made: " + data["error"])
    return 0


# ---- board -----------------------------------------------------------------------------------------------------------
def _newer_kicad(kc) -> str:
    """What to tell the user when this KiCad cannot read a file that a newer one may read."""
    newer = [k for k in kicad_io.list_installs() if k.major > kc.major]
    if newer:
        n = newer[0]
        have = f"KiCad {n.version} is installed on this machine: set KICAD_BIN to `{n.bin_dir}` and run this command again"
    else:
        have = "no newer KiCad is installed on this machine; after installing one, set KICAD_BIN to its bin folder and run this command again"
    return (f"A newer KiCad can read files that KiCad {kc.version} cannot (KiCad 10 and newer have their own import "
            f"command); {have}. The board that a newer KiCad writes is in its own file format, which KiCad {kc.version} "
            f"cannot open: from then on the whole project (schematic, board, every script of this skill) continues with "
            f"that newer KiCad.")


def _load_message(board: str) -> str:
    """KiCad's own words about a board file it cannot load ('' when kicad-cli loads it): asked by a harmless export."""
    with kicad_io.private_tmp("import-probe-") as tmp:
        try:
            r = kicad_io.run_cli(["pcb", "export", "ipcd356", "-o", os.path.join(tmp, "probe.d356"), board], timeout=STAGE_TIMEOUT)
        except kicad_io.KicadIOError as e:
            return str(e)
    return "" if r.returncode == 0 else " ".join(((r.stdout or "") + " " + (r.stderr or "")).split())[:600]


def cmd_board(a) -> int:
    kc = kicad_io.require_kicad()
    src = os.path.abspath(a.file)
    if not os.path.isfile(src):
        raise kicad_io.KicadIOError(f"no such file: {src}")
    out = os.path.abspath(a.out)
    if os.path.normcase(out) == os.path.normcase(os.path.dirname(src)):
        raise kicad_io.KicadIOError("--out must not be the folder of the original design")
    os.makedirs(out, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_.+-]+", "_", os.path.splitext(os.path.basename(src))[0]).strip("_") or "imported"
    dst = os.path.join(out, name + ".kicad_pcb")
    record = {"script": "import_design.py board", "when": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "source": src, "source_sha256": kicad_io.sha256(src), "kicad": kc.version, "reader": "", "format": "", "result_file": dst,
              "result_sha256": None, "counts": None, "warnings": [], "screen": "", "refill": "", "readable": True,
              "verified": "no: run import_design.py verify"}
    counts, unreadable = None, ""
    with kicad_io.private_tmp("import-design-") as tmp:
        copy = os.path.join(tmp, os.path.basename(src))
        shutil.copyfile(src, copy)                                       # the original is never opened by KiCad
        work = os.path.join(tmp, name + ".kicad_pcb")
        done = False
        if kc.major >= 10:
            rep = os.path.join(tmp, "report.json")
            args = ["pcb", "import", "-o", work, "--report-format", "json", "--report-file", rep]
            if a.format:
                args += ["--format", a.format]
            r = kicad_io.run_cli(args + [copy], timeout=STAGE_TIMEOUT)
            text = ((r.stdout or "") + (r.stderr or "")).strip()
            if r.returncode == 0 and os.path.isfile(work):
                done, record["reader"] = True, f"kicad-cli pcb import (KiCad {kc.version})"
                rj = {}
                if os.path.isfile(rep):
                    try:
                        with open(rep, encoding="utf-8") as f:
                            rj = json.load(f)
                    except ValueError:
                        pass
                record["cli_report"] = rj
                record["format"] = str(rj.get("source_format") or a.format or "detected by kicad-cli")
                record["warnings"] += [str(w) for w in rj.get("errors", []) + rj.get("warnings", [])]
                record["screen"] = "kicad-cli's import report"
            else:
                record["warnings"].append("kicad-cli pcb import could not read the file (" + " ".join(text.split())[-300:]
                                          + "); the reader in KiCad's Python was used instead")
        if not done:
            rep = os.path.join(tmp, "load.json")
            rc, text = _stage(["--stage-load", copy, work, rep])
            info = {}
            if os.path.isfile(rep):
                with open(rep, encoding="utf-8") as f:
                    info = json.load(f)
            record["format"] = info.get("format", "")
            if not info.get("ok"):
                said = "; ".join(_messages(text))[-400:]
                why = info.get("error") or (f"its reader stopped without a message (exit code {rc})" + (": " + said if said else ""))
                raise kicad_io.KicadIOError(f"KiCad {kc.version} cannot read {os.path.basename(src)} (format: "
                                            f"{record['format'] or 'not recognised; see --list'}): {why}. {_newer_kicad(kc)}")
            record["reader"] = f"reader in KiCad's Python (pcbnew.LoadBoard, KiCad {kc.version})"
            record["warnings"] += _messages(text)
            record["screen"] = "KiCad's log, " + next((ln[8:] for ln in text.splitlines() if ln.startswith("wx log: ")), "sent to stderr")
        # ---- can the result be read back? (an importer can write a board that KiCad itself then refuses)
        rep = os.path.join(tmp, "count.json")
        rc, text = _stage(["--stage-count", work, rep])
        if rc == 0 and os.path.isfile(rep):
            if not a.no_refill:
                rc2, text2 = _stage(["--stage-refill", work])
                record["refill"] = "zones refilled in a separate process" if rc2 == 0 else \
                    "REFILL FAILED: " + "; ".join(_messages(text2))[-300:]
            else:
                record["refill"] = "not refilled (--no-refill)"
            with open(rep, encoding="utf-8") as f:
                counts = json.load(f)
        else:
            unreadable = _load_message(work) or "; ".join(_messages(text))[-400:] or "KiCad gave no reason"
            record["readable"], record["refill"] = False, "not refilled (the board could not be read back)"
        for ext in (".kicad_pcb", ".kicad_pro"):
            if os.path.isfile(work[:-len(".kicad_pcb")] + ext):
                kicad_io.atomic_copy(work[:-len(".kicad_pcb")] + ext, dst[:-len(".kicad_pcb")] + ext)
    record["result_sha256"] = kicad_io.sha256(dst)
    stats = (record.get("cli_report") or {}).get("statistics") or {}
    md = ["# Import record", "", f"Script `import_design.py board`, {record['when']}.", "",
          "| Item | Value |", "|---|---|", f"| Source (never opened; a copy was read) | `{src}` |",
          f"| Source SHA-256 | `{record['source_sha256']}` |", f"| Format | {record['format']} |", f"| Reader | {record['reader']} |",
          f"| Result | `{dst}` |", f"| Result SHA-256 | `{record['result_sha256']}` |", f"| Zones | {record['refill']} |"]
    if counts:
        record["counts"] = c = {k: v for k, v in counts.items() if k not in ("refs", "net_pins")}
        md += [f"| Footprints | {c['footprints']} |", f"| Pads | {c['pads']} |", f"| Nets | {c['nets']} |", f"| Copper layers | {c['copper_layers']} |",
               f"| Drill hits (pad holes + vias) | {c['drill_hits']} ({c['vias']} vias) |", f"| Tracks; zones | {c['tracks']}; {c['zones']} |",
               f"| Board size (mm) | {c['board_size_mm'][0]} x {c['board_size_mm'][1]} |",
               f"| Drill hits by diameter (mm) | {', '.join(f'{k}: {v}' for k, v in c['drill_by_diameter'].items()) or '-'} |"]
    else:
        record["unreadable"] = unreadable
        md += [f"| Counts as the importer reported them | {', '.join(f'{k} {v}' for k, v in stats.items()) or 'none reported'} |"]
        steps = [f"1. Open KiCad {kc.version}, then its PCB Editor, and open `{dst}` (a file made here; the original is untouched).",
                 "2. Resolve what the editor reports (for items on layers that the importer could not map: put each on a layer "
                 "of your choice, for example a user drawing layer), then File > Save.",
                 f"3. Run `python -I import_design.py verify \"{dst}\" ...` with the exports of the original tool; the checks of "
                 "the skill can read the board from then on.",
                 "(Steps 1 and 2 were not tried by the script: it never opens a KiCad window.)"]
        md += ["", "## NOT USABLE YET: KiCad cannot read back the board that its importer wrote", "",
               f"KiCad {kc.version} says: \"{unreadable}\"", "",
               "The importer converted the file, but the result needs a decision that only KiCad's own editor asks for. "
               "No script of this skill can read this board until that is done:", ""] + steps
    md += ["", "## What the importer skipped or changed (its own messages)", ""]
    md += [f"- {w}" for w in record["warnings"]] or ["Nothing: the reader gave no message."]
    mapping = (record.get("cli_report") or {}).get("layer_mapping") or {}
    if mapping:
        md += ["", f"Layers as the importer mapped them ({len(mapping)}): " +
               ", ".join(f"{k} -> {v.get('kicad_layer', '?')}" for k, v in mapping.items() if isinstance(v, dict)) + "."]
    md += ["", "These messages were collected from " + (record.get("screen") or "KiCad's output") +
           "; no window was shown. Each one is a difference between the original and the import: check it in the verification."]
    md += ["", "## Not verified yet", "",
           "Compare with exports of the original tool: `import_design.py verify <this board> --netlist ... --bom ... --drill ... "
           "--gerbers ...`. Known weak spots of imports: refilled pours can differ; design rules do not carry over; text "
           "sizes and fonts shift; custom pad shapes and 3D models can be lost. Until the import is verified, every finding is "
           "\"found on the import; confirm in the original\"."]
    kicad_io.atomic_write(os.path.join(out, "import_record.md"), "\n".join(md) + "\n")
    kicad_io.atomic_write(os.path.join(out, "import_record.json"), json.dumps(record, indent=1) + "\n")
    for w in record["warnings"][:15]:
        print("  importer:", w[:200])
    if len(record["warnings"]) > 15:
        print(f"  ... and {len(record['warnings']) - 15} more message(s) in the record")
    if not counts:
        print(f"record: {os.path.join(out, 'import_record.md')}")
        raise kicad_io.KicadIOError(f"{record['reader']} converted {os.path.basename(src)}, but KiCad {kc.version} cannot read "
                                    f"back the board it wrote ({unreadable}). The file is kept as {dst}; the record says how to "
                                    f"finish the import in KiCad's PCB Editor. Nothing was checked.")
    ok = not record["warnings"] and not record["refill"].startswith("REFILL FAILED")
    print(f"{'IMPORTED' if ok else 'IMPORTED WITH REMARKS'}: {c['footprints']} footprints, {c['pads']} pads, {c['nets']} nets, "
          f"{c['copper_layers']} copper layers, {c['board_size_mm'][0]} x {c['board_size_mm'][1]} mm -> {dst}")
    print(f"record: {os.path.join(out, 'import_record.md')}; not verified yet")
    return 0 if ok else 1


# ---- verify ----------------------------------------------------------------------------------------------------------
def read_any_netlist(path: str):
    """({net name: set of (ref, pin)}, format name) from a netlist of several tools; (None, why) when not recognised."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError as e:
        return None, str(e)
    head = txt.lstrip()[:400]
    nets: dict[str, set] = {}
    if head.startswith("(export"):
        try:
            n = kicad_io.read_netlist(path)
        except kicad_io.KicadIOError as e:
            return None, str(e)
        return {k: set(v) for k, v in n.nets.items()}, "KiCad"
    if re.search(r"^\s*(317|327)", txt, re.M) and ("IPC-D-356" in txt or re.search(r"^C\s", txt, re.M) or re.search(r"^P\s", txt, re.M)):
        for ln in txt.splitlines():
            if ln[:3] in ("317", "327") and len(ln) > 30:
                net, ref, pin = ln[3:17].strip(), ln[20:26].strip(), ln[27:31].strip().lstrip("-")
                if ref and ref.upper() != "VIA" and net and net != "N/C":
                    nets.setdefault(net, set()).add((ref, pin))
        return (nets, "IPC-D-356") if nets else (None, "an IPC-D-356 file without part records")
    if "*SIGNAL*" in txt or "*NET*" in txt:
        cur = None
        for ln in txt.splitlines():
            s = ln.strip()
            if s.startswith("*SIGNAL*") or s.startswith("*SIG*"):
                cur = s.split(None, 1)[1].split()[0] if len(s.split()) > 1 else None
            elif s.startswith("*"):
                cur = None if not s.startswith("*NET*") else cur
            elif cur:
                for tok in s.split():
                    if "." in tok:
                        ref, pin = tok.rsplit(".", 1)
                        nets.setdefault(cur, set()).add((ref, pin))
        return (nets, "PADS") if nets else (None, "a PADS netlist without signals")
    if re.search(r"^\(\s*$", txt, re.M) and re.search(r"^\[\s*$", txt, re.M):
        lines = [ln.strip() for ln in txt.splitlines()]
        i = 0
        while i < len(lines):
            if lines[i] == "(":
                name = lines[i + 1] if i + 1 < len(lines) else ""
                i += 2
                while i < len(lines) and lines[i] != ")":
                    m = re.match(r"(.+)-([^-\s]+)$", lines[i].split()[0]) if lines[i] else None
                    if m:
                        nets.setdefault(name, set()).add((m.group(1), m.group(2)))
                    i += 1
            i += 1
        return (nets, "Protel / Altium") if nets else (None, "a Protel netlist without nets")
    if re.search(r"^Net\s+Part\s+Pad", txt, re.M):
        cur = None
        started = False
        for ln in txt.splitlines():
            if re.match(r"^Net\s+Part\s+Pad", ln):
                started = True
                continue
            if not started or not ln.strip():
                continue
            parts = ln.split()
            if not ln[0].isspace() and len(parts) >= 3:
                cur, parts = parts[0], parts[1:]
            if cur and len(parts) >= 2:
                nets.setdefault(cur, set()).add((parts[0], parts[1]))
        return (nets, "Eagle") if nets else (None, "an Eagle netlist without nets")
    return None, "the netlist format was not recognised (KiCad, Protel/Altium, PADS, IPC-D-356 and Eagle are read)"


def read_bom_refs(path: str):
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            txt = f.read()
    except OSError as e:
        return None, str(e)
    try:
        dialect = csv.Sniffer().sniff(txt[:4000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(txt.splitlines(), dialect))
    for hi, row in enumerate(rows[:15]):
        low = [c.strip().lower() for c in row]
        col = next((i for i, c in enumerate(low) if c in REF_COLS), None)
        if col is not None:
            refs = set()
            for r in rows[hi + 1:]:
                if col < len(r):
                    refs.update(t for t in re.split(r"[,\s;]+", r[col].strip()) if t)
            return refs, f"column '{row[col].strip()}'"
    return None, "no designator column found (looked for: designator, reference, refdes, ref, parts)"


def cmd_verify(a) -> int:
    kicad_io.require_kicad()
    board = os.path.abspath(a.board)
    if not os.path.isfile(board):
        raise kicad_io.KicadIOError(f"no such board file: {board}")
    with kicad_io.private_tmp("import-verify-") as tmp:
        work = os.path.join(tmp, os.path.basename(board))
        kicad_io.copy_board(board, work, lock_source=False)
        rep = os.path.join(tmp, "count.json")
        rc, text = _stage(["--stage-count", work, rep])
        if rc != 0 or not os.path.isfile(rep):
            raise kicad_io.KicadIOError("the board could not be read: " + text[-300:])
        with open(rep, encoding="utf-8") as f:
            c = json.load(f)
    rows = []                       # (comparison, result, detail)
    lists = {}                      # the complete lists behind the details, for the JSON twin
    board_nets = {k: {tuple(p) for p in v} for k, v in c["net_pins"].items()}
    refs = set(c["refs"])
    if a.netlist:
        nets, fmt = read_any_netlist(a.netlist)
        if nets is None:
            rows.append(("Nets against the netlist", "UNKNOWN", fmt))
        else:
            cut_short = []                  # parts that this netlist format cannot name
            if fmt == "IPC-D-356":          # the format keeps 6 characters of a reference
                cut = {}
                for r in refs:
                    if len(r) > 6:
                        cut.setdefault(r[:6], []).append(r)
                ren = {k: v[0] for k, v in cut.items() if len(v) == 1 and k not in refs}
                cut_short = sorted(r for k, v in cut.items() if k not in ren for r in v)
                nets = {n: {(ren.get(r, r), q) for r, q in pins if r not in cut or r in ren} for n, pins in nets.items()}
            nl_refs = {r for pins in nets.values() for r, _ in pins}
            common = (refs & nl_refs) - set(cut_short)
            bparts = {frozenset(p for p in pins if p[0] in common) for pins in board_nets.values()}
            nparts = {frozenset(p for p in pins if p[0] in common) for pins in nets.values()}
            bparts = {p for p in bparts if len(p) > 1}
            nparts = {p for p in nparts if len(p) > 1}
            only_n, only_b = nparts - bparts, bparts - nparts
            missing = sorted(nl_refs - refs)
            extra = sorted(r for r in refs - nl_refs if r not in cut_short)
            ok = not only_n and not only_b and not missing
            detail = (f"{fmt} netlist: {len(nparts)} nets with two or more pins, {len(nl_refs)} parts; board: {len(bparts)} such nets, "
                      f"{len(refs)} footprints")
            if only_n:
                ex = "; ".join(", ".join(f"{r}.{p}" for r, p in sorted(s)[:6]) + (" ..." if len(s) > 6 else "") for s in list(only_n)[:5])
                detail += f". {len(only_n)} net(s) of the netlist are not one net on the board, e.g. [{ex}]"
            if only_b:
                detail += f". {len(only_b)} net(s) of the board are not one net in the netlist"
            if missing:
                detail += f". Parts of the netlist that are not on the board: {', '.join(missing[:15])}{' ...' if len(missing) > 15 else ''}"
            if extra:
                detail += f". Footprints that the netlist does not know (mechanical parts?): {', '.join(extra[:15])}{' ...' if len(extra) > 15 else ''}"
            if cut_short:
                detail += (f". NOT COMPARED: {len(cut_short)} part(s) whose references are longer than 6 characters and share their "
                           f"first 6 (an IPC-D-356 file keeps only 6): {', '.join(cut_short[:15])}{' ...' if len(cut_short) > 15 else ''}")
            rows.append(("Nets against the netlist (pin by pin, names ignored)",
                         "FAIL" if not ok else "UNKNOWN" if cut_short else "PASS", detail))
            lists["netlist"] = {"parts_not_on_board": missing, "footprints_not_in_netlist": extra, "not_compared": cut_short,
                                "nets_of_netlist_not_one_net_on_board": [sorted(f"{r}.{q}" for r, q in n) for n in only_n],
                                "nets_of_board_not_one_net_in_netlist": [sorted(f"{r}.{q}" for r, q in n) for n in only_b]}
    if a.bom:
        brefs, how = read_bom_refs(a.bom)
        if brefs is None:
            rows.append(("Parts against the BOM", "UNKNOWN", how))
        else:
            miss, extra = sorted(brefs - refs), sorted(refs - brefs)
            detail = f"BOM ({how}): {len(brefs)} designators; board: {len(refs)} footprints"
            if miss:
                detail += f". In the BOM but not on the board: {', '.join(miss[:20])}{' ...' if len(miss) > 20 else ''}"
            if extra:
                detail += f". On the board but not in the BOM: {', '.join(extra[:20])}{' ...' if len(extra) > 20 else ''}"
            rows.append(("Parts against the BOM", "PASS" if not miss and not extra else "FAIL", detail))
            lists["bom"] = {"in_bom_not_on_board": miss, "on_board_not_in_bom": extra}
    if a.drill:
        import edge_check
        total, by_d, notes, bad = 0, {}, [], False
        for path in a.drill:
            try:
                d = edge_check.read_drill(path)
            except kicad_io.KicadIOError as e:
                notes.append(str(e))
                bad = True
                continue
            for _, _, dia in d.holes:
                by_d[round(dia, 2)] = by_d.get(round(dia, 2), 0) + 1
            for s in d.slots:
                by_d[round(s[4], 2)] = by_d.get(round(s[4], 2), 0) + 1
            total += len(d.holes) + len(d.slots)
            notes += d.notes
        bd = {float(k): v for k, v in c["drill_by_diameter"].items()}
        if bad:
            rows.append(("Drill hits against the drill files", "UNKNOWN", "; ".join(notes)))
        else:
            same = total == c["drill_hits"] and by_d == bd
            diff = sorted(set(by_d) | set(bd))
            detail = (f"drill files: {total} hits; board: {c['drill_hits']} (pad holes + vias)" + ("" if same else ". Per diameter (file / board): "
                      + ", ".join(f"{k:.2f}: {by_d.get(k, 0)} / {bd.get(k, 0)}" for k in diff if by_d.get(k, 0) != bd.get(k, 0))))
            rows.append(("Drill hits against the drill files (per diameter)", "PASS" if same else "FAIL", detail + ("; " + "; ".join(notes) if notes else "")))
    if a.gerbers:
        import edge_check
        files = edge_check.find_files(os.path.abspath(a.gerbers))
        prof = [g for g in files["gerbers"] if g[1] == "outline" and g[3] is not None]
        cu = [g for g in files["gerbers"] if g[1] == "copper"]
        if not prof:
            rows.append(("Board size against the Gerber outline", "UNKNOWN", "no readable outline Gerber in the folder"))
        else:
            bb = prof[0][3].bbox()
            size = (bb[2] - bb[0], bb[3] - bb[1]) if bb else (0, 0)
            bs = c["board_size_mm"]
            # the board's box includes the outline's line width; allow it
            ok = abs(size[0] - bs[0]) <= 0.25 and abs(size[1] - bs[1]) <= 0.25
            rows.append(("Board size against the Gerber outline", "PASS" if ok else "FAIL",
                         f"Gerber outline {size[0]:.2f} x {size[1]:.2f} mm; board {bs[0]:.2f} x {bs[1]:.2f} mm (0.25 mm allowed for line width)"))
        if not cu:
            rows.append(("Copper layers against the Gerbers", "UNKNOWN", "no copper Gerber recognised in the folder"))
        else:
            rows.append(("Copper layers against the Gerbers", "PASS" if len(cu) == c["copper_layers"] else "FAIL",
                         f"{len(cu)} copper Gerber(s); board {c['copper_layers']} copper layers"))
    if not rows:
        rows.append(("Anything", "UNKNOWN", "no export of the original tool was given: nothing was compared (--netlist, --bom, --drill, --gerbers)"))
    ok = all(r[1] == "PASS" for r in rows)
    out = os.path.abspath(a.out) if a.out else None
    md = ["# Import verification", "", f"Script `import_design.py verify`; board `{os.path.basename(board)}`, SHA-256 `{kicad_io.sha256(board)}`.", "",
          f"Board as imported: {c['footprints']} footprints, {c['pads']} pads, {c['nets']} nets, {c['copper_layers']} copper layers, "
          f"{c['drill_hits']} drill hits, {c['board_size_mm'][0]} x {c['board_size_mm'][1]} mm.", "",
          "| Comparison | Result | Detail |", "|---|---|---|"] + [f"| {n} | {r} | {d} |" for n, r, d in rows]
    md += ["", f"**Result: {'PASS' if ok else 'FAIL (a FAIL or UNKNOWN comparison is not a pass)'}**", "",
           "Not compared: copper shapes (look at the imported board and the original Gerbers side by side with "
           "review_images.py), pours, text, 3D models. A comparison lists at most the first names; the JSON twin "
           "(with --out) holds every one. The BOM comparison is strict: a footprint that the BOM does not list "
           "(a mounting hole, an unfitted part) is a difference to explain, not an error of the import by itself."]
    if out:
        os.makedirs(out, exist_ok=True)
        kicad_io.atomic_write(os.path.join(out, "import_verify.md"), "\n".join(md) + "\n")
        kicad_io.atomic_write(os.path.join(out, "import_verify.json"), json.dumps(
            {"script": "import_design.py verify", "result": "PASS" if ok else "FAIL", "board": board,
             "rows": [{"comparison": n, "result": r, "detail": d} for n, r, d in rows], "lists": lists}, indent=1) + "\n")
    for n, r, d in rows:
        print(f"{r}  {n}: {d[:300]}")
    print("PASS" if ok else "FAIL (a FAIL or UNKNOWN comparison is not a pass)")
    return 0 if ok else 1


# ---- schematic -------------------------------------------------------------------------------------------------------
def cmd_schematic(a) -> int:
    kc = kicad_io.find_kicad()
    src = os.path.abspath(a.file)
    if not os.path.isfile(src):
        raise kicad_io.KicadIOError(f"no such file: {src}")
    out = os.path.abspath(a.out)
    if os.path.normcase(out) == os.path.normcase(os.path.dirname(src)):
        raise kicad_io.KicadIOError("--out must not be the folder of the original design")
    work = os.path.join(out, "schematic_source")
    os.makedirs(work, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    copied = []
    for n in sorted(os.listdir(os.path.dirname(src))):                  # the file and its companions of the same name
        p = os.path.join(os.path.dirname(src), n)
        if os.path.isfile(p) and (n == os.path.basename(src) or os.path.splitext(n)[0] == stem):
            shutil.copyfile(p, os.path.join(work, n))
            copied.append(n)
    copy = os.path.join(work, os.path.basename(src))
    name = re.sub(r"[^A-Za-z0-9_.+-]+", "_", stem).strip("_") or "imported"
    target = os.path.join(out, name + ".kicad_sch")
    steps = [
        f"NOT IMPORTED: KiCad{' ' + kc.version if kc else ''} has no command to import a schematic of another tool. A copy is ready; "
        "the import takes three clicks in KiCad itself:",
        f"  copy of the schematic: {copy}   (SHA-256 {kicad_io.sha256(copy)}; {len(copied)} file(s) copied; the original was not opened)",
        "  1. Open KiCad, then the Schematic Editor (an empty one).",
        "  2. File > Import > Non-KiCad Schematic...  and choose the copy above.",
        "     (For a whole project of Altium, CADSTAR, Eagle or EasyEDA: in the KiCad project window, File > Import Non-KiCad",
        "      Project > the tool's name, choose the copy, and give this folder as the target: " + out + ")",
        f"  3. File > Save As...  {target}",
        "  (Menu names as in KiCad 9; other versions may word them slightly differently.)",
        "Then, to verify the import against the imported board:",
        f"  kicad-cli sch export netlist --format kicadsexpr -o \"{os.path.join(out, name + '.net')}\" \"{target}\"",
        f"  python -I import_design.py verify <imported board .kicad_pcb> --netlist \"{os.path.join(out, name + '.net')}\"",
        "and against a netlist exported from the original tool with netlist_compare.py.",
    ]
    kicad_io.atomic_write(os.path.join(out, "schematic_import_steps.md"), "# Schematic import: steps to do by hand\n\n" + "\n".join(steps) + "\n")
    print("\n".join(steps))
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0].startswith("--stage-"):
        print("wx log:", pcb_common.quiet_wx(), file=sys.stderr)     # before any pcbnew call: no message box, ever
    if argv and argv[0] == "--stage-load" and len(argv) == 4:
        return stage_load(argv[1], argv[2], argv[3])
    if argv and argv[0] == "--stage-refill" and len(argv) == 2:
        return stage_refill(argv[1])
    if argv and argv[0] == "--stage-count" and len(argv) == 3:
        return stage_count(argv[1], argv[2])
    if argv and argv[0] == "--stage-list" and len(argv) == 3:
        return stage_list(argv[1], argv[2])
    ap = argparse.ArgumentParser(description="Bring a design of another tool into KiCad on a copy, and verify the import.",
                                 epilog="Exit codes: 0 done / pass, 1 remarks / fail / unknown, 2 could not run.")
    ap.add_argument("--list", action="store_true", help="print the board formats the installed KiCad can read")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("board", help="import a board file of another tool")
    b.add_argument("file")
    b.add_argument("--out", required=True, help="folder for the KiCad board and the import record")
    b.add_argument("--format", help="format hint for kicad-cli pcb import (KiCad 10 and newer)")
    b.add_argument("--no-refill", action="store_true", dest="no_refill", help="do not refill the zones")
    v = sub.add_parser("verify", help="compare an imported board with exports of the original tool")
    v.add_argument("board")
    v.add_argument("--netlist", help="a netlist exported by the original tool, or of the imported schematic")
    v.add_argument("--bom", help="the original tool's BOM (CSV)")
    v.add_argument("--drill", nargs="+", help="the original tool's drill file(s)")
    v.add_argument("--gerbers", help="folder of the original tool's Gerber files")
    v.add_argument("--out", help="folder for import_verify.md (default: print only)")
    s = sub.add_parser("schematic", help="prepare a copy of a foreign schematic and print the import clicks")
    s.add_argument("file")
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.list:
        return cmd_list()
    if a.cmd == "board":
        return cmd_board(a)
    if a.cmd == "verify":
        return cmd_verify(a)
    if a.cmd == "schematic":
        return cmd_schematic(a)
    ap.print_usage(sys.stderr)
    print("CANNOT RUN: give --list, or one of: board, verify, schematic", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(kicad_io.run_main(main))
