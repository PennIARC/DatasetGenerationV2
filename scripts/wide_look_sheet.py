#!/usr/bin/env python3
"""Review sheet of the "wide" 960x960 dataset (ADR 0018): 8 plan rows of output_dataset/v2_3000_wide rendered in
memory exactly as the dataset would (native 960x960 crop of the 1920x1080 render, no zoom coupling, sampled JPEG
quality), YOLO boxes drawn, every panel labelled.

    python3 scripts/wide_look_sheet.py               # -> docs/wide_look.png (+ full-res panels with --crops-dir)
"""
import argparse
import os
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import generate_dataset as G  # noqa: E402

G.set_variant("wide")

from features.camera import jpeg_roundtrip  # noqa: E402
from scene import render_scene  # noqa: E402

LIGHT = ["overcast", "sun 0.25-0.35", "sun 0.35-0.45", "sun 0.45-0.55", "sun 0.55-0.65"]
# (scale bin, mines per image) of the 8 panels: every log bin, the 8-mine extreme in the smallest and largest bin
PICKS = [(0, 8), (0, 4), (1, 7), (1, 2), (2, 6), (3, 1), (4, 8), (4, 5)]
CW = 960


def pick_rows(design):
    out, used_b, used_l = [], set(), set()
    for k, (sb, n) in enumerate(PICKS):
        fam = k % 2                               # grass / non-grass alternating
        cand = [r for r in design if r["scale_bin"] == sb and r["n_mines"] == n and r["family"] == fam] or \
               [r for r in design if r["scale_bin"] == sb and r["n_mines"] == n]
        cand.sort(key=lambda r: ((r["burial_bin"] in used_b) + (r["light"] in used_l), r["index"]))
        r = cand[0]
        used_b.add(r["burial_bin"])
        used_l.add(r["light"])
        out.append(r)
    return out


def render_row(r):
    cfg = G.make_config(G.row_overrides(r))
    rgb, labels, meta = render_scene(G.BASE_SEED, G.compact_overrides(r), index=r["index"], cfg=cfg)
    return jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"]), labels, meta


def panel(r, rgb, labels, meta):
    img = rgb.copy()
    for l in labels:
        _, xc, yc, w, h = l
        x0, y0 = int(round((xc - w / 2) * CW)) - 3, int(round((yc - h / 2) * CW)) - 3
        cv2.rectangle(img, (x0, y0), (x0 + int(round(w * CW)) + 6, y0 + int(round(h * CW)) + 6), (255, 50, 30), 2)
    ms = meta["mines"]
    nb = sum(1 for m in ms if m.get("burial", {}).get("buried"))
    hid = [m["burial"].get("achieved", 0) for m in ms if m.get("burial", {}).get("buried")]
    lo, hi = G.bucket_range(G.SCALE_EDGES, r["scale_bin"])
    blo, bhi = G.bucket_range(G.BURIAL_EDGES, r["burial_bin"])
    lens = [m["length_px"] for m in ms]
    c = meta["crop"]
    lines = [f"row {r['index']}  scale bin {r['scale_bin']}: {lo:.3f}-{hi:.3f}  (mines {min(m['scale'] for m in ms):.3f}-"
             f"{max(m['scale'] for m in ms):.3f}, length {min(lens):.0f}-{max(lens):.0f} px)",
             f"{len(labels)} boxes / {r['n_mines']} planned / {len(ms)} placed, {nb} buried"
             + (f" (hidden {', '.join(f'{h:.2f}' for h in hid)}; bin {blo:.2f}-{bhi:.2f})" if nb else
                f" (burial bin {blo:.2f}-{bhi:.2f})") + f"  {LIGHT[r['light']]}",
             f"{G.FAMILY_NAMES[r['family']]}: {r['bg_file'][:52]}  psf {meta['post']['psf_sigma']:.2f}"
             f"  q{meta['post']['jpeg_quality']}  crop at ({c['x0']}, {c['y0']}) of 1920x1080"]
    head = np.full((86, CW, 3), 250, np.uint8)
    for i, t in enumerate(lines):
        cv2.putText(head, t, (8, 24 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (20, 20, 20), 1, cv2.LINE_AA)
    return np.concatenate([head, img], 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "wide_look.png"))
    ap.add_argument("--crops-dir", default=None, help="also save each labelled 960x960 panel here")
    args = ap.parse_args()
    design = G.load_design(G.OUT_DEFAULT)
    panels = []
    for r in pick_rows(design):
        rgb, labels, meta = render_row(r)
        assert rgb.shape[:2] == (CW, CW), rgb.shape
        p = panel(r, rgb, labels, meta)
        panels.append(p)
        if args.crops_dir:
            os.makedirs(args.crops_dir, exist_ok=True)
            cv2.imwrite(os.path.join(args.crops_dir, f"row_{r['index']:05d}.png"), cv2.cvtColor(p, cv2.COLOR_RGB2BGR))
        print("rendered row", r["index"], (r["scale_bin"], r["n_mines"]), len(labels), "labels", flush=True)
    gap, ncol = 10, 4
    W = ncol * CW + (ncol - 1) * gap
    rows = []
    for k in range(0, len(panels), ncol):
        strip = []
        for p in panels[k:k + ncol]:
            strip += [p, np.full((p.shape[0], gap, 3), 255, np.uint8)]
        rows += [np.concatenate(strip[:-1], 1), np.full((gap, W, 3), 255, np.uint8)]
    title = np.full((52, W, 3), 255, np.uint8)
    cv2.putText(title, "Wide 960x960 dataset (ADR 0018, output_dataset/v2_3000_wide): 8 plan rows rendered as the dataset "
                       "would, native 960x960 crops at full size, no zoom coupling. Columns left to right; top row: "
                       "scale bins 0, 0, 1, 1 (8, 4, 7, 2 mines); bottom row: bins 2, 3, 4, 4 (6, 1, 8, 5 mines). "
                       "Grass / non-grass alternating. Red = YOLO boxes (drawn 3 px outside)",
                (10, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 1, cv2.LINE_AA)
    sheet = np.concatenate([title] + rows[:-1], 0)
    cv2.imwrite(args.out, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print("wrote", args.out, sheet.shape)


if __name__ == "__main__":
    main()
