import type { ReplayEvent } from "./replay-controller";

export type RunKind = "launchpad" | "operations" | "supervisor" | "local_network" | "embodiment";

export type RunConsoleFixture = {
  fixture_id: string;
  label: string;
  description: string;
  path: string;
  run_kind: RunKind;
};

export type RunConsoleSummary = {
  run_id: string;
  run_kind: RunKind | string;
  agent_id: string;
  session_id?: string;
  supervisor_id?: string;
  template?: string;
  backend?: string;
  status: string;
  current_phase?: string;
  ticks_requested?: number;
  ticks_completed?: number;
  policy_gate_state?: string;
  risk_score?: number;
  confidence_score?: number;
  learning_steps?: number;
  memory_records_written?: number;
  visual_events_emitted?: number;
  replay_artifact_path?: string;
  run_record_path?: string;
  bundle_path?: string;
  gpu_evidence_status?: string;
  warnings?: string[];
  event_category_counts?: Record<string, number>;
};

export const runConsoleFixtures: RunConsoleFixture[] = [
  {
    fixture_id: "live-neural-agent-launch",
    label: "Live Neural Agent Launch",
    description: "One-shot local neural-live agent replay with policy-gated advisory neural steps.",
    path: "dashboard/src/mock-data/live-neural-agent-launch.json",
    run_kind: "launchpad",
  },
  {
    fixture_id: "live-agent-operations",
    label: "Live Agent Operations",
    description: "Run registry replay showing inspect, replay, export, stop, and continuation metadata.",
    path: "dashboard/src/mock-data/live-agent-operations.json",
    run_kind: "operations",
  },
  {
    fixture_id: "live-agent-supervisor",
    label: "Live Agent Supervisor",
    description: "Bounded supervisor heartbeat/tick replay for local neural-live operations.",
    path: "dashboard/src/mock-data/live-agent-supervisor.json",
    run_kind: "supervisor",
  },
  {
    fixture_id: "live-neural-embodiment",
    label: "Live Neural Embodiment",
    description: "3D-ready neural runtime, loop phase, policy gate, memory, learning, heartbeat, and GPU evidence replay.",
    path: "dashboard/src/mock-data/live-neural-embodiment.json",
    run_kind: "embodiment",
  },
  {
    fixture_id: "local-network-replay",
    label: "Local Network Replay",
    description: "Requester, worker, verifier, auditor, economy, safety, memory, RL, and compute replay.",
    path: "dashboard/src/mock-data/local-network-replay.json",
    run_kind: "local_network",
  },
];

export function eventCategoryCounts(events: ReplayEvent[]): Record<string, number> {
  const counts: Record<string, number> = {
    neural: 0,
    policy: 0,
    memory: 0,
    action: 0,
    supervisor: 0,
    "compute/economy": 0,
    "audit/safety": 0,
  };
  for (const event of events) {
    const payloadEvent = typeof event.payload?.event === "string" ? event.payload.event : "";
    if (event.event_type === "neural") counts.neural += 1;
    else if (event.event_type === "memory") counts.memory += 1;
    else if (event.event_type === "supervisor") counts.supervisor += 1;
    else if (event.event_type === "economy" || event.event_type === "compute") counts["compute/economy"] += 1;
    else if (event.event_type === "audit" || event.event_type === "safety") counts["audit/safety"] += 1;
    else counts.action += 1;
    if (event.event_type === "safety" || payloadEvent.includes("policy")) counts.policy += 1;
  }
  return counts;
}

export function summarizeRunFixture(fixture: RunConsoleFixture, payload: any): RunConsoleSummary {
  const summary = payload?.summary ?? {};
  const runRecord = payload?.run_record ?? {};
  const supervisor = payload?.supervisor ?? {};
  const embodiment = payload?.embodiment ?? {};
  const source = Object.keys(embodiment).length ? embodiment : Object.keys(supervisor).length ? supervisor : Object.keys(runRecord).length ? runRecord : summary;
  const state = payload?.state ?? {};
  const neural = Array.isArray(state.neural) ? state.neural : [];
  const latestNeural = neural.length ? neural[neural.length - 1] : {};
  const events = Array.isArray(payload?.events) ? payload.events : [];
  return {
    run_id: source.run_id ?? fixture.fixture_id,
    run_kind: fixture.run_kind,
    agent_id: source.agent_id ?? summary.agent_id ?? "",
    session_id: source.session_id ?? summary.session_id ?? latestNeural.session_id ?? "",
    supervisor_id: source.supervisor_id ?? supervisor.supervisor_id ?? "",
    template: source.template ?? summary.template ?? "",
    backend: source.backend ?? summary.backend ?? latestNeural.backend ?? "tiny_torch",
    status: source.status ?? (payload?.ok ? "completed" : "missing"),
    current_phase: source.current_loop_phase ?? supervisor.current_phase ?? latestNeural.phase ?? source.status ?? "observed",
    ticks_requested: source.tick_count_requested ?? supervisor.max_ticks ?? source.heartbeat_state?.max_ticks ?? summary.loop_ticks_completed ?? 0,
    ticks_completed: source.tick_count_completed ?? supervisor.ticks_completed ?? source.heartbeat_state?.ticks_completed ?? summary.loop_ticks_completed ?? 0,
    policy_gate_state: source.policy_gate_state ?? supervisor.policy_gate_state ?? latestNeural.policy_gate_state ?? "applied",
    risk_score: Number(source.risk_score ?? latestNeural.risk_score ?? 0),
    confidence_score: Number(source.confidence_score ?? latestNeural.prediction_confidence ?? 0),
    learning_steps: Number(source.learning_tick_count ?? summary.learning_steps ?? events.filter((event: ReplayEvent) => event.payload?.event === "neural_learning_step_completed").length),
    memory_records_written: Number(source.memory_activation_count ?? source.memory_records_written ?? summary.memory_records_written ?? (Array.isArray(state.memory) ? state.memory.length : 0)),
    visual_events_emitted: Number(source.visual_events_emitted ?? summary.visual_events_emitted ?? events.length),
    replay_artifact_path: source.replay_artifact_path ?? fixture.path,
    run_record_path: source.run_record_path ?? "",
    bundle_path: source.bundle_path ?? "",
    gpu_evidence_status: source.gpu_evidence_status ?? summary.gpu_evidence_status ?? "blocked_missing_artifact",
    warnings: [
      "local deterministic public-alpha demo only",
      "neural outputs are advisory and policy-gated",
    ],
    event_category_counts: eventCategoryCounts(events),
  };
}

export function runStatusFields(summary: RunConsoleSummary): [string, string][] {
  return [
    ["Run", summary.run_id],
    ["Kind", String(summary.run_kind)],
    ["Agent", summary.agent_id],
    ["Backend", summary.backend ?? ""],
    ["Status", summary.status],
    ["Phase", summary.current_phase ?? ""],
    ["Ticks", `${summary.ticks_completed ?? 0}/${summary.ticks_requested ?? 0}`],
    ["Policy", summary.policy_gate_state ?? ""],
    ["Risk", String(summary.risk_score ?? 0)],
    ["Confidence", String(summary.confidence_score ?? 0)],
    ["Memory", String(summary.memory_records_written ?? 0)],
    ["Events", String(summary.visual_events_emitted ?? 0)],
    ["GPU evidence", summary.gpu_evidence_status ?? "blocked_missing_artifact"],
  ];
}
