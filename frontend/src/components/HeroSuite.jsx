import { levelColor, RISK_LABELS } from "../constants/risk";

/** Hero metric suite: 3-cell continuous Manila ledger bar. */
export default function HeroSuite({
  priorityTarget, priorityBadge, priorityTitle, prioritySubtitle,
  priorityRoadStatus, priorityRoadIcon, priorityRank,
  dangerCount, dangerRatio, dangerList, highestSector, stableCount,
  cutoffPop, cutoffDesc, isolationTag, isolatedWards, reconStatus,
  isSevere, isCriticalSeverance,
}) {
  const crit = isSevere;
  return (
    <section className="hero-suite">
      <div className="hero-box" style={{ background: "#FFFDF0" }}>
        <div className="box-head">
          <span className="box-tag" style={{ color: crit ? "#DC2626" : "#B45309" }}>
            <span className="dot" style={{ background: crit ? "#DC2626" : "#B45309" }} />{priorityTarget}
          </span>
          <span className="box-badge" style={{ background: crit ? "#FEF2F2" : "#ECFDF5", color: crit ? "#DC2626" : "#15803D", borderColor: crit ? "rgba(220,38,38,0.4)" : "rgba(21,128,61,0.4)" }}>
            {priorityBadge}
          </span>
        </div>
        <div className="py-1 my-auto">
          <h2 className="box-title" style={{ color: crit ? "#DC2626" : "#B45309" }}>{priorityTitle}</h2>
          <p className="box-sub">{prioritySubtitle}</p>
        </div>
        <div className="box-foot">
          <span className="box-road" style={{ color: crit ? "#DC2626" : "#15803D" }}>
            <span className="material-symbols-outlined text-[14px]">{priorityRoadIcon}</span>{priorityRoadStatus}
          </span>
          <span className="box-rank" style={{ color: crit ? "#DC2626" : "#0052FF", background: crit ? "#FEF2F2" : "#EFF6FF" }}>{priorityRank}</span>
        </div>
      </div>

      <div className="hero-box" style={{ background: "#FEF9C3" }}>
        <div className="box-head">
          <span className="box-tag">ZONES AT HIGH OR SEVERE RISK</span>
          <span className="box-badge" style={{ background: "#FEE2E2", color: "#DC2626", borderColor: "rgba(220,38,38,0.4)" }}>{dangerRatio}</span>
        </div>
        <div className="flex items-center gap-3.5 py-1 my-auto">
          <span className="box-title" style={{ color: crit ? "#DC2626" : "#B45309", fontSize: "clamp(48px, 5.4vw, 64px)" }}>{dangerCount}</span>
          <div className="flex flex-col min-w-0">
            <span className="font-serif-title text-[19px] md:text-[21px] text-[#1C1917] font-bold leading-tight truncate">Critical Sectors</span>
            <span className="font-sans-editorial text-[11.5px] text-[#44403C] mt-1 font-medium leading-tight">{dangerList}</span>
          </div>
        </div>
        <div className="box-foot">
          <span className="text-[11px] font-sans-editorial text-[#1C1917]">Highest: <strong className="text-[#DC2626] font-mono-dispatch font-bold">{highestSector}</strong></span>
          <span className="text-[#15803D] font-mono-dispatch font-bold uppercase tracking-wider text-[9.5px]">{stableCount}</span>
        </div>
      </div>

      <div className="hero-box" style={{ background: crit ? "#FFFDF0" : "#ECFDF5" }}>
        <div className="box-head">
          <span className="box-tag" style={{ color: crit ? "#0284C7" : "#15803D" }}>ISOLATED POPULATION</span>
          <span className="box-badge" style={{ background: crit ? "#E0F2FE" : "#ECFDF5", color: crit ? "#0284C7" : "#15803D", borderColor: crit ? "rgba(2,132,199,0.4)" : "rgba(21,128,61,0.4)" }}>{isolationTag}</span>
        </div>
        <div className="flex items-center gap-3 py-1 my-auto">
          <span className="box-title" style={{ color: crit ? "#0284C7" : "#15803D", fontSize: "clamp(38px, 4.4vw, 54px)" }}>{cutoffPop}</span>
          <div className="flex flex-col min-w-0">
            <span className="font-serif-title text-[19px] md:text-[21px] text-[#1C1917] font-bold leading-tight">Citizens Cut Off</span>
            <span className="font-sans-editorial text-[11.5px] text-[#44403C] mt-1 font-medium leading-tight">{cutoffDesc}</span>
          </div>
        </div>
        <div className="box-foot">
          <span className="text-[11px] font-sans-editorial text-[#1C1917]">{reconStatus}</span>
          <span className="font-mono-dispatch font-bold uppercase tracking-wider text-[9.5px]" style={{ color: crit ? "#0284C7" : "#15803D" }}>{isolatedWards}</span>
        </div>
      </div>
    </section>
  );
}