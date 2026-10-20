# =====================================================================================================
# controlPanel.py -- every knob of the generator lives here (v1 settings first, v2 realism after).
#
# v1 parity: set every flag in "V2 FEATURE FLAGS" to False (or run main.py --v1) and the generator
# behaves like v1: pre-rendered sprites from assets/mines, nearest-neighbour scale + rotate, hard dirt
# dots, no shadows, v1 post-process (noise, chromatic aberration, vignette, contrast). See
# docs/CHANGES.md for what each v2 feature does.
#
# Angles are in degrees. Colours are RGB 0-255 unless stated otherwise. "U(a, b)" = uniform in [a, b].
# Ranges are written as (min, max) tuples and sampled uniformly unless stated otherwise.
# =====================================================================================================

# --- GENERATION SETTINGS ---
NUM_IMAGES_TO_GENERATE = 2000
START_INDEX = 0  # Useful if running batches (CLI: --start-index)
SEED = 0         # Base seed; image i uses seed (SEED, i), so any batch split reproduces the same images

# --- DISPLAY / OUTPUT ---
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
OUTPUT_PATH = "output_dataset"
IMAGES_DIR = "images"
LABELS_DIR = "labels"
META_DIR = "meta"            # per-image sidecar JSON (v2); written when WRITE_SIDECAR_JSON
WRITE_SIDECAR_JSON = True

# --- SCENARIO SETTINGS ---
MIN_MINES = 0
MAX_MINES = 8
ZERO_MINE_PROB = 0.10        # v1: 10% of images have no mines at all
MINE_PLACEMENT_ATTEMPTS = 50 # v1: rejection-sampling attempts per mine
MINE_PLACEMENT_MARGIN = 10   # v1: rect.inflate(10, 10) used in the overlap test

# --- SCALE ---
# How big should the mine be relative to 1080p?
# Real PFM-1 is ~12cm. At 5m altitude, it might be 100-200 pixels wide depending on FOV.
MINE_SCALE_MIN = 0.1
MINE_SCALE_MAX = 0.4
# v1 sprites were rendered with an orthographic camera of half-width 0.6 mesh-units into 512 px, mesh longest
# side = 1 unit -> 512 / 1.2 = 426.7 px per unit at scale 1. The on-the-fly renderer uses the same factor so
# MINE_SCALE_* mean the same thing (mine length ~43-171 px at 1080p).
MINE_PX_PER_UNIT = 512 / 1.2

# --- COLORS ---
# Dirt particle colors
DIRT_COLOR_BASE = (101, 67, 33) # Dark Brown
DIRT_VARIANCE = 40
DIRT_RECTS_PER_LAYER = (50, 200)   # v1 ground "dirt" squares per debris layer
DIRT_RECT_SIZE = (4, 12)

# --- GRASS DEBRIS ---
GRASS_IMAGES_TO_SAMPLE = 4      # How many distinct grass images to use per scene
GRASS_CLIPPINGS_PER_IMAGE = 16   # How many small crops to take from each image
GRASS_CROP_SIZE_MIN = 100       # Size of the crop window on the source image
GRASS_CROP_SIZE_MAX = 300
GRASS_OUTPUT_SIZE_MIN = 40      # Final width on screen
GRASS_OUTPUT_SIZE_MAX = 80

# --- ROCK DEBRIS ---
ROCKS_TO_SPAWN_MIN = 5
ROCKS_TO_SPAWN_MAX = 20
ROCK_OUTPUT_SIZE_MIN = 40      # Larger than grass
ROCK_OUTPUT_SIZE_MAX = 100

# --- ASSET AUDIT (ASSET_AUDIT_FILTER) ---
# docs/asset_audit/exclude.json (from the 10-auditor asset audit): "hard_exclude" (stock-photo watermarks / unusable)
# is never sampled; "review" items are down-weighted by ASSET_REVIEW_WEIGHT. Matched by path relative to the repo.
# Applies to backgrounds (folder and index sampling), rocks, grass snippets, leaf clumps and dirt. With the flag off
# (v1 mode) every file is used exactly as in v1, including the watermarked ones.
ASSET_AUDIT_PATH = "../docs/asset_audit/exclude.json"
ASSET_REVIEW_WEIGHT = 0.4

