"""Tests for alert_generator.py -- explanations must be data-grounded.

Acceptance: two locations with different top_factor values must produce
explanation text that names different specific numbers (not just a different
risk-level adjective).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alert_generator import generate_alert


def _factor(factor, raw, contribution, raw_value_7d=None):
    entry = {
        "factor": factor,
        "raw_value": raw,
        "unit": "",
        "normalized_value": 0.0,
        "weight": 0.0,
        "contribution": contribution,
        "note": "",
    }
    if raw_value_7d is not None:
        entry["raw_value_7d"] = raw_value_7d
    return entry


class TestAlertGenerator(unittest.TestCase):
    def test_rainfall_and_slope_explanations_name_different_numbers(self):
        """Two locations with different top_factor must quote different numbers."""
        rainfall_factors = [
            _factor("rainfall_intensity", 105.9, 50.00, raw_value_7d=289.79),
            _factor("slope_angle", 42.69, 31.63),
            _factor("soil_saturation", 0.4262, 6.52),
            _factor("historical_proximity", 33.675, 0.0),
        ]
        slope_factors = [
            _factor("slope_angle", 42.69, 50.00),
            _factor("rainfall_intensity", 66.66, 16.00, raw_value_7d=180.0),
            _factor("soil_saturation", 0.4973, 7.95),
            _factor("historical_proximity", 24.652, 0.0),
        ]

        rain = generate_alert(37.22, "moderate", rainfall_factors, "Village 1")
        slope = generate_alert(55.58, "high", slope_factors, "Village 3")

        # Both must name their raw numbers (not be a static string).
        self.assertIn("105.9", rain["explanation"])
        self.assertIn("289.8", rain["explanation"])
        self.assertIn("42.7", slope["explanation"])
        self.assertIn("35.0", slope["explanation"])

        # The two explanations must differ in their specific numbers.
        self.assertNotEqual(rain["explanation"], slope["explanation"])
        self.assertNotEqual(rain["explanation_hi"], slope["explanation_hi"])

        # Same template structure, translated: EN rainfall case quotes "mm".
        self.assertIn("mm", rain["explanation_hi"])

    def test_soil_saturation_explanation_uses_percentage(self):
        factors = [
            _factor("soil_saturation", 0.8636, 50.00),
            _factor("rainfall_intensity", 44.51, 13.21, raw_value_7d=120.0),
            _factor("slope_angle", 6.47, 3.02),
            _factor("historical_proximity", 11.297, 1.96),
        ]
        alert = generate_alert(36.37, "moderate", factors, "Village 2")
        self.assertIn("86.4", alert["explanation"])
        self.assertIn("85.0", alert["explanation"])
        self.assertIn("86.4", alert["explanation_hi"])

    def test_historical_proximity_inside_radius(self):
        factors = [
            _factor("historical_proximity", 0.0, 50.00),
            _factor("slope_angle", 46.76, 33.46),
            _factor("rainfall_intensity", 111.86, 30.00, raw_value_7d=300.0),
            _factor("soil_saturation", 0.8024, 16.73),
        ]
        alert = generate_alert(95.19, "severe", factors, "Village 73")
        self.assertIn("0.0", alert["explanation"])
        self.assertIn("within the 5.0", alert["explanation"])
        self.assertIn("5.0 km", alert["explanation_hi"])

    def test_historical_proximity_outside_radius(self):
        factors = [
            _factor("historical_proximity", 15.962, 50.00),
            _factor("slope_angle", None, 0.0),
            _factor("rainfall_intensity", None, 0.0, raw_value_7d=None),
            _factor("soil_saturation", None, 0.0),
        ]
        alert = generate_alert(0.91, "low", factors, "Meppadi")
        self.assertIn("16.0", alert["explanation"])
        self.assertIn("outside the 5.0", alert["explanation"])

    def test_unknown_factor_falls_back_gracefully(self):
        factors = [
            {"factor": "weird_factor", "raw_value": 1.0, "unit": "",
             "normalized_value": 0.0, "weight": 0.0, "contribution": 5.0, "note": ""},
            _factor("slope_angle", 42.0, 31.15),
            _factor("rainfall_intensity", 204.5, 30.00, raw_value_7d=573.1),
            _factor("soil_saturation", 1.0, 20.0),
            _factor("historical_proximity", 0.0, 15.0),
        ]
        alert = generate_alert(96.15, "severe", factors, "Mundakkai")
        self.assertTrue(alert["explanation"])  # non-empty fallback


if __name__ == "__main__":
    unittest.main()