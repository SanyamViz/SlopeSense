"""Per-zone "alert trust score" derived from historical prediction accuracy.

A zone's trust score answers: "when this zone was flagged at a given risk
level in the past, how often was the observed outcome consistent with that
flag?" High accuracy -> high trust. Low accuracy -> low trust, which the
pipeline surfaces as a "consider secondary confirmation" nudge.

Band-matching rule (explicit, single source of truth):
  A prediction is "correct" when predicted_risk_level and actual_outcome fall
  in the same severity band. We use two bands:
    - LOW band   = {predicted: low | moderate}  <-> {actual: none | minor}
    - HIGH band  = {predicted: high | severe}   <-> {actual: moderate | severe}
  So e.g. a "high" prediction counts as correct if the actual outcome was
  "moderate" or "severe"; a "moderate" prediction counts as correct if the
  actual outcome was "none" or "minor".
"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import CONFIG, TRUST_LOW_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

# Threshold is stored as a fraction (0.6 == 60%) while accuracy_pct is a
# 0-100 percentage, so convert once here for an apples-to-apples comparison.
_LOW_CONFIDENCE_PCT = TRUST_LOW_CONFIDENCE_THRESHOLD * 100.0

# Predicted levels that belong to the LOW band (mild) vs HIGH band (elevated).
_LOW_PREDICTED = {"low", "moderate"}
_HIGH_PREDICTED = {"high", "severe"}

# Actual outcomes that belong to the LOW band vs HIGH band.
_LOW_ACTUAL = {"none", "minor"}
_HIGH_ACTUAL = {"moderate", "severe"}

CONFIDENCE_NOTE = "Consider secondary confirmation"


def _bands_match(predicted: str, actual: str) -> bool:
    """Return True when predicted and actual fall in the same severity band."""
    predicted_low = predicted in _LOW_PREDICTED
    actual_low = actual in _LOW_ACTUAL
    # Both in the low band, or both in the high band -> a match.
    return predicted_low == actual_low


def load_alert_history(path: Optional[Path] = None) -> List[dict]:
    """Read the alert-history CSV into a list of plain dicts.

    Missing/empty file -> empty list (caller decides how to handle zones with
    no history; trust_score() below treats 0 records as low confidence).
    """
    if path is None:
        path = CONFIG["inputs"]["alert_history"]
    path = Path(path)
    if not path.exists():
        logger.warning("Alert history not found at %s -- returning empty.", path)
        return []

    records = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "zone_id": (row.get("zone_id") or "").strip(),
                "date": (row.get("date") or "").strip(),
                "predicted_risk_level": (row.get("predicted_risk_level") or "").strip().lower(),
                "actual_outcome": (row.get("actual_outcome") or "").strip().lower(),
            })
    logger.info("Loaded %d alert-history records from %s", len(records), path)
    return records


def compute_trust_score(zone_id: str, history: List[dict]) -> dict:
    """Compute a zone's historical alert-accuracy trust score.

    Args:
        zone_id: Location id (e.g. "loc_000" or "WAYANAD_2024_VAL").
        history: Alert records for this zone (pre-filtered by caller, or the
            full list -- only records whose zone_id matches are used).

    Returns:
        {
            "accuracy_pct": float,        # 0-100, rounded to 1 dp; 0.0 if no records
            "correct_count": int,
            "total_count": int,
            "low_confidence": bool,       # accuracy_pct < TRUST_LOW_CONFIDENCE_THRESHOLD
        }
    """
    zone_id = (zone_id or "").strip()
    relevant = [r for r in history if (r.get("zone_id") or "").strip() == zone_id]

    total = len(relevant)
    if total == 0:
        return {
            "accuracy_pct": 0.0,
            "correct_count": 0,
            "total_count": 0,
            "low_confidence": True,
        }

    correct = sum(1 for r in relevant
                  if _bands_match(r["predicted_risk_level"], r["actual_outcome"]))
    accuracy_pct = round(100.0 * correct / total, 1)

    return {
        "accuracy_pct": accuracy_pct,
        "correct_count": correct,
        "total_count": total,
        "low_confidence": accuracy_pct < _LOW_CONFIDENCE_PCT,
    }


def build_trust_block(zone_id: str, history: List[dict]) -> dict:
    """Convenience wrapper returning the export-ready trust_score object.

    Adds the confidence_note field the export schema expects: the
    "Consider secondary confirmation" nudge when low_confidence is true, else
    None. accuracy_pct is rounded to an integer for compact UI display while
    the raw 1-dp value stays in accuracy_pct.
    """
    score = compute_trust_score(zone_id, history)
    return {
        "accuracy_pct": score["accuracy_pct"],
        "correct_count": score["correct_count"],
        "total_count": score["total_count"],
        "low_confidence": score["low_confidence"],
        "confidence_note": CONFIDENCE_NOTE if score["low_confidence"] else None,
    }