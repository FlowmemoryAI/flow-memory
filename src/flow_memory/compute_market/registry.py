"""Deterministic local registry for Compute Market public-alpha demos."""
from __future__ import annotations

from flow_memory.compute_market.models import ComputeBudgetPolicy, ComputeProvider, ComputeRoute


def default_providers() -> tuple[ComputeProvider, ...]:
    return (
        ComputeProvider("local-cpu", "Local CPU dry-run", "local", reputation=0.7, trust_posture="local deterministic simulation", supports_reservations=True),
        ComputeProvider("market-sim-small", "Marketplace small route simulator", "marketplace", reputation=0.82, trust_posture="bond/reputation/canary model, simulated locally", supports_reservations=True),
        ComputeProvider("central-fallback-sim", "Central fallback simulator", "centralized", reputation=0.9, trust_posture="centralized fallback metadata only", supports_reservations=False),
    )


def default_routes() -> tuple[ComputeRoute, ...]:
    return (
        ComputeRoute("local-cpu-small", "local-cpu", "local", "small-general", 0.02, 0.04, latency_ms=120, quality_score=0.55, capacity_units=2.0),
        ComputeRoute("market-small", "market-sim-small", "marketplace", "small-general", 0.05, 0.08, latency_ms=180, quality_score=0.68, capacity_units=8.0, fallback_route_id="central-frontier"),
        ComputeRoute("market-quality", "market-sim-small", "marketplace", "quality-general", 0.11, 0.18, latency_ms=260, quality_score=0.82, capacity_units=4.0, fallback_route_id="central-frontier"),
        ComputeRoute("central-frontier", "central-fallback-sim", "centralized", "frontier-general", 0.24, 0.42, latency_ms=90, quality_score=0.94, capacity_units=16.0),
    )


def default_policies() -> tuple[ComputeBudgetPolicy, ...]:
    return (
        ComputeBudgetPolicy(policy_id="cheap-local", max_total_cost=0.01, max_quote=0.01, max_input_price_per_million=0.10, max_output_price_per_million=0.20, strategy="cheapest_eligible", allow_fallback=False),
        ComputeBudgetPolicy(policy_id="marketplace-only", max_total_cost=0.05, max_quote=0.05, max_input_price_per_million=0.15, max_output_price_per_million=0.25, strategy="cheapest_eligible", marketplace_only=True, allow_fallback=False),
        ComputeBudgetPolicy(policy_id="quality-sensitive", max_total_cost=0.15, max_quote=0.15, strategy="highest_quality", allow_fallback=True),
    )
