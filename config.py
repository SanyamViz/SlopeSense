"""Central configuration for the landslide risk pipeline.

HACKATHON NOTE: This is a prototype. All tunable constants (weights, thresholds,
normalization reference ranges, paths) live here so they can be changed without
touching pipeline logic. Swap real dataset paths into `inputs` to run on real data.
"""
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"
REAL_DATA_DIR = BASE_DIR / "real_data"

# --- Alert-trust scoring ---------------------------------------------------
# A zone's historical alert accuracy below this fraction is treated as
# low-confidence and surfaced with a "consider secondary confirmation" nudge.
TRUST_LOW_CONFIDENCE_THRESHOLD = 0.6

# data_freshness timestamps are set dynamically at pipeline run time.
# The config default here is a fallback; pipeline.py overwrites
# rainfall_data_timestamp with datetime.now(timezone.utc).isoformat() on each run.
CURRENT_RUN_TIMESTAMP = lambda: datetime.now(timezone.utc).isoformat()

CONFIG = {
    "model_version": "weighted-v1.0",

    # --- Configurable factor weights. These MUST sum to 1.0. ---
    # They are deliberately exposed as named constants (no magic numbers inline).
    "weights": {
        "slope_angle": 0.35,
        "rainfall_intensity": 0.30,
        "soil_saturation": 0.20,
        "historical_proximity": 0.15,
    },

    # --- Risk classification thresholds on the 0-100 score ---
    # Expressed as [low_bound, high_bound] inclusive pairs, matching the output schema.
    "risk_thresholds": {
        "low": [0, 25],
        "moderate": [26, 50],
        "high": [51, 75],
        "severe": [76, 100],
    },

    # --- Per-factor normalization reference curves.
    # Each factor converts a raw physical value into a [0,1] hazard fraction using
    # piecewise-linear breakpoints (x=raw, y=normalized). Directionality is encoded
    # in the breakpoints themselves, so no separate "invert" flag is needed.
    "normalization": {
        "slope_angle": {
            "unit": "degrees",
            "breakpoints": [(0, 0.0), (15, 0.2), (30, 0.5), (35, 0.75), (45, 0.95), (60, 1.0)],
            "notes": {
                "critical": 35.0,  # ASSUMPTION: >35 deg is treated as critical (USGS trigger zone)
            },
        },
        "rainfall_intensity": {
            "unit": "mm/24hr",
            "breakpoints": [(0, 0.0), (25, 0.2), (50, 0.4), (75, 0.6), (100, 0.8), (150, 1.0)],
            "cumulative_window_days": 7,
            "cumulative_threshold_mm": 200,  # ASSUMPTION: 200mm over 7 days considered elevated
        },
        "soil_saturation": {
            "unit": "fraction_saturated",
            "breakpoints": [(0.0, 0.0), (0.3, 0.2), (0.5, 0.4), (0.7, 0.7), (0.85, 0.9), (1.0, 1.0)],
        },
        "historical_proximity": {
            "unit": "km_to_nearest_past_event",
            "breakpoints": [(0, 1.0), (1, 0.8), (3, 0.5), (5, 0.3), (10, 0.15), (20, 0.0)],
            "nearby_radius_km": 5.0,  # used only for the human-readable note
        },
    },

    # --- Vulnerability layer weights (composite 0-1 score) ---
    # VALUE JUDGEMENT: a village's exposure to harm is a separate axis from the
    # physical hazard. Population drives the raw headcount of people at risk;
    # facilities (hospitals + schools) proxy for evacuation capacity and
    # community resilience -- fewer facilities means more vulnerable; elderly
    # share captures the demographic least able to self-evacuate. Weights sum
    # to 1.0 and are deliberately exposed as named constants.
    "vulnerability_weights": {
        "population": 0.40,
        "facilities": 0.35,
        "elderly_pct": 0.35,
    },

    # --- Priority weights: how raw hazard risk and vulnerability combine ---
    # VALUE JUDGEMENT: response priority is NOT raw risk. A 0.6/0.4 blend
    # means a moderately hazardous village with many vulnerable people can
    # outrank a steep-but-empty one. Risk dominates (so the physics are not
    # washed out) but vulnerability is a meaningful, independent second axis.
    # This is a defensible default for a resource-constrained first-response
    # setting; adjust toward 0.5/0.5 if equity is the stated priority.
    "priority_weights": {
        "risk": 0.6,
        "vulnerability": 0.4,
    },

    # --- Per-factor vulnerability normalization curves.
    # Same piecewise-linear primitive as the hazard normalisation above.
    # Directionality is encoded in the breakpoints: higher raw value =>
    # higher vulnerability by construction (facilities are inverted in
    # vulnerability.py so 0 facilities => vulnerability 1.0).
    "normalization_vulnerability": {
        "population": {
            "unit": "people",
            # Saturation: tiny hamlets score ~0, large towns plateau at 1.0.
            "breakpoints": [(0, 0.0), (500, 0.15), (2000, 0.45), (5000, 0.7),
                            (10000, 0.9), (30000, 1.0)],
        },
        "facilities": {
            "unit": "hospitals + schools",
            # Breakpoints are on facility SUPPLY; vulnerability.py inverts.
            "breakpoints": [(0, 0.0), (1, 0.35), (2, 0.6), (3, 0.8), (5, 1.0)],
        },
        "elderly_pct": {
            "unit": "percent_of_population_65plus",
            "breakpoints": [(0, 0.0), (5, 0.15), (10, 0.35), (15, 0.6),
                            (20, 0.85), (30, 1.0)],
        },
    },

    # --- Per-factor danger thresholds surfaced in alert explanation copy ---
    # These are the defensible reference numbers the explanation text quotes
    # (e.g. "7-day rainfall has reached X mm, well above the Y mm safety
    # margin"). They live here -- not hardcoded inside alert_generator.py --
    # so the copy always agrees with the normalisation layer's assumptions.
    "alert_thresholds": {
        "slope_angle": {
            "danger_deg": 35.0,
            "note": "Slopes steeper than this are treated as critical (USGS trigger zone).",
        },
        "rainfall_intensity": {
            "rainfall_7d_danger_mm": 250.0,
            "rainfall_24h_danger_mm": 150.0,
            "note": "7-day cumulative above this level is considered a deep-seated "
                    "failure trigger; 24h total above the secondary limit is "
                    "treated as an intense short-duration event.",
        },
        "soil_saturation": {
            "saturation_danger_frac": 0.85,
            "note": "Soil at/above this saturation fraction is considered waterlogged "
                    "enough to destabilise slopes.",
        },
        "historical_proximity": {
            "nearby_radius_km": 5.0,
            "note": "Events within this radius are considered 'nearby' for the alert "
                    "explanation and the historical-proximity normalisation.",
        },
    },

    # --- Spatial alignment ---
    "spatial": {
        # Master layer is the village/district point set. All other datasets are
        # snapped to it by NEAREST-NEIGHBOUR spatial join within this tolerance.
        # ASSUMPTION: 0.05 degrees (~5.5 km at the equator) is a sensible max
        # snap distance for a prototype; tune per region (1 deg ~ 111 km latitude).
        "join_tolerance_deg": 0.05,
        "crs": "EPSG:4326",
    },

    # --- Data-freshness metadata surfaced in the output ---
    # rainfall_data_timestamp is set dynamically at pipeline run time
    # (pipeline.py overwrites this with datetime.now(timezone.utc).isoformat()).
    # The value below is a config-level fallback only.
    "data_freshness": {
        "rainfall_data_timestamp": datetime.now(timezone.utc).isoformat(),
        "soil_data_source": "static_survey_2023",
    },

    # --- Dataset file paths (point at real files to swap in real data) ---
    "inputs": {
        "points": SAMPLE_DATA_DIR / "villages.geojson",
        "slope": SAMPLE_DATA_DIR / "slope.csv",
        "rainfall": SAMPLE_DATA_DIR / "rainfall.csv",
        "soil": SAMPLE_DATA_DIR / "soil.csv",
        "historical_events": SAMPLE_DATA_DIR / "historical_landslides.geojson",
        "alert_history": SAMPLE_DATA_DIR / "alert_history.csv",
        "vulnerability": SAMPLE_DATA_DIR / "vulnerability.csv",
    },

    # --- Real-data pipeline inputs (populated by prepare_real_data.py) ---
    # Swap these into `inputs` above to run on real data instead of synthetic
    # sample_data/.  Missing files fall back to sample_data/ at pipeline runtime.
    "real_data_inputs": {
        "points": REAL_DATA_DIR / "villages.geojson",
        "slope": REAL_DATA_DIR / "slope.csv",
        "rainfall": REAL_DATA_DIR / "rainfall.csv",
        "soil": REAL_DATA_DIR / "soil.csv",
        "historical_events": REAL_DATA_DIR / "historical_landslides.geojson",
        "terrain": REAL_DATA_DIR / "terrain.csv",
    },

    # --- ML model artifact path (RandomForest trained on GLC schema) ---
    "ml_model_path": REAL_DATA_DIR / "models" / "ml_model.pkl",

    "output": BASE_DIR / "landslide_risk_output.json",

    # --- Explainability logging ---
    "log_file": BASE_DIR / "pipeline.log",
}
