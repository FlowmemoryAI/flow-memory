from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for


def test_release_endpoints_return_evidence_and_decision_metadata():
    router = create_default_router()
    evidence = router.dispatch("GET", "/release/evidence")
    decision = router.dispatch("GET", "/release/decision/local")
    assert evidence["raw_artifacts_exposed"] is False
    assert "bundle_exists" in evidence
    assert decision["target"] == "local"
    assert "decision" in decision


def test_release_read_scope_required_when_enabled():
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/release/evidence", {"x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/release/evidence", {"x-flow-memory-scopes": "release:read"})
    assert denied.status == 403
    assert allowed.status == 200


def test_release_decision_invalid_target_uses_structured_error():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    response = gateway.handle("GET", "/release/decision/production", {})
    body = response.body
    assert response.status == 400
    assert body["error"]["code"] == "request.invalid"


def test_release_scope_mapping():
    assert required_scopes_for("GET", "/release/evidence") == ("release:read",)
