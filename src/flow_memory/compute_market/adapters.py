"""Provider adapter interfaces and production-safe quote collection scaffolding."""
from __future__ import annotations

import json
import ipaddress
import math
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, SupportsFloat, cast

from flow_memory.compute_market.models import (
    ComputeMarketPolicy,
    ComputeProvider,
    ComputeQuote,
    ComputeRoute,
    ProviderHealthSnapshot,
    QuoteCacheEntry,
    QuoteStatus,
    TaskEconomicProfile,
)
from flow_memory.compute_market.pricing import collect_quote, normalize_quote
from flow_memory.compute_market.provider_contracts import (
    EXECUTION_RESULT_SIGNATURE_CONTEXT,
    QUOTE_SIGNATURE_CONTEXT,
    parse_quote_timestamp,
    verify_provider_quote_signature,
)
from flow_memory.compute_market.storage import ComputeMarketStore, deterministic_id, utc_now_iso
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import sign_payload


class ComputeProviderAdapter(Protocol):
    def get_provider_metadata(self) -> ComputeProvider:
        ...

    def health_check(self) -> ProviderHealthSnapshot:
        ...

    def list_routes(self) -> tuple[ComputeRoute, ...]:
        ...

    def get_capacity(self, route_id: str) -> Mapping[str, Any]:
        ...

    def quote(self, task_profile: TaskEconomicProfile, policy: ComputeMarketPolicy) -> tuple[ComputeQuote, ...]:
        ...

    def normalize_quote(self, raw_quote: Mapping[str, Any]) -> ComputeQuote:
        ...

    def simulate_execution(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def execute_plan(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def get_reliability_snapshot(self) -> Mapping[str, Any]:
        ...

    def get_rate_limits(self) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    backoff_seconds: float = 0.01
    jitter_seconds: float = 0.0


@dataclass
class ProviderCircuitBreaker:
    failure_threshold: int = 3
    reset_after_seconds: int = 60
    failures: dict[str, int] = field(default_factory=dict)
    opened_at: dict[str, float] = field(default_factory=dict)

    def allow(self, provider_id: str, *, now: float | None = None) -> bool:
        opened = self.opened_at.get(provider_id)
        if opened is None:
            return True
        current = time.monotonic() if now is None else now
        if current - opened >= self.reset_after_seconds:
            self.failures[provider_id] = 0
            self.opened_at.pop(provider_id, None)
            return True
        return False

    def record_success(self, provider_id: str) -> None:
        self.failures[provider_id] = 0
        self.opened_at.pop(provider_id, None)

    def record_failure(self, provider_id: str, *, now: float | None = None) -> None:
        count = self.failures.get(provider_id, 0) + 1
        self.failures[provider_id] = count
        if count >= self.failure_threshold:
            self.opened_at[provider_id] = time.monotonic() if now is None else now


@dataclass(frozen=True)
class StaticConfiguredProvider:
    provider: ComputeProvider
    routes: tuple[ComputeRoute, ...]

    def get_provider_metadata(self) -> ComputeProvider:
        return self.provider

    def health_check(self) -> ProviderHealthSnapshot:
        status = "healthy" if self.provider.status == "active" and self.provider.capacity_available else "degraded"
        return ProviderHealthSnapshot(
            health_snapshot_id=deterministic_id("provider_health", {"provider_id": self.provider.provider_id, "status": status}),
            provider_id=self.provider.provider_id,
            status=status,
            reliability_score=self.provider.reliability_score,
            latency_ms=self.provider.average_latency_ms,
            route_count=len(self.routes),
            rate_limits=self.provider.rate_limit_profile,
        )

    def list_routes(self) -> tuple[ComputeRoute, ...]:
        if self.provider.status != "active":
            return ()
        return tuple(route for route in self.routes if route.enabled and route.provider_id == self.provider.provider_id)

    def get_capacity(self, route_id: str) -> Mapping[str, Any]:
        for route in self.routes:
            if route.route_id == route_id:
                return {
                    "route_id": route_id,
                    "capacity_available": route.capacity_available,
                    "capacity_window": route.capacity_window.as_record() if route.capacity_window else {},
                }
        return {"route_id": route_id, "capacity_available": False, "error_code": "route_not_found"}

    def quote(self, task_profile: TaskEconomicProfile, policy: ComputeMarketPolicy) -> tuple[ComputeQuote, ...]:
        if self.provider.status != "active":
            return tuple(
                _quote_with_status(collect_quote(route, task_profile), QuoteStatus.DISABLED_PROVIDER.value)
                for route in self.routes
                if route.provider_id == self.provider.provider_id
            )
        quotes = []
        for route in self.list_routes():
            quote = collect_quote(route, task_profile)
            if policy.quote_ttl_seconds and quote.quote_ttl_seconds > policy.quote_ttl_seconds:
                quote = ComputeQuote(**{**quote.as_record(), "stale": True, "status": QuoteStatus.STALE.value})
            quotes.append(quote)
        return tuple(quotes)

    def normalize_quote(self, raw_quote: Mapping[str, Any]) -> ComputeQuote:
        return ComputeQuote(**dict(raw_quote))

    def simulate_execution(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"ok": True, "dry_run_only": True, "plan_id": str(plan.get("decision_id", ""))}

    def execute_plan(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "ok": False,
            "error_code": "settlement_disallowed",
            "message": "execute_plan is disabled unless future live settlement gates pass",
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
        }

    def get_reliability_snapshot(self) -> Mapping[str, Any]:
        return {"provider_id": self.provider.provider_id, "reliability_score": self.provider.reliability_score}

    def get_rate_limits(self) -> Mapping[str, Any]:
        return dict(self.provider.rate_limit_profile)


@dataclass(frozen=True)
class LocalMockComputeProvider(StaticConfiguredProvider):
    """Deterministic provider adapter for tests and local dry-run planning."""


@dataclass(frozen=True)
class ReservedCapacityProvider(StaticConfiguredProvider):
    def quote(self, task_profile: TaskEconomicProfile, policy: ComputeMarketPolicy) -> tuple[ComputeQuote, ...]:
        quotes = []
        for route in self.list_routes():
            quote = collect_quote(route, task_profile)
            if route.reservation_required and not route.capacity_available:
                quote = _quote_with_status(quote, QuoteStatus.CAPACITY_UNAVAILABLE.value)
            quotes.append(quote)
        return tuple(quotes)


@dataclass(frozen=True)
class MarketplaceProvider(StaticConfiguredProvider):
    def list_routes(self) -> tuple[ComputeRoute, ...]:
        return tuple(route for route in super().list_routes() if route.market_type == "marketplace")


@dataclass(frozen=True)
class HTTPQuoteProvider:
    provider: ComputeProvider
    routes: tuple[ComputeRoute, ...]
    endpoint: str = ""
    execution_endpoint: str = ""
    execution_enabled: bool = False
    execution_timeout_seconds: float = 10.0
    auth_header_name: str = ""
    auth_header_value_env: str = ""
    execution_auth_header_name: str = ""
    execution_auth_header_value_env: str = ""
    timeout_seconds: float = 2.0
    enabled: bool = False
    allowed_hosts: tuple[str, ...] = ()
    allow_private_networks: bool = False
    max_response_bytes: int = 65_536
    preserve_raw_quote: bool = True
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    signing_key: LocalKeyPair | None = None
    execution_signing_key: LocalKeyPair | None = None
    signing_required: bool = False
    execution_signing_required: bool = False
    verification_public_key: str | Mapping[str, Any] = ""

    def get_provider_metadata(self) -> ComputeProvider:
        return self.provider

    def health_check(self) -> ProviderHealthSnapshot:
        if not self.enabled or not self.endpoint:
            return ProviderHealthSnapshot(
                health_snapshot_id=deterministic_id("provider_health", {"provider_id": self.provider.provider_id, "status": "disabled"}),
                provider_id=self.provider.provider_id,
                status="disabled",
                reliability_score=0.0,
                latency_ms=0,
                error_code="disabled_provider",
                message="HTTP quote provider is disabled unless explicitly configured",
            )
        return ProviderHealthSnapshot(
            health_snapshot_id=deterministic_id("provider_health", {"provider_id": self.provider.provider_id, "status": "configured"}),
            provider_id=self.provider.provider_id,
            status="configured",
            reliability_score=self.provider.reliability_score,
            latency_ms=self.provider.average_latency_ms,
            route_count=len(self.routes),
        )

    def list_routes(self) -> tuple[ComputeRoute, ...]:
        return tuple(route for route in self.routes if route.provider_id == self.provider.provider_id and route.enabled)

    def get_capacity(self, route_id: str) -> Mapping[str, Any]:
        return {"route_id": route_id, "capacity_available": bool(self.enabled), "source": "http_provider"}

    def quote(self, task_profile: TaskEconomicProfile, policy: ComputeMarketPolicy) -> tuple[ComputeQuote, ...]:
        if not self.enabled or not self.endpoint:
            return tuple(
                _quote_with_status(collect_quote(route, task_profile), QuoteStatus.DISABLED_PROVIDER.value)
                for route in self.list_routes()
            )
        endpoint_error = _validate_http_endpoint(
            self.endpoint,
            allowed_hosts=self.allowed_hosts,
            allow_private_networks=self.allow_private_networks,
        )
        if endpoint_error:
            return tuple(_quote_with_status(collect_quote(route, task_profile), QuoteStatus.PROVIDER_ERROR.value) for route in self.list_routes())
        if self.signing_required and self._signing_key(execution=False) is None:
            return tuple(_quote_with_status(collect_quote(route, task_profile), QuoteStatus.PROVIDER_ERROR.value) for route in self.list_routes())
        payload_record = {"profile": task_profile.as_record(), "policy_hash": content_hash(policy.as_record())}
        payload = json.dumps(payload_record, sort_keys=True).encode("utf-8")
        attempts = max(1, self.retry_policy.max_retries + 1)
        last_status = QuoteStatus.PROVIDER_ERROR.value
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(
                    self.endpoint,
                    data=payload,
                    headers=self._request_headers(payload=payload_record),
                    method="POST",
                )
                opener = urllib.request.build_opener(_NoRedirectHandler())
                with opener.open(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - URL is validated by _validate_http_endpoint before use
                    raw_bytes = response.read(self.max_response_bytes + 1)
                if len(raw_bytes) > self.max_response_bytes:
                    raise ValueError("provider response exceeds max_response_bytes")
                raw = json.loads(raw_bytes.decode("utf-8"))
                return tuple(self.normalize_quote(item) for item in _extract_quotes(raw))
            except TimeoutError:
                last_status = QuoteStatus.PROVIDER_TIMEOUT.value
            except urllib.error.HTTPError as exc:
                last_status = QuoteStatus.INVALID_RESPONSE.value if 300 <= exc.code < 400 else QuoteStatus.PROVIDER_ERROR.value
            except urllib.error.URLError:
                last_status = QuoteStatus.PROVIDER_ERROR.value
            except OSError:
                last_status = QuoteStatus.PROVIDER_ERROR.value
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                last_status = QuoteStatus.INVALID_RESPONSE.value if attempt == attempts - 1 else QuoteStatus.PROVIDER_ERROR.value
            if attempt + 1 < attempts:
                time.sleep(self.retry_policy.backoff_seconds)
        return tuple(_quote_with_status(collect_quote(route, task_profile), last_status) for route in self.list_routes())

    def normalize_quote(self, raw_quote: Mapping[str, Any]) -> ComputeQuote:
        normalized_raw = dict(raw_quote)
        raw_signature = raw_quote.get("signature") or raw_quote.get("verification")
        signed_quote_valid = False
        if self.verification_public_key:
            signed_quote_valid = verify_provider_quote_signature(raw_quote, self.verification_public_key, signature_context=QUOTE_SIGNATURE_CONTEXT)
            if not signed_quote_valid:
                raise ValueError("provider quote signature is missing or invalid")
        normalized_raw.setdefault("provider_or_route", normalized_raw.get("route_id", self.provider.provider_name))
        normalized_raw.setdefault("provider_type", self.provider.provider_type)
        normalized_raw.setdefault("market_type", self.provider.market_type)
        normalized_raw.setdefault("network", normalized_raw.get("supported_network", self.provider.network))
        normalized_raw.setdefault("payment_asset", normalized_raw.get("currency_or_asset", self.provider.payment_asset))
        normalized_raw["settlement_mode"] = "generic_dry_run"
        normalized_raw["settlement_options"] = ("generic_dry_run",)
        normalized_raw["dry_run_only"] = True
        normalized_raw.setdefault("original_quote", dict(raw_quote))
        required = {
            "quote_id",
            "provider_id",
            "provider_or_route",
            "provider_type",
            "route_id",
            "market_type",
            "network",
            "payment_asset",
            "unit_type",
            "unit_price",
            "estimated_units",
            "estimated_total_cost",
            "expires_at",
        }
        missing = tuple(key for key in required if key not in normalized_raw)
        if missing:
            raise ValueError(f"provider quote missing fields: {missing}")
        raw_provider_id = str(normalized_raw.get("provider_id", "")).strip()
        if raw_provider_id != self.provider.provider_id:
            raise ValueError("provider quote provider_id does not match configured provider")
        raw_route_id = str(normalized_raw.get("route_id", "")).strip()
        configured_route_ids = frozenset(route.route_id for route in self.routes)
        synthetic_only = configured_route_ids == frozenset({f"{self.provider.provider_id}:external"})
        if not synthetic_only and raw_route_id not in configured_route_ids:
            raise ValueError("provider quote route_id does not match configured provider routes")
        allowed = set(ComputeQuote.__dataclass_fields__)
        sanitized = {str(key): value for key, value in normalized_raw.items() if str(key) in allowed}
        sanitized["source"] = "live"
        sanitized.setdefault("status", QuoteStatus.VALID.value)
        sanitized.setdefault("confidence", 0.75)
        sanitized["provider_id"] = self.provider.provider_id
        sanitized["unit_price"] = _optional_float(sanitized.get("unit_price"))
        sanitized["estimated_units"] = _optional_non_negative(sanitized.get("estimated_units"))
        sanitized["estimated_total_cost"] = _optional_float(sanitized.get("estimated_total_cost"))
        if sanitized.get("unit_price") is None or sanitized.get("estimated_total_cost") is None:
            sanitized["status"] = QuoteStatus.UNKNOWN_PRICE.value
        if str(sanitized.get("expires_at", "")) and _expired(str(sanitized.get("expires_at", ""))):
            sanitized["status"] = QuoteStatus.STALE.value
            sanitized["stale"] = True
        if normalized_raw.get("stale") is True:
            sanitized["status"] = QuoteStatus.STALE.value
            sanitized["stale"] = True
        if raw_signature:
            sanitized["signed_quote"] = json.dumps(raw_signature, sort_keys=True, default=str)
            sanitized["signed_quote_valid"] = signed_quote_valid
        if self.preserve_raw_quote:
            sanitized["raw_quote_hash"] = content_hash(raw_quote)
        return normalize_quote(ComputeQuote(**sanitized))

    def _request_headers(self, *, execution: bool = False, payload: Mapping[str, Any] | None = None) -> dict[str, str]:
        headers = {"content-type": "application/json", "accept": "application/json"}
        header_name = self.execution_auth_header_name if execution and self.execution_auth_header_name else self.auth_header_name
        value_env = self.execution_auth_header_value_env if execution and self.execution_auth_header_value_env else self.auth_header_value_env
        if header_name and value_env:
            value = os.environ.get(value_env, "")
            if value:
                headers[header_name] = value
        signing_key = self._signing_key(execution=execution)
        if signing_key is not None and payload is not None:
            headers.update(
                signed_provider_request_headers(
                    payload,
                    provider_id=self.provider.provider_id,
                    signing_key=signing_key,
                    kind="execution" if execution else "quote",
                )
            )
        return headers

    def _signing_key(self, *, execution: bool) -> LocalKeyPair | None:
        return self.execution_signing_key if execution and self.execution_signing_key is not None else self.signing_key

    def simulate_execution(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"ok": True, "source": "http_provider", "dry_run_only": True, "plan_id": str(plan.get("decision_id", plan.get("job_id", "")))}

    def execute_plan(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self.execution_enabled or not self.execution_endpoint:
            return _execution_error(
                "provider_execution.disabled",
                "HTTP provider execution is disabled unless explicitly configured.",
                provider_id=self.provider.provider_id,
                job_id=str(plan.get("job_id", "")),
            )
        endpoint_error = _validate_http_endpoint(
            self.execution_endpoint,
            allowed_hosts=self.allowed_hosts,
            allow_private_networks=self.allow_private_networks,
        )
        if endpoint_error:
            return _execution_error(
                "provider_execution.endpoint_rejected",
                endpoint_error,
                provider_id=self.provider.provider_id,
                job_id=str(plan.get("job_id", "")),
            )
        if self.execution_signing_required and self._signing_key(execution=True) is None:
            return _execution_error(
                "provider_execution.signing_key_missing",
                "Provider execution requires outbound request signing, but no signing key is configured.",
                provider_id=self.provider.provider_id,
                job_id=str(plan.get("job_id", "")),
            )
        execution_job = _execution_job_contract(plan)
        payload_record = {
            "job": execution_job,
            "provider_id": self.provider.provider_id,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }
        execution_idempotency_key = str(execution_job.get("execution_idempotency_key", ""))
        request_headers = self._request_headers(execution=True, payload=payload_record)
        if execution_idempotency_key:
            request_headers["idempotency-key"] = execution_idempotency_key
            request_headers["x-flow-memory-provider-idempotency-key"] = execution_idempotency_key
        payload = json.dumps(payload_record, sort_keys=True, default=str).encode("utf-8")
        attempts = max(1, self.retry_policy.max_retries + 1)
        last_error = "provider_execution.provider_error"
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(
                    self.execution_endpoint,
                    data=payload,
                    headers=request_headers,
                    method="POST",
                )
                opener = urllib.request.build_opener(_NoRedirectHandler())
                with opener.open(request, timeout=self.execution_timeout_seconds) as response:  # noqa: S310 - URL is validated by _validate_http_endpoint before use
                    raw_bytes = response.read(self.max_response_bytes + 1)
                if len(raw_bytes) > self.max_response_bytes:
                    raise ValueError("provider execution response exceeds max_response_bytes")
                raw = json.loads(raw_bytes.decode("utf-8"))
                return self.normalize_execution_result(
                    raw,
                    {**dict(plan), "execution_idempotency_key": execution_idempotency_key},
                )
            except TimeoutError:
                last_error = "provider_execution.timeout"
            except urllib.error.HTTPError as exc:
                last_error = "provider_execution.invalid_response" if 300 <= exc.code < 400 else "provider_execution.provider_error"
            except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                last_error = "provider_execution.invalid_response" if attempt == attempts - 1 else "provider_execution.provider_error"
            if attempt + 1 < attempts:
                time.sleep(self.retry_policy.backoff_seconds)
        return _execution_error(last_error, "Provider execution request failed.", provider_id=self.provider.provider_id, job_id=str(plan.get("job_id", "")))

    def normalize_execution_result(self, raw_result: object, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        result = _extract_execution_result(raw_result)
        job_id = str(plan.get("job_id", ""))
        raw_signature = result.get("signature") or result.get("verification")
        execution_signature_valid = False
        if self.verification_public_key:
            execution_signature_valid = verify_provider_quote_signature(result, self.verification_public_key, signature_context=EXECUTION_RESULT_SIGNATURE_CONTEXT)
            if not execution_signature_valid:
                return _execution_error(
                    "provider_execution.signature_invalid",
                    "Provider execution response signature is missing or invalid.",
                    provider_id=self.provider.provider_id,
                    job_id=job_id,
                )
        result_job_id = str(result.get("job_id", job_id))
        result_provider_id = str(result.get("provider_id", self.provider.provider_id))
        if result_job_id != job_id:
            return _execution_error("provider_execution.job_mismatch", "Provider execution response job_id does not match the requested job.", provider_id=self.provider.provider_id, job_id=job_id)
        if result_provider_id != self.provider.provider_id:
            return _execution_error("provider_execution.provider_mismatch", "Provider execution response provider_id does not match the configured provider.", provider_id=self.provider.provider_id, job_id=job_id)
        status = str(result.get("status", "accepted")).strip().lower()
        if status not in {"accepted", "queued", "dispatched", "running", "succeeded", "failed"}:
            return _execution_error("provider_execution.invalid_status", "Provider execution response has an invalid status.", provider_id=self.provider.provider_id, job_id=job_id)
        artifact_ref = str(result.get("artifact_ref", ""))
        artifact_error = _validate_artifact_ref(artifact_ref, allowed_hosts=self.allowed_hosts, allow_private_networks=self.allow_private_networks)
        if artifact_error:
            return _execution_error("provider_execution.artifact_ref_rejected", artifact_error, provider_id=self.provider.provider_id, job_id=job_id)
        artifact_data = result.get("artifact_data", result.get("artifact", {}))
        if artifact_data and not isinstance(artifact_data, Mapping):
            return _execution_error("provider_execution.invalid_artifact", "artifact_data must be an object when present.", provider_id=self.provider.provider_id, job_id=job_id)
        normalized = {
            "ok": status != "failed",
            "job_id": job_id,
            "provider_id": self.provider.provider_id,
            "provider_job_id": str(result.get("provider_job_id", result.get("execution_id", ""))),
            "status": status,
            "artifact_ref": artifact_ref,
            "artifact_data": dict(artifact_data) if isinstance(artifact_data, Mapping) else {},
            "actual_units": _optional_non_negative(result.get("actual_units", result.get("units", 0.0))),
            "actual_total_cost": _optional_non_negative(result.get("actual_total_cost", result.get("cost", 0.0))),
            "actual_latency_ms": _optional_non_negative(result.get("actual_latency_ms", result.get("latency_ms", 0.0))),
            "error_code": str(result.get("error_code", "")),
            "message": str(result.get("message", "")),
            "source": "external_provider_execution",
            "external_provider_called": True,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
            "execution_idempotency_key": str(plan.get("execution_idempotency_key", "")),
            "raw_result_hash": content_hash(result),
        }
        if raw_signature:
            normalized["provider_execution_signature"] = json.dumps(raw_signature, sort_keys=True, default=str)
            normalized["provider_execution_signature_valid"] = execution_signature_valid
        return normalized

    def get_reliability_snapshot(self) -> Mapping[str, Any]:
        return {"provider_id": self.provider.provider_id, "reliability_score": self.provider.reliability_score}

    def get_rate_limits(self) -> Mapping[str, Any]:
        return dict(self.provider.rate_limit_profile)


def signed_provider_request_headers(
    payload: Mapping[str, Any],
    *,
    provider_id: str,
    signing_key: LocalKeyPair,
    kind: str,
    timestamp: str = "",
    nonce: str = "",
) -> dict[str, str]:
    issued_at = timestamp or str(int(time.time()))
    payload_hash = content_hash(payload)
    request_nonce = nonce or deterministic_id(
        "provider_request_nonce",
        {
            "provider_id": provider_id,
            "kind": kind,
            "payload_hash": payload_hash,
            "timestamp": issued_at,
        },
    )
    signature_payload = {
        "provider_id": provider_id,
        "kind": kind,
        "payload_hash": payload_hash,
        "timestamp": issued_at,
        "nonce": request_nonce,
    }
    envelope = sign_payload(signature_payload, signing_key).as_record()
    return {
        "x-flow-memory-provider-signature": json.dumps(envelope, sort_keys=True),
        "x-flow-memory-provider-signature-payload": json.dumps(signature_payload, sort_keys=True),
        "x-flow-memory-provider-signature-key-id": signing_key.key_id,
        "x-flow-memory-provider-request-timestamp": issued_at,
        "x-flow-memory-provider-request-nonce": request_nonce,
    }

@dataclass
class QuoteCollector:
    adapters: tuple[ComputeProviderAdapter, ...]
    store: ComputeMarketStore | None = None
    circuit_breaker: ProviderCircuitBreaker = field(default_factory=ProviderCircuitBreaker)

    def collect(
        self,
        task_profile: TaskEconomicProfile,
        policy: ComputeMarketPolicy,
        *,
        use_cache: bool = True,
    ) -> tuple[ComputeQuote, ...]:
        quotes: list[ComputeQuote] = []
        task_hash = task_profile.task_hash or content_hash(task_profile.as_record())
        policy_hash = content_hash(policy.as_record())
        for adapter in self.adapters:
            provider = adapter.get_provider_metadata()
            if not self.circuit_breaker.allow(provider.provider_id):
                quotes.extend(
                    _quote_with_status(collect_quote(route, task_profile), QuoteStatus.PROVIDER_ERROR.value)
                    for route in adapter.list_routes()
                )
                continue
            try:
                provider_quotes = self._collect_adapter_quotes(adapter, task_profile, policy, task_hash, policy_hash, use_cache)
                self.circuit_breaker.record_success(provider.provider_id)
                quotes.extend(provider_quotes)
            except Exception:
                self.circuit_breaker.record_failure(provider.provider_id)
                quotes.extend(
                    _quote_with_status(collect_quote(route, task_profile), QuoteStatus.PROVIDER_ERROR.value)
                    for route in adapter.list_routes()
                )
        return tuple(quotes)

    def _collect_adapter_quotes(
        self,
        adapter: ComputeProviderAdapter,
        task_profile: TaskEconomicProfile,
        policy: ComputeMarketPolicy,
        task_hash: str,
        policy_hash: str,
        use_cache: bool,
    ) -> tuple[ComputeQuote, ...]:
        if self.store is None or not use_cache:
            return tuple(normalize_quote(quote) for quote in adapter.quote(task_profile, policy))
        cached: list[ComputeQuote] = []
        misses: list[ComputeRoute] = []
        for route in adapter.list_routes():
            cache_key = self.store.quote_cache_key(route.provider_id, route.route_id, task_hash, policy_hash)
            cached_entry = self.store.get_record("quote_cache_entry", cache_key)
            if cached_entry:
                cache_status = str(cached_entry.get("status", "")).lower()
                if cache_status not in {"invalidated", "stale", "expired", "disabled"} and not _expired(str(cached_entry.get("expires_at", ""))):
                    quote_record = cached_entry.get("quote", {})
                    if isinstance(quote_record, Mapping):
                        cached.append(ComputeQuote(**dict(quote_record, source="cache")))
                        continue
            misses.append(route)
        if not misses:
            return tuple(cached)
        live_quotes = tuple(normalize_quote(quote) for quote in adapter.quote(task_profile, policy) if quote.route_id in {route.route_id for route in misses})
        for quote in live_quotes:
            cache_key = self.store.quote_cache_key(quote.provider_id, quote.route_id, task_hash, policy_hash)
            expires_at = quote.expires_at or utc_now_iso()
            cache_entry = QuoteCacheEntry(
                cache_key=cache_key,
                provider_id=quote.provider_id,
                route_id=quote.route_id,
                task_hash=task_hash,
                policy_hash=policy_hash,
                quote=quote.as_record(),
                source=quote.source or "static",
                ttl_seconds=quote.quote_ttl_seconds,
                expires_at=expires_at,
                status=quote.status,
            )
            self.store.put_record(
                "quote_cache_entry",
                cache_key,
                cache_entry.as_record(),
                provider_id=quote.provider_id,
                route_id=quote.route_id,
                task_hash=task_hash,
                status=quote.status,
                expires_at=expires_at,
            )
        return (*cached, *live_quotes)


def build_external_provider_adapter(
    provider_record: Mapping[str, Any],
    routes: tuple[Mapping[str, Any], ...],
    config: object,
) -> HTTPQuoteProvider:
    provider = _provider_from_record(provider_record)
    endpoint = _quote_endpoint(provider_record)
    execution_endpoint = _execution_endpoint(provider_record)
    route_records = routes or (_synthetic_route_record(provider_record),)
    route_objects = tuple(_route_from_record(route, provider) for route in route_records)
    timeout_ms = int(getattr(config, "external_provider_quote_timeout_ms", getattr(config, "provider_timeout_ms", 5_000)) or 5_000)
    return HTTPQuoteProvider(
        provider,
        route_objects,
        endpoint=endpoint,
        execution_endpoint=execution_endpoint,
        execution_enabled=bool(getattr(config, "external_provider_execution_enabled", False)),
        enabled=bool(getattr(config, "external_provider_quotes_enabled", False)),
        allowed_hosts=tuple(str(item) for item in getattr(config, "external_provider_allowlist", ()) if str(item)),
        allow_private_networks=str(getattr(config, "compute_market_mode", "")) == "test",
        max_response_bytes=65_536,
        timeout_seconds=max(1.0, timeout_ms / 1000.0),
        execution_timeout_seconds=max(1.0, int(getattr(config, "external_provider_execution_timeout_ms", timeout_ms) or timeout_ms) / 1000.0),
        auth_header_name=str(_metadata_value(provider_record, "auth_header_name", "")),
        auth_header_value_env=str(_metadata_value(provider_record, "auth_header_value_env", "")),
        execution_auth_header_name=str(_metadata_value(provider_record, "execution_auth_header_name", _metadata_value(provider_record, "auth_header_name", ""))),
        execution_auth_header_value_env=str(_metadata_value(provider_record, "execution_auth_header_value_env", _metadata_value(provider_record, "auth_header_value_env", ""))),
        signing_key=_local_signing_key(provider_record, execution=False),
        execution_signing_key=_local_signing_key(provider_record, execution=True),
        verification_public_key=_verification_public_key(provider_record),
        signing_required=_truthy(_metadata_value(provider_record, "outbound_signing_required", False)),
        execution_signing_required=_truthy(
            _metadata_value(
                provider_record,
                "execution_outbound_signing_required",
                _metadata_value(provider_record, "outbound_signing_required", False),
            )
        ),
    )


def _provider_from_record(record: Mapping[str, Any]) -> ComputeProvider:
    metadata = record.get("metadata", {})
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    return ComputeProvider(
        provider_id=str(record.get("provider_id", "")),
        provider_name=str(record.get("provider_name", record.get("provider_id", ""))),
        provider_type=str(record.get("provider_type", "marketplace")),
        market_type=str(record.get("market_type", "marketplace")),
        network=str(record.get("network") or _first(record.get("supported_networks"), "offchain")),
        payment_asset=str(record.get("payment_asset") or _first(record.get("supported_assets"), "USD")),
        capabilities=(),
        reliability_score=float(record.get("reliability_score", 1.0) or 1.0),
        dry_run_only=bool(record.get("dry_run_only", True)),
        capacity_available=bool(record.get("capacity_available", True)),
        metadata=dict(metadata_map),
        status=str(record.get("status", "active")),
        supported_unit_types=_tuple(record.get("supported_unit_types", ())),
        supported_networks=_tuple(record.get("supported_networks", ())),
        supported_assets=_tuple(record.get("supported_assets", ())),
        supported_settlement_modes=_tuple(record.get("supported_settlement_modes", ("generic_dry_run",))),
        average_latency_ms=int(record.get("average_latency_ms", 1000) or 1000),
        quote_ttl_seconds=int(record.get("quote_ttl_seconds", 300) or 300),
        health_check_url=str(record.get("health_check_url", metadata_map.get("health_endpoint", ""))),
        configured_by=str(record.get("configured_by", "provider-admin")),
        verified=bool(record.get("verified", False)),
        config_version=int(record.get("config_version", 1) or 1),
    )


def _route_from_record(record: Mapping[str, Any], provider: ComputeProvider) -> ComputeRoute:
    return ComputeRoute(
        route_id=str(record.get("route_id") or f"{provider.provider_id}:external"),
        provider_id=provider.provider_id,
        provider_or_route=str(record.get("provider_or_route", provider.provider_name)),
        provider_type=str(record.get("provider_type", provider.provider_type)),
        market_type=str(record.get("market_type", provider.market_type)),
        network=str(record.get("network", provider.network)),
        payment_asset=str(record.get("payment_asset", provider.payment_asset)),
        unit_type=str(record.get("unit_type") or _first(provider.supported_unit_types, "request")),
        unit_price=_optional_float(record.get("unit_price")),
        estimated_units=float(record.get("estimated_units", 0.0) or 0.0),
        estimated_total_cost=_optional_float(record.get("estimated_total_cost")),
        estimated_latency_ms=int(record.get("estimated_latency_ms", provider.average_latency_ms) or provider.average_latency_ms),
        capacity_available=bool(record.get("capacity_available", True)),
        reservation_required=bool(record.get("reservation_required", False)),
        settlement_mode="generic_dry_run",
        settlement_modes=("generic_dry_run",),
        dry_run_only=True,
        fallback_route=bool(record.get("fallback_route", False)),
        quote_ttl_seconds=int(record.get("quote_ttl_seconds", provider.quote_ttl_seconds) or provider.quote_ttl_seconds),
        confidence=float(record.get("confidence", 0.75) or 0.75),
        metadata=dict(record.get("metadata", {})) if isinstance(record.get("metadata"), Mapping) else {},
        enabled=bool(record.get("enabled", True)),
        verified_provider_required=bool(record.get("verified_provider_required", False)),
        config_version=int(record.get("config_version", 1) or 1),
    )


def _quote_endpoint(record: Mapping[str, Any]) -> str:
    return str(record.get("quote_endpoint") or _metadata_value(record, "quote_endpoint", ""))


def _execution_endpoint(record: Mapping[str, Any]) -> str:
    return str(record.get("execution_endpoint") or _metadata_value(record, "execution_endpoint", ""))


def _synthetic_route_record(provider_record: Mapping[str, Any]) -> Mapping[str, Any]:
    provider_id = str(provider_record.get("provider_id", "external_provider"))
    return {
        "route_id": f"{provider_id}:external",
        "provider_id": provider_id,
        "provider_or_route": str(provider_record.get("provider_name", provider_id)),
        "provider_type": str(provider_record.get("provider_type", "marketplace")),
        "market_type": "marketplace",
        "network": _first(provider_record.get("supported_networks"), "offchain"),
        "payment_asset": _first(provider_record.get("supported_assets"), "USD"),
        "unit_type": _first(provider_record.get("supported_unit_types"), "request"),
        "enabled": True,
    }


def _metadata_value(record: Mapping[str, Any], key: str, default: object) -> object:
    metadata = record.get("metadata", {})
    if isinstance(metadata, Mapping) and key in metadata:
        return metadata[key]
    return record.get(key, default)


def _local_signing_key(record: Mapping[str, Any], *, execution: bool) -> LocalKeyPair | None:
    key_id_name = "execution_outbound_signing_key_id" if execution else "outbound_signing_key_id"
    env_name_key = "execution_outbound_signing_key_env" if execution else "outbound_signing_key_env"
    default_key_id = _metadata_value(record, "outbound_signing_key_id", "")
    default_env_name = _metadata_value(record, "outbound_signing_key_env", "")
    key_id = str(_metadata_value(record, key_id_name, default_key_id)).strip()
    env_name = str(_metadata_value(record, env_name_key, default_env_name)).strip()
    secret = os.environ.get(env_name, "") if env_name else ""
    if not key_id or not secret:
        return None
    return LocalKeyPair(key_id=key_id, secret=secret)


def _verification_public_key(record: Mapping[str, Any]) -> str | Mapping[str, Any]:
    for key in ("quote_verification_public_key", "provider_public_key", "public_key"):
        value = _metadata_value(record, key, "")
        if isinstance(value, Mapping):
            return value
        if str(value or "").strip():
            return str(value)
    return ""


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _first(value: object, default: str) -> str:
    values = _tuple(value)
    return values[0] if values else default


def _tuple(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    amount = float(cast(SupportsFloat | str | bytes | bytearray, value))
    if not math.isfinite(amount):
        raise ValueError("numeric values must be finite")
    return amount


def _optional_non_negative(value: object) -> float:
    if value in (None, ""):
        return 0.0
    amount = float(cast(SupportsFloat | str | bytes | bytearray, value))
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("execution numeric values must be finite and non-negative")
    return amount


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Mapping[str, str], newurl: str) -> None:  # type: ignore[override]
        return None


def _validate_http_endpoint(endpoint: str, *, allowed_hosts: tuple[str, ...], allow_private_networks: bool) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        return "unsupported_scheme"
    host = parsed.hostname or ""
    if not host:
        return "missing_host"
    allowed = {item.lower() for item in allowed_hosts}
    if allowed and host.lower() not in allowed:
        return "disallowed_host"
    if not allow_private_networks and _is_private_or_local_host(host):
        return "private_network_disallowed"
    if parsed.username or parsed.password:
        return "userinfo_disallowed"
    return ""


def _validate_artifact_ref(artifact_ref: str, *, allowed_hosts: tuple[str, ...], allow_private_networks: bool) -> str:
    if not artifact_ref:
        return ""
    parsed = urlparse(artifact_ref)
    if parsed.scheme in {"", "s3", "gs", "az", "filecoin", "ipfs"}:
        return ""
    if parsed.scheme in {"http", "https"}:
        return _validate_http_endpoint(artifact_ref, allowed_hosts=allowed_hosts, allow_private_networks=allow_private_networks)
    return "unsupported_artifact_ref_scheme"


def _is_private_or_local_host(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    if (
        lowered in {"localhost", "ip6-localhost", "ip6-loopback", "metadata.google.internal"}
        or lowered.endswith(".localhost")
        or lowered.endswith(".local")
    ):
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified or address.is_multicast)

def _quote_with_status(quote: ComputeQuote, status: str) -> ComputeQuote:
    return ComputeQuote(
        **{
            **quote.as_record(),
            "status": status,
            "capacity_available": False if status == QuoteStatus.CAPACITY_UNAVAILABLE.value else quote.capacity_available,
            "expired": status == QuoteStatus.EXPIRED.value or quote.expired,
            "stale": status == QuoteStatus.STALE.value or quote.stale,
        }
    )


def _extract_quotes(raw: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(raw, Mapping):
        if isinstance(raw.get("quote"), Mapping):
            return (raw["quote"],)
        quotes = raw.get("quotes", ())
        if isinstance(quotes, (list, tuple)):
            return tuple(item for item in quotes if isinstance(item, Mapping))
    if isinstance(raw, (list, tuple)):
        return tuple(item for item in raw if isinstance(item, Mapping))
    raise ValueError("provider response must contain a quote or quotes array")


def _extract_execution_result(raw: object) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("provider execution response must be an object")
    result = raw.get("execution", raw.get("result", raw))
    if not isinstance(result, Mapping):
        raise ValueError("provider execution response must contain an execution object")
    return result


def _execution_job_contract(job: Mapping[str, Any]) -> Mapping[str, Any]:
    resource_request = job.get("resource_request", {})
    provider_id = str(job.get("provider_id", ""))
    route_id = str(job.get("route_id", ""))
    job_id = str(job.get("job_id", ""))
    attempt = int(float(job.get("attempt", 0) or 0))
    execution_idempotency_key = deterministic_id(
        "provider_execution",
        {
            "provider_id": provider_id,
            "route_id": route_id,
            "job_id": job_id,
            "attempt": attempt,
        },
    )
    return {
        "job_id": job_id,
        "task_type": str(job.get("task_type", "")),
        "input_ref": str(job.get("input_ref", "")),
        "model_or_runtime": str(job.get("model_or_runtime", "")),
        "resource_request": dict(resource_request) if isinstance(resource_request, Mapping) else {},
        "budget_policy_id": str(job.get("budget_policy_id", "")),
        "route_id": route_id,
        "provider_id": provider_id,
        "attempt": attempt,
        "execution_idempotency_key": execution_idempotency_key,
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
    }


def _execution_error(error_code: str, message: str, *, provider_id: str, job_id: str) -> Mapping[str, Any]:
    return {
        "ok": False,
        "job_id": job_id,
        "provider_id": provider_id,
        "status": "failed",
        "error_code": error_code,
        "message": message,
        "source": "external_provider_execution",
        "external_provider_called": False,
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
    }


def _expired(expires_at: str) -> bool:
    if not expires_at.strip():
        return False
    parsed_expires_at = parse_quote_timestamp(expires_at)
    parsed_now = parse_quote_timestamp(str(utc_now_iso()))
    if parsed_expires_at is None or parsed_now is None:
        return True
    return parsed_expires_at <= parsed_now
