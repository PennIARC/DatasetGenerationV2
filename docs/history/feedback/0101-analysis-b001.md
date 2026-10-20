# 0101 - Analysis of review note on card b001

Card: b001 (seed 5001, `grass_bg_gen_23_grass_dry_normal`, sun 50.2 deg, burial 0.41, face_down False, blades 4, dust 0.38).
Images: `../images/review48-b001-after.jpg` (burial on), `../images/review48-b001-before.jpg` (burial off). 480x270 native-pixel crops; the whole frame is soft/blurred in both, so fine edges are hard to judge.

## 1. What the user literally says (separate claims)

- **C1.** The burial is "relatively convincing".
- **C2.** The only part that isn't believable is that the mine should "weigh into the grass" more *in this specific scenario*. The user calls this an "unsolvable problem with the background image".
- **C3.** Fixing C2 would need to know what the material is at each location in each image, and the user says that is **not worth doing**. So C2 is not a fix request.
- **C4.** The real issue: because of the **blades on top of the mine**, the mine ends up about **80% buried/hidden**.
- **C5.** That may be too hard for any model to learn.
- **C6.** Decision: **leave this as is for now**. See whether models learn it anyway. If they don't, "we can figure out a solution" later. No specific fix is proposed or approved.

## 2. Visual evidence per claim

Mine location (both images): a pale olive PFM-1 near the centre. The upper lobe is at about x 200-235, y 85-150. The lower wing is at about x 240-315, y 150-210. The only pixels that differ between before and after (|diff| > 12) are inside x 193-333, y 69-223, about 6.5k px. The rest of the frame is identical.

| Claim | Evidence | Confirmed? |
|---|---|---|
| C1 convincing burial | In "after", the lower wing is fully replaced by a dark brown soil patch. Mean RGB goes from (94,86,48) to (58,48,27), and the texture std drops from 17 to 9. The patch tone is close to the dark gaps between the straw stems, so it reads as ground and not as a pasted blob. The upper lobe stays visible and is slightly darkened, from (73,68,39) to (69,63,37), which matches the "dirty exposed part" effect. No hard seams are visible at this resolution. | Consistent with the image. This is a subjective judgement and I have no reason to dispute it. |
| C2 weight into the grass | The background is a thick mat of dry straw/needles with no visible bare soil. In both images the exposed lobe sits *on top of* the stems. Nothing shows the stems being pressed down or parted around the mine, and the soil patch sits on the mat without the stems bending into it. That is the "not weighing into the grass" look. | Plausible, and visible as an absence of deformation. It is specific to this thick-mat background. |
| C3 not worth fixing | This is a judgement call, so there is no visual evidence to check. | n/a |
| C4 blades on top give ~80% hidden | Soil alone (metadata burial 0.41, cap 0.5) hides the lower wing, about 40% of the silhouette. What remains visible is mainly the upper lobe. Several long over-layer blades (green and straw-coloured) cross that lobe: one along its top edge, plus the converging bundle at about x 230-270, y 90-200 that runs down its right side and over the buried wing. My rough estimate is that only about 20-30% of the mine silhouette is still clearly readable in "after", which matches the user's "like 80%". In "before" the same blades cross the mine, but the large pale wing is still visible, so the mine stays easy to see. The diff image also shows the blades over the buried region rendered differently (dimmer) in "after", which fits the blade-emerge effect. | Confirmed qualitatively. "80%" is the user's estimate. I can't measure it exactly from a blurred JPEG, and my estimate is in the same range. |
| C5 too hard to learn | The remaining visible lobe has almost the same mean colour as the background straw (bg grass mean (74,67,34) vs lobe (69,63,37)). It stands out only by being smoother. Under the blades that cue is weak. | Plausible. This is a prediction about model training and cannot be verified from the image. |
| C6 leave as is | Decision only. | n/a |

## 3. Likely code causes (hypotheses, not verified by running)

