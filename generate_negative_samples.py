"""Generate negative samples (label=0) for ML model training.

The NASA Global Landslide Catalog (GLC) contains only positive events.
To train a classifier you need negatives -- points with comparable
terrain / rainfall conditions but no reported landslide. This module
generates those negatives by sampling nearby geographic points around
each positive event and re-using the event's rainfall / DEM context.

HACKATHON NOTE: if real GLC data is not available (no network), the
generator falls back to a synthetic event set so the training pipeline
still produces a model artifact. See ``_synthetic_positives()``.

Usage:
    python generate_negative_samples.py \\
        --input nasa_glc_enriched.csv \\
        --output negative_samples.csv \\
        --n-negatives-per-positive 3 \\
        --radius-km 5

Output schema (matches data-pack §2 "Target Model Schema"):
    record_id, event_date, latitude, longitude, landslide_label,
    rain_1d_mm, rain_3d_mm, rain_7d_mm, rain_30d_mm,
    elevation_m, slope_deg, aspect_deg, curvature,
    susceptibility_class, lulc_class, vegetation_proxy
"""
import argparse
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0

# Kerala bounding box (matches data pack / OpenTopography DEM request).
KERALA_WEST, KERALA_EAST = 74.80, 77.40
KERALA_SOUTH, KERALA_NORTH = 8.25, 12.80

TARGET_COLUMNS = [
    "record_id", "event_date", "latitude", "longitude", "landslide_label",
    "rain_1d_mm", "rain_3d_mm", "rain_7d_mm", "rain_30d_mm",
    "elevation_m", "slope_deg", "aspect_deg", "curvature",
    "susceptibility_class", "lulc_class", "vegetation_proxy",
]


def _synthetic_positives(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic positive events when real GLC data is unavailable."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        lat = float(rng.uniform(KERALA_SOUTH + 0.3, KERALA_NORTH - 0.3))
        lon = float(rng.uniform(KERALA_WEST + 0.3, KERALA_EAST - 0.3))
        rows.append({
            "record_id": f"synth_pos_{i:04d}",
            "event_date": f"20{rng.integers(15, 26):02d}-{rng.integers(1, 13):02d}-{rng.integers(1, 29):02d}",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "landslide_label": 1,
            "rain_1d_mm": round(float(rng.uniform(50, 300)), 2),
            "rain_3d_mm": round(float(rng.uniform(100, 600)), 2),
            "rain_7d_mm": round(float(rng.uniform(200, 900)), 2),
            "rain_30d_mm": round(float(rng.uniform(300, 2000)), 2),
            "elevation_m": round(float(rng.uniform(5, 2500)), 1),
            "slope_deg": round(float(rng.uniform(5, 55)), 2),
            "aspect_deg": round(float(rng.uniform(0, 360)), 1),
            "curvature": round(float(rng.uniform(-2.0, 2.0)), 4),
            "susceptibility_class": int(rng.integers(1, 5)),
            "lulc_class": int(rng.integers(1, 9)),
            "vegetation_proxy": round(float(rng.uniform(0.1, 0.9)), 4),
        })
    df = pd.DataFrame(rows, columns=TARGET_COLUMNS)
    logger.info("Generated %d synthetic positive events (fallback)", len(df))
    return df


def _offset_point(lat: float, lon: float, radius_km: float, rng: np.random.Generator) -> tuple[float, float]:
    """Return a random point within `radius_km` of (lat, lon), clamped to Kerala."""
    bearing = float(rng.uniform(0, 360))
    distance = float(rng.uniform(0, radius_km))
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)
    dist_ratio = distance / EARTH_RADIUS_KM

    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(dist_ratio) +
        math.cos(lat_rad) * math.sin(dist_ratio) * math.cos(bearing_rad)
    )
    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(dist_ratio) * math.cos(lat_rad),
        math.cos(dist_ratio) - math.sin(lat_rad) * math.sin(new_lat_rad),
    )
    new_lat = math.degrees(new_lat_rad)
    new_lon = math.degrees(new_lon_rad)

    # Clamp to Kerala bounding box so negatives stay in-region.
    new_lat = float(np.clip(new_lat, KERALA_SOUTH, KERALA_NORTH))
    new_lon = float(np.clip(new_lon, KERALA_WEST, KERALA_EAST))
    return new_lat, new_lon


