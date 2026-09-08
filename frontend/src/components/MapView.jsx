import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { levelColor, scoreToLevel } from "../constants/risk";
import SortToggle from "./SortToggle";

const TILE_URL = "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png";
const TILE_ATTR = '© <a href="https://stadiamaps.com/">Stadia Maps</a> © <a href="https://openmaptile.org/">OpenMapTiles</a> © OpenStreetMap';

function MarkerFor({ loc, selectedId, onSelect }) {
  const level = loc.risk_level || scoreToLevel(loc.risk_score, null);
  const color = levelColor(level);
  const selected = loc.location_id === selectedId;
  const icon = L.divIcon({
    className: "risk-marker",
    html: makeMarkerHtml(color, level, selected),
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
  return (
    <Marker
      position={[loc.coordinates.lat, loc.coordinates.lon]}
      icon={icon}
      eventHandlers={{ click: () => onSelect(loc.location_id) }}
    >
      <Popup className="risk-popup">
        <div className="popup-head">
          <span className="popup-dot" style={{ background: color }} />
          <strong>{loc.name}</strong>
        </div>
        <div className="popup-meta">
          <span className="popup-id">{loc.location_id}</span>
          <span className="popup-district">{loc.district}</span>
        </div>
        <div className="popup-score" style={{ color }}>
          Score {loc.risk_score.toFixed(1)}
        </div>
        <div className="popup-level" style={{ color }}>
          {level.toUpperCase()} RISK
        </div>
        <div className="popup-action">
          {loc.alert?.recommended_action?.slice(0, 110)}
          {loc.alert?.recommended_action?.length > 110 ? "…" : ""}
        </div>
      </Popup>
    </Marker>
  );
}

function makeMarkerHtml(color, level, selected) {
  const ring = selected ? "var(--primary)" : "rgba(255,255,255,0.5)";
  return `<div style="position:relative;width:22px;height:22px">
    <div style="width:22px;height:22px;border-radius:50%;background:${color};border:2px solid ${ring};box-shadow:0 0 8px ${color}cc;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;color:#0b0f14">${level[0].toUpperCase()}</div>
  </div>`;
}

function DeselectHandler({ onSelect }) {
  useMapEvents({ click() { onSelect(null); } });
  return null;
}

export default function MapView({ locations, selectedId, onSelect }) {
  const centre = locations.length > 0
    ? locations.reduce((a, b) => [a[0] + b.coordinates.lat, a[1] + b.coordinates.lon], [0, 0])
    : [10.5, 76.5];
  const centreLat = locations.length ? centre[0] / locations.length : 10.5;
  const centreLon = locations.length ? centre[1] / locations.length : 76.5;
  return (
    <MapContainer center={[centreLat, centreLon]} zoom={7} minZoom={5} maxZoom={18} className="leaflet-map" zoomControl={false} doubleClickZoom={false}>
      <TileLayer url={TILE_URL} attribution={TILE_ATTR} />
      {locations.map((loc) => (
        <MarkerFor key={loc.location_id} loc={loc} selectedId={selectedId} onSelect={onSelect} />
      ))}
      <DeselectHandler onSelect={onSelect} />
    </MapContainer>
  );
}
