from __future__ import annotations

from typing import Any, Mapping

import scripts.validate_compute_market_public_buildout as validator


def _production_env_text(api_key: str = "fmk_live_test_secret") -> str:
    return (
        "\n".join(
            (
                f"FLOW_MEMORY_API_KEY={api_key}",
                "FLOW_MEMORY_API_ENABLE_NONCE_CHECK=true",
                "FLOW_MEMORY_API_NONCE_FAIL_CLOSED=true",
                "FLOW_MEMORY_API_NONCE_REQUIRE_TLS=true",
                "FLOW_MEMORY_API_NONCE_VERIFY_TLS=true",
                "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND=redis",
                "FLOW_MEMORY_API_NONCE_REDIS_PREFIX=flow-memory:api",
                "FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_METRICS_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_TRACING_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL=https://alerts.flowmemory.ai/compute-market",
                "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL=https://errors.flowmemory.ai/compute-market",
                "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED=true",
                "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL=https://otel.flowmemory.ai/v1/traces",
                "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=postgres",
                "FLOW_MEMORY_COMPUTE_DATABASE_URL=postgresql://db.example.com:5432/flow_memory",
                "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true",
                "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION=true",
                "FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND=redis",
                "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND=redis",
                "FLOW_MEMORY_COMPUTE_REDIS_URL=rediss://redis.example.com:6379/0",
                "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED=false",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=s3://flow-memory-audit/compute-market",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE=COMPLIANCE",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS=365",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION=us-east-1",
            )
        )
        + "\n"
    )


def test_public_validator_nonce_headers_are_random_per_authenticated_request(monkeypatch: Any) -> None:
    nonces = iter(("nonce-a", "nonce-b"))
    monkeypatch.setattr(validator.secrets, "token_urlsafe", lambda _size: next(nonces))
    monkeypatch.setattr(validator.time, "time", lambda: 1234567890.0)

    first = validator.nonce_headers(
        {"x-flow-memory-api-key": "prod-key", "x-flow-memory-scopes": "compute:read"},
        label="GET-json",
    )
    second = validator.nonce_headers(
        {"authorization": "Bearer token", "x-flow-memory-scopes": "compute:read"},
        label="GET-json",
    )
    unauthenticated = validator.nonce_headers({"x-flow-memory-scopes": "compute:read"}, label="GET-json")
    existing = validator.nonce_headers(
        {"x-flow-memory-api-key": "prod-key", "x-flow-memory-nonce": "caller-nonce"},
        label="GET-json",
    )

    assert first["x-flow-memory-timestamp"] == "1234567890.0"
    assert second["x-flow-memory-timestamp"] == "1234567890.0"
    assert first["x-flow-memory-nonce"] == "GET-json-nonce-a"
    assert second["x-flow-memory-nonce"] == "GET-json-nonce-b"
    assert first["x-flow-memory-nonce"] != second["x-flow-memory-nonce"]
    assert "x-flow-memory-nonce" not in unauthenticated
    assert existing["x-flow-memory-nonce"] == "caller-nonce"
    assert "x-flow-memory-timestamp" not in existing


def test_public_buildout_main_blocks_loopback_public_url(tmp_path: Any) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text("FLOW_MEMORY_API_KEY=prod-key\n", encoding="utf-8")

    try:
        validator.main(["--api-url", "https://127.0.0.1:8443", "--env-file", str(env_file)])
    except SystemExit as exc:
        assert "public_url_must_use_global_host" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted a loopback public URL")

def test_public_buildout_main_blocks_placeholder_api_key_before_network(tmp_path: Any, monkeypatch: Any) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text("FLOW_MEMORY_API_KEY=CHANGEME-high-entropy-api-key\n", encoding="utf-8")

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        assert "api_key_placeholder_not_allowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted a placeholder API key")

def test_public_buildout_main_blocks_weak_api_key_before_network(tmp_path: Any, monkeypatch: Any) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text("FLOW_MEMORY_API_KEY=prod-key\n", encoding="utf-8")

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        assert "api_key_weak_value_not_allowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted a weak API key")

def test_public_buildout_main_blocks_missing_live_prerequisites_before_network(
    tmp_path: Any, monkeypatch: Any
) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text("FLOW_MEMORY_API_KEY=fmk_live_test_secret\n", encoding="utf-8")

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        message = str(exc)
        assert "production environment prerequisites failed" in message
        assert "FLOW_MEMORY_COMPUTE_DATABASE_URL" in message
        assert "FLOW_MEMORY_COMPUTE_REDIS_URL" in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted missing production prerequisites")


