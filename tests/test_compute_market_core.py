import pytest
from typing import Any, Mapping

from flow_memory.compute_market import (
    SUPPORTED_UNIT_TYPES,
    AgentBudgetPolicy,
    ComputeMarketPolicy,
    PaymentPlan,
    SettlementIntent,
    TaskEconomicProfile,
    build_compute_plan,
    build_payment_plan,
    collect_quotes,
    default_compute_routes,
    economic_memory_schema,
    metadata_registry,
    normalize_quotes,
    query_memory,
    SIMULATION_SCENARIOS,
)
from flow_memory.compute_market.models import (
    ComputeCapacityWindow,
    ComputeIntent,
    ComputeProvider,
    ComputeQuote,
    ComputeReservation,
    ComputeRoute,
    EconomicMemoryRecord,
    PaymentIntent,
    PriceCurve,
    ProviderCapability,
    RouteDecision,
    UnitPriceSnapshot,
)
from flow_memory.compute_market.planner import build_task_profile


def test_supported_unit_types_cover_compute_capacity_not_just_tokens() -> None:
    for unit_type in (
        "token",
        "request",
        "gpu_second",
        "gpu_minute",
        "gpu_hour",
        "cpu_second",
        "memory_gb_hour",
        "storage_gb_month",
        "bandwidth_gb",
        "agent_step",
        "tool_call",
        "inference_job",
        "batch_job",
        "reserved_capacity_slot",
    ):
        assert unit_type in SUPPORTED_UNIT_TYPES


def test_compute_domain_models_serialize() -> None:
    capability = ProviderCapability("cap", unit_types=("token",), networks=("local",), payment_assets=("CREDITS",))
    provider = ComputeProvider("provider", "Provider", "local", "local", "local", "CREDITS", (capability,))
    price = UnitPriceSnapshot("token", 0.1, "CREDITS", "local", provider_id="provider", route_id="route")
    curve = PriceCurve("unit", (price,))
    window = ComputeCapacityWindow("window", capacity_available=True, provider_id="provider", route_id="route")
    route = ComputeRoute("route", "provider", "Local", "local", "local", "local", "CREDITS", "token", price_curve=curve, capacity_window=window)
    reservation = ComputeReservation("reservation", "provider", "route", window)
    quote = ComputeQuote("quote", "provider", "Local", "local", "route", "local", "local", "CREDITS", "token", 0.1, 10, 1.0)
    compute_intent = ComputeIntent("intent", "task", "agent", "goal", "route", "provider", "token", 10, 1.0)
    payment_intent = PaymentIntent("payment", "generic", "local", "CREDITS", 1.0)
    payment_plan = PaymentPlan("plan", "generic", (payment_intent,), 1.0, "CREDITS", "local")
    settlement = SettlementIntent("settlement", "route", "provider", "plan", "generic_dry_run", 1.0, "CREDITS", "local")
    profile = TaskEconomicProfile("task", "do work", agent_id="agent", goal_id="goal")
    agent_policy = AgentBudgetPolicy(max_total_cost=2.0)
    market_policy = ComputeMarketPolicy()
    decision = RouteDecision(route.as_record(), quote.as_record(), (route.as_record(),), (), {}, "accepted")
    memory = EconomicMemoryRecord(
        "task",
        "agent",
        "goal",
        "Local",
        "local",
        False,
        {"token": 0.1},
        "token",
        10,
        None,
        1.0,
        None,
        1,
        None,
        1.0,
        "estimated",
        False,
        "",
        (),
        agent_policy.as_record() | market_policy.as_record(),
        quote.as_record(),
        "settlement",
        True,
        "selected",
    )
    for item in (capability, provider, price, curve, window, route, reservation, quote, compute_intent, payment_intent, payment_plan, settlement, profile, agent_policy, market_policy, decision, memory):
        assert item.as_record()


def test_compute_plan_success_includes_required_sections() -> None:
    plan = build_compute_plan({"task": "run agent batch inference", "estimated_value": 5.0, "policy": {"max_total_cost": 10.0}})
    record = plan.as_record()

    assert record["ok"] is True
    assert record["selected_route"]
    assert record["normalized_quote"]
    assert "payment_plan" in record
    assert record["payment_plan"]["dry_run_only"] is True
    assert record["settlement_intent"]["dry_run_only"] is True
    assert record["settlement_intent"]["broadcast_allowed"] is False
    assert record["settlement_intent"]["private_key_required"] is False
    assert record["settlement_intent"]["funds_moved"] is False
    assert record["economic_memory_preview"]["unit_prices"]
    assert record["economic_memory_preview"]["rejected_routes"] is not None
    assert "selected_by_" in record["economic_memory_preview"]["selected_reason"]


