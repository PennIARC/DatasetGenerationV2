# 0007: burial round 2, slivers and soil-displacement cues

Date: 2026-10-20 (feedback 05:59Z = 01:59 EDT; commit 02:15 EDT)

## Context

After round 1 (ADR 0006) the user looked at the new burial image and wrote three comments (feedback 0019):

1. "there is still a faint line at the top".
2. The burial is not believable: "no clear disturbance in the dirt around/over the mine ... it looks very obviously edited". Suggestions: more shadow work to show the dirt going up, the part of the mine that sticks out on the right end should be darker, and more dirt specks overflowing or covering other parts of the mine since a buried mine is unlikely to be clean everywhere else.
3. Be wary of blades of grass over buried portions: a blade partly over dirt and partly over the buried area would in real life be angled upwards because the dirt comes up slightly over the mine.

![the screenshot that came with these comments](images/0019-burial-feedback-round2-1.jpg)

## Decision

The generator agent was asked for believability that scales with burial depth, each behind its own flag, plus a regression test and a six-case before/after figure.

- Faint line: it was a thin wing rim grazed by the clip plane (1-4 px diagonal line and a detached wing-tip island). New `features/burial_fx.clean_mask`: after the clip, after the soil line and for the final label mask, a morphological opening with radius max(1 px, 0.025 x mine length) removes thin strips, and visible islands under 6% of the full area are dropped (the largest part always stays). Removed pixels count as buried.
- Cue strength scales with s = clip(burial fraction / 0.4, 0.25, 1.25): subtle for small burials, clear at 40-50%.
- `BURIAL_BERM`: a raised clumpy ridge along the clip line, sun-shaded, casting a short shadow onto the mine and ground.
- `BURIAL_DISTURBED_SOIL`: a darker, rougher, browner turned-soil patch on the ground around the buried part, drawn under the mine and its shadow. Turned soil also takes a brown soil tone (`BURIAL_SOIL_RGB`) so digging into lawn exposes earth.
- `BURIAL_CLODS`: 3-9 clods from the audited dirt assets scattered along and over the soil line, coloured towards the turned soil.
- `BURIAL_DIRTY_EXPOSED`: the exposed part gets an occlusion gradient at the soil line, is darker and less saturated, and carries grains, streaks and a dusty film whose density rises towards the buried side.
- `BLADE_SOIL_LIFT`, `BLADE_EMERGE`: blades that cross the soil line are warped upward by about 4% of the mine length, leave a soft shadow where they would have lain, and are partly covered by soil on the buried side so they look rooted.
- The clip plane hides 85% of the target fraction; the rough line, ridge and clods hide the rest, and the 50% cap is kept by bisection if needed (50-image sample: 63 buried mines, cap never exceeded, max hidden 0.50).
- Deliverable `docs/burial_realism.png`: gravel, dark grass, light dry grass, bare soil, face down, low/high sun; columns burial off, old 40%, new 40%, new 40% with blades. Tests extended in `tests/test_burial.py` (9 seeds/poses: no visible component below the minimum area, no line-like parts, under 6% of pixels in 1-2 px structures).

## Consequences

- Most of the module is already in the first generator snapshot; commit `fc741b9` holds the final tuning and the extended tests.
- Subtle versions of the cues were judged by the user in the next round to be still wrong in the dark-grass case: the soil edge remained a straight diagonal (ADR 0008).
- Cost: roughly 1.0 s/image (2.1x v1) with these cues.

## Feedback that triggered this

- [0019 burial feedback round 2](feedback/0019-burial-feedback-round2.md)

## Commits

- `fc741b9` 2026-10-20 02:15:29 -0400 feat: improve burial realism with berm, disturbed soil, clods and blade warp (real time; regenerated `burial_realism.png` and the contact sheets, CHANGES.md update, test additions)
- Earlier parts of this work sit in the snapshot `e215f70` (ADR 0005).
