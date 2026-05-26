import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router


def test_internal_router_agent_launch_endpoints() -> None:
    router = create_default_router()
    local = router.dispatch("POST", "/agents/launch", {"goal": "Explore and report"})
    neural = router.dispatch("POST", "/agents/launch-neural", {"goal": "Explore and report", "backend": "tiny_torch"})
    network = router.dispatch("POST", "/network/run-scenario", {"scenario": "basic-economy"})
    assert local["result"]["accepted"] is True
    assert neural["neural"]["backend"] == "tiny_torch"
    assert network["ok"] is True


def test_http_agent_launch_scope_enforcement() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True))
    body = json.dumps({"goal": "Explore and report"}).encode("utf-8")
    missing = gateway.handle("POST", "/agents/launch", headers={"x-flow-memory-api-key": "dev-local-only"}, body=body)
    allowed = gateway.handle("POST", "/agents/launch", headers={"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "agents:launch"}, body=body)
    assert missing.status == 403
    assert allowed.status == 200
    assert allowed.body["data"]["result"]["accepted"] is True


def test_http_network_run_scope_enforcement() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True))
    body = json.dumps({"scenario": "basic-economy"}).encode("utf-8")
    missing = gateway.handle("POST", "/network/run-scenario", headers={"x-flow-memory-api-key": "dev-local-only"}, body=body)
    allowed = gateway.handle("POST", "/network/run-scenario", headers={"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "network:run"}, body=body)
    assert missing.status == 403
    assert allowed.status == 200
    assert allowed.body["data"]["ok"] is True
