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

## Layout

| Path | Purpose |
|---|---|
| `src/xbd.py` | Reads raw xBD tiles, labels and building outlines; draws before/after pairs |
| `src/preprocess.py` | Converts raw GeoTIFFs to JPEG images and per-pixel damage masks in `data/processed/` |
| `src/dataset.py` | PyTorch dataset for the building localization model |
| `src/train.py` | Phase 2: U-Net (ResNet-34) that finds buildings in the pre-disaster image |
| `src/damage.py` | Phase 3: U-Net on pre + post images that labels each pixel's damage level, with xView2 scoring |
| `src/progress.py` | Live training progress in the terminal |
| `notebooks/01_explore_xbd.ipynb` | Dataset exploration and label statistics |
| `notebooks/02_building_localization.ipynb` | Phase 2 results |
| `notebooks/03_damage_classification.ipynb` | Phase 3 results and building-level confusion matrix |

## Results (validation on the `hold` split, trained on `tier1`)

| Model | Metric | Score |
|---|---|---|
| Building localization | pixel F1 | 0.792 |
| Damage classification | xView2 score (0.3 × loc F1 + 0.7 × damage F1) | 0.575 |
| Damage classification | building-level accuracy | 0.784 |

Per-class damage F1: no damage 0.93, minor 0.22, major 0.59, destroyed 0.78.

## Progress

- [x] Advisor approval
- [x] Project scaffold and dataset exploration
- [x] Building localization model
- [x] Damage classification model (first version)
- [ ] Improve minor-damage detection (class weights, tier3 data)
- [ ] Map dashboard
- [ ] Final evaluation on the `test` split
- [ ] Report and presentation
