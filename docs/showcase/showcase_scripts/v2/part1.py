from v2lib import *
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from features.mesh import sample_pose
from config import make_config

feat = {"id": "mesh_mines", "title": "On-the-fly mine rendering", "flag": "MESH_MINES",
        "summary": "v1 pasted one of 50 pre-rendered mine pictures, so the detector saw the same 50 shapes and one near-constant colour over and over. v2 draws every mine from the 3D model when the image is made, with its own tilt, rotation, size, colour, lighting and dust, so no two mines are alike. A detector trained on a small pool of look-alike sprites tends to memorise them; real mines in the field never match a fixed pool.",
        "how": "The STL mesh is rotated (yaw 0-360, pitch/roll mostly small with a thin tail), projected top-down and rasterised triangle by triangle, far to near, at 4x resolution. Lighting is Lambert + specular from the image's sun. Scale uses the same pixels-per-unit as v1 sprites, so MINE_SCALE_MIN/MAX mean the same.",
        "code": "DatasetGenerator/features/mesh.py: sample_pose, render_mine; objects.py: Mine._render_mesh; assets/mine.stl",
        "options": [], "before_after": [],
        "notes": "Flat shading per triangle (the STL is faceted); no self-shadowing between body and wings; no plastic texture or moulding detail; about 35-60 ms per mine. Grid tiles are plain 200 px windows around each mine (not rescaled), so the size differences are real."}

# ---- grid of 42 v2 instances
tiles = []; seed = 100
while len(tiles) < 42:
    rgb, lab, meta = render(seed, n_mines=8, min_mines=8, zero_mine_prob=0.0)
    for m in meta["mines"]:
        if not m.get("labelled") or m["visible_fraction"] < 0.9 or m["burial"].get("buried"):
            continue
        cx, cy = m["placed_at"][0] + m["length_px"] / 2, m["placed_at"][1] + m["length_px"] / 2
        b = m["box"]; cx, cy = b[0] * W, b[1] * H
        if not (100 <= cx <= W - 100 and 100 <= cy <= H - 100):
            continue
        t = crop(rgb, cx, cy, 200, 200, 1)[0]
        t = tag(t, f"s{m['scale']:.2f} p{m['pitch']:.0f} r{m['roll']:.0f} y{m['yaw']:.0f}", "bl")
        t = t.copy(); t[:2] = 0; t[:, :2] = 0
        if len(tiles) < 42: tiles.append(t)
    seed += 1
grid = tiles_grid(tiles, 7)
img_grid = save(grid, "mesh_grid_42.jpg")

# ---- v1 sprite grid for contrast
tiles1 = []; seed = 100
while len(tiles1) < 21:
    rgb, lab, meta = render(seed, v1=True, n_mines=8, min_mines=8, zero_mine_prob=0.0)
    for m in meta["mines"]:
        if not m.get("labelled"): continue
        b = m["box"]; cx, cy = b[0] * W, b[1] * H
        if not (100 <= cx <= W - 100 and 100 <= cy <= H - 100): continue
        t = crop(rgb, cx, cy, 200, 200, 1)[0]
        t = tag(t, f"{m['sprite'][:16]} s{m['scale']:.2f}", "bl").copy(); t[:2] = 0; t[:, :2] = 0
        if len(tiles1) < 21: tiles1.append(t)
    seed += 1
img_v1grid = save(tiles_grid(tiles1, 7), "mesh_grid_v1_21.jpg")

# ---- pitch/roll distribution
cfg = make_config({})
rng = np.random.default_rng(0)
P = np.array([sample_pose(rng, cfg)[:2] for _ in range(2000)])
fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.6), dpi=110, gridspec_kw={"width_ratios": [1.3, 1]})
a = np.abs(P).ravel(); pc = np.percentile(a, [50, 90, 99])
bins = np.arange(0, 32, 1)
ax[0].hist(a, bins=bins, color="#4c78a8", edgecolor="white")
for p, v, c in zip((50, 90, 99), pc, ("#2ca02c", "#e08a00", "#d62728")):
    ax[0].axvline(v, color=c, ls="--"); ax[0].text(v + .3, ax[0].get_ylim()[1] * (0.93 - 0.1 * (p == 90) - 0.2 * (p == 99)), f"p{p} = {v:.1f} deg", color=c)
