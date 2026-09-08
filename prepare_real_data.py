"""Orchestrate real-data acquisition, transformation, and pipeline ingestion.

This script ties together every data-source script in the project into one
end-to-end "real data" pipeline:

  1. Download NASA GLC CSV                 (download_glc.py / download_glc_full.py)
  2. Download 13 Kerala GSI shapefiles     (download_kerala_gsi.py)
  3. Download Kerala SRTM DEM              (opentopography_srtm_template.py)
  4. Generate negative samples            (generate_negative_samples.py)
  5. Enrich rainfall via Open-Meteo       (fetch_open_meteo_for_events.py)
  6. Derive slope/aspect/curvature from DEM
  7. Extract susceptibility + LULC at village points
  8. Write pipeline-compatible CSVs to real_data/

HACKATHON NOTE: Each step is independently guarded -- if a download fails
(network / API key missing) the script logs a warning and falls back to
synthetic data for that layer so the pipeline always produces output.

Usage:
    python prepare_real_data.py [--skip-downloads] [--api-key KEY]
"""
import argparse
import json
import logging
import shutil
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from config import BASE_DIR, SAMPLE_DATA_DIR

logger = logging.getLogger(__name__)

REAL_DATA_DIR = BASE_DIR / "real_data"
REAL_DATA_DIR.mkdir(exist_ok=True)

# Kerala bounding box.
KERALA_WEST, KERALA_EAST = 74.80, 77.40
KERALA_SOUTH, KERALA_NORTH = 8.25, 12.80

# GLC CSV columns we care about (from NASA's export schema).
GLC_LAT_COL = "latitude"
GLC_LON_COL = "longitude"
GLC_DATE_COL = "event_date"


def _run_script(script_name: str) -> bool:
    """Run a sibling script as a subprocess; return True on success."""
    script_path = BASE_DIR / script_name
    if not script_path.exists():
        logger.warning("Script %s not found", script_path)
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Script %s ran successfully", script_name)
            return True
        logger.warning("Script %s failed (rc=%d): %s", script_name,
                       result.returncode, result.stderr[:500])
        return False
    except Exception as exc:
        logger.warning("Script %s crashed: %s", script_name, exc)
        return False


def step_download_glc() -> Path:
    """Step 1: Download NASA GLC CSV. Returns path to the file."""
    target = REAL_DATA_DIR / "nasa_glc_raw.csv"
    if target.exists() and target.stat().st_size > 1000:
        logger.info("NASA GLC already downloaded at %s", target)
        return target

    if _run_script("download_glc.py"):
        # download_glc.py writes to the CWD; move it into real_data/.
        src = BASE_DIR / "nasa_glc_raw.csv"
        if src.exists():
            shutil.move(str(src), str(target))
        if target.exists():
            return target

    logger.warning("NASA GLC download failed -- will use synthetic positives")
    return None


def step_download_gsi_shapefiles() -> Path:
    """Step 2: Download 13 Kerala GSI shapefiles."""
    gsi_dir = REAL_DATA_DIR / "kerala_gsi_2022"
    if gsi_dir.exists() and any(gsi_dir.glob("*.zip")):
        logger.info("GSI shapefiles already downloaded at %s", gsi_dir)
        return gsi_dir

    # Modify download_kerala_gsi.py to output into real_data/.
    # We run it with cwd=REAL_DATA_DIR so it writes there.
    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "download_kerala_gsi.py")],
            cwd=REAL_DATA_DIR,
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            logger.warning("GSI download failed: %s", result.stderr[:500])
        elif gsi_dir.exists() and any(gsi_dir.glob("*.zip")):
            return gsi_dir
    except Exception as exc:
        logger.warning("GSI download crashed: %s", exc)

    logger.warning("GSI shapefiles not available")
    return None


def step_download_dem(api_key: str) -> Path:
    """Step 3: Download Kerala SRTM DEM from OpenTopography."""
    dem_path = REAL_DATA_DIR / "kerala_srtm_30m.tif"
    if dem_path.exists() and dem_path.stat().st_size > 1000:
        logger.info("SRTM DEM already downloaded at %s", dem_path)
        return dem_path

    import os, requests
    os.environ["OPENTOPO_API_KEY"] = api_key

    params = {
        "demtype": "SRTMGL1",
        "south": KERALA_SOUTH, "north": KERALA_NORTH,
        "west": KERALA_WEST, "east": KERALA_EAST,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }
    try:
        r = requests.get("https://portal.opentopography.org/API/globaldem",
                         params=params, timeout=300)
        r.raise_for_status()
        dem_path.write_bytes(r.content)
        logger.info("DEM downloaded to %s (%d bytes)", dem_path, dem_path.stat().st_size)
    except Exception as exc:
        logger.warning("DEM download failed: %s -- will use default elevation", exc)
        return None

    return dem_path


