"""Deterministic compute-market simulation scenarios."""
from __future__ import annotations

from dataclasses import replace

from flow_memory.compute_market.models import ComputeRoute
from flow_memory.compute_market.registry import default_compute_routes

SIMULATION_SCENARIOS: tuple[str, ...] = (
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
)


def simulated_routes(scenario: str = "provider_quote_available") -> tuple[ComputeRoute, ...]:
    routes = default_compute_routes()
    if scenario in {"marketplace_route_available", "marketplace_only_success"}:
        return tuple(route for route in routes if route.market_type == "marketplace") + tuple(
            route for route in routes if route.market_type != "marketplace"
        )
    if scenario in {"marketplace_route_unavailable", "marketplace_only_fail_closed"}:
        return tuple(
            replace(route, capacity_available=False) if route.market_type == "marketplace" else route
            for route in routes
        )
    if scenario == "reserved_capacity_available":
        return tuple(
            replace(route, capacity_available=True) if route.market_type == "reserved_capacity" else route
            for route in routes
        )
    if scenario == "reserved_capacity_exhausted":
        return tuple(
            replace(route, capacity_available=False) if route.market_type == "reserved_capacity" else route
            for route in routes
        )
    if scenario == "provider_outage":
        return tuple(
            replace(route, capacity_available=False) if route.provider_type in {"direct", "fallback"} else route
            for route in routes
        )
    if scenario == "budget_exceeded":
        return tuple(replace(route, unit_price=(route.unit_price or 0.0) * 1000.0) for route in routes)
    if scenario in {"unknown_price_fail_closed", "unknown_price_allowed", "provider_quote_unavailable"}:
        return tuple(
            replace(route, unit_price=None) if route.market_type == "marketplace" else route
            for route in routes
        )
    if scenario == "no_valid_routes":
        return tuple(replace(route, unit_price=None, capacity_available=False) for route in routes)
    if scenario in {"multiple_valid_routes", "best_roi_route_selected", "lowest_cost_route_selected", "best_latency_route_selected"}:
        return routes
    if scenario == "dry_run_payment_policy_failure":
        return tuple(
            replace(route, dry_run_only=False, settlement_mode="live_broadcast", settlement_modes=("live_broadcast",))
            if route.provider_type == "direct"
            else route
            for route in routes
        )
    return routes


def simulation_catalog() -> tuple[dict[str, object], ...]:
    return tuple({"scenario": scenario, "live_calls": False, "dry_run_only": True} for scenario in SIMULATION_SCENARIOS)
