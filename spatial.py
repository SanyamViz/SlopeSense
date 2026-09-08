"""Spatial alignment layer.

Aligns every auxiliary dataset onto the master points layer using nearest-
neighbour spatial joins within a configurable tolerance. This is the single
place that decides the join key, so the rest of the pipeline works on a single
unified per-location table.

HACKATHON NOTE: Nearest-neighbour snapping assumes auxiliary points are roughly
colocated with villages. A production system would raster-sample DEMs and use
polygon joins by admin boundary; those are out of scope here.
"""
import logging

import geopandas as gpd

logger = logging.getLogger(__name__)


def align_to_points(master_gdf, layer_gdf, value_cols, tolerance_deg, suffixes=("_master", "_aux")):
    """Snap each master point to its nearest auxiliary record within tolerance.

    Returns a GeoDataFrame (one row per master point) with the auxiliary value
    columns appended. Master points with no match within the tolerance get NaN.
    HACKATHON NOTE: geometry is force-included in the aux subset so the result
    stays a GeoDataFrame (selecting only non-geometry cols would demote it).
    """
    left = master_gdf.to_crs(epsg=4326)
    # Keep geometry + requested value cols (geometry keeps it a GeoDataFrame).
    keep = ["geometry"] + [c for c in value_cols if c != "geometry"]
    aux = layer_gdf.to_crs(epsg=4326)[keep]
    # how='left' keeps every master point; unmatched get NaN in value cols.
    joined = gpd.sjoin_nearest(left, aux,
                               how="left",
                               max_distance=tolerance_deg,
                               distance_col="match_dist_deg")
    # Drop the index column sjoin_nearest adds.
    joined = joined.drop(columns=["index_right"], errors="ignore")
    unmatched = joined[value_cols[0]].isna().sum()
    if unmatched:
        logger.warning("%d master points had no %s match within %.4f deg",
                       unmatched, value_cols, tolerance_deg)
    return joined


def distance_to_nearest_km(master_gdf, events_gdf):
    """For each master point compute distance (km) and count of events within radius.

    Uses an azimuthal equidistant projection centred on the master centroid so
    great-circle distances are accurate per point. ASSUMPTION: the region fits in
    a small-area projection tolerance (~100 km radius) acceptable for a prototype.
    """
    # ASSUMPTION: project to a metre-based CRS centred on the dataset centroid.
    centroid = master_gdf.unary_union.centroid
    proj_crs = f"+proj=aeqd +lat_0={centroid.y} +lon_0={centroid.x} +datum=WGS84 +units=m"
    master_m = master_gdf.to_crs(proj_crs)
    events_m = events_gdf.to_crs(proj_crs)

    dists_km = []
    counts_5km = []
    radius_5km = 5000.0  # metres
    if events_m.shape[0] == 0:
        return [float("nan")] * len(master_m), [0] * len(master_m)
    # Vectorised nearest distance from every master point to the nearest event.
    nearest_m = master_m.geometry.apply(lambda g: float(events_m.distance(g).min()))
    within_mask = master_m.geometry.apply(lambda g: int((events_m.distance(g) <= radius_5km).sum()))
    dists_km = [round(d / 1000.0, 3) for d in nearest_m]
    counts_5km = [int(c) for c in within_mask]

    return dists_km, counts_5km


def build_unified_table(cfg, layers):
    """Merge every layer onto the master points into one analysis GeoDataFrame."""
    tol = cfg["spatial"]["join_tolerance_deg"]
    master = layers["points"].copy()

    master = align_to_points(master, layers["slope"], ["slope_angle"], tol)
    master = align_to_points(master, layers["rainfall"], ["rainfall_24h", "rainfall_7d"], tol)
    master = align_to_points(master, layers["soil"],
                             ["soil_saturation", "soil_type", "drainage_class"], tol)

    # Proximity factor computed geometrically rather than joined from a table.
    dists_km, counts_5km = distance_to_nearest_km(master, layers["historical_events"])
    master["proximity_to_event_km"] = dists_km
    master["historical_events_5km"] = counts_5km

    # ASSUMPTION: rainfall_intensity raw value is the 24h amount; the 7-day
    # cumulative figure feeds the normalizer note + composite normalisation.
    logger.info("Built unified table: %d locations", len(master))
    return master
