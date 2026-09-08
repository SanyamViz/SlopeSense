import { levelColor, RISK_LABELS } from "../constants/risk";

/** Top bar: title, live KPI tiles, search. */
export default function TopBar({
  counts,
  total,
  modelVersion,
  generatedAt,
  search,
  onSearch,
}) {
  return (
    <div className="masthead-title-bar">
      <div>
        <div className="brand-row">
          <span className="brand-tag">SLOPESENSE</span>
          <span className="text-[#1C1917]/40 text-[11px] font-mono-dispatch font-bold">|</span>
          <span className="font-mono-dispatch text-[10.5px] uppercase font-bold tracking-[0.18em] text-[#1C1917]">
            TACTICAL COMMAND CONSOLE · WAYANAD
          </span>
        </div>
        <h1>Slope Sense</h1>
      </div>
      <div className="flex flex-wrap items-center gap-3 pb-1 self-start lg:self-auto">
        <span className="px-3.5 py-1 bg-[#FEF2F2] border border-[#DC2626]/50 text-[#DC2626] font-mono-dispatch text-[11px] font-bold uppercase tracking-wider flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#DC2626] animate-ping"></span>
          CRITICAL COMMAND STATE
        </span>
      </div>
    </div>
  );
}

function formatTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}