"""On-the-fly PFM-1 renderer (v2): small software rasterizer for assets/mine.stl.

Coordinates: world x = image right, world y = image up, z = towards the camera (camera looks straight down,
orthographic). The mesh is normalised so its longest side is 1 unit and rotated by extrinsic 'xyz' Euler angles
(pitch about x, roll about y, then yaw about z = pure in-plane rotation). The mine rests on its lowest point.

Rasterization: painter's algorithm (triangles sorted far -> near, filled with cv2.fillConvexPoly) into a
triangle-ID buffer at SUPERSAMPLE x resolution; colour, alpha and depth are looked up per pixel from the ID and
the buffer is area-averaged down once (alpha = sub-pixel coverage, RGB premultiplied). Nothing is cached except the
colour-free normalised mesh, so every instance (pose, colour, light, burial) is rendered fresh.

Burial clips the 3D triangles against a tilted plane (Sutherland-Hodgman); the shadow is the orthographic
projection of the (clipped) triangles along the sun direction onto the ground plane.
"""
from functools import lru_cache

import cv2
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R

from config import asset_path
from features.sun import sun_vector

SHIFT = 4  # sub-pixel bits for cv2.fillConvexPoly


@lru_cache(maxsize=2)
def load_mesh(path):
    """-> (V (n, 3) float64, F (m, 3) int) normalised (bbox-centred, longest side 1)."""
    m = trimesh.load(path)
    v = (m.vertices - m.bounds.mean(0)) / np.max(m.extents)
    return np.asarray(v, np.float64), np.asarray(m.faces)


# ----------------------------------------------------------------------------------------------- sampling
def sample_tilt(rng, cp):
    if rng.random() < cp.TILT_TAIL_PROB:
        return float(rng.choice([-1.0, 1.0]) * rng.uniform(*cp.TILT_TAIL_RANGE))
    while True:
        t = float(rng.normal(0.0, cp.TILT_SIGMA))
        if abs(t) <= cp.TILT_CAP:
            return t


def sample_pose(rng, cp):
    """-> (pitch, roll, yaw, face_down). pitch / roll are the small tilts relative to lying flat (on the bottom, or on
    the back when face_down), degrees. With prob FLIP_PROB the mine lies face down (underside towards the camera).
    MINE_POSE fixes the pose for controlled comparisons: (pitch, roll, yaw) or (pitch, roll, yaw, face_down)."""
    face_down = bool(rng.random() < cp.FLIP_PROB)   # drawn first: tilt sampling uses a variable number of draws
    p = (sample_tilt(rng, cp), sample_tilt(rng, cp), float(rng.uniform(0.0, 360.0)), face_down)
    if cp.MINE_POSE is not None:
        mp = tuple(cp.MINE_POSE)
        return (float(mp[0]), float(mp[1]), float(mp[2]), bool(mp[3]) if len(mp) > 3 else False)
    return p


# 180-degree turn about the mesh x axis (= roll 180, x = the mine's long axis): the underside faces the camera.
FLIP = np.diag([1.0, -1.0, -1.0])


