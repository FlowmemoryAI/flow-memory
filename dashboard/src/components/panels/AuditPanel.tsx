import type { VisualNetworkState } from "../../lib/visual-state";

export function AuditPanel({ state }: { state: VisualNetworkState }) {
  const recent = state.audit.slice(-6).reverse();
  const policyEvents = state.safety.length;
  return (
    <section className="panel panel-audit">
      <header><span>Audit trail</span><strong>{state.audit.length}</strong></header>
      <p>{policyEvents} policy/safety decision record(s) attached to this state.</p>
      <ol>
        {recent.map((item) => (
          <li key={item.audit_id}>
            <b>{item.event_type}</b>
            <span>{item.actor_id}</span>
            <small>{item.source_event_id || "no source"}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}
