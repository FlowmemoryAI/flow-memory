import type { VisualNetworkState } from "../../lib/visual-state";

export function NeuralPanel({ state }: { state: VisualNetworkState }) {
  const signal = state.neural[0];
  return (
    <section className="panel panel-neural">
      <header><span>Neural advisory</span><strong>{state.neural.length}</strong></header>
      {signal ? (
        <dl>
          <div><dt>Backend</dt><dd>{signal.backend}</dd></div>
          <div><dt>Status</dt><dd>{signal.status}</dd></div>
          <div><dt>Plan score</dt><dd>{signal.plan_score.toFixed(2)}</dd></div>
          <div><dt>Risk score</dt><dd>{signal.risk_score.toFixed(2)}</dd></div>
          <div><dt>Surprise</dt><dd>{signal.surprise_score.toFixed(2)}</dd></div>
          <div><dt>Prediction confidence</dt><dd>{Math.max(0.12, signal.plan_score).toFixed(2)}</dd></div>
          <div><dt>GPU evidence</dt><dd>external artifact required for GPU-gated releases</dd></div>
        </dl>
      ) : <p>No neural signal in this replay. Neural models remain advisory.</p>}
    </section>
  );
}
