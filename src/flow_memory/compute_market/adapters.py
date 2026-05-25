"""Provider adapter interfaces and production-safe quote collection scaffolding."""
from __future__ import annotations

import json
import ipaddress
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

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
from flow_memory.compute_market.storage import ComputeMarketStore, deterministic_id, utc_now_iso
from flow_memory.crypto.hashes import content_hash


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
        return self.provider.rate_limit_profile


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
    auth_header_name: str = ""
    auth_header_value_env: str = ""
    timeout_seconds: float = 2.0
    enabled: bool = False
    allowed_hosts: tuple[str, ...] = ()
    allow_private_networks: bool = False
    max_response_bytes: int = 65_536
    preserve_raw_quote: bool = True
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

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
        payload = json.dumps({"profile": task_profile.as_record(), "policy_hash": content_hash(policy.as_record())}, sort_keys=True).encode("utf-8")
        attempts = max(1, self.retry_policy.max_retries + 1)
        last_status = QuoteStatus.PROVIDER_ERROR.value
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(
                    self.endpoint,
                    data=payload,
                    headers=self._request_headers(),
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
            except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                last_status = QuoteStatus.INVALID_RESPONSE.value if attempt == attempts - 1 else QuoteStatus.PROVIDER_ERROR.value
            if attempt + 1 < attempts:
                time.sleep(self.retry_policy.backoff_seconds)
        return tuple(_quote_with_status(collect_quote(route, task_profile), last_status) for route in self.list_routes())

    def normalize_quote(self, raw_quote: Mapping[str, Any]) -> ComputeQuote:
        required = {"quote_id", "provider_id", "provider_or_route", "provider_type", "route_id", "market_type", "network", "payment_asset", "unit_type", "unit_price", "estimated_units", "estimated_total_cost"}
        missing = tuple(key for key in required if key not in raw_quote)
        if missing:
            raise ValueError(f"provider quote missing fields: {missing}")
        allowed = set(ComputeQuote.__dataclass_fields__)
        sanitized = {str(key): value for key, value in raw_quote.items() if str(key) in allowed}
        sanitized["source"] = "live"
        sanitized.setdefault("status", QuoteStatus.VALID.value)
        sanitized.setdefault("confidence", 0.75)
        sanitized["provider_id"] = self.provider.provider_id
        if sanitized.get("unit_price") is None or sanitized.get("estimated_total_cost") is None:
            sanitized["status"] = QuoteStatus.UNKNOWN_PRICE.value
        if str(sanitized.get("expires_at", "")) and _expired(str(sanitized.get("expires_at", ""))):
            sanitized["status"] = QuoteStatus.STALE.value
            sanitized["stale"] = True
        if self.preserve_raw_quote:
            sanitized["raw_quote_hash"] = content_hash(raw_quote)
        return normalize_quote(ComputeQuote(**sanitized))

    def _request_headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json", "accept": "application/json"}
        if self.auth_header_name and self.auth_header_value_env:
            value = os.environ.get(self.auth_header_value_env, "")
            if value:
                headers[self.auth_header_name] = value
        return headers

    def simulate_execution(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"ok": True, "source": "http_provider", "dry_run_only": True, "plan_id": str(plan.get("decision_id", ""))}

    def execute_plan(self, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "ok": False,
            "error_code": "settlement_disallowed",
            "message": "HTTP provider execution is disabled until all live-settlement gates pass",
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
        }

    def get_reliability_snapshot(self) -> Mapping[str, Any]:
        return {"provider_id": self.provider.provider_id, "reliability_score": self.provider.reliability_score}

    def get_rate_limits(self) -> Mapping[str, Any]:
        return self.provider.rate_limit_profile


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
            if cached_entry and not _expired(str(cached_entry.get("expires_at", ""))):
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


def _is_private_or_local_host(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    if lowered in {"localhost", "ip6-localhost", "ip6-loopback"} or lowered.endswith(".local"):
        return True
    if lowered == "metadata.google.internal":
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast)

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


def _expired(expires_at: str) -> bool:
    if not expires_at:
        return False
    return expires_at < utc_now_iso()
