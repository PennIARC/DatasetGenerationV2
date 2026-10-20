# 0101 - Analysis of review note on b002

Card: b002 (seed 5002, ground_bg_Ground005, sun 24.8, burial 0.41, face_down True, blades 0, dust 0.33, visible_frac 0.59).
Images: `../images/review48-b002-after.jpg` (burial on), `../images/review48-b002-before.jpg` (burial off). Both are 480x270 native crops. All coordinates are native pixels (x right, y down). "Lum" means 8-bit luminance (0 is black, 255 is white). Values come from 3x3 or 5x5 averages and blurred maps.

User note, verbatim:
> 1) is it intentional for the shape of the shadow of the mine to change? it looks wrong in the burial version (it seems to extend further than it should, and it extends further than in the non-buried image)
> 2) the sand that is added on top of the mine doesn't blend into the sand on the ground and instead has a sharp shadow line separating them
> 3) the shadow of the sand on top of the mine is too aggressive/sharp/strong

Scene overview. In these crops the mine renders saturated green, not pale olive. The sun is low (24.8 deg) and comes from the bottom of the frame, so the mine's cast shadow falls upward, roughly y 30-140, x 170-320 in the before image. Before burial, the mine fills about x 175-325, y 95-205. After burial, the lower part (about y 175-205) is gone. A pale band of soil (lum 90-105) sits along the new lower edge, about x 225-325, y 150-186. A dark band runs across the exposed mine just above that soil.

## 1. What the user literally says

- **C1a (question).** Is it intentional that the mine's shadow *shape* changes between before and after?
- **C1b.** In the after image the shadow looks wrong because it *extends further than it should*.
- **C1c.** It also extends further than the shadow in the before (unburied) image.
- **C2a.** The "sand added on top of the mine" does not blend into the ground sand around it.
- **C2b.** What separates them is a *sharp shadow line*: a dark line or step at the boundary, not just a colour mismatch.
- **C3.** The shadow that the on-mine sand casts is too aggressive. The user names three qualities: too sharp (hard-edged), too strong (too dark), and "aggressive" (too much overall).

The user does not say *which direction* the shadow over-extends, by how much, or what the right shadow would be. The sentence in C1 only complains about it extending *further*.

## 2. Visual evidence

| Claim | Where / what | Before vs after | Confirmed? |
|---|---|---|---|
| C1a | Whole cast-shadow region, x 160-330, y 0-150 | Before: one broad, rounded dark blob above the mine (top edge about y 28-30, right edge about x 300-320). After: a different shape. A narrower arm on the left (x 165-210) runs up almost to the crop top. A large patch on the upper right (about x 220-300, y 40-75) that was shadow is now lit ground (row 60, x 236-254: before lum 48-70, after 74-112; row 90, x 284-314: before 59-79, after 85-112). | **Yes.** The shape clearly changes, not just the size. Some change is expected because less of the mine sticks up, but the type of change is the issue (see C1b/c). |
| C1b / C1c | Upper-left arm of the shadow, x 165-210 | Before: shadow ends at about y 28-30. After: it continues to about y 5-10 (the after-minus-before difference map shows a block that is darker only in the after image, at x 165-205, y 10-25). From the mine's top edge (about y 95) that is about 65 px before vs about 85-90 px after, roughly 1.3-1.4x longer, at the same sun elevation. It may run on past the crop top, so the full extent is unknown. | **Yes, on this side.** The after shadow reaches clearly further than the before shadow, and a sunk mine should cast a shorter shadow, not a longer one. |
| C1b (other sides) | Right side of the shadow, and the band along the right edge of the soil, x 290-320, y 80-185 | The shadow edge on the right is at about the same x in both images. A thin dark rim follows the right and lower-right edge of the pale soil. That rim belongs to C2 and is not part of the mine's cast shadow. | **Not confirmed** as further extension. On the right the cast shadow is actually *shorter* after burial. "Extends further" holds for the upper-left arm only. |
| C2a | Pale soil band, x 225-325, y 150-186 (lum 90-105), against the ground right outside it below and to the right | The ground right next to the soil is much darker (lum 68-80) than the soil and than open ground in the same image (lum about 104 at x 380-470, y 200-260). Moving away from the soil it brightens back to about 88-90 over about 5-8 px. So the soil reads as a lighter, separate patch pasted on top. | **Yes.** |
| C2b | Lower edge of the soil band. Column x 270: lum 98 at y 184, then 69 at y 185. Column x 295: 99 at y 186, then 68 at y 187. Column x 240: 83 to 52 in one row. Right edge (row 160, x 300-315): a smaller dip, 92 down to 78 and back up to 84. | The edge is a 25-30 lum step that happens within **1 px**, then a dark trough on the ground side that fades out. In the before image these pixels were mine body (lum 73-80) with no edge. | **Yes.** It is a sharp dark line or step, strongest along the lower edge and weaker on the right end. |
| C3 | Dark band on the exposed mine directly above the soil, about x 180-320, y 150-168 | Mine body before: lum about 70-80. After, inside the band: 37-50 (column x 240 bottoms out at 37 at y 164, column x 295 at 38 at y 166). That is about 0.5x the mine's brightness. The band then jumps to the pale soil (lum 79-93) within 2-4 px. The right lobe of the mine (x 270-320, y 120-165) is also heavily darkened and speckled with dark brown grains. The band is nearly as dark as the deepest part of the mine's real cast shadow on the ground. | **Yes.** It is strong, close to the mine-shadow darkness, and its lower edge is hard. Its upper edge fades over about 8-10 px, so "sharp" fits mainly the soil side of the band. |

