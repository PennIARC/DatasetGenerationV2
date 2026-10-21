# Wide ("zoomed out") second dataset request, verbatim

Relayed by the lead on 2026-10-20, after the first YOLO training on the zoomed 640x640 dataset (`output_dataset/v2_3000`):

```
the model seemed to actually learn this dataset quite easily. it might be worth it to go back to the 'zoomed out' original version of the dataset (so just undo the mine/rock/grass zooming in) and re-build that dataset. don't delete the existing current one, just create a second one. afterwards, train another yolo model on it for 10 epochs
```

Decisions from the follow-up interview, confirmed by the user (as relayed by the lead):

1. Image size: "let's train on a 960x960 random crop of the fullsize 1920x1080 render".
2. The crop is BAKED at generation (OUTPUT_CROP = (960, 960), a uniformly placed window containing all mines, like the
   existing 640 pipeline); the dataset is stored as 960x960 JPEG and trained later at imgsz 960.
3. The ORIGINAL plan: mine scale 0.1-0.4 in 5 LOG bins (600 images each), mines per image 0-8 (600 empty, 300 each
   for 1-8), SCENE_ZOOM_COUPLING off (no rock / blade / debris / background zoom), same 3000 images, 2700 / 300
   train / val balanced, all other strata as in the current plan (sun, light, burial, background family / file incl.
   the grass1.png / grass2.png exclusion, PSF bins, sampled JPEG q70-95, soft grains random).
