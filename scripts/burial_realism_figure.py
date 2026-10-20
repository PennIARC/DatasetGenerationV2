"""docs/burial_realism.png: partial burial before / after the soil-displacement cues.

Rows: gravel, dark grass, light (dry) grass, bare soil, face-down mine, low sun (18 deg), high sun (65 deg).
Columns: burial off | OLD 40% (all new burial cues and the fragment clean-up switched off) | NEW 40% |
NEW 40% with BLADES_OVER_ON_MINE = 1 (blades lifted where they cross the soil line). Same seed per row; 4x zoom.

    python3 scripts/burial_realism_figure.py [--zoom 4] [--out docs/burial_realism.png]
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
            overcast_prob=0.0, blades_over_on_mine=0.0)
BUR = dict(burial_prob=1.0, burial_fraction=0.4, burial_tilt=15)
OLD = dict(burial_berm=False, burial_disturbed_soil=False, burial_clods=False, burial_dirty_exposed=False,
           blade_soil_lift=False, blade_emerge=False, burial_min_fragment_frac=0.0, burial_open_px=0,
           burial_open_frac=0.0, burial_clip_share=1.0, burial_irregular_line=False)
CASES = [("gravel", 1, dict(mine_pose=(3, -2, 30))),
         ("dark grass", 12, dict(mine_pose=(3, -2, 30))),
         ("light dry grass", 8, dict(mine_pose=(4, 3, 120))),
         ("bare soil", 3, dict(mine_pose=(-2, 5, 200))),
         ("face down", 4, dict(mine_pose=(2, -3, 60, True))),
         ("low sun 18 deg", 2, dict(mine_pose=(3, -2, 300), sun_elevation=18)),
         ("high sun 65 deg", 2, dict(mine_pose=(3, -2, 300), sun_elevation=65))]
COLS = [("burial off", dict(burial_prob=0.0)), ("OLD 40%", {**BUR, **OLD}), ("NEW 40%", BUR),
        ("NEW 40% + blades on mine", {**BUR, "blades_over_on_mine": 1.0})]


def tile(rgb, zoom, cw=170, ch=100):
    c = rgb[540 - ch // 2:540 + ch // 2, 960 - cw // 2:960 + cw // 2]
    return cv2.resize(c, (cw * zoom, ch * zoom), interpolation=cv2.INTER_NEAREST)


def caption(img, text):
    out = img.copy()
    cv2.rectangle(out, (0, 0), (len(text) * 13 + 12, 30), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs/burial_realism.png"))
    ap.add_argument("--rows", default=None, help="comma list of row indices (debugging)")
    a = ap.parse_args()
    rows = []
    sel = [int(i) for i in a.rows.split(",")] if a.rows else range(len(CASES))
    for i in sel:
        name, seed, ov = CASES[i]
        tiles = []
        for cname, cov in COLS:
            rgb, _, meta = render_scene(seed, {**BASE, **ov, **cov})
            rgb = jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"])
            t = tile(rgb, a.zoom)
            if cname.startswith("NEW") and meta["mines"][0]["burial"].get("achieved") is not None:
                cname = f"{cname} (hidden {meta['mines'][0]['burial']['achieved']:.2f})"
            tiles.append(caption(t, f"{name}: {cname}" if not tiles else cname))
        rows.append(np.hstack([np.pad(t, ((3, 3), (3, 3), (0, 0)), constant_values=255) for t in tiles]))
    cv2.imwrite(a.out, cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