ax[0].set_xlabel("|tilt| (deg), pitch and roll pooled"); ax[0].set_ylabel("count (4000 values)")
ax[0].set_title("Mostly flat, thin tail to 30 deg (v1: uniform +-20)")
ax[1].scatter(P[:, 0], P[:, 1], s=5, alpha=.45, color="#4c78a8")
ax[1].axhline(0, c="#999", lw=.6); ax[1].axvline(0, c="#999", lw=.6)
for r in (10, 25):
    ax[1].add_patch(plt.Circle((0, 0), r, fill=False, ls=":", color="#888"))
ax[1].set_xlim(-35, 35); ax[1].set_ylim(-35, 35); ax[1].set_aspect("equal")
ax[1].set_xlabel("pitch (deg)"); ax[1].set_ylabel("roll (deg)"); ax[1].set_title("2000 sampled mines (dotted: 10 and 25 deg)")
for x in ax: x.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "mesh_pose_distribution.png")); plt.close(fig)
# 2000 sampled mines straight from features.mesh.sample_pose with the default controlPanel settings

# ---- poses at fixed colour/position
poses = [(0, 0), (12, 0), (20, 15), (-30, 8)]
opts = [O("grid of 42 v2 mines", "n_mines=8 per image, seeds 100+, default settings (burial excluded)", img_grid,
          "Each tile is one distinct instance cropped around its box (200 px windows, true relative size). Tag: scale, pitch, roll, yaw in degrees. Colour, size, tilt, light and dust all differ."),
        O("v1 for contrast (21 sprites)", "v1=True, n_mines=8 per image", img_v1grid,
          "The same kind of grid from v1: sprites from a pool of 50, near-identical dark olive, only the in-plane rotation and size change."),
        O("pose distribution (2000 mines)", "features.mesh.sample_pose, TILT_SIGMA=5, TILT_TAIL_PROB=0.05, TILT_CAP=35", "images/v2/mesh_pose_distribution.png",
          "Left: histogram of |pitch| and |roll| with median, 90th and 99th percentile. Right: pitch vs roll scatter.")]
for p, r in poses:
    rgb, lab, meta = render(13, **{**BASE, "mine_pose": (p, r, 30), "psf_sigma": 0.3, "motion_blur_prob": 0})
    im = save(mine_crop(rgb, 4), f"mesh_pose_{p}_{r}.png".replace("-", "m"))
    opts.append(O(f"pitch {p}, roll {r}", f"mine_pose=({p}, {r}, 30), seed 13, scale 0.35", im,
                  "Real 3D tilt: the raised edge catches the light, the low edge goes dark, and the outline changes; a flat rotated picture cannot do this."))
feat["options"] = opts

# ---- before / after v1 vs v2
for s, nm in [(13, "a"), (12, "b")]:
    kw = {**BASE, "psf_sigma": 0.3, "motion_blur_prob": 0}
    V1MINE = dict(mesh_mines=False, soft_edges=False, soil_blend=False, colour_palette=False, shadows=False, burial=False)
    r1, _, _ = render(s, **kw, **V1MINE)
    r2, _, _ = render(s, **kw)
    feat["before_after"].append(BA(f"v1 sprite vs v2 mesh (seed {s})",
        save(mine_crop(r1, 4), f"mesh_ba_{nm}_v1.png"), save(mine_crop(r2, 4), f"mesh_ba_{nm}_v2.png"),
        "v1-style mine", "v2 mine",
        "Same seed, background, position and size, 4x zoom. Before = the five mine features switched off (sprite, hard edges, hard dots, v1 colour, no shadow) on the v2 background so only the mine differs. v1 is a flat pre-baked picture with hard dots; v2 has smooth shading, a cast shadow, dust and a sun-consistent look."))
dump("frag_1.json", feat)
print("done part1")
