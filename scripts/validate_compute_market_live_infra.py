from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
import urllib.parse
from time import monotonic_ns
from typing import Any, Mapping

from flow_memory.compute_market.config import ComputeMarketConfig
from flow_memory.compute_market.controls import RedisCircuitBreaker, RedisRateLimiter
from flow_memory.compute_market.service import ComputeMarketService
from flow_memory.compute_market.storage import ComputeMarketStore, deterministic_id
from flow_memory.compute_market.storage_backends import PostgresComputeMarketStore


POSTGRES_ENV_NAMES = ("FLOW_MEMORY_TEST_POSTGRES_URL", "FLOW_MEMORY_COMPUTE_DATABASE_URL")
REDIS_ENV_NAMES = ("FLOW_MEMORY_TEST_REDIS_URL", "FLOW_MEMORY_COMPUTE_REDIS_URL")
POSTGRES_SECURE_SSL_MODES = ("require", "verify-ca", "verify-full")

REQUIRED_POSTGRES_INDEX_GROUPS: Mapping[str, tuple[str, ...]] = {
    "economic_memory_by_agent_id": ("idx_compute_economic_memory_agent",),
    "economic_memory_by_goal_id": ("idx_compute_economic_memory_goal",),
    "provider_route_lookups": (
        "idx_compute_quotes_provider",
        "idx_compute_quotes_route",
        "idx_compute_decisions_provider",
        "idx_compute_decisions_route",
        "idx_compute_quote_cache_provider",
        "idx_compute_quote_cache_route",
    ),
    "quote_expiration": ("idx_compute_quotes_expires", "idx_compute_quote_cache_expires"),
    "audit_chain_sequence": ("idx_compute_audit_events_chain",),
    "audit_event_hash": ("idx_compute_audit_events_hash",),
}


