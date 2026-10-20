#!/usr/bin/env python3
"""v2 dataset driver: balanced sampling plan + (optional) parallel render. Generator code is not modified; every
per-image choice is passed to DatasetGenerator/scene.render_scene as controlPanel overrides.

    python3 scripts/generate_dataset.py --plan-only                 # write the 3000-row plan, render nothing
    python3 scripts/generate_dataset.py --verify-plan 4             # render 4 plan rows in memory, check plan == render
    python3 scripts/generate_dataset.py --render --workers 4        # full dataset (NOT run yet: awaiting confirmation)
    python3 scripts/generate_dataset.py --render --limit 8 --out /tmp/x   # small trial render elsewhere

Design (docs/history/0013-dataset-v2-plan.md, zoomed 640x640 revision: 0016-zoomed-640-dataset.md):
  * Output: 640x640 NATIVE crop of the 1920x1080 scene (OUTPUT_CROP; no resize), all mines inside the crop, YOLO labels
    normalised to the crop; SCENE_ZOOM_COUPLING on (debris / soil sizes x mine scale / 0.2, counts x (0.2 / scale)^2,
    background magnified, capped at 1.5 output px per source px).
  * STRATIFIED image-level factors get exact equal-count (or exact-quota) buckets: mines per image (0-4), mine scale
    (4 linear bins 0.25-0.40), burial fraction (target, of buried mines), sun elevation, light (overcast / 4 shadow-strength bins),
    background family (+ file quotas proportional to the tuned weights), lens blur. Each image draws its value
    uniformly INSIDE its bucket with the generator's own RNG (override = bucket range).
  * Joint coverage: every factor column starts as a shuffled balanced list; a swap search (swaps inside one column
    keep its marginal exact) then minimises the pairwise chi-square over all factor pairs, i.e. every pair of
    factors is close to an orthogonal (independent, evenly crossed) design without a full cross.
  * The train / val split is one more column (2700 / 300) balanced the same way against every factor.
  * Everything else (sun azimuth, mine pose / face-down / colour / burial yes-no / position, debris counts, camera
    jitter) stays RANDOMIZED with the controlPanel distributions; per-mine values are replicated in the plan from
    the same random streams the renderer uses (exact, see --verify-plan).

Low priority / hygiene for --render: re-execs under `caffeinate -i`, nice 10, `taskpolicy -b` on itself and every
worker, OMP / MKL / OpenCV 1 thread, spawn pool from this file, pool terminated on error / Ctrl-C.
"""
import argparse
import csv
import json
import os
import sys
import time

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(REPO, "DatasetGenerator")
sys.path.insert(0, GEN)

from config import make_config  # noqa: E402
from features import background, camera, colour, mesh, soil, sun as sunmod, zoom as zoommod  # noqa: E402

# ------------------------------------------------------------------------------------------------ design constants
N_IMAGES = 3000
BASE_SEED = 2026            # image k uses render_scene(seed=BASE_SEED, index=k); showcase / samples use seed 0
SPARE_INDEX0 = 100000       # retries: row k, attempt a -> index SPARE_INDEX0 + 10 k + a (never overlaps 0..2999)
PLAN_SEED = 20261020        # RNG of the design itself (bucket assignment, swap search)
VAL_COUNT = 300
OUT_DEFAULT = os.path.join(REPO, "output_dataset", "v2_3000")

# mines per image 0-4 (user decision, ADR 0016): 600 empty (20 %), 600 each for 1..4
N_MINES_LEVELS = list(range(5))
N_MINES_QUOTA = [600] * 5
SCALE_EDGES = [float(x) for x in np.linspace(0.25, 0.40, 5)]     # 4 LINEAR bins of MINE_SCALE (user decision, ADR 0016)
OUTPUT_CROP = (640, 640)                                           # native crop of the 1920x1080 render (no resize)
BURIAL_EDGES = [0.05, 0.2, 0.3, 0.4, 0.5]                          # 4 bins of the target burial fraction
ELEV_EDGES = [float(x) for x in np.linspace(15.0, 70.0, 7)]        # 6 bins of sun elevation
SHADOW_EDGES = [float(x) for x in np.linspace(0.25, 0.65, 5)]      # 4 bins of direct-sun shadow strength
OVERCAST_COUNT = 450                                               # exactly 15 %
PSF_EDGES = [0.0, 0.5, 1.0, 1.5]                                   # 3 bins of lens-blur sigma
FAMILY_QUOTA = {"grass": 1950, "non_grass": 1050}                  # exactly 65 / 35 %

