import { useEffect, useState } from "react";
import { levelColor } from "../constants/risk";
import { playSiren } from "../hooks/useSiren";
import { dispatchAlert } from "../api/riskClient";

const SECTOR_MESSAGES = {
  Mundakkai: {
    en: "EVACUATE IMMEDIATELY: Chooralmala Bridge severed. Proceed on foot to North Helipad LZ.",
    ml: "ഉടൻ ഒഴിയുക: ചൂരൽമല പാലം തകർന്നു. കാൽനടയായി വടക്കൻ ഹെലിപാഡിലേക്ക് നീങ്ങുക.",
  },
  Chooralmala: {
    en: "CRITICAL WARNING: River inundation breaching bridge approach. Move immediately to Higher Secondary School Shelter.",
    ml: "അതീവ ജാഗ്രത: നദി കരകവിഞ്ഞ് ഒഴുകുന്നു. ഉടൻ ഹയർ സെക്കൻഡറി സ്കൂൾ ദുരിതാശ്വാസ ക്യാമ്പിലേക്ക് മാറുക.",
  },
  Attamala: {
    en: "SPUR ISOLATION ADVISORY: Upper ridge runoff active. Assemble at Attamala High Ridge Helipad pickup zone.",
    ml: "റോഡ് ബന്ധം വിച്ഛേദിക്കപ്പെട്ടു: മലമുകളിലെ വെള്ളപ്പാച്ചിൽ ശക്തമാണ്. അട്ടമല ഹെലിപാഡ് കേന്ദ്രത്തിൽ എത്തുക.",
  },
  Punjirimattom: {
    en: "IMMINENT DEBRIS RUNOUT WATCH: Slope slip detected upstream. Immediate clearance of stream banks ordered.",
    ml: "മണ്ണിടച്ചിൽ സാധ്യത: പുഞ്ചിരിമട്ടത്ത് മലവെള്ളപ്പാച്ചിൽ സാധ്യത. അരുവികളുടെ തീരത്തുനിന്ന് ഉടനടി മാറുക.",
  },
};

/** Resolve the real alert text for a sector, falling back to the hardcoded map. */
function sectorMessages(sector, location) {
  if (location?.alert) {
    return {
      en: location.alert.message_en || SECTOR_MESSAGES[sector]?.en || "",
      ml: location.alert.message_local || SECTOR_MESSAGES[sector]?.ml || "",
    };
  }
  return SECTOR_MESSAGES[sector] || SECTOR_MESSAGES.Mundakkai;
}

export default function DispatchModal({ open, sector, location, onClose, onTransmit }) {
  const [transmitting, setTransmitting] = useState(false);
  const [error, setError] = useState(null);

  // Reset transient UI state whenever the modal opens/closes or sector changes.
  useEffect(() => {
    setTransmitting(false);
    setError(null);
  }, [open, sector]);

  if (!open || !sector) return null;
  const msg = sectorMessages(sector, location);
  const locationId = location?.location_id || sector;

  const handleTransmit = async () => {
    setTransmitting(true);
    setError(null);
    playSiren();
    try {
      const result = await dispatchAlert({
        sector,
        locationId,
        messageEn: msg.en,
        messageLocal: msg.ml,
        channel: "whatsapp",
      });
      console.log("[DispatchModal] Success:", result);
      onTransmit(sector, result);
    } catch (err) {
      console.error("[DispatchModal] Dispatch failed:", err);
      setError(err.message || "Dispatch failed");
      setTransmitting(false);
    }
  };

  return (
    <div className="dispatch-modal-backdrop show" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dispatch-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="sector-title">
            <span className="dot"></span>EMERGENCY BROADCAST TRANSMISSION CELL — SECTOR [{sector.toUpperCase()}]
          </span>
          <button className="modal-close" onClick={onClose} type="button">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="modal-body">
          <div>
            <div className="modal-section-title">
              <span>1. CELL BROADCAST (SMS / CAP TRANSMISSION)</span>
              <span className="geo-tag">GEO-TARGETED RECEPTACLE</span>
            </div>
            <div className="cap-preview">
              <div className="cap-en">
                <span className="material-symbols-outlined text-[18px]">warning</span>
                <span id="modal-alert-en">{msg.en}</span>
              </div>
              <div className="cap-ml" id="modal-alert-ml">{msg.ml}</div>
            </div>
          </div>
          <div className="vhf-relay">
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px] vhf-icon">radio</span>
              <span>AUTOMATED VHF RELAY</span>
            </span>
            <span className="vhf-status">CH 156.800 MHz — Repeaters Armed &amp; Transmitting</span>
          </div>
          <div className="signoff">
            <span>AUTHORITY SIGN-OFF:</span>
            <span className="auth-val">VERIFIED (District Collector Triage Cell)</span>
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn btn-cancel" onClick={onClose} type="button">[ CANCEL / DISARM ]</button>
          <button
            className={`btn btn-transmit ${transmitting ? "opacity-70 cursor-wait" : ""}`}
            onClick={handleTransmit}
            disabled={transmitting}
            type="button"
          >
            <span className="material-symbols-outlined text-[15px]">send</span>
            {transmitting ? "[ TRANSMITTING… ]" : error ? "[ RETRY TRANSMIT ]" : "[ TRANSMIT LIVE ALERT ]"}
          </button>
        </div>
        {error && (
          <div className="modal-error" style={{ color: "#DC2626", fontSize: 11, fontFamily: "JetBrains Mono, monospace", marginTop: 8 }}>
            ⚠ DISPATCH FAILED: {error}
          </div>
        )}
      </div>
    </div>
  );
}