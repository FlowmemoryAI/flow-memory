from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from flow_memory.api.server_cli import build_http_api_config
import scripts.deploy_compute_market_render_level1 as render_deploy

ROOT = Path(__file__).resolve().parents[1]


def test_live_env_template_preserves_non_settlement_safety_defaults() -> None:
    template = (ROOT / "deployments" / "compute-market" / "live.env.example").read_text(encoding="utf-8")

    for required in (
        "FLOW_MEMORY_API_JWT_HS256_SECRET=",
        "FLOW_MEMORY_API_JWT_ISSUER=",
        "FLOW_MEMORY_API_JWT_AUDIENCE=",
        "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS=60",
        "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=postgres",
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true",
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION=true",
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
        "FLOW_MEMORY_COMPUTE_REDIS_URL=rediss://CHANGEME-managed-redis-host:6379/0",
        "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED=false",
        "FLOW_MEMORY_BILLING_STRIPE_API_BASE_URL=https://api.stripe.com",
        "FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS=300",
        "RENDER_KEYVALUE_IP_ALLOWLIST",
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
    assert "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION: ${FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION:-false}" in compose
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
    assert "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED: ${FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED:-false}" in compose
    assert "FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET: ${FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET:-}" in compose
    assert (
        "FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS: "
        "${FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS:-300}"
    ) in compose


def test_render_blueprint_requires_explicit_tls_redis_url() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    redis_url_key = "      - key: FLOW_MEMORY_COMPUTE_REDIS_URL\n        sync: false"

    assert redis_url_key in blueprint
    assert "property: connectionString" not in blueprint[
        blueprint.index("FLOW_MEMORY_COMPUTE_REDIS_URL") : blueprint.index("FLOW_MEMORY_COMPUTE_REDIS_PREFIX")
    ]

    assert "Direct blueprint deploys cannot infer public egress CIDRs" in blueprint
    assert "RENDER_KEYVALUE_IP_ALLOWLIST" in blueprint
    assert "FLOW_MEMORY_API_JWT_HS256_SECRET\n        sync: false" in blueprint
    assert "FLOW_MEMORY_API_JWT_ISSUER\n        value: \"\"" in blueprint
    assert "FLOW_MEMORY_API_JWT_AUDIENCE\n        value: \"\"" in blueprint
    assert "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS\n        value: 60" in blueprint


def test_render_deploy_requires_https_public_url_before_smoke() -> None:
    assert render_deploy.public_url({"serviceDetails": {"url": "flow-memory-api.onrender.com"}}) == (
        "https://flow-memory-api.onrender.com"
    )
    with pytest.raises(SystemExit) as blocked:
        render_deploy.assert_https_public_url("http://flow-memory-api.example.com")

    smoke = render_deploy.smoke_public("http://flow-memory-api.example.com", "api-key")

    assert blocked.value.code == 33
    assert smoke["ok"] is False
    assert smoke["reason"] == "public_url_must_use_https_tls"

def test_render_smoke_validates_gateway_jwt_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    jwt_health_calls = 0

    def fake_call_json(method: str, url: str, headers=None, body=None):
        nonlocal jwt_health_calls
        calls.append((method, url, headers, body))
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
                    },
                },
            }
        if url.endswith("/compute/plan") and scopes == "compute:read":
            return 403, {"ok": False, "error": {"code": "scope.denied"}}
        if url.endswith("/compute/plan"):
            return 200, {
                "ok": True,
                "data": {
                    "compute_plan": {
                        "dry_run_only": True,
                        "funds_moved": False,
                        "broadcast_allowed": False,
                        "private_key_required": False,
                    }
                },
            }
        if url.endswith("/compute/audit/verify"):
            return 200, {"ok": True, "data": {"ok": True}}
        if url.endswith("/admin/audit/export"):
            return 200, {"ok": True, "data": {"immutable": True}}
        if url.endswith("/admin/storage/diagnostics"):
            return 200, {
                "ok": True,
                "data": {
                    "schema_verification": {
                        "ok": True,
                        "missing_tables": [],
                        "missing_indexes": [],
                        "advisory_lock_probe": {"acquired": True},
                    }
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
        if url.endswith("/compute/alerts") or url.endswith("/compute/telemetry"):
            return 200, {"ok": True, "data": {}}
        raise AssertionError(f"unexpected JSON call: {method} {url}")

    def fake_call_text(method: str, url: str, headers=None):
        calls.append((method, url, headers, None))
        return 200, "compute_plan_requests_total 1\n"

    monkeypatch.setattr(render_deploy, "call_json", fake_call_json)
    monkeypatch.setattr(render_deploy, "call_text", fake_call_text)

    result = render_deploy.smoke_public(
        "https://api.example.test",
        "api-key",
        {
            "FLOW_MEMORY_API_JWT_HS256_SECRET": "gateway-jwt-secret-with-at-least-32-characters",
            "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
            "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
        },
    )

    jwt_calls = [call for call in calls if call[2] and call[2].get("authorization", "").startswith("Bearer ")]
    assert result["ok"] is True
    assert result["statuses"]["jwt_health"] == 200
    assert result["statuses"]["jwt_wrong_audience"] == 401
    assert len(jwt_calls) == 2
    assert jwt_calls[0][2]["x-flow-memory-scopes"] == "compute:read"


def test_render_blueprint_preserves_billing_safety_defaults() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED\n        value: false" in blueprint
    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_SECRET_KEY\n        sync: false" in blueprint
    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET\n        sync: false" in blueprint
    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS\n        value: 300" in blueprint


def test_public_smoke_scripts_verify_observability_endpoints() -> None:
    smoke_script = (ROOT / "scripts" / "smoke_compute_market_public.ps1").read_text(encoding="utf-8")
    render_script = (ROOT / "scripts" / "deploy_compute_market_render_level1.py").read_text(encoding="utf-8")

    assert 'Invoke-WebRequest -Uri "$baseUrl/metrics"' in smoke_script
    assert "compute_plan_requests_total" in smoke_script
    assert "Path '/compute/alerts'" in smoke_script
    assert "Path '/compute/telemetry'" in smoke_script
    assert 'checks["metrics"] = call_text("GET", f"{base}/metrics", headers_read)' in render_script
    assert 'checks["alerts"] = call_json("GET", f"{base}/compute/alerts", headers_read)' in render_script
    assert 'checks["telemetry"] = call_json("GET", f"{base}/compute/telemetry", headers_read)' in render_script
    assert '"metrics": checks["metrics"][0]' in render_script
    assert '"alerts": checks["alerts"][0]' in render_script
    assert '"telemetry": checks["telemetry"][0]' in render_script
    assert "deployments/compute-market/prometheus-alerts.yml" in render_script
    assert 'checks["jwt_health"] = call_json(' in render_script
    assert 'checks["jwt_wrong_audience"] = call_json(' in render_script


def test_public_buildout_validator_requires_observability_endpoints() -> None:
    validator_script = (ROOT / "scripts" / "validate_compute_market_public_buildout.py").read_text(encoding="utf-8")

    assert 'checks["metrics"] = call_text("GET", f"{base}/metrics", headers_read)' in validator_script
    assert 'checks["alerts"] = call_json("GET", f"{base}/compute/alerts", headers_read)' in validator_script
    assert 'checks["telemetry"] = call_json("GET", f"{base}/compute/telemetry", headers_read)' in validator_script
    assert '"compute_plan_requests_total" in checks["metrics"][1]' in validator_script
    assert 'checks[name][0] == 200 and checks[name][1].get("ok") is True' in validator_script


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


def test_render_deploy_requires_s3_object_lock_audit_export(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as missing:
        render_deploy.audit_export_uri_from_env({})
    with pytest.raises(SystemExit) as local_file:
        render_deploy.audit_export_uri_from_env(
            {"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": "/var/lib/flow-memory/audit/compute-market.ndjson"}
        )
    with pytest.raises(SystemExit) as missing_region:
        render_deploy.audit_export_s3_region_from_env(
            {"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": "s3://flow-memory-audit/compute-market"}
        )
    monkeypatch.setattr(render_deploy, "DEFAULT_AUDIT_EXPORT_URI", "s3://flow-memory-shell-audit/compute-market")
    monkeypatch.setattr(render_deploy, "DEFAULT_AUDIT_EXPORT_S3_REGION", "us-west-2")
    monkeypatch.setattr(render_deploy, "DEFAULT_PROVIDER_CALLBACK_IP_ALLOWLIST", "")

    assert (
        render_deploy.audit_export_uri_from_env(
            {"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": "/var/lib/flow-memory/audit/compute-market.ndjson"}
        )
        == "s3://flow-memory-shell-audit/compute-market"
    )
    assert render_deploy.audit_export_s3_region_from_env({}) == "us-west-2"


    env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_s3_region="us-east-1",
        )
    }

    assert missing.value.code == 23
    assert local_file.value.code == 23
    assert missing_region.value.code == 23
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI"] == "s3://flow-memory-audit/compute-market"
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED"] == "true"
    assert env_vars["FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION"] == "true"
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE"] == "COMPLIANCE"
    assert env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION"] == "us-east-1"
    assert env_vars["FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED"] == "false"
    assert env_vars["FLOW_MEMORY_BILLING_STRIPE_API_BASE_URL"] == "https://api.stripe.com"
    assert env_vars["FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS"] == "300"
    assert env_vars["FLOW_MEMORY_BILLING_STRIPE_SECRET_KEY"] == ""
    assert env_vars["FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET"] == ""
    assert env_vars["FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST"] == ""
    assert env_vars["FLOW_MEMORY_API_JWT_HS256_SECRET"] == ""
    assert env_vars["FLOW_MEMORY_API_JWT_ISSUER"] == ""
    assert env_vars["FLOW_MEMORY_API_JWT_AUDIENCE"] == ""
    assert env_vars["FLOW_MEMORY_API_JWT_LEEWAY_SECONDS"] == "60"


def test_render_env_builder_binds_https_observability_sinks() -> None:
    env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_s3_region="us-east-1",
            alert_webhook_url="https://alerts.example.test/flow-memory",
            alert_webhook_secret="alert-secret",
            alert_webhook_timeout_ms="2500",
            error_tracking_webhook_url="https://errors.example.test/flow-memory",
            error_tracking_webhook_secret="error-secret",
            error_tracking_timeout_ms="3000",
            otlp_endpoint_url="https://otel.example.test/v1/traces",
            otlp_headers="authorization: Bearer otlp-secret",
            otlp_timeout_ms="4000",
        )
    }

    assert env_vars["FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED"] == "true"
    assert env_vars["FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL"] == "https://alerts.example.test/flow-memory"
    assert env_vars["FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_SECRET"] == "alert-secret"
    assert env_vars["FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS"] == "2500"
    assert env_vars["FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED"] == "true"
    assert env_vars["FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL"] == "https://errors.example.test/flow-memory"
    assert env_vars["FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_SECRET"] == "error-secret"
    assert env_vars["FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS"] == "3000"
    assert env_vars["FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED"] == "true"
    assert env_vars["FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL"] == "https://otel.example.test/v1/traces"
    assert env_vars["FLOW_MEMORY_COMPUTE_OTLP_HEADERS"] == "authorization: Bearer otlp-secret"
    assert env_vars["FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS"] == "4000"

    baseline_env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_s3_region="us-east-1",
        )
    }
    assert baseline_env_vars["FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED"] == "false"
    assert baseline_env_vars["FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL"] == ""
    assert baseline_env_vars["FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED"] == "false"
    assert baseline_env_vars["FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL"] == ""
    assert baseline_env_vars["FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED"] == "false"
    assert baseline_env_vars["FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL"] == ""

    with pytest.raises(SystemExit) as missing:
        render_deploy.observability_sink_url_from_env(
            {"FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED": "true"},
            "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL",
            "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED",
        )
    with pytest.raises(SystemExit) as insecure:
        render_deploy.observability_sink_url_from_env(
            {"FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL": "http://otel.example.test/v1/traces"},
            "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL",
            "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED",
        )

    assert missing.value.code == 29
    assert insecure.value.code == 29

