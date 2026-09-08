"""JSON export layer -- writes the exact schema requested by the pipeline spec.

HACKATHON NOTE: output is a single self-describing JSON document so the FastAPI
backend can just `json.load` it. All float rounding happens here so the rest of
the pipeline can keep full precision for logging.
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


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


def build_alert(risk_score, risk_level, factors, location_name="this location"):
    """Generate alert text from score + dominant contributing factor.

    ASSUMPTION: a hand-written rule set over the top factor is a reasonable
    hackathon substitute for a domain-alert taxonomy.
    """
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
    generated = generate_alert(risk_score, risk_level, factors, location_name)

    return {
        "message_en": en,
        "message_local": f"{generated['headline_hi']}\n\n{generated['explanation_hi']}",
        "recommended_action": action,
        "headline": generated["headline"],
        "headline_hi": generated["headline_hi"],
        "explanation": generated["explanation"],
        "explanation_hi": generated["explanation_hi"],
        "recommended_action_hi": generated["recommended_action_hi"],
        "top_factor": generated["top_factor"],
        "language": generated["language"],
    }


def export_results(cfg, locations, out_path, infrastructure=None):
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
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %d locations to %s", len(locations), out_path)
    return doc
