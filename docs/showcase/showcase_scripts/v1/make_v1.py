"""Builds all v1 showcase images + manifest data (manifest_v1.json written by build_manifest.py).
Run:  cd <orig>/DatasetGenerator && <orig>/.venv/bin/python3 <this file>
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from v1lib import *

BASE_BG = int(os.environ.get("BASE_BG", 0))
SEED = 11
RES = {}  # feature id -> {"options":[...], "before_after":[...]}


def add_opt(fid, label, params, image, caption=""):
    RES.setdefault(fid, {"options": [], "before_after": []})["options"].append(
        dict(label=label, params=params, image=image, caption=caption))


def add_ba(fid, label, before, after, bl, al, caption=""):
    RES.setdefault(fid, {"options": [], "before_after": []})["before_after"].append(
        dict(label=label, before=before, after=after, before_label=bl, after_label=al, caption=caption))


def label_img(im, text):
    return caption(im, text, 22)


# =============== 1 backgrounds ===============
def f_backgrounds():
    cols, cw, ch = 5, 360, 203
    sheet = Image.new("RGB", (cols * cw, 3 * (ch + 22)), (24, 24, 24))
    d = ImageDraw.Draw(sheet); f = font(16)
    for i, p in enumerate(BG_FILES):
        im = Image.open(p).convert("RGB")
        sc = max(cw / im.width, ch / im.height)
        im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
        l, t = (im.width - cw) // 2, (im.height - ch) // 2
        im = im.crop((l, t, l + cw, t + ch))
        x, y = (i % cols) * cw, (i // cols) * (ch + 22)
        sheet.paste(im, (x, y + 22))
        d.text((x + 6, y + 3), f"{i:02d} {os.path.basename(p)[:30]}", fill=(255, 255, 255), font=f)
    add_opt("backgrounds", "all 15 photos", "assets/backgrounds/*.png (7 grassN.png + 8 screenshots)",
            save_jpg(np.array(sheet), "bg_contact_sheet.jpg"), "Centre-cropped thumbnails of every background photo v1 can pick.")
    for z in (1.0, 1.25, 1.5):
        s = background(BASE_BG, z, 0.4, 0.3)
        tag = str(z).replace(".", "_")
        add_opt("backgrounds", f"zoom {z}", f"zoom={z}, crop offset fraction (0.4, 0.3)",
                save_jpg(s2np(s), f"bg_zoom_{tag}.jpg"), "Same photo and same crop anchor; higher zoom shows a smaller, blurrier part of the photo.")
    a = s2np(background(BASE_BG, 1.5, 0.05, 0.05)); b = s2np(background(BASE_BG, 1.5, 0.95, 0.9))
    add_ba("backgrounds", "Random crop offset", save_jpg(a, "bg_crop_a.jpg"), save_jpg(b, "bg_crop_b.jpg"),
           "offset near top-left", "offset near bottom-right", "Same photo, zoom 1.5: the random offset gives two different-looking training images.")


# =============== 2 dirt ===============
def f_dirt():
    bg = background(BASE_BG, 1.0, 0.4, 0.3)
    for dens in (0.5, 1.0, 2.0):
        deb = make_debris(SEED, dirt=dens)
        img = s2np(compose(bg, deb))
        add_opt("dirt", f"density {dens}", f"density_factor={dens} ({deb.counts['dirt']} squares; v1 count = randint(50,200) x density)",
                save_jpg(img, f"dirt_density_{str(dens).replace('.', '_')}.jpg"))
    off = s2np(bg); on = s2np(compose(bg, make_debris(SEED, dirt=1.0)))
    r = (500, 250, 640, 360)
    add_ba("dirt", "Dirt specks (2x crop)", save_png(np.array(zoom(off, *r, 2)), "dirt_off.png"),
           save_png(np.array(zoom(on, *r, 2)), "dirt_on.png"), "off", "on (density 1.0)",
           "Hard-edged brown squares, 4-12 px, with a different shade each.")


# =============== 3 rocks ===============
def f_rocks():
    bg = background(BASE_BG, 1.0, 0.4, 0.3)
    for n in (5, 12, 20):
        deb = make_debris(SEED, rocks=n)
        add_opt("rocks", f"{n} rocks", f"ROCKS_TO_SPAWN_MIN=MAX={n}, size 40-100 px, random rotation",
                save_jpg(s2np(compose(bg, deb)), f"rocks_{n}.jpg"))
    off = s2np(bg); on = s2np(compose(bg, make_debris(SEED, rocks=12)))
    r = (400, 200, 800, 450)
    add_ba("rocks", "Rock debris (crop)", save_jpg(np.array(zoom(off, *r, 1)), "rocks_off.jpg"),
           save_jpg(np.array(zoom(on, *r, 1)), "rocks_on.jpg"), "off", "on (12 rocks)",
           "Photographed rocks pasted on the grass at random positions and rotations; there is no shadow under them.")
    # cutout edge: raw photo vs Otsu cutout
    deb = EnvironmentDebris.__new__(EnvironmentDebris)
    files = sorted(os.path.join(cp.ROCK_ASSET_DIR, f) for f in os.listdir(cp.ROCK_ASSET_DIR))
    path = files[4]
    cut = deb._process_image_otsu(path)
    raw = pygame.image.load(path).convert()
    tw = 100; th = int(tw * cut.get_height() / cut.get_width())
    cut = pygame.transform.scale(cut, (tw, th)); raw = pygame.transform.scale(raw, (tw, th))
    pos = (700, 400)
    sa = bg.copy(); sa.blit(raw, pos)
    sb = bg.copy(); sb.blit(cut, pos)
    mask = pygame.Surface((tw, th)); mask.fill((0, 0, 0))
    ma = pygame.mask.from_surface(cut).to_surface(setcolor=(255, 255, 255), unsetcolor=(0, 0, 0))
    sc = bg.copy(); sc.blit(ma, pos)
    r = (pos[0] - 15, pos[1] - 15, tw + 30, th + 30)
    add_opt("rocks", "Otsu alpha mask", "mask = Otsu threshold of blurred grey rock photo (white = kept)",
            save_png(np.array(zoom(s2np(sc), *r, 5, True)), "rocks_mask.png"), "The binary mask that becomes the alpha channel.")
    add_ba("rocks", "Cutout edge (5x zoom)", save_png(np.array(zoom(s2np(sa), *r, 5, True)), "rock_edge_raw.png"),
           save_png(np.array(zoom(s2np(sb), *r, 5, True)), "rock_edge_cut.png"), "raw photo pasted", "Otsu cutout",
           "Look at the rim: the cut is a hard 1-bit edge with no feathering, and shadowed parts of the rock can be cut away.")


# =============== 4 grass ===============
def f_grass():
    bg = background(BASE_BG, 1.0, 0.4, 0.3)
    for n in (5, 16, 32):
        deb = make_debris(SEED, grass=n)
        add_opt("grass", f"cap {n}", f"GRASS_CLIPPINGS_PER_IMAGE={n} ({deb.counts['grass']} clippings from 4 source photos)",
                save_jpg(s2np(compose(bg, deb)), f"grass_{n}.jpg"),
                "Value 4 from the brief is impossible in v1: randint(5, 4) raises ValueError, so 5 is the smallest usable setting." if n == 5 else "")
    off = s2np(bg); on = s2np(compose(bg, make_debris(SEED, grass=16)))
    r = (400, 200, 800, 450)
    add_ba("grass", "Grass clippings (crop)", save_jpg(np.array(zoom(off, *r, 1)), "grass_off.jpg"),
           save_jpg(np.array(zoom(on, *r, 1)), "grass_on.jpg"), "off", "on (cap 16)",
           "Cut-out crops of blade photos scattered on the lawn; patches that are mostly background are skipped.")


# =============== 5 sprites ===============
def f_sprites():
    cols, rows, cw, ch = 10, 5, 150, 150
    sheet = Image.new("RGB", (cols * cw, rows * ch), (128, 128, 128))
    for i, p in enumerate(SPRITES):
        im = Image.open(p).convert("RGBA")
        sc = min((cw - 8) / im.width, (ch - 8) / im.height)
        im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
        x, y = (i % cols) * cw + (cw - im.width) // 2, (i // cols) * ch + (ch - im.height) // 2
        sheet.paste(im, (x, y), im)
    add_opt("sprites", "all 50 sprites", "assets/mines/mine_0000..0049.png on mid-grey",
            save_png(np.array(sheet), "sprite_sheet.png"), "Pre-rendered 3D mine renders: pitch/roll in +-20 deg, yaw 0-360, brightness shifts.")
    # scale x rotation grid
    sp = SPRITES[7]
    scales = [cp.MINE_SCALE_MIN, 0.25, cp.MINE_SCALE_MAX]
    rots = [37, 151, 262]
    cell = 260
    bgs = background(BASE_BG, 1.0, 0.5, 0.5)
    canvas = pygame.Surface((cell * 3, cell * 3))
    canvas.blit(bgs, (0, 0), (600, 300, cell * 3, cell * 3))
    for r, s in enumerate(scales):
        for c, a in enumerate(rots):
            m = make_mine(sp, s, a, True, seed=100 + r * 3 + c)
            m.rect.center = (c * cell + cell // 2, r * cell + cell // 2)
            m.draw(canvas)
    im = Image.fromarray(s2np(canvas))
    d = ImageDraw.Draw(im); f = font(18)
    for r, s in enumerate(scales):
        for c, a in enumerate(rots):
            d.text((c * cell + 6, r * cell + 4), f"scale {s}  rot {a} deg", fill=(255, 255, 255), font=f, stroke_width=2, stroke_fill=(0, 0, 0))
    add_opt("sprites", "scale x rotation grid", f"{os.path.basename(sp)}; scale in {scales}; in-plane rotation in {rots} deg (rows = scale, cols = rotation)",
            save_png(np.array(im), "sprite_scale_rotation.png"), "One sprite placed at the three scales and three in-plane rotations.")
    # before/after: raw vs placed
    flat = pygame.Surface((cell, cell)); flat.fill((128, 128, 128))
    m0 = make_mine(sp, 0.4, 0, False); m0.rect.center = (cell // 2, cell // 2); m0.draw(flat)
    pl = pygame.Surface((cell, cell)); pl.blit(bgs, (0, 0), (600, 300, cell, cell))
    m1 = make_mine(sp, 0.4, 110, True, seed=5); m1.rect.center = (cell // 2, cell // 2); m1.draw(pl)
    add_ba("sprites", "Sprite vs placed mine", save_png(s2np(flat), "sprite_flat.png"), save_png(s2np(pl), "sprite_placed.png"),
           "sprite on grey (scale 0.4)", "as placed: rotated 110 deg + dirt, on grass",
           "Same sprite; placement adds the second rotation and surface specks. Note the sprite carries its own baked-in lighting.")


# =============== 6 count & placement ===============
def f_count():
    bg = background(BASE_BG, 1.0, 0.4, 0.3)
    for n in (0, 1, 4, 8):
        mines, labels = place_mines(SEED + n, n)
        img = draw_boxes(s2np(compose(bg, make_debris(SEED, dirt=1.0), mines)), labels, width=3)
        add_opt("count", f"{n} mines", f"n_mines={n} (v1: randint(0,8), 10% chance forced to 0), YOLO boxes in green",
                save_jpg(img, f"mines_{n}.jpg"))
    # naive vs rejection, scale forced 0.4
    found = None
    for s in range(200):
        mines_n, lab_n = place_mines(s, 8, scale_range=(0.4, 0.4), naive=True)
        ov = sum(mines_n[i].rect.colliderect(mines_n[j].rect.inflate(10, 10)) for i in range(8) for j in range(i + 1, 8) if len(mines_n) == 8)
        if len(mines_n) == 8 and ov >= 2:
            found = s; break
    s = found if found is not None else 0
    mines_n, lab_n = place_mines(s, 8, scale_range=(0.4, 0.4), naive=True)
    mines_r, lab_r = place_mines(s, 8, scale_range=(0.4, 0.4), naive=False)
    bg2 = background(BASE_BG, 1.0, 0.4, 0.3)
    a = draw_boxes(s2np(compose(bg2, None, mines_n)), lab_n, (255, 60, 60), 3)
    b = draw_boxes(s2np(compose(bg2, None, mines_r)), lab_r, (0, 255, 0), 3)
    add_ba("count", "Overlap rejection", save_jpg(a, "place_naive.jpg"), save_jpg(b, "place_reject.jpg"),
           "no check (random positions)", "v1 check: rect vs rect inflated by 10 px, up to 50 tries",
           f"8 mines at scale 0.4 (seed {s}). Without the check some boxes overlap; with it each mine is re-rolled until its rectangle is clear. Failures after 50 tries are silently dropped.")


# =============== 7 mine dirt ===============
def f_minedirt():
    sp = SPRITES[12]
    bgs = background(BASE_BG, 1.0, 0.5, 0.5)
    def patch(dirt, seed, sprite=sp):
        c = pygame.Surface((200, 150)); c.blit(bgs, (0, 0), (800, 400, 200, 150))
        m = make_mine(sprite, 0.4, 25, dirt, seed=seed); m.rect.center = (100, 75); m.draw(c)
        return s2np(c)
    for i, sd in enumerate((1, 2, 3)):
        sprite = SPRITES[[12, 20, 33][i]]
        add_opt("minedirt", f"example {i + 1}", f"{os.path.basename(sprite)}, scale 0.4, 5-20 circles r=1-3, colour (80,60,40)+-30, 4x nearest zoom",
                save_png(np.array(Image.fromarray(patch(True, sd, sprite)).resize((800, 600), Image.NEAREST)), f"minedirt_ex{i + 1}.png"))
    a = np.array(Image.fromarray(patch(False, 7)).resize((800, 600), Image.NEAREST))
    b = np.array(Image.fromarray(patch(True, 7)).resize((800, 600), Image.NEAREST))
    add_ba("minedirt", "Surface dirt (4x zoom)", save_png(a, "minedirt_off.png"), save_png(b, "minedirt_on.png"), "off", "on",
           "Round, hard-edged dots in one brownish colour family; the pixels near a dot's edge can spill past the silhouette.")


# =============== 8 overgrowth ===============
def f_over():
    sp = SPRITES[7]
    m = make_mine(sp, 0.4, 70, True, seed=3)
    mw, mh = m.rect.size
    maskarr = pygame.surfarray.array3d(pygame.mask.from_surface(m.image).to_surface(setcolor=(255, 255, 255), unsetcolor=(0, 0, 0)))[:, :, 0] > 0  # (w,h)
    best = None
    for s in range(1, 80):
        rng = random.Random(s)
        over = make_debris(1000 + s, dirt=1.0, rocks=rng.randint(5, 20), grass=16)
        ov = pygame.Surface((W, H), pygame.SRCALPHA); ov.fill((0, 0, 0, 0)); over.draw(ov)
        alpha = pygame.surfarray.array_alpha(ov) > 0  # (W,H)
        for _ in range(30):
            x = rng.randint(100, W - mw - 100); y = rng.randint(100, H - mh - 100)
            cov = alpha[x:x + mw, y:y + mh][maskarr].mean()
            if 0.25 <= cov <= 0.5 and (best is None or abs(cov - 0.35) < abs(best[0] - 0.35)):
                best = (cov, s, x, y, over, alpha[x:x + mw, y:y + mh].copy())
        if best and abs(best[0] - 0.35) < 0.05:
            break
    cov, s, x, y, over, ovsub = best
    bg = background(BASE_BG, 1.0, 0.4, 0.3)
    m.rect.topleft = (x, y)
    before = compose(bg, None, [m]); after = compose(bg, None, [m], over)
    lab = m.get_yolo_bbox(W, H)
    pad = 60
    r = (x - pad, y - pad, mw + 2 * pad, mh + 2 * pad)
    r = (max(r[0], 0), max(r[1], 0), r[2], r[3])
    f = 3
    A = s2np(before); B = s2np(after)
    add_ba("overgrowth", "Occlusion layer", save_png(np.array(zoom(A, *r, f)), "over_off.png"), save_png(np.array(zoom(B, *r, f)), "over_on.png"),
           "mine, no overgrowth", "second debris layer drawn after the mine",
           f"About {cov * 100:.0f}% of this mine's silhouette is covered (seed {s}).")
    # box vs visible
    vis = maskarr & ~ovsub
    xs, ys = np.where(vis)
    vbox = (x + xs.min(), y + ys.min(), x + xs.max() + 1, y + ys.max() + 1)
    im = Image.fromarray(B); d = ImageDraw.Draw(im)
    _, xc, yc, bw, bh = lab
    gb = ((xc - bw / 2) * W, (yc - bh / 2) * H, (xc + bw / 2) * W, (yc + bh / 2) * H)
    d.rectangle(gb, outline=(0, 255, 0), width=1); d.rectangle(vbox, outline=(255, 60, 60), width=1)
    crop = im.crop((r[0], r[1], r[0] + r[2], r[1] + r[3])).resize((r[2] * f, r[3] * f), Image.NEAREST)
    d = ImageDraw.Draw(crop)
    for bx, col in ((gb, (0, 255, 0)), (vbox, (255, 60, 60))):
        d.rectangle([(bx[0] - r[0]) * f, (bx[1] - r[1]) * f, (bx[2] - r[0]) * f, (bx[3] - r[1]) * f], outline=col, width=3)
    add_opt("overgrowth", "label box vs visible area", "green = v1 YOLO box (from unoccluded sprite mask); red = bounding box of the pixels actually still visible",
            save_png(np.array(crop), "over_box_vs_visible.png"), f"Visible fraction of the silhouette ~{(1 - cov) * 100:.0f}%.")
    # second example: the mine with a different overgrowth seed (stronger)
    over2 = make_debris(2001, dirt=2.0, rocks=20, grass=32)
    C = s2np(compose(bg, None, [m], over2))
    add_opt("overgrowth", "heavy overgrowth", "second layer with dirt density 2, 20 rocks, grass cap 32 (not the v1 default; exaggerated)",
            save_png(np.array(zoom(C, *r, f)), "over_heavy.png"), "The same mine under a denser second layer.")


# =============== full scene for 9 and 10 ===============
def full_scene(seed=7, n=5):
    bg = background(BASE_BG, 1.25, 0.4, 0.3)
    deb = make_debris(seed, dirt=1.0, rocks=10, grass=16)
    mines, labels = place_mines(seed, n)
    over = make_debris(seed + 500, dirt=1.0, rocks=6, grass=8)
    return compose(bg, deb, mines, over), mines, labels


def f_shader():
    surf, mines, labels = full_scene()
    base = shade(surf)  # all effects off
    assert np.abs(base.astype(int) - s2np(surf).astype(int)).max() <= 1, "identity shader pass mismatch"
    g05 = shade(surf, noise=0.05); g12 = shade(surf, noise=0.12)
    ca = shade(surf, ab=0.002); vg = shade(surf, vig=0.4); ct = shade(surf, contrast=1.1)
    allfx = shade(surf, **V1_SHADER)
    cr = (700, 400, 200, 200)
    def zc(a, r=cr, f=4): return np.array(zoom(a, *r, f, True))
    add_opt("shader", "grain 0.05", "noise_strength=0.05 (alone), 4x nearest crop of 200x200", save_png(zc(g05), "shader_grain_005.png"),
            "The grain is added to all three channels, then red and blue are overwritten by the aberration step, so only green keeps it.")
    add_opt("shader", "grain 0.12", "noise_strength=0.12 (alone), 4x nearest crop of 200x200", save_png(zc(g12), "shader_grain_012.png"))
    add_opt("shader", "vignette 0.4", "vignette strength 0.4 (alone), full frame", save_jpg(vg, "shader_vignette.jpg"))
    add_opt("shader", "all four together", "noise 0.08 (v1 draws U(0.05,0.12)), aberration 0.002, vignette 0.4, contrast 1.1", save_jpg(allfx, "shader_all.jpg"))
    add_ba("shader", "Grain 0.12 (4x crop)", save_png(zc(base), "shader_grain_off.png"), save_png(zc(g12), "shader_grain_on.png"), "off", "noise 0.12")
    # CA crop at a mine edge
    _, xc, yc, bw, bh = labels[0]
    ex, ey = int((xc - bw / 2) * W), int(yc * H)
    r = (max(0, ex - 40), max(0, ey - 40), 80, 80)
    add_ba("shader", "Chromatic aberration (8x crop at a mine edge)", save_png(zc(base, r, 8), "shader_ca_off.png"), save_png(zc(ca, r, 8), "shader_ca_on.png"),
           "off", "aberration 0.002 (about 3.8 px)", "Red is sampled 3.8 px to the right and blue 3.8 px to the left, giving coloured fringes on vertical edges.")
    add_ba("shader", "Vignette", save_jpg(base, "shader_vig_off.jpg"), save_jpg(vg, "shader_vig_on.jpg"), "off", "0.4",
           "Corners are multiplied by about 0.72; the centre is untouched.")
    add_ba("shader", "Contrast 1.1", save_jpg(base, "shader_ct_off.jpg"), save_jpg(ct, "shader_ct_on.jpg"), "off", "1.1",
           "A mild push around mid-grey: darks get darker, lights lighter.")
    add_ba("shader", "All effects", save_jpg(base, "shader_pre.jpg"), save_jpg(allfx, "shader_all2.jpg"), "pre-shader frame", "after full v1 pass")


def f_export():
    surf, mines, labels = full_scene()
    img = shade(surf, **V1_SHADER)
    a = draw_boxes(img, labels, (0, 255, 0), 3)
    res = cv2.resize(img, (640, 640), interpolation=cv2.INTER_LINEAR)
    b = draw_boxes(res, labels, (0, 255, 0), 1)
    left = Image.fromarray(a).resize((800, 450), Image.LANCZOS)
    right = Image.fromarray(b).resize((560, 560), Image.LANCZOS)
    can = Image.new("RGB", (800 + 20 + 560, 560), (24, 24, 24))
    can.paste(left, (0, 55)); can.paste(right, (820, 0))
    d = ImageDraw.Draw(can); f = font(20)
    d.text((6, 6), "generated 1920x1080 + YOLO boxes", fill=(255, 255, 255), font=f)
    d.text((6, 30), "same file values (normalised) unchanged", fill=(200, 200, 200), font=font(16))
    side = np.array(can)
    add_opt("export", "side by side", "cv2.resize(img,(640,640), INTER_LINEAR); label numbers copied unchanged",
            save_jpg(side, "export_side_by_side.jpg"),
            "Left: 1920x1080 with boxes. Right: the 640x640 export (shown at 560 px) with the same normalised boxes redrawn.")
    add_opt("export", "1920x1080 source", "full-resolution labels drawn", save_jpg(a, "export_1920.jpg"))
    add_opt("export", "640x640 stretched", "640x640, boxes redrawn from the unchanged label file", save_png(b, "export_640.png"))
    _, xc, yc, bw, bh = labels[0]
    cx, cy = int(xc * W), int(yc * H)
    r = (max(0, cx - 100), max(0, cy - 100), 200, 200)
    before = np.array(Image.fromarray(img).crop((r[0], r[1], r[0] + 200, r[1] + 200)).resize((400, 400), Image.LANCZOS))
    sx, sy = 640 / W, 640 / H
    r2 = (int(r[0] * sx), int(r[1] * sy), max(1, round(200 * sx)), max(1, round(200 * sy)))
    after = np.array(Image.fromarray(res).crop((r2[0], r2[1], r2[0] + r2[2], r2[1] + r2[3])).resize((r2[2] * 6, r2[3] * 6), Image.NEAREST))
    add_ba("export", "Same mine before/after export", save_png(before, "export_mine_before.png"), save_png(after, "export_mine_after.png"),
           "1920x1080 (2x view)", "640x640 (6x nearest view of the same region)",
           f"x shrinks by {sx:.3f} (1/3) and y by {sy:.3f}, so round things become tall and narrow.")


for fn in (f_backgrounds, f_dirt, f_rocks, f_grass, f_sprites, f_count, f_minedirt, f_over, f_shader, f_export):
    print("running", fn.__name__, flush=True)
    fn()
json.dump(RES, open(os.path.join(OUT, "showcase_scripts/v1/results.json"), "w"), indent=1)
print("done")
