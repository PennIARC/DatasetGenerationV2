"""Asset discovery and loading (backgrounds, rocks, grass debris, dirt snippets).

Two cut-out formats are accepted:
  * v1 photos of an object on a white / checkerboard background with no real alpha -> Otsu threshold
    (object = darker than the background), as v1 did;
  * RGBA PNGs with a real alpha channel (assets_new/) -> the alpha is used directly.
A file counts as "real alpha" when at least 1% of its pixels have alpha < 128.

Each asset kind has several source folders with sampling weights (controlPanel *_SOURCES); a source is picked
by weight among the folders that exist and are non-empty, then a file uniformly inside it. With NEW_ASSETS off
only the first (v1) source is used. Decoded files are cached per process (no mine colours are cached here).
"""
import os

import cv2
import numpy as np

from config import asset_path

_CACHE = {}
EXTS = (".jpg", ".png", ".jpeg")


def _cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def list_files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(EXTS))


def sources(cfg, kind):
    """kind in {'BACKGROUND', 'ROCK', 'GRASS', 'DIRT', 'LEAF'} -> [(files, weight), ...] (existing, non-empty)."""
    srcs = getattr(cfg, f"{kind}_SOURCES")
    if not cfg.NEW_ASSETS:
        srcs = srcs[:1] if kind not in ("DIRT", "LEAF") else []
    out = []
    for folder, w in srcs:
        files = _cached(("ls", asset_path(cfg, folder)), lambda f=folder: list_files(asset_path(cfg, f)))
        if files and w > 0:
            out.append((files, float(w)))
    return out


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def repo_rel(path):
    """Path relative to the repository root (the audit list's convention), normalised."""
    return os.path.normpath(os.path.relpath(os.path.abspath(path), REPO))


def audit_lists(cfg):
    """docs/asset_audit/exclude.json -> (hard_exclude set, review set) of file names."""
    def load():
        import json
        p = asset_path(cfg, cfg.ASSET_AUDIT_PATH)
        if not os.path.isfile(p):
            return set(), set()
        with open(p) as f:
            d = json.load(f)
        # matched by file NAME (assets may have been moved, e.g. to a _rejected/ folder; missing files are simply
        # never listed, so they count as excluded); names are unique across the asset folders
        return ({os.path.basename(x) for x in d.get("hard_exclude", [])},
                {os.path.basename(x) for x in d.get("review", [])})
    return _cached(("audit", asset_path(cfg, cfg.ASSET_AUDIT_PATH)), load)


def audit_status(cfg, path):
    """'exclude' | 'review' | 'ok' (always 'ok' with ASSET_AUDIT_FILTER off, e.g. v1 mode)."""
    if not cfg.ASSET_AUDIT_FILTER or not path:
        return "ok"
    hard, review = audit_lists(cfg)
    r = os.path.basename(path)
    return "exclude" if r in hard else "review" if r in review else "ok"


def audit_weight(cfg, path):
    st = audit_status(cfg, path)
    return 0.0 if st == "exclude" else float(cfg.ASSET_REVIEW_WEIGHT) if st == "review" else 1.0


def _weighted_sources(cfg, kind):
    """[(files, cumulative file weights, source weight)] with audit weights applied; sources with no usable file
    are dropped (the remaining source weights renormalise)."""
    key = ("wsrc", kind, bool(cfg.NEW_ASSETS), bool(cfg.ASSET_AUDIT_FILTER), float(cfg.ASSET_REVIEW_WEIGHT),
           tuple(getattr(cfg, f"{kind}_SOURCES")))

    def build():
        out = []
        for files, w in sources(cfg, kind):
            fw = np.array([audit_weight(cfg, f) for f in files])
            if fw.sum() > 0:
                out.append((files, np.cumsum(fw), w))
        return out
    return _cached(key, build)


def pick_file(rng, cfg, kind):
    """Weighted source, then a file (uniform, or audit-weighted with ASSET_AUDIT_FILTER: hard-excluded files never,
    'review' files x ASSET_REVIEW_WEIGHT). Two draws are always consumed. -> path or None."""
    src = _weighted_sources(cfg, kind)
    u, v = rng.random(), rng.random()
    if not src:
        return None
    w = np.cumsum([s[2] for s in src])
    files, cw, _ = src[min(int(np.searchsorted(w, u * w[-1], side="right")), len(src) - 1)]
    return files[min(int(np.searchsorted(cw, v * cw[-1], side="right")), len(files) - 1)]


def load_rgb(path):
    """-> uint8 RGB (alpha, if any, is dropped)."""
    return _cached(("rgb", path), lambda: cv2.cvtColor(cv2.imread(path, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB))


def _load_cutout(path, erode):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED) if path else None
    if im is None:  # missing / unreadable (e.g. an asset folder being regenerated): callers skip the element
        print(f"[assets] cannot read {path}; skipped")
        return None
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    if im.dtype != np.uint8:
        im = (im / 257).astype(np.uint8)
    bgr = im[..., :3]
    rgb = cv2.cvtColor(np.ascontiguousarray(bgr), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    if im.shape[2] == 4 and (im[..., 3] < 128).mean() > 0.01:
        alpha = im[..., 3].astype(np.float32) / 255.0
        return rgb, alpha, "alpha"
    gray = cv2.cvtColor(np.ascontiguousarray(bgr), cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if erode:  # drop the 1-px rim contaminated by the white photo background (would show as a light halo)
        mask = cv2.erode(mask, np.ones((3, 3), np.uint8))
    return rgb, mask.astype(np.float32) / 255.0, "otsu"


def load_cutout(path, erode=False):
    """-> (rgb float32 (h, w, 3), alpha float32 (h, w), 'alpha' | 'otsu'), or None if the file cannot be read."""
    return _cached(("cut", path, bool(erode)), lambda: _load_cutout(path, erode))


def load_sprite(path):
    """v1 pre-rendered mine sprite -> (rgb, alpha) float32 (v1 mode only)."""
    def load():
        im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        return (cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2RGB).astype(np.float32) / 255,
                im[..., 3].astype(np.float32) / 255)
    return _cached(("sprite", path), load)


def sprite_files(cfg):
    return _cached(("ls", asset_path(cfg, cfg.MINE_SPRITE_DIR)), lambda: list_files(asset_path(cfg, cfg.MINE_SPRITE_DIR)))


def dirt_index(cfg):
    """assets_new/dirt/index.json -> {basename: {kind: clod | patch | dust, opacity: [lo, hi], casts_shadow}}."""
    import json

    def load():
        out = {}
        for folder, _ in cfg.DIRT_SOURCES:
            p = os.path.join(asset_path(cfg, folder), "index.json")
            if os.path.isfile(p):
                with open(p) as f:
                    for it in json.load(f).get("items", []):
                        out[it["file"]] = it
        return out
    return _cached(("dirtindex",), load)
