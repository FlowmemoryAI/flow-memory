from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from collections.abc import Mapping
from typing import Any, cast


import pytest

from flow_memory.api.server_cli import build_http_api_config
import scripts.deploy_compute_market_render_level1 as render_deploy

ROOT = Path(__file__).resolve().parents[1]


def _render_blueprint_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    current_key = ""
    for raw_line in (ROOT / "render.yaml").read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- key: "):
            current_key = stripped.removeprefix("- key: ").strip()
            continue
        if current_key and stripped.startswith("value: "):
            values[current_key] = stripped.removeprefix("value: ").strip().strip('"')
            current_key = ""
    return values



def test_live_env_template_preserves_non_settlement_safety_defaults() -> None:
    template = (ROOT / "deployments" / "compute-market" / "live.env.example").read_text(encoding="utf-8")

    for required in (
        "FLOW_MEMORY_API_JWT_HS256_SECRET=",
        "FLOW_MEMORY_API_JWT_ISSUER=",
        "FLOW_MEMORY_API_JWT_AUDIENCE=",
        "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS=60",
        "FLOW_MEMORY_API_ENABLE_NONCE_CHECK=true",
        "FLOW_MEMORY_API_MAX_REQUEST_AGE_SECONDS=300",
        "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND=redis",
        "FLOW_MEMORY_API_NONCE_FAIL_CLOSED=true",
        "FLOW_MEMORY_API_NONCE_REQUIRE_TLS=true",
        "FLOW_MEMORY_PUBLIC_API_URL=https://api.yourdomain.com",
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
        "FLOW_MEMORY_COMPUTE_METRICS_ENABLED=true",
        "FLOW_MEMORY_COMPUTE_TRACING_ENABLED=true",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=s3://CHANGEME-audit-object-lock-bucket/compute-market",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED=true",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION=us-east-1",
        "FLOW_MEMORY_COMPUTE_AUDIT_CHECKPOINT_INTERVAL_SECONDS=86400",
        "FLOW_MEMORY_COMPUTE_REDIS_URL=rediss://CHANGEME-managed-redis-host:6379/0",
        "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED=false",
        "FLOW_MEMORY_BILLING_STRIPE_API_BASE_URL=https://api.stripe.com",
        "FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS=300",
        "RENDER_KEYVALUE_IP_ALLOWLIST",
        "RENDER_API_KEY=CHANGEME-render-api-key",
        "RENDER_OWNER_ID=CHANGEME-render-owner-or-workspace-id",
        "RENDER_POSTGRES_PLAN=basic_256mb",
        "RENDER_KEYVALUE_PLAN=starter",
        "RENDER_SERVICE_PLAN=starter",
        "RENDER_SERVICE_NAME=flow-memory-compute-market-api",
        "RENDER_BRANCH=main",
        "RENDER_REPO_URL=CHANGEME-render-connected-repository-url",
        "RENDER_ENABLE_DISK=false",
        "RENDER_REGION=oregon",
        "Leave empty for AWS S3",
    ):
        assert required in template

    assert "FLOW_MEMORY_API_KEY=CHANGEME-high-entropy-api-key" in template
    assert "FLOW_MEMORY_API_KEY_SCOPES=api:read api:write api:admin api:audit compute:read compute:plan compute:execute compute:admin compute:audit compute:provider-admin compute:policy-admin compute:billing compute:settlement-admin inference:read inference:plan inference:proxy inference:buy inference:sell inference:admin inference:audit" in template
    assert "FLOW_MEMORY_POSTGRES_PASSWORD=CHANGEME-compose-fallback-postgres-password" in template
    assert "PRIVATE" + "_KEY=" not in template
    assert "SEED" not in template


def test_compute_market_compose_uses_postgres_redis_and_scope_enforced_api() -> None:
    compose = (ROOT / "docker-compose.compute-market.yml").read_text(encoding="utf-8")

    assert "FLOW_MEMORY_EXTRAS: compute-market-live" in compose
    assert "FLOW_MEMORY_API_KEY: ${FLOW_MEMORY_API_KEY:?" in compose
    assert "FLOW_MEMORY_API_KEY_SCOPES: ${FLOW_MEMORY_API_KEY_SCOPES:-api:read api:write api:admin api:audit compute:read compute:plan compute:execute compute:admin compute:audit compute:provider-admin compute:policy-admin compute:billing compute:settlement-admin inference:read inference:plan inference:proxy inference:buy inference:sell inference:admin inference:audit}" in compose
    assert "--require-scopes" in compose
    assert "FLOW_MEMORY_API_ENABLE_NONCE_CHECK: \"true\"" in compose
    assert "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND: ${FLOW_MEMORY_API_NONCE_REPLAY_BACKEND:-redis}" in compose
    assert "FLOW_MEMORY_API_NONCE_FAIL_CLOSED: \"true\"" in compose
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
    assert (
        "FLOW_MEMORY_COMPUTE_AUDIT_CHECKPOINT_INTERVAL_SECONDS: "
        "${FLOW_MEMORY_COMPUTE_AUDIT_CHECKPOINT_INTERVAL_SECONDS:-86400}"
    ) in compose
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

    assert "FLOW_MEMORY_PUBLIC_API_URL\n        sync: false" in blueprint
    assert "Direct blueprint deploys cannot infer public egress CIDRs" in blueprint
    assert "RENDER_KEYVALUE_IP_ALLOWLIST" in blueprint
    assert "FLOW_MEMORY_API_JWT_HS256_SECRET\n        sync: false" in blueprint
    assert "FLOW_MEMORY_API_JWT_ISSUER\n        value: \"\"" in blueprint
    assert "FLOW_MEMORY_API_JWT_AUDIENCE\n        value: \"\"" in blueprint
    assert "FLOW_MEMORY_API_JWT_LEEWAY_SECONDS\n        value: 60" in blueprint
    assert "FLOW_MEMORY_API_ENABLE_NONCE_CHECK\n        value: true" in blueprint
    assert "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND\n        value: redis" in blueprint
    assert "FLOW_MEMORY_API_NONCE_REQUIRE_TLS\n        value: true" in blueprint
    assert "PRODUCTION: change every `plan: free` below to a paid Render plan" in blueprint
    assert "inference:proxy" in blueprint

