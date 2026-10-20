"""Merge frag_*.json (written by part1-4.py) into docs/showcase/manifest_v2.json."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
order = [1, 2, 3, 12, 4, 5, 6, 7, 8, 13, 9, 11, 10]  # flip (11) sits before the whole-image comparison
feats = [json.load(open(f"{HERE}/frag_{i}.json")) for i in order]
glossary = {
 "alpha": "Per-pixel opacity: 0 is see-through, 1 is solid. Edge pixels get fractional alpha for soft edges.",
 "premultiplied alpha": "Colour stored already multiplied by alpha, so blurring or resizing never mixes in the undefined colour of transparent pixels (prevents halos).",
 "supersampling": "Drawing at several times the resolution and averaging down, which anti-aliases edges.",
 "penumbra": "The soft transition at the edge of a shadow; wider for low sun and long shadows.",
 "fBm noise": "Fractal Brownian motion: smooth random noise summed over several scales, used for natural-looking blotches of dust and ragged soil lines.",
 "soil blending": "Making the mine share the ground's colour and brightness: dust, a darker contact band, soil grains.",
 "sun azimuth": "Compass direction of the sun in the image: 0 deg = toward the right edge, 90 deg = toward the top. Shadows fall the opposite way.",
 "sun elevation": "Angle of the sun above the horizon: low = long shadows, high = short ones.",
 "overcast": "Cloudy, diffuse light: weak, very soft shadows.",
 "Lambert shading": "Surface brightness proportional to how directly it faces the light.",
 "ambient occlusion": "Extra darkening where a surface meets the ground and little sky is visible.",
 "white balance": "Colour cast of a camera: gains on the red and blue channels that make white look neutral.",
 "gamma": "Non-linear brightness curve; values above 1 darken midtones.",
 "exposure": "Overall brightness multiplier set by the camera.",
 "saturation": "How vivid colours are; 0 is grey.",
 "contrast": "Spread between light and dark parts around mid-grey.",
 "vignette": "Darkening toward the image corners.",
 "chromatic aberration": "Colour fringes at edges from a lens focusing colours differently.",
 "JPEG artifacts": "Blockiness and ringing from lossy compression; lower quality means stronger.",
 "lens blur / PSF": "Point-spread function: how a camera spreads a point of light; modelled as a Gaussian of sigma px.",
 "motion blur": "Smear along the direction of camera or object motion during the exposure.",
 "domain randomisation": "Deliberately varying nuisance factors (lighting, colour, noise, backgrounds) in training data so the model cannot rely on them and generalises to real images.",
 "pitch / roll / yaw": "Tilt forward-back, tilt side-to-side and rotation about the vertical axis (degrees).",
 "face down": "A mine lying on its back with its underside toward the camera.",
 "painter's algorithm": "Drawing triangles from far to near so nearer ones cover farther ones.",
 "Sutherland-Hodgman": "A method for cutting a polygon against a plane; used to slice the 3D mine at the soil plane.",
 "berm": "A small lip of disturbed soil along the line where a buried object meets the surface.",
 "albedo": "The base colour of a surface before lighting.",
 "HSV": "Hue (colour angle), saturation, value (brightness): a way to describe colour.",
 "YOLO label": "Text line 'class x_center y_center width height', all as fractions of the image size.",
 "ablation": "Switching features on or off one at a time to see what each contributes.",
 "seed": "Number that fixes the random generator so before / after pairs differ only by the feature.",
 "RGBA cut-out": "An image with a real transparency channel, used for rocks, leaves and dirt snippets.",
}
page = {"id": "v2", "tab": "v2: new realism features", "title": "v2: realism features of the new generator",
        "intro": "v2 keeps v1's pipeline (ground photo, clutter, mines, camera) but replaces the parts that made synthetic images easy to spot: mines are rendered from a 3D model with their own pose, colour, shadow, dust, burial and orientation; edges are soft; debris casts consistent shadows; the whole image gets randomised camera effects. Every picture here comes from the v2 code with a fixed seed; before / after pairs use the same seed and change only the named feature, and effects are shown zoomed. Where the effect is weak or imperfect, the notes say so.",
        "glossary": glossary, "features": feats}
out = os.path.join(ROOT, "manifest_v2.json")
json.dump({"pages": [page]}, open(out, "w"), indent=1)
miss = []
for f in feats:
    for o in f["options"]:
        if not os.path.exists(os.path.join(ROOT, o["image"])): miss.append(o["image"])
    for b in f["before_after"]:
        for k in ("before", "after"):
            if not os.path.exists(os.path.join(ROOT, b[k])): miss.append(b[k])
print("features", len(feats), "missing", miss)
