import React from "react";
import MapView from "./MapView";

export default function MapCard({ locations, selectedId, onSelect, isSevere, isCriticalSeverance }) {
  return (
    <section className="map-card">
      <div className="card-head">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 bg-[#1C1917]"></span>
            <h2 className="card-title">CORRIDOR SCHEMATIC ROAD NETWORK</h2>
          </div>
          <p className="card-sub">Single-point-of-failure topology connecting settlements to Kalpetta Command HQ.</p>
        </div>
        <span className="map-badge">
          <span className="dot"></span>
          {isCriticalSeverance ? "CRITICAL SEVERANCE WARNING — KM 14" : isSevere ? "CHOORALMALA BRIDGE SEVERED" : "BRIDGE TRANSIT PASSABLE - 15 KM/H"}
        </span>
      </div>
      <div className="map-svg-wrap">
        <MapView locations={locations} selectedId={selectedId} onSelect={onSelect} />
        <div className="map-legend-card">
          <span className="legend-title">NETWORK MAP KEY</span>
          <div className="legend-grid">
            <span className="flex items-center gap-1.5"><span className="swatch" style={{ background: "#15803D" }}></span>Low Risk</span>
            <span className="flex items-center gap-1.5"><span className="swatch" style={{ background: "#B45309" }}></span>Moderate</span>
            <span className="flex items-center gap-1.5"><span className="swatch" style={{ background: "#EA580C" }}></span>High Risk</span>
            <span className="flex items-center gap-1.5"><span className="swatch" style={{ background: "#DC2626" }}></span>Severe</span>
          </div>
          <div className="legend-isolated">
            <span className="swatch"></span>Isolated Spur Active
          </div>
        </div>
      </div>
    </section>
  );
}