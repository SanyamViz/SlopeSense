import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSimulate, fetchConfig } from "../api/riskClient";
import { levelColor, RISK_LABELS } from "../constants/risk";

const SLIDER_KEYS = ["slope_angle", "rainfall_24h", "rainfall_7d", "soil_saturation"];

const SLIDER_META = {
  slope_angle: { label: "Slope angle", unit: "degrees", step: 1, max: 60 },
  rainfall_24h: { label: "Rainfall (24h)", unit: "mm", step: 1, max: 150 },
  rainfall_7d: { label: "Rainfall (7d)", unit: "mm", step: 1, max: 500 },
  soil_saturation: { label: "Soil saturation", unit: "fraction", step: 0.01, max: 1 },
};

export default function WhatIfPanel({ location, onClose }) {
  const [cfg, setCfg] = useState(null);
  const [sliders, setSliders] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetchConfig()
      .then((c) => { if (!cancelled) setCfg(c); })
      .catch(() => { if (!cancelled) setError("Failed to load simulation config"); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!location) return;
    const initial = {};
    for (const f of location.factors || []) {
      if (f.factor === "rainfall_intensity") {
        initial.rainfall_24h = f.raw_value;
        initial.rainfall_7d = f.raw_value_7d ?? f.raw_value;
      } else if (f.factor === "historical_proximity") {
        initial.proximity_to_event_km = f.raw_value;
      } else {
        initial[f.factor] = f.raw_value;
      }
    }
    for (const k of SLIDER_KEYS) if (!(k in initial)) initial[k] = 0;
    setSliders(initial);
    setResult(null);
    setError(null);
  }, [location]);

  const runSimulation = useCallback(async (values) => {
    if (!location) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSimulate(location.location_id, values);
      setResult(res);
    } catch (e) {
      setError(e.message || "Simulation failed");
      setResult(null);
    } finally { setLoading(false); }
  }, [location]);

  const handleSliderChange = (key, rawValue) => {
    const value = Number(rawValue);
    const next = { ...sliders, [key]: value };
    setSliders(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { runSimulation(next); }, 300);
  };

  if (!location) return null;

  const originalScore = location.risk_score;
  const originalLevel = location.risk_level;
  const newScore = result?.risk_score;
  const newLevel = result?.risk_level;
  const delta = result?.delta_from_current;

  return (
    <div className="whatif-panel">
      <div className="whatif-header">
        <h3>What-If Scenario</h3>
        <button className="whatif-close" onClick={onClose} type="button">×</button>
      </div>
      <p className="whatif-sub">
        Adjust factors for <strong>{location.name}</strong> and see the live re-score.
      </p>
      {error && <div className="whatif-error">{error}</div>}
      <div className="whatif-sliders">
        {SLIDER_KEYS.map((key) => {
          const meta = SLIDER_META[key];
          const current = sliders[key] ?? 0;
          let max = meta.max;
          if (cfg?.normalization?.[key]?.breakpoints?.length) {
            max = Math.max(...cfg.normalization[key].breakpoints.map((b) => b[0]));
          }
          return (
            <div key={key} className="whatif-slider-row">
              <label className="whatif-slider-label">
                <span>{meta.label}</span>
                <span className="whatif-slider-value">
                  {typeof current === "number" && meta.step < 1 ? current.toFixed(2) : current} {meta.unit}
                </span>
              </label>
              <input
                type="range"
                min={0}
                max={max}
                step={meta.step}
                value={current}
                onChange={(e) => handleSliderChange(key, e.target.value)}
                className="whatif-range"
              />
            </div>
          );
        })}
      </div>
      <div className="whatif-divider" />
      <div className="whatif-result">
        <div className="whatif-compare">
          <div className="whatif-col">
            <span className="whatif-col-label">Original</span>
            <span className="whatif-badge" style={{ color: levelColor(originalLevel), background: `${levelColor(originalLevel)}1f` }}>
              {RISK_LABELS[originalLevel]?.toUpperCase()}
            </span>
            <span className="whatif-score">{originalScore.toFixed(1)}<span className="whatif-score-max">/ 100</span></span>
          </div>
          <div className="whatif-arrow">{loading ? <span className="spinner" /> : "→"}</div>
          <div className="whatif-col">
            <span className="whatif-col-label">Simulated</span>
            {newLevel ? (
              <span className="whatif-badge" style={{ color: levelColor(newLevel), background: `${levelColor(newLevel)}1f` }}>
                {RISK_LABELS[newLevel]?.toUpperCase()}
              </span>
            ) : (
              <span className="whatif-badge whatif-badge-muted">—</span>
            )}
            {newScore !== undefined && newScore !== null ? (
              <span className="whatif-score">{newScore.toFixed(1)}<span className="whatif-score-max">/ 100</span></span>
            ) : (
              <span className="whatif-score whatif-score-muted">—</span>
            )}
          </div>
        </div>
        {delta !== undefined && delta !== null && (
          <div className={`whatif-delta ${delta > 0 ? "whatif-delta-worse" : delta < 0 ? "whatif-delta-better" : "whatif-delta-neutral"}`}>
            {delta > 0 ? "▲" : delta < 0 ? "▼" : "="} {delta > 0 ? "+" : ""}{delta.toFixed(1)} &nbsp;{originalLevel} → {newLevel}
          </div>
        )}
      </div>
    </div>
  );
}