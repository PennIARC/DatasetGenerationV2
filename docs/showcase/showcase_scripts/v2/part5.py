from v2lib import *
f12 = {"id": "rock_seating", "title": "Rock and debris seating (contact shadows)", "flag": "SHADOWS (ROCK_CONTACT_SHADOW, ROCK_CAST_SHADOW, ROCK_RIM_BLEND)",
       "summary": "A pasted rock cut-out looks like a sticker unless it appears to touch the ground. v2 adds a soft contact shadow right under rocks, dirt clods and leaf clumps, a sun-direction cast shadow, and a rim blend that tints the rock edge toward the local ground and darkens the side away from the sun. Mines already had such cues; without them on the clutter, 'seated and shadowed = mine' would be a shortcut for the detector.",
       "how": "debris_shadow: contact shadow = dilated, blurred alpha shifted slightly away from the sun, darkening 20-50% scaled by the image's shadow strength; cast shadow = swept silhouette with capped length; rim blend = 1.5 px edge tinted toward the ground, darker on the shadow side. Rocks are otherwise rotated so their baked-in bright side faces the sun; these comparisons set rock_align_light=False so rotation is identical across variants.",
       "code": "DatasetGenerator/features/shadows.py: debris_shadow; objects.py: EnvironmentDebris.draw; controlPanel: ROCK_CONTACT_SHADOW, ROCK_CAST_SHADOW, ROCK_RIM_BLEND, ROCK_CONTACT_*, ROCK_HEIGHT_FRAC",
       "options": [], "before_after": [],
       "notes": "On this busy grass background the shadow is hard to see at 35-65 deg elevation (best at 18 deg, where the dark side of the rock and the shadow edge show); on pale ground the effect is clearer. The shadows are 2D approximations (swept silhouettes) and the rock photos have their own baked-in lighting, so a rock can still look flat or lit from a different side, especially with rock_align_light off. Contact shadow is weaker in overcast images. Seed 30 with leaf clumps and blades off to keep the rock clear; azimuth 120 deg in every image (arrow overlay shows sun direction)."}
S = dict(n_mines=0, overcast_prob=0, rocks_to_spawn_min=14, rocks_to_spawn_max=14, rock_align_light=False, sun_azimuth=120, shadow_strength=0.5, sun_elevation=35, bg_zoom=1.0, psf_sigma=0.3, motion_blur_prob=0, leaf_clumps_new=False, grass_blades=False)
(rg, _, _), rk = render_rocks(30, **S)
rk = sorted([r for r in rk if r[2] >= 80 and 200 < r[0] < 1700 and 150 < r[1] < 900], key=lambda r: -r[2])
rk = [r for r in rk if r[:2] == (540, 690)] + [r for r in rk if r[:2] == (896, 428)]
print(rk)
cx0, cy0 = rk[0][0] + rk[0][2] // 2, rk[0][1] + rk[0][3] // 2
V = [("shadows off", dict(shadows=False)), ("contact shadow only", dict(rock_cast_shadow=False)),
     ("full, sun 18 deg", dict(sun_elevation=18)), ("full, sun 35 deg", dict(sun_elevation=35)), ("full, sun 65 deg", dict(sun_elevation=65))]
imgs = {}
for lbl, d in V:
    r, _, _ = render(30, **{**S, **d}); imgs[lbl] = r
    el = d.get("sun_elevation", 35)
    im = mine_crop(r, 6, cx0, cy0)
    if "off" not in lbl: im = arrow_overlay(im, 120, el)
    f12["options"].append(O(lbl, ", ".join(f"{k}={v}" for k, v in d.items()), save(im, f"rock_opt_{len(f12['options'])}.png"), "6x zoom on one rock; same rock, same rotation."))
for k, rr in enumerate(rk):
    cx, cy = rr[0] + rr[2] // 2, rr[1] + rr[3] // 2
    f12["before_after"].append(BA(f"Rock {k+1}: no shadows vs full", save(mine_crop(imgs["shadows off"], 6, cx, cy), f"rock_ba{k}_off.png"), save(mine_crop(imgs["full, sun 35 deg"], 6, cx, cy), f"rock_ba{k}_on.png"),
                                  "SHADOWS off", "contact + cast + rim", "6x zoom, sun elevation 35: the rock sits on the ground instead of floating."))
    f12["before_after"].append(BA(f"Rock {k+1}: contact only vs full", save(mine_crop(imgs["contact shadow only"], 6, cx, cy), f"rock_ba{k}_contact.png"), save(mine_crop(imgs["full, sun 35 deg"], 6, cx, cy), f"rock_ba{k}_full.png"),
                                  "contact shadow only", "contact + cast", "Adding the sun-direction cast shadow on top of the contact shadow."))
dump("frag_12.json", f12)
print("done")
