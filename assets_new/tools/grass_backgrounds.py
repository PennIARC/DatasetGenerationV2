"""Grass-family background generator (real-texture photometric treatment + procedural lawns).
Usage: python3 grass_backgrounds.py [test]   -> writes ../backgrounds/bg_real_*.jpg / bg_gen_*.jpg
and tools/grass_bg_manifest.json. Needs raw_downloads/ambientcg (CC0 1K colour maps).
"""
import os, sys, glob, json, random, time
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_grass_blades import make_blade, make_tuft
A = os.path.normpath(os.path.join(HERE, ".."))
W, H = 2304, 1296

def load(a):
    return Image.open(glob.glob(f"{A}/raw_downloads/ambientcg/{a}/*_Color.jpg")[0]).convert("RGB")

def sq(im, s=1024):
    w, h = im.size; m = min(w, h); l = (w - m) // 2; t = (h - m) // 2
    return im.crop((l, t, l + m, t + m)).resize((s, s), Image.LANCZOS)

def mosaic(im, rng, T=1024, step=640, deblock=False):
    base = sq(im, T); bf = np.asarray(base, float)
    acc = np.zeros((H, W, 3)); wt = np.zeros((H, W, 1))
    win = np.hanning(T + 2)[1:-1]; w2 = (np.outer(win, win) ** 0.7)[..., None]
    for y in range(-T // 2, H, step):
        for x in range(-T // 2, W, step):
            x += int(rng.integers(-80, 80)); y += int(rng.integers(-80, 80))
            tb = bf
            if deblock:  # random slight rescale per tile: breaks alignment of the source JPEG 8x8 grid with output
                sc = rng.uniform(1.015, 1.05); n2 = int(T * sc)
                big = np.asarray(Image.fromarray(np.clip(bf, 0, 255).astype(np.uint8)).resize((n2, n2), Image.BICUBIC), float)
                o = int(rng.integers(0, n2 - T + 1)); tb = big[o:o + T, o:o + T]
            t = np.rot90(tb, int(rng.integers(0, 4)))
            if rng.random() < .5: t = t[:, ::-1]
            t = t * (bf.mean() / max(t.mean(), 1))
            x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + T, W), min(y + T, H)
            if x1 <= x0 or y1 <= y0: continue
            acc[y0:y1, x0:x1] += t[y0 - y:y1 - y, x0 - x:x1 - x] * w2[y0 - y:y1 - y, x0 - x:x1 - x]
            wt[y0:y1, x0:x1] += w2[y0 - y:y1 - y, x0 - x:x1 - x]
    out = acc / np.maximum(wt, 1e-6)
    out = (out - out.mean((0, 1))) * (bf.std((0, 1)) / np.maximum(out.std((0, 1)), 1e-3)) + bf.mean((0, 1))
    return np.clip(out, 0, 255) / 255.0

def smooth(rng, scale):
    lh, lw = H // 8 + 2, W // 8 + 2
    z = ndi.gaussian_filter(rng.standard_normal((lh, lw)), max(scale / 8, .5), mode="reflect")
    z = (z - z.mean()) / z.std()
    return np.asarray(Image.fromarray(z.astype(np.float32), "F").resize((W, H), Image.BILINEAR))

def sig(x): return 1 / (1 + np.exp(-x))

def finish(arr, rng, desat=0.2):
    lum = arr.mean(2, keepdims=True)
    arr = arr * (1 - desat) + lum * desat
    arr = arr + rng.normal(0, 0.011, arr.shape)
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))

SOILS = ["Ground002", "Ground015", "Ground023", "Ground009", "Ground007", "Ground008", "Ground004", "Ground005", "Ground031"]