# --- ASSET SOURCES: [(folder, weight), ...], folders relative to DatasetGenerator ---
# A source folder is picked by weight (among folders that exist and are non-empty), then a file uniformly in it.
# The FIRST entry is the v1 asset set; with NEW_ASSETS off only that one is used (no dirt snippets).
# Rocks / grass / dirt accept v1-style photos on white (Otsu cut-out) and RGBA PNGs with real alpha.
BACKGROUND_SOURCES = [("assets/backgrounds", 1.0), ("../assets_new/backgrounds", 1.0)]
ROCK_SOURCES = [("assets/rocks", 1.0), ("../assets_new/rocks", 1.0)]
GRASS_SOURCES = [("assets/grassDebris", 1.0)]   # v1 grass clippings only; new leaf clumps: LEAF_* below
LEAF_SOURCES = [("../assets_new/grassDebris", 1.0)]  # RGBA leaf-litter clumps (LEAF_CLUMPS_NEW); weight per folder
DIRT_SOURCES = [("../assets_new/dirt", 1.0)]     # no v1 equivalent (v1 drew coloured squares)
# Background index (assets_new/backgrounds_index.json: 15 v1 + 104 new, each with family grass | non_grass, category,
# weight; weight 0 = never). BG_USE_INDEX (with NEW_ASSETS): pick the family by BG_FAMILY_WEIGHTS (None = the
# file's family_weights = grass 0.65 / non_grass 0.35, user wants 60-70% grass), then an item by its weight.
# BG_USE_INDEX = False -> BACKGROUND_SOURCES (uniform per folder).
BG_USE_INDEX = True
BG_INDEX_PATH = "../assets_new/backgrounds_index.json"
BG_V1_DIR = "assets/backgrounds"                 # where index entries with source "v1" live
BG_FAMILY_WEIGHTS = None                         # e.g. {"grass": 0.65, "non_grass": 0.35}
# Generator-side weight overrides by file name (assets_new is not edited). These three show 8x8 JPEG blocking in
# their dark (multiplied) patches: blockiness ratio 1.37 / 1.90 / 1.22 vs a median of 1.06 over all 119 backgrounds.
BG_WEIGHT_OVERRIDES = {"bg_real_07_Grass007_grass_patchy.jpg": 0.25, "bg_real_08_Grass008_grass_olive.jpg": 0.25,
                       "bg_real_06_Grass007_grass_dry.jpg": 0.5}
DIRT_SNIPPETS_PER_LAYER = (2, 10)
DIRT_SNIPPET_SIZE = (15, 60)                     # on-screen width, px at 1080p
MINE_SPRITE_DIR = "assets/mines"   # v1 pre-rendered sprites (used only when MESH_MINES is False)
MINE_STL_PATH = "assets/mine.stl"  # copy of SpriteGenerator/mine.stl

# --- SHADERS / v1 POST-PROCESS ---
ENABLE_POST_PROCESSING = True
V1_NOISE_STRENGTH = (0.05, 0.12)   # v1 shader: uniform positive grain, only survives in the G channel
V1_ABERRATION = 0.002              # v1 shader: R/B shift in uv units (= 3.84 px at 1920)
V1_VIGNETTE = 0.4                  # v1 shader: rgb *= 1 - dist(uv, centre) * 0.4
V1_CONTRAST = 1.1                  # v1 shader: (rgb - 0.5) * 1.1 + 0.5
V1_BG_ZOOM = (1.0, 1.5)            # v1 background zoom on top of "scale to cover"
JPEG_QUALITY = 85                  # v1 (pygame.image.save) quality; used when PHOTOMETRIC_JITTER is off

# =====================================================================================================
# V2 FEATURE FLAGS  (all False == v1 behaviour)
# =====================================================================================================
ASSET_AUDIT_FILTER = True  # skip assets flagged by the asset audit (docs/asset_audit/exclude.json; v1 mode keeps all)
NEW_ASSETS = True          # also sample from assets_new/ (more backgrounds, RGBA rocks / grass, dirt snippets)
LEAF_CLUMPS_NEW = True     # new RGBA leaf-litter clumps (assets_new/grassDebris), own count / size (needs NEW_ASSETS)
GRASS_BLADES = True        # thin grass blades / tufts / wisps under AND over the mines (needs NEW_ASSETS)
MESH_MINES = True          # render every mine on the fly from mine.stl (else: v1 sprite set)
SOFT_EDGES = True          # supersampled AA, area downsampling, premultiplied alpha, single resample
SHADOWS = True             # cast shadows (mesh projected along the sun) + contact AO; rock/grass shadows too
SOIL_BLEND = True          # dust layer, contact band, grains, local exposure harmonisation, soft ground dirt
BURIAL = True              # partial burial (3D clip by a tilted ground plane) + soil line + berm
COLOUR_PALETTE = True      # per-instance realistic palette (else v1 olive formula)
PHOTOMETRIC_JITTER = True  # per-image exposure / gamma / WB / saturation / contrast / noise / JPEG / vignette
BLUR = True                # camera PSF (Gaussian defocus) + optional motion blur on the whole composite
BG_AUGMENT = True          # background flips / 90-degree rotations / zoom-crops / colour jitter
LABEL_VISIBLE_MASK = True  # boxes from the visible mask after overgrowth occlusion (v1: un-occluded mask)

# Features that need the 3D mesh (BURIAL, COLOUR_PALETTE, mesh-accurate mine SHADOWS) are skipped / approximated
# when MESH_MINES is False: sprite mines then get the 2D-offset shadow used for rocks.

# =====================================================================================================
# V2 PARAMETERS
# =====================================================================================================

# --- MINE POSE (on-the-fly renderer) ---
# yaw ~ U(0, 360). pitch and roll are independent, zero-mean and concentrated near flat:
#   with prob 1 - TILT_TAIL_PROB: N(0, TILT_SIGMA) (re-drawn if |x| > TILT_CAP)
#   with prob TILT_TAIL_PROB:     random sign * U(TILT_TAIL_RANGE)   (mine resting on a rock / tilted ground)
# Resulting |pitch| (and |roll|) percentiles (2e5 draws): median 3.6, p90 9.5, p99 25.6, max 30 deg.
FLIP_PROB = 0.30               # probability that a mine lies FACE DOWN (underside up; user decision). One-line setting.
                               # Flip = 180 deg about the mine's long horizontal axis, applied before the tilts below,
                               # so pitch / roll are relative to lying flat on its back. Sidecar: face_down.
TILT_SIGMA = 5.0
TILT_TAIL_PROB = 0.05
TILT_TAIL_RANGE = (8.0, 30.0)
TILT_CAP = 35.0

# --- SUN (one per image; drives mine shading, mine shadows and rock / grass shadows) ---
SUN_AZIMUTH = (0.0, 360.0)     # degrees, 0 = sun towards image +x (right), 90 = towards image top
SUN_ELEVATION = (15.0, 70.0)   # degrees above the horizon (user decision)
OVERCAST_PROB = 0.15           # user decision: ~15% overcast images (diffuse light) ...
OVERCAST_SHADOW_STRENGTH = (0.03, 0.15)  # ... with weak ...
OVERCAST_PENUMBRA_SCALE = 6.0  # ... and very soft shadows (penumbra sigma multiplied by this)

# --- MINE SHADING (Lambert + ambient + Blinn-Phong specular; camera looks straight down) ---
# Lighting is tied to the per-image SHADOW_STRENGTH s so mine and ground agree: a face's gain is
#   (1 - s) + s * min(max(n . L, 0) / sin(elevation), SHADE_MAX_GAIN)
# i.e. a horizontal face in sun = 1 (like the photographed ground), a face turned away from the sun = 1 - s (exactly
# as dark as the cast shadow on the ground), faces tilted towards a low sun get brighter (capped).
SHADE_MAX_GAIN = 2.0
SPECULAR = (0.0, 0.12)         # specular strength (plastic sheen)
SPECULAR_EXP = (8.0, 30.0)     # Blinn-Phong exponent
SUPERSAMPLE = 4                # SOFT_EDGES: render at 4x and area-average down

# --- COLOUR PALETTE (COLOUR_PALETTE) ---
# Realistic PFM-1 / military-plastic families only. HSV with H in degrees [0, 360), S and V in [0, 1].
# A family is chosen by weight, then H, S, V are drawn uniformly inside its ranges. Families overlap so the
# hue axis is covered continuously from red-brown (~20) to blue-green (~160) and V spans 0.15-0.78; together
# with bleaching, dirt tint, per-instance brightness and the scene lighting no single hue/brightness identifies
# a mine. v1 base colour for reference: RGB (0.149, 0.384, 0.275) = H 153, S 0.61, V 0.38.
PALETTE = {
    #  name          weight  H range        S range       V range
    "olive_drab":  (0.28, (55.0, 85.0),   (0.30, 0.60), (0.22, 0.45)),
    "dark_green":  (0.22, (85.0, 160.0),  (0.30, 0.65), (0.15, 0.40)),
    "khaki":       (0.15, (40.0, 58.0),   (0.22, 0.45), (0.42, 0.70)),
    "brown":       (0.20, (18.0, 38.0),   (0.35, 0.65), (0.18, 0.45)),
    "tan":         (0.15, (26.0, 45.0),   (0.18, 0.40), (0.50, 0.78)),
}
BLEACH_PROB = 0.35             # sun-bleaching: S *= 1 - 0.6 a, V += 0.3 a (1 - V), a ~ U(BLEACH_AMOUNT)
BLEACH_AMOUNT = (0.0, 0.6)
DIRT_TINT_PROB = 0.4           # mix albedo towards DIRT_TINT_RGB by U(DIRT_TINT_AMOUNT)
DIRT_TINT_AMOUNT = (0.0, 0.3)
DIRT_TINT_RGB = (0.42, 0.33, 0.22)
BRIGHTNESS_JITTER = (0.85, 1.15)  # per-instance multiplier on V
# v1 colour formula (COLOUR_PALETTE off): base + one common shift U(-0.3, 0.3) + per-channel U(-0.05, 0.05)
V1_BASE_COLOUR = (0.1490, 0.3843, 0.2745)
V1_COMMON_SHIFT = 0.3
V1_CHANNEL_JITTER = 0.05

