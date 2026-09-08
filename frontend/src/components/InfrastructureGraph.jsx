import { useMemo, useState, useEffect } from "react";
import { levelColor } from "../constants/risk";
import { fetchInfrastructure, fetchImpactAssessment } from "../api/riskClient";

const NODE_COORDS = {
  shelter_1:   { x: 60,  y: 80 },
  loc_072:     { x: 180, y: 80 },
  loc_004:     { x: 300, y: 80 },
  hospital_1:  { x: 420, y: 80 },
  loc_050:     { x: 180, y: 200 },
  loc_010:     { x: 300, y: 200 },
  loc_038:     { x: 420, y: 200 },
  loc_029:     { x: 540, y: 200 },
  shelter_2:   { x: 660, y: 200 },
};

const SAFE_COLOR = "#0052FF";
const STRANDED_COLOR = "#FF1744";
const EDGE_COLOR = "#737688";

export default function InfrastructureGraph({ locations = [] }) {
  const [data, setData] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [impactLoading, setImpactLoading] = useState(true);
  const [error, setError] = useState(null);
  const [impactError, setImpactError] = useState(null);
  const locMap = useMemo(() => { const m = {}; for (const l of locations) m[l.location_id] = l; return m; }, [locations]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchInfrastructure()
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setImpactLoading(true);
    setImpactError(null);
    fetchImpactAssessment(20)
      .then((d) => { if (!cancelled) setImpact(d); })
      .catch((e) => { if (!cancelled) setImpactError(e.message); })
      .finally(() => { if (!cancelled) setImpactLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div className="infra-graph infra-loading"><span className="spinner" /> Loading infrastructure graph...</div>;
  if (error) return <div className="infra-graph infra-error">Infrastructure data unavailable: {error}</div>;
  if (!data) return null;

  const strandedSet = new Set(data.stranded_zones.map((s) => s.zone_id));
  const strandedMap = {};
  for (const s of data.stranded_zones) strandedMap[s.zone_id] = s;

  const impactZoneMap = useMemo(() => {
    const m = {};
    if (!impact) return m;
    for (const z of impact.zones || []) m[z.zone_id] = z;
    return m;
  }, [impact]);

  const svgW = 980, svgH = 320;
  return (
    <div className="infra-graph">
      <div className="infra-legend">
        <span className="infra-legend-item"><i style={{ background: SAFE_COLOR }} /> Shelter / Hospital</span>
        <span className="infra-legend-item"><i style={{ background: STRANDED_COLOR }} /> Stranded zone</span>
        <span className="infra-legend-item"><i style={{ background: "#00C853" }} /> Available capacity</span>
      </div>
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="infra-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arr" markerWidth="10" markerHeight="10" refX="22" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill={EDGE_COLOR} />
          </marker>
        </defs>
        {data.edges.map((e, i) => {
          const a = NODE_COORDS[e.from], b = NODE_COORDS[e.to];
          if (!a || !b) return null;
          const dx = b.x - a.x, dy = b.y - a.y;
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
          const nx = -dy / len, ny = dx / len;
          const cx = mx + nx * 8, cy = my + ny * 8;
          return (
            <g key={i}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={EDGE_COLOR} strokeWidth="2" strokeOpacity="0.6" />
              <line x1={a.x} y1={a.y} x2={cx} y2={cy} stroke={EDGE_COLOR} strokeWidth="2" strokeOpacity="0.9" markerEnd="url(#arr)" />
              <text x={cx + (dx / len) * 10} y={cy + (dy / len) * 10} fill={EDGE_COLOR} fontSize="9" fontFamily="monospace" textAnchor="middle" alignmentBaseline="middle">{e.road_id}</text>
            </g>
          );
        })}
        {data.nodes.map((node) => {
          const pos = NODE_COORDS[node.id];
          if (!pos) return null;
          const loc = locMap[node.id];
          const isStranded = strandedSet.has(node.id);
          const isSafe = node.type === "safe";
          let fill = isSafe ? SAFE_COLOR : (loc ? levelColor(loc.risk_level) : "#8b9bb0");
          if (isStranded) fill = STRANDED_COLOR;
          const r = isSafe ? 14 : (isStranded ? 16 : 12);
          const iz = impactZoneMap[node.id];
          const capAvail = iz ? iz.total_available_capacity_nearby : null;
          return (
            <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
              <circle r={r} fill={fill} stroke={isStranded ? "#fff" : "#0e1620"} strokeWidth={isStranded ? 2.5 : 1.5} />
              <text y={isSafe ? 5 : 4} textAnchor="middle" alignmentBaseline="middle" fill="#070b10" fontSize="10" fontWeight="700" fontFamily="sans-serif">
                {node.name.length > 10 ? node.name.slice(0, 9) + "…" : node.name}
              </text>
              {capAvail !== null && capAvail > 0 && (
                <text y={22} textAnchor="middle" alignmentBaseline="middle" fill="#00C853" fontSize="9" fontWeight="700" fontFamily="monospace">
                  {capAvail} beds free
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {impactLoading && <div className="infra-impact-loading"><span className="spinner" /> Loading impact assessment...</div>}
      {impactError && <div className="infra-impact-error">Impact assessment unavailable: {impactError}</div>}

      {impact && !impactLoading && (
        <div className="infra-impact">
          <div className="infra-impact-summary">
            <div className="infra-impact-card">
              <div className="infra-impact-label">Zones at high / severe risk</div>
              <div className="infra-impact-value">{impact.summary.total_zones_at_risk}</div>
            </div>
            <div className="infra-impact-card">
              <div className="infra-impact-label">Zones with hospital within 20 km</div>
              <div className="infra-impact-value">{impact.summary.zones_with_hospitals_nearby} <span className="infra-impact-sub">/ {impact.summary.total_zones}</span></div>
            </div>
            <div className="infra-impact-card">
              <div className="infra-impact-label">Zones with NO hospital within 20 km</div>
              <div className="infra-impact-value infra-impact-danger">{impact.summary.zones_with_no_hospitals_nearby}</div>
            </div>
            <div className="infra-impact-card">
              <div className="infra-impact-label">Total available capacity nearby</div>
              <div className="infra-impact-value infra-impact-ok">{impact.summary.total_available_capacity_nearby} <span className="infra-impact-sub">beds</span></div>
            </div>
          </div>

          <div className="infra-impact-detail">
            <h4 className="infra-impact-heading">Per-zone hospital &amp; route status</h4>
            <div className="infra-impact-table-wrap">
              <table className="infra-impact-table">
                <thead>
                  <tr>
                    <th>Zone</th>
                    <th>Risk</th>
                    <th>Hospitals nearby</th>
                    <th>Beds free</th>
                    <th>Alternative route</th>
                  </tr>
                </thead>
                <tbody>
                  {(impact.zones || []).map((z) => {
                    const alt = z.alternative_routes && z.alternative_routes.length > 0
                      ? z.alternative_routes.find((r) => !r.unreachable)
                      : null;
                    const altText = alt
                      ? `${alt.safe_node_name} (${alt.hops} hops)`
                      : (z.alternative_routes && z.alternative_routes.every((r) => r.unreachable) ? "UNREACHABLE" : "N/A");
                    const altClass = altText === "UNREACHABLE" ? "infra-impact-unreachable" : (alt ? "infra-impact-reachable" : "");
                    return (
                      <tr key={z.zone_id} className={strandedSet.has(z.zone_id) ? "infra-impact-stranded-row" : ""}>
                        <td data-label="Zone">{z.zone_name}</td>
                        <td data-label="Risk">
                          <span className={`risk-badge risk-${z.risk_level}`}>{z.risk_level}</span>
                        </td>
                        <td data-label="Hospitals nearby" className="text-center">{z.nearby_hospital_count}</td>
                        <td data-label="Beds free" className="text-center">{z.total_available_capacity_nearby}</td>
                        <td data-label="Alternative route" className={altClass}>{altText}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <div className="infra-footer">
        {data.stranded_zones.length === 0 ? (
          <span className="infra-ok">No zones are currently stranded.</span>
        ) : (
          data.stranded_zones.map((s, i) => {
            const node = data.nodes.find((n) => n.id === s.zone_id);
            const blocker = data.nodes.find((n) => n.id === s.blocked_by_zone_id);
            return (
              <div className="infra-stranded-card" key={i}>
                <strong>{node ? node.name : s.zone_id}</strong> stranded if <em>{blocker ? blocker.name : s.blocked_by_zone_id}</em> goes high/severe.
                <span className="infra-stranded-reason">{s.reason}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
