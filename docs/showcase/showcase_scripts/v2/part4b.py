"""Adds overgrowth-covered (unburied) label examples and, if found, a fully hidden mine to frag_9.json."""
from v2lib import *
import json
exec(open("part4.py").read().split("found = []; hidden = None")[0].split("# ================= 9 labels")[1].split("kwl =")[0]) if False else None
kwl = dict(n_mines=8, min_mines=8, zero_mine_prob=0.0, burial_prob=0.0, psf_sigma=0.3, motion_blur_prob=0)
f9 = json.load(open("/Users/pranavgupta/Desktop/PennAiR/IARCtesting/IARCdatasetGenerationV2/docs/showcase/showcase_scripts/v2/frag_9.json"))


def lab_pair(rgb, la, lb, cx, cy):
    c, (x0, y0) = crop(rgb, cx, cy, 320, 180, 3)
    before = draw_boxes(c, la, x0, y0, 3, (255, 40, 40), 2)
    after = draw_boxes(c, la, x0, y0, 3, (255, 40, 40), 1); after = draw_boxes(after, lb, x0, y0, 3, (0, 255, 0), 2)
    return before, after


part = []; hidden = None
for seed in range(300, 340):
    ra, la, ma = render(seed, **kwl, label_visible_mask=False); rb, lb, mb = render(seed, **kwl, label_visible_mask=True)
    for j, (a, b) in enumerate(zip(ma["mines"], mb["mines"])):
        if not a.get("labelled"): continue
        cx, cy = a["box"][0] * W, a["box"][1] * H
        if not b.get("labelled"):
            if hidden is None: hidden = (seed, j)
            continue
        r = b["box"][2] * b["box"][3] / (a["box"][2] * a["box"][3])
        if r < 0.9 and 160 < cx < W - 160 and 90 < cy < H - 90:
            part.append((r, seed, j))
    print(seed, len(part), hidden, flush=True)
    if len(part) >= 3 and hidden: break
    if len(part) >= 6: break
part.sort()
for k, (r, seed, j) in enumerate(part[:2]):
    ra, la, ma = render(seed, **kwl, label_visible_mask=False); rb, lb, mb = render(seed, **kwl, label_visible_mask=True)
    bx = ma["mines"][j]["box"]
    be, af = lab_pair(rb, [[0, *bx]], [[0, *mb["mines"][j]["box"]]], bx[0] * W, bx[1] * H)
    f9["before_after"].append(dict(label=f"Mine covered by grass / debris, seed {seed} #{j} (box area x{r:.2f})", before=save(be, f"label_ba_over{k}_off.png"), after=save(af, f"label_ba_over{k}_on.png"),
        before_label="mask off: v1 box (red)", after_label="mask on: visible-part box (green)", caption="3x zoom, no burial. Overgrowth (blades, leaves, rocks drawn over the mine) is subtracted from the mask, so the green box shrinks to the visible part."))
if hidden:
    seed, j = hidden
    rb, lb, mb = render(seed, **kwl, label_visible_mask=True); ra, la, ma = render(seed, **kwl, label_visible_mask=False)
    bx = ma["mines"][j]["box"]
    be, af = lab_pair(rb, [[0, *bx]], [], bx[0] * W, bx[1] * H)
    f9["options"].append(dict(label="fully hidden mine (no box)", params=f"seed {seed}, mine #{j}, LABEL_MIN_VISIBLE_PX=1", image=save(af, "label_hidden.png"),
        caption="Red thin box: where v1 would have labelled the mine. With the visible mask no pixel remains visible, so no label is written (the open question in the notes)."))
    f9["notes"] = f9["notes"].replace(" (No fully hidden mine turned up in the sampled seeds, so no example image.)", "")
else:
    f9["notes"] += " In about 64 sampled 8-mine images no mine was fully hidden, so no example image is shown (the CHANGES notes report 2 of 192 mines hidden in their sample)."
dump("frag_9.json", f9)
print("done", part[:3], hidden)
