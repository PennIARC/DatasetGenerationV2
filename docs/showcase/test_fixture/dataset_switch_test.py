#!/usr/bin/env python3
"""Dataset registry / switching test for scripts/serve_dataset_view.py + the "Dataset: live sample" tab (ADR 0018).

    python3 test_fixture/dataset_switch_test.py WORK_DIR [--port 8811]

Builds WORK_DIR/root with two fake datasets (a: 30 images 640x640, older plan; b: 12 images 960x960, newer plan with
variant "wide"), starts ONE server with --datasets-root WORK_DIR/root, checks the API (registry, default = newest,
?ds= routing, unknown / malformed ids, thumbnails, a third dataset appearing without restart), then switches datasets
in headless Chrome through the dropdown. Always stops the server it started.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = HERE.parent
REPO = SC.parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MANIFESTS = ["manifest_v1.json", "manifest_v2.json", "manifest_review.json", "manifest_params.json",
             "manifest_dataset.json", "manifest_training.json"]

TEST = r"""
<script>
(function(){
var R = [];
function ok(name, cond, info){ R.push((cond ? "PASS " : "FAIL ") + name + (info !== undefined ? " [" + info + "]" : "")); }
var q = function(s){ return document.querySelector(s); }, qa = function(s){ return [].slice.call(document.querySelectorAll(s)); };
window.addEventListener("error", function(e){ R.push("FAIL js error: " + e.message); });
function done(){ var p = document.createElement("pre"); p.id = "results"; p.textContent = R.join("\n"); document.body.appendChild(p); }
function wait(cond, ms, then){ var t0 = Date.now(); (function loop(){ if (cond() || Date.now() - t0 > ms) then(); else setTimeout(loop, 100); })(); }
function imgsDone(n){ var im = qa(".dgrid .gcard img"); return im.length === n && im.every(function(i){ return i.complete && i.naturalWidth > 0; }); }
wait(function(){ return imgsDone(12); }, 15000, function(){
  try {
    var sel = q(".dspick select");
    ok("dataset dropdown shown", sel && !q(".dspick").hidden);
    ok("3 datasets listed", sel && sel.options.length === 3, sel && sel.options.length);
    ok("default = newest (ds_b)", sel && sel.value === "ds_b", sel && sel.value);
    ok("option label has variant + size", sel && /ds_b · wide · 960×960/.test(sel.options[sel.selectedIndex].textContent), sel && sel.options[sel.selectedIndex].textContent);
    ok("description line", /mine scale 0\.10-0\.40 in 5 bins/.test(q(".dspick").textContent), q(".dspick .s").textContent);
    ok("ds_b count", /^12 \/ 3000 images/.test(q(".big").textContent), q(".big").textContent);
    var im = qa(".dgrid .gcard img");
    ok("960 thumbnails are native 960", im.every(function(i){ return i.naturalWidth === 960 && i.naturalHeight === 960; }), im[0].naturalWidth + "x" + im[0].naturalHeight);
    ok("thumb urls carry ds", im.every(function(i){ return /[?&]ds=ds_b/.test(i.getAttribute("src")); }));
    var fr = qa(".dgrid .gcard .thumb").map(function(t){ var r = t.getBoundingClientRect(); return r.width / r.height; });
    ok("square frames", fr.every(function(r){ return Math.abs(r - 1) < 0.03; }), fr[0].toFixed(3));
    ok("no horizontal scroll", document.documentElement.scrollWidth <= window.innerWidth);
    sel.value = "ds_a"; sel.dispatchEvent(new Event("change"));
    wait(function(){ return imgsDone(24) && /^30 /.test(q(".big").textContent); }, 15000, function(){
      var im2 = qa(".dgrid .gcard img");
      ok("switched to ds_a without reload", /^30 \/ 3000 images/.test(q(".big").textContent), q(".big").textContent);
      ok("24 cards of ds_a", im2.length === 24, im2.length);
      ok("ds_a images are 640", im2.every(function(i){ return i.naturalWidth === 640; }), im2[0].naturalWidth);
      ok("ds_a urls carry ds", im2.every(function(i){ return /[?&]ds=ds_a/.test(i.getAttribute("src")); }));
      ok("choice remembered", localStorage.getItem("showcase-dsid") === "ds_a");
      ok("dataset folder tile", /root\/ds_a/.test(q(".stats").textContent));
      var b = qa(".dgrid .bbox");
      ok("boxes present", b.length > 0, b.length);
      sel.value = "ds_c"; sel.dispatchEvent(new Event("change"));
      wait(function(){ return /No images yet/.test(q(".dsview").textContent); }, 8000, function(){
        ok("empty ds_c shows the empty state", /No images yet/.test(q(".dsview").textContent) && qa(".dgrid").length === 0);
        done();
      });
    });
  } catch(e){ R.push("FAIL exception: " + e.message); done(); }
});
})();
</script>
"""


def get(port, path):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def chrome(url, profile, size="1400,1800"):
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--window-size=" + size,
            "--user-data-dir=" + profile, "--virtual-time-budget=30000", "--run-all-compositor-stages-before-draw"]
    try:
        out = subprocess.run(args + ["--dump-dom", url], capture_output=True, text=True, timeout=240).stdout
    except subprocess.TimeoutExpired:
        return ["FAIL headless Chrome timed out"]
    s = out.find('<pre id="results">')
    if s < 0:
        return ["FAIL no results (page did not finish)"]
    import html
    return html.unescape(out[s + len('<pre id="results">'):out.find("</pre>", s)]).splitlines()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--port", type=int, default=8811)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    root = work / "root"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(work / "thumbs", ignore_errors=True)
    mk = HERE / "make_fake_dataset.py"
    subprocess.run([sys.executable, str(mk), str(root / "ds_a"), "--n", "30", "--size", "640x640"], check=True)
    subprocess.run([sys.executable, str(mk), str(root / "ds_b"), "--n", "12", "--size", "960x960"], check=True)
    pb = root / "ds_b" / "plan" / "plan.json"
    pb.write_text(json.dumps({"variant": "wide", "output_crop": [960, 960], "scene_zoom_coupling": False,
                              "n_images": 3000, "split": {"train": 2700, "val": 300}, "n_mines_planned": 10800,
                              "edges": {"scale": [0.1, 0.132, 0.174, 0.23, 0.303, 0.4]},
                              "counts": {"n_mines": {str(i): 1 for i in range(9)}}}))
    old = time.time() - 3600
    os.utime(root / "ds_a" / "plan" / "plan.json", (old, old))
    (root / ".thumb_cache").mkdir()            # dot folders are never datasets
    (root / "not_a_dataset").mkdir()           # no plan/ and no images/
    srv = subprocess.Popen([sys.executable, str(REPO / "scripts" / "serve_dataset_view.py"), "--port", str(a.port),
                            "--datasets-root", str(root), "--cache-dir", str(work / "thumbs")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    res, page = [], SC / "_ds_switch_test.html"
    profile = tempfile.mkdtemp(prefix="dsswitch_chrome_")

    def ok(name, cond, info=""):
        res.append(("PASS " if cond else "FAIL ") + name + (" [%s]" % (info,) if info != "" else ""))
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/datasets" % a.port, timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        c, b = get(a.port, "/api/datasets")
        d = json.loads(b)
        ids = [x["id"] for x in d["datasets"]]
        ok("registry lists ds_a, ds_b only", c == 200 and sorted(ids) == ["ds_a", "ds_b"], ids)
        ok("default = newest plan (ds_b)", d["default"] == "ds_b", d["default"])
        xb = [x for x in d["datasets"] if x["id"] == "ds_b"][0]
        ok("ds_b metadata", xb["variant"] == "wide" and xb["crop"] == [960, 960] and xb["has_images"]
           and xb["mines_per_image"] == [0, 8] and xb["scale_bins"] == 5, xb)
        c, b = get(a.port, "/api/dataset-info")
        ok("default info = ds_b (12)", json.loads(b)["count"] == 12 and json.loads(b)["dataset_id"] == "ds_b")
        c, b = get(a.port, "/api/dataset-info?ds=ds_a")
        ok("?ds=ds_a info (30, 640)", json.loads(b)["count"] == 30 and json.loads(b)["resolution"] == [640, 640],
           json.loads(b)["resolution"])
        c, b = get(a.port, "/api/dataset-info?ds=nope")
        ok("unknown ds -> 404", c == 404, c)
        c, b = get(a.port, "/api/sample?n=5&seed=1&ds=..%2Fds_a")
        ok("malformed ds -> 404", c == 404, c)
        c, b = get(a.port, "/api/sample?n=5&seed=1&ds=ds_a")
        it = json.loads(b)["items"][0]
        ok("sample urls carry ds", "ds=ds_a" in it["thumb"] and "ds=ds_a" in it["image"] and "ds=ds_a" in it["meta_url"], it["thumb"])
        c, body = get(a.port, it["thumb"])
        ok("thumb via ds", c == 200 and body[:2] == b"\xff\xd8", c)
        from io import BytesIO
        from PIL import Image
        wa = Image.open(BytesIO(body)).size
        c, body_b = get(a.port, it["image"].replace("ds=ds_a", "ds=ds_b"))
        wb = Image.open(BytesIO(body_b)).size if c == 200 else None
        ok("same file name is served from the chosen dataset (640 in ds_a, 960 or absent in ds_b)",
           wa == (640, 640) and (c == 404 or wb == (960, 960)), (wa, c, wb))
        c, _ = get(a.port, it["meta_url"])
        ok("meta via ds", c == 200, c)
        c, _ = get(a.port, "/dataset/meta/%s.json?ds=zzz" % it["name"])
        ok("file route with unknown ds -> 404", c == 404, c)
        # a third dataset appears without restarting
        (root / "ds_c" / "plan").mkdir(parents=True)
        (root / "ds_c" / "plan" / "plan.json").write_text(json.dumps({"n_images": 3000}))
        os.utime(root / "ds_c" / "plan" / "plan.json", (old - 10, old - 10))
        time.sleep(2.2)
        d = json.loads(get(a.port, "/api/datasets")[1])
        ok("new folder appears without restart", sorted(x["id"] for x in d["datasets"]) == ["ds_a", "ds_b", "ds_c"]
           and d["default"] == "ds_b", [x["id"] for x in d["datasets"]])
        if Path(CHROME).exists():
            subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", *MANIFESTS, "--out", str(page)],
                           check=True, capture_output=True)
            page.write_text(page.read_text().replace("</body>", TEST + "</body>"))
            res += ["-- chrome: switch datasets"] + chrome("http://127.0.0.1:%d/%s#dataset" % (a.port, page.name), profile)
        else:
            res.append("-- Chrome not found: browser part skipped")
    finally:
        srv.terminate()
        try:
            srv.wait(5)
        except subprocess.TimeoutExpired:
            srv.kill()
        page.unlink(missing_ok=True)
        shutil.rmtree(profile, ignore_errors=True)
    print("\n".join(res))
    fails = [l for l in res if l.startswith("FAIL")]
    print("%d checks, %d failed" % (sum(l[:4] in ("PASS", "FAIL") for l in res), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
