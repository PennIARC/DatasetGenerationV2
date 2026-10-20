from v2lib import *
import colorsys
from features.colour import sample_colour_params, colour_from_params
from config import make_config

# ================= 5 burial
f5 = {"id": "burial", "title": "Partial burial", "flag": "BURIAL",
      "summary": "Real mines are often half-sunk in soil, so only part of the body shows. In v1 every mine was whole and sitting on top. In v2 35% of mines are buried: a soil plane (tilted up to 25 deg) hides a chosen fraction of the mine, with a rough soil line and a small soil lip along it. The label box covers only the part that is still visible. This teaches the detector to find mines from a fragment (a wing, an edge) rather than only from the complete outline.",
      "how": "features/mesh.py: the soil plane offset is the burial-fraction quantile of the surface heights, so the hidden fraction of the top-down area is hit exactly; the 3D triangles are clipped against the plane (Sutherland-Hodgman) and the shadow is projected onto the same plane. soil.burial_overlay adds an fBm-roughened soil line and a berm (lip) in the local ground colour. The hidden fraction is capped at 50% (BURIAL_MAX_FRACTION); the achieved fraction is stored in the sidecar.",
      "code": "DatasetGenerator/features/mesh.py: sample_burial, clip_triangles, render_mine; features/soil.py: burial_overlay; controlPanel: BURIAL_PROB, BURIAL_FRACTION, BURIAL_MAX_FRACTION, BURIAL_TILT, BERM_*",
      "options": [], "before_after": [],
      "notes": "The soil plane is a plane (no local relief) and no soil is spilled onto the wings away from the line. The soil lip lies only along the true soil line and is tinted like the local ground, so it is subtle: the main cue is the missing part of the mine and the shrunken box (the earlier 1-2 px leftover outline is fixed, and the mine no longer shifts between burial off and on). The hidden fraction is the target; the soil-line roughness can add a few percent (achieved is capped at 50%). Boxes are drawn in green on every image below."}
kwb = dict(**BASE, psf_sigma=0.3, motion_blur_prob=0)
kwb.pop("burial_prob")
SEEDB = 13


def burial(seed, frac=None, tilt=None, **ov):
    kw = dict(kwb, burial_prob=0.0 if frac is None else 1.0, **ov)
    if frac is not None: kw["burial_fraction"] = frac
    if tilt is not None: kw["burial_tilt"] = tilt
    kw["mine_pose"] = (3, -2, 30)
    rgb, lab, meta = render(seed, **kw)
    b = meta["mines"][0]["burial"]
    cx, cy = 960, 540
    c, (x0, y0) = crop(rgb, cx, cy, 256, 144, 4)
    return draw_boxes(c, lab, x0, y0, 4), b, lab


for fr in (0.0, 0.2, 0.35, 0.5):
    im, b, _ = burial(SEEDB, None if fr == 0 else fr, 12)
    f5["options"].append(O(f"hidden {int(fr*100)}%", "burial_prob=0" if fr == 0 else f"burial_prob=1, burial_fraction={fr}, burial_tilt=12" + f" (achieved {b.get('achieved', 0):.2f})",
                           save(im, f"burial_frac_{int(fr*100)}.png"), "Green box = YOLO label from the visible part. 0.5 is the cap: at least half the mine always stays visible."))
for t in (0, 12, 25):
    im, b, _ = burial(SEEDB, 0.35, t)
    f5["options"].append(O(f"plane tilt {t} deg", f"burial_fraction=0.35, burial_tilt={t}", save(im, f"burial_tilt_{t}.png"),
                           "Tilt of the buried soil plane (its direction is random but fixed for the seed): the soil line runs at a different angle and the shadow lies on the tilted plane."))
for s, nm in [(13, "a"), (12, "b")]:
    a, _, la = burial(s, None, None); b_, bi, lb = burial(s, 0.4, 15)
    f5["before_after"].append(BA(f"Not buried vs 40% buried (seed {s})", save(a, f"burial_ba_{nm}_off.png"), save(b_, f"burial_ba_{nm}_on.png"), "BURIAL off", "40% buried",
                                 f"4x zoom, same mine, pose and position. The box shrinks to the visible part (green). Achieved hidden fraction {bi.get('achieved', 0):.2f}."))
