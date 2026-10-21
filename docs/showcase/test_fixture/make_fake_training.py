#!/usr/bin/env python3
"""Fake YOLO run folders (same files as kernelBashing/baselines/yolo11n/scripts/train_yolo.py) for the training tab.

    python3 test_fixture/make_fake_training.py OUT_DIR                  # static runs only (finished + crashed)
    python3 test_fixture/make_fake_training.py OUT_DIR --live 6 --step 4  # + a live run: 6 epochs, ~4 s train each

Static runs: <..>_fake-finished (5 epochs, status finished, report.png + report/*.png + report.html/md, notes.md) and
<..>_fake-crashed (2 epochs, no final status, files 1 h old). The live run writes tqdm progress lines (carriage
returns + ANSI escapes, like the ultralytics console) to train.log, appends one ultra/results.csv row and rewrites
timing.json per epoch, then writes the final status and the report files, like the real script.
"""
import argparse
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

HEAD = ("epoch,time,train/box_loss,train/cls_loss,train/dfl_loss,metrics/precision(B),metrics/recall(B),"
        "metrics/mAP50(B),metrics/mAP50-95(B),val/box_loss,val/cls_loss,val/dfl_loss,lr/pg0,lr/pg1,lr/pg2\n")
FIGS = ["report.png", "report/pr_f1.png", "report/confusion.png", "report/factors.png", "report/gallery.png",
        "report/failures.png"]


def metrics(e, n):
    k = 1 - math.exp(-e / 2.0)
    lr = 0.002 * (e / 3 if e <= 3 else 1 - (e - 3) / max(1, n))
    return dict(box=1.05 - 0.3 * k, cls=1.9 - 1.3 * k, dfl=1.15 - 0.15 * k, p=0.85 + 0.12 * k, r=0.82 + 0.1 * k,
                m50=0.88 + 0.08 * k, m95=0.68 + 0.14 * k, vbox=0.9 - 0.3 * k, vcls=0.9 - 0.35 * k, vdfl=1.1 - 0.15 * k, lr=lr)


def row(e, n, t):
    m = metrics(e, n)
    return "%d,%.3f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f,%.6g,%.6g,%.6g\n" % (
        e, t, m["box"], m["cls"], m["dfl"], m["p"], m["r"], m["m50"], m["m95"], m["vbox"], m["vcls"], m["vdfl"],
        m["lr"], m["lr"], m["lr"])


def write_json(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, p)


def config(name, epochs, notes):
    return {"args": {"epochs": epochs, "imgsz": 640, "batch": 16, "device": "mps", "fraction": 1.0, "name": name,
                     "scratch": False, "notes": notes},
            "argv": ["--epochs", str(epochs), "--name", name],
            "dataset": {"root": "/fake/v2_3000", "names": {"0": "pfm1"}, "n_train_images": 2700, "n_val_images": 300},
            "env": {"python": "3.14.0", "torch": "2.x", "ultralytics": "8.x"},
            "ultralytics_train_kwargs": {"epochs": epochs, "imgsz": 640, "batch": 16, "device": "mps", "close_mosaic": 2,
                                         "patience": 50, "seed": 0, "flipud": 0.5, "pretrained": True}}


