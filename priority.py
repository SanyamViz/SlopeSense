"""Priority scoring layer.

Combines raw hazard risk (0-100) with socio-economic vulnerability (0-1)
into a single response-priority score (0-100) using a transparent weighted
sum. Same auditable style as scoring.py -- no black boxes, no hidden
normalisation; every term and weight is a named config constant.

Formula (config.priority_weights, defaults risk=0.6 / vulnerability=0.4):
    priority = risk * w_risk + (vulnerability * 100) * w_vuln

The vulnerability term is scaled to the 0-100 risk range before blending so
both axes contribute on equal footing. The 0.6/0.4 split is a value
judgement (documented in config.py): physical hazard is the prerequisite for
any landslide impact, so it dominates, but vulnerability is a meaningful,
independent second axis -- a moderately hazardous village with many
vulnerable people can outrank a steep-but-empty one.
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)


def compute_priority_score(risk_score_0to100, vulnerability_score_0to1, cfg=None):
    """Weighted sum of risk and vulnerability -> 0-100 priority score.

    Args:
        risk_score_0to100: raw hazard risk score in [0, 100].
        vulnerability_score_0to1: composite vulnerability in [0, 1].
        cfg: config dict (defaults to module CONFIG); reads
             priority_weights["risk"] and ["vulnerability"].

    Returns:
        float priority score clamped to [0, 100].
    """
    from config import CONFIG
    cfg = cfg or CONFIG
    pw = cfg["priority_weights"]

    risk = float(np.clip(risk_score_0to100, 0.0, 100.0))
    vuln = float(np.clip(vulnerability_score_0to1, 0.0, 1.0))

    # Bring vulnerability onto the same 0-100 scale as risk before blending.
    priority = risk * pw["risk"] + (vuln * 100.0) * pw["vulnerability"]
    priority = float(np.clip(priority, 0.0, 100.0))

    logger.info("Priority: risk=%.2f vuln=%.4f -> priority=%.2f "
                "(w_risk=%.2f w_vuln=%.2f)",
                risk, vuln, priority, pw["risk"], pw["vulnerability"])
    return priority