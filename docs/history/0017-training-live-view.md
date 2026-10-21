# 0017: training live view (sixth showcase tab, streamed by the local server)

Date: 2026-10-20 (uncommitted at the time of writing; the lead commits)

## Context

The YOLO11n baseline (`kernelBashing/baselines/yolo11n`, `scripts/train_yolo.py`) writes one folder per training
session under `runs/<YYYY-MM-DD_HHMMSS>_<name>/`: `config.json`, `timing.json` (rewritten after every epoch),
`train.log`, `ultra/results.csv` (one row per epoch) and, at the end, `report.*` + `report/*.png`. While the first
10-epoch session was running, the user asked: "add another tab to the html and use the local server to stream live
training progress to the page" ([0105](feedback/0105-training-live-view-request.md)).

`train.log` holds ultralytics' log lines but not its tqdm progress bars (those go to the console), so within-epoch
progress is only visible if the console output is redirected to a file.

## Decision

- Same local server as the dataset tab (`scripts/serve_dataset_view.py`, ADR 0015), new read-only routes, same
  127.0.0.1 binding and Host check:
  - `/api/training/runs`: run folders, newest first, with status guessed from files.
  - `/api/training/run?name=`: config summary, timing, `results.csv` per epoch merged with `timing.json`, live
    progress (epoch k/N, iteration i/n, train / val phase, running-mean losses, GPU memory, it/s) parsed from the last
    tqdm line, ETA, elapsed, latest / best metrics, report links, `notes.md`, `train.log` tail.
  - `/api/training/stream?name=`: Server-Sent Events. A `run` event when any of the run's files change (polled every
    1 s with `stat`, at most one event per 1.5 s), a `runs` event when folders appear, a heartbeat every 15 s.
    Without `name` the stream follows the newest run. Streams end after 30 min (the browser reconnects) and are capped
    at 64; payloads are cached ~1 s and shared between clients.
  - `/training-files/<run>/{report.png,report.html,report.md,report/<name>.png}` only (regex + realpath check;
    report.html is sent with a CSP that blocks scripts).
  - `--training-dir` (default `../kernelBashing/baselines/yolo11n/runs`) and `--console-log FILE` (repeatable;
    redirected console output with the tqdm bars, attached to the newest run if it was written after the run started).
- Status without `ps`: `finished` / `failed` from the final status `train_yolo.py` writes into `timing.json`
  (`config.json` as a fallback); otherwise `running` while any run file changed within max(90 s, 1.5 x median epoch
  time + 30 s) (15 min before the first epoch ends), else `failed` ("no file activity ... probably crashed"). The
  window is longer than 90 s because without a console log the files change only once per epoch (~110 s).
- Without a tqdm line the within-epoch fraction is estimated from the time since `timing.json` was last written
  divided by the median epoch time, and labelled as an estimate.
- Page type `"training"` in `template.html` (`renderTraining`, `lineChart` in inline SVG, no libraries) and
  `manifest_training.json`; `build_showcase.py` only gained the tab name and the optional manifest.
  The page: run selector (default "newest, follow"), status badge, epoch k/N with an overall bar (striped = epoch in
  progress) and a within-epoch bar, tiles (elapsed, ETA, s/epoch, images/s, GPU memory, current losses, latest val
  metrics, best mAP50-95, setup), 8 charts (box / cls / dfl train+val, precision / recall, mAP50 / mAP50-95, lr,
  epoch time, throughput) with titles, axis labels and units, legends, hover tooltips and a hollow running-mean
  point for the epoch in progress; per-epoch table (best row bold); report gallery with captions + report.html link
  once the run ends; configuration + notes; glossary. Connection indicator live / polling / offline / paused; Pause
  closes the stream. If EventSource fails twice (or is missing) the page polls every 5 s and retries the stream
  after 60 s. file:// and "old server without these endpoints" show the start/restart command.

## Consequences

- A server started before this change has no training endpoints: it must be restarted (the tab says so on 404).
- Exact within-epoch progress needs the console output in a file passed with `--console-log` (or saved as
  `<run>/console.log`); otherwise progress inside an epoch and the ETA are time-based estimates.
- Status is a guess from file times: a run paused (e.g. laptop asleep) longer than the window shows `failed` until
  files change again; a resumed run (`--resume`) shows `running` again as soon as it writes.
- Tested: `docs/showcase/test_fixture/training_view_test.py` (66 checks: API validation / whitelist / Host,
  SSE, 40 concurrent streams + 200 requests, live page updates without reload from a fake 10-epoch run, pause,
  polling fallback, finished / crashed runs, report gallery, empty folder, file://, phone width) plus a read-only
  check on the real first-10ep session (with its console log). Existing tests still pass (run_tests.py,
  chrome_test.py 18, dataset_view_test.py 59).

## Commits
