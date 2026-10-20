"""Mine albedo (base colour) per instance: realistic palette (COLOUR_PALETTE) or the v1 formula."""
import colorsys

import numpy as np


def colour_from_params(h, s, v, bleach=0.0, dirt_tint=0.0, brightness=1.0, dirt_rgb=(0.42, 0.33, 0.22)):
    """HSV (H deg, S, V in [0, 1]) + sun-bleaching a in [0, 1] (S *= 1 - 0.6 a, V += 0.3 a (1 - V)) + brightness
    multiplier on V + dirt tint t (mix towards dirt_rgb). -> RGB float array in [0, 1]."""
    s = s * (1.0 - 0.6 * bleach)
    v = v + 0.3 * bleach * (1.0 - v)
    v = float(np.clip(v * brightness, 0.03, 1.0))
    rgb = np.array(colorsys.hsv_to_rgb((h % 360) / 360.0, float(np.clip(s, 0, 1)), v))
    return (1 - dirt_tint) * rgb + dirt_tint * np.asarray(dirt_rgb)


def sample_colour_params(rng, cfg):
    """-> dict(family, h, s, v, bleach, dirt_tint, brightness). Always the same number of draws."""
    names = list(cfg.PALETTE)
    w = np.array([cfg.PALETTE[n][0] for n in names], float)
    u = rng.random(9)
    name = names[min(int(np.searchsorted(np.cumsum(w / w.sum()), u[0], side="right")), len(names) - 1)]
    _, hr, sr, vr = cfg.PALETTE[name]
    lerp = lambda r, t: r[0] + (r[1] - r[0]) * t  # noqa: E731
    return {"family": name, "h": lerp(hr, u[1]), "s": lerp(sr, u[2]), "v": lerp(vr, u[3]),
            "bleach": lerp(cfg.BLEACH_AMOUNT, u[5]) if u[4] < cfg.BLEACH_PROB else 0.0,
            "dirt_tint": lerp(cfg.DIRT_TINT_AMOUNT, u[7]) if u[6] < cfg.DIRT_TINT_PROB else 0.0,
            "brightness": lerp(cfg.BRIGHTNESS_JITTER, u[8])}


def sample_colour(rng, cfg):
    """-> (rgb float array in [0, 1], info dict)."""
    if cfg.MINE_COLOUR is not None:  # fixed colour for controlled comparisons: RGB in [0, 1]
        return np.asarray(cfg.MINE_COLOUR, float), {"family": "fixed"}
    if not cfg.COLOUR_PALETTE:
        u = rng.random(4)
        c = np.array(cfg.V1_BASE_COLOUR) + (2 * u[0] - 1) * cfg.V1_COMMON_SHIFT
        c = np.clip(c + (2 * u[1:] - 1) * cfg.V1_CHANNEL_JITTER, 0, 1)
        return c, {"family": "v1"}
    p = sample_colour_params(rng, cfg)
    rgb = colour_from_params(p["h"], p["s"], p["v"], p["bleach"], p["dirt_tint"], p["brightness"], cfg.DIRT_TINT_RGB)
    return rgb, p
