import type { VisualNetworkState } from "../../lib/visual-state";

export function EconomyPanel({ state }: { state: VisualNetworkState }) {
  const byKind = state.economy.reduce<Record<string, number>>((acc, edge) => {
    acc[edge.kind] = (acc[edge.kind] ?? 0) + 1;
    return acc;
  }, {});
  const total = state.economy.reduce((sum, edge) => sum + Number(edge.amount || 0), 0);
  return (
    <section className="panel panel-economy">
      <header><span>Local economy</span><strong>{state.economy.length}</strong></header>
      <dl>
        <div><dt>Active tasks</dt><dd>{state.tasks.length}</dd></div>
        <div><dt>Bid/assignment/escrow</dt><dd>{(byKind.bid ?? 0) + (byKind.task_assignment ?? 0) + (byKind.escrow ?? 0)}</dd></div>
        <div><dt>Settlement</dt><dd>{(byKind.settlement ?? 0) + (byKind.payment ?? 0)}</dd></div>
        <div><dt>Disputes/slashing</dt><dd>{(byKind.dispute ?? 0) + (byKind.slashing ?? 0)}</dd></div>
        <div><dt>Simulated value</dt><dd>{total.toFixed(2)} LOCAL_CREDITS</dd></div>
      </dl>
      <p className="panel-warning">Local simulated accounting only. No real funds are used.</p>
    </section>
  );
}
