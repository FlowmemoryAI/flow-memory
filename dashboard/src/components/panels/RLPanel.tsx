import type { VisualNetworkState } from "../../lib/visual-state";

export function RLPanel({ state }: { state: VisualNetworkState }) {
  return <section className="panel panel-rl">RL episodes: {state.rl.length}</section>;
}