def timing(start, epochs_rows, status=None, wall=None):
    t = {"sessions": [{"start": start, "startup_seconds": 1.5, "amp": False, "workers_effective": 0, "batch": 16,
                       "n_train_images_used": 2700}],
         "epochs": epochs_rows, "full_train_images": 2700}
    if epochs_rows:
        later = epochs_rows[1:] or epochs_rows
        med = sorted(e["epoch_seconds"] for e in later)[len(later) // 2]
        t["summary"] = {"epochs_done": len(epochs_rows), "median_epoch_seconds": med,
                        "median_train_seconds": med * 0.95, "median_val_seconds": med * 0.05,
                        "train_images_per_s": round(2700 / (med * 0.95), 2)}
    if status:
        t["sessions"][0].update(status=status, end=datetime.now().isoformat(timespec="seconds"), wall_seconds=wall)
    return t


def report(d, name):
    from PIL import Image, ImageDraw
    (d / "report").mkdir(exist_ok=True)
    for i, f in enumerate(FIGS):
        im = Image.new("RGB", (900, 500), (240 - 20 * i, 245, 250))
        dr = ImageDraw.Draw(im)
        dr.rectangle([20, 20, 880, 480], outline=(40, 60, 120), width=4)
        dr.text((40, 40), "FAKE %s (%s)" % (f, name), fill=(10, 10, 10))
        im.save(d / f)
    (d / "report.md").write_text("# Fake report %s\n\n![training curves](report.png)\n" % name)
    (d / "report.html").write_text("<!doctype html><title>fake report</title><h1>Fake report %s</h1>"
                                   "<img src='report.png' width=400><img src='report/pr_f1.png' width=400>" % name)


def static_runs(out):
    now = time.time()
    fin = out / "2026-01-01_100000_fake-finished"
    (fin / "ultra").mkdir(parents=True, exist_ok=True)
    write_json(fin / "config.json", dict(config("fake-finished", 5, "fake finished run"), status="finished"))
    ep = [{"epoch": e, "train_seconds": 95.0 + e, "val_seconds": 5.0, "epoch_seconds": 100.0 + e,
           "train_images_per_s": 27.0, "mps_driver_allocated_gb": 5.6} for e in range(1, 6)]
    write_json(fin / "timing.json", timing("2026-01-01T10:00:00", ep, "finished", 520.0))
    (fin / "ultra" / "results.csv").write_text(HEAD + "".join(row(e, 5, 100.0 * e) for e in range(1, 6)))
    (fin / "train.log").write_text("10:00:00 Ultralytics fake\n10:09:00 5 epochs completed in 0.144 hours.\n")
    (fin / "notes.md").write_text("# Notes: fake-finished\n\nfake finished run\n")
    report(fin, fin.name)
    crash = out / "2026-01-02_100000_fake-crashed"
    (crash / "ultra").mkdir(parents=True, exist_ok=True)
    write_json(crash / "config.json", config("fake-crashed", 10, "fake crashed run"))
    write_json(crash / "timing.json", timing("2026-01-02T10:00:00", ep[:2]))
    (crash / "ultra" / "results.csv").write_text(HEAD + "".join(row(e, 10, 100.0 * e) for e in range(1, 3)))
    (crash / "train.log").write_text("10:00:00 Ultralytics fake\nRuntimeError: fake MPS out of memory\n")
    for d in (fin, crash):
        for p in [d] + list(d.rglob("*")):
            os.utime(p, (now - 3600, now - 3600))
    return fin, crash


def live_run(out, epochs, step, iters=169):
    start = datetime.now()
    d = out / ("%s_fake-live" % start.strftime("%Y-%m-%d_%H%M%S"))
    (d / "ultra").mkdir(parents=True)
    write_json(d / "config.json", config("fake-live", epochs, "fake live run"))
    log = open(d / "train.log", "a", buffering=1)
    log.write("%s Ultralytics fake live\nStarting training for %d epochs...\n" % (start.strftime("%H:%M:%S"), epochs))
    (d / "ultra" / "results.csv").write_text(HEAD)
    write_json(d / "timing.json", timing(start.isoformat(timespec="seconds"), []))
    t0, ep = time.time(), []
    for e in range(1, epochs + 1):
        te = time.time()
        log.write("\n      Epoch    GPU_mem   box_loss   cls_loss   dfl_loss  Instances       Size\n")
        m = metrics(e - 0.5, epochs)
        n_upd = max(4, int(step / 0.25))
        for k in range(1, n_upd + 1):
            it = round(k / n_upd * iters)
            el = time.time() - te
            rem = el / it * (iters - it) if it else 0
            log.write("\r\x1b[K%11s %10s %10.4g %10.4g %10.4g %10d %10d: %d%% ━━━╸── %d/%d %.1fit/s %.1fs<%.1fs"
                      % ("%d/%d" % (e, epochs), "5.27G", m["box"], m["cls"], m["dfl"], 50 + k % 9, 640,
                         it * 100 // iters, it, iters, it / max(el, 1e-3), el, rem))
            time.sleep(step / n_upd)
        log.write("\n                 Class     Images  Instances      Box(P          R      mAP50  mAP50-95): 50%% ━━ 5/10 3.0it/s 0.5s<0.5s")
        time.sleep(0.5)
        log.write("\n%s                    all        300        600      0.899      0.863       0.92      0.719\n"
                  % datetime.now().strftime("%H:%M:%S"))
        es = time.time() - te
        ep.append({"epoch": e, "train_seconds": round(es - 0.5, 2), "val_seconds": 0.5, "epoch_seconds": round(es, 2),
                   "train_images_per_s": round(2700 / max(es - 0.5, 0.1), 2), "mps_driver_allocated_gb": 5.64})
        with open(d / "ultra" / "results.csv", "a") as f:
            f.write(row(e, epochs, time.time() - t0))
        write_json(d / "timing.json", timing(start.isoformat(timespec="seconds"), ep))
    log.write("%s %d epochs completed in 0.01 hours.\n" % (datetime.now().strftime("%H:%M:%S"), epochs))
    log.close()
    write_json(d / "timing.json", timing(start.isoformat(timespec="seconds"), ep, "finished", round(time.time() - t0, 1)))
    write_json(d / "config.json", dict(config("fake-live", epochs, "fake live run"), status="finished"))
    (d / "notes.md").write_text("# Notes: fake-live\n\nfake live run\n")
    time.sleep(1.5)        # "making the report"
    report(d, d.name)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--live", type=int, default=0, help="epochs of a live run to write (0 = none)")
    ap.add_argument("--step", type=float, default=4.0, help="seconds of fake training per live epoch")
    ap.add_argument("--no-static", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not a.no_static:
        static_runs(out)
    if a.live:
        print(live_run(out, a.live, a.step), flush=True)


if __name__ == "__main__":
    main()
