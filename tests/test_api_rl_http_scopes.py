import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway


def test_rl_read_scope_required_when_enabled():
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/rl/envs", {"x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/rl/envs", {"x-flow-memory-scopes": "rl:read"})
    assert denied.status == 403
    assert allowed.status == 200


def test_rl_train_requires_train_scope_and_api_key_when_configured():
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle(
        "POST",
        "/rl/train-smoke",
        {"x-flow-memory-api-key": "dev", "x-flow-memory-scopes": "rl:evaluate"},
        json.dumps({"episodes": 2}).encode(),
    )
    allowed = gateway.handle(
        "POST",
        "/rl/train-smoke",
        {"x-flow-memory-api-key": "dev", "x-flow-memory-scopes": "rl:train"},
        json.dumps({"episodes": 2}).encode(),
    )
    assert denied.status == 403
    assert allowed.status == 200
