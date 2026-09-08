import { useEffect, useState, useCallback, useMemo } from "react";
import { fetchRiskMap, fetchConfig } from "./api/riskClient";
import { levelColor, scoreToLevel, RISK_LABELS } from "./constants/risk";
import "./styles.css";
import MastheadMicro from "./components/MastheadMicro";
import TopBar from "./components/TopBar";
import AlertRibbon from "./components/AlertRibbon";
import HeroSuite from "./components/HeroSuite";
import MapCard from "./components/MapCard";
import ActionStackCard from "./components/ActionStackCard";
import SidePanel from "./components/SidePanel";
import CrisisForecastSimulator from "./components/CrisisForecastSimulator";
import InfrastructureGraph from "./components/InfrastructureGraph";
import DispatchModal from "./components/DispatchModal";
import Toast from "./components/Toast";
import { buildStackRows, computeHero, computeAdvisory, computeTiles } from "./engine";
import { playSiren } from "./hooks/useSiren";

export default function App() {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [search, setSearch] = useState("");
  const [rankMode, setRankMode] = useState("priority");
  const [showWhatIf, setShowWhatIf] = useState(false);
  const [rain, setRain] = useState(75);
  const [soil, setSoil] = useState(38);
  const [cfg, setCfg] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalSector, setModalSector] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetchRiskMap(), fetchConfig()])
      .then(([d, c]) => { if (!cancelled) { setDoc(d); setCfg(c); } })
      .catch((e) => { if (!cancelled) setError(e.message || "Failed to load risk data"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const locations = doc?.locations ?? [];
  const counts = doc?.summary?.counts_by_risk_level ?? {};
  const thresholds = doc?.metadata?.risk_thresholds;

  const isSevere = rain >= 50 || soil >= 28;
  const isCriticalSeverance = rain > 80 || soil > 40;

  const stackRows = useMemo(() => buildStackRows(locations, isSevere, isCriticalSeverance), [locations, isSevere, isCriticalSeverance]);
  const hero = useMemo(() => computeHero(locations, isSevere, isCriticalSeverance), [locations, isSevere, isCriticalSeverance]);
  const advisory = useMemo(() => computeAdvisory(isSevere, isCriticalSeverance), [isSevere, isCriticalSeverance]);
  const tiles = useMemo(() => computeTiles(locations, isSevere, isCriticalSeverance), [locations, isSevere, isCriticalSeverance]);

  const handleDispatch = (id) => { setModalSector(id); setModalOpen(true); };
  const handleTransmit = (sector) => { setModalOpen(false); playSiren(); setToast({ key: Date.now(), sector }); };

  const selectedLocation = useMemo(() => {
    if (!selectedId) return null;
    return locations.find((l) => l.location_id === selectedId) || null;
  }, [locations, selectedId]);

  return (
    <div className="app">
      <MastheadMicro title="EMERGENCY DISPATCH · WAYANAD DISTRICT HQ" cycle="CYCLE #1,482 · DOPPLER SYNCED" live="19:15:11 IST" />
      <TopBar counts={counts} total={doc?.metadata?.total_locations ?? locations.length} modelVersion={doc?.metadata?.model_version} generatedAt={doc?.metadata?.generated_at} search={search} onSearch={setSearch} />
      <AlertRibbon isSevere={isSevere} isCriticalSeverance={isCriticalSeverance} gaugeReadout={isCriticalSeverance ? "+4.4m (CRITICAL RUNOUT)" : isSevere ? "+3.8m (DANGER PEAK)" : "+1.1m (SAFE BASIN)"} alertText={isCriticalSeverance ? "CRITICAL SEVERANCE WARNING: CHOORALMALA-MUNDAKKAI SPUR COMPLETELY RUPTURED — MAXIMUM EVACUATION DISPATCH ARMED" : isSevere ? "CRITICAL SITUATION: MUNDAKKAI & ATTAMALA FULLY ISOLATED — CHOORALMALA BRIDGE SEVERED AT KM 14+200" : "ELEVATED MONITORING: ALL PRIMARY CORRIDORS ACCESSIBLE — MONITORING ACTIVE INFLOW AT CHOORALMALA"} alertIcon={isSevere ? "error" : "check_circle"} />
      <main className="w-full px-4 md:px-8 py-5 flex-grow space-y-5">
        <HeroSuite {...hero} isSevere={isSevere} isCriticalSeverance={isCriticalSeverance} />
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
          <MapCard className="lg:col-span-8" locations={locations} selectedId={selectedId} onSelect={setSelectedId} isSevere={isSevere} isCriticalSeverance={isCriticalSeverance} />
          <div className="lg:col-span-4">
            {selectedLocation
              ? <SidePanel location={selectedLocation} />
              : <ActionStackCard rows={stackRows} advisory={advisory} isSevere={isSevere} onDispatch={handleDispatch} />}
          </div>
        </div>
        <CrisisForecastSimulator rain={rain} soil={soil} onRainChange={setRain} onSoilChange={setSoil} onBaseline={() => { setRain(15); setSoil(14); }} onSevere={() => { setRain(95); setSoil(52); }} onReset={() => { setRain(75); setSoil(38); }} locations={locations} selectedId={selectedId} />
        <InfrastructureGraph locations={locations} />
      </main>
      <footer className="app-footer">
        <div className="foot-left">
          <span className="foot-item"><span className="dot" />STATION SENSORS: <span className="foot-val">—</span><span className="foot-illustrative">illustrative</span></span>
          <span className="foot-item">INFERENCE LATENCY: <span className="foot-latency">—</span><span className="foot-illustrative">illustrative</span></span>
          <span className="foot-item">GRAPH ENGINE: <span className="foot-graph">NetworkX</span><span className="foot-illustrative">illustrative</span></span>
        </div>
        <div className="foot-right">
          <span className="foot-model">MODEL: <span className="model-name">{doc?.metadata?.model_version || "WeightedScorer"}</span></span>
          <span className="foot-command">COMMAND CELL: WAYANAD DISTRICT HQ</span>
        </div>
      </footer>
      <DispatchModal open={modalOpen} sector={modalSector} onClose={() => setModalOpen(false)} onTransmit={handleTransmit} />
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}