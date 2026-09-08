"""Generate a synthetic historical alert-accuracy dataset for the trust score.

For each of the 142 villages (matching generate_sample_data.py's location_id
space, loc_000..loc_141) we synthesize 4-8 historical alert records spanning
the past ~2 years. Each record carries a predicted_risk_level and an
actual_outcome; predictions are loosely correlated with outcomes so most
zones look well-calibrated, but a deliberate minority (~15-20%) are seeded
with poor accuracy. That minority is what makes the
"consider secondary confirmation" nudge fire during the demo.

RNG seeding pattern mirrors generate_sample_data.py (np.random.default_rng(42))
so the dataset is reproducible. The WAYANAD_2024_VAL anchor is intentionally
NOT synthesized here -- pipeline.py injects a hand-authored high-confidence
history for it instead.
"""
import numpy as np
import pandas as pd

from config import SAMPLE_DATA_DIR

# Same seed as generate_sample_data.py for reproducible synthetic data.
RNG = np.random.default_rng(42)

N_VILLAGES = 142

# Risk levels, lowest -> highest. Band-matching rule (see trust_score.py):
#   predicted low/moderate  -> correct if actual in {none, minor}
#   predicted high/severe   -> correct if actual in {moderate, severe}
PREDICTED_LEVELS = ["low", "moderate", "high", "severe"]
ACTUAL_OUTCOMES = ["none", "minor", "moderate", "severe"]

# Approximate 2-year lookback window, ending just before the current run.
# (The pipeline stamps data_freshness with datetime.now, so a fixed historical
# window keeps the demo deterministic regardless of when it is run.)
START_DATE = pd.Timestamp("2024-09-01")
END_DATE = pd.Timestamp("2026-09-01")

# --- Accuracy seeding -------------------------------------------------------
# ~15-20% of zones are deliberately miscalibrated. We pick the indices by a
# deterministic pseudo-random draw so the set is stable across runs.
N_POOR = int(round(0.18 * N_VILLAGES))  # ~26 zones
POOR_INDICES = set(RNG.choice(N_VILLAGES, size=N_POOR, replace=False).tolist())

# For well-calibrated zones: probability the prediction lands in the "correct"
# band is high. For poor zones: it is low (they are systematically over- or
# under-forecast).
P_CORRECT_GOOD = 0.80
P_CORRECT_POOR = 0.35


def _calibrated_outcome(predicted: str, well_calibrated: bool) -> str:
    """Sample an actual_outcome loosely correlated with the prediction.

    Band-matching definition of "correct":
      predicted low/moderate  -> actual none/minor
      predicted high/severe   -> actual moderate/severe
    """
    p_correct = P_CORRECT_GOOD if well_calibrated else P_CORRECT_POOR
    if RNG.random() < p_correct:
        # Stay inside the matching band.
        if predicted in ("low", "moderate"):
            return RNG.choice(["none", "minor"])
        return RNG.choice(["moderate", "severe"])
    # Drift outside the matching band. Bias the drift direction so poor zones
    # look *systematically* off (e.g. over-forecasting), which is more
    # realistic than random noise and makes the trust score visibly low.
    if predicted in ("low", "moderate"):
        # Over-forecast: actual was worse than predicted.
        return RNG.choice(["moderate", "severe"], p=[0.7, 0.3])
    # Under-forecast: actual was milder than predicted.
    return RNG.choice(["none", "minor"], p=[0.7, 0.3])


def _random_date(rng: np.random.Generator) -> pd.Timestamp:
    span = (END_DATE - START_DATE).days
    return START_DATE + pd.Timedelta(days=int(rng.integers(0, span + 1)))


def generate():
    SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(N_VILLAGES):
        well_calibrated = i not in POOR_INDICES
        # 4-8 historical alerts per zone.
        n_alerts = int(RNG.integers(4, 9))  # 4..8 inclusive
        for _ in range(n_alerts):
            predicted = RNG.choice(PREDICTED_LEVELS)
            actual = _calibrated_outcome(predicted, well_calibrated)
            rows.append({
                "zone_id": f"loc_{i:03d}",
                "date": _random_date(RNG).strftime("%Y-%m-%d"),
                "predicted_risk_level": predicted,
                "actual_outcome": actual,
            })

    df = pd.DataFrame(rows, columns=[
        "zone_id", "date", "predicted_risk_level", "actual_outcome",
    ])
    df = df.sort_values(["zone_id", "date"]).reset_index(drop=True)
    df.to_csv(SAMPLE_DATA_DIR / "alert_history.csv", index=False)

    # Quick self-report so the calibration split is visible at a glance.
    n_good = N_VILLAGES - len(POOR_INDICES)
    print(f"Generated {len(df)} historical alert records for {N_VILLAGES} villages "
          f"({n_good} well-calibrated, {len(POOR_INDICES)} deliberately poor) "
          f"in {SAMPLE_DATA_DIR / 'alert_history.csv'}")


if __name__ == "__main__":
    generate()