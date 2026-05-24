import type { VisualAgentNode } from "../../lib/visual-state";

export function AgentDetailDrawer({ agent }: { agent?: VisualAgentNode }) {
  if (!agent) return <aside className="agent-detail-drawer">Select an agent to inspect goals, risk, memory, and economy state.</aside>;
  return (
    <aside className="agent-detail-drawer">
      <h2>{agent.label}</h2>
      <dl>
        <dt>Role</dt><dd>{agent.role}</dd>
        <dt>Status</dt><dd>{agent.status}</dd>
        <dt>Reputation</dt><dd>{agent.reputation}</dd>
        <dt>Source event</dt><dd>{agent.source_event_id ?? "none"}</dd>
      </dl>
    </aside>
  );
}
