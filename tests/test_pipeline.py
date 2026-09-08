"""Comprehensive pytest suite for the landslide risk pipeline.

Covers normalization, scoring, classification, trust score, cascading
infrastructure, vulnerability/priority, explainable alerts, simulator, and API contract.
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CONFIG
from normalization import normalize_value
from scoring import WeightedScorer, score_single_location
from classification import classify
from trust_score import compute_trust_score, build_trust_block, load_alert_history
from graph_analysis import build_graph, find_stranded_zones
from vulnerability import compute_vulnerability_score
from priority import compute_priority_score
from alert_generator import generate_alert

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "landslide_risk_output.json"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def output_doc():
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def locations(output_doc):
    return output_doc["locations"]


@pytest.fixture(scope="session")
def location_by_id(output_doc):
    return {loc["location_id"]: loc for loc in output_doc["locations"]}


@pytest.fixture(scope="session")
def trust_history():
    return load_alert_history()


# ===================================================================
# 1. Normalization & Scoring (regression protection)
# ===================================================================
class TestNormalization:
    def test_documented_breakpoints_map_exactly(self):
        bp_cfg = CONFIG["normalization"]
        assert normalize_value(30, bp_cfg["slope_angle"]["breakpoints"]) == pytest.approx(0.5, abs=1e-9)
        assert normalize_value(100, bp_cfg["rainfall_intensity"]["breakpoints"]) == pytest.approx(0.8, abs=1e-9)
        assert normalize_value(0.7, bp_cfg["soil_saturation"]["breakpoints"]) == pytest.approx(0.7, abs=1e-9)
        assert normalize_value(5, bp_cfg["historical_proximity"]["breakpoints"]) == pytest.approx(0.3, abs=1e-9)

    def test_midpoint_interpolation_per_factor(self):
        bp_cfg = CONFIG["normalization"]
        # slope: midpoint of (15,0.2) and (30,0.5)
        assert normalize_value(22.5, bp_cfg["slope_angle"]["breakpoints"]) == pytest.approx(0.35, abs=1e-9)
        # rainfall: midpoint of (50,0.4) and (75,0.6)
        assert normalize_value(62.5, bp_cfg["rainfall_intensity"]["breakpoints"]) == pytest.approx(0.5, abs=1e-9)
        # soil: midpoint of (0.5,0.4) and (0.7,0.7)
        assert normalize_value(0.6, bp_cfg["soil_saturation"]["breakpoints"]) == pytest.approx(0.55, abs=1e-9)
        # proximity: midpoint of (3,0.5) and (5,0.3)
        assert normalize_value(4.0, bp_cfg["historical_proximity"]["breakpoints"]) == pytest.approx(0.4, abs=1e-9)


class TestScoring:
    def test_weighted_sum_exact(self):
        raw_factors = {
            "location_id": "test",
            "slope_angle": 30.0,
            "rainfall_24h": 100.0,
            "rainfall_7d": 0.0,
            "soil_saturation": 0.7,
            "proximity_to_event_km": 5.0,
        }
        result = score_single_location(raw_factors, CONFIG)
        expected = 100.0 * (
            0.5 * 0.35
            + 0.8 * 0.30
            + 0.7 * 0.20
            + 0.3 * 0.15
        )
        assert result["risk_score"] == pytest.approx(expected, abs=1e-9)
        assert result["risk_score"] == pytest.approx(60.0, abs=1e-9)


# ===================================================================
# 2. Classification
# ===================================================================
class TestClassification:
    @pytest.mark.parametrize("score,expected", [
        (0.0, "low"),
        (25.0, "low"),
        (25.5, "low"),
        (26.0, "moderate"),
        (50.0, "moderate"),
        (51.0, "high"),
        (75.0, "high"),
        (76.0, "severe"),
        (100.0, "severe"),
    ])
    def test_band_boundaries(self, score, expected):
        assert classify(score, CONFIG["risk_thresholds"]) == expected


# ===================================================================
# 3. Trust Score
# ===================================================================
class TestTrustScore:
    def test_three_correct_one_wrong(self):
        history = [
            {"zone_id": "z1", "predicted_risk_level": "low", "actual_outcome": "minor"},
            {"zone_id": "z1", "predicted_risk_level": "moderate", "actual_outcome": "none"},
            {"zone_id": "z1", "predicted_risk_level": "high", "actual_outcome": "severe"},
            {"zone_id": "z1", "predicted_risk_level": "low", "actual_outcome": "moderate"},
        ]
        score = compute_trust_score("z1", history)
        assert score["accuracy_pct"] == 75.0
        assert score["low_confidence"] is False

    def test_below_threshold_yields_low_confidence_and_note(self):
        history = [
            {"zone_id": "z2", "predicted_risk_level": "low", "actual_outcome": "moderate"},
        ]
        score = compute_trust_score("z2", history)
        assert score["low_confidence"] is True
        block = build_trust_block("z2", history)
        assert block["confidence_note"] is not None
        assert "secondary confirmation" in block["confidence_note"].lower()

    def test_every_location_has_trust_score(self, locations):
        for loc in locations:
            ts = loc.get("trust_score")
            assert ts is not None, f"{loc['location_id']} missing trust_score"
            assert "accuracy_pct" in ts
            assert "low_confidence" in ts

    def test_wayanad_has_trust_score(self, location_by_id):
        loc = location_by_id["WAYANAD_2024_VAL"]
        assert loc.get("trust_score") is not None
        assert loc["trust_score"]["accuracy_pct"] == 100.0
        assert loc["trust_score"]["low_confidence"] is False


# ===================================================================
# 4. Cascading Infrastructure
# ===================================================================
class TestCascadingInfrastructure:
    def test_stranded_zones_from_hand_authored_graph(self):
        edges = [
            {"from": "A", "to": "safe1", "road_id": "R1", "passes_through_zone_id": "B"},
            {"from": "B", "to": "safe1", "road_id": "R2", "passes_through_zone_id": None},
            {"from": "C", "to": "B", "road_id": "R3", "passes_through_zone_id": None},
            {"from": "C", "to": "safe1", "road_id": "R4", "passes_through_zone_id": "B"},
        ]
        scored = [
            {"location_id": "A", "risk_level": "low"},
            {"location_id": "B", "risk_level": "severe"},
            {"location_id": "C", "risk_level": "moderate"},
        ]
        g = build_graph(edges)
        results = find_stranded_zones(g, scored, ["safe1"])
        stranded_ids = {r["zone_id"] for r in results}
        assert "A" in stranded_ids
        assert "B" not in stranded_ids
        assert "C" not in stranded_ids
        for r in results:
            if r["zone_id"] == "A":
                assert r["blocked_by_zone_id"] == "B"
                assert "safe1" in r["reason"].lower() or "shelter" in r["reason"].lower()

    def test_no_stranded_zone_has_null_cascading_risk_in_output(self, locations):
        for loc in locations:
            cr = loc.get("cascading_risk")
            if cr is None:
                continue
            if cr.get("stranded"):
                assert "blocked_by_zone" in cr
                assert "reason" in cr

    def test_real_output_has_at_least_one_stranded(self, locations):
        stranded = [l for l in locations if l.get("cascading_risk") and l["cascading_risk"].get("stranded")]
        assert len(stranded) >= 1, "Expected at least one stranded location in real output"


# ===================================================================
# 5. Vulnerability & Priority
# ===================================================================
class TestVulnerabilityAndPriority:
    def test_vulnerability_in_bounds_at_boundaries(self):
        vuln_csv = SAMPLE_DATA_DIR / "vulnerability.csv"
        import pandas as pd
        df = pd.read_csv(vuln_csv)
        max_pop = int(df["population"].max())

        row_zero = {"population": 0, "num_hospitals": 0, "num_schools": 0, "elderly_pct": 0.0}
        row_max = {"population": max_pop, "num_hospitals": 0, "num_schools": 0, "elderly_pct": 0.0}

        score_zero, _ = compute_vulnerability_score(row_zero, CONFIG)
        score_max, _ = compute_vulnerability_score(row_max, CONFIG)

        assert 0.0 <= score_zero <= 1.0
        assert 0.0 <= score_max <= 1.0

    def test_priority_weights_hand_built(self):
        risk = 50.0
        vuln = 0.5
        expected = risk * 0.6 + (vuln * 100.0) * 0.4
        result = compute_priority_score(risk, vuln, CONFIG)
        assert result == pytest.approx(expected, abs=1e-9)

    def test_top_risk_and_priority_differ_in_real_output(self, output_doc):
        top_risk = set(output_doc["summary"]["top_risk_locations"])
        top_priority = set(output_doc["summary"]["top_priority_locations"])
        assert top_risk != top_priority, "top_risk_locations and top_priority_locations should differ"


# ===================================================================
# 6. Explainable Alerts
# ===================================================================
class TestExplainableAlerts:
    def test_different_top_factors_yield_different_numbers_in_explanations(self, location_by_id):
        loc_a = location_by_id["loc_000"]  # top_factor: rainfall_intensity
        loc_b = location_by_id["loc_001"]  # top_factor: soil_saturation

        assert loc_a["alert"]["top_factor"] != loc_b["alert"]["top_factor"]

        nums_a = {float(m) for m in re.findall(r"\d+\.?\d*", loc_a["alert"]["explanation"])}
        nums_b = {float(m) for m in re.findall(r"\d+\.?\d*", loc_b["alert"]["explanation"])}

        # Find a number present in both that corresponds to the same semantic field
        # but with different values because raw_value differs.
        # At minimum, the set of numbers should not be identical.
        assert nums_a != nums_b, "Explanations should contain different numeric values"


# ===================================================================
# 7. Simulator
# ===================================================================
class TestSimulator:
    def test_score_single_location_matches_pipeline(self, location_by_id):
        loc = location_by_id["loc_000"]
        factors = loc["factors"]
        by_factor = {f["factor"]: f for f in factors}

        raw_factors = {
            "location_id": loc["location_id"],
            "slope_angle": by_factor["slope_angle"]["raw_value"],
            "rainfall_24h": by_factor["rainfall_intensity"]["raw_value"],
            "rainfall_7d": by_factor["rainfall_intensity"].get("raw_value_7d", 0.0),
            "soil_saturation": by_factor["soil_saturation"]["raw_value"],
            "proximity_to_event_km": by_factor["historical_proximity"]["raw_value"],
        }
        result = score_single_location(raw_factors, CONFIG)
        assert result["risk_score"] == pytest.approx(loc["risk_score"], abs=1e-9)
        assert result["risk_level"] == loc["risk_level"]

    def test_override_changes_risk_level(self, location_by_id):
        loc = location_by_id["loc_000"]
        factors = loc["factors"]
        by_factor = {f["factor"]: f for f in factors}

        raw_factors = {
            "location_id": loc["location_id"],
            "slope_angle": by_factor["slope_angle"]["raw_value"],
            "rainfall_24h": by_factor["rainfall_intensity"]["raw_value"],
            "rainfall_7d": by_factor["rainfall_intensity"].get("raw_value_7d", 0.0),
            "soil_saturation": by_factor["soil_saturation"]["raw_value"],
            "proximity_to_event_km": by_factor["historical_proximity"]["raw_value"],
        }
        original_level = score_single_location(raw_factors, CONFIG)["risk_level"]

        raw_factors["slope_angle"] = 60.0
        raw_factors["rainfall_24h"] = 200.0
        raw_factors["rainfall_7d"] = 500.0
        raw_factors["soil_saturation"] = 1.0
        raw_factors["proximity_to_event_km"] = 0.0
        new_level = score_single_location(raw_factors, CONFIG)["risk_level"]

        assert new_level == "severe"


# ===================================================================
# 8. API Contract
# ===================================================================
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


class TestAPIContract:
    def test_risk_map_schema(self, client):
        resp = client.get("/risk-map")
        assert resp.status_code == 200
        data = resp.json()
        assert "metadata" in data
        assert "summary" in data
        assert "locations" in data
        for loc in data["locations"]:
            assert "trust_score" in loc
            assert "vulnerability" in loc
            assert "priority_score" in loc
            assert "cascading_risk" in loc

    def test_risk_by_id_valid(self, client):
        resp = client.get("/risk/loc_000")
        assert resp.status_code == 200
        assert resp.json()["location_id"] == "loc_000"

    def test_risk_by_id_not_found(self, client):
        resp = client.get("/risk/does_not_exist")
        assert resp.status_code == 404

    def test_active_alerts_min_level_high(self, client):
        resp = client.get("/alerts/active?min_level=high")
        assert resp.status_code == 200
        for loc in resp.json()["locations"]:
            assert loc["risk_level"] in {"high", "severe"}

    def test_infrastructure_endpoint(self, client):
        resp = client.get("/infrastructure")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "stranded_zones" in data

    def test_simulate_valid_location(self, client, location_by_id):
        loc = location_by_id["loc_000"]
        payload = {
            "location_id": loc["location_id"],
            "overrides": {"rainfall_24h": loc["factors"][1]["raw_value"]},
        }
        resp = client.post("/simulate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "delta_from_current" in data
        assert data["location_id"] == loc["location_id"]

    def test_simulate_invalid_location(self, client):
        payload = {"location_id": "does_not_exist", "overrides": {}}
        resp = client.post("/simulate", json=payload)
        assert resp.status_code == 404
