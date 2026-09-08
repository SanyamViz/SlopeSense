# Landslide Early Warning System — Master Data Pack
_One consolidated file: every source, schema, script, and validated event in this project. Nothing summarized away — this is the full working reference for Antigravity._

---

## 1. Data Source Manifest (full)

| Dataset | Provider | Geography | Format | Coverage | Resolution | URL | Notes |
|---|---|---|---|---|---|---|---|
| NASA Global Landslide Catalog | NASA | Global | CSV | through 2025-05-29 export | event points | https://data.nasa.gov/docs/legacy/Global_Landslide_Catalog_Export/Global_Landslide_Catalog_Export_rows.csv | Official NASA CSV export |
| NASA COOLR | NASA GPM | Global | Web repository | Multiple inventories | event/report | https://gpm.nasa.gov/applications/landslides/coolr | Superset of GLC + citizen reports |
| Kerala GSI Susceptibility — TVM | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/TVM.zip | |
| Kerala GSI Susceptibility — Kollam | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Kollam.zip | |
| Kerala GSI Susceptibility — Pathanamthitta | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Pathanamthitta.zip | |
| Kerala GSI Susceptibility — Kottayam | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Kottayam.zip | |
| Kerala GSI Susceptibility — Idukki | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Idukki.zip | |
| Kerala GSI Susceptibility — Ernakulam | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Ernakulam.zip | |
| Kerala GSI Susceptibility — Thrissur | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Thrissur.zip | |
| Kerala GSI Susceptibility — Palakkad | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Palakkad.zip | |
| Kerala GSI Susceptibility — Malappuram | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Malappuram.zip | |
| Kerala GSI Susceptibility — Kozhikode | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Kozhikode.zip | |
| Kerala GSI Susceptibility — Wayanad | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Wayanad.zip | Priority district — matches validation case |
| Kerala GSI Susceptibility — Kannur | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Kannur.zip | |
| Kerala GSI Susceptibility — Kasaragod | Kerala SDMA/GSI | District | ZIP shapefile | 2022 | polygon class | https://sdma.kerala.gov.in/wp-content/uploads/2025/08/Kasaragod.zip | |
| Open-Meteo Historical Weather API | Open-Meteo | Global | JSON/CSV | 1940–present | hourly, ERA5-Land 0.1° | https://open-meteo.com/en/docs/historical-weather-api | No API key required |
| IMD 0.25° daily gridded rainfall | IMD | India | NetCDF | 1901–2024 | 0.25° daily | https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html | India-specific, official |
| OpenTopography Global DEM API | OpenTopography | Global | GeoTIFF | current | 30m SRTM GL1 | https://portal.opentopography.org/apidocs/ | **Requires free API key** |
| OpenTopography Developers | OpenTopography | Global | API docs | current | multiple DEMs | https://opentopography.org/developers | Get key here |
| Bhuvan LULC 1:50k | Bhuvan/NRSC | India | WMS/WMTS | 2005–2016 | 1:50,000 | https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore2.php | WMS: https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms |
| Bhuvan LULC 1:250k | Bhuvan/NRSC | India | WMS | 2004–2023 | 1:250,000 | https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore2.php | WMS: https://bhuvan-ras2.nrsc.gov.in/cgi-bin/LULC250K.exe |
| Bhuvan SIS-DP Phase 2 | Bhuvan/NRSC | India | WMS | 2018–2023 | 1:10,000 | https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore2.php | Finer district-scale LULC |
| USGS NLCD 2021 | USGS | USA only | GeoTIFF | 2021 | 30m | — | **Do not use for Kerala** |
| USGS EarthExplorer | USGS | Global | Web download | current | AOI-based | https://earthexplorer.usgs.gov/ | Login required |

---

## 2. Target Model Schema

| Field | Source | Type | Description |
|---|---|---|---|
| record_id | NASA GLC / COOLR | string | Unique event identifier |
| event_date | NASA GLC / COOLR | date | Reported/event date |
| latitude | NASA GLC / COOLR | float | Event latitude |
| longitude | NASA GLC / COOLR | float | Event longitude |
| landslide_label | derived | binary | 1 = landslide, 0 = negative/control sample |
| rain_1d_mm | Open-Meteo or IMD | float | Rainfall, 24h window |
| rain_3d_mm | Open-Meteo or IMD | float | 3-day antecedent rainfall |
| rain_7d_mm | Open-Meteo or IMD | float | 7-day antecedent rainfall |
| rain_30d_mm | Open-Meteo or IMD | float | 30-day antecedent rainfall |
| elevation_m | OpenTopography/SRTM | float | DEM elevation |
| slope_deg | derived from DEM | float | Slope in degrees |
| aspect_deg | derived from DEM | float | Aspect in degrees |
| curvature | derived from DEM | float | Terrain curvature |
| susceptibility_class | GSI 2022 | float/int | Low/moderate/high class |
| lulc_class | Bhuvan | float/int | Land-use/land-cover class |
| vegetation_proxy | Bhuvan/derived | float | Forest/vegetation indicator |

