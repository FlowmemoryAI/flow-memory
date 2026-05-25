export type VisualProvenance = "live" | "replay" | "mock" | "synthetic";

export type VisualAgentNode = {
  agent_id: string;
  label: string;
  role: string;
  status: string;
  reputation: number;
  capabilities?: string[];
  current_goal?: string;
  position?: [number, number, number];
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualTaskNode = {
  task_id: string;
  label: string;
  status: string;
  requester_id?: string;
  worker_id?: string;
  verifier_id?: string;
  reward?: number;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
  ignored_regressions?: string[];
};

export type VisualMemoryNode = {
  memory_id: string;
  agent_id: string;
  kind: string;
  summary: string;
  importance: number;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualEconomyEdge = {
  edge_id: string;
  from_id: string;
  to_id: string;
  kind: string;
  amount: number;
  currency: string;
  status: string;
  task_id?: string;
  reputation_delta?: number;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualNeuralSignal = {
  signal_id: string;
  agent_id: string;
  backend: string;
  status: string;
  plan_score: number;
  risk_score: number;
  surprise_score: number;
  memory_score?: number;
  uncertainty?: number;
  prediction_confidence?: number;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualComputeMarketSignal = {
  signal_id: string;
  agent_id: string;
  task_id: string;
  event: string;
  status: string;
  provider_id?: string;
  route_id?: string;
  quote_total?: number;
  payment_rail?: string;
  dry_run_only?: boolean;
  no_funds_moved?: boolean;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualSupervisorSignal = {
  signal_id: string;
  supervisor_id: string;
  run_id: string;
  agent_id: string;
  session_id: string;
  backend: string;
  status: string;
  current_phase?: string;
  ticks_completed?: number;
  max_ticks?: number;
  policy_gate_state?: string;
  last_heartbeat_at?: string;
  parent_run_id?: string;
  bounded?: boolean;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualRLEpisode = {
  episode_id: string;
  agent_id: string;
  env_id: string;
  mean_reward: number;
  success_rate: number;
  safety_violation_rate: number;
  policy: string;
  before_after?: { before?: number; after?: number };
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualSafetyGate = {
  gate_id: string;
  agent_id: string;
  decision: string;
  risk_level: string;
  requires_approval: boolean;
  reason: string;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualAuditTrailItem = {
  audit_id: string;
  event_type: string;
  actor_id: string;
  summary: string;
  ok: boolean;
  provenance?: VisualProvenance | string;
  source_event_id?: string;
};

export type VisualRuntimeHealth = {
  status: string;
  agents: number;
  tasks: number;
  events: number;
  warnings?: string[];
  ignored_regressions?: string[];
};

export type VisualNetworkState = {
  schema_version: string;
  provenance: VisualProvenance | string;
  runtime: VisualRuntimeHealth;
  agents: VisualAgentNode[];
  tasks: VisualTaskNode[];
  memory: VisualMemoryNode[];
  economy: VisualEconomyEdge[];
  neural: VisualNeuralSignal[];
  rl: VisualRLEpisode[];
  compute?: VisualComputeMarketSignal[];
  supervisor?: VisualSupervisorSignal[];
  safety: VisualSafetyGate[];
  audit: VisualAuditTrailItem[];
  layout?: { layout_version: string; seed: number; positions: Record<string, [number, number, number]> };
};

export function summarizeVisualState(state: VisualNetworkState): string {
  return `${state.runtime.events} events · ${state.agents.length} agents · ${state.tasks.length} tasks · ${state.provenance}`;
}

export function agentNeuralActivity(state: VisualNetworkState, agentId: string): number {
  const signals = state.neural.filter((signal) => signal.agent_id === agentId);
  if (!signals.length) return 0;
  return clamp(Math.max(...signals.map((signal) => Number(signal.plan_score || 0) * 0.7 + Number(signal.surprise_score || 0) * 0.3)));
}

export function agentRiskScore(state: VisualNetworkState, agentId: string): number {
  const neuralRisk = Math.max(0, ...state.neural.filter((signal) => signal.agent_id === agentId).map((signal) => Number(signal.risk_score || 0)));
  const safetyRisk = Math.max(0, ...state.safety.filter((gate) => gate.agent_id === agentId).map((gate) => gate.risk_level === "high" || gate.decision === "blocked" ? 1 : gate.requires_approval ? 0.72 : gate.risk_level === "medium" ? 0.45 : 0.12));
  return clamp(Math.max(neuralRisk, safetyRisk));
}

export function recentEventsForAgent(state: VisualNetworkState, agentId: string, limit = 5): VisualAuditTrailItem[] {
  return state.audit
    .filter((event) => event.actor_id === agentId || event.source_event_id?.includes(agentId) || event.summary?.includes(agentId))
    .slice(-limit)
    .reverse();
}

export function selectedAgentEconomy(state: VisualNetworkState, agentId: string): VisualEconomyEdge[] {
  return state.economy.filter((edge) => edge.from_id === agentId || edge.to_id === agentId);
}

export function economyKindCount(state: VisualNetworkState, kind: string): number {
  return state.economy.filter((edge) => edge.kind === kind || edge.status === kind).length;
}

export function settlementTotal(state: VisualNetworkState): number {
  return state.economy
    .filter((edge) => edge.kind === "settlement" || edge.status === "settled")
    .reduce((sum, edge) => sum + Number(edge.amount || 0), 0);
}

export function activeTasks(state: VisualNetworkState): VisualTaskNode[] {
  const terminal = new Set(["settled", "slashed"]);
  return state.tasks.filter((task) => !terminal.has((task.status || "").toLowerCase()));
}

export function gpuEvidenceLabel(state: VisualNetworkState): string {
  const evidenceSignal = state.neural.find((signal) => signal.status === "gpu_evidence" || signal.backend === "gpu_evidence");
  if (evidenceSignal) return evidenceSignal.status;
  return "external RunPod artifact required for GPU-gated releases";
}

function clamp(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}
