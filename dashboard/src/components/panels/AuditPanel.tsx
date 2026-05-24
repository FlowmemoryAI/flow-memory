import type { VisualNetworkState } from "../../lib/visual-state";

export function AuditPanel({ state }: { state: VisualNetworkState }) {
  return <section className="panel panel-audit">Audit trail: {state.audit.length}</section>;
}
