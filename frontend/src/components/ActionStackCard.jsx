import { levelColor, RISK_LABELS, factorLabel } from "../constants/risk";

/** Priority Action Stack card with integrated ground advisory lockup. */
export default function ActionStackCard({ rows, advisory, isSevere, onDispatch, className }) {
  return (
    <section className={`action-stack-card ${className || ""}`}>
      <div className="card-head">
        <h2 className="card-title">
          <span className="dot" />PRIORITY ACTION STACK
        </h2>
        <span className="stack-badge">TOP CRITICAL</span>
      </div>
      <div className="priority-stack">
        {rows.map((r) => (
          <div key={r.id} className={`priority-row rank-${r.rank}`}>
            <div className="pr-top">
              <div className="flex items-baseline gap-2">
                <span className="pr-rank">{r.rank}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="flex items-center">
                    <span className="pr-name">{r.name}</span>
                    {r.urgencyTag && (
                      <span className="pr-urgency-tag" style={r.urgencyTagStyle}>
                        {r.urgencyTag}
                      </span>
                    )}
                  </div>
                  <span className="pr-sub">{r.subtitle}</span>
                  {r.localAlert && (
                    <div className="pr-vernacular">
                      <span className="pr-vernacular-icon material-symbols-outlined">volume_up</span>
                      <span className="pr-vernacular-text">{r.localAlert}</span>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex flex-col items-end gap-0.5 shrink-0">
                <span
                  className="pr-status-pill"
                  style={{
                    background: r.statusBg,
                    color: r.statusColor,
                    border: `1px solid ${r.statusColor}`,
                  }}
                >
                  {r.status}
                </span>
                <span
                  className="pr-risk-pill"
                  style={{
                    background: r.riskBg,
                    color: r.riskColor,
                    border: `1px solid ${r.riskColor}`,
                  }}
                >
                  {r.riskLabel}
                </span>
              </div>
            </div>
            {r.factors && r.factors.length > 0 && (
              <div className="pr-factors">
                <div className="pr-factors-head">
                  <span className="pr-factors-title">Risk factors</span>
                  <span className="pr-factors-sub">Top contributors</span>
                </div>
                {r.factors.map((f, i) => {
                  const maxContrib = 100;
                  const pct = Math.min(Math.max(f.contribution, 0), 100);
                  return (
                    <div key={f.factor} className="pr-factor-row">
                      <span className="pr-factor-label">{factorLabel(f.factor)}</span>
                      <div className="pr-factor-track">
                        <div
                          className="pr-factor-fill"
                          style={{
                            width: `${pct}%`,
                            background: i === 0 ? "#DC2626" : i === 1 ? "#EA580C" : i === 2 ? "#B45309" : "#0052FF",
                          }}
                        />
                      </div>
                      <span className="pr-factor-pct">{pct.toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="pr-trust">
              <span className="trust-val" style={{ color: r.trustColor }}>
                Trust Score: <strong>{r.trustText}</strong>
              </span>
              <span
                className="trust-badge"
                style={{
                  background: r.trustBadgeBg,
                  color: r.trustBadgeColor,
                  border: `1px solid ${r.trustBadgeColor}`,
                }}
              >
                {r.trustBadge}
              </span>
            </div>
            <div className="pr-foot">
              <span
                className="road-status"
                style={{ color: r.roadColor }}
              >
                <span className="dot" />{r.roadStatus}
              </span>
              <button
                type="button"
                className="px-2.5 py-1 bg-[#0052FF] hover:bg-[#003EC7] text-white font-sans-editorial text-[10px] font-bold uppercase border border-[#1C1917] flex items-center gap-1 shadow-[1.5px_1.5px_0_0_#1C1917] transition-all cursor-pointer"
                onClick={() => onDispatch(r.id)}
              >
                <span className="material-symbols-outlined text-[13px]">cell_tower</span>
                DISPATCH SIREN
              </button>
            </div>
          </div>
        ))}
      </div>
      {advisory && (
        <div className="advisory-lockup">
          <div className="adv-head">
            <span className="adv-title">CRITICAL GROUND ADVISORY</span>
            <span className="adv-dot" />
          </div>
          <div className="adv-reliability">
            <span>
              <span className="rel-val" style={{ color: advisory.relColor }}>
                ALERT RELIABILITY: {advisory.relPct}
              </span>{" "}
              ({advisory.relNote})
            </span>
            <span
              className="rel-badge"
              style={{
                background: advisory.relBadgeBg,
                color: advisory.relBadgeColor,
                border: `1px solid ${advisory.relBadgeColor}`,
              }}
            >
              {advisory.relBadge}
            </span>
          </div>
          <p className="adv-en">{advisory.en}</p>
          <div className="adv-foot">
            <span className="vhf">VHF RELAY CH: 156.800 MHz</span>
            <span className="armed">ALL REPEATERS ARMED</span>
          </div>
        </div>
      )}
    </section>
  );
}