def test_public_smoke_script_validates_gateway_jwt_when_configured() -> None:
    script = (ROOT / "scripts" / "smoke_compute_market_public.ps1").read_text(encoding="utf-8")

    expected_snippets = (
        "$GatewayJwtHs256Secret = $env:FLOW_MEMORY_API_JWT_HS256_SECRET",
        "$GatewayJwtIssuer = $env:FLOW_MEMORY_API_JWT_ISSUER",
        "$GatewayJwtAudience = $env:FLOW_MEMORY_API_JWT_AUDIENCE",
        "function New-GatewayJwt",
        "System.Security.Cryptography.HMACSHA256",
        "Invoke-GatewayJwtRequest -Token $jwtToken -Path '/compute/health'",
        "Invoke-GatewayJwtRequest -Token $badJwtToken -Path '/compute/health'",
        "Assert-Status -Response $jwtWrongAudience -Expected 401",
        "jwt_health = $jwtHealthStatus",
        "jwt_wrong_audience = $jwtWrongAudienceStatus",
        "flow_memory_roles",
        "-Roles 'inference-admin'",
        "Invoke-GatewayJwtRequest -Token $jwtRoleToken -Path '/inference/market/order-book'",
        "jwt_role_health = $jwtRoleHealthStatus",
        "jwt_role_inference_order_book = $jwtRoleInferenceStatus",
        "$MinimumPostgresSchemaTableCount = 110",
        "$MinimumPostgresSchemaIndexCount = 1311",
        "required_table_count",
        "required_index_count",
        "postgres_required_table_count = $requiredSchemaTableCount",
        "postgres_required_index_count = $requiredSchemaIndexCount",
        "idempotency_key = $planBody.idempotency_key",
        "Assert-True ($planReplay.Json.data.idempotent_replay -eq $true)",
        "Assert-True ($planReplay.Json.data.compute_plan.decision_id -eq $computePlan.decision_id)",
        "plan_idempotent_replay = [bool]$planReplay.Json.data.idempotent_replay",
        "Gateway JWT secret must be a real high-entropy secret",
        "must be configured together when JWT smoke is configured",
        "[switch]$IncludeMarketAlpha",
        "if ($IncludeMarketAlpha)",
        "Invoke-ComputeMarketRequest -Method POST -Path '/inference/opportunity-cost' -Scopes 'inference:plan'",
        "Invoke-ComputeMarketRequest -Method GET -Path '/inference/market/order-book' -Scopes 'inference:read'",
        "Invoke-ComputeMarketRequest -Method POST -Path '/v1/chat/completions' -Scopes 'inference:proxy'",
        "Invoke-ComputeMarketRequest -Method POST -Path '/v1/responses' -Scopes 'inference:proxy'",
        "Invoke-ComputeMarketRequest -Method POST -Path '/v1/embeddings' -Scopes 'inference:proxy'",
        "Invoke-ComputeMarketRequest -Method GET -Path '/capacity/inventory' -Scopes 'compute:read'",
        "Invoke-ComputeMarketRequest -Method GET -Path '/futures/markets' -Scopes 'compute:read'",
        "Assert-DataFlag -Response $futuresMarkets -Field 'live_trading_enabled' -Expected $false",
        "market_alpha = [bool]$IncludeMarketAlpha",
    )
    for expected in expected_snippets:
        assert expected in script

def test_public_smoke_rejects_placeholder_gateway_jwt_secret_before_network() -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public smoke JWT preflight validation")
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "smoke_compute_market_public.ps1"),
            "-ApiUrl",
            "https://api.flowmemory.ai",
            "-ApiKey",
            "fmk_live_smoke_secret",
            "-GatewayJwtHs256Secret",
            "CHANGEME-gateway-jwt-secret-with-at-least-32-characters",
            "-GatewayJwtIssuer",
            "https://issuer.example",
            "-GatewayJwtAudience",
            "flow-memory-api",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "Gateway JWT secret must be a real high-entropy secret" in result.stderr


def test_public_smoke_rejects_incomplete_gateway_jwt_before_network() -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public smoke JWT preflight validation")
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "smoke_compute_market_public.ps1"),
            "-ApiUrl",
            "https://api.flowmemory.ai",
            "-ApiKey",
            "fmk_live_smoke_secret",
            "-GatewayJwtIssuer",
            "https://issuer.example",
            "-GatewayJwtAudience",
            "flow-memory-api",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "must be configured together when JWT smoke is configured" in result.stderr
    assert "FLOW_MEMORY_API_JWT_HS256_SECRET" in result.stderr


def test_render_blueprint_and_env_builder_match_level1_safety_contract() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")
    blueprint_env = _render_blueprint_env_values()
    deploy_env = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_s3_region="us-east-1",
        )
    }

    for key, expected in render_deploy.LEVEL1_EXPECTED_BOOLEAN_SETTINGS.items():
        assert blueprint_env.get(key) == expected
        assert deploy_env[key] == expected

    assert "FLOW_MEMORY_METRICS_ENABLED" not in blueprint
    assert "FLOW_MEMORY_TRACING_ENABLED" not in blueprint
    assert "FLOW_MEMORY_METRICS_ENABLED" not in deploy_env
    assert "FLOW_MEMORY_TRACING_ENABLED" not in deploy_env
    assert blueprint_env["FLOW_MEMORY_COMPUTE_METRICS_ENABLED"] == "true"
    assert blueprint_env["FLOW_MEMORY_COMPUTE_TRACING_ENABLED"] == "true"
    assert deploy_env["FLOW_MEMORY_COMPUTE_METRICS_ENABLED"] == "true"
    assert deploy_env["FLOW_MEMORY_COMPUTE_TRACING_ENABLED"] == "true"
    assert blueprint_env["FLOW_MEMORY_COMPUTE_AUDIT_CHECKPOINT_INTERVAL_SECONDS"] == "86400"
    assert deploy_env["FLOW_MEMORY_COMPUTE_AUDIT_CHECKPOINT_INTERVAL_SECONDS"] == "86400"


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
    with pytest.raises(SystemExit) as local_blocked:
        render_deploy.assert_https_public_url("https://localhost:8443")
    local_smoke = render_deploy.smoke_public("https://localhost:8443", "api-key")

    assert local_blocked.value.code == 33
    assert local_smoke["ok"] is False
    assert local_smoke["reason"] == "public_url_must_not_use_localhost"
    with pytest.raises(SystemExit) as placeholder_blocked:
        render_deploy.assert_https_public_url("https://api.yourdomain.com")
    placeholder_smoke = render_deploy.smoke_public("https://api.yourdomain.com", "api-key")

    assert placeholder_blocked.value.code == 33
    assert placeholder_smoke["ok"] is False
    assert placeholder_smoke["reason"] == "public_url_placeholder_not_allowed"
    with pytest.raises(SystemExit) as reserved_blocked:
        render_deploy.assert_https_public_url("https://api.example.com")
    reserved_smoke = render_deploy.smoke_public("https://api.example.test", "api-key")

    assert reserved_blocked.value.code == 33
    assert reserved_smoke["ok"] is False
    assert reserved_smoke["reason"] == "public_url_placeholder_not_allowed"


def test_render_deploy_blocks_unsafe_level1_env_overrides() -> None:
    with pytest.raises(SystemExit) as blocked:
        render_deploy.assert_level1_safety_settings(
            {
                "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED": "false",
                "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED": "true",
                "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED": "true",
            }
        )

    assert blocked.value.code == 38


def test_render_deploy_blocks_disabled_level1_control_planes(capsys: Any) -> None:
    with pytest.raises(SystemExit) as blocked:
        render_deploy.assert_level1_safety_settings(
            {
                "FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED": "false",
                "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED": "false",
                "FLOW_MEMORY_COMPUTE_METRICS_ENABLED": "false",
                "FLOW_MEMORY_COMPUTE_TRACING_ENABLED": "false",
            }
        )

    payload = json.loads(capsys.readouterr().out)
    invalid_keys = {item["key"] for item in payload["invalid_values"]}
    assert blocked.value.code == 38
    assert invalid_keys == {
        "FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED",
        "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED",
        "FLOW_MEMORY_COMPUTE_METRICS_ENABLED",
        "FLOW_MEMORY_COMPUTE_TRACING_ENABLED",
    }

