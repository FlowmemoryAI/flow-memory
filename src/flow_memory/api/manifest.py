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
    EndpointSpec("GET", "/neural/status", "neural_status", "Neural subsystem status", response_fields=("ok", "torch_available", "cuda_available", "gpu_evidence_ok")),
    EndpointSpec("GET", "/neural/backends", "neural_backends", "List neural backend availability", response_fields=("backends",)),
    EndpointSpec("GET", "/neural/gpu-runs", "neural_gpu_runs", "List imported neural GPU evidence runs", response_fields=("runs",)),
    EndpointSpec("GET", "/neural/gpu-runs/{run_id}", "neural_gpu_run_detail", "Get imported neural GPU evidence run metadata", response_fields=("run",)),
    EndpointSpec("GET", "/neural/benchmarks", "neural_benchmarks", "List neural benchmark evidence metadata", response_fields=("benchmarks", "scripts")),
    EndpointSpec("GET", "/neural/checkpoints", "neural_checkpoints", "List neural checkpoint metadata without weights", response_fields=("checkpoints", "raw_weights_returned")),
    EndpointSpec("POST", "/neural/validate-smoke", "neural_validate_smoke", "Run local neural smoke validation", request_fields=("backend", "require_cuda"), response_fields=("ok", "backend", "environment", "gpu_evidence")),
    EndpointSpec("POST", "/neural/train-smoke", "neural_train_smoke", "Run local neural training smoke test", request_fields=("steps", "seed", "out"), response_fields=("ok", "out", "steps", "seed", "checkpoints", "raw_weights_returned")),
    EndpointSpec("POST", "/marketplace/assign", "marketplace_assign", "Assign a marketplace task"),
    EndpointSpec("POST", "/marketplace/submit", "marketplace_submit", "Submit marketplace work"),
    EndpointSpec("POST", "/marketplace/verify", "marketplace_verify", "Verify marketplace work"),
    EndpointSpec("POST", "/marketplace/dispute", "marketplace_dispute", "Open marketplace dispute"),
)


def endpoint_manifest() -> Mapping[str, Any]:
    return {"endpoints": tuple(endpoint.as_record() for endpoint in API_ENDPOINTS)}
