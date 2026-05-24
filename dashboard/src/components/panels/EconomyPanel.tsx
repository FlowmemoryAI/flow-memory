import type { VisualNetworkState } from "../../lib/visual-state";

export function EconomyPanel({ state }: { state: VisualNetworkState }) {
  return <section className="panel panel-economy">Economy edges: {state.economy.length}</section>;
}