def test_render_smoke_validates_gateway_jwt_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, str] | None, object | None]] = []
    audit_exporter = ""

    def _jwt_payload(auth_header: str) -> dict[str, object]:
        token = auth_header.removeprefix("Bearer ").strip()
        payload_segment = token.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        return cast(dict[str, object], json.loads(base64.urlsafe_b64decode(f"{payload_segment}{padding}").decode("utf-8")))

    def fake_call_json(
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: object | None = None,
    ) -> tuple[int, dict[str, object]]:
        request_headers = headers or {}
        calls.append((method, url, headers, body))
        plan_counter = sum(
            1
            for _method, called_url, _headers, _body in calls
            if called_url.endswith("/compute/plan")
        )
        scopes = request_headers.get("x-flow-memory-scopes", "")
        if url == "https://api.flowmemory.ai/":
            return 200, {"ok": True, "data": {"service": "Flow Memory Compute Market"}}
        if url.endswith("/compute/health") and request_headers.get("authorization"):
            payload = _jwt_payload(request_headers["authorization"])
            if str(payload.get("aud", "")).endswith("-wrong"):
                return 401, {"ok": False, "error": {"code": "auth.invalid"}}
            return 200, {"ok": True, "data": {"ok": True}}
        if url.endswith("/compute/health") and not request_headers.get("x-flow-memory-api-key"):
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
                        "require_managed_sql_in_production": True,
                        "redis_url_scheme": "rediss",
                        "dry_run_required": True,
                        "live_settlement_enabled": False,
                        "broadcast_enabled": False,
                        "private_key_inputs_allowed": False,
                        "audit_required": True,
                        "audit_export_required": True,
                        "stripe_checkout_enabled": False,
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
                        "decision_id": "decision_render_smoke",
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
            assert body == {"chain_id": "all"}
            return 200, {"ok": True, "data": {"ok": True, "manifest_hash": "manifest-hash", "event_count": 3}}
        if url.endswith("/admin/audit/export"):
            exporter_status = {"exporter": audit_exporter} if audit_exporter else {}
            return 200, {"ok": True, "data": {"immutable": True, "audit_exporter_status": exporter_status}}
        if url.endswith("/admin/storage/diagnostics"):
            return 200, {
                "ok": True,
                "data": {
                    "schema_verification": {
                        "ok": True,
                        "missing_tables": [],
                        "missing_indexes": [],
                        "required_table_count": 110,
                        "required_index_count": 1311,
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
        if url.endswith("/inference/opportunity-cost"):
            return 200, {"ok": True, "data": {"ok": True, "dry_run_only": True, "funds_moved": False}}
        if url.endswith("/inference/market/order-book"):
            if request_headers.get("authorization"):
                payload = _jwt_payload(request_headers["authorization"])
                assert payload.get("flow_memory_roles") == ["inference-admin"]
                assert scopes == "inference:read"
            return 200, {"ok": True, "data": {"ok": True, "dry_run_only": True, "funds_moved": False}}
        if url.endswith("/v1/chat/completions"):
            return 200, {
                "ok": True,
                "data": {
                    "object": "chat.completion",
                    "flow_memory": {"dry_run_only": True, "funds_moved": False},
                },
            }
        if url.endswith("/v1/responses"):
            return 200, {
                "ok": True,
                "data": {
                    "object": "response",
                    "flow_memory": {"dry_run_only": True, "funds_moved": False},
                },
            }
        if url.endswith("/v1/embeddings"):
            return 200, {
                "ok": True,
                "data": {
                    "object": "list",
                    "flow_memory": {"dry_run_only": True, "funds_moved": False},
                },
            }
        if url.endswith("/capacity/inventory"):
            return 200, {"ok": True, "data": {"ok": True, "dry_run_only": True, "funds_moved": False}}
        if url.endswith("/futures/markets"):
            return 200, {
                "ok": True,
                "data": {
                    "ok": True,
                    "dry_run_only": True,
                    "funds_moved": False,
                    "live_trading_enabled": False,
                },
            }
        if url.endswith("/compute/alerts") or url.endswith("/compute/telemetry"):
            return 200, {"ok": True, "data": {}}
        raise AssertionError(f"unexpected JSON call: {method} {url}")

    def fake_call_text(
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        calls.append((method, url, headers, None))
        return 200, "compute_plan_requests_total 1\n"

    monkeypatch.setattr(render_deploy, "call_json", fake_call_json)
    monkeypatch.setattr(render_deploy, "call_text", fake_call_text)

    result = render_deploy.smoke_public(
        "https://api.flowmemory.ai",
        "fmk_live_smoke_secret",
        {
            "FLOW_MEMORY_API_JWT_HS256_SECRET": "gateway-jwt-secret-with-at-least-32-characters",
            "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
            "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
        },
    )

    jwt_headers = [
        headers
        for _, _, headers, _ in calls
        if headers is not None and headers.get("authorization", "").startswith("Bearer ")
    ]
    assert result["ok"] is True
    assert result["statuses"]["jwt_health"] == 200
    assert result["statuses"]["jwt_wrong_audience"] == 401
    assert result["statuses"]["jwt_role_health"] == 200
    assert result["postgres_required_table_count"] == 110
    assert result["postgres_required_index_count"] == 1311
    assert result["plan_idempotent_replay"] is True
    assert result["dry_run_required"] is True
    assert result["live_settlement_enabled"] is False
    assert result["broadcast_enabled_readiness"] is False
    assert result["private_key_inputs_allowed"] is False
    assert result["audit_required"] is True
    assert result["audit_export_required"] is True
    assert result["stripe_checkout_enabled"] is False
    assert len(jwt_headers) == 3
    role_payloads = [_jwt_payload(headers["authorization"]) for headers in jwt_headers if headers is not None]
    assert any(payload.get("flow_memory_roles") == ["inference-admin"] for payload in role_payloads)
    assert jwt_headers[0]["x-flow-memory-scopes"] == "compute:read"
    authenticated_headers = [
        headers
        for _, _, headers, _ in calls
        if headers is not None
        and ("x-flow-memory-api-key" in headers or headers.get("authorization", "").startswith("Bearer "))
    ]
    nonce_pairs = [
        (headers.get("x-flow-memory-timestamp"), headers.get("x-flow-memory-nonce"))
        for headers in authenticated_headers
    ]

    assert len(authenticated_headers) == 16
    assert all(timestamp and nonce for timestamp, nonce in nonce_pairs)
    assert len(set(nonce_pairs)) == len(nonce_pairs)
    strict_audit_result = render_deploy.smoke_public(
        "https://api.flowmemory.ai",
        "fmk_live_smoke_secret",
        require_immutable_audit=True,
    )
    assert strict_audit_result["ok"] is False
    assert strict_audit_result["audit_export_s3_object_lock"] is False

    audit_exporter = "s3_object_lock"
    strict_s3_result = render_deploy.smoke_public(
        "https://api.flowmemory.ai",
        "fmk_live_smoke_secret",
        require_immutable_audit=True,
    )
    assert strict_s3_result["ok"] is True
    assert strict_s3_result["audit_export_s3_object_lock"] is True
    market_alpha_result = render_deploy.smoke_public(
        "https://api.flowmemory.ai",
        "fmk_live_smoke_secret",
        {
            "FLOW_MEMORY_API_JWT_HS256_SECRET": "gateway-jwt-secret-with-at-least-32-characters",
            "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
            "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
        },
        include_market_alpha=True,
    )
    assert market_alpha_result["ok"] is True
    assert market_alpha_result["include_market_alpha"] is True
    assert market_alpha_result["statuses"]["jwt_role_inference_order_book"] == 200
    assert market_alpha_result["market_alpha_statuses"] == {
        "inference_opportunity_cost": 200,
        "inference_order_book": 200,
        "openai_proxy": 200,
        "openai_responses": 200,
        "openai_embeddings": 200,
        "capacity_inventory": 200,
        "futures_markets": 200,
    }


def test_render_smoke_rejects_runtime_missing_managed_sql_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call_json(
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: object | None = None,
    ) -> tuple[int, dict[str, object]]:
        request_headers = headers or {}
        scopes = request_headers.get("x-flow-memory-scopes", "")
        if url == "https://api.flowmemory.ai/":
            return 200, {"ok": True, "data": {"service": "Flow Memory Compute Market"}}
        if url.endswith("/compute/health") and not request_headers.get("x-flow-memory-api-key"):
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
                        "require_managed_sql_in_production": False,
                        "redis_url_scheme": "rediss",
                        "dry_run_required": True,
                        "live_settlement_enabled": False,
                        "broadcast_enabled": False,
                        "private_key_inputs_allowed": False,
                        "audit_required": True,
                        "audit_export_required": True,
                        "stripe_checkout_enabled": False,
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
        if url.endswith("/compute/audit/export"):
            assert method == "POST"
            assert body == {"chain_id": "all"}
            return 200, {"ok": True, "data": {"ok": True, "manifest_hash": "manifest-hash", "event_count": 1}}
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
                        "required_table_count": 110,
                        "required_index_count": 1311,
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

    monkeypatch.setattr(render_deploy, "call_json", fake_call_json)
    monkeypatch.setattr(render_deploy, "call_text", lambda *_args, **_kwargs: (200, "compute_plan_requests_total 1\n"))

    result = render_deploy.smoke_public("https://api.flowmemory.ai", "fmk_live_smoke_secret")

    assert result["ok"] is False
    assert result["require_managed_sql_in_production"] is False


def test_render_blueprint_preserves_billing_safety_defaults() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED\n        value: false" in blueprint
    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_SECRET_KEY\n        sync: false" in blueprint
    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET\n        sync: false" in blueprint
    assert "      - key: FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS\n        value: 300" in blueprint
    public_script = (ROOT / "scripts" / "deploy_compute_market_public_level1.ps1").read_text(encoding="utf-8")
    assert "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED = 'false'" in public_script


def test_compute_market_deployment_runbook_covers_live_drills() -> None:
    deployment = (ROOT / "docs" / "ops" / "COMPUTE_MARKET_DEPLOYMENT.md").read_text(encoding="utf-8")
    launch = (ROOT / "docs" / "ops" / "COMPUTE_MARKET_LIVE_LAUNCH.md").read_text(encoding="utf-8")

    for required in (
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED=true",
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION=true",
        "FLOW_MEMORY_API_REQUIRE_SCOPES=true",
        "Managed PostgreSQL backup/PITR runbook",
        "Production Level 1 RPO is 15 minutes",
        "Managed PostgreSQL restore drill",
        "Blue/green migration rehearsal",
        "python scripts/validate_compute_market_live_infra.py",
        "FLOW_MEMORY_COMPUTE_SETTLEMENT_ENVIRONMENT",
    ):
        assert required in deployment

    for required in (
        "aws s3api put-object",
        "--object-lock-mode COMPLIANCE",
        "aws s3api get-object-retention",
        "aws s3api head-object",
        "python scripts/validate_compute_market_public_buildout.py --require-immutable-audit",
    ):
        assert required in launch


def test_public_smoke_scripts_verify_observability_endpoints() -> None:
    smoke_script = (ROOT / "scripts" / "smoke_compute_market_public.ps1").read_text(encoding="utf-8")
    render_script = (ROOT / "scripts" / "deploy_compute_market_render_level1.py").read_text(encoding="utf-8")

    assert 'Invoke-WebRequest -Uri "$baseUrl/metrics"' in smoke_script
    assert "compute_plan_requests_total" in smoke_script
    assert "Path '/compute/alerts'" in smoke_script
    assert "Path '/compute/telemetry'" in smoke_script
    assert '_smoke_api_headers(api_key_value, "compute:read", "metrics")' in render_script
    assert "Path '/compute/audit/export'" in smoke_script
    assert "audit_export_write_manifest_hash_present" in smoke_script
    assert '_smoke_api_headers(api_key_value, "compute:read", "alerts")' in render_script
    assert '_smoke_api_headers(api_key_value, "compute:read", "telemetry")' in render_script
    assert '"metrics": checks["metrics"][0]' in render_script
    assert '"alerts": checks["alerts"][0]' in render_script
    assert '"telemetry": checks["telemetry"][0]' in render_script
    assert '"audit_export_write": checks["audit_export_write"][0]' in render_script
    assert '"audit_export_write_manifest_hash_present": bool(audit_export_write_payload.get("manifest_hash"))' in render_script
    assert "Get-PublicUrlBlockReason" in smoke_script
    assert "public_url_placeholder_not_allowed" in smoke_script
    assert "example\\.test" in smoke_script
    assert "example\\.invalid" in smoke_script
    assert "public_url_must_use_global_host" in smoke_script
    assert "RequireImmutableAudit" in smoke_script
    assert "s3_object_lock" in smoke_script
    assert "deployments/compute-market/prometheus-alerts.yml" in render_script
    assert 'checks["jwt_health"] = call_json(' in render_script
    assert 'checks["jwt_wrong_audience"] = call_json(' in render_script
    assert "_smoke_nonce_headers" in render_script
    assert "x-flow-memory-nonce" in smoke_script
    assert "Get-ApiKeyBlockReason" in smoke_script
    assert "api_key_placeholder_not_allowed" in smoke_script
    assert "require_managed_sql_in_production" in smoke_script
    assert "require_managed_sql_in_production" in render_script
    for expected in (
        "production_safety_defaults.dry_run_required -eq $true",
        "production_safety_defaults.live_settlement_enabled -eq $false",
        "production_safety_defaults.broadcast_enabled -eq $false",
        "production_safety_defaults.private_key_inputs_allowed -eq $false",
        "production_safety_defaults.stripe_checkout_enabled -eq $false",
        "production_safety_defaults.audit_required -eq $true",
        "production_safety_defaults.audit_export_required -eq $true",
    ):
        assert expected in smoke_script
    for expected in (
        '"stripe_checkout_enabled": safety.get("stripe_checkout_enabled")',
        '"audit_required": safety.get("audit_required")',
        '"audit_export_required": safety.get("audit_export_required")',
    ):
        assert expected in render_script

def test_public_smoke_rejects_placeholder_api_key_before_network() -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public smoke preflight validation")
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "smoke_compute_market_public.ps1"),
            "-ApiUrl",
            "https://api.flowmemory.ai",
            "-ApiKey",
            "CHANGEME-high-entropy-api-key",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "api_key_placeholder_not_allowed" in result.stderr


def test_named_render_powershell_wrapper_refuses_to_fake_success() -> None:
    wrapper = (ROOT / "scripts" / "deploy_render_compute_market.ps1").read_text(encoding="utf-8")

    assert "deploy_compute_market_render_level1.py" in wrapper
    assert "RENDER_API_KEY" in wrapper
    assert "RENDER_OWNER_ID" in wrapper
    assert "RENDER_ALLOW_FREE_PLANS" in wrapper
    assert "render_helper_missing" in wrapper
    assert "env_file_missing" in wrapper
    assert "python_missing" in wrapper
    assert "exit $LASTEXITCODE" in wrapper

def test_named_render_powershell_wrapper_blocks_missing_env_file(tmp_path: Path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for Render wrapper validation")
    assert powershell is not None

    missing_env_file = tmp_path / "missing-render.env"
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "deploy_render_compute_market.ps1"),
            "-EnvFile",
            str(missing_env_file),
            "-RenderApiKey",
            "render_live_test_key",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode == 11, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed_deployment"
    assert payload["reason"] == "env_file_missing"
    assert payload["missing_values"] == [str(missing_env_file)]


def test_render_placeholder_detection_rejects_generic_secret_placeholders() -> None:
    assert render_deploy.has_placeholder("<production-secret>") is True
    assert render_deploy.has_placeholder("CHANGEME-high-entropy-api-key") is True
    assert render_deploy.has_placeholder("managed-postgres-host") is True
    assert render_deploy.has_placeholder("fmk_live_realistic_secret_value") is False
    assert render_deploy.api_key_block_reason("api-key") == "api_key_weak_value_not_allowed"
    assert render_deploy.api_key_block_reason("fmk_live_realistic_secret_value") == ""


def test_public_powershell_preflight_rejects_placeholders_before_deploy() -> None:
    deploy_script = (ROOT / "scripts" / "deploy_compute_market_public_level1.ps1").read_text(encoding="utf-8")

    assert "$renderApiKey -match $placeholderPattern" in deploy_script
    assert "<[^>]*>" in deploy_script
    assert "high-entropy-api-key" in deploy_script
    assert "$weakApiKeys" in deploy_script
    assert "$placeholders.Add('FLOW_MEMORY_PUBLIC_API_URL')" in deploy_script
    assert "$placeholders.Add('RENDER_KEYVALUE_IP_ALLOWLIST')" in deploy_script
    assert "blocked_invalid_public_url" in deploy_script
    assert "Get-PublicUrlBlockReason" in deploy_script
    assert "public_url_must_use_global_host" in deploy_script
    assert "blocked_incomplete_gateway_jwt" in deploy_script
    assert "blocked_weak_gateway_jwt_secret" in deploy_script
    assert "blocked_insecure_gateway_jwt_issuer" in deploy_script
    assert "blocked_invalid_gateway_jwt_leeway" in deploy_script
    assert "'-RequireImmutableAudit'" in deploy_script
    assert "FLOW_MEMORY_COMPUTE_METRICS_ENABLED = 'true'" in deploy_script
    assert "FLOW_MEMORY_COMPUTE_TRACING_ENABLED = 'true'" in deploy_script

def test_public_powershell_preflight_rejects_private_public_url(tmp_path: Path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public deployment preflight validation")
    assert powershell is not None
    env_file = tmp_path / "private-url.env"
    env_file.write_text(
        "\n".join(
            (
                "FLOW_MEMORY_API_KEY=fmk_live_test_secret",
                "FLOW_MEMORY_PUBLIC_API_URL=https://127.0.0.1:8443",
            )
        )
        + "\n",
        encoding="utf-8",
    )

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
            "-Mode",
            "validate-only",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode == 14, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_invalid_public_url"
    assert payload["reason"] == "public_url_must_use_global_host"
    assert payload["public_url"] == "https://127.0.0.1:8443"


def test_public_powershell_preflight_rejects_weak_api_key(tmp_path: Path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public deployment preflight validation")
    assert powershell is not None
    env_file = tmp_path / "weak-api-key.env"
    env_file.write_text(
        "\n".join(
            (
                "FLOW_MEMORY_API_KEY=prod-key",
                "FLOW_MEMORY_PUBLIC_API_URL=https://api.flowmemory.ai",
            )
        )
        + "\n",
        encoding="utf-8",
    )

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
            "-Mode",
            "validate-only",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_missing_values"
    assert "FLOW_MEMORY_API_KEY" in payload["placeholder_values"]


def test_public_powershell_preflight_rejects_placeholder_gateway_jwt_secret(tmp_path: Path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is required for public deployment preflight validation")
    assert powershell is not None
    env_values = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "fmk_live_test_secret",
            "postgresql://db.example.com:5432/flow_memory",
            "rediss://redis.example.com:6379/0",
            public_api_url="https://api.flowmemory.ai",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_immutable_required="true",
            audit_export_object_lock_mode="COMPLIANCE",
            audit_export_retention_days="30",
            audit_export_s3_region="us-east-1",
        )
    }
    env_values["FLOW_MEMORY_API_JWT_HS256_SECRET"] = "CHANGEME-gateway-jwt-secret-with-at-least-32-characters"
    env_values["FLOW_MEMORY_API_JWT_ISSUER"] = "https://issuer.example"
    env_values["FLOW_MEMORY_API_JWT_AUDIENCE"] = "flow-memory-api"
    env_file = tmp_path / "placeholder-gateway-jwt.env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in env_values.items()) + "\n",
        encoding="utf-8",
    )

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
            "-Mode",
            "validate-only",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert result.returncode == 16, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_incomplete_gateway_jwt"
    assert payload["missing_values"] == ["FLOW_MEMORY_API_JWT_HS256_SECRET"]


def test_public_buildout_validator_requires_observability_endpoints() -> None:
    validator_script = (ROOT / "scripts" / "validate_compute_market_public_buildout.py").read_text(encoding="utf-8")

    assert 'checks["metrics"] = call_text("GET", f"{base}/metrics", headers_read)' in validator_script
    assert 'checks["alerts"] = call_json("GET", f"{base}/compute/alerts", headers_read)' in validator_script
    assert 'checks["telemetry"] = call_json("GET", f"{base}/compute/telemetry", headers_read)' in validator_script
    assert '"compute_plan_requests_total" in checks["metrics"][1]' in validator_script
    assert 'checks[name][0] == 200 and checks[name][1].get("ok") is True' in validator_script
    assert "nonce_headers(headers or {}, label=f\"{method}-json\")" in validator_script


def test_api_server_cli_rejects_public_bind_without_api_key() -> None:
    with pytest.raises(SystemExit):
        build_http_api_config(["--host", "0.0.0.0"], env={})


def test_api_server_cli_rejects_public_bind_without_scope_enforcement() -> None:
    with pytest.raises(SystemExit):
        build_http_api_config(["--host", "0.0.0.0", "--api-key", "dev-key"], env={})
    with pytest.raises(SystemExit):
        build_http_api_config(
            ["--host", "0.0.0.0"],
            env={
                "FLOW_MEMORY_API_JWT_HS256_SECRET": "gateway-shared-secret",
                "FLOW_MEMORY_API_JWT_ISSUER": "https://issuer.example",
                "FLOW_MEMORY_API_JWT_AUDIENCE": "flow-memory-api",
            },
        )


def test_api_server_cli_public_bind_override_allows_private_proxy_auth() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--allow-unauthenticated-public-bind"],
        env={},
    )

    assert config.host == "0.0.0.0"
    assert config.api_key == ""
    assert config.require_scopes is False


def test_api_server_cli_accepts_public_bind_with_api_key_and_scopes() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--api-key", "dev-key", "--require-scopes"],
        env={},
    )

    assert config.host == "0.0.0.0"
    assert config.api_key == "dev-key"
    assert config.require_scopes is True
    assert "compute:read" in config.api_key_scopes
    assert "compute:plan" in config.api_key_scopes


def test_api_server_cli_accepts_public_bind_with_limited_api_key_scopes() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--api-key", "dev-key", "--require-scopes"],
        env={"FLOW_MEMORY_API_KEY_SCOPES": "compute:read compute:plan"},
    )

    assert config.host == "0.0.0.0"
    assert config.api_key == "dev-key"
    assert config.api_key_scopes == ("compute:plan", "compute:read")


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
    assert config.jwt_require_tenant is False
    tenant_required_config = build_http_api_config(
        ["--host", "0.0.0.0", "--require-scopes"],
        env={
            "FLOW_MEMORY_API_JWT_HS256_SECRET": "gateway-shared-secret",
            "FLOW_MEMORY_API_JWT_REQUIRE_TENANT": "true",
        },
    )
    assert tenant_required_config.jwt_require_tenant is True


