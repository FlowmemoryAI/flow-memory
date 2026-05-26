from __future__ import annotations

import json
from typing import Any

import scripts.validate_compute_market_live_infra as validator


def _clear_live_env(monkeypatch: Any) -> None:
    for name in (*validator.POSTGRES_ENV_NAMES, *validator.REDIS_ENV_NAMES):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION", raising=False)


def test_live_infra_validator_blocks_missing_urls(monkeypatch: Any, capsys: Any) -> None:
    _clear_live_env(monkeypatch)

    exit_code = validator.main([])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "blocked_missing_live_infra"
    assert "FLOW_MEMORY_TEST_POSTGRES_URL or FLOW_MEMORY_COMPUTE_DATABASE_URL" in payload["missing_values"]
    assert "FLOW_MEMORY_TEST_REDIS_URL or FLOW_MEMORY_COMPUTE_REDIS_URL" in payload["missing_values"]


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
