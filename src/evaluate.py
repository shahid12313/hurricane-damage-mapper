"""Final evaluation of the trained models on the untouched test split.

The hold split was used to choose the best epoch of every run, so its scores are slightly optimistic.
The test split was never used for any decision; run this once at the end for the reported numbers.

Usage (from the project root):

    /opt/anaconda3/bin/python3 -m src.evaluate                  # test split -> runs/test_results.json
    /opt/anaconda3/bin/python3 -m src.evaluate --split hold     # same metrics on another split
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from src import damage, train
from src.dataset import BuildingDataset

DAMAGE_RUNS = {"v1": "runs/damage_resnet34", "v3": "runs/damage_v3"}


def load(build, run_dir, device):
    model = build(pretrained=False).to(device)
    model.load_state_dict(torch.load(Path(run_dir) / "best.pt", map_location=device)["model"])
    return model.eval()


def main(split, data_root="data/processed", workers=4):
    device = train.pick_device()
    split_dir = Path(data_root) / split
    results = {"split": split}

    loc_model = load(train.build_model, "runs/loc_resnet34", device)
    loc_loader = DataLoader(BuildingDataset([split_dir], crop=None, augment=False), batch_size=2, num_workers=workers)
    results["localization"] = train.evaluate(loc_model, loc_loader, device)
    print(f"localization: {results['localization']}", flush=True)

    damage_ds = damage.DamageDataset([split_dir], crop=None, augment=False)
    damage_loader = DataLoader(damage_ds, batch_size=2, num_workers=workers)
    for name, run_dir in DAMAGE_RUNS.items():
        model = load(damage.build_model, run_dir, device)
        metrics = damage.evaluate(model, damage_loader, device)
        matrix = damage.building_confusion(model, damage_ds, device)
        metrics["building_accuracy"] = float(np.trace(matrix) / matrix.sum())
        metrics["building_confusion"] = matrix.tolist()
        results[f"damage_{name}"] = metrics
        print(f"damage {name}: " + "  ".join(f"{k}={v:.4f}" for k, v in metrics.items() if isinstance(v, float)), flush=True)

    out = Path("runs") / f"{split}_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the trained models on a split.")
    parser.add_argument("--split", default="test")
    args = parser.parse_args()
    main(args.split)
