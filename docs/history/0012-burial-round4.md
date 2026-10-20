# 0012: burial round 4 rework: wavy soil line, soil = ground, physical shadow, mine contact shadow

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

This replaces the rejected ragged edge of ADR 0009 (`BURIAL_RAGGED_EDGE`, commit `61b6a85`). The uncommitted partial
wavy-edge edits left by the stopped agent (sin / cos wander, ragged edge off, clustered clods, weaker contact band)
were read with `git diff`, kept as the starting point, and finished here.

## Context

The user's requirements, verbatim from the feedback files:

- Feedback 0024: "now it looks unnatural. also, in this example the old one actually looks better since it's more
  believable", "the burial edge should be wavey to look more natural instead of it being a straight line. you should
  sample some combination of sin and cos waves at different amplitudes/freq + some noise on top. spawn clods/crumbs
  but limit their number and vary their size more. also, don't spawn them around the entire mine since it looks
  "forced" in that it's too uniform".
- Review grid, 0100 / 0102 (48 cards of commit `61b6a85`):
  - b002: "1) is it intentional for the shape of the shadow of the mine to change? it looks wrong in the burial
    version (it seems to extend further than it should, and it extends further than in the non-buried image)
    2) the sand that is added on top of the mine doesn't blend into the sand on the ground and instead has a sharp
    shadow line separating them 3) the shadow of the sand on top of the mine is too aggressive/sharp/strong"
  - b004: "you can still see the outline/shadow around the mine"
  - b019: "dirt on top of mine doesn't blend into dirt in the background"
  - b020: "sand on top of mine doesn't blend into sand in the background"
  - b001: "burial is relatively convincing ... we can leave this as is for now" (blades on top make it ~80% hidden)
  - b005: "very convincing but a straight line, although the line is along the ridge in the middle of the mine which
    is believable since it's a real height different in the STL file so it's fine"
  - b008: "this isn't related to the burial, but here the mine looks like it's floating on top of the grass (it's not
    blended into the background). I think the issue is that the shadow is the same size as the mine, so when the sun
    is at an angle the shadow is offset from the mine and not enough of it is under the mine itself, which makes it
    look like its floating on the side closer to the sun"
  - b022: "mine looks like it's floating"

Per-card analyses (`feedback/0101-analysis-*.md`) traced the causes in code and listed what the user did NOT say.
Main findings used here: the soil cover took its colour from the ground BEFORE the mine shadow was drawn, while the
ground around it was shadowed (b002, b020); the shadow was projected onto the tilted soil plane (stretch up to
1 / 0.1) and was cast by mesh parts later hidden by soil (b002, b004); `disturbed_patch` laid a blurred, darkened copy
of the ground shaped like the buried footprint (b004 ghost, b019 darker soil); the ridge shadow used the full image
shadow strength with a near-hard edge (b002 point 3); mine contact AO was 1.5-3.5 px and invisible on busy grass, so
nothing grounded the sun side (b008, b022). Things deliberately NOT done because the user did not ask: no change to
burial fractions, the 50% cap, blades on mines (b001), background deformation, soil colour rules for all
backgrounds, or forcing waviness where the line sits on a real STL step (b005).

## Decision

1. Wavy line (`BURIAL_IRREGULAR_LINE`): soil surface = plane + wander x (4-7 sin / cos plane waves, random direction /
   phase, wavelengths 0.2-0.8 x mine length, longer waves taller) + 15% fBm. Wander 0.025-0.055 mesh units. Shorter
   wavelengths (0.12) gave zigzags on flat wings at 6x and were dropped.
2. Clean edge, no crumbs: ragged edge off, soil lip no longer darkened, contact band of buried mines x 0.5.
3. Soil on the mine is the ground: cover alpha first, then the shadow, then the cover filled with the ground pixels
   after the shadow. Seam-free by construction.
4. Physically consistent shadow: horizontal soil level per vertex in `mesh.render_mine`, intersection with the unburied
   raster, and for buried mines a height-field sweep of the final visible part only; penumbra from the unburied
   length; ridge shadow halved, softer, and clipped to the unburied shadow region; AO on the soil cover damped.
5. Subtle localised cues: turned-soil patch faint, patchy, unblurred; ridge made of ground pixels with sun shading only;
   2-6 clods in 1-2 clusters, wide size spread, never centred on the exposed mine, never darker than the ground.
6. Separate flag `MINE_CONTACT_SHADOW` (not burial-specific, b008 / b022): soft ring hugging the footprint on all
   sides (sigma 3-6% of the mine length, strength 0.2-0.4 x shadow strength / 0.45).

## Consequences

- `docs/burial_realism.png` regenerated (columns: burial off, OLD 40% baseline, NEW 40%, NEW 40% + blades; contact
  shadow on everywhere). `burial_fix.png`, `burial_fix_2.png`, `v1_vs_v2.png`, `mine_crops.png`, `ablation.png`,
  `rock_shadows.png` regenerated (every mine now has the contact shadow). Showcase / review grid untouched.
- Tests: new `tests/test_burial_shadow_edge.py` (buried shadow reach <= unburied + 2 px, 6 cases; soil line wavy but
  bounded); `tests/test_burial.py` measures the final visible mask. All pass (5 tests). 50-image sample: max hidden
  0.50, cap never exceeded.
- Known weak spots: the wave can split the visible part into two pieces; on very dark grass the soft ridge is barely
  visible (by design); the contact ring is weak at high sun on bright straw (b022 sun-side ring 0.94 of the ground,
  short of the analysis' 0.8-0.9 target, kept low to avoid a dark outline, cf. b004); blades + burial can still
  hide ~80% (b001, left as is); the mine does not press into thick grass mats (b001, not worth solving).
- Next check is the user's eye on a regenerated review grid (b002, b004, b019, b020, b008, b022, and b005 must stay
  acceptable).

## Feedback that triggered this

- [0024 burial unnatural, wavy edge](feedback/0024-burial-unnatural-wavy-edge.md)
- [0100 review grid notes](feedback/0100-review-grid-48-notes.md), [0102 all notes](feedback/0102-review-grid-48-new-notes.md)
- Analyses: `feedback/0101-analysis-{b001,b002,b004,b005,b008,b019,b020,b022}.md`

## Commits

None yet (left uncommitted for the lead).
