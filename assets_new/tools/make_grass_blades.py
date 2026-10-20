"""Procedural grass blade / tuft / wisp generator (numpy + PIL only, seeded).

All functions return an RGBA uint8 numpy array (H, W, 4) with a real alpha channel,
cropped tight to the content, blade pointing roughly "up" unless `orientation` is given
(radians, 0 = up, clockwise positive). Colours are straight (non-premultiplied) RGB.

    from make_grass_blades import make_blade, make_tuft, make_wisp
    rgba = make_blade(seed=12)                      # random family/length/width
    rgba = make_blade(5, length=120, width=6, family="straw", bend=0.6)
    rgba = make_tuft(3); rgba = make_wisp(4)
Families: "green", "olive", "straw", "tan".
"""
import math
import numpy as np
from PIL import Image, ImageDraw

FAMILIES = {  # base RGB (mean), per-channel jitter
    "green": ((72, 118, 42), 0.16),
    "olive": ((112, 122, 52), 0.14),
    "straw": ((200, 178, 102), 0.12),
    "tan":   ((152, 118, 72), 0.14),
    "brown": ((108, 80, 52), 0.14),
}
FAMILY_P = {"green": .30, "olive": .28, "straw": .26, "tan": .16}


def _pick_family(rng, family=None):
    if family:
        return family
    ks = list(FAMILY_P)
    return ks[rng.choice(len(ks), p=[FAMILY_P[k] for k in ks])]


def _jitter_colour(rng, family):
    base, j = FAMILIES[family]
    c = np.array(base, float) * rng.uniform(1 - j, 1 + j)
    c = c * (1 + rng.normal(0, 0.04, 3))  # slight hue shift
    return np.clip(c, 0, 255)


class _Canvas:
    def __init__(self, w, h, ss):
        self.ss = ss
        self.rgb = Image.new("RGB", (w * ss, h * ss), (0, 0, 0))
        self.mask = Image.new("L", (w * ss, h * ss), 0)
        self.d_rgb = ImageDraw.Draw(self.rgb)
        self.d_mask = ImageDraw.Draw(self.mask)

    def result(self):
        ss = self.ss
        rgb = np.asarray(self.rgb, float)
        m = np.asarray(self.mask, float) / 255.0
        H, W = m.shape
        h, w = H // ss, W // ss
        pm = (rgb * m[..., None]).reshape(h, ss, w, ss, 3).mean((1, 3))  # premultiplied
        a = m.reshape(h, ss, w, ss).mean((1, 3))
        col = np.where(a[..., None] > 1e-4, pm / np.maximum(a[..., None], 1e-4), 0)
        out = np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8)
        out[out[..., 3] < 6] = 0
        ys, xs = np.nonzero(out[..., 3] > 0)
        if len(ys) == 0:
            return out[:2, :2]
        return out[max(ys.min() - 1, 0):ys.max() + 2, max(xs.min() - 1, 0):xs.max() + 2]


def _draw_blade(cv, rng, base, a0, L, W, colour, curv, droop, twist, wobble=0.0, lanes=7):
    """Draw one blade on canvas cv (supersampled coords handled here). base in final px."""
    ss = cv.ss
    n = max(24, int(L / 3))
    ts = np.linspace(0, 1, n)
    ang = a0 + curv * ts + droop * ts ** 2
    if wobble:
        ang = ang + np.cumsum(rng.normal(0, wobble, n)) / math.sqrt(n) * 2
    step = L / (n - 1)
    # up = -y ; angle measured clockwise from up
    dx = np.sin(ang) * step
    dy = -np.cos(ang) * step
    cx = base[0] + np.concatenate([[0], np.cumsum(dx[:-1])])
    cy = base[1] + np.concatenate([[0], np.cumsum(dy[:-1])])
    nx, ny = np.cos(ang), np.sin(ang)  # unit normal (right of direction)
    # width profile: slight swell near base, long taper to a pointed tip
    prof = np.where(ts < .12, .75 + .25 * ts / .12, 1.0) * (1 - ts ** 2.6) ** 0.8
    prof = np.maximum(prof, 0)
    hw = W / 2 * prof
    # twist: lateral offset of the midrib across the width and slight foreshortening
    tw_phase = rng.uniform(0, 6.28)
    tw = twist * np.sin(ts * rng.uniform(2, 5) + tw_phase)  # -1..1 -> midrib offset
    shade_t = 1.0 + rng.normal(0, 0.03, n).cumsum() * 0.15
    shade_t = np.clip(shade_t, .85, 1.15)
    lane_u = np.linspace(-1, 1, lanes + 1)
    lane_noise = rng.normal(0, 0.035, lanes)
    tipc = np.array([225, 215, 140.0]) if colour.mean() < 160 else np.array([235, 225, 170.0])
    for i in range(n - 1):
        t = ts[i]
        wid_scale = 1 - 0.25 * abs(tw[i])  # foreshortened when twisted
        for k in range(lanes):
            u0, u1 = lane_u[k], lane_u[k + 1]
            um = (u0 + u1) / 2
            # distance from midrib (shifted by twist), 0 centre .. 1 edge
            dm = abs(um - 0.5 * tw[i])
            dm = min(dm / (1 + 0.5 * abs(tw[i])), 1)
            lum = 0.72 + 0.30 * (1 - dm ** 1.5)          # darker edges
            lum += 0.14 * math.exp(-(um - 0.5 * tw[i]) ** 2 / 0.012)  # lighter midrib
            lum *= shade_t[i] * (1 + lane_noise[k]) * (1 + 0.035 * math.sin(t * 90 + k))  # veins/noise
            c = colour * lum
            tr = t ** 2.2 * 0.35                            # translucency/lightening to tip
            c = c * (1 - tr) + tipc * tr * (0.6 + 0.4 * lum)
            c = tuple(int(v) for v in np.clip(c, 0, 255))
            def pt(j, u):
                w_ = hw[j] * wid_scale
                return ((cx[j] + nx[j] * u * w_) * ss, (cy[j] + ny[j] * u * w_) * ss)
            e = 0.02  # slight overlap to avoid seams
            poly = [pt(i, u0 - e), pt(i + 1, u0 - e), pt(i + 1, u1 + e), pt(i, u1 + e)]
            cv.d_rgb.polygon(poly, fill=c)
            al = int(255 * (1 - 0.25 * t ** 3))
            cv.d_mask.polygon(poly, fill=al)
    return cx, cy


