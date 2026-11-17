"""The standard view set of the model: six orthographic views, one perspective, one exploded, named section cuts, one contact sheet.

What it does
    Calls `build()` of the project model (model/build_model.py) and renders every solid with VTK offscreen (shaded flat
    colours with the B-rep edges drawn dark; no Blender, no GPU needed). Views written to `<out>/views/`:
      front, back, top, bottom, left, right   orthographic, with the OVERALL dimensions written on the picture
      perspective                             one 3/4 view (front-left-top)
      exploded                                perspective view with the parts pulled apart (explode vectors from the model's
                                              EXPLODE dict or `[views.explode]`; otherwise automatic: parts ranked by height
                                              in the model's ASSEMBLY_ORDER, or by the z of their bottom face, and lifted along z)
      section_<name>                          one cut per `[[views.section]]` entry, looking at the cut face
      contact_sheet.png                       every picture, small, with its name
    Next to each picture `<name>.camera.json` holds the camera (orthographic: centre, ppm; perspective: eye, fov), so that
    `annotate.py` can project model millimetres onto the picture. `views_manifest.json` lists files, size and the model's
    metadata (ASSEMBLY_ORDER, part names, model file time) for `manual_build.py`.
    Frame: x right, y back, z up; "front" is what a viewer at -y sees (x to the right), "left" is seen from -x (the front of
    the box is on the right of the picture), "top" has the back at the top, "bottom" has the front at the top.
    Method: VTK shaded render + B-rep edges, NOT a hidden-line projection (chosen because it renders large models in
    seconds on any PC and was proven offscreen here). Tessellation is done once per part on all cores (cached as .vtp under
    `<out>/cache/views/`), then every view is rendered in its own worker process; a serial run gives the same pictures.
    A FULL run empties the whole `<out>/views/` folder first: one folder, nothing stale. A run with `--only` (or `--no-clear`)
    does NOT delete anything: it redraws the named pictures and leaves the others as they were (they may be older than the
    model: a note says so); the contact sheet and views_manifest.json then list every picture in the folder.

Why it exists (the real failure, told without names)
    Pictures made by hand from an old model were pasted into a review and the reviewer approved a box that no longer
    existed. One command that rebuilds the full set from the code, with the camera written beside each picture, makes a
    stale picture impossible and lets later steps place call-outs from model millimetres instead of by eye.

Usage
    python -I scripts/views.py [--project DIR] [--out DIR] [--model FILE] [--only front,top,section_x] [--ppm N]
                               [--no-clear] [--serial]
    --only redraws just those views and keeps every other picture (the folder is emptied only on a full run); a name that is
    not a view of this model (front, back, top, bottom, left, right, perspective, exploded, section_<name>) is an error, exit 2.
    Model extras (all optional, module level of build_model.py): ASSEMBLY_ORDER = [names], COLOURS = {name: "#rrggbb" or chart
    name}, EXPLODE = {name: [dx, dy, dz]}.

Config keys (mech.toml)
    [views] long_px = 1500          long side of the model in pixels in each picture (default 1500)
            margin_px = 120         room for the dimension lines (default 120)
            tolerance = 0.0008, angle = 0.15      tessellation (relative deflection, radians)
            fov_deg = 28            perspective field of view
            azimuth_deg = 35, elevation_deg = 28    perspective direction (azimuth from the front towards the left)
            explode_gap = 0         automatic explode step in mm (0 = a quarter of the model height, at least 10)
            dims = true             write overall dimensions on the orthographic views
            titles = true           write the view name in the corner of each picture
            hide = ["name", ...]    solids left out of every view
            skip = ["bottom", ...]  views not made
    [views.colours]  part = "#rrggbb" | chart name from suppliers/*.capability.toml ([coat_rgb] / [ink_rgb])
    [views.explode]  part = [dx, dy, dz]
    [[views.section]]  name = "mid", axis = "y", at = 40.0, keep = "positive"   (axis x|y|z; keep the side with coordinates
                       above or below `at`; the viewer looks at the cut face from the removed side)

Exit codes: 0 all pictures made and every row passes; 1 a row failed; 2 CadQuery, VTK, PIL or the model is missing, or an --only
name is not a view of this model.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import glob
import hashlib
import importlib.util
import json
import math
import shutil
import time
from concurrent.futures import ProcessPoolExecutor

import mech_common as mc

AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}

# name: (view direction = from the viewer into the model, up)
ORTHO = {
    "front":  ((0, 1, 0), (0, 0, 1)),
    "back":   ((0, -1, 0), (0, 0, 1)),
    "top":    ((0, 0, -1), (0, 1, 0)),
    "bottom": ((0, 0, 1), (0, -1, 0)),
    "left":   ((1, 0, 0), (0, 0, 1)),
    "right":  ((-1, 0, 0), (0, 0, 1)),
}
DEFAULT_PALETTE = ["#9db4c8", "#c8a98b", "#a7c4a0", "#c9b6d9", "#d8cf8a", "#8fc5c9", "#d49a9a", "#b0b0b0"]


# ---------------------------------------------------------------- vectors (no numpy needed here) ----------------------
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def ortho_up(dirv, up):
    """The up vector made perpendicular to the view direction (a 3/4 view's up is only roughly vertical)."""
    d = _norm(dirv)
    k = _dot(up, d)
    return _norm((up[0] - k * d[0], up[1] - k * d[1], up[2] - k * d[2]))


def right_of(dirv, up):
    """right = dir x up (x right, y back, z up: front view dir (0,1,0), up (0,0,1) gives right (1,0,0))."""
    return _norm(_cross(dirv, up))


def project(cam: dict, p) -> tuple[float, float, float]:
    """Pixel (x to the right, y down) and depth of model point p (mm) in the picture described by a camera.json dict."""
    d = _norm(cam["dir"])
    u = ortho_up(d, cam["up"])
    r = right_of(d, u)
    w, h = cam["size"]
    if cam["kind"] == "ortho":
        q = _sub(p, cam["centre"])
        return (w / 2 + _dot(q, r) * cam["ppm"], h / 2 - _dot(q, u) * cam["ppm"], _dot(q, d))
    q = _sub(p, cam["eye"])
    zc = _dot(q, d)
    f = (h / 2) / math.tan(math.radians(cam["fov_deg"]) / 2)
    zc_s = zc if abs(zc) > 1e-9 else 1e-9
    return (w / 2 + f * _dot(q, r) / zc_s, h / 2 - f * _dot(q, u) / zc_s, zc)


def load_camera(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- colours --------------------------------------------
def _hex_rgb(s: str):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def chart_colours(cfg: dict) -> dict:
    """All chart colour names of every suppliers/*.capability.toml ([coat_rgb] and [ink_rgb]) -> '#rrggbb' (case-insensitive keys)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(cfg["_project"], "suppliers", "*.capability.toml"))):
        try:
            t = mc.load_toml(p)
        except mc.MechError:
            continue
        for sec in ("coat_rgb", "ink_rgb"):
            for k, v in (t.get(sec) or {}).items():
                out.setdefault(str(k).lower(), v)
    return out


def resolve_colour(value: str, cfg: dict):
    """'#rrggbb' or a chart colour name -> (r, g, b) floats 0..1. Raises MechError for an unknown name."""
    v = str(value).strip()
    if v.startswith("#") or (len(v) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in v)):
        return _hex_rgb(v)
    ch = chart_colours(cfg)
    if v.lower() in ch:
        return _hex_rgb(ch[v.lower()])
    raise mc.MechError(f"colour '{value}' is neither #rrggbb nor a name in a suppliers/*.capability.toml [coat_rgb]/[ink_rgb]")


def default_colour(name: str, index: int):
    n = name.lower()
    if any(k in n for k in ("pcb", "board")):
        return _hex_rgb("#2e7d4f")
    if any(k in n for k in ("screw", "nut", "stand", "washer", "bolt")):
        return _hex_rgb("#8a8f98")
    return _hex_rgb(DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)])


# ---------------------------------------------------------------- model ----------------------------------------------
def load_model_full(path: str):
    """Import the model, call build(). Returns (solids name -> cq.Shape, meta dict with ASSEMBLY_ORDER, COLOURS, EXPLODE, PLACEMENTS)."""
    import cadquery as cq
    path = os.path.abspath(path)
    mdir = os.path.dirname(path)
    if mdir not in sys.path:
        sys.path.insert(0, mdir)
    spec = importlib.util.spec_from_file_location("project_build_model_v", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.build()
    if isinstance(res, tuple):
        res = res[0]
    solids = {}
    for k, v in dict(res).items():
        if k.startswith("_") or isinstance(v, (dict, list, tuple, str, int, float)):
            continue
        if isinstance(v, cq.Workplane):
            vals = [o for o in v.vals() if isinstance(o, cq.Shape)]
            if not vals:
                continue
            v = vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
        solids[str(k)] = v
    meta = {"ASSEMBLY_ORDER": list(getattr(mod, "ASSEMBLY_ORDER", []) or []),
            "COLOURS": dict(getattr(mod, "COLOURS", {}) or {}),
            "EXPLODE": dict(getattr(mod, "EXPLODE", {}) or {}),
            "PLACEMENTS": dict(getattr(mod, "PLACEMENTS", {}) or {})}
    return solids, meta


def model_mtime(model_path: str) -> float:
    """Newest change among the model file and the .py files next to it (the model's own helpers)."""
    d = os.path.dirname(os.path.abspath(model_path))
    t = [os.path.getmtime(model_path)]
    t += [os.path.getmtime(p) for p in glob.glob(os.path.join(d, "*.py"))]
    return max(t)


# ---------------------------------------------------------------- stage 1: tessellation (worker) ---------------------
def _poly_to_faces_edges(shape, tol, ang):
    import vtk
    data = shape.toVtkPolyData(tol, ang)
    ex = vtk.vtkExtractCellsByType()
    ex.SetInputData(data)
    ex.AddCellType(vtk.VTK_TRIANGLE)
    ex.Update()
    faces = vtk.vtkPolyData()
    faces.DeepCopy(ex.GetOutput())
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(faces)
    nrm.SetFeatureAngle(40)
    nrm.SplittingOn()
    nrm.Update()
    faces = nrm.GetOutput()
    ex2 = vtk.vtkExtractCellsByType()
    ex2.SetInputData(data)
    ex2.AddCellType(vtk.VTK_LINE)
    ex2.AddCellType(vtk.VTK_POLY_LINE)
    ex2.Update()
    edges = vtk.vtkPolyData()
    edges.DeepCopy(ex2.GetOutput())
    mt = edges.GetCellData().GetArray("MESH_TYPES")
    if mt is not None and edges.GetNumberOfCells():          # drop the seam lines of cylinders
        keep = vtk.vtkIdList()
        for i in range(edges.GetNumberOfCells()):
            if int(mt.GetTuple1(i)) != 8:
                keep.InsertNextId(i)
        ext = vtk.vtkExtractCells()
        ext.SetInputData(edges)
        ext.SetCellList(keep)
        ext.Update()
        geo = vtk.vtkGeometryFilter()
        geo.SetInputConnection(ext.GetOutputPort())
        geo.Update()
        edges = geo.GetOutput()
    return faces, edges


def _write_vtp(poly, path):
    import vtk
    w = vtk.vtkXMLPolyDataWriter()
    w.SetFileName(path)
    w.SetInputData(poly)
    w.SetDataModeToBinary()
    w.Write()


def _read_vtp(path):
    import vtk
    r = vtk.vtkXMLPolyDataReader()
    r.SetFileName(path)
    r.Update()
    return r.GetOutput()


def tess_task(job):
    """Worker: BREP file -> faces.vtp + edges.vtp. job = (brep, faces_path, edges_path, tol, ang)."""
    import cadquery as cq
    brep, fp, ep, tol, ang = job
    shape = cq.Shape.importBrep(brep)
    faces, edges = _poly_to_faces_edges(shape, tol, ang)
    _write_vtp(faces, fp)
    _write_vtp(edges, ep)
    return fp


# ---------------------------------------------------------------- stage 2: one picture (worker) ------------------------
def _font(size, bold=False):
    from PIL import ImageFont
    names = (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]) + ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for n in names:
        for d in ("C:/Windows/Fonts", ""):
            try:
                return ImageFont.truetype(os.path.join(d, n) if d else n, size)
            except OSError:
                continue
    try:
        import matplotlib
        p = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
        return ImageFont.truetype(p, size)
    except Exception:
        return ImageFont.load_default()


def _draw_dim(draw, p0, p1, offset, text, vertical, font):
    """A dimension line between pixel points p0, p1 (same x if vertical, else same y), drawn `offset` px away
    (to the right/below when positive) with extension lines, arrows and the text on a white patch."""
    ink = (45, 52, 66)
    if not vertical:
        y = max(p0[1], p1[1]) + offset
        draw.line([(p0[0], p0[1] + 4), (p0[0], y + 6)], fill=ink, width=1)
        draw.line([(p1[0], p1[1] + 4), (p1[0], y + 6)], fill=ink, width=1)
        a, b = (p0[0], y), (p1[0], y)
    else:
        x = min(p0[0], p1[0]) - offset
        draw.line([(p0[0] - 4, p0[1]), (x - 6, p0[1])], fill=ink, width=1)
        draw.line([(p1[0] - 4, p1[1]), (x - 6, p1[1])], fill=ink, width=1)
        a, b = (x, p0[1]), (x, p1[1])
    draw.line([a, b], fill=ink, width=2)
    for q, s in ((a, 1), (b, -1)):
        dx, dy = (b[0] - a[0], b[1] - a[1])
        L = math.hypot(dx, dy) or 1
        ux, uy = s * dx / L, s * dy / L
        nx, ny = -uy, ux
        tip = q
        draw.polygon([tip, (tip[0] + ux * 14 + nx * 5, tip[1] + uy * 14 + ny * 5), (tip[0] + ux * 14 - nx * 5, tip[1] + uy * 14 - ny * 5)], fill=ink)
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    bb = draw.textbbox((cx, cy), text, font=font, anchor="mm")
    draw.rectangle((bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2), fill=(255, 255, 255))
    draw.text((cx, cy), text, fill=ink, font=font, anchor="mm")


def _make_camera(kind, spec, bbox, long_px, margin, fov):
    """Camera dict for a bbox ((x0,y0,z0),(x1,y1,z1)) in model mm (after explode/cut)."""
    d = _norm(spec["dir"])
    u = ortho_up(d, spec["up"])
    r = right_of(d, u)
    lo, hi = bbox
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    centre = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    if kind == "ortho":
        us = [_dot(_sub(c, centre), r) for c in corners]
        vs = [_dot(_sub(c, centre), u) for c in corners]
        wmm, hmm = max(us) - min(us), max(vs) - min(vs)
        ppm = long_px / max(wmm, hmm, 1e-6)
        # the picture centre is the middle of the projected extent
        cu, cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
        centre = tuple(centre[i] + r[i] * cu + u[i] * cv for i in range(3))
        w, h = int(round(wmm * ppm + 2 * margin)), int(round(hmm * ppm + 2 * margin))
        return {"kind": "ortho", "size": [w, h], "centre": list(centre), "dir": list(d), "up": list(u), "ppm": ppm,
                "extent_mm": [wmm, hmm]}
    # perspective: from a direction, far enough that all corners fit; the picture is 4:3
    w, h = int(long_px), int(long_px * 0.75)
    rad = max(math.dist(c, centre) for c in corners)
    dist = rad / math.sin(math.radians(fov) / 2) * 1.0
    for _ in range(40):
        cam = {"kind": "persp", "size": [w, h], "eye": [centre[i] - d[i] * dist for i in range(3)], "dir": list(d), "up": list(u), "fov_deg": fov}
        pts = [project(cam, c) for c in corners]
        fx = max(max(abs(p[0] - w / 2) for p in pts) / (w / 2 - margin * 0.6), max(abs(p[1] - h / 2) for p in pts) / (h / 2 - margin * 0.6))
        if fx <= 1.0 and fx > 0.9:
            break
        dist *= fx / 0.95 if fx > 0 else 1.0
    return cam


def render_task(job):
    """Worker: one picture. job is a dict (see build_jobs). Returns {name, png, camera, problems}."""
    import numpy as np
    import vtk
    from PIL import Image, ImageDraw
    from vtk.util.numpy_support import vtk_to_numpy
    cam = job["camera"]
    w, h = cam["size"]
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    cut = job.get("cut")
    items = job["items"]
    if cut:
        import cadquery as cq
    for it in items:
        offs = it.get("offset", (0, 0, 0))
        layers = []
        if cut:
            shape = cq.Shape.importBrep(it["brep"])
            part, cap = _cut_shape(shape, cut)
            if part is None:
                continue
            f, e = _poly_to_faces_edges(part, job["tol"], job["ang"])
            layers.append((f, it["rgb"], False))
            layers.append((e, (0.1, 0.11, 0.13), True))
            if cap is not None:
                cf, ce = _poly_to_faces_edges(cap, job["tol"], job["ang"])
                layers.append((cf, (0.78, 0.15, 0.15), False))
        else:
            layers.append((_read_vtp(it["faces"]), it["rgb"], False))
            layers.append((_read_vtp(it["edges"]), (0.1, 0.11, 0.13), True))
        for poly, col, is_edge in layers:
            if poly.GetNumberOfCells() == 0:
                continue
            m = vtk.vtkPolyDataMapper()
            m.SetInputData(poly)
            m.ScalarVisibilityOff()
            m.SetResolveCoincidentTopologyToPolygonOffset()
            if is_edge:
                m.SetRelativeCoincidentTopologyLineOffsetParameters(-1.0, -1.0)
            else:
                m.SetRelativeCoincidentTopologyPolygonOffsetParameters(1.5, 1.5)
            a = vtk.vtkActor()
            a.SetMapper(m)
            a.SetPosition(*offs)
            p = a.GetProperty()
            p.SetColor(*col)
            if is_edge:
                p.SetLineWidth(max(1.0, min(2.2, (cam.get("ppm") or 3.0) / 5.0)))
                p.LightingOff()
            else:
                p.SetAmbient(0.38)
                p.SetDiffuse(0.62)
                p.SetSpecular(0.06)
            ren.AddActor(a)
    lk = vtk.vtkLightKit()
    lk.SetKeyLightIntensity(0.85)
    lk.AddLightsToRenderer(ren)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetMultiSamples(0)
    win.AddRenderer(ren)
    win.SetSize(w, h)
    ren.UseFXAAOn()
    vc = ren.GetActiveCamera()
    d, u = cam["dir"], cam["up"]
    if cam["kind"] == "ortho":
        vc.ParallelProjectionOn()
        c = cam["centre"]
        vc.SetFocalPoint(*c)
        vc.SetPosition(*(c[i] - d[i] * 5000.0 for i in range(3)))
        vc.SetViewUp(*u)
        vc.SetParallelScale(h / cam["ppm"] / 2.0)
        vc.SetClippingRange(100.0, 10000.0)
    else:
        e = cam["eye"]
        vc.ParallelProjectionOff()
        vc.SetPosition(*e)
        vc.SetFocalPoint(*(e[i] + d[i] * 1000.0 for i in range(3)))
        vc.SetViewUp(*u)
        vc.SetViewAngle(cam["fov_deg"])
        ren.ResetCameraClippingRange()
    win.Render()
    f = vtk.vtkWindowToImageFilter()
    f.SetInput(win)
    f.SetInputBufferTypeToRGB()
    f.ReadFrontBufferOff()
    f.Update()
    img = f.GetOutput()
    dims = img.GetDimensions()
    arr = vtk_to_numpy(img.GetPointData().GetScalars()).reshape(dims[1], dims[0], -1)[::-1]
    win.Finalize()
    im = Image.fromarray(np.ascontiguousarray(arr[:, :, :3]))
    dr = ImageDraw.Draw(im)
    fnt = _font(max(20, int(w / 50)), True)
    lab = _font(max(16, int(w / 70)))
    # the dimensions of the whole model on an orthographic view
    if cam["kind"] == "ortho" and job.get("dims", True):
        lo, hi = job["bbox"]
        r = right_of(d, u)
        corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        pts = [project(cam, c) for c in corners]
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        em = cam["extent_mm"]
        _draw_dim(dr, (x0, y1), (x1, y1), 34, f"{em[0]:.1f} mm", False, fnt)
        _draw_dim(dr, (x0, y0), (x0, y1), 34, f"{em[1]:.1f} mm", True, fnt)
    if job.get("titles", True):
        dr.text((14, 10), job["title"], fill=(45, 52, 66), font=fnt)
    if cam["kind"] == "ortho" and job.get("titles", True):
        dr.text((14, h - 10), job.get("note", ""), fill=(110, 118, 132), font=lab, anchor="ls")
    im.save(job["png"])
    with open(job["png"][:-4] + ".camera.json", "w", encoding="utf-8") as fh:
        json.dump(cam, fh, indent=1)
    return {"name": job["name"], "png": job["png"]}


def _cut_shape(shape, cut):
    """Keep the half of `shape` on the `keep` side of the plane; also return the thin cap on the plane (cut face).
    Returns (None, None) when nothing of the shape is left."""
    import cadquery as cq
    ax, at, keep = cut["axis"], cut["at"], cut["keep"]
    bb = shape.BoundingBox()
    big = 10 * max(bb.xlen, bb.ylen, bb.zlen, 1.0) + 1000.0
    i = "xyz".index(ax)
    lo = [-big, -big, -big]
    hi = [big, big, big]
    if keep == "positive":
        lo[i], hi[i] = at, big
        slab = (at, at + 0.04)
    else:
        lo[i], hi[i] = -big, at
        slab = (at - 0.04, at)
    box = cq.Solid.makeBox(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], cq.Vector(*lo))
    try:
        part = shape.intersect(box)
    except Exception:
        return None, None
    if part is None or part.Volume() < 1e-6:
        return None, None
    s_lo = list(lo)
    s_hi = list(hi)
    s_lo[i], s_hi[i] = slab
    sbox = cq.Solid.makeBox(s_hi[0] - s_lo[0], s_hi[1] - s_lo[1], s_hi[2] - s_lo[2], cq.Vector(*s_lo))
    try:
        cap = shape.intersect(sbox)
        if cap is None or cap.Volume() < 1e-9:
            cap = None
    except Exception:
        cap = None
    return part, cap


# ---------------------------------------------------------------- planning (parent) -----------------------------------
def explode_offsets(names, bboxes, order, manual, gap, height):
    """Offsets per solid: `manual` wins; the rest are ranked (ASSEMBLY_ORDER, else z of the part's centre) and lifted along z.
    Parts whose centres are within 1 mm in z share a rank."""
    off = {n: (0.0, 0.0, 0.0) for n in names}
    auto = [n for n in names if n not in manual]
    if order:
        pos = {n: order.index(n) for n in order}
        auto.sort(key=lambda n: (pos.get(n, len(order)), (bboxes[n][0][2] + bboxes[n][1][2]) / 2))
        ranks, r, last = {}, 0, None
        for n in auto:
            p = pos.get(n, len(order))
            if last is not None and p != last:
                r += 1
            ranks[n] = r
            last = p
        # the order lists the first part first: it stays, later ones go up
    else:
        auto.sort(key=lambda n: bboxes[n][0][2])
        ranks, r, last = {}, 0, None
        for n in auto:
            zc = bboxes[n][0][2]
            if last is not None and zc - last > 1.0:
                r += 1
            ranks[n] = r
            last = zc
    for n in auto:
        off[n] = (0.0, 0.0, ranks[n] * gap)
    for n, v in manual.items():
        if n in off:
            off[n] = tuple(float(a) for a in v)
    return off


def _shift_bbox(bb, o):
    return (tuple(bb[0][i] + o[i] for i in range(3)), tuple(bb[1][i] + o[i] for i in range(3)))


def _union_bbox(bbs):
    lo = tuple(min(b[0][i] for b in bbs) for i in range(3))
    hi = tuple(max(b[1][i] for b in bbs) for i in range(3))
    return lo, hi


def plan_views(names, bboxes, meta, vcfg, cfg):
    """List of view specs {name, kind, dir, up, offsets, cut, title}. Names in vcfg['skip'] are left out."""
    skip = set(vcfg.get("skip", []))
    specs = []
    zero = {n: (0.0, 0.0, 0.0) for n in names}
    for n, (d, u) in ORTHO.items():
        if n in skip:
            continue
        specs.append({"name": n, "kind": "ortho", "dir": d, "up": u, "offsets": zero, "cut": None,
                      "title": n.upper(), "note": {"front": "seen from the front (-y)", "back": "seen from the back (+y)",
                                                   "top": "seen from above, back at the top", "bottom": "seen from below, front at the top",
                                                   "left": "seen from the left (-x), front on the right", "right": "seen from the right (+x), front on the left"}[n]})
    az, el = math.radians(vcfg.get("azimuth_deg", 35)), math.radians(vcfg.get("elevation_deg", 28))
    # eye at front-left-up: direction from the eye into the model
    dv = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), -math.sin(el))
    # azimuth turns the eye from -y towards -x: the viewer then looks along (+sin az, +cos az) horizontally
    up = (0, 0, 1)
    if "perspective" not in skip:
        specs.append({"name": "perspective", "kind": "persp", "dir": dv, "up": up, "offsets": zero, "cut": None,
                      "title": "PERSPECTIVE", "note": "from front, left, above"})
    if "exploded" not in skip:
        allbb = _union_bbox(list(bboxes.values()))
        height = allbb[1][2] - allbb[0][2]
        gap = float(vcfg.get("explode_gap", 0) or 0) or max(10.0, height / 4.0)
        off = explode_offsets(names, bboxes, meta.get("ASSEMBLY_ORDER") or [], {**meta.get("EXPLODE", {}), **vcfg.get("explode", {})}, gap, height)
        specs.append({"name": "exploded", "kind": "persp", "dir": dv, "up": up, "offsets": off, "cut": None,
                      "title": "EXPLODED", "note": "parts pulled apart, not to scale in z"})
    for s in vcfg.get("section", []) or []:
        ax = s["axis"].lower()
        keep = s.get("keep", "positive")
        if ax not in AXES or keep not in ("positive", "negative"):
            raise mc.MechError(f"[[views.section]] {s}: axis must be x|y|z and keep positive|negative")
        i = "xyz".index(ax)
        sgn = 1.0 if keep == "positive" else -1.0        # kept side positive: the viewer is on the negative side, looking +axis
        dv2 = tuple(AXES[ax][k] * sgn for k in range(3))
        up2 = (0, 1, 0) if ax == "z" else (0, 0, 1)
        specs.append({"name": "section_" + s["name"], "kind": "ortho", "dir": dv2, "up": up2, "offsets": zero,
                      "cut": {"axis": ax, "at": float(s["at"]), "keep": keep},
                      "title": f"SECTION {s['name'].upper()}  ({ax} = {float(s['at']):g}, keep {keep})", "note": ""})
    return specs


