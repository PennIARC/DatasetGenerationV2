"""Scene zoom coupling (SCENE_ZOOM_COUPLING) and native output crop (OUTPUT_CROP).

Zoom coupling = "the camera moved closer": per image z = image mine scale / SCENE_ZOOM_REF_SCALE (the image scale is
the existing R(9) draw that already sets the ground px/mm, so grass blades sized in mm were scaled by it before).
Every PHYSICAL pixel size that is not already tied to the mine length or to px/mm is multiplied by z:
rocks, v1 grass clippings, leaf clumps, dirt snippets, ground dirt grains (sizes; their shadow heights / contact
shadows are fractions of the size and follow), the mine's contact band, contact AO, berm lip, exposed-part AO, soft
grain blur and soil grain size, the placement margin; debris COUNTS are multiplied by z ** -SCENE_ZOOM_COUNT_EXP
(2 = constant density per ground area) with stochastic rounding from own streams; the background texture is
magnified by z (capped, see zoom_background). SENSOR / optics effects stay in pixels: PSF, motion blur, noise,
chromatic aberration (pixel shift kept when cropping), vignette, JPEG, the 0.6 px penumbra base and the 0.8 px
cut-out feather (anti-aliasing).

Output crop: the scene is still rendered at SCREEN_WIDTH x SCREEN_HEIGHT; a crop window (own stream R(11), uniform
position) is chosen before the mines, mines are placed fully inside it (CROP_MINE_MARGIN), and the window is cut out
before the camera model (blur with a context pad so it equals blurring the full frame; noise / vignette /
contrast act on the crop as the camera's own sensor). No resize, no resampling.
"""
import numpy as np

# pixel-valued (min, max) ranges / scalars of the mine renderer that represent physical sizes -> x z
ZOOM_SCALED_PX = ("CONTACT_BAND_PX", "BERM_WIDTH_PX", "EXPOSED_AO_PX", "CONTACT_AO_SIGMA", "SOFT_GRAIN_BLUR_PX",
                  "SOIL_GRAIN_PX", "MINE_PLACEMENT_MARGIN")


def zoom_factor(image_scale, cfg):
    return float(image_scale) / float(cfg.SCENE_ZOOM_REF_SCALE)


def zoomed_config(cfg, z):
    """Shallow copy of cfg with the ZOOM_SCALED_PX values multiplied by z (lerp-sampled ranges -> same draws)."""
    from types import SimpleNamespace
    c = SimpleNamespace(**vars(cfg))
    for k in ZOOM_SCALED_PX:
        v = getattr(c, k)
        if isinstance(v, tuple):
            setattr(c, k, tuple(float(x) * z for x in v))
        elif k == "MINE_PLACEMENT_MARGIN":
            setattr(c, k, int(round(v * z)))
        else:
            setattr(c, k, float(v) * z)
    return c


def count_factor(z, cfg):
    return float(z) ** (-float(cfg.SCENE_ZOOM_COUNT_EXP))


def zoom_background(bgp, z, W, H, src_hw, cfg):
    """Magnify the background texture by z (camera closer), but cap the magnification (output px per source px) at
    max(SCENE_ZOOM_BG_MAX_MAG, the uncoupled magnification): never less zoom than without coupling, never a blurrier
    upscale than the cap. -> (zoom, info)."""
    h, w = src_hw
    if bgp["rot90"] % 2:
        h, w = w, h
    base = max(W / w, H / h)
    mag0 = base * bgp["zoom"]
    mag = min(mag0 * z, max(cfg.SCENE_ZOOM_BG_MAX_MAG, mag0))
    return mag / base, {"zoom_sampled": bgp["zoom"], "zoom_coupling": z, "magnification": mag,
                        "magnification_uncoupled": mag0, "capped": bool(mag < mag0 * z - 1e-9)}


def crop_window(rng, W, H, cw, ch):
    """Uniform crop position (always 2 draws). -> (x0, y0, cw, ch)."""
    u = rng.random(2)
    return int(u[0] * (W - cw + 1)), int(u[1] * (H - ch + 1)), int(cw), int(ch)


def stochastic_count(n, f, u):
    """floor(n f + u), u ~ U(0, 1): unbiased rounding of a scaled count."""
    return int(np.floor(n * f + u))
