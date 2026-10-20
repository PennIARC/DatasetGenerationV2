"""Writes ../backgrounds_index.json from the hand classification below + grass_bg_manifest.json."""
import json, os, glob
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.normpath(HERE + "/..")
V1 = "/Users/pranavgupta/PycharmProjects/IARCdatasetGeneration/DatasetGenerator/assets/backgrounds"
v1cls = {  # by sorted order of the Screenshot files then grassN
 "Screenshot 2026-02-07 at 4.17.23": ("grass_patchy", 1.0, "dappled grass with bare soil/stones"),
 "Screenshot 2026-02-07 at 4.17.41": ("grass_patchy", 1.0, "olive moss/grass with soil"),
 "Screenshot 2026-02-07 at 4.21.04": ("mixed_ground", 1.0, "rocks with grass"),
 "Screenshot 2026-02-07 at 4.21.15": ("mixed_ground", 1.0, "boulders with grass"),
 "Screenshot 2026-02-07 at 4.21.26": ("soil", 1.0, "dry soil with litter"),
 "Screenshot 2026-02-07 at 4.21.38": ("soil", 1.0, "bare brown soil, edge vegetation"),
 "Screenshot 2026-02-07 at 4.21.45": ("soil", 1.0, "dark rich soil"),
 "Screenshot 2026-02-07 at 4.21.51": ("gravel", 1.0, "pebbles with dry leaves"),
 "grass1": ("moss_clover", 1.0, "clover and grass, dark green"),
 "grass2": ("grass_fresh", 1.0, "bright green lawn, blurry streaks"),
 "grass3": ("grass_olive", 1.0, "olive/yellow-green mowed lawn"),
 "grass4": ("grass_olive", 1.0, "yellow-green overgrown"),
 "grass5": ("grass_patchy", 1.0, "green lawn with dry patches"),
 "grass6": ("grass_dry", 1.0, "dark grass with straw, shadowed"),
 "grass7": ("grass_dry", 1.0, "dry tan lawn"),
}
nw = {  # new ambientCG mosaics: id -> (category, weight, note)
 "Grass004": ("grass_fresh", .8, "flat CG-like green"), "Grass002": ("grass_fresh", .8, "dark green, flat"),
 "Grass003": ("grass_olive", .8, "olive-green, flat"), "Moss001": ("grass_patchy", 1, "green with tan"),
 "Moss002": ("moss_clover", .8, "cloudy green moss"), "Ground001": ("grass_patchy", 1, "dark olive mossy ground"),
 "Ground015": ("soil", 1, "dark litter soil"), "Ground023": ("soil", 1, "brown soil with leaf bits"), "Ground002": ("soil", 1, "dark brown soil"),
 "Ground009": ("soil", 1, "flat brown soil"), "Ground031": ("soil", 1, "grey-brown soil"), "Ground007": ("soil", 1, "pinkish-brown soil"),
 "Ground008": ("soil", .7, "flat mauve-brown soil"), "Ground004": ("soil", 1, "beige dry soil"), "Ground005": ("soil", 1, "beige dry soil"),
 "Ground027": ("sand", .3, "pale sand, low detail"), "Ground029": ("sand", .4, "beige sand"), "Ground033": ("sand", 0, "DROPPED: pale pink-beige sand"),
 "Ground034": ("sand", .25, "pale sand with specks"), "Ground049A": ("sand", .3, "tan sand"), "Ground092A": ("sand", 0, "DROPPED: cream, featureless"),
 "Ground026": ("sand", 0, "DROPPED: peach/pink, featureless"),
 "Ground019": ("gravel", 1, "grey gravel"), "Ground020": ("gravel", 1, "grey gravel with colour flecks"), "Ground022": ("gravel", .8, "light gravel"),
 "Ground028": ("gravel", 1, "gravel with sand"), "Ground018": ("gravel", 1, "dark grey gravel"), "Ground032": ("gravel", .8, "grey rough ground"),
 "Ground014": ("gravel", 0, "DROPPED: flat grey"), "Ground021": ("gravel", 0, "DROPPED: flat grey"),
 "Ground011": ("mixed_ground", .4, "pinkish rocky ground"), "Ground013": ("mixed_ground", 1, "grey-green mossy ground"),
 "Ground024": ("mixed_ground", 1, "grey-green ground with moss"), "Ground030": ("mixed_ground", .7, "pale ground with green specks"),
}
nw["Ground003"]=("grass_patchy", 1, "green weeds on soil, very natural")
for g in range(1, 21): nw.setdefault(f"Gravel{g:03d}", ("gravel", 1, "grey gravel"))
for g in ("Gravel002", "Gravel007"): nw[g] = ("gravel", .5, "flat grey gravel")
items = []
for f in sorted(os.listdir(V1)):
    k = os.path.splitext(f)[0].replace(" ", " ").rsplit(" ", 1)[0] if f.startswith("Screenshot") else os.path.splitext(f)[0]
    c, w, n = v1cls[k]
    items.append(dict(path=f, source="v1", category=c, family="grass" if c.startswith(("grass", "moss")) else "non_grass", weight=w, note="v1: " + n))
