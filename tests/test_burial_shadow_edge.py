"""Regression tests for burial round 4 (user review of the 48-card grid, docs/history/feedback/0100 / 0102).

(1) Shadow: a buried mine's cast shadow on the ground never reaches further than the same mine's shadow without
    burial (review b002: "it extends further than in the non-buried image"). Same seed / pose / sun with burial on
    and off, uniform grey ground, the turned-soil patch switched off (it darkens the ground on purpose); the darkened
    ground outside the unburied silhouette is projected on the shadow direction and its far end compared
    (tolerance 2 px). Covers low sun (18 deg), steep soil-plane tilt (25 deg) and a face-down mine.
(2) Wavy edge: with BURIAL_IRREGULAR_LINE the soil line (visible mine next to the buried / covered part) departs
    from the plain clip line of the same mine (> 0.9 px on average, >= 3% of the mine length somewhere on most
    mines), crosses it (covers AND uncovers) on most mines, and never strays more than 15% of the mine length (a gentle wave, not a different burial) (review notes
    0022 / 0024: "the burial edge should be wavey").
Run: python3 tests/test_burial_shadow_edge.py  (or pytest tests/).
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

GREY = 0.4
SHADOW_CASES = [(12, (3, -2, 30), 18.0, 15), (13, (3, -2, 30), 35.0, 25), (2, (3, -2, 300), 18.0, 25),
                (4, (2, -3, 60, True), 25.0, 15), (21, (-6, 10, 75), 50.0, 25), (5, (0, 0, 120), 20.0, 25)]


def _render(seed, pose, elevation, tilt, burial, extra=None):
    cfg = make_config(dict(n_mines=1, mine_scale=0.35, mine_pose=pose, burial_prob=burial, burial_fraction=0.45,
                           burial_tilt=tilt, sun_elevation=elevation, overcast_prob=0.0,
                           burial_disturbed_soil=False, **(extra or {})))
    sun = sunmod.sample_sun(np.random.default_rng([seed, 0, 0]), cfg)
    scene = {"sun": sun, "luma": GREY, "px_per_mm": 1.0, "blade_budget": [0]}
    m = Mine(cfg, [seed, 0, 10, 0], scene)
    m.set_position(1920, 1080, centre=(960, 540))
    img = np.full((1080, 1920, 3), GREY, np.float32)
    m.draw(img)
    full = np.zeros((1080, 1920), np.float32)
    h, w = m.alpha_full.shape
    full[m.y:m.y + h, m.x:m.x + w] = m.alpha_full
    return img, full, sun, m


def shadow_reach(seed, pose, elevation, tilt):
    """-> (reach without burial, reach with burial) in px along the shadow direction, measured from the unburied
    silhouette's centroid, over ground pixels darkened by >= 6% outside the (dilated) unburied silhouette."""
    out = []
    for b in (0.0, 1.0):
        img, full, sun, _ = _render(seed, pose, elevation, tilt, b)
        sil = cv2.dilate((full > 0.02).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        dark = (img.mean(2) < GREY * 0.94) & ~sil
        ys, xs = np.nonzero(full > 0.5)
        cx, cy = xs.mean(), ys.mean()
        az = np.deg2rad(sun["azimuth"])
        d = np.array([-np.cos(az), np.sin(az)])          # away from the sun, image coords (y down)
        yy, xx = np.nonzero(dark)
        out.append(float(((xx - cx) * d[0] + (yy - cy) * d[1]).max()) if len(xx) else 0.0)
    return out[0], out[1]


def test_buried_shadow_never_longer():
    for seed, pose, el, tilt in SHADOW_CASES:
        off, on = shadow_reach(seed, pose, el, tilt)
        assert on <= off + 2.0, f"seed {seed} el {el} tilt {tilt}: buried shadow reaches {on:.1f} px > unburied {off:.1f}"


WAVE_SEEDS = [12, 13, 1, 3, 2, 21, 8, 30]


def _soil_line(m):
    vis = (m.visible > 0.5).astype(np.uint8)
    gone = ((m.alpha_full > 0.5) & (m.visible < 0.5)).astype(np.uint8)
    return (vis > 0) & (cv2.dilate(gone, np.ones((3, 3), np.uint8)) > 0), vis


def wave_stats(seed):
    """Soil line with the wavy surface vs the plain clip line of the same mine (same clip plane, no wander):
    -> (mean / max distance of the wavy line from the plain one in px, px uncovered and px covered relative to the
    plain clip, mine length). A wave crosses the nominal line, so both uncovered and covered px must exist."""
    pose = (3, -2, 30 + 37 * seed)
    kw = dict(burial_clods=False, burial_berm=False)
    _, _, _, mw = _render(seed, pose, 40.0, 15, 1.0, dict(burial_irregular_line=True, **kw))
    _, _, _, mp = _render(seed, pose, 40.0, 15, 1.0, dict(burial_irregular_line=False, **kw))
    lw, vw = _soil_line(mw)
    lp, vp = _soil_line(mp)
    if not lw.any() or not lp.any():
        return None
    d = cv2.distanceTransform((~lp).astype(np.uint8), cv2.DIST_L2, 3)[lw]
    return float(d.mean()), float(d.max()), int(((vw > 0) & (vp == 0)).sum()), int(((vw == 0) & (vp > 0)).sum()), \
        mw.meta["length_px"]


def test_soil_line_is_wavy():
    stats = [st for st in (wave_stats(s) for s in WAVE_SEEDS) if st is not None]
    assert len(stats) >= 6
    for mean_d, max_d, up, down, L in stats:
        assert max_d < 0.15 * L, f"soil line strays {max_d:.1f} px from the clip line (> 15% of the mine length)"
    assert np.mean([st[0] for st in stats]) > 0.9, "soil line hardly deviates from the plain clip line"
    assert sum(1 for st in stats if st[1] >= 0.03 * st[4]) >= len(stats) // 2, \
        "on most mines the wave should move the line by >= 3% of the mine length somewhere"
    both = sum(1 for st in stats if st[2] > 10 and st[3] > 10)
    assert both >= len(stats) // 2, "the wave should cross the nominal line (cover AND uncover) on most mines"


if __name__ == "__main__":
    for seed, pose, el, tilt in SHADOW_CASES:
        off, on = shadow_reach(seed, pose, el, tilt)
        print(f"seed {seed} el {el} tilt {tilt}: shadow reach unburied {off:.1f} px, buried {on:.1f} px")
    test_buried_shadow_never_longer()
    for s in WAVE_SEEDS:
        print(f"seed {s}: wavy vs plain clip line (mean px, max px, uncovered px, covered px, L):", wave_stats(s))
    test_soil_line_is_wavy()
    print("PASS")
