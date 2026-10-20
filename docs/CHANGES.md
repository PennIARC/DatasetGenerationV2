# v2 realism features

All settings live in `DatasetGenerator/controlPanel.py`; every feature has its own flag (listed in `V2_FLAGS`).
Setting all flags to False (`main.py --v1`, or `{"v1": True}` in the API) reproduces v1 behaviour: sprite mines,
nearest-neighbour scaling, hard dirt squares, no shadows, v1's post shader (re-implemented in numpy).
Contact sheets: `docs/v1_vs_v2.png`, `docs/mine_crops.png` (row 3 = face-down mines), `docs/ablation.png` (last
row = all features with every mine face down), `docs/rock_shadows.png` (`scripts/visual_check.py`).

Glossary: **alpha** = per-pixel opacity; **premultiplied alpha** = RGB stored multiplied by alpha, so resampling
and blurring never mix the undefined colour of transparent pixels into edges (no halo); **supersampling** =
render at k times the resolution and average down (anti-aliasing); **painter's algorithm** = draw triangles
far-to-near so nearer ones cover farther ones; **Lambert shading** = brightness proportional to cos(angle between
surface normal and light); **Blinn-Phong specular** = small highlight; **penumbra** = soft edge of a shadow;
**ambient occlusion (AO)** = darkening where little sky is visible (contact points); **fBm** = fractal Brownian
motion, smooth noise summed over octaves; **Sutherland-Hodgman** = polygon clipping against a plane; **PSF** =
point-spread function (camera blur kernel); **HSV** = hue (deg), saturation, value (brightness).

## 1. On-the-fly mine rendering (`MESH_MINES`)
- **What**: each mine instance is rendered from `assets/mine.stl` (copy of `SpriteGenerator/mine.stl`) with its own
  pose, colour, light, burial and dust. No sprite set; only the colour-free normalised mesh is cached.
- **Distinct instances**: effectively unlimited. Pose (3 continuous angles), scale, HSV colour + bleach / tint /
  brightness, sun direction, burial plane (fraction, tilt, direction) and four 31-bit noise seeds are all
  continuous or 2^31-valued draws per instance; there is no pose or sprite pool.
- **Pose**: yaw U(0, 360). Pitch and roll independently: N(0, `TILT_SIGMA`=5) re-drawn beyond `TILT_CAP`=35, with
  probability `TILT_TAIL_PROB`=0.05 replaced by +-U(`TILT_TAIL_RANGE`=8-30). |pitch| / |roll| percentiles:
  median 3.6, p90 9.5, p99 25.6, max 30 deg (v1: uniform +-20). Recorded per mine in the sidecar.
- **Face down** (`FLIP_PROB` = 0.30, one-line setting): with this probability the mine lies on its back, underside
  towards the camera. The flip is a 180-degree turn about the mine's long (x) axis, followed by a ~1.5 deg
  correction onto the convex-hull face the upside-down mesh actually settles on (from
  `trimesh.poses.compute_stable_poses`), so it rests on the body and a wing tip instead of balancing on the body.
  The tilt distribution above is then applied relative to lying flat on its back, and yaw is uniform as before.
  Sidecar: `face_down` (bool) and `pitch` / `roll` relative to the flat attitude (face up or face down). In the
  50-image sample, 54 of 192 mines (28%) are face down; sample |tilt| p50 / p90 / p99 = 3.4 / 9.6 / 24.9 deg.
  `mine.stl` is closed (watertight, consistent winding) and has a plausible underside: a flat plate with the ends
  of the body tube showing; the silhouette comes out mirrored as expected. Everything downstream is generic in the
  rotated mesh (lowest point = ground contact, normals vs. sun, shadow projection, burial plane quantile, soil lip,
  visible-mask labels), so it works unchanged for face-down mines (checked visually at several yaws, with and
  without burial).
- **How** (`features/mesh.py`): mesh normalised to longest side 1 and rotated (extrinsic xyz Euler), orthographic
  top-down camera. Triangles facing the camera are filled far-to-near (painter's algorithm, `cv2.fillConvexPoly`
  with 4 sub-pixel bits) into a triangle-ID buffer; colour, coverage and surface height are looked up per pixel from
  the ID. Scale: `MINE_PX_PER_UNIT` = 426.7 px per mesh unit at scale 1, the same as v1's sprites, so
  `MINE_SCALE_MIN/MAX` keep their meaning (mine length 43-171 px at 1080p).
