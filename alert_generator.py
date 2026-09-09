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
# Human-readable factor names (English + Hindi + Malayalam)
# ---------------------------------------------------------------------------
_FACTOR_LABELS = {
    "slope_angle": {
        "en": "steep slope",
        "hi": "ढलान",
        "ml": "ഢലാന ചരിവ്",
    },
    "rainfall_intensity": {
        "en": "heavy rainfall",
        "hi": "भारी बारिश",
        "ml": "ശക്തമായ മഴ",
    },
    "soil_saturation": {
        "en": "waterlogged soil",
        "hi": "मिट्टी में पानी",
        "ml": "മണ്ണിലെ ജലാംശം",
    },
    "historical_proximity": {
        "en": "nearby past landslide activity",
        "hi": "पिछले भूस्खलन की गतिविधि",
        "ml": "പില്ലി ഭൂസ്ഖലന സമീപത",
    },
}

# ---------------------------------------------------------------------------
# Risk-level labels (English + Hindi + Malayalam)
# ---------------------------------------------------------------------------
_LEVEL_LABELS = {
    "severe": {"en": "Severe", "hi": "गंभीर", "ml": "തീവ്ര"},
    "high": {"en": "High", "hi": "उच्च", "ml": "ഉയർന്ന"},
    "moderate": {"en": "Moderate", "hi": "मध्यम", "ml": "മധ്യമ"},
    "low": {"en": "Low", "hi": "कम", "ml": "കമ"},
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

_HEADLINE_TEMPLATES_ML = {
    "severe": "{village} എന്ന പ്രദേശത്ത് തീവ്ര ഭൂസ്ഖലന അപകടം",
    "high": "{village} എന്ന പ്രദേശത്ത് ഉയർന്ന ഭൂസ്ഖലന അപകടം",
    "moderate": "{village} എന്ന പ്രദേശത്ത് മധ്യമ ഭൂസ്ഖലന അപകടം",
    "low": "{village} എന്ന പ്രദേശത്ത് കറാഞ്ഞ ഭൂസ്ഖലന അപകടം",
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
# Explanation templates (Malayalam) -- parallel translation of the EN strings.
# ---------------------------------------------------------------------------
_EXPLANATION_TEMPLATES_ML = {
    "slope_angle": (
        "ഇവിടെ ഢലാനത ഖതരാക്കാനുള്ള പ്രധാന കാരണമാണ്: ചരിവിന്റെ കോണ് "
        "{slope_angle} ഡിഗ്രിയായി അളിചെട്ടിട്ടുണ്ട്, {danger_deg} ഡിഗ്രിയുടെ "
        "ഖതര കിന്നിയിൽ നിന്ന് കൂടുതലാണ്, അതിനാൽ ഗുരുത്വാകർഷണം കല്ലുകളും "
        "മണ്ണും താഴേക്ക് വലിക്കും."
    ),
    "rainfall_intensity": (
        "ഇവിടെ മഴയുടെ ഖതരമാണ് പ്രധാന കാരണം: 24 മണിക്കൂറിലെ മഴ "
        "{rainfall_intensity} mm എത്തിയിട്ടുണ്ട്, 7 ദിവസത്തെ മൊത്തം "
        "{rainfall_7d} mm, {rainfall_7d_danger_mm} mm എന്ന സുരക്ഷിത ബാധിത മിതിയിൽ "
        "നിന്ന് വളരെ കൂടുതലാണ്, ഇത് ഢലാനങ്ങളെ ഭാരം നിറഞ്ഞു പുറപ്പെടുവാൻ "
        "തയാറാക്കിയിട്ടുണ്ട്."
    ),
    "soil_saturation": (
        "ഇവിടെ മണ്ണിലെ ജലാംശത്തിന്റെ ഖതരമാണ് പ്രധാന കാരണം: ഭൂമി "
        "{soil_saturation_pct}% സംതൃപ്തിയിലാണ്, {saturation_danger_pct}% എന്ന ഖതര "
        "മിതിയിൽ നിന്ന് കൂടുതലാണ്, ഇത് ഢലാനത്തിന് അതിരിക്ത ഭാരം കൂട്ടി "
        "മണ്ണിന്റെ ഒന്നിക്കാനുള്ള ക്ഷമത കുറയ്ക്കും."
    ),
    "historical_proximity": (
        "ഈ സ്ഥാനം പില്ലി ഭൂസ്ഖലനത്തിൽ നിന്ന് {historical_proximity} km "
        "ദൂരത്തിലാണ്, {proximity_note_ml}, പുരാതന ചലനം ഭൂകമ്പത്തിന് ശേഷവും "
        "ഢലാനത്തിന്റെ ശക്തി കുറഞ്ഞിട്ടുണ്ട്."
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

_ACTION_TEMPLATES_ML = {
    "severe": "ഢലാനമുള്ള പ്രദേശങ്ങളിലേക്കുള്ള പ്രവേശനം നിരോധിക്കുക; മുന്നോട്ട് എതിർത്താൽ സൈറൻ സജ്ജീകരിക്കുക; അപകടത്തിലുള്ള കുടുംബങ്ങളെ മാറ്റിനിർത്താൻ തയാറാക്കുക.",
    "high": "ഢലാനങ്ങളും കുളങ്ങളും ഒഴിവാക്കുക; ക്രാക്കുകളോ സാധാരണമില്ലാത്ത ജലപ്രവാഹമോ പര്യവേക്ഷണം ചെയ്യുക; 24 മണിക്കൂറിനുള്ളിൽ പൊതുജനങ്ങളെ അറിയിക്കുക.",
    "moderate": "പര്യവേക്ഷണം തുടരുക; പ്രാഥമിക ജലനിരമ്പാൻ ചാനലുകൾ ക്ലിയർ ചെയ്യുക; വന്യപാതകളും മുറിച്ചുകൊണ്ടുള്ള ഢലാനങ്ങളും സംഭവിച്ചുകൊണ്ടുള്ള സ്ഥലങ്ങളിൽ ജാഗ്രത പ്രാപ്പിക്കുക.",
    "low": "നിയമിതമായ പര്യവേക്ഷണം; ഉടനെ എത്രയും നിരോധങ്ങളും ആവശ്യമില്ല.",
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
        proximity_note_ml = f"{nearby} km എന്ന സമീപത സീമയ്ക്ക് ഉള്ളിൽ"
    elif proximity is not None and nearby is not None:
        proximity_note_en = f"outside the {nearby} km 'nearby' radius"
        proximity_note_hi = f"{nearby} km की 'नज़दीक' सीमा से बाहर"
        proximity_note_ml = f"{nearby} km എന്ന സമീപത സീമയ്ക്ക് പുറത്ത്"
    else:
        proximity_note_en = "at an unknown distance from past landslide activity"
        proximity_note_hi = "पिछले भूस्खलन से अज्ञात दूरी पर"
        proximity_note_ml = "പില്ലി ഭൂസ്ഖലനത്തിൽ നിന്നുള്ള ദൂരം അറിഞ്ഞില്ല"

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
        "proximity_note_ml": proximity_note_ml,
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
    language: str = "hi",
) -> dict[str, str]:
    """Return a structured alert dict with English + vernacular text.

    Args:
        risk_score: Normalised 0-100 risk score.
        risk_level: One of ``low``, ``moderate``, ``high``, ``severe``.
        factors: Per-factor contribution dicts from the scoring layer.
        location_name: Village / settlement name for headline placeholders.
        language: Vernacular code to render -- ``"hi"`` (Hindi, default) or
            ``"ml"`` (Malayalam, used for Wayanad villages). Unknown codes
            fall back to ``"hi"``.

    Returns:
        Dict with keys ``headline``, ``headline_hi``, ``headline_ml``,
        ``explanation``, ``explanation_hi``, ``explanation_ml``,
        ``recommended_action``, ``recommended_action_hi``,
        ``recommended_action_ml``, ``top_factor``, ``language``.
    """
    risk_level = risk_level.lower()
    if risk_level not in _HEADLINE_TEMPLATES:
        logger.warning("Unknown risk_level '%s' -- falling back to 'moderate'", risk_level)
        risk_level = "moderate"

    if language not in ("hi", "ml"):
        logger.warning("Unknown language '%s' -- falling back to 'hi'", language)
        language = "hi"

    dominant = max(factors, key=lambda f: f["contribution"])
    top_factor = dominant["factor"]

    headline = _HEADLINE_TEMPLATES[risk_level].format(village=location_name)
    headline_hi = _HEADLINE_TEMPLATES_HI[risk_level].format(village=location_name)
    headline_ml = _HEADLINE_TEMPLATES_ML[risk_level].format(village=location_name)

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
    explanation_ml = _format_explanation(
        _EXPLANATION_TEMPLATES_ML.get(
            top_factor, "ഉന്നത ഭൂസ്ഖലന അപകടത്തിന് ഒന്നിക്കുന്ന ഒരു പല ഘടകങ്ങളും ഉണ്ട്."
        ),
        ctx,
    )

    action = _ACTION_TEMPLATES.get(
        risk_level, _ACTION_TEMPLATES["moderate"]
    )
    action_hi = _ACTION_TEMPLATES_HI.get(
        risk_level, _ACTION_TEMPLATES_HI["moderate"]
    )
    action_ml = _ACTION_TEMPLATES_ML.get(
        risk_level, _ACTION_TEMPLATES_ML["moderate"]
    )

    alert = {
        "headline": headline,
        "headline_hi": headline_hi,
        "headline_ml": headline_ml,
        "explanation": explanation,
        "explanation_hi": explanation_hi,
        "explanation_ml": explanation_ml,
        "recommended_action": action,
        "recommended_action_hi": action_hi,
        "recommended_action_ml": action_ml,
        "top_factor": top_factor,
        "language": language,
    }

    logger.debug("Generated alert for %s (level=%s, factor=%s, lang=%s): %s",
                 location_name, risk_level, top_factor, language, headline)
    return alert
