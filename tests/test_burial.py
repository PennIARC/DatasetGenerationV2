"""Regression test: burial must not move the mine and must only remove pixels.

For several seeds / poses, the same mine is built with burial off and with 40% burial (same random streams).
Checks: (1) the placement anchor (bbox of the unclipped silhouette) is identical -> 0 px offset;
(2) every visible pixel of the buried mine lies inside the unburied mine's silhouette (1 px tolerance for
anti-aliasing); (3) the visible area actually shrinks; (4) the full scene: the label box of the buried mine lies
inside the unburied box. Run: python3 tests/test_burial.py  (or pytest tests/).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from config import make_config  # noqa: E402
from features import sun as sunmod  # noqa: E402
from objects import Mine  # noqa: E402
from scene import render_scene  # noqa: E402

CASES = [(12, (3, -2, 30)), (13, (3, -2, 30)), (5, (0, 0, 120)), (7, (8, -4, 250, True)), (21, (-6, 10, 75))]


def _place(m, W=1920, H=1080):
    m.set_position(W, H, centre=(960, 540))
    canvas = np.zeros((H, W), np.float32)
    h, w = m.alpha.shape
    canvas[m.y:m.y + h, m.x:m.x + w] = m.alpha
    full = np.zeros((H, W), np.float32)
    full[m.y:m.y + h, m.x:m.x + w] = m.alpha_full
    return canvas, full, (m.x + m.bx0, m.y + m.by0)


def check(seed, pose):
    ov = dict(n_mines=1, mine_scale=0.35, mine_pose=pose, burial_fraction=0.4, burial_tilt=15)
    out = {}
    for b in (0.0, 1.0):
        cfg = make_config({**ov, "burial_prob": b})
        scene = {"sun": sunmod.sample_sun(np.random.default_rng([seed, 0, 0]), cfg), "luma": 0.4}
        m = Mine(cfg, [seed, 0, 10, 0], scene)
        out[b] = _place(m)
    vis_off, _, anchor_off = out[0.0]
    vis_on, full_on, anchor_on = out[1.0]
    assert anchor_off == anchor_on, f"seed {seed}: anchor moved {anchor_off} -> {anchor_on}"
    sil = cv2.dilate((vis_off > 0.5).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    outside = (vis_on > 0.5) & ~sil
    assert outside.sum() == 0, f"seed {seed}: {outside.sum()} buried-mine pixels outside the unburied silhouette"
    assert (vis_on > 0.5).sum() < 0.9 * (vis_off > 0.5).sum(), f"seed {seed}: burial removed nothing"
    # full scene: label box of the buried mine inside the unburied one
    labs = {}
    for b in (0.0, 1.0):
        _, l, _ = render_scene(seed, {**ov, "burial_prob": b, "mine_positions": [(960, 540)]})
        labs[b] = l[0]
    def box(l):
        return (l[1] - l[3] / 2) * 1920, (l[2] - l[4] / 2) * 1080, (l[1] + l[3] / 2) * 1920, (l[2] + l[4] / 2) * 1080
    a, c = box(labs[0.0]), box(labs[1.0])
    assert c[0] >= a[0] - 1.5 and c[1] >= a[1] - 1.5 and c[2] <= a[2] + 1.5 and c[3] <= a[3] + 1.5, \
        f"seed {seed}: buried box {c} not inside unburied box {a}"
    return anchor_off, int((vis_on > 0.5).sum()), int((vis_off > 0.5).sum())


def test_burial_keeps_position_and_silhouette():
    for seed, pose in CASES:
        check(seed, pose)


if __name__ == "__main__":
    for seed, pose in CASES:
        anchor, a_on, a_off = check(seed, pose)
        print(f"seed {seed} pose {pose}: anchor {anchor} identical, visible {a_on}/{a_off} px, all inside -> OK")
    print("PASS")
