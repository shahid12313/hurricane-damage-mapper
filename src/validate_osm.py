"""Validate xBD georeferencing against OpenStreetMap building footprints.

OSM buildings are traced independently of xBD, on other imagery. For a sample of tiles, this
script downloads the OSM buildings around each tile (cached in data/osm/) and places every xBD
building two ways:

    label   using the longitude/latitude in the xBD label file
    tif     using the GeoTIFF tags (tiepoint + pixel size)

and measures for each way:

    hit_rate       share of xBD building centres that fall inside an OSM building
    median_dist_m  median distance from an xBD building centre to the nearest OSM building (0 inside)

It also searches for the translation (up to ±40 m) that best aligns the label positions with OSM;
if the labels are correct this shift should be close to zero.

Usage (from the project root; the first run downloads OSM data, about 20 minutes):

    /opt/anaconda3/bin/python3 -m src.validate_osm               # -> outputs/osm_validation.csv
    /opt/anaconda3/bin/python3 -m src.validate_osm --per-disaster 5
"""

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import shapely
import tifffile

from src.xbd import parse_wkt_polygon

RAW_ROOT = Path("data/xbd")
OSM_CACHE = Path("data/osm")
SPLITS = ["tier1", "tier3", "hold", "test"]
DISASTERS = ["palu-tsunami", "hurricane-matthew", "hurricane-harvey", "hurricane-michael",
             "hurricane-florence", "joplin-tornado", "santa-rosa-wildfire"]
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "xbd-georef-validation (academic project, contact via github.com/shahid12313/hurricane-damage-mapper)"
MARGIN_DEG = 0.001  # about 100 m around the tile, so shifted buildings are still covered
MIN_BUILDINGS = 30
SHIFTS_M = np.arange(-40, 41, 2)


def sample_tiles(per_disaster, seed=0):
    rng = random.Random(seed)
    chosen = []
    for disaster in DISASTERS:
        candidates = []
        for split in SPLITS:
            for label in sorted((RAW_ROOT / split / "labels").glob(f"{disaster}_*_post_disaster.json")):
                candidates.append(label)
        rng.shuffle(candidates)
        picked = []
        for label in candidates:
            with open(label) as f:
                if len(json.load(f)["features"]["lng_lat"]) >= MIN_BUILDINGS:
                    picked.append(label)
            if len(picked) == per_disaster:
                break
        chosen += picked
    return chosen


def xbd_buildings(label_path):
    """Each building's outline in lng/lat from the label, and from the GeoTIFF tags."""
    with open(label_path) as f:
        features = json.load(f)["features"]
    pixel = {feat["properties"]["uid"]: parse_wkt_polygon(feat["wkt"]) for feat in features["xy"]}
    tif_path = label_path.parent.parent / "images" / f"{label_path.stem}.tif"
    with tifffile.TiffFile(tif_path) as tif:
        tags = tif.pages[0].tags
        scale_x, scale_y = tags["ModelPixelScaleTag"].value[:2]
        lon0, lat0 = tags["ModelTiepointTag"].value[3:5]
    label_polys, tif_polys = [], []
    for feat in features["lng_lat"]:
        xy = pixel.get(feat["properties"]["uid"])
        if xy is None:
            continue
        label_polys.append(parse_wkt_polygon(feat["wkt"]))
        tif_polys.append(np.column_stack([lon0 + xy[:, 0] * scale_x, lat0 - xy[:, 1] * scale_y]))
    return label_polys, tif_polys


def fetch_osm(tile, bbox):
    """OSM building ways inside bbox (south, west, north, east), cached per tile."""
    OSM_CACHE.mkdir(parents=True, exist_ok=True)
    cache = OSM_CACHE / f"{tile}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    south, west, north, east = bbox
    query = f'[out:json][timeout:60];way["building"]({south},{west},{north},{east});out geom;'
    problem = None
    for attempt in range(6):
        try:
            response = requests.post(OVERPASS, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=240)
            if response.status_code == 200:
                elements = response.json()["elements"]
                cache.write_text(json.dumps(elements))
                time.sleep(2)  # be polite to the public server
                return elements
            problem = f"HTTP {response.status_code}"
        except requests.RequestException as error:  # the public server is often slow or busy
            problem = type(error).__name__
        time.sleep(20 * (attempt + 1))
    print(f"  skipped {tile}: Overpass {problem}", flush=True)
    return None


def to_metres(lnglat, origin):
    lon_c, lat_c = origin
    return np.column_stack([(lnglat[:, 0] - lon_c) * 111_320 * np.cos(np.radians(lat_c)),
                            (lnglat[:, 1] - lat_c) * 110_574])


def centres(polygons, origin):
    return np.array([to_metres(p, origin).mean(axis=0) for p in polygons])


def score(points, osm_polys, tree):
    pts = shapely.points(points)
    inside = np.zeros(len(points), bool)
    inside[np.unique(tree.query(pts, predicate="within")[0])] = True
    (point_idx, _), distances = tree.query_nearest(pts, return_distance=True)
    dist = np.full(len(points), np.inf)
    np.minimum.at(dist, point_idx, distances)  # a point can tie with several nearest buildings
    dist[inside] = 0.0
    return inside.mean(), float(np.median(dist))


