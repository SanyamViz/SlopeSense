# Landslide Risk Dashboard

A prototype early-warning system that scores village-level landslide risk across Kerala, India, using slope, rainfall, soil saturation, and historical proximity factors. The backend is a thin FastAPI read layer; the frontend is a React + Leaflet dashboard.

---

## Prerequisites

| Tool | Minimum version | Check command |
|------|----------------|---------------|
| Python | 3.10 | `python --version` |
| Node.js | 18.x | `node --version` |
| npm | 9.x | `npm --version` |

---

## 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

Key packages: `pandas`, `numpy`, `geopandas`, `shapely`, `fastapi`, `uvicorn`.

> **GeoPandas note:** on Windows you may need the pre-built wheel:
> `pip install geopandas --only-binary :all:`

---

## 2. Run the pipeline

The pipeline reads the input datasets in `sample_data/`, scores every village, classifies risk, builds bilingual alerts, and writes the output to `landslide_risk_output.json`.

```bash
python pipeline.py
```

Expected output:

```
INFO  Counts by risk level: {'low': ..., 'moderate': ..., 'high': ..., 'severe': ...}
INFO  Top risk locations: [...]
INFO  Total locations: 143
```

> **Validation case:** the pipeline injects a **Mundakkai–Chooralmala (Wayanad 2024)** ground-truth location on every run. This entry uses the real July 30 2024 event coordinates (11.5167°N, 76.1333°E) with documented rainfall (204.5 mm / 24 h, 573.1 mm / 7 d) and soil saturation (1.0).

> **Data freshness:** `metadata.data_freshness.rainfall_data_timestamp` is set dynamically to `datetime.now(timezone.utc).isoformat()` at each pipeline run. It is no longer a hardcoded value.

---

## 3. Start the FastAPI backend

The server reads `landslide_risk_output.json` and exposes the following endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /` | Index of available endpoints |
| `GET /risk-map` | Full risk document (all locations) |
| `GET /risk/{location_id}` | Single location detail + alert |
| `GET /alerts/active?min_level=high` | Locations at/above threshold |

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- Swagger UI: http://localhost:8000/docs
- Re-run `python pipeline.py` then call `GET /reload` to pick up fresh data without restarting the server.

---

## 4. Start the frontend dev server

The frontend is a Vite + React + Leaflet app in the `frontend/` directory.

```bash
cd frontend
npm install      # first time only
npm run dev
```

The dashboard will be available at **http://localhost:5173**.

> The Vite dev server proxies API requests to the FastAPI backend on port 8000.
> Ensure the backend is running before opening the dashboard.

---

## Quick-start (all steps)

```bash
# Terminal 1 — backend
pip install -r requirements.txt
python pipeline.py
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Project structure

```
├── config.py                      # Tunable weights, thresholds, paths
├── pipeline.py                    # Orchestrator (load → spatial → score → export)
├── export.py                      # JSON schema writer
├── alert_generator.py             # English + Hindi alert templates
├── scoring.py                     # Weighted risk scorer
├── classification.py              # Score → risk-level classifier
├── spatial.py                     # Nearest-neighbour spatial join
├── data_loader.py                 # CSV/GeoJSON reader
├── generate_sample_data.py        # Synthetic data generator (real Wayanad names)
├── main.py                        # FastAPI server (single source of truth)
├── landslide_risk_output.json     # Pipeline output (generated)
├── sample_data/
│   ├── villages.geojson           # Village points with real Kerala place names
│   ├── slope.csv
│   ├── rainfall.csv
│   ├── soil.csv
│   └── historical_landslides.geojson
├── frontend/
│   ├── src/                       # React components
│   ├── package.json
│   └── vite.config.js
└── landslide_master_data_pack.md  # Full data-source reference
```

---

## Notes

- Scoring weights and risk thresholds are in `config.py` — do **not** change them unless you understand the normalization curves.
- The `alert.message_local` field contains the Hindi-language headline and explanation (same as `alert.headline_hi` + `alert.explanation_hi`), populated at export time.
- The duplicate `backend/main.py` was removed; the canonical server entry point is `main.py` at the project root.