dump("frag_5.json", f5)

# ================= 6 colour
f6 = {"id": "colour", "title": "Colour palette", "flag": "COLOUR_PALETTE",
      "summary": "v1 painted every mine the same dark olive-teal with tiny jitter, so colour alone told a detector 'mine'. v2 draws each mine's colour from realistic military-plastic families (olive drab, dark green, khaki, brown, tan), then adds sun-bleaching, a dirt tint and a brightness factor, so hue and brightness cover the real range and no single colour is a shortcut. Colours outside realistic plastics (blue, red...) are deliberately excluded.",
      "how": "features/colour.py: family by weight (olive 0.28, dark green 0.22, brown 0.20, khaki 0.15, tan 0.15), H, S, V uniform inside the family's range; with p=0.35 bleaching (S down, V up); with p=0.4 mix towards a dirt colour by up to 30%; brightness x U(0.85, 1.15). The result is the albedo that the scene lighting then shades.",
      "code": "DatasetGenerator/features/colour.py: sample_colour_params, colour_from_params; controlPanel: PALETTE, BLEACH_*, DIRT_TINT_*, BRIGHTNESS_JITTER",
      "options": [], "before_after": [],
      "notes": "Whether this palette matches real PFM-1 / field colours should be checked against reference photos; the ranges are a judgement call (arbitrary hues were excluded by decision). Each swatch is the same background and position, with the lighting and shading of that scene."}
cfg = make_config({})


def tile(rgb, tg):
    c = crop(rgb, 960, 540, 128, 128, 1)[0]
    t = tag(c, tg, "bl").copy(); t[:2] = 0; t[:, :2] = 0
    return t


kw6 = dict(n_mines=1, mine_positions=[(960, 540)], mine_scale=0.28, mine_pose=(3, -2, 30), burial_prob=0, psf_sigma=0.3, motion_blur_prob=0)
rng = np.random.default_rng(5)
tl, fams = [], {}
for i in range(60):
    p = sample_colour_params(rng, cfg); fams.setdefault(p["family"], []).append(p)
    rgb = colour_from_params(p["h"], p["s"], p["v"], p["bleach"], p["dirt_tint"], p["brightness"], cfg.DIRT_TINT_RGB)
    r, _, _ = render(13, **kw6, mine_colour=tuple(float(x) for x in rgb))
    tl.append(tile(r, p["family"][:5] + (" b" if p["bleach"] > 0 else "") + (" d" if p["dirt_tint"] > 0 else "")))
f6["options"].append(O("60 sampled colours, same background", "mine_colour = colour_from_params(sample_colour_params(...)), 60 draws, seed 13, scale 0.28", save(tiles_grid(tl, 10), "colour_sheet_60.jpg"),
                       "Tag: family; b = sun-bleached, d = dirt-tinted. Everything else (ground, position, pose, lighting) is identical, only the albedo changes."))
# per-family rows
rows = []
for fam in cfg.PALETTE:
    row = []
    for j in range(7):
        p = None
        while p is None:
            q = sample_colour_params(rng, cfg)
            if q["family"] == fam: p = q
        rgb = colour_from_params(p["h"], p["s"], p["v"], p["bleach"], p["dirt_tint"], p["brightness"], cfg.DIRT_TINT_RGB)
        r, _, _ = render(13, **kw6, mine_colour=tuple(float(x) for x in rgb))
        row.append(tile(r, fam[:8]) if j == 0 else tile(r, "#%d" % j))
    rows.append(np.hstack(row))
f6["options"].append(O("by family (7 samples each)", "rows: olive_drab, dark_green, khaki, brown, tan", save(np.vstack(rows), "colour_families.jpg"), "Each row is one family, with its internal spread."))
# v1 colour formula, 10 draws (same formula as colour.sample_colour with COLOUR_PALETTE off)
tl1 = []
for i in range(10):
    u = rng.random(4)
    c = np.array(cfg.V1_BASE_COLOUR) + (2 * u[0] - 1) * cfg.V1_COMMON_SHIFT
    c = np.clip(c + (2 * u[1:] - 1) * cfg.V1_CHANNEL_JITTER, 0, 1)
    r, _, _ = render(13, **kw6, mine_colour=tuple(float(x) for x in c))
    tl1.append(tile(r, "v1 colour"))