- **Shading**: Lambert + ambient + Blinn-Phong specular from the image's sun, tied to the shadow strength s:
  gain = (1 - s) + s * min(n.L / sin(elevation), `SHADE_MAX_GAIN`). A horizontal face in sun has gain 1 (like the
  photographed ground), a face turned away is exactly as dark as the cast shadow. Rotating a mine therefore rotates
  it relative to the light correctly.
- **Limitations**: flat shading per triangle (the STL is faceted); no self-shadowing between the body and wings;
  a tilted mine rests on its single lowest point (no physical settling beyond the two stable flat attitudes);
  the face-down mine props its wing up on the body, so its shadow is longer than a face-up mine's (physically
  plausible for a rigid PFM-1);
  plastic texture/moulding detail is not modelled; ~35-60 ms per mine.

## 2. Soft edges (`SOFT_EDGES`) and blur (`BLUR`)
- **What / why**: v1 scaled with nearest neighbour and rotated twice (in the sprite and at placement), producing
  jaggy, hard edges that are a giveaway. v2 renders at `SUPERSAMPLE`=4x and area-averages once (alpha = sub-pixel
  coverage, RGB premultiplied), so there is a single resample and no colour bleeding. Rocks / grass / dirt cut-outs
  are resampled the same way (area downscale on premultiplied RGBA, bilinear rotation, `DEBRIS_ALPHA_FEATHER`=0.8 px
  feather, 1-px erosion of Otsu masks to drop white-background rims) so mines are not the only soft objects.
- **Blur**: after compositing, the whole image gets a Gaussian PSF with sigma U(`PSF_SIGMA`=0-1.5) px and, with
  probability `MOTION_BLUR_PROB`=0.15, a line-shaped motion blur of U(1-4) px at a random angle.
- **Code**: `features/edges.py` (`resize_rotate`), `features/camera.py` (`apply_blur`).
- **Limitations**: blur is spatially uniform (no depth of field variation); motion blur is linear.

## 3. Cast shadows (`SHADOWS`)
- **Sun** (`features/sun.py`): one per image. Azimuth U(0, 360); with prob 1 - `OVERCAST_PROB` (0.85) direct sun:
  elevation U(`SUN_ELEVATION`=15-70), strength U(`SHADOW_STRENGTH`=0.25-0.65); otherwise overcast: strength
  U(`OVERCAST_SHADOW_STRENGTH`=0.03-0.15) and penumbra x`OVERCAST_PENUMBRA_SCALE`=6 (weak, very soft).
- **Mines**: all (clipped) triangles are projected along the sun direction onto the soil plane and filled
  (orthographic projection, union) -> the true silhouette, at the same supersampling. Penumbra = Gaussian, sigma =
  (`PENUMBRA_BASE_PX` + `PENUMBRA_PER_LENGTH` x shadow length) x overcast scale, so low sun -> long, softer shadows.
  Contact AO: blurred footprint x U(`CONTACT_AO_STRENGTH`). Ground is multiplied by 1 - s x coverage x (1 + t/2, 1,
  1 - t) with cool tint t ~ U(`SHADOW_COOL_TINT`=0-0.15).
- **Rocks, grass, dirt snippets, sprite mines**: 2D approximation with the same sun and strength: the alpha
  silhouette is swept away from the sun by height / tan(elevation) (grey-scale dilation with a line kernel) and
  blurred by the same penumbra rule. Heights: grass / leaves 0.02-0.08 of their width (shadow x
  `GRASS_SHADOW_SCALE`=0.6), dirt clods `CLOD_HEIGHT_FRAC` 0.05-0.15, grass blades / tufts / wisps from
  `*_HEIGHT_MM`. Rocks are rotated so their photographed bright side faces the sun (`ROCK_ALIGN_LIGHT`, +-30 deg),
  so baked-in lighting does not contradict the shadows.
