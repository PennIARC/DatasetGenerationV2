"""Soil-displacement cues for partially buried mines (BURIAL_* flags), all on the mine's canvas.

Without these, a buried mine looks like a mine with a piece cut away. Real burial disturbs the soil:
  * clean_fragments      drop slivers / tiny islands the clip plane leaves on thin wings and rims
  * disturbed_patch      BURIAL_DISTURBED_SOIL: a darker, rougher patch of turned soil around the buried part
  * berm_ridge           BURIAL_BERM: a raised, clumpy ridge along the soil line, shaded by the sun (lit side
                         lighter, far side darker) and casting a short shadow onto the mine and the ground
  * dirty_exposed        BURIAL_DIRTY_EXPOSED: the exposed part gets an occlusion gradient at the soil line, is
                         darker / less saturated overall, and carries grains, streaks and a dusty film whose density
                         rises towards the buried side
  * clods                BURIAL_CLODS: a few displaced soil clods (assets_new/dirt clods) around the soil line
  * lift_blade           warp for over-layer grass blades crossing the soil line (lifted by the berm)
Effects scale with s = clip(burial fraction / 0.4, 0.25, 1.25): small burials are subtle, 40-50% clearly visible.
"""
import cv2
import numpy as np

import fx
from features import assets, blades, edges, shadows

K3 = np.ones((3, 3), np.uint8)


def _sun_dir_img(az_deg):
    """Unit vector towards the sun in image coordinates (x right, y down)."""
    a = np.deg2rad(az_deg)
    return np.array([np.cos(a), -np.sin(a)], np.float32)


def strength_scale(fraction):
    return float(np.clip(fraction / 0.4, 0.25, 1.25))


# ----------------------------------------------------------------------------------------------- fragments
def clean_mask(vis_mask, min_area_px, open_px=1):
    """Binary mask of what may stay visible: morphological opening (removes structures thinner than ~2 open_px + 1
    px), then connected components smaller than min_area_px are dropped (the largest one is always kept), then grown
    back by open_px so the anti-aliased rim of kept parts survives. -> uint8 keep mask (0 / 1)."""
    m = (vis_mask > 0).astype(np.uint8)
    if not m.any():
        return m
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * open_px + 1, 2 * open_px + 1))
    o = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(o, connectivity=8)
    keep = np.zeros_like(m)
    if n > 1:
        areas = st[1:, cv2.CC_STAT_AREA]
        big = int(np.argmax(areas)) + 1
        for i in range(1, n):
            if i == big or st[i, cv2.CC_STAT_AREA] >= min_area_px:
                keep[lab == i] = 1
    keep = cv2.dilate(keep, k) & m
    return keep


def soften_keep(alpha, keep):
    """Apply a keep mask to an anti-aliased alpha without hard cuts at partially covered rim pixels."""
    grow = cv2.dilate(keep, K3)
    return alpha * grow.astype(np.float32)


# ----------------------------------------------------------------------------------------------- geometry
def soil_line(vis, core):
    """Pixels where the visible mine touches the soil-covered / buried part. -> (line bool, distance to line px)."""
    v, c = (vis > 0.5).astype(np.uint8), (core > 0.5).astype(np.uint8)
    line = ((cv2.dilate(c, K3) > 0) & (v > 0)) | ((cv2.dilate(v, K3) > 0) & (c > 0))
    if not line.any():
        return line, np.full(vis.shape, 1e6, np.float32)
    return line, cv2.distanceTransform((~line).astype(np.uint8), cv2.DIST_L2, 3)


def soil_colour(local_blur, cfg):
    """Colour of turned soil under this ground: the local ground colour pulled towards a brown soil tone, more so on
    green (grassy) ground where digging exposes earth, not grass. Brightness follows the local ground. (h, w, 3)."""
    lum = fx.luminance(local_blur)[..., None]
    green = np.clip((local_blur[..., 1] - local_blur[..., 0]) * 6 + 0.2, 0, 1)[..., None]
    lo, hi = cfg.BURIAL_SOIL_MIX
    mix = lo + (hi - lo) * green
    ref = np.asarray(cfg.BURIAL_SOIL_RGB, np.float32)
    brown = ref / float(ref @ fx.LUMA) * np.maximum(lum, 0.08)
    return (local_blur * (1 - mix) + brown * mix).astype(np.float32)


