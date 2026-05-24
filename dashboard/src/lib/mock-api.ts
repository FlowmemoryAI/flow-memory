import type { DashboardSnapshot } from "./types";

export const mockDashboardSnapshot: DashboardSnapshot = {
  runtime: { status: "ok", mode: "mock/replay/live local API" },
  agents: ["requester", "worker", "verifier", "auditor"],
  tasks: ["Public-alpha launch readiness task"],
  disputes: ["simulated local dispute/slashing path"],
  audit: ["visual replay generated from local network"],
  neural: { backend: "tiny_torch advisory", status: "prototype" },
  rlBenchmarks: ["safety_gate", "economy_market"],
  launchPaths: ["CLI", "FlowLang", "neural", "API", "local network"],
  localNetwork: ["basic-economy", "neural-agent", "rl-training", "dispute-slashing", "memory-learning", "safety-approval"],
  paymentFlows: ["local credits", "escrow", "settlement", "refund", "slashing"],
  release: { releaseDecision: "local-public-alpha" },
};

export const evidenceFiles = [
  "release_evidence/clean_clone_validation.json",
  "release_evidence/visual_system.json",
  "release_evidence/public_alpha_launch/summary.json",
];

export function dashboardSnapshot(): DashboardSnapshot {
  return mockDashboardSnapshot;
}
