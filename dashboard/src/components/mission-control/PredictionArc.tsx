import type { VisualNeuralSignal } from "../../lib/visual-state";

export function PredictionArc({ signal, confidence }: { signal: VisualNeuralSignal; confidence: number }) {
  const normalized = Math.max(0.05, Math.min(1, confidence));
  return (
    <div className="prediction-arc" style={{ "--prediction-confidence": normalized } as Record<string, number>}>
      <span className="prediction-arc-line" />
      <span className="prediction-arc-head" />
      <small>prediction {(normalized * 100).toFixed(0)}% · {signal.agent_id}</small>
    </div>
  );
}
