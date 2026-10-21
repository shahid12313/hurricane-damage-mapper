"""Phase 4: run both trained models on tiles and export the results for the map dashboard.

For each tile:
  1. the localization model (phase 2) gives a building probability per pixel
  2. the damage model (phase 3) gives damage-level probabilities per pixel
  3. building pixels are split into separate buildings (connected regions)
  4. each building gets the damage level with the highest average probability inside it
  5. outlines are converted from pixels to longitude/latitude (see georeference)

Usage (from the project root):

    /opt/anaconda3/bin/python3 -m src.predict                     # hurricane tiles in hold and test
    /opt/anaconda3/bin/python3 -m src.predict --splits hold

Writes into dashboard/: data/<disaster>.geojson, data/tiles.json and images/<tile>_{pre,post}.jpg.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import tifffile
import torch

from src import damage, train
from src.dataset import read_rgb, to_tensor
from src.xbd import parse_wkt_polygon

DAMAGE_NAMES = damage.DAMAGE_NAMES
MIN_BUILDING_PIXELS = 30  # smaller blobs are almost always noise
DASHBOARD = Path("dashboard")


def load_models(device, loc_run="runs/loc_resnet34", damage_run="runs/damage_resnet34"):
    loc_model = train.build_model(pretrained=False).to(device).eval()
    loc_model.load_state_dict(torch.load(Path(loc_run) / "best.pt", map_location=device)["model"])
    dmg_model = damage.build_model(pretrained=False).to(device).eval()
    dmg_model.load_state_dict(torch.load(Path(damage_run) / "best.pt", map_location=device)["model"])
    return loc_model, dmg_model


@torch.no_grad()
def predict_maps(loc_model, dmg_model, pre, post, device):
    """Per-pixel building probability (H, W) and damage-level probabilities (4, H, W)."""
    building = torch.sigmoid(loc_model(to_tensor(pre)[None].to(device)))[0, 0]
    x = torch.cat([to_tensor(pre), to_tensor(post)])[None].to(device)
    levels = torch.softmax(dmg_model(x)[0, 1:5], dim=0)  # damage levels only, background left out
    return building.cpu().numpy(), levels.cpu().numpy()


def extract_buildings(building_prob, level_prob, threshold=0.5):
    """Split the building mask into separate buildings, each with a damage level and outline in pixels."""
    n, components = cv2.connectedComponents((building_prob > threshold).astype(np.uint8))
    buildings = []
    for k in range(1, n):
        inside = components == k
        if inside.sum() < MIN_BUILDING_PIXELS:
            continue
        mean_prob = level_prob[:, inside].mean(axis=1)
        contours, _ = cv2.findContours(inside.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        outline = cv2.approxPolyDP(max(contours, key=cv2.contourArea), 1.0, True)[:, 0, :]
        if len(outline) < 3:
            continue
        buildings.append({
            "damage": int(mean_prob.argmax()) + 1,
            "confidence": float(mean_prob.max()),
            "outline": outline.astype(np.float64),
        })
    return buildings


def georeference(label_path, tif_path):
    """Pixel -> (longitude, latitude) function for a tile.

    The label file lists every building both in pixels and in longitude/latitude, which fixes an
    exact affine transform. The GeoTIFF tags are used only for tiles without buildings: they claim
    square pixels in degrees, which is wrong away from the equator and shifts buildings by 10-30 m.
    """
    with open(label_path) as f:
        features = json.load(f)["features"]
    pixel_outlines = {feat["properties"]["uid"]: parse_wkt_polygon(feat["wkt"]) for feat in features["xy"]}
    pixels, lnglats = [], []
    for feat in features["lng_lat"]:
        xy, lnglat = pixel_outlines.get(feat["properties"]["uid"]), parse_wkt_polygon(feat["wkt"])
        if xy is not None and len(xy) == len(lnglat):
            pixels.append(xy)
            lnglats.append(lnglat)

    if sum(len(p) for p in pixels) >= 3:
        pixels = np.vstack(pixels)
        coef = np.linalg.lstsq(np.column_stack([pixels, np.ones(len(pixels))]), np.vstack(lnglats), rcond=None)[0]
    else:
        with tifffile.TiffFile(tif_path) as tif:
            tags = tif.pages[0].tags
            scale_x, scale_y = tags["ModelPixelScaleTag"].value[:2]
            lon0, lat0 = tags["ModelTiepointTag"].value[3:5]
        coef = np.array([[scale_x, 0.0], [0.0, -scale_y], [lon0, lat0]])

    def to_lnglat(xy):
        return np.column_stack([xy, np.ones(len(xy))]) @ coef

    return to_lnglat


def geojson_polygon(lnglat):
    ring = np.round(lnglat, 7).tolist()
    return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


def true_buildings(label_path, level_prob):
    """Ground-truth buildings with the model's damage level read from inside each true outline."""
    with open(label_path) as f:
        label = json.load(f)
    pixel_outlines = {feat["properties"]["uid"]: parse_wkt_polygon(feat["wkt"]) for feat in label["features"]["xy"]}
    predicted_level = np.argmax(level_prob, axis=0) + 1
    result = []
    for feat in label["features"]["lng_lat"]:
        props = feat["properties"]
        if props.get("subtype", "un-classified") not in DAMAGE_NAMES:
            continue
        mask = np.zeros(predicted_level.shape, np.uint8)
        cv2.fillPoly(mask, [np.round(pixel_outlines[props["uid"]]).astype(np.int32)], 1)
        votes = np.bincount(predicted_level[mask > 0], minlength=5)[1:]
        result.append({
            "damage": DAMAGE_NAMES.index(props["subtype"]) + 1,
            "model_damage": int(votes.argmax()) + 1 if votes.sum() else None,
            "lnglat": parse_wkt_polygon(feat["wkt"]),
        })
    return result


