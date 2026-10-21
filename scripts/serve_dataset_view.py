#!/usr/bin/env python3
"""Tiny local server for the showcase's "Dataset: live sample" tab (stdlib http.server + Pillow for thumbnails).

    python3 scripts/serve_dataset_view.py                       # http://127.0.0.1:8765/showcase.html#dataset
    python3 scripts/serve_dataset_view.py --port 8800 --dataset-dir /path/to/other_dataset

Datasets: every folder under --datasets-root (default output_dataset/) that has plan/plan.json or images/ is selectable
in the tab without restarting (rescanned on each /api/datasets call); the default is the newest (plan.json mtime).
--dataset-dir alone serves just that folder (as before); with --datasets-root as well it is added and is the default.

Binds 127.0.0.1 only and is read-only (except the resample request file, see below). Routes:
  /                          -> redirect to /showcase.html#dataset
  /<file>                    -> static files of docs/showcase/ (html/json/images only, no dotfiles, no '..')
  /dataset/images/{train,val}/<name>.jpg, /dataset/labels/{train,val}/<name>.txt, /dataset/meta/<name>.json
                             -> dataset files (strict regex, nothing else of the dataset dir is reachable)
  /thumb/{train,val}/<name>.jpg -> 960 px wide JPEG, cached under output_dataset/.thumb_cache/ (gitignored)
  /api/datasets              -> registry of selectable datasets {default, datasets: [{id, dir, variant, crop, ...}]}
  (every dataset route below takes ?ds=<id>; without it the default dataset is used; unknown id -> 404)
  /api/dataset-info          -> counts, storage size, timestamps, rate / ETA, status, resolution, label counts, failures
  /api/sample?n=24&seed=S    -> random sample of finished images with YOLO boxes and key sidecar parameters
  /api/training/runs         -> YOLO run folders in --training-dir, newest first, with status (training tab)
  /api/training/run?name=R   -> one run: config summary, timing, results.csv per epoch, live progress, ETA, report links
  /api/training/stream?name=R -> Server-Sent Events: "run" event whenever the run's files change, "runs" event when the
                                run list changes, a heartbeat comment every 15 s
  /api/training/preds?name=R  -> live test examples: {set (16 val images, GT boxes), epochs, history, predictor state}
  /api/training/preds?name=R&epoch=<n|latest|final> -> predictions of that epoch (written by live_predict.py)
  /training-img/<run>/<k>.jpg[?full=1] -> image k of the run's live_preds/set.json only (640 px thumb, or original)
  POST /api/training/resample?name=R -> ask the predictor for a new random 16 (request file; rate-limited)
  (the stream also sends a "preds" event with the preds index whenever live_preds/ changes)
  /training-files/<run>/{report.png,report.html,report.md,report/<name>.png} -> report artifacts (whitelist only)

An image counts as finished only when its label file and its sidecar (meta/<name>.json, written last by
scripts/generate_dataset.py) exist and the sidecar is complete JSON, so half-written renders are never shown.
Works with 0 images and while files appear during a request (a file that vanishes or is incomplete is skipped).
Training runs are folders written by kernelBashing/baselines/yolo11n/scripts/train_yolo.py (config.json, timing.json,
train.log, ultra/results.csv, later report.*). Live within-epoch progress comes from the last tqdm progress line of
train.log or of a console log passed with --console-log (train.log itself has no progress bars); without one it is
estimated from the time since the last epoch ended.
"""
import argparse
import csv
import io
import json
import os
import random
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOWCASE = os.path.join(REPO, "docs", "showcase")
DATASETS_ROOT_DEFAULT = os.path.join(REPO, "output_dataset")
DS_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")
CACHE_DEFAULT = os.path.join(REPO, "output_dataset", ".thumb_cache")
SPLITS = ("train", "val")
NAME = r"[A-Za-z0-9][A-Za-z0-9_\-]{0,63}"
NAME_RE = re.compile(r"^(%s)\.jpg$" % NAME)
DATASET_RE = re.compile(r"^/dataset/(?:images/(train|val)/(%s)\.jpg|labels/(train|val)/(%s)\.txt|meta/(%s)\.json)$"
                        % (NAME, NAME, NAME))
THUMB_RE = re.compile(r"^/thumb/(train|val)/(%s)\.jpg$" % NAME)
STATIC_EXT = {".html": "text/html; charset=utf-8", ".json": "application/json", ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml",
              ".gif": "image/gif", ".css": "text/css", ".js": "text/javascript", ".txt": "text/plain; charset=utf-8"}
THUMB_W = 960
ACTIVE_S = 60          # newest finished file younger than this -> "generating"
RATE_WINDOW_S = 600    # recent-rate window for the ETA

# ---- training runs (tab "Training: live")
TRAIN_DEFAULT = os.path.join(os.path.dirname(REPO), "kernelBashing", "baselines", "yolo11n", "runs")
RUN_NAME = r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}"
RUN_RE = re.compile(r"^%s$" % RUN_NAME)
TFILE_RE = re.compile(r"^/training-files/(%s)/(report\.png|report\.html|report\.md|report/[A-Za-z0-9][A-Za-z0-9_\-]{0,63}\.png)$"
                      % RUN_NAME)
RUN_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{6})_")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOGTS_RE = re.compile(r"^\d\d:\d\d:\d\d ")
TQDM_TRAIN_RE = re.compile(r"^\s*(\d+)/(\d+)\s+(\S+)\s+([\d.]+|nan)\s+([\d.]+|nan)\s+([\d.]+|nan)\s+(\d+)\s+(\d+):\s*(\d+)%(.*)$")
TQDM_VAL_RE = re.compile(r"Class\s+Images\s+Instances.*?:\s*(\d+)%(.*)$")
NIT_RE = re.compile(r"(\d+)/(\d+)")
RATE_RE = re.compile(r"([\d.]+)\s*(it/s|s/it)")
TIMES_RE = re.compile(r"([\d:.]+)s?<([\d:.]+)s?")
ACTIVE_TRAIN_S = 90        # minimum "no file activity" window before a run without a final status counts as failed
FIRST_EPOCH_S = 900        # window while no epoch has finished yet (startup + first epoch, no timing to scale by)
PRED_FILE_RE = re.compile(r"^epoch_(\d{1,4}|final)\.json$")
PRED_IMG_REL_RE = re.compile(r"^images/(?:train|val)/%s\.(?:jpg|jpeg|png)$" % NAME)
PRED_IMG_RE = re.compile(r"^/training-img/(%s)/(\d{1,4})\.jpg$" % RUN_NAME)
PRED_THUMB_W = 640
RESAMPLE_MIN_GAP_S = 20    # at most one 'Resample 16' request per run per 20 s
PREDICTOR_DEFAULT = os.path.join(os.path.dirname(REPO), "kernelBashing", "baselines", "yolo11n")
STREAM_POLL_S = 1.0
STREAM_MIN_GAP_S = 1.5     # at most one "run" event per 1.5 s per client
HEARTBEAT_S = 15.0
STREAM_MAX_S = 1800        # a stream ends after 30 min; EventSource reconnects by itself
MAX_STREAMS = 64
RESULT_COLS = {"epoch": "epoch", "time": "time", "train/box_loss": "train_box", "train/cls_loss": "train_cls",
               "train/dfl_loss": "train_dfl", "metrics/precision(B)": "precision", "metrics/recall(B)": "recall",
               "metrics/mAP50(B)": "map50", "metrics/mAP50-95(B)": "map50_95", "val/box_loss": "val_box",
               "val/cls_loss": "val_cls", "val/dfl_loss": "val_dfl", "lr/pg0": "lr0", "lr/pg1": "lr1", "lr/pg2": "lr2"}
