import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for


def test_compute_api_plan_route_payment_and_memory() -> None:
    router = create_default_router()
    payload = {
        "task": "run agent batch inference",
        "selection_strategy": "marketplace_preferred",
        "policy": {"marketplace_only": True, "allowed_assets": ("USDC",), "allowed_networks": ("solana",)},
    }

    plan = router.dispatch("POST", "/compute/plan", payload)
    quote = router.dispatch("POST", "/compute/quote", payload)
    route = router.dispatch("POST", "/compute/route", payload)
    payment = router.dispatch("POST", "/compute/payment-plan", payload)
    settlement = router.dispatch("POST", "/compute/simulate-settlement", payload)
    memory = router.dispatch("GET", "/compute/economic-memory")
    query = router.dispatch("POST", "/compute/economic-memory/query", {"query": "cheapest"})

    assert plan["ok"] is True
    assert plan["compute_plan"]["selected_route"]["market_type"] == "marketplace"
    assert plan["compute_plan"]["economic_memory_preview"]["dry_run_only"] is True
    assert quote["quotes"]
    assert route["route_decision"]["selected_route"]
    assert payment["payment_plan"]["dry_run_only"] is True
    assert settlement["settlement_intent"]["dry_run_only"] is True
    assert "task_id" in memory["schema_fields"]
    assert query["ok"] is True


def test_compute_api_fail_closed_route_details() -> None:
    router = create_default_router()
    result = router.dispatch(
        "POST",
        "/compute/route",
        {"task": "fail closed", "policy": {"allowed_assets": ("NOTREAL",)}},
    )

    assert result["ok"] is False
    assert result["route_decision"]["rejected_routes"]
    reasons = tuple(reason for values in result["route_decision"]["rejected_reasons"].values() for reason in values)
    assert "unsupported_asset" in reasons


def test_compute_provider_route_policy_endpoints() -> None:
    router = create_default_router()

    providers = router.dispatch("GET", "/compute/providers")
    routes = router.dispatch("GET", "/compute/routes")
    policies = router.dispatch("GET", "/compute/policies")
    marketplace_plan = router.dispatch("POST", "/compute/marketplace-plan", {"task": "market only"})

    assert providers["providers"]
    assert providers["registry"]["assets"]
    assert routes["routes"]
    assert "balanced" in policies["selection_strategies"]
    assert marketplace_plan["compute_plan"]["profile"]["task_description"] == "market only"


def test_compute_scope_enforcement() -> None:
    assert required_scopes_for("GET", "/compute/providers") == ("compute:read",)
    assert required_scopes_for("POST", "/compute/plan") == ("compute:plan",)
    assert required_scopes_for("POST", "/compute/economic-memory/query") == ("compute:plan",)

    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only", require_scopes=True, enable_rate_limit=False))
    denied = gateway.handle("GET", "/compute/providers", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "api:read"})
    allowed = gateway.handle("GET", "/compute/providers", {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:read"})
    plan_allowed = gateway.handle(
        "POST",
        "/compute/plan",
        {"x-flow-memory-api-key": "dev-local-only", "x-flow-memory-scopes": "compute:plan"},
        json.dumps({"task": "route compute"}).encode("utf-8"),
    )

    assert denied.status == 403
    assert allowed.status == 200
    assert plan_allowed.status == 200
    assert json.loads(plan_allowed.to_bytes())["data"]["compute_plan"]["payment_plan"]["dry_run_only"] is True


def test_compute_api_rejects_private_key_inputs() -> None:
    router = create_default_router()

    try:
        router.dispatch("POST", "/compute/plan", {"task": "unsafe", "private_key": "not accepted"})
    except ValueError as exc:
        assert "private_key" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("private_key payload was accepted")
