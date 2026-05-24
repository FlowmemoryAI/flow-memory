import type { VisualNetworkState } from "../../lib/visual-state";
import { agentRiskScore, recentEventsForAgent } from "../../lib/visual-state";

export function AgentPanel({ state }: { state: VisualNetworkState }) {
  const selected = state.agents[0];
  const recent = selected ? recentEventsForAgent(state, selected.agent_id, 3) : [];
  return (
    <section className="panel panel-agents">
      <header><span>Agents</span><strong>{state.agents.length}</strong></header>
      {selected ? (
        <div>
          <h3>{selected.label}</h3>
          <dl>
            <div><dt>Role</dt><dd>{selected.role}</dd></div>
            <div><dt>Status</dt><dd>{selected.status}</dd></div>
            <div><dt>Reputation</dt><dd>{selected.reputation.toFixed(1)}</dd></div>
            <div><dt>Memory load</dt><dd>{state.memory.filter((item) => item.agent_id === selected.agent_id).length}</dd></div>
            <div><dt>Risk score</dt><dd>{(agentRiskScore(state, selected.agent_id) * 100).toFixed(0)}%</dd></div>
          </dl>
          <ul>{recent.map((event) => <li key={event.audit_id}>{event.event_type} · {event.source_event_id}</li>)}</ul>
        </div>
      ) : <p>No agents in current visual state.</p>}
    </section>
  );
}
