# Live test examples on the Training tab, verbatim

Relayed by the lead on 2026-10-20 (about 23:45), while the second YOLO11n session
(`runs/2026-10-20_232733_wide-960-10ep`, imgsz 960, batch 8, Apple GPU) was running:

```
you should show live test examples on http://127.0.0.1:8765/showcase.html#training as well
```

Revision, relayed a few minutes later while the first version (stratified pick of 16 val images) was being built:

```
can't you just sample randomly from the most recent validation set and show 16 of those?
```

The lead's brief turned the revision into: a uniform random sample of 16 val images (seed recorded), fixed across epochs
by default, plus a 'Resample 16' button that draws a new random 16 and predicts them with the current weights.
