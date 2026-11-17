"""Freezes a set of files for a review or an order: a checked copy in reviews/frozen/<name>/ and a manifest of checksums.

What it does
    1. Refuses to freeze anything stale. It runs `build.py --check-only` (every expected output must exist and be newer than
       its inputs) and applies the rule of `check_all.py` to `out/checks/` (a check file whose recorded input changed
       afterwards is STALE). Either one is exit 1 and nothing is copied.
    2. Copies the files of the chosen profile into `<project>/reviews/frozen/<name>/`, laid out as the mech folder
       (the same relative paths, `mech.toml` at the top when the profile has it):
         review   mech.toml, suppliers/, model/, interface*.json, vendor3d/, cables/ (but NOT routes.toml and
                  second_measure.toml unless named with --include: the second measure must not see the first route),
                  out/step/, out/views/, out/renders/, out/drawings/, out/checks/, out/CHECKS.md (when check_all.py
                  made it), and the board file that an
                  interface*.json names as `board_file` when it lies inside the project (the board-file checksum row
                  of the interface check needs it)
         visual   pictures only: out/views/, out/renders/, out/drawings/pages/, out/silk/*.png, out/cables/*.png
                  (png, jpg, jpeg, gif, webp); no mech.toml, no text
         order    out/upload/ (every file), the field sheets and remarks under orders/ (FIELD_SHEET*, REMARK*) and
                  out/cables/FIELD_SHEET_cables.md
       `--include` adds files of the project by glob (relative to the mech folder, `**` allowed) to any profile.
       Nothing under `__pycache__`, no `.pyc`, nothing already under `reviews/frozen/`.
    3. Writes `<project>/reviews/frozen/<name>.MANIFEST.sha256` beside the folder: one line `<sha256>  <path>` per file
       (paths relative to the set folder, forward slashes, sorted), the format of `sha256sum -c`
       (`cd reviews/frozen/<name> && sha256sum -c ../<name>.MANIFEST.sha256`). Every file is hashed before and after its
       copy; a file that changed while it was copied aborts the freeze and leaves nothing behind.
    4. Prints the lines to paste into the `frozen:` block of the state file: the manifest's own sha256 and, for a small
       set, each file's.
    Never overwrites: a set (folder or manifest) of that name that exists is exit 2 and left exactly as it was. The script
    itself writes no check file; the build check it runs rewrites `out/checks/build.json` first, so the copy carries that one.

Why it exists (the real failure, told without names)
    Frozen sets were copied by hand with a checksum list made by hand. One copy was taken while the build had stopped at
    an earlier failing step, so the reviewer received a STALE 3D file and stale pictures and reported a fault that had
    already been fixed; another copy lacked the board file, so the reviewer could not reproduce the board-file checksum
    row; and a set made only of pictures for a visual review had no name in the skill at all.

Usage
    python -I freeze.py --project <mech folder> --name <set> --profile review|visual|order [--include GLOB ...] [--out DIR]
    --name      letters, digits, . _ - (e.g. print-r1, order-r1, rev-A)
    --include   one or more globs relative to the mech folder (an include that matches nothing is exit 2)
    --out       the folder with the generated files (default <project>/out, or [paths] out)

Config keys (mech.toml)
    [paths] out        [build] steps, inputs (read by `build.py --check-only`)      [cables] routes, second

Exit codes
    0 frozen (the manifest line is printed)   1 refused: the build is stale or an output is missing, or a check file is
    stale, or a file changed while it was copied   2 could not run: bad name or profile, the set already exists, the
    build check could not run, an include matched nothing, nothing to freeze
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import glob
import hashlib
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mech_common as mc  # noqa: E402
import check_all as ca  # noqa: E402

PROFILES = ("review", "visual", "order")
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp")
SMALL_SET = 40          # a set of at most this many files has every file line printed for the state file


class Refused(Exception):
    """The freeze is refused (exit 1 or 2): `code` says which."""

    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


# ---------------------------------------------------------------- what goes into a set --------------------------------
def _expand(base: str, pattern: str) -> list[str]:
    """Absolute paths of the regular files matched by `pattern` under `base` (`**` goes through every level). A pattern that names a
    folder means all the files under it."""
    probe = os.path.join(base, pattern)
    if os.path.isdir(probe):
        pattern = pattern.rstrip("/\\") + "/**"
    return [h for h in glob.glob(os.path.join(base, pattern), recursive=True) if os.path.isfile(h) and not os.path.islink(h)]


def _board_files(project: str) -> list[str]:
    """The board files named by `board_file` in the project's interface*.json that lie inside the project."""
    out = []
    for p in sorted(glob.glob(os.path.join(project, "interface*.json"))):
        try:
            bf = mc.load_json(p).get("board_file")
        except (ValueError, OSError, AttributeError):
            continue
        if not isinstance(bf, str) or not bf:
            continue
        cand = bf if os.path.isabs(bf) else os.path.join(project, bf)
        if os.path.isfile(cand) and _inside(cand, project):
            out.append(cand)
    return out


