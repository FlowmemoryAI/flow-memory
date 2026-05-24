import { visualFieldMappings } from "../../lib/mission-control-config";

const LEGEND = [
  ["memory", "Blue", "retrieval and consolidation"],
  ["neural", "Violet", "advisory scoring and prediction"],
  ["economy", "Gold", "bid, escrow, settlement"],
  ["safety", "Orange/red", "approval, denial, dispute"],
  ["verification", "Green", "accepted work"],
  ["inactive", "Gray", "mock, replay, or idle"],
] as const;

export function NetworkLegend() {
  return (
    <aside className="network-legend" aria-label="visual semantics">
      <header>
        <span>Visual semantics</span>
        <strong>All motion maps to telemetry</strong>
      </header>
      <div className="legend-grid">
        {LEGEND.map(([kind, label, detail]) => (
          <p key={kind} className={`legend-item legend-${kind}`}><b>{label}</b><span>{detail}</span></p>
        ))}
      </div>
      <dl>
        {visualFieldMappings.slice(0, 4).map((item) => (
          <div key={item.visual}>
            <dt>{item.visual}</dt>
            <dd>{item.sourceField}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
