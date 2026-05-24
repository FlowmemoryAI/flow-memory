export type MissionControlMode = "mock" | "replay" | "live";

export type MissionControlEndpoint = {
  name: string;
  method: "GET" | "POST";
  path: string;
  mode: MissionControlMode;
  scope?: string;
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
  { name: "local replay", method: "GET", path: "dashboard/src/mock-data/local-network-replay.json", mode: "replay" },
  { name: "live neural agent launch replay", method: "GET", path: "dashboard/src/mock-data/live-neural-agent-launch.json", mode: "replay" },
];

export const visualFieldMappings: VisualFieldMapping[] = [
  { visual: "agent node size", sourceField: "agent.reputation", meaning: "DID-bound local reputation" },
  { visual: "agent glow", sourceField: "neural.plan_score + neural.surprise_score", meaning: "advisory neural activity" },
  { visual: "risk halo", sourceField: "safety.risk_level", meaning: "policy/approval gate risk" },
  { visual: "gold edge", sourceField: "economy.amount + economy.status", meaning: "local simulated bid, escrow, settlement, dispute, or slashing event" },
  { visual: "blue memory flow", sourceField: "memory.importance", meaning: "memory write/retrieval/consolidation importance" },
  { visual: "RL pulse", sourceField: "rl.mean_reward + rl.safety_violation_rate", meaning: "Flow Arena training/evaluation result" },
];

export function modeLabel(mode: MissionControlMode): string {
  if (mode === "live") return "live local API";
  if (mode === "replay") return "replay artifact";
  return "mock fallback";
}
