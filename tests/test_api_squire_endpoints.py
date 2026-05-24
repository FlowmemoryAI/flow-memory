import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for


def test_internal_squire_status_and_skill_endpoints():
    router = create_default_router()

    status = router.dispatch("GET", "/squire/status")
    skill = router.dispatch("GET", "/squire/skill")
    schema = router.dispatch("GET", "/squire/memory-schema")

    assert status["ok"] is True
    assert status["no_real_funds_by_default"] is True
    assert skill["ok"] is True
    assert "SQUIRE" in skill["description_contains"]
    assert "balance_after" in schema["schema_fields"]


def test_internal_squire_plan_and_routes():
    router = create_default_router()

    plan = router.dispatch("POST", "/squire/plan", {"goal": "route cheap inference with marketplace-only policy"})
    route = router.dispatch("POST", "/squire/routes", {"marketplace_only": True, "max_input_price_per_million": 0.1, "max_output_price_per_million": 0.2})

    assert plan["ok"] is True
    assert "memory_writes" in plan["plan"]
    assert route["selected"]["provider_class"] == "marketplace"


def test_squire_docs_sources_are_offline_sync_plan():
    router = create_default_router()
    docs = router.dispatch("GET", "/squire/docs-sources")

    assert docs["ok"] is True
    assert docs["docs_sync"]["base_tests_fetch_network"] is False
    assert docs["docs_sync"]["sources"]


def test_squire_scope_enforcement():
    assert required_scopes_for("GET", "/squire/status") == ("squire:read",)
    assert required_scopes_for("POST", "/squire/plan") == ("squire:plan",)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/squire/status", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/squire/status", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "squire:read"})
    plan_allowed = gateway.handle(
        "POST",
        "/squire/plan",
        {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "squire:plan"},
        json.dumps({"goal": "UsePod routing"}).encode("utf-8"),
    )

    assert denied.status == 403
    assert allowed.status == 200
    assert plan_allowed.status == 200
    assert json.loads(plan_allowed.to_bytes())["data"]["plan"]["live_stack_to_use_now"]