# ---------------- real-texture treatment
def treat(src, kind, seed, dapple):
    rng = np.random.default_rng(seed)
    arr = mosaic(load(src), rng, deblock=True)
    lum = arr.mean(2, keepdims=True)
    arr = arr * 0.8 + lum * 0.2  # tame saturated cartoon green
    if kind in ("grass_fresh",):
        arr = arr * np.array([.88, .92, .8])
    if kind == "grass_olive":
        arr = arr * 0.7 + 0.3 * lum * np.array([1.25, 1.2, .55])
    if kind == "grass_dry":
        m = sig((smooth(rng, 260) + 0.5) * 2.5)[..., None]
        straw = lum * np.array([1.5, 1.25, .78]) + 0.05
        arr = arr * (1 - m * .85) + straw * (m * .85)
    if kind in ("grass_patchy",):
        soil = mosaic(load(random.Random(seed).choice(SOILS)), rng) * .8
        n = smooth(rng, 220) + 0.5 * smooth(rng, 70)
        m = sig((n - 0.7) * 4.5)[..., None]
        arr = arr * (1 - m) + soil * m
        dm = sig((smooth(rng, 160) - 0.6) * 4)[..., None] * .5
        arr = arr * (1 - dm) + lum * np.array([1.5, 1.3, .8]) * dm
    if kind == "moss_clover":
        arr = arr * np.array([.95, 1.0, .85])
    # patchiness/dappling as a gain-limited, smooth low-frequency gain applied to the LOW band only,
    # so detail contrast in dark areas is preserved (no hard multiply crushing the texture)
    g = (1 + 0.16 * smooth(rng, 300)[..., None]) * (1 + 0.05 * smooth(rng, 40)[..., None])
    g = np.repeat(g, 3, axis=2)
    if dapple:
        d = sig((smooth(rng, 170) + 0.6 * smooth(rng, 55) - 0.1) * 2.6)[..., None]
        g = g * (1 - 0.30 * d) * (1 - d + d * np.array([.92, .98, 1.06]))
    g = np.clip(g, 0.62, 1.3)
    arr = 0.02 + 0.98 * arr  # lift pure blacks
    low = np.stack([ndi.gaussian_filter(arr[..., c], 4) for c in range(3)], -1)
    arr = low * g + (arr - low) * np.maximum(g, 0.9) ** 0.5 * 1.04
    # shadow lift: smooth gain-limited lift of dark regions (local mean luminance floor ~0.2), no crushed blacks
    L = ndi.gaussian_filter(arr.mean(2), 20)
    gl = np.clip(0.21 / np.maximum(L, 0.02), 1.0, 1.7)
    arr = arr * gl[..., None]
    arr = 0.025 + 0.975 * arr
    return finish(arr, rng, 0.12)

# ---------------- procedural lawns
STYLES = {"mowed": dict(L=(14, 34), Wd=(1.6, 3.0), n=70000, curv=.25),
          "normal": dict(L=(22, 60), Wd=(1.8, 4.0), n=38000, curv=.45),
          "over": dict(L=(34, 90), Wd=(2.6, 5.5), n=20000, curv=.6)}
_pool = {}
def blade_pool(style, fam, k=70):
    key = (style, fam)
    if key not in _pool:
        s = STYLES[style]; r = np.random.default_rng(hash((style, fam)) % 10**6)
        _pool[key] = [make_blade(int(r.integers(1, 10**9)), length=float(r.uniform(*s["L"])),
                                 width=float(r.uniform(*s["Wd"])), family=fam,
                                 bend=float(r.normal(0, s["curv"])), droop=float(r.normal(0, .5) * r.random()))
                      for _ in range(k)]
    return _pool[key]
_tufts = []
def tuft_pool():
    if not _tufts:
        r = np.random.default_rng(5)
        _tufts.extend(make_tuft(int(r.integers(1, 10**9)), size=float(r.uniform(30, 70))) for _ in range(24))
    return _tufts

def orient(s, rng):
    s = np.rot90(s, int(rng.integers(0, 4)))
    return s[:, ::-1] if rng.random() < .5 else s

