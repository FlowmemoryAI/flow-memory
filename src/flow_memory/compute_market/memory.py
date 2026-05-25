"""Economic memory helpers and analytics for compute-market decisions."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

from flow_memory.compute_market.models import (
    ComputeQuote,
    EconomicMemoryQueryRequest,
    EconomicMemoryQueryResponse,
    EconomicMemoryRecord,
    RouteDecision,
    SettlementIntent,
    TaskEconomicProfile,
)
from flow_memory.crypto.hashes import content_hash


def build_economic_memory_record(
    *,
    profile: TaskEconomicProfile,
    quote: ComputeQuote | None,
    decision: RouteDecision,
    settlement: SettlementIntent,
) -> EconomicMemoryRecord:
    selected = quote
    rejected = decision.rejected_routes
    quote_snapshot = selected.as_record() if selected is not None else {}
    policy_snapshot = {
        "policy_result": decision.policy_result,
        "rejected_reasons": decision.rejected_reasons,
        "fail_closed_errors": decision.fail_closed_errors,
        "rejected_explanations": decision.rejected_explanations,
        "selection_strategy": decision.selection_strategy,
        "policy_trace": decision.policy_trace,
        "policy_hash": decision.policy_hash,
    }
    policy_failure_codes = tuple(dict.fromkeys(reason for values in decision.rejected_reasons.values() for reason in values))
    record_payload = {
        "task_id": profile.task_id,
        "decision_id": decision.decision_id,
        "provider_id": selected.provider_id if selected else "",
        "route_id": selected.route_id if selected else "",
        "task_hash": profile.task_hash,
    }
    return EconomicMemoryRecord(
        task_id=profile.task_id,
        agent_id=profile.agent_id,
        goal_id=profile.goal_id,
        provider_or_route=selected.provider_or_route if selected else "",
        provider_type=selected.provider_type if selected else "",
        marketplace_route=bool(selected and selected.market_type == "marketplace"),
        unit_prices={selected.unit_type: float(selected.unit_price or 0.0)} if selected else {},
        unit_type=selected.unit_type if selected else "",
        estimated_units=selected.estimated_units if selected else 0.0,
        actual_units=None,
        estimated_total_cost=selected.estimated_total_cost if selected else None,
        actual_total_cost=None,
        estimated_latency_ms=selected.estimated_latency_ms if selected else 0,
        actual_latency_ms=None,
        task_roi=selected.task_roi if selected else 0.0,
        roi_basis="estimated_value_minus_estimated_cost_over_cost",
        fallback_used=bool(selected and selected.provider_type == "fallback"),
        fallback_reason="selected fallback route" if selected and selected.provider_type == "fallback" else "",
        rejected_routes=rejected,
        policy_snapshot=policy_snapshot,
        quote_snapshot=quote_snapshot,
        settlement_intent_id=settlement.settlement_intent_id,
        dry_run_only=True,
        selected_reason=decision.selected_reason,
        record_id=f"economic_memory_{content_hash(record_payload)[:24]}",
        tenant_id=profile.tenant_id,
        workspace_id=profile.workspace_id,
        request_id=decision.request_id,
        decision_id=decision.decision_id,
        provider_id=selected.provider_id if selected else "",
        route_id=selected.route_id if selected else "",
        task_type=profile.task_type,
        task_hash=profile.task_hash,
        policy_result=decision.policy_result,
        selected_route_id=selected.route_id if selected else "",
        route_rejected_count=len(rejected),
        stale_quote=bool(selected and selected.stale),
        policy_failure_codes=policy_failure_codes,
        idempotency_key=decision.idempotency_key,
    )


def economic_memory_schema() -> tuple[str, ...]:
    return tuple(EconomicMemoryRecord(
        task_id="schema",
        agent_id="",
        goal_id="",
        provider_or_route="",
        provider_type="",
        marketplace_route=False,
        unit_prices={},
        unit_type="",
        estimated_units=0.0,
        actual_units=None,
        estimated_total_cost=None,
        actual_total_cost=None,
        estimated_latency_ms=0,
        actual_latency_ms=None,
        task_roi=0.0,
        roi_basis="",
        fallback_used=False,
        fallback_reason="",
        rejected_routes=(),
        policy_snapshot={},
        quote_snapshot={},
        settlement_intent_id="",
        dry_run_only=True,
        selected_reason="",
    ).as_record().keys())


def query_request_from_payload(payload: Mapping[str, Any] | None = None) -> EconomicMemoryQueryRequest:
    payload = payload or {}
    return EconomicMemoryQueryRequest(
        query=str(payload.get("query", "summary")),
        start_time=str(payload.get("start_time", payload.get("from", ""))),
        end_time=str(payload.get("end_time", payload.get("to", ""))),
        agent_id=str(payload.get("agent_id", "")),
        goal_id=str(payload.get("goal_id", "")),
        provider_id=str(payload.get("provider_id", "")),
        route_id=str(payload.get("route_id", "")),
        task_type=str(payload.get("task_type", "")),
        marketplace_only=_optional_bool(payload.get("marketplace_only")),
        unit_type=str(payload.get("unit_type", "")),
        policy_result=str(payload.get("policy_result", "")),
        selected_only=bool(payload.get("selected_only", False)),
        rejected_only=bool(payload.get("rejected_only", False)),
        fallback_used=_optional_bool(payload.get("fallback_used")),
        limit=min(max(1, int(float(payload.get("limit", 100) or 100))), 500),
        cursor=str(payload.get("cursor", "")),
    )


def filter_economic_records(records: tuple[Mapping[str, Any], ...], request: EconomicMemoryQueryRequest) -> tuple[Mapping[str, Any], ...]:
    filtered = []
    for record in records:
        if request.start_time and str(record.get("created_at", "")) < request.start_time:
            continue
        if request.end_time and str(record.get("created_at", "")) > request.end_time:
            continue
        if request.agent_id and record.get("agent_id") != request.agent_id:
            continue
        if request.goal_id and record.get("goal_id") != request.goal_id:
            continue
        if request.provider_id and record.get("provider_id") != request.provider_id:
            continue
        if request.route_id and record.get("route_id") != request.route_id:
            continue
        if request.task_type and record.get("task_type") != request.task_type:
            continue
        if request.marketplace_only is not None and bool(record.get("marketplace_route")) != request.marketplace_only:
            continue
        if request.unit_type and record.get("unit_type") != request.unit_type:
            continue
        if request.policy_result and record.get("policy_result") != request.policy_result:
            continue
        if request.selected_only and not record.get("selected_route_id"):
            continue
        if request.rejected_only and not record.get("rejected_routes"):
            continue
        if request.fallback_used is not None and bool(record.get("fallback_used")) != request.fallback_used:
            continue
        filtered.append(record)
    offset = int(request.cursor or 0) if str(request.cursor or "").isdigit() else 0
    return tuple(filtered[offset: offset + request.limit])


def query_economic_memory(records: tuple[Mapping[str, Any], ...], query: str = "summary") -> Mapping[str, Any]:
    request = EconomicMemoryQueryRequest(query=query)
    response = query_economic_memory_typed(records, request)
    data = response.data
    return {"ok": response.ok, "query": query, "record_count": response.sample_size, **data}


def query_economic_memory_typed(
    records: tuple[Mapping[str, Any], ...],
    request: EconomicMemoryQueryRequest | None = None,
) -> EconomicMemoryQueryResponse:
    request = request or EconomicMemoryQueryRequest()
    filtered = filter_economic_records(records, request)
    if not filtered:
        return EconomicMemoryQueryResponse(
            ok=True,
            query=request.query,
            data={"records": (), "answer": "no economic memory records"},
            confidence=0.0,
            sample_size=0,
            time_range={"start_time": request.start_time, "end_time": request.end_time},
            filters_applied=request.as_record(),
            warnings=("no matching durable economic memory records",),
            next_recommended_action="run a dry-run compute plan to create durable economic memory",
            cursor="",
            record_count=0,
        )
    data = _analytics(filtered)
    confidence = min(1.0, len(filtered) / 20.0)
    return EconomicMemoryQueryResponse(
        ok=True,
        query=request.query,
        data=data,
        confidence=round(confidence, 4),
        sample_size=len(filtered),
        time_range={"start_time": request.start_time, "end_time": request.end_time},
        filters_applied=request.as_record(),
        warnings=_analytics_warnings(filtered),
        next_recommended_action=_next_action(data),
        cursor=str(request.limit) if len(filtered) == request.limit else "",
        record_count=len(filtered),
    )


def _analytics(records: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any]:
    cheapest = min(records, key=lambda item: _cost(item))
    best_roi = max(records, key=lambda item: float(item.get("task_roi", 0.0) or 0.0))
    latency_adjusted = min(records, key=lambda item: (_latency_adjusted_cost(item), _cost(item)))
    fallback_count = sum(1 for item in records if item.get("fallback_used"))
    marketplace_count = sum(1 for item in records if item.get("marketplace_route"))
    rejected_counter: Counter[str] = Counter()
    selected_route_counter: Counter[str] = Counter()
    selected_reason_counter: Counter[str] = Counter()
    provider_confidence: dict[str, list[float]] = defaultdict(list)
    provider_costs: dict[str, list[float]] = defaultdict(list)
    provider_latency: dict[str, list[float]] = defaultdict(list)
    stale_count = 0
    budget_overrun_attempts = 0
    for item in records:
        provider = str(item.get("provider_or_route") or item.get("route_id") or "unknown")
        provider_costs[provider].append(_cost(item))
        provider_latency[provider].append(float(item.get("estimated_latency_ms", 0) or 0))
        selected_route_counter[provider] += 1
        reason = str(item.get("selected_reason", ""))
        if reason:
            selected_reason_counter[reason] += 1
        quote = item.get("quote_snapshot", {})
        if isinstance(quote, Mapping):
            provider_confidence[provider].append(float(quote.get("confidence", 0.0) or 0.0))
            stale_count += int(bool(quote.get("stale")))
        policy = item.get("policy_snapshot", {})
        if isinstance(policy, Mapping):
            reasons = policy.get("rejected_reasons", {})
            if isinstance(reasons, Mapping):
                for values in reasons.values():
                    for policy_reason in values:
                        rejected_counter[str(policy_reason)] += 1
                        if str(policy_reason) == "budget_exceeded":
                            budget_overrun_attempts += 1
    provider_reliability = {
        provider: round(sum(values) / max(1, len(values)), 6)
        for provider, values in provider_confidence.items()
    }
    estimated_vs_actual_cost = tuple(
        {
            "task_id": item.get("task_id", ""),
            "estimated_total_cost": item.get("estimated_total_cost"),
            "actual_total_cost": item.get("actual_total_cost"),
            "delta": _delta(item.get("estimated_total_cost"), item.get("actual_total_cost")),
        }
        for item in records
        if item.get("actual_total_cost") is not None
    )
    estimated_vs_actual_latency = tuple(
        {
            "task_id": item.get("task_id", ""),
            "estimated_latency_ms": item.get("estimated_latency_ms"),
            "actual_latency_ms": item.get("actual_latency_ms"),
            "delta": _delta(item.get("estimated_latency_ms"), item.get("actual_latency_ms")),
        }
        for item in records
        if item.get("actual_latency_ms") is not None
    )
    human_approval_routes = tuple(
        item.get("provider_or_route", "")
        for item in records
        if "human_approval_required_not_granted" in tuple(item.get("policy_failure_codes", ()))
    )
    return {
        "records": records,
        "cheapest_route": cheapest.get("provider_or_route", ""),
        "best_roi_route": best_roi.get("provider_or_route", ""),
        "best_latency_adjusted_cost_route": latency_adjusted.get("provider_or_route", ""),
        "provider_reliability": provider_reliability,
        "route_rejection_rates": tuple((reason, count / max(1, len(records))) for reason, count in rejected_counter.most_common()),
        "fallback_used_count": fallback_count,
        "fallback_frequency": fallback_count / max(1, len(records)),
        "stale_quote_count": stale_count,
        "stale_quote_frequency": stale_count / max(1, len(records)),
        "policy_failure_distribution": tuple(rejected_counter.most_common()),
        "marketplace_route_count": marketplace_count,
        "marketplace_route_performance": tuple(
            (provider, round(sum(costs) / max(1, len(costs)), 8))
            for provider, costs in provider_costs.items()
            if provider
        ),
        "budget_overrun_attempts": budget_overrun_attempts,
        "estimated_vs_actual_cost": estimated_vs_actual_cost,
        "estimated_vs_actual_latency": estimated_vs_actual_latency,
        "provider_drift_over_time": tuple(
            (provider, {"avg_cost": _avg(costs), "avg_latency_ms": _avg(provider_latency[provider])})
            for provider, costs in provider_costs.items()
        ),
        "tasks_should_be_deferred_due_to_compute_cost": tuple(
            item.get("task_id", "") for item in records if float(item.get("task_roi", 0.0) or 0.0) < 0.0
        ),
        "routes_needing_human_approval_most_often": human_approval_routes,
        "common_policy_failures": tuple(rejected_counter.most_common()),
        "selected_route_counts": tuple(selected_route_counter.most_common()),
        "selected_reason_counts": tuple(selected_reason_counter.most_common()),
        "stale_pricing_detected": stale_count > 0,
        "stale_price_routes": tuple(item.get("provider_or_route", "") for item in records if _quote_flag(item, "stale")),
        "routes_often_fail_policy": tuple(reason for reason, count in rejected_counter.items() if count > 0),
    }


def _cost(item: Mapping[str, Any]) -> float:
    value = item.get("estimated_total_cost")
    return float(value) if isinstance(value, (int, float)) else float("inf")


def _latency_adjusted_cost(item: Mapping[str, Any]) -> float:
    latency = float(item.get("estimated_latency_ms", 0) or 1)
    return _cost(item) * max(1.0, latency / 1000.0)


def _quote_flag(item: Mapping[str, Any], flag: str) -> bool:
    quote = item.get("quote_snapshot", {})
    return bool(isinstance(quote, Mapping) and quote.get(flag))


def _optional_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    return bool(value)


def _avg(values: list[float]) -> float:
    return round(sum(values) / max(1, len(values)), 8)


def _delta(left: object, right: object) -> float | None:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(right) - float(left)
    return None


def _analytics_warnings(records: tuple[Mapping[str, Any], ...]) -> tuple[str, ...]:
    warnings = []
    if len(records) < 5:
        warnings.append("low sample size; confidence is limited")
    if any(_quote_flag(item, "stale") for item in records):
        warnings.append("stale quote records are present")
    return tuple(warnings)


def _next_action(data: Mapping[str, Any]) -> str:
    if data.get("stale_pricing_detected"):
        return "refresh provider quotes and invalidate stale cache entries"
    if data.get("budget_overrun_attempts"):
        return "review per-agent and per-goal budget policies"
    return "continue durable compute planning and monitor provider drift"
