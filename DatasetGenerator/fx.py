"""Image-space helpers for the v2 generator: noise, blurs, region-clipped compositing, post-processing.

All images are float32 RGB in [0, 1], shape (H, W, 3); masks / alphas are float32 (H, W) in [0, 1].
"Premultiplied" RGBA means the RGB channels are already multiplied by alpha (rgb_pm = rgb * a), so
compositing is out = rgb_pm + (1 - a) * dst and resampling never bleeds the (undefined) colour of
transparent pixels into the edge (no dark / bright fringes).
"""
import cv2
import numpy as np

LUMA = np.array([0.299, 0.587, 0.114], np.float32)


# ----------------------------------------------------------------------------------------------- noise
def fbm(h, w, scale_px, rng, octaves=4, persistence=0.5):
    """Fractal Brownian motion (fBm): a sum of value-noise octaves, each twice the frequency and `persistence`
    times the amplitude of the previous one. Value noise = random values on a coarse grid, bicubically
    upsampled. scale_px = size of the coarsest features. -> (h, w) float32 in [0, 1] (min/max normalised)."""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    s = max(float(scale_px), 1.0)
    for _ in range(octaves):
        gh, gw = int(np.ceil(h / s)) + 3, int(np.ceil(w / s)) + 3
        grid = rng.random((gh, gw), dtype=np.float32)
        up = cv2.resize(grid, (int(gw * s), int(gh * s)), interpolation=cv2.INTER_CUBIC)
        oy, ox = rng.integers(0, max(1, up.shape[0] - h)), rng.integers(0, max(1, up.shape[1] - w))
        out += amp * up[oy:oy + h, ox:ox + w]
        total += amp
        amp *= persistence
        s = max(s / 2.0, 1.0)
    out /= total
    lo, hi = float(out.min()), float(out.max())
    return (out - lo) / (hi - lo + 1e-6)


# ----------------------------------------------------------------------------------------------- blurs
def gblur(img, sigma):
    if sigma <= 0.05:
        return img
    return cv2.GaussianBlur(img, (0, 0), sigmaX=float(sigma), borderType=cv2.BORDER_REFLECT)


def motion_blur(img, length, angle_deg):
    """Line-shaped point-spread function (camera / drone motion during exposure)."""
    k = int(np.ceil(length)) | 1
    k = max(k, 3)
    ker = np.zeros((k, k), np.float32)
    c = (k - 1) / 2
    a = np.deg2rad(angle_deg)
    for t in np.linspace(-length / 2, length / 2, 4 * k):
        x, y = c + t * np.cos(a), c - t * np.sin(a)
        x0, y0 = int(np.floor(x)), int(np.floor(y))
        fx, fy = x - x0, y - y0
        for dx, dy, wgt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            if 0 <= x0 + dx < k and 0 <= y0 + dy < k:
                ker[y0 + dy, x0 + dx] += wgt
    ker /= ker.sum()
    return cv2.filter2D(img, -1, ker, borderType=cv2.BORDER_REFLECT)


# ----------------------------------------------------------------------------------------------- regions
def clip_region(H, W, x, y, h, w):
    """Intersect a (h, w) patch placed at (x, y) with an (H, W) image. -> (dst_slices, src_slices) or None."""
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return None
    return (slice(y0, y1), slice(x0, x1)), (slice(y0 - y, y1 - y), slice(x0 - x, x1 - x))


def crop_padded(img, x, y, h, w):
    """Crop (h, w) at (x, y), replicating the border where the window leaves the image."""
    H, W = img.shape[:2]
    out = np.empty((h, w) + img.shape[2:], img.dtype)
    xs = np.clip(np.arange(x, x + w), 0, W - 1)
    ys = np.clip(np.arange(y, y + h), 0, H - 1)
    out[:] = img[ys[:, None], xs[None, :]]
    return out


def over(dst, rgb_pm, alpha, x, y):
    """Premultiplied 'over' composite of a patch into dst (in place), clipped to the image."""
    r = clip_region(dst.shape[0], dst.shape[1], x, y, alpha.shape[0], alpha.shape[1])
    if r is None:
        return
    d, s = r
    a = alpha[s][..., None]
    dst[d] = rgb_pm[s] + (1.0 - a) * dst[d]


def darken(dst, factor, x, y):
    """Multiply dst by a (h, w) or (h, w, 3) factor patch, in place, clipped."""
    r = clip_region(dst.shape[0], dst.shape[1], x, y, factor.shape[0], factor.shape[1])
    if r is None:
        return
    d, s = r
    f = factor[s]
    dst[d] *= f[..., None] if f.ndim == 2 else f


def accumulate_alpha(acc, alpha, x, y):
    """acc = 1 - (1 - acc)(1 - alpha) (union of soft masks), in place, clipped."""
    r = clip_region(acc.shape[0], acc.shape[1], x, y, alpha.shape[0], alpha.shape[1])
    if r is None:
        return
    d, s = r
    acc[d] = 1.0 - (1.0 - acc[d]) * (1.0 - alpha[s])


def shadow_factor(cov, strength, tint):
    """Ground multiplier under a shadow coverage map: 1 - strength * cov * w, w = per-channel weights; a cool
    tint (tint > 0) removes more red than blue, because shadowed ground is lit only by the bluish sky."""
    w = np.array([1.0 + 0.5 * tint, 1.0, 1.0 - tint], np.float32)
    return 1.0 - strength * cov[..., None] * w


