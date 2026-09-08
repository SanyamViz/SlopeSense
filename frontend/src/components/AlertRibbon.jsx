import { levelColor, RISK_LABELS } from "../constants/risk";

/** Editorial alert ribbon — dynamic based on simulator state. */
export default function AlertRibbon({
  isSevere,
  isCriticalSeverance,
  gaugeReadout,
  alertText,
  alertIcon,
}) {
  const ok = !isSevere;
  return (
    <div
      className={`alert-ribbon ${ok ? "ok" : ""}`}
      style={ok ? {} : { background: "var(--crit)" }}
    >
      <div className="flex items-center gap-2 font-sans-editorial font-bold text-[12px] md:text-[13.5px] tracking-tight text-white flex-1 min-w-0">
        <span
          className="material-symbols-outlined text-[18px] text-white shrink-0"
          style={ok ? {} : { animation: "pulse-intense 1.6s infinite" }}
        >
          {alertIcon}
        </span>
        <span className="truncate sm:whitespace-normal uppercase tracking-wide">
          {alertText}
        </span>
      </div>
      <div className="self-start sm:self-auto shrink-0 flex items-center gap-2 font-mono-dispatch text-[11px] font-bold bg-[#1C1917] text-white px-2.5 py-0.5 uppercase tracking-wider border border-white/20">
        <span className="text-stone-300">IRUVAIPUZHA GAUGE:</span>
        <span
          className="px-1.5 font-extrabold"
          style={{ color: ok ? "#15803D" : "#DC2626", background: ok ? "#ECFDF5" : "#fff" }}
        >
          {gaugeReadout}
        </span>
      </div>
    </div>
  );
}