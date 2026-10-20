# 0016: zoomed 640x640 dataset (native crop, scale 0.25-0.40, scene zoom coupling, 0-4 mines)

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

Status: **plan regenerated, dataset not yet rendered** (the lead starts the render after the user has reviewed
`docs/zoomed_look.png`). Supersedes the format / scale / mines-per-image parts of [0013](0013-dataset-v2-plan.md).

## Context

After looking at the earlier 3000-image plan and render, the user wrote
([feedback/0104](feedback/0104-zoomed-640-dataset-request.md), verbatim):

> we should increase mine size and use 640x640. right now mines are extremely small and often barely visible in the
> generated dataset. we should delete the existing dataset and re-generate with mines at scales between 0.25 and 0.4.
> note that you will likely have to scale other features like rocks, blades of grass, etc. to match the new zoomed in
> look.

Four decisions came out of a short interview, all confirmed by the user:

1. **640x640 via native crop**: render at 1920x1080 as before, then cut a 640x640 window with no resize and no
   resampling. The window must contain every mine, with a margin. Its position is random and otherwise unbiased.
   Labels are converted to the crop's normalised YOLO coordinates.
2. **Mine scale in 4 linear bins over 0.25-0.40**: 750 images per bin, uniform inside the bin. This replaces the
   5 log bins over 0.1-0.4.
3. **Zoom coupling**: rocks, grass, leaf clumps, dirt, debris and other pixel-sized objects get bigger by
   mine_scale / 0.2 per image (0.2 was the old median scale), as if the camera had moved closer. It is a new
   generator flag, off by default, so existing seeds and outputs stay identical. It uses no new draws in existing
   random streams.
4. **0-4 mines per image**: 600 empty images (20 %) and 600 each for 1, 2, 3 and 4 mines. This replaces 0-8.

Everything else in the plan stays as it was: sun, overcast and shadow strata, burial bins, background family and
per-file quotas, PSF bins, the randomized factors, the balanced 2700 / 300 split, JPEG quality sampled 70-95, and
random soft-grain parameters.

## Decision

### Generator (`DatasetGenerator/features/zoom.py`, controlPanel "SCENE ZOOM COUPLING + NATIVE OUTPUT CROP")

- `SCENE_ZOOM_COUPLING` (default False). Per image, z = image_scale / `SCENE_ZOOM_REF_SCALE` (0.2). image_scale is
  the existing R(9) draw that already sets the ground px/mm, and it comes from the image's scale bucket, so
  z = 1.25-2.0.
  - **Scaled by z (physical sizes):**
    - On-screen sizes of rocks, v1 grass clippings, leaf clumps, dirt snippets and ground dirt specks. Their
      cast-shadow heights, contact shadows and rim bands are fractions of the size and follow automatically. The
      rock "small rock" height rule uses the unscaled size, so the shape distribution is unchanged.
    - The mine's pixel-sized details: `CONTACT_BAND_PX`, `BERM_WIDTH_PX`, `EXPOSED_AO_PX`, `CONTACT_AO_SIGMA`,
      `SOFT_GRAIN_BLUR_PX`, the soil-grain fBm size (new `SOIL_GRAIN_PX` = 1.5, previously hard-coded) and the
      placement overlap margin. These were tuned in pixels at a typical mine size. Everything else on the mine
      (shadow length, penumbra growth, contact shadow, burial ridge, clods, dust and soft-grain feature size) was
      already a fraction of the mine length.
    - Grass blades, tufts and wisps are sized in mm and already followed px/mm, so they are not scaled again.
  - **Counts × z^-2** (`SCENE_ZOOM_COUNT_EXP` = 2) for every debris kind in both layers: the density per ground area
    stays the same, which is what "camera closer" means. Counts are rounded stochastically from the new streams
    R(12) and R(13). Blades placed on mines stay per mine.
  - **Background** (`SCENE_ZOOM_BG`): the texture magnification (output px per photo px) is multiplied by z and
    capped at max(`SCENE_ZOOM_BG_MAX_MAG`, uncoupled value), so coupling never zooms less than before. Upscaling
    uses bicubic interpolation.
    - The cap is **1.5**. At 2.0 the review renders showed visibly soft texture on the softer and close-up photos
      (e.g. `grass1.png`, whose grass also looked oversized next to the mine). At 1.5 they stay crisp, and the
      ground-texture scale is already random (BG_ZOOM 1-2) because the photos' real scale is unknown.
    - In the plan the cap binds for 2701 / 3000 images. Median magnification is 1.50. 1366 images are above 1.5
      without any coupling: small or 90-degree-rotated photos, which the generator allowed before and which are
      unchanged.
  - **Kept in pixels (sensor and optics)**:
    - PSF, motion blur, sensor noise, the chromatic-aberration shift and JPEG.
    - The vignette, which acts on the crop as the camera frame.
    - The 0.6 px penumbra base and the 0.8 px cut-out feather. Both are anti-aliasing.