def export(splits, damage_run="runs/damage_v3", disaster_prefix="hurricane"):
    device = train.pick_device()
    loc_model, dmg_model = load_models(device, damage_run=damage_run)
    (DASHBOARD / "data").mkdir(parents=True, exist_ok=True)
    (DASHBOARD / "images").mkdir(parents=True, exist_ok=True)

    features = defaultdict(list)
    tiles = []
    for split in splits:
        processed = Path("data/processed") / split
        masks = sorted(p for p in (processed / "masks").glob("*.png") if p.stem.startswith(disaster_prefix))
        for i, mask_path in enumerate(masks, 1):
            tile_id = mask_path.stem
            disaster = tile_id.rsplit("_", 1)[0]
            pre = read_rgb(processed / "images" / f"{tile_id}_pre.jpg")
            post = read_rgb(processed / "images" / f"{tile_id}_post.jpg")
            building_prob, level_prob = predict_maps(loc_model, dmg_model, pre, post, device)
            label_path = Path("data/xbd") / split / "labels" / f"{tile_id}_post_disaster.json"
            to_lnglat = georeference(label_path, Path("data/xbd") / split / "images" / f"{tile_id}_post_disaster.tif")

            predicted = extract_buildings(building_prob, level_prob)
            for b in predicted:
                features[disaster].append({
                    "type": "Feature",
                    "geometry": geojson_polygon(to_lnglat(b["outline"])),
                    "properties": {"source": "predicted", "tile": tile_id, "damage": b["damage"],
                                   "confidence": round(b["confidence"], 3)},
                })
            truth = true_buildings(label_path, level_prob)
            for b in truth:
                features[disaster].append({
                    "type": "Feature",
                    "geometry": geojson_polygon(b["lnglat"]),
                    "properties": {"source": "true", "tile": tile_id, "damage": b["damage"],
                                   "model_damage": b["model_damage"]},
                })

            for phase, rgb in (("pre", pre), ("post", post)):
                small = cv2.resize(rgb, (512, 512), interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(DASHBOARD / "images" / f"{tile_id}_{phase}.jpg"),
                            cv2.cvtColor(small, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
            corners = to_lnglat(np.array([[0.0, 0.0], [1024.0, 1024.0]]))
            tiles.append({
                "tile": tile_id,
                "disaster": disaster,
                "split": split,
                "bounds": [[corners[1, 1], corners[0, 0]], [corners[0, 1], corners[1, 0]]],  # [[south, west], [north, east]]
                "predicted": [sum(b["damage"] == c for b in predicted) for c in range(1, 5)],
                "true": [sum(b["damage"] == c for b in truth) for c in range(1, 5)],
            })
            if i % 50 == 0 or i == len(masks):
                print(f"{split}: {i}/{len(masks)} tiles", flush=True)

    for disaster, feats in features.items():
        with open(DASHBOARD / "data" / f"{disaster}.geojson", "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))
    with open(DASHBOARD / "data" / "tiles.json", "w") as f:
        json.dump({"damage_names": DAMAGE_NAMES, "tiles": tiles}, f, separators=(",", ":"))
    print(f"wrote {len(tiles)} tiles, disasters: {', '.join(sorted(features))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export model predictions for the map dashboard.")
    parser.add_argument("--splits", nargs="+", default=["hold", "test"])
    parser.add_argument("--damage-run", default="runs/damage_v3", help="folder of the damage model to use")
    args = parser.parse_args()
    export(args.splits, args.damage_run)
