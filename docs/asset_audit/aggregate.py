"""Aggregate results/batch_*.json into AUDIT.md, summary.csv and exclude.json (hard excludes: watermark/drop)."""
import csv, json
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).parent
rows = []
for f in sorted((here / "results").glob("batch_*.json")):
    rows += json.loads(f.read_text())
print(len(rows), "entries")
cnt = Counter(r["category"] for r in rows)
print(dict(cnt))
bad = [r for r in rows if r.get("watermark", "none") != "none"]
drop = [r for r in rows if r["verdict"] == "drop" or r.get("watermark", "none") != "none"]
review = [r for r in rows if r["verdict"] == "review" and r not in drop]
by_cat = defaultdict(lambda: Counter())
for r in rows:
    by_cat[r["category"]][r["verdict"] if r not in drop else "drop"] += 1
with open(here / "summary.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    cols = ["id", "category", "file", "verdict", "watermark", "watermark_text", "quality", "notes"]
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c, "") for c in cols])
(here / "exclude.json").write_text(json.dumps(
    {"hard_exclude": sorted(r["file"] for r in drop),
     "review": sorted(r["file"] for r in review),
     "note": "hard_exclude = watermark != none or verdict drop (auditor opinion, spot-check before relying on it)"}, indent=1))
print("\nWATERMARKS:")
for r in bad:
    print(" ", r["id"], Path(r["file"]).name, r["watermark"], r.get("watermark_text", ""))
print("\nDROP (not watermark):")
for r in drop:
    if r not in bad:
        print(" ", r["id"], Path(r["file"]).name, "-", r.get("notes", ""))
print("\nPER CATEGORY (keep/review/drop):")
for c, v in by_cat.items():
    print(" ", c, dict(v))