- **H1 (main): the burial cap ignores grass occlusion.** `objects.py`, buried-mine draw (about lines 455-534), enforces `BURIAL_MAX_FRACTION = 0.5` (`controlPanel.py:241`) on soil/clip coverage only. The over-layer blades are drawn later, in `EnvironmentDebris(..., layer="over")` (`scene.py:62`). So soil (up to 50%) and blades stack, and the total hidden fraction is never capped. That would explain how 0.41 burial plus blades can reach about 80% hidden.
- **H2: extra blades are aimed at mines.** `objects.py::_generate_blades` (lines 80-97) adds `BLADES_ON_MINE_COUNT = (1, 4)` blades with probability `BLADES_OVER_ON_MINE = 0.6`, centred inside the mine box expanded by `BLADES_ON_MINE_EXPAND = 0.2` (`controlPanel.py:306-308`). This card has "blades 4", the maximum. Their placement doesn't depend on burial, so they can land on the small exposed part.
- **H3 (minor contributor): the exposed part is darkened.** `burial_fx.dirty_exposed` (`BURIAL_DIRTY_EXPOSED`) darkens and desaturates the exposed lobe a little. This further lowers its contrast against straw-coloured blades.
- C2 (weight into the grass) has no specific code cause. Nothing in `soil.py`/`burial_fx.py` deforms the background, and the user says that is not worth doing.

## 4. What the user did NOT say (over-generalisations to avoid)

- They did **not** ask for any change now. The explicit decision is "leave this as is for now". Don't implement a fix on the basis of this note alone.
- They did **not** say burial is bad, too strong, or that `BURIAL_FRACTION`/`BURIAL_MAX_FRACTION` should be lowered. They called the burial convincing.
- They did **not** say blades on mines are bad in general, or that `BLADES_OVER_ON_MINE` / `BLADES_ON_MINE_COUNT` should be reduced or disabled. The problem is the *combination* of burial and blades in this case.
- They did **not** say every mine must be X% visible, or give a new numeric cap. "80%" describes this card, not a target.
- They did **not** ask for background-aware deformation (stems pressed down, mine sinking into the mat). They called that unsolvable and not worth doing. Don't start material segmentation or similar work.
- They did **not** generalise C2 to all backgrounds. It is "this specific scenario" (thick dry straw mat).
- They did **not** say models will fail. It is a "may be". Whether to fix depends on future training results.
- They did **not** comment on colour, dust, shadows, sun, the soil patch colour or the edge quality, so treat those as acceptable or unreviewed. Don't change them on the basis of this note.

## 5. Narrow, testable acceptance check (only if the user later asks for a fix)

The trigger is training results showing the model misses heavily buried and grass-covered mines. Then:

- Compute per mine the **total hidden fraction** = 1 - (final visible-mask px, after soil AND over-layer occlusion) / (full silhouette px). Log it in the metadata next to `burial`.
- Check: on a regenerated seed-5001 b001 (same background, burial 0.41, 4 on-mine blades), plus a batch of N >= 200 buried mines, the total hidden fraction stays at or below an agreed cap. The cap value is for the user to decide; it is not set here.
- Non-regression: for mines with burial off, or with no on-mine blades, the output is pixel-identical to the current output. The soil look on b001 (lower wing under dark soil, slightly darkened exposed lobe) is unchanged, and the user still rates it "relatively convincing".
- Out of scope: any background deformation or "weigh into the grass" change.

## Summary

1. The user rates b001's burial "relatively convincing". The only flaw they name, that the mine doesn't weigh into the grass, is called unsolvable and not worth fixing.
2. The real concern is that soil (about 40%) plus the blades on top hide about 80% of the mine. The image supports this: the lower wing is fully under soil and blades cross the remaining lobe.
3. Code hypothesis: `BURIAL_MAX_FRACTION` (objects.py) caps soil only. On-mine blades (`_generate_blades`, `BLADES_OVER_ON_MINE`) are added later, so nothing caps the two together.
4. The explicit decision is to leave it as is and fix only if models fail. No burial/blade parameter changes, global visibility rule or background-deformation work is implied.
5. If a fix is requested later: log the combined hidden fraction per mine and cap it at a value the user picks, with pixel-identical output for un-buried or blade-free mines.
