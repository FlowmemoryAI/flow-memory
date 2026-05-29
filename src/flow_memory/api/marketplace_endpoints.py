"""Inference, capacity, and futures simulator endpoint adapters."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.capacity_market.service import CapacityMarketService
from flow_memory.compute_market.service import default_service as default_compute_market_service
from flow_memory.futures_market.service import FuturesMarketService
from flow_memory.inference_market.service import InferenceMarketService

_INFERENCE_SERVICE: InferenceMarketService | None = None
_CAPACITY_SERVICE: CapacityMarketService | None = None
_FUTURES_SERVICE: FuturesMarketService | None = None


def _inference_service() -> InferenceMarketService:
    global _INFERENCE_SERVICE
    store = default_compute_market_service().store
    if _INFERENCE_SERVICE is None or _INFERENCE_SERVICE.store is not store:
        _INFERENCE_SERVICE = InferenceMarketService.seeded(store=store)
    return _INFERENCE_SERVICE


def _capacity_service() -> CapacityMarketService:
    global _CAPACITY_SERVICE
    store = default_compute_market_service().store
    if _CAPACITY_SERVICE is None or _CAPACITY_SERVICE.store is not store:
        _CAPACITY_SERVICE = CapacityMarketService.seeded(store=store)
    return _CAPACITY_SERVICE


def _futures_service() -> FuturesMarketService:
    global _FUTURES_SERVICE
    store = default_compute_market_service().store
    if _FUTURES_SERVICE is None or _FUTURES_SERVICE.store is not store:
        _FUTURES_SERVICE = FuturesMarketService(store=store)
    return _FUTURES_SERVICE

def _ensure_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("market endpoint returned a non-object response")
    return value


def inference_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().opportunity_cost(payload))


def inference_opportunity_cost(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().opportunity_cost(payload))


def inference_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().quote(payload))


def inference_route(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().route(payload))


def inference_credits(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().credits(payload))


def inference_sources(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().sources_list(payload))


def inference_credit_account_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().create_account(payload))


def inference_credit_list(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().sell(payload))


def inference_credit_buy(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().buy(payload))


def inference_credit_sell(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().sell(payload))


def inference_credit_cancel_listing(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().cancel_listing(payload))


def inference_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().order_book(payload))


def inference_listings(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().order_book(payload))


def inference_prices(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().prices(payload))


def inference_spreads(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    prices = _inference_service().prices(payload)
    return {**dict(prices), "spreads": prices.get("prices", ())}


def inference_demand(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().demand(payload))


def inference_usage(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().usage(payload))


def inference_usage_by_agent(agent_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().usage({**dict(payload), "agent_id": agent_id}))


def inference_usage_by_goal(goal_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().usage({**dict(payload), "goal_id": goal_id}))


def inference_statement(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().statement(payload))


def inference_roi(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = _inference_service().usage(payload)
    summary = usage.get("summary", {})
    return {"ok": True, "roi": summary, "dry_run_only": True, "funds_moved": False}


def inference_admin_sources(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().sources_list(payload))


def inference_admin_source_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().create_source(payload))


def inference_admin_source_update(source_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().update_source(source_id, payload))


def inference_admin_source_disable(source_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().disable_source(source_id, payload))


def inference_admin_source_health(source_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().source_health(source_id, payload))


def inference_proxy(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().proxy_chat_completion(payload))


def openai_models(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().models(payload))


def openai_chat_completions(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_inference_service().proxy_chat_completion(payload))


def capacity_inventory(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().inventory(payload))


def capacity_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().quote(payload))


def capacity_hold(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().hold(payload))


def capacity_reserve(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().reserve(payload))


def capacity_release(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().release(payload))


def capacity_reservations(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().reservations_list(payload))


def capacity_utilization(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().utilization(payload))


def capacity_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().order_book(payload))


def capacity_forward_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().forward_quote(payload))


def capacity_forward_draft(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().forward_draft(payload))


def capacity_forward_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().forward_simulate(payload))


def capacity_forward_list(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "contracts": tuple(contract.as_record() for contract in _capacity_service().forward_contracts.values()),
        "dry_run_only": True,
        "funds_moved": False,
    }


def capacity_forward_get(contract_id: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    contract = _capacity_service().forward_contracts.get(contract_id)
    return {"ok": contract is not None, "contract": contract.as_record() if contract else {}, "dry_run_only": True}


def capacity_forward_simulate_delivery(contract_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().forward_simulate_delivery({**dict(payload), "contract_id": contract_id}))


def capacity_forward_simulate_settlement(contract_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_capacity_service().forward_simulate({**dict(payload), "contract_id": contract_id}))


def capacity_forward_cancel(contract_id: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "contract": {"contract_id": contract_id, "status": "cancelled", "dry_run_only": True},
        "funds_moved": False,
    }


def futures_markets(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().markets(payload))


def futures_markets_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().markets(payload))


def futures_contracts(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().contracts_list(payload))


def futures_contract_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().contract_create(payload))


def futures_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().order_book(payload))


def futures_order_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().simulate_order(payload))


def futures_order_cancel(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().cancel_order(payload))


def futures_positions(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().positions_list(payload))


def futures_mark_price(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().mark_price(payload))


def futures_index_price(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().index_price(payload))


def futures_risk_check(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().risk_check(payload))


def futures_expiry_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().expiry_simulate(payload))


def futures_delivery_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().delivery_simulate(payload))


def futures_settlement_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().settlement_simulate(payload))


def capacity_indexes(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().indexes(payload))


def capacity_forward_curve(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().forward_curve(payload))


def capacity_forward_curve_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().forward_curve(payload))


def futures_indexes(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().indexes(payload))


def futures_mark_prices(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_futures_service().mark_price(payload))
