#!/usr/bin/env python3
"""End-to-end test of the "Training: live" tab + the training endpoints of scripts/serve_dataset_view.py.

    python3 test_fixture/training_view_test.py WORK_DIR [--port 8821] [--live-run-dir RUNS --console-log FILE]

Writes fake run folders (make_fake_training.py: finished, crashed, and a 10-epoch live run that adds an epoch every ~4 s) to
WORK_DIR/fake_runs, plus an empty WORK_DIR/empty_runs; starts servers on PORT (fake runs) and PORT+1 (empty), checks
the HTTP API (validation, whitelist, Host header, SSE events, 40 concurrent streams + 200 requests) and drives the page
in headless Chromium (playwright): live updates without reload, polling fallback without EventSource, pause, run
selector, finished / failed runs, report gallery, empty folder, file://, phone width. Optional --live-run-dir runs a
read-only smoke check against a real runs folder on PORT+2. Saves screenshots in WORK_DIR; always stops what it started.
"""
import argparse
import http.client
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = HERE.parent
REPO = SC.parent.parent
MANIFESTS = ["manifest_v1.json", "manifest_v2.json", "manifest_review.json", "manifest_params.json",
             "manifest_dataset.json", "manifest_training.json"]
R = []
# every column of every table with a header row: header text-align == text-align of all its body cells
ALIGN_JS = """() => { const bad = [];
  document.querySelectorAll('main table').forEach(t => { const hr = t.querySelector('thead tr'); if (!hr) return;
    [...hr.children].forEach((th, j) => { const a = getComputedStyle(th).textAlign;
      t.querySelectorAll('tbody tr').forEach(r => { const c = r.children[j];
        if (c && getComputedStyle(c).textAlign !== a) bad.push(th.textContent.trim() + ': th ' + a + ' / td ' + getComputedStyle(c).textAlign); }); }); });
  return [...new Set(bad)]; }"""


def ok(name, cond, info=None):
    R.append(("PASS " if cond else "FAIL ") + name + ("" if info is None else " [%s]" % (info,)))


def get(port, path, host=None, method="GET", headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": host or "127.0.0.1:%d" % port}
    h.update(headers or {})
    c.request(method, path, headers=h)
    r = c.getresponse()
    body = r.read()
    c.close()
    return r.status, r.getheader("Content-Type") or "", body


def sse_events(port, path, seconds):
    """Read an SSE stream for `seconds` over a raw socket; returns (status, content-type, [(event, data)])."""
    import socket
    sk = socket.create_connection(("127.0.0.1", port), timeout=1.0)
    sk.sendall(("GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nAccept: text/event-stream\r\n\r\n" % (path, port)).encode())
    buf, t0 = b"", time.time()
    while time.time() - t0 < seconds:
        try:
            chunk = sk.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
    sk.close()
    head, _, body = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split()[1]) if lines and len(lines[0].split()) > 1 else 0
    ctype = next((l.split(":", 1)[1].strip() for l in lines[1:] if l.lower().startswith("content-type:")), "")
    out, ev = [], None
    for line in body.decode("utf-8", "replace").split("\n"):
        if line.startswith("event: "):
            ev = line[7:]
        elif line.startswith("data: "):
            out.append((ev, line[6:]))
    return status, ctype, out


