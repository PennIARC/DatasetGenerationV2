from v2lib import *
import json, shutil
ex = json.load(open(ROOT + "/docs/asset_audit/exclude.json"))
bad = {os.path.basename(p) for p in ex["hard_exclude"]}
shutil.copy(ROOT + "/docs/asset_audit/flagged_assets.jpg", OUT + "/asset_audit_flagged.jpg")
f13 = {"id": "asset_audit", "title": "Asset audit and filter", "flag": "ASSET_AUDIT_FILTER",
       "summary": "Before using the extra images for training, every background, rock, leaf, dirt and grass image was checked individually (186 audited). Some of the original v1 backgrounds turned out to be screenshots with stock-photo watermarks or other flaws; a detector could learn such marks as a shortcut. The audit's exclusion list is applied when the generator samples assets, and 'review' items are drawn less often.",
       "how": "features/assets.py and features/background.py read docs/asset_audit/exclude.json by file name: 'hard_exclude' files are never sampled; 'review' files (69) get weight x0.4 (ASSET_REVIEW_WEIGHT). v1 mode (flag off) reproduces v1 exactly, watermarks included. The sidecar records the audit status of the background.",
       "code": "DatasetGenerator/features/assets.py, features/background.py; docs/asset_audit/ (exclude.json, summary.csv, flagged_sheet.py); controlPanel: ASSET_AUDIT_FILTER, ASSET_AUDIT_PATH, ASSET_REVIEW_WEIGHT",
       "options": [], "before_after": [],
       "notes": "Findings: 186 images audited individually; 6 of the 15 v1 backgrounds and 2 of the 5 v1 grass snippets (debris1, debris2) are hard-excluded; no watermarks were found in the new assets (assets_new was cleaned: 17 backgrounds rejected, rocks / leaf clumps / dirt regenerated or defringed, six real-grass backgrounds added). The exclusion list is an auditor opinion and was meant to be spot-checked. After filtering, 9 of the 15 v1 photos remain. All images on this page use the current, filtered asset pool."}
f13["options"].append(O("flagged assets", "docs/asset_audit/flagged_assets.jpg", "images/v2/asset_audit_flagged.jpg", "Contact sheet of the flagged assets (sheet produced by the audit)."))
kw = dict(n_mines=0, grass_blades=False, leaf_clumps_new=False, bg_augment=False, photometric_jitter=False, psf_sigma=0.0, motion_blur_prob=0)
done = 0
for seed in range(0, 120):
    r0, _, m0 = render(seed, **kw, asset_audit_filter=False)
    if os.path.basename(m0["background"]["file"]) not in bad: continue
    r1, _, m1 = render(seed, **kw, asset_audit_filter=True)
    f13["before_after"].append(BA(f"Filter off vs on (seed {seed})", save(frame(r0, 960), f"audit_ba_{done}_off.jpg"), save(frame(r1, 960), f"audit_ba_{done}_on.jpg"), "ASSET_AUDIT_FILTER off", "on",
                                  f"With the filter off, seed {seed} draws a hard-excluded background ({os.path.basename(m0['background']['file'])[:28]}); with it on a different, clean photo is used. The excluded photo carries a faint stock-photo watermark (ghost spiral marks near the centre of the first example)."))
    done += 1
    if done >= 2: break
if not done: f13["notes"] += " (No excluded background was drawn in the first 120 seeds, so no before/after pair.)"
dump("frag_13.json", f13)
print("done", done)
