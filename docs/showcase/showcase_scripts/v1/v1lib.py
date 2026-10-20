"""Helpers that re-implement v1 main.generate_one_image in controllable pieces.
Run with cwd = the original DatasetGenerator directory (read-only); outputs go to the V2 docs folder.
"""
import os, sys, array, random, math
ORIG = "/Users/pranavgupta/PycharmProjects/IARCdatasetGeneration/DatasetGenerator"
OUT = "/Users/pranavgupta/Desktop/PennAiR/IARCtesting/IARCdatasetGenerationV2/docs/showcase"
os.chdir(ORIG)
sys.path.insert(0, ORIG)
sys.dont_write_bytecode = True  # never write __pycache__ into the original repo

import numpy as np
import pygame, moderngl, cv2
from PIL import Image, ImageDraw, ImageFont
import controlPanel as cp
import objects
from objects import Mine, EnvironmentDebris
from calcs import normalize_yolo

W, H = cp.SCREEN_WIDTH, cp.SCREEN_HEIGHT

pygame.init()
for a, v in [(pygame.GL_CONTEXT_MAJOR_VERSION, 3), (pygame.GL_CONTEXT_MINOR_VERSION, 3),
             (pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE),
             (pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1), (pygame.GL_DOUBLEBUFFER, 1)]:
    pygame.display.gl_set_attribute(a, v)
pygame.display.set_mode((W, H), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)

BG_FILES = sorted(os.path.join("assets/backgrounds", f) for f in os.listdir("assets/backgrounds")
                  if f.lower().endswith((".jpg", ".png", ".jpeg")))
SPRITES = sorted(os.path.join("assets/mines", f) for f in os.listdir("assets/mines") if f.endswith(".png"))

# ---------------- shader (post.frag with 3 constants turned into uniforms) ----------------
_frag = open("shaders/post.frag").read()
_vert = open("shaders/basic.vert").read()
for old, new in [("uniform float noise_strength;", "uniform float noise_strength;\nuniform float ab;\nuniform float vig;\nuniform float contrast;"),
                 ("float aberration = 0.002;", "float aberration = ab;"),
                 ("(1.0 - dist * 0.4)", "(1.0 - dist * vig)"),
                 ("* 1.1 + 0.5", "* contrast + 0.5")]:
    assert old in _frag, old
    _frag = _frag.replace(old, new)

ctx = moderngl.create_context()
tex = ctx.texture((W, H), 3)
tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
quad = ctx.buffer(data=array.array("f", [-1, 1, 0, 0, -1, -1, 0, 1, 1, 1, 1, 0, 1, -1, 1, 1]))
prog = ctx.program(vertex_shader=_vert, fragment_shader=_frag)
vao = ctx.vertex_array(prog, [(quad, "2f 2f", "in_vert", "in_text")])
fbo = ctx.simple_framebuffer((W, H))


def shade(surface, noise=0.0, ab=0.0, vig=0.0, contrast=1.0, t=123.0):
    """Exactly the v1 pass (noise, then aberration which overwrites R and B, vignette, contrast)."""
    tex.write(pygame.image.tobytes(surface, "RGB"), alignment=1)
    tex.use(0)
    prog["time"].value = t
    prog["noise_strength"].value = noise
    prog["ab"].value = ab
    prog["vig"].value = vig
    prog["contrast"].value = contrast
    fbo.use(); ctx.clear()
    vao.render(mode=moderngl.TRIANGLE_STRIP)
    data = fbo.read(components=3, alignment=1)
    img = pygame.image.frombytes(data, (W, H), "RGB")
    img = pygame.transform.flip(img, False, True)
    return s2np(img)


V1_SHADER = dict(noise=0.08, ab=0.002, vig=0.4, contrast=1.1)  # v1 draws noise U(0.05,0.12)


def s2np(surf):
    w, h = surf.get_size()
    return np.frombuffer(pygame.image.tobytes(surf, "RGB"), np.uint8).reshape(h, w, 3).copy()


# ---------------- layers ----------------
def background(bg_idx=0, zoom=None, fx=0.5, fy=0.5):
    """zoom=None -> plain cover-scale (min_scale). zoom z -> min_scale*z with offset fraction (fx,fy)
    (v1 draws offset with randint(0,max_offset); fractions make it comparable across options)."""
    surf = pygame.Surface((W, H)).convert()
    img = pygame.image.load(BG_FILES[bg_idx]).convert()
    iw, ih = img.get_size()
    sc = max(W / iw, H / ih) * (zoom or 1.0)
    nw, nh = int(iw * sc), int(ih * sc)
    img = pygame.transform.scale(img, (nw, nh))
    ox = int(fx * max(0, nw - W)); oy = int(fy * max(0, nh - H))
    surf.blit(img, (-ox, -oy))
    return surf


