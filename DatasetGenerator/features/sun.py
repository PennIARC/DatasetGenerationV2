"""Per-image illumination: one sun direction (or overcast sky) shared by mine shading and every shadow."""
import numpy as np


def sample_sun(rng, cfg):
    """-> dict(azimuth, elevation (deg), overcast (bool), shadow_strength, shadow_tint, penumbra_scale).

    Direct sun (prob 1 - OVERCAST_PROB): elevation ~ U(SUN_ELEVATION), strength ~ U(SHADOW_STRENGTH).
    Overcast: light is diffuse, so shadows are weak (U(OVERCAST_SHADOW_STRENGTH)) and very soft (penumbra x
    OVERCAST_PENUMBRA_SCALE); a nominal direction is still drawn (the brightest part of the sky). Always 5 draws.
    """
    u_over, az, el, s_sun, s_over = rng.random(), rng.uniform(*cfg.SUN_AZIMUTH), rng.uniform(*cfg.SUN_ELEVATION), \
        rng.uniform(*cfg.SHADOW_STRENGTH), rng.uniform(*cfg.OVERCAST_SHADOW_STRENGTH)
    tint = rng.uniform(*cfg.SHADOW_COOL_TINT)
    overcast = bool(u_over < cfg.OVERCAST_PROB)
    return {"azimuth": float(az), "elevation": float(el), "overcast": overcast,
            "shadow_strength": float(s_over if overcast else s_sun), "shadow_tint": float(tint),
            "penumbra_scale": float(cfg.OVERCAST_PENUMBRA_SCALE if overcast else 1.0)}


def sun_vector(az_deg, el_deg):
    """World direction towards the sun (x = image right, y = image up, z = towards the camera)."""
    az, el = np.deg2rad(az_deg), np.deg2rad(el_deg)
    return np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])


def shadow_offset_px(height_px, sun):
    """Image-space (dx, dy) of the shadow tip of a point `height_px` above the ground (image y points down)."""
    length = height_px / np.tan(np.deg2rad(sun["elevation"]))
    az = np.deg2rad(sun["azimuth"])
    return -np.cos(az) * length, np.sin(az) * length, length
