"""Helpers for the v2 showcase. Imports the v2 generator read-only; writes only into docs/showcase/images/v2.
Run with the venv python3 (needs opencv-python-headless, numpy, scipy, trimesh, Pillow, matplotlib)."""
import os, sys
sys.dont_write_bytecode = True
ROOT = "/Users/pranavgupta/Desktop/PennAiR/IARCtesting/IARCdatasetGenerationV2"
GEN = ROOT + "/DatasetGenerator"
OUT = ROOT + "/docs/showcase/images/v2"
os.makedirs(OUT, exist_ok=True)
os.chdir(GEN)
sys.path.insert(0, GEN)
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from scene import render_scene
from features.camera import jpeg_roundtrip

W, H = 1920, 1080
_cache = {}


def render(seed, **ov):
    """render_scene with cache. Returns (rgb uint8, labels, meta). Keys of ov are controlPanel names."""
    key = (seed, repr(sorted(ov.items())))
    if key not in _cache:
        if len(_cache) > 40:
            _cache.clear()
        _cache[key] = render_scene(seed, dict(ov))
    return _cache[key]


def _font(sz):
    for p in ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def crop(img, cx, cy, w=240, h=135, zoom=4):
    """Crop a 16:9 window (w x h px) centred at (cx, cy) and enlarge by `zoom` with nearest neighbour."""
    x0 = int(np.clip(cx - w // 2, 0, img.shape[1] - w)); y0 = int(np.clip(cy - h // 2, 0, img.shape[0] - h))
    c = img[y0:y0 + h, x0:x0 + w]
    return cv2.resize(c, (w * zoom, h * zoom), interpolation=cv2.INTER_NEAREST), (x0, y0)


def box_px(label):
    _, xc, yc, w, h = label
    return xc * W, yc * H, w * W, h * H


def draw_boxes(img, labels, x0=0, y0=0, zoom=1, col=(0, 255, 0), th=2):
    im = img.copy()
    for l in labels:
        xc, yc, w, h = box_px(l)
        a = (int((xc - w / 2 - x0) * zoom), int((yc - h / 2 - y0) * zoom))
        b = (int((xc + w / 2 - x0) * zoom), int((yc + h / 2 - y0) * zoom))
        cv2.rectangle(im, a, b, col, th)
    return im


def save(img, name, q=88):
    """Save RGB array. name ends .jpg (q88) or .png. Returns the manifest path."""
    p = os.path.join(OUT, name)
    Image.fromarray(img).save(p, quality=q) if name.endswith(".jpg") else Image.fromarray(img).save(p, optimize=True)
    return "images/v2/" + name


def frame(rgb, width=1280):
    return cv2.resize(rgb, (width, width * H // W), interpolation=cv2.INTER_AREA)


def tag(img, text, pos="tl"):
    """Burn a small caption on an image copy."""
    im = Image.fromarray(img.copy()); d = ImageDraw.Draw(im); f = _font(max(14, img.shape[1] // 55))
    tw = d.textlength(text, font=f); pad = 5
    x = pad if "l" in pos else im.width - tw - 3 * pad
    y = pad if "t" in pos else im.height - f.size - 3 * pad
    d.rectangle([x - pad, y - pad, x + tw + pad, y + f.size + pad], fill=(0, 0, 0))
    d.text((x, y), text, fill=(255, 255, 255), font=f)
    return np.array(im)


def arrow_overlay(img, azimuth, elevation, cx=None, cy=None, label=True):
    """Small sun arrow: points the way the SUN is (azimuth 0 = image +x, 90 = image top). Shadows fall opposite."""
    im = Image.fromarray(img.copy()); d = ImageDraw.Draw(im)
    s = im.width / 1280.0
    cx = cx if cx is not None else 70 * s; cy = cy if cy is not None else 70 * s
    r = 44 * s
    d.ellipse([cx - r - 6 * s, cy - r - 6 * s, cx + r + 6 * s, cy + r + 6 * s], fill=(0, 0, 0))
    a = np.deg2rad(azimuth)
    dx, dy = np.cos(a), -np.sin(a)
    L = r * (0.45 + 0.55 * np.cos(np.deg2rad(elevation)))   # shorter arrow for a higher sun
    x1, y1 = cx + dx * L, cy + dy * L
    d.line([cx, cy, x1, y1], fill=(255, 210, 40), width=max(3, int(5 * s)))
    hx, hy = -dy, dx
    d.polygon([(x1 + dx * 12 * s, y1 + dy * 12 * s), (x1 + hx * 8 * s, y1 + hy * 8 * s), (x1 - hx * 8 * s, y1 - hy * 8 * s)], fill=(255, 210, 40))
    d.ellipse([cx - 4 * s, cy - 4 * s, cx + 4 * s, cy + 4 * s], fill=(255, 255, 255))
    if label:
        f = _font(int(15 * s)); t = f"sun az {azimuth:.0f}, el {elevation:.0f}"
        d.text((cx - r, cy + r + 10 * s), t, fill=(255, 255, 255), font=f, stroke_width=2, stroke_fill=(0, 0, 0))
    return np.array(im)


# ---------------------------------------------------------------- recording rocks (read-only monkeypatch of scene)
import scene as _scene
import objects as _objects
ROCKS = []


class _RecDebris(_objects.EnvironmentDebris):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        ROCKS.append([(e["x"], e["y"], e["alpha"].shape[1], e["alpha"].shape[0]) for e in self.elements
                      if e.get("kind") == "rock"])


_scene.EnvironmentDebris = _RecDebris


def rocks_of_last_render():
    """Rocks (x, y, w, h) of the layers of the LAST render (layer 0 = under the mines, layer 1 = over them)."""
    return ROCKS[-2:]


def render_rocks(seed, **ov):
    """Uncached render that also returns [(x, y, w, h)] of the rocks of the undergrowth layer."""
    ROCKS.clear()
    out = render_scene(seed, dict(ov))
    return out, [r for layer in ROCKS[:1] for r in layer]


BASE = dict(n_mines=1, mine_positions=[(960, 540)], mine_scale=0.35, mine_pose=(3, -2, 30), burial_prob=0)


def mine_crop(rgb, zoom=4, cx=960, cy=540):
    w, h = 1024 // zoom, 576 // zoom
    return crop(rgb, cx, cy, w, h, zoom)[0]


def O(label, params, image, caption=""):
    return {"label": label, "params": params, "image": image, "caption": caption}


def BA(label, before, after, bl, al, caption=""):
    return {"label": label, "before": before, "after": after, "before_label": bl, "after_label": al, "caption": caption}


def dump(name, obj):
    import json
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "w") as f:
        json.dump(obj, f, indent=1)


def tiles_grid(tiles, cols):
    rows = []
    for i in range(0, len(tiles), cols):
        r = tiles[i:i + cols]
        r += [np.zeros_like(tiles[0])] * (cols - len(r))
        rows.append(np.hstack(r))
    return np.vstack(rows)
