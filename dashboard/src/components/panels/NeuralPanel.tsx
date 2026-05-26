import type { VisualNetworkState } from "../../lib/visual-state";
import { gpuEvidenceLabel } from "../../lib/visual-state";

export function NeuralPanel({ state }: { state: VisualNetworkState }) {
  const signal = state.neural[0];
  const cognitive = state.cognitive?.[0];
  return (
    <section className="panel panel-neural">
      <header><span>Neural advisory</span><strong>{state.neural.length} neural · {state.cognitive?.length ?? 0} predictive</strong></header>
      {signal ? (
        <>
        <dl>
          <div><dt>Backend</dt><dd>{signal.backend}</dd></div>
          <div><dt>Status</dt><dd>{signal.status}</dd></div>
          <div><dt>Plan score</dt><dd>{signal.plan_score.toFixed(2)}</dd></div>
          <div><dt>Risk score</dt><dd>{signal.risk_score.toFixed(2)}</dd></div>
          <div><dt>Surprise</dt><dd>{signal.surprise_score.toFixed(2)}</dd></div>
          <div><dt>Prediction confidence</dt><dd>{Number(signal.prediction_confidence ?? Math.max(0.12, signal.plan_score)).toFixed(2)}</dd></div>
          <div><dt>GPU evidence</dt><dd>{gpuEvidenceLabel(state)}</dd></div>
        </dl>
        {cognitive ? (
          <dl>
            <div><dt>Predicted action</dt><dd>{cognitive.chosen_action}</dd></div>
            <div><dt>Prediction error</dt><dd>{Number(cognitive.prediction_error ?? 0).toFixed(2)}</dd></div>
            <div><dt>Lesson</dt><dd>{cognitive.lesson}</dd></div>
          </dl>
        ) : null}
        </>
      ) : <p>No neural signal in this replay. Neural models remain advisory and safety remains authoritative.</p>}
    </section>
  );
}
