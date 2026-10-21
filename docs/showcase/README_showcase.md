# Showcase builder

Builds one offline HTML file with tabbed pages (v1, v2, review grid, dataset parameters, dataset live sample, training live) from JSON manifests.

    python3 build_showcase.py                      # manifest_v1/v2.json (+ review/params/dataset/training manifests if present) -> showcase.html
    python3 build_showcase.py --manifests a.json b.json --out out.html
    python3 build_showcase.py --embed              # inline images as base64 (single sendable file)

- Pages are taken from each manifest's `pages[]`, in file order (tabs = `tab`).
- A missing or unreadable manifest becomes a page with an "Images not generated yet" notice.
- Image paths are relative to this folder (docs/showcase/). Missing image files show a labelled placeholder box.
- Deep links: `#v2` (page) and `#v2-shadows` (page-id + "-" + feature id). The last tab is remembered.
- Files: `build_showcase.py`, `template.html` (all CSS/JS, no external resources), `test_fixture/`.

## Manifest schema

    {"pages":[{"id":"v1","tab":"v1: original generator","title":"...","intro":"2-4 sentences",
      "glossary":{"term":"one-line explanation"},
      "features":[{"id":"backgrounds","title":"Background photos","summary":"1-3 sentences",
        "how":"implementation note","code":"DatasetGenerator/main.py: generate_one_image",
        "flag":"optional config flag (v2)",
        "options":[{"label":"zoom 1.5","params":"zoom=1.5","image":"images/v1/x.jpg","caption":"optional"}],
        "before_after":[{"label":"Dirt specks","before":"images/v1/off.jpg","after":"images/v1/on.jpg",
                         "before_label":"off","after_label":"on","caption":"what to look at"}],
        "notes":"limitations"}]}]}

Only `id` and `title` of a feature are needed; every other field may be absent or empty.

Optional extras (feature pages): page `"tables":[{"title":"...","columns":["a","b"],"rows":[["1","2"]],"note":"..."}]`
(rendered after the glossary), feature `"facts":[["key","value"], ...]` (small key/value table) and feature
`"figure":{"image":"images/x.png","label":"...","caption":"..."}` (full-width, uncropped image, e.g. a graph).
The fourth tab "Dataset v2: parameters" (`manifest_params.json`) is made by
`showcase_scripts/params/build_params.py` from the dataset plan of `scripts/generate_dataset.py --plan-only`.

## Review grid page (`"type": "grid"`)

A page with `"type": "grid"` becomes a review page (e.g. third tab "Review: buried mines") for flagging bad crops.
Default pages (no `type`) stay feature-card pages. Pass the review manifest as the third `--manifests` entry
(or name it `manifest_review.json`, which is picked up automatically).

    {"pages":[{"id":"burial_review","tab":"Review: buried mines","type":"grid","title":"...","intro":"...",
      "glossary":{"term":"explanation"},
      "columns":["id","seed","background","sun_el","burial","face_down","blades","notes"],   # optional, orders meta columns
      "items":[{"id":"b001","image":"images/v2/review/b001.jpg","thumb":"images/v2/review/b001_t.jpg",
                "meta":{"seed":12,"background":"grass_olive","sun_el":35.0,"burial":0.4,"face_down":false,
                        "blades_on_mine":2,"visible_frac":0.8,"dust":0.33},
                "caption":"optional","tags":["grass","low_sun"]}]}]}

- `thumb` (small, used in the grid/table) is optional; `image` (full size, used in the lightbox) falls back to it and vice versa.
- Meta keys are free-form. Dedicated filters appear when these keys exist: `background` (family = text before the first `_`),
  `sun_el`, `burial`, `face_down`, `blades_on_mine`; plus tag filter, "any field contains" filter, sort by any key.
- Cards show up to 3 key fields (background, sun_el, burial, face_down, blades_on_mine, in that order if present).
- Performance: cards render in chunks of 60 (auto-loads on scroll, plus a "Load more" button), images are lazy, filter data is precomputed. Tested with 400 items.
- UI: cards per row 2-10 (capped at 3 on phones), Grid/Table toggle (sortable headers), flag checkbox, per-item note.
  Keys on a focused card: arrows move, `f` flags, Enter opens the lightbox (`f` also works inside the lightbox).
- Flags and notes are stored in localStorage (`showcase-flags:<page id>`, debounced) and the page works without storage.
- Toolbar buttons: "Copy flagged ids + notes" (one line per flagged item: `id | seed=.. | key meta | note: ..`; falls back to a selectable textarea if the clipboard is blocked), "Download flagged.json", "Clear flags" (click twice; notes are kept).
- `--embed` stores each image once in an `assets` table and references it by key, so reused thumbnails are not duplicated.

## Dataset live sample page (`"type": "dataset"`, fifth tab)

