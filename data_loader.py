"""Data loading layer.

HACKATHON NOTE: loaders are intentionally permissive about schema. Each loader
accepts a mapping of expected-column -> actual-column so you can drop in real
files with different header names without editing this module.

ASSUMPTION: every auxiliary dataset is already point-based (lat/lon) or can be
treated as such. Raster data (e.g. DEMs) would need an upstream sampling step
that we skip for the prototype.
"""
import logging

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

logger = logging.getLogger(__name__)


def _to_geodataframe(df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon") -> gpd.GeoDataFrame:
    """Promote a DataFrame with lat/lon columns into a GeoDataFrame (WGS84)."""
    gdf = gdf_from_xy(df, lon_col, lat_col)
    return gdf


def gdf_from_xy(df: pd.DataFrame, lon_col: str, lat_col: str) -> gpd.GeoDataFrame:
    geom = [Point(xy) for xy in zip(df[lon_col].astype(float), df[lat_col].astype(float))]
    return gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")


def load_master_points(path, lat_col="lat", lon_col="lon", id_col="location_id",
                       name_col="name", district_col="district"):
    """Load the authoritative set of village/district locations to score.

    This is the 'join key' anchor layer: every other dataset is aligned here.
    Join key = geographic nearest-neighbour (lat/lon) with district_id as fallback.
    HACKATHON NOTE: if the file carries a Point geometry but no lat/lon columns,
    lat/lon are derived from the geometry so alignment logic below works uniformly.
    """
    gdf = gpd.read_file(path)
    # Normalise id/name/district column names if the user remapped them.
    rename = {}
    for actual, canonical in [(id_col, "location_id"), (name_col, "name"),
                              (district_col, "district"), (lat_col, "lat"), (lon_col, "lon")]:
        if actual != canonical and actual in gdf.columns:
            rename[actual] = canonical
    gdf = gdf.rename(columns=rename)
    # Derive lat/lon from geometry when the file didn't carry them as columns.
    if "lat" not in gdf.columns or "lon" not in gdf.columns:
        gdf["lon"] = gdf.geometry.x
        gdf["lat"] = gdf.geometry.y
    gdf["lat"] = gdf["lat"].astype(float)
    gdf["lon"] = gdf["lon"].astype(float)
    logger.info("Loaded %d master points from %s", len(gdf), path)
    return gdf


def load_point_dataset(path, value_cols, lat_col="lat", lon_col="lon", extra_cols=None):
    """Generic loader for slope / rainfall / soil point datasets.

    value_cols: list of column names to keep as factor inputs.
    """
    df = pd.read_csv(path)
    needed = list(value_cols) + [lat_col, lon_col]
    if extra_cols:
        needed += list(extra_cols)
    needed = [c for c in needed if c in df.columns]
    df = df[needed].copy()
    gdf = gdf_from_xy(df, lon_col, lat_col)
    logger.info("Loaded %d point records from %s", len(gdf), path)
    return gdf


def load_historical_events(path, lat_col="lat", lon_col="lon", date_col="event_date"):
    """Load historical landslide event points used for proximity calculations.

    Accepts either a CSV (with lat/lon columns) or a GeoJSON (Point geometry).
    Always returns a GeoDataFrame with lat/lon + date columns populated.
    """
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        gdf = gdf_from_xy(df, lon_col, lat_col)
    else:
        gdf = gpd.read_file(path)  # preserves Point geometry
        # Derive lat/lon columns from geometry if the source didn't carry them.
        if lon_col not in gdf.columns:
            gdf[lon_col] = gdf.geometry.x
        if lat_col not in gdf.columns:
            gdf[lat_col] = gdf.geometry.y
    if date_col in gdf.columns:
        gdf[date_col] = pd.to_datetime(gdf[date_col], errors="coerce")
    logger.info("Loaded %d historical events from %s", len(gdf), path)
    return gdf


def load_all_inputs(cfg):
    """Convenience: load every configured input and return a dict of GeoDataFrames."""
    inputs = cfg["inputs"]
    layers = {
        "points": load_master_points(inputs["points"]),
        "slope": load_point_dataset(inputs["slope"], ["slope_angle"]),
        "rainfall": load_point_dataset(inputs["rainfall"], ["rainfall_24h", "rainfall_7d"]),
        "soil": load_point_dataset(inputs["soil"], ["soil_saturation", "soil_type", "drainage_class"]),
        "historical_events": load_historical_events(inputs["historical_events"]),
    }
    return layers
