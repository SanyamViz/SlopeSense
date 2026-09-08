"""Generate a small synthetic landslide dataset for the hackathon prototype.

Produces the 5 input files referenced by config.CONFIG['inputs'] under
sample_data/. Most values are PLAINLY FAKE and seeded for reproducibility;
they exist only so the pipeline runs end-to-end and the backend can be demoed
without waiting on real downloads.

ASSUMPTION: point-based factors scattered near each village (within the spatial
join tolerance) so the nearest-neighbour alignment always finds a match.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from config import CONFIG, SAMPLE_DATA_DIR

RNG = np.random.default_rng(42)

# Kerala bounding box (matches the data pack / OpenTopography request).
WEST, EAST = 74.80, 77.40
SOUTH, NORTH = 8.25, 12.80
N_VILLAGES = 142

# Real Kerala place names — Wayanad names are assigned to seed indices so
# the pipeline's high-risk / severe cases map to the documented Wayanad 2024
# event area.  Remaining slots get generic "Village N" labels.
REAL_NAMES: dict[int, dict] = {
    # ---- Wayanad (seed / high-risk villages near Mundakkai-Chooralmala) ----
    10:  {"name": "Meppadi",       "district": "Wayanad",       "lat": 11.5833, "lon": 76.1500},
    14:  {"name": "Mundakkai",     "district": "Wayanad",       "lat": 11.5167, "lon": 76.1333},
    24:  {"name": "Chooralmala",   "district": "Wayanad",       "lat": 11.5300, "lon": 76.1500},
    38:  {"name": "Kambalakkad",   "district": "Wayanad",       "lat": 11.6000, "lon": 76.2000},
    52:  {"name": "Kalpetta",      "district": "Wayanad",       "lat": 11.6100, "lon": 76.2500},
    66:  {"name": "Pulpally",      "district": "Wayanad",       "lat": 11.6500, "lon": 76.2000},
    80:  {"name": "Sulthan Bathery","district": "Wayanad",      "lat": 11.6700, "lon": 76.2700},
    94:  {"name": "Mananthavady",  "district": "Wayanad",       "lat": 11.7000, "lon": 76.2000},
    108: {"name": "Padinharethara","district": "Wayanad",       "lat": 11.5800, "lon": 76.1000},
    122:{"name": "Vellamunda",    "district": "Wayanad",       "lat": 11.5500, "lon": 76.0500},
    # ---- Selected non-Wayanad districts for geographic spread ----
    4:  {"name": "Thekkady",      "district": "Idukki",        "lat": 9.5333,  "lon": 77.2000},
    29: {"name": "Punalur",       "district": "Kollam",        "lat": 9.0167,  "lon": 77.0167},
    50: {"name": "Munnar",        "district": "Idukki",        "lat": 10.0883, "lon": 77.0594},
    72: {"name": "Gavi",          "district": "Pathanamthitta","lat": 9.4333,  "lon": 77.1667},
    101:{"name": "Vagamon",       "district": "Kottayam",      "lat": 9.6833,  "lon": 76.9167},
    136:{"name": "Munnar-Highlands","district": "Idukki",     "lat": 10.1300, "lon": 77.0800},
}

SOIL_TYPES = ["clay-loam", "sandy-loam", "silty-clay", "loam", "clay"]
DRAINAGE   = ["poor", "moderate", "good", "excellent"]

# HACKATHON SEED: indices that get deliberately elevated risk factors so the
# demo shows "severe" cases and /alerts/active has something to sort.
SEED_INDICES = {14, 72, 101, 136}


def _scatter_near(lat, lon, spread_deg=0.015, n=1):
    """Return n (lat, lon) points jittered by up to ~spread_deg (~1.7 km)."""
    out = []
    for _ in range(n):
        dlat = RNG.uniform(-spread_deg, spread_deg)
        dlon = RNG.uniform(-spread_deg, spread_deg)
        out.append((float(np.clip(lat + dlat, SOUTH, NORTH)),
                    float(np.clip(lon + dlon, WEST, EAST))))
    return out


def generate():
    SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ---- master points (villages) ----
    lats = RNG.uniform(SOUTH + 0.5, NORTH - 0.5, N_VILLAGES)
    lons = RNG.uniform(WEST + 0.5, EAST - 0.5, N_VILLAGES)
    names, districts = [], []
    for i in range(N_VILLAGES):
        if i in REAL_NAMES:
            names.append(REAL_NAMES[i]["name"])
            districts.append(REAL_NAMES[i]["district"])
            lats[i] = REAL_NAMES[i]["lat"]
            lons[i] = REAL_NAMES[i]["lon"]
        else:
            names.append(f"Village {i+1}")
            districts.append(
                ["Thiruvananthapuram", "Kollam", "Pathanamthitta", "Kottayam",
                 "Idukki", "Ernakulam", "Thrissur", "Palakkas", "Malappuram",
                 "Kozhikode", "Wayanad", "Kannur", "Kasaragod", "Alappuzha"
                 ][i % 14]
            )

    feats = []
    for i in range(N_VILLAGES):
        feats.append({
            "type": "Feature",
            "properties": {
                "location_id": f"loc_{i:03d}",
                "name": names[i],
                "district": districts[i],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(float(lons[i]), 6), round(float(lats[i]), 6)]
            },
        })
    gdf = gpd.GeoDataFrame(
        {"location_id": [f"loc_{i:03d}" for i in range(N_VILLAGES)],
         "name": names,
         "district": districts,
         "lat": lats, "lon": lons},
        geometry=[Point(lon, lat) for lon, lat in zip(lons, lats)],
        crs="EPSG:4326",
    )
    gdf.to_file(SAMPLE_DATA_DIR / "villages.geojson", driver="GeoJSON")

    # ---- slope (degrees) near each village ----
    slope_rows = []
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        bl, bn = _scatter_near(lat, lon)[0]
        if i in SEED_INDICES:
            sa = round(float(RNG.uniform(44, 47)), 2)
        else:
            sa = round(float(RNG.uniform(2, 46)), 2)
        slope_rows.append({"lat": bl, "lon": bn, "slope_angle": sa})
    pd.DataFrame(slope_rows).to_csv(SAMPLE_DATA_DIR / "slope.csv", index=False)

    # ---- rainfall (24h + 7d cumulative mm) near each village ----
    rain_rows = []
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        bl, bn = _scatter_near(lat, lon)[0]
        if i in SEED_INDICES:
            r24 = round(float(RNG.uniform(110, 140)), 2)
            r7  = round(float(RNG.uniform(280, 340)), 2)
        else:
            r24 = round(float(RNG.uniform(0, 130)), 2)
            r7  = round(float(RNG.uniform(10, 320)), 2)
        rain_rows.append({"lat": bl, "lon": bn, "rainfall_24h": r24, "rainfall_7d": r7})
    pd.DataFrame(rain_rows).to_csv(SAMPLE_DATA_DIR / "rainfall.csv", index=False)

    # ---- soil (saturation fraction + type + drainage) near each village ----
    soil_rows = []
    for i, (lat, lon) in enumerate(zip(lats, lons)):
        bl, bn = _scatter_near(lat, lon)[0]
        if i in SEED_INDICES:
            sat = round(float(RNG.uniform(0.80, 0.95)), 4)
            st  = "clay-loam"
            dr  = "poor"
        else:
            sat = round(float(np.clip(RNG.uniform(0.15, 0.92), 0, 1)), 4)
            st  = RNG.choice(SOIL_TYPES)
            dr  = RNG.choice(DRAINAGE)
        soil_rows.append({"lat": bl, "lon": bn, "soil_saturation": sat,
                          "soil_type": st, "drainage_class": dr})
    pd.DataFrame(soil_rows).to_csv(SAMPLE_DATA_DIR / "soil.csv", index=False)

    # ---- historical landslide events (~30, scattered across Kerala) ----
    n_events = 30
    ev_lats = RNG.uniform(SOUTH + 0.5, NORTH - 0.5, n_events).tolist()
    ev_lons = RNG.uniform(WEST + 0.5, EAST - 0.5, n_events).tolist()
    # Plant events exactly on the seed villages so their proximity factor
    # normalises to ~1.0 (drives severe scores).
    for i in SEED_INDICES:
        ev_lats.append(float(lats[i]))
        ev_lons.append(float(lons[i]))
        n_events += 1
    n_events_actual = n_events
    dates = pd.date_range("2015-01-01", "2025-01-01",
                          periods=n_events_actual).strftime("%Y-%m-%d")
    feats = []
    for i in range(n_events_actual):
        feats.append({
            "type": "Point",
            "coordinates": [round(float(ev_lons[i]), 6), round(float(ev_lats[i]), 6)],
            "properties": {"event_date": str(dates[i]), "event_id": f"hist_{i:02d}"},
        })
    gpd.GeoDataFrame(
        {"event_date": list(dates),
         "event_id": [f"hist_{i:02d}" for i in range(n_events_actual)]},
        geometry=[Point(lon, lat) for lon, lat in zip(ev_lons, ev_lats)],
        crs="EPSG:4326",
    ).to_file(SAMPLE_DATA_DIR / "historical_landslides.geojson", driver="GeoJSON")

    print(f"Generated {N_VILLAGES} villages (with real Wayanad names), "
          f"slope/rainfall/soil, {n_events_actual} historical events "
          f"in {SAMPLE_DATA_DIR}")


if __name__ == "__main__":
    generate()
