"""Inference, capacity, and futures simulator endpoint adapters."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.capacity_market.service import default_capacity_market_service
from flow_memory.futures_market.service import default_futures_market_service
from flow_memory.inference_market.service import default_inference_market_service

_INFERENCE_SERVICE = default_inference_market_service()
_CAPACITY_SERVICE = default_capacity_market_service()
_FUTURES_SERVICE = default_futures_market_service()

def _ensure_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("market endpoint returned a non-object response")
    return value


def inference_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.opportunity_cost(payload))


def inference_opportunity_cost(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.opportunity_cost(payload))


def inference_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.quote(payload))


def inference_route(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.route(payload))


def inference_credits(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.credits(payload))


def inference_sources(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.sources_list(payload))


def inference_credit_account_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "account": {
            "account_id": str(payload.get("account_id") or "acct-simulated"),
            "owner_id": str(payload.get("owner_id") or payload.get("agent_id") or "agent-simulated"),
            "source_id": str(payload.get("source_id") or "src-discount-openai-compatible"),
            "status": "simulated",
            "dry_run_only": True,
            "funds_moved": False,
        },
        "dry_run_only": True,
        "funds_moved": False,
    }


def inference_credit_list(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.sell(payload))


def inference_credit_buy(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.buy(payload))


def inference_credit_sell(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.sell(payload))


def inference_credit_cancel_listing(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "listing": {
            "listing_id": str(payload.get("listing_id") or ""),
            "status": "cancelled",
            "dry_run_only": True,
            "funds_moved": False,
        },
        "dry_run_only": True,
        "funds_moved": False,
    }


def inference_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.order_book(payload))


def inference_listings(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.order_book(payload))


def inference_prices(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.prices(payload))


def inference_spreads(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    prices = _INFERENCE_SERVICE.prices(payload)
    return {**dict(prices), "spreads": prices.get("prices", ())}


def inference_demand(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "demand": (
            {
                "requested_model": str(payload.get("model") or "gpt-4o-mini"),
                "unit_type": str(payload.get("unit_type") or "token"),
                "units_requested": float(payload.get("estimated_units", 1000.0) or 1000.0),
                "dry_run_only": True,
            },
        ),
        "dry_run_only": True,
        "funds_moved": False,
    }


def inference_usage(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.usage(payload))


def inference_usage_by_agent(agent_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.usage({**dict(payload), "agent_id": agent_id}))


def inference_usage_by_goal(goal_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.usage({**dict(payload), "goal_id": goal_id}))


def inference_statement(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.statement(payload))


def inference_roi(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = _INFERENCE_SERVICE.usage(payload)
    summary = usage.get("summary", {})
    return {"ok": True, "roi": summary, "dry_run_only": True, "funds_moved": False}


def inference_admin_sources(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.sources_list(payload))


def inference_admin_source_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "source": {"source_id": str(payload.get("source_id") or "src-simulated"), "status": "simulated"},
        "credential_storage": "secret_reference_only",
        "dry_run_only": True,
    }


def inference_admin_source_update(source_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"ok": True, "source": {"source_id": source_id, "status": str(payload.get("status") or "updated")}}


def inference_admin_source_disable(source_id: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"ok": True, "source": {"source_id": source_id, "status": "disabled"}, "dry_run_only": True}


def inference_admin_source_health(source_id: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"ok": True, "source_id": source_id, "health": "simulated_healthy", "dry_run_only": True}


def inference_proxy(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.proxy_chat_completion(payload))


def openai_models(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.models(payload))


def openai_chat_completions(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_INFERENCE_SERVICE.proxy_chat_completion(payload))


def capacity_inventory(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.inventory(payload))


def capacity_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.quote(payload))


def capacity_hold(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.hold(payload))


def capacity_reserve(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.reserve(payload))


def capacity_release(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.release(payload))


def capacity_reservations(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.reservations_list(payload))


def capacity_utilization(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.utilization(payload))


def capacity_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.order_book(payload))


def capacity_forward_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.forward_quote(payload))


def capacity_forward_draft(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.forward_draft(payload))


def capacity_forward_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.forward_simulate(payload))


def capacity_forward_list(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "contracts": tuple(contract.as_record() for contract in _CAPACITY_SERVICE.forward_contracts.values()),
        "dry_run_only": True,
        "funds_moved": False,
    }


def capacity_forward_get(contract_id: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    contract = _CAPACITY_SERVICE.forward_contracts.get(contract_id)
    return {"ok": contract is not None, "contract": contract.as_record() if contract else {}, "dry_run_only": True}


def capacity_forward_simulate_delivery(contract_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.forward_simulate_delivery({**dict(payload), "contract_id": contract_id}))


def capacity_forward_simulate_settlement(contract_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_CAPACITY_SERVICE.forward_simulate({**dict(payload), "contract_id": contract_id}))


def capacity_forward_cancel(contract_id: str, _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "contract": {"contract_id": contract_id, "status": "cancelled", "dry_run_only": True},
        "funds_moved": False,
    }


def futures_markets(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.markets(payload))


def futures_markets_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.markets(payload))


def futures_contracts(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.contracts_list(payload))


def futures_contract_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.contract_create(payload))


def futures_order_book(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.order_book(payload))


def futures_order_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.simulate_order(payload))


def futures_order_cancel(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.cancel_order(payload))


def futures_positions(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.positions_list(payload))


def futures_mark_price(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.mark_price(payload))


def futures_index_price(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.index_price(payload))


def futures_risk_check(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.risk_check(payload))


def futures_expiry_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.expiry_simulate(payload))


def futures_delivery_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.delivery_simulate(payload))


def futures_settlement_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.settlement_simulate(payload))


def capacity_indexes(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.indexes(payload))


def capacity_forward_curve(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.forward_curve(payload))


def capacity_forward_curve_simulate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.forward_curve(payload))


def futures_indexes(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.indexes(payload))


def futures_mark_prices(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return _ensure_mapping(_FUTURES_SERVICE.mark_price(payload))
