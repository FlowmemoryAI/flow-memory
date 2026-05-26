import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router


def test_internal_visual_state_endpoint_returns_real_network_projection() -> None:
    router = create_default_router()
    state = router.dispatch("GET", "/visual/state")
    assert state["ok"] is True
    assert state["state"]["runtime"]["agents"] == 4
    assert state["state"]["tasks"]


def test_internal_visual_events_and_schema_endpoints() -> None:
    router = create_default_router()
    events = router.dispatch("GET", "/visual/events")
    schema = router.dispatch("GET", "/visual/schema")
    assert events["events"]
    assert schema["schema"]["schema_version"] == "visual.telemetry.v1"


def test_network_run_scenario_can_return_visual_payload() -> None:
    router = create_default_router()
    result = router.dispatch("POST", "/network/run-scenario", {"scenario": "basic-economy", "emit_visual_events": True})
    assert result["ok"] is True
    assert result["visual_events"]
    assert result["visual_state"]["runtime"]["tasks"] >= 1


def test_visual_replay_start_and_fetch_roundtrip() -> None:
    router = create_default_router()
    started = router.dispatch("POST", "/visual/replay/start", {"scenario": "safety-approval", "run_id": "pytest-visual-replay"})
    assert started["ok"] is True
    replay = router.dispatch("GET", "/visual/replay/pytest-visual-replay")
    assert replay["ok"] is True
    assert replay["state"]["runtime"]["events"] >= 1


def test_http_visual_scope_enforcement() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/visual/state", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/visual/state", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "visual:read"})
    assert denied.status == 403
    assert allowed.status == 200
    body = json.loads(allowed.to_bytes())
    assert body["data"]["state"]["runtime"]["agents"] == 4
