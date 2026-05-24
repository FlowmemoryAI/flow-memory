import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.scopes import (
    NEURAL_EVIDENCE_SCOPE,
    NEURAL_READ_SCOPE,
    NEURAL_TRAIN_SCOPE,
    NEURAL_VALIDATE_SCOPE,
    required_scopes_for,
)


def test_neural_scope_mapping():
    assert required_scopes_for("GET", "/neural/status") == (NEURAL_READ_SCOPE,)
    assert required_scopes_for("GET", "/neural/gpu-runs") == (NEURAL_EVIDENCE_SCOPE,)
    assert required_scopes_for("GET", "/neural/benchmarks") == (NEURAL_EVIDENCE_SCOPE,)
    assert required_scopes_for("POST", "/neural/validate-smoke") == (NEURAL_VALIDATE_SCOPE,)
    assert required_scopes_for("POST", "/neural/train-smoke") == (NEURAL_TRAIN_SCOPE,)


def test_http_gateway_enforces_neural_scopes_when_enabled():
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))

    denied = gateway.handle("GET", "/neural/status", {"x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/neural/status", {"x-flow-memory-scopes": NEURAL_READ_SCOPE})
    evidence_denied = gateway.handle("GET", "/neural/gpu-runs", {"x-flow-memory-scopes": NEURAL_READ_SCOPE})
    evidence_allowed = gateway.handle("GET", "/neural/gpu-runs", {"x-flow-memory-scopes": NEURAL_EVIDENCE_SCOPE})

    assert denied.status == 403
    assert allowed.status == 200
    assert evidence_denied.status == 403
    assert evidence_allowed.status == 200


def test_train_smoke_requires_train_scope_and_loopback_binding():
    body = json.dumps({"steps": 1}).encode("utf-8")
    scoped_gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = scoped_gateway.handle(
        "POST",
        "/neural/train-smoke",
        {"x-flow-memory-scopes": NEURAL_VALIDATE_SCOPE},
        body,
    )
    public_gateway = HttpApiGateway(
        config=HttpApiConfig(host="0.0.0.0", require_scopes=True, enable_rate_limit=False)
    )
    public_denied = public_gateway.handle(
        "POST",
        "/neural/train-smoke",
        {"x-flow-memory-scopes": NEURAL_TRAIN_SCOPE},
        body,
    )

    assert denied.status == 403
    assert public_denied.status == 403
    assert public_denied.body["error"]["message"] == "Neural train-smoke is local-only"
