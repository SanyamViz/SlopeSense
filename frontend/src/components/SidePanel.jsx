import { levelColor, RISK_LABELS, factorLabel, factorUnit } from "../constants/risk";

function BarChart({ factors }) {
  if (!factors || factors.length === 0) return <div className="chart-empty">No factor data available.</div>;
  const max = Math.max(...factors.map((f) => f.contribution), 1);
  const chartW = 320, rowH = 30, padL = 110, padR = 54, barW = chartW - padL - padR;
  const height = factors.length * rowH + 8;
  return (
    <svg className="bar-chart" viewBox={`0 0 ${chartW} ${height}`} width="100%" height={height} role="img" aria-label="Risk factor contribution breakdown">
      {factors.map((f, i) => {
        const y = i * rowH + 6;
        const w = (f.contribution / max) * barW;
        return (
          <g key={f.factor}>
            <text x={padL - 8} y={y + 12} textAnchor="end" className="bar-label">{factorLabel(f.factor)}</text>
            <rect x={padL} y={y - 10} width={w} height={16} rx={3} fill="#0052FF" opacity={0.92} />
            <text x={padL + w + 6} y={y + 2} className="bar-value">{f.contribution.toFixed(1)}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function SidePanel({ location, riskRank, priorityRank, rankMode = "priority", onOpenWhatIf }) {
  if (!location) {
    return (
      <div className="panel empty">
        <div className="panel-icon">◎</div>
        <p>No location selected.</p>
        <p className="panel-hint">Click a marker on the map to inspect its risk breakdown.</p>
      </div>
    );
  }
  const level = location.risk_level;
  const color = levelColor(level);
  const trust = location.trust_score || null;
  const vuln = location.vulnerability || null;
  return (
    <div className="panel">
      <header className="panel-head">
        <div>
          <span className="panel-id">{location.location_id}</span>
          <h2 className="panel-name">{location.name}</h2>
          <span className="panel-district">{location.district}</span>
        </div>
        <div className="panel-level-col">
          <span className="panel-level" style={{ color, background: `${color}1f` }}>{RISK_LABELS[level].toUpperCase()}</span>
          {trust && (
            <span className="panel-trust">
              past accuracy: {trust.accuracy_pct.toFixed(0)}%{" "}
              <span className="panel-trust-count">({trust.correct_count}/{trust.total_count})</span>
            </span>
          )}
        </div>
      </header>
      {trust?.low_confidence && trust.confidence_note && (
        <div className="trust-nudge">
          <span className="trust-nudge-dot" aria-hidden="true" />
          <span className="trust-nudge-text">{trust.confidence_note}</span>
        </div>
      )}
      <section className="panel-score">
        <span className="panel-score-label">Risk score</span>
        <span className="panel-score-value" style={{ color }}>{location.risk_score.toFixed(1)}</span>
        <span className="panel-score-max">/ 100</span>
      </section>
      <section className="panel-score priority">
        <span className="panel-score-label">Response priority</span>
        <span className="panel-score-value" style={{ color: "#0052FF" }}>{(location.priority_score ?? 0).toFixed(1)}</span>
        <span className="panel-score-max">/ 100</span>
      </section>
      {vuln && (
        <section className="panel-section vulnerability">
          <h3>Vulnerability — who is here</h3>
          <div className="vuln-grid">
            <div className="vuln-cell"><span className="vuln-value">{vuln.population}</span><span className="vuln-label">population</span></div>
            <div className="vuln-cell"><span className="vuln-value">{vuln.num_hospitals}</span><span className="vuln-label">hospitals</span></div>
            <div className="vuln-cell"><span className="vuln-value">{vuln.num_schools}</span><span className="vuln-label">schools</span></div>
            <div className="vuln-cell"><span className="vuln-value">{vuln.elderly_pct}%</span><span className="vuln-label">elderly</span></div>
          </div>
          <p className="panel-note">Vulnerability score {vuln.vulnerability_score.toFixed(3)} (0-1).</p>
        </section>
      )}
      <section className="panel-section">
        <h3>Contributing factors</h3>
        <BarChart factors={location.factors} />
      </section>
      <section className="panel-section">
        <h3>Alert message</h3>
        <div className="alert-msg en"><span className="alert-lang-tag">EN</span><p>{location.alert?.message_en || "—"}</p></div>
        <div className="alert-msg local"><span className="alert-lang-tag">LOCAL</span><p>{location.alert?.message_local || location.alert?.message_en || "—"}</p></div>
      </section>
      <section className="panel-section">
        <h3>Explanation</h3>
        <div className="alert-msg en"><span className="alert-lang-tag">EN</span><p>{location.alert?.explanation || "—"}</p></div>
        <div className="alert-msg local"><span className="alert-lang-tag">LOCAL</span><p>{location.alert?.explanation_hi || "—"}</p></div>
      </section>
      <section className="panel-section">
        <h3>Recommended action</h3>
        <p className="panel-action">{location.alert?.recommended_action || "—"}</p>
      </section>
      {onOpenWhatIf && (
        <button className="whatif-trigger" type="button" onClick={onOpenWhatIf}>Run What-If Scenario</button>
      )}
      <footer className="panel-foot">
        <span>Rainfall data: <em>{location.data_freshness?.rainfall_data_timestamp || "—"}</em></span>
        <span>Soil source: <em>{location.data_freshness?.soil_data_source || "—"}</em></span>
      </footer>
    </div>
  );
}
