"""Helpers for reading the xBD (xView2) building damage dataset.

Expected layout after extracting the download:

    data/xbd/train/images/hurricane-harvey_00000001_pre_disaster.tif   (.png in the smaller release)
    data/xbd/train/images/hurricane-harvey_00000001_post_disaster.tif
    data/xbd/train/labels/hurricane-harvey_00000001_post_disaster.json
    ...

The same layout repeats for tier3/, test/ and hold/.
"""

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tifffile
from matplotlib.patches import Polygon as MplPolygon
from PIL import Image

DAMAGE_CLASSES = ["no-damage", "minor-damage", "major-damage", "destroyed", "un-classified"]

DAMAGE_COLORS = {
    "no-damage": "#2ca02c",
    "minor-damage": "#f2c14e",
    "major-damage": "#f28e2b",
    "destroyed": "#d62728",
    "un-classified": "#9e9e9e",
}

_NUM_PAIR = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)")


def parse_wkt_polygon(wkt):
    """Return the outer ring of a WKT POLYGON as an (N, 2) array of pixel x, y."""
    outer = wkt[wkt.index("((") + 2:]
    outer = outer.split(")")[0]
    return np.array([(float(x), float(y)) for x, y in _NUM_PAIR.findall(outer)])


def polygon_area(points):
    """Shoelace formula, in square pixels."""
    x, y = points[:, 0], points[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def find_pairs(split_dir):
    """One row per tile: disaster name, tile id, and the pre/post image and label paths."""
    split_dir = Path(split_dir)
    # The PNG release and the full GeoTIFF release differ only in image extension
    ext = ".tif" if any((split_dir / "images").glob("*.tif")) else ".png"
    rows = []
    for post_label in sorted((split_dir / "labels").glob("*_post_disaster.json")):
        tile_id = post_label.name.replace("_post_disaster.json", "")
        disaster = tile_id.rsplit("_", 1)[0]
        rows.append({
            "tile_id": tile_id,
            "disaster": disaster,
            "pre_image": split_dir / "images" / f"{tile_id}_pre_disaster{ext}",
            "post_image": split_dir / "images" / f"{tile_id}_post_disaster{ext}",
            "post_label": post_label,
        })
    return pd.DataFrame(rows)


def load_image(path):
    """RGB image as a (H, W, 3) uint8 array.

    The GeoTIFF release stores pixels as int16 that already lie in 0-255, which Pillow cannot open.
    """
    path = Path(path)
    if path.suffix.lower() in (".tif", ".tiff"):
        return np.clip(tifffile.imread(path), 0, 255).astype(np.uint8)
    return np.array(Image.open(path).convert("RGB"))


def load_buildings(label_path):
    """Buildings in a post-disaster label file, each with its damage level and outline."""
    with open(label_path) as f:
        label = json.load(f)
    buildings = []
    for feature in label["features"]["xy"]:
        props = feature["properties"]
        if props.get("feature_type", "building") != "building":
            continue
        buildings.append({
            "uid": props.get("uid"),
            "damage": props.get("subtype", "un-classified"),
            "polygon": parse_wkt_polygon(feature["wkt"]),
        })
    return buildings


def load_metadata(label_path):
    with open(label_path) as f:
        return json.load(f).get("metadata", {})


def building_table(pairs):
    """One row per building across all tiles, for counting and plotting."""
    rows = []
    for pair in pairs.itertuples():
        for b in load_buildings(pair.post_label):
            rows.append({
                "tile_id": pair.tile_id,
                "disaster": pair.disaster,
                "uid": b["uid"],
                "damage": b["damage"],
                "area_px": polygon_area(b["polygon"]),
            })
    return pd.DataFrame(rows)


def show_pair(pair, figsize=(14, 7)):
    """Pre-disaster image next to the post-disaster image with damage-colored outlines."""
    fig, (ax_pre, ax_post) = plt.subplots(1, 2, figsize=figsize)
    ax_pre.imshow(load_image(pair["pre_image"]))
    ax_post.imshow(load_image(pair["post_image"]))

    counts = {}
    for b in load_buildings(pair["post_label"]):
        color = DAMAGE_COLORS.get(b["damage"], "#9e9e9e")
        ax_post.add_patch(MplPolygon(b["polygon"], closed=True, fill=False, edgecolor=color, linewidth=1.2))
        counts[b["damage"]] = counts.get(b["damage"], 0) + 1

    ax_pre.set_title(f"{pair['tile_id']} — before")
    ax_post.set_title("after: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for ax in (ax_pre, ax_post):
        ax.axis("off")

    handles = [plt.Line2D([], [], color=c, linewidth=3, label=k) for k, c in DAMAGE_COLORS.items()]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig
