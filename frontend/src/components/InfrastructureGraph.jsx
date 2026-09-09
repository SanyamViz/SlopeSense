import { useMemo, useState, useEffect, useRef } from "react";
import { levelColor, RISK_COLORS } from "../constants/risk";
import { fetchInfrastructure, fetchImpactAssessment } from "../api/riskClient";

const SAFE_COLOR = "#0052FF";
const STRANDED_COLOR = "#FF1744";
const EDGE_COLOR = "#737688";
const SVG_W = 980;
const SVG_H = 340;
const MARGIN = 50;

// Manual node positions for the known Wayanad sample dataset (6 nodes).
// This eliminates edge crossings through unrelated nodes for the hackathon's
// primary sample data. Falls back to geographic projection + force relaxation
// for any other dataset.
const KNOWN_LAYOUT = {
  "loc_100": { x: 380, y: 255 },
  "loc_101": { x: 580, y: 170 },
  "loc_102": { x: 380, y: 85 },
  "loc_103": { x: 200, y: 255 },
  "shelter_wayanad": { x: 820, y: 85 },
  "hospital_wayanad": { x: 900, y: 245 },
};

// Perpendicular offset (in px) from edge midpoint for route-ID badges.
// Large enough to clear both node circles (max r=18) and their "beds free"
// text labels (which extend ~32px below the node center).
const EDGE_BADGE_PERP_OFFSET = 42;

