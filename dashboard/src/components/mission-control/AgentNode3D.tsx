import type { VisualAgentNode } from "../../lib/visual-state";

export function AgentNode3D({ agent }: { agent: VisualAgentNode }) {
  const role = agent.role || "agent";
  const size = 32 + Math.max(0, agent.reputation) * 2;
  return (
    <button className={`agent-node agent-node-${role}`} style={{ width: size, height: size }} data-agent-id={agent.agent_id}>
      <span className="agent-node-glow" />
      <strong>{agent.label}</strong>
      <small>{role} · rep {agent.reputation}</small>
    </button>
  );
}