`manifest_dataset.json` adds the tab "Dataset: live sample": 24 random finished images of `output_dataset/v2_3000`
with their YOLO boxes, and live render progress. A file:// page cannot read the disk, so this tab needs a local server
(the tab shows the command and link when opened as a file; the other tabs keep working):

    python3 scripts/serve_dataset_view.py            # then open http://127.0.0.1:8765/showcase.html#dataset
    python3 scripts/serve_dataset_view.py --port 8800 --dataset-dir /other/dataset   # also --cache-dir, --target, --verbose

- Several datasets (ADR 0018): every folder under `--datasets-root` (default `output_dataset/`, e.g. `v2_3000` and
  `v2_3000_wide`) with `plan/plan.json` or `images/` is listed by `/api/datasets` and picked in the tab's "Dataset"
  dropdown without restarting (default: newest plan). Dataset routes take `?ds=<id>`. `--dataset-dir` alone serves
  only that folder. Test: `test_fixture/dataset_switch_test.py WORK_DIR`.

- Server: stdlib `http.server`, binds 127.0.0.1 only, read-only, rejects other Host headers. Serves docs/showcase/
  (html/json/images, no dotfiles) and only `/dataset/images|labels/{train,val}/<name>` and `/dataset/meta/<name>.json`.
- `/api/dataset-info`: finished count / target (plan.json), pending, train/val (+ planned), storage on disk (by folder),
  first / last image time, rate (images/min over the last 10 min) and ETA, status (generating = a file newer than 60 s,
  idle, complete, empty), JPEG resolution, box counts, `render_log.json` failures and the tail of any `*.log` in the dataset dir.
- `/api/sample?n=24&seed=S`: random finished images (same seed = same sample) with boxes and key sidecar values
  (seed, background, sun_el, shadow, scale, buried, burial_max, face_down, blades_on_mine, psf_sigma, jpeg_q).
- An image counts only when its label and its sidecar (`meta/<name>.json`, written last) exist and the sidecar parses,
  so half-written renders never appear; files vanishing or appearing mid-request are skipped.
- Thumbnails: `/thumb/<split>/<name>.jpg`, 960 px wide, made with Pillow on first request and cached in
  `output_dataset/.thumb_cache/` (gitignored, safe to delete). Full 1920x1080 files load only in the click-to-enlarge view.
- Page: info panel (polled every 10 s while Auto-refresh is on; the sample stays fixed, "N new since this sample" shows
  when to Resample), buttons Boxes on/off, Resample 24, Auto-refresh, Parameters shown/hidden, Refresh info, cards-per-row
  slider (1-8, max 2 on phones). Lightbox: arrows step, `b` toggles boxes. Preferences are kept in localStorage.
