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
