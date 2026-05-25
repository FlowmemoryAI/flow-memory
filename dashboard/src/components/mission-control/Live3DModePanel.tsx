import type { NeuralEmbodimentPayload, VisualNetworkState } from "../../lib/visual-state";

export function Live3DModePanel({ state, payload }: { state: VisualNetworkState; payload: NeuralEmbodimentPayload }) {
  const embodiment = payload.embodiment;
  const visual = embodiment.visual ?? {};
  const heartbeat = embodiment.heartbeat_state ?? {};
  const live3DReady = Boolean(
    payload.ok &&
    visual.three_ready &&
    payload.graph.policy_gated &&
    embodiment.local_only &&
    embodiment.neural_advisory_only,
  );
  const safetyRails = [
    ["Authority", embodiment.policy_authority],
    ["Provider calls", embodiment.no_live_provider_calls ? "disabled" : "blocked"],
    ["Funds", embodiment.no_funds_moved ? "not moved" : "blocked"],
    ["Settlement", embodiment.no_live_settlement ? "disabled" : "blocked"],
  ];
  const sceneStyle = {
    "--confidence": embodiment.confidence_score,
    "--risk": embodiment.risk_score,
    "--node-scale": visual.node_scale ?? 1,
    "--memory-orbits": visual.memory_orbit_count ?? 0,
  } as Record<string, number>;

  return (
    <section
      className="live-3d-mode-panel"
      aria-label="Mission Control Live 3D Mode"
      data-live-3d-mode={live3DReady ? "ready" : "blocked"}
      data-source={state.provenance}
      data-gpu={embodiment.gpu_evidence_status}
    >
      <header>
        <div>
          <span>Mission Control Live 3D Mode</span>
          <strong>{live3DReady ? "3D telemetry ready" : "3D telemetry blocked"}</strong>
        </div>
        <small>{state.provenance} · {embodiment.backend} · {embodiment.gpu_evidence_status}</small>
      </header>
      <div className="live-3d-mode-body">
        <div className="live-3d-scene" style={sceneStyle} aria-label="Read-only live 3D neural scene preview">
          <div className="live-3d-grid" />
          <div className="live-3d-agent-body">
            <i className="live-3d-risk-shell" />
            <i className="live-3d-neural-core" />
            <b>{embodiment.current_loop_phase}</b>
          </div>
          <div className="live-3d-memory-orbit live-3d-memory-orbit-a" />
          <div className="live-3d-memory-orbit live-3d-memory-orbit-b" />
          <div className="live-3d-policy-gate">Policy gate: {embodiment.policy_gate_state}</div>
        </div>
        <div className="live-3d-readout">
          <h2>Local neural embodiment, rendered as a read-only 3D operations mode.</h2>
          <p>
            The scene is driven by replay/live API telemetry from the bounded local supervisor and neural runtime. It is WebGL-ready data surfaced through CSS 3D today; it does not start agents, contact providers, move funds, or bypass approval gates.
          </p>
          <dl>
            <div><dt>Run</dt><dd>{embodiment.run_id}</dd></div>
            <div><dt>Session</dt><dd>{embodiment.session_id}</dd></div>
            <div><dt>Heartbeat</dt><dd>{heartbeat.status ?? "observed"} · {heartbeat.ticks_completed ?? 0}/{heartbeat.max_ticks ?? 0}</dd></div>
            <div><dt>Confidence / risk</dt><dd>{embodiment.confidence_score.toFixed(3)} / {embodiment.risk_score.toFixed(3)}</dd></div>
            <div><dt>Memory / learning</dt><dd>{embodiment.memory_activation_count} / {embodiment.learning_tick_count}</dd></div>
            <div><dt>Replay index</dt><dd>{embodiment.replay_event_index}</dd></div>
          </dl>
        </div>
      </div>
      <div className="live-3d-loop-strip" aria-label={payload.graph.loop}>
        {payload.graph.nodes.map((node) => (
          <span key={node.id} className={`live-3d-loop-node live-3d-loop-node-${node.kind}`} data-active={node.active} title={node.source}>
            {node.label}<small>{node.status}</small>
          </span>
        ))}
      </div>
      <footer>
        {safetyRails.map(([label, value]) => <span key={label}>{label}: {value}</span>)}
      </footer>
    </section>
  );
}
