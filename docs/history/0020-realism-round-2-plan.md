# 0020 - Realism round 2: plan (2026-10-21)

Request: `feedback/0109-realism-round-2-request.md` (verbatim).

## Evidence (4 Opus image-inspection agents + 4 Sonnet research agents)
Note: 3 of the 4 research reports were written from memory without web searches; links/licences are unverified.

- **Shadows (53 mines):** shadow far darker than the photo's own shadows in 29/53 (cast x AO x contact ring multiply; median factor ~0.30 vs photo p5/p50 0.5-0.8); hard 3-8 px "sticker" edge at sun >40 deg (~15/22); symmetric dark outline on the sun side 25/53; light gap between mine and shadow 15/53 (soil_blend samples `local` before the shadow is drawn); shadow bluer than photo shadows 31/53 (`SHADOW_COOL_TINT`); flat "over" debris not darkened by the shadow 8/53; some buried mines have no contact shading 4/21.
- **Assets (1815 pasted elements):** v1 grass clippings median dE 32 vs ground (opaque studio photos, no adaptation); rocks dE 20, no colour adaptation, smoother than ground (sharpness 0.42); blades too saturated on grey/brown ground (~12/40) and float over bare soil (~13/40); no dust/soil at rock base (~34/40); leaf clumps flat dark blobs. Worst backgrounds: gravel, pale/grey ground.
- **Layering:** no rock/mine separation rule. ~13-14% of mines overlap a rock (29% of zoomed images, 47% of wide). Buried mines on rock copy rock pixels as "soil". Label box covers only the visible part; a 96-99% hidden mine still gets a box.
- **YOLO shortcut (run first-10ep):** detector mostly learned "smooth texture-free patch of mine size on textured ground": ground blurred 6 px in mine shape fires 96%, flat blob 100%, rectangle 45%; real ground texture inside the outline drops recall 99% -> 12%. Not the cue: burial edge, noise, JPEG, resampling, shadow without mine. Cause: flat-shaded single-albedo mine mesh, smooth fBm dust, soft grains blurred 5-11 px.

## Decisions (user, /grillMe)
1. Scope: cheap 2.5D now, full 3D rocks deferred.
2. Geometry: wide 960 (same as run 2) for a clean before/after comparison.
3. Cache budget: up to ~5 GB, layered (per background / per asset, never per combination).
4. Label policy: label if >=30% of the mine silhouette visible; 15-30% = ignore region; <15% dropped.
5. Shortcut fix: mine surface texture + ground-matched grain, plus unlabelled smooth decoys in ~30% of images.
6. Issue 1a (user): all mines buried, uniform 10-50%.

## Work plan
A. Placement/layering: place mines first; reject rocks/clods touching a mine silhouette (+2 px), pebbles <0.3x mine length may touch; never bury a mine over rock/clod pixels; flat over-layer debris gets the shadow-factor buffer.
B. Shadows: floor on darkness from the photo (`f >= 0.9 p5/p50`, cached per background); combine cast/AO/contact with max; wider zoom-scaled penumbra fading with distance; contact ring weighted to shadow side; drop cool tint (or per-background shadow colour); re-sample dust band after shadow; minimum shading on buried mines' shadow side.
C. Assets: local-ring LAB colour+saturation match (partial strength, clipped) for blades/rocks/leaves/debris; asset-to-background assignment table (LAB stats nearest-neighbour, sampled with noise); drop or re-cut v1 grass clippings; rocks/debris get immersion (partial burial, dust, soft contact shadow, grain/blur match); blade contact shadows on soil.
D. Shortcut: mine texture (PFM-1 ribbing/bump) + grain matched to ground; smooth decoys; global post-process (re-noise/blur/JPEG round trip) after compositing; random blend modes; perturbation suite as regression test (ground-blob, flat-blob, texture-inside).
E. Caches (<=5 GB): per-background stats (LAB mean/std grid, p5/p50 shadow depth, low-res lighting map, optional Depth-Anything-V2-Small float16 depth, mmap), per-asset LAB stats + compat table, mine renders by pose; zstd/WebP.
F. Then: regenerate 3000-image wide dataset, run 10-epoch YOLO11n (same settings as run 2), compare with the perturbation suite.

Evidence files (scratchpad, not committed): insp_shadow, insp_assets, insp_layering, insp_yolo.
