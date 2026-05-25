from __future__ import annotations

import os
from time import monotonic_ns

import pytest

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.controls import RedisCircuitBreaker, RedisRateLimiter
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import deterministic_id
from flow_memory.compute_market.storage_backends import PostgresComputeMarketStore


def test_postgres_live_integration_when_url_is_configured() -> None:
    database_url = os.environ.get("FLOW_MEMORY_TEST_POSTGRES_URL") or os.environ.get("FLOW_MEMORY_COMPUTE_DATABASE_URL")
    if not database_url:
        pytest.skip("set FLOW_MEMORY_TEST_POSTGRES_URL to run live PostgreSQL validation")
    assert database_url is not None

    config = ComputeMarketConfig(
        database_url=database_url,
        storage_backend="postgres",
        postgres_ssl_mode=os.environ.get("FLOW_MEMORY_COMPUTE_POSTGRES_SSL_MODE", "require"),
        require_managed_sql_in_production=True,
        redis_url="",
        rate_limit_backend="none",
        circuit_breaker_backend="none",
        audit_export_uri="configured-by-test",
        audit_export_required=True,
        provider_contracts_required=False,
    )
    service = ComputeMarketService(config=config)
    try:
        result = service.plan(
            {
                "task": "live postgres integration verification",
                "idempotency_key": deterministic_id("live_pg", {"run": str(monotonic_ns())}),
                "dry_run": True,
            }
        )
        readiness = service.readiness()
    finally:
        service.store.close()

    assert isinstance(service.store, PostgresComputeMarketStore)
    assert result["ok"] is True
    assert readiness["ready"] is True
    assert readiness["storage"]["backend"] == "postgresql"
    assert readiness["migration_status"]["current"] is True
    assert readiness["audit_chain"]["ok"] is True


def test_redis_live_integration_when_url_is_configured() -> None:
    redis_url = os.environ.get("FLOW_MEMORY_TEST_REDIS_URL") or os.environ.get("FLOW_MEMORY_COMPUTE_REDIS_URL")
    if not redis_url:
        pytest.skip("set FLOW_MEMORY_TEST_REDIS_URL to run live Redis validation")
    assert redis_url is not None

    prefix = f"flow-memory:test:{monotonic_ns()}"
    limiter = RedisRateLimiter(redis_url, prefix=prefix, default_limit=1, window_seconds=30)
    breaker = RedisCircuitBreaker(redis_url, prefix=prefix, failure_threshold=1, reset_after_seconds=30)

    first = limiter.check_limit("actor", "POST /compute/plan")
    second = limiter.check_limit("actor", "POST /compute/plan")
    breaker.record_failure("provider", error_class="provider_timeout")
    opened = breaker.allow_request("provider")

    assert limiter.get_status("readiness")["configured"] is True
    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "rate_limited"
    assert breaker.get_state("provider")["configured"] is True
    assert opened.ok is False
    assert opened.reason_code == "circuit_open"
