# 0008: burial round 3, organic soil line

Date: 2026-10-20 (feedback 06:27Z = 02:27 EDT; commit 02:36 EDT)

## Context

Looking at the dark-grass case in `docs/burial_realism.png` (the output of ADR 0007), the user wrote (feedback 0022): "i think it would help if the burial line wasn't so straight", and said the straight line was why the extra dirt patches on top of the mine did not blend into the existing dirt covering the right side of the mine.

![dark grass case, burial off / old 40% / new 40% / new 40% with blades](images/0022-burial-line-too-straight-1.png)

## Decision

Flag `BURIAL_IRREGULAR_LINE` (default on). The soil surface is no longer the clip plane itself but the plane plus a wander of U(0.015, 0.04) mesh units x sqrt(fraction / 0.4) (clipped 0.5-1.2), built from three fBm (fractal noise) layers at 0.35, 0.12 and 0.04 of the mine length with weights 0.6 / 0.3 / 0.1 (slow wander, bays, small lumps) on top of the existing fine edge noise. The 3D clip runs at the lower envelope of that surface and the per-pixel soil cover decides the rest. The ridge, clods, occlusion gradient and blade lift follow the irregular edge. For blending, the soil cover, ridge, clods and dirt take their colour and texture from the ground as it looks under the mine after the turned-soil patch is drawn, the cover uses the ground colour itself with only the lip darker, and its alpha is feathered 0.6 px. The 50% cap check now includes the fragment and final label clean-ups.

While this was running, the review-grid builder (ADR 0010) was told to wait for the final images rather than render the 360-card grid against the old look.

## Consequences

- The user's reaction to the result, with a new screenshot of the same dark-grass case (hidden 0.44), was "this one still looks wrong" (feedback 0023): the covered edge was still one smooth blurry diagonal sweep and two dark clod blobs near the bottom right looked like holes. That led to round 4 (ADR 0009).
- Round 3 changed the edge geometry and blending but kept a smooth feathered soil cover, which is what round 4 then targeted.

![after round 3: "this one still looks wrong"](images/0023-burial-still-wrong-grid-48-1.jpg)

## Feedback that triggered this

- [0022 burial line too straight](feedback/0022-burial-line-too-straight.md)
- [0023 burial still wrong, grid 48](feedback/0023-burial-still-wrong-grid-48.md) (the reaction to this round)

## Commits

- `dd3c4da` 2026-10-20 02:36:36 -0400 feat: irregular burial soil line with seamless soil blending