f6["options"].append(O("v1 colour for contrast (10 draws)", "v1 formula: base RGB (0.15, 0.38, 0.27) + common shift U(-0.3, 0.3) + per-channel U(-0.05, 0.05)", save(tiles_grid(tl1, 10), "colour_v1_10.jpg"),
                        "v1's colour formula: always the same teal-green hue, only lighter or darker."))
for s, nm in [(13, "a"), (12, "b")]:
    r0, _, _ = render(s, **BASE, colour_palette=False, psf_sigma=0.3, motion_blur_prob=0)
    # use different mine seed? colour is drawn from the same stream index, so palette changes only colour
    r1, _, m1 = render(s, **BASE, psf_sigma=0.3, motion_blur_prob=0)
    f6["before_after"].append(BA(f"v1 colour vs palette (seed {s})", save(mine_crop(r0, 4), f"colour_ba_{nm}_v1.png"), save(mine_crop(r1, 4), f"colour_ba_{nm}_v2.png"),
                                 "COLOUR_PALETTE off", f"palette ({m1['mines'][0]['colour']['family']})", "4x zoom. Same mine and scene, only the albedo is drawn differently."))
dump("frag_6.json", f6)

# ================= 7 photometric / blur / bg
import features.camera as cam
_orig = cam.sample_camera_params
CAMOV = {}


def _patched(rng, cfg):
    d = _orig(rng, cfg); d.update(CAMOV); return d


cam.sample_camera_params = _patched
f7 = {"id": "photometric", "title": "Photometric jitter and background augmentation", "flag": "PHOTOMETRIC_JITTER, BG_AUGMENT",
      "summary": "Real footage varies with camera exposure, white balance, sensor noise, JPEG quality and lens vignetting, and with the ground it flies over. v1 applied almost the same grain, colour fringe, vignette and contrast to every image, and gave the background only a small zoom. v2 randomises all of these per image (domain randomisation: deliberately varying nuisance factors so the detector cannot rely on them), and flips, rotates, zooms and colour-shifts the background photo.",
      "how": "features/camera.py sample_camera_params / apply_camera: exposure 0.75-1.25, gamma 0.85-1.15, red and blue white-balance gains 0.92-1.08, saturation 0.75-1.25, contrast 0.95-1.2, zero-mean Gaussian noise sigma 0-0.025 (0-50% colour), chromatic aberration up to 0.2% of width, vignette 0-0.5, JPEG quality 70-95. features/background.py: flips, 90-degree rotations, zoom 1-2, hue +-8 deg, saturation / brightness 0.8-1.2, channel gains 0.95-1.05.",
      "code": "DatasetGenerator/features/camera.py: sample_camera_params, apply_camera, jpeg_roundtrip; features/background.py: sample_background_params, make_background; fx.py: photometric",
      "options": [], "before_after": [],
      "notes": "No sensor-specific noise model (Poisson noise, banding); colour jitter is global per image, not per region. The eight jitter images below are the same scene with hand-picked, deliberately strong values (taken from the edges of the sampled ranges) so the effect is visible; real draws are usually milder. They are produced by temporarily substituting the sampled camera dict in the showcase script (the generator is untouched). JPEG q shown is applied via jpeg_roundtrip."}
PJ = [("exposure 0.75 (dark)", dict(exposure=0.75)), ("exposure 1.25 (bright)", dict(exposure=1.25)), ("gamma 1.15", dict(gamma=1.15)),
      ("white balance R 1.08 / B 0.92 (warm)", dict(wb_r=1.08, wb_b=0.92)), ("white balance R 0.92 / B 1.08 (cool)", dict(wb_r=0.92, wb_b=1.08)),
      ("saturation 0.75 (washed out)", dict(saturation=0.75)), ("saturation 1.25", dict(saturation=1.25)), ("contrast 1.2", dict(contrast=1.2)),
      ("sensor noise sigma 0.025", dict(noise_sigma=0.025, noise_chroma=0.5)), ("JPEG quality 70", dict(jpeg_quality=70)), ("vignette 0.5", dict(vignette=0.5))]
