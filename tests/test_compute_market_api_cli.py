import json
import subprocess
import sys

from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for
from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway


def test_compute_api_endpoints_and_scopes():
    router = create_default_router()

    assert router.dispatch("GET", "/compute/providers")["ok"] is True
    assert router.dispatch("GET", "/compute/routes")["ok"] is True
    plan = router.dispatch("POST", "/compute/marketplace-plan", {"task": {"task_id": "api"}, "policy": {"max_total_cost": 0.01, "max_quote": 0.01, "dry_run_required": True}})
    assert plan["ok"] is True
    assert plan["no_funds_moved"] is True

    assert required_scopes_for("GET", "/compute/providers") == ("compute:read",)
    assert required_scopes_for("POST", "/compute/route") == ("compute:plan",)


def test_compute_api_scope_enforcement():
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/compute/providers", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/compute/providers", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:read"})
    planned = gateway.handle(
        "POST",
        "/compute/route",
        {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:plan"},
        json.dumps({"task": {"task_id": "scoped"}, "policy": {"max_total_cost": 0.01, "max_quote": 0.01, "dry_run_required": True}}).encode("utf-8"),
    )

    assert denied.status == 403
    assert allowed.status == 200
    assert planned.status == 200


def test_flow_memory_compute_cli_plan_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "flow_memory", "compute", "plan", "--goal", "Explore and report", "--budget", "0.01", "--max-quote", "0.01"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["dry_run_only"] is True
    assert payload["no_broadcast"] is True