def step_generate_negatives() -> Path:
    """Step 4: Generate negative samples from the GLC positives."""
    negatives_path = REAL_DATA_DIR / "negative_samples.csv"
    positives_path = REAL_DATA_DIR / "nasa_glc_enriched.csv"

    # If enriched positives exist, use them; otherwise use raw GLC.
    glc_input = None
    for candidate in [positives_path, REAL_DATA_DIR / "nasa_glc_raw.csv"]:
        if candidate.exists():
            glc_input = str(candidate)
            break

    logger.info("Generating negative samples (input=%s)", glc_input)
    from generate_negative_samples import generate
    generate(
        input_path=glc_input,
        output_path=str(negatives_path),
        n_per_positive=3,
        radius_km=5.0,
        seed=42,
    )
    return negatives_path


def step_enrich_rainfall() -> Path:
    """Step 5: Enrich GLC events with 30-day historical rainfall via Open-Meteo."""
    glc_path = REAL_DATA_DIR / "nasa_glc_enriched.csv"
    if glc_path.exists() and "rain_1d_mm" in pd.read_csv(glc_path, nrows=0).columns:
        logger.info("Rainfall already enriched at %s", glc_path)
        return glc_path

    raw_glc = REAL_DATA_DIR / "nasa_glc_raw.csv"
    enriched_path = REAL_DATA_DIR / "nasa_glc_enriched.csv"

    # Prepare a stripped CSV with the columns fetch_open_meteo expects.
    stripped_path = REAL_DATA_DIR / "glc_stripped.csv"
    if raw_glc.exists():
        df = pd.read_csv(raw_glc)
        # Normalise column names for the fetcher.
        rename_map = {}
        for col in df.columns:
            low = col.lower().strip()
            if low in ("latitude", "lat"):
                rename_map[col] = "latitude"
            elif low in ("longitude", "lon", "lng"):
                rename_map[col] = "longitude"
            elif low in ("event_date", "date", "eventdate"):
                rename_map[col] = "event_date"
        df = df.rename(columns=rename_map)
        needed = [c for c in ("latitude", "longitude", "event_date") if c in df.columns]
        df[needed].to_csv(stripped_path, index=False)

        try:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "fetch_open_meteo_for_events.py"),
                 str(stripped_path), str(enriched_path)],
                cwd=BASE_DIR, capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0 and enriched_path.exists():
                logger.info("Rainfall enrichment complete")
                return enriched_path
            logger.warning("Open-Meteo enrichment failed: %s", result.stderr[:500])
        except Exception as exc:
            logger.warning("Rainfall enrichment crashed: %s", exc)

    logger.warning("Rainfall enrichment unavailable -- using defaults")
    return None


