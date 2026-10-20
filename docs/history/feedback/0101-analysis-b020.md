# 0101 - Analysis of review-48 note on b020

Card: `b020` (seed 5020, `ground_bg_Ground005`, sun elevation 16.8 deg, burial 0.19, face_down False, blades 2, dust 0.29).
Images: `../images/review48-b020-after.jpg` (burial on), `../images/review48-b020-before.jpg` (burial off).
Coordinates below are native pixels in the 480x270 crops (x right, y down). Luminance (lum) = mean of R, G, B, 0-255.

User note, verbatim:

> sand on top of mine doesn't blend into sand in the background

## 1. What the user literally says

The note is a single sentence. It breaks down into these claims:

- **C1. There is sand on top of the mine.** The note takes the soil cover as given. It does not complain that the soil is there.
- **C2. That sand does not blend into the background sand.** The soil on the mine reads as a separate thing and not as a continuation of the surrounding ground.

The note says nothing about the reason (colour, brightness, texture or edge), and nothing about the exposed mine, shadows, blades or the amount of burial.

## 2. Visual evidence per claim

**Overall layout.** The mine sits near the centre (body about x 200-290, y 80-150). The left wing spans about x 165-240, y 115-185. The sun is low and to the right, so the cast shadow falls to the upper-left. In *after*, the burial effect covers the **upper part of the left wing** (about x 185-225, y 105-150) with a roughly triangular patch of sand. The lower part of the left wing (about x 165-215, y 150-185) is still green mine. Pixels that differ between before and after (summed RGB difference over 30) fall in the box x 138-245, y 81-188.

**C1: confirmed.** In before, the region x 195-215, y 128-148 is green mine: mean RGB (83, 94, 53), lum std 3.6. In after, the same region is sand-coloured: mean RGB (101, 103, 81), lum std 13.2.

**C2: confirmed, mostly because of how the patch is bounded and not because of its hue.**

1. **A dark band separates the patch from the background sand.** A horizontal lum profile at y = 135 (5x5 box-smoothed) reads:
   - Background sand at x 110-160: 102-114
   - x 164-194: 98, 92, 81, **68, 65, 69** (dark gap)
   - Soil patch at x 200-218: 98-109
   - Then darker mine to the right.

   The band is about 10-15 px wide and neutral grey, with RGB about (63-68, 70-73, 61-64) at (184,135) and (190,135). That reads as ground in shadow, not mine. It runs along the whole upper-left edge of the patch. On that side, the soil never touches the background sand directly; it borders this dark strip. Pixel (184,135) is identical in before and after. It is the part of the mine's cast shadow / contact darkening that survived burial. The wider shadow further left (x 140-175) is gone in after: region x 140-175, y 110-150 goes from lum 83 to 110.
2. **A thin pale line outlines the patch.** It runs along the patch's upper-left border, about from (182,138) to (210,115), and is not present in before. It makes the patch look like a cut-out with an edge.
3. **On its other sides the patch is enclosed by green mine.** That is the centre body to the right and the lower wing below. The soil therefore reads as an isolated island sitting on the mine, not as ground that runs over it.
4. **Tone is close but a bit darker.** The patch has mean RGB (101, 103, 81) and G-B 21. Open sand measures:

   | Open sand region | Mean RGB | G-B |
   |---|---|---|
   | x 60-110, y 150-190 | (121, 124, 100) | 24 |
   | x 330-400, y 200-240 | (118, 121, 97) | 24 |
   | x 60-130, y 20-60 | (108, 110, 86) | 24 |

   Hue matches. Brightness is about 5-15 % lower than nearby open sand. On its own this is a minor contributor.
5. **Texture is roughly comparable.** The high-frequency residual (lum minus 5x5 blur) is 4.0 on the patch and 2.9-3.2 on open sand. The patch has a few extra dark specks (crumbs), but the grain is not obviously smoother or blurrier than the ground.

**Limits of the evidence.** The 480x270 crop is soft and noisy. I cannot separate which code layer produced the dark band (cast shadow, contact AO, ridge shadow or disturbed patch) or the pale line (ridge highlight or a lifted blade) from pixels alone. Section 3 has hypotheses for both.

