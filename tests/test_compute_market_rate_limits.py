from __future__ import annotations

import ssl
import time

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.controls import (
    DistributedCircuitBreaker,
    DistributedRateLimiter,
    InMemoryCircuitBreaker,
    InMemoryRateLimiter,
    RedisCircuitBreaker,
    RedisRateLimiter,
    _redis_client_kwargs,
    create_circuit_breaker,
    create_rate_limiter,
)
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import ComputeMarketStore


def test_in_memory_rate_limiter_exceeds_and_resets_window() -> None:
    limiter = InMemoryRateLimiter(default_limit=1, window_seconds=1)
    first = limiter.check_limit("actor", "POST /compute/plan")
    second = limiter.check_limit("actor", "POST /compute/plan")

    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "rate_limited"

    time.sleep(1.05)
    assert limiter.check_limit("actor", "POST /compute/plan").ok is True


def test_circuit_breaker_opens_half_opens_and_closes_after_recovery() -> None:
    breaker = InMemoryCircuitBreaker(failure_threshold=2, reset_after_seconds=1)
    assert breaker.allow_request("provider").ok is True
    breaker.record_failure("provider", error_class="provider_timeout")
    breaker.record_failure("provider", error_class="invalid_response")

    opened = breaker.allow_request("provider")
    assert opened.ok is False
    assert opened.state == "open"
    assert breaker.get_state("provider")["last_error"] == "invalid_response"

    time.sleep(1.05)
    half_open = breaker.allow_request("provider")
    assert half_open.ok is True
    assert half_open.state == "half_open"

    breaker.record_success("provider")
    assert breaker.allow_request("provider").state == "closed"


def test_planning_denies_open_circuit_provider_and_audits_event() -> None:
    breaker = InMemoryCircuitBreaker(failure_threshold=1, reset_after_seconds=60)
    breaker.record_failure("market-token-provider", error_class="provider_timeout")
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"),
        circuit_breaker=breaker,
    )

    result = service.plan(
        {
            "task": "open circuit provider should not be selected",
            "provider_constraints": ("market-token-provider",),
            "policy": {"marketplace_only": True},
        }
    )

    plan = result["compute_plan"]
    assert plan["ok"] is False
    assert plan["selected_route"] is None
    assert "provider_denied" in plan["fail_closed_errors"]
    audit_actions = tuple(event["action"] for event in service.audit({})["audit_events"])
    assert "compute.provider.circuit_open" in audit_actions


def test_service_rate_limit_returns_structured_error_and_audit_event() -> None:
    limiter = InMemoryRateLimiter(default_limit=1, window_seconds=60)
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(database_url=":memory:", compute_market_mode="test"),
        rate_limiter=limiter,
    )

    first = service.plan({"task": "first", "actor_id": "actor-rate"})
    second = service.plan({"task": "second", "actor_id": "actor-rate"})

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["error"]["error_category"] == "rate_limited"
    assert any(event["action"] == "compute.rate_limited" for event in service.audit({})["audit_events"])


def test_distributed_scaffolds_are_explicitly_not_configured() -> None:
    limiter = DistributedRateLimiter()
    circuit = DistributedCircuitBreaker()

    assert limiter.get_status("k")["configured"] is False
    assert circuit.get_state("provider")["configured"] is False


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.values: dict[str, int] = {}
        self.hashes: dict[str, dict[str, object]] = {}
        self.expirations: dict[str, int] = {}

    def ping(self) -> bool:
        if self.fail:
            raise RuntimeError("redis unavailable")
        return True

    def incrby(self, key: str, amount: int) -> int:
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.values[key] = self.values.get(key, 0) + amount
        return self.values[key]

    def expire(self, key: str, seconds: int) -> bool:
        self.expirations[key] = seconds
        return True

    def ttl(self, key: str) -> int:
        return self.expirations.get(key, -1)

    def hgetall(self, key: str) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("redis unavailable")
        return dict(self.hashes.get(key, {}))

    def hset(self, key: str, mapping: dict[str, object]) -> int:
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.hashes[key] = {**self.hashes.get(key, {}), **mapping}
        return len(mapping)

    def delete(self, key: str) -> int:
        self.hashes.pop(key, None)
        self.values.pop(key, None)
        return 1


def test_redis_rate_limiter_uses_atomic_counter_and_factory() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter("redis://localhost:6379/0", default_limit=1, window_seconds=30, client=redis)

    first = limiter.check_limit("actor", "POST /compute/plan")
    second = limiter.check_limit("actor", "POST /compute/plan")

    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "rate_limited"
    assert limiter.get_status("readiness")["configured"] is True
    assert isinstance(
        create_rate_limiter(
            ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="test",
                rate_limit_backend="redis",
                redis_url="redis://localhost:6379/0",
            )
        ),
        RedisRateLimiter,
    )

