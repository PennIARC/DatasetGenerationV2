# 0013: dataset v2 (3000 images) sampling plan: plan awaiting confirmation

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

Status: **plan awaiting confirmation**. The 3000-row plan exists (`output_dataset/v2_3000/plan/`, gitignored, rebuilt
by `python3 scripts/generate_dataset.py --plan-only`); no dataset images have been rendered.

## Context

The user judged the burial / realism state at `5ca4e9e` "strong enough to be used" and asked for a v2 dataset of
3000 images with every parameter documented in a fourth showcase tab. Before rendering, the user asked to confirm
the plan first (relayed by the lead): "do NOT generate the dataset yet; the user wants to confirm the plan first ...
write the sampling plan as code that produces the full 3000-row PLANNED parameter table WITHOUT rendering".

Constraints: generator rendering code unchanged (only a new driver), keep the user's tuned distributions (grass
~65 %, FLIP_PROB 0.30, flat-skewed poses, sun 15-70 deg + 15 % overcast, shadow 0.25-0.65, dust ~35 %, burial
<= 50 %, blades over mines) unless stratification replaces them, and document every deliberate change.

## Decision

`scripts/generate_dataset.py` turns each plan row into controlPanel overrides for `scene.render_scene` (seed 2026,
index = row). Image-level factors that drive detection difficulty or where coverage gaps matter are **stratified**
(exact equal-count buckets or exact quotas; the value is drawn by the generator uniformly inside the bucket):

| factor | override | buckets | counts |
|---|---|---|---|
| mines per image | N_MINES | 9 (0..8) | 600, then 300 each (the generator's real pmf, made exact) |
| mine scale | MINE_SCALE_MIN/MAX | 5 log bins 0.1-0.4 | 600 each |
| burial target fraction | BURIAL_FRACTION | 4: 0.05-0.2-0.3-0.4-0.5 | 750 each |
| sun elevation | SUN_ELEVATION | 6 x 9.2 deg, 15-70 | 500 each |
| light | OVERCAST_PROB 0/1, SHADOW_STRENGTH | overcast + 4 strength bins | 450 / 638 / 638 / 637 / 637 |
| background | BG_FAMILY_WEIGHTS + forced file | grass / non_grass, 99 file quotas | 1950 / 1050; file counts by tuned weight |
| lens blur | PSF_SIGMA | 3 x 0.5 px | 1000 each |

Joint coverage: each factor column is a shuffled balanced list, then a swap search (swaps inside one column keep
its marginal exact) minimises the summed pairwise chi-square over all 21 factor pairs: 298.0 -> 0.30, i.e. every
pair is almost perfectly evenly crossed without a full cross (9 x 5 x 4 x 6 x 5 x 2 x 3 = 32400 cells > 3000).
Because n_mines x scale and n_mines x burial are balanced, per-MINE counts per scale bucket are exact (2160 each).

The train / val split (2700 / 300) is one more balanced column (split chi-square 44.2 -> 0.32): every bucket of
every factor has 10 % in val. Train and val indices are disjoint; retries use spare indices 100000 + 10 row + attempt.

**Randomized** (i.i.d., controlPanel distributions unchanged): sun azimuth, shadow tint, motion blur, all
photometric jitter (exposure, gamma, WB, saturation, contrast, noise, aberration, vignette, JPEG quality),
background flips / rotations / zoom / colour jitter, and every per-mine factor (yaw, pitch / roll, face down,
colour family / HSV / bleach / dirt tint, burial yes / no at 0.35, burial tilt, dust, grains, specular, position,
blades on the mine) plus debris counts. Per-mine factors cannot be bucketed through image-level overrides (MINE_POSE
fixes all mines of an image to one pose); with 10800 mines their i.i.d. counts are within a few % of even.

The plan replicates the renderer's own random streams (sun, background, ground px/mm, camera, per-mine scale /
pose / colour / burial / specular / soil), so the plan tables are exactly what the render will produce;
`--verify-plan 4` rendered 4 rows in memory: 100 / 100 checked values matched.

Deliberate changes vs the generator defaults:
1. Mine scale log-uniform (equal count per log bin) instead of linear uniform: more small, hard mines (median
   0.20 instead of 0.25).
2. All mines of an image share one scale bucket, and the ground px/mm (blade size) comes from the same bucket
   (the default draws it independently of the mines).
3. Burial fraction buckets: the first bucket is 0.05-0.2 (wider), so per-0.01 density of the lightest burials is
   slightly lower than uniform 0.05-0.5.
4. Overcast, family and empty-image shares are exact instead of random.

## Decisions for the user to confirm

1. Dataset size 3000 (2700 / 300), 10800 planned mines (3763 buried).
2. Stratified vs randomized split above; bucket counts 9 / 5 / 4 / 6 / 5 / 2 / 3.
3. Log-uniform mine scale (or 5 linear bins).
4. Empty images 20 % (the generator's real P(0) = 0.10 + 0.9 / 9; the controlPanel comment says 10 %).
5. Format: native 1920x1080 JPEG, not resized. JPEG quality: generator-sampled 70-95 per image (default,
   recommended: an augmentation) or a fixed q95 as in the brief (`--jpeg-quality 95`).
6. v1 for comparison: v1 also rendered 1920x1080, then `exportToYOLO.py` stretched every image to 640x640 (16:9 -> 1:1,
   anisotropic) and re-saved at OpenCV's default quality 95 (`~/PycharmProjects/IARCdatasetGeneration/DatasetGenerator/finalDataset`).
7. Output: `output_dataset/v2_3000` (gitignored): images/{train,val}, labels/{train,val}, meta/, manifest.csv,
   data.yaml, plan/, README.md.
8. Time: single-process renders of plan rows took 0.8-2.0 s; ~15-25 min with 4 low-priority workers
   (`--render --workers 4`: caffeinate -i, nice 10, taskpolicy -b, 1 thread per worker).

## Consequences

- Fourth showcase tab "Dataset v2: parameters" (`docs/showcase/manifest_params.json`, built by
  `docs/showcase/showcase_scripts/params/build_params.py`): decisions table, overview table, bucket counts, and one
  card per parameter (43) with planned-distribution graph, type / buckets / range / override, and same-seed
  before / after renders. `template.html` / `build_showcase.py` gained optional `tables`, `facts` and `figure`
  fields (existing pages unchanged; showcase tests pass).
- After rendering, the manifest / contact sheet / realised hidden-fraction checks still need doing.

## Known limitations

- Per-mine factors are random, not stratified (would need per-mine override lists in the generator).
- Mine positions and debris counts are not in the plan (decided at render time); their graphs are approximations /
  configured distributions and are labelled as such.
- Buried-mine counts per burial bucket vary slightly (968 / 952 / 902 / 941) because burial yes / no is random.
- Placement of 8 large mines can fail (50 attempts); the render log records placed vs planned.
- Rocks, grass clippings and dirt are drawn in both debris layers (v1 behaviour), so some sit on top of mines.

## Commits

None yet (plan only; the lead commits).