def best_shift(points, tree):
    """Translation (in metres) that puts the most label building centres inside OSM buildings."""
    dx, dy = np.meshgrid(SHIFTS_M, SHIFTS_M)
    shifts = np.column_stack([dx.ravel(), dy.ravel()])
    moved = (points[None, :, :] + shifts[:, None, :]).reshape(-1, 2)
    hits = np.zeros(len(moved), bool)
    hits[np.unique(tree.query(shapely.points(moved), predicate="within")[0])] = True
    counts = hits.reshape(len(shifts), len(points)).sum(axis=1)
    best = counts.max()
    # several shifts can tie; take the one closest to zero
    tied = shifts[counts == best]
    sx, sy = tied[np.argmin(np.hypot(tied[:, 0], tied[:, 1]))]
    return float(sx), float(sy), int(best)


def validate_tile(label_path):
    tile = label_path.stem.replace("_post_disaster", "")
    label_polys, tif_polys = xbd_buildings(label_path)
    all_pts = np.vstack(label_polys + tif_polys)
    bbox = (all_pts[:, 1].min() - MARGIN_DEG, all_pts[:, 0].min() - MARGIN_DEG,
            all_pts[:, 1].max() + MARGIN_DEG, all_pts[:, 0].max() + MARGIN_DEG)
    elements = fetch_osm(tile, bbox)
    origin = (all_pts[:, 0].mean(), all_pts[:, 1].mean())
    if elements is None:
        return {"tile": tile, "disaster": tile.rsplit("_", 1)[0], "lat": origin[1], "xbd_buildings": len(label_polys)}

    osm_polys = []
    for way in elements:
        ring = np.array([[node["lon"], node["lat"]] for node in way.get("geometry", [])])
        if len(ring) >= 4:
            poly = shapely.make_valid(shapely.Polygon(to_metres(ring, origin)))
            if poly.area > 1:
                osm_polys.append(poly)
    row = {"tile": tile, "disaster": tile.rsplit("_", 1)[0], "lat": origin[1],
           "xbd_buildings": len(label_polys), "osm_buildings": len(osm_polys)}
    if len(osm_polys) < 5:
        return row

    tree = shapely.STRtree(osm_polys)
    label_pts, tif_pts = centres(label_polys, origin), centres(tif_polys, origin)
    row["label_hit_rate"], row["label_median_dist_m"] = score(label_pts, osm_polys, tree)
    row["tif_hit_rate"], row["tif_median_dist_m"] = score(tif_pts, osm_polys, tree)
    row["best_shift_x_m"], row["best_shift_y_m"], _ = best_shift(label_pts, tree)
    row["best_shift_m"] = float(np.hypot(row["best_shift_x_m"], row["best_shift_y_m"]))
    row["tif_vs_label_m"] = float(np.median(np.hypot(*(tif_pts - label_pts).T)))
    return row


def main(per_disaster):
    tiles = sample_tiles(per_disaster)
    print(f"{len(tiles)} tiles sampled from {len(DISASTERS)} disasters", flush=True)
    rows = []
    for i, label in enumerate(tiles, 1):
        rows.append(validate_tile(label))
        if i % 20 == 0 or i == len(tiles):
            print(f"{i}/{len(tiles)} tiles", flush=True)
    df = pd.DataFrame(rows)
    out = Path("outputs/osm_validation.csv")
    df.to_csv(out, index=False)

    scored = df.dropna(subset=["label_hit_rate"])
    covered = scored[scored.osm_buildings >= 0.5 * scored.xbd_buildings]
    print(f"\nwrote {out}: {len(df)} tiles, {len(scored)} with OSM buildings, "
          f"{len(covered)} where OSM has at least half as many buildings as xBD\n")
    for name, part in [("all tiles with OSM buildings", scored), ("well-covered tiles", covered)]:
        print(f"{name}: hit rate label {part.label_hit_rate.mean():.1%} vs tif {part.tif_hit_rate.mean():.1%}; "
              f"median distance label {part.label_median_dist_m.median():.1f} m vs tif {part.tif_median_dist_m.median():.1f} m; "
              f"best label shift median {part.best_shift_m.median():.1f} m")
    summary = covered.groupby("disaster").agg(
        tiles=("tile", "size"), lat=("lat", "mean"), tif_vs_label_m=("tif_vs_label_m", "median"),
        label_hit=("label_hit_rate", "mean"), tif_hit=("tif_hit_rate", "mean"),
        label_dist_m=("label_median_dist_m", "median"), tif_dist_m=("tif_median_dist_m", "median"),
        best_label_shift_m=("best_shift_m", "median"))
    print("\nwell-covered tiles by disaster:")
    print(summary.sort_values("lat", key=abs).round(2).to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate xBD georeferencing against OpenStreetMap buildings.")
    parser.add_argument("--per-disaster", type=int, default=40)
    args = parser.parse_args()
    main(args.per_disaster)
