"""Optional photo-style render of the model with Blender (headless), driven from a finish table and a shot list.

What it does
    1. Calls `build()` of the project model and exports every solid to an STL file (`<out>/cache/render_stl/<part>.stl`) with a
       `manifest.json` (part, file, colour, roughness, metallic, bounding box).
    2. Writes a Blender Python job (`<out>/renders/job.py`): a studio scene (a light floor, three sun lamps as key, fill and rim, a soft
       grey world, no downloaded sky image), Cycles with the GPU when Blender finds one (else the CPU on all cores), Standard colour
       management (so a colour set as #rrggbb stays that colour), one camera per shot.
    3. Runs `blender -b --factory-startup -P job.py` and checks that every picture exists and is not blank.
    Output: `<out>/renders/<shot>.png` and `<shot>.camera.json` (the same camera format as views.py, so annotate.py can place call-outs
    from model millimetres on a render), plus `<out>/renders/job.py` and the Blender log. The folder is emptied first.
    Without Blender the script exits 2 and prints: "use views.py; renders are not photo-real". The job file is still written, so it can be
    taken to another machine. Blender is looked up in: `[tools] blender`, the BLENDER environment variable, `where blender` / PATH, then the
    usual install folders (Program Files, the user's AppData programs, a `tools/blender*` folder next to the project).

Why it exists (the real failure, told without names)
    Renders were made by hand in a scene that no one could reproduce; the colours were guessed, so the powder colour on the picture
    was not the colour of the supplier's chart, and a reviewer approved a shade that the factory then could not make. A finish table that
    resolves a chart name to its published RGB value, and a shot list in a file, make the pictures repeatable and honest.

Usage
    python -I scripts/render_blender.py [--project DIR] [--out DIR] [--model FILE] [--shots front-left,top] [--samples N]
                                        [--job-only] [--serial]
    --shots names shots of the project (`[[render.shot]]` names, or front-left, rear-right, top when none are given); a PRESET
    name works as a shot name too (presets: front-left, front-right, rear-left, rear-right, front, back, top, left, right).
    A name that is neither is an error (exit 2) that lists the known ones; so is an unknown preset in a `[[render.shot]]`.
    Nothing is deleted or rendered before the shot list is checked. Zero pictures made is never a pass.
    Model extras (module level of build_model.py, optional): COLOURS = {part: "#rrggbb" or chart name}.

Config keys (mech.toml)
    [render]  samples = 64, resolution = [1600, 1200], background = "#dfe3e8", floor = true, device = "auto" | "cpu" | "gpu",
              fov_deg = 30, margin = 0.12 (free border round the model), transparent = false, threads = 0 (0 = all cores),
              stl_tolerance = 0.05
    [render.finish.<part>]  colour = "#rrggbb" or a chart name (resolved through suppliers/*.capability.toml [coat_rgb] / [ink_rgb]),
                            roughness = 0.5, metallic = 0.0
    [render.finish.default]  the same keys, for every part without its own entry
    [[render.shot]]  name = "iso", preset = "front-left" | "front-right" | "rear-left" | "rear-right" | "front" | "back" | "top" | "left" | "right",
                     or azimuth = 35, elevation = 25 (degrees; azimuth 0 looks from the front (-y), turning towards the left (-x));
                     distance = mm (default: fitted so the whole model fills the picture), target = [x, y, z] (default the model centre)
                     (default shots when none are given: front-left, rear-right, top)
    [tools]   blender = "path to blender", or "none" = the user declined Blender (never looked for; exit 2 with the job file written)

Exit codes: 0 all pictures made and rows pass; 1 a row failed (a picture missing, blank, or none made at all); 2 Blender declined or
missing, CadQuery missing, an input missing, or an unknown shot name or preset (nothing is reported as passed).
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import glob
import json
import math
import shutil
import subprocess
import time

import mech_common as mc

PRESETS = {"front-left": (35, 25), "front-right": (-35, 25), "rear-left": (145, 25), "rear-right": (215, 25), "front": (0, 8), "back": (180, 8),
           "left": (90, 8), "right": (-90, 8), "top": (0, 90)}
MISSING_TEXT = "use views.py; renders are not photo-real"


# ---------------------------------------------------------------- finding Blender -------------------------------------
def find_blender(cfg: dict | None) -> str | None:
    import env_check
    if env_check.is_declined(cfg, "blender"):
        return None                       # the user said no Blender: never auto-detected
    cands = []
    if cfg:
        cands.append(cfg.get("tools", {}).get("blender", ""))
    cands.append(os.environ.get("BLENDER", ""))
    exe = shutil.which("blender")
    if exe:
        cands.append(exe)
    pats = []
    for pf in (os.environ.get("ProgramFiles", "C:/Program Files"), os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")):
        pats.append(os.path.join(pf, "Blender Foundation", "Blender*", "blender.exe"))
    home = os.path.expanduser("~")
    pats += [os.path.join(os.environ.get("LOCALAPPDATA", home), "Programs", "Blender Foundation", "Blender*", "blender.exe"),
             os.path.join(home, "tools", "blender*", "blender.exe"), os.path.join(home, "tools", "blender*", "blender*", "blender.exe"),
             "/Applications/Blender.app/Contents/MacOS/Blender", "/usr/bin/blender", "/snap/bin/blender", "/usr/local/bin/blender"]
    if cfg:
        pr = cfg.get("_project", "")
        for base in (pr, os.path.dirname(pr)):
            pats += [os.path.join(base, "tools", "blender*", "blender.exe"), os.path.join(base, "tools", "blender*", "blender*", "blender.exe")]
    for p in pats:
        cands += sorted(glob.glob(p), reverse=True)
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


# ---------------------------------------------------------------- shots / cameras ------------------------------------
def eye_for(target, az_deg, el_deg, dist):
    az, el = math.radians(az_deg), math.radians(el_deg)
    d = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), -math.sin(el))        # from the eye into the model (as views.py)
    return tuple(target[i] - d[i] * dist for i in range(3)), d


def make_shot_camera(shot: dict, bbox, size, fov, margin):
    """Camera dict (views.py format) for a shot; distance fitted to the bounding box unless given."""
    import views
    lo, hi = bbox
    target = shot.get("target") or [(lo[i] + hi[i]) / 2 for i in range(3)]
    if "preset" in shot:
        if shot["preset"] not in PRESETS:
            raise mc.MechError(f"shot {shot.get('name')}: preset must be one of {sorted(PRESETS)}")
        az, el = PRESETS[shot["preset"]]
    else:
        az, el = float(shot.get("azimuth", 35)), float(shot.get("elevation", 25))
    up = (0, 0, 1) if el < 89.5 else (0, 1, 0)
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    w, h = size
    dist = float(shot["distance"]) if shot.get("distance") else None
    if dist is None:
        rad = max(math.dist(c, target) for c in corners)
        dist = rad / math.sin(math.radians(fov) / 2)
        for _ in range(60):
            eye, d = eye_for(target, az, el, dist)
            cam = {"kind": "persp", "size": [w, h], "eye": list(eye), "dir": list(d), "up": list(views.ortho_up(d, up)), "fov_deg": fov}
            pts = [views.project(cam, c) for c in corners]
            fx = max(max(abs(p[0] - w / 2) for p in pts) / (w / 2), max(abs(p[1] - h / 2) for p in pts) / (h / 2))
            if 1.0 - margin - 0.03 <= fx <= 1.0 - margin:
                break
            dist *= fx / (1.0 - margin - 0.015)
    eye, d = eye_for(target, az, el, dist)
    return {"kind": "persp", "size": [w, h], "eye": list(eye), "dir": list(d), "up": list(views.ortho_up(d, up)), "fov_deg": fov}


def plan_shots(rc: dict, only=None) -> list[dict]:
    """The shot entries to render: the `[[render.shot]]` list (default: front-left, rear-right, top), restricted to `only` (names
    given with --shots) when that is not None. A name of `only` is a configured shot, or a preset name (a shot with that preset).
    Raises MechError, naming what is known, for a shot without a name, a repeated name, an unknown preset, or an unknown name."""
    cfgs = rc.get("shot") or [{"name": k, "preset": k} for k in ("front-left", "rear-right", "top")]
    names = []
    for s in cfgs:
        if not s.get("name"):
            raise mc.MechError("a [[render.shot]] entry needs a name")
        if s["name"] in names:
            raise mc.MechError(f"[[render.shot]] name {s['name']!r} is used twice")
        names.append(s["name"])
        if "preset" in s and s["preset"] not in PRESETS:
            raise mc.MechError(f"shot {s['name']}: unknown preset {s['preset']!r}; presets: {', '.join(PRESETS)}")
    if only is None:
        return list(cfgs)
    asked = [x for x in only if x]
    if not asked:
        raise mc.MechError("--shots names no shot; shots of this project: " + ", ".join(names) + "; presets: " + ", ".join(PRESETS))
    out, seen = [], set()
    for x in asked:
        if x in seen:
            continue
        seen.add(x)
        if x in names:
            out.append(cfgs[names.index(x)])
        elif x in PRESETS:
            out.append({"name": x, "preset": x})
        else:
            raise mc.MechError(f"unknown shot {x!r} in --shots. Shots of this project: {', '.join(names)}. Presets (also usable as shot names): "
                               f"{', '.join(PRESETS)}")
    return out


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# ---------------------------------------------------------------- the Blender job -------------------------------------
JOB_TEMPLATE = r'''# Generated by render_blender.py: run with   blender -b --factory-startup -P job.py
import json, math, os, sys
import bpy
from mathutils import Vector

CFG = json.loads(r"""__CFG__""")
OUT = CFG["out_dir"]
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.001            # 1 Blender unit = 1 mm, as in the model

def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def material(name, rgb, rough, metal):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (lin(rgb[0]), lin(rgb[1]), lin(rgb[2]), 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m

def import_stl(path):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=path)
    else:
        bpy.ops.import_mesh.stl(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    return new[0]

zmin = CFG["bbox"][0][2]
for p in CFG["parts"]:
    ob = import_stl(p["stl"])
    ob.name = p["name"]
    ob.data.materials.append(material(p["name"], p["rgb"], p["roughness"], p["metallic"]))
    for poly in ob.data.polygons:
        poly.use_smooth = False
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    mod = ob.modifiers.new("angle", 'EDGE_SPLIT')       # hard edges stay hard, curved faces look round
    mod.split_angle = math.radians(35)
    ob.select_set(False)

lo, hi = CFG["bbox"]
centre = Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
size = max(hi[i] - lo[i] for i in range(3))
if CFG["floor"]:
    bpy.ops.mesh.primitive_plane_add(size=size * 40, location=(centre.x, centre.y, zmin - 0.05))
    fl = bpy.context.active_object
    fl.name = "floor"
    fl.data.materials.append(material("floor", CFG["background_rgb"], 0.9, 0.0))

# world: a soft uniform grey, no image
world = bpy.data.worlds.new("studio")
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (lin(CFG["background_rgb"][0]), lin(CFG["background_rgb"][1]), lin(CFG["background_rgb"][2]), 1.0)
bg.inputs["Strength"].default_value = 0.5
scene.world = world

def sun(name, az, el, strength, angle):
    data = bpy.data.lights.new(name, 'SUN')
    data.energy = strength
    data.angle = math.radians(angle)
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    a, e = math.radians(az), math.radians(el)
    direction = Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), -math.sin(e)))     # light travels from front-left-above into the model
    ob.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return ob

sun("key", 40, 50, 1.9, 6)
sun("fill", -60, 30, 0.55, 12)
sun("rim", 200, 35, 0.8, 8)

r = scene.render
r.engine = 'CYCLES'
r.resolution_x, r.resolution_y = CFG["resolution"]
r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'
r.film_transparent = CFG["transparent"]
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.cycles.samples = CFG["samples"]
scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
r.threads_mode = 'FIXED' if CFG["threads"] else 'AUTO'
if CFG["threads"]:
    r.threads = CFG["threads"]

used = "CPU"
want = CFG["device"]
if want in ("auto", "gpu"):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type != 'CPU']
                if devs:
                    for d in prefs.devices:
                        d.use = d.type != 'CPU'
                    scene.cycles.device = 'GPU'
                    used = "GPU " + kind
                    break
            except Exception:
                continue
    except Exception as e:
        print("GPU setup failed, CPU:", e)
if used == "CPU":
    scene.cycles.device = 'CPU'
print("RENDER DEVICE:", used, "threads", CFG["threads"] or "all")

cam_data = bpy.data.cameras.new("cam")
cam_data.sensor_fit = 'VERTICAL'
cam_data.sensor_height = 24.0
cam_data.clip_start = 1.0
cam_data.clip_end = 1.0e6
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam

for shot in CFG["shots"]:
    c = shot["camera"]
    eye = Vector(c["eye"])
    d = Vector(c["dir"])
    cam_data.lens = 12.0 / math.tan(math.radians(c["fov_deg"]) / 2.0)
    cam.location = eye
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler() if abs(d.z) < 0.999 else (Vector((0, 0, -1)).to_track_quat('-Z', 'Y').to_euler())
    if abs(d.z) >= 0.999:                              # straight down: put the back of the model at the top of the picture
        cam.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(OUT, shot["name"] + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)
'''


def write_job(path: str, data: dict) -> None:
    text = JOB_TEMPLATE.replace("__CFG__", json.dumps(data))
    mc.atomic_write(path, text)


# ---------------------------------------------------------------- main -----------------------------------------------
def run(args) -> int:
    job = mc.resolve(args)
    cfg = job.cfg
    rc = dict(cfg.get("render", {}))
    shots_cfg = plan_shots(rc, [s.strip() for s in args.shots.split(",")] if args.shots else None)      # before anything is deleted or rendered
    model_path = args.model or mc.path_of(cfg, "model")
    if not os.path.isfile(model_path):
        print(f"could not run: model file not found: {model_path}", file=sys.stderr)
        return 2
    import views
    solids, meta = views.load_model_full(model_path)
    if not solids:
        print("could not run: build() returned no solids", file=sys.stderr)
        return 2
    rows = mc.Rows()
    rdir = os.path.join(job.out, "renders")
    if os.path.isdir(rdir):
        shutil.rmtree(rdir, ignore_errors=True)
    os.makedirs(rdir, exist_ok=True)
    stl_dir = os.path.join(job.out, "cache", "render_stl")
    if os.path.isdir(stl_dir):
        shutil.rmtree(stl_dir, ignore_errors=True)
    os.makedirs(stl_dir, exist_ok=True)
    import cadquery as cq
    fin = rc.get("finish", {})
    dflt = fin.get("default", {})
    tol = float(rc.get("stl_tolerance", 0.05))
    manifest = {"parts": []}
    colours = {**meta.get("COLOURS", {})}
    bbs = []
    for i, (n, shape) in enumerate(solids.items()):
        f = {"roughness": 0.5, "metallic": 0.0, **dflt, **fin.get(n, {})}
        if "colour" in f:
            rgb = views.resolve_colour(f["colour"], cfg)
        elif n in colours:
            rgb = views.resolve_colour(colours[n], cfg)
        else:
            rgb = views.default_colour(n, i)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in n)
        p = os.path.join(stl_dir, f"{i:03d}_{safe}.stl")
        cq.exporters.export(cq.Workplane(obj=shape) if not isinstance(shape, cq.Workplane) else shape, p, tolerance=tol, angularTolerance=0.2)
        bb = shape.BoundingBox()
        bbs.append(((bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax)))
        manifest["parts"].append({"name": n, "stl": p.replace("\\", "/"), "rgb": list(rgb), "roughness": float(f["roughness"]), "metallic": float(f["metallic"])})
    lo = tuple(min(b[0][i] for b in bbs) for i in range(3))
    hi = tuple(max(b[1][i] for b in bbs) for i in range(3))
    manifest["bbox"] = [list(lo), list(hi)]
    mc.atomic_write(os.path.join(stl_dir, "manifest.json"), json.dumps(manifest, indent=1))
    # shots
    res = [int(v) for v in rc.get("resolution", [1600, 1200])]
    fov = float(rc.get("fov_deg", 30))
    margin = float(rc.get("margin", 0.12))
    shots = []
    for s in shots_cfg:
        cam = make_shot_camera(s, (lo, hi), res, fov, margin)
        shots.append({"name": s["name"], "camera": cam})
    if not shots:
        raise mc.MechError("no shot to render")
    bgc = views.resolve_colour(rc.get("background", "#dfe3e8"), cfg)
    data = {"out_dir": rdir.replace("\\", "/"), "parts": manifest["parts"], "bbox": manifest["bbox"], "shots": shots, "resolution": res,
            "samples": int(args.samples or rc.get("samples", 64)), "device": rc.get("device", "auto"), "floor": bool(rc.get("floor", True)),
            "transparent": bool(rc.get("transparent", False)), "background_rgb": list(bgc),
            "threads": int(rc.get("threads", 0) or (0 if not args.serial else 1))}
    job_py = os.path.join(rdir, "job.py")
    write_job(job_py, data)
    for sh in shots:
        mc.atomic_write(os.path.join(rdir, sh["name"] + ".camera.json"), json.dumps(sh["camera"], indent=1))
    if args.job_only:
        rows.add("RND-JOB", "render", "Blender job file written", job_py, "job.py parses as Python", "pass" if _parses(job_py) else "fail")
        rows.write(job.out, "render_blender.py", [model_path])
        print(f"job written: {job_py} (not run: --job-only)")
        print(rows.headline())
        return rows.exit_code()
    import env_check
    declined = env_check.is_declined(cfg, "blender")
    blender = None if declined else find_blender(cfg)
    if not blender:
        why = 'declined by the user ([tools] blender = "none")' if declined else "not found (set [tools] blender or BLENDER)"
        print(f"could not run: Blender {why}. {MISSING_TEXT}. Job file: {job_py}", file=sys.stderr)
        rows.add("RND-BLENDER", "render", "Blender found", "declined by the user" if declined else "not found", MISSING_TEXT, "could_not_run")
        rows.add("RND-JOB", "render", "Blender job file written", job_py, "job.py parses as Python", "pass" if _parses(job_py) else "fail")
        rows.write(job.out, "render_blender.py", [model_path])
        rows.print_table()
        print(rows.headline())
        return rows.exit_code()
    print(f"Blender: {blender}\nrendering {len(shots)} shot(s), {data['samples']} samples ...")
    t0 = time.time()
    log = os.path.join(rdir, "blender.log")
    with open(log, "w", encoding="utf-8", errors="replace") as lf:
        r = subprocess.run([blender, "-b", "--factory-startup", "-P", job_py], stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=3600)
    rows.add("RND-RUN", "render", "Blender exit code", str(r.returncode), "0", "pass" if r.returncode == 0 else "fail")
    from PIL import Image
    import numpy as np
    made = sum(1 for sh in shots if os.path.isfile(os.path.join(rdir, sh["name"] + ".png")))
    rows.add("RND-PICS", "render", "pictures made", f"{made} of {len(shots)}", "every shot has a picture (none made is never a pass)",
             "pass" if made == len(shots) and made > 0 else "fail")
    for sh in shots:
        p = os.path.join(rdir, sh["name"] + ".png")
        if not os.path.isfile(p):
            rows.add(f"RND-{sh['name']}", "render", f"{sh['name']} picture", "missing (see blender.log)", "file exists", "fail")
            continue
        a = np.asarray(Image.open(p).convert("L"))
        spread = float(a.std())
        rows.add(f"RND-{sh['name']}", "render", f"{sh['name']} picture", f"{a.shape[1]}x{a.shape[0]} px, std {spread:.1f}", "not blank (std > 3)", "pass" if spread > 3 else "fail")
    rows.write(job.out, "render_blender.py", [model_path])
    rows.print_table(only_bad=True)
    print(f"renders in {rdir} ({time.time() - t0:.0f} s)")
    print(rows.headline())
    return rows.exit_code()


def _parses(path: str) -> bool:
    import ast
    try:
        with open(path, encoding="utf-8") as f:
            ast.parse(f.read())
        return True
    except SyntaxError:
        return False


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Blender photo render of the model",
                                 epilog="Presets (usable as shot names, or as `preset =` in a [[render.shot]]): " + ", ".join(PRESETS) +
                                        ". Exit: 0 pictures made, 1 a row failed, 2 could not run (Blender declined or missing, unknown shot).")
    mc.add_std_args(ap)
    ap.add_argument("--model")
    ap.add_argument("--shots", help="comma list of shot names: names from [[render.shot]], or a preset name (" + ", ".join(PRESETS) + ")")
    ap.add_argument("--samples", type=int)
    ap.add_argument("--job-only", action="store_true", help="write the Blender job and stop")
    ap.add_argument("--serial", action="store_true", help="one render thread")
    args = ap.parse_args(argv)
    try:
        cfg_probe = mc.load_config(mc.find_project(args.project))
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2
    mc.reexec_with_cadquery(cfg_probe)
    try:
        return run(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
