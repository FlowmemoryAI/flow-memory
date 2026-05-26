from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.render.com/v1"
SERVICE_NAME = "flow-memory-compute-market-api"
POSTGRES_NAME = "flow-memory-compute-market-postgres"
KEYVALUE_NAME = "flow-memory-compute-market-redis"
DEFAULT_AUDIT_EXPORT_URI = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI", "")
DEFAULT_POSTGRES_PLAN = os.environ.get("RENDER_POSTGRES_PLAN", "free")
DEFAULT_KEYVALUE_PLAN = os.environ.get("RENDER_KEYVALUE_PLAN", "free")
DEFAULT_SERVICE_PLAN = os.environ.get("RENDER_SERVICE_PLAN", "free")
ENABLE_RENDER_DISK = os.environ.get("RENDER_ENABLE_DISK", "").strip().lower() in {"1", "true", "yes"}
DEFAULT_AUDIT_EXPORT_OBJECT_LOCK_MODE = os.environ.get(
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE", "COMPLIANCE"
)
DEFAULT_AUDIT_EXPORT_RETENTION_DAYS = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS", "365")
DEFAULT_AUDIT_EXPORT_IMMUTABLE_REQUIRED = os.environ.get(
    "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED", "true"
)
DEFAULT_AUDIT_EXPORT_S3_REGION = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION", "")
DEFAULT_AUDIT_EXPORT_S3_ENDPOINT_URL = os.environ.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_ENDPOINT_URL", "")
DEPLOY_PATHS = (
    "Dockerfile.compute-market",
    "render.yaml",
    "src/flow_memory/api/http_server.py",
    "src/flow_memory/api/auth.py",
    "src/flow_memory/api/compute_endpoints.py",
    "src/flow_memory/api/manifest.py",
    "src/flow_memory/api/router.py",
    "src/flow_memory/api/server_cli.py",
    "src/flow_memory/api/scopes.py",
    "src/flow_memory/compute_market/audit_export.py",
    "src/flow_memory/compute_market/adapters.py",
    "src/flow_memory/compute_market/config.py",
    "src/flow_memory/compute_market/observability.py",
    "src/flow_memory/compute_market/provider_contracts.py",
    "src/flow_memory/compute_market/provider_sandbox.py",
    "src/flow_memory/compute_market/service.py",
    "src/flow_memory/compute_market/storage.py",
    "src/flow_memory/compute_market/storage_backends.py",
    "src/flow_memory/compute_market/__init__.py",
    "scripts/deploy_compute_market_public_level1.ps1",
    "scripts/deploy_compute_market_render_level1.py",
    "scripts/smoke_compute_market_public.ps1",
    "scripts/validate_compute_market_public_buildout.py",
)
PLACEHOLDERS = (
    "CHANGEME",
    "<required>",
    "<your-domain>",
    "<managed_postgres_url>",
    "<managed_redis_url>",
    "<audit_export_uri>",
    "managed-postgres-host",
    "managed-redis-host",
)


class RenderError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def emit(status: str, code: int = 0, **fields: Any) -> None:
    payload: dict[str, Any] = {"status": status}
    payload.update(fields)
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(code)