Not supported or out of scope: nothing in these crops shows a problem with the *colour* of the soil, apart from the brightness step. Nothing shows a problem with how much of the mine is buried.

## 3. Likely code causes (hypotheses; nothing was re-rendered)

**C1 (shadow shape and length)**
- H1.1 `features/mesh.py::render_mine`. With burial on, the shadow is projected onto the **tilted soil plane** `n_pl` (tilt up to `BURIAL_TILT` = 25 deg in `controlPanel.py`) instead of the flat ground the photo shows. The code divides by `denom = max(n_pl @ L, 0.1)`. At sun elevation 24.8 deg, a plane that tilts away from the sun by up to 25 deg pushes `n_pl·L` from about 0.42 (flat) toward the 0.1 floor, which can stretch the shadow up to about 4x. The `(x, y)` of points projected onto the tilted plane are then used as if the ground were flat. Heights are also measured from the tilted plane (`d = (p·n - c)/denom`), so parts of the mine on the low side of the plane get longer shadows. That would explain why the shadow is longer on one side and shorter on the other, which is what the image shows (upper-left arm longer, upper-right patch gone).
- H1.2 (smaller effect) The shadow raster uses the clipped 3D triangles only. Mine pixels later hidden by the soil cover or by `clean_mask` drops still cast shadow (`objects.py::_draw_shadow` uses `self.r["shadow"]`). This can change the shape but cannot make the shadow longer than in the before image.

**C2 (on-mine sand vs ground: sharp shadow line)**
- H2.1 `objects.py::draw` fixes the order of operations. `ground = fx.crop_padded(img, ...)` is captured **before** `self._draw_shadow(img)`. `soil.burial_overlay` (`soil = local_bg * tex ...`) and `burial_fx.berm_ridge` take their colour from that unshadowed `ground`. The ground right around the soil is then darkened by the mine's blurred cast shadow, its penumbra and contact AO (`shadows.mine_shadow`; AO means ambient occlusion, the extra darkening where an object touches the ground) and by `burial_fx.disturbed_patch`. The soil is pasted on top with almost no feather: `fx.gblur(a, 0.35)` when ragged. The result is a bright patch with a 1 px step down to darker ground, which matches the evidence for C2.
- H2.2 `burial_fx.berm_ridge` shading `shade` reaches up to 1.15x on the side facing the sun (the bottom side here), so the soil's lower edge gets even brighter than the ground.
- Note: the soil only covers pixels where `alpha > 0` (the visible mine) plus a small zone. The buried footprint next to it shows plain ground, darkened as described in H2.1. That puts two differently lit "sands" right next to each other.

