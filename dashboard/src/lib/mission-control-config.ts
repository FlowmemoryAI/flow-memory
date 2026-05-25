export type MissionControlMode = "mock" | "replay" | "live";

export type MissionControlEndpoint = {
  name: string;
  method: "GET" | "POST";
  path: string;
  mode: MissionControlMode;
  scope?: string;
};

export type MissionControlRunFixture = {
  fixture_id: string;
  label: string;
  description: string;
  path: string;
  run_kind: "launchpad" | "operations" | "supervisor" | "local_network" | "embodiment";
};

export type VisualFieldMapping = {
  visual: string;
  sourceField: string;
  meaning: string;
};

export const missionControlModes: MissionControlMode[] = ["mock", "replay", "live"];

export const missionControlEndpoints: MissionControlEndpoint[] = [
  { name: "visual state", method: "GET", path: "/visual/state", mode: "live", scope: "visual:read" },
  { name: "visual events", method: "GET", path: "/visual/events", mode: "live", scope: "visual:read" },
  { name: "network state", method: "GET", path: "/network/state", mode: "live", scope: "visual:read" },
  { name: "run network scenario", method: "POST", path: "/network/run-scenario", mode: "live", scope: "network:run" },
  { name: "supervisor status", method: "GET", path: "/launch/supervisor/status", mode: "live", scope: "launch:read" },
  { name: "run console", method: "GET", path: "/launch/console/runs", mode: "live", scope: "launch:read" },
  { name: "run console fixtures", method: "GET", path: "/launch/console/fixtures", mode: "live", scope: "launch:read" },
  { name: "public alpha demo bundle", method: "POST", path: "/launch/bundles/public-alpha", mode: "live", scope: "launch:export" },
  { name: "neural embodiment", method: "GET", path: "/visual/embodiment/{run_id}", mode: "live", scope: "visual:read" },
  { name: "run embodiment", method: "GET", path: "/launch/console/runs/{run_id}/embodiment", mode: "live", scope: "launch:read" },
  { name: "local replay", method: "GET", path: "dashboard/src/mock-data/local-network-replay.json", mode: "replay" },
  { name: "live neural agent launch replay", method: "GET", path: "dashboard/src/mock-data/live-neural-agent-launch.json", mode: "replay" },
  { name: "live agent operations replay", method: "GET", path: "dashboard/src/mock-data/live-agent-operations.json", mode: "replay" },
  { name: "live agent supervisor replay", method: "GET", path: "dashboard/src/mock-data/live-agent-supervisor.json", mode: "replay" },
  { name: "live neural embodiment replay", method: "GET", path: "dashboard/src/mock-data/live-neural-embodiment.json", mode: "replay" },
];

export const missionControlRunFixtures: MissionControlRunFixture[] = [
  {
    fixture_id: "live-neural-agent-launch",
    label: "Live Neural Agent Launch",
    description: "One-shot local neural-live agent launch replay.",
    path: "dashboard/src/mock-data/live-neural-agent-launch.json",
    run_kind: "launchpad",
  },
  {
    fixture_id: "live-agent-operations",
    label: "Live Agent Operations",
    description: "Run registry, replay, export, and stop/resume local operations replay.",
    path: "dashboard/src/mock-data/live-agent-operations.json",
    run_kind: "operations",
  },
  {
    fixture_id: "live-agent-supervisor",
    label: "Live Agent Supervisor",
    description: "Bounded supervisor heartbeat, tick, pause/resume, and stop replay.",
    path: "dashboard/src/mock-data/live-agent-supervisor.json",
    run_kind: "supervisor",
  },
  {
    fixture_id: "live-neural-embodiment",
    label: "Live Neural Embodiment",
    description: "3D-ready neural runtime/session, loop phase, policy gate, memory, learning, heartbeat, and GPU evidence replay.",
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

export const visualFieldMappings: VisualFieldMapping[] = [
  { visual: "agent node size", sourceField: "agent.reputation", meaning: "DID-bound local reputation" },
  { visual: "agent glow", sourceField: "neural.plan_score + neural.surprise_score", meaning: "advisory neural activity" },
  { visual: "risk halo", sourceField: "safety.risk_level", meaning: "policy/approval gate risk" },
  { visual: "gold edge", sourceField: "economy.amount + economy.status", meaning: "local simulated bid, escrow, settlement, dispute, or slashing event" },
  { visual: "blue memory flow", sourceField: "memory.importance", meaning: "memory write/retrieval/consolidation importance" },
  { visual: "RL pulse", sourceField: "rl.mean_reward + rl.safety_violation_rate", meaning: "Flow Arena training/evaluation result" },
  { visual: "embodied phase", sourceField: "embodiment.current_loop_phase", meaning: "current local neural agent loop phase" },
  { visual: "memory orbit", sourceField: "embodiment.memory_activation_count", meaning: "neural memory activations and memory records written" },
  { visual: "learning glow", sourceField: "embodiment.learning_tick_count", meaning: "local deterministic learning updates" },
  { visual: "GPU evidence badge", sourceField: "embodiment.gpu_evidence_status", meaning: "imported RunPod evidence status, not production ML certification" },
];

export function modeLabel(mode: MissionControlMode): string {
  if (mode === "live") return "live local API";
  if (mode === "replay") return "replay artifact";
  return "mock fallback";
}
