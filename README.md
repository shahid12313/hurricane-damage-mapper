# Hurricane Damage Mapper

Classifies every building in before/after satellite images as no damage, minor, major, or destroyed, and shows the results on a map for response teams. Data: [xBD / xView2](https://xview2.org).

Master's project, Computer Science, Lamar University.

## Setup

```bash
pip install -r requirements.txt
```

Download xBD from xview2.org (free account) and extract it into `data/xbd/` so you have:

```
data/xbd/train/images/*_pre_disaster.png
data/xbd/train/images/*_post_disaster.png
data/xbd/train/labels/*_post_disaster.json
```

The `data/` and `outputs/` folders are git-ignored, so images never reach GitHub.

## Layout

| Path | Purpose |
|---|---|
| `src/xbd.py` | Reads tiles, labels and building outlines; draws before/after pairs |
| `notebooks/01_explore_xbd.ipynb` | Phase 1: dataset exploration and label statistics |
| `outputs/` | Generated CSVs and figures |

## Progress

- [ ] Advisor approval
- [x] Project scaffold and exploration notebook
- [ ] xBD downloaded and exploration notebook run
- [ ] Baseline model (building localization)
- [ ] Damage classification model
- [ ] Map dashboard
