# --- GENERATION SETTINGS ---
NUM_IMAGES_TO_GENERATE = 2000
START_INDEX = 0 # Useful if running batches

# --- DISPLAY / OUTPUT ---
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
OUTPUT_PATH = "output_dataset"
IMAGES_DIR = "images"
LABELS_DIR = "labels"

# --- SCENARIO SETTINGS ---
MIN_MINES = 0
MAX_MINES = 8

# --- SCALE ---
# How big should the mine be relative to 1080p?
# Real PFM-1 is ~12cm. At 5m altitude, it might be 100-200 pixels wide depending on FOV.
MINE_SCALE_MIN = 0.1
MINE_SCALE_MAX = 0.4

# --- COLORS ---
# Dirt particle colors
DIRT_COLOR_BASE = (101, 67, 33) # Dark Brown
DIRT_VARIANCE = 40

# --- GRASS DEBRIS ---
GRASS_ASSET_DIR = "assets/grassDebris"
GRASS_IMAGES_TO_SAMPLE = 4      # How many distinct grass images to use per scene
GRASS_CLIPPINGS_PER_IMAGE = 16   # How many small crops to take from each image
GRASS_CROP_SIZE_MIN = 100       # Size of the crop window on the source image
GRASS_CROP_SIZE_MAX = 300
GRASS_OUTPUT_SIZE_MIN = 40      # Final width on screen
GRASS_OUTPUT_SIZE_MAX = 80

# --- ROCK DEBRIS ---
ROCK_ASSET_DIR = "assets/rocks"
ROCKS_TO_SPAWN_MIN = 5
ROCKS_TO_SPAWN_MAX = 20
ROCK_OUTPUT_SIZE_MIN = 40      # Larger than grass
ROCK_OUTPUT_SIZE_MAX = 100

# --- SHADERS ---
ENABLE_POST_PROCESSING = True