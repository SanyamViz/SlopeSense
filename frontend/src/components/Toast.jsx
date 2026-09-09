export default function Toast({ toast, onDismiss }) {
  if (!toast) return null;
  const d = new Date();
  const tStr = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")} IST`;

  const result = toast.result;
  const failedCount = result?.failed ?? 0;
  const successCount = result?.sent ?? 0;
  const hasResult = result && typeof result.sent === "number";
  const failedRecipients = (result?.results || []).filter((r) => !r.sid || r.status === "error");

  // A dispatch that errored before reaching the backend (no result object) is
  // surfaced as a failure rather than a fake success.
  const failed = !hasResult || failedCount > 0;
  const tag = failed ? "DISPATCH FAILED" : "SIREN BROADCAST SENT";
  const icon = failed ? "error" : "cell_tower";
  const headline = failed
    ? `SMS/WhatsApp dispatch failed for sector [${toast.sector.toUpperCase()}]`
    : `SMS/WhatsApp sent to ${successCount} number(s)`;

  const statusLines = (result?.results || []).map((r) => {
    const status = r.status || (r.sid ? "queued" : "error");
    return `${r.to}: ${status}${r.sid ? ` (${r.sid})` : ""}`;
  });

  return (
    <div className="toast-container show">
      <div className="toast-card">
        <span className={`material-symbols-outlined toast-icon ${failed ? "" : "animate-pulse"}`}>{icon}</span>
        <div className="toast-body">
          <div className="toast-head">
            <span className={`toast-tag ${failed ? "toast-tag-fail" : ""}`}>{tag}</span>
            <span className="toast-time">{tStr}</span>
          </div>
          <p className="toast-text">{headline}</p>
          {statusLines.length > 0 && (
            <div className="toast-statuses" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#44403C", marginTop: 4 }}>
              {statusLines.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          )}
          {failed && failedRecipients.length === 0 && (
            <p className="toast-text" style={{ color: "#DC2626", marginTop: 4 }}>
              {result?.error || "The backend rejected the dispatch request."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}