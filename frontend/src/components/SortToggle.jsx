/** Toggle between ranking locations by raw hazard risk or by response priority. */
export default function SortToggle({ mode, onChange }) {
  const modes = ["risk", "priority"];
  const labels = { risk: "By Risk", priority: "By Priority" };
  const PRIORITY_COLOR = "#0052FF";
  return (
    <div className="sort-toggle" role="group" aria-label="Sort locations by">
      {modes.map((m) => (
        <button
          key={m}
          className={mode === m ? "active" : ""}
          onClick={() => onChange(m)}
          style={mode === m ? { color: PRIORITY_COLOR, borderColor: PRIORITY_COLOR } : undefined}
        >
          {labels[m]}
        </button>
      ))}
    </div>
  );
}