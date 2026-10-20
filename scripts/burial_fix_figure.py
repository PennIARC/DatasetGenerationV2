"""docs/burial_fix.png: burial before / after the anchor + soil-lip fix (showcase seeds 13 = gravel, 12 = tan on grass).

Columns: old showcase render (burial off, 40% buried; from docs/showcase/images/v2), new render (off, 40% buried),
and |new buried - new off| (bright = changed pixels: only inside the mine's own silhouette, no sideways shift).
Red outline on the new buried crop = the unburied mine's silhouette (from the burial-off render)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "DatasetGenerator"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

from scene import render_scene  # noqa: E402

BASE = dict(n_mines=1, mine_positions=[(960, 540)], mine_scale=0.35, mine_pose=(3, -2, 30), psf_sigma=0.3,
            motion_blur_prob=0)
OLD = os.path.join(ROOT, "docs/showcase/images/v2")
Z, CW, CH = 4, 256, 144


def crop(img):
    x0, y0 = 960 - CW // 2, 540 - CH // 2
    return cv2.resize(img[y0:y0 + CH, x0:x0 + CW], (CW * Z, CH * Z), interpolation=cv2.INTER_NEAREST)


def label(img, text):
    out = img.copy()
    cv2.rectangle(out, (0, 0), (len(text) * 14 + 12, 34), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return out


rows = []
for seed, nm in ((13, "a"), (12, "b")):
    off, _, _ = render_scene(seed, {**BASE, "burial_prob": 0.0})
    on, _, _ = render_scene(seed, {**BASE, "burial_prob": 1.0, "burial_fraction": 0.4, "burial_tilt": 15})
    # silhouette of the unburied mine: render it with MINE_COLOUR magenta on the same scene (only for the outline)
    mag, _, _ = render_scene(seed, {**BASE, "burial_prob": 0.0, "mine_colour": (1.0, 0.0, 1.0), "soil_blend": False,
                                    "photometric_jitter": False, "blur": False, "grass_blades": False})
    sil = ((mag[..., 0].astype(int) - mag[..., 1]) > 90) & ((mag[..., 2].astype(int) - mag[..., 1]) > 90)
    sil = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    on_c = crop(on)
    cnts, _ = cv2.findContours(crop(sil * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    on_o = on_c.copy()
    cv2.drawContours(on_o, cnts, -1, (255, 0, 0), 2)
    diff = np.abs(on.astype(int) - off.astype(int)).sum(2)
    diff = np.clip(diff * 3, 0, 255).astype(np.uint8)
    old_off = cv2.cvtColor(cv2.imread(os.path.join(OLD, f"burial_ba_{nm}_off.png")), cv2.COLOR_BGR2RGB)
    old_on = cv2.cvtColor(cv2.imread(os.path.join(OLD, f"burial_ba_{nm}_on.png")), cv2.COLOR_BGR2RGB)
    tiles = [label(old_off, f"OLD off (seed {seed})"), label(old_on, "OLD 40% buried"),
             label(crop(off), "NEW off"), label(on_o, "NEW 40% buried + unburied outline"),
             label(cv2.cvtColor(crop(diff), cv2.COLOR_GRAY2RGB), "|NEW buried - NEW off|")]
    rows.append(np.hstack([np.pad(t, ((4, 4), (4, 4), (0, 0)), constant_values=255) for t in tiles]))
out = np.vstack(rows)
out = cv2.resize(out, (out.shape[1] // 2, out.shape[0] // 2), interpolation=cv2.INTER_AREA)
p = os.path.join(ROOT, "docs/burial_fix.png")
cv2.imwrite(p, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
print("wrote", p)