def test_api_server_cli_builds_redis_nonce_guard_from_public_env() -> None:
    config = build_http_api_config(
        ["--host", "0.0.0.0", "--api-key", "dev-key", "--require-scopes"],
        env={
            "FLOW_MEMORY_API_ENABLE_NONCE_CHECK": "true",
            "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND": "redis",
            "FLOW_MEMORY_COMPUTE_REDIS_URL": "rediss://cache.example:6379/0",
            "FLOW_MEMORY_API_NONCE_REQUIRE_TLS": "true",
            "FLOW_MEMORY_API_NONCE_FAIL_CLOSED": "true",
        },
    )

    assert config.enable_nonce_check is True
    assert config.nonce_replay_backend == "redis"
    assert config.nonce_redis_url == "rediss://cache.example:6379/0"
    assert config.nonce_require_tls is True
    assert config.nonce_fail_closed is True


def test_api_server_cli_builds_provider_callback_ip_allowlist_from_env_and_cli() -> None:
    env_config = build_http_api_config(
        ["--host", "0.0.0.0", "--api-key", "dev-key", "--require-scopes"],
        env={"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "203.0.113.0/24,2001:db8::1"},
    )
    cli_config = build_http_api_config(
        [
            "--host",
            "0.0.0.0",
            "--api-key",
            "dev-key",
            "--require-scopes",
            "--provider-callback-ip-allowlist",
            "198.51.100.10",
        ],
        env={"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "203.0.113.0/24"},
    )

    assert env_config.provider_callback_ip_allowlist == ("203.0.113.0/24", "2001:db8::1")
    assert cli_config.provider_callback_ip_allowlist == ("198.51.100.10",)

    with pytest.raises(SystemExit):
        build_http_api_config(
            ["--host", "0.0.0.0", "--api-key", "dev-key", "--provider-callback-ip-allowlist", "not-an-ip"],
            env={},
        )


def test_render_deploy_supports_render_disk_local_audit_and_s3_object_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    local_uri = "/var/lib/flow-memory/audit/compute-market.ndjson"

    assert render_deploy.audit_export_uri_from_env({}) == local_uri
    assert render_deploy.audit_export_uri_from_env({"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": "s3://changeme-audit/compute-market"}) == local_uri
    assert render_deploy.audit_export_uri_from_env({"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": local_uri}) == local_uri
    with pytest.raises(SystemExit) as missing_region:
        render_deploy.audit_export_s3_region_from_env(
            {"FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": "s3://flow-memory-audit/compute-market"},
            "s3://flow-memory-audit/compute-market",
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
    assert render_deploy.audit_export_s3_region_from_env({}, "s3://flow-memory-shell-audit/compute-market") == "us-west-2"

    local_env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri=local_uri,
        )
    }
    s3_env_vars = {
        item["key"]: item["value"]
        for item in render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_object_lock_mode="COMPLIANCE",
            audit_export_retention_days="365",
            audit_export_immutable_required="true",
            audit_export_s3_region="us-east-1",
        )
    }

    assert missing_region.value.code == 23
    assert local_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI"] == local_uri
    assert local_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED"] == "false"
    assert local_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE"] == ""
    assert local_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION"] == ""
    assert s3_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI"] == "s3://flow-memory-audit/compute-market"
    assert s3_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED"] == "true"
    assert s3_env_vars["FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION"] == "true"
    assert s3_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE"] == "COMPLIANCE"
    assert s3_env_vars["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION"] == "us-east-1"
    assert s3_env_vars["FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED"] == "false"
    assert s3_env_vars["FLOW_MEMORY_BILLING_STRIPE_API_BASE_URL"] == "https://api.stripe.com"
    assert s3_env_vars["FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS"] == "300"
    assert s3_env_vars["FLOW_MEMORY_BILLING_STRIPE_SECRET_KEY"] == ""
    assert s3_env_vars["FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_SECRET"] == ""
    assert s3_env_vars["FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST"] == ""
    assert s3_env_vars["FLOW_MEMORY_API_JWT_HS256_SECRET"] == ""
    assert s3_env_vars["FLOW_MEMORY_API_JWT_ISSUER"] == ""
    assert s3_env_vars["FLOW_MEMORY_API_JWT_AUDIENCE"] == ""
    assert s3_env_vars["FLOW_MEMORY_API_JWT_LEEWAY_SECONDS"] == "60"
    assert s3_env_vars["FLOW_MEMORY_API_ENABLE_NONCE_CHECK"] == "true"
    assert s3_env_vars["FLOW_MEMORY_API_NONCE_REPLAY_BACKEND"] == "redis"
    assert s3_env_vars["FLOW_MEMORY_API_NONCE_FAIL_CLOSED"] == "true"
    assert s3_env_vars["FLOW_MEMORY_API_NONCE_REQUIRE_TLS"] == "true"


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
    with pytest.raises(SystemExit) as lowercase_placeholder:
        render_deploy.provider_callback_ip_allowlist_from_env(
            {"FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "changeme-provider-cidr"}
        )

    assert missing.value.code == 30
    assert world_open.value.code == 31
    assert placeholder.value.code == 31
    assert lowercase_placeholder.value.code == 31

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


def test_render_deploy_prefers_internal_keyvalue_connection_string() -> None:
    redis_url = render_deploy.select_managed_redis_url(
        {
            "internalConnectionString": "redis://internal-render-redis:6379",
            "externalConnectionString": "rediss://external-render-redis:6380",
        }
    )

    assert redis_url == "redis://internal-render-redis:6379"


def test_render_deploy_blocks_insecure_keyvalue_connection_info() -> None:
    with pytest.raises(SystemExit) as blocked:
        render_deploy.select_managed_redis_url(
            {
                "connectionString": "http://not-redis.example",
            }
        )

    assert blocked.value.code == 24

def test_render_keyvalue_creation_defaults_to_non_world_open_external_tls_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_bodies: list[dict[str, object]] = []

    def fake_find_named(api_key: str, path: str, envelope: str, owner_id: str, name: str) -> None:
        return None

    def fake_render_request(
        api_key: str,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if method == "POST" and path == "/key-value":
            assert body is not None
            created_body = dict(body)
            created_bodies.append(created_body)
            return {"id": f"kv_{len(created_bodies)}", **created_body}
        raise AssertionError(f"unexpected Render call: {method} {path}")

    monkeypatch.setattr(render_deploy, "find_named", fake_find_named)
    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)

    default_created = render_deploy.ensure_keyvalue("render-key", "owner", "oregon")
    monkeypatch.setattr(render_deploy, "DEFAULT_KEYVALUE_IP_ALLOWLIST", "203.0.113.10/32,198.51.100.0/24")
    explicit_created = render_deploy.ensure_keyvalue("render-key", "owner", "oregon")

    assert default_created["ipAllowList"] == [
        {"cidrBlock": "0.0.0.0/32", "description": "flow-memory-compute-market-redis-tls"},
    ]
    assert explicit_created["ipAllowList"] == [
        {"cidrBlock": "203.0.113.10/32", "description": "flow-memory-compute-market-redis-tls"},
        {"cidrBlock": "198.51.100.0/24", "description": "flow-memory-compute-market-redis-tls"},
    ]

def test_render_deploy_upgrades_existing_free_resources_and_attaches_audit_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, Mapping[str, object] | None]] = []

    def fake_find_named(
        api_key: str,
        path: str,
        envelope: str,
        owner_id: str,
        name: str,
    ) -> dict[str, object] | None:
        if path == "/postgres":
            return {"id": "pg_free", "name": name, "plan": "free"}
        if path == "/key-value":
            return {"id": "kv_free", "name": name, "plan": "free"}
        if path == "/services":
            return {"id": "srv_free", "name": name, "serviceDetails": {"plan": "free"}}
        return None

    def fake_render_request(
        api_key: str,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object] | list[dict[str, object]]:
        calls.append((method, path, body))
        if method == "PATCH" and path == "/postgres/pg_free":
            assert body == {"plan": "starter"}
            return {"id": "pg_free", "plan": "starter"}
        if method == "PATCH" and path == "/key-value/kv_free":
            assert body is not None
            assert body["plan"] == "starter"
            assert body["persistenceMode"] == "journal_snapshot"
            assert body["maxmemoryPolicy"] == "noeviction"
            return {"id": "kv_free", "plan": "starter"}
        if method == "GET" and path == "/disks?serviceId=srv_free&limit=100":
            return []
        if method == "POST" and path == "/disks":
            assert body == {
                "name": "compute-market-audit",
                "mountPath": "/var/lib/flow-memory/audit",
                "sizeGB": 10,
                "serviceId": "srv_free",
            }
            return {"disk": {"id": "disk_1", **dict(body)}}
        if method == "PATCH" and path == "/services/srv_free":
            assert body is not None
            service_details = body["serviceDetails"]
            assert isinstance(service_details, Mapping)
            assert service_details["plan"] == "starter"
            return {"id": "srv_free"}
        if method == "PUT" and path == "/services/srv_free/env-vars":
            return {}
        if method == "GET" and path == "/services/srv_free":
            return {"id": "srv_free", "serviceDetails": {"plan": "starter"}}
        raise AssertionError(f"unexpected Render call: {method} {path}")

    monkeypatch.setattr(render_deploy, "find_named", fake_find_named)
    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)

    postgres = render_deploy.ensure_postgres("render-key", "owner", "oregon", plan="starter")
    keyvalue = render_deploy.ensure_keyvalue(
        "render-key",
        "owner",
        "oregon",
        plan="starter",
        ip_allowlist="0.0.0.0/32",
    )
    service = render_deploy.ensure_service(
        "render-key",
        "owner",
        "oregon",
        "https://github.com/FlowmemoryAI/flow-memory",
        "main",
        [render_deploy.env_var("FLOW_MEMORY_API_KEY", "fmk_test")],
        plan="starter",
        enable_disk=True,
    )

    assert postgres["plan"] == "starter"
    assert keyvalue["plan"] == "starter"
    assert service["serviceDetails"]["plan"] == "starter"
    assert ("POST", "/disks", {
        "name": "compute-market-audit",
        "mountPath": "/var/lib/flow-memory/audit",
        "sizeGB": 10,
        "serviceId": "srv_free",
    }) in calls


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


