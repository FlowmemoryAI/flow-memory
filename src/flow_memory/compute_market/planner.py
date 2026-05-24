"""Deterministic Compute Market planning helpers."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from flow_memory.compute_market.models import (
    CapacityWindow,
    ComputeBudgetPolicy,
    ComputeQuote,
    ComputeRoute,
    ComputeRouteDecision,
    EconomicMemoryRecord,
    PaymentIntent,
    ReservationIntent,
    SettlementSimulation,
    TaskEconomicProfile,
)
from flow_memory.compute_market.registry import default_routes


def task_profile_from_mapping(payload: Mapping[str, Any] | None = None) -> TaskEconomicProfile:
    data = dict(payload or {})
    return TaskEconomicProfile(
        task_id=str(data.get("task_id", "local-task")),
        goal_id=str(data.get("goal_id", data.get("goal", "local-goal"))),
        model_requested=str(data.get("model_requested", data.get("model", "small-general"))),
        expected_input_tokens=max(0, int(data.get("expected_input_tokens", data.get("tokens_in", 1000)) or 0)),
        expected_output_tokens=max(0, int(data.get("expected_output_tokens", data.get("tokens_out", 500)) or 0)),
        quality_sensitive=bool(data.get("quality_sensitive", False)),
        latency_sensitive=bool(data.get("latency_sensitive", False)),
        requires_marketplace=bool(data.get("requires_marketplace", data.get("marketplace_only", False))),
        max_budget=float(data.get("max_budget", data.get("budget", 0.0)) or 0.0),
        metadata={str(k): v for k, v in data.items() if k not in {"task_id", "goal_id", "goal", "model_requested", "model", "expected_input_tokens", "tokens_in", "expected_output_tokens", "tokens_out", "quality_sensitive", "latency_sensitive", "requires_marketplace", "marketplace_only", "max_budget", "budget"}},
    )


def budget_policy_from_mapping(payload: Mapping[str, Any] | None = None) -> ComputeBudgetPolicy:
    data = dict(payload or {})
    return ComputeBudgetPolicy(
        max_total_cost=float(data.get("max_total_cost", data.get("budget_limit", data.get("budget", 0.0))) or 0.0),
        max_quote=float(data.get("max_quote", data.get("max_quote_cost", 0.0)) or 0.0),
        max_input_price_per_million=float(data.get("max_input_price_per_million", 0.0) or 0.0),
        max_output_price_per_million=float(data.get("max_output_price_per_million", 0.0) or 0.0),
        strategy=str(data.get("strategy", data.get("preferred_strategy", "cheapest_eligible"))),
        allowed_providers=_as_tuple(data.get("allowed_providers", ())),
        allowed_routes=_as_tuple(data.get("allowed_routes", ())),
        marketplace_only=bool(data.get("marketplace_only", False)),
        allow_fallback=bool(data.get("allow_fallback", True)),
        dry_run_required=bool(data.get("dry_run_required", True)),
        payment_rail=str(data.get("payment_rail", data.get("payment_rail_preference", "local_credits"))),
        policy_id=str(data.get("policy_id", "local-compute-policy")),
    )


def deterministic_compute_quote(route: ComputeRoute, task: TaskEconomicProfile) -> ComputeQuote:
    input_cost = (task.expected_input_tokens / 1_000_000.0) * route.input_price_per_million
    output_cost = (task.expected_output_tokens / 1_000_000.0) * route.output_price_per_million
    total = round(input_cost + output_cost, 8)
    return ComputeQuote(
        quote_id=_stable_id("quote", route.route_id, task.task_id, str(task.expected_input_tokens), str(task.expected_output_tokens)),
        route_id=route.route_id,
        provider_id=route.provider_id,
        task_id=task.task_id,
        model=route.model,
        input_tokens=task.expected_input_tokens,
        output_tokens=task.expected_output_tokens,
        input_cost=round(input_cost, 8),
        output_cost=round(output_cost, 8),
        total_cost=total,
    )


def deterministic_route_decision(
    task: TaskEconomicProfile,
    policy: ComputeBudgetPolicy | None,
    routes: tuple[ComputeRoute, ...] | None = None,
) -> ComputeRouteDecision:
    if policy is None:
        return ComputeRouteDecision(False, "fail_closed", "compute budget policy missing", task, None)
    errors = policy.validate()
    if errors:
        return ComputeRouteDecision(False, "fail_closed", "; ".join(errors), task, policy)
    if task.max_budget and policy.ceiling() and task.max_budget < policy.ceiling():
        policy = ComputeBudgetPolicy(**{**policy.as_record(), "max_total_cost": task.max_budget, "max_quote": min(policy.max_quote or task.max_budget, task.max_budget)})
    candidates = tuple(routes or default_routes())
    eligible = tuple(route for route in candidates if route.eligible_for(policy))
    if task.requires_marketplace:
        eligible = tuple(route for route in eligible if route.provider_class == "marketplace")
    if not eligible:
        return ComputeRouteDecision(False, "fail_closed", "no eligible compute route under policy", task, policy)
    ranked = _rank_routes(eligible, task, policy)
    selected = ranked[0]
    quote = deterministic_compute_quote(selected, task)
    ceiling = policy.ceiling()
    if ceiling and quote.total_cost > ceiling:
        return ComputeRouteDecision(False, "fail_closed", "compute quote exceeds budget policy", task, policy, selected, quote)
    if selected.provider_class == "centralized" and not policy.allow_fallback:
        return ComputeRouteDecision(False, "fail_closed", "centralized fallback not allowed by policy", task, policy, selected, quote)
    reservation = ReservationIntent(
        reservation_id=_stable_id("reservation", task.task_id, selected.route_id),
        provider_id=selected.provider_id,
        route_id=selected.route_id,
        capacity_units=max(1.0, (task.expected_input_tokens + task.expected_output_tokens) / 1000.0),
    )
    return ComputeRouteDecision(True, "selected", "deterministic dry-run route selected", task, policy, selected, quote, reservation, fallback_used=selected.provider_class == "centralized")


def payment_intent_for_decision(decision: ComputeRouteDecision) -> PaymentIntent:
    if not decision.ok or decision.quote is None or decision.policy is None:
        amount = 0.0
        quote_id = ""
        task_id = decision.task.task_id
        rail = "noop"
    else:
        amount = decision.quote.total_cost
        quote_id = decision.quote.quote_id
        task_id = decision.task.task_id
        rail = decision.policy.payment_rail
    return PaymentIntent(
        payment_id=_stable_id("payment", task_id, quote_id, rail),
        task_id=task_id,
        quote_id=quote_id,
        amount=amount,
        rail=rail,
    )


def simulate_settlement(payment: PaymentIntent, provider_id: str = "") -> SettlementSimulation:
    worker_amount = round(payment.amount * 0.8, 8)
    treasury_amount = round(payment.amount - worker_amount, 8)
    return SettlementSimulation(
        settlement_id=_stable_id("settlement", payment.payment_id, provider_id),
        payment_id=payment.payment_id,
        provider_id=provider_id,
        worker_amount=worker_amount,
        treasury_amount=treasury_amount,
    )


def economic_memory_from_decision(decision: ComputeRouteDecision) -> EconomicMemoryRecord:
    route = decision.selected_route
    quote = decision.quote
    return EconomicMemoryRecord(
        record_id=_stable_id("compute_memory", decision.task.goal_id, decision.task.task_id, route.route_id if route else "none"),
        goal_id=decision.task.goal_id,
        task_id=decision.task.task_id,
        route_mode=decision.policy.strategy if decision.policy else "fail_closed",
        provider_id=route.provider_id if route else "",
        provider_class=route.provider_class if route else "none",
        route_id=route.route_id if route else "",
        model_requested=decision.task.model_requested,
        provider_model_id=route.model if route else "",
        tokens_in=quote.input_tokens if quote else 0,
        tokens_out=quote.output_tokens if quote else 0,
        unit_price_input=route.input_price_per_million if route else 0.0,
        unit_price_output=route.output_price_per_million if route else 0.0,
        total_cost=quote.total_cost if quote else 0.0,
        latency_ms=route.latency_ms if route else 0,
        fallback_used=decision.fallback_used,
        quality_signal=route.quality_score if route else 0.0,
    )


def compute_marketplace_plan(payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    data = dict(payload or {})
    task = task_profile_from_mapping(data.get("task") if isinstance(data.get("task"), Mapping) else data)
    policy_payload = data.get("policy") if isinstance(data.get("policy"), Mapping) else data.get("budget_policy")
    if not isinstance(policy_payload, Mapping):
        policy_payload = data
    policy = budget_policy_from_mapping(policy_payload)
    decision = deterministic_route_decision(task, policy)
    payment = payment_intent_for_decision(decision)
    settlement = simulate_settlement(payment, decision.selected_route.provider_id if decision.selected_route else "")
    memory = economic_memory_from_decision(decision)
    return {
        "ok": decision.ok,
        "status": decision.status,
        "reason": decision.reason,
        "task": task.as_record(),
        "policy": policy.as_record(),
        "decision": decision.as_record(),
        "quote": decision.quote.as_record() if decision.quote else {},
        "reservation": decision.reservation.as_record() if decision.reservation else {},
        "payment_intent": payment.as_record(),
        "settlement_simulation": settlement.as_record(),
        "economic_memory": memory.as_record(),
        "dry_run_only": True,
        "no_private_keys": True,
        "no_funds_moved": True,
        "no_broadcast": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }


def capacity_windows() -> tuple[CapacityWindow, ...]:
    return tuple(
        CapacityWindow(route.provider_id, route.route_id, capacity_units=route.capacity_units, price_per_unit=route.input_price_per_million + route.output_price_per_million)
        for route in default_routes()
    )


def _rank_routes(routes: tuple[ComputeRoute, ...], task: TaskEconomicProfile, policy: ComputeBudgetPolicy) -> tuple[ComputeRoute, ...]:
    strategy = policy.strategy
    if task.quality_sensitive:
        strategy = "highest_quality"
    if task.latency_sensitive:
        strategy = "lowest_latency"
    if strategy == "highest_quality":
        return tuple(sorted(routes, key=lambda route: (-route.quality_score, route.input_price_per_million + route.output_price_per_million, route.latency_ms, route.route_id)))
    if strategy == "lowest_latency":
        return tuple(sorted(routes, key=lambda route: (route.latency_ms, route.input_price_per_million + route.output_price_per_million, -route.quality_score, route.route_id)))
    return tuple(sorted(routes, key=lambda route: (route.input_price_per_million + route.output_price_per_million, route.latency_ms, -route.quality_score, route.route_id)))


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value),)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
