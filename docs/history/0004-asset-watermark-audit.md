# 0004: asset watermark and artifact audit

Date: 2026-10-20 (request 05:40Z = 01:40 EDT; results 05:44-05:51Z)

## Context

While reviewing the showcase the user noticed (point 5 of their comments) that "a lot of the images in the v1 dataset had watermarks" and asked for every image used to be scanned with Haiku subagents, one image at a time, for watermarks and other unwanted artifacts.

## Decision

- Build audit previews (backgrounds as image plus contrast-boosted view; cutouts magnified on grey / dark green / tan) and run 10 Haiku auditors over 186 images: 15 v1 backgrounds, 15 v1 rocks, 5 v1 grass snippets, 64 new non-procedural backgrounds, 34 new rocks, 24 leaf clumps, 29 dirt snippets. Procedural lawns and blades were skipped. Criteria: watermarks/text/logos, black or blank patches, non-top-down view, foreign objects, seams, banding, halos, flat/synthetic look. Verdict per file: keep / review / drop.
- Findings: all watermarks are in the v1 assets. Five v1 backgrounds carry stock-photo marks (alamy, shutterstock, Adobe Stock, dreamstime, ccpixx/shutterstock), one more v1 background is an oblique phone photo with a cable in view, `debris1.png` has a dreamstime mark and `debris2.png` has a leftover grey background and shadows. Net: 6 of 15 v1 backgrounds and 2 of 5 v1 grass snippets are out, 7 of 15 v1 rocks are "review". New assets had no watermarks, but many had artifacts: backgrounds 42 keep / 22 review, rocks 19/15, leaf clumps 11/13, dirt 24/5 (yellow dotted fringes, pixelated rocks, stamped patchiness repeats, wood-grain-like texture).
- Results are stored in `docs/asset_audit/` (per-batch JSON, `summary.csv`, `exclude.json`, `flagged_assets.jpg`, the scripts).
- Generator side, `ASSET_AUDIT_FILTER` (part of `V2_FLAGS`, so `--v1` still reproduces v1 exactly, watermarks included): files in `hard_exclude` are never sampled, `review` files get weight x 0.4, matching is by file name, `_rejected/` folders are never read, and the family weights (65/35) are applied before the item weights.
- Asset side, the asset agent then rejected 17 backgrounds (13 flagged ground/gravel textures and 4 real-grass mosaics with baked-in stamps), added 6 new real-grass backgrounds, removed bow-tie / aggregate / star-outline rocks, regenerated pixelated rocks, defringed leaf clumps and rebuilt dust snippets.

## Consequences

- Usable pool after the audit: 105 backgrounds (78 grass), 31 rocks, 21 leaf clumps, 30 dirt snippets; over 500 seeds, 65.6% grass backgrounds and 2.2% "review" backgrounds. Only `debris3-5` remain of the v1 grass snippets.
- The auditors' free-text counts were inconsistent and id/note pairing by view order may be off for some files; the fixed assets were not re-audited, and the procedural lawns and blades were never audited. A later re-audit of changed files was offered but not done.
- Regression test `tests/test_asset_audit.py` checks that no excluded or `_rejected/` file is drawn in 500 seeds per kind, and that v1 mode still samples the original set.
- A side question about why the batch subagents did not show in the user's agent panel was answered separately (no hidden flag was set) and is not part of this history.

## Feedback that triggered this

- [0016 burial feedback round 1](feedback/0016-burial-feedback-round1.md) (point 5 of that message)

## Commits

- `a6b2fbf` 2026-10-20 01:48:00 -0400 chore: add asset watermark audit results and exclusion list (backfilled estimate)
- `654fcf2` 2026-10-20 01:52:00 -0400 test: add burial and asset audit regression tests (backfilled estimate)
- The filter itself is in `e215f70` (ADR 0005); the cleaned asset files are in `5f3437e` (ADR 0003).