def test_public_powershell_render_placeholder_gate_requires_render_api_key(tmp_path: Path) -> None:
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
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=/var/lib/flow-memory/audit/compute-market.ndjson",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.pop("RENDER_API_KEY", None)
    assert powershell is not None
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

    assert result.returncode == 20, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_missing_render_auth"
    assert payload["missing_values"] == ["RENDER_API_KEY"]



def test_render_deploy_main_uses_env_file_render_provisioning_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / "render.env"
    env_file.write_text(
        "\n".join(
            [
                "RENDER_API_KEY=render_live_key_from_env_file",
                "RENDER_OWNER_ID=owner_from_env_file",
                "RENDER_REGION=frankfurt",
                "RENDER_POSTGRES_PLAN=pro",
                "RENDER_KEYVALUE_PLAN=pro",
                "RENDER_SERVICE_PLAN=professional",
                "RENDER_KEYVALUE_IP_ALLOWLIST=203.0.113.10/32",
                "RENDER_BRANCH=main",
                "RENDER_REPO_URL=https://github.com/FlowmemoryAI/flow-memory",
                "RENDER_ENABLE_DISK=true",
                "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true",
                "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION=true",
                "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED=false",
                "FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE=COMPLIANCE",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS=365",
                "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=s3://flow-memory-audit/compute-market",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION=us-east-1",
                "FLOW_MEMORY_PUBLIC_API_URL=https://api.flowmemory.example",
            ]
        ),
        encoding="utf-8",
    )
    calls: dict[str, Any] = {}

    def fake_find_named(
        api_key: str,
        path: str,
        envelope: str,
        owner_id: str,
        name: str,
    ) -> dict[str, str] | None:
        calls["existing_service_lookup"] = {
            "api_key": api_key,
            "path": path,
            "envelope": envelope,
            "owner_id": owner_id,
            "name": name,
        }
        return {"id": "srv_existing"} if path == "/services" else None


    def fake_service_env_value(api_key: str, service_id: str, key: str) -> str:
        calls["existing_api_key_lookup"] = {
            "api_key": api_key,
            "service_id": service_id,
            "key": key,
        }
        return "fmk_existing_render_service_key" if key == "FLOW_MEMORY_API_KEY" else ""


    def fake_ensure_postgres(api_key: str, owner_id: str, region: str, *, plan: str) -> dict[str, str]:
        calls["postgres"] = {"api_key": api_key, "owner_id": owner_id, "region": region, "plan": plan}
        return {"id": "pg_1"}

    def fake_ensure_keyvalue(
        api_key: str,
        owner_id: str,
        region: str,
        *,
        plan: str,
        ip_allowlist: str | None = None,
    ) -> dict[str, str]:
        calls["keyvalue"] = {
            "api_key": api_key,
            "owner_id": owner_id,
            "region": region,
            "plan": plan,
            "ip_allowlist": ip_allowlist,
        }
        return {"id": "kv_1"}

    def fake_wait_available(api_key: str, path: str, resource_id: str, label: str) -> dict[str, str]:
        return {"id": resource_id, "label": label, "path": path}

    def fake_render_request(
        api_key: str,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if method == "GET" and path == "/postgres/pg_1/connection-info":
            return {"internalConnectionString": "postgresql://postgres.internal/flow_memory"}
        if method == "GET" and path == "/key-value/kv_1/connection-info":
            return {"externalConnectionString": "rediss://redis.external:6379/0"}
        if method == "PUT" and path == "/services/srv_1/env-vars":
            calls["env_put"] = {"api_key": api_key, "body": body}
            return {}
        raise AssertionError(f"unexpected Render call: {method} {path}")

    def fake_ensure_service(
        api_key: str,
        owner_id: str,
        region: str,
        repo: str,
        branch: str,
        env_vars: list[dict[str, str]],
        *,
        plan: str,
        enable_disk: bool,
    ) -> dict[str, object]:
        calls["service"] = {
            "api_key": api_key,
            "owner_id": owner_id,
            "region": region,
            "repo": repo,
            "branch": branch,
            "plan": plan,
            "enable_disk": enable_disk,
            "env_vars": env_vars,
        }
        return {"id": "srv_1", "serviceDetails": {"url": "flow-memory-api.onrender.com"}}

    monkeypatch.setattr(sys, "argv", ["deploy", "--env-file", str(env_file)])
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    monkeypatch.setattr(render_deploy, "ensure_postgres", fake_ensure_postgres)
    monkeypatch.setattr(render_deploy, "ensure_keyvalue", fake_ensure_keyvalue)
    monkeypatch.setattr(render_deploy, "wait_available", fake_wait_available)
    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)
    monkeypatch.setattr(render_deploy, "ensure_service", fake_ensure_service)
    monkeypatch.setattr(render_deploy, "find_named", fake_find_named)
    monkeypatch.setattr(render_deploy, "service_env_value", fake_service_env_value)
    monkeypatch.setattr(render_deploy, "trigger_service_deploy", lambda api_key, service_id: {"id": "deploy_1"})
    def fake_smoke_public(
        url: str,
        api_key: str,
        gateway_jwt: Mapping[str, str] | None = None,
        *,
        require_immutable_audit: bool = False,
        include_market_alpha: bool = False,
    ) -> dict[str, object]:
        calls["smoke"] = {
            "url": url,
            "api_key": api_key,
            "gateway_jwt": gateway_jwt,
            "require_immutable_audit": require_immutable_audit,
            "include_market_alpha": include_market_alpha,
        }
        return {"ok": True}

    monkeypatch.setattr(render_deploy, "smoke_public", fake_smoke_public)
    monkeypatch.setattr(render_deploy, "assert_branch_is_publishable", lambda branch: None)

    with pytest.raises(SystemExit) as completed:
        render_deploy.main()

    payload = json.loads(capsys.readouterr().out)

    assert completed.value.code == 0
    assert payload["status"] == "public_level_1_live"
    assert payload["postgres"] == "managed_render_postgres:pro"
    assert payload["redis"] == "managed_render_keyvalue:pro"
    assert payload["service_plan"] == "professional"
    assert payload["public_url"] == "https://flow-memory-api.onrender.com"
    assert calls["postgres"] == {
        "api_key": "render_live_key_from_env_file",
        "owner_id": "owner_from_env_file",
        "region": "frankfurt",
        "plan": "pro",
    }
    assert calls["keyvalue"]["ip_allowlist"] == "203.0.113.10/32"
    assert calls["service"]["plan"] == "professional"
    assert calls["service"]["enable_disk"] is True
    assert calls["env_put"]["api_key"] == "render_live_key_from_env_file"
    env_vars_by_key = {item["key"]: item["value"] for item in calls["env_put"]["body"]}
    assert env_vars_by_key["FLOW_MEMORY_PUBLIC_API_URL"] == "https://flow-memory-api.onrender.com"
    assert env_vars_by_key["FLOW_MEMORY_API_KEY"] == "fmk_existing_render_service_key"
    assert "compute:read" in env_vars_by_key["FLOW_MEMORY_API_KEY_SCOPES"]
    assert "compute:admin" in env_vars_by_key["FLOW_MEMORY_API_KEY_SCOPES"]
    assert "inference:plan" in env_vars_by_key["FLOW_MEMORY_API_KEY_SCOPES"]
    assert "inference:proxy" in env_vars_by_key["FLOW_MEMORY_API_KEY_SCOPES"]
    assert calls["smoke"]["api_key"] == "fmk_existing_render_service_key"
    assert calls["smoke"]["url"] == "https://flow-memory-api.onrender.com"
    assert calls["smoke"]["require_immutable_audit"] is True
    assert calls["smoke"]["include_market_alpha"] is False



