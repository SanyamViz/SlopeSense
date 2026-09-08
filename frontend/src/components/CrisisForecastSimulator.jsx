import { levelColor, RISK_LABELS } from "../constants/risk";

/** Crisis Forecast Simulator — sliders + live indicator tiles. */
export default function CrisisForecastSimulator({
  rain,
  soil,
  onRainChange,
  onSoilChange,
  onBaseline,
  onSevere,
  onReset,
  tiles,
}) {
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