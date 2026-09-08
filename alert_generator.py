"""Template-based landslide risk alert generator.

HACKATHON NOTE: Uses hand-written string templates filled from risk factor data
rather than free-form generation.  This keeps output deterministic, repeatable,
and easy to audit.  Hindi translations use simple, broadcast-safe vocabulary.

Integration: call `generate_alert(risk_score, risk_level, factors, location_name)`
and inject the returned dict into the location JSON under the `alert` key.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Human-readable factor names (English + Hindi)
# ---------------------------------------------------------------------------
_FACTOR_LABELS = {
    "slope_angle": {
        "en": "steep slope",
        "hi": "ढलान",
    },
    "rainfall_intensity": {
        "en": "heavy rainfall",
        "hi": "भारी बारिश",
    },
    "soil_saturation": {
        "en": "waterlogged soil",
        "hi": "मिट्टी में पानी",
    },
    "historical_proximity": {
        "en": "nearby past landslide activity",
        "hi": "पिछले भूस्खलन की गतिविधि",
    },
}

# ---------------------------------------------------------------------------
# Risk-level labels (English + Hindi)
# ---------------------------------------------------------------------------
_LEVEL_LABELS = {
    "severe": {"en": "Severe", "hi": "गंभीर"},
    "high": {"en": "High", "hi": "उच्च"},
    "moderate": {"en": "Moderate", "hi": "मध्यम"},
    "low": {"en": "Low", "hi": "कम"},
}

# ---------------------------------------------------------------------------
# Headline templates
# ---------------------------------------------------------------------------
_HEADLINE_TEMPLATES = {
    "severe": "Severe landslide risk detected in {village}",
    "high": "High landslide risk detected in {village}",
    "moderate": "Moderate landslide risk in {village}",
    "low": "Low landslide risk in {village}",
}

_HEADLINE_TEMPLATES_HI = {
    "severe": "{village} में गंभीर भूस्खलन का खतरा",
    "high": "{village} में उच्च भूस्खलन का खतरा",
    "moderate": "{village} में मध्यम भूस्खलन का खतरा",
    "low": "{village} में कम भूस्खलन का खतरा",
}

# ---------------------------------------------------------------------------
# Explanation templates keyed by top factor.
#
# These are *interpolation* templates, not static strings: every placeholder is
# filled from the location's actual factor dict (raw_value / normalized_value)
# so the rendered explanation names real numbers and changes per location.
# The EN and HI templates share the same structure -- the HI string is a
# translation of the EN string, not a separately hand-written variant.
# Threshold numbers come from config.CONFIG["alert_thresholds"]; the values
# below are the fallbacks used if a threshold is missing from config.
# ---------------------------------------------------------------------------
_ALERT_THRESHOLD_FALLBACKS = {
    "slope_angle": {"danger_deg": 35.0},
    "rainfall_intensity": {
        "rainfall_7d_danger_mm": 250.0,
        "rainfall_24h_danger_mm": 150.0,
    },
    "soil_saturation": {"saturation_danger_frac": 0.85},
    "historical_proximity": {"nearby_radius_km": 5.0},
}

_EXPLANATION_TEMPLATES = {
    "slope_angle": (
        "Steep terrain is the main driver of risk here: the slope angle has "
        "measured {slope_angle} deg, above the {danger_deg} deg danger threshold, "
        "so gravity can pull soil and rock downhill."
    ),
    "rainfall_intensity": (
        "Rainfall is the main driver of risk here: 24-hour rainfall has reached "
        "{rainfall_intensity} mm and the 7-day total is {rainfall_7d} mm, well "
        "above the {rainfall_7d_danger_mm} mm safety margin, leaving slopes "
        "heavily saturated and primed to fail."
    ),
    "soil_saturation": (
        "Soil saturation is the main driver of risk here: the ground is at "
        "{soil_saturation_pct}% saturation, above the {saturation_danger_pct}% "
        "danger level, which adds extra weight to the slope and reduces the "
        "soil's ability to hold together."
    ),
    "historical_proximity": (
        "This location sits {historical_proximity} km from the nearest past "
        "landslide, {proximity_note_en}, and past movement has weakened the slope "
        "for future events."
    ),
}

_EXPLANATION_TEMPLATES_HI = {
    "slope_angle": (
        "यहाँ ढलान का खतरा मुख्य कारण है: ढलान का कोण {slope_angle} डिग्री मापा गया है, "
        "जो {danger_deg} डिग्री के खतरे की सीमा से अधिक है, इसलिए गुरुत्वाकर्षण मिट्टी और "
        "चट्टानों को नीचे की ओर खींच सकता है।"
    ),
    "rainfall_intensity": (
        "यहाँ बारिश का खतरा मुख्य कारण है: 24 घंटे की बारिश {rainfall_intensity} mm "
        "पहुँची है और 7 दिन का कुल {rainfall_7d} mm है, जो {rainfall_7d_danger_mm} mm "
        "की सुरक्षा सीमा से बहुत अधिक है, जिससे ढलान भार से भरे हुए और फैलने के लिए "
        "तैयार हो जाते हैं।"
    ),
    "soil_saturation": (
        "यहाँ मिट्टी में पानी का खतरा मुख्य कारण है: जमीन {soil_saturation_pct}% "
        "संतृप्ति पर है, जो {saturation_danger_pct}% के खतरे की सीमा से अधिक है, जिससे "
        "ढलान पर अतिरिक्त भार पड़ता है और मिट्टी टिकने की क्षमता कम हो जाती है।"
    ),
    "historical_proximity": (
        "यह स्थान पिछले भूस्खलन से {historical_proximity} km की दूरी पर है, "
        "{proximity_note_hi}, और पुरानी गति से ढलान की मजबूती कम हो जाती है।"
    ),
}

# ---------------------------------------------------------------------------
# Recommended-action templates
# ---------------------------------------------------------------------------
_ACTION_TEMPLATES = {
    "severe": (
        "Impose movement restrictions on steep slopes; activate early-warning sirens; "
        "prepare evacuation of at-risk settlements."
    ),
    "high": (
        "Avoid steep slopes and gullies; monitor for cracks or unusual water flow; "
        "issue a public advisory within 24 hours."
    ),
    "moderate": (
        "Keep monitoring; clear surface drainage channels; advise caution on trails and cut slopes."
    ),
    "low": (
        "Routine monitoring; no immediate restrictions required."
    ),
}

_ACTION_TEMPLATES_HI = {
    "severe": "ढलान वाले क्षेत्रों में आवागमन बंद करें; पूर्व चेतावनी की सीरेन सक्रिय करें; खतरे वाले बस्तियों का खाली करना तैयार करें।",
    "high": "ढलान और नालियों से बचें; दरार या असामान्य पानी की धार के लिए निगरानी करें; 24 घंटे के भीतर जनता को सलाह दें।",
    "moderate": "निगरानी जारी रखें; सतह के ड्रेनेज चैनल साफ करें; मार्गों और कटे हुए ढलानों पर सावधानी बताएं।",
    "low": "नियमित निगरानी; तुरंत किसी प्रतिबंध की आवश्यकता नहीं है।",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_explanation_context(factors, top_factor):
    """Assemble the interpolation context for the explanation template.

    Pulls raw_value / normalized_value straight from the factor dict that the
    scorer produced (no resampling, no re-fetching) and merges in the
    per-factor danger thresholds from config so the copy quotes defensible
    numbers instead of hardcoded literals.
    """
    by_factor = {f["factor"]: f for f in factors}
    dominant = by_factor[top_factor]

    # Pull the danger thresholds from config, falling back to the local table
    # so the module stays importable without a running pipeline.
    thresholds = dict(_ALERT_THRESHOLD_FALLBACKS[top_factor])
    try:
        from config import CONFIG
        cfg_thr = CONFIG.get("alert_thresholds", {}).get(top_factor, {})
        thresholds.update(cfg_thr)
    except Exception:  # pragma: no cover - config not on path in unit tests
        pass

    proximity = dominant.get("raw_value")
    nearby = thresholds.get("nearby_radius_km")
    if proximity is not None and nearby is not None and proximity <= nearby:
        proximity_note_en = f"within the {nearby} km 'nearby' radius"
        proximity_note_hi = f"{nearby} km की 'नज़दीक' सीमा के भीतर"
    elif proximity is not None and nearby is not None:
        proximity_note_en = f"outside the {nearby} km 'nearby' radius"
        proximity_note_hi = f"{nearby} km की 'नज़दीक' सीमा से बाहर"
    else:
        proximity_note_en = "at an unknown distance from past landslide activity"
        proximity_note_hi = "पिछले भूस्खलन से अज्ञात दूरी पर"

    ctx = {
        "slope_angle": dominant.get("raw_value"),
        "danger_deg": thresholds.get("danger_deg"),
        "rainfall_intensity": dominant.get("raw_value"),
        "rainfall_7d": dominant.get("raw_value_7d"),
        "rainfall_7d_danger_mm": thresholds.get("rainfall_7d_danger_mm"),
        "rainfall_24h_danger_mm": thresholds.get("rainfall_24h_danger_mm"),
        "soil_saturation": dominant.get("raw_value"),
        "soil_saturation_pct": round((dominant.get("raw_value") or 0.0) * 100, 1),
        "saturation_danger_frac": thresholds.get("saturation_danger_frac"),
        "saturation_danger_pct": round((thresholds.get("saturation_danger_frac") or 0.0) * 100, 1),
        "historical_proximity": proximity,
        "nearby_radius_km": nearby,
        "proximity_note_en": proximity_note_en,
        "proximity_note_hi": proximity_note_hi,
    }
    return ctx


def _format_explanation(template, ctx):
    """Render an explanation template, substituting every placeholder from ctx.

    Missing values fall back to a neutral phrase so a sparse factor dict still
    produces a readable (if less specific) sentence rather than crashing.
    """
    def _fmt(key, value):
        if value is None:
            return "n/a"
        if isinstance(value, float):
            return f"{value:.1f}"
        return str(value)

    class _SafeDict(dict):
        def __missing__(self, key):
            return "n/a"

    safe = _SafeDict({k: _fmt(k, v) for k, v in ctx.items()})
    return template.format_map(safe)


def generate_alert(
    risk_score: float,
    risk_level: str,
    factors: list[dict[str, Any]],
    location_name: str = "this location",
) -> dict[str, str]:
    """Return a structured alert dict with English and Hindi text.

    Args:
        risk_score: Normalised 0-100 risk score.
        risk_level: One of ``low``, ``moderate``, ``high``, ``severe``.
        factors: Per-factor contribution dicts from the scoring layer.
        location_name: Village / settlement name for headline placeholders.

    Returns:
        Dict with keys ``headline``, ``headline_hi``, ``explanation``,
        ``explanation_hi``, ``recommended_action``, ``recommended_action_hi``,
        ``top_factor``, ``language``.
    """
    risk_level = risk_level.lower()
    if risk_level not in _HEADLINE_TEMPLATES:
        logger.warning("Unknown risk_level '%s' -- falling back to 'moderate'", risk_level)
        risk_level = "moderate"

    dominant = max(factors, key=lambda f: f["contribution"])
    top_factor = dominant["factor"]

    headline = _HEADLINE_TEMPLATES[risk_level].format(village=location_name)
    headline_hi = _HEADLINE_TEMPLATES_HI[risk_level].format(village=location_name)

    # Explanation is chosen by top_factor and interpolated from the SAME factor
    # object that was selected as dominant -- no resampling, no re-fetch.
    ctx = _build_explanation_context(factors, top_factor)
    explanation = _format_explanation(
        _EXPLANATION_TEMPLATES.get(
            top_factor, "Multiple factors are contributing to elevated landslide risk."
        ),
        ctx,
    )
    explanation_hi = _format_explanation(
        _EXPLANATION_TEMPLATES_HI.get(
            top_factor, "भूस्खलन के खतरे को ढ़ावा देने के कई कारक हैं।"
        ),
        ctx,
    )

    action = _ACTION_TEMPLATES.get(
        risk_level, _ACTION_TEMPLATES["moderate"]
    )
    action_hi = _ACTION_TEMPLATES_HI.get(
        risk_level, _ACTION_TEMPLATES_HI["moderate"]
    )

    alert = {
        "headline": headline,
        "headline_hi": headline_hi,
        "explanation": explanation,
        "explanation_hi": explanation_hi,
        "recommended_action": action,
        "recommended_action_hi": action_hi,
        "top_factor": top_factor,
        "language": "en,hi",
    }

    logger.debug("Generated alert for %s (level=%s, factor=%s): %s",
                 location_name, risk_level, top_factor, headline)
    return alert
