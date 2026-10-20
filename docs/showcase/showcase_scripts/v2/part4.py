from v2lib import *
from config import make_config
import json

CS = "images/assets_contact_sheet.jpg"
# ================= 8 assets
f8 = {"id": "assets", "title": "New assets and sampling", "flag": "NEW_ASSETS, GRASS_BLADES",
      "summary": "v1 drew from 15 background photos, a handful of rock and grass photos and flat coloured dirt squares. v2 adds many more backgrounds (indexed by family, e.g. grass vs non-grass), 34 transparent rock cut-outs, a separate layer of leaf-litter clumps (2-10 per image, desaturated and tinted towards the ground), soft dirt/dust snippets and a layer of thin grass blades, tufts and wisps that lie under and over the mines (the overgrowth partly hides mines and is counted in the labels). More varied clutter and ground means the detector cannot tie 'mine' to the few textures it saw in v1.",
      "how": "features/assets.py picks a source folder by weight, then a file; RGBA PNGs use their real alpha (no Otsu cut-out). features/background.py reads assets_new/backgrounds_index.json when BG_USE_INDEX is on. features/blades.py makes blades / tufts / wisps (about half generated on the fly, half from assets_new/grassBlades), sized in millimetres via the scene's px-per-mm.",
      "code": "DatasetGenerator/features/assets.py: sources, pick_file, load_cutout; features/background.py: pick_background; features/blades.py: make_blade_elements; objects.py: EnvironmentDebris; controlPanel: BACKGROUND_SOURCES, ROCK_SOURCES, GRASS_SOURCES, DIRT_SOURCES, GRASS_BLADES, BLADES_*",
      "options": [], "before_after": [],
      "notes": "Assets are CC0 close-up textures (ambientCG, see assets_new/ATTRIBUTION.md), not true aerial photos: scale, perspective and baked-in shadows differ from the v1 photos. Leaf clumps are now desaturated and ground-tinted, which looks more natural than the earlier garish yellow/orange, but they are still visibly pasted textures; rock cut-outs have no baked shadow but receive the synthetic one. The contact sheet is owned by another agent and may be updated."}
f8["options"].append(O("asset contact sheet", "docs/showcase/images/assets_contact_sheet.jpg", CS, "Backgrounds, rocks, leaf litter, dirt snippets and grass blades available to the sampler (sheet produced by the assets agent)."))
W3 = dict(n_mines=3, mine_positions=[(800, 560), (1050, 470), (1300, 640)], mine_scale=0.35, burial_prob=0, mine_pose=(3, -2, 30))
for s in (7, 16, 12):
    (rgb, _, m) = render(s, **W3, rocks_to_spawn_min=10, rock_align_light=False)
    f8["options"].append(O(f"new-asset scene: {m['background']['file'][-30:]}", f"seed {s}, 3 mines, defaults", save(crop(rgb, 1050, 540, 640, 360, 2)[0], f"assets_scene_{s}.jpg"),
                           "2x zoom: new ground, rocks, leaf litter, soil snippets and grass blades around the mines."))
for s, nm in [(3, "a"), (7, "b")]:
    a, _, ma = render(s, **W3, new_assets=False); b, _, mb = render(s, **W3, new_assets=True)
    f8["before_after"].append(BA(f"v1 assets only vs new assets (seed {s})", save(crop(a, 1050, 540, 640, 360, 2)[0], f"assets_ba_{nm}_off.jpg"), save(crop(b, 1050, 540, 640, 360, 2)[0], f"assets_ba_{nm}_on.jpg"),
                                 "NEW_ASSETS off (v1 set)", "on", "2x zoom. The background photo is drawn from a different pool (same random stream), so the ground may differ, plus the new rock / leaf / dirt layers."))
for s, nm in [(7, "a"), (16, "b")]:
    a, _, _ = render(s, **W3, grass_blades=False); b, _, _ = render(s, **W3, grass_blades=True)
    f8["before_after"].append(BA(f"Grass blades off / on (seed {s})", save(crop(a, 1050, 540, 640, 360, 2)[0], f"blades_ba_{nm}_off.jpg"), save(crop(b, 1050, 540, 640, 360, 2)[0], f"blades_ba_{nm}_on.jpg"),
                                 "GRASS_BLADES off", "on", "2x zoom. Thin blades, tufts and wisps lie under and over the mines; blades over a mine hide part of it."))