- Test: `python3 test_fixture/dataset_view_test.py WORK_DIR` builds a fake dataset (`make_fake_dataset.py`, incl. a
  half-written image and a truncated sidecar), an empty one, starts two servers on 8799/8800, checks the page in headless
  Chrome (desktop, empty, file://, narrow) and stops the servers.

## Training live page (`"type": "training"`, sixth tab)

`manifest_training.json` adds "Training: live": live progress of the YOLO11n runs in
`kernelBashing/baselines/yolo11n/runs/<timestamp>_<name>/`, pushed by the same local server (needs a restart if it was
started before this tab existed; the tab says so):

    python3 scripts/serve_dataset_view.py            # then open http://127.0.0.1:8765/showcase.html#training
    python3 scripts/serve_dataset_view.py --training-dir /other/runs --console-log /path/train_console.log

- Endpoints (read-only, 127.0.0.1, Host checked): `/api/training/runs` (newest first, status), `/api/training/run?name=`
  (config summary, timing, `ultra/results.csv` per epoch merged with `timing.json`, live progress, ETA, elapsed, latest /
  best metrics, report links, notes, `train.log` tail), `/api/training/stream?name=` (Server-Sent Events: `run` on file
  change, `runs` when folders change, heartbeat every 15 s; without `name` it follows the newest run), and
  `/training-files/<run>/{report.png,report.html,report.md,report/<name>.png}` only.
- Status: finished / failed from the final status train_yolo.py writes (timing.json, config.json); otherwise running
  while a run file changed within max(90 s, 1.5 x median epoch time + 30 s), else failed ("probably crashed").
- Within-epoch progress (iteration i/n, running-mean losses, GPU_mem, it/s) comes from the last tqdm line of
  `<run>/train.log`, `<run>/console.log` or a `--console-log` file. `train_yolo.py`'s train.log has no progress bars, so
  redirect the console (`... train_yolo.py ... > console.log 2>&1`) and pass it with `--console-log`; without it the
  in-epoch fraction is estimated from time and labelled as such.
- Page: run selector (default follows the newest), status badge, epoch k/N with overall + within-epoch bars, tiles
  (elapsed, ETA, s/epoch, images/s, GPU memory, current losses, latest val metrics, best mAP50-95, setup), 8 inline-SVG
  charts (box / cls / dfl losses train+val, precision/recall, mAP50/mAP50-95, learning rate, epoch time, throughput)
  with hover values, per-epoch table, report gallery + report.html link after the run, configuration and notes,
  glossary. Indicator live / polling / offline / paused; Pause closes the stream; without EventSource or after two
  stream errors it polls every 5 s and retries the stream every 60 s.
- Test: `python3 test_fixture/training_view_test.py WORK_DIR [--port 8821] [--live-run-dir RUNS --console-log FILE]`
  makes fake runs (`make_fake_training.py`: finished with report, crashed, and a live 10-epoch run that writes tqdm
  lines / results.csv / timing.json every few seconds), starts servers on PORT and PORT+1 (empty folder), checks the
  API, SSE, 40 concurrent streams, and the page in headless Chromium (playwright), then stops everything. The fake runs
  also carry `live_preds/` (finished run: 960 px set, final only; live run: 640 px set, one epoch file per epoch) and
  the server under test uses `test_fixture/fake_live_predict.py` for Resample, so no ultralytics is needed.

### Live test examples (Training tab)

16 val images of the run's dataset, picked once per run by a uniform random draw (seed recorded in `set.json`) and kept
fixed so every epoch is judged on the same pictures, predicted after every epoch. ADR
[0019](../history/0019-training-live-predictions.md).

- Predictor: `kernelBashing/baselines/yolo11n/scripts/live_predict.py <run>` (the venv's ultralytics, CPU only, 2 torch
  threads; run it with `nice -n 10`). It reads imgsz and the data yaml from the run's `config.json`, writes
  `<run>/live_preds/set.json` (paths relative to the dataset root, image size, GT boxes in pixels), and every time
  `ultra/weights/last.pt` changes (size / mtime stable, copied to a temp file first) runs inference (conf >= 0.1 stored,
  ultralytics' default NMS) and writes `epoch_<NN>.json` + `latest.json` (boxes with confidence, GT, per-image TP/FP/FN at
  conf 0.25 / IoU 0.5, set precision / recall, inference seconds). When training ends (final status in `config.json`,
  `report.md`, `--parent-pid` gone, or `--idle-exit`) it does a last pass with `best.pt` (`epoch_final.json`) and exits.
  `--once` = only that final pass (finished runs). `train_yolo.py` starts it as a low-priority child by default
  (`--no-live-preds` to skip). For a run started without it:

      cd kernelBashing/baselines/yolo11n
      OMP_NUM_THREADS=2 nohup nice -n 10 .venv/bin/python scripts/live_predict.py runs/<run> > /dev/null 2>&1 &
      .venv/bin/python scripts/live_predict.py runs/<finished run> --once

- Endpoints: `GET /api/training/preds?name=R` (set + epochs + per-epoch summary + predictor state),
  `GET /api/training/preds?name=R&epoch=<n|latest|final>`, `GET /training-img/<run>/<k>.jpg[?full=1]` (only image k of
  that run's `set.json`, only inside the dataset named in the run's `config.json`, only `images/<split>/<name>.jpg|png`;
  640 px thumbnails cached like the dataset tab), and `POST /api/training/resample?name=R` (Host + Origin checked,
  one request per run per 20 s, `--resample-gap`). Resample writes `live_preds/resample_request.json` with a new seed;
  the watcher archives the current set and its epochs to `live_preds/archive/`, samples a new 16 and predicts them with
  the current weights. If no watcher is running (finished run) the server starts
  `nice -n 10 <venv python> live_predict.py <run> --handle-request` (`--predictor-dir`, `--no-spawn-predictor`); the
  server itself never imports ultralytics. The SSE stream sends a `preds` event whenever `live_preds/` changes.
- Page: grid of 16 cards (GT green thin, missed GT dashed; predictions red with confidence, unmatched ones dashed),
  confidence slider (client-side filter, default 0.25), GT / prediction toggles, epoch slider + buttons ("Latest" follows
  new epochs until you scrub), "epoch k of N", per-card TP/FP/FN badges and the summary line computed in the browser at
  the current threshold (IoU 0.5, greedy matching by confidence like the predictor), precision / recall vs epoch chart,
  click a card to enlarge. Empty states: waiting for the first epoch, no predictor watching, no predictions (with the
  `--once` command). Works with 640 px and 960 px datasets.

### Table alignment

Every table column is aligned as one unit, header included: a column whose cells are all numbers (optionally with a
unit, blank or "–") gets class `num` (right-aligned, tabular figures) on the `th` and every `td`; all other columns stay
left-aligned (`dataTable`, the review table view, the per-epoch metrics table). `training_view_test.py` checks that
`th` and `td` alignment match for every column on the training, parameters and review (table view) tabs.

## Tests

    python3 test_fixture/run_tests.py

Regenerates placeholder images/manifests (needs Pillow), builds plain, `--embed` and missing-manifest
variants, checks HTML balance, runs `node --check` on the JS, and checks embedding.
Also `python3 test_fixture/chrome_test.py` (macOS Google Chrome, headless) loads a 400-item grid and exercises chunked loading, keyboard flagging, filters, sort, table view, lightbox, copy text and localStorage persistence (18 checks).
Note: test outputs reference `test_fixture/...` paths, so build them into docs/showcase/, not elsewhere.
