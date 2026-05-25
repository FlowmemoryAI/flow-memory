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
NETWORK_RUN_SCOPE = "network:run"
RELEASE_READ_SCOPE = "release:read"
DASHBOARD_READ_SCOPE = "dashboard:read"
VISUAL_READ_SCOPE = "visual:read"
VISUAL_STREAM_SCOPE = "visual:stream"
COMPUTE_READ_SCOPE = "compute:read"
COMPUTE_PLAN_SCOPE = "compute:plan"
COMPUTE_WRITE_SCOPE = "compute:write"
COMPUTE_ADMIN_SCOPE = "compute:admin"
COMPUTE_AUDIT_SCOPE = "compute:audit"
COMPUTE_PROVIDER_ADMIN_SCOPE = "compute:provider-admin"
COMPUTE_POLICY_ADMIN_SCOPE = "compute:policy-admin"
COMPUTE_SETTLEMENT_ADMIN_SCOPE = "compute:settlement-admin"
COMPUTE_EXECUTE_SCOPE = "compute:execute"
COMPUTE_BILLING_SCOPE = "compute:billing"
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
    NETWORK_RUN_SCOPE,
    RELEASE_READ_SCOPE,
    DASHBOARD_READ_SCOPE,
    VISUAL_READ_SCOPE,
    VISUAL_STREAM_SCOPE,
    COMPUTE_READ_SCOPE,
    COMPUTE_PLAN_SCOPE,
    COMPUTE_WRITE_SCOPE,
    COMPUTE_ADMIN_SCOPE,
    COMPUTE_AUDIT_SCOPE,
    COMPUTE_PROVIDER_ADMIN_SCOPE,
    COMPUTE_POLICY_ADMIN_SCOPE,
    COMPUTE_SETTLEMENT_ADMIN_SCOPE,
    COMPUTE_EXECUTE_SCOPE,
    COMPUTE_BILLING_SCOPE,
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
    admin_scopes = {ADMIN_SCOPE, COMPUTE_ADMIN_SCOPE}
    missing = tuple(
        scope for scope in required_scopes if scope not in granted and not (admin_scopes & granted)
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
    if path_key.startswith("/auth/"):
        return (ADMIN_SCOPE,)
    if path_key.startswith("/neural/gpu-runs"):
        return (NEURAL_EVIDENCE_SCOPE,)
    if path_key == "/neural/validate-smoke":
        return (NEURAL_VALIDATE_SCOPE,)
    if path_key == "/neural/train-smoke":
        return (NEURAL_TRAIN_SCOPE,)
    if path_key.startswith("/neural/"):
        return (NEURAL_READ_SCOPE,)
    if path_key in {"/agents/launch", "/agents/launch-flowlang", "/agents/launch-neural"}:
        return (AGENT_LAUNCH_SCOPE,)
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
    if path_key.startswith("/visual/") or path_key == "/network/state":
        return (VISUAL_READ_SCOPE,)
    if path_key == "/events/stream":
        return (VISUAL_STREAM_SCOPE,)
    if path_key.startswith("/billing/"):
        return (COMPUTE_BILLING_SCOPE,)
    if path_key.startswith("/admin/"):
        return (COMPUTE_ADMIN_SCOPE,)
    if path_key.startswith("/market/providers") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_PROVIDER_ADMIN_SCOPE,)
    if path_key.startswith("/market/quotes") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_PROVIDER_ADMIN_SCOPE,)
    if path_key.startswith("/market/capacity") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_PROVIDER_ADMIN_SCOPE,)
    if path_key.startswith("/market/"):
        return (COMPUTE_READ_SCOPE,)
    if path_key.startswith("/compute/jobs") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_EXECUTE_SCOPE,)
    if path_key.startswith("/compute/alerts") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_ADMIN_SCOPE,)
    if path_key.startswith("/compute/alerts"):
        return (COMPUTE_READ_SCOPE,)
    if path_key.startswith("/compute/audit"):
        return (COMPUTE_AUDIT_SCOPE,)
    if path_key.startswith("/compute/providers") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_PROVIDER_ADMIN_SCOPE,)
    if "/health-check" in path_key and path_key.startswith("/compute/providers"):
        return (COMPUTE_PROVIDER_ADMIN_SCOPE,)
    if path_key.startswith("/compute/routes") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_PROVIDER_ADMIN_SCOPE,)
    if path_key.startswith("/compute/policies") and normalized_method in {"POST", "PATCH", "DELETE"}:
        return (COMPUTE_POLICY_ADMIN_SCOPE,)
    if path_key.endswith("/validate") and path_key.startswith("/compute/policies"):
        return (COMPUTE_POLICY_ADMIN_SCOPE,)
    if path_key.startswith("/compute/decisions/") and path_key.endswith("/replay"):
        return (COMPUTE_PLAN_SCOPE,)
    if path_key in {
        "/compute/plan",
        "/compute/marketplace-plan",
        "/compute/quote",
        "/compute/route",
        "/compute/payment-plan",
        "/compute/simulate-settlement",
        "/compute/economic-memory/query",
        "/compute/decisions/{decision_id}/replay",
    }:
        return (COMPUTE_PLAN_SCOPE,)
    if path_key.startswith("/compute/"):
        return (COMPUTE_READ_SCOPE,)
    if normalized_method in READ_METHODS:
        return (READ_SCOPE,)
    return (WRITE_SCOPE,)


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return ""
