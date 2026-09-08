export default function Toast({ toast, onDismiss }) {
  if (!toast) return null;
  const d = new Date();
  const tStr = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")} IST`;
  return (
    <div className="toast-container show">
      <div className="toast-card">
        <span className="material-symbols-outlined toast-icon animate-pulse">cell_tower</span>
        <div className="toast-body">
          <div className="toast-head">
            <span className="toast-tag">SIREN BROADCAST SENT</span>
            <span className="toast-time">{tStr}</span>
          </div>
          <p className="toast-text">CRITICAL EVACUATION SIREN &amp; CAP SMS broadcast successfully transmitted across sector [{toast.sector.toUpperCase()}] via VHF 156.800 MHz.</p>
        </div>
      </div>
    </div>
  );
}