def _min_rotation(a, b):
    """Smallest rotation matrix taking unit vector a to unit vector b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


@lru_cache(maxsize=2)
def face_down_base(path):
    """Rest attitude of a face-down mine: FLIP followed by the small correction that puts it on its actual stable
    face (the convex-hull face it settles on, from trimesh.poses.compute_stable_poses; for mine.stl ~1.7 deg, so a
    wing tip and the body touch the ground instead of balancing on the body alone). Tilts and yaw are applied on
    top, so pitch / roll are relative to this attitude."""
    m = trimesh.load(path)
    T, prob = trimesh.poses.compute_stable_poses(m, n_samples=1)
    down = [(p, Ti[:3, :3]) for Ti, p in zip(T, prob) if (Ti[:3, :3] @ [0, 0, 1])[2] < -0.5]
    if not down:
        return FLIP
    Rs = max(down, key=lambda t: t[0])[1]
    n_support = Rs.T @ np.array([0.0, 0.0, -1.0])        # support-face normal in the mesh frame
    return _min_rotation(FLIP @ n_support, np.array([0.0, 0.0, -1.0])) @ FLIP


def sample_burial(rng, cp):
    """-> dict(fraction, tilt, direction) or None (not buried). BURIAL_FRACTION is capped at BURIAL_MAX_FRACTION.
    Always 4 draws."""
    u, f, t, d = rng.random(), rng.uniform(*cp.BURIAL_FRACTION), rng.uniform(*cp.BURIAL_TILT), rng.uniform(0, 360)
    if not (cp.BURIAL and cp.MESH_MINES) or u >= cp.BURIAL_PROB:
        return None
    return {"fraction": float(min(f, cp.BURIAL_MAX_FRACTION)), "tilt": float(t), "direction": float(d)}


def sample_specular(rng, cp):
    return float(rng.uniform(*cp.SPECULAR)), float(rng.uniform(*cp.SPECULAR_EXP))


# ----------------------------------------------------------------------------------------------- geometry
def clip_triangles(tri, parent, n, c):
    """Sutherland-Hodgman clip of triangles (F, 3, 3) against the half-space n . p >= c (kept side = above the
    soil). Clipped polygons (3 or 4 vertices) are fan-triangulated. -> (tri', parent')."""
    s = tri @ n - c
    above = s >= 0
    cnt = above.sum(1)
    keep = cnt == 3
    out_t, out_p = [tri[keep]], [parent[keep]]
    for i in np.nonzero((cnt == 1) | (cnt == 2))[0]:
        poly = []
        t, si = tri[i], s[i]
        for k in range(3):
            P, Q, sp, sq = t[k], t[(k + 1) % 3], si[k], si[(k + 1) % 3]
            if sp >= 0:
                poly.append(P)
            if (sp >= 0) != (sq >= 0):
                poly.append(P + (Q - P) * (sp / (sp - sq)))
        for k in range(1, len(poly) - 1):
            out_t.append(np.array([[poly[0], poly[k], poly[k + 1]]]))
            out_p.append(np.array([parent[i]]))
    return np.concatenate(out_t), np.concatenate(out_p)


def _to_px(xy, origin, ppu, ss):
    """world xy -> fixed-point supersampled pixel coords (x right, y down)."""
    u = (xy[..., 0] - origin[0]) * ppu * ss
    v = (origin[1] - xy[..., 1]) * ppu * ss
    return np.round(np.stack([u, v], -1) * (1 << SHIFT)).astype(np.int32)


def _raster_ids(px, order, shape):
    """Painter's algorithm into an ID buffer: value = triangle index + 1 (0 = empty). float32 is exact < 2^24."""
    buf = np.zeros(shape, np.float32)
    for i in order:
        cv2.fillConvexPoly(buf, px[i], float(i + 1), cv2.LINE_8, SHIFT)
    return buf


def _raster_union(px, shape):
    buf = np.zeros(shape, np.uint8)
    for p in px:
        cv2.fillConvexPoly(buf, p, 255, cv2.LINE_8, SHIFT)
    return buf


def _face_normals(tri):
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)


def _top_depth(ids, tri, nrm, origin, ppu, ss):
    """Per-pixel z of the visible (top) surface, from the plane of the triangle in the ID buffer. NaN = empty."""
    h, w = ids.shape
    z = np.full((h, w), np.nan, np.float32)
    m = ids > 0
    if not m.any():
        return z
    k = ids[m].astype(np.int64) - 1
    yy, xx = np.nonzero(m)
    x = origin[0] + (xx + 0.5) / (ppu * ss)
    y = origin[1] - (yy + 0.5) / (ppu * ss)
    a, nn = tri[k, 0], nrm[k]
    z[m] = a[:, 2] - (nn[:, 0] * (x - a[:, 0]) + nn[:, 1] * (y - a[:, 1])) / np.where(np.abs(nn[:, 2]) < 1e-6, 1e-6, nn[:, 2])
    return z


