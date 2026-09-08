"""Robust one-shot download of the full NASA GLC catalog to nasa_glc_raw.csv.
Uses urllib buffered IO; atomic rename so a partial file never corrupts output.
"""
import os, tempfile, urllib.request

URL = "https://data.nasa.gov/docs/legacy/Global_Landslide_Catalog_Export/Global_Landslide_Catalog_Export_rows.csv"
OUT = "nasa_glc_raw.csv"


def main():
    tmp = OUT + ".part"
    req = urllib.request.Request(URL, headers={"User-Agent": "landslide-pipeline/1.0"})
    print("Starting download...", flush=True)
    with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        seen = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            seen += len(chunk)
            if total:
                print(f"\r{seen/1e6:.1f}MB / {total/1e6:.1f}MB", end="", flush=True)
        print(flush=True)
    os.replace(tmp, OUT)
    print("Saved", OUT, "size=", os.path.getsize(OUT))


if __name__ == "__main__":
    main()
