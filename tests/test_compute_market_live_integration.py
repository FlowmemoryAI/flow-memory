from __future__ import annotations

import os
from time import monotonic_ns

import pytest

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.controls import RedisCircuitBreaker, RedisRateLimiter
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import ComputeMarketStore, deterministic_id
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
        run_id = str(monotonic_ns())
        idempotency_key = deterministic_id("live_pg", {"run": run_id})
        result = service.plan(
            {
                "task": "live postgres integration verification",
                "idempotency_key": idempotency_key,
                "dry_run": True,
            }
        )
        replay = service.plan(
            {
                "task": "live postgres integration replay verification",
                "idempotency_key": idempotency_key,
                "dry_run": True,
            }
        )
        migration_second = service.store.migrate()
        schema = service.store.schema_verification()
        production = service.store.production_readiness_check()
        job_id = deterministic_id("live_pg_job", {"run": run_id})
        service.store.put_record(
            "compute_job",
            job_id,
            {"job_id": job_id, "status": "queued", "created_by": "live_postgres_validation"},
            status="queued",
            idempotency_key=job_id,
        )
        updated = service.store.put_record_if_state(
            "compute_job",
            job_id,
            ("queued",),
            {"job_id": job_id, "status": "running", "created_by": "live_postgres_validation"},
            status="running",
            idempotency_key=job_id,
        )
        stale_update = service.store.put_record_if_state(
            "compute_job",
            job_id,
            ("queued",),
            {"job_id": job_id, "status": "failed", "created_by": "live_postgres_validation"},
            status="failed",
            idempotency_key=job_id,
        )
        stored_job = service.store.find_by_idempotency("compute_job", job_id)
        job_count = service.store.count_records("compute_job")
        readiness = service.readiness()
    finally:
        service.store.close()

    assert isinstance(service.store, PostgresComputeMarketStore)
    assert result["ok"] is True
    assert readiness["ready"] is True
    assert readiness["storage"]["backend"] == "postgresql"
    assert readiness["migration_status"]["current"] is True
    assert readiness["audit_chain"]["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["compute_plan"]["decision_id"] == result["compute_plan"]["decision_id"]
    assert migration_second.applied == ()
    assert schema["ok"] is True
    assert schema["missing_tables"] == ()
    assert schema["missing_indexes"] == ()
    assert schema["advisory_lock_probe"]["acquired"] is True
    assert production["production_ready"] is True
    assert updated is True
    assert stale_update is False
    assert stored_job is not None and stored_job["job_id"] == job_id
    assert job_count >= 1


def test_redis_live_integration_when_url_is_configured() -> None:
    redis_url = os.environ.get("FLOW_MEMORY_TEST_REDIS_URL") or os.environ.get("FLOW_MEMORY_COMPUTE_REDIS_URL")
    if not redis_url:
        pytest.skip("set FLOW_MEMORY_TEST_REDIS_URL to run live Redis validation")
    assert redis_url is not None

    require_managed_redis = os.environ.get("FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if require_managed_redis:
        assert redis_url.startswith("rediss://")

    prefix = f"flow-memory:test:{monotonic_ns()}"
    limiter_a = RedisRateLimiter(redis_url, prefix=prefix, default_limit=1, window_seconds=30)
    limiter_b = RedisRateLimiter(redis_url, prefix=prefix, default_limit=1, window_seconds=30)
    breaker_a = RedisCircuitBreaker(redis_url, prefix=prefix, failure_threshold=1, reset_after_seconds=0)
    breaker_b = RedisCircuitBreaker(redis_url, prefix=prefix, failure_threshold=1, reset_after_seconds=0)

    first = limiter_a.check_limit("actor", "POST /compute/plan")
    second = limiter_b.check_limit("actor", "POST /compute/plan")
    breaker_a.record_failure("provider", error_class="provider_timeout")
    opened = breaker_b.allow_request("provider")
    breaker_b.record_success("provider")
    recovered = breaker_a.allow_request("provider")

    service = ComputeMarketService(
        store=ComputeMarketStore(":memory:"),
        config=ComputeMarketConfig(
            database_url=":memory:",
            compute_market_mode="production_planning" if require_managed_redis else "test",
            rate_limit_backend="redis",
            circuit_breaker_backend="redis",
            redis_url=redis_url,
            redis_prefix=prefix,
            require_managed_redis_in_production=require_managed_redis,
        ),
        rate_limiter=RedisRateLimiter(redis_url, prefix=prefix, default_limit=100),
        circuit_breaker=RedisCircuitBreaker(redis_url, prefix=prefix, failure_threshold=3),
    )
    diagnostics = service.admin_redis_diagnostics({"request_id": f"live-redis-{monotonic_ns()}"})

    assert limiter_a.get_status("readiness")["configured"] is True
    assert first.ok is True
    assert second.ok is False
    assert second.reason_code == "rate_limited"
    assert breaker_b.get_state("provider")["configured"] is True
    assert opened.ok is False
    assert opened.reason_code == "circuit_open"
    assert recovered.ok is True
    assert recovered.state == "closed"
    assert diagnostics["ok"] is True
    assert diagnostics["rate_limit_probe"]["ok"] is True
    assert diagnostics["rate_limit_probe"]["shared_state"] is True
    assert diagnostics["circuit_breaker_probe"]["ok"] is True
    assert diagnostics["circuit_breaker_probe"]["shared_state"] is True
    assert diagnostics["rate_limit_fail_closed"] is True
    assert diagnostics["circuit_breaker_fail_closed"] is True
