import { useMemo, useState, useEffect } from "react";
import { levelColor } from "../constants/risk";
import { fetchInfrastructure, fetchImpactAssessment } from "../api/riskClient";

const SAFE_COLOR = "#0052FF";
const STRANDED_COLOR = "#FF1744";
const EDGE_COLOR = "#737688";
const SVG_W = 980;
const SVG_H = 340;
const MARGIN = 50;

function computeNodePositions(nodes, edges) {
  const coords = nodes
    .filter((n) => typeof n.lat === "number" && typeof n.lon === "number")
    .map((n) => ({ id: n.id, lat: n.lat, lon: n.lon }));
  if (coords.length === 0) return {};

  const lats = coords.map((c) => c.lat);
  const lons = coords.map((c) => c.lon);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const latRange = maxLat - minLat || 1;
  const lonRange = maxLon - minLon || 1;

  const positions = {};
  for (const c of coords) {
    positions[c.id] = {
      x: MARGIN + ((c.lon - minLon) / lonRange) * (SVG_W - 2 * MARGIN),
      y: MARGIN + (1 - (c.lat - minLat) / latRange) * (SVG_H - 2 * MARGIN),
    };
  }

  // Simple force-directed relaxation to prevent overlap
  const iterations = 60;
  const repulsion = 8000;
  const attraction = 0.005;
  const damping = 0.85;
  const nodeIds = Object.keys(positions);

  for (let iter = 0; iter < iterations; iter++) {
    const forces = {};
    for (const id of nodeIds) forces[id] = { fx: 0, fy: 0 };

    for (let i = 0; i < nodeIds.length; i++) {
      for (let j = i + 1; j < nodeIds.length; j++) {
        const a = nodeIds[i], b = nodeIds[j];
        const pa = positions[a], pb = positions[b];
        const dx = pb.x - pa.x, dy = pb.y - pa.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        forces[a].fx -= fx; forces[a].fy -= fy;
        forces[b].fx += fx; forces[b].fy += fy;
      }
    }

    if (edges && edges.length) {
      for (const e of edges) {
        const a = positions[e.from], b = positions[e.to];
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = dist * attraction;
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        forces[e.from].fx += fx; forces[e.from].fy += fy;
        forces[e.to].fx -= fx; forces[e.to].fy -= fy;
      }
    }

    const alpha = 1 - (iter / iterations);
    for (const id of nodeIds) {
      positions[id].x += forces[id].fx * alpha * damping;
      positions[id].y += forces[id].fy * alpha * damping;
      positions[id].x = Math.max(MARGIN, Math.min(SVG_W - MARGIN, positions[id].x));
      positions[id].y = Math.max(MARGIN, Math.min(SVG_H - MARGIN, positions[id].y));
    }
  }

  return positions;
}

export default function InfrastructureGraph({ locations = [], highSevereCount }) {
  const [data, setData] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [impactLoading, setImpactLoading] = useState(true);
  const [error, setError] = useState(null);
  const [impactError, setImpactError] = useState(null);
  const locMap = useMemo(() => { const m = {}; for (const l of locations) m[l.location_id] = l; return m; }, [locations]);

  const nodePositions = useMemo(() => computeNodePositions(data?.nodes || [], data?.edges || []), [data?.nodes, data?.edges]);

  const impactZoneMap = useMemo(() => {
    const m = {};
    if (!impact) return m;
    for (const z of impact.zones || []) m[z.zone_id] = z;
    return m;
  }, [impact]);

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

  return (
    <div className="infra-graph">
      <div className="infra-legend infra-legend-swatches">
        <span className="infra-legend-item"><span className="swatch" style={{ background: SAFE_COLOR }} /> Shelter</span>
        <span className="infra-legend-item"><span className="swatch" style={{ background: "#fff", border: "2px solid #0052FF" }} /> Hospital</span>
        <span className="infra-legend-item"><span className="swatch" style={{ background: STRANDED_COLOR }} /> Stranded Zone</span>
        <span className="infra-legend-item"><span className="swatch" style={{ background: "#00C853" }} /> Available Capacity</span>
      </div>
      <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} className="infra-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arr" markerWidth="10" markerHeight="10" refX="22" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill={EDGE_COLOR} />
          </marker>
          <filter id="edge-label-bg" x="-20%" y="-20%" width="140%" height="140%">
            <feFlood floodColor="#FEF9C3" result="bg" />
            <feMerge><feMergeNode in="bg" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {data.edges.map((e, i) => {
          const a = nodePositions[e.from], b = nodePositions[e.to];
          if (!a || !b) return null;
          const dx = b.x - a.x, dy = b.y - a.y;
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
          const nx = -dy / len, ny = dx / len;
          const cx = mx + nx * 14, cy = my + ny * 14;
          const labelX = cx + (dx / len) * 12;
          const labelY = cy + (dy / len) * 12;
          return (
            <g key={i}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={EDGE_COLOR} strokeWidth="2" strokeOpacity="0.6" />
              <line x1={a.x} y1={a.y} x2={cx} y2={cy} stroke={EDGE_COLOR} strokeWidth="2" strokeOpacity="0.9" markerEnd="url(#arr)" />
              <rect
                x={labelX - 14}
                y={labelY - 8}
                width={28}
                height={16}
                rx="3"
                fill="#FEF9C3"
                stroke="#1C1917"
                strokeWidth="1"
              />
              <text x={labelX} y={labelY + 3} fill={EDGE_COLOR} fontSize="8" fontFamily="monospace" textAnchor="middle" alignmentBaseline="middle">{e.road_id}</text>
            </g>
          );
        })}
        {data.nodes.map((node) => {
          const pos = nodePositions[node.id];
          if (!pos) return null;
          const loc = locMap[node.id];
          const isStranded = strandedSet.has(node.id);
          const isSafe = node.type === "safe";
          let fill = isSafe ? SAFE_COLOR : (loc ? levelColor(loc.risk_level) : "#8b9bb0");
          if (isStranded) fill = STRANDED_COLOR;
          const r = isSafe ? 16 : (isStranded ? 18 : 14);
          const iz = impactZoneMap[node.id];
          const capAvail = iz ? iz.total_available_capacity_nearby : null;
          const label = node.name || node.id;
          return (
            <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
              <circle r={r} fill={fill} stroke={isStranded ? "#fff" : "#0e1620"} strokeWidth={isStranded ? 2.5 : 1.5} />
              <title>{label}</title>
              <text y={isSafe ? 6 : 5} textAnchor="middle" alignmentBaseline="middle" fill="#070b10" fontSize="9.5" fontWeight="700" fontFamily="sans-serif">
                {label}
              </text>
              {capAvail !== null && capAvail > 0 && (
                <text y={24} textAnchor="middle" alignmentBaseline="middle" fill="#00C853" fontSize="8.5" fontWeight="700" fontFamily="monospace">
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
              <div className="infra-impact-value">{highSevereCount !== undefined ? highSevereCount : impact.summary.total_zones_at_risk}</div>
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
