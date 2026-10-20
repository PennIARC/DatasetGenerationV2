#!/usr/bin/env python3
"""Build the "Dataset v2: parameters" showcase tab (zoomed 640x640 revision, ADR 0016): one card per sampled parameter
with a distribution graph drawn from the 3000-row sampling PLAN (output_dataset/v2_3000/plan, made by scripts/generate_dataset.py --plan-only), plus
before / after renders (render_scene, same seed, one parameter changed) and a few planned rows rendered as samples.

    python3 docs/showcase/showcase_scripts/params/build_params.py            # graphs + renders + manifest
    python3 docs/showcase/showcase_scripts/params/build_params.py --no-render  # graphs + manifest only

Writes docs/showcase/images/params/*.png|jpg (gitignored, regenerable) and docs/showcase/manifest_params.json.
"""
import argparse
import csv
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SHOW = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(os.path.dirname(SHOW))
sys.path.insert(0, os.path.join(REPO, "DatasetGenerator"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import generate_dataset as G  # noqa: E402

IMG = os.path.join(SHOW, "images", "params")
REL = "images/params/"
PLAN = os.path.join(REPO, "output_dataset", "v2_3000", "plan")
PLANNED = "Planned distribution from the 3000-row sampling plan (dataset not yet generated)."

# reference palette (dataviz skill, light mode)
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False})


# ------------------------------------------------------------------------------------------------ data
def read_csv(name):
    with open(os.path.join(PLAN, name)) as f:
        return list(csv.DictReader(f))


def col(rows, k, cast=float, where=None):
    out = []
    for r in rows:
        if where and not where(r):
            continue
        v = r[k]
        if v in ("", "None"):
            continue
        out.append(cast(v) if cast is not bool else v == "True")
    return np.array(out)


# ------------------------------------------------------------------------------------------------ plots
def _legend_below(ax):
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8)


def _save(fig, name):
    p = os.path.join(IMG, name)
    fig.savefig(p, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return REL + name


def plot_stratified(name, values, edges, xlabel, title, unit="images", sub=4, logx=False, labels=None, note=None):
    """Fine histogram (sub sub-bins per bucket), bucket edges dashed, equal-count target line per sub-bin."""
    edges = np.asarray(edges, float)
    fine = np.concatenate([(np.geomspace if logx else np.linspace)(edges[i], edges[i + 1], sub + 1)[:-1]
                           for i in range(len(edges) - 1)] + [edges[-1:]])
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.hist(values, bins=fine, color=C1, edgecolor=SURF, linewidth=1.5, label=f"planned {unit} per sub-bin")
    cnt = np.histogram(values, bins=edges)[0]
    target = len(values) / (len(edges) - 1) / sub
    ax.axhline(target, color=C2, ls="--", lw=1.8, label=f"equal-count target ({target:.0f} per sub-bin)")
    for e in edges:
        ax.axvline(e, color=INK2, ls=":", lw=1.2)
    ymax = ax.get_ylim()[1]
    for i in range(len(edges) - 1):
        mid = np.sqrt(edges[i] * edges[i + 1]) if logx else (edges[i] + edges[i + 1]) / 2
        tag = (labels[i] + "\n") if labels else ""
        ax.text(mid, ymax * 1.02, f"{tag}bucket {i}: n={cnt[i]}", ha="center", va="bottom", fontsize=8, color=INK2)
    if logx:
        ax.set_xscale("log")
        ax.set_xticks(edges)
        ax.set_xticklabels([f"{e:.3g}" for e in edges])
        ax.minorticks_off()
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"{unit} (count)")
    ax.set_title(title, loc="left", fontsize=11, pad=22)
    _legend_below(ax)
    if note:
        fig.text(0.0, -0.04, note, fontsize=8, color=INK2)
    return _save(fig, name)


def plot_bar(name, cats, counts, xlabel, title, unit="images", target=None, target_label=None, rot=0):
    many = len(cats) > 20
    fig, ax = plt.subplots(figsize=(11, 4.4) if many else (7.2, 3.0))
    x = np.arange(len(cats))
    ax.bar(x, counts, color=C1, edgecolor=SURF, linewidth=0.5 if many else 2, width=0.8)
    if not many:
        for xi, c in zip(x, counts):
            ax.text(xi, c, f"{int(c)}", ha="center", va="bottom", fontsize=8, color=INK2)
    if target is not None:
        t = np.broadcast_to(np.asarray(target, float), (len(cats),))
        ax.step(np.r_[x - 0.5, x[-1] + 0.5], np.r_[t, t[-1]], where="post", color=C2, ls="--", lw=1.8,
                label=target_label or "target")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.5 if rot else -0.34), ncol=1, fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=rot, ha="right" if rot else "center",
                       fontsize=6 if many else (8 if rot else 9))
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"{unit} (count)")
    ax.set_title(title, loc="left", fontsize=11)
    return _save(fig, name)


def plot_random(name, values, xlabel, title, unit="images", bins=30, rng_lim=None, ref=None, ref_label=None,
                logy=False, discrete=False, note=None):
    """Randomized parameter: histogram + optional reference (e.g. the expected count of the configured
    distribution)."""
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    if discrete:
        lo, hi = int(np.min(values)), int(np.max(values))
        b = np.arange(lo - 0.5, hi + 1.5)
    else:
        b = np.linspace(*(rng_lim or (np.min(values), np.max(values))), bins + 1)
    ax.hist(values, bins=b, color=C1, edgecolor=SURF, linewidth=1.0, label=f"planned {unit}")
    if ref is not None:
        ax.axhline(ref, color=C2, ls="--", lw=1.8, label=ref_label)
    if rng_lim is not None:
        for e in rng_lim:
            ax.axvline(e, color=INK2, ls=":", lw=1.2)
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"{unit} (count{', log scale' if logy else ''})")
    ax.set_title(title, loc="left", fontsize=11)
    _legend_below(ax)
    if note:
        fig.text(0.0, -0.05, note, fontsize=8, color=INK2)
    return _save(fig, name)


def plot_two(name, a, b, la, lb, xlabel, title, unit="images", bins=30, rng_lim=None):
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    bb = np.linspace(*(rng_lim or (min(a.min(), b.min()), max(a.max(), b.max()))), bins + 1)
    ax.hist(a, bins=bb, color=C1, alpha=0.85, label=la, histtype="stepfilled", edgecolor=SURF)
    ax.hist(b, bins=bb, color=C2, lw=2.0, label=lb, histtype="step")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"{unit} (count)")
    ax.set_title(title, loc="left", fontsize=11)
    _legend_below(ax)
    return _save(fig, name)