def test_redis_rate_limiter_route_limits_success_counter_and_tls_kwargs() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(
        "redis://localhost:6379/0",
        default_limit=10,
        route_limits={"POST /compute/plan": 1},
        window_seconds=30,
        client=redis,
    )

    first = limiter.check_limit("actor", "POST /compute/plan")
    second = limiter.check_limit("actor", "POST /compute/plan")
    other_route = limiter.check_limit("actor", "GET /compute/health")
    limiter.record_success(first.key)

    assert first.ok is True
    assert first.limit == 1
    assert second.ok is False
    assert second.reason_code == "rate_limited"
    assert other_route.ok is True
    assert other_route.limit == 10
    assert redis.values[f"{first.key}:successes"] == 1
    assert redis.expirations[f"{first.key}:successes"] == 30
    assert _redis_client_kwargs("rediss://cache.example:6379/0")["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert "ssl_cert_reqs" not in _redis_client_kwargs("rediss://cache.example:6379/0", verify_tls=False)


def test_redis_controls_fail_closed_when_tls_is_required_for_plain_url() -> None:
    limiter = RedisRateLimiter("redis://localhost:6379/0", require_tls=True, client=FakeRedis())
    breaker = RedisCircuitBreaker("redis://localhost:6379/0", require_tls=True, client=FakeRedis())

    rate_decision = limiter.check_limit("actor", "POST /compute/plan")
    circuit_decision = breaker.allow_request("provider")

    assert rate_decision.ok is False
    assert rate_decision.reason_code == "rate_limit_backend_unavailable"
    assert limiter.get_status("readiness")["configured"] is False
    assert circuit_decision.ok is False
    assert circuit_decision.reason_code == "circuit_backend_unavailable"
    assert breaker.get_state("provider")["configured"] is False

def test_redis_controls_allow_explicit_internal_render_redis_without_tls_requirement() -> None:
    config = ComputeMarketConfig(
        rate_limit_backend="redis",
        circuit_breaker_backend="redis",
        redis_url="redis://render-internal-redis:6379/0",
        require_managed_redis_in_production=True,
        allow_internal_redis_in_production=True,
    )

    limiter = create_rate_limiter(config)
    breaker = create_circuit_breaker(config)

    assert isinstance(limiter, RedisRateLimiter)
    assert limiter.require_tls is False
    assert isinstance(breaker, RedisCircuitBreaker)
    assert breaker.require_tls is False



def test_redis_rate_limiter_shares_state_across_instances() -> None:
    redis = FakeRedis()
    limiter_a = RedisRateLimiter("redis://localhost:6379/0", default_limit=2, window_seconds=30, client=redis)
    limiter_b = RedisRateLimiter("redis://localhost:6379/0", default_limit=2, window_seconds=30, client=redis)

    first = limiter_a.check_limit("actor", "POST /compute/plan", api_key="tenant-key")
    second = limiter_b.check_limit("actor", "POST /compute/plan", api_key="tenant-key")
    third = limiter_a.check_limit("actor", "POST /compute/plan", api_key="tenant-key")

    assert first.ok is True
    assert second.ok is True
    assert second.remaining == 0
    assert third.ok is False
    assert third.reason_code == "rate_limited"


def test_redis_rate_limiter_fail_closed_and_fail_open_modes() -> None:
    fail_closed = RedisRateLimiter("redis://localhost", fail_closed=True, client=FakeRedis(fail=True))
    fail_open = RedisRateLimiter("redis://localhost", fail_closed=False, client=FakeRedis(fail=True))

    assert fail_closed.check_limit("actor", "POST /compute/plan").ok is False
    assert fail_closed.check_limit("actor", "POST /compute/plan").reason_code == "rate_limit_backend_unavailable"
    assert fail_open.check_limit("actor", "POST /compute/plan").ok is True
    assert fail_open.check_limit("actor", "POST /compute/plan").reason_code == "rate_limit_backend_fail_open"


def test_redis_circuit_breaker_opens_and_factory_selects_backend() -> None:
    redis = FakeRedis()
    breaker = RedisCircuitBreaker("redis://localhost:6379/0", failure_threshold=1, reset_after_seconds=60, client=redis)

    assert breaker.allow_request("provider").ok is True
    breaker.record_failure("provider", error_class="provider_timeout")
    opened = breaker.allow_request("provider")

    assert opened.ok is False
    assert opened.state == "open"
    assert opened.reason_code == "circuit_open"
    assert breaker.get_state("provider")["configured"] is True
    assert isinstance(
        create_circuit_breaker(
            ComputeMarketConfig(
                database_url=":memory:",
                compute_market_mode="test",
                circuit_breaker_backend="redis",
                redis_url="redis://localhost:6379/0",
            )
        ),
        RedisCircuitBreaker,
    )


def test_redis_factories_require_tls_when_managed_redis_is_required() -> None:
    config = ComputeMarketConfig(
        database_url=":memory:",
        compute_market_mode="test",
        rate_limit_backend="redis",
        circuit_breaker_backend="redis",
        redis_url="redis://localhost:6379/0",
        require_managed_redis_in_production=True,
    )
    limiter = create_rate_limiter(config)
    breaker = create_circuit_breaker(config)

    assert isinstance(limiter, RedisRateLimiter)
    assert isinstance(breaker, RedisCircuitBreaker)
    assert limiter.check_limit("actor", "POST /compute/plan").reason_code == "rate_limit_backend_unavailable"
    assert breaker.allow_request("provider").reason_code == "circuit_backend_unavailable"


def test_redis_circuit_breaker_recovers_across_instances_after_half_open_success() -> None:
    redis = FakeRedis()
    breaker_a = RedisCircuitBreaker("redis://localhost:6379/0", failure_threshold=1, reset_after_seconds=0, client=redis)
    breaker_b = RedisCircuitBreaker("redis://localhost:6379/0", failure_threshold=1, reset_after_seconds=0, client=redis)

    breaker_a.record_failure("provider", route_id="route", error_class="provider_timeout")
    half_open = breaker_b.allow_request("provider", route_id="route")
    breaker_b.record_success("provider", route_id="route")

    assert half_open.ok is True
    assert half_open.state == "half_open"
    assert breaker_a.allow_request("provider", route_id="route").state == "closed"


def test_redis_circuit_breaker_reopens_across_instances_after_half_open_failure() -> None:
    redis = FakeRedis()
    breaker_a = RedisCircuitBreaker("redis://localhost:6379/0", failure_threshold=1, reset_after_seconds=60, client=redis)
    breaker_b = RedisCircuitBreaker("redis://localhost:6379/0", failure_threshold=1, reset_after_seconds=60, client=redis)

    breaker_a.record_failure("provider", route_id="route", error_class="provider_timeout")
    circuit_key = next(iter(redis.hashes))
    redis.hashes[circuit_key]["opened_at"] = time.monotonic() - 61
    half_open = breaker_b.allow_request("provider", route_id="route")
    breaker_b.record_failure("provider", route_id="route", error_class="half_open_failure")
    reopened = breaker_a.allow_request("provider", route_id="route")
    state = breaker_a.get_state("provider", route_id="route")

    assert half_open.ok is True
    assert half_open.state == "half_open"
    assert reopened.ok is False
    assert reopened.state == "open"
    assert reopened.reason_code == "circuit_open"
    assert state["state"] == "open"
    assert state["last_reason"] == "half_open_failure"


def test_redis_circuit_breaker_fail_closed_and_fail_open_modes() -> None:
    fail_closed = RedisCircuitBreaker("redis://localhost", fail_closed=True, client=FakeRedis(fail=True))
    fail_open = RedisCircuitBreaker("redis://localhost", fail_closed=False, client=FakeRedis(fail=True))

    assert fail_closed.allow_request("provider").ok is False
    assert fail_closed.allow_request("provider").reason_code == "circuit_backend_unavailable"
    assert fail_open.allow_request("provider").ok is True
    assert fail_open.allow_request("provider").reason_code == "circuit_backend_fail_open"


def test_readiness_reports_missing_redis_when_required() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limit_backend="redis",
            circuit_breaker_backend="redis",
            redis_url="",
        ),
    )

    readiness = service.readiness()

    assert readiness["ready"] is False
    assert "rate_limiter_unavailable" in readiness["readiness_failures"]
    assert "circuit_breaker_unavailable" in readiness["readiness_failures"]


