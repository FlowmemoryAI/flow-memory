import type { VisualAgentNode } from "../../lib/visual-state";

const ROLE_LABELS: Record<string, string> = {
  requester: "Requester",
  worker: "Worker",
  verifier: "Verifier",
  auditor: "Observer",
  observer: "Observer",
  treasury: "Treasury",
  governance: "Governance",
};

export function AgentNode3D({
  agent,
  index,
  neuralActivity,
  riskScore,
  approvalRequired,
  memoryLoad,
}: {
  agent: VisualAgentNode;
  index: number;
  neuralActivity: number;
  riskScore: number;
  approvalRequired: boolean;
  memoryLoad: number;
}) {
  const role = (agent.role || "agent").toLowerCase();
  const position = agent.position ?? [Math.cos(index) * 4, 0, Math.sin(index) * 3];
  const size = Math.max(54, Math.min(96, 48 + agent.reputation * 5));
  const dimmed = agent.status === "error" || agent.status === "inactive";
  return (
    <button
      className={`agent-node agent-node-${role}${approvalRequired ? " agent-node-approval" : ""}${dimmed ? " agent-node-dimmed" : ""}`}
      style={{
        "--node-size": `${size}px`,
        "--node-x": `${50 + position[0] * 8}%`,
        "--node-y": `${50 + position[2] * 8}%`,
        "--neural-activity": neuralActivity,
        "--risk-score": riskScore,
      } as Record<string, string | number>}
      data-agent-id={agent.agent_id}
      aria-label={`${agent.label} ${ROLE_LABELS[role] ?? role}`}
    >
      <span className="agent-node-risk" />
      <span className="agent-node-glow" />
      <span className="agent-node-core">
        <span className="agent-node-role-mark" />
        <strong>{agent.label}</strong>
        <small>{ROLE_LABELS[role] ?? role} · rep {agent.reputation.toFixed(1)}</small>
      </span>
      <span className="agent-node-meta">mem {memoryLoad} · risk {(riskScore * 100).toFixed(0)}%</span>
    </button>
  );
}
