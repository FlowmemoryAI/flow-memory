"""Squire inference routing helpers.

No network calls are made here. The helpers build drop-in proxy URLs, parse safe
response metadata, and select among provided route candidates under explicit
budget constraints.
"""
from __future__ import annotations

from typing import Mapping

from flow_memory.squire.models import RouteCandidate, SquireRoutingPolicy


def usepod_proxy_base_url(token: str, *, openai_v1: bool = True) -> str:
    if not token.strip():
        raise ValueError("UsePod token is required to build a proxy URL")
    suffix = "/v1" if openai_v1 else ""
    return f"https://api.usepod.ai/proxy/{token.strip()}{suffix}"


def level5_proxy_base_url(token: str) -> str:
    if not token.strip():
        raise ValueError("Level5 API token is required to build a proxy URL")
    return f"https://api.level5.cloud/proxy/{token.strip()}"


def parse_usepod_response_headers(headers: Mapping[str, str]) -> dict[str, object]:
    lowered = {key.lower(): value for key, value in headers.items()}
    balance = _float_or_none(lowered.get("x-balance-remaining", ""))
    route = lowered.get("x-pod-route", "")
    return {
        "balance_remaining": balance,
        "pod_route": route,
        "fallback_used": "central" in route.lower() or "fallback" in route.lower(),
        "provider_class": _provider_class(route),
    }


def choose_route(policy: SquireRoutingPolicy, candidates: tuple[RouteCandidate, ...]) -> RouteCandidate:
    eligible = tuple(candidate for candidate in candidates if candidate.eligible_for(policy))
    if not eligible:
        if policy.marketplace_only:
            raise ValueError("No marketplace route satisfies the routing policy; refusing centralized fallback")
        raise ValueError("No route satisfies the routing policy")
    if policy.quality_sensitive:
        return min(eligible, key=lambda candidate: (-(candidate.quality_score), candidate.score_price, candidate.latency_ms))
    return min(eligible, key=lambda candidate: (candidate.score_price, candidate.latency_ms, -candidate.quality_score))


def default_route_candidates() -> tuple[RouteCandidate, ...]:
    return (
        RouteCandidate("marketplace", "usepod-marketplace-cheapest", "commodity-open-weight", 0.05, 0.15, latency_ms=900, quality_score=0.72),
        RouteCandidate("key_relay", "usepod-key-relay", "frontier-compatible", 0.30, 1.10, latency_ms=700, quality_score=0.84),
        RouteCandidate("centralized", "usepod-centralized-fallback", "fallback-frontier", 0.50, 1.50, latency_ms=650, quality_score=0.88, centralized_fallback=True),
    )


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _provider_class(route: str) -> str:
    normalized = route.lower()
    if "market" in normalized:
        return "marketplace"
    if "relay" in normalized or "byok" in normalized:
        return "key_relay"
    if "central" in normalized or "fallback" in normalized:
        return "centralized"
    return "unknown"