def make_debris(seed, dirt=None, rocks=None, grass=None):
    """dirt: density_factor or None; rocks: exact count or None; grass: GRASS_CLIPPINGS_PER_IMAGE or None.
    Each sub-layer has its own seed so toggling one does not reshuffle the others."""
    d = EnvironmentDebris.__new__(EnvironmentDebris)
    d.w, d.h, d.elements = W, H, []
    counts = {}
    if dirt is not None:
        random.seed(seed * 10 + 1); np.random.seed(seed * 10 + 1)
        n0 = len(d.elements); d._generate_dirt(dirt); counts["dirt"] = len(d.elements) - n0
    if rocks is not None:
        random.seed(seed * 10 + 2)
        old = (cp.ROCKS_TO_SPAWN_MIN, cp.ROCKS_TO_SPAWN_MAX)
        cp.ROCKS_TO_SPAWN_MIN = cp.ROCKS_TO_SPAWN_MAX = rocks
        n0 = len(d.elements); d._generate_rocks(1.0); counts["rocks"] = len(d.elements) - n0
        cp.ROCKS_TO_SPAWN_MIN, cp.ROCKS_TO_SPAWN_MAX = old
    if grass is not None:
        random.seed(seed * 10 + 3)
        old = cp.GRASS_CLIPPINGS_PER_IMAGE
        cp.GRASS_CLIPPINGS_PER_IMAGE = grass
        n0 = len(d.elements); d._generate_grass_overlays(1.0); counts["grass"] = len(d.elements) - n0
        cp.GRASS_CLIPPINGS_PER_IMAGE = old
    d.counts = counts
    return d


_orig_dirt = Mine._add_surface_dirt
_DIRT_ON = [True]


def _dirt_wrapper(self):
    if _DIRT_ON[0]:
        _orig_dirt(self)
    else:  # keep the RNG stream identical, but discard the specks
        bak = self.image.copy(); _orig_dirt(self); self.image = bak


Mine._add_surface_dirt = _dirt_wrapper


def make_mine(sprite_path, scale, angle, dirt=True, seed=0):
    """Mine.__init__ with sprite / scale / rotation forced."""
    random.seed(seed)
    _DIRT_ON[0] = dirt
    m = Mine.__new__(Mine)
    m.original_image = pygame.image.load(sprite_path).convert_alpha()
    w = int(m.original_image.get_width() * scale); h = int(m.original_image.get_height() * scale)
    m.image = pygame.transform.scale(m.original_image, (w, h))
    m.angle = angle
    m.image = pygame.transform.rotate(m.image, angle)
    m.mask = pygame.mask.from_surface(m.image)
    m.rect = m.image.get_rect()
    m._add_surface_dirt()
    _DIRT_ON[0] = True
    return m


def place_mines(seed, n, dirt=True, scale_range=None, naive=False):
    """v1 placement loop. naive=True skips the overlap rejection (for comparison only)."""
    random.seed(seed * 10 + 4)
    _DIRT_ON[0] = dirt
    sr = scale_range or (cp.MINE_SCALE_MIN, cp.MINE_SCALE_MAX)
    mines, labels = [], []
    for _ in range(n):
        m = Mine("assets/mines", sr)
        placed, att = False, 0
        while not placed and att < 50:
            m.set_position(W, H)
            coll = any(m.rect.colliderect(e.rect.inflate(10, 10)) for e in mines) if not naive else False
            placed = not coll
            att += 1
        if placed:
            lbl = m.get_yolo_bbox(W, H)
            if lbl:
                labels.append(lbl); mines.append(m)
    _DIRT_ON[0] = True
    return mines, labels


def compose(bg, debris=None, mines=(), over=None):
    s = bg.copy()
    if debris: debris.draw(s)
    for m in mines: m.draw(s)
    if over: over.draw(s)
    return s


# ---------------- image helpers ----------------
def font(sz):
    for p in ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def save_jpg(arr, name, maxw=1400):
    im = Image.fromarray(arr) if isinstance(arr, np.ndarray) else arr
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    p = os.path.join(OUT, "images/v1", name); im.convert("RGB").save(p, quality=88); return "images/v1/" + name


def save_png(arr, name, maxw=1400):
    im = Image.fromarray(arr) if isinstance(arr, np.ndarray) else arr
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    p = os.path.join(OUT, "images/v1", name); im.convert("RGB").save(p, optimize=True); return "images/v1/" + name


def zoom(arr, x, y, w, h, f, nearest=False):
    im = Image.fromarray(arr).crop((x, y, x + w, y + h))
    return im.resize((w * f, h * f), Image.NEAREST if nearest else Image.LANCZOS)


def draw_boxes(arr, labels, color=(0, 255, 0), width=3, w=None, h=None):
    im = Image.fromarray(arr); d = ImageDraw.Draw(im)
    iw, ih = im.size
    for l in labels:
        _, xc, yc, bw, bh = l
        d.rectangle([(xc - bw / 2) * iw, (yc - bh / 2) * ih, (xc + bw / 2) * iw, (yc + bh / 2) * ih], outline=color, width=width)
    return np.array(im)


def caption(im, text, sz=22):
    """Add a dark label bar at the top of a PIL image."""
    f = font(sz)
    out = Image.new("RGB", (im.width, im.height + sz + 14), (24, 24, 24))
    out.paste(im, (0, sz + 14))
    ImageDraw.Draw(out).text((8, 6), text, fill=(255, 255, 255), font=f)
    return out