def paste(cv, s, x, y, mult):
    h, w = s.shape[:2]
    x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0: return
    sub = s[y0 - y:y1 - y, x0 - x:x1 - x]; a = sub[..., 3:4] * (1 / 255.)
    cv[y0:y1, x0:x1] = cv[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * (mult / 255.) * a
    return a

RECIPES = {
    "grass_fresh": dict(fam={"green": .7, "olive": .24, "straw": .05, "tan": .01}, dry=.3, dspots=.08, styles=["normal", "mowed", "over"]),
    "grass_olive": dict(fam={"olive": .6, "green": .15, "straw": .2, "tan": .05}, dry=.5, dspots=.15, styles=["normal", "over", "mowed"]),
    "grass_dry": dict(fam={"straw": .5, "tan": .25, "olive": .18, "green": .07}, dry=.3, dspots=.3, styles=["over", "normal"]),
    "grass_patchy": dict(fam={"green": .35, "olive": .3, "straw": .25, "tan": .1}, dry=.8, dspots=.45, styles=["normal", "over"], patchy=True),
    "moss_clover": dict(fam={"green": .8, "olive": .2}, dry=.1, dspots=.05, styles=["mowed", "normal"], clover=True),
}

def clover_sprite(rng):
    ss = 4; S = 22
    from PIL import ImageDraw
    im = Image.new("RGB", (S * ss, S * ss)); m = Image.new("L", (S * ss, S * ss))
    d = ImageDraw.Draw(im); dm = ImageDraw.Draw(m)
    col = np.array([80, 128, 56]) * rng.uniform(.85, 1.15, 3)
    a0 = rng.uniform(0, 6.28); r = S * ss * .2; c = S * ss / 2
    for k in range(3):
        a = a0 + k * 2.094; cx = c + np.cos(a) * r * .9; cy = c + np.sin(a) * r * .9
        bb = [cx - r, cy - r, cx + r, cy + r]
        d.ellipse(bb, fill=tuple(int(v * .8) for v in col)); dm.ellipse(bb, fill=255)
        bb2 = [cx - r * .75, cy - r * .75, cx + r * .75, cy + r * .75]
        d.ellipse(bb2, fill=tuple(int(v) for v in col))
    rgb = np.asarray(im, float).reshape(S, ss, S, ss, 3).mean((1, 3))
    a = np.asarray(m, float).reshape(S, ss, S, ss).mean((1, 3))
    rgb = rgb / np.maximum(a[..., None] / 255, 1e-3)
    return np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8)

def lawn(kind, seed, dapple):
    rng = np.random.default_rng(seed); R = RECIPES[kind]
    style = R["styles"][seed % len(R["styles"])]
    S = STYLES[style]
    soil = mosaic(load(SOILS[seed % len(SOILS)]), rng)
    cv = (soil * 0.62).astype(np.float32)
    nlow = smooth(rng, 240); nmid = smooth(rng, 80)
    dryn = sig(smooth(rng, 300) * 1.6)         # 0..1 dryness
    bright = 1 + 0.18 * smooth(rng, 200) + 0.06 * nmid
    dens = np.exp(0.5 * nlow + 0.2 * nmid)
    sp = sig((smooth(rng, 150) - (1.3 - 2.5 * R["dspots"])) * 3.5)  # dry/soil spots
    dens = dens * (1 - (0.93 if R.get("patchy") else 0.8) * sp)
    if R.get("patchy"):
        dens = dens * sig((smooth(rng, 200) + 0.4) * 2.2)
    dens = dens + 0.02
    # sample positions on a coarse grid
    cg = 4
    dg = dens[::cg, ::cg]; p = (dg / dg.sum()).ravel()
    fams = list(R["fam"]); base = np.array([R["fam"][f] for f in fams])
    dryf = np.array([f in ("straw", "tan") for f in fams], float)
    passes = [(0.45, .76), (.35, .92), (.2, 1.05)]
    N = int(S["n"] * rng.uniform(.8, 1.2)); tp = tuft_pool()
    for frac, pm in passes:
        n = int(N * frac)
        idx = rng.choice(p.size, size=n, p=p)
        gy, gx = np.divmod(idx, dg.shape[1])
        xs = gx * cg + rng.integers(0, cg, n) - 15; ys = gy * cg + rng.integers(0, cg, n) - 15
        al = np.zeros((H, W), np.float32)
        for x, y in zip(xs, ys):
            xc = min(max(x + 15, 0), W - 1); yc = min(max(y + 15, 0), H - 1)
            d = dryn[yc, xc] * R["dry"]
            w = base * (1 + 3 * (d * dryf + (1 - d) * (1 - dryf)) * 0 + 4 * (dryf * d - (1 - dryf) * d * .5))
            w = np.maximum(w, 0.01); w = w / w.sum()
            f = fams[rng.choice(len(fams), p=w)]
            if style != "mowed" and rng.random() < .01:
                s = orient(tp[rng.integers(len(tp))], rng)
            else:
                s = orient(blade_pool(style, f)[rng.integers(70)], rng)
            m = pm * bright[yc, xc] * rng.uniform(.88, 1.1)
            a = paste(cv, s, int(x), int(y), m)
            if a is not None:
                h_, w_ = s.shape[:2]
                y0, x0 = max(y, 0), max(x, 0); y1, x1 = min(y + h_, H), min(x + w_, W)
                al[y0:y1, x0:x1] = np.maximum(al[y0:y1, x0:x1], a[..., 0])
        cov = ndi.gaussian_filter(al, 3)
        cv *= (1 - 0.3 * cov)[..., None]
    if R.get("clover") or rng.random() < .15:
        spr = [clover_sprite(rng) for _ in range(12)]
        cn = sig(smooth(rng, 120) * 2) * (1.0 if R.get("clover") else .2)
        for _ in range(2600 if R.get("clover") else 300):
            x = int(rng.integers(0, W)); y = int(rng.integers(0, H))
            if rng.random() < cn[y, x]:
                paste(cv, orient(spr[rng.integers(12)], rng), x, y, bright[y, x] * rng.uniform(.85, 1.1) * .95)
    arr = cv.astype(np.float64)
    arr = arr * (1 + 0.08 * smooth(rng, 400)[..., None])
    if dapple:
        d = sig((smooth(rng, 170) + 0.6 * smooth(rng, 55) - 0.1) * 2.6)[..., None]
        arr = arr * (1 - 0.36 * d) * (1 - d + d * np.array([.9, .97, 1.08]))
    return finish(arr, rng, 0.1), style