def test_render_env_builder_propagates_and_validates_provider_callback_ip_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_deploy, "DEFAULT_PROVIDER_CALLBACK_IP_ALLOWLIST", "")
    env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_s3_region="us-east-1",
            provider_callback_ip_allowlist="203.0.113.0/24,2001:db8::1",
        )
    }

    assert env_vars["FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST"] == "203.0.113.0/24,2001:db8::1"

    assert (
        render_deploy.provider_callback_ip_allowlist_from_env(
            {"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "203.0.113.10,2001:db8::1"}
        )
        == "203.0.113.10,2001:db8::1"
    )
    with pytest.raises(SystemExit) as missing:
        render_deploy.provider_callback_ip_allowlist_from_env(
            {"FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED": "true"}
        )
    with pytest.raises(SystemExit) as world_open:
        render_deploy.provider_callback_ip_allowlist_from_env(
            {"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "0.0.0.0/0"}
        )
    with pytest.raises(SystemExit) as placeholder:
        render_deploy.provider_callback_ip_allowlist_from_env(
            {"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "CHANGEME-provider-cidr"}
        )

    assert missing.value.code == 30
    assert world_open.value.code == 31
    assert placeholder.value.code == 31

def test_render_env_builder_propagates_and_validates_gateway_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_deploy, "DEFAULT_API_JWT_HS256_SECRET", "")
    monkeypatch.setattr(render_deploy, "DEFAULT_API_JWT_ISSUER", "")
    monkeypatch.setattr(render_deploy, "DEFAULT_API_JWT_AUDIENCE", "")
    monkeypatch.setattr(render_deploy, "DEFAULT_API_JWT_LEEWAY_SECONDS", "")

    jwt_secret = "gateway-jwt-secret-with-at-least-32-characters"
    env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_s3_region="us-east-1",
            jwt_hs256_secret=jwt_secret,
            jwt_issuer="https://issuer.example",
            jwt_audience="flow-memory-api",
            jwt_leeway_seconds="45",
        )
    }
    parsed = render_deploy.gateway_jwt_config_from_env(
        {
            "FLOW_MEMORY_API_JWT_HS256_SECRET": jwt_secret,
            "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
            "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
            "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS": "45",
        }
    )

    assert env_vars["FLOW_MEMORY_API_JWT_HS256_SECRET"] == jwt_secret
    assert env_vars["FLOW_MEMORY_API_JWT_ISSUER"] == "https://issuer.example"
    assert env_vars["FLOW_MEMORY_API_JWT_AUDIENCE"] == "flow-memory-api"
    assert env_vars["FLOW_MEMORY_API_JWT_LEEWAY_SECONDS"] == "45"
    assert parsed["FLOW_MEMORY_API_JWT_HS256_SECRET"] == jwt_secret
    with pytest.raises(SystemExit) as missing:
        render_deploy.gateway_jwt_config_from_env(
            {
                "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
                "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
            }
        )
    with pytest.raises(SystemExit) as weak:
        render_deploy.gateway_jwt_config_from_env(
            {
                "FLOW_MEMORY_API_JWT_HS256_SECRET": "short-secret",
                "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
                "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
            }
        )
    with pytest.raises(SystemExit) as insecure_issuer:
        render_deploy.gateway_jwt_config_from_env(
            {
                "FLOW_MEMORY_API_JWT_HS256_SECRET": jwt_secret,
                "FLOW_MEMORY_API_JWT_ISSUER": "http://issuer.example",
                "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
            }
        )
    with pytest.raises(SystemExit) as invalid_leeway:
        render_deploy.gateway_jwt_config_from_env(
            {
                "FLOW_MEMORY_API_JWT_HS256_SECRET": jwt_secret,
                "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
                "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
                "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS": "-1",
            }
        )

    assert missing.value.code == 32
    assert weak.value.code == 32
    assert insecure_issuer.value.code == 32
    assert invalid_leeway.value.code == 32

