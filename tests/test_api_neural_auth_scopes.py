import json
from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway

def test_neural_read_scope_required_when_enabled():
    gateway=HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied=gateway.handle("GET", "/neural/status", {"x-flow-memory-scopes":"api:read"})
    allowed=gateway.handle("GET", "/neural/status", {"x-flow-memory-scopes":"neural:read"})
    assert denied.status == 403
    assert allowed.status == 200

def test_neural_train_requires_train_scope_and_api_key_when_configured():
    gateway=HttpApiGateway(config=HttpApiConfig(api_key="dev", require_scopes=True, enable_rate_limit=False))
    denied=gateway.handle("POST", "/neural/train-smoke", {"x-flow-memory-api-key":"dev", "x-flow-memory-scopes":"neural:read"}, json.dumps({}).encode())
    allowed=gateway.handle("POST", "/neural/train-smoke", {"x-flow-memory-api-key":"dev", "x-flow-memory-scopes":"neural:train"}, json.dumps({"out":"artifacts/neural/test_api"}).encode())
    assert denied.status == 403
    assert allowed.status == 200