def clear_dir(d: str) -> None:
    """Empty the views folder (only files and the cache-free contents; the folder itself stays)."""
    if os.path.isdir(d):
        for n in os.listdir(d):
            p = os.path.join(d, n)
            try:
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            except OSError:
                pass
    os.makedirs(d, exist_ok=True)


def contact_sheet(files, out_png, cols=3, cell=520):
    from PIL import Image, ImageDraw
    ims = []
    for name, p in files:
        im = Image.open(p).convert("RGB")
        im.thumbnail((cell, int(cell * 0.78)))
        ims.append((name, im))
    if not ims:
        return
    rows = math.ceil(len(ims) / cols)
    ch = int(cell * 0.78) + 34
    sheet = Image.new("RGB", (cols * (cell + 16) + 16, rows * ch + 16), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    f = _font(20, True)
    for i, (name, im) in enumerate(ims):
        x = 16 + (i % cols) * (cell + 16)
        y = 16 + (i // cols) * ch
        dr.rectangle((x - 1, y - 1, x + cell, y + int(cell * 0.78) + 28), outline=(200, 204, 212))
        dr.text((x + 8, y + 4), name, fill=(45, 52, 66), font=f)
        sheet.paste(im, (x + (cell - im.width) // 2, y + 30 + (int(cell * 0.78) - im.height) // 2))
    sheet.save(out_png)


def run(args) -> int:
    job = mc.resolve(args)
    cfg = job.cfg
    vcfg = dict(cfg.get("views", {}))
    model_path = args.model or mc.path_of(cfg, "model")
    if not os.path.isfile(model_path):
        print(f"could not run: model file not found: {model_path}", file=sys.stderr)
        return 2
    mc.require_module("vtk", "pictures")
    mc.require_module("PIL", "pictures")
    mc.require_module("numpy", "pictures")
    rows = mc.Rows()
    t0 = time.time()
    solids, meta = load_model_full(model_path)
    for h in vcfg.get("hide", []):
        solids.pop(h, None)
    if not solids:
        print("could not run: build() returned no solids", file=sys.stderr)
        return 2
    names = list(solids)
    views_dir = os.path.join(job.out, "views")
    only = [s.strip() for s in args.only.split(",") if s.strip()] if args.only else None
    if args.only is not None and not only:
        raise mc.MechError("--only names no view")
    partial = bool(only) or args.no_clear                  # a full run is the only one that empties the folder
    if not partial:
        clear_dir(views_dir)
    os.makedirs(views_dir, exist_ok=True)
    cache = os.path.join(job.out, "cache", "views")
    os.makedirs(cache, exist_ok=True)
    tol, ang = float(vcfg.get("tolerance", 0.0008)), float(vcfg.get("angle", 0.15))
    # colours
    colcfg = {**{k: v for k, v in meta["COLOURS"].items()}, **vcfg.get("colours", {})}
    rgb = {}
    for i, n in enumerate(names):
        rgb[n] = resolve_colour(colcfg[n], cfg) if n in colcfg else default_colour(n, i)
    # BREP + stage 1
    jobs, breps, bboxes = [], {}, {}
    for n in names:
        key = hashlib.sha1(n.encode()).hexdigest()[:10]
        bp = os.path.join(cache, f"{key}.brep")
        solids[n].exportBrep(bp)
        sha = mc.sha256(bp)[:16]
        fp = os.path.join(cache, f"{key}_{sha}_{tol}_{ang}.faces.vtp")
        ep = os.path.join(cache, f"{key}_{sha}_{tol}_{ang}.edges.vtp")
        breps[n] = (bp, fp, ep)
        bb = solids[n].BoundingBox()
        bboxes[n] = ((bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax))
        if not (os.path.isfile(fp) and os.path.isfile(ep)):
            jobs.append((bp, fp, ep, tol, ang))
    nw = 1 if args.serial else min(mc.workers(), max(1, len(jobs)))
    print(f"tessellating {len(jobs)} of {len(names)} parts on {nw} worker(s) ...")
    if jobs:
        if nw == 1:
            for j in jobs:
                tess_task(j)
        else:
            with ProcessPoolExecutor(nw) as ex:
                for k, _ in enumerate(ex.map(tess_task, jobs), 1):
                    print(f"  tessellated {k}/{len(jobs)}")
    specs = plan_views(names, bboxes, meta, vcfg, cfg)
    if only:
        unknown = [x for x in only if x not in {sp["name"] for sp in specs}]
        if unknown:
            raise mc.MechError(f"--only: {', '.join(unknown)} is not a view of this model; the views are: {', '.join(sp['name'] for sp in specs)}")
    long_px = int(args.ppm or vcfg.get("long_px", 1500))
    margin = int(vcfg.get("margin_px", 120))
    fov = float(vcfg.get("fov_deg", 28))
    rjobs = []
    for sp in specs:
        if only and sp["name"] not in only:
            continue
        off = sp["offsets"]
        shown = [_shift_bbox(bboxes[n], off[n]) for n in names]
        bbox = _union_bbox(shown)
        if sp["cut"]:                                   # the visible part of the model is the kept half
            ax = "xyz".index(sp["cut"]["axis"])
            lo, hi = list(bbox[0]), list(bbox[1])
            if sp["cut"]["keep"] == "positive":
                lo[ax] = max(lo[ax], sp["cut"]["at"])
            else:
                hi[ax] = min(hi[ax], sp["cut"]["at"])
            if lo[ax] >= hi[ax]:
                rows.add(f"VW-{sp['name']}", "views", f"{sp['name']} cut inside the model", f"plane {sp['cut']['at']} outside {bbox[0][ax]:.1f}..{bbox[1][ax]:.1f}", "plane must cut the model", "fail")
                continue
            bbox = (tuple(lo), tuple(hi))
        cam = _make_camera(sp["kind"], sp, bbox, long_px, margin, fov)
        rjobs.append({"name": sp["name"], "png": os.path.join(views_dir, sp["name"] + ".png"), "camera": cam, "cut": sp["cut"],
                      "title": sp["title"], "note": sp.get("note", ""), "bbox": bbox, "dims": bool(vcfg.get("dims", True)), "titles": bool(vcfg.get("titles", True)),
                      "tol": tol, "ang": ang,
                      "items": [{"name": n, "brep": breps[n][0], "faces": breps[n][1], "edges": breps[n][2], "rgb": rgb[n], "offset": off[n]} for n in names]})
    nw = 1 if args.serial else min(mc.workers(), max(1, len(rjobs)))
    print(f"rendering {len(rjobs)} pictures on {nw} worker(s) ...")
    made = []
    if nw == 1:
        for j in rjobs:
            made.append(render_task(j))
    else:
        with ProcessPoolExecutor(nw) as ex:
            for r in ex.map(render_task, rjobs):
                made.append(r)
                print(f"  {r['name']}")
    # rows
    from PIL import Image
    import numpy as np
    for j in rjobs:
        p = j["png"]
        ok = os.path.isfile(p)
        if not ok:
            rows.add(f"VW-{j['name']}", "views", f"{j['name']} written", "missing", "file exists", "fail")
            continue
        im = np.asarray(Image.open(p).convert("L"))
        filled = float((im < 240).mean())
        rows.add(f"VW-{j['name']}", "views", f"{j['name']} picture", f"{im.shape[1]}x{im.shape[0]} px, {filled * 100:.1f} % drawn",
                 "not blank (> 0.5 % non-white)", "pass" if filled > 0.005 else "fail")
        cam = j["camera"]
        if cam["kind"] == "ortho" and not j["cut"]:
            # the drawn part must fill the box the camera data says it fills (proves the camera file)
            lo, hi = j["bbox"]
            pts = [project(cam, (x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
            px0, px1 = min(q[0] for q in pts), max(q[0] for q in pts)
            py0, py1 = min(q[1] for q in pts), max(q[1] for q in pts)
            body = im[int(py0) - 1:int(py1) + 2, int(px0) - 1:int(px1) + 2]
            ys, xs = np.where(im[int(max(py0 - 6, 0)):int(py1 + 6), int(max(px0 - 6, 0)):int(px1 + 6)] < 235)
            if len(xs):
                gx0, gx1 = xs.min() + max(px0 - 6, 0), xs.max() + max(px0 - 6, 0)
                err = max(abs(gx0 - px0), abs(gx1 - px1))
                rows.add(f"CAM-{j['name']}", "views", f"{j['name']} camera data matches the picture", f"edge error {err:.1f} px",
                         "<= 6 px (dimension lines and labels excluded)", "pass" if err <= 6 else "fail")
        em = cam.get("extent_mm")
    dims = _union_bbox(list(bboxes.values()))
    rows.add("VW-SIZE", "views", "overall size of the model (x, y, z)", " x ".join(f"{dims[1][i] - dims[0][i]:.1f}" for i in range(3)) + " mm",
             "written on the views", "pass")
    # every picture of the folder that this model's view list names: after a partial run that is the redrawn ones plus the kept ones
    present = [(sp["name"], os.path.join(views_dir, sp["name"] + ".png")) for sp in specs if os.path.isfile(os.path.join(views_dir, sp["name"] + ".png"))]
    kept = [n for n, _ in present if n not in {r["name"] for r in made}]
    if kept:
        print(f"note: {len(kept)} picture(s) were kept as they were ({', '.join(kept)}); they may be older than the model. Run views.py without --only to redraw all.")
        for n in kept:                                    # not checked in this run: not applicable (never a pass), so the headline says so
            rows.add(f"VW-{n}", "views", f"{n} picture", "kept from an earlier run, not redrawn", "a full run (without --only) checks every picture", "na")
    contact_sheet(present, os.path.join(views_dir, "contact_sheet.png"))
    man = {"model": os.path.abspath(model_path).replace("\\", "/"), "model_mtime": model_mtime(model_path),
           "parts": names, "assembly_order": meta["ASSEMBLY_ORDER"],
           "views": [{"name": n, "png": os.path.basename(pp), "camera": os.path.basename(pp)[:-4] + ".camera.json"} for n, pp in present],
           "overall_mm": [dims[1][i] - dims[0][i] for i in range(3)]}
    mc.atomic_write(os.path.join(views_dir, "views_manifest.json"), json.dumps(man, indent=1))
    rows.write(job.out, "views.py", [model_path])
    rows.print_table(only_bad=True)
    print(f"views in {views_dir} ({len(made)} pictures drawn" + (f", {len(kept)} kept" if kept else "") + f" + contact_sheet.png, {time.time() - t0:.1f} s)")
    print(rows.headline())
    return rows.exit_code()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="standard view set of the model")
    mc.add_std_args(ap)
    ap.add_argument("--model", help="model file (default [paths] model)")
    ap.add_argument("--only", help="comma list of view names to redraw; the other pictures are kept (only a full run empties the folder)")
    ap.add_argument("--ppm", type=int, help="long side of the model in pixels")
    ap.add_argument("--no-clear", action="store_true", help="do not empty the views folder first (a full run does)")
    ap.add_argument("--serial", action="store_true", help="one process (same pictures)")
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
