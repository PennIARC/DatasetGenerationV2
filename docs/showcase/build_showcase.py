#!/usr/bin/env python3
"""Build a single self-contained showcase HTML page from one or more manifests.

Usage: python3 build_showcase.py [--manifests manifest_v1.json manifest_v2.json]
                                 [--out showcase.html] [--embed]
Image paths in manifests are relative to this directory (docs/showcase/).
"""
import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TABS = ["v1: original generator", "v2: new realism features", "Review: buried mines",
                "Dataset v2: parameters", "Dataset: live sample"]
OPTIONAL_MANIFESTS = ["manifest_review.json", "manifest_params.json", "manifest_dataset.json"]


def load_manifest(path, index):
    """Return a list of page dicts; a stub page with 'missing' set on failure."""
    fallback_id = "v%d" % (index + 1)
    tab = DEFAULT_TABS[index] if index < len(DEFAULT_TABS) else fallback_id
    stub = {"id": fallback_id, "tab": tab, "title": tab, "intro": "", "glossary": {}, "features": []}
    if not path.is_file():
        stub["missing"] = "Manifest %s was not found. Run the image generator for this page, then rebuild." % path.name
        return [stub]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pages = data["pages"]
        if not isinstance(pages, list) or not pages:
            raise ValueError("'pages' is empty")
    except Exception as exc:  # malformed manifest: do not fail the whole build
        stub["missing"] = "Manifest %s could not be read (%s)." % (path.name, exc)
        return [stub]
    out = []
    for n, p in enumerate(pages):
        if not isinstance(p, dict):
            continue
        p = dict(p)
        p.setdefault("id", "p%d_%d" % (index, n))
        out.append(p)
    return out


def iter_image_slots(page):
    """Yield (dict, key) for every image reference in a page."""
    for it in page.get("items") or []:
        if isinstance(it, dict):
            yield it, "image"
            yield it, "thumb"
    for f in page.get("features") or []:
        if not isinstance(f, dict):
            continue
        for o in f.get("options") or []:
            if isinstance(o, dict):
                yield o, "image"
        if isinstance(f.get("figure"), dict):
            yield f["figure"], "image"
        for b in f.get("before_after") or []:
            if isinstance(b, dict):
                yield b, "before"
                yield b, "after"


def to_data_uri(path):
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode("ascii"))


def process_images(pages, embed):
    """Embed images (if requested) and blank out references to missing files.
    Returns (found, missing) counts."""
    found = missing = 0
    cache = {}
    assets = {}
    for page in pages:
        for d, key in iter_image_slots(page):
            ref = d.get(key)
            if not isinstance(ref, str) or not ref.strip():
                continue
            if ref.startswith("data:"):
                continue
            p = (HERE / ref).resolve()
            if not p.is_file():
                missing += 1
                print("warning: missing image %s" % ref, file=sys.stderr)
                if embed:
                    d[key] = ""  # placeholder box
                continue  # non-embed: keep path; browser onerror shows placeholder too
            found += 1
            if embed:
                if p not in cache:
                    cache[p] = "asset:%d" % len(cache)
                    assets[cache[p]] = to_data_uri(p)  # stored once, referenced by key
                d[key] = cache[p]
    return found, missing, assets


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifests", nargs="+", default=None,
                    help="manifest files, in tab order (relative to docs/showcase/ unless absolute/existing); "
                         "default: manifest_v1.json manifest_v2.json (+ manifest_review/params/dataset.json if they exist)")
    ap.add_argument("--out", default="showcase.html")
    ap.add_argument("--embed", action="store_true", help="inline images as base64 data URIs")
    args = ap.parse_args()

    if args.manifests is None:
        args.manifests = ["manifest_v1.json", "manifest_v2.json"] + [
            m for m in OPTIONAL_MANIFESTS if (HERE / m).is_file()]
    pages = []
    for i, m in enumerate(args.manifests):
        mp = Path(m)
        if not mp.is_absolute() and not mp.exists():
            mp = HERE / m
        pages.extend(load_manifest(mp, i))

    found, missing, assets = process_images(pages, args.embed)

    payload = json.dumps({"pages": pages, "assets": assets}, ensure_ascii=False)
    # keep the JSON safe inside a <script> element
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") \
                     .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    if "__DATA__" not in tpl:
        sys.exit("template.html has no __DATA__ placeholder")
    html = tpl.replace("__DATA__", payload)

    out = Path(args.out)
    if not out.is_absolute():
        out = HERE / out
    out.write_text(html, encoding="utf-8")
    print("wrote %s (%.1f KB): %d pages, %d images found, %d missing%s"
          % (out, len(html) / 1024, len(pages), found, missing, ", embedded" if args.embed else ""))


if __name__ == "__main__":
    main()
