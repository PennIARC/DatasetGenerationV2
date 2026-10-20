"""Camera model applied to the whole composite: PSF / motion blur (BLUR) and either v1's shader or the v2 per-image
photometric randomisation (PHOTOMETRIC_JITTER), then JPEG.

PSF = point-spread function: how a single point of light is smeared by the lens (defocus ~ Gaussian) or by motion
during the exposure (a short line). Applying it to the full composite blurs mines, debris and background alike, so
the mine edges are exactly as sharp as everything else.
"""
import cv2
import numpy as np

import fx


def sample_camera_params(rng, cfg):
    """-> dict with every camera parameter for one image (flags decide which are used). Fixed number of draws."""
    u = rng.random(20)
    lerp = lambda r, t: float(r[0] + (r[1] - r[0]) * t)  # noqa: E731
    p = {"blur": bool(cfg.BLUR), "psf_sigma": lerp(cfg.PSF_SIGMA, u[0]),
         "motion_px": lerp(cfg.MOTION_BLUR_LENGTH, u[2]) if u[1] < cfg.MOTION_BLUR_PROB else 0.0,
         "motion_angle": float(u[3] * 180), "post": bool(cfg.ENABLE_POST_PROCESSING),
         "photometric": bool(cfg.PHOTOMETRIC_JITTER), "noise_seed": int(u[19] * 2 ** 31)}
    if cfg.PHOTOMETRIC_JITTER:
        p.update(exposure=lerp(cfg.EXPOSURE, u[4]), gamma=lerp(cfg.GAMMA, u[5]), wb_r=lerp(cfg.WB_GAIN, u[6]),
                 wb_b=lerp(cfg.WB_GAIN, u[7]), saturation=lerp(cfg.SATURATION, u[8]), contrast=lerp(cfg.CONTRAST, u[9]),
                 noise_sigma=lerp(cfg.NOISE_SIGMA, u[10]), noise_chroma=lerp(cfg.NOISE_CHROMA, u[11]),
                 aberration=lerp(cfg.ABERRATION, u[12]), vignette=lerp(cfg.VIGNETTE, u[13]),
                 jpeg_quality=int(round(lerp(cfg.JPEG_QUALITY_RANGE, u[14]))))
    else:
        p.update(v1_noise_strength=lerp(cfg.V1_NOISE_STRENGTH, u[15]), aberration=cfg.V1_ABERRATION,
                 vignette=cfg.V1_VIGNETTE, contrast=cfg.V1_CONTRAST, jpeg_quality=int(cfg.JPEG_QUALITY))
    return p


def apply_blur(img, sigma, motion_px=0.0, motion_angle=0.0):
    img = fx.gblur(img, sigma)
    if motion_px > 0:
        img = fx.motion_blur(img, motion_px, motion_angle)
    return img


def apply_camera(img, p):
    """img float32 RGB [0, 1] -> float32 RGB [0, 1] (before JPEG)."""
    rng = np.random.default_rng(p["noise_seed"])
    if p["blur"]:
        img = apply_blur(img, p["psf_sigma"], p["motion_px"], p["motion_angle"])
    if p["post"]:
        if p["photometric"]:
            img = fx.photometric(img, rng, p)
        else:
            img = fx.v1_shader(img, rng, p["v1_noise_strength"], p["aberration"], p["vignette"], p["contrast"])
    return np.clip(img, 0, 1)


def encode_jpeg(rgb_u8, quality):
    """-> JPEG bytes (BGR order handled here)."""
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    return buf.tobytes()


def jpeg_roundtrip(rgb_u8, quality):
    """Apply JPEG compression artefacts in memory (what the saved file will look like)."""
    return cv2.cvtColor(cv2.imdecode(np.frombuffer(encode_jpeg(rgb_u8, quality), np.uint8), cv2.IMREAD_COLOR),
                        cv2.COLOR_BGR2RGB)