def test_render_deploy_blocks_free_plans_unless_explicitly_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_deploy, "DEFAULT_POSTGRES_PLAN", "free")
    monkeypatch.setattr(render_deploy, "DEFAULT_KEYVALUE_PLAN", "free")
    monkeypatch.setattr(render_deploy, "DEFAULT_SERVICE_PLAN", "free")
    monkeypatch.setattr(render_deploy, "ALLOW_FREE_RENDER_PLANS", False)

    with pytest.raises(SystemExit) as blocked:
        render_deploy.validate_render_plans()

    monkeypatch.setattr(render_deploy, "ALLOW_FREE_RENDER_PLANS", True)

    assert blocked.value.code == 28
    assert render_deploy.validate_render_plans() is None


def test_render_deploy_selects_tls_keyvalue_connection_string() -> None:
    redis_url = render_deploy.select_managed_redis_url(
        {
            "internalConnectionString": "redis://internal-render-redis:6379",
            "externalConnectionString": "rediss://external-render-redis:6380",
        }
    )

    assert redis_url == "rediss://external-render-redis:6380"


def test_render_deploy_blocks_insecure_keyvalue_connection_info() -> None:
    with pytest.raises(SystemExit) as blocked:
        render_deploy.select_managed_redis_url(
            {
                "internalConnectionString": "redis://internal-render-redis:6379",
                "connectionString": "redis://external-render-redis:6379",
            }
        )

    assert blocked.value.code == 24

