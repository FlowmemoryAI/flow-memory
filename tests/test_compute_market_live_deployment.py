from __future__ import annotations

from pathlib import Path

import pytest

from flow_memory.api.server_cli import build_http_api_config
import scripts.deploy_compute_market_render_level1 as render_deploy

ROOT = Path(__file__).resolve().parents[1]


def test_live_env_template_preserves_non_settlement_safety_defaults() -> None:
    template = (ROOT / "deployments" / "compute-market" / "live.env.example").read_text(encoding="utf-8")

    for required in (
        "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=postgres",
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true",
        "FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND=redis",
        "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND=redis",
        "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true",
        "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED=false",
        "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED=false",
        "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED=false",
        "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED=false",
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS=2000",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED=false",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS=2000",
        "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED=false",
        "FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS=5000",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=s3://CHANGEME-audit-object-lock-bucket/compute-market",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED=true",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION=us-east-1",
    ):
        assert required in template

    assert "FLOW_MEMORY_API_KEY=CHANGEME-high-entropy-api-key" in template
    assert "FLOW_MEMORY_POSTGRES_PASSWORD=CHANGEME-compose-fallback-postgres-password" in template
    assert "PRIVATE" + "_KEY=" not in template
    assert "SEED" not in template


def test_compute_market_compose_uses_postgres_redis_and_scope_enforced_api() -> None:
    compose = (ROOT / "docker-compose.compute-market.yml").read_text(encoding="utf-8")

    assert "FLOW_MEMORY_EXTRAS: compute-market-live" in compose
    assert "FLOW_MEMORY_API_KEY: ${FLOW_MEMORY_API_KEY:?" in compose
    assert "--require-scopes" in compose
    assert "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND: postgres" in compose
    assert "FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND: redis" in compose
    assert "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND: redis" in compose
    assert "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED: \"false\"" in compose
    assert "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED: \"false\"" in compose
    assert "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED: \"false\"" in compose
    assert "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED: ${FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED:-false}" in compose
    assert "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS: ${FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS:-2000}" in compose
    assert "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED: ${FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED:-false}" in compose
    assert "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS: ${FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS:-2000}" in compose
    assert "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED: ${FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED:-false}" in compose
    assert "FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS: ${FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS:-5000}" in compose
    assert "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED: ${FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED:-false}" in compose
    assert "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE: ${FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE:-COMPLIANCE}" in compose


def test_api_server_cli_rejects_public_bind_without_api_key() -> None:
    with pytest.raises(SystemExit):
        build_http_api_config(["--host", "0.0.0.0"], env={})


def test_api_server_cli_accepts_public_bind_with_api_key_and_scopes() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--api-key", "dev-key", "--require-scopes"],
        env={},
    )

    assert config.host == "0.0.0.0"
    assert config.api_key == "dev-key"
    assert config.require_scopes is True


def test_api_server_cli_accepts_public_bind_with_hashed_tenant_key_records() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--require-scopes"],
        env={
            "FLOW_MEMORY_API_KEYS_JSON": '[{"key_id":"tenant-key","key_prefix":"fmk_","key_hash":"hash","tenant_id":"tenant","scopes":["compute:read"],"enabled":true}]'
        },
    )

    assert config.host == "0.0.0.0"
    assert config.api_key == ""
    assert config.api_key_records[0]["tenant_id"] == "tenant"

def test_api_server_cli_accepts_public_bind_with_jwt_gateway_secret() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--require-scopes"],
        env={
            "FLOW_MEMORY_API_JWT_HS256_SECRET": "gateway-shared-secret",
            "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
            "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
        },
    )

    assert config.host == "0.0.0.0"
    assert config.api_key == ""
    assert config.jwt_hs256_secret == "gateway-shared-secret"
    assert config.jwt_issuer == "https://issuer.example"
    assert config.jwt_audience == "flow-memory-api"


def test_render_deploy_requires_s3_object_lock_audit_export() -> None:
    with pytest.raises(SystemExit) as missing:
        render_deploy.audit_export_uri_from_env({})
    with pytest.raises(SystemExit) as local_file:
        render_deploy.audit_export_uri_from_env(
            {"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": "/var/lib/flow-memory/audit/compute-market.ndjson"}
        )

    env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
        )
    }

    assert missing.value.code == 23
    assert local_file.value.code == 23
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI"] == "s3://flow-memory-audit/compute-market"
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED"] == "true"
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE"] == "COMPLIANCE"


def test_render_deploy_fallback_waits_for_new_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"deploy_list": 0, "waited_for": ""}

    def fake_render_request(api_key: str, method: str, path: str, body=None):
        if method == "GET" and path == "/services/srv_1/deploys?limit=10":
            calls["deploy_list"] = int(calls["deploy_list"]) + 1
            if calls["deploy_list"] == 1:
                return [{"deploy": {"id": "deploy_old", "status": "live"}}]
            return [
                {"deploy": {"id": "deploy_new", "status": "build_in_progress"}},
                {"deploy": {"id": "deploy_old", "status": "live"}},
            ]
        if method == "POST" and path == "/services/srv_1/deploys":
            return {"deploy": {"status": "created"}}
        raise AssertionError(f"unexpected Render call: {method} {path}")

    def fake_wait_deploy_live(api_key: str, service_id: str, deploy_id: str):
        calls["waited_for"] = deploy_id
        return {"id": deploy_id, "status": "live"}

    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)
    monkeypatch.setattr(render_deploy, "wait_deploy_live", fake_wait_deploy_live)

    result = render_deploy.trigger_service_deploy("render-key", "srv_1")

    assert calls["waited_for"] == "deploy_new"
    assert result["status"] == "live"