def _inside(path: str, folder: str) -> bool:
    try:
        return os.path.commonpath([os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))]) == os.path.normcase(os.path.abspath(folder))
    except ValueError:                                   # another drive
        return False


def profile_files(job, profile: str, includes: list[str]) -> dict[str, str]:
    """{path inside the set (forward slashes): absolute source file} for the profile and the includes."""
    project, out = job.project, job.out
    cfg_c = job.cfg.get("cables") or {}
    pats: list[tuple[str, str, tuple]] = []            # (base folder, glob, allowed extensions or ())
    if profile == "review":
        pats += [(project, "mech.toml", ()), (project, "suppliers/**", ()), (project, "model/**", ()), (project, "interface*.json", ()),
                 (project, "vendor3d/**", ()), (project, "cables/**", ()),
                 (out, "step/**", ()), (out, "views/**", ()), (out, "renders/**", ()), (out, "drawings/**", ()), (out, "checks/**", ()), (out, "CHECKS.md", ())]
    elif profile == "visual":
        pats += [(out, "views/**", IMAGES), (out, "renders/**", IMAGES), (out, "drawings/pages/**", IMAGES),
                 (out, "silk/*", IMAGES), (out, "cables/*", IMAGES)]
    else:
        pats += [(out, "upload/**", ()), (project, "orders/**/FIELD_SHEET*", ()), (project, "orders/**/REMARK*", ()),
                 (out, "cables/FIELD_SHEET_cables.md", ())]
    found: dict[str, str] = {}

    def put(src: str, base: str, prefix: str = ""):
        rel = os.path.relpath(src, base).replace("\\", "/")
        parts = rel.split("/")
        if "__pycache__" in parts or rel.endswith(".pyc") or rel.endswith(".tmp"):
            return
        full = prefix + rel
        if full.startswith("reviews/frozen/"):
            return
        found[full] = os.path.abspath(src)

    for base, pat, exts in pats:
        for src in _expand(base, pat):
            if exts and os.path.splitext(src)[1].lower() not in exts:
                continue
            if base == out and not _inside(out, project):
                put(src, out, "out/")
            elif base == out:
                put(src, project)
            else:
                put(src, project)
    if profile == "review":
        for src in _board_files(project):
            put(src, project)
        # the first route and the second measure stay out unless asked for
        for key, default in (("routes", "cables/routes.toml"), ("second", "cables/second_measure.toml")):
            p = mc.rel_to_project(job.cfg, cfg_c.get(key) or default)
            rel = os.path.relpath(p, project).replace("\\", "/") if _inside(p, project) else None
            if rel:
                found.pop(rel, None)
    for pat in includes:
        hits = _expand(project, pat)
        if not hits:
            raise Refused(f"--include {pat!r} matches no file of the project", 2)
        for src in hits:
            if not _inside(src, project):
                raise Refused(f"--include {pat!r} reaches outside the project folder", 2)
            put(src, project)
    return found


# ---------------------------------------------------------------- checks before copying -------------------------------
def build_is_current(job, args) -> str:
    """Runs `build.py --check-only`; returns its last line. Raises Refused(1) on a stale or missing output, Refused(2) when it cannot run."""
    cmd = [sys.executable, "-I", os.path.join(_HERE, "build.py"), "--project", job.project, "--check-only"]
    if getattr(args, "out", None):
        cmd += ["--out", job.out]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MECH_SCRIPTS=_HERE)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    text = ((r.stdout or "") + (r.stderr or "")).strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    last = lines[-1] if lines else "(no output)"
    if r.returncode == 0:
        return last
    stale = [ln for ln in lines if ln.startswith("STALE")]
    if r.returncode == 1:
        raise Refused("build.py --check-only: the build is not current, nothing was frozen. Run build.py, then freeze again.\n  "
                      + "\n  ".join(stale[:12] or lines[-6:]), 1)
    raise Refused("build.py --check-only could not run, so freshness is not proven and nothing was frozen:\n  " + "\n  ".join(lines[-4:]), 2)


def checks_are_current(job) -> str:
    """check_all's rule on out/checks: a check file with an input whose sha256 changed (or vanished) is stale. Raises Refused(1)."""
    checks = ca.load_checks(job.out)
    bad = [f"{os.path.basename(d.get('file', d.get('script', '?')))}: " + "; ".join(d["stale"]) for d in checks if d.get("stale")]
    if bad:
        raise Refused("out/checks has stale check files, nothing was frozen. Re-run those checks (build.py), then freeze again.\n  "
                      + "\n  ".join(bad[:12]), 1)
    return f"{len(checks)} check file(s), none stale" if checks else "no check files in out/checks"


