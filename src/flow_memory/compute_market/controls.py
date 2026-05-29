"""Rate-limit and circuit-breaker controls for Flow Memory Compute Market.

The concrete implementations here are intentionally dependency-free so local and
single-node deployments keep working.  The protocol and distributed-ready
scaffolds define the contract that a Redis or managed-rate-limit backend must
satisfy before a horizontally scaled deployment enables it.
"""
from __future__ import annotations

import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class RateLimitDecision:
    ok: bool
    key: str
    limit: int
    remaining: int
    reset_at: float
    retry_after_seconds: float = 0.0
    reason_code: str = ""

    def as_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "key": self.key,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "retry_after_seconds": self.retry_after_seconds,
            "reason_code": self.reason_code,
        }


class RateLimiter(Protocol):
    def check_limit(
        self,
        actor_id: str,
        endpoint: str,
        *,
        cost: int = 1,
        agent_id: str = "",
        workspace_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        api_key: str = "",
    ) -> RateLimitDecision:
        ...

    def record_success(self, key: str) -> None:
        ...

    def record_rejection(self, key: str, reason_code: str) -> None:
        ...

    def get_status(self, key: str) -> Mapping[str, object]:
        ...


@dataclass
class InMemoryRateLimiter:
    """Fixed-window limiter for local/dev/tests.

    This is safe as a local guard but is not a substitute for distributed
    enforcement in multi-node deployments.
    """

    default_limit: int = 120
    window_seconds: int = 60
    route_limits: Mapping[str, int] = field(default_factory=dict)
    _counts: dict[tuple[str, int], int] = field(default_factory=dict)
    _rejections: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def check_limit(
        self,
        actor_id: str,
        endpoint: str,
        *,
        cost: int = 1,
        agent_id: str = "",
        workspace_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        api_key: str = "",
    ) -> RateLimitDecision:
        if cost < 1:
            raise ValueError("rate limit cost must be positive")
        now = time.time()
        window = int(now // self.window_seconds)
        key = rate_limit_key(
            actor_id=actor_id,
            endpoint=endpoint,
            agent_id=agent_id,
            workspace_id=workspace_id,
            provider_id=provider_id,
            route_id=route_id,
            api_key=api_key,
        )
        limit = int(self.route_limits.get(endpoint, self.default_limit))
        counter_key = (key, window)
        next_count = self._counts.get(counter_key, 0) + cost
        reset_at = float((window + 1) * self.window_seconds)
        if next_count > limit:
            retry_after = max(0.0, reset_at - now)
            decision = RateLimitDecision(False, key, limit, 0, reset_at, retry_after, "rate_limited")
            self.record_rejection(key, decision.reason_code)
            return decision
        self._counts[counter_key] = next_count
        return RateLimitDecision(True, key, limit, limit - next_count, reset_at)

    def record_success(self, key: str) -> None:
        self._rejections.pop(key, None)

    def record_rejection(self, key: str, reason_code: str) -> None:
        history = self._rejections.get(key, ())
        self._rejections[key] = (*history[-9:], reason_code)

    def get_status(self, key: str) -> Mapping[str, object]:
        return {"key": key, "backend": "in_memory", "rejections": self._rejections.get(key, ())}


@dataclass(frozen=True)
class DistributedRateLimiter:
    """Redis-ready contract holder for production deployments.

    A deployment can inject an implementation with the same methods backed by
    Redis, Envoy global rate-limit service, or a managed API gateway.  This
    class deliberately refuses checks so it cannot be mistaken for enforcement.
    """

    backend_name: str = "redis-ready"
    connection_url_env: str = "FLOW_MEMORY_COMPUTE_RATE_LIMIT_REDIS_URL"

    def check_limit(
        self,
        actor_id: str,
        endpoint: str,
        *,
        cost: int = 1,
        agent_id: str = "",
        workspace_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        api_key: str = "",
    ) -> RateLimitDecision:
        raise RuntimeError("distributed rate limiter is not configured; inject a concrete backend")

    def record_success(self, key: str) -> None:
        raise RuntimeError("distributed rate limiter is not configured; inject a concrete backend")

    def record_rejection(self, key: str, reason_code: str) -> None:
        raise RuntimeError("distributed rate limiter is not configured; inject a concrete backend")

    def get_status(self, key: str) -> Mapping[str, object]:
        return {"key": key, "backend": self.backend_name, "configured": False, "env": self.connection_url_env}


@dataclass(frozen=True)
class CircuitDecision:
    ok: bool
    key: str
    state: str
    reason_code: str = ""
    retry_after_seconds: float = 0.0

    def as_record(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "key": self.key,
            "state": self.state,
            "reason_code": self.reason_code,
            "retry_after_seconds": self.retry_after_seconds,
        }


class CircuitBreaker(Protocol):
    def allow_request(
        self,
        provider_id: str,
        *,
        route_id: str = "",
        adapter_type: str = "",
        error_class: str = "",
    ) -> CircuitDecision:
        ...

    def record_success(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        ...

    def record_failure(
        self,
        provider_id: str,
        *,
        route_id: str = "",
        adapter_type: str = "",
        error_class: str = "provider_error",
    ) -> None:
        ...

    def get_state(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> Mapping[str, object]:
        ...

    def reset(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        ...

    def open_keys(self) -> tuple[str, ...]:
        ...

    def open_provider_ids(self) -> tuple[str, ...]:
        ...


@dataclass
class InMemoryCircuitBreaker:
    failure_threshold: int = 3
    reset_after_seconds: int = 60
    _failures: dict[str, int] = field(default_factory=dict)
    _opened_at: dict[str, float] = field(default_factory=dict)
    _last_error: dict[str, str] = field(default_factory=dict)
    _half_open: set[str] = field(default_factory=set)

    def allow_request(
        self,
        provider_id: str,
        *,
        route_id: str = "",
        adapter_type: str = "",
        error_class: str = "",
    ) -> CircuitDecision:
        key = circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        opened = self._opened_at.get(key)
        if opened is None:
            return CircuitDecision(True, key, "closed")
        now = time.monotonic()
        elapsed = now - opened
        if elapsed >= self.reset_after_seconds:
            self._half_open.add(key)
            return CircuitDecision(True, key, "half_open")
        return CircuitDecision(False, key, "open", "circuit_open", max(0.0, self.reset_after_seconds - elapsed))

    def record_success(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        key = circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        self._failures.pop(key, None)
        self._opened_at.pop(key, None)
        self._last_error.pop(key, None)
        self._half_open.discard(key)

    def record_failure(
        self,
        provider_id: str,
        *,
        route_id: str = "",
        adapter_type: str = "",
        error_class: str = "provider_error",
    ) -> None:
        key = circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        self._last_error[key] = error_class
        self._half_open.discard(key)
        if count >= self.failure_threshold:
            self._opened_at[key] = time.monotonic()

    def get_state(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> Mapping[str, object]:
        key = circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        if key in self._opened_at:
            decision = self.allow_request(provider_id, route_id=route_id, adapter_type=adapter_type)
            state = decision.state if decision.ok else "open"
        else:
            state = "closed"
        return {
            "key": key,
            "backend": "in_memory",
            "state": state,
            "failures": self._failures.get(key, 0),
            "last_error": self._last_error.get(key, ""),
        }

    def reset(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        self.record_success(provider_id, route_id=route_id, adapter_type=adapter_type)

    def open_keys(self) -> tuple[str, ...]:
        now = time.monotonic()
        return tuple(
            sorted(
                key
                for key, opened in self._opened_at.items()
                if now - opened < self.reset_after_seconds
            )
        )

    def open_provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted({key.split("|", 1)[0] for key in self.open_keys()}))


@dataclass(frozen=True)
class DistributedCircuitBreaker:
    backend_name: str = "redis-ready"
    connection_url_env: str = "FLOW_MEMORY_COMPUTE_CIRCUIT_REDIS_URL"

    def allow_request(
        self,
        provider_id: str,
        *,
        route_id: str = "",
        adapter_type: str = "",
        error_class: str = "",
    ) -> CircuitDecision:
        raise RuntimeError("distributed circuit breaker is not configured; inject a concrete backend")

    def record_success(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        raise RuntimeError("distributed circuit breaker is not configured; inject a concrete backend")

    def record_failure(
        self,
        provider_id: str,
        *,
        route_id: str = "",
        adapter_type: str = "",
        error_class: str = "provider_error",
    ) -> None:
        raise RuntimeError("distributed circuit breaker is not configured; inject a concrete backend")

    def get_state(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> Mapping[str, object]:
        return {"key": circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type), "backend": self.backend_name, "configured": False, "env": self.connection_url_env}

    def reset(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        raise RuntimeError("distributed circuit breaker is not configured; inject a concrete backend")

    def open_keys(self) -> tuple[str, ...]:
        return ()

    def open_provider_ids(self) -> tuple[str, ...]:
        return ()
@dataclass
class NoopRateLimiter:
    """Explicitly disabled limiter for tests or gateway-enforced deployments."""

    def check_limit(
        self,
        actor_id: str,
        endpoint: str,
        *,
        cost: int = 1,
        agent_id: str = "",
        workspace_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        api_key: str = "",
    ) -> RateLimitDecision:
        key = rate_limit_key(
            actor_id=actor_id,
            endpoint=endpoint,
            agent_id=agent_id,
            workspace_id=workspace_id,
            provider_id=provider_id,
            route_id=route_id,
            api_key=api_key,
        )
        return RateLimitDecision(True, key, 0, 0, 0, reason_code="disabled")

    def record_success(self, key: str) -> None:
        return None

    def record_rejection(self, key: str, reason: str) -> None:
        return None

    def get_status(self, key: str) -> Mapping[str, object]:
        return {"key": key, "backend": "none", "configured": True}


@dataclass
class NoopCircuitBreaker:
    """Explicitly disabled circuit breaker for gateway-enforced deployments."""

    def allow_request(self, provider_id: str, *, route_id: str = "", adapter_type: str = "", error_class: str = "") -> CircuitDecision:
        return CircuitDecision(True, circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type), "disabled", reason_code="disabled")

    def record_success(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        return None

    def record_failure(self, provider_id: str, *, route_id: str = "", adapter_type: str = "", error_class: str = "provider_error") -> None:
        return None

    def get_state(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> Mapping[str, object]:
        return {"key": circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type), "backend": "none", "state": "disabled"}

    def reset(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        return None

    def open_keys(self) -> tuple[str, ...]:
        return ()

    def open_provider_ids(self) -> tuple[str, ...]:
        return ()


@dataclass
class RedisRateLimiter:
    """Redis-backed fixed-window limiter for multi-node deployments.

    The Redis client is optional and injected in tests; production imports the
    redis package lazily. Fail-closed is the default production posture.
    """

    redis_url: str
    prefix: str = "flow-memory:compute-market"
    default_limit: int = 60
    window_seconds: int = 60
    fail_closed: bool = True
    route_limits: Mapping[str, int] = field(default_factory=dict)
    require_tls: bool = False
    verify_tls: bool = True
    client: Any | None = None

    def check_limit(
        self,
        actor_id: str,
        endpoint: str,
        *,
        cost: int = 1,
        agent_id: str = "",
        workspace_id: str = "",
        provider_id: str = "",
        route_id: str = "",
        api_key: str = "",
    ) -> RateLimitDecision:
        key = self._redis_key(
            rate_limit_key(
                actor_id=actor_id,
                endpoint=endpoint,
                agent_id=agent_id,
                workspace_id=workspace_id,
                provider_id=provider_id,
                route_id=route_id,
                api_key=api_key,
            )
        )
        limit = int(self.route_limits.get(endpoint, self.default_limit))
        try:
            redis_client = self._client()
            count = int(redis_client.incrby(key, max(1, int(cost))))
            if count == max(1, int(cost)):
                redis_client.expire(key, self.window_seconds)
            ttl = _redis_ttl(redis_client, key, self.window_seconds)
        except Exception:
            if self.fail_closed:
                return RateLimitDecision(
                    False,
                    key,
                    limit,
                    0,
                    time.monotonic() + self.window_seconds,
                    self.window_seconds,
                    "rate_limit_backend_unavailable",
                )
            return RateLimitDecision(
                True,
                key,
                limit,
                limit,
                time.monotonic(),
                0,
                "rate_limit_backend_fail_open",
            )
        remaining = max(0, limit - count)
        if count > limit:
            return RateLimitDecision(False, key, limit, remaining, time.monotonic() + ttl, ttl, "rate_limited")
        return RateLimitDecision(True, key, limit, remaining, time.monotonic() + ttl, 0)

    def record_success(self, key: str) -> None:
        try:
            redis_client = self._client()
            success_key = f"{key}:successes"
            redis_client.incrby(success_key, 1)
            redis_client.expire(success_key, self.window_seconds)
        except Exception:
            return None

    def record_rejection(self, key: str, reason: str) -> None:
        try:
            redis_client = self._client()
            redis_client.incrby(f"{key}:rejections:{reason}", 1)
            redis_client.expire(f"{key}:rejections:{reason}", self.window_seconds)
        except Exception:
            return None

    def get_status(self, key: str) -> Mapping[str, object]:
        if not self.redis_url:
            return {"key": key, "backend": "redis", "configured": False, "reason": "missing_redis_url"}
        try:
            redis_client = self._client()
            redis_client.ping()
        except Exception as exc:
            return {"key": key, "backend": "redis", "configured": False, "reason": type(exc).__name__, "fail_closed": self.fail_closed}
        return {"key": key, "backend": "redis", "configured": True, "prefix": self.prefix, "fail_closed": self.fail_closed}

    def _redis_key(self, key: str) -> str:
        return f"{self.prefix}:rate:{key}"

    def _client(self) -> Any:
        if not self.redis_url:
            raise RuntimeError("redis_url is required")
        _validate_redis_tls(self.redis_url, self.require_tls)
        if self.client is not None:
            return self.client
        try:
            import redis
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Redis rate limiting requires optional dependency: redis") from exc
        self.client = redis.Redis.from_url(self.redis_url, **_redis_client_kwargs(self.redis_url, verify_tls=self.verify_tls))
        return self.client


@dataclass
class RedisCircuitBreaker:
    """Redis-backed provider/route circuit breaker for multi-node deployments."""

    redis_url: str
    prefix: str = "flow-memory:compute-market"
    failure_threshold: int = 3
    reset_after_seconds: int = 60
    success_threshold: int = 1
    fail_closed: bool = True
    require_tls: bool = False
    verify_tls: bool = True
    client: Any | None = None

    def allow_request(self, provider_id: str, *, route_id: str = "", adapter_type: str = "", error_class: str = "") -> CircuitDecision:
        key = self._redis_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        try:
            redis_client = self._client()
            state = _redis_hgetall(redis_client, key)
            status = str(state.get("state", "closed"))
            failures = _object_to_int(state.get("failures", 0))
            opened_at = _object_to_float(state.get("opened_at", 0.0))
            now = time.monotonic()
            if status == "open" and now - opened_at >= self.reset_after_seconds:
                redis_client.hset(key, mapping={"state": "half_open", "successes": 0, "failures": failures, "opened_at": opened_at})
                redis_client.expire(key, self.reset_after_seconds * 2)
                return CircuitDecision(True, key, "half_open", retry_after_seconds=self.reset_after_seconds)
            if status == "open":
                return CircuitDecision(False, key, "open", reason_code="circuit_open", retry_after_seconds=max(0, int(self.reset_after_seconds - (now - opened_at))))
            return CircuitDecision(True, key, status)
        except Exception:
            if self.fail_closed:
                return CircuitDecision(
                    False,
                    key,
                    "open",
                    reason_code="circuit_backend_unavailable",
                    retry_after_seconds=self.reset_after_seconds,
                )
            return CircuitDecision(True, key, "fail_open", reason_code="circuit_backend_fail_open")

    def record_success(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        key = self._redis_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        try:
            redis_client = self._client()
            state = _redis_hgetall(redis_client, key)
            if str(state.get("state", "closed")) == "half_open":
                successes = _object_to_int(state.get("successes", 0)) + 1
                if successes >= self.success_threshold:
                    redis_client.delete(key)
                else:
                    redis_client.hset(key, mapping={"state": "half_open", "successes": successes, "failures": 0, "opened_at": state.get("opened_at", 0.0)})
            else:
                redis_client.delete(key)
        except Exception:
            return None

    def record_failure(self, provider_id: str, *, route_id: str = "", adapter_type: str = "", error_class: str = "provider_error") -> None:
        key = self._redis_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        try:
            redis_client = self._client()
            state = _redis_hgetall(redis_client, key)
            failures = _object_to_int(state.get("failures", 0)) + 1
            status = "open" if failures >= self.failure_threshold else "closed"
            mapping = {
                "state": status,
                "failures": failures,
                "last_reason": error_class,
                "opened_at": time.monotonic() if status == "open" else _object_to_float(state.get("opened_at", 0.0)),
                "successes": 0,
            }
            redis_client.hset(key, mapping=mapping)
            redis_client.expire(key, self.reset_after_seconds * 2)
        except Exception:
            return None

    def get_state(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> Mapping[str, object]:
        key = self._redis_key(provider_id, route_id=route_id, adapter_type=adapter_type)
        if not self.redis_url:
            return {"key": key, "backend": "redis", "configured": False, "reason": "missing_redis_url"}
        try:
            redis_client = self._client()
            redis_client.ping()
            state = _redis_hgetall(redis_client, key)
        except Exception as exc:
            return {"key": key, "backend": "redis", "configured": False, "reason": type(exc).__name__, "fail_closed": self.fail_closed}
        return {"key": key, "backend": "redis", "configured": True, **state}

    def reset(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> None:
        try:
            self._client().delete(self._redis_key(provider_id, route_id=route_id, adapter_type=adapter_type))
        except Exception:
            return None

    def open_keys(self) -> tuple[str, ...]:
        if not self.redis_url:
            return ()
        try:
            redis_client = self._client()
            prefix = f"{self.prefix}:circuit:"
            keys: list[str] = []
            for raw_key in _redis_scan_iter(redis_client, f"{prefix}*"):
                key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
                state = _redis_hgetall(redis_client, key)
                if str(state.get("state", "closed")) != "open":
                    continue
                logical_key = key[len(prefix) :] if key.startswith(prefix) else key
                keys.append(logical_key)
            return tuple(sorted(keys))
        except Exception as exc:
            if self.fail_closed:
                raise RuntimeError("circuit_backend_unavailable") from exc
            return ()

    def open_provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted({key.split("|", 1)[0] for key in self.open_keys() if key}))

    def _redis_key(self, provider_id: str, *, route_id: str = "", adapter_type: str = "") -> str:
        return f"{self.prefix}:circuit:{circuit_key(provider_id, route_id=route_id, adapter_type=adapter_type)}"

    def _client(self) -> Any:
        if not self.redis_url:
            raise RuntimeError("redis_url is required")
        _validate_redis_tls(self.redis_url, self.require_tls)
        if self.client is not None:
            return self.client
        try:
            import redis
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Redis circuit breaking requires optional dependency: redis") from exc
        self.client = redis.Redis.from_url(self.redis_url, **_redis_client_kwargs(self.redis_url, verify_tls=self.verify_tls))
        return self.client


def create_rate_limiter(config: Any) -> RateLimiter:
    enabled = bool(getattr(config, "rate_limits_enabled", True)) and bool(getattr(config, "rate_limit_enabled", True))
    backend = str(getattr(config, "rate_limit_backend", "memory")).strip().lower()
    if not enabled or backend == "none":
        return NoopRateLimiter()
    if backend in {"memory", "in_memory"}:
        return InMemoryRateLimiter()
    if backend == "redis":
        redis_url = str(getattr(config, "redis_url", ""))
        return RedisRateLimiter(
            redis_url=redis_url,
            prefix=str(getattr(config, "redis_prefix", "flow-memory:compute-market")),
            fail_closed=bool(getattr(config, "rate_limit_fail_closed", True)),
            require_tls=bool(getattr(config, "require_managed_redis_in_production", False))
            and not (bool(getattr(config, "allow_internal_redis_in_production", False)) and redis_url.startswith("redis://")),
        )
    return DistributedRateLimiter(backend_name=backend)


def create_circuit_breaker(config: Any) -> CircuitBreaker:
    enabled = bool(getattr(config, "circuit_breaker_enabled", True))
    backend = str(getattr(config, "circuit_breaker_backend", "memory")).strip().lower()
    if not enabled or backend == "none":
        return NoopCircuitBreaker()
    if backend in {"memory", "in_memory"}:
        return InMemoryCircuitBreaker()
    if backend == "redis":
        redis_url = str(getattr(config, "redis_url", ""))
        return RedisCircuitBreaker(
            redis_url=redis_url,
            prefix=str(getattr(config, "redis_prefix", "flow-memory:compute-market")),
            fail_closed=bool(getattr(config, "circuit_breaker_fail_closed", True)),
            require_tls=bool(getattr(config, "require_managed_redis_in_production", False))
            and not (bool(getattr(config, "allow_internal_redis_in_production", False)) and redis_url.startswith("redis://")),
        )
    return DistributedCircuitBreaker(backend_name=backend)


def _validate_redis_tls(redis_url: str, require_tls: bool) -> None:
    if require_tls and not redis_url.startswith("rediss://"):
        raise RuntimeError("managed Redis requires a rediss:// TLS URL")


def _redis_client_kwargs(redis_url: str, *, verify_tls: bool = True) -> dict[str, object]:
    kwargs: dict[str, object] = {"decode_responses": True}
    if verify_tls and redis_url.startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED
    return kwargs


def _redis_ttl(redis_client: Any, key: str, default_ttl: int) -> int:
    ttl = int(redis_client.ttl(key))
    return default_ttl if ttl < 0 else ttl


def _redis_hgetall(redis_client: Any, key: str) -> Mapping[str, object]:
    result = redis_client.hgetall(key)
    return result if isinstance(result, Mapping) else {}

def _redis_scan_iter(redis_client: Any, pattern: str) -> tuple[object, ...]:
    scan_iter = getattr(redis_client, "scan_iter", None)
    if callable(scan_iter):
        return tuple(scan_iter(match=pattern))
    keys = getattr(redis_client, "keys", None)
    if callable(keys):
        return tuple(keys(pattern))
    return ()


def _object_to_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _object_to_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def rate_limit_key(
    *,
    actor_id: str,
    endpoint: str,
    agent_id: str = "",
    workspace_id: str = "",
    provider_id: str = "",
    route_id: str = "",
    api_key: str = "",
) -> str:
    return "|".join(
        (
            actor_id or "anonymous",
            agent_id or "agent:*",
            workspace_id or "workspace:*",
            endpoint,
            provider_id or "provider:*",
            route_id or "route:*",
            api_key or "api-key:*",
        )
    )


def circuit_key(provider_id: str, *, route_id: str = "", adapter_type: str = "") -> str:
    return "|".join((provider_id or "provider:*", route_id or "route:*", adapter_type or "adapter:*"))
