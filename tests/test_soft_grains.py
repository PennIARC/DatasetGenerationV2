"""MINE_SOFT_GRAINS (second, blurred grain layer) regression test.

(1) Own random stream: switching the flag on changes nothing but the mine's pixels: labels, every other sidecar value
    and pixels away from the mine are identical (up to 1-level rounding of the image-wide camera steps), so existing
    seeds / the dataset plan do not shift.
(2) The layer is soft: the change it makes inside the mine has far less pixel-scale (Laplacian) energy per unit of
    change than the existing crisp SOIL_BLEND grains.
(3) Sidecar: mine["soft_grains"] holds the sampled parameters; SOFT_GRAIN_PROB = 0 leaves the image unchanged.
Run: python3 tests/test_soft_grains.py  (or pytest tests/).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from scene import render_scene  # noqa: E402

BASE = dict(n_mines=2, psf_sigma=0.0, motion_blur_prob=0, dust_strength=0.25)
SEEDS = [1, 3, 12]


def _render(seed, **ov):
    rgb, labels, meta = render_scene(seed, {**BASE, **ov})
    return rgb.astype(np.float32), labels, meta


def _strip(meta):
    return [{k: v for k, v in m.items() if k != "soft_grains"} for m in meta["mines"]]


def _near_mines(meta, shape, pad=8):
    m = np.zeros(shape[:2], bool)
    for mm in meta["mines"]:
        if "box" not in mm:
            continue
        xc, yc, w, h = mm["box"]
        H, W = shape[:2]
        x0, x1 = int((xc - w / 2) * W) - pad, int((xc + w / 2) * W) + pad
        y0, y1 = int((yc - h / 2) * H) - pad, int((yc + h / 2) * H) + pad
        m[max(0, y0):y1, max(0, x0):x1] = True
    return m


def _hf_ratio(d):
    """Laplacian energy / plain energy of a difference image (high for crisp dots, low for smooth blotches)."""
    g = d.mean(2)
    lap = cv2.Laplacian(g, cv2.CV_32F)
    return float((lap ** 2).sum() / max((g ** 2).sum(), 1e-9))


def check(seed):
    off, l_off, m_off = _render(seed, mine_soft_grains=False, grain_density=0.0)
    on, l_on, m_on = _render(seed, mine_soft_grains=True, soft_grain_prob=1.0, grain_density=0.0)
    grains, _, _ = _render(seed, mine_soft_grains=False, grain_density=0.05)
    assert l_off == l_on, f"seed {seed}: labels changed"
    assert _strip(m_off) == _strip(m_on), f"seed {seed}: other mine sidecar values changed"
    assert m_off["sun"] == m_on["sun"] and m_off["post"] == m_on["post"], f"seed {seed}: image-level draws changed"
    near = _near_mines(m_on, on.shape)
    # away from the mines only 8-bit rounding of the image-wide camera steps may differ (<= 1 level, rare)
    far = np.abs(on - off)[~near]
    assert far.max() <= 1.0 and (far > 0).mean() < 0.01, f"seed {seed}: pixels away from the mines changed"
    d_soft = on - off
    assert np.abs(d_soft).max() > 0.02, f"seed {seed}: soft grains invisible"
    assert all("soft_grains" in m for m in m_on["mines"])
    r_soft, r_grain = _hf_ratio(d_soft), _hf_ratio(grains - off)
    assert r_soft < 0.5 * r_grain, f"seed {seed}: soft grains not smoother than grains ({r_soft:.3f} vs {r_grain:.3f})"
    none, _, _ = _render(seed, mine_soft_grains=True, soft_grain_prob=0.0, grain_density=0.0)
    assert np.array_equal(none, off), f"seed {seed}: SOFT_GRAIN_PROB = 0 changed the image"
    return r_soft, r_grain


def test_soft_grains():
    for s in SEEDS:
        check(s)


if __name__ == "__main__":
    for s in SEEDS:
        r_soft, r_grain = check(s)
        print(f"seed {s}: high-frequency ratio soft {r_soft:.3f} vs crisp grains {r_grain:.3f} -> OK")
    print("PASS")