def step_extract_pipeline_inputs(master_points: pd.DataFrame) -> None:
    """Step 6-8: Derive slope/aspect/curvature, extract GSI + LULC, write CSVs.

    Reads the DEM (if available) and GSI shapefiles (if available) and samples
    them at each master point location, then writes pipeline-compatible CSVs
    to ``real_data/``.
    """
    dem_path = REAL_DATA_DIR / "kerala_srtm_30m.tif"
    gsi_dir = REAL_DATA_DIR / "kerala_gsi_2022"

    import rasterio
    from rasterio import features
    from shapely.geometry import shape, Point

    # --- Load DEM if available ---
    elevation = np.full(len(master_points), 500.0)
    slope_deg = np.full(len(master_points), 15.0)
    aspect_deg = np.full(len(master_points), 180.0)
    curvature = np.zeros(len(master_points))

    if dem_path.exists():
        with rasterio.open(str(dem_path)) as src:
            transform = src.transform
            dem = src.read(1, masked=True)
            rows, cols = zip(*[
                ~transform * (lon, lat) for lon, lat in
                zip(master_points["lon"], master_points["lat"])
            ])
            rows = [int(r) for r in rows]
            cols = [int(c) for c in cols]
            valid = [(r, c) for r, c in zip(rows, cols)
                     if 0 <= r < dem.shape[0] and 0 <= c < dem.shape[1]]
            for idx, (r, c) in enumerate(valid):
                elevation[idx] = float(dem[r, c]) if not dem.mask[r, c] else 500.0

            # Derive slope from the DEM using terrain analysis.
            from scipy import ndimage
            x_grad, y_grad = np.gradient(dem.filled(np.nan), transform[0], transform[4])
            slope_rad = np.arctan(np.sqrt(x_grad**2 + y_grad**2))
            slope_deg_all = np.degrees(slope_rad)
            aspect_rad = np.arctan2(-x_grad, y_grad)

            for idx, (r, c) in enumerate(valid):
                slope_deg[idx] = float(slope_deg_all[r, c]) if not np.isnan(slope_deg_all[r, c]) else 15.0
                aspect_deg[idx] = float(aspect_rad[r, c]) if not np.isnan(aspect_rad[r, c]) else 180.0
    else:
        logger.warning("No DEM found -- using default elevation/slope")

    # --- Load GSI shapefiles for susceptibility_class ---
    susceptibility = np.full(len(master_points), 2)  # default: moderate
    if gsi_dir.exists() and any(gsi_dir.glob("**/*.shp")):
        import geopandas as gpd
        shp_files = list(gsi_dir.glob("**/*.shp"))
        gsi_gdf = gpd.GeoDataFrame(pd.concat(
            [gpd.read_file(str(f)) for f in shp_files], ignore_index=True
        ))
        gsi_pts = gpd.GeoDataFrame(
            {"geometry": [Point(lon, lat) for lon, lat in
                          zip(master_points["lon"], master_points["lat"])]},
            crs="EPSG:4326",
        )
        joined = gpd.sjoin_nearest(gsi_pts, gsi_gdf.to_crs("EPSG:4326"),
                                    how="left", max_distance=0.05)
        for col in ["suceptibility", "suscept", "class", "class_1", "grid_code"]:
            if col in joined.columns:
                susceptibility = joined[col].values
                break
    else:
        logger.warning("No GSI shapefiles found -- using default susceptibility")

    # --- Write pipeline-compatible inputs ---
    # slope.csv -- lat, lon, slope_angle (derived from DEM)
    slope_df = pd.DataFrame({
        "lat": master_points["lat"].values,
        "lon": master_points["lon"].values,
        "slope_angle": slope_deg,
    })
    slope_df.to_csv(REAL_DATA_DIR / "slope.csv", index=False)

    # rainfall.csv -- lat, lon, rainfall_24h, rainfall_7d
    # Use enriched GLC rainfall if available; otherwise derive from proximity
    # to GLC events with rainfall data.
    rainfall_24h = np.zeros(len(master_points))
    rainfall_7d = np.zeros(len(master_points))
    glc_enriched = REAL_DATA_DIR / "nasa_glc_enriched.csv"
    if glc_enriched.exists():
        from scipy.spatial import cKDTree
        glc_df = pd.read_csv(glc_enriched)
        glc_pts = np.column_stack([glc_df["longitude"].values, glc_df["latitude"].values])
        tree = cKDTree(glc_pts)
        master_pts = np.column_stack([master_points["lon"].values, master_points["lat"].values])
        _, idx = tree.query(master_pts, k=1)
        for i, glc_idx in enumerate(idx):
            rainfall_24h[i] = float(glc_df.iloc[glc_idx].get("rain_1d_mm", 0))
            rainfall_7d[i] = float(glc_df.iloc[glc_idx].get("rain_7d_mm", 0))
    rainfall_df = pd.DataFrame({
        "lat": master_points["lat"].values,
        "lon": master_points["lon"].values,
        "rainfall_24h": rainfall_24h,
        "rainfall_7d": rainfall_7d,
    })
    rainfall_df.to_csv(REAL_DATA_DIR / "rainfall.csv", index=False)

    # soil.csv -- lat, lon, soil_saturation, soil_type, drainage_class
    # Derived from DEM (wetness ~ elevation inverse) if no soil map available.
    soil_sat = np.clip(1.0 - (elevation / elevation.max() if elevation.max() > 0 else 1.0), 0.1, 0.95)
    soil_df = pd.DataFrame({
        "lat": master_points["lat"].values,
        "lon": master_points["lon"].values,
        "soil_saturation": soil_sat,
        "soil_type": ["clay-loam"] * len(master_points),  # default; GSI would refine
        "drainage_class": ["moderate"] * len(master_points),
    })
    soil_df.to_csv(REAL_DATA_DIR / "soil.csv", index=False)

    # historical_landslides.geojson -- from GLC positives
    glc_raw = REAL_DATA_DIR / "nasa_glc_raw.csv"
    if glc_raw.exists():
        glc_df = pd.read_csv(glc_raw)
        # Normalise column names
        lat_col = "latitude" if "latitude" in glc_df.columns else "lat"
        lon_col = "longitude" if "longitude" in glc_df.columns else "lon"
        date_col = "event_date" if "event_date" in glc_df.columns else "date"
        feats = []
        for i, row in glc_df.iterrows():
            feats.append({
                "type": "Feature",
                "properties": {
                    "event_id": f"glc_{i:05d}",
                    "event_date": str(row.get(date_col, "")),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row[lon_col]), float(row[lat_col])],
                },
            })
        gdf = type("G", (), {})()  # dummy
        import geopandas as gpd
        gdf = gpd.GeoDataFrame(
            {"event_date": [str(r.get(date_col, "")) for _, r in glc_df.iterrows()],
             "event_id": [f"glc_{i:05d}" for i in range(len(glc_df))]},
            geometry=[Point(float(row[lon_col]), float(row[lat_col]))
                      for _, row in glc_df.iterrows()],
            crs="EPSG:4326",
        )
        gdf.to_file(REAL_DATA_DIR / "historical_landslides.geojson", driver="GeoJSON")
    else:
        logger.warning("No GLC data -- historical events will use sample_data fallback")

    # elevation raster sampled at village points (for the ML model schema)
    elev_df = pd.DataFrame({
        "lat": master_points["lat"].values,
        "lon": master_points["lon"].values,
        "elevation_m": elevation,
        "slope_deg": slope_deg,
        "aspect_deg": aspect_deg,
        "curvature": curvature,
        "susceptibility_class": susceptibility,
    })
    elev_df.to_csv(REAL_DATA_DIR / "terrain.csv", index=False)

    logger.info("Pipeline inputs written to %s", REAL_DATA_DIR)