def test_policy_fail_closed_cases() -> None:
    cases: tuple[tuple[Mapping[str, Any], str], ...] = (
        ({"marketplace_only": True, "scenario": "marketplace_route_unavailable", "policy": {"marketplace_only": True, "require_capacity_confirmation": True}}, "required_capacity_unavailable"),
        ({"policy": {"marketplace_only": True, "allowed_networks": ("offchain",)}}, "marketplace_only_no_marketplace_route"),
        ({"policy": {"marketplace_only": True, "fallback_allowed": False, "allowed_assets": ("USD",)}}, "marketplace_only_no_marketplace_route"),
        ({"policy": {"max_total_cost": 0.000001, "allowed_assets": ("USDC",)}}, "budget_exceeded"),
        ({"policy": {"allowed_assets": ("EUR",)}}, "unsupported_asset"),
        ({"policy": {"allowed_networks": ("mars",)}}, "unsupported_network"),
        ({"scenario": "quote_expired"}, "quote_expired"),
        ({"scenario": "unknown_price_fail_closed", "policy": {"marketplace_only": True}}, "unknown_price_fail_closed"),
        ({"scenario": "dry_run_payment_policy_failure", "policy": {"allowed_providers": ("direct-request-provider",)}}, "dry_run_required_live_broadcast_route"),
        ({"policy": {"denied_providers": ("market-token-provider", "direct-request-provider", "gpu-time-provider", "reserved-capacity-provider", "local-provider", "fallback-provider")}}, "provider_denied"),
        ({"estimated_value": 0.001, "policy": {"require_roi_positive": True, "allowed_assets": ("USD",)}}, "roi_requirement_failed"),
        ({"policy": {"settlement_modes_allowed": ("wire_transfer",)}}, "settlement_mode_denied"),
        ({"scenario": "stale_pricing"}, "stale_quote"),
        ({"policy": {"allowed_providers": ("direct-request-provider",), "require_human_approval_above": 0.000001}}, "human_approval_required_not_granted"),
    )
    for payload, reason in cases:
        plan = build_compute_plan({"task": "policy test", **payload}).as_record()
        all_reasons = tuple(reason for values in plan["rejected_reasons"].values() for reason in values)

        assert plan["ok"] is False
        assert reason in all_reasons or reason in plan["fail_closed_errors"]
        assert plan["rejected_explanations"]


def test_unknown_price_can_be_allowed_by_policy() -> None:
    plan = build_compute_plan(
        {
            "task": "unknown price allowed",
            "scenario": "unknown_price_allowed",
            "policy": {"allow_unknown_price": True, "marketplace_only": True},
        }
    )

    assert plan.ok is True
    assert plan.normalized_quote is not None
    assert plan.normalized_quote["unit_price"] is None


def test_route_selection_strategies() -> None:
    expected = {
        "lowest_cost": "local-no-payment-route",
        "best_latency": "fallback-token-route",
        "best_roi": "market-token-route",
        "marketplace_preferred": "market-token-route",
        "capacity_guaranteed": "local-no-payment-route",
        "reliability_weighted": "local-no-payment-route",
        "balanced": "local-no-payment-route",
    }
    for strategy, route_id in expected.items():
        plan = build_compute_plan({"task": "route selection", "estimated_value": 5.0, "selection_strategy": strategy})
        assert plan.selected_route is not None
        assert plan.selected_route["route_id"] == route_id


def test_no_valid_route_reports_fail_closed() -> None:
    plan = build_compute_plan({"policy": {"allowed_assets": ("NOTREAL",)}})

    assert plan.ok is False
    assert plan.selected_route is None
    assert plan.fail_closed_errors


def test_payment_planning_rails_are_dry_run_only() -> None:
    profile = build_task_profile({"task": "payment rails"})
    quotes = normalize_quotes(collect_quotes(default_compute_routes(), profile))
    rails = {build_payment_plan(quote).selected_rail: build_payment_plan(quote) for quote in quotes}

    assert "http_402" in rails
    assert "solana_usdc" in rails
    assert "generic" in rails
    assert "no_payment" in rails
    base_quote = ComputeQuote("base", "p", "Base", "direct", "r", "direct", "base-sepolia", "ETH", "request", 0.1, 1, 0.1, settlement_mode="base_sepolia_erc4337_dry_run", settlement_options=("base_sepolia_erc4337_dry_run",))
    base_plan = build_payment_plan(base_quote)
    assert base_plan.selected_rail == "base_sepolia_erc4337"
    assert rails["solana_usdc"].payment_intents[0].payload["harness"] == "local_solana_testnet"
    assert rails["solana_usdc"].payment_intents[0].payload["funds_moved"] is False
    assert base_plan.payment_intents[0].payload["harness"] == "local_base_sepolia_erc4337"
    assert base_plan.payment_intents[0].payload["simulated_gas_estimate"] > 0
    for plan in (*rails.values(), base_plan):
        for intent in plan.payment_intents:
            assert intent.dry_run_only is True
            assert intent.broadcast_required is False
            assert intent.requires_private_key is False
            assert intent.moves_funds is False
            assert intent.broadcast_allowed is False
            assert intent.private_key_required is False
            assert intent.funds_moved is False


