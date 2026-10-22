"""Compare the GeoTIFF georeferencing of every xBD image with the coordinates in its label file.

Each label file lists every building twice: in pixel coordinates ("xy") and in longitude/latitude
("lng_lat"). Fitting an affine transform between the two gives the georeferencing the labels use.
This script compares it with the GeoTIFF tags (ModelTiepointTag + ModelPixelScaleTag) for every
image, pre and post, in every split, and reports:

    offset_median_m, offset_max_m   how far apart the two place the building corners, in metres
    label_fit_max_m                 how exactly a single affine transform explains the labels
    label_ratio, tif_ratio          degrees of longitude per degree of latitude for one pixel
    expected_ratio                  1 / cos(latitude), the ratio for pixels that are square on the ground
    label_px_m, tif_px_x_m/y_m      pixel size on the ground implied by each, in metres

Usage (from the project root):

    /opt/anaconda3/bin/python3 -m src.check_georef        # -> outputs/georef_check.csv + summary
"""

import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile

from src.xbd import parse_wkt_polygon

RAW_ROOT = Path("data/xbd")
SPLITS = ["tier1", "tier3", "hold", "test"]
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON_EQUATOR = 111_320.0


def check_image(label_path):
    with open(label_path) as f:
        features = json.load(f)["features"]
    pixel_outlines = {feat["properties"]["uid"]: parse_wkt_polygon(feat["wkt"]) for feat in features["xy"]}
    pixels, lnglats = [], []
    for feat in features["lng_lat"]:
        xy, lnglat = pixel_outlines.get(feat["properties"]["uid"]), parse_wkt_polygon(feat["wkt"])
        if xy is not None and len(xy) == len(lnglat):
            pixels.append(xy)
            lnglats.append(lnglat)
    row = {"image": label_path.stem, "split": label_path.parent.parent.name,
           "disaster": label_path.stem.rsplit("_", 3)[0], "buildings": len(pixels)}
    if sum(len(p) for p in pixels) < 3:
        return row

    pixels, lnglats = np.vstack(pixels), np.vstack(lnglats)
    lat = lnglats[:, 1].mean()
    m_per_deg_lon = M_PER_DEG_LON_EQUATOR * np.cos(np.radians(lat))

    def metres(d_lnglat):
        return np.hypot(d_lnglat[:, 0] * m_per_deg_lon, d_lnglat[:, 1] * M_PER_DEG_LAT)

    design = np.column_stack([pixels, np.ones(len(pixels))])
    coef = np.linalg.lstsq(design, lnglats, rcond=None)[0]  # rows: x, y, 1 ; columns: lon, lat

    tif_path = label_path.parent.parent / "images" / f"{label_path.stem}.tif"
    with tifffile.TiffFile(tif_path) as tif:
        tags = tif.pages[0].tags
        scale_x, scale_y = tags["ModelPixelScaleTag"].value[:2]
        lon0, lat0 = tags["ModelTiepointTag"].value[3:5]
    tif_lnglat = np.column_stack([lon0 + pixels[:, 0] * scale_x, lat0 - pixels[:, 1] * scale_y])
    offset = metres(tif_lnglat - lnglats)

    row.update({
        "lat": lat,
        "offset_median_m": float(np.median(offset)),
        "offset_max_m": float(offset.max()),
        "label_fit_max_m": float(metres(design @ coef - lnglats).max()),
        "label_ratio": float(abs(coef[0, 0] / coef[1, 1])),
        "tif_ratio": float(scale_x / scale_y),
        "expected_ratio": float(1 / np.cos(np.radians(lat))),
        "label_rotation": float(np.hypot(coef[1, 0], coef[0, 1]) / np.hypot(coef[0, 0], coef[1, 1])),
        "label_px_m": float(abs(coef[1, 1]) * M_PER_DEG_LAT),
        "tif_px_x_m": float(scale_x * m_per_deg_lon),
        "tif_px_y_m": float(scale_y * M_PER_DEG_LAT),
    })
    return row


def main():
    labels = [p for split in SPLITS for p in sorted((RAW_ROOT / split / "labels").glob("*.json"))]
    with Pool() as pool:
        rows = pool.map(check_image, labels, chunksize=64)
    df = pd.DataFrame(rows)
    out = Path("outputs/georef_check.csv")
    df.to_csv(out, index=False)

    checked = df.dropna(subset=["offset_median_m"])
    print(f"images: {len(df):,}  with buildings (checked): {len(checked):,}  -> {out}\n")
    print("offset between GeoTIFF tags and label coordinates (median per image, metres):")
    print(checked.offset_median_m.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).round(2).to_string(), "\n")
    print(f"images with median offset > 5 m: {(checked.offset_median_m > 5).mean():.1%}   > 10 m: {(checked.offset_median_m > 10).mean():.1%}")
    print(f"label transform fits within 0.1 m: {(checked.label_fit_max_m < 0.1).mean():.1%}   max rotation term: {checked.label_rotation.max():.2e}")
    print(f"label ratio / expected ratio: median {np.median(checked.label_ratio / checked.expected_ratio):.4f}  "
          f"(5-95%: {np.percentile(checked.label_ratio / checked.expected_ratio, 5):.4f}-{np.percentile(checked.label_ratio / checked.expected_ratio, 95):.4f})")
    print(f"tif ratio: min {checked.tif_ratio.min():.4f}  max {checked.tif_ratio.max():.4f}\n")
    by = checked.groupby("disaster").agg(images=("image", "size"), lat=("lat", "mean"),
                                         offset_median_m=("offset_median_m", "median"),
                                         offset_max_m=("offset_max_m", "max"),
                                         label_px_m=("label_px_m", "median"),
                                         tif_px_x_m=("tif_px_x_m", "median"), tif_px_y_m=("tif_px_y_m", "median"))
    print(by.sort_values("offset_median_m").round(2).to_string())


if __name__ == "__main__":
    main()
