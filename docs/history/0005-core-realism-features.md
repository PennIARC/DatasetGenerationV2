# 0005: core realism features of generator v2

Date: 2026-10-20 (04:07Z-05:50Z = 00:07-01:50 EDT)

## Context

See ADR 0001 for why v2 exists. The v1 generator pasted 50 pre-rendered sprites with hard edges, no shadows, no burial and a narrow colour range. The user wanted each of these attacked, and added requirements during the build. A generator subagent (Opus) implemented the features, each behind its own flag in `DatasetGenerator/controlPanel.py` (`V2_FLAGS`); the per-feature reference is `docs/CHANGES.md`.

## Decision

Each item lists the user's input that shaped it.

- On-the-fly mine rendering (`MESH_MINES`): each mine is rasterised from `mine.stl` per instance (software painter's algorithm, 4x supersampling, one area downsample), so there is no sprite pool. User: "let's also use more than 50 samples of the mine. we should also skew towards more of them being where the mine is laying flat since it's unlikely for the mine to be vertical". Pose: yaw uniform, pitch and roll N(0, 5 deg) with a small tail and a 35 deg cap (median 3.6, p90 9.5, p99 25.6 deg).
- Face-down mines: "we should flip mines and have angles of them facing down as well as up, not just up". `FLIP_PROB = 0.30`; the mesh is turned 180 degrees about its long axis and settled onto the stable face; recorded as `face_down` in the sidecar. The detector's kernel bank also got `num_sides` and `num_tilts` options (increase tilts from 2 to 3-4 was requested; "we can test this later").
- Pose figures: the user asked for a 3D point-on-sphere render of the pose distribution and a side-by-side of mine renders at each angle, to check nothing is rotated or offset; then asked what the 3 columns of the figure were, and told the assistant to label things like that in future. Figures live in the other repo (`kernelBashing/outputs`).
- Sun and shadows (`SHADOWS`): one sun per image, elevation uniform 15-70 deg for about 85% of images plus about 15% overcast (weak, very soft shadows), azimuth uniform, strength 0.25-0.65. The user picked these from options ("Wide 15-70 deg + 15% overcast", "Varied 0.25-0.65"). Mine shadows are projected from the 3D mesh onto the ground plane; rocks, grass, dirt and blades get 2D swept shadows with the same sun, so that "has a shadow" does not become a shortcut for "is a mine".
- Soft edges and blur (`SOFT_EDGES`, `BLUR`): supersampled area resampling, premultiplied alpha (no halos), Gaussian PSF sigma 0-1.5 px, optional motion blur.
- Soil blending (`SOIL_BLEND`): exposure harmonisation with the local ground, a dust layer tinted by the ground, a contact band and soil grains instead of v1's hard dots. Dust strength was later set by the user (ADR 0006).
- Partial burial (`BURIAL`): probability 0.35 per mine, hidden fraction capped at 50% so every mine keeps a box (user answer "Bury at most ~50%"), implemented by clipping the 3D model against a tilted soil plane. Refined over four rounds (ADRs 0006-0009).
- Colour and camera (`COLOUR_PALETTE`, `PHOTOMETRIC_JITTER`, `BG_AUGMENT`): realistic palette only (user answer), per-instance sun-bleach and dirt tint, per-image exposure, gamma, white balance, saturation, contrast, noise, vignette, aberration and JPEG quality, background flips/rotations/zoom/jitter.
- Labels (`LABEL_VISIBLE_MASK`): the box is the bounding box of mine pixels still visible after soil and blades; a mine with fewer than `LABEL_MIN_VISIBLE_PX = 1` visible pixels gets no box. The policy for very hidden mines (for example a minimum visible fraction of 30%) was raised to the user and left open.
- Tooling: sidecar JSON per image, `render_scene(seed, overrides)` API, per-subsystem seeded random streams so toggling one flag leaves the rest of the scene identical.

## Consequences

- Speed: 0.93 s/image single process (1.9x v1 at 0.49 s); about 0.32 s/image with 4 workers; later burial cues bring it to about 1.02 s.
- Limitations recorded in `docs/CHANGES.md`: flat triangle shading, no self-shadowing between body and wings, no plastic texture, the burial plane is flat, dust is a 2D overlay, backgrounds carry their own baked shadows.
- Not validated against real photos or by training the detector on v2 data yet; the assistant's honest notes were that bleached dark-green mines look minty, face-down undersides are flat-coloured and 15 deg shadows are faint.
- First commit of the generator is a snapshot (earlier working states were never saved), so it already contains the first burial fix and the asset audit filter.

## Feedback that triggered this

- [0001 dataset realism targets](feedback/0001-dataset-realism-targets.md)
- [0002 location, burial and palette answers](feedback/0002-location-burial-palette-answers.md)
- [0003 more mine samples, flat skew](feedback/0003-more-mine-samples-flat-skew.md)
- [0004 pose sphere render request](feedback/0004-pose-sphere-render-request.md)
- [0005 grill request on new variations](feedback/0005-grill-new-variations-request.md)
- [0006 sun and shadow answers](feedback/0006-sun-and-shadow-answers.md)
- [0010 pose columns and flip](feedback/0010-pose-columns-and-flip.md)
- [0011 label diagrams, more tilts](feedback/0011-label-diagrams-more-tilts.md)
- [0014 soft shadows under rocks](feedback/0014-soft-shadows-under-rocks.md)

## Commits

- `e215f70` 2026-10-20 00:52:00 -0400 feat: add generator v2 with on-the-fly mines, sun shadows, burial and soil (backfilled estimate; a snapshot of the code as of the backfill, including `docs/CHANGES.md`, visual-check scripts and the contact sheets)
- `654fcf2` 2026-10-20 01:52:00 -0400 test: add burial and asset audit regression tests
