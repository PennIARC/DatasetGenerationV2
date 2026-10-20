#!/usr/bin/env python3
"""End-to-end test of the "Dataset: live sample" tab + scripts/serve_dataset_view.py (macOS Google Chrome, headless).

    python3 test_fixture/dataset_view_test.py WORK_DIR [--port 8799]

Builds a fake dataset (make_fake_dataset.py) in WORK_DIR/fake_ds and an empty one in WORK_DIR/empty_ds, starts two
servers (PORT, PORT+1) with their thumbnail cache in WORK_DIR, loads the page in headless Chrome with an appended
test script, prints PASS/FAIL lines, saves screenshots in WORK_DIR, and always stops the servers.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = HERE.parent
REPO = SC.parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MANIFESTS = ["manifest_v1.json", "manifest_v2.json", "manifest_review.json", "manifest_params.json", "manifest_dataset.json"]

TEST = r"""
<script>
(function(){
var R = [];
function ok(name, cond, info){ R.push((cond ? "PASS " : "FAIL ") + name + (info !== undefined ? " [" + info + "]" : "")); }
var q = function(s){ return document.querySelector(s); }, qa = function(s){ return [].slice.call(document.querySelectorAll(s)); };
window.addEventListener("error", function(e){ R.push("FAIL js error: " + e.message); });
function btn(re){ return qa("button").filter(function(b){ return re.test(b.textContent); })[0]; }
function done(){ var p = document.createElement("pre"); p.id = "results"; p.textContent = R.join("\n"); document.body.appendChild(p); }
var MODE = "__MODE__";
function wait(cond, ms, then){ var t0 = Date.now(); (function loop(){ if (cond() || Date.now() - t0 > ms) then(); else setTimeout(loop, 100); })(); }
if (MODE === "file" || MODE === "empty"){
  wait(function(){ return MODE === "file" ? q(".dsview .empty") : (q(".badge") && !/loading/.test(q(".badge").textContent) && /No images yet/.test(q(".dsview").textContent)); }, 8000, function(){
    ok("five tabs", qa(".tab").length === 5, qa(".tab").length);
    ok("dataset tab selected", /Dataset: live/.test(q('[aria-selected="true"]').textContent));
    var t = q(".dsview").textContent;
    if (MODE === "file") ok("file:// message with command + link", /serve_dataset_view\.py/.test(t) && q(".dsview a[href^='http://127.0.0.1:8765']"), t.slice(0, 120));
    else ok("empty state", /No images yet/.test(t) && /no images yet/.test(q(".badge").textContent) && /^0 \/ 3000/.test(q(".big").textContent), q(".big").textContent + " | " + q(".badge").textContent);
    done();
  });
  return;
}
wait(function(){ return qa(".dgrid .gcard img").length === 24 && qa(".dgrid .gcard img").every(function(i){ return i.complete; }); }, 15000, function(){
  try {
    ok("five tabs", qa(".tab").length === 5, qa(".tab").length);
    ok("no horizontal page scroll", document.documentElement.scrollWidth <= window.innerWidth, document.documentElement.scrollWidth + " <= " + window.innerWidth);
    ok("info count", /^30 \/ 3000 images/.test(q(".big").textContent), q(".big").textContent);
    ok("status badge", /generating/.test(q(".badge").textContent), q(".badge").textContent);
    ok("stat tiles", qa(".stat").length >= 9 && /__W__ × __H__/.test(q(".stats").textContent) && /27 \/ 3/.test(q(".stats").textContent), qa(".stat").length);
    ok("storage shown", /MB/.test(q(".stats").textContent));
    var cards = qa(".dgrid .gcard");
    ok("24 cards", cards.length === 24, cards.length);
    var imgs = qa(".dgrid .gcard img");
    ok("thumbs are server thumbnails (960 px, or the native image when smaller)", imgs.every(function(i){ return /^\/thumb\//.test(i.getAttribute("src")) && i.naturalWidth === Math.min(960, __W__); }), imgs.map(function(i){ return i.naturalWidth; }).slice(0, 4).join(","));
    var th = qa(".dgrid .gcard .thumb").map(function(t){ var r = t.getBoundingClientRect(); return r.width / r.height; });
    ok("card frame follows the image aspect (__W__:__H__)", th.every(function(r){ return Math.abs(r - __W__ / __H__) < 0.03; }), th.slice(0, 3).map(function(r){ return r.toFixed(3); }).join(","));
    var boxes = qa(".dgrid .bbox");
    ok("boxes drawn", boxes.length > 24, boxes.length);
    ok("boxes visible by default", getComputedStyle(boxes[0]).display === "block");
    ok("meta line", /seed 2026:\d+ · \d+ mines? · (train|val)/.test(q(".dgrid .gm").textContent), q(".dgrid .gm").textContent);
    btn(/^Boxes:/).click();
    ok("toggle hides boxes", getComputedStyle(boxes[0]).display === "none" && btn(/^Boxes:/).textContent === "Boxes: off");
    btn(/^Boxes:/).click();
    ok("toggle shows boxes again", getComputedStyle(boxes[0]).display === "block");
    var par = q(".dgrid .gpar"); ok("params shown", getComputedStyle(par).display !== "none" && /sun_el=/.test(par.textContent), par.textContent.slice(0, 60));
    btn(/^Parameters:/).click(); ok("params hidden", getComputedStyle(q(".dgrid .gpar")).display === "none");
    btn(/^Parameters:/).click();
    var range = q('input[aria-label="cards per row"]'); range.value = "6"; range.dispatchEvent(new Event("input"));
    ok("cards per row", q(".dgrid").style.getPropertyValue("--cols") === "6" && getComputedStyle(q(".dgrid")).gridTemplateColumns.split(" ").length === 6);
    var aspect = imgs[0].parentNode.getBoundingClientRect(); ok("card image __W__:__H__", Math.abs(aspect.width / aspect.height - __W__ / __H__) < 0.05, (aspect.width / aspect.height).toFixed(3));
    var seed1 = /seed (\d+)/.exec(q(".counts").textContent)[1];
    q(".dgrid .thumb").click();
    ok("lightbox open with boxes", q("#lb").classList.contains("open") && q("#lbStage .lbwrap.showbox") && qa("#lbStage .bbox").length > 0 && /^\/dataset\/images\//.test(q("#lbStage img").getAttribute("src")));
    document.dispatchEvent(new KeyboardEvent("keydown", {key: "b", bubbles: true}));
    ok("b toggles boxes in lightbox", !q("#lbStage .lbwrap").classList.contains("showbox") && btn(/^Boxes:/).textContent === "Boxes: off");
    document.dispatchEvent(new KeyboardEvent("keydown", {key: "b", bubbles: true}));
    document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
    ok("lightbox closes", !q("#lb").classList.contains("open"));
    btn(/^Resample/).click();
    wait(function(){ var m = /seed (\d+)/.exec(q(".counts").textContent); return m && m[1] !== seed1; }, 5000, function(){
      ok("resample gives a new seed", /seed (\d+)/.exec(q(".counts").textContent)[1] !== seed1, q(".counts").textContent);
      ok("auto-refresh on by default", btn(/^Auto-refresh/).getAttribute("aria-pressed") === "true");
      btn(/^Auto-refresh/).click(); ok("auto-refresh toggles off", btn(/^Auto-refresh/).textContent === "Auto-refresh: off");
      btn(/^Auto-refresh/).click();
      window.__shot = 1;
      /* other tabs still work */
      location.hash = "#v1";
      setTimeout(function(){
        ok("v1 tab renders feature cards", qa("main .card").length > 0 && !q(".dsview"), qa("main .card").length);
        location.hash = "#burial_review_2";
        setTimeout(function(){
          ok("review grid tab renders", qa(".gcard").length > 0, qa(".gcard").length);
          location.hash = "#dataset";
          wait(function(){ return qa(".dgrid .gcard").length === 24; }, 5000, function(){
            ok("back to dataset tab", qa(".dgrid .gcard").length === 24);
            done();
          });
        }, 300);
      }, 300);
    });
  } catch(e){ R.push("FAIL exception: " + e.message); done(); }
});
})();
</script>
"""


def chrome(url, shot=None, size="1400,1800"):
    args = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--window-size=" + size,
            "--virtual-time-budget=20000", "--run-all-compositor-stages-before-draw"]
    try:
        out = subprocess.run(args + ["--dump-dom", url], capture_output=True, text=True, timeout=240).stdout
    except subprocess.TimeoutExpired:
        return ["FAIL headless Chrome timed out"]
    if shot:   # optional; headless screenshots can stall under heavy CPU load
        try:
            subprocess.run(args + ["--screenshot=" + str(shot), url], capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            print("note: screenshot %s timed out (ignored)" % Path(shot).name)
    s = out.find('<pre id="results">')
    if s < 0:
        return ["FAIL no results (page did not finish)"]
    import html
    return html.unescape(out[s + len('<pre id="results">'):out.find("</pre>", s)]).splitlines()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--size", default="1920x1080", help="fake image size WxH (e.g. 640x640 for the zoomed dataset)")
    a = ap.parse_args()
    W, H = (int(v) for v in a.size.lower().split("x"))
    if not Path(CHROME).exists():
        sys.exit("Chrome not found; skipping")
    work = Path(a.work).resolve()
    for d in ("fake_ds", "empty_ds", "thumbs"):
        shutil.rmtree(work / d, ignore_errors=True)
    (work / "empty_ds").mkdir(parents=True)
    subprocess.run([sys.executable, str(HERE / "make_fake_dataset.py"), str(work / "fake_ds"), "--n", "30", "--partial",
                    "--size", a.size], check=True)
    (work / "empty_ds" / "plan").mkdir()
    (work / "empty_ds" / "plan" / "plan.json").write_text(json.dumps({"n_images": 3000}))
    pages = {}
    for mode in ("full", "empty", "file"):
        p = SC / ("_ds_test_%s.html" % mode)
        subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", *MANIFESTS, "--out", str(p)],
                       check=True, capture_output=True)
        p.write_text(p.read_text().replace("</body>", TEST.replace("__MODE__", mode).replace("__W__", str(W)).replace("__H__", str(H)) + "</body>"))
        pages[mode] = p
    srv = [subprocess.Popen([sys.executable, str(REPO / "scripts" / "serve_dataset_view.py"), "--port", str(a.port + i),
                             "--dataset-dir", str(work / d), "--cache-dir", str(work / "thumbs")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i, d in enumerate(("fake_ds", "empty_ds"))]
    res = []
    try:
        for i in range(50):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/dataset-info" % a.port, timeout=1)
                urllib.request.urlopen("http://127.0.0.1:%d/api/dataset-info" % (a.port + 1), timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        res += ["-- full (fake 30 images)"] + chrome("http://127.0.0.1:%d/%s#dataset" % (a.port, pages["full"].name),
                                                     work / "shot_full.png")
        res += ["-- empty dataset"] + chrome("http://127.0.0.1:%d/%s#dataset" % (a.port + 1, pages["empty"].name),
                                             work / "shot_empty.png", "1400,900")
        res += ["-- file://"] + chrome(pages["file"].as_uri() + "#dataset", work / "shot_file.png", "1400,900")
        res += ["-- phone width"] + [l for l in chrome("http://127.0.0.1:%d/%s#dataset" % (a.port, pages["full"].name),
                                                         work / "shot_phone.png", "390,1600") if "cards per row" not in l]
    finally:
        for s in srv:
            s.terminate()
        for s in srv:
            try:
                s.wait(5)
            except subprocess.TimeoutExpired:
                s.kill()
        for p in pages.values():
            p.unlink(missing_ok=True)
    print("\n".join(res))
    fails = [l for l in res if l.startswith("FAIL")]
    print("%d checks, %d failed; screenshots in %s" % (sum(l[:4] in ("PASS", "FAIL") for l in res), len(fails), work))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
