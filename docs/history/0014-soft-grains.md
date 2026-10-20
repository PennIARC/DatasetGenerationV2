# 0014: soft grains, a second blurred grain layer on the mine (`MINE_SOFT_GRAINS`)

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

## Context

Dataset generation (ADR 0013, `output_dataset/v2_3000`) was blocked on one more mine-surface augmentation. The user's
request, verbatim: "add a second augmentation similar to 'Soil grains and contact band' where you add randomized
grains except you should blur/smooth these out more".

The existing feature (`SOIL_BLEND`, `soil.soil_blend`, `docs/CHANGES.md` section 4) has a contact band inside the
outline and crisp soil grains: thresholded 1.5 px fBm with a hard 0.03 ramp, covering 0-5% of the mine at 0.5-0.9
opacity. They read as sharp dots at 4-6x.

## Decision

- Add a new, separate flag `MINE_SOFT_GRAINS` (default on, needs `SOIL_BLEND`) with its own parameters in
  `controlPanel.py`. It applies to a mine with probability `SOFT_GRAIN_PROB` = 0.75. Per mine it draws:
  - density 6-22%
  - speckle size 1.2-3.5% of the mine length (about 2-5 px)
  - blur sigma 1.2-3 px
  - peak opacity 0.2-0.45
  - tone 0.65-1.3 x the blurred local ground
  - contact-zone density boost 0.5-2 (applied within 8% of the length from the outline)

  The result is soft, low-contrast, larger blotches, not dots. Varying the parameters per mine adds variation
  between mines.
- The layer uses its own random sub-stream (mine sub-stream 12, 9 draws every time). No existing draw moves:
  - with the flag off, images are identical to before;
  - with the flag on, labels, all other sidecar values and the v2_3000 plan are unchanged.
- It changes colour only, never alpha, so the 50% burial cap, labels and the `render_scene` API are untouched. It is
  computed on the unclipped silhouette's box, so burial only removes speckle.
- The sidecar logs `mine["soft_grains"]` (apply, density, size_frac, blur_px, strength, tone, edge_boost).

## Consequences

- `docs/soft_grains.png` (`scripts/soft_grains_figure.py`): 6 cases (gravel, dark grass, light dry grass, bare soil,
  face down, buried 40%). Columns are off / existing grains only / + soft grains, with the sampled parameters
  captioned.
- `tests/test_soft_grains.py`:
  - only the mines change; labels and other sidecar values are identical;
  - the change has 10-60x less pixel-scale (Laplacian) energy per unit than the crisp grains;
  - prob 0 leaves the image unchanged.
- The plan's `plan_mines.csv` was re-derived for 1385 mines with 0 differences, and `--verify-plan 3` matched on
  all checks.
- For the dataset plan, the soft-grain parameters should be a RANDOM, unstratified per-mine factor. To record
  them, `plan_values` can replicate them with `soil.sample_soft_grain_params(sub(12), cfg)`.
- The other docs sheets (`burial_realism.png`, `v1_vs_v2.png`, `mine_crops.png`, ...) predate this layer and do not
  show it. Mines whose colour is close to the ground get almost invisible soft grains (the colour comes from the
  ground). That is intended: it is low contrast.

## Feedback that triggered this

- User request relayed by the lead (quoted above).

## Commits

None yet (left uncommitted for the lead).
