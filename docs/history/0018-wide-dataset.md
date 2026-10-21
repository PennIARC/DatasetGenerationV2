# 0018: second dataset, "wide" variant (960x960 crop of the zoomed-out original plan)

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

Status: **plan written and verified, dataset not yet rendered** (the lead starts the render). The zoomed 640x640
dataset of [0016](0016-zoomed-640-dataset.md) in `output_dataset/v2_3000` stays as it is and stays the generator's
default.

## Context

A YOLO model trained on the zoomed 640x640 set learned it easily. The user wrote
([feedback/0106](feedback/0106-wide-dataset-request.md), verbatim):

> the model seemed to actually learn this dataset quite easily. it might be worth it to go back to the 'zoomed out'
> original version of the dataset (so just undo the mine/rock/grass zooming in) and re-build that dataset. don't
> delete the existing current one, just create a second one. afterwards, train another yolo model on it for 10 epochs

Three decisions came out of the interview, all confirmed by the user:

1. "let's train on a 960x960 random crop of the fullsize 1920x1080 render".
2. The crop is **baked at generation**: `OUTPUT_CROP = (960, 960)`, a uniformly placed window that contains every mine,
   as in the 640 pipeline. The dataset is stored as 960x960 JPEG and trained later at imgsz 960.
3. **The original plan** ([0013](0013-dataset-v2-plan.md)): mine scale 0.1-0.4 in 5 log bins (600 images each),
   0-8 mines per image (600 empty, 300 each for 1-8), `SCENE_ZOOM_COUPLING` off, 3000 images, 2700 / 300 balanced
   split. All other strata stay as in the current plan: sun, light, burial, background family and per-file quotas
   (grass1.png / grass2.png excluded), PSF bins, JPEG quality sampled 70-95, random soft grains.

## Decision

- `scripts/generate_dataset.py --variant {zoom640,wide}`. The design constants moved into a `VARIANTS` table bound by
  `set_variant()` (also called in every spawned render worker). `zoom640` is the default and regenerates the existing
  plan **byte for byte** (plan_design / plan_images / plan_mines identical by md5, plan.json identical apart from
  `plan_seconds`; checked in a scratch folder, the real `v2_3000` was never rewritten).
- `wide`: output `output_dataset/v2_3000_wide`, `SCALE_EDGES = geomspace(0.1, 0.4, 6)` (0.1, 0.132, 0.174, 0.230,
  0.303, 0.4), `N_MINES` 0..8 with quotas 600 / 300 x 8, `OUTPUT_CROP (960, 960)`, `SCENE_ZOOM_COUPLING False`.
  It has its own seed namespace (`render_scene(seed=2027, index=k)`, plan seed 20261021) and file prefix `v2w_`,
  so no file name or image is shared with the zoom640 set. Retries use the same rule (index 100000 + 10 k + attempt).
  The generator itself is unchanged: `OUTPUT_CROP` already worked without zoom coupling.
- **Crowding.** Up to 8 mines of up to 171 px must fit in the 944x944 placement region (960 minus the 8 px margin).
  The generator's rejection sampling (50 attempts per mine, boxes inflated by 10 px, a mine that cannot be placed is
  dropped) is kept. New `--placement-check` replicates the placement **exactly** (same cfg, sun, crop window, per-mine
  silhouette from `objects.Mine`, same draws; nothing drawn) for every row with >= 2 mines and writes
  `plan/placement_check.json`:
  - 0 of 10500 mines dropped, in 0 images. The most attempts any mine needed was 7 of 50, and a 500-attempt run also
    drops 0.
  - The silhouette boxes cover on average 5.0 % of the crop at 8 mines, and at most 12.7 % in any image. The
    rule keeps boxes apart, so mines never overlap one another.
  - Rocks and clippings in the over-layer can still lie on a mine, as in every v2 dataset.
- `--verify-plan` now also checks the replicated placement against the render: number placed and every full-frame
  rectangle. It also checks that each silhouette box lies inside the crop, the crop size, the JPEG quality, and that no
  `zoom` block is present when coupling is off. Rows are picked to mix mine counts and scale bins.

### Plan stats (`--variant wide --plan-only --placement-check`, then `--verify-plan 6`)