REPORT_FIGS = [("report.png", "Training curves: losses, precision / recall, mAP, learning rate, epoch time, throughput"),
               ("report/pr_f1.png", "Precision-recall and F1 curves on the val split, with the max-F1 confidence threshold"),
               ("report/confusion.png", "Confusion matrix at the operating threshold (mine vs background), IoU of hits"),
               ("report/factors.png", "Recall by generator factor (scale, box size, burial, face-down, sun, light, blur, background)"),
               ("report/gallery.png", "Prediction gallery: fixed val images, predictions vs ground truth"),
               ("report/failures.png", "The worst val images (most misses + false positives)")]


def _st(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _read_json(path):
    try:
        with open(path, "rb") as f:
            v = json.loads(f.read())
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None      # missing, or caught mid-rewrite: treat as absent this round


def _fnum(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _secs(t):
    """'1:17' / '26.9' / '1:02:03' -> seconds."""
    try:
        parts = [float(p) for p in t.strip().rstrip("s").split(":")]
    except ValueError:
        return None
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def _iso_ts(s):
    try:
        from datetime import datetime
        return datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError):
        return None


def _mem_gb(s):
    m = re.match(r"^([\d.]+)([KMGT]?)", s or "")
    if not m:
        return None
    return float(m.group(1)) * {"": 1e-9, "K": 1e-6, "M": 1e-3, "G": 1.0, "T": 1e3}[m.group(2)]


def parse_progress(text):
    """Last tqdm state in a log tail -> dict (phase train / val / val_done / epoch_start / final) or None."""
    lines = re.split(r"[\r\n]+", ANSI_RE.sub("", text))
    for ln in reversed(lines[-400:]):
        ln = LOGTS_RE.sub("", ln)
        if not ln.strip():
            continue
        m = TQDM_TRAIN_RE.match(ln)
        if m:
            rest = m.group(10)
            p = {"phase": "train", "epoch": int(m.group(1)), "epochs": int(m.group(2)), "gpu_mem_gb": _mem_gb(m.group(3)),
                 "losses": {"box": _fnum(m.group(4)), "cls": _fnum(m.group(5)), "dfl": _fnum(m.group(6))},
                 "instances": int(m.group(7)), "imgsz": int(m.group(8)), "pct": int(m.group(9))}
            n = NIT_RE.search(rest)
            if n:
                p["iter"], p["iters"] = int(n.group(1)), int(n.group(2))
            r = RATE_RE.search(rest)
            if r:
                v = float(r.group(1))
                p["it_s"] = v if r.group(2) == "it/s" else (1.0 / v if v else None)
            t = TIMES_RE.search(rest)
            if t:
                p["elapsed_s"], p["remaining_s"] = _secs(t.group(1)), _secs(t.group(2))
            return p
        m = TQDM_VAL_RE.search(ln)
        if m:
            p = {"phase": "val", "pct": int(m.group(1))}
            n = NIT_RE.search(m.group(2))
            if n:
                p["iter"], p["iters"] = int(n.group(1)), int(n.group(2))
            t = TIMES_RE.search(m.group(2))
            if t:
                p["elapsed_s"], p["remaining_s"] = _secs(t.group(1)), _secs(t.group(2))
            return p
        if re.match(r"^\s*all\s+\d+\s+\d+\s", ln):
            return {"phase": "val_done"}
        if re.match(r"^\s*Epoch\s+GPU_mem\s+box_loss", ln):
            return {"phase": "epoch_start"}
        if re.search(r"epochs completed in|Validating .*best\.pt", ln):
            return {"phase": "final"}
    return None


class Training:
    """Reads YOLO run folders on demand; per-run payloads cached ~1 s so many clients / streams share the work."""

    def __init__(self, root, console_logs=()):
        self.root = root
        self.console_logs = [os.path.abspath(p) for p in console_logs]
        self.lock = threading.Lock()
        self.cache = {}          # run name -> (fingerprint, payload, computed_at)
        self.tail_cache = {}     # log path -> ((mtime_ns, size), progress)
        self.csv_cache = {}      # path -> ((mtime_ns, size), rows)
        self.streams = 0
        self.last_resample = {}  # run name -> time of the last accepted resample request
        self.children = []       # --handle-request predictor processes started for finished runs
        self.predictor_cmd = None   # (python, live_predict.py) or None: never spawn
        self.cache_dir = CACHE_DEFAULT
        self.resample_gap = RESAMPLE_MIN_GAP_S

    # ---- folders
    def run_names(self):
        try:
            names = [e.name for e in os.scandir(self.root) if e.is_dir() and RUN_RE.match(e.name)]
        except OSError:
            return []
        out = []
        for n in names:
            d = os.path.join(self.root, n)
            if any(os.path.exists(os.path.join(d, f)) for f in ("config.json", "timing.json", "train.log", "ultra")):
                out.append(n)
        return out

    def run_dir(self, name):
        if not name or not RUN_RE.match(name):
            return None
        root = os.path.realpath(self.root)
        d = os.path.realpath(os.path.join(root, name))
        if os.path.dirname(d) != root or not os.path.isdir(d):
            return None
        return d

    def start_ts(self, name, timing=None):
        m = RUN_TS_RE.match(name)
        if m:
            try:
                return time.mktime(time.strptime(m.group(1), "%Y-%m-%d_%H%M%S"))
            except ValueError:
                pass
        sess = (timing or {}).get("sessions") or []
        if sess and _iso_ts(sess[0].get("start")):
            return _iso_ts(sess[0].get("start"))
        try:
            return os.stat(os.path.join(self.root, name)).st_mtime
        except OSError:
            return 0.0

    def newest(self):
        names = self.run_names()
        return max(names, key=lambda n: (self.start_ts(n), n)) if names else None

    def logs_for(self, name, d):
        logs = [os.path.join(d, "train.log"), os.path.join(d, "console.log")]
        if self.console_logs and name == self.newest():   # a console log belongs to the newest run only
            st0 = self.start_ts(name)
            for p in self.console_logs:
                s = _st(p)
                if s and s[0] / 1e9 >= st0 - 5:
                    logs.append(p)
        return logs

    def fingerprint(self, name):
        d = self.run_dir(name)
        if d is None:
            return None
        files = ["config.json", "timing.json", "notes.md", "ultra/results.csv", "report.html", "report.png", "eval.json",
                 "report"] + ["report/" + f.split("/")[-1] for f, _ in REPORT_FIGS[1:]]
        return tuple(_st(os.path.join(d, f)) for f in files) + tuple(_st(p) for p in self.logs_for(name, d))

    def runs_fingerprint(self):
        return tuple(sorted(self.run_names()))

    # ---- parsing
    def results(self, d):
        p = os.path.join(d, "ultra", "results.csv")
        key = _st(p)
        if key is None:
            return []
        with self.lock:
            c = self.csv_cache.get(p)
            if c and c[0] == key:
                return c[1]
        rows = {}
        try:
            with open(p, newline="") as f:
                rd = csv.reader(f)
                head = [h.strip() for h in next(rd, [])]
                for r in rd:
                    if len(r) != len(head):
                        continue          # partial last line while the file is being written
                    row = {RESULT_COLS.get(h, h): _fnum(v) for h, v in zip(head, r)}
                    if row.get("epoch") is not None:
                        rows[int(row["epoch"])] = row     # a resumed run may repeat an epoch: keep the last one
        except (OSError, csv.Error, UnicodeDecodeError):
            return []
        out = [rows[k] for k in sorted(rows)]
        with self.lock:
            self.csv_cache[p] = (key, out)
        return out

    def progress_from(self, path):
        key = _st(path)
        if key is None:
            return None
        with self.lock:
            c = self.tail_cache.get(path)
            if c and c[0] == key:
                return c[1]
        try:
            with open(path, "rb") as f:
                f.seek(max(0, key[1] - 65536))
                txt = f.read(65536).decode("utf-8", "replace")
        except OSError:
            return None
        p = parse_progress(txt)
        if p is not None:
            p["source"] = os.path.basename(path)
            p["mtime"] = key[0] / 1e9
        with self.lock:
            self.tail_cache[path] = (key, p)
        return p

    def log_tail(self, d, n=8):
        p = os.path.join(d, "train.log")
        try:
            with open(p, "rb") as f:
                f.seek(max(0, os.path.getsize(p) - 8000))
                lines = ANSI_RE.sub("", f.read().decode("utf-8", "replace")).splitlines()
        except OSError:
            return []
        return [ln.rstrip() for ln in lines if ln.strip()][-n:]

    # ---- API
    # ---- live test examples (written by kernelBashing/baselines/yolo11n/scripts/live_predict.py into <run>/live_preds/)
    def _preds_dir(self, name):
        d = self.run_dir(name)
        return (d, os.path.join(d, "live_preds")) if d else (None, None)

    def preds_fingerprint(self, name):
        d, p = self._preds_dir(name)
        if p is None or not os.path.isdir(p):
            return None
        try:
            names = sorted(e.name for e in os.scandir(p) if PRED_FILE_RE.match(e.name) or e.name in
                           ("set.json", "latest.json", "resample_request.json", "predictor.pid"))
        except OSError:
            return None
        return tuple((n, _st(os.path.join(p, n))) for n in names)

    def predictor_pid(self, p):
        try:
            with open(os.path.join(p, "predictor.pid")) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return pid
        except (OSError, ValueError):
            return None

    def preds_set(self, name):
        """set.json, validated: its dataset_root must be the run's own dataset (config.json) and every image path must
        be images/<split>/<name>.<ext>; anything else -> None (so the image route can only serve these files)."""
        d, p = self._preds_dir(name)
        if p is None:
            return None, None
        sset = _read_json(os.path.join(p, "set.json"))
        if not isinstance(sset, dict) or not isinstance(sset.get("images"), list):
            return None, None
        cfg = _read_json(os.path.join(d, "config.json")) or {}
        ds = cfg.get("dataset") or {}
        root = ds.get("root") or (os.path.dirname(ds["data_yaml"]) if ds.get("data_yaml") else None)
        if not root or os.path.realpath(root) != os.path.realpath(sset.get("dataset_root") or ""):
            return None, None
        ok = [im for im in sset["images"] if isinstance(im, dict) and PRED_IMG_REL_RE.match(str(im.get("rel", "")))]
        sset["images"] = ok
        return sset, os.path.realpath(root)

    def preds_index(self, name):
        d, p = self._preds_dir(name)
        if p is None:
            return None
        sset, _ = self.preds_set(name)
        epochs = []
        try:
            for e in os.scandir(p):
                m = PRED_FILE_RE.match(e.name)
                if m:
                    epochs.append(m.group(1))
        except OSError:
            pass
        nums = sorted(int(x) for x in epochs if x != "final")
        keys = [str(n) for n in nums] + (["final"] if "final" in epochs else [])
        history = []
        for k in keys:   # small per-epoch summary for the chart (files are a few KB each)
            j = _read_json(os.path.join(p, "epoch_%s.json" % (k if k == "final" else "%02d" % int(k))))
            if isinstance(j, dict):
                history.append({"epoch": k, "summary": j.get("summary"), "weights": j.get("weights"),
                                "best_epoch": j.get("best_epoch"), "created": j.get("created")})
        req = _st(os.path.join(p, "resample_request.json"))
        arch = os.path.join(p, "archive")
        try:
            n_arch = sum(1 for e in os.scandir(arch) if e.is_dir())
        except OSError:
            n_arch = 0
        if sset:
            for im in sset["images"]:
                im["img"] = "/training-img/%s/%d.jpg?s=%s" % (name, int(im.get("id", 0)), int(sset.get("seed") or 0))
            sset.pop("dataset_root", None)
            sset.pop("data_yaml", None)
        return {"run": name, "set": sset, "epochs": keys, "history": history,
                "predictor_running": self.predictor_pid(p) is not None, "resample_pending": req is not None,
                "archived_sets": n_arch, "server_time": time.time()}

    def preds_epoch(self, name, epoch):
        d, p = self._preds_dir(name)
        if p is None:
            return None
        if epoch == "latest":
            f = "latest.json"
        elif epoch == "final":
            f = "epoch_final.json"
        elif re.fullmatch(r"\d{1,4}", epoch or ""):
            f = "epoch_%02d.json" % int(epoch)
        else:
            return None
        return _read_json(os.path.join(p, f))

    def request_resample(self, name):
        """Write live_preds/resample_request.json {seed}; start a --handle-request predictor child when no watcher is
        running. Returns (http code, payload)."""
        d, p = self._preds_dir(name)
        if p is None:
            return 404, {"error": "unknown run"}
        now = time.time()
        with self.lock:
            if now - self.last_resample.get(name, 0) < self.resample_gap:
                return 429, {"error": "resampled %ds ago; wait %ds" % (now - self.last_resample[name],
                                                                       self.resample_gap)}
            reqf = os.path.join(p, "resample_request.json")
            st = _st(reqf)
            if st and now - st[0] / 1e9 < 300:
                return 409, {"error": "a resample request is already pending"}
            self.last_resample[name] = now
        os.makedirs(p, exist_ok=True)
        seed = random.randrange(1, 10 ** 9)
        tmp = reqf + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"seed": seed, "requested": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)
        os.replace(tmp, reqf)
        spawned = False
        if self.predictor_pid(p) is None and self.predictor_cmd:
            py, script = self.predictor_cmd
            if os.path.isfile(py) and os.path.isfile(script):
                import subprocess
                env = dict(os.environ, OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
                cmd = ["nice", "-n", "10", py, script, d, "--handle-request", "--threads", "2"]
                with self.lock:
                    self.children = [c for c in self.children if c.poll() is None]   # reap finished children
                    self.children.append(subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                          stderr=subprocess.DEVNULL, env=env, start_new_session=True))
                spawned = True
        return 202, {"queued": True, "seed": seed, "spawned_predictor": spawned,
                     "watcher_running": self.predictor_pid(p) is not None}

    def run_list(self):
        out = []
        now = time.time()
        for n in self.run_names():
            info = self.run(n, light=True)
            if info:
                out.append(info)
        out.sort(key=lambda r: (r["start"] or 0, r["name"]), reverse=True)
        return {"training_dir": self.root, "exists": os.path.isdir(self.root), "server_time": now, "runs": out}

    def run(self, name, light=False):
        fp = self.fingerprint(name)
        if fp is None:
            return None
        now = time.time()
        ck = (name, light)
        with self.lock:
            c = self.cache.get(ck)
            if c and c[0] == fp and now - c[2] < 1.0:
                return c[1]
        info = self._build(name, light, now)
        with self.lock:
            self.cache[ck] = (fp, info, now)
        return info

    def _build(self, name, light, now):
        d = self.run_dir(name)
        if d is None:
            return None
        cfg = _read_json(os.path.join(d, "config.json")) or {}
        timing = _read_json(os.path.join(d, "timing.json")) or {}
        rows = self.results(d)
        sess = [s for s in timing.get("sessions") or [] if isinstance(s, dict)]
        tep = [e for e in timing.get("epochs") or [] if isinstance(e, dict)]
        summ = timing.get("summary") if isinstance(timing.get("summary"), dict) else {}
        args = cfg.get("args") if isinstance(cfg.get("args"), dict) else {}
        kw = cfg.get("ultralytics_train_kwargs") if isinstance(cfg.get("ultralytics_train_kwargs"), dict) else {}
        start = self.start_ts(name, timing)

        # progress from the freshest log that has a tqdm line
        logs = self.logs_for(name, d)
        prog = None
        for p in logs:
            q = self.progress_from(p)
            if q and (prog is None or q["mtime"] > prog["mtime"]):
                prog = q
        mt = [s[0] / 1e9 for s in (_st(os.path.join(d, f)) for f in
              ("config.json", "timing.json", "train.log", "ultra/results.csv", "report.png", "report.html", "report"))
              if s] + [s[0] / 1e9 for s in (_st(p) for p in logs[2:]) if s]
        last_act = max(mt) if mt else None
        age = now - last_act if last_act else None

        epochs_total = kw.get("epochs") or args.get("epochs") or (prog or {}).get("epochs")
        done = max(len(rows), len(tep))
        med = summ.get("median_epoch_seconds")
        med_val = summ.get("median_val_seconds")
        med_tr = summ.get("median_train_seconds")

        # status
        last_s = sess[-1] if sess else {}
        final = last_s.get("status") if sess else cfg.get("status")
        has_html = os.path.isfile(os.path.join(d, "report.html"))
        window = max(ACTIVE_TRAIN_S, 1.5 * med + 30) if med else (FIRST_EPOCH_S if not done else ACTIVE_TRAIN_S)
        if final == "finished":
            status, detail = "finished", ("report written" if has_html else
                                          "making the report" if age is not None and age < 900 else "finished, no report")
        elif final in ("error", "interrupted"):
            status, detail = "failed", "interrupted (Ctrl-C)" if final == "interrupted" else "training raised an error (see train.log)"
        elif final:
            status, detail = "failed", str(final)
        elif age is not None and age < window:
            status, detail = "running", "training"
        else:
            status = "failed"
            detail = ("no file activity for %s and no final status: the process probably crashed or was killed"
                      % (("%d min" % round(age / 60)) if age else "a while"))
        active = status == "running" or (status == "finished" and not has_html and age is not None and age < 900)

        base = {"name": name, "start": start, "status": status, "status_detail": detail, "active": active,
                "last_activity": last_act, "age_s": age, "epochs_total": epochs_total, "epochs_done": done,
                "latest_map50_95": rows[-1].get("map50_95") if rows else None, "has_report": has_html,
                "notes": (args.get("notes") or "")[:200]}
        if light:
            return base

        # live progress + ETA
        since_epoch = None
        tst = _st(os.path.join(d, "timing.json"))
        if tep and tst:
            since_epoch = now - tst[0] / 1e9        # timing.json is rewritten when an epoch ends
        elif sess and _iso_ts(sess[-1].get("start")):
            since_epoch = now - _iso_ts(sess[-1].get("start"))
        train_share = (med_tr / med) if med and med_tr else 0.95
        P = {"epochs_total": epochs_total, "epochs_done": done, "epoch": None, "phase": None, "iter": None, "iters": None,
             "frac_epoch": None, "frac_total": (done / epochs_total) if epochs_total else None, "it_s": None,
             "images_per_s": summ.get("train_images_per_s"), "gpu_mem_gb": (tep[-1].get("mps_driver_allocated_gb") if tep else None),
             "gpu_mem_source": "timing.json (MPS driver memory at epoch end)" if tep else None,
             "losses": None, "instances": None, "source": None, "estimated": False, "line_age_s": None}
        eta = None
        batch = (sess[-1].get("batch") if sess else None) or args.get("batch") or kw.get("batch")
        if status == "running" and epochs_total and done < epochs_total:
            cur = done + 1
            P["epoch"] = cur
            fresh = prog is not None and now - prog["mtime"] < max(60, window) and prog.get("epoch", cur) == cur
            cur_rem = None
            if fresh and prog["phase"] == "train" and prog.get("iters"):
                f_tr = prog["iter"] / prog["iters"]
                P.update(phase="train", iter=prog["iter"], iters=prog["iters"], frac_epoch=f_tr * train_share,
                         it_s=prog.get("it_s"), losses=prog["losses"], instances=prog["instances"], source=prog["source"],
                         line_age_s=now - prog["mtime"])
                if prog.get("gpu_mem_gb") is not None:
                    P.update(gpu_mem_gb=prog["gpu_mem_gb"], gpu_mem_source="tqdm GPU_mem column")
                if prog.get("it_s") and batch:
                    P["images_per_s"] = prog["it_s"] * batch
                rem = prog.get("remaining_s")
                if rem is None and prog.get("it_s"):
                    rem = (prog["iters"] - prog["iter"]) / prog["it_s"]
                vs = med_val if med_val is not None else (0.05 * med if med else 0.0)
                cur_rem = (rem or 0.0) + vs
                if med is None and prog.get("it_s"):
                    med = prog["iters"] / prog["it_s"] + vs
            elif fresh and prog["phase"] == "val" and prog.get("iters"):
                f_v = prog["iter"] / prog["iters"]
                P.update(phase="val", iter=prog["iter"], iters=prog["iters"], frac_epoch=train_share + (1 - train_share) * f_v,
                         source=prog["source"], line_age_s=now - prog["mtime"])
                cur_rem = prog.get("remaining_s") or ((1 - f_v) * med_val if med_val else 0.0)
            elif med and since_epoch is not None:
                f = min(0.99, max(0.0, since_epoch / med))
                P.update(phase="estimated", frac_epoch=f, estimated=True)
                cur_rem = max(0.0, med - since_epoch)
            else:
                P.update(phase="starting" if not done else "estimated", estimated=True)
            if P["frac_epoch"] is not None:
                P["frac_total"] = (done + P["frac_epoch"]) / epochs_total
            if med is not None and cur_rem is not None:
                eta = cur_rem + max(0, epochs_total - cur) * med
        elif status == "finished" or (epochs_total and done >= epochs_total):
            P.update(phase="done", frac_total=1.0 if status == "finished" else P["frac_total"])

        # elapsed (all sessions; the open one counts up to now)
        elapsed = 0.0
        for i, s in enumerate(sess):
            if s.get("wall_seconds") is not None:
                elapsed += float(s["wall_seconds"])
            elif i == len(sess) - 1 and _iso_ts(s.get("start")):
                elapsed += (now if status == "running" else (last_act or now)) - _iso_ts(s.get("start"))
        if not sess and start:
            elapsed = (now if status == "running" else (last_act or now)) - start

        # per-epoch table (results.csv + timing.json)
        tmap = {int(e["epoch"]): e for e in tep if isinstance(e.get("epoch"), (int, float))}
        epochs = []
        for r in rows:
            e = tmap.get(int(r["epoch"]), {})
            r = dict(r)
            r.update(epoch_s=e.get("epoch_seconds"), train_s=e.get("train_seconds"), val_s=e.get("val_seconds"),
                     images_per_s=e.get("train_images_per_s"), gpu_gb=e.get("mps_driver_allocated_gb"))
            epochs.append(r)
        best = max((r for r in epochs if r.get("map50_95") is not None), key=lambda r: r["map50_95"], default=None)

        u = "/training-files/%s/" % name
        figs = [{"name": f, "url": u + f + "?v=%d" % (s[0] // 1_000_000), "caption": cap}
                for f, cap in REPORT_FIGS for s in [_st(os.path.join(d, f))] if s]
        notes = ""
        try:
            with open(os.path.join(d, "notes.md"), encoding="utf-8", errors="replace") as f:
                notes = f.read(6000)
        except OSError:
            pass
        env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
        ds = cfg.get("dataset") if isinstance(cfg.get("dataset"), dict) else {}
        config = {"epochs": epochs_total, "batch": batch, "imgsz": kw.get("imgsz") or args.get("imgsz"),
                  "device": kw.get("device") or args.get("device"), "fraction": kw.get("fraction", args.get("fraction")),
                  "init": "from scratch (random init)" if args.get("scratch") or kw.get("pretrained") is False else "COCO-pretrained yolo11n.pt",
                  "patience": kw.get("patience", args.get("patience")), "close_mosaic": kw.get("close_mosaic"),
                  "flipud": kw.get("flipud", args.get("flipud")), "seed": kw.get("seed", args.get("seed")),
                  "workers": (sess[-1].get("workers_effective") if sess else None) if sess else kw.get("workers"),
                  "amp": sess[-1].get("amp") if sess else None, "notes": args.get("notes"),
                  "n_train": ds.get("n_train_images"), "n_val": ds.get("n_val_images"),
                  "dataset": ds.get("root"), "classes": list((ds.get("names") or {}).values()) if isinstance(ds.get("names"), dict) else ds.get("names"),
                  "ultralytics": env.get("ultralytics"), "torch": env.get("torch"), "python": env.get("python"),
                  "resumes": len(cfg.get("resumes") or []), "argv": " ".join(map(str, cfg.get("argv") or []))}
        base.update({"server_time": now, "config": config,
                     "timing": {"sessions": sess, "summary": summ}, "epochs": epochs,
                     "progress": P, "eta_s": eta, "eta_at": (now + eta) if eta is not None else None,
                     "elapsed_s": elapsed, "sec_per_epoch": med,
                     "latest": epochs[-1] if epochs else None, "best": best,
                     "report": {"html": u + "report.html" if has_html else None,
                                "md": u + "report.md" if os.path.isfile(os.path.join(d, "report.md")) else None,
                                "figures": figs},
                     "notes_md": notes, "log_tail": self.log_tail(d), "logs": [os.path.basename(p) for p in logs if _st(p)]})
        return base


class Dataset:
    """Scans the dataset dir on demand (results cached for a couple of seconds; safe to call from many threads)."""

    def __init__(self, root, cache_dir, target=None, ds_id=None):
        self.root, self.cache_dir, self.target_arg = root, cache_dir, target
        self.id = ds_id or os.path.basename(root.rstrip(os.sep))
        self.lock = threading.Lock()
        self.scan_at, self.scan_res = 0.0, None
        self.size_at, self.size_res = 0.0, None
        self.label_cache = {}     # path -> (mtime_ns, size, n_boxes)
        self.res_cache = {}       # path -> (mtime_ns, (w, h))
        self.json_ok = {}         # sidecar path -> (mtime_ns, size) that parsed OK
        self.newest_any = 0.0     # newest image file mtime, finished or not

    # ---- finished images
    def _complete_json(self, path, st, now):
        """True if the sidecar parses as JSON (cached per mtime/size, so each file is parsed once)."""
        if st.st_size <= 0:
            return False
        key = (st.st_mtime_ns, st.st_size)
        if self.json_ok.get(path) == key:
            return True
        try:
            with open(path, "rb") as f:
                json.loads(f.read())
        except (OSError, ValueError):
            return False      # still being written (or broken): not finished
        self.json_ok[path] = key
        return True

    def scan(self):
        with self.lock:
            now = time.time()
            if self.scan_res is not None and now - self.scan_at < 2.0:
                return self.scan_res
            items, pending, newest_any = [], 0, 0.0
            for sp in SPLITS:
                d = os.path.join(self.root, "images", sp)
                try:
                    names = [e.name for e in os.scandir(d) if e.is_file()]
                except OSError:
                    continue
                for fn in names:
                    m = NAME_RE.match(fn)
                    if not m:
                        continue
                    name = m.group(1)
                    lp = os.path.join(self.root, "labels", sp, name + ".txt")
                    mp = os.path.join(self.root, "meta", name + ".json")
                    try:
                        ist = os.stat(os.path.join(d, fn))
                        newest_any = max(newest_any, ist.st_mtime)
                        lst = os.stat(lp)
                        mst = os.stat(mp)
                    except OSError:
                        pending += 1
                        continue
                    if ist.st_size <= 0 or not self._complete_json(mp, mst, now):
                        pending += 1
                        continue
                    items.append({"name": name, "split": sp, "mtime": max(ist.st_mtime, lst.st_mtime, mst.st_mtime),
                                  "img_mtime_ns": ist.st_mtime_ns, "img_bytes": ist.st_size, "label": lp, "meta": mp,
                                  "label_st": (lst.st_mtime_ns, lst.st_size)})
            items.sort(key=lambda x: x["name"])
            self.newest_any = newest_any
            self.scan_at, self.scan_res = now, (items, pending)
            return self.scan_res

    # ---- helpers
    def plan(self):
        try:
            with open(os.path.join(self.root, "plan", "plan.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def target(self, plan):
        if self.target_arg:
            return int(self.target_arg)
        return int(plan.get("n_images") or 0) or None

    def storage(self):
        with self.lock:
            now = time.time()
            if self.size_res is not None and now - self.size_at < 5.0:
                return self.size_res
        parts, total, nfiles = {}, 0, 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            rel = os.path.relpath(dirpath, self.root).split(os.sep)[0]
            key = rel if rel in ("images", "labels", "meta", "plan") else "other"
            for fn in filenames:
                try:
                    s = os.stat(os.path.join(dirpath, fn)).st_size
                except OSError:
                    continue
                total += s
                nfiles += 1
                parts[key] = parts.get(key, 0) + s
        res = {"bytes": total, "files": nfiles, "by_dir": parts}
        with self.lock:
            self.size_at, self.size_res = time.time(), res
        return res

    def n_boxes(self, it):
        key = it["label"]
        c = self.label_cache.get(key)
        if c and c[:2] == it["label_st"]:
            return c[2]
        n = len(read_labels(key) or [])
        self.label_cache[key] = (*it["label_st"], n)
        return n

    def resolution(self, items):
        if not items:
            return None
        it = items[-1]
        p = os.path.join(self.root, "images", it["split"], it["name"] + ".jpg")
        c = self.res_cache.get(p)
        if c and c[0] == it["img_mtime_ns"]:
            return c[1]
        try:
            from PIL import Image
            with Image.open(p) as im:
                wh = list(im.size)
        except Exception:  # noqa: BLE001
            return None
        self.res_cache[p] = (it["img_mtime_ns"], wh)
        return wh

    def failures(self):
        out = {"render_log": False, "failed": [], "retried": 0, "log_tail": []}
        p = os.path.join(self.root, "render_log.json")
        if os.path.isfile(p):
            try:
                with open(p) as f:
                    log = json.load(f)
                res = log.get("results", [])
                out.update(render_log=True, failed=[{"index": r.get("index"), "error": r.get("error")}
                                                    for r in res if not r.get("ok")][:50],
                           retried=sum(1 for r in res if r.get("attempt", 0) > 0), seconds=log.get("seconds"))
            except (OSError, ValueError):
                pass
        logs = []   # generator stdout redirected to a log: <dataset>/*.log or <dataset>/../render*.log
        parent = os.path.dirname(self.root)
        for d, pat in ((self.root, re.compile(r".*\.log$")), (parent, re.compile(r"render.*\.log$"))):
            try:
                logs += [os.path.join(d, fn) for fn in sorted(os.listdir(d)) if pat.match(fn)]
            except OSError:
                pass
        for p in logs[:3]:
            try:
                with open(p, "rb") as f:
                    f.seek(max(0, os.path.getsize(p) - 4000))
                    lines = f.read().decode("utf-8", "replace").splitlines()[-6:]
                out["log_tail"].append({"file": os.path.relpath(p, parent), "lines": lines})
            except OSError:
                pass
        return out

    # ---- API
    def info(self):
        now = time.time()
        items, pending = self.scan()
        plan = self.plan()
        target = self.target(plan)
        n = len(items)
        mt = sorted(x["mtime"] for x in items)
        split_counts = {sp: sum(1 for x in items if x["split"] == sp) for sp in SPLITS}
        boxes = [self.n_boxes(x) for x in items]
        newest = mt[-1] if mt else None
        active = now - max(newest or 0.0, getattr(self, "newest_any", 0.0)) < ACTIVE_S
        rate = eta = None
        if n >= 2:
            lo = max(mt[0], now - RATE_WINDOW_S) if active else mt[0]
            hi = now if active else mt[-1]
            k = sum(1 for t in mt if t >= lo)
            if hi - lo > 1:
                rate = (k - (0 if active else 1)) / (hi - lo) * 60.0   # images per minute
        if active and rate and target and n < target:
            eta = (target - n) / rate * 60.0
        complete = bool(target and n >= target) or os.path.isfile(os.path.join(self.root, "render_log.json"))
        status = ("missing" if not os.path.isdir(self.root) else "generating" if active
                  else "complete" if complete else "empty" if n == 0 else "idle")
        planned_split = plan.get("split") or {}
        return {"dataset_dir": self.root, "dataset_id": self.id, "variant": plan.get("variant") or _guess_variant(plan),
                "server_time": now, "status": status, "active": active,
                "count": n, "pending": pending, "target": target,
                "split": split_counts,
                "split_target": {"train": planned_split.get("train"), "val": planned_split.get("val")},
                "storage": self.storage(),
                "first_mtime": mt[0] if mt else None, "last_mtime": newest,
                "rate_per_min": rate, "eta_s": eta,
                "resolution": self.resolution(items),
                "labels": {"boxes": sum(boxes), "images_without_boxes": sum(1 for b in boxes if b == 0),
                           "mean_boxes": (sum(boxes) / n) if n else None, "max_boxes": max(boxes) if boxes else None},
                "planned_mines": plan.get("n_mines_planned"),
                "has": {k: os.path.isfile(os.path.join(self.root, f)) for k, f in
                        (("data_yaml", "data.yaml"), ("manifest_csv", "manifest.csv"), ("render_log", "render_log.json"),
                         ("plan", "plan/plan.json"))},
                "failures": self.failures()}

    def sample(self, n, seed):
        items, _ = self.scan()
        rng = random.Random(seed)
        order = list(range(len(items)))
        rng.shuffle(order)
        out = []
        for i in order:      # skip entries that vanished / are unreadable since the scan
            if len(out) >= n:
                break
            rec = describe(items[i], self.id)
            if rec is not None:
                out.append(rec)
        out.sort(key=lambda r: r["name"])
        return {"seed": seed, "n": n, "available": len(items), "items": out, "server_time": time.time(),
                "dataset_id": self.id}


def _guess_variant(plan):
    """Plans written before --variant existed (output_dataset/v2_3000) have no "variant" key."""
    if not plan:
        return None
    return "zoom640" if plan.get("base_seed") == 2026 and len((plan.get("counts") or {}).get("n_mines") or {}) == 5 else None


class Registry:
    """Selectable datasets: explicit --dataset-dir folders plus every dataset-like folder under --datasets-root
    (rescanned at most every 2 s, so new folders appear without restarting). One Dataset object per folder."""

    def __init__(self, roots_dir, explicit, cache_dir, target=None):
        self.roots_dir, self.cache_dir, self.target = roots_dir, cache_dir, target
        self.explicit = [os.path.abspath(d) for d in explicit]
        self.lock = threading.Lock()
        self.objs = {}            # realpath -> Dataset
        self.at, self.res = 0.0, None

    def _dirs(self):
        out = list(self.explicit)
        if self.roots_dir:
            try:
                ents = sorted(e.path for e in os.scandir(self.roots_dir) if e.is_dir() and not e.name.startswith("."))
            except OSError:
                ents = []
            for d in ents:
                if os.path.isfile(os.path.join(d, "plan", "plan.json")) or os.path.isdir(os.path.join(d, "images")):
                    out.append(os.path.abspath(d))
        seen, uniq = set(), []
        for d in out:
            r = os.path.realpath(d)
            if r not in seen:
                seen.add(r)
                uniq.append(d)
        return uniq

    def _newest_key(self, d):
        for f in (os.path.join(d, "plan", "plan.json"), d):
            s = _st(f)
            if s:
                return s[0]
        return 0

    def scan(self):
        """-> (ordered {id: Dataset}, default id)."""
        with self.lock:
            now = time.time()
            if self.res is not None and now - self.at < 2.0:
                return self.res
            dsets, used = {}, set()
            for d in self._dirs():
                base = os.path.basename(d.rstrip(os.sep)) or "dataset"
                base = base if DS_ID_RE.match(base) else "dataset"
                i, k = base, 2
                while i in used:
                    i, k = "%s-%d" % (base, k), k + 1
                used.add(i)
                r = os.path.realpath(d)
                if r not in self.objs or self.objs[r].id != i:
                    self.objs[r] = Dataset(d, self.cache_dir, self.target, ds_id=i)
                dsets[i] = self.objs[r]
            if self.explicit and dsets:
                default = next(iter(dsets))          # an explicit --dataset-dir is the default
            elif dsets:
                default = max(dsets, key=lambda i: (self._newest_key(dsets[i].root), i))
            else:
                default = None
            self.at, self.res = now, (dsets, default)
            return self.res

    def get(self, ds_id):
        """'' -> default dataset; unknown id -> None. With no dataset at all, a placeholder on the default path."""
        dsets, default = self.scan()
        if not ds_id:
            if default is None:
                return Dataset(os.path.join(self.roots_dir or REPO, "v2_3000"), self.cache_dir, self.target)
            return dsets[default]
        return dsets.get(ds_id) if DS_ID_RE.match(ds_id) else None

    def listing(self):
        dsets, default = self.scan()
        out = []
        for i, ds in dsets.items():
            plan = ds.plan()
            crop = plan.get("output_crop") or ([640, 640] if _guess_variant(plan) == "zoom640" else None)
            img_any = False
            for sp in SPLITS:
                try:
                    with os.scandir(os.path.join(ds.root, "images", sp)) as it:
                        img_any = img_any or any(e.name.endswith(".jpg") for e in it)
                except OSError:
                    pass
            edges = (plan.get("edges") or {}).get("scale")
            nm = list(((plan.get("counts") or {}).get("n_mines") or {}).keys())
            out.append({"id": i, "dir": ds.root, "name": os.path.basename(ds.root.rstrip(os.sep)),
                        "variant": plan.get("variant") or _guess_variant(plan), "crop": crop,
                        "zoom_coupling": plan.get("scene_zoom_coupling", True if _guess_variant(plan) == "zoom640" else None),
                        "n_images": plan.get("n_images"), "mines_per_image": [int(nm[0]), int(nm[-1])] if nm else None,
                        "scale_range": [edges[0], edges[-1]] if edges else None, "scale_bins": len(edges) - 1 if edges else None,
                        "has_images": img_any, "default": i == default})
        return {"default": default, "datasets": out, "server_time": time.time()}


def read_labels(path):
    try:
        with open(path) as f:
            txt = f.read()
    except OSError:
        return None
    boxes = []
    for line in txt.splitlines():
        p = line.split()
        if len(p) != 5:
            continue
        try:
            c, xc, yc, w, h = int(float(p[0])), *map(float, p[1:])
        except ValueError:
            continue
        boxes.append([c, xc, yc, w, h])
    return boxes


def _r(v, d=3):
    return round(float(v), d) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def describe(it, ds_id=None):
    """Finished image -> card record (boxes + key sidecar parameters); None if its files are not readable.
    URLs carry &ds=<id> so the right dataset is served whichever one is the server's default."""
    boxes = read_labels(it["label"])
    try:
        with open(it["meta"]) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    if boxes is None or not isinstance(meta, dict):
        return None
    mines = [m for m in meta.get("mines") or [] if isinstance(m, dict)]
    sun = meta.get("sun") or {}
    bg = meta.get("background") or {}
    post = meta.get("post") or {}
    plan = meta.get("plan") or {}
    bur = [m.get("burial") or {} for m in mines]
    scales = [m.get("scale") for m in mines if isinstance(m.get("scale"), (int, float))]
    bgname = os.path.splitext(os.path.basename(bg.get("file") or ""))[0] or None
    params = {
        "split": it["split"],
        "seed": meta.get("seed"),
        "render_index": plan.get("render_index", meta.get("index")),
        "attempt": plan.get("attempt"),
        "background": bgname,
        "sun_el": _r(sun.get("elevation"), 1), "sun_az": _r(sun.get("azimuth"), 0),
        "overcast": sun.get("overcast"), "shadow": _r(sun.get("shadow_strength"), 2),
        "mines_planned": plan.get("n_mines"), "mines_placed": len(mines), "boxes": len(boxes),
        "scale": _r(sum(scales) / len(scales)) if scales else None,
        "buried": sum(1 for b in bur if b.get("buried")),
        "burial_max": _r(max([b.get("achieved") or 0.0 for b in bur] or [0.0]), 2) if mines else None,
        "face_down": sum(1 for m in mines if m.get("face_down")),
        "blades_on_mine": sum(int(m.get("blades_on_mine") or 0) for m in mines),
        "psf_sigma": _r(post.get("psf_sigma"), 2), "jpeg_q": plan.get("saved_jpeg_quality", post.get("jpeg_quality")),
    }
    d = "&ds=%s" % ds_id if ds_id else ""
    v = "?v=%d%s" % (it["img_mtime_ns"] // 1_000_000, d)
    q = "?ds=%s" % ds_id if ds_id else ""
    return {"id": it["name"], "name": it["name"], "split": it["split"], "boxes": boxes, "params": params,
            "mtime": it["mtime"], "bytes": it["img_bytes"],
            "thumb": "/thumb/%s/%s.jpg%s" % (it["split"], it["name"], v),
            "image": "/dataset/images/%s/%s.jpg%s" % (it["split"], it["name"], v),
            "meta_url": "/dataset/meta/%s.json%s" % (it["name"], q),
            "label_url": "/dataset/labels/%s/%s.txt%s" % (it["split"], it["name"], q)}


def make_thumb(src, dst, width):
    """Downscaled JPEG for the grid; an image that is already at most `width` wide (e.g. the 640x640 dataset crops)
    is served as its own bytes (no re-encode, no resize)."""
    from PIL import Image
    with Image.open(src) as im:
        small = im.width <= width
    if small:
        with open(src, "rb") as f:
            data = f.read()
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = "%s.%d.%d.tmp" % (dst, os.getpid(), threading.get_ident())
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dst)
        return data
    with Image.open(src) as im:
        im.draft("RGB", (width, width))       # fast JPEG DCT downscale
        im = im.convert("RGB")
        if im.width > width:
            im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = "%s.%d.%d.tmp" % (dst, os.getpid(), threading.get_ident())
    with open(tmp, "wb") as f:
        f.write(buf.getvalue())
    os.replace(tmp, dst)       # atomic: concurrent requests never see a partial thumbnail
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "DatasetView/1"
    reg = None
    tr = None
    verbose = False
    port = 8765

    def log_message(self, fmt, *args):
        if self.verbose:
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code, body, ctype, cache="no-store", extra=None):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def _err(self, code, msg):
        self._send(code, (msg + "\n").encode(), "text/plain; charset=utf-8")

    def _file(self, path, ctype, cache="no-cache"):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            return self._err(404, "not found")
        self._send(200, body, ctype, cache)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        host = (self.headers.get("Host") or "").lower()
        if host not in ("127.0.0.1:%d" % self.port, "localhost:%d" % self.port):   # DNS-rebinding guard
            return self._err(403, "forbidden host")
        u = urlsplit(self.path)
        path, q = u.path, parse_qs(u.query)
        if "%" in path or "\\" in path or "/." in path or "\0" in path:
            return self._err(404, "not found")
        try:
            if path == "/":
                return self._send(302, b"", "text/plain", extra={"Location": "/showcase.html#dataset"})
            if path == "/api/datasets":
                return self._json(self.reg.listing())
            ds = None
            if path.startswith("/api/dataset-info") or path.startswith("/api/sample") or path.startswith("/dataset/") \
                    or path.startswith("/thumb/"):
                ds = self.reg.get(q.get("ds", [""])[0])
                if ds is None:
                    return self._json({"error": "unknown dataset"}, 404) if path.startswith("/api/") else \
                        self._err(404, "not found")
            self.ds = ds
            if path == "/api/dataset-info":
                return self._json(ds.info())
            if path == "/api/sample":
                try:
                    n = max(1, min(200, int(q.get("n", ["24"])[0])))
                except ValueError:
                    n = 24
                s = q.get("seed", [""])[0]
                seed = int(s) if re.fullmatch(r"\d{1,12}", s or "") else random.randrange(10 ** 9)
                return self._json(ds.sample(n, seed))
            m = DATASET_RE.match(path)
            if m:
                if m.group(1):
                    return self._file(os.path.join(ds.root, "images", m.group(1), m.group(2) + ".jpg"), "image/jpeg",
                                      "max-age=300")
                if m.group(3):
                    return self._file(os.path.join(ds.root, "labels", m.group(3), m.group(4) + ".txt"),
                                      "text/plain; charset=utf-8")
                return self._file(os.path.join(ds.root, "meta", m.group(5) + ".json"), "application/json")
            m = THUMB_RE.match(path)
            if m:
                return self._thumb(m.group(1), m.group(2))
            if path.startswith("/api/training/") or path.startswith("/training-files/") or \
                    path.startswith("/training-img/"):
                return self._training(path, q)
            return self._static(path)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            return self._err(500, "error: %s" % type(e).__name__)

    def _thumb(self, split, name):
        ds = self.ds
        src = os.path.join(ds.root, "images", split, name + ".jpg")
        dst = os.path.join(ds.cache_dir, os.path.basename(ds.root), split, "%s_%d.jpg" % (name, THUMB_W))
        try:
            sst = os.stat(src)
        except OSError:
            return self._err(404, "not found")
        try:
            if os.stat(dst).st_mtime_ns >= sst.st_mtime_ns:
                return self._file(dst, "image/jpeg", "max-age=300")
        except OSError:
            pass
        try:
            body = make_thumb(src, dst, THUMB_W)
        except Exception:  # noqa: BLE001   (e.g. image still being written)
            return self._err(503, "thumbnail not ready")
        self._send(200, body, "image/jpeg", "max-age=300")

    # ---- training tab
    def _run_name(self, q):
        """?name=<run> (validated) or the newest run when absent; (name, error)."""
        tr = self.tr
        name = q.get("name", [""])[0]
        if not name:
            return tr.newest(), None
        if not RUN_RE.match(name) or tr.run_dir(name) is None:
            return None, "unknown run"
        return name, None

    def _training(self, path, q):
        tr = self.tr
        if path == "/api/training/runs":
            return self._json(tr.run_list())
        if path == "/api/training/run":
            name, err = self._run_name(q)
            if err:
                return self._json({"error": err}, 404)
            info = tr.run(name) if name else None
            return self._json({"run": info, "server_time": time.time()})
        if path == "/api/training/stream":
            name, err = self._run_name(q)
            if err:
                return self._json({"error": err}, 404)
            return self._stream(name, bool(q.get("name", [""])[0]))
        if path == "/api/training/preds":
            name, err = self._run_name(q)
            if err or not name:
                return self._json({"error": err or "no runs"}, 404)
            ep = q.get("epoch", [""])[0]
            if not ep:
                return self._json(tr.preds_index(name))
            j = tr.preds_epoch(name, ep)
            if j is None:
                return self._json({"error": "no predictions for epoch %s" % ep[:12]}, 404)
            return self._json(j)
        m = PRED_IMG_RE.match(path)
        if m:
            return self._pred_img(m.group(1), int(m.group(2)), q.get("full", [""])[0] == "1")
        m = TFILE_RE.match(path)
        if m:
            d = tr.run_dir(m.group(1))
            if d is None:
                return self._err(404, "not found")
            rel = m.group(2)
            full = os.path.realpath(os.path.join(d, *rel.split("/")))
            if not full.startswith(d + os.sep) or not os.path.isfile(full):
                return self._err(404, "not found")
            ext = os.path.splitext(rel)[1]
            ctype = {".png": "image/png", ".html": "text/html; charset=utf-8", ".md": "text/plain; charset=utf-8"}[ext]
            extra = {"Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"} \
                if ext == ".html" else None
            try:
                with open(full, "rb") as f:
                    body = f.read()
            except OSError:
                return self._err(404, "not found")
            return self._send(200, body, ctype, "no-cache", extra)
        return self._err(404, "not found")

    def _pred_img(self, name, idx, full):
        """Only the images listed in the run's live_preds/set.json (by position), inside the run's own dataset."""
        tr = self.tr
        sset, root = tr.preds_set(name)
        if not sset:
            return self._err(404, "not found")
        im = next((i for i in sset["images"] if i.get("id") == idx), None)
        if im is None:
            return self._err(404, "not found")
        src = os.path.realpath(os.path.join(root, *im["rel"].split("/")))
        if not src.startswith(root + os.sep) or not os.path.isfile(src):
            return self._err(404, "not found")
        ctype = "image/png" if src.lower().endswith(".png") else "image/jpeg"
        if full:
            return self._file(src, ctype, "max-age=300")
        split, base = im["rel"].split("/")[1], os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(tr.cache_dir, "_training", os.path.basename(root), split, "%s_%d.jpg" % (base, PRED_THUMB_W))
        try:
            if os.stat(dst).st_mtime_ns >= os.stat(src).st_mtime_ns:
                return self._file(dst, "image/jpeg", "max-age=300")
        except OSError:
            pass
        try:
            body = make_thumb(src, dst, PRED_THUMB_W)
        except Exception:  # noqa: BLE001
            return self._err(503, "thumbnail not ready")
        self._send(200, body, "image/jpeg" if body[:2] == b"\xff\xd8" else ctype, "max-age=300")

    def do_POST(self):
        host = (self.headers.get("Host") or "").lower()
        if host not in ("127.0.0.1:%d" % self.port, "localhost:%d" % self.port):
            return self._err(403, "forbidden host")
        origin = self.headers.get("Origin")
        if origin and origin.lower() not in ("http://127.0.0.1:%d" % self.port, "http://localhost:%d" % self.port):
            return self._err(403, "forbidden origin")       # cross-site form posts
        u = urlsplit(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 0:
                self.rfile.read(min(n, 4096))                # body ignored: the run name is the only input
            if u.path != "/api/training/resample":
                return self._err(404, "not found")
            name = parse_qs(u.query).get("name", [""])[0]
            if not name or not RUN_RE.match(name) or self.tr.run_dir(name) is None:
                return self._json({"error": "unknown run"}, 404)
            code, obj = self.tr.request_resample(name)
            return self._json(obj, code)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            return self._err(500, "error: %s" % type(e).__name__)

    def _stream(self, name, pinned):
        """Server-Sent Events. 'run' = full run payload (on file change, and when the status flips by time alone),
        'runs' = run list (when folders appear / vanish), heartbeat comment + 'heartbeat' event every 15 s.
        Unpinned streams (no ?name=) follow the newest run."""
        tr = self.tr
        with tr.lock:
            if tr.streams >= MAX_STREAMS:
                busy = True
            else:
                busy = False
                tr.streams += 1
        if busy:
            return self._err(503, "too many streams; poll /api/training/run instead")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            if self.command == "HEAD":
                return

            def send(event, obj):
                data = json.dumps(obj, default=str, separators=(",", ":"))
                self.wfile.write(("event: %s\ndata: %s\n\n" % (event, data)).encode())
                self.wfile.flush()

            self.wfile.write(b"retry: 3000\n\n")
            t0 = last_beat = last_sent = time.time()
            last_fp = last_runs = last_state = None
            last_pfp = False
            while time.time() - t0 < STREAM_MAX_S:
                now = time.time()
                runs_fp = tr.runs_fingerprint()
                if runs_fp != last_runs:
                    last_runs = runs_fp
                    send("runs", tr.run_list())
                    if not pinned:
                        name = tr.newest()
                fp = tr.fingerprint(name) if name else None
                beat = now - last_beat >= HEARTBEAT_S
                if (fp != last_fp and now - last_sent >= STREAM_MIN_GAP_S) or last_state is None or beat:
                    info = tr.run(name) if name else None
                    state = (fp, info and info["status"], info and info["active"])
                    if state != last_state or beat:
                        send("run", {"run": info, "server_time": now})
                        last_fp, last_state, last_sent = fp, state, now
                pfp = tr.preds_fingerprint(name) if name else None
                if pfp != last_pfp:
                    if last_pfp is not False or pfp is not None:
                        send("preds", tr.preds_index(name) if name else None)
                    last_pfp = pfp
                if beat:
                    self.wfile.write((": heartbeat %d\n\n" % now).encode())
                    send("heartbeat", {"server_time": now})
                    last_beat = now
                time.sleep(STREAM_POLL_S)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            with tr.lock:
                tr.streams -= 1

    def _static(self, path):
        rel = path.lstrip("/")
        parts = rel.split("/")
        if not rel or any(p in ("", ".", "..") or p.startswith(".") for p in parts):
            return self._err(404, "not found")
        ext = os.path.splitext(rel)[1].lower()
        if ext not in STATIC_EXT:
            return self._err(404, "not found")
        full = os.path.normpath(os.path.join(SHOWCASE, *parts))
        if not full.startswith(SHOWCASE + os.sep) or not os.path.isfile(full):
            return self._err(404, "not found")
        self._file(full, STATIC_EXT[ext])


class Server(ThreadingHTTPServer):
    daemon_threads = True          # open event streams never block Ctrl-C
    request_queue_size = 128       # many tabs / clients connecting at once


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dataset-dir", action="append", default=[],
                    help="serve this dataset folder (repeatable). Alone: only these folders; default: none, i.e. every "
                         "dataset under --datasets-root")
    ap.add_argument("--datasets-root", default=None,
                    help="folder whose sub-folders are the selectable datasets (default output_dataset/ when no "
                         "--dataset-dir is given)")
    ap.add_argument("--cache-dir", default=CACHE_DEFAULT, help="thumbnail cache (default output_dataset/.thumb_cache)")
    ap.add_argument("--target", type=int, default=None, help="planned image count (default: plan/plan.json n_images)")
    ap.add_argument("--training-dir", default=TRAIN_DEFAULT,
                    help="folder of YOLO run folders (default ../kernelBashing/baselines/yolo11n/runs)")
    ap.add_argument("--console-log", action="append", default=[], metavar="FILE",
                    help="console output of a running train_yolo.py (tqdm progress bars), attached to the newest run; "
                         "repeatable")
    ap.add_argument("--predictor-dir", default=PREDICTOR_DEFAULT,
                    help="folder with .venv/bin/python and scripts/live_predict.py; 'Resample 16' on a run without a "
                         "running watcher starts '<venv python> live_predict.py <run> --handle-request' (CPU, nice 10)")
    ap.add_argument("--predictor-python", default=None, help="override the predictor's python")
    ap.add_argument("--predictor-script", default=None, help="override the predictor script")
    ap.add_argument("--no-spawn-predictor", action="store_true", help="only write the request file, never start a child")
    ap.add_argument("--resample-gap", type=float, default=RESAMPLE_MIN_GAP_S,
                    help="minimum seconds between two 'Resample 16' requests for one run (default %(default)s)")
    ap.add_argument("--verbose", action="store_true", help="log every request")
    args = ap.parse_args()
    roots = args.datasets_root or (None if args.dataset_dir else DATASETS_ROOT_DEFAULT)
    Handler.reg = Registry(os.path.abspath(roots) if roots else None, args.dataset_dir, os.path.abspath(args.cache_dir),
                           args.target)
    Handler.tr = Training(os.path.abspath(args.training_dir), args.console_log)
    Handler.tr.cache_dir = os.path.abspath(args.cache_dir)
    Handler.tr.resample_gap = max(0.0, args.resample_gap)
    if not args.no_spawn_predictor:
        Handler.tr.predictor_cmd = (
            os.path.abspath(args.predictor_python or os.path.join(args.predictor_dir, ".venv", "bin", "python")),
            os.path.abspath(args.predictor_script or os.path.join(args.predictor_dir, "scripts", "live_predict.py")))
    Handler.verbose, Handler.port = args.verbose, args.port
    srv = Server(("127.0.0.1", args.port), Handler)
    dsets, default = Handler.reg.scan()
    print("serving docs/showcase + datasets %s (default %s) + %s\n  open http://127.0.0.1:%d/showcase.html#dataset   "
          "(training: #training; Ctrl-C to stop)" % (", ".join(dsets) or "none", default, Handler.tr.root, args.port),
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
