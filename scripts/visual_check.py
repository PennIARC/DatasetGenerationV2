"""Contact sheets for eyeballing the generator (writes PNGs to docs/):

  v1_vs_v2.png       same seeds rendered with every v2 flag off (v1 mode) and with the defaults (v2)
  mine_crops.png     3 x 3 full-resolution crops of v2 mines (buried / low sun / face down)
  rock_shadows.png   rocks with shadows off / contact shadow only / full, at low, mid and high sun
  ablation.png       one scene, crops around its mines: v1 mode, then each v2 flag alone, then all flags, then all flags with every mine face down

    python3 scripts/visual_check.py [--seed 0] [--out docs]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from features.camera import jpeg_roundtrip  # noqa: E402
from scene import render_scene  # noqa: E402

FONT = cv2.FONT_HERSHEY_SIMPLEX


def caption(img, text, scale=0.8):
    out = img.copy()
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, 2)
    cv2.rectangle(out, (0, 0), (tw + 12, th + 14), (0, 0, 0), -1)
    cv2.putText(out, text, (6, th + 6), FONT, scale, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def render(seed, ov, index=0, boxes=False):
    rgb, labels, meta = render_scene(seed, ov, index=index)
    rgb = jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"])
    if boxes:
        rgb = rgb.copy()
        H, W = rgb.shape[:2]
        for _, xc, yc, w, h in labels:
            cv2.rectangle(rgb, (int((xc - w / 2) * W), int((yc - h / 2) * H)), (int((xc + w / 2) * W), int((yc + h / 2) * H)),
                          (255, 0, 0), 2)
    return rgb, labels, meta


def crop(img, cx, cy, size):
    H, W = img.shape[:2]
    x0 = int(np.clip(cx - size // 2, 0, W - size))
    y0 = int(np.clip(cy - size // 2, 0, H - size))
    return img[y0:y0 + size, x0:x0 + size]


def grid(tiles, cols, pad=6):
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    out = np.full((rows * (h + pad) + pad, cols * (w + pad) + pad, 3), 255, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        out[pad + r * (h + pad):pad + r * (h + pad) + h, pad + c * (w + pad):pad + c * (w + pad) + w] = t
    return out


def save(path, rgb):
    cv2.imwrite(path, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    print("wrote", path)


def v1_vs_v2(out, seed):
    tiles = []
    for idx in range(4):
        a, _, _ = render(seed, {"v1": True}, idx, boxes=True)
        b, _, mb = render(seed, {}, idx, boxes=True)
        sun = mb["sun"]
        nfd = sum(bool(m.get("face_down")) for m in mb["mines"])
        tiles += [caption(cv2.resize(a, (960, 540), interpolation=cv2.INTER_AREA), f"v1 mode  idx {idx}"),
                  caption(cv2.resize(b, (960, 540), interpolation=cv2.INTER_AREA),
                          f"v2  idx {idx}  sun el {sun['elevation']:.0f}{' overcast' if sun['overcast'] else ''}"
                          f"  face down {nfd}/{len(mb['mines'])}")]
    save(os.path.join(out, "v1_vs_v2.png"), grid(tiles, 2))


def mine_crops(out, seed, size=220):
    picks = {"buried": [], "low sun": [], "face down": []}
    idx = 100
    while min(len(v) for v in picks.values()) < 3 and idx < 400:
        rgb, labels, meta = render(seed, {}, idx)
        H, W = rgb.shape[:2]
        for m in meta["mines"]:
            if not m.get("labelled"):
                continue
            xc, yc = m["box"][0] * W, m["box"][1] * H
            fd = " FACE DOWN" if m.get("face_down") else ""
            t = f"el {meta['sun']['elevation']:.0f} p{m['pitch']:.0f} r{m['roll']:.0f} {m['colour']['family']}"
            if m["burial"]["buried"] and len(picks["buried"]) < 3:
                picks["buried"].append(caption(crop(rgb, xc, yc, size), f"buried {m['burial']['achieved']:.2f}{fd}", 0.5))
            elif m.get("face_down") and len(picks["face down"]) < 3:
                picks["face down"].append(caption(crop(rgb, xc, yc, size), "FACE DOWN " + t, 0.4))
            elif meta["sun"]["elevation"] < 30 and not meta["sun"]["overcast"] and len(picks["low sun"]) < 3:
                picks["low sun"].append(caption(crop(rgb, xc, yc, size), t, 0.45))
        idx += 1
    tiles = picks["buried"] + picks["low sun"] + picks["face down"]
    save(os.path.join(out, "mine_crops.png"), grid(tiles, 3))


def ablation(out, seed, index=7, size=260):
    import controlPanel as cp
    base = dict(n_mines=3, mine_positions=[(500, 400), (1000, 600), (1450, 380)], mine_scale=0.32,
                overcast_prob=0.0, sun_elevation=25)
    variants = [("v1 mode", {"v1": True})] + \
        [(f, {"only": [f]}) for f in cp.V2_FLAGS if f != "LABEL_VISIBLE_MASK"] + \
        [(f"MESH_MINES+{f}", {"only": ["MESH_MINES", f]}) for f in ("SOFT_EDGES", "SHADOWS", "SOIL_BLEND", "BURIAL",
                                                                   "COLOUR_PALETTE")] + \
        [("all v2", {}), ("all v2, all face down", {"flip": True})]
    rows = []
    for name, ov in variants:
        if name == "BURIAL":
            continue
        ov = {**base, **ov}
        if "BURIAL" in str(ov.get("only")):
            ov["burial_prob"] = 1.0
        rgb, labels, meta = render(seed, ov, index)
        tiles = [caption(crop(rgb, x, y, size), name if k == 0 else "", 0.5) for k, (x, y) in enumerate(base["mine_positions"])]
        tiles.append(cv2.resize(rgb, (int(size * 16 / 9), size), interpolation=cv2.INTER_AREA))
        rows.append(np.hstack([np.pad(t, ((3, 3), (3, 3), (0, 0)), constant_values=255) for t in tiles]))
    save(os.path.join(out, "ablation.png"), np.vstack(rows))


def rock_shadows(out, seed, size=200):
    """Rocks: shadows off / contact shadow only / full (contact + capped cast shadow + rim blend), low and high sun."""
    rows = []
    variants = [("shadows off", {"shadows": False, "rock_rim_blend": False}),
                ("contact only", {"rock_cast_shadow": False, "rock_rim_blend": False}),
                ("full", {})]
    for el, idx in ((18, 3), (35, 11), (65, 5)):
        base = {"n_mines": 0, "overcast_prob": 0.0, "sun_elevation": el, "blur": False, "grass_blades": False,
                "rock_align_light": False}   # same rock rotation in every variant
        _, _, m0 = render(seed, base, idx)
        rocks = sorted([r for r in m0["rocks"] if r[3] == "under" and 60 < r[0] < 1860 and 60 < r[1] < 1020],
                       key=lambda r: -r[2])[:3]
        for name, ov in variants:
            rgb, _, _ = render(seed, {**base, **ov}, idx)
            tiles = [caption(crop(rgb, r[0], r[1], size), f"{name}  el {el}" if k == 0 else "", 0.45)
                     for k, r in enumerate(rocks)]
            rows.append(np.hstack([np.pad(t, ((3, 3), (3, 3), (0, 0)), constant_values=255) for t in tiles]))
    save(os.path.join(out, "rock_shadows.png"), np.vstack(rows))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--only", default="v1_vs_v2,mine_crops,ablation,rock_shadows")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name in a.only.split(","):
        globals()[name](a.out, a.seed)
