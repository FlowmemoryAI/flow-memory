import type { VisualNetworkState } from "../../lib/visual-state";

export function NeuralPanel({ state }: { state: VisualNetworkState }) {
  return <section className="panel panel-neural">Neural advisory signals: {state.neural.length}</section>;
}