# ----------------------------------------------------------------------------------------------- params
def sample_params(rng, cfg):
    u = rng.random(24)
    lerp = lambda r, t: float(r[0] + (r[1] - r[0]) * t)  # noqa: E731
    return {"ridge_width_frac": lerp(cfg.BERM_RIDGE_WIDTH_FRAC, u[0]), "ridge_height_frac": lerp(cfg.BERM_RIDGE_HEIGHT_FRAC, u[1]),
            "ridge_opacity": lerp(cfg.BERM_RIDGE_OPACITY, u[2]),
            "patch_radius_frac": lerp(cfg.DISTURBED_RADIUS_FRAC, u[3]), "patch_darken": lerp(cfg.DISTURBED_DARKEN, u[4]),
            "patch_desat": lerp(cfg.DISTURBED_DESAT, u[5]), "patch_opacity": lerp(cfg.DISTURBED_OPACITY, u[6]),
            "ao_px": lerp(cfg.EXPOSED_AO_PX, u[7]), "ao_strength": lerp(cfg.EXPOSED_AO_STRENGTH, u[8]),
            "exp_darken": lerp(cfg.EXPOSED_DARKEN, u[9]), "exp_desat": lerp(cfg.EXPOSED_DESAT, u[10]),
            "grain_density": lerp(cfg.EXPOSED_GRAIN_DENSITY, u[11]), "streaks": lerp(cfg.EXPOSED_STREAKS, u[12]),
            "film": lerp(cfg.EXPOSED_FILM, u[13]), "clod_count": lerp(cfg.BURIAL_CLOD_COUNT, u[14]),
            "streak_angle": float(u[15] * 180), "seed": int(u[16] * 2 ** 31)}


# ----------------------------------------------------------------------------------------------- disturbed soil
def disturbed_patch(alpha_full, buried, local, L, p, s, rng, cfg):
    """Turned-soil patch around the buried part (drawn on the ground before the mine). -> (rgb_pm, alpha)."""
    h, w = alpha_full.shape
    seed_m = ((buried > 0.5) | False).astype(np.uint8)
    if not seed_m.any():
        return np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
    R = max(2.0, p["patch_radius_frac"] * L)
    d = cv2.distanceTransform(1 - seed_m, cv2.DIST_L2, 3)
    n = fx.fbm(h, w, max(2.0, 0.2 * L), rng)
    a = np.clip(1 - d / (R * (0.5 + 1.0 * n)), 0, 1)          # irregular, noise-modulated boundary
    a = fx.gblur(a, max(1.0, 0.05 * L)) * p["patch_opacity"] * min(1.0, s)
    tex = 0.8 + 0.4 * fx.fbm(h, w, max(1.5, 0.03 * L), rng, octaves=3)   # rough, clumpy texture
    base = soil_colour(fx.gblur(local, max(1.0, 0.1 * L)), cfg)
    lum = fx.luminance(base)[..., None]
    col = (base * (1 - p["patch_desat"]) + lum * p["patch_desat"]) * p["patch_darken"] * tex[..., None]
    col = col * np.array([1.02, 0.98, 0.94], np.float32)          # turned soil: slightly warmer / browner
    return (col * a[..., None]).astype(np.float32), a.astype(np.float32)