def _sample_context(row: pd.Series, rng: np.random.Generator) -> dict:
    """Jitter the continuous context fields so negatives aren't exact copies."""
    def _jitter(value, spread_pct=0.25):
        v = float(value) if pd.notna(value) else 0.0
        jitter = 1.0 + rng.uniform(-spread_pct, spread_pct)
        return round(v * jitter, 4)

    return {
        "rain_1d_mm": _jitter(row.get("rain_1d_mm", 0)),
        "rain_3d_mm": _jitter(row.get("rain_3d_mm", 0)),
        "rain_7d_mm": _jitter(row.get("rain_7d_mm", 0)),
        "rain_30d_mm": _jitter(row.get("rain_30d_mm", 0)),
        "elevation_m": _jitter(row.get("elevation_m", 0), 0.1),
        "slope_deg": _jitter(row.get("slope_deg", 0), 0.15),
        "aspect_deg": round(float(rng.uniform(0, 360)), 1),
        "curvature": _jitter(row.get("curvature", 0), 0.15),
        "susceptibility_class": int(row.get("susceptibility_class", 2)) if rng.random() > 0.3 else int(rng.integers(1, 5)),
        "lulc_class": int(row.get("lulc_class", 4)) if rng.random() > 0.3 else int(rng.integers(1, 9)),
        "vegetation_proxy": round(float(np.clip(_jitter(row.get("vegetation_proxy", 0.5), 0.2), 0, 1)), 4),
    }


def generate_negatives(
    positives: pd.DataFrame,
    n_per_positive: int = 3,
    radius_km: float = 5.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate negative samples around each positive event.

    For each positive row, sample `n_per_positive` nearby geographic points
    within `radius_km`.  Each negative inherits a jittered copy of the parent's
    environmental context (rainfall, elevation, slope, etc.) so negatives are
    geographically and environmentally plausible.

    Args:
        positives: DataFrame of positive events with the target schema columns.
        n_per_positive: how many negatives to generate per positive event.
        radius_km: max distance from the parent event to sample negatives.
        seed: RNG seed for reproducibility.

    Returns:
        DataFrame of negative samples (landslide_label=0).
    """
    rng = np.random.default_rng(seed)
    negatives = []

    for _, row in positives.iterrows():
        lat = float(row["latitude"])
        lon = float(row["longitude"])

        for j in range(n_per_positive):
            neg_lat, neg_lon = _offset_point(lat, lon, radius_km, rng)
            ctx = _sample_context(row, rng)
            neg_id = f"NEG_{row['record_id']}_{j}"

            neg = {
                "record_id": neg_id,
                "event_date": row.get("event_date", ""),
                "latitude": round(neg_lat, 6),
                "longitude": round(neg_lon, 6),
                "landslide_label": 0,
                **ctx,
            }
            negatives.append(neg)

    neg_df = pd.DataFrame(negatives, columns=TARGET_COLUMNS)
    return neg_df


def generate(input_path: Path | str | None = None,
             output_path: Path | str = "negative_samples.csv",
             n_per_positive: int = 3,
             radius_km: float = 5.0,
             seed: int = 42) -> pd.DataFrame:
    """Top-level entry point: load positives, generate negatives, write CSV.

    If ``input_path`` is None or the file doesn't exist, falls back to
    synthetic positives so the training pipeline always has data.
    """
    if input_path is not None and Path(input_path).exists():
        logger.info("Loading positive events from %s", input_path)
        positives = pd.read_csv(input_path)
        # Ensure label column exists and is 1 for all positives.
        if "landslide_label" not in positives.columns:
            positives["landslide_label"] = 1
        positives["landslide_label"] = 1
        logger.info("Loaded %d positive events", len(positives))
    else:
        logger.warning("No input file at %s -- generating synthetic positives", input_path)
        positives = _synthetic_positives(seed=seed)

    negatives = generate_negatives(positives, n_per_positive=n_per_positive,
                                  radius_km=radius_km, seed=seed)
    logger.info("Generated %d negative samples (%.1f:1 ratio)",
                len(negatives), n_per_positive)

    negatives.to_csv(output_path, index=False)
    logger.info("Wrote negatives to %s", output_path)
    return negatives


def main():
    parser = argparse.ArgumentParser(
        description="Generate negative (label=0) landslide samples."
    )
    parser.add_argument("--input", type=str, default=None,
                        help="Path to enriched GLC CSV (positives). "
                             "If missing, synthetic positives are used.")
    parser.add_argument("--output", type=str, default="negative_samples.csv",
                        help="Output CSV path")
    parser.add_argument("--n-negatives-per-positive", type=int, default=3,
                        help="Negatives to generate per positive event")
    parser.add_argument("--radius-km", type=float, default=5.0,
                        help="Max distance from parent event for negatives")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducibility")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    generate(
        input_path=args.input,
        output_path=args.output,
        n_per_positive=args.n_negatives_per_positive,
        radius_km=args.radius_km,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
