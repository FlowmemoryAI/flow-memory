"""API endpoint manifest for the dependency-free local router."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class EndpointSpec:
    method: str
    path: str
    name: str
    description: str
    request_fields: Sequence[str] = field(default_factory=tuple)
    response_fields: Sequence[str] = field(default_factory=tuple)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "name": self.name,
            "description": self.description,
            "request_fields": tuple(self.request_fields),
            "response_fields": tuple(self.response_fields),
        }


API_ENDPOINTS: tuple[EndpointSpec, ...] = (
    EndpointSpec("GET", "/health", "health", "Router health check", response_fields=("ok", "service")),
    EndpointSpec("GET", "/runtime/status", "runtime_status", "Local runtime status"),
    EndpointSpec("POST", "/runtime/tick", "runtime_tick", "Advance local runtime tick"),
    EndpointSpec("GET", "/agents", "agents_list", "List registered agent cards"),
    EndpointSpec("GET", "/agents/{did}", "agents_get", "Get a registered agent card"),
    EndpointSpec("GET", "/agents/{did}/memory", "agent_memory", "Get local memory records for an agent"),
    EndpointSpec("GET", "/agents/{did}/skills", "agent_skills", "Get skills associated with an agent"),
    EndpointSpec("POST", "/agents/{did}/run", "agent_run", "Run a local agent cycle placeholder"),
    EndpointSpec("POST", "/agents/launch", "agents_launch", "Launch a local agent through the API", request_fields=("goal", "name", "identity", "autonomy_mode")),
    EndpointSpec("POST", "/agents/launch-flowlang", "agents_launch_flowlang", "Launch a FlowLang-declared agent through the API", request_fields=("source", "goal")),
    EndpointSpec("POST", "/agents/launch-neural", "agents_launch_neural", "Launch a neural-advisory agent through the API", request_fields=("goal", "backend")),
    EndpointSpec("POST", "/launch/agent", "launch_agent", "Run the Live Agent Launchpad workflow", request_fields=("template", "ticks", "neural", "emit_visual"), response_fields=("summary", "events", "state")),
    EndpointSpec("POST", "/launch/agent/from-flow", "launch_agent_from_flow", "Run the Live Agent Launchpad workflow from FlowLang source", request_fields=("source", "ticks", "neural", "emit_visual"), response_fields=("summary", "events", "state")),
    EndpointSpec("GET", "/launch/runs", "launch_runs_list", "List local Live Agent Launchpad run records", response_fields=("runs",)),
    EndpointSpec("GET", "/launch/runs/{run_id}", "launch_run_get", "Inspect one local Live Agent Launchpad run record", response_fields=("run",)),
    EndpointSpec("POST", "/launch/runs/{run_id}/replay", "launch_run_replay", "Return replay metadata for a local Live Agent Launchpad run", response_fields=("run", "replay_artifact_path", "summary")),
    EndpointSpec("POST", "/launch/runs/{run_id}/export", "launch_run_export", "Export a lightweight local run bundle", request_fields=("out",), response_fields=("bundle_path", "record")),
    EndpointSpec("POST", "/launch/runs/{run_id}/stop", "launch_run_stop", "Stop or no-op a local Live Agent Launchpad run", response_fields=("status_before", "status_after", "noop")),
    EndpointSpec("POST", "/launch/supervisor/start", "launch_supervisor_start", "Start a bounded local Live Agent Supervisor run", request_fields=("template", "ticks", "tick_interval_ms", "neural", "emit_visual"), response_fields=("supervisor", "heartbeat", "run")),
    EndpointSpec("GET", "/launch/supervisor/status", "launch_supervisor_status", "Inspect local Live Agent Supervisor status", response_fields=("runs", "latest_run_id")),
    EndpointSpec("GET", "/launch/supervisor/runs/{run_id}", "launch_supervisor_get", "Inspect one local Live Agent Supervisor run", response_fields=("supervisor",)),
    EndpointSpec("GET", "/launch/supervisor/runs/{run_id}/heartbeat", "launch_supervisor_heartbeat", "Inspect heartbeat metadata for a supervised run", response_fields=("heartbeat",)),
    EndpointSpec("POST", "/launch/supervisor/runs/{run_id}/pause", "launch_supervisor_pause", "Pause a non-terminal supervised run or return a terminal no-op", response_fields=("status_before", "status_after", "noop")),
    EndpointSpec("POST", "/launch/supervisor/runs/{run_id}/resume", "launch_supervisor_resume", "Create a continuation run from supervised metadata", request_fields=("ticks", "emit_visual"), response_fields=("supervisor", "continued_from_run_id")),
    EndpointSpec("POST", "/launch/supervisor/runs/{run_id}/stop", "launch_supervisor_stop", "Stop a non-terminal supervised run or return a terminal no-op", response_fields=("status_before", "status_after", "noop")),
    EndpointSpec("GET", "/launch/console/runs", "launch_console_runs", "List Mission Control run console summaries", response_fields=("runs", "fixtures")),
    EndpointSpec("GET", "/launch/console/runs/{run_id}", "launch_console_run", "Inspect one Mission Control run console summary", response_fields=("run", "source")),
    EndpointSpec("GET", "/launch/console/fixtures", "launch_console_fixtures", "List Mission Control replay/demo fixtures", response_fields=("fixtures",)),
    EndpointSpec("POST", "/launch/bundles/public-alpha", "launch_bundle_public_alpha", "Build a local public-alpha demo bundle", request_fields=("out",), response_fields=("bundle_path", "mission_control_fixtures", "commands")),
    EndpointSpec("GET", "/launch/console/runs/{run_id}/embodiment", "launch_console_run_embodiment", "Return the 3D-ready neural embodiment state for a Mission Control run", response_fields=("embodiment", "graph", "events")),
    EndpointSpec("POST", "/launch/finalize/public-alpha", "launch_finalize_public_alpha", "Finalize local public-alpha handoff evidence", request_fields=("out",), response_fields=("finalizer_path", "mission_control_live_3d", "release_decisions")),
    EndpointSpec("GET", "/visual/embodiment/{run_id}", "visual_embodiment", "Return the Mission Control neural embodiment projection for a run", response_fields=("embodiment", "graph", "events")),
    EndpointSpec("POST", "/marketplace/tasks", "marketplace_task_create", "Create a local marketplace task", request_fields=("title", "reward", "requester", "metadata")),
    EndpointSpec("POST", "/marketplace/bids", "marketplace_bid_create", "Create a local marketplace bid", request_fields=("task_id", "agent_did", "price")),
    EndpointSpec("POST", "/marketplace/settle", "marketplace_settle", "Settle a local marketplace task"),
    EndpointSpec("GET", "/reputation/{did}", "reputation_lookup", "Look up DID-bound reputation"),
    EndpointSpec("POST", "/attestations", "attestation_create", "Record a local attestation"),
    EndpointSpec("GET", "/audit", "audit_log", "Read local API audit events"),
    EndpointSpec("GET", "/swarm/agents", "swarm_agents", "List local swarm agents"),
    EndpointSpec("POST", "/swarm/delegate", "swarm_delegate", "Create and assign a local delegation contract", request_fields=("delegator_did", "delegate_did", "capability", "objective", "budget", "constraints")),
    EndpointSpec("POST", "/verification/submit", "verification_submit_alias", "Submit a verification result"),
    EndpointSpec("POST", "/verification/{contract_id}", "verification_submit", "Submit completion and optional verification for a delegation", request_fields=("result", "accepted", "evidence")),
    EndpointSpec("GET", "/verification/result", "verification_result_alias", "Get the latest verification result"),
    EndpointSpec("GET", "/verification/{contract_id}", "verification_result", "Get delegation verification status"),
    EndpointSpec("GET", "/manifest", "manifest", "List router endpoints"),
    EndpointSpec("POST", "/flowlang/compile", "flowlang_compile", "Compile FlowLang source to FlowIR manifest", request_fields=("source",)),
    EndpointSpec("POST", "/flowlang/validate", "flowlang_validate", "Validate FlowLang source", request_fields=("source",)),
    EndpointSpec("POST", "/flowlang/run", "flowlang_run", "Run a FlowLang-declared agent", request_fields=("source", "prompt")),
    EndpointSpec("GET", "/flowlang/examples", "flowlang_examples", "Return bundled FlowLang examples"),
    EndpointSpec("POST", "/marketplace/assign", "marketplace_assign", "Assign a marketplace task"),
    EndpointSpec("POST", "/marketplace/submit", "marketplace_submit", "Submit marketplace work"),
    EndpointSpec("POST", "/marketplace/verify", "marketplace_verify", "Verify marketplace work"),
    EndpointSpec("POST", "/marketplace/dispute", "marketplace_dispute", "Open marketplace dispute"),
    EndpointSpec("GET", "/neural/status", "neural_status", "Return neural subsystem status"),
    EndpointSpec("GET", "/neural/backends", "neural_backends", "List neural backend metadata"),
    EndpointSpec("GET", "/neural/gpu-runs", "neural_gpu_runs", "List imported GPU validation runs"),
    EndpointSpec("GET", "/neural/gpu-runs/{run_id}", "neural_gpu_run", "Get imported GPU validation run summary"),
    EndpointSpec("GET", "/neural/benchmarks", "neural_benchmarks", "List neural benchmark metadata"),
    EndpointSpec("GET", "/neural/checkpoints", "neural_checkpoints", "List checkpoint metadata without raw weights"),
    EndpointSpec("POST", "/neural/validate-smoke", "neural_validate_smoke", "Return neural validation smoke command/status"),
    EndpointSpec("POST", "/neural/train-smoke", "neural_train_smoke", "Run tiny local neural smoke trainers", request_fields=("out",)),
    EndpointSpec("POST", "/neural/live/sessions", "neural_live_create", "Create a local neural live runtime session", request_fields=("agent_id", "config"), response_fields=("session",)),
    EndpointSpec("GET", "/neural/live/sessions", "neural_live_sessions", "List local neural live runtime sessions"),
    EndpointSpec("GET", "/neural/live/sessions/{session_id}", "neural_live_session", "Inspect a local neural live runtime session"),
    EndpointSpec("POST", "/neural/live/sessions/{session_id}/step", "neural_live_step", "Run one deterministic local neural live step", request_fields=("context",)),
    EndpointSpec("POST", "/neural/live/sessions/{session_id}/learn", "neural_live_learn", "Run one deterministic local neural learning update", request_fields=("sample",)),
    EndpointSpec("POST", "/neural/live/sessions/{session_id}/checkpoint", "neural_live_checkpoint", "Write neural checkpoint metadata only", request_fields=("checkpoint_ref",)),
    EndpointSpec("POST", "/neural/live/sessions/{session_id}/stop", "neural_live_stop", "Stop a local neural live runtime session"),
    EndpointSpec("GET", "/rl/envs", "rl_envs", "List local Flow Arena environments"),
    EndpointSpec("GET", "/rl/benchmarks", "rl_benchmarks", "List local RL benchmark metadata"),
    EndpointSpec("POST", "/rl/evaluate", "rl_evaluate", "Evaluate a local RL policy", request_fields=("env_id", "policy", "episodes")),
    EndpointSpec("POST", "/rl/train-smoke", "rl_train_smoke", "Run local tabular Q smoke training", request_fields=("env_id", "episodes")),
    EndpointSpec("POST", "/network/run-scenario", "network_run_scenario", "Run a local network scenario", request_fields=("scenario",)),
    EndpointSpec("GET", "/release/evidence", "release_evidence", "Return local release evidence bundle metadata"),
    EndpointSpec("GET", "/release/decision/{target}", "release_decision", "Return local release readiness decision for a target"),
    EndpointSpec("GET", "/dashboard/snapshot", "dashboard_snapshot", "Return local dashboard mock snapshot metadata"),
    EndpointSpec("GET", "/visual/state", "visual_state", "Return current Mission Control visual state"),
    EndpointSpec("GET", "/visual/events", "visual_events", "Return recent Mission Control visual events"),
    EndpointSpec("GET", "/visual/schema", "visual_schema", "Return Mission Control visual telemetry schema"),
    EndpointSpec("GET", "/visual/replay/{run_id}", "visual_replay", "Return a saved visual replay snapshot"),
    EndpointSpec("GET", "/network/state", "network_state", "Return current local network state with visual projection"),
    EndpointSpec("POST", "/visual/replay/start", "visual_replay_start", "Run a local visual replay scenario", request_fields=("scenario", "run_id")),
    EndpointSpec("POST", "/compute/plan", "compute_plan", "Build a dry-run Compute Market plan", request_fields=("goal", "task", "policy")),
    EndpointSpec("POST", "/compute/marketplace-plan", "compute_marketplace_plan", "Build a full dry-run Compute Market plan and record economic memory", request_fields=("task", "policy")),
    EndpointSpec("POST", "/compute/quote", "compute_quote", "Generate a deterministic dry-run compute quote", request_fields=("task", "route_id")),
    EndpointSpec("POST", "/compute/route", "compute_route", "Select a policy-bounded dry-run compute route", request_fields=("task", "policy")),
    EndpointSpec("POST", "/compute/payment-plan", "compute_payment_plan", "Generate dry-run payment intent metadata", request_fields=("task", "policy")),
    EndpointSpec("POST", "/compute/simulate-settlement", "compute_simulate_settlement", "Simulate local settlement without moving funds", request_fields=("task", "policy")),
    EndpointSpec("GET", "/compute/providers", "compute_providers", "List local dry-run compute providers"),
    EndpointSpec("GET", "/compute/routes", "compute_routes", "List local dry-run compute routes"),
    EndpointSpec("GET", "/compute/policies", "compute_policies", "List local dry-run compute policies"),
    EndpointSpec("GET", "/compute/capacity", "compute_capacity", "List local dry-run capacity windows"),
    EndpointSpec("GET", "/compute/economic-memory", "compute_economic_memory", "Return dry-run compute economic memory records"),
    EndpointSpec("POST", "/compute/economic-memory/query", "compute_economic_memory_query", "Query dry-run compute economic memory records", request_fields=("route_id", "provider_id", "goal_id")),
)


def endpoint_manifest() -> Mapping[str, Any]:
    return {"endpoints": tuple(endpoint.as_record() for endpoint in API_ENDPOINTS)}
