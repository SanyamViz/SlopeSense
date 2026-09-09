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
import os
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import CONFIG
from graph_analysis import compute_impact_assessment
from scoring import score_single_location

# Twilio REST client for SMS/WhatsApp alert dispatch. Credentials come from
# the environment (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) -- never hardcode.
# The client is created lazily so a missing credential does not break app import.
_twilio_client = None


def _get_twilio_client():
    global _twilio_client
    if _twilio_client is None:
        from twilio.rest import Client

        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if not account_sid or not auth_token:
            raise RuntimeError(
                "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID and "
                "TWILIO_AUTH_TOKEN environment variables."
            )
        _twilio_client = Client(account_sid, auth_token)
    return _twilio_client


def _split_recipients(raw: str) -> list:
    """Parse a comma-separated list of E.164 numbers, dropping blanks."""
    if not raw:
        return []
    return [n.strip() for n in raw.split(",") if n.strip()]


# --- Voice-call escalation threshold ---
# A zone triggers a Twilio Voice call when risk_level == "severe" AND its
# elderly_pct exceeds this value. Configurable via environment variable so
# the demo can be tuned without a code change. Default 25 (%).
_VOICE_CALL_ELDERLY_THRESHOLD = float(
    os.environ.get("VOICE_CALL_ELDERLY_THRESHOLD_PCT", "25")
)


def _build_voice_twiml(text_ml: str, text_en: str, location_id: str) -> str:
    """Build TwiML for a voice-call escalation to a severe+elderly zone.

    Uses <Say> with Malayalam (ml-IN, via a neural voice) as the primary
    language, followed by an English <Say> for bilingual coverage.  The
    alert text is reused verbatim from alert_generator.py (passed in as
    ``message_local`` / ``message_en``) -- no new copy is written here.

    If <Say> Malayalam pronunciation quality is insufficient in production,
    swap both <Say> blocks below for a single <Play> of a pre-recorded MP3:

    # TODO: drop the real bilingual Malayalam+English recording at:
    #   https://your-bucket.s3.ap-south-1.amazonaws.com/keraland/voice/<location_id>_alert.mp3
    # and replace the <Say> blocks above with:
    #   <Play>https://your-bucket.s3.ap-south-1.amazonaws.com/keraland/voice/<location_id>_alert.mp3</Play>
    """
    safe_ml = _xml_escape(text_ml or text_en or "")
    safe_en = _xml_escape(text_en or "")
    # loop="1" ensures the message is spoken exactly once (no repeat).
    return (
        f'<Response>'
        f'<Say language="ml-IN" voice="Polly.Raveena" loop="1">{safe_ml}</Say>'
        f'<Say language="en-US" voice="Polly.Joanna" loop="1">{safe_en}</Say>'
        f'</Response>'
    )


def dispatch_voice_call(
    location_id: str,
    message_local: str,
    message_en: str,
    to: str,
    from_number: str,
) -> dict:
    """Place a single Twilio Voice call and log the attempt.

    Returns a result dict matching the shape used by the SMS/WhatsApp
    dispatch results: { to, sid, status, success, error? }.
    """
    client = _get_twilio_client()
    twiml = _build_voice_twiml(message_local, message_en, location_id)
    ts = datetime.now(timezone.utc).isoformat()
    try:
        call = client.calls.create(twiml=twiml, to=to, from_=from_number)
        logger.info(
            "Voice call dispatched: zone_id=%s to=%s call_sid=%s status=%s timestamp=%s",
            location_id, to, call.sid, call.status, ts,
        )
        return {"to": to, "sid": call.sid, "status": call.status, "success": True}
    except Exception as exc:
        logger.warning(
            "Voice call failed: zone_id=%s to=%s error=%s timestamp=%s",
            location_id, to, str(exc), ts,
        )
        return {"to": to, "sid": None, "status": "error", "error": str(exc), "success": False}


logger = logging.getLogger("backend")
OUTPUT_PATH = Path(CONFIG["output"])
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

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

# CORS: explicitly allow the frontend dev server and a placeholder for
# production. Replace the placeholder with your real deployed frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://slope-sense.vercel.app",
    ],
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