man = {m[0]: m for m in json.load(open(HERE + "/grass_bg_manifest.json"))}
REJ = set(os.listdir(A + "/backgrounds/_rejected"))
OVR = {"bg_Ground018.jpg": .4, "bg_Ground020.jpg": .4, "bg_real_02_Grass005_grass_fresh.jpg": .4, "bg_real_03_Grass005_grass_patchy.jpg": .4,
       "bg_real_18_Moss001_grass_patchy.jpg": .4}
for f in sorted(os.listdir(A + "/backgrounds")) + sorted(REJ):
    if f.startswith("_") or not f.endswith(".jpg"): continue
    if f in man:
        m = man[f]
        items.append(dict(path="backgrounds/" + f, source="new", category=m[1], family="grass", weight=1.0,
                          note=("real CC0 %s texture, photometric treatment%s" % (m[3], ", dappled" if m[4] else "")) if m[2] == "real" else "procedural lawn (make_grass_blades)" + (", dappled" if m[4] else "")))
    else:
        s = f[3:-4]
        c, w, n = nw[s]
        items.append(dict(path="backgrounds/" + f, source="new", category=c, family="grass" if c.startswith(("grass", "moss")) else "non_grass", weight=w, note="ambientCG %s mosaic: %s" % (s, n)))
for it in items:
    f = os.path.basename(it["path"])
    if it["source"] == "new" and f in REJ:
        it["path"] = "backgrounds/_rejected/" + f; it["weight"] = 0
        it["note"] = "REJECTED by audit (file moved to _rejected/): " + it["note"]
    elif f in OVR: it["weight"] = OVR[f]; it["note"] += " (audit: down-weighted)"
    if it["category"] == "gravel" and it["weight"] > 0: it["weight"] = round(it["weight"] * 0.6, 3); it["note"] += " (gravel x0.6: pool dominated by similar gravel)"
idx = dict(family_weights={"grass": 0.65, "non_grass": 0.35},
           path_roots={"v1": V1, "new": "assets_new/ (this folder)"},
           sampling="pick family by family_weights, then pick an item of that family with probability proportional to its weight (weight 0 = dropped)",
           backgrounds=items)
json.dump(idx, open(A + "/backgrounds_index.json", "w"), indent=1)
use = [i for i in items if i["weight"] > 0]
from collections import Counter
print(Counter(i["category"] for i in use)); print(Counter(i["family"] for i in use), len(items), len(use))
for fam in ("grass","non_grass"): print(fam, round(sum(i["weight"] for i in use if i["family"]==fam),2))
tw=sum(i["weight"] for i in use);print("sampling share by weight (family_weights 0.65/0.35 applied):", "within-family weights only")
