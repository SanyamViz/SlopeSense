import { levelColor } from "./constants/risk";

function makeRow(loc, rank, opts) {
  if (!loc) return null;
  const trust = loc.trust_score || {};
  return {
    id: loc.location_id,
    rank,
    name: loc.name,
    subtitle: opts.subtitle || `${loc.district} · Risk ${loc.risk_score}`,
    status: opts.status,
    statusBg: opts.statusBg, statusColor: opts.statusColor,
    riskBg: opts.riskBg, riskColor: opts.riskColor, riskLabel: opts.riskLabel,
    trustText: opts.trustText || `${trust.accuracy_pct ?? 0}%`,
    trustBadge: opts.trustBadge,
    trustBadgeBg: opts.trustBadgeBg, trustBadgeColor: opts.trustBadgeColor, trustColor: opts.trustColor,
    roadStatus: opts.roadStatus, roadColor: opts.roadColor,
    urgencyTag: opts.urgencyTag, urgencyTagStyle: opts.urgencyTagStyle,
  };
}

export function buildStackRows(locations, isSevere, isCriticalSeverance) {
  const byId = {};
  for (const l of locations) byId[l.location_id] = l;
  const mundakkai = byId.loc_014 || byId["WAYANAD_2024_VAL"];
  const chooralmala = byId.loc_024;
  const attamala = null;
  const punjirimattom = null;

  if (isSevere) {
    return [
      makeRow(mundakkai, 1, {
        status: "CUT OFF", statusBg: "#FEF2F2", statusColor: "#DC2626",
        riskBg: "#FEF2F2", riskColor: "#DC2626", riskLabel: "Risk 94.2",
        trustText: "88% (17/20 verified)",
        trustBadge: "AIR RECON LAUNCHED", trustBadgeBg: "#ECFDF5", trustBadgeColor: "#059669", trustColor: "#15803D",
        roadStatus: "BRIDGE SEVERED AT KM 14", roadColor: "#DC2626",
        urgencyTag: isCriticalSeverance ? "CRITICAL ISOLATION SEVERED" : "CUT OFF HIGHEST PRIORITY",
        urgencyTagStyle: isCriticalSeverance ? { background: "#DC2626", color: "#fff" } : { background: "#0052FF", color: "#fff" },
      }),
      makeRow(chooralmala, 2, {
        status: "SEVERE", statusBg: "#FEE2E2", statusColor: "#DC2626",
        riskBg: "#FEE2E2", riskColor: "#DC2626", riskLabel: "Risk 92",
        trustText: "82% (14/17 accurate)",
        trustBadge: "GROUND CORPS ON-SITE", trustBadgeBg: "#ECFDF5", trustBadgeColor: "#059669", trustColor: "#15803D",
        roadStatus: "Shelter: Higher Secondary School", roadColor: "#1C1917",
      }),
      makeRow(attamala, 3, {
        status: "HIGH", statusBg: "#FEF3C7", statusColor: "#B45309",
        riskBg: "#FEF3C7", riskColor: "#B45309", riskLabel: "Risk 78",
        trustText: "68% (11/16 accurate)",
        trustBadge: isCriticalSeverance ? "⚠️ SECONDARY VERIFICATION ADVISED" : "Secondary Verification",
        trustBadgeBg: isCriticalSeverance ? "#FEF3C7" : "#FDE68A",
        trustBadgeColor: isCriticalSeverance ? "#B45309" : "#92400E",
        trustColor: "#B45309",
        roadStatus: "Cut Off Spur", roadColor: "#0284C7",
      }),
      makeRow(punjirimattom, 4, {
        status: "SEVERE", statusBg: "#FEE2E2", statusColor: "#DC2626",
        riskBg: "#FEE2E2", riskColor: "#DC2626", riskLabel: "Risk 96",
        trustText: "64% (9/14 accurate)",
        trustBadge: isCriticalSeverance ? "⚠️ SECONDARY VERIFICATION ADVISED" : "Secondary Verification",
        trustBadgeBg: isCriticalSeverance ? "#FEF3C7" : "#FDE68A",
        trustBadgeColor: isCriticalSeverance ? "#B45309" : "#92400E",
        trustColor: "#B45309",
        roadStatus: "Origin Catchment", roadColor: "#DC2626",
      }),
    ];
  }
  return [
    makeRow(punjirimattom, 1, {
      status: "HIGH", statusBg: "#FEF3C7", statusColor: "#B45309",
      riskBg: "#FEF3C7", riskColor: "#B45309", riskLabel: "Risk 88",
      trustText: "Corridor: TRANSIT PASSABLE",
      trustBadge: "ALL SECTORS MONITORED", trustBadgeBg: "#ECFDF5", trustBadgeColor: "#059669", trustColor: "#15803D",
      roadStatus: "BRIDGE CLEAR · 15 KM/H", roadColor: "#15803D",
    }),
    makeRow(chooralmala, 2, {
      status: "ELEVATED", statusBg: "#FEF3C7", statusColor: "#B45309",
      riskBg: "#FEF3C7", riskColor: "#B45309", riskLabel: "Risk 72",
      trustText: "84%",
      trustBadge: "RIVERBED INFLOW STABLE", trustBadgeBg: "#ECFDF5", trustBadgeColor: "#059669", trustColor: "#15803D",
      roadStatus: "Bridge Passable", roadColor: "#15803D",
    }),
    makeRow(mundakkai, 3, {
      status: "OPEN", statusBg: "#ECFDF5", statusColor: "#15803D",
      riskBg: "#ECFDF5", riskColor: "#15803D", riskLabel: "Risk 42",
      trustText: "Corridor Status: SH 59 Connected",
      trustBadge: "NO ROAD CUT-OFF", trustBadgeBg: "#ECFDF5", trustBadgeColor: "#059669", trustColor: "#15803D",
      roadStatus: "Road Passable", roadColor: "#15803D",
    }),
    makeRow(attamala, 4, {
      status: "OPEN", statusBg: "#ECFDF5", statusColor: "#15803D",
      riskBg: "#ECFDF5", riskColor: "#15803D", riskLabel: "Risk 40",
      trustText: "Drainage: Stable",
      trustBadge: "NORMAL ACCESS", trustBadgeBg: "#ECFDF5", trustBadgeColor: "#15803D", trustColor: "#15803D",
      roadStatus: "Spur clear", roadColor: "#737688",
    }),
  ];
}

