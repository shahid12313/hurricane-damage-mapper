# Hurricane Damage Mapper

Classifies every building in before/after satellite images as no damage, minor, major, or destroyed, and shows the results on a map for response teams. Data: [xBD / xView2](https://xview2.org).

Master's project, Computer Science, Lamar University.

## Setup

Everything runs locally on a Mac (Apple Silicon GPU) using Anaconda Python:

```bash
/opt/anaconda3/bin/python3 -m pip install -r requirements.txt
```

Download the full xBD GeoTIFF release from xview2.org and extract it into `data/xbd/` so you have
`data/xbd/{tier1,tier3,hold,test}/{images,labels}/`. Then convert it into the compact training format:

```bash
/opt/anaconda3/bin/python3 -m src.preprocess
```

## Training

```bash
/opt/anaconda3/bin/python3 -m src.train  --epochs 30   # phase 2: find buildings   (~3.5 h)
/opt/anaconda3/bin/python3 -m src.damage --epochs 30   # phase 3: classify damage  (~3.5 h)
/opt/anaconda3/bin/python3 -m src.progress             # live progress of both
```

Rerunning a training command resumes from the last finished epoch. Checkpoints and logs go to `runs/`.

`data/`, `outputs/` and `runs/` are git-ignored, so images and model weights never reach GitHub.

## Map dashboard

```bash
/opt/anaconda3/bin/python3 -m src.predict                    # run both models on hurricane tiles (~25 min)
/opt/anaconda3/bin/python3 -m http.server 8000 -d dashboard  # then open http://localhost:8000
```

Buildings are colored by predicted damage on a satellite basemap, with before/after tile images,
a switch to the true labels for comparison, and a list of the hardest-hit tiles.

## Layout

| Path | Purpose |
|---|---|
| `src/xbd.py` | Reads raw xBD tiles, labels and building outlines; draws before/after pairs |
| `src/preprocess.py` | Converts raw GeoTIFFs to JPEG images and per-pixel damage masks in `data/processed/` |
| `src/dataset.py` | PyTorch dataset for the building localization model |
| `src/train.py` | Phase 2: U-Net (ResNet-34) that finds buildings in the pre-disaster image |
| `src/damage.py` | Phase 3: U-Net on pre + post images that labels each pixel's damage level, with xView2 scoring |
| `src/progress.py` | Live training progress in the terminal |
| `src/evaluate.py` | Final evaluation of all models on the test split |
| `src/predict.py` | Phase 4: runs both models on tiles and exports map data (GeoJSON) for the dashboard |
| `dashboard/index.html` | Phase 4: interactive damage map (Leaflet) |
| `notebooks/01_explore_xbd.ipynb` | Dataset exploration and label statistics |
| `notebooks/02_building_localization.ipynb` | Phase 2 results |
| `notebooks/03_damage_classification.ipynb` | Phase 3 results and building-level confusion matrix |

## Final results (untouched `test` split, `python -m src.evaluate`)

| Model | Metric | Test |
|---|---|---|
| Building localization | pixel F1 | 0.788 |
| Damage v1 | xView2 score | 0.584 |
| **Damage v3 (final)** | xView2 score | **0.702** |
| **Damage v3 (final)** | building-level accuracy | **80.8%** |

## Development results (validation on the `hold` split)

| Model | Metric | Score |
|---|---|---|
| Building localization | pixel F1 | 0.792 |
| Damage v1 (tier1, from ImageNet) | xView2 score (0.3 × loc F1 + 0.7 × damage F1) | 0.575 |
| Damage v2 (tier1+tier3, minor weight 6) | xView2 score | 0.402 |
| **Damage v3 (fine-tuned from v1, tier1+tier3, balanced weights) — final** | xView2 score | **0.711** |

Per-class damage F1, v1 → v3: no damage 0.93 → 0.91, minor 0.22 → 0.45, major 0.59 → 0.69, destroyed 0.78 → 0.80.
Building-level accuracy is about the same (78.4% → 77.7%) because v3 calls more undamaged buildings minor damage.

v3 was trained with:

```bash
/opt/anaconda3/bin/python3 -m src.damage --out-dir runs/damage_v3 --train-splits tier1 tier3 --epochs 10 \
    --lr 1e-4 --init-from runs/damage_resnet34/best.pt --class-weights 0.5 1 4 4 3
```

The full write-up is in `docs/Hurricane_Damage_Mapper_Report.docx` (rebuild with `python docs/build_report.py`).

## Progress

- [x] Advisor approval
- [x] Project scaffold and dataset exploration
- [x] Building localization model
- [x] Damage classification model (first version)
- [x] Improve minor-damage detection (v2 failed, v3 improved the score to 0.711)
- [x] Map dashboard
- [x] Final evaluation on the `test` split (v3 score 0.702)
- [x] Report draft (docs/)
- [ ] Presentation
