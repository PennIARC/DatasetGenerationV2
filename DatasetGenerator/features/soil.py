"""Soil blending (SOIL_BLEND) and the burial soil overlay (BURIAL).

fBm ("fractal Brownian motion") noise = several octaves of smooth random noise summed with halving amplitude;
it gives natural-looking blotchy variation used here for dust coverage, the soil line and grain texture.
All functions take an explicit params dict (from the sample_* functions) that includes a noise seed, so they are
deterministic and can be called with hand-picked values.
"""
import cv2
import numpy as np

import fx


# ----------------------------------------------------------------------------------------------- dust on the mine
def triangular(r, t):
    """Inverse CDF of a triangular distribution (low, mode, high) at t in [0, 1]; a 2-tuple is uniform."""
    if len(r) == 2:
        return float(r[0] + (r[1] - r[0]) * t)
    lo, mo, hi = (float(v) for v in r)
    if hi <= lo:
        return lo
    c = (mo - lo) / (hi - lo)
    return float(lo + np.sqrt(t * (hi - lo) * (mo - lo))) if t < c else float(hi - np.sqrt((1 - t) * (hi - lo) * (hi - mo)))


def sample_soil_params(rng, cfg):
    u = rng.random(8)
    lerp = lambda r, t: float(r[0] + (r[1] - r[0]) * t)  # noqa: E731
    return {"dust_strength": triangular(cfg.DUST_STRENGTH, u[0]), "dust_noise_scale": lerp(cfg.DUST_NOISE_SCALE, u[1]),
            "band_px": lerp(cfg.CONTACT_BAND_PX, u[2]), "band_darken": lerp(cfg.CONTACT_BAND_DARKEN, u[3]),
            "band_dust": lerp(cfg.CONTACT_BAND_DUST, u[4]), "grain_density": lerp(cfg.GRAIN_DENSITY, u[5]),
            "grain_opacity": lerp(cfg.GRAIN_OPACITY, u[6]), "noise_seed": int(u[7] * 2 ** 31)}


def harmonize_gain(local_bg, footprint, scene_luma, cfg):
    """Exposure match: mine *= (local ground luminance / image luminance) ** HARMONIZE_LOCAL *
    (image luminance / reference) ** HARMONIZE_GLOBAL, clipped. A mine in a shaded / dark patch of the photo gets
    darker, in a bright photo brighter."""
    lum_local = float(fx.luminance(local_bg)[footprint].mean()) if footprint.any() else scene_luma
    g = (lum_local / max(scene_luma, 1e-3)) ** cfg.HARMONIZE_LOCAL * (scene_luma / cfg.HARMONIZE_REF_LUMA) ** cfg.HARMONIZE_GLOBAL
    return float(np.clip(g, *cfg.HARMONIZE_CLIP))