def run_git(args: list[str], *, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stdout.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def parse_env(path: Path) -> dict[str, str]:
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


def audit_export_uri_from_env(values: dict[str, str]) -> str:
    uri = values.get("FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI") or DEFAULT_AUDIT_EXPORT_URI
    if not uri or has_placeholder(uri):
        emit(
            "blocked_missing_audit_object_storage",
            23,
            missing_values=["FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI"],
            required_action="configure an S3 Object Lock audit export URI before public deployment",
        )
    if not uri.startswith("s3://"):
        emit(
            "blocked_missing_audit_object_storage",
            23,
            audit_export_uri=uri,
            required_action="FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI must be an s3:// Object Lock bucket/prefix",
        )
    return uri


def has_placeholder(value: str) -> bool:
    return any(token in value for token in PLACEHOLDERS)


def public_repo_url() -> str:
    remote = run_git(["remote", "get-url", "origin"])
    if remote.startswith("git@github.com:"):
        remote = "https://github.com/" + remote.removeprefix("git@github.com:")
    if remote.endswith(".git"):
        remote = remote[:-4]
    return remote


def current_branch() -> str:
    return run_git(["branch", "--show-current"])


def assert_branch_is_publishable(branch: str) -> None:
    status = run_git(["status", "--short", "--", *DEPLOY_PATHS], check=False)
    if status:
        emit(
            "blocked_uncommitted_deploy_artifacts",
            21,
            changed_paths=[line[3:] if len(line) > 3 else line for line in status.splitlines()],
            required_action="commit and push deployment artifacts before Render can build them",
        )
    heads = run_git(["ls-remote", "--heads", "origin", branch], check=False)
    if not heads:
        emit(
            "blocked_branch_not_published",
            22,
            branch=branch,
            required_action="push the deployment branch to origin before Render can build it",
        )


def render_request(api_key: str, method: str, path: str, body: Any | None = None) -> Any:
    data = None
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", "replace")
            return json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        message = text.strip()
        try:
            parsed = json.loads(text)
            message = parsed.get("message") or parsed.get("error") or message
        except Exception:
            pass
        raise RenderError(exc.code, message) from exc


def query(params: dict[str, str]) -> str:
    return urllib.parse.urlencode(params, safe=",")


def find_named(api_key: str, path: str, envelope: str, owner_id: str, name: str) -> dict[str, Any] | None:
    items = render_request(api_key, "GET", f"{path}?{query({'name': name, 'ownerId': owner_id, 'limit': '100'})}")
    for item in items if isinstance(items, list) else []:
        obj = item.get(envelope, {}) if isinstance(item, dict) else {}
        if obj.get("name") == name:
            return obj
    return None


def wait_available(api_key: str, path: str, resource_id: str, label: str) -> dict[str, Any]:
    for _ in range(90):
        obj = render_request(api_key, "GET", f"{path}/{urllib.parse.quote(resource_id)}")
        status = str(obj.get("status", "")).lower()
        suspended = str(obj.get("suspended", "")).lower()
        if status == "available" or suspended == "not_suspended":
            return obj
        if status in {"unavailable", "suspended"}:
            emit("failed_deployment", 31, resource=label, resource_status=status)
        time.sleep(10)
    emit("failed_deployment", 32, resource=label, resource_status="timeout_waiting_available")
    raise AssertionError("unreachable")

def wait_deploy_live(api_key: str, service_id: str, deploy_id: str) -> dict[str, Any]:
    if not deploy_id:
        emit("failed_deployment", 35, reason="render_deploy_id_missing")
    for _ in range(120):
        deploy = render_request(api_key, "GET", f"/services/{urllib.parse.quote(service_id)}/deploys/{urllib.parse.quote(deploy_id)}")
        envelope = deploy.get("deploy", deploy) if isinstance(deploy, dict) else {}
        status = str(envelope.get("status", "")).lower()
        if status == "live":
            return envelope
        if status in {"build_failed", "update_failed", "canceled", "deactivated"}:
            emit("failed_deployment", 36, deploy_id=deploy_id, deploy_status=status)
        time.sleep(10)
    emit("failed_deployment", 37, deploy_id=deploy_id, deploy_status="timeout_waiting_live")
    raise AssertionError("unreachable")


def list_service_deploys(api_key: str, service_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    deploys = render_request(api_key, "GET", f"/services/{urllib.parse.quote(service_id)}/deploys?limit={limit}")
    results: list[dict[str, Any]] = []
    for item in deploys if isinstance(deploys, list) else []:
        envelope = item.get("deploy", item) if isinstance(item, dict) else {}
        if isinstance(envelope, dict) and envelope.get("id"):
            results.append(envelope)
    return results


def trigger_service_deploy(api_key: str, service_id: str) -> dict[str, Any]:
    before_ids = {str(deploy.get("id", "")) for deploy in list_service_deploys(api_key, service_id)}
    deploy = render_request(api_key, "POST", f"/services/{urllib.parse.quote(service_id)}/deploys", {"clearCache": "do_not_clear"})
    envelope = deploy.get("deploy", deploy) if isinstance(deploy, dict) else {}
    deploy_id = str(envelope.get("id", ""))
    if not deploy_id:
        deadline = time.time() + 300
        while time.time() < deadline and not deploy_id:
            for candidate in list_service_deploys(api_key, service_id):
                candidate_id = str(candidate.get("id", ""))
                if candidate_id and candidate_id not in before_ids:
                    deploy_id = candidate_id
                    break
            if not deploy_id:
                time.sleep(5)
    if not deploy_id:
        emit("failed_deployment", 35, reason="render_deploy_id_missing")
    return wait_deploy_live(api_key, service_id, deploy_id)


def ensure_postgres(api_key: str, owner_id: str, region: str) -> dict[str, Any]:
    existing = find_named(api_key, "/postgres", "postgres", owner_id, POSTGRES_NAME)
    if existing is not None:
        return existing
    body = {
        "name": POSTGRES_NAME,
        "ownerId": owner_id,
        "plan": DEFAULT_POSTGRES_PLAN,
        "version": "16",
        "databaseName": "flow_memory",
        "databaseUser": "flow_memory",
        "region": region,
        "ipAllowList": [],
    }
    return render_request(api_key, "POST", "/postgres", body)


def ensure_keyvalue(api_key: str, owner_id: str, region: str) -> dict[str, Any]:
    existing = find_named(api_key, "/key-value", "keyValue", owner_id, KEYVALUE_NAME)
    if existing is not None:
        return existing
    body = {
        "name": KEYVALUE_NAME,
        "ownerId": owner_id,
        "plan": DEFAULT_KEYVALUE_PLAN,
        "region": region,
        "maxmemoryPolicy": "noeviction",
        "ipAllowList": [],
    }
    if DEFAULT_KEYVALUE_PLAN != "free":
        body["persistenceMode"] = "journal_snapshot"
    return render_request(api_key, "POST", "/key-value", body)


def env_var(key: str, value: str) -> dict[str, str]:
    return {"key": key, "value": value}


def build_env_vars(
    api_key_value: str,
    database_url: str,
    redis_url: str,
    public_api_url: str = "",
    audit_export_uri: str = "",
) -> list[dict[str, str]]:
    values = {
        "FLOW_MEMORY_API_HOST": "0.0.0.0",
        "FLOW_MEMORY_API_PORT": "8765",
        "FLOW_MEMORY_API_KEY": api_key_value,
        "FLOW_MEMORY_API_REQUIRE_SCOPES": "true",
        "FLOW_MEMORY_API_RATE_LIMIT": "120",
        "FLOW_MEMORY_API_RATE_LIMIT_WINDOW_SECONDS": "60",
        "FLOW_MEMORY_API_MAX_BODY_BYTES": "1048576",
        "FLOW_MEMORY_LOG_LEVEL": "INFO",
        "FLOW_MEMORY_METRICS_ENABLED": "true",
        "FLOW_MEMORY_TRACING_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_MARKET_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_MARKET_MODE": "production_planning",
        "FLOW_MEMORY_COMPUTE_STORAGE_BACKEND": "postgres",
        "FLOW_MEMORY_COMPUTE_DATABASE_URL": database_url,
        "FLOW_MEMORY_COMPUTE_POSTGRES_SSL_MODE": "require",
        "FLOW_MEMORY_COMPUTE_STORAGE_POOL_SIZE": "4",
        "FLOW_MEMORY_COMPUTE_STORAGE_MAX_OVERFLOW": "4",
        "FLOW_MEMORY_COMPUTE_STORAGE_TIMEOUT_MS": "5000",
        "FLOW_MEMORY_COMPUTE_STORAGE_STATEMENT_TIMEOUT_MS": "5000",
        "FLOW_MEMORY_COMPUTE_MIGRATIONS_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_MIGRATIONS_AUTO_RUN": "true",
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION": "true",
        "FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_REDIS_IN_PRODUCTION": "true",
        "FLOW_MEMORY_COMPUTE_RATE_LIMIT_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND": "redis",
        "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND": "redis",
        "FLOW_MEMORY_COMPUTE_REDIS_URL": redis_url,
        "FLOW_MEMORY_COMPUTE_REDIS_PREFIX": "flow-memory:compute-market",
        "FLOW_MEMORY_COMPUTE_RATE_LIMIT_FAIL_CLOSED": "true",
        "FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_FAIL_CLOSED": "true",
        "FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED": "true",
        "FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED": "false",
        "FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED": "true",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED": "true",
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI": audit_export_uri,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_OBJECT_LOCK_MODE": DEFAULT_AUDIT_EXPORT_OBJECT_LOCK_MODE,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_RETENTION_DAYS": DEFAULT_AUDIT_EXPORT_RETENTION_DAYS,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_IMMUTABLE_REQUIRED": DEFAULT_AUDIT_EXPORT_IMMUTABLE_REQUIRED,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_REGION": DEFAULT_AUDIT_EXPORT_S3_REGION,
        "FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_S3_ENDPOINT_URL": DEFAULT_AUDIT_EXPORT_S3_ENDPOINT_URL,
        "FLOW_MEMORY_COMPUTE_ALERT_ROUTING_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_URL": "",
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_SECRET": "",
        "FLOW_MEMORY_COMPUTE_ALERT_WEBHOOK_TIMEOUT_MS": "2000",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_URL": "",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_WEBHOOK_SECRET": "",
        "FLOW_MEMORY_COMPUTE_ERROR_TRACKING_TIMEOUT_MS": "2000",
        "FLOW_MEMORY_COMPUTE_TELEMETRY_EXPORT_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_OTLP_ENDPOINT_URL": "",
        "FLOW_MEMORY_COMPUTE_OTLP_HEADERS": "",
        "FLOW_MEMORY_COMPUTE_OTLP_TIMEOUT_MS": "5000",
        "FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED": "false",
        "FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST": "",
        "FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST": "",
        "FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_REQUIRED": "false",
        "FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_VERIFIED": "false",
        "FLOW_MEMORY_COMPUTE_ECONOMIC_MEMORY_WRITES_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_ADMIN_MUTATIONS_ENABLED": "true",
        "FLOW_MEMORY_COMPUTE_PROVIDER_TIMEOUT_MS": "2000",
        "FLOW_MEMORY_COMPUTE_GLOBAL_PLANNING_TIMEOUT_MS": "10000",
        "FLOW_MEMORY_COMPUTE_MAX_CANDIDATE_ROUTES": "64",
        "FLOW_MEMORY_COMPUTE_MAX_QUOTE_CACHE_ENTRIES": "10000",
        "FLOW_MEMORY_COMPUTE_SETTLEMENT_ENVIRONMENT": "",
        "FLOW_MEMORY_COMPUTE_SETTLEMENT_SECURITY_REVIEW_ID": "",
    }
    if public_api_url:
        values["FLOW_MEMORY_PUBLIC_API_URL"] = public_api_url
    return [env_var(key, value) for key, value in values.items()]


def ensure_service(
    api_key: str,
    owner_id: str,
    region: str,
    repo: str,
    branch: str,
    env_vars: list[dict[str, str]],
) -> dict[str, Any]:
    existing = find_named(api_key, "/services", "service", owner_id, SERVICE_NAME)
    service_details = {
        "runtime": "docker",
        "plan": DEFAULT_SERVICE_PLAN,
        "region": region,
        "numInstances": 1,
        "healthCheckPath": "/healthz",
        "envSpecificDetails": {
            "dockerfilePath": "./Dockerfile.compute-market",
            "dockerContext": ".",
            "dockerCommand": "flow-memory-api --host 0.0.0.0 --port 8765 --require-scopes",
        },
    }
    if ENABLE_RENDER_DISK:
        service_details["disk"] = {"name": "compute-market-audit", "mountPath": "/var/lib/flow-memory/audit", "sizeGB": 10}
    if existing is not None:
        service_id = str(existing["id"])
        render_request(api_key, "PUT", f"/services/{urllib.parse.quote(service_id)}/env-vars", env_vars)
        return render_request(api_key, "GET", f"/services/{urllib.parse.quote(service_id)}")
    body = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "ownerId": owner_id,
        "repo": repo,
        "branch": branch,
        "autoDeploy": "no",
        "envVars": env_vars,
        "serviceDetails": service_details,
    }
    created = render_request(api_key, "POST", "/services", body)
    return created.get("service", created) if isinstance(created, dict) else created


def public_url(service: dict[str, Any]) -> str:
    details = service.get("serviceDetails", {}) if isinstance(service, dict) else {}
    url = str(details.get("url", "") or "")
    if url and not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def call_json(method: str, url: str, headers: dict[str, str] | None = None, body: Any | None = None) -> tuple[int, Any]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(text) if text.strip() else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(text) if text.strip() else {}
        except Exception:
            return exc.code, {"raw": text}
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        return 0, {"raw": str(exc)}


def smoke_public(base_url: str, api_key_value: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    plan_body = {"task": "public live Level 1 Flow Memory Compute Market smoke test", "dry_run": True}
    checks: dict[str, Any] = {}
    headers_read = {"x-flow-memory-api-key": api_key_value, "x-flow-memory-scopes": "compute:read"}
    headers_plan = {"x-flow-memory-api-key": api_key_value, "x-flow-memory-scopes": "compute:plan"}
    headers_audit = {"x-flow-memory-api-key": api_key_value, "x-flow-memory-scopes": "compute:audit"}
    headers_admin = {"x-flow-memory-api-key": api_key_value, "x-flow-memory-scopes": "compute:admin"}
    checks["root"] = call_json("GET", f"{base}/")
    checks["health"] = call_json("GET", f"{base}/compute/health", headers_read)
    checks["readiness"] = call_json("GET", f"{base}/compute/readiness", headers_read)
    checks["plan"] = call_json("POST", f"{base}/compute/plan", headers_plan, plan_body)
    checks["audit_verify"] = call_json("GET", f"{base}/compute/audit/verify", headers_audit)
    checks["admin_audit_export"] = call_json("GET", f"{base}/admin/audit/export", headers_admin)
    checks["admin_storage_diagnostics"] = call_json("GET", f"{base}/admin/storage/diagnostics", headers_admin)
    checks["admin_redis_diagnostics"] = call_json("GET", f"{base}/admin/redis/diagnostics", headers_admin)
    checks["missing_key"] = call_json("GET", f"{base}/compute/health", {"x-flow-memory-scopes": "compute:read"})
    checks["wrong_scope"] = call_json("POST", f"{base}/compute/plan", headers_read, plan_body)
    health_ok = checks["health"][0] == 200 and checks["health"][1].get("ok") is True
    readiness_payload = checks["readiness"][1].get("data", {}) if isinstance(checks["readiness"][1], dict) else {}
    safety = readiness_payload.get("production_safety_defaults", {})
    storage = readiness_payload.get("storage", {})
    plan_payload = checks["plan"][1].get("data", {}).get("compute_plan", {}) if isinstance(checks["plan"][1], dict) else {}
    audit_ok = checks["audit_verify"][0] == 200 and checks["audit_verify"][1].get("ok") is True
    root_payload = checks["root"][1].get("data", {}) if isinstance(checks["root"][1], dict) else {}
    audit_export_payload = checks["admin_audit_export"][1].get("data", {}) if isinstance(checks["admin_audit_export"][1], dict) else {}
    storage_diag = checks["admin_storage_diagnostics"][1].get("data", {}) if isinstance(checks["admin_storage_diagnostics"][1], dict) else {}
    schema_verification = storage_diag.get("schema_verification", {}) if isinstance(storage_diag, dict) else {}
    advisory_lock_probe = schema_verification.get("advisory_lock_probe", {}) if isinstance(schema_verification, dict) else {}
    redis_diag = checks["admin_redis_diagnostics"][1].get("data", {}) if isinstance(checks["admin_redis_diagnostics"][1], dict) else {}
    ok = all(
        (
            checks["root"][0] == 200,
            root_payload.get("service") == "Flow Memory Compute Market",
            health_ok,
            checks["readiness"][0] == 200,
            readiness_payload.get("ready") is True,
            storage.get("backend") in {"postgres", "postgresql"},
            (safety.get("rate_limit_backend") or readiness_payload.get("rate_limiter_status", {}).get("backend")) == "redis",
            (safety.get("circuit_breaker_backend") or readiness_payload.get("circuit_breaker_status", {}).get("backend")) == "redis",
            safety.get("require_managed_redis_in_production") is True,
            safety.get("redis_url_scheme") == "rediss",
            checks["plan"][0] == 200,
            plan_payload.get("dry_run_only") is True,
            plan_payload.get("funds_moved") is False,
            plan_payload.get("broadcast_allowed") is False,
            plan_payload.get("private_key_required") is False,
            audit_ok,
            checks["admin_audit_export"][0] == 200,
            checks["admin_storage_diagnostics"][0] == 200,
            isinstance(schema_verification, dict),
            schema_verification.get("ok") is True,
            not schema_verification.get("missing_tables", ()),
            not schema_verification.get("missing_indexes", ()),
            isinstance(advisory_lock_probe, dict),
            advisory_lock_probe.get("acquired") is True,
            checks["admin_redis_diagnostics"][0] == 200,
            isinstance(redis_diag, dict),
            redis_diag.get("ok") is True,
            redis_diag.get("rate_limit_probe", {}).get("ok") is True,
            redis_diag.get("circuit_breaker_probe", {}).get("ok") is True,
            redis_diag.get("rate_limit_fail_closed") is True,
            redis_diag.get("circuit_breaker_fail_closed") is True,
            audit_export_payload.get("immutable") is True,
            checks["missing_key"][0] == 401,
            checks["wrong_scope"][0] == 403,
        )
    )
    return {
        "ok": ok,
        "statuses": {name: value[0] for name, value in checks.items()},
        "storage_backend": storage.get("backend"),
        "rate_limit_backend": safety.get("rate_limit_backend") or readiness_payload.get("rate_limiter_status", {}).get("backend"),
        "circuit_breaker_backend": safety.get("circuit_breaker_backend") or readiness_payload.get("circuit_breaker_status", {}).get("backend"),
        "dry_run_only": plan_payload.get("dry_run_only"),
        "funds_moved": plan_payload.get("funds_moved"),
        "broadcast_allowed": plan_payload.get("broadcast_allowed"),
        "private_key_required": plan_payload.get("private_key_required"),
        "audit_export_immutable": audit_export_payload.get("immutable"),
        "admin_storage_diagnostics": checks["admin_storage_diagnostics"][0],
        "admin_redis_diagnostics": checks["admin_redis_diagnostics"][0],
        "redis_url_scheme": safety.get("redis_url_scheme"),
    }


def infer_owner_id(api_key: str, owner_id: str) -> str:
    if owner_id:
        return owner_id
    owners = render_request(api_key, "GET", "/owners?limit=100")
    candidates = [item.get("owner", {}) for item in owners if isinstance(item, dict)]
    candidates = [item for item in candidates if item.get("id")]
    if len(candidates) == 1:
        return str(candidates[0]["id"])
    if not candidates:
        emit("blocked_missing_render_auth", 20, missing_values=["RENDER_OWNER_ID"], reason="api_key_has_no_accessible_render_workspaces")
    emit(
        "blocked_missing_render_auth",
        20,
        missing_values=["RENDER_OWNER_ID"],
        available_workspaces=[{"id": item.get("id"), "name": item.get("name"), "type": item.get("type")} for item in candidates],
    )
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Flow Memory Compute Market Level 1 to Render")
    parser.add_argument("--env-file", default=".env.compute-market.live")
    parser.add_argument("--api-key", default=os.environ.get("RENDER_API_KEY", ""))
    parser.add_argument("--owner-id", default=os.environ.get("RENDER_OWNER_ID", ""))
    parser.add_argument("--region", default=os.environ.get("RENDER_REGION", "oregon"))
    parser.add_argument("--branch", default=os.environ.get("RENDER_BRANCH", ""))
    parser.add_argument("--repo-url", default=os.environ.get("RENDER_REPO_URL", ""))
    args = parser.parse_args()

    if not args.api_key:
        emit("blocked_missing_render_auth", 20, missing_values=["RENDER_API_KEY"])
    env_values = parse_env(Path(args.env_file))
    audit_export_uri = audit_export_uri_from_env(env_values)
    owner_id = infer_owner_id(args.api_key, args.owner_id)

    api_key_value = env_values.get("FLOW_MEMORY_API_KEY", "")
    if not api_key_value or has_placeholder(api_key_value):
        api_key_value = "fmk_live_" + secrets.token_urlsafe(48)

    branch = args.branch or current_branch()
    repo = args.repo_url or public_repo_url()
    assert_branch_is_publishable(branch)

    try:
        postgres = ensure_postgres(args.api_key, owner_id, args.region)
        keyvalue = ensure_keyvalue(args.api_key, owner_id, args.region)
        postgres = wait_available(args.api_key, "/postgres", str(postgres["id"]), "postgres")
        keyvalue = wait_available(args.api_key, "/key-value", str(keyvalue["id"]), "keyvalue")
        pg_conn = render_request(args.api_key, "GET", f"/postgres/{urllib.parse.quote(str(postgres['id']))}/connection-info")
        kv_conn = render_request(args.api_key, "GET", f"/key-value/{urllib.parse.quote(str(keyvalue['id']))}/connection-info")
        env_vars = build_env_vars(
            api_key_value,
            str(pg_conn["internalConnectionString"]),
            str(kv_conn["internalConnectionString"]),
            audit_export_uri=audit_export_uri,
        )
        service = ensure_service(args.api_key, owner_id, args.region, repo, branch, env_vars)
        url = public_url(service)
        if not url:
            service = render_request(args.api_key, "GET", f"/services/{urllib.parse.quote(str(service['id']))}")
            url = public_url(service)
        if not url:
            emit("failed_deployment", 33, public_url="", reason="render_service_url_missing")
        env_vars = build_env_vars(
            api_key_value,
            str(pg_conn["internalConnectionString"]),
            str(kv_conn["internalConnectionString"]),
            url,
            audit_export_uri,
        )
        render_request(args.api_key, "PUT", f"/services/{urllib.parse.quote(str(service['id']))}/env-vars", env_vars)
        trigger_service_deploy(args.api_key, str(service["id"]))
        last_smoke: dict[str, Any] | None = None
        for _ in range(90):
            last_smoke = smoke_public(url, api_key_value)
            if last_smoke.get("ok") is True:
                emit(
                    "public_level_1_live",
                    0,
                    public_url=url,
                    postgres=f"managed_render_postgres:{DEFAULT_POSTGRES_PLAN}",
                    redis=f"managed_render_keyvalue:{DEFAULT_KEYVALUE_PLAN}",
                    service_plan=DEFAULT_SERVICE_PLAN,
                    audit_export_storage="s3_object_lock",
                    smoke="passed",
                    live_settlement_enabled=False,
                    funds_moved=False,
                    private_keys_accepted=False,
                    broadcast_enabled=False,
                )
            time.sleep(10)
        emit("failed_public_smoke_tests", 34, public_url=url, smoke=last_smoke or {})
    except RenderError as exc:
        status = "blocked_render_payment_or_permission" if exc.status in {401, 402, 403} else "failed_deployment"
        emit(status, 40, render_status=exc.status, render_message=exc.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
