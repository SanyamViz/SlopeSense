"""Robust retry-downloader for the NASA GLC CSV.

Writes to a .part file and only swaps it into nasa_glc_raw.csv once the byte
count matches the server's Content-Length (so a partial file is never mistaken
for the full dataset). Retries on short reads / timeouts.
"""
import os
import sys
import requests

URL = "https://data.nasa.gov/docs/legacy/Global_Landslide_Catalog_Export/Global_Landslide_Catalog_Export_rows.csv"
OUT = "nasa_glc_raw.csv"
PART = OUT + ".part"
HEADERS = {"User-Agent": "landslide-pipeline/1.0 (hackathon)"}


def main(max_attempts=5):
    # Get expected length via a GET (some CDNs don't answer HEAD fully).
    with requests.get(URL, headers=HEADERS, timeout=60, stream=True) as r:
        r.raise_for_status()
        expected = int(r.headers.get("Content-Length", 0))
        print("Expected bytes:", expected, flush=True)
        best = 0
        for attempt in range(1, max_attempts + 1):
            try:
                with requests.get(URL, headers=HEADERS, timeout=120, stream=True) as resp:
                    resp.raise_for_status()
                    total = 0
                    with open(PART, "wb") as f:
                        for chunk in resp.iter_content(1 << 16):
                            if chunk:
                                f.write(chunk)
                                total += len(chunk)
                    print(f"Attempt {attempt}: wrote {total} bytes", flush=True)
                    if expected and total >= expected * 0.999:
                        os.replace(PART, OUT)
                        print("Complete ->", OUT, os.path.getsize(OUT), "bytes", flush=True)
                        return True
                    best = max(best, total)
            except Exception as e:
                print(f"Attempt {attempt} failed: {type(e).__name__}: {e}", flush=True)
        print(f"Best received: {best} / expected {expected}", flush=True)
    return False


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
