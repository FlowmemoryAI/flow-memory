import type { VisualAgentNode, VisualNetworkState } from "../../lib/visual-state";
import { agentNeuralActivity, agentRiskScore, recentEventsForAgent } from "../../lib/visual-state";

export function AgentDetailDrawer({ agent, state }: { agent?: VisualAgentNode; state?: VisualNetworkState }) {
  if (!agent) return <aside className="agent-detail-drawer empty">Select an agent to inspect goals, risk, memory, and economy state.</aside>;
  const memory = state?.memory.filter((item) => item.agent_id === agent.agent_id) ?? [];
  const economy = state?.economy.filter((edge) => edge.from_id === agent.agent_id || edge.to_id === agent.agent_id) ?? [];
  const recent = state ? recentEventsForAgent(state, agent.agent_id, 5) : [];
  const neural = state ? agentNeuralActivity(state, agent.agent_id) : 0;
  const risk = state ? agentRiskScore(state, agent.agent_id) : 0;
  return (
    <aside className="agent-detail-drawer">
      <header>
        <span>{agent.role}</span>
        <h2>{agent.label}</h2>
        <p>{agent.status} · source {agent.source_event_id ?? "none"}</p>
      </header>
      <dl className="agent-detail-metrics">
        <div><dt>Reputation</dt><dd>{agent.reputation.toFixed(1)}</dd></div>
        <div><dt>Memory load</dt><dd>{memory.length}</dd></div>
        <div><dt>Neural activity</dt><dd>{(neural * 100).toFixed(0)}%</dd></div>
        <div><dt>Risk</dt><dd>{(risk * 100).toFixed(0)}%</dd></div>
      </dl>
      <section>
        <h3>Capabilities</h3>
        <p>{agent.capabilities?.join(" · ") || "none declared"}</p>
      </section>
      <section>
        <h3>Economy state</h3>
        <p>{economy.length ? economy.map((edge) => `${edge.kind}:${edge.status}`).join(" · ") : "no active local edges"}</p>
      </section>
      <section>
        <h3>Recent events</h3>
        <ul>
          {recent.length ? recent.map((event) => <li key={event.audit_id}>{event.event_type} · {event.source_event_id}</li>) : <li>No recent events for this agent.</li>}
        </ul>
      </section>
    </aside>
  );
}
