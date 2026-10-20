# 0003: new asset pools (backgrounds, rocks, leaf litter, blades, wisps, dirt)

Date: 2026-10-20 (about 04:18Z-05:10Z = 00:18-01:10 EDT)

## Context

v1 only had 15 backgrounds, 15 rocks and 5 grass snippets. The user asked for more of each, then corrected the first delivery several times by looking at it.

## Decision

A Sonnet agent sourced CC0 (public domain) material from ambientCG into `assets_new/` (attribution in `ATTRIBUTION.md`; the 121 MB of raw downloads are not tracked). First delivery: 44 backgrounds, 30 rocks, 24 grass/leaf debris, 21 dirt patches. User corrections and what each changed:

- "the grass debric that you found is mostly of large sclumps of leaves. we should include individual blades of grass as well (maybe as a separate category)": new `assets_new/grassBlades/` (procedural, tapered curved blades, tufts, wisps; the pool later grew to 135 files) and a separate blade layer in the generator (`GRASS_BLADES`, sizes in millimetres converted with a per-image px/mm). The ambientCG "grass debris" became an own leaf-clump layer (`LEAF_CLUMPS_NEW`, 2-10 per image, desaturated and darkened towards the ground).
- "the majority of your backgrounds are not grass. skew towards 60-70% of the backgrounds being different colors/textures of grass": each background gets a family and category in `assets_new/backgrounds_index.json`, family weights 65% grass / 35% non-grass; 20 real grass/moss mosaics plus 40 procedural lawns added (119 backgrounds, 104 new). Measured over 500 draws: 70.6% grass before the audit, 65.6% after.
- "add more wisps": about 50 dry wisps in total (strands, curved, tangled, stubble, hair).
- "the edges of a lot of the dirt patches are quite sharp. how do you plan on using them?": dirt is used as ground clutter and, later, as clods at burial edges (ADR 0007); alpha edges were feathered 3-12 px with a noise dissolve, stone-like ones moved to rocks, sharp originals kept unused under `dirt/_orig_sharp/`. Result: 30 soft snippets (clods, flat patches, dust).
- "you should also cast soft shadows under rocks so they blend in to the image more": contact shadow / ambient occlusion under rocks, clods and leaf clumps, a capped cast shadow, and a rim blend towards ground colour (`ROCK_CONTACT_SHADOW`, `ROCK_CAST_SHADOW`, `ROCK_RIM_BLEND`; see `docs/rock_shadows.png`).
- Posterised dark patches in some grass backgrounds were traced to 8x8 JPEG blocking baked into three source files (blockiness ratio 1.90, 1.37, 1.22 against a median of 1.06), not to the pipeline. They were first down-weighted through `BG_WEIGHT_OVERRIDES`, then the 20 real-grass backgrounds were regenerated (ratios about 0.99).

## Consequences

- The background pool is mostly synthetic or macro-texture scans: the assistant's own notes say gravel and sand look like close-up textures rather than drone views, procedural lawns lean straw-coloured, leaf litter looks pasted, and v1 photos still look more realistic. New backgrounds were weighted lower for that reason.
- Asset folder about 294 MB including raw downloads.
- This pool then went through the watermark audit (ADR 0004), which rejected more files.
- The user also asked that whenever assets or other generated PNGs for them change they be re-opened; this became a standing rule (ADR 0011).

## Feedback that triggered this

- [0007 HTML showcase request](feedback/0007-html-showcase-request.md) (asks for more backgrounds, grass snippets, rocks, dirt)
- [0008 grass blades category](feedback/0008-grass-blades-category.md)
- [0009 grass background skew](feedback/0009-grass-background-skew.md)
- [0012 show assets](feedback/0012-show-assets.md)
- [0013 wisps and dirt edges](feedback/0013-wisps-and-dirt-edges.md)
- [0014 soft shadows under rocks](feedback/0014-soft-shadows-under-rocks.md)
- [0015 re-open changed visuals](feedback/0015-reopen-changed-visuals.md)

## Commits

- `5f3437e` 2026-10-20 00:34:00 -0400 feat(assets): add CC0 backgrounds, rocks, dirt, grass blades and tools (backfilled estimate; the later audit fixes are in this snapshot too)
- The generator-side sampling code (index weights, blade layer, leaf layer, rock seating) is in `e215f70`, see ADR 0005.