export function computeHero(locations, isSevere, isCriticalSeverance) {
  const byId = {};
  for (const l of locations) byId[l.location_id] = l;
  const mundakkai = byId.loc_014 || byId["WAYANAD_2024_VAL"];
  const chooralmala = byId.loc_024;
  const punjirimattom = byId.loc_052 || chooralmala;

  const highSevere = locations.filter((l) => l.risk_level === "high" || l.risk_level === "severe");
  const sorted = [...highSevere].sort((a, b) => b.risk_score - a.risk_score);
  const dangerCount = isCriticalSeverance ? Math.min(sorted.length + 1, 10) : sorted.length;
  const dangerList = isCriticalSeverance
    ? "Chooralmala, Mundakkai, Punjirimattom, Attamala, Vellarimala"
    : "Chooralmala, Mundakkai, Punjirimattom, Attamala";
  const stableCount = isCriticalSeverance ? "5 sectors stable" : "6 sectors stable";
  const highestSector = "Punjirimattom (96/100)";

  const cutoffPop = isCriticalSeverance ? "3,920" : "2,960";
  const cutoffDesc = isCriticalSeverance
    ? "Mundakkai (1,840) + Attamala (1,120) + Upper Vellarimala (960)"
    : "Mundakkai (1,840) + Attamala (1,120)";
  const isolationTag = isCriticalSeverance ? "AIR/FOOT ONLY" : "AIR/FOOT ONLY";
  const isolatedWards = isCriticalSeverance ? "3 WARDS ISOLATED" : "2 WARDS ISOLATED";

  const priorityTitle = isSevere ? "MUNDAKKAI" : "PUNJIRIMATTOM";
  const prioritySubtitle = isSevere
    ? `Population 1,840 · Upper slope catchment · ${isCriticalSeverance ? "Catastrophic debris blockage" : "Completely cut off"}`
    : "Population 960 · Upstream slope origin · Continuous saturation scan";
  const priorityRoadStatus = isSevere ? "NO ROAD ACCESS" : "ALL ROADS OPEN";
  const priorityRoadIcon = isSevere ? "block" : "check_circle";
  const priorityRank = isCriticalSeverance ? "PRIORITY RANK 98.4" : isSevere ? "PRIORITY RANK 94.2" : "PRIORITY RANK 62.0";
  const priorityBadge = isCriticalSeverance ? "SEVERED & FLOOD SURGE" : isSevere ? "BRIDGE SEVERED" : "TRANSIT PASSABLE";

  return {
    priorityTarget: "PRIORITY #1 EVACUATION TARGET",
    priorityBadge, priorityTitle, prioritySubtitle, priorityRoadStatus, priorityRoadIcon, priorityRank,
    dangerCount, dangerRatio: `${dangerCount} / 10 WARDS`, dangerList, highestSector, stableCount,
    cutoffPop, cutoffDesc, isolationTag, isolatedWards, reconStatus: "Helipad LZ reconnaissance active",
  };
}

