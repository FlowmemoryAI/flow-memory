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
    `release evidence: ${snapshot.release.releaseDecision}`
  ];
}
