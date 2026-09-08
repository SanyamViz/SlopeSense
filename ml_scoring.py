"""ML-driven scorer powered by a RandomForestClassifier over the NASA GLC schema.

This module implements the same ``Scorer`` protocol as ``WeightedScorer`` in
scoring.py, so it can be injected into ``pipeline.main(scorer=MLScorer(...))``
with zero changes to pipeline logic.

The ML model is trained on the data-pack §2 target schema:
    rain_1d_mm, rain_3d_mm, rain_7d_mm, rain_30d_mm,
    elevation_m, slope_deg, aspect_deg, curvature,
    susceptibility_class, lulc_class, vegetation_proxy

When used inside the pipeline, each location row is mapped from the pipeline's
4-factor schema (slope_angle, rainfall_24h, rainfall_7d, soil_saturation,
proximity_to_event_km) into the ML feature space.  Features not present in the
pipeline row are filled from config defaults so the model always receives a
complete feature vector.

HACKATHON NOTE: The model probability is scaled to 0-100 to match the
WeightedScorer output range.  Per-factor contributions are derived from the
model's feature_importances_ so the output stays explainable and auditable.
"""
import logging
import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np

from config import CONFIG

logger = logging.getLogger(__name__)

# --- Default feature values for pipeline features not in the ML schema --------
# These are neutral / representative values for Kerala, used when the pipeline
# row doesn't carry a given ML feature (e.g. elevation, aspect, curvature,
# LULC).  The model was trained with these as fallbacks.
_DEFAULT_FEATURES: dict[str, float | int] = {
    "rain_1d_mm": 0.0,
    "rain_3d_mm": 0.0,
    "rain_7d_mm": 0.0,
    "rain_30d_mm": 0.0,
    "elevation_m": 500.0,
    "slope_deg": 15.0,
    "aspect_deg": 180.0,
    "curvature": 0.0,
    "susceptibility_class": 2,
    "lulc_class": 4,
    "vegetation_proxy": 0.5,
}

# Mapping from ML feature → canonical pipeline factor name.
# Used to aggregate feature importances into the 4 canonical factors.
_ML_FEATURE_TO_CANONICAL: dict[str, str] = {
    "slope_deg": "slope_angle",
    "elevation_m": "slope_angle",
    "aspect_deg": "slope_angle",
    "curvature": "slope_angle",
    "rain_1d_mm": "rainfall_intensity",
    "rain_3d_mm": "rainfall_intensity",
    "rain_7d_mm": "rainfall_intensity",
    "rain_30d_mm": "rainfall_intensity",
    "vegetation_proxy": "soil_saturation",
    "lulc_class": "soil_saturation",
    "susceptibility_class": "historical_proximity",
}

_CANONICAL_FACTORS = ["slope_angle", "rainfall_intensity", "soil_saturation", "historical_proximity"]
_CANONICAL_UNITS = {
    "slope_angle": "degrees",
    "rainfall_intensity": "mm/24hr",
    "soil_saturation": "fraction_saturated",
    "historical_proximity": "km_to_nearest_past_event",
}


