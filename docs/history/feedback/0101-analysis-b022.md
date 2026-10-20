# Analysis: card b022 ("mine looks like it's floating")

Card: b022, seed 5022, `grass_bg_gen_19_grass_dry_normal`, sun elevation 60.1 deg, burial 0.32 (visible_frac 0.68), face_down False, blades_on_mine 0, dust 0.28. The metadata does not record sun azimuth or shadow strength.
Images: `../images/review48-b022-after.jpg` (burial on), `../images/review48-b022-before.jpg` (burial off, same scene).

## 1. What the user literally says

Verbatim note: "mine looks like it's floating"

Split into claims:
- C1: the mine looks like it is floating, meaning it does not read as resting on or in the ground.

That is the only claim. The note gives no cause, no region, no comparison with the before image, and no mention of burial, shadow, blending or colour.

## 2. Visual evidence

Method: 4x zoom crops of the mine region in both images, an amplified |after - before| difference image, and median luminance in rings at fixed distances outside a colour-segmented mine mask. The rings were split into four quadrants around the mine centroid.

**C1 (floating): plausible and partly supported. The evidence for "why" is circumstantial.**

- **No visible contact darkening at the edge, in either image.** At 1-3 px outside the mine, median luminance is about 122 (before) and 123 (after). At 3-6 px it is about 113 / 115, and at 15-30 px it is about 113 / 111. The ground right next to the mine is no darker than the ground farther away, and the 1-3 px ring is slightly brighter (some of that is anti-aliased mine edge). At the zoom I could not see a dark line or soft dark band along any edge of the body, including the lower-left edge, where the body crosses dry straws.
- **No visible cast shadow beside the mine in either image.** No quadrant shows a dark lobe touching the mine. The darkest quadrant (lower-right, about 77-78 at 15-30 px) is the same in both images and comes from the background photo (darker grass there), not from the mine.
- **The mine reads as flat, evenly lit and smooth against a busy, high-contrast straw background.** The body is a fairly uniform olive (median L about 135-139), with weak shading across its surface and crisp outlines. Straws run up to the silhouette and stop. None cross over the mine (blades_on_mine = 0), so nothing ties the object into the straw layer.
- **Before vs after.** The body is pixel-for-pixel nearly identical in both images. The difference image is non-zero only (a) where the wing (with the "ARC" text) was removed by burial and replaced with ground, and (b) in a thin halo along the right and lower-right edge of the body (soil blend / dust). That halo is faint and does not read as a contact shadow. The floating look is **present in the before image too**, and arguably slightly stronger there, because the raised wing is fully visible with no shadow under it.
- **What I cannot confirm from the image:** whether the renderer produced a shadow that is simply too small to see (at 60 deg elevation the cast shadow is short and largely hidden under the body), or whether the shadow / AO came out very weak. That needs a re-render with the shadow layer dumped. I also cannot tell whether the user mainly reacted to the missing shadow, the flat shading, or the missing occlusion by straws. The note does not say.

## 3. Likely code causes (hypotheses, not verified by re-rendering)

- `features/shadows.py::mine_shadow`: contact AO is `gblur(alpha, ao_sigma) * ao_strength`, with `CONTACT_AO_STRENGTH = (0.1, 0.3)` and `CONTACT_AO_SIGMA = (1.5, 3.5)` px (`controlPanel.py`). The AO is a blur of the visible silhouette, so only about 1 sigma (2-3 px) of it extends past the edge, at roughly half strength or less, i.e. at most about 5-15% darkening. The ring measurements show nothing at that level. For a dull object on high-frequency straw texture, that is too small to read as contact.
- `features/mesh.py::render_mine` (shadow projection) + `objects.py::_draw_shadow`: at sun elevation 60.1 deg, the shadow length is about height / tan(60) ≈ 0.58 x mine height. Most of the projected shadow falls under the mine's own footprint, which the mine then covers. The cast shadow therefore adds almost nothing visible outside the silhouette. This is a different mechanism from b008, where a low sun made the shadow offset to one side. Here the issue is "no visible shadow at all", not "shadow offset".
- `features/shadows.py::mine_shadow` uses `self.alpha` (the visible, post-burial silhouette) for AO. In the after image this means no AO where the wing was buried. That is correct for burial, but it does not explain the before image, which floats too.
- Possible contributor: mine shading in `features/mesh.py::render_mine` (`amb = 1 - shadow_strength` ambient gain, with high sun). With weak shading across the body, the mine reads as a flat cutout. This is a hypothesis only. I did not measure the shading against the background's lighting.

## 4. What the user did NOT say (avoid over-generalising)

- They did not say it is caused by burial, and the evidence says it is not burial-specific. The before image (burial off) floats the same way. Do not "fix" this in `burial_fx.py` / `soil.py`.
- They did not say the shadow is offset or the same size as the mine. That was their b008 diagnosis, at a lower sun. Do not import it into b022 without evidence. At 60 deg sun, the offset mechanism is weak.
- They did not say every mine floats, or that every grass background floats, or that high-sun images float. This is one card.
- They did not ask for blades over the mine, a colour/saturation change, or stronger dust/soil.
- They did not comment on the burial result itself (the buried wing, the soil line). Do not count this card as burial feedback, positive or negative.

## 5. Narrow testable acceptance check

Re-render seed 5022 with the same settings, with burial on and with burial off. Use the same mine mask (unclipped `alpha_full` for the before image, visible `alpha` for the after image) and measure median ground luminance in a 1-4 px ring outside the silhouette against a 12-30 px ring. Do this on the ground layer before the mine is composited (or on the final image, excluding the mine pixels).
- Pass: in both renders, the 1-4 px ring is at least about 10% darker than the 12-30 px ring all the way round (all four quadrants), and darkest on the side away from the sun. The original b022 measures about 0% (actually slightly brighter).
- Guard: on a lower-sun card (b008 at sun 53.5, and any card at 15-25 deg), the far end of the cast shadow keeps its current length and softness, so the change does not just paint a uniform dark halo.
- Final check: the user views the re-rendered b022 before/after pair and no longer calls it floating.
