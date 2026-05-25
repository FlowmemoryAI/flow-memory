"""Budget and compute-market policy enforcement."""
from __future__ import annotations

from typing import Mapping

from flow_memory.compute_market.models import AgentBudgetPolicy, ComputeMarketPolicy, ComputeQuote, ComputeRoute, PolicyTrace, TaskEconomicProfile

POLICY_REASON_EXPLANATIONS: dict[str, str] = {
    "marketplace_only_no_marketplace_route": "Marketplace-only policy requires a marketplace route, but this route is not marketplace-native or marketplace capacity is unavailable.",
    "fallback_required_but_not_allowed": "The route is a fallback route and fallback is disallowed by compute market policy.",
    "dry_run_required_live_broadcast_route": "Dry-run policy is required, but the route advertises a live broadcast path.",
    "dry_run_required_live_quote": "Dry-run policy is required, but the quote is not marked dry-run-only.",
    "unknown_price_fail_closed": "The route price is unknown and policy does not allow unknown-price planning.",
    "quote_expired": "The quote is expired and stale or expired quotes are disallowed.",
    "stale_quote": "The quote uses stale pricing and stale quotes are disallowed.",
    "budget_exceeded": "The estimated total cost exceeds the agent budget policy.",
    "unit_price_exceeded": "The quoted unit price exceeds the maximum unit price policy.",
    "unsupported_asset": "The quote payment asset is not in the allowed asset set.",
    "unsupported_network": "The quote network is not in the allowed network set.",
    "provider_not_allowed": "The provider is not in the explicitly allowed provider set.",
    "provider_denied": "The provider is explicitly denied by budget policy.",
    "required_capacity_unavailable": "Capacity confirmation is required and this route does not have available capacity.",
    "latency_exceeded": "The route latency exceeds the maximum latency policy.",
    "settlement_mode_denied": "The route settlement mode is not allowed by policy.",
    "roi_requirement_failed": "Positive ROI is required and the task ROI estimate is not positive.",
    "human_approval_required_not_granted": "The estimated cost is above the human-approval threshold and no approval flag was provided.",
    "provider_disabled": "The provider or route is disabled and cannot be selected.",
    "provider_timeout": "The provider did not return a quote within the bounded timeout.",
    "provider_error": "The provider returned an error or could not be queried safely.",
    "invalid_provider_response": "The provider quote response failed validation.",
    "unsupported_task": "The provider does not support this task type or unit type.",
    "verified_provider_required": "Policy requires verified providers and this route is not verified.",
    "signed_quote_required": "Policy requires a signed quote and this quote is unsigned or unverifiable.",
    "budget_period_exceeded": "The request would exceed a configured period budget.",
}

_CHECKS: tuple[str, ...] = (
    "provider_enabled",
    "marketplace_only",
    "fallback_allowed",
    "dry_run_required",
    "known_price",
    "fresh_quote",
    "budget",
    "unit_price",
    "allowed_asset",
    "allowed_network",
    "allowed_provider",
    "denied_provider",
    "capacity",
    "latency",
    "settlement_mode",
    "roi",
    "human_approval",
    "verified_provider",
    "signed_quote",
)


