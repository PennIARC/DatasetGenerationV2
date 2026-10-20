"""v2 realism features as importable, deterministic functions (DatasetGenerator must be on sys.path).

    sun.sample_sun(rng, cfg)                         one sun / overcast sky per image
    mesh.sample_pose / sample_burial / render_mine   on-the-fly PFM-1 rasterizer (soft edges, burial clip, shadow)
    colour.sample_colour / colour_from_params        realistic palette
    shadows.mine_shadow / debris_shadow              cast shadows + contact AO
    soil.soil_blend / burial_overlay / dirt_grain    dust, contact band, grains, soil line, berm
    edges.resize_rotate                              hard (v1) vs soft (v2) resampling of 2D cut-outs
    camera.sample_camera_params / apply_camera       PSF + motion blur, photometric jitter or v1 shader, JPEG
    background.sample_background_params / make_background
    assets                                           asset folders (v1 Otsu cut-outs and RGBA PNGs)

Each sample_* function draws a fixed number of random numbers from the rng it is given and returns a plain dict;
the matching apply / render function is deterministic given that dict, so hand-picked values can be passed in.
The full scene entry point is scene.render_scene(seed, overrides).
"""
