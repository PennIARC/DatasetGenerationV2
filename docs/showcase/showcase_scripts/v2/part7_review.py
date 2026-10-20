"""Review grid: ~360 varied buried-mine cards -> images/v2/review2/*.jpg + manifest_review.json"""
from v2lib import *
import json, time
RD = OUT + "/review2"; os.makedirs(RD, exist_ok=True)
for _f in os.listdir(RD): os.remove(os.path.join(RD, _f))  # clear stale cards
N = 24
rng = np.random.default_rng(2027)
items, fails = [], []
t0 = time.time(); seed = 6000
while len(items) < N and seed < 6000 + 6 * N:
    seed += 1
    try:
        cx, cy = int(rng.integers(260, W - 260)), int(rng.integers(160, H - 160))
        el = float(rng.uniform(15, 70)); fr = float(rng.uniform(0.1, 0.5))
        fd = bool(rng.random() < 0.35); bl = bool(rng.random() < 0.5)
        sc = float(rng.uniform(0.25, 0.4))
        ov = dict(n_mines=1, mine_positions=[(cx, cy)], mine_scale=sc, burial_prob=1.0, burial_fraction=fr, sun_elevation=el, overcast_prob=0.0,
                  flip_prob=1.0 if fd else 0.0, blades_over_on_mine=1.0 if bl else 0.0)
        rgb, lab, meta = render_scene(seed, ov)
        mm = meta["mines"][0]
        if not mm.get("labelled"):
            fails.append((seed, "no label")); continue
        bx = mm["box"]; mx, my = bx[0] * W, bx[1] * H
        big, (x0, y0) = crop(rgb, mx, my, 480, 270, 1)  # native 1920x1080 pixels, no upscaling
        rgb0, _, _ = render_scene(seed, {**ov, "burial_prob": 0.0})  # same scene without burial
        before, _ = crop(rgb0, mx, my, 480, 270, 1)
        Image.fromarray(before).save(f"{RD}/c{len(items)+1:03d}_before.jpg", quality=95)
        bw, bh = bx[2] * W, bx[3] * H
        box = [round((mx - bw / 2 - x0) / 480, 4), round((my - bh / 2 - y0) / 270, 4), round(bw / 480, 4), round(bh / 270, 4)]
        thumb = big
        iid = f"c{len(items)+1:03d}"
        Image.fromarray(big).save(f"{RD}/{iid}.jpg", quality=95)
        bg = meta["background"]; fam = "grass" if bg.get("family") == "grass" else "ground"
        bgname = fam + "_" + os.path.splitext(os.path.basename(bg["file"]))[0]
        tags = [fam, "low_sun" if meta["sun"]["elevation"] < 30 else ("high_sun" if meta["sun"]["elevation"] > 55 else "mid_sun")]
        if fd: tags.append("face_down")
        if mm["blades_on_mine"]: tags.append("blades")
        items.append({"id": iid, "image": f"images/v2/review2/{iid}.jpg", "thumb": f"images/v2/review2/{iid}.jpg", "before": f"images/v2/review2/{iid}_before.jpg", "box": box,
                      "meta": {"seed": seed, "background": bgname, "sun_el": round(float(meta["sun"]["elevation"]), 1), "burial": round(float(mm["burial"]["achieved"]), 2),
                               "face_down": bool(mm["face_down"]), "blades_on_mine": int(mm["blades_on_mine"]), "visible_frac": round(float(mm["visible_fraction"]), 2),
                               "dust": round(float(mm["soil_blend"]["dust_strength"]), 2)},
                      "caption": f"target burial {fr:.2f}, scale {sc:.2f}", "tags": tags})
    except Exception as e:
        fails.append((seed, repr(e)[:120]))
    if len(items) % 12 == 0: print(len(items), round(time.time() - t0), flush=True)
page = {"id": "burial_review_2", "tab": "Review 2: buried mines", "type": "grid", "title": "Review: buried mines (current generator)",
        "intro": f"{len(items)} single-mine crops (native-resolution 480x270 px window around the box (no upscaling)) with burial 0.1-0.5, random sun elevation 15-70 deg, 35% face down, 50% with blades forced over the mine, default dust (triangular 0.25-0.5) and grass-weighted backgrounds. Flag crops that look wrong (floating soil, odd outlines, unnatural clods) and add a note, then copy the flagged ids.",
        "glossary": {"burial": "Achieved hidden fraction of the mine's top-down area.", "visible_frac": "Visible mine pixels / unburied mine pixels (after soil and blades).", "dust": "Per-mine dust opacity ceiling.", "sun_el": "Sun elevation in degrees."},
        "columns": ["id", "seed", "background", "sun_el", "burial", "face_down", "blades_on_mine", "visible_frac", "dust"], "items": items}
json.dump({"pages": [page]}, open(ROOT + "/docs/showcase/manifest_review.json", "w"), indent=0)
print("items", len(items), "fails", len(fails), fails[:10])