# ---------------------------------------------------------------- the copy -------------------------------------------
def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _copy_one(task):
    rel, src, dest_root = task
    before = _sha(src)
    dst = os.path.join(dest_root, *rel.split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    after = _sha(dst)
    if before != after:
        return rel, None, f"{rel}: the file changed while it was copied"
    return rel, before, None


def freeze(job, name: str, profile: str, includes: list[str], args=None) -> dict:
    frozen = os.path.join(job.project, "reviews", "frozen")
    final = os.path.join(frozen, name)
    manifest = os.path.join(frozen, name + ".MANIFEST.sha256")
    if os.path.exists(final) or os.path.exists(manifest):
        raise Refused(f"the set {name!r} already exists in {frozen} (folder or manifest): a frozen set is never overwritten; "
                      "choose another name", 2)
    build_line = build_is_current(job, args)
    checks_line = checks_are_current(job)
    files = profile_files(job, profile, includes)
    if not files:
        raise Refused(f"nothing to freeze for profile {profile!r}: none of its files exists in {job.project}", 2)
    part = os.path.join(frozen, "." + name + ".partial")
    shutil.rmtree(part, ignore_errors=True)
    os.makedirs(part)
    sums, errs = {}, []
    try:
        tasks = [(rel, src, part) for rel, src in sorted(files.items())]
        with ThreadPoolExecutor(max_workers=min(mc.workers(), 16)) as ex:
            for k, (rel, h, err) in enumerate(ex.map(_copy_one, tasks), 1):
                if err:
                    errs.append(err)
                else:
                    sums[rel] = h
                if k % 200 == 0:
                    print(f"  copied {k}/{len(tasks)}", flush=True)
        if errs:
            raise Refused("a file changed while it was copied, nothing was frozen:\n  " + "\n  ".join(errs[:8]), 1)
        text = "".join(f"{sums[rel]}  {rel}\n" for rel in sorted(sums))
        mc.atomic_write(manifest, text)
        os.rename(part, final)
    except BaseException:
        shutil.rmtree(part, ignore_errors=True)
        if os.path.isfile(manifest) and not os.path.isdir(final):
            os.remove(manifest)
        raise
    return {"name": name, "profile": profile, "folder": final, "manifest": manifest, "manifest_sha256": _sha(manifest),
            "files": sums, "bytes": sum(os.path.getsize(os.path.join(final, *r.split("/"))) for r in sums),
            "build": build_line, "checks": checks_line}


def state_lines(job, res: dict) -> list[str]:
    rel = lambda p: os.path.relpath(p, job.project).replace("\\", "/")
    out = [f"  {rel(res['manifest'])}: {res['manifest_sha256']}"]
    if len(res["files"]) <= SMALL_SET:
        out += [f"  {rel(res['folder'])}/{r}: {h}" for r, h in sorted(res["files"].items())]
    else:
        out.append(f"  # {len(res['files'])} files, every sha256 is in the manifest")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Freeze a review or order set: refuse stale files, copy, write the manifest.",
                                 epilog="Exit codes: 0 frozen, 1 refused (stale or changed while copying), 2 could not run (set exists, bad input).")
    mc.add_std_args(ap)
    ap.add_argument("--name", required=True, help="name of the set, e.g. print-r1")
    ap.add_argument("--profile", required=True, choices=PROFILES, help="review | visual | order")
    ap.add_argument("--include", nargs="+", action="extend", default=[], metavar="GLOB", help="more files, relative to the mech folder")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", a.name or ""):
        print("could not run: --name may hold letters, digits, . _ - only (it becomes a folder name)")
        return 2
    try:
        job = mc.resolve(a)
        res = freeze(job, a.name, a.profile, a.include, a)
    except Refused as e:
        print(("REFUSED: " if e.code == 1 else "could not run: ") + str(e))
        return e.code
    except mc.MechError as e:
        print("could not run:", e)
        return 2
    print(f"frozen set '{res['name']}' (profile {res['profile']}): {len(res['files'])} files, {res['bytes'] / 1e6:.2f} MB")
    print(f"  folder   {os.path.relpath(res['folder'], job.project).replace(os.sep, '/')}")
    print(f"  manifest {os.path.relpath(res['manifest'], job.project).replace(os.sep, '/')}")
    print(f"  proven before copying: build.py --check-only: {res['build']}; out/checks: {res['checks']}")
    print("Paste into the `frozen:` block of PROJECT_STATE.md:")
    print("\n".join(state_lines(job, res)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