# ----------------------------------------------------------------------------------------------- berm ridge
def berm_ridge(line_dist, core, vis, local, L, sun, p, s, rng, cfg):
    """Raised, clumpy ridge along the soil line with sun-consistent shading and a short cast shadow.
    -> (rgb_pm, alpha, shadow_cov) on the canvas; shadow_cov darkens mine and ground (apply under the ridge)."""
    h, w = line_dist.shape
    width = max(1.5, p["ridge_width_frac"] * L)
    n = fx.fbm(h, w, max(2.0, 0.06 * L), rng)
    clumps = fx.fbm(h, w, max(1.5, 0.025 * L), rng, octaves=2)
    prof = np.clip(1 - line_dist / (width * (0.5 + n)), 0, 1)      # irregular width
    # the ridge sits on the soil side and only laps onto the exposed mine by ~25% of its width
    inside = cv2.distanceTransform((vis > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
    prof *= np.clip(1 - inside / max(1.0, 0.25 * width), 0, 1)
    height = fx.gblur(prof ** 0.7 * (0.7 + 0.6 * clumps), max(0.8, 0.15 * width))
    a = np.clip(height * 1.6, 0, 1) * p["ridge_opacity"] * min(1.0, s)
    # shading from the height field: lit where the surface faces the sun
    gy, gx = np.gradient(height)
    sd = _sun_dir_img(sun["azimuth"])
    shade = -(gx * sd[0] + gy * sd[1]) * (width * 1.5)            # >0 on the sunlit slope
    k = cfg.BERM_RIDGE_SHADE * sun["shadow_strength"] / 0.45
    shade = np.clip(1 + k * np.clip(shade, -1, 1), 0.6, 1.3)
    base = soil_colour(fx.gblur(local, max(1.0, 0.05 * L)), cfg) * 0.95 * (0.8 + 0.4 * clumps)[..., None]
    rgb = base * shade[..., None]
    # cast shadow of the ridge (height ~ ridge_height_frac x L) away from the sun
    hpx = p["ridge_height_frac"] * L * min(1.0, s)
    length = hpx / np.tan(np.deg2rad(sun["elevation"]))
    dx, dy = -sd[0] * length, -sd[1] * length
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    sh = cv2.warpAffine((height > 0.25).astype(np.float32), M, (w, h), flags=cv2.INTER_LINEAR)
    sh = fx.gblur(np.clip(sh - (height > 0.25), 0, 1), max(0.7, 0.3 * length))
    return (rgb * a[..., None]).astype(np.float32), a.astype(np.float32), sh.astype(np.float32)


# ----------------------------------------------------------------------------------------------- exposed part
def dirty_exposed(rgb_pm, alpha, line_dist, local, L, p, s, rng, cfg):
    """Darker / less saturated exposed part, occlusion gradient at the soil line, grains + streaks + film whose
    density rises towards the buried side. Works on the premultiplied mine colour. -> rgb_pm'."""
    h, w = alpha.shape
    m = alpha > 0
    if not m.any():
        return rgb_pm
    toward = np.exp(-line_dist / max(1.0, 0.35 * L))              # 1 at the soil line -> 0 far away
    out = rgb_pm.copy()
    lum = fx.luminance(out)[..., None]
    ds = p["exp_desat"] * s
    out = out * (1 - ds) + lum * ds
    out *= (1 - p["exp_darken"] * s * (0.5 + 0.5 * toward))[..., None]
    ao = p["ao_strength"] * np.exp(-line_dist / max(0.5, p["ao_px"])) * min(1.0, s)
    out *= (1 - ao)[..., None]
    soil = soil_colour(fx.gblur(local, max(1.0, 0.1 * L)), cfg) * 0.9
    # dusty film
    film = p["film"] * s * (0.3 + 0.7 * toward) * fx.fbm(h, w, max(2.0, 0.15 * L), rng)
    # grains: fine noise thresholded with a density that rises towards the soil line
    g = fx.fbm(h, w, 1.2, rng, octaves=2)
    dens = np.clip(p["grain_density"] * s * (0.3 + 1.7 * toward), 0, 0.6)
    ga = np.clip((g - (1 - dens)) / 0.04, 0, 1) * 0.8
    # streaks: noise smeared along one direction
    ang = np.deg2rad(p["streak_angle"])
    klen = max(3, int(0.12 * L)) | 1
    ker = np.zeros((klen, klen), np.float32)
    c = klen // 2
    cv2.line(ker, (int(c - np.cos(ang) * c), int(c - np.sin(ang) * c)), (int(c + np.cos(ang) * c), int(c + np.sin(ang) * c)), 1.0, 1)
    ker /= ker.sum()
    st = cv2.filter2D(rng.random((h, w), dtype=np.float32), -1, ker)
    st = (st - st.mean()) / (st.std() + 1e-6)
    sa = np.clip((st - 1.2) / 0.8, 0, 1) * p["streaks"] * s * 3 * (0.3 + 0.7 * toward)
    d = np.clip(np.maximum(np.maximum(film, ga), sa), 0, 0.9)
    tone = (0.7 + 0.5 * fx.fbm(h, w, 2.0, rng, octaves=1))[..., None]
    out = out * (1 - d[..., None]) + (soil * tone) * (alpha * d)[..., None]
    return out.astype(np.float32)


# ----------------------------------------------------------------------------------------------- clods
def clods(cfg, line, L, sun, p, s, rng, local):
    """A few displaced soil clods along / near the soil line. -> list of (rgb_pm, alpha, x, y, shadow_factor, pad)
    in canvas coordinates (centre placed near random soil-line pixels)."""
    ys, xs = np.nonzero(line)
    files = [f for f in (assets.list_files(assets.asset_path(cfg, d)) for d, _ in cfg.DIRT_SOURCES) for f in f
             if "clod" in f.rsplit("/", 1)[-1] and assets.audit_status(cfg, f) != "exclude"]
    n = int(round(p["clod_count"] * s))
    out = []
    soil_col = soil_colour(fx.gblur(local, max(1.0, 0.1 * L)), cfg) * 0.9
    if not len(xs) or not files or n <= 0:
        return out
    for _ in range(n):
        u = rng.random(6)
        cut = assets.load_cutout(files[min(int(u[0] * len(files)), len(files) - 1)])
        if cut is None:
            continue
        rgb, a, _ = cut
        size = max(3, int((cfg.BURIAL_CLOD_SIZE_FRAC[0] + (cfg.BURIAL_CLOD_SIZE_FRAC[1] - cfg.BURIAL_CLOD_SIZE_FRAC[0]) * u[1]) * L))
        th = max(2, int(size * a.shape[0] / a.shape[1]))
        prgb, pa = edges.resize_rotate(rgb, a, size, th, float(u[2] * 360), True, 0.6)
        i = min(int(u[3] * len(xs)), len(xs) - 1)
        off = (u[4] - 0.5) * 0.25 * L
        cx, cy = xs[i] + off * np.cos(u[5] * 6.28), ys[i] + off * np.sin(u[5] * 6.28)
        tgt = soil_col[int(np.clip(cy, 0, soil_col.shape[0] - 1)), int(np.clip(cx, 0, soil_col.shape[1] - 1))]
        prgb = blades.adapt_colour(prgb, pa, tgt, cfg.BURIAL_CLOD_COLOUR_ADAPT, 1.0)
        f, pad = shadows.debris_shadow(pa, 0.25 * size, sun, sun["shadow_strength"], cfg, max_length=size)
        out.append((prgb, pa, int(cx - pa.shape[1] / 2), int(cy - pa.shape[0] / 2), f, pad))
    return out


# ----------------------------------------------------------------------------------------------- blades
def lift_blade(rgb_pm, alpha, zone_w, lift_px, up_dir, shadow_strength):
    """Warp an over-layer blade where it crosses the soil-line zone: pixels move by lift_px * zone_w along up_dir
    (away from the shadow direction, i.e. the blade rides over the berm), a soft shadow is left under the lifted part,
    and the lifted part is slightly brightened. zone_w: (h, w) weight in [0, 1] on the blade's own canvas.
    -> (rgb_pm, alpha, shadow_factor (h, w))."""
    h, w = alpha.shape
    if zone_w.max() <= 0.01:
        return rgb_pm, alpha, np.ones((h, w), np.float32)
    zw = fx.gblur(zone_w.astype(np.float32), 1.5)
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    mx = gx - up_dir[0] * lift_px * zw
    my = gy - up_dir[1] * lift_px * zw
    a2 = cv2.remap(alpha, mx, my, cv2.INTER_LINEAR, borderValue=0)
    c2 = cv2.remap(rgb_pm, mx, my, cv2.INTER_LINEAR, borderValue=0)
    c2 = c2 * (1 + 0.12 * zw)[..., None]
    # shadow left on the surface below the lifted segment (where the blade would have lain)
    sh = fx.gblur(alpha * zw, 1.0) * (1 - a2)
    return c2.astype(np.float32), a2.astype(np.float32), (1 - shadow_strength * 0.9 * sh).astype(np.float32)
