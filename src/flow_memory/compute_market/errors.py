"""Structured Flow Memory Compute Market error taxonomy."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.compute_market.models import ComputeMarketError, ErrorCategory

_ERROR_CATEGORY_BY_REASON: Mapping[str, str] = {
    "request.invalid": ErrorCategory.VALIDATION_ERROR.value,
    "auth.invalid": ErrorCategory.AUTH_ERROR.value,
    "auth.forbidden": ErrorCategory.SCOPE_ERROR.value,
    "rate_limit.exceeded": ErrorCategory.RATE_LIMITED.value,
    "circuit_open": ErrorCategory.CIRCUIT_OPEN.value,
    "provider_temporarily_disabled": ErrorCategory.PROVIDER_UNAVAILABLE.value,
    "marketplace_only_no_marketplace_route": ErrorCategory.MARKETPLACE_REQUIRED.value,
    "fallback_required_but_not_allowed": ErrorCategory.FALLBACK_DISALLOWED.value,
    "dry_run_required_live_broadcast_route": ErrorCategory.SETTLEMENT_DISALLOWED.value,
    "dry_run_required_live_quote": ErrorCategory.SETTLEMENT_DISALLOWED.value,
    "unknown_price_fail_closed": ErrorCategory.UNKNOWN_PRICE.value,
    "quote_expired": ErrorCategory.QUOTE_EXPIRED.value,
    "stale_quote": ErrorCategory.QUOTE_STALE.value,
    "budget_exceeded": ErrorCategory.BUDGET_EXCEEDED.value,
    "unit_price_exceeded": ErrorCategory.BUDGET_EXCEEDED.value,
    "required_capacity_unavailable": ErrorCategory.CAPACITY_UNAVAILABLE.value,
    "latency_exceeded": ErrorCategory.POLICY_DENIED.value,
    "settlement_mode_denied": ErrorCategory.SETTLEMENT_DISALLOWED.value,
    "roi_requirement_failed": ErrorCategory.ROI_NEGATIVE.value,
    "human_approval_required_not_granted": ErrorCategory.POLICY_DENIED.value,
    "audit_required_failed": ErrorCategory.AUDIT_REQUIRED_FAILED.value,
    "unsafe_payload": ErrorCategory.UNSAFE_PAYLOAD.value,
    "no_valid_route": ErrorCategory.NO_VALID_ROUTE.value,
    "provider_timeout": ErrorCategory.PROVIDER_TIMEOUT.value,
    "provider_error": ErrorCategory.PROVIDER_ERROR.value,
    "provider_unavailable": ErrorCategory.PROVIDER_UNAVAILABLE.value,
    "storage_error": ErrorCategory.STORAGE_ERROR.value,
    "configuration_error": ErrorCategory.CONFIGURATION_ERROR.value,
}

_NEXT_ACTION_BY_CATEGORY: Mapping[str, tuple[str, ...]] = {
    ErrorCategory.POLICY_DENIED.value: ("inspect policy_trace and retry with an explicit safer policy",),
    ErrorCategory.NO_VALID_ROUTE.value: ("wait for provider capacity or relax policy without weakening safety gates",),
    ErrorCategory.PROVIDER_TIMEOUT.value: ("retry after provider backoff or disable the unhealthy provider",),
    ErrorCategory.PROVIDER_ERROR.value: ("inspect provider health and preserve the failed raw quote for audit",),
    ErrorCategory.QUOTE_EXPIRED.value: ("refresh quotes before planning",),
    ErrorCategory.QUOTE_STALE.value: ("refresh quotes or explicitly allow stale quotes in policy",),
    ErrorCategory.UNKNOWN_PRICE.value: ("require a priced quote or explicitly allow unknown prices for dry-run planning",),
    ErrorCategory.SETTLEMENT_DISALLOWED.value: ("keep dry-run mode enabled unless live settlement gates are approved",),
    ErrorCategory.UNSAFE_PAYLOAD.value: ("remove private-key, mnemonic, broadcast, transfer, withdraw, or deposit fields",),
    ErrorCategory.AUDIT_REQUIRED_FAILED.value: ("restore durable audit logging before retrying",),
    ErrorCategory.CONFIGURATION_ERROR.value: ("fix compute market configuration and restart",),
    ErrorCategory.CIRCUIT_OPEN.value: ("wait for the provider circuit to half-open or use another provider",),
}


def compute_error(
    error_code: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
    request_id: str = "",
    retryable: bool = False,
    rejected_reasons: tuple[str, ...] = (),
) -> ComputeMarketError:
    category = category_for_code(error_code, rejected_reasons)
    return ComputeMarketError(
        error_code=error_code,
        error_category=category,
        message=message,
        details=details or {},
        request_id=request_id,
        retryable=retryable,
        rejected_reasons=rejected_reasons,
        next_safe_actions=_NEXT_ACTION_BY_CATEGORY.get(category, ("review request and retry only after correcting the error",)),
    )


def category_for_code(error_code: str, rejected_reasons: tuple[str, ...] = ()) -> str:
    if error_code in _ERROR_CATEGORY_BY_REASON:
        return _ERROR_CATEGORY_BY_REASON[error_code]
    for reason in rejected_reasons:
        category = _ERROR_CATEGORY_BY_REASON.get(reason)
        if category:
            return category
    if error_code.startswith("provider.timeout"):
        return ErrorCategory.PROVIDER_TIMEOUT.value
    if error_code.startswith("provider."):
        return ErrorCategory.PROVIDER_ERROR.value
    if error_code.startswith("policy."):
        return ErrorCategory.POLICY_DENIED.value
    if error_code.startswith("storage."):
        return ErrorCategory.STORAGE_ERROR.value
    return ErrorCategory.INTERNAL_ERROR.value


def policy_denial_error(request_id: str, rejected_reasons: tuple[str, ...]) -> ComputeMarketError:
    code = rejected_reasons[0] if rejected_reasons else "no_valid_route"
    return compute_error(
        code,
        "Compute Market policy denied every route; planning failed closed.",
        request_id=request_id,
        rejected_reasons=rejected_reasons,
    )