def test_render_keyvalue_creation_requires_explicit_external_tls_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    created_body: dict[str, object] = {}

    def fake_find_named(api_key: str, path: str, envelope: str, owner_id: str, name: str):
        return None

    def fake_render_request(api_key: str, method: str, path: str, body=None):
        nonlocal created_body
        if method == "POST" and path == "/key-value":
            created_body = dict(body)
            return {"id": "kv_1", **created_body}
        raise AssertionError(f"unexpected Render call: {method} {path}")

    monkeypatch.setattr(render_deploy, "find_named", fake_find_named)
    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)

    with pytest.raises(SystemExit) as blocked:
        render_deploy.ensure_keyvalue("render-key", "owner", "oregon")

    monkeypatch.setattr(render_deploy, "DEFAULT_KEYVALUE_IP_ALLOWLIST", "203.0.113.10/32,198.51.100.0/24")
    created = render_deploy.ensure_keyvalue("render-key", "owner", "oregon")

    assert blocked.value.code == 26
    assert created["ipAllowList"] == [
        {"source": "203.0.113.10/32", "description": "flow-memory-compute-market-redis-tls"},
        {"source": "198.51.100.0/24", "description": "flow-memory-compute-market-redis-tls"},
    ]


def test_render_keyvalue_external_allowlist_rejects_invalid_or_world_open_cidrs() -> None:
    with pytest.raises(SystemExit) as missing_prefix:
        render_deploy.keyvalue_ip_allow_list("203.0.113.10")

    with pytest.raises(SystemExit) as host_bits:
        render_deploy.keyvalue_ip_allow_list("203.0.113.10/24")

    with pytest.raises(SystemExit) as world_open:
        render_deploy.keyvalue_ip_allow_list("0.0.0.0/0")

    assert missing_prefix.value.code == 27
    assert host_bits.value.code == 27
    assert world_open.value.code == 27


