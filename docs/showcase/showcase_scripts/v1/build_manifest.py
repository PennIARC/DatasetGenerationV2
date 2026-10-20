import json, os
here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(os.path.dirname(here))
R = json.load(open(os.path.join(here, "results.json")))
F = [
 ("backgrounds", "Background photos",
  "Real lawn, soil and gravel photos give the scene its texture and lighting, so the detector learns mines against realistic ground rather than flat colour.",
  "Picks one of 15 photos, scales it to cover 1920x1080 times a random zoom U(1, 1.5), then blits it at a random offset.",
  "DatasetGenerator/main.py: generate_one_image (step 1)",
  "Only 15 photos, so the ground variety is limited. High zoom upsamples the photo and looks soft. Several 'backgrounds' are screenshots of stock photos and some carry faint watermarks."),
 ("dirt", "Dirt specks",
  "Small brown squares scattered everywhere add clutter that looks vaguely like soil crumbs and stops the detector from keying on 'anything small and dark'.",
  "EnvironmentDebris._generate_dirt draws 50-200 (x density_factor) filled squares of 4-12 px with colour DIRT_COLOR_BASE (101,67,33) +- DIRT_VARIANCE 40.",
  "DatasetGenerator/objects.py: EnvironmentDebris._generate_dirt",
  "Perfect axis-aligned squares with hard edges, no blur or shading; obviously synthetic when zoomed. Note main.py always uses density_factor 1.0 (the options here are a parameter the code supports but the pipeline never varies)."),
 ("rocks", "Rock debris",
  "Photographed rocks pasted at random make clutter that is larger than the mines and sometimes similar in shape or colour, so the detector must tell them apart.",
  "_generate_rocks loads a rock photo, makes an alpha channel with Otsu thresholding (_process_image_otsu), scales it to 40-100 px wide, rotates 0-360 deg and places it anywhere (partly off-screen allowed).",
  "DatasetGenerator/objects.py: EnvironmentDebris._generate_rocks / _process_image_otsu",
  "No shadows or ambient-occlusion, so rocks look pasted on. The Otsu cut is a hard 1-bit edge, can cut away pale or shadowed rock parts, and every rock is re-read and re-thresholded from disk each time. Only 15 rock photos."),
 ("grass", "Grass clippings",
  "Cut-out pieces of real grass photos lie over the ground and partly hide things, imitating blades and leaves on top of the soil.",
  "_generate_grass_overlays samples 4 grass photos, Otsu-thresholds each, then takes randint(5, GRASS_CLIPPINGS_PER_IMAGE) random 100-300 px crops per photo, scaled to 40-80 px wide and placed at random.",
  "DatasetGenerator/objects.py: EnvironmentDebris._generate_grass_overlays",
  "Setting GRASS_CLIPPINGS_PER_IMAGE below 5 crashes (randint(5, n)). Crops are sharp-edged and flat-lit, so they do not match the lighting of the background. Only 5 grass photos."),
 ("sprites", "Mine sprites",
  "The mines are pre-rendered 3D images (a PFM-1-style scatterable mine) in many poses and shades, so one 3D model yields 50 distinct looks.",
  "SpriteGenerator renders 50 PNGs with random pitch/roll U(-20,20), yaw U(0,360) and dark-olive colour with a shared brightness shift +-0.3 and +-0.05 jitter. Mine.__init__ picks one, scales it by U(0.1, 0.4) and applies a second random 0-360 deg in-plane rotation.",
  "DatasetGenerator/objects.py: Mine.__init__ (sprites from SpriteGenerator/generate_sprites.py)",
  "Only 50 images, one mine model and one colour family. The lighting is baked into each sprite and does not match the background light; the 2D rotation at placement can turn the baked-in light direction the wrong way. Colour/pose values quoted from the generator settings; I did not re-render sprites."),
 ("count", "Mine count and placement",
  "Each image holds 0-8 mines at random places; empty images teach the detector what 'no mine' looks like.",
  "main.generate_one_image: 10% of images get 0 mines, otherwise randint(0, 8). Each mine gets up to 50 random positions; a position is rejected if its rectangle touches any earlier mine's rectangle inflated by 10 px. A mine that never fits is dropped.",
  "DatasetGenerator/main.py: generate_one_image (step 3); objects.py: Mine.set_position, get_yolo_bbox",
  "Positions are uniform over the frame (edges and corners included), so there is no spatial pattern like real minefields. Overlap is judged on the rotated sprite's rectangle, which is larger than the silhouette. Counting the 10% forced-empty rule plus randint returning 0, about 20% of images have no mine."),
 ("minedirt", "Mine surface dirt",
  "A few dark dots on top of the mine make its surface less clean and stop it looking like a perfect render.",
  "Mine._add_surface_dirt draws 5-20 filled circles (radius 1-3, colour (80,60,40) +- 30) at random points that lie on the sprite (alpha > 0 at the centre).",
  "DatasetGenerator/objects.py: Mine._add_surface_dirt",
  "Hard-edged dots in a single colour family, with no soil caking, scratches or shading. The sprite mask (used for boxes) is made before the dots are drawn, so dots that spill past the edge are not in the box."),
 ("overgrowth", "Overgrowth / occlusion",
  "A second layer of debris is drawn after the mines so grass, rocks and dirt can lie on top of them, making some mines partly hidden.",
  "main.generate_one_image makes a second EnvironmentDebris (dirt + rocks + grass) and draws it after the mines (step 4). The YOLO box was computed earlier from the unoccluded sprite mask.",
  "DatasetGenerator/main.py: generate_one_image (step 4)",
  "Boxes ignore occlusion: a mostly-hidden mine still gets its full box, so labels can point at areas with little visible mine. The cover is random, not physical (rock pixels simply overwrite the mine). In this demo the green and red boxes nearly coincide because the rock covers the middle, not the extremities."),
 ("shader", "Post-processing shader",
  "A final GPU pass degrades the clean render into something more camera-like: grain, colour fringing, darker corners and a little extra contrast.",
  "main.py runs the 1920x1080 canvas through shaders/post.frag with moderngl: noise (U(0.05,0.12) strength, random time seed), aberration 0.002, vignette 0.4, contrast 1.1. These demos re-run the same shader with the 3 constants exposed as uniforms so each effect can be shown alone.",
  "DatasetGenerator/shaders/post.frag; main.py: generate_one_image (step 5)",
  "Bug-like detail: the aberration step overwrites the red and blue channels after the noise is added, so grain only survives in the green channel (greenish speckle). Grain is also only added, never subtracted, so it brightens the image. The texture uses wrap-around sampling, so the left/right 4 px edges mix. Only the strengths of the noise vary per image; the other three effects are fixed. There is no blur, lens distortion, motion blur or compression."),
 ("export", "Labels and export",
  "Each image gets a text label file of boxes in YOLO format, then the dataset is resized to 640x640 for training.",
  "main.py writes 'class x_center y_center width height' normalised to 0-1. exportToYOLO.process_dataset resizes with cv2.resize to 640x640 (stretch, no letterbox) and copies the labels unchanged because normalised values are unaffected.",
  "DatasetGenerator/exportToYOLO.py: process_dataset; calcs.py: normalize_yolo",
  "The 16:9 to 1:1 stretch squeezes x by 1/3 and y by 0.59, so mines look tall and narrow and no longer match real camera geometry; a model trained on this sees a distorted shape unless test images are stretched the same way. Single class (0 = mine)."),
]
glossary = {
 "alpha": "A per-pixel transparency value: 0 is see-through, 255 is solid.",
 "Otsu thresholding": "An automatic way to pick a brightness cutoff that splits an image into 'object' and 'background'; v1 uses it to cut rocks and grass out of their white photo backdrops.",
 "cutout": "An image with its background removed (made transparent) so it can be pasted onto another picture.",
 "sprite": "A small pre-made image of an object (here a rendered mine) that is placed onto scenes.",
 "YOLO label": "A text line 'class x_center y_center width height' with positions as fractions of the image size (0 to 1).",
 "bounding box": "The smallest axis-aligned rectangle around an object; what the detector is trained to predict.",
 "normalised": "Expressed as a fraction of image width/height so it does not depend on resolution.",
 "shader": "A small program that runs on the GPU for every pixel; here it applies the camera-like effects.",
 "post-processing": "Effects applied to the finished picture after the scene is drawn.",
 "grain / noise": "Random per-pixel brightness speckle, like a camera sensor in low light.",
 "chromatic aberration": "Coloured fringes at edges because a lens focuses red and blue slightly differently; here red and blue are shifted sideways.",
 "vignette": "Darkening toward the corners of the image.",
 "contrast": "How far light and dark parts are pushed apart around mid-grey.",
 "occlusion": "One object hiding part of another.",
 "overgrowth": "In this project, a second debris layer drawn on top of the mines to hide parts of them.",
 "seed": "A number that fixes the random generator so a result can be reproduced; before/after pairs share a seed.",
 "nearest-neighbour zoom": "Enlarging by repeating each pixel as a block, so you see the real pixels.",
 "Lanczos": "A smooth resampling method used when resizing images.",
 "density_factor": "A multiplier for how many debris items are drawn.",
 "yaw / pitch / roll": "Rotation angles of the 3D model about its vertical, side and front axes when rendering a sprite.",
 "in-plane rotation": "Rotating a flat image around its centre, like turning a photo on a table.",
 "stretch (resize without letterbox)": "Resizing to a new aspect ratio by squashing, rather than adding padding bars.",
 "moderngl": "A Python library for running OpenGL (GPU) code, used to run the shader.",
}
feats = []
for fid, title, summ, how, code, notes in F:
    r = R[fid]
    feats.append(dict(id=fid, title=title, summary=summ, how=how, code=code, options=r["options"], before_after=r["before_after"], notes=notes))
m = {"pages": [dict(id="v1", tab="v1: original generator", title="v1: the original synthetic mine dataset generator",
  intro="v1 builds each training picture by layering real ground photos, scattered debris, pre-rendered mine sprites, more debris on top, and a final camera-like shader. It writes a YOLO label file for every image. Every picture on this page was made with v1's own code and a fixed random seed; where an effect is small, the crops are zoomed.",
  glossary=glossary, features=feats)]}
json.dump(m, open(os.path.join(OUT, "manifest_v1.json"), "w"), indent=1)
bad = []
for f in feats:
    for o in f["options"]: bad += [o["image"]] if not os.path.exists(os.path.join(OUT, o["image"])) else []
    for b in f["before_after"]:
        for k in ("before", "after"): bad += [b[k]] if not os.path.exists(os.path.join(OUT, b[k])) else []
print("missing:", bad, "features:", len(feats))