def env_value(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def is_loopback_endpoint(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").strip().strip("[]").lower().rstrip(".")
    if not host:
        return False
    if host in {"localhost", "ip6-localhost", "ip6-loopback"} or host.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(address.is_loopback or address.is_unspecified)


def required_postgres_index_evidence(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    missing = frozenset(str(item) for item in schema.get("missing_indexes", ()) if str(item))
    schema_ok = schema.get("ok") is True
    groups: dict[str, Mapping[str, Any]] = {}
    for name, indexes in REQUIRED_POSTGRES_INDEX_GROUPS.items():
        missing_for_group = tuple(index for index in indexes if index in missing)
        groups[name] = {
            "ok": schema_ok and not missing_for_group,
            "indexes": indexes,
            "missing_indexes": missing_for_group,
        }
    return {"ok": all(bool(group["ok"]) for group in groups.values()), "groups": groups}


def validate_postgres(database_url: str, *, ssl_mode: str = "require") -> Mapping[str, Any]:
    config = ComputeMarketConfig(
        database_url=database_url,
        storage_backend="postgres",
        postgres_ssl_mode=ssl_mode,
        require_managed_sql_in_production=True,
        redis_url="",
        rate_limit_backend="none",
        circuit_breaker_backend="none",
        audit_export_required=False,
        provider_contracts_required=False,
    )
    service: ComputeMarketService | None = None
    try:
        service = ComputeMarketService(config=config)
        if not isinstance(service.store, PostgresComputeMarketStore):
            return {"ok": False, "backend": service.store.storage_status().get("backend"), "error_code": "postgres_not_selected"}
        run_id = str(monotonic_ns())
        idempotency_key = deterministic_id("live_pg_validator", {"run": run_id})
        first = service.plan(
            {
                "task": "live managed Postgres infrastructure validation",
                "idempotency_key": idempotency_key,
                "dry_run": True,
            }
        )
        replay = service.plan(
            {
                "task": "live managed Postgres idempotency replay validation",
                "idempotency_key": idempotency_key,
                "dry_run": True,
            }
        )
        migration_second = service.store.migrate()
        schema = service.store.schema_verification()
        production = service.store.production_readiness_check()
        index_evidence = required_postgres_index_evidence(schema)
        readiness = service.readiness()
        job_id = deterministic_id("live_pg_validator_job", {"run": run_id})
        service.store.put_record(
            "compute_job",
            job_id,
            {"job_id": job_id, "status": "queued", "created_by": "live_infra_validator"},
            status="queued",
            idempotency_key=job_id,
        )
        updated = service.store.put_record_if_state(
            "compute_job",
            job_id,
            ("queued",),
            {"job_id": job_id, "status": "running", "created_by": "live_infra_validator"},
            status="running",
            idempotency_key=job_id,
        )
        stale_update = service.store.put_record_if_state(
            "compute_job",
            job_id,
            ("queued",),
            {"job_id": job_id, "status": "failed", "created_by": "live_infra_validator"},
            status="failed",
            idempotency_key=job_id,
        )
        stored_job = service.store.find_by_idempotency("compute_job", job_id)
        ok = all(
            (
                first.get("ok") is True,
                replay.get("idempotent_replay") is True,
                replay.get("compute_plan", {}).get("decision_id") == first.get("compute_plan", {}).get("decision_id"),
                migration_second.applied == (),
                schema.get("ok") is True,
                not schema.get("missing_tables", ()),
                not schema.get("missing_indexes", ()),
                index_evidence.get("ok") is True,
                schema.get("advisory_lock_probe", {}).get("acquired") is True,
                production.get("production_ready") is True,
                readiness.get("ready") is True,
                updated is True,
                stale_update is False,
                isinstance(stored_job, Mapping) and stored_job.get("job_id") == job_id,
            )
        )
        return {
            "ok": ok,
            "backend": "postgresql",
            "migration_second_applied": migration_second.applied,
            "schema_verification": schema,
            "required_index_evidence": index_evidence,
            "production_readiness": production,
            "readiness_failures": readiness.get("readiness_failures", ()),
            "idempotent_replay": replay.get("idempotent_replay") is True,
            "state_update_ok": updated is True and stale_update is False,
        }
    except Exception as exc:
        return {"ok": False, "backend": "postgresql", "error_code": type(exc).__name__, "message": str(exc)}
    finally:
        if service is not None:
            service.store.close()


def validate_redis(redis_url: str, *, require_tls: bool = True) -> Mapping[str, Any]:
    if require_tls and not redis_url.startswith("rediss://"):
        return {"ok": False, "backend": "redis", "error_code": "redis_tls_required", "redis_url_scheme": url_scheme(redis_url)}
    prefix = f"flow-memory:live-infra:{monotonic_ns()}"
    try:
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
                compute_market_mode="production_planning" if require_tls else "test",
                rate_limit_backend="redis",
                circuit_breaker_backend="redis",
                redis_url=redis_url,
                redis_prefix=prefix,
                require_managed_redis_in_production=require_tls,
            ),
            rate_limiter=RedisRateLimiter(redis_url, prefix=prefix, default_limit=100),
            circuit_breaker=RedisCircuitBreaker(redis_url, prefix=prefix, failure_threshold=3),
        )
        diagnostics = service.admin_redis_diagnostics({"request_id": f"live-redis-{monotonic_ns()}"})
        ok = all(
            (
                limiter_a.get_status("readiness").get("configured") is True,
                first.ok is True,
                second.ok is False,
                second.reason_code == "rate_limited",
                breaker_b.get_state("provider").get("configured") is True,
                opened.ok is False,
                opened.reason_code == "circuit_open",
                recovered.ok is True,
                recovered.state == "closed",
                diagnostics.get("ok") is True,
                diagnostics.get("rate_limit_probe", {}).get("ok") is True,
                diagnostics.get("circuit_breaker_probe", {}).get("ok") is True,
                diagnostics.get("rate_limit_fail_closed") is True,
                diagnostics.get("circuit_breaker_fail_closed") is True,
            )
        )
        return {
            "ok": ok,
            "backend": "redis",
            "redis_url_scheme": url_scheme(redis_url),
            "rate_limit_denial_reason": second.reason_code,
            "circuit_open_reason": opened.reason_code,
            "circuit_recovered": recovered.ok is True and recovered.state == "closed",
            "diagnostics": diagnostics,
        }
    except Exception as exc:
        return {"ok": False, "backend": "redis", "error_code": type(exc).__name__, "message": str(exc)}


def url_scheme(value: str) -> str:
    scheme, sep, _rest = value.partition("://")
    return scheme.lower() if sep else ""


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name, "")
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate live managed Postgres and Redis for Compute Market")
    parser.add_argument("--postgres-url", default="")
    parser.add_argument("--redis-url", default="")
    parser.add_argument("--postgres-ssl-mode", default=os.environ.get("FLOW_MEMORY_COMPUTE_POSTGRES_SSL_MODE", "require"))
    parser.add_argument("--allow-insecure-local-redis", action="store_true")
    parser.add_argument("--allow-local-postgres", action="store_true")
    args = parser.parse_args(argv)

    postgres_url = args.postgres_url.strip() or env_value(POSTGRES_ENV_NAMES)
    redis_url = args.redis_url.strip() or env_value(REDIS_ENV_NAMES)
    missing = []
    if not postgres_url:
        missing.append("FLOW_MEMORY_TEST_POSTGRES_URL or FLOW_MEMORY_COMPUTE_DATABASE_URL")
    if not redis_url:
        missing.append("FLOW_MEMORY_TEST_REDIS_URL or FLOW_MEMORY_COMPUTE_REDIS_URL")
    if missing:
        print(json.dumps({"ok": False, "status": "blocked_missing_live_infra", "missing_values": missing}, indent=2, sort_keys=True))
        return 2
    postgres_is_loopback = is_loopback_endpoint(postgres_url)
    postgres_ssl_mode = args.postgres_ssl_mode.strip().lower()
    if postgres_ssl_mode not in POSTGRES_SECURE_SSL_MODES and not (args.allow_local_postgres and postgres_is_loopback):
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "blocked_insecure_postgres",
                    "postgres_ssl_mode": postgres_ssl_mode,
                    "required_ssl_modes": POSTGRES_SECURE_SSL_MODES,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 6
    if postgres_is_loopback and not args.allow_local_postgres:
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "blocked_local_postgres",
                    "postgres_host": urllib.parse.urlparse(postgres_url).hostname or "",
                    "message": "live managed Postgres validation refuses loopback/local endpoints",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 4
    require_tls = not args.allow_insecure_local_redis and _bool_env(
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION",
        True,
    )
    if require_tls and not redis_url.startswith("rediss://"):
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "blocked_insecure_redis",
                    "redis_url_scheme": url_scheme(redis_url),
                    "required_scheme": "rediss",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 3
    if require_tls and is_loopback_endpoint(redis_url):
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "blocked_local_redis",
                    "redis_host": urllib.parse.urlparse(redis_url).hostname or "",
                    "message": "live managed Redis validation refuses loopback/local endpoints",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 5

    postgres = validate_postgres(postgres_url, ssl_mode=args.postgres_ssl_mode)
    redis = validate_redis(redis_url, require_tls=require_tls)
    ok = bool(postgres.get("ok")) and bool(redis.get("ok"))
    print(json.dumps({"ok": ok, "status": "passed" if ok else "failed", "postgres": postgres, "redis": redis}, indent=2, sort_keys=True, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
