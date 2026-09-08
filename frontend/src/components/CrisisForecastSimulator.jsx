import { useState, useEffect, useCallback, useMemo } from "react";
import { levelColor, RISK_LABELS } from "../constants/risk";
import { fetchSimulate } from "../api/riskClient";

const DEBOUNCE_MS = 300;

/** Crisis Forecast Simulator — sliders + live indicator tiles. */
export default function CrisisForecastSimulator({
  rain,
  soil,
  onRainChange,
  onSoilChange,
  onBaseline,
  onSevere,
  onReset,
  locations,
  selectedId,
}) {
  const [sim, setSim] = useState(null);
  const [loading, setLoading] = useState(false);

  const selectedLocation = useMemo(() => {
    if (!selectedId) return null;
    return (locations || []).find((l) => l.location_id === selectedId) || null;
  }, [locations, selectedId]);

  const runSim = useCallback(async (loc, overrides) => {
    if (!loc) return;
    setLoading(true);
    try {
      const res = await fetchSimulate(loc.location_id, overrides);
      setSim(res);
    } catch (e) {
      setSim(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedLocation) { setSim(null); return; }
    let cancelled = false;
    const id = setTimeout(() => {
      if (cancelled) return;
      runSim(selectedLocation, { rainfall_24h: rain, soil_saturation: soil });
    }, DEBOUNCE_MS);
    return () => { cancelled = true; clearTimeout(id); };
  }, [selectedLocation, rain, soil, runSim]);

  const tiles = useMemo(() => {
    const score = sim?.risk_score;
    const level = sim?.risk_level;
    if (score === undefined || !level) {
      return [
        { key: "danger", value: "—", color: "#DC2626", bg: "#FEF2F2", label: "High/Severe Zones", labelColor: "#991B1B" },
        { key: "cutoff", value: "—", color: "#0284C7", bg: "#E0F2FE", label: "Cut-Off Wards", labelColor: "#0369A1" },
        { key: "priority", value: "—", color: "#0052FF", bg: "#FEF9C3", label: "Priority #1 Target", labelColor: "#003EC7" },
      ];
    }
    const color = levelColor(level);
    const delta = sim?.delta_from_current;
    const deltaStr = delta === undefined || delta === null ? "—" : (delta > 0 ? "+" : "") + delta.toFixed(1);
    return [
      { key: "risk", value: score.toFixed(1), color, bg: color + "1f", label: RISK_LABELS[level]?.toUpperCase() + " RISK", labelColor: color },
      { key: "delta", value: deltaStr, color: delta !== undefined && delta > 0 ? "#DC2626" : "#15803D", bg: (delta !== undefined && delta > 0 ? "#DC2626" : "#15803D") + "1f", label: "Delta vs baseline", labelColor: delta !== undefined && delta > 0 ? "#991B1B" : "#14532D" },
      { key: "sim", value: loading ? "..." : "LIVE", color: "#0052FF", bg: "#EFF6FF", label: selectedLocation ? selectedLocation.name : "Simulating", labelColor: "#003EC7" },
    ];
  }, [sim, loading, selectedLocation]);

  return (
    <section className="simulator-card">
      <div className="sim-head">
        <div>
          <div className="flex items-center gap-2">
            <span className="dot" id="sim-indicator" />
            <h3 className="sim-title">CRISIS FORECAST SIMULATOR</h3>
            <span className="px-2 py-0.5 bg-[#FAF7EE] text-[#0052FF] border border-[#0052FF]/40 text-[9.5px] font-mono-dispatch font-bold uppercase tracking-wider hidden sm:inline-block">
              LIVE DYNAMIC CONTROLLER
            </span>
          </div>
          <p className="sim-sub">
            Drag weather &amp; saturation sliders or click presets to instantly trigger cascading bridge failure &amp; triage reranking across Wayanad.
            {selectedLocation ? <> Simulating <strong>{selectedLocation.name}</strong> against the live scorer.</> : <> Select a map location to simulate its live risk score.</>}
          </p>
        </div>
        <div className="sim-presets">
          <button
            type="button"
            className="px-2.5 py-1 bg-[#FAF7EE] hover:bg-[#F2EBD4] text-[#1C1917] border border-[#1C1917] font-mono-dispatch text-[10.5px] font-bold transition-all shadow-[1px_1px_0_0_#1C1917] active:translate-y-0.5"
            onClick={onBaseline}
          >
            [ Demo: Baseline (15mm) ]
          </button>
          <button
            type="button"
            className="px-2.5 py-1 bg-[#DC2626] hover:bg-[#B91C1C] text-white border border-[#1C1917] font-mono-dispatch text-[10.5px] font-bold transition-all shadow-[1px_1px_0_0_#1C1917] active:translate-y-0.5 flex items-center gap-1"
            onClick={onSevere}
          >
            <span className="material-symbols-outlined text-[12px]">bolt</span>
            [ Severe Storm (+95mm) ]
          </button>
          <button
            type="button"
            className="px-2.5 py-1 bg-[#FAF7EE] border border-[#1C1917] text-[#0052FF] hover:bg-[#EFF6FF] font-sans-editorial text-[10.5px] font-bold transition-colors flex items-center gap-1 shadow-[1px_1px_0_0_#1C1917] active:translate-y-0.5"
            onClick={onReset}
          >
            <span className="material-symbols-outlined text-[13px]">restart_alt</span>Reset
          </button>
        </div>
      </div>
      <div className="sim-grid">
        <div className="sim-controls">
          <div className="sim-card-slider">
            <div className="slider-head">
              <label htmlFor="rain-slider">Rainfall Threshold (6h)</label>
              <span className="slider-val" id="rain-val">+{rain} mm</span>
            </div>
            <input
              id="rain-slider"
              type="range"
              min={0}
              max={128}
              value={rain}
              onInput={(e) => onRainChange(Number(e.target.value))}
            />
            <div className="ruler ruler-tick" />
            <div className="ticks">
              <span>0 mm (Calm)</span>
              <span className="crit">⚠️ +50mm / +80mm Critical</span>
              <span>+128 mm (Peak)</span>
            </div>
          </div>
          <div className="sim-card-slider">
            <div className="slider-head">
              <label htmlFor="soil-slider">Soil Moisture Index</label>
              <span className="slider-val" id="soil-val">+{soil}%</span>
            </div>
            <input
              id="soil-slider"
              type="range"
              min={0}
              max={60}
              value={soil}
              onInput={(e) => onSoilChange(Number(e.target.value))}
            />
            <div className="ruler ruler-tick" />
            <div className="ticks">
              <span>0% (Dry)</span>
              <span className="crit">+28% Slump / +40% Critical</span>
              <span>+60% (Saturated)</span>
            </div>
          </div>
        </div>
        <div className="sim-card-tiles">
          {tiles.map((t) => (
            <div key={t.key} className="sim-tile" style={{ background: t.bg }}>
              <span className="tile-num" style={{ color: t.color }}>
                {t.value}
              </span>
              <span className="tile-label" style={{ color: t.labelColor }}>
                {t.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}