## 3. Likely code causes (hypotheses, not verified by re-rendering)

- **H1 (main suspect): the soil gets its colour from the ground before the shadow is drawn, while the ground next to it stays shadowed.** In `objects.py` `Mine.draw`, `ground = fx.crop_padded(img, ...)` (line ~433) is taken **before** `self._draw_shadow(img)` (line ~435). `soil.burial_overlay` then paints the cover as `local_bg * tex`, which is unshadowed sand. Around it, `shadows.mine_shadow` darkens the ground with the clipped-mesh shadow (`mesh.render_mine` projects only the clipped `tri`) plus contact AO from `gblur(self.alpha)`. With sun elevation 16.8 deg this produces a lit sand island next to a dark shadow strip, which matches evidence 1.
- **H2: dark lip and ridge shadow along the soil line.** `burial_fx.berm_ridge` uses darkened turned-soil colour (`patch_darken`) and casts `r_sh` away from the sun. The cast length `hpx / tan(elevation)` is long at 16.8 deg. `soil.burial_overlay` also adds a darker berm band (`berm_darken`). Either could widen or deepen the dark band.
- **H3: the pale outline.** Two candidates: `burial_fx.berm_ridge` sunlit-slope shading (`shade` up to 1.15), or `burial_fx.lift_blade`, which shifts a crossing over-layer blade and brightens it by up to 12 % (`1 + 0.12 * zw`). The diagonal pale line lies where a blade could cross the soil line.
- **H4 (minor): the patch is a little darker than open sand.** `burial_fx.disturbed_patch` darkens and desaturates the ground under the mine before `ground` is re-sampled, so the soil cover inherits the turned-soil tone.
- **H5 (contributing): the island shape.** The `cover` / `buried` geometry in `soil.burial_overlay` puts the soil in the middle of the wing, so it touches mine on two sides. This is geometry, and the user did not comment on it (see section 4).

## 4. What the user did NOT say (over-generalisations to avoid)

- They did not say there should be less burial or no burial, or that soil should never sit on top of the mine.
- They did not say the soil colour or hue is wrong in general, or that soil must be pixel-identical to open sand everywhere. The hue matches already.
- They did not say to remove the mine's cast shadow, contact AO, berm ridge, clods or crumbs globally, or on other cards. Any change to those should be limited to how they make *this* soil edge look separate.
- They did not comment on the exposed (green) mine, its colour, dirtiness or edges.
- They did not comment on grass blades, the blade lift, or the pale line as such. That link is my inference.
- They did not say the shadow change between before and after is wrong.
- They did not ask for a texture change, such as more or less grain or blur.
- They did not state a rule for all cards or all backgrounds. The note is about b020 (low sun, sand background). Low-sun or other-background generalisation is a hypothesis to check, not a user rule.
- They did not ask for a different burial shape (island vs edge-connected). H5 is context, not a request.

## 5. Narrow, testable acceptance check

Re-render b020 (seed 5020, same parameters) with burial on and produce the same 480x270 crop. Then check:

1. **No dark seam.** Sample lum profiles perpendicular to the soil-cover boundary wherever the cover borders ground, not mine (for this card, the upper-left edge, about x 175-200, y 100-150). For each profile, the minimum lum in a band of 0-8 px outside the cover must not be more than about 15 lum below **both** the inner soil (2-6 px inside) and the outer ground (10-16 px outside). Today it is about 35-40 below (65-68 vs 100-110).
2. **Tone match.** The mean lum of the soil cover is within about 8 % of the mean lum of ground sampled in a 10-20 px ring around the cover, excluding mine pixels. Mean G-B stays within about 5 of that ring.
3. **No new bright outline.** Along the same boundary, no continuous pale line more than about 10 lum above both the soil and the ground on either side.
4. **Scope guard.** Pixels more than 25 px from the soil cover stay unchanged against the current after image, apart from JPEG noise. The burial fraction and visible-mask label stay within the current cap.
5. **Final judge.** A before/after pair is shown to the user for b020. The numeric checks above are proxies only.