**Modeling notes:** Use Random Forest / XGBoost for a hackathon-feasible first model. Generate negative samples from nearby points/comparable rainfall windows with no reported event. Use spatial or temporal holdout for train/test — never split neighboring pixels randomly (leakage).

---

## 3. Wayanad 2024 — Validated Ground-Truth Event (use for demo validation, NOT training)

**Location:** Mundakkai-Chooralmala, Wayanad, Kerala (11.5167° N, 76.1333° E) | **Date:** July 30, 2024

### Terrain deltas
| Metric | Pre-event | Post-event | Delta |
|---|---|---|---|
| Initiation zone elevation (Punchirimattam Scarp) | 1,571 m | 1,564 m | −7.08 m depletion depth |
| Deposition base elevation (Chooralmala Valley) | 803 m | 818 m | +15 m debris deposit |
| Runout distance & drop | — | 8.0 km travel, 768 m vertical descent | — |
| Flow corridor width | 30–50 m (original channel) | 100–275 m (scoured) | +225 m widening |

### Rainfall / soil moisture escalation (use this to validate your alert thresholds)
| Period | Rainfall | Anomaly vs. normal | Soil moisture | Alert status |
|---|---|---|---|---|
| Jul 15–27, 2024 | 168.0 mm | 110% | 72% | MONSOON BASELINE |
| Jul 28, 2024 (24h) | 204.5 mm | 280% | 88% | ADVISORY |
| Jul 29, 2024 (24h) | 372.6 mm | 493% | 98% | CRITICAL THRESHOLD |
| Jul 30, 00:00–04:30 | 573.1 mm (48h total) | Extreme deluge | 100% (pore pressure peak) | DUAL FAILURE (02:17 & 04:10) |

### Event JSON (embedded, ready to use)
```json
{
  "event_id": "ISRO_NRSC_2024_WAYANAD_001",
  "data_sources": {
    "dem": "ISRO NRSC Cartosat-3 & ESA Sentinel-1 D-InSAR",
    "hydro": "IMD Daily Weather Briefing & NASA SMAP SPL3SMP_E",
    "geotechnical": "Geological Survey of India (GSI) Field Assessment"
  },
  "coordinates": { "latitude": 11.5167, "longitude": 76.1333 },
  "metrics": {
    "elevation_drop_m": 768.0,
    "runout_distance_km": 8.0,
    "48_hr_antecedent_rain_mm": 573.1,
    "soil_saturation_index": 1.0
  },
  "blocked_infrastructure": [
    { "name": "Chooralmala Bridge", "status": "Washed away entirely at 04:10 AM IST" },
    { "name": "Meppadi-Chooralmala Road", "status": "Blocked by 15m debris flow" }
  ]
}
```

### Medical/response infrastructure (for your ACT-stage demo)
| Facility | Role | Status | Distance/Corridor |
|---|---|---|---|
| Wayanad District Hospital (Mananthavady) | District Tertiary Referral | OPERATIONAL | 38.5 km (SH 59) |
| Meppadi PHC | Local Triage/First Response | OPERATIONAL | 12.2 km (Chooralmala-Meppadi Rd) |
| Kozhikode Govt. Medical College | Level-1 Regional Trauma | OPERATIONAL | 73.0 km (Thamarassery Ghat) |
| Mundakkai/Chooralmala Dispensaries | Local Primary Health | **SEVERED/DESTROYED** | 0.0 km (bridge collapsed) |

---

## 4. Working Scripts (full, embedded)