- `OUTPUT_CROP` = (w, h) (default None) and `CROP_MINE_MARGIN` = 8:
  - **Window and placement.** The window position is uniform, from the new stream R(11), and is drawn before the
    mines. `Mine.set_position(region=...)` places each mine's unclipped silhouette box inside the window minus the
    margin, using the same number of draws as before.
  - **Labels.** `Mine.label(crop=...)` counts only mask pixels inside the window. A box crossing the edge would be
    clipped and kept only if it still has `LABEL_MIN_VISIBLE_PX` visible pixels, which is the usual policy. With the
    margin, no box crosses the edge. Boxes are normalised to the crop. The sidecar gains `crop`, and per mine
    `box_px_full` and `rect_full`.
  - **Camera.** `camera.apply_camera_crop` blurs the window plus a context pad, which gives the same result as
    blurring the full frame and then cropping. Noise, colour, contrast and vignette are then applied to the crop.
    The aberration keeps its full-frame pixel shift. Mine exposure harmonisation uses the crop's mean luminance.
  - **No re-rendering.** The full 1920x1080 scene is still rendered. Rendering only the window was optional, and
    the pixels would differ near the edges.
- With both flags off, images, labels and sidecars are bit-identical to the previous generator: checked against a
  HEAD checkout on four seeds, including v1 mode, and pinned by md5 in `tests/test_zoom_crop.py`.

### Dataset driver (`scripts/generate_dataset.py`)

- `N_MINES` uses levels 0..4 with quota 600 each.
- `SCALE_EDGES` = linspace(0.25, 0.40, 5), giving 4 bins of 750 images.
- Every row turns on `SCENE_ZOOM_COUPLING` and `OUTPUT_CROP` (640, 640). JPEG files are written at 640x640.
- The plan replicates z, the crop window, the coupled background zoom and magnification, and the count factor.
  `--verify-plan` now also checks z, the background zoom, the crop window and every label against the full-frame
  pixel box.
- Plan stats:
  - 6000 mines, 2059 of them buried.
  - Pairwise chi-square 197.1 → 0.21; split chi-square 27.2 → 0.22.
  - n_mines × scale is balanced, so each scale bin gets exactly 1500 mines.
- `--verify-plan 8` (2 rows per scale bin): every check matched (19-31 per row), at 0.7-1.3 s per image in a single
  process.

### Showcase and live view

- **Params tab.**
  - Updated cards: mines per image, scale, ground scale, background zoom (coupled magnification), position (inside
    the crop), and the debris cards (counts and sizes × z).
  - New cards: "Scene zoom coupling" (z per image, plus before / after pairs "old look vs zoomed look" and "scale
    0.40 without vs with coupling") and "Native 640x640 crop" (window position, plus render vs saved crop).
  - Before / after pairs now use the dataset's zoom coupling and show native 640x640 windows.
  - The samples are native 640 crops.
  - The decisions table is marked confirmed.
  - The page notes that the dataset is not yet generated.
- **Template.** Before / after sliders, side-by-side frames and live-view cards now take the aspect ratio of their
  image instead of a fixed 16:9. Square images are no longer cropped, so the % boxes on the dataset cards stay
  aligned. Sliders are capped at 75vh.
- **Live-view server.** Images that are already at most 960 px wide are served as thumbnails byte-for-byte, with no
  re-encode, and enlarging shows the native 640 image. The live-view test gained `--size 640x640`.

## Consequences

- `docs/zoomed_look.png` (`scripts/zoomed_look_sheet.py`) shows 8 plan rows: 2 per scale bin, grass and non-grass,
  2-4 mines, buried and unburied.
- The full-frame render is still paid for. Debris counts drop by z^2, so the time per image is similar to before.
- The old 1920x1080 images, labels and meta were deleted by the lead. The stale `manifest.csv`,
  `render_log.json` and `data.yaml` from that render were removed with them. The plan files were replaced.

## Known limitations / open points

- The chromatic-aberration shift stays at up to 3.8 px. On a 640 px frame the colour fringes are clearly visible
  (e.g. row 38 of the review sheet). It is realistic for a cheap lens, but this is the obvious knob if it
  looks too strong.
- Over-layer rocks and clippings can still sit on top of a mine, as in v1 (ADR 0013). Rocks are now drawn z times
  larger, so one can hide most of a mine. The label then shrinks to the visible part.
- Some fresh "tangle" wisps (from `blades.make_wisp`) look like synthetic nets at the larger zoom.
- Backgrounds that were already above 1.5x magnification without coupling (low-resolution or rotated photos) stay
  as soft as they were before.

## Commits

None yet (the lead commits).
