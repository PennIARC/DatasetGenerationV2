"""Full-scene entry point (no global state, no disk writes, no window):

    from scene import render_scene
    rgb, labels, meta = render_scene(seed=3, overrides={"shadows": False, "sun_elevation": 20, "n_mines": 1})

rgb: uint8 (1080, 1920, 3) RGB before JPEG compression (features.camera.jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"])
gives what the saved file looks like); labels: [[0, xc, yc, w, h], ...] normalised YOLO; meta: the sidecar dict.

Random streams: every subsystem draws from its own generator seeded by (seed, index, k), so toggling one flag
(e.g. SHADOWS) leaves background, debris, mine poses / colours / positions and camera noise unchanged ->
before / after pairs on the same seed differ only by that feature.
"""
import numpy as np

import fx
from config import make_config
from features import background, camera, sun as sunmod
from objects import EnvironmentDebris, Mine


def render_scene(seed=0, overrides=None, index=0, cfg=None):
    cfg = cfg if cfg is not None else make_config(overrides)
    W, H = cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT
    R = lambda *k: np.random.default_rng([int(seed), int(index), *k])  # noqa: E731
    sun = sunmod.sample_sun(R(0), cfg)
    rs = R(9)
    px_per_mm = float(cfg.MINE_PX_PER_UNIT * rs.uniform(cfg.MINE_SCALE_MIN, cfg.MINE_SCALE_MAX) / cfg.MINE_LENGTH_MM)
    scene = {"sun": sun, "px_per_mm": px_per_mm, "blade_budget": [int(cfg.BLADE_MAX_FRESH_PER_IMAGE)]}
    meta = {"index": int(index), "seed": [int(seed), int(index)],
            "flags": {f: bool(getattr(cfg, f)) for f in cfg.V2_FLAGS}, "sun": sun,
            "overrides": {k: (list(v) if isinstance(v, tuple) else v) for k, v in (overrides or {}).items()}}

    # 1. background, 2. undergrowth
    bgp = background.sample_background_params(R(1), cfg)
    img = background.make_background(bgp, W, H, smooth=cfg.SOFT_EDGES or cfg.BG_AUGMENT)
    meta["background"] = background.describe(bgp)
    EnvironmentDebris(cfg, R(2), scene, R(3)).draw(img)
    scene["luma"] = float(fx.luminance(img[::8, ::8]).mean())

    # 3. mines: v1 placement (rejection sampling against already placed boxes) unless MINE_POSITIONS is given
    rm = R(4)
    u, n = rm.random(), int(rm.integers(cfg.MIN_MINES, cfg.MAX_MINES + 1))
    num = cfg.N_MINES if cfg.N_MINES is not None else (0 if u < cfg.ZERO_MINE_PROB else n)
    mines = []
    for j in range(num):
        m = Mine(cfg, [int(seed), int(index), 10, j], scene)
        if cfg.MINE_POSITIONS is not None and j < len(cfg.MINE_POSITIONS):
            m.set_position(W, H, centre=cfg.MINE_POSITIONS[j])
            m.draw(img)
            mines.append(m)
            continue
        for _ in range(cfg.MINE_PLACEMENT_ATTEMPTS):
            m.set_position(W, H)
            if not any(m.collides(o, cfg.MINE_PLACEMENT_MARGIN) for o in mines):
                m.draw(img)
                mines.append(m)
                break

    scene["mine_rects"] = [(j, m.rect) for j, m in enumerate(mines)]
    # 4. overgrowth (occludes mines; alpha accumulated for visible-mask labels)
    occlusion = np.zeros((H, W), np.float32) if cfg.LABEL_VISIBLE_MASK else None
    EnvironmentDebris(cfg, R(5), scene, R(6), layer="over").draw(img, occlusion)

    labels, mine_meta = [], []
    for j, m in enumerate(mines):
        m.meta["blades_on_mine"] = int(scene.get("blades_on_mine", {}).get(j, 0))
        lbl = m.label(W, H, occlusion)
        m.meta["labelled"] = lbl is not None
        m.meta["placed_at"] = [int(m.x), int(m.y)]
        if lbl is not None:
            labels.append(lbl)
            m.meta["box"] = lbl[1:]
        mine_meta.append(m.meta)
    meta["mines"] = mine_meta
    meta["ground_px_per_mm"] = px_per_mm
    meta["debris_counts"] = scene.get("debris_counts", {})   # per layer and kind (rock, leaf, blade, dirt_clod, ...)
    meta["rocks"] = scene.get("rocks", [])   # [cx, cy, width, layer] of every rock (for crops / checks)

    # 5. camera
    cam = camera.sample_camera_params(R(7), cfg)
    img = camera.apply_camera(img, cam)
    meta["post"] = cam
    rgb = (img * 255.0 + 0.5).astype(np.uint8)
    return rgb, labels, meta
