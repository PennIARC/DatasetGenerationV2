"""Scene objects: debris layers (dirt / rocks / grass / dirt snippets) and mines, built from features/*.

v2 rewrite of the v1 pygame objects in numpy / OpenCV (float32 RGB in [0, 1]). With every v2 flag off, each step
mirrors v1 (nearest-neighbour scale / rotate, hard squares, sprite mines, ...). Every object gets its own random
streams so switching one feature flag does not change the rest of the scene.
"""
import os

import cv2
import numpy as np

import fx
from features import assets, blades, burial_fx, colour, edges, mesh, shadows, soil


CONTACT_KIND_SCALE = {"leaf": 0.5}   # leaf clumps: weaker contact shadow than rocks / clods


def _ri(rng, a, b):
    """random integer in [a, b] inclusive (like random.randint)."""
    return int(rng.integers(a, b + 1))


# ===================================================================================================== debris
class EnvironmentDebris:
    """One debris layer (v1 draws two: undergrowth before the mines, overgrowth after). rng drives generation
    (counts, files, sizes, positions); draw_rng drives draw-time choices that depend on flags."""

    def __init__(self, cfg, rng, scene, draw_rng, density_factor=1.0, layer="under"):
        self.cfg, self.rng, self.scene, self.draw_rng, self.layer = cfg, rng, scene, draw_rng, layer
        self.elements = []
        self._generate_dirt(density_factor)
        self._generate_dirt_snippets(density_factor)
        self._generate_rocks(density_factor)
        self._generate_grass_overlays(density_factor)
        self._generate_leaf_clumps(density_factor)
        self._generate_blades(density_factor)

    def _generate_leaf_clumps(self, density_factor):
        """LEAF_CLUMPS_NEW: RGBA leaf-litter clumps from assets_new/grassDebris, own count / size / stream; colour
        pulled towards the local ground, desaturated and darkened at draw time; contact shadow + rim blend."""
        cfg = self.cfg
        rng = np.random.default_rng(self.rng.integers(2 ** 31))
        if not (cfg.LEAF_CLUMPS_NEW and cfg.NEW_ASSETS) or not assets.sources(cfg, "LEAF"):
            return
        n = int(_ri(rng, *(cfg.LEAF_CLUMPS_UNDER if self.layer == "under" else cfg.LEAF_CLUMPS_OVER)) * density_factor)
        for _ in range(n):
            cut = assets.load_cutout(assets.pick_file(rng, cfg, "LEAF"))
            tw = _ri(rng, *cfg.LEAF_CLUMP_SIZE)
            u = rng.random(8)
            if cut is None:
                continue
            rgb, alpha, _ = cut
            th = max(1, int(tw * rgb.shape[0] / rgb.shape[1]))
            prgb, pa = edges.resize_rotate(rgb, alpha, tw, th, float(u[0] * 360), cfg.SOFT_EDGES,
                                           cfg.DEBRIS_ALPHA_FEATHER)
            lerp = lambda r, t: r[0] + (r[1] - r[0]) * t  # noqa: E731
            self.elements.append({
                "type": "image", "rgb_pm": prgb, "alpha": pa, "kind": "leaf", "width": tw, "u": u[4:8],
                "x": _ri(rng, -tw // 2, cfg.SCREEN_WIDTH), "y": _ri(rng, -th // 2, cfg.SCREEN_HEIGHT),
                "height_px": lerp(cfg.GRASS_HEIGHT_FRAC, u[1]) * tw, "shadow_scale": cfg.GRASS_SHADOW_SCALE,
                "adapt": cfg.LEAF_COLOUR_ADAPT, "bright": 1.0 - lerp(cfg.LEAF_DARKEN, u[2]),
                "desat": lerp(cfg.LEAF_DESATURATE, u[3])})

    def _generate_blades(self, density_factor):
        """GRASS_BLADES: thin blades / tufts / wisps (features/blades.py), own random stream."""
        cfg = self.cfg
        rng = np.random.default_rng(self.rng.integers(2 ** 31))
        if not (cfg.GRASS_BLADES and cfg.NEW_ASSETS):
            return
        rng_n = cfg.BLADES_UNDER if self.layer == "under" else cfg.BLADES_OVER
        n = int(_ri(rng, *rng_n) * density_factor)
        els = blades.make_blade_elements(cfg, rng, self.scene["px_per_mm"], n, self.scene["blade_budget"])
        for el in els:
            h, w = el["alpha"].shape
            el["x"], el["y"] = _ri(rng, -w // 2, cfg.SCREEN_WIDTH), _ri(rng, -h // 2, cfg.SCREEN_HEIGHT)
        self.elements.extend(els)
        if self.layer != "over":
            return
        # BLADES_OVER_ON_MINE: extra over-layer blades whose centre lies in (slightly expanded) mine boxes, so some
        # mines are partly covered by grass (labels come from the visible mask after this occlusion)
        rm = np.random.default_rng(rng.integers(2 ** 31))
        on = self.scene.setdefault("blades_on_mine", {})
        for j, (mx, my, mw, mh) in self.scene.get("mine_rects", []):
            u = rm.random()
            k = _ri(rm, *cfg.BLADES_ON_MINE_COUNT)
            if u >= cfg.BLADES_OVER_ON_MINE:
                continue
            els = blades.make_blade_elements(cfg, rm, self.scene["px_per_mm"], k, self.scene["blade_budget"])
            e = cfg.BLADES_ON_MINE_EXPAND
            for el in els:
                h, w = el["alpha"].shape
                cx = rm.uniform(mx - e * mw, mx + (1 + e) * mw)
                cy = rm.uniform(my - e * mh, my + (1 + e) * mh)
                el["x"], el["y"] = int(cx - w / 2), int(cy - h / 2)
            on[j] = len(els)
            self.elements.extend(els)

    def _generate_dirt(self, density_factor):
        cfg, rng = self.cfg, self.rng
        for _ in range(int(_ri(rng, *cfg.DIRT_RECTS_PER_LAYER) * density_factor)):
            size = _ri(rng, *cfg.DIRT_RECT_SIZE)
            x, y = _ri(rng, 0, cfg.SCREEN_WIDTH), _ri(rng, 0, cfg.SCREEN_HEIGHT)
            col = np.clip(np.array(cfg.DIRT_COLOR_BASE) + rng.integers(-cfg.DIRT_VARIANCE, cfg.DIRT_VARIANCE + 1, 3),
                          0, 255) / 255.0
            self.elements.append({"type": "rect", "x": x, "y": y, "size": size, "col": col.astype(np.float32)})

    def _generate_dirt_snippets(self, density_factor):
        """NEW_ASSETS: RGBA dirt / soil-clod snippets (assets_new/dirt)."""
        cfg = self.cfg
        rng = np.random.default_rng(self.rng.integers(2 ** 31))   # own stream: absent assets change nothing else
        if not assets.sources(cfg, "DIRT"):
            return
        for _ in range(int(_ri(rng, *cfg.DIRT_SNIPPETS_PER_LAYER) * density_factor)):
            path = assets.pick_file(rng, cfg, "DIRT")
            cut = assets.load_cutout(path, erode=cfg.SOFT_EDGES)
            tw = _ri(rng, *cfg.DIRT_SNIPPET_SIZE)
            if cut is None:
                continue
            rgb, alpha, _ = cut
            th = max(1, int(tw * rgb.shape[0] / rgb.shape[1]))
            prgb, pa = edges.resize_rotate(rgb, alpha, tw, th, float(rng.uniform(0, 360)), cfg.SOFT_EDGES,
                                           cfg.DEBRIS_ALPHA_FEATHER)
            # dirt/index.json: clod = raised lump (shadow), patch / dust = flat overlays with an opacity range
            it = assets.dirt_index(cfg).get(os.path.basename(path), {})
            dkind = it.get("kind", "clod" if "clod" in os.path.basename(path) else "patch")
            op = it.get("opacity", [0.9, 1.0] if dkind == "clod" else [0.6, 0.95])
            u = rng.random(5)
            o = op[0] + (op[1] - op[0]) * u[0]
            el = {"type": "image", "rgb_pm": prgb * o, "alpha": pa * o, "kind": f"dirt_{dkind}",
                  "x": _ri(rng, -tw // 2, cfg.SCREEN_WIDTH), "y": _ri(rng, -th // 2, cfg.SCREEN_HEIGHT),
                  "height_px": (cfg.CLOD_HEIGHT_FRAC[0] + (cfg.CLOD_HEIGHT_FRAC[1] - cfg.CLOD_HEIGHT_FRAC[0]) * u[1]) * tw,
                  "shadow_scale": 1.0 if it.get("casts_shadow", dkind == "clod") else 0.0, "width": tw, "u": u[1:]}
            if dkind != "clod":
                el.update(adapt=cfg.DIRT_PATCH_ADAPT, bright=1.0)
            self.elements.append(el)

    def _generate_rocks(self, density_factor):
        cfg, rng = self.cfg, self.rng
        if not assets.sources(cfg, "ROCK"):
            return
        for _ in range(int(_ri(rng, cfg.ROCKS_TO_SPAWN_MIN, cfg.ROCKS_TO_SPAWN_MAX) * density_factor)):
            cut_path = assets.pick_file(rng, cfg, "ROCK")
            cut = assets.load_cutout(cut_path, erode=cfg.SOFT_EDGES)
            tw = _ri(rng, cfg.ROCK_OUTPUT_SIZE_MIN, cfg.ROCK_OUTPUT_SIZE_MAX)
            if cut is None:
                continue
            rgb, alpha, _ = cut
            gravel = "gravel" in os.path.basename(cut_path).lower()
            th = max(1, int(tw * rgb.shape[0] / rgb.shape[1]))
            angle = float(rng.uniform(0, 360))
            jitter = float(rng.uniform(-cfg.ROCK_ALIGN_JITTER, cfg.ROCK_ALIGN_JITTER))
            if cfg.SHADOWS and cfg.ROCK_ALIGN_LIGHT:
                angle = light_aligned_angle(rgb, alpha, self.scene["sun"]["azimuth"], jitter)
            prgb, pa = edges.resize_rotate(rgb, alpha, tw, th, angle, cfg.SOFT_EDGES, cfg.DEBRIS_ALPHA_FEATHER)
            x, y = _ri(rng, -tw // 2, cfg.SCREEN_WIDTH), _ri(rng, -th // 2, cfg.SCREEN_HEIGHT)
            # rock height (for the cast shadow): fraction of the width, smaller for small rocks and gravel
            hf = rng.uniform(*cfg.ROCK_HEIGHT_FRAC)
            size_t = (tw - cfg.ROCK_OUTPUT_SIZE_MIN) / max(1, cfg.ROCK_OUTPUT_SIZE_MAX - cfg.ROCK_OUTPUT_SIZE_MIN)
            hf = cfg.ROCK_HEIGHT_FRAC[0] + (hf - cfg.ROCK_HEIGHT_FRAC[0]) * (cfg.ROCK_SMALL_HEIGHT_SCALE +
                                                                         (1 - cfg.ROCK_SMALL_HEIGHT_SCALE) * size_t)
            if gravel:
                hf *= cfg.ROCK_GRAVEL_HEIGHT_SCALE
            self.elements.append({"type": "image", "rgb_pm": prgb, "alpha": pa, "x": x, "y": y, "kind": "rock",
                                  "audit": assets.audit_status(cfg, cut_path), "file": assets.repo_rel(cut_path),
                                  "height_px": hf * tw, "shadow_scale": 1.0, "width": tw, "u": rng.random(4)})

    def _generate_grass_overlays(self, density_factor):
        cfg, rng = self.cfg, self.rng
        if not assets.sources(cfg, "GRASS"):
            return
        for _ in range(cfg.GRASS_IMAGES_TO_SAMPLE):
            cut = assets.load_cutout(assets.pick_file(rng, cfg, "GRASS"), erode=cfg.SOFT_EDGES)
            if cut is None:
                continue
            rgb, alpha, kind = cut
            mh, mw = alpha.shape
            for _ in range(int(_ri(rng, 5, cfg.GRASS_CLIPPINGS_PER_IMAGE) * density_factor)):
                cw = _ri(rng, cfg.GRASS_CROP_SIZE_MIN, cfg.GRASS_CROP_SIZE_MAX)
                ch = _ri(rng, cfg.GRASS_CROP_SIZE_MIN, cfg.GRASS_CROP_SIZE_MAX)
                if kind == "alpha":  # RGBA snippets (assets_new) are already single clippings: crop at most to size
                    cw, ch = min(cw, mw - 1), min(ch, mh - 1)
                if cw >= mw or ch >= mh or cw < 2 or ch < 2:
                    continue
                cx, cy = _ri(rng, 0, mw - cw), _ri(rng, 0, mh - ch)
                ca = alpha[cy:cy + ch, cx:cx + cw]
                if (ca > 0.5).sum() < 10:
                    continue
                tw = _ri(rng, cfg.GRASS_OUTPUT_SIZE_MIN, cfg.GRASS_OUTPUT_SIZE_MAX)
                th = max(1, int(tw * ch / cw))
                prgb, pa = edges.resize_rotate(rgb[cy:cy + ch, cx:cx + cw], ca, tw, th, None, cfg.SOFT_EDGES,
                                               cfg.DEBRIS_ALPHA_FEATHER)
                x, y = _ri(rng, 0, cfg.SCREEN_WIDTH), _ri(rng, 0, cfg.SCREEN_HEIGHT)
                self.elements.append({"type": "image", "rgb_pm": prgb, "alpha": pa, "x": x, "y": y,
                                      "kind": "leaf" if kind == "alpha" else "grass", "width": tw, "u": rng.random(4),
                                      "height_px": rng.uniform(*cfg.GRASS_HEIGHT_FRAC) * tw,
                                      "shadow_scale": cfg.GRASS_SHADOW_SCALE})

    def draw(self, img, occlusion=None):
        cfg, sun = self.cfg, self.scene["sun"]
        cmap = blades.local_colour_map(img) if any("adapt" in el for el in self.elements) else None
        H, W = img.shape[:2]
        for el in self.elements:
            if el["type"] == "rect":
                self._draw_dirt(img, el, occlusion)
                continue
            if "adapt" in el:
                h, w = el["alpha"].shape
                el["rgb_pm"] = blades.adapt_colour(el["rgb_pm"], el["alpha"],
                                                   blades.lookup(cmap, el["x"] + w / 2, el["y"] + h / 2, W, H),
                                                   el["adapt"], el["bright"])
                if el.get("desat", 0) > 0:  # pull towards grey (premultiplied luminance keeps the alpha)
                    lum = fx.luminance(el["rgb_pm"])[..., None]
                    el["rgb_pm"] = (el["rgb_pm"] * (1 - el["desat"]) + lum * el["desat"]).astype(np.float32)
            k = el["kind"]
            if self.layer == "over" and k in ("blade", "tuft", "wisp") and self.scene.get("soil_zones"):
                self._soil_zone_blade(img, el)
            cnt = self.scene.setdefault("debris_counts", {})
            cnt[f"{self.layer}_{k}"] = cnt.get(f"{self.layer}_{k}", 0) + 1
            if cfg.SHADOWS and cfg.ROCK_CONTACT_SHADOW and k in cfg.CONTACT_SHADOW_KINDS:
                u = el["u"]
                st = (cfg.ROCK_CONTACT_STRENGTH[0] + (cfg.ROCK_CONTACT_STRENGTH[1] - cfg.ROCK_CONTACT_STRENGTH[0]) * u[0])
                st *= float(np.clip(sun["shadow_strength"] / cfg.ROCK_CONTACT_SUN_REF, cfg.ROCK_CONTACT_MIN_SCALE, 1.3))
                wf = cfg.ROCK_CONTACT_WIDTH_FRAC[0] + (cfg.ROCK_CONTACT_WIDTH_FRAC[1] - cfg.ROCK_CONTACT_WIDTH_FRAC[0]) * u[1]
                f, pad = shadows.contact_shadow(el["alpha"], el["width"], sun, st * CONTACT_KIND_SCALE.get(k, 1.0), wf,
                                                cfg.ROCK_CONTACT_OFFSET_FRAC)
                fx.darken(img, f, el["x"] - pad, el["y"] - pad)
            if k == "rock":
                h, w = el["alpha"].shape
                self.scene.setdefault("rocks", []).append([int(el["x"] + w / 2), int(el["y"] + h / 2), int(w), self.layer,
                                                           el.get("audit", "ok"), el.get("file", "")])
            if cfg.SHADOWS and el["shadow_scale"] > 0 and (cfg.ROCK_CAST_SHADOW or k not in cfg.CONTACT_SHADOW_KINDS):
                rock_like = k in cfg.CONTACT_SHADOW_KINDS and cfg.ROCK_CONTACT_SHADOW
                f, pad = shadows.debris_shadow(
                    el["alpha"], el["height_px"], sun, sun["shadow_strength"] * el["shadow_scale"], cfg,
                    max_length=cfg.ROCK_SHADOW_MAX_LENGTH_FRAC * el["width"] if rock_like else None,
                    penumbra_per_length=cfg.ROCK_PENUMBRA_PER_LENGTH if rock_like else None)
                fx.darken(img, f, el["x"] - pad, el["y"] - pad)
            if cfg.ROCK_RIM_BLEND and k in cfg.RIM_BLEND_KINDS:
                h, w = el["alpha"].shape
                ground = fx.crop_padded(img, el["x"] - 4, el["y"] - 4, h + 8, w + 8).reshape(-1, 3).mean(0)
                u = el["u"]
                el["rgb_pm"] = edges.rim_blend(
                    el["rgb_pm"], el["alpha"], ground, sun["azimuth"],
                    cfg.ROCK_GROUND_TINT[0] + (cfg.ROCK_GROUND_TINT[1] - cfg.ROCK_GROUND_TINT[0]) * u[2],
                    (cfg.ROCK_RIM_DARKEN[0] + (cfg.ROCK_RIM_DARKEN[1] - cfg.ROCK_RIM_DARKEN[0]) * u[3])
                    * (sun["shadow_strength"] / cfg.ROCK_CONTACT_SUN_REF), cfg.ROCK_RIM_BAND_PX)
            fx.over(img, el["rgb_pm"], el["alpha"], el["x"], el["y"])
            if occlusion is not None:
                fx.accumulate_alpha(occlusion, el["alpha"], el["x"], el["y"])

    def _soil_zone_blade(self, img, el):
        """Over-layer blade crossing a buried mine's soil line: lifted by the berm (warp + shadow below + highlight);
        parts lying on the soil-covered region are partly covered (the blade emerges from the soil)."""
        cfg, sun = self.cfg, self.scene["sun"]
        h, w = el["alpha"].shape
        zw = np.zeros((h, w), np.float32)
        core = np.zeros((h, w), np.float32)
        for z in self.scene["soil_zones"]:
            r = fx.clip_region(z["line_w"].shape[0], z["line_w"].shape[1], el["x"] - z["x"], el["y"] - z["y"], h, w)
            if r is None:
                continue
            d, s_ = r   # d: slices in the zone canvas, s_: slices in the blade canvas
            zw[s_] = np.maximum(zw[s_], z["line_w"][d])
            core[s_] = np.maximum(core[s_], z["core"][d])
            lift = z["lift_px"]
        if cfg.BLADE_SOIL_LIFT and (zw * el["alpha"]).max() > 0.05:
            a_ = np.deg2rad(sun["azimuth"])
            up = np.array([np.cos(a_), -np.sin(a_)], np.float32)     # towards the sun = away from the shadow side
            el["rgb_pm"], el["alpha"], f = burial_fx.lift_blade(el["rgb_pm"], el["alpha"], zw, lift, up,
                                                                sun["shadow_strength"])
            fx.darken(img, f, el["x"], el["y"])
            el["lifted"] = True
        if cfg.BLADE_EMERGE and (core * el["alpha"]).max() > 0.05:
            n = fx.fbm(h, w, 3.0, np.random.default_rng(int(el["x"] * 7919 + el["y"])), octaves=2)
            cov = np.clip(core * cfg.BLADE_EMERGE_COVER * (0.4 + 0.9 * n), 0, 0.95)
            el["rgb_pm"] = (el["rgb_pm"] * (1 - cov)[..., None]).astype(np.float32)
            el["alpha"] = (el["alpha"] * (1 - cov)).astype(np.float32)

    def _draw_dirt(self, img, el, occlusion):
        x, y, s = el["x"], el["y"], el["size"]
        if not self.cfg.SOIL_BLEND:  # v1: hard opaque square
            a = np.ones((s, s), np.float32)
            rgb_pm = el["col"] * a[..., None]
        else:
            local = fx.crop_padded(img, x + s // 2 - 3, y + s // 2 - 3, 7, 7).reshape(-1, 3).mean(0)
            rgb_pm, a, off = soil.dirt_grain(s, el["col"], local, self.draw_rng, self.cfg)
            x, y = x + off, y + off
        fx.over(img, rgb_pm, a, x, y)
        if occlusion is not None:
            fx.accumulate_alpha(occlusion, a, x, y)


def light_aligned_angle(rgb, alpha, sun_az, jitter):
    """Rotation (deg, counter-clockwise) that turns the bright side of a rock photo (its baked-in light) towards the
    sun azimuth, +- jitter."""
    lum = fx.luminance(rgb) * alpha
    ys, xs = np.mgrid[:alpha.shape[0], :alpha.shape[1]]
    wsum, lsum = alpha.sum() + 1e-6, lum.sum() + 1e-6
    cx, cy = (xs * alpha).sum() / wsum, (ys * alpha).sum() / wsum
    bx, by = (xs * lum).sum() / lsum - cx, (ys * lum).sum() / lsum - cy
    return float(sun_az - np.degrees(np.arctan2(-by, bx)) + jitter)


# ===================================================================================================== mines
class Mine:
    """One mine instance: rendered on the fly from mine.stl (MESH_MINES) or a v1 sprite.
    seed = [SEED, image index, 10, mine number]; sub-streams: 0 core (scale, sprite, placement), 1 pose, 2 colour,
    3 burial, 4 specular, 5 soil blend, 6 burial overlay, 7 shadow / AO, 8 v1 dots."""

    def __init__(self, cfg, seed, scene):
        self.sub = lambda k: np.random.default_rng(list(seed) + [k])
        self.cfg, self.scene = cfg, scene
        self.rng = self.sub(0)
        self.meta = {}
        scale = float(self.rng.uniform(cfg.MINE_SCALE_MIN, cfg.MINE_SCALE_MAX))
        self.meta["scale"] = scale
        self.r = None
        if cfg.MESH_MINES:
            self._render_mesh(scale)
        else:
            self._load_sprite(scale)
        # placement anchor = bbox of the UNCLIPPED silhouette (alpha_full), so burial never moves the mine; labels
        # still come from the visible mask (Mine.label)
        a = self.alpha_full > cfg.LABEL_ALPHA_THRESHOLD
        ys, xs = np.nonzero(a)
        if len(xs) == 0:
            ys, xs = np.array([0]), np.array([0])
        self.bx0, self.by0, self.bx1, self.by1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        self.x = self.y = 0
        self.visible = self.alpha

    def _render_mesh(self, scale):
        cfg, sun = self.cfg, self.scene["sun"]
        pose = mesh.sample_pose(self.sub(1), cfg)
        albedo, cinfo = colour.sample_colour(self.sub(2), cfg)
        burial = mesh.sample_burial(self.sub(3), cfg)
        ppu = cfg.MINE_PX_PER_UNIT * scale
        r = mesh.render_mine(cfg, pose, ppu, sun["azimuth"], sun["elevation"], albedo, sun["shadow_strength"],
                             burial=burial, specular=mesh.sample_specular(self.sub(4), cfg), soft=cfg.SOFT_EDGES)
        self.r = r
        self.rgb_pm, self.alpha, self.alpha_full = r["rgb_pm"], r["alpha"], r["alpha_full"]
        if burial is not None:
            # the clip plane can leave slivers on thin wings / rims and tiny islands: remove them (they count as buried)
            full_px = float((self.alpha_full > 0.5).sum())
            keep = burial_fx.clean_mask(self.alpha > 0.5, cfg.BURIAL_MIN_FRAGMENT_FRAC * full_px, self._open_r(ppu))
            g = cv2.dilate(keep, burial_fx.K3).astype(np.float32)
            self.alpha = self.alpha * g
            self.rgb_pm = self.rgb_pm * g[..., None]
        hsv = cv2.cvtColor(albedo.astype(np.float32)[None, None], cv2.COLOR_RGB2HSV)[0, 0]
        self.meta.update(pitch=pose[0], roll=pose[1], yaw=pose[2], face_down=pose[3], length_px=float(ppu),
                         colour_rgb=[float(c) for c in albedo], colour_hsv=[float(hsv[0]), float(hsv[1]), float(hsv[2])],
                         colour=cinfo, burial={"buried": burial is not None, **(burial or {}), **r["info"]})
        if not cfg.SOIL_BLEND:
            self._v1_dots()

    def _open_r(self, length_px):
        """Opening radius for the burial clean-up: strips thinner than ~2 r px (r = BURIAL_OPEN_FRAC x mine length,
        at least BURIAL_OPEN_PX) left by the clip plane on thin wings / rims are removed."""
        return int(max(self.cfg.BURIAL_OPEN_PX, round(self.cfg.BURIAL_OPEN_FRAC * length_px)))

    def _load_sprite(self, scale):
        cfg, rng = self.cfg, self.rng
        files = assets.sprite_files(cfg)
        if not files:
            raise FileNotFoundError(f"No sprites found in {cfg.MINE_SPRITE_DIR}")
        path = files[int(rng.integers(len(files)))]
        rgb, a = assets.load_sprite(path)
        tw, th = int(a.shape[1] * scale), int(a.shape[0] * scale)
        angle = float(rng.uniform(0, 360))
        self.rgb_pm, self.alpha = edges.resize_rotate(rgb, a, tw, th, angle, cfg.SOFT_EDGES, cfg.DEBRIS_ALPHA_FEATHER)
        self.alpha_full = self.alpha
        self.meta.update(sprite=path.rsplit("/", 1)[-1], angle=angle, length_px=float(max(rgb.shape[:2]) * scale))
        if not cfg.SOIL_BLEND:
            self._v1_dots()

    def _v1_dots(self):
        """v1 _add_surface_dirt: 5-20 opaque brown circles (radius 1-3) centred on non-transparent pixels. The label
        mask is taken before the dots, as in v1."""
        rng = self.sub(8)
        self.alpha_label = self.alpha.copy()
        rgb_pm, alpha = self.rgb_pm.copy(), self.alpha.copy()
        h, w = alpha.shape
        for _ in range(_ri(rng, 5, 20)):
            dx, dy = _ri(rng, 0, w - 1), _ri(rng, 0, h - 1)
            col = np.clip(np.array([80, 60, 40]) + rng.integers(-30, 31, 3), 0, 255) / 255.0
            rad = _ri(rng, 1, 3)
            if alpha[dy, dx] > 0:
                m = np.zeros((h, w), np.uint8)
                cv2.circle(m, (dx, dy), rad, 1, -1)
                m = m.astype(bool)
                rgb_pm[m] = col
                alpha[m] = 1.0
        self.rgb_pm, self.alpha = rgb_pm, alpha

    # --- placement ---
    @property
    def rect(self):
        return (self.x + self.bx0, self.y + self.by0, self.bx1 - self.bx0, self.by1 - self.by0)

    def set_position(self, W, H, centre=None):
        bw, bh = self.bx1 - self.bx0, self.by1 - self.by0
        if centre is not None:
            self.x, self.y = int(centre[0] - bw / 2) - self.bx0, int(centre[1] - bh / 2) - self.by0
            return
        self.x = _ri(self.rng, 0, max(0, W - bw)) - self.bx0
        self.y = _ri(self.rng, 0, max(0, H - bh)) - self.by0

    def collides(self, other, margin):
        ax, ay, aw, ah = self.rect
        bx, by, bw, bh = other.rect
        bx, by, bw, bh = bx - margin // 2, by - margin // 2, bw + margin, bh + margin
        return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah

    # --- drawing ---
    def draw(self, img):
        cfg, sc = self.cfg, self.scene
        h, w = self.alpha.shape
        local = fx.crop_padded(img, self.x, self.y, h, w)       # composite under the mine, before shadow / mine
        buried_mine = self.r is not None and self.meta["burial"]["buried"]
        L = self.meta["length_px"]
        if buried_mine:
            bp = burial_fx.sample_params(self.sub(9), cfg)
            sB = burial_fx.strength_scale(self.meta["burial"]["fraction"])
            rngb = np.random.default_rng(bp["seed"])
            buried = np.clip(self.alpha_full - self.alpha, 0, 1)
            if cfg.BURIAL_DISTURBED_SOIL:   # turned soil on the ground, under shadow and mine
                prgb, pa = burial_fx.disturbed_patch(self.alpha_full, buried, local, L, bp, sB, rngb, cfg)
                fx.over(img, prgb, pa, self.x, self.y)
        if cfg.SHADOWS:
            self._draw_shadow(img)
        rgb_pm, alpha = self.rgb_pm, self.alpha
        if cfg.SOIL_BLEND:
            rgb_pm, info = soil.soil_blend(rgb_pm, alpha, self.alpha_full, local, L, sc["luma"],
                                           soil.sample_soil_params(self.sub(5), cfg), cfg)
            self.meta["soil_blend"] = info
        if not buried_mine:
            fx.over(img, rgb_pm, alpha, self.x, self.y)
            self.visible = alpha.copy()
            return
        p = soil.sample_burial_overlay_params(self.sub(6), cfg)
        if cfg.BURIAL_BERM:
            p["berm_opacity"] *= 0.5            # the shaded ridge below takes over most of the lip
        full = float((self.alpha_full > 0.5).sum())
        for _ in range(4):  # the rough soil line covers a bit more: shrink it until the cap holds
            s_rgb, s_a = soil.burial_overlay(alpha, self.alpha_full, self.r["height"], local, L, p)
            vis = alpha * (1.0 - s_a)
            achieved = float(1 - (vis > 0.5).sum() / max(full, 1))
            if achieved <= cfg.BURIAL_MAX_FRACTION:
                break
            p["edge_noise"] *= 0.5
            p["berm_width_px"] *= 0.6
        else:  # still over the cap: keep soil off the visible mine (only the clip itself hides it)
            s_a = np.where(alpha > 0.5, 0.0, s_a).astype(np.float32)
            s_rgb = s_rgb * (s_a > 0)[..., None]
        # what the soil line leaves visible must not contain slivers / islands either: cover them with soil
        vis = alpha * (1.0 - s_a)
        stages = {"clip": float(1 - (alpha > 0.5).sum() / max(full, 1)),
                  "soil_line": float(1 - (vis > 0.5).sum() / max(full, 1))}
        keep = burial_fx.clean_mask(vis > 0.5, cfg.BURIAL_MIN_FRAGMENT_FRAC * full, self._open_r(L))
        drop = ((alpha > 0.02) & (cv2.dilate(keep, burial_fx.K3) == 0)).astype(np.float32)
        if drop.any():
            soil_col = fx.gblur(local, 1.0) * p["berm_darken"]
            s_rgb = s_rgb * (1 - drop)[..., None] + soil_col * drop[..., None]
            s_a = np.maximum(s_a, drop)
        vis = alpha * (1.0 - s_a)
        stages["fragments"] = float(1 - (vis > 0.5).sum() / max(full, 1))
        core = np.maximum(np.clip(self.alpha_full - alpha, 0, 1), s_a)
        # the ridge / occlusion gradient follow the CLIP line (visible mine against the part cut away by the soil
        # plane, incl. dropped fragments); the noisy soil cover over low rims only roughens the edge
        clip_core = np.maximum(np.clip(self.alpha_full - alpha, 0, 1), drop)
        line, dist = burial_fx.soil_line(vis, clip_core)
        if cfg.BURIAL_DIRTY_EXPOSED:
            rgb_pm = burial_fx.dirty_exposed(rgb_pm, alpha, dist, local, L, bp, sB, rngb, cfg)
        fx.over(img, rgb_pm, alpha, self.x, self.y)
        fx.over(img, s_rgb, s_a, self.x, self.y)
        cover = np.zeros_like(alpha)
        if cfg.BURIAL_BERM and line.any():
            r_rgb, r_a, r_sh = burial_fx.berm_ridge(dist, core, vis, local, L, sc["sun"], bp, sB, rngb, cfg)
            fx.darken(img, fx.shadow_factor(r_sh, sc["sun"]["shadow_strength"], sc["sun"]["shadow_tint"]), self.x, self.y)
            fx.over(img, r_rgb, r_a, self.x, self.y)
            cover = np.maximum(cover, r_a)
        if cfg.BURIAL_CLODS and line.any():
            for c_rgb, c_a, cx, cy, f, pad in burial_fx.clods(cfg, line, L, sc["sun"], bp, sB, rngb, local):
                if cfg.SHADOWS:
                    fx.darken(img, f, self.x + cx - pad, self.y + cy - pad)
                fx.over(img, c_rgb, c_a, self.x + cx, self.y + cy)
                tmp = np.zeros_like(alpha)
                fx.accumulate_alpha(tmp, c_a, cx, cy)
                cover = np.maximum(cover, tmp)
        vis_final = vis * (1.0 - cover)
        achieved = float(1 - (vis_final > 0.5).sum() / max(full, 1))
        if achieved > cfg.BURIAL_MAX_FRACTION:
            # ridge / clods would hide too much: they are drawn as they are, but for the visible mask (label) they
            # count with the largest weight f that keeps the cap (bisection), i.e. as partly see-through cover
            lo, hi = 0.0, 1.0
            for _ in range(8):
                f = (lo + hi) / 2
                if 1 - (vis * (1 - f * cover) > 0.5).sum() / max(full, 1) > cfg.BURIAL_MAX_FRACTION:
                    hi = f
                else:
                    lo = f
            vis_final = vis * (1.0 - lo * cover)
            achieved = float(1 - (vis_final > 0.5).sum() / max(full, 1))
        # ridge / clods can split off tiny bits of the visible mask: the label mask drops them like any fragment
        keep = burial_fx.clean_mask(vis_final > 0.5, cfg.BURIAL_MIN_FRAGMENT_FRAC * full, cfg.BURIAL_OPEN_PX)
        vis_final = vis_final * cv2.dilate(keep, burial_fx.K3).astype(np.float32)
        achieved = float(1 - (vis_final > 0.5).sum() / max(full, 1))
        stages["final"] = achieved
        self.meta["burial"]["hidden_by_stage"] = stages
        self.meta["burial"]["cap_exceeded"] = bool(achieved > cfg.BURIAL_MAX_FRACTION + 0.01)
        self.visible = vis_final
        self.meta["burial"].update({k: v for k, v in p.items() if k != "noise_seed"})
        self.meta["burial"].update(achieved=achieved, realism={k: v for k, v in bp.items() if k != "seed"}, scale=sB)
        # soil-line zone for over-layer blades (lifted where they cross the berm, half-covered where on soil)
        rw = max(1.5, bp["ridge_width_frac"] * L) * 1.5
        sc.setdefault("soil_zones", []).append({
            "x": self.x, "y": self.y, "line_w": np.clip(1 - dist / rw, 0, 1).astype(np.float32),
            "core": (core > 0.5).astype(np.float32) * (vis < 0.5), "lift_px": float(np.clip(0.04 * L * sB, 1.5, 6.0))})

    def _draw_shadow(self, img):
        cfg, sun = self.cfg, self.scene["sun"]
        if self.r is None:  # sprite mine: 2D approximation like rocks
            f, pad = shadows.debris_shadow(self.alpha, cfg.MINE_HEIGHT_FRAC * self.meta["length_px"], sun,
                                           sun["shadow_strength"], cfg)
            fx.darken(img, f, self.x - pad, self.y - pad)
            return
        ao_s, ao_sig = shadows.sample_ao(self.sub(7), cfg)
        length = self.r["info"]["shadow_length_px"]
        f, sigma = shadows.mine_shadow(self.r["shadow"], self.alpha, length, sun, ao_s, ao_sig, cfg)
        fx.darken(img, f, self.x, self.y)
        self.meta["shadow"] = {"length_px": float(length), "penumbra_sigma_px": float(sigma), "contact_ao": ao_s}

    def label(self, W, H, occlusion):
        """YOLO box. v1: un-occluded mask. LABEL_VISIBLE_MASK: mask after burial soil and overgrowth.
        pygame-Rect integer centre arithmetic like v1. -> [0, xc, yc, w, h] or None."""
        cfg = self.cfg
        if cfg.LABEL_VISIBLE_MASK:
            vis = np.zeros_like(self.visible)
            r = fx.clip_region(H, W, self.x, self.y, vis.shape[0], vis.shape[1])
            if r is not None:
                d, s = r
                vis[s] = self.visible[s] * (1.0 - occlusion[d]) if occlusion is not None else self.visible[s]
            m = vis > cfg.LABEL_ALPHA_THRESHOLD
            before = max(int((self.visible > cfg.LABEL_ALPHA_THRESHOLD).sum()), 1)
            self.meta["overgrowth_occluded_fraction"] = float(1 - m.sum() / before)
            full = max(int((self.alpha_full > cfg.LABEL_ALPHA_THRESHOLD).sum()), 1)
            self.meta["visible_px"], self.meta["visible_fraction"] = int(m.sum()), float(m.sum() / full)
            if m.sum() < cfg.LABEL_MIN_VISIBLE_PX:
                return None
        else:
            m = getattr(self, "alpha_label", self.alpha) > cfg.LABEL_ALPHA_THRESHOLD
        ys, xs = np.nonzero(m)
        if len(xs) == 0:
            return None
        x0, y0 = int(xs.min()) + self.x, int(ys.min()) + self.y
        bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        return [0, (x0 + bw // 2) / W, (y0 + bh // 2) / H, bw / W, bh / H]
