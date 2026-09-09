"""JSON export layer -- writes the exact schema requested by the pipeline spec.

HACKATHON NOTE: output is a single self-describing JSON document so the FastAPI
backend can just `json.load` it. All float rounding happens here so the rest of
the pipeline can keep full precision for logging.
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Districts whose primary vernacular is Malayalam (Wayanad villages). Every
# other Kerala district defaults to Hindi for the alert vernacular.
_MALAYALAM_DISTRICTS = {"wayanad"}


def _district_language(district):
    """Resolve the vernacular alert language for a district.

    Wayanad -> Malayalam ("ml"); everything else -> Hindi ("hi").
    """
    if district and str(district).strip().lower() in _MALAYALAM_DISTRICTS:
        return "ml"
    return "hi"


def build_metadata(cfg):
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": cfg["model_version"],
        "weights_used": cfg["weights"],
        "risk_thresholds": {k: list(v) for k, v in cfg["risk_thresholds"].items()},
        "vulnerability_weights": cfg.get("vulnerability_weights"),
        "priority_weights": cfg.get("priority_weights"),
        "alert_thresholds": cfg.get("alert_thresholds", {}),
        "total_locations": 0,  # patched by caller
    }


def build_alert(risk_score, risk_level, factors, location_name="this location",
                district=None, language=None):
    """Generate alert text from score + dominant contributing factor.

    ASSUMPTION: a hand-written rule set over the top factor is a reasonable
    hackathon substitute for a domain-alert taxonomy.

    The vernacular ``language`` is resolved per district so Wayanad villages
    receive Malayalam (``ml``) while every other Kerala district defaults to
    Hindi (``hi``). Pass ``language`` explicitly to override the default.
    """
    if language is None:
        language = _district_language(district)

    dominant = max(factors, key=lambda f: f["contribution"])
    f = dominant["factor"]

    if risk_level == "severe":
        en = (f"Severe landslide risk (score {risk_score:.1f}). Multiple hazards align "
              f"on {f.replace('_', ' ')}.")
        action = ("Impose movement restrictions on steep slopes; activate "
                  "early-warning sirens; prepare evacuation of at-risk settlements.")
    elif risk_level == "high":
        en = (f"High landslide risk (score {risk_score:.1f}). Primary driver: "
              f"{f.replace('_', ' ')}.")
        action = ("Avoid steep slopes; monitor for cracks or unusual water flow; "
                  "issue public advisory within 24h.")
    elif risk_level == "moderate":
        en = (f"Moderate landslide risk (score {risk_score:.1f}). Watch "
              f"{f.replace('_', ' ')} for increasing trend.")
        action = ("Keep monitoring; clear surface drainage; advise caution on trails.")
    else:
        en = f"Low landslide risk (score {risk_score:.1f}). Current conditions stable."
        action = "Routine monitoring; no immediate restrictions."

    # Delegate to the template-based alert generator for richer structured output.
    from alert_generator import generate_alert
    generated = generate_alert(
        risk_score, risk_level, factors, location_name, language=language
    )

    headline_hi = generated["headline_hi"]
    explanation_hi = generated["explanation_hi"]
    action_hi = generated["recommended_action_hi"]
    if language == "ml":
        headline_local = generated["headline_ml"]
        explanation_local = generated["explanation_ml"]
        action_local = generated["recommended_action_ml"]
    else:
        headline_local = headline_hi
        explanation_local = explanation_hi
        action_local = action_hi

    return {
        "message_en": en,
        "message_local": f"{headline_local}\n\n{explanation_local}",
        "recommended_action": action,
        "headline": generated["headline"],
        "headline_hi": generated["headline_hi"],
        "headline_ml": generated["headline_ml"],
        "explanation": generated["explanation"],
        "explanation_hi": generated["explanation_hi"],
        "explanation_ml": generated["explanation_ml"],
        "recommended_action_hi": generated["recommended_action_hi"],
        "recommended_action_ml": generated["recommended_action_ml"],
        "top_factor": generated["top_factor"],
        "language": generated["language"],
    }


def export_results(cfg, locations, out_path, infrastructure=None, impact_assessment=None):
    """Write the final risk JSON document to `out_path`."""
    # Summary
    counts = {"low": 0, "moderate": 0, "high": 0, "severe": 0}
    low_confidence_count = 0
    for loc in locations:
        counts[loc["risk_level"]] = counts.get(loc["risk_level"], 0) + 1
        trust = loc.get("trust_score") or {}
        if trust.get("low_confidence"):
            low_confidence_count += 1

    # Top by raw hazard risk.
    top_risk = sorted(locations, key=lambda l: l["risk_score"], reverse=True)[:3]
    # Top by response priority (risk blended with vulnerability). Falls back to
    # 0 for any location missing a priority_score (e.g. partial vulnerability data).
    top_priority = sorted(locations, key=lambda l: l.get("priority_score") or 0.0,
                          reverse=True)[:3]

    summary = {
        "counts_by_risk_level": counts,
        "top_risk_locations": [l["location_id"] for l in top_risk],
        "top_priority_locations": [l["location_id"] for l in top_priority],
        "low_confidence_locations": low_confidence_count,
    }

    metadata = build_metadata(cfg)
    metadata["total_locations"] = len(locations)

    doc = {"metadata": metadata, "summary": summary, "locations": locations}
    if infrastructure is not None:
        doc["infrastructure"] = infrastructure
    if impact_assessment is not None:
        doc["impact_assessment"] = impact_assessment
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %d locations to %s", len(locations), out_path)
    return doc
