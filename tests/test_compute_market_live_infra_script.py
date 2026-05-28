from __future__ import annotations

import json
from typing import Any

import scripts.validate_compute_market_live_infra as validator
from flow_memory.compute_market.storage import COMPUTE_RECORD_TYPES, ComputeMarketStore
from flow_memory.compute_market.storage_backends import PostgresComputeMarketStore, _POSTGRES_TABLES


def _clear_live_env(monkeypatch: Any) -> None:
    for name in (*validator.POSTGRES_ENV_NAMES, *validator.REDIS_ENV_NAMES):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION", raising=False)


class _FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.hashes: dict[str, dict[str, object]] = {}
        self.ttls: dict[str, int] = {}

    def ping(self) -> bool:
        return True

    def incrby(self, key: str, amount: int) -> int:
        self.values[key] = int(self.values.get(key, 0)) + amount
        return self.values[key]

    def expire(self, key: str, seconds: int) -> bool:
        if seconds <= 0:
            self.delete(key)
            return True
        self.ttls[key] = seconds
        return True

    def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)

    def hgetall(self, key: str) -> dict[str, object]:
        return dict(self.hashes.get(key, {}))

    def hset(self, key: str, *, mapping: dict[str, object]) -> int:
        values = self.hashes.setdefault(key, {})
        values.update(mapping)
        return len(mapping)

    def delete(self, key: str) -> int:
        existed = int(key in self.values or key in self.hashes)
        self.values.pop(key, None)
        self.hashes.pop(key, None)
        self.ttls.pop(key, None)
        return existed


