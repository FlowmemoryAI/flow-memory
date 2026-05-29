from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from flow_memory.compute_market.storage import migration_plan


PUBLIC_TASK = "Flow Memory Compute Market public production buildout validation"
_PLACEHOLDER_PUBLIC_URL_FRAGMENTS = (
    "<",
    ">",
    "changeme",
    "your-domain",
)
_PLACEHOLDER_PUBLIC_HOST_SUFFIXES = (
    "yourdomain.com",
    "example.com",
    "example.test",
    "example.invalid",
    "test",
    "invalid",
)
_PLACEHOLDER_API_KEY_FRAGMENTS = (
    "<",
    ">",
    "changeme",
    "high-entropy-api-key",
)
_WEAK_API_KEYS = frozenset(("api-key", "dev-key", "prod-key", "test", "secret", "password"))
_MIN_POSTGRES_SCHEMA_TABLE_COUNT_FALLBACK = 110
_MIN_POSTGRES_SCHEMA_INDEX_COUNT_FALLBACK = 1311
_LEVEL1_EXPECTED_BOOLEAN_SETTINGS = {
    "FLOW_MEMORY_API_ENABLE_NONCE_CHECK": "true",
    "FLOW_MEMORY_API_NONCE_FAIL_CLOSED": "true",
    "FLOW_MEMORY_API_NONCE_REQUIRE_TLS": "true",
    "FLOW_MEMORY_API_NONCE_VERIFY_TLS": "true",
    "FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_METRICS_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_TRACING_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED": "true",
    "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED": "true",
    "FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED": "false",
}
_OBSERVABILITY_HTTPS_URL_KEYS = (
    "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL",
    "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL",
    "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL",
)
_PRODUCTION_ENV_REQUIRED_KEYS = (
    "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND",
    "FLOW_MEMORY_API_NONCE_REDIS_PREFIX",
    "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND",
    "FLOW_MEMORY_COMPUTE_DATABASE_URL",
    "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION",
    "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION",
    "FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND",
    "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND",
    "FLOW_MEMORY_COMPUTE_REDIS_URL",
    "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED",
    "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED",
    "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED",
    "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION",
    "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL",
    "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL",
    "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL",
    *_LEVEL1_EXPECTED_BOOLEAN_SETTINGS.keys(),
)
_PRODUCTION_ENV_EXPECTED_VALUES = {
    "FLOW_MEMORY_API_NONCE_REPLAY_BACKEND": "redis",
    "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND": "postgres",
    "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION": "true",
    "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION": "true",
    "FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND": "redis",
    "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND": "redis",
    "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED": "true",
    "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED": "false",
    "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED": "false",
    "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED": "false",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED": "true",
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED": "true",
    **_LEVEL1_EXPECTED_BOOLEAN_SETTINGS,
}
_PLACEHOLDER_INFRA_FRAGMENTS = _PLACEHOLDER_API_KEY_FRAGMENTS + (
    "yourdomain.com",
    "api.yourdomain.com",
    "managed-postgres-host",
    "managed-redis-host",
    "audit-object-lock-bucket",
    "<managed_postgres_url>",
    "<managed_redis_url>",
    "<audit_export_uri>",
)


def _postgres_schema_floor() -> tuple[int, int]:
    plan = migration_plan()
    steps = plan.get("steps", ())
    step = steps[0] if steps else {}
    if not isinstance(step, Mapping):
        return _MIN_POSTGRES_SCHEMA_TABLE_COUNT_FALLBACK, _MIN_POSTGRES_SCHEMA_INDEX_COUNT_FALLBACK
    table_count = int(step.get("postgres_table_count", 0) or 0) + 1
    index_count = int(step.get("postgres_index_count", 0) or 0)
    return (
        max(table_count, _MIN_POSTGRES_SCHEMA_TABLE_COUNT_FALLBACK),
        max(index_count, _MIN_POSTGRES_SCHEMA_INDEX_COUNT_FALLBACK),
    )


MIN_POSTGRES_SCHEMA_TABLE_COUNT, MIN_POSTGRES_SCHEMA_INDEX_COUNT = _postgres_schema_floor()


