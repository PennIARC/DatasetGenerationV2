# IARCdatasetGeneration (v2)
Generating a dataset to train a YOLOv11 nano model to detect bounding boxes around PFM-1 mines.

v2 makes the synthetic images harder to tell apart from real drone photos, so a detector trained on them has a
better chance of transferring. The output format is unchanged: 1920x1080 JPEGs + YOLO labels (`0 xc yc w h`,
normalised) in `output_dataset/`, then `exportToYOLO.py` stretches them to the 640x640 `finalDataset/` exactly as
v1 did. New: a sidecar JSON per image (`output_dataset/meta/train_XXXXX.json`) with every random choice.

## What changed from v1
| v1 | v2 (each behind a flag in `DatasetGenerator/controlPanel.py`) |
|---|---|
| 50 pre-rendered mine sprites, colour baked in | every mine rendered on the fly from `mine.stl` (`MESH_MINES`), new pose, colour, light, burial each time; 30% lie face down (`FLIP_PROB`) |
| near-constant olive-green hue | realistic palette: olive, dark green, khaki, brown, tan + bleaching, dirt tint (`COLOUR_PALETTE`) |
| hard, jaggy edges (nearest-neighbour scale + two rotations) | 4x supersampling, area downsampling, premultiplied alpha, one resample (`SOFT_EDGES`) |
| light fixed to the camera, rotated with the sprite | one sun per image drives mine shading and all shadows; 15% overcast images |
| no shadows | mesh shadows projected along the sun, penumbra, contact darkening; rocks and grass get shadows too (`SHADOWS`) |
| mines pasted on top | dust tinted by the local ground, darker contact band, soil grains, exposure matching (`SOIL_BLEND`) |
| always fully exposed | ~35% partially buried (up to 50% of the area) with a rough soil line and berm (`BURIAL`) |
| fixed shader (grain, aberration, vignette, contrast) | per-image exposure, gamma, white balance, saturation, contrast, noise, JPEG quality, vignette (`PHOTOMETRIC_JITTER`); lens/motion blur (`BLUR`) |
| 15 background photos | flips, 90-degree turns, zoom-crops, colour jitter (`BG_AUGMENT`) + `assets_new/` photos, rocks, grass, dirt (`NEW_ASSETS`) |
| box from the un-occluded sprite | box from what is actually visible after burial and overgrowth (`LABEL_VISIBLE_MASK`) |

Details, implementation notes, limitations and the Python API: [docs/CHANGES.md](docs/CHANGES.md).

## Running
```
pip install -r requirements.txt            # numpy, opencv, scipy, trimesh; pygame/moderngl only for visualizeData.py
cd DatasetGenerator
python3 main.py --num 50 --seed 0          # all v2 features -> output_dataset/
python3 main.py --num 50 --v1              # every v2 flag off (v1 behaviour)
python3 main.py --num 20 --only MESH_MINES,SHADOWS --out ablation_shadows
python3 main.py --num 2000 --start-index 0 --workers 8
python3 exportToYOLO.py                    # output_dataset -> finalDataset (640x640, stretched)
python3 ../scripts/visual_check.py         # contact sheets in docs/
```
`--set KEY=VALUE` overrides any `controlPanel.py` value (`--set SUN_ELEVATION=15,25`). Image `i` depends only on
`(seed, i)`, so batches and worker counts reproduce the same images. No window or GPU is needed.

Terms: *alpha* = per-pixel opacity of an overlay; *premultiplied alpha* = colour stored already multiplied by alpha,
which keeps resampled edges free of dark/bright fringes; *penumbra* = soft edge of a shadow; *fBm* (fractal
Brownian motion) = smooth random noise summed over several scales, used for natural-looking blotches; *PSF*
(point-spread function) = the blur a camera applies to a point of light.