function computeNodePositions(nodes, edges) {
  if (!nodes || nodes.length === 0) return {};

  // Manual layout for the known Wayanad dataset
  const ids = nodes.map((n) => n.id);
  if (ids.length && ids.every((id) => KNOWN_LAYOUT[id])) {
    const positions = {};
    for (const n of nodes) positions[n.id] = { ...KNOWN_LAYOUT[n.id] };
    return positions;
  }

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

  // Force-directed relaxation with tuned parameters to reduce edge crossings
  const iterations = 120;
  const repulsion = 15000;
  const attraction = 0.01;
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

function getNodeTooltip(node, loc, impactZone) {
  if (node.type === "safe") {
    const capTotal = node.capacity_total || 0;
    const capFilled = node.capacity_filled || 0;
    const capAvail = capTotal - capFilled;
    return {
      title: node.name,
      subtitle: node.subtype === "hospital" ? "Hospital" : "Shelter",
      lines: [
        `Capacity: ${capTotal}`,
        `Occupied: ${capFilled}`,
        `Available: ${capAvail} beds`,
      ],
    };
  }
  const nearestHospital = impactZone?.nearby_safe_nodes?.find(
    (s) => s.subtype === "hospital",
  );
  return {
    title: node.name,
    subtitle: loc ? `Risk: ${loc.risk_level} (score ${loc.risk_score.toFixed(1)})` : "Risk: unknown",
    lines: [
      `Beds free nearby: ${impactZone ? impactZone.total_available_capacity_nearby : "—"}`,
      `Nearest hospital: ${nearestHospital ? `${nearestHospital.distance_km} km` : "—"}`,
      `Hospitals nearby: ${impactZone ? impactZone.nearby_hospital_count : "—"}`,
      `Elderly share: ${loc ? `${loc.vulnerability?.elderly_pct ?? 0}%` : "—"}`,
    ],
  };
}

// Legend entries for filtering and display
const LEGEND_ENTRIES = [
  { key: "shelter", label: "Shelter", swatch: { background: SAFE_COLOR } },
  { key: "hospital", label: "Hospital", swatch: { background: "#fff", border: `2px solid ${SAFE_COLOR}` } },
  { key: "stranded", label: "Stranded Zone", swatch: { background: STRANDED_COLOR } },
  { key: "risk_low", label: "Low Risk", swatch: { background: RISK_COLORS.low } },
  { key: "risk_moderate", label: "Moderate Risk", swatch: { background: RISK_COLORS.moderate } },
  { key: "risk_high", label: "High Risk", swatch: { background: RISK_COLORS.high } },
  { key: "risk_severe", label: "Severe Risk", swatch: { background: RISK_COLORS.severe } },
  { key: "capacity", label: "Available Capacity", swatch: { background: "#00C853" } },
];

function matchesFilter(node, loc, isStranded, filterKey) {
  if (!filterKey) return true;
  const isSafe = node.type === "safe";
  switch (filterKey) {
    case "shelter":
      return isSafe && node.subtype === "shelter";
    case "hospital":
      return isSafe && node.subtype === "hospital";
    case "stranded":
      return isStranded;
    case "risk_low":
      return loc && loc.risk_level === "low";
    case "risk_moderate":
      return loc && loc.risk_level === "moderate";
    case "risk_high":
      return loc && loc.risk_level === "high";
    case "risk_severe":
      return loc && loc.risk_level === "severe";
    default:
      return true;
  }
}

export default function InfrastructureGraph({ locations = [], highSevereCount }) {
  const [data, setData] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [impactLoading, setImpactLoading] = useState(true);
  const [error, setError] = useState(null);
  const [impactError, setImpactError] = useState(null);
  const [viewTransform, setViewTransform] = useState({ x: 0, y: 0, k: 1 });
  const [activeFilter, setActiveFilter] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  const svgRef = useRef(null);
  const draggingRef = useRef(false);
  const lastPosRef = useRef({ x: 0, y: 0 });

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

  // --- Zoom / pan handlers ---
  const onWheel = (e) => {
    e.preventDefault();
    if (!svgRef.current) return;
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const pt = svg.createSVGPoint();
    pt.x = e.clientX - rect.left;
    pt.y = e.clientY - rect.top;
    const ctm = svg.getScreenCTM();
    const viewPt = pt.matrixTransform(ctm.inverse());

    const delta = e.deltaY < 0 ? 1.1 : 0.9;
    const newK = Math.min(3, Math.max(0.5, viewTransform.k * delta));
    const factor = newK / viewTransform.k;
    const newX = viewPt.x - (viewPt.x - viewTransform.x) * factor;
    const newY = viewPt.y - (viewPt.y - viewTransform.y) * factor;
    setViewTransform({ x: newX, y: newY, k: newK });
  };

  const onMouseDown = (e) => {
    if (e.button !== 0) return;
    lastPosRef.current = { x: e.clientX, y: e.clientY, active: true };
    // Don't preventDefault — allow click events on nodes to fire when no drag occurs
  };

  const onMouseMove = (e) => {
    if (!lastPosRef.current?.active) return;
    const dx = e.clientX - lastPosRef.current.x;
    const dy = e.clientY - lastPosRef.current.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist > 3 && !draggingRef.current) {
      draggingRef.current = true;
    }

    if (draggingRef.current) {
      lastPosRef.current = { x: e.clientX, y: e.clientY, active: true };
      setViewTransform((t) => ({ x: t.x + dx, y: t.y + dy, k: t.k }));
    }
  };

  const onMouseUp = () => {
    draggingRef.current = false;
    lastPosRef.current = { active: false };
  };

  const resetView = () => setViewTransform({ x: 0, y: 0, k: 1 });

  const toggleFilter = (key) => {
    setActiveFilter((prev) => (prev === key ? null : key));
  };

  const handleNodeClick = (nodeId) => {
    setSelectedNode(nodeId);
    const row = document.getElementById(`zone-row-${nodeId}`);
    if (row) {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  };

  if (loading) return <div className="infra-graph infra-loading"><span className="spinner" /> Loading infrastructure graph...</div>;
  if (error) return <div className="infra-graph infra-error">Infrastructure data unavailable: {error}</div>;
  if (!data) return null;

  const strandedSet = new Set(data.stranded_zones.map((s) => s.zone_id));

  return (
    <div className="infra-graph">
      {/* Interactive legend with clickable filters */}
      <div className="infra-legend infra-legend-swatches">
        {LEGEND_ENTRIES.map((entry) => {
          const isActive = !activeFilter || activeFilter === entry.key;
          const isFilterable = ["shelter", "hospital", "stranded", "risk_low", "risk_moderate", "risk_high", "risk_severe"].includes(entry.key);
          return (
            <span
              key={entry.key}
              className={`infra-legend-item ${!isActive && isFilterable ? "infra-legend-dimmed" : ""} ${isFilterable ? "infra-legend-clickable" : ""}`}
              style={{ opacity: !isActive && isFilterable ? 0.3 : 1 }}
              onClick={isFilterable ? () => toggleFilter(entry.key) : undefined}
              title={isFilterable ? `Click to ${isActive ? "dim" : "highlight"} ${entry.label}` : entry.label}
            >
              <span className="swatch" style={entry.swatch} />
              {entry.label}
            </span>
          );
        })}
      </div>

      {/* Zoom/pan SVG canvas */}
      <div className="infra-svg-wrapper">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="infra-svg"
          xmlns="http://www.w3.org/2000/svg"
          onWheel={onWheel}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          <defs>
          <marker id="arr" markerWidth="10" markerHeight="10" refX="22" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill={EDGE_COLOR} />
          </marker>
          <filter id="edge-label-bg" x="-20%" y="-20%" width="140%" height="140%">
            <feFlood floodColor="#FEF9C3" result="bg" />
            <feMerge><feMergeNode in="bg" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          </defs>

          {/* Zoom reset button */}
          {viewTransform.k !== 1 || viewTransform.x !== 0 || viewTransform.y !== 0 ? (
            <g className="infra-zoom-reset-wrap">
              <rect x={SVG_W - 50} y={10} width={24} height={24} rx="4" fill="var(--surface-container-lowest)" stroke="var(--on-surface)" strokeWidth="1.5" />
              <text x={SVG_W - 38} y={25} fontSize="14" textAnchor="middle" fill="var(--on-surface)" cursor="pointer" onClick={resetView}>×</text>
            </g>
          ) : null}

          <g transform={`translate(${viewTransform.x}, ${viewTransform.y}) scale(${viewTransform.k})`}>
            {/* Edges */}
            {data.edges.map((e, i) => {
              const a = nodePositions[e.from], b = nodePositions[e.to];
              if (!a || !b) return null;
              const aNode = data.nodes.find((n) => n.id === e.from);
              const bNode = data.nodes.find((n) => n.id === e.to);
              const locA = locMap[e.from], locB = locMap[e.to];
              const strA = strandedSet.has(e.from), strB = strandedSet.has(e.to);

              const aVisible = matchesFilter(aNode, locA, strA, activeFilter);
              const bVisible = matchesFilter(bNode, locB, strB, activeFilter);
              const edgeDimmed = activeFilter && (!aVisible || !bVisible);

              const dx = b.x - a.x, dy = b.y - a.y;
              const len = Math.sqrt(dx * dx + dy * dy) || 1;
              const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
              const nx = -dy / len, ny = dx / len;
              // Badge sits at exact midpoint, offset perpendicular by EDGE_BADGE_PERP_OFFSET
              const bx = mx + nx * EDGE_BADGE_PERP_OFFSET;
              const by = my + ny * EDGE_BADGE_PERP_OFFSET;
              const edgeOpacity = edgeDimmed ? 0.1 : 0.6;
              const arrowOpacity = edgeDimmed ? 0.15 : 0.9;
              return (
                <g key={i}>
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={EDGE_COLOR} strokeWidth="2" strokeOpacity={edgeOpacity} />
                  <line x1={a.x} y1={a.y} x2={bx} y2={by} stroke={EDGE_COLOR} strokeWidth="2" strokeOpacity={arrowOpacity} markerEnd="url(#arr)" />
                  <rect
                    x={bx - 14}
                    y={by - 8}
                    width={28}
                    height={16}
                    rx="3"
                    fill="#FEF9C3"
                    stroke="#1C1917"
                    strokeWidth="1"
                  />
                  <text x={bx} y={by + 3} fill={EDGE_COLOR} fontSize="8" fontFamily="monospace" textAnchor="middle" alignmentBaseline="middle">{e.road_id}</text>
                </g>
              );
            })}

            {/* Nodes */}
            {data.nodes.map((node) => {
              const pos = nodePositions[node.id];
              if (!pos) return null;
              const loc = locMap[node.id];
              const isStranded = strandedSet.has(node.id);
              const isSafe = node.type === "safe";
              const isHospital = isSafe && node.subtype === "hospital";
              const nodeDimmed = activeFilter && !matchesFilter(node, loc, isStranded, activeFilter);
              const isSelected = selectedNode === node.id;

              let fill, stroke, strokeWidth;
              if (isStranded) {
                fill = STRANDED_COLOR;
                stroke = "#fff";
                strokeWidth = 2.5;
              } else if (isHospital) {
                fill = "none";
                stroke = SAFE_COLOR;
                strokeWidth = 2;
              } else {
                fill = isSafe ? SAFE_COLOR : (loc ? levelColor(loc.risk_level) : "#8b9bb0");
                stroke = "#0e1620";
                strokeWidth = 1.5;
              }
              const r = isSafe ? 16 : (isStranded ? 18 : 14);

              const iz = impactZoneMap[node.id];
              const capAvail = iz ? iz.total_available_capacity_nearby : null;
              const label = node.name || node.id;

              const handleMouseEnter = (e) => {
                if (nodeDimmed) return;
                const tip = getNodeTooltip(node, loc, iz);
                setTooltip({ ...tip, x: e.clientX, y: e.clientY });
              };
              const handleMouseMove = (e) => {
                if (!nodeDimmed) {
                  setTooltip((t) => ({ ...t, x: e.clientX, y: e.clientY }));
                }
              };

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onClick={() => handleNodeClick(node.id)}
                  onMouseEnter={handleMouseEnter}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={() => setTooltip(null)}
                  style={{ cursor: "pointer", opacity: nodeDimmed ? 0.2 : 1 }}
                >
                  <circle
                    r={r}
                    fill={fill}
                    stroke={isSelected ? "#fff" : stroke}
                    strokeWidth={(isSelected ? 3 : 0) + strokeWidth}
                    style={isSelected ? { filter: "url(#glow)" } : {}}
                  />
                  <title>{label}</title>
                  <text y={isSafe ? 6 : 5} textAnchor="middle" alignmentBaseline="middle" fill={nodeDimmed ? "#999" : "#070b10"} fontSize="9.5" fontWeight="700" fontFamily="sans-serif">
                    {label}
                  </text>
                  {capAvail !== null && capAvail > 0 && !isSafe && (
                    <text y={24} textAnchor="middle" alignmentBaseline="middle" fill="#00C853" fontSize="8.5" fontWeight="700" fontFamily="monospace">
                      {capAvail} beds free
                    </text>
                  )}
                  {isStranded && (
                    <text y={-r - 6} textAnchor="middle" alignmentBaseline="middle" fill={STRANDED_COLOR} fontSize="8" fontWeight="700" fontFamily="monospace">
                      ⚠ STRANDED
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* Hover tooltip (HTML overlay positioned at cursor) */}
        {tooltip && (
          <div
            className="infra-tooltip"
            style={{
              left: tooltip.x + 14,
              top: tooltip.y + 14,
              maxWidth: "260px",
            }}
            onMouseEnter={() => setTooltip(null)}
          >
            <div className="infra-tooltip-inner">
              <div className="infra-tooltip-title">{tooltip.title}</div>
              <div className="infra-tooltip-subtitle">{tooltip.subtitle}</div>
              {tooltip.lines.map((line, i) => (
                <div key={i} className="infra-tooltip-line">{line}</div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Zoom instructions hint */}
      <div className="infra-zoom-hint">
        <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>zoom_in</span>
        Scroll to zoom · Drag to pan
      </div>

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
                    const isHighlighted = selectedNode === z.zone_id;
                    return (
                      <tr
                        key={z.zone_id}
                        id={`zone-row-${z.zone_id}`}
                        className={`
                          ${strandedSet.has(z.zone_id) ? "infra-impact-stranded-row" : ""}
                          ${isHighlighted ? "infra-row-highlight" : ""}
                        `}
                      >
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
