"""Asset audit filter: no hard-excluded file is ever sampled in v2 mode (500 seeds per asset kind, plus the
backgrounds exactly as render_scene draws them); v1 mode still uses the full v1 asset set.
Run: python3 tests/test_asset_audit.py  (or pytest tests/)."""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))

import numpy as np  # noqa: E402

from config import make_config  # noqa: E402
from features import assets, background  # noqa: E402

N = 500


def run():
    cfg = make_config({})
    hard, review = assets.audit_lists(cfg)
    assert hard, "exclude.json not found / empty"
    stats = {}
    # backgrounds exactly as render_scene draws them (stream (seed, index, 1)), 500 seeds
    fam, files, rev = collections.Counter(), collections.Counter(), 0
    for seed in range(N):
        p = background.sample_background_params(np.random.default_rng([seed, 0, 1]), cfg)
        r = assets.repo_rel(p["file"])
        assert os.path.basename(r) not in hard and "_rejected" not in r, f"seed {seed}: hard-excluded background sampled: {r}"
        fam[p.get("family")] += 1
        files[r] += 1
        rev += p["audit"] == "review"
    stats["backgrounds"] = dict(grass_share=fam["grass"] / N, distinct=len(files), review_share=rev / N)
    for kind in ("ROCK", "GRASS", "LEAF", "DIRT"):
        seen = collections.Counter()
        for seed in range(N):
            f = assets.pick_file(np.random.default_rng([seed, 99]), cfg, kind)
            if f is None:
                continue
            r = assets.repo_rel(f)
            assert os.path.basename(r) not in hard and "_rejected" not in r, f"seed {seed}: hard-excluded {kind} sampled: {r}"
            seen[r] += 1
        stats[kind.lower()] = dict(distinct=len(seen),
                                   review_share=sum(v for k, v in seen.items() if os.path.basename(k) in review) / N)
    # v1 mode keeps every v1 file (incl. the watermarked ones)
    v1 = make_config({"v1": True})
    v1_bg = {assets.repo_rel(assets.pick_file(np.random.default_rng([s, 1]), v1, "BACKGROUND")) for s in range(N)}
    assert any(os.path.basename(r) in hard for r in v1_bg), "v1 mode no longer samples the original (excluded) backgrounds"
    stats["v1_backgrounds_distinct"] = len(v1_bg)
    return stats


def test_no_hard_excluded_asset_sampled():
    run()


if __name__ == "__main__":
    for k, v in run().items():
        print(k, v)
    print("PASS")
