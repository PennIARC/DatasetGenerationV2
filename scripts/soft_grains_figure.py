"""docs/soft_grains.png: the MINE_SOFT_GRAINS layer (blurred soil speckle) next to the existing soil grains.

Rows: different backgrounds / mine colours (one mine each, same seed per row, sun / pose fixed per row).
Columns: off (no grains: grain_density 0, soft grains off) | existing grains only (SOIL_BLEND grains at 4%) |
existing + soft grains (MINE_SOFT_GRAINS forced on for the mine, its sampled parameters in the caption).
Dust is kept at its low end (0.25) so the grains are visible. 4x zoom of a 170 x 100 px window.

    python3 scripts/soft_grains_figure.py [--zoom 4] [--out docs/soft_grains.png]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

from features.camera import jpeg_roundtrip  # noqa: E402
from scene import render_scene  # noqa: E402

BASE = dict(n_mines=1, mine_positions=[(960, 540)], mine_scale=0.35, psf_sigma=0.3, motion_blur_prob=0,
            overcast_prob=0.0, blades_over_on_mine=0.0, burial_prob=0.0, dust_strength=0.25)
CASES = [("gravel", 1, dict(mine_pose=(3, -2, 30))),
         ("dark grass", 12, dict(mine_pose=(3, -2, 30))),
         ("light dry grass", 8, dict(mine_pose=(4, 3, 120))),
         ("bare soil", 3, dict(mine_pose=(-2, 5, 200))),
         ("face down", 4, dict(mine_pose=(2, -3, 60, True))),
         ("buried 40%", 2, dict(mine_pose=(3, -2, 300), burial_prob=1.0, burial_fraction=0.4))]
COLS = [("off", dict(grain_density=0.0, mine_soft_grains=False)),
        ("existing grains only", dict(grain_density=0.04, mine_soft_grains=False)),
        ("+ soft grains (new)", dict(grain_density=0.04, mine_soft_grains=True, soft_grain_prob=1.0))]


def tile(rgb, zoom, cw=170, ch=100):
    c = rgb[540 - ch // 2:540 + ch // 2, 960 - cw // 2:960 + cw // 2]
    return cv2.resize(c, (cw * zoom, ch * zoom), interpolation=cv2.INTER_NEAREST)


def caption(img, text, y=0):
    out = img.copy()
    cv2.rectangle(out, (0, y), (len(text) * 11 + 12, y + 26), (0, 0, 0), -1)
    cv2.putText(out, text, (6, y + 19), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs/soft_grains.png"))
    a = ap.parse_args()
    rows = []
    for name, seed, ov in CASES:
        tiles = []
        for cname, cov in COLS:
            rgb, _, meta = render_scene(seed, {**BASE, **ov, **cov})
            rgb = jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"])
            t = caption(tile(rgb, a.zoom), f"{name}: {cname}" if not tiles else cname)
            g = meta["mines"][0].get("soft_grains")
            if cov.get("mine_soft_grains") and g:
                t = caption(t, f"density {g['density']:.2f}  size {g['size_frac']:.3f}L  blur {g['blur_px']:.1f}px  "
                               f"strength {g['strength']:.2f}  tone {g['tone']:.2f}", t.shape[0] - 26)
            tiles.append(t)
        rows.append(np.hstack([np.pad(t, ((3, 3), (3, 3), (0, 0)), constant_values=255) for t in tiles]))
    cv2.imwrite(a.out, cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
