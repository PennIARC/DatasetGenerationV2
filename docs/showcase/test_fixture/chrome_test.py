#!/usr/bin/env python3
"""Headless-Chrome interaction test for the review grid (needs Google Chrome on macOS).
Builds a page with an appended test script, dumps the DOM, and prints the script's results."""
import json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = HERE.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if not Path(CHROME).exists():
    sys.exit("Chrome not found; skipping")
out = SC / "_grid_test.html"
subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", str(HERE / "manifest_test_review.json"),
                "--out", str(out)], check=True, capture_output=True)
TEST = r"""
<script>
(function(){
var R = [];
function ok(name, cond, info){ R.push((cond ? "PASS " : "FAIL ") + name + (info !== undefined ? " [" + info + "]" : "")); }
var q = function(s){ return document.querySelector(s); }, qa = function(s){ return [].slice.call(document.querySelectorAll(s)); };
window.addEventListener("error", function(e){ R.push("FAIL js error: " + e.message); });
window.__copied = null;
Object.defineProperty(navigator, "clipboard", {value: {writeText: function(t){ window.__copied = t; return Promise.resolve(); }}, configurable: true});
setTimeout(function(){
  try {
    ok("grid tab selected", /Review/.test(q('[aria-selected="true"]').textContent));
    var cards = qa(".gcard");
    ok("chunked initial render (<400, >0)", cards.length > 0 && cards.length < 400, cards.length);
    ok("counts text", /Showing 400 of 400/.test(q(".counts").textContent), q(".counts").textContent);
    // load more
    q(".grow button[hidden],.grow[hidden] button") ;
    var more = qa("button").filter(function(b){ return /Load more/.test(b.textContent); })[0];
    for (var i = 0; i < 12; i++) more.click();
    ok("all rendered after load more", qa(".gcard").length === 400, qa(".gcard").length);
    // flag via keyboard
    var c0 = qa(".gcard")[0]; c0.focus();
    c0.dispatchEvent(new KeyboardEvent("keydown", {key: "f", bubbles: true}));
    ok("f flags card", c0.classList.contains("flagged") && c0.querySelector("input[type=checkbox]").checked);
    c0.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowRight", bubbles: true}));
    ok("arrow moves focus", document.activeElement === qa(".gcard")[1], document.activeElement.getAttribute("data-id"));
    var c1 = qa(".gcard")[1];
    c1.querySelector("input[type=checkbox]").click();
    var note = c1.querySelector("input.note"); note.value = "blurry"; note.dispatchEvent(new Event("input", {bubbles: true}));
    ok("counts flagged 2", /Flagged 2/.test(q(".counts").textContent), q(".counts").textContent);
    // filters
    var sels = qa(".gfilters select");
    var bg = sels[0]; bg.value = "grass"; bg.dispatchEvent(new Event("change"));
    var n = qa(".gcard").length; var expect = 400 - Math.floor(400 / 6 * 4);
    ok("bg family filter", /Showing (\d+) of 400/.exec(q(".counts").textContent)[1] > 100 && /Showing (\d+) of 400/.exec(q(".counts").textContent)[1] < 200, q(".counts").textContent);
    bg.value = ""; bg.dispatchEvent(new Event("change"));
    var face = qa(".gfilters select").filter(function(s){ return /face/.test(s.getAttribute("aria-label")); })[0];
    face.value = "yes"; face.dispatchEvent(new Event("change"));
    ok("face_down yes = 134", /Showing 134 of/.test(q(".counts").textContent), q(".counts").textContent);
    face.value = ""; face.dispatchEvent(new Event("change"));
    var sunMin = qa('.gfilters input[type=number]')[0]; sunMin.value = "70"; sunMin.dispatchEvent(new Event("input"));
    var cnt = +/Showing (\d+)/.exec(q(".counts").textContent)[1];
    ok("sun>=70 filter reduces", cnt > 0 && cnt < 100, cnt);
    sunMin.value = ""; sunMin.dispatchEvent(new Event("input"));
    // flagged only
    var only = qa("button").filter(function(b){ return /flagged only/.test(b.textContent); })[0]; only.click();
    ok("flagged only = 2", /Showing 2 of/.test(q(".counts").textContent), q(".counts").textContent);
    // copy
    qa("button").filter(function(b){ return /Copy flagged/.test(b.textContent); })[0].click();
    setTimeout(function(){
      ok("copy text", window.__copied && window.__copied.split("\n").length === 2 && /b001 \| seed=1000/.test(window.__copied) && /note: blurry/.test(window.__copied), JSON.stringify(window.__copied));
      // table view + sort
      only.click();
      qa("button").filter(function(b){ return b.textContent === "Table"; })[0].click();
      ok("table rows chunked", qa("table.gt tbody tr").length > 0, qa("table.gt tbody tr").length);
      var th = qa("table.gt th button").filter(function(b){ return /^burial/.test(b.textContent); })[0]; th.click();
      qa("button").filter(function(b){ return /Load more/.test(b.textContent); })[0].click();
      var first = qa("table.gt tbody tr")[0].children[6].textContent;
      ok("table sorted by burial asc", first === "0", first);
      // lightbox
      qa("table.gt .thumb")[0].click();
      ok("lightbox opens with meta table", q("#lb").classList.contains("open") && qa("#lbInfo table.tbl tr").length >= 7, qa("#lbInfo table.tbl tr").length);
      document.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowRight", bubbles: true}));
      document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      ok("lightbox closes", !q("#lb").classList.contains("open"));
      // persistence (debounced)
      setTimeout(function(){
        var raw = localStorage.getItem("showcase-flags:burial_review");
        var o = raw ? JSON.parse(raw) : {};
        ok("localStorage flags", o.b001 && o.b001.f === 1 && o.b002 && o.b002.n === "blurry", raw);
        // clear
        var clr = qa("button").filter(function(b){ return /Clear flags/.test(b.textContent); })[0]; clr.click(); clr.click();
        ok("clear flags", /Flagged 0/.test(q(".counts").textContent), q(".counts").textContent);
        finish();
      }, 600);
    }, 100);
  } catch(e){ R.push("FAIL exception: " + e.message + " " + e.stack); finish(); }
}, 800);
function finish(){ var pre = document.createElement("pre"); pre.id = "TESTRESULT"; pre.textContent = R.join("\n"); document.body.appendChild(pre); }
})();
</script>
"""
html = out.read_text().replace("</body>", TEST + "</body>")
out.write_text(html)
prof = tempfile.mkdtemp()
try:
    r = subprocess.run([CHROME, "--user-data-dir=" + prof, "--headless=new", "--disable-gpu", "--no-sandbox",
                        "--virtual-time-budget=8000", "--dump-dom", "file://" + str(out) + "#burial_review"],
                       capture_output=True, text=True, timeout=120)
finally:
    subprocess.run(["pkill", "-f", "user-data-dir=" + prof])
    shutil.rmtree(prof, ignore_errors=True)
    out.unlink()
m = re.search(r'<pre id="TESTRESULT">(.*?)</pre>', r.stdout, re.S)
if not m:
    sys.exit("no test result found in DOM")
import html as H
res = H.unescape(m.group(1)); print(res)
sys.exit(1 if "FAIL" in res else 0)
