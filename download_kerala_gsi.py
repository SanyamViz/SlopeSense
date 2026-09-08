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
