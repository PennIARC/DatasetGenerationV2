"""Background photo: v1 scale-to-cover + random zoom / offset; BG_AUGMENT adds flips, 90-degree rotations, a wider
zoom range and colour jitter (hue rotation, saturation, brightness, per-channel gain) so the 15 (+ new) photos
yield far more distinct grounds."""
import json
import os

import cv2
import numpy as np

import fx
from config import asset_path
from features import assets


def _load_index(cfg):
    """Parse assets_new/backgrounds_index.json -> {family: [(abs path, weight, category), ...]} (weight > 0, existing)."""
    def load():
        path = asset_path(cfg, cfg.BG_INDEX_PATH)
        if not os.path.isfile(path):
            return None
        with open(path) as f:
            d = json.load(f)
        root_new = os.path.dirname(path)
        fams = {}
        for b in d["backgrounds"]:
            if b.get("weight", 0) <= 0:
                continue
            full = (os.path.join(asset_path(cfg, cfg.BG_V1_DIR), b["path"]) if b["source"] == "v1"
                    else os.path.join(root_new, b["path"]))
            w = float(cfg.BG_WEIGHT_OVERRIDES.get(os.path.basename(b["path"]), b["weight"]))
            full_ = (os.path.join(asset_path(cfg, cfg.BG_V1_DIR), b["path"]) if b["source"] == "v1"
                     else os.path.join(root_new, b["path"]))
            w *= assets.audit_weight(cfg, full_)   # asset audit: hard-excluded -> 0, review -> x ASSET_REVIEW_WEIGHT
            if os.path.isfile(full) and w > 0:
                fams.setdefault(b["family"], []).append((full, w, b.get("category", "")))
        return {"families": fams, "family_weights": d.get("family_weights", {})}
    key = ("bgindex", asset_path(cfg, cfg.BG_INDEX_PATH), tuple(sorted(cfg.BG_WEIGHT_OVERRIDES.items())),
           bool(cfg.ASSET_AUDIT_FILTER), float(cfg.ASSET_REVIEW_WEIGHT))
    return assets._cached(key, load)


def pick_background(rng, cfg):
    """-> (path, info). BG_USE_INDEX (with NEW_ASSETS): family by BG_FAMILY_WEIGHTS (None = the index file's
    family_weights), then an item of that family with probability proportional to its weight. Otherwise the
    *_SOURCES folders (uniform within a folder; v1 mode = the 15 v1 photos). Always 2 draws."""
    idx = _load_index(cfg) if (cfg.NEW_ASSETS and cfg.BG_USE_INDEX) else None
    if not idx or not idx["families"]:
        return assets.pick_file(rng, cfg, "BACKGROUND"), {"sampling": "folders"}
    u, v = rng.random(), rng.random()
    fw = cfg.BG_FAMILY_WEIGHTS if cfg.BG_FAMILY_WEIGHTS is not None else idx["family_weights"]
    fams = [f for f in idx["families"] if fw.get(f, 0) > 0] or list(idx["families"])
    w = np.cumsum([fw.get(f, 1.0) for f in fams])
    fam = fams[min(int(np.searchsorted(w, u * w[-1], side="right")), len(fams) - 1)]
    items = idx["families"][fam]
    wi = np.cumsum([it[1] for it in items])
    path, _, cat = items[min(int(np.searchsorted(wi, v * wi[-1], side="right")), len(items) - 1)]
    return path, {"sampling": "index", "family": fam, "category": cat}


def sample_background_params(rng, cfg):
    """-> dict(file, flip_h, flip_v, rot90, zoom, off_x, off_y (fractions), hue, sat, bright, gains). Fixed draws."""
    path, binfo = pick_background(rng, cfg)
    u = rng.random(13)
    lerp = lambda r, t: float(r[0] + (r[1] - r[0]) * t)  # noqa: E731
    aug = bool(cfg.BG_AUGMENT)
    binfo["audit"] = assets.audit_status(cfg, path)
    return {"file": path, **binfo, "flip_h": aug and u[0] < cfg.BG_FLIP_PROB, "flip_v": aug and u[1] < cfg.BG_FLIP_PROB,
            "rot90": (1 + int(u[3] * 3)) if aug and u[2] < cfg.BG_ROT90_PROB else 0,
            "zoom": lerp(cfg.BG_ZOOM if aug else cfg.V1_BG_ZOOM, u[4]), "off_x": float(u[5]), "off_y": float(u[6]),
            "colour_jitter": aug, "hue": lerp(cfg.BG_HUE_SHIFT, u[7]), "sat": lerp(cfg.BG_SATURATION, u[8]),
            "bright": lerp(cfg.BG_BRIGHTNESS, u[9]), "gains": [lerp(cfg.BG_CHANNEL_GAIN, t) for t in u[10:13]]}


def make_background(p, W, H, smooth=True):
    """-> float32 RGB (H, W, 3). smooth=False reproduces v1's nearest-neighbour scaling."""
    if p["file"] is None:
        return np.full((H, W, 3), np.array([34, 139, 34], np.float32) / 255, np.float32)
    src = assets.load_rgb(p["file"])
    if p["flip_h"]:
        src = src[:, ::-1]
    if p["flip_v"]:
        src = src[::-1]
    src = np.rot90(src, p["rot90"])
    h, w = src.shape[:2]
    scale = max(W / w, H / h) * p["zoom"]
    cw, ch = min(w, int(np.ceil(W / scale))), min(h, int(np.ceil(H / scale)))
    ox, oy = int(p["off_x"] * (w - cw)), int(p["off_y"] * (h - ch))
    crop = np.ascontiguousarray(src[oy:oy + ch, ox:ox + cw])
    interp = (cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR) if smooth else cv2.INTER_NEAREST
    if smooth and scale > 1 and p.get("upscale_cubic"):   # SCENE_ZOOM_BG: sharper upscale of the magnified texture
        interp = cv2.INTER_CUBIC
    bg = cv2.resize(crop, (W, H), interpolation=interp).astype(np.float32) / 255.0
    if p["colour_jitter"]:
        bg = np.clip(fx.apply_matrix(bg, fx.colour_matrix(p["hue"], p["sat"], p["bright"], p["gains"])), 0, 1)
    return bg


def describe(p):
    """Sidecar form: path relative to the repository root (e.g. assets_new/backgrounds/bg_Grass003.jpg)."""
    f = p["file"]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {**p, "file": os.path.relpath(f, os.path.dirname(repo)) if f else None,
            "source": os.path.basename(os.path.dirname(os.path.dirname(f))) if f else None}
