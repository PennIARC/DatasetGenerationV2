# 0001: v2 baseline import

Date: 2026-10-20 (decision about 00:01-00:07 EDT; commit time is an estimate, see Commits)

## Context

The sibling detector project `kernelBashing` (fixed mine-template kernels, one conv layer, small learned head) reached held-out AP 0.456 only after switching to per-channel colour templates. The diagnosis was that real-looking mines differ from the background by hue, and the synthetic mines are teal on brown grass. That result could be a property of the v1 generator rather than of real PFM-1 mines (a small Soviet plastic anti-personnel mine). The user's stated worry: "my main concern is to just not overfit to our dataset, especially since the dataset is generated and may not match reality".

Inspection of the v1 generator (`PennIARC/IARCdatasetGeneration`, local copy under `~/PycharmProjects`) found:

- only 50 pre-rendered mine sprites (`NUM_ANGLES = 50`), colour baked in, barely varied (dark olive, green always highest channel);
- 15 background photos, 15 rocks, 5 grass snippets; post-process is noise, chromatic aberration, vignette, contrast only (no blur, white balance, exposure, JPEG);
- hard nearest-neighbour sprite edges, no cast shadows, hard brown dirt squares instead of soil blending, no burial.

The user asked for these to be fixed first ("it may be worth it to first make the dataset itself better") and listed: sharp alpha edges, cast shadows, soil blending, partial burial, and randomised colours.

## Decision

- Create `IARCdatasetGenerationV2` as a sibling of `kernelBashing` (not a git clone, so no upstream history), copy the tracked files of the v1 repo into it, and run `git init` (explicitly requested by the user). All work happens there; the original clone stays read-only so v1 data can be regenerated for comparison.
- Answers given by the user to the planning questions: burial capped at about 50% so every mine stays labelled ("Bury at most ~50%"), and a "Realistic palette only" colour policy (olive, green, khaki, brown, tan with sun-bleach and dirt variation) instead of any-hue domain randomisation.
- First commit is the unmodified v1 import, so every later change is a diff against v1. Note this commit includes the stock-photo-watermarked v1 backgrounds and snippets; they are excluded at sampling time later (see ADR 0004), not deleted.

## Consequences

- v1 behaviour stays reproducible: every v2 feature has a flag and `main.py --v1` / `{"v1": True}` turns all of them off.
- Because the repo was created from a file copy there is no remote and no history before this commit.
- The user also asked for the existing `kernelBashing` runs to be committed separately with their timestamps as estimates; that happened in the other repo and is out of scope here.

## Feedback that triggered this

- [0001 dataset realism targets](feedback/0001-dataset-realism-targets.md) (04:01Z)
- [0002 location, burial and palette answers](feedback/0002-location-burial-palette-answers.md) (04:06Z)

## Commits

- `a3ffe4e` 2026-10-20 00:07:13 -0400 chore: import IARCdatasetGeneration v1 as baseline. The time is a rough backfill estimate (the user asked for "rough timestamps"), chosen to match when the repo was created (about 04:07Z).