# blades: size options, under / over
GB = dict(W3, rock_align_light=False, leaf_clumps_new=False, blades_over=(0, 0))
for sz in (40.0, 100.0, 160.0):
    r, _, _ = render(7, **GB, blades_under=(60, 60), blade_size_mm=sz, blade_fresh_prob=0.0)
    f8["options"].append(O(f"blade length {int(sz)} mm", f"grass_blades=True, blades_under=60, blades_over=0, blade_size_mm={sz}", save(crop(r, 1050, 540, 640, 360, 2)[0], f"blades_size_{int(sz)}.jpg"),
                           "2x zoom, 60 blades under the mines. Length is in millimetres and converted with the scene's px/mm, so blades are a few px wide."))
r, _, _ = render(7, **{**GB, "blades_over": (0, 0)}, blades_under=(60, 60))
f8["options"].append(O("blades under the mines (60)", "blades_under=60, blades_over=0", save(crop(r, 1050, 540, 640, 360, 2)[0], "blades_under_60.jpg"), "Blades drawn before the mines; the mines lie on top of them."))
OM = dict(GB, blades_under=(0, 0), blades_over=(0, 0), blades_on_mine_count=3, blade_fresh_prob=0.0)
for p in (0.0, 0.6, 1.0):
    r, _, _ = render(7, **OM, blades_over_on_mine=p)
    f8["options"].append(O(f"blades on each mine: probability {p}", f"blades_over_on_mine={p}, blades_on_mine_count=3 (default 1-4)", save(crop(r, 1050, 540, 640, 360, 2)[0], f"blades_onmine_{str(p).replace('.','_')}.jpg"),
                           "2x zoom, three mines. BLADES_OVER_ON_MINE is the per-mine chance of extra over-layer blades centred on the mine's box (expanded 20%), so they cross the mine."))
for s_, nm in [(7, "a"), (16, "b")]:
    a, _, _ = render(s_, **OM, blades_over_on_mine=0.0); b, _, _ = render(s_, **OM, blades_over_on_mine=1.0)
    f8["before_after"].append(BA(f"Blades crossing a mine: 0 vs 1.0 (seed {s_})", save(mine_crop(a, 6, 1050, 470), f"blades_ba_{nm}_off.png"), save(mine_crop(b, 6, 1050, 470), f"blades_ba_{nm}_on.png"), "blades_over_on_mine=0", "blades_over_on_mine=1.0 (3 blades)",
                                  "6x zoom on the middle mine, same seed. Blades lie over the mine and hide part of it; the visible-mask label shrinks accordingly."))
dump("frag_8.json", f8)

# ================= 9 labels
f9 = {"id": "labels", "title": "Label policy (visible-mask boxes)", "flag": "LABEL_VISIBLE_MASK",
      "summary": "v1 drew the label box around the mine as it would look unobstructed, even when rocks, grass or soil covered part of it, so the box could include things the camera cannot see. v2 builds the box from the pixels of the mine that are actually visible after burial soil and the overgrowth layer. That matches what a human annotator would draw on a real photo.",
      "how": "Mine.label: with LABEL_VISIBLE_MASK the visible mask = mine alpha after burial soil, minus accumulated overgrowth alpha; box = bounding box of pixels with alpha > 0.5. A mine with fewer than LABEL_MIN_VISIBLE_PX (default 1) visible pixels gets no box.",
      "code": "DatasetGenerator/objects.py: Mine.label; scene.py (occlusion buffer); controlPanel: LABEL_VISIBLE_MASK, LABEL_ALPHA_THRESHOLD, LABEL_MIN_VISIBLE_PX",
      "options": [], "before_after": [],
      "notes": "OPEN QUESTION: a mine fully hidden by overgrowth currently gets no box (LABEL_MIN_VISIBLE_PX = 1), so it becomes an unlabelled mine, i.e. a (rare) false negative for training; alternatives are keeping it labelled or dropping that image. A mine that is only a few pixels visible still gets a tiny box. Red = box with the mask switched off (v1 policy), green = visible-mask box."}