# --- SHADOWS (SHADOWS) ---
SHADOW_STRENGTH = (0.25, 0.65)      # direct-sun images (user decision), per image: ground *= 1 - strength * coverage (shared by mines/rocks/grass)
SHADOW_COOL_TINT = (0.0, 0.15)      # per image: shadows lose more red than blue (sky-lit shadows are bluish)
PENUMBRA_BASE_PX = 0.6              # Gaussian sigma of the shadow edge at 1080p ...
PENUMBRA_PER_LENGTH = 0.06          # ... + this * shadow length (px); low sun -> longer, softer shadows
CONTACT_AO_STRENGTH = (0.1, 0.3)    # extra darkening right around the mine footprint (ambient occlusion)
CONTACT_AO_SIGMA = (1.5, 3.5)       # px
MINE_CONTACT_SHADOW = True          # soft contact shadow hugging the mine footprint on ALL sides, incl. the sun side
MINE_CONTACT_STRENGTH = (0.2, 0.4)  #   (user review b008 / b022: "looks like it's floating"); darkening at the edge ...
MINE_CONTACT_WIDTH_FRAC = (0.03, 0.06) # ... x clip(shadow strength / 0.45, 0.35, 1.3); Gaussian sigma / mine length
MINE_HEIGHT_FRAC = 21.2 / 120.0     # PFM-1 thickness / length (sprite-mode 2D shadows)
ROCK_HEIGHT_FRAC = (0.1, 0.35)      # rock height / on-screen width for the swept cast shadow (user: was 0.25-0.5)
ROCK_SMALL_HEIGHT_SCALE = 0.5       # smallest rocks use this share of the drawn height (scales up to 1 for largest)
ROCK_GRAVEL_HEIGHT_SCALE = 0.5      # "Gravel" snippets (flat granular lumps) are lower still
ROCK_SHADOW_MAX_LENGTH_FRAC = 0.8   # cap: cast shadow at most this x rock width long (no smears at low sun)
ROCK_PENUMBRA_PER_LENGTH = 0.15     # rocks: penumbra sigma = PENUMBRA_BASE_PX + this x shadow length
CLOD_HEIGHT_FRAC = (0.05, 0.15)     # dirt clods: small raised lumps
GRASS_HEIGHT_FRAC = (0.02, 0.08)    # grass clippings lie nearly flat -> short shadows
GRASS_SHADOW_SCALE = 0.6            # grass shadows are fainter (thin, translucent blades)
ROCK_ALIGN_LIGHT = True             # rotate each rock photo so its baked-in bright side faces this image's sun ...
ROCK_ALIGN_JITTER = 30.0            # ... +- this many degrees
# Seating rocks on the ground (user request)
ROCK_CAST_SHADOW = True             # the sun-direction swept shadow of rocks / clods / leaves (False = contact only)
ROCK_CONTACT_SHADOW = True          # soft contact shadow / AO under rocks, dirt clods, leaf clumps (needs SHADOWS)
CONTACT_SHADOW_KINDS = ("rock", "dirt_clod", "leaf")
ROCK_CONTACT_STRENGTH = (0.2, 0.5)  # multiplicative darkening at the centre ...
ROCK_CONTACT_SUN_REF = 0.45         # ... times clip(image shadow strength / this, ROCK_CONTACT_MIN_SCALE, 1.3)
ROCK_CONTACT_MIN_SCALE = 0.35       #     (overcast images keep a weaker but present contact shadow)
ROCK_CONTACT_WIDTH_FRAC = (0.04, 0.12)  # Gaussian width as a fraction of the object width
ROCK_CONTACT_OFFSET_FRAC = 0.03     # shifted this x width away from the sun
ROCK_RIM_BLEND = True               # rim tint towards the local ground + darker rim line on the side away from the sun
RIM_BLEND_KINDS = ("rock", "dirt_clod", "leaf")
ROCK_GROUND_TINT = (0.1, 0.35)      # colour mix towards the local ground within the rim band
ROCK_RIM_DARKEN = (0.15, 0.35)      # away-from-sun rim darkening (scaled by shadow strength / ROCK_CONTACT_SUN_REF)
ROCK_RIM_BAND_PX = 1.5
DIRT_PATCH_ADAPT = 0.5              # dirt patches / dust: colour pulled towards the local ground (like grass blades)

# --- SOIL BLENDING (SOIL_BLEND) ---
DUST_STRENGTH = (0.25, 0.30, 0.50)  # per-mine max dust opacity ~ triangular(low, mode, high), mean 0.35 (user);
                                    # modulated by fBm noise. A 2-tuple = uniform; override with a scalar to fix it.
DUST_NOISE_SCALE = (0.15, 0.5)      # fBm feature size as a fraction of the mine length
CONTACT_BAND_PX = (1.5, 4.0)        # width of the darker / dustier band where the mine meets the ground
CONTACT_BAND_DARKEN = (0.1, 0.3)
CONTACT_BAND_DUST = (0.2, 0.5)
GRAIN_DENSITY = (0.0, 0.05)         # fraction of mine pixels covered by soil grains (replaces v1 dots)
GRAIN_OPACITY = (0.5, 0.9)
# Soft grains (MINE_SOFT_GRAINS, needs SOIL_BLEND): a second, blurred grain layer (user: "add a second augmentation
# similar to 'Soil grains and contact band' where you add randomized grains except you should blur/smooth these out
# more"). Soft, low-contrast, larger speckle in the local soil colour, denser in the contact zone near the outline.
# Own random sub-stream (mine sub-stream 12): no other draw changes, flag off = identical images.
MINE_SOFT_GRAINS = True
SOFT_GRAIN_PROB = 0.75              # share of mines that get the layer (per mine)
SOFT_GRAIN_DENSITY = (0.06, 0.22)   # fraction of the mine's pixels inside speckles (before blurring)
SOFT_GRAIN_SIZE_FRAC = (0.015, 0.04)    # speckle feature size / mine length (~2-6 px at 150 px; grains: 1.5 px)
SOFT_GRAIN_BLUR_PX = (2.5, 6.0)     # Gaussian sigma of speckle alpha and colour (user: "blur the soft grains more";
                                    # existing grains: unblurred, 0.03 ramp)
SOFT_GRAIN_STRENGTH = (0.2, 0.45)   # peak opacity of a speckle (low contrast; grains: 0.5-0.9)
SOFT_GRAIN_TONE = (0.95, 1.05)      # small brightness jitter of the sampled colour (+ 3% per speckle)
SOFT_GRAIN_RING_FRAC = (0.03, 0.15) # speckle colours = background pixels sampled in this ring around the mine
                                    # (x mine length; user: "same/similar color (maybe sample them) from the background")
SOFT_GRAIN_EDGE_BOOST = (0.5, 2.0)  # density x (1 + this) inside the contact zone (SOFT_GRAIN_EDGE_FRAC x length)
SOFT_GRAIN_EDGE_FRAC = 0.08
HARMONIZE_LOCAL = 0.5               # mine *= (local bg luminance / image luminance) ** this
HARMONIZE_GLOBAL = 0.5              # mine *= (image luminance / HARMONIZE_REF_LUMA) ** this
HARMONIZE_REF_LUMA = 0.40
HARMONIZE_CLIP = (0.6, 1.6)
LOCAL_BG_SIGMA_FRAC = 0.25          # blur of the local background (fraction of mine length) used as dust colour

