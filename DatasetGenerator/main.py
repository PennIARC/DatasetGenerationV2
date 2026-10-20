"""Synthetic PFM-1 dataset generator (v2). Writes 1920x1080 JPEGs + YOLO labels (+ sidecar JSON) to
OUTPUT_PATH/{images,labels,meta}. Can be run from any folder; asset paths are relative to this file.

    python3 main.py --num 50 --start-index 0 --seed 0                 # all v2 features (controlPanel defaults)
    python3 main.py --num 50 --v1                                      # every v2 flag off (v1 behaviour)
    python3 main.py --num 5 --only SHADOWS,MESH_MINES --out ablation   # only these v2 flags on
    python3 main.py --num 5 --set BURIAL_PROB=1.0 --set SUN_ELEVATION=20,25
    python3 main.py --num 2000 --workers 8                             # parallel; identical output to --workers 1

Image i uses random streams seeded by (seed, i): batches (--start-index) and worker counts never change an image.
Pure numpy / OpenCV: no window or OpenGL context (v1 used a hidden pygame + moderngl window).
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cv2  # noqa: E402

from config import make_config  # noqa: E402
from features.camera import encode_jpeg  # noqa: E402
from scene import render_scene  # noqa: E402

_CFG = None
_OV = None


def _parse_value(s):
    if "," in s:
        return tuple(_parse_value(v) for v in s.split(",") if v != "")
    for cast in (int, float):
        try:
            return cast(s)
        except ValueError:
            pass
    return {"True": True, "False": False, "None": None}.get(s, s)


def build_overrides(args):
    ov = {}
    if args.v1:
        ov["v1"] = True
    if args.only is not None:
        ov["only"] = args.only
    for kv in args.set or []:
        k, v = kv.split("=", 1)
        ov[k] = _parse_value(v)
    if args.out:
        ov["OUTPUT_PATH"] = os.path.abspath(args.out)
    if args.seed is not None:
        ov["SEED"] = args.seed
    if args.no_json:
        ov["WRITE_SIDECAR_JSON"] = False
    return ov


def _init_worker(overrides):
    global _CFG, _OV
    cv2.setNumThreads(1)
    _OV = overrides
    _CFG = make_config(overrides)


def generate_one_image(index):
    cfg = _CFG
    rgb, labels, meta = render_scene(cfg.SEED, _OV, index=index, cfg=cfg)
    out = cfg.OUTPUT_PATH if os.path.isabs(cfg.OUTPUT_PATH) else os.path.join(HERE, cfg.OUTPUT_PATH)
    name = f"train_{index:05d}"
    with open(os.path.join(out, cfg.IMAGES_DIR, name + ".jpg"), "wb") as f:
        f.write(encode_jpeg(rgb, meta["post"]["jpeg_quality"]))
    with open(os.path.join(out, cfg.LABELS_DIR, name + ".txt"), "w") as f:
        for l in labels:
            f.write(f"{int(l[0])} {l[1]:.6f} {l[2]:.6f} {l[3]:.6f} {l[4]:.6f}\n")
    if cfg.WRITE_SIDECAR_JSON:
        with open(os.path.join(out, cfg.META_DIR, name + ".json"), "w") as f:
            json.dump(meta, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    return len(labels)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--num", type=int, default=None, help="images to generate (default NUM_IMAGES_TO_GENERATE)")
    ap.add_argument("--start-index", type=int, default=None, help="first image index (default START_INDEX)")
    ap.add_argument("--seed", type=int, default=None, help="base seed (default SEED)")
    ap.add_argument("--out", default=None, help="output folder (default OUTPUT_PATH inside DatasetGenerator)")
    ap.add_argument("--v1", action="store_true", help="switch every v2 flag off")
    ap.add_argument("--only", default=None, help="comma list of v2 flags to switch on; all others off")
    ap.add_argument("--set", action="append", help="override any controlPanel value, e.g. BURIAL_PROB=0.5")
    ap.add_argument("--workers", type=int, default=1, help="parallel processes (default 1)")
    ap.add_argument("--no-json", action="store_true", help="do not write sidecar JSON")
    args = ap.parse_args()
    overrides = build_overrides(args)
    _init_worker(overrides)
    cfg = _CFG
    num = args.num if args.num is not None else cfg.NUM_IMAGES_TO_GENERATE
    start = args.start_index if args.start_index is not None else cfg.START_INDEX
    out = cfg.OUTPUT_PATH if os.path.isabs(cfg.OUTPUT_PATH) else os.path.join(HERE, cfg.OUTPUT_PATH)
    for d in (cfg.IMAGES_DIR, cfg.LABELS_DIR) + ((cfg.META_DIR,) if cfg.WRITE_SIDECAR_JSON else ()):
        os.makedirs(os.path.join(out, d), exist_ok=True)

    flags_on = [f for f in cfg.V2_FLAGS if getattr(cfg, f)]
    print(f"Generating {num} images (indices {start}..{start + num - 1}, seed {cfg.SEED}) -> {out}; "
          f"v2 flags on: {flags_on or 'none (v1 mode)'}")
    t0 = time.time()
    indices = range(start, start + num)
    if args.workers > 1:
        from multiprocessing import get_context
        with get_context("spawn").Pool(args.workers, initializer=_init_worker, initargs=(overrides,)) as pool:
            for k, _ in enumerate(pool.imap_unordered(generate_one_image, indices)):
                if k % 10 == 0:
                    print(f"Generated {k} / {num}")
    else:
        for k, i in enumerate(indices):
            generate_one_image(i)
            if k % 10 == 0:
                print(f"Generated {k} / {num}")
    dt = time.time() - t0
    print(f"Done in {dt:.2f}s ({dt / max(num, 1):.3f} s/image)")


if __name__ == "__main__":
    main()