### 4a. `fetch_open_meteo_for_events.py` — rainfall enrichment (no API key needed)
```python
"""Fetch historical precipitation for event coordinates from a landslide CSV.
Usage: python fetch_open_meteo_for_events.py input.csv output.csv
Expected columns: latitude, longitude, event_date
"""
import sys, time
from datetime import datetime, timedelta
import csv
import requests

if len(sys.argv) != 3:
    raise SystemExit("Usage: python fetch_open_meteo_for_events.py input.csv output.csv")

src, dst = sys.argv[1:]

def pick(row, names):
    lower = {k.lower().strip(): v for k, v in row.items()}
    for n in names:
        if n in lower and lower[n] not in (None, ""):
            return lower[n]
    return None

with open(src, newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

out = []
s = requests.Session()
for i, row in enumerate(rows, 1):
    lat = pick(row, ["latitude", "lat"])
    lon = pick(row, ["longitude", "lon", "lng"])
    date = pick(row, ["event_date", "date", "eventdate"])
    rec = dict(row)
    if not lat or not lon or not date:
        rec.update({"rain_1d_mm":"", "rain_3d_mm":"", "rain_7d_mm":"", "rain_30d_mm":"", "rain_status":"missing_coordinate_or_date"})
        out.append(rec); continue
    try:
        d = datetime.strptime(date[:10], "%Y-%m-%d").date()
    except ValueError:
        rec.update({"rain_1d_mm":"", "rain_3d_mm":"", "rain_7d_mm":"", "rain_30d_mm":"", "rain_status":"bad_date"})
        out.append(rec); continue
    start = d - timedelta(days=30)
    params = {
        "latitude": float(lat), "longitude": float(lon),
        "start_date": start.isoformat(), "end_date": d.isoformat(),
        "hourly": "precipitation", "timezone": "UTC"
    }
    try:
        r = s.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        vals = data.get("hourly", {}).get("precipitation", [])
        times = data.get("hourly", {}).get("time", [])
        daily = {}
        for t, v in zip(times, vals):
            day = t[:10]
            daily[day] = daily.get(day, 0.0) + float(v or 0.0)
        def agg(n):
            return sum(daily.get((d - timedelta(days=j)).isoformat(), 0.0) for j in range(n))
        rec.update({"rain_1d_mm": round(agg(1), 2), "rain_3d_mm": round(agg(3), 2), "rain_7d_mm": round(agg(7), 2), "rain_30d_mm": round(agg(30), 2), "rain_status":"ok"})
    except Exception as e:
        rec.update({"rain_1d_mm":"", "rain_3d_mm":"", "rain_7d_mm":"", "rain_30d_mm":"", "rain_status":f"error:{type(e).__name__}"})
    out.append(rec)
    if i < len(rows):
        time.sleep(0.1)

with open(dst, 'w', newline='', encoding='utf-8') as f:
    fields = list(out[0].keys()) if out else []
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(out)
print(f"Wrote {len(out)} rows to {dst}")
```

### 4b. `download_kerala_gsi.py` — 13 Kerala district susceptibility ZIPs
```python
"""Download the 13 Kerala district GSI 2022 landslide-susceptibility ZIPs."""
from pathlib import Path
import requests

BASE = "https://sdma.kerala.gov.in/wp-content/uploads/2025/08/"
NAMES = [
    "TVM","Kollam","Pathanamthitta","Kottayam","Idukki","Ernakulam",
    "Thrissur","Palakkad","Malappuram","Kozhikode","Wayanad","Kannur","Kasaragod"
]
outdir = Path("kerala_gsi_2022")
outdir.mkdir(exist_ok=True)
for name in NAMES:
    url = BASE + name + ".zip"
    target = outdir / (name + ".zip")
    print("Downloading", url)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    target.write_bytes(r.content)
    print(target, target.stat().st_size, "bytes")
print("Done")
```

### 4c. `opentopography_srtm_template.py` — Kerala DEM (needs free API key)
```python
"""Template for downloading a Kerala DEM from OpenTopography.
Set OPENTOPO_API_KEY in your environment before running.
Get a free key: https://opentopography.org/developers
"""
import os, requests

key = os.environ.get("OPENTOPO_API_KEY")
if not key:
    raise SystemExit("Set OPENTOPO_API_KEY first. Get a free key from https://opentopography.org/developers")

# Kerala approximate bounding box: west, south, east, north
params = {
    "demtype": "SRTMGL1",
    "south": 8.25, "north": 12.80,
    "west": 74.80, "east": 77.40,
    "outputFormat": "GTiff",
    "API_Key": key,
}
r = requests.get("https://portal.opentopography.org/API/globaldem", params=params, timeout=180)
r.raise_for_status()
open("kerala_srtm_30m.tif", "wb").write(r.content)
print("Wrote kerala_srtm_30m.tif")
```

### 4d. Bhuvan LULC endpoints (reference — no script needed, request AOI-clipped tiles)
```
Bhuvan catalog: https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore2.php
1:50,000 WMS:   https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms
1:50,000 WMTS:  https://bhuvan-vec2.nrsc.gov.in/bhuvan/gwc/service/wmts
1:250,000 WMS:  https://bhuvan-ras2.nrsc.gov.in/cgi-bin/LULC250K.exe
```

---

## 5. What is NOT executable from this file alone (needs live network access)

Everything above is complete and self-contained *except the actual binary/large downloads*, which require live internet access this document can't perform on its own:

- The real NASA GLC event CSV (~thousands of rows) — not embedded here, must be fetched
- 13 Kerala GSI shapefile ZIPs — must be fetched
- Kerala SRTM DEM GeoTIFF — must be fetched (needs API key)
- Bhuvan LULC raster tiles — must be fetched
- A negative-sample (label=0) generator — does not exist yet in any file, must be written