if __name__ == "__main__":
    out = f"{A}/backgrounds"
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        t = time.time(); im, st = lawn("grass_patchy", 3, False); print(st, time.time() - t)
        im.save(f"{HERE}/_t1.jpg", quality=90)
        im, st = lawn("grass_fresh", 4, True); im.save(f"{HERE}/_t2.jpg", quality=90)
        treat("Grass005", "grass_patchy", 1, True).save(f"{HERE}/_t3.jpg", quality=90); sys.exit()
    man = []
    REAL_ONLY = len(sys.argv) > 1 and sys.argv[1] == "real"   # regenerate only bg_real_* (keeps bg_gen_*)
    for f in glob.glob(out + "/bg_real_*") + ([] if REAL_ONLY else glob.glob(out + "/bg_gen_*")): os.remove(f)
    real = [("Grass001", "grass_fresh", 1), ("Grass001", "moss_clover", 0), ("Grass005", "grass_fresh", 1), ("Grass005", "grass_patchy", 0),
            ("Grass006", "grass_olive", 1), ("Grass006", "grass_dry", 0), ("Grass007", "grass_dry", 1), ("Grass007", "grass_patchy", 1),
            ("Grass008", "grass_olive", 0), ("Grass008", "grass_fresh", 0), ("Grass002", "grass_olive", 1), ("Grass002", "grass_dry", 0),
            ("Grass003", "grass_patchy", 0), ("Grass003", "grass_dry", 1), ("Grass004", "grass_olive", 1), ("Grass004", "grass_patchy", 1),
            ("Moss001", "moss_clover", 0), ("Moss002", "moss_clover", 1), ("Moss001", "grass_patchy", 1), ("Moss002", "grass_olive", 0)]
    for i, (src, kind, dap) in enumerate(real):
        fn = f"bg_real_{i:02d}_{src}_{kind}.jpg"
        treat(src, kind, 100 + i, dap).save(f"{out}/{fn}", quality=96, subsampling=0)
        man.append([fn, kind, "real", src, bool(dap)]); print(fn, flush=True)
    if REAL_ONLY: sys.exit()
    plan = [("grass_fresh", 9), ("grass_olive", 9), ("grass_dry", 8), ("grass_patchy", 9), ("moss_clover", 5)]
    j = 0
    for kind, c in plan:
        for k in range(c):
            im, st = lawn(kind, 500 + j, k % 3 == 2)
            fn = f"bg_gen_{j:02d}_{kind}_{st}.jpg"; im.save(f"{out}/{fn}", quality=90)
            man.append([fn, kind, "procedural", "", k % 3 == 2]); j += 1; print(fn, flush=True)
    json.dump(man, open(f"{HERE}/grass_bg_manifest.json", "w"))
