"""Convert raw xBD into a compact training format that loads much faster than the 16-bit GeoTIFFs.

For every tile it writes:

    data/processed/<split>/images/<tile_id>_pre.jpg    before image, JPEG quality 95
    data/processed/<split>/images/<tile_id>_post.jpg   after image
    data/processed/<split>/masks/<tile_id>.png         one value per pixel, see MASK_VALUES

Usage (from the project root):

    /opt/anaconda3/bin/python3 -m src.preprocess              # all splits
    /opt/anaconda3/bin/python3 -m src.preprocess tier1 hold   # only these
"""

import sys
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

from src.xbd import find_pairs, load_buildings, load_image

RAW_ROOT = Path("data/xbd")
OUT_ROOT = Path("data/processed")
SPLITS = ["tier1", "tier3", "hold", "test"]
JPEG_QUALITY = 95

# Pixel values in the mask. 0 is background; anything above 0 is a building.
MASK_VALUES = {
    "no-damage": 1,
    "minor-damage": 2,
    "major-damage": 3,
    "destroyed": 4,
    "un-classified": 5,
}


def make_mask(label_path, height=1024, width=1024):
    mask = np.zeros((height, width), dtype=np.uint8)
    for b in load_buildings(label_path):
        points = np.round(b["polygon"]).astype(np.int32)
        cv2.fillPoly(mask, [points], MASK_VALUES.get(b["damage"], 5))
    return mask


def process_tile(args):
    pair, out_dir = args
    tile_id = pair["tile_id"]
    for phase in ("pre", "post"):
        out = out_dir / "images" / f"{tile_id}_{phase}.jpg"
        if not out.exists():
            rgb = load_image(pair[f"{phase}_image"])
            cv2.imwrite(str(out), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    mask_out = out_dir / "masks" / f"{tile_id}.png"
    if not mask_out.exists():
        cv2.imwrite(str(mask_out), make_mask(pair["post_label"]))


def process_split(split):
    pairs = find_pairs(RAW_ROOT / split)
    out_dir = OUT_ROOT / split
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "masks").mkdir(parents=True, exist_ok=True)

    jobs = [(row, out_dir) for row in pairs.to_dict("records")]
    with Pool() as pool:
        for i, _ in enumerate(pool.imap_unordered(process_tile, jobs, chunksize=8), 1):
            if i % 500 == 0 or i == len(jobs):
                print(f"{split}: {i}/{len(jobs)} tiles", flush=True)


if __name__ == "__main__":
    for split in sys.argv[1:] or SPLITS:
        process_split(split)
