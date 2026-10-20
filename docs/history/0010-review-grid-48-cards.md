# 0010: buried-mine review grid (360 cards, cut to 48)

Date: 2026-10-20 (request 06:00Z = 02:00 EDT; 48-card grid built 06:57Z; commit 03:08 EDT)

## Context

After the burial rounds the user wanted a systematic way to look at many cases and report failures: "once this is complete you should make a table in the html file showing a grid of images with buried mines so I can see if all of them look right and show you faillure cases", then "make the grid relatively large so I have a lot of them to look at (and make them varied)". The showcase builder (ADR 0002) got a third page type, "grid".

## Decision

- Review-grid page type (agent S3): tab "Review: buried mines", responsive card grid with a cards-per-row slider, a table view, per-card metadata (seed, background, sun elevation, burial fraction, face-down, blades), a lightbox, a flag toggle plus note per card persisted in the browser (localStorage, works without storage), "Copy flagged ids + notes" and "Download flagged.json", filters and sorting (background family, sun, burial fraction, face-down, blades, tags, flagged only).
- First scope was 250-400 cards, lazy-loaded; 360 were rendered, but before the irregular-line change (ADR 0008) so they were stale.
- At 06:39Z the user cut the scope: "the grid doesn't need to be so large, render 48 instead of 360". The builder agent was told to stop the 360-card re-render and `part7_review.py` / `manifest_review.json` now describe 48 varied items (same variety rules: backgrounds, suns, burial fractions, face-down, blades).
- Misunderstanding (06:51-06:57Z): the user said "don't restart the grid yet, I will send more examples from that". The assistant read that as stop everything and killed the refresh, which deleted most of the old 360 images; the page was left mostly broken. The user was confused ("how am I supposed to send screenshots from the grid if it doesn't exist and you stopped its generation?") and clarified that a 48-image grid had been in progress and the 360 grid was "from way earlier". The 48-card grid was then built (3 pages, 0 missing images) and opened at 06:57Z; the showcase agent had been stopped mid-render, so the assistant finished the render itself.
- Layout feedback on the built page (screenshot below): images should take the full page width, the per-image metadata should be removed or smaller, the note box and flag button larger, and images rendered at a higher resolution (nothing above what the real dataset would contain). Implemented.
- Further requests: "flip" buttons to show before/after burial and a bounding-box toggle; then notes without a length cap and with wrapping, smaller font, the two buttons side by side and the box toggle inside each image as a third button. Implemented (box alignment was checked offline on two cards; the page was not click-tested by the assistant). The user also noted the HTML was opened multiple times (a failed `sed` rebuild still ran `open` after a `;`, then the corrected run opened it again); rule added: put `open` last in an `&&` chain.

![the 48-card grid after the first build, with the layout the user commented on](images/0026-grid-layout-feedback-1.jpg)

Example cards are in `images/review48-*` (before/after pairs for b001, b002, b004, b019, b020); those files were placed there by another process, not by this backfill.

## Consequences

- The user typed failure notes into the grid. They are stored only in that browser's localStorage and were not exported, so they are NOT recoverable from the session log. At 07:20Z the user said they had finished about half of them and asked whether the assistant could read them. It could not; the assistant asked them to use "Copy flagged ids + notes" or "Download flagged.json" without refreshing the tab. The only text found on the clipboard was one line that may be unrelated: [0029 clipboard fragment](feedback/0029-clipboard-fragment.md) ("sand on top of mine doesn't blend into sand in the background"), kept with a provenance caveat.
- Next grid: 24 cards, with new ids so notes on the old ids `b001`-`b048` cannot collide, and not before the notes are exported.
- Open: failures found in the grid and the wavy-edge work (ADR 0009) are both pending at the end of the logged session.

## Feedback that triggered this

- [0020 review grid request](feedback/0020-review-grid-request.md)
- [0023 burial still wrong, grid 48](feedback/0023-burial-still-wrong-grid-48.md) (the 48 instead of 360 instruction)
- [0024 burial unnatural, wavy edge](feedback/0024-burial-unnatural-wavy-edge.md) ("don't restart the grid yet")
- [0025 grid confusion and clarification](feedback/0025-grid-confusion-and-clarification.md)
- [0026 grid layout feedback](feedback/0026-grid-layout-feedback.md)
- [0027 grid flip and bbox buttons](feedback/0027-grid-flip-and-bbox-buttons.md)
- [0028 history docs request](feedback/0028-history-docs-request.md) (asks to reduce the next grid to 24 images and to keep typed notes verbatim)
- [0029 clipboard fragment](feedback/0029-clipboard-fragment.md)

## Commits

- `c831415` 2026-10-20 03:08:13 -0400 feat: add 48-card burial review grid with flip, boxes and notes (`manifest_review.json`, `template.html`, `part7_review.py`, rebuilt `showcase.html`)
