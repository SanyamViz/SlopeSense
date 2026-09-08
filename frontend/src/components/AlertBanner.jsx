import { levelColor, RISK_LABELS, RISK_LEVELS } from "../constants/risk";

/** Top banner listing currently active High/Severe alerts. */
export default function AlertBanner({ locations, rankMode = "risk" }) {
  const alerts = locations
    .filter((l) => l.risk_level === "high" || l.risk_level === "severe")
    .sort((a, b) => {
      const av = rankMode === "priority" ? (a.priority_score ?? 0) : a.risk_score;
      const bv = rankMode === "priority" ? (b.priority_score ?? 0) : b.risk_score;
      if (bv !== av) return bv - av;
      return (b.risk_level > a.risk_level ? 1 : -1);
    });

  if (alerts.length === 0) {
    return (
      <div className="alert-banner empty">
        <span className="alert-dot ok" />
        <span>No active high/severe alerts. All locations nominal.</span>
      </div>
    );
  }

  return (
    <div className="alert-banner">
      <div className="alert-head">
        <span className="alert-dot pulse" />
        <span className="alert-title">
          ACTIVE ALERTS — {alerts.length} location{alerts.length === 1 ? "" : "s"} at HIGH/SEVERE
        </span>
        <span className="alert-sub">Sorted by severity · threshold 51+</span>
      </div>
      <div className="alert-list">
        {alerts.map((a) => (
          <a
            key={a.location_id}
            className="alert-item"
            href={`#${a.location_id}`}
            style={{ borderLeftColor: levelColor(a.risk_level) }}
          >
            <span className="alert-sev" style={{ background: levelColor(a.risk_level) }}>
              {a.risk_level.toUpperCase()}
            </span>
            <span className="alert-name">
              {a.name}{" "}
              <em className="alert-district">{a.district}</em>
            </span>
            <span className="alert-score" style={{ color: levelColor(a.risk_level) }}>
              {a.risk_score.toFixed(0)}
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}