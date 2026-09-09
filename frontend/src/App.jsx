import { useEffect, useState, useCallback, useMemo } from "react";
import { fetchRiskMap, fetchConfig, fetchImpactAssessment, onWarmingChange } from "./api/riskClient";
import { levelColor, scoreToLevel, RISK_LABELS } from "./constants/risk";
import "./styles.css";
import MastheadMicro from "./components/MastheadMicro";
import TopBar from "./components/TopBar";
import AlertRibbon from "./components/AlertRibbon";
import HeroSuite from "./components/HeroSuite";
import MapCard from "./components/MapCard";
import ActionStackCard from "./components/ActionStackCard";
import CrisisForecastSimulator from "./components/CrisisForecastSimulator";
import DispatchModal from "./components/DispatchModal";
import Toast from "./components/Toast";
import AlertBanner from "./components/AlertBanner";
import SidePanel from "./components/SidePanel";
import WhatIfPanel from "./components/WhatIfPanel";
import InfrastructureGraph from "./components/InfrastructureGraph";
import { buildStackRows, computeHero, computeAdvisory, computeTiles, computeHighSevereCount } from "./engine";

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
  const [activeTab, setActiveTab] = useState("dashboard"); // "dashboard" | "infrastructure"
  const [warmingUp, setWarmingUp] = useState(false);
  const [now, setNow] = useState(new Date());
  const [impact, setImpact] = useState(null);

  useEffect(() => {
    const unsub = onWarmingChange(setWarmingUp);
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetchRiskMap(), fetchConfig()])
      .then(([d, c]) => { if (!cancelled) { setDoc(d); setCfg(c); } })
      .catch((e) => { if (!cancelled) setError(e.message || "Failed to load risk data"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; unsub(); };
  }, []);

  // Fetch the impact assessment once so the dashboard stack rows can quote
  // real stranded-zone / alternative-route data instead of literal strings.
  useEffect(() => {
    let cancelled = false;
    fetchImpactAssessment(20)
      .then((d) => { if (!cancelled) setImpact(d); })
      .catch(() => { if (!cancelled) setImpact(null); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const locations = doc?.locations ?? [];
  const counts = doc?.summary?.counts_by_risk_level ?? {};
  const thresholds = doc?.metadata?.risk_thresholds;

  const isSevere = rain >= 50 || soil >= 28;
  const isCriticalSeverance = rain > 80 || soil > 40;

  // Build a zone_id -> impact zone map (same data InfrastructureGraph uses).
  const impactMap = useMemo(() => {
    const m = {};
    for (const z of impact?.zones || []) m[z.zone_id] = z;
    return m;
  }, [impact]);

  const stackRows = useMemo(
    () => buildStackRows(locations, isSevere, isCriticalSeverance, impactMap),
    [locations, isSevere, isCriticalSeverance, impactMap]
  );
  const hero = useMemo(
    () => computeHero(locations, isSevere, isCriticalSeverance, impactMap),
    [locations, isSevere, isCriticalSeverance, impactMap]
  );
  const advisory = useMemo(() => computeAdvisory(isSevere, isCriticalSeverance), [isSevere, isCriticalSeverance]);
  const highSevereCount = useMemo(() => computeHighSevereCount(locations), [locations]);
  const tiles = useMemo(
    () => computeTiles(locations, isSevere, isCriticalSeverance),
    [locations, isSevere, isCriticalSeverance]
  );

  // Selected location object for SidePanel and WhatIfPanel
  const selectedLocation = useMemo(
    () => locations.find((l) => l.location_id === selectedId) ?? null,
    [locations, selectedId]
  );

  const handleDispatch = (id) => { setModalSector(id); setModalOpen(true); };
  const handleTransmit = (sector, result) => {
    setModalOpen(false);
    setToast({ key: Date.now(), sector, result });
  };

  // Resolve the real location record (with alert.message_en/message_local) for
  // the sector currently open in the dispatch modal.
  const modalLocation = useMemo(
    () => locations.find((l) => l.location_id === modalSector) ?? null,
    [locations, modalSector]
  );

  if (warmingUp) {
    return (
      <div className="app" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div style={{ textAlign: "center", fontFamily: "JetBrains Mono, monospace" }}>
          <div className="spinner" style={{ margin: "0 auto 16px" }} />
          <div style={{ color: "#0052FF", fontWeight: 700, fontSize: 13, letterSpacing: "0.1em" }}>
            WAKING UP THE SERVER, THIS MAY TAKE UP TO A MINUTE…
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="app" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div style={{ textAlign: "center", fontFamily: "JetBrains Mono, monospace" }}>
          <div className="spinner" style={{ margin: "0 auto 16px" }} />
          <div style={{ color: "#0052FF", fontWeight: 700, fontSize: 13, letterSpacing: "0.1em" }}>LOADING RISK DATA…</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: 32 }}>
        <div style={{ maxWidth: 480, textAlign: "center", fontFamily: "JetBrains Mono, monospace" }}>
          <div style={{ color: "#DC2626", fontWeight: 800, fontSize: 14, marginBottom: 8, letterSpacing: "0.08em" }}>⚠ BACKEND UNREACHABLE</div>
          <div style={{ color: "#44403C", fontSize: 12, marginBottom: 16 }}>{error}</div>
          <div style={{ color: "#44403C", fontSize: 11 }}>Make sure the FastAPI server is running:<br /><code style={{ background: "#F5F1E8", padding: "2px 6px", borderRadius: 2 }}>uvicorn main:app --port 8000</code><br />from the project root (<code>SlopeSense/</code>)</div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <MastheadMicro title="EMERGENCY DISPATCH · WAYANAD DISTRICT HQ" cycle="CYCLE #1,482 · DOPPLER SYNCED" />
      <TopBar counts={counts} total={doc?.metadata?.total_locations ?? locations.length} modelVersion={doc?.metadata?.model_version} generatedAt={doc?.metadata?.generated_at} search={search} onSearch={setSearch} />
      <AlertRibbon isSevere={isSevere} isCriticalSeverance={isCriticalSeverance} gaugeReadout={isCriticalSeverance ? "+4.4m (CRITICAL RUNOUT)" : isSevere ? "+3.8m (DANGER PEAK)" : "+1.1m (SAFE BASIN)"} alertText={isCriticalSeverance ? "CRITICAL SEVERANCE WARNING: CHOORALMALA-MUNDAKKAI SPUR COMPLETELY RUPTURED — MAXIMUM EVACUATION DISPATCH ARMED" : isSevere ? "CRITICAL SITUATION: MUNDAKKAI & ATTAMALA FULLY ISOLATED — CHOORALMALA BRIDGE SEVERED AT KM 14+200" : "ELEVATED MONITORING: ALL PRIMARY CORRIDORS ACCESSIBLE — MONITORING ACTIVE INFLOW AT CHOORALMALA"} alertIcon={isSevere ? "error" : "check_circle"} />

      {/* Active alert banner (real data from /risk-map filtered client-side) */}
      <AlertBanner locations={locations} rankMode={rankMode} />

      {/* Tab navigation */}
      <div style={{ display: "flex", gap: 0, borderBottom: "2px solid #1C1917", background: "#FEF9C3", padding: "0 2rem" }}>
        {[
          { key: "dashboard", label: "COMMAND DASHBOARD" },
          { key: "infrastructure", label: "INFRASTRUCTURE GRAPH" },
        ].map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActiveTab(t.key)}
            style={{
              padding: "8px 18px",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "0.1em",
              border: "none",
              borderBottom: activeTab === t.key ? "3px solid #0052FF" : "3px solid transparent",
              background: "transparent",
              color: activeTab === t.key ? "#0052FF" : "#44403C",
              cursor: "pointer",
              textTransform: "uppercase",
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <main className="w-full px-4 md:px-8 py-5 flex-grow space-y-5">
        {activeTab === "dashboard" && (
          <>
            <HeroSuite {...hero} isSevere={isSevere} isCriticalSeverance={isCriticalSeverance} />

            {/* Main 2-col: map (left) + side panel / action stack (right) */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 400px", gap: "1.25rem", alignItems: "stretch" }}>
              {/* Map */}
              <MapCard locations={locations} selectedId={selectedId} onSelect={setSelectedId} isSevere={isSevere} isCriticalSeverance={isCriticalSeverance} />

              {/* Right column: SidePanel when a marker is clicked, else ActionStack */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem", minWidth: 0 }}>
                {selectedLocation ? (
                  <>
                    <SidePanel
                      location={selectedLocation}
                      rankMode={rankMode}
                      onOpenWhatIf={() => setShowWhatIf(true)}
                    />
                    {showWhatIf && (
                      <WhatIfPanel
                        location={selectedLocation}
                        onClose={() => setShowWhatIf(false)}
                      />
                    )}
                  </>
                ) : (
                  <ActionStackCard rows={stackRows} advisory={advisory} isSevere={isSevere} onDispatch={handleDispatch} />
                )}
              </div>
            </div>

            {/* Crisis Forecast Simulator — now wired with locations + selectedId for /simulate */}
            <CrisisForecastSimulator
              rain={rain}
              soil={soil}
              onRainChange={setRain}
              onSoilChange={setSoil}
              onBaseline={() => { setRain(15); setSoil(14); }}
              onSevere={() => { setRain(95); setSoil(52); }}
              onReset={() => { setRain(75); setSoil(38); }}
              tiles={tiles}
              locations={locations}
              selectedId={selectedId}
            />
          </>
        )}

        {activeTab === "infrastructure" && (
          <section style={{ border: "2px solid #1C1917", background: "#FEFCE8", padding: "1rem" }}>
            <div style={{ borderBottom: "2px solid #1C1917", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
              <h2 style={{ fontFamily: "Newsreader, serif", fontSize: 20, fontWeight: 800, margin: 0, textTransform: "uppercase", letterSpacing: "-0.02em" }}>
                Infrastructure Graph & Impact Assessment
              </h2>
              <p style={{ fontFamily: "Plus Jakarta Sans, sans-serif", fontSize: 12, color: "#44403C", margin: "4px 0 0" }}>
                Stranded-zone analysis · Hospital proximity · Alternative evacuation routes · Real data from <code>/infrastructure</code> &amp; <code>/impact-assessment</code>
              </p>
            </div>
            <InfrastructureGraph locations={locations} highSevereCount={highSevereCount} />
          </section>
        )}
      </main>

      <footer className="app-footer">
        <div className="foot-left">
          <span className="foot-item"><span className="dot" />LOCATIONS INDEXED: <span className="foot-val">{locations.length}</span></span>
          <span className="foot-item">INFERENCE LATENCY: <span className="foot-latency foot-illustrative">14ms (demo)</span></span>
          <span className="foot-item">GRAPH ENGINE: <span className="foot-graph">NetworkX v3.2</span></span>
          <span className="foot-item foot-source">RAINFALL: <span className="foot-source-val">IMD</span> · TERRAIN: <span className="foot-source-val">Bhuvan DEM</span> · MODEL: <span className="foot-source-val">{doc?.metadata?.model_version || "—"}</span></span>
        </div>
        <div className="foot-right">
          <span className="foot-model">MODEL: <span className="model-name">{doc?.metadata?.model_version || "—"}</span></span>
          <span className="foot-command">COMMAND CELL: WAYANAD DISTRICT HQ</span>
          <span className="foot-timestamp">Last updated: {now.toLocaleTimeString()}</span>
        </div>
      </footer>

      <DispatchModal open={modalOpen} sector={modalSector} location={modalLocation} onClose={() => setModalOpen(false)} onTransmit={handleTransmit} />
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}