def _int_field(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
        return int(str(value))
    except ValueError:
        return 0


def postgres_schema_count_evidence(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    table_count = _int_field(schema.get("required_table_count"))
    index_count = _int_field(schema.get("required_index_count"))
    return {
        "ok": table_count >= MIN_POSTGRES_SCHEMA_TABLE_COUNT and index_count >= MIN_POSTGRES_SCHEMA_INDEX_COUNT,
        "required_table_count": table_count,
        "minimum_table_count": MIN_POSTGRES_SCHEMA_TABLE_COUNT,
        "required_index_count": index_count,
        "minimum_index_count": MIN_POSTGRES_SCHEMA_INDEX_COUNT,
    }


def postgres_connection_tuning_evidence(storage: Mapping[str, Any]) -> Mapping[str, Any]:
    pool_size = _int_field(storage.get("pool_size"))
    max_overflow = _int_field(storage.get("max_overflow"))
    timeout_ms = _int_field(storage.get("timeout_ms"))
    statement_timeout_ms = _int_field(storage.get("statement_timeout_ms"))
    ssl_mode = str(storage.get("postgres_ssl_mode", "")).strip().lower()
    migrations_enabled = storage.get("migrations_enabled") is True
    migrations_auto_run = storage.get("migrations_auto_run") is True
    return {
        "ok": (
            ssl_mode in {"require", "verify-ca", "verify-full"}
            and pool_size >= 1
            and max_overflow >= 0
            and timeout_ms >= 1000
            and statement_timeout_ms >= 1000
            and migrations_enabled
            and migrations_auto_run
        ),
        "postgres_ssl_mode": ssl_mode,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "timeout_ms": timeout_ms,
        "statement_timeout_ms": statement_timeout_ms,
        "migrations_enabled": migrations_enabled,
        "migrations_auto_run": migrations_auto_run,
    }


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def nonce_headers(headers: Mapping[str, str], *, label: str) -> dict[str, str]:
    enriched = dict(headers)
    lowered = {key.lower(): value for key, value in enriched.items()}
    has_auth = "x-flow-memory-api-key" in lowered or "authorization" in lowered
    if has_auth and "x-flow-memory-nonce" not in lowered:
        enriched["x-flow-memory-timestamp"] = str(time.time())
        enriched["x-flow-memory-nonce"] = f"{label}-{secrets.token_urlsafe(18)}"
    return enriched


def call_json(method: str, url: str, headers: Mapping[str, str] | None = None, body: Mapping[str, Any] | None = None) -> tuple[int, Mapping[str, Any]]:
    data = None
    request_headers = nonce_headers(headers or {}, label=f"{method}-json")
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request_headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            text = response.read().decode("utf-8", "replace")
            return response.status, json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            return exc.code, {"raw": text}


def call_text(method: str, url: str, headers: Mapping[str, str] | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=nonce_headers(headers or {}, label=f"{method}-text"), method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("data", {})
    return value if isinstance(value, Mapping) else {}



def public_url_block_reason(url: str) -> str:
    raw = url.strip().lower()
    if any(fragment in raw for fragment in _PLACEHOLDER_PUBLIC_URL_FRAGMENTS):
        return "public_url_placeholder_not_allowed"
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").strip().strip("[]").lower().rstrip(".")
    if not host:
        return "public_url_missing_host"
    if host in {"localhost", "ip6-localhost", "ip6-loopback"} or host.endswith(".local"):
        return "public_url_must_not_use_localhost"
    if host in _PLACEHOLDER_PUBLIC_HOST_SUFFIXES or any(
        host.endswith(f".{suffix}") for suffix in _PLACEHOLDER_PUBLIC_HOST_SUFFIXES
    ):
        return "public_url_placeholder_not_allowed"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return ""
    return "" if address.is_global else "public_url_must_use_global_host"
def api_key_block_reason(api_key: str) -> str:
    raw = api_key.strip().lower()
    if any(fragment in raw for fragment in _PLACEHOLDER_API_KEY_FRAGMENTS):
        return "api_key_placeholder_not_allowed"
    if raw in _WEAK_API_KEYS:
        return "api_key_weak_value_not_allowed"
    return ""


def has_placeholder(value: str) -> bool:
    raw = value.strip().lower()
    return any(fragment in raw for fragment in _PLACEHOLDER_API_KEY_FRAGMENTS)


def has_infra_placeholder(value: str) -> bool:
    raw = value.strip().lower()
    return any(fragment in raw for fragment in _PLACEHOLDER_INFRA_FRAGMENTS)


def validate_production_env_prerequisites(values: Mapping[str, str]) -> None:
    missing = [key for key in _PRODUCTION_ENV_REQUIRED_KEYS if not values.get(key, "").strip()]
    placeholders = [
        key
        for key in _PRODUCTION_ENV_REQUIRED_KEYS
        if values.get(key, "").strip() and has_infra_placeholder(values[key])
    ]
    invalid: list[dict[str, str]] = []
    for key, expected in _PRODUCTION_ENV_EXPECTED_VALUES.items():
        actual = values.get(key, "").strip().lower()
        if actual and actual != expected:
            invalid.append({"key": key, "actual": actual, "expected": expected})

    database_url = values.get("FLOW_MEMORY_COMPUTE_DATABASE_URL", "").strip()
    if database_url and not has_infra_placeholder(database_url):
        database_scheme = urllib.parse.urlparse(database_url).scheme.lower()
        if database_scheme not in {"postgres", "postgresql"}:
            invalid.append(
                {
                    "key": "FLOW_MEMORY_COMPUTE_DATABASE_URL",
                    "actual": database_scheme,
                    "expected": "postgresql",
                }
            )

    redis_url = values.get("FLOW_MEMORY_COMPUTE_REDIS_URL", "").strip()
    if redis_url and not has_infra_placeholder(redis_url):
        redis_scheme = urllib.parse.urlparse(redis_url).scheme.lower()
        if redis_scheme != "rediss":
            invalid.append(
                {
                    "key": "FLOW_MEMORY_COMPUTE_REDIS_URL",
                    "actual": redis_scheme,
                    "expected": "rediss",
                }
            )

    audit_export_uri = values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI", "").strip()
    if audit_export_uri and not has_infra_placeholder(audit_export_uri):
        audit_scheme = urllib.parse.urlparse(audit_export_uri).scheme.lower()
        if audit_scheme != "s3":
            invalid.append(
                {
                    "key": "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI",
                    "actual": audit_scheme,
                    "expected": "s3",
                }
            )

    object_lock_mode = values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE", "").strip().upper()
    if object_lock_mode and object_lock_mode not in {"COMPLIANCE", "GOVERNANCE"}:
        invalid.append(
            {
                "key": "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE",
                "actual": object_lock_mode,
                "expected": "COMPLIANCE_or_GOVERNANCE",
            }
        )

    retention_days = values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS", "").strip()
    if retention_days:
        try:
            retention_days_int = int(retention_days)
        except ValueError:
            retention_days_int = 0
        if retention_days_int < 1:
            invalid.append(
                {
                    "key": "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS",
                    "actual": retention_days,
                    "expected": "positive_integer",
                }
            )

    for key in _OBSERVABILITY_HTTPS_URL_KEYS:
        sink_url = values.get(key, "").strip()
        if not sink_url or has_infra_placeholder(sink_url):
            continue
        scheme = urllib.parse.urlparse(sink_url).scheme.lower()
        if scheme != "https":
            invalid.append({"key": key, "actual": scheme, "expected": "https"})
    if missing or placeholders or invalid:
        raise SystemExit(
            "production environment prerequisites failed: "
            + json.dumps(
                {"missing": missing, "placeholder_values": placeholders, "invalid": invalid},
                sort_keys=True,
            )
        )


def base64url_json(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def gateway_jwt_config_from_env(values: Mapping[str, str]) -> dict[str, str] | None:
    secret = values.get("FLOW_MEMORY_API_JWT_HS256_SECRET", "").strip()
    issuer = values.get("FLOW_MEMORY_API_JWT_ISSUER", "").strip()
    audience = values.get("FLOW_MEMORY_API_JWT_AUDIENCE", "").strip()
    leeway = values.get("FLOW_MEMORY_API_JWT_LEEWAY_SECONDS", "60").strip() or "60"
    configured = bool(secret or issuer or audience)
    if not configured:
        return None

    missing = []
    if not secret or has_placeholder(secret):
        missing.append("FLOW_MEMORY_API_JWT_HS256_SECRET")
    if not issuer or has_placeholder(issuer):
        missing.append("FLOW_MEMORY_API_JWT_ISSUER")
    if not audience or has_placeholder(audience):
        missing.append("FLOW_MEMORY_API_JWT_AUDIENCE")
    if missing:
        raise SystemExit(
            "Gateway JWT auth must configure real FLOW_MEMORY_API_JWT_HS256_SECRET, "
            f"FLOW_MEMORY_API_JWT_ISSUER, and FLOW_MEMORY_API_JWT_AUDIENCE together: {', '.join(missing)}"
        )
    if len(secret) < 32:
        raise SystemExit("FLOW_MEMORY_API_JWT_HS256_SECRET must be at least 32 characters")
    if not issuer.startswith("https://"):
        raise SystemExit("FLOW_MEMORY_API_JWT_ISSUER must be an https:// URL")
    try:
        parsed_leeway = int(leeway)
    except ValueError as exc:
        raise SystemExit("FLOW_MEMORY_API_JWT_LEEWAY_SECONDS must be a non-negative integer") from exc
    if parsed_leeway < 0:
        raise SystemExit("FLOW_MEMORY_API_JWT_LEEWAY_SECONDS must be a non-negative integer")

    return {
        "secret": secret,
        "issuer": issuer,
        "audience": audience,
        "leeway_seconds": str(parsed_leeway),
    }


def gateway_jwt_headers(config: Mapping[str, str], scopes: str, *, audience: str | None = None) -> dict[str, str]:
    now = int(time.time())
    claims = {
        "iss": config["issuer"],
        "aud": audience or config["audience"],
        "sub": "flow-memory-public-buildout-validator",
        "scope": scopes,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{base64url_json(header)}.{base64url_json(claims)}"
    signature = hmac.new(config["secret"].encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return {
        "authorization": f"Bearer {signing_input}.{base64.urlsafe_b64encode(signature).decode('ascii').rstrip('=')}",
        "x-flow-memory-scopes": scopes,
    }




def validate(
    base_url: str,
    api_key: str,
    *,
    require_immutable_audit: bool = False,
    gateway_jwt_config: Mapping[str, str] | None = None,
) -> Mapping[str, Any]:
    base = base_url.rstrip("/")
    headers_read = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:read"}
    headers_plan = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:plan"}
    headers_audit = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:audit"}
    headers_provider = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:provider-admin"}
    headers_execute = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:execute"}
    headers_billing = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:billing"}
    headers_settlement = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:settlement-admin"}
    headers_admin = {"x-flow-memory-api-key": api_key, "x-flow-memory-scopes": "compute:admin"}

    suffix = str(int(time.time()))
    plan_idempotency_key = f"plan_public_buildout_{suffix}"
    checks: dict[str, Any] = {}
    checks["root"] = call_json("GET", f"{base}/")
    checks["health"] = call_json("GET", f"{base}/compute/health", headers_read)
    checks["readiness"] = call_json("GET", f"{base}/compute/readiness", headers_read)
    checks["plan"] = call_json("POST", f"{base}/compute/plan", headers_plan, {"task": PUBLIC_TASK, "idempotency_key": plan_idempotency_key, "dry_run": True})
    checks["plan_replay"] = call_json("POST", f"{base}/compute/plan", headers_plan, {"task": f"{PUBLIC_TASK} idempotency replay", "idempotency_key": plan_idempotency_key, "dry_run": True})
    checks["audit_verify"] = call_json("GET", f"{base}/compute/audit/verify", headers_audit)
    checks["missing_key"] = call_json("GET", f"{base}/compute/health", {"x-flow-memory-scopes": "compute:read"})
    checks["wrong_scope"] = call_json("POST", f"{base}/compute/plan", headers_read, {"task": PUBLIC_TASK, "dry_run": True})
    if gateway_jwt_config is not None:
        checks["jwt_health"] = call_json(
            "GET",
            f"{base}/compute/health",
            gateway_jwt_headers(gateway_jwt_config, "compute:read"),
        )
        checks["jwt_wrong_audience"] = call_json(
            "GET",
            f"{base}/compute/health",
            gateway_jwt_headers(
                gateway_jwt_config,
                "compute:read",
                audience=f"{gateway_jwt_config['audience']}-wrong",
            ),
        )
        checks["jwt_wrong_scope"] = call_json(
            "POST",
            f"{base}/compute/plan",
            gateway_jwt_headers(gateway_jwt_config, "compute:read"),
            {"task": PUBLIC_TASK, "dry_run": True},
        )

    provider_id = f"provider_public_buildout_{suffix}"
    route_id = f"route_public_buildout_{suffix}"
    account_id = f"acct_public_buildout_{suffix}"
    provider = {
        "provider_id": provider_id,
        "provider_name": "Public Buildout Validation Provider",
        "provider_type": "gpu",
        "supported_unit_types": ["gpu_minute", "gpu_hour", "request"],
        "supported_assets": ["USD", "USDC", "CREDITS"],
        "supported_networks": ["offchain", "solana", "base"],
        "quote_endpoint": "https://providers.flowmemory.ai/public-buildout/quote",
        "health_endpoint": "https://providers.flowmemory.ai/public-buildout/health",
        "credentials": {"secret_ref": "external/secret/flow-memory-provider-validation"},
        "sla": {"uptime_target": 0.99, "max_latency_ms": 1000, "refund_policy": "credit"},
    }
    quote = {
        "quote_id": f"quote_public_buildout_{suffix}",
        "provider_id": provider_id,
        "route_id": route_id,
        "unit_type": "gpu_minute",
        "unit_price": 0.09,
        "estimated_units": 2,
        "estimated_total_cost": 0.18,
        "currency_or_asset": "USDC",
        "network": "solana",
        "confidence": 0.93,
        "capacity_available": True,
        "quote_ttl_seconds": 300,
        "expires_at": "2099-01-01T00:00:00Z",
        "settlement_modes": ["generic_dry_run"],
        "dry_run_supported": True,
        "assumptions": [],
    }

    checks["provider_apply"] = call_json("POST", f"{base}/market/providers/apply", headers_provider, provider)
    checks["provider_verify"] = call_json("POST", f"{base}/market/providers/{provider_id}/verify", headers_provider, {})
    checks["provider_conformance"] = call_json("POST", f"{base}/market/providers/{provider_id}/conformance", headers_provider, {"sample_quote": quote, "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    checks["provider_get"] = call_json("GET", f"{base}/market/providers/{provider_id}", headers_read)
    checks["capacity_list"] = call_json(
        "POST",
        f"{base}/market/capacity/list",
        headers_provider,
        {
            "provider_id": provider_id,
            "route_id": route_id,
            "resource_type": "gpu_hour",
            "gpu_type": "H100",
            "available_units": 10,
            "region": "us-east",
            "starts_at": "2099-01-01T00:00:00Z",
            "ends_at": "2099-01-01T01:00:00Z",
            "price_floor": 2.4,
        },
    )
    checks["capacity_reserve"] = call_json("POST", f"{base}/market/capacity/reserve", headers_provider, {"provider_id": provider_id, "route_id": route_id, "capacity_units": 2})
    reservation_id = str(data(checks["capacity_reserve"][1]).get("reservation", {}).get("reservation_id", ""))
    checks["capacity_release"] = call_json("POST", f"{base}/market/capacity/release", headers_provider, {"reservation_id": reservation_id})
    checks["quote_ingest"] = call_json("POST", f"{base}/market/quotes/ingest", headers_provider, {"quote": quote, "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    checks["external_quote_disabled"] = call_json("POST", f"{base}/compute/providers/external/quote", headers_provider, {"provider_id": provider_id, "task": PUBLIC_TASK, "allowed_assets": ["USDC"], "allowed_networks": ["solana"]})
    checks["prices"] = call_json("GET", f"{base}/market/prices", headers_read)
    checks["job_create"] = call_json(
        "POST",
        f"{base}/compute/jobs",
        headers_execute,
        {
            "task_type": "inference",
            "input_ref": "s3://flow-memory-inputs/public-buildout-validation.json",
            "model_or_runtime": "llama-runtime",
            "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
            "budget_policy_id": "policy_default",
            "route_id": route_id,
            "provider_id": provider_id,
        },
    )
    job_id = str(data(checks["job_create"][1]).get("job", {}).get("job_id", ""))
    checks["job_get"] = call_json("GET", f"{base}/compute/jobs/{job_id}", headers_read)
    checks["job_events"] = call_json("GET", f"{base}/compute/jobs/{job_id}/events", headers_read)
    checks["job_retry_create"] = call_json(
        "POST",
        f"{base}/compute/jobs",
        headers_execute,
        {
            "task_type": "inference",
            "input_ref": "s3://flow-memory-inputs/public-buildout-validation-retry.json",
            "model_or_runtime": "llama-runtime",
            "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
            "budget_policy_id": "policy_default",
            "route_id": route_id,
            "provider_id": provider_id,
        },
    )
    retry_job_id = str(data(checks["job_retry_create"][1]).get("job", {}).get("job_id", ""))
    checks["job_retry"] = call_json("POST", f"{base}/compute/jobs/{retry_job_id}/retry", headers_execute, {})
    checks["job_cancel"] = call_json("POST", f"{base}/compute/jobs/{retry_job_id}/cancel", headers_execute, {"reason": "public validation"})
    checks["job_dispatch"] = call_json("POST", f"{base}/compute/jobs/{job_id}/dispatch", headers_execute, {})
    unsigned_receipt = {
        "receipt_id": f"receipt_public_buildout_unsigned_{suffix}",
        "timestamp": "2099-01-01T00:00:00Z",
        "job_id": job_id,
        "provider_id": provider_id,
        "route_id": route_id,
        "status": "succeeded",
        "actual_units": 2,
        "actual_total_cost": 0.18,
        "actual_latency_ms": 1000,
        "artifact_ref": "s3://flow-memory-results/public-buildout-receipt.json",
        "funds_moved": False,
    }
    checks["job_receipt_wrong_scope"] = call_json("POST", f"{base}/compute/jobs/{job_id}/receipt", headers_read, {"receipt": unsigned_receipt})
    checks["job_receipt_unsigned"] = call_json("POST", f"{base}/compute/jobs/{job_id}/receipt", headers_execute, {"receipt": unsigned_receipt})
    checks["alerts_route"] = call_json(
        "POST",
        f"{base}/compute/alerts/route",
        headers_admin,
        {"request_id": f"public_buildout_alert_route_{suffix}"},
    )
    checks["job_complete"] = call_json(
        "POST",
        f"{base}/compute/jobs/{job_id}/complete",
        headers_execute,
        {
            "actual_units": 2,
            "actual_total_cost": 0.18,
            "currency": "USD",
            "account_id": account_id,
            "artifact_ref": "s3://flow-memory-results/public-buildout-validation.json",
            "artifact_data": {"result": "ok"},
        },
    )
    checks["job_artifacts"] = call_json("GET", f"{base}/compute/jobs/{job_id}/artifacts", headers_read)
    payout_id = str(data(checks["job_complete"][1]).get("provider_payout", {}).get("provider_payout_id", ""))
    checks["billing_provider_payouts"] = call_json(
        "GET",
        f"{base}/billing/provider-payouts?provider_id={provider_id}&account_id={account_id}",
        headers_billing,
    )
    checks["billing_provider_payout_settle"] = call_json(
        "POST",
        f"{base}/billing/provider-payouts/{payout_id}/settle",
        headers_settlement,
        {"external_payout_reference": f"public_validation_payout_{suffix}", "settled_by": "public-buildout-validator"},
    )
    checks["job_fail_create"] = call_json(
        "POST",
        f"{base}/compute/jobs",
        headers_execute,
        {
            "task_type": "inference",
            "input_ref": "s3://flow-memory-inputs/public-buildout-validation-fail.json",
            "model_or_runtime": "llama-runtime",
            "resource_request": {"gpu_type": "H100", "gpu_count": 1, "memory_gb": 80, "max_runtime_seconds": 600},
            "budget_policy_id": "policy_default",
            "route_id": route_id,
            "provider_id": provider_id,
        },
    )
    fail_job_id = str(data(checks["job_fail_create"][1]).get("job", {}).get("job_id", ""))
    checks["job_fail"] = call_json("POST", f"{base}/compute/jobs/{fail_job_id}/fail", headers_execute, {"error_code": "public_validation_failure_path"})
    checks["error_tracking"] = call_json(
        "POST",
        f"{base}/compute/errors/track",
        headers_admin,
        {
            "error_code": "public_buildout_validation",
            "message": "Public buildout validation exercised the production error tracking sink.",
            "details": {"source": "validate_compute_market_public_buildout"},
            "request_id": f"public_buildout_error_tracking_{suffix}",
        },
    )
    checks["telemetry"] = call_json("GET", f"{base}/compute/telemetry", headers_read)
    checks["metrics"] = call_text("GET", f"{base}/metrics", headers_read)
    checks["alerts"] = call_json("GET", f"{base}/compute/alerts", headers_read)
    checks["otlp_export"] = call_json(
        "POST",
        f"{base}/admin/compute/otlp/export",
        headers_admin,
        {"reset": False, "request_id": f"public_buildout_otlp_export_{suffix}"},
    )
    checks["billing_checkout"] = call_json("POST", f"{base}/billing/checkout", headers_billing, {"account_id": account_id, "amount": 100, "currency": "USD"})
    checks["billing_balance"] = call_json("GET", f"{base}/billing/balance?account_id={account_id}", headers_billing)
    checks["billing_refund"] = call_json(
        "POST",
        f"{base}/billing/refund",
        headers_billing,
        {
            "account_id": account_id,
            "amount": 1,
            "currency": "USD",
            "reason": "public_validation_no_custody",
            "idempotency_key": f"refund_public_buildout_{suffix}",
        },
    )
    checks["admin_reconciliation"] = call_json("GET", f"{base}/admin/reconciliation", headers_admin)
    checks["admin_storage_diagnostics"] = call_json("GET", f"{base}/admin/storage/diagnostics", headers_admin)
    checks["admin_redis_diagnostics"] = call_json("GET", f"{base}/admin/redis/diagnostics", headers_admin)
    checks["admin_audit_export"] = call_json("GET", f"{base}/admin/audit/export", headers_admin)
    checks["audit_export_write"] = call_json("POST", f"{base}/compute/audit/export", headers_audit, {"chain_id": "all"})

    root_data = data(checks["root"][1])
    readiness = data(checks["readiness"][1])
    plan = data(checks["plan"][1]).get("compute_plan", {})
    plan_replay = data(checks["plan_replay"][1]).get("compute_plan", {})
    job = data(checks["job_create"][1]).get("job", {})
    checkout = data(checks["billing_checkout"][1]).get("checkout", {})
    refund = data(checks["billing_refund"][1]).get("refund", {})
    payout_list = data(checks["billing_provider_payouts"][1])
    payout_settle = data(checks["billing_provider_payout_settle"][1]).get("provider_payout", {})
    storage_diag = data(checks["admin_storage_diagnostics"][1])
    redis_diag = data(checks["admin_redis_diagnostics"][1])
    safety_defaults = readiness.get("production_safety_defaults", {})
    alert_route = data(checks["alerts_route"][1])
    error_tracking = data(checks["error_tracking"][1])
    otlp_export = data(checks["otlp_export"][1])
    schema_verification = storage_diag.get("schema_verification", {})
    advisory_lock_probe = schema_verification.get("advisory_lock_probe", {})
    schema_count_evidence = postgres_schema_count_evidence(schema_verification)
    storage_status = storage_diag.get("storage", {})
    storage_status_map = storage_status if isinstance(storage_status, Mapping) else {}
    connection_tuning_evidence = postgres_connection_tuning_evidence(storage_status_map)

    audit_export_status = data(checks["admin_audit_export"][1])
    audit_export_write = data(checks["audit_export_write"][1])
    audit_exporter_status = audit_export_status.get("audit_exporter_status", {})
    audit_exporter_status_map = audit_exporter_status if isinstance(audit_exporter_status, Mapping) else {}
    audit_exporter_name = str(audit_exporter_status_map.get("exporter", ""))
    audit_export_is_immutable = audit_export_status.get("immutable") is True or audit_exporter_status_map.get("immutable") is True
    require(checks["root"][0] == 200 and root_data.get("service") == "Flow Memory Compute Market", "root public landing failed")
    require(checks["health"][0] == 200 and data(checks["health"][1]).get("ok") is True, "health failed")
    require(checks["readiness"][0] == 200 and readiness.get("ready") is True, "readiness failed")
    require(readiness.get("storage", {}).get("backend") in {"postgres", "postgresql"}, "readiness did not report Postgres")
    require(readiness.get("rate_limiter_status", {}).get("backend") == "redis" or readiness.get("production_safety_defaults", {}).get("rate_limit_backend") == "redis", "readiness did not report Redis limiter")
    require(readiness.get("circuit_breaker_status", {}).get("backend") == "redis" or readiness.get("production_safety_defaults", {}).get("circuit_breaker_backend") == "redis", "readiness did not report Redis circuit breaker")
    require(safety_defaults.get("require_managed_redis_in_production") is True, "managed Redis requirement is not enabled")
    require(
        safety_defaults.get("redis_url_scheme") == "rediss"
        or (
            safety_defaults.get("redis_url_scheme") == "redis"
            and safety_defaults.get("allow_internal_redis_in_production") is True
        ),
        "managed Redis URL is neither rediss:// nor explicitly allowed internal redis://",
    )
    require(safety_defaults.get("require_managed_sql_in_production") is True, "managed Postgres requirement is not enabled")
    require(safety_defaults.get("dry_run_required") is True, "dry-run requirement is not enabled")
    require(safety_defaults.get("live_settlement_enabled") is False, "live settlement must remain disabled for Level 1")
    require(safety_defaults.get("broadcast_enabled") is False, "broadcasting must remain disabled for Level 1")
    require(safety_defaults.get("private_key_inputs_allowed") is False, "private key inputs must remain disabled")
    require(safety_defaults.get("audit_required") is True, "audit requirement is not enabled")
    require(safety_defaults.get("audit_export_required") is True, "audit export requirement is not enabled")
    require(safety_defaults.get("stripe_checkout_enabled") is False, "Stripe Checkout must remain disabled for Level 1")
    require(
        safety_defaults.get("alert_routing_enabled") is True
        and safety_defaults.get("alert_webhook_configured") is True,
        "alert routing sink is not enabled and configured",
    )
    require(
        safety_defaults.get("error_tracking_enabled") is True
        and safety_defaults.get("error_tracking_webhook_configured") is True,
        "error tracking sink is not enabled and configured",
    )
    require(
        safety_defaults.get("telemetry_export_enabled") is True
        and safety_defaults.get("otlp_endpoint_configured") is True,
        "OTLP telemetry export sink is not enabled and configured",
    )
    require(plan.get("dry_run_only") is True and plan.get("funds_moved") is False and plan.get("broadcast_allowed") is False and plan.get("private_key_required") is False, "plan safety flags failed")
    require(
        checks["plan_replay"][0] == 200
        and data(checks["plan_replay"][1]).get("idempotent_replay") is True
        and plan_replay.get("decision_id") == plan.get("decision_id"),
        "plan idempotent replay failed",
    )
    require(checks["audit_verify"][0] == 200 and data(checks["audit_verify"][1]).get("ok") is True, "audit verify failed")
    require(checks["missing_key"][0] == 401, "missing key did not fail")
    require(checks["wrong_scope"][0] == 403, "wrong scope did not fail")
    if gateway_jwt_config is not None:
        require(checks["jwt_health"][0] == 200, "gateway JWT health check failed")
        require(checks["jwt_wrong_audience"][0] == 401, "gateway JWT wrong-audience check did not fail")
        require(checks["jwt_wrong_scope"][0] == 403, "gateway JWT wrong-scope check did not fail")
    require(checks["external_quote_disabled"][0] == 200 and data(checks["external_quote_disabled"][1]).get("ok") is False, "external quote endpoint did not fail closed")
    require(checks["job_receipt_wrong_scope"][0] == 403, "receipt endpoint wrong scope did not fail")
    require(checks["job_receipt_unsigned"][0] == 200 and data(checks["job_receipt_unsigned"][1]).get("ok") is False, "unsigned provider receipt did not fail closed")
    for name in ("provider_apply", "provider_verify", "provider_conformance", "provider_get", "capacity_list", "capacity_reserve", "capacity_release", "quote_ingest", "prices", "job_create", "job_get", "job_events", "job_dispatch", "job_complete", "job_artifacts", "job_fail_create", "job_fail", "job_retry_create", "job_retry", "job_cancel", "telemetry", "alerts", "alerts_route", "error_tracking", "otlp_export", "billing_provider_payouts", "billing_provider_payout_settle"):
        require(checks[name][0] == 200 and checks[name][1].get("ok") is True, f"{name} failed")
    require(checks["metrics"][0] == 200 and "compute_plan_requests_total" in checks["metrics"][1], "Prometheus metrics did not expose compute_plan_requests_total")
    require(alert_route.get("routing_enabled") is True and int(alert_route.get("delivery_count", 0) or 0) >= 1, "alert routing did not deliver to the configured sink")
    require(error_tracking.get("status") == "delivered", "error tracking sink delivery failed")
    require(otlp_export.get("status") == "delivered", "OTLP telemetry export delivery failed")
    require(job.get("dry_run_only") is True and job.get("funds_moved") is False and job.get("broadcast_allowed") is False and job.get("private_key_required") is False, "job safety flags failed")
    require(checks["billing_checkout"][0] == 200 and checkout.get("funds_moved") is False and checkout.get("status") == "requires_external_checkout_provider", "billing checkout safety failed")
    require(checks["billing_balance"][0] == 200 and data(checks["billing_balance"][1]).get("balance", {}).get("account_id") == account_id, "billing balance failed")
    require(checks["billing_refund"][0] == 200 and refund.get("funds_moved") is False and refund.get("external_refund_created") is False and refund.get("status") == "recorded_no_custody", "billing refund safety failed")
    require(
        payout_list.get("provider_payouts", ())
        and payout_list.get("provider_payouts", ())[0].get("funds_moved") is False
        and payout_settle.get("status") == "settled"
        and payout_settle.get("funds_moved") is False,
        "provider payout no-custody validation failed",
    )
    require(checks["admin_reconciliation"][0] == 200 and checks["admin_reconciliation"][1].get("ok") is True, "admin reconciliation failed")
    require(checks["admin_storage_diagnostics"][0] == 200 and storage_diag.get("ok") is True and storage_diag.get("production_readiness", {}).get("production_ready") is True, "admin storage diagnostics failed")
    require(
        schema_verification.get("ok") is True
        and not schema_verification.get("missing_tables", ())
        and not schema_verification.get("missing_indexes", ())
        and isinstance(advisory_lock_probe, Mapping)
        and advisory_lock_probe.get("acquired") is True,
        "admin storage schema verification failed",
    )
    require(
        schema_count_evidence.get("ok") is True,
        f"admin storage schema count floor failed: {json.dumps(schema_count_evidence, sort_keys=True)}",
    )
    require(
        connection_tuning_evidence.get("ok") is True,
        f"admin storage connection tuning failed: {json.dumps(connection_tuning_evidence, sort_keys=True)}",
    )
    require(checks["admin_redis_diagnostics"][0] == 200 and redis_diag.get("ok") is True and redis_diag.get("rate_limit_probe", {}).get("ok") is True and redis_diag.get("circuit_breaker_probe", {}).get("ok") is True, "admin redis diagnostics failed")
    require(
        redis_diag.get("rate_limit_fail_closed") is True
        and redis_diag.get("circuit_breaker_fail_closed") is True,
        "admin redis diagnostics did not report fail-closed Redis controls",
    )
    require(checks["admin_audit_export"][0] == 200 and isinstance(audit_exporter_status, Mapping), "admin audit export status failed")
    require(
        checks["audit_export_write"][0] == 200
        and audit_export_write.get("ok") is True
        and bool(audit_export_write.get("manifest_hash"))
        and int(audit_export_write.get("event_count", 0) or 0) >= 1,
        "audit export write failed",
    )
    if require_immutable_audit:
        require(
            audit_export_is_immutable and audit_exporter_name == "s3_object_lock",
            "admin audit export is not immutable S3 Object Lock storage",
        )
        require(safety_defaults.get("audit_export_immutable_required") is True, "immutable audit export requirement is not enabled")
    else:
        require(
            audit_export_is_immutable or audit_exporter_name in {"s3_object_lock", "local_file"},
            "admin audit export is neither immutable nor an allowed local/S3 exporter",
        )

    return {
        "status": "passed",
        "public_url": base,
        "checks": {name: status for name, (status, _payload) in sorted(checks.items())},
        "storage_backend": readiness.get("storage", {}).get("backend"),
        "rate_limit_backend": readiness.get("rate_limiter_status", {}).get("backend") or readiness.get("production_safety_defaults", {}).get("rate_limit_backend"),
        "circuit_breaker_backend": readiness.get("circuit_breaker_status", {}).get("backend") or readiness.get("production_safety_defaults", {}).get("circuit_breaker_backend"),
        "require_managed_redis_in_production": safety_defaults.get("require_managed_redis_in_production"),
        "redis_url_scheme": safety_defaults.get("redis_url_scheme"),
        "allow_internal_redis_in_production": safety_defaults.get("allow_internal_redis_in_production"),
        "require_managed_sql_in_production": safety_defaults.get("require_managed_sql_in_production"),
        "dry_run_required": safety_defaults.get("dry_run_required"),
        "live_settlement_enabled": safety_defaults.get("live_settlement_enabled"),
        "broadcast_enabled": safety_defaults.get("broadcast_enabled"),
        "private_key_inputs_allowed": safety_defaults.get("private_key_inputs_allowed"),
        "audit_required": safety_defaults.get("audit_required"),
        "audit_export_required": safety_defaults.get("audit_export_required"),
        "audit_export_immutable_required": safety_defaults.get("audit_export_immutable_required"),
        "stripe_checkout_enabled": safety_defaults.get("stripe_checkout_enabled"),
        "alert_routing_enabled": safety_defaults.get("alert_routing_enabled"),
        "alert_webhook_configured": safety_defaults.get("alert_webhook_configured"),
        "error_tracking_enabled": safety_defaults.get("error_tracking_enabled"),
        "error_tracking_webhook_configured": safety_defaults.get("error_tracking_webhook_configured"),
        "telemetry_export_enabled": safety_defaults.get("telemetry_export_enabled"),
        "otlp_endpoint_configured": safety_defaults.get("otlp_endpoint_configured"),
        "alert_route_delivery_count": alert_route.get("delivery_count"),
        "error_tracking_status": error_tracking.get("status"),
        "otlp_export_status": otlp_export.get("status"),
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "plan_idempotent_replay": data(checks["plan_replay"][1]).get("idempotent_replay"),
        "audit_export_immutable": audit_export_status.get("immutable"),
        "audit_export_write_manifest_hash_present": bool(audit_export_write.get("manifest_hash")),
        "audit_export_write_event_count": audit_export_write.get("event_count"),
        "postgres_required_table_count": schema_count_evidence.get("required_table_count"),
        "postgres_minimum_table_count": schema_count_evidence.get("minimum_table_count"),
        "postgres_required_index_count": schema_count_evidence.get("required_index_count"),
        "postgres_minimum_index_count": schema_count_evidence.get("minimum_index_count"),
        "postgres_connection_pool_size": connection_tuning_evidence.get("pool_size"),
        "postgres_connection_max_overflow": connection_tuning_evidence.get("max_overflow"),
        "postgres_connection_timeout_ms": connection_tuning_evidence.get("timeout_ms"),
        "postgres_statement_timeout_ms": connection_tuning_evidence.get("statement_timeout_ms"),
        "postgres_migrations_auto_run": connection_tuning_evidence.get("migrations_auto_run"),
        "audit_exporter": audit_exporter_name,
    }



def _bool_env(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Flow Memory Compute Market public production buildout")
    parser.add_argument("--api-url", default="")
    parser.add_argument("--env-file", default=".env.compute-market.live")
    parser.add_argument("--require-immutable-audit", action="store_true")
    args = parser.parse_args(argv)

    env_values = parse_env_file(Path(args.env_file))
    api_url = args.api_url or env_values.get("FLOW_MEMORY_PUBLIC_API_URL", "")
    api_key = env_values.get("FLOW_MEMORY_API_KEY", "")
    if not api_url.startswith("https://"):
        raise SystemExit("FLOW_MEMORY_PUBLIC_API_URL/--api-url must be an https:// URL")
    block_reason = public_url_block_reason(api_url)
    if block_reason:
        raise SystemExit(f"FLOW_MEMORY_PUBLIC_API_URL/--api-url is not a public endpoint: {block_reason}")
    if not api_key:
        raise SystemExit("FLOW_MEMORY_API_KEY is required in the env file")
    api_key_block = api_key_block_reason(api_key)
    if api_key_block:
        raise SystemExit(f"FLOW_MEMORY_API_KEY is not a production secret: {api_key_block}")
    require_immutable_audit = args.require_immutable_audit or _bool_env(
        env_values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED", ""),
        False,
    )
    gateway_jwt_config = gateway_jwt_config_from_env(env_values)
    validate_production_env_prerequisites(env_values)
    if gateway_jwt_config is not None:
        result = validate(
            api_url,
            api_key,
            require_immutable_audit=require_immutable_audit,
            gateway_jwt_config=gateway_jwt_config,
        )
    else:
        result = validate(api_url, api_key, require_immutable_audit=require_immutable_audit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
