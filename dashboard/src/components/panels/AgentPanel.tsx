import type { VisualNetworkState } from "../../lib/visual-state";
import { agentNeuralActivity, agentRiskScore, recentEventsForAgent } from "../../lib/visual-state";

export function AgentPanel({ state }: { state: VisualNetworkState }) {
  const selected = state.agents[0];
  const recent = selected ? recentEventsForAgent(state, selected.agent_id, 4) : [];
  const activeTask = selected ? state.tasks.find((task) => task.requester_id === selected.agent_id || task.worker_id === selected.agent_id || task.verifier_id === selected.agent_id) : undefined;
  return (
    <section className="panel panel-agents">
      <header><span>Agents</span><strong>{state.agents.length}</strong></header>
      {selected ? (
        <div>
          <h3>{selected.label}</h3>
          <p>{selected.current_goal || activeTask?.label || "standing by for local network events"}</p>
          <dl>
            <div><dt>Role</dt><dd>{selected.role}</dd></div>
            <div><dt>Status</dt><dd>{selected.status}</dd></div>
            <div><dt>Reputation</dt><dd>{selected.reputation.toFixed(1)}</dd></div>
            <div><dt>Memory load</dt><dd>{state.memory.filter((item) => item.agent_id === selected.agent_id).length}</dd></div>
            <div><dt>Neural activity</dt><dd>{(agentNeuralActivity(state, selected.agent_id) * 100).toFixed(0)}%</dd></div>
            <div><dt>Risk score</dt><dd>{(agentRiskScore(state, selected.agent_id) * 100).toFixed(0)}%</dd></div>
          </dl>
          <ul>{recent.length ? recent.map((event) => <li key={event.audit_id}>{event.event_type} · {event.source_event_id}</li>) : <li>No recent agent-specific events in this replay.</li>}</ul>
        </div>
      ) : <p>No agents in current visual state.</p>}
    </section>
  );
}