SB = dict(n_mines=3, mine_positions=[(800, 560), (1050, 470), (1300, 640)], mine_scale=0.35, burial_prob=0, mine_pose=(3, -2, 30),
          psf_sigma=0.3, motion_blur_prob=0, bg_augment=False)
neutral = dict(exposure=1.0, gamma=1.0, wb_r=1.0, wb_b=1.0, saturation=1.0, contrast=1.0, noise_sigma=0.0, noise_chroma=0.0, aberration=0.0, vignette=0.0, jpeg_quality=95)


def jit(label, d):
    global CAMOV
    CAMOV = {**neutral, **d}
    rgb, lab, meta = render_scene(13, dict(SB))
    rgb = jpeg_roundtrip(rgb, CAMOV["jpeg_quality"])
    return rgb


for lbl, d in PJ:
    rgb = jit(lbl, d)
    c = crop(rgb, 1050, 540, 640, 360, 2)[0]
    k = list(d)[0]
    f7["options"].append(O(lbl, "camera dict: " + ", ".join(f"{a}={b}" for a, b in d.items()) + " (others neutral)", save(c, f"jitter_{len(f7['options'])}_{k}.jpg"),
                           "2x zoom of the same scene; one parameter pushed to the end of its sampled range."))
# background augmentation options
CAMOV = {}
bgk = dict(n_mines=0, burial_prob=0, psf_sigma=0.3, motion_blur_prob=0, photometric_jitter=False)
BGO = [("off (reference)", dict(bg_augment=False)), ("horizontal flip", dict(bg_flip_prob=1.0, bg_rot90_prob=0.0, bg_zoom=1.0)),
       ("rotate 90 + zoom 1.8", dict(bg_flip_prob=0.0, bg_rot90_prob=1.0, bg_zoom=1.8)), ("colour jitter hue +8, sat 1.2, brightness 1.2", dict(bg_flip_prob=0, bg_rot90_prob=0, bg_zoom=1.0, bg_hue_shift=8.0, bg_saturation=1.2, bg_brightness=1.2))]
for i, (lbl, d) in enumerate(BGO):
    rgb, _, m = render(21, **bgk, **d)
    f7["options"].append(O("background: " + lbl, ", ".join(f"{a}={b}" for a, b in d.items()), save(frame(rgb, 960), f"bgaug_{i}.jpg"),
                           "Background photo only (no mines), photometric jitter off."))
# before / after photometric
for s, nm in [(13, "a"), (8, "b")]:
    kw = dict(SB, bg_augment=True)
    r0, _, _ = render(s, **{**kw, "photometric_jitter": False}); r1, _, m1 = render(s, **kw)
    r0 = jpeg_roundtrip(r0, 85); r1 = jpeg_roundtrip(r1, m1["post"]["jpeg_quality"])
    p = m1["post"]
    f7["before_after"].append(BA(f"v1 shader vs photometric jitter (seed {s})", save(crop(r0, 1050, 540, 640, 360, 2)[0], f"photo_ba_{nm}_off.jpg"), save(crop(r1, 1050, 540, 640, 360, 2)[0], f"photo_ba_{nm}_on.jpg"),
        "PHOTOMETRIC_JITTER off (v1 shader)", "on",
        f"2x zoom. Off: v1's fixed grain / 3.8 px colour fringe / vignette / contrast / JPEG 85. On (this draw): exposure {p['exposure']:.2f}, gamma {p['gamma']:.2f}, saturation {p['saturation']:.2f}, noise {p['noise_sigma']:.3f}, vignette {p['vignette']:.2f}, JPEG {p['jpeg_quality']}."))
r0, _, _ = render(13, **{**SB, "bg_augment": False}); r1, _, _ = render(13, **{**SB, "bg_augment": True})
f7["before_after"].append(BA("Background augmentation off / on", save(frame(r0, 960), "bgaug_ba_off.jpg"), save(frame(r1, 960), "bgaug_ba_on.jpg"), "BG_AUGMENT off", "BG_AUGMENT on", "Same scene (mines at identical positions); the background photo is flipped / rotated / zoomed / recoloured."))
dump("frag_7.json", f7)
print("done")
