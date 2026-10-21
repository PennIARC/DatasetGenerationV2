# 0019: live test examples on the Training tab (+ table alignment pass)

Date: 2026-10-21 (uncommitted at the time of writing; the lead commits)

## Context

While the second YOLO11n session (`runs/2026-10-20_232733_wide-960-10ep`, v2_3000_wide 960x960, imgsz 960, batch 8,
Apple GPU) was running, the user asked: "you should show live test examples on
http://127.0.0.1:8765/showcase.html#training as well", and then revised the image choice: "can't you just sample
randomly from the most recent validation set and show 16 of those?"
([0107](feedback/0107-training-live-predictions-request.md)). A side request asked for matching header / cell
alignment in tables across all tabs ([0108](feedback/0108-table-alignment-request.md)).

Ultralytics saves `ultra/weights/last.pt` after every epoch, but only `last.pt` / `best.pt` are kept, so predictions
for an epoch have to be made while that epoch's `last.pt` exists. The training process owns the GPU; anything else
must stay out of its way.

## Decision

- A separate watcher, `kernelBashing/baselines/yolo11n/scripts/live_predict.py <run>` (stdlib + the venv's
  ultralytics), not a training callback: it runs on the CPU only (2 torch threads, `nice -n 10`), so it cannot slow
  the GPU step or crash the run, and it works for runs that were started without it.
  - Image set: a uniform random sample of 16 images of the run's val split (dataset and imgsz from the run's
    `config.json`), seed recorded, picked once and kept fixed so epochs are comparable. Empty images, small mines,
    buried mines etc. appear at their natural rate (a stratified pick was built first and dropped after the revision).
  - Each time `last.pt` changes (size / mtime unchanged over 3 s, copied to a temp file and re-checked, so a
    half-written file is never loaded): predict at the run's imgsz, keep boxes with conf >= 0.1 (ultralytics' default
    NMS), write `live_preds/epoch_<NN>.json` (epoch from the checkpoint, else the `results.csv` row count) and
    `latest.json`: boxes + confidence, GT, per-image TP/FP/FN at conf 0.25 / IoU 0.5, set precision / recall,
    inference seconds. All epoch files are kept (a few KB each).
  - End: when `config.json` gets a final status, `report.md` appears, the `--parent-pid` is gone, or nothing changed
    for `--idle-exit` (3 h): one pass with `best.pt` as `epoch_final.json`, then exit. `--once` = only that pass.
  - `train_yolo.py --live-preds` (default on) spawns it as its own session with nice 10 and 2 threads.
- 'Resample 16': `POST /api/training/resample?name=R` (Host and Origin checked, run name validated, one request per
  run per 20 s) only writes `live_preds/resample_request.json` with a new random seed. The watcher archives the current
  set + its epoch files into `live_preds/archive/set_seed<S>_<time>/`, samples a new 16 and predicts them with the
  current weights (last.pt; best.pt for a finished run); history for the new set starts there. If no watcher is alive
  (`predictor.pid`), the server starts `live_predict.py <run> --handle-request` under nice; the server never imports
  ultralytics or torch.
- Server (`scripts/serve_dataset_view.py`), read-only otherwise: `GET /api/training/preds?name=R` (set without dataset
  paths, epochs, per-epoch summaries, predictor running / resample pending / archived sets),
  `GET /api/training/preds?name=R&epoch=<n|latest|final>`, `GET /training-img/<run>/<k>.jpg[?full=1]`: image k of the
  run's `set.json` only, only when `set.json`'s dataset root equals the run's `config.json` dataset root, only paths
  matching `images/<split>/<name>.(jpg|jpeg|png)`, realpath inside that root; 640 px thumbnails in the thumbnail cache.
  The run's SSE stream sends a `preds` event (with the index) whenever `live_preds/` changes.
- Page (`template.html`, `livePredsView` inside the Training tab, between the curves and the report): 16 cards with GT
  boxes (green, thin; dashed when missed) and predictions (red with conf; dashed when they match no mine), confidence
  slider (client-side, default 0.25), GT / prediction toggles, epoch slider + prev / next / "Latest" (follows new epochs
  until the user scrubs), "epoch k of N", per-card TP/FP/FN badges and the summary line computed in the browser with the
  same greedy IoU 0.5 matching as the predictor, a precision / recall vs epoch chart (labelled axes), lightbox on click,
  legend, glossary entries (GT, conf, TP / FP / FN, NMS). Empty states: waiting for the first epoch, no predictor
  watching (with the start command), finished run without predictions (with the `--once` command).
- Table alignment: a column whose cells are all numbers (with optional unit, blank or "–") is right-aligned with
  tabular figures, header included; other columns are left-aligned, header included (`dataTable`, the review table
  view, the per-epoch metrics table). Also: toolbar rows bottom-align labelled fields with buttons and give inputs /
  selects the button height; stat tiles keep "box 0.779", "12.0 s", "mAP50-95" unbroken.

## Consequences

- The running wide-960-10ep session got its watcher after epoch 5, so its history starts at epoch 6 (earlier
  `last.pt` files no longer exist). first-10ep only has `epoch_final.json` (best.pt, `--once`).
- Cost per pass on the M4 CPU: 2.1-3.9 s for 16 images at 960 px (1.6 s at 640 px), about 0.5 GB peak memory, idle
  (one `stat` every 15 s) between epochs. wide-960-10ep train seconds per epoch: 1-5 (no watcher) 219-232, 6 = 225,
  7-10 = 237-243 (5-8 % slower). The watcher was busy for about 3 s of each ~240 s epoch, so most of that is other
  load at the same time (the user's Chrome with video decoding, WindowServer, and this change's headless-browser
  checks), but it cannot be separated exactly from one run.
- Results: wide-960-10ep has epochs 6-10 + final (best.pt = epoch 10: P 0.953, R 0.953 on its 16 images at conf 0.25);
  first-10ep has final only (P 0.962, R 1.0).
- A server started before this change has none of these routes (the section says so); it must be restarted.
- Resample on a run whose watcher has exited needs the yolo11n venv next to the runs folder (`--predictor-dir`).

## Tests

- `docs/showcase/test_fixture/training_view_test.py`: 119 checks, 0 failed (was 66). New: preds index / epoch API,
  bad epoch values, image whitelist (thumbnail 640 px from a 960 px set, `?full=1`, 640 px set as is, out-of-set ids,
  traversal, tampered `set.json` with `..`, a labels path or a foreign dataset root), SSE `preds` events, epoch files
  growing during a fake live run, POST-only resample with Host / Origin checks, rate limit, archive + new seed via
  `fake_live_predict.py`; in Chromium: 16 cards, boxes, badges, summary = sum of badges, epoch auto-advance, scrub
  stops following, confidence slider, GT toggle, lightbox, chart axis labels, glossary, finished run with final only
  (960 px), Resample button, run without predictions, phone width, and th / td alignment per column on the training,
  parameters and review-table tabs. Plus a read-only check on the real runs folder.
- Unchanged suites still pass: run_tests.py (ALL OK), chrome_test.py 18/18, dataset_view_test.py 59/59,
  dataset_switch_test.py 31/31.
