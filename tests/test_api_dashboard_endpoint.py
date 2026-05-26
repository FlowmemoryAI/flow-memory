from flow_memory.api.dashboard_endpoints import dashboard_snapshot
from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for


def test_dashboard_snapshot_loads_mock_data_without_raw_artifacts() -> None:
    payload = dashboard_snapshot()
    assert payload["ok"] is True
    assert payload["mock_data_only"] is True
    assert payload["raw_artifacts_exposed"] is False
    assert {"runtime", "neural_status", "rl_benchmarks", "agent_launch", "local_network", "payments"} <= set(payload["records"])


def test_dashboard_snapshot_router_endpoint() -> None:
    router = create_default_router()
    payload = router.dispatch("GET", "/dashboard/snapshot")
    assert payload["ok"] is True
    assert payload["records"]["payments"]["realFundsUsed"] is False


def test_dashboard_read_scope_required_when_enabled() -> None:
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/dashboard/snapshot", {"x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/dashboard/snapshot", {"x-flow-memory-scopes": "dashboard:read"})
    assert denied.status == 403
    assert allowed.status == 200
    assert required_scopes_for("GET", "/dashboard/snapshot") == ("dashboard:read",)
