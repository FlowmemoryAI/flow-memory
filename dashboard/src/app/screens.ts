import type { DashboardSnapshot } from "../lib/types";

export function renderScreenNames(snapshot: DashboardSnapshot): string[] {
  return [
    `runtime health: ${snapshot.runtime.status}`,
    `agents: ${snapshot.agents.length}`,
    "agent state",
    "goals/plans",
    "skills",
    `marketplace: ${snapshot.tasks.length}`,
    `disputes: ${snapshot.disputes.length}`,
    `audit log: ${snapshot.audit.length}`,
    "reputation",
    "FlowLang compile/run",
    "Base Sepolia dry-run status",
    `neural status: ${snapshot.neural.backend}`,
    `RL benchmarks: ${snapshot.rlBenchmarks.length}`,
    `agent launch paths: ${snapshot.launchPaths.length}`,
    `local network scenarios: ${snapshot.localNetwork.length}`,
    `payment flows: ${snapshot.paymentFlows.length}`,
    `release evidence: ${snapshot.release.releaseDecision}`
  ];
}