kwl = dict(n_mines=8, min_mines=8, zero_mine_prob=0.0, psf_sigma=0.3, motion_blur_prob=0)


def lab_pair(rgb, la, lb, cx, cy):
    c, (x0, y0) = crop(rgb, cx, cy, 320, 180, 3)
    before = draw_boxes(c, la, x0, y0, 3, (255, 40, 40), 2)
    after = draw_boxes(c, la, x0, y0, 3, (255, 40, 40), 1); after = draw_boxes(after, lb, x0, y0, 3, (0, 255, 0), 2)
    return before, after


found = []; hidden = None
for seed in range(200, 224):
    ra, la, ma = render(seed, **kwl, label_visible_mask=False)
    rb, lb, mb = render(seed, **kwl, label_visible_mask=True)
    for j, (mm_off, mm_on) in enumerate(zip(ma["mines"], mb["mines"])):
        if not mm_off.get("labelled"): continue
        box_off = mm_off["box"]
        if mm_on.get("labelled"):
            r = (mm_on["box"][2] * mm_on["box"][3]) / (box_off[2] * box_off[3])
            cx, cy = box_off[0] * W, box_off[1] * H
            if r < 0.75 and 160 < cx < W - 160 and 90 < cy < H - 90:
                found.append((r, seed, j, mm_on["burial"].get("buried", False)))
        elif hidden is None:
            hidden = (seed, j)
    if len(found) >= 6 and hidden: break
found.sort()
print("found", found[:6], "hidden", hidden)
for k, (r, seed, j, buried) in enumerate(found[:3]):
    ra, la, ma = render(seed, **kwl, label_visible_mask=False); rb, lb, mb = render(seed, **kwl, label_visible_mask=True)
    bx = ma["mines"][j]["box"]
    # boxes belonging to this mine only (single-mine pair so colours are unambiguous)
    box_off = [[0, *bx]]; box_on = [[0, *mb["mines"][j]["box"]]]
    be, af = lab_pair(rb, box_off, box_on, bx[0] * W, bx[1] * H)
    f9["before_after"].append(BA(f"Partly covered mine, seed {seed} #{j} (box area x{r:.2f})", save(be, f"label_ba_{k}_off.png"), save(af, f"label_ba_{k}_on.png"),
                                 "mask off: v1 box (red)", "mask on: visible-part box (green)", "3x zoom. Same pixels in both images; the red box (v1 policy) includes the covered part of the mine, the green one hugs what is visible."))
# burial pair
rkw = dict(**BASE, psf_sigma=0.3, motion_blur_prob=0); rkw.pop("burial_prob")
for s, nm in [(13, "a")]:
    ra, la, ma = render(s, **rkw, burial_prob=1.0, burial_fraction=0.5, burial_tilt=12, label_visible_mask=False)
    rb, lb, mb = render(s, **rkw, burial_prob=1.0, burial_fraction=0.5, burial_tilt=12, label_visible_mask=True)
    be, af = lab_pair(rb, la, lb, 960, 540)
    f9["before_after"].append(BA("Half-buried mine", save(be, f"label_ba_bur_off.png"), save(af, f"label_ba_bur_on.png"), "mask off: v1 box (red)", "mask on (green)",
                                 f"3x zoom, 50% burial. Hidden fraction achieved {mb['mines'][0]['burial'].get('achieved', 0):.2f}. Note: v1 mode took the box from the clipped sprite alpha before soil; the visible-mask box also excludes the soil line and lip."))
