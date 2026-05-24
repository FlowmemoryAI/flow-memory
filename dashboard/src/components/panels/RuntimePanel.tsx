import type { VisualNetworkState } from "../../lib/visual-state";

export function RuntimePanel({ state }: { state: VisualNetworkState }) {
  return <section className="panel panel-runtime">Runtime: {state.runtime.status} · {state.runtime.events} events</section>;
}
