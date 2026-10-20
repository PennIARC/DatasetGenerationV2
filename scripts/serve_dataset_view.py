#!/usr/bin/env python3
"""Tiny local server for the showcase's "Dataset: live sample" tab (stdlib http.server + Pillow for thumbnails).

    python3 scripts/serve_dataset_view.py                       # http://127.0.0.1:8765/showcase.html#dataset
    python3 scripts/serve_dataset_view.py --port 8800 --dataset-dir /path/to/other_dataset

Binds 127.0.0.1 only and is read-only. Routes:
  /                          -> redirect to /showcase.html#dataset
  /<file>                    -> static files of docs/showcase/ (html/json/images only, no dotfiles, no '..')
  /dataset/images/{train,val}/<name>.jpg, /dataset/labels/{train,val}/<name>.txt, /dataset/meta/<name>.json
                             -> dataset files (strict regex, nothing else of the dataset dir is reachable)
  /thumb/{train,val}/<name>.jpg -> 960 px wide JPEG, cached under output_dataset/.thumb_cache/ (gitignored)
  /api/dataset-info          -> counts, storage size, timestamps, rate / ETA, status, resolution, label counts, failures
  /api/sample?n=24&seed=S    -> random sample of finished images with YOLO boxes and key sidecar parameters

An image counts as finished only when its label file and its sidecar (meta/<name>.json, written last by
scripts/generate_dataset.py) exist and the sidecar is complete JSON, so half-written renders are never shown.
Works with 0 images and while files appear during a request (a file that vanishes or is incomplete is skipped).
"""
import argparse
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
DATASET_DEFAULT = os.path.join(REPO, "output_dataset", "v2_3000")
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


class Dataset:
    """Scans the dataset dir on demand (results cached for a couple of seconds; safe to call from many threads)."""

    def __init__(self, root, cache_dir, target=None):
        self.root, self.cache_dir, self.target_arg = root, cache_dir, target
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
        return {"dataset_dir": self.root, "server_time": now, "status": status, "active": active,
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
            rec = describe(items[i])
            if rec is not None:
                out.append(rec)
        out.sort(key=lambda r: r["name"])
        return {"seed": seed, "n": n, "available": len(items), "items": out, "server_time": time.time()}


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


def describe(it):
    """Finished image -> card record (boxes + key sidecar parameters); None if its files are not readable."""
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
    v = "?v=%d" % (it["img_mtime_ns"] // 1_000_000)
    return {"id": it["name"], "name": it["name"], "split": it["split"], "boxes": boxes, "params": params,
            "mtime": it["mtime"], "bytes": it["img_bytes"],
            "thumb": "/thumb/%s/%s.jpg%s" % (it["split"], it["name"], v),
            "image": "/dataset/images/%s/%s.jpg%s" % (it["split"], it["name"], v),
            "meta_url": "/dataset/meta/%s.json" % it["name"],
            "label_url": "/dataset/labels/%s/%s.txt" % (it["split"], it["name"])}


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
    ds = None
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
        ds = self.ds
        try:
            if path == "/":
                return self._send(302, b"", "text/plain", extra={"Location": "/showcase.html#dataset"})
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dataset-dir", default=DATASET_DEFAULT, help="dataset root (default output_dataset/v2_3000)")
    ap.add_argument("--cache-dir", default=CACHE_DEFAULT, help="thumbnail cache (default output_dataset/.thumb_cache)")
    ap.add_argument("--target", type=int, default=None, help="planned image count (default: plan/plan.json n_images)")
    ap.add_argument("--verbose", action="store_true", help="log every request")
    args = ap.parse_args()
    Handler.ds = Dataset(os.path.abspath(args.dataset_dir), os.path.abspath(args.cache_dir), args.target)
    Handler.verbose, Handler.port = args.verbose, args.port
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    print("serving docs/showcase + %s\n  open http://127.0.0.1:%d/showcase.html#dataset   (Ctrl-C to stop)"
          % (Handler.ds.root, args.port), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
