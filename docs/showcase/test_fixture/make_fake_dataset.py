#!/usr/bin/env python3
"""Fake dataset (same layout as output_dataset/v2_3000) for testing scripts/serve_dataset_view.py.

    python3 make_fake_dataset.py OUT_DIR [--n 30] [--start 0] [--spread 600] [--partial] [--size 640x640]

Images come from docs/showcase/images/v2/review2/c*.jpg (resized to --size, default 1920x1080; grey placeholders if absent),
labels from the review manifest boxes (+ random extra boxes), sidecars with the keys the server reads.
Modification times are spread over the last --spread seconds (oldest first) so rate / ETA are non-trivial.
--partial also writes one image without label/sidecar and one with a truncated sidecar (must NOT be counted).
Run it again with --start N --spread 0 to simulate new images arriving while the server runs.
"""
import argparse
import json
import os
import random
import time
from pathlib import Path

from PIL import Image

SC = Path(__file__).resolve().parent.parent
SRC = SC / "images" / "v2" / "review2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--spread", type=float, default=600.0)
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--size", default="1920x1080", help="image size WxH (the zoomed dataset is 640x640)")
    a = ap.parse_args()
    WH = tuple(int(v) for v in a.size.lower().split("x"))
    out = Path(a.out)
    for d in ("images/train", "images/val", "labels/train", "labels/val", "meta", "plan"):
        (out / d).mkdir(parents=True, exist_ok=True)
    (out / "plan" / "plan.json").write_text(json.dumps({"n_images": 3000, "split": {"train": 2700, "val": 300},
                                                       "n_mines_planned": 10800}))
    srcs = sorted(p for p in SRC.glob("c*.jpg") if "_before" not in p.name)
    boxes = {}
    try:
        man = json.loads((SC / "manifest_review.json").read_text())
        boxes = {it["id"]: it.get("box") for it in man["pages"][0]["items"]}
    except Exception:  # noqa: BLE001
        pass
    rng = random.Random(a.start)
    now = time.time()
    for k in range(a.start, a.start + a.n):
        name, split = "v2_%05d" % k, "val" if k % 10 == 9 else "train"
        if srcs:
            src = srcs[k % len(srcs)]
            im = Image.open(src).convert("RGB").resize(WH, Image.LANCZOS)
            b0 = boxes.get(src.stem)
        else:
            im, b0 = Image.new("RGB", WH, (90 + k % 60, 110, 80)), None
        lab = []
        if b0:
            x, y, w, h = b0
            lab.append((0, x + w / 2, y + h / 2, w, h))
        for _ in range(rng.choice([0, 0, 1, 2, 3])):
            w, h = rng.uniform(0.03, 0.09), rng.uniform(0.04, 0.12)
            lab.append((0, rng.uniform(w, 1 - w), rng.uniform(h, 1 - h), w, h))
        mines = [{"scale": rng.uniform(0.1, 0.4), "face_down": rng.random() < 0.3, "labelled": True,
                  "blades_on_mine": rng.choice([0, 0, 1, 2]),
                  "burial": {"buried": (bur := rng.random() < 0.35), "achieved": rng.uniform(0.05, 0.5) if bur else 0.0}}
                 for _ in lab]
        meta = {"index": k, "seed": [2026, k], "sun": {"elevation": rng.uniform(15, 70), "azimuth": rng.uniform(0, 360),
                                                       "overcast": rng.random() < 0.15, "shadow_strength": rng.uniform(0.25, 0.65)},
                "background": {"file": "assets_new/backgrounds/bg_%s.jpg" % rng.choice(["Grass003", "Ground029", "Gravel022"])},
                "mines": mines, "post": {"psf_sigma": rng.uniform(0, 1.5), "jpeg_quality": rng.randint(70, 95)},
                "plan": {"row": k, "split": split, "n_mines": len(lab), "attempt": 0, "render_index": k,
                         "base_seed": 2026, "saved_jpeg_quality": 90}}
        ip, lp, mp = out / "images" / split / (name + ".jpg"), out / "labels" / split / (name + ".txt"), out / "meta" / (name + ".json")
        im.save(ip, "JPEG", quality=90)
        lp.write_text("".join("%d %.6f %.6f %.6f %.6f\n" % l for l in lab))
        mp.write_text(json.dumps(meta, indent=1))
        t = now - a.spread * (1 - (k - a.start) / max(1, a.n))
        for p in (ip, lp, mp):
            os.utime(p, (t, t))
    if a.partial:
        k = a.start + a.n
        Image.new("RGB", WH, (40, 40, 40)).save(out / "images" / "train" / ("v2_%05d.jpg" % k))   # no label/meta
        k += 1
        Image.new("RGB", WH, (60, 40, 40)).save(out / "images" / "train" / ("v2_%05d.jpg" % k))
        (out / "labels" / "train" / ("v2_%05d.txt" % k)).write_text("0 0.5 0.5 0.1 0.1\n")
        (out / "meta" / ("v2_%05d.json" % k)).write_text('{"index": %d, "seed": [2026, ' % k)            # truncated
    print("fake dataset: %d images (+%s partial) in %s" % (a.n, 2 if a.partial else 0, out))


if __name__ == "__main__":
    main()
