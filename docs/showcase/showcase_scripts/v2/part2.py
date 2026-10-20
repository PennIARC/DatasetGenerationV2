from v2lib import *

# ================= 2 soft edges & optics
f2 = {"id": "soft_edges", "title": "Soft edges and optics (blur)", "flag": "SOFT_EDGES, BLUR",
      "summary": "v1 enlarged and rotated sprites with nearest-neighbour sampling, giving jagged, hard-edged cut-outs that no real camera produces, and then added no lens blur. v2 draws at 4x size and averages down once (so edges get partial-coverage pixels), feathers rocks and grass, and finally blurs the whole picture with a lens-like kernel (sometimes plus motion blur). Without this the detector can learn 'razor-sharp pasted edge = mine'; real aerial frames are soft and slightly motion-smeared.",
      "how": "SOFT_EDGES: features/edges.py resize_rotate (area downscale on premultiplied RGBA, one resample, 0.8 px alpha feather on debris, 1 px erosion of Otsu masks). BLUR: features/camera.py apply_blur: Gaussian PSF sigma U(0, 1.5) px, with probability 0.15 a linear motion blur of 1-4 px at a random angle.",
      "code": "DatasetGenerator/features/edges.py: resize_rotate; features/camera.py: apply_blur; controlPanel: SUPERSAMPLE, DEBRIS_ALPHA_FEATHER, PSF_SIGMA, MOTION_BLUR_PROB, MOTION_BLUR_LENGTH",
      "options": [], "before_after": [],
      "notes": "Blur is spatially uniform (no depth-of-field variation) and motion blur is a straight line. For the edge zoom both images have blur switched off (psf_sigma=0, no motion blur) so you see the raw edge. The 'off' image also turns SOFT_EDGES off only; everything else is identical."}
E_ = dict(**BASE, photometric_jitter=False, shadows=False)
qs = dict(photometric_jitter=False)
for sg in (0.0, 0.7, 1.5):
    rgb, _, _ = render(13, **BASE, psf_sigma=sg, motion_blur_prob=0)
    f2["options"].append(O(f"lens blur sigma {sg} px", f"psf_sigma={sg}, motion_blur_prob=0", save(mine_crop(rgb, 4), f"blur_psf_{str(sg).replace('.','_')}.png"),
                           "4x zoom. sigma 0 keeps the anti-aliased edge sharp, 0.7 is mild defocus, 1.5 (top of the sampled range) is clearly soft."))
rgb, _, _ = render(13, **BASE, psf_sigma=0.0, motion_blur_prob=1.0, motion_blur_length=4.0)
f2["options"].append(O("motion blur 4 px", "psf_sigma=0, motion_blur_prob=1, motion_blur_length=4", save(mine_crop(rgb, 4), "blur_motion_4.png"),
                       "A 4 px line-shaped smear at a random angle (the angle is drawn per image); applied to everything, mine and ground alike."))
for s, nm in [(13, "a"), (12, "b")]:
    kw = dict(**BASE, psf_sigma=0.0, motion_blur_prob=0, shadows=False)
    r0, _, _ = render(s, **kw, soft_edges=False); r1, _, _ = render(s, **kw, soft_edges=True)
    f2["before_after"].append(BA(f"Hard v1-style edge vs soft edge (seed {s})",
        save(mine_crop(r0, 6), f"edges_ba_{nm}_off.png"), save(mine_crop(r1, 6), f"edges_ba_{nm}_on.png"), "SOFT_EDGES off", "SOFT_EDGES on",
        "6x zoom, no lens blur. Off: stair-stepped outline with a coloured fringe; on: the boundary pixels blend part mine, part ground."))
r0, _, _ = render(13, **BASE, psf_sigma=0.0, motion_blur_prob=0); r1, _, _ = render(13, **BASE, psf_sigma=1.2, motion_blur_prob=0)
f2["before_after"].append(BA("Lens blur off vs on (psf_sigma 1.2)", save(mine_crop(r0, 4), "blur_ba_off.png"), save(mine_crop(r1, 4), "blur_ba_on.png"),
                             "BLUR off (sigma 0)", "BLUR on (sigma 1.2)", "4x zoom: fine ground texture and the mine's outline lose their crispness."))
dump("frag_2.json", f2)

# ================= 3 shadows
SP = [(800, 560), (1050, 470), (1300, 640)]
S3 = dict(n_mines=3, mine_positions=SP, mine_scale=0.35, burial_prob=0, overcast_prob=0, rocks_to_spawn_min=14, rocks_to_spawn_max=14,
          mine_pose=(3, -2, 30), rock_align_light=False)
