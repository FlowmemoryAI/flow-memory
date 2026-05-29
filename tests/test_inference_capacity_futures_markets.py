from __future__ import annotations

import json

import pytest

from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import required_scopes_for
from flow_memory.capacity_market.service import default_capacity_market_service
from flow_memory.cli import main
from flow_memory.futures_market.service import default_futures_market_service
from flow_memory.inference_market.service import default_inference_market_service


def test_inference_market_quotes_discounted_route_and_openai_proxy() -> None:
    service = default_inference_market_service()

    quote = service.quote({"model": "gpt-4o-mini", "estimated_units": 1000})
    assert quote["ok"] is True
    assert quote["dry_run_only"] is True
    assert quote["funds_moved"] is False
    assert quote["broadcast_allowed"] is False
    quotes = quote["quotes"]
    assert quotes
    assert quotes[0]["discount_bps"] > 0

    response = service.proxy_chat_completion({"model": "flow-local-small", "messages": []})
    assert response["object"] == "chat.completion"
    assert response["flow_memory"]["dry_run_only"] is True


def test_agent_opportunity_planner_can_sell_unused_inference() -> None:
    service = default_inference_market_service()

    result = service.opportunity_cost(
        {
            "agent_id": "seller-unused-daily-credits",
            "task": "low value background task",
            "estimated_value": 0,
            "allow_sell_unused": True,
        }
    )

    assert result["ok"] is True
    assert result["decision"]["decision"] == "sell_unused_inference"
    assert result["decision"]["analysis"]["estimated_sell_value"] > 0
    assert result["dry_run_only"] is True
    assert result["funds_moved"] is False


def test_inference_market_rejects_unsafe_payloads() -> None:
    service = default_inference_market_service()

    with pytest.raises(ValueError, match="private_key"):
        service.quote({"model": "gpt-4o-mini", "private_key": "do-not-accept"})

    with pytest.raises(ValueError, match="broadcast"):
        service.opportunity_cost({"task": "unsafe", "broadcast": True})


def test_capacity_market_reserve_and_forward_simulation_are_non_binding() -> None:
    service = default_capacity_market_service()

    reservation = service.reserve({"gpu_class": "H100", "region": "us-east", "hours": 10})
    assert reservation["ok"] is True
    assert reservation["reservation"]["dry_run_only"] is True
    assert reservation["reservation"]["funds_moved"] is False
    assert reservation["reservation"]["legally_binding"] is False

    forward = service.forward_simulate({"gpu_class": "H100", "region": "us-east", "hours": 4000})
    assert forward["ok"] is True
    assert forward["dry_run_only"] is True
    assert forward["live_trading_enabled"] is False
    assert forward["legal_review_required"] is True
    assert forward["compliance_review_required"] is True


def test_futures_simulator_rejects_live_trading_and_margin() -> None:
    service = default_futures_market_service()

    order = service.simulate_order({"symbol": "FM-H100-USEAST-Q3-2027", "side": "buy", "quantity": 1})
    assert order["ok"] is True
    assert order["live_trading_enabled"] is False
    assert order["funds_moved"] is False
    assert order["legal_review_required"] is True

    with pytest.raises(ValueError, match="live futures"):
        service.simulate_order({"symbol": "FM-H100-USEAST-Q3-2027", "live futures": True})

    with pytest.raises(ValueError, match="margin"):
        service.risk_check({"margin": True})


def test_router_exposes_inference_capacity_and_futures_endpoints() -> None:
    router = create_default_router()

    inference = router.dispatch(
        "POST",
        "/inference/opportunity-cost",
        {"task": "research", "estimated_value": 50, "budget": 5},
    )
    assert inference["ok"] is True
    assert inference["dry_run_only"] is True

    capacity = router.dispatch("GET", "/capacity/inventory", {})
    assert capacity["ok"] is True
    assert capacity["inventory"]["total_available_units"] > 0

    futures = router.dispatch("GET", "/futures/markets", {})
    assert futures["ok"] is True
    assert futures["live_trading_enabled"] is False

    proxy = router.dispatch("POST", "/v1/chat/completions", {"model": "flow-local-small", "messages": []})
    assert proxy["object"] == "chat.completion"


def test_new_market_scope_mapping() -> None:
    assert required_scopes_for("POST", "/inference/opportunity-cost") == ("inference:plan",)
    assert required_scopes_for("POST", "/inference/credits/buy") == ("inference:buy",)
    assert required_scopes_for("POST", "/inference/credits/sell") == ("inference:sell",)
    assert required_scopes_for("POST", "/inference/proxy") == ("inference:proxy",)
    assert required_scopes_for("POST", "/capacity/forwards/simulate") == ("compute:settlement-admin",)
    assert required_scopes_for("POST", "/futures/orders/simulate") == ("compute:settlement-admin",)



def test_cli_inference_capacity_and_futures_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inference", "opportunity-cost", "--task", "research", "--estimated-value", "50"]) == 0
    inference = json.loads(capsys.readouterr().out)
    assert inference["dry_run_only"] is True

    assert main(["capacity", "quote", "--gpu-class", "H100", "--region", "us-east", "--hours", "10"]) == 0
    capacity = json.loads(capsys.readouterr().out)
    assert capacity["quote"]["funds_moved"] is False

    assert main(["futures", "simulate-order", "--side", "buy", "--quantity", "1"]) == 0
    futures = json.loads(capsys.readouterr().out)
    assert futures["live_trading_enabled"] is False
