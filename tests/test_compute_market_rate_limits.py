from __future__ import annotations

import time

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.controls import (
    DistributedCircuitBreaker,
    DistributedRateLimiter,
    InMemoryCircuitBreaker,
    InMemoryRateLimiter,
    RedisCircuitBreaker,
    RedisRateLimiter,
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