def test_live_infra_validator_blocks_missing_urls(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    exit_code = validator.main([])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "blocked_missing_live_infra"
    assert "FLOW_MEMORY_TEST_POSTGRES_URL or FLOW_MEMORY_COMPUTE_DATABASE_URL" in payload["missing_values"]
    assert "FLOW_MEMORY_TEST_REDIS_URL or FLOW_MEMORY_COMPUTE_REDIS_URL" in payload["missing_values"]

def test_live_infra_validator_blocks_placeholder_urls_before_network(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    def fail_postgres(database_url: str, *, ssl_mode: str = "require") -> dict[str, object]:
        raise AssertionError(f"postgres validation should not run for {database_url!r} with {ssl_mode!r}")

    def fail_redis(redis_url: str, *, require_tls: bool = True) -> dict[str, object]:
        raise AssertionError(f"redis validation should not run for {redis_url!r} with {require_tls!r}")

    monkeypatch.setattr(validator, "validate_postgres", fail_postgres)
    monkeypatch.setattr(validator, "validate_redis", fail_redis)

    exit_code = validator.main(
        [
            "--postgres-url",
            "postgresql://flow_memory:CHANGEME_PASSWORD@managed-postgres-host/flow_memory",
            "--redis-url",
            "rediss://:CHANGEME_REDIS@managed-redis-host:6379/0",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 7
    assert payload["status"] == "blocked_placeholder_values"
    assert payload["placeholder_values"] == {
        "postgres_url": "placeholder_value_not_allowed",
        "redis_url": "placeholder_value_not_allowed",
    }



def test_live_infra_validator_reports_required_postgres_index_evidence() -> None:
    passing = validator.required_postgres_index_evidence({"ok": True, "missing_indexes": ()})
    missing = validator.required_postgres_index_evidence(
        {
            "ok": True,
            "missing_indexes": (
                "idx_compute_economic_memory_agent",
                "idx_compute_quote_cache_expires",
                "idx_compute_audit_events_hash",
            ),
        }
    )

    assert passing["ok"] is True
    assert passing["groups"]["provider_route_lookups"]["ok"] is True
    assert missing["ok"] is False
    assert missing["groups"]["economic_memory_by_agent_id"]["missing_indexes"] == (
        "idx_compute_economic_memory_agent",
    )
    assert missing["groups"]["quote_expiration"]["ok"] is False
    assert missing["groups"]["audit_event_hash"]["ok"] is False


def test_postgres_schema_sql_covers_all_compute_record_types() -> None:
    statement_by_name = {statement.name: statement.sql for statement in PostgresComputeMarketStore.schema_statements()}
    postgres_record_types = frozenset(_POSTGRES_TABLES)

    assert postgres_record_types == frozenset(COMPUTE_RECORD_TYPES)
    assert "compute_migrations" in statement_by_name
    for record_type, table_name in _POSTGRES_TABLES.items():
        assert f"{table_name}_table" in statement_by_name, record_type
        assert f"create table if not exists {table_name} " in statement_by_name[f"{table_name}_table"]
        assert f"idx_{table_name}_idempotency_unique" in statement_by_name


def test_required_postgres_index_groups_are_generated_by_schema_sql() -> None:
    generated_index_names = {
        statement.name
        for statement in PostgresComputeMarketStore.schema_statements()
        if statement.sql.lower().startswith("create index") or statement.sql.lower().startswith("create unique index")
    }

    for group_name, index_names in validator.REQUIRED_POSTGRES_INDEX_GROUPS.items():
        for index_name in index_names:
            assert index_name in generated_index_names, group_name


def test_sqlite_storage_idempotency_lookup_does_not_duplicate_replayed_record_id() -> None:
    store = ComputeMarketStore(":memory:")
    record_id = "job_live_infra_idempotency"
    idempotency_key = "idem_live_infra_idempotency"

    store.put_record(
        "compute_job",
        record_id,
        {"job_id": record_id, "status": "queued", "idempotency_key": idempotency_key},
        status="queued",
        idempotency_key=idempotency_key,
    )
    store.put_record(
        "compute_job",
        record_id,
        {"job_id": record_id, "status": "queued", "idempotency_key": idempotency_key},
        status="queued",
        idempotency_key=idempotency_key,
    )

    stored = store.find_by_idempotency("compute_job", idempotency_key)
    assert stored is not None
    assert stored["job_id"] == record_id
    assert store.count_records("compute_job") == 1


def test_live_infra_validator_blocks_plain_redis_before_network(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    exit_code = validator.main(
        [
            "--postgres-url",
            "postgresql://flow_memory:secret@db.example/flow_memory",
            "--redis-url",
            "redis://cache.example:6379/0",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert payload["status"] == "blocked_insecure_redis"
    assert payload["redis_url_scheme"] == "redis"
    assert payload["required_scheme"] == "rediss"


def test_live_infra_validator_blocks_insecure_postgres_before_network(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    exit_code = validator.main(
        [
            "--postgres-url",
            "postgresql://flow_memory:secret@db.example/flow_memory",
            "--postgres-ssl-mode",
            "disable",
            "--redis-url",
            "rediss://cache.example:6379/0",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 6
    assert payload["status"] == "blocked_insecure_postgres"
    assert payload["postgres_ssl_mode"] == "disable"
    assert "require" in payload["required_ssl_modes"]


def test_live_infra_validator_blocks_loopback_postgres_before_network(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    exit_code = validator.main(
        [
            "--postgres-url",
            "postgresql://flow_memory:secret@127.0.0.1:5432/flow_memory",
            "--redis-url",
            "rediss://cache.example:6379/0",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 4
    assert payload["status"] == "blocked_local_postgres"
    assert payload["postgres_host"] == "127.0.0.1"


def test_live_infra_validator_blocks_loopback_rediss_before_network(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    exit_code = validator.main(
        [
            "--postgres-url",
            "postgresql://flow_memory:secret@db.example/flow_memory",
            "--redis-url",
            "rediss://localhost:6379/0",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 5
    assert payload["status"] == "blocked_local_redis"
    assert payload["redis_host"] == "localhost"


def test_live_infra_validator_fail_closed_probe_reports_structured_reasons() -> None:
    probe = validator.redis_fail_closed_probe()

    assert probe["ok"] is True
    assert probe["rate_limit_reason"] == "rate_limit_backend_unavailable"
    assert probe["circuit_reason"] == "circuit_backend_unavailable"


def test_live_infra_validator_exercises_redis_shared_state_with_injected_client(monkeypatch: Any) -> None:
    redis_client = _FakeRedisClient()

    class FakeRedisRateLimiter(validator.RedisRateLimiter):  # type: ignore[misc]
        def __init__(self, redis_url: str, **kwargs: Any) -> None:
            client = kwargs.pop("client", redis_client)
            super().__init__(redis_url, **kwargs, client=client)

    class FakeRedisCircuitBreaker(validator.RedisCircuitBreaker):  # type: ignore[misc]
        def __init__(self, redis_url: str, **kwargs: Any) -> None:
            client = kwargs.pop("client", redis_client)
            super().__init__(redis_url, **kwargs, client=client)

    monkeypatch.setattr(validator, "RedisRateLimiter", FakeRedisRateLimiter)
    monkeypatch.setattr(validator, "RedisCircuitBreaker", FakeRedisCircuitBreaker)

    result = validator.validate_redis("rediss://cache.example:6379/0", require_tls=True)

    assert result["ok"] is True
    assert result["rate_limit_denial_reason"] == "rate_limited"
    assert result["circuit_open_reason"] == "circuit_open"
    assert result["circuit_recovered"] is True
    assert result["diagnostics"]["ok"] is True
    assert result["fail_closed_probe"]["ok"] is True


def test_live_infra_validator_can_run_local_insecure_redis_when_explicitly_allowed(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    _clear_live_env(monkeypatch)

    def fake_postgres(database_url: str, *, ssl_mode: str = "require") -> dict[str, object]:
        return {"ok": database_url.startswith("postgresql://"), "ssl_mode": ssl_mode}

    def fake_redis(redis_url: str, *, require_tls: bool = True) -> dict[str, object]:
        return {"ok": redis_url.startswith("redis://"), "require_tls": require_tls}

    monkeypatch.setattr(validator, "validate_postgres", fake_postgres)
    monkeypatch.setattr(validator, "validate_redis", fake_redis)

    exit_code = validator.main(
        [
            "--postgres-url",
            "postgresql://flow_memory:secret@db.example/flow_memory",
            "--redis-url",
            "redis://cache.example:6379/0",
            "--allow-insecure-local-redis",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["postgres"]["ok"] is True
    assert payload["redis"]["ok"] is True
    assert payload["redis"]["require_tls"] is False
