#!/usr/bin/env python3
"""Build the showcase from the test manifests and validate the output."""
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = HERE.parent
sys.path.insert(0, str(HERE))


class P(HTMLParser):
    VOID = {"meta", "br", "img", "input", "link", "hr"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, t, a):
        if t not in self.VOID:
            self.stack.append(t)

    def handle_endtag(self, t):
        if not self.stack or self.stack[-1] != t:
            self.errors.append("unbalanced </%s> (open: %s)" % (t, self.stack[-3:]))
        else:
            self.stack.pop()


def check(path):
    txt = path.read_text(encoding="utf-8")
    p = P()
    p.feed(txt)
    p.close()
    assert not p.errors and not p.stack, (p.errors, p.stack)
    scripts = re.findall(r"<script(?![^>]*application/json)[^>]*>(.*?)</script>", txt, re.S)
    assert scripts
    js = Path(tempfile.mkdtemp()) / "s.js"
    js.write_text("\n".join(scripts))
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        print("  node --check OK")
    else:
        print("  node not available; JS not syntax-checked")
    import json
    blob = re.search(r'<script id="showcase-data" type="application/json">(.*?)</script>', txt, re.S).group(1)
    assert len(json.loads(blob)["pages"]) >= 2
    return len(txt)


subprocess.run([sys.executable, str(HERE / "make_fixture.py")], check=True)
ms = [str(HERE / "manifest_test_v1.json"), str(HERE / "manifest_test_v2.json"), str(HERE / "manifest_test_review.json")]
out1, out2, out3 = (HERE / n for n in ("out_plain.html", "out_embed.html", "out_missing.html"))
subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", *ms, "--out", str(out1)], check=True)
subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", *ms, "--out", str(out2), "--embed"], check=True)
subprocess.run([sys.executable, str(SC / "build_showcase.py"), "--manifests", ms[0], "nonexistent.json", "--out", str(out3)], check=True)
for o in (out1, out2, out3):
    print(o.name, check(o), "bytes")
assert "data:image/jpeg;base64," in out2.read_text() and "data:image" not in out1.read_text()
assert "test_fixture/images/shadows_0.jpg" in out1.read_text()
assert "Images not generated" in out3.read_text() or "was not found" in out3.read_text()
print("ALL OK")