def test_render_deploy_main_fails_closed_when_public_smoke_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / "render.env"
    env_file.write_text(
        "\n".join(
            [
                "RENDER_API_KEY=render_live_key_from_env_file",
                "RENDER_OWNER_ID=owner_from_env_file",
                "RENDER_REGION=frankfurt",
                "RENDER_POSTGRES_PLAN=pro",
                "RENDER_KEYVALUE_PLAN=pro",
                "RENDER_SERVICE_PLAN=professional",
                "RENDER_KEYVALUE_IP_ALLOWLIST=203.0.113.10/32",
                "RENDER_BRANCH=main",
                "RENDER_REPO_URL=https://github.com/FlowmemoryAI/flow-memory",
                "RENDER_ENABLE_DISK=true",
                "FLOW_MEMORY_API_KEY=fmk_live_test_secret",
                "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true",
                "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION=true",
                "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED=false",
                "FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED=true",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE=COMPLIANCE",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS=365",
                "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED=false",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=s3://flow-memory-audit/compute-market",
                "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION=us-east-1",
                "FLOW_MEMORY_PUBLIC_API_URL=https://api.flowmemory.example",
            ]
        ),
        encoding="utf-8",
    )
    smoke_calls: list[dict[str, object]] = []

    def fake_ensure_postgres(api_key: str, owner_id: str, region: str, *, plan: str) -> dict[str, str]:
        return {"id": "pg_1"}

    def fake_ensure_keyvalue(
        api_key: str,
        owner_id: str,
        region: str,
        *,
        plan: str,
        ip_allowlist: str | None = None,
    ) -> dict[str, str]:
        return {"id": "kv_1"}

    def fake_wait_available(api_key: str, path: str, resource_id: str, label: str) -> dict[str, str]:
        return {"id": resource_id, "label": label, "path": path}

    def fake_render_request(
        api_key: str,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if method == "GET" and path == "/postgres/pg_1/connection-info":
            return {"internalConnectionString": "postgresql://postgres.internal/flow_memory"}
        if method == "GET" and path == "/key-value/kv_1/connection-info":
            return {"externalConnectionString": "rediss://redis.external:6379/0"}
        if method == "PUT" and path == "/services/srv_1/env-vars":
            return {}
        raise AssertionError(f"unexpected Render call: {method} {path}")

    def fake_ensure_service(
        api_key: str,
        owner_id: str,
        region: str,
        repo: str,
        branch: str,
        env_vars: list[dict[str, str]],
        *,
        plan: str,
        enable_disk: bool,
    ) -> dict[str, object]:
        return {"id": "srv_1", "serviceDetails": {"url": "flow-memory-api.onrender.com"}}

    def fake_smoke_public(
        url: str,
        api_key: str,
        gateway_jwt: Mapping[str, str] | None = None,
        *,
        require_immutable_audit: bool = False,
        include_market_alpha: bool = False,
    ) -> dict[str, object]:
        smoke_calls.append(
            {
                "url": url,
                "api_key": api_key,
                "require_immutable_audit": require_immutable_audit,
                "include_market_alpha": include_market_alpha,
            }
        )
        return {"ok": False, "reason": "require_managed_sql_in_production is False"}

    monkeypatch.setattr(sys, "argv", ["deploy", "--env-file", str(env_file)])
    monkeypatch.setattr(render_deploy, "ensure_postgres", fake_ensure_postgres)
    monkeypatch.setattr(render_deploy, "ensure_keyvalue", fake_ensure_keyvalue)
    monkeypatch.setattr(render_deploy, "wait_available", fake_wait_available)
    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)
    monkeypatch.setattr(render_deploy, "ensure_service", fake_ensure_service)
    monkeypatch.setattr(render_deploy, "trigger_service_deploy", lambda api_key, service_id: {"id": "deploy_1"})
    monkeypatch.setattr(render_deploy, "smoke_public", fake_smoke_public)
    monkeypatch.setattr(render_deploy, "assert_branch_is_publishable", lambda branch: None)
    monkeypatch.setattr(render_deploy.time, "sleep", lambda seconds: None)

    with pytest.raises(SystemExit) as failed:
        render_deploy.main()

    payload = json.loads(capsys.readouterr().out)

    assert failed.value.code == 34
    assert payload["status"] == "failed_public_smoke_tests"
    assert payload["public_url"] == "https://flow-memory-api.onrender.com"
    assert payload["smoke"]["ok"] is False
    assert payload["smoke"]["reason"] == "require_managed_sql_in_production is False"
    assert smoke_calls
    assert smoke_calls[0]["api_key"] == "fmk_live_test_secret"
    assert smoke_calls[0]["require_immutable_audit"] is True