# --- BURIAL (BURIAL; needs MESH_MINES) ---
BURIAL_PROB = 0.35
BURIAL_FRACTION = (0.05, 0.5)       # fraction of the mine's top-down visible area that ends up under soil
BURIAL_CLIP_SHARE = 0.85            # the 3D clip hides this share of BURIAL_FRACTION; soil line / ridge / clods the rest
BURIAL_MAX_FRACTION = 0.5           # hard cap (user decision: every mine stays reasonably visible, always boxed)
BURIAL_TILT = (0.0, 25.0)           # ground-plane tilt
SOIL_EDGE_NOISE = (0.01, 0.035)     # soil-line roughness, mesh units (mine length = 1)
BERM_WIDTH_PX = (2.0, 6.0)          # soil lip / berm along the buried edge
BERM_OPACITY = (0.4, 0.85)
BERM_DARKEN = (0.75, 0.95)          # (unused since round 4: the soil over the mine is the ground pixels themselves)
BURIAL_IRREGULAR_LINE = True        # organic soil line instead of a straight clip edge: the soil surface is the
BURIAL_LINE_WANDER = (0.025, 0.055)  # nominal plane +- this (mesh units, mine length = 1; x sqrt(fraction / 0.4))
BURIAL_WAVES = (4, 7)               # the wander is a sum of this many sin / cos waves (random direction, phase) ...
BURIAL_WAVE_LENGTH_FRAC = (0.2, 0.8)   # ... with wavelengths log-uniform in this range x mine length ...
BURIAL_WAVE_NOISE = 0.15            # ... plus this share of fBm noise on top
BURIAL_RAGGED_EDGE = False          # soil edge made of crumbs (dithered grainy alpha + spilled crumbs) and the cover
BURIAL_CRUMB_REACH = 0.06           # copies the ground pixels; crumbs reach this x mine length onto the exposed part
BURIAL_MIN_FRAGMENT_FRAC = 0.06     # after clipping: visible islands smaller than this x full area are dropped ...
BURIAL_OPEN_PX = 1                  # ... and structures thinner than ~2 r px removed (morphological opening, radius
BURIAL_OPEN_FRAC = 0.025            #     r = max(BURIAL_OPEN_PX, BURIAL_OPEN_FRAC x mine length); ~4 px at 150 px)
# Soil-displacement cues (user feedback: a cut-away mine looks edited). Strength scales with
# s = clip(burial fraction / 0.4, 0.25, 1.25): subtle for small burials, clear at 40-50%.
BURIAL_BERM = True                  # raised, clumpy ridge along the soil line, sun-shaded, casting a short shadow
BERM_RIDGE_WIDTH_FRAC = (0.03, 0.08)    # ridge width / mine length
BERM_RIDGE_HEIGHT_FRAC = (0.02, 0.05)   # ridge height / mine length (cast-shadow length)
BERM_RIDGE_OPACITY = (0.3, 0.6)
BERM_RIDGE_SHADE = 0.25             # sun shading contrast of the ridge (lit side x (1 + this), far side x (1 - this))
BERM_RIDGE_SHADOW = 0.5            # ridge cast-shadow strength x this (soft, low contrast)
BURIAL_DISTURBED_SOIL = True        # darker, rougher turned-soil patch around the buried part (on the ground)
DISTURBED_RADIUS_FRAC = (0.08, 0.2) # patch extent beyond the buried region / mine length (noise-modulated edge)
DISTURBED_DARKEN = (0.85, 0.95)
DISTURBED_DESAT = (0.05, 0.15)
DISTURBED_OPACITY = (0.15, 0.35)
DISTURBED_SOIL_TINT = 0.35          # share of the brown turned-soil tone in the patch (rest = the ground pixels)
BURIAL_CLODS = True                 # displaced soil clods (assets_new/dirt clods) along the soil line, with shadows
BURIAL_CLOD_COUNT = (2.0, 6.0)      # at s = 1 (user: few clods, clustered on 1-2 line segments)
BURIAL_CLOD_SIZE_FRAC = (0.015, 0.09)   # clod width / mine length, log-uniform skewed to small (wide spread)
BURIAL_CLOD_CLUSTER_FRAC = 0.06     # clods scatter around their cluster centre by this x mine length
BURIAL_EDGE_AO_DAMP = 0.6           # contact AO / contact shadow on the soil covering a buried mine x (1 - this)
BURIAL_CONTACT_BAND_SCALE = 0.5     # buried mines: SOIL_BLEND contact band darkening x this (no dark rim)
BURIAL_CLOD_COLOUR_ADAPT = 0.85     # clod colour pulled towards the turned-soil colour at its position
BURIAL_SOIL_RGB = (0.40, 0.31, 0.22)    # brown reference for turned soil (brightness follows the local ground) ...
BURIAL_SOIL_MIX = (0.3, 0.75)       # ... mixed in by this much (more on green, grassy ground)
BURIAL_DIRTY_EXPOSED = True         # exposed part: occlusion gradient at the soil line, darker / desaturated, grains,
EXPOSED_AO_PX = (2.0, 6.0)          #   streaks and a dusty film, denser towards the buried side
EXPOSED_AO_STRENGTH = (0.1, 0.25)
EXPOSED_DARKEN = (0.03, 0.1)
EXPOSED_DESAT = (0.05, 0.15)
EXPOSED_GRAIN_DENSITY = (0.04, 0.12)
EXPOSED_STREAKS = (0.05, 0.15)
EXPOSED_FILM = (0.05, 0.15)
BLADE_SOIL_LIFT = True              # over-layer blades crossing a soil line are lifted by the berm (warp + shadow)
BLADE_EMERGE = True                 # blades lying on the soil-covered part are partly covered (emerging from soil)
BLADE_EMERGE_COVER = 0.6

