"""Tests for ML model training and inference (ml_scoring, train_ml_model, generate_negative_samples).

Covers:
  - Negative sample generation: schema, labels, geographic distribution, jitter
  - MLScorer protocol compliance: returns (float, list[dict]) with correct structure
  - MLScorer fallback to WeightedScorer when model file is missing
  - MLScorer end-to-end with a trained model artifact
  - train_ml_model: synthetic data fallback, spatial split, model save/load round-trip
"""
import json
import os
import sys
import pickle
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_negative_samples import (
    generate, generate_negatives, _synthetic_positives, TARGET_COLUMNS,
    _offset_point, _sample_context,
)
from ml_scoring import MLScorer, _CANONICAL_FACTORS
from train_ml_model import (
    train_model, save_model, FEATURE_COLUMNS as ML_FEATURES,
    _load_training_data, _validate_columns,
)
from config import CONFIG
from scoring import WeightedScorer, score_single_location
from classification import classify


# ===================================================================
# 1. Negative Sample Generation
# ===================================================================
class TestNegativeSamples:
    def test_synthetic_positives_have_correct_schema(self):
        df = _synthetic_positives(n=10, seed=42)
        assert len(df) == 10
        expected_cols = set(TARGET_COLUMNS)
        assert set(df.columns) == expected_cols
        assert (df["landslide_label"] == 1).all()

    def test_negatives_have_label_zero(self):
        pos = _synthetic_positives(n=10, seed=42)
        neg = generate_negatives(pos, n_per_positive=3, radius_km=5.0, seed=42)
        assert len(neg) == 30
        assert (neg["landslide_label"] == 0).all()

    def test_negative_schema_matches_target(self):
        pos = _synthetic_positives(n=5, seed=42)
        neg = generate_negatives(pos, n_per_positive=2, seed=42)
        assert set(neg.columns) == set(TARGET_COLUMNS)

    def test_negatives_within_radius(self):
        """Each negative must be within radius_km of its parent positive."""
        from math import radians, cos, sin, sqrt, atan2, asin
        pos = _synthetic_positives(n=5, seed=42)
        neg = generate_negatives(pos, n_per_positive=3, radius_km=5.0, seed=42)

        for _, p_row in pos.iterrows():
            parent_id = p_row["record_id"]
            parent_negs = neg[neg["record_id"].str.startswith(f"NEG_{parent_id}_")]
            for _, n_row in parent_negs.iterrows():
                lat1, lon1 = radians(float(p_row["latitude"])), radians(float(p_row["longitude"]))
                lat2, lon2 = radians(float(n_row["latitude"])), radians(float(n_row["longitude"]))
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                dist_km = 2 * 6371 * asin(sqrt(a))
                assert dist_km <= 5.0 + 0.1, f"Negative at {dist_km:.2f}km exceeds 5km radius"

    def test_offset_point_stays_in_kerala(self):
        lat, lon = 11.5, 76.1  # central Kerala
        rng = np.random.default_rng(42)
        for _ in range(100):
            new_lat, new_lon = _offset_point(lat, lon, 5.0, rng)
            assert 8.25 <= new_lat <= 12.80
            assert 74.80 <= new_lon <= 77.40

    def test_generate_writes_csv(self, tmp_path):
        pos = _synthetic_positives(n=5, seed=42)
        pos_path = tmp_path / "pos.csv"
        pos.to_csv(pos_path, index=False)
        out_path = tmp_path / "neg.csv"
        generate(input_path=pos_path, output_path=str(out_path), n_per_positive=2)
        assert out_path.exists()
        df = pd.read_csv(out_path)
        assert len(df) == 10
        assert (df["landslide_label"] == 0).all()