def test_public_powershell_render_placeholder_gate_requires_redis_allowlist(tmp_path: Path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public deployment script validation")

    env_file = tmp_path / "render-placeholder.env"
    env_file.write_text(
        "\n".join(
            [
                "FLOW_MEMORY_API_KEY=fmk_live_test_key",
                "FLOW_MEMORY_COMPUTE_DATABASE_URL=postgresql://CHANGEME-managed-postgres-host:5432/flow_memory",
                "FLOW_MEMORY_COMPUTE_REDIS_URL=rediss://CHANGEME-managed-redis-host:6379/0",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=s3://flow-memory-audit/compute-market",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION=us-east-1",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.pop("RENDER_API_KEY", None)
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "deploy_compute_market_public_level1.ps1"),
            "-EnvFile",
            str(env_file),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode == 13, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_missing_deployment_target"
    assert payload["placeholder_values"] == [
        "FLOW_MEMORY_COMPUTE_DATABASE_URL",
        "FLOW_MEMORY_COMPUTE_REDIS_URL",
    ]
    assert payload["missing_values"] == ["RENDER_API_KEY", "RENDER_KEYVALUE_IP_ALLOWLIST"]



def test_render_env_builder_blocks_insecure_redis_and_non_postgres_urls() -> None:
    with pytest.raises(SystemExit) as redis_blocked:
        render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "redis://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
        )
    with pytest.raises(SystemExit) as postgres_blocked:
        render_deploy.build_env_vars(
            "dev-key",
            "sqlite:///tmp/local.db",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
        )

    assert redis_blocked.value.code == 24
    assert postgres_blocked.value.code == 25


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