# ----------------------------------------------------------------------------------------------- render
def render_mine(cp, pose, ppu, sun_az, sun_el, albedo, shadow_strength, burial=None, specular=(0.0, 1.0), soft=True):
    """Render one mine instance (deterministic: all random choices are parameters). ppu = pixels per mesh unit.
    pose = (pitch, roll, yaw[, face_down]) deg; albedo = RGB in [0, 1]; burial = sample_burial() dict or None;
    specular = (strength, Blinn-Phong exponent); soft = supersample + area-average (else 1 sample / pixel).

    -> dict with (all arrays share one canvas, float32):
       rgb_pm (h, w, 3) premultiplied colour, alpha (h, w) visible coverage, alpha_full (h, w) coverage before
       burial, shadow (h, w) shadow coverage (unblurred, includes the mine footprint), height (h, w) height of the
       visible surface above the soil plane in mesh units (NaN outside), and info (burial plane etc.).
    """
    V, F = load_mesh(asset_path(cp, cp.MINE_STL_PATH))
    pitch, roll, yaw = pose[:3]
    face_down = len(pose) > 3 and bool(pose[3])
    Rm = R.from_euler("xyz", (pitch, roll, yaw), degrees=True).as_matrix()
    if face_down:
        Rm = Rm @ face_down_base(asset_path(cp, cp.MINE_STL_PATH))
    tri = (V @ Rm.T)[F]
    z0 = float(tri[..., 2].min())
    nrm = _face_normals(tri)
    parent = np.arange(len(tri))
    L = sun_vector(sun_az, sun_el)
    ss = cp.SUPERSAMPLE if soft else 1
    info = {"burial_target": 0.0, "plane_tilt": 0.0}

    # soil plane n . p = c (default: flat ground through the lowest point)
    n_pl, c_pl = np.array([0.0, 0.0, 1.0]), z0
    front_all = nrm[:, 2] > 0
    # the clip plane hides BURIAL_CLIP_SHARE of the target; the rough soil line, ridge and clods add the rest
    burial_frac = burial["fraction"] * cp.BURIAL_CLIP_SHARE if burial else 0.0
    if burial_frac > 0:
        tilt, phi = np.deg2rad(burial["tilt"]), np.deg2rad(burial["direction"])
        n_pl = np.array([np.sin(tilt) * np.cos(phi), np.sin(tilt) * np.sin(phi), np.cos(tilt)])
        # choose c so that `burial_frac` of the top-down visible area lies below the plane: the visible surface is a
        # height field, so a pixel is buried exactly when its top point is below the plane -> quantile.
        lo, hi = tri[..., :2].reshape(-1, 2).min(0), tri[..., :2].reshape(-1, 2).max(0)
        pb = max(ppu, 96.0)
        org = (lo[0], hi[1])
        shape = (int((hi[1] - lo[1]) * pb) + 2, int((hi[0] - lo[0]) * pb) + 2)
        tf, nf = tri[front_all], nrm[front_all]
        ids = _raster_ids(_to_px(tf[..., :2], org, pb, 1), np.argsort(tf[..., 2].mean(1)), shape)
        zt = _top_depth(ids, tf, nf, org, pb, 1)
        m = ~np.isnan(zt)
        yy, xx = np.nonzero(m)
        P = np.stack([org[0] + (xx + 0.5) / pb, org[1] - (yy + 0.5) / pb, zt[m]], -1)
        c_pl = float(np.quantile(P @ n_pl, burial_frac))
        info.update(burial_target=float(burial_frac), plane_tilt=float(np.rad2deg(tilt)),
                    plane_dir=float(np.rad2deg(phi)))
        tri_full = tri
        tri, parent = clip_triangles(tri, parent, n_pl, c_pl)
    else:
        tri_full = tri

    # shadow: project vertices along the sun onto the soil plane (orthographic, all triangles, union fill)
    denom = max(float(n_pl @ L), 0.1)
    flat = tri.reshape(-1, 3)
    d = (flat @ n_pl - c_pl) / denom
    sh = (flat - np.outer(np.maximum(d, 0), L)).reshape(tri.shape)

    pts = np.concatenate([tri_full[..., :2].reshape(-1, 2), sh[..., :2].reshape(-1, 2)])
    pad = 4 + int(np.ceil(3 * (cp.PENUMBRA_BASE_PX + cp.PENUMBRA_PER_LENGTH * 0.4 * ppu) + cp.BERM_WIDTH_PX[1] * 2
                           + 3 * cp.CONTACT_AO_SIGMA[1]))
    lo, hi = pts.min(0), pts.max(0)
    # Canvas origin snapped to whole pixels relative to the UNCLIPPED mesh's top-left corner, so the mine has the
    # same sub-pixel phase (identical anti-aliased silhouette / bbox) with or without burial, whatever the shadow does.
    lo_f, hi_f = tri_full[..., :2].reshape(-1, 2).min(0), tri_full[..., :2].reshape(-1, 2).max(0)
    left = int(np.ceil((lo_f[0] - lo[0]) * ppu)) + pad
    top = int(np.ceil((hi[1] - hi_f[1]) * ppu)) + pad
    org = (lo_f[0] - left / ppu, hi_f[1] + top / ppu)
    w = left + int(np.ceil((hi[0] - lo_f[0]) * ppu)) + pad
    h = top + int(np.ceil((hi_f[1] - lo[1]) * ppu)) + pad
    S = (h * ss, w * ss)

    # shading per (parent) face. Lighting is normalised so a horizontal surface in sun has gain 1 and a surface
    # facing away from the sun has gain 1 - shadow_strength, i.e. exactly as dark as the ground in the cast shadow.
    nz = nrm[:, 2] > 0
    ndl = nrm @ L
    amb = 1.0 - shadow_strength
    gain = amb + (1.0 - amb) * np.clip(np.maximum(ndl, 0) / L[2], 0, cp.SHADE_MAX_GAIN)
    Hv = L + np.array([0, 0, 1.0])
    Hv /= np.linalg.norm(Hv)
    spec_k, spec_e = specular
    spec = spec_k * np.maximum(nrm @ Hv, 0) ** spec_e * (ndl > 0)
    shade = np.clip(albedo[None] * gain[:, None] + spec[:, None], 0, 1).astype(np.float32)

    front = nz[parent]
    tf, pf = tri[front], parent[front]
    order = np.argsort(tf[..., 2].mean(1))
    ids = _raster_ids(_to_px(tf[..., :2], org, ppu, ss), order, S)
    m = ids > 0
    k = ids.astype(np.int64) - 1
    rgb = np.zeros(S + (3,), np.float32)
    rgb[m] = shade[pf[k[m]]]
    zt = _top_depth(ids, tf, nrm[pf], org, ppu, ss)
    yy, xx = np.nonzero(m)
    height = np.full(S, np.nan, np.float32)
    P = np.stack([org[0] + (xx + 0.5) / (ppu * ss), org[1] - (yy + 0.5) / (ppu * ss), zt[m]], -1)
    height[m] = P @ n_pl - c_pl
    alpha = m.astype(np.float32)

    if tri_full is tri:
        alpha_full = alpha
    else:
        ff = tri_full[front_all]
        alpha_full = (_raster_union(_to_px(ff[..., :2], org, ppu, ss), S) > 0).astype(np.float32)
    shadow = (_raster_union(_to_px(sh[..., :2], org, ppu, ss), S) > 0).astype(np.float32)

    if ss > 1:
        down = lambda a: cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
        rgb, alpha, alpha_full, shadow = down(rgb), down(alpha), down(alpha_full), down(shadow)
        hz = np.nan_to_num(height, nan=0.0)
        hsum = down(hz * m)
        height = np.where(alpha > 1e-3, hsum / np.maximum(alpha, 1e-3), np.nan).astype(np.float32)
    info["shadow_length_px"] = float(np.max(np.linalg.norm((flat - sh.reshape(-1, 3))[:, :2], axis=1)) * ppu) \
        if len(flat) else 0.0
    return {"rgb_pm": rgb, "alpha": alpha, "alpha_full": alpha_full, "shadow": shadow, "height": height,
            "info": info, "length_px": float(ppu)}