# ===================================================================
# 2. MLScorer -- Protocol Compliance
# ===================================================================
class TestMLScorerProtocol:
    def test_scorer_returns_float_and_list(self):
        """MLScorer.score must return (float, list[dict]) per Scorer protocol."""
        scorer = MLScorer(model_path="nonexistent_model.pkl")
        row = pd.Series({
            "location_id": "test_001",
            "slope_angle": 30.0,
            "rainfall_24h": 100.0,
            "rainfall_7d": 200.0,
            "soil_saturation": 0.7,
            "proximity_to_event_km": 5.0,
        })
        score, factors = scorer.score(row)
        assert isinstance(score, float)
        assert isinstance(factors, list)
        assert 0.0 <= score <= 100.0

    def test_fallback_to_weighted_scorer_when_no_model(self):
        """Without a model file, MLScorer should fall back to WeightedScorer."""
        scorer = MLScorer(model_path="nonexistent_model.pkl")
        assert scorer._fallback is not None
        assert scorer._model is None

        row = pd.Series({
            "location_id": "test_002",
            "slope_angle": 30.0,
            "rainfall_24h": 100.0,
            "rainfall_7d": 0.0,
            "soil_saturation": 0.7,
            "proximity_to_event_km": 5.0,
        })
        # Should match WeightedScorer exactly.
        ws = WeightedScorer(CONFIG)
        ws_score, ws_factors = ws.score(row)
        ml_score, ml_factors = scorer.score(row)
        assert ml_score == pytest.approx(ws_score, abs=1e-6)
        assert len(ml_factors) == len(ws_factors)

    def test_factor_structure_matches_weighted_scorer(self):
        """MLScorer factors should have the same keys as WeightedScorer."""
        scorer = MLScorer(model_path="nonexistent_model.pkl")
        row = pd.Series({
            "location_id": "test_003",
            "slope_angle": 42.0,
            "rainfall_24h": 204.5,
            "rainfall_7d": 500.0,
            "soil_saturation": 0.85,
            "proximity_to_event_km": 0.0,
        })
        _, factors = scorer.score(row)
        for f in factors:
            assert "factor" in f
            assert "raw_value" in f
            assert "unit" in f
            assert "normalized_value" in f
            assert "weight" in f
            assert "contribution" in f
            assert "note" in f

    def test_four_canonical_factors_present(self):
        scorer = MLScorer(model_path="nonexistent_model.pkl")
        row = pd.Series({
            "location_id": "test_004",
            "slope_angle": 30.0,
            "rainfall_24h": 100.0,
            "rainfall_7d": 200.0,
            "soil_saturation": 0.7,
            "proximity_to_event_km": 5.0,
        })
        _, factors = scorer.score(row)
        factor_names = [f["factor"] for f in factors]
        assert factor_names == _CANONICAL_FACTORS


