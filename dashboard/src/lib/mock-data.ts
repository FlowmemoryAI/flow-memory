export const missionControlMockData = {
  replayPath: "dashboard/src/mock-data/local-network-replay.json",
  liveNeuralAgentLaunchPath: "dashboard/src/mock-data/live-neural-agent-launch.json",
  runtimePath: "dashboard/src/mock-data/runtime.json",
  neuralStatusPath: "dashboard/src/mock-data/neural-status.json",
  rlBenchmarksPath: "dashboard/src/mock-data/rl-benchmarks.json",
  paymentFlowsPath: "dashboard/src/mock-data/payments.json",
};

export function isMockModeLabel(label: string): boolean {
  return label.toLowerCase().includes("mock");
}