# factor name -> (levels, quota); "light" level 0 = overcast, 1..4 = shadow-strength bins
_direct = N_IMAGES - OVERCAST_COUNT
FACTORS = {
    "n_mines": (N_MINES_LEVELS, N_MINES_QUOTA),
    "scale_bin": (list(range(4)), [750] * 4),
    "burial_bin": (list(range(4)), [750] * 4),
    "elev_bin": (list(range(6)), [500] * 6),
    "light": (list(range(5)), [OVERCAST_COUNT] + [_direct // 4 + (1 if i < _direct % 4 else 0) for i in range(4)]),
    "family": ([0, 1], [FAMILY_QUOTA["grass"], FAMILY_QUOTA["non_grass"]]),
    "psf_bin": (list(range(3)), [1000] * 3),
}
FAMILY_NAMES = ["grass", "non_grass"]


def bucket_range(edges, b):
    return float(edges[b]), float(edges[b + 1])


# ------------------------------------------------------------------------------------------------ balanced design
def _chi2_tables(cols, levels):
    F = cols.shape[1]
    N = cols.shape[0]
    marg = [np.bincount(cols[:, f], minlength=levels[f]).astype(float) for f in range(F)]
    C, E = {}, {}
    for a in range(F):
        for b in range(a + 1, F):
            c = np.zeros((levels[a], levels[b]))
            np.add.at(c, (cols[:, a], cols[:, b]), 1)
            C[a, b], E[a, b] = c, np.outer(marg[a], marg[b]) / N
    return C, E


def chi2_total(C, E):
    return float(sum(((C[k] - E[k]) ** 2 / E[k]).sum() for k in C))


def balance_columns(cols, levels, rng, iters, movable):
    """Swap search: pick a movable column f and two rows with different values, swap if the summed pairwise
    chi-square does not increase. Marginals never change."""
    C, E = _chi2_tables(cols, levels)
    F, N = cols.shape[1], cols.shape[0]
    start = chi2_total(C, E)
    for _ in range(iters):
        f = movable[rng.integers(len(movable))]
        i, j = rng.integers(N, size=2)
        vi, vj = cols[i, f], cols[j, f]
        if vi == vj:
            continue
        delta, upd = 0.0, []
        for g in range(F):
            if g == f:
                continue
            gi, gj = cols[i, g], cols[j, g]
            if gi == gj:
                continue
            key = (f, g) if f < g else (g, f)
            c, e = C[key], E[key]
            cells = [(vi, gi, -1), (vj, gi, +1), (vi, gj, +1), (vj, gj, -1)]
            for (x, y, d) in cells:
                r, s = (x, y) if f < g else (y, x)
                o = c[r, s]
                delta += ((o + d - e[r, s]) ** 2 - (o - e[r, s]) ** 2) / e[r, s]
                upd.append((key, r, s, d))
        if delta <= 0:
            for key, r, s, d in upd:
                C[key][r, s] += d
            cols[i, f], cols[j, f] = vj, vi
    return start, chi2_total(C, E), C, E


def balanced_column(levels, quota, rng):
    col = np.repeat(np.asarray(levels), quota)
    rng.shuffle(col)
    return col


EXCLUDE_BG = {"grass1.png", "grass2.png"}  # removed from the dataset by the user (v1 grass snippets); their share is redistributed over the other files


def largest_remainder(total, weights):
    w = np.asarray(weights, float)
    raw = total * w / w.sum()
    n = np.floor(raw).astype(int)
    for k in np.argsort(-(raw - n))[: total - n.sum()]:
        n[k] += 1
    return n


def build_design():
    rng = np.random.default_rng(PLAN_SEED)
    names = list(FACTORS)
    levels = [len(FACTORS[n][0]) for n in names]
    cols = np.stack([balanced_column(*FACTORS[n], rng) for n in names], 1)
    s0, s1, C, E = balance_columns(cols, levels, rng, 300_000, movable=list(range(len(names))))
    # train / val split as one more balanced column
    split = balanced_column([0, 1], [N_IMAGES - VAL_COUNT, VAL_COUNT], rng)
    cols2 = np.concatenate([cols, split[:, None]], 1)
    v0, v1, _, _ = balance_columns(cols2, levels + [2], rng, 200_000, movable=[len(names)])
    design = [{n: int(cols2[k, f]) for f, n in enumerate(names)} | {"split": "val" if cols2[k, -1] else "train"}
              for k in range(N_IMAGES)]
    # background file quotas within each family, proportional to the tuned effective weights
    cfg = make_config()
    idx = background._load_index(cfg)
    names_seen = [os.path.basename(p) for fam in idx["families"].values() for p, _, _ in fam]
    assert len(names_seen) == len(set(names_seen)), "background basenames are not unique"
    for fi, fam in enumerate(FAMILY_NAMES):
        items = [it for it in idx["families"][fam] if os.path.basename(it[0]) not in EXCLUDE_BG]  # user: drop v1 grass1/grass2
        n = largest_remainder(FAMILY_QUOTA[fam], [w for _, w, _ in items])
        files = np.repeat(np.arange(len(items)), n)
        rng.shuffle(files)
        rows = [r for r in design if r["family"] == fi]
        for r, k in zip(rows, files):
            p, w, cat = items[int(k)]
            r.update(bg_file=os.path.basename(p), bg_category=cat, bg_weight=float(w))
    pair_stats = {f"{names[a]} x {names[b]}": round(float(((C[a, b] - E[a, b]) ** 2 / E[a, b]).sum()), 3)
                  for (a, b) in C}
    stats = {"chi2_pairs_before": round(s0, 2), "chi2_pairs_after": round(s1, 2),
             "chi2_split_before": round(v0, 2), "chi2_split_after": round(v1, 2), "chi2_per_pair": pair_stats}
    for k, r in enumerate(design):
        r["row"] = k
        r["index"] = k
    return design, stats


# ------------------------------------------------------------------------------------------------ row -> overrides
_BG_FAMILY_FILES = None


def _family_files():
    global _BG_FAMILY_FILES
    if _BG_FAMILY_FILES is None:
        cfg = make_config()
        idx = background._load_index(cfg)
        _BG_FAMILY_FILES = {fam: [os.path.basename(p) for p, _, _ in items] for fam, items in idx["families"].items()}
    return _BG_FAMILY_FILES


def row_overrides(r):
    """Full controlPanel overrides for one plan row (the only place a row is turned into generator settings)."""
    fam = FAMILY_NAMES[r["family"]]
    base = dict(make_config().BG_WEIGHT_OVERRIDES)
    force = {b: 0.0 for b in _family_files()[fam] if b != r["bg_file"]}
    force[r["bg_file"]] = 1.0
    ov = {"N_MINES": r["n_mines"],
          "MINE_SCALE_MIN": bucket_range(SCALE_EDGES, r["scale_bin"])[0],
          "MINE_SCALE_MAX": bucket_range(SCALE_EDGES, r["scale_bin"])[1],
          "BURIAL_FRACTION": bucket_range(BURIAL_EDGES, r["burial_bin"]),
          "SUN_ELEVATION": bucket_range(ELEV_EDGES, r["elev_bin"]),
          "OVERCAST_PROB": 1.0 if r["light"] == 0 else 0.0,
          "BG_FAMILY_WEIGHTS": {fam: 1.0},
          "BG_WEIGHT_OVERRIDES": {**base, **force},
          "PSF_SIGMA": bucket_range(PSF_EDGES, r["psf_bin"]),
          "SCENE_ZOOM_COUPLING": True,
          "OUTPUT_CROP": OUTPUT_CROP}
    if r["light"] > 0:
        ov["SHADOW_STRENGTH"] = bucket_range(SHADOW_EDGES, r["light"] - 1)
    return ov


def compact_overrides(r):
    """What the sidecar's "overrides" field records (the forced-file weight table is summarised as bg_force)."""
    ov = row_overrides(r)
    ov["BG_WEIGHT_OVERRIDES"] = {"bg_force": r["bg_file"]}
    return ov


# ------------------------------------------------------------------------------------------------ plan replication
def plan_values(r, index=None):
    """Replicates the renderer's cheap random draws for row r (same streams as scene.render_scene / objects.Mine).
    -> (image dict, [mine dicts]). Debris, positions and burial-cue details are drawn inside the renderer and are
    not replicated (configured distributions are shown instead)."""
    cfg = make_config(row_overrides(r))
    seed, index = BASE_SEED, r["index"] if index is None else index
    R = lambda *k: np.random.default_rng([seed, int(index), *k])  # noqa: E731
    s = sunmod.sample_sun(R(0), cfg)
    bgp = background.sample_background_params(R(1), cfg)
    image_scale = float(R(9).uniform(cfg.MINE_SCALE_MIN, cfg.MINE_SCALE_MAX))
    px_mm = float(cfg.MINE_PX_PER_UNIT * image_scale / cfg.MINE_LENGTH_MM)
    cam = camera.sample_camera_params(R(7), cfg)
    z = zoommod.zoom_factor(image_scale, cfg)
    x0, y0, cw, ch = zoommod.crop_window(R(11), cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT, *cfg.OUTPUT_CROP)
    bg_zoom, bzi = zoommod.zoom_background(bgp, z, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT, _src_hw(bgp["file"]), cfg)
    img = {"sun_azimuth": s["azimuth"], "sun_elevation": s["elevation"], "overcast": s["overcast"],
           "shadow_strength": s["shadow_strength"], "shadow_tint": s["shadow_tint"],
           "bg_file_sampled": os.path.basename(bgp["file"]), "bg_flip_h": bgp["flip_h"], "bg_flip_v": bgp["flip_v"],
           "bg_rot90": bgp["rot90"], "bg_zoom": bgp["zoom"], "bg_hue": bgp["hue"], "bg_sat": bgp["sat"],
           "bg_bright": bgp["bright"], "ground_px_per_mm": px_mm, "image_scale": image_scale, "zoom": z,
           "count_factor": zoommod.count_factor(z, cfg), "bg_zoom_coupled": bg_zoom,
           "bg_magnification": bzi["magnification"], "bg_mag_capped": bzi["capped"],
           "crop_x0": x0, "crop_y0": y0}
    for k in ("psf_sigma", "motion_px", "motion_angle", "exposure", "gamma", "wb_r", "wb_b", "saturation", "contrast",
              "noise_sigma", "noise_chroma", "aberration", "vignette", "jpeg_quality"):
        img[k] = cam[k]
    mines = []
    for j in range(r["n_mines"]):
        sub = lambda k: np.random.default_rng([seed, int(index), 10, j, k])  # noqa: E731
        scale = float(sub(0).uniform(cfg.MINE_SCALE_MIN, cfg.MINE_SCALE_MAX))
        pitch, roll, yaw, fd = mesh.sample_pose(sub(1), cfg)
        _, cp = colour.sample_colour(sub(2), cfg)
        b = mesh.sample_burial(sub(3), cfg)
        spec = mesh.sample_specular(sub(4), cfg)
        sp = soil.sample_soil_params(sub(5), cfg)
        mines.append({"j": j, "scale": scale, "length_px": scale * cfg.MINE_PX_PER_UNIT, "pitch": pitch,
                      "roll": roll, "yaw": yaw, "face_down": fd, "colour_family": cp["family"], "h": cp["h"],
                      "s": cp["s"], "v": cp["v"], "bleach": cp["bleach"], "dirt_tint": cp["dirt_tint"],
                      "brightness": cp["brightness"], "buried": b is not None,
                      "burial_fraction": b["fraction"] if b else 0.0, "burial_tilt": b["tilt"] if b else None,
                      "burial_direction": b["direction"] if b else None, "burial_wander": b["wander"] if b else None,
                      "specular": spec[0], "specular_exp": spec[1], "dust_strength": sp["dust_strength"],
                      "band_px": sp["band_px"], "band_darken": sp["band_darken"],
                      "grain_density": sp["grain_density"]})
    return img, mines


_SRC_HW = {}


def _src_hw(path):
    """(h, w) of a background file from its header (PIL, no decode)."""
    if path not in _SRC_HW:
        from PIL import Image
        with Image.open(path) as im:
            _SRC_HW[path] = (im.size[1], im.size[0])
    return _SRC_HW[path]


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


def make_plan(out):
    t0 = time.time()
    design, stats = build_design()
    img_rows, mine_rows = [], []
    for r in design:
        img, mines = plan_values(r)
        assert img["bg_file_sampled"] == r["bg_file"], (r, img["bg_file_sampled"])
        lo_s, hi_s = bucket_range(SCALE_EDGES, r["scale_bin"])
        img_rows.append({"index": r["index"], "seed": BASE_SEED, "split": r["split"], "n_mines": r["n_mines"],
                         "scale_bin": r["scale_bin"], "scale_lo": lo_s, "scale_hi": hi_s,
                         "burial_bin": r["burial_bin"], "elev_bin": r["elev_bin"], "light": r["light"],
                         "family": FAMILY_NAMES[r["family"]], "psf_bin": r["psf_bin"], "bg_file": r["bg_file"],
                         "bg_category": r["bg_category"], **{k: v for k, v in img.items() if k != "bg_file_sampled"}})
        for m in mines:
            mine_rows.append({"index": r["index"], "split": r["split"], "scale_bin": r["scale_bin"],
                              "burial_bin": r["burial_bin"], **m})
    plan_dir = os.path.join(out, "plan")
    os.makedirs(plan_dir, exist_ok=True)
    write_csv(os.path.join(plan_dir, "plan_images.csv"), img_rows)
    write_csv(os.path.join(plan_dir, "plan_mines.csv"), mine_rows)
    counts = {n: {str(l): int(sum(1 for r in design if r[n] == l)) for l in FACTORS[n][0]} for n in FACTORS}
    val_counts = {n: {str(l): int(sum(1 for r in design if r[n] == l and r["split"] == "val")) for l in FACTORS[n][0]}
                  for n in FACTORS}
    meta = {"n_images": N_IMAGES, "base_seed": BASE_SEED, "plan_seed": PLAN_SEED, "spare_index0": SPARE_INDEX0,
            "edges": {"scale": SCALE_EDGES, "burial_fraction": BURIAL_EDGES, "sun_elevation": ELEV_EDGES,
                      "shadow_strength": SHADOW_EDGES, "psf_sigma": PSF_EDGES},
            "factors": {n: {"levels": FACTORS[n][0], "quota": FACTORS[n][1]} for n in FACTORS},
            "counts": counts, "val_counts": val_counts, "balance": stats,
            "split": {"train": sum(r["split"] == "train" for r in design), "val": VAL_COUNT,
                      "val_indices": [r["index"] for r in design if r["split"] == "val"]},
            "n_mines_planned": len(mine_rows),
            "n_buried_planned": int(sum(m["buried"] for m in mine_rows)),
            "plan_seconds": round(time.time() - t0, 1)}
    with open(os.path.join(plan_dir, "plan.json"), "w") as f:
        json.dump(meta, f, indent=1)
    with open(os.path.join(plan_dir, "plan_design.json"), "w") as f:
        json.dump(design, f)
    write_readme(out, meta, rendered=False)
    print(f"plan: {N_IMAGES} images, {len(mine_rows)} mines ({meta['n_buried_planned']} buried), "
          f"train {meta['split']['train']} / val {VAL_COUNT}; pairwise chi2 {stats['chi2_pairs_before']} -> "
          f"{stats['chi2_pairs_after']}, split chi2 {stats['chi2_split_before']} -> {stats['chi2_split_after']}; "
          f"{meta['plan_seconds']} s -> {plan_dir}")
    return design, meta


def load_design(out):
    with open(os.path.join(out, "plan", "plan_design.json")) as f:
        return json.load(f)


def write_readme(out, meta, rendered):
    status = ("RENDERED" if rendered else
              "PLAN ONLY: images not generated yet (awaiting the user's confirmation of the plan)")
    c = meta["counts"]
    txt = f"""# IARC synthetic PFM-1 dataset v2 (3000 images)

Status: {status}.

Made by `scripts/generate_dataset.py` (plan: `--plan-only`; images: `--render --workers 4`) from the v2 generator in
`DatasetGenerator/` (HEAD burial / realism round 4 + soft grains + zoom coupling). Design rationale:
`docs/history/0013-dataset-v2-plan.md`, zoomed 640x640 revision `docs/history/0016-zoomed-640-dataset.md`;
per-parameter page: `docs/showcase/showcase.html`, tab "Dataset v2: parameters".

- Images: 640x640 RGB JPEG, a NATIVE crop of the 1920x1080 render (no resize / resampling; v1's `finalDataset` was
  stretched to 640x640 by exportToYOLO.py). Every mine is placed fully inside the crop (8 px margin); the crop
  position is uniform. Labels are normalised to the crop. JPEG quality sampled 70-95 per image.
- Zoom coupling (SCENE_ZOOM_COUPLING): per image z = mine scale / 0.2; rocks, grass clippings, leaf clumps, dirt and
  the mine's soil / contact / AO sizes x z, debris counts x z^-2, background texture magnified by z (capped at 1.5
  output px per source px); grass blades follow the ground px/mm; sensor effects (PSF, noise, aberration px) unchanged.
- Seeds: image k = `render_scene(seed={meta['base_seed']}, index=k)`; retries use index {meta['spare_index0']} + 10 k + attempt.
- Split: train {meta['split']['train']} / val {meta['split']['val']} (val indices in plan/plan.json), balanced on every stratified factor.
- Layout after rendering: images/{{train,val}}/v2_NNNNN.jpg, labels/{{train,val}}/v2_NNNNN.txt (YOLO: class xc yc w h,
  normalised), meta/v2_NNNNN.json (generator sidecar + "plan" block), manifest.csv (realised parameters), data.yaml.
- plan/: plan_images.csv (one row per image: bucket ids + every replicated per-image draw), plan_mines.csv (one row
  per planned mine), plan.json (edges, quotas, counts, balance statistics), plan_design.json.

## Stratified factors (equal-count buckets; value drawn uniformly inside the bucket)

| factor | buckets | counts |
|---|---|---|
| mines per image (N_MINES) | 0..4 | {list(c['n_mines'].values())} |
| mine scale (MINE_SCALE_MIN/MAX), linear bins {[round(e, 4) for e in meta['edges']['scale']]} | 4 | {list(c['scale_bin'].values())} |
| burial target fraction of buried mines (BURIAL_FRACTION) {meta['edges']['burial_fraction']} | 4 | {list(c['burial_bin'].values())} |
| sun elevation (SUN_ELEVATION) {[round(e, 2) for e in meta['edges']['sun_elevation']]} | 6 | {list(c['elev_bin'].values())} |
| light: overcast / shadow strength bins {meta['edges']['shadow_strength']} | 1 + 4 | {list(c['light'].values())} |
| background family grass / non_grass (+ per-file quotas by weight) | 2 | {list(c['family'].values())} |
| lens blur PSF_SIGMA {meta['edges']['psf_sigma']} | 3 | {list(c['psf_bin'].values())} |

Everything else is randomized with the controlPanel distributions (see the showcase tab for each parameter).
Planned mines: {meta['n_mines_planned']} ({meta['n_buried_planned']} buried).
"""
    with open(os.path.join(out, "README.md"), "w") as f:
        f.write(txt)


# ------------------------------------------------------------------------------------------------ render
_OUT = None
_JPEG_Q = None


def _low_priority(pid):
    try:
        os.setpriority(os.PRIO_PROCESS, pid, 10)
    except Exception:
        pass
    if sys.platform == "darwin":
        os.system(f"taskpolicy -b -p {int(pid)} >/dev/null 2>&1")


def _init_worker(out, jpeg_q):
    global _OUT, _JPEG_Q
    import cv2
    cv2.setNumThreads(1)
    _OUT, _JPEG_Q = out, jpeg_q
    _low_priority(os.getpid())


def render_row(r):
    """Render one plan row with retries -> summary dict. Retry on exception or burial cap exceeded."""
    from scene import render_scene
    out = _OUT
    name = f"v2_{r['index']:05d}"
    last_err = None
    for attempt in range(5):
        index = r["index"] if attempt == 0 else SPARE_INDEX0 + 10 * r["index"] + attempt
        try:
            cfg = make_config(row_overrides(r))
            rgb, labels, meta = render_scene(BASE_SEED, compact_overrides(r), index=index, cfg=cfg)
            hidden = [m.get("burial", {}).get("achieved", 0.0) or 0.0 for m in meta["mines"]]
            if any(m.get("burial", {}).get("cap_exceeded") for m in meta["mines"]):
                last_err = f"burial cap exceeded (max hidden {max(hidden):.3f})"
                continue
            q = int(meta["post"]["jpeg_quality"]) if _JPEG_Q is None else int(_JPEG_Q)
            meta["plan"] = {k: r[k] for k in ("row", "split", *FACTORS, "bg_file")} | {
                "attempt": attempt, "render_index": index, "base_seed": BASE_SEED, "saved_jpeg_quality": q}
            sp = r["split"]
            with open(os.path.join(out, "images", sp, name + ".jpg"), "wb") as f:
                f.write(camera.encode_jpeg(rgb, q))
            with open(os.path.join(out, "labels", sp, name + ".txt"), "w") as f:
                for l in labels:
                    f.write(f"{int(l[0])} {l[1]:.6f} {l[2]:.6f} {l[3]:.6f} {l[4]:.6f}\n")
            with open(os.path.join(out, "meta", name + ".json"), "w") as f:
                json.dump(meta, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
            return {"index": r["index"], "ok": True, "attempt": attempt, "render_index": index,
                    "n_labels": len(labels), "n_placed": len(meta["mines"]), "n_planned": r["n_mines"],
                    "max_hidden": max(hidden) if hidden else 0.0, "error": last_err}
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
    return {"index": r["index"], "ok": False, "error": last_err}


def build_manifest(out, design):
    rows = []
    for r in design:
        p = os.path.join(out, "meta", f"v2_{r['index']:05d}.json")
        if not os.path.isfile(p):
            continue
        with open(p) as f:
            m = json.load(f)
        post, s = m["post"], m["sun"]
        ms = m["mines"]
        rows.append({"index": r["index"], "split": r["split"], **{k: r[k] for k in FACTORS},
                     "bg_file": r["bg_file"], "sun_azimuth": s["azimuth"], "sun_elevation": s["elevation"],
                     "overcast": s["overcast"], "shadow_strength": s["shadow_strength"],
                     "psf_sigma": post["psf_sigma"], "motion_px": post["motion_px"], "exposure": post.get("exposure"),
                     "zoom": m.get("zoom", {}).get("factor"), "crop_x0": m.get("crop", {}).get("x0"),
                     "crop_y0": m.get("crop", {}).get("y0"),
                     "bg_magnification": m.get("zoom", {}).get("background", {}).get("magnification"),
                     "jpeg_quality": m["plan"]["saved_jpeg_quality"], "n_placed": len(ms),
                     "n_labelled": sum(1 for x in ms if x.get("labelled")),
                     "n_buried": sum(1 for x in ms if x.get("burial", {}).get("buried")),
                     "max_hidden": max([x.get("burial", {}).get("achieved", 0.0) or 0.0 for x in ms] or [0.0]),
                     "n_face_down": sum(1 for x in ms if x.get("face_down")),
                     "attempt": m["plan"]["attempt"]})
    write_csv(os.path.join(out, "manifest.csv"), rows)
    return rows


def render(out, design, workers, limit, jpeg_q):
    for d in ("images/train", "images/val", "labels/train", "labels/val", "meta"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    rows = design[:limit] if limit else design
    t0 = time.time()
    results = []
    from multiprocessing import get_context
    pool = get_context("spawn").Pool(workers, initializer=_init_worker, initargs=(out, jpeg_q))
    try:
        for k, res in enumerate(pool.imap_unordered(render_row, rows, chunksize=2)):
            results.append(res)
            if k % 100 == 0 or k == len(rows) - 1:
                el = time.time() - t0
                print(f"{k + 1}/{len(rows)}  {el / 60:.1f} min  eta {(len(rows) - k - 1) * el / (k + 1) / 60:.1f} min",
                      flush=True)
        pool.close()
    except BaseException:
        pool.terminate()
        raise
    finally:
        pool.join()
    dt = time.time() - t0
    with open(os.path.join(out, "render_log.json"), "w") as f:
        json.dump({"seconds": dt, "workers": workers, "results": sorted(results, key=lambda x: x["index"])}, f, indent=1)
    with open(os.path.join(out, "data.yaml"), "w") as f:
        f.write(f"path: {out}\ntrain: images/train\nval: images/val\nnames:\n  0: pfm1\n")
    man = build_manifest(out, design)
    fails = [r for r in results if not r["ok"]]
    print(f"rendered {len(results) - len(fails)} / {len(rows)} in {dt / 60:.1f} min "
          f"({dt / max(len(rows), 1) * workers:.2f} s/img/worker); failures {len(fails)}; "
          f"retried {sum(1 for r in results if r.get('attempt', 0) > 0)}; manifest rows {len(man)}")


def verify_plan(design, k):
    """Render k rows in memory (no files) and compare the replicated plan values with the render's sidecar."""
    from scene import render_scene
    picks = []
    for b in range(len(SCALE_EDGES) - 1):          # spread over the scale bins
        picks += [r for r in design if r["n_mines"] >= 2 and r["scale_bin"] == b][: -(-k // (len(SCALE_EDGES) - 1))]
    picks = picks[:k]
    for r in picks:
        t = time.time()
        img, mines = plan_values(r)
        _, labels, meta = render_scene(BASE_SEED, compact_overrides(r), index=r["index"],
                                       cfg=make_config(row_overrides(r)))
        dt = time.time() - t
        s = meta["sun"]
        ok = [abs(s["elevation"] - img["sun_elevation"]) < 1e-9, abs(s["azimuth"] - img["sun_azimuth"]) < 1e-9,
              os.path.basename(meta["background"]["file"]) == r["bg_file"],
              abs(meta["post"]["psf_sigma"] - img["psf_sigma"]) < 1e-9,
              abs(meta["zoom"]["factor"] - img["zoom"]) < 1e-9,
              abs(meta["background"]["zoom"] - img["bg_zoom_coupled"]) < 1e-9,
              meta["crop"]["x0"] == img["crop_x0"] and meta["crop"]["y0"] == img["crop_y0"]]
        # labels: inside [0, 1] of the crop, one per labelled mine, matching the full-frame pixel box
        cx, cy = meta["crop"]["x0"], meta["crop"]["y0"]
        for l, m in zip(labels, [m for m in meta["mines"] if m["labelled"]]):
            x0, y0, bw, bh = m["box_px_full"]
            ok += [all(0 <= v <= 1 for v in (l[1] - l[3] / 2, l[2] - l[4] / 2, l[1] + l[3] / 2, l[2] + l[4] / 2)),
                   abs(l[1] * OUTPUT_CROP[0] - (x0 - cx + bw // 2)) < 1e-6 and abs(l[3] * OUTPUT_CROP[0] - bw) < 1e-6]
        for m, pm in zip(meta["mines"], mines):
            ok += [abs(m["scale"] - pm["scale"]) < 1e-9, abs(m["yaw"] - pm["yaw"]) < 1e-9,
                   m["face_down"] == pm["face_down"], m["burial"]["buried"] == pm["buried"]]
        print(f"row {r['index']}: scale bin {r['scale_bin']} (zoom {img['zoom']:.2f}), {r['n_mines']} planned, "
              f"{len(meta['mines'])} placed, {len(labels)} labels, checks {sum(ok)}/{len(ok)} match, {dt:.2f} s")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--plan-only", action="store_true", help="write plan/ + README, render nothing")
    ap.add_argument("--verify-plan", type=int, default=0, help="render N rows in memory and check plan == render")
    ap.add_argument("--render", action="store_true", help="render the dataset (writes images)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="render only the first N rows (trial)")
    ap.add_argument("--jpeg-quality", default="sampled",
                    help="'sampled' = the generator's per-image JPEG_QUALITY_RANGE (70-95), or a fixed int e.g. 95")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    if args.render and sys.platform == "darwin" and not os.environ.get("_GEN_CAFFEINATED"):
        os.environ["_GEN_CAFFEINATED"] = "1"
        os.execvp("caffeinate", ["caffeinate", "-i", sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
    if args.render:
        _low_priority(os.getpid())
    if args.plan_only or not os.path.isfile(os.path.join(out, "plan", "plan_design.json")):
        design, _ = make_plan(out)
    else:
        design = load_design(out)
    if args.verify_plan:
        verify_plan(design, args.verify_plan)
    if args.render:
        jq = None if args.jpeg_quality == "sampled" else int(args.jpeg_quality)
        render(out, design, args.workers, args.limit, jq)


if __name__ == "__main__":
    main()