def make_blade(seed, length=None, width=None, family=None, bend=None, droop=None,
               twist=None, orientation=None, supersample=4):
    """One blade. length 40-260 px, width 2-10 px (final px). Returns RGBA uint8."""
    rng = np.random.default_rng(seed)
    family = _pick_family(rng, family)
    L = length if length is not None else float(rng.uniform(40, 260) ** 1.0)
    W = width if width is not None else float(rng.uniform(3, 10))
    W = min(W, max(L / 7, 2.5))
    curv = bend if bend is not None else rng.normal(0, 0.45)
    dr = droop if droop is not None else rng.normal(0, 0.7) * rng.uniform(0, 1)
    tw = twist if twist is not None else rng.uniform(-0.8, 0.8)
    a0 = orientation if orientation is not None else rng.uniform(0, 2 * math.pi)
    colour = _jitter_colour(rng, family)
    pad = int(L * 1.3 + 12)
    cv = _Canvas(2 * pad, 2 * pad, supersample)
    _draw_blade(cv, rng, (pad, pad), a0, L, W, colour, curv, dr, tw)
    return cv.result()


def make_tuft(seed, n_blades=None, size=None, family=None, supersample=4):
    """Fan of 3-12 blades from a common base; long side ~ size (60-200 px)."""
    rng = np.random.default_rng(seed)
    n = n_blades if n_blades is not None else int(rng.integers(3, 13))
    size = size if size is not None else float(rng.uniform(60, 200))
    fam = _pick_family(rng, family)
    spread = rng.uniform(0.5, 1.1)
    lean = rng.normal(0, 0.25)
    pad = int(size * 1.4 + 12)
    cv = _Canvas(2 * pad, 2 * pad, supersample)
    base = (pad, pad)
    items = []
    for _ in range(n):
        a0 = lean + rng.uniform(-spread, spread)
        L = size * rng.uniform(0.55, 1.0) * (1 - 0.25 * abs(a0))
        items.append((abs(a0), a0, L))
    for _, a0, L in sorted(items, reverse=True):  # outer first, central blades on top
        f = fam if rng.random() < .8 else _pick_family(rng)
        col = _jitter_colour(rng, f)
        W = float(np.clip(rng.uniform(2, 7) * (L / 120) ** .5, 1.6, 9))
        bx = base[0] + rng.normal(0, size * .02)
        _draw_blade(cv, rng, (bx, base[1]), a0, L, W, col, rng.normal(0, .4) + a0 * .5,
                    rng.normal(0, .6) * rng.uniform(0, 1), rng.uniform(-.7, .7))
    return cv.result()