- **Seating rocks on the ground** (user request; `docs/rock_shadows.png` shows shadows off / contact only / full
  at sun elevation 18, 35 and 65 deg):
  - `ROCK_CONTACT_SHADOW`: soft contact shadow / AO under rocks, dirt clods and leaf clumps
    (`CONTACT_SHADOW_KINDS`): the alpha is dilated, Gaussian-blurred by U(`ROCK_CONTACT_WIDTH_FRAC`=0.04-0.12) x
    object width, shifted `ROCK_CONTACT_OFFSET_FRAC`=0.03 x width away from the sun, and darkens the ground by
    U(`ROCK_CONTACT_STRENGTH`=0.2-0.5) x clip(image shadow strength / 0.45, 0.35, 1.3), so overcast images keep a
    weaker contact shadow. Leaf clumps get half strength.
  - Cast shadow (`ROCK_CAST_SHADOW`; False = contact shadow only): rock height `ROCK_HEIGHT_FRAC`=0.1-0.35 of the
    width, scaled down to 50% for the smallest rocks (`ROCK_SMALL_HEIGHT_SCALE`) and halved again for gravel
    snippets (`ROCK_GRAVEL_HEIGHT_SCALE`); length capped at `ROCK_SHADOW_MAX_LENGTH_FRAC`=0.8 x width (no smears at
    low sun); penumbra sigma = 0.6 + `ROCK_PENUMBRA_PER_LENGTH`=0.15 x length.
  - `ROCK_RIM_BLEND` (rocks, clods; `RIM_BLEND_KINDS`): within a `ROCK_RIM_BAND_PX`=1.5 px rim the colour is mixed
    U(`ROCK_GROUND_TINT`=0.1-0.35) towards the local ground colour, and the rim on the side away from the sun is
    darkened by U(`ROCK_RIM_DARKEN`=0.15-0.35) x shadow strength / 0.45 (a thin self-shadow line). The 0.8 px alpha
    feather (`DEBRIS_ALPHA_FEATHER`) is unchanged.
- **Why rocks too**: otherwise "has a shadow => mine" becomes a shortcut.
- **Limitations**: the background photos have their own baked shadows in arbitrary directions; mine shadows fall
  on a flat (or the tilted burial) plane, not on rocks or grass relief; the PFM-1 wings are thin, so mine shadows
  are mostly cast by the body and stay small (physically right).

