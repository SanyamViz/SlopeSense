import { levelColor } from "./constants/risk";

export function computeHighSevereCount(locations) {
  return locations.filter((l) => l.risk_level === "high" || l.risk_level === "severe").length;
}

function makeRow(loc, rank, opts) {
  if (!loc) return null;
  const trust = loc.trust_score || {};
  const factors = (loc.factors || [])
    .slice()
    .sort((a, b) => (b.contribution ?? 0) - (a.contribution ?? 0))
    .slice(0, 4);
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
    factors,
    localAlert: loc.alert?.message_local || loc.alert?.message_en || "",
  };
}

export function buildStackRows(locations, isSevere, isCriticalSeverance, impactMap = {}) {
  const byId = {};
  for (const l of locations) byId[l.location_id] = l;
  const mundakkai = byId.loc_014 || byId["WAYANAD_2024_VAL"];
  const chooralmala = byId.loc_024;

  // Resolve the stranded / route status for each zone from the real
  // /impact-assessment data (same source InfrastructureGraph.jsx uses).
  const strandedOf = (id) => {
    const z = impactMap[id];
    if (!z) return null;
    return {
      stranded: z.alternative_routes
        ? z.alternative_routes.every((r) => r.unreachable)
        : false,
      alt: z.alternative_routes
        ? z.alternative_routes.find((r) => !r.unreachable)
        : null,
      nearbyHospitals: z.nearby_hospital_count,
      bedsFree: z.total_available_capacity_nearby,
    };
  };

  const roadFor = (loc) => {
    const s = strandedOf(loc.location_id);
    if (!s) return { status: "—", color: "#44403C" };
    if (s.stranded) return { status: "STRANDED — no route to shelter", color: "#DC2626" };
    if (s.alt) return { status: `Alt route: ${s.alt.safe_node_name} (${s.alt.hops} hops)`, color: "#15803D" };
    return { status: "Routes nominal", color: "#15803D" };
  };

  const trustOf = (loc) => {
    const t = loc.trust_score || {};
    return {
      accuracy: t.accuracy_pct ?? 0,
      correct: t.correct_count ?? 0,
      total: t.total_count ?? 0,
    };
  };

  const riskOf = (loc) => ({
    label: `Risk ${loc.risk_score.toFixed(1)}`,
    color: levelColor(loc.risk_level),
    bg: levelColor(loc.risk_level) + "1f",
  });

  const statusOf = (loc) => {
    if (loc.risk_level === "severe") return { status: "SEVERE", bg: "#FEE2E2", color: "#DC2626" };
    if (loc.risk_level === "high") return { status: "HIGH", bg: "#FEF3C7", color: "#B45309" };
    if (loc.risk_level === "moderate") return { status: "ELEVATED", bg: "#FEF3C7", color: "#B45309" };
    return { status: "OPEN", bg: "#ECFDF5", color: "#15803D" };
  };

  if (isSevere) {
    return [mundakkai, chooralmala].filter(Boolean).map((loc, i) => {
      const t = trustOf(loc);
      const r = riskOf(loc);
      const st = statusOf(loc);
      const road = roadFor(loc);
      const s = strandedOf(loc.location_id);
      const badge = s && s.stranded ? "STRANDED" : (loc.risk_level === "severe" ? "CUT OFF" : "ACTIVE");
      return makeRow(loc, i + 1, {
        status: st.status, statusBg: st.bg, statusColor: st.color,
        riskBg: r.bg, riskColor: r.color, riskLabel: r.label,
        trustText: `${t.accuracy.toFixed(0)}% (${t.correct}/${t.total})`,
        trustBadge: badge,
        trustBadgeBg: s && s.stranded ? "#FEF2F2" : "#ECFDF5",
        trustBadgeColor: s && s.stranded ? "#DC2626" : "#059669",
        trustColor: "#15803D",
        roadStatus: road.status, roadColor: road.color,
        urgencyTag: s && s.stranded ? "ISOLATED" : (loc.risk_level === "severe" ? "CUT OFF" : "ELEVATED"),
        urgencyTagStyle: { background: s && s.stranded ? "#DC2626" : (loc.risk_level === "severe" ? "#DC2626" : "#0052FF"), color: "#fff" },
      });
    });
  }

  // Non-severe view: list the top real locations by priority score, so the
  // stack reflects the actual dataset instead of hand-picked Wayanad sectors.
  const ranked = [...locations]
    .filter((l) => l.risk_level === "high" || l.risk_level === "moderate" || l.risk_level === "low")
    .sort((a, b) => (b.priority_score ?? 0) - (a.priority_score ?? 0))
    .slice(0, 3);

  return ranked.map((loc, i) => {
    const t = trustOf(loc);
    const r = riskOf(loc);
    const st = statusOf(loc);
    const road = roadFor(loc);
    const s = strandedOf(loc.location_id);
    return makeRow(loc, i + 1, {
      status: st.status, statusBg: st.bg, statusColor: st.color,
      riskBg: r.bg, riskColor: r.color, riskLabel: r.label,
      trustText: `${t.accuracy.toFixed(0)}% (${t.correct}/${t.total})`,
      trustBadge: s && s.stranded ? "STRANDED" : "MONITORED",
      trustBadgeBg: s && s.stranded ? "#FEF2F2" : "#ECFDF5",
      trustBadgeColor: s && s.stranded ? "#DC2626" : "#059669",
      trustColor: "#15803D",
      roadStatus: road.status, roadColor: road.color,
      urgencyTag: s && s.stranded ? "ISOLATED" : "MONITORED",
      urgencyTagStyle: { background: s && s.stranded ? "#DC2626" : "#0052FF", color: "#fff" },
    });
  });
}