def make_wisp(seed, size=None, kind=None, family=None, supersample=4):
    """Dry-grass strands / litter wisp. kind=None keeps the original behaviour (seed-stable);
    otherwise kind in {"strands","curved","tangle","stubble","hair"}.
    Colours: straw/tan/olive/brown mostly, occasionally green."""
    rng = np.random.default_rng(seed)
    if kind is None:
        size = size if size is not None else float(rng.uniform(50, 200))
        pad = int(size * 1.2 + 12)
        cv = _Canvas(2 * pad, 2 * pad, supersample)
        base_dir = rng.uniform(0, 6.28)
        fam = "straw" if rng.random() < .55 else "tan"
        for _ in range(int(rng.integers(3, 9))):
            L = size * rng.uniform(.3, 1.0)
            f = fam if rng.random() < .8 else "olive"
            col = _jitter_colour(rng, f) * rng.uniform(.9, 1.05)
            W = float(rng.uniform(1.4, 3.2))
            start = (pad + rng.normal(0, size * .12), pad + rng.normal(0, size * .12))
            _draw_blade(cv, rng, start, base_dir + rng.normal(0, .55), L, W, col,
                        rng.normal(0, .8), rng.normal(0, .9), rng.uniform(-.5, .5), wobble=0.35, lanes=3)
        return cv.result()
    famp = {"straw": .32, "tan": .22, "olive": .18, "brown": .18, "green": .10}
    def pickf():
        if family: return family
        ks = list(famp); return ks[rng.choice(len(ks), p=[famp[k] for k in ks])]
    size = size if size is not None else float(rng.uniform(40, 200) if kind != "stubble" else rng.uniform(25, 70))
    pad = int(size * 1.3 + 12)
    cv = _Canvas(2 * pad, 2 * pad, supersample)
    d0 = rng.uniform(0, 6.28); fam = pickf()
    def col(f=None):
        return _jitter_colour(rng, f or (fam if rng.random() < .75 else pickf())) * rng.uniform(.9, 1.05)
    if kind == "strands":      # a few roughly parallel dry strands
        for _ in range(int(rng.integers(2, 5))):
            _draw_blade(cv, rng, (pad + rng.normal(0, size * .1), pad + rng.normal(0, size * .1)), d0 + rng.normal(0, .25),
                        size * rng.uniform(.5, 1), float(rng.uniform(1.5, 3.0)), col(), rng.normal(0, .5), rng.normal(0, .6),
                        rng.uniform(-.4, .4), wobble=0.2, lanes=3)
    elif kind == "curved":     # 1-3 long thin strongly curved wisps
        for _ in range(int(rng.integers(1, 4))):
            sg = rng.choice([-1, 1])
            _draw_blade(cv, rng, (pad + rng.normal(0, size * .08), pad + rng.normal(0, size * .08)), d0 + rng.normal(0, .3),
                        size * rng.uniform(.6, 1), float(rng.uniform(1.1, 2.4)), col(), sg * rng.uniform(.9, 2.0),
                        sg * rng.uniform(0, 1.2), rng.uniform(-.3, .3), wobble=0.15, lanes=3)
    elif kind == "tangle":     # 2-5 strands crossing at different angles
        for _ in range(int(rng.integers(2, 6))):
            _draw_blade(cv, rng, (pad + rng.normal(0, size * .22), pad + rng.normal(0, size * .22)), rng.uniform(0, 6.28),
                        size * rng.uniform(.4, .9), float(rng.uniform(1.3, 3.0)), col(), rng.normal(0, 1.0), rng.normal(0, .8),
                        rng.uniform(-.5, .5), wobble=0.4, lanes=3)
    elif kind == "stubble":    # short cut stems / blade stubs clustered together
        for _ in range(int(rng.integers(5, 15))):
            _draw_blade(cv, rng, (pad + rng.normal(0, size * .22), pad + rng.normal(0, size * .22)), d0 + rng.normal(0, .5),
                        size * rng.uniform(.15, .45), float(rng.uniform(1.6, 3.4)), col(), rng.normal(0, .3), rng.normal(0, .3),
                        rng.uniform(-.3, .3), lanes=3)
    elif kind == "hair":       # fine hair-like grass, near parallel, gently curved
        cu = rng.normal(0, .6)
        for _ in range(int(rng.integers(6, 15))):
            _draw_blade(cv, rng, (pad + rng.normal(0, size * .06), pad + rng.normal(0, size * .06)), d0 + rng.normal(0, .35),
                        size * rng.uniform(.6, 1.0), float(rng.uniform(0.9, 1.4)), col(), cu + rng.normal(0, .25),
                        rng.normal(0, .5), 0.0, wobble=0.12, lanes=3)
    else:
        raise ValueError(kind)
    return cv.result()


if __name__ == "__main__":
    import json, os, sys
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "grassBlades")
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".png"):
            os.remove(os.path.join(out, f))
    man = []
    jobs = [("blade", 60, make_blade), ("tuft", 25, make_tuft), ("wisp", 10, make_wisp)]
    WK = ["strands", "curved", "tangle", "stubble", "hair"]
    for kind, cnt, fn in jobs:
        for i in range(cnt):
            seed = 1000 * (jobs.index((kind, cnt, fn)) + 1) + i
            kw = {}
            if kind == "blade":  # spread colour families evenly for the pool
                kw["family"] = list(FAMILIES)[i % 4] if i % 5 else None
            a = fn(seed, **kw)
            name = f"{kind}_{i:02d}.png"
            Image.fromarray(a, "RGBA").save(os.path.join(out, name), optimize=True)
            man.append([name, f"procedural seed {seed}", [a.shape[1], a.shape[0]]])
    for i in range(10, 50):  # extra varied wisps (wisp_00-09 stay as before)
        kind = WK[i % 5]; seed = 3000 + i
        a = make_wisp(seed, kind=kind)
        name = f"wisp_{i:02d}.png"
        Image.fromarray(a, "RGBA").save(os.path.join(out, name), optimize=True)
        man.append([name, f"procedural {kind} seed {seed}", [a.shape[1], a.shape[0]]])
    json.dump(man, open(os.path.join(out, "..", "tools", "grassBlades_manifest.json"), "w"))
    print(len(man))
