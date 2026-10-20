"""Contact sheet of the hard-excluded assets (watermark / drop) with the auditor's reason."""
import json
from pathlib import Path
import cv2, numpy as np

here = Path(__file__).parent
S = Path("/private/tmp/claude-501/-Users-pranavgupta-Desktop-PennAiR-IARCtesting/7243d6d8-0cfc-40e3-a3d5-7165f3b40d9e/scratchpad/audit")
rows = []
for f in sorted((here / "results").glob("batch_*.json")):
    rows += json.loads(f.read_text())
flag = [r for r in rows if r["verdict"] == "drop" or r.get("watermark", "none") != "none"]
W = 520
tiles = []
for r in flag:
    prev = S / (r["id"] + ("_full.jpg" if r["category"].endswith("background") else "_rgba.png"))
    im = cv2.imread(str(prev))
    if im is None:
        continue
    h, w = im.shape[:2]
    im = cv2.resize(im, (W, int(h * W / w)))[:340]
    pad = np.full((340, W, 3), 30, np.uint8)
    pad[:im.shape[0]] = im
    txt = f"{r['id']}  " + (f"WATERMARK: {r.get('watermark_text', '')}" if r.get('watermark', 'none') != 'none' else "DROP")
    cv2.rectangle(pad, (0, 0), (W, 26), (0, 0, 0), -1)
    cv2.putText(pad, txt[:62], (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 220, 255), 1, cv2.LINE_AA)
    note = (r.get("notes") or "")[:70]
    cv2.rectangle(pad, (0, 314), (W, 340), (0, 0, 0), -1)
    cv2.putText(pad, note, (6, 332), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1, cv2.LINE_AA)
    tiles.append(pad)
cols = 3
while len(tiles) % cols:
    tiles.append(np.full((340, W, 3), 30, np.uint8))
sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
cv2.imwrite(str(here / "flagged_assets.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
print("tiles", len(flag), sheet.shape)
