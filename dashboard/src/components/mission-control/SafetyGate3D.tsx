import type { VisualSafetyGate } from "../../lib/visual-state";

export function SafetyGate3D({ gate, index }: { gate: VisualSafetyGate; index: number }) {
  const highRisk = gate.risk_level === "high" || gate.decision === "blocked";
  return (
    <div
      className={`safety-gate safety-${gate.risk_level}${gate.requires_approval ? " safety-approval" : ""}`}
      aria-label={`safety gate ${gate.decision}`}
      style={{ "--gate-index": index } as Record<string, number>}
    >
      <span className="safety-gate-shield" />
      <strong>{highRisk ? "blocked" : gate.decision}</strong>
      <small>{gate.requires_approval ? "approval required" : gate.risk_level}</small>
    </div>
  );
}
