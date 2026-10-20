# 0009: burial round 4, ragged ground-textured edge (implemented, then rejected by the user)

Date: 2026-10-20 (feedback 06:39Z = 02:39 EDT; commit 02:47 EDT; rejection 06:51Z = 02:51 EDT)

## Context

After round 3 (ADR 0008) the user said the dark-grass case "still looks wrong" (feedback 0023; screenshot in ADR 0008) and, in the same message, asked for the review grid to be 48 cards instead of 360 (ADR 0010). The assistant's reading of the screenshot, sent to the generator agent:

- the covered edge is still one smooth blurry diagonal sweep of the silhouette (the mine looks faded or cut, not covered by soil);
- two dark clod blobs near the bottom right look like holes or dark stains with hard outlines;
- the exposed mine body looks flat, low-contrast and blurry compared with the burial-off crop;
- no soil texture (grain, small stones, grass bits) overlaps the mine edge, so there is no transition from mine to ground.

## Decision

Flag `BURIAL_RAGGED_EDGE`, committed as `61b6a85`:

- the soil-cover ramp is dithered against clustered multi-scale grain noise, so the transition is made of crumbs with grainy partial coverage (0.35 px anti-aliasing only);
- crumbs spill onto the exposed mine up to `BURIAL_CRUMB_REACH` = 6% of the mine length, density falling off with distance;
- the cover copies the actual (unblurred) ground pixels under the mine, so the covered area continues the surrounding ground;
- only soil connected to the buried part is kept;
- clods become smaller and more numerous (`BURIAL_CLOD_SIZE_FRAC` 2.5-6%, `BURIAL_CLOD_COUNT` 4-10), colour- and brightness-matched to the ground, with weaker shorter shadows;
- the ridge comes and goes along the line (low-frequency mask);
- the exposed part keeps more contrast (`EXPOSED_DARKEN` 0.03-0.10, `EXPOSED_DESAT` 0.05-0.15, `EXPOSED_FILM` 0.05-0.15).

Tuned on gravel, dark grass, light dry grass and bare soil at 6x; tests pass (1-2 px structures 0.3-1.9% of visible pixels, from the intentional crumbs, limit 6%).

## Why the user rejected it

The user's words (feedback 0024, verbatim copy there): "now it looks unnatural. also, in this example the old one actually looks better since it's more believable", "the burial edge should be wavey to look more natural instead of it being a straight line", "spawn clods/crumbs but limit their number and vary their size more. also, don't spawn them around the entire mine since it looks "forced" in that it's too uniform".

![gravel case after round 4: old 40% / new 40% / new 40% with blades](images/0024-burial-unnatural-wavy-edge-1.jpg)

In the screenshot the crumb dithering and lip show up as a dark, beaded, dotted ring all the way around the exposed outline, evenly spaced and of similar size, which reads as a decorative outline rather than soil. The assistant agreed ("The dotted ring of crumbs and the dark rim around the whole outline look forced, and the old 40% column was more believable"). The old 40% version had no such ring. Assessment (this author's reading, consistent with the user's wording): the effect was uniform in space (the same crumb treatment everywhere along the outline, not only where soil is piled) and uniform in size (smaller but more clods), the opposite of what the user asked for.

## Decision going forward (requested, not implemented in the logged session)

Instructions sent to the generator agent at 06:51Z:

1. Treat the OLD 40% look as the believability baseline; new effects only add subtle, localised disturbance on top of a clean wavy soil line.
2. The soil-line offset should be a sum of several sin and cos waves with different amplitudes and frequencies (random phases, per-mine parameters) plus noise on top, replacing the fBm wander of round 3 as the primary shape.
3. Limit the number of clods/crumbs, vary their size much more (a few larger, several small), and place them only near parts of the soil line in irregular clusters, none along the outer outline of the exposed part; remove the dark dotted rim and the thin dark contact band around the silhouette.
4. Keep the 50% cap, the sliver clean-up and the `render_scene` API; re-tune on gravel, bare soil, dark grass, light grass at 6x.
5. The user also said not to restart the review grid yet, because they would send more examples from it (see ADR 0010).

## Consequences

- At 06:55Z the user stopped the two running background agents ("Build realistic generator v2" and "Build v2 showcase images and manifest") while clarifying the grid misunderstanding. The generator agent was partway through the wavy-edge fix and could not be resumed ("stopped by the user and won't be resumed"); a replacement was not launched without the user's say-so, and the assistant offered to start one once the user sent their grid screenshots.
- No commit for the sin/cos wavy edge exists in `git log`. The ragged-edge code from `61b6a85` is therefore still the committed default (`BURIAL_RAGGED_EDGE`), and `docs/CHANGES.md` still documents it as the fourth round without noting the rejection.
- The assistant said the generator agent's partial wavy-edge edits are uncommitted in `controlPanel.py`, `features/burial_fx.py`, `features/soil.py`, `objects.py` and `scripts/burial_realism_figure.py`; `git status` still shows modifications to those files and regenerated sheets. They were deliberately not touched or examined for this history.
- At 07:20Z the user said they had written enough notes in the grid and were ready to regenerate (a 24-card grid next); those notes could not be read (ADR 0010).

## Feedback that triggered this

- [0023 burial still wrong, grid 48](feedback/0023-burial-still-wrong-grid-48.md)
- [0024 burial unnatural, wavy edge](feedback/0024-burial-unnatural-wavy-edge.md)
- [0025 grid confusion and clarification](feedback/0025-grid-confusion-and-clarification.md) (context for stopping the agents)

## Commits

- `61b6a85` 2026-10-20 02:47:08 -0400 feat: ragged burial edge with ground-textured cover and matched clods
