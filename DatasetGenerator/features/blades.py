"""Grass-blade debris (GRASS_BLADES): single blades, tufts and dry wisps, drawn under and over the mines.

Sources: fresh blades generated on the fly by assets_new/tools/make_grass_blades.py (seeded; imported through a
try/except so the generator still runs without it) and the pre-made RGBA pool in assets_new/grassBlades
(blade_*, tuft_*, wisp_*). Every instance gets its own size, rotation and colour adaptation, so even pool blades
are never pasted identically.

Scale: blades are sized in millimetres and converted with a per-image pixels-per-mm drawn from the mine scale range
(mine length 120 mm = MINE_PX_PER_UNIT x U(MINE_SCALE_MIN, MAX) px), so a 3 mm-wide blade is ~1-4 px wide.
Colour: blade RGB is pulled towards the local ground colour (per channel, ratio ** BLADE_COLOUR_ADAPT) so green
blades sit on green lawns and straw-coloured ones on dry ground, plus a small brightness jitter.
"""
import os
import sys

import cv2
import numpy as np

from config import asset_path
from features import assets, edges

KINDS = ("blade", "tuft", "wisp")


def _generator(cfg):
    """-> module make_grass_blades or None (missing tools folder / import error)."""
    def load():
        tools = asset_path(cfg, cfg.BLADE_TOOLS_DIR)
        try:
            if tools not in sys.path:
                sys.path.insert(0, tools)
            import make_grass_blades  # noqa: E402
            return make_grass_blades
        except Exception as e:  # pragma: no cover - environment dependent
            print(f"[blades] on-the-fly generator unavailable ({e}); using the PNG pool only")
            return None
    return assets._cached(("bladegen", asset_path(cfg, cfg.BLADE_TOOLS_DIR)), load)


def _pool(cfg):
    def load():
        files = assets.list_files(asset_path(cfg, cfg.BLADE_POOL_DIR))
        return {k: [f for f in files if os.path.basename(f).startswith(k + "_")] for k in KINDS}
    return assets._cached(("bladepool", asset_path(cfg, cfg.BLADE_POOL_DIR)), load)


def _rgba_to_float(rgba):
    return rgba[..., :3].astype(np.float32) / 255.0, rgba[..., 3].astype(np.float32) / 255.0


def make_blade_elements(cfg, rng, px_per_mm, count, fresh_budget):
    """-> list of debris elements (rgb_pm, alpha, x, y, height_px, shadow_scale, kind, adapt). fresh_budget: list with
    one int (remaining on-the-fly generations for this image, shared by both layers)."""
    gen = _generator(cfg)
    pool = _pool(cfg)
    kinds, kp = list(cfg.BLADE_KIND_PROBS), np.array(list(cfg.BLADE_KIND_PROBS.values()), float)
    out = []
    for _ in range(count):
        u = rng.random(8)
        kind = kinds[min(int(np.searchsorted(np.cumsum(kp / kp.sum()), u[0], side="right")), len(kinds) - 1)]
        size_mm = getattr(cfg, f"{kind.upper()}_SIZE_MM")
        L = max(4.0, (size_mm[0] + (size_mm[1] - size_mm[0]) * u[1]) * px_per_mm)
        angle = float(u[2] * 360)
        seed = int(u[3] * 2 ** 31)
        rgba = None
        if gen is not None and u[4] < cfg.BLADE_FRESH_PROB and fresh_budget[0] > 0:
            fresh_budget[0] -= 1
            if kind == "blade":
                wr = cfg.BLADE_WIDTH_MM
                W = max(1.0, (wr[0] + (wr[1] - wr[0]) * u[5]) * px_per_mm)
                rgba = gen.make_blade(seed, length=L, width=W, orientation=np.deg2rad(angle), supersample=4)
            elif kind == "tuft":
                rgba = gen.make_tuft(seed, size=L)
            else:
                wk = cfg.WISP_KINDS[min(int(u[5] * len(cfg.WISP_KINDS)), len(cfg.WISP_KINDS) - 1)] if cfg.WISP_KINDS else None
                try:
                    rgba = gen.make_wisp(seed, size=L, kind=wk)
                except TypeError:  # older generator without kinds
                    rgba = gen.make_wisp(seed, size=L)
            rgb, a = _rgba_to_float(rgba)
            # tufts / wisps come out at their own size; blades are already at L
            tw = int(round(a.shape[1] * (1.0 if kind == "blade" else min(1.0, L / max(a.shape)))))
            th = max(1, int(round(a.shape[0] * tw / max(a.shape[1], 1))))
            prgb, pa = edges.resize_rotate(rgb, a, max(tw, 1), th, None if kind == "blade" else angle,
                                           cfg.SOFT_EDGES, 0.0)
            src = "fresh"
        elif pool.get(kind):
            path = pool[kind][min(int(u[6] * len(pool[kind])), len(pool[kind]) - 1)]
            cut = assets.load_cutout(path)
            if cut is None:
                continue
            rgb, a, _ = cut
            f = L / max(a.shape)
            tw, th = max(1, int(round(a.shape[1] * f))), max(1, int(round(a.shape[0] * f)))
            prgb, pa = edges.resize_rotate(rgb, a, tw, th, angle, cfg.SOFT_EDGES, 0.0)
            src = "pool"
        else:
            continue
        if pa.max() <= 0.05:
            continue
        hr = getattr(cfg, f"{kind.upper()}_HEIGHT_MM")
        out.append({"type": "image", "rgb_pm": prgb, "alpha": pa, "kind": kind, "source": src,
                    "height_px": (hr[0] + (hr[1] - hr[0]) * u[7]) * px_per_mm, "shadow_scale": cfg.BLADE_SHADOW_SCALE,
                    "adapt": cfg.BLADE_COLOUR_ADAPT, "bright": float(rng.uniform(*cfg.BLADE_BRIGHTNESS))})
    return out


def adapt_colour(rgb_pm, alpha, target_rgb, k, bright=1.0):
    """Pull a premultiplied cut-out's mean colour towards target_rgb per channel: rgb *= (target / mean) ** k."""
    w = alpha.sum()
    if w <= 1e-6 or k <= 0:
        return rgb_pm * bright
    mean = rgb_pm.reshape(-1, 3).sum(0) / w
    gain = np.clip((np.asarray(target_rgb) + 1e-3) / (mean + 1e-3), 0.25, 4.0) ** k
    return (rgb_pm * (gain * bright).astype(np.float32)).astype(np.float32)


def local_colour_map(img, cells=(48, 27)):
    """Coarse map of the current composite for cheap 'local ground colour' look-ups."""
    return cv2.resize(img, cells, interpolation=cv2.INTER_AREA)


def lookup(cmap, x, y, W, H):
    gw, gh = cmap.shape[1], cmap.shape[0]
    return cmap[int(np.clip(y / H * gh, 0, gh - 1)), int(np.clip(x / W * gw, 0, gw - 1))]