SEED3 = 12


def scene3(**ov):
    kw = {**S3, **ov}
    return render(SEED3, **kw)[0]


def win(rgb, z=2):
    return crop(rgb, 1050, 540, 640, 360, z)[0]


f3 = {"id": "shadows", "title": "Cast shadows", "flag": "SHADOWS",
      "summary": "v1 had no shadows at all: mines floated on the ground. In v2 each image has one sun (direction, height, strength) and mines, rocks, grass and dirt all cast shadows that agree with it, and mines are shaded by the same light. Shadows are one of the most important real cues for an object lying on the ground. Rocks get shadows too, otherwise 'has a shadow = mine' would become a shortcut.",
      "how": "features/sun.py samples one sun per image (azimuth, elevation 15-70 deg, strength 0.25-0.65; 15% overcast images with weak, very soft shadows). Mines: the 3D triangles are projected along the sun onto the ground and blurred by a distance-dependent penumbra, plus a little contact darkening. Rocks / grass / dirt: the alpha silhouette is swept away from the sun by height / tan(elevation) and blurred the same way.",
      "code": "DatasetGenerator/features/sun.py: sample_sun; features/shadows.py: mine_shadow, debris_shadow; objects.py: Mine._draw_shadow, EnvironmentDebris.draw",
      "options": [], "before_after": [],
      "notes": "No self-shadowing on the mine (wings do not shade the body). The background photos have their own baked-in shadows in arbitrary directions, which can contradict the synthetic sun. Mine shadows fall on a flat plane, not over rocks or grass relief. PFM-1 mines are thin, so their shadows are short (physically right). Rocks keep their rotation (rock_align_light=False) so only the shadows differ between off and on. Arrow overlay: points toward the sun; shadows fall the opposite way. Azimuth 0 = sun toward image right, 90 = toward image top."}
base3 = dict(sun_azimuth=120, sun_elevation=35, shadow_strength=0.45)
for el in (15, 35, 70):
    rgb = scene3(**{**base3, "sun_elevation": el})
    im = arrow_overlay(win(rgb), 120, el)
    f3["options"].append(O(f"elevation {el} deg", f"sun_elevation={el}, sun_azimuth=120, shadow_strength=0.45", save(im, f"shadow_el_{el}.jpg"),
                           "Same scene, 2x zoom. Low sun: long soft shadows; high sun: short, tight ones under each object."))
rgb = scene3(overcast_prob=1.0, sun_elevation=50, sun_azimuth=120)
f3["options"].append(O("overcast", "overcast_prob=1 (strength U(0.03, 0.15), penumbra x6)", save(win(rgb), "shadow_overcast.jpg"), "Diffuse light: shadows almost vanish and are very blurry."))
for az in (0, 120, 240):
    rgb = scene3(**{**base3, "sun_azimuth": az})
    f3["options"].append(O(f"azimuth {az} deg", f"sun_azimuth={az}, sun_elevation=35", save(arrow_overlay(win(rgb), az, 35), f"shadow_az_{az}.jpg"),
                           "Shadows of mines and rocks all point away from the arrow; rock photos are also rotated so their baked-in bright side faces the sun."))
for st in (0.25, 0.45, 0.65):
    rgb = scene3(**{**base3, "shadow_strength": st})
    f3["options"].append(O(f"strength {st}", f"shadow_strength={st}, sun_elevation=35, azimuth=120", save(arrow_overlay(win(rgb), 120, 35), f"shadow_str_{str(st).replace('.','_')}.jpg"),
                           "Fraction of light removed in shadow (sampled 0.25-0.65 per image)."))
# before / after
a, b = scene3(**base3, shadows=False), scene3(**base3, shadows=True)
f3["before_after"].append(BA("Mines: shadows off / on", save(mine_crop(a, 4, 1050, 470), "shadow_ba_mine_off.png"),
                             save(arrow_overlay(mine_crop(b, 4, 1050, 470), 120, 35), "shadow_ba_mine_on.png"), "SHADOWS off", "SHADOWS on",
                             "4x zoom on the middle mine. With shadows the mine sits on the ground, has a lit and a dark side and a soft shadow."))
f3["before_after"].append(BA("Whole region: mines and rocks", save(arrow_overlay(win(a), 120, 35), "shadow_ba_rocks_off.jpg"),
                             save(arrow_overlay(win(b), 120, 35), "shadow_ba_rocks_on.jpg"), "SHADOWS off", "SHADOWS on",
                             "2x zoom. Rocks, leaf litter and the mines all gain shadows falling the same way (away from the arrow), so the debris is consistent with the sun that lights the mines."))