def api_checks(port, fake):
    st, ct, b = get(port, "/api/training/runs")
    runs = json.loads(b)["runs"]
    ok("runs endpoint lists 3 runs, newest first", st == 200 and len(runs) == 3 and runs[0]["name"].endswith("fake-live"),
       [r["name"] for r in runs])
    by = {r["name"].split("_")[-1]: r for r in runs}
    ok("statuses guessed from files", by["fake-live"]["status"] == "running" and by["fake-finished"]["status"] == "finished"
       and by["fake-crashed"]["status"] == "failed", {k: v["status"] for k, v in by.items()})
    ok("active flag only on the live run", by["fake-live"]["active"] and not by["fake-finished"]["active"] and not by["fake-crashed"]["active"])
    fin = by["fake-finished"]["name"]
    st, ct, b = get(port, "/api/training/run?name=" + fin)
    r = json.loads(b)["run"]
    ok("run payload: epochs parsed", st == 200 and len(r["epochs"]) == 5 and r["epochs"][-1]["map50_95"] > 0.7, len(r["epochs"]))
    ok("run payload: timing merged", r["epochs"][0]["epoch_s"] == 101.0 and r["sec_per_epoch"])
    ok("run payload: 6 report figures + html", len(r["report"]["figures"]) == 6 and r["report"]["html"])
    st, ct, b = get(port, "/api/training/run")
    r = json.loads(b)["run"]
    ok("default run = newest", r["name"].endswith("fake-live"))
    P = r["progress"]
    ok("live progress parsed from tqdm line", P["phase"] in ("train", "val") and P["iters"] in (169, 10) and P["source"] == "train.log", P)
    ok("GPU mem + losses from the progress line", P["phase"] != "train" or (P["gpu_mem_gb"] == 5.27 and P["losses"]["box"] > 0))
    for bad in ("../fake_runs", "..", "%2e%2e", "a/b", ".hidden", "x" * 200, "nope"):
        st, _, _ = get(port, "/api/training/run?name=" + bad)
        ok("bad run name rejected: %s" % bad[:12], st == 404, st)
    st, _, b = get(port, "/training-files/%s/report.png" % fin)
    ok("whitelisted report.png served", st == 200 and b[:4] == b"\x89PNG")
    st, ct, _ = get(port, "/training-files/%s/report.html" % fin)
    ok("report.html served as html", st == 200 and ct.startswith("text/html"))
    st, _, _ = get(port, "/training-files/%s/report/pr_f1.png" % fin)
    ok("report/pr_f1.png served", st == 200)
    for p in ("config.json", "timing.json", "train.log", "ultra/results.csv", "report/../config.json", "report/x.jpg",
              "../%s/report.png" % fin, "report/sub/a.png"):
        st, _, _ = get(port, "/training-files/%s/%s" % (fin, p))
        ok("non-whitelisted file refused: %s" % p, st == 404, st)
    st, _, _ = get(port, "/api/training/runs", host="evil.example:%d" % port)
    ok("foreign Host header refused", st == 403, st)
    st, ct, ev = sse_events(port, "/api/training/stream", 5)
    kinds = [e for e, _ in ev]
    ok("SSE: text/event-stream with runs + run events", st == 200 and ct.startswith("text/event-stream") and "runs" in kinds
       and kinds.count("run") >= 2, kinds)
    # many concurrent clients: 40 streams open + 200 API calls in 8 threads
    errs, cnt = [], [0]
    stop = time.time() + 6

    def streamer():
        try:
            s, _, e = sse_events(port, "/api/training/stream?name=" + fin, 5)
            if s != 200 or not e:
                errs.append("stream %s" % s)
        except Exception as x:  # noqa: BLE001
            errs.append(repr(x))

    def hammer():
        while time.time() < stop and cnt[0] < 200:
            try:
                s, _, _ = get(port, "/api/training/run")
                if s != 200:
                    errs.append(s)
                cnt[0] += 1
            except Exception as x:  # noqa: BLE001
                errs.append(repr(x))
    th = [threading.Thread(target=streamer) for _ in range(40)] + [threading.Thread(target=hammer) for _ in range(8)]
    for t in th:
        t.start()
    for t in th:
        t.join(30)
    ok("40 concurrent streams + %d requests, 0 errors" % cnt[0], not errs and cnt[0] >= 50, errs[:3])
    st, _, _ = get(port, "/api/dataset-info")
    ok("dataset endpoint still works", st == 200)
    preds_api_checks(port, fake, by)