def test_registry_is_generic_asset_metadata() -> None:
    registry = metadata_registry()
    asset_symbols = {asset["asset_symbol"] for asset in registry["assets"]}

    assert {"USDC", "SOL", "ETH", "CREDITS"}.issubset(asset_symbols)
    assert all("asset_mint_or_address" in asset for asset in registry["assets"])


def test_economic_memory_query_answers_feedback_questions() -> None:
    first = build_compute_plan({"task": "cheap route", "selection_strategy": "lowest_cost"}).economic_memory_preview
    second = build_compute_plan({"task": "market route", "selection_strategy": "marketplace_preferred"}).economic_memory_preview
    result = query_memory((first, second), query="which route is cheapest")

    assert result["ok"] is True
    assert result["cheapest_route"]
    assert result["best_roi_route"]
    assert "stale_pricing_detected" in result
    assert "routes_often_fail_policy" in result
    assert "fallback_used_count" in result
    assert "best_latency_adjusted_cost_route" in result
    assert "selected_route_counts" in result
    assert "selected_reason_counts" in result
    assert "provider_reliability" in result


def test_economic_memory_schema_contains_required_fields() -> None:
    fields = economic_memory_schema()
    for field in (
        "task_id",
        "agent_id",
        "goal_id",
        "provider_or_route",
        "provider_type",
        "marketplace_route",
        "unit_prices",
        "unit_type",
        "estimated_units",
        "actual_units",
        "estimated_total_cost",
        "actual_total_cost",
        "estimated_latency_ms",
        "actual_latency_ms",
        "task_roi",
        "fallback_used",
        "fallback_reason",
        "rejected_routes",
        "policy_snapshot",
        "quote_snapshot",
        "settlement_intent_id",
        "dry_run_only",
        "selected_reason",
        "created_at",
    ):
        assert field in fields


def test_simulation_catalog_covers_launch_scenarios() -> None:
    required = {
        "provider_quote_available",
        "provider_quote_unavailable",
        "marketplace_route_available",
        "marketplace_route_unavailable",
        "reserved_capacity_available",
        "reserved_capacity_exhausted",
        "quote_expired",
        "stale_pricing",
        "provider_outage",
        "network_disallowed",
        "asset_disallowed",
        "budget_exceeded",
        "roi_negative",
        "fallback_allowed",
        "fallback_denied",
        "dry_run_payment_success",
        "dry_run_payment_policy_failure",
        "unknown_price_fail_closed",
        "unknown_price_allowed",
        "marketplace_only_success",
        "marketplace_only_fail_closed",
        "no_valid_routes",
        "multiple_valid_routes",
        "best_roi_route_selected",
        "lowest_cost_route_selected",
        "best_latency_route_selected",
    }

    assert required.issubset(set(SIMULATION_SCENARIOS))
    assert build_compute_plan({"scenario": "marketplace_only_success", "policy": {"marketplace_only": True}}).ok is True
    assert build_compute_plan(
        {
            "scenario": "marketplace_only_fail_closed",
            "policy": {"marketplace_only": True, "require_capacity_confirmation": True},
        }
    ).ok is False
    assert build_compute_plan({"scenario": "no_valid_routes"}).ok is False
    best_roi = build_compute_plan(
        {"scenario": "best_roi_route_selected", "selection_strategy": "best_roi", "estimated_value": 5.0}
    ).selected_route
    assert best_roi is not None
    assert best_roi["route_id"] == "market-token-route"
    lowest_cost = build_compute_plan(
        {"scenario": "lowest_cost_route_selected", "selection_strategy": "lowest_cost"}
    ).selected_route
    assert lowest_cost is not None
    assert lowest_cost["route_id"] == "local-no-payment-route"
    best_latency = build_compute_plan(
        {"scenario": "best_latency_route_selected", "selection_strategy": "best_latency"}
    ).selected_route
    assert best_latency is not None
    assert best_latency["route_id"] == "fallback-token-route"


def test_compute_market_rejects_live_payment_inputs() -> None:
    with pytest.raises(ValueError, match="private_key"):
        build_compute_plan({"task": "unsafe", "private_key": "not-accepted"})
    with pytest.raises(ValueError, match="dry_run=true"):
        build_compute_plan({"task": "unsafe", "dry_run": False})
