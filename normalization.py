"""Normalization layer.

Converts each raw physical factor into a dimensionless [0,1] hazard fraction
using configurable piecewise-linear breakpoints defined in config.CONFIG.

HACKATHON NOTE: breakpoints are expert judgement, not statistically fitted.
The curve shape (sigmoid-like ramp) is a prototype substitute for a proper
hazard function derived from landslide inventory statistics.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def normalize_value(raw_value, breakpoints):
    """Linearly interpolate raw_value across breakpoints -> [0,1] clamped."""
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)) or pd.isna(raw_value):
        return 0.0
    xs = [p[0] for p in breakpoints]
    ys = [p[1] for p in breakpoints]
    norm = float(np.interp(raw_value, xs, ys))  # np.interp clamps to endpoint values
    return float(np.clip(norm, 0.0, 1.0))


def normalize_rainfall(row, norm_cfg):
    """Composite rainfall normalisation.

    ASSUMPTION: recent 24h rainfall is the primary driver; the 7-day cumulative
    amount is blended in as a secondary stressor with a soft additive bump when
    it exceeds its configured threshold. Reported raw_value stays the 24h figure
    so the output is physically interpretable; the 7-day cumulative is exposed
    separately as ``raw_value_7d`` so alert copy can quote it verbatim.
    """
    recent = float(row.get("rainfall_24h", 0.0) or 0.0)
    cumulative = float(row.get("rainfall_7d", 0.0) or 0.0)
    bp = norm_cfg["normalization"]["rainfall_intensity"]
    base = normalize_value(recent, bp["breakpoints"])
    cumulative_threshold = bp.get("cumulative_threshold_mm", 200)
    # Soft bump: cumulative rainfall beyond threshold adds hazard.
    if cumulative > cumulative_threshold:
        bump = normalize_value(cumulative,
                               [(cumulative_threshold, 0.0), (cumulative_threshold * 2, 0.3)])
        base = min(1.0, base + bump)
    note = _rainfall_note(recent, cumulative, cumulative_threshold)
    return recent, base, note, cumulative


def _rainfall_note(recent, cumulative, threshold):
    parts = []
    if recent >= 100:
        parts.append("Intense 24h rainfall (>100mm)")
    if cumulative > threshold:
        parts.append(f"Cumulative 7-day rainfall elevated (>{threshold}mm)")
    return "; ".join(parts) if parts else "Rainfall within normal range"