class MLScorer:
    """Random Forest scorer implementing the ``Scorer`` protocol.

    The model is loaded from a pickle file (produced by ``train_ml_model.py``)
    containing a dict with keys: ``model``, ``feature_names``, ``feature_importances``.

    If the model file is missing or fails to load, the scorer falls back to
    ``WeightedScorer`` so the pipeline still runs.
    """

    def __init__(self, model_path: Optional[Path | str] = None, cfg: Optional[dict] = None):
        self.cfg = cfg or CONFIG
        self.weights = self.cfg["weights"]
        self.norm = self.cfg["normalization"]
        self.feature_names: list[str] = []
        self.feature_importances: np.ndarray = np.array([])
        self._model = None
        self._fallback: Optional[Any] = None

        if model_path is None:
            model_path = self.cfg.get("ml_model_path", CONFIG.get("ml_model_path"))

        if model_path and Path(model_path).exists():
            self._load_model(Path(model_path))
        else:
            logger.warning("ML model not found at %s -- falling back to WeightedScorer", model_path)
            from scoring import WeightedScorer
            self._fallback = WeightedScorer(self.cfg)

    def _load_model(self, model_path: Path) -> None:
        try:
            with open(model_path, "rb") as f:
                artifact = pickle.load(f)
            self._model = artifact["model"]
            self.feature_names = artifact["feature_names"]
            self.feature_importances = np.array(artifact.get("feature_importances", []),
                                                dtype=float)
            logger.info("Loaded ML model from %s (features=%s)", model_path, self.feature_names)
        except Exception as exc:
            logger.error("Failed to load ML model from %s: %s -- falling back", model_path, exc)
            from scoring import WeightedScorer
            self._fallback = WeightedScorer(self.cfg)

    def _row_to_features(self, row: Any) -> np.ndarray:
        """Map a pipeline row (Series or dict) to the ML feature vector."""
        values = {}

        # Direct mappings from pipeline schema to ML schema.
        slope = float(row.get("slope_angle", 0.0) or 0.0)
        values["slope_deg"] = slope

        rain_24h = float(row.get("rainfall_24h", 0.0) or 0.0)
        rain_7d = float(row.get("rainfall_7d", 0.0) or 0.0)
        values["rain_1d_mm"] = rain_24h
        values["rain_3d_mm"] = rain_7d * 0.4  # heuristic: 3-day ~ 40% of 7-day
        values["rain_7d_mm"] = rain_7d
        values["rain_30d_mm"] = rain_7d * 1.5  # heuristic: 30-day > 7-day

        soil = float(row.get("soil_saturation", 0.0) or 0.0)
        values["vegetation_proxy"] = 1.0 - soil  # inverse: wetter soil → less vegetation proxy

        # Elevation: not in pipeline row, use default unless a column exists.
        values["elevation_m"] = float(row.get("elevation_m", _DEFAULT_FEATURES["elevation_m"]))
        values["aspect_deg"] = float(row.get("aspect_deg", _DEFAULT_FEATURES["aspect_deg"]))
        values["curvature"] = float(row.get("curvature", _DEFAULT_FEATURES["curvature"]))

        # GSI susceptibility and LULC: not in pipeline row, use defaults.
        values["susceptibility_class"] = int(row.get("susceptibility_class",
                                                      _DEFAULT_FEATURES["susceptibility_class"]))
        values["lulc_class"] = int(row.get("lulc_class", _DEFAULT_FEATURES["lulc_class"]))

        # Proximity: map to susceptibility_class (lower proximity → higher susceptibility).
        proximity = float(row.get("proximity_to_event_km", 10.0) or 10.0)
        if proximity == 0.0:
            values["susceptibility_class"] = 4  # very high near past events
        elif proximity < 5.0:
            values["susceptibility_class"] = 3
        else:
            values["susceptibility_class"] = 1

        vec = np.array([values.get(f, _DEFAULT_FEATURES.get(f, 0.0)) for f in self.feature_names],
                       dtype=float).reshape(1, -1)
        return vec

    def _canonical_importance(self) -> dict[str, float]:
        """Aggregate ML feature importances into the 4 canonical pipeline factors."""
        aggregated: dict[str, float] = {f: 0.0 for f in _CANONICAL_FACTORS}
        for feat_name, importance in zip(self.feature_names, self.feature_importances):
            canonical = _ML_FEATURE_TO_CANONICAL.get(feat_name)
            if canonical:
                aggregated[canonical] += float(importance)

        total = sum(aggregated.values())
        if total > 0:
            for k in aggregated:
                aggregated[k] /= total
        return aggregated

    def score(self, row: Any) -> tuple[float, list[dict]]:
        """Return (risk_score_0to100, factors_list).

        Falls back to WeightedScorer if the model isn't loaded.
        """
        if self._fallback is not None:
            return self._fallback.score(row)

        # --- Primary scoring path (ML model) ---
        vec = self._row_to_features(row)

        # predict_proba gives P(landslide) in [0, 1].
        if hasattr(self._model, "predict_proba"):
            proba = float(self._model.predict_proba(vec)[0, 1])
        else:
            # Fallback for models without predict_proba (e.g. SVC without
            # probability calibration) -- use the raw decision function.
            proba = float(self._model.predict(vec)[0])

        risk_score = float(np.clip(proba * 100.0, 0.0, 100.0))

        # --- Factor contributions from feature importances ---
        canonical_imp = self._canonical_importance()

        factors = []
        for factor in _CANONICAL_FACTORS:
            if factor == "slope_angle":
                raw = float(row.get("slope_angle", 0.0) or 0.0)
                norm = self._norm(factor, raw)
            elif factor == "rainfall_intensity":
                from normalization import normalize_rainfall
                raw, norm, _note, _raw_7d = normalize_rainfall(row, self.cfg)
            elif factor == "soil_saturation":
                raw = float(row.get("soil_saturation", 0.0) or 0.0)
                norm = self._norm(factor, raw)
            elif factor == "historical_proximity":
                raw = float(row.get("proximity_to_event_km", 0.0) or 0.0)
                norm = self._norm(factor, raw)
            else:
                raw = 0.0
                norm = 0.0

            weight = canonical_imp.get(factor, 0.0)
            contribution = round(risk_score * weight, 2)
            entry = {
                "factor": factor,
                "raw_value": round(float(raw), 4),
                "unit": _CANONICAL_UNITS[factor],
                "normalized_value": round(float(norm), 4),
                "weight": round(weight, 4),
                "contribution": contribution,
                "note": f"ML feature importance weight",
            }
            if factor == "rainfall_intensity":
                entry["raw_value_7d"] = round(float(row.get("rainfall_7d", 0.0) or 0.0), 4)
            factors.append(entry)

        logger.info("MLScored %s: score=%.2f / factors=%s",
                    row.get("location_id", "?"), risk_score,
                    [(f["factor"], f["raw_value"], f["contribution"]) for f in factors])
        return risk_score, factors

    def _norm(self, factor: str, raw: float) -> float:
        from normalization import normalize_value
        return normalize_value(raw, self.norm[factor]["breakpoints"])
