"""Regression test: burial must not move the mine and must only remove pixels.

For several seeds / poses, the same mine is built with burial off and with 40% burial (same random streams).
Checks: (1) the placement anchor (bbox of the unclipped silhouette) is identical -> 0 px offset;
(2) every visible pixel of the buried mine lies inside the unburied mine's silhouette (1 px tolerance for
anti-aliasing); (3) the visible area actually shrinks; (4) the full scene: the label box of the buried mine lies
inside the unburied box; (5) the final visible mask of buried mines (9 seeds / poses incl. face down) has no tiny
islands and no 1-2 px-wide line structures. Run: python3 tests/test_burial.py  (or pytest tests/).
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
    m.draw(np.full((H, W, 3), 0.4, np.float32))     # final visible mask (clip + wavy soil cover + clean-up)
    canvas[m.y:m.y + h, m.x:m.x + w] = m.visible
    full = np.zeros((H, W), np.float32)
    full[m.y:m.y + h, m.x:m.x + w] = m.alpha_full
    return canvas, full, (m.x + m.bx0, m.y + m.by0)


def check(seed, pose):
    ov = dict(n_mines=1, mine_scale=0.35, mine_pose=pose, burial_fraction=0.4, burial_tilt=15)
    out = {}
    for b in (0.0, 1.0):
        cfg = make_config({**ov, "burial_prob": b})
        scene = {"sun": sunmod.sample_sun(np.random.default_rng([seed, 0, 0]), cfg), "luma": 0.4, "px_per_mm": 1.0,
                 "blade_budget": [0]}
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


FRAG_CASES = [(12, (3, -2, 30)), (13, (3, -2, 30)), (1, (3, -2, 30)), (3, (-2, 5, 200)), (4, (2, -3, 60, True)),
              (2, (3, -2, 300)), (7, (8, -4, 250, True)), (21, (-6, 10, 75)), (8, (4, 3, 120))]


def check_fragments(seed, pose, fraction=0.4):
    """Final visible mask of a buried mine (after soil line, fragment clean-up, ridge, clods): no connected component
    smaller than BURIAL_MIN_FRAGMENT_FRAC x full area, and no 1-2 px-wide line structures (a 3x3 opening keeps at
    least 70% of every component; overall it removes < 6% of the visible pixels)."""
    cfg = make_config(dict(n_mines=1, mine_scale=0.35, mine_pose=pose, burial_prob=1.0, burial_fraction=fraction,
                           burial_tilt=15))
    rng = np.random.default_rng([seed, 0, 0])
    sun = sunmod.sample_sun(rng, cfg)
    scene = {"sun": sun, "luma": 0.4, "px_per_mm": 1.0, "blade_budget": [0]}
    m = Mine(cfg, [seed, 0, 10, 0], scene)
    m.set_position(1920, 1080, centre=(960, 540))
    img = np.full((1080, 1920, 3), 0.4, np.float32)
    m.draw(img)
    vis = (m.visible > 0.5).astype(np.uint8)
    full = float((m.alpha_full > 0.5).sum())
    n, lab, st, _ = cv2.connectedComponentsWithStats(vis, connectivity=8)
    opened = cv2.morphologyEx(vis, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    for i in range(1, n):
        area = st[i, cv2.CC_STAT_AREA]
        assert area >= cfg.BURIAL_MIN_FRAGMENT_FRAC * full * 0.5, \
            f"seed {seed}: visible fragment of {area} px (< min {cfg.BURIAL_MIN_FRAGMENT_FRAC * full:.0f})"
        kept = (opened[lab == i] > 0).mean()
        assert kept >= 0.7, f"seed {seed}: component {i} is line-like ({kept:.2f} survives a 3x3 opening)"
    lost = 1 - opened.sum() / max(vis.sum(), 1)
    assert lost < 0.06, f"seed {seed}: {lost:.3f} of the visible pixels are 1-2 px structures"
    return n - 1, float(m.meta["burial"]["achieved"]), float(lost)


def test_buried_visible_mask_has_no_slivers():
    for seed, pose in FRAG_CASES:
        check_fragments(seed, pose)


def test_burial_keeps_position_and_silhouette():
    for seed, pose in CASES:
        check(seed, pose)


if __name__ == "__main__":
    for seed, pose in CASES:
        anchor, a_on, a_off = check(seed, pose)
        print(f"seed {seed} pose {pose}: anchor {anchor} identical, visible {a_on}/{a_off} px, all inside -> OK")
    for seed, pose in FRAG_CASES:
        n, ach, lost = check_fragments(seed, pose)
        print(f"seed {seed} pose {pose}: {n} visible component(s), hidden {ach:.2f}, 1-2 px structures {lost:.3f} -> OK")
    print("PASS")