**C3 (shadow of the on-mine sand)**
- H3.1 `burial_fx.berm_ridge` cast shadow `sh`. It is a hard binary mask `(height > 0.25)` shifted away from the sun, blurred only by `max(0.7, 0.3*length)` px, and applied with the **full** `sun["shadow_strength"]` (`objects.py::draw`, `fx.darken(img, fx.shadow_factor(r_sh, ...))`). So a ridge only 0.02-0.05 x mine length tall gets a shadow as dark as the mine's own shadow, with a near-hard edge.
- H3.2 `burial_fx.dirty_exposed` stacks on top of H3.1: occlusion `ao_strength` 0.25-0.45 (`EXPOSED_AO_STRENGTH`) with `exp(-dist/ao_px)` falloff, plus `exp_darken`, desaturation and dark grains/streaks that get denser toward the soil line. Combined with H3.1 this can produce the observed drop to about 0.5x brightness. The grains also explain the dark speckle on the right lobe.

## 4. What the user did NOT say (over-generalizations to avoid)

- They did **not** say the shadow should be identical to the unburied one. C1a is a question. The complaint is that it is *longer / extends further*. A buried mine casting a *shorter* or smaller shadow is not criticised and is physically expected.
- They did **not** say to remove the ground-plane tilt, the burial clip, or the irregular soil line in general. Only the shadow's shape and length are flagged.
- They did **not** say the soil on the mine should go away, be darker or lighter in colour, or be textured differently. They said it should *blend* and not have a sharp *shadow line* at its boundary.
- They did **not** ask to remove the shadow of the sand on top of the mine (C3). They said it is too aggressive, sharp and strong. A softer, weaker shadow is implicitly acceptable.
- They did **not** complain about the disturbed-soil patch, the clods, the dust film or the grains as such. (The grains may add to C3's darkness, but they are not named.)
- They did **not** generalize to other cards, sun angles or backgrounds. Notes on other cards look similar (b019 "dirt on top of mine doesn't blend into dirt in the background", b004 "outline/shadow around the mine"), but they are separate notes and should be checked separately, not merged into a rule from this card.
- They did **not** say all shadows in the generator are too strong. C3 only covers the shadow from the on-mine sand.
- They did **not** comment on how much of the mine is buried, the label/visible fraction, or the mine's colour.

## 5. Narrow, testable acceptance checks

Re-render seed 5002 with the same settings, burial on and off, and crop the same 480x270 window.
1. **C1:** Measure the cast shadow on the ground (blurred lum below the local-ground median minus 20, with mine, soil and ridge pixels masked out). The after shadow's farthest extent along the shadow direction (away from the sun), measured from the mine's top edge, must be **<= the before shadow's extent**. The after shadow mask must be a subset of the before mask, allowing at most 2-3 px of penumbra growth. In particular, the upper-left arm must not reach above y about 30.
2. **C2:** Take luminance profiles across the outer boundary of the on-mine soil (e.g. columns x 240, 270, 295 and row 160). There must be no step larger than about 10 lum within 2 px, and no dark trough on the ground side more than about 8 lum below the ground 10 px further out. The mean soil luminance must be within about 8 lum of the ground right next to it.
3. **C3:** In the band of exposed mine directly next to the soil line (about y 150-168 in this crop), the median luminance must be **>= 0.75x** the median luminance of the same mine pixels with burial off (currently about 0.5x). The darkening must ramp over at least about 3 px at the soil-line edge, not jump within 1 px.
4. Regression guard: the before (unburied) render of seed 5002 must be pixel-identical to the current `review48-b002-before.jpg` source.

Summary:
- C1 is confirmed in part. The shadow shape changes, and its upper-left arm reaches about 20-25 px further (about 1.3-1.4x) than before burial. The upper-right part actually got shorter. Likely cause: shadow projected onto the tilted soil plane (`mesh.render_mine`, `denom` up to 1/0.1).
- C2 is confirmed. The pale on-mine soil (lum 90-105) meets darker ground (lum 68-80) in a 1 px step with a dark trough on the ground side. Likely cause: soil colour sampled before the mine shadow, AO and disturbed patch are drawn (`objects.py::draw`), and pasted with almost no feather.
- C3 is confirmed. The band on the exposed mine above the soil drops to about 0.5x the mine's brightness (lum 37-50 vs 70-80) with a hard lower edge. Likely cause: `berm_ridge` cast shadow at full `shadow_strength`, stacked with `dirty_exposed` occlusion and grains.
- The user did not ask for identical shadows, for removing the soil or the ridge shadow, or for any change beyond these three symptoms on this card.
- Checks: after shadow inside before shadow; no step over 10 lum at the soil edge; soil-line band at least 0.75x the unburied mine brightness.
