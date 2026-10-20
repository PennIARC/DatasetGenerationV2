# 0101 — Analysis of review-48 note on b019

Card: `b019 (seed 5019, ground_Screenshot 2026-02-07 at 4.21.38 PM, sun 32.7, burial 0.4, face_down True, blades 0, dust 0.37)`
Images: `docs/history/images/review48-b019-after.jpg` (burial on), `review48-b019-before.jpg` (burial off). Both are 480x270 native-pixel crops.

Note on the object: in this card the mine is a **saturated green** PFM-1, not a pale/olive one. The background is pinkish-brown dirt with pale blotches, a few dry grass tufts, a mottled rock (left) and a dark rock (upper right). The mine sits at native x≈202–283, y≈90–177 (before). With burial on, the visible green part shrinks to x≈207–262, y≈93–156 (~1550 px of green against ~3980 before, measured with a green-dominance mask). The right/upper-right part of the body and the lower-right tip are covered by soil.

## 1. What the user literally says

Note, verbatim: "dirt on top of mine doesn't blend into dirt in the background"

Split into claims:

- **C1.** There is "dirt on top of the mine", i.e. some soil rendered over the mine.
- **C2.** That dirt does not blend into the background dirt. It reads as a separate layer or patch instead of continuous ground.

The note does not say which dirt it means. Three layers could count as "dirt on top of the mine" (see section 4, A1):
(a) the soil cover over the buried part (`soil.burial_overlay`),
(b) the darker berm/ridge along the soil line (`burial_fx.berm_ridge` plus the burial_overlay lip),
(c) the dust, grains and streaks on the exposed green part (`burial_fx.dirty_exposed`, `soil.soil_blend`).
The evidence below points mostly to (a) and (b).

## 2. Visual evidence per claim

Method: I viewed both images at 1x. I made 4x and 6x zooms of the mine region with and without a contrast boost. I made a before/after luminance-difference map and a high-pass (detail-only) map, with the before-mine outline drawn on top. I sampled mean colours in masked regions. Zooms are in the scratchpad (`.../scratchpad/b019/`).

**C1 (dirt over the mine): confirmed.**
- In the after image, the part of the green body that ran to the right and lower-right (native ≈ x 255–285, y 95–175) is replaced by brown soil. The before image shows bright green there.
- The left edge of the visible green part carries small tan and brown crumbs on a dark rim (native ≈ x 205–215, y 100–125, and around the small left lobe ≈ x 215–235, y 130–150). These are the crumb and ridge pixels.

**C2 (does not blend): confirmed, mainly as a tone and hue mismatch plus internal dark streaks. The texture itself is not the problem.**
- **Darker.** Over the covered footprint (before-mine mask minus after-mine mask, 1570 px) the mean RGB is (75, 63, 49), luminance (brightness) ≈ 65. The same-image ground in a ring 25–45 px away is (96, 73, 61), luminance ≈ 78. The sunlit half of a ring 6–14 px away is ≈ 80. So the covered area is about 17–19% darker than the dirt around it. Both halves of the footprint are about equally dark (x≥265: luminance 66; x<265: 64), so this is not just the remains of the mine's cast shadow. That shadow fell lower-left, and in the after image it has mostly disappeared.
- **Less rosy and more olive/grey.** The red-to-green ratio (R/G) over the footprint is 1.20, against 1.31–1.32 for the surrounding ground. The background dirt is pinkish-brown. The soil on the mine is a duller khaki-brown. At 6x zoom the covered right half reads as a distinct, darker, mine-shaped patch next to the lighter pink ground immediately to its right (native x 286–300: luminance 80).
- **Dark streaks inside the patch.** The high-pass map shows dark bands running along the soil line inside the footprint, at native ≈ (250–262, 130–160) and along the lower-right tip. They run parallel to the old body edge, so they partly trace the buried shape. At normal size they read as a dark lip or "ghost edge", not as ground.
- **Ground just outside the footprint is only slightly darker.** To the right (x 286–300) after/before luminance is 80 vs 83. Above (y 78–88) it is 76 vs 80. So the disturbed-soil patch on open ground is mild. The mismatch is concentrated on the footprint itself.
- **Grain or texture: not supported.** Local high-frequency energy over the footprint (2.9) is similar to the background (2.4). The soil is not visibly smoother or blurrier than the ground. I do not see evidence that texture or sharpness is the issue.
- **Small olive spot.** A small olive/yellow spot sits at ≈ (265, 120) on the soil in the after image. In the before image it is a dark spot on the mine surface. It is probably a small over-layer item that exists in both images. It does not come from the soil code, but it does add to the "something sits here" look.

What I cannot confirm: whether the user also means the crumbs and dust on the exposed green surface (c). Those crumbs are small and tan or brown. Whether they "match" is hard to judge at this scale, and the note does not single them out.

## 3. Likely code causes (hypotheses)