def test_admin_redis_diagnostics_probe_shared_limiter_and_circuit_state() -> None:
    redis = FakeRedis()
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limit_backend="redis",
            circuit_breaker_backend="redis",
            redis_url="redis://localhost:6379/0",
        ),
        rate_limiter=RedisRateLimiter("redis://localhost:6379/0", default_limit=100, client=redis),
        circuit_breaker=RedisCircuitBreaker("redis://localhost:6379/0", failure_threshold=3, client=redis),
    )

    diagnostics = service.admin_redis_diagnostics({"request_id": "redis-diagnostic-test"})

    assert diagnostics["ok"] is True
    assert diagnostics["expected_redis"] is True
    assert diagnostics["rate_limiter"]["configured"] is True
    assert diagnostics["circuit_breaker"]["configured"] is True
    assert diagnostics["rate_limit_probe"]["ok"] is True
    assert diagnostics["rate_limit_probe"]["second"]["reason_code"] == "rate_limited"
    assert diagnostics["circuit_breaker_probe"]["ok"] is True
    assert diagnostics["circuit_breaker_probe"]["opened"]["reason_code"] == "circuit_open"


def test_admin_redis_diagnostics_fails_when_required_backend_is_unavailable() -> None:
    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="test",
            rate_limit_backend="redis",
            circuit_breaker_backend="redis",
            redis_url="redis://localhost:6379/0",
        ),
        rate_limiter=RedisRateLimiter("redis://localhost:6379/0", fail_closed=True, client=FakeRedis(fail=True)),
        circuit_breaker=RedisCircuitBreaker("redis://localhost:6379/0", fail_closed=True, client=FakeRedis(fail=True)),
    )

    diagnostics = service.admin_redis_diagnostics({"request_id": "redis-unavailable-test"})

    assert diagnostics["ok"] is False
    assert diagnostics["rate_limit_probe"]["ok"] is False
    assert diagnostics["rate_limit_probe"]["first"]["reason_code"] == "rate_limit_backend_unavailable"
    assert diagnostics["circuit_breaker_probe"]["ok"] is False
    assert diagnostics["circuit_breaker_probe"]["before"]["reason_code"] == "circuit_backend_unavailable"
