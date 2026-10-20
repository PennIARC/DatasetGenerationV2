"""Build per-asset preview images and batch manifests for the watermark / artifact audit.

    python3 prepare_previews.py OUT_DIR

Backgrounds get <id>_full.jpg (<=1600 px wide) and <id>_hp.png (CLAHE local-contrast boost that makes faint
semi-transparent watermarks visible). RGBA snippets get <id>_rgba.png: the cut-out on mid-grey | dark green | light tan,
upscaled so fringes/halos are visible. Writes OUT_DIR/batches/batch_XX.json.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

V2 = Path(__file__).resolve().parents[2]
out = Path(sys.argv[1])
(out / "batches").mkdir(parents=True, exist_ok=True)


def bg_preview(path: Path, item_id: str):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = min(1.0, 1600 / w)
    small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    cv2.imwrite(str(out / f"{item_id}_full.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 92])
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    l = lab[..., 0]
    hp = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)).apply(cv2.subtract(l, cv2.GaussianBlur(l, (0, 0), 9)) + 128)
    cv2.imwrite(str(out / f"{item_id}_hp.png"), hp)
    return [f"{item_id}_full.jpg", f"{item_id}_hp.png"]


def rgba_preview(path: Path, item_id: str):
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return []
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    if im.shape[2] == 3:
        im = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    h, w = im.shape[:2]
    sc = max(1, int(round(360 / max(h, w))))
    sc = min(sc, 6)
    im = cv2.resize(im, (w * sc, h * sc), interpolation=cv2.INTER_NEAREST)
    a = im[..., 3:4].astype(np.float32) / 255
    panels = []
    for bgc in ((128, 128, 128), (50, 85, 45), (170, 190, 205)):   # BGR: grey, dark green, light tan
        bg = np.empty_like(im[..., :3], dtype=np.float32)
        bg[:] = bgc
        panels.append((im[..., :3] * a + bg * (1 - a)).astype(np.uint8))
    cv2.imwrite(str(out / f"{item_id}_rgba.png"), np.hstack(panels))
    return [f"{item_id}_rgba.png"]


groups = []
a1 = V2 / "DatasetGenerator" / "assets"
n1 = V2 / "assets_new"
img_ext = {".png", ".jpg", ".jpeg"}
groups.append(("v1_background", sorted(p for p in (a1 / "backgrounds").iterdir() if p.suffix.lower() in img_ext), bg_preview))
groups.append(("v1_rock", sorted(p for p in (a1 / "rocks").iterdir() if p.suffix.lower() in img_ext), rgba_preview))
groups.append(("v1_grass", sorted(p for p in (a1 / "grassDebris").iterdir() if p.suffix.lower() in img_ext), rgba_preview))
groups.append(("new_background", sorted(p for p in (n1 / "backgrounds").iterdir()
                                         if p.suffix.lower() in img_ext and not p.name.startswith("bg_gen_")), bg_preview))
groups.append(("new_rock", sorted(p for p in (n1 / "rocks").iterdir() if p.suffix.lower() in img_ext), rgba_preview))
groups.append(("new_leaf_clump", sorted(p for p in (n1 / "grassDebris").iterdir() if p.suffix.lower() in img_ext), rgba_preview))
groups.append(("new_dirt", sorted(p for p in (n1 / "dirt").iterdir() if p.suffix.lower() in img_ext), rgba_preview))

items = []
for cat, paths, fn in groups:
    for i, p in enumerate(paths):
        item_id = f"{cat}_{i:03d}"
        items.append({"id": item_id, "category": cat, "file": str(p), "previews": [str(out / x) for x in fn(p, item_id)]})
print(len(items), "items")

# batches: v1 backgrounds in two, v1 rocks+grass together, new backgrounds in 16s, then rocks, leaf clumps, dirt
def pick(cat):
    return [x for x in items if x["category"] == cat]
batches = [pick("v1_background")[:8], pick("v1_background")[8:], pick("v1_rock") + pick("v1_grass")]
nb = pick("new_background")
batches += [nb[i:i + 16] for i in range(0, len(nb), 16)]
batches += [pick("new_rock"), pick("new_leaf_clump"), pick("new_dirt")]
for k, b in enumerate(batches, 1):
    (out / "batches" / f"batch_{k:02d}.json").write_text(json.dumps(b, indent=1))
    print(f"batch_{k:02d}: {len(b)} items")