- 3000 images, 10800 mines (3775 buried), train 2700 / val 300.
- Pairwise chi-square 268.97 → 0.26 (largest single pair 0.10). Split chi-square 30.58 → 0.29.
- n_mines 600 / 300 x 8 (val 60 / 30 x 8). Scale bins 600 each (val 60), 2160 mines each.
- Burial 750 x 4. Elevation 500 x 6. Light 450 / 638 / 638 / 637 / 637. Family 1950 / 1050 (val 194 / 106).
  PSF 1000 x 3.
- 97 background files, with grass1 and grass2 excluded. Mine length 43-171 px (median 86).
- `--verify-plan 6` covered rows (bin, mines) (4, 8), (0, 0), (1, 7), (2, 5), (3, 3) and (4, 1): 0 mismatches
  (11-67 checks per row), 0.4-1.7 s per image in a single process.
- An 8-image trial render with `--render --workers 2` into a scratch folder gave 960x960 JPEGs, seed 2027 and
  `v2w_` names, with no failures.

### Review sheet

`docs/wide_look.png` (`scripts/wide_look_sheet.py`) shows 8 plan rows at full size, covering every scale bin and
1-8 mines, grass and non-grass, with boxes.

- All 41 planned mines are placed and labelled. No box touches the crop edge and no mines overlap.
- Bins 3-4 (128-166 px) are clearly visible.
- Bins 0-1 (44-72 px) are small and often well camouflaged. Some are hard to find without the box, especially buried
  ones on busy gravel, at high PSF, or under overcast light on dark grass. Rocks are often larger than the mines. This
  is the intended "zoomed out" look and the point of the variant.
- Two things carried over from the generator stand out more at this zoom:
  - The fresh "tangle" grass wisps (row 368) look like white synthetic scribbles.
  - Over-layer rocks can sit on a mine (row 18).

### Live view (dataset tab)

- `scripts/serve_dataset_view.py` has a **dataset registry**. Every folder under `--datasets-root` (default
  `output_dataset/`) that has `plan/plan.json` or `images/` can be selected. The list is rescanned at most every 2 s,
  so a new dataset appears without restarting the server.
- The default is the dataset with the newest `plan.json`, which is now `v2_3000_wide`.
- New endpoint `/api/datasets`. Every dataset route takes `?ds=<id>`; an unknown or malformed id returns 404. Card
  URLs carry `ds`. Thumbnails are cached per dataset folder. 960 images are served byte for byte, as 640 images
  already were.
- `--dataset-dir` alone still serves just that folder, as the existing tests expect.
- The tab has a "Dataset" dropdown showing id · variant · size, plus a description line (scale range and bins, mines
  per image, zoom coupling). The choice is remembered in localStorage, and switching does not reload the page.
  Against an older server without `/api/datasets`, the dropdown is hidden.
- The parameters tab has a new comparison table "zoom640 vs wide", built from both plan.json files
  (`build_params.py --patch-variant-table`, no renders). The cards themselves still describe zoom640 only.

## Consequences

- Render: `python3 scripts/generate_dataset.py --variant wide --render --workers 4`. The full 1920x1080 scene is
  still rendered, and there are on average 3.6 mines per image instead of 2. Estimate: about 1-1.3 s per image per
  worker, so roughly 13-17 min with 4 workers (up to about 20 min under load).
- Training needs `--data output_dataset/v2_3000_wide/data.yaml` and imgsz 960. The YOLO scripts in `kernelBashing`
  default to `v2_3000`, so their `make_report.py` dataset root must point at the wide set. Image stems `v2w_NNNNN`
  still end in `_<index>`, which is what `make_report.py` parses.
- The server already running on port 8765 predates the registry and must be restarted to show the dropdown.

## Tests

- `docs/showcase/test_fixture/dataset_switch_test.py` is new, with 31 checks:
  - registry contents and the newest-plan default;
  - `?ds=` routing, 404s, and file and thumbnail routes per dataset;
  - a folder added while the server runs appears;
  - in headless Chrome: the dropdown, 960 square cards, switching to a 640 dataset and to an empty one, and that the
    choice is remembered.
- Existing tests still pass:
  - `run_tests.py`: ALL OK.
  - `chrome_test.py`
  - `dataset_view_test.py`: 59 checks at 1920x1080 and 59 at 960x960.
  - `training_view_test.py`: 64 checks.
- `python3 -m pytest tests`: 11 passed (generator unchanged).

## Commits

None yet (the lead commits).
