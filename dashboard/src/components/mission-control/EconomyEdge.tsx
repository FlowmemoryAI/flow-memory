import type { VisualEconomyEdge } from "../../lib/visual-state";

export function EconomyEdge({ edge }: { edge: VisualEconomyEdge }) {
  return <div className={`economy-edge economy-${edge.status}`}>{edge.kind}: {edge.amount} {edge.currency}</div>;
}