- **H1, main hypothesis: the cover is coloured from darkened "turned soil", not from the undisturbed background.** In `objects.py` `Mine.draw` (≈ lines 427–433), `burial_fx.disturbed_patch` is drawn first. That patch is darkened by `DISTURBED_DARKEN` 0.72–0.88, desaturated by `DISTURBED_DESAT` 0.1–0.3, and pulled toward `BURIAL_SOIL_RGB` through `soil_colour` and `BURIAL_SOIL_MIX`. Then `ground` is re-cropped from the image. `soil.burial_overlay(..., ground, ...)` uses that `ground` as the cover colour, `soil = local_bg * tex * (...)`. So the soil over the mine inherits the darkened, desaturated patch at the patch's peak (alpha up to `DISTURBED_OPACITY` 0.45 right at the buried region). Away from the buried region the patch fades out, which fits the "dark patch on the footprint, almost unchanged ground outside" pattern. Desaturating toward grey lowers R/G, which fits the 1.31 to 1.20 shift.
- **H2: lip and ridge darkening stack on top.** `burial_overlay` darkens the lip by `BERM_DARKEN` 0.75–0.95 (opacity halved when `BURIAL_BERM` is on). `burial_fx.berm_ridge` then draws a ridge coloured `(0.6*g + 0.4*soil_colour(g)) * patch_darken`, plus its own cast shadow (`fx.darken` with `r_sh`). These sit inside or right next to a narrow covered strip, about 10–15 px wide here, so they cover much of it. That would explain the dark streaks that trace the old edge.
- **H3, minor: green leakage.** The cover alpha is blurred (`fx.gblur(a, 0.35)`) and the edge is partial (ragged/grainy). At partially covered pixels a little of the green mine may show through, which would also lower R/G. The effect is small, and the colour samples cannot separate it from H1.

None of these were verified by re-rendering. They are inferences from the code read together with the pixel measurements.

## 4. What the user did NOT say (avoid over-generalizing)

- **A1.** The note does not say which dirt layer is wrong (cover, ridge/lip, or exposed-surface dust). Do not retune `dirty_exposed`, `soil_blend` dust, or clods on the strength of this note alone.
- **A2.** It does not say "remove the berm/ridge", "remove the disturbed patch", or "no darkening at all". Real disturbed soil can be slightly darker. The complaint is that it fails to *blend* (a visible boundary or patch), not that any darkening exists.
- **A3.** It does not say burial is too deep, too shallow, or wrongly shaped, and it does not mention the soil-line geometry, edge raggedness, or crumbs.
- **A4.** It does not mention shadows. The mine's cast shadow mostly disappearing in the after image is a separate effect. Do not "fix" it from this note.
- **A5.** It does not say this happens on every background or for every mine colour. The evidence is one card: pinkish dirt, green mine, sun at 32.7°, burial 0.4. Do not invent a rule like "soil must equal the background colour exactly" or "never use BURIAL_SOIL_RGB".
- **A6.** It does not mention texture, blur, or grain. Measurements show the texture is comparable, so a texture rewrite is not called for.
- **A7.** It does not ask for global changes to background rendering, harmonisation (`harmonize_gain`), or the exposed mine's colour.

## 5. Narrow, testable acceptance check

Re-render b019 (seed 5019, same ground, burial 0.4) and compute these in the after image:

1. **Covered-footprint mask:** before-image green mask minus after-image green mask, eroded by 1 px, excluding the ~3 px band at the soil line.
2. **Brightness match:** mean luminance of the footprint lies within ±6% of the mean luminance of the sunlit ground in a ring 6–20 px outside the before-mine outline. Today the footprint is about 17–19% darker.
3. **Hue match:** the footprint's R/G ratio lies within ±0.04 of that ring's R/G. Today it is 1.20 vs 1.31.
4. **No ghost edge:** inside the footprint, away from the soil line, there is no continuous dark streak longer than ~10 px that runs parallel to the old mine outline in the high-pass map.
5. **Visual check:** in a side-by-side 4x zoom, the covered region is not identifiable as a separate patch. The only dirt-related feature that stays visible is a thin soil-line lip at the edge of the exposed part.
6. **Regression guard:** the visible-fraction stats (`hidden_by_stage`) and the burial fraction for b019 are unchanged within ±2%. The fix changes colour or tone, not the geometry.

## Summary

1. The user says the dirt drawn over the mine does not blend with the background dirt. They do not say which dirt layer, and they say nothing about texture, shadows, or how deep the mine is buried.
2. Confirmed: the soil over the covered right part of the green mine is about 17–19% darker (luminance 65 vs 78–80) and less rosy (R/G 1.20 vs 1.31) than the ground around it, and it has dark streaks tracing the old edge. Its texture matches the background.
3. Hypothesis: the soil over the mine takes its colour from `ground`, which is re-cropped after `burial_fx.disturbed_patch` has darkened and desaturated it (`objects.py` `Mine.draw`). Lip darkening (`BERM_DARKEN`) and the `berm_ridge` ridge and shadow add more darkening on top.
4. Avoid inferring: remove the berm or patch, zero darkening, retune the dust on the exposed surface, change shadows or soil-line geometry, or treat this one card as a rule for all backgrounds.
5. Acceptance check: on re-rendered b019, footprint luminance within ±6% and R/G within ±0.04 of the nearby sunlit ground, no ghost-edge streaks, and burial fraction unchanged.
