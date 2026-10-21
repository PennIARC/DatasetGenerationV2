#!/usr/bin/env python3
"""Stand-in for kernelBashing/baselines/yolo11n/scripts/live_predict.py --handle-request (no ultralytics): the server
under test starts it for 'Resample 16' on a run without a watcher. Archives the current set, samples a new one with the
requested seed from the run's (fake) dataset and writes fake predictions for it as epoch 'final'."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fake_training import fake_preds, fake_set  # noqa: E402


def main():
    run = Path(sys.argv[1])
    lp = run / "live_preds"
    req = lp / "resample_request.json"
    if "--handle-request" not in sys.argv or not req.exists():
        return 0
    seed = int(json.loads(req.read_text())["seed"])
    cfg = json.loads((run / "config.json").read_text())
    old = json.loads((lp / "set.json").read_text()) if (lp / "set.json").exists() else {"seed": "none"}
    arch = lp / "archive" / ("set_seed%s" % old["seed"])
    arch.mkdir(parents=True, exist_ok=True)
    for f in list(lp.glob("epoch_*.json")) + [lp / "set.json"]:
        if f.exists():
            os.replace(f, arch / f.name)
    imgsz = cfg["args"]["imgsz"]
    sset = fake_set(run, cfg["dataset"]["root"], imgsz, seed)
    req.unlink()
    fake_preds(run, sset, "final", cfg["args"]["epochs"], best_epoch=cfg["args"]["epochs"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