export function computeAdvisory(isSevere, isCriticalSeverance) {
  if (!isSevere) {
    return {
      relPct: "88%", relNote: "5 Monsoon Cycles Synced", relColor: "#15803D",
      relBadge: "VERIFIED", relBadgeBg: "#ECFDF5", relBadgeColor: "#059669",
      en: "All arterial corridors open. Pre-monsoon drainage channels operating within nominal parameters.",
      ml: "എല്ലാ പാതകളും തുറന്നിരിക്കുന്നു. അടിയന്തര സാഹചര്യമില്ല.",
    };
  }
  return {
    relPct: isCriticalSeverance ? "92%" : "88%",
    relNote: isCriticalSeverance ? "6 Monsoon Cycles Synced" : "5 Monsoon Cycles Synced",
    relColor: isCriticalSeverance ? "#DC2626" : "#15803D",
    relBadge: isCriticalSeverance ? "CRITICAL" : "VERIFIED",
    relBadgeBg: isCriticalSeverance ? "#FEF2F2" : "#ECFDF5",
    relBadgeColor: isCriticalSeverance ? "#DC2626" : "#059669",
    en: isCriticalSeverance
      ? "CRITICAL PEAK: Soil moisture supersaturated. Massive slope runout active down to Chooralmala bridgehead."
      : "Risk elevated: heavy rainfall, steep slope saturation, fractured bridge.",
    ml: isCriticalSeverance
      ? "അതിതീവ്ര അപകടാവസ്ഥ: മണ്ണിൽ ജലാംശം പരമാവധിയിലെത്തി. മലവെള്ളപ്പാച്ചിൽ ചൂരൽമല ഭാഗത്തേക്ക് വ്യാപിക്കുന്നു."
      : "അപകടസാധ്യത അത്യന്തം ഗുരുതരമാണ്: ശക്തമായ മഴ, കുത്തനെ യുള്ള ചരിവ്, തകർന്ന പാലം.",
  };
}

export function computeTiles(locations, isSevere, isCriticalSeverance) {
  const highSevere = locations.filter((l) => l.risk_level === "high" || l.risk_level === "severe");
  const count = isCriticalSeverance ? Math.min(highSevere.length + 1, 10) : highSevere.length;
  const cutoff = isCriticalSeverance ? 3 : 2;
  return [
    { key: "danger", value: String(count), color: "#DC2626", bg: "#FEF2F2", label: "High/Severe Zones", labelColor: "#991B1B" },
    { key: "cutoff", value: String(cutoff), color: "#0284C7", bg: "#E0F2FE", label: "Cut-Off Wards", labelColor: "#0369A1" },
    { key: "priority", value: "Mundakkai", color: "#0052FF", bg: "#FEF9C3", label: "Priority #1 Target", labelColor: "#003EC7" },
  ];
}