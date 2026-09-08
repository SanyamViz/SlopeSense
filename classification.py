"""Risk classification layer.

Maps a 0-100 score onto categorical risk levels using configurable thresholds.
HACKATHON NOTE: thresholds are flat boundaries; a real model would use
class-conditional probability calibration.
"""
import logging

logger = logging.getLogger(__name__)


def classify(score: float, thresholds: dict) -> str:
    """Return the risk-level label that owns the score.

    Handles gaps between bands gracefully (e.g. 25->26) by falling back to the
    highest lower-bound that is <= score. Bands are treated as inclusive.
    """
    score = float(score)
    # Order bands by their lower bound ascending.
    ordered = sorted(thresholds.items(), key=lambda kv: kv[1][0])
    for level, (lo, hi) in ordered:
        if lo <= score <= hi:
            return level
    # Fallback for scores landing in a gap (e.g. 25.5 between 25 and 26).
    for level, (lo, hi) in reversed(ordered):
        if lo <= score:
            return level
    return ordered[-1][0]
