"""Call-outs, motion arrows and a warning frame drawn on a picture, from a small TOML; refuses overlapping call-out boxes.

What it does
    Opens a picture (a `views.py` or `render_blender.py` PNG), reads its camera file (`<stem>.camera.json`, written next to it) and draws:
      call-outs   white box with a dark frame, the first text line in bold, leader lines ending in a dot on every named point
                  (a point is `{mm = [x, y, z]}` in model millimetres, projected with the camera; `{px = [x, y]}` in pixels; or
                  `{frac = [u, v]}` as fractions of the picture); style "threadlocker" adds a blue drop and a blue frame, style "warning"
                  adds a red frame and a "!" badge
      arrows      orange motion arrows (where a part goes) between two points
      warning     a red frame round given points (or a pixel rectangle) with a red "!" badge: the one thing that goes wrong
      crop        the result is cropped to the drawing plus its call-outs plus a pad
    Check rows (`<out>/checks/annotate.json`; the output picture is NOT written when one fails, unless --force):
      call-out boxes overlap       no two call-out boxes (placed or automatic) overlap
      box inside the picture       every call-out box lies inside the picture plus the `grow` margin
      points on the picture        every anchor lies inside the picture (a mm point behind the camera or outside fails)
      camera data                  a mm point needs the camera file ("could not run" without it)
    A call-out without `box` is placed automatically: rings of positions around its anchor, nearest first, the first that overlaps no other
    box and stays inside the canvas.

Why it exists (the real failure, told without names)
    Assembly pictures were annotated by eye, in an image editor; after a model change the dots pointed at empty air and two boxes sat on top
    of each other in the printed manual. Anchors in model millimetres follow the model, and an overlap is a failed row instead of a surprise.

Usage
    python -I scripts/annotate.py SPEC.toml [SPEC2.toml ...] [--out DIR] [--force]
    Importable: annotate(spec_dict, base_dir, out_png) -> (rows, size)

Config (the spec TOML; one picture per file)
    [image]   file = "views/front.png", camera = "views/front.camera.json" (default beside the file), out = "name" (output stem),
              crop = true, pad = 30, grow = [left, top, right, bottom] px of white added round the picture (room for call-outs)
    [[callout]]  text = "Lid|1 pc" (| or newline starts a line), anchors = [ {mm=[x,y,z]}, ... ] (or anchor = {...}), box = {px=[x,y]} | {frac=[u,v]}
                 (the box centre), style = "normal" | "threadlocker" | "warning", size = font px (default from the picture width)
    [[arrow]]    from = {...}, to = {...}, label = "", width = px
    [warning]    points = [ {...}, ... ] (frame round them) or rect = [x0, y0, x1, y1] px, pad = 24, text = "" (adds a warning call-out)

Exit codes: 0 all pictures written and every row passes; 1 a row failed (picture not written unless --force); 2 spec, picture or PIL missing.
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import math

import mech_common as mc

INK = (29, 35, 48)
MUTED = (91, 100, 117)
ARROW = (232, 89, 12)
BLUE = (25, 103, 210)
RED = (201, 42, 42)
WHITE = (255, 255, 255)


def _font(size, bold=False):
    from PIL import ImageFont
    names = (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]) + ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for n in names:
        for d in ("C:/Windows/Fonts", ""):
            try:
                return ImageFont.truetype(os.path.join(d, n) if d else n, int(size))
            except OSError:
                continue
    try:
        import matplotlib
        return ImageFont.truetype(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), int(size))
    except Exception:
        return ImageFont.load_default()


def _anchor_px(a, cam, w, h, grow):
    """Pixel position of an anchor dict, in the canvas (picture + grow). Returns (x, y) or raises KeyError with a reason."""
    if "px" in a:
        return (a["px"][0] + grow[0], a["px"][1] + grow[1])
    if "frac" in a:
        return (a["frac"][0] * w + grow[0], a["frac"][1] * h + grow[1])
    if "mm" in a:
        if cam is None:
            raise KeyError("no camera file for a point given in mm")
        import views
        x, y, d = views.project(cam, a["mm"])
        if cam["kind"] != "ortho" and d <= 0:
            raise KeyError(f"point {a['mm']} is behind the camera")
        return (x + grow[0], y + grow[1])
    raise KeyError(f"anchor needs mm, px or frac: {a}")


def _anchors(c):
    if "anchors" in c:
        return list(c["anchors"])
    if "anchor" in c:
        return [c["anchor"]]
    return []


def _overlap(a, b, gap=4):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def _drop(draw, cx, cy, r, col):
    draw.ellipse([cx - r, cy - r * 0.4, cx + r, cy + r * 1.6], fill=col)
    draw.polygon([(cx - r * 0.86, cy + r * 0.1), (cx + r * 0.86, cy + r * 0.1), (cx, cy - r * 1.5)], fill=col)


def _arrow(draw, p, q, width, col):
    x0, y0 = p
    x1, y1 = q
    ang = math.atan2(y1 - y0, x1 - x0)
    head = width * 3.4
    bx, by = x1 - head * math.cos(ang), y1 - head * math.sin(ang)
    draw.line([(x0, y0), (bx, by)], fill=col, width=int(width))
    l = (bx + head * 0.55 * math.cos(ang + math.pi / 2), by + head * 0.55 * math.sin(ang + math.pi / 2))
    r = (bx + head * 0.55 * math.cos(ang - math.pi / 2), by + head * 0.55 * math.sin(ang - math.pi / 2))
    draw.polygon([(x1, y1), l, r], fill=col)
    draw.ellipse([x0 - width / 2, y0 - width / 2, x0 + width / 2, y0 + width / 2], fill=col)


def _box_size(draw, text, size, style):
    lines = text.replace("|", "\n").split("\n")
    fonts = [_font(size if i == 0 else size * 0.92, bold=(i == 0)) for i in range(len(lines))]
    widths = [draw.textlength(ln, font=f) for ln, f in zip(lines, fonts)]
    heights = [f.getbbox("Ag")[3] - f.getbbox("Ag")[1] + 4 for f in fonts]
    extra = size * 1.5 if style in ("threadlocker", "warning") else 0
    padx, pady = size * 0.55, size * 0.35
    return lines, fonts, max(widths) + 2 * padx + extra, sum(heights) + 2 * pady, heights, padx, pady, extra


def annotate(spec: dict, base_dir: str, out_png: str | None, rows: mc.Rows, force=False, name="picture"):
    """Draw one picture. Returns the size of the written picture or None when not written."""
    from PIL import Image, ImageDraw
    im_spec = spec["image"]
    src = im_spec["file"] if os.path.isabs(im_spec["file"]) else os.path.join(base_dir, im_spec["file"])
    if not os.path.isfile(src):
        raise mc.MechError(f"picture not found: {src}")
    cam_path = im_spec.get("camera") or (os.path.splitext(src)[0] + ".camera.json")
    cam_path = cam_path if os.path.isabs(cam_path) else os.path.join(base_dir, cam_path)
    cam = None
    if os.path.isfile(cam_path):
        with open(cam_path, encoding="utf-8") as f:
            cam = json.load(f)
    im0 = Image.open(src).convert("RGB")
    w0, h0 = im0.size
    grow = [int(v) for v in im_spec.get("grow", [0, 0, 0, 0])]
    im = Image.new("RGB", (w0 + grow[0] + grow[2], h0 + grow[1] + grow[3]), WHITE)
    im.paste(im0, (grow[0], grow[1]))
    W, H = im.size
    d = ImageDraw.Draw(im)
    # extent of the drawing before anything is drawn on it
    mask = im.convert("L").point(lambda v: 255 if v < 247 else 0)
    ext = list(mask.getbbox() or (0, 0, W, H))
    used = list(ext)
    fsize = max(18, int(w0 / 36))
    problems = 0
    could_not = False

    def grow_used(b):
        used[0], used[1], used[2], used[3] = min(used[0], b[0]), min(used[1], b[1]), max(used[2], b[2]), max(used[3], b[3])

    def pts_of(lst, what):
        nonlocal could_not
        out = []
        for a in lst:
            try:
                p = _anchor_px(a, cam, w0, h0, grow)
            except KeyError as e:
                rows.add(f"ANN-{name}-PT", "annotate", f"{name}: {what} anchor", str(e), "anchor can be projected", "could_not_run")
                could_not = True
                continue
            out.append(p)
        return out

    callouts = spec.get("callout", [])
    # first pass: sizes, explicit positions
    items = []
    for i, c in enumerate(callouts):
        style = c.get("style", "normal")
        size = c.get("size", fsize)
        lines, fonts, bw, bh, hts, padx, pady, extra = _box_size(d, c["text"], size, style)
        targets = pts_of(_anchors(c), f"call-out {i + 1}")
        items.append({"c": c, "style": style, "lines": lines, "fonts": fonts, "bw": bw, "bh": bh, "hts": hts, "padx": padx, "pady": pady,
                      "extra": extra, "targets": targets, "box": None, "size": size})
    warn = spec.get("warning")
    wr = None
    if warn:
        if "rect" in warn:
            x0, y0, x1, y1 = warn["rect"]
            wr = [x0 + grow[0], y0 + grow[1], x1 + grow[0], y1 + grow[1]]
        else:
            ps = pts_of(warn.get("points", []), "warning")
            if ps:
                pad = warn.get("pad", 24)
                wr = [min(p[0] for p in ps) - pad, min(p[1] for p in ps) - pad, max(p[0] for p in ps) + pad, max(p[1] for p in ps) + pad]
        if warn.get("text"):
            tg = [((wr[0] + wr[2]) / 2, (wr[1] + wr[3]) / 2)] if wr else []
            lines, fonts, bw, bh, hts, padx, pady, extra = _box_size(d, warn["text"], fsize, "warning")
            items.append({"c": {"text": warn["text"]}, "style": "warning", "lines": lines, "fonts": fonts, "bw": bw, "bh": bh, "hts": hts, "padx": padx,
                          "pady": pady, "extra": extra, "targets": tg, "box": None, "size": fsize, "from_warning": True})
    for it in items:
        b = it["c"].get("box")
        if b:
            cx, cy = ((b["px"][0] + grow[0], b["px"][1] + grow[1]) if "px" in b else (b["frac"][0] * w0 + grow[0], b["frac"][1] * h0 + grow[1]))
            it["box"] = (cx - it["bw"] / 2, cy - it["bh"] / 2, cx + it["bw"] / 2, cy + it["bh"] / 2)
    placed = [it["box"] for it in items if it["box"]]
    avoid = [pt for o in items for pt in o["targets"]]
    for a in spec.get("arrow", []):                          # keep boxes off the arrows too
        try:
            p, q = _anchor_px(a["from"], cam, w0, h0, grow), _anchor_px(a["to"], cam, w0, h0, grow)
        except KeyError:
            continue
        n = max(2, int(math.dist(p, q) // 20))
        avoid += [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(n + 1)]
    # automatic positions: rings around the anchor
    for it in items:
        if it["box"]:
            continue
        tg = it["targets"]
        cx = sum(p[0] for p in tg) / len(tg) if tg else W / 2
        cy = sum(p[1] for p in tg) / len(tg) if tg else H / 2
        best = None
        for r in range(int(it["bh"] * 0.9), int(max(W, H)), max(12, int(it["bh"] * 0.25))):
            for k in range(24):
                ang = 2 * math.pi * k / 24 + 0.3
                bx, by = cx + r * math.cos(ang), cy + r * math.sin(ang)
                bb = (bx - it["bw"] / 2, by - it["bh"] / 2, bx + it["bw"] / 2, by + it["bh"] / 2)
                if bb[0] < 6 or bb[1] < 6 or bb[2] > W - 6 or bb[3] > H - 6:
                    continue
                if any(_overlap(bb, o) for o in placed):
                    continue
                if any(bb[0] - 14 < tx < bb[2] + 14 and bb[1] - 14 < ty < bb[3] + 14 for (tx, ty) in avoid):
                    continue                      # never cover an anchor or an arrow
                best = bb
                break
            if best:
                break
        it["box"] = best
        if best:
            placed.append(best)
    # checks
    over = []
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            if items[a]["box"] and items[b]["box"] and _overlap(items[a]["box"], items[b]["box"], gap=0):
                over.append((items[a]["lines"][0], items[b]["lines"][0]))
    rows.add(f"ANN-{name}-OVERLAP", "annotate", f"{name}: call-out boxes do not overlap", "; ".join(f"'{a}' over '{b}'" for a, b in over) if over else f"{len(items)} boxes, none overlap",
             "no overlapping boxes", "fail" if over else "pass")
    outside = [it["lines"][0] for it in items if it["box"] is None or it["box"][0] < 0 or it["box"][1] < 0 or it["box"][2] > W or it["box"][3] > H]
    rows.add(f"ANN-{name}-INSIDE", "annotate", f"{name}: call-out boxes inside the picture (grow {grow})", "; ".join(outside) if outside else "all inside",
             "inside the picture; use grow for room", "fail" if outside else "pass")
    offpic = []
    for it in items:
        for p in it["targets"]:
            if not (0 <= p[0] <= W and 0 <= p[1] <= H):
                offpic.append(f"{it['lines'][0]} at ({p[0]:.0f}, {p[1]:.0f})")
    extra_pts = [(f"arrow {k + 1}", p) for k, a in enumerate(spec.get("arrow", [])) for p in pts_of([a["from"], a["to"]], "arrow")]
    if warn:
        extra_pts += [("warning", p) for p in (pts_of(warn.get("points", []), "warning") if "points" in warn else [])]
    for what, p in extra_pts:
        if not (0 <= p[0] <= W and 0 <= p[1] <= H):
            offpic.append(f"{what} at ({p[0]:.0f}, {p[1]:.0f})")
    rows.add(f"ANN-{name}-POINTS", "annotate", f"{name}: anchors on the picture", "; ".join(offpic) if offpic else "all inside", "inside the picture", "fail" if offpic else "pass")
    bad = bool(over or outside or offpic)
    if (bad and not force) or could_not:
        return None
    # draw: warning frame, arrows, call-outs
    if wr:
        d.rectangle(wr, outline=RED, width=max(4, fsize // 4))
        r = fsize * 0.7
        bx, by = wr[0], wr[1]
        d.ellipse([bx - r, by - r, bx + r, by + r], fill=RED, outline=WHITE, width=3)
        d.text((bx, by), "!", fill=WHITE, font=_font(r * 1.4, True), anchor="mm")
        grow_used((wr[0] - r, wr[1] - r, wr[2], wr[3]))
    for a in spec.get("arrow", []):
        p = pts_of([a["from"]], "arrow")
        q = pts_of([a["to"]], "arrow")
        if not p or not q:
            continue
        wd = a.get("width", max(6, fsize // 3))
        _arrow(d, p[0], q[0], wd, ARROW)
        if a.get("label"):
            mx, my = (p[0][0] + q[0][0]) / 2, (p[0][1] + q[0][1]) / 2
            f = _font(fsize * 0.9, True)
            bb = d.textbbox((mx, my - wd * 2.2), a["label"], font=f, anchor="mm")
            d.rectangle((bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2), fill=WHITE)
            d.text((mx, my - wd * 2.2), a["label"], fill=ARROW, font=f, anchor="mm")
        grow_used((min(p[0][0], q[0][0]) - 20, min(p[0][1], q[0][1]) - 20, max(p[0][0], q[0][0]) + 20, max(p[0][1], q[0][1]) + 20))
    for it in items:
        bx0, by0, bx1, by1 = it["box"]
        frame = {"threadlocker": BLUE, "warning": RED}.get(it["style"], INK)
        lw = max(3, int(it["size"] / 9))
        for (tx, ty) in it["targets"]:
            sx, sy = min(max(tx, bx0), bx1), min(max(ty, by0), by1)
            if bx0 < tx < bx1 and by0 < ty < by1:
                continue
            d.line([(sx, sy), (tx, ty)], fill=frame, width=max(2, lw - 1))
            r = max(6, it["size"] * 0.3)
            d.ellipse([tx - r, ty - r, tx + r, ty + r], fill=frame, outline=WHITE, width=2)
        d.rounded_rectangle((bx0, by0, bx1, by1), radius=it["size"] * 0.4, fill=WHITE, outline=frame, width=lw)
        x = bx0 + it["padx"] + it["extra"]
        y = by0 + it["pady"]
        if it["style"] == "threadlocker":
            _drop(d, bx0 + it["padx"] + it["size"] * 0.5, by0 + it["bh"] / 2 - it["size"] * 0.3, it["size"] * 0.42, BLUE)
        if it["style"] == "warning":
            cx, cy, r = bx0 + it["padx"] + it["size"] * 0.55, by0 + it["bh"] / 2, it["size"] * 0.55
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
            d.text((cx, cy), "!", fill=WHITE, font=_font(it["size"] * 0.9, True), anchor="mm")
        for k, (ln, f, hh) in enumerate(zip(it["lines"], it["fonts"], it["hts"])):
            col = (frame if it["style"] != "normal" else INK) if k == 0 else MUTED
            d.text((x, y), ln, fill=col, font=f, anchor="la")
            y += hh
        grow_used(it["box"])
    if im_spec.get("crop", True):
        pad = int(im_spec.get("pad", 30))
        im = im.crop((max(0, used[0] - pad), max(0, used[1] - pad), min(W, used[2] + pad), min(H, used[3] + pad)))
    if out_png:
        os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
        im.save(out_png)
    return im.size


def run(args) -> int:
    try:
        job = mc.resolve(args)
    except mc.MechError:
        if not args.out:
            raise
        job = mc.Job(os.getcwd(), mc.load_config(os.getcwd()), os.path.abspath(args.out))
    mc.require_module("PIL", "pictures")
    rows = mc.Rows()
    written = []
    for sp in args.specs:
        if not os.path.isfile(sp):
            print(f"could not run: spec not found: {sp}", file=sys.stderr)
            return 2
        spec = mc.load_toml(sp)
        if "image" not in spec:
            print(f"could not run: {sp}: no [image] table", file=sys.stderr)
            return 2
        stem = spec["image"].get("out") or os.path.splitext(os.path.basename(spec["image"]["file"]))[0]
        out_png = os.path.join(job.out, "manual", "annotated", stem + ".png")
        size = annotate(spec, os.path.dirname(os.path.abspath(sp)), out_png, rows, force=args.force, name=stem)
        if size:
            written.append(out_png)
            print(f"wrote {out_png} ({size[0]}x{size[1]})")
    rows.write(job.out, "annotate.py", list(args.specs))
    rows.print_table(only_bad=True)
    print(rows.headline())
    return rows.exit_code()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="call-outs on a picture")
    ap.add_argument("specs", nargs="+", help="spec TOML files")
    mc.add_std_args(ap)
    ap.add_argument("--force", action="store_true", help="write the picture even when a row fails")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except mc.MechError as e:
        print(f"could not run: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
