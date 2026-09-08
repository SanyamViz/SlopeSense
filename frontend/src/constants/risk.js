/**
 * Risk-level constants, palette, and severity ordering for the tactical console.
 * Colours follow the Kinetic Ops design system (Material-inspired tokens).
 */
export const RISK_LEVELS = ["low", "moderate", "high", "severe"];

export const RISK_COLORS = {
  low: "#15803D",       // radiant emerald / operational
  moderate: "#B45309",  // solar amber / advisory
  high: "#EA580C",      // kinetic orange / elevated
  severe: "#DC2626",    // punchy coral crimson / critical
};

export const RISK_LABELS = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
};

export const RISK_SEVERITY = { low: 1, moderate: 2, high: 3, severe: 4 };

export const STATUS_TOKENS = {
  ok: "#00E676",
  warn: "#FF9100",
  crit: "#FF1744",
};

/** Map a numeric score (0-100) to a risk level using API thresholds. */
export function scoreToLevel(score, thresholds) {
  if (thresholds) {
    for (const level of RISK_LEVELS) {
      const [lo, hi] = thresholds[level];
      if (score >= lo && score <= hi) return level;
    }
    if (score > 100) return "severe";
    return "low";
  }
  if (score <= 25) return "low";
  if (score <= 50) return "moderate";
  if (score <= 75) return "high";
  return "severe";
}

export function levelColor(level) {
  return RISK_COLORS[level] || RISK_COLORS.low;
}

/** Factor display names + units for the breakdown bar chart. */
export const FACTOR_META = {
  slope_angle: { label: "Slope angle", unit: "degrees" },
  rainfall_intensity: { label: "Rainfall intensity", unit: "mm/24h" },
  soil_saturation: { label: "Soil saturation", unit: "fraction" },
  historical_proximity: { label: "Historical proximity", unit: "km to event" },
};

export function factorLabel(f) {
  return (FACTOR_META[f] && FACTOR_META[f].label) || f.replace(/_/g, " ");
}
export function factorUnit(f) {
  return (FACTOR_META[f] && FACTOR_META[f].unit) || "";
}