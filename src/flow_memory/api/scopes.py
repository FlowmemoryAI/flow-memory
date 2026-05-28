"""API scope parsing and authorization checks for local/public-alpha seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.api.errors import ApiError, auth_error, forbidden_error
from flow_memory.api.request_context import RequestContext, build_request_context


READ_SCOPE = "api:read"
WRITE_SCOPE = "api:write"
ADMIN_SCOPE = "api:admin"
AUDIT_SCOPE = "api:audit"
NEURAL_READ_SCOPE = "neural:read"
NEURAL_VALIDATE_SCOPE = "neural:validate"
NEURAL_TRAIN_SCOPE = "neural:train"
NEURAL_EVIDENCE_SCOPE = "neural:evidence"
RL_READ_SCOPE = "rl:read"
RL_EVALUATE_SCOPE = "rl:evaluate"
RL_TRAIN_SCOPE = "rl:train"
AGENT_LAUNCH_SCOPE = "agents:launch"
LAUNCH_READ_SCOPE = "launch:read"
LAUNCH_RUN_SCOPE = "launch:run"
LAUNCH_EXPORT_SCOPE = "launch:export"
LAUNCH_CONTROL_SCOPE = "launch:control"
NETWORK_RUN_SCOPE = "network:run"
RELEASE_READ_SCOPE = "release:read"
DASHBOARD_READ_SCOPE = "dashboard:read"
VISUAL_READ_SCOPE = "visual:read"
VISUAL_STREAM_SCOPE = "visual:stream"
COMPUTE_READ_SCOPE = "compute:read"
COMPUTE_PLAN_SCOPE = "compute:plan"
COGNITION_READ_SCOPE = "cognition:read"
COGNITION_RUN_SCOPE = "cognition:run"
COGNITION_WRITE_SCOPE = "cognition:write"
GENESIS_READ_SCOPE = "genesis:read"
GENESIS_CREATE_SCOPE = "genesis:create"
GENESIS_TEACH_SCOPE = "genesis:teach"
GENESIS_EXPORT_SCOPE = "genesis:export"
INTERNET_READ_SCOPE = "internet:read"
INTERNET_WRITE_SCOPE = "internet:write"
INTERNET_MATCH_SCOPE = "internet:match"
INTERNET_COLLABORATE_SCOPE = "internet:collaborate"
INTERNET_EXPORT_SCOPE = "internet:export"
INTERNET_SIMULATE_SCOPE = "internet:simulate"
BYOK_READ_SCOPE = "byok:read"
BYOK_WRITE_SCOPE = "byok:write"
WALLET_READ_SCOPE = "wallet:read"
WALLET_WRITE_SCOPE = "wallet:write"
ONCHAIN_READ_SCOPE = "onchain:read"
ONCHAIN_PREPARE_SCOPE = "onchain:prepare"
ONCHAIN_APPROVE_SCOPE = "onchain:approve"
ONCHAIN_RELAY_SCOPE = "onchain:relay"
EMERGENCY_WRITE_SCOPE = "emergency:write"
X402_READ_SCOPE = "x402:read"
X402_PREPARE_SCOPE = "x402:prepare"
FORGE_READ_SCOPE = "forge:read"
FORGE_CREATE_SCOPE = "forge:create"
FORGE_SIMULATE_SCOPE = "forge:simulate"
EXPERIENCE_GRAPH_READ_SCOPE = "experience-graph:read"
EXPERIENCE_GRAPH_WRITE_SCOPE = "experience-graph:write"

KNOWN_SCOPES = frozenset({
    READ_SCOPE,
    WRITE_SCOPE,
    ADMIN_SCOPE,
    AUDIT_SCOPE,
    NEURAL_READ_SCOPE,
    NEURAL_VALIDATE_SCOPE,
    NEURAL_TRAIN_SCOPE,
    NEURAL_EVIDENCE_SCOPE,
    RL_READ_SCOPE,
    RL_EVALUATE_SCOPE,
    RL_TRAIN_SCOPE,
    AGENT_LAUNCH_SCOPE,
    LAUNCH_READ_SCOPE,
    LAUNCH_RUN_SCOPE,
    LAUNCH_EXPORT_SCOPE,
    LAUNCH_CONTROL_SCOPE,
    NETWORK_RUN_SCOPE,
    RELEASE_READ_SCOPE,
    DASHBOARD_READ_SCOPE,
    VISUAL_READ_SCOPE,
    VISUAL_STREAM_SCOPE,
    COMPUTE_READ_SCOPE,
    COMPUTE_PLAN_SCOPE,
    COGNITION_READ_SCOPE,
    COGNITION_RUN_SCOPE,
    COGNITION_WRITE_SCOPE,
    GENESIS_READ_SCOPE,
    GENESIS_CREATE_SCOPE,
    GENESIS_TEACH_SCOPE,
    GENESIS_EXPORT_SCOPE,
    INTERNET_READ_SCOPE,
    INTERNET_WRITE_SCOPE,
    INTERNET_MATCH_SCOPE,
    INTERNET_COLLABORATE_SCOPE,
    INTERNET_EXPORT_SCOPE,
    INTERNET_SIMULATE_SCOPE,
    BYOK_READ_SCOPE,
    BYOK_WRITE_SCOPE,
    WALLET_READ_SCOPE,
    WALLET_WRITE_SCOPE,
    ONCHAIN_READ_SCOPE,
    ONCHAIN_PREPARE_SCOPE,
    ONCHAIN_APPROVE_SCOPE,
    ONCHAIN_RELAY_SCOPE,
    EMERGENCY_WRITE_SCOPE,
    X402_READ_SCOPE,
    X402_PREPARE_SCOPE,
    FORGE_READ_SCOPE,
    FORGE_CREATE_SCOPE,
    FORGE_SIMULATE_SCOPE,
    EXPERIENCE_GRAPH_READ_SCOPE,
    EXPERIENCE_GRAPH_WRITE_SCOPE,

})
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})




@dataclass(frozen=True)
class ScopeDecision:
    ok: bool
    granted: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    error: ApiError | None = None

    def as_record(self) -> dict[str, object]:
        record: dict[str, object] = {"ok": self.ok, "granted": self.granted}
        if self.missing:
            record["missing"] = self.missing
        if self.invalid:
            record["invalid"] = self.invalid
        if self.error is not None:
            record["error"] = self.error.as_record()["error"]
        return record


def parse_scope_header(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    normalized = value.replace(",", " ")
    return tuple(sorted({part.strip() for part in normalized.split() if part.strip()}))


def context_from_headers(method: str, path: str, headers: Mapping[str, str]) -> RequestContext:
    scopes = parse_scope_header(_header(headers, "x-flow-memory-scopes"))
    return build_request_context(method, path, headers, scopes=scopes)


def require_scopes(
    context: RequestContext,
    required: tuple[str, ...] | list[str] | set[str] | None = None,
) -> ScopeDecision:
    default_required = required_scopes_for(context.method, context.path)
    required_scopes = tuple(sorted(set(required if required is not None else default_required)))
    granted = set(context.scopes)
    invalid = tuple(scope for scope in context.scopes if scope not in KNOWN_SCOPES)
    if invalid:
        return ScopeDecision(
            ok=False,
            granted=context.scopes,
            invalid=invalid,
            error=auth_error(
                "Invalid API scope",
                code="auth.invalid_scope",
                details={"invalid": invalid},
            ),
        )
    missing = tuple(
        scope for scope in required_scopes if scope not in granted and ADMIN_SCOPE not in granted
    )
    if missing:
        return ScopeDecision(
            ok=False,
            granted=context.scopes,
            missing=missing,
            error=forbidden_error(
                "Missing required API scope",
                details={"missing": missing},
            ),
        )
    return ScopeDecision(ok=True, granted=context.scopes)


def required_scopes_for(method: str, path: str) -> tuple[str, ...]:
    normalized_method = method.upper()
    normalized_path = path if path.startswith("/") else f"/{path}"
    path_key = normalized_path.rstrip("/") or "/"
    if path_key == "/audit":
        return (AUDIT_SCOPE,)
    if path_key.startswith("/neural/gpu-runs"):
        return (NEURAL_EVIDENCE_SCOPE,)
    if path_key == "/neural/validate-smoke":
        return (NEURAL_VALIDATE_SCOPE,)
    if path_key == "/neural/train-smoke":
        return (NEURAL_TRAIN_SCOPE,)
    if path_key.startswith("/neural/live/"):
        if normalized_method in READ_METHODS:
            return (NEURAL_READ_SCOPE,)
        if path_key.endswith("/learn"):
            return (NEURAL_TRAIN_SCOPE,)
        return (NEURAL_VALIDATE_SCOPE,)
    if path_key.startswith("/neural/"):
        return (NEURAL_READ_SCOPE,)
    if path_key in {"/agents/launch", "/agents/launch-flowlang", "/agents/launch-neural", "/launch/agent", "/launch/agent/from-flow"}:
        return (AGENT_LAUNCH_SCOPE,)
    if path_key == "/launch/supervisor/start":
        return (LAUNCH_RUN_SCOPE,)
    if path_key == "/launch/supervisor/status" or (path_key.startswith("/launch/supervisor/runs/") and normalized_method in READ_METHODS):
        return (LAUNCH_READ_SCOPE,)
    if path_key.startswith("/launch/supervisor/runs/") and path_key.endswith("/resume"):
        return (LAUNCH_RUN_SCOPE,)
    if path_key.startswith("/launch/supervisor/runs/") and (path_key.endswith("/pause") or path_key.endswith("/stop")):
        return (LAUNCH_CONTROL_SCOPE,)
    if path_key.startswith("/launch/console/runs/") and path_key.endswith("/predictions"):
        return (COGNITION_READ_SCOPE,)
    if path_key.startswith("/launch/console/"):
        return (LAUNCH_READ_SCOPE,)
    if path_key.startswith("/cognition/"):
        if normalized_method in READ_METHODS or path_key in {"/cognition/predict", "/cognition/memory/query"}:
            return (COGNITION_READ_SCOPE,)
        if path_key in {"/cognition/tick", "/cognition/benchmarks/run"}:
            return (COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE)
        if path_key == "/cognition/lessons/consolidate":
            return (COGNITION_WRITE_SCOPE,)
        return (COGNITION_WRITE_SCOPE,)
    if path_key.startswith("/genesis/"):
        if normalized_method in READ_METHODS:
            return (GENESIS_READ_SCOPE,)
        if path_key == "/genesis/birth":
            return (GENESIS_CREATE_SCOPE,)
        if path_key.endswith("/teaching"):
            return (GENESIS_TEACH_SCOPE,)
        if path_key == "/genesis/contributions/export":
            return (GENESIS_EXPORT_SCOPE,)
        return (GENESIS_CREATE_SCOPE,)
    if path_key.startswith("/internet/"):
        if path_key.startswith("/internet/erc8004/"):
            return (INTERNET_EXPORT_SCOPE,)
        if normalized_method in READ_METHODS:
            return (INTERNET_READ_SCOPE,)
        if path_key == "/internet/skills/match":
            return (INTERNET_MATCH_SCOPE,)
        if path_key == "/internet/collaborations/propose":
            return (INTERNET_COLLABORATE_SCOPE,)
        if path_key == "/internet/payment-intents/simulate":
            return (INTERNET_SIMULATE_SCOPE,)
        return (INTERNET_WRITE_SCOPE,)
    if path_key.startswith("/byok/"):
        if normalized_method in READ_METHODS:
            return (BYOK_READ_SCOPE,)
        return (BYOK_WRITE_SCOPE,)
    if path_key.startswith("/wallet/"):
        if normalized_method in READ_METHODS:
            return (WALLET_READ_SCOPE,)
        return (WALLET_WRITE_SCOPE,)
    if path_key.startswith("/onchain/"):
        if path_key.endswith("/relay"):
            return (ONCHAIN_RELAY_SCOPE,)
        if path_key.endswith("/approve"):
            return (ONCHAIN_APPROVE_SCOPE,)
        if normalized_method in READ_METHODS:
            return (ONCHAIN_READ_SCOPE,)
        return (ONCHAIN_PREPARE_SCOPE,)
    if path_key.startswith("/emergency-stop"):
        return (EMERGENCY_WRITE_SCOPE,)
    if path_key.startswith("/x402/"):
        if normalized_method in READ_METHODS:
            return (X402_READ_SCOPE,)
        return (X402_PREPARE_SCOPE,)
    if path_key.startswith("/forge/"):
        if normalized_method in READ_METHODS or path_key == "/forge/defaults":
            return (FORGE_READ_SCOPE,)
        if path_key == "/forge/simulate-upgrades":
            return (FORGE_SIMULATE_SCOPE,)
        return (FORGE_CREATE_SCOPE,)
    if path_key.startswith("/experience-graph"):
        if normalized_method in READ_METHODS:
            return (EXPERIENCE_GRAPH_READ_SCOPE,)
        return (EXPERIENCE_GRAPH_WRITE_SCOPE,)
    if path_key.startswith("/proof-of-learning") or path_key.startswith("/learning-reputation"):
        return (EXPERIENCE_GRAPH_READ_SCOPE,)
    if path_key.startswith("/visual/embodiment/") and path_key.endswith("/cognition"):
        return (COGNITION_READ_SCOPE,)
    if path_key.startswith("/visual/embodiment/"):
        return (VISUAL_READ_SCOPE,)
    if path_key in {"/launch/bundles/public-alpha", "/launch/finalize/public-alpha"}:
        return (LAUNCH_EXPORT_SCOPE,)
    if path_key == "/launch/runs" or path_key.startswith("/launch/runs/"):
        if normalized_method in READ_METHODS or path_key.endswith("/replay"):
            return (LAUNCH_READ_SCOPE,)
        if path_key.endswith("/export"):
            return (LAUNCH_EXPORT_SCOPE,)
        return (LAUNCH_RUN_SCOPE,)
    if path_key == "/network/run-scenario":
        return (NETWORK_RUN_SCOPE,)
    if path_key == "/rl/evaluate":
        return (RL_EVALUATE_SCOPE,)
    if path_key == "/rl/train-smoke":
        return (RL_TRAIN_SCOPE,)
    if path_key.startswith("/rl/"):
        return (RL_READ_SCOPE,)
    if path_key.startswith("/release/"):
        return (RELEASE_READ_SCOPE,)
    if path_key.startswith("/dashboard/"):
        return (DASHBOARD_READ_SCOPE,)
    if path_key.startswith("/compute/"):
        if normalized_method in READ_METHODS:
            return (COMPUTE_READ_SCOPE,)
        return (COMPUTE_PLAN_SCOPE,)
    if path_key.startswith("/visual/") or path_key == "/network/state":
        return (VISUAL_READ_SCOPE,)
    if path_key == "/events/stream":
        return (VISUAL_STREAM_SCOPE,)
    if normalized_method in READ_METHODS:
        return (READ_SCOPE,)
    return (WRITE_SCOPE,)


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return ""