def evaluate_quote(
    quote: ComputeQuote,
    route: ComputeRoute,
    profile: TaskEconomicProfile,
    budget_policy: AgentBudgetPolicy,
    market_policy: ComputeMarketPolicy,
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    rejected: list[str] = []
    warnings: list[str] = []
    if not route.enabled or quote.status == "disabled_provider":
        rejected.append("provider_disabled")
    if quote.status == "provider_timeout":
        rejected.append("provider_timeout")
    if quote.status == "provider_error":
        rejected.append("provider_error")
    if quote.status == "invalid_response":
        rejected.append("invalid_provider_response")
    if quote.status == "unsupported_task":
        rejected.append("unsupported_task")
    if market_policy.marketplace_only and route.market_type != "marketplace":
        rejected.append("marketplace_only_no_marketplace_route")
    if route.fallback_route and not (budget_policy.fallback_allowed and market_policy.fallback_allowed):
        rejected.append("fallback_required_but_not_allowed")
    if market_policy.dry_run_required and not route.dry_run_only:
        rejected.append("dry_run_required_live_broadcast_route")
    if (budget_policy.dry_run_required or market_policy.dry_run_required) and not quote.dry_run_only:
        rejected.append("dry_run_required_live_quote")
    unknown_price = quote.unit_price is None or quote.estimated_total_cost is None or quote.status == "unknown_price"
    if unknown_price and not (budget_policy.allow_unknown_price or market_policy.allow_unknown_price):
        rejected.append("unknown_price_fail_closed")
    if (quote.expired or quote.status == "expired") and not (budget_policy.allow_stale_quote or market_policy.allow_stale_quote):
        rejected.append("quote_expired")
    if (quote.stale or quote.status == "stale") and not (budget_policy.allow_stale_quote or market_policy.allow_stale_quote):
        rejected.append("stale_quote")
    if budget_policy.max_total_cost and quote.estimated_total_cost is not None:
        if quote.estimated_total_cost > budget_policy.max_total_cost:
            rejected.append("budget_exceeded")
    if market_policy.per_agent_daily_budget and quote.estimated_total_cost is not None:
        if quote.estimated_total_cost > market_policy.per_agent_daily_budget:
            rejected.append("budget_period_exceeded")
    if budget_policy.max_unit_price and quote.unit_price is not None and quote.unit_price > budget_policy.max_unit_price:
        rejected.append("unit_price_exceeded")
    if budget_policy.allowed_assets and quote.payment_asset not in budget_policy.allowed_assets:
        rejected.append("unsupported_asset")
    if budget_policy.allowed_networks and quote.network not in budget_policy.allowed_networks:
        rejected.append("unsupported_network")
    if budget_policy.allowed_providers and quote.provider_id not in budget_policy.allowed_providers:
        rejected.append("provider_not_allowed")
    if quote.provider_id in budget_policy.denied_providers:
        rejected.append("provider_denied")
    if (market_policy.require_capacity_confirmation or budget_policy.require_capacity_confirmation or route.reservation_required) and not quote.capacity_available:
        rejected.append("required_capacity_unavailable")
    if budget_policy.max_latency_ms and quote.estimated_latency_ms > budget_policy.max_latency_ms:
        rejected.append("latency_exceeded")
    if market_policy.max_latency_ms and quote.estimated_latency_ms > market_policy.max_latency_ms:
        rejected.append("latency_exceeded")
    if not _settlement_allowed(quote, budget_policy, market_policy):
        rejected.append("settlement_mode_denied")
    if budget_policy.require_roi_positive and quote.task_roi <= 0.0:
        rejected.append("roi_requirement_failed")
    human_threshold = budget_policy.require_human_approval_above or market_policy.require_human_approval_above
    if human_threshold and quote.estimated_total_cost is not None and quote.estimated_total_cost > human_threshold:
        warnings.append("human_approval_required_above_threshold")
        if not budget_policy.human_approval_granted:
            rejected.append("human_approval_required_not_granted")
        else:
            warnings.append("human_approval_threshold_satisfied")
    if (budget_policy.require_verified_provider or market_policy.require_verified_provider or route.verified_provider_required) and not bool(route.metadata.get("provider_verified", False)):
        rejected.append("verified_provider_required")
    if (budget_policy.require_signed_quote or market_policy.require_signed_quote) and not quote.signed_quote_valid:
        rejected.append("signed_quote_required")
    if budget_policy.quote_ttl_seconds and quote.quote_ttl_seconds > budget_policy.quote_ttl_seconds:
        warnings.append("quote_ttl_exceeds_policy_window")
    if profile.latency_requirement_ms and quote.estimated_latency_ms > profile.latency_requirement_ms:
        warnings.append("task_latency_requirement_missed")
    return (not rejected, tuple(dict.fromkeys(rejected)), tuple(dict.fromkeys(warnings)))


def build_policy_trace(
    market_policy: ComputeMarketPolicy,
    rejected_reasons: Mapping[str, tuple[str, ...]],
    warnings: tuple[str, ...] = (),
) -> PolicyTrace:
    failed = tuple(dict.fromkeys(reason for values in rejected_reasons.values() for reason in values))
    failed_checks = tuple(_check_for_reason(reason) for reason in failed)
    passed_checks = tuple(check for check in _CHECKS if check not in failed_checks)
    return PolicyTrace(
        policy_id=market_policy.policy_id,
        policy_version=market_policy.policy_version,
        checks_run=_CHECKS,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        rejected_reasons=explain_rejections(failed),
        warnings=warnings,
        final_result="fail_closed" if failed else "accepted",
    )


def explain_rejections(reasons: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "reason": reason,
            "explanation": POLICY_REASON_EXPLANATIONS.get(reason, "The route violates compute market policy."),
        }
        for reason in reasons
    )


def _settlement_allowed(quote: ComputeQuote, budget_policy: AgentBudgetPolicy, market_policy: ComputeMarketPolicy) -> bool:
    allowed = budget_policy.settlement_modes_allowed or market_policy.settlement_modes_allowed
    if not allowed:
        return True
    return any(option in allowed for option in quote.settlement_options) or quote.settlement_mode in allowed


def _check_for_reason(reason: str) -> str:
    if reason in {"provider_disabled", "provider_timeout", "provider_error", "invalid_provider_response"}:
        return "provider_enabled"
    if reason == "marketplace_only_no_marketplace_route":
        return "marketplace_only"
    if reason == "fallback_required_but_not_allowed":
        return "fallback_allowed"
    if reason.startswith("dry_run_required"):
        return "dry_run_required"
    if reason == "unknown_price_fail_closed":
        return "known_price"
    if reason in {"quote_expired", "stale_quote"}:
        return "fresh_quote"
    if reason in {"budget_exceeded", "budget_period_exceeded"}:
        return "budget"
    if reason == "unit_price_exceeded":
        return "unit_price"
    if reason == "unsupported_asset":
        return "allowed_asset"
    if reason == "unsupported_network":
        return "allowed_network"
    if reason == "provider_not_allowed":
        return "allowed_provider"
    if reason == "provider_denied":
        return "denied_provider"
    if reason == "required_capacity_unavailable":
        return "capacity"
    if reason == "latency_exceeded":
        return "latency"
    if reason == "settlement_mode_denied":
        return "settlement_mode"
    if reason == "roi_requirement_failed":
        return "roi"
    if reason == "human_approval_required_not_granted":
        return "human_approval"
    if reason == "verified_provider_required":
        return "verified_provider"
    if reason == "signed_quote_required":
        return "signed_quote"
    return "policy"