# rock close-up: find a rock near the centre
(rg, _, _), rk = render_rocks(SEED3, **{**S3, **base3})
rk = sorted([r for r in rk if r[2] >= 80 and 150 < r[0] < 1800 and 100 < r[1] < 950], key=lambda r: (r[0] + r[2] / 2 - 1050) ** 2 + (r[1] + r[3] / 2 - 540) ** 2)
rx = rk[0]; print("rock", rx)
a2 = scene3(**base3, shadows=False)
cxr, cyr = rx[0] + rx[2] // 2, rx[1] + rx[3] // 2
f3["before_after"].append(BA("A single rock: shadow off / on", save(mine_crop(a2, 6, cxr, cyr), "shadow_ba_rock1_off.png"),
                             save(mine_crop(b, 6, cxr, cyr), "shadow_ba_rock1_on.png"), "SHADOWS off", "SHADOWS on",
                             "6x zoom on a rock: the shadow is a swept, blurred copy of its outline, away from the sun."))
dump("frag_3.json", f3)

# ================= 4 soil blending
f4 = {"id": "soil_blend", "title": "Soil blending", "flag": "SOIL_BLEND",
      "summary": "In v1 the mine sprite was pasted with a clean outline and a few hard-edged brown dots. In reality a mine lying in the field is dusty, partly coated with the local soil, darker where it touches the ground and shares the scene's exposure. v2 adds a noisy dust layer in the local ground colour, a darker contact band, soft soil grains and matches the mine's brightness to its surroundings. This removes the 'clean sticker on a photo' look.",
      "how": "soil.soil_blend samples the composite under the mine: (a) exposure harmonisation, (b) dust layer coloured by the blurred local ground, with opacity from fBm noise, (c) 1.5-4 px contact band inside the edge, darker and dustier, (d) thresholded-noise soil grains 0-5% of the mine, local colour. Ground dirt squares also become soft, tinted irregular grains (soil.dirt_grain).",
      "code": "DatasetGenerator/features/soil.py: soil_blend, dirt_grain; objects.py: Mine.draw; controlPanel: DUST_STRENGTH, CONTACT_BAND_*, GRAIN_*",
      "options": [], "before_after": [],
      "notes": "Dust is a 2D overlay (no accumulation in crevices) and there is no wetness or mud. Default dust is drawn per mine from a triangular distribution (0.25 / 0.30 / 0.50, mean 0.35). With dust 0 the contact band, grains and exposure matching are still active. In the strength images grain density is fixed at 3% so that only the dust differs."}
kw4 = dict(**BASE, psf_sigma=0.3, motion_blur_prob=0, shadows=True, grain_density=0.03)
r, _, _ = render(13, **kw4, soil_blend=False)
f4["options"].append(O("blend off (v1 look)", "soil_blend=False", save(mine_crop(r, 5), "soil_opt_off.png"), "5x zoom: clean paste with hard dots."))
r, _, _ = render(13, **kw4, dust_strength=0.0)
f4["options"].append(O("0% (blend on, no dust)", "soil_blend=True, dust_strength=0 (grain_density=0.03)", save(mine_crop(r, 5), "soil_dust_0.png"), "Contact band, grains and exposure matching only; no dust layer."))
for d in (0.25, 0.35, 0.5):
    r, _, _ = render(13, **kw4, dust_strength=d)
    f4["options"].append(O(f"dust {int(d*100)}%", f"dust_strength={d} (grain_density=0.03)", save(mine_crop(r, 5), f"soil_dust_{int(d*100)}.png"),
                           "Dust opacity ceiling (before the fBm noise modulates it). The sampler now draws it per mine from a triangle: low 0.25, mode 0.30, high 0.50 (mean 0.35)."))
for s, nm in [(13, "a"), (12, "b")]:
    kw = dict(**BASE, psf_sigma=0.0, motion_blur_prob=0, shadows=True, grain_density=0.04, dust_strength=0.35)
    r0, _, _ = render(s, **kw, soil_blend=False); r1, _, _ = render(s, **kw, soil_blend=True)
    f4["before_after"].append(BA(f"Soil blending off / on (seed {s})", save(mine_crop(r0, 8, 960, 540), f"soil_ba_{nm}_off.png"), save(mine_crop(r1, 8, 960, 540), f"soil_ba_{nm}_on.png"),
                                 "SOIL_BLEND off (hard dots)", "SOIL_BLEND on", "8x zoom (no lens blur). Look at the contact band at the edge, the blotchy dust that picks up the ground colour, and the grains that replace v1's round dots."))
dump("frag_4.json", f4)
print("done")
