"""Compute Market API endpoints for the dependency-free local router."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.compute_market.planner import (
    budget_policy_from_mapping,
    capacity_windows,
    compute_marketplace_plan,
    deterministic_compute_quote,
    deterministic_route_decision,
    economic_memory_from_decision,
    payment_intent_for_decision,
    simulate_settlement,
    task_profile_from_mapping,
)
from flow_memory.compute_market.registry import default_policies, default_providers, default_routes

_ECONOMIC_MEMORY: list[Mapping[str, Any]] = []


def compute_providers() -> Mapping[str, Any]:
    return {"ok": True, "providers": tuple(provider.as_record() for provider in default_providers()), "dry_run_only": True}


def compute_routes() -> Mapping[str, Any]:
    return {"ok": True, "routes": tuple(route.as_record() for route in default_routes()), "dry_run_only": True}


def compute_policies() -> Mapping[str, Any]:
    return {"ok": True, "policies": tuple(policy.as_record() for policy in default_policies()), "dry_run_required": True}


def compute_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return compute_marketplace_plan(payload)


def compute_marketplace_plan_endpoint(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    record = compute_marketplace_plan(payload)
    memory = dict(record.get("economic_memory", {}))
    if memory:
        _ECONOMIC_MEMORY.append(memory)
    return record


def compute_quote(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    task = task_profile_from_mapping(payload.get("task") if isinstance(payload.get("task"), Mapping) else payload)
    route_id = str(payload.get("route_id", ""))
    routes = default_routes()
    route = next((item for item in routes if item.route_id == route_id), routes[0])
    quote = deterministic_compute_quote(route, task)
    return {"ok": True, "quote": quote.as_record(), "dry_run_only": True}


def compute_route(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    task = task_profile_from_mapping(payload.get("task") if isinstance(payload.get("task"), Mapping) else payload)
    policy_payload = payload.get("policy") if isinstance(payload.get("policy"), Mapping) else payload.get("budget_policy")
    policy = budget_policy_from_mapping(policy_payload if isinstance(policy_payload, Mapping) else payload)
    decision = deterministic_route_decision(task, policy)
    memory = economic_memory_from_decision(decision).as_record()
    _ECONOMIC_MEMORY.append(memory)
    return {"ok": decision.ok, "decision": decision.as_record(), "economic_memory": memory, "dry_run_only": True}


def compute_payment_plan(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    decision_record = compute_route(payload)
    decision_payload = dict(decision_record.get("decision", {}))
    # Recompute the typed decision from the same payload to avoid trusting client-supplied records.
    task = task_profile_from_mapping(payload.get("task") if isinstance(payload.get("task"), Mapping) else payload)
    policy_payload = payload.get("policy") if isinstance(payload.get("policy"), Mapping) else payload.get("budget_policy")
    decision = deterministic_route_decision(task, budget_policy_from_mapping(policy_payload if isinstance(policy_payload, Mapping) else payload))
    payment = payment_intent_for_decision(decision)
    return {"ok": bool(decision_payload.get("ok", decision.ok)), "payment_intent": payment.as_record(), "dry_run_only": True, "no_private_keys": True, "no_funds_moved": True, "no_broadcast": True}


def compute_simulate_settlement(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    task = task_profile_from_mapping(payload.get("task") if isinstance(payload.get("task"), Mapping) else payload)
    policy_payload = payload.get("policy") if isinstance(payload.get("policy"), Mapping) else payload.get("budget_policy")
    decision = deterministic_route_decision(task, budget_policy_from_mapping(policy_payload if isinstance(policy_payload, Mapping) else payload))
    payment = payment_intent_for_decision(decision)
    settlement = simulate_settlement(payment, decision.selected_route.provider_id if decision.selected_route else "")
    return {"ok": True, "settlement": settlement.as_record(), "dry_run_only": True, "no_live_settlement": True}


def compute_economic_memory() -> Mapping[str, Any]:
    return {"ok": True, "records": tuple(dict(record) for record in _ECONOMIC_MEMORY), "dry_run_only": True}


def compute_economic_memory_query(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    route_id = str(payload.get("route_id", ""))
    provider_id = str(payload.get("provider_id", ""))
    goal_id = str(payload.get("goal_id", ""))
    matches = []
    for record in _ECONOMIC_MEMORY:
        if route_id and record.get("route_id") != route_id:
            continue
        if provider_id and record.get("provider_id") != provider_id:
            continue
        if goal_id and record.get("goal_id") != goal_id:
            continue
        matches.append(dict(record))
    return {"ok": True, "records": tuple(matches), "count": len(matches)}


def compute_capacity_windows() -> Mapping[str, Any]:
    return {"ok": True, "capacity_windows": tuple(window.as_record() for window in capacity_windows()), "dry_run_only": True}