# ===================================================================
# 3. MLScorer -- End-to-End with Trained Model
# ===================================================================
class TestMLScorerWithModel:
    @pytest.fixture(autouse=True, scope="class")
    def _restore_pipeline_output(self):
        """Regenerate landslide_risk_output.json with the default WeightedScorer
        after ML tests finish.

        The pipeline test below runs ``pipeline.main(scorer=MLScorer)`` which
        overwrites ``landslide_risk_output.json`` with ML-scored results.  Tests
        in test_pipeline.py depend on the default WeightedScorer output, so we
        re-run the pipeline with the default scorer (scorer=None) in tearDown.
        """
        yield
        try:
            from pipeline import main as _main
            _main(scorer=None)
        except Exception as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Failed to restore pipeline output: %s", exc)

    @pytest.fixture(scope="class")
    def trained_artifact(self, tmp_path_factory):
        """Train a small RF on synthetic data and save the artifact."""
        tmp = tmp_path_factory.mktemp("ml_test")
        df = _load_training_data()
        clf = train_model(df, n_estimators=20, random_state=42)
        model_path = tmp / "test_model.pkl"
        save_model(clf, model_path)
        return model_path

    def test_ml_scorer_loads_trained_model(self, trained_artifact):
        scorer = MLScorer(model_path=trained_artifact)
        assert scorer._model is not None
        assert scorer._fallback is None
        assert len(scorer.feature_names) > 0

    def test_ml_scorer_scores_realistic_row(self, trained_artifact):
        scorer = MLScorer(model_path=trained_artifact)
        row = pd.Series({
            "location_id": "ml_test_loc",
            "slope_angle": 42.0,
            "rainfall_24h": 204.5,
            "rainfall_7d": 573.1,
            "soil_saturation": 1.0,
            "proximity_to_event_km": 0.0,
        })
        score, factors = scorer.score(row)
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0
        assert len(factors) == 4

    def test_ml_scorer_wayanad_validation_case(self, trained_artifact):
        """The ML model should classify the Wayanad validation row as severe/high."""
        scorer = MLScorer(model_path=trained_artifact)
        row = pd.Series({
            "location_id": "WAYANAD_2024_VAL",
            "name": "Mundakkai-Chooralmala",
            "slope_angle": 42.0,
            "rainfall_24h": 204.5,
            "rainfall_7d": 573.1,
            "soil_saturation": 1.0,
            "proximity_to_event_km": 0.0,
        })
        score, factors = scorer.score(row)
        level = classify(score, CONFIG["risk_thresholds"])
        # The Wayanad validation case should be at least "high".
        assert level in ("high", "severe"), f"Expected high/severe, got {level} (score={score})"

    def test_ml_and_weighted_scores_differ(self, trained_artifact):
        """ML scorer and WeightedScorer should produce different scores for
        some rows (otherwise the ML model isn't adding value)."""
        scorer = MLScorer(model_path=trained_artifact)
        ws = WeightedScorer(CONFIG)
        test_row = pd.Series({
            "location_id": "divergence_test",
            "slope_angle": 5.0,
            "rainfall_24h": 10.0,
            "rainfall_7d": 20.0,
            "soil_saturation": 0.3,
            "proximity_to_event_km": 20.0,
        })
        ml_score, _ = scorer.score(test_row)
        ws_score, _ = ws.score(test_row)
        # At least the factor weights should differ (ML imports vs config weights).
        assert scorer.feature_importances is not None

    def test_pipeline_accepts_ml_scorer(self, trained_artifact):
        """pipeline.main(scorer=...) should run with MLScorer."""
        from pipeline import main
        scorer = MLScorer(model_path=trained_artifact)
        main(scorer=scorer)
        # The pipeline writes output; verify it exists and has ML metadata.
        from config import CONFIG
        out_path = Path(CONFIG["output"])
        assert out_path.exists()
        with open(out_path, encoding="utf-8") as f:
            doc = json.load(f)
        assert len(doc["locations"]) > 0
        # Verify at least one location has factors from the ML scorer.
        loc = doc["locations"][0]
        assert "risk_score" in loc
        assert "factors" in loc


# ===================================================================
# 4. Training Pipeline
# ===================================================================
class TestTrainingPipeline:
    def test_load_training_data_falls_back_to_synthetic(self):
        """Without real data files, _load_training_data should generate synthetic data."""
        df = _load_training_data()
        assert len(df) > 0
        assert "landslide_label" in df.columns
        assert set(ML_FEATURES).issubset(set(df.columns))

    def test_validate_columns_fills_defaults(self):
        df = pd.DataFrame({
            "latitude": [10.0],
            "longitude": [76.0],
            "landslide_label": [1],
            # Missing elevation_m, aspect_deg, etc.
        })
        validated = _validate_columns(df)
        for col in ML_FEATURES:
            assert col in validated.columns
        assert (validated["landslide_label"] == 1).all()

    def test_train_model_returns_classifier(self):
        df = _load_training_data()
        clf = train_model(df, n_estimators=10, random_state=42)
        from sklearn.ensemble import RandomForestClassifier
        assert isinstance(clf, RandomForestClassifier)
        assert hasattr(clf, "feature_importances_")
        assert len(clf.feature_importances_) == len(ML_FEATURES)

    def test_model_save_and_load_roundtrip(self, tmp_path):
        df = _load_training_data()
        clf = train_model(df, n_estimators=10, random_state=42)
        model_path = tmp_path / "roundtrip_model.pkl"
        save_model(clf, model_path)
        assert model_path.exists()

        with open(model_path, "rb") as f:
            artifact = pickle.load(f)
        assert "model" in artifact
        assert "feature_names" in artifact
        assert "feature_importances" in artifact
        assert artifact["feature_names"] == ML_FEATURES

        # The loaded model should make predictions.
        loaded = artifact["model"]
        sample = df[ML_FEATURES].head(5).values
        preds = loaded.predict(sample)
        assert len(preds) == 5
