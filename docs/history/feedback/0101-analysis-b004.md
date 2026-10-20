# 0101 - Analysis of review note on b004

Card: b004 (seed 5004, grass_bg_real_00_Grass001_grass_fresh, sun 27.4, burial 0.45, face_down False, blades 0, dust 0.28).
Images: `../images/review48-b004-after.jpg` (burial on), `../images/review48-b004-before.jpg` (burial off). 480x270 native crops; all coordinates below are native pixels (x right, y down).

User note, verbatim: "you can still see the outline/shadow around the mine"

## 1. What the user literally says

- **C1.** In the after image, you can still see something *around* the mine that the user calls an "outline/shadow".
- **C2 (implied by "still").** That something should have gone away with burial. It's leftover from the unburied mine (its old outline, or its shadow), not a new feature.
- The slash in "outline/shadow" reads as one artefact that looks like either an outline or a shadow. It does not name two separate defects. The note says nothing about where around the mine it is, how strong it is, or what colour it is.

## 2. Visual evidence

Overview. Before: a dark olive PFM-1 (upper wing about x 228-262, y 55-110; body/lower lobe about x 215-265, y 110-165) with a long, soft cast shadow down-right (to about x 310). After: the upper wing and the whole cast shadow are replaced by grass ground, and the lower roughly 55% of the mine is still visible as a dark lobe (about x 212-280, y 108-165). Dark pixels (blurred luminance < 45) drop from 8038 to 3323, so most of the shadow really is gone.

Remnants I can see in the after image that trace the old mine/shadow:

| # | Where (after) | What | Before vs after | Confirms C1/C2? |
|---|---|---|---|---|
| E1 | Thin diagonal line from about (242,54) to (262,78), roughly 2-3 px wide | Dark streak, luminance 36-45 against ground about 60-75. It runs parallel to the old upper wing's top-right edge, offset about 3-5 px outward | Before, those pixels were ground just outside the wing (lum about 55-62). After, they are *darker* (signed diff is negative only here). So the line is new in the after image and traces the buried wing's outline | **Yes, the clearest "outline".** It is visible at 1x in the after image as a dark line above the exposed lobe |
| E2 | Right tip of the exposed lobe, about x 268-282, y 112-128 | Dark blob (lum about 38, min 19) sticking out past the lobe's right corner at the soil line | Before, this was inside the cast shadow (lum about 28). After, it is still dark while the rest of the shadow is gone | **Plausibly the "shadow" part.** It is a shadow remnant attached to the mine. It could be the real shadow of the still-exposed part, or the berm ridge shadow, so it is not certainly wrong |
| E3 | The whole area that was mine plus shadow before and is ground after (about x 225-310, y 55-165) | Ground there is smoother (local 5x5 std 3.6 vs 4.3 on far ground) and slightly darker (lum 64.8 vs 67.7). The 0-4 px ring just outside it is darker again (63.7) | Before, this was mine and shadow. After, it should match the surrounding ground but it is a faint, smoother, darker "ghost" of the old footprint. In the zoomed view it reads as a soft dome with an edge above the lobe | **Weakly.** It is measurable and visible when zoomed, but subtle at 1x. It may add to the perceived "outline" |
| E4 | Left and bottom edge of the exposed lobe | Faint, slightly darker rim (seen in the after-minus-before diff) | Small change | **Not confirmed as the complaint.** This is the edge of the visible mine itself, which should exist |

Not supported: the full cast shadow is **not** still there. It was removed almost entirely. If "shadow" meant the original big shadow, the image does not show that. What remains is the thin line (E1), the tip blob (E2) and the faint ghost (E3).

## 3. Likely code causes (hypotheses, not verified by re-rendering)

