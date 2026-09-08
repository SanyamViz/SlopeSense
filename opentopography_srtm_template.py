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
