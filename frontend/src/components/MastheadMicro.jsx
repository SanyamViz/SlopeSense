import { levelColor, RISK_LABELS, RISK_LEVELS } from "../constants/risk";

/** Top micro bar / gazette metadata with live clock. */
export default function MastheadMicro({ title, cycle, live }) {
  return (
    <div className="masthead-micro">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="inline-flex items-center gap-2">
          <span className="pulse-dot" />
          <span className="font-bold tracking-widest text-[#DC2626]">{title}</span>
        </span>
        <span className="hidden sm:inline font-mono-dispatch text-[11px] text-[#44403C] font-semibold bg-[#EDE5CE] px-2.5 py-0.5 border border-[#1C1917]/30">
          {cycle}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="live-telemetry">
          <span className="dot" />LIVE TELEMETRY
        </span>
        <span className="clock">
          <span className="material-symbols-outlined text-[14px]">schedule</span>
          <span id="live-clock">{live}</span>
        </span>
      </div>
    </div>
  );
}