def test_public_buildout_main_blocks_insecure_live_prerequisites_before_network(
    tmp_path: Any, monkeypatch: Any
) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(
        _production_env_text().replace("rediss://redis.example.com:6379/0", "redis://redis.example.com:6379/0"),
        encoding="utf-8",
    )

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        message = str(exc)
        assert "FLOW_MEMORY_COMPUTE_REDIS_URL" in message
        assert '"expected": "rediss"' in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted insecure production prerequisites")


def test_public_buildout_main_blocks_missing_nonce_prerequisites_before_network(
    tmp_path: Any, monkeypatch: Any
) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(
        _production_env_text().replace("FLOW_MEMORY_API_ENABLE_NONCE_CHECK=true\n", ""),
        encoding="utf-8",
    )

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        message = str(exc)
        assert "FLOW_MEMORY_API_ENABLE_NONCE_CHECK" in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted missing nonce prerequisites")


def test_public_buildout_main_blocks_non_redis_nonce_replay_backend_before_network(
    tmp_path: Any, monkeypatch: Any
) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(
        _production_env_text().replace("FLOW_MEMORY_API_NONCE_REPLAY_BACKEND=redis\n", "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND=memory\n"),
        encoding="utf-8",
    )

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        message = str(exc)
        assert "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND" in message
        assert '"expected": "redis"' in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted non-Redis nonce replay backend")

def test_public_buildout_main_blocks_missing_observability_sinks_before_network(
    tmp_path: Any, monkeypatch: Any
) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(
        _production_env_text()
        .replace("FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL=https://alerts.flowmemory.ai/compute-market\n", "")
        .replace("FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL=https://errors.flowmemory.ai/compute-market\n", "")
        .replace("FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL=https://otel.flowmemory.ai/v1/traces\n", ""),
        encoding="utf-8",
    )

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        message = str(exc)
        assert "production environment prerequisites failed" in message
        assert "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL" in message
        assert "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL" in message
        assert "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL" in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted missing observability sinks")



def test_public_buildout_main_blocks_http_observability_sink_before_network(
    tmp_path: Any, monkeypatch: Any
) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(
        _production_env_text() + "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL=http://alerts.example.com/hook\n",
        encoding="utf-8",
    )

    def fail_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        message = str(exc)
        assert "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL" in message
        assert '"expected": "https"' in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted insecure observability sink")


