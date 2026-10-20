"""Resampling of 2D cut-outs (rocks, grass, dirt snippets, v1 sprites): hard v1 style or soft v2 style."""
import cv2
import numpy as np

import fx


def resize_rotate(rgb, alpha, tw, th, angle=None, soft=True, feather=0.8):
    """Scale to (tw, th) then rotate by `angle` degrees counter-clockwise (canvas expanded like
    pygame.transform.rotate).

    soft=False (v1): nearest neighbour both times, binary alpha (jaggy edges).
    soft=True (v2):  premultiplied alpha (rgb * a, so transparent pixels never bleed colour into the edge),
                     area-average downscale, bilinear rotation, Gaussian alpha feather of `feather` px.
    -> (rgb_pm float32 (h, w, 3), alpha float32 (h, w)).
    """
    pm = np.dstack([rgb * alpha[..., None], alpha]).astype(np.float32)
    interp = (cv2.INTER_AREA if tw < rgb.shape[1] else cv2.INTER_LINEAR) if soft else cv2.INTER_NEAREST
    pm = cv2.resize(pm, (int(tw), int(th)), interpolation=interp)
    if angle is not None:
        a = np.deg2rad(angle)
        c, s = abs(np.cos(a)), abs(np.sin(a))
        nw, nh = int(np.ceil(tw * c + th * s)), int(np.ceil(tw * s + th * c))
        M = cv2.getRotationMatrix2D((tw / 2, th / 2), angle, 1.0)
        M[0, 2] += nw / 2 - tw / 2
        M[1, 2] += nh / 2 - th / 2
        pm = cv2.warpAffine(pm, M, (nw, nh), flags=cv2.INTER_LINEAR if soft else cv2.INTER_NEAREST, borderValue=0)
    if not soft:
        a = (pm[..., 3] > 0.5).astype(np.float32)
        rgb_out = np.where(pm[..., 3:] > 1e-6, pm[..., :3] / np.maximum(pm[..., 3:], 1e-6), 0) * a[..., None]
        return rgb_out.astype(np.float32), a
    if feather > 0:  # blurring premultiplied RGBA is exact: the colour of the feathered rim stays the object colour
        pm = fx.gblur(np.pad(pm, ((2, 2), (2, 2), (0, 0))), feather)
    return np.ascontiguousarray(pm[..., :3]), np.ascontiguousarray(pm[..., 3])


def rim_blend(rgb_pm, alpha, ground_rgb, sun_az, tint, rim_darken, band_px=1.5):
    """Seat a cut-out on the ground: within ~band_px of its edge, mix the colour towards the local ground colour by
    `tint`, and darken the rim on the side facing away from the sun by `rim_darken` (thin self-shadow line).
    Works on premultiplied colour. -> rgb_pm'."""
    a = alpha.astype(np.float32)
    inner = fx.gblur(cv2.erode(a, np.ones((3, 3), np.uint8), iterations=max(1, int(round(band_px)))), 0.8)
    band = np.clip(a - inner, 0, 1)                                   # 1 at the rim, 0 inside / outside
    gx = cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3)
    n = np.sqrt(gx * gx + gy * gy) + 1e-6
    # outward normal = -grad(alpha); sun direction in image coords (y down) = (cos az, -sin az)
    away = np.clip(((-gx / n) * -np.cos(np.deg2rad(sun_az)) + (-gy / n) * np.sin(np.deg2rad(sun_az))), 0, 1)
    away = fx.gblur(away * (n > 0.05), 0.8)
    out = rgb_pm * (1 - tint * band)[..., None] + np.asarray(ground_rgb, np.float32)[None, None] * (tint * band)[..., None] * a[..., None]
    out *= (1 - rim_darken * band * away)[..., None]
    return out.astype(np.float32)