def plot_small_multiples(name, series, title, unit="images"):
    """series: [(values, xlabel, (lo, hi))] -> one panel each, shared style."""
    fig, axs = plt.subplots(1, len(series), figsize=(7.4, 2.8), sharey=True)
    for ax, (v, xl, lim) in zip(np.atleast_1d(axs), series):
        ax.hist(v, bins=np.linspace(lim[0], lim[1], 21), color=C1, edgecolor=SURF, linewidth=1.0)
        ax.set_xlabel(xl)
    np.atleast_1d(axs)[0].set_ylabel(f"{unit} (count)")
    fig.suptitle(title, x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    return _save(fig, name)


# ------------------------------------------------------------------------------------------------ renders
DEMO_SEED, DEMO_INDEX = 11, 0
BASE = {"N_MINES": 1, "MINE_POSITIONS": [(960, 540)], "mine_scale": 0.3, "BURIAL_PROB": 0.0, "flip": False,
        "OVERCAST_PROB": 0.0, "SUN_ELEVATION": 40.0, "SUN_AZIMUTH": 135.0, "SHADOW_STRENGTH": 0.45,
        "PSF_SIGMA": 0.4, "MOTION_BLUR_PROB": 0.0, "MINE_POSE": (3.0, 2.0, 30.0, False), "BLADES_OVER_ON_MINE": 0.0,
        "BG_FAMILY_WEIGHTS": {"grass": 1.0}, "SCENE_ZOOM_COUPLING": True}
# before / after renders use the dataset's zoom coupling (scale 0.3 -> zoom 1.5) on the full frame with the mine at the
# centre and show a native 640x640 window around it (= the dataset's crop size; no resize)


def crop(rgb, spec):
    """spec: ("mine", half, zoom) native crop around the centre (zoom = nearest-neighbour upscale, 1 = native);
    ("frame", f) whole frame downscaled by f (only for frame-wide effects, stated in the caption)."""
    import cv2
    if spec[0] == "frame":
        h, w = rgb.shape[:2]
        return cv2.resize(rgb, (int(w / spec[1]), int(h / spec[1])), interpolation=cv2.INTER_AREA)
    _, half, zoom = spec
    c = rgb[540 - half:540 + half, 960 - half:960 + half]
    if zoom != 1:
        c = cv2.resize(c, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
    return c


def render_pair(key, before_ov, after_ov, spec, jpeg=(95, 95), seed=DEMO_SEED, index=DEMO_INDEX):
    import cv2
    from features.camera import jpeg_roundtrip
    from scene import render_scene
    outs = []
    for tag, ov, q in (("before", before_ov, jpeg[0]), ("after", after_ov, jpeg[1])):
        full = {**BASE, **ov}
        rgb, labels, meta = render_scene(seed, full, index=index)
        rgb = jpeg_roundtrip(rgb, q)
        name = f"{key}_{tag}.png"
        cv2.imwrite(os.path.join(IMG, name), cv2.cvtColor(crop(rgb, spec), cv2.COLOR_RGB2BGR))
        outs.append(REL + name)
    return outs


def spec_text(spec):
    if spec[0] == "frame":
        return f"whole 1920x1080 render (before the 640x640 crop) shown at 1/{spec[1]} size"
    s = 2 * spec[1]
    return f"native-resolution {s}x{s} px crop around the mine" + (f", {spec[2]}x nearest-neighbour zoom" if spec[2] != 1 else "")


# ------------------------------------------------------------------------------------------------ cards
def build_cards(imgs, mines, meta, do_render):
    E = meta["edges"]
    N = len(imgs)
    n_mines_total = len(mines)
    buried = [m for m in mines if m["buried"] == "True"]
    direct = lambda r: r["overcast"] == "False"  # noqa: E731
    cards = []

    def card(cid, title, flag, kind, buckets, rng_txt, dist, what, graph, ba=(), notes="", extra_facts=()):
        cards.append({"cid": cid, "title": title, "flag": flag, "kind": kind, "buckets": buckets, "range": rng_txt,
                      "dist": dist, "what": what, "graph": graph, "ba": list(ba), "notes": notes,
                      "extra_facts": list(extra_facts)})

    def BA(key, label, bov, aov, bl, al, spec, caption, jpeg=(95, 95)):
        if not do_render:
            return {"label": label, "before": REL + f"{key}_before.png", "after": REL + f"{key}_after.png",
                    "before_label": bl, "after_label": al, "caption": caption + " " + spec_text(spec) + "."}
        b, a = render_pair(key, bov, aov, spec, jpeg)
        print("rendered", key, flush=True)
        return {"label": label, "before": b, "after": a, "before_label": bl, "after_label": al,
                "caption": caption + " " + spec_text(spec) + f"; seed {DEMO_SEED}, one mine at the centre."}

    M = ("mine", 320, 1)
    Z = ("mine", 70, 3)
    # ---------------------------------------------------------------- stratified
    nm = col(imgs, "n_mines", int)
    q = meta["factors"]["n_mines"]["quota"]
    card("n_mines", "Mines per image", "N_MINES", "stratified", "5 (0..4)", "0-4 mines",
         "Exact quota: 600 images (20 %) with 0 mines and 600 with each of 1..4 (user decision for the zoomed "
         "640x640 dataset; was 0-8 with 600 / 300 x 8).",
         "How many PFM-1 mines are placed in the 640x640 crop (rejection sampling inside the crop, 50 attempts).",
         plot_bar("n_mines.png", [str(k) for k in range(5)], np.bincount(nm, minlength=5), "mines in the image",
                  "Mines per image (planned)", target=q, target_label="quota (600 each for 0-4)"),
         notes=f"Planned mines in total: {n_mines_total}. 4 mines of up to 171 px fit easily in the 624x624 placement "
               "area; the rendered manifest will record placed vs planned.")
    sc = col(mines, "scale")
    card("mine_scale", "Mine scale (altitude)", "MINE_SCALE_MIN / MINE_SCALE_MAX (per-image bucket)", "stratified",
         "4 linear", "0.25-0.40 (mine length ~107-171 px in the 640x640 crop)",
         "Each image gets one of 4 equal-width buckets (750 images per bucket); every mine in it draws its scale "
         "uniformly inside that bucket, i.e. uniform 0.25-0.40 overall (user decision: was 5 log bins over 0.1-0.4, "
         "where mines were often barely visible).",
         "Mine size in the frame (proxy for flight altitude). The ground blade scale (px per mm) and the zoom "
         "coupling factor (scale / 0.2) come from the same bucket, so grass, rocks, debris and mines agree in scale.",
         plot_stratified("mine_scale.png", sc, E["scale"], "mine scale (x 426.7 = mine length in px)",
                         "Mine scale per mine (planned)", unit="mines"),
         ba=[BA("scale", "Scale 0.25 vs 0.40", {"mine_scale": 0.25}, {"mine_scale": 0.4}, "scale 0.25 (zoom 1.25)",
                "scale 0.40 (zoom 2.0)", M, "Smallest vs largest end of the range, both zoom-coupled.")],
         notes="Per-image buckets mean all mines in one image share a scale range (like one flight altitude). Mine "
               "counts per bucket are exact because the n_mines x scale table is balanced.")
    bf = col(buried, "burial_fraction")
    card("burial_fraction", "Burial fraction (target)", "BURIAL_FRACTION (per-image bucket), BURIAL_PROB 0.35",
         "stratified (fraction) + randomized (buried yes/no)", "4", "0.05-0.50 of the mine's top-down area",
         "Each image gets one of 4 fraction buckets (750 images each); every mine is buried with the tuned "
         "probability 0.35 (random) and, if buried, draws its target fraction inside the image's bucket. Hard cap "
         "BURIAL_MAX_FRACTION 0.5 (render retries if the cap is exceeded).",
         "How much of a buried mine is hidden under soil (3D clip by a tilted ground plane + wavy soil line, berm, "
         "clods).",
         plot_stratified("burial_fraction.png", bf, E["burial_fraction"], "target hidden fraction",
                         f"Target burial fraction of buried mines (planned; {len(bf)} of {n_mines_total} mines "
                         f"buried = {100 * len(bf) / n_mines_total:.1f}%)", unit="buried mines", sub=3),
         ba=[BA("burial_none", "Not buried vs 45% buried", {}, {"BURIAL_PROB": 1.0, "BURIAL_FRACTION": 0.45},
                "not buried", "45% buried", M, "Same mine, fraction 0.45 (top bucket)."),
             BA("burial_low", "15% vs 45% buried", {"BURIAL_PROB": 1.0, "BURIAL_FRACTION": 0.15},
                {"BURIAL_PROB": 1.0, "BURIAL_FRACTION": 0.45}, "15% buried", "45% buried", M,
                "Lowest vs highest bucket.")],
         notes="Buckets are [0.05, 0.2), [0.2, 0.3), [0.3, 0.4), [0.4, 0.5]: the first is wider, so the lightest "
               "burials get slightly less density per 0.01 than in the old uniform 0.05-0.5. The achieved hidden "
               "fraction is measured after rendering (it differs a little from the target). Images per bucket are exact (750); "
               "buried MINES per bucket vary a little (graph) because burial yes / no stays random per mine.")
    el = col(imgs, "sun_elevation")
    card("sun_elevation", "Sun elevation", "SUN_ELEVATION (per-image bucket)", "stratified", "6 (9.2 deg wide)",
         "15-70 deg", "500 images per 9.2-degree bucket, uniform inside the bucket (same overall shape as the "
         "generator's U(15, 70), made exact). Overcast images keep a nominal elevation for mine shading.",
         "Height of the sun: drives shadow length (low sun = long, soft shadows) and mine shading.",
         plot_stratified("sun_elevation.png", el, E["sun_elevation"], "sun elevation (degrees)",
                         "Sun elevation per image (planned)", sub=3),
         ba=[BA("sun_el", "Sun 15 deg vs 70 deg", {"SUN_ELEVATION": 15.0}, {"SUN_ELEVATION": 70.0}, "15 deg",
                "70 deg", M, "Long low-sun shadow vs short noon shadow.")])
    ss = col(imgs, "shadow_strength")
    light = col(imgs, "light", int)
    sh_edges = [0.03, 0.15] + E["shadow_strength"]
    card("light", "Light: overcast and shadow strength", "OVERCAST_PROB (0/1 per image), SHADOW_STRENGTH (bucket)",
         "stratified", "5 (overcast + 4 strength bins)", "overcast 0.03-0.15; direct sun 0.25-0.65",
         "Exactly 450 overcast images (15 %, the user's setting) with weak, very soft shadows (random strength "
         "0.03-0.15); the 2550 direct-sun images are split into 4 equal strength buckets (637-638 each).",
         "How dark shadows are (ground *= 1 - strength x coverage), shared by mines, rocks and grass; mine shading "
         "uses the same value.",
         plot_bar("light.png", ["overcast\n0.03-0.15"] + [f"direct\n{E['shadow_strength'][i]:.2f}-"
                                                          f"{E['shadow_strength'][i + 1]:.2f}" for i in range(4)],
                  np.bincount(light, minlength=5), "light condition (shadow strength range)",
                  "Light condition per image (planned)", target=meta["factors"]["light"]["quota"],
                  target_label="quota (15% overcast, rest split evenly)"),
         ba=[BA("overcast", "Overcast vs strong direct sun", {"OVERCAST_PROB": 1.0}, {"SHADOW_STRENGTH": 0.65},
                "overcast", "direct, strength 0.65", M, "Diffuse sky vs hard sun.")],
         extra_facts=[("strength histogram", f"direct-sun mean {ss[light > 0].mean():.3f}, overcast mean "
                                             f"{ss[light == 0].mean():.3f}")])
    fam = [r["family"] for r in imgs]
    files = {}
    for r in imgs:
        files[r["bg_file"]] = files.get(r["bg_file"], 0) + 1
    card("background", "Background family and file", "BG_FAMILY_WEIGHTS + BG_WEIGHT_OVERRIDES (forced file)",
         "stratified", "2 families; 99 files by quota", "77 grass + 22 non-grass photos",
         "Exact 65 / 35 % family split (1950 grass, 1050 non-grass, the user's 60-70 % grass). Inside a family "
         "every file gets a fixed count proportional to its tuned weight (largest remainder), so the JPEG-blocky "
         "files keep their 0.25 / 0.5 weights and audit 'review' files their 0.4.",
         "Which ground photo is used (then flipped / rotated / zoomed / colour-jittered, see below).",
         plot_bar("background.png", ["grass", "non_grass"], [fam.count("grass"), fam.count("non_grass")],
                  "background family", "Background family per image (planned)",
                  target=[1950, 1050], target_label="quota (65 / 35 %)"),
         notes=f"Per-file counts range {min(files.values())}-{max(files.values())} images "
               f"({len(files)} files used); see the per-file graph in the options of the 'Background files' card.")
    cards[-1]["options"] = [{"label": "images per background file", "image": plot_bar(
        "background_files.png", [k.replace("bg_", "")[:22] for k in sorted(files, key=lambda k: -files[k])],
        sorted(files.values(), reverse=True), "background file (sorted by count)",
        "Planned images per background file (quota by tuned weight)", rot=90),
        "caption": "Counts are fixed by the plan (largest-remainder quotas), not random."}]
    ps = col(imgs, "psf_sigma")
    card("psf_sigma", "Lens blur (PSF sigma)", "PSF_SIGMA (per-image bucket)", "stratified", "3", "0-1.5 px",
         "1000 images per 0.5-px bucket, uniform inside (same shape as the generator's U(0, 1.5), made exact).",
         "Gaussian defocus of the whole composite (point-spread function).",
         plot_stratified("psf_sigma.png", ps, E["psf_sigma"], "Gaussian blur sigma (px, same in the crop)",
                         "Lens blur per image (planned)", sub=4),
         ba=[BA("psf", "Sigma 0 vs 1.5 px", {"PSF_SIGMA": 0.0}, {"PSF_SIGMA": 1.5}, "sigma 0", "sigma 1.5", Z,
                "Sharp vs most blurred.")])
    # ---------------------------------------------------------------- random, image level
    az = col(imgs, "sun_azimuth")
    card("sun_azimuth", "Sun azimuth", "SUN_AZIMUTH", "randomized", "-", "0-360 deg", "Uniform U(0, 360) per image.",
         "Direction the shadows fall; rocks are rotated so their baked-in lit side faces it.",
         plot_random("sun_azimuth.png", az, "sun azimuth (degrees, 0 = towards image right)", "Sun azimuth (planned)",
                     bins=24, rng_lim=(0, 360), ref=N / 24, ref_label="uniform expectation per 15-deg bin"),
         ba=[BA("sun_az", "Azimuth 0 vs 180 deg", {"SUN_AZIMUTH": 0.0}, {"SUN_AZIMUTH": 180.0}, "0 deg", "180 deg",
                M, "Shadow flips side.")],
         notes="Randomized: azimuth is a nuisance factor and background flips / 90-degree rotations already spread "
               "it; 3000 uniform draws fill every 15-degree bin (see graph).")
    card("shadow_tint", "Shadow cool tint", "SHADOW_COOL_TINT", "randomized", "-", "0-0.15", "Uniform per image.",
         "Shadows lose more red than blue (sky-lit shadows look bluish).",
         plot_random("shadow_tint.png", col(imgs, "shadow_tint"), "cool tint amount", "Shadow tint (planned)",
                     bins=20, rng_lim=(0, 0.15), ref=N / 20, ref_label="uniform expectation"),
         ba=[BA("tint", "Tint 0 vs 0.15", {"SHADOW_COOL_TINT": 0.0, "SHADOW_STRENGTH": 0.65},
                {"SHADOW_COOL_TINT": 0.15, "SHADOW_STRENGTH": 0.65}, "tint 0", "tint 0.15", M,
                "Strong shadow so the tint is visible.")])
    mp = col(imgs, "motion_px")
    card("motion_blur", "Motion blur", "MOTION_BLUR_PROB, MOTION_BLUR_LENGTH", "randomized", "-",
         "15 % of images, 1-4 px, random angle", "Bernoulli(0.15) per image, then length U(1, 4) px.",
         "Linear smear from camera motion during the exposure.",
         plot_random("motion_blur.png", mp[mp > 0], "motion blur length (px)",
                     f"Motion blur length, images with blur ({(mp > 0).sum()} of {N} = {100 * (mp > 0).mean():.1f}%)",
                     bins=12, rng_lim=(1, 4)),
         ba=[BA("motion", "No motion blur vs 4 px", {}, {"MOTION_BLUR_PROB": 1.0, "MOTION_BLUR_LENGTH": 4.0},
                "none", "4 px", Z, "Longest smear.")])
    for k, flag, lim, what, lo, hi in [
            ("exposure", "EXPOSURE", (0.75, 1.25), "Overall brightness multiplier.", 0.75, 1.25),
            ("gamma", "GAMMA", (0.85, 1.15), "Tone curve rgb ** gamma (mid-tone brightness).", 0.85, 1.15),
            ("saturation", "SATURATION", (0.75, 1.25), "Colour saturation multiplier.", 0.75, 1.25),
            ("contrast", "CONTRAST", (0.95, 1.2), "Contrast around mid-grey (replaces v1's fixed 1.1).", 0.95, 1.2),
            ("vignette", "VIGNETTE", (0.0, 0.5), "Corner darkening.", 0.0, 0.5),
            ("aberration", "ABERRATION", (0.0, 0.002), "Chromatic aberration: R / B shift in units of the 1920 px "
             "render width (0.002 = 3.8 px; the crop keeps the pixel shift).", 0.0, 0.002)]:
        v = col(imgs, k)
        spec = ("frame", 3) if k == "vignette" else (Z if k == "aberration" else M)
        card(k, k.capitalize() if k != "aberration" else "Chromatic aberration", flag, "randomized", "-",
             f"{lim[0]}-{lim[1]}", "Uniform per image (PHOTOMETRIC_JITTER).", what,
             plot_random(f"{k}.png", v, k, f"{k.capitalize()} (planned)", bins=20, rng_lim=lim, ref=N / 20,
                         ref_label="uniform expectation"),
             ba=[BA(k, f"{k} {lo} vs {hi}", {flag: lo}, {flag: hi}, f"{lo}", f"{hi}", spec, "Range ends.")])
    card("white_balance", "White balance (R and B gains)", "WB_GAIN", "randomized", "-", "0.92-1.08 each",
         "Independent uniform R and B gains per image (G = 1).", "Colour cast of the camera (warm / cool).",
         plot_two("white_balance.png", col(imgs, "wb_r"), col(imgs, "wb_b"), "red gain", "blue gain", "gain",
                  "White-balance gains (planned)", bins=16, rng_lim=(0.92, 1.08)),
         ba=[BA("wb", "Cool vs warm cast", {"WB_GAIN": (0.92, 0.92)}, {"WB_GAIN": (1.08, 1.08)}, "R, B = 0.92",
                "R, B = 1.08", M, "Both gains at the range ends.")],
         notes="The before / after sets both gains together; in the dataset they are independent.")
    card("noise", "Sensor noise", "NOISE_SIGMA, NOISE_CHROMA", "randomized", "-", "sigma 0-0.025, chroma 0-0.5",
         "Uniform per image.", "Zero-mean Gaussian sensor noise; chroma = share that differs per channel.",
         plot_small_multiples("noise.png", [(col(imgs, "noise_sigma"), "noise sigma", (0, 0.025)),
                                            (col(imgs, "noise_chroma"), "noise chroma share", (0, 0.5))],
                              "Sensor noise (planned)"),
         ba=[BA("noise", "Noise 0 vs 0.025", {"NOISE_SIGMA": 0.0}, {"NOISE_SIGMA": 0.025, "NOISE_CHROMA": 0.5},
                "sigma 0", "sigma 0.025, chroma 0.5", Z, "Range ends.")])
    jq = col(imgs, "jpeg_quality", int)
    card("jpeg_quality", "JPEG quality", "JPEG_QUALITY_RANGE", "randomized", "-", "70-95",
         "Uniform integer per image; main.py saves the JPEG at this quality (compression is an augmentation).",
         "JPEG compression strength of the saved file (blocking / ringing at low quality).",
         plot_random("jpeg_quality.png", jq, "JPEG quality", "JPEG quality (planned)", discrete=True,
                     ref=N / 26, ref_label="uniform expectation (26 values)"),
         ba=[BA("jpeg", "Quality 70 vs 95", {}, {}, "q70", "q95", Z, "Same render, saved at 70 vs 95.",
                jpeg=(70, 95))],
         notes="DECISION: the brief asked for q95 files. The generator instead samples 70-95 per image; the driver "
               "keeps that by default (--jpeg-quality sampled) and can force q95 with --jpeg-quality 95.")
    flips = [f"{'H' if r['bg_flip_h'] == 'True' else '-'}{'V' if r['bg_flip_v'] == 'True' else '-'} r{r['bg_rot90']}"
             for r in imgs]
    cats = sorted(set(flips))
    card("bg_flip_rot", "Background flips and 90-degree rotations", "BG_FLIP_PROB, BG_ROT90_PROB", "randomized", "-",
         "flip H / V each p=0.5; rotate by 90/180/270 with p=0.5", "Independent Bernoulli draws per image.",
         "Geometric augmentation of the ground photo (16 combinations).",
         plot_bar("bg_flip_rot.png", cats, [flips.count(c) for c in cats],
                  "flip H / flip V / rotation (multiples of 90 deg)", "Background flip / rotation (planned)", rot=45))
    mag = col(imgs, "bg_magnification")
    card("bg_zoom", "Background zoom", "BG_ZOOM x zoom coupling (SCENE_ZOOM_BG, SCENE_ZOOM_BG_MAX_MAG)", "randomized",
         "-", "BG_ZOOM 1.0-2.0, then x mine scale / 0.2, capped at 1.5 output px per source px",
         "Uniform BG_ZOOM per image, random offset; zoom coupling multiplies it by z (camera closer), but the "
         "magnification (output px per photo px) is capped at max(1.5, uncoupled value) so the texture does not "
         "get blurrier than the generator already allowed; upscaling uses bicubic interpolation.",
         "Zoom-crop into the ground photo on top of scale-to-cover (texture scale).",
         plot_random("bg_zoom.png", mag, "background magnification (output px per source px, log y)",
                     f"Background magnification after zoom coupling (planned; {int((col(imgs, 'bg_mag_capped', bool)).sum())} "
                     f"of {N} at the cap)", bins=35, rng_lim=(0.5, 7.5), logy=True,
                     note="Values above 1.5 come from small / 90-degree-rotated photos that are already above the cap "
                          "without coupling (unchanged)."),
         ba=[BA("bgzoom", "Zoom 1.0 vs 2.0", {"BG_ZOOM": 1.0}, {"BG_ZOOM": 2.0}, "1.0", "2.0", ("frame", 3),
                "Ground texture scale.")])
    card("bg_colour", "Background colour jitter", "BG_HUE_SHIFT, BG_SATURATION, BG_BRIGHTNESS, BG_CHANNEL_GAIN",
         "randomized", "-", "hue +-8 deg, sat 0.8-1.2, bright 0.8-1.2, gains 0.95-1.05",
         "Uniform per image.", "Colour variation of the ground photo before anything is drawn on it.",
         plot_small_multiples("bg_colour.png", [(col(imgs, "bg_hue"), "hue shift (deg)", (-8, 8)),
                                                (col(imgs, "bg_sat"), "saturation", (0.8, 1.2)),
                                                (col(imgs, "bg_bright"), "brightness", (0.8, 1.2))],
                              "Background colour jitter (planned)"),
         ba=[BA("bgbright", "Background brightness 0.8 vs 1.2", {"BG_BRIGHTNESS": 0.8}, {"BG_BRIGHTNESS": 1.2},
                "0.8", "1.2", M, "Ground only; the mine is harmonised to the ground's brightness.")])
    card("ground_scale", "Ground scale (px per mm)", "derived from the scale bucket", "stratified (via scale)",
         "4 (same as mine scale)", "0.89-1.42 px/mm",
         "Drawn per image inside the image's mine-scale bucket (not separately planned).",
         "Size of grass blades / tufts / wisps (specified in mm) on screen.",
         plot_stratified("ground_scale.png", col(imgs, "ground_px_per_mm"),
                         [e * 512 / 1.2 / 120 for e in E["scale"]], "ground px per mm",
                         "Ground scale per image (planned)", sub=3),
         notes="In the default generator this value is drawn independently of the mines' scale, so blades could be "
               "drawn at a different 'altitude' than the mines of the same image; the per-image scale bucket keeps "
               "the two within one bucket.")
    # ---------------------------------------------------------------- zoom coupling + native crop (ADR 0016)
    zz = col(imgs, "zoom")
    card("zoom", "Scene zoom coupling (camera closer)", "SCENE_ZOOM_COUPLING, SCENE_ZOOM_REF_SCALE 0.2, "
         "SCENE_ZOOM_COUNT_EXP 2", "stratified (via scale)", "4 (same as mine scale)", "z = 1.25-2.0",
         "z = the image's mine scale / 0.2 (0.2 = the old plan's median scale), so it follows the scale bucket.",
         "Like moving the camera closer: rocks, grass clippings, leaf clumps, dirt snippets and specks are drawn z "
         "times larger and z^2 times rarer (same density per ground area); the mine's contact band, contact AO, berm "
         "lip, exposed-part AO, soil-grain size and soft-grain blur grow by z; the background texture is magnified by "
         "z (capped, see 'Background zoom'). Grass blades are sized in mm and already follow px/mm. Sensor effects "
         "(PSF, motion blur, noise, aberration shift, vignette, JPEG) stay in pixels.",
         plot_stratified("zoom.png", zz, [e / 0.2 for e in E["scale"]], "zoom factor z = scale / 0.2",
                         "Zoom coupling factor per image (planned)", sub=3),
         ba=[BA("zoom_old_new", "Old look vs zoomed look", {"SCENE_ZOOM_COUPLING": False, "mine_scale": 0.2},
                {"mine_scale": 0.3}, "old: scale 0.20, no coupling", "new: scale 0.30, zoom 1.5", M,
                "The old median look vs the middle of the new range (debris counts / sizes differ by design)."),
             BA("zoom_coupling", "Scale 0.40 without vs with coupling", {"SCENE_ZOOM_COUPLING": False,
                                                                          "mine_scale": 0.4},
                {"mine_scale": 0.4}, "scale 0.40, coupling off", "scale 0.40, coupling on (z 2.0)", M,
                "Same mine size: without coupling rocks, clippings and the ground texture keep the old pixel size, "
                "so the mine looks out of scale.")],
         notes="Default OFF in controlPanel (existing seeds and the earlier outputs are bit-identical with it off); "
               "the dataset driver turns it on. Debris count rounding and the crop window use new random streams "
               "R(11) / R(12) / R(13), so no existing stream changes.")
    cx0, cy0 = col(imgs, "crop_x0"), col(imgs, "crop_y0")
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    hb = ax.hist2d(cx0 + 320, cy0 + 320, bins=[32, 18], range=[[0, 1920], [0, 1080]], cmap="Blues")
    fig.colorbar(hb[3], ax=ax, label="images per cell (count)")
    ax.invert_yaxis()
    ax.add_patch(plt.Rectangle((320, 320), 1280, 440, fill=False, ec=C2, lw=1.5, ls="--"))
    ax.text(330, 335, "possible crop centres", color=C2, fontsize=8, va="top")
    ax.set_xlabel("crop centre x in the 1920x1080 render (px)")
    ax.set_ylabel("crop centre y (px)")
    ax.set_title("640x640 crop window position (planned)", loc="left", fontsize=11)
    ax.grid(False)
    card("crop", "Native 640x640 crop", "OUTPUT_CROP (640, 640), CROP_MINE_MARGIN 8", "randomized", "-",
         "window anywhere in the 1920x1080 render",
         "Uniform window position per image (own stream R(11)), drawn before the mines; every mine is then placed "
         "fully inside the window (8 px margin).",
         "The saved image: a 640x640 window cut out of the 1920x1080 render without any resize or resampling. "
         "Labels are converted to the crop's normalised YOLO coordinates (a box crossing the edge would be clipped "
         "and kept only if visible pixels remain inside, the usual label policy; with the margin none do). The camera "
         "model (blur with a context pad, noise, colour, vignette) is applied to the crop as the camera's frame.",
         _save(fig, "crop.png"))
    if do_render:
        crop_demo()
    cards[-1]["ba"] = [{"label": "Render vs saved crop", "before": REL + "crop_full.jpg", "after": REL + "crop_crop.jpg",
                        "before_label": "1920x1080 render (1/3 size, letterboxed), orange = crop window",
                        "after_label": "saved 640x640 image (native pixels), red = YOLO boxes",
                        "caption": "Plan row rendered with OUTPUT_CROP; the full frame on the left is the same scene "
                                   "re-rendered without the crop (mines pinned at the same positions)."}]
    # ---------------------------------------------------------------- random, per mine
    yaw = col(mines, "yaw")
    card("yaw", "Mine yaw (in-plane rotation)", "MINE_POSE (yaw part)", "randomized (per mine)", "-", "0-360 deg",
         "Uniform per mine. Drawn per mine inside the renderer, so it cannot be bucketed by per-image overrides "
         "without a generator change; with " + f"{n_mines_total} mines every 30-degree bin is within a few % of equal.",
         "Rotation of the mine about the vertical axis.",
         plot_random("yaw.png", yaw, "yaw (degrees)", "Mine yaw (planned)", unit="mines", bins=12, rng_lim=(0, 360),
                     ref=len(yaw) / 12, ref_label="equal count per 30-deg bin (12 bins)"),
         ba=[BA("yaw", "Yaw 30 vs 120 deg", {}, {"MINE_POSE": (3.0, 2.0, 120.0, False)}, "30 deg", "120 deg", M,
                "Same mine rotated.")])
    pr = np.abs(np.r_[col(mines, "pitch"), col(mines, "roll")])
    card("pitch_roll", "Mine pitch and roll (tilt)", "TILT_SIGMA, TILT_TAIL_PROB, TILT_TAIL_RANGE, TILT_CAP",
         "randomized (per mine)", "-", "|tilt| up to 30 deg",
         "N(0, 5 deg) with prob 0.95 (capped at 35), else +-U(8, 30) (resting on a rock); skewed flat as tuned.",
         "Tilt of the mine relative to lying flat.",
         plot_random("pitch_roll.png", pr, "|pitch| and |roll| (degrees)", "Mine tilt magnitude (planned)",
                     unit="angles", bins=30, rng_lim=(0, 30), logy=True),
         ba=[BA("tilt", "Flat vs 25 deg pitch", {}, {"MINE_POSE": (25.0, 0.0, 30.0, False)}, "pitch 3, roll 2",
                "pitch 25", M, "Tail of the distribution.")])
    fd = col(mines, "face_down", bool)
    card("face_down", "Face down", "FLIP_PROB", "randomized (per mine)", "-", "yes / no",
         "Bernoulli(0.30) per mine (the user's setting).", "Mine lies on its back (underside towards the camera).",
         plot_bar("face_down.png", ["face up", "face down"], [(~fd).sum(), fd.sum()], "orientation",
                  "Face-down mines (planned)", unit="mines", target=[0.7 * len(fd), 0.3 * len(fd)],
                  target_label="expected (FLIP_PROB 0.30)"),
         ba=[BA("flip", "Face up vs face down", {}, {"MINE_POSE": (3.0, 2.0, 30.0, True)}, "face up", "face down",
                M, "Same pose otherwise.")],
         notes=f"Kept random per mine (realistic mixed orientations in one image); {len(fd)} Bernoulli draws give "
               f"{100 * fd.mean():.1f}% face down.")
    fams = [m["colour_family"] for m in mines]
    names = list(G.make_config().PALETTE)
    w = np.array([G.make_config().PALETTE[n][0] for n in names])
    card("colour_family", "Mine colour family", "PALETTE", "randomized (per mine)", "-", "5 families",
         "Family by weight (olive 0.28, dark green 0.22, khaki 0.15, brown 0.20, tan 0.15), then H, S, V uniform "
         "inside the family's ranges.", "Base plastic colour of the mine.",
         plot_bar("colour_family.png", names, [fams.count(n) for n in names], "palette family",
                  "Mine colour family (planned)", unit="mines", target=w / w.sum() * len(fams),
                  target_label="expected from the weights"),
         ba=[BA("colour", "Olive vs tan albedo", {"MINE_COLOUR": (0.30, 0.33, 0.17)},
                {"MINE_COLOUR": (0.70, 0.60, 0.45)}, "olive", "tan", M, "Two fixed albedos from the palette.")])
    card("colour_hsv", "Mine hue, saturation, value", "PALETTE ranges, BRIGHTNESS_JITTER", "randomized (per mine)",
         "-", "H 18-160 deg, S 0.18-0.65, V 0.15-0.78; brightness x0.85-1.15", "Uniform inside the family ranges.",
         "Fine colour variation inside a family.",
         plot_small_multiples("colour_hsv.png", [(col(mines, "h"), "hue (deg)", (15, 165)),
                                                 (col(mines, "s"), "saturation", (0.15, 0.7)),
                                                 (col(mines, "v"), "value", (0.1, 0.8))],
                              "Mine HSV before bleaching / tint (planned)", unit="mines"))
    bl = col(mines, "bleach")
    card("bleach", "Sun bleaching", "BLEACH_PROB, BLEACH_AMOUNT", "randomized (per mine)", "-",
         "35 % of mines, amount 0-0.6", "Bernoulli(0.35), then U(0, 0.6).",
         "Faded plastic: S *= 1 - 0.6 a, V += 0.3 a (1 - V).",
         plot_random("bleach.png", bl[bl > 0], "bleach amount",
                     f"Sun bleaching, bleached mines ({(bl > 0).sum()} = {100 * (bl > 0).mean():.1f}%)", unit="mines",
                     bins=20, rng_lim=(0, 0.6)),
         ba=[BA("bleach", "No bleach vs 0.6", {"BLEACH_PROB": 0.0}, {"BLEACH_PROB": 1.0, "BLEACH_AMOUNT": 0.6},
                "none", "0.6", M, "Strongest fading.")])
    dt = col(mines, "dirt_tint")
    card("dirt_tint", "Dirt tint", "DIRT_TINT_PROB, DIRT_TINT_AMOUNT", "randomized (per mine)", "-",
         "40 % of mines, 0-0.3", "Bernoulli(0.4), then U(0, 0.3).", "Albedo mixed towards soil brown.",
         plot_random("dirt_tint.png", dt[dt > 0], "dirt tint amount",
                     f"Dirt tint, tinted mines ({(dt > 0).sum()} = {100 * (dt > 0).mean():.1f}%)", unit="mines",
                     bins=15, rng_lim=(0, 0.3)),
         ba=[BA("dtint", "No tint vs 0.3", {"DIRT_TINT_PROB": 0.0}, {"DIRT_TINT_PROB": 1.0, "DIRT_TINT_AMOUNT": 0.3},
                "none", "0.3", M, "Strongest tint.")])
    du = col(mines, "dust_strength")
    card("dust", "Dust on the mine", "DUST_STRENGTH", "randomized (per mine)", "-", "0.25-0.50, mode 0.30",
         f"Triangular(0.25, 0.30, 0.50), mean 0.35 (the user's ~35 %); planned mean {du.mean():.3f}.",
         "Max opacity of the fBm-modulated dust film (local ground colour) on the mine.",
         plot_random("dust.png", du, "max dust opacity", "Dust strength per mine (planned)", unit="mines", bins=25,
                     rng_lim=(0.25, 0.5)),
         ba=[BA("dust", "Dust 0.25 vs 0.50", {"DUST_STRENGTH": 0.25}, {"DUST_STRENGTH": 0.5}, "0.25", "0.50", M,
                "Range ends.")])
    card("grain", "Soil grains and contact band", "GRAIN_DENSITY, CONTACT_BAND_PX, CONTACT_BAND_DARKEN",
         "randomized (per mine)", "-", "grains 0-5 % of mine pixels; band (1.5-4 px) x zoom, darken 0.1-0.3",
         "Uniform per mine; band width, grain size and soft-grain blur are multiplied by the zoom factor.",
         "Soil specks on the mine and the darker band where it meets the ground.",
         plot_small_multiples("grain.png", [(col(mines, "grain_density"), "grain density", (0, 0.05)),
                                            (col(mines, "band_px"), "contact band before zoom (px)", (1.5, 4)),
                                            (col(mines, "band_darken"), "band darkening", (0.1, 0.3))],
                              "Grains and contact band (planned)", unit="mines"),
         ba=[BA("grain", "Grains 0 vs 5 %", {"GRAIN_DENSITY": 0.0}, {"GRAIN_DENSITY": 0.05}, "0", "0.05", Z,
                "Range ends.")])
    bt = col(buried, "burial_tilt")
    card("burial_tilt", "Burial ground-plane tilt", "BURIAL_TILT", "randomized (per buried mine)", "-", "0-25 deg",
         "Uniform per buried mine; direction U(0, 360); soil-line wander scaled with the fraction.",
         "Tilt of the soil plane that clips the mine (shape of the soil line).",
         plot_random("burial_tilt.png", bt, "ground-plane tilt (degrees)", "Burial tilt (planned, buried mines)",
                     unit="buried mines", bins=25, rng_lim=(0, 25), ref=len(bt) / 25, ref_label="uniform expectation"),
         ba=[BA("btilt", "Tilt 0 vs 25 deg", {"BURIAL_PROB": 1.0, "BURIAL_FRACTION": 0.35, "BURIAL_TILT": 0.0},
                {"BURIAL_PROB": 1.0, "BURIAL_FRACTION": 0.35, "BURIAL_TILT": 25.0}, "tilt 0", "tilt 25", M,
                "Fraction 0.35.")])
    spc = col(mines, "specular")
    card("specular", "Specular sheen", "SPECULAR, SPECULAR_EXP", "randomized (per mine)", "-",
         "strength 0-0.12, exponent 8-30", "Uniform per mine.", "Plastic highlight (Blinn-Phong).",
         plot_random("specular.png", spc, "specular strength", "Specular strength (planned)", unit="mines", bins=24,
                     rng_lim=(0, 0.12), ref=len(spc) / 24, ref_label="uniform expectation"),
         ba=[BA("spec", "Sheen 0 vs 0.12", {"SPECULAR": 0.0}, {"SPECULAR": 0.12, "SPECULAR_EXP": 8.0}, "0", "0.12",
                M, "Range ends.")])
    # mine position: drawn at render time; approximate with the planned box sizes and uniform placement
    rng = np.random.default_rng(0)
    L = col(mines, "length_px")
    cx = rng.uniform(8, 632 - 0.8 * L) + 0.4 * L
    cy = rng.uniform(8, 632 - 0.8 * L) + 0.4 * L
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    hb = ax.hist2d(cx, cy, bins=[16, 16], range=[[0, 640], [0, 640]], cmap="Blues")
    fig.colorbar(hb[3], ax=ax, label="mines per cell (count)")
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.set_xlabel("box centre x in the 640x640 crop (px)")
    ax.set_ylabel("box centre y (px)")
    ax.set_title("Mine position in the crop (approximation:\nuniform placement of the planned box sizes)", loc="left",
                 fontsize=11)
    ax.grid(False)
    card("position", "Mine position", "MINE_PLACEMENT_ATTEMPTS, MINE_PLACEMENT_MARGIN, CROP_MINE_MARGIN",
         "randomized (per mine)", "-", "anywhere with the box fully inside the 640x640 crop (8 px margin)",
         "Uniform inside the crop window, rejection sampling against already-placed boxes (50 attempts, 10 px x zoom "
         "overlap margin).",
         "Where the mine lands in the image.", _save(fig, "position.png"),
         notes="Not replicated in the plan (it depends on the rendered silhouette and on the other mines); the graph "
               "is an approximation. Fixing positions (MINE_POSITIONS) would skip the overlap test, so position is "
               "left random; the rendered manifest will give the real distribution.")
    # ---------------------------------------------------------------- random, debris (configured distributions)
    rr = np.random.default_rng(1)
    K = 20000

    def ri(a, b, n=K):
        return rr.integers(a, b + 1, n)
    cfgd = "Configured distribution (drawn inside the renderer, not replicated in the plan; 20000 draws)."
    zc = ("Configured distribution per 1920x1080 render BEFORE zoom coupling (drawn inside the renderer, not "
          "replicated in the plan; 20000 draws). With zoom z = scale / 0.2 (1.25-2.0) the count is multiplied by z^-2 "
          "(stochastic rounding) and sizes by z; about 20 % of the render lands in the 640x640 crop.")
    card("blades", "Grass blades, tufts, wisps", "BLADES_UNDER, BLADES_OVER, BLADE_KIND_PROBS", "randomized", "-",
         "under 20-80, over 15-60 per 1920x1080 render, x z^-2",
         "Uniform integer counts per image; kind blade 0.6 / tuft 0.25 / wisp 0.15. Sizes in mm (follow px/mm).",
         "Thin grass under and over the mines (over-layer blades partly occlude mines; labels use the visible mask).",
         plot_two("blades.png", ri(20, 80).astype(float), ri(15, 60).astype(float), "under the mines",
                  "over the mines", "blades per image", "Grass blade counts per image (configured)", bins=33,
                  rng_lim=(14.5, 80.5)),
         ba=[BA("blades", "No over-layer blades vs 60", {"BLADES_OVER": 0}, {"BLADES_OVER": 60}, "0 over", "60 over",
                M, "Over-layer count only.")], notes=zc)
    on = (rr.random(K) < 0.6) * ri(1, 4)
    card("blades_on_mine", "Blades crossing a mine", "BLADES_OVER_ON_MINE, BLADES_ON_MINE_COUNT", "randomized (per mine)",
         "-", "60 % of mines get 1-4", "Bernoulli(0.6) per mine, then U{1..4}.",
         "Extra over-layer blades centred on the mine box (partial occlusion).",
         plot_bar("blades_on_mine.png", [str(k) for k in range(5)], np.bincount(on, minlength=5),
                  "extra blades on the mine", "Blades crossing each mine (configured)", unit="mines (of 20000)"),
         ba=[BA("bom", "0 vs 4 blades on the mine", {"BLADES_OVER_ON_MINE": 0.0},
                {"BLADES_OVER_ON_MINE": 1.0, "BLADES_ON_MINE_COUNT": 4}, "0", "4", M, "Partial occlusion.")],
         notes=cfgd)
    card("leaf_clumps", "Leaf-litter clumps", "LEAF_CLUMPS_UNDER, LEAF_CLUMPS_OVER, LEAF_CLUMP_SIZE", "randomized", "-",
         "under 2-8, over 0-2 per render, x z^-2; 25-60 px x z", "Uniform integer counts per image.",
         "RGBA leaf-litter clumps, colour-adapted to the ground.",
         plot_bar("leaf_clumps.png", [str(k) for k in range(2, 11)],
                  np.bincount(ri(2, 8) + ri(0, 2), minlength=11)[2:], "clumps per image (under + over)",
                  "Leaf clumps per image (configured)", unit="images (of 20000)"),
         ba=[BA("leaf", "0 vs 8 leaf clumps", {"LEAF_CLUMPS_UNDER": 0, "LEAF_CLUMPS_OVER": 0},
                {"LEAF_CLUMPS_UNDER": 8, "LEAF_CLUMPS_OVER": 2}, "0", "10 (x z^-2)", M, "Range ends.")],
         notes=zc)
    card("rocks", "Rocks", "ROCKS_TO_SPAWN_MIN / MAX, ROCK_OUTPUT_SIZE_MIN / MAX", "randomized", "-",
         "5-20 per layer (two layers) x z^-2, 40-100 px x z", "Uniform integer per layer; under and over layer each draw.",
         "Rock photos with cast and contact shadows.",
         plot_random("rocks.png", (ri(5, 20) + ri(5, 20)).astype(float), "rocks per image (both layers)",
                     "Rocks per image (configured)", unit="images (of 20000)", discrete=True),
         ba=[BA("rocks", "5 vs 20 rocks per layer", {"ROCKS_TO_SPAWN_MIN": 5, "ROCKS_TO_SPAWN_MAX": 5},
                {"ROCKS_TO_SPAWN_MIN": 20, "ROCKS_TO_SPAWN_MAX": 20}, "5 per layer", "20 per layer", M,
                "Range ends (before x z^-2).")],
         notes=zc + " Rocks, grass clippings and dirt are drawn in BOTH debris layers (v1 behaviour), so some "
                      "land on top of mines.")
    card("dirt", "Dirt snippets and specks", "DIRT_SNIPPETS_PER_LAYER, DIRT_RECTS_PER_LAYER", "randomized", "-",
         "2-10 snippets (15-60 px) and 50-200 soft specks (4-12 px) per layer; counts x z^-2, sizes x z",
         "Uniform integer per layer.",
         "Soil clod photos and small soft dirt specks on the ground.",
         plot_random("dirt.png", (ri(2, 10) + ri(2, 10)).astype(float), "dirt snippets per image (both layers)",
                     "Dirt snippets per image (configured)", unit="images (of 20000)", discrete=True), notes=zc)
    card("grass_clippings", "Grass clippings (v1 photos)", "GRASS_IMAGES_TO_SAMPLE, GRASS_CLIPPINGS_PER_IMAGE",
         "randomized", "-", "4 source photos x 5-16 crops per layer (x z^-2), 40-80 px x z", "Uniform integer per photo.",
         "Crops of v1 grass photos scattered as clutter.",
         plot_random("grass_clippings.png", sum(ri(5, 16) for _ in range(8)).astype(float),
                     "grass clippings per image (both layers)", "Grass clippings per image (configured)",
                     unit="images (of 20000)", discrete=True), notes=zc)
    return cards


def _draw_boxes(rgb, labels, W, H, pad=3, thick=2):
    import cv2
    for l in labels:
        _, xc, yc, w, h = l
        x0, y0 = int(round((xc - w / 2) * W)) - pad, int(round((yc - h / 2) * H)) - pad
        cv2.rectangle(rgb, (x0, y0), (x0 + int(round(w * W)) + 2 * pad, y0 + int(round(h * H)) + 2 * pad),
                      (255, 60, 40), thick)
    return rgb


def crop_demo():
    """Render vs saved crop for one plan row: the crop as saved, and the same scene without the crop (mines pinned
    at their placed positions) with the window outlined."""
    import cv2
    from features.camera import jpeg_roundtrip
    from scene import render_scene
    design = G.load_design(os.path.dirname(PLAN))
    r = next(x for x in design if x["n_mines"] == 3 and x["scale_bin"] == 1)
    cfg = G.make_config(G.row_overrides(r))
    rgb, labels, meta = render_scene(G.BASE_SEED, G.compact_overrides(r), index=r["index"], cfg=cfg)
    rgb = _draw_boxes(jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"]), labels, 640, 640)
    cv2.imwrite(os.path.join(IMG, "crop_crop.jpg"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    pos = [(m["rect_full"][0] + m["rect_full"][2] / 2, m["rect_full"][1] + m["rect_full"][3] / 2) for m in meta["mines"]]
    cfg2 = G.make_config({**G.row_overrides(r), "OUTPUT_CROP": None, "MINE_POSITIONS": pos})
    full, _, _ = render_scene(G.BASE_SEED, {}, index=r["index"], cfg=cfg2)
    c = meta["crop"]
    full = full.copy()
    cv2.rectangle(full, (c["x0"], c["y0"]), (c["x0"] + 640, c["y0"] + 640), (235, 104, 52), 6)
    small = cv2.resize(full, (640, 360), interpolation=cv2.INTER_AREA)
    small = np.concatenate([np.full((140, 640, 3), 245, np.uint8), small, np.full((140, 640, 3), 245, np.uint8)], 0)
    cv2.imwrite(os.path.join(IMG, "crop_full.jpg"), cv2.cvtColor(small, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("rendered crop demo", r["index"], flush=True)


def sample_gallery(design, do_render):
    """Render 6 planned rows (in memory) as examples of the plan."""
    import cv2
    from features.camera import jpeg_roundtrip
    from scene import render_scene
    picks, seen = [], set()
    for r in design:
        key = (r["scale_bin"], r["light"] == 0)
        if r["n_mines"] >= 2 and key not in seen:
            seen.add(key)
            picks.append(r)
        if len(picks) == 6:
            break
    opts = []
    for r in picks:
        name = f"sample_row_{r['index']:05d}.jpg"
        if do_render:
            rgb, labels, meta = render_scene(G.BASE_SEED, G.compact_overrides(r), index=r["index"],
                                             cfg=G.make_config(G.row_overrides(r)))
            rgb = _draw_boxes(jpeg_roundtrip(rgb, meta["post"]["jpeg_quality"]), labels, 640, 640)
            cv2.imwrite(os.path.join(IMG, name), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
            print("rendered sample", r["index"], flush=True)
        lo, hi = G.bucket_range(G.SCALE_EDGES, r["scale_bin"])
        opts.append({"label": f"plan row {r['index']} ({r['split']}, scale {lo:.4g}-{hi:.4g})",
                     "params": f"n_mines={r['n_mines']} scale_bin={r['scale_bin']} burial_bin={r['burial_bin']} "
                               f"elev_bin={r['elev_bin']} light={r['light']} family={G.FAMILY_NAMES[r['family']]} "
                               f"psf_bin={r['psf_bin']} bg={r['bg_file']}",
                     "image": REL + name,
                     "caption": "Rendered from the plan row exactly as the dataset would: the native 640x640 crop at "
                                "full size (red = YOLO boxes, drawn 3 px outside). Not part of a generated dataset."})
    return opts


# ------------------------------------------------------------------------------------------------ manifest
def caption_for(c):
    if c["cid"] == "position":
        return "Approximation from the planned box sizes (positions are decided at render time)."
    if "Configured distribution" in c["notes"]:
        return "Configured distribution from controlPanel (drawn inside the renderer, not in the plan table)."
    extra = (" Dotted lines: bucket edges; dashed orange: equal-count target." if c["kind"].startswith("strat") and
             c["cid"] not in ("n_mines", "light", "background") else "")
    return PLANNED + extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()
    os.makedirs(IMG, exist_ok=True)
    imgs, mines = read_csv("plan_images.csv"), read_csv("plan_mines.csv")
    with open(os.path.join(PLAN, "plan.json")) as f:
        meta = json.load(f)
    with open(os.path.join(PLAN, "plan_design.json")) as f:
        design = json.load(f)
    do_render = not args.no_render
    cards = build_cards(imgs, mines, meta, do_render)

    # split balance graph: val share per level of every stratified factor
    labs, shares = [], []
    for fac, d in meta["counts"].items():
        for lvl, n in d.items():
            labs.append(f"{fac}={lvl}")
            shares.append(100 * meta["val_counts"][fac][lvl] / n)
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.bar(np.arange(len(labs)), shares, color=C1, edgecolor=SURF, linewidth=1.0)
    ax.axhline(10, color=C2, ls="--", lw=1.8, label="target 10 %")
    ax.set_xticks(np.arange(len(labs)))
    ax.set_xticklabels(labs, rotation=90, fontsize=6.5)
    ax.set_ylabel("val share of the level (%)")
    ax.set_xlabel("factor = bucket")
    ax.set_ylim(0, 14)
    ax.set_title("Validation share per bucket of every stratified factor (planned)", loc="left", fontsize=11)
    ax.legend(loc="upper right", fontsize=8, framealpha=1, frameon=True)
    split_png = _save(fig, "split_balance.png")

    features = []
    gallery = sample_gallery(design, do_render)
    sp = meta["split"]
    features.append({"id": "split", "title": "Train / val split", "flag": "split column of the plan",
                     "summary": f"{sp['train']} train / {sp['val']} val images (90 / 10), chosen by seed index. The "
                                "split is a balanced design column: every bucket of every stratified factor has 10 % "
                                "of its images in val. Val and train indices never overlap (one image = one index; "
                                f"retries use spare indices {G.SPARE_INDEX0}+, unique per row).",
                     "facts": [["type", "stratified (balanced column)"], ["counts", f"train {sp['train']}, val {sp['val']}"],
                               ["balance", f"split-vs-factor chi-square {meta['balance']['chi2_split_before']} -> "
                                           f"{meta['balance']['chi2_split_after']} after the swap search"]],
                     "figure": {"image": split_png, "label": "val share per bucket", "caption": PLANNED}})
    features.append({"id": "samples", "title": "Planned rows rendered (examples)", "flag": "render_scene(2026, k)",
                     "summary": "Six plan rows with different scale buckets and light conditions, rendered in memory "
                                "with their overrides (640x640 native crops, zoom coupling on) to show what the plan "
                                "produces. No dataset images were written.",
                     "options": gallery})
    for c in cards:
        f = {"id": c["cid"], "title": c["title"], "flag": c["flag"], "summary": c["what"],
             "facts": [["type", c["kind"]], ["buckets", c["buckets"] if c["buckets"] != "-" else "none (randomized)"],
                       ["range", c["range"]], ["distribution", c["dist"]], ["override / config", c["flag"]]]
                      + [list(x) for x in c["extra_facts"]],
             "figure": {"image": c["graph"], "label": c["title"],
                        "caption": caption_for(c)}}
        if c["ba"]:
            f["before_after"] = c["ba"]
        if c.get("options"):
            f["options"] = c["options"]
        if c["notes"]:
            f["notes"] = c["notes"]
        features.append(f)

    overview = [[c["title"], c["kind"], c["buckets"] if c["buckets"] != "-" else "randomized", c["range"], c["flag"]]
                for c in cards]
    b = meta["balance"]
    nm_tot, nb_tot = meta["n_mines_planned"], meta["n_buried_planned"]
    decisions = [
        ["Image format / resolution (NEW)", "640x640 JPEG as a NATIVE crop of the 1920x1080 render (no resize, no "
         "resampling); the window position is uniform and every mine is placed fully inside it (8 px margin); labels "
         "normalised to the crop", "confirmed (ADR 0016)"],
        ["Mine-scale distribution (NEW)", "4 LINEAR bins over 0.25-0.40 (750 images each, uniform inside the bucket), "
         "mine length ~107-171 px; was 5 log bins over 0.10-0.40", "confirmed (ADR 0016)"],
        ["Zoom coupling (NEW)", "rocks, grass clippings, leaf clumps, dirt and the mine's pixel-sized soil / contact "
         "details x z = scale / 0.2, debris counts x z^-2, background magnified by z (capped at 1.5 px per source px); "
         "blades follow px/mm; sensor effects stay in pixels (SCENE_ZOOM_COUPLING, default off in the generator)",
         "confirmed (ADR 0016)"],
        ["Mines per image (NEW)", "0-4: 600 empty (20 %) and 600 each for 1..4; was 0-8", "confirmed (ADR 0016)"],
        ["Dataset size", f"3000 images (2700 train / 300 val), {nm_tot} planned mines ({nb_tot} buried), 600 empty",
         "confirmed"],
        ["Stratified factors", "mines per image (5), mine scale (4 linear bins), burial fraction (4), sun elevation "
                               "(6), light: overcast + 4 shadow bins (5), background family (2, + per-file quotas), "
                               "lens blur (3)", "confirmed (unchanged except mines / scale)"],
        ["Randomized factors", "sun azimuth, all per-mine pose / face-down / colour / burial yes-no / dust / soft "
                               "grains / position, camera jitter, debris counts, crop position", "confirmed"],
        ["Burial", "35 % of mines buried (random), target fraction in 4 equal-count buckets [0.05, 0.2, 0.3, 0.4, "
                   "0.5], cap 0.5", "confirmed (unchanged)"],
        ["JPEG quality", "generator-sampled 70-95 per image (an augmentation), saved at 640x640", "confirmed"],
        ["Output location", "output_dataset/v2_3000 (gitignored): images/{train,val}, labels/{train,val}, meta/, "
                            "manifest.csv, data.yaml, plan/, README.md; the earlier 1920x1080 render was deleted",
         "confirmed"],
        ["Generation time", "~0.7-2 s per image single-process (the full scene is still rendered at 1920x1080, "
                            "fewer debris objects) -> roughly 15-25 min with 4 low-priority workers",
         "the lead starts the render after the review of docs/zoomed_look.png"],
    ]
    page = {"id": "params", "tab": "Dataset v2: parameters",
            "title": "Dataset v2 (3000 zoomed 640x640 images): every sampled parameter",
            "intro": "DATASET NOT YET GENERATED. Plan confirmed with the zoomed 640x640 revision (ADR 0016: native "
                     "640x640 crop, mine scale 0.25-0.40 in 4 linear bins, scene zoom coupling, 0-4 mines). Every "
                     "graph on this page is the planned distribution from the 3000-row sampling plan "
                     "(scripts/generate_dataset.py --plan-only). Stratified factors are evenly sampled: equal-count buckets per image, value "
                     "uniform inside the bucket, buckets crossed with each other by a balanced design. Everything "
                     "else is randomized with the generator's tuned distributions. Before / after pairs use the same "
                     "seed and change only the named parameter.",
            "glossary": {"stratified": "Evenly sampled: the range is cut into buckets and every bucket gets exactly "
                                       "the same number of images (or a fixed quota); the value is random inside it.",
                         "randomized": "Each image / mine draws the value independently (i.i.d.) from the configured "
                                       "distribution.",
                         "balanced design": "Bucket columns are shuffled, then rows are swapped inside a column to make "
                                            "every pair of factors as evenly crossed as possible (pairwise chi-square "
                                            "minimised); marginal counts never change.",
                         "chi-square": "Sum over table cells of (count - expected)^2 / expected; 0 = perfectly "
                                       "even crossing.",
                         "PSF": "Point-spread function: how the lens smears a point (here a Gaussian blur).",
                         "YOLO label": "One line per box: class x_centre y_centre width height, normalised to 0-1.",
                         "native crop": "Cutting a window out of the rendered image pixel for pixel (no resize or "
                                        "interpolation), so nothing gets blurred or stretched.",
                         "zoom coupling": "Scaling everything physical (rocks, debris, ground texture, soil details) "
                                          "with the mine size, as if the camera moved closer."},
            "tables": [
                {"title": "Decisions", "columns": ["decision", "plan", "status"],
                 "rows": decisions},
                {"title": "Overview: parameters", "columns": ["parameter", "type", "buckets", "range", "override / config"],
                 "rows": overview,
                 "note": f"Balance: pairwise chi-square over all {len(b['chi2_per_pair'])} factor pairs "
                         f"{b['chi2_pairs_before']} (shuffled) -> {b['chi2_pairs_after']} (balanced). "
                         f"Planned mines {meta['n_mines_planned']}, buried {meta['n_buried_planned']}."},
                {"title": "Planned bucket counts (all images / val)", "columns": ["factor", "all", "val"],
                 "rows": [[k, " ".join(str(v) for v in meta["counts"][k].values()),
                           " ".join(str(v) for v in meta["val_counts"][k].values())] for k in meta["counts"]],
                 "note": f"Train {sp['train']}, val {sp['val']}. Base seed {meta['base_seed']}, image k = index k."}],
            "features": features}
    with open(os.path.join(SHOW, "manifest_params.json"), "w") as f:
        json.dump({"pages": [page]}, f, indent=1)
    print(f"manifest_params.json: {len(features)} cards")


if __name__ == "__main__":
    main()
