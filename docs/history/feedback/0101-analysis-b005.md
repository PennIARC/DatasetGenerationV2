# Analysis: card b005 (review grid 48)

Card: seed 5005, `ground_bg_Ground005`, sun elevation 35.1, burial 0.42, face_down False, blades 2, dust 0.32
(metadata from `0102-review-grid-48-new-notes.md`).
Images: `../images/review48-b005-after.jpg` (burial on), `../images/review48-b005-before.jpg` (burial off). Both are 480x270 native-pixel crops.

User note (verbatim):

```
very convincing but a straight line, although the line is along the ridge in the middle of the mine which is believable since it's a real height different in the STL file so it's fine
```

## 1. What the user literally says

- C1: The card is "very convincing" overall.
- C2: The soil line (burial edge) is a straight line.
- C3: The straight line runs along the ridge in the middle of the mine.
- C4: That ridge is a real height difference in the STL geometry, so a straight edge there is believable.
- C5: Verdict: "it's fine". The straight line is accepted for this card, and the user asks for no change.

## 2. Visual evidence

I compared the after and before crops, a 4x zoom of the mine region (x 180-330, y 80-230), and an after-vs-before absolute difference map.

- C1 (convincing): consistent with the images. The difference map shows that burial changed only two things. (a) The long lower-left wing of the PFM-1, roughly x 195-265, y 160-215, is completely replaced by ground-coloured soil. The soil there is barely distinguishable from the surrounding sand, with a few slightly darker specks (possibly disturbed soil or clods; I can't tell at this resolution). (b) The cast shadow on the right is shorter. The visible upper body keeps its colour and shading. No obvious seam, halo or ring of soil appears around the visible outline. Confirmed, within the limits of a blurry 480x270 crop.
- C2 (straight line): confirmed. The upper edge of the buried region, where the visible body meets the soil, runs roughly diagonally from about (207,152) to (262,165) in crop pixels. Over that span it shows no visible waviness on the scale of the wander waves. The only irregularity is near the right end, around (265-275, 160-170), where a small lobe of the body stays visible.
- C3 (along the middle ridge): plausible, but I can only partly confirm it. In the before image, the edge sits where the wide upper body meets the narrower lower wing, at the step/fold of the PFM-1 shape. The after-image soil line follows that same boundary. From a top-down 2D image alone I cannot confirm that this boundary is the height ridge, because the crop has no height information.
- C4 (real height difference in STL): I cannot verify this from the images. It is the user's statement about the mesh. It agrees with the code: the edge is chosen from per-pixel surface height (see section 3), so a sharp height step would produce exactly this result.
- C5 (fine): this is a judgement, not something to verify. The user is not asking for a fix on this card.

## 3. Likely code causes (hypothesis; nothing changed)

- `features/mesh.py::render_mine`: the clip plane `n_pl . p = c_pl - wander` (`clip_triangles`) is chosen so that a quantile of the top-down visible surface lies below it. If the mesh has a near-vertical step between the body and the wing, every pixel on the low side falls below the plane and every pixel on the high side stays above it. The plane-mesh intersection then projects onto the step's outline, which is a straight crease in the STL, and not onto a contour across a gentle slope.
- `features/soil.py::burial_overlay`: the wavy soil surface `surf = A * wf` (sum of sine/cosine waves plus fBm noise, amplitude `wander`, from `BURIAL_LINE_WANDER = (0.025, 0.06)` mesh units scaled by sqrt(f/0.4)) is compared against the per-pixel height `hgt` (`cover = clip((surf + amp*n1 - hgt)/...)`). Where the height jumps by more than about 2xA across one or two pixels, the zero crossing of `surf - hgt` is pinned to the step whatever the wave phase is. The waviness disappears there, and the edge takes the shape of the geometry.
- With burial 0.42 and `BURIAL_CLIP_SHARE = 0.85` (controlPanel.py), the clip hides about 36% of the area. That is roughly the whole lower wing, which makes it likely that the plane lands right at the body/wing step.
- Contributing: `features/burial_fx.py` berm / dirty_exposed effects are drawn along `soil_line`, so they follow the same straight edge. At this resolution I see no distinct berm.

These are hypotheses from reading the code. I did not re-render seed 5005 or dump its height map.

## 4. What the user did NOT say (avoid over-generalising)

- The user did NOT say the burial line is too straight in general, and did NOT ask to revisit the wavy-line logic (`BURIAL_IRREGULAR_LINE`, `BURIAL_LINE_WANDER`). Earlier complaints (0022 "line too straight", 0024 "unnatural / should be wavy") are separate and must not be re-applied based on this card. This card is an accepted case.
- The user did NOT ask to break up straight edges that follow real mesh height steps. The note explicitly endorses them ("believable", "it's fine"). Adding extra wander or noise to force waviness along a geometric ridge would go against this note.
- The user did NOT comment on the shadow, the soil colour, the clods, the berm, the grass blades, the dust, or any "floating" look. The floating complaint belongs to b008, not b005. Checking the b005 before image anyway: the mine's shadow is attached directly to its right edge (sun from the left), and I see no visible gap, so I see no floating effect in either image. If anyone raises floating for b005 later, it would not be caused by burial, since the before image has the same contact/shadow setup.
- The user did NOT say whether the hidden lower wing is too much burial. Burial 0.42 is close to the 0.4-0.5 "clearly visible" range, and the user called it convincing.

## 5. Narrow acceptance check

Any future burial change must keep b005 acceptable:

1. Re-render seed 5005 with the same config. The after image must still hide the lower wing, with the soil line along the body/wing step and the visible body unchanged versus before (difference map ~0 on the visible body pixels).
2. Regression guard: compute the soil line (`burial_fx.soil_line`) for seed 5005 and the height-gradient magnitude along it. If the median |grad h| along the line is high (a step edge), a straight line is acceptable and no test should flag it. A straightness metric (e.g. RMS deviation of the line from its best-fit straight line, in px) should only be enforced where the line crosses low-gradient surfaces.
3. No change is required for b005 itself. Pass = the user still rates it convincing in the next grid.