@app.get("/api", tags=["info"])
def api_index():
    """API discovery index (kept at /api so the dashboard SPA can own /)."""
    return {
        "service": "Landslide Risk API",
        "endpoints": {
            "risk-map": "GET /risk-map -- full risk document",
            "risk-by-id": "GET /risk/{location_id} -- per-location breakdown + alert",
            "alerts": "GET /alerts/active -- locations >= threshold, sorted by severity",
            "reload": "GET /reload -- reload output JSON",
            "infrastructure": "GET /infrastructure -- graph + stranded zones",
            "impact-assessment": "GET /impact-assessment -- hospitals nearby, capacity, alternative routes",
            "dispatch": "POST /dispatch -- send SMS/WhatsApp alerts via Twilio; escalates to voice call for severe+elderly zones",
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
    min_level: str | None = Query(
        default="high",
        description="Minimum risk level to include (low/moderate/high/severe). "
                    "Ignored if min_score is also provided.",
    ),
    min_score: float | None = Query(
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


class DispatchRequest(BaseModel):
    sector: str
    location_id: str
    message_en: str
    message_local: str
    channel: str = "whatsapp"


@app.post("/dispatch", tags=["dispatch"])
def dispatch(request: DispatchRequest):
    """Send a real SMS/WhatsApp alert to every configured recipient via Twilio.

    Body:
        { sector, location_id, message_en, message_local, channel }

    channel is "whatsapp" or "sms". The WhatsApp sandbox requires a
    "whatsapp:" prefix on both the from and to numbers.

    Each recipient is attempted individually so a single bad number cannot
    abort the whole broadcast. Returns { sent, failed, results: [...] }.

    Voice-call escalation:
        When the location for ``location_id`` has risk_level == "severe" AND
        its vulnerability.elderly_pct exceeds VOICE_CALL_ELDERLY_THRESHOLD_PCT
        (default 25), a Twilio Voice call is also placed to every recipient.
        The call uses <Say> TwiML with the Malayalam alert text (message_local)
        and an English <Say> fallback.  Moderate / high / low zones are never
        escalated to voice.  Voice results appear under the "voice_calls" key
        in the response.
    """
    if request.channel not in ("whatsapp", "sms"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported channel '{request.channel}'. Use 'whatsapp' or 'sms'.",
        )

    client = _get_twilio_client()

    from_number = os.environ.get(
        "TWILIO_WHATSAPP_FROM" if request.channel == "whatsapp" else "TWILIO_SMS_FROM",
        "",
    )
    if not from_number:
        raise HTTPException(
            status_code=500,
            detail=f"Missing from-number env var for channel '{request.channel}'.",
        )

    recipients = _split_recipients(os.environ.get("DISPATCH_RECIPIENTS", ""))
    if not recipients:
        raise HTTPException(
            status_code=500,
            detail="DISPATCH_RECIPIENTS is empty. Configure comma-separated E.164 numbers.",
        )

    body = f"{request.message_local}\n\n{request.message_en}"
    results = []
    sent = 0
    failed = 0

    for to in recipients:
        try:
            if request.channel == "whatsapp":
                to_addr = f"whatsapp:{to}"
                from_addr = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
            else:
                to_addr = to
                from_addr = from_number

            message = client.messages.create(
                to=to_addr,
                from_=from_addr,
                body=body,
            )
            results.append({"to": to, "sid": message.sid, "status": message.status})
            sent += 1
        except Exception as exc:
            logger.warning("Dispatch to %s failed: %s", to, exc)
            results.append({"to": to, "sid": None, "status": "error", "error": str(exc)})
            failed += 1

    # --- Critical-only voice-call escalation ---
    # ONLY for zones that are severe-risk AND have an above-threshold elderly
    # population.  Moderate / high / low zones never trigger voice calls.
    # The threshold is configurable via VOICE_CALL_ELDERLY_THRESHOLD_PCT (default 25).
    voice_calls = []
    loc = next(
        (l for l in _DOC.get("locations", []) if l["location_id"] == request.location_id),
        None,
    )
    elderly_pct = (loc or {}).get("vulnerability", {}).get("elderly_pct", 0) if loc else 0
    if loc and loc.get("risk_level") == "severe" and elderly_pct > _VOICE_CALL_ELDERLY_THRESHOLD:
        voice_from = os.environ.get("TWILIO_SMS_FROM", "")
        if voice_from:
            for to in recipients:
                result = dispatch_voice_call(
                    request.location_id,
                    request.message_local,
                    request.message_en,
                    to,
                    voice_from,
                )
                voice_calls.append(result)
        else:
            logger.warning(
                "Voice call skipped for zone %s: TWILIO_SMS_FROM not set",
                request.location_id,
            )

    return {
        "sector": request.sector,
        "location_id": request.location_id,
        "channel": request.channel,
        "sent": sent,
        "failed": failed,
        "results": results,
        "voice_calls_issued": len(voice_calls),
        "voice_calls": voice_calls,
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


# ---------------------------------------------------------------------------
# Frontend dashboard (SPA).
#
# The combined Docker/Render build (Dockerfile) compiles the React app into
# frontend/dist/ inside the same image that runs uvicorn. Mounting that
# directory as static files here lets the deployed service serve the dashboard
# at the same origin as the JSON API, so the SPA's relative fetches to
# /risk-map etc. resolve without any cross-origin or VITE_API_BASE_URL config.
#
# The API routes above are registered first, so they keep taking precedence
# over the catch-all mount; any unmatched path falls through to the SPA's
# index.html (the Vite build emits a single index.html that loads main.jsx).
# ---------------------------------------------------------------------------
if FRONTEND_DIST.is_dir():
    # Mount the compiled bundle as static assets (CSS/JS/images) so the SPA
    # loads its real files instead of falling back to index.html for each one.
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST), html=False), name="frontend-static")
    logger.info("Mounted frontend dashboard assets from %s", FRONTEND_DIST)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _serve_spa(full_path: str):
        """Serve the SPA for any non-API path (client-side routing).

        Real files inside frontend/dist (assets, index.html, favicon, ...) are
        served directly so the browser can load the compiled bundle; everything
        else falls back to index.html so client-side React Router keeps working.
        API routes registered above take precedence because they are matched
        first by FastAPI's router.
        """
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            from fastapi.responses import FileResponse
            return FileResponse(str(candidate))
        return _FRONTEND_INDEX_RESPONSE
else:
    logger.warning(
        "Frontend dist directory not found at %s -- the dashboard will not be "
        "served. Build the frontend (npm run build) or run the Dockerfile.",
        FRONTEND_DIST,
    )


def _build_frontend_index_response():
    """Build the cached FileResponse for the SPA's index.html."""
    from fastapi.responses import FileResponse
    index_path = FRONTEND_DIST / "index.html"
    if index_path.is_file():
        return FileResponse(str(index_path), media_type="text/html; charset=utf-8")
    return None


_FRONTEND_INDEX_RESPONSE = _build_frontend_index_response()
