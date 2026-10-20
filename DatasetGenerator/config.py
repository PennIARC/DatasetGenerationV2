"""Config objects: an immutable-by-convention copy of controlPanel.py with per-call overrides.

    cfg = make_config({"shadows": False, "sun_elevation": 20, "burial_prob": 1.0, "n_mines": 1})

Override keys are controlPanel names, case-insensitive. A scalar given for a (min, max) range fixes it
((v, v)). Extra keys: "v1": True switches every v2 flag off; "only": ["SHADOWS", ...] switches only those
flags on; "mine_scale": s fixes MINE_SCALE_MIN = MINE_SCALE_MAX = s; "flip": True / False forces every mine
face down / face up (same as FLIP_PROB = 1.0 / 0.0). controlPanel itself is never modified.
"""
import copy
import os
from types import SimpleNamespace

import controlPanel

ROOT = os.path.dirname(os.path.abspath(__file__))


def make_config(overrides=None):
    cfg = SimpleNamespace(**{k: copy.deepcopy(v) for k, v in vars(controlPanel).items() if k.isupper()})
    cfg.ROOT = ROOT
    ov = dict(overrides or {})
    # flag presets first, so explicit flags in the same dict win
    if ov.pop("v1", False):
        for f in cfg.V2_FLAGS:
            setattr(cfg, f, False)
    only = ov.pop("only", None)
    if only is not None:
        if isinstance(only, str):
            only = [s for s in only.split(",") if s.strip()]
        on = {s.strip().upper() for s in only}
        bad = on - set(cfg.V2_FLAGS)
        if bad:
            raise KeyError(f"unknown flags {sorted(bad)}; choose from {cfg.V2_FLAGS}")
        for f in cfg.V2_FLAGS:
            setattr(cfg, f, f in on)
    for k, v in ov.items():
        set_option(cfg, k, v)
    return cfg


def set_option(cfg, key, value):
    K = key.upper()
    if K == "FLIP":  # True -> every mine face down, False -> none
        cfg.FLIP_PROB = 1.0 if value else 0.0
        return
    if K == "MINE_SCALE":
        cfg.MINE_SCALE_MIN = cfg.MINE_SCALE_MAX = float(value)
        return
    if not hasattr(cfg, K):
        raise KeyError(f"unknown controlPanel setting: {key}")
    cur = getattr(cfg, K)
    if isinstance(cur, tuple) and len(cur) in (2, 3) and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = (value,) * len(cur)   # a scalar fixes a (min, max) range or a (low, mode, high) triangle
    setattr(cfg, K, value)


def asset_path(cfg, rel):
    return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(cfg.ROOT, rel))
