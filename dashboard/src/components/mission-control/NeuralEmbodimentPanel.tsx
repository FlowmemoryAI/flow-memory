import type { NeuralEmbodimentPayload } from "../../lib/visual-state";

export function NeuralEmbodimentPanel({ payload }: { payload: NeuralEmbodimentPayload }) {
  const embodiment = payload.embodiment;
  const heartbeat = embodiment.heartbeat_state ?? {};
  const graph = payload.graph;
  const fields: [string, string][] = [
    ["Run", embodiment.run_id],
    ["Agent", embodiment.agent_id],
    ["Session", embodiment.session_id],
    ["Backend", embodiment.backend],
    ["GPU evidence", embodiment.gpu_evidence_status],
    ["Phase", embodiment.current_loop_phase],
    ["Policy", embodiment.policy_gate_state],
    ["Runtime", embodiment.neural_runtime_status],
    ["Heartbeat", heartbeat.status ?? "observed"],
    ["Ticks", `${heartbeat.ticks_completed ?? 0}/${heartbeat.max_ticks ?? 0}`],
    ["Confidence", embodiment.confidence_score.toFixed(3)],
    ["Risk", embodiment.risk_score.toFixed(3)],
    ["Memory", String(embodiment.memory_activation_count)],
    ["Learning", String(embodiment.learning_tick_count)],
  ];

  return (
    <section className="neural-embodiment-panel" aria-label="Neural embodiment state">
      <header>
        <span>Visible neural embodiment</span>
        <strong>{embodiment.current_loop_phase}</strong>
      </header>
      <div className="embodiment-hero" data-phase={embodiment.current_loop_phase} data-gpu={embodiment.gpu_evidence_status}>
        <div className="embodiment-avatar" style={{ "--confidence": embodiment.confidence_score, "--risk": embodiment.risk_score } as Record<string, number>}>
          <i />
          <b>{embodiment.current_loop_phase}</b>
        </div>
        <div>
          <h2>Policy-gated local neural agent</h2>
          <p>
            This is replay/live Mission Control state from the local neural runtime and supervisor artifacts. Neural outputs are advisory; PolicyEngine and ApprovalGate remain authoritative.
          </p>
          <small>Animation state: {embodiment.visual?.animation_state ?? "3d-ready"}</small>
        </div>
      </div>
      <dl className="embodiment-metrics">
        {fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
      <div className="neural-loop-graph" aria-label={graph.loop}>
        {graph.nodes.map((node) => (
          <div key={node.id} className={`loop-node loop-node-${node.kind}`} data-active={node.active} title={node.source}>
            <span>{node.label}</span>
            <small>{node.status}</small>
          </div>
        ))}
      </div>
      <footer>
        <span>{graph.loop}</span>
        <span>Replay event index {embodiment.replay_event_index}</span>
        <span>{embodiment.replay_artifact_path}</span>
      </footer>
    </section>
  );
}