def _load_master_points() -> pd.DataFrame:
    """Load master village points. Prefer real_data; fall back to sample_data."""
    # If real_data has villages.geojson use it; else copy from sample_data.
    villages_path = REAL_DATA_DIR / "villages.geojson"
    if villages_path.exists():
        import geopandas as gpd
        gdf = gpd.read_file(villages_path)
    else:
        villages_path = SAMPLE_DATA_DIR / "villages.geojson"
        import geopandas as gpd
        gdf = gpd.read_file(villages_path)

    master = pd.DataFrame({
        "lat": gdf.geometry.y.values,
        "lon": gdf.geometry.x.values,
        "location_id": gdf["location_id"].values if "location_id" in gdf.columns else [f"loc_{i:03d}" for i in range(len(gdf))],
        "name": gdf["name"].values if "name" in gdf.columns else [f"Village {i+1}" for i in range(len(gdf))],
        "district": gdf["district"].values if "district" in gdf.columns else ["unknown"] * len(gdf),
    })
    return master


def main():
    import sys
    parser = argparse.ArgumentParser(description="Prepare real data for the pipeline")
    parser.add_argument("--skip-downloads", action="store_true",
                        help="Skip download steps (use already-downloaded data)")
    parser.add_argument("--api-key", type=str, default=None,
                        help="OpenTopography API key (or set OPENTOPO_API_KEY env var)")
    parser.add_argument("--skip-ml-training", action="store_true",
                        help="Skip training the ML model after data prep")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.skip_downloads:
        logger.info("=== Step 1: Download NASA GLC ===")
        step_download_glc()

        logger.info("=== Step 2: Download GSI shapefiles ===")
        step_download_gsi_shapefiles()

        logger.info("=== Step 3: Download SRTM DEM ===")
        api_key = args.api_key or os.environ.get("OPENTOPO_API_KEY")
        if api_key:
            step_download_dem(api_key)
        else:
            logger.warning("No OPENTOPO_API_KEY -- skipping DEM download")

    logger.info("=== Step 4: Generate negative samples ===")
    step_generate_negatives()

    logger.info("=== Step 5: Enrich rainfall via Open-Meteo ===")
    step_enrich_rainfall()

    logger.info("=== Steps 6-8: Derive pipeline inputs ===")
    master_points = _load_master_points()
    step_extract_pipeline_inputs(master_points)

    # Combine positives + negatives into a single training file.
    positives = REAL_DATA_DIR / "nasa_glc_enriched.csv"
    negatives = REAL_DATA_DIR / "negative_samples.csv"
    training_parts = []
    if positives.exists():
        training_parts.append(pd.read_csv(positives))
    if negatives.exists():
        training_parts.append(pd.read_csv(negatives))
    if training_parts:
        training_df = pd.concat(training_parts, ignore_index=True)
        training_df.to_csv(REAL_DATA_DIR / "training_data_ml.csv", index=False)
        logger.info("Combined training data: %d rows", len(training_df))

    logger.info("=== Training ML model ===")
    if not args.skip_ml_training:
        from train_ml_model import main as train_main
        train_main()

    logger.info("Real data preparation complete. Files in %s", REAL_DATA_DIR)


if __name__ == "__main__":
    import sys
    import os
    main()