def preds_api_checks(port, fake, by):
    """live test examples: /api/training/preds, /training-img whitelist, SSE 'preds' events, POST resample."""
    import io
    from PIL import Image
    fin, live, crash = by["fake-finished"]["name"], by["fake-live"]["name"], by["fake-crashed"]["name"]
    st, _, b = get(port, "/api/training/preds?name=" + fin)
    ix = json.loads(b)
    ok("preds index (finished run): 16-image set, epochs = [final]", st == 200 and ix["set"]["n"] == 16 and
       len(ix["set"]["images"]) == 16 and ix["epochs"] == ["final"], (st, ix.get("epochs")))
    ok("preds index hides dataset paths, gives image urls", "dataset_root" not in ix["set"] and
       ix["set"]["images"][0]["img"].startswith("/training-img/%s/0.jpg" % fin))
    st, _, b = get(port, "/api/training/preds?name=%s&epoch=final" % fin)
    d = json.loads(b)
    ok("preds epoch=final: boxes + per-image TP/FP/FN + summary", st == 200 and d["epoch"] == "final" and
       len(d["images"]) == 16 and "precision" in d["summary"] and all(len(p) == 5 for im in d["images"] for p in im["pred"]))
    st, _, b = get(port, "/api/training/preds?name=%s&epoch=latest" % fin)
    ok("preds epoch=latest", st == 200 and json.loads(b)["epoch"] == "final")
    for bad in ("99", "../set", "x", "-1", "1e3"):
        st, _, _ = get(port, "/api/training/preds?name=%s&epoch=%s" % (fin, bad))
        ok("preds bad epoch refused: %s" % bad, st == 404, st)
    st, _, b = get(port, "/api/training/preds?name=" + crash)
    ix_c = json.loads(b)
    ok("run without live_preds: set null, no epochs", st == 200 and ix_c["set"] is None and ix_c["epochs"] == [])
    st, _, _ = get(port, "/api/training/preds?name=../" + fin)
    ok("preds bad run name refused", st == 404, st)
    st, ct, b = get(port, "/training-img/%s/0.jpg" % fin)
    w0 = Image.open(io.BytesIO(b)).size if st == 200 else None
    ok("set image served as a 640 px thumbnail (960 px source)", st == 200 and ct == "image/jpeg" and w0 and w0[0] == 640, (st, w0))
    st, ct, b = get(port, "/training-img/%s/0.jpg?full=1" % fin)
    ok("?full=1 serves the original 960 px image", st == 200 and Image.open(io.BytesIO(b)).size == (960, 960))
    st, _, b = get(port, "/training-img/%s/3.jpg" % live)
    ok("live run (640 px dataset) image served as is", st == 200 and Image.open(io.BytesIO(b)).size == (640, 640))
    for path in ("/training-img/%s/16.jpg" % fin, "/training-img/%s/0.jpg" % crash, "/training-img/../%s/0.jpg" % fin,
                 "/training-img/%s/0.png" % fin, "/training-img/%s/a.jpg" % fin, "/training-img/%s/%%2e%%2e.jpg" % fin):
        st, _, _ = get(port, path)
        ok("image route refuses %s" % path.split("/training-img/")[1][-24:], st == 404, st)
    # a tampered set.json (path outside images/, or another dataset root) serves nothing
    tam = fake / "2026-01-03_100000_fake-tamper"
    (tam / "live_preds").mkdir(parents=True, exist_ok=True)
    cfg = json.loads((fake / fin / "config.json").read_text())
    (tam / "config.json").write_text(json.dumps(cfg))
    good = json.loads((fake / fin / "live_preds" / "set.json").read_text())
    bad = dict(good, images=[dict(good["images"][0], id=0, rel="images/val/../../../config.json"),
                             dict(good["images"][1], id=1, rel="labels/val/" + good["images"][1]["rel"].split("/")[-1])])
    (tam / "live_preds" / "set.json").write_text(json.dumps(bad))
    st0, _, _ = get(port, "/training-img/%s/0.jpg" % tam.name)
    st1, _, _ = get(port, "/training-img/%s/1.jpg" % tam.name)
    (tam / "live_preds" / "set.json").write_text(json.dumps(dict(good, dataset_root="/")))
    st2, _, _ = get(port, "/training-img/%s/2.jpg" % tam.name)
    ok("tampered set.json: traversal / non-image / foreign dataset root refused", (st0, st1, st2) == (404, 404, 404), (st0, st1, st2))
    shutil.rmtree(tam)
    # live run: epochs grow while it trains, and the stream says so
    st, _, b = get(port, "/api/training/preds?name=" + live)
    e0 = json.loads(b)["epochs"]
    st, ct, ev = sse_events(port, "/api/training/stream?name=" + live, 4.5)
    pk = [json.loads(dd) for e, dd in ev if e == "preds"]
    ok("SSE: 'preds' event with the preds index", pk and pk[0]["run"] == live and pk[0]["set"]["n"] == 16, [e for e, _ in ev][:6])
    st, _, b = get(port, "/api/training/preds?name=" + live)
    e1 = json.loads(b)["epochs"]
    ok("live run: epoch files appear as epochs finish", len(e1) > len(e0) and all(k.isdigit() for k in e1), (e0, e1))
    ok("live run: predictor shown as watching", json.loads(b)["predictor_running"] is True)
    # resample: POST only, origin + run checked, rate-limited, handled by the predictor
    st, _, _ = get(port, "/api/training/resample?name=" + fin)
    ok("GET resample is not a route", st == 404, st)
    st, _, _ = get(port, "/api/training/resample?name=nope", method="POST")
    ok("POST resample unknown run -> 404", st == 404, st)
    st, _, _ = get(port, "/api/training/resample?name=" + fin, method="POST", headers={"Origin": "http://evil.example"})
    ok("POST resample from a foreign Origin -> 403", st == 403, st)
    st, _, _ = get(port, "/api/training/resample?name=" + fin, method="POST", host="evil.example:%d" % port)
    ok("POST resample with a foreign Host -> 403", st == 403, st)
    seed0 = ix["set"]["seed"]
    st, _, b = get(port, "/api/training/resample?name=" + fin, method="POST", headers={"Origin": "http://127.0.0.1:%d" % port})
    rr = json.loads(b)
    ok("POST resample (finished run) -> 202 + one-off predictor started", st == 202 and rr["queued"] and rr["spawned_predictor"], rr)
    st2, _, _ = get(port, "/api/training/resample?name=" + fin, method="POST")
    ok("second resample within the gap -> 429 (rate limit)", st2 == 429, st2)
    ix2 = None
    for _ in range(50):
        time.sleep(0.2)
        ix2 = json.loads(get(port, "/api/training/preds?name=" + fin)[2])
        if ix2["set"] and ix2["set"]["seed"] != seed0 and ix2["epochs"] and not ix2["resample_pending"]:
            break
    ok("resample: new seed, new set predicted, old set archived", ix2["set"]["seed"] == rr["seed"] and ix2["epochs"] == ["final"]
       and ix2["archived_sets"] == 1, (ix2["set"]["seed"], rr["seed"], ix2["epochs"], ix2["archived_sets"]))
    ok("resample: dataset untouched (still 24 val images)", len(list((fake / "_fake_ds960" / "images" / "val").glob("*.jpg"))) == 24)


