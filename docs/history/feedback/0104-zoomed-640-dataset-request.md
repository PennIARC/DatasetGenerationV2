# Zoomed 640x640 dataset request, verbatim

Relayed by the lead on 2026-10-20, after the user looked at the previous 3000-image plan / render:

```
we should increase mine size and use 640x640. right now mines are extremely small and often barely visible in the generated dataset. we should delete the existing dataset and re-generate with mines at scales between 0.25 and 0.4. note that you will likely have to scale other features like rocks, blades of grass, etc. to match the new zoomed in look.
```

Decisions from the follow-up interview, all confirmed by the user (as relayed by the lead):

1. 640x640 via NATIVE CROP: render the scene at 1920x1080 as now, then cut a 640x640 window (no resize, no
   resampling blur) that contains all the mines (placed so they fit in the window with margin; window position
   random but otherwise unbiased); labels converted to the crop's normalized YOLO coordinates.
2. Mine scale sampled evenly in 4 LINEAR bins across 0.25-0.40 (750 images each, uniform within the bucket) instead
   of 5 log bins over 0.1-0.4.
3. Rocks, grass blades, leaf clumps / grass debris, dirt, tools / debris and other pixel-sized objects scale COUPLED
   to the mine scale: per image multiply their size by mine_scale / 0.2 (0.2 = the old median mine scale), like
   moving the camera closer; a new generator feature flag, default off.
4. Mines per image 0-4 (600 empty = 20 %, 600 each for 1-4) instead of 0-8.

Everything else in the plan unchanged.
