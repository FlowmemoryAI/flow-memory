"""Quote collection and normalization for heterogeneous compute prices."""
from __future__ import annotations

from typing import Mapping

from flow_memory.compute_market.models import ComputeCapacityWindow, ComputeQuote, ComputeRoute, QuoteStatus, TaskEconomicProfile


def estimate_units(profile: TaskEconomicProfile, unit_type: str) -> float:
    if unit_type in profile.estimated_units:
        return max(0.0, float(profile.estimated_units[unit_type]))
    defaults: Mapping[str, float] = {
        "token": 12_000.0,
        "request": 1.0,
        "gpu_second": 120.0,
        "gpu_minute": 2.0,
        "gpu_hour": 1.0 / 30.0,
        "cpu_second": 30.0,
        "memory_gb_hour": 0.25,
        "storage_gb_month": 0.01,
        "bandwidth_gb": 0.01,
        "agent_step": 8.0,
        "tool_call": 2.0,
        "inference_job": 1.0,
        "batch_job": 1.0,
        "reserved_capacity_slot": 1.0,
    }
    multiplier = 2.0 if "batch" in profile.task_description.lower() else 1.0
    return defaults.get(unit_type, 1.0) * multiplier


def collect_quote(route: ComputeRoute, profile: TaskEconomicProfile, *, scenario: str = "provider_quote_available") -> ComputeQuote:
    estimated_units = route.estimated_units or estimate_units(profile, route.unit_type)
    unit_price = route.unit_price
    estimated_total = None if unit_price is None else round(max(0.0, estimated_units) * max(0.0, unit_price), 8)
    capacity_available = route.capacity_available
    expired = False
    stale = False
    assumptions = ["deterministic local quote simulation", f"scenario={scenario}"]
    confidence = route.confidence
    if scenario == "provider_quote_unavailable" and route.provider_type == "direct":
        unit_price = None
        estimated_total = None
        confidence = 0.25
        assumptions.append("provider quote unavailable; price unknown")
    elif scenario == "marketplace_route_unavailable" and route.market_type == "marketplace":
        capacity_available = False
        assumptions.append("marketplace capacity unavailable")
    elif scenario == "reserved_capacity_exhausted" and route.market_type == "reserved_capacity":
        capacity_available = False
        assumptions.append("reserved capacity exhausted")
    elif scenario == "quote_expired":
        expired = True
        assumptions.append("quote marked expired")
    elif scenario == "stale_pricing":
        stale = True
        confidence = min(confidence, 0.4)
        assumptions.append("pricing is stale")
    elif scenario == "provider_outage" and route.provider_type in {"direct", "fallback"}:
        capacity_available = False
        confidence = 0.1
        assumptions.append("provider outage")
    elif scenario == "unknown_price_allowed" and route.market_type == "marketplace":
        unit_price = None
        estimated_total = None
        confidence = 0.35
        assumptions.append("unknown price permitted only by permissive policy")
    task_roi = task_roi_from_cost(profile.estimated_value, estimated_total)
    capacity_window = route.capacity_window or ComputeCapacityWindow(
        window_id=f"window-{route.route_id}",
        capacity_available=capacity_available,
        capacity_units=estimated_units,
        provider_id=route.provider_id,
        route_id=route.route_id,
    )
    status = QuoteStatus.VALID.value
    if expired:
        status = QuoteStatus.EXPIRED.value
    elif stale:
        status = QuoteStatus.STALE.value
    elif unit_price is None or estimated_total is None:
        status = QuoteStatus.UNKNOWN_PRICE.value
    elif not capacity_available:
        status = QuoteStatus.CAPACITY_UNAVAILABLE.value
    return ComputeQuote(
        quote_id=f"quote-{route.route_id}",
        provider_id=route.provider_id,
        provider_or_route=route.provider_or_route,
        provider_type=route.provider_type,
        route_id=route.route_id,
        market_type=route.market_type,
        network=route.network,
        payment_asset=route.payment_asset,
        unit_type=route.unit_type,
        unit_price=unit_price,
        estimated_units=estimated_units,
        estimated_total_cost=estimated_total,
        estimated_latency_ms=route.estimated_latency_ms,
        capacity_available=capacity_available,
        reservation_required=route.reservation_required,
        settlement_mode=route.settlement_mode,
        settlement_options=route.settlement_modes,
        dry_run_only=route.dry_run_only,
        task_roi=task_roi,
        confidence=confidence,
        quote_ttl_seconds=route.quote_ttl_seconds,
        expired=expired,
        stale=stale,
        assumptions=tuple(assumptions),
        capacity_window=capacity_window,
        original_quote={"route": route.as_record(), "pricing_model": route.price_curve.as_record() if route.price_curve else {}},
        comparability_warnings=comparability_warnings(route.unit_type),
        status=status,
        expires_at="9999-12-31T23:59:59Z" if not expired else "2026-05-24T00:00:00Z",
    )


def collect_quotes(routes: tuple[ComputeRoute, ...], profile: TaskEconomicProfile, *, scenario: str = "provider_quote_available") -> tuple[ComputeQuote, ...]:
    return tuple(collect_quote(route, profile, scenario=scenario) for route in routes)


def normalize_quote(quote: ComputeQuote) -> ComputeQuote:
    if quote.unit_type == "token":
        warning = "token quote normalized to task-level cost; token count remains original unit"
    elif quote.unit_type.startswith("gpu_"):
        warning = "GPU-time quote normalized to task-level cost; wall-clock assumptions remain estimated"
    elif quote.unit_type == "reserved_capacity_slot":
        warning = "reserved capacity quote normalized as slot cost; unused capacity is not credited"
    else:
        warning = "quote normalized to task-level cost"
    warnings = tuple(dict.fromkeys((*quote.comparability_warnings, warning)))
    return ComputeQuote(**{**quote.as_record(), "comparability_warnings": warnings})


def normalize_quotes(quotes: tuple[ComputeQuote, ...]) -> tuple[ComputeQuote, ...]:
    return tuple(normalize_quote(quote) for quote in quotes)


def task_roi_from_cost(estimated_value: float | None, estimated_total_cost: float | None) -> float:
    if estimated_value is None:
        return 0.0
    if estimated_total_cost is None:
        return 0.0
    if estimated_total_cost == 0:
        return float(estimated_value)
    return round((float(estimated_value) - estimated_total_cost) / estimated_total_cost, 6)


def comparability_warnings(unit_type: str) -> tuple[str, ...]:
    if unit_type not in {"token", "request"}:
        return ("non-token unit; compare using normalized total cost and confidence",)
    return ()