def test_render_env_builder_blocks_incomplete_immutable_s3_audit_settings() -> None:
    with pytest.raises(SystemExit) as blocked:
        render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "rediss://redis/0",
            audit_export_uri="s3://flow-memory-audit/compute-market",
            audit_export_object_lock_mode="",
            audit_export_retention_days="0",
            audit_export_immutable_required="true",
            audit_export_s3_region="us-east-1",
        )

    assert blocked.value.code == 23

def test_render_env_builder_blocks_insecure_redis_and_non_postgres_urls() -> None:
    with pytest.raises(SystemExit) as redis_blocked:
        render_deploy.build_env_vars(
            "dev-key",
            "postgresql://db/flow_memory",
            "http://redis/0",
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


def test_render_deploy_ignores_placeholder_public_api_url_for_generated_render_url() -> None:
    assert render_deploy.public_api_url_from_env({"FLOW_MEMORY_PUBLIC_API_URL": "https://api.yourdomain.com"}) == ""


def test_render_deploy_fallback_waits_for_new_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {"deploy_list": 0, "waited_for": ""}

    def fake_render_request(
        api_key: str,
        method: str,
        path: str,
        body: Mapping[str, object] | None = None,
    ) -> object:
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

    def fake_wait_deploy_live(api_key: str, service_id: str, deploy_id: str) -> dict[str, str]:
        calls["waited_for"] = deploy_id
        return {"id": deploy_id, "status": "live"}

    monkeypatch.setattr(render_deploy, "render_request", fake_render_request)
    monkeypatch.setattr(render_deploy, "wait_deploy_live", fake_wait_deploy_live)

    result = render_deploy.trigger_service_deploy("render-key", "srv_1")

    assert calls["waited_for"] == "deploy_new"
    assert result["status"] == "live"