def page_checks(port, page_name, work, empty_port, file_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        try:
            ctx = br.new_context(viewport={"width": 1400, "height": 1000})
            pg = ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.goto("http://127.0.0.1:%d/%s#training" % (port, page_name))
            pg.wait_for_selector(".conn.live", timeout=10000)
            ok("six tabs, training tab selected", pg.locator(".tab").count() == 6 and "Training: live" in pg.locator('[aria-selected="true"]').inner_text())
            ok("stream indicator live", pg.locator(".conn").inner_text().startswith("live"))
            pg.wait_for_function("document.querySelector('.trview .badge').textContent === 'running'", timeout=8000)
            ok("status badge running", True)
            big1 = pg.locator(".trview .big").inner_text()
            ok("big progress 'Epoch k / 10'", big1.startswith("Epoch ") and big1.endswith("/ 10"), big1)
            ok("glossary explains mAP / dfl / cls / box loss", all(t in pg.locator("details.glossary").first.text_content() for t in ("mAP50-95", "dfl loss", "cls loss", "box loss")))
            C8 = ".charts:not(.lpcharts) .chart"
            ok("8 charts with titles, legends and axis labels", pg.locator(C8).count() == 8 and pg.locator(C8 + " .legend").count() == 8
               and pg.locator(C8 + " svg text", has_text="epoch (1 = first").count() == 8, pg.locator(C8).count())
            ok("stat tiles (elapsed, ETA, s/epoch, img/s, GPU, losses)", pg.locator(".trview .stat").count() >= 9 and
               "GB" in pg.locator("[data-k=gpu]").inner_text(), pg.locator(".trview .stat").count())
            pg.wait_for_function("/iteration \\d+ \\/ 169/.test(document.querySelectorAll('.trview .plabel')[1].textContent)", timeout=8000)
            ok("within-epoch iteration progress shown", True, pg.locator(".trview .plabel").nth(1).inner_text()[:80])
            rows0 = pg.locator(".trview table.gt tbody tr").count()
            it0 = pg.locator(".trview .plabel").nth(1).inner_text()
            pg.wait_for_function("document.querySelectorAll('.trview table.gt tbody tr').length > %d" % rows0, timeout=15000)
            rows1 = pg.locator(".trview table.gt tbody tr").count()
            ok("table grows live without reload", rows1 > rows0, "%d -> %d" % (rows0, rows1))
            ok("iteration text changes live", pg.locator(".trview .plabel").nth(1).inner_text() != it0)
            ok("charts have lines once 2 epochs exist", pg.locator(".chart svg path").count() >= 8 or rows1 < 2)
            ok("live running-mean point on loss charts", pg.locator(".chart svg circle[fill='var(--surface)']").count() >= 1)
            eta = pg.locator("[data-k=eta] .v").inner_text()
            ok("ETA shown while running", eta not in ("–", "") , eta)
            # hover tooltip
            sv0 = pg.locator(".chart svg").first
            sv0.scroll_into_view_if_needed()
            bb = sv0.bounding_box()
            sv0.hover(position={"x": bb["width"] * 0.3, "y": bb["height"] * 0.5})
            pg.wait_for_timeout(200)
            ok("hover tooltip", pg.locator(".chart .tip:not([hidden])").count() == 1 and "epoch" in pg.locator(".chart .tip").first.inner_text())
            pg.screenshot(path=str(work / "tr_live.png"), full_page=True)
            # live test examples
            pg.wait_for_function("document.querySelectorAll('.lpcard').length === 16 && document.querySelector('.lpsum').textContent.indexOf('precision') >= 0", timeout=15000)
            ok("live test examples: 16 cards, summary line", True, pg.locator(".lpsum").inner_text()[:90])
            ok("legend + GT/prediction boxes drawn", pg.locator(".lplegend").count() == 1 and pg.locator(".lpcard .lpgt").count() > 10
               and pg.locator(".lpcard .lppr").count() > 5, (pg.locator(".lpcard .lpgt").count(), pg.locator(".lpcard .lppr").count()))
            ok("per-card TP/FP/FN badges", pg.locator(".lpcard .lpb.tp").count() == 16 and pg.locator(".lpcard .lpb.fn").count() == 16)
            ok("epoch label 'epoch k of 10' + following latest", " of 10" in pg.locator(".lpbar .lpval").first.inner_text()
               and pg.locator(".lpbar button[aria-pressed='true']").count() == 1, pg.locator(".lpbar .lpval").first.inner_text())
            ok("set-level precision/recall chart with axis labels", pg.locator(".lpcharts .chart svg text", has_text="fraction (0-1)").count() == 1
               and pg.locator(".lpcharts .chart svg text", has_text="epoch (1 = first").count() == 1)
            ok("glossary explains TP / FP / FN, IoU, conf", all(t in pg.locator("details.glossary").first.text_content() for t in ("TP / FP / FN", "IoU", "conf", "GT")))
            lab0 = pg.locator(".lpbar .lpval").first.inner_text()
            pg.wait_for_function("document.querySelector('.lpbar .lpval').textContent !== %s" % json.dumps(lab0), timeout=15000)
            ok("epoch auto-advances as new epochs arrive", True, "%s -> %s" % (lab0, pg.locator(".lpbar .lpval").first.inner_text()))
            ok("client-side TP/FP/FN equal the predictor's at conf 0.25", pg.evaluate("""() => fetch('/api/training/preds?epoch=latest&name=' + encodeURIComponent(document.querySelector('.trview select option:nth-child(2)').value)).then(r => r.json()).then(d => {
                 const t = d.images.reduce((a, i) => [a[0] + i.tp, a[1] + i.fp, a[2] + i.fn], [0, 0, 0]);
                 return t[0] === d.summary.tp && t[1] === d.summary.fp && t[2] === d.summary.fn; })"""))
            n_pr = pg.locator(".lpcard .lppr").count()
            pg.locator(".lpbar input[type=range]").nth(1).fill("0.9")
            n_pr9 = pg.locator(".lpcard .lppr").count()
            ok("confidence slider filters boxes client-side", n_pr9 < n_pr and "0.90" in pg.locator(".lpsum").inner_text(), (n_pr, n_pr9))
            pg.locator(".lpbar input[type=range]").nth(1).fill("0.25")
            sums = pg.evaluate("""() => { const n = c => [...document.querySelectorAll('.lpcard .lpb.' + c)].reduce((a, b) => a + +b.textContent.split(' ')[1], 0);
                 const m = document.querySelector('.lpsum').textContent.match(/\\((\\d+) TP of (\\d+) predictions\\).*\\((\\d+) of (\\d+) mines/);
                 return [n('tp'), n('tp') + n('fp'), n('tp') + n('fn'), m && +m[1], m && +m[2], m && +m[4]]; }""")
            ok("summary line = sum of the card badges (TP, predictions, mines)", sums[:3] == sums[3:], sums)
            pg.get_by_label("ground truth", exact=True).uncheck()
            ok("GT toggle hides green boxes", pg.locator(".lpcard .lpgt").count() == 0)
            pg.get_by_label("ground truth", exact=True).check()
            pg.get_by_role("button", name="previous epoch").click()
            lab_s = pg.locator(".lpbar .lpval").first.inner_text()
            ok("scrubbing back stops following latest", pg.locator(".lpbar button[aria-pressed='true']").count() == 0, lab_s)
            pg.wait_for_timeout(3500)
            ok("scrubbed epoch stays while new epochs arrive", pg.locator(".lpbar .lpval").first.inner_text().split(" · ")[0] == lab_s.split(" · ")[0])
            pg.get_by_role("button", name="Latest").click()
            pg.locator(".lpopen").first.click()
            pg.wait_for_timeout(300)
            ok("card enlarges in the lightbox with the box overlay", pg.locator("#lb.open .lpimg svg").count() == 1
               and pg.locator("#lb.open .lpimg img").count() == 1, pg.locator("#lb.open").count())
            pg.keyboard.press("Escape")
            pg.locator(".lpsec").screenshot(path=str(work / "tr_live_preds.png"))
            ok("th / td alignment match in every training table column", pg.evaluate(ALIGN_JS) == [], pg.evaluate(ALIGN_JS)[:3])
            # pause
            pg.get_by_role("button", name="Pause updates").click()
            ok("pause -> indicator paused", pg.locator(".conn").inner_text() == "paused")
            r_p = pg.locator(".trview table.gt tbody tr").count()
            pg.wait_for_timeout(4500)
            ok("no updates while paused", pg.locator(".trview table.gt tbody tr").count() == r_p)
            pg.get_by_role("button", name="Resume updates").click()
            pg.wait_for_selector(".conn.live", timeout=8000)
            ok("resume -> live again", True)
            # selector: finished + crashed
            opts = pg.locator(".trview select option").all_inner_texts()
            ok("run selector: follow-newest + 3 runs", len(opts) == 4 and opts[0].startswith("Newest run"), opts)
            fin = [o for o in pg.locator(".trview select option").evaluate_all("o => o.map(x => x.value)") if o.endswith("fake-finished")][0]
            pg.locator(".trview select").select_option(fin)
            pg.wait_for_function("document.querySelector('.trview .badge').textContent === 'finished'", timeout=8000)
            pg.wait_for_function("[...document.querySelectorAll('.rgal img')].length === 6 && [...document.querySelectorAll('.rgal img')].every(i => i.complete && i.naturalWidth > 0)", timeout=8000)
            ok("finished run: 6 report images with captions", pg.locator(".rgal figcaption").count() == 6)
            href = pg.locator("a", has_text="Open report.html").get_attribute("href")
            ok("report.html link", href.endswith("/report.html"), href)
            pg.wait_for_function("document.querySelectorAll('.lpcard').length === 16 && /final/.test(document.querySelector('.lpbar .lpval').textContent)", timeout=8000)
            ok("finished run: final-only predictions, 'final (best.pt, epoch 5) of 5'", "final (best.pt, epoch 5) of 5" in pg.locator(".lpbar .lpval").first.inner_text(),
               pg.locator(".lpbar .lpval").first.inner_text())
            ok("finished run: 960 px images, square cards", pg.locator(".lpimg").first.get_attribute("style").startswith("aspect-ratio:960 / 960"))
            seed_txt = pg.locator(".lpstatus").inner_text()
            pg.get_by_role("button", name="Resample 16").click()
            pg.wait_for_function("(t => t !== %s && /seed \\d+/.test(t) && /archived/.test(t))(document.querySelector('.lpstatus').textContent) && document.querySelectorAll('.lpcard').length === 16" % json.dumps(seed_txt), timeout=15000)
            ok("Resample 16 -> new set shown, old one archived", pg.locator(".lpstatus").inner_text() != seed_txt, pg.locator(".lpstatus").inner_text()[:100])
            ok("finished run: 5 table rows, best row bold", pg.locator(".trview table.gt tbody tr").count() == 5 and pg.locator("tr.best").count() == 1)
            pg.locator(".rgal button").first.click()
            ok("report image opens in lightbox", pg.locator("#lb.open").count() == 1)
            pg.keyboard.press("Escape")
            pg.screenshot(path=str(work / "tr_finished.png"), full_page=True)
            crash = [o for o in pg.locator(".trview select option").evaluate_all("o => o.map(x => x.value)") if o.endswith("fake-crashed")][0]
            pg.locator(".trview select").select_option(crash)
            pg.wait_for_function("document.querySelector('.trview .badge').textContent === 'failed'", timeout=8000)
            pg.wait_for_function("/No live test examples/.test(document.querySelector('.lpstatus').textContent)", timeout=8000)
            ok("run without predictions: '--once' hint", "--once" in pg.locator(".lpstatus").inner_text())
            ok("crashed run: failed + reason + log tail", "probably crashed" in pg.locator(".trview .dfail").inner_text() and "RuntimeError" in pg.locator(".trview pre.log").first.inner_text())
            pg.locator(".trview select").select_option("")
            pg.wait_for_function("document.querySelector('.trview .badge').textContent !== 'failed'", timeout=8000)
            # wait for the live run to finish -> report appears by itself
            pg.wait_for_function("document.querySelector('.trview .badge').textContent === 'finished' && document.querySelectorAll('.rgal img').length === 6", timeout=60000)
            ok("live run finishes -> badge finished + gallery appear without reload", True)
            ok("10 / 10 epochs after finish", pg.locator(".trview .big").inner_text() == "10 / 10 epochs", pg.locator(".trview .big").inner_text())
            # theme toggle keeps charts readable
            pg.locator("#themeBtn").click()
            pg.screenshot(path=str(work / "tr_theme.png"), full_page=True)
            pg.evaluate("location.hash='#v1'")
            pg.wait_for_selector("main .card", timeout=5000)
            ok("other tabs still render (v1 cards), training view gone", pg.locator(".trview").count() == 0)
            for tab in ("params", "burial_review_2"):
                pg.evaluate("location.hash='#%s'" % tab)
                pg.wait_for_timeout(800)
                if tab == "burial_review_2" and pg.get_by_role("button", name="Table").count():
                    pg.get_by_role("button", name="Table").first.click()
                    pg.wait_for_timeout(300)
                bad = pg.evaluate(ALIGN_JS)
                ok("th / td alignment match in every table column (%s, %d tables)" % (tab, pg.locator("main table").count()), bad == [], bad[:3])
            pg.evaluate("location.hash='#training'")
            pg.wait_for_selector(".conn.live", timeout=8000)
            ok("back to training tab reconnects", True)
            ok("no JS errors", not errors, errors[:3])
            ctx.close()

            # polling fallback: no EventSource
            ctx = br.new_context(viewport={"width": 1200, "height": 900})
            ctx.add_init_script("delete window.EventSource; window.EventSource = undefined;")
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:%d/%s#training" % (port, page_name))
            pg.wait_for_selector(".conn.polling", timeout=10000)
            ok("no EventSource -> polling every 5 s", "polling" in pg.locator(".conn").inner_text())
            pg.wait_for_selector(".trview .badge.finished", timeout=8000)
            ok("polling shows data", pg.locator(".trview table.gt tbody tr").count() == 10)
            ctx.close()

            # empty training dir
            pg = br.new_page()
            pg.goto("http://127.0.0.1:%d/%s#training" % (empty_port, page_name))
            pg.wait_for_function("document.querySelector('.trview .badge') && document.querySelector('.trview .badge').textContent === 'no runs yet'", timeout=10000)
            ok("empty folder: 'no runs yet' + hint", "No training runs yet" in pg.locator(".trview").inner_text())
            pg.screenshot(path=str(work / "tr_empty.png"))
            pg.close()
            # file://
            pg = br.new_page()
            pg.goto(file_url + "#training")
            pg.wait_for_selector(".trview .empty", timeout=5000)
            t = pg.locator(".trview").inner_text()
            ok("file:// message with command + link", "serve_dataset_view.py" in t and pg.locator(".trview a[href^='http://127.0.0.1:8765']").count() == 1)
            pg.close()
            # phone width
            ctx = br.new_context(viewport={"width": 390, "height": 1600})
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:%d/%s#training" % (port, page_name))
            pg.wait_for_selector(".trview .badge.finished", timeout=10000)
            pg.wait_for_timeout(500)
            sw = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
            ok("phone width: no horizontal page scroll", sw[0] <= sw[1], sw)
            pg.screenshot(path=str(work / "tr_phone.png"), full_page=True)
            ctx.close()
        finally:
            br.close()


def start(port, d, extra=()):
    p = subprocess.Popen([sys.executable, str(REPO / "scripts" / "serve_dataset_view.py"), "--port", str(port),
                          "--training-dir", str(d), "--dataset-dir", str(d / "_no_dataset"), *extra],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/api/training/runs" % port, timeout=1)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--port", type=int, default=8821)
    ap.add_argument("--live-run-dir", help="optional real runs folder for a read-only smoke check")
    ap.add_argument("--console-log", action="append", default=[])
    a = ap.parse_args()
    work = Path(a.work).resolve()
    fake, empty = work / "fake_runs", work / "empty_runs"
    for d in (fake, empty):
        shutil.rmtree(d, ignore_errors=True)
    empty.mkdir(parents=True)
    subprocess.run([sys.executable, str(HERE / "make_fake_training.py"), str(fake)], check=True)
    page = SC / "_tr_test.html"
    subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", *MANIFESTS, "--out", str(page)],
                   check=True, capture_output=True)
    procs = []
    try:
        writer = subprocess.Popen([sys.executable, str(HERE / "make_fake_training.py"), str(fake), "--no-static",
                                   "--live", "10", "--step", "3"], stdout=subprocess.DEVNULL)
        procs.append(writer)
        procs.append(start(a.port, fake, ["--predictor-python", sys.executable,
                                          "--predictor-script", str(HERE / "fake_live_predict.py"), "--resample-gap", "3"]))
        procs.append(start(a.port + 1, empty))
        time.sleep(2.5)                     # live run folder exists and has a progress line
        R.append("-- API (fake runs)")
        api_checks(a.port, fake)
        R.append("-- page (headless Chromium)")
        page_checks(a.port, page.name, work, a.port + 1, page.as_uri())
        writer.wait(90)
        if a.live_run_dir:
            R.append("-- real runs folder (read-only)")
            procs.append(start(a.port + 2, Path(a.live_run_dir), [x for c in a.console_log for x in ("--console-log", c)]))
            st, _, b = get(a.port + 2, "/api/training/run")
            r = json.loads(b)["run"]
            ok("real run payload", st == 200 and r and r["status"] in ("running", "finished", "failed"),
               r and (r["name"], r["status"], r["progress"]["phase"], r["epochs_done"], r["eta_s"]))
            st, ct, ev = sse_events(a.port + 2, "/api/training/stream", 4)
            ok("real run SSE events", st == 200 and any(e == "run" for e, _ in ev), [e for e, _ in ev])
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        page.unlink(missing_ok=True)
    print("\n".join(R))
    fails = [l for l in R if l.startswith("FAIL")]
    print("%d checks, %d failed; screenshots in %s" % (sum(l[:4] in ("PASS", "FAIL") for l in R), len(fails), work))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
