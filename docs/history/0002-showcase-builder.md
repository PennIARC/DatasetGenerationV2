# 0002: HTML showcase builder

Date: 2026-10-20 (request 04:17-04:19Z = 00:17-00:19 EDT; builder delivered about 04:23Z)

## Context

The assistant had started a /grillMe interview about each planned v2 feature (sun elevation, shadow strength were answered; see ADR 0005). The user interrupted it and asked for something visual instead: an HTML file with different options and before/afters for each addition, one page for v1 and one for v2, "so I can visually see implementations of each feature", built with 3-4 Sonnet subagents in parallel. They also asked for more background, grass, rock and dirt images (ADR 0003) and for an explanation of the pose_sphere / pose_renders figures.

## Decision

- Split the work by manifest: one agent renders v1 feature images and a manifest, one agent builds the asset pool, one agent writes a generic manifest-driven page builder (`docs/showcase/build_showcase.py` plus `template.html`), and a fourth later renders the v2 features.
- The builder produces one self-contained `showcase.html`: tabs per manifest, lightbox, before/after slider, glossary, light/dark theme. Page types are chosen from the manifest, so a later "grid" manifest (`manifest_review.json`) becomes a third tab automatically (ADR 0010).
- v1 page content: 10 features, 62 images, 21 glossary terms. The v1 survey also surfaced quirks of the original generator: grain only survives in the green channel (the chromatic-aberration step overwrites red and blue after noise), about 20% of images are empty rather than 10%, boxes ignore occlusion, `density_factor` is never varied.
- Generated images are not committed (regenerable by the scripts); the manifests, scripts and built HTML are.

## Consequences

- Every later feedback round could be shown as a before/after in the same page instead of through ad hoc contact sheets.
- Drag, touch, lightbox and dark mode were not tested in a real browser by the builder agent; the user's later layout feedback (ADR 0010) found the rest.
- v2 page grew from 11 to 13 features (205 to 215 images) as features were added, including rock seating and the asset audit.

## Feedback that triggered this

- [0005 grill request on new variations](feedback/0005-grill-new-variations-request.md) (the interview that was interrupted)
- [0007 HTML showcase request](feedback/0007-html-showcase-request.md) (04:17-04:19Z, includes the interrupt and two near-identical sends)

## Commits

- `49d1a81` 2026-10-20 00:27:00 -0400 docs: add HTML showcase builder and v1 page (backfilled estimate)
- `afd4ede` 2026-10-20 01:15:00 -0400 docs: add v2 showcase page (backfilled estimate; manifest_v2, rendering scripts, built showcase.html)