def test_public_buildout_main_blocks_incomplete_gateway_jwt_before_network(tmp_path: Any, monkeypatch: Any) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(
        "\n".join(
            (
                "FLOW_MEMORY_API_KEY=fmk_live_test_secret",
                "FLOW_MEMORY_API_JWT_ISSUER=https://issuer.example",
                "FLOW_MEMORY_API_JWT_AUDIENCE=flow-memory-api",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_validate(
        base_url: str,
        api_key: str,
        *,
        require_immutable_audit: bool = False,
        gateway_jwt_config: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        raise AssertionError(f"network validation should not run for {base_url} with {api_key}")

    monkeypatch.setattr(validator, "validate", fail_validate)

    try:
        validator.main(["--api-url", "https://api.flowmemory.ai", "--env-file", str(env_file)])
    except SystemExit as exc:
        assert "FLOW_MEMORY_API_JWT_HS256_SECRET" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted incomplete gateway JWT config")


def test_public_buildout_main_accepts_require_immutable_audit_flag(tmp_path: Any, monkeypatch: Any) -> None:
    env_file = tmp_path / "live.env"
    env_file.write_text(_production_env_text(), encoding="utf-8")
    captured: dict[str, Any] = {}

    def fake_validate(base_url: str, api_key: str, *, require_immutable_audit: bool = False) -> Mapping[str, Any]:
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        captured["require_immutable_audit"] = require_immutable_audit
        return {"status": "passed"}

    monkeypatch.setattr(validator, "validate", fake_validate)

    assert (
        validator.main(
            [
                "--api-url",
                "https://api.flowmemory.ai",
                "--env-file",
                str(env_file),
                "--require-immutable-audit",
            ]
        )
        == 0
    )
    assert captured == {
        "base_url": "https://api.flowmemory.ai",
        "api_key": "fmk_live_test_secret",
        "require_immutable_audit": True,
    }


def test_public_url_block_reason_rejects_placeholder_domains() -> None:
    blocked = (
        "https://api.yourdomain.com",
        "https://example.com",
        "https://compute.<your-domain>",
        "https://changeme.flowmemory.invalid",
        "https://api.example.test",
        "https://flowmemory.invalid",
    )

    for url in blocked:
        assert validator.public_url_block_reason(url) == "public_url_placeholder_not_allowed"

    assert validator.public_url_block_reason("https://api.flowmemory.ai") == ""


def test_public_url_block_reason_rejects_private_networks() -> None:
    blocked = (
        "https://10.0.0.12",
        "https://172.16.4.20",
        "https://192.168.1.30",
        "https://169.254.1.5",
        "https://[fd00::1]",
    )

    for url in blocked:
        assert validator.public_url_block_reason(url) == "public_url_must_use_global_host"


def test_public_validator_schema_count_evidence_blocks_underreported_schema() -> None:
    evidence = validator.postgres_schema_count_evidence(
        {
            "required_table_count": validator.MIN_POSTGRES_SCHEMA_TABLE_COUNT - 1,
            "required_index_count": validator.MIN_POSTGRES_SCHEMA_INDEX_COUNT,
        }
    )

    assert evidence["ok"] is False
    assert evidence["minimum_table_count"] == validator.MIN_POSTGRES_SCHEMA_TABLE_COUNT
    assert evidence["minimum_index_count"] == validator.MIN_POSTGRES_SCHEMA_INDEX_COUNT


def test_public_validator_connection_tuning_evidence_blocks_unbounded_postgres() -> None:
    passing = validator.postgres_connection_tuning_evidence(
        {
            "postgres_ssl_mode": "require",
            "pool_size": 4,
            "max_overflow": 4,
            "timeout_ms": 5000,
            "statement_timeout_ms": 5000,
            "migrations_enabled": True,
            "migrations_auto_run": True,
        }
    )
    missing_statement_timeout = validator.postgres_connection_tuning_evidence(
        {
            "postgres_ssl_mode": "disable",
            "pool_size": 0,
            "max_overflow": -1,
            "timeout_ms": 0,
            "statement_timeout_ms": 0,
            "migrations_enabled": True,
            "migrations_auto_run": False,
        }
    )

    assert passing["ok"] is True
    assert missing_statement_timeout["ok"] is False
    assert missing_statement_timeout["postgres_ssl_mode"] == "disable"
    assert missing_statement_timeout["statement_timeout_ms"] == 0


def test_public_validator_migration_history_evidence_requires_locked_current_history() -> None:
    expected_version = int(validator.migration_plan()["current_version"])
    passing = validator.postgres_migration_history_evidence(
        {
            "migration_status": {"current": True, "version": expected_version, "expected_version": expected_version},
            "migration_history": {
                "ok": True,
                "migration_lock": "postgres_advisory_lock",
                "history": [{"version": expected_version, "name": "current"}],
            },
        }
    )
    missing_history = validator.postgres_migration_history_evidence(
        {
            "migration_status": {"current": True, "version": expected_version, "expected_version": expected_version},
            "migration_history": {"ok": True, "migration_lock": "", "history": []},
        }
    )

    assert passing["ok"] is True
    assert passing["migration_lock"] == "postgres_advisory_lock"
    assert missing_history["ok"] is False
    assert missing_history["has_expected_history"] is False




def _passing_public_buildout_call_text(
    method: str,
    url: str,
    headers: Mapping[str, str] | None = None,
) -> tuple[int, str]:
    return 200, "# HELP compute_plan_requests_total Total compute plan requests\ncompute_plan_requests_total 1\n"


def _passing_public_buildout_call_json(
    redis_overrides: Mapping[str, Any] | None = None,
    audit_export_overrides: Mapping[str, Any] | None = None,
    storage_overrides: Mapping[str, Any] | None = None,
    migration_status_overrides: Mapping[str, Any] | None = None,
    migration_history_overrides: Mapping[str, Any] | None = None,
) -> Any:
    expected_migration_version = int(validator.migration_plan()["current_version"])
    job_counter = 0
    plan_counter = 0

    def fake_call_json(
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        nonlocal job_counter, plan_counter
        scopes = (headers or {}).get("x-flow-memory-scopes", "")
        if url == "https://api.example.test/":
            return 200, {"ok": True, "data": {"service": "Flow Memory Compute Market"}}
        if url.endswith("/compute/health") and not (headers or {}).get("x-flow-memory-api-key"):
            return 401, {"ok": False, "error": {"code": "auth.required"}}
        if url.endswith("/compute/health"):
            return 200, {"ok": True, "data": {"ok": True}}
        if url.endswith("/compute/readiness"):
            return 200, {
                "ok": True,
                "data": {
                    "ready": True,
                    "storage": {"backend": "postgres"},
                    "rate_limiter_status": {"backend": "redis"},
                    "circuit_breaker_status": {"backend": "redis"},
                    "production_safety_defaults": {
                        "rate_limit_backend": "redis",
                        "circuit_breaker_backend": "redis",
                        "require_managed_redis_in_production": True,
                        "redis_url_scheme": "rediss",
                        "require_managed_sql_in_production": True,
                        "dry_run_required": True,
                        "live_settlement_enabled": False,
                        "broadcast_enabled": False,
                        "private_key_inputs_allowed": False,
                        "audit_required": True,
                        "audit_export_required": True,
                        "audit_export_immutable_required": True,
                        "stripe_checkout_enabled": False,
                        "alert_routing_enabled": True,
                        "alert_webhook_configured": True,
                        "error_tracking_enabled": True,
                        "error_tracking_webhook_configured": True,
                        "telemetry_export_enabled": True,
                        "otlp_endpoint_configured": True,
                    },
                },
            }
        if url.endswith("/compute/plan") and scopes == "compute:read":
            return 403, {"ok": False, "error": {"code": "scope.denied"}}
        if url.endswith("/compute/plan"):
            plan_counter += 1
            return 200, {
                "ok": True,
                "data": {
                    "idempotent_replay": plan_counter >= 2,
                    "compute_plan": {
                        "decision_id": "decision_public_buildout",
                        "dry_run_only": True,
                        "funds_moved": False,
                        "broadcast_allowed": False,
                        "private_key_required": False,
                    },
                },
            }
        if url.endswith("/compute/audit/verify"):
            return 200, {"ok": True, "data": {"ok": True}}
        if url.endswith("/compute/audit/export"):
            return 200, {"ok": True, "data": {"ok": True, "manifest_hash": "manifest-hash", "event_count": 2}}
        if url.endswith("/compute/providers/external/quote"):
            return 200, {"ok": True, "data": {"ok": False}}
        if url.endswith("/market/capacity/reserve"):
            return 200, {"ok": True, "data": {"reservation": {"reservation_id": "res_public"}}}
        if url.endswith("/compute/jobs"):
            job_counter += 1
            return 200, {
                "ok": True,
                "data": {
                    "job": {
                        "job_id": f"job_public_{job_counter}",
                        "dry_run_only": True,
                        "funds_moved": False,
                        "broadcast_allowed": False,
                        "private_key_required": False,
                    }
                },
            }
        if url.endswith("/receipt") and scopes == "compute:read":
            return 403, {"ok": False, "error": {"code": "scope.denied"}}
        if url.endswith("/receipt"):
            return 200, {"ok": True, "data": {"ok": False}}
        if url.endswith("/compute/alerts/route"):
            return 200, {"ok": True, "data": {"ok": True, "routing_enabled": True, "delivery_count": 1}}
        if url.endswith("/compute/errors/track"):
            return 200, {"ok": True, "data": {"ok": True, "status": "delivered", "event_id": "error_public"}}
        if url.endswith("/admin/compute/otlp/export"):
            return 200, {"ok": True, "data": {"ok": True, "status": "delivered", "export_id": "otlp_public"}}
        if url.endswith("/complete"):
            return 200, {
                "ok": True,
                "data": {
                    "job": {"job_id": "job_public_1", "status": "succeeded"},
                    "provider_payout": {"provider_payout_id": "payout_public", "status": "accrued", "funds_moved": False},
                },
            }
        if "/billing/provider-payouts?" in url:
            return 200, {
                "ok": True,
                "data": {
                    "provider_payouts": [{"provider_payout_id": "payout_public", "status": "accrued", "funds_moved": False}],
                    "summary": {"accrued_total": 0.18},
                },
            }
        if url.endswith("/billing/provider-payouts/payout_public/settle"):
            return 200, {
                "ok": True,
                "data": {"provider_payout": {"provider_payout_id": "payout_public", "status": "settled", "funds_moved": False}},
            }
        if url.endswith("/billing/checkout"):
            return 200, {"ok": True, "data": {"checkout": {"funds_moved": False, "status": "requires_external_checkout_provider"}}}
        if "/billing/balance" in url:
            return 200, {"ok": True, "data": {"balance": {"account_id": "acct_public_buildout_1234567890"}}}
        if url.endswith("/billing/refund"):
            return 200, {
                "ok": True,
                "data": {"refund": {"funds_moved": False, "external_refund_created": False, "status": "recorded_no_custody"}},
            }
        if url.endswith("/admin/storage/diagnostics"):
            return 200, {
                "ok": True,
                "data": {
                    "ok": True,
                    "production_readiness": {"production_ready": True},
                    "storage": {
                        "backend": "postgresql",
                        "postgres_ssl_mode": "require",
                        "pool_size": 4,
                        "max_overflow": 4,
                        "timeout_ms": 5000,
                        "statement_timeout_ms": 5000,
                        "migrations_enabled": True,
                        "migrations_auto_run": True,
                        **(storage_overrides or {}),
                    },
                    "migration_status": {
                        "current": True,
                        "version": expected_migration_version,
                        "expected_version": expected_migration_version,
                        **(migration_status_overrides or {}),
                    },
                    "migration_history": {
                        "ok": True,
                        "migration_lock": "postgres_advisory_lock",
                        "history": [{"version": expected_migration_version, "name": "current"}],
                        **(migration_history_overrides or {}),
                    },
                    "schema_verification": {
                        "ok": True,
                        "missing_tables": [],
                        "missing_indexes": [],
                        "advisory_lock_probe": {"acquired": True},
                        "required_table_count": validator.MIN_POSTGRES_SCHEMA_TABLE_COUNT,
                        "required_index_count": validator.MIN_POSTGRES_SCHEMA_INDEX_COUNT,
                    },
                },
            }
        if url.endswith("/admin/redis/diagnostics"):
            redis_diag = {
                "ok": True,
                "rate_limit_probe": {"ok": True},
                "circuit_breaker_probe": {"ok": True},
                "rate_limit_fail_closed": True,
                "circuit_breaker_fail_closed": True,
            }
            redis_diag.update(redis_overrides or {})
            return 200, {"ok": True, "data": redis_diag}
        if url.endswith("/admin/audit/export"):
            audit_export_status = {
                "immutable": True,
                "audit_exporter_status": {"exporter": "s3_object_lock", "immutable": True},
            }
            audit_export_status.update(audit_export_overrides or {})
            return 200, {"ok": True, "data": audit_export_status}
        return 200, {"ok": True, "data": {"ok": True}}

    return fake_call_json

def test_public_buildout_validation_rejects_unsafe_postgres_connection_tuning(monkeypatch: Any) -> None:
    monkeypatch.setattr(validator.time, "time", lambda: 1234567890)
    monkeypatch.setattr(validator, "call_text", _passing_public_buildout_call_text)
    monkeypatch.setattr(
        validator,
        "call_json",
        _passing_public_buildout_call_json(
            storage_overrides={"statement_timeout_ms": 0, "migrations_auto_run": False}
        ),
    )

    try:
        validator.validate(
            "https://api.example.test",
            "prod-key",
            require_immutable_audit=True,
        )
    except AssertionError as exc:
        message = str(exc)
        assert "admin storage connection tuning failed" in message
        assert '"statement_timeout_ms": 0' in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted unsafe Postgres tuning")


def test_public_buildout_validation_rejects_missing_postgres_migration_history(monkeypatch: Any) -> None:
    monkeypatch.setattr(validator.time, "time", lambda: 1234567890)
    monkeypatch.setattr(validator, "call_text", _passing_public_buildout_call_text)
    monkeypatch.setattr(
        validator,
        "call_json",
        _passing_public_buildout_call_json(
            migration_history_overrides={"migration_lock": "", "history": []}
        ),
    )

    try:
        validator.validate(
            "https://api.example.test",
            "prod-key",
            require_immutable_audit=True,
        )
    except AssertionError as exc:
        message = str(exc)
        assert "admin storage migration history failed" in message
        assert '"has_expected_history": false' in message
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted missing migration history")


def test_public_buildout_validation_rejects_redis_fail_open_controls(monkeypatch: Any) -> None:
    for redis_overrides in (
        {"rate_limit_fail_closed": False},
        {"circuit_breaker_fail_closed": False},
    ):
        monkeypatch.setattr(validator.time, "time", lambda: 1234567890)
        monkeypatch.setattr(validator, "call_text", _passing_public_buildout_call_text)
        monkeypatch.setattr(
            validator,
            "call_json",
            _passing_public_buildout_call_json(redis_overrides),
        )

        try:
            validator.validate(
                "https://api.example.test",
                "prod-key",
                require_immutable_audit=True,
            )
        except AssertionError as exc:
            assert "admin redis diagnostics did not report fail-closed Redis controls" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("public buildout validator accepted fail-open Redis diagnostics")


def test_public_buildout_validation_requires_immutable_s3_audit_when_requested(monkeypatch: Any) -> None:
    monkeypatch.setattr(validator.time, "time", lambda: 1234567890)
    monkeypatch.setattr(validator, "call_text", _passing_public_buildout_call_text)
    monkeypatch.setattr(
        validator,
        "call_json",
        _passing_public_buildout_call_json(
            audit_export_overrides={
                "immutable": False,
                "audit_exporter_status": {"exporter": "local_file", "immutable": False},
            }
        ),
    )

    try:
        validator.validate(
            "https://api.example.test",
            "prod-key",
            require_immutable_audit=True,
        )
    except AssertionError as exc:
        assert "admin audit export is not immutable S3 Object Lock storage" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("public buildout validator accepted non-immutable audit storage")


def test_public_buildout_validation_checks_unsigned_provider_receipts(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, Mapping[str, str] | None, Mapping[str, Any] | None]] = []
    job_counter = 0
    text_calls: list[tuple[str, str, Mapping[str, str] | None]] = []
    jwt_health_calls = 0

    def fake_call_json(
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[int, Mapping[str, Any]]:
        nonlocal job_counter, jwt_health_calls
        calls.append((method, url, headers, body))
        plan_counter = sum(
            1
            for _method, called_url, _headers, _body in calls
            if called_url.endswith("/compute/plan")
        )
        scopes = (headers or {}).get("x-flow-memory-scopes", "")
        if url == "https://api.example.test/":
            return 200, {"ok": True, "data": {"service": "Flow Memory Compute Market"}}
        if url.endswith("/compute/health") and (headers or {}).get("authorization"):
            jwt_health_calls += 1
            if jwt_health_calls == 1:
                return 200, {"ok": True, "data": {"ok": True}}
            return 401, {"ok": False, "error": {"code": "auth.invalid"}}
        if url.endswith("/compute/health") and not (headers or {}).get("x-flow-memory-api-key"):
            return 401, {"ok": False, "error": {"code": "auth.required"}}
        if url.endswith("/compute/health"):
            return 200, {"ok": True, "data": {"ok": True}}
        if url.endswith("/compute/readiness"):
            return 200, {
                "ok": True,
                "data": {
                    "ready": True,
                    "storage": {"backend": "postgres"},
                    "rate_limiter_status": {"backend": "redis"},
                    "circuit_breaker_status": {"backend": "redis"},
                    "production_safety_defaults": {
                        "rate_limit_backend": "redis",
                        "circuit_breaker_backend": "redis",
                        "require_managed_redis_in_production": True,
                        "redis_url_scheme": "rediss",
                        "require_managed_sql_in_production": True,
                        "dry_run_required": True,
                        "live_settlement_enabled": False,
                        "broadcast_enabled": False,
                        "private_key_inputs_allowed": False,
                        "audit_required": True,
                        "audit_export_required": True,
                        "audit_export_immutable_required": True,
                        "stripe_checkout_enabled": False,
                        "alert_routing_enabled": True,
                        "alert_webhook_configured": True,
                        "error_tracking_enabled": True,
                        "error_tracking_webhook_configured": True,
                        "telemetry_export_enabled": True,
                        "otlp_endpoint_configured": True,
                    },
                },
            }
        if url.endswith("/compute/plan") and scopes == "compute:read":
            return 403, {"ok": False, "error": {"code": "scope.denied"}}
        if url.endswith("/compute/plan"):
            replay = plan_counter >= 2
            return 200, {
                "ok": True,
                "data": {
                    "idempotent_replay": replay,
                    "compute_plan": {
                        "decision_id": "decision_public_buildout",
                        "dry_run_only": True,
                        "funds_moved": False,
                        "broadcast_allowed": False,
                        "private_key_required": False,
                    },
                },
            }
        if url.endswith("/compute/audit/verify"):
            return 200, {"ok": True, "data": {"ok": True}}
        if url.endswith("/compute/audit/export"):
            assert method == "POST"
            assert scopes == "compute:audit"
            assert body == {"chain_id": "all"}
            return 200, {"ok": True, "data": {"ok": True, "manifest_hash": "manifest-hash", "event_count": 2}}
        if url.endswith("/market/capacity/reserve"):
            return 200, {"ok": True, "data": {"reservation": {"reservation_id": "res_public"}}}
        if url.endswith("/compute/providers/external/quote"):
            return 200, {"ok": True, "data": {"ok": False}}
        if url.endswith("/compute/jobs"):
            job_counter += 1
            return 200, {
                "ok": True,
                "data": {
                    "job": {
                        "job_id": f"job_public_{job_counter}",
                        "dry_run_only": True,
                        "funds_moved": False,
                        "broadcast_allowed": False,
                        "private_key_required": False,
                    }
                },
            }
        if url.endswith("/receipt") and scopes == "compute:read":
            return 403, {"ok": False, "error": {"code": "scope.denied"}}
        if url.endswith("/receipt"):
            return 200, {"ok": True, "data": {"ok": False, "error": {"error_code": "provider_receipt.signing_key_missing"}}}
        if url.endswith("/compute/alerts/route"):
            return 200, {"ok": True, "data": {"ok": True, "routing_enabled": True, "delivery_count": 1}}
        if url.endswith("/compute/errors/track"):
            return 200, {"ok": True, "data": {"ok": True, "status": "delivered", "event_id": "error_public"}}
        if url.endswith("/admin/compute/otlp/export"):
            return 200, {"ok": True, "data": {"ok": True, "status": "delivered", "export_id": "otlp_public"}}
        if url.endswith("/complete"):
            return 200, {
                "ok": True,
                "data": {
                    "job": {"job_id": "job_public_1", "status": "succeeded"},
                    "provider_payout": {
                        "provider_payout_id": "payout_public",
                        "status": "accrued",
                        "funds_moved": False,
                    },
                },
            }
        if url.endswith("/billing/checkout"):
            return 200, {
                "ok": True,
                "data": {"checkout": {"funds_moved": False, "status": "requires_external_checkout_provider"}},
            }
        if "/billing/balance" in url:
            return 200, {"ok": True, "data": {"balance": {"account_id": "acct_public_buildout_1234567890"}}}
        if "/billing/provider-payouts?" in url:
            return 200, {
                "ok": True,
                "data": {
                    "provider_payouts": [
                        {"provider_payout_id": "payout_public", "status": "accrued", "funds_moved": False}
                    ],
                    "summary": {"accrued_total": 0.18},
                },
            }
        if url.endswith("/billing/provider-payouts/payout_public/settle"):
            return 200, {
                "ok": True,
                "data": {
                    "provider_payout": {
                        "provider_payout_id": "payout_public",
                        "status": "settled",
                        "funds_moved": False,
                    }
                },
            }
        if url.endswith("/billing/refund"):
            return 200, {
                "ok": True,
                "data": {
                    "refund": {
                        "funds_moved": False,
                        "external_refund_created": False,
                        "status": "recorded_no_custody",
                    }
                },
            }
        if url.endswith("/admin/storage/diagnostics"):
            return 200, {
                "ok": True,
                "data": {
                    "ok": True,
                    "production_readiness": {"production_ready": True},
                    "storage": {
                        "backend": "postgresql",
                        "postgres_ssl_mode": "require",
                        "pool_size": 4,
                        "max_overflow": 4,
                        "timeout_ms": 5000,
                        "statement_timeout_ms": 5000,
                        "migrations_enabled": True,
                        "migrations_auto_run": True,
                    },
                    "migration_status": {
                        "current": True,
                        "version": int(validator.migration_plan()["current_version"]),
                        "expected_version": int(validator.migration_plan()["current_version"]),
                    },
                    "migration_history": {
                        "ok": True,
                        "migration_lock": "postgres_advisory_lock",
                        "history": [{"version": int(validator.migration_plan()["current_version"]), "name": "current"}],
                    },
                    "schema_verification": {
                        "ok": True,
                        "missing_tables": [],
                        "missing_indexes": [],
                        "advisory_lock_probe": {"acquired": True},
                        "required_table_count": validator.MIN_POSTGRES_SCHEMA_TABLE_COUNT,
                        "required_index_count": validator.MIN_POSTGRES_SCHEMA_INDEX_COUNT,
                    },
                },
            }
        if url.endswith("/admin/redis/diagnostics"):
            return 200, {
                "ok": True,
                "data": {
                    "ok": True,
                    "rate_limit_probe": {"ok": True},
                    "circuit_breaker_probe": {"ok": True},
                    "rate_limit_fail_closed": True,
                    "circuit_breaker_fail_closed": True,
                },
            }
        if url.endswith("/admin/audit/export"):
            return 200, {
                "ok": True,
                "data": {
                    "immutable": True,
                    "audit_exporter_status": {"exporter": "s3_object_lock", "immutable": True},
                },
            }
        return 200, {"ok": True, "data": {}}

    def fake_call_text(
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, str]:
        text_calls.append((method, url, headers))
        return 200, "# HELP compute_plan_requests_total Total compute plan requests\ncompute_plan_requests_total 1\n"

    monkeypatch.setattr(validator.time, "time", lambda: 1234567890)
    monkeypatch.setattr(validator, "call_json", fake_call_json)
    monkeypatch.setattr(validator, "call_text", fake_call_text)

    result = validator.validate(
        "https://api.example.test",
        "prod-key",
        require_immutable_audit=True,
        gateway_jwt_config={
            "secret": "gateway-jwt-secret-with-at-least-32-characters",
            "issuer": "https://issuer.example",
            "audience": "flow-memory-api",
            "leeway_seconds": "60",
        },
    )

    receipt_calls = [call for call in calls if call[1].endswith("/receipt")]
    assert result["status"] == "passed"
    assert result["checks"]["job_receipt_wrong_scope"] == 403
    assert result["checks"]["job_receipt_unsigned"] == 200
    assert result["audit_export_immutable"] is True
    assert result["checks"]["audit_export_write"] == 200
    assert result["audit_export_write_manifest_hash_present"] is True
    assert result["audit_export_write_event_count"] == 2
    assert result["plan_idempotent_replay"] is True
    assert result["postgres_required_table_count"] >= validator.MIN_POSTGRES_SCHEMA_TABLE_COUNT
    assert result["postgres_required_index_count"] >= validator.MIN_POSTGRES_SCHEMA_INDEX_COUNT
    assert result["postgres_connection_pool_size"] == 4
    assert result["postgres_connection_max_overflow"] == 4
    assert result["postgres_connection_timeout_ms"] == 5000
    assert result["postgres_statement_timeout_ms"] == 5000
    assert result["postgres_migrations_auto_run"] is True
    assert result["postgres_migration_version"] == int(validator.migration_plan()["current_version"])
    assert result["postgres_migration_expected_version"] == int(validator.migration_plan()["current_version"])
    assert result["postgres_migration_history_count"] == 1
    assert result["postgres_migration_lock"] == "postgres_advisory_lock"
    assert result["audit_exporter"] == "s3_object_lock"
    assert result["require_managed_redis_in_production"] is True
    assert result["redis_url_scheme"] == "rediss"
    assert result["require_managed_sql_in_production"] is True
    assert result["dry_run_required"] is True
    assert result["live_settlement_enabled"] is False
    assert result["broadcast_enabled"] is False
    assert result["private_key_inputs_allowed"] is False
    assert result["audit_required"] is True
    assert result["audit_export_required"] is True
    assert result["audit_export_immutable_required"] is True
    assert result["stripe_checkout_enabled"] is False
    assert result["alert_routing_enabled"] is True
    assert result["alert_webhook_configured"] is True
    assert result["error_tracking_enabled"] is True
    assert result["error_tracking_webhook_configured"] is True
    assert result["telemetry_export_enabled"] is True
    assert result["otlp_endpoint_configured"] is True
    assert result["alert_route_delivery_count"] == 1
    assert result["error_tracking_status"] == "delivered"
    assert result["otlp_export_status"] == "delivered"
    assert result["checks"]["metrics"] == 200
    assert result["checks"]["jwt_health"] == 200
    assert result["checks"]["jwt_wrong_audience"] == 401
    assert result["checks"]["jwt_wrong_scope"] == 403
    assert result["checks"]["alerts"] == 200
    assert result["checks"]["alerts_route"] == 200
    assert result["checks"]["error_tracking"] == 200
    assert result["checks"]["otlp_export"] == 200
    assert text_calls == [
        (
            "GET",
            "https://api.example.test/metrics",
            {"x-flow-memory-api-key": "prod-key", "x-flow-memory-scopes": "compute:read"},
        )
    ]
    assert any(
        call[1] == "https://api.example.test/compute/alerts"
        and call[2] == {"x-flow-memory-api-key": "prod-key", "x-flow-memory-scopes": "compute:read"}
        for call in calls
    )
    assert len(receipt_calls) == 2
    audit_export_write_calls = [call for call in calls if call[1].endswith("/compute/audit/export")]
    assert len(audit_export_write_calls) == 1
    assert audit_export_write_calls[0][2] is not None
    assert audit_export_write_calls[0][2]["x-flow-memory-scopes"] == "compute:audit"
    assert audit_export_write_calls[0][3] == {"chain_id": "all"}
    jwt_calls = [call for call in calls if call[2] and "authorization" in call[2]]
    assert len(jwt_calls) == 3
    assert all(call[2] is not None and call[2].get("x-flow-memory-scopes") == "compute:read" for call in jwt_calls)
    assert any(call[0] == "POST" and call[1] == "https://api.example.test/compute/plan" for call in jwt_calls)
    refund_calls = [call for call in calls if call[1].endswith("/billing/refund")]
    assert len(refund_calls) == 1
    assert refund_calls[0][2] is not None and refund_calls[0][2]["x-flow-memory-scopes"] == "compute:billing"
    assert refund_calls[0][3] is not None
    assert refund_calls[0][3]["amount"] == 1
    payout_calls = [call for call in calls if "/billing/provider-payouts" in call[1]]
    assert len(payout_calls) == 2
    assert payout_calls[0][2] is not None and payout_calls[0][2]["x-flow-memory-scopes"] == "compute:billing"
    assert payout_calls[1][2] is not None and payout_calls[1][2]["x-flow-memory-scopes"] == "compute:settlement-admin"
    assert payout_calls[1][3] is not None
    assert payout_calls[1][3]["settled_by"] == "public-buildout-validator"
    assert receipt_calls[0][2] is not None and receipt_calls[0][2]["x-flow-memory-scopes"] == "compute:read"
    assert receipt_calls[1][2] is not None and receipt_calls[1][2]["x-flow-memory-scopes"] == "compute:execute"
    assert receipt_calls[1][3] is not None
    assert "signature" not in receipt_calls[1][3]
    assert receipt_calls[1][3]["receipt"]["funds_moved"] is False
    plan_calls = [
        call
        for call in calls
        if call[1].endswith("/compute/plan")
        and call[2] is not None
        and call[2].get("x-flow-memory-scopes") == "compute:plan"
    ]
    assert len(plan_calls) == 2
    assert plan_calls[0][3] is not None and plan_calls[1][3] is not None
    assert plan_calls[0][3]["idempotency_key"] == plan_calls[1][3]["idempotency_key"]
