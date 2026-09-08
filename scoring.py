"""Scoring layer -- the swappable core of the pipeline.

A `Scorer` exposes a single `score(row)` method that returns a risk score
(0-100) and a list of per-factor contribution dicts. The default implementation
is a transparent weighted sum. To swap in an ML model, implement the same
`Scorer` protocol and pass it to `run_pipeline` -- nothing else changes.

HACKATHTHACKATHON NOTE: factor contributions are rounded for the output JSON;
the underlying float is kept for logging so the score is fully auditable.
"""
import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class Scorer(Protocol):
    """Interface every scoring implementation must satisfy."""
    def score(self, row) -> tuple[float, list[dict]]:
        ...


class WeightedScorer:
    """Transparent weighted-sum scorer driven by config constants.

    risk_score = 100 * sum( normalized_i * weight_i )
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.weights = cfg["weights"]
        self.norm = cfg["normalization"]
        # Sanity: weights should sum to 1.0 (allow tiny float slack).
        total = sum(self.weights.values())
        if not np.isclose(total, 1.0, atol=1e-6):
            logger.warning("Weights sum to %.4f, expected 1.0; results still computed", total)

    def score(self, row) -> tuple[float, list[dict]]:
        factors = []
        total = 0.0
        for factor in ["slope_angle", "rainfall_intensity", "soil_saturation", "historical_proximity"]:
            entry = self._score_factor(factor, row)
            total += entry["contribution"] / 100.0 * entry["weight"]  # noop, kept for clarity
            factors.append(entry)

        # contribution already = normalized * weight * 100, so just sum.
        risk_score = sum(f["contribution"] for f in factors)
        risk_score = float(np.clip(risk_score, 0.0, 100.0))
        logger.info("Scored %s: score=%.2f / factors=%s",
                    row.get("location_id", "?"), risk_score,
                    [(f["factor"], f["raw_value"], f["normalized_value"], f["contribution"])
                     for f in factors])
        return risk_score, factors

    def _score_factor(self, factor: str, row) -> dict:
        weight = self.weights[factor]
        cfg = self.norm[factor]
        unit = cfg["unit"]
        if factor == "slope_angle":
            raw = float(row["slope_angle"])
            norm = self._norm(factor, raw)
            note = self._slope_note(raw, cfg)
        elif factor == "rainfall_intensity":
            raw, norm, note, raw_7d = self._rainfall(row)
        elif factor == "soil_saturation":
            raw = float(row["soil_saturation"])
            norm = self._norm(factor, raw)
            note = self._soil_note(row, raw)
        elif factor == "historical_proximity":
            raw = float(row["proximity_to_event_km"])
            norm = self._norm(factor, raw)
            note = self._history_note(row)
        else:
            raise ValueError(f"Unknown factor: {factor}")

        contribution = round(norm * weight * 100, 2)
        entry = {
            "factor": factor,
            "raw_value": round(raw, 4),
            "unit": unit,
            "normalized_value": round(float(norm), 4),
            "weight": weight,
            "contribution": contribution,
            "note": note,
        }
        # Expose the 7-day cumulative raw value alongside the 24h figure so
        # alert copy can quote it (rainfall raw_value is the 24h total by design).
        if factor == "rainfall_intensity":
            entry["raw_value_7d"] = round(float(raw_7d), 4)
        return entry

    # --- factor-specific helpers ---
    def _norm(self, factor, raw):
        from normalization import normalize_value
        return normalize_value(raw, self.norm[factor]["breakpoints"])

    def _rainfall(self, row):
        from normalization import normalize_rainfall
        return normalize_rainfall(row, self.cfg)

    def _slope_note(self, raw, cfg):
        critical = cfg.get("notes", {}).get("critical", 35.0)
        # ASSUMPTION: critical threshold is a single hardcoded cutoff, not a
        # terrain-class-specific failure envelope.
        if raw >= critical:
            return f"Above critical slope threshold (>{critical} deg)"
        if raw >= 30:
            return "Steep slope, elevated driving stress"
        if raw >= 15:
            return "Moderate slope"
        return "Gentle slope, low gravitational stress"

    def _soil_note(self, row, raw):
        soil_type = str(row.get("soil_type", "unknown"))
        drainage = str(row.get("drainage_class", "unknown"))
        # ASSUMPTION: clay-like texture + poor drainage = low infiltration is
        # encoded with rule-of-thumb text rather than measured hydraulic params.
        if raw >= 0.7:
            return f"Highly saturated {soil_type} soil, {drainage} drainage capacity"
        if raw >= 0.5:
            return f"{soil_type} soil nearing field capacity ({drainage} drainage)"
        return f"{soil_type} soil, {drainage} drainage, moisture within normal bounds"

    def _history_note(self, row):
        count = int(row.get("historical_events_5km", 0))
        if count >= 3:
            return f"{count} historical events within 5km since 2015"
        if count >= 1:
            return f"{count} historical event(s) within 5km since 2015"
        return "No recent historical events within 5km"


def score_single_location(raw_factors: dict, cfg: dict) -> dict:
    """Standalone scoring entry point for /simulate and other non-pipeline callers.

    Accepts the minimal set of raw physical factors required by the scoring
    layer and returns the same schema as ``WeightedScorer.score`` plus the
    classified risk level.  No duplicated logic -- this is a thin wrapper
    around the exact same ``WeightedScorer`` and ``classify`` calls used by
    the full pipeline.

    Args:
        raw_factors: dict with at least these keys:
            slope_angle (float): slope in degrees.
            rainfall_24h (float): recent 24-hour rainfall in mm.
            rainfall_7d (float): 7-day cumulative rainfall in mm.
            soil_saturation (float): fraction saturated, 0-1.
            proximity_to_event_km (float): km to nearest historical event.
        cfg: config dict (typically ``config.CONFIG``).

    Returns:
        dict with keys:
            risk_score (float, 0-100),
            risk_level (str),
            factors (list[dict]) -- per-factor breakdown.
    """
    from classification import classify

    scorer = WeightedScorer(cfg)

    row = {
        "location_id": raw_factors.get("location_id", "unknown"),
        "slope_angle": float(raw_factors["slope_angle"]),
        "rainfall_24h": float(raw_factors["rainfall_24h"]),
        "rainfall_7d": float(raw_factors.get("rainfall_7d", 0.0)),
        "soil_saturation": float(raw_factors["soil_saturation"]),
        "proximity_to_event_km": float(raw_factors["proximity_to_event_km"]),
        "soil_type": raw_factors.get("soil_type", "unknown"),
        "drainage_class": raw_factors.get("drainage_class", "unknown"),
        "historical_events_5km": int(raw_factors.get("historical_events_5km", 0)),
    }

    risk_score, factors = scorer.score(row)
    risk_level = classify(risk_score, cfg["risk_thresholds"])

    return {
        "risk_score": round(float(risk_score), 2),
        "risk_level": risk_level,
        "factors": factors,
    }
