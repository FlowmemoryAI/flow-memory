import type { VisualEconomyEdge } from "../../lib/visual-state";

const EDGE_LABELS: Record<string, string> = {
  bid: "Bid",
  task_assignment: "Assigned",
  escrow: "Escrow",
  verification: "Verified",
  settlement: "Settled",
  payment: "Payment",
  dispute: "Dispute",
  slashing: "Slashing",
  refund: "Refund",
};

export function EconomyEdge({ edge, index }: { edge: VisualEconomyEdge; index: number }) {
  const kind = (edge.kind || "payment").toLowerCase();
  const status = (edge.status || "observed").toLowerCase();
  const amount = Number(edge.amount || 0);
  return (
    <div
      className={`economy-edge economy-${kind} economy-status-${status}`}
      style={{ "--edge-index": index, "--edge-amount": Math.max(0.4, Math.min(4, amount || 1)) } as Record<string, number>}
      aria-label={`${kind} ${status}`}
    >
      <span className="economy-edge-track" />
      <span className="economy-edge-pulse" />
      <strong>{EDGE_LABELS[kind] ?? kind}</strong>
      <small>{amount.toFixed(2)} {edge.currency}</small>
    </div>
  );
}
