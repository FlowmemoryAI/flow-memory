import type { VisualNeuralSignal } from "../../lib/visual-state";

export function NeuralHalo({ signal, index }: { signal: VisualNeuralSignal; index: number }) {
  const planScore = Math.max(0, Math.min(1, Number(signal.plan_score || 0)));
  const uncertainty = Math.max(0.05, Math.min(1, Number(signal.risk_score || 0) + Number(signal.surprise_score || 0) * 0.5));
  return (
    <div
      className={`neural-halo neural-${signal.status}`}
      aria-label={`neural advisory ${signal.backend}`}
      style={{ "--halo-index": index, "--plan-score": planScore, "--uncertainty": uncertainty } as Record<string, number>}
    >
      <span className="neural-halo-ring" />
      <span className="neural-halo-noise" />
      <small>{signal.backend}</small>
    </div>
  );
}
