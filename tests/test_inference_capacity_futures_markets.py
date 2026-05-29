from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow_memory.capacity_market.service import CapacityMarketService
from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.service import ComputeMarketService, reset_default_service
from flow_memory.compute_market.storage import COMPUTE_RECORD_TYPES, ComputeMarketStore
from flow_memory.compute_market.storage_backends import PostgresComputeMarketStore, _POSTGRES_TABLES
from flow_memory.futures_market.service import FuturesMarketService
from flow_memory.inference_market.service import InferenceMarketService
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

    anthropic = service.proxy_anthropic_message(
        {"model": "claude-3-5-haiku", "messages": [{"role": "user", "content": "hello"}]}
    )
    assert anthropic["type"] == "message"
    assert anthropic["flow_memory"]["dry_run_only"] is True
    assert anthropic["flow_memory"]["usage_record"]["source_id"] == "src-discount-anthropic-compatible"

    anthropic_models = service.anthropic_models()
    assert any(model["id"] == "claude-3-5-haiku" for model in anthropic_models["data"])


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


def test_inference_admin_credit_and_demand_methods_are_stateful_and_safe() -> None:
    service = InferenceMarketService.seeded()

    source = service.create_source(
        {
            "source_id": "src-admin-test",
            "source_name": "Admin test source",
            "models": ["gpt-4o-mini"],
            "credential_ref": "secret://inference/src-admin-test",
            "seller_id": "seller-admin-test",
        }
    )
    assert source["ok"] is True
    assert service.sources["src-admin-test"].source_name == "Admin test source"

    account = service.create_account(
        {
            "account_id": "acct-admin-test",
            "owner_id": "seller-admin-test",
            "source_id": "src-admin-test",
            "sell_enabled": True,
        }
    )
    assert account["account"]["sell_enabled"] is True
    assert "acct-admin-test" in service.accounts

    updated = service.update_source("src-admin-test", {"status": "paused"})
    assert updated["source"]["status"] == "paused"

    disabled = service.disable_source("src-admin-test", {})
    assert disabled["source"]["status"] == "disabled"
    health = service.source_health("src-admin-test", {})
    assert health["health"] == "disabled_or_unknown"

    listed = service.sell({"agent_id": "seller-admin-test", "units": 10})
    cancelled = service.cancel_listing({"listing_id": listed["listing"]["listing_id"]})
    assert cancelled["listing"]["status"] == "cancelled"

    demand = service.demand({"agent_id": "agent-demand", "model": "gpt-4o-mini", "estimated_units": 123})
    assert demand["demand"][0]["units_requested"] == 123.0
    assert service.demand_snapshots[demand["demand"][0]["snapshot_id"]].agent_id == "agent-demand"

    with pytest.raises(ValueError, match="raw inference provider credential"):
        service.create_source({"source_id": "src-unsafe", "api_key": "raw-provider-key"})


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

    anthropic = router.dispatch(
        "POST",
        "/anthropic/v1/messages",
        {"model": "claude-3-5-haiku", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert anthropic["type"] == "message"



def test_marketplace_api_endpoints_persist_through_compute_store(tmp_path: Path) -> None:
    db_path = tmp_path / "marketplace-api-store.sqlite3"
    service = ComputeMarketService(
        store=ComputeMarketStore(f"sqlite:///{db_path}"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"),
    )
    reset_default_service(service)
    router = create_default_router()
    try:
        source = router.dispatch(
            "POST",
            "/inference/admin/sources",
            {
                "source_id": "src-api-persist",
                "source_name": "Persisted API source",
                "credential_ref": "secret://inference/src-api-persist",
            },
        )
        reservation = router.dispatch(
            "POST",
            "/capacity/reserve",
            {"gpu_class": "H100", "region": "us-east", "hours": 2},
        )
        order = router.dispatch(
            "POST",
            "/futures/orders/simulate",
            {"symbol": "FM-H100-USEAST-Q3-2027", "side": "buy", "quantity": 1},
        )
    finally:
        reset_default_service(None)

    assert service.store.get_record("inference_credit_source", str(source["source"]["source_id"])) is not None
    assert service.store.get_record("capacity_reservation", str(reservation["reservation"]["reservation_id"])) is not None
    assert service.store.get_record("futures_order_simulated", str(order["order"]["order_id"])) is not None


def test_new_market_scope_mapping() -> None:
    assert required_scopes_for("POST", "/inference/opportunity-cost") == ("inference:plan",)
    assert required_scopes_for("POST", "/inference/credits/buy") == ("inference:buy",)
    assert required_scopes_for("POST", "/inference/credits/sell") == ("inference:sell",)
    assert required_scopes_for("POST", "/inference/proxy") == ("inference:proxy",)
    assert required_scopes_for("POST", "/anthropic/v1/messages") == ("inference:proxy",)
    assert required_scopes_for("POST", "/capacity/forwards/simulate") == ("compute:settlement-admin",)
    assert required_scopes_for("POST", "/futures/orders/simulate") == ("compute:settlement-admin",)



def test_cli_inference_capacity_and_futures_commands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inference", "opportunity-cost", "--task", "research", "--estimated-value", "50"]) == 0
    inference = json.loads(capsys.readouterr().out)
    assert inference["dry_run_only"] is True

    assert main(["inference", "credits", "list"]) == 0
    nested_credits = json.loads(capsys.readouterr().out)
    assert nested_credits["dry_run_only"] is True

    assert main(["inference", "credits", "buy", "--units", "1"]) == 0
    nested_buy = json.loads(capsys.readouterr().out)
    assert nested_buy["funds_moved"] is False

    assert main(["capacity", "quote", "--gpu-class", "H100", "--region", "us-east", "--hours", "10"]) == 0
    capacity = json.loads(capsys.readouterr().out)
    assert capacity["quote"]["funds_moved"] is False

    assert main(["capacity", "forward", "quote", "--gpu-class", "H100", "--hours", "10"]) == 0
    nested_forward = json.loads(capsys.readouterr().out)
    assert nested_forward["legal_review_required"] is True

    assert main(["capacity", "index", "--gpu-class", "H100"]) == 0
    capacity_index = json.loads(capsys.readouterr().out)
    assert capacity_index["dry_run_only"] is True

    assert main(["capacity", "forward-curve", "--gpu-class", "H100"]) == 0
    forward_curve = json.loads(capsys.readouterr().out)
    assert forward_curve["not_investment_advice"] is True

    assert main(["futures", "simulate-order", "--side", "buy", "--quantity", "1"]) == 0
    futures = json.loads(capsys.readouterr().out)
    assert futures["live_trading_enabled"] is False


def test_new_market_record_families_are_in_sqlite_and_postgres_schema() -> None:
    required = {
        "inference_credit_source",
        "inference_credit_account",
        "inference_credit_balance",
        "inference_credit_listing",
        "inference_credit_order",
        "inference_credit_fill",
        "inference_credit_quote",
        "inference_route",
        "opportunity_cost_decision",
        "inference_usage_record",
        "inference_price_snapshot",
        "capacity_window",
        "capacity_hold",
        "capacity_reservation",
        "capacity_quote",
        "forward_capacity_contract",
        "forward_capacity_settlement_plan",
        "forward_capacity_risk_assessment",
        "futures_contract_spec",
        "futures_order_simulated",
        "futures_position_simulated",
        "futures_mark_price",
        "futures_index_price",
        "futures_risk_check",
        "futures_settlement_simulation",
        "compute_capacity_index",
        "gpu_forward_curve",
    }

    assert required <= set(COMPUTE_RECORD_TYPES)
    assert set(_POSTGRES_TABLES) == set(COMPUTE_RECORD_TYPES)

    statement_by_name = {statement.name: statement.sql for statement in PostgresComputeMarketStore.schema_statements()}
    for record_type in required:
        table_name = _POSTGRES_TABLES[record_type]
        assert f"{table_name}_table" in statement_by_name
        assert f"create table if not exists {table_name} " in statement_by_name[f"{table_name}_table"]


def test_market_simulators_persist_records_to_compute_store(tmp_path: Path) -> None:
    db_path = tmp_path / "market-records.sqlite3"
    store = ComputeMarketStore(f"sqlite:///{db_path}")

    inference = InferenceMarketService.seeded(store=store)
    listed = inference.sell(
        {
            "agent_id": "agent-seller",
            "model": "gpt-4o-mini",
            "unit_type": "token",
            "units": 25,
            "unit_price": 0.0000007,
        }
    )
    bought = inference.buy(
        {
            "buyer_id": "buyer-one",
            "listing_id": listed["listing"]["listing_id"],
            "units": 5,
        }
    )
    opportunity = inference.opportunity_cost(
        {
            "agent_id": "seller-unused-daily-credits",
            "task": "persisted opportunity",
            "estimated_value": 0,
            "allow_sell_unused": True,
        }
    )
    prices = inference.prices()
    admin_source = inference.create_source(
        {
            "source_id": "src-persist-admin",
            "source_name": "Persisted admin source",
            "credential_ref": "secret://inference/src-persist-admin",
        }
    )
    admin_account = inference.create_account(
        {
            "account_id": "acct-persist-admin",
            "owner_id": "seller-persist-admin",
            "source_id": "src-persist-admin",
        }
    )
    demand_snapshot = inference.demand({"agent_id": "agent-persist-demand", "model": "gpt-4o-mini"})

    capacity = CapacityMarketService.seeded(store=store)
    reservation = capacity.reserve({"gpu_class": "H100", "region": "us-east", "hours": 4})
    forward = capacity.forward_simulate({"gpu_class": "H100", "region": "us-east", "hours": 400})
    delivery = capacity.forward_simulate_delivery({"contract_id": forward["contract"]["contract_id"]})

    futures = FuturesMarketService(store=store)
    order = futures.simulate_order({"symbol": "FM-H100-USEAST-Q3-2027", "side": "buy", "quantity": 2})
    mark = futures.mark_price({"symbol": "FM-H100-USEAST-Q3-2027", "mark_price": 2.6})
    index = futures.index_price({"symbol": "FM-H100-USEAST-Q3-2027", "index_price": 2.4})
    risk = futures.risk_check({"symbol": "FM-H100-USEAST-Q3-2027"})
    settlement = futures.settlement_simulate({"symbol": "FM-H100-USEAST-Q3-2027", "settlement_value": 2.45})

    listing_id = str(listed["listing"]["listing_id"])
    order_id = str(bought["order"]["order_id"])
    decision_id = str(opportunity["decision"]["decision_id"])
    price_id = str(prices["prices"][0]["snapshot_id"])
    source_id = str(admin_source["source"]["source_id"])
    account_id = str(admin_account["account"]["account_id"])
    demand_id = str(demand_snapshot["demand"][0]["snapshot_id"])
    reservation_id = str(reservation["reservation"]["reservation_id"])
    forward_id = str(forward["contract"]["contract_id"])
    delivery_id = str(delivery["delivery_schedule"]["schedule_id"])
    futures_order_id = str(order["order"]["order_id"])
    mark_id = str(mark["mark_price"]["mark_price_id"])
    index_id = str(index["index_price"]["index_price_id"])
    risk_id = str(risk["risk_check"]["risk_check_id"])
    settlement_id = str(settlement["settlement_simulation"]["settlement_simulation_id"])

    store.close()
    reopened = ComputeMarketStore(f"sqlite:///{db_path}")

    assert reopened.get_record("inference_credit_listing", listing_id) is not None
    assert reopened.get_record("inference_credit_order", order_id) is not None
    assert reopened.get_record("opportunity_cost_decision", decision_id) is not None
    assert reopened.get_record("inference_price_snapshot", price_id) is not None
    assert reopened.get_record("inference_credit_source", source_id) is not None
    assert reopened.get_record("inference_credit_account", account_id) is not None
    assert reopened.get_record("inference_demand_snapshot", demand_id) is not None
    assert reopened.get_record("capacity_reservation", reservation_id) is not None
    assert reopened.get_record("forward_capacity_contract", forward_id) is not None
    assert reopened.get_record("forward_capacity_delivery_schedule", delivery_id) is not None
    assert reopened.get_record("futures_order_simulated", futures_order_id) is not None
    assert reopened.get_record("futures_mark_price", mark_id) is not None
    assert reopened.get_record("futures_index_price", index_id) is not None
    assert reopened.get_record("futures_risk_check", risk_id) is not None
    assert reopened.get_record("futures_settlement_simulation", settlement_id) is not None

    reloaded_inference = InferenceMarketService.seeded(store=reopened)
    reloaded_capacity = CapacityMarketService.seeded(store=reopened)
    reloaded_futures = FuturesMarketService(store=reopened)

    assert listing_id in reloaded_inference.listings
    assert order_id in reloaded_inference.orders
    assert reservation_id in reloaded_capacity.reservations
    assert forward_id in reloaded_capacity.forward_contracts
    assert futures_order_id in reloaded_futures.orders
