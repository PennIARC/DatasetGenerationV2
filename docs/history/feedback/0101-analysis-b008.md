# Analysis: card b008 (review grid 48)

Card: seed 5008, `grass_bg_gen_23_grass_dry_normal`, sun elevation 53.5, burial 0.21, face_down False, blades 0, dust 0.37
(metadata from `0102-review-grid-48-new-notes.md`).
Images: `../images/review48-b008-after.jpg` (burial on) and `../images/review48-b008-before.jpg` (burial off). Both are 480x270 native-pixel crops.

User note (verbatim):

```
this isn't related to the burial, but here the mine looks like it's floating on top of the grass (it's not blended into the background). I think the issue is that the shadow is the same size as the mine, so when the sun is at an angle the shadow is offset from the mine and not enough of it is under the mine itself, which makes it look like its floating on the side closer to the sun
```

## 1. What the user literally says

- C1: The issue is not related to burial.
- C2: The mine looks like it is floating on top of the grass, meaning it is not blended into the background.
- C3 (the user's own hypothesis, hedged with "I think"): the shadow is the same size as the mine.
- C4 (hypothesis, continued): with the sun at an angle, the shadow is offset from the mine, so not enough of it is under the mine itself.
- C5: As a result, the mine looks like it floats on the side closer to the sun.

## 2. Visual evidence

I compared both crops, 4x zooms of the mine region (x 160-340, y 80-210), and vertical luminance profiles through the mine at x = 210, 230, 250 and 280. Luminance is 0-255 grey, averaged over 5 columns.

- C1 (not burial): confirmed. Burial changes only the right wing. In the after image the right wing (about x 265-310) is cut back to a smaller lobe. Every other part of the crop, including the shadow below the main body and the edge above it, has the same values in both images to within JPEG noise. At x=210 and x=230 the profiles match row for row. The floating look appears equally in the before image, so it does not depend on burial.
- C2 (floating, not blended): confirmed as a visual impression in both images. The mine reads as a flat brown cut-out lying over the grass. Its outline is clean against the grass on every side. No blades cross it, which matches `blades 0` for this card.
- C4/C5 (offset shadow, floating on the sun side): partly confirmed. The cast shadow falls downward in the image (+y), so the sun is towards the top of the frame.
  - Anti-sun (bottom) side: a dark band about 20-25 px tall sits directly below the main body. At x=230 the mine (lum about 45) ends near y=154, then shadow (lum 30-37) runs to about y=178, then grass (lum 40-60+). At x=210 the shadow reaches lum 22-26.
  - Sun (top) side: the mine has no visible darkening around it. At x=230, lum goes from 86 at y=98 straight to the mine's 53 at y=102. At x=250, the grass is still at 85-124 just above the mine edge. Bright grass blades touch the top edge and the upper-right wing directly. This is the side the user says looks like it floats, and the images agree: grounding cues sit only on one side.
- C3 (shadow same size as the mine): cannot be confirmed from the image. The part of the shadow that would be under the mine is hidden by the mine, so a 2D crop cannot show the full shadow's size. Only a band that sticks out on the anti-sun side is visible. In the code (section 3), the cast shadow is not the same size as the mine. It is the mine's footprint plus the projection of the raised parts, so it is larger than the footprint and extends only away from the sun. The user's underlying observation still holds: under the sun-side edge there is nothing beyond the mine's own outline. The cause is just not a size mismatch.

## 3. Likely code causes (hypotheses, not verified by rerendering)

1. The cast shadow is purely geometric and one-sided. In `features/mesh.py`, `render_mine` builds `shadow` from `_raster_union` of the mesh vertices projected along the sun onto the flat plane at z0. Base vertices project onto themselves, so the coverage is the footprint plus a sweep away from the sun, and nothing extends past the outline on the sun side. `features/shadows.py`, `mine_shadow` then only blurs this by `penumbra_sigma` (PENUMBRA_BASE_PX 0.6 + 0.06 x length, about 1-2 px here). For a flat ground plane at 53.5 deg elevation this is physically correct. That is why the sun side has no darkening at all.
2. The contact AO (ambient occlusion: extra darkening where an object meets the ground) is too small to show. `mine_shadow` uses `fx.gblur(alpha, ao_sigma) * ao_strength`, with `CONTACT_AO_SIGMA = (1.5, 3.5)` px and `CONTACT_AO_STRENGTH = (0.1, 0.3)` in `controlPanel.py`. Outside the outline the blurred alpha is at most about 0.5 and falls to near zero within a few px, so the rim is at most about 5-15% darker over 3-7 px. On bright, high-contrast dry grass that cannot be seen, and the profiles above show no measurable rim. By contrast, rocks and clods use `shadows.contact_shadow`, called from `objects.py` around line 225, which dilates and blurs by `width_frac x object width` and therefore scales with object size. The mesh mine does not use this path (`objects.py`, `_draw_shadow`).
3. Possible contributing factor that the user did not name: the ground model is a flat photo, so the mine sits on top of the grass layer instead of among it (see section 4). The user attributes the look to the shadow, so this is listed only for completeness.

## 4. What the user did NOT say (over-generalisations to avoid)

- The user did not say burial is involved. They explicitly say it is not, and the before image shows the same look. Do not change burial code for this card.
- The user did not say the cast-shadow direction, length or softness is wrong, or that the shadow on the anti-sun side should be shorter or removed. The complaint is about the sun side lacking grounding.
- The user did not say the mine's colour, shading, outline sharpness or size is wrong.
- The user did not ask for grass blades over the mine. "Not blended into the background" is explained by their shadow hypothesis, not by occlusion. Don't add overgrowth as the fix for this note.
- The user did not say this happens on every card or every background. It is stated for "here" (b008, dry grass, sun 53.5). Card b022 ("mine looks like it's floating") is a separate note. It may share the cause, but the b008 note does not claim that.
- The user did not prescribe a literal fix such as "make the shadow larger than the mine". C3 is a hypothesis ("I think"), and per section 2 it is not literally what the code does. The fix should target the observed symptom (no darkening on the sun side under or around the edge), not necessarily the shadow's size.

## 5. Narrow acceptance check

Re-render seed 5008 with the same overrides, burial both on and off, and the same native-pixel crop.

- Measure: take the mine alpha. In a ring 1-6 px outside the outline, keep the pixels whose outward direction points towards the sun (the top edge here). Compute their mean luminance divided by the mean luminance of a matching ring 15-25 px out on the same side. Today this ratio is about 1.0, because there is no darkening.
- Pass: the sun-side ratio is clearly below 1 (target about 0.8 or lower, tune it). The anti-sun cast shadow band keeps roughly its current length (about 20-25 px) and position, so the shadow direction does not change. The burial-on and burial-off images still differ only in the right wing.
- Final gate: the user views the regenerated b008 pair and no longer reads the mine as floating on the sun side.

## Summary

1. Confirmed in both images: the mine looks pasted on top of the grass, and burial plays no part (the before image is identical outside the right wing).
2. Confirmed: the only grounding cue is a 20-25 px cast-shadow band below the mine. The sun side (top) goes straight from bright grass to mine with no darkening.
3. Not confirmed literally: the shadow is not "the same size as the mine". It is footprint plus an anti-sun sweep (`mesh.render_mine`), so nothing extends past the outline on the sun side.
4. Likely cause: contact AO in `shadows.mine_shadow` is tiny (sigma 1.5-3.5 px, strength 0.1-0.3), unlike the width-scaled `shadows.contact_shadow` that rocks get.
5. Acceptance: on a re-render of seed 5008, a 1-6 px sun-side ring is measurably darker (ratio about 0.8 or lower), the anti-sun shadow is unchanged, and the user no longer sees floating.
