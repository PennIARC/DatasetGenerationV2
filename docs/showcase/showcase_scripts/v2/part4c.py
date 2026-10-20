"""Leave-one-out ablation sheet appended to frag_10.json."""
from v2lib import *
import json
from config import make_config
f10 = json.load(open("/Users/pranavgupta/Desktop/PennAiR/IARCtesting/IARCdatasetGenerationV2/docs/showcase/showcase_scripts/v2/frag_10.json"))
flags = list(make_config({}).V2_FLAGS)
ab = dict(n_mines=3, mine_positions=[(800, 560), (1050, 470), (1300, 640)], mine_scale=0.35, mine_pose=(3, -2, 30), burial_prob=1.0, burial_fraction=0.35, flip_prob=0.0, rocks_to_spawn_min=10)
tiles = []
for lbl, d in [("all on (v2)", {})] + [("all except " + f, {f.lower(): False}) for f in flags]:
    r, _, _ = render(12, **ab, **d)
    c = cv2.resize(crop(r, 1050, 540, 640, 360, 1)[0], (460, 259), interpolation=cv2.INTER_AREA)
    t = tag(c, lbl, "tl").copy(); t[:2] = 0; t[:, :2] = 0; tiles.append(t)
f10["options"].insert(1, O("leave-one-out ablation sheet", "seed 12, everything on except the named flag", save(tiles_grid(tiles, 3), "ablation_leave_one_out.jpg"),
    "More informative than the only-one sheet: first tile is full v2, each other tile removes one feature. Turning NEW_ASSETS off or BG_AUGMENT off changes the background photo itself, so those tiles look different overall."))
f10["notes"] += " In the only-one sheet, the NEW_ASSETS tile (and the all-on tile) draw a different background photo because that flag changes the background pool, so compare mines rather than ground there."
dump("frag_10.json", f10)
