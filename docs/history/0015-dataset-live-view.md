# 0015: dataset live view (fifth showcase tab + local server)

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

## Context

The 3000-image v2 dataset (ADR 0013) was about to be rendered in the background into `output_dataset/v2_3000`. The
user asked: "make a fifth tab to see a grid of 24 randomly sampled images from the dataset (and make it work as the
dataset is being generated as well). at the top it should show info about the dataset (image count, storage size,
timestamp, etc.) and buttons for things like toggling bounding boxes" ([0103](feedback/0103-dataset-live-view-request.md)).

The showcase is a single offline HTML file, and a `file://` page cannot list or read the dataset folder, so a live
view needs something that can read the disk.

## Decision

- `scripts/serve_dataset_view.py`: a stdlib `http.server` on 127.0.0.1:8765 (read-only, Host header checked, strict
  regex routes so only images / labels / sidecars of the dataset are reachable). JSON endpoints `/api/dataset-info`
  (count / target, pending, train/val, storage, first/last image time, rate and ETA, status, resolution, box counts,
  failures from `render_log.json` and any `*.log`) and `/api/sample?n=24&seed=` (boxes + key sidecar values).
  `--dataset-dir`, `--cache-dir`, `--port`, `--target` make it testable on fake data.
- "Finished" = label file and sidecar exist and the sidecar parses (the generator writes jpg, txt, then json), so a
  render in progress is never counted or shown. Parsed sidecars are cached by mtime/size; scans are cached for 2 s.
- Thumbnails (960 px, Pillow, JPEG draft decode) are cached in `output_dataset/.thumb_cache/` (already gitignored via
  `output_dataset/`); the full 1920x1080 image is loaded only when a card is enlarged.
- New page type `"dataset"` in `template.html` (`renderDataset`) and `manifest_dataset.json`; `build_showcase.py`
  only gained the tab name and picks up the optional manifests (review, params, dataset) by default. The lightbox
  got an optional box overlay (`b` key). Other tabs are unchanged and still work from `file://`.
- Toolbar: Boxes on/off, Resample 24, Auto-refresh (info every 10 s; the sample stays stable and shows how many new
  images exist since it was drawn; an empty grid fills itself when the first images appear), Parameters shown/hidden,
  Refresh info, cards per row.

## Consequences

- Viewing the live tab needs `python3 scripts/serve_dataset_view.py` running; opened as a file the tab shows that
  command and the link instead.
- Rate / ETA are inferred from file modification times (last 10 min), so they need at least 2 finished images and are
  shown only while files keep appearing ("generating" = newest image < 60 s old). Failures are only known once the
  generator writes `render_log.json` at the end of the run (or if its stdout is redirected to a `*.log` in the dataset dir).
- The first info request parses every sidecar once (cached afterwards); storage size walks the dataset dir every 5 s.
- Tested on a fake 30-image dataset (plus a half-written image and a truncated sidecar) and an empty one:
  `docs/showcase/test_fixture/dataset_view_test.py` (57 headless-Chrome checks) and a concurrency run (4 threads,
  1609 requests while 20 images and a partial sidecar were being added: 0 errors). Not yet run on the real render.

## Commits
