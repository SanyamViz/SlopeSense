# Landslide Risk Command Dashboard

A dark, control-room-style React dashboard that visualizes landslide risk on a
map. It consumes the FastAPI backend at `http://localhost:8000/risk-map`.

## Features

- **Map layer** — Leaflet + dark Stadia basemap, with a custom circle marker per
  location colour-coded by risk level (green / amber / orange / red).
- **Click a marker** — opens a side panel with the risk score, a bar chart of
  the contributing factors, and the alert message in English + local language.
- **Top banner** — live KPI tiles for each risk level plus a scrolling list of
  currently active High/Severe alerts, sorted by severity.
- **Search** — filter locations by name, district, or ID.
- **Dashboard aesthetic** — dark base theme, monospace data readouts, pulsing
  alert indicator, high-contrast risk palette.

## Swap mock → real API

All network access is in `src/api/riskClient.js`. The only tunable is
`VITE_API_BASE_URL`, which must be set in your deployment environment
(e.g. Vercel) to point at the backend URL:

```bash
# Vercel Dashboard → Settings → Environment Variables
VITE_API_BASE_URL=https://your-backend-url.example.com
```

For local development it defaults to `http://localhost:8000`.

Point it at the real API and nothing else changes — the component layer only
consumes the normalised shape returned by `/risk-map`.

## Run

```bash
# 1. Backend (already running on :8000)
cd .. && python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 2. Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173
# or
npm run build      # static site in dist/
```

## Layout

```
src/
  App.jsx                 top-level data fetch + layout
  api/riskClient.js       single network layer (swap point)
  constants/risk.js       risk levels, palette, severity, score→level
  components/
    TopBar.jsx            title + KPI tiles + search
    AlertBanner.jsx       active high/severe alerts, severity-sorted
    MapView.jsx           Leaflet map + custom markers
    SidePanel.jsx         score, factor bar chart, alert EN + LOCAL
  styles.css
```