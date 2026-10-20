#!/usr/bin/env python3
"""Review sheet of the zoomed 640x640 dataset look (ADR 0016): 8 plan rows rendered in memory exactly as the dataset
would (native crop, zoom coupling, sampled JPEG quality), boxes drawn, each panel labelled.

    python3 scripts/zoomed_look_sheet.py                 # -> docs/zoomed_look.png (+ full-res crops in --crops-dir)
"""
import argparse
import os
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import generate_dataset as G  # noqa: E402

from features.camera import jpeg_roundtrip  # noqa: E402
from scene import render_scene  # noqa: E402

LIGHT = ["overcast", "sun 0.25-0.35", "sun 0.35-0.45", "sun 0.45-0.55", "sun 0.55-0.65"]


def pick_rows(design):
    """8 rows: every scale bin x both background families, mines >= 2, burial bins and light spread out."""
    out, used_b, used_l = [], set(), set()
    for sb in range(4):
        for fam in (0, 1):
            cand = [r for r in design if r["scale_bin"] == sb and r["family"] == fam and r["n_mines"] >= 2]
            want = (2, 3, 4)[len(out) % 3]          # spread the mine count too
            cand.sort(key=lambda r: ((r["burial_bin"] in used_b) + (r["light"] in used_l), r["n_mines"] != want,
                                     r["index"]))
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
        x0, y0 = int(round((xc - w / 2) * 640)) - 3, int(round((yc - h / 2) * 640)) - 3
        cv2.rectangle(img, (x0, y0), (x0 + int(round(w * 640)) + 6, y0 + int(round(h * 640)) + 6), (255, 50, 30), 2)
    ms = meta["mines"]
    nb = sum(1 for m in ms if m.get("burial", {}).get("buried"))
    hid = [m["burial"].get("achieved", 0) for m in ms if m.get("burial", {}).get("buried")]
    lo, hi = G.bucket_range(G.SCALE_EDGES, r["scale_bin"])
    blo, bhi = G.bucket_range(G.BURIAL_EDGES, r["burial_bin"])
    lines = [f"row {r['index']}  scale {lo:.4g}-{hi:.4g} (mines {min(m['scale'] for m in ms):.3f}-"
             f"{max(m['scale'] for m in ms):.3f})  zoom {meta['zoom']['factor']:.2f}",
             f"{len(labels)} boxes / {r['n_mines']} mines, {nb} buried"
             + (f" (hidden {', '.join(f'{h:.2f}' for h in hid)}; bin {blo:.2f}-{bhi:.2f})" if nb else
                f" (burial bin {blo:.2f}-{bhi:.2f})")
             + f"  {LIGHT[r['light']]}",
             f"{G.FAMILY_NAMES[r['family']]}: {r['bg_file'][:44]}  bg mag {meta['zoom']['background']['magnification']:.2f}"
             f"  psf {meta['post']['psf_sigma']:.2f}  q{meta['post']['jpeg_quality']}"]
    head = np.full((74, 640, 3), 250, np.uint8)
    for i, t in enumerate(lines):
        cv2.putText(head, t, (6, 20 + 23 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
    return np.concatenate([head, img], 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "zoomed_look.png"))
    ap.add_argument("--crops-dir", default=None, help="also save each native crop (with boxes) here")
    args = ap.parse_args()
    design = G.load_design(G.OUT_DEFAULT)
    panels = []
    for r in pick_rows(design):
        rgb, labels, meta = render_row(r)
        p = panel(r, rgb, labels, meta)
        panels.append(p)
        if args.crops_dir:
            os.makedirs(args.crops_dir, exist_ok=True)
            cv2.imwrite(os.path.join(args.crops_dir, f"row_{r['index']:05d}.png"), cv2.cvtColor(p, cv2.COLOR_RGB2BGR))
        print("rendered row", r["index"], flush=True)
    gap = 8
    rows = []
    for k in range(0, 8, 4):
        strip = []
        for p in panels[k:k + 4]:
            strip += [p, np.full((p.shape[0], gap, 3), 255, np.uint8)]
        rows += [np.concatenate(strip[:-1], 1), np.full((gap, 4 * 640 + 3 * gap, 3), 255, np.uint8)]
    title = np.full((44, 4 * 640 + 3 * gap, 3), 255, np.uint8)
    cv2.putText(title, "Zoomed 640x640 dataset look (ADR 0016): 8 plan rows rendered as the dataset would, native "
                       "crops at full size. Top: scale bins 0, 0, 1, 1; bottom: 2, 2, 3, 3 (grass, non-grass "
                       "alternating). Red = YOLO boxes (drawn 3 px outside)", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1,
                cv2.LINE_AA)
    sheet = np.concatenate([title] + rows[:-1], 0)
    cv2.imwrite(args.out, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print("wrote", args.out, sheet.shape)


if __name__ == "__main__":
    main()