## 4. Soil blending (`SOIL_BLEND`)
- **What** (`features/soil.py: soil_blend`): before the mine is drawn, the composite under it is sampled.
  (a) exposure harmonisation: mine x (local luminance / image luminance)^0.5 x (image luminance / 0.4)^0.5,
  clipped to 0.6-1.6; (b) dust layer coloured by the local ground blurred at 0.25 x mine length, opacity =
  triangular(`DUST_STRENGTH`=(low 0.25, mode 0.30, high 0.50); mean 0.35, user decision) x fBm noise (feature size 0.15-0.5 x mine length); (c) contact band of
  U(1.5-4) px inside the silhouette edge, darkened by 10-30% and dustier; (d) soil grains: thresholded fine noise
  covering 0-5% of the mine, coloured from the local ground (replaces v1's hard brown dots).
  v1's hard ground dirt squares become soft irregular grains tinted by the local ground (`dirt_grain`).
- **Limitations**: dust is a 2D overlay (no accumulation in crevices); no wetness / mud.

## 5. Partial burial (`BURIAL`, needs `MESH_MINES`)
- **What**: with probability `BURIAL_PROB`=0.35 a fraction U(`BURIAL_FRACTION`=0.05-0.5) of the mine's top-down
  area is buried (hard cap `BURIAL_MAX_FRACTION`=0.5; every mine stays visible and always gets a box).
- **How** (`features/mesh.py`): a soil plane tilted U(`BURIAL_TILT`=0-25) deg in a random direction. Because the
  top-down visible surface is a height field, the plane offset is the burial-fraction quantile of n.p over the top
  surface points (from a low-res depth render), which hits the target area exactly. The 3D triangles are then
  clipped against the plane (Sutherland-Hodgman) and the clipped mesh is rendered and shadow-projected onto that
  plane. `soil.burial_overlay` adds a rough soil line (surface within fBm x `SOIL_EDGE_NOISE` of the plane is
  covered) and a berm (soil lip, `BERM_WIDTH_PX` 2-6, irregular width) in the local ground colour, darkened
  by `BERM_DARKEN`. If the soil line pushes the hidden area past the cap, it is shrunk (up to 4 times).
  Achieved fraction is recorded (`burial.achieved`).
- **Fixes (user feedback on the showcase)**: (a) the soil lip is drawn only along the TRUE soil line (where the
  still-visible mine meets the soil-covered part); before, it was measured from the whole buried region and so also
  left a 1-2 px band along the original, unburied outline. (b) burial no longer moves the mine: placement uses the
  bbox of the UNCLIPPED silhouette, the canvas origin is snapped to whole pixels relative to the unclipped mesh (same
  sub-pixel phase / anti-aliasing with or without burial, whatever the shadow extent), and the dust / grain noise is
  computed on the unclipped silhouette's box, so burial on / off differ only in the buried part, the soil overlay and
  the shadow. Regression test: `tests/test_burial.py` (5 seeds / poses incl. face down: anchor offset 0 px, every
  buried-mine pixel inside the unburied silhouette, label box inside the unburied box). Before / after:
  `docs/burial_fix.png` (`scripts/burial_fix_figure.py`). The irregular soil line on the gravel example (buried part
  in the middle, ragged edge) is unchanged. If the rough soil line would push the hidden area past the 50% cap even
  after shrinking it 4 times, soil is kept off the visible mine (200-image check: max achieved 0.50, 255 buried mines).
- **Slivers / fragments (second round of user feedback)**: a thin wing rim grazed by the clip plane could leave a
  1-4 px diagonal line and a detached wing-tip island. Now, after the clip, after the soil line and for the final
  label mask, the visible mask is cleaned (`features/burial_fx.clean_mask`): morphological opening with radius
  r = max(`BURIAL_OPEN_PX`=1, `BURIAL_OPEN_FRAC`=0.025 x mine length) removes strips thinner than ~2r px, and visible
  islands smaller than `BURIAL_MIN_FRAGMENT_FRAC`=0.06 of the full area are dropped (the largest part always stays);
  what is removed counts as buried and is covered by soil. Regression test (in `tests/test_burial.py`, 9 seeds /
  poses incl. face down): no visible component below the minimum area, every component keeps >= 70% under a 3x3
  opening (no line-like parts), < 6% of the visible pixels are 1-2 px structures.
- **Soil-displacement cues** (`features/burial_fx.py`; strength scales with s = clip(burial fraction / 0.4, 0.25,
  1.25), subtle for small burials, clear at 40-50%). Before / after: `docs/burial_realism.png` (gravel, dark grass,
  light dry grass, bare soil, face down, low / high sun; columns burial off, old 40%, new 40%, new 40% with blades).
  Turned soil takes a brown soil tone (`BURIAL_SOIL_RGB`, mixed in by `BURIAL_SOIL_MIX`=0.3-0.75, more on green
  ground, brightness from the local ground) so digging into a lawn exposes earth, not grass.
  - `BURIAL_BERM`: a raised, clumpy ridge along the clip line (width `BERM_RIDGE_WIDTH_FRAC`=3-8% of the mine
    length, irregular, fBm clumps), sitting on the soil side and lapping onto the mine by ~25% of its width,
    shaded by the sun from its height field (`BERM_RIDGE_SHADE`=0.35: lit slope lighter, far slope darker) and
    casting a short shadow (height `BERM_RIDGE_HEIGHT_FRAC`=2-5% of the length) onto the mine and the ground.
  - `BURIAL_DISTURBED_SOIL`: a darker, rougher, slightly browner turned-soil patch on the ground around the buried
    part (`DISTURBED_RADIUS_FRAC`=0.08-0.2 of the length, noise-modulated edge, opacity 0.35-0.65, darken 0.72-0.88,
    desaturate 0.1-0.3), drawn under the mine and its shadow.
  - `BURIAL_CLODS`: `BURIAL_CLOD_COUNT`=3-9 (x s) clods from `assets_new/dirt` (clod snippets, audit-filtered),
    3-9% of the mine length, coloured towards the turned soil (`BURIAL_CLOD_COLOUR_ADAPT`=0.85), scattered along
    and over the soil line (some on the mine) with small sun-consistent shadows.
  - `BURIAL_DIRTY_EXPOSED`: the exposed part gets an occlusion gradient at the soil line (`EXPOSED_AO_PX`=2-6 px,
    strength 0.25-0.45), is darker (5-15%) and less saturated (10-25%), and carries grains, thin streaks and a dusty
    film (`EXPOSED_GRAIN_DENSITY`, `EXPOSED_STREAKS`, `EXPOSED_FILM`) whose density rises towards the buried side.
  - Hidden fraction: the clip plane now hides `BURIAL_CLIP_SHARE`=0.85 of `BURIAL_FRACTION`; the rough soil line,
    ridge and clods hide the rest. If ridge / clods would push the hidden area past the 50% cap, they are still
    drawn but count for the label mask with the largest weight that keeps the cap (bisection). Sidecar:
    `burial.hidden_by_stage` (clip, soil_line, fragments, final), `burial.realism` (all sampled cue parameters),
    `burial.scale`, `burial.cap_exceeded`. 50-image sample: 63 buried mines, max hidden 0.50, cap never exceeded.
- **Blades over buried mines** (`BLADE_SOIL_LIFT`, `BLADE_EMERGE`): every over-layer blade / tuft / wisp that
  crosses a buried mine's soil-line zone is warped (cv2.remap with a smooth weight around the clip line): its pixels
  are lifted by up to ~4% of the mine length (1.5-6 px) towards the sun side (away from the shadow direction), a soft
  shadow is left where it would have lain, and the lifted segment is brightened slightly. Parts lying on the
  soil-covered region are partly covered by soil (`BLADE_EMERGE_COVER`=0.6, noise-modulated), so they look rooted /
  emerging. Pool blades are also capped in width (`BLADE_WIDTH_MM` max; tufts / wisps 3x) so no flat, wide strips.
- **Limitations**: the soil plane is a plane (no local relief); no soil spilled onto the wings away from the line;
  where the tilted plane runs close to a low wing rim, the noisy soil line can cover a thin strip of that rim.

## 6. Colours (`COLOUR_PALETTE`), photometric jitter (`PHOTOMETRIC_JITTER`), backgrounds (`BG_AUGMENT`, `NEW_ASSETS`)
- **Palette** (`features/colour.py`), HSV ranges and weights (H deg, S, V):
  olive_drab 0.28 (55-85, 0.30-0.60, 0.22-0.45); dark_green 0.22 (85-160, 0.30-0.65, 0.15-0.40);
  khaki 0.15 (40-58, 0.22-0.45, 0.42-0.70); brown 0.20 (18-38, 0.35-0.65, 0.18-0.45);
  tan 0.15 (26-45, 0.18-0.40, 0.50-0.78). Then sun-bleaching with prob 0.35 (amount a ~ U(0, 0.6):
  S x (1 - 0.6a), V + 0.3a(1 - V)), dirt tint with prob 0.4 (mix up to 30% towards RGB (0.42, 0.33, 0.22)) and a
  brightness factor U(0.85, 1.15). Hue covers ~18-160 deg continuously and V 0.15-0.78 so no single colour is a
  shortcut; arbitrary hues are excluded (user decision). In a 50-image sample: olive 62, dark green 36, brown 37,
  khaki 30, tan 27 mines.
- **Photometric** (`features/camera.py`, per image): exposure U(0.75-1.25), gamma U(0.85-1.15), white-balance R and
  B gains U(0.92-1.08), saturation U(0.75-1.25), contrast U(0.95-1.2), Gaussian noise sigma U(0-0.025) with 0-50%
  colour noise, chromatic aberration U(0-0.002) of the width, vignette U(0-0.5), JPEG quality U(70-95).
  Off: v1 shader (grain U(0.05-0.12) that only survives in G, 3.8 px aberration, vignette 0.4, contrast 1.1,
  JPEG 85).
- **Backgrounds** (`features/background.py`): flips (p 0.5 each), rotation by a random multiple of 90 (p 0.5),
  zoom U(1-2) on top of scale-to-cover, hue shift +-8 deg, saturation 0.8-1.2, brightness 0.8-1.2, channel gains
  0.95-1.05.
- **Background sampling** (`BG_USE_INDEX`, with `NEW_ASSETS`): `assets_new/backgrounds_index.json` lists 119
  backgrounds (15 v1 + 104 new; 114 with weight > 0) with family (grass / non_grass), category (grass_fresh,
  grass_olive, grass_dry, grass_patchy, moss_clover, soil, gravel, sand, mixed_ground) and weight. A family is
  drawn by `BG_FAMILY_WEIGHTS` (None = the file's {grass 0.65, non_grass 0.35}), then an item of that family with
  probability proportional to its weight (0 = never). 500 drawn images: 353 grass (70.6%; expected 65%, binomial
  sd 2.1%), 147 non-grass; 435 new and 65 v1 photos. `BG_USE_INDEX=False` restores folder sampling
  (`BACKGROUND_SOURCES`); `NEW_ASSETS=False` = the 15 v1 photos (v1 mode). The sidecar records the path (relative
  to the repo), family and category.
- **Asset audit filter** (`ASSET_AUDIT_FILTER`, in V2_FLAGS, so `v1` mode switches it off and reproduces v1
  exactly, watermarked files included): reads `docs/asset_audit/exclude.json` (`ASSET_AUDIT_PATH`); files in
  `hard_exclude` (6 v1 backgrounds with stock-photo watermarks or unusable, v1 grass snippets debris1 / debris2) are
  never sampled, files in `review` (69) get weight x `ASSET_REVIEW_WEIGHT`=0.4. Matched by file NAME (assets moved to
  a `_rejected/` folder keep matching; missing files are simply not listed; loaders never recurse into
  `_rejected/`). Applies to folder sampling (backgrounds, rocks, v1 grass snippets, leaf clumps, dirt: weighted file
  choice inside a folder, empty folders drop out and the folder weights renormalise) and to the background index
  (item weight x audit weight; the family is still chosen first, so grass / non_grass stay 65 / 35). After the
  filter the index has 77 grass and 22 non-grass usable backgrounds (9 of the 15 v1 photos). 500 seeds:
  grass share 65.6%, 93 distinct backgrounds, 2.2% 'review' backgrounds; rocks 46 distinct (16% review), leaf clumps
  21, dirt 30; v1 grass snippets: only debris3-5 remain (all 'review', so within that folder they are equally
  likely). Sidecar: `background.audit` ('ok' | 'review') and per rock `[cx, cy, width, layer, audit, file]`.
  Test: `tests/test_asset_audit.py` (no hard-excluded or `_rejected/` file in 500 seeds per kind and for the
  backgrounds exactly as render_scene draws them; v1 mode still samples the original set).
- **Background weight overrides** (`BG_WEIGHT_OVERRIDES`, generator side; assets_new is not edited): the
  posterised / blocky look reported in a v2 contact-sheet image comes from the assets, not the pipeline. Evidence:
  (a) the pipeline is float32 from decode to the final rounding, and the output histogram has no empty bins in the
  dark range even at max exposure 1.25 x contrast 1.2 without noise (no posterisation from gamma / contrast); a
  full-resolution crop of the rendered dark area is smooth before and after our JPEG (q93); (b) the source files
  carry 8x8 JPEG blocking inside their dark, multiplied "patchiness" regions. Blockiness (mean step across 8-px
  block borders / mean step inside blocks, dark areas only) over all 119 backgrounds: median 1.06;
  `bg_real_08_Grass008_grass_olive.jpg` 1.90, `bg_real_07_Grass007_grass_patchy.jpg` 1.37,
  `bg_real_06_Grass007_grass_dry.jpg` 1.22 (all others <= 1.15 except a v1 photo with a tiny dark area). The dark
  multiplied blobs also flatten the grass texture. These three are down-weighted to 0.25 / 0.25 / 0.5 until S2
  regenerates them (re-encode at higher quality or apply the patchiness in float before saving).
- **New leaf-litter clumps** (`LEAF_CLUMPS_NEW`, needs `NEW_ASSETS`): the RGBA clumps from
  `assets_new/grassDebris` are no longer mixed into the v1 grass clippings (`GRASS_SOURCES` = v1 folder only, v1
  counts unchanged). Own layer: `LEAF_CLUMPS_UNDER`=2-8 + `LEAF_CLUMPS_OVER`=0-2 per image (sample: 2-10, median
  6.5), `LEAF_CLUMP_SIZE`=25-60 px, source weights `LEAF_SOURCES`; colour pulled towards the local ground
  (`LEAF_COLOUR_ADAPT`=0.7), desaturated U(`LEAF_DESATURATE`=0.3-0.5) and darkened U(`LEAF_DARKEN`=0.3-0.5); half-
  strength contact shadow, short cast shadow and rim blend.
- **Other new assets** (`NEW_ASSETS`): `assets_new/rocks` (34 RGBA stones / gravel), `assets_new/dirt` (29 soft-edged snippets classified by `dirt/index.json`: clods =
  raised lumps with cast + contact shadow and opacity 0.9-1.0; patches / dust = flat overlays with their per-file
  opacity range, no shadow, colour pulled towards the local ground by `DIRT_PATCH_ADAPT`=0.5;
  `DIRT_SNIPPETS_PER_LAYER`=2-10, `DIRT_SNIPPET_SIZE`=15-60 px). Cut-outs may be v1 photos on white (Otsu) or RGBA
  PNGs with real alpha (detected automatically, never Otsu-thresholded); unreadable files are skipped.
- **Grass blades** (`GRASS_BLADES`, needs `NEW_ASSETS`; `features/blades.py`): a separate layer of thin blades,
  tufts and dry wisps (`BLADE_KIND_PROBS` 0.6 / 0.25 / 0.15), `BLADES_UNDER`=20-80 drawn before the mines and
  `BLADES_OVER`=15-60 after them at random positions (they partially occlude mines; the visible-mask labels account
  for it), plus `BLADES_OVER_ON_MINE`=0.6: per mine, with that probability `BLADES_ON_MINE_COUNT`=1-4 extra
  over-layer blades / tufts / wisps centred in the mine box expanded by `BLADES_ON_MINE_EXPAND`=0.2 per side. 200-image
  check: 59% of mines get targeted blades, 65% have >1% of their area covered by overgrowth; mean overgrowth-covered
  fraction 0.10 (0.14 for targeted mines); mean visible fraction 0.79 (p5 0.42); all 692 mines boxed (12 with < 30%
  visible). Sidecar per mine: `blades_on_mine`, `overgrowth_occluded_fraction`. Sizes are in
  mm (`BLADE_SIZE_MM` 40-160 long, `BLADE_WIDTH_MM` 2-5 wide, `TUFT_SIZE_MM`, `WISP_SIZE_MM`) converted with a
  per-image px/mm drawn from the mine scale range (0.36-1.42 px/mm, recorded as `ground_px_per_mm`), so blades are
  1-7 px wide. Sources: fresh blades from `assets_new/tools/make_grass_blades.py` (imported in a try/except; with
  prob `BLADE_FRESH_PROB`=0.5, at most `BLADE_MAX_FRESH_PER_IMAGE`=3 per image because each costs 15-100 ms; wisps
  use all `WISP_KINDS` strands / curved / tangle / stubble / hair) and the 135-file PNG pool
  `assets_new/grassBlades` rescaled and rotated per instance. Colour: rgb x (local ground colour / blade colour) **
  `BLADE_COLOUR_ADAPT`=0.5 (green on lawns, straw on dry ground) x brightness U(0.85-1.1). Shadows: 2D swept
  silhouette, heights `BLADE_HEIGHT_MM` 0.5-4, `TUFT_HEIGHT_MM` 8-30, `WISP_HEIGHT_MM` 0.5-4, x 0.6 strength.
- **Limitations**: no sensor-specific noise model (Poisson / banding); colour jitter is global per image.

## 7. Flags, labels and sidecar JSON
- Flags (`V2_FLAGS`): `ASSET_AUDIT_FILTER, NEW_ASSETS, LEAF_CLUMPS_NEW, GRASS_BLADES, MESH_MINES, SOFT_EDGES, SHADOWS, SOIL_BLEND, BURIAL, COLOUR_PALETTE,
  PHOTOMETRIC_JITTER, BLUR, BG_AUGMENT, LABEL_VISIBLE_MASK`. Sub-switches (not in V2_FLAGS, default on): `BG_USE_INDEX`,
  `ROCK_ALIGN_LIGHT`, `ROCK_CONTACT_SHADOW`, `ROCK_CAST_SHADOW`, `ROCK_RIM_BLEND`. Features that need the mesh
  (burial, palette, mesh shadows) are skipped or approximated when `MESH_MINES` is off.
- Labels: with `LABEL_VISIBLE_MASK` the box is the bounding box of mine pixels with alpha > 0.5 after burial soil
  and overgrowth occlusion; a mine with fewer than `LABEL_MIN_VISIBLE_PX`=1 visible pixels gets no box (2 of 192
  mines in an earlier sample were fully hidden by overgrowth). v1 used the un-occluded sprite mask. With the blade
  layer on, the current 50-image sample has visible fraction p5 / p25 / p50 = 0.50 / 0.69 / 0.95; all 192 mines are
  boxed, 5 of them with less than 30% visible.
- Sidecar `output_dataset/meta/train_XXXXX.json`: seed, flags, sun (azimuth, elevation, overcast, shadow strength,
  tint), background (path, family, category, flips, rotation, zoom, colour jitter), ground_px_per_mm, rocks
  ([cx, cy, width, layer]), debris_counts (per layer and kind: rock, leaf, grass, blade, tuft, wisp, dirt_clod,
  dirt_patch, dirt_dust, rect), per mine (scale, pitch / roll / yaw, colour RGB +
  HSV + family / bleach / tint, burial (target, achieved, plane tilt, edge noise, berm), soil blend (dust strength,
  harmonise gain, band, grains), shadow (length, penumbra sigma, AO), face_down, visible fraction, box), camera (blur sigma,
  motion blur, photometric parameters, JPEG quality).

## 8. Python API (headless, deterministic)
Put `DatasetGenerator/` on `sys.path`.
```python
from scene import render_scene
from features.camera import jpeg_roundtrip
rgb, labels, meta = render_scene(seed=3, overrides={"shadows": False, "sun_elevation": 20,
                                                    "burial_prob": 1.0, "n_mines": 1})
# rgb: uint8 (1080, 1920, 3) RGB before JPEG; labels: [[0, xc, yc, w, h], ...]; meta: sidecar dict
saved_look = jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"])
```
- Overrides: any controlPanel name, case-insensitive; a scalar for a (min, max) range fixes it. Extras:
  `"v1": True` (all flags off), `"only": ["MESH_MINES", "SHADOWS"]` (only these on), `"mine_scale": 0.3`,
  `"flip": True`.
- Controlled comparisons: `N_MINES`, `MINE_POSE` (pitch, roll, yaw) or (pitch, roll, yaw, face_down),
  `FLIP_PROB` (or `"flip": True / False` = every mine face down / face up), `MINE_POSITIONS` [(cx, cy), ...] box
  centres, `MINE_COLOUR` (r, g, b in [0, 1]), `overcast_prob: 0`, `sun_azimuth`, `sun_elevation`, `burial_prob`,
  `burial_fraction`, `psf_sigma`, `exposure`, ...
- Assets / debris toggles: `grass_blades`, `blades_under` / `blades_over` (count ranges, e.g. (0, 0)),
  `burial_berm`, `burial_disturbed_soil`, `burial_clods`, `burial_dirty_exposed`, `blade_soil_lift`, `blade_emerge`,
  `burial_min_fragment_frac`, `burial_open_frac`, `burial_open_px`, `burial_clip_share`, `berm_ridge_width_frac`,
  `berm_ridge_shade`, `disturbed_radius_frac`, `disturbed_opacity`, `burial_clod_count`, `exposed_ao_strength`,
  `exposed_film`, `burial_soil_rgb` (old-style burial for comparisons: set the four BURIAL_* cue flags and the two
  blade flags False, `burial_min_fragment_frac=0`, `burial_open_px=0`, `burial_open_frac=0`, `burial_clip_share=1`),
  `blades_over_on_mine` (probability per mine, 1.0 = every mine), `blades_on_mine_count`, `dust_strength` (scalar
  fixes it; or a (low, mode, high) triangle),
  `blade_size_mm`, `blade_width_mm`, `blade_colour_adapt`, `blade_fresh_prob`, `blade_max_fresh_per_image`,
  `bg_use_index`, `bg_family_weights` (e.g. {"grass": 1.0, "non_grass": 0.0}), `bg_weight_overrides`
  ({file name: weight}), `new_assets`, `leaf_clumps_new`, `leaf_clumps_under` / `leaf_clumps_over`,
  `leaf_clump_size`, `leaf_colour_adapt`, `leaf_desaturate`, `leaf_darken`,
  `rock_contact_shadow`, `rock_cast_shadow`, `rock_rim_blend`, `rock_contact_strength`, `rock_height_frac`,
  `asset_audit_filter`, `asset_review_weight`, `asset_audit_path`,
  `rock_align_light` (set False to keep rock rotations identical between shadow on / off renders).
- Every subsystem draws from its own stream seeded by (seed, index, k) and each mine has sub-streams (pose, colour,
  burial, soil, shadow ...), so toggling one flag leaves the rest of the scene identical: before / after pairs on the
  same seed differ only by that feature. Same seed + overrides -> bit-identical output.
- Feature functions (`features/`): `sun.sample_sun`; `mesh.sample_pose` (-> pitch, roll, yaw, face_down),
  `sample_burial`, `render_mine` (pose may carry face_down), `face_down_base`;
  `colour.sample_colour`, `colour_from_params`; `shadows.mine_shadow`, `debris_shadow`, `contact_shadow`;
  `soil.soil_blend`, `burial_overlay`, `dirt_grain`; `edges.resize_rotate`, `rim_blend`;
  `blades.make_blade_elements`, `adapt_colour`; `background.pick_background`; `camera.sample_camera_params`, `apply_camera`,
  `apply_blur`, `jpeg_roundtrip`; `background.sample_background_params`, `make_background`. Each `sample_*` takes
  `(rng, cfg)` (cfg from `config.make_config(overrides)`) and returns a plain dict; the apply / render functions are
  deterministic given that dict, so hand-picked values can be passed in.

## 9. Speed (20 images, 1080p, single process, Apple Silicon, numbers from this machine)
| generator | s / image |
|---|---|
| v1 (original, pygame + moderngl) | 0.49 |
| v2, all features (before new assets / blades) | 0.64 (1.3x v1) |
| v2, all features incl. blades, new assets, rock seating, leaf clumps, blades on mines, audit filter | 0.93 (1.9x v1) |
| v2, + burial soil-displacement cues | 1.01 (2.1x v1) |
| v2 engine, `--v1` | 0.33 |
`--workers N` parallelises (50 images with 4 workers: 0.32 s / image wall clock). The extra time is mostly the
on-the-fly blades (capped at 3 per image), ~100 more debris elements with shadows, and the soft dirt grains.