# --- GROUND DIRT (SOIL_BLEND: v1's hard squares become soft, irregular, locally tinted grains) ---
DIRT_LOCAL_MIX = (0.3, 0.7)         # mix of v1 dirt colour with darkened local background colour

# --- NEW LEAF-LITTER CLUMPS (LEAF_CLUMPS_NEW) ---
LEAF_CLUMPS_UNDER = (2, 8)          # per image, drawn before the mines ...
LEAF_CLUMPS_OVER = (0, 2)           # ... and after them (total ~2-10 per image)
LEAF_CLUMP_SIZE = (25, 60)          # on-screen width, px at 1080p (v1 grass clippings: 40-80)
LEAF_COLOUR_ADAPT = 0.7             # rgb *= (local ground colour / clump colour) ** this
LEAF_DESATURATE = (0.3, 0.5)        # mix towards grey
LEAF_DARKEN = (0.3, 0.5)            # brightness *= 1 - this

# --- GRASS BLADES (GRASS_BLADES) ---
# Sizes in mm on the ground; pixels per mm are drawn per image from the mine scale range:
# px_per_mm = MINE_PX_PER_UNIT * U(MINE_SCALE_MIN, MINE_SCALE_MAX) / MINE_LENGTH_MM (0.36-1.42 px/mm at 1080p).
MINE_LENGTH_MM = 120.0
BLADES_UNDER = (20, 80)             # count per image, drawn before the mines
BLADES_OVER = (15, 60)              # count per image at random positions, drawn over the mines (partial occlusion)
BLADES_OVER_ON_MINE = 0.6           # per mine: probability of extra over-layer blades crossing its box ...
BLADES_ON_MINE_COUNT = (1, 4)       # ... how many (blades / tufts / wisps, kinds as BLADE_KIND_PROBS) ...
BLADES_ON_MINE_EXPAND = 0.2         # ... centred uniformly in the box expanded by this fraction per side
BLADE_KIND_PROBS = {"blade": 0.6, "tuft": 0.25, "wisp": 0.15}
BLADE_SIZE_MM = (40.0, 160.0)       # single blade length
BLADE_WIDTH_MM = (2.0, 5.0)         # single blade width (fresh blades; pool blades keep their aspect)
TUFT_SIZE_MM = (50.0, 150.0)        # long side of a tuft
WISP_SIZE_MM = (40.0, 140.0)
BLADE_HEIGHT_MM = (0.5, 4.0)        # height above ground for the 2D shadow (blades lie nearly flat)
TUFT_HEIGHT_MM = (8.0, 30.0)        # tufts stand up -> longer shadows
WISP_HEIGHT_MM = (0.5, 4.0)
BLADE_SHADOW_SCALE = 0.6            # thin, translucent -> fainter shadows
BLADE_COLOUR_ADAPT = 0.5            # rgb *= (local ground colour / blade colour) ** this (0 = keep generator colour)
BLADE_BRIGHTNESS = (0.85, 1.1)
BLADE_FRESH_PROB = 0.5              # share of instances generated on the fly (rest: assets_new/grassBlades pool) ...
BLADE_MAX_FRESH_PER_IMAGE = 3       # ... capped per image for speed (a fresh blade / tuft costs 15-100 ms)
WISP_KINDS = ("strands", "curved", "tangle", "stubble", "hair")   # make_wisp kinds used for fresh wisps
BLADE_TOOLS_DIR = "../assets_new/tools"
BLADE_POOL_DIR = "../assets_new/grassBlades"

# --- DEBRIS EDGES (SOFT_EDGES) ---
DEBRIS_ALPHA_FEATHER = 0.8          # Gaussian sigma (px) applied to rock / grass Otsu masks after resampling

# --- BLUR (BLUR) ---
PSF_SIGMA = (0.0, 1.5)              # Gaussian defocus sigma, px at 1080p
MOTION_BLUR_PROB = 0.15
MOTION_BLUR_LENGTH = (1.0, 4.0)     # px

# --- PHOTOMETRIC JITTER (PHOTOMETRIC_JITTER) --- per image, applied after blur
EXPOSURE = (0.75, 1.25)             # multiplicative
GAMMA = (0.85, 1.15)                # rgb ** gamma
WB_GAIN = (0.92, 1.08)              # independent R and B gains (G = 1), i.e. white-balance shift
SATURATION = (0.75, 1.25)
CONTRAST = (0.95, 1.2)              # replaces V1_CONTRAST
NOISE_SIGMA = (0.0, 0.025)          # zero-mean Gaussian sensor noise (replaces v1's positive-only grain)
NOISE_CHROMA = (0.0, 0.5)           # fraction of the noise that is per-channel (colour noise)
ABERRATION = (0.0, 0.002)           # replaces V1_ABERRATION
VIGNETTE = (0.0, 0.5)               # replaces V1_VIGNETTE
JPEG_QUALITY_RANGE = (70, 95)

