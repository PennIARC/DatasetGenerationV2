"""Cast shadows and contact ambient occlusion (SHADOWS).

Terminology: the umbra is the fully shadowed core; the penumbra is the soft transition at the shadow edge (the
sun is not a point). Here the penumbra is a Gaussian blur whose sigma grows with the shadow length, so low sun ->
long, softer shadows. Contact ambient occlusion (AO) is the extra darkening right where an object touches the
ground, because that spot sees less of the sky.

All functions return multiplicative factor patches (h, w, 3) for the ground; apply with fx.darken.
"""
import cv2
import numpy as np

import fx
from features.sun import shadow_offset_px


def penumbra_sigma(length_px, sun, cfg):
    return (cfg.PENUMBRA_BASE_PX + cfg.PENUMBRA_PER_LENGTH * length_px) * sun.get("penumbra_scale", 1.0)


def sweep_mask(alpha, dx, dy, pad):
    """Union of the mask translated by t * (dx, dy), t in [0, 1] (the shadow volume of an extruded silhouette):
    a grey-scale dilation with a line-shaped structuring element. Output canvas is padded by `pad` per side."""
    h, w = alpha.shape
    sh = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    sh[pad:pad + h, pad:pad + w] = alpha
    ix, iy = int(round(dx)), int(round(dy))
    if ix or iy:
        k = np.zeros((abs(iy) + 1, abs(ix) + 1), np.uint8)
        ax, ay = (0 if ix > 0 else -ix), (0 if iy > 0 else -iy)
        cv2.line(k, (ax, ay), (ax + ix, ay + iy), 1, 1)
        # cv2.dilate: out(p) = max_k src(p + k - anchor); we need src(p - t * offset) -> flipped kernel and anchor
        sh = cv2.dilate(sh, k[::-1, ::-1].copy(), anchor=(k.shape[1] - 1 - ax, k.shape[0] - 1 - ay))
    return sh


def debris_shadow(alpha, height_px, sun, strength, cfg, max_length=None, penumbra_per_length=None):
    """2D approximation for rocks / grass / sprite mines: the alpha silhouette swept away from the sun by
    height / tan(elevation) (capped at max_length px), blurred by the penumbra (sigma grows with the length; rocks use
    a larger ROCK_PENUMBRA_PER_LENGTH). -> (factor (h + 2 pad, w + 2 pad, 3), pad)."""
    dx, dy, length = shadow_offset_px(height_px, sun)
    if max_length is not None and length > max_length:
        dx, dy, length = dx * max_length / length, dy * max_length / length, max_length
    if penumbra_per_length is None:
        sigma = penumbra_sigma(length, sun, cfg)
    else:
        sigma = (cfg.PENUMBRA_BASE_PX + penumbra_per_length * length) * sun.get("penumbra_scale", 1.0)
    pad = int(np.ceil(max(abs(dx), abs(dy)) + 3 * sigma)) + 2
    cov = fx.gblur(sweep_mask(alpha, dx, dy, pad), sigma)
    return fx.shadow_factor(cov, strength, sun["shadow_tint"]), pad


def contact_shadow(alpha, width_px, sun, strength, width_frac, offset_frac):
    """Soft contact shadow / ambient occlusion under a rock (or clod / leaf clump): the alpha dilated and Gaussian-
    blurred by ~width_frac x object width, shifted slightly away from the sun, darkening the ground multiplicatively
    (no hard edge). -> (factor (h + 2 pad, w + 2 pad, 3), pad)."""
    r = max(0.5, width_frac * width_px)
    pad = int(np.ceil(4 * r + offset_frac * width_px)) + 2
    h, w = alpha.shape
    a = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    a[pad:pad + h, pad:pad + w] = alpha
    k = max(1, int(round(r * 0.6)))
    a = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    az = np.deg2rad(sun["azimuth"])
    off = offset_frac * width_px
    if off > 0.05:
        M = np.float32([[1, 0, -np.cos(az) * off], [0, 1, np.sin(az) * off]])
        a = cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR, borderValue=0)
    cov = fx.gblur(a, r)
    return (1.0 - strength * cov)[..., None] * np.ones(3, np.float32), pad


def mine_shadow(shadow_cov, alpha, length_px, sun, ao_strength, ao_sigma, cfg):
    """Mesh mine: shadow_cov is the rasterised projection of the 3D mesh along the sun (mesh.render_mine), on the
    mine's canvas. Penumbra blur + contact AO from the mine's footprint. -> factor (h, w, 3) on the same canvas."""
    sigma = penumbra_sigma(length_px, sun, cfg)
    cov = fx.gblur(shadow_cov, sigma)
    ao = fx.gblur(alpha, ao_sigma) * ao_strength
    return fx.shadow_factor(cov, sun["shadow_strength"], sun["shadow_tint"]) * (1.0 - ao)[..., None], sigma


def sample_ao(rng, cfg):
    return float(rng.uniform(*cfg.CONTACT_AO_STRENGTH)), float(rng.uniform(*cfg.CONTACT_AO_SIGMA))