def soil_blend(rgb_pm, alpha, alpha_full, local_bg, length_px, scene_luma, p, cfg):
    """Dust layer tinted by the local ground (blurred composite under the mine), fBm-modulated; darker / dustier
    contact band where the mine meets the ground; sparse soil grains; exposure harmonisation.
    rgb_pm / alpha: premultiplied mine; local_bg: (h, w, 3) composite under the mine canvas. -> (rgb_pm', info).
    All noise fields are computed on the box of the UNCLIPPED silhouette (not the whole canvas, whose size depends on
    the shadow), so the dust pattern is identical with and without burial."""
    ys, xs = np.nonzero(alpha_full > 0.01)
    if len(xs) == 0:
        return rgb_pm, {"harmonize_gain": 1.0}
    pad = 8
    y0, y1 = max(0, ys.min() - pad), min(alpha.shape[0], ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(alpha.shape[1], xs.max() + 1 + pad)
    r = (slice(y0, y1), slice(x0, x1))
    out = rgb_pm.copy()
    out[r], info = _soil_blend(rgb_pm[r], alpha[r], alpha_full[r], local_bg[r], length_px, scene_luma, p, cfg)
    return out, info


def _soil_blend(rgb_pm, alpha, alpha_full, local_bg, length_px, scene_luma, p, cfg):
    rng = np.random.default_rng(p["noise_seed"])
    h, w = alpha.shape
    L = length_px
    lb = fx.gblur(local_bg, max(1.0, cfg.LOCAL_BG_SIGMA_FRAC * L))
    foot = cv2.dilate((alpha_full > 0.1).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    gain = harmonize_gain(local_bg, foot, scene_luma, cfg)
    rgb = rgb_pm * gain
    n = fx.fbm(h, w, max(2.0, p["dust_noise_scale"] * L), rng)
    dust = p["dust_strength"] * np.clip(1.5 * n - 0.25, 0, 1)
    inside = (alpha > 0.5).astype(np.uint8)
    dist = cv2.distanceTransform(inside, cv2.DIST_L2, 3)
    band = np.clip(1 - dist / max(p["band_px"], 1e-3), 0, 1) * (alpha > 0)
    rgb = rgb * (1 - p["band_darken"] * band)[..., None]
    dust = np.clip(dust + p["band_dust"] * band, 0, 1)
    if p["grain_density"] > 0 and inside.any():
        g = fx.fbm(h, w, 1.5, rng, octaves=2)
        thr = np.quantile(g[alpha_full > 0.5] if (alpha_full > 0.5).any() else g[inside > 0], 1 - p["grain_density"])
        ga = np.clip((g - thr) / 0.03, 0, 1) * p["grain_opacity"]
        gcol = lb * (0.55 + 0.6 * fx.fbm(h, w, 2.0, rng, octaves=1))[..., None]
        lb = lb * (1 - ga[..., None]) + gcol * ga[..., None]
        dust = np.maximum(dust, ga)
    out = rgb * (1 - dust[..., None]) + lb * (alpha * dust)[..., None]
    return out.astype(np.float32), {"harmonize_gain": gain, **{k: v for k, v in p.items() if k != "noise_seed"}}


# ----------------------------------------------------------------------------------------------- burial
def sample_burial_overlay_params(rng, cfg):
    u = rng.random(5)
    lerp = lambda r, t: float(r[0] + (r[1] - r[0]) * t)  # noqa: E731
    return {"edge_noise": lerp(cfg.SOIL_EDGE_NOISE, u[0]), "berm_width_px": lerp(cfg.BERM_WIDTH_PX, u[1]),
            "berm_opacity": lerp(cfg.BERM_OPACITY, u[2]), "berm_darken": lerp(cfg.BERM_DARKEN, u[3]),
            "noise_seed": int(u[4] * 2 ** 31)}


def burial_overlay(alpha, alpha_full, height, local_bg, length_px, p):
    """Soil over a partially buried mine: (1) a rough soil line: mine pixels whose surface is within a noisy margin
    (edge_noise mesh units, fBm) above the soil plane get covered; (2) a berm / soil lip: a band of slightly darker
    disturbed soil along the edge of the buried region, irregular width. Colour = local ground (lightly blurred),
    darkened, fBm-textured. -> (soil_rgb_pm (h, w, 3), soil_alpha (h, w)); composite over the mine."""
    rng = np.random.default_rng(p["noise_seed"])
    h, w = alpha.shape
    L = length_px
    hgt = np.nan_to_num(height, nan=1.0)
    amp = p["edge_noise"]
    n1 = fx.fbm(h, w, max(2.0, 0.08 * L), rng)
    cover = np.clip((amp * n1 - hgt) / (0.25 * amp + 1e-6), 0, 1) * (alpha > 0)
    buried = np.clip(alpha_full - alpha, 0, 1)
    core = ((buried > 0.5) | (cover > 0.5)).astype(np.uint8)
    vis = ((alpha > 0.5) & (cover <= 0.5)).astype(np.uint8)
    bw = p["berm_width_px"]
    # the berm follows the TRUE soil line only: pixels where the still-visible mine touches the soil-covered part.
    # (Measuring from the whole buried region would also draw a band along the original, unburied outline.)
    k3 = np.ones((3, 3), np.uint8)
    line = ((cv2.dilate(core, k3) > 0) & (vis > 0)) | ((cv2.dilate(vis, k3) > 0) & (core > 0))
    if line.any():
        dist = cv2.distanceTransform((~line).astype(np.uint8), cv2.DIST_L2, 3)
        n2 = fx.fbm(h, w, max(2.0, 0.05 * L), rng)
        berm = np.clip(1 - dist / (bw * (0.4 + 1.2 * n2)), 0, 1)
        berm = fx.gblur(berm, 0.7) * p["berm_opacity"]
    else:
        berm = np.zeros((h, w), np.float32)
    a = np.maximum(cover, berm).astype(np.float32)
    soil = fx.gblur(local_bg, 1.0) * p["berm_darken"] * (0.85 + 0.3 * fx.fbm(h, w, 2.0, rng, octaves=3))[..., None]
    return (soil * a[..., None]).astype(np.float32), a


# ----------------------------------------------------------------------------------------------- ground dirt
def dirt_grain(size, base_col, local_col, rng, cfg):
    """SOIL_BLEND replacement for v1's hard dirt squares: a soft irregular grain whose colour mixes the v1 dirt colour
    with the darkened local ground. -> (rgb_pm, alpha, offset) where offset is the patch's shift from (x, y)."""
    s = int(size)
    p = s + 6
    a = np.zeros((p, p), np.float32)
    u = rng.random(6)
    ax = (max(1, int(s * (0.25 + 0.35 * u[0]))), max(1, int(s * (0.2 + 0.25 * u[1]))))
    cv2.ellipse(a, (p // 2, p // 2), ax, float(u[2] * 180), 0, 360, 1.0, -1, cv2.LINE_AA)
    a *= 0.6 + 0.4 * fx.fbm(p, p, max(2, s / 3), rng, octaves=2)
    a = fx.gblur(a, 0.7) * (0.6 + 0.4 * u[3])
    mix = cfg.DIRT_LOCAL_MIX[0] + (cfg.DIRT_LOCAL_MIX[1] - cfg.DIRT_LOCAL_MIX[0]) * u[4]
    col = (1 - mix) * np.asarray(base_col) + mix * np.asarray(local_col) * (0.55 + 0.3 * u[5])
    return (col[None, None] * a[..., None]).astype(np.float32), a, -3
