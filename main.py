"""FastAPI backend serving the landslide risk JSON produced by the pipeline.

Endpoints:
  GET /              -> index of available endpoints
  GET /risk-map      -> full risk document (metadata + summary + all locations)
  GET /risk/{id}     -> single location with factors + alert (404 if unknown)
  GET /alerts/active -> locations at/above a risk threshold, sorted by severity

CORS is enabled for all origins (hackathon demo, no auth).

HACKATHON NOTE: data is loaded from the JSON file the pipeline writes
(config.output). The backend does NOT recompute scores -- it is a thin,
cacheable read layer. Use GET /reload to pick up a freshly-generated file.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import CONFIG
from scoring import score_single_location
from graph_analysis import compute_impact_assessment

logger = logging.getLogger("backend")
OUTPUT_PATH = Path(CONFIG["output"])

# Level -> minimum inclusive score, derived from configurable thresholds so the
# active-alert endpoint stays in sync with config (no magic numbers).
LEVEL_MIN_SCORE = {lvl: bounds[0] for lvl, bounds in CONFIG["risk_thresholds"].items()}


def load_document() -> dict:
    """Read the pipeline's output JSON from disk. Auto-generates if missing."""
    if not OUTPUT_PATH.exists():
        logger.info("%s missing -- running pipeline to generate it.", OUTPUT_PATH)
        import pipeline
        pipeline.main(scorer=None)
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        return json.load(f)


app = FastAPI(
    title="Landslide Risk API",
    version=CONFIG["model_version"],
    description="Read-only risk layer over village-level landslide scores.",
)

# CORS: open for local frontend dev (hackathon build, no auth).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warm_cache():
    """Pre-load the risk document at startup so the first request is fast."""
    global _DOC
    _DOC = load_document()


_DOC: dict = load_document()


@app.get("/reload", tags=["admin"])
def reload_data():
    """Re-read the output JSON from disk (call after re-running the pipeline)."""
    global _DOC
    _DOC = load_document()
    return {"reloaded": True, "total_locations": _DOC["metadata"]["total_locations"]}


@app.get("/", tags=["info"])
def index():
    return {
        "service": "Landslide Risk API",
        "endpoints": {
            "risk-map": "GET /risk-map -- full risk document",
            "risk-by-id": "GET /risk/{location_id} -- per-location breakdown + alert",
            "alerts": "GET /alerts/active -- locations >= threshold, sorted by severity",
            "reload": "GET /reload -- reload output JSON",
            "infrastructure": "GET /infrastructure -- graph + stranded zones",
            "impact-assessment": "GET /impact-assessment -- hospitals nearby, capacity, alternative routes",
            "docs": "GET /docs -- interactive Swagger UI",
        },
    }


@app.get("/risk-map", tags=["risk"])
def risk_map() -> dict:
    """Return risk data for ALL locations (full schema document)."""
    return _DOC


@app.get("/risk/{location_id}", tags=["risk"])
def risk_by_id(location_id: str):
    """Return detailed factor breakdown + alert text for one location."""
    for loc in _DOC["locations"]:
        if loc["location_id"] == location_id:
            return loc
    raise HTTPException(status_code=404, detail=f"location_id '{location_id}' not found")


@app.get("/infrastructure", tags=["risk"])
def infrastructure():
    """Return the infrastructure graph, edges, and stranded-zone analysis."""
    infra = _DOC.get("infrastructure")
    if infra is None:
        raise HTTPException(status_code=404, detail="No infrastructure data in current document")
    return infra


@app.get("/impact-assessment", tags=["risk"])
def impact_assessment(radius_km: float = Query(default=20.0, ge=1.0, le=200.0, description="Search radius in km for nearby hospitals/safe places.")):
    """Return per-zone hospital proximity, available capacity, and alternative routes.

    For each location, returns:
      - nearby hospitals/safe places within ``radius_km`` with capacity info
      - nearby_hospital_count
      - total_available_capacity_nearby
      - alternative evacuation routes if the zone is high/severe and primary roads are blocked
    """
    infra = _DOC.get("infrastructure")
    if infra is None:
        raise HTTPException(status_code=404, detail="No infrastructure data in current document")
    edges = infra.get("edges", [])
    nodes = infra.get("nodes", [])
    result = compute_impact_assessment(
        edges=edges,
        scored_locations=_DOC.get("locations", []),
        nodes=nodes,
        hospital_radius_km=radius_km,
    )
    return result