def shift_mask(alpha, dx, dy, pad):
    """Translate a mask by (dx, dy) px (sub-pixel, bilinear) into a canvas padded by `pad` on every side."""
    h, w = alpha.shape
    M = np.float32([[1, 0, dx + pad], [0, 1, dy + pad]])
    return cv2.warpAffine(alpha, M, (w + 2 * pad, h + 2 * pad), flags=cv2.INTER_LINEAR, borderValue=0)


# ----------------------------------------------------------------------------------------------- colour
def colour_matrix(hue_deg=0.0, sat=1.0, bright=1.0, gains=(1.0, 1.0, 1.0)):
    """3x3 linear RGB transform: hue rotation + saturation scale in YIQ space, then brightness and channel gains."""
    to_yiq = np.array([[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]], np.float32)
    from_yiq = np.linalg.inv(to_yiq)
    c, s = np.cos(np.deg2rad(hue_deg)), np.sin(np.deg2rad(hue_deg))
    rot = np.array([[1, 0, 0], [0, c * sat, -s * sat], [0, s * sat, c * sat]], np.float32)
    M = from_yiq @ rot @ to_yiq
    return (np.diag(np.asarray(gains, np.float32)) * bright) @ M


def apply_matrix(img, M):
    return cv2.transform(img, M.astype(np.float32))


def luminance(img):
    return img @ LUMA


# ----------------------------------------------------------------------------------------------- post
def _uv_dist(H, W):
    u = (np.arange(W, dtype=np.float32) + 0.5) / W - 0.5
    v = (np.arange(H, dtype=np.float32) + 0.5) / H - 0.5
    return np.sqrt(u[None, :] ** 2 + v[:, None] ** 2)


_DIST_CACHE = {}


def uv_dist(H, W):
    if (H, W) not in _DIST_CACHE:
        _DIST_CACHE[(H, W)] = _uv_dist(H, W)
    return _DIST_CACHE[(H, W)]


def shift_channel(ch, dx):
    """Horizontal sub-pixel shift with wrap-around (moderngl textures repeat by default, as in v1's shader)."""
    M = np.float32([[1, 0, -dx], [0, 1, 0]])
    return cv2.warpAffine(ch, M, (ch.shape[1], ch.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def v1_shader(img, rng, noise_strength, aberration, vignette, contrast):
    """numpy re-implementation of shaders/post.frag: grain is added to rgb, then R and B are REPLACED by shifted
    texture samples (so the grain only survives in G), vignette, contrast, clamp."""
    H, W = img.shape[:2]
    out = np.empty_like(img)
    dx = aberration * W
    out[..., 0] = shift_channel(img[..., 0], dx)
    out[..., 1] = img[..., 1] + rng.random((H, W), dtype=np.float32) * noise_strength
    out[..., 2] = shift_channel(img[..., 2], -dx)
    out *= (1.0 - uv_dist(H, W) * vignette)[..., None]
    out = (out - 0.5) * contrast + 0.5
    return np.clip(out, 0.0, 1.0, out=out)


def photometric(img, rng, p):
    """v2 per-image camera model. p: dict of sampled parameters (see controlPanel PHOTOMETRIC_JITTER).
    Order: white balance + exposure, saturation, sensor noise, clip, gamma, contrast, chromatic aberration,
    vignette. Written with OpenCV primitives (numpy versions were ~4x slower at 1080p)."""
    H, W = img.shape[:2]
    e = p["exposure"]
    s = p["saturation"]
    # WB + exposure + saturation are all linear: one 3x3 colour matrix
    M = (1 - s) * np.outer(np.ones(3), LUMA) + s * np.eye(3)
    M = M @ np.diag([p["wb_r"] * e, e, p["wb_b"] * e])
    out = cv2.transform(img, M.astype(np.float32))
    if p["noise_sigma"] > 0:
        cv2.setRNGSeed(int(rng.integers(2 ** 31)))
        mono = np.empty((H, W), np.float32)
        cv2.randn(mono, 0.0, p["noise_sigma"] * (1 - p["noise_chroma"]))
        chroma = np.empty((H, W, 3), np.float32)
        cv2.randn(chroma, (0.0, 0.0, 0.0), (p["noise_sigma"] * p["noise_chroma"],) * 3)
        out += chroma
        out += mono[..., None]
    np.clip(out, 0.0, 1.0, out=out)
    out = cv2.pow(out, p["gamma"])
    m = float(out[::4, ::4].mean())
    out = cv2.addWeighted(out, p["contrast"], out, 0.0, m * (1 - p["contrast"]))
    if p["aberration"] > 0:
        dx = p["aberration"] * W
        out[..., 0] = shift_channel(np.ascontiguousarray(out[..., 0]), dx)
        out[..., 2] = shift_channel(np.ascontiguousarray(out[..., 2]), -dx)
    if p["vignette"] > 0:
        out *= (1.0 - uv_dist(H, W) * p["vignette"])[..., None]
    return np.clip(out, 0.0, 1.0, out=out)


def to_uint8_bgr(img):
    return cv2.cvtColor((img * 255.0 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR)