export function computeHero(locations, isSevere, isCriticalSeverance, impactMap = {}) {
  const byId = {};
  for (const l of locations) byId[l.location_id] = l;

  const highSevere = locations.filter((l) => l.risk_level === "high" || l.risk_level === "severe");
  const sorted = [...highSevere].sort((a, b) => (b.priority_score ?? 0) - (a.priority_score ?? 0));
  const dangerCount = sorted.length;
  const dangerList = sorted.slice(0, 5).map((l) => l.name).join(", ") || "—";
  const highestSector = sorted.length
    ? `${sorted[0].name} (${sorted[0].risk_score.toFixed(0)}/100)`
    : "—";
  const stableCount = `${locations.length - dangerCount} sectors stable`;

  // Isolated population: sum the population of high/severe zones (real data).
  const cutoffPop = String(
    highSevere.reduce((sum, l) => sum + (l.vulnerability?.population || 0), 0).toLocaleString()
  );
  const cutoffDesc = highSevere.length
    ? highSevere.slice(0, 3).map((l) => `${l.name} (${(l.vulnerability?.population || 0).toLocaleString()})`).join(" + ")
    : "—";
  const isolationTag = "AIR/FOOT ONLY";
  const isolatedWards = `${highSevere.length} WARDS AT RISK`;

  // Priority target: the top location by priority score (real data).
  const priorityLoc = sorted.length ? sorted[0] : (locations.length ? locations[0] : null);
  const priorityTitle = priorityLoc ? priorityLoc.name : "—";
  const prioritySubtitle = priorityLoc
    ? `Population ${(priorityLoc.vulnerability?.population || 0).toLocaleString()} · ${priorityLoc.district} · ${priorityLoc.risk_level} risk`
    : "—";
  const priorityRoadStatus = priorityLoc && (impactMap[priorityLoc.location_id]?.alternative_routes?.every((r) => r.unreachable))
    ? "NO ROAD ACCESS"
    : (priorityLoc ? "EVACUATION ROUTES OPEN" : "—");
  const priorityRoadIcon = priorityRoadStatus === "NO ROAD ACCESS" ? "block" : "check_circle";
  const priorityRank = priorityLoc
    ? `PRIORITY RANK ${(priorityLoc.priority_score ?? 0).toFixed(1)}`
    : "PRIORITY RANK —";
  const priorityBadge = priorityLoc
    ? (priorityLoc.risk_level === "severe" ? "SEVERED & FLOOD SURGE" : priorityLoc.risk_level === "high" ? "HIGH RISK" : "MONITORED")
    : "—";

  return {
    priorityTarget: "PRIORITY #1 EVACUATION TARGET",
    priorityBadge, priorityTitle, prioritySubtitle, priorityRoadStatus, priorityRoadIcon, priorityRank,
    dangerCount, dangerRatio: `${dangerCount} / ${locations.length} ZONES`, dangerList, highestSector, stableCount,
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
  const count = highSevere.length;
  const priorityLoc = [...highSevere]
    .sort((a, b) => (b.priority_score ?? 0) - (a.priority_score ?? 0))[0];
  return [
    { key: "danger", value: String(count), color: "#DC2626", bg: "#FEF2F2", label: "High/Severe Zones", labelColor: "#991B1B" },
    { key: "cutoff", value: String(count), color: "#0284C7", bg: "#E0F2FE", label: "Zones At Risk", labelColor: "#0369A1" },
    { key: "priority", value: priorityLoc ? priorityLoc.name : "—", color: "#0052FF", bg: "#FEF9C3", label: "Priority #1 Target", labelColor: "#003EC7" },
  ];
}