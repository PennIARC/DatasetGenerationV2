#!/usr/bin/env python3
"""Generate placeholder images and two test manifests in this directory."""
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
random.seed(1)


def make(rel, text, hue):
    p = HERE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    w, h = 640, 360
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            n = random.randint(-12, 12)
            px[x, y] = tuple(max(0, min(255, c + n)) for c in
                             ((x * 255 // w + hue) % 256, y * 255 // h, (hue * 2) % 256))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 140, 620, 220], fill=(0, 0, 0))
    d.text((40, 170), text, fill=(255, 255, 255))
    im.save(p, quality=85)


def opts(prefix, n, base):
    out = []
    for i in range(n):
        rel = "images/%s_%d.jpg" % (prefix, i)
        make(rel, "%s option %d" % (prefix, i), base + i * 40)
        out.append({"label": "%s %d" % (prefix, i), "params": "k=%d, random crop" % i, "image": "test_fixture/" + rel,
                    "caption": "caption %d" % i if i % 2 == 0 else ""})
    return out


def ba(prefix, hue):
    make("images/%s_off.jpg" % prefix, prefix + " OFF", hue)
    make("images/%s_on.jpg" % prefix, prefix + " ON", hue + 90)
    return [{"label": prefix.title(), "before": "test_fixture/images/%s_off.jpg" % prefix,
             "after": "test_fixture/images/%s_on.jpg" % prefix, "before_label": "off", "after_label": "on",
             "caption": "Look at the centre band."}]


def feature(fid, title, hue, flag=None, broken=False):
    f = {"id": fid, "title": title, "summary": "Plain summary of " + title + ".", "how": "Does a thing in a function.",
         "code": "DatasetGenerator/main.py: " + fid, "options": opts(fid, 4, hue), "before_after": ba(fid, hue),
         "notes": "Placeholder limitation for " + title + "."}
    if flag:
        f["flag"] = flag
    if broken:
        f["options"][1]["image"] = "test_fixture/images/does_not_exist.jpg"
        f["before_after"][0]["after"] = "test_fixture/images/also_missing.jpg"
    return f


m1 = {"pages": [{"id": "v1", "tab": "v1: original generator", "title": "Original generator",
                 "intro": "Test intro for v1. It has two sentences.",
                 "glossary": {"Alpha": "A test term.", "Beta": "Another test term."},
                 "features": [feature("backgrounds", "Background photos", 10),
                              feature("sprites", "Sprite placement", 60, broken=True),
                              feature("noise", "Dirt specks", 120)]}]}
m2 = {"pages": [{"id": "v2", "tab": "v2: new realism features", "title": "New realism features",
                 "intro": "Test intro for v2.", "glossary": {"Shadow": "A dark area."},
                 "features": [feature("shadows", "Shadows", 30, flag="enable_shadows"),
                              feature("blur", "Motion blur", 80, flag="enable_blur"),
                              feature("sparse", "Sparse feature", 140)]}]}
del m2["pages"][0]["features"][2]["options"], m2["pages"][0]["features"][2]["notes"], m2["pages"][0]["features"][2]["how"]
(HERE / "manifest_test_v1.json").write_text(json.dumps(m1, indent=1))
(HERE / "manifest_test_v2.json").write_text(json.dumps(m2, indent=1))

# ---- grid (review) manifest: 400 items reusing 8 thumb + 8 full files ----
def small(rel, text, hue, size):
    p = HERE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 255 // size + hue) % 256, (y * 255 // size) % 256, (hue * 3) % 256)
    ImageDraw.Draw(im).text((6, size // 2), text, fill=(255, 255, 255))
    im.save(p, quality=80)


for k in range(8):
    small("images/review/thumb_%d.jpg" % k, "T%d" % k, k * 30, 96)
    small("images/review/full_%d.jpg" % k, "FULL %d" % k, k * 30, 384)
bgs = ["grass_olive", "grass_dry", "dirt_red", "dirt_gray", "gravel_light", "sand_pale"]
items = []
for i in range(400):
    it = {"id": "b%03d" % (i + 1), "image": "test_fixture/images/review/full_%d.jpg" % (i % 8),
          "thumb": "test_fixture/images/review/thumb_%d.jpg" % (i % 8),
          "meta": {"seed": 1000 + i, "background": bgs[i % 6], "sun_el": round(10 + (i * 7) % 70 + 0.5, 1),
                   "burial": round((i % 10) / 10, 1), "face_down": i % 3 == 0,
                   "blades_on_mine": (i % 5), "visible_frac": round(1 - (i % 10) / 12, 2), "dust": round((i % 7) / 7, 2)},
          "tags": (["grass"] if i % 6 < 2 else ["bare"]) + (["low_sun"] if (10 + (i * 7) % 70) < 30 else [])}
    if i % 50 == 7:
        del it["thumb"]            # falls back to full image
    if i == 11:
        it["image"] = it["thumb"] = "test_fixture/images/review/nope.jpg"   # missing on purpose
    if i % 40 == 0:
        it["caption"] = "caption for " + it["id"]
    items.append(it)
mg = {"pages": [{"id": "burial_review", "tab": "Review: buried mines", "type": "grid", "title": "Buried mine review",
                 "intro": "Flag crops that look wrong.", "glossary": {"Burial": "fraction of the mine covered"},
                 "columns": ["id", "seed", "background", "sun_el", "burial", "face_down", "blades_on_mine", "notes"],
                 "items": items}]}
(HERE / "manifest_test_review.json").write_text(json.dumps(mg))
print("fixture written")
