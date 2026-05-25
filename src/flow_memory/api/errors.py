"""Deterministic API error contract for local/public-alpha seams."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


JsonObject = Mapping[str, Any]


@dataclass(frozen=True)
class ApiError(Exception):
    """Structured API error that can be raised or serialized without framework support."""

    code: str
    message: str
    status: int = 400
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self, *, request_id: str = "") -> dict[str, Any]:
        category = _category_for_code(self.code)
        error: dict[str, Any] = {
            "code": self.code,
            "error_code": self.code,
            "error_category": category,
            "message": self.message,
            "status": self.status,
            "retryable": category in {"provider_timeout", "provider_error", "rate_limited"},
            "next_safe_actions": _next_safe_actions(category),
        }
        if self.details:
            error["details"] = _sorted_record(self.details)
        if request_id:
            error["request_id"] = request_id
        return {"ok": False, "error": error}


def error_response(error: ApiError, *, request_id: str = "") -> dict[str, Any]:
    return error.as_record(request_id=request_id)


def auth_error(message: str, *, code: str = "auth.invalid", details: Mapping[str, Any] | None = None) -> ApiError:
    return ApiError(code=code, message=message, status=401, details=details or {})


def forbidden_error(message: str, *, details: Mapping[str, Any] | None = None) -> ApiError:
    return ApiError(code="auth.forbidden", message=message, status=403, details=details or {})


def rate_limited_error(message: str = "Rate limit exceeded", *, details: Mapping[str, Any] | None = None) -> ApiError:
    return ApiError(code="rate_limit.exceeded", message=message, status=429, details=details or {})


def validation_error(message: str, *, details: Mapping[str, Any] | None = None) -> ApiError:
    return ApiError(code="request.invalid", message=message, status=400, details=details or {})


def _sorted_record(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe(value[key]) for key in sorted(value, key=str)}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sorted_record(value)
    if isinstance(value, tuple):
        return tuple(_json_safe(item) for item in value)
    if isinstance(value, list):
        return tuple(_json_safe(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _category_for_code(code: str) -> str:
    if code.startswith("auth.forbidden"):
        return "scope_error"
    if code.startswith("auth."):
        return "auth_error"
    if code.startswith("rate_limit."):
        return "rate_limited"
    if code.startswith("request."):
        return "validation_error"
    if code.startswith("provider.timeout"):
        return "provider_timeout"
    if code.startswith("provider."):
        return "provider_error"
    if code.startswith("storage."):
        return "storage_error"
    if code.startswith("policy."):
        return "policy_denied"
    return "internal_error" if code.startswith("internal.") else "validation_error"


def _next_safe_actions(category: str) -> tuple[str, ...]:
    actions = {
        "scope_error": ("retry with the required compute scope",),
        "auth_error": ("provide valid API authentication",),
        "rate_limited": ("wait for the rate-limit window before retrying",),
        "validation_error": ("correct the request payload and retry",),
        "policy_denied": ("inspect policy_trace and retry only with an explicit safer policy",),
        "provider_timeout": ("retry after provider backoff or disable the unhealthy provider",),
        "provider_error": ("inspect provider health before retrying",),
        "storage_error": ("restore durable storage before retrying",),
        "internal_error": ("capture request_id and inspect server logs",),
    }
    return actions.get(category, ("review request and retry only after correcting the error",))
