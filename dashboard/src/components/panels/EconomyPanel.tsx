import type { VisualNetworkState } from "../../lib/visual-state";
import { activeTasks, economyKindCount, settlementTotal } from "../../lib/visual-state";

export function EconomyPanel({ state }: { state: VisualNetworkState }) {
  const bids = economyKindCount(state, "bid");
  const escrow = economyKindCount(state, "escrow");
  const disputes = economyKindCount(state, "dispute");
  const slashing = economyKindCount(state, "slashing");
  return (
    <section className="panel panel-economy">
      <header><span>Local economy</span><strong>{state.economy.length}</strong></header>
      <dl>
        <div><dt>Active tasks</dt><dd>{activeTasks(state).length}</dd></div>
        <div><dt>Bids</dt><dd>{bids}</dd></div>
        <div><dt>Escrow</dt><dd>{escrow}</dd></div>
        <div><dt>Settlement</dt><dd>{settlementTotal(state).toFixed(2)} LOCAL_CREDITS</dd></div>
        <div><dt>Disputes</dt><dd>{disputes}</dd></div>
        <div><dt>Slashing</dt><dd>{slashing}</dd></div>
      </dl>
      <p className="panel-warning">Local simulated accounting only. No real funds, wallets, or chain transactions are used.</p>
    </section>
  );
}