- **H1 (E1, strongest).** In `objects.py` `Mine.draw()`, the mine shadow is drawn by `_draw_shadow()` -> `shadows.mine_shadow(self.r["shadow"], ...)` **before** the burial cleanup. The `drop` mask (slivers or thin rims that `burial_fx.clean_mask` removes from the visible mine, about lines 456-481) is applied only to the mine's colour and alpha, never to `self.r["shadow"]`. A thin wing rim that the clip plane left above the soil (then dropped as a fragment) would still cast a thin shadow line. That line would sit just outside the old wing edge and run along the shadow direction, which matches E1. The other possibility is that the shadow raster from `mesh.py` (`render_mine`) includes geometry that is above the soil plane but later covered by `soil.burial_overlay`. Either way, the shadow source is not the final visible part.
- **H2 (E2).** Same path. The shadow is computed from the mesh above the clip plane, not from the final visible mask (`vis_final`). Soil cover and the berm hide some of that mesh but its shadow stays. `burial_fx.berm_ridge` also adds its own cast shadow (`r_sh`) at the soil line, which could make the tip darker.
- **H3 (E3).** `burial_fx.disturbed_patch()` covers the buried region plus a radius of about 0.08-0.2 L with *blurred* ground colour (`gblur(local, 0.1 L)`), darkened by 0.72-0.88 and partly opaque. A blurred, darkened copy of the ground shaped like the buried footprint gives a smoother, darker ghost of the old outline. Its edge comes from `distanceTransform` of the buried mask, so it follows the mine's shape.

## 4. What the user did NOT say (do not infer)

- The user did not say burial is wrong, the burial fraction is wrong, or the exposed lobe looks bad.
- The user did not say to remove all shadows from buried mines. The exposed part may still cast a correct shadow, and only leftover outline or shadow traces of the hidden part are in scope.
- The user did not say to remove the disturbed-soil patch, the berm or the clods globally, and gave no other rule for them.
- The user did not say the dark edge of the visible lobe (its own silhouette) is a problem.
- The note gives no general rule for other cards, sun angles or backgrounds. It is one observation on b004 only, so don't turn it into a dataset-wide rule.
- The user did not say the outline is dark (it could be read as a light halo). The measured data points to dark remnants, but the user did not specify a colour.
- The user did not ask for a lighter or darker ground fill under the buried area, or for different soil colours.

## 5. Narrow acceptance check

Re-render b004 (seed 5004, same parameters) with the fix and compare after vs before:

1. **E1 gone.** In the band about x 240-265, y 52-80, no connected dark streak remains. Pixels on the old wing-edge line are within about 8 luminance levels of the adjacent ground (no run of 10 or more pixels below about 50 lum along the old edge).
2. **No shadow from hidden geometry.** The shadow that reaches the ground comes only from the final visible part of the mine. A debug check: the shadow source mask is a subset of the final visible mask (dilated by 1-2 px) plus whatever the berm ridge legitimately adds.
3. **E2 justified or gone.** Any dark region past the lobe's right tip is explained by the exposed part's own shadow at sun 27.4 (it lies on the shadow side of a visible pixel), not left over from the buried wing.
4. **E3 not worse.** Inside the old footprint, local texture std is at least about 90% of the surrounding ground and mean luminance is within about 2 levels, so no traceable ghost outline remains (only if E3 is addressed; it is the weakest evidence).
5. A person viewing the after crop at 1x cannot trace the buried wing's shape.

Summary:
1. The user sees a leftover "outline/shadow" around the partly buried mine in b004.
2. The strongest evidence is a thin dark line (about (242,54)-(262,78)) that traces the buried upper wing's edge. It is darker after than before, so burial created it.
3. A dark blob at the exposed lobe's right tip and a faint, smoother, darker ghost of the old footprint also remain. The big cast shadow itself was removed.
4. Likely cause (hypothesis): the mine shadow comes from mesh or alpha before burial cleanup (dropped slivers and soil-covered parts still cast shadow); `disturbed_patch` blur probably causes the ghost.
5. Fix scope: remove shadow and outline traces of the hidden part only. Don't remove the exposed part's own shadow, the soil effects or the burial; acceptance is checked on re-rendered b004.