# --- BACKGROUND AUGMENT (BG_AUGMENT) ---
BG_FLIP_PROB = 0.5                  # independently for horizontal and vertical flips
BG_ROT90_PROB = 0.5                 # rotate by a random multiple of 90 degrees
BG_ZOOM = (1.0, 2.0)                # replaces V1_BG_ZOOM
BG_HUE_SHIFT = (-8.0, 8.0)          # degrees
BG_SATURATION = (0.8, 1.2)
BG_BRIGHTNESS = (0.8, 1.2)
BG_CHANNEL_GAIN = (0.95, 1.05)

# --- SCENE ZOOM COUPLING + NATIVE OUTPUT CROP (features/zoom.py; ADR 0016) ---
# Both default OFF: with them off every image, label and sidecar is unchanged (own random streams R(11) / R(12) / R(13)).
# SCENE_ZOOM_COUPLING: "camera moved closer". Per image z = image mine scale (the R(9) draw that also sets the ground
# px/mm) / SCENE_ZOOM_REF_SCALE. Rock / grass clipping / leaf clump / dirt snippet / ground-dirt sizes and the mine's
# pixel-sized soil / contact / AO / berm / soft-grain-blur / grain sizes are multiplied by z (grass blades are sized in
# mm and already follow px/mm); debris counts x z ** -SCENE_ZOOM_COUNT_EXP (2 = same density per ground area); the
# background texture is magnified by z, capped at SCENE_ZOOM_BG_MAX_MAG output px per source px. Sensor / optics
# effects (PSF, motion blur, noise, aberration, vignette, JPEG, penumbra base, cut-out feather) stay in pixels.
SCENE_ZOOM_COUPLING = False
SCENE_ZOOM_REF_SCALE = 0.2          # old median mine scale of the v2 plan (log bins 0.1-0.4)
SCENE_ZOOM_COUNT_EXP = 2.0          # debris counts x z ** -this (0 = keep counts per frame)
SCENE_ZOOM_BG = True                # magnify the background texture by z as well (needs SCENE_ZOOM_COUPLING)
SCENE_ZOOM_BG_MAX_MAG = 1.5         # cap: output px per background source px (never below the uncoupled value);
                                    # 2.0 looked visibly soft on soft / close-up photos (ADR 0016)
SOIL_GRAIN_PX = 1.5                 # fBm feature size (px) of the soil grains on the mine (SOIL_BLEND)
# OUTPUT_CROP = (w, h): render at SCREEN_WIDTH x SCREEN_HEIGHT, cut a w x h window (uniform position, stream R(11))
# that contains every mine (placed inside it with CROP_MINE_MARGIN px), apply the camera model to the crop, return the
# crop and labels normalised to it. None = full frame.
OUTPUT_CROP = None
CROP_MINE_MARGIN = 8

# --- LABELS ---
LABEL_ALPHA_THRESHOLD = 0.5         # pixel counts as mine if alpha > this (v1: pygame mask threshold 127/255)
LABEL_MIN_VISIBLE_PX = 1            # drop the box if fewer visible mine pixels remain (only with LABEL_VISIBLE_MASK)

# --- CONTROLLED COMPARISONS (for render_scene / showcase; None = random as usual) ---
N_MINES = None                      # force the number of mines
MINE_POSE = None                    # (pitch, roll, yaw) or (pitch, roll, yaw, face_down) for every mine
MINE_POSITIONS = None               # [(cx, cy), ...] box centres in px for mines 0, 1, ... (no overlap test)
MINE_COLOUR = None                  # (r, g, b) in [0, 1] albedo for every mine
# MINE_SCALE (override only): render_scene(..., {"mine_scale": 0.3}) fixes MINE_SCALE_MIN = MINE_SCALE_MAX

# Names of the v2 flags (used by main.py --v1 / --only and by the sidecar JSON)
V2_FLAGS = ("ASSET_AUDIT_FILTER", "NEW_ASSETS", "LEAF_CLUMPS_NEW", "GRASS_BLADES", "MESH_MINES", "SOFT_EDGES", "SHADOWS", "SOIL_BLEND", "BURIAL", "COLOUR_PALETTE",
            "PHOTOMETRIC_JITTER", "BLUR", "BG_AUGMENT", "LABEL_VISIBLE_MASK")
