"""soften_alpha(rgba, width_px, noise_scale, seed) -> RGBA uint8.

Natural alpha edge for soil/dust snippets: distance-transform feather over `width_px` inside the
edge, a noise dissolve (grains/crumbs, grain size ~ `noise_scale` px) that only acts in the rim,
and colour bleed (rim/transparent pixels take the colour of nearby interior pixels, so no dark or
white fringe). Interior (further than width_px from the edge) is untouched. Seeded/deterministic.

    from soften_alpha import soften_alpha
    out = soften_alpha(np.asarray(Image.open(p).convert("RGBA")), width_px=random.uniform(3, 12),
                       noise_scale=2.5, seed=random.randrange(10**9))
"""
import numpy as np
from scipy import ndimage as ndi


def soften_alpha(rgba, width_px=6.0, noise_scale=2.5, seed=0, dissolve=1.0):
    rgba = np.asarray(rgba)
    rng = np.random.default_rng(seed)
    rgb = rgba[..., :3].astype(np.float64)
    a = rgba[..., 3].astype(np.float64) / 255.0
    inside = a > 0.5
    if not inside.any():
        return rgba.copy()
    pad = 2
    inside_p = np.pad(inside, pad)  # image border counts as edge only where the content touches it
    dist = ndi.distance_transform_edt(np.pad(inside, pad, mode="edge"))[pad:-pad, pad:-pad]
    f = np.clip(dist / max(width_px, 1e-3), 0, 1)
    f = f * f * (3 - 2 * f)
    z = ndi.gaussian_filter(rng.standard_normal(a.shape), max(noise_scale, .5))
    z = z / z.std()
    z2 = ndi.gaussian_filter(rng.standard_normal(a.shape), max(noise_scale, .5) * 2.8)
    z = 0.7 * z + 0.5 * z2 / z2.std()
    n = np.clip(0.5 + 0.30 * z / z.std(), 0, 1)
    t = f + (n - 0.5) * 1.8 * dissolve * (1 - f)
    s = np.clip((t - 0.10) / 0.45, 0, 1)
    s = s * s * (3 - 2 * s)
    new_a = np.minimum(a, 1.0) * s
    new_a = np.where(f >= 1.0, a, new_a)
    new_a = ndi.gaussian_filter(new_a, 0.5)  # 0.5 px antialias of grains
    # colour bleed: normalised convolution of interior colour
    sig = max(width_px / 2.0, 1.0)
    m = inside.astype(np.float64)
    bl = np.stack([ndi.gaussian_filter(rgb[..., c] * m, sig) for c in range(3)], -1)
    bm = ndi.gaussian_filter(m, sig)[..., None]
    bled = np.where(bm > 1e-4, bl / np.maximum(bm, 1e-4), rgb)
    w = (1 - f)[..., None] * 0.5
    out_rgb = rgb * (1 - w) + bled * w
    out_rgb = np.where((~inside)[..., None], bled, out_rgb)
    return np.dstack([np.clip(out_rgb, 0, 255), np.clip(new_a, 0, 1) * 255]).astype(np.uint8)