@app.get("/alerts/active", tags=["risk"])
def active_alerts(
    min_level: Optional[str] = Query(
        default="high",
        description="Minimum risk level to include (low/moderate/high/severe). "
                    "Ignored if min_score is also provided.",
    ),
    min_score: Optional[float] = Query(
        default=None, ge=0, le=100, description="Explicit minimum risk_score (overrides min_level)."
    ),
):
    """Locations at/above a risk threshold, sorted by severity (score desc).

    Default returns high + severe. Pass min_level=severe or min_score=76 to narrow.
    """
    if min_score is None:
        min_score = float(LEVEL_MIN_SCORE.get(min_level, LEVEL_MIN_SCORE["high"]))

    locs = [l for l in _DOC["locations"] if l["risk_score"] >= min_score]
    locs.sort(key=lambda l: l["risk_score"], reverse=True)
    return {
        "threshold": min_score,
        "min_level": min_level,
        "count": len(locs),
        "locations": locs,
    }


class SimulateRequest(BaseModel):
    location_id: str
    overrides: dict = {}


@app.post("/simulate", tags=["risk"])
def simulate(request: SimulateRequest):
    """What-if scoring: re-score a location against slider-adjusted inputs.

    Body:
        { location_id: str, overrides: { factor: value, ... } }

    Only the factors provided in ``overrides`` are changed; everything else
    stays at the location's current values.  The result is stateless and is
    **never** persisted back to ``landslide_risk_output.json``.
    """
    location_id = request.location_id
    overrides = {k: float(v) for k, v in request.overrides.items()}

    loc = None
    for l in _DOC["locations"]:
        if l["location_id"] == location_id:
            loc = l
            break

    if loc is None:
        raise HTTPException(status_code=404, detail=f"location_id '{location_id}' not found")

    factor_map = {}
    rainfall_7d = None
    for f in loc.get("factors", []):
        if f["factor"] == "rainfall_intensity":
            factor_map["rainfall_24h"] = f["raw_value"]
            rainfall_7d = f.get("raw_value_7d")
        elif f["factor"] == "slope_angle":
            factor_map["slope_angle"] = f["raw_value"]
        elif f["factor"] == "soil_saturation":
            factor_map["soil_saturation"] = f["raw_value"]
        elif f["factor"] == "historical_proximity":
            factor_map["proximity_to_event_km"] = f["raw_value"]

    raw_factors = {
        "location_id": location_id,
        "slope_angle": factor_map.get("slope_angle", 0.0),
        "rainfall_24h": factor_map.get("rainfall_24h", 0.0),
        "rainfall_7d": rainfall_7d if rainfall_7d is not None else 0.0,
        "soil_saturation": factor_map.get("soil_saturation", 0.0),
        "proximity_to_event_km": factor_map.get("proximity_to_event_km", 0.0),
    }

    for key, value in overrides.items():
        if key in raw_factors:
            raw_factors[key] = value

    original_score = loc["risk_score"]
    result = score_single_location(raw_factors, CONFIG)

    return {
        "location_id": location_id,
        "risk_score": result["risk_score"],
        "risk_level": result["risk_level"],
        "factors": result["factors"],
        "original_score": original_score,
        "original_level": loc["risk_level"],
        "delta_from_current": round(result["risk_score"] - original_score, 2),
    }


@app.get("/config", tags=["risk"])
def get_config():
    """Return tunable config values needed by the frontend (breakpoints, thresholds, weights)."""
    norm = {}
    for key, val in CONFIG["normalization"].items():
        norm[key] = {
            "breakpoints": val["breakpoints"],
            "unit": val.get("unit", ""),
        }
        if "cumulative_threshold_mm" in val:
            norm[key]["cumulative_threshold_mm"] = val["cumulative_threshold_mm"]

    return {
        "weights": CONFIG["weights"],
        "risk_thresholds": CONFIG["risk_thresholds"],
        "normalization": norm,
    }
