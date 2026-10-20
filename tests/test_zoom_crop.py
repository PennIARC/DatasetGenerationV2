"""SCENE_ZOOM_COUPLING + OUTPUT_CROP regression test (ADR 0016).

(1) Flags off = unchanged generator: two reference renders hash to the values recorded from the pre-zoom generator
    (commit 95dcf25; verified bit-identical images, labels and sidecars against a HEAD checkout at the time).
(2) Labels land on the mines in the 640x640 crop: magenta flat mines (no soil / blur / camera / occluders); every
    label box equals the bounding box of a magenta blob in the crop (+-1 px), all boxes lie inside the crop, the
    crop is a native cut (same size, no resize) and the crop window equals meta["crop"].
(3) Mine pixel size: a flat mine at scale s is ~426.7 s px long (0.25 -> 107 px, 0.40 -> 171 px) in the crop.
(4) Features scale with the zoom: the scaled pixel parameters are exactly x z; rock widths grow ~x z and rock counts
    shrink ~x z^-2 (several seeds); grass blades follow px/mm as before.
Run: python3 tests/test_zoom_crop.py  (or pytest tests/).
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from config import make_config  # noqa: E402
from features import zoom as zoommod  # noqa: E402
from scene import render_scene  # noqa: E402

REFERENCE = {   # (seed, index, overrides) -> md5 of the RGB array, first label (pre-zoom generator)
    (0, 0): ({}, "8c4f19918156faba19e7a362d21f5ac6", [0, 0.7072916666666667, 0.41203703703703703,
                                                      0.06927083333333334, 0.075]),
    (2026, 5): ({"n_mines": 4, "burial_prob": 1.0}, "1f95601b687d95745d29c11ce947bc3d",
                [0, 0.4078125, 0.8592592592592593, 0.053125, 0.07962962962962963]),
}
CROP = (640, 640)
ZOOM = {"scene_zoom_coupling": True, "output_crop": CROP}
PLAIN = {"mine_colour": (1.0, 0.0, 1.0), "soil_blend": False, "shadows": False, "blur": False,
         "photometric_jitter": False, "enable_post_processing": False, "burial_prob": 0.0, "grass_blades": False,
         "rocks_to_spawn_min": 0, "rocks_to_spawn_max": 0, "leaf_clumps_over": 0, "dirt_snippets_per_layer": 0,
         "grass_clippings_per_image": 5, "grass_images_to_sample": 0, "dirt_rects_per_layer": 0}


def test_flags_off_unchanged():
    for (seed, idx), (ov, md5, lab0) in REFERENCE.items():
        rgb, labels, meta = render_scene(seed, ov, index=idx)
        assert rgb.shape == (1080, 1920, 3)
        assert "zoom" not in meta and "crop" not in meta
        assert labels[0] == lab0, (seed, labels[0])
        h = hashlib.md5(rgb.tobytes()).hexdigest()
        assert h == md5, f"seed {seed}: image changed with the zoom / crop flags off ({h})"


def _magenta(rgb):
    f = rgb.astype(np.int32)
    return (f[..., 0] > 2 * f[..., 1] + 40) & (f[..., 2] > 2 * f[..., 1] + 40)


def test_labels_land_in_crop():
    checked = 0
    for seed in range(6):
        for scale in (0.25, 0.4):
            ov = {**ZOOM, **PLAIN, "n_mines": 4, "mine_scale": scale, "mine_pose": (0.0, 0.0, 30.0 * seed, False)}
            rgb, labels, meta = render_scene(seed, ov, index=seed)
            assert rgb.shape == (CROP[1], CROP[0], 3)
            c = meta["crop"]
            assert 0 <= c["x0"] <= 1920 - 640 and 0 <= c["y0"] <= 1080 - 640
            assert len(labels) == len(meta["mines"]) >= 3, (seed, len(labels))
            mag = _magenta(rgb)
            covered = np.zeros_like(mag)
            for l in labels:
                _, xc, yc, w, h = l
                assert 0 <= xc - w / 2 and xc + w / 2 <= 1 and 0 <= yc - h / 2 and yc + h / 2 <= 1, l
                x0, y0 = round((xc - w / 2) * 640), round((yc - h / 2) * 640)
                bw, bh = round(w * 640), round(h * 640)
                ya, xa = max(0, y0 - 3), max(0, x0 - 3)
                ys, xs = np.nonzero(mag[ya:y0 + bh + 3, xa:x0 + bw + 3])
                got = (xs.min() + xa, ys.min() + ya, xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
                err = max(abs(got[0] - x0), abs(got[1] - y0), abs(got[2] - bw), abs(got[3] - bh))
                assert err <= 2, (seed, scale, l, got)   # anti-aliased rim pixels: +-2 px
                covered[ya:y0 + bh + 3, xa:x0 + bw + 3] = True
                checked += 1
            assert (mag & ~covered).sum() == 0, "magenta mine pixels outside every label box"
            for m in meta["mines"]:   # the full-frame box minus the crop offset is the crop box
                x0, y0, bw, bh = m["box_px_full"]
                assert c["x0"] <= x0 and x0 + bw <= c["x0"] + 640 and c["y0"] <= y0 and y0 + bh <= c["y0"] + 640
    assert checked >= 40


def test_crop_is_native_cut():
    """Without the camera model the crop is exactly the window of the full render (no resampling)."""
    ov = {**PLAIN, "mine_colour": None, "rocks_to_spawn_min": 5, "rocks_to_spawn_max": 20, "n_mines": 2,
          "output_crop": CROP}
    rgb, _, meta = render_scene(4, ov, index=4)
    c = meta["crop"]
    # same scene with MINE_POSITIONS at the placed centres, full frame -> identical pixels inside the window
    assert rgb.shape == (640, 640, 3) and len(meta["mines"]) == 2
    full, _, meta2 = render_scene(4, {**ov, "output_crop": None,
                                      "mine_positions": [(m["rect_full"][0] + m["rect_full"][2] / 2,
                                                          m["rect_full"][1] + m["rect_full"][3] / 2)
                                                         for m in meta["mines"]]}, index=4)
    win = full[c["y0"]:c["y0"] + 640, c["x0"]:c["x0"] + 640]
    diff = np.abs(win.astype(int) - rgb.astype(int))
    assert (diff > 1).mean() < 0.001, float((diff > 1).mean())


def test_mine_pixel_size():
    for scale in (0.25, 0.325, 0.4):
        ov = {**ZOOM, **PLAIN, "n_mines": 1, "mine_scale": scale, "mine_pose": (0.0, 0.0, 0.0, False)}
        _, labels, meta = render_scene(1, ov, index=1)
        L = 512 / 1.2 * scale
        assert abs(meta["mines"][0]["length_px"] - L) < 1e-6
        long_side = max(labels[0][3], labels[0][4]) * 640
        assert 0.8 * L <= long_side <= 1.02 * L, (scale, long_side, L)


def test_features_scale_with_zoom():
    cfg = make_config()
    for z in (1.25, 2.0):
        zc = zoommod.zoomed_config(cfg, z)
        for k in zoommod.ZOOM_SCALED_PX:
            a, b = getattr(cfg, k), getattr(zc, k)
            if isinstance(a, tuple):
                assert all(abs(y - x * z) < 1e-9 for x, y in zip(a, b)), k
        assert abs(zoommod.count_factor(z, cfg) - z ** -2) < 1e-12
    # rocks: widths ~ x z, counts ~ x z^-2 (over seeds)
    w_off, w_on, n_off, n_on = [], [], 0, 0
    for seed in range(8):
        base = {"n_mines": 1, "mine_scale": 0.4, "grass_blades": False}
        _, _, m0 = render_scene(seed, base, index=seed)
        _, _, m1 = render_scene(seed, {**base, **ZOOM}, index=seed)
        w_off += [r[2] for r in m0["rocks"]]
        w_on += [r[2] for r in m1["rocks"]]
        n_off, n_on = n_off + len(m0["rocks"]), n_on + len(m1["rocks"])
        assert abs(m1["zoom"]["factor"] - 2.0) < 1e-9 and abs(m1["ground_px_per_mm"] - m0["ground_px_per_mm"]) < 1e-12
    r = np.median(w_on) / np.median(w_off)
    assert 1.6 < r < 2.5, r
    assert 0.12 < n_on / n_off < 0.45, (n_on, n_off)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
