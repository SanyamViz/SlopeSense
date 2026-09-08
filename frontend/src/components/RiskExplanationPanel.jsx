import { useState, useMemo } from "react";
import { factorLabel } from "../constants/risk";

export default function RiskExplanationPanel({ factors }) {
  const [open, setOpen] = useState(false);
  const sorted = useMemo(
    () =>
      (factors || [])
        .slice()
        .sort((a, b) => (b.contribution ?? 0) - (a.contribution ?? 0)),
    [factors]
  );

  const toggle = () => setOpen((v) => !v);
  const onKey = (e) => {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      toggle();
    }
  };

  return (
    <section className="panel-section risk-explanation">
      <header
        className="risk-exp-head"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-controls="risk-exp-body"
        onClick={toggle}
        onKeyDown={onKey}
      >
        <h3>Explain this risk score</h3>
        <span
          className={`risk-exp-chevron ${open ? "risk-exp-chevron-open" : ""}`}
          aria-hidden="true"
        >
          ▾
        </span>
      </header>
      <div
        id="risk-exp-body"
        className={`risk-exp-body ${open ? "risk-exp-body-open" : ""}`}
        aria-hidden={!open}
      >
        {sorted.length === 0 ? (
          <p className="risk-exp-empty">No factor explanations available for this location.</p>
        ) : (
          <ul className="risk-exp-list" role="list">
            {sorted.map((f) => {
              const contribution = Number(f.contribution ?? 0);
              const pct = contribution > 100 ? 100 : contribution < 0 ? 0 : contribution;
              const note = f.note || "";
              return (
                <li key={f.factor} className="risk-exp-row">
                  <div className="risk-exp-row-top">
                    <span className="risk-exp-name" title={factorLabel(f.factor)}>
                      {factorLabel(f.factor)}
                    </span>
                    <div className="risk-exp-track-wrap">
                      <div className="risk-exp-track">
                        <div className="risk-exp-bar" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                    <span className="risk-exp-val">{contribution.toFixed(1)}/100</span>
                  </div>
                  <div className="risk-exp-row-bottom">
                    <span className="risk-exp-note" title={note}>
                      {note || "—"}
                    </span>
                    {note && (
                      <span className="risk-exp-why-wrap">
                        <span className="risk-exp-why" aria-label="Why this matters">
                          ⓘ
                        </span>
                        <span className="risk-exp-tip">
                          <span className="risk-exp-tip-title">Why this matters</span>
                          <span className="risk-exp-tip-text">{note}</span>
                        </span>
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