if hidden:
    seed, j = hidden
    rb, lb, mb = render(seed, **kwl, label_visible_mask=True)
    ra, la, ma = render(seed, **kwl, label_visible_mask=False)
    bx = ma["mines"][j]["box"]
    be, af = lab_pair(rb, [[0, *bx]], [], bx[0] * W, bx[1] * H)
    f9["options"].append(O("fully hidden mine (no box)", f"seed {seed}, mine #{j}, LABEL_MIN_VISIBLE_PX=1", save(af, "label_hidden.png"),
                           "Red thin box: where v1 would have labelled the mine. With the visible mask no pixel is visible, so no label is written (the open question in the notes)."))
else:
    f9["notes"] += " (No fully hidden mine turned up in the sampled seeds, so no example image.)"
f9["options"].insert(0, O("example: policy summary", "LABEL_VISIBLE_MASK=True, LABEL_ALPHA_THRESHOLD=0.5", f9["before_after"][0]["after"] if f9["before_after"] else "", "See the before / after pairs below.")) if False else None
dump("frag_9.json", f9)

# ================= 11 flip (face-down) -- built before 10 so ablation can mention it
f11 = {"id": "flip", "title": "Face-up and face-down mines", "flag": "FLIP_PROB",
       "summary": "A mine on the ground can lie on its bottom or on its back, showing its underside. v2 flips each mine (rotated 180 degrees about its long axis) with probability FLIP_PROB = 0.30, so the detector sees both the top and the different underside shape, with the same colour, shading, shadow and burial machinery. Without it every training mine would show only its upper surface.",
       "how": "features/mesh.py: sample_pose returns (pitch, roll, yaw, face_down); a face-down mine starts from a rest attitude computed from the mesh's stable pose (about 1.5 deg off flat so a wing tip and the body touch the ground), and tilts of sigma 5 deg and the yaw are applied on top. MINE_POSE accepts a 4th value face_down; override {'flip': True/False} or FLIP_PROB.",
       "code": "DatasetGenerator/features/mesh.py: sample_pose, face_down_base; objects.py: Mine._render_mesh; controlPanel: FLIP_PROB",
       "options": [], "before_after": [],
       "notes": "A face-down mine props one wing on the body, so its shadow is longer than a face-up mine's (physically plausible). The underside geometry is plausible but untextured (no moulding detail). The mirrored silhouette is what makes it recognisably different from face-up at the same yaw."}
sc = dict(n_mines=8, min_mines=8, zero_mine_prob=0.0, burial_prob=0.0)
for p in (0.0, 0.3, 1.0):
    rgb, lab, meta = render(5, **sc, flip_prob=p)
    nd = sum(m["face_down"] for m in meta["mines"])
    f11["options"].append(O(f"FLIP_PROB = {p}", f"flip_prob={p}, seed 5, 8 mines ({nd} face down here)", save(frame(rgb, 1280), f"flip_prob_{str(p).replace('.','_')}.jpg"),
                            "Same scene, same positions and sizes; only which mines are flipped changes."))
fk = dict(n_mines=1, mine_positions=[(960, 540)], mine_scale=0.35, burial_prob=0, psf_sigma=0.3, motion_blur_prob=0)
rows = []
for fd in (False, True):
    row = []
    for yaw in (0, 60, 120, 200):
        r, _, _ = render(13, **fk, mine_pose=(2, -2, yaw, fd))
        c = crop(r, 960, 540, 180, 180, 1)[0]
        c = cv2.resize(c, (340, 340), interpolation=cv2.INTER_NEAREST)
        row.append(tag(c, f"{'face down' if fd else 'face up'} yaw {yaw}", "bl"))
    rows.append(np.hstack(row))
f11["options"].append(O("yaw strip: face up (top) vs face down (bottom)", "mine_pose=(2, -2, yaw, face_down), yaw 0 / 60 / 120 / 200, seed 13, scale 0.35", save(np.vstack(rows), "flip_strip.png"),
                        "Same mine and yaw in each column. Face down is a mirrored outline and shows the underside (flat base, different light and wing profile). 1.9x zoom."))
for s, nm in [(13, "a"), (12, "b")]:
    a, _, ma = render(s, **fk, mine_pose=(2, -2, 30, False)); b, _, mb = render(s, **fk, mine_pose=(2, -2, 30, True))
    f11["before_after"].append(BA(f"Face up vs face down (seed {s})", save(mine_crop(a, 4), f"flip_ba_{nm}_up.png"), save(mine_crop(b, 4), f"flip_ba_{nm}_down.png"), "face up", "face down",
                                  f"4x zoom, same mine, yaw and position. Shadow length {ma['mines'][0]['shadow']['length_px']:.0f} px up vs {mb['mines'][0]['shadow']['length_px']:.0f} px down (propped wing)."))
dump("frag_11.json", f11)

# ================= 10 whole image
f10 = {"id": "whole", "title": "Whole-image comparison", "flag": "all flags (V2_FLAGS)",
       "summary": "The features above combined. Same seed, v1 against v2 shows the overall change; the ablation sheet switches each flag on alone; the 3x3 grid shows how varied v2 scenes are. FLIP_PROB = 0.30 applies to the v2 mines in the whole-image pictures (so about a third are face down) except in the ablation sheet, where mines are fixed face up.",
       "how": "render_scene(seed, overrides): v1 uses {'v1': True} (every flag off, v1 post shader); the ablation uses {'only': [FLAG]}. Each subsystem draws from its own random stream so a flag changes only its own feature.",
       "code": "DatasetGenerator/scene.py: render_scene; config.py: make_config (v1 / only); scripts/visual_check.py", "options": [], "before_after": [],
       "notes": "The v1 and v2 images share a seed, not a scene: v1 mode picks its backgrounds from the v1 pool and the v2 sampler differs, so the ground and mines are not identical. Per-flag ablation images keep the same random streams, so they are directly comparable. The ablation uses 3 mines at fixed positions, burial 35% for visibility and FLIP_PROB 0 (mines face up)."}
for s, nm in [(5, "a"), (9, "b")]:
    a, la, _ = render(s, v1=True); b, lb, mb = render(s)
    f10["before_after"].append(BA(f"v1 vs v2, seed {s}", save(frame(a, 1280), f"whole_ba_{nm}_v1.jpg"), save(frame(b, 1280), f"whole_ba_{nm}_v2.jpg"), "v1", f"v2 (FLIP_PROB {0.3}, {len(mb['mines'])} mines)",
                                  "Full frame at 2/3 size. v2: shadows consistent with one sun, varied mine colours, soil blending, grass blades, jitter."))
cfg = make_config({})
flags = list(cfg.V2_FLAGS)
ab = dict(n_mines=3, mine_positions=[(800, 560), (1050, 470), (1300, 640)], mine_scale=0.35, mine_pose=(3, -2, 30), burial_prob=1.0, burial_fraction=0.35, flip_prob=0.0, rocks_to_spawn_min=10, rock_align_light=False)
tiles = []
entries = [("v1 (all off)", dict(v1=True))] + [("only " + f, dict(only=[f])) for f in flags] + [("all on (v2)", {})]
for lbl, d in entries:
    r, _, _ = render(12, **ab, **d)
    c = cv2.resize(crop(r, 1050, 540, 640, 360, 1)[0], (460, 259), interpolation=cv2.INTER_AREA)
    t = tag(c, lbl, "tl").copy(); t[:2] = 0; t[:, :2] = 0
    tiles.append(t)
f10["options"].append(O("per-feature ablation sheet", "seed 12, only=[FLAG] for each of " + ", ".join(flags), save(tiles_grid(tiles, 3), "ablation_sheet.jpg"),
                        "Each tile enables one flag alone on top of the v1 pipeline (top-left = v1, last = everything). Features that need the mesh (burial, colour palette, mesh shadows) do little without MESH_MINES, as documented."))
tl = []
for s in range(40, 49):
    r, _, _ = render(s)
    tl.append(cv2.resize(r, (460, 259), interpolation=cv2.INTER_AREA))
f10["options"].append(O("3x3 grid of v2 scenes", "seeds 40-48, all defaults", save(tiles_grid(tl, 3), "grid_3x3.jpg"), "Nine unrelated v2 images at 460 px per tile: different ground, light, clutter and mines."))
dump("frag_10.json", f10)
print("done")
