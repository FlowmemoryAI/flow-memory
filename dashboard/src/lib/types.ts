export type DashboardSnapshot = {
  runtime: { status: string; mode: string };
  agents: unknown[];
  tasks: unknown[];
  disputes: unknown[];
  audit: unknown[];
  neural: { backend: string; status: string };
  rlBenchmarks: unknown[];
  launchPaths: unknown[];
  localNetwork: unknown[];
  paymentFlows: unknown[];
  release: { releaseDecision: string };
};
