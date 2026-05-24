import type { VisualNetworkState } from "../../lib/visual-state";

export function AgentPanel({ state }: { state: VisualNetworkState }) {
  return <section className="panel">Agents: {state.agents.length}</section>;
}
