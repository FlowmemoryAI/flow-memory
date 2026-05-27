"""Deterministic Flow Memory Compute Market planning pipeline."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from flow_memory.compute_market.memory import build_economic_memory_record, query_economic_memory
from flow_memory.compute_market.models import (
    AgentBudgetPolicy,
    ComputeMarketPolicy,
    ComputePlan,
    ComputeProvider,
    ComputeQuote,
    ComputeRoute,
    BackgroundRunPolicy,
    PLANNER_VERSION,
    RouteDecision,
    SelectionStrategy,
    TaskEconomicProfile,
    IntelligenceTier,
    QualityTarget,
    ReasoningBudget,
    ReasoningLevel,
    TaskUrgency,
)
from flow_memory.compute_market.payment import build_payment_plan, simulate_settlement
from flow_memory.compute_market.policy import build_policy_trace, evaluate_quote, explain_rejections
from flow_memory.compute_market.pricing import collect_quotes, normalize_quotes
from flow_memory.compute_market.registry import default_compute_providers
from flow_memory.compute_market.simulation import simulated_routes
from flow_memory.core.types import new_id
from flow_memory.crypto.hashes import content_hash

_UNSAFE_PAYMENT_PAYLOAD_KEYS = frozenset(
    {
        "private_key",
        "privateKey",
        "seed_phrase",
        "seedPhrase",
        "seed phrase",
        "mnemonic",
        "secret_key",
        "wallet_private_key",
        "live_settlement",
        "broadcast",
        "broadcast_allowed",
        "broadcastAllowed",
        "sendTransaction",
        "signTransaction",
        "custody",
        "withdraw",
        "deposit",
        "transfer",
        "settle",
        "settlement_broadcast",
    }
)


def build_task_profile(payload: Mapping[str, Any] | None = None) -> TaskEconomicProfile:
    payload = payload or {}
    _assert_no_live_payment_fields(payload)
    profile = payload.get("profile")
    if isinstance(profile, Mapping):
        payload = {**profile, **{key: value for key, value in payload.items() if key != "profile"}}
    task = str(payload.get("task") or payload.get("task_description") or "plan compute for agent task")
    estimated_units = payload.get("estimated_units", {})
    if not isinstance(estimated_units, Mapping):
        estimated_units = {}
    estimated_unit_map = {str(key): float(value) for key, value in estimated_units.items()}
    task_type = str(payload.get("task_type") or _infer_task_type(task))
    profile_record: dict[str, Any] = {
        "task": task,
        "agent_id": str(payload.get("agent_id", "")),
        "goal_id": str(payload.get("goal_id", "")),
        "estimated_units": estimated_unit_map,
        "task_type": task_type,
    }
    task_hash = str(payload.get("task_hash") or content_hash(profile_record))
    return TaskEconomicProfile(
        task_id=str(payload.get("task_id") or f"compute_task_{task_hash[:16]}"),
        task_description=task,
        agent_id=str(payload.get("agent_id", "")),
        goal_id=str(payload.get("goal_id", "")),
        expected_output_type=str(payload.get("expected_output_type", "artifact")),
        latency_requirement_ms=int(float(payload.get("latency_requirement_ms", payload.get("max_latency_ms", 0)) or 0)),
        budget=float(payload.get("budget", payload.get("max_total_cost", 0.0)) or 0.0),
        quality_requirement=str(payload.get("quality_requirement", "standard")),
        estimated_value=_optional_float(payload.get("estimated_value")),
        estimated_units=estimated_unit_map,
        tenant_id=str(payload.get("tenant_id", payload.get("workspace_id", ""))),
        workspace_id=str(payload.get("workspace_id", payload.get("tenant_id", ""))),
        task_type=task_type,
        task_hash=task_hash,
        intelligence_tier=_intelligence_tier(payload),
        reasoning_level=_reasoning_level(payload),
        reasoning_budget=_reasoning_budget(payload).as_record(),
        background_run_policy=_background_run_policy(payload).as_record(),
        urgency=_task_urgency(payload).as_record(),
        quality_target=_quality_target(payload).as_record(),
    )


def budget_policy_from_payload(payload: Mapping[str, Any] | None = None) -> AgentBudgetPolicy:
    payload = payload or {}
    source = payload.get("budget_policy", payload.get("policy", payload))
    if not isinstance(source, Mapping):
        source = payload
    return AgentBudgetPolicy(
        max_total_cost=float(source.get("max_total_cost", payload.get("budget", 0.0)) or 0.0),
        max_unit_price=float(source.get("max_unit_price", 0.0) or 0.0),
        allowed_assets=_tuple(source.get("allowed_assets", payload.get("payment_asset_preferences", payload.get("asset", ())))),
        allowed_networks=_tuple(source.get("allowed_networks", payload.get("network_preferences", payload.get("network", ())))),
        allowed_providers=_tuple(source.get("allowed_providers", payload.get("provider_constraints", ()))),
        denied_providers=_tuple(source.get("denied_providers", ())),
        require_roi_positive=bool(source.get("require_roi_positive", False)),
        require_human_approval_above=float(source.get("require_human_approval_above", 0.0) or 0.0),
        human_approval_granted=bool(
            source.get(
                "human_approval_granted",
                source.get("human_approval_present", payload.get("human_approval_granted", False)),
            )
        ),
        max_latency_ms=int(float(source.get("max_latency_ms", payload.get("max_latency_ms", 0)) or 0)),
        max_slippage_bps=int(float(source.get("max_slippage_bps", 0) or 0)),
        quote_ttl_seconds=int(float(source.get("quote_ttl_seconds", 0) or 0)),
        allow_unknown_price=bool(source.get("allow_unknown_price", False)),
        allow_stale_quote=bool(source.get("allow_stale_quote", False)),
        settlement_modes_allowed=_tuple(source.get("settlement_modes_allowed", ())),
        dry_run_required=bool(source.get("dry_run_required", True)),
        fallback_allowed=bool(source.get("fallback_allowed", payload.get("fallback_allowed", True))),
        require_capacity_confirmation=bool(source.get("require_capacity_confirmation", False)),
        max_retries=int(float(source.get("max_retries", 2) or 2)),
        max_provider_timeout_ms=int(float(source.get("max_provider_timeout_ms", 2_000) or 2_000)),
        max_global_planning_timeout_ms=int(float(source.get("max_global_planning_timeout_ms", 10_000) or 10_000)),
        require_audit_log=bool(source.get("require_audit_log", True)),
        require_idempotency_key=bool(source.get("require_idempotency_key", False)),
        require_verified_provider=bool(source.get("require_verified_provider", False)),
        require_signed_quote=bool(source.get("require_signed_quote", False)),
        max_budget_period=str(source.get("max_budget_period", "daily")),
        per_agent_daily_budget=float(source.get("per_agent_daily_budget", 0.0) or 0.0),
        per_goal_budget=float(source.get("per_goal_budget", 0.0) or 0.0),
        per_workspace_budget=float(source.get("per_workspace_budget", 0.0) or 0.0),
        provider_rate_limit_policy=_mapping(source.get("provider_rate_limit_policy", {})),
    )


def market_policy_from_payload(payload: Mapping[str, Any] | None = None) -> ComputeMarketPolicy:
    payload = payload or {}
    source = payload.get("market_policy", payload.get("policy", payload))
    if not isinstance(source, Mapping):
        source = payload
    strategy = str(payload.get("selection_strategy", source.get("selection_strategy", SelectionStrategy.BALANCED.value)))
    return ComputeMarketPolicy(
        marketplace_only=bool(source.get("marketplace_only", payload.get("marketplace_only", False))),
        dry_run_required=True,
        fallback_allowed=bool(source.get("fallback_allowed", payload.get("fallback_allowed", True))),
        require_capacity_confirmation=bool(source.get("require_capacity_confirmation", False)),
        allow_unknown_price=bool(source.get("allow_unknown_price", False)),
        allow_stale_quote=bool(source.get("allow_stale_quote", False)),
        selection_strategy=strategy,
        settlement_modes_allowed=_tuple(
            source.get(
                "settlement_modes_allowed",
                (
                    "http_402_dry_run",
                    "solana_usdc_dry_run",
                    "base_sepolia_erc4337_dry_run",
                    "generic_dry_run",
                    "no_payment",
                ),
            )
        ),
        quote_ttl_seconds=int(float(source.get("quote_ttl_seconds", 300) or 300)),
        policy_id=str(source.get("policy_id", "default-compute-market-policy")),
        policy_version=str(source.get("policy_version", "v2")),
        max_retries=int(float(source.get("max_retries", 2) or 2)),
        max_provider_timeout_ms=int(float(source.get("max_provider_timeout_ms", 2_000) or 2_000)),
        max_global_planning_timeout_ms=int(float(source.get("max_global_planning_timeout_ms", 10_000) or 10_000)),
        require_audit_log=bool(source.get("require_audit_log", True)),
        require_idempotency_key=bool(source.get("require_idempotency_key", False)),
        require_verified_provider=bool(source.get("require_verified_provider", False)),
        require_signed_quote=bool(source.get("require_signed_quote", False)),
        require_human_approval_above=float(source.get("require_human_approval_above", 0.0) or 0.0),
        max_latency_ms=int(float(source.get("max_latency_ms", 0) or 0)),
        max_slippage_bps=int(float(source.get("max_slippage_bps", 0) or 0)),
        per_agent_daily_budget=float(source.get("per_agent_daily_budget", 0.0) or 0.0),
        per_goal_budget=float(source.get("per_goal_budget", 0.0) or 0.0),
        per_workspace_budget=float(source.get("per_workspace_budget", 0.0) or 0.0),
        provider_rate_limit_policy=_mapping(source.get("provider_rate_limit_policy", {})),
        tenant_id=str(payload.get("tenant_id", payload.get("workspace_id", ""))),
        workspace_id=str(payload.get("workspace_id", payload.get("tenant_id", ""))),
    )


def discover_providers(_payload: Mapping[str, Any] | None = None) -> tuple[ComputeProvider, ...]:
    return default_compute_providers()


def discover_routes(payload: Mapping[str, Any] | None = None) -> tuple[ComputeRoute, ...]:
    payload = payload or {}
    scenario = str(payload.get("scenario", "provider_quote_available"))
    routes = simulated_routes(scenario)
    provider_filter = set(_tuple(payload.get("provider_constraints", ())))
    if provider_filter:
        routes = tuple(route for route in routes if route.provider_id in provider_filter)
    return routes


def build_compute_plan(payload: Mapping[str, Any] | None = None) -> ComputePlan:
    payload = payload or {}
    _assert_no_live_payment_fields(payload)
    request_id = str(payload.get("request_id") or new_id("request"))
    idempotency_key = str(payload.get("idempotency_key", ""))
    profile = build_task_profile(payload)
    budget_policy = budget_policy_from_payload(payload)
    market_policy = market_policy_from_payload(payload)
    providers = discover_providers(payload)
    routes = discover_routes(payload)
    scenario = str(payload.get("scenario", "provider_quote_available"))
    quotes = normalize_quotes(collect_quotes(routes, profile, scenario=scenario))
    decision = decide_route(
        quotes,
        routes,
        profile,
        budget_policy,
        market_policy,
        request_id=request_id,
        idempotency_key=idempotency_key,
        payload=payload,
        providers=providers,
    )
    selected_quote = _quote_by_route(quotes, decision.selected_route)
    payment_plan = build_payment_plan(selected_quote, dry_run_required=market_policy.dry_run_required)
    settlement = simulate_settlement(selected_quote, payment_plan)
    memory = build_economic_memory_record(profile=profile, quote=selected_quote, decision=decision, settlement=settlement)
    warnings = tuple(dict.fromkeys((*decision.warnings, *payment_plan.warnings)))
    next_safe_actions = payment_plan.next_safe_actions
    if decision.fail_closed_errors:
        next_safe_actions = ("relax policy or wait for eligible capacity before retrying", *next_safe_actions)
    return ComputePlan(
        ok=not decision.fail_closed_errors,
        profile=profile.as_record(),
        selected_route=decision.selected_route,
        normalized_quote=decision.normalized_quote,
        rejected_routes=decision.rejected_routes,
        rejected_reasons=decision.rejected_reasons,
        policy_result=decision.policy_result,
        payment_plan=payment_plan.as_record(),
        settlement_intent=settlement.as_record(),
        economic_memory_preview=memory.as_record(),
        warnings=warnings,
        next_safe_actions=next_safe_actions,
        fail_closed_errors=decision.fail_closed_errors,
        rejected_explanations=decision.rejected_explanations,
        provider_count=len(providers),
        route_count=len(routes),
        quote_count=len(quotes),
        request_id=request_id,
        idempotency_key=idempotency_key,
        decision_id=decision.decision_id,
        policy_trace=decision.policy_trace,
        route_decision=decision.as_record(),
        dry_run_only=True,
        funds_moved=False,
        broadcast_allowed=False,
        private_key_required=False,
    )


def decide_route(
    quotes: tuple[ComputeQuote, ...],
    routes: tuple[ComputeRoute, ...],
    profile: TaskEconomicProfile,
    budget_policy: AgentBudgetPolicy,
    market_policy: ComputeMarketPolicy,
    *,
    request_id: str = "",
    idempotency_key: str = "",
    payload: Mapping[str, Any] | None = None,
    providers: tuple[ComputeProvider, ...] = (),
) -> RouteDecision:
    route_by_id = {route.route_id: route for route in routes}
    accepted: list[ComputeQuote] = []
    rejected: list[Mapping[str, Any]] = []
    rejected_reasons: dict[str, tuple[str, ...]] = {}
    warnings: list[str] = []
    rejected_explanations: dict[str, tuple[Mapping[str, str], ...]] = {}
    for quote in quotes:
        route = route_by_id[quote.route_id]
        ok, reasons, route_warnings = evaluate_quote(quote, route, profile, budget_policy, market_policy)
        warnings.extend(route_warnings)
        if ok:
            accepted.append(replace(quote, policy_result="accepted"))
        else:
            rejected_quote = replace(quote, rejected_reasons=reasons, policy_result="rejected")
            rejected.append(rejected_quote.as_record())
            rejected_reasons[quote.route_id] = reasons
            rejected_explanations[quote.route_id] = explain_rejections(reasons)
    policy_trace = build_policy_trace(market_policy, rejected_reasons if not accepted else {}, tuple(dict.fromkeys(warnings)))
    decision_id = _decision_id(profile, market_policy, quotes, request_id, idempotency_key)
    common: dict[str, Any] = {
        "decision_id": decision_id,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "agent_id": profile.agent_id,
        "goal_id": profile.goal_id,
        "tenant_id": profile.tenant_id,
        "workspace_id": profile.workspace_id,
        "task_profile_hash": profile.task_hash,
        "policy_hash": content_hash(market_policy.as_record()),
        "strategy": market_policy.selection_strategy,
        "provider_candidates": tuple(provider.provider_id for provider in providers) or tuple(route.provider_id for route in routes),
        "quote_snapshots": tuple(quote.as_record() for quote in quotes),
        "normalized_quotes": tuple(quote.as_record() for quote in quotes),
        "policy_trace": policy_trace.as_record(),
        "planner_version": PLANNER_VERSION,
        "replay_payload": dict(payload or {}),
    }
    if not accepted:
        failures = _fail_closed_errors(rejected_reasons, market_policy)
        return RouteDecision(
            selected_route=None,
            normalized_quote=None,
            accepted_routes=(),
            rejected_routes=tuple(rejected),
            rejected_reasons=rejected_reasons,
            policy_result="fail_closed",
            fail_closed_errors=failures,
            rejected_explanations=rejected_explanations,
            selection_strategy=market_policy.selection_strategy,
            warnings=tuple(dict.fromkeys(warnings)),
            confidence=0.0,
            tie_breakers=_tie_breakers(market_policy.selection_strategy),
            **common,
        )
    selected = _select_quote(accepted, market_policy.selection_strategy)
    selected_reason = _selected_reason(selected, market_policy.selection_strategy)
    accepted_records = tuple(
        replace(quote, selected_reason=(selected_reason if quote.route_id == selected.route_id else "")).as_record()
        for quote in accepted
    )
    return RouteDecision(
        selected_route=route_by_id[selected.route_id].as_record(),
        normalized_quote=replace(selected, selected_reason=selected_reason, policy_result="selected").as_record(),
        accepted_routes=accepted_records,
        rejected_routes=tuple(rejected),
        rejected_reasons=rejected_reasons,
        policy_result="accepted",
        rejected_explanations=rejected_explanations,
        selection_strategy=market_policy.selection_strategy,
        selected_reason=selected_reason,
        confidence=selected.confidence,
        warnings=tuple(dict.fromkeys(warnings)),
        tie_breakers=_tie_breakers(market_policy.selection_strategy),
        **common,
    )


def replay_decision(original: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = original.get("replay_payload", {})
    current = build_compute_plan(payload if isinstance(payload, Mapping) else {}).as_record()
    original_selected = original.get("selected_route") or {}
    current_selected = current.get("selected_route") or {}
    differences = {
        "selected_route_changed": _field(original_selected, "route_id") != _field(current_selected, "route_id"),
        "policy_result_changed": original.get("policy_result") != current.get("policy_result"),
        "quote_drift": _quote_drift(original.get("normalized_quote"), current.get("normalized_quote")),
        "policy_drift": original.get("policy_hash") != current.get("policy_hash"),
        "provider_availability_drift": _provider_drift(original.get("quote_snapshots", ()), current.get("normalized_quote")),
    }
    return {
        "ok": True,
        "original_decision": original,
        "current_decision": current,
        "differences": differences,
        "quote_drift": differences["quote_drift"],
        "policy_drift": differences["policy_drift"],
        "provider_availability_drift": differences["provider_availability_drift"],
        "mutated_original": False,
    }


def query_memory(records: tuple[Mapping[str, Any], ...], query: str = "summary") -> Mapping[str, Any]:
    return query_economic_memory(records, query=query)


def _select_quote(quotes: list[ComputeQuote], strategy: str) -> ComputeQuote:
    if strategy == SelectionStrategy.LOWEST_COST.value:
        return min(quotes, key=lambda quote: (_cost(quote), quote.estimated_latency_ms, -quote.confidence))
    if strategy == SelectionStrategy.BEST_LATENCY.value:
        return min(quotes, key=lambda quote: (quote.estimated_latency_ms, _cost(quote)))
    if strategy == SelectionStrategy.BEST_ROI.value:
        return max(quotes, key=lambda quote: (quote.task_roi, -_cost(quote), quote.confidence))
    if strategy == SelectionStrategy.MARKETPLACE_PREFERRED.value:
        return min(quotes, key=lambda quote: (quote.market_type != "marketplace", _cost(quote), quote.estimated_latency_ms))
    if strategy == SelectionStrategy.CAPACITY_GUARANTEED.value:
        return min(quotes, key=lambda quote: (not quote.capacity_available, quote.reservation_required, _cost(quote)))
    if strategy == SelectionStrategy.RELIABILITY_WEIGHTED.value:
        return max(quotes, key=lambda quote: (quote.confidence - min(_cost(quote), 10.0) / 10.0, -quote.estimated_latency_ms))
    return min(quotes, key=lambda quote: (_cost(quote), quote.estimated_latency_ms, -quote.confidence, quote.market_type != "marketplace"))


def _selected_reason(quote: ComputeQuote, strategy: str) -> str:
    return f"selected_by_{strategy}: {quote.provider_or_route}"


def _cost(quote: ComputeQuote) -> float:
    return float(quote.estimated_total_cost) if quote.estimated_total_cost is not None else float("inf")


def _quote_by_route(quotes: tuple[ComputeQuote, ...], route_record: Mapping[str, Any] | None) -> ComputeQuote | None:
    if route_record is None:
        return None
    route_id = str(route_record.get("route_id", ""))
    for quote in quotes:
        if quote.route_id == route_id:
            return quote
    return None


def _fail_closed_errors(rejected_reasons: Mapping[str, tuple[str, ...]], market_policy: ComputeMarketPolicy) -> tuple[str, ...]:
    reasons = tuple(dict.fromkeys(reason for values in rejected_reasons.values() for reason in values))
    if not rejected_reasons:
        return ("no_valid_route",)
    if market_policy.marketplace_only and "marketplace_only_no_marketplace_route" in reasons:
        return ("marketplace_only_no_marketplace_route", *tuple(reason for reason in reasons if reason != "marketplace_only_no_marketplace_route"))
    return reasons or ("no_valid_route",)


def _tuple(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _mapping(value: object) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _assert_no_live_payment_fields(payload: Mapping[str, Any]) -> None:
    for key, value in _walk_mapping(payload):
        if key in _UNSAFE_PAYMENT_PAYLOAD_KEYS:
            raise ValueError(
                f"Compute Market production planning rejects live payment field {key!r}; "
                "payment and settlement planning is dry-run only."
            )
        if key == "dry_run" and value is False:
            raise ValueError("Compute Market production planning requires dry_run=true.")
        if key == "dry_run_required" and value is False:
            raise ValueError("Compute Market production planning requires dry_run_required=true.")


def _walk_mapping(value: object) -> tuple[tuple[str, object], ...]:
    if isinstance(value, Mapping):
        pairs: list[tuple[str, object]] = []
        for key, child in value.items():
            pairs.append((str(key), child))
            pairs.extend(_walk_mapping(child))
        return tuple(pairs)
    if isinstance(value, (tuple, list)):
        pairs = []
        for child in value:
            pairs.extend(_walk_mapping(child))
        return tuple(pairs)
    return ()


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, str)):
        return float(value)
    raise TypeError(f"Expected numeric value, got {type(value).__name__}")


def _infer_task_type(task: str) -> str:
    lowered = task.lower()
    if "gpu" in lowered or "batch" in lowered:
        return "batch_gpu_inference"
    if "token" in lowered or "llm" in lowered or "inference" in lowered:
        return "token_inference"
    if "tool" in lowered:
        return "tool_call"
    return "generic"


def _intelligence_tier(payload: Mapping[str, Any]) -> str:
    value = str(payload.get("intelligence_tier") or payload.get("tier") or "")
    if value in {item.value for item in IntelligenceTier}:
        return value
    task = str(payload.get("task") or payload.get("task_description") or "").lower()
    if bool(payload.get("allow_background", False)):
        return IntelligenceTier.BACKGROUND_AGENT.value
    if bool(payload.get("allow_reserved_capacity", False)):
        return IntelligenceTier.RESERVED_CAPACITY.value
    if "batch" in task:
        return IntelligenceTier.BATCH.value
    if "deep" in task or "research" in task or "architecture" in task:
        return IntelligenceTier.DEEP_REASONING.value
    return IntelligenceTier.STANDARD.value


def _reasoning_level(payload: Mapping[str, Any]) -> str:
    value = str(payload.get("reasoning_level") or "")
    if value in {item.value for item in ReasoningLevel}:
        return value
    tier = _intelligence_tier(payload)
    if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.BACKGROUND_AGENT.value, IntelligenceTier.PREMIUM.value}:
        return ReasoningLevel.HIGH.value
    if tier == IntelligenceTier.RESERVED_CAPACITY.value:
        return ReasoningLevel.EXTREME.value
    if tier == IntelligenceTier.INSTANT.value:
        return ReasoningLevel.LOW.value
    return ReasoningLevel.MEDIUM.value


def _reasoning_budget(payload: Mapping[str, Any]) -> ReasoningBudget:
    raw = payload.get("reasoning_budget", {})
    source = dict(raw) if isinstance(raw, Mapping) else {}
    tier = _intelligence_tier(payload)
    defaults: dict[str, int] = {
        IntelligenceTier.INSTANT.value: 2,
        IntelligenceTier.STANDARD.value: 8,
        IntelligenceTier.DEEP_REASONING.value: 32,
        IntelligenceTier.BACKGROUND_AGENT.value: 64,
        IntelligenceTier.BATCH.value: 16,
        IntelligenceTier.PREMIUM.value: 48,
        IntelligenceTier.RESERVED_CAPACITY.value: 96,
    }
    steps = int(source.get("max_reasoning_steps", defaults.get(tier, 8)) or defaults.get(tier, 8))
    background_runtime = int(
        source.get(
            "max_background_runtime_seconds",
            payload.get("max_background_runtime_seconds", 3600 if tier == IntelligenceTier.BACKGROUND_AGENT.value else 0),
        )
        or 0
    )
    return ReasoningBudget(
        reasoning_level=str(source.get("reasoning_level") or _reasoning_level(payload)),
        max_reasoning_steps=steps,
        max_parallel_branches=int(source.get("max_parallel_branches", 4 if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.BACKGROUND_AGENT.value, IntelligenceTier.PREMIUM.value} else 1) or 1),
        max_reflection_passes=int(source.get("max_reflection_passes", 3 if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.PREMIUM.value} else 1) or 1),
        max_tool_calls=int(source.get("max_tool_calls", 16 if tier in {IntelligenceTier.DEEP_REASONING.value, IntelligenceTier.BACKGROUND_AGENT.value} else 4) or 4),
        max_wall_time_seconds=int(source.get("max_wall_time_seconds", payload.get("max_wall_time_seconds", 600 if tier != IntelligenceTier.INSTANT.value else 30)) or 60),
        max_background_runtime_seconds=background_runtime,
        checkpoint_interval_seconds=int(source.get("checkpoint_interval_seconds", payload.get("checkpoint_interval_seconds", 300 if background_runtime else 0)) or 0),
    )


def _background_run_policy(payload: Mapping[str, Any]) -> BackgroundRunPolicy:
    raw = payload.get("background_run_policy", {})
    source = dict(raw) if isinstance(raw, Mapping) else {}
    allow_background = bool(source.get("allow_background", payload.get("allow_background", False)))
    return BackgroundRunPolicy(
        allow_background=allow_background,
        background_deadline=str(source.get("background_deadline", payload.get("background_deadline", ""))),
        checkpoint_interval_seconds=int(source.get("checkpoint_interval_seconds", payload.get("checkpoint_interval_seconds", 300 if allow_background else 0)) or 0),
        max_background_runtime_seconds=int(source.get("max_background_runtime_seconds", payload.get("max_background_runtime_seconds", 3600 if allow_background else 0)) or 0),
        defer_policy=str(source.get("defer_policy", payload.get("defer_policy", "run_now"))),
    )


def _task_urgency(payload: Mapping[str, Any]) -> TaskUrgency:
    raw = payload.get("urgency", {})
    source = dict(raw) if isinstance(raw, Mapping) else {}
    return TaskUrgency(
        run_now=bool(source.get("run_now", payload.get("run_now", True))),
        defer_allowed=bool(source.get("defer_allowed", payload.get("defer_allowed", False))),
        deadline=str(source.get("deadline", payload.get("deadline", ""))),
        max_latency_ms=int(source.get("max_latency_ms", payload.get("max_latency_ms", 0)) or 0),
        off_peak_allowed=bool(source.get("off_peak_allowed", payload.get("off_peak_allowed", False))),
    )


def _quality_target(payload: Mapping[str, Any]) -> QualityTarget:
    raw = payload.get("quality_target", {})
    if isinstance(raw, Mapping):
        target = str(raw.get("target", payload.get("quality_requirement", "standard")))
        min_confidence = float(raw.get("min_confidence", 0.0) or 0.0)
        require_audit = bool(raw.get("require_audit_trail", True))
        require_verified = bool(raw.get("require_verified_provider", payload.get("require_verified_provider", False)))
    else:
        target = str(raw or payload.get("quality_requirement", "standard"))
        min_confidence = 0.0
        require_audit = True
        require_verified = bool(payload.get("require_verified_provider", False))
    return QualityTarget(target=target, min_confidence=min_confidence, require_audit_trail=require_audit, require_verified_provider=require_verified)


def _decision_id(profile: TaskEconomicProfile, policy: ComputeMarketPolicy, quotes: tuple[ComputeQuote, ...], request_id: str, idempotency_key: str) -> str:
    stable = {
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "task_hash": profile.task_hash,
        "policy_hash": content_hash(policy.as_record()),
        "quotes": tuple((quote.quote_id, quote.status, quote.estimated_total_cost) for quote in quotes),
    }
    return f"decision_{content_hash(stable)[:24]}"


def _tie_breakers(strategy: str) -> tuple[str, ...]:
    if strategy == SelectionStrategy.LOWEST_COST.value:
        return ("estimated_total_cost", "estimated_latency_ms", "confidence")
    if strategy == SelectionStrategy.BEST_LATENCY.value:
        return ("estimated_latency_ms", "estimated_total_cost")
    if strategy == SelectionStrategy.BEST_ROI.value:
        return ("task_roi", "estimated_total_cost", "confidence")
    if strategy == SelectionStrategy.MARKETPLACE_PREFERRED.value:
        return ("marketplace_route", "estimated_total_cost", "estimated_latency_ms")
    if strategy == SelectionStrategy.CAPACITY_GUARANTEED.value:
        return ("capacity_available", "reservation_required", "estimated_total_cost")
    if strategy == SelectionStrategy.RELIABILITY_WEIGHTED.value:
        return ("confidence", "estimated_total_cost", "estimated_latency_ms")
    return ("estimated_total_cost", "estimated_latency_ms", "confidence", "marketplace_route")


def _field(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, Mapping) else None


def _quote_drift(original: object, current: object) -> Mapping[str, object]:
    original_cost = _field(original, "estimated_total_cost")
    current_cost = _field(current, "estimated_total_cost")
    return {
        "estimated_total_cost_before": original_cost,
        "estimated_total_cost_after": current_cost,
        "changed": original_cost != current_cost,
    }


def _provider_drift(original_quotes: object, current_quote: object) -> Mapping[str, object]:
    original_statuses = tuple(
        str(item.get("status", "")) for item in original_quotes if isinstance(item, Mapping)
    ) if isinstance(original_quotes, (tuple, list)) else ()
    return {
        "original_statuses": original_statuses,
        "current_status": _field(current_quote, "status"),
        "changed": bool(original_statuses and _field(current_quote, "status") not in original_statuses),